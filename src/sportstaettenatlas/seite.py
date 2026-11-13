"""Statische Webseite für GitHub Pages bauen (Ordner docs/).

    docs/index.html                     Seite (Gerüst aus web/index.html)
    docs/app/                           Stil und Skripte (aus web/, bei jedem Lauf neu)
    docs/konfig.js                      Einstellungen – nur beim ersten Mal angelegt, danach
    docs/impressum.html, datenschutz.html   nie überschrieben (von Hand bzw. auf GitHub gepflegt)
    docs/daten/index.html               Download-Seite
    docs/daten/bestand.geojson          Datenbestand aus daten/ (bestand_geojson)
    docs/daten/gebiete.json,            Kreise, Verbandsgemeinden, Gemeinden zur Auswahl
    docs/daten/gebiete_*.geojson        (Umrisse werden erst bei Bedarf geladen)
    docs/daten/analysen/index.json      Verzeichnis der Analysen (Reiter „Analysen“)
    docs/daten/analysen/<name>/         Dateien einer Analyse, z. B. alkis/ (lädt erst beim Öffnen)
    docs/vendor/leaflet/                Kartenbibliothek, lokal (keine Anfragen an Dritt-CDNs)
    docs/.nojekyll                      GitHub Pages soll die Dateien unverändert ausliefern

Kontaktdaten (E-Mail, Telefon) werden nicht veröffentlicht. Zusätzlich wird jeder Wert,
der eine E-Mail-Adresse enthält, entfernt.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import shutil
import urllib.request
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from . import anlagen as anlagen_typen
from . import web
from .bestand import EMAIL, adresse_text

KONTAKT_FELDER = {"email", "email_quelle", "alt_email", "telefon", "telefon_quelle", "alt_telefon"}

LEAFLET_DATEIEN = (
    "leaflet.js",
    "leaflet.css",
    "images/layers.png",
    "images/layers-2x.png",
    "images/marker-icon.png",
    "images/marker-icon-2x.png",
    "images/marker-shadow.png",
)
VON_HAND = ("konfig.js", "impressum.html", "datenschutz.html")  # nie überschreiben


# --- Datenbestand für die Karte ---------------------------------------------------------

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
# Angaben einer Sportanlage, die die Karte zeigt (neben Typ, Kennung und Name)
ANLAGE_FELDER = ("sportarten", "baujahr", "baukosten_eur", "ausstattung")


def betreiber_art(name: str | None) -> str | None:
    """'Verein', 'Kommune' oder 'sonstige' – Schätzung aus dem Namen; None ohne Namen."""
    name = (name or "").strip()
    if not name:
        return None
    if _VEREIN.search(name):
        return "Verein"
    return "Kommune" if _KOMMUNE.search(name) else "sonstige"


def _anlage_kurz(a: dict) -> list:
    """Sportanlage für die Karte: [Typ, Kurz-ID, Name, {Angaben}]; leere Teile am Ende
    entfallen. Die Kurz-ID (Anfang der UUID) genügt, um die Datei zu finden."""
    extra = {k: a[k] for k in ANLAGE_FELDER if a.get(k) not in (None, "", [])}
    out = [a["typ"], str(a.get("id", ""))[:8], a.get("bezeichnung") or "", extra]
    while len(out) > 2 and not out[-1]:
        out.pop()
    return out


def bestand_geojson(datensaetze, praezision: int = 5) -> dict:
    """Sportstätten → GeoJSON-Punkte (flache Eigenschaften, Anlagen als Liste) und die
    Gruppen der Anlagentypen für den Filter (`anlagengruppen`, `anlagentypen`)."""
    features = []
    typen: set[str] = set()
    reihe = {t: i for i, t in enumerate(anlagen_typen.GRUPPE_VON)}
    for d in datensaetze:
        lage = d.get("lage") or {}
        if lage.get("lon") is None or lage.get("lat") is None:
            continue
        a = d.get("adresse") or {}
        anlagen = sorted(
            (_anlage_kurz(x) for x in d.get("anlagen") or []),
            key=lambda x: (reihe.get(x[0], len(reihe)), x[0], x[1]),
        )
        typen.update(x[0] for x in anlagen)
        p = {
            "id": d.get("id"),
            "name": d.get("name"),
            "kategorie": d.get("kategorie"),
            "adresse": adresse_text(a),
            "plz": a.get("plz"),
            "ort": a.get("ort"),
            "strasse": a.get("strasse"),
            "hausnummer": a.get("hausnummer"),
            "sportarten": d.get("sportarten") or [],
            "anlagen": anlagen,
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
        punkt = [round(float(lage["lon"]), praezision), round(float(lage["lat"]), praezision)]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": punkt},
                "properties": {k: v for k, v in p.items() if v not in (None, "", [])},
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "anlagengruppen": [[g, text] for g, (text, _) in anlagen_typen.GRUPPEN.items()],
        "anlagentypen": {t: anlagen_typen.gruppe(t) for t in sorted(typen)},
    }


# --- Veröffentlichen --------------------------------------------------------------------


def oeffentlich(fc: dict) -> tuple[dict, Counter]:
    """Kontaktdaten und Werte mit E-Mail-Adresse entfernen. Liefert (GeoJSON, entfernt)."""
    entfernt: Counter = Counter()
    for f in fc.get("features", []):
        p = f.get("properties") or {}
        neu = {}
        for k, v in p.items():
            if k in KONTAKT_FELDER:
                if v not in (None, ""):
                    entfernt[k] += 1
                continue
            if isinstance(v, str) and EMAIL.search(v):
                entfernt[f"E-Mail-Adresse in „{k}“"] += 1
                continue
            neu[k] = v
        f["properties"] = neu
    return fc, entfernt


def leaflet_lokal(ziel: Path, version_url: str = web.LEAFLET) -> bool:
    """Leaflet einmalig nach docs/vendor/leaflet laden. True, wenn danach vorhanden."""
    if all((ziel / d).exists() for d in LEAFLET_DATEIEN):
        return True
    try:
        for d in LEAFLET_DATEIEN:
            pfad = ziel / d
            pfad.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(f"{version_url}/{d}", timeout=30) as r:
                pfad.write_bytes(r.read())
        return True
    except OSError:
        return False


def _groesse(n: int) -> str:
    return f"{n / 1e6:.1f} MB" if n >= 1e5 else f"{n / 1e3:.0f} kB"


def _schreibe_json(pfad: Path, obj: dict) -> int:
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    pfad.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def download_seite(
    titel: str, quellenvermerk: str, dateien: list[tuple[str, str, int, int]]
) -> str:
    zeilen = "".join(
        f'<tr><td><a href="{html.escape(name)}" download>{html.escape(name)}</a></td>'
        f"<td>{html.escape(text)}</td>"
        f"<td>{'–' if anzahl is None else f'{anzahl:,}'.replace(',', '.')}</td>"
        f"<td>{_groesse(groesse)}</td></tr>"
        for name, text, anzahl, groesse in dateien
    )
    return (
        web.datei("vorlagen/daten.html")
        .replace("__TITEL__", html.escape(titel))
        .replace("__STAND__", dt.datetime.now(dt.UTC).strftime("%d.%m.%Y"))
        .replace("__ZEILEN__", zeilen)
        .replace("__VERMERK_JS__", web.einbetten(quellenvermerk))
        .replace("__VERMERK__", html.escape(quellenvermerk) or "–")
    )


def _anzahl(obj) -> int | None:
    """Zahl der Objekte für die Download-Seite (None: keine Liste, z. B. eine Zusammenfassung)."""
    for schluessel in ("features", "eintraege"):
        if isinstance(obj.get(schluessel), list):
            return len(obj[schluessel])
    return None


def _analysen(ordner: Path, analysen: dict) -> tuple[dict, list[tuple[str, str, dict]]]:
    """Verzeichnis der Analysen (für index.json) und ihre Dateien (Pfad, Beschreibung, Inhalt).

    Analysen aus früheren Läufen bleiben im Verzeichnis, solange ihr Ordner existiert;
    der Ordner einer neu gerechneten Analyse wird vorher geleert.
    """
    index = ordner / "index.json"
    frueher = json.loads(index.read_text("utf-8"))["analysen"] if index.exists() else []
    verzeichnis = {a["name"]: a for a in frueher if (ordner / a["name"]).is_dir()}
    dateien = []
    for name, (titel, inhalte, texte) in analysen.items():
        if (ordner / name).exists():
            shutil.rmtree(ordner / name)  # keine Reste früherer Läufe
        verzeichnis[name] = {"name": name, "titel": titel, "dateien": texte}
        for datei, inhalt in inhalte.items():
            dateien.append((f"analysen/{name}/{datei}", texte.get(datei, ""), inhalt))
    return verzeichnis, dateien


def _fruehere_analysen(ordner: Path, verzeichnis: dict, neu: set[str]) -> list[tuple]:
    """Zeilen der Download-Liste für Dateien von Analysen, die diesmal nicht neu gerechnet
    wurden."""
    zeilen = []
    for name, eintrag in verzeichnis.items():
        for datei in sorted((ordner / name).glob("*.*json")):
            pfad = f"analysen/{name}/{datei.name}"
            if pfad not in neu:
                obj = json.loads(datei.read_text("utf-8"))
                text = eintrag.get("dateien", {}).get(datei.name, "")
                zeilen.append((pfad, text, _anzahl(obj), datei.stat().st_size))
    return zeilen


def schreibe_webseite(
    ausgabe: Path,
    bestand: list[dict] | None = None,
    gebiete: dict | None = None,
    analysen: dict[str, tuple[str, dict, dict]] | None = None,
    ars_von: Callable | None = None,
    quellenvermerk: str = "",
    titel: str = "Sportstättenatlas Rheinland-Pfalz",
    leaflet_laden: bool = True,
) -> dict:
    """Webseite nach `ausgabe` (z. B. docs/) schreiben. Liefert eine kleine Statistik.

    bestand:  Datensätze aus daten/ (bestand.lies_bestand)
    gebiete:  Verwaltungsgebiete (gebiete.lade) für die Gebietsauswahl
    analysen: {Name: (Titel, {Datei: Inhalt}, {Datei: Beschreibung})}, z. B. aus
              analysen.alkis.webdaten. Fehlt eine Analyse, bleiben ihre Dateien aus
              einem früheren Lauf unverändert.
    ars_von:  (lon, lat) → Regionalschlüssel der Gemeinde, für Datensätze aus `bestand`
    """
    from . import gebiete as gb

    ausgabe.mkdir(parents=True, exist_ok=True)
    daten = ausgabe / "daten"
    daten.mkdir(exist_ok=True)

    # (Pfad unter daten/, Beschreibung, Inhalt)
    schreiben: list[tuple[str, str, dict]] = []
    if bestand is not None:
        fc = bestand_geojson(bestand)
        if ars_von:
            for f in fc["features"]:
                if ars := ars_von(*f["geometry"]["coordinates"]):
                    f["properties"]["ars"] = ars
        schreiben.append(("bestand.geojson", "Sportstätten (Datenbestand des Atlas)", fc))
    if gebiete:
        schreiben.append(
            (
                "gebiete.json",
                "Verzeichnis der Gebiete (Auswahlliste)",
                {"eintraege": gb.index(gebiete)},
            )
        )
        for ebene in gb.EBENEN:
            schreiben.append(
                (
                    f"gebiete_{ebene}.geojson",
                    f"Umrisse: {gb.EBENEN_TEXT[ebene]} (VG250, BKG)",
                    gb.umrisse(gebiete, ebene),
                )
            )
    elif (daten / "gebiete.json").exists():
        (daten / "gebiete.json").unlink()  # sonst zeigt die Karte eine veraltete Auswahl

    verzeichnis, analyse_dateien = _analysen(daten / "analysen", analysen or {})
    schreiben += analyse_dateien

    entfernt: Counter = Counter()
    liste = []
    for pfad, text, obj in schreiben:
        if "features" in obj:
            obj, weg = oeffentlich(obj)
            entfernt += weg
        (daten / pfad).parent.mkdir(parents=True, exist_ok=True)
        liste.append((pfad, text, _anzahl(obj), _schreibe_json(daten / pfad, obj)))
    if verzeichnis:
        (daten / "analysen").mkdir(exist_ok=True)
        _schreibe_json(daten / "analysen" / "index.json", {"analysen": list(verzeichnis.values())})
    liste += _fruehere_analysen(daten / "analysen", verzeichnis, {p for p, *_ in liste})

    lokal = leaflet_laden and leaflet_lokal(ausgabe / "vendor" / "leaflet")
    web.kopiere_app(ausgabe / "app")
    (ausgabe / "index.html").write_text(
        web.html_seite(titel, quellenvermerk, leaflet="vendor/leaflet" if lokal else web.LEAFLET),
        encoding="utf-8",
    )
    neu_angelegt = []
    for name in VON_HAND:
        if not (ausgabe / name).exists():
            (ausgabe / name).write_text(web.vorlage(name, titel), encoding="utf-8")
            neu_angelegt.append(name)
    (daten / "index.html").write_text(
        download_seite(titel, quellenvermerk, liste), encoding="utf-8"
    )
    (ausgabe / ".nojekyll").write_text("", encoding="utf-8")
    return {
        "dateien": liste,
        "entfernt": dict(entfernt),
        "leaflet_lokal": lokal,
        "neu_angelegt": neu_angelegt,
        "gesamt": sum(f.stat().st_size for f in ausgabe.rglob("*") if f.is_file()),
    }
