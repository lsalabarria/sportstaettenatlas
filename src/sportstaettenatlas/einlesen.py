"""CSV-Dateien in den Datenbestand daten/ übernehmen (Befehl `bestand`).

`lies_csv` erkennt die Art der Tabelle (Atlas-Export, Sportstätten, Sportanlagen,
Sportkomplexe, Stützpunkte, Organisationen), ordnet die Spalten über das Modell zu (`spalten_namen`) und liest die
Werte nach dem Typ des Feldes (`wert`, mit werte.py). Geschrieben wird in bestand.py
(`schreibe_bestand`, `schreibe_sportkomplexe`, `schreibe_organisationen`). Die Regeln für Spalten, Werte und Modi
beschreibt daten/README.md („CSV einlesen“); `schreibe_vorlage` schreibt die Vorlagen.
"""

from __future__ import annotations

import csv
import functools
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import atlas, modell, werte
from .bestand import KONTAKT, NUR_ANLAGEN

_STAETTEN_NAMENSRAUM = uuid.UUID("0b6a1f63-3f7e-4f1a-9b55-6c2d9e8a4c21")
_KOMPLEX_NAMENSRAUM = uuid.UUID("6e2b9d14-7c3a-4f85-a1d0-3b8e5c7f9a42")
_STUETZPUNKT_NAMENSRAUM = uuid.UUID("a3f1c8e2-9d4b-4e7a-b6c5-2f8e1d0a9b37")
MITGLIEDER = "sportstaetten"  # Spalte der Sportkomplex-Tabelle: IDs ihrer Sportstätten
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
    art: str = ""  # atlas, sportstaetten, sportanlagen, sportkomplexe, stuetzpunkte, organisationen
    zeilen: int = 0
    spalten: dict[str, str] = field(default_factory=dict)  # Spalte → Feld
    ignoriert: list[str] = field(default_factory=list)  # Spalten ohne passendes Feld
    kontakt: list[str] = field(default_factory=list)  # Spalten mit Kontaktdaten, nicht gelesen
    nicht_lesbar: Counter = field(default_factory=Counter)  # Feld → Werte, die nicht passten
    bereinigt: Counter = field(default_factory=Counter)  # Feld → Werte, die werte.bereinige behob


# --- Spalten erkennen --------------------------------------------------------------------


@functools.cache
def _schema() -> dict:  # einmal je Lauf; nur gelesen
    return modell.schema()


def _eigenschaften(name: str) -> dict:
    return _schema()["$defs"][name]["properties"]


def _art(p: dict) -> dict:
    """Typ eines Feldes im Schema ohne „oder leer“."""
    return next((t for t in p.get("anyOf", [p]) if t.get("type") != "null"), p)


def spalten_namen(modellname: str) -> dict[str, str]:
    """Erkannte Spaltennamen (normalisiert) → Pfad des Feldes ("adresse.plz") für ein Modell.
    Feldnamen gehen vor Beschriftungen."""
    felder: list[tuple[str, dict]] = []
    for k, p in _eigenschaften(modellname).items():
        if k == "anlagen":
            continue
        ref = _art(p).get("$ref", "").rsplit("/", 1)[-1]
        if ref:
            felder += [(f"{k}.{k2}", p2) for k2, p2 in _eigenschaften(ref).items()]
        else:
            felder.append((k, p))
    namen: dict[str, str] = {}
    for stufe in ("feld", "titel"):
        for pfad, p in felder:
            if stufe == "feld":
                kandidaten = [pfad, pfad.split(".")[-1]] + list(_LAGE.get(pfad.split(".")[-1], ()))
            else:
                kandidaten = [p.get("title") or ""]
            for k in kandidaten:
                if _norm(k):
                    namen.setdefault(_norm(k), pfad)
    if modellname == "Sportstaette":
        for k in ("anlagen", "sportanlagen"):
            namen.setdefault(k, "anlagen")
    if modellname == "Sportkomplex":
        namen.setdefault(MITGLIEDER, MITGLIEDER)
    return namen


def _zaehler_spalte(modellname: str, spalte: str) -> tuple[str, str] | None:
    """Eine Spalte je Wert wie „felder_je_belag_sand“ → ("felder_je_belag", "Sand")."""
    for k, p in _eigenschaften(modellname).items():
        if p.get("widget") != "zaehler":
            continue
        praefix = _norm(k)
        if _norm(spalte).startswith(praefix):
            rest = _norm(spalte)[len(praefix) :]
            for w in p["propertyNames"]["enum"]:
                if _norm(w) == rest:
                    return k, w
    return None


