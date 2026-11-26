import assert from 'node:assert/strict';
import { test } from 'node:test';
import { dailyEditions } from '../src/content/daily-fixtures.ts';
import { parseDaily, parseDailyIndex } from '../src/content/daily.ts';
import { FixtureContentService } from '../src/content/fixture-service.ts';
import { compose, fromArticle, topicsForSection, type Candidate } from '../src/lib/composer.ts';
import {
  defaultProfile, isPersonal, loadProfile, migrateLegacy, parseProfile, recordRead, resetAll, saveProfile, savedItems, toggleFollow, toggleSaved,
  history,
} from '../src/lib/profile.ts';
import { allArticles, articleDate } from '../src/models-daily.ts';
import { legacyOrder } from '../src/views/legacy.ts';

// A tiny localStorage for the device-local profile.
const store = new Map<string, string>();
(globalThis as { localStorage?: unknown }).localStorage = {
  getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v),
  removeItem: (k: string) => void store.delete(k), clear: () => store.clear(),
};

const cand = (id: string, o: Partial<Candidate> = {}): Candidate => ({
  id, headline: id, section: 'International', kind: 'news', topics: ['politics'], regions: ['GLOBAL'], importance: 0.5,
  minutes: 2, cluster: id, authors: [], publishers: [], ...o,
});

test('composer keeps the most important global news whatever the interests', () => {
  const p = defaultProfile();
  p.onboarding = 'done';
  p.topicInterests = { science: 1 };
  p.edition.readingTimeMinutes = 6;
  const pool = [cand('war', { importance: 1 }), cand('summit', { importance: 0.8 }), cand('lab', { topics: ['science'], importance: 0.2 }),
    cand('gossip', { topics: ['culture'], importance: 0.1 })];
  const c = compose(pool, p);
  assert.deepEqual(c.items.filter((i) => i.reason === 'global').map((i) => i.id), ['war', 'summit']);
  assert.ok(c.items.some((i) => i.id === 'lab' && i.reason === 'interest'));
});

test('composer avoids ten variants of one event and respects the reading time', () => {
  const p = defaultProfile();
  p.topicInterests = { politics: 1 };
  p.edition.readingTimeMinutes = 10;
  p.edition.discoveryRatio = 0;
  const pool = [...Array.from({ length: 10 }, (_, i) => cand(`v${i}`, { cluster: 'same-event', topicSlug: 'cable', importance: 0.65 })),
    ...Array.from({ length: 10 }, (_, i) => cand(`o${i}`, { section: `S${i % 4}` }))];
  const c = compose(pool, p);
  assert.equal(c.items.filter((i) => i.id.startsWith('v')).length, 1);
  assert.ok(c.minutes <= 10 + 2);
  assert.ok(c.omitted > 0);
});

test('composer keeps a discovery share and follows win over plain interests', () => {
  const p = defaultProfile();
  p.topicInterests = { science: 1 };
  p.follows.topics = ['seed-banks'];
  p.edition.readingTimeMinutes = 10;
  p.edition.discoveryRatio = 0.35;
  const pool = [cand('s1', { topics: ['science'], importance: 0.3 }), cand('s2', { topics: ['science'], importance: 0.4, section: 'Science' }),
    cand('seed', { topics: [], topicSlug: 'seed-banks', importance: 0.2, section: 'Other' }), cand('outside', { topics: ['culture'], importance: 0.6, section: 'Culture' })];
  const c = compose(pool, p);
  assert.equal(c.items.find((i) => i.id === 'seed')?.reason, 'follow');
  assert.equal(c.items.find((i) => i.id === 'outside')?.reason, 'discovery');
  assert.equal(c.items[0]?.id, 'seed');
});

test('composer reports coverage gaps instead of inventing content, and is deterministic', () => {
  const p = defaultProfile();
  p.topicInterests = { culture: 1, science: 0.2 };
  p.geographicInterests = { IT: 1, GLOBAL: 1 };
  const pool = [cand('a'), cand('b')];
  const first = compose(pool, p);
  assert.deepEqual(first.gaps.map((g) => `${g.kind}:${g.key}`), ['region:IT', 'topic:culture']);
  assert.deepEqual(compose([...pool].reverse(), p), first);
});

test('reading history demotes read articles only with behavioural personalisation', () => {
  const p = defaultProfile();
  p.topicInterests = { politics: 1 };
  p.edition.readingTimeMinutes = 2;
  p.edition.discoveryRatio = 0;
  const pool = [cand('read', { importance: 0.6 }), cand('fresh', { importance: 0.5, section: 'Other' })];
  assert.equal(compose(pool, p, new Set(['read'])).items[0]?.id, 'read');
  p.behaviouralPersonalisation = true;
  assert.equal(compose(pool, p, new Set(['read'])).items[0]?.id, 'fresh');
});

