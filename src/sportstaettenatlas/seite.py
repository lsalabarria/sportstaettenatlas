"""Statische Webseite für GitHub Pages (Ordner docs/).

Aufbau:
    docs/index.html                 Karte (lädt die Daten nach, mit Ladehinweis)
    docs/konfig.js                  Titel, Link zum Meldeformular, Impressum, Datenschutz,
                                    Lizenz – wird nur beim ersten Mal angelegt und danach nie
                                    überschrieben (direkt auf GitHub bearbeitbar)
    docs/impressum.html,            Entwürfe der Rechtstexte (Platzhalter gelb markiert) –
    docs/datenschutz.html           ebenfalls nur einmal angelegt
    docs/daten/index.html           Download-Seite
    docs/daten/bestand.geojson      Sportstätten aus daten/ (Startansicht, Liste, Übersicht)
    docs/daten/sportstaetten.geojson, sportanlagen.geojson, atlas_abgleich.geojson
                                    ALKIS und Abgleich (Ansicht „Verifikation“, lädt erst dann)
    docs/daten/gebiete.json,        Kreise, Verbandsgemeinden, Gemeinden zur Auswahl
    docs/daten/gebiete_*.geojson    (Umrisse werden erst bei Bedarf geladen)
    docs/vendor/leaflet/            Kartenbibliothek, lokal (keine Anfragen an Dritt-CDNs)
    docs/.nojekyll                  GitHub Pages soll die Dateien unverändert ausliefern

Kontaktdaten (E-Mail, Telefon) werden nicht veröffentlicht. Zusätzlich wird jeder Wert,
der eine E-Mail-Adresse enthält, entfernt.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

from .karte import LEAFLET, html_seite

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

VERIFIKATION_DATEIEN = {
    "sportstaetten.geojson": "ALKIS: Sportstätten (Standorte mit Umriss)",
    "sportanlagen.geojson": "ALKIS: Sportanlagen (Hallen, Spielfelder, Becken …)",
    "atlas_abgleich.geojson": "Einträge des bisherigen Atlas ohne passende ALKIS-Fläche",
}

LEAFLET_DATEIEN = (
    "leaflet.js",
    "leaflet.css",
    "images/layers.png",
    "images/layers-2x.png",
    "images/marker-icon.png",
    "images/marker-icon-2x.png",
    "images/marker-shadow.png",
)

KONFIG_VORLAGE = """// Einstellungen der Webseite. Diese Datei kann direkt auf GitHub bearbeitet werden
// (Stift-Symbol); nach dem Speichern ist die Änderung nach ein bis zwei Minuten online.
// `sportstaettenatlas seite` überschreibt sie nicht.
window.KONFIG = {
  titel: "Sportstättenatlas Rheinland-Pfalz",

  // Link zum Meldeformular (LimeSurvey). Leer lassen = kein Knopf „Sportstätte vorschlagen“.
  // Beispiel: "https://limesurvey.hs-koblenz.de/index.php/123456?lang=de"
  vorschlag_url: "",
  // Optional: Name des URL-Parameters, mit dem das Formular die Nummer der Sportstätte
  // vorbelegt (Link „Änderung oder Fehler melden“ bei jeder Sportstätte). Leer = ohne.
  vorschlag_parameter: "",

  // Pflichtangaben für öffentliche Webseiten. Entwürfe liegen als impressum.html und
  // datenschutz.html bei (gelb markierte Stellen ergänzen). Alternativ hier die Adressen
  // der Seiten der Hochschule eintragen.
  impressum_url: "impressum.html",
  datenschutz_url: "datenschutz.html",

  // Lizenz der Daten (Download-Seite). Vorschlag: dieselbe Lizenz wie die ALKIS-Daten.
  // Vorher klären, ob die Rechte am bisherigen Atlas-Bestand das zulassen.
  lizenz: "Datenlizenz Deutschland – Namensnennung – Version 2.0 (dl-de/by-2-0)",
  lizenz_url: "https://www.govdata.de/dl-de/by-2-0",
  // So sollen Nutzende die Quelle nennen (ergänzt um den Quellenvermerk der ALKIS-Daten)
  namensnennung: "Sportstättenatlas Rheinland-Pfalz",

  // Ortssuche über OpenStreetMap (Nominatim/Photon). false = nur Suche in den eigenen Daten.
  ortssuche: true,
};
"""


_STIL = """<style>
 body { font: 15px/1.55 system-ui, sans-serif; max-width: 820px; margin: 0 auto; padding: 20px;
        color: #222; }
 h1 { font-size: 22px; border-bottom: 3px solid #871D33; padding-bottom: 6px; }
 h2 { font-size: 17px; margin-top: 26px; }
 a { color: #871D33; }
 mark { background: #FFF3B0; padding: 0 2px; }
 .entwurf { background: #FFF3B0; border: 1px solid #E0C200; padding: 8px 12px; border-radius: 6px; }
</style>"""

IMPRESSUM = """<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Impressum – __TITEL__</title>
__STIL__
</head><body>
<p><a href="./">← zur Karte</a></p>
<p class="entwurf">Entwurf: gelb markierte Stellen ergänzen und vor der Veröffentlichung von der
Hochschule (Rechtsabteilung bzw. Pressestelle) prüfen lassen. Danach diesen Hinweis löschen.
Alternativ in <code>konfig.js</code> auf das Impressum der Hochschule verlinken.</p>
<h1>Impressum</h1>

<h2>Anbieter</h2>
<p>Angaben gemäß § 5 Digitale-Dienste-Gesetz (DDG)</p>
<p><mark>Hochschule Koblenz</mark><br>
<mark>[Straße, Hausnummer]</mark><br>
<mark>[PLZ] Koblenz</mark></p>
<p>Die Hochschule Koblenz ist eine Körperschaft des öffentlichen Rechts.
Sie wird vertreten durch <mark>[Präsidentin/Präsident, Name]</mark>.</p>
<p>Zuständige Aufsichtsbehörde: <mark>[Ministerium, Anschrift]</mark><br>
Umsatzsteuer-Identifikationsnummer: <mark>[USt-IdNr.]</mark></p>

<h2>Kontakt</h2>
<p>Projekt __TITEL__<br>
<mark>[Fachbereich / Institut]</mark><br>
E-Mail: <mark>[Funktionsadresse, z. B. sportstaettenatlas@…]</mark></p>

<h2>Inhaltlich verantwortlich</h2>
<p>gemäß § 18 Abs. 2 Medienstaatsvertrag (MStV):<br>
<mark>[Name, Anschrift wie oben]</mark></p>

<h2>Hinweise zu den Daten</h2>
<p>Die Angaben zu den Sportstätten wurden sorgfältig zusammengestellt. Sie beruhen auf dem
amtlichen Liegenschaftskataster (ALKIS) und dem bisherigen Sportstättenatlas, in den Kommunen,
Vereine und andere öffentliche Stellen Daten eingetragen haben. Für Vollständigkeit und
Richtigkeit wird keine Gewähr übernommen. Fehler und Änderungen können über das Meldeformular
mitgeteilt werden.</p>

<h2>Quellen</h2>
<ul>
 <li>Liegenschaftskataster: © GeoBasis-DE / LVermGeoRP, Datenlizenz Deutschland – Namensnennung –
     Version 2.0 (<a href="https://www.govdata.de/dl-de/by-2-0">dl-de/by-2-0</a>)</li>
 <li>Hintergrundkarte: © <a href="https://basemap.de">basemap.de</a> / BKG, CC BY 4.0</li>
 <li>Verwaltungsgrenzen: © <a href="https://www.bkg.bund.de">BKG</a>, VG250,
     <a href="https://www.govdata.de/dl-de/by-2-0">dl-de/by-2-0</a></li>
 <li>Ortssuche: © OpenStreetMap-Mitwirkende (ODbL)</li>
 <li>Kartenbibliothek: <a href="https://leafletjs.com">Leaflet</a> (BSD-2-Clause)</li>
</ul>
</body></html>
"""

DATENSCHUTZ = """<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Datenschutz – __TITEL__</title>
__STIL__
</head><body>
<p><a href="./">← zur Karte</a></p>
<p class="entwurf">Entwurf: gelb markierte Stellen ergänzen und vor der Veröffentlichung mit dem
oder der Datenschutzbeauftragten der Hochschule abstimmen. Danach diesen Hinweis löschen.</p>
<h1>Datenschutzerklärung</h1>

<h2>1. Verantwortliche Stelle</h2>
<p><mark>Hochschule Koblenz, [Anschrift]</mark>, vertreten durch
<mark>[Präsidentin/Präsident]</mark>.<br>
Kontakt zum Projekt: <mark>[Funktionsadresse]</mark></p>
<p>Datenschutzbeauftragte/r der Hochschule: <mark>[Name bzw. Funktion, Kontakt]</mark></p>

<h2>2. Grundsätzliches</h2>
<p>Diese Webseite ist eine reine Informationsseite. Sie setzt keine Cookies, verwendet keine
Analyse- oder Werbedienste und enthält keine Eingabeformulare. Die angezeigten Daten über
Sportstätten enthalten keine Kontaktdaten von Personen.</p>

<h2>3. Bereitstellung der Webseite (GitHub Pages)</h2>
<p>Die Seite wird über den Dienst GitHub Pages der GitHub, Inc. (USA) ausgeliefert. Beim Aufruf
übermittelt Ihr Browser technisch notwendige Daten, insbesondere Ihre IP-Adresse, Datum und
Uhrzeit, die aufgerufene Datei sowie Browser und Betriebssystem. GitHub protokolliert nach
eigenen Angaben die IP-Adressen der Besucherinnen und Besucher von GitHub-Pages-Seiten und
speichert sie zu Sicherheitszwecken. Wir selbst haben auf diese Protokolle keinen Zugriff.</p>
<p>Zweck ist die Auslieferung der Webseite und die Sicherheit des Dienstes. Rechtsgrundlage ist
<mark>Art. 6 Abs. 1 lit. e DSGVO in Verbindung mit [Vorschrift des Landesdatenschutzgesetzes
Rheinland-Pfalz bzw. des Hochschulgesetzes] (Information der Öffentlichkeit als Aufgabe der
Hochschule)</mark>. Dabei können Daten in die USA übermittelt werden; <mark>[Grundlage der
Übermittlung prüfen, z. B. EU-US Data Privacy Framework]</mark>. Weitere Informationen:
<a href="https://docs.github.com/de/site-policy/privacy-policies/github-general-privacy-statement">Datenschutzerklärung
von GitHub</a>.</p>

<h2>4. Hintergrundkarte (basemap.de)</h2>
<p>Die Hintergrundkarte wird beim Anzeigen direkt von den Servern des Bundesamts für Kartographie
und Geodäsie (BKG) geladen (basemap.de). Dabei werden Ihre IP-Adresse und die angefragten
Kartenausschnitte an das BKG übermittelt. Ohne diese Übermittlung kann die Karte nicht angezeigt
werden. Weitere Informationen: <a href="https://www.bkg.bund.de">www.bkg.bund.de</a>.</p>

<h2>5. Ortssuche (OpenStreetMap)</h2>
<p>Nur wenn Sie im Suchfeld einen Begriff eingeben und mit Enter bzw. „Suchen“ bestätigen, wird
der Suchbegriff zusammen mit Ihrer IP-Adresse an den Suchdienst Nominatim der OpenStreetMap
Foundation (Vereinigtes Königreich) übermittelt, ersatzweise an den Dienst Photon der komoot
GmbH (Deutschland). Die Suche in den Sportstätten selbst findet nur in Ihrem Browser statt.
Weitere Informationen: <a href="https://osmfoundation.org/wiki/Privacy_Policy">Datenschutzerklärung
der OpenStreetMap Foundation</a>.</p>

<h2>6. Links zu anderen Angeboten</h2>
<p>Die Karte enthält Links, etwa zu Google Maps oder zum Meldeformular. Erst wenn Sie einen
solchen Link anklicken, wird das jeweilige Angebot aufgerufen; dort gelten dessen
Datenschutzhinweise. Für das Meldeformular (LimeSurvey der Hochschule Koblenz) gelten die dort
angegebenen Hinweise.</p>

<h2>7. Ihre Rechte</h2>
<p>Sie haben das Recht auf Auskunft (Art. 15 DSGVO), Berichtigung (Art. 16), Löschung (Art. 17),
Einschränkung der Verarbeitung (Art. 18) und Widerspruch (Art. 21). Wenden Sie sich dazu an die
oben genannte verantwortliche Stelle. Außerdem können Sie sich bei einer Aufsichtsbehörde
beschweren, in Rheinland-Pfalz beim Landesbeauftragten für den Datenschutz und die
Informationsfreiheit, Hintere Bleiche 34, 55116 Mainz.</p>

<p><small>Stand: <mark>[Datum]</mark></small></p>
</body></html>
"""


def rechtstext(vorlage: str, titel: str) -> str:
    return vorlage.replace("__STIL__", _STIL).replace("__TITEL__", html.escape(titel))


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


def leaflet_lokal(ziel: Path, version_url: str = LEAFLET) -> bool:
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
    titel: str, quellenvermerk: str, dateien: list[tuple[str, str, int, int]], stand: str
) -> str:
    vermerk_js = json.dumps(quellenvermerk, ensure_ascii=False).replace("</", "<\\/")
    zeilen = "".join(
        f'<tr><td><a href="{html.escape(name)}" download>{html.escape(name)}</a></td>'
        f"<td>{html.escape(text)}</td><td>{f'{anzahl:,}'.replace(',', '.')}</td>"
        f"<td>{_groesse(groesse)}</td></tr>"
        for name, text, anzahl, groesse in dateien
    )
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daten – {html.escape(titel)}</title>
<style>
 body {{ font: 15px/1.5 system-ui, sans-serif; max-width: 820px; margin: 0 auto; padding: 20px; color: #222; }}
 h1 {{ font-size: 22px; border-bottom: 3px solid #871D33; padding-bottom: 6px; }}
 table {{ border-collapse: collapse; width: 100%; }} td, th {{ text-align: left; padding: 6px 10px 6px 0;
 border-bottom: 1px solid #ddd; vertical-align: top; }} th {{ color: #555; font-weight: 600; }}
 .q {{ color: #555; font-size: 13px; }} a {{ color: #871D33; }}
</style></head><body>
<p><a href="../">← zur Karte</a></p>
<h1>Offene Daten</h1>
<p>Alle Daten der Karte zum Herunterladen, als GeoJSON (Koordinaten in WGS84, EPSG:4326).
Stand: {html.escape(stand)}.</p>
<table><tr><th>Datei</th><th>Inhalt</th><th>Objekte</th><th>Größe</th></tr>{zeilen}</table>
<h2>Quellen und Lizenz</h2>
<p class="q">{html.escape(quellenvermerk) or "–"}</p>
<p class="q" id="lizenz"></p>
<p class="q">Kontaktdaten (E-Mail-Adressen, Telefonnummern) werden nicht veröffentlicht.</p>
<script src="../konfig.js"></script>
<script>
  const k = window.KONFIG || {{}}, el = document.getElementById("lizenz");
  const vermerk = {vermerk_js};
  if (k.lizenz) {{
    const a = document.createElement(k.lizenz_url ? "a" : "span");
    a.textContent = k.lizenz;
    if (k.lizenz_url) a.href = k.lizenz_url;
    el.append("Lizenz: ", a);
    if (k.namensnennung) el.append(document.createElement("br"),
      "Bitte als Quelle nennen: " + k.namensnennung + (vermerk ? "; " + vermerk : ""));
  }}
</script>
</body></html>
"""


def _ars_setzen(fc: dict, zuordnung, ars_von: dict | None = None, schluessel: str = "") -> int:
    """Jedem Objekt den ARS seiner Gemeinde geben (Koordinate bzw. lon/lat-Eigenschaften)."""
    n = 0
    for f in fc.get("features", []):
        p = f.setdefault("properties", {})
        ars = ars_von.get(p.get(schluessel)) if ars_von and schluessel else None
        if ars is None:
            g = f.get("geometry") or {}
            if g.get("type") == "Point":
                ars = zuordnung.ars(*g["coordinates"][:2])
            else:
                ars = zuordnung.ars(p.get("lon"), p.get("lat"))
        if ars:
            p["ars"] = ars
            n += 1
    return n


def schreibe_webseite(
    anlagen,
    staetten,
    ausgabe: Path,
    quellenvermerk: str = "",
    abgleich_altbestand=None,
    titel: str = "Sportstättenatlas Rheinland-Pfalz",
    leaflet_laden: bool = True,
    bestand=None,
    gebiete: dict | None = None,
    verifikation: bool = True,
) -> dict:
    """Webseite nach `ausgabe` (z. B. docs/) schreiben. Liefert eine kleine Statistik.

    bestand:      Datensätze aus daten/ (bestand.lies_bestand) – die Startansicht
    gebiete:      Verwaltungsgebiete (gebiete.lade) für die Gebietsauswahl
    verifikation: False = ALKIS-Dateien nicht neu schreiben (vorhandene bleiben)
    """
    from . import gebiete as gb
    from .bestand import bestand_geojson
    from .karte import atlas_geojson, geojson

    ausgabe.mkdir(parents=True, exist_ok=True)
    daten = ausgabe / "daten"
    daten.mkdir(exist_ok=True)

    fcs: dict[str, tuple[str, dict]] = {}
    if bestand is not None:
        fcs["bestand.geojson"] = (
            "Sportstätten (Datenbestand, Startansicht der Karte)",
            bestand_geojson(bestand, abgleich_altbestand),
        )
    if verifikation:
        fcs["sportstaetten.geojson"] = (
            "ALKIS: Sportstätten (Standorte mit Umriss)",
            geojson(staetten, praezision=1e-5, vereinfachen_m=1.0),
        )
        fcs["sportanlagen.geojson"] = (
            "ALKIS: Sportanlagen (Hallen, Spielfelder, Becken …)",
            geojson(anlagen, praezision=1e-5, vereinfachen_m=1.0),
        )
        fcs["atlas_abgleich.geojson"] = (
            "Einträge des bisherigen Atlas ohne passende ALKIS-Fläche",
            atlas_geojson(abgleich_altbestand),
        )

    zugeordnet = {}
    if gebiete and gebiete.get("gemeinde", {}).get("features"):
        z = gb.Zuordnung(gebiete["gemeinde"])
        st_ars: dict = {}
        for name in ("bestand.geojson", "sportstaetten.geojson", "atlas_abgleich.geojson"):
            if name in fcs:
                zugeordnet[name] = _ars_setzen(fcs[name][1], z)
        if "sportstaetten.geojson" in fcs:
            st_ars = {
                f["properties"].get("sportstaette_id"): f["properties"].get("ars")
                for f in fcs["sportstaetten.geojson"][1]["features"]
            }
            zugeordnet["sportanlagen.geojson"] = _ars_setzen(
                fcs["sportanlagen.geojson"][1], z, st_ars, "sportstaette_id"
            )
        for ebene in gb.EBENEN:
            fcs[f"gebiete_{ebene}.geojson"] = (
                f"Umrisse: {gb.EBENEN_TEXT[ebene]} (VG250, BKG)",
                gb.umrisse(gebiete, ebene),
            )

    entfernt: Counter = Counter()
    liste = []
    for name, (text, fc) in fcs.items():
        fc, weg = oeffentlich(fc)
        entfernt += weg
        groesse = _schreibe_json(daten / name, fc)
        liste.append((name, text, len(fc["features"]), groesse))
    if gebiete:
        eintraege = gb.index(gebiete)
        groesse = _schreibe_json(daten / "gebiete.json", {"eintraege": eintraege})
        liste.append(
            ("gebiete.json", "Verzeichnis der Gebiete (Auswahlliste)", len(eintraege), groesse)
        )
    elif (daten / "gebiete.json").exists():
        (daten / "gebiete.json").unlink()  # sonst zeigt die Karte eine veraltete Auswahl

    lokal = leaflet_laden and leaflet_lokal(ausgabe / "vendor" / "leaflet")
    (ausgabe / "index.html").write_text(
        html_seite(
            None,
            None,
            titel,
            quellenvermerk,
            webseite=True,
            leaflet="vendor/leaflet" if lokal else LEAFLET,
        ),
        encoding="utf-8",
    )
    neu_angelegt = []
    vorlagen = {
        "konfig.js": KONFIG_VORLAGE.replace("Sportstättenatlas Rheinland-Pfalz", titel),
        "impressum.html": rechtstext(IMPRESSUM, titel),
        "datenschutz.html": rechtstext(DATENSCHUTZ, titel),
    }
    for name, inhalt in vorlagen.items():  # nie überschreiben – werden von Hand gepflegt
        if not (ausgabe / name).exists():
            (ausgabe / name).write_text(inhalt, encoding="utf-8")
            neu_angelegt.append(name)
    stand = dt.datetime.now(dt.UTC).strftime("%d.%m.%Y")
    # in der Download-Liste auch Dateien früherer Läufe (z. B. ALKIS ohne neue Pipeline)
    beschrieben = {n for n, *_ in liste}
    for name, text in VERIFIKATION_DATEIEN.items():
        pfad = daten / name
        if name not in beschrieben and pfad.exists():
            n = len(json.loads(pfad.read_text(encoding="utf-8")).get("features", []))
            liste.append((name, text, n, pfad.stat().st_size))
    (daten / "index.html").write_text(
        download_seite(titel, quellenvermerk, liste, stand), encoding="utf-8"
    )
    (ausgabe / ".nojekyll").write_text("", encoding="utf-8")
    return {
        "dateien": liste,
        "entfernt": dict(entfernt),
        "leaflet_lokal": lokal,
        "neu_angelegt": neu_angelegt,
        "zugeordnet": zugeordnet,
        "gesamt": sum(f.stat().st_size for f in ausgabe.rglob("*") if f.is_file()),
    }
