"""Analysen: Auswertungen, die auf dem Datenbestand oder zusätzlichen Quellen rechnen.

Jede Analyse ist ein Unterpaket mit
- `cli.py`: Befehle unter `sportstaettenatlas <name> …` (Funktion `befehle(sub)`),
- `karte.py` (o. ä.): `webdaten(...)` liefert die Dateien für die Webseite; `seite`
  schreibt sie nach docs/daten/analysen/<name>/ und trägt die Analyse in
  docs/daten/analysen/index.json ein,
- im Browser einen Eintrag in ANALYSEN in web/analysen.js.

Bisher: alkis – Sportstätten aus dem Liegenschaftskataster (ALKIS) ableiten und mit dem
Atlas abgleichen.
"""
