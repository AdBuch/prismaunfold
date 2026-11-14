import { siteFooter, siteHeader } from './components/chrome.ts';
import { ContentError, type ContentService } from './content/content-service.ts';
import { matchRoute } from './lib/router.ts';
import { runtime } from './runtime.ts';
import { aboutView, errorView, notFoundView } from './views/about.ts';
import { archiveView } from './views/archive.ts';
import { editionView } from './views/edition.ts';
import { magazineView, magazinesView } from './views/magazine.ts';
import { preferencesView } from './views/preferences.ts';
import { storyView } from './views/story.ts';
import { topicView } from './views/topic.ts';
import type { ViewResult } from './views/types.ts';

const LOADING_DELAY_MS = 250;

/**
 * Starts the app with the given content source. The entry points decide which one:
 * `entry-api.ts` reads the pipeline's JSON API, `entry-demo.ts` the fictional fixtures.
 */
export function boot(content: ContentService, options: { demo: boolean }): void {
  runtime.demo = options.demo;
  const app = document.getElementById('app') as HTMLElement;
  const announcer = document.getElementById('announcer') as HTMLElement;
  let renderToken = 0;

  async function resolve(pathname: string, search: URLSearchParams): Promise<ViewResult> {
    const route = matchRoute(pathname);
    switch (route.name) {
      case 'edition': return editionView(content, route.date);
      case 'archive': return archiveView(content);
      case 'story': return storyView(content, route.slug, search);
      case 'topic': return topicView(content, route.slug);
      case 'magazine': return magazineView(content, route.slug);
      case 'magazines': return magazinesView(content);
      case 'preferences': return preferencesView(content);
      case 'about': return aboutView();
      default: return notFoundView(route.path);
    }
  }

  async function render(): Promise<void> {
    const token = ++renderToken;
    // Only show a loading state when loading is slow enough to notice.
    const loading = window.setTimeout(() => {
      if (token !== renderToken) return;
      app.setAttribute('aria-busy', 'true');
      const view = app.querySelector<HTMLElement>('.view');
      if (view) view.classList.add('view--loading');
      else app.innerHTML = '<p class="loading">Loading the edition…</p>';
    }, LOADING_DELAY_MS);

    let view: ViewResult;
    let latestDate: string | undefined;
    try {
      // Section labels are needed by every view, so they load first.
      runtime.sections = (await content.getSiteInfo()).sections;
      view = await resolve(location.pathname, new URLSearchParams(location.search));
      latestDate = (await content.getLatestEdition())?.date;
    } catch (err) {
      const message = err instanceof ContentError ? err.message : 'An unexpected error occurred.';
      if (!(err instanceof ContentError)) console.error(err);
      view = errorView(message);
    } finally {
      window.clearTimeout(loading);
    }
    if (token !== renderToken) return; // a newer navigation superseded this one

    const paint = () => {
      document.documentElement.dataset['mode'] = view.mode;
      app.removeAttribute('aria-busy');
      app.innerHTML = `${siteHeader(view.nav, latestDate).value}<div class="view">${view.body.value}</div>${siteFooter().value}`;
      document.title = `${view.title} · PrismUnfold`;
      window.scrollTo(0, 0);
      view.mount?.(app);
      announcer.textContent = `${view.title} loaded`;
      app.querySelector<HTMLElement>('#main')?.focus({ preventScroll: true });
    };

    type Transition = { ready: Promise<void>; finished: Promise<void>; updateCallbackDone: Promise<void> };
    const doc = document as Document & { startViewTransition?: (cb: () => void) => Transition };
    if (doc.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const t = doc.startViewTransition(paint);
      // A newer navigation may skip this transition; that is expected, not an error.
      for (const promise of [t.ready, t.finished, t.updateCallbackDone]) promise.catch(() => undefined);
    } else paint();
  }

  function navigate(path: string, replace = false): void {
    if (path === location.pathname + location.search) { void render(); return; }
    history[replace ? 'replaceState' : 'pushState']({}, '', path);
    void render();
  }

  function toast(message: string): void {
    let el = document.getElementById('toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'toast';
      el.setAttribute('role', 'status');
      document.body.appendChild(el);
    }
    el.textContent = message;
    el.classList.add('toast--show');
    window.setTimeout(() => el?.classList.remove('toast--show'), 2600);
  }

  async function share(title: string): Promise<void> {
    const url = new URL(location.pathname + location.search, location.origin).toString();
    const nav = navigator as Navigator & { share?: (d: ShareData) => Promise<void> };
    try {
      if (nav.share) { await nav.share({ title, url }); return; }
    } catch { /* user cancelled the native sheet */ return; }
    try {
      await navigator.clipboard.writeText(url);
      toast('Link copied to clipboard');
    } catch {
      window.prompt('Copy this link', url);
    }
  }

  document.addEventListener('click', (ev) => {
    const target = ev.target as HTMLElement | null;
    if (!target) return;
    if (target.closest('[data-retry]')) { void render(); return; }
    if (target.closest('a.skip')) { ev.preventDefault(); document.getElementById('main')?.focus(); return; }
    const shareBtn = target.closest<HTMLElement>('[data-share]');
    if (shareBtn) { void share(shareBtn.dataset['title'] ?? document.title); return; }
    if (target.closest('[data-top]')) { ev.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }); return; }
    // In-page source references: jump without touching the history, which would re-render.
    const cite = target.closest<HTMLAnchorElement>('a[data-cite]');
    if (cite) {
      ev.preventDefault();
      const entry = document.getElementById(cite.dataset['cite'] ?? '');
      entry?.scrollIntoView({ block: 'center' });
      entry?.querySelector<HTMLElement>('a')?.focus({ preventScroll: true });
      return;
    }
    const a = target.closest<HTMLAnchorElement>('a[data-link]');
    if (!a || ev.defaultPrevented || ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    const url = new URL(a.href, location.origin);
    if (url.origin !== location.origin) return;
    ev.preventDefault();
    navigate(url.pathname + url.search);
  });

  document.addEventListener('change', (ev) => {
    const t = ev.target as HTMLElement;
    if (t instanceof HTMLSelectElement && t.hasAttribute('data-edition-select')) navigate(`/edition/${t.value}`);
  });

  document.addEventListener('navigate', ((ev: CustomEvent<string>) => navigate(ev.detail)) as EventListener);
  window.addEventListener('popstate', () => void render());
  void render();
}
