import type { Edition, MagazineFeature, Section, SectionId, Story, Topic } from '../models.ts';

export interface AdjacentEditions {
  previous?: string;
  next?: string;
}

/**
 * Boundary between views and data. A future implementation can call a real
 * news backend (HTTP, GraphQL) without touching any view code.
 */
export interface ContentService {
  listSections(): Promise<Section[]>;
  listEditions(): Promise<Edition[]>; // newest first
  getEdition(date: string): Promise<Edition | undefined>;
  getLatestEdition(): Promise<Edition>;
  getAdjacentEditions(date: string): Promise<AdjacentEditions>;
  getStory(slug: string): Promise<Story | undefined>;
  getStories(slugs: string[]): Promise<Story[]>;
  getRelatedStories(slug: string): Promise<Story[]>;
  getTopic(slug: string): Promise<Topic | undefined>;
  getMagazine(slug: string): Promise<MagazineFeature | undefined>;
  listMagazines(): Promise<MagazineFeature[]>;
  /** Editions in which a story was placed. */
  getEditionsForStory(slug: string): Promise<Edition[]>;
}

export const SECTION_ORDER: SectionId[] = [
  'switzerland', 'international', 'peru', 'society', 'science', 'discoveries', 'underreported',
];