test('canonical articles become candidates without copying content', () => {
  const e = dailyEditions[0]!;
  const list = allArticles(e);
  const c = fromArticle(list[0]!, 0, list.length, e.mainHeadline?.articleId);
  assert.equal(c.id, list[0]!.articleId);
  assert.equal(c.importance, 1);
  assert.deepEqual(topicsForSection('Schweiz Politik'), ['politics']);
  assert.deepEqual(topicsForSection('Wirtschaft, Technologie & Wissenschaft'), ['economy', 'technology', 'science']);
});

test('profile: defaults, hostile input, legacy migration, device-local controls', () => {
  store.clear();
  assert.equal(loadProfile().onboarding, 'new');
  assert.equal(isPersonal(loadProfile()), false);
  const hostile = parseProfile(JSON.stringify({ language: '<script>', timezone: '../../etc', topicInterests: { politics: 7, 'bad key!': 1 },
    edition: { readingTimeMinutes: 1e9, discoveryRatio: 3, preferredDeliveryTime: '25:99' }, follows: { topics: [1, 'x'] } }))!;
  assert.equal(hostile.language, 'de-CH');
  assert.equal(hostile.timezone, 'Europe/Zurich');
  assert.deepEqual(hostile.topicInterests, { politics: 1 });
  assert.equal(hostile.edition.readingTimeMinutes, 90);
  assert.equal(hostile.edition.discoveryRatio, 0.5);
  assert.equal(hostile.edition.preferredDeliveryTime, '07:00');
  assert.deepEqual(hostile.follows.topics, ['x']);
  assert.equal(parseProfile('not json'), undefined);

  store.set('prismunfold.preferences.v1', JSON.stringify({ languages: ['de'], regions: ['ch'], sections: ['politics'] }));
  const migrated = loadProfile();
  assert.equal(migrated.language, 'de');
  assert.deepEqual(migrated.geographicInterests, { CH: 1 });
  assert.ok(isPersonal(migrated));
  assert.deepEqual(migrateLegacy({ languages: [], regions: [], sections: [] }), undefined);

  recordRead('a1');
  assert.deepEqual(history(), []); // history is off by default
  const p = loadProfile();
  p.readingHistory = true;
  saveProfile(p);
  recordRead('a1');
  assert.deepEqual(history(), ['a1']);
  p.readingHistory = false;
  saveProfile(p);
  assert.deepEqual(history(), []); // turning it off deletes it
  assert.equal(toggleSaved({ id: 'x', title: 'X', href: '/article/x' }), true);
  assert.equal(savedItems().length, 1);
  assert.equal(toggleFollow('topics', 'seed-banks'), true);
  resetAll();
  assert.equal(store.size, 0);
});

test('daily contract parsing is defensive', () => {
  assert.equal(parseDaily({ date: 'nope' }), undefined);
  const e = parseDaily({ date: '2026-11-25', articles: [
    { articleId: 'ed-2026-11-25-a', headline: 'H', images: [{ url: 'https://img.example.org/a.jpg', display: true, credit: '' },
      { url: 'javascript:alert(1)', display: true, credit: 'x' }], sources: [{ url: 'javascript:x' }, { url: 'https://example.org/a', id: 'a' }] },
    { articleId: 'bad id with spaces', headline: 'X' },
  ] })!;
  assert.equal(e.articles.length, 1);
  const a = e.articles[0]!;
  assert.equal(a.images.filter((i) => i.display).length, 0); // no credit, or not https: never displayed
  assert.equal(a.images.every((i) => i.url === undefined), true);
  assert.deepEqual(a.sources.map((s) => s.url), ['https://example.org/a']);
  assert.equal(a.verification.factual, 'not_independently_verified');
  assert.equal(parseDailyIndex([{ date: '2026-11-24' }, { date: '2026-11-25' }, { date: 'x' }])[0]?.date, '2026-11-25');
  assert.equal(articleDate('pd-2026-11-25-abc'), '2026-11-25');
  assert.equal(articleDate('2026-11-25-0'), '2026-11-25');
  assert.equal(articleDate('nothing'), undefined);
});

test('demo daily fixtures are fictional, labelled and consistent', async () => {
  const svc = new FixtureContentService();
  for (const e of dailyEditions) {
    assert.equal(e.demo, true);
    for (const a of allArticles(e)) {
      assert.equal(articleDate(a.articleId), e.date);
      for (const s of a.sources) { assert.match(s.url, /^https:\/\/example\.org\/demo\//); assert.match(s.publisher, /\(fictional\)$/); }
      const found = await svc.getArticle(a.articleId);
      assert.equal(found?.article.articleId, a.articleId);
    }
  }
  assert.equal((await svc.getArticle('pd-2026-11-09-valmera'))?.parent?.articleId, 'ed-2026-11-09-valmerawat');
  assert.equal((await svc.listDaily())[0]?.date, '2026-11-09');
});

test('0.2 article indexes map to the same articles', () => {
  const e = dailyEditions[0]!;
  const order = legacyOrder(e);
  // authored news (Good News last), then the authored magazine
  assert.equal(order[0]?.articleId, e.articles[0]?.articleId);
  assert.equal(order[e.articles.length]?.kind, 'good_news');
  assert.equal(order[e.articles.length + 1]?.kind, 'magazine');
});
