/**
 * The unified daily edition (schema `prismunfold.daily-edition/1`, docs/API.md).
 * One canonical edition per publication date; articles are canonical and are
 * referenced, never copied, by personal editions, the World, dossiers and authors.
 * Optional fields are optional because the pipeline does not provide them yet
 * (docs/PIPELINE_INTERFACE.md); views must show nothing rather than invent them.
 */

export interface DailySource {
  id: string;
  url: string;
  title: string;
  publisher: string;
  publishedAt?: string;
  sourceType?: string;
  access?: string;
  /** reachable | restricted | missing | rate_limited | unavailable | timeout | dns_failure | unsafe | unknown */
  linkStatus?: string;
  /** Planned: author of the original document, when the publisher names one. */
  author?: string;
}

export type ImageOrigin = 'publisher' | 'wikimedia_commons' | 'official' | 'licensed_photo' | 'chart' | 'ai_illustration' | 'unknown';

export interface DailyImage {
  /** Present only when the image may be displayed. */
  url?: string;
  alt: string;
  caption: string;
  credit: string;
  license: string;
  licenseUrl: string;
  rights: string;
  rightsNote: string;
  sourceUrl: string;
  origin: ImageOrigin | string;
  display: boolean;
}

export interface DailyParagraph {
  text: string;
  heading?: string;
  sourceIds: string[];
  reviewRequired: boolean;
}

export interface DailyPerspective {
  text: string;
  label?: string;
  attribution?: string;
  sources: DailySource[];
}

export interface DailyShortItem {
  label?: string;
  text: string;
  attribution?: string;
  reviewRequired: boolean;
  sources: DailySource[];
}

export interface DailyProvenance {
  provider: string;
  originType: 'original_publisher' | 'ai_secondary' | 'editorial_synthesis' | string;
  publicationBasis?: string;
  citationLevel?: 'paragraph' | 'item' | string;
  generatedAt?: string;
  upstreamStatus?: string;
}

export interface DailyCorrection {
  date: string;
  text: string;
}

export interface DailyArticle {
  articleId: string;
  kind: 'news' | 'magazine' | 'good_news' | 'random' | string;
  section: string;
  headline: string;
  lead: string;
  topic?: string;
  paragraphs: DailyParagraph[];
  sources: DailySource[];
  images: DailyImage[];
  perspectives: DailyPerspective[];
  uncertainties: string[];
  background: { heading?: string; text: string; reviewRequired?: boolean; sources: DailySource[] }[];
  reviewRequired: boolean;
  limitations: string[];
  verification: { sourceAccess: string[]; factual: string };
  provenance: DailyProvenance;
  coverage: DailyArticle[];
  storySlug?: string;
  /** Planned fields (docs/PIPELINE_INTERFACE.md). Shown only when present. */
  summary?: string;
  whyItMatters?: string;
  authors?: { name: string; slug?: string; verified?: boolean; publisher?: string }[];
  regions?: string[];
  importance?: number;
  language?: string;
  corrections?: DailyCorrection[];
  updatedAt?: string;
}

export interface DailyEdition {
  schemaVersion: string;
  date: string;
  timezone: string;
  title: string;
  mainHeadline: { articleId: string; headline: string } | null;
  introduction: { text: string; provider: string; originType: string } | null;
  rubrics: { name: string; articleIds: string[] }[];
  articles: DailyArticle[];
  briefs: DailyShortItem[];
  magazine: DailyArticle[];
  goodNews: DailyArticle[];
  randomFacts: DailyShortItem[];
  assessments: DailyShortItem[];
  contributors: { provider: string; originType: string }[];
  transparency: {
    disclosures: string[];
    warnings: string[];
    editorialNote?: string | null;
    completeness: 'complete' | 'partial' | 'unknown' | string;
    independentVerification?: string;
  };
  revision: { publishedAt?: string | null; publicationMode?: string | null; bulletinGeneratedAt?: string | null; bulletinBasis?: string | null };
  /** Planned: edition profile and language of this composition (docs/READER_PROFILE.md). */
  editionProfile?: string;
  language?: string;
  /** True only for the fictional demo fixtures. */
  demo?: boolean;
}

export interface DailyIndexEntry {
  date: string;
  mainHeadline: { articleId: string; headline: string } | null;
  articleCount: number;
  magazineCount: number;
  completeness: string;
  contributors: string[];
  href?: string;
}

/** The date an article id belongs to: ed-YYYY-MM-DD-…, pd-YYYY-MM-DD-…, or YYYY-MM-DD-… */
export function articleDate(articleId: string): string | undefined {
  return /^(?:[a-z]{2}-)?(\d{4}-\d{2}-\d{2})(?:-|$)/.exec(articleId)?.[1];
}

/** Every canonical article of an edition, in reading order, each exactly once. */
export function allArticles(e: DailyEdition): DailyArticle[] {
  const seen = new Set<string>();
  return [...e.articles, ...e.goodNews, ...e.magazine].filter((a) => !seen.has(a.articleId) && seen.add(a.articleId));
}
