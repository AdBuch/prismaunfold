import { html, sectionLabel } from '../components/ui.ts';
import type { ContentService } from '../content/content-service.ts';
import { OUTSIDE_LIMIT, loadPrefs, savePrefs, type Preferences } from '../lib/prefs.ts';
import type { Raw } from '../lib/util.ts';
import type { ViewResult } from './types.ts';

const LANGUAGE_NAMES: Record<string, string> = { de: 'Deutsch', en: 'English', es: 'Español', fr: 'Français', it: 'Italiano' };

function group(name: keyof Preferences, legend: string, options: { value: string; label: string }[], chosen: string[]): Raw {
  if (!options.length) return html`<fieldset class="prefs__group"><legend>${legend}</legend><p class="hint">Nothing to choose from yet.</p></fieldset>`;
  return html`<fieldset class="prefs__group"><legend>${legend}</legend>
    ${options.map((o) => html`<label class="prefs__option"><input type="checkbox" name="${name}" value="${o.value}" ${chosen.includes(o.value) ? html`checked` : ''}> <span>${o.label}</span></label>`)}
  </fieldset>`;
}

export async function preferencesView(svc: ContentService): Promise<ViewResult> {
  const info = await svc.getSiteInfo();
  const prefs = loadPrefs();
  const body = html`<main id="main" tabindex="-1" class="page page--narrow">
    <p class="kicker">Preferences</p>
    <h1 class="page__title">What you want to read first</h1>
    <p class="page__dek">Choose languages, regions and sections. Leave a group empty to see everything in it.</p>
    <form class="prefs" data-prefs-form>
      ${group('languages', 'Languages', info.languages.map((l) => ({ value: l, label: LANGUAGE_NAMES[l] ?? l })), prefs.languages)}
      ${group('regions', 'Regions', info.regions.map((r) => ({ value: r, label: r.toUpperCase() })), prefs.regions)}
      ${group('sections', 'Sections', info.sections.map((s) => ({ value: s.id, label: sectionLabel(s.id) })), prefs.sections)}
      <div class="prefs__actions">
        <button class="btn" type="submit">Save</button>
        <button class="btn btn--ghost" type="button" data-prefs-clear>Show everything</button>
      </div>
      <p class="prefs__status" data-prefs-status role="status"></p>
    </form>
    <h2 class="small-head">How this works</h2>
    <ul class="plain-list">
      <li>Your choices stay in this browser. They are not sent to PrismUnfold or anyone else.</li>
      <li>The edition is the same for every reader. Your choices only decide what is shown first.</li>
      <li>The lead story is always shown, and up to ${OUTSIDE_LIMIT} stories from outside your selection stay visible, so you still see what else happened.</li>
    </ul>
  </main>`;

  return {
    title: 'Preferences',
    nav: 'preferences',
    mode: 'news',
    body,
    mount(root) {
      const form = root.querySelector<HTMLFormElement>('[data-prefs-form]');
      const status = root.querySelector<HTMLElement>('[data-prefs-status]');
      const say = (text: string) => { if (status) status.textContent = text; };
      const read = (name: keyof Preferences): string[] =>
        [...(form?.querySelectorAll<HTMLInputElement>(`input[name="${name}"]:checked`) ?? [])].map((i) => i.value);
      form?.addEventListener('submit', (ev) => {
        ev.preventDefault();
        const ok = savePrefs({ languages: read('languages'), regions: read('regions'), sections: read('sections') });
        say(ok ? 'Saved in this browser.' : 'This browser does not allow saving. Your choices apply until you close the page.');
      });
      root.querySelector('[data-prefs-clear]')?.addEventListener('click', () => {
        form?.querySelectorAll<HTMLInputElement>('input[type="checkbox"]').forEach((i) => { i.checked = false; });
        savePrefs({ languages: [], regions: [], sections: [] });
        say('Showing everything.');
      });
    },
  };
}
