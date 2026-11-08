import { html } from '../components/ui.ts';
import { paths } from '../lib/router.ts';
import type { ViewResult } from './types.ts';

export async function aboutView(): Promise<ViewResult> {
  return {
    title: 'About the demo',
    nav: 'about',
    mode: 'news',
    body: html`<main id="main" tabindex="-1" class="page page--narrow">
      <p class="kicker">About</p>
      <h1 class="page__title">A prototype of the PrismUnfold newspaper</h1>
      <p class="page__dek">This is the Phase 2 frontend. It shows how a curated daily edition, a news article, a story timeline and a magazine feature could look and feel.</p>
      <h2 class="small-head">What is fictional</h2>
      <p>All stories, municipalities, states, publishers, statistics and images are invented. Source links point to reserved <code>example.org</code> addresses. Nothing here has been verified, and no real publisher is involved. The artwork is procedurally generated and is a stand-in for credited photography.</p>
      <h2 class="small-head">What works</h2>
      <ul class="plain-list">
        <li>Three dated editions with a stable order and wording. See the <a href="${paths.archive()}" data-link>archive</a>.</li>
        <li>Twelve stories, each with sources, a confidence note and related reading.</li>
        <li>Two topic timelines with milestones, updates and corrections.</li>
        <li>Two magazine features with their own reading style. See the <a href="${paths.magazines()}" data-link>magazine</a>.</li>
        <li>Share links that use the public URL of each page.</li>
      </ul>
      <h2 class="small-head">What is not included</h2>
      <p>Accounts, payments, publisher integrations, live news ingestion and social features are outside Phase 2. Content comes from a typed content service backed by local fixtures, so a real backend can replace it later without touching the views.</p>
    </main>`,
  };
}

export async function notFoundView(path: string): Promise<ViewResult> {
  return {
    title: 'Page not found',
    nav: '',
    mode: 'news',
    status: 404,
    body: html`<main id="main" tabindex="-1" class="page page--narrow">
      <p class="kicker">404</p>
      <h1 class="page__title">This page is not in the edition</h1>
      <p class="page__dek">We could not find <code>${path}</code>.</p>
      <p><a class="btn" href="/" data-link>Go to today's edition</a></p>
    </main>`,
  };
}
