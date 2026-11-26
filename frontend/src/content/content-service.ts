import type { Edition, MagazineFeature, Section, Story, Topic } from '../models.ts';
import type { DailyArticle, DailyEdition, DailyIndexEntry } from '../models-daily.ts';

export interface AdjacentEditions {
  previous?: string;
  next?: string;
}

/** What the paper currently covers; drives section labels and the preference choices. */
export interface SiteInfo {
  sections: Section[];
  languages: string[];
  regions: string[];
  generatedAt?: string;
}

/** Content could not be loaded. `network`: unreachable or server error. `invalid`: unusable data. */
export class ContentError extends Error {
  readonly kind: 'network' | 'invalid';
  constructor(kind: 'network' | 'invalid', message: string) {
    super(message);
    this.name = 'ContentError';
    this.kind = kind;
  }
}

/**
 * Boundary between views and data. Two implementations exist: `ApiContentService`
 * reads the pipeline's JSON API, `FixtureContentService` serves the fictional demo.
 * Methods reject with `ContentError` when content cannot be loaded.
 */
export interface ContentService {
  getSiteInfo(): Promise<SiteInfo>;
  listEditions(): Promise<Edition[]>; // newest first
  getEdition(date: string): Promise<Edition | undefined>;
  /** Undefined while no edition has been published yet. */
  getLatestEdition(): Promise<Edition | undefined>;
  getAdjacentEditions(date: string): Promise<AdjacentEditions>;
  getStory(slug: string): Promise<Story | undefined>;
  getStories(slugs: string[]): Promise<Story[]>;
  getRelatedStories(slug: string): Promise<Story[]>;
  getTopic(slug: string): Promise<Topic | undefined>;
  getMagazine(slug: string): Promise<MagazineFeature | undefined>;
  listMagazines(): Promise<MagazineFeature[]>;
  /** Editions in which a story was placed. */
  getEditionsForStory(slug: string): Promise<Edition[]>;

  // --- Unified daily edition (api/v1/daily, milestone 0.3) ---
  /** Newest first; empty when the pipeline has not exported any daily edition yet. */
  listDaily(): Promise<DailyIndexEntry[]>;
  getDaily(date: string): Promise<DailyEdition | undefined>;
  /** A canonical article (or a matched coverage contribution) by its id, with its edition. */
  getArticle(articleId: string): Promise<{ article: DailyArticle; edition: DailyEdition; parent?: DailyArticle } | undefined>;
}

/** Shared lookup used by both services: the article id carries its edition date. */
export function findArticle(edition: DailyEdition, articleId: string): { article: DailyArticle; parent?: DailyArticle } | undefined {
  for (const article of [...edition.articles, ...edition.goodNews, ...edition.magazine]) {
    if (article.articleId === articleId) return { article };
    const covered = article.coverage.find((c) => c.articleId === articleId);
    if (covered) return { article: covered, parent: article };
  }
  return undefined;
}
