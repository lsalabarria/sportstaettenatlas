"""Datenbestand im Git: eine JSON-Datei je Sportstätte unter daten/<LAND>/<id>.json.

Ab der ersten Überführung sind diese Dateien die Quelle der Daten. Änderungen laufen
über das Git (z. B. Pull Requests); Quelldateien wie der Atlas-Export werden mit
`sportstaettenatlas bestand` eingelesen.

Neue Quellformate: eine Funktion `lies_<format>(pfad, land, umrechnen)` schreiben, die
Datensätze im Format unten liefert, und in LESER eintragen.

Format einer Datei (leere Angaben werden weggelassen):

    {
      "id": "RP-12345",
      "name": "Sportplatz Musterdorf",
      "kategorie": "Sportplatz",
      "adresse": {"strasse": "Am Weg", "hausnummer": "1", "plz": "56068", "ort": "Koblenz"},
      "lage": {"lon": 7.59, "lat": 50.35},
      "oeffentlicher_zugang": "ja" | "nein",
      "schulsport": "ja" | "nein",
      "zuschauerplaetze": 300,
      "betriebsstatus": "in Betrieb",
      "eigentuemer": "…", "betreiber": "…", "website": "…",
      "sportarten": ["Fußball", "Leichtathletik"],
      "anlagen": [{"bezeichnung": "Großspielfeld (ab 5.000 m²)"}],
      "quellen": {"atlas_rlp": {"id": "12345", "datei": "…csv", "stand": "2026-11-04"}}
    }

Kontaktdaten (E-Mail, Telefon) werden nie gelesen. Zusätzlich wird jeder Wert entfernt,
der eine E-Mail-Adresse enthält.
"""

from __future__ import annotations

import functools
import json
import re
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .anreicherung.altbestand import EXPORT_PFLICHT, _datum, _text, _utm, _zahl, _zeilen

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
Umrechnen = Callable[[float, float], tuple[float, float]]  # (x, y) EPSG:25832 → (lon, lat)


@functools.cache
def _transformer():
    from pyproj import Transformer

    return Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)


def utm32_nach_wgs84(x: float, y: float) -> tuple[float, float]:
    lon, lat = _transformer().transform(x, y)
    return round(lon, 6), round(lat, 6)


def _ja_nein(wert: str) -> str | None:
    w = (wert or "").strip().lower()
    return w if w in ("ja", "nein") else None


def _ganzzahl(wert: str) -> int | None:
    z = _zahl(wert)
    return int(z) if z is not None and z == int(z) and z >= 0 else None


def _liste(wert: str) -> list[str]:
    # "A, B (x, y), C" → ["A", "B (x, y)", "C"]: Kommas in Klammern trennen nicht
    return [t.strip() for t in re.split(r",\s*(?![^()]*\))", wert or "") if t.strip()]


def datei_id(land: str, quell_id: str) -> str:
    return f"{land.upper()}-{re.sub(r'[^A-Za-z0-9_-]+', '-', str(quell_id)).strip('-')}"


def lies_atlas_export(
    pfad: Path, land: str, umrechnen: Umrechnen = utm32_nach_wgs84
) -> Iterator[dict]:
    """Export des bisherigen Sportstättenatlas (CSV, eine Zeile je Sportstätte)."""
    zeilen = _zeilen(_text(Path(pfad).read_bytes()))
    if not zeilen or not EXPORT_PFLICHT <= set(zeilen[0]):
        raise ValueError(
            f"{pfad.name}: Spalten {sorted(EXPORT_PFLICHT)} fehlen – kein Atlas-Export?"
        )
    stand = _datum(pfad.name)
    for z in zeilen:

        def g(k: str, z: dict = z) -> str:
            return (z.get(k) or "").strip()

        a, b = _zahl(z.get("Latitude")), _zahl(z.get("Longitude"))
        lage = None
        if a is not None and b is not None:
            x, y = _utm(a, b)
            lon, lat = umrechnen(x, y)
            lage = {"lon": lon, "lat": lat}
        yield {
            "id": datei_id(land, g("ID")),
            "name": g("Name"),
            "kategorie": g("Sportstättenkategorie"),
            "adresse": {
                "strasse": g("Straße"),
                "hausnummer": g("Hausnummer"),
                "plz": g("PLZ"),
                "ort": g("Stadt"),
            },
            "lage": lage,
            "oeffentlicher_zugang": _ja_nein(g("Öffentlicher Zugang")),
            "schulsport": _ja_nein(g("Schulsport")),
            "zuschauerplaetze": _ganzzahl(g("Zuschauerplätze Gesamt")),
            "betriebsstatus": g("Betriebsstatus"),
            "eigentuemer": g("Name des Eigentümers"),
            "betreiber": g("Name des Betreibers"),
            "website": g("Webseite"),
            "sportarten": _liste(g("Sportarten")),
            "anlagen": [{"bezeichnung": t} for t in _liste(g("Sportanlagen"))],
            "quellen": {"atlas_rlp": {"id": g("ID"), "datei": pfad.name, "stand": stand}},
        }


