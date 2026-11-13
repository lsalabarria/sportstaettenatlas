"""Kleine Hilfen: Arbeitsordner, User-Agent, Datum als Text."""

from __future__ import annotations

import os
from pathlib import Path

# Arbeitsordner, nicht im Git: raw/ (Downloads), cache/, out/ (Ergebnisse der Analysen).
# Nicht zu verwechseln mit daten/, dem gepflegten Datenbestand.
ERGEBNISSE = Path("results")

# Kontakt im User-Agent für Abfragen bei BKG und LVermGeo (freiwillig):
#   export SPORTSTAETTENATLAS_KONTAKT="name@example.org"
_KONTAKT = os.environ.get("SPORTSTAETTENATLAS_KONTAKT", "")
USER_AGENT = "sportstaettenatlas/0.1 (Sportstaettenatlas" + (f"; {_KONTAKT})" if _KONTAKT else ")")


def datum_text(s):
    """Datum/Zeitstempel → "JJJJ-MM-TT" als Text.

    Gemischte Spalten (Datum und leer) kann pyogrio nicht als GeoPackage schreiben.
    """
    import pandas as pd

    werte = pd.to_datetime(s, errors="coerce", utc=True)
    text = werte.dt.strftime("%Y-%m-%d")
    # Werte, die kein Datum sind, unverändert als Text behalten
    roh = s.where(werte.isna()).map(lambda v: None if pd.isna(v) else str(v))
    erg = text.where(werte.notna(), roh).astype("object")
    return pd.Series([None if pd.isna(v) else v for v in erg], index=s.index, dtype="object")
