"""Kleine Hilfsfunktionen ohne Geo-Abhängigkeiten."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATEN = Path("data")  # Arbeitsordner: raw/ (Downloads), cache/, out/ (Ergebnisse)


def datum_text(s: pd.Series) -> pd.Series:
    """Datum/Zeitstempel → "JJJJ-MM-TT" als Text.

    Gemischte Spalten (Datum und leer) kann pyogrio nicht als GeoPackage schreiben.
    """
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
