# Datenbestand

Ein Ordner je Kreis, darin ein Ordner je Sportstätte. In dem beschreibt `<id>_meta.json` die
Sportstätte (Standort, Name, Betreiber …), und jede Sportanlage hat eine weitere Datei
`<anlage-id>.json` (z. B. ein Großspielfeld, eine Rundlaufbahn):

    RP/07111-koblenz/333d6875-…/333d6875-…_meta.json
    RP/07111-koblenz/333d6875-…/8f0c41d2-….json

Jede Sportanlage gehört zu genau einer Sportstätte: Sie liegt in deren Ordner und nennt sie
in `sportstaette_id`. Diese Dateien sind die Quelle der Daten: Änderungen werden hier
vorgenommen (direkt auf GitHub oder per Pull Request) und landen beim nächsten Erzeugen der
Webseite auf der Karte.

- Format und Felder: siehe `src/sportstaettenatlas/bestand.py`, Typen der Anlagen:
  `src/sportstaettenatlas/anlagen.py`
- Neue Sportanlage: Datei mit neuer UUID als Namen in den Ordner der Sportstätte legen
  (`id`, `sportstaette_id`, `typ`)
- Neue Sportstätte: Ordner im Ordner ihres Kreises; liegt sie nach einer Änderung der Lage
  in einem anderen Kreis, bringt `uv run sportstaettenatlas umstellen` sie dorthin
- Neue Quelldateien einlesen: `uv run sportstaettenatlas bestand <datei>`
  (legt nur fehlende Sportstätten an; `--modus aktualisieren` überschreibt vorhandene)
- Kontaktdaten (E-Mail-Adressen, Telefonnummern) gehören nicht hierher.
