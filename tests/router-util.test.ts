import assert from 'node:assert/strict';
import { test } from 'node:test';
import { matchRoute } from '../src/lib/router.ts';
import { esc, formatLong, html, isIsoDate } from '../src/lib/util.ts';

test('routes match the brief', () => {
  assert.deepEqual(matchRoute('/'), { name: 'edition', date: 'today' });
  assert.deepEqual(matchRoute('/edition/today'), { name: 'edition', date: 'today' });
  assert.deepEqual(matchRoute('/edition/2026-11-08/'), { name: 'edition', date: '2026-11-08' });
  assert.deepEqual(matchRoute('/archive'), { name: 'archive' });
  assert.deepEqual(matchRoute('/story/some-slug'), { name: 'story', slug: 'some-slug' });
  assert.deepEqual(matchRoute('/topic/x'), { name: 'topic', slug: 'x' });
  assert.deepEqual(matchRoute('/magazine/x'), { name: 'magazine', slug: 'x' });
  assert.deepEqual(matchRoute('/magazine'), { name: 'magazines' });
  assert.equal(matchRoute('/nope/at/all').name, 'notfound');
  assert.equal(matchRoute('/story').name, 'notfound');
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
