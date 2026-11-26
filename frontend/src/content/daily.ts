import type {
  DailyArticle, DailyEdition, DailyImage, DailyIndexEntry, DailyPerspective, DailyShortItem, DailySource,
} from '../models-daily.ts';

/**
 * Shape checks for `api/v1/daily`. Unknown fields are ignored, missing optional
 * collections become empty, and anything that is not text never reaches a view as
 * text. Links that are not http(s) are dropped.
 */
const rec = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const str = (v: unknown, max = 20000): string => (typeof v === 'string' ? v.slice(0, max) : '');
const opt = (v: unknown, max = 2000): string | undefined => (typeof v === 'string' && v ? v.slice(0, max) : undefined);
const list = <T>(v: unknown, f: (x: unknown) => T | undefined, max = 200): T[] =>
  Array.isArray(v) ? v.slice(0, max).map(f).filter((x): x is T => x !== undefined) : [];
const strings = (v: unknown): string[] => list(v, (x) => (typeof x === 'string' ? x.slice(0, 2000) : undefined), 50);
export const safeUrl = (v: unknown): string | undefined => (typeof v === 'string' && /^https?:\/\/[^\s]+$/i.test(v) ? v : undefined);
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const ID = /^[\w.-]{1,160}$/;

function source(v: unknown): DailySource | undefined {
  if (!rec(v)) return undefined;
  const url = safeUrl(v['url']);
  if (!url) return undefined;
  const out: DailySource = { id: str(v['id'], 120) || url, url, title: str(v['title'], 700) || url, publisher: str(v['publisher'], 200) };
  for (const key of ['publishedAt', 'sourceType', 'access', 'linkStatus', 'author'] as const) {
    const value = opt(v[key], 300);
    if (value) out[key] = value;
  }
  return out;
}

function image(v: unknown): DailyImage | undefined {
  if (!rec(v)) return undefined;
  const display = v['display'] === true && !!safeUrl(v['url']) && /^https:\/\//i.test(str(v['url']));
  const out: DailyImage = {
    alt: str(v['alt'], 500), caption: str(v['caption'], 700), credit: str(v['credit'], 400), license: str(v['license'], 250),
    licenseUrl: safeUrl(v['licenseUrl']) ?? '', rights: str(v['rights'], 250), rightsNote: str(v['rightsNote'], 700),
    sourceUrl: safeUrl(v['sourceUrl']) ?? '', origin: str(v['origin'], 40) || 'unknown',
    // Rights decide rendering: without a display grant and a credit there is no URL to render.
    display: display && !!str(v['credit']),
  };
  if (out.display) out.url = str(v['url']);
  return out;
}

function perspective(v: unknown): DailyPerspective | undefined {
  if (!rec(v) || !str(v['text'])) return undefined;
  return { text: str(v['text'], 4000), label: opt(v['label'], 250), attribution: opt(v['attribution'], 250), sources: list(v['sources'], source, 20) };
}

function short(v: unknown): DailyShortItem | undefined {
  if (!rec(v) || !str(v['text'])) return undefined;
  return { label: opt(v['label'], 250), text: str(v['text'], 6000), attribution: opt(v['attribution'], 250),
    reviewRequired: v['reviewRequired'] === true, sources: list(v['sources'], source, 20) };
}

