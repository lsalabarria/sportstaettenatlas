"""Kleine Hilfen: Arbeitsordner, User-Agent, Fortschrittsbalken."""

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


class Fortschritt:
    """Fortschrittsbalken (tqdm). Ohne tqdm oder ohne Terminal: stiller Ersatz."""

    def __init__(
        self,
        total: int | None = None,
        desc: str = "",
        einheit: str = "it",
        ebene: int = 0,
        bleiben: bool = True,
    ):
        self._bar = None
        try:
            from tqdm.auto import tqdm
        except ImportError:  # pragma: no cover – tqdm ist Abhängigkeit, nur zur Sicherheit
            return
        self._bar = tqdm(
            total=total, desc=desc, unit=einheit, position=ebene, leave=bleiben, dynamic_ncols=True
        )

    def weiter(self, n: int = 1) -> None:
        if self._bar is not None:
            self._bar.update(n)

    def text(self, desc: str) -> None:
        if self._bar is not None:
            self._bar.set_description_str(desc)

    def info(self, **werte) -> None:
        if self._bar is not None:
            self._bar.set_postfix(werte, refresh=False)

    def schliessen(self) -> None:
        if self._bar is not None:
            self._bar.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.schliessen()


def logging_mit_balken():
    """Kontext, in dem Log-Ausgaben die Fortschrittsbalken nicht zerreißen."""
    try:
        from tqdm.contrib.logging import logging_redirect_tqdm
    except ImportError:  # pragma: no cover
        import contextlib

        return contextlib.nullcontext()
    return logging_redirect_tqdm()
