"""Datenbestand im Git: ein Ordner je Kreis, darin ein Ordner je Sportstätte mit einer Datei
je Sportanlage.

    daten/RP/07111-koblenz/<id>/<id>_meta.json     die Sportstätte (Standort, Name …)
    daten/RP/07111-koblenz/<id>/<anlage-id>.json   je Sportanlage eine Datei

Die ID einer Sportstätte ist die UUID aus dem Atlas, ihr Ordner heißt wie sie. Der Ordner
des Kreises ergibt sich aus der Lage (Kreisschlüssel und Name, siehe `kreis_ordner`); liegt
eine Sportstätte in keinem Kreis, landet sie in `ohne-kreis`. Jede Sportanlage gehört über
`sportstaette_id` zu genau einer Sportstätte und liegt in deren Ordner; `lies_bestand`
prüft das. Ab der ersten Überführung sind diese Dateien die Quelle
der Daten. Änderungen laufen über das Git (z. B. Pull Requests); Quelldateien wie der
Atlas-Export werden mit `sportstaettenatlas bestand` eingelesen.

Neue Quellformate: eine Funktion `lies_<format>(pfad, land, umrechnen)` schreiben, die
Datensätze im Format unten liefert (Sportstätte mit Liste ihrer Anlagen), und in LESER
eintragen.

Sportstätte (`<id>_meta.json`, leere Angaben werden weggelassen):

    {
      "id": "333d6875-a691-492f-9c89-64bf3315706b",
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
      "quellen": {"atlas_rlp": {"id": "…", "datei": "…csv", "stand": "2026-11-04"}}
    }

Sportanlage (`<anlage-id>.json`):

    {
      "id": "8f0c…",                        UUID, aus Sportstätte und Typ abgeleitet
      "sportstaette_id": "333d6875-…",      Pflicht: die Sportstätte, zu der sie gehört
      "typ": "Großspielfeld",               einheitlicher Typ (siehe anlagen.py)
      "bezeichnung": "Kunstrasen B",        optional: eigener Name der Anlage
      "sportarten": ["Fußball"],            was auf dieser Anlage betrieben wird
      "baujahr": 1998,
      "baukosten_eur": 1200000,
      "ausstattung": ["Flutlicht", "Beregnung"],
      "quellen": {"atlas_rlp": {"bezeichnung": "Großspielfeld (ab 5.000 m²)"}}
    }

Die Sportarten der Sportstätte (aus dem Atlas) bleiben daneben bestehen: Der Atlas kennt sie
nur je Sportstätte, nicht je Anlage.

Kontaktdaten (E-Mail, Telefon) werden nie gelesen. Zusätzlich wird jeder Wert entfernt,
der eine E-Mail-Adresse enthält.
"""

from __future__ import annotations

import functools
import json
import re
import shutil
import uuid
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from . import anlagen as anlagen_typen
from .atlas import EXPORT_PFLICHT, _datum, _text, _utm, _zahl, _zeilen

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
    """ "A, B (x, y), C" → ["A", "B (x, y)", "C"]: Kommas in Klammern trennen nicht,
    "Weit-, Dreisprunganlage" bleibt eine Anlage."""
    return anlagen_typen.zusammenfuegen(re.split(r",\s*(?![^()]*\))", wert or ""))


def staette_id(quell_id: str) -> str:
    """ID einer Sportstätte (= Name ihres Ordners): die UUID aus der Quelle, bereinigt."""
    return re.sub(r"[^A-Za-z0-9_-]+", "-", str(quell_id)).strip("-").lower()


# feste Basis, damit dieselbe Anlage bei jedem Einlesen dieselbe ID bekommt
_ANLAGEN_NAMENSRAUM = uuid.UUID("5c1e0b8e-6d0a-4c57-9a43-2f1d6b0c7a11")


def anlage_id(staette: str, typ: str, nr: int) -> str:
    """ID einer Sportanlage: aus Sportstätte, Typ und laufender Nummer je Typ (1, 2 …)."""
    return str(uuid.uuid5(_ANLAGEN_NAMENSRAUM, f"{staette}/{typ}/{nr}"))


