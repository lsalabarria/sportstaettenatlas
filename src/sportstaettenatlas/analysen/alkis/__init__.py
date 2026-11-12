"""ALKIS-Abgleich: Sportstätten aus dem Liegenschaftskataster und Vergleich mit dem Atlas.

quellen.py         WFS-Dienste je Land, Testausschnitte
wfs.py             Laden über WFS (gekachelt, mit Zwischenspeicher)
regeln.toml,       Zuordnung von ALKIS-Nutzungen und Gebäudefunktionen zu Typen
klassifikation.py
pipeline.py        Sportstätten (Flächen) und Sportanlagen (Gebäude, Plätze) bauen
abgleich.py        Atlas-Einträge den ALKIS-Sportstätten zuordnen, Bericht
verifikation.py    Verifikationsstufe und zusammengeführte Felder mit Herkunft
vor_ort.py         Was führt ALKIS dort, wo nur der Atlas eine Sportstätte kennt?
karte.py           Dateien für die Webseite und karte.html
cli.py             Befehle `sportstaettenatlas alkis …`
"""
