"""Datenbestand in daten/: Kreis / Sportstätte / Sportanlagen (Aufbau: daten/README.md).

    daten/RP/07111-koblenz/<id>/<id>_meta.json     die Sportstätte
    daten/RP/07111-koblenz/<id>/<anlage-id>.json   je Sportanlage eine Datei
    daten/organisationen/<id>.json                 je Organisation eine Datei

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

from .modell import (
    EMAIL_MUSTER,
    Organisation,
    Sportanlage,
    Sportstaette,
    migriere,
    ordne,
    pruefe,
)

EMAIL = re.compile(EMAIL_MUSTER)
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
    entfernt: Counter = field(default_factory=Counter)
    regelverstoesse: Counter = field(default_factory=Counter)  # Feld → Anzahl (modell.py)


MODI = ("neu", "ergaenzen", "aktualisieren")
NUR_ANLAGEN = "_nur_anlagen"  # Datensatz trägt nur Sportanlagen zu einer vorhandenen Sportstätte


def _staetten_ordner(land_ordner: Path) -> dict[str, Path]:
    return {p.name: p for p in sorted(land_ordner.glob("*/*")) if p.is_dir()}


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


def lies_bestand(ordner: Path, verstoesse: list | None = None) -> Iterator[dict]:
    """Alle Sportstätten unter daten/<LAND>/<Kreis>/<id>/, jeweils mit ihren Anlagen.

    Prüft den Aufbau: Jeder Ordner hat seine <id>_meta.json, jede Anlage nennt in
    `sportstaette_id` die Sportstätte ihres Ordners, Dateiname = id, typ ist gesetzt.
    Ein Fehler im Aufbau bricht ab (ValueError). Verstöße gegen die Regeln des Modells
    (modell.py, z. B. PLZ mit sechs Ziffern) brechen nicht ab, sondern landen als
    (Datei, Meldung) in `verstoesse`. Im Ergebnis steht zusätzlich "_ordner" (Kreis-Ordner).
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
            if verstoesse is not None:
                verstoesse += [(str(pfad), m) for m in pruefe(Sportanlage, a)]
            anlagen.append(a)
        if verstoesse is not None:
            verstoesse += [(str(meta_pfad), m) for m in pruefe(Sportstaette, meta)]
        yield {**meta, "anlagen": anlagen, "_ordner": st_ordner.parent.name}


def migriere_bestand(ordner: Path) -> int:
    """Dateien auf den Stand des Modells bringen (modell.migriere, z. B. umbenannte Felder).
    Liefert die Zahl der geänderten Dateien."""
    n = 0
    for pfad in sorted(Path(ordner).glob("*/*/*/*.json")):
        alt = pfad.read_text(encoding="utf-8")
        modell = Sportstaette if pfad.name.endswith("_meta.json") else Sportanlage
        neu = als_json(migriere(json.loads(alt), modell))
        if neu != alt:
            pfad.write_text(neu, encoding="utf-8")
            n += 1
    return n


def falsch_einsortiert(datensaetze, kreis_von: KreisVon) -> list[tuple[str, str, str]]:
    """Sportstätten, die nicht im Ordner ihres Kreises liegen: [(id, ist, soll)]."""
    out = []
    for d in datensaetze:
        soll = _kreis(d, kreis_von)
        if d.get("_ordner") and d["_ordner"] != soll:
            out.append((d["id"], d["_ordner"], soll))
    return out


# --- Verzeichnis der Organisationen (daten/organisationen/) -----------------------------

ORGANISATIONEN = "organisationen"
_ORG_NAMENSRAUM = uuid.UUID("a7d4c2e1-9f3b-4b8a-8c6d-1e5f0a2b3c4d")


def org_schluessel(name: str | None) -> str:
    """Name zum Vergleichen: klein, Leerzeichen vereinheitlicht (wie schluesselName im Web)."""
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


def organisation_id(name: str) -> str:
    """Feste ID aus dem Namen – für Organisationen, die aus dem Bestand angelegt werden."""
    return str(uuid.uuid5(_ORG_NAMENSRAUM, org_schluessel(name)))


def lies_organisationen(daten: Path, verstoesse: list | None = None) -> list[dict]:
    """Alle Organisationen aus daten/organisationen/<id>.json. Dateiname = id; ein Name
    (auch eine weitere Schreibweise) darf nur bei einer Organisation stehen."""
    out, namen = [], {}
    for pfad in sorted((Path(daten) / ORGANISATIONEN).glob("*.json")):
        o = _lies_json(pfad)
        if o.get("id") != pfad.stem:
            raise ValueError(f"{pfad}: id {o.get('id')!r} passt nicht zum Dateinamen")
        if verstoesse is not None:
            verstoesse += [(str(pfad), m) for m in pruefe(Organisation, o)]
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


def schreibe_organisation(daten: Path, o: dict) -> Path:
    """Eine Organisation als daten/organisationen/<id>.json (neue ID, wenn sie fehlt)."""
    o = {**o, "id": o.get("id") or str(uuid.uuid4())}
    pfad = Path(daten) / ORGANISATIONEN / f"{o['id']}.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(als_json(ordne(bereinigen(o, Counter()), Organisation)), encoding="utf-8")
    return pfad


ROLLEN = ("eigentuemer", "betreiber", "nutzer")


def organisationen_von(d: dict) -> list[tuple[str, str]]:
    """Organisationen einer Sportstätte: [(Rolle, Name)] – Eigentümer, Betreiber, Nutzer."""
    out = []
    for rolle in ROLLEN:
        werte = d.get(rolle) or []
        for name in [werte] if isinstance(werte, str) else werte:
            if (name or "").strip():
                out.append((rolle, name.strip()))
    return out


def organisationen_aus_bestand(bestand, daten: Path, typen: bool = False) -> int:
    """Für jeden Eigentümer, Betreiber und Nutzer im Bestand, der noch nicht im Verzeichnis steht,
    eine Organisation anlegen (Name in der häufigsten Schreibweise). typen=True übernimmt
    eine bei den Sportstätten angegebene Art, wenn sie dort einheitlich ist. Liefert die
    Zahl der neuen."""
    verzeichnis = org_verzeichnis(lies_organisationen(daten))
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
        schreibe_organisation(daten, o)
    return len(gefunden)


def schreibe_organisationen(datensaetze, daten: Path, modus: str = "neu") -> Ergebnis:
    """Organisationen (z. B. aus einer CSV) ins Verzeichnis übernehmen. Vorhandene findet
    die ID oder der Name (auch eine weitere Schreibweise); Modi wie bei schreibe_bestand."""
    if modus not in MODI:
        raise ValueError(f"Unbekannter Modus: {modus} (erlaubt: {', '.join(MODI)})")
    vorhanden = lies_organisationen(daten)
    nach_id = {o["id"]: o for o in vorhanden}
    verzeichnis = org_verzeichnis(vorhanden)
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
        schreibe_organisation(daten, neu)
        nach_id[neu["id"]] = neu
        verzeichnis.update(org_verzeichnis([neu]))
    return e
