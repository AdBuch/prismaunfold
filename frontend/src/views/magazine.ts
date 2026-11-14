import { figure, formatMedium, html, shareButton, sourceList } from '../components/ui.ts';
import type { ContentService } from '../content/content-service.ts';
import { artSvg } from '../lib/art.ts';
import { paths } from '../lib/router.ts';
import { raw, type Raw } from '../lib/util.ts';
import type { MagazineBlock, MagazineFeature } from '../models.ts';
import { relatedCard } from './story.ts';
import type { ViewResult } from './types.ts';

function block(b: MagazineBlock): Raw {
  switch (b.type) {
    case 'p':
      return html`<p class="mag-p${b.dropcap ? ' mag-p--drop' : ''}">${b.text}</p>`;
    case 'h2':
      return html`<h2 class="mag-h2">${b.text}</h2>`;
    case 'pullquote':
      return html`<blockquote class="mag-quote"><p>${b.text}</p></blockquote>`;
    case 'figure':
      return html`<div class="mag-figure${b.wide ? ' mag-figure--wide' : ''}">${figure(b.image, { ratio: b.wide ? '21 / 9' : '16 / 9' })}</div>`;
    case 'sidebar':
      return html`<aside class="mag-sidebar"><h3 class="mag-sidebar__title">${b.title}</h3>${b.text.map((t) => html`<p>${t}</p>`)}</aside>`;
    case 'chronology':
      return html`<section class="mag-chrono" aria-label="${b.title}">
        <h3 class="mag-chrono__title">${b.title}</h3>
        <ol>${b.steps.map((s) => html`<li><span class="mag-chrono__label">${s.label}</span><span>${s.text}</span></li>`)}</ol>
      </section>`;
    case 'glossary':
      return html`<section class="mag-gloss" aria-label="Glossary"><h3 class="mag-gloss__title">In short</h3>
        <dl>${b.terms.map((t) => html`<div><dt>${t.term}</dt><dd>${t.text}</dd></div>`)}</dl></section>`;
  }
}

export async function magazineView(svc: ContentService, slug: string): Promise<ViewResult> {
  const m = await svc.getMagazine(slug);
  if (!m) {
    return {
      title: 'Feature not found', nav: 'magazine', mode: 'magazine', status: 404,
      body: html`<main id="main" class="page page--narrow" tabindex="-1"><h1 class="page__title">We could not find that feature</h1><p><a href="${paths.magazines()}" data-link>See all features</a></p></main>`,
    };
  }
  const [stories, topic] = await Promise.all([
    svc.getStories(m.relatedStorySlugs),
    m.topicSlug ? svc.getTopic(m.topicSlug) : Promise.resolve(undefined),
  ]);
  const allFeatures = await svc.listMagazines();
  const otherFeatures = m.relatedFeatureSlugs.map((s) => allFeatures.find((f) => f.slug === s)).filter((f): f is MagazineFeature => !!f);

  const body = html`<main id="main" tabindex="-1" class="mag">
    <header class="mag-hero">
      <div class="mag-hero__art">${raw(artSvg(m.hero))}</div>
      <div class="mag-hero__veil"></div>
      <div class="mag-hero__text">
        <p class="kicker kicker--light">${m.kicker}</p>
        <h1 class="mag-hero__title">${m.title}</h1>
        <p class="mag-hero__dek">${m.standfirst}</p>
        <p class="mag-hero__meta">${m.byline} · ${formatMedium(m.publishedAt)} · ${m.readingMinutes} minute read</p>
      </div>
      <p class="mag-hero__credit">${m.hero.caption} ${m.hero.credit}</p>
    </header>
    <nav class="breadcrumb breadcrumb--mag" aria-label="Breadcrumb"><a href="/" data-link>← Today's edition</a>${shareButton(m.title)}</nav>
    <article class="mag-body">${m.blocks.map(block)}</article>
    ${topic ? html`<aside class="mag-topic"><p class="kicker">Follow the story</p><p>This feature is part of an evolving topic.</p><a class="btn" href="${paths.topic(topic.slug)}" data-link>Open the timeline: ${topic.title}</a></aside>` : ''}
    <section class="mag-end" aria-label="Sources and transparency">
      <h2 class="small-head">Sources</h2>
      ${sourceList(m.sources)}
      <h2 class="small-head">Transparency</h2>
      <p>${m.aiDisclosure}</p>
    </section>
    <section class="related related--mag" aria-labelledby="mr-h">
      <h2 id="mr-h" class="small-head">Related reading</h2>
      <div class="related__grid">${stories.map((s) => relatedCard(s))}</div>
      ${otherFeatures.length ? html`<div class="more-features">${otherFeatures.map((f) => html`<a class="more-features__item" href="${paths.magazine(f.slug)}" data-link><span class="kicker">${f.kicker}</span><strong>${f.title}</strong><span>${f.readingMinutes} minute read</span></a>`)}</div>` : ''}
    </section>
  </main>`;
  return { title: m.title, nav: 'magazine', mode: 'magazine', body };
}

export async function magazinesView(svc: ContentService): Promise<ViewResult> {
  const features = await svc.listMagazines();
  const body = html`<main id="main" tabindex="-1" class="page">
    <p class="kicker">Magazine</p>
    <h1 class="page__title">Background</h1>
    <p class="page__dek">Slower, longer and more atmospheric. Where the daily edition tells you what happened, the magazine explains how we got here.</p>
    ${features.length ? '' : html`<p class="state state--empty hint">No feature has been published yet. Deep dives appear here when a topic has enough reporting behind it.</p>`}
    <div class="mag-index">${features.map((f) => html`<article class="mag-index__item">
      <a href="${paths.magazine(f.slug)}" data-link tabindex="-1" aria-hidden="true">${figure(f.hero, { ratio: '4 / 3' })}</a>
      <p class="kicker">${f.kicker}</p>
      <h2 class="mag-index__title"><a href="${paths.magazine(f.slug)}" data-link>${f.title}</a></h2>
      <p>${f.standfirst}</p>
      <p class="hint">${f.readingMinutes} minute read</p>
    </article>`)}</div>
  </main>`;
  return { title: 'Magazine', nav: 'magazine', mode: 'news', body };
}
