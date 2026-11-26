/**
 * The World: the public, continuously updated newspaper of significant events.
 * Not personalised. Uses the same canonical articles as the daily editions; an
 * event that continues over several days appears once, with its newest article and
 * a link to its dossier.
 */
import { itemTeaser, leadTeaser, secondaryTeaser } from '../components/daily-ui.ts';
import { formatMedium, html, storyHref } from '../components/ui.ts';
import { humanize, placed, recentDaily, topicsOf, type Placed } from '../content/collect.ts';
import type { ContentService } from '../content/content-service.ts';
import { clusterKey, fromArticle, regionsForSection } from '../lib/composer.ts';
import { paths } from '../lib/router.ts';
import { allArticles } from '../models-daily.ts';
import type { ViewResult } from './types.ts';

const REGION_TITLE: [string, string][] = [['GLOBAL', 'World'], ['CH', 'Switzerland'], ['PE', 'Peru'], ['', 'More regions']];

export async function worldView(svc: ContentService): Promise<ViewResult> {
  const [editions, feed] = await Promise.all([recentDaily(svc), svc.getLatestEdition()]);
  const items: (Placed & { importance: number })[] = [];
  for (const e of editions) {
    const list = allArticles(e).filter((a) => a.kind === 'news');
    list.forEach((a, i) => items.push({ article: a, date: e.date, importance: fromArticle(a, i, list.length, e.mainHeadline?.articleId).importance }));
  }
  // Newest article per event: a topic or a headline cluster.
  const seen = new Set<string>();
  const current = [...items].sort((a, b) => b.date.localeCompare(a.date) || b.importance - a.importance)
    .filter((p) => { const k = p.article.topic ?? clusterKey(p.article.headline); return !seen.has(k) && !!seen.add(k); })
    .slice(0, 30);
  const ranked = [...current].sort((a, b) => b.importance - a.importance || b.date.localeCompare(a.date) || a.article.articleId.localeCompare(b.article.articleId));
  const [lead, ...rest] = ranked;
  const major = rest.slice(0, 3);
  const others = rest.slice(3);
  const region = (p: Placed) => (p.article.regions?.length ? p.article.regions : regionsForSection(p.article.section))[0] ?? '';
  const groups = REGION_TITLE.map(([code, title]) => ({ title, items: others.filter((p) => (code ? region(p) === code : !REGION_TITLE.some(([c]) => c && c === region(p)))) }))
    .filter((g) => g.items.length);
  const continuing = topicsOf(placed(editions)).filter((t) => t.count > 1).slice(0, 8);

  const body = html`<main id="main" tabindex="-1" class="edition world">
    <header class="page-head">
      <p class="kicker">The World</p>
      <h1 class="page__title">What is happening</h1>
      <p class="page__dek">The public newspaper of significant events, updated with every edition. The same for every reader, not personalised.</p>
    </header>
    ${!lead && !feed ? html`<p class="state state--empty hint">Nothing has been published yet.</p>` : ''}
    ${lead ? html`<section class="front" aria-label="Major developments">
      ${leadTeaser(lead.article, html`<p class="why">${formatMedium(lead.date)}</p>`)}
      <div class="front__side">${major.map((p) => secondaryTeaser(p.article, html`<p class="why">${formatMedium(p.date)}</p>`))}</div>
    </section>` : ''}
    ${continuing.length ? html`<section class="continuing" aria-labelledby="cont-h">
      <h2 id="cont-h" class="small-head">Continuing coverage</h2>
      <ul class="continuing__list">${continuing.map((t) => html`<li><a href="${paths.topic(t.slug)}" data-link>${humanize(t.slug)}</a>
        <span class="hint">${t.count} articles · since ${formatMedium(t.first)}</span></li>`)}</ul>
    </section>` : ''}
    ${groups.map((g) => html`<section class="section" aria-label="${g.title}">
      <div class="section-head"><h2 class="section-head__title">${g.title}</h2></div>
      <div class="section__grid">${g.items.map((p) => itemTeaser(p.article, html`<p class="why">${formatMedium(p.date)}</p>`))}</div>
    </section>`)}
    ${feed?.placements.length ? html`<section class="section section--wire" aria-labelledby="wire-h">
      <div class="section-head"><h2 id="wire-h" class="section-head__title">From the newsroom</h2></div>
      <p class="hint">Stories assembled by the feed desk and research agents, ${formatMedium(feed.date)}.</p>
      <ul class="plain-list">${[...feed.placements].sort((a, b) => a.order - b.order).slice(0, 8).map((p) => html`<li>
        <a href="${storyHref(p.storySlug, feed.date)}" data-link>${p.snapshot.headline}</a></li>`)}</ul>
    </section>` : ''}
  </main>`;
  return { title: 'The World', nav: 'world', mode: 'news', body,
    meta: { description: 'The public newspaper of significant events, the same for every reader.', canonical: paths.world() } };
}
