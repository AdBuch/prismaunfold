import type { Edition, MagazineFeature, Section, Story, Topic } from '../models.ts';
import type { AdjacentEditions, ContentService } from './content-service.ts';
import { editions } from './editions.ts';
import { magazines } from './magazines.ts';
import { stories } from './stories.ts';
import { topics } from './topics.ts';

export const SECTIONS: Section[] = [
  { id: 'switzerland', label: 'Switzerland' },
  { id: 'international', label: 'International' },
  { id: 'peru', label: 'Peru' },
  { id: 'society', label: 'Society' },
  { id: 'science', label: 'Science' },
  { id: 'discoveries', label: 'Discoveries' },
  { id: 'underreported', label: 'Underreported' },
];

const wait = <T>(v: T): Promise<T> => Promise.resolve(v);

/** Local-fixture implementation. Swap for an HTTP-backed one later. */
export class FixtureContentService implements ContentService {
  private readonly sortedEditions = [...editions].sort((a, b) => b.date.localeCompare(a.date));

  listSections() { return wait(SECTIONS); }
  listEditions() { return wait(this.sortedEditions); }
  getEdition(date: string) { return wait(this.sortedEditions.find((e) => e.date === date)); }

  getLatestEdition(): Promise<Edition> {
    const latest = this.sortedEditions[0];
    if (!latest) throw new Error('No editions available');
    return wait(latest);
  }

  getAdjacentEditions(date: string): Promise<AdjacentEditions> {
    const asc = [...this.sortedEditions].reverse();
    const i = asc.findIndex((e) => e.date === date);
    const result: AdjacentEditions = {};
    const prev = asc[i - 1];
    const next = asc[i + 1];
    if (i > 0 && prev) result.previous = prev.date;
    if (i >= 0 && next) result.next = next.date;
    return wait(result);
  }

  getStory(slug: string) { return wait(stories.find((s) => s.slug === slug)); }
  getStories(slugs: string[]) {
    return wait(slugs.map((slug) => stories.find((s) => s.slug === slug)).filter((s): s is Story => !!s));
  }
  getRelatedStories(slug: string) {
    const story = stories.find((s) => s.slug === slug);
    return this.getStories(story?.relatedSlugs ?? []);
  }
  getTopic(slug: string): Promise<Topic | undefined> { return wait(topics.find((t) => t.slug === slug)); }
  getMagazine(slug: string): Promise<MagazineFeature | undefined> { return wait(magazines.find((m) => m.slug === slug)); }
  listMagazines() { return wait(magazines); }
  getEditionsForStory(slug: string) {
    return wait(this.sortedEditions.filter((e) => e.placements.some((p) => p.storySlug === slug)));
  }
}

export const content: ContentService = new FixtureContentService();
