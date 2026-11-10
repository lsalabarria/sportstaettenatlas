# Datenbestand

Eine JSON-Datei je Sportstätte, nach Land sortiert (`RP/RP-12345.json`). Diese Dateien sind
die Quelle der Daten: Änderungen werden hier vorgenommen (direkt auf GitHub oder per Pull
Request) und landen beim nächsten Erzeugen der Webseite auf der Karte.

- Format und Felder: siehe `src/sportstaettenatlas/bestand.py`
- Neue Quelldateien einlesen: `uv run sportstaettenatlas bestand <datei>`
  (legt nur fehlende Sportstätten an; `--modus aktualisieren` überschreibt vorhandene)
- Kontaktdaten (E-Mail-Adressen, Telefonnummern) gehören nicht hierher.
