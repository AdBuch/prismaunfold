# Editorial workflow

How contributions become the daily newspaper, and what each label means.
Product target: [EDITORIAL_SPEC.md](EDITORIAL_SPEC.md). Operations: [OPERATIONS.md](OPERATIONS.md).

Status words used below: **implemented** (in code and tested in CI),
**experimental** (in code, opt-in, not proven in production), **planned**.

## Contributors and contributions (implemented)

RSS publishers, the prism-data bulletin (ChatGPT), Codex, Claude, Mistral and other
workers are **contributors to one newspaper**, not separate publications. Each thing a
contributor hands in is a *contribution* (`src/prismunfold/contributions.py`), stored
as received in the `contributions` table:

| Field | Meaning |
| --- | --- |
| `provider` | `rss`, `prism-data`, `chatgpt`, `codex`, `claude`, `mistral`, `goose`, `other` |
| `source_key` | Where it came from, e.g. `prism-data/morgenbriefing/2026-11-25`, `codex/morgenbriefing/2026-11-25` |
| `content_hash` | SHA-256 of the received document; the same content is stored once |
| `generated_at`, `received_at` | When the contributor made it, when we got it |
| `origin_type` | `original_publisher` (RSS) or `ai_secondary` (every AI contribution) |
| `upstream_status` | The contributor's own publication status (prism-data) |
| `state`, `state_history` | Editorial state, with who changed it when and why |
| `limitations` | e.g. `ai_curated_secondary`, `item_level_citations`, `no_original_sources` |
| `raw` | The original document, never modified |

What readers see is composed from contributions; a contribution never becomes a
published article by itself.

### Provenance rules

- Original publisher, original document, AI secondary reporting, editorial synthesis,
  source accessibility, factual verification, editorial approval and publication state
  are separate fields. None implies another.
- Several AI contributions citing the same original article are **one** confirmation
  (`contributions.independent_publishers` counts canonical original hosts, never contributors).
- The prism-data bulletin is an AI-curated secondary source. Its citations are
  item-level and are never turned into paragraph-level claims (`citation_level: item`).
- Nothing is invented: a missing URL, date, credit or licence stays missing and is
  shown as a limitation.

## Editorial states (implemented)

```
received → normalised → validated ─────────────→ published
                      ↘ review_required → approved → published
                                         ↘ rejected
any revision replaced by a newer one → superseded
```

| State | Article (editorial edition) | Bulletin (prism-data) |
| --- | --- | --- |
| `validated` | Every paragraph has an openly reachable source | Upstream `published`/`final` |
| `review_required` | A paragraph rests only on restricted, missing or temporarily unreachable sources | Upstream `draft`, `unverified`, `test_import_unverified` |
| `rejected` | A paragraph rests only on unsafe or catalogue-excluded sources (cannot be approved) | Operator rejected the revision |
| `withdrawn` | An operator rejected a published article; `approve` reverses it | – |
| `approved` / `published` | Published automatically (validated) or approved by an operator | Operator approved this exact content hash |
| `superseded` | Replaced by `--replace` | Replaced by a newer revision, or arrived older than the stored one |

Malformed items (unknown rubric, wrong length, unknown source ids) are listed under
`invalid` with the reason; they never fail the edition.

## Publication policies (implemented)

Defined in `editorial.apply_policy`, configured in `config/config.json`
(`editorial.auto_publish`: `min_articles` 5, `min_sections` 3).

| Case | Automatic (07:00 timer) | Manual (operator) |
| --- | --- | --- |
| Validated article | Published | Published |
| Review-required article | Withheld; `approve` later | Published only with `--approve-review-required`, labelled "Prüfbedürftig" |
| Restricted (403/paywall) source next to a reachable one | Published; source labelled "Link nicht verifiziert (restricted)" | Same |
| Rejected article (unsafe/excluded source) | Withheld | Withheld; cannot be approved |
| Magazine fails or needs review | Edition still published, marked `partial`; magazine withheld | Same, or approve it |
| Missing Random / Lagebild | Edition `partial` | Same |
| Too few publishable articles | Nothing published; previous issue stays | Refused unless `--allow-partial` |
| Same raw edition published again | Re-export only (`already_published`) | Same |
| Different content for a published date | Refused | Only with `--replace`; old version `superseded` |

Unsupported claims are never published silently: an article that needs review is
either withheld or carries a visible label.

## Source accessibility (implemented)

`src/prismunfold/linkcheck.py` answers one question: can the cited document be
retrieved now? It is **not** factual verification. A 200 response does not show the
page supports the claim; a 403 does not show the source is invented.

