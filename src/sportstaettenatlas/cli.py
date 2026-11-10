"""Kommandozeile: sportstaettenatlas laden | bauen | werte | anreichern | karte | seite | lauf."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .quellen import GEBIETE, QUELLEN

DATEN = Path("data")


def _bbox(args) -> tuple[float, float, float, float]:
    if args.bbox:
        teile = [float(x) for x in args.bbox.split(",")]
        if len(teile) != 4:
            raise SystemExit("--bbox erwartet xmin,ymin,xmax,ymax (EPSG:25832)")
        return tuple(teile)  # type: ignore[return-value]
    return GEBIETE[args.gebiet]


def _cache(args, typ: str) -> Path:
    return DATEN / "raw" / f"{args.land}_{args.gebiet if not args.bbox else 'bbox'}_{typ}.gpkg"


def cmd_laden(args):
    from . import wfs
    from .klassifikation import Regelwerk

    quelle = QUELLEN[args.land]
    bbox = _bbox(args)
    regeln = Regelwerk.laden(args.regeln)
    filter_an = not args.ohne_filter
    auftraege = [
        ("nutzung", quelle.typ_nutzung, "nutzart", [regeln.nutzart]),
        ("gebaeude", quelle.typ_gebaeude, "funktion", regeln.stichwoerter_gebaeude()),
    ]
    for typ, typename, feld, muster in auftraege:
        wfs.lade(
            quelle,
            typename,
            bbox,
            ziel=_cache(args, typ),
            feld=feld if filter_an else None,
            muster=muster if filter_an else (),
            kachel_m=args.kachel_km * 1000,
            neu=args.neu,
        )


def _lies_roh(args):
    import geopandas as gpd

    pfade = {t: _cache(args, t) for t in ("nutzung", "gebaeude")}
    for p in pfade.values():
        if not p.exists():
            raise SystemExit(f"{p} fehlt – zuerst `sportstaettenatlas laden` ausführen.")
    return gpd.read_file(pfade["nutzung"]), gpd.read_file(pfade["gebaeude"])


def cmd_bauen(args):
    from .klassifikation import Regelwerk
    from .pipeline import baue, schreibe

    nutzung, gebaeude = _lies_roh(args)
    regeln = Regelwerk.laden(args.regeln)
    ergebnis = baue(nutzung, gebaeude, regeln)
    dateien = schreibe(ergebnis, Path(args.ziel), QUELLEN[args.land], _bbox(args))

    st, an = ergebnis.sportstaetten, ergebnis.sportanlagen
    print(f"Sportstätten:  {len(st)}")
    print(f"Sportanlagen:  {len(an)}")
    if len(an):
        print(an.groupby(["rolle", "typgruppe"]).size().to_string())
        print(f"davon zu prüfen: {int(an['pruefen'].fillna(True).astype(bool).sum())}")
    print("\nGeschrieben: " + "\n             ".join(str(d) for d in dateien))


def _lies_ergebnis(ziel: Path):
    """Sportstätten und Sportanlagen lesen – angereicherte Fassung bevorzugt."""
    import geopandas as gpd
    import pyogrio

    gpkg = ziel / "sportstaetten.gpkg"
    if not gpkg.exists():
        raise SystemExit(f"{gpkg} fehlt – zuerst `sportstaettenatlas bauen` ausführen.")
    layer = {n for n, _ in pyogrio.list_layers(gpkg)}
    if "sportanlagen" not in layer:
        raise SystemExit(
            f"{gpkg} stammt aus einer älteren Version – bitte `sportstaettenatlas bauen` "
            "erneut ausführen (die ALKIS-Daten kommen aus dem Cache)."
        )

    def lies(name):
        return gpd.read_file(
            gpkg, layer=f"{name}_angereichert" if f"{name}_angereichert" in layer else name
        )

    return gpkg, lies("sportstaetten"), lies("sportanlagen")


def cmd_werte(args):
    """Alle vorkommenden Werte auflisten, um regeln.toml zu verfeinern."""
    from .klassifikation import Regelwerk

    nutzung, gebaeude = _lies_roh(args)
    regeln = Regelwerk.laden(args.regeln)
    print("== Nutzung: Bezeichnungen der Sport-, Freizeit- und Erholungsflächen ==")
    if "nutzart" in nutzung.columns:
        sfe = nutzung[nutzung["nutzart"].map(regeln.ist_sportflaeche)]
        spalte = "bez" if "bez" in sfe.columns else "funktion"
        for wert, n in sfe[spalte].fillna("(leer)").value_counts().items():
            t = regeln.nutzung(wert)
            print(f"{n:6d}  {wert:<50} -> {t.typ if t else '–'}")
    print("\n== Gebäude/Bauwerke: Funktionen ==")
    if "funktion" in gebaeude.columns:
        for wert, n in gebaeude["funktion"].fillna("(leer)").value_counts().items():
            t = regeln.gebaeude(wert)
            if t or args.alle:
                print(f"{n:6d}  {wert:<50} -> {t.typ if t else '–'}")
        if not args.alle:
            print("(nur zugeordnete Funktionen; --alle zeigt sämtliche Werte)")


def cmd_anreichern(args):
    """Abgleich mit dem bisherigen Sportstättenatlas – mit Herkunft und Verifikation."""
    import datetime as dt

    import geopandas as gpd

    from .anreicherung.abgleich import anreichern
    from .anreicherung.http import Sitzung
    from .karte import schreibe_karte

    ziel = Path(args.ziel)
    gpkg, _, _ = _lies_ergebnis(ziel)  # prüft Version des GeoPackages
    # immer von den unangereicherten ALKIS-Daten ausgehen
    staetten = gpd.read_file(gpkg, layer="sportstaetten")
    anlagen = gpd.read_file(gpkg, layer="sportanlagen")

    sitzung = Sitzung(DATEN / "cache" / "http", pause_s=args.pause)
    st, an, bericht = anreichern(
        staetten,
        anlagen,
        sitzung,
        altbestand=Path(args.altbestand),
        alkis_quelle=None if args.ohne_alkis_vor_ort else QUELLEN[args.land],
    )

    st.to_file(gpkg, layer="sportstaetten_angereichert", driver="GPKG")
    an.to_file(gpkg, layer="sportanlagen_angereichert", driver="GPKG")
    csv_st = ziel / "sportstaetten_angereichert.csv"
    csv_an = ziel / "sportanlagen_angereichert.csv"
    st.drop(columns="geometry").to_csv(csv_st, index=False, encoding="utf-8")
    an.drop(columns="geometry").to_csv(csv_an, index=False, encoding="utf-8")
    quelle = QUELLEN[args.land]
    vermerk = quelle.quellenvermerk.format(jahr=dt.datetime.now(dt.UTC).year)
    alle = [vermerk, *bericht.lizenzen]
    (ziel / "QUELLENVERMERK.txt").write_text("\n".join(alle) + "\n", encoding="utf-8")
    abgleich_csv = ziel / "abgleich_altbestand.csv"
    if bericht.abgleich_altbestand is not None:
        bericht.abgleich_altbestand.to_csv(abgleich_csv, index=False, encoding="utf-8")
        bericht(f"Abgleich Altbestand ↔ ALKIS: {abgleich_csv}")
    else:
        abgleich_csv.unlink(missing_ok=True)  # kein veralteter Bericht neben neuen Daten
    (ziel / "osm_ohne_alkis.csv").unlink(missing_ok=True)  # Datei früherer Versionen
    karte = schreibe_karte(
        an,
        st,
        ziel / "karte.html",
        quellenvermerk=" | ".join(alle),
        abgleich_altbestand=bericht.abgleich_altbestand,
    )

    print("\n".join(bericht.zeilen))
    print(
        f"\nGeschrieben: {csv_st}\n             {csv_an}"
        f"\n             {gpkg} (Layer *_angereichert)\n             {karte}"
    )


def cmd_karte(args):
    """Karte aus einem vorhandenen Ergebnis (sportstaetten.gpkg) neu erzeugen."""
    from .karte import schreibe_karte

    ziel = Path(args.ziel)
    _, staetten, anlagen = _lies_ergebnis(ziel)
    pfad = schreibe_karte(
        anlagen,
        staetten,
        ziel / "karte.html",
        quellenvermerk=_vermerk(ziel, args.land),
        abgleich_altbestand=_abgleich(ziel),
    )
    print(f"Karte: {pfad}")
    if args.oeffnen:
        import webbrowser

        webbrowser.open(pfad.resolve().as_uri())


def _vermerk(ziel: Path, land: str) -> str:
    """Quellenvermerk für Karte und Webseite (ohne die Lizenz-Zeile)."""
    import datetime as dt

    vermerk_datei = ziel / "QUELLENVERMERK.txt"
    vermerk = (
        " | ".join(
            vermerk_datei.read_text("utf-8").splitlines()[:1]
            + [
                z
                for z in vermerk_datei.read_text("utf-8").splitlines()[1:]
                if not z.startswith("Lizenz:")
            ]
        )
        if vermerk_datei.exists()
        else QUELLEN[land].quellenvermerk.format(jahr=dt.datetime.now(dt.UTC).year)
    )
    # Vermerk früherer Läufe: der Atlas-Bestand war damals nur intern
    return vermerk.replace(" (nur intern)", "")


def _abgleich(ziel: Path):
    abgleich = None
    if (ziel / "abgleich_altbestand.csv").exists():
        import pandas as pd

        abgleich = pd.read_csv(ziel / "abgleich_altbestand.csv")
        if not {"lon", "lat"} <= set(abgleich.columns):
            print(
                "Hinweis: abgleich_altbestand.csv stammt aus einer älteren Version (ohne "
                "Koordinaten). Für die Atlas-Punkte `anreichern --altbestand …` neu ausführen."
            )
    return abgleich


def cmd_seite(args):
    """Statische Webseite für GitHub Pages (Ordner docs/) erzeugen."""
    from .seite import schreibe_webseite

    ziel, ausgabe = Path(args.ziel), Path(args.ausgabe)
    _, staetten, anlagen = _lies_ergebnis(ziel)
    info = schreibe_webseite(
        anlagen,
        staetten,
        ausgabe,
        quellenvermerk=_vermerk(ziel, args.land),
        abgleich_altbestand=_abgleich(ziel),
        titel=args.titel,
    )
    print(f"Webseite: {ausgabe}/  ({info['gesamt'] / 1e6:.1f} MB)")
    for name, _, anzahl, groesse in info["dateien"]:
        print(f"  daten/{name}: {anzahl} Objekte, {groesse / 1e6:.1f} MB")
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
        print("    in konfig.js den Link zum Meldeformular eintragen.")
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


def cmd_lauf(args):
    cmd_laden(args)
    cmd_bauen(args)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="sportstaettenatlas",
        description="Sportstätten und Sportanlagen aus offenen ALKIS-Daten ableiten und anreichern.",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="befehl", required=True)

    def gemeinsam(sp):
        sp.add_argument("--land", default="rp", choices=sorted(QUELLEN))
        sp.add_argument("--gebiet", default="koblenz-innenstadt", choices=sorted(GEBIETE))
        sp.add_argument("--bbox", help="eigener Ausschnitt xmin,ymin,xmax,ymax in EPSG:25832")
        sp.add_argument("--regeln", type=Path, help="eigene regeln.toml")

    def laden_optionen(sp):
        sp.add_argument("--neu", action="store_true", help="Cache ignorieren, alles neu laden")
        sp.add_argument("--kachel-km", type=float, default=10.0, help="Kachelgröße (Standard 10)")
        sp.add_argument(
            "--ohne-filter",
            action="store_true",
            help="keinen serverseitigen Vorfilter senden (lädt alle Gebäude – sehr viel)",
        )

    sp = sub.add_parser("laden", help="ALKIS-Daten per WFS laden (Cache in data/raw)")
    gemeinsam(sp)
    laden_optionen(sp)
    sp.set_defaults(func=cmd_laden)

    sp = sub.add_parser("bauen", help="Tabellen Sportstätten und Sportanlagen bauen")
    gemeinsam(sp)
    sp.add_argument("--ziel", default=str(DATEN / "out"))
    sp.set_defaults(func=cmd_bauen)

    sp = sub.add_parser("werte", help="Vorkommende ALKIS-Werte und ihre Zuordnung zeigen")
    gemeinsam(sp)
    sp.add_argument("--alle", action="store_true")
    sp.set_defaults(func=cmd_werte)

    sp = sub.add_parser(
        "anreichern", help="Mit dem bisherigen Sportstättenatlas abgleichen und verifizieren"
    )
    sp.add_argument("--land", default="rp", choices=sorted(QUELLEN))
    sp.add_argument("--ziel", default=str(DATEN / "out"))
    sp.add_argument(
        "--altbestand",
        required=True,
        help="Export des bisherigen Sportstättenatlas RLP (CSV) oder Ordner mit CSV-Dateien",
    )
    sp.add_argument(
        "--ohne-alkis-vor-ort",
        action="store_true",
        help="für 'nur Atlas' nicht nachschlagen, welche Nutzung/Gebäude ALKIS dort führt",
    )
    sp.add_argument("--pause", type=float, default=1.0, help="Sekunden zwischen Anfragen je Host")
    sp.set_defaults(func=cmd_anreichern)

    sp = sub.add_parser("karte", help="Karte (karte.html) aus vorhandenem Ergebnis erzeugen")
    sp.add_argument("--land", default="rp", choices=sorted(QUELLEN))
    sp.add_argument("--ziel", default=str(DATEN / "out"))
    sp.add_argument("--oeffnen", action="store_true", help="Karte im Browser öffnen")
    sp.set_defaults(func=cmd_karte)

    sp = sub.add_parser("seite", help="Webseite für GitHub Pages (Ordner docs/) erzeugen")
    sp.add_argument("--land", default="rp", choices=sorted(QUELLEN))
    sp.add_argument("--ziel", default=str(DATEN / "out"), help="Ergebnis von bauen/anreichern")
    sp.add_argument("--ausgabe", default="docs", help="Ordner der Webseite (Standard: docs)")
    sp.add_argument("--titel", default="Sportstättenatlas Rheinland-Pfalz")
    sp.add_argument("--vorschau", action="store_true", help="danach lokal im Browser zeigen")
    sp.add_argument("--port", type=int, default=8000)
    sp.set_defaults(func=cmd_seite)

    sp = sub.add_parser("lauf", help="laden + bauen")
    gemeinsam(sp)
    laden_optionen(sp)
    sp.add_argument("--ziel", default=str(DATEN / "out"))
    sp.set_defaults(func=cmd_lauf)

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
