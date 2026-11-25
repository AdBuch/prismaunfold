import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ApiContentService } from '../src/content/api-service.ts';
import { ContentError } from '../src/content/content-service.ts';
import { applyPrefs, matches, parsePrefs } from '../src/lib/prefs.ts';

const image = { motif: 'grid', seed: 1, alt: 'Abstract illustration', caption: 'c', credit: 'not a photograph' };
const edition = (date: string, slugs: string[]) => ({
  id: `edition-${date}`, date, number: 1, editorsNote: 'note', briefs: [], magazineTeaser: '', demo: false,
  placements: slugs.map((storySlug, i) => ({
    storySlug, section: 'energy', slot: i === 0 ? 'lead' : 'standard', order: i + 1,
    snapshot: { headline: storySlug, teaser: 't', image },
  })),
});
const story = (slug: string, relatedSlugs: string[] = []) => ({
  id: slug, slug, section: 'energy', headline: `Headline ${slug}`, standfirst: 's', body: ['s'], byline: 'Codex',
  aiDisclosure: 'ai', publishedAt: '2026-11-12T10:00:00+00:00', corrections: [], confidence: 'reported',
  confidenceNote: 'n', relatedSlugs, image, demo: false,
  sources: [{ id: 'a1', name: 'Example', title: 'T', url: 'https://example.org/a' }],
  sentences: [{ text: 's', sourceIds: ['a1'], verification: null }],
  verification: { state: 'unverified', reasons: [] },
});

type Routes = Record<string, { status?: number; body?: unknown; text?: string; fail?: boolean }>;

function service(routes: Routes) {
  const calls: string[] = [];
  const fetchFn = async (input: string): Promise<Response> => {
    calls.push(input);
    const route = routes[input.replace('/api/v1/', '')];
    if (!route) return new Response('not found', { status: 404 });
    if (route.fail) throw new TypeError('network down');
    return new Response(route.text ?? JSON.stringify(route.body), { status: route.status ?? 200 });
  };
  return { svc: new ApiContentService('/api/v1', fetchFn), calls };
}

test('editions are listed newest first and navigable', async () => {
  const { svc } = service({ 'editions.json': { body: [edition('2026-11-11', ['a']), edition('2026-11-13', ['c']), edition('2026-11-12', ['b'])] } });
  assert.deepEqual((await svc.listEditions()).map((e) => e.date), ['2026-11-13', '2026-11-12', '2026-11-11']);
  assert.equal((await svc.getLatestEdition())?.date, '2026-11-13');
  assert.deepEqual(await svc.getAdjacentEditions('2026-11-12'), { previous: '2026-11-11', next: '2026-11-13' });
  assert.deepEqual(await svc.getAdjacentEditions('2026-11-13'), { previous: '2026-11-12' });
  assert.equal(await svc.getEdition('2020-01-01'), undefined);
  assert.deepEqual((await svc.getEditionsForStory('b')).map((e) => e.date), ['2026-11-12']);
});

test('nothing published yet is an empty state, not an error', async () => {
  const { svc } = service({});
  assert.deepEqual(await svc.listEditions(), []);
  assert.equal(await svc.getLatestEdition(), undefined);
  assert.deepEqual(await svc.listMagazines(), []);
  assert.deepEqual(await svc.getSiteInfo(), { sections: [], languages: [], regions: [] });
});

test('stories, related stories and topics are read from their own files', async () => {
  const { svc } = service({
    'stories/a.json': { body: story('a', ['b', 'missing']) },
    'stories/b.json': { body: story('b') },
    'topics/energy.json': { body: { slug: 'energy', title: 'Energy', summary: 's', section: 'energy', events: [], image, demo: false } },
  });
  assert.equal((await svc.getStory('a'))?.headline, 'Headline a');
  assert.deepEqual((await svc.getRelatedStories('a')).map((s) => s.slug), ['b']);
  assert.equal((await svc.getTopic('energy'))?.title, 'Energy');
  assert.equal(await svc.getStory('nope'), undefined);
});

test('odd slugs never become request paths', async () => {
  const { svc, calls } = service({});
  for (const slug of ['../index', 'a/b', 'a?x=1', '', 'a%2f..', 'x'.repeat(200)]) {
    assert.equal(await svc.getStory(slug), undefined);
    assert.equal(await svc.getTopic(slug), undefined);
  }
  assert.deepEqual(calls, []);
});

