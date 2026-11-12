"""Kommandozeile.

sportstaettenatlas bestand EXPORT   Atlas-Export in den Datenbestand daten/ übernehmen
sportstaettenatlas einordnen        Sportstätten in den Ordner ihres Kreises verschieben
sportstaettenatlas seite            Webseite für GitHub Pages (docs/) bauen
sportstaettenatlas alkis            ALKIS-Abgleich gegen daten/ (Ergebnis in results/out)
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
from pathlib import Path

from .analysen.alkis import cli as alkis_cli

LAND = "rp"
DATEN = Path("daten")
DOCS = Path("docs")
TITEL = "Sportstättenatlas Rheinland-Pfalz"


def _gebiete():
    """Verwaltungsgebiete (einmal vom BKG geladen, dann aus results/cache)."""
    from . import gebiete as gb

    try:
        return gb.lade(LAND)
    except Exception as exc:  # noqa: BLE001 – Netz, Dienst geändert …
        raise SystemExit(f"Verwaltungsgebiete nicht verfügbar ({exc}).") from None


def _lies_bestand():
    from .bestand import lies_bestand

    try:
        return list(lies_bestand(DATEN))
    except ValueError as exc:
        raise SystemExit(f"Datenbestand: {exc}") from None


def cmd_bestand(args):
    """Atlas-Export in daten/<LAND>/<Kreis>/ übernehmen."""
    from .atlas import lies_export
    from .bestand import kreis_ordner, schreibe_bestand

    quelle = Path(args.export)
    if not quelle.is_file():
        raise SystemExit(f"{quelle} nicht gefunden.")
    try:
        e = schreibe_bestand(lies_export(quelle), DATEN, LAND, kreis_ordner(_gebiete()), args.modus)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print(f"{quelle.name} → {DATEN}/{LAND.upper()}/")
    print(f"  neu angelegt:        {e.neu} Sportstätten")
    if args.modus == "aktualisieren":
        print(f"  aktualisiert:        {e.aktualisiert}")
        print(f"  unverändert:         {e.unveraendert}")
    else:
        print(f"  schon vorhanden:     {e.behalten} (nicht verändert; --modus aktualisieren)")
    if e.ohne_lage:
        print(f"  ohne Koordinate:     {e.ohne_lage} (übersprungen)")
    if e.doppelt:
        print(f"  doppelte ID:         {e.doppelt} (nur der erste Eintrag übernommen)")
    if e.nicht_mehr_in_quelle:
        print(f"  nicht in der Quelle: {e.nicht_mehr_in_quelle} Sportstätten (bleiben)")
    if e.entfernt:
        weg = ", ".join(f"{k} {v}×" for k, v in sorted(e.entfernt.items()))
        print(f"  entfernt (enthielt E-Mail-Adresse): {weg}")


def cmd_einordnen(args):
    """Sportstätten, deren Lage in einem anderen Kreis liegt, dorthin verschieben."""
    from .bestand import einordnen, kreis_ordner

    try:
        n = einordnen(DATEN, kreis_ordner(_gebiete()))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print(f"{n} Sportstätten verschoben." if n else "Alle Sportstätten liegen im richtigen Kreis.")


def cmd_seite(args):
    """Statische Webseite für GitHub Pages (Ordner docs/) erzeugen."""
    from . import gebiete as gb
    from .bestand import falsch_einsortiert, kreis_ordner
    from .seite import schreibe_webseite

    bestand = _lies_bestand()
    gebiete = _gebiete()
    ars_von = gb.Zuordnung(gebiete["gemeinde"]).ars
    if falsch := falsch_einsortiert(bestand, kreis_ordner(gebiete)):
        print(
            f"Hinweis: {len(falsch)} Sportstätten liegen nicht im Ordner ihres Kreises "
            f"(z. B. {falsch[0][0]}: {falsch[0][1]} statt {falsch[0][2]}) – "
            "`sportstaettenatlas einordnen` verschiebt sie."
        )
    vermerke = [gb.QUELLENVERMERK.format(jahr=dt.datetime.now(dt.UTC).year)]
    analysen = {}
    if alkis := alkis_cli.fuer_webseite(ars_von):
        titel, dateien, texte, vermerk = alkis
        analysen["alkis"] = (titel, dateien, texte)
        vermerke.insert(0, vermerk)
    else:
        print(
            "Hinweis: kein ALKIS-Ergebnis in results/out – der Reiter „Analysen“ bleibt, wie er ist."
        )

    info = schreibe_webseite(
        DOCS,
        bestand=bestand,
        gebiete=gebiete,
        analysen=analysen,
        ars_von=ars_von,
        quellenvermerk=" | ".join(vermerke),
        titel=TITEL,
    )
    print(f"Webseite: {DOCS}/  ({info['gesamt'] / 1e6:.1f} MB)")
    for name, _, anzahl, groesse in info["dateien"]:
        objekte = "" if anzahl is None else f"{anzahl} Objekte, "
        print(f"  daten/{name}: {objekte}{groesse / 1e6:.1f} MB")
    if info["entfernt"]:
        weg = ", ".join(f"{k}: {v}" for k, v in sorted(info["entfernt"].items()))
        print(f"Nicht veröffentlicht (Kontaktdaten): {weg}")
    if not info["leaflet_lokal"]:
        print("Hinweis: Leaflet nicht heruntergeladen – die Seite lädt es von unpkg.com.")
    if info["neu_angelegt"]:
        print("Neu angelegt (wird nie überschrieben): " + ", ".join(info["neu_angelegt"]))
        print("  → in impressum.html, datenschutz.html und konfig.js die Platzhalter ausfüllen.")
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
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="sportstaettenatlas", description="Offener Sportstättenatlas.")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="befehl", required=True)

    sp = sub.add_parser("bestand", help="Atlas-Export in den Datenbestand daten/ übernehmen")
    sp.add_argument("export", help="CSV-Export des bisherigen Atlas")
    sp.add_argument(
        "--modus",
        default="neu",
        choices=["neu", "aktualisieren"],
        help="neu: nur fehlende anlegen (Standard); aktualisieren: vorhandene überschreiben",
    )
    sp.set_defaults(func=cmd_bestand)

    sp = sub.add_parser("einordnen", help="Sportstätten in den Ordner ihres Kreises verschieben")
    sp.set_defaults(func=cmd_einordnen)

    sp = sub.add_parser("seite", help="Webseite für GitHub Pages (docs/) erzeugen")
    sp.add_argument("--vorschau", action="store_true", help="danach lokal im Browser zeigen")
    sp.set_defaults(func=cmd_seite)

    alkis_cli.befehle(sub)

    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    from .hilfen import logging_mit_balken

    with logging_mit_balken():  # Log-Zeilen erscheinen über den Fortschrittsbalken
        args.func(args)


if __name__ == "__main__":
    main()
