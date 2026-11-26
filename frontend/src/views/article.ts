/**
 * Article page with progressive unfolding (docs/PRODUCT.md, "Article layers"):
 * 1 Overview · 2 Article · 3 Context · 4 Perspectives · 5 Evidence.
 * Layers 1 and 2 are always open; 3 to 5 unfold on demand and exist only when the
 * edition carries matching data. Nothing missing is filled in by the frontend.
 */
import {
  ACCESS_LABEL, authorHref, dailyFigure, displayable, providerLabel, sourceEntries,
} from '../components/daily-ui.ts';
import { formatLong, formatMedium, html, shareButton } from '../components/ui.ts';
import { humanize, placed, recentDaily, uniqueBy } from '../content/collect.ts';
import type { ContentService } from '../content/content-service.ts';
import { isSavedItem, loadProfile, recordRead, toggleFollow, toggleSaved } from '../lib/profile.ts';
import { paths } from '../lib/router.ts';
import type { Raw } from '../lib/util.ts';
import type { DailyArticle, DailyEdition } from '../models-daily.ts';
import type { ViewResult } from './types.ts';

const BASIS: Record<string, string> = {
  validated: 'every paragraph had an openly reachable source when published',
  approved: 'approved by an editor after review',
  upstream_published: 'published by the bulletin’s editors upstream',
  manually_approved: 'approved by a PrismUnfold editor although upstream marked it unverified',
};

function body(a: DailyArticle): Raw {
  const number = new Map(a.sources.map((s, i) => [s.id, i + 1]));
  return html`${a.paragraphs.map((p) => html`${p.heading ? html`<h2 class="story__h2">${p.heading}</h2>` : ''}<p class="${p.reviewRequired ? 'para para--review' : 'para'}">${p.text}${
    p.sourceIds.map((id) => { const n = number.get(id); return n ? html`<sup class="cite"><a href="#src-${n}" data-cite="src-${n}" aria-label="Source ${n}">${n}</a></sup>` : ''; })}${
    p.reviewRequired ? html` <span class="mark mark--review_required">No openly reachable source</span>` : ''}</p>`)}`;
}

function layer(id: string, title: string, count: number, content: Raw, open = false, label = String(count)): Raw {
  if (!count) return html``;
  return html`<details class="layer" id="${id}"${open ? html` open` : ''}>
    <summary class="layer__summary"><span class="layer__name">${title}</span><span class="layer__count">${label}</span></summary>
    <div class="layer__body">${content}</div>
  </details>`;
}

function evidence(a: DailyArticle, e: DailyEdition): Raw {
  const p = a.provenance;
  const hidden = a.images.filter((i) => !displayable(i));
  const access = a.verification.sourceAccess.map((s) => ACCESS_LABEL[s] ?? s);
  return html`<h3 class="assess__sub">Sources and original reporting</h3>
    ${a.sources.length ? sourceEntries(a.sources) : html`<p class="hint">This contribution came without original source links. It cannot be checked against them.</p>`}
    ${p.citationLevel === 'item' ? html`<p class="hint">Sources are cited for the article as a whole, not per paragraph.</p>` : ''}
    <h3 class="assess__sub">What was checked</h3>
    <ul class="assess__list">
      <li>Source links: ${access.length ? access.join(', ') : 'not checked'}. This shows whether a document could be opened, not whether it supports the text.</li>
      <li>Facts: not independently verified. ${a.reviewRequired ? 'At least one paragraph has no openly reachable source.' : ''}</li>
      <li>Publication: ${BASIS[p.publicationBasis ?? ''] ?? p.publicationBasis ?? 'published with the edition'}.</li>
    </ul>
    <h3 class="assess__sub">Who wrote this</h3>
    <p>${providerLabel(p.provider)}${p.generatedAt ? `, ${formatMedium(p.generatedAt)}` : ''}. ${p.originType === 'ai_secondary'
      ? 'Written by an AI system from the cited sources. Not reviewed line by line by a human editor.' : ''}${
      p.upstreamStatus ? ` Upstream status: ${p.upstreamStatus}.` : ''}</p>
    ${a.limitations.length ? html`<h3 class="assess__sub">Known limitations</h3><ul class="assess__list">${a.limitations.map((l) => html`<li>${LIMITATION[l] ?? l}</li>`)}</ul>` : ''}
    ${hidden.length ? html`<h3 class="assess__sub">Images not shown</h3><ul class="assess__list">${hidden.map((i) => html`<li>${i.caption || i.alt || 'Image'}${
      i.credit ? ` · ${i.credit}` : ''}: rights not cleared for display${i.rightsNote ? ` (${i.rightsNote})` : ''}.</li>`)}</ul>` : ''}
    <p class="hint">Edition of ${formatLong(e.date)} · <a href="${paths.about()}" data-link>How this paper is made</a></p>`;
}