def anlagen_aus(bezeichnungen: list[str], quelle: str = "atlas_rlp") -> list[dict]:
    """Bezeichnungen aus einer Quelle → Sportanlagen mit einheitlichem Typ.

    Weicht die Schreibweise der Quelle vom Typ ab ("Großspielfeld (ab 5.000 m²)"), steht
    sie unter quellen.<quelle>.bezeichnung. Das Feld `bezeichnung` selbst bleibt für einen
    eigenen Namen der Anlage frei ("Halle 1", "Kunstrasen B").
    """
    out = []
    for b in anlagen_typen.zusammenfuegen(bezeichnungen):
        t = anlagen_typen.typ(b)
        out.append({"typ": t, **({"quellen": {quelle: {"bezeichnung": b}}} if b != t else {})})
    return out


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
            "id": staette_id(g("ID")),
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
            "anlagen": anlagen_aus(_liste(g("Sportanlagen"))),
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


OHNE_KREIS = "ohne-kreis"
KreisVon = Callable[[float, float], str]  # (lon, lat) → Name des Kreis-Ordners


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
    doppelt = {n for n in (k["name"] for k in kreise) if [x["name"] for x in kreise].count(n) > 1}
    namen = {}
    for k in kreise:
        name = _slug(k["name"])
        if k["name"] in doppelt and k.get("bez") == "Kreisfreie Stadt":
            name += "-stadt"
        namen[str(k["ars"])[:5]] = f"{str(k['ars'])[:5]}-{name}"
    zuordnung = Zuordnung(gebiete["gemeinde"])

    def ordner(lon: float, lat: float) -> str:
        ars = zuordnung.ars(lon, lat)
        return namen.get(ars[:5], OHNE_KREIS) if ars else OHNE_KREIS

    return ordner


def _kreis_von_daten(d: dict, kreis_von: KreisVon) -> str:
    lage = d.get("lage") or {}
    return kreis_von(lage.get("lon"), lage.get("lat"))


def staetten_ordner(land_ordner: Path) -> dict[str, Path]:
    """Alle Ordner von Sportstätten eines Landes: {id: Pfad} (über alle Kreise)."""
    return {p.name: p for p in sorted(land_ordner.glob("*/*")) if p.is_dir()}


def meta_datei(ordner: Path) -> Path:
    """<id>_meta.json im Ordner einer Sportstätte."""
    return ordner / f"{ordner.name}_meta.json"


def aufteilen(d: dict) -> dict[str, str]:
    """Sportstätte mit Anlagen → {Dateiname: Inhalt} für ihren Ordner."""
    sid = d["id"]
    meta = {k: v for k, v in d.items() if k not in ("anlagen", "_ordner")}
    dateien = {f"{sid}_meta.json": als_json(meta)}
    nr: Counter = Counter()
    for a in d.get("anlagen") or []:
        typ = a.get("typ") or anlagen_typen.typ(a.get("bezeichnung", ""))
        nr[typ] += 1
        aid = a.get("id") or anlage_id(sid, typ, nr[typ])
        rest = {k: v for k, v in a.items() if k not in ("id", "sportstaette_id", "typ")}
        dateien[f"{aid}.json"] = als_json({"id": aid, "sportstaette_id": sid, "typ": typ, **rest})
    return dateien


def _altes_format(ordner: Path) -> list[Path]:
    """Dateien früherer Formate: daten/RP/RP-<id>.json und daten/RP/<id>/ ohne Kreis."""
    dateien = sorted(Path(ordner).glob("*/*.json"))
    ohne_kreis = sorted(
        p.parent
        for p in Path(ordner).glob("*/*/*_meta.json")
        if p.name == f"{p.parent.name}_meta.json"
    )
    return dateien + ohne_kreis


