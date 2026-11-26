/**
 * Topics and dossiers: evolving pages that connect events, chronology, background,
 * perspectives, open questions, sources and corrections. A dossier combines the
 * topic timeline (api/v1/topics/{slug}.json, when it exists) with every canonical
 * article carrying the topic. Background explanations appear once per dossier.
 */
import { authorHref, providerLabel, sourceEntries } from '../components/daily-ui.ts';
import { KIND_LABEL, formatDayMonth, formatMedium, html, kicker, sectionLabel, shareButton, storyHref } from '../components/ui.ts';
import { humanize, placed, recentDaily, topicsOf, uniqueBy } from '../content/collect.ts';
import type { ContentService } from '../content/content-service.ts';
import { loadProfile, toggleFollow } from '../lib/profile.ts';
import { paths } from '../lib/router.ts';
import type { DailySource } from '../models-daily.ts';
import type { ViewResult } from './types.ts';

export async function topicsView(svc: ContentService): Promise<ViewResult> {
  const topics = topicsOf(placed(await recentDaily(svc)));
  const follows = loadProfile().follows.topics;
  const body = html`<main id="main" tabindex="-1" class="page">
    <p class="kicker">Topics</p>
    <h1 class="page__title">Dossiers</h1>
    <p class="page__dek">Subjects PrismUnfold follows over time: what happened, in which order, what is explained and what is still open.</p>
    ${follows.length ? html`<p class="prefs-note">You follow ${follows.map((f, i) => html`${i ? ', ' : ''}<a href="${paths.topic(f)}" data-link>${humanize(f)}</a>`)}.</p>` : ''}
    ${topics.length ? html`<ol class="dossier-index">${topics.map((t) => html`<li class="dossier-index__item">
      <a href="${paths.topic(t.slug)}" data-link class="dossier-index__link">
        <span class="kicker">${t.sections.join(' · ')}</span>
        <strong class="dossier-index__title">${humanize(t.slug)}</strong>
        <span class="dossier-index__latest">Latest: ${t.latest.headline}</span>
        <span class="hint">${t.count} article${t.count > 1 ? 's' : ''} · ${t.first === t.last ? formatMedium(t.last) : `${formatMedium(t.first)} to ${formatMedium(t.last)}`}</span>
      </a></li>`)}</ol>`
      : html`<p class="state state--empty hint">No topic has been tagged in the recent editions yet.</p>`}
  </main>`;
  return { title: 'Topics', nav: 'topics', mode: 'news', body,
    meta: { description: 'Dossiers: subjects PrismUnfold follows over time.', canonical: paths.topics() } };
}

