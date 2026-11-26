/**
 * Routes (docs/PRODUCT.md, "Routes"). Pure path-to-route mapping, DOM-free for tests.
 * Old URLs stay valid: /morgenbriefing… and /preferences redirect to their successors.
 */
export type Route =
  | { name: 'today'; date?: string }
  | { name: 'article'; id: string }
  | { name: 'world' }
  | { name: 'archive' }
  | { name: 'story'; slug: string }
  | { name: 'topics' }
  | { name: 'topic'; slug: string }
  | { name: 'magazine'; slug: string }
  | { name: 'magazines' }
  | { name: 'author'; slug: string }
  | { name: 'me' }
  | { name: 'about' }
  | { name: 'redirect'; to: string }
  | { name: 'legacyArticle'; date: string; index: number }
  | { name: 'notfound'; path: string };

const SLUG = /^[\w-]{1,160}$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export function matchRoute(pathname: string): Route {
  const path = pathname.replace(/\/+$/, '') || '/';
  let seg: string[];
  try {
    seg = path.split('/').filter(Boolean).map(decodeURIComponent);
  } catch {
    return { name: 'notfound', path };
  }
  const [a, b, c, d] = seg;
  const n = seg.length;
  if (n === 0) return { name: 'today' };
  if (a === 'edition' && n === 2 && b) return b === 'today' ? { name: 'today' } : { name: 'today', date: b };
  if (a === 'article' && n === 2 && b && SLUG.test(b)) return { name: 'article', id: b };
  if (a === 'world' && n === 1) return { name: 'world' };
  if (a === 'archive' && n === 1) return { name: 'archive' };
  if (a === 'story' && n === 2 && b) return { name: 'story', slug: b };
  if (a === 'topics' && n === 1) return { name: 'topics' };
  if (a === 'topic' && n === 2 && b) return { name: 'topic', slug: b };
  if (a === 'magazine' && n === 1) return { name: 'magazines' };
  if (a === 'magazine' && n === 2 && b) return { name: 'magazine', slug: b };
  if (a === 'author' && n === 2 && b && SLUG.test(b)) return { name: 'author', slug: b };
  if (a === 'me' && n === 1) return { name: 'me' };
  if (a === 'about' && n === 1) return { name: 'about' };
  // Compatibility with 0.2 URLs.
  if (a === 'preferences' && n === 1) return { name: 'redirect', to: '/me' };
  if (a === 'morgenbriefing' && n === 1) return { name: 'redirect', to: '/' };
  if (a === 'morgenbriefing' && n === 2 && b && DATE.test(b)) return { name: 'redirect', to: `/edition/${b}` };
  if (a === 'morgenbriefing' && n === 4 && b && DATE.test(b) && c === 'artikel' && d && /^\d{1,3}$/.test(d)) {
    return { name: 'legacyArticle', date: b, index: Number(d) };
  }
  return { name: 'notfound', path };
}

export const paths = {
  today: () => '/',
  edition: (date: string) => `/edition/${date}`,
  article: (id: string) => `/article/${encodeURIComponent(id)}`,
  world: () => '/world',
  archive: () => '/archive',
  story: (slug: string) => `/story/${slug}`,
  topics: () => '/topics',
  topic: (slug: string) => `/topic/${encodeURIComponent(slug)}`,
  magazine: (slug: string) => `/magazine/${slug}`,
  magazines: () => '/magazine',
  author: (slug: string) => `/author/${encodeURIComponent(slug)}`,
  me: () => '/me',
  preferences: () => '/me',
  about: () => '/about',
};

export function slugify(text: string): string {
  return text.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80) || 'unknown';
}
