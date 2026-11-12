"""Kommandozeile.

sportstaettenatlas bestand QUELLE   Atlas-Export in den Datenbestand daten/ überführen
sportstaettenatlas umstellen        daten/ ins Format „ein Ordner je Sportstätte“ bringen
sportstaettenatlas seite            Webseite für GitHub Pages (docs/) bauen
sportstaettenatlas alkis …          Analyse ALKIS-Abgleich (laden, bauen, abgleich …)
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
from pathlib import Path

from .analysen.alkis import cli as alkis_cli
from .hilfen import DATEN


def cmd_bestand(args):
    """Quelldatei (z. B. Atlas-Export) in den Datenbestand daten/<LAND>/*.json überführen."""
    from .bestand import LESER, README_DATEN, erkenne_format, schreibe_bestand

    quelle, ziel = Path(args.quelle), Path(args.ziel)
    if not quelle.is_file():
        raise SystemExit(f"{quelle} nicht gefunden.")
    fmt = args.format if args.format != "auto" else erkenne_format(quelle)
    land = args.land.upper()
    try:
        e = schreibe_bestand(LESER[fmt](quelle, land), ziel, land, args.modus)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if not (ziel / "README.md").exists():
        (ziel / "README.md").write_text(README_DATEN, encoding="utf-8")
    print(f"{quelle.name} ({fmt}) → {ziel}/{land}/")
    print(f"  neu angelegt:        {e.neu} Sportstätten (je ein Ordner mit ihren Anlagen)")
    if args.modus == "aktualisieren":
        print(f"  aktualisiert:        {e.aktualisiert}")
        print(f"  unverändert:         {e.unveraendert}")
    else:
        print(
            f"  schon vorhanden:     {e.behalten} (nicht verändert; --modus aktualisieren überschreibt)"
        )
    if e.ohne_lage:
        print(f"  ohne Koordinate:     {e.ohne_lage} (übersprungen)")
    if e.doppelt:
        print(f"  doppelte ID:         {e.doppelt} (nur der erste Eintrag übernommen)")
    if e.nicht_mehr_in_quelle:
        print(f"  nicht in der Quelle: {e.nicht_mehr_in_quelle} Dateien (bleiben unverändert)")
    if e.entfernt:
        print(
            "  entfernt (enthielt E-Mail-Adresse): "
            + ", ".join(f"{k} {v}×" for k, v in sorted(e.entfernt.items()))
        )


def cmd_umstellen(args):
    """Einmalig: daten/<LAND>/<id>.json → daten/<LAND>/<id>/ mit einer Datei je Anlage."""
    from .bestand import README_DATEN, umstellen

    ziel = Path(args.ziel)
    staetten, anlagen = umstellen(ziel)
    if not staetten:
        print(f"{ziel}/: nichts umzustellen.")
        return
    (ziel / "README.md").write_text(README_DATEN, encoding="utf-8")
    print(f"{ziel}/: {staetten} Sportstätten in eigene Ordner, {anlagen} Sportanlagen als Dateien.")
    print(
        'Prüfen und übernehmen: git add -A daten && git commit -m "Datenbestand: Ordner je Sportstätte"'
    )


def cmd_seite(args):
    """Statische Webseite für GitHub Pages (Ordner docs/) erzeugen."""
    from . import gebiete as gb
    from .bestand import lies_bestand
    from .seite import schreibe_webseite

    ausgabe = Path(args.ausgabe)
    vermerke = []

    bestand = None
    if Path(args.bestand).is_dir():
        try:
            bestand = list(lies_bestand(Path(args.bestand)))
        except ValueError as exc:
            raise SystemExit(f"Datenbestand: {exc}") from None
    else:
        print(f"Hinweis: kein Datenbestand unter {args.bestand}/ – zuerst `bestand` ausführen.")

    gebiete = ars_von = None
    if args.gebiete != "aus":
        quelle = None if args.gebiete == "auto" else Path(args.gebiete)
        name = f"gebiete_{args.land}{'' if quelle is None else '_' + quelle.stem}.json"
        try:
            gebiete = gb.lade(args.land, DATEN / "cache" / name, quelle)
            ars_von = gb.Zuordnung(gebiete["gemeinde"]).ars
            vermerke.append(gb.QUELLENVERMERK.format(jahr=dt.datetime.now(dt.UTC).year))
        except Exception as exc:  # noqa: BLE001 – Netz, Dienst geändert …: Seite trotzdem bauen
            print(f"Hinweis: Verwaltungsgebiete nicht verfügbar ({exc}) – ohne Gebietsauswahl.")

    analysen = {}
    alkis = alkis_cli.fuer_webseite(Path(args.alkis), args.land, ars_von)
    if alkis is None:
        print(
            f"Hinweis: {args.alkis}/sportstaetten.gpkg fehlt – der ALKIS-Abgleich behält seinen "
            "bisherigen Stand (neu mit `alkis bauen` und `alkis abgleich`)."
        )
    else:
        titel, dateien, texte, vermerk = alkis
        analysen["alkis"] = (titel, dateien, texte)
        vermerke.insert(0, vermerk)

    info = schreibe_webseite(
        ausgabe,
        bestand=bestand,
        gebiete=gebiete,
        analysen=analysen,
        ars_von=ars_von,
        quellenvermerk=" | ".join(vermerke),
        titel=args.titel,
    )
    print(f"Webseite: {ausgabe}/  ({info['gesamt'] / 1e6:.1f} MB)")
    for name, _, anzahl, groesse in info["dateien"]:
        objekte = "" if anzahl is None else f"{anzahl} Objekte, "
        print(f"  daten/{name}: {objekte}{groesse / 1e6:.1f} MB")
    if info["entfernt"]:
        print(
            "Nicht veröffentlicht (Kontaktdaten): "
            + ", ".join(f"{k}: {v}" for k, v in sorted(info["entfernt"].items()))
        )
    if not info["leaflet_lokal"]:
        print(
            "Hinweis: Leaflet konnte nicht heruntergeladen werden – die Seite lädt es von unpkg.com."
        )
    if info["neu_angelegt"]:
        print(
            "Neu angelegt (wird nie überschrieben): "
            + ", ".join(f"{ausgabe}/{n}" for n in info["neu_angelegt"])
        )
        print("  → gelb markierte Stellen in impressum.html und datenschutz.html ergänzen,")
        print("    in konfig.js die Links zur Umfrage und zu „Bug melden“ eintragen.")
    if args.vorschau:
        _vorschau(ausgabe, args.port)


def _vorschau(ordner: Path, port: int) -> None:
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
    p = argparse.ArgumentParser(
        prog="sportstaettenatlas",
        description="Offener Sportstättenatlas: Datenbestand, Webseite und Analysen.",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="befehl", required=True)

    sp = sub.add_parser(
        "bestand", help="Quelldatei (z. B. Atlas-Export) in den Datenbestand daten/ überführen"
    )
    sp.add_argument("quelle", help="Datei, z. B. der CSV-Export des bisherigen Atlas")
    sp.add_argument("--format", default="auto", choices=["auto", "atlas-export"])
    sp.add_argument("--land", default="rp", help="Länderkürzel, bestimmt Ordner und ID-Präfix")
    sp.add_argument("--ziel", default="daten", help="Ordner des Datenbestands (Standard: daten)")
    sp.add_argument(
        "--modus",
        default="neu",
        choices=["neu", "aktualisieren"],
        help="neu: nur fehlende anlegen (Standard); aktualisieren: vorhandene überschreiben",
    )
    sp.set_defaults(func=cmd_bestand)

    sp = sub.add_parser(
        "umstellen", help="Datenbestand einmalig ins Format „ein Ordner je Sportstätte“ bringen"
    )
    sp.add_argument("--ziel", default="daten", help="Ordner des Datenbestands (Standard: daten)")
    sp.set_defaults(func=cmd_umstellen)

    sp = sub.add_parser("seite", help="Webseite für GitHub Pages (Ordner docs/) erzeugen")
    sp.add_argument("--land", default="rp")
    sp.add_argument("--bestand", default="daten", help="Ordner des Datenbestands (Standard: daten)")
    sp.add_argument(
        "--alkis",
        "--ziel",
        dest="alkis",
        default=str(alkis_cli.ZIEL),
        help="Ergebnis des ALKIS-Abgleichs (Standard: data/out)",
    )
    sp.add_argument("--ausgabe", default="docs", help="Ordner der Webseite (Standard: docs)")
    sp.add_argument("--titel", default="Sportstättenatlas Rheinland-Pfalz")
    sp.add_argument(
        "--gebiete",
        default="auto",
        help="Verwaltungsgebiete: auto (BKG-WFS, einmal geladen), Pfad zu einem "
        "VG250-GeoPackage oder aus",
    )
    sp.add_argument("--vorschau", action="store_true", help="danach lokal im Browser zeigen")
    sp.add_argument("--port", type=int, default=8000)
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
