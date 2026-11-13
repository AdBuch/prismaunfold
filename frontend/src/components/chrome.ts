import { paths } from '../lib/router.ts';
import { html, type Raw } from '../lib/util.ts';
import { demoBanner } from './ui.ts';

export type NavKey = 'edition' | 'archive' | 'magazine' | 'about' | '';

export function siteHeader(active: NavKey, latestDate: string): Raw {
  const link = (key: NavKey, href: string, label: string) =>
    html`<a href="${href}" data-link ${active === key ? html`aria-current="page"` : ''}>${label}</a>`;
  return html`${demoBanner()}
  <header class="masthead">
    <div class="masthead__rule"></div>
    <a class="masthead__name" href="/" data-link aria-label="PrismUnfold, today's edition">
      <span class="masthead__prism" aria-hidden="true"></span>PrismUnfold
    </a>
    <p class="masthead__tag">Independent journalism. Many perspectives. One clearer view of the world.</p>
    <nav class="masthead__nav" aria-label="Primary">
      ${link('edition', paths.edition(latestDate), "Today's edition")}
      ${link('archive', paths.archive(), 'Archive')}
      ${link('magazine', paths.magazines(), 'Magazine')}
      ${link('about', paths.about(), 'About')}
    </nav>
  </header>`;
}

export function siteFooter(): Raw {
  return html`<footer class="footer">
    <p class="footer__name">PrismUnfold</p>
    <p>A bounded daily edition: it has a beginning and an end. Phase 2 prototype with fictional demo content.</p>
    <p class="footer__links"><a href="${paths.about()}" data-link>About the demo</a> · <a href="${paths.archive()}" data-link>All editions</a> · <a href="#top" data-top>Back to top</a></p>
  </footer>`;
}
