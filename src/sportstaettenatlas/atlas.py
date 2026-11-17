"""Export des bisherigen Sportstättenatlas RLP lesen (CSV, eine Zeile je Sportstätte).

Achtung: Unter "Latitude"/"Longitude" stehen UTM-Werte (Hochwert/Rechtswert, EPSG:25832);
echte Grad-Werte werden erkannt. Spalten mit Kontaktdaten liest `lies_export` nicht.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Iterator
from pathlib import Path

from . import anlagen as anlagen_typen
from . import werte

PFLICHT = {"ID", "Name", "Sportstättenkategorie", "Latitude", "Longitude"}


@functools.cache
def _transformer(von: str, nach: str):
    from pyproj import Transformer

    return Transformer.from_crs(von, nach, always_xy=True)


def lage(a: float, b: float) -> dict:
    """Spalten Latitude=a, Longitude=b → {"lon", "lat"} in WGS84."""
    if a > 1e5 and b > 1e5:  # UTM, nur falsch beschriftet: Hochwert und Rechtswert
        x, y = (b, a) if a > b else (a, b)
        lon, lat = _transformer("EPSG:25832", "EPSG:4326").transform(x, y)
    else:
        lon, lat = b, a
    return {"lon": round(lon, 6), "lat": round(lat, 6)}


def anlagen_aus(bezeichnungen: list[str]) -> list[dict]:
    """Bezeichnungen des Atlas → Sportanlagen mit einheitlichem Typ."""
    return [{"typ": anlagen_typen.typ(b)} for b in bezeichnungen]


def lies_export(pfad: Path, lage_aus=lage) -> Iterator[dict]:
    """Atlas-Export → Sportstätten im Format des Datenbestands (mit Liste "anlagen")."""
    pfad = Path(pfad)
    zeilen = werte.zeilen(werte.text(pfad.read_bytes()))
    if not zeilen or not PFLICHT <= set(zeilen[0]):
        raise ValueError(f"{pfad.name}: Spalten {sorted(PFLICHT)} fehlen – kein Atlas-Export?")
    for z in zeilen:

        def g(k: str, z: dict = z) -> str:
            return (z.get(k) or "").strip()

        a, b = (
            werte.oder_none(werte.zahl, g("Latitude")),
            werte.oder_none(werte.zahl, g("Longitude")),
        )
        yield {
            "id": re.sub(r"[^A-Za-z0-9_-]+", "-", g("ID")).strip("-").lower(),
            "name": g("Name"),
            "kategorie": g("Sportstättenkategorie"),
            "adresse": {
                "strasse": g("Straße"),
                "hausnummer": g("Hausnummer"),
                "plz": g("PLZ"),
                "ort": g("Stadt"),
            },
            "lage": lage_aus(a, b) if a is not None and b is not None else None,
            "oeffentlicher_zugang": werte.oder_none(werte.ja_nein, g("Öffentlicher Zugang")),
            "schulsport": werte.oder_none(werte.ja_nein, g("Schulsport")),
            "zuschauerplaetze": werte.oder_none(werte.ganzzahl, g("Zuschauerplätze Gesamt")),
            "betriebsstatus": g("Betriebsstatus"),
            "eigentuemer": g("Name des Eigentümers"),
            "betreiber": g("Name des Betreibers"),
            "website": g("Webseite"),
            "sportarten": werte.liste(g("Sportarten")),
            "anlagen": anlagen_aus(werte.liste(g("Sportanlagen"))),
        }
