"""Statische Webseite für GitHub Pages bauen (Ordner docs/).

    docs/index.html                     Seite (Gerüst aus web/index.html)
    docs/app/                           Stil und Skripte (aus web/, bei jedem Lauf neu)
    docs/konfig.js                      Einstellungen; wie Impressum und Datenschutz von Hand
    docs/impressum.html, datenschutz.html   gepflegt in webseite/ und von dort kopiert
    docs/daten/index.html               Download-Seite
    docs/daten/bestand.geojson          Datenbestand aus daten/ (bestand_geojson)
    docs/daten/gebiete.json,            Kreise, Verbandsgemeinden, Gemeinden zur Auswahl
    docs/daten/gebiete_*.geojson        (Umrisse werden erst bei Bedarf geladen)
    docs/daten/analysen/index.json      Verzeichnis der Analysen (Reiter „Analysen“)
    docs/daten/analysen/<name>/         Dateien einer Analyse, z. B. alkis/ (lädt erst beim Öffnen),
                                        aus webseite/analysen/<name>/ (speichere_analyse)
    docs/vendor/leaflet/                Kartenbibliothek, lokal (keine Anfragen an Dritt-CDNs)
    docs/daten/organisationen.json      Verzeichnis der Organisationen
    docs/.nojekyll                      GitHub Pages soll die Dateien unverändert ausliefern
    docs/daten/schema.json              Datenmodell (modell.schema) für Formular, Popup, Liste

Kontaktdaten werden nicht veröffentlicht (`oeffentlich`, Regeln: README „Kontaktdaten“).
"""

from __future__ import annotations

import datetime as dt
import html
import json
import shutil
import urllib.request
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from . import anlagen as anlagen_typen
from . import modell, web
from .bestand import EMAIL, KONTAKT, adresse_text

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
ANALYSE = "analyse.json"  # Titel, Beschreibungen und Quellenvermerk einer gespeicherten Analyse


# --- Datenbestand für die Karte ---------------------------------------------------------

# Angaben einer Sportanlage, die die Karte zeigt (neben Typ, Kennung und Name): alle Felder
# des Modells außer IDs
ANLAGE_FELDER = tuple(
    f
    for f in modell.Sportanlage.model_fields
    if f not in ("id", "sportstaette_id", "typ", "bezeichnung")
)


def betreiber_art(name: str | None, typ: str | None = None) -> str | None:
    """'Verein', 'Kommune' oder 'sonstige' aus der angegebenen Art (modell.ORGANISATIONSTYPEN).
    Ohne Art bleibt sie unbekannt (None) – geschätzt wird nicht; None auch ohne Namen."""
    if not (name or "").strip():
        return None
    return modell.ORGANISATIONSTYPEN.get(typ or "")


def _anlage_kurz(a: dict) -> list:
    """Sportanlage für die Karte: [Typ, Kurz-ID, Name, {Angaben}]; leere Teile am Ende
    entfallen. Die Kurz-ID (Anfang der UUID) genügt, um die Datei zu finden."""
    extra = {k: a[k] for k in ANLAGE_FELDER if a.get(k) not in (None, "", [], {})}
    out = [a["typ"], str(a.get("id", ""))[:8], a.get("bezeichnung") or "", extra]
    while len(out) > 2 and not out[-1]:
        out.pop()
    return out


