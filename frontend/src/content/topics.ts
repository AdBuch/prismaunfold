import type { Topic } from '../models.ts';
import { img } from './helpers.ts';

export const topics: Topic[] = [
  {
    slug: 'valmera-reservoir',
    title: 'The Valmera reservoir',
    summary:
      'How a dry summer in a fictional Alpine municipality became a shared-water plan, a consultation and a municipal vote.',
    section: 'switzerland',
    image: img('alpine', 11, 'An alpine lake at dusk', 'Valmera, as imagined. Illustration.'),
    demo: true,
    events: [
      {
        id: 'vr-1', date: '2026-10-05', kind: 'milestone',
        title: 'Third dry summer in six years ends',
        summary: 'Village cisterns drop below a quarter of capacity in September, according to the municipal water office.',
      },
      {
        id: 'vr-2', date: '2026-10-19', kind: 'report',
        title: 'Hydrology assessment published',
        summary: 'A consultant\'s assessment finds a single shared basin would stabilise supply in all but the driest years.',
      },
      {
        id: 'vr-3', date: '2026-10-26', kind: 'milestone',
        title: 'Council opens a three-week consultation',
        summary: 'Households and farmers are invited to respond in writing or at village meetings.',
      },
      {
        id: 'vr-4', date: '2026-11-07', kind: 'report',
        title: 'Consultation closes with 1,240 responses',
        summary: 'Responses split roughly between village households and upper-meadow farmers.',
        storySlug: 'valmera-reservoir-consultation', editionDate: '2026-11-07',
      },
      {
        id: 'vr-5', date: '2026-11-08', kind: 'update',
        title: 'Vote moved to Sunday; water-board charter published',
        summary: 'The council confirms a Sunday ballot and publishes the draft charter of a three-member water board.',
        editionDate: '2026-11-08',
      },
      {
        id: 'vr-6', date: '2026-11-09', kind: 'milestone',
        title: 'Voters approve the shared reservoir',
        summary: 'A clear majority backs the plan. A cantonal planning permit is still required.',
        storySlug: 'valmera-reservoir-vote', editionDate: '2026-11-09',
      },
    ],
  },
  {
    slug: 'undersea-cable-accord',
    title: 'The undersea-cable accord',
    summary:
      'From unexplained faults to a signed framework: how fictional states moved towards pooled cable repair.',
    section: 'international',
    image: img('sea', 21, 'A ship over a dark sea', 'The cable route, as imagined. Illustration.'),
    demo: true,
    events: [
      {
        id: 'uc-1', date: '2026-10-21', kind: 'milestone',
        title: 'Two regional networks report slowdowns',
        summary: 'Operators say traffic was rerouted after faults on two cable routes. The cause is unstated.',
      },
      {
        id: 'uc-2', date: '2026-10-30', kind: 'report',
        title: 'Repair delayed by access dispute',
        summary: 'A repair ship waits several days for permission to enter disputed waters, according to a fictional trade newsletter.',
      },
      {
        id: 'uc-3', date: '2026-11-07', kind: 'milestone',
        title: 'Talks open in a harbour city',
        summary: 'Delegations meet for the first time. No draft text is published.',
        storySlug: 'cable-accord-talks-open', editionDate: '2026-11-07',
      },
      {
        id: 'uc-4', date: '2026-11-08', kind: 'update',
        title: 'Signing slips over inspection rights',
        summary: 'Negotiators disagree on inspections of landing stations; officials describe the gap as narrow.',
        storySlug: 'cable-accord-delay', editionDate: '2026-11-08',
      },
      {
        id: 'uc-5', date: '2026-11-08', kind: 'correction',
        title: 'Correction: eleven states, not twelve',
        summary: 'An earlier version of the report stated twelve negotiating states. The number was corrected to eleven.',
        storySlug: 'cable-accord-delay', editionDate: '2026-11-08',
      },
      {
        id: 'uc-6', date: '2026-11-09', kind: 'milestone',
        title: 'Eleven states sign the framework',
        summary: 'The text creates a pooled repair fleet and common response times. Ownership questions are deferred to a working group.',
        storySlug: 'cable-accord-framework', editionDate: '2026-11-09',
      },
    ],
  },
];
