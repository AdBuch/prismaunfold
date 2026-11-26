// Desktop and mobile screenshots of the main pages (demo build by default).
// Usage: PORT=4200 OUT=screenshots node tests/screenshots.mjs
// CHROME_PATH=/usr/bin/google-chrome uses a local Chrome instead of Playwright's Chromium.
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';

const base = process.env.BASE_URL ?? `http://localhost:${process.env.PORT ?? 4200}`;
const out = process.env.OUT ?? 'screenshots';
const pages = (process.env.PAGES ?? '/,/article/ed-2026-11-09-valmerawat,/article/ed-2026-11-09-magazine-water,/world,/magazine,/topics,/topic/valmera-water,/archive,/me').split(',');
const viewports = { desktop: { width: 1366, height: 900 }, mobile: { width: 390, height: 844 } };

await mkdir(out, { recursive: true });
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
for (const [name, viewport] of Object.entries(viewports)) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: name === 'mobile' ? 2 : 1, reducedMotion: 'reduce' });
  // PROFILE=1 shows the personal edition of a sample reader (home Peru, science, 10 minutes).
  if (process.env.PROFILE) {
    await ctx.addInitScript(() => localStorage.setItem('prismunfold.profile.v1', JSON.stringify({
      version: 1, language: 'de-CH', timezone: 'Europe/Zurich', homeRegion: 'PE', geographicInterests: { PE: 1 },
      topicInterests: { science: 1, culture: 1 }, edition: { readingTimeMinutes: 10, preferredDeliveryTime: '07:00', discoveryRatio: 0.2, depth: 'standard' },
      follows: { topics: [], authors: [], publishers: [] }, recurringSections: ['magazine', 'good_news'], behaviouralPersonalisation: false,
      readingHistory: false, onboarding: 'done' })));
  }
  const page = await ctx.newPage();
  for (const path of pages) {
    await page.goto(base + path);
    await page.waitForSelector('main h1', { timeout: 15000 });
    // Lazy images load only when scrolled into view.
    await page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 40)); } window.scrollTo(0, 0); });
    await page.waitForTimeout(300);
    const file = `${out}/${name}${process.env.PROFILE ? '-personal' : ''}-${(path.replace(/^\/|\/$/g, '') || 'today').replace(/[/]/g, '_')}.png`;
    await page.screenshot({ path: file, fullPage: !!process.env.FULL });
    console.log(file);
  }
  await ctx.close();
}
await browser.close();