export function article(v: unknown, depth = 0): DailyArticle | undefined {
  if (!rec(v) || !str(v['headline']) || !ID.test(str(v['articleId']))) return undefined;
  const prov = rec(v['provenance']) ? v['provenance'] : {};
  const verification = rec(v['verification']) ? v['verification'] : {};
  const out: DailyArticle = {
    articleId: str(v['articleId']), kind: str(v['kind'], 40) || 'news', section: str(v['section'], 160),
    headline: str(v['headline'], 400), lead: str(v['lead'], 3000), topic: opt(v['topic'], 80),
    paragraphs: list(v['paragraphs'], (p) => rec(p) && str(p['text']) ? {
      text: str(p['text'], 8000), heading: opt(p['heading'], 200), sourceIds: strings(p['sourceIds']), reviewRequired: p['reviewRequired'] === true,
    } : undefined, 80),
    sources: list(v['sources'], source, 80), images: list(v['images'], image, 20), perspectives: list(v['perspectives'], perspective, 40),
    uncertainties: strings(v['uncertainties']),
    background: list(v['background'], (b) => rec(b) && str(b['text']) ? {
      heading: opt(b['heading'], 200), text: str(b['text'], 4000), reviewRequired: b['reviewRequired'] === true, sources: list(b['sources'], source, 20),
    } : undefined, 20),
    reviewRequired: v['reviewRequired'] === true, limitations: strings(v['limitations']),
    verification: { sourceAccess: strings(verification['sourceAccess']), factual: str(verification['factual'], 80) || 'not_independently_verified' },
    provenance: { provider: str(prov['provider'], 60) || 'unknown', originType: str(prov['originType'], 60) || 'ai_secondary',
      publicationBasis: opt(prov['publicationBasis'], 80), citationLevel: opt(prov['citationLevel'], 40),
      generatedAt: opt(prov['generatedAt'], 60), upstreamStatus: opt(prov['upstreamStatus'], 60) },
    coverage: depth < 2 ? list(v['coverage'], (c) => article(c, depth + 1), 20) : [],
    storySlug: /^[\w-]{1,120}$/.test(str(v['storySlug'])) ? str(v['storySlug']) : undefined,
    summary: opt(v['summary'], 2000), whyItMatters: opt(v['whyItMatters'], 2000),
    regions: strings(v['regions']), language: opt(v['language'], 20), updatedAt: opt(v['updatedAt'], 60),
    importance: typeof v['importance'] === 'number' && Number.isFinite(v['importance']) ? Math.max(0, Math.min(1, v['importance'])) : undefined,
    authors: list(v['authors'], (a) => rec(a) && str(a['name']) ? {
      name: str(a['name'], 160), slug: /^[\w-]{1,80}$/.test(str(a['slug'])) ? str(a['slug']) : undefined,
      verified: a['verified'] === true, publisher: opt(a['publisher'], 160),
    } : undefined, 10),
    corrections: list(v['corrections'], (c) => rec(c) && str(c['text']) && DATE.test(str(c['date']).slice(0, 10))
      ? { date: str(c['date'], 30), text: str(c['text'], 2000) } : undefined, 20),
  };
  return out;
}

export function parseDaily(v: unknown): DailyEdition | undefined {
  if (!rec(v) || !DATE.test(str(v['date']))) return undefined;
  const t = rec(v['transparency']) ? v['transparency'] : {};
  const r = rec(v['revision']) ? v['revision'] : {};
  const main = rec(v['mainHeadline']) && str(v['mainHeadline']['articleId'])
    ? { articleId: str(v['mainHeadline']['articleId']), headline: str(v['mainHeadline']['headline'], 400) } : null;
  const intro = rec(v['introduction']) && str(v['introduction']['text'])
    ? { text: str(v['introduction']['text'], 6000), provider: str(v['introduction']['provider'], 60), originType: str(v['introduction']['originType'], 60) } : null;
  return {
    schemaVersion: str(v['schemaVersion'], 80), date: str(v['date']), timezone: str(v['timezone'], 60) || 'Europe/Zurich',
    title: str(v['title'], 200), mainHeadline: main, introduction: intro,
    rubrics: list(v['rubrics'], (x) => rec(x) && str(x['name']) ? { name: str(x['name'], 160), articleIds: strings(x['articleIds']) } : undefined, 40),
    articles: list(v['articles'], (a) => article(a)), briefs: list(v['briefs'], short, 60),
    magazine: list(v['magazine'], (a) => article(a), 20), goodNews: list(v['goodNews'], (a) => article(a), 20),
    randomFacts: list(v['randomFacts'], short, 10), assessments: list(v['assessments'], short, 20),
    contributors: list(v['contributors'], (c) => rec(c) && str(c['provider']) ? { provider: str(c['provider'], 60), originType: str(c['originType'], 60) } : undefined, 20),
    transparency: { disclosures: strings(t['disclosures']), warnings: strings(t['warnings']), editorialNote: opt(t['editorialNote'], 4000) ?? null,
      completeness: str(t['completeness'], 40) || 'unknown', independentVerification: opt(t['independentVerification'], 600) },
    revision: { publishedAt: opt(r['publishedAt'], 60) ?? null, publicationMode: opt(r['publicationMode'], 40) ?? null,
      bulletinGeneratedAt: opt(r['bulletinGeneratedAt'], 60) ?? null, bulletinBasis: opt(r['bulletinBasis'], 60) ?? null },
    editionProfile: opt(v['editionProfile'], 60), language: opt(v['language'], 20), demo: v['demo'] === true,
  };
}

export function parseDailyIndex(v: unknown): DailyIndexEntry[] {
  return list(v, (x) => rec(x) && DATE.test(str(x['date'])) ? {
    date: str(x['date']),
    mainHeadline: rec(x['mainHeadline']) ? { articleId: str(x['mainHeadline']['articleId'], 160), headline: str(x['mainHeadline']['headline'], 400) } : null,
    articleCount: typeof x['articleCount'] === 'number' ? x['articleCount'] : 0,
    magazineCount: typeof x['magazineCount'] === 'number' ? x['magazineCount'] : 0,
    completeness: str(x['completeness'], 40) || 'unknown', contributors: strings(x['contributors']),
  } : undefined, 4000).sort((a, b) => b.date.localeCompare(a.date));
}
