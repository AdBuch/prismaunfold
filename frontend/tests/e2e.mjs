// End-to-end navigation checks. Requires `npm run build`, a running server and Playwright.
// Usage: PORT=4200 node tests/e2e.mjs
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const base = `http://localhost:${process.env.PORT ?? 4200}`;
const browser = await chromium.launch();
const results = [];
const test = async (name, fn) => {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'] });
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

await test('front page shows masthead, date, lead and an end marker', async (p) => {
  await p.goto(base + '/');
  assert.equal(await h1(p), 'Monday, 9 November 2026');
  assert.ok(await p.locator('.masthead__name').isVisible());
  assert.match(await p.locator('.lead__title').innerText(), /Valmera/);
  assert.ok(await p.getByText('That is the whole edition.').isVisible());
});

await test('previous/next edition and select navigate; archive is stable', async (p) => {
  await p.goto(base + '/');
  await p.getByRole('link', { name: /Previous edition/ }).click();
  await p.waitForURL('**/edition/2026-11-08');
  assert.equal(await heading(p, /8 November/), 'Sunday, 8 November 2026');
  assert.match(await p.locator('.lead__title').innerText(), /Cable talks run over/);
  assert.match(await p.locator('.secondary__title').first().innerText(), /Valmera readies/);
  await p.getByRole('link', { name: /Previous edition/ }).click();
  await p.waitForURL('**/edition/2026-11-07');
  await heading(p, /7 November/);
  assert.equal(await p.getByRole('link', { name: /Previous edition/ }).count(), 0);
  await p.selectOption('#edition-select', '2026-11-09');
  await p.waitForURL('**/edition/2026-11-09');
  await heading(p, /9 November/);
  await p.goBack();
  await p.waitForURL('**/edition/2026-11-07');
  assert.equal(await heading(p, /7 November/), 'Saturday, 7 November 2026');
});

await test('story reader, return link, sources and related stories', async (p) => {
  await p.goto(base + '/edition/2026-11-08');
  await p.locator('.lead__title a').click();
  await p.waitForURL('**/story/cable-accord-delay*');
  assert.match(await heading(p, /Cable talks run over/), /Cable talks run over/);
  assert.ok(await p.locator('.correction').isVisible());
  const href = await p.locator('.sources a').first().getAttribute('href');
  assert.match(href, /^https:\/\/example\.org\//);
  await p.locator('.related-card__title a').first().click();
  assert.match(p.url(), /\/story\//);
  await p.goBack();
  await heading(p, /Cable talks run over/);
  await p.getByRole('link', { name: /Edition of 8 November 2026/ }).click();
  await p.waitForURL('**/edition/2026-11-08');
});

await test('timeline: open from story, filter and reorder', async (p) => {
  await p.goto(base + '/story/cable-accord-delay');
  await p.getByRole('link', { name: /Open the full timeline/ }).click();
  await p.waitForURL('**/topic/undersea-cable-accord');
  await heading(p, /undersea-cable accord/);
  assert.equal(await p.locator('.tl').count(), 6);
  await p.getByRole('button', { name: 'Updates and corrections' }).click();
  assert.equal(await p.locator('.tl').count(), 2);
  assert.ok(await p.locator('.tl--correction').isVisible());
  await p.getByRole('button', { name: 'All entries' }).click();
  const firstAsc = await p.locator('.tl__title').first().innerText();
  await p.locator('[data-order]').click();
  assert.notEqual(await p.locator('.tl__title').first().innerText(), firstAsc);
  await p.locator('.tl__links a', { hasText: 'In the edition of 9 November 2026' }).click();
  await p.waitForURL('**/edition/2026-11-09');
});

await test('magazine feature opens from the edition and links to its topic', async (p) => {
  await p.goto(base + '/');
  await p.getByRole('link', { name: 'Read the feature' }).click();
  await p.waitForURL('**/magazine/the-water-that-remembers');
  await heading(p, /Water That Remembers/);
  assert.ok(await p.locator('.mag-quote').first().isVisible());
  assert.ok(await p.locator('.mag-chrono').isVisible());
  await p.getByRole('link', { name: /Open the timeline/ }).click();
  await p.waitForURL('**/topic/valmera-reservoir');
});

await test('share copies the canonical URL', async (p) => {
  await p.goto(base + '/story/valmera-reservoir-vote');
  await p.evaluate(() => { Object.defineProperty(navigator, 'share', { value: undefined, configurable: true }); });
  await p.locator('[data-share]').first().click();
  await p.waitForSelector('#toast.toast--show');
  assert.equal(await p.evaluate(() => navigator.clipboard.readText()), base + '/story/valmera-reservoir-vote');
});

await test('archive date selection validates input', async (p) => {
  await p.goto(base + '/archive');
  await p.fill('#archive-date', '2026-11-01');
  await p.getByRole('button', { name: 'Open edition' }).click();
  assert.ok(await p.locator('[data-archive-error]').isVisible());
  await p.fill('#archive-date', '2026-11-07');
  await p.getByRole('button', { name: 'Open edition' }).click();
  await p.waitForURL('**/edition/2026-11-07');
});

await test('unknown routes and dates are handled', async (p) => {
  await p.goto(base + '/edition/2020-01-01');
  assert.match(await h1(p), /No edition for this date/);
  await p.goto(base + '/story/does-not-exist');
  assert.match(await h1(p), /could not find/);
  await p.goto(base + '/nowhere');
  assert.match(await h1(p), /not in the edition/);
});

await test('no horizontal overflow on mobile for any page', async (p) => {
  await p.setViewportSize({ width: 360, height: 740 });
  for (const path of ['/', '/archive', '/story/cable-accord-delay', '/topic/valmera-reservoir', '/magazine', '/magazine/the-water-that-remembers', '/magazine/terraces-after-dark', '/about']) {
    await p.goto(base + path);
    await p.waitForSelector('#main');
    const over = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert.ok(over <= 0, `${path} overflows by ${over}px`);
  }
});

await browser.close();
for (const r of results) console.log(r.join(' | '));
if (results.some((r) => r[0] === 'FAIL')) process.exit(1);
