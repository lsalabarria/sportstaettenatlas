"""Datenbestand in daten/: Dateien lesen und schreiben (ablage.py), prüfen (pruefung.py),
Verwaltungsgebiete als Bezug (gebiete.py).

Die Funktionen aus ablage.py stehen auch direkt hier (`from sportstaettenatlas.bestand import
lies_bestand`). Importiert nur aus modell, nie aus pflege, analysen oder webseite.
"""

from .ablage import *
from .ablage import (  # noqa: F401 – auch intern genutzte Hilfen
    _laender,
    _lies_json,
    _lies_ordner,
    _staetten_dirs,
    _staetten_ordner,
)
