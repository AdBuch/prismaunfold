/**
 * My PrismUnfold: onboarding, reading preferences, follows, saved articles, history
 * and privacy controls. Everything lives on this device (localStorage); there are no
 * accounts yet, so nothing is synchronised or sent anywhere.
 */
import { html, raw } from '../components/ui.ts';
import { humanize } from '../content/collect.ts';
import type { ContentService } from '../content/content-service.ts';
import {
  INTEREST_KEYS, RECURRING, REGIONS, clearHistory, history, loadProfile, resetAll, saveProfile, savedItems, toggleFollow, toggleSaved,
  type ReaderProfile,
} from '../lib/profile.ts';
import { paths } from '../lib/router.ts';
import type { Raw } from '../lib/util.ts';
import type { ViewResult } from './types.ts';

const LANGUAGES: [string, string][] = [['de-CH', 'Deutsch (Schweiz)'], ['de-DE', 'Deutsch'], ['en', 'English'], ['es-PE', 'Español (Perú)'], ['fr-CH', 'Français'], ['it-CH', 'Italiano']];
const LEVELS: [number, string][] = [[0, 'No'], [0.5, 'Some'], [1, 'Very']];
const checked = (on: boolean): Raw => (on ? raw('checked') : raw(''));
const selected = (on: boolean): Raw => (on ? raw('selected') : raw(''));

function zones(current: string): string[] {
  const intl = Intl as typeof Intl & { supportedValuesOf?: (k: string) => string[] };
  const list = intl.supportedValuesOf ? intl.supportedValuesOf('timeZone') : ['Europe/Zurich', 'Europe/Berlin', 'America/Lima', 'UTC'];
  return list.includes(current) ? list : [current, ...list];
}

function form(p: ReaderProfile): Raw {
  const extra = Object.keys(p.geographicInterests);
  return html`<form class="prefs onboarding" data-profile-form id="setup" aria-labelledby="setup-h">
    <h2 id="setup-h" class="small-head">Your newspaper</h2>
    <div class="prefs__row">
      <label class="prefs__field">Reading language
        <select name="language">${LANGUAGES.map(([v, l]) => html`<option value="${v}" ${selected(p.language === v)}>${l}</option>`)}</select></label>
      <label class="prefs__field">Home country or region
        <select name="homeRegion"><option value="">Not set</option>${REGIONS.filter((r) => r.code !== 'GLOBAL').map((r) => html`<option value="${r.code}" ${selected(p.homeRegion === r.code)}>${r.label}</option>`)}</select></label>
    </div>
    <fieldset class="prefs__group"><legend>Also follow news from</legend>
      ${REGIONS.map((r) => html`<label class="prefs__option"><input type="checkbox" name="regions" value="${r.code}" ${checked(extra.includes(r.code))}> <span>${r.label}</span></label>`)}
    </fieldset>
    <fieldset class="prefs__group prefs__group--topics"><legend>How interested are you in</legend>
      ${INTEREST_KEYS.map((t) => html`<div class="level" role="radiogroup" aria-label="${t.label}"><span class="level__name">${t.label}</span>${LEVELS.map(([w, l]) => html`
        <label class="level__opt"><input type="radio" name="topic-${t.key}" value="${w}" ${checked((p.topicInterests[t.key] ?? 0) === w)}> <span>${l}</span></label>`)}</div>`)}
    </fieldset>
    <div class="prefs__row">
      <label class="prefs__field">Daily reading time
        <select name="minutes">${[5, 10, 15, 20, 30, 45].map((m) => html`<option value="${m}" ${selected(p.edition.readingTimeMinutes === m)}>${m} minutes</option>`)}</select></label>
      <label class="prefs__field">Level of detail
        <select name="depth">${([['brief', 'Brief'], ['standard', 'Standard'], ['deep', 'In depth']] as const).map(([v, l]) => html`<option value="${v}" ${selected(p.edition.depth === v)}>${l}</option>`)}</select></label>
      <label class="prefs__field">Beyond my interests
        <select name="discovery">${([[0.1, 'A little'], [0.2, 'Some'], [0.35, 'A lot']] as const).map(([v, l]) => html`<option value="${v}" ${selected(Math.abs(p.edition.discoveryRatio - v) < 0.01)}>${l}</option>`)}</select></label>
    </div>
    <div class="prefs__row">
      <label class="prefs__field">Edition ready at <input type="time" name="time" value="${p.edition.preferredDeliveryTime}"></label>
      <label class="prefs__field">Time zone <select name="timezone">${zones(p.timezone).map((z) => html`<option value="${z}" ${selected(p.timezone === z)}>${z}</option>`)}</select></label>
    </div>
    <p class="hint">Today the edition is published at 07:00 Europe/Zurich for everyone; the time is stored for personal delivery later.</p>
    <fieldset class="prefs__group"><legend>Always include</legend>
      ${RECURRING.map((r) => html`<label class="prefs__option"><input type="checkbox" name="recurring" value="${r.key}" ${checked(p.recurringSections.includes(r.key))}> <span>${r.label}</span></label>`)}
    </fieldset>
    <fieldset class="prefs__group"><legend>Privacy</legend>
      <label class="prefs__option"><input type="checkbox" name="history" ${checked(p.readingHistory)}> <span>Keep a reading history on this device</span></label>
      <label class="prefs__option"><input type="checkbox" name="behaviour" ${checked(p.behaviouralPersonalisation)}> <span>Use it to move articles I have read further down</span></label>
    </fieldset>
    <div class="prefs__actions">
      <button class="btn" type="submit">Save and read my edition</button>
      <a class="btn btn--ghost" href="/?edition=public" data-link data-skip>Skip: read the public edition</a>
    </div>
    <p class="prefs__status" data-profile-status role="status"></p>
  </form>`;
}

