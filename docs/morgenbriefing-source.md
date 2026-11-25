# Morgenbriefing als zusätzliche Quelle

Die täglichen ChatGPT-Morgenbriefings werden unter `data/morgenbriefing/YYYY-MM-DD.json` erwartet. **Sie ergänzen RSS, Agenturen und andere Quellen; sie ersetzen sie nicht.** Das Briefing ist bereits eine KI-Kuratierung und darf nicht als unabhängige Bestätigung einer Nachricht gezählt werden.

## Import

```sh
python3 tools/import_morgenbriefing.py data/morgenbriefing/2026-11-26.json > /tmp/morgenbriefing-normalized.json
```

Der Adapter validiert Datum und Quellen-URLs und erzeugt stabile, tagesbezogene IDs sowie Provenienz-Metadaten. Originalquellen bleiben erhalten; jedes Item erhält `requires_independent_verification: true`. Er importiert nur vorhandene Dateien und verändert keine anderen Feeds. Das Eingabeformat entspricht dem täglichen Automation-Auftrag: `date`, `timezone`, `generated_at`, `lead`, `sections: [{title, items: [{title, body, source_urls}]}]`, `deep_dive`, `good_news`, `random_fact`, `outlook`.

## Integration in die produktive Pipeline

1. Bei jedem Pipeline-Lauf neue Dateien aus dem GitHub-Repo lesen (GitHub Contents API oder lokaler Git-Checkout), nach Datum und Datei-SHA idempotent verarbeiten.
2. Importierte Items mit bestehenden Events anhand von Original-URLs und semantischer Ähnlichkeit zusammenführen. **Keine zweite Meldung**, nur weil dieselbe Nachricht im Morgenbriefing vorkommt.
3. Die redaktionelle Priorisierung und Themenauswahl als Signal verwenden, niemals als alleinige Faktenquelle oder zusätzliche unabhängige Bestätigung.
4. Die Ausgabe in der Edition mit Quelle `ChatGPT Morgenbriefing` kennzeichnen; auf Originalquellen verlinken. Vertiefung als Magazinbeitrag behandeln, Good News/Random als eigene Rubriken.
5. Bei fehlender, ungültiger oder verspäteter Tagesdatei normal mit den übrigen Quellen fortfahren. Importfehler protokollieren; historische Editionen nicht still überschreiben.
6. Für ein echtes Deployment den Importer an den vorhandenen DB-/Pipeline-Adapter anschliessen und mit Beispieldaten testen. **Dieses Repository enthält derzeit keinen ausführbaren Pipeline-Code**, daher ist der Adapter noch nicht an den laufenden Docker-Dienst angeschlossen.

Keine GitHub-Tokens in Dateien einchecken; für private Repositories Token nur über Laufzeit-Secrets bereitstellen.
