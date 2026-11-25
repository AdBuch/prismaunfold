import assert from 'node:assert/strict';
import { test } from 'node:test';
import { editorialView } from '../src/views/editorial.ts';

test('morning briefing renders coverage provenance, perspectives and cleared pictures', async (t) => {
  const original = {
    headline: 'Ein gemeinsames Thema', section: 'Schweiz Politik', lead: '',
    paragraphs: [{ text: 'Aus der Redaktion', source_ids: [] }], sources: [],
  };
  const bulletin = {
    ...original, origin: 'prism-data', paragraphs: [{ text: 'Zusätzlicher  Kontext', source_ids: [] }],
    sources: [{ id: 's', url: 'https://example.org/report', title: 'Bericht', publisher: 'Amt', source_type: 'primary' }],
    uncertainties: ['Das Datum ist offen.'],
    perspectives: [{ text: 'Andere Einschätzung', label: 'Forschung', sources: [] }],
    images: [
      { display: true, url: 'https://example.org/cleared.jpg', alt: 'Bildmotiv', credit: 'Bildautor', license: 'CC BY 4.0' },
      { display: false, url: 'https://example.org/unlicensed.jpg', rights_note: 'Rechte unklar' },
    ],
  };
  const issue = {
    date: '2026-11-25', articles: [{ ...original, coverage: [bulletin] }],
    magazine: { ...original, section: 'Magazin', headline: 'Bestehendes Magazin' },
    additional_articles: [{ ...bulletin, headline: 'Zusätzlicher Bericht' }],
    warnings: [], disclosure: 'Redaktion',
  };
  t.mock.method(globalThis, 'fetch', async () => Response.json([issue]));
  const front = (await editorialView()).body.value;
  for (const value of ['KI-kuratierte Sekundärquelle', 'Andere Einschätzung', 'Das Datum ist offen.',
    'CC BY 4.0', 'Keine Anzeigefreigabe', 'https://example.org/report']) {
    assert.ok(front.includes(value), value);
  }
  assert.match(front, /<img src="https:\/\/example\.org\/cleared\.jpg"/);
  assert.doesNotMatch(front, /unlicensed\.jpg/);
  assert.equal((await editorialView('2026-11-25', 1)).title, 'Bestehendes Magazin');
  assert.equal((await editorialView('2026-11-25', 2)).title, 'Zusätzlicher Bericht');
});

test('a bulletin without a magazine still renders', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => Response.json([{
    date: '2026-11-25', articles: [], magazine: null, warnings: [], disclosure: 'Sekundärquelle',
  }]));
  assert.match((await editorialView()).body.value, /Sekundärquelle/);
});
