"""Datenmodell des Sportstättenatlas – die einzige Stelle, an der Felder und Regeln stehen.

Was daraus abgeleitet wird: README.md („Datenmodell im Code“); was die Felder bedeuten:
daten/README.md (zum Teil aus diesem Modul erzeugt).

Angaben je Feld (json_schema_extra, landen im Schema):
  gruppe      Abschnitt im Formular und in der Übersicht (Reihenfolge: GRUPPEN bzw.
              ANLAGE_GRUPPEN)
  widget      besondere Eingabe/Anzeige: ja_nein, karte, chips, organisation, ort, url,
              anlagentyp, jahr, zaehler (Anzahl je Wert, z. B. Felder je Belag),
              organisationen (Liste von Namen aus dem Verzeichnis der Organisationen)
  formular    False: nicht im Formular (IDs, Herkunft)
  uebersicht  False: zählt nicht zur Vollständigkeit in der Übersicht
  einheit     wird hinter Zahlen angezeigt (z. B. m²); einheit_aus: aus einem anderen Feld
              (Baukosten → Währung)
  (fuer       steht nicht am Feld: folgt aus MERKMALE, siehe fuer_von)
  spalte      weiterer Spaltenname, unter dem `bestand` das Feld in einer CSV erkennt
Regeln zwischen Feldern (prüft Basis, das Formular ebenso):
  braucht     dieses Feld braucht das genannte (Baukosten → Währung)
  teil_von    Werte müssen auch im genannten Feld stehen (Wettkampfeignung → Sportarten)
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic.json_schema import models_json_schema

from . import anlagen

# --- Auswahllisten ----------------------------------------------------------------------

KATEGORIEN = (
    "Sportplatz",
    "Sporthalle",
    "Tennissportstätte",
    "Öffentlicher Sport- und Bewegungsraum",
    "Reitsportstätte",
    "Schwimmsportstätte",
    "Schießsportstätte",
    "Fitnessstudio",
    "Golfsportstätte",
    "Roll- und Skatesportstätte",
    "Sportgelegenheiten in sonstigen Gebäuden",
    "Radsportstätte",
    "Flugsportstätte",
    "Wintersportstätte",
    "Wassersportstätte",
    "Klettersportstätte",
    "Motorsportstätte",
    "Eissportstätte",
    "Leistungsstützpunkt",
    "Segelsportstätte",
)
BETRIEBSSTATUS = (
    "in Betrieb",
    "vorübergehend geschlossen",
    "stillgelegt/geschlossen",
    "im Bau",
    "in Planung",
)
# Art einer Organisation → Art auf der Karte
ORGANISATIONSTYPEN = {
    "Bund": "sonstige",
    "Land Rheinland-Pfalz": "sonstige",
    "Landkreis": "Kommune",
    "Stadt/Gemeinde": "Kommune",
    "Kommunales Unternehmen": "Kommune",
    "Zweckverband": "Kommune",
    "Sportverein im LSB RLP": "Verein",
    "Sonstiger Sportverein": "Verein",
    "Sportverband im LSB RLP": "sonstige",
    "Sonstiger Sportverband": "sonstige",
    "Privatwirtschaftlich/kommerziell": "sonstige",
    "Sonstige": "sonstige",
}
WAEHRUNGEN = ("€", "DM", "RM")
BODENBELAEGE = (
    "Sportparkett",
    "Rasen",
    "Kunstrasen",
    "Hartplatz/Tenne",
    "Beton",
    "Sand",
    "Kunststoff",
    "Teppich",
    "Granulat",
    "Linoleum",
    "Sonstiges",
)
SPIELFELDER = (
    "Fußball",
    "Handball",
    "Basketball",
    "Volleyball",
    "Beachvolleyball",
    "Badminton",
    "Futsal",
    "Funino",
    "Hallenhockey",
    "Feldhockey",
    "Faustball",
    "American Football",
    "Rugby",
    "Baseball",
    "Softball",
    "Cricket",
    "Streetball",
    "Sonstige",
)
KLEINFELDER = ("Fußball", "Hockey", "Basketball", "Streetball", "Sonstige")
LEUCHTMITTEL = ("LED", "Leuchtröhren", "Sonstige")
LUXWERTE = (100, 150, 200, 300, 500, 750, 1000)


def _auswahl(name: str, werte, typ=str) -> type[Enum]:
    """Auswahlliste als Enum: im Diagramm und im Modell einmal benannt statt bei jedem Feld
    ausgeschrieben. Die Werte bleiben Text bzw. Zahlen (schema löst sie im Schema wieder auf)."""
    return Enum(name, [(f"w{i}", w) for i, w in enumerate(werte)], type=typ)


Kategorie = _auswahl("Kategorie", KATEGORIEN)
Betriebsstatus = _auswahl("Betriebsstatus", BETRIEBSSTATUS)
Organisationstyp = _auswahl("Organisationstyp", ORGANISATIONSTYPEN)
JaNein = _auswahl("JaNein", ("ja", "nein"))
Waehrung = _auswahl("Waehrung", WAEHRUNGEN)
Bodenbelag = _auswahl("Bodenbelag", BODENBELAEGE)
Spielfeldart = _auswahl("Spielfeldart", SPIELFELDER)
Kleinfeldart = _auswahl("Kleinfeldart", KLEINFELDER)
Leuchtmittel = _auswahl("Leuchtmittel", LEUCHTMITTEL)
Luxwert = _auswahl("Luxwert", LUXWERTE, int)
AUSWAHL = (
    Kategorie,
    Betriebsstatus,
    Organisationstyp,
    JaNein,
    Waehrung,
    Bodenbelag,
    Spielfeldart,
    Kleinfeldart,
    Leuchtmittel,
    Luxwert,
)
Anzahl = Annotated[int, Field(ge=0, le=10_000)]

# Kontaktdaten werden nie gespeichert oder veröffentlicht: Werte mit einer E-Mail-Adresse
# (EMAIL_MUSTER, auch im Formular) und Felder bzw. Spalten, deren Name so aussieht (KONTAKT_NAME)
EMAIL_MUSTER = r"[\w.+-]+@[\w-]+(\.[\w-]+)+"
KONTAKT_NAME = r"e-?mail|telefon|telefax|(^|[^a-z])fax([^a-z]|$)|handy|mobilnummer|mobiltelefon|kontakt|ansprechpartner"

# Abschnitte des Formulars in dieser Reihenfolge
GRUPPEN = ("Sportstätte", "Adresse und Lage", "Nutzung", "Sportarten", "Organisationen")
ANLAGE_GRUPPEN = (
    "Allgemein",
    "Sportarten",
    "Maße",
    "Belag und Felder",
    "Becken",
    "Ausstattung",
    "Licht",
    "Nutzung",
    "Barrierefreiheit",
    "Kosten",
)


def _f(titel: str, beschreibung: str | None = None, pflicht: bool = False, **angaben):
    """Feld mit Beschriftung; Regeln (ge, le, pattern …), Vorgabe und Angaben für die Webseite."""
    regeln = {
        k: angaben.pop(k)
        for k in ("ge", "le", "pattern", "min_length", "max_length", "default", "default_factory")
        if k in angaben
    }
    if pflicht:
        regeln["default"] = ...
    elif "default_factory" not in regeln:
        regeln.setdefault("default", None)
    return Field(title=titel, description=beschreibung, json_schema_extra=angaben or None, **regeln)


class Basis(BaseModel):
    """Gemeinsame Einstellungen und die Regeln zwischen Feldern (Angaben braucht, teil_von)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=True)

    @model_validator(mode="after")
    def _regeln_zwischen_feldern(self):
        fehler = []
        for name, feld in type(self).model_fields.items():
            extra = feld.json_schema_extra or {}
            wert = getattr(self, name)
            if extra.get("braucht") and wert not in (None, "", [], {}):
                anderes = extra["braucht"]
                if getattr(self, anderes) in (None, "", [], {}):
                    fehler.append(f"{anderes}: nötig, wenn {feld.title} angegeben ist")
            if extra.get("teil_von") and wert:
                alle = getattr(self, extra["teil_von"]) or []
                fehlt = [w for w in wert if w not in alle]
                if fehlt:
                    titel = type(self).model_fields[extra["teil_von"]].title
                    fehler.append(f"{name}: {', '.join(fehlt)} fehlt unter {titel}")
        if fehler:
            raise ValueError("; ".join(fehler))
        return self


