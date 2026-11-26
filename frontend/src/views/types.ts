import type { ContentService } from '../content/content-service.ts';
import type { NavKey } from '../components/chrome.ts';
import type { PageMeta } from '../lib/meta.ts';
import type { Raw } from '../lib/util.ts';

export interface ViewResult {
  title: string;
  nav: NavKey;
  mode: 'news' | 'magazine';
  body: Raw;
  /** Wire up interactions after the HTML is in the DOM. */
  mount?: (root: HTMLElement) => void;
  status?: 200 | 404;
  /** Description, canonical path and indexing of the page (lib/meta.ts). */
  meta?: Omit<PageMeta, 'title'>;
  /** Replace the URL with this path and render it instead (compatibility routes). */
  redirect?: string;
}

export type ViewFactory = (svc: ContentService, search: URLSearchParams) => Promise<ViewResult>;
