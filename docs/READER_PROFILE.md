# Reader profile and edition composition

Contract between the reader experience and the editorial pipeline for personal
editions. Implemented in `frontend/src/lib/profile.ts` and `frontend/src/lib/composer.ts`.

## Reader profile (`prismunfold.profile.v1`)

Stored in the browser's `localStorage` only. Weights are **relevance signals**, not
preferences about what is true; they decide selection and order, never content.

```jsonc
{
  "version": 1,
  "language": "de-CH",                 // BCP 47
  "timezone": "Europe/Zurich",         // IANA
  "homeRegion": "CH",                  // ISO 3166 or ""
  "geographicInterests": { "CH": 1.0, "PE": 0.8, "GLOBAL": 0.6 },   // 0..1
  "topicInterests": { "politics": 0.5, "technology": 1.0, "science": 1.0 },  // 0..1, keys below
  "edition": { "readingTimeMinutes": 15, "preferredDeliveryTime": "07:00", "discoveryRatio": 0.2, "depth": "standard" },
  "follows": { "topics": ["valmera-water"], "authors": ["lea-marti", "codex"], "publishers": [] },
  "recurringSections": ["magazine", "good_news", "editorial_outlook", "random"],
  "behaviouralPersonalisation": false,  // off by default
  "readingHistory": false,              // off by default; turning it off deletes the history
  "onboarding": "new | done | skipped",
  "updatedAt": "2026-11-26T07:12:00Z"
}
```

Interest keys: `politics`, `economy`, `technology`, `science`, `society`,
`environment`, `crises`, `culture`, `travel`. Region keys: ISO 3166 codes, `EU`,
`GLOBAL`. Limits: reading time 3–90 minutes, discovery ratio 0–0.5, at most 200
follows per kind. Unreadable or hostile values fall back to defaults. The 0.2
preferences (`prismunfold.preferences.v1`: languages, regions, sections) are migrated
once.

Separate keys: `prismunfold.saved.v1` (saved articles: id, title, path, time) and
`prismunfold.history.v1` (read article ids, only with `readingHistory`).

## Composition

Input: candidates (canonical articles and feed stories of one edition) and a profile.

```ts
interface Candidate {
  id: string; headline: string; section: string; kind: 'news' | 'magazine' | 'good_news';
  topics: string[];       // interest keys
  topicSlug?: string;     // dossier
  regions: string[];
  importance: number;     // 0..1
  minutes: number;        // reading time
  cluster: string;        // event cluster
  authors: string[];      // follow keys: author slugs and the contributing provider
  publishers: string[];
}
interface Composition {
  items: { id: string; reason: 'global' | 'interest' | 'follow' | 'discovery' | 'recurring'; score: number }[];
  minutes: number; budgetMinutes: number;
  gaps: { kind: 'topic' | 'region'; key: string; weight: number; available: number }[];
  omitted: number;
}
```

Rules, in order:

1. **Global:** up to 3 news items with importance ≥ 0.7 are always included, whatever
   the interests and the reading time.
2. **Recurring:** the best magazine and Good News item when the reader asked for them.
3. **Interests and follows:** by score
   `0.45·importance + 0.35·topic weight + 0.25·region weight + 0.5·followed − 0.5·read`
   (the last term only with behavioural personalisation), within the reading time
   minus the discovery share; at least one item.
4. **Discovery:** the most important items outside the interests fill the discovery
   share of the remaining time.
5. Remaining time goes to further interests.

Limits throughout: one item per event cluster, at most 3 per section and 2 per topic.
Ties break on the id in code-point order, so the same input gives the same output on
every device. Interests with weight ≥ 0.5 and no candidate become **coverage gaps**;
nothing is generated to fill them.

## Coverage-gap signal (planned interface)

The gaps are shown to the reader and kept on the device. The research pipeline will
receive **aggregated, anonymous demand**, never individual profiles:

```jsonc
// POST /api/v1/signals/coverage-gaps (planned; batched, no identifiers, no history)
{ "date": "2026-11-26", "language": "de", "gaps": [{ "kind": "topic", "key": "culture" }, { "kind": "region", "key": "IT" }] }
```

The server is expected to count and threshold these (k-anonymity) before any worker
sees them. Until accounts exist, nothing is transmitted.

## Edition profiles and languages (planned)

One canonical edition per date, profile and language: `daily/{date}.json` is the
public profile in the edition's language. Additional files
`daily/{date}.{profile}.{language}.json` (for example a shorter `brief` profile or an
English edition) will set `editionProfile` and `language` and reference the same
article ids where the facts are shared.