def bestand_geojson(datensaetze, praezision: int = 5, organisationen=None) -> dict:
    """Sportstätten → GeoJSON-Punkte (flache Eigenschaften, Anlagen als Liste) und die
    Gruppen der Anlagentypen für den Filter (`anlagengruppen`, `anlagentypen`).
    Steht ein Eigentümer oder Betreiber im Verzeichnis der Organisationen, gilt dessen Art,
    wenn bei der Sportstätte keine angegeben ist."""
    from .bestand import org_schluessel, org_verzeichnis

    verzeichnis = org_verzeichnis(organisationen or [])
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
        # alle Felder des Modells, flach: die Teile der Adresse stehen einzeln daneben,
        # "adresse" ist der Text; die Lage steckt in der Geometrie
        p = {}
        for feld in modell.Sportstaette.model_fields:
            if feld == "adresse":
                p["adresse"] = adresse_text(a)
                p.update({k: a.get(k) for k in modell.Adresse.model_fields})
            elif feld == "anlagen":
                p["anlagen"] = anlagen
            elif feld != "lage":
                p[feld] = d.get(feld)
        for rolle in ("betreiber", "eigentuemer"):
            org = verzeichnis.get(org_schluessel(d.get(rolle)))
            if org and org.get("typ") and not p.get(f"{rolle}_typ"):
                p[f"{rolle}_typ"] = org["typ"]
            p[f"{rolle}_art"] = betreiber_art(d.get(rolle), p.get(f"{rolle}_typ"))
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
        # alle bekannten Typen (für Formular und Prüfungen) und die im Bestand
        "anlagentypen": {
            t: anlagen_typen.gruppe(t) for t in sorted(typen | set(anlagen_typen.GRUPPE_VON))
        },
    }


# --- Veröffentlichen --------------------------------------------------------------------


