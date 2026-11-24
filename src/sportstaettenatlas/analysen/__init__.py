"""Analysen: Auswertungen, die den Datenbestand lesen (nie verändern) und Ergebnisse nach
results/ schreiben.

    alkis/       Abgleich mit dem Liegenschaftskataster; liefert auch Dateien für die
                 Webseite (`seite` schreibt sie nach docs/daten/analysen/alkis/; im Browser
                 gehört dazu ein Eintrag in ANALYSEN in webseite/app/analysen.js)
    crawler.py   Webseiten für Vereine ohne Webseite suchen → results/vereinswebseiten.csv

Importiert aus modell und bestand, nie aus pflege oder webseite.
"""