export async function dossierView(svc: ContentService, slug: string): Promise<ViewResult> {
  const [timeline, editions] = await Promise.all([svc.getTopic(slug).catch(() => undefined), recentDaily(svc)]);
  const articles = placed(editions).filter((p) => p.article.topic === slug).sort((a, b) => b.date.localeCompare(a.date));
  if (!timeline && !articles.length) {
    return {
      title: 'Topic not found', nav: 'topics', mode: 'news', status: 404,
      body: html`<main id="main" class="page page--narrow" tabindex="-1"><h1 class="page__title">We could not find that topic</h1><p><a href="${paths.topics()}" data-link>See all topics</a></p></main>`,
    };
  }
  const storySlugs = [...new Set((timeline?.events ?? []).map((e) => e.storySlug).filter((s): s is string => !!s))];
  const stories = await svc.getStories(storySlugs);
  const titles = new Map(stories.map((s) => [s.slug, s.headline]));
  const title = timeline?.title ?? humanize(slug);
  const background = uniqueBy(articles.flatMap((p) => p.article.background), (b) => b.text);
  const perspectives = uniqueBy(articles.flatMap((p) => p.article.perspectives), (x) => x.text);
  const open = uniqueBy(articles.flatMap((p) => p.article.uncertainties.map((u) => ({ u, date: p.date }))), (x) => x.u);
  const corrections = articles.flatMap((p) => (p.article.corrections ?? []).map((c) => ({ ...c, headline: p.article.headline, id: p.article.articleId })));
  const sources = uniqueBy(articles.flatMap((p) => p.article.sources), (s: DailySource) => s.url);
  const authors = uniqueBy(articles.flatMap((p) => p.article.authors ?? []), (a) => a.name);
  const providers = [...new Set(articles.map((p) => p.article.provenance.provider))];
  const following = loadProfile().follows.topics.includes(slug);

  const chronology = [
    ...articles.map((p) => ({ date: p.date, kind: 'report' as const, title: p.article.headline, text: p.article.lead, href: paths.article(p.article.articleId) })),
    ...(timeline?.events ?? []).map((e) => ({ date: e.date, kind: e.kind, title: e.title, text: e.summary,
      href: e.storySlug ? storyHref(e.storySlug, e.editionDate) : e.editionDate ? paths.edition(e.editionDate) : '' })),
  ].sort((a, b) => b.date.localeCompare(a.date));

  const body = html`<main id="main" tabindex="-1" class="page dossier">
    <nav class="breadcrumb" aria-label="Breadcrumb"><a href="${paths.topics()}" data-link>← All topics</a></nav>
    <header class="dossier__head">
      ${kicker(`Dossier${timeline ? ` · ${sectionLabel(timeline.section)}` : articles[0] ? ` · ${articles[0].article.section}` : ''}`)}
      <h1 class="page__title">${title}</h1>
      ${timeline?.summary ? html`<p class="page__dek">${timeline.summary}</p>` : articles[0] ? html`<p class="page__dek">Latest: ${articles[0].article.lead}</p>` : ''}
      <p class="topic__stats">${chronology.length} entries${chronology.length ? ` · ${formatMedium(chronology[chronology.length - 1]!.date)} to ${formatMedium(chronology[0]!.date)}` : ''}${
        corrections.length ? ` · ${corrections.length} correction${corrections.length > 1 ? 's' : ''}` : ''}</p>
      <div class="topic__actions"><button type="button" class="btn" data-follow-topic="${slug}" aria-pressed="${following ? 'true' : 'false'}">${following ? 'Following' : 'Follow this topic'}</button>${shareButton(title, 'Share this dossier')}</div>
    </header>
    <div class="dossier__grid">
      <section class="dossier__main" aria-labelledby="chron-h">
        <h2 id="chron-h" class="small-head">Chronology, newest first</h2>
        <div class="chips" role="group" aria-label="Show">
          <button type="button" class="chip" data-filter="all" aria-pressed="true">All entries</button>
          <button type="button" class="chip" data-filter="milestone report" aria-pressed="false">Milestones and reports</button>
          <button type="button" class="chip" data-filter="update correction" aria-pressed="false">Updates and corrections</button>
        </div>
        <ol class="timeline" data-timeline>${chronology.map((c) => html`<li class="tl tl--${c.kind}" data-kind="${c.kind}">
          <div class="tl__date"><span>${formatDayMonth(c.date)}</span><small>${c.date.slice(0, 4)}</small></div>
          <div class="tl__dot" aria-hidden="true"></div>
          <div class="tl__card"><p class="tl__kind"><span class="tag tag--${c.kind}">${KIND_LABEL[c.kind]}</span></p>
            <h3 class="tl__title">${c.href ? html`<a href="${c.href}" data-link>${titles.get(c.title) ?? c.title}</a>` : c.title}</h3>
            ${c.text ? html`<p class="tl__text">${c.text}</p>` : ''}</div></li>`)}</ol>
      </section>
      <aside class="dossier__side">
        ${background.length ? html`<section><h2 class="small-head">Background</h2>${background.map((b) => html`${b.heading ? html`<h3 class="assess__sub">${b.heading}</h3>` : ''}<p>${b.text}</p>`)}</section>` : ''}
        ${perspectives.length ? html`<section><h2 class="small-head">Interpretations</h2>${perspectives.map((p) => html`<p><strong>${p.label || 'Position'}.</strong> ${p.text}${p.attribution ? html` <span class="hint">· ${p.attribution}</span>` : ''}</p>`)}</section>` : ''}
        ${open.length ? html`<section><h2 class="small-head">Open questions</h2><ul class="assess__list">${open.map((o) => html`<li>${o.u} <span class="hint">· ${formatMedium(o.date)}</span></li>`)}</ul></section>` : ''}
        ${corrections.length ? html`<section><h2 class="small-head">Corrections and updates</h2><ul class="assess__list">${corrections.map((c) => html`<li><strong>${formatMedium(c.date)}.</strong> ${c.text} <a href="${paths.article(c.id)}" data-link>${c.headline}</a></li>`)}</ul></section>` : ''}
        ${authors.length || providers.length ? html`<section><h2 class="small-head">Voices</h2><ul class="plain-list">${authors.map((a) => html`<li><a href="${authorHref(a.name)}" data-link>${a.name}</a>${a.publisher ? html` <span class="hint">· ${a.publisher}</span>` : ''}</li>`)}${
          providers.map((p) => html`<li><a href="${authorHref(p)}" data-link>${providerLabel(p)}</a></li>`)}</ul></section>` : ''}
      </aside>
    </div>
    ${sources.length ? html`<section class="story__sources" aria-labelledby="dsrc-h"><h2 id="dsrc-h" class="small-head">Sources and documents in this dossier</h2>${sourceEntries(sources, 'dsrc')}</section>` : ''}
  </main>`;

  return {
    title: `Dossier: ${title}`, nav: 'topics', mode: 'news', body,
    meta: { description: timeline?.summary ?? `Dossier: ${title}. Chronology, background and open questions.`, canonical: paths.topic(slug) },
    mount(root) {
      root.querySelectorAll<HTMLButtonElement>('[data-filter]').forEach((chip) => chip.addEventListener('click', () => {
        const kinds = (chip.dataset['filter'] ?? 'all').split(' ');
        root.querySelectorAll<HTMLButtonElement>('[data-filter]').forEach((b) => b.setAttribute('aria-pressed', String(b === chip)));
        root.querySelectorAll<HTMLElement>('[data-kind]').forEach((li) => { li.hidden = !kinds.includes('all') && !kinds.includes(li.dataset['kind'] ?? ''); });
      }));
      const btn = root.querySelector<HTMLButtonElement>('[data-follow-topic]');
      btn?.addEventListener('click', () => {
        const on = toggleFollow('topics', slug);
        btn.textContent = on ? 'Following' : 'Follow this topic';
        btn.setAttribute('aria-pressed', String(on));
      });
    },
  };
}
