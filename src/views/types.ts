import type { ContentService } from '../content/content-service.ts';
import type { NavKey } from '../components/chrome.ts';
import type { Raw } from '../lib/util.ts';

export interface ViewResult {
  title: string;
  nav: NavKey;
  mode: 'news' | 'magazine';
  body: Raw;
  /** Wire up interactions after the HTML is in the DOM. */
  mount?: (root: HTMLElement) => void;
  /** Date of the latest edition used for the header link. */
  status?: 200 | 404;
}

export type ViewFactory = (svc: ContentService, search: URLSearchParams) => Promise<ViewResult>;
