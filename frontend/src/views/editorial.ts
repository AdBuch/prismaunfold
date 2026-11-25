import { html, type Raw } from '../lib/util.ts';
import type { ViewResult } from './types.ts';

type Source = { id: string; url: string; title: string; publisher: string; access?: string; source_type?: string; published_at?: string; link_status?: string };
type ShortItem = { review_required?: boolean; text: string; sources: Source[]; label?: string; attribution?: string };
type EditorialImage = {
  url: string; alt: string; caption: string; credit: string; license: string; rights: string;
  rights_note: string; source_url: string; license_url: string; display: boolean;
};
type Article = {
  background?: (ShortItem & { heading: string })[]; topic?: string; section: string; headline: string;
  lead: string; paragraphs: { heading?: string; text: string; source_ids: string[] }[]; sources: Source[];
  origin?: 'prism-data' | 'prismunfold'; coverage?: Article[]; uncertainties?: string[]; review_required?: boolean;
  perspectives?: ShortItem[]; images?: EditorialImage[]; story_slug?: string; verification?: string;
};
type Edition = {
  random?: ShortItem; lagebild?: (ShortItem & { category: string })[]; date: string; articles: Article[];
  magazine?: Article | null; additional_articles?: Article[]; additional_magazines?: Article[];
  bulletin?: { lead: string; note: string; outlook: ShortItem[]; random_article?: Article | null; disclosure: string };
  disclosure: string; warnings: string[];
};

function sources(refs: Source[]): Raw {
  return refs.length ? html`<details class="editorial-sources"><summary>Originalquellen · ${refs.length}</summary>
    <ol>${refs.map(s => html`<li><a href="${/^https?:\/\//i.test(s.url) ? s.url : '#'}" target="_blank" rel="noopener noreferrer">${s.publisher}: ${s.title}</a>
      ${s.source_type ? ` · ${s.source_type}` : ''}${s.published_at ? ` · ${s.published_at}` : ''}
      ${s.access === 'paywalled' ? ' · Bezahlschranke / Verweis' : s.access === 'excerpt' ? ' · Auszug' : ''}
      ${s.link_status && s.link_status !== 'reachable' ? ' · Link nicht verifiziert (' + s.link_status + ')' : ''}</li>`)}</ol></details>` : html``;
}

function shortItem(item: ShortItem): Raw {
  return html`${item.label && html`<h3>${item.label}</h3>`}${item.review_required ? html`<p class="editorial-disclosure">Quellenzugriff unvollständig · prüfbedürftig</p>` : ''}
    <p>${item.attribution ? `${item.attribution} · ` : ''}${item.text}</p>${sources(item.sources)}`;
}