# --- Datenbestand -----------------------------------------------------------------------


class Adresse(Basis):
    strasse: str | None = _f("Straße", max_length=150, spalte="adresse.strasse")
    hausnummer: str | None = _f(
        "Hausnummer",
        "z. B. 12, 12a oder 2-4",
        max_length=12,
        pattern=r"^\d+\s?[a-zA-Z]?(\s?[-/]\s?\d+\s?[a-zA-Z]?)?$",
        spalte="adresse.hausnummer",
    )
    adresszusatz: str | None = _f(
        "Adresszusatz",
        "z. B. Eingang Schulhof",
        max_length=150,
        uebersicht=False,
        spalte="adresse.adresszusatz",
    )
    plz: str | None = _f("PLZ", "fünf Ziffern", pattern=r"^\d{5}$", spalte="adresse.postleitzahl")
    ort: str | None = _f("Ort", max_length=100, widget="ort", spalte="adresse.ort")


class Lage(Basis):
    """Immer WGS84 (EPSG:4326), Grad mit Dezimalstellen."""

    lon: float = _f("Längengrad", "WGS84", pflicht=True, ge=5.8, le=9.0)
    lat: float = _f("Breitengrad", "WGS84", pflicht=True, ge=48.8, le=51.1)


# Welche Felder es je Anlagentyp gibt (MERKMALE); MERKMALE_ALLE und jedes Feld, das dort
# nicht steht, gelten für alle Typen. Daraus folgt die Angabe „fuer“ im Schema (fuer_von): das
# Formular zeigt ein Feld nur bei diesen Typen, die Übersicht zählt es nur unter ihnen.
MERKMALE_ALLE = (
    "bezeichnung",
    "betriebsstatus",
    "baujahr",
    "letzte_sanierung",
    "baukosten",
    "waehrung",
    "oeffnungsstunden",
    "oeffnungsstunden_schule",
    "oeffnungsstunden_verein",
    "flutlicht",
    "leuchtmittel",
    "lux",
    "barrierefrei_erreichbar",
)
MERKMALE: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        (
            "Sport-/Turnhalle untermaßig",
            "Einfachsporthalle",
            "Zweifachsporthalle",
            "Dreifachsporthalle",
            "Großsporthalle",
            "Freilufthalle",
            "Sporthalle Sondermaße",
            "Sporthalle (Größe unbekannt)",
        ),
        ("laenge", "breite", "hoehe", "bodenbelag", "felder_je_sportart"),
    ),
    (("Bühne",), ("laenge", "breite", "hoehe", "trennvorhang")),
    (("Squashhalle", "Paddleplatz"), ("laenge", "breite", "hoehe", "bodenbelag", "spielfelder")),
    (
        ("Kurs-/Übungsraum", "Gerätebereich", "Skateplatz", "Rollsportplatz"),
        ("bodenbelag", "flaeche"),
    ),
    (
        ("Großspielfeld",),
        (
            "laenge",
            "breite",
            "bodenbelag",
            "bewaesserung",
            "felder_je_sportart",
            "kleinfelder_je_sportart",
        ),
    ),
    (
        ("Kleinspielfeld", "Nicht normiertes Spielfeld"),
        ("laenge", "breite", "bodenbelag", "bewaesserung", "felder_je_sportart"),
    ),
    (("Rundlaufbahn", "Kurzstreckenbahn", "Radrennbahn"), ("bodenbelag", "laenge", "bahnen")),
    (("Tennishalle",), ("laenge", "breite", "hoehe", "felder_je_belag")),
    (("Tennisplatz",), ("bewaesserung", "felder_je_belag")),
    (
        ("Bogenschießanlage", "Schießstand", "Wurfscheibenanlage"),
        ("schiessstaende_gedeckt", "schiessstaende_offen", "schiessstaende_teilgedeckt"),
    ),
    (("Führ- und Longierplatz", "Sportkindergarten"), ("flaeche",)),
    (
        ("Führ- und Longierhalle", "Stall", "Eissporthalle", "Bootshaus/-halle"),
        ("laenge", "breite", "hoehe"),
    ),
    (("Rennbahn", "Eisschnelllaufbahn"), ("laenge", "bahnen")),
    (
        (
            "Fahrparcours",
            "Bob-/Rodelbahn",
            "Mountainbikestrecke",
            "BMX-Strecke",
            "Enduro-Strecke",
            "Kartbahn",
            "Motocross-Strecke",
            "Motorsport-Rennstrecke",
            "SuperMoto-Strecke",
        ),
        ("laenge",),
    ),
    (("Reitplatz",), ("bodenbelag", "flaeche", "bewaesserung", "dressurplatz")),
    (
        ("Reithalle", "Radsporthalle", "Rollsporthalle", "Skatehalle"),
        ("laenge", "breite", "hoehe", "bodenbelag"),
    ),
    (
        ("Hallenbad", "Freibad", "Cabriobad", "Kombibad"),
        (
            "becken_bis_25m",
            "becken_25_bis_50m",
            "becken_ueber_50m",
            "nichtschwimmerbecken",
            "kinderbecken",
            "erholungsbecken",
            "lehrbecken",
            "wasserflaeche",
            "wasserflaeche_lehrbecken",
            "bahnlaenge",
            "wasserflaeche_relevant",
            "becken_tiefer_3m",
            "sprungturm",
            "sprungtuerme_3m",
            "sprungtuerme_5m",
            "sprungtuerme_10m",
            "baederleben_id",
        ),
    ),
    (
        ("Naturbad",),
        (
            "wasserflaeche",
            "nichtschwimmerbecken",
            "bahnlaenge",
            "wasserflaeche_relevant",
            "becken_tiefer_3m",
            "sprungturm",
            "sprungtuerme_3m",
            "sprungtuerme_5m",
            "sprungtuerme_10m",
            "baederleben_id",
        ),
    ),
    (("Golfplatz",), ("loecher",)),
    (("Bahnengolf", "Bowlingbahn", "Kegelbahn"), ("bahnen",)),
    (
        ("Eissportanlage ungedeckt", "Segelfluggelände", "Sonderlandeplatz", "Sportflugplatz"),
        ("laenge", "breite"),
    ),
    (("Alpine Skianlage",), ("laenge", "lifte")),
    (("Skisprungschanze",), ("laenge", "hoehe")),
    (("Klettersporthalle",), ("laenge", "breite", "hoehe", "boulderwand", "kletterwand")),
    (("Klettersportanlage Outdoor",), ("boulderwand", "kletterwand")),
    (("Sporthafen",), ("wasserflaeche", "flaeche")),
    (("Regattastrecke",), ("wasserflaeche", "flaeche", "bahnen")),
    (("Wildwasseranlage",), ("laenge", "breite", "wasserflaeche")),
    (("Rundrennstrecke (Motorboot)",), ("laenge", "wasserflaeche")),
    (("Bouleanlage",), ("bodenbelag", "bahnen")),
    (("Volleyballfeld",), ("bodenbelag", "bewaesserung", "hoehenverstellbares_netz")),
    (
        (
            "Weit- und Dreisprunganlage",
            "Kugelstoßanlage",
            "Hindernislauf mit Wassergraben",
            "Hochsprunganlage",
            "Stabhochsprunganlage",
            "Diskus- und Hammerwurfanlage",
            "Speerwurfanlage",
            "Ballwand",
            "Polofeld",
            "Springparcours",
            "Geländeparcours",
            "Freestyleanlage",
            "Skilanglauf- und Biathlonanlage",
            "Bewegungsparcours",
            "Calisthenicsanlage",
        ),
        (),
    ),
)


