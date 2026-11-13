import { html, formatLong, formatMedium, sectionLabel } from '../components/ui.ts';
import type { ContentService } from '../content/content-service.ts';
import { paths } from '../lib/router.ts';
import { isIsoDate } from '../lib/util.ts';
import type { ViewResult } from './types.ts';

export async function archiveView(svc: ContentService): Promise<ViewResult> {
  const editions = await svc.listEditions();
  const min = editions[editions.length - 1]?.date ?? '';
  const max = editions[0]?.date ?? '';
  const body = html`<main id="main" tabindex="-1" class="page">
    <p class="kicker">Archive</p>
    <h1 class="page__title">Previous editions</h1>
    <p class="page__dek">Every edition is kept exactly as it was published: the same stories, order and wording.</p>
    <form class="datepicker" data-archive-form novalidate>
      <label for="archive-date">Go to a date</label>
      <input id="archive-date" name="date" type="date" min="${min}" max="${max}" value="${max}" required aria-describedby="archive-hint">
      <button class="btn" type="submit">Open edition</button>
      <p id="archive-hint" class="hint">Available from ${formatMedium(min)} to ${formatMedium(max)}.</p>
      <p class="form-error" data-archive-error role="alert" hidden></p>
    </form>
    <ol class="archive-list">${editions.map((e) => {
      const lead = e.placements.find((p) => p.slot === 'lead');
      return html`<li class="archive-item">
        <a href="${paths.edition(e.date)}" data-link class="archive-item__link">
          <span class="archive-item__date">${formatLong(e.date)}<small>No. ${e.number}</small></span>
          <span class="archive-item__lead">${lead ? html`<span class="kicker">${sectionLabel(lead.section)}</span><strong>${lead.snapshot.headline}</strong>` : ''}
          <span class="archive-item__count">${e.placements.length} stories · ${e.briefs.length} briefs · 1 feature</span></span>
        </a>
      </li>`;
    })}</ol>
  </main>`;

  return {
    title: 'Archive',
    nav: 'archive',
    mode: 'news',
    body,
    mount(root) {
      const form = root.querySelector<HTMLFormElement>('[data-archive-form]');
      const err = root.querySelector<HTMLElement>('[data-archive-error]');
      form?.addEventListener('submit', (ev) => {
        ev.preventDefault();
        const value = (form.elements.namedItem('date') as HTMLInputElement).value;
        const exists = isIsoDate(value) && editions.some((e) => e.date === value);
        if (!exists) {
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
