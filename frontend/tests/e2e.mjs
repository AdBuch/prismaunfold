// End-to-end checks of the demo build (fictional fixtures). Requires `npm run build:demo`,
// a running server and Playwright. Usage: PORT=4200 node tests/e2e.mjs
// CHROME_PATH=/usr/bin/google-chrome uses a local Chrome instead of Playwright's Chromium.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const base = `http://localhost:${process.env.PORT ?? 4200}`;
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const results = [];
const test = async (name, fn, viewport = { width: 1280, height: 900 }) => {
  const ctx = await browser.newContext({ viewport, permissions: ['clipboard-read', 'clipboard-write'] });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  try { await fn(page); assert.deepEqual(errors, [], 'no page errors'); results.push(['ok', name]); }
  catch (e) { results.push(['FAIL', name, e.message]); }
  await ctx.close();
};
const h1 = (page) => page.locator('main h1').first().innerText();
// Views render asynchronously after the URL changes, so wait for the heading before asserting.
const heading = async (page, re) => {
  await page.waitForFunction((src) => new RegExp(src).test(document.querySelector('main h1')?.textContent ?? ''), re.source);
  return h1(page);
};

await test('Today: one newspaper with masthead, lead, sections, magazine and an end', async (p) => {
  await p.goto(base + '/');
  assert.equal(await heading(p, /November/), 'Monday, 9 November 2026');
  assert.ok(await p.locator('.masthead__name').isVisible());
  assert.match(await p.locator('.lead__title').innerText(), /Cable talks/);
  assert.equal(await p.locator('nav[aria-label="Primary"] a').count(), 6);
  assert.equal(await p.getByRole('link', { name: 'Morgenbriefing' }).count(), 0); // no separate publication
  assert.ok(await p.getByText('More reporting').isVisible()); // feed-desk stories in the same paper
  assert.ok(await p.locator('#feature-heading').isVisible());
  assert.ok(await p.getByRole('heading', { name: 'Good News' }).isVisible());
  assert.ok(await p.getByText('Updated since publication').isVisible());
  assert.ok(await p.getByText('That is the whole edition.').isVisible());
  assert.equal(await p.getAttribute('link[rel="canonical"]', 'href'), `${base}/edition/2026-11-09`);
});

await test('edition navigation and the archive keep historical editions', async (p) => {
  await p.goto(base + '/');
  await heading(p, /9 November/);
  await p.getByRole('link', { name: /Previous edition/ }).click();
  await p.waitForURL('**/edition/2026-11-08');
  assert.equal(await heading(p, /8 November/), 'Sunday, 8 November 2026');
  assert.ok(await p.getByText('Partial edition', { exact: true }).isVisible());
  await p.selectOption('#edition-select', '2026-11-07');
  await p.waitForURL('**/edition/2026-11-07');
  await heading(p, /7 November/);
  assert.match(await p.locator('.lead__title').innerText(), /./); // feed-only date still renders
  await p.goto(base + '/archive');
  await heading(p, /Previous editions/);
  await p.fill('#archive-date', '2026-11-01');
  await p.getByRole('button', { name: 'Open edition' }).click();
  assert.ok(await p.locator('[data-archive-error]').isVisible());
  await p.fill('#archive-date', '2026-11-08');
  await p.getByRole('button', { name: 'Open edition' }).click();
  await p.waitForURL('**/edition/2026-11-08');
});

await test('article unfolds in layers: overview, text, context, perspectives, evidence', async (p) => {
  await p.goto(base + '/');
  await p.getByRole('link', { name: /Valmera agrees to share/ }).first().click();
  await p.waitForURL('**/article/ed-2026-11-09-valmerawat');
  await heading(p, /Valmera agrees/);
  assert.ok(await p.getByText('Why it matters.').isVisible());
  assert.equal(await p.locator('.story__body .cite').count(), 4);
  for (const name of ['Context', 'Perspectives', 'Evidence and transparency']) {
    const layer = p.locator('details.layer', { has: p.locator('.layer__name', { hasText: name }) });
    assert.equal(await layer.getAttribute('open'), null, `${name} starts folded`);
    await layer.locator('summary').click();
    assert.notEqual(await layer.getAttribute('open'), null);
  }
  assert.ok(await p.getByText('Opposition').isVisible());
  assert.ok(await p.getByText('What is not known').isVisible());
  assert.ok(await p.getByText('Other contributors on the same event').isVisible());
  assert.match(await p.locator('#evidence').innerText(), /not independently verified/);
  await p.locator('#evidence .sources a').first().evaluate((a) => a.getAttribute('rel')).then((rel) => assert.equal(rel, 'noopener noreferrer'));
  assert.equal(await p.getAttribute('meta[property="og:type"]', 'content'), 'article');
});