def fuer_von(feld: str) -> list[str] | None:
    """Anlagentypen, für die ein Feld gedacht ist (MERKMALE); None: für alle."""
    if feld in MERKMALE_ALLE:
        return None
    typen = [t for typen_, felder in MERKMALE if feld in felder for t in typen_]
    return list(dict.fromkeys(typen)) or None


def _a(titel, beschreibung=None, gruppe="Allgemein", **angaben):
    return _f(titel, beschreibung, gruppe=gruppe, **angaben)


def _jn(titel, beschreibung=None, gruppe="Ausstattung", **angaben):
    return _a(titel, beschreibung, gruppe, widget="ja_nein", **angaben)


def _n(titel, beschreibung=None, gruppe="Maße", **angaben):
    return _a(titel, beschreibung, gruppe, ge=0, **angaben)


class Sportanlage(Basis):
    """Eine Einheit einer Sportstätte, z. B. ein Großspielfeld, eine Halle oder ein Becken."""

    model_config = ConfigDict(
        json_schema_extra={
            "gruppen": list(ANLAGE_GRUPPEN),
            "examples": [
                {
                    "id": "17abb3c4-7493-5549-a6ca-f432ef00fba3",
                    "sportstaette_id": "9c24bfa6-71c1-4164-b226-061f0a139997",
                    "typ": "Großspielfeld",
                    "bezeichnung": "Kunstrasen B",
                    "betriebsstatus": "in Betrieb",
                    "baujahr": 1998,
                    "sportarten": ["Fußball"],
                    "wettkampf": ["Fußball"],
                    "laenge": 105,
                    "breite": 68,
                    "bodenbelag": "Kunstrasen",
                    "flutlicht": "ja",
                    "baukosten": 1200000,
                    "waehrung": "DM",
                }
            ],
        }
    )

    id: str | None = _f(
        "ID",
        "UUID, zugleich der Dateiname (in der Datei Pflicht)",
        formular=False,
        uebersicht=False,
    )
    sportstaette_id: str | None = _f(
        "Sportstätte",
        "ID der Sportstätte, zu der die Anlage gehört, = Name des Ordners (in der Datei Pflicht)",
        formular=False,
        uebersicht=False,
    )
    # Sportanlage
    typ: str = _a(
        "Typ",
        "einheitlicher Typ aus src/sportstaettenatlas/anlagen.py, z. B. „Großspielfeld“",
        pflicht=True,
        min_length=1,
        max_length=100,
        widget="anlagentyp",
        uebersicht=False,
        spalte="typid",
    )
    bezeichnung: str | None = _a(
        "Name",
        "eigener Name der Anlage, z. B. „Halle 1“, „Kunstrasen B“",
        max_length=100,
        spalte="bezeichnung",
    )
    betriebsstatus: Betriebsstatus | None = _a("Betriebsstatus", spalte="betriebsstatustypid")
    baujahr: int | None = _a("Baujahr", ge=1800, le=2100, widget="jahr", spalte="baujahr")
    letzte_sanierung: int | None = _a(
        "Letzte Sanierung", "Jahr", ge=1800, le=2100, widget="jahr", spalte="letzteSanierung"
    )
    # Sportarten
    sportarten: list[str] = _a("Sportarten", gruppe="Sportarten", default_factory=list)
    wettkampf: list[str] = _a(
        "Wettkampfeignung",
        "Sportarten, für die die Anlage wettkampfgeeignet ist (müssen unter Sportarten stehen)",
        gruppe="Sportarten",
        default_factory=list,
        teil_von="sportarten",
        spalte="sportanlagesportart.wettkampfeignung",
    )
    # Maße
    laenge: float | None = _n("Länge", "der Sportfläche", einheit="m", spalte="laenge")
    breite: float | None = _n("Breite", "der Sportfläche", einheit="m", spalte="breite")
    hoehe: float | None = _n("Höhe", "lichte Höhe der Halle", einheit="m", spalte="hoehe")
    flaeche: float | None = _n(
        "Fläche",
        "nutzbare Sportfläche, wenn nicht Länge × Breite (z. B. Reitplatz)",
        einheit="m²",
        spalte="groesse",
    )
    bahnlaenge: float | None = _n("Bahnlänge", einheit="m", spalte="bahnlaenge")
    bahnen: int | None = _n(
        "Bahnen", "Zahl der Lauf-, Schwimm-, Kegel- oder Schießbahnen", spalte="anzbahnen"
    )
    # Belag und Felder
    bodenbelag: Bodenbelag | None = _a(
        "Bodenbelag", gruppe="Belag und Felder", spalte="bodenbelagtypid"
    )
    felder_je_belag: dict[Bodenbelag, Anzahl] = _a(
        "Felder je Belag",
        "z. B. Tennisplätze: 3 Sand, 1 Kunstrasen",
        gruppe="Belag und Felder",
        default_factory=dict,
        widget="zaehler",
        spalte="bodenbelag_anz_*",
    )
    spielfelder: int | None = _n(
        "Spielfelder",
        "Zahl, wenn nicht nach Sportart bekannt",
        gruppe="Belag und Felder",
        spalte="anzspielfelder",
    )
    felder_je_sportart: dict[Spielfeldart, Anzahl] = _a(
        "Spielfelder je Sportart",
        "markierte Felder, z. B. 3 Badminton, 1 Handball",
        gruppe="Belag und Felder",
        default_factory=dict,
        widget="zaehler",
        spalte="anz_feld_*",
    )
    kleinfelder_je_sportart: dict[Kleinfeldart, Anzahl] = _a(
        "Kleinfelder je Sportart",
        gruppe="Belag und Felder",
        default_factory=dict,
        widget="zaehler",
        spalte="anz_kleinfeld_*",
    )
    loecher: int | None = _n(
        "Löcher", "Golf, Bahnengolf", gruppe="Belag und Felder", spalte="anzloecher"
    )
    # Becken
    wasserflaeche: float | None = _n(
        "Wasserfläche", "gesamt", gruppe="Becken", einheit="m²", spalte="wasserflaeche"
    )
    wasserflaeche_relevant: float | None = _n(
        "Relevante Wasserfläche",
        "ohne Kaltwassertret-, Warmsprudelbecken usw.",
        gruppe="Becken",
        einheit="m²",
        spalte="relevante_wasserflaeche",
    )
    wasserflaeche_lehrbecken: float | None = _n(
        "Wasserfläche Lern- und Kursbecken",
        gruppe="Becken",
        einheit="m²",
        spalte="wasserflaechelernundkursbecken",
    )
    becken_bis_25m: int | None = _n("Becken bis 25 m", gruppe="Becken", spalte="anzbeckenbis25")
    becken_25_bis_50m: int | None = _n(
        "Becken 25 bis 50 m", gruppe="Becken", spalte="anzbeckenbis25bis50"
    )
    becken_ueber_50m: int | None = _n(
        "Becken über 50 m", gruppe="Becken", spalte="anzbeckenueber50"
    )
    becken_tiefer_3m: int | None = _n(
        "Becken tiefer als 3 m", gruppe="Becken", spalte="anzbeckenue3m"
    )
    nichtschwimmerbecken: int | None = _n(
        "Nichtschwimmerbecken", gruppe="Becken", spalte="anznichtschwimmer"
    )
    lehrbecken: int | None = _n("Lehrbecken", gruppe="Becken", spalte="anzlehrbecken")
    kinderbecken: int | None = _n("Kinderbecken", gruppe="Becken", spalte="anzkinderbecken")
    erholungsbecken: int | None = _n(
        "Erholungsbecken", gruppe="Becken", spalte="anzerholungsbecken"
    )
    sprungturm: JaNein | None = _jn(
        "Sprungturm", "mindestens einer", gruppe="Becken", spalte="sprungturm"
    )
    sprungtuerme_3m: int | None = _n("Sprungtürme 3 m", gruppe="Becken", spalte="anzturm3m")
    sprungtuerme_5m: int | None = _n("Sprungtürme 5 m", gruppe="Becken", spalte="anztur5m")
    sprungtuerme_10m: int | None = _n("Sprungtürme 10 m", gruppe="Becken", spalte="anztur10m")
    baederleben_id: str | None = _a(
        "ID bei baederleben.de",
        gruppe="Becken",
        max_length=50,
        uebersicht=False,
        spalte="baederlebenid",
    )
    # Ausstattung
    trennvorhang: JaNein | None = _jn(
        "Trennvorhang", "zur Hallenteilung oder für eine Bühne", spalte="vorhangvorhanden"
    )
    bewaesserung: JaNein | None = _jn("Bewässerung", spalte="bewaesserung")
    hoehenverstellbares_netz: JaNein | None = _jn(
        "Höhenverstellbares Netz", spalte="hoehenverstellnetz"
    )
    kletterwand: JaNein | None = _jn("Kletterwand", spalte="kletterwand")
    boulderwand: JaNein | None = _jn("Boulderwand", spalte="boulderwand")
    dressurplatz: JaNein | None = _jn("Dressurplatz", spalte="dressurplatz")
    springplatz: JaNein | None = _jn("Springplatz", spalte="springplatz")
    schiessstaende_gedeckt: int | None = _n(
        "Schießstände gedeckt", gruppe="Ausstattung", spalte="anzschiesstubgedeckt"
    )
    schiessstaende_teilgedeckt: int | None = _n(
        "Schießstände teilgedeckt", gruppe="Ausstattung", spalte="anzschiesstuboteilgedeckt"
    )
    schiessstaende_offen: int | None = _n(
        "Schießstände offen", gruppe="Ausstattung", spalte="anzschiesstuboffen"
    )
    lifte: int | None = _n("Lifte", gruppe="Ausstattung", spalte="anzlift")
    spielgeraete: int | None = _n("Spielgeräte", gruppe="Ausstattung", spalte="anz_spielgeraete")
    ausstattung: list[str] = _a(
        "Weitere Ausstattung",
        "z. B. Umkleiden, Anzeigetafel",
        gruppe="Ausstattung",
        default_factory=list,
    )
    # Licht
    flutlicht: JaNein | None = _jn("Flutlicht", gruppe="Licht", spalte="flutlicht")
    leuchtmittel: Leuchtmittel | None = _a(
        "Leuchtmittel", gruppe="Licht", spalte="leuchtmitteltypid"
    )
    lux: Luxwert | None = _a(
        "Beleuchtungsstärke", gruppe="Licht", einheit="lx", spalte="luxwerttypid"
    )
    # Nutzung
    oeffnungsstunden: int | None = _n(
        "Öffnungsstunden",
        "im Jahr, insgesamt",
        gruppe="Nutzung",
        le=8784,
        einheit="h",
        spalte="oeffnungsstunden",
    )
    oeffnungsstunden_schule: int | None = _n(
        "davon Schulsport",
        "Stunden im Jahr",
        gruppe="Nutzung",
        le=8784,
        einheit="h",
        spalte="oeffnungsstundenschule",
    )
    oeffnungsstunden_verein: int | None = _n(
        "davon Vereine",
        "Stunden im Jahr",
        gruppe="Nutzung",
        le=8784,
        einheit="h",
        spalte="oeffnungsstundenverein",
    )
    altersempfehlung: str | None = _a(
        "Altersempfehlung",
        "z. B. 6–12 Jahre",
        gruppe="Nutzung",
        max_length=50,
        spalte="altersempfehlung",
    )
    # Barrierefreiheit
    barrierefrei_erreichbar: JaNein | None = _jn(
        "Barrierefrei erreichbar", gruppe="Barrierefreiheit", spalte="barrierefreierreichbar"
    )
    geeignet_mobilitaet: JaNein | None = _jn(
        "Geeignet bei eingeschränkter Mobilität",
        gruppe="Barrierefreiheit",
        spalte="eignungparasport1",
    )
    geeignet_sehen: JaNein | None = _jn(
        "Geeignet bei Sehbeeinträchtigung", gruppe="Barrierefreiheit", spalte="eignungparasport2"
    )
    geeignet_kleinwuchs: JaNein | None = _jn(
        "Geeignet für Kleinwüchsige", gruppe="Barrierefreiheit", spalte="eignungparasport3"
    )
    geeignet_mental: JaNein | None = _jn(
        "Geeignet bei geistiger Beeinträchtigung",
        gruppe="Barrierefreiheit",
        spalte="eignungparasport4",
    )
    # Kosten
    baukosten: float | None = _n(
        "Baukosten",
        "damalige Kosten",
        gruppe="Kosten",
        braucht="waehrung",
        einheit_aus="waehrung",
        spalte="baukosten",
    )
    waehrung: Waehrung | None = _a(
        "Währung", "der Baukosten", gruppe="Kosten", uebersicht=False, spalte="waehrung"
    )
    quellen: dict[str, dict[str, Any]] = _f(
        "Herkunft",
        "je Quelle, z. B. die Schreibweise im Atlas",
        default_factory=dict,
        formular=False,
        uebersicht=False,
    )


