"""Datenbestand in daten/: Kreis / Sportstätte / Sportanlagen (Aufbau: daten/README.md).

    daten/RP/07111-koblenz/<id>/<id>_meta.json     die Sportstätte
    daten/RP/07111-koblenz/<id>/<anlage-id>.json   je Sportanlage eine Datei
    daten/RP/07111-koblenz/sportkomplexe/<id>.json je Sportkomplex eine Datei (nur wo es welche gibt)
    daten/organisationen/RP/<art>/<id>.json        je Organisation eine Datei, Ordner = Art

Felder, ihre Reihenfolge in den Dateien und die Regeln kommen aus modell.py. Werte mit einer
E-Mail-Adresse entfallen beim Schreiben (`bereinigen`).
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

from . import werte
from .modell import (
    EMAIL_MUSTER,
    KONTAKT_NAME,
    Organisation,
    Sportanlage,
    Sportkomplex,
    Sportstaette,
    Stuetzpunkt,
    ordne,
    pruefe,
)

EMAIL = re.compile(EMAIL_MUSTER)  # Werte mit E-Mail-Adresse
KONTAKT = re.compile(KONTAKT_NAME, re.IGNORECASE)  # Felder bzw. Spalten mit Kontaktdaten
OHNE_KREIS = "ohne-kreis"
# Sportstätten außerhalb von Rheinland-Pfalz (aus dem Altsystem): daten/outside/<Land>/<id>/,
# nicht auf der Webseite, nicht eingeordnet
OUTSIDE = "outside"
KreisVon = Callable[[float, float], str]  # (lon, lat) → Name des Kreis-Ordners

# feste Basis, damit dieselbe Anlage bei jedem Einlesen dieselbe ID bekommt
_ANLAGEN_NAMENSRAUM = uuid.UUID("5c1e0b8e-6d0a-4c57-9a43-2f1d6b0c7a11")


def adresse_text(a: dict) -> str:
    strasse = " ".join(x for x in (a.get("strasse"), a.get("hausnummer")) if x)
    ort = " ".join(x for x in (a.get("plz"), a.get("ort")) if x)
    return ", ".join(x for x in (strasse, ort) if x)


# --- Kreis-Ordner -----------------------------------------------------------------------


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
        ordner[str(k["ars"])[:5]] = f"{str(k['ars'])[:5]}-{werte.slug(k['name'])}" + (
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
            if not _leer(v):
                out[k] = v
        return out
    if isinstance(wert, list):
        liste = (bereinigen(v, entfernt, pfad) for v in wert)
        return [v for v in liste if not _leer(v)]
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
    dateien = {f"{sid}_meta.json": als_json(ordne(meta, Sportstaette))}
    nr: Counter = Counter()
    for a in d.get("anlagen") or []:
        nr[a["typ"]] += 1
        aid = a.get("id") or anlage_id(sid, a["typ"], nr[a["typ"]])
        dateien[f"{aid}.json"] = als_json(
            ordne({**a, "id": aid, "sportstaette_id": sid}, Sportanlage)
        )
    return dateien


@dataclass
class Ergebnis:
    neu: int = 0
    aktualisiert: int = 0
    unveraendert: int = 0
    behalten: int = 0  # vorhanden, im Modus "neu" nicht angefasst
    ohne_lage: int = 0
    ohne_sportstaette: int = 0  # Sportanlagen zu einer Sportstätte, die es nicht gibt
    doppelt: int = 0
    nicht_mehr_in_quelle: int = 0
    anlagen_neu: int = 0
    anlagen_geaendert: int = 0
    zugeordnet: int = 0  # Sportstätten, die einem Sportkomplex zugeordnet wurden
    entfernt: Counter = field(default_factory=Counter)
    regelverstoesse: Counter = field(default_factory=Counter)  # Feld → Anzahl (modell.py)


MODI = ("neu", "ergaenzen", "aktualisieren")
NUR_ANLAGEN = "_nur_anlagen"  # Datensatz trägt nur Sportanlagen zu einer vorhandenen Sportstätte


def _laender(daten: Path) -> list[Path]:
    """Ordner der Länder in daten/ (RP …), ohne die Verzeichnisse der Organisationen und der
    Stützpunkte."""
    return [
        p
        for p in sorted(Path(daten).glob("*"))
        if p.is_dir() and p.name not in (ORGANISATIONEN, STUETZPUNKTE)
    ]


STUETZPUNKTE = "stuetzpunkte"  # daten/stuetzpunkte/<id>.json


SPORTKOMPLEXE = "sportkomplexe"  # Ordner der Sportkomplexe in einem Kreis-Ordner


def _staetten_dirs(land_ordner: Path) -> list[Path]:
    """Ordner der Sportstätten eines Landes (<Kreis>/<id>/), ohne die der Sportkomplexe."""
    return [p for p in sorted(land_ordner.glob("*/*")) if p.is_dir() and p.name != SPORTKOMPLEXE]


def _staetten_ordner(land_ordner: Path) -> dict[str, Path]:
    return {p.name: p for p in _staetten_dirs(land_ordner)}


def _lies_ordner(st_ordner: Path) -> dict:
    """Sportstätte aus ihrem Ordner, mit Liste "anlagen"."""
    meta_pfad = st_ordner / f"{st_ordner.name}_meta.json"
    d = _lies_json(meta_pfad) if meta_pfad.exists() else {"id": st_ordner.name}
    d["anlagen"] = [_lies_json(p) for p in sorted(st_ordner.glob("*.json")) if p != meta_pfad]
    return d


def _leer(v) -> bool:
    return v in (None, "", [], {})


def _uebernimm(alt: dict, neu: dict, modus: str) -> dict:
    """Felder aus `neu` in `alt`: "aktualisieren" überschreibt, "ergaenzen" füllt nur leere.
    Leere Werte in `neu` heißen „keine Angabe“ und ändern nichts. Die Adresse wird feldweise
    zusammengeführt."""
    out = dict(alt)
    for k, v in neu.items():
        if _leer(v) or k in ("anlagen", NUR_ANLAGEN):
            continue
        if k == "adresse" and isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _uebernimm(out[k], v, modus)
        elif modus == "aktualisieren" or _leer(out.get(k)):
            out[k] = v
    return out


def _anlagen_zusammen(sid: str, alt: list[dict], neu: list[dict], modus: str, e: Ergebnis):
    """Sportanlagen der Quelle den vorhandenen zuordnen: über die ID (auch die Kurz-ID, den
    Anfang der UUID); ohne ID ist die n-te Anlage eines Typs in der Quelle die mit der ID
    anlage_id(Sportstätte, Typ, n) – so finden sich die Anlagen eines erneut eingelesenen
    Exports wieder. Vorhandene, die in der Quelle fehlen, bleiben."""
    nach_id = {a["id"]: a for a in alt}
    out = {a["id"]: a for a in alt}
    nr: Counter = Counter()
    for a in neu:
        nr[a.get("typ")] += 1
        roh = str(a.get("id") or "")
        treffer = [
            i for i in nach_id if roh and (i == roh or (len(roh) >= 8 and i.startswith(roh)))
        ]
        if len(treffer) == 1:
            aid = treffer[0]
        elif roh and len(roh) >= 32:  # vollständige, neue UUID
            aid = roh
        else:
            aid = anlage_id(sid, a.get("typ", ""), nr[a.get("typ")])
        a = {**a, "id": aid, "sportstaette_id": sid}
        if aid not in out:
            out[aid] = a
            e.anlagen_neu += 1
        elif modus != "neu":
            vorher = out[aid]
            out[aid] = _uebernimm(vorher, a, modus)
            e.anlagen_geaendert += out[aid] != vorher
    return list(out.values())


def schreibe_bestand(
    datensaetze, ziel: Path, land: str, kreis_von: KreisVon, modus: str = "neu"
) -> Ergebnis:
    """Sportstätten (mit Liste "anlagen") als daten/<LAND>/<Kreis>/<id>/ ablegen.

    modus="neu":           nur fehlende Sportstätten anlegen, vorhandene nie verändern
                           (sie können inzwischen von Hand gepflegt sein)
    modus="ergaenzen":     zusätzlich bei vorhandenen leere Felder füllen und fehlende
                           Sportanlagen anlegen; vorhandene Werte bleiben
    modus="aktualisieren": zusätzlich vorhandene Werte mit denen der Quelle überschreiben;
                           Felder, die die Quelle nicht hat oder leer lässt, bleiben
    Datensätze mit NUR_ANLAGEN (aus einer Tabelle von Sportanlagen) ergänzen die Anlagen
    einer vorhandenen Sportstätte; im Modus "neu" kommen nur neue Anlagen dazu.
    Gelöscht wird nie etwas: Sportstätten und Anlagen, die in der Quelle fehlen, bleiben.
    """
    if modus not in MODI:
        raise ValueError(f"Unbekannter Modus: {modus} (erlaubt: {', '.join(MODI)})")
    ordner = ziel / land.upper()
    ordner.mkdir(parents=True, exist_ok=True)
    vorhanden = _staetten_ordner(ordner)
    e = Ergebnis()
    gesehen: set[str] = set()
    ganze = False  # stehen ganze Sportstätten in der Quelle (nicht nur Anlagen)?
    for roh in datensaetze:
        d = bereinigen(roh, e.entfernt)
        nur_anlagen = bool(roh.get(NUR_ANLAGEN))
        ganze |= not nur_anlagen
        st_ordner = vorhanden.get(d.get("id", ""))
        if nur_anlagen and st_ordner is None:
            e.ohne_sportstaette += len(d.get("anlagen") or [])
            continue
        if not nur_anlagen and (not d.get("id") or (st_ordner is None and not d.get("lage"))):
            e.ohne_lage += 1
            continue
        if d["id"] in gesehen and not nur_anlagen:
            e.doppelt += 1
            continue
        gesehen.add(d["id"])
        neu = st_ordner is None
        if neu:
            st_ordner = ordner / _kreis(d, kreis_von) / d["id"]
            st_ordner.mkdir(parents=True)
            e.neu += 1
            ergebnis = {k: v for k, v in d.items() if k != NUR_ANLAGEN}
        elif modus == "neu" and not nur_anlagen:
            e.behalten += 1
            continue
        else:
            alt = _lies_ordner(st_ordner)
            ergebnis = alt if nur_anlagen else _uebernimm(alt, d, modus)
            ergebnis["anlagen"] = _anlagen_zusammen(
                d["id"], alt["anlagen"], d.get("anlagen") or [], modus, e
            )
        for meldung in pruefe(Sportstaette, {k: v for k, v in ergebnis.items() if k != "anlagen"}):
            e.regelverstoesse[meldung.split(":")[0]] += 1
        geaendert = False
        for name, text in aufteilen(ergebnis).items():
            pfad = st_ordner / name
            if not pfad.exists() or pfad.read_text(encoding="utf-8") != text:
                pfad.write_text(text, encoding="utf-8")
                geaendert = True
        if not neu:
            if geaendert:
                e.aktualisiert += 1
            else:
                e.unveraendert += 1
    if ganze:
        e.nicht_mehr_in_quelle = len(set(vorhanden) - gesehen)
    return e


def einordnen(ziel: Path, kreis_von: KreisVon) -> int:
    """Ordner von Sportstätten, die nicht im Ordner ihres Kreises liegen (z. B. nach einer
    Änderung der Lage), dorthin verschieben. Liefert die Zahl der verschobenen."""
    n = 0
    for meta in sorted(
        m
        for o in _laender(ziel)
        if o.name != OUTSIDE
        for p in _staetten_dirs(o)
        for m in p.glob("*_meta.json")
    ):
        st_ordner = meta.parent
        soll = st_ordner.parent.parent / _kreis(_lies_json(meta), kreis_von) / st_ordner.name
        if soll == st_ordner:
            continue
        if soll.exists():
            raise ValueError(f"{soll} gibt es schon – {st_ordner} bitte von Hand prüfen.")
        soll.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(st_ordner, soll)
        n += 1
    for leer in (k for o in _laender(ziel) for k in o.glob("*")):  # leer gewordene Kreise
        if leer.is_dir() and not any(leer.iterdir()):
            leer.rmdir()
    return n


# --- Lesen ------------------------------------------------------------------------------


def _lies_json(datei: Path) -> dict:
    try:
        return json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{datei}: kein gültiges JSON ({exc})") from exc


def lies_bestand(ordner: Path, verstoesse: list | None = None) -> Iterator[dict]:
    """Alle Sportstätten unter daten/<LAND>/<Kreis>/<id>/, jeweils mit ihren Anlagen.

    Prüft den Aufbau: Jeder Ordner hat seine <id>_meta.json, jede Anlage nennt in
    `sportstaette_id` die Sportstätte ihres Ordners, Dateiname = id, typ ist gesetzt.
    Ein Fehler im Aufbau bricht ab (ValueError). Verstöße gegen die Regeln des Modells
    (modell.py, z. B. PLZ mit sechs Ziffern) brechen nicht ab, sondern landen als
    (Datei, Meldung) in `verstoesse`. Im Ergebnis steht zusätzlich "_ordner" (Kreis-Ordner).
    """
    for st_ordner in sorted(p for o in _laender(ordner) for p in _staetten_dirs(o)):
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
            if verstoesse is not None:
                verstoesse += [(str(pfad), m) for m in pruefe(Sportanlage, a)]
            anlagen.append(a)
        if verstoesse is not None:
            verstoesse += [(str(meta_pfad), m) for m in pruefe(Sportstaette, meta)]
        yield {
            **meta,
            "anlagen": anlagen,
            "_ordner": st_ordner.parent.name,
            "_land": st_ordner.parent.parent.name,
        }


@dataclass
class Migration:
    dateien: int = 0  # geändert (oder mit probe: würden geändert)
    umbenannt: Counter = field(default_factory=Counter)
    entfernt: Counter = field(default_factory=Counter)
    konflikte: list = field(default_factory=list)  # (Datei, alt, neu): beide Namen belegt


def migriere_bestand(
    daten: Path,
    umbenennen: dict[str, str] | None = None,
    entfernen: set[str] | frozenset[str] = frozenset(),
    probe: bool = False,
) -> Migration:
    """Felder in allen Dateien von daten/ umbenennen ({alt: neu}) oder entfernen und die
    Schlüssel in die Reihenfolge des Modells bringen. Sportstätten, Sportanlagen und
    Organisationen; nur oberste Ebene. Steht der neue Name schon in einer Datei, bleibt sie
    für dieses Feld, wie sie ist (konflikte). Mit probe wird nichts geschrieben."""
    umbenennen = umbenennen or {}
    felder = {
        *Sportstaette.model_fields,
        *Sportanlage.model_fields,
        *Sportkomplex.model_fields,
        *Stuetzpunkt.model_fields,
        *Organisation.model_fields,
    }
    if fremd := sorted(set(umbenennen.values()) - felder):
        raise ValueError(f"nicht im Modell: {', '.join(fremd)}")
    e = Migration()
    daten = Path(daten)
    dateien = [
        *((p, Organisation) for p in org_dateien(daten)),
        *((p, Sportkomplex) for p in komplex_dateien(daten)),
        *((p, Stuetzpunkt) for p in stuetzpunkt_dateien(daten)),
        *(
            (p, Sportstaette if p.name.endswith("_meta.json") else Sportanlage)
            for p in sorted(
                x for o in _laender(daten) for d in _staetten_dirs(o) for x in d.glob("*.json")
            )
        ),
    ]
    for pfad, modell in dateien:
        alt = pfad.read_text(encoding="utf-8")
        d = json.loads(alt)
        for k in entfernen & d.keys():
            del d[k]
            e.entfernt[k] += 1
        for a, n in umbenennen.items():
            if a not in d:
                continue
            if n in d:
                e.konflikte.append((str(pfad), a, n))
                continue
            d = {n if k == a else k: v for k, v in d.items()}
            e.umbenannt[f"{a} → {n}"] += 1
        neu = als_json(ordne(d, modell))
        if neu != alt:
            e.dateien += 1
            if not probe:
                pfad.write_text(neu, encoding="utf-8")
    return e


def falsch_einsortiert(datensaetze, kreis_von: KreisVon) -> list[tuple[str, str, str]]:
    """Sportstätten, die nicht im Ordner ihres Kreises liegen: [(id, ist, soll)]."""
    out = []
    for d in datensaetze:
        if d.get("_land") == OUTSIDE:
            continue
        soll = _kreis(d, kreis_von)
        if d.get("_ordner") and d["_ordner"] != soll:
            out.append((d["id"], d["_ordner"], soll))
    return out


# --- Verzeichnis der Organisationen (daten/organisationen/<LAND>/<Ordner der Art>/) -------

ORGANISATIONEN = "organisationen"
ORG_LAND = "RP"


OHNE_ART = "ohne-art"


def org_pfad(daten: Path, o: dict) -> Path:
    """Wo eine Organisation hingehört: daten/organisationen/RP/<Art>/<id>.json. Der Ordner
    heißt wie die Art (z. B. „sportverein-im-lsb-rlp“, „ortsgemeinde“), ohne Art „ohne-art“."""
    art = werte.slug(o["typ"]) if o.get("typ") else OHNE_ART
    return Path(daten) / ORGANISATIONEN / ORG_LAND / art / f"{o['id']}.json"


def org_dateien(daten: Path) -> list[Path]:
    """Alle Dateien des Verzeichnisses (in jeder Tiefe, auch noch nicht einsortierte)."""
    return sorted((Path(daten) / ORGANISATIONEN).rglob("*.json"))


_ORG_NAMENSRAUM = uuid.UUID("a7d4c2e1-9f3b-4b8a-8c6d-1e5f0a2b3c4d")


def org_schluessel(name: str | None) -> str:
    """Name zum Vergleichen: klein, Leerzeichen vereinheitlicht (wie schluesselName im Web)."""
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


def organisation_id(name: str) -> str:
    """Feste ID aus dem Namen – für Organisationen, die aus dem Bestand angelegt werden."""
    return str(uuid.uuid5(_ORG_NAMENSRAUM, org_schluessel(name)))


def lies_organisationen(daten: Path, verstoesse: list | None = None) -> list[dict]:
    """Alle Organisationen aus daten/organisationen/. Dateiname = id; ein Name (auch eine
    weitere Schreibweise) darf nur bei einer Organisation stehen; der Ordner folgt aus der Art
    (sonst Verstoß; `einordnen` verschiebt)."""
    out, namen = [], {}
    for pfad in org_dateien(daten):
        o = _lies_json(pfad)
        if o.get("id") != pfad.stem:
            raise ValueError(f"{pfad}: id {o.get('id')!r} passt nicht zum Dateinamen")
        if verstoesse is not None:
            verstoesse += [(str(pfad), m) for m in pruefe(Organisation, o)]
            if pfad != org_pfad(daten, o):
                verstoesse.append((str(pfad), "Ordner passt nicht zur Art (einordnen)"))
            for n in [o.get("name"), *(o.get("weitere_namen") or [])]:
                k = org_schluessel(n)
                if k in namen and namen[k] != o["id"]:
                    verstoesse.append((str(pfad), f"name: „{n}“ steht auch bei {namen[k]}"))
                namen.setdefault(k, o["id"])
        out.append(o)
    return out


def org_verzeichnis(organisationen: list[dict]) -> dict[str, dict]:
    """Name und weitere Schreibweisen (org_schluessel) → Organisation."""
    out = {}
    for o in organisationen:
        for n in [o.get("name"), *(o.get("weitere_namen") or [])]:
            if n:
                out.setdefault(org_schluessel(n), o)
    return out


def schreibe_organisation(daten: Path, o: dict, dateien: dict[str, Path] | None = None) -> Path:
    """Eine Organisation in den Ordner ihrer Art schreiben (neue ID, wenn sie fehlt); liegt
    sie noch anderswo (Art geändert), wird die alte Datei entfernt. `dateien` (id → Pfad,
    wird mitgeführt) spart bei vielen Organisationen das Suchen."""
    o = {**o, "id": o.get("id") or str(uuid.uuid4())}
    pfad = org_pfad(daten, o)
    if dateien is None:
        dateien = {p.stem: p for p in org_dateien(daten)}
    if (alt := dateien.get(o["id"])) and alt != pfad:
        alt.unlink()
    dateien[o["id"]] = pfad
    pfad.parent.mkdir(parents=True, exist_ok=True)
    text = als_json(ordne(bereinigen(o, Counter()), Organisation))
    if not pfad.exists() or pfad.read_text(encoding="utf-8") != text:
        pfad.write_text(text, encoding="utf-8")
    return pfad


def finde_organisation(daten: Path, oid: str) -> Path | None:
    return next((p for p in org_dateien(daten) if p.stem == oid), None)


def organisationen_einordnen(daten: Path) -> int:
    """Organisationen in den Ordner ihrer Art verschieben; leere Ordner entfernen."""
    n = 0
    dateien = {p.stem: p for p in org_dateien(daten)}
    for pfad in list(dateien.values()):
        o = _lies_json(pfad)
        if pfad != org_pfad(daten, o):
            schreibe_organisation(daten, o, dateien)
            n += 1
    for ordner in sorted((Path(daten) / ORGANISATIONEN).rglob("*"), reverse=True):
        if ordner.is_dir() and not any(ordner.iterdir()):
            ordner.rmdir()
    return n


ROLLEN = ("eigentuemer", "betreiber", "nutzer")


def organisationen_von(d: dict) -> list[tuple[str, str]]:
    """Organisationen einer Sportstätte: [(Rolle, Name)] – Eigentümer, Betreiber, Nutzer."""
    out = []
    for rolle in ROLLEN:
        namen = d.get(rolle) or []
        for name in [namen] if isinstance(namen, str) else namen:
            if (name or "").strip():
                out.append((rolle, name.strip()))
    return out


def organisationen_aus_bestand(bestand, daten: Path, typen: bool = False) -> int:
    """Für jeden Eigentümer, Betreiber und Nutzer im Bestand, der noch nicht im Verzeichnis steht,
    eine Organisation anlegen (Name in der häufigsten Schreibweise). typen=True übernimmt
    eine bei den Sportstätten angegebene Art, wenn sie dort einheitlich ist. Liefert die
    Zahl der neuen."""
    verzeichnis = org_verzeichnis(lies_organisationen(daten))
    dateien = {p.stem: p for p in org_dateien(daten)}
    gefunden: dict[str, Counter] = {}
    arten: dict[str, set] = {}
    for d in bestand:
        for rolle, name in organisationen_von(d):
            k = org_schluessel(name)
            if k in verzeichnis:
                continue
            gefunden.setdefault(k, Counter())[re.sub(r"\s+", " ", name)] += 1
            if d.get(f"{rolle}_typ"):
                arten.setdefault(k, set()).add(d[f"{rolle}_typ"])
    for k, schreibweisen in gefunden.items():
        name = schreibweisen.most_common(1)[0][0]
        o = {"id": organisation_id(name), "name": name}
        if typen and len(arten.get(k, ())) == 1:
            o["typ"] = next(iter(arten[k]))
        schreibe_organisation(daten, o, dateien)
    return len(gefunden)


def schreibe_organisationen(datensaetze, daten: Path, modus: str = "neu") -> Ergebnis:
    """Organisationen (z. B. aus einer CSV) ins Verzeichnis übernehmen. Vorhandene findet
    die ID oder der Name (auch eine weitere Schreibweise); Modi wie bei schreibe_bestand."""
    if modus not in MODI:
        raise ValueError(f"Unbekannter Modus: {modus} (erlaubt: {', '.join(MODI)})")
    vorhanden = lies_organisationen(daten)
    nach_id = {o["id"]: o for o in vorhanden}
    verzeichnis = org_verzeichnis(vorhanden)
    dateien = {p.stem: p for p in org_dateien(daten)}
    e = Ergebnis()
    for roh in datensaetze:
        o = bereinigen(roh, e.entfernt)
        if not o.get("name") and not o.get("id"):
            continue
        alt = nach_id.get(o.get("id", "")) or verzeichnis.get(org_schluessel(o.get("name")))
        if alt is None:
            o.setdefault("id", organisation_id(o["name"]))
            neu = o
            e.neu += 1
        elif modus == "neu":
            e.behalten += 1
            continue
        else:
            neu = _uebernimm(alt, {**o, "id": alt["id"]}, modus)
            if neu == alt:
                e.unveraendert += 1
                continue
            e.aktualisiert += 1
        for meldung in pruefe(Organisation, neu):
            e.regelverstoesse[meldung.split(":")[0]] += 1
        schreibe_organisation(daten, neu, dateien)
        nach_id[neu["id"]] = neu
        verzeichnis.update(org_verzeichnis([neu]))
    return e


# --- Sportkomplexe (daten/<LAND>/<Kreis>/sportkomplexe/<id>.json) ----------------------


def komplex_dateien(daten: Path) -> list[Path]:
    return sorted(p for o in _laender(daten) for p in o.glob(f"*/{SPORTKOMPLEXE}/*.json"))


def lies_sportkomplexe(daten: Path, verstoesse: list | None = None) -> list[dict]:
    """Alle Sportkomplexe; im Ergebnis zusätzlich "_ordner" (Kreis-Ordner). Dateiname = id."""
    out = []
    for pfad in komplex_dateien(daten):
        k = _lies_json(pfad)
        if k.get("id") != pfad.stem:
            raise ValueError(f"{pfad}: id {k.get('id')!r} passt nicht zum Dateinamen")
        if verstoesse is not None:
            verstoesse += [(str(pfad), m) for m in pruefe(Sportkomplex, k)]
        out.append(
            {**k, "_ordner": pfad.parent.parent.name, "_land": pfad.parent.parent.parent.name}
        )
    return out


def komplex_kreis(k: dict, staetten: list[dict], kreis_von: KreisVon) -> str:
    """Kreis-Ordner eines Sportkomplexes: aus seiner Lage, sonst der häufigste Kreis-Ordner
    seiner Sportstätten (mit "_ordner" wie aus lies_bestand)."""
    if k.get("lage"):
        return _kreis(k, kreis_von)
    ordner = Counter(d["_ordner"] for d in staetten if d.get("sportkomplex") == k["id"])
    return ordner.most_common(1)[0][0] if ordner else OHNE_KREIS


def schreibe_sportkomplex(daten: Path, k: dict, kreis: str, land: str | None = None) -> Path:
    """Einen Sportkomplex in daten/<LAND>/<kreis>/sportkomplexe/ schreiben (neue ID, wenn sie
    fehlt); liegt er noch in einem anderen Kreis, wird die alte Datei entfernt. Ohne `land`:
    das bisherige ("_land" wie aus lies_sportkomplexe), sonst RP."""
    land = land or k.get("_land") or ORG_LAND
    k = {key: v for key, v in k.items() if key not in ("_ordner", "_land")}
    k["id"] = k.get("id") or str(uuid.uuid4())
    pfad = Path(daten) / land / kreis / SPORTKOMPLEXE / f"{k['id']}.json"
    for alt in komplex_dateien(daten):
        if alt.stem == k["id"] and alt != pfad:
            alt.unlink()
            if not any(alt.parent.iterdir()):
                alt.parent.rmdir()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    text = als_json(ordne(bereinigen(k, Counter()), Sportkomplex))
    if not pfad.exists() or pfad.read_text(encoding="utf-8") != text:
        pfad.write_text(text, encoding="utf-8")
    return pfad


def sportkomplexe_einordnen(daten: Path, kreis_von: KreisVon) -> int:
    """Sportkomplexe in den Ordner ihres Kreises verschieben (komplex_kreis)."""
    staetten = list(lies_bestand(daten))
    n = 0
    for k in lies_sportkomplexe(daten):
        if k["_land"] == OUTSIDE:
            continue
        soll = komplex_kreis(k, staetten, kreis_von)
        if soll != k["_ordner"]:
            schreibe_sportkomplex(daten, k, soll)
            n += 1
    return n


def finde_staette(daten: Path, sid: str) -> Path:
    """Ordner einer Sportstätte über ihre ID oder deren Anfang (mindestens 8 Zeichen)."""
    treffer = [
        p
        for o in _laender(daten)
        for p in _staetten_dirs(o)
        if p.name == sid or (len(sid) >= 8 and p.name.startswith(sid))
    ]
    if len(treffer) != 1:
        raise ValueError(f"Sportstätte {sid}: {'nicht gefunden' if not treffer else 'mehrdeutig'}")
    return treffer[0]


def ordne_sportkomplex_zu(daten: Path, komplex_id: str | None, ids: list[str]) -> list[Path]:
    """In den Sportstätten `ids` das Feld sportkomplex setzen (None: entfernen)."""
    geaendert = []
    for sid in ids:
        meta = finde_staette(daten, sid)
        meta = meta / f"{meta.name}_meta.json"
        d = _lies_json(meta)
        werte.setze(d, "sportkomplex", komplex_id)
        text = als_json(ordne(d, Sportstaette))
        if meta.read_text(encoding="utf-8") != text:
            meta.write_text(text, encoding="utf-8")
            geaendert.append(meta)
    return geaendert


def schreibe_sportkomplexe(
    datensaetze, daten: Path, kreis_von: KreisVon, modus: str = "neu"
) -> Ergebnis:
    """Sportkomplexe (z. B. aus einer CSV, mit Liste "sportstaetten": IDs oder ihr Anfang)
    übernehmen. Vorhandene findet die ID; Modi wie bei schreibe_bestand. Die genannten
    Sportstätten werden in jedem Modus zugeordnet (`sportkomplex`), herausgenommen wird keine.
    Der Kreis-Ordner folgt aus der Lage, sonst aus den Sportstätten (komplex_kreis)."""
    if modus not in MODI:
        raise ValueError(f"Unbekannter Modus: {modus} (erlaubt: {', '.join(MODI)})")
    vorhanden = {k["id"]: k for k in lies_sportkomplexe(daten)}
    e = Ergebnis()
    for roh in datensaetze:
        d = bereinigen(roh, e.entfernt)
        mitglieder = []
        for sid in d.pop("sportstaetten", []) or []:
            try:
                mitglieder.append(finde_staette(daten, str(sid)))
            except ValueError:
                e.ohne_sportstaette += 1
        alt = vorhanden.get(d.get("id", ""))
        if alt is None:
            k = d
            e.neu += 1
        elif modus == "neu":
            k = alt
            e.behalten += 1
        else:
            k = _uebernimm(alt, d, modus)
            if k == alt:
                e.unveraendert += 1
            else:
                e.aktualisiert += 1
        for meldung in pruefe(Sportkomplex, {x: v for x, v in k.items() if x != "_ordner"}):
            e.regelverstoesse[meldung.split(":")[0]] += 1
        if k.get("lage"):
            kreis = _kreis(k, kreis_von)
        elif mitglieder:
            kreise = Counter(p.parent.name for p in mitglieder)
            kreis = kreise.most_common(1)[0][0]
        else:
            kreis = (alt or {}).get("_ordner") or OHNE_KREIS
        if k is not alt or kreis != alt.get("_ordner"):
            schreibe_sportkomplex(daten, k, kreis)
        e.zugeordnet += len(ordne_sportkomplex_zu(daten, k["id"], [p.name for p in mitglieder]))
        vorhanden[k["id"]] = {**k, "_ordner": kreis}
    return e


# --- Stützpunkte (daten/stuetzpunkte/<id>.json) -------------------------------------------


def stuetzpunkt_dateien(daten: Path) -> list[Path]:
    return sorted((Path(daten) / STUETZPUNKTE).glob("*.json"))


def lies_stuetzpunkte(daten: Path, verstoesse: list | None = None) -> list[dict]:
    """Alle Stützpunkte (Dateiname = id)."""
    out = []
    for pfad in stuetzpunkt_dateien(daten):
        st = _lies_json(pfad)
        if st.get("id") != pfad.stem:
            raise ValueError(f"{pfad}: id {st.get('id')!r} passt nicht zum Dateinamen")
        if verstoesse is not None:
            verstoesse += [(str(pfad), m) for m in pruefe(Stuetzpunkt, st)]
        out.append(st)
    return out


def schreibe_stuetzpunkt(daten: Path, st: dict) -> Path:
    """Einen Stützpunkt schreiben (neue ID, wenn sie fehlt)."""
    st = dict(st)
    st["id"] = st.get("id") or str(uuid.uuid4())
    pfad = Path(daten) / STUETZPUNKTE / f"{st['id']}.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    text = als_json(ordne(bereinigen(st, Counter()), Stuetzpunkt))
    if not pfad.exists() or pfad.read_text(encoding="utf-8") != text:
        pfad.write_text(text, encoding="utf-8")
    return pfad


def loesche_stuetzpunkt(daten: Path, sid: str) -> bool:
    pfad = Path(daten) / STUETZPUNKTE / f"{sid}.json"
    if pfad.exists():
        pfad.unlink()
        return True
    return False


def _volle_ids(kurz: list, alle: list[str]) -> tuple[list[str], int]:
    """IDs oder ihr Anfang (ab 8 Zeichen) → volle IDs aus `alle`; dazu die Zahl unbekannter."""
    out, unbekannt = [], 0
    for k in kurz or []:
        k = str(k).strip()
        treffer = [i for i in alle if i == k or (len(k) >= 8 and i.startswith(k))]
        if len(treffer) != 1:
            unbekannt += 1
        elif treffer[0] not in out:
            out.append(treffer[0])
    return out, unbekannt


def schreibe_stuetzpunkte(datensaetze, daten: Path, modus: str = "neu") -> Ergebnis:
    """Stützpunkte (z. B. aus einer CSV) übernehmen. "sportstaetten" und "sportkomplexe" dürfen
    den Anfang einer ID enthalten; unbekannte werden übersprungen (ohne_sportstaette). Vorhandene
    findet die ID; Modi wie bei schreibe_bestand (Listen werden im Modus aktualisieren ersetzt)."""
    if modus not in MODI:
        raise ValueError(f"Unbekannter Modus: {modus} (erlaubt: {', '.join(MODI)})")
    vorhanden = {x["id"]: x for x in lies_stuetzpunkte(daten)}
    staetten = [p.name for o in _laender(daten) for p in _staetten_dirs(o)]
    komplexe = [p.stem for p in komplex_dateien(daten)]
    e = Ergebnis()
    for roh in datensaetze:
        d = bereinigen(roh, e.entfernt)
        for feld, alle in (("sportstaetten", staetten), ("sportkomplexe", komplexe)):
            if feld in d:
                d[feld], n = _volle_ids(d[feld], alle)
                e.ohne_sportstaette += n
        alt = vorhanden.get(d.get("id", ""))
        if alt is None:
            st = d
            e.neu += 1
        elif modus == "neu":
            e.behalten += 1
            continue
        else:
            st = _uebernimm(alt, d, modus)
            if st == alt:
                e.unveraendert += 1
                continue
            e.aktualisiert += 1
        for meldung in pruefe(Stuetzpunkt, st):
            e.regelverstoesse[meldung.split(":")[0]] += 1
        schreibe_stuetzpunkt(daten, st)
        vorhanden[st["id"]] = st
    return e