def _pruefe_format(ordner: Path) -> None:
    if alt := _altes_format(ordner):
        raise ValueError(
            f"{len(alt)} Sportstätten im früheren Format (z. B. {alt[0]}). "
            "Einmalig umstellen: `sportstaettenatlas umstellen`."
        )


def schreibe_bestand(
    datensaetze, ziel: Path, land: str, kreis_von: KreisVon, modus: str = "neu"
) -> Ergebnis:
    """Datensätze als daten/<LAND>/<Kreis>/<id>/ ablegen (Sportstätte und ihre Anlagen).

    kreis_von: (lon, lat) → Ordner des Kreises (siehe kreis_ordner)

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
    _pruefe_format(ziel)
    vorhanden = staetten_ordner(ordner)
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
        dateien = aufteilen(d)
        if st_ordner is None:
            st_ordner = ordner / _kreis_von_daten(d, kreis_von) / d["id"]
            st_ordner.mkdir(parents=True)
            for name, text in dateien.items():
                (st_ordner / name).write_text(text, encoding="utf-8")
            e.neu += 1
        elif modus == "neu":
            e.behalten += 1
        else:
            geaendert = False
            for name, text in dateien.items():
                pfad = st_ordner / name
                if not pfad.exists() or pfad.read_text(encoding="utf-8") != text:
                    pfad.write_text(text, encoding="utf-8")
                    geaendert = True
            if geaendert:
                e.aktualisiert += 1
            else:
                e.unveraendert += 1
    e.nicht_mehr_in_quelle = len(set(vorhanden) - gesehen)
    return e


@dataclass
class Umstellung:
    umgestellt: int = 0  # aus einer Datei je Sportstätte (RP-<id>.json)
    verschoben: int = 0  # Ordner in den Ordner ihres Kreises gebracht
    anlagen: int = 0  # dabei als eigene Dateien angelegte Sportanlagen


def umstellen(ziel: Path, kreis_von: KreisVon) -> Umstellung:
    """Datenbestand ins aktuelle Format bringen; kann jederzeit wieder laufen.

    - daten/RP/RP-<id>.json (eine Datei je Sportstätte mit Liste "anlagen") → Ordner mit
      einer Datei je Anlage; von Hand gepflegte Angaben bleiben erhalten
    - Ordner einer Sportstätte, die nicht im Ordner ihres Kreises liegen (ohne Kreis-Ebene
      oder nach einer Änderung der Lage), werden dorthin verschoben
    """
    u = Umstellung()
    for land in sorted(p for p in Path(ziel).iterdir() if p.is_dir()):
        for alt in sorted(land.glob("*.json")):
            d = json.loads(alt.read_text(encoding="utf-8"))
            sid = staette_id(str(d.get("id") or alt.stem).removeprefix(f"{land.name}-"))
            d["id"] = sid
            bez = [a.get("bezeichnung", "") for a in d.get("anlagen") or []]
            d["anlagen"] = anlagen_aus(bez)
            st_ordner = land / _kreis_von_daten(d, kreis_von) / sid
            if st_ordner.exists():
                raise ValueError(
                    f"{st_ordner} gibt es schon – {alt} bitte von Hand zusammenführen."
                )
            st_ordner.mkdir(parents=True)
            for name, text in aufteilen(d).items():
                (st_ordner / name).write_text(text, encoding="utf-8")
            alt.unlink()
            u.umgestellt += 1
            u.anlagen += len(d["anlagen"])
        # Ordner von Sportstätten: direkt unter dem Land oder im falschen Kreis
        kandidaten = [p.parent for p in land.glob("*/*_meta.json")]
        kandidaten += [p.parent for p in land.glob("*/*/*_meta.json")]
        for st_ordner in sorted(kandidaten):
            meta = meta_datei(st_ordner)
            if not meta.exists():
                continue
            soll = land / _kreis_von_daten(_lies_json(meta), kreis_von) / st_ordner.name
            if soll != st_ordner:
                if soll.exists():
                    raise ValueError(f"{soll} gibt es schon – {st_ordner} bitte von Hand prüfen.")
                soll.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(st_ordner, soll)
                u.verschoben += 1
        for leer in land.iterdir():  # leere Kreis-Ordner
            if leer.is_dir() and not any(leer.iterdir()):
                leer.rmdir()
    return u


# daten/README.md: Aufbau und Datenmodell. Vorlage im Paket; bestand, umstellen und seite
# halten die Datei auf dem Stand der Vorlage (Änderungen also in daten_readme.md machen).
README_DATEN = resources.files("sportstaettenatlas").joinpath("daten_readme.md").read_text("utf-8")


def schreibe_readme(ziel: Path) -> bool:
    """daten/README.md aus der Vorlage schreiben, wenn sie fehlt oder veraltet ist."""
    pfad = Path(ziel) / "README.md"
    if pfad.exists() and pfad.read_text(encoding="utf-8") == README_DATEN:
        return False
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(README_DATEN, encoding="utf-8")
    return True


# --- Für die Webseite --------------------------------------------------------------------

# Angaben einer Sportanlage, die die Karte zeigt (neben Typ, Kennung und Name)
ANLAGE_FELDER = ("sportarten", "baujahr", "baukosten_eur", "ausstattung")

# Art des Betreibers bzw. Eigentümers, geschätzt aus dem Namen. Verein zuerst prüfen:
# "Turnverein Ortsgemeinde X e.V." ist ein Verein.
_VEREIN = re.compile(
    r"e\.\s?v\b|\be\s?v\.?$|\bev\b|verein|sportgemeinde|sportgemeinschaft|sportfreunde|"
    r"\b(tus|tsv|sv|fc|sc|sg|vfl|vfb|vfr|tv|tc|tsg|jsg|spvgg|fsv|ssv|djk|tura|dlrg|dav|"
    r"rv|rfv|lc|ltv|asv|esv|psv|bsv|hsv|msv|svg|tg|ttc|ttv|vsg|ksv|sgm)\b|"
    r"club|klub|schützen|gilde|alpenverein|kanu|ruder|turnerschaft|sportbund|sportkreis",
    re.IGNORECASE,
)
_KOMMUNE = re.compile(
    r"\b(orts|verbands|stadt)?gemeinde|\bstadt\b|städtisch|stadtverwaltung|"
    r"landkreis|kreisverwaltung|\bkreis\b|kommun|bürgermeister|\b(og|vg|vgv)\b|stadtwerk|"
    r"zweckverband|eigenbetrieb|^stadt|^gemeinde",
    re.IGNORECASE,
)
ARTEN = ("Verein", "Kommune", "sonstige")


def betreiber_art(name: str | None) -> str | None:
    """'Verein', 'Kommune' oder 'sonstige' – Schätzung aus dem Namen; None ohne Namen."""
    name = (name or "").strip()
    if not name:
        return None
    if _VEREIN.search(name):
        return "Verein"
    if _KOMMUNE.search(name):
        return "Kommune"
    return "sonstige"


def _adresse_text(a: dict) -> str:
    strasse = " ".join(x for x in (a.get("strasse"), a.get("hausnummer")) if x)
    ort = " ".join(x for x in (a.get("plz"), a.get("ort")) if x)
    return ", ".join(x for x in (strasse, ort) if x)


def _lies_json(datei: Path) -> dict:
    try:
        return json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{datei}: kein gültiges JSON ({exc})") from exc


def lies_bestand(ordner: Path) -> Iterator[dict]:
    """Alle Sportstätten unter daten/<LAND>/<Kreis>/<id>/, jeweils mit ihren Anlagen.

    Im Ergebnis steht zusätzlich "_ordner" (Kreis-Ordner), um die Einordnung zu prüfen.

    Prüft den Aufbau: Jeder Ordner hat seine <id>_meta.json, jede Anlage nennt in
    `sportstaette_id` die Sportstätte ihres Ordners, Dateiname = id.
    """
    _pruefe_format(ordner)
    for st_ordner in sorted(p for p in Path(ordner).glob("*/*/*") if p.is_dir()):
        sid = st_ordner.name
        meta_pfad = meta_datei(st_ordner)
        andere = sorted(p for p in st_ordner.glob("*.json") if p != meta_pfad)
        if not meta_pfad.exists():
            raise ValueError(
                f"{st_ordner}: {meta_pfad.name} fehlt – Sportanlagen ohne Sportstätte"
                + (f" ({len(andere)} Dateien)" if andere else "")
            )
        meta = _lies_json(meta_pfad)
        if meta.get("id") != sid:
            raise ValueError(f"{meta_pfad}: id {meta.get('id')!r} passt nicht zum Ordner {sid}")
        anlagen = []
        for pfad in andere:
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
        soll = _kreis_von_daten(d, kreis_von)
        if d.get("_ordner") and d["_ordner"] != soll:
            out.append((d["id"], d["_ordner"], soll))
    return out


def _anlage_kurz(a: dict) -> list:
    """Sportanlage für die Karte: [Typ, Kurz-ID, Name, {weitere Angaben}] – leere Teile am
    Ende entfallen. Die Kurz-ID (Anfang der UUID) genügt, um die Datei im Ordner der
    Sportstätte zu finden (Vorschläge zu Anlagen)."""
    extra = {k: a[k] for k in ANLAGE_FELDER if a.get(k) not in (None, "", [])}
    out = [
        a.get("typ") or anlagen_typen.typ(a.get("bezeichnung", "")),
        str(a.get("id", ""))[:8],
        a.get("bezeichnung") or "",
        extra,
    ]
    while len(out) > 2 and not out[-1]:
        out.pop()
    return out


def bestand_geojson(datensaetze, praezision: int = 5) -> dict:
    """Sportstätten → GeoJSON-Punkte für die Karte (flache Eigenschaften).

    `anlagen`: je Anlage [Typ, Kurz-ID, Name?, {Angaben}?] (siehe _anlage_kurz). Für den Filter
    stehen neben den Punkten die Gruppen der Typen (`anlagengruppen`, `anlagentypen`).
    """
    features = []
    typen: set[str] = set()
    reihe = {t: i for i, t in enumerate(anlagen_typen.GRUPPE_VON)}
    for d in datensaetze:
        lage = d.get("lage") or {}
        if lage.get("lon") is None or lage.get("lat") is None:
            continue
        a = d.get("adresse") or {}
        p = {
            "id": d.get("id"),
            "name": d.get("name"),
            "kategorie": d.get("kategorie"),
            "adresse": _adresse_text(a),
            "plz": a.get("plz"),
            "ort": a.get("ort"),
            "strasse": a.get("strasse"),
            "hausnummer": a.get("hausnummer"),
            "sportarten": d.get("sportarten") or [],
            "anlagen": [_anlage_kurz(a) for a in d.get("anlagen") or []],
            "oeffentlicher_zugang": d.get("oeffentlicher_zugang"),
            "schulsport": d.get("schulsport"),
            "zuschauerplaetze": d.get("zuschauerplaetze"),
            "betriebsstatus": d.get("betriebsstatus"),
            "betreiber": d.get("betreiber"),
            "betreiber_art": betreiber_art(d.get("betreiber")),
            "eigentuemer": d.get("eigentuemer"),
            "eigentuemer_art": betreiber_art(d.get("eigentuemer")),
            "website": d.get("website"),
        }
        p["anlagen"].sort(key=lambda a: (reihe.get(a[0], len(reihe)), a[0], a[1]))
        typen.update(a[0] for a in p["anlagen"])
        p = {k: v for k, v in p.items() if v not in (None, "", [])}
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        round(float(lage["lon"]), praezision),
                        round(float(lage["lat"]), praezision),
                    ],
                },
                "properties": p,
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "anlagengruppen": [[g, text] for g, (text, _) in anlagen_typen.GRUPPEN.items()],
        "anlagentypen": {t: anlagen_typen.gruppe(t) for t in sorted(typen)},
    }