await test('image rights decide rendering; AI illustrations are labelled', async (p) => {
  await p.goto(base + '/article/ed-2026-11-09-darksky');
  await heading(p, /dark-sky/);
  assert.ok(await p.locator('.ai-label').isVisible());
  await p.goto(base + '/article/ed-2026-11-09-seedvault');
  await heading(p, /Seeds stored/);
  assert.equal(await p.locator('main img').count(), 0); // no cleared image: text-led layout
  await p.locator('#evidence summary').click();
  assert.match(await p.locator('#evidence').innerText(), /rights not cleared for display/);
  for (const img of await p.locator('img').all()) assert.ok((await img.getAttribute('alt'))?.length, 'every image has alt text');
});

await test('magazine: daily features and earlier features in one place', async (p) => {
  await p.goto(base + '/');
  await p.getByRole('link', { name: 'Read the feature' }).click();
  await p.waitForURL('**/article/ed-2026-11-09-magazine-water');
  await heading(p, /Who owns a spring/);
  assert.equal(await p.evaluate(() => document.documentElement.dataset.mode), 'magazine');
  await p.goto(base + '/magazine');
  await heading(p, /Background/);
  assert.ok(await p.getByRole('link', { name: /Who owns a spring/ }).first().isVisible());
  await p.getByRole('link', { name: /The Water That Remembers/i }).first().click();
  await p.waitForURL('**/magazine/the-water-that-remembers');
  assert.ok(await p.locator('.mag-quote').first().isVisible());
});

await test('topics and dossiers connect chronology, background and open questions', async (p) => {
  await p.goto(base + '/topics');
  await heading(p, /Dossiers/);
  await p.getByRole('link', { name: /Valmera water/ }).click();
  await p.waitForURL('**/topic/valmera-water');
  await heading(p, /Valmera water/);
  assert.ok(await p.getByText('Why the spring matters').isVisible());
  assert.equal(await p.getByText('Why the spring matters').count(), 1); // background shown once
  assert.ok(await p.getByRole('heading', { name: 'Open questions' }).isVisible());
  await p.goto(base + '/topic/undersea-cable-accord');
  await heading(p, /undersea-cable accord/i);
  assert.equal(await p.locator('.tl').count(), 6);
  await p.getByRole('button', { name: 'Updates and corrections' }).click();
  assert.equal(await p.locator('.tl:visible').count(), 2);
  await p.getByRole('button', { name: 'Follow this topic' }).click();
  await p.goto(base + '/me');
  await heading(p, /paper yours|Your newspaper/);
  assert.ok(await p.getByRole('link', { name: /Undersea cable accord/i }).isVisible());
});

await test('voices: contributor pages are labelled as assembled records', async (p) => {
  await p.goto(base + '/article/ed-2026-11-09-valmerawat');
  await p.getByRole('link', { name: 'Lea Marti' }).click();
  await p.waitForURL('**/author/lea-marti');
  await heading(p, /Lea Marti/);
  assert.match(await p.locator('.notice').innerText(), /Automatically assembled record/);
  assert.equal(await p.getAttribute('meta[name="robots"]', 'content'), 'noindex, nofollow');
  await p.goto(base + '/author/codex');
  assert.match(await heading(p, /Codex/), /AI editorial worker/);
});

await test('onboarding builds a personal edition from the same articles', async (p) => {
  await p.goto(base + '/');
  assert.ok(await p.getByText('Make this paper yours in two minutes').isVisible());
  await p.getByRole('link', { name: 'Set up my edition' }).click();
  await p.waitForURL('**/me*');
  await heading(p, /Make this paper yours/);
  assert.equal(await p.getAttribute('meta[name="robots"]', 'content'), 'noindex, nofollow');
  await p.selectOption('select[name="homeRegion"]', 'PE');
  await p.check('input[name="topic-science"][value="1"]');
  await p.check('input[name="topic-culture"][value="1"]');
  await p.selectOption('select[name="minutes"]', '10');
  await p.getByRole('button', { name: 'Save and read my edition' }).click();
  await p.waitForURL(base + '/');
  await heading(p, /9 November/);
  assert.ok(await p.getByText('Your edition', { exact: true }).isVisible());
  assert.ok(await p.getByText('Important for everyone today').first().isVisible()); // the global news stays
  assert.match(await p.locator('main').innerText(), /Matches your interest in (Science|Peru)/);
  assert.ok(await p.getByText('Not covered today').isVisible()); // culture: a gap, not invented content
  assert.equal(await p.getAttribute('link[rel="canonical"]', 'href'), `${base}/edition/2026-11-09`);
  await p.getByRole('link', { name: 'Read the public edition' }).click();
  await p.waitForURL('**/edition/2026-11-09?edition=public');
  assert.ok(await p.getByText("Today's edition", { exact: true }).isVisible());
});