class Sportstaette(Basis):
    """Der Standort, z. B. ein Sportpark, ein Schulsportzentrum oder ein Freibad."""

    model_config = ConfigDict(
        json_schema_extra={
            "gruppen": list(GRUPPEN),
            "examples": [
                {
                    "id": "9c24bfa6-71c1-4164-b226-061f0a139997",
                    "name": "Sportplatz Musterdorf",
                    "kategorie": "Sportplatz",
                    "adresse": {
                        "strasse": "Am Weg",
                        "hausnummer": "1",
                        "plz": "56068",
                        "ort": "Koblenz",
                    },
                    "lage": {"lon": 7.59, "lat": 50.35},
                    "betreiber": "TuS Musterdorf e.V.",
                    "betreiber_typ": "Sportverein im LSB RLP",
                    "sportarten": ["Fußball", "Leichtathletik"],
                    "quellen": {
                        "atlas_rlp": {
                            "id": "9c24bfa6-…",
                            "datei": "sportstaetten_04112026.csv",
                            "stand": "2026-11-04",
                        }
                    },
                }
            ],
        }
    )

    id: str | None = _f(
        "ID",
        "UUID, zugleich Name des Ordners (in der Datei Pflicht)",
        formular=False,
        uebersicht=False,
    )
    name: str = _f(
        "Name",
        pflicht=True,
        min_length=1,
        max_length=200,
        gruppe="Sportstätte",
        spalte="bezeichnung",
    )
    kategorie: Kategorie = _f(
        "Sportstättenkategorie", pflicht=True, gruppe="Sportstätte", spalte="typid"
    )
    adresse: Adresse = _f("Adresse", default_factory=Adresse, gruppe="Adresse und Lage")
    lage: Lage = _f(
        "Lage",
        "bestimmt Kreis und Gemeinde",
        pflicht=True,
        gruppe="Adresse und Lage",
        widget="karte",
        uebersicht=False,
    )
    oeffentlicher_zugang: JaNein | None = _f(
        "Öffentlicher Zugang",
        gruppe="Nutzung",
        widget="ja_nein",
        spalte="oeffentlich",
    )
    schulsport: JaNein | None = _f(
        "Schulsport", gruppe="Nutzung", widget="ja_nein", spalte="schulsport"
    )
    zuschauerplaetze: int | None = _f(
        "Zuschauerplätze", ge=0, le=100_000, gruppe="Nutzung", spalte="zuschauerplatzgesamt"
    )
    betriebsstatus: Betriebsstatus | None = _f(
        "Betriebsstatus", gruppe="Sportstätte", spalte="betriebsstatustypid"
    )
    eigentuemer: str | None = _f(
        "Eigentümer",
        "Name einer Organisation (Verzeichnis daten/organisationen/), keine Personen",
        max_length=200,
        gruppe="Organisationen",
        widget="organisation",
        spalte="eignerbezeichnung",
    )
    eigentuemer_typ: Organisationstyp | None = _f(
        "Art des Eigentümers",
        gruppe="Organisationen",
        braucht="eigentuemer",
        spalte="eignertyp",
    )
    betreiber: str | None = _f(
        "Betreiber",
        "Name einer Organisation (Verzeichnis daten/organisationen/), keine Personen",
        max_length=200,
        gruppe="Organisationen",
        widget="organisation",
        spalte="betreiberbezeichnung",
    )
    betreiber_typ: Organisationstyp | None = _f(
        "Art des Betreibers",
        gruppe="Organisationen",
        braucht="betreiber",
        spalte="betreibertyp",
    )
    website: str | None = _f(
        "Webseite",
        "vollständige Adresse mit https://",
        pattern=r"^https?://\S+\.\S+$",
        gruppe="Organisationen",
        widget="url",
        spalte="url",
    )
    nutzer: list[str] = _f(
        "Nutzer",
        "Vereine und andere Organisationen, die die Sportstätte nutzen (Verzeichnis "
        "daten/organisationen/)",
        default_factory=list,
        gruppe="Organisationen",
        widget="organisationen",
        spalte="sportstaettenutzer.nutzername",
    )
    sportarten: list[str] = _f(
        "Sportarten", default_factory=list, gruppe="Sportarten", widget="chips"
    )
    quellen: dict[str, dict[str, Any]] = _f(
        "Herkunft",
        "je Quelle, z. B. ID, Datei und Stand im Atlas",
        default_factory=dict,
        formular=False,
        uebersicht=False,
    )
    anlagen: list[Sportanlage] = _f(
        "Sportanlagen",
        "stehen als eigene Dateien im Ordner der Sportstätte, nicht in `<id>_meta.json`",
        default_factory=list,
        formular=False,
        datei=False,
        gruppe="Sportstätte",
    )


