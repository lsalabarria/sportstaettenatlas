"""Befehle der Analyse ALKIS-Abgleich.

    sportstaettenatlas alkis         ALKIS laden, Sportstätten bauen, mit daten/ abgleichen
    sportstaettenatlas alkis-werte   vorkommende ALKIS-Werte zeigen (zum Anpassen der Regeln)

Ergebnis in results/out/; `sportstaettenatlas seite` bringt es auf die Webseite.
"""

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


def _laden(args, regeln):
    """ALKIS-Nutzung und -Gebäude per WFS laden (Cache in results/raw, fortsetzbar)."""
    import geopandas as gpd

    from . import wfs

    quelle = QUELLEN[args.land]
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
    return gpd.read_file(_cache(args, "nutzung")), gpd.read_file(_cache(args, "gebaeude"))


def cmd_alkis(args):
    """Vollständiger Abgleich: ALKIS laden → Sportstätten bauen → mit daten/ abgleichen."""
    from ...bestand import lies_bestand
    from ...http import Sitzung
    from .abgleich import anreichern, aus_bestand
    from .karte import schreibe_karte
    from .klassifikation import Regelwerk
    from .pipeline import baue, schreibe

    # zuerst den Bestand lesen: ein Fehler darin soll nicht erst nach dem Download auffallen
    try:
        bestand = list(lies_bestand(Path(args.bestand)))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Datenbestand {args.bestand}/: {exc}") from None
    if not bestand:
        raise SystemExit(f"Kein Datenbestand unter {args.bestand}/ – zuerst `bestand` ausführen.")

    ziel, quelle = Path(args.ziel), QUELLEN[args.land]
    regeln = Regelwerk.laden(args.regeln)
    print("1/3 ALKIS laden …")
    nutzung, gebaeude = _laden(args, regeln)
    print("2/3 Sportstätten und Sportanlagen bauen …")
    ergebnis = baue(nutzung, gebaeude, regeln)
    gpkg, *_ = schreibe(ergebnis, ziel, quelle, _bbox(args))
    st, an = ergebnis.sportstaetten, ergebnis.sportanlagen
    print(f"    {len(st)} Sportstätten, {len(an)} Sportanlagen aus ALKIS")

    print(f"3/3 mit dem Datenbestand abgleichen ({len(bestand)} Sportstätten in {args.bestand}/) …")
    st, an, bericht = anreichern(
        st,
        an,
        Sitzung(ERGEBNISSE / "cache" / "http", pause_s=args.pause),
        atlas=aus_bestand(bestand),
        alkis_quelle=None if args.ohne_alkis_vor_ort else quelle,
    )
    st.to_file(gpkg, layer="sportstaetten_angereichert", driver="GPKG")
    an.to_file(gpkg, layer="sportanlagen_angereichert", driver="GPKG")
    st.drop(columns="geometry").to_csv(ziel / "sportstaetten_angereichert.csv", index=False)
    an.drop(columns="geometry").to_csv(ziel / "sportanlagen_angereichert.csv", index=False)
    alle = [quelle.quellenvermerk.format(jahr=dt.datetime.now(dt.UTC).year), *bericht.lizenzen]
    (ziel / "QUELLENVERMERK.txt").write_text("\n".join(alle) + "\n", encoding="utf-8")
    bericht.abgleich_altbestand.to_csv(ziel / "abgleich_altbestand.csv", index=False)
    karte = schreibe_karte(
        an,
        st,
        ziel / "karte.html",
        quellenvermerk=" | ".join(alle),
        abgleich_altbestand=bericht.abgleich_altbestand,
    )

    print("\n".join(bericht.zeilen))
    print(f"\nErgebnis in {ziel}/ (u. a. {gpkg.name}, abgleich_altbestand.csv, {karte.name}).")
    print("Auf die Webseite bringen: uv run sportstaettenatlas seite")


def cmd_werte(args):
    """Alle vorkommenden Werte auflisten, um regeln.toml zu verfeinern (nutzt den Cache)."""
    from .klassifikation import Regelwerk

    regeln = Regelwerk.laden(args.regeln)
    nutzung, gebaeude = _laden(args, regeln)
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


def lies_ergebnis(ziel: Path):
    """Sportstätten und Sportanlagen aus results/out lesen – die abgeglichene Fassung."""
    import geopandas as gpd
    import pyogrio

    gpkg = ziel / "sportstaetten.gpkg"
    layer = {n for n, _ in pyogrio.list_layers(gpkg)}

    def lies(name):
        abgeglichen = f"{name}_angereichert"
        return gpd.read_file(gpkg, layer=abgeglichen if abgeglichen in layer else name)

    return lies("sportstaetten"), lies("sportanlagen")


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


def fuer_webseite(ziel: Path, land: str, ars_von=None):
    """Dateien für den Reiter „Analysen“ der Webseite – oder None ohne Ergebnis.

    Liefert (Titel, {Datei: Inhalt}, {Datei: Beschreibung}, Quellenvermerk).
    """
    from . import karte

    if not (ziel / "sportstaetten.gpkg").exists():
        return None
    staetten, anlagen = lies_ergebnis(ziel)
    dateien = karte.webdaten(staetten, anlagen, bericht(ziel), ars_von)
    return karte.TITEL, dateien, karte.DATEIEN, vermerk(ziel, land)


def befehle(sub) -> None:
    """Befehle `alkis` und `alkis-werte` an den Parser hängen."""

    def gemeinsam(sp):
        sp.add_argument("--land", default="rp", choices=sorted(QUELLEN))
        sp.add_argument(
            "--gebiet",
            default="rlp",
            choices=sorted(GEBIETE),
            help="Ausschnitt (Standard: ganz Rheinland-Pfalz; zum Ausprobieren koblenz-innenstadt)",
        )
        sp.add_argument("--bbox", help="eigener Ausschnitt xmin,ymin,xmax,ymax in EPSG:25832")
        sp.add_argument("--regeln", type=Path, help="eigene regeln.toml")
        sp.add_argument("--neu", action="store_true", help="ALKIS neu laden statt aus dem Cache")
        sp.add_argument("--kachel-km", type=float, default=10.0, help="Kachelgröße (Standard 10)")
        sp.add_argument(
            "--ohne-filter",
            action="store_true",
            help="keinen serverseitigen Vorfilter senden (lädt alle Gebäude – sehr viel)",
        )

    sp = sub.add_parser(
        "alkis", help="ALKIS laden, Sportstätten bauen und mit dem Datenbestand abgleichen"
    )
    gemeinsam(sp)
    sp.add_argument("--bestand", default="daten", help="Ordner des Datenbestands (Standard: daten)")
    sp.add_argument("--ziel", default=str(ZIEL), help="Ergebnis (Standard: results/out)")
    sp.add_argument(
        "--ohne-alkis-vor-ort",
        action="store_true",
        help="für 'nicht in ALKIS' nicht nachschlagen, welche Nutzung/Gebäude ALKIS dort führt",
    )
    sp.add_argument("--pause", type=float, default=1.0, help="Sekunden zwischen Anfragen je Host")
    sp.set_defaults(func=cmd_alkis)

    sp = sub.add_parser("alkis-werte", help="Vorkommende ALKIS-Werte und ihre Zuordnung zeigen")
    gemeinsam(sp)
    sp.add_argument("--alle", action="store_true", help="auch nicht zugeordnete Werte")
    sp.set_defaults(func=cmd_werte)
