"""Export des bisherigen Sportstättenatlas RLP lesen (CSV, eine Zeile je Sportstätte).

Spalten ID, Name, Sportstättenkategorie, …, Sportanlagen, Latitude, Longitude. Achtung:
Unter "Latitude"/"Longitude" stehen UTM-Werte (Hochwert/Rechtswert, EPSG:25832); echte
Grad-Werte werden erkannt. Die E-Mail-Spalte wird nie gelesen. Der Export enthält
Kontaktdaten und gehört nicht ins Repository.
"""

from __future__ import annotations

import csv
import functools
import io
import re
from collections.abc import Iterator
from pathlib import Path

from . import anlagen as anlagen_typen

PFLICHT = {"ID", "Name", "Sportstättenkategorie", "Latitude", "Longitude"}


def _text(roh: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return roh.decode(enc)
        except UnicodeDecodeError:
            continue
    return roh.decode("utf-8", errors="replace")


def _zeilen(text: str) -> list[dict]:
    try:
        dialekt = csv.Sniffer().sniff(text[:5000], delimiters=";,")
    except csv.Error:
        dialekt = csv.excel
    return list(csv.DictReader(io.StringIO(text), dialect=dialekt))


def _zahl(v: str | None) -> float | None:
    try:
        return float(str(v).strip().replace(",", ".")) if v and str(v).strip() else None
    except ValueError:
        return None


def _datum(name: str) -> str:
    """Stand aus dem Dateinamen: 2026-11-04 oder 04112026."""
    if m := re.search(r"(\d{4}-\d{2}-\d{2})", name):
        return m.group(1)
    if m := re.search(r"(?<!\d)(\d{2})(\d{2})(20\d{2})(?!\d)", name):
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return ""


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


def _ja_nein(wert: str) -> str | None:
    w = wert.lower()
    return w if w in ("ja", "nein") else None


def _ganzzahl(wert: str) -> int | None:
    z = _zahl(wert)
    return int(z) if z is not None and z == int(z) and z >= 0 else None


def _liste(wert: str) -> list[str]:
    """ "A, B (x, y), C" → ["A", "B (x, y)", "C"]; Kommas in Klammern trennen nicht,
    "Weit-, Dreisprunganlage" bleibt eine Anlage."""
    return anlagen_typen.zusammenfuegen(re.split(r",\s*(?![^()]*\))", wert or ""))


def anlagen_aus(bezeichnungen: list[str]) -> list[dict]:
    """Bezeichnungen des Atlas → Sportanlagen mit einheitlichem Typ; eine abweichende
    Schreibweise ("Großspielfeld (ab 5.000 m²)") bleibt unter quellen.atlas_rlp."""
    out = []
    for b in anlagen_typen.zusammenfuegen(bezeichnungen):
        t = anlagen_typen.typ(b)
        out.append({"typ": t, **({"quellen": {"atlas_rlp": {"bezeichnung": b}}} if b != t else {})})
    return out


def lies_export(pfad: Path, lage_aus=lage) -> Iterator[dict]:
    """Atlas-Export → Sportstätten im Format des Datenbestands (mit Liste "anlagen")."""
    pfad = Path(pfad)
    zeilen = _zeilen(_text(pfad.read_bytes()))
    if not zeilen or not PFLICHT <= set(zeilen[0]):
        raise ValueError(f"{pfad.name}: Spalten {sorted(PFLICHT)} fehlen – kein Atlas-Export?")
    stand = _datum(pfad.name)
    for z in zeilen:

        def g(k: str, z: dict = z) -> str:
            return (z.get(k) or "").strip()

        a, b = _zahl(g("Latitude")), _zahl(g("Longitude"))
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
            "oeffentlicher_zugang": _ja_nein(g("Öffentlicher Zugang")),
            "schulsport": _ja_nein(g("Schulsport")),
            "zuschauerplaetze": _ganzzahl(g("Zuschauerplätze Gesamt")),
            "betriebsstatus": g("Betriebsstatus"),
            "eigentuemer": g("Name des Eigentümers"),
            "betreiber": g("Name des Betreibers"),
            "website": g("Webseite"),
            "sportarten": _liste(g("Sportarten")),
            "anlagen": anlagen_aus(_liste(g("Sportanlagen"))),
            "quellen": {"atlas_rlp": {"id": g("ID"), "datei": pfad.name, "stand": stand}},
        }
