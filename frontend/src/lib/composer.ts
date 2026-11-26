/**
 * Deterministic edition composer (contract: docs/READER_PROFILE.md).
 *
 * Input: canonical articles of the public edition (never copied, only referenced)
 * and a reader profile. Output: an ordered selection with a reason per item,
 * coverage gaps for interests the pool cannot serve, and the reading time used.
 *
 * Guarantees:
 * - The most important developments of the day are always included ("global"),
 *   whatever the interests are.
 * - At most one item per event cluster and a bounded number per section and topic,
 *   so the edition cannot become ten variants of the same story.
 * - A share of the edition (discovery ratio) goes to important items outside the
 *   reader's interests.
 * - Nothing is invented: an interest without content becomes a coverage gap.
 * Same input, same output: ties break on the article id.
 */
import type { ReaderProfile } from './profile.ts';
import { slugify } from './router.ts';

export interface Candidate {
  id: string;
  headline: string;
  section: string;
  kind: string;
  /** Interest keys (politics, science, ...). */
  topics: string[];
  /** Stable topic/dossier slug, used for follows and repetition limits. */
  topicSlug?: string;
  regions: string[];
  /** 0..1 editorial importance. */
  importance: number;
  minutes: number;
  /** Event cluster; items sharing it are variants of one event. */
  cluster: string;
  authors: string[];
  publishers: string[];
  publishedAt?: string;
}

export type Reason = 'global' | 'interest' | 'follow' | 'discovery' | 'recurring';

export interface CoverageGap {
  kind: 'topic' | 'region';
  key: string;
  weight: number;
  available: number;
}

export interface Composition {
  items: { id: string; reason: Reason; score: number }[];
  minutes: number;
  budgetMinutes: number;
  gaps: CoverageGap[];
  /** Candidates left out (budget, diversity or repetition limits). */
  omitted: number;
}

export const GLOBAL_COUNT = 3;
export const GLOBAL_THRESHOLD = 0.7;
const MAX_PER_SECTION = 3;
const MAX_PER_TOPIC = 2;
const GAP_WEIGHT = 0.5;

const topicWeight = (c: Candidate, p: ReaderProfile): number => Math.max(0, ...c.topics.map((t) => p.topicInterests[t] ?? 0));
const regionWeight = (c: Candidate, p: ReaderProfile): number => {
  const w = c.regions.map((r) => p.geographicInterests[r] ?? (r === p.homeRegion && p.homeRegion ? 1 : 0));
  return Math.max(0, ...w);
};
const followed = (c: Candidate, p: ReaderProfile): boolean =>
  (!!c.topicSlug && p.follows.topics.includes(c.topicSlug))
  || c.authors.some((a) => p.follows.authors.includes(a))
  || c.publishers.some((x) => p.follows.publishers.includes(x));

export function score(c: Candidate, p: ReaderProfile, read: Set<string> = new Set()): number {
  const s = 0.45 * c.importance + 0.35 * topicWeight(c, p) + 0.25 * regionWeight(c, p) + (followed(c, p) ? 0.5 : 0)
    - (p.behaviouralPersonalisation && read.has(c.id) ? 0.5 : 0);
  return Math.round(s * 1000) / 1000;
}

/** Code-point order: independent of the browser's locale, so the result is the same everywhere. */
const cmp = (a: string, b: string): number => (a < b ? -1 : a > b ? 1 : 0);

const byPriority = (a: { s: number; c: Candidate }, b: { s: number; c: Candidate }) =>
  b.s - a.s || b.c.importance - a.c.importance || cmp(a.c.id, b.c.id);

