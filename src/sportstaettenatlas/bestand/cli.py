"""Befehle zum Datenbestand: prüfen, einordnen, Sportkomplexe zuordnen."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..hilfen import DATEN, LAND

REGELVERSTOESSE = (
    Path("erzeugt") / "regelverstoesse.csv"
)  # in daten/, im Git: für alle ohne Installation


def lade_gebiete():
    """Verwaltungsgebiete (einmal vom BKG geladen, dann aus results/cache)."""
    from . import gebiete as gb

    try:
        return gb.lade(LAND)
    except Exception as exc:  # noqa: BLE001 – Netz, Dienst geändert …
        raise SystemExit(f"Verwaltungsgebiete nicht verfügbar ({exc}).") from None


def kreis_von_bei_bedarf():
    """(lon, lat) → Kreis-Ordner; die Verwaltungsgebiete werden erst beim ersten Aufruf geladen
    (gebraucht nur, wenn eine neue Sportstätte angelegt wird)."""
    from . import kreis_ordner

    geladen: list = []

    def kreis_von(lon, lat):
        if not geladen:
            geladen.append(kreis_ordner(lade_gebiete()))
        return geladen[0](lon, lat)

    return kreis_von


def lies_daten():
    """Datenbestand und Verzeichnis der Organisationen lesen; Fehler im Aufbau brechen ab,
    Verstöße gegen die Regeln des Modells kommen als Liste (Datei, Meldung) mit."""
    from . import lies_bestand, lies_organisationen, lies_sportkomplexe, lies_stuetzpunkte

    verstoesse: list = []
    try:
        bestand = list(lies_bestand(DATEN, verstoesse))
        organisationen = lies_organisationen(DATEN, verstoesse)
        lies_sportkomplexe(DATEN, verstoesse)  # nur die Regeln des Modells; validate liest selbst
        lies_stuetzpunkte(DATEN, verstoesse)
    except ValueError as exc:
        raise SystemExit(f"Datenbestand: {exc}") from None
    return bestand, organisationen, verstoesse


def pruefe_und_melde(bestand, organisationen, verstoesse, gebiete) -> None:
    """Regeln des Modells und Prüfungen aus bestand/pruefung.py nach daten/erzeugt/regelverstoesse.csv – im
    Git, damit sie jeder ohne Installation sieht (auf GitHub als Tabelle mit Suche). Sortiert,
    damit ein Commit nur zeigt, was sich wirklich geändert hat."""
    import csv

    from .pruefung import DATENMODELL, name_zu, pruefe

    alle = [(d, DATENMODELL, m) for d, m in verstoesse]
    alle += pruefe(bestand, organisationen, gebiete, DATEN)
    alle = sorted(set(alle))
    datei = DATEN / REGELVERSTOESSE
    if alle:
        datei.parent.mkdir(parents=True, exist_ok=True)
        with datei.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["datei", "name", "pruefung", "meldung"])
            cache: dict = {}
            w.writerows((d, name_zu(d, cache), p, m) for d, p, m in alle)
        je = Counter(p for _, p, _ in alle)
        print(
            f"Hinweis: {len(alle)} Auffälligkeiten "
            f"({', '.join(f'{k} {v}×' for k, v in je.most_common(6))}) – Liste: {datei}"
        )
    elif datei.exists():
        datei.unlink()


def cmd_pruefen(args):
    """Nur prüfen: Regeln des Datenmodells und bestand/pruefung.py, Liste nach daten/."""
    bestand, organisationen, verstoesse = lies_daten()
    pruefe_und_melde(bestand, organisationen, verstoesse, lade_gebiete())
    print(f"{len(bestand)} Sportstätten, {len(organisationen)} Organisationen geprüft.")


def cmd_einordnen(args):
    """Organisationen in den Ordner ihrer Art, Sportstätten und Sportkomplexe, deren Lage in
    einem anderen Kreis liegt, dorthin verschieben."""
    from . import einordnen, kreis_ordner, organisationen_einordnen, sportkomplexe_einordnen

    if n := organisationen_einordnen(DATEN):
        print(f"{n} Organisationen in den Ordner ihrer Art verschoben.")
    kreis_von = kreis_ordner(lade_gebiete())
    try:
        n = einordnen(DATEN, kreis_von)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print(f"{n} Sportstätten verschoben." if n else "Alle Sportstätten liegen im richtigen Kreis.")
    if n := sportkomplexe_einordnen(DATEN, kreis_von):
        print(f"{n} Sportkomplexe verschoben.")


def cmd_sportkomplex(args):
    """Sportkomplex anlegen und Sportstätten zuordnen, ergänzen oder herausnehmen."""
    from . import (
        OHNE_KREIS,
        finde_staette,
        lies_sportkomplexe,
        ordne_sportkomplex_zu,
        schreibe_sportkomplex,
    )

    try:
        ids = [finde_staette(DATEN, i).name for i in args.ids]
        komplexe = {k["id"]: k for k in lies_sportkomplexe(DATEN)}
        if args.entfernen:
            n = len(ordne_sportkomplex_zu(DATEN, None, ids))
            print(f"{n} Sportstätten aus ihrem Sportkomplex genommen.")
            return
        if args.zu:
            treffer = [i for i in komplexe if i.startswith(args.zu)]
            if len(treffer) != 1:
                raise ValueError(f"Sportkomplex {args.zu}: nicht gefunden oder mehrdeutig")
            k = komplexe[treffer[0]]
            if args.name:
                k = {**k, "name": args.name}
                schreibe_sportkomplex(DATEN, k, k["_ordner"])
        else:
            if not args.name:
                raise ValueError("Neuer Sportkomplex: --name angeben (oder --zu ID)")
            if len(ids) < 2:
                raise ValueError("Ein Sportkomplex braucht mindestens zwei Sportstätten")
            k = {"name": args.name}
            kreise = [finde_staette(DATEN, i).parent.name for i in ids]
            pfad = schreibe_sportkomplex(DATEN, k, max(set(kreise), key=kreise.count) or OHNE_KREIS)
            k["id"] = pfad.stem
            print(f"Sportkomplex „{args.name}“ angelegt: {pfad}")
        n = len(ordne_sportkomplex_zu(DATEN, k["id"], ids))
        print(f"{n} Sportstätten dem Sportkomplex „{k['name']}“ zugeordnet.")
    except ValueError as exc:
        raise SystemExit(str(exc)) from None


def befehle(sub) -> None:
    """Befehle dieses Teils an den Parser von `sportstaettenatlas` hängen."""
    sp = sub.add_parser(
        "einordnen",
        help="Sportstätten und Sportkomplexe in den Ordner ihres Kreises, Organisationen in den "
        "ihrer Art verschieben",
    )
    sp.set_defaults(func=cmd_einordnen)

    sp = sub.add_parser(
        "sportkomplex",
        help="Sportkomplex anlegen (--name) oder ergänzen (--zu) und Sportstätten zuordnen",
    )
    sp.add_argument(
        "ids", nargs="+", metavar="ID", help="Sportstätten (ID oder ihr Anfang, ab 8 Zeichen)"
    )
    sp.add_argument("--name", help="Name eines neuen Sportkomplexes (oder neuer Name mit --zu)")
    sp.add_argument("--zu", metavar="KOMPLEX", help="vorhandener Sportkomplex (ID oder ihr Anfang)")
    sp.add_argument(
        "--entfernen", action="store_true", help="die Sportstätten aus ihrem Sportkomplex nehmen"
    )
    sp.set_defaults(func=cmd_sportkomplex)

    sp = sub.add_parser(
        "pruefen",
        help="Datenbestand prüfen (Datenmodell und weitere Prüfungen) – Liste in "
        "daten/erzeugt/regelverstoesse.csv, ohne die Webseite zu bauen",
    )
    sp.set_defaults(func=cmd_pruefen)
