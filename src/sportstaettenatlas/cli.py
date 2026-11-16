"""Kommandozeile.

sportstaettenatlas bestand CSV …    CSV-Dateien in den Datenbestand daten/ übernehmen
                                    (Atlas-Export, Sportstätten, Sportanlagen; einlesen.py)
sportstaettenatlas vorlage          Vorlagen für eigene CSV-Dateien
sportstaettenatlas organisationen   Verzeichnis der Organisationen (Eigentümer, Betreiber, Nutzer) (--aus-bestand)
sportstaettenatlas einordnen        Sportstätten in den Ordner ihres Kreises verschieben
sportstaettenatlas seite            Webseite für GitHub Pages (docs/) bauen
sportstaettenatlas modell           Datenmodell in daten/README.md und daten/datenmodell.svg
                                    (--migrieren: Dateien in daten/ anpassen)
sportstaettenatlas alkis            ALKIS-Abgleich gegen daten/ (Ergebnis in results/out)
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
from collections import Counter
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
    """Datenbestand und Verzeichnis der Organisationen lesen; Verstöße gegen die Regeln des
    Modells nach results/regelverstoesse.csv (brechen nicht ab)."""
    import csv

    from .bestand import lies_bestand, lies_organisationen
    from .hilfen import ERGEBNISSE

    verstoesse: list = []
    try:
        bestand = list(lies_bestand(DATEN, verstoesse))
        organisationen = lies_organisationen(DATEN, verstoesse)
    except ValueError as exc:
        raise SystemExit(f"Datenbestand: {exc}") from None
    datei = ERGEBNISSE / "regelverstoesse.csv"
    if verstoesse:
        datei.parent.mkdir(parents=True, exist_ok=True)
        with datei.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["datei", "meldung"])
            w.writerows(verstoesse)
        felder = Counter(m.split(":")[0] for _, m in verstoesse)
        print(
            f"Hinweis: {len(verstoesse)} Werte passen nicht zu den Regeln des Datenmodells "
            f"({', '.join(f'{k} {v}×' for k, v in felder.most_common(5))}) – Liste: {datei}"
        )
    elif datei.exists():
        datei.unlink()
    return bestand, organisationen


def cmd_bestand(args):
    """CSV-Dateien (Atlas-Export, Sportstätten oder Sportanlagen) in daten/ übernehmen."""
    from .bestand import kreis_ordner, schreibe_bestand, schreibe_organisationen
    from .einlesen import lies_csv

    gelesen = []
    for datei in map(Path, args.dateien):
        if not datei.is_file():
            raise SystemExit(f"{datei} nicht gefunden.")
        try:
            datensaetze, b = lies_csv(datei)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        art = {
            "atlas": "Export des bisherigen Atlas",
            "sportstaetten": "Sportstätten",
            "sportanlagen": "Sportanlagen",
            "organisationen": "Organisationen",
        }[b.art]
        print(f"{datei.name}: {art}, {b.zeilen} Zeilen")
        if b.spalten:
            breite = max(map(len, b.spalten))
            for spalte, feld in b.spalten.items():
                print(f"  {spalte:<{breite}}  → {feld}")
        if b.ignoriert:
            print(f"  ohne passendes Feld (ignoriert): {', '.join(b.ignoriert)}")
        if b.kontakt:
            print(f"  Kontaktdaten (nie gelesen): {', '.join(b.kontakt)}")
        if b.nicht_lesbar:
            fehler = ", ".join(f"{k} {v}×" for k, v in b.nicht_lesbar.most_common())
            print(f"  Werte, die nicht zum Feld passen (übernommen, wie sie sind): {fehler}")
        gelesen.append((datei, datensaetze, b.art))
    if args.probe:
        print("Probelauf: nichts geschrieben.")
        return
    kreis_von = None
    for datei, datensaetze, art in gelesen:
        try:
            if art == "organisationen":
                e = schreibe_organisationen(datensaetze, DATEN, args.modus)
            else:
                kreis_von = kreis_von or kreis_ordner(_gebiete())
                e = schreibe_bestand(datensaetze, DATEN, LAND, kreis_von, args.modus)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        orgs = art == "organisationen"
        ziel = f"{DATEN}/organisationen/" if orgs else f"{DATEN}/{LAND.upper()}/"
        print(f"{datei.name} → {ziel} (Modus {args.modus})")
        was = "Organisationen" if orgs else "Sportstätten"
        zeilen = [
            ("neu angelegt", e.neu, was),
            ("geändert", e.aktualisiert, was),
            ("unverändert", e.unveraendert, was),
            ("schon vorhanden", e.behalten, "(nicht verändert; --modus ergaenzen/aktualisieren)"),
            ("Sportanlagen neu", e.anlagen_neu, "zu vorhandenen Sportstätten"),
            ("Sportanlagen geändert", e.anlagen_geaendert, ""),
            ("ohne Koordinate", e.ohne_lage, "(übersprungen)"),
            (
                "ohne Sportstätte",
                e.ohne_sportstaette,
                "Sportanlagen (ID nicht in daten/, übersprungen)",
            ),
            ("doppelte ID", e.doppelt, "(nur der erste Eintrag übernommen)"),
            ("nicht in der Quelle", e.nicht_mehr_in_quelle, "Sportstätten (bleiben)"),
        ]
        for text, n, zusatz in zeilen:
            if n:
                print(f"  {text + ':':<23}{n} {zusatz}".rstrip())
        if e.entfernt:
            weg = ", ".join(f"{k} {v}×" for k, v in sorted(e.entfernt.items()))
            print(f"  entfernt (enthielt E-Mail-Adresse): {weg}")
        if e.regelverstoesse:
            felder = ", ".join(f"{k} {v}×" for k, v in e.regelverstoesse.most_common())
            print(f"  passen nicht zu den Regeln des Datenmodells: {felder} (übernommen)")


def cmd_organisationen(args):
    """Verzeichnis der Organisationen (daten/organisationen/): Stand zeigen, aus dem Bestand
    anlegen."""
    from .bestand import (
        lies_bestand,
        lies_organisationen,
        org_schluessel,
        org_verzeichnis,
        organisationen_aus_bestand,
        organisationen_von,
    )

    bestand = list(lies_bestand(DATEN))
    if args.aus_bestand:
        n = organisationen_aus_bestand(bestand, DATEN, typen=args.mit_art)
        print(f"{n} Organisationen in {DATEN}/organisationen/ angelegt")
    orgs = lies_organisationen(DATEN)
    verzeichnis = org_verzeichnis(orgs)
    namen = {org_schluessel(n) for d in bestand for _, n in organisationen_von(d)}
    fehlen = namen - set(verzeichnis)
    print(
        f"{len(orgs)} Organisationen im Verzeichnis, {sum(1 for o in orgs if o.get('typ'))} mit Art"
    )
    print(f"{len(namen) - len(fehlen)} von {len(namen)} Namen im Bestand sind im Verzeichnis")
    if fehlen:
        print("  fehlen, z. B.: " + "; ".join(sorted(fehlen)[:5]) + " (--aus-bestand legt sie an)")


def cmd_vorlage(args):
    """Vorlagen für eigene CSV-Dateien (alle Spalten aus dem Modell, eine Beispielzeile)."""
    from .einlesen import schreibe_vorlage

    for pfad in schreibe_vorlage(Path(args.ordner)):
        print(pfad)


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
    from .modell import schreibe_doku
    from .seite import schreibe_webseite

    bestand, organisationen = _lies_bestand()
    for hinweis in schreibe_doku(DATEN):
        print(hinweis)
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
        organisationen=organisationen,
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


def cmd_modell(args):
    """Datenmodell (modell.py) in daten/README.md und als Diagramm daten/datenmodell.svg."""
    from .modell import schreibe_doku

    if args.migrieren:
        from .bestand import migriere_bestand

        print(f"{migriere_bestand(DATEN)} Dateien in {DATEN}/ auf den Stand des Modells gebracht")
    for hinweis in schreibe_doku(DATEN):
        print(hinweis)


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

    sp = sub.add_parser(
        "bestand", help="CSV-Dateien in den Datenbestand daten/ übernehmen (siehe einlesen.py)"
    )
    sp.add_argument(
        "dateien", nargs="+", help="Atlas-Export, Tabelle der Sportstätten oder der Sportanlagen"
    )
    sp.add_argument(
        "--modus",
        default="neu",
        choices=["neu", "ergaenzen", "aktualisieren"],
        help="neu: nur Neues anlegen (Standard); ergaenzen: auch leere Felder füllen; "
        "aktualisieren: auch vorhandene Werte überschreiben",
    )
    sp.add_argument("--probe", action="store_true", help="nur zeigen, welche Spalte wohin geht")
    sp.set_defaults(func=cmd_bestand)

    sp = sub.add_parser(
        "organisationen",
        help="Verzeichnis der Organisationen (Eigentümer, Betreiber, Nutzer) zeigen bzw. anlegen",
    )
    sp.add_argument(
        "--aus-bestand",
        action="store_true",
        help="für jeden Eigentümer, Betreiber und Nutzer im Bestand ohne Eintrag eine Organisation anlegen",
    )
    sp.add_argument(
        "--mit-art",
        action="store_true",
        help="dabei die Art übernehmen, wenn sie bei den Sportstätten einheitlich angegeben ist",
    )
    sp.set_defaults(func=cmd_organisationen)

    sp = sub.add_parser("vorlage", help="Vorlagen für CSV-Dateien zum Einlesen schreiben")
    sp.add_argument("ordner", nargs="?", default="results/vorlagen")
    sp.set_defaults(func=cmd_vorlage)

    sp = sub.add_parser("einordnen", help="Sportstätten in den Ordner ihres Kreises verschieben")
    sp.set_defaults(func=cmd_einordnen)

    sp = sub.add_parser("seite", help="Webseite für GitHub Pages (docs/) erzeugen")
    sp.add_argument("--vorschau", action="store_true", help="danach lokal im Browser zeigen")
    sp.set_defaults(func=cmd_seite)

    sp = sub.add_parser(
        "modell", help="Datenmodell in daten/README.md und daten/datenmodell.svg schreiben"
    )
    sp.add_argument(
        "--migrieren",
        action="store_true",
        help="vorher die Dateien in daten/ anpassen (umbenannte Felder, z. B. baukosten_eur)",
    )
    sp.set_defaults(func=cmd_modell)

    alkis_cli.befehle(sub)

    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    from tqdm.contrib.logging import logging_redirect_tqdm

    with logging_redirect_tqdm():  # Log-Zeilen erscheinen über dem Fortschrittsbalken
        args.func(args)


if __name__ == "__main__":
    main()
