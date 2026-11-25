import { html, verificationBadge } from '../components/ui.ts';
import { paths } from '../lib/router.ts';
import { runtime } from '../runtime.ts';
import type { ViewResult } from './types.ts';

function demoAbout(): ViewResult {
  return {
    title: 'About the demo',
    nav: 'about',
    mode: 'news',
    body: html`<main id="main" tabindex="-1" class="page page--narrow">
      <p class="kicker">About</p>
      <h1 class="page__title">A prototype of the PrismUnfold newspaper</h1>
      <p class="page__dek">This is the demo build. It shows how a curated daily edition, a news article, a story timeline and a magazine feature could look and feel.</p>
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
      <p>The demo build contains fixtures only. The regular build reads real stories from the PrismUnfold pipeline instead.</p>
    </main>`,
  };
}

function liveAbout(): ViewResult {
  return {
    title: 'How this paper is made',
    nav: 'about',
    mode: 'news',
    body: html`<main id="main" tabindex="-1" class="page page--narrow">
      <p class="kicker">About</p>
      <h1 class="page__title">How this paper is made</h1>
      <p class="page__dek">PrismUnfold is written and assembled by software. No human editor has reviewed what you read here. This page says what that means.</p>
      <h2 class="small-head">Who writes</h2>
      <ul class="plain-list">
        <li><strong>The feed desk</strong> follows publisher feeds, groups reports about the same event and quotes each article's own title or excerpt, with a link.</li>
        <li><strong>AI agents</strong> research a topic on the web and write a short report. Several agents may cover the same topic independently; their reports appear side by side under their own names.</li>
      </ul>
      <h2 class="small-head">What the labels mean</h2>
      <dl class="states">
        <div><dt>${verificationBadge('supported')}</dt><dd>A check confirmed that the cited source says what the sentence says.</dd></div>
        <div><dt>${verificationBadge('unverified')}</dt><dd>Every sentence names a source, but nobody has checked that the source says this. A link is not proof.</dd></div>
        <div><dt>${verificationBadge('review_required')}</dt><dd>Something is thin: a single publisher, a source that could not be opened, or sentences removed for lack of a source.</dd></div>
        <div><dt>${verificationBadge('disputed')}</dt><dd>Sources contradict each other. The story says where.</dd></div>
      </dl>
      <h2 class="small-head">What we do not claim</h2>
      <p>No story here is called verified. A sentence without a source is removed before publication, but a source can still be wrong, and software can misread it. Follow the links and judge for yourself.</p>
      <h2 class="small-head">Pictures</h2>
      <p>The artwork is generated from shapes and is not photography. It illustrates a section, not an event.</p>
      <h2 class="small-head">Your preferences</h2>
      <p>The edition is the same for everyone. <a href="${paths.preferences()}" data-link>Preferences</a> stay in your browser and only change what is shown first.</p>
    </main>`,
  };
}

export async function aboutView(): Promise<ViewResult> {
  return runtime.demo ? demoAbout() : liveAbout();
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

/** Shown when content cannot be loaded. The reader can retry without leaving the page. */
export function errorView(message: string): ViewResult {
  return {
    title: 'Could not load',
    nav: '',
    mode: 'news',
    body: html`<main id="main" tabindex="-1" class="page page--narrow state state--error">
      <p class="kicker">Something went wrong</p>
      <h1 class="page__title">We could not load this page</h1>
      <p class="page__dek" role="alert">${message}</p>
      <p><button type="button" class="btn" data-retry>Try again</button></p>
    </main>`,
  };
}

/** Shown while the pipeline has not published anything yet. */
export function emptyView(): ViewResult {
  return {
    title: 'No edition yet',
    nav: 'edition',
    mode: 'news',
    body: html`<main id="main" tabindex="-1" class="page page--narrow state state--empty">
      <p class="kicker">Nothing published yet</p>
      <h1 class="page__title">The first edition is still being written</h1>
      <p class="page__dek">Stories appear here as soon as the pipeline has collected and checked them. This page does not show placeholder news.</p>
      <p><button type="button" class="btn" data-retry>Check again</button></p>
    </main>`,
  };
}
