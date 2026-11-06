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