def oeffentlich(fc: dict) -> tuple[dict, Counter]:
    """Kontaktdaten und Werte mit E-Mail-Adresse entfernen. Liefert (GeoJSON, entfernt)."""
    entfernt: Counter = Counter()
    for f in fc.get("features", []):
        p = f.get("properties") or {}
        neu = {}
        for k, v in p.items():
            if KONTAKT.search(k):
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

    Der Ordner `ordner` (docs/daten/analysen) wird vorher geleert: keine Reste früherer Läufe.
    """
    if ordner.exists():
        shutil.rmtree(ordner)
    verzeichnis, dateien = {}, []
    for name, (titel, inhalte, texte) in analysen.items():
        verzeichnis[name] = {"name": name, "titel": titel, "dateien": texte}
        for datei, inhalt in inhalte.items():
            dateien.append((f"analysen/{name}/{datei}", texte.get(datei, ""), inhalt))
    return verzeichnis, dateien


def speichere_analyse(
    ordner: Path, name: str, titel: str, inhalte: dict, texte: dict, quellenvermerk: str = ""
) -> None:
    """Ergebnis einer Analyse für die Webseite nach `ordner/name/` (webseite/analysen/, im Git).

    Dazu `analyse.json` mit Titel, Beschreibungen und Quellenvermerk. Kontaktdaten werden
    vorher entfernt (`oeffentlich`), der Ordner vorher geleert.
    """
    ziel = ordner / name
    if ziel.exists():
        shutil.rmtree(ziel)
    ziel.mkdir(parents=True)
    for datei, obj in inhalte.items():
        _schreibe_json(ziel / datei, oeffentlich(obj)[0] if "features" in obj else obj)
    kopf = {"titel": titel, "dateien": texte, "quellenvermerk": quellenvermerk}
    (ziel / ANALYSE).write_text(json.dumps(kopf, ensure_ascii=False, indent=2) + "\n", "utf-8")


def lade_analysen(ordner: Path) -> tuple[dict[str, tuple[str, dict, dict]], list[str]]:
    """Gespeicherte Analysen (speichere_analyse): ({Name: (Titel, Inhalte, Texte)}, Vermerke)."""
    analysen, vermerke = {}, []
    for kopf_datei in sorted(ordner.glob(f"*/{ANALYSE}")):
        kopf = json.loads(kopf_datei.read_text("utf-8"))
        inhalte = {
            p.name: json.loads(p.read_text("utf-8"))
            for p in sorted(kopf_datei.parent.glob("*.*json"))
            if p.name != ANALYSE
        }
        analysen[kopf_datei.parent.name] = (kopf["titel"], inhalte, kopf.get("dateien", {}))
        if kopf.get("quellenvermerk"):
            vermerke.append(kopf["quellenvermerk"])
    return analysen, vermerke


def schreibe_webseite(
    ausgabe: Path,
    bestand: list[dict] | None = None,
    gebiete: dict | None = None,
    analysen: dict[str, tuple[str, dict, dict]] | None = None,
    ars_von: Callable | None = None,
    quellenvermerk: str = "",
    titel: str = "Sportstättenatlas Rheinland-Pfalz",
    leaflet_laden: bool = True,
    organisationen: list[dict] | None = None,
    von_hand: Path | None = None,
) -> dict:
    """Webseite nach `ausgabe` (z. B. docs/) schreiben. Liefert eine kleine Statistik.

    bestand:  Datensätze aus daten/ (bestand.lies_bestand)
    gebiete:  Verwaltungsgebiete (gebiete.lade) für die Gebietsauswahl
    analysen: {Name: (Titel, {Datei: Inhalt}, {Datei: Beschreibung})}, z. B. aus
              lade_analysen. Was hier fehlt, fehlt auch auf der Seite.
    ars_von:  (lon, lat) → Regionalschlüssel der Gemeinde, für Datensätze aus `bestand`
    organisationen: Verzeichnis der Organisationen (Eigentümer, Betreiber, Nutzer) (bestand.lies_organisationen)
    von_hand: Ordner mit konfig.js, impressum.html, datenschutz.html (webseite/); sie werden
              nach `ausgabe` kopiert. Fehlt eine dort, wird sie aus `ausgabe` übernommen oder
              aus der Vorlage angelegt. Ohne Ordner: in `ausgabe` nur beim ersten Mal angelegt.
    """
    from . import gebiete as gb

    ausgabe.mkdir(parents=True, exist_ok=True)
    daten = ausgabe / "daten"
    daten.mkdir(exist_ok=True)

    # (Pfad unter daten/, Beschreibung, Inhalt)
    schreiben: list[tuple[str, str, dict]] = []
    if bestand is not None:
        fc = bestand_geojson(bestand, organisationen=organisationen)
        if ars_von:
            for f in fc["features"]:
                if ars := ars_von(*f["geometry"]["coordinates"]):
                    f["properties"]["ars"] = ars
        schreiben.append(("bestand.geojson", "Sportstätten (Datenbestand des Atlas)", fc))
    if organisationen is not None:
        felder = modell.datei_felder(modell.Organisation)
        eintraege = [
            {k: o[k] for k in felder if o.get(k) not in (None, "", [])} for o in organisationen
        ]
        schreiben.append(
            (
                "organisationen.json",
                "Organisationen: Eigentümer, Betreiber, Nutzer",
                {"eintraege": eintraege},
            )
        )
    # Datenmodell: Felder, Regeln und Beschriftungen für Formular, Popup und Übersicht
    schreiben.append(("schema.json", "Datenmodell (JSON Schema)", modell.schema()))
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

    lokal = leaflet_laden and leaflet_lokal(ausgabe / "vendor" / "leaflet")
    web.kopiere_app(ausgabe / "app")
    (ausgabe / "index.html").write_text(
        web.html_seite(titel, quellenvermerk, leaflet="vendor/leaflet" if lokal else web.LEAFLET),
        encoding="utf-8",
    )
    neu_angelegt = []
    quelle = von_hand or ausgabe
    for name in VON_HAND:
        if not (quelle / name).exists():
            quelle.mkdir(parents=True, exist_ok=True)
            if (ausgabe / name).exists():  # früher nur in docs/ gepflegt
                shutil.copy2(ausgabe / name, quelle / name)
            else:
                (quelle / name).write_text(web.vorlage(name, titel), encoding="utf-8")
                neu_angelegt.append(name)
        if quelle != ausgabe:
            shutil.copy2(quelle / name, ausgabe / name)
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
