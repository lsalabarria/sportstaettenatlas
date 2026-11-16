"""CSV-Dateien in den Datenbestand daten/ übernehmen.

Erkannt werden drei Arten von Tabellen:

- **Export des bisherigen Atlas** (Spalten ID, Name, Sportstättenkategorie, …, Latitude,
  Longitude): liest atlas.lies_export.
- **Sportstätten**, eine Zeile je Sportstätte: Spalten wie die Felder von `Sportstaette`.
  Eine Spalte `anlagen` darf die Typen der Sportanlagen als Liste nennen.
- **Sportanlagen**, eine Zeile je Anlage: Spalten wie die Felder von `Sportanlage`, dazu
  `sportstaette_id` (Pflicht) und `id` (die UUID oder ihre ersten 8 Zeichen, für vorhandene
  Anlagen; neue ohne).
- **Organisationen** (Vereine, Kommunen, Verbände …), eine Zeile je Organisation: Spalten
  wie die Felder von `Organisation` – erkannt an `name` und `typ` bzw. „Art“ ohne Kategorie
  und Lage. Vorhandene findet die ID oder der Name.

Spaltennamen werden über das Modell erkannt, ohne Rücksicht auf Groß-/Kleinschreibung,
Umlaute und Satzzeichen: der Feldname (`plz` oder `adresse.plz`), die Beschriftung („PLZ“)
oder der Name im alten Atlas („postleitzahl“, „bodenbelag_anz_sand“). Werte:

    Listen               mit ; getrennt (ohne ; auch mit Komma): Fußball; Leichtathletik
    Anzahl je Wert       Sand: 3; Rasen: 1
    ja/nein              ja, nein (auch 1/0, x, true/false, wahr/falsch)
    Zahlen               12,5 oder 12.5; 1.200.000 oder 1200000
    Auswahl              wie im Modell, Groß-/Kleinschreibung egal
    Lage                 lat/lon in Grad (WGS84); UTM-Werte (EPSG:25832) werden umgerechnet

Spalten mit Kontaktdaten (E-Mail, Telefon, Ansprechpartner) werden nie gelesen. Die Vorlage
(`sportstaettenatlas vorlage`) schreibt beide Tabellen mit allen Spalten und einem Beispiel.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import atlas, modell
from .bestand import NUR_ANLAGEN

KONTAKT = re.compile(r"e-?mail|telefon|fax|mobil|handy|kontakt|ansprechpartner", re.IGNORECASE)
_STAETTEN_NAMENSRAUM = uuid.UUID("0b6a1f63-3f7e-4f1a-9b55-6c2d9e8a4c21")
# weitere übliche Namen für Spalten der Lage
_LAGE = {
    "lat": ("latitude", "breite", "y", "hochwert"),
    "lon": ("longitude", "lng", "x", "rechtswert"),
}


def _norm(text: str) -> str:
    t = str(text).lower().strip()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "", t)


@dataclass
class Bericht:
    """Was beim Einlesen einer Datei passiert ist (für die Ausgabe der Kommandozeile)."""

    datei: str
    art: str = ""  # "atlas", "sportstaetten", "sportanlagen" oder "organisationen"
    zeilen: int = 0
    spalten: dict[str, str] = field(default_factory=dict)  # Spalte → Feld
    ignoriert: list[str] = field(default_factory=list)  # Spalten ohne passendes Feld
    kontakt: list[str] = field(default_factory=list)  # Spalten mit Kontaktdaten, nicht gelesen
    nicht_lesbar: Counter = field(default_factory=Counter)  # Feld → Werte, die nicht passten


# --- Spalten erkennen --------------------------------------------------------------------


def _eigenschaften(name: str) -> dict:
    return modell.schema()["$defs"][name]["properties"]


def _art(p: dict) -> dict:
    """Typ eines Feldes im Schema ohne „oder leer“."""
    return next((t for t in p.get("anyOf", [p]) if t.get("type") != "null"), p)


def spalten_namen(modellname: str) -> dict[str, str]:
    """Erkannte Spaltennamen (normalisiert) → Pfad des Feldes ("adresse.plz") für ein Modell.
    Reihenfolge: Feldnamen vor Beschriftungen vor Namen im alten Atlas."""
    felder: list[tuple[str, dict]] = []
    for k, p in _eigenschaften(modellname).items():
        if k in ("quellen", "anlagen"):
            continue
        ref = _art(p).get("$ref", "").rsplit("/", 1)[-1]
        if ref:
            felder += [(f"{k}.{k2}", p2) for k2, p2 in _eigenschaften(ref).items()]
        else:
            felder.append((k, p))
    namen: dict[str, str] = {}
    for stufe in ("feld", "titel", "legacy"):
        for pfad, p in felder:
            if stufe == "feld":
                kandidaten = [pfad, pfad.split(".")[-1]] + list(_LAGE.get(pfad.split(".")[-1], ()))
            elif stufe == "titel":
                kandidaten = [p.get("title") or ""]
            else:
                legacy = re.sub(r"\s*\(.*\)", "", p.get("legacy") or "")
                kandidaten = [] if "*" in legacy else [legacy, legacy.split(".")[-1]]
            for k in kandidaten:
                if _norm(k):
                    namen.setdefault(_norm(k), pfad)
    if modellname == "Sportstaette":
        for k in ("anlagen", "sportanlagen"):
            namen.setdefault(k, "anlagen")
    return namen


def _zaehler_spalte(modellname: str, spalte: str) -> tuple[str, str] | None:
    """Spalte des alten Atlas wie „bodenbelag_anz_sand“ → ("felder_je_belag", "Sand")."""
    for k, p in _eigenschaften(modellname).items():
        legacy = p.get("legacy") or ""
        if p.get("widget") != "zaehler" or not legacy.endswith("*"):
            continue
        praefix = _norm(legacy[:-1])
        if _norm(spalte).startswith(praefix):
            rest = _norm(spalte)[len(praefix) :]
            for w in p["propertyNames"]["enum"]:
                if _norm(w) == rest:
                    return k, w
    return None


# --- Werte -------------------------------------------------------------------------------

_JA = {"ja", "j", "1", "x", "true", "wahr", "yes", "y"}
_NEIN = {"nein", "n", "0", "false", "falsch", "no"}


def _zahl(text: str) -> float:
    t = text.replace(" ", "").replace(" ", "")
    if "," in t and "." in t:  # 1.234,5 → 1234.5
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    elif t.count(".") > 1:  # 1.200.000
        t = t.replace(".", "")
    return float(t)


def _liste(text: str) -> list[str]:
    teile = text.split(";") if ";" in text else atlas._liste(text)
    return [x.strip() for x in teile if x.strip()]


def wert(text: str, p: dict):
    """Text einer Zelle → Wert nach dem Feld des Modells. ValueError, wenn er nicht passt."""
    text = (text or "").strip()
    if not text:
        return None
    t = _art(p)
    if "enum" in t:
        werte = t["enum"]
        if set(werte) == {"ja", "nein"}:
            if text.lower() in _JA:
                return "ja"
            if text.lower() in _NEIN:
                return "nein"
        for w in werte:
            if _norm(w) == _norm(text) or (isinstance(w, (int, float)) and _zahl_oder(text) == w):
                return w
        raise ValueError(text)
    if t.get("type") in ("integer", "number"):
        if t["type"] == "integer" and re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
            text = text.replace(".", "")  # 1.200 Plätze
        z = _zahl(text)
        if t["type"] == "integer":
            if z != int(z):
                raise ValueError(text)
            return int(z)
        return z
    if t.get("type") == "array":
        return _liste(text)
    if t.get("type") == "object":  # Anzahl je Wert: "Sand: 3; Rasen: 1" oder "3× Sand"
        erlaubt = t.get("propertyNames", {}).get("enum", [])
        out = {}
        for teil in _liste(text):
            m = re.fullmatch(r"(.+?)\s*[:=]\s*(\d+)", teil) or re.fullmatch(
                r"(\d+)\s*[x×]?\s*(.+)", teil
            )
            if not m:
                raise ValueError(teil)
            name, n = (m.group(1), m.group(2)) if not m.group(1).isdigit() else m.group(2, 1)
            schluessel = next((w for w in erlaubt if _norm(w) == _norm(name)), name.strip())
            out[schluessel] = int(n)
        return out
    return text


def _zahl_oder(text: str):
    try:
        return _zahl(text)
    except ValueError:
        return None


def _setze(d: dict, pfad: str, w) -> None:
    *vorne, letzt = pfad.split(".")
    for k in vorne:
        d = d.setdefault(k, {})
    d[letzt] = w


# --- Lesen -------------------------------------------------------------------------------


def _staette_id(name: str, lage: dict | None) -> str:
    """Feste ID für eine neue Sportstätte ohne ID: gleiche Zeile, gleiche ID."""
    schluessel = f"{_norm(name)}|{(lage or {}).get('lon')}|{(lage or {}).get('lat')}"
    return str(uuid.uuid5(_STAETTEN_NAMENSRAUM, schluessel))


def _stand(pfad: Path) -> str:
    """Datum aus dem Dateinamen (atlas._datum), sonst der Tag der letzten Änderung der Datei."""
    zeit = dt.datetime.fromtimestamp(pfad.stat().st_mtime, dt.UTC)
    return atlas._datum(pfad.name) or zeit.date().isoformat()


def lies_csv(pfad: Path, lage_aus=atlas.lage) -> tuple[list[dict], Bericht]:
    """CSV → Datensätze für bestand.schreibe_bestand, dazu ein Bericht.

    Sportstätten kommen mit ihren Feldern (und ggf. "anlagen"), Sportanlagen gebündelt je
    Sportstätte als {"id", "anlagen", NUR_ANLAGEN: True}."""
    pfad = Path(pfad)
    b = Bericht(pfad.name)
    zeilen = atlas._zeilen(atlas._text(pfad.read_bytes()))
    kopf = [k for k in (zeilen[0] if zeilen else {}) if k]  # ohne Überzählige (Schlüssel None)
    b.zeilen = len(zeilen)
    if atlas.PFLICHT <= set(kopf):
        b.art = "atlas"
        b.kontakt = [k for k in kopf if KONTAKT.search(k)]
        datensaetze = list(atlas.lies_export(pfad, lage_aus))
        stand = _stand(pfad)
        for d in datensaetze:  # ohne Datum im Dateinamen: Stand der Datei
            d["quellen"]["atlas_rlp"]["stand"] = d["quellen"]["atlas_rlp"]["stand"] or stand
        return datensaetze, b

    staetten_namen = spalten_namen("Sportstaette")
    normiert = {_norm(k) for k in kopf}
    ist_anlagen = {"sportstaetteid", "typ"} <= normiert or (
        "sportstaetteid" in normiert and "name" not in normiert
    )
    hat_staette = {staetten_namen.get(k) for k in normiert} & {"kategorie", "lage.lat", "lage.lon"}
    ist_org = (
        not ist_anlagen and not hat_staette and normiert & {"typ", "art"} and "name" in normiert
    )
    b.art = "sportanlagen" if ist_anlagen else "organisationen" if ist_org else "sportstaetten"
    modellname = {"sportanlagen": "Sportanlage", "organisationen": "Organisation"}.get(
        b.art, "Sportstaette"
    )
    namen = spalten_namen(modellname)
    zuordnung: dict[
        str, tuple[str, str | None]
    ] = {}  # Spalte → (Pfad, Schlüssel bei Anzahl je Wert)
    for k in kopf:
        if KONTAKT.search(k):
            b.kontakt.append(k)
        elif _norm(k) in namen:
            zuordnung[k] = (namen[_norm(k)], None)
        elif z := _zaehler_spalte(modellname, k):
            zuordnung[k] = z
        else:
            b.ignoriert.append(k)
    b.spalten = {k: p + (f"[{s}]" if s else "") for k, (p, s) in zuordnung.items()}
    if not ist_anlagen and not {"name", "id"} & {p for p, _ in zuordnung.values()}:
        raise ValueError(
            f"{pfad.name}: keine Spalte für den Namen oder die ID – Sportstätten brauchen "
            "mindestens name, kategorie, lat und lon; Sportanlagen sportstaette_id und typ"
        )

    def eigenschaft(pfad_: str) -> dict:
        teile = pfad_.split(".")
        p = _eigenschaften(modellname)[teile[0]]
        if len(teile) > 1:
            p = _eigenschaften(_art(p)["$ref"].rsplit("/", 1)[-1])[teile[1]]
        return p

    stand = _stand(pfad)
    datensaetze: list[dict] = []
    je_staette: dict[str, list[dict]] = {}
    for z in zeilen:
        d: dict = {}
        for spalte, (pfad_, schluessel) in zuordnung.items():
            text = (z.get(spalte) or "").strip()
            if not text:
                continue
            if pfad_ == "anlagen":
                d["anlagen"] = atlas.anlagen_aus(_liste(text))
                continue
            p = eigenschaft(pfad_)
            try:
                if schluessel:  # eine Spalte je Wert (alter Atlas): Zahl
                    d.setdefault(pfad_, {})[schluessel] = int(_zahl(text))
                elif pfad_.startswith("lage."):
                    _setze(d, pfad_, _zahl(text))
                else:
                    _setze(d, pfad_, wert(text, p))
            except ValueError:
                b.nicht_lesbar[pfad_] += 1
                _setze(d, pfad_, text)  # bleibt, wie er ist; die Regeln melden ihn
        if not d:
            continue
        if ist_org:
            datensaetze.append(d)
            continue
        if ist_anlagen:
            sid = str(d.pop("sportstaette_id", "") or "")
            if sid and d.get("typ"):
                je_staette.setdefault(sid, []).append(d)
            else:
                b.nicht_lesbar["sportstaette_id oder typ fehlt"] += 1
            continue
        lage = d.get("lage") or {}
        if isinstance(lage.get("lat"), float) and isinstance(lage.get("lon"), float):
            d["lage"] = lage_aus(lage["lat"], lage["lon"])
        elif lage:
            b.nicht_lesbar["lage"] += 1
            d.pop("lage")
        d.setdefault("id", _staette_id(d.get("name", ""), d.get("lage")))
        d["quellen"] = {"csv": {"datei": pfad.name, "stand": stand}}
        datensaetze.append(d)
    datensaetze += [{"id": sid, "anlagen": a, NUR_ANLAGEN: True} for sid, a in je_staette.items()]
    return datensaetze, b


# --- Vorlage -----------------------------------------------------------------------------


def _vorlage_spalten(modellname: str) -> list[str]:
    out = []
    for k, p in _eigenschaften(modellname).items():
        if k in ("quellen", "anlagen") or (
            p.get("formular") is False and k not in ("id", "sportstaette_id")
        ):
            continue
        ref = _art(p).get("$ref", "").rsplit("/", 1)[-1]
        out += list(_eigenschaften(ref)) if ref else [k]
    return out + (["anlagen"] if modellname == "Sportstaette" else [])


def _zelle(v) -> str:
    if isinstance(v, list):
        return "; ".join(map(str, v))
    if isinstance(v, dict):
        return "; ".join(f"{k}: {n}" for k, n in v.items())
    return "" if v is None else str(v).replace(".", ",") if isinstance(v, float) else str(v)


def schreibe_vorlage(ordner: Path) -> list[Path]:
    """vorlage_sportstaetten.csv, _sportanlagen.csv, _organisationen.csv: alle Spalten aus dem Modell
    und eine Beispielzeile. Mit ; getrennt und mit BOM, damit Excel sie richtig öffnet."""
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    beispiele = {
        "Sportstaette": {
            **modell.Sportstaette.model_config["json_schema_extra"]["examples"][0],
            "anlagen": ["Großspielfeld", "Rundlaufbahn"],
        },
        "Sportanlage": modell.Sportanlage.model_config["json_schema_extra"]["examples"][0],
    }
    pfade = []
    beispiele["Organisation"] = modell.Organisation.model_config["json_schema_extra"]["examples"][0]
    for modellname, datei in (
        ("Sportstaette", "sportstaetten"),
        ("Sportanlage", "sportanlagen"),
        ("Organisation", "organisationen"),
    ):
        spalten = _vorlage_spalten(modellname)
        b = beispiele[modellname]
        flach = {**b, **(b.get("adresse") or {}), **(b.get("lage") or {})}
        pfad = ordner / f"vorlage_{datei}.csv"
        with pfad.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(spalten)
            w.writerow([_zelle(flach.get(k)) for k in spalten])
        pfade.append(pfad)
    return pfade
