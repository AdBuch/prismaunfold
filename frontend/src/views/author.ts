/**
 * Voices: author and contributor pages. Records are assembled automatically from
 * article metadata; they are not accounts and imply no affiliation with or
 * endorsement of PrismUnfold. A verified profile requires `verified: true` from the
 * pipeline (planned: accounts controlled by the journalists themselves).
 */
import { PROVIDER_LABEL, providerLabel } from '../components/daily-ui.ts';
import { formatMedium, html } from '../components/ui.ts';
import { humanize, placed, recentDaily, uniqueBy } from '../content/collect.ts';
import type { ContentService } from '../content/content-service.ts';
import { loadProfile, toggleFollow } from '../lib/profile.ts';
import { paths, slugify } from '../lib/router.ts';
import type { ViewResult } from './types.ts';

export async function authorView(svc: ContentService, slug: string): Promise<ViewResult> {
  const items = placed(await recentDaily(svc));
  const isProvider = Object.keys(PROVIDER_LABEL).includes(slug);
  const byAuthor = items.filter((p) => (p.article.authors ?? []).some((a) => slugify(a.name) === slug));
  const byProvider = isProvider ? items.filter((p) => p.article.provenance.provider === slug) : [];
  const list = (byAuthor.length ? byAuthor : byProvider).sort((a, b) => b.date.localeCompare(a.date));
  const author = byAuthor.flatMap((p) => p.article.authors ?? []).find((a) => slugify(a.name) === slug);
  if (!list.length) {
    return {
      title: 'Author not found', nav: '', mode: 'news', status: 404,
      body: html`<main id="main" class="page page--narrow" tabindex="-1"><h1 class="page__title">No record for this name</h1>
        <p>Author pages exist only when recent articles name the author.</p><p><a href="/" data-link>Return to today's edition</a></p></main>`,
    };
  }
  const name = author?.name ?? providerLabel(slug);
  const verified = !!author?.verified;
  const topics = uniqueBy(list.map((p) => p.article.topic).filter((t): t is string => !!t), (t) => t);
  const publishers = uniqueBy(list.flatMap((p) => p.article.authors ?? []).filter((a) => slugify(a.name) === slug && a.publisher).map((a) => a.publisher as string), (x) => x);
  const following = loadProfile().follows.authors.includes(slug);

  const body = html`<main id="main" tabindex="-1" class="page page--narrow author">
    <p class="kicker">Voices</p>
    <h1 class="page__title">${name}</h1>
    ${isProvider && !author ? html`<p class="page__dek">An AI system contributing to PrismUnfold. It writes from cited sources; it is not a journalist and not a person.</p>`
      : html`<p class="page__dek">${publishers.length ? `Cited as the author of reporting for ${publishers.join(', ')}.` : 'Named as the author in reporting PrismUnfold cites.'}</p>`}
    <p class="notice">${verified ? html`<strong>Verified profile.</strong> Confirmed by the author.`
      : html`<strong>Automatically assembled record.</strong> Built from article metadata. Not an account, not verified, and no affiliation with or endorsement of PrismUnfold is implied.`}</p>
    <p><button type="button" class="btn" data-follow-author aria-pressed="${following ? 'true' : 'false'}">${following ? 'Following' : 'Follow'}</button></p>
    ${topics.length ? html`<h2 class="small-head">Topics</h2><p>${topics.map((t, i) => html`${i ? ' · ' : ''}<a href="${paths.topic(t)}" data-link>${humanize(t)}</a>`)}</p>` : ''}
    <h2 class="small-head">Recent articles</h2>
    <ul class="plain-list">${list.slice(0, 30).map((p) => html`<li><a href="${paths.article(p.article.articleId)}" data-link>${p.article.headline}</a>
      <span class="hint">· ${p.article.section} · ${formatMedium(p.date)}</span></li>`)}</ul>
  </main>`;
  return {
    title: name, nav: '', mode: 'news', body,
    meta: { description: `${name}: recent articles in PrismUnfold.`, canonical: paths.author(slug), noindex: !verified && !isProvider },
    mount(root) {
      const btn = root.querySelector<HTMLButtonElement>('[data-follow-author]');
      btn?.addEventListener('click', () => {
        const on = toggleFollow('authors', slug);
        btn.textContent = on ? 'Following' : 'Follow';
        btn.setAttribute('aria-pressed', String(on));
      });
    },
  };
}
