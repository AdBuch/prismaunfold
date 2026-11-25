import type { Edition, MagazineFeature, Story, Topic } from '../models.ts';
import { ContentError, type AdjacentEditions, type ContentService, type SiteInfo } from './content-service.ts';

type FetchFn = (input: string, init?: { signal?: AbortSignal }) => Promise<Response>;

const SLUG = /^[\w-]{1,120}$/;
const TTL_MS = 60_000;

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const isString = (v: unknown): v is string => typeof v === 'string';

function isEdition(v: unknown): v is Edition {
  return isRecord(v) && isString(v['date']) && /^\d{4}-\d{2}-\d{2}$/.test(v['date'])
    && Array.isArray(v['placements']) && Array.isArray(v['briefs']);
}
function isStory(v: unknown): v is Story {
  return isRecord(v) && isString(v['slug']) && isString(v['headline']) && Array.isArray(v['body'])
    && Array.isArray(v['sources']) && isRecord(v['image']);
}
function isTopic(v: unknown): v is Topic {
  return isRecord(v) && isString(v['slug']) && isString(v['title']) && Array.isArray(v['events']);
}
function isMagazine(v: unknown): v is MagazineFeature {
  return isRecord(v) && isString(v['slug']) && isString(v['title']) && Array.isArray(v['blocks']);
}

/**
 * Reads the static JSON the pipeline exports under /api/v1 (see src/prismunfold/export.py).
 * Responses are cached for a minute, failures are never cached, and every payload is
 * shape-checked before a view sees it.
 */
export class ApiContentService implements ContentService {
  private readonly cache = new Map<string, { at: number; value: Promise<unknown> }>();
  private readonly base: string;
  private readonly fetchFn: FetchFn;
  private readonly timeoutMs: number;

  constructor(base = '/api/v1', fetchFn: FetchFn = (input, init) => fetch(input, init), timeoutMs = 8000) {
    this.base = base.replace(/\/+$/, '');
    this.fetchFn = fetchFn;
    this.timeoutMs = timeoutMs;
  }

  /** Resolves to undefined for a 404, rejects with ContentError for anything else that fails. */
  private get(path: string): Promise<unknown> {
    const hit = this.cache.get(path);
    if (hit && Date.now() - hit.at < TTL_MS) return hit.value;
    const value = this.load(path);
    this.cache.set(path, { at: Date.now(), value });
    value.catch(() => this.cache.delete(path));
    return value;
  }

  private async load(path: string): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    let response: Response;
    try {
      response = await this.fetchFn(`${this.base}/${path}`, { signal: controller.signal });
    } catch {
      throw new ContentError('network', 'The edition could not be loaded. Check your connection and try again.');
    } finally {
      clearTimeout(timer);
    }
    if (response.status === 404) return undefined;
    if (!response.ok) throw new ContentError('network', `The server answered with an error (${response.status}).`);
    try {
      return await response.json();
    } catch {
      throw new ContentError('invalid', 'The server sent content this page cannot read.');
    }
  }

  async getSiteInfo(): Promise<SiteInfo> {
    const raw = await this.get('index.json');
    if (!isRecord(raw)) return { sections: [], languages: [], regions: [] };
    const sections = Array.isArray(raw['sections'])
      ? raw['sections'].filter((s): s is { id: string; label: string } => isRecord(s) && isString(s['id']) && isString(s['label']))
      : [];
    const strings = (v: unknown) => (Array.isArray(v) ? v.filter(isString) : []);
    return {
      sections,
      languages: strings(raw['languages']),
      regions: strings(raw['regions']),
      ...(isString(raw['generatedAt']) ? { generatedAt: raw['generatedAt'] } : {}),
    };
  }

  async listEditions(): Promise<Edition[]> {
    const raw = await this.get('editions.json');
    if (raw === undefined) return [];
    if (!Array.isArray(raw)) throw new ContentError('invalid', 'The list of editions is not readable.');
    return raw.filter(isEdition).sort((a, b) => b.date.localeCompare(a.date));
  }

  async getEdition(date: string): Promise<Edition | undefined> {
    return (await this.listEditions()).find((e) => e.date === date);
  }

  async getLatestEdition(): Promise<Edition | undefined> {
    return (await this.listEditions())[0];
  }

  async getAdjacentEditions(date: string): Promise<AdjacentEditions> {
    const asc = [...(await this.listEditions())].reverse();
    const i = asc.findIndex((e) => e.date === date);
    const result: AdjacentEditions = {};
    const prev = asc[i - 1];
    const next = asc[i + 1];
    if (i > 0 && prev) result.previous = prev.date;
    if (i >= 0 && next) result.next = next.date;
    return result;
  }

  async getStory(slug: string): Promise<Story | undefined> {
    if (!SLUG.test(slug)) return undefined; // never build a request path from an odd slug
    const raw = await this.get(`stories/${encodeURIComponent(slug)}.json`);
    if (raw === undefined) return undefined;
    if (!isStory(raw)) throw new ContentError('invalid', 'This story could not be read.');
    return raw;
  }

  async getStories(slugs: string[]): Promise<Story[]> {
    const found = await Promise.all(slugs.map((s) => this.getStory(s).catch(() => undefined)));
    return found.filter((s): s is Story => !!s);
  }

  async getRelatedStories(slug: string): Promise<Story[]> {
    const story = await this.getStory(slug);
    return this.getStories(story?.relatedSlugs ?? []);
  }

  async getTopic(slug: string): Promise<Topic | undefined> {
    if (!SLUG.test(slug)) return undefined;
    const raw = await this.get(`topics/${encodeURIComponent(slug)}.json`);
    if (raw === undefined) return undefined;
    if (!isTopic(raw)) throw new ContentError('invalid', 'This timeline could not be read.');
    return raw;
  }

  async listMagazines(): Promise<MagazineFeature[]> {
    const raw = await this.get('magazines.json');
    return Array.isArray(raw) ? raw.filter(isMagazine) : [];
  }

  async getMagazine(slug: string): Promise<MagazineFeature | undefined> {
    return (await this.listMagazines()).find((m) => m.slug === slug);
  }

  async getEditionsForStory(slug: string): Promise<Edition[]> {
    return (await this.listEditions()).filter((e) => e.placements.some((p) => p.storySlug === slug));
  }
}
