"""Static output: one mobile HTML page per language plus JSON editions. No JavaScript, no trackers."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from .models import Article, Event, Summary, to_jsonable
from .normalize import title_key

LANGUAGE_NAMES = {"de": "Deutsch", "en": "English", "es": "Español"}

CSS = """
:root { --bg:#f6f5f2; --card:#fff; --ink:#1b1b1b; --muted:#6b6b6b; --accent:#b4382b; --line:#e4e1da; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --bg:#141414; --card:#1e1e1e; --ink:#eee; --muted:#9a9a9a; --accent:#ff7a66; --line:#2c2c2c; }
}
:root[data-theme="dark"] { --bg:#141414; --card:#1e1e1e; --ink:#eee; --muted:#9a9a9a; --accent:#ff7a66; --line:#2c2c2c; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font-family: -apple-system, system-ui, "Segoe UI", Roboto, sans-serif; line-height:1.5; }
header { position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--line); padding:14px 16px; z-index:1; }
header h1 { margin:0; font-size:1.2rem; }
header p { margin:2px 0 0; color:var(--muted); font-size:.85rem; }
main { max-width:680px; margin:0 auto; padding:12px 16px 32px; }
.edition { color:var(--muted); font-size:.85rem; margin:4px 0 14px; }
article.card { background:var(--card); border-radius:14px; overflow:hidden; margin:0 0 16px; box-shadow:0 1px 3px rgba(0,0,0,.06); }
article.card img { width:100%; aspect-ratio:16/9; object-fit:cover; display:block; background:var(--line); }
.body { padding:14px 16px 16px; }
.meta { font-size:.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
.badge { display:inline-block; margin-left:6px; padding:0 6px; border-radius:6px; border:1px solid var(--line); text-transform:none; letter-spacing:0; }
.badge.new { color:var(--accent); border-color:var(--accent); }
h2 { font-size:1.1rem; margin:6px 0 8px; line-height:1.3; }
ul { margin:0 0 10px; padding-left:18px; }
li { font-size:.95rem; margin-bottom:6px; }
a { color:var(--accent); }
.cite { font-size:.75rem; text-decoration:none; }
.src, .foot, .credit { font-size:.75rem; color:var(--muted); margin:6px 0 0; }
.src a, .credit a { color:var(--muted); }
.empty { color:var(--muted); text-align:center; padding:40px 0; }
"""


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render_event(
    event: Event, summary: Summary, articles: list[Article], names: dict[str, str], tz_name: str
) -> str:
    by_id = {a.id: a for a in articles}
    numbering: dict[str, int] = {}
    for sentence in summary.sentences:
        for article_id in sentence.article_ids:
            numbering.setdefault(article_id, len(numbering) + 1)

    image = next((a for a in articles if a.image_url and a.image_source_url), None)
    badges = []
    if event.single_source:
        badges.append('<span class="badge">nur eine Quelle</span>')
    if event.new:
        badges.append('<span class="badge new">neu</span>')

    items = []
    for sentence in summary.sentences:
        if title_key(sentence.text) == title_key(event.title):
            continue  # already shown as the headline
        cites = " ".join(
            f'<a class="cite" href="{_e(by_id[i].url)}" rel="noopener">[{numbering[i]}]</a>'
            for i in sentence.article_ids
        )
        items.append(f"<li>{_e(sentence.text)} {cites}</li>")

    sources = "; ".join(
        f'<a href="{_e(by_id[i].url)}" rel="noopener">[{n}] {_e(names.get(by_id[i].source_id, by_id[i].source_id))}</a>'
        for i, n in numbering.items()
    )

    parts = ['<article class="card">']
    if image:
        parts.append(
            f'<img src="{_e(image.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer">'
        )
    parts.append('<div class="body">')
    parts.append(
        f'<div class="meta">{len(set(event.source_ids))} Quelle(n) · '
        f"{_e(event.last_published.strftime('%d.%m.%Y %H:%M UTC'))}{''.join(badges)}</div>"
    )
    lead = by_id[event.article_ids[0]]
    parts.append(f'<h2><a href="{_e(lead.url)}" rel="noopener">{_e(event.title)}</a></h2>')
    parts.append(f"<ul>{''.join(items)}</ul>")
    parts.append(f'<p class="src">Quellen: {sources}</p>')
    if image:
        credit = image.image_credit or "Quelle"
        parts.append(
            f'<p class="credit">Foto: <a href="{_e(image.image_source_url)}" rel="noopener">{_e(credit)}</a></p>'
        )
    foot = "Automatisch erstellte Zusammenfassung"
    if summary.translations_pending:
        pending = ", ".join(LANGUAGE_NAMES.get(l, l) for l in summary.translations_pending)
        foot += f". Übersetzung ausstehend: {pending}"
    parts.append(f'<p class="foot">{_e(foot)}</p>')
    parts.append("</div></article>")
    return "\n".join(parts)


def _page(lang: str, title: str, subtitle: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="{_e(lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<style>{CSS}</style>
</head>
<body>
<header><h1>PrismUnfold</h1><p>{_e(subtitle)}</p></header>
<main>
{body}
</main>
</body>
</html>
"""


def render_site(
    site_dir: Path,
    pages: dict[str, list[tuple[Event, Summary, list[Article]]]],
    label: str,
    start: datetime,
    end: datetime,
    generated_at: datetime,
    tz_name: str,
    names: dict[str, str],
) -> list[str]:
    """Write per-language pages, JSON editions and an index. Return the written paths."""
    site_dir = Path(site_dir)
    written: list[str] = []
    slug = start.strftime("%Y%m%dT%H%MZ")
    for lang, items in pages.items():
        cards = "\n".join(
            render_event(e, s, arts, names, tz_name) for e, s, arts in items
        )
        body = f'<p class="edition">Ausgabe {_e(label)}</p>' + (
            cards or '<p class="empty">Keine Ereignisse in dieser Ausgabe.</p>'
        )
        page_dir = site_dir / lang
        page_dir.mkdir(parents=True, exist_ok=True)
        page_path = page_dir / "index.html"
        page_path.write_text(
            _page(lang, f"PrismUnfold · {LANGUAGE_NAMES.get(lang, lang)}", f"Ausgabe {label}", body),
            encoding="utf-8",
        )
        written.append(str(page_path))

        payload = {
            "language": lang,
            "edition": label,
            "timezone": tz_name,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "generated_at": generated_at.isoformat(),
            "events": [
                {"event": to_jsonable(e), "summary": to_jsonable(s), "articles": to_jsonable(arts)}
                for e, s, arts in items
            ],
        }
        data_dir = site_dir / "data" / lang
        data_dir.mkdir(parents=True, exist_ok=True)
        for name in (f"{slug}.json", "latest.json"):
            path = data_dir / name
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            written.append(str(path))

    links = "".join(
        f'<li><a href="{_e(lang)}/">{_e(LANGUAGE_NAMES.get(lang, lang))}</a></li>' for lang in pages
    )
    index_body = (
        f'<p class="edition">Ausgabe {_e(label)}</p><ul>{links}</ul>'
        if pages
        else '<p class="empty">Noch keine Ausgabe.</p>'
    )
    index_path = site_dir / "index.html"
    index_path.write_text(_page("de", "PrismUnfold", "Sprache wählen", index_body), encoding="utf-8")
    written.append(str(index_path))
    return written
