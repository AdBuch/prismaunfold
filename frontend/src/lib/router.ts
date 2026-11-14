export type Route =
  | { name: 'edition'; date: 'today' | string }
  | { name: 'archive' }
  | { name: 'story'; slug: string }
  | { name: 'topic'; slug: string }
  | { name: 'magazine'; slug: string }
  | { name: 'magazines' }
  | { name: 'preferences' }
  | { name: 'about' }
  | { name: 'notfound'; path: string };

/** Pure path-to-route mapping, kept DOM-free so it can be unit tested. */
export function matchRoute(pathname: string): Route {
  const path = pathname.replace(/\/+$/, '') || '/';
  const seg = path.split('/').filter(Boolean).map(decodeURIComponent);
  const [a, b] = seg;
  if (seg.length === 0) return { name: 'edition', date: 'today' };
  if (a === 'edition' && seg.length === 2 && b) return { name: 'edition', date: b };
  if (a === 'archive' && seg.length === 1) return { name: 'archive' };
  if (a === 'story' && seg.length === 2 && b) return { name: 'story', slug: b };
  if (a === 'topic' && seg.length === 2 && b) return { name: 'topic', slug: b };
  if (a === 'magazine' && seg.length === 1) return { name: 'magazines' };
  if (a === 'magazine' && seg.length === 2 && b) return { name: 'magazine', slug: b };
  if (a === 'preferences' && seg.length === 1) return { name: 'preferences' };
  if (a === 'about' && seg.length === 1) return { name: 'about' };
  return { name: 'notfound', path };
}

export const paths = {
  edition: (date: string) => `/edition/${date}`,
  archive: () => '/archive',
  story: (slug: string) => `/story/${slug}`,
  topic: (slug: string) => `/topic/${slug}`,
  magazine: (slug: string) => `/magazine/${slug}`,
  magazines: () => '/magazine',
  preferences: () => '/preferences',
  about: () => '/about',
};
