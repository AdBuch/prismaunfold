/**
 * Today's Edition: the one daily newspaper (docs/PRODUCT.md).
 *
 * A date's edition combines the editorial daily edition (api/v1/daily: Codex,
 * prism-data, matched coverage) with the feed desk's edition (editions.json). The
 * public edition follows the editorial order. With a reader profile the same
 * canonical articles are recomposed for the reader (lib/composer.ts); the public
 * edition stays one click away. If a date has only a feed edition, it is shown as
 * before 0.3.
 */
import {
  articleMarks, featureTeaser, itemTeaser, leadTeaser, providerLabel, secondaryTeaser,
} from '../components/daily-ui.ts';
import {
  VERIFICATION_LABEL, figure, formatLong, formatMedium, html, kicker, sectionHeading, sectionLabel, shareButton, storyHref,
} from '../components/ui.ts';
import type { ContentService } from '../content/content-service.ts';
import { compose, fromArticle, type Candidate, type Composition, type CoverageGap, type Reason } from '../lib/composer.ts';
import { INTEREST_KEYS, REGIONS, history, isPersonal, loadProfile, saveProfile, type ReaderProfile } from '../lib/profile.ts';
import { paths } from '../lib/router.ts';
import { isIsoDate, raw, type Raw } from '../lib/util.ts';
import type { EditionStoryPlacement, MagazineFeature } from '../models.ts';
import type { DailyArticle, DailyEdition, DailyShortItem } from '../models-daily.ts';
import { runtime } from '../runtime.ts';
import { emptyView } from './about.ts';
import type { ViewResult } from './types.ts';

// --- Edition navigation over every published date (daily or feed) ---

function editionNav(date: string, dates: string[]): Raw {
  const asc = [...dates].sort();
  const i = asc.indexOf(date);
  const prev = i > 0 ? asc[i - 1] : undefined;
  const next = i >= 0 && i < asc.length - 1 ? asc[i + 1] : undefined;
  return html`<nav class="edition-nav" aria-label="Edition navigation">
    ${prev ? html`<a class="edition-nav__step" href="${paths.edition(prev)}" data-link rel="prev"><span aria-hidden="true">←</span> Previous edition<small>${formatMedium(prev)}</small></a>`
      : html`<span class="edition-nav__step edition-nav__step--end">Earliest edition</span>`}
    <div class="edition-nav__select">
      <label for="edition-select">Choose an edition</label>
      <select id="edition-select" data-edition-select>
        ${dates.map((d) => html`<option value="${d}" ${d === date ? raw('selected') : ''}>${formatLong(d)}</option>`)}
      </select>
    </div>
    ${next ? html`<a class="edition-nav__step edition-nav__step--next" href="${paths.edition(next)}" data-link rel="next">Next edition <span aria-hidden="true">→</span><small>${formatMedium(next)}</small></a>`
      : html`<span class="edition-nav__step edition-nav__step--end edition-nav__step--next">Latest edition</span>`}
  </nav>`;
}

// --- Feed-desk placements (kept from 0.2) ---

function placementMarks(p: EditionStoryPlacement): Raw {
  const state = p.verificationState;
  return html`${state === 'review_required' || state === 'disputed' ? html`<span class="mark mark--${state}">${VERIFICATION_LABEL[state]}</span>` : ''}${
    p.underreported ? html`<span class="mark mark--under">Underreported</span>` : ''}${p.isUpdate ? html`<span class="mark">Updated</span>` : ''}`;
}
const lang = (p: EditionStoryPlacement): Raw => (p.language ? html` lang="${p.language}"` : html``);

