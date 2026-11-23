import { html } from '../lib/util.ts';
import type { ViewResult } from './types.ts';

type Source = { id: string; url: string; title: string; publisher: string };
type Article = { section: string; headline: string; lead: string; paragraphs: { heading?: string; text: string; source_ids: string[] }[]; sources: Source[] };
type ShortItem = { text: string; sources: Source[] };
type Edition = { random?: ShortItem; lagebild?: (ShortItem & { category: string })[]; date: string; articles: Article[]; magazine: Article; disclosure: string; warnings: string[] };

function article(a: Article, index: number) {
  const ids = new Map(a.sources.map((s, i) => [s.id, i + 1]));
  return html`<article class="editorial-article" id="article-${index}">
    <div class="editorial-kicker">${a.section}</div><h2>${a.headline}</h2><p class="editorial-lead">${a.lead}</p>
    ${a.paragraphs.map(p => html`${p.heading ? html`<h3>${p.heading}</h3>` : ''}<p>${p.text} <sup>${p.source_ids.map(id => ids.get(id)).filter(Boolean).join(', ')}</sup></p>`)}
    <details class="editorial-sources"><summary>Quellen · ${a.sources.length}</summary><ol>${a.sources.map(s => html`<li><a href="${/^https?:\/\//i.test(s.url) ? s.url : '#'}" target="_blank" rel="noopener noreferrer">${s.publisher}: ${s.title}</a></li>`)}</ol></details>
  </article>`;
}

function shortItem(item: ShortItem) {
  return html`<p>${item.text}</p><details class="editorial-sources"><summary>Quellen</summary><ul>${item.sources.map(s => html`<li><a href="${/^https?:\/\//i.test(s.url) ? s.url : '#'}" target="_blank" rel="noopener noreferrer">${s.publisher}: ${s.title}</a></li>`)}</ul></details>`;
}

export async function editorialView(date?: string): Promise<ViewResult> {
  const response = await fetch('/api/v1/editorial/morgenbriefing.json', { cache: 'no-cache' });
  if (!response.ok && response.status !== 404) throw new Error('Editorial editions unavailable');
  let editions: Edition[] = [];
  if (response.ok && (response.headers.get('content-type') || '').includes('json')) editions = await response.json();
  const e = date ? editions.find(x => x.date === date) : editions[0];
  return {title: 'Morgenbriefing', nav: 'editorial', mode: 'news', body: html`
    <main id="main" tabindex="-1" class="editorial-paper">
      <header class="editorial-banner"><div class="editorial-kicker">Die persönliche Zeitung · ChatGPT / Codex</div>
      <h1>Morgenbriefing</h1><p>${e ? new Date(e.date + 'T12:00:00Z').toLocaleDateString('de-CH', {dateStyle: 'full', timeZone: 'Europe/Zurich'}) : 'Noch keine Ausgabe'}</p></header>
      ${editions.length ? html`<nav class="editorial-archive" aria-label="Ausgaben">${editions.map(x => html`<a data-link href="/morgenbriefing/${x.date}" aria-current="${x.date === e?.date ? 'page' : 'false'}">${x.date}</a>`)}</nav>` : ''}
      ${e ? html`<p class="editorial-disclosure">${e.disclosure}</p>
      <nav class="editorial-contents" aria-label="Inhalt">${e.articles.map((a,i) => html`<a href="#article-${i}">${a.section}: ${a.headline}</a>`)}<a href="#magazin">Magazin: ${e.magazine.headline}</a></nav>
      <div class="editorial-news">${e.articles.map((a,i) => article(a,i))}</div>
      <section id="magazin" class="editorial-magazine"><div class="editorial-magazine-label">MAGAZIN / VERTIEFUNG</div>${article(e.magazine,e.articles.length)}</section>
      ${e.random ? html`<section class="editorial-article"><div class="editorial-kicker">Random des Tages</div>${shortItem(e.random)}</section>` : ''}
      ${e.lagebild?.length ? html`<section class="editorial-article"><h2>Lagebild</h2><p class="editorial-disclosure">Redaktionelle Einschätzung · KI-Analyse</p><div class="editorial-news">${e.lagebild.map(item => html`<div><h3>${item.category}</h3>${shortItem(item)}</div>`)}</div></section>` : ''}
      ${e.warnings.length ? html`<details><summary>Redaktionelle Hinweise</summary>${e.warnings.map(w => html`<p>${w}</p>`)}</details>` : ''}` : html`<p>Für diese Ausgabe liegt noch keine veröffentlichte Redaktion vor.</p>`}
    </main>`};
}
