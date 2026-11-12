"""Statische Webseite für GitHub Pages bauen (Ordner docs/).

    docs/index.html                     Seite (Gerüst aus web/index.html)
    docs/app/                           Stil und Skripte (aus web/, bei jedem Lauf neu)
    docs/konfig.js                      Einstellungen – nur beim ersten Mal angelegt, danach
    docs/impressum.html, datenschutz.html   nie überschrieben (von Hand bzw. auf GitHub gepflegt)
    docs/daten/index.html               Download-Seite
    docs/daten/bestand.geojson          Datenbestand aus daten/ (Karte, Liste, Übersicht, Vorschlag)
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

from . import web

KONTAKT_FELDER = {
    "email",
    "email_quelle",
    "alt_email",
    "telefon",
    "telefon_quelle",
    "alt_telefon",
}
# Rohspalten des Atlas, die die Karte noch braucht (Suche, Verweis „Atlas: …“);
# alle anderen alt_* stecken schon in den zusammengeführten Feldern.
ATLAS_ROH_BEHALTEN = {"alt_bezug", "alt_name", "alt_adresse", "alt_typ", "alt_atlas_id", "alt_id"}
UEBERFLUESSIG = {"verifikation_sportstaette", "verifikation_anzahl"}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")

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


def oeffentlich(fc: dict) -> tuple[dict, Counter]:
    """Eigenschaften für die Veröffentlichung bereinigen. Liefert (GeoJSON, entfernte Felder)."""
    entfernt: Counter = Counter()
    for f in fc.get("features", []):
        p = f.get("properties") or {}
        neu = {}
        for k, v in p.items():
            if k in KONTAKT_FELDER:
                if v not in (None, ""):
                    entfernt[k] += 1
                continue
            if (k.startswith("alt_") and k not in ATLAS_ROH_BEHALTEN) or k in UEBERFLUESSIG:
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


def _alte_alkis_dateien(daten: Path) -> None:
    """Frühere Ablage der ALKIS-Dateien direkt in docs/daten/ → analysen/alkis/."""
    ziel = daten / "analysen" / "alkis"
    for name in ("sportstaetten.geojson", "sportanlagen.geojson", "atlas_abgleich.geojson"):
        alt = daten / name
        if alt.exists():
            ziel.mkdir(parents=True, exist_ok=True)
            if (ziel / name).exists():
                alt.unlink()
            else:
                shutil.move(alt, ziel / name)


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
              analysen.alkis.karte.webdaten. Fehlt eine Analyse, bleiben ihre Dateien aus
              einem früheren Lauf unverändert.
    ars_von:  (lon, lat) → Regionalschlüssel der Gemeinde, für Datensätze aus `bestand`
    """
    from . import gebiete as gb
    from .bestand import bestand_geojson

    ausgabe.mkdir(parents=True, exist_ok=True)
    daten = ausgabe / "daten"
    daten.mkdir(exist_ok=True)
    _alte_alkis_dateien(daten)

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

    index_pfad = daten / "analysen" / "index.json"
    verzeichnis = {
        a["name"]: a
        for a in (
            json.loads(index_pfad.read_text("utf-8"))["analysen"] if index_pfad.exists() else []
        )
        if (daten / "analysen" / a["name"]).is_dir()
    }
    if (daten / "analysen" / "alkis").is_dir() and "alkis" not in verzeichnis:
        verzeichnis["alkis"] = {"name": "alkis", "titel": "ALKIS-Abgleich", "dateien": {}}
    for name, (titel_a, dateien, texte) in (analysen or {}).items():
        ordner = daten / "analysen" / name
        if ordner.exists():
            shutil.rmtree(ordner)  # keine Reste früherer Läufe
        verzeichnis[name] = {"name": name, "titel": titel_a, "dateien": texte}
        for datei, inhalt in dateien.items():
            schreiben.append((f"analysen/{name}/{datei}", texte.get(datei, ""), inhalt))

    entfernt: Counter = Counter()
    liste = []
    for pfad, text, obj in schreiben:
        if "features" in obj:
            obj, weg = oeffentlich(obj)
            entfernt += weg
        (daten / pfad).parent.mkdir(parents=True, exist_ok=True)
        liste.append((pfad, text, _anzahl(obj), _schreibe_json(daten / pfad, obj)))
    if verzeichnis:
        index_pfad.parent.mkdir(parents=True, exist_ok=True)
        _schreibe_json(index_pfad, {"analysen": list(verzeichnis.values())})
    # Download-Liste: auch Dateien von Analysen, die diesmal nicht neu gerechnet wurden
    neu = {p for p, *_ in liste}
    for name, eintrag in verzeichnis.items():
        for datei in sorted((daten / "analysen" / name).glob("*.*json")):
            pfad = f"analysen/{name}/{datei.name}"
            if pfad not in neu:
                obj = json.loads(datei.read_text("utf-8"))
                text = eintrag.get("dateien", {}).get(datei.name, "")
                liste.append((pfad, text, _anzahl(obj), datei.stat().st_size))

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
