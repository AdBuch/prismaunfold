import { html, formatLong, formatMedium, sectionLabel } from '../components/ui.ts';
import type { ContentService } from '../content/content-service.ts';
import { paths } from '../lib/router.ts';
import { isIsoDate } from '../lib/util.ts';
import type { ViewResult } from './types.ts';

/**
 * Every published edition by date. An edition stays as it was published; later
 * corrections are labelled on the article, and later developments live in dossiers.
 */
export async function archiveView(svc: ContentService): Promise<ViewResult> {
  const [daily, feed] = await Promise.all([svc.listDaily(), svc.listEditions()]);
  const dates = [...new Set([...daily.map((d) => d.date), ...feed.map((e) => e.date)])].sort().reverse();
  if (!dates.length) {
    return {
      title: 'Archive', nav: 'archive', mode: 'news',
      body: html`<main id="main" tabindex="-1" class="page page--narrow state state--empty">
        <p class="kicker">Archive</p>
        <h1 class="page__title">No editions yet</h1>
        <p class="page__dek">Past editions are listed here once the first one has been published.</p>
      </main>`,
    };
  }
  const min = dates[dates.length - 1] ?? '';
  const max = dates[0] ?? '';
  const body = html`<main id="main" tabindex="-1" class="page">
    <p class="kicker">Archive</p>
    <h1 class="page__title">Previous editions</h1>
    <p class="page__dek">Every edition is kept as it was published. Corrections are marked on the article; later developments are followed in the dossiers.</p>
    <form class="datepicker" data-archive-form novalidate>
      <label for="archive-date">Go to a date</label>
      <input id="archive-date" name="date" type="date" min="${min}" max="${max}" value="${max}" required aria-describedby="archive-hint">
      <button class="btn" type="submit">Open edition</button>
      <p id="archive-hint" class="hint">Available from ${formatMedium(min)} to ${formatMedium(max)}.</p>
      <p class="form-error" data-archive-error role="alert" hidden></p>
    </form>
    <ol class="archive-list">${dates.map((date) => {
      const d = daily.find((x) => x.date === date);
      const e = feed.find((x) => x.date === date);
      const lead = e?.placements.find((p) => p.slot === 'lead');
      const headline = d?.mainHeadline?.headline ?? lead?.snapshot.headline;
      const counts = [d ? `${d.articleCount} articles` : '', e ? `${e.placements.length} stories` : '', (d?.magazineCount ?? 0) || e?.magazineSlug ? 'feature' : '',
        d?.completeness === 'partial' ? 'partial' : ''].filter(Boolean).join(' · ');
      return html`<li class="archive-item">
        <a href="${paths.edition(date)}" data-link class="archive-item__link">
          <span class="archive-item__date">${formatLong(date)}${e ? html`<small>No. ${e.number}</small>` : ''}</span>
          <span class="archive-item__lead">${lead && !d ? html`<span class="kicker">${sectionLabel(lead.section)}</span>` : ''}${headline ? html`<strong>${headline}</strong>` : ''}
          <span class="archive-item__count">${counts}</span></span>
        </a>
      </li>`;
    })}</ol>
  </main>`;

  return {
    title: 'Archive', nav: 'archive', mode: 'news', body,
    meta: { description: 'Every PrismUnfold edition by date.', canonical: paths.archive() },
    mount(root) {
      const form = root.querySelector<HTMLFormElement>('[data-archive-form]');
      const err = root.querySelector<HTMLElement>('[data-archive-error]');
      form?.addEventListener('submit', (ev) => {
        ev.preventDefault();
        const value = (form.elements.namedItem('date') as HTMLInputElement).value;
        if (!(isIsoDate(value) && dates.includes(value))) {
          if (err) {
            err.hidden = false;
            err.textContent = value ? `There is no edition for ${isIsoDate(value) ? formatMedium(value) : value}. Try ${formatMedium(max)} or choose from the list.` : 'Please pick a date.';
          }
          return;
        }
        document.dispatchEvent(new CustomEvent('navigate', { detail: paths.edition(value) }));
      });
    },
  };
}