function placementLead(p: EditionStoryPlacement, date: string, why?: Raw): Raw {
  return html`<article class="lead">
    <a class="lead__media" href="${storyHref(p.storySlug, date)}" data-link tabindex="-1" aria-hidden="true">${p.snapshot.image ? figure(p.snapshot.image, { ratio: '4 / 3' }) : ''}</a>
    ${kicker(sectionLabel(p.section))}
    <h2 class="lead__title"${lang(p)}><a href="${storyHref(p.storySlug, date)}" data-link>${p.snapshot.headline}</a></h2>
    <p class="lead__dek"${lang(p)}>${p.snapshot.teaser}</p>
    <p class="more"><a href="${storyHref(p.storySlug, date)}" data-link>Read the story</a> ${placementMarks(p)}</p>${why ?? ''}
  </article>`;
}
function placementSecondary(p: EditionStoryPlacement, date: string, why?: Raw): Raw {
  return html`<article class="secondary">${kicker(sectionLabel(p.section))}
    <h3 class="secondary__title"${lang(p)}><a href="${storyHref(p.storySlug, date)}" data-link>${p.snapshot.headline}</a></h3>
    <p class="secondary__dek"${lang(p)}>${p.snapshot.teaser}</p>${placementMarks(p)}${why ?? ''}</article>`;
}
function placementItem(p: EditionStoryPlacement, date: string, why?: Raw): Raw {
  return html`<article class="item">
    ${p.snapshot.image ? html`<a class="item__media" href="${storyHref(p.storySlug, date)}" data-link tabindex="-1" aria-hidden="true">${figure(p.snapshot.image, { ratio: '3 / 2' })}</a>` : ''}
    <div class="item__text"><h3 class="item__title"${lang(p)}><a href="${storyHref(p.storySlug, date)}" data-link>${p.snapshot.headline}</a></h3>
    <p class="item__dek"${lang(p)}>${p.snapshot.teaser}</p>${placementMarks(p)}${why ?? ''}</div></article>`;
}

/** Feed placements as composer candidates: lead and secondary slots count as more important. */
export function fromPlacement(p: EditionStoryPlacement, rank: number, total: number): Candidate {
  const slot = p.slot === 'lead' ? 1 : p.slot === 'secondary' ? 0.75 : Math.max(0.2, 0.6 - rank / Math.max(1, total) * 0.4);
  return {
    id: `story:${p.storySlug}`, headline: p.snapshot.headline, section: sectionLabel(p.section), kind: 'news',
    topics: [], regions: (p.regions ?? []).map((r) => r.toUpperCase()), importance: slot,
    minutes: 2, cluster: `story:${p.storySlug}`, authors: [], publishers: [],
  };
}

// --- Reasons, gaps and onboarding ---

const interestLabel = (k: string) => INTEREST_KEYS.find((x) => x.key === k)?.label ?? k;
const regionLabel = (k: string) => REGIONS.find((x) => x.code === k)?.label ?? k;

function whyLine(reason: Reason | undefined, c: Candidate | undefined, profile: ReaderProfile): Raw {
  if (!reason || !c) return html``;
  let text = '';
  if (reason === 'global') text = 'Important for everyone today';
  else if (reason === 'recurring') text = 'Part of your recurring sections';
  else if (reason === 'discovery') text = 'Beyond your interests: important today';
  else if (reason === 'follow') text = c.topicSlug && profile.follows.topics.includes(c.topicSlug) ? 'You follow this topic' : 'You follow this author or publisher';
  else {
    const topics = c.topics.filter((t) => (profile.topicInterests[t] ?? 0) > 0).map(interestLabel);
    const regions = c.regions.filter((r) => (profile.geographicInterests[r] ?? 0) > 0 || r === profile.homeRegion).map(regionLabel);
    text = `Matches your interest in ${[...topics, ...regions].join(', ') || 'this section'}`;
  }
  return html`<p class="why">${text}</p>`;
}

function gapsPanel(gaps: CoverageGap[]): Raw {
  if (!gaps.length) return html``;
  return html`<aside class="gaps" aria-labelledby="gaps-h">
    <h2 id="gaps-h" class="gaps__title">Not covered today</h2>
    <p>This edition has no reporting on ${gaps.map((g, i) => html`${i ? ', ' : ''}<strong>${g.kind === 'topic' ? interestLabel(g.key) : regionLabel(g.key)}</strong>`)}.
      PrismUnfold does not fill empty sections with invented articles.</p>
    <p class="hint">The gap is noted on this device as a coverage-gap signal. Sending aggregated, anonymous demand to the research desk is planned; your profile itself is never sent.</p>
  </aside>`;
}

