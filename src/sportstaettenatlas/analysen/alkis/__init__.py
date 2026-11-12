"""ALKIS-Abgleich: Sportstätten aus dem Liegenschaftskataster ableiten, mit daten/ vergleichen.

quellen.py          ALKIS-Dienst (WFS) und Ausschnitte
wfs.py              Laden, gekachelt und mit Zwischenspeicher in results/raw
regeln.toml,        Zuordnung von ALKIS-Nutzungen und Gebäudefunktionen zu Typen
klassifikation.py
pipeline.py         Sportstätten (Flächen) und Sportanlagen (Gebäude, Plätze) bauen
abgleich.py         Sportstätten aus daten/ den ALKIS-Flächen zuordnen, Bericht
verifikation.py     Verifikationsstufe und zusammengeführte Felder mit Herkunft
webdaten.py         Dateien für die Webseite
cli.py              Befehl `sportstaettenatlas alkis`
"""
