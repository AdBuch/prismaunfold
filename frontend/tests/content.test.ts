import assert from 'node:assert/strict';
import { test } from 'node:test';
import { editions } from '../src/content/editions.ts';
import { FixtureContentService } from '../src/content/fixture-service.ts';
import { magazines } from '../src/content/magazines.ts';
import { stories } from '../src/content/stories.ts';
import { topics } from '../src/content/topics.ts';

const svc = new FixtureContentService();

test('fixtures meet the brief: counts', () => {
  assert.ok(editions.length >= 3);
  assert.ok(stories.length >= 8 && stories.length <= 12);
  assert.ok(magazines.length >= 2);
  assert.ok(topics.length >= 2);
});

test('all fixture content is flagged as demo and sources use example.org', () => {
  for (const x of [...stories, ...topics, ...magazines, ...editions]) assert.equal(x.demo, true);
  for (const s of [...stories.flatMap((s) => s.sources), ...magazines.flatMap((m) => m.sources)]) {
    assert.match(s.url, /^https:\/\/example\.org\/demo\//);
    assert.match(s.name, /\(fictional\)$/);
  }
});

test('ids and slugs are unique', () => {
  for (const list of [stories.map((s) => s.slug), stories.map((s) => s.id), editions.map((e) => e.date), topics.map((t) => t.slug), magazines.map((m) => m.slug)]) {
    assert.equal(new Set(list).size, list.length);
  }
});

test('every reference resolves', () => {
  const slugs = new Set(stories.map((s) => s.slug));
  const topicSlugs = new Set(topics.map((t) => t.slug));
  const magSlugs = new Set(magazines.map((m) => m.slug));
  const dates = new Set(editions.map((e) => e.date));
  for (const s of stories) {
    for (const r of s.relatedSlugs) assert.ok(slugs.has(r), `${s.slug} -> ${r}`);
    if (s.topicSlug) assert.ok(topicSlugs.has(s.topicSlug));
  }
  for (const e of editions) {
    assert.ok(magSlugs.has(e.magazineSlug));
    for (const p of e.placements) assert.ok(slugs.has(p.storySlug));
    for (const b of e.briefs) if (b.storySlug) assert.ok(slugs.has(b.storySlug));
  }
  for (const t of topics) for (const ev of t.events) {
    if (ev.storySlug) assert.ok(slugs.has(ev.storySlug));
    if (ev.editionDate) assert.ok(dates.has(ev.editionDate));
  }
  for (const m of magazines) {
    for (const r of m.relatedStorySlugs) assert.ok(slugs.has(r));
    for (const r of m.relatedFeatureSlugs) assert.ok(magSlugs.has(r));
  }
});

test('each edition has one lead, unique stories and a clear order', () => {
  for (const e of editions) {
    assert.equal(e.placements.filter((p) => p.slot === 'lead').length, 1);
    const slugs = e.placements.map((p) => p.storySlug);
    assert.equal(new Set(slugs).size, slugs.length);
    const orders = e.placements.map((p) => p.order);
    assert.deepEqual([...orders].sort((a, b) => a - b), orders.map((_, i) => i + 1));
  }
});

test('stories are never placed in an edition before they were published', () => {
  for (const e of editions) for (const p of e.placements) {
    const s = stories.find((x) => x.slug === p.storySlug)!;
    assert.ok(s.publishedAt.slice(0, 10) <= e.date, `${s.slug} in ${e.date}`);
  }
});

test('archived edition keeps its snapshot wording even if the story changes', async () => {
  const ed = await svc.getEdition('2026-11-08');
  const p = ed!.placements.find((x) => x.storySlug === 'valmera-reservoir-consultation')!;
  const story = await svc.getStory('valmera-reservoir-consultation');
  assert.notEqual(p.snapshot.headline, story!.headline);
  const again = await svc.getEdition('2026-11-08');
  assert.equal(again!.placements.find((x) => x.storySlug === p.storySlug)!.snapshot.headline, p.snapshot.headline);
});

test('adjacent edition navigation', async () => {
  assert.deepEqual(await svc.getAdjacentEditions('2026-11-08'), { previous: '2026-11-07', next: '2026-11-09' });
  assert.deepEqual(await svc.getAdjacentEditions('2026-11-07'), { next: '2026-11-08' });
  assert.deepEqual(await svc.getAdjacentEditions('2026-11-09'), { previous: '2026-11-08' });
  assert.equal((await svc.getLatestEdition())?.date, '2026-11-09');
  assert.deepEqual((await svc.listEditions()).map((e) => e.date), ['2026-11-09', '2026-11-08', '2026-11-07']);
});

test('timelines are chronological and distinguish corrections', () => {
  for (const t of topics) {
    const dates = t.events.map((e) => e.date);
    assert.deepEqual([...dates].sort(), dates);
    assert.ok(t.events.length >= 5);
  }
  const cable = topics.find((t) => t.slug === 'undersea-cable-accord')!;
  assert.ok(cable.events.some((e) => e.kind === 'correction'));
  assert.ok(cable.events.some((e) => e.kind === 'update'));
});

test('stories with corrections show them, and related stories resolve', async () => {
  const s = await svc.getStory('cable-accord-delay');
  assert.equal(s!.corrections.length, 1);
  assert.ok((await svc.getRelatedStories('cable-accord-delay')).length >= 2);
  assert.deepEqual((await svc.getEditionsForStory('valmera-reservoir-vote')).map((e) => e.date), ['2026-11-09']);
});
