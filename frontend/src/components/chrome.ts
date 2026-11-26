import { paths } from '../lib/router.ts';
import { formatLong, html, type Raw } from '../lib/util.ts';
import { runtime } from '../runtime.ts';
import { demoBanner } from './ui.ts';

/** Six destinations; content types (articles, dossiers, authors) are reached from them. */
export type NavKey = 'today' | 'world' | 'magazine' | 'topics' | 'archive' | 'me' | 'about' | '';

export function siteHeader(active: NavKey, latestDate?: string): Raw {
  const link = (key: NavKey, href: string, label: string) =>
    html`<a href="${href}" data-link ${active === key ? html`aria-current="page"` : ''}>${label}</a>`;
  return html`${runtime.demo ? demoBanner() : ''}
  <header class="masthead">
    <div class="masthead__rule"></div>
    <p class="masthead__dateline">${latestDate ? html`<span>${formatLong(latestDate)}</span>` : ''}<span>Independent journalism · many perspectives</span></p>
    <a class="masthead__name" href="/" data-link aria-label="PrismUnfold, today's edition">
      <span class="masthead__prism" aria-hidden="true"></span>PrismUnfold
    </a>
    <p class="masthead__tag">Personalise access to reality, not reality itself.</p>
    <nav class="masthead__nav" aria-label="Primary">
      ${link('today', '/', 'Today')}
      ${link('world', paths.world(), 'The World')}
      ${link('magazine', paths.magazines(), 'Magazine')}
      ${link('topics', paths.topics(), 'Topics')}
      ${link('archive', paths.archive(), 'Archive')}
      ${link('me', paths.me(), 'My PrismUnfold')}
    </nav>
  </header>`;
}

export function siteFooter(): Raw {
  return html`<footer class="footer">
    <p class="footer__name">PrismUnfold</p>
    <p>A bounded daily edition: it has a beginning and an end. ${runtime.demo
      ? 'Prototype with fictional demo content.'
      : 'Written and assembled by software from cited sources. Source links are checked for access; facts are not independently verified.'}</p>
    <p class="footer__links"><a href="${paths.about()}" data-link>${runtime.demo ? 'About the demo' : 'How this paper is made'}</a> · <a href="${paths.archive()}" data-link>All editions</a> · <a href="${paths.me()}" data-link>Privacy and settings</a> · <a href="#top" data-top>Back to top</a></p>
  </footer>`;
}