const LIMITATION: Record<string, string> = {
  no_original_sources: 'No original sources were supplied with this contribution.',
  item_level_citations: 'Sources apply to the whole article, not to single paragraphs.',
  ai_curated_secondary: 'AI-curated secondary source; not an independent confirmation.',
};

export async function articleView(svc: ContentService, id: string): Promise<ViewResult> {
  const found = await svc.getArticle(id);
  if (!found) {
    return {
      title: 'Article not found', nav: '', mode: 'news', status: 404,
      body: html`<main id="main" class="page page--narrow" tabindex="-1"><h1 class="page__title">We could not find that article</h1><p><a href="/" data-link>Return to today's edition</a></p></main>`,
    };
  }
  const { article: a, edition: e, parent } = found;
  const recent = a.topic ? await recentDaily(svc) : [];
  const related = a.topic ? placed(recent).filter((p) => p.article.topic === a.topic && p.article.articleId !== a.articleId).slice(0, 6) : [];
  const topicExists = a.topic ? !!(await svc.getTopic(a.topic).catch(() => undefined)) || related.length > 0 : false;
  const magazine = a.kind === 'magazine';
  const image = a.images.find(displayable);
  const profile = loadProfile();
  const following = !!a.topic && profile.follows.topics.includes(a.topic);
  const saved = isSavedItem(a.articleId);

  const background = uniqueBy(a.background, (b) => b.text);
  const contextCount = background.length + a.coverage.length + related.length + (parent ? 1 : 0);
  const perspectivesCount = a.perspectives.length + a.uncertainties.length;
  const overview = a.summary || a.whyItMatters;

  const content = html`<main id="main" tabindex="-1" class="${magazine ? 'reader reader--magazine' : 'reader'}">
    <nav class="breadcrumb" aria-label="Breadcrumb"><a href="${paths.edition(e.date)}" data-link>← Edition of ${formatMedium(e.date)}</a>${
      magazine ? html`<a href="${paths.magazines()}" data-link>Magazine</a>` : ''}</nav>
    <article class="story${magazine ? ' story--magazine' : ''}"${a.language ? html` lang="${a.language}"` : ''}>
      <header class="story__head">
        <p class="kicker">${magazine ? 'Magazine · Background' : a.section}${a.topic ? html` · <a href="${paths.topic(a.topic)}" data-link>${humanize(a.topic)}</a>` : ''}</p>
        <h1 class="story__title">${a.headline}</h1>
        ${a.lead ? html`<p class="story__dek">${a.lead}</p>` : ''}
        <div class="story__meta">
          <span class="meta meta--by">${a.authors?.length ? a.authors.map((x, i) => html`${i ? ', ' : ''}<a href="${authorHref(x.name)}" data-link>${x.name}</a>`) : html`<a href="${authorHref(a.provenance.provider)}" data-link>${providerLabel(a.provenance.provider)}</a>`}</span>
          <span class="meta">${formatMedium(e.date)}</span>
          ${a.updatedAt ? html`<span class="meta meta--updated">Updated ${formatMedium(a.updatedAt)}</span>` : ''}
          <span class="story__actions">
            <button type="button" class="btn btn--ghost" data-save aria-pressed="${saved ? 'true' : 'false'}">${saved ? 'Saved' : 'Save'}</button>
            ${a.topic ? html`<button type="button" class="btn btn--ghost" data-follow-topic="${a.topic}" aria-pressed="${following ? 'true' : 'false'}">${following ? 'Following topic' : 'Follow topic'}</button>` : ''}
            ${shareButton(a.headline)}
          </span>
        </div>
      </header>
      ${overview ? html`<section class="glance" aria-labelledby="glance-h"><h2 id="glance-h" class="glance__title">At a glance</h2>
        ${a.summary ? html`<p><strong>What happened.</strong> ${a.summary}</p>` : ''}
        ${a.whyItMatters ? html`<p><strong>Why it matters.</strong> ${a.whyItMatters}</p>` : ''}</section>` : ''}
      ${a.reviewRequired ? html`<p class="notice notice--review" role="note"><strong>Needs review.</strong> At least one paragraph has no openly reachable source. Read it as reported, not as confirmed.</p>` : ''}
      ${image ? dailyFigure(image, { wide: true, ratio: magazine ? '21 / 9' : '16 / 9' }) : ''}
      <div class="story__body${magazine ? ' mag-body' : ''}">${body(a)}</div>
      ${a.corrections?.length ? html`<aside class="correction" aria-labelledby="corr-h"><h2 id="corr-h" class="correction__title">Correction${a.corrections.length > 1 ? 's' : ''}</h2>
        ${a.corrections.map((c) => html`<p><strong>${formatMedium(c.date)}.</strong> ${c.text}</p>`)}</aside>` : ''}

      <section class="unfold" aria-label="Unfold this story">
        <p class="unfold__intro">Unfold for more</p>
        ${layer('context', 'Context', contextCount, html`
          ${background.map((b) => html`<div class="ctx">${b.heading ? html`<h3 class="assess__sub">${b.heading}</h3>` : ''}<p>${b.text}</p>${
            b.sources.length ? html`<p class="hint">${b.sources.map((s, i) => html`${i ? ', ' : ''}<a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.publisher || s.title}</a>`)}</p>` : ''}</div>`)}
          ${parent ? html`<p>This is one contributor’s account. The main article: <a href="${paths.article(parent.articleId)}" data-link>${parent.headline}</a>.</p>` : ''}
          ${a.coverage.length ? html`<h3 class="assess__sub">Other contributors on the same event</h3><ul class="plain-list">${a.coverage.map((c) => html`<li>
            <a href="${paths.article(c.articleId)}" data-link>${c.headline}</a> <span class="hint">· ${providerLabel(c.provenance.provider)}${
            c.uncertainties.length ? ` · ${c.uncertainties.length} open question${c.uncertainties.length > 1 ? 's' : ''}` : ''}</span></li>`)}</ul>` : ''}
          ${related.length ? html`<h3 class="assess__sub">Earlier reporting on this topic</h3><ul class="plain-list">${related.map((r) => html`<li>
            <a href="${paths.article(r.article.articleId)}" data-link>${r.article.headline}</a> <span class="hint">· ${formatMedium(r.date)}</span></li>`)}</ul>` : ''}
          ${a.topic && topicExists ? html`<p><a class="btn" href="${paths.topic(a.topic)}" data-link>Open the dossier: ${humanize(a.topic)}</a></p>` : ''}`)}
        ${layer('perspectives', 'Perspectives', perspectivesCount, html`
          ${a.perspectives.map((p) => html`<div class="persp"><h3 class="persp__label">${p.label || 'Position'}${p.attribution ? html` <span class="hint">· ${p.attribution}</span>` : ''}</h3>
            <p>${p.text}</p>${p.sources.length ? html`<p class="hint">${p.sources.map((s, i) => html`${i ? ', ' : ''}<a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.publisher || s.title}</a>`)}</p>` : ''}</div>`)}
          ${a.uncertainties.length ? html`<h3 class="assess__sub">What is not known</h3><ul class="assess__list">${a.uncertainties.map((u) => html`<li>${u}</li>`)}</ul>` : ''}
          <p class="hint">Perspectives are shown when the reporting contains them. None are added for balance.</p>`)}
        ${layer('evidence', 'Evidence and transparency', 1, evidence(a, e), false, `${a.sources.length} source${a.sources.length === 1 ? '' : 's'}`)}
      </section>
    </article>
  </main>`;

  return {
    title: a.headline, nav: magazine ? 'magazine' : 'today', mode: magazine ? 'magazine' : 'news', body: content,
    meta: { description: a.summary ?? a.lead, canonical: paths.article(a.articleId), type: 'article' },
    mount(root) {
      recordRead(a.articleId);
      const save = root.querySelector<HTMLButtonElement>('[data-save]');
      save?.addEventListener('click', () => {
        const on = toggleSaved({ id: a.articleId, title: a.headline, href: paths.article(a.articleId) });
        save.textContent = on ? 'Saved' : 'Save';
        save.setAttribute('aria-pressed', String(on));
      });
      const follow = root.querySelector<HTMLButtonElement>('[data-follow-topic]');
      follow?.addEventListener('click', () => {
        const on = toggleFollow('topics', follow.dataset['followTopic'] ?? '');
        follow.textContent = on ? 'Following topic' : 'Follow topic';
        follow.setAttribute('aria-pressed', String(on));
      });
    },
  };
}
