"""Befehle `sportstaettenatlas alkis laden | bauen | werte | abgleich | karte | lauf`."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from ...hilfen import ERGEBNISSE
from .quellen import GEBIETE, QUELLEN

ZIEL = ERGEBNISSE / "out"


def _bbox(args) -> tuple[float, float, float, float]:
    if args.bbox:
        teile = [float(x) for x in args.bbox.split(",")]
        if len(teile) != 4:
            raise SystemExit("--bbox erwartet xmin,ymin,xmax,ymax (EPSG:25832)")
        return tuple(teile)  # type: ignore[return-value]
    return GEBIETE[args.gebiet]


def _cache(args, typ: str) -> Path:
    return ERGEBNISSE / "raw" / f"{args.land}_{args.gebiet if not args.bbox else 'bbox'}_{typ}.gpkg"


def cmd_laden(args):
    from . import wfs
    from .klassifikation import Regelwerk

    quelle = QUELLEN[args.land]
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
            _bbox(args),
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
            raise SystemExit(f"{p} fehlt – zuerst `sportstaettenatlas alkis laden` ausführen.")
    return gpd.read_file(pfade["nutzung"]), gpd.read_file(pfade["gebaeude"])


def cmd_bauen(args):
    from .klassifikation import Regelwerk
    from .pipeline import baue, schreibe

    nutzung, gebaeude = _lies_roh(args)
    ergebnis = baue(nutzung, gebaeude, Regelwerk.laden(args.regeln))
    dateien = schreibe(ergebnis, Path(args.ziel), QUELLEN[args.land], _bbox(args))

    st, an = ergebnis.sportstaetten, ergebnis.sportanlagen
    print(f"Sportstätten:  {len(st)}")
    print(f"Sportanlagen:  {len(an)}")
    if len(an):
        print(an.groupby(["rolle", "typgruppe"]).size().to_string())
        print(f"davon zu prüfen: {int(an['pruefen'].fillna(True).astype(bool).sum())}")
    print("\nGeschrieben: " + "\n             ".join(str(d) for d in dateien))


def lies_ergebnis(ziel: Path, roh: bool = False):
    """Sportstätten und Sportanlagen lesen – die abgeglichene Fassung, wenn vorhanden."""
    import geopandas as gpd
    import pyogrio

    gpkg = ziel / "sportstaetten.gpkg"
    if not gpkg.exists():
        raise SystemExit(f"{gpkg} fehlt – zuerst `sportstaettenatlas alkis bauen` ausführen.")
    layer = {n for n, _ in pyogrio.list_layers(gpkg)}

    def lies(name):
        abgeglichen = f"{name}_angereichert"
        return gpd.read_file(gpkg, layer=abgeglichen if abgeglichen in layer and not roh else name)

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


def cmd_abgleich(args):
    """Abgleich mit dem Datenbestand (daten/) – mit Herkunft der Angaben und Verifikation."""
    from ...bestand import lies_bestand
    from ...http import Sitzung
    from .abgleich import anreichern, aus_bestand
    from .karte import schreibe_karte

    ziel = Path(args.ziel)
    gpkg, staetten, anlagen = lies_ergebnis(ziel, roh=True)  # immer von ALKIS allein ausgehen
    try:
        bestand = list(lies_bestand(Path(args.bestand)))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Datenbestand {args.bestand}/: {exc}") from None
    if not bestand:
        raise SystemExit(f"Kein Datenbestand unter {args.bestand}/ – zuerst `bestand` ausführen.")
    st, an, bericht = anreichern(
        staetten,
        anlagen,
        Sitzung(ERGEBNISSE / "cache" / "http", pause_s=args.pause),
        atlas=aus_bestand(bestand),
        alkis_quelle=None if args.ohne_alkis_vor_ort else QUELLEN[args.land],
    )

    st.to_file(gpkg, layer="sportstaetten_angereichert", driver="GPKG")
    an.to_file(gpkg, layer="sportanlagen_angereichert", driver="GPKG")
    csv_st = ziel / "sportstaetten_angereichert.csv"
    csv_an = ziel / "sportanlagen_angereichert.csv"
    st.drop(columns="geometry").to_csv(csv_st, index=False, encoding="utf-8")
    an.drop(columns="geometry").to_csv(csv_an, index=False, encoding="utf-8")
    vermerk = QUELLEN[args.land].quellenvermerk.format(jahr=dt.datetime.now(dt.UTC).year)
    alle = [vermerk, *bericht.lizenzen]
    (ziel / "QUELLENVERMERK.txt").write_text("\n".join(alle) + "\n", encoding="utf-8")
    bericht_csv = ziel / "abgleich_altbestand.csv"
    bericht.abgleich_altbestand.to_csv(bericht_csv, index=False, encoding="utf-8")
    karte = schreibe_karte(
        an,
        st,
        ziel / "karte.html",
        quellenvermerk=" | ".join(alle),
        abgleich_altbestand=bericht.abgleich_altbestand,
    )

    print("\n".join(bericht.zeilen))
    print(
        f"\nGeschrieben: {csv_st}\n             {csv_an}\n             {bericht_csv}"
        f"\n             {gpkg} (Layer *_angereichert)\n             {karte}"
    )


def vermerk(ziel: Path, land: str) -> str:
    """Quellenvermerk für Karte und Webseite (ohne die Lizenz-Zeile)."""
    datei = ziel / "QUELLENVERMERK.txt"
    if not datei.exists():
        return QUELLEN[land].quellenvermerk.format(jahr=dt.datetime.now(dt.UTC).year)
    zeilen = datei.read_text("utf-8").splitlines()
    text = " | ".join(z for z in zeilen if z and not z.startswith("Lizenz:"))
    return text.replace(" (nur intern)", "")  # Vermerk früherer Läufe


def bericht(ziel: Path):
    """Bericht des Abgleichs (abgleich_altbestand.csv) oder None."""
    pfad = ziel / "abgleich_altbestand.csv"
    if not pfad.exists():
        return None
    import pandas as pd

    return pd.read_csv(pfad)


def cmd_karte(args):
    """karte.html aus einem vorhandenen Ergebnis neu erzeugen."""
    from .karte import schreibe_karte

    ziel = Path(args.ziel)
    _, staetten, anlagen = lies_ergebnis(ziel)
    pfad = schreibe_karte(
        anlagen,
        staetten,
        ziel / "karte.html",
        quellenvermerk=vermerk(ziel, args.land),
        abgleich_altbestand=bericht(ziel),
    )
    print(f"Karte: {pfad}")
    if args.oeffnen:
        import webbrowser

        webbrowser.open(pfad.resolve().as_uri())


def fuer_webseite(ziel: Path, land: str, ars_von=None):
    """Dateien für den Reiter „Analysen“ der Webseite – oder None ohne Ergebnis.

    Liefert (Titel, {Datei: Inhalt}, {Datei: Beschreibung}, Quellenvermerk).
    """
    from . import karte

    if not (ziel / "sportstaetten.gpkg").exists():
        return None
    _, staetten, anlagen = lies_ergebnis(ziel)
    dateien = karte.webdaten(staetten, anlagen, bericht(ziel), ars_von)
    return karte.TITEL, dateien, karte.DATEIEN, vermerk(ziel, land)


def cmd_lauf(args):
    cmd_laden(args)
    cmd_bauen(args)


def befehle(sub) -> None:
    """Befehlsgruppe `alkis` an den Parser hängen."""
    gruppe = sub.add_parser(
        "alkis", help="Sportstätten aus ALKIS ableiten und mit dem Atlas abgleichen"
    ).add_subparsers(dest="alkis_befehl", required=True)

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

    sp = gruppe.add_parser("laden", help="ALKIS-Daten per WFS laden (Cache in results/raw)")
    gemeinsam(sp)
    laden_optionen(sp)
    sp.set_defaults(func=cmd_laden)

    sp = gruppe.add_parser("bauen", help="Tabellen Sportstätten und Sportanlagen bauen")
    gemeinsam(sp)
    sp.add_argument("--ziel", default=str(ZIEL))
    sp.set_defaults(func=cmd_bauen)

    sp = gruppe.add_parser("lauf", help="laden + bauen")
    gemeinsam(sp)
    laden_optionen(sp)
    sp.add_argument("--ziel", default=str(ZIEL))
    sp.set_defaults(func=cmd_lauf)

    sp = gruppe.add_parser("werte", help="Vorkommende ALKIS-Werte und ihre Zuordnung zeigen")
    gemeinsam(sp)
    sp.add_argument("--alle", action="store_true")
    sp.set_defaults(func=cmd_werte)

    sp = gruppe.add_parser("abgleich", help="Mit dem Datenbestand (daten/) abgleichen")
    sp.add_argument("--land", default="rp", choices=sorted(QUELLEN))
    sp.add_argument("--ziel", default=str(ZIEL))
    sp.add_argument("--bestand", default="daten", help="Ordner des Datenbestands (Standard: daten)")
    sp.add_argument(
        "--ohne-alkis-vor-ort",
        action="store_true",
        help="für 'nur Atlas' nicht nachschlagen, welche Nutzung/Gebäude ALKIS dort führt",
    )
    sp.add_argument("--pause", type=float, default=1.0, help="Sekunden zwischen Anfragen je Host")
    sp.set_defaults(func=cmd_abgleich)

    sp = gruppe.add_parser("karte", help="karte.html aus vorhandenem Ergebnis erzeugen")
    sp.add_argument("--land", default="rp", choices=sorted(QUELLEN))
    sp.add_argument("--ziel", default=str(ZIEL))
    sp.add_argument("--oeffnen", action="store_true", help="Karte im Browser öffnen")
    sp.set_defaults(func=cmd_karte)