await test('save, history and reset stay on the device', async (p) => {
  await p.goto(base + '/article/ed-2026-11-09-library');
  await heading(p, /library/);
  await p.getByRole('button', { name: 'Save', exact: true }).click();
  await p.goto(base + '/me');
  await heading(p, /paper yours|Your newspaper/);
  assert.ok(await p.getByRole('link', { name: /library that lends drills/ }).isVisible());
  await p.getByRole('button', { name: 'Reset everything' }).click();
  await p.getByRole('button', { name: /Confirm/ }).click();
  await p.waitForFunction(() => !document.body.innerText.includes('library that lends drills'));
  assert.equal(await p.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith('prismunfold')).length), 0);
});

await test('0.2 URLs redirect to their successors', async (p) => {
  await p.goto(base + '/preferences');
  await p.waitForURL('**/me');
  await p.goto(base + '/morgenbriefing');
  await p.waitForURL(base + '/');
  await p.goto(base + '/morgenbriefing/2026-11-09');
  await p.waitForURL('**/edition/2026-11-09');
  await p.goto(base + '/morgenbriefing/2026-11-09/artikel/1');
  await p.waitForURL('**/article/ed-2026-11-09-valmerawat');
  await heading(p, /Valmera agrees/);
  await p.goBack();
  assert.notEqual(new URL(p.url()).pathname, '/morgenbriefing/2026-11-09/artikel/1'); // replaced, no redirect loop
});

await test('The World is public and shows continuing coverage once', async (p) => {
  await p.goto(base + '/world');
  await heading(p, /What is happening/);
  const headlines = await p.locator('main h2 a, main h3 a').allInnerTexts();
  assert.equal(headlines.filter((h) => /Cable talks/.test(h)).length, 1); // newest article of the event only
  assert.ok(await p.getByRole('heading', { name: 'From the newsroom' }).isVisible());
});

await test('share copies the canonical URL', async (p) => {
  await p.goto(base + '/article/ed-2026-11-09-cabletalks');
  await heading(p, /Cable talks/);
  await p.evaluate(() => { Object.defineProperty(navigator, 'share', { value: undefined, configurable: true }); });
  await p.locator('[data-share]').first().click();
  await p.waitForSelector('#toast.toast--show');
  assert.equal(await p.evaluate(() => navigator.clipboard.readText()), base + '/article/ed-2026-11-09-cabletalks');
});

await test('unknown routes, dates and articles are handled', async (p) => {
  await p.goto(base + '/edition/2020-01-01');
  assert.match(await heading(p, /No edition/), /No edition for this date/);
  await p.goto(base + '/article/ed-2026-11-09-nothing');
  assert.match(await heading(p, /could not find/), /could not find/);
  await p.goto(base + '/story/does-not-exist');
  assert.match(await heading(p, /could not find/), /could not find/);
  await p.goto(base + '/nowhere');
  assert.match(await heading(p, /not in the edition/), /not in the edition/);
});

await test('accessibility basics on every page: one h1, named controls, keyboard layers', async (p) => {
  for (const path of ['/', '/world', '/magazine', '/topics', '/archive', '/me', '/article/ed-2026-11-09-cabletalks', '/about']) {
    await p.goto(base + path);
    await p.waitForSelector('main h1');
    assert.equal(await p.locator('h1').count(), 1, `${path}: one h1`);
    const unnamed = await p.evaluate(() => [...document.querySelectorAll('button, a[href], select, input')]
      .filter((el) => !(el.getAttribute('aria-label') || el.textContent?.trim() || el.labels?.length || el.getAttribute('aria-hidden') === 'true' || el.closest('[aria-hidden="true"]')))
      .map((el) => el.outerHTML.slice(0, 80)));
    assert.deepEqual(unnamed, [], `${path}: unnamed controls`);
  }
  await p.goto(base + '/article/ed-2026-11-09-cabletalks');
  await p.waitForSelector('#context summary');
  await p.focus('#context summary');
  await p.keyboard.press('Enter');
  assert.notEqual(await p.getAttribute('#context', 'open'), null);
});

await test('no horizontal overflow on a phone', async (p) => {
  for (const path of ['/', '/world', '/archive', '/article/ed-2026-11-09-valmerawat', '/article/ed-2026-11-09-magazine-water', '/topic/valmera-water',
    '/topics', '/magazine', '/magazine/the-water-that-remembers', '/me', '/about', '/story/cable-accord-delay']) {
    await p.goto(base + path);
    await p.waitForSelector('main h1');
    const over = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert.ok(over <= 0, `${path} overflows by ${over}px`);
  }
}, { width: 360, height: 740 });

await browser.close();
for (const r of results) console.log(r.join(' | '));
if (results.some((r) => r[0] === 'FAIL')) process.exit(1);