class Organisation(Basis):
    """Verein, Kommune, Verband, Unternehmen … als Eigentümer, Betreiber oder Nutzer von
    Sportstätten (Verzeichnis in daten/organisationen/). Sportstätten nennen sie in
    `eigentuemer`, `betreiber` und `nutzer` beim Namen; auch die weiteren Schreibweisen
    gelten. Keine Personen, keine Kontaktdaten."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "3f0c2a8e-5b1d-4e57-9a0c-6d2e1b7f4a90",
                    "name": "TuS Musterdorf e.V.",
                    "typ": "Sportverein im LSB RLP",
                    "website": "https://tus-musterdorf.example",
                    "weitere_namen": ["TuS Musterdorf", "Turn- und Sportverein Musterdorf"],
                }
            ]
        }
    )

    id: str | None = _f(
        "ID",
        "UUID, zugleich der Dateiname (in der Datei Pflicht)",
        formular=False,
        uebersicht=False,
    )
    name: str = _f(
        "Name",
        "wie er bei den Sportstätten steht",
        pflicht=True,
        min_length=1,
        max_length=200,
        spalte="organisation.bezeichnung",
    )
    typ: Organisationstyp | None = _f("Art", spalte="organisation.typid")
    website: str | None = _f(
        "Webseite",
        "vollständige Adresse mit https://",
        pattern=r"^https?://\S+\.\S+$",
        widget="url",
        spalte="organisation.webseite",
    )
    uebergeordnet: str | None = _f(
        "Übergeordnet",
        "Name der übergeordneten Organisation, z. B. des Verbands",
        max_length=200,
        widget="organisation",
        spalte="organisation.parentid",
    )
    weitere_namen: list[str] = _f(
        "Weitere Schreibweisen",
        "andere Namen, unter denen Sportstätten sie nennen",
        default_factory=list,
    )


# --- Vorschlag (Formular → LimeSurvey) ------------------------------------------------


class Vorschlag(Basis):
    """Was das Formular „Vorschlag“ als JSON in die LimeSurvey-Frage „data“ schreibt."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "version": 1,
                    "art": "anlagen",
                    "sportstaette_id": "9c24bfa6-71c1-4164-b226-061f0a139997",
                    "anlagen": [
                        {"id": "17abb3c4", "typ": "Großspielfeld", "baujahr": 1998},
                        {"typ": "Kleinspielfeld"},
                    ],
                    "entfernte_anlagen": ["1fb06acd"],
                }
            ]
        }
    )

    version: Literal[1] = _f("Version des Formats", default=1)
    art: Literal["neu", "aenderung", "anlagen", "organisation"] = _f(
        "Art",
        "neu: neue Sportstätte mit Anlagen; aenderung: Angaben einer Sportstätte; "
        "anlagen: Sportanlagen einer Sportstätte; organisation: Organisation anlegen, "
        "ändern oder löschen",
        pflicht=True,
    )
    sportstaette_id: str | None = _f("Sportstätte", "ID der geänderten Sportstätte")
    sportstaette: Sportstaette | None = _f(
        "Angaben der Sportstätte", "vollständig, nach der Änderung (bei neu und aenderung)"
    )
    anlagen: list[Sportanlage] | None = _f(
        "Sportanlagen",
        "alle Anlagen nach der Änderung (bei neu und anlagen); vorhandene mit ihrer "
        "Kurz-ID (Anfang der UUID), neue ohne",
    )
    entfernte_anlagen: list[str] = _f("Entfernte Sportanlagen", "Kurz-IDs", default_factory=list)
    organisation_id: str | None = _f(
        "Organisation", "ID der geänderten oder gelöschten Organisation (fehlt bei einer neuen)"
    )
    organisation: Organisation | None = _f(
        "Angaben der Organisation", "vollständig, nach der Änderung (nicht beim Löschen)"
    )
    loeschen: bool = _f("Löschen", "die Organisation aus dem Verzeichnis entfernen", default=False)
    geaendert: list[str] = _f("Geänderte Felder", default_factory=list)
    gemeinde: str | None = _f("Gemeinde", "Regionalschlüssel der Gemeinde an der Lage")
    dubletten_geprueft: list[str] = _f(
        "Geprüfte Doppelungen",
        "IDs ähnlicher Sportstätten, die als verschieden bestätigt wurden",
        default_factory=list,
    )

    @model_validator(mode="after")
    def _passt_zur_art(self):
        if self.art == "neu" and (self.sportstaette is None or self.anlagen is None):
            raise ValueError("neu: sportstaette und anlagen nötig")
        if self.art == "organisation":
            if self.loeschen and not self.organisation_id:
                raise ValueError("organisation: zum Löschen organisation_id nötig")
            if not self.loeschen and self.organisation is None:
                raise ValueError("organisation: organisation nötig")
            return self
        if self.art != "neu" and not self.sportstaette_id:
            raise ValueError(f"{self.art}: sportstaette_id nötig")
        if self.art == "aenderung" and self.sportstaette is None:
            raise ValueError("aenderung: sportstaette nötig")
        if self.art == "anlagen" and self.anlagen is None:
            raise ValueError("anlagen: anlagen nötig")
        return self


