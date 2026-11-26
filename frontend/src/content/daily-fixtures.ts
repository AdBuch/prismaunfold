/**
 * FICTIONAL demo daily editions in the `prismunfold.daily-edition/1` shape.
 * Every place, person, publisher, figure and link is invented; links use the
 * reserved example.org domain; images are generated SVG stand-ins. Used only by the
 * demo build and tests; the production build does not bundle this file.
 */
import { artSvg } from '../lib/art.ts';
import type { ArtMotif } from '../models.ts';
import type { DailyArticle, DailyEdition, DailyImage, DailySource } from '../models-daily.ts';

const src = (id: string, publisher: string, title: string, publishedAt: string, linkStatus = 'reachable', access = 'open'): DailySource =>
  ({ id, url: `https://example.org/demo/${id}`, title, publisher: publisher.endsWith('(fictional)') ? publisher : `${publisher} (fictional)`, publishedAt, linkStatus, access, sourceType: 'news report' });

function demoImage(motif: ArtMotif, seed: number, alt: string, caption: string, origin: DailyImage['origin'] = 'licensed_photo'): DailyImage {
  const svg = artSvg({ motif, seed, alt, caption, credit: '' });
  return {
    url: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`, alt, caption,
    credit: origin === 'ai_illustration' ? 'PrismUnfold demo illustration' : 'Demo picture desk (fictional)',
    license: 'Demo only', licenseUrl: '', rights: 'approved', rightsNote: 'Generated stand-in, not a photograph.',
    sourceUrl: '', origin, display: true,
  };
}

interface Draft {
  id: string; section: string; headline: string; lead: string; paragraphs: [string, string[]][]; sources: DailySource[];
  kind?: string; topic?: string; regions?: string[]; importance?: number; provider?: string; images?: DailyImage[];
  perspectives?: DailyArticle['perspectives']; uncertainties?: string[]; background?: DailyArticle['background'];
  coverage?: DailyArticle[]; whyItMatters?: string; summary?: string; reviewRequired?: boolean; authors?: DailyArticle['authors'];
  corrections?: DailyArticle['corrections'];
}

function art(d: Draft): DailyArticle {
  const provider = d.provider ?? 'codex';
  return {
    articleId: d.id, kind: d.kind ?? 'news', section: d.section, headline: d.headline, lead: d.lead, topic: d.topic,
    paragraphs: d.paragraphs.map(([text, sourceIds]) => ({ text, sourceIds, reviewRequired: false })),
    sources: d.sources, images: d.images ?? [], perspectives: d.perspectives ?? [], uncertainties: d.uncertainties ?? [],
    background: d.background ?? [], reviewRequired: d.reviewRequired ?? false,
    limitations: provider === 'prism-data' ? ['item_level_citations'] : [],
    verification: { sourceAccess: [...new Set(d.sources.map((s) => s.linkStatus ?? 'unknown'))], factual: 'not_independently_verified' },
    provenance: { provider, originType: 'ai_secondary', publicationBasis: provider === 'prism-data' ? 'upstream_published' : 'validated',
      citationLevel: provider === 'prism-data' ? 'item' : 'paragraph', generatedAt: '2026-11-09T05:40:00+01:00' },
    coverage: d.coverage ?? [], regions: d.regions ?? [], importance: d.importance, whyItMatters: d.whyItMatters,
    summary: d.summary, authors: d.authors, corrections: d.corrections, language: 'en',
  };
}

const D9 = '2026-11-09';
const s9 = {
  valmera: src('valmera-council', 'Valmera Courier', 'Council approves water-sharing plan after night session', '2026-11-09T06:10:00+01:00'),
  canton: src('canton-notice', 'Cantonal Gazette (fictional)', 'Official notice: water-sharing agreement', '2026-11-08T17:00:00+01:00'),
  cable: src('cable-wire', 'Northern Wire', 'Cable talks enter second week', '2026-11-08T21:30:00+01:00'),
  cableDoc: src('cable-draft', 'Commission for the Strait (fictional)', 'Draft framework, public version', '2026-11-07T12:00:00+01:00', 'restricted'),
  andes: src('andes-radio', 'Radio Altiplano (fictional)', 'Terrace farmers report early harvest', '2026-11-08T15:00:00-05:00'),
  andesMin: src('andes-ministry', 'Ministry of Highlands (fictional)', 'Seasonal bulletin: rainfall and soil', '2026-11-06T09:00:00-05:00'),
  lib: src('library-things', 'Lakeside Weekly (fictional)', 'The library that lends drills turns one', '2026-11-08T10:00:00+01:00'),
  seed: src('seed-vault', 'Science Desk Review (fictional)', 'Seed bank completes cold storage test', '2026-11-08T08:00:00+00:00'),
  seedPaper: src('seed-paper', 'Journal of Plant Archives (fictional)', 'Viability after ten years at minus 18 °C', '2026-10-30T00:00:00+00:00'),
  grid: src('grid-report', 'Energy Observer (fictional)', 'Winter grid reserve set at record level', '2026-11-08T19:00:00+01:00'),
  gridOp: src('grid-operator', 'Northgrid Operator (fictional)', 'Reserve tender results', '2026-11-08T16:00:00+01:00'),
  night: src('night-sky', 'Valley Observer (fictional)', 'Dark-sky zone extended along the ridge', '2026-11-08T20:00:00+01:00'),
};

const water = art({
  id: 'ed-2026-11-09-valmerawat', section: 'Switzerland', topic: 'valmera-water', regions: ['CH'], importance: 0.9,
  headline: 'Valmera agrees to share its spring water with two neighbouring villages',
  lead: 'After a session that ran past midnight, the council approved a ten-year sharing plan. The canton still has to confirm it.',
  summary: 'A small valley town will share spring water with two villages for ten years, pending cantonal approval.',
  whyItMatters: 'Three dry summers left the lower villages on trucked water; the plan is the first binding agreement between the communities.',
  paragraphs: [
    ['The council of Valmera approved the plan by eleven votes to four shortly after 1 a.m., according to the local paper.', ['valmera-council']],
    ['The agreement reserves a fixed share of the spring for the villages of Orsa and Pianel in months when the reservoir falls below a set level.', ['valmera-council', 'canton-notice']],
    ['The cantonal office must still confirm the plan; its notice gives no date for a decision.', ['canton-notice']],
  ],
  sources: [s9.valmera, s9.canton],
  images: [demoImage('alpine', 4, 'A reservoir below a mountain ridge', 'The upper reservoir of Valmera (demo image).')],
  perspectives: [
    { label: 'Council majority', text: 'Supporters said the plan gives the lower villages security without endangering Valmera’s own supply.', sources: [s9.valmera] },
    { label: 'Opposition', attribution: 'Four council members', text: 'Opponents argued that the trigger level is set too low to protect Valmera in a fourth dry year.', sources: [s9.valmera] },
  ],
  uncertainties: ['How much water the plan moves in a dry year depends on a measurement rule not yet published.'],
  background: [{ heading: 'Why the spring matters', text: 'The spring is the only year-round source in the upper valley; the two lower villages rely on surface water that has failed in recent summers.', sources: [s9.canton] }],
  authors: [{ name: 'Lea Marti', publisher: 'Valmera Courier (fictional)', verified: false }],
  coverage: [art({
    id: 'pd-2026-11-09-valmera', provider: 'prism-data', section: 'Schweiz', headline: 'Valmera shares its spring water',
    lead: 'The bulletin summarises the council vote.', paragraphs: [
      ['After a session that ran past midnight, the council approved a ten-year sharing plan.', []],
      ['The bulletin notes that the cantonal decision is outstanding and that neighbouring councils still have to vote on their share of the costs.', []],
    ], sources: [s9.valmera], uncertainties: ['The cost split between the three communities is open.'],
  })],
});

const cable = art({
  id: 'ed-2026-11-09-cabletalks', section: 'International', topic: 'strait-cable', regions: ['GLOBAL'], importance: 1,
  headline: 'Cable talks run into a second week as both sides dispute repair rights',
  lead: 'Negotiators for the two coastal states have not settled who may repair the undersea cable in disputed waters.',
  whyItMatters: 'The cable carries most of the region’s internet traffic; an outage would affect hospitals and payment systems on both coasts.',
  paragraphs: [
    ['Talks over the damaged undersea cable will continue next week after a third round ended without agreement, the wire service reported.', ['cable-wire']],
    ['A draft framework published by the joint commission lists repair access as the main open point.', ['cable-draft', 'cable-wire']],
    ['Neither delegation commented on the substance of the talks.', ['cable-wire']],
  ],
  sources: [s9.cable, s9.cableDoc],
  perspectives: [
    { label: 'Northern delegation', text: 'Insists that repairs in its claimed zone need its permission.', sources: [s9.cable] },
    { label: 'Southern delegation', text: 'Argues that the cable treaty grants neutral repair crews free passage.', sources: [s9.cableDoc] },
  ],
  uncertainties: ['The extent of the damage has not been independently assessed.', 'The draft framework is only partly public.'],
  background: [{ heading: 'The 1998 cable treaty', text: 'The treaty set out joint ownership of the cable but left maritime boundaries undecided.', sources: [s9.cableDoc] }],
  corrections: [{ date: '2026-11-09', text: 'An earlier version said the talks had collapsed. They were adjourned.' }],
});

const terraces = art({
  id: 'ed-2026-11-09-terraces', section: 'Peru', topic: 'highland-farming', regions: ['PE'], importance: 0.6,
  headline: 'Terrace farmers in the highlands bring in an early harvest',
  lead: 'Unusually early rain let farmers on the old stone terraces plant weeks ahead of the usual calendar.',
  paragraphs: [
    ['Farmers in three highland districts began harvesting potatoes about three weeks early, according to a regional radio station.', ['andes-radio']],
    ['The ministry’s seasonal bulletin recorded above-average rainfall in September.', ['andes-ministry']],
  ],
  sources: [s9.andes, s9.andesMin],
  images: [demoImage('terraces', 7, 'Stone terraces on a hillside', 'Terraced fields in the highlands (demo image).')],
  uncertainties: ['Whether the early harvest means a larger harvest is not yet known.'],
});

const seeds = art({
  id: 'ed-2026-11-09-seedvault', section: 'Science', topic: 'seed-banks', regions: ['GLOBAL'], importance: 0.55,
  headline: 'Seeds stored for ten years at minus 18 degrees still sprout',
  lead: 'A long-running test at a public seed bank found most samples remain viable.',
  paragraphs: [
    ['Nine in ten samples germinated after a decade in cold storage, a peer-reviewed study reports.', ['seed-paper']],
    ['The seed bank says it will extend the test to fifty more crop varieties.', ['seed-vault']],
  ],
  sources: [s9.seed, s9.seedPaper],
  images: [{ alt: 'Seed packets on a shelf', caption: 'Seed packets in cold storage.', credit: '', license: '', licenseUrl: '', rights: 'unknown',
    rightsNote: 'Rights not cleared; not displayed.', sourceUrl: 'https://example.org/demo/seed-photo', origin: 'publisher', display: false }],
});

const grid = art({
  id: 'ed-2026-11-09-gridreserve', section: 'Switzerland', topic: 'winter-energy', regions: ['CH'], importance: 0.7,
  headline: 'Grid operator books its largest winter reserve so far',
  lead: 'The reserve is meant to cover two weeks of shortfall in a cold, windless February.',
  paragraphs: [
    ['The operator contracted reserve capacity for the coming winter, the largest volume since the reserve was introduced.', ['grid-operator']],
    ['An energy newsletter notes that the cost will be passed on to consumers through grid fees.', ['grid-report']],
  ],
  sources: [s9.gridOp, s9.grid],
});

const library = art({
  id: 'ed-2026-11-09-library', section: 'Society', topic: 'library-of-things', regions: ['CH'], importance: 0.35,
  headline: 'The library that lends drills turns one',
  lead: 'Two thousand loans in a year: a lakeside town’s experiment with sharing tools has outgrown its basement.',
  paragraphs: [
    ['The library of things recorded about two thousand loans in its first year, the weekly paper reports.', ['library-things']],
    ['Volunteers now plan to move to a larger room in the old post office.', ['library-things']],
  ],
  sources: [s9.lib],
});

const sky = art({
  id: 'ed-2026-11-09-darksky', section: 'Good News', kind: 'good_news', regions: ['CH'], importance: 0.3,
  headline: 'A valley switches off its streetlights after midnight and gains a dark-sky zone',
  lead: 'Three communities agreed to dim their lights, and astronomers are already returning.',
  paragraphs: [['The protected dark-sky zone now covers the whole ridge, the valley paper reports.', ['night-sky']],
    ['Residents can request motion-sensor lights for paths near the school.', ['night-sky']]],
  sources: [s9.night],
  images: [demoImage('night', 3, 'Stars above a dark ridge', 'An illustration of the night sky above the ridge.', 'ai_illustration')],
});

const magazine = art({
  id: 'ed-2026-11-09-magazine-water', kind: 'magazine', section: 'Magazine', topic: 'valmera-water', regions: ['CH'],
  headline: 'Who owns a spring? Three dry summers in the upper valley',
  lead: 'How a water dispute between neighbours became a lesson in sharing a resource that used to seem endless.',
  paragraphs: [
    ['For generations the spring above Valmera was simply there. The village fountains ran all year, and the question of whose water it was never came up.', ['valmera-council']],
    ['That changed in the first dry summer, when the lower villages began to order water by truck and the price of a delivery doubled within a month.', ['canton-notice']],
    ['The agreement approved this week is a compromise that both sides describe as imperfect, and both sides say they could live with.', ['valmera-council']],
    ['What remains open is the measurement rule that decides when the spring is shared, and the cost of the pipe that would carry it.', ['canton-notice']],
  ],
  sources: [s9.valmera, s9.canton],
  images: [demoImage('alpine', 11, 'A fountain in a village square', 'The village fountain of Valmera (demo image).')],
  perspectives: [{ label: 'Historian’s view', attribution: 'Local archive (fictional)', text: 'Water rights in the valley were last renegotiated in 1911.', sources: [s9.canton] }],
});

export const dailyEditions: DailyEdition[] = [
  {
    schemaVersion: 'prismunfold.daily-edition/1', date: D9, timezone: 'Europe/Zurich', title: 'PrismUnfold · Tagesausgabe', demo: true,
    mainHeadline: { articleId: cable.articleId, headline: cable.headline },
    introduction: { text: 'A Monday of slow agreements: a valley shares its water, two coastal states keep talking about a cable, and a library celebrates its first year.', provider: 'prism-data', originType: 'ai_secondary' },
    rubrics: [
      { name: 'International', articleIds: [cable.articleId] },
      { name: 'Switzerland', articleIds: [water.articleId, grid.articleId] },
      { name: 'Peru', articleIds: [terraces.articleId] },
      { name: 'Science', articleIds: [seeds.articleId] },
      { name: 'Society', articleIds: [library.articleId] },
    ],
    articles: [cable, water, grid, terraces, seeds, library], briefs: [], magazine: [magazine], goodNews: [sky],
    randomFacts: [{ label: 'Random of the day', text: 'Some seed varieties stay viable for more than a century when kept dry and cold.', reviewRequired: false, sources: [s9.seedPaper] }],
    assessments: [
      { label: 'Important', text: 'The cable talks: an outage would hit essential services on both coasts.', reviewRequired: false, sources: [s9.cable] },
      { label: 'Watch', text: 'The cantonal decision on the Valmera plan.', reviewRequired: false, sources: [s9.canton] },
    ],
    contributors: [{ provider: 'codex', originType: 'ai_secondary' }, { provider: 'prism-data', originType: 'ai_secondary' }],
    transparency: { disclosures: ['Fictional demo edition. Every story, place, source and image is invented.'], warnings: [], editorialNote: null,
      completeness: 'complete', independentVerification: 'AI contributions and source-access checks are not independent factual verification.' },
    revision: { publishedAt: '2026-11-09T07:00:00+01:00', publicationMode: 'automatic', bulletinGeneratedAt: '2026-11-09T06:01:00+01:00', bulletinBasis: 'upstream_published' },
  },
  {
    schemaVersion: 'prismunfold.daily-edition/1', date: '2026-11-08', timezone: 'Europe/Zurich', title: 'PrismUnfold · Tagesausgabe', demo: true,
    mainHeadline: { articleId: 'ed-2026-11-08-cabletalks', headline: 'Cable talks resume with a new mediator' },
    introduction: null, rubrics: [],
    articles: [art({
      id: 'ed-2026-11-08-cabletalks', section: 'International', topic: 'strait-cable', regions: ['GLOBAL'], importance: 1,
      headline: 'Cable talks resume with a new mediator', lead: 'A retired judge from a third country will chair the talks.',
      paragraphs: [['The two delegations agreed on a mediator on Saturday, the wire service reported.', ['cable-wire']],
        ['The commission published a partial draft of the framework.', ['cable-draft']]],
      sources: [s9.cable, s9.cableDoc],
    })],
    briefs: [], magazine: [], goodNews: [], randomFacts: [], assessments: [],
    contributors: [{ provider: 'codex', originType: 'ai_secondary' }],
    transparency: { disclosures: ['Fictional demo edition.'], warnings: ['Magazin zurückgestellt oder nicht vorhanden'], completeness: 'partial' },
    revision: { publishedAt: '2026-11-08T07:00:00+01:00', publicationMode: 'automatic' },
  },
];
