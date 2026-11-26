// End-to-end checks of the real build against a running stack (docker compose).
// The stories come from the pipeline, not from fixtures.
// Usage: BASE_URL=http://localhost:8080 EXPECT_HEADLINE="..." node tests/e2e-api.mjs
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const base = process.env.BASE_URL ?? 'http://localhost:8080';
const expectHeadline = process.env.EXPECT_HEADLINE ?? '';
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const results = [];
const test = async (name, fn, viewport = { width: 1280, height: 900 }) => {
  const ctx = await browser.newContext({ viewport });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  try { await fn(page); assert.deepEqual(errors, [], 'no page errors'); results.push(['ok', name]); }
  catch (e) { results.push(['FAIL', name, e.message]); }
  await ctx.close();
};
const ready = (page, selector) => page.waitForSelector(selector, { timeout: 15000 });

await test('front page shows a real lead story and no demo banner', async (p) => {
  await p.goto(base + '/');
  await ready(p, '.lead__title');
  const headline = await p.locator('.lead__title').innerText();
  assert.ok(headline.trim().length > 0);
  if (expectHeadline) assert.match(headline, new RegExp(expectHeadline));
  assert.equal(await p.locator('.demo-banner').count(), 0);
  assert.match(await p.locator('.editors-note').innerText(), /no human editor/);
  assert.ok(await p.getByText('That is the whole edition.').isVisible());
});

await test('story reader links every sentence to a source and states how sure we are', async (p) => {
  await p.goto(base + '/');
  await ready(p, '.lead__title a');
  await p.locator('.lead__title a').click();
  await ready(p, '.story__title');
  assert.ok((await p.locator('.claim').count()) >= 1);
  assert.equal(await p.locator('.claim').count(), await p.locator('.claim:has(.cite a)').count(), 'every sentence cites a source');
  const sources = p.locator('.sources li a');
  assert.ok((await sources.count()) >= 1);
  assert.match(await sources.first().getAttribute('href'), /^https?:\/\//);
  assert.equal(await sources.first().getAttribute('rel'), 'noopener noreferrer');
  assert.ok(await p.locator('.assess .verify').isVisible());
  assert.doesNotMatch(await p.locator('.assess').innerText(), /verified by|Established by several sources/i);
  assert.match(await p.locator('.story__disclosure').innerText(), /Not reviewed by a human editor/);
  // A source reference jumps to its entry without reloading the view.
  await p.locator('.cite a').first().click();
  assert.ok(await p.locator('.story__title').isVisible());
});

await test('archive, timeline, preferences and about are reachable', async (p) => {
  await p.goto(base + '/archive');
  await ready(p, '.archive-item');
  await p.goto(base + '/');
  await ready(p, '.lead__title a');
  await p.locator('.lead__title a').click();
  await ready(p, '.story__title');
  const timeline = p.getByRole('link', { name: /Open the full timeline/ });
  if (await timeline.count()) {
    await timeline.click();
    await ready(p, '.timeline');
  }
  await p.goto(base + '/preferences'); // 0.2 URL redirects to My PrismUnfold
  await p.waitForURL('**/me');
  await ready(p, '[data-profile-form]');
  await p.goto(base + '/about');
  await ready(p, '.states');
  assert.match(await p.locator('main h1').innerText(), /How this paper is made/);
});

// The pipeline's unified daily edition (api/v1/daily), e.g. an imported and approved prism-data bulletin.
const daily = await fetch(base + '/api/v1/daily/index.json').then((r) => (r.ok ? r.json() : [])).catch(() => []);
if (daily.length) {
  await test('the daily edition from the pipeline renders as one newspaper with provenance', async (p) => {
    const date = daily[0].date;
    await p.goto(`${base}/edition/${date}`);
    await ready(p, '.lead__title a');
    assert.match(await p.locator('.lead__title').innerText(), new RegExp(daily[0].mainHeadline.headline.slice(0, 20).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    await p.locator('.lead__title a').click();
    await ready(p, '.story__title');
    assert.match(p.url(), /\/article\//);
    await p.locator('#evidence summary').click();
    assert.match(await p.locator('#evidence').innerText(), /not independently verified/);
    assert.match(await p.locator('#evidence').innerText(), /ChatGPT bulletin|AI editorial worker/);
    await p.goto(`${base}/morgenbriefing/${date}`); // 0.2 URL
    await p.waitForURL(`**/edition/${date}`);
  });
}

await test('unknown story and unknown date are handled', async (p) => {
  await p.goto(base + '/story/does-not-exist');
  await p.waitForFunction(() => /could not find/i.test(document.querySelector('main h1')?.textContent ?? ''));
  await p.goto(base + '/edition/2020-01-01');
  await p.waitForFunction(() => /No edition/i.test(document.querySelector('main h1')?.textContent ?? ''));
});

await test('no horizontal overflow on a phone', async (p) => {
  for (const path of ['/', '/world', '/archive', '/me', '/about', '/magazine', '/topics']) {
    await p.goto(base + path);
    await ready(p, 'main');
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    assert.ok(overflow <= 1, `${path} overflows by ${overflow}px`);
  }
}, { width: 375, height: 740 });

await browser.close();
for (const [status, name, message] of results) console.log(`${status}  ${name}${message ? `\n      ${message}` : ''}`);
if (results.some(([status]) => status === 'FAIL')) process.exit(1);
