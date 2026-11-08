import type { Edition, EditionStoryPlacement, PlacementSlot, SectionId } from '../models.ts';
import { stories } from './stories.ts';

function bySlug(slug: string) {
  const s = stories.find((x) => x.slug === slug);
  if (!s) throw new Error(`Unknown story ${slug}`);
  return s;
}

function place(
  slug: string,
  section: SectionId | 'front',
  slot: PlacementSlot,
  order: number,
  overrides: { headline?: string; teaser?: string } = {},
): EditionStoryPlacement {
  const s = bySlug(slug);
  return {
    storySlug: slug,
    section,
    slot,
    order,
    // Snapshot copies the wording at publication time so archives never change.
    snapshot: {
      headline: overrides.headline ?? s.headline,
      teaser: overrides.teaser ?? s.standfirst,
      image: s.image,
    },
  };
}

export const editions: Edition[] = [
  {
    id: 'ed-2026-11-07',
    date: '2026-11-07',
    number: 311,
    demo: true,
    editorsNote: 'A quiet Saturday morning: a new diplomatic track, a valley deciding about water, and a library that lends drills.',
    placements: [
      place('cable-accord-talks-open', 'international', 'lead', 1),
      place('valmera-reservoir-consultation', 'switzerland', 'secondary', 2),
      place('library-tool-lending', 'society', 'secondary', 3),
      place('timetable-sensor-audit', 'switzerland', 'standard', 4),
      place('quellca-quechua-science', 'peru', 'standard', 5),
      place('city-trees-cooling-study', 'science', 'standard', 6),
      place('terrace-restoration-highlands', 'underreported', 'standard', 7),
    ],
    briefs: [
      { id: 'b-0701', section: 'switzerland', text: 'A fictional cantonal office reminds residents that the winter ski-bus timetable starts on 15 December.' },
      { id: 'b-0702', section: 'international', text: 'Delegates to the cable talks have scheduled three days of closed sessions.', storySlug: 'cable-accord-talks-open' },
      { id: 'b-0703', section: 'peru', text: 'A fictional highland radio station will broadcast school lessons in Quechua on weekday afternoons.', storySlug: 'quellca-quechua-science' },
      { id: 'b-0704', section: 'science', text: 'The street-cooling preprint is open for comments; its authors list their data and sensor models.', storySlug: 'city-trees-cooling-study' },
      { id: 'b-0705', section: 'discoveries', text: 'An amateur observing club in the demo world reports its first comet candidate of the season.' },
    ],
    magazineSlug: 'the-water-that-remembers',
    magazineTeaser: 'Before the vote: how one valley\'s water rules grew, gate by gate.',
  },
  {
    id: 'ed-2026-11-08',
    date: '2026-11-08',
    number: 312,
    demo: true,
    editorsNote: 'Talks overran, a valley prepares to vote, and amateurs spot something faint in the southern sky.',
    placements: [
      place('cable-accord-delay', 'international', 'lead', 1),
      place('valmera-reservoir-consultation', 'switzerland', 'secondary', 2, {
        headline: 'Valmera readies for Sunday\'s vote on shared water',
        teaser: 'After 1,240 responses, the council publishes the water-board charter and confirms the ballot date.',
      }),
      place('faint-comet-amateurs', 'discoveries', 'secondary', 3),
      place('san-aurelio-night-market-link', 'peru', 'standard', 4),
      place('timetable-sensor-audit', 'switzerland', 'standard', 5, {
        teaser: 'Commuter groups ask for the passenger-count data behind the proposed change.',
      }),
      place('city-trees-cooling-study', 'science', 'standard', 6, {
        headline: 'Why one unbroken row of trees beats many scattered ones',
      }),
    ],
    briefs: [
      { id: 'b-0801', section: 'switzerland', text: 'The Valmera council confirms polling stations will open from 10:00 to 17:00 on Sunday.', storySlug: 'valmera-reservoir-consultation' },
      { id: 'b-0802', section: 'international', text: 'Two delegations ask for military sites to be exempted from landing-station inspections.', storySlug: 'cable-accord-delay' },
      { id: 'b-0803', section: 'society', text: 'A fictional city\'s tool library reports a waiting list for its tile cutter.', storySlug: 'library-tool-lending' },
      { id: 'b-0804', section: 'peru', text: 'San Aurelio will review its late bus link after eight weeks.', storySlug: 'san-aurelio-night-market-link' },
      { id: 'b-0805', section: 'science', text: 'The authors of the canopy study have clarified that its sensors measured pavement, not air, temperature.', storySlug: 'city-trees-cooling-study' },
    ],
    magazineSlug: 'terraces-after-dark',
    magazineTeaser: 'A season of repair in a high valley where the walls are older than the roads.',
  },
  {
    id: 'ed-2026-11-09',
    date: '2026-11-09',
    number: 313,
    demo: true,
    editorsNote: 'Two decisions on Sunday: a valley votes for shared water, and eleven states sign a framework for the sea floor.',
    placements: [
      place('valmera-reservoir-vote', 'switzerland', 'lead', 1),
      place('cable-accord-framework', 'international', 'secondary', 2),
      place('san-aurelio-night-market-link', 'peru', 'secondary', 3, {
        teaser: 'Traders counted missed customers; the district now runs weekend buses until 2 a.m.',
      }),
      place('quellca-quechua-science', 'peru', 'standard', 4),
      place('library-tool-lending', 'society', 'standard', 5),
      place('faint-comet-amateurs', 'discoveries', 'standard', 6),
      place('terrace-restoration-highlands', 'underreported', 'standard', 7),
    ],
    briefs: [
      { id: 'b-0901', section: 'switzerland', text: 'The Valmera planning permit will be filed with the cantonal authority this week.', storySlug: 'valmera-reservoir-vote' },
      { id: 'b-0902', section: 'international', text: 'A working group on landing-station inspections is due to report in spring.', storySlug: 'cable-accord-framework' },
      { id: 'b-0903', section: 'society', text: 'Branch libraries will publish tool-lending figures after the first quarter.', storySlug: 'library-tool-lending' },
      { id: 'b-0904', section: 'discoveries', text: 'Professional observers say they will confirm the amateur comet position this week.', storySlug: 'faint-comet-amateurs' },
      { id: 'b-0905', section: 'underreported', text: 'Highland organisers invite agronomists to compare restored and unrestored terraces.', storySlug: 'terrace-restoration-highlands' },
    ],
    magazineSlug: 'the-water-that-remembers',
    magazineTeaser: 'Now the valley has voted: the long history behind a shared reservoir.',
  },
];