# --- Werte -------------------------------------------------------------------------------


def _liste(text: str) -> list[str]:
    return [x.strip() for x in werte.liste(text) if x.strip()]


def wert(text: str, p: dict):
    """Text einer Zelle → Wert nach dem Feld des Modells (Regeln in werte.py). ValueError,
    wenn er nicht passt."""
    text = (text or "").strip()
    if not text:
        return None
    t = _art(p)
    if "enum" in t:
        if set(t["enum"]) == {"ja", "nein"}:
            return werte.ja_nein(text)
        for w in t["enum"]:
            if _norm(w) == _norm(text) or (
                isinstance(w, (int, float)) and werte.oder_none(werte.zahl, text) == w
            ):
                return w
        raise ValueError(text)
    if t.get("type") == "integer":
        return werte.ganzzahl(text)
    if t.get("type") == "number":
        return werte.zahl(text)
    if t.get("type") == "array":
        return _liste(text)
    if t.get("format") == "date":  # 31.12.2028 oder 2028-12-31
        if m := re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text):
            return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return text
        raise ValueError(text)
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


# --- Lesen -------------------------------------------------------------------------------


def _staette_id(name: str, lage: dict | None) -> str:
    """Feste ID für eine neue Sportstätte ohne ID: gleiche Zeile, gleiche ID."""
    schluessel = f"{_norm(name)}|{(lage or {}).get('lon')}|{(lage or {}).get('lat')}"
    return str(uuid.uuid5(_STAETTEN_NAMENSRAUM, schluessel))


def _komplex_id(name: str, adresse: dict | None) -> str:
    """Feste ID für einen neuen Sportkomplex ohne ID: aus Name und Ort."""
    a = adresse or {}
    schluessel = f"{_norm(name)}|{_norm(a.get('plz') or '')}|{_norm(a.get('ort') or '')}"
    return str(uuid.uuid5(_KOMPLEX_NAMENSRAUM, schluessel))


def lies_csv(pfad: Path, lage_aus=atlas.lage) -> tuple[list[dict], Bericht]:
    """CSV → Datensätze für bestand.schreibe_bestand, dazu ein Bericht.

    Sportstätten kommen mit ihren Feldern (und ggf. "anlagen"), Sportanlagen gebündelt je
    Sportstätte als {"id", "anlagen", NUR_ANLAGEN: True}."""
    pfad = Path(pfad)
    b = Bericht(pfad.name)
    zeilen = werte.zeilen(werte.text(pfad.read_bytes()))
    kopf = [k for k in (zeilen[0] if zeilen else {}) if k]  # ohne Überzählige (Schlüssel None)
    b.zeilen = len(zeilen)
    if atlas.PFLICHT <= set(kopf):
        b.art = "atlas"
        b.kontakt = [k for k in kopf if KONTAKT.search(k)]
        return list(atlas.lies_export(pfad, lage_aus)), b

    staetten_namen = spalten_namen("Sportstaette")
    normiert = {_norm(k) for k in kopf}
    ist_anlagen = {"sportstaetteid", "typ"} <= normiert or (
        "sportstaetteid" in normiert and "name" not in normiert
    )
    hat_staette = {staetten_namen.get(k) for k in normiert} & {"kategorie", "lage.lat", "lage.lon"}
    # Stützpunkte: Sportstätten bzw. Sportkomplexe und eine Art oder Gültigkeit
    ist_stp = (
        not ist_anlagen
        and normiert & {MITGLIEDER, "sportkomplexe"}
        and normiert & {"art", "gueltig_bis", "gueltig_ab"}
    )
    ist_komplex = not ist_anlagen and not ist_stp and MITGLIEDER in normiert
    ist_org = (
        not ist_anlagen
        and not ist_stp
        and not ist_komplex
        and not hat_staette
        and normiert & {"typ", "art"}
        and "name" in normiert
    )
    b.art = (
        "sportanlagen"
        if ist_anlagen
        else "stuetzpunkte"
        if ist_stp
        else "sportkomplexe"
        if ist_komplex
        else "organisationen"
        if ist_org
        else "sportstaetten"
    )
    modellname = {
        "sportanlagen": "Sportanlage",
        "sportkomplexe": "Sportkomplex",
        "stuetzpunkte": "Stuetzpunkt",
        "organisationen": "Organisation",
    }.get(b.art, "Sportstaette")
    namen = spalten_namen(modellname)
    if ist_anlagen:  # die Sportstätte steht nur in der Tabelle, in daten/ ist es der Ordner
        namen = {**namen, "sportstaetteid": "sportstaette_id", "sportstaette": "sportstaette_id"}
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
            if pfad_ == MITGLIEDER:
                d[MITGLIEDER] = _liste(text)
                continue
            if pfad_ == "sportstaette_id":
                d[pfad_] = text
                continue
            p = eigenschaft(pfad_)
            try:
                if schluessel:  # eine Spalte je Wert (alter Atlas): Zahl
                    d.setdefault(pfad_, {})[schluessel] = werte.ganzzahl(text)
                elif pfad_.startswith("lage."):
                    werte.setze(d, pfad_, werte.zahl(text))
                else:
                    werte.setze(d, pfad_, wert(text, p))
            except ValueError:
                b.nicht_lesbar[pfad_] += 1
                werte.setze(d, pfad_, text)  # bleibt, wie er ist; die Regeln melden ihn
        if not d:
            continue
        for feld in werte.bereinige(d):  # „6.0“ als Hausnummer, Webseite ohne https:// …
            b.bereinigt[feld] += 1
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
        if ist_stp:
            d.setdefault("id", str(uuid.uuid5(_STUETZPUNKT_NAMENSRAUM, _norm(d.get("name", "")))))
            datensaetze.append(d)
            continue
        if ist_komplex:
            d.setdefault("id", _komplex_id(d.get("name", ""), d.get("adresse")))
            datensaetze.append(d)
            continue
        d.setdefault("id", _staette_id(d.get("name", ""), d.get("lage")))
        datensaetze.append(d)
    datensaetze += [{"id": sid, "anlagen": a, NUR_ANLAGEN: True} for sid, a in je_staette.items()]
    return datensaetze, b


