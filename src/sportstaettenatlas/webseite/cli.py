"""Befehl `seite`: die Webseite für GitHub Pages (docs/) bauen."""

from __future__ import annotations

import contextlib
import datetime as dt
from pathlib import Path

from ..analysen.alkis import cli as alkis_cli
from ..bestand.cli import (
    REGELVERSTOESSE,
    lade_gebiete,
    lies_daten,
    pruefe_und_melde,
)
from ..hilfen import DATEN, DOCS, TITEL, WEBSEITE


def cmd_seite(args):
    """Statische Webseite für GitHub Pages (Ordner docs/) erzeugen."""
    from ..bestand import gebiete as gb
    from ..bestand import lies_sportkomplexe, lies_stuetzpunkte
    from ..modell import schreibe_doku
    from .bauen import lade_analysen, schreibe_webseite, speichere_analyse

    bestand, organisationen, verstoesse = lies_daten()
    for hinweis in schreibe_doku(DATEN):
        print(hinweis)
    gebiete = lade_gebiete()
    pruefe_und_melde(bestand, organisationen, verstoesse, gebiete)
    ars_von = gb.Zuordnung(gebiete["gemeinde"]).ars
    if alkis := alkis_cli.fuer_webseite(ars_von):
        titel, dateien, texte, vermerk = alkis
        speichere_analyse(WEBSEITE / "analysen", "alkis", titel, dateien, texte, vermerk)
        print(f"ALKIS-Ergebnis aus results/out nach {WEBSEITE}/analysen/alkis/ (ins Git).")
    analysen, vermerke = lade_analysen(WEBSEITE / "analysen")
    vermerke.append(gb.QUELLENVERMERK.format(jahr=dt.datetime.now(dt.UTC).year))
    if not analysen:
        print(f"Hinweis: keine Analyse in {WEBSEITE}/analysen – der Reiter „Analysen“ fehlt.")

    info = schreibe_webseite(
        DOCS,
        bestand=bestand,
        gebiete=gebiete,
        analysen=analysen,
        ars_von=ars_von,
        quellenvermerk=" | ".join(vermerke),
        titel=TITEL,
        organisationen=organisationen,
        von_hand=WEBSEITE,
        sportkomplexe=lies_sportkomplexe(DATEN),
        stuetzpunkte=lies_stuetzpunkte(DATEN),
    )
    print(f"Webseite: {DOCS}/  ({info['gesamt'] / 1e6:.1f} MB)")
    for name, _, anzahl, groesse in info["dateien"]:
        objekte = "" if anzahl is None else f"{anzahl} Objekte, "
        print(f"  daten/{name}: {objekte}{groesse / 1e6:.1f} MB")
    if info["entfernt"]:
        weg = ", ".join(f"{k}: {v}" for k, v in sorted(info["entfernt"].items()))
        print(f"Nicht veröffentlicht (Kontaktdaten): {weg}")
    if info["ausserhalb"]:
        print(
            f"Nicht auf der Karte: {info['ausserhalb']} Sportstätten, deren Lage in keiner Gemeinde "
            "von Rheinland-Pfalz liegt (Lage korrigieren oder nach daten/outside/<Land>/ "
            f"verschieben; Liste in daten/{REGELVERSTOESSE})."
        )
    if not info["leaflet_lokal"]:
        print("Hinweis: Leaflet nicht heruntergeladen – die Seite lädt es von unpkg.com.")
    if info["neu_angelegt"]:
        print("Neu angelegt (wird nie überschrieben): " + ", ".join(info["neu_angelegt"]))
        print(f"  → in {WEBSEITE}/ die Platzhalter ausfüllen.")
    if args.vorschau:
        _vorschau(DOCS)


def _vorschau(ordner: Path, port: int = 8000) -> None:
    """Seite lokal über einen kleinen Webserver zeigen (wie später auf GitHub Pages)."""
    import functools
    import http.server
    import webbrowser

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ordner))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        url = f"http://localhost:{port}/"
        print(f"Vorschau: {url}  (beenden mit Strg+C)")
        webbrowser.open(url)
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()


def befehle(sub) -> None:
    """Befehle dieses Teils an den Parser von `sportstaettenatlas` hängen."""
    sp = sub.add_parser("seite", help="Webseite für GitHub Pages (docs/) erzeugen")
    sp.add_argument("--vorschau", action="store_true", help="danach lokal im Browser zeigen")
    sp.set_defaults(func=cmd_seite)
