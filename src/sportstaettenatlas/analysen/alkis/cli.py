"""Befehl `sportstaettenatlas alkis`: ALKIS laden, Sportstätten bauen, mit daten/ abgleichen.

Ergebnis in results/out/ (sportstaetten.gpkg, abgleich_altbestand.csv, QUELLENVERMERK.txt);
`sportstaettenatlas seite` bringt es mit `fuer_webseite` auf die Webseite.
"""

from __future__ import annotations

from pathlib import Path

from ...hilfen import ERGEBNISSE
from .quellen import GEBIETE, RP

ZIEL = ERGEBNISSE / "out"


def cmd_alkis(args):
    """ALKIS laden (Cache in results/raw) → Sportstätten bauen → mit daten/ abgleichen."""
    from ...bestand import lies_bestand
    from . import wfs
    from .abgleich import anreichern, aus_bestand
    from .klassifikation import Regelwerk
    from .pipeline import baue, schreibe

    # zuerst den Bestand lesen: ein Fehler darin soll nicht erst nach dem Download auffallen
    try:
        bestand = list(lies_bestand(Path(args.bestand)))
    except ValueError as exc:
        raise SystemExit(f"Datenbestand: {exc}") from None
    if not bestand:
        raise SystemExit(f"Kein Datenbestand unter {args.bestand}/ – zuerst `bestand` ausführen.")

    regeln = Regelwerk.laden()
    bbox = GEBIETE[args.gebiet]
    print("1/3 ALKIS laden …")
    roh = {}
    for typ, typename, feld, muster in (
        ("nutzung", RP.typ_nutzung, "nutzart", [regeln.nutzart]),
        ("gebaeude", RP.typ_gebaeude, "funktion", regeln.stichwoerter_gebaeude()),
    ):
        cache = ERGEBNISSE / "raw" / f"rp_{args.gebiet}_{typ}.gpkg"
        roh[typ] = wfs.lade(RP, typename, bbox, cache, feld=feld, muster=muster, neu=args.neu)

    print("2/3 Sportstätten und Sportanlagen bauen …")
    ergebnis = baue(roh["nutzung"], roh["gebaeude"], regeln)
    print(f"    {len(ergebnis.sportstaetten)} Sportstätten, {len(ergebnis.sportanlagen)} Anlagen")

    print(f"3/3 mit dem Datenbestand abgleichen ({len(bestand)} Sportstätten) …")
    st, an, bericht = anreichern(
        ergebnis.sportstaetten, ergebnis.sportanlagen, aus_bestand(bestand)
    )
    schreibe(st, an, bericht, ZIEL, RP, bbox)
    print("\n".join(bericht.zeilen))
    print(f"\nErgebnis in {ZIEL}/. Auf die Webseite bringen: uv run sportstaettenatlas seite")


def fuer_webseite(ars_von=None):
    """(Titel, {Datei: Inhalt}, {Datei: Beschreibung}, Quellenvermerk) – None ohne Ergebnis."""
    gpkg = ZIEL / "sportstaetten.gpkg"
    if not gpkg.exists():
        return None
    import geopandas as gpd
    import pandas as pd

    from . import webdaten

    csv = ZIEL / "abgleich_altbestand.csv"
    bericht = pd.read_csv(csv) if csv.exists() else None
    staetten = gpd.read_file(gpkg, layer="sportstaetten")
    anlagen = gpd.read_file(gpkg, layer="sportanlagen")
    dateien = webdaten.webdaten(staetten, anlagen, bericht, ars_von)
    zeilen = (ZIEL / "QUELLENVERMERK.txt").read_text("utf-8").splitlines()
    vermerk = " | ".join(z for z in zeilen if z and not z.startswith("Lizenz:"))
    return webdaten.TITEL, dateien, webdaten.DATEIEN, vermerk


def befehle(sub) -> None:
    sp = sub.add_parser(
        "alkis", help="ALKIS laden, Sportstätten bauen und mit dem Datenbestand abgleichen"
    )
    sp.add_argument(
        "--gebiet",
        default="rlp",
        choices=sorted(GEBIETE),
        help="Ausschnitt (Standard: ganz Rheinland-Pfalz; zum Ausprobieren koblenz-innenstadt)",
    )
    sp.add_argument("--neu", action="store_true", help="ALKIS neu laden statt aus dem Cache")
    sp.add_argument("--bestand", default="daten", help="Ordner des Datenbestands (Standard: daten)")
    sp.set_defaults(func=cmd_alkis)
