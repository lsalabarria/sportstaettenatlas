"""Die Webseite: HTML-Gerüst, Stil und Skripte als eigene Dateien in diesem Ordner.

    index.html      Gerüst mit Platzhaltern (__TITEL__, __SKRIPTE__ …)
    stil.css        Aussehen
    grundlagen.js   Hilfen, Karte, Gebietsauswahl, Umschalten der Ansichten
    bestand.js      Ansichten Karte, Liste, Übersicht (Datenbestand des Atlas)
    vorschlag.js    Ansicht Vorschlag (Formular mit Doppelungsprüfung → LimeSurvey)
    analysen.js     Ansicht Analysen, darin der ALKIS-Abgleich
    start.js        Suche, Rechtsklick-Menü, Start
    vorlagen/       konfig.js, Impressum, Datenschutz, Download-Seite

Zwei Arten, die Seite zu bauen (`html_seite`):
- Webseite (GitHub Pages): Stil und Skripte werden nach docs/app/ kopiert und verlinkt,
  die Daten lädt die Seite aus docs/daten/ nach.
- Eine Datei (karte.html der ALKIS-Analyse): alles eingebettet, per Doppelklick zu öffnen.

Die Skripte sind normale Browser-Skripte ohne Build-Schritt; sie teilen sich ihre
Funktionen über den globalen Namensraum und werden in der Reihenfolge SKRIPTE geladen.
"""

from __future__ import annotations

import hashlib
import html
import json
from importlib import resources
from pathlib import Path

LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist"
STIL = "stil.css"
SKRIPTE = ("grundlagen.js", "bestand.js", "vorschlag.js", "analysen.js", "start.js")


def datei(name: str) -> str:
    """Inhalt einer Datei aus diesem Ordner (auch aus dem installierten Paket)."""
    return resources.files(__name__).joinpath(name).read_text("utf-8")


def einbetten(obj) -> str:
    """JSON für einen <script>-Block ("</" darf darin nicht vorkommen)."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _version(text: str) -> str:
    """Kurzer Prüfwert für ?v=…, damit Browser nach einer Änderung die neue Datei laden."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def html_seite(
    titel: str,
    quellenvermerk: str = "",
    eingebettet: dict | None = None,
    leaflet: str = LEAFLET,
    app: str = "app",
) -> str:
    """Die Seite als HTML-Text. Reine Funktion – testbar ohne Geo-Bibliotheken.

    eingebettet=None: Webseite; Stil und Skripte liegen unter `app/` (siehe kopiere_app).
    eingebettet={Pfad: Daten}: eine Datei mit allem darin; die Pfade sind die, unter denen
        die Webseite die Daten aus daten/ laden würde (z. B. "analysen/alkis/…").
    """
    if eingebettet is None:
        stil = f'<link rel="stylesheet" href="{app}/{STIL}?v={_version(datei(STIL))}">'
        skripte = "\n".join(
            f'<script src="{app}/{n}?v={_version(datei(n))}"></script>' for n in SKRIPTE
        )
        # konfig.js wird auf GitHub von Hand bearbeitet: immer frisch laden, sonst zeigt der
        # Browser bis zu zehn Minuten den alten Stand aus dem Zwischenspeicher
        konfig = (
            "<script>document.write('<script src=\"konfig.js?' + Date.now() + '\"><\\/script>');"
            "</script>"
        )
        laden = (
            '<div id="laden"><span class="kreisel"></span>'
            "<span>Sportstätten werden geladen …</span></div>"
        )
    else:
        stil = f"<style>\n{datei(STIL)}</style>"
        ende = "</" + "script"  # im eingebetteten Skript darf das Ende-Tag nicht vorkommen
        skripte = "\n".join(
            "<script>\n" + datei(n).replace(ende, "<\\/script") + "</script>" for n in SKRIPTE
        )
        konfig = laden = ""
    return (
        datei("index.html")
        .replace("__TITEL__", html.escape(titel))
        .replace("__LEAFLET__", leaflet)
        .replace("__STIL__", stil)
        .replace("__LADEN__", laden)
        .replace("__KONFIG__", konfig)
        .replace("__QUELLE__", einbetten(quellenvermerk))
        .replace("__SKRIPTE__", skripte)
        # zuletzt: eingebettete Daten nie nach Platzhaltern durchsuchen
        .replace("__EINGEBETTET__", "null" if eingebettet is None else einbetten(eingebettet))
    )


def kopiere_app(ziel: Path) -> list[str]:
    """Stil und Skripte nach `ziel` (docs/app/) kopieren; veraltete Dateien entfernen."""
    ziel.mkdir(parents=True, exist_ok=True)
    namen = [STIL, *SKRIPTE]
    for n in namen:
        (ziel / n).write_text(datei(n), encoding="utf-8")
    for alt in ziel.iterdir():
        if alt.is_file() and alt.name not in namen:
            alt.unlink()
    return namen


def vorlage(name: str, titel: str) -> str:
    """konfig.js, impressum.html oder datenschutz.html mit eingesetztem Titel."""
    text = datei(f"vorlagen/{name}")
    if name == "konfig.js":
        return text.replace("Sportstättenatlas Rheinland-Pfalz", titel)
    return text.replace("__TITEL__", html.escape(titel))
