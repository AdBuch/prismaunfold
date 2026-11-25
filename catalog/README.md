# Source catalog

`sources.json` lists every source the platform knows about. It is versioned in Git, so each change to a source is reviewed.

Each entry:

| Field | Values | Meaning |
| --- | --- | --- |
| `id` | unique slug | Stable identifier |
| `name` | text | Display name, shown as attribution |
| `feed_url` | http(s) URL | RSS or Atom feed |
| `languages` | e.g. `["de"]` | Language of the articles; the first entry is used in the MVP |
| `rights` | `excerpt_only`, `full_text`, `link_only` | `full_text` keeps the body; `link_only` keeps only the title and link |
| `status` | `pending_review`, `active`, `blocked` | Only `active` sources are fetched |
| `ai_policy` | `exclude`, `label` | `exclude` drops articles the publisher marks as AI-generated |
| `regions`, `topics` | lists | Tags for the feed mix |

New sources start as `pending_review`. A person sets them to `active` after checking rights and quality.

## The candidates in `sources.json`

The file ships with a few well-known feeds as **candidates**. All are `pending_review`,
so a fresh checkout fetches nothing. They are set to `link_only`: only the headline and
the link are kept and shown, with the publisher named.

Before you set one to `active`:

1. Read the publisher's terms for its feed. Most allow personal, non-commercial use of
   headlines and links; a public news site is a different use and may need permission.
2. Decide whether `link_only` is enough or the terms allow `excerpt_only`.
3. Check the feed still exists: run the "Live feeds" workflow, or
   `PYTHONPATH=src python3 -m prismunfold run` and read the errors it prints.

Nobody has done this rights review yet.

What is confirmed: on 14 November 2026 the "Live feeds" workflow fetched and parsed
all six candidates. A seventh, El País, was removed because its `robots.txt`
disallows the feed address, and the pipeline does not fetch what robots.txt disallows.
