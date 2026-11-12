"""Datenbestand in daten/: Kreis / Sportstätte / Sportanlagen (Aufbau: daten/README.md).

    daten/RP/07111-koblenz/<id>/<id>_meta.json     die Sportstätte
    daten/RP/07111-koblenz/<id>/<anlage-id>.json   je Sportanlage eine Datei

Der Kreis-Ordner ergibt sich aus der Lage (`kreis_ordner`). Jede Sportanlage nennt in
`sportstaette_id` die Sportstätte ihres Ordners; `lies_bestand` prüft das. Werte mit einer
E-Mail-Adresse werden beim Schreiben entfernt.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
OHNE_KREIS = "ohne-kreis"
KreisVon = Callable[[float, float], str]  # (lon, lat) → Name des Kreis-Ordners

# feste Basis, damit dieselbe Anlage bei jedem Einlesen dieselbe ID bekommt
_ANLAGEN_NAMENSRAUM = uuid.UUID("5c1e0b8e-6d0a-4c57-9a43-2f1d6b0c7a11")


def adresse_text(a: dict) -> str:
    strasse = " ".join(x for x in (a.get("strasse"), a.get("hausnummer")) if x)
    ort = " ".join(x for x in (a.get("plz"), a.get("ort")) if x)
    return ", ".join(x for x in (strasse, ort) if x)


# --- Kreis-Ordner -----------------------------------------------------------------------


def _slug(text: str) -> str:
    t = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def kreis_ordner(gebiete: dict) -> KreisVon:
    """Aus den Verwaltungsgebieten (gebiete.lade): (lon, lat) → "07111-koblenz".

    Gleichnamige Kreise (Stadt und Landkreis Kaiserslautern) unterscheidet der Schlüssel;
    die kreisfreie Stadt bekommt zusätzlich "-stadt".
    """
    from .gebiete import Zuordnung

    kreise = [f["properties"] for f in gebiete["kreis"]["features"]]
    namen = Counter(k["name"] for k in kreise)
    ordner = {}
    for k in kreise:
        stadt = namen[k["name"]] > 1 and k.get("bez") == "Kreisfreie Stadt"
        ordner[str(k["ars"])[:5]] = f"{str(k['ars'])[:5]}-{_slug(k['name'])}" + (
            "-stadt" if stadt else ""
        )
    zuordnung = Zuordnung(gebiete["gemeinde"])

    def kreis_von(lon: float, lat: float) -> str:
        ars = zuordnung.ars(lon, lat)
        return ordner.get(ars[:5], OHNE_KREIS) if ars else OHNE_KREIS

    return kreis_von


def _kreis(d: dict, kreis_von: KreisVon) -> str:
    lage = d.get("lage") or {}
    return kreis_von(lage.get("lon"), lage.get("lat"))


# --- Schreiben --------------------------------------------------------------------------


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
        werte = (bereinigen(v, entfernt, pfad) for v in wert)
        return [v for v in werte if v not in (None, "", [], {})]
    if isinstance(wert, str):
        if EMAIL.search(wert):
            entfernt[re.sub(r"\.\d+$", "", pfad)] += 1
            return None
        return wert.strip()
    return wert


def als_json(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False, indent=2) + "\n"


def anlage_id(staette: str, typ: str, nr: int) -> str:
    """ID einer Sportanlage: aus Sportstätte, Typ und laufender Nummer je Typ (1, 2 …)."""
    return str(uuid.uuid5(_ANLAGEN_NAMENSRAUM, f"{staette}/{typ}/{nr}"))


def aufteilen(d: dict) -> dict[str, str]:
    """Sportstätte mit Liste "anlagen" → {Dateiname: Inhalt} für ihren Ordner."""
    sid = d["id"]
    meta = {k: v for k, v in d.items() if k not in ("anlagen", "_ordner")}
    dateien = {f"{sid}_meta.json": als_json(meta)}
    nr: Counter = Counter()
    for a in d.get("anlagen") or []:
        nr[a["typ"]] += 1
        aid = a.get("id") or anlage_id(sid, a["typ"], nr[a["typ"]])
        rest = {k: v for k, v in a.items() if k not in ("id", "sportstaette_id", "typ")}
        dateien[f"{aid}.json"] = als_json(
            {"id": aid, "sportstaette_id": sid, "typ": a["typ"], **rest}
        )
    return dateien


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


def _staetten_ordner(land_ordner: Path) -> dict[str, Path]:
    return {p.name: p for p in sorted(land_ordner.glob("*/*")) if p.is_dir()}


def schreibe_bestand(
    datensaetze, ziel: Path, land: str, kreis_von: KreisVon, modus: str = "neu"
) -> Ergebnis:
    """Sportstätten (mit Liste "anlagen") als daten/<LAND>/<Kreis>/<id>/ ablegen.

    modus="neu":           nur fehlende Sportstätten anlegen, vorhandene nie verändern
                           (sie können inzwischen von Hand gepflegt sein)
    modus="aktualisieren": Dateien vorhandener Sportstätten mit dem Stand der Quelle
                           überschreiben; zusätzlich angelegte Anlagen bleiben
    Sportstätten, die in der Quelle fehlen, werden nur gezählt, nie gelöscht.
    """
    if modus not in ("neu", "aktualisieren"):
        raise ValueError(f"Unbekannter Modus: {modus}")
    ordner = ziel / land.upper()
    ordner.mkdir(parents=True, exist_ok=True)
    vorhanden = _staetten_ordner(ordner)
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
        st_ordner = vorhanden.get(d["id"])
        if st_ordner is not None and modus == "neu":
            e.behalten += 1
            continue
        neu = st_ordner is None
        if neu:
            st_ordner = ordner / _kreis(d, kreis_von) / d["id"]
            st_ordner.mkdir(parents=True)
            e.neu += 1
        geaendert = False
        for name, text in aufteilen(d).items():
            pfad = st_ordner / name
            if not pfad.exists() or pfad.read_text(encoding="utf-8") != text:
                pfad.write_text(text, encoding="utf-8")
                geaendert = True
        if not neu:
            if geaendert:
                e.aktualisiert += 1
            else:
                e.unveraendert += 1
    e.nicht_mehr_in_quelle = len(set(vorhanden) - gesehen)
    return e


def einordnen(ziel: Path, kreis_von: KreisVon) -> int:
    """Ordner von Sportstätten, die nicht im Ordner ihres Kreises liegen (z. B. nach einer
    Änderung der Lage), dorthin verschieben. Liefert die Zahl der verschobenen."""
    n = 0
    for meta in sorted(Path(ziel).glob("*/*/*/*_meta.json")):
        st_ordner = meta.parent
        soll = st_ordner.parent.parent / _kreis(_lies_json(meta), kreis_von) / st_ordner.name
        if soll == st_ordner:
            continue
        if soll.exists():
            raise ValueError(f"{soll} gibt es schon – {st_ordner} bitte von Hand prüfen.")
        soll.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(st_ordner, soll)
        n += 1
    for leer in Path(ziel).glob("*/*"):  # leer gewordene Kreis-Ordner
        if leer.is_dir() and not any(leer.iterdir()):
            leer.rmdir()
    return n


# --- Lesen ------------------------------------------------------------------------------


def _lies_json(datei: Path) -> dict:
    try:
        return json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{datei}: kein gültiges JSON ({exc})") from exc


def lies_bestand(ordner: Path) -> Iterator[dict]:
    """Alle Sportstätten unter daten/<LAND>/<Kreis>/<id>/, jeweils mit ihren Anlagen.

    Prüft den Aufbau: Jeder Ordner hat seine <id>_meta.json, jede Anlage nennt in
    `sportstaette_id` die Sportstätte ihres Ordners, Dateiname = id, typ ist gesetzt.
    Im Ergebnis steht zusätzlich "_ordner" (Kreis-Ordner).
    """
    for st_ordner in sorted(p for p in Path(ordner).glob("*/*/*") if p.is_dir()):
        sid = st_ordner.name
        meta_pfad = st_ordner / f"{sid}_meta.json"
        if not meta_pfad.exists():
            raise ValueError(f"{st_ordner}: {meta_pfad.name} fehlt – Sportanlagen ohne Sportstätte")
        meta = _lies_json(meta_pfad)
        if meta.get("id") != sid:
            raise ValueError(f"{meta_pfad}: id {meta.get('id')!r} passt nicht zum Ordner {sid}")
        anlagen = []
        for pfad in sorted(p for p in st_ordner.glob("*.json") if p != meta_pfad):
            a = _lies_json(pfad)
            if a.get("sportstaette_id") != sid:
                raise ValueError(
                    f"{pfad}: sportstaette_id {a.get('sportstaette_id')!r} – jede Sportanlage "
                    f"muss im Ordner ihrer Sportstätte liegen (hier {sid})"
                )
            if a.get("id") != pfad.stem:
                raise ValueError(f"{pfad}: id {a.get('id')!r} passt nicht zum Dateinamen")
            if not a.get("typ"):
                raise ValueError(f"{pfad}: typ fehlt")
            anlagen.append(a)
        yield {**meta, "anlagen": anlagen, "_ordner": st_ordner.parent.name}


def falsch_einsortiert(datensaetze, kreis_von: KreisVon) -> list[tuple[str, str, str]]:
    """Sportstätten, die nicht im Ordner ihres Kreises liegen: [(id, ist, soll)]."""
    out = []
    for d in datensaetze:
        soll = _kreis(d, kreis_von)
        if d.get("_ordner") and d["_ordner"] != soll:
            out.append((d["id"], d["_ordner"], soll))
    return out