export async function meView(svc: ContentService): Promise<ViewResult> {
  await svc.getSiteInfo().catch(() => undefined);
  const p = loadProfile();
  const saved = savedItems();
  const read = history();
  const follows = ([['topics', 'Topics'], ['authors', 'Authors'], ['publishers', 'Publishers']] as const);

  const body = html`<main id="main" tabindex="-1" class="page page--narrow me">
    <p class="kicker">My PrismUnfold</p>
    <h1 class="page__title">${p.onboarding === 'done' ? 'Your newspaper' : 'Make this paper yours'}</h1>
    <p class="page__dek">Your choices decide which articles you see first, in which language and depth. They never change what an article says.</p>
    <p class="notice"><strong>Stored on this device only.</strong> There are no PrismUnfold accounts yet: nothing is synchronised or sent to us, to AI systems or to anyone else. Another browser starts empty.</p>
    ${form(p)}
    <section aria-labelledby="follow-h"><h2 id="follow-h" class="small-head">Following</h2>
      ${follows.map(([kind, label]) => html`<h3 class="assess__sub">${label}</h3>${p.follows[kind].length ? html`<ul class="plain-list">${p.follows[kind].map((x) => html`<li class="row">
        ${kind === 'topics' ? html`<a href="${paths.topic(x)}" data-link>${humanize(x)}</a>` : kind === 'authors' ? html`<a href="${paths.author(x)}" data-link>${humanize(x)}</a>` : x}
        <button type="button" class="btn btn--ghost" data-unfollow="${kind}" data-value="${x}">Remove</button></li>`)}</ul>`
        : html`<p class="hint">Nothing yet. ${kind === 'topics' ? html`Follow a topic from any article or <a href="${paths.topics()}" data-link>dossier</a>.` : kind === 'authors' ? 'Follow an author from their page.' : 'Publisher follows are planned.'}</p>`}`)}
    </section>
    <section aria-labelledby="saved-h"><h2 id="saved-h" class="small-head">Saved articles</h2>
      ${saved.length ? html`<ul class="plain-list">${saved.map((s) => html`<li class="row"><a href="${s.href}" data-link>${s.title}</a>
        <button type="button" class="btn btn--ghost" data-unsave="${s.id}">Remove</button></li>`)}</ul>` : html`<p class="hint">Use “Save” on an article to keep it here.</p>`}
    </section>
    <section aria-labelledby="hist-h"><h2 id="hist-h" class="small-head">Reading history</h2>
      <p>${p.readingHistory ? `${read.length} article${read.length === 1 ? '' : 's'} recorded on this device.` : 'Off. Nothing is recorded.'}</p>
      ${read.length ? html`<button type="button" class="btn btn--ghost" data-clear-history>Clear reading history</button>` : ''}
    </section>
    <section aria-labelledby="reset-h"><h2 id="reset-h" class="small-head">Start over</h2>
      <p>Remove your settings, follows, saved articles and history from this device. The public edition stays available.</p>
      <button type="button" class="btn btn--ghost" data-reset>Reset everything</button>
      <details class="tx"><summary>Exactly what is stored</summary><pre class="profile-json">${JSON.stringify(p, null, 2)}</pre></details>
    </section>
  </main>`;

  return {
    title: 'My PrismUnfold', nav: 'me', mode: 'news', body, meta: { noindex: true, canonical: paths.me() },
    mount(root) {
      const formEl = root.querySelector<HTMLFormElement>('[data-profile-form]');
      const status = root.querySelector<HTMLElement>('[data-profile-status]');
      const value = (name: string) => (formEl?.elements.namedItem(name) as HTMLInputElement | HTMLSelectElement | null)?.value ?? '';
      const all = (name: string) => [...(formEl?.querySelectorAll<HTMLInputElement>(`input[name="${name}"]:checked`) ?? [])].map((i) => i.value);
      const box = (name: string) => !!formEl?.querySelector<HTMLInputElement>(`input[name="${name}"]`)?.checked;
      formEl?.addEventListener('submit', (ev) => {
        ev.preventDefault();
        const next = loadProfile();
        next.language = value('language') || next.language;
        next.homeRegion = value('homeRegion');
        next.geographicInterests = Object.fromEntries(all('regions').map((r) => [r, r === next.homeRegion ? 1 : 0.8]));
        if (next.homeRegion) next.geographicInterests[next.homeRegion] = 1;
        next.topicInterests = Object.fromEntries(INTEREST_KEYS.map((t) => [t.key, Number(all(`topic-${t.key}`)[0] ?? 0)]).filter(([, w]) => (w as number) > 0));
        next.edition = { readingTimeMinutes: Number(value('minutes')) || 15, preferredDeliveryTime: value('time') || '07:00',
          discoveryRatio: Number(value('discovery')) || 0.2, depth: (value('depth') as ReaderProfile['edition']['depth']) || 'standard' };
        next.timezone = value('timezone') || next.timezone;
        next.recurringSections = all('recurring');
        next.readingHistory = box('history');
        next.behaviouralPersonalisation = box('behaviour') && next.readingHistory;
        next.onboarding = 'done';
        const ok = saveProfile(next);
        if (!ok && status) { status.textContent = 'This browser does not allow saving. Your choices apply until you close the page.'; return; }
        document.dispatchEvent(new CustomEvent('navigate', { detail: '/' }));
      });
      root.querySelector('[data-skip]')?.addEventListener('click', () => {
        const next = loadProfile();
        if (next.onboarding === 'new') { next.onboarding = 'skipped'; saveProfile(next); }
      });
      const refresh = () => document.dispatchEvent(new CustomEvent('navigate', { detail: paths.me() }));
      root.querySelectorAll<HTMLButtonElement>('[data-unfollow]').forEach((b) => b.addEventListener('click', () => {
        toggleFollow(b.dataset['unfollow'] as keyof ReaderProfile['follows'], b.dataset['value'] ?? '');
        refresh();
      }));
      root.querySelectorAll<HTMLButtonElement>('[data-unsave]').forEach((b) => b.addEventListener('click', () => {
        toggleSaved({ id: b.dataset['unsave'] ?? '', title: '', href: '/' });
        refresh();
      }));
      root.querySelector('[data-clear-history]')?.addEventListener('click', () => { clearHistory(); refresh(); });
      const reset = root.querySelector<HTMLButtonElement>('[data-reset]');
      reset?.addEventListener('click', () => {
        if (reset.dataset['armed'] !== '1') { reset.dataset['armed'] = '1'; reset.textContent = 'Confirm: remove everything'; return; }
        resetAll();
        refresh();
      });
    },
  };
}