function onboardingInvite(): Raw {
  return html`<aside class="onboard" aria-labelledby="onboard-h" data-onboard>
    <div><p class="kicker">My PrismUnfold</p>
    <h2 id="onboard-h" class="onboard__title">Make this paper yours in two minutes</h2>
    <p>Choose your languages, regions, topics and reading time. The important news of the day stays in every edition. Your settings stay on this device.</p></div>
    <div class="onboard__actions"><a class="btn" href="${paths.me()}#setup" data-link>Set up my edition</a>
    <button type="button" class="btn btn--ghost" data-onboard-skip>Not now, read the public edition</button></div>
  </aside>`;
}

// --- Short sections ---

function shortList(title: string, items: DailyShortItem[], id: string): Raw {
  if (!items.length) return html``;
  return html`<section class="shorts" aria-labelledby="${id}">
    <div class="section-head"><h2 id="${id}" class="section-head__title">${title}</h2></div>
    <div class="shorts__grid">${items.map((s) => html`<div class="short">
      ${s.label ? html`<h3 class="short__label">${s.label}</h3>` : ''}
      <p>${s.text}${s.reviewRequired ? html` <span class="mark mark--review_required">Needs review</span>` : ''}</p>
      ${s.sources.length ? html`<p class="short__src">${s.attribution ? `${s.attribution} · ` : ''}${s.sources.map((x, i) => html`${i ? ', ' : ''}<a href="${x.url}" target="_blank" rel="noopener noreferrer">${x.publisher || x.title}</a>`)}</p>` : ''}
    </div>`)}</div>
  </section>`;
}

/** Public reading order: main headline, then rubrics, then anything left. */
export function publicOrder(e: DailyEdition): DailyArticle[] {
  const byId = new Map(e.articles.map((a) => [a.articleId, a]));
  const ordered: DailyArticle[] = [];
  const push = (a?: DailyArticle) => { if (a && !ordered.includes(a)) ordered.push(a); };
  push(e.mainHeadline ? byId.get(e.mainHeadline.articleId) : undefined);
  for (const r of e.rubrics) for (const id of r.articleIds) push(byId.get(id));
  e.articles.forEach(push);
  return ordered;
}

function transparency(e: DailyEdition): Raw {
  const t = e.transparency;
  return html`<details class="tx">
    <summary>How this edition was made · ${e.contributors.length} contributor${e.contributors.length === 1 ? '' : 's'}${t.completeness === 'partial' ? ' · partial edition' : ''}</summary>
    <ul class="plain-list">${e.contributors.map((c) => html`<li>${providerLabel(c.provider)} <span class="hint">(${c.originType === 'ai_secondary' ? 'AI-written from cited sources' : c.originType})</span></li>`)}</ul>
    ${t.disclosures.map((d) => html`<p>${d}</p>`)}
    ${t.independentVerification ? html`<p class="hint">${t.independentVerification}</p>` : ''}
    ${t.editorialNote ? html`<p class="hint">${t.editorialNote}</p>` : ''}
    ${t.warnings.length ? html`<h3 class="small-head">Editorial notes</h3><ul>${t.warnings.map((w) => html`<li>${w}</li>`)}</ul>` : ''}
    ${e.revision.publishedAt ? html`<p class="hint">Published ${formatMedium(e.revision.publishedAt)}${e.revision.publicationMode ? ` · ${e.revision.publicationMode} publication` : ''}.</p>` : ''}
  </details>`;
}

// --- The view ---

