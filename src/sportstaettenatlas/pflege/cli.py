"""Befehle zur Pflege des Bestands: CSV einlesen, Organisationen, Vorschläge, Vorlagen,
migrieren – alles, was daten/ verändert."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..bestand.cli import (
    kreis_von_bei_bedarf,
    lade_gebiete,
)
from ..hilfen import DATEN, LAND


def cmd_bestand(args):
    """CSV-Dateien (Atlas-Export, Sportstätten, Sportanlagen, Sportkomplexe, Stützpunkte oder
    Organisationen) in daten/ übernehmen. Tabellen zum Entfernen (art, id, begruendung) kommen
    danach dran, in der Reihenfolge der Dateien und Zeilen."""
    from ..bestand import (
        schreibe_bestand,
        schreibe_organisationen,
        schreibe_sportkomplexe,
        schreibe_stuetzpunkte,
    )
    from . import entfernen
    from .einlesen import lies_csv

    gelesen, zu_entfernen = [], []
    for datei in map(Path, args.dateien):
        if not datei.is_file():
            raise SystemExit(f"{datei} nicht gefunden.")
        if entfernen.ist_tabelle(_spalten(datei)):
            eintraege = entfernen.lies(datei)
            print(f"{datei.name}: Entfernen, {len(eintraege)} Zeilen (nach den übrigen Dateien)")
            zu_entfernen.append((datei, eintraege))
            continue
        try:
            datensaetze, b = lies_csv(datei)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        art = {
            "atlas": "Export des bisherigen Atlas",
            "sportstaetten": "Sportstätten",
            "sportanlagen": "Sportanlagen",
            "sportkomplexe": "Sportkomplexe",
            "stuetzpunkte": "Stützpunkte",
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
        if b.bereinigt:
            weg = ", ".join(f"{k} {v}×" for k, v in b.bereinigt.most_common())
            print(f"  Formfehler behoben: {weg}")
        if b.nicht_lesbar:
            fehler = ", ".join(f"{k} {v}×" for k, v in b.nicht_lesbar.most_common())
            print(f"  Werte, die nicht zum Feld passen (übernommen, wie sie sind): {fehler}")
        gelesen.append((datei, datensaetze, b.art))
    if args.probe:
        for datei, eintraege in zu_entfernen:
            _zeige_entfernen(datei, entfernen.entferne(eintraege, DATEN, probe=True), probe=True)
        if zu_entfernen and gelesen:
            print(
                "  (geprüft gegen daten/ ohne die übrigen Dateien – die können Verweise noch lösen)"
            )
        print("Probelauf: nichts geschrieben.")
        return
    kreis_von = kreis_von_bei_bedarf()
    for datei, datensaetze, art in gelesen:
        try:
            if art == "organisationen":
                e = schreibe_organisationen(datensaetze, DATEN, args.modus)
            elif art == "stuetzpunkte":
                e = schreibe_stuetzpunkte(datensaetze, DATEN, args.modus)
            elif art == "sportkomplexe":
                e = schreibe_sportkomplexe(datensaetze, DATEN, kreis_von, args.modus)
            else:
                e = schreibe_bestand(datensaetze, DATEN, LAND, kreis_von, args.modus)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        orgs, komplexe, stp = art == "organisationen", art == "sportkomplexe", art == "stuetzpunkte"
        ziel = (
            f"{DATEN}/organisationen/"
            if orgs
            else f"{DATEN}/stuetzpunkte/"
            if stp
            else f"{DATEN}/{LAND.upper()}/"
        )
        print(f"{datei.name} → {ziel} (Modus {args.modus})")
        was = (
            "Organisationen"
            if orgs
            else "Sportkomplexe"
            if komplexe
            else "Stützpunkte"
            if stp
            else "Sportstätten"
        )
        zeilen = [
            ("neu angelegt", e.neu, was),
            ("geändert", e.aktualisiert, was),
            ("unverändert", e.unveraendert, was),
            ("schon vorhanden", e.behalten, "(nicht verändert; --modus ergaenzen/aktualisieren)"),
            ("Sportanlagen neu", e.anlagen_neu, "zu vorhandenen Sportstätten"),
            ("zugeordnet", e.zugeordnet, "Sportstätten einem Sportkomplex"),
            ("Sportanlagen geändert", e.anlagen_geaendert, ""),
            ("ohne Koordinate", e.ohne_lage, "(übersprungen)"),
            ("ID unbekannt", e.unbekannt, "(nicht in daten/, übersprungen)"),
            (
                "Sportstätte unbekannt" if komplexe or stp else "ohne Sportstätte",
                e.ohne_sportstaette,
                ("IDs" if komplexe or stp else "Sportanlagen") + " (nicht in daten/, übersprungen)",
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
    for datei, eintraege in zu_entfernen:
        _zeige_entfernen(datei, entfernen.entferne(eintraege, DATEN))


def _spalten(datei: Path) -> set[str]:
    """Normierte Spaltennamen einer CSV-Datei."""
    from ..modell import werte
    from . import entfernen

    zeilen = werte.zeilen(werte.text(datei.read_bytes()))
    return {entfernen._norm(k) for k in (zeilen[0] if zeilen else {}) if k}


def _zeige_entfernen(datei: Path, e, probe: bool = False) -> None:
    print(f"{datei.name} → entfernen{' (Probe)' if probe else ''}: {len(e.entfernt)}")
    for art, oid, name in e.entfernt:
        print(f"  {art} {oid[:8]} {name}")
    for w in e.warnungen:
        print(f"  WARNUNG: {w}")
    if e.entfernt and not probe:
        print(f"  protokolliert in {DATEN}/entfernt.csv")


def cmd_organisationen(args):
    """Verzeichnis der Organisationen (daten/organisationen/): Stand zeigen; aus den
    Verwaltungsgebieten bzw. dem Bestand anlegen."""
    from ..bestand import (
        lies_bestand,
        lies_organisationen,
        org_schluessel,
        org_verzeichnis,
        organisationen_aus_bestand,
        organisationen_von,
    )

    if args.gebiete:
        from .kommunen import lege_an

        b = lege_an(DATEN, lade_gebiete())
        arten = ", ".join(f"{n} {art}" for art, n in b.je_art.items())
        print(f"Gebietskörperschaften: {arten}")
        print(f"  {b.neu} neu, {b.ergaenzt} ergänzt, {b.unveraendert} schon aktuell")
        for alt, neu in b.umbenannt:
            print(f"  umbenannt: {alt} → {neu} (alter Name bleibt als weitere Schreibweise)")
        for name, passend in b.mehrdeutig:
            print(f"WARNUNG: „{name}“ nicht eindeutig ({'; '.join(passend)}) – bitte von Hand")
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


def cmd_vorschlaege(args):
    """Vorschläge aus einem LimeSurvey-Export in daten/ übernehmen (vorschlaege.py)."""
    from .vorschlaege import UEBERNOMMEN, lies_export, uebernimm

    try:
        antworten = lies_export(Path(args.export))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    e = uebernimm(antworten, DATEN, kreis_von_bei_bedarf(), probe=args.probe, alle=args.alle)
    arten = ", ".join(f"{n}× {art}" for art, n in e.uebernommen.items()) or "keine"
    print(f"{len(antworten)} Antworten im Export; übernommen: {arten}")
    if e.uebersprungen:
        print(f"  {e.uebersprungen} schon früher übernommen (siehe {DATEN}/{UEBERNOMMEN}; --alle)")
    for sid in e.neue_ids:
        print(f"  neue Sportstätte: {sid}")
    for antwort, text in e.kommentare:
        print(f"  Kommentar zu Antwort {antwort}: {text}")
    for w in e.warnungen:
        print(f"WARNUNG: {w}")
    if args.probe:
        print("(--probe: nichts geschrieben)")


def _umbenennung(text: str) -> tuple[str, str]:
    alt, gleich, neu = text.partition("=")
    if not (gleich and alt.strip() and neu.strip()):
        raise argparse.ArgumentTypeError(f"{text!r}: erwartet ALT=NEU")
    return alt.strip(), neu.strip()


def cmd_migrieren(args):
    """Felder in allen Dateien von daten/ umbenennen oder entfernen (bestand.migriere_bestand)."""
    from ..bestand import migriere_bestand

    try:
        e = migriere_bestand(
            DATEN, dict(args.umbenennen), set(args.entfernen), args.probe, args.bereinigen
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    for was, zaehler in (
        ("umbenannt", e.umbenannt),
        ("entfernt", e.entfernt),
        ("bereinigt", e.bereinigt),
    ):
        for feld, n in zaehler.items():
            print(f"  {was}: {feld} in {n} Dateien")
    for pfad, alt, neu in e.konflikte:
        print(f"  nicht umbenannt, {neu} steht schon da: {pfad} ({alt})")
    print(f"{e.dateien} Dateien in {DATEN}/ {'würden geändert' if args.probe else 'geändert'}")


def befehle(sub) -> None:
    """Befehle dieses Teils an den Parser von `sportstaettenatlas` hängen."""
    sp = sub.add_parser(
        "bestand", help="CSV-Dateien in den Datenbestand daten/ übernehmen (siehe einlesen.py)"
    )
    sp.add_argument(
        "dateien",
        nargs="+",
        help="Atlas-Export, Tabellen der Sportstätten, Sportanlagen, Sportkomplexe, Stützpunkte, "
        "Organisationen; Tabellen zum Entfernen kommen zuletzt dran",
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
        "--gebiete",
        action="store_true",
        help="alle Landkreise, Städte, Verbands- und Ortsgemeinden anlegen bzw. ergänzen",
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

    sp = sub.add_parser(
        "vorschlaege", help="Vorschläge aus einem LimeSurvey-Export in daten/ übernehmen"
    )
    sp.add_argument("export", help="CSV-Export der Umfrage")
    sp.add_argument("--probe", action="store_true", help="nur zeigen, nichts schreiben")
    sp.add_argument("--alle", action="store_true", help="auch schon übernommene Antworten")
    sp.set_defaults(func=cmd_vorschlaege)

    sp = sub.add_parser("vorlage", help="Vorlagen für CSV-Dateien zum Einlesen schreiben")
    sp.add_argument("ordner", nargs="?", default="results/vorlagen")
    sp.set_defaults(func=cmd_vorlage)

    sp = sub.add_parser(
        "migrieren",
        help="Felder in allen Dateien von daten/ umbenennen oder entfernen; "
        "ordnet die Schlüssel wie im Modell",
    )
    sp.add_argument(
        "--umbenennen",
        metavar="ALT=NEU",
        type=_umbenennung,
        action="append",
        default=[],
        help="Feld umbenennen, z. B. baukosten_eur=baukosten (mehrfach möglich)",
    )
    sp.add_argument(
        "--entfernen",
        metavar="FELD",
        action="append",
        default=[],
        help="Feld aus allen Dateien löschen, z. B. quellen (mehrfach möglich)",
    )
    sp.add_argument(
        "--bereinigen",
        action="store_true",
        help="Formfehler beheben: Hausnummer „6.0“ → „6“ und „Aug 14“ → „8-14“, PLZ ohne "
        "führende Null, Ort als Dict-Text, Webseite ohne https://, Platzhalter „-“, Fläche einer "
        "Halle, die nur Länge × Breite ist",
    )
    sp.add_argument("--probe", action="store_true", help="nur zählen, nichts schreiben")
    sp.set_defaults(func=cmd_migrieren)
