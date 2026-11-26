/**
 * Page metadata for sharing and search: title, description, canonical link, Open
 * Graph, and `noindex` for personal pages. Personal editions and profiles are never
 * indexable; their canonical link points to the public page.
 */
export interface PageMeta {
  title: string;
  description?: string;
  /** Path of the public, shareable version of this page. */
  canonical?: string;
  noindex?: boolean;
  type?: 'website' | 'article';
}

const DEFAULT_DESCRIPTION = 'PrismUnfold: a finite daily newspaper in which every statement names its source.';

function upsert(selector: string, create: () => HTMLElement, set: (el: HTMLElement) => void): void {
  let el = document.head.querySelector<HTMLElement>(selector);
  if (!el) { el = create(); document.head.appendChild(el); }
  set(el);
}

const meta = (attr: 'name' | 'property', key: string, value: string) =>
  upsert(`meta[${attr}="${key}"]`, () => { const m = document.createElement('meta'); m.setAttribute(attr, key); return m; },
    (el) => el.setAttribute('content', value));

export function applyMeta(m: PageMeta, origin = location.origin): void {
  const title = `${m.title} · PrismUnfold`;
  document.title = title;
  const description = (m.description || DEFAULT_DESCRIPTION).replace(/\s+/g, ' ').slice(0, 300);
  meta('name', 'description', description);
  meta('property', 'og:title', m.title);
  meta('property', 'og:description', description);
  meta('property', 'og:type', m.type ?? 'website');
  meta('property', 'og:site_name', 'PrismUnfold');
  meta('name', 'robots', m.noindex ? 'noindex, nofollow' : 'index, follow');
  const canonical = new URL(m.canonical ?? location.pathname, origin).toString();
  meta('property', 'og:url', canonical);
  upsert('link[rel="canonical"]', () => { const l = document.createElement('link'); l.setAttribute('rel', 'canonical'); return l; },
    (el) => el.setAttribute('href', canonical));
}
