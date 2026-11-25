# GitHub-Bulletins (prism-data) in PrismUnfold

Quelle: Repository `AdBuch/prism-data`, Branch `main`, Pfad
`data/morgenbriefing/YYYY-MM-DD.json`, Zeitzone `Europe/Zurich`, verfügbar ab 07:00.
Code: `src/prismunfold/bulletin.py`. Betrieb und Secrets: [OPERATIONS.md](OPERATIONS.md).

Das Bulletin ist eine **KI-kuratierte Sekundärquelle** (ChatGPT). Es ergänzt RSS,
Agenturen und die übrigen Redaktions-Worker; es ersetzt sie nicht und zählt nie als
unabhängige Bestätigung einer Aussage. Der Import braucht keinen KI-Aufruf und
funktioniert unabhängig von allen lokalen Workern.

## Einschalten

1. Fein abgestuftes GitHub-Token: nur Repository `AdBuch/prism-data`, Berechtigung
   **Contents: Read-only**, Ablauf höchstens 90 Tage. Ablage und Rotation:
   OPERATIONS.md, «Configuration and secrets».
2. In `.env`:

   ```dotenv
   COMPOSE_FILE=docker-compose.yml:deploy/compose.prism-data.yml
   PRISM_DATA_SECRET_PATH=/absoluter/pfad/prism-data.token
   ```

3. `docker compose up -d --build pipeline web`. Nur die Pipeline erhält das Secret
   unter `/run/secrets/prism_data_token`.

## Schema

Akzeptiert werden `schema_version` `1.0` und `1.1` (geprüft am realen Export vom
25.11.2026). Pflicht: `date` (muss zum Dateinamen passen), `timezone`
(`Europe/Zurich`), `generated_at` mit Zeitzone, `publication_status`, mindestens ein
Artikel. Rubriken: `sections[{title, items[]}]`; Artikel: `id` (eindeutig), `title`,
`body`, optional `lead`, `sources[{url, title, publisher, published_at, source_type,
access}]`, `source_urls[]`, `assessments[]`, `perspectives[]`, `uncertainties[]`,
`images[]`. Zusätzlich `deep_dive` (Magazin), `good_news`, `random_fact`,
`outlook[]` (Lagebild/Ausblick), `lead`, `editorial_note`, `editorial_cutoff`.
`null` in optionalen Feldern ist erlaubt und bleibt leer – fehlende URLs, Daten oder
Bildrechte werden nie ergänzt. Grenzen: 2 MiB pro Datei, 200 Artikel, Textlängen pro Feld.

Alles wird erhalten: Datum, Erzeugungszeit, Status, Vorspann, Rubriken (Reihenfolge),
Artikel, Originalquellen mit Verlag, Titel und Datum, Einschätzungen, Perspektiven,
Unsicherheiten, Bildmetadaten und -rechte, Magazin, Good News, Random, Ausblick,
redaktionelle Hinweise, Schema-Version, Redaktionsschluss. Das Originaldokument
liegt unverändert in der Tabelle `contributions`.

## Publikationsstatus

| `publication_status` | Wirkung |
| --- | --- |
| `published`, `final` | In die Tagesausgabe übernommen, gekennzeichnet als KI-kuratierte Sekundärquelle |
| `draft`, `unverified`, `test_import_unverified` | Gespeichert (`review_required`), nicht exportiert, nicht als Modellkontext genutzt |
| anderes | Abgewiesen (`invalid_document`) |

Der Status wird nie umgeschrieben. Eine ausdrückliche Prüfung ist möglich und an den
Inhalts-Hash gebunden – eine neue Revision braucht eine neue Freigabe:

```sh
docker compose run --rm pipeline import-bulletin --date 2026-11-25 \
  --review approved --reviewer adrian --note "Darstellungstest"
```

Freigegebene Bulletins erscheinen als «manuell freigegeben» mit dem Upstream-Status.
`--review rejected` hält auch ein upstream veröffentlichtes Bulletin zurück.

Das Testbulletin vom 25.11.2026 ist `test_import_unverified` und hat fast keine
Originalquellen. Es dient (gekürzt) als Test-Fixture
`tests/fixtures/prism-data/2026-11-25.json` und wird nicht veröffentlicht.

## Ablauf, Revisionen, Fehler

- Ab 07:00 prüft jeder Pipeline-Zyklus (10 Minuten) die heutige Datei. Fehlt sie:
  `import_waiting`, nächster Zyklus versucht es erneut.
- Gleicher Inhalt (SHA-256): `import_unchanged`, nichts geschieht.
- Korrigierte Datei mit neuerem oder gleichem `generated_at`: ersetzt die gespeicherte
  Revision; die alte bleibt als `superseded` erhalten.
- Ältere Revision: wird als `superseded` protokolliert, ersetzt nie die neuere.
- Ein unterbrochener Import hinterlässt nichts (eine Transaktion); der nächste Lauf
  importiert erneut.
- Fehler beenden nie die Pipeline. Fehlercodes im Event `import_failed`:
  `auth_failed`, `github_unavailable`, `invalid_json`, `invalid_document`,
  `unsupported_schema`, `too_large`, `secret_unreadable`, `invalid_date`.
  Bestehende Ausgaben bleiben veröffentlicht.

Bei 404 prüft der Import separat, ob das Repository lesbar ist, weil GitHub fehlende
Berechtigungen ebenfalls mit 404 beantwortet (`auth_failed` statt `import_waiting`).

Manuell und rückwirkend:

```sh
docker compose run --rm pipeline import-bulletin --date 2026-11-25
docker compose run --rm pipeline import-bulletin --from 2026-11-01 --to 2026-11-25
PYTHONPATH=src python3 -m prismunfold import-bulletin --date 2026-11-25 --file pfad/2026-11-25.json   # lokal, ohne GitHub
```

## Einbindung in die Tagesausgabe

- Am selben Datum werden Bulletin-Artikel deterministisch mit vorhandener
  Berichterstattung abgeglichen (`dedupe.py`: kanonische URLs, Titel, Entitäten,
  ±2 Tage). Eindeutige Treffer erscheinen beim bestehenden Artikel unter «Weitere
  Berichterstattung» mit eigener Herkunft; schon gezeigte Absätze werden nicht
  wiederholt. Zweifelhafte Treffer bleiben eigenständig.
- Die Quellenangaben gelten auf Artikelebene (`citation_level: item`); sie beeinflussen
  weder Verifikationsstatus noch die Zahl unabhängiger Belege.
- Die Vertiefung wird Magazin-Beitrag, Good News und Random eigene Rubriken.
- Bilder werden nur mit Credit und dokumentierter Freigabe oder offener Lizenz
  angezeigt (EDITORIAL_WORKFLOW.md, «Images»).
- Der 06:00-Redaktionslauf erhält das Bulletin des Vortags (oder bereits heutige) als
  Recherchehinweis – nur veröffentlichte oder freigegebene Bulletins, nie als Beleg.

## Grenzen

- Korrekturen des Vortags nach Mitternacht werden nicht automatisch gesucht
  (`--date` verwenden).
- Freigaben werden von der Kommandozeile erteilt; eine Redaktionsoberfläche ist geplant.
