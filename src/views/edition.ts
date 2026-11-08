import { figure, html, kicker, sectionHeading, sectionLabel, storyHref, formatLong, formatMedium, shareButton } from '../components/ui.ts';
import type { ContentService } from '../content/content-service.ts';
import { SECTION_ORDER } from '../content/content-service.ts';
import { paths } from '../lib/router.ts';
import { isIsoDate, raw, type Raw } from '../lib/util.ts';
import type { Edition, EditionStoryPlacement } from '../models.ts';
import type { ViewResult } from './types.ts';

function editionNav(edition: Edition, prev: string | undefined, next: string | undefined, all: Edition[]): Raw {
  return html`<nav class="edition-nav" aria-label="Edition navigation">
    ${prev ? html`<a class="edition-nav__step" href="${paths.edition(prev)}" data-link rel="prev"><span aria-hidden="true">←</span> Previous edition<small>${formatMedium(prev)}</small></a>`
      : html`<span class="edition-nav__step edition-nav__step--end">Earliest edition</span>`}
    <div class="edition-nav__select">
      <label for="edition-select">Choose an edition</label>
      <select id="edition-select" data-edition-select>
        ${all.map((e) => html`<option value="${e.date}" ${e.date === edition.date ? raw('selected') : ''}>${formatLong(e.date)} · No. ${e.number}</option>`)}
      </select>
    </div>
    ${next ? html`<a class="edition-nav__step edition-nav__step--next" href="${paths.edition(next)}" data-link rel="next">Next edition <span aria-hidden="true">→</span><small>${formatMedium(next)}</small></a>`
      : html`<span class="edition-nav__step edition-nav__step--end edition-nav__step--next">Latest edition</span>`}
  </nav>`;
}

function leadBlock(p: EditionStoryPlacement, date: string): Raw {
  return html`<article class="lead">
    <a class="lead__media" href="${storyHref(p.storySlug, date)}" data-link tabindex="-1" aria-hidden="true">${p.snapshot.image ? figure(p.snapshot.image, { ratio: '4 / 3' }) : ''}</a>
    ${kicker(sectionLabel(p.section))}
    <h2 class="lead__title"><a href="${storyHref(p.storySlug, date)}" data-link>${p.snapshot.headline}</a></h2>
    <p class="lead__dek">${p.snapshot.teaser}</p>
    <p class="more"><a href="${storyHref(p.storySlug, date)}" data-link>Read the story</a></p>
  </article>`;
}

function secondaryBlock(p: EditionStoryPlacement, date: string): Raw {
  return html`<article class="secondary">
    ${kicker(sectionLabel(p.section))}
    <h3 class="secondary__title"><a href="${storyHref(p.storySlug, date)}" data-link>${p.snapshot.headline}</a></h3>
    <p class="secondary__dek">${p.snapshot.teaser}</p>
  </article>`;
}

function standardBlock(p: EditionStoryPlacement, date: string): Raw {
  return html`<article class="item">
    ${p.snapshot.image ? html`<a class="item__media" href="${storyHref(p.storySlug, date)}" data-link tabindex="-1" aria-hidden="true">${figure(p.snapshot.image, { ratio: '3 / 2' })}</a>` : ''}
    <div class="item__text"><h3 class="item__title"><a href="${storyHref(p.storySlug, date)}" data-link>${p.snapshot.headline}</a></h3>
    <p class="item__dek">${p.snapshot.teaser}</p></div>
  </article>`;
}

