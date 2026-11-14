/**
 * Typed domain models for the PrismUnfold newspaper.
 * The pipeline's JSON API (site/api/v1) is written in these shapes.
 * Fixture content is fictional demo material and carries `demo: true`.
 */

/**
 * A section of the paper. The demo fixtures use a fixed set; the real pipeline
 * derives sections from the topics it covers, so the id is an open string.
 */
export type SectionId = string;

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
  /** Publisher name. Fictional in the demo fixtures. */
  name: string;
  title: string;
  /** Link to the original report. The demo fixtures use the reserved example.org domain. */
  url: string;
  /** ISO date or date-time; absent when the source gave none. */
  publishedAt?: string;
  note?: string;
}

export type Confidence = 'established' | 'reported' | 'disputed';

/**
 * What is known about a claim. A source link alone never makes a claim `supported`:
 * that needs a check that the source really says so.
 */
export type VerificationState = 'unverified' | 'supported' | 'disputed' | 'review_required';

export interface ClaimVerification {
  state: VerificationState;
  citation: 'structural';
  /** null: links were not opened. */
  sources_reachable: boolean | null;
  support: 'not_checked' | 'supported' | 'not_supported' | 'contradicted';
  independent_publishers: number;
  corroborated: boolean;
}

export interface StoryVerification {
  state: VerificationState;
  checker?: string;
  links_checked?: boolean;
  independent_publishers?: number;
  corroborated_sentences?: number;
  reasons: string[];
}

export interface StorySentence {
  text: string;
  /** Ids of the SourceReference entries backing this sentence. */
  sourceIds: string[];
  verification?: ClaimVerification | null;
}

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
  /** Pipeline content: the text sentence by sentence, each with its sources. */
  sentences?: StorySentence[];
  verification?: StoryVerification;
  /** What is not known. */
  uncertainties?: string[];
  /** Points on which sources contradict each other. */
  disputes?: string[];
  language?: string;
  regions?: string[];
  /** Which writer produced it: an agent name, or "desk" for the feed desk. */
  agent?: string;
  model?: string;
  /** True only for the fictional fixtures; real pipeline content is false. */
  demo: boolean;
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
  /** True only for the fictional fixtures; real pipeline content is false. */
  demo: boolean;
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
  /** True only for the fictional fixtures; real pipeline content is false. */
  demo: boolean;
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
  language?: string;
  regions?: string[];
  verificationState?: VerificationState;
  /** A lone, thinly sourced voice from its region or section, placed on purpose. */
  underreported?: boolean;
  /** The story first ran in an earlier edition and gained sources since. */
  isUpdate?: boolean;
}

export interface Brief {
  id: string;
  section: SectionId;
  text: string;
  storySlug?: string;
  language?: string;
  regions?: string[];
}

export interface Edition {
  id: string;
  date: string; // ISO date, YYYY-MM-DD
  number: number;
  editorsNote: string;
  placements: EditionStoryPlacement[];
  briefs: Brief[];
  /** Absent when the edition carries no feature. */
  magazineSlug?: string;
  magazineTeaser: string;
  /** True only for the fictional fixtures; real pipeline content is false. */
  demo: boolean;
}