# --- Vorlage -----------------------------------------------------------------------------


def _vorlage_spalten(modellname: str) -> list[str]:
    out = []
    for k, p in _eigenschaften(modellname).items():
        ids = (
            "id",
            "sportstaette_id",
            "sportstaetten",
            "sportkomplexe",
        )  # IDs gehören in die Vorlage
        if k == "anlagen" or (p.get("formular") is False and k not in ids):
            continue
        ref = _art(p).get("$ref", "").rsplit("/", 1)[-1]
        out += list(_eigenschaften(ref)) if ref else [k]
    return (
        (["sportstaette_id"] if modellname == "Sportanlage" else [])
        + out
        + (["anlagen"] if modellname == "Sportstaette" else [])
        + ([MITGLIEDER] if modellname == "Sportkomplex" else [])
    )


def _zelle(v) -> str:
    if isinstance(v, list):
        return "; ".join(map(str, v))
    if isinstance(v, dict):
        return "; ".join(f"{k}: {n}" for k, n in v.items())
    return "" if v is None else str(v).replace(".", ",") if isinstance(v, float) else str(v)


def schreibe_vorlage(ordner: Path) -> list[Path]:
    """vorlage_sportstaetten.csv, _sportanlagen.csv, _sportkomplexe.csv, _stuetzpunkte.csv,
    _organisationen.csv: alle Spalten aus dem Modell und eine Beispielzeile; dazu
    vorlage_entfernen.csv (art, id, begruendung). Mit ; getrennt und mit BOM für Excel."""
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    beispiele = {
        "Sportstaette": {
            **modell.Sportstaette.model_config["json_schema_extra"]["examples"][0],
            "anlagen": ["Großspielfeld", "Rundlaufbahn"],
        },
        "Sportanlage": {
            "sportstaette_id": modell.Sportstaette.model_config["json_schema_extra"]["examples"][0][
                "id"
            ],
            **modell.Sportanlage.model_config["json_schema_extra"]["examples"][0],
        },
    }
    pfade = []
    beispiele["Organisation"] = modell.Organisation.model_config["json_schema_extra"]["examples"][0]
    beispiele["Stuetzpunkt"] = modell.Stuetzpunkt.model_config["json_schema_extra"]["examples"][0]
    beispiele["Sportkomplex"] = {
        **modell.Sportkomplex.model_config["json_schema_extra"]["examples"][0],
        MITGLIEDER: [
            modell.Sportstaette.model_config["json_schema_extra"]["examples"][0]["id"],
            "2b7e41d0",
        ],
    }
    for modellname, datei in (
        ("Sportstaette", "sportstaetten"),
        ("Sportanlage", "sportanlagen"),
        ("Sportkomplex", "sportkomplexe"),
        ("Stuetzpunkt", "stuetzpunkte"),
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
    from .entfernen import schreibe_vorlage as vorlage_entfernen

    pfade.append(vorlage_entfernen(ordner / "vorlage_entfernen.csv"))
    return pfade
