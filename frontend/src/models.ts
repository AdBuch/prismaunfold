/**
 * Typed domain models for the PrismUnfold Phase 2 prototype.
 * All fixture content is fictional demo material (see `demo: true`).
 */

export type SectionId =
  | 'switzerland'
  | 'international'
  | 'peru'
  | 'society'
  | 'science'
  | 'discoveries'
  | 'underreported';

export interface Section {
  id: SectionId;
  label: string;
}

/** Procedural artwork definition; real photography would replace this later. */
export type ArtMotif =
  | 'alpine' | 'sea' | 'terraces' | 'night' | 'trees'
  | 'city' | 'seed' | 'library' | 'market' | 'grid';

export interface ImageRef {
  motif: ArtMotif;
  seed: number;
  alt: string;
  caption: string;
  /** Credit field is required so real photo credits slot in later. */
  credit: string;
}

export interface SourceReference {
  id: string;
  /** Fictional publisher name used for demo purposes. */
  name: string;
  title: string;
  /** Uses reserved example.org domain: never a real publisher link. */
  url: string;
  publishedAt: string; // ISO date
  note?: string;
}

export type Confidence = 'established' | 'reported' | 'disputed';

export interface Correction {
  date: string;
  text: string;
}

export interface Story {
  id: string;
  slug: string;
  section: SectionId;
  headline: string;
  standfirst: string;
  body: string[];
  byline: string;
  aiDisclosure: string;
  publishedAt: string; // ISO date-time
  updatedAt?: string;
  corrections: Correction[];
  sources: SourceReference[];
  confidence: Confidence;
  confidenceNote: string;
  topicSlug?: string;
  relatedSlugs: string[];
  image: ImageRef;
  demo: true;
}

export type TimelineEventKind = 'milestone' | 'report' | 'update' | 'correction';

export interface TimelineEvent {
  id: string;
  date: string; // ISO date
  kind: TimelineEventKind;
  title: string;
  summary: string;
  storySlug?: string;
  /** Link to an older daily edition that carried this development. */
  editionDate?: string;
  sources?: string[]; // SourceReference ids/names, free text in demo
}

export interface Topic {
  slug: string;
  title: string;
  summary: string;
  section: SectionId;
  events: TimelineEvent[];
  image: ImageRef;
  demo: true;
}

export type MagazineBlock =
  | { type: 'p'; text: string; dropcap?: boolean }
  | { type: 'h2'; text: string }
  | { type: 'pullquote'; text: string }
  | { type: 'figure'; image: ImageRef; wide?: boolean }
  | { type: 'sidebar'; title: string; text: string[] }
  | { type: 'chronology'; title: string; steps: { label: string; text: string }[] }
  | { type: 'glossary'; terms: { term: string; text: string }[] };

export interface MagazineFeature {
  slug: string;
  kicker: string;
  title: string;
  standfirst: string;
  byline: string;
  aiDisclosure: string;
  publishedAt: string;
  readingMinutes: number;
  hero: ImageRef;
  blocks: MagazineBlock[];
  relatedStorySlugs: string[];
  relatedFeatureSlugs: string[];
  topicSlug?: string;
  sources: SourceReference[];
  demo: true;
}

/** Snapshot of how a story looked at publication, so old editions stay stable. */
export interface PlacementSnapshot {
  headline: string;
  teaser: string;
  image?: ImageRef;
}

export type PlacementSlot = 'lead' | 'secondary' | 'standard';

export interface EditionStoryPlacement {
  storySlug: string;
  section: SectionId | 'front';
  slot: PlacementSlot;
  order: number;
  snapshot: PlacementSnapshot;
}

export interface Brief {
  id: string;
  section: SectionId;
  text: string;
  storySlug?: string;
}

export interface Edition {
  id: string;
  date: string; // ISO date, YYYY-MM-DD
  number: number;
  editorsNote: string;
  placements: EditionStoryPlacement[];
  briefs: Brief[];
  magazineSlug: string;
  magazineTeaser: string;
  demo: true;
}