test('network failures and server errors reject with ContentError and are not cached', async () => {
  const routes: Routes = { 'editions.json': { fail: true } };
  const { svc, calls } = service(routes);
  await assert.rejects(svc.listEditions(), (e) => e instanceof ContentError && e.kind === 'network');
  routes['editions.json'] = { status: 503, body: {} };
  await assert.rejects(svc.listEditions(), (e) => e instanceof ContentError && e.kind === 'network');
  routes['editions.json'] = { body: [edition('2026-11-12', ['a'])] };
  assert.equal((await svc.listEditions()).length, 1); // a retry reaches the server again
  assert.equal(calls.length, 3);
  await svc.listEditions();
  assert.equal(calls.length, 3); // a success is cached
});

test('unreadable or malformed content is rejected instead of rendered', async () => {
  const { svc } = service({
    'editions.json': { body: { not: 'a list' } },
    'stories/a.json': { body: { slug: 'a' } },
    'stories/b.json': { text: '<html>gateway error</html>' },
    'magazines.json': { body: [{ slug: 1 }, 'x', null] },
  });
  await assert.rejects(svc.listEditions(), (e) => e instanceof ContentError && e.kind === 'invalid');
  await assert.rejects(svc.getStory('a'), (e) => e instanceof ContentError && e.kind === 'invalid');
  await assert.rejects(svc.getStory('b'), (e) => e instanceof ContentError && e.kind === 'invalid');
  assert.deepEqual(await svc.listMagazines(), []);
});

test('malformed entries inside a list are skipped', async () => {
  const { svc } = service({ 'editions.json': { body: [edition('2026-11-12', ['a']), { date: 'tomorrow' }, null, 7] } });
  assert.deepEqual((await svc.listEditions()).map((e) => e.date), ['2026-11-12']);
});

test('site info keeps only well-formed sections and strings', async () => {
  const { svc } = service({ 'index.json': { body: { sections: [{ id: 'energy', label: 'Energy' }, { id: 3 }, null], languages: ['de', 5], regions: 'ch', generatedAt: '2026-11-12T10:00:00Z' } } });
  assert.deepEqual(await svc.getSiteInfo(), { sections: [{ id: 'energy', label: 'Energy' }], languages: ['de'], regions: [], generatedAt: '2026-11-12T10:00:00Z' });
});

test('preferences: empty means everything, stored text is never trusted', () => {
  const none = parsePrefs(null);
  assert.deepEqual(none, { languages: [], regions: [], sections: [] });
  assert.deepEqual(parsePrefs('{broken'), none);
  assert.deepEqual(parsePrefs('"text"'), none);
  assert.deepEqual(parsePrefs(JSON.stringify({ languages: ['de', 7, null], regions: 'ch', sections: { a: 1 } })), { languages: ['de'], regions: [], sections: [] });
  assert.ok(matches(none, { section: 'x', language: 'es', regions: ['pe'] }));
});

test('preferences filter by language, region and section', () => {
  const prefs = { languages: ['de'], regions: ['ch'], sections: [] };
  assert.ok(matches(prefs, { section: 's', language: 'de', regions: ['ch', 'eu'] }));
  assert.ok(!matches(prefs, { section: 's', language: 'en', regions: ['ch'] }));
  assert.ok(!matches(prefs, { section: 's', language: 'de', regions: ['pe'] }));
  assert.ok(matches(prefs, { section: 's', language: 'de' })); // no region: not tied to a place
  assert.ok(!matches({ languages: [], regions: [], sections: ['energy'] }, { section: 'trade' }));
});

test('preferences never hide the lead and keep the rest reachable', () => {
  const items = [
    { id: 'lead', section: 'trade', language: 'en' },
    { id: 'mine', section: 'energy', language: 'de' },
    { id: 'other', section: 'trade', language: 'es' },
  ];
  const { mine, outside } = applyPrefs(items, { languages: ['de'], regions: [], sections: [] });
  assert.deepEqual(mine.map((i) => i.id), ['lead', 'mine']);
  assert.deepEqual(outside.map((i) => i.id), ['other']);
  const all = applyPrefs(items, { languages: [], regions: [], sections: [] });
  assert.equal(all.mine.length, 3);
  assert.equal(all.outside.length, 0);
});