export async function todayView(svc: ContentService, param: string | undefined, search: URLSearchParams): Promise<ViewResult> {
  const [index, feedEditions] = await Promise.all([svc.listDaily(), svc.listEditions()]);
  const dates = [...new Set([...index.map((i) => i.date), ...feedEditions.map((e) => e.date)])].sort().reverse();
  if (!dates.length) return emptyView();
  const latest = dates[0] ?? '';
  const date = param ?? latest;
  const daily = isIsoDate(date) && index.some((i) => i.date === date) ? await svc.getDaily(date) : undefined;
  const feed = isIsoDate(date) ? feedEditions.find((e) => e.date === date) : undefined;

  if (!daily && !feed) {
    return {
      title: 'Edition not found', nav: 'archive', mode: 'news', status: 404,
      body: html`<main id="main" class="page page--narrow" tabindex="-1">
        <h1 class="page__title">No edition for this date</h1>
        <p class="lead__dek">PrismUnfold publishes one edition per day. Pick one of the editions below.</p>
        <ul class="plain-list">${dates.map((d) => html`<li><a href="${paths.edition(d)}" data-link>${formatLong(d)}</a></li>`)}</ul>
      </main>`,
    };
  }

  const profile = loadProfile();
  const wantsPublic = search.get('edition') === 'public';
  const personal = isPersonal(profile) && !wantsPublic;
  const isLatest = date === latest;

  // Feed stories already attached to an editorial article are not shown twice.
  const covered = new Set((daily?.articles ?? []).flatMap((a) => [a.storySlug, ...a.coverage.map((c) => c.storySlug)]).filter(Boolean));
  const placements = [...(feed?.placements ?? [])].sort((a, b) => a.order - b.order).filter((p) => !covered.has(p.storySlug));
  const dailyNews = daily ? publicOrder(daily) : [];
  const feedMagazine: MagazineFeature | undefined = !daily?.magazine.length && feed?.magazineSlug ? await svc.getMagazine(feed.magazineSlug) : undefined;

  // Candidates: canonical articles and feed stories, referenced by id.
  const articleById = new Map<string, DailyArticle>();
  const placementById = new Map<string, EditionStoryPlacement>();
  const candidates: Candidate[] = [];
  dailyNews.forEach((a, i) => { articleById.set(a.articleId, a); candidates.push(fromArticle(a, i, dailyNews.length, daily?.mainHeadline?.articleId)); });
  for (const a of [...(daily?.goodNews ?? []), ...(daily?.magazine ?? [])]) {
    articleById.set(a.articleId, a);
    candidates.push({ ...fromArticle(a, dailyNews.length, dailyNews.length + 1), kind: a.kind === 'magazine' ? 'magazine' : 'good_news', importance: 0.3 });
  }
  placements.forEach((p, i) => { const c = fromPlacement(p, i, placements.length); placementById.set(c.id, p); candidates.push(daily ? { ...c, importance: Math.min(c.importance, 0.5) } : c); });
  const candidateById = new Map(candidates.map((c) => [c.id, c]));
  const composition: Composition | undefined = personal ? compose(candidates, profile, new Set(history())) : undefined;
  const reasonOf = new Map(composition?.items.map((i) => [i.id, i.reason]));

  const why = (id: string): Raw | undefined => (personal ? whyLine(reasonOf.get(id), candidateById.get(id), profile) : undefined);
  const render = (id: string, variant: 'lead' | 'secondary' | 'item'): Raw => {
    const a = articleById.get(id);
    if (a) return variant === 'lead' ? leadTeaser(a, why(id)) : variant === 'secondary' ? secondaryTeaser(a, why(id)) : itemTeaser(a, why(id));
    const p = placementById.get(id);
    if (p) return variant === 'lead' ? placementLead(p, date, why(id)) : variant === 'secondary' ? placementSecondary(p, date, why(id)) : placementItem(p, date, why(id));
    return html``;
  };

  // Front page and sections.
  let front: Raw;
  let sections: Raw;
  let counts: string;
  if (composition) {
    const ids = composition.items.filter((i) => candidateById.get(i.id)?.kind === 'news').map((i) => i.id);
    const [leadId, ...rest] = ids;
    const groups: [string, Reason[]][] = [['For you', ['interest', 'follow']], ['Beyond your interests', ['discovery']]];
    const globals = rest.filter((id) => reasonOf.get(id) === 'global');
    front = html`${leadId ? render(leadId, 'lead') : ''}<div class="front__side">${globals.map((id) => render(id, 'secondary'))}</div>`;
    sections = html`${groups.map(([title, reasons]) => {
      const items = rest.filter((id) => reasons.includes(reasonOf.get(id) as Reason));
      return items.length ? html`<section class="section" aria-label="${title}">
        <div class="section-head"><h2 class="section-head__title">${title}</h2></div>
        <div class="section__grid">${items.map((id) => render(id, 'item'))}</div></section>` : '';
    })}`;
    counts = `${ids.length} of ${candidates.filter((c) => c.kind === 'news').length} stories · about ${composition.minutes} of ${composition.budgetMinutes} minutes`;
  } else if (daily) {
    const [lead, ...rest] = dailyNews;
    const secondaries = rest.filter((a, i, all) => all.findIndex((x) => x.section === a.section) === i).slice(0, 3);
    const remaining = rest.filter((a) => !secondaries.includes(a));
    const bySection = new Map<string, DailyArticle[]>();
    for (const a of remaining) bySection.set(a.section, [...(bySection.get(a.section) ?? []), a]);
    front = html`${lead ? leadTeaser(lead) : ''}<div class="front__side">${secondaries.map((a) => secondaryTeaser(a))}</div>`;
    sections = html`${[...bySection].map(([name, items]) => html`<section class="section" aria-label="${name}">
      <div class="section-head"><h2 class="section-head__title">${name}</h2></div>
      <div class="section__grid">${items.map((a) => itemTeaser(a))}</div></section>`)}
      ${placements.length ? html`<section class="section section--wire" aria-labelledby="wire-h">
        <div class="section-head"><h2 id="wire-h" class="section-head__title">More reporting</h2></div>
        <p class="hint">Stories assembled by the feed desk and research agents from the day's sources.</p>
        <div class="section__grid">${placements.map((p) => placementItem(p, date))}</div></section>` : ''}`;
    counts = `${dailyNews.length + placements.length} stories${daily.magazine.length ? ' · 1 feature' : ''}`;
  } else {
    const ordered = placements;
    const lead = ordered.find((p) => p.slot === 'lead') ?? ordered[0];
    const secondaries = ordered.filter((p) => p !== lead && p.slot === 'secondary');
    const standard = ordered.filter((p) => p !== lead && p.slot !== 'secondary');
    const known = runtime.sections.map((s) => s.id);
    const extra = [...new Set(standard.map((p) => p.section))].filter((id) => !known.includes(id));
    front = html`${lead ? placementLead(lead, date) : ''}<div class="front__side">${secondaries.map((p) => placementSecondary(p, date))}</div>`;
    sections = html`${[...known, ...extra].map((id) => ({ id, items: standard.filter((p) => p.section === id) })).filter((s) => s.items.length)
      .map((s) => html`<section class="section" aria-label="${sectionLabel(s.id)}">${sectionHeading(s.id)}
        <div class="section__grid">${s.items.map((p) => placementItem(p, date))}</div></section>`)}`;
    counts = `${ordered.length} stories · ${feed?.briefs.length ?? 0} briefs${feed?.magazineSlug ? ' · 1 feature' : ''}`;
  }

  const briefs = feed?.briefs ?? [];
  const showRecurring = (key: string) => !personal || profile.recurringSections.includes(key);
  const magazine = daily?.magazine[0];
  const updates = dailyNews.filter((a) => a.corrections?.length || (a.updatedAt && daily?.revision.publishedAt && a.updatedAt > daily.revision.publishedAt));
  const intro = daily?.introduction;
  const note = intro?.text ?? feed?.editorsNote;
  const publicHref = `${paths.edition(date)}?edition=public`;

  const body = html`<main id="main" tabindex="-1" class="edition">
    <section class="edition-bar" aria-labelledby="edition-heading">
      <h1 id="edition-heading" class="edition-bar__date">${formatLong(date)}</h1>
      <p class="edition-bar__meta"><span>${personal ? 'Your edition' : isLatest ? "Today's edition" : 'Archived edition'}</span>${
        feed ? html`<span>No. ${feed.number}</span>` : ''}<span>${counts}</span>${
        daily?.transparency.completeness === 'partial' ? html`<span class="mark">Partial edition</span>` : ''}</p>
      ${editionNav(date, dates)}
    </section>
    ${profile.onboarding === 'new' && !wantsPublic && isLatest ? onboardingInvite() : ''}
    ${personal ? html`<p class="prefs-note">Composed for you from the public edition on this device. <a href="${publicHref}" data-link>Read the public edition</a> · <a href="${paths.me()}" data-link>Change settings</a></p>`
      : isPersonal(profile) ? html`<p class="prefs-note">You are reading the public edition. <a href="${paths.edition(date)}" data-link>Back to your edition</a></p>` : ''}
    ${note ? html`<p class="editors-note"><span class="editors-note__label">${intro ? 'Introduction' : runtime.demo ? 'From the editors' : 'About this edition'}</span> ${note}${
      intro ? html` <span class="hint">· ${providerLabel(intro.provider)}</span>` : ''}</p>` : ''}
    ${composition ? gapsPanel(composition.gaps) : ''}
    <section class="front" aria-label="Front page">
      ${front}
      ${briefs.length ? html`<aside class="brief" aria-labelledby="brief-heading">
        <h2 id="brief-heading" class="brief__title">In brief</h2>
        <ul>${briefs.map((b) => html`<li><span class="brief__tag">${sectionLabel(b.section)}</span> ${b.text}${b.storySlug ? html` <a href="${storyHref(b.storySlug, date)}" data-link class="brief__more">Read<span class="sr-only"> the related story</span></a>` : ''}</li>`)}</ul>
      </aside>` : ''}
    </section>
    ${updates.length ? html`<section class="updates" aria-labelledby="upd-h"><h2 id="upd-h" class="small-head">Updated since publication</h2>
      <ul class="plain-list">${updates.map((a) => html`<li><a href="${paths.article(a.articleId)}" data-link>${a.headline}</a> ${articleMarks(a)}${
        a.corrections?.map((c) => html`<span class="hint"> · ${formatMedium(c.date)}: ${c.text}</span>`)}</li>`)}</ul></section>` : ''}
    ${sections}
    ${magazine && showRecurring('magazine') ? featureTeaser(magazine) : feedMagazine && showRecurring('magazine') ? html`<section class="feature" aria-labelledby="feature-heading">
      <a class="feature__media" href="${paths.magazine(feedMagazine.slug)}" data-link tabindex="-1" aria-hidden="true">${figure(feedMagazine.hero, { ratio: '5 / 4' })}</a>
      <div class="feature__text"><p class="kicker kicker--light">Magazine · Background</p>
        <h2 id="feature-heading" class="feature__title"><a href="${paths.magazine(feedMagazine.slug)}" data-link>${feedMagazine.title}</a></h2>
        <p class="feature__dek">${feed?.magazineTeaser}</p><p class="feature__meta">${feedMagazine.readingMinutes} minute read · ${feedMagazine.byline}</p>
        <a class="btn btn--light" href="${paths.magazine(feedMagazine.slug)}" data-link>Read the feature</a></div></section>` : ''}
    ${daily?.goodNews.length && showRecurring('good_news') ? html`<section class="section section--good" aria-labelledby="good-h">
      <div class="section-head"><h2 id="good-h" class="section-head__title">Good News</h2></div>
      <div class="section__grid">${daily.goodNews.map((a) => itemTeaser(a))}</div></section>` : ''}
    ${daily && showRecurring('random') ? shortList('Discoveries', daily.randomFacts, 'disc-h') : ''}
    ${daily && showRecurring('editorial_outlook') ? shortList('Editorial outlook', daily.assessments, 'outlook-h') : ''}
    ${daily ? transparency(daily) : ''}
    <section class="end" aria-label="End of edition">
      <p class="end__mark" aria-hidden="true">◆</p>
      <h2 class="end__title">That is the whole edition.</h2>
      <p>${feed ? `No. ${feed.number} ends here. ` : ''}Come back tomorrow, or read an earlier edition in the <a href="${paths.archive()}" data-link>archive</a>.</p>
      <div class="end__actions">${shareButton(`PrismUnfold edition of ${formatMedium(date)}${runtime.demo ? ' (demo)' : ''}`, 'Share this edition')}</div>
    </section>
  </main>`;

  const lead = dailyNews[0];
  return {
    title: personal ? 'Your edition' : `Edition of ${formatMedium(date)}`,
    nav: 'today', mode: 'news', body,
    meta: { description: lead ? `${lead.headline}. ${lead.lead}` : note, canonical: paths.edition(date), noindex: personal },
    mount(root) {
      root.querySelector('[data-onboard-skip]')?.addEventListener('click', () => {
        const p = loadProfile();
        p.onboarding = 'skipped';
        saveProfile(p);
        root.querySelector('[data-onboard]')?.remove();
      });
    },
  };
}