export async function editionView(svc: ContentService, param: string): Promise<ViewResult> {
  const all = await svc.listEditions();
  const latest = await svc.getLatestEdition();
  const date = param === 'today' ? latest.date : param;
  const edition = isIsoDate(date) ? await svc.getEdition(date) : undefined;

  if (!edition) {
    return {
      title: 'Edition not found',
      nav: 'archive',
      mode: 'news',
      status: 404,
      body: html`<main id="main" class="page page--narrow" tabindex="-1">
        <h1 class="page__title">No edition for this date</h1>
        <p class="lead__dek">PrismUnfold publishes a curated edition on selected days. Pick one of the editions below.</p>
        <ul class="plain-list">${all.map((e) => html`<li><a href="${paths.edition(e.date)}" data-link>${formatLong(e.date)}</a> · No. ${e.number}</li>`)}</ul>
      </main>`,
    };
  }

  const { previous, next } = await svc.getAdjacentEditions(edition.date);
  const ps = [...edition.placements].sort((a, b) => a.order - b.order);
  const lead = ps.find((p) => p.slot === 'lead');
  const secondaries = ps.filter((p) => p.slot === 'secondary');
  const standard = ps.filter((p) => p.slot === 'standard');
  const magazine = await svc.getMagazine(edition.magazineSlug);
  const isLatest = edition.date === latest.date;
  const total = ps.length;

  const sections = SECTION_ORDER.map((id) => ({ id, items: standard.filter((p) => p.section === id) })).filter((s) => s.items.length);

  const body = html`<main id="main" tabindex="-1" class="edition">
    <section class="edition-bar" aria-labelledby="edition-heading">
      <h1 id="edition-heading" class="edition-bar__date">${formatLong(edition.date)}</h1>
      <p class="edition-bar__meta"><span>${isLatest ? "Today's edition" : 'Archived edition'}</span><span>No. ${edition.number}</span><span>${total} stories · ${edition.briefs.length} briefs · 1 feature</span></p>
      ${editionNav(edition, previous, next, all)}
    </section>
    <p class="editors-note"><span class="editors-note__label">From the editors</span> ${edition.editorsNote}</p>
    <section class="front" aria-label="Front page">
      ${lead ? leadBlock(lead, edition.date) : ''}
      <div class="front__side">${secondaries.map((p) => secondaryBlock(p, edition.date))}</div>
      <aside class="brief" aria-labelledby="brief-heading">
        <h2 id="brief-heading" class="brief__title">In brief</h2>
        <ul>${edition.briefs.map((b) => html`<li><span class="brief__tag">${sectionLabel(b.section)}</span> ${b.text}${b.storySlug ? html` <a href="${storyHref(b.storySlug, edition.date)}" data-link class="brief__more">Read<span class="sr-only"> the related story</span></a>` : ''}</li>`)}</ul>
      </aside>
    </section>
    ${sections.map((s) => html`<section class="section" aria-label="${sectionLabel(s.id)}">
      ${sectionHeading(s.id)}
      <div class="section__grid">${s.items.map((p) => standardBlock(p, edition.date))}</div>
    </section>`)}
    ${magazine ? html`<section class="feature" aria-labelledby="feature-heading">
      <a class="feature__media" href="${paths.magazine(magazine.slug)}" data-link tabindex="-1" aria-hidden="true">${figure(magazine.hero, { ratio: '5 / 4' })}</a>
      <div class="feature__text">
        <p class="kicker kicker--light">Magazine · Background</p>
        <h2 id="feature-heading" class="feature__title"><a href="${paths.magazine(magazine.slug)}" data-link>${magazine.title}</a></h2>
        <p class="feature__dek">${edition.magazineTeaser}</p>
        <p class="feature__meta">${magazine.readingMinutes} minute read · ${magazine.byline}</p>
        <a class="btn btn--light" href="${paths.magazine(magazine.slug)}" data-link>Read the feature</a>
      </div>
    </section>` : ''}
    <section class="end" aria-label="End of edition">
      <p class="end__mark" aria-hidden="true">◆</p>
      <h2 class="end__title">That is the whole edition.</h2>
      <p>No. ${edition.number} ends here. Come back tomorrow, or read yesterday's.</p>
      <div class="end__actions">
        ${previous ? html`<a class="btn" href="${paths.edition(previous)}" data-link>← ${formatMedium(previous)}</a>` : ''}
        ${shareButton(`PrismUnfold edition of ${formatMedium(edition.date)} (demo)`, 'Share this edition')}
        ${next ? html`<a class="btn" href="${paths.edition(next)}" data-link>${formatMedium(next)} →</a>` : ''}
      </div>
    </section>
  </main>`;

  return { title: `Edition of ${formatMedium(edition.date)}`, nav: 'edition', mode: 'news', body };
}