export function compose(pool: Candidate[], profile: ReaderProfile, read: Set<string> = new Set()): Composition {
  const unique = [...new Map(pool.map((c) => [c.id, c])).values()];
  const budget = profile.edition.readingTimeMinutes;
  const chosen: { id: string; reason: Reason; score: number }[] = [];
  const clusters = new Set<string>();
  const perSection = new Map<string, number>();
  const perTopic = new Map<string, number>();
  let minutes = 0;

  const fits = (c: Candidate) => !clusters.has(c.cluster)
    && (perSection.get(c.section) ?? 0) < MAX_PER_SECTION
    && (!c.topicSlug || (perTopic.get(c.topicSlug) ?? 0) < MAX_PER_TOPIC);
  const take = (c: Candidate, reason: Reason, s: number) => {
    chosen.push({ id: c.id, reason, score: s });
    clusters.add(c.cluster);
    perSection.set(c.section, (perSection.get(c.section) ?? 0) + 1);
    if (c.topicSlug) perTopic.set(c.topicSlug, (perTopic.get(c.topicSlug) ?? 0) + 1);
    minutes += c.minutes;
  };

  const ranked = unique.map((c) => ({ c, s: score(c, profile, read) }));
  const news = ranked.filter((x) => x.c.kind === 'news');

  // 1. What everyone should know today, independent of interests and budget.
  [...news].sort((a, b) => b.c.importance - a.c.importance || cmp(a.c.id, b.c.id))
    .filter((x) => x.c.importance >= GLOBAL_THRESHOLD).slice(0, GLOBAL_COUNT)
    .forEach((x) => fits(x.c) && take(x.c, 'global', x.s));

  // 2. Recurring sections the reader asked for (magazine, good news).
  for (const kind of ['magazine', 'good_news'] as const) {
    if (!profile.recurringSections.includes(kind)) continue;
    const best = ranked.filter((x) => x.c.kind === kind).sort(byPriority)[0];
    if (best && fits(best.c)) take(best.c, 'recurring', best.s);
  }

  // 3. Interests and follows within the reading-time budget, keeping a discovery share.
  const rest = news.filter((x) => !chosen.some((y) => y.id === x.c.id));
  const interested = rest.filter((x) => topicWeight(x.c, profile) > 0 || regionWeight(x.c, profile) > 0 || followed(x.c, profile)).sort(byPriority);
  const outside = rest.filter((x) => !interested.includes(x)).sort((a, b) => b.c.importance - a.c.importance || cmp(a.c.id, b.c.id));
  // The discovery share is reserved from the time left after the global items.
  const discoveryBudget = Math.max(0, budget - minutes) * profile.edition.discoveryRatio;
  let personal = 0;
  for (const x of interested) {
    // At least one item for the reader's interests, even when the global news filled the budget.
    if (personal > 0 && minutes + x.c.minutes > budget - discoveryBudget) break;
    if (fits(x.c)) { take(x.c, followed(x.c, profile) ? 'follow' : 'interest', x.s); personal += 1; }
  }
  for (const x of outside) {
    if (minutes + x.c.minutes > budget) break;
    if (fits(x.c)) take(x.c, 'discovery', x.s);
  }
  // Fill remaining time with further interests if discovery found nothing to add.
  for (const x of interested) {
    if (chosen.some((y) => y.id === x.c.id)) continue;
    if (minutes + x.c.minutes > budget) break;
    if (fits(x.c)) take(x.c, followed(x.c, profile) ? 'follow' : 'interest', x.s);
  }

  const gaps: CoverageGap[] = [];
  for (const [key, weight] of Object.entries(profile.topicInterests)) {
    if (weight >= GAP_WEIGHT) {
      const available = unique.filter((c) => c.topics.includes(key)).length;
      if (!available) gaps.push({ kind: 'topic', key, weight, available });
    }
  }
  for (const [key, weight] of Object.entries(profile.geographicInterests)) {
    if (weight >= GAP_WEIGHT && key !== 'GLOBAL') {
      const available = unique.filter((c) => c.regions.includes(key)).length;
      if (!available) gaps.push({ kind: 'region', key, weight, available });
    }
  }
  gaps.sort((a, b) => b.weight - a.weight || cmp(a.key, b.key));
  return { items: chosen, minutes: Math.round(minutes), budgetMinutes: budget, gaps, omitted: unique.length - chosen.length };
}

// --- Adapters from canonical content to candidates (interim, docs/PIPELINE_INTERFACE.md) ---

const SECTION_TOPICS: [RegExp, string[]][] = [
  [/politi/i, ['politics']], [/wirtschaft|econom|business/i, ['economy']], [/technolog/i, ['technology']],
  [/wissenschaft|science/i, ['science']], [/gesellschaft|society/i, ['society']], [/krise|konflikt|crisis|conflict/i, ['crises']],
  [/reise|travel/i, ['travel']], [/kultur|culture/i, ['culture']], [/klima|umwelt|environment|climate|energy/i, ['environment']],
  [/international|welt|world/i, ['politics']],
];
const SECTION_REGIONS: [RegExp, string][] = [
  [/schweiz|switzerland/i, 'CH'], [/peru/i, 'PE'], [/international|welt|world|krisen|konflikt/i, 'GLOBAL'],
];

export function topicsForSection(section: string): string[] {
  return [...new Set(SECTION_TOPICS.filter(([re]) => re.test(section)).flatMap(([, t]) => t))];
}
export function regionsForSection(section: string): string[] {
  return SECTION_REGIONS.filter(([re]) => re.test(section)).map(([, r]) => r);
}

export function readingMinutes(words: number): number {
  return Math.max(1, Math.round(words / 230));
}

const words = (...texts: string[]) => texts.join(' ').split(/\s+/).filter(Boolean).length;

export function clusterKey(headline: string, topic?: string): string {
  const tokens = headline.toLowerCase().normalize('NFKD').replace(/[^\p{L}\p{N} ]/gu, ' ').split(/\s+/)
    .filter((t) => t.length > 3).slice(0, 5).sort().join('-');
  return topic ? `${topic}:${tokens}` : tokens;
}

export interface ArticleLike {
  articleId: string; headline: string; section: string; kind: string; lead: string; topic?: string;
  regions?: string[]; importance?: number; paragraphs: { text: string }[];
  authors?: { name: string }[]; sources: { publisher: string }[]; provenance?: { provider: string };
}

/** A canonical daily article as a candidate; `rank` is its position in the public edition. */
export function fromArticle(a: ArticleLike, rank: number, total: number, mainId?: string): Candidate {
  const derived = total > 1 ? 1 - rank / (total - 1) * 0.6 : 1;
  const importance = a.importance ?? (a.articleId === mainId ? 1 : Math.round(derived * 100) / 100);
  return {
    id: a.articleId, headline: a.headline, section: a.section, kind: a.kind === 'news' || !a.kind ? 'news' : a.kind,
    topics: topicsForSection(a.section), topicSlug: a.topic,
    regions: a.regions?.length ? a.regions : regionsForSection(a.section),
    importance, minutes: readingMinutes(words(a.lead, ...a.paragraphs.map((p) => p.text))),
    // Distinct topics are distinct events; within one topic, headline tokens separate events.
    cluster: clusterKey(a.headline, a.topic),
    // Follow keys: author slugs and the contributing provider (docs/READER_PROFILE.md).
    authors: [...(a.authors ?? []).map((x) => slugify(x.name)), ...(a.provenance ? [a.provenance.provider] : [])],
    publishers: [...new Set(a.sources.map((s) => s.publisher).filter(Boolean))],
  };
}
