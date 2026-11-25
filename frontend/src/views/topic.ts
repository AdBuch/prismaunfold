import { KIND_LABEL, figure, formatDayMonth, formatLong, formatMedium, html, kicker, sectionLabel, shareButton, storyHref } from '../components/ui.ts';
import type { ContentService } from '../content/content-service.ts';
import { paths } from '../lib/router.ts';
import type { Raw } from '../lib/util.ts';
import type { Topic, TimelineEvent } from '../models.ts';
import type { ViewResult } from './types.ts';

type Filter = 'all' | 'milestones' | 'changes';
type Order = 'asc' | 'desc';

function renderEvents(topic: Topic, filter: Filter, order: Order, storyTitles: Map<string, string>): Raw {
  let events: TimelineEvent[] = [...topic.events];
  if (filter === 'milestones') events = events.filter((e) => e.kind === 'milestone' || e.kind === 'report');
  if (filter === 'changes') events = events.filter((e) => e.kind === 'update' || e.kind === 'correction');
  events.sort((a, b) => (order === 'asc' ? a.date.localeCompare(b.date) : b.date.localeCompare(a.date)));
  if (!events.length) return html`<p class="hint">No entries match this filter.</p>`;
  return html`<ol class="timeline">${events.map((e) => html`<li class="tl tl--${e.kind}">
    <div class="tl__date"><span>${formatDayMonth(e.date)}</span><small>${e.date.slice(0, 4)}</small></div>
    <div class="tl__dot" aria-hidden="true"></div>
    <div class="tl__card">
      <p class="tl__kind"><span class="tag tag--${e.kind}">${KIND_LABEL[e.kind]}</span></p>
      <h3 class="tl__title">${e.title}</h3>
      <p class="tl__text">${e.summary}</p>
      <p class="tl__links">
        ${e.storySlug ? html`<a href="${storyHref(e.storySlug, e.editionDate)}" data-link>Read: ${storyTitles.get(e.storySlug) ?? 'the report'}</a>` : ''}
        ${e.editionDate ? html`<a href="${paths.edition(e.editionDate)}" data-link>In the edition of ${formatMedium(e.editionDate)}</a>` : ''}
        ${!e.storySlug && !e.editionDate ? html`<span class="hint">Before the first PrismUnfold edition on this topic</span>` : ''}
      </p>
    </div></li>`)}</ol>`;
}

export async function topicView(svc: ContentService, slug: string): Promise<ViewResult> {
  const topic = await svc.getTopic(slug);
  if (!topic) {
    return {
      title: 'Topic not found', nav: '', mode: 'news', status: 404,
      body: html`<main id="main" class="page page--narrow" tabindex="-1"><h1 class="page__title">We could not find that topic</h1><p><a href="/" data-link>Return to today's edition</a></p></main>`,
    };
  }
  const slugs = [...new Set(topic.events.map((e) => e.storySlug).filter((s): s is string => !!s))];
  const stories = await svc.getStories(slugs);
  const titles = new Map(stories.map((s) => [s.slug, s.headline]));
  const first = topic.events[0];
  const last = topic.events[topic.events.length - 1];
  const corrections = topic.events.filter((e) => e.kind === 'correction').length;

  const body = html`<main id="main" tabindex="-1" class="page topic">
    <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/" data-link>← Today's edition</a></nav>
    <header class="topic__head">
      <div>
        ${kicker(`Topic timeline · ${sectionLabel(topic.section)}`)}
        <h1 class="page__title">${topic.title}</h1>
        <p class="page__dek">${topic.summary}</p>
        <p class="topic__stats">${topic.events.length} entries · ${first && last ? `${formatMedium(first.date)} to ${formatMedium(last.date)}` : ''}${corrections ? ` · ${corrections} correction${corrections > 1 ? 's' : ''}` : ''}</p>
        <div class="topic__actions">${shareButton(topic.title, 'Share this timeline')}</div>
      </div>
      <div class="topic__art">${figure(topic.image, { ratio: '4 / 3' })}</div>
    </header>
    <div class="topic__controls" role="group" aria-label="Timeline controls">
      <div class="chips" role="group" aria-label="Show">
        <button type="button" class="chip" data-filter="all" aria-pressed="true">All entries</button>
        <button type="button" class="chip" data-filter="milestones" aria-pressed="false">Milestones and reports</button>
        <button type="button" class="chip" data-filter="changes" aria-pressed="false">Updates and corrections</button>
      </div>
      <button type="button" class="chip chip--order" data-order="asc" aria-label="Sort order: oldest first. Activate to reverse.">Oldest first ↓</button>
    </div>
    <div data-timeline aria-live="polite">${renderEvents(topic, 'all', 'asc', titles)}</div>
    <aside class="legend" aria-label="Legend">
      <p><span class="tag tag--milestone">Milestone</span> a major development</p>
      <p><span class="tag tag--report">Report</span> reporting that added facts</p>
      <p><span class="tag tag--update">Update</span> a change to an ongoing story</p>
      <p><span class="tag tag--correction">Correction</span> something we got wrong, and what is right</p>
    </aside>
    <section class="related" aria-labelledby="ts-h">
      <h2 id="ts-h" class="small-head">Stories on this topic</h2>
      <ul class="plain-list">${stories.map((s) => html`<li><a href="${storyHref(s.slug)}" data-link>${s.headline}</a> <span class="hint">· ${formatLong(s.publishedAt)}</span></li>`)}</ul>
    </section>
  </main>`;

  return {
    title: `Timeline: ${topic.title}`,
    nav: 'edition',
    mode: 'news',
    body,
    mount(root) {
      let filter: Filter = 'all';
      let order: Order = 'asc';
      const host = root.querySelector<HTMLElement>('[data-timeline]');
      const paint = () => {
        if (host) host.innerHTML = renderEvents(topic, filter, order, titles).value;
      };
      root.querySelectorAll<HTMLButtonElement>('[data-filter]').forEach((btn) => {
        btn.addEventListener('click', () => {
          filter = btn.dataset['filter'] as Filter;
          root.querySelectorAll<HTMLButtonElement>('[data-filter]').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
          paint();
        });
      });
      const orderBtn = root.querySelector<HTMLButtonElement>('[data-order]');
      orderBtn?.addEventListener('click', () => {
        order = order === 'asc' ? 'desc' : 'asc';
        orderBtn.textContent = order === 'asc' ? 'Oldest first ↓' : 'Newest first ↑';
        orderBtn.setAttribute('aria-label', `Sort order: ${order === 'asc' ? 'oldest' : 'newest'} first. Activate to reverse.`);
        paint();
      });
    },
  };
}