| Status | Cause | Retried |
| --- | --- | --- |
| `reachable` | 2xx | – |
| `restricted` | 401, 402, 403, 407, 451 (HEAD refusals are retried with GET) | no |
| `missing` | 404, 410 | no |
| `rate_limited` | 429 | yes |
| `unavailable` | 5xx, connection or TLS error | yes |
| `timeout` | No answer in time | yes |
| `dns_failure` | Name not resolvable now | yes |
| `unsafe` | Non-http(s), credentials in URL, literal IP, non-public address, unsafe redirect, too many redirects | no |
| `unknown` | Not checked | – |

Retries: 3 attempts, exponential backoff 1 s, 2 s (max 8 s); a hard limit of 30 s per URL over all attempts and redirects. Results are cached per
cycle (definitive 6 h, transient 15 min; file cache via `SOURCE_CHECK_CACHE`).
Publisher refusals are respected: no cookies, no credentials, no paywall or anti-bot
circumvention.

**SSRF protection.** Every host (including each redirect target, at most 5) must
resolve only to public addresses. The connection is pinned to the vetted address,
so the HTTP client cannot resolve the name again to an internal address (DNS
rebinding). Remaining limitations: the check connects directly (no proxy support);
TLS is verified against the original host name; only the first resolved address is tried; NAT64 prefixes count as public; a public address that forwards to
internal services is outside this check, so run the pipeline where internal services
are not reachable anyway (own container network).

## Factual verification (partly implemented)

`src/prismunfold/verification.py` keeps citation, reachability, support and
corroboration apart for agent and feed stories. A checker that reads the cited page
and compares it with the claim is **planned**; until then AI contributions are never
labelled verified. The daily API states `factual: not_independently_verified`.

## Deduplication and thematic integration (implemented)

`src/prismunfold/dedupe.py`, deterministic, no model call. Two contributions are the
same event only if, within ±2 days, they share an identical normalised headline, or a
canonical original URL plus headline overlap, or strong headline overlap (optionally
supported by shared named entities). Sharing a country, politician or organisation
alone never matches. Ambiguous matches stay separate.

On a match the stronger, existing editorial article keeps its headline, text and
sources; the other contribution is attached as `coverage` with its own attribution,
sources, perspectives and uncertainties. Paragraphs already shown are not repeated.
Stable `topic` slugs connect daily articles with topic timelines.

## Images (implemented)

`src/prismunfold/images.py`. Fields: `url`, `source_url`, `alt`, `caption`, `credit`,
`license`, `license_url`, `rights`, `rights_note`, `display_allowed`, `origin`
(`publisher`, `wikimedia_commons`, `official`, `licensed_photo`, `chart`,
`ai_illustration`, `unknown`), plus our decision `display` / `display_reason`.

An image is displayed only over HTTPS, with a credit, and with an explicit grant
(`display_allowed: true` or rights `approved`/`licensed`/`public_domain`) or an
open licence (CC BY, CC BY-SA, CC0, public domain). AI illustrations need an explicit
grant and always carry the label "KI-generierte Illustration – kein Foto eines
realen Ereignisses". Metadata of non-displayable images is kept; the API omits their
`url`. An article without an image is publishable. Image discovery and generation are
**planned** (not a pipeline dependency).

## Editorial workers (implemented / experimental)

Any worker submits the same edition JSON (`config/editorial/edition.schema.json`,
`provider` one of `codex`, `claude`, `mistral`, `goose`, `chatgpt`, `other`). A
failing worker affects only its own run; the importer and the feed pipeline go on.
Today only Codex runs as an editorial worker; Claude/Mistral are configured as
topic collectors (`collectors/`), not yet as edition writers (**planned**).

Stages: research → selection → writing → magazine → evidence check → review →
composition → publication. The default Codex run combines research and writing in
one structured call; `EDITORIAL_STAGES=split` (**experimental**) separates them and
lets a saved dossier be reused. Evidence checking, review, composition and
publication never call a model.

AI resource controls: one generation per day unless `EDITORIAL_FORCE_GENERATE=1`;
`EDITORIAL_TIMEOUT_SECONDS` (default 2400); recovery, re-validation and re-export
without a model call; single articles approved later instead of regenerating; token
use recorded in `run.json` when the CLI reports it.

## How states reach the API and the reader

| Where | What |
| --- | --- |
| `api/v1/editorial/morgenbriefing.json` | Published items only. `state`, `review_required`, `approval`, `provenance`, `link_status` per source |
| `api/v1/daily/{date}.json` | Same items in the unified contract ([API.md](API.md)); `transparency.completeness`, warnings, disclosures |
| Reader | "Prüfbedürftig" note on approved review-required articles; "Link nicht verifiziert (restricted)" per source; "KI-kuratierte Sekundärquelle" on bulletin items; "Magazin noch in redaktioneller Prüfung" when withheld; editorial notes collapsed under "Redaktionelle Hinweise" |
| Never public | Withheld items, `invalid` list, raw documents, review reasons with URLs (logs and `status` only) |