function articleContent(a: Article): Raw {
  const ids = new Map(a.sources.map((s, i) => [s.id, i + 1]));
  return html`
    ${a.origin === 'prism-data' ? html`<p class="editorial-disclosure">KI-kuratierte Sekundärquelle · Originalbelege auf Artikelebene</p>` : ''}
    ${a.lead ? html`<p class="editorial-lead">${a.lead}</p>` : ''}
    ${a.images?.map(image => html`<figure class="editorial-image">
      ${image.display && /^https:\/\//i.test(image.url) ? html`<img src="${image.url}" alt="${image.alt || image.caption}" loading="lazy" referrerpolicy="no-referrer">` : ''}
      <figcaption>${[image.caption, image.credit, image.license, image.rights, image.rights_note].filter(Boolean).join(' · ')}
      ${!image.display ? ' · Keine Anzeigefreigabe' : ''}
      ${/^https?:\/\//i.test(image.source_url) ? html`<a href="${image.source_url}" rel="noreferrer">Bildquelle</a>` : ''}
      ${/^https?:\/\//i.test(image.license_url) ? html`<a href="${image.license_url}" rel="noreferrer">Lizenz</a>` : ''}</figcaption>
    </figure>`)}
    ${a.paragraphs.map(p => html`${p.heading ? html`<h3>${p.heading}</h3>` : ''}<p>${p.text} ${p.source_ids.length ? html`<sup>${p.source_ids.map(id => ids.get(id)).filter(Boolean).join(', ')}</sup>` : ''}</p>`)}
    ${a.uncertainties?.length ? html`<aside><h3>Unsicherheiten</h3><ul>${a.uncertainties.map(note => html`<li>${note}</li>`)}</ul></aside>` : ''}
    ${a.perspectives?.length ? html`<section><h3>Einschätzungen und Perspektiven</h3>${a.perspectives.map(shortItem)}</section>` : ''}
    ${sources(a.sources)}
    ${a.origin === 'prism-data' && !a.sources.length ? html`<p class="editorial-disclosure">Keine Originalquellen mitgeliefert.</p>` : ''}
    ${a.story_slug ? html`<p><a data-link href="/story/${a.story_slug}">PrismUnfold-Bericht und Prüfstatus →</a></p>` : ''}
  `;
}

function article(a: Article, index: number, day: string, detail = false): Raw {
  return html`<article class="editorial-article" id="article-${index}">
    <div class="editorial-kicker">${a.section}</div><h2>${a.headline}</h2>${a.review_required ? html`<p class="editorial-disclosure" role="note"><strong>Prüfbedürftig:</strong> Mindestens ein Absatz hat keinen erreichbaren Beleg. Nicht unabhängig verifiziert.</p>` : ''}${articleContent(a)}
    ${a.coverage?.length ? html`<details class="editorial-coverage"><summary>Weitere Berichterstattung · ${a.coverage.length}</summary>
      ${a.coverage.map(c => html`<section><div class="editorial-kicker">${c.section}</div><h3>${c.headline}</h3>${articleContent(c)}</section>`)}
    </details>` : ''}
    ${!detail && index >= 0 ? html`<a class="editorial-more" data-link href="/morgenbriefing/${day}/artikel/${index}">Artikel & Hintergrund →</a>` : ''}
  </article>`;
}

function articleEntries(e: Edition): { item: Article; index: number }[] {
  const extras = [...(e.additional_articles ?? []), ...(e.additional_magazines ?? [])];
  const entries = e.articles.map((item, index) => ({ item, index }));
  if (e.magazine) entries.push({item: e.magazine, index: entries.length});
  const offset = entries.length;
  return entries.concat(extras.map((item, index) => ({ item, index: index + offset })));
}

export async function editorialView(date?: string, articleIndex?: number): Promise<ViewResult> {
  const response = await fetch('/api/v1/editorial/morgenbriefing.json', { cache: 'no-cache' });
  if (!response.ok && response.status !== 404) throw new Error('Editorial editions unavailable');
  let editions: Edition[] = [];
  if (response.ok && (response.headers.get('content-type') || '').includes('json')) editions = await response.json();
  const e = date ? editions.find(x => x.date === date) : editions[0];
  if (e && articleIndex !== undefined) {
    const a = articleEntries(e).find(x => x.index === articleIndex)?.item;
    if (a) {
      const related = editions.flatMap(issue => articleEntries(issue).map(({item,index: i}) => ({item,i,date:issue.date}))).filter(x => (x.date !== e.date || x.i !== articleIndex) && a.topic && x.item.topic === a.topic);
      const existingTopic = a.topic ? await fetch('/api/v1/topics/' + encodeURIComponent(a.topic) + '.json').then(r => r.ok && (r.headers.get('content-type') || '').includes('json')).catch(() => false) : false;
      return {title:a.headline, nav:'editorial', mode: a.section === 'Magazin' ? 'magazine' : 'news', body:html`<main id="main" tabindex="-1" class="editorial-paper editorial-detail"><a data-link href="/morgenbriefing/${e.date}">← Zur Ausgabe</a>${article(a,articleIndex,e.date,true)}${a.background?.length ? html`<section class="editorial-background editorial-article"><div class="editorial-kicker">Thema vertiefen</div><h2>Hintergrund & Perspektiven</h2>${a.background.map(b => html`<h3>${b.heading}</h3>${shortItem(b)}`)}</section>` : ''}<section class="editorial-article"><h2>Chronologie & verwandte Artikel</h2>${existingTopic ? html`<p><a data-link href="/topic/${a.topic}">PrismUnfold Themenchronologie →</a></p>` : ''}${related.length ? related.map(x => html`<p><a data-link href="/morgenbriefing/${x.date}/artikel/${x.i}">${x.date} · ${x.item.headline}</a></p>`) : html`<p>Noch keine weitere Berichterstattung zu diesem Thema im Archiv.</p>`}</section></main>`};
    }
  }
  if (articleIndex !== undefined) return {title: "Artikel nicht gefunden", nav: "editorial", mode: "news", status: 404, body: html`<main id="main" class="page page--narrow"><h1>Artikel nicht gefunden</h1><a data-link href="/morgenbriefing">Zur Zeitung</a></main>`};
  const news = e ? articleEntries(e).filter(({item}) => item.section !== 'Magazin') : [];
  const magazines = e ? articleEntries(e).filter(({item}) => item.section === 'Magazin') : [];
  return {title: 'Morgenbriefing', nav: 'editorial', mode: 'news', body: html`
    <main id="main" tabindex="-1" class="editorial-paper">
      <header class="editorial-banner"><div class="editorial-kicker">Weltlage · Die persönliche Ausgabe</div>
      <h1>Morgenbriefing</h1><div class="editorial-kicker">Schweiz · Peru · Welt · Magazin</div><p>${e ? new Date(e.date + 'T12:00:00Z').toLocaleDateString('de-CH', {dateStyle: 'full', timeZone: 'Europe/Zurich'}) : 'Noch keine Ausgabe'}</p></header>
      ${editions.length ? html`<nav class="editorial-archive" aria-label="Ausgaben">${editions.map(x => html`<a data-link href="/morgenbriefing/${x.date}" aria-current="${x.date === e?.date ? 'page' : 'false'}">${x.date}</a>`)}</nav>` : ''}
      ${e ? html`<p class="editorial-disclosure">${e.disclosure}</p>
      ${e.bulletin?.lead ? html`<p class="editorial-lead">${e.bulletin.lead}</p><p class="editorial-disclosure">${e.bulletin.disclosure}</p>` : ''}
      <nav class="editorial-contents" aria-label="Inhalt">${[...news, ...magazines].map(({item, index}) => html`<a href="#article-${index}"><span class="editorial-kicker">${item.section}</span><span>${item.headline}</span></a>`)}</nav>
      <div class="editorial-news">${news.map(({item,index}) => article(item,index,e.date))}</div>
      ${magazines.length ? magazines.map(({item,index}, position) => html`<section ${position === 0 ? html`id="magazin"` : ''} class="editorial-magazine"><div class="editorial-magazine-label">MAGAZIN / VERTIEFUNG</div>${article(item,index,e.date)}</section>`) : html`<p class="editorial-disclosure">Magazin noch in redaktioneller Prüfung.</p>`}
      ${e.bulletin?.random_article ? html`<section class="editorial-article"><div class="editorial-kicker">Random des Tages · KI-kuratiert</div><h2>${e.bulletin.random_article.headline}</h2>${articleContent(e.bulletin.random_article)}</section>` : ''}
      ${e.bulletin?.outlook.length ? html`<section class="editorial-article"><h2>Ausblick · KI-kuratiert</h2>${e.bulletin.outlook.map(shortItem)}</section>` : ''}
      ${e.bulletin?.note ? html`<p class="editorial-disclosure">${e.bulletin.note}</p>` : ''}
      ${e.random ? html`<section class="editorial-article"><div class="editorial-kicker">Random des Tages</div>${shortItem(e.random)}</section>` : ''}
      ${e.lagebild?.length ? html`<section class="editorial-article"><h2>Lagebild</h2><p class="editorial-disclosure">Redaktionelle Einschätzung · KI-Analyse</p><div class="editorial-assessments">${e.lagebild.map(item => html`<div><h3>${item.category}</h3>${shortItem(item)}</div>`)}</div></section>` : ''}
      ${e.warnings.length ? html`<details><summary>Redaktionelle Hinweise</summary>${e.warnings.map(w => html`<p>${w}</p>`)}</details>` : ''}` : html`<p>Für diese Ausgabe liegt noch keine veröffentlichte Redaktion vor.</p>`}
    </main>`};
}