MODELLE = (Sportstaette, Sportanlage, Adresse, Lage, Organisation, Vorschlag)


# --- Hilfen für den Code --------------------------------------------------------------


def angabe(modell: type[BaseModel], feld: str, schluessel: str, vorgabe=None):
    """Angabe für die Webseite (gruppe, widget, formular …) eines Feldes."""
    if schluessel == "fuer" and modell is Sportanlage:
        return fuer_von(feld) or vorgabe
    extra = modell.model_fields[feld].json_schema_extra or {}
    return extra.get(schluessel, vorgabe)


def datei_felder(modell: type[BaseModel]) -> list[str]:
    """Felder in der Reihenfolge der JSON-Dateien (ohne die, die nicht in der Datei stehen)."""
    return [f for f in modell.model_fields if angabe(modell, f, "datei", True)]


# Umbenannte Felder: alter Name → neuer Name (für `sportstaettenatlas modell --migrieren`)
UMBENANNT = {Sportanlage: {"baukosten_eur": "baukosten"}}


def migriere(d: dict, modell: type[BaseModel]) -> dict:
    """Datensatz auf den Stand des Modells bringen (umbenannte Felder)."""
    out = {UMBENANNT.get(modell, {}).get(k, k): v for k, v in d.items()}
    if modell is Sportanlage and "baukosten_eur" in d and not d.get("waehrung"):
        out["waehrung"] = "€"
    return ordne(out, modell)


