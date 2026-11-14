import { artSvg } from '../lib/art.ts';
import { paths } from '../lib/router.ts';
import { esc, formatDayMonth, formatLong, formatMedium, formatTime, html, raw, type Raw } from '../lib/util.ts';
import type { Confidence, ImageRef, SectionId, SourceReference, TimelineEventKind, VerificationState } from '../models.ts';
import { runtime } from '../runtime.ts';

export const sectionLabel = (id: SectionId | 'front'): string =>
  id === 'front' ? 'Front page' : runtime.sections.find((s) => s.id === id)?.label ?? id;

export function storyHref(slug: string, editionDate?: string): string {
  return paths.story(slug) + (editionDate ? `?e=${editionDate}` : '');
}

export function figure(image: ImageRef, opts: { wide?: boolean; ratio?: string; showCredit?: boolean } = {}): Raw {
  const ratio = opts.ratio ?? '16 / 10';
  return html`<figure class="figure${opts.wide ? ' figure--wide' : ''}">
    <div class="figure__frame" style="aspect-ratio:${ratio}">${raw(artSvg(image))}</div>
    <figcaption class="figcaption"><span>${image.caption}</span><span class="credit">${image.credit}</span></figcaption>
  </figure>`;
}

export function demoBanner(): Raw {
  return html`<div class="demo-banner" role="note">
    <strong>Prototype · fictional demo content.</strong>
    Every story, place, source and image here is invented to test the layout. Nothing has been verified. <a href="${paths.about()}" data-link>About the demo</a>
  </div>`;
}

export function shareButton(title: string, label = 'Share'): Raw {
  return html`<button type="button" class="btn btn--ghost" data-share data-title="${title}">
    <svg aria-hidden="true" viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10 13V3M6 7l4-4 4 4M4 11v5h12v-5"/></svg>
    <span>${label}</span></button>`;
}

export function sectionHeading(id: SectionId | 'front', extra?: Raw): Raw {
  return html`<div class="section-head"><h2 class="section-head__title">${sectionLabel(id)}</h2>${extra}</div>`;
}

export function kicker(text: string): Raw {
  return html`<p class="kicker">${text}</p>`;
}

export function dateline(isoDateTime: string, updated?: string): Raw {
  return html`<span class="meta">${formatMedium(isoDateTime)}${formatTime(isoDateTime) ? ` · ${formatTime(isoDateTime)}` : ''}</span>${
    updated ? html`<span class="meta meta--updated">Updated ${formatTime(updated)}</span>` : ''
  }`;
}

const CONFIDENCE_LABEL: Record<Confidence, string> = {
  established: 'Established by several sources',
  reported: 'Reported, limited sourcing',
  disputed: 'Sources disagree',
};

export function confidenceBadge(c: Confidence): Raw {
  return html`<span class="confidence confidence--${c}">${CONFIDENCE_LABEL[c]}</span>`;
}

export const VERIFICATION_LABEL: Record<VerificationState, string> = {
  supported: 'Backed by its sources',
  unverified: 'Cited, not yet checked',
  review_required: 'Thinly sourced',
  disputed: 'Sources disagree',
};

export function verificationBadge(state: VerificationState): Raw {
  return html`<span class="verify verify--${state}">${VERIFICATION_LABEL[state]}</span>`;
}

/** Numbered so that sentence references ([1], [2]) can point at an entry. */
export function sourceList(sources: SourceReference[]): Raw {
  return html`<ol class="sources">${sources.map((s, i) => html`<li id="src-${i + 1}">
      <a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.title}<span class="sr-only"> (opens in a new tab)</span></a>
      <span class="sources__meta">${s.name}${s.publishedAt ? ` · ${formatMedium(s.publishedAt)}` : ''}${s.note ? ` · ${s.note}` : ''}</span>
    </li>`)}</ol>`;
}

export const KIND_LABEL: Record<TimelineEventKind, string> = {
  milestone: 'Milestone',
  report: 'Report',
  update: 'Update',
  correction: 'Correction',
};

export function editionDateLink(date: string, label?: string): Raw {
  return html`<a href="${paths.edition(date)}" data-link>${label ?? formatLong(date)}</a>`;
}

export { formatDayMonth, formatLong, formatMedium, esc, html, raw };
