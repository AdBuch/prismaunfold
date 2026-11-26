import assert from 'node:assert/strict';
import { test } from 'node:test';
import { matchRoute } from '../src/lib/router.ts';
import { esc, formatLong, html, isIsoDate } from '../src/lib/util.ts';

test('routes of the unified newspaper', () => {
  assert.deepEqual(matchRoute('/'), { name: 'today' });
  assert.deepEqual(matchRoute('/edition/today'), { name: 'today' });
  assert.deepEqual(matchRoute('/edition/2026-11-08/'), { name: 'today', date: '2026-11-08' });
  assert.deepEqual(matchRoute('/article/ed-2026-11-09-abc'), { name: 'article', id: 'ed-2026-11-09-abc' });
  assert.deepEqual(matchRoute('/world'), { name: 'world' });
  assert.deepEqual(matchRoute('/archive'), { name: 'archive' });
  assert.deepEqual(matchRoute('/story/some-slug'), { name: 'story', slug: 'some-slug' });
  assert.deepEqual(matchRoute('/topics'), { name: 'topics' });
  assert.deepEqual(matchRoute('/topic/x'), { name: 'topic', slug: 'x' });
  assert.deepEqual(matchRoute('/magazine/x'), { name: 'magazine', slug: 'x' });
  assert.deepEqual(matchRoute('/magazine'), { name: 'magazines' });
  assert.deepEqual(matchRoute('/author/lea-marti'), { name: 'author', slug: 'lea-marti' });
  assert.deepEqual(matchRoute('/me'), { name: 'me' });
  assert.equal(matchRoute('/nope/at/all').name, 'notfound');
  assert.equal(matchRoute('/story').name, 'notfound');
  assert.equal(matchRoute('/article/<script>').name, 'notfound');
  assert.equal(matchRoute('/%E0%A4%A').name, 'notfound'); // malformed escape does not throw
});

test('0.2 URLs keep working', () => {
  assert.deepEqual(matchRoute('/preferences'), { name: 'redirect', to: '/me' });
  assert.deepEqual(matchRoute('/morgenbriefing'), { name: 'redirect', to: '/' });
  assert.deepEqual(matchRoute('/morgenbriefing/2026-11-25'), { name: 'redirect', to: '/edition/2026-11-25' });
  assert.deepEqual(matchRoute('/morgenbriefing/2026-11-25/artikel/3'), { name: 'legacyArticle', date: '2026-11-25', index: 3 });
  assert.equal(matchRoute('/morgenbriefing/yesterday').name, 'notfound');
});

test('html template escapes interpolated text', () => {
  const out = html`<p>${'<script>alert(1)</script>'}</p>`.value;
  assert.equal(out, '<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>');
  assert.equal(esc(`"'&`), '&quot;&#39;&amp;');
  assert.equal(html`<b>${html`<i>x</i>`}</b>`.value, '<b><i>x</i></b>');
});

test('dates are timezone independent', () => {
  assert.equal(formatLong('2026-11-09'), 'Monday, 9 November 2026');
  assert.ok(isIsoDate('2026-02-28'));
  assert.ok(!isIsoDate('2026-13-01'));
  assert.ok(!isIsoDate('yesterday'));
});