def ordne(d: dict, modell: type[BaseModel]) -> dict:
    """Schlüssel in der Reihenfolge des Modells; unbekannte bleiben, hinten angehängt."""
    out = {k: d[k] for k in modell.model_fields if k in d}
    out.update({k: v for k, v in d.items() if k not in out})
    for feld, unter in (("adresse", Adresse), ("lage", Lage)):
        if modell is Sportstaette and isinstance(out.get(feld), dict):
            out[feld] = ordne(out[feld], unter)
    for feld, info in modell.model_fields.items():  # Anzahl je Wert: Reihenfolge der Auswahl
        if angabe(modell, feld, "widget") == "zaehler" and isinstance(out.get(feld), dict):
            reihe = [w.value for w in get_args(info.annotation)[0]]
            out[feld] = dict(
                sorted(
                    out[feld].items(),
                    key=lambda kv: (reihe.index(kv[0]) if kv[0] in reihe else len(reihe), kv[0]),
                )
            )
    return out


_MELDUNG = {
    "missing": "fehlt",
    "string_pattern_mismatch": "Format passt nicht",
    "literal_error": "nicht in der Auswahl",
    "enum": "nicht in der Auswahl",
    "extra_forbidden": "unbekanntes Feld",
    "int_type": "keine ganze Zahl",
    "int_parsing": "keine ganze Zahl",
    "int_from_float": "keine ganze Zahl",
    "float_type": "keine Zahl",
    "float_parsing": "keine Zahl",
    "string_type": "kein Text",
    "list_type": "keine Liste",
    "dict_type": "kein Objekt",
    "string_too_short": "leer",
    "string_too_long": "zu lang",
    "greater_than_equal": "zu klein",
    "less_than_equal": "zu groß",
}


def pruefe(modell: type[BaseModel], daten: dict) -> list[str]:
    """Regelverstöße als lesbare Zeilen ("adresse.plz: Format passt nicht (535474)")."""
    try:
        modell.model_validate(daten)
    except ValidationError as exc:
        out = []
        for e in exc.errors():
            feld = ".".join(str(x) for x in e["loc"] if x != "[key]") or "(Datensatz)"
            if e["type"] == "value_error":
                text = str((e.get("ctx") or {}).get("error", e["msg"]))
                out += [t if not e["loc"] else f"{feld}.{t}" for t in text.split("; ")]
                continue
            text = _MELDUNG.get(e["type"], e["msg"])
            if e["type"] in ("greater_than_equal", "less_than_equal"):
                text += f" ({'mindestens' if e['type'] == 'greater_than_equal' else 'höchstens'} "
                text += f"{next(iter((e.get('ctx') or {}).values()), '')})"
            if e["type"] not in ("missing", "extra_forbidden") and e.get("input") not in (None, ""):
                text += f": {str(e['input'])[:60]}"
            out.append(f"{feld}: {text}")
        return out
    return []


def _auswahl_einsetzen(knoten, auswahl: dict):
    """Verweise auf Auswahllisten ($ref auf ein Enum) durch die Liste selbst ersetzen."""
    if isinstance(knoten, list):
        return [_auswahl_einsetzen(x, auswahl) for x in knoten]
    if not isinstance(knoten, dict):
        return knoten
    out = {k: _auswahl_einsetzen(v, auswahl) for k, v in knoten.items()}
    ziel = out.get("$ref", "").rsplit("/", 1)[-1]
    if ziel in auswahl:
        del out["$ref"]
        out = {**{k: v for k, v in auswahl[ziel].items() if k != "title"}, **out}
    return out


def schema() -> dict:
    """JSON Schema aller Modelle (unter $defs) – für die Webseite (docs/daten/schema.json).
    Auswahllisten stehen dort direkt am Feld (enum), nicht als eigene Definition."""
    _, s = models_json_schema([(m, "validation") for m in MODELLE], title="Sportstättenatlas")
    auswahl = {k: v for k, v in s["$defs"].items() if "enum" in v}
    s["$defs"] = {
        k: _auswahl_einsetzen(v, auswahl) for k, v in s["$defs"].items() if k not in auswahl
    }
    # Pydantic lässt den Titel bei Verweisen weg (z. B. lage → Lage); die Webseite braucht ihn
    for m in MODELLE:
        for name, feld in m.model_fields.items():
            s["$defs"][m.__name__]["properties"][name].setdefault("title", feld.title)
    for name, p in s["$defs"]["Sportanlage"]["properties"].items():
        if fuer := fuer_von(name):
            p["fuer"] = fuer
    # Zuordnungen und Regeln, die nicht an einem Feld hängen (für die Webseite)
    s["atlas"] = {
        "organisationstypen": ORGANISATIONSTYPEN,
        "email": EMAIL_MUSTER,
    }
    s["description"] = "Datenmodell des Sportstättenatlas (aus src/sportstaettenatlas/modell.py)"
    return s


# --- Dokumentation: daten/README.md und Diagramm ---------------------------------------

ANFANG = (
    "<!-- modell:anfang – erzeugt aus src/sportstaettenatlas/modell.py, nicht von Hand ändern -->"
)
ENDE = "<!-- modell:ende -->"


def _ref(t: dict) -> str:
    return t.get("$ref", "").rsplit("/", 1)[-1]


def _auswahl_namen() -> set[str]:
    return {a.__name__ for a in AUSWAHL}