LESER: dict[str, Callable[..., Iterator[dict]]] = {"atlas-export": lies_atlas_export}


def erkenne_format(pfad: Path) -> str:
    kopf = _zeilen(_text(Path(pfad).read_bytes()[:20000]))
    if kopf and EXPORT_PFLICHT <= set(kopf[0]):
        return "atlas-export"
    raise ValueError(
        f"{pfad.name}: Format nicht erkannt – bitte --format angeben ({', '.join(LESER)})"
    )


def bereinigen(wert, entfernt: Counter, pfad: str = ""):
    """Leere Angaben weglassen; Werte mit E-Mail-Adresse entfernen (und zählen)."""
    if isinstance(wert, dict):
        out = {}
        for k, v in wert.items():
            v = bereinigen(v, entfernt, f"{pfad}.{k}" if pfad else k)
            if v not in (None, "", [], {}):
                out[k] = v
        return out
    if isinstance(wert, list):
        return [
            v for v in (bereinigen(v, entfernt, pfad) for v in wert) if v not in (None, "", [], {})
        ]
    if isinstance(wert, str):
        if EMAIL.search(wert):
            entfernt[re.sub(r"\.\d+$", "", pfad)] += 1
            return None
        return wert.strip()
    return wert


def als_json(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False, indent=2) + "\n"


@dataclass
class Ergebnis:
    neu: int = 0
    aktualisiert: int = 0
    unveraendert: int = 0
    behalten: int = 0  # vorhanden, im Modus "neu" nicht angefasst
    ohne_lage: int = 0
    doppelt: int = 0
    nicht_mehr_in_quelle: int = 0
    entfernt: Counter = field(default_factory=Counter)


def schreibe_bestand(datensaetze, ziel: Path, land: str, modus: str = "neu") -> Ergebnis:
    """Datensätze als daten/<LAND>/<id>.json ablegen.

    modus="neu":           nur fehlende Dateien anlegen, vorhandene nie verändern
                           (sie können inzwischen von Hand gepflegt sein)
    modus="aktualisieren": vorhandene Dateien mit dem Stand der Quelle überschreiben
    Dateien, die in der Quelle fehlen, werden nur gezählt, nie gelöscht.
    """
    if modus not in ("neu", "aktualisieren"):
        raise ValueError(f"Unbekannter Modus: {modus}")
    ordner = ziel / land.upper()
    ordner.mkdir(parents=True, exist_ok=True)
    e = Ergebnis()
    gesehen: set[str] = set()
    for roh in datensaetze:
        d = bereinigen(roh, e.entfernt)
        if not d.get("id") or not d.get("lage"):
            e.ohne_lage += 1
            continue
        if d["id"] in gesehen:
            e.doppelt += 1
            continue
        gesehen.add(d["id"])
        datei = ordner / f"{d['id']}.json"
        text = als_json(d)
        if not datei.exists():
            datei.write_text(text, encoding="utf-8")
            e.neu += 1
        elif modus == "neu":
            e.behalten += 1
        elif datei.read_text(encoding="utf-8") == text:
            e.unveraendert += 1
        else:
            datei.write_text(text, encoding="utf-8")
            e.aktualisiert += 1
    e.nicht_mehr_in_quelle = sum(1 for p in ordner.glob("*.json") if p.stem not in gesehen)
    return e


README_DATEN = """# Datenbestand

Eine JSON-Datei je Sportstätte, nach Land sortiert (`RP/RP-12345.json`). Diese Dateien sind
die Quelle der Daten: Änderungen werden hier vorgenommen (direkt auf GitHub oder per Pull
Request) und landen beim nächsten Erzeugen der Webseite auf der Karte.

- Format und Felder: siehe `src/sportstaettenatlas/bestand.py`
- Neue Quelldateien einlesen: `uv run sportstaettenatlas bestand <datei>`
  (legt nur fehlende Sportstätten an; `--modus aktualisieren` überschreibt vorhandene)
- Kontaktdaten (E-Mail-Adressen, Telefonnummern) gehören nicht hierher.
"""
