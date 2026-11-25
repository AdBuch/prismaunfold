import type { ArtMotif, ImageRef, SourceReference } from '../models.ts';

export const DEMO_CREDIT = 'PrismUnfold demo artwork (procedural, not a photograph)';

export function img(motif: ArtMotif, seed: number, alt: string, caption: string): ImageRef {
  return { motif, seed, alt, caption, credit: DEMO_CREDIT };
}

/** Builds a clearly fictional source reference on the reserved example.org domain. */
export function src(id: string, name: string, title: string, publishedAt: string, note?: string): SourceReference {
  return { id, name: `${name} (fictional)`, title, url: `https://example.org/demo/${id}`, publishedAt, ...(note ? { note } : {}) };
}

export const AI_NOTE =
  'Demo text drafted with AI assistance for prototype purposes. Fictional; not verified journalism.';
