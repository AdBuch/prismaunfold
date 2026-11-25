import {
  KIND_LABEL, confidenceBadge, dateline, figure, formatDayMonth, formatLong, formatMedium, html, kicker,
  sectionLabel, shareButton, sourceList, storyHref, verificationBadge,
} from '../components/ui.ts';
import type { ContentService } from '../content/content-service.ts';
import { paths } from '../lib/router.ts';
import { isIsoDate, type Raw } from '../lib/util.ts';
import type { Story } from '../models.ts';
import { runtime } from '../runtime.ts';
import type { ViewResult } from './types.ts';

export function relatedCard(s: Story, edition?: string): Raw {
  return html`<article class="related-card">
    <a class="related-card__media" href="${storyHref(s.slug, edition)}" data-link tabindex="-1" aria-hidden="true">${figure(s.image, { ratio: '3 / 2' })}</a>
    ${kicker(s.agent ? `${sectionLabel(s.section)} · ${s.byline}` : sectionLabel(s.section))}
    <h3 class="related-card__title"><a href="${storyHref(s.slug, edition)}" data-link>${s.headline}</a></h3>
  </article>`;
}

/** Pipeline stories: every sentence is followed by numbered links to the sources backing it. */
function bodyWithSources(story: Story): Raw {
  const number = new Map(story.sources.map((s, i) => [s.id, i + 1]));
  const sentences = story.sentences ?? [];
  return html`<p class="story__first">${sentences.map((s) => html`<span class="claim claim--${s.verification?.state ?? 'unverified'}">${s.text}${
    s.sourceIds.map((id) => {
      const n = number.get(id);
      return n ? html`<sup class="cite"><a href="#src-${n}" data-cite="src-${n}" aria-label="Source ${n}">${n}</a></sup>` : '';
    })} </span>`)}</p>`;
}

function assessment(story: Story): Raw {
  const v = story.verification;
  if (!v) {
    // Demo fixtures carry only the older three-level confidence.
    return html`<p>${confidenceBadge(story.confidence)}</p><p>${story.confidenceNote}</p>`;
  }
  const list = (title: string, items: string[] | undefined) =>
    items?.length ? html`<h3 class="assess__sub">${title}</h3><ul class="assess__list">${items.map((i) => html`<li>${i}</li>`)}</ul>` : '';
  const publishers = v.independent_publishers ?? 0;
  return html`<p>${verificationBadge(v.state)}</p>
    <p>${story.confidenceNote}</p>
    ${list('Why this label', v.reasons)}
    ${list('Where sources disagree', story.disputes)}
    ${list('Not known', story.uncertainties)}
    <p class="hint">${publishers} independent publisher${publishers === 1 ? '' : 's'} cited · ${
      v.links_checked ? 'source links were opened' : 'source links were not opened'} · ${
      v.checker && v.checker !== 'none' ? `support check: ${v.checker}` : 'nobody has checked that the sources say this'}</p>`;
}

export async function storyView(svc: ContentService, slug: string, search: URLSearchParams): Promise<ViewResult> {
  const story = await svc.getStory(slug);
  if (!story) {
    return {
      title: 'Story not found', nav: '', mode: 'news', status: 404,
      body: html`<main id="main" class="page page--narrow" tabindex="-1"><h1 class="page__title">We could not find that story</h1><p><a href="/" data-link>Return to today's edition</a></p></main>`,
    };
  }
  const [related, editions, topic] = await Promise.all([
    svc.getRelatedStories(slug),
    svc.getEditionsForStory(slug),
    story.topicSlug ? svc.getTopic(story.topicSlug) : Promise.resolve(undefined),
  ]);
  const fromParam = search.get('e') ?? '';
  const from = isIsoDate(fromParam) && editions.some((e) => e.date === fromParam) ? fromParam : editions[0]?.date;
  const editionDate = from;

  const events = topic ? topic.events.filter((e) => e.date <= story.publishedAt.slice(0, 10)).slice(-4) : [];
  const live = !!story.sentences?.length;

  const body = html`<main id="main" tabindex="-1" class="reader">
    <nav class="breadcrumb" aria-label="Breadcrumb">
      ${from ? html`<a href="${paths.edition(from)}" data-link>← Edition of ${formatMedium(from)}</a>` : html`<a href="/" data-link>← Today's edition</a>`}
    </nav>
    <article class="story"${story.language ? html` lang="${story.language}"` : ''}>
      <header class="story__head">
        ${kicker(sectionLabel(story.section))}
        <h1 class="story__title">${story.headline}</h1>
        ${live ? '' : html`<p class="story__dek">${story.standfirst}</p>`}
        <div class="story__meta">
          <span class="meta meta--by">${story.byline}</span>
          ${dateline(story.publishedAt, story.updatedAt)}
          ${shareButton(story.headline)}
        </div>
      </header>
      ${figure(story.image, { wide: true })}
      <div class="story__body">
        ${live ? bodyWithSources(story) : story.body.map((p, i) => html`<p class="${i === 0 ? 'story__first' : ''}">${p}</p>`)}
      </div>

      ${story.corrections.length ? html`<aside class="correction" aria-labelledby="corr-h">
        <h2 id="corr-h" class="correction__title">Correction${story.corrections.length > 1 ? 's' : ''}</h2>
        ${story.corrections.map((c) => html`<p><strong>${formatMedium(c.date)}.</strong> ${c.text}</p>`)}
      </aside>` : ''}

      <aside class="assess" aria-labelledby="assess-h" lang="en">
        <h2 id="assess-h" class="assess__title">How sure are we?</h2>
        ${assessment(story)}
      </aside>

      ${topic && events.length ? html`<aside class="mini-timeline" aria-labelledby="mt-h">
        <h2 id="mt-h" class="mini-timeline__title">The story so far</h2>
        <ol>${events.map((e) => html`<li class="mini-timeline__item mini-timeline__item--${e.kind}">
          <span class="mini-timeline__date">${formatDayMonth(e.date)}</span>
          <span><span class="tag tag--${e.kind}">${KIND_LABEL[e.kind]}</span> ${e.title}</span></li>`)}</ol>
        <a class="btn" href="${paths.topic(topic.slug)}" data-link>Open the full timeline: ${topic.title}</a>
      </aside>` : ''}

      <section class="story__sources" aria-labelledby="src-h" lang="en">
        <h2 id="src-h" class="small-head">Sources and original reporting</h2>
        ${sourceList(story.sources)}
        ${runtime.demo
          ? html`<p class="hint">Links point to reserved example addresses. They stand in for original publisher links in a real edition.</p>`
          : html`<p class="hint">Links lead to the original publishers. The numbers in the text point to the entries in this list.</p>`}
      </section>

      <section class="story__disclosure" aria-labelledby="ai-h" lang="en">
        <h2 id="ai-h" class="small-head">Transparency</h2>
        <p>${story.aiDisclosure}</p>
        ${editions.length ? html`<p>Appeared in: ${editions.map((e, i) => html`${i ? ', ' : ''}<a href="${paths.edition(e.date)}" data-link>${formatLong(e.date)}</a>`)}.</p>` : ''}
      </section>
    </article>
    ${related.length ? html`<section class="related" aria-labelledby="rel-h">
      <h2 id="rel-h" class="small-head">${live ? 'Other writers on this topic' : 'Related stories'}</h2>
      <div class="related__grid">${related.map((s) => relatedCard(s, editionDate))}</div>
    </section>` : ''}
  </main>`;

  return { title: story.headline, nav: 'edition', mode: 'news', body };
}
