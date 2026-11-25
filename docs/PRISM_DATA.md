# GitHub-Bulletins in PrismUnfold

Der Pipeline-Container liest `AdBuch/prism-data`, Branch `main`, über die
GitHub Contents API. Erwartet wird `data/morgenbriefing/YYYY-MM-DD.json`.
Die lokale Ausgabe richtet sich nach `Europe/Zurich` und wird ab 07:00 Uhr
im bestehenden Pipeline-Zyklus gesucht. Bei zehn Minuten Zykluszeit kann die
erste Zustellung bis zum nächsten Durchlauf dauern. Fehlt das Bulletin,
ist GitHub vorübergehend nicht erreichbar oder enthält die Datei Fehler,
bleiben die bestehende Ausgabe und die übrigen Quellen aktiv.

## Einschalten

1. Für `prism-data` ein fein abgestuftes GitHub-Token mit Zugriff nur auf dieses
   Repository und der Berechtigung **Contents: Read-only** erstellen. Für den
   Betrieb den Ablauf des Tokens überwachen und das Token regelmässig erneuern.
2. Den Tokenwert in einer Datei ausserhalb des Checkouts ablegen, ohne
   Gruppen- oder Weltzugriff. Die Datei muss für den Pipeline-Prozess (UID 1000
   im Container) lesbar sein. Bei rootless Docker die Host-UID-Zuordnung
   berücksichtigen. Compose bindet dateibasierte Secrets ein und übernimmt
   deshalb die Eigentümerschaft und Rechte der Datei.
3. In der lokalen `.env` nur den Dateipfad und die Compose-Dateien setzen.
   Wenn bereits weitere Overlays verwendet werden, die Liste ergänzen.

   ```dotenv
   COMPOSE_FILE=docker-compose.yml:deploy/compose.prism-data.yml
   PRISM_DATA_SECRET_PATH=/absoluter/pfad/prism-data.token
   ```

4. Die Images von Pipeline und Web neu bauen und starten. Nur die Pipeline
   bekommt das Secret unter `/run/secrets/prism_data_token`.

   ```sh
   docker compose up -d --build pipeline web
   docker compose logs --tail 100 pipeline
   ```

## Ausgabeformat und Redaktion

Die Integration akzeptiert Schema `1.0` und `1.1` mit Datum, Zeitzone,
`generated_at` inklusive Zeitzone und `publication_status`. Die Rubriken
enthalten Artikel mit stabiler ID, Titel und Text. `deep_dive`, `good_news`,
`random_fact`, `outlook`, Vorspann und redaktionelle Hinweise werden
übernommen, sofern vorhanden. Zur Publikation `published` oder `final`
setzen. `draft`, `unverified` und `test_import_unverified` werden für den
Importtest gespeichert. Diese drei Zustände werden weder exportiert noch
als Modellkontext verwendet. Unbekannte Zustände und fehlerhafte Dokumente
werden zurückgewiesen.

- **Originalquellen:** `sources` enthält URL, Titel und Verlag sowie
  gegebenenfalls Veröffentlichungsdatum, Typ und Zugriff. `source_urls`
  ergänzt einfache Verweise. Diese Zuordnung gilt auf Artikelebene. Sie
  beeinflusst weder den Verifikationsstatus noch die Zahl unabhängiger
  Belege in der bestehenden Pipeline.
- **Perspektiven:** `assessments` und `perspectives` unterstützen Text oder
  Objekte mit Text, Bezeichnung, Attribution und eigenen Quellen.
  `uncertainties` bleibt am jeweiligen Artikel sichtbar.
- **Bilder:** `images` unterstützt `url`, `source_url`, `alt`, `caption`,
  `credit`, `license`, `license_url`, `rights`, `rights_note` und
  `display_allowed`. Eingebettet werden HTTPS-Bilder mit Credit und
  dokumentierter Freigabe oder erkannter offener Lizenz. Bei fehlender Freigabe
  erscheinen nur die Rechtehinweise und der Bildquellen-Link, sofern
  mitgeliefert. Der Browser lädt freigegebene Bilder direkt ohne Referrer.
  Die Rechtekennzeichnung kommt vom Upstream, der seine Freigaben prüfen muss.
- **Tagesausgabe:** Am selben Ausgabedatum ordnet der Export eindeutige Treffer
  nach normalisiertem Titel und gemeinsamen Original-URLs zusammen. Bei hoher
  Titelähnlichkeit ist auch ein Treffer aus unterschiedlichen Quellen möglich.
  Zweifelhafte oder mehrdeutige Treffer bleiben eigenständig. Der bestehende
  Artikel behält Titel, Text und Quellen. Ergänzungen erscheinen mit eigener
  Herkunft, Unsicherheit und Quellenbindung unter «Weitere Berichterstattung».
  Eigenständige Vertiefungen bleiben als Magazin-Stücke erhalten. Feed-Überblick,
  bestehende Ausgaben und deren Prüfregeln bleiben verfügbar.
- **Redaktionslauf:** Der 06:00-Uhr-Lauf kann den Vortag als Kontext verwenden.
  Sobald das aktuelle Bulletin importiert ist, wird es beim nächsten Export in
  die aktuelle Morgenbriefing-Ausgabe integriert. Spätere manuelle
  Redaktionsläufe sehen die aktuellen Überschriften und Originalverweise als
  Recherchehinweise. Zur Faktenbestätigung bleiben Originalbelege erforderlich.

## Betrieb und Fehler

Der Import speichert je Ausgabedatum einen Datensatz mit Inhalts-Hash und
Erzeugungszeit. Unveränderte Dateien werden erkannt. Korrigierte Dateien
werden neu geprüft und aktualisiert. Bei einem 404 prüft der Import separat,
ob das Repository lesbar ist, weil GitHub fehlende private Berechtigungen
ebenfalls mit 404 beantwortet. Tokens und Bulletin-Inhalte gelangen nicht
ins Importlog.

Ein Datum lässt sich ohne Wartezeit nachladen:

```sh
docker compose exec -T pipeline python3 -m prismunfold import-bulletin \
  --date YYYY-MM-DD --site /site
```

Logs zeigen Wartestatus, unveränderte Inhalte, öffentliche beziehungsweise
zurückgehaltene Ausgaben und Importfehler. Bei Berechtigungsfehlern den
Repository-Zugriff des Tokens und die Lesbarkeit der Secret-Datei im
Pipeline-Container prüfen. Den Tokenwert dabei nicht ausgeben.
