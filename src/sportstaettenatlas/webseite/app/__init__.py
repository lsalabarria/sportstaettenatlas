"""Die Webseite: HTML-Gerüst, Stil und Skripte als eigene Dateien in diesem Ordner.

    index.html      Gerüst mit Platzhaltern (__TITEL__, __SKRIPTE__ …)
    stil.css        Aussehen
    start.js        Einstieg: Daten laden, Ansichten anlegen, die gewünschte zeigen
    seite.js        Einstellungen (konfig.js), Kopfzeile, Laden und Fehler
    lib/            Hilfen ohne Seite und Karte: text.js, vergleich.js (wie bestand/pruefung.py)
    daten/          geladene Daten und ihr Zustand: schema.js (Datenmodell), organisationen.js,
                    sportkomplexe.js, stuetzpunkte.js
    karte/          karte.js (Karte, Popups), haufen.js, gebiete.js (Auswahl, Umrisse), suche.js
    ansichten/      umschalten.js (welche Ansicht gezeigt wird) und je Ansicht eine Datei:
                    bestand.js (Karte), liste.js, uebersicht.js, analysen.js, vorschlag/ (das
                    Formular in Teilen mit gemeinsamem Zustand, siehe vorschlag/ansicht.js)
    vorlagen/       konfig.js, Impressum, Datenschutz, Download-Seite
    schrift/        Schrift Inter (WOFF, lateinische Zeichen) mit ihrer Lizenz (OFL.txt)

Die Skripte sind ES-Module: Jede Datei sagt mit import, was sie aus anderen braucht, und mit
export, was sie anbietet; der Browser lädt sie ab start.js selbst (kein Build-Schritt).
`html_seite` bindet start.js ein und schreibt eine Import-Map, die jedem Modul ?v=… anhängt,
damit Browser nach einer Änderung die neue Datei laden. `kopiere_app` kopiert alles nach
docs/app/; die Daten lädt die Seite aus docs/daten/ nach. Module laufen nur über einen
Webserver (GitHub Pages, `sportstaettenatlas seite --vorschau`), nicht aus file://.
"""

from __future__ import annotations

import hashlib
import html
import json
from importlib import resources
from pathlib import Path

LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist"
STIL = "stil.css"
EINSTIEG = "start.js"
# Schrift: liegt der Seite bei (kein Abruf bei Google Fonts o. Ä.), stil.css bindet sie ein
SCHRIFTEN = ("inter-400.woff", "inter-600.woff", "inter-700.woff", "OFL.txt")
NICHT_MODULE = ("vorlagen", "schrift", "__pycache__")


def module() -> list[str]:
    """Alle Module der Seite als Pfade unter app/ ("karte/haufen.js"), sortiert."""
    out: list[str] = []

    def lauf(ordner, praefix: str) -> None:
        for t in ordner.iterdir():
            if t.is_dir() and t.name not in NICHT_MODULE:
                lauf(t, f"{praefix}{t.name}/")
            elif t.is_file() and t.name.endswith(".js"):
                out.append(praefix + t.name)

    lauf(resources.files(__name__), "")
    return sorted(out)


def datei(name: str) -> str:
    """Inhalt einer Datei aus diesem Ordner (auch aus dem installierten Paket), z. B.
    "stil.css" oder "karte/haufen.js"."""
    return resources.files(__name__).joinpath(*name.split("/")).read_text("utf-8")


def einbetten(obj) -> str:
    """JSON für einen <script>-Block ("</" darf darin nicht vorkommen)."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _version(text: str) -> str:
    """Kurzer Prüfwert für ?v=…, damit Browser nach einer Änderung die neue Datei laden."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def html_seite(titel: str, quellenvermerk: str = "", leaflet: str = LEAFLET) -> str:
    """index.html der Webseite; Stil und Module liegen unter `app/` (siehe kopiere_app)."""
    stil = f'<link rel="stylesheet" href="app/{STIL}?v={_version(datei(STIL))}">'
    versionen = {f"./app/{m}": f"./app/{m}?v={_version(datei(m))}" for m in module()}
    skripte = (
        '<script type="importmap">'
        + json.dumps({"imports": versionen}, ensure_ascii=False, indent=1)
        + "</script>\n"
        + f'<script type="module" src="{versionen["./app/" + EINSTIEG][2:]}"></script>'
    )
    return (
        datei("index.html")
        .replace("__TITEL__", html.escape(titel))
        .replace("__LEAFLET__", leaflet)
        .replace("__STIL__", stil)
        .replace("__QUELLE__", einbetten(quellenvermerk))
        .replace("__SKRIPTE__", skripte)
    )


def kopiere_app(ziel: Path) -> None:
    """Stil, Module und Schrift nach `ziel` (docs/app/) kopieren; veraltete Dateien entfernen."""
    ziel.mkdir(parents=True, exist_ok=True)
    texte = [STIL, *module()]
    for n in texte:
        (ziel / n).parent.mkdir(parents=True, exist_ok=True)
        (ziel / n).write_text(datei(n), encoding="utf-8")
    schrift = ziel / "schrift"
    schrift.mkdir(exist_ok=True)
    for n in SCHRIFTEN:
        (schrift / n).write_bytes(resources.files(__name__).joinpath("schrift", n).read_bytes())
    gewollt = {*texte, *(f"schrift/{n}" for n in SCHRIFTEN)}
    for alt in sorted(ziel.rglob("*"), reverse=True):  # Dateien vor ihren Ordnern
        rel = alt.relative_to(ziel).as_posix()
        if alt.is_file() and rel not in gewollt:
            alt.unlink()
        elif alt.is_dir() and not any(alt.iterdir()):
            alt.rmdir()


def vorlage(name: str, titel: str) -> str:
    """konfig.js, impressum.html oder datenschutz.html mit eingesetztem Titel."""
    text = datei(f"vorlagen/{name}")
    if name == "konfig.js":
        return text.replace("Sportstättenatlas Rheinland-Pfalz", titel)
    return text.replace("__TITEL__", html.escape(titel))
