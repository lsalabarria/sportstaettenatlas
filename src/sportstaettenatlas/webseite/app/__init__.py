"""Die Webseite: HTML-Gerüst, Stil und Skripte als eigene Dateien in diesem Ordner.

    index.html      Gerüst mit Platzhaltern (__TITEL__, __SKRIPTE__ …)
    stil.css        Aussehen
    grundlagen.js   Hilfen, Karte, Gebietsauswahl, Umschalten der Ansichten
    bestand.js      Ansichten Karte und Übersicht (Datenbestand des Atlas)
    liste.js        Ansicht Liste: Sportstätten, Sportanlagen, Betreiber; alle Angaben je Eintrag
    vorschlag/      Ansicht Vorschlag (Formular mit Doppelungsprüfung → LimeSurvey), in Teilen:
                    00_hilfen.js, 10_formular.js … 95_senden.js, 99_links.js; werden der
                    Reihe nach zu app/vorschlag.js zusammengesetzt (siehe ZUSAMMENGESETZT)
    analysen.js     Ansicht Analysen, darin der ALKIS-Abgleich
    start.js        Suche, Rechtsklick-Menü, Start
    vorlagen/       konfig.js, Impressum, Datenschutz, Download-Seite
    schrift/        Schrift Inter (WOFF, lateinische Zeichen) mit ihrer Lizenz (OFL.txt)

`html_seite` setzt Titel und Quellenvermerk ein und verlinkt Stil und Skripte, die
`kopiere_app` nach docs/app/ kopiert; die Daten lädt die Seite aus docs/daten/ nach.

Die Skripte sind normale Browser-Skripte; sie teilen sich ihre Funktionen über den
globalen Namensraum und werden in der Reihenfolge SKRIPTE geladen. Einziger Build-Schritt:
vorschlag.js wird aus den Dateien in vorschlag/ zusammengesetzt (nur aneinandergehängt). Die
Teile 10–95 bilden zusammen den Rumpf von ansichtVorschlag und sind einzeln kein gültiges
JavaScript; 00 und 99 stehen für sich.
"""

from __future__ import annotations

import hashlib
import html
import json
from importlib import resources
from pathlib import Path

LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist"
STIL = "stil.css"
SKRIPTE = ("grundlagen.js", "bestand.js", "liste.js", "vorschlag.js", "analysen.js", "start.js")
# Schrift: liegt der Seite bei (kein Abruf bei Google Fonts o. Ä.), stil.css bindet sie ein
SCHRIFTEN = ("inter-400.woff", "inter-600.woff", "inter-700.woff", "OFL.txt")


# Skripte, die aus mehreren Dateien eines Ordners zusammengesetzt werden (nach Namen sortiert)
ZUSAMMENGESETZT = {"vorschlag.js": "vorschlag"}


def teile(name: str) -> list[str]:
    """Namen der Teile eines zusammengesetzten Skripts, in der Reihenfolge."""
    ordner = resources.files(__name__).joinpath(ZUSAMMENGESETZT[name])
    return sorted(t.name for t in ordner.iterdir() if t.name.endswith(".js"))


def datei(name: str) -> str:
    """Inhalt einer Datei aus diesem Ordner (auch aus dem installierten Paket); ein
    zusammengesetztes Skript (ZUSAMMENGESETZT) als seine Teile hintereinander."""
    if name in ZUSAMMENGESETZT:
        ordner = resources.files(__name__).joinpath(ZUSAMMENGESETZT[name])
        return "".join(ordner.joinpath(t).read_text("utf-8") for t in teile(name))
    return resources.files(__name__).joinpath(name).read_text("utf-8")


def einbetten(obj) -> str:
    """JSON für einen <script>-Block ("</" darf darin nicht vorkommen)."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _version(text: str) -> str:
    """Kurzer Prüfwert für ?v=…, damit Browser nach einer Änderung die neue Datei laden."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def html_seite(titel: str, quellenvermerk: str = "", leaflet: str = LEAFLET) -> str:
    """index.html der Webseite; Stil und Skripte liegen unter `app/` (siehe kopiere_app)."""
    stil = f'<link rel="stylesheet" href="app/{STIL}?v={_version(datei(STIL))}">'
    skripte = "\n".join(f'<script src="app/{n}?v={_version(datei(n))}"></script>' for n in SKRIPTE)
    return (
        datei("index.html")
        .replace("__TITEL__", html.escape(titel))
        .replace("__LEAFLET__", leaflet)
        .replace("__STIL__", stil)
        .replace("__QUELLE__", einbetten(quellenvermerk))
        .replace("__SKRIPTE__", skripte)
    )


def kopiere_app(ziel: Path) -> None:
    """Stil, Skripte und Schrift nach `ziel` (docs/app/) kopieren; veraltete Dateien entfernen."""
    ziel.mkdir(parents=True, exist_ok=True)
    namen = [STIL, *SKRIPTE]
    for n in namen:
        (ziel / n).write_text(datei(n), encoding="utf-8")
    for alt in ziel.iterdir():
        if alt.is_file() and alt.name not in namen:
            alt.unlink()
    schrift = ziel / "schrift"
    schrift.mkdir(exist_ok=True)
    for n in SCHRIFTEN:
        (schrift / n).write_bytes(resources.files(__name__).joinpath("schrift", n).read_bytes())
    for alt in schrift.iterdir():
        if alt.is_file() and alt.name not in SCHRIFTEN:
            alt.unlink()


def vorlage(name: str, titel: str) -> str:
    """konfig.js, impressum.html oder datenschutz.html mit eingesetztem Titel."""
    text = datei(f"vorlagen/{name}")
    if name == "konfig.js":
        return text.replace("Sportstättenatlas Rheinland-Pfalz", titel)
    return text.replace("__TITEL__", html.escape(titel))
