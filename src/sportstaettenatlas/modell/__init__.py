"""Datenmodell des Sportstättenatlas – die einzige Stelle, an der Felder und Regeln stehen.

    klassen.py   Modelle (Sportstätte, Sportanlage, Organisation …), Auswahllisten, Regeln
    anlagen.py   Typen und Gruppen der Sportanlagen
    werte.py     Werte aus Text lesen und bereinigen (CSV, Altdaten)
    export.py    Schema für die Webseite (schema.json)
    doku.py      Feldtabellen und Diagramm (Befehl `modell`)

Dieses Paket importiert nichts aus den anderen Teilen (bestand, pflege, analysen, webseite).
"""

from .doku import (  # noqa: F401
    ERZEUGT,
    aktualisiere_readme,
    alten_block_ersetzen,
    felder_tabelle,
    fuer_text,
    nur_fuer,
    readme_block,
    schreibe_doku,
    zeichne,
)
from .export import schema  # noqa: F401
from .klassen import *