def _typ_text(p: dict) -> str:
    teile = p.get("anyOf") or [p]
    texte = []
    for t in teile:
        if t.get("type") == "null":
            continue
        if _ref(t) in _auswahl_namen():
            texte.append(f"Auswahl [{_ref(t)}](#auswahllisten)")
        elif "$ref" in t:
            texte.append(_ref(t))
        elif "enum" in t or "const" in t:
            texte.append("Auswahl")
        elif t.get("type") == "array":
            innen = t.get("items", {})
            texte.append(
                f"Liste von {innen['$ref'].rsplit('/', 1)[-1]}"
                if "$ref" in innen
                else "Liste von Text"
            )
        else:
            texte.append(
                {
                    "object": "Anzahl je Wert" if "propertyNames" in t else "Objekt",
                    "string": "Text",
                    "integer": "ganze Zahl",
                    "number": "Zahl",
                }.get(t.get("type"), str(t.get("type", "")))
            )
    return " oder ".join(texte)


def _regeln_text(p: dict) -> str:
    teile = p.get("anyOf") or [p]
    out = []
    for t in teile:
        if "enum" in t:
            out.append(", ".join(f"„{w}“" for w in t["enum"]))
        if "const" in t:
            out.append(f"„{t['const']}“")
        if "minimum" in t:
            out.append(f"≥ {t['minimum']:g}")
        if "maximum" in t:
            out.append(f"≤ {t['maximum']:g}")
        if "pattern" in t:
            out.append(f"Muster `{t['pattern']}`")
        if "maxLength" in t:
            out.append(f"höchstens {t['maxLength']} Zeichen")
        if t.get("minLength") == 1:
            out.append("nicht leer")
        if "propertyNames" in t:
            out.append(f"Anzahl je [{_ref(t['propertyNames'])}](#auswahllisten)")
    for k, text in (
        ("braucht", "braucht `{}`"),
        ("teil_von", "Teil von `{}`"),
        ("einheit", "in {}"),
        ("einheit_aus", "Einheit aus `{}`"),
    ):
        if p.get(k):
            out.append(text.format(p[k]))
    if p.get("fuer"):
        out.append("nur für bestimmte Typen ([Felder je Anlagentyp](#felder-je-anlagentyp))")
    return "; ".join(out)


def fuer_text(typen: list[str]) -> str:
    """Typen kurz: ganze Gruppen aus anlagen.GRUPPEN mit ihrem Namen, der Rest einzeln."""
    rest, teile = list(typen), []
    for text, gruppe in anlagen.GRUPPEN.values():
        if len(gruppe) > 1 and all(t in rest for t in gruppe):
            teile.append(text)
            rest = [t for t in rest if t not in gruppe]
    return ", ".join(teile + rest)


def felder_tabelle(modell: type[BaseModel]) -> str:
    s = modell.model_json_schema()
    if modell is Sportanlage:
        for name, p in s["properties"].items():
            if fuer := fuer_von(name):
                p["fuer"] = fuer
    pflicht = set(s.get("required", []))
    zeilen = [
        "| Feld | Bezeichnung | Typ | Pflicht | Regeln | Beschreibung | Weitere Spalte |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, p in s["properties"].items():
        spalte = angabe(modell, name, "spalte")
        zeilen.append(
            f"| `{name}` | {modell.model_fields[name].title or ''} | {_typ_text(p)} | "
            f"{'ja' if name in pflicht else ''} | {_regeln_text(p)} | "
            f"{(p.get('description') or '').replace('|', '/')} | "
            f"{f'`{spalte}`' if spalte else ''} |"
        )
    return "\n".join(zeilen)


def readme_block() -> str:
    """Teil von daten/README.md, der aus dem Modell erzeugt wird."""
    teile = [ANFANG, "", "![Datenmodell](datenmodell.svg)", ""]
    for modell, ueberschrift in (
        (Sportstaette, "Sportstätte (`<id>_meta.json`)"),
        (Adresse, "Adresse"),
        (Lage, "Lage"),
        (Sportanlage, "Sportanlage (`<anlage-id>.json`)"),
        (Organisation, "Organisation (`organisationen/<id>.json`)"),
        (Vorschlag, "Vorschlag (Formular → LimeSurvey, Frage `data`)"),
    ):
        teile += [f"### {ueberschrift}", ""]
        if modell.__doc__:
            teile += [modell.__doc__.strip(), ""]
        teile += [felder_tabelle(modell), ""]
        beispiele = (modell.model_config.get("json_schema_extra") or {}).get("examples")
        if beispiele:
            teile += ["```json", json.dumps(beispiele[0], ensure_ascii=False, indent=2), "```", ""]
    titel = {k: f.title for k, f in Sportanlage.model_fields.items()}
    teile += [
        "### Felder je Anlagentyp",
        "",
        "Felder, die nicht hier stehen, gelten für alle Typen.",
        "",
    ]
    teile += ["| Anlagentypen | Felder |", "|---|---|"]
    for typen, felder in MERKMALE:
        teile.append(f"| {fuer_text(list(typen))} | {', '.join(titel[f] for f in felder)} |")
    teile += ["", "### Auswahllisten", "", "| Liste | Werte |", "|---|---|"]
    for a in AUSWAHL:
        teile.append(f"| {a.__name__} | " + ", ".join(f"„{w.value}“" for w in a) + " |")
    teile += [""]
    teile.append(ENDE)
    return "\n".join(teile)


def aktualisiere_readme(pfad: Path) -> bool:
    """Ersetzt den erzeugten Teil in daten/README.md. Liefert True, wenn sich etwas änderte."""
    text = pfad.read_text("utf-8") if pfad.exists() else ""
    block = readme_block()
    if ANFANG.split(" –")[0] in text and ENDE in text:
        a = text.index(ANFANG.split(" –")[0])
        e = text.index(ENDE) + len(ENDE)
        neu = text[:a] + block + text[e:]
    else:
        neu = text.rstrip() + "\n\n## Datenmodell\n\n" + block + "\n"
    if neu != text:
        pfad.write_text(neu, "utf-8")
        return True
    return False


def zeichne(ziel: Path) -> bool:
    """Diagramm mit erdantic (braucht Graphviz). False, wenn erdantic fehlt."""
    try:
        import erdantic as erd
    except ImportError:
        return False
    erd.draw(Vorschlag, out=ziel)
    return True


def schreibe_doku(ordner: Path) -> list[str]:
    """daten/README.md und daten/datenmodell.svg aus dem Modell. Liefert Hinweise."""
    hinweise = []
    if aktualisiere_readme(ordner / "README.md"):
        hinweise.append(f"{ordner}/README.md: Datenmodell aktualisiert")
    if zeichne(ordner / "datenmodell.svg"):
        hinweise.append(f"{ordner}/datenmodell.svg geschrieben")
    else:
        hinweise.append(
            "Diagramm nicht erzeugt: erdantic fehlt (sudo apt install graphviz graphviz-dev; "
            "uv sync --extra doku)"
        )
    return hinweise
