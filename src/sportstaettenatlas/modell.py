"""Datenmodell des Sportstättenatlas – die einzige Stelle, an der Felder und Regeln stehen.

Ein neues Feld, eine neue Auswahl oder eine neue Regel wird nur hier eingetragen. Daraus
leiten sich ab:

- Prüfen beim Lesen und Schreiben von daten/ (bestand.py) und Reihenfolge der Felder
  in den JSON-Dateien
- Eigenschaften der Sportstätten auf der Karte (seite.bestand_geojson)
- docs/daten/schema.json (JSON Schema): Formular „Vorschlag“, Popup und Übersicht der Webseite
- `Vorschlag`: der JSON-Text, den das Formular an LimeSurvey übergibt (Frage „data“)
- daten/README.md (Feldtabellen und Beispiele) und daten/datenmodell.svg (Diagramm)
  – `sportstaettenatlas modell`, läuft auch bei `seite` mit

Angaben je Feld (json_schema_extra, landen im Schema):
  gruppe      Abschnitt im Formular und in der Übersicht (Reihenfolge: GRUPPEN bzw.
              ANLAGE_GRUPPEN)
  widget      besondere Eingabe/Anzeige: ja_nein, karte, chips, organisation, ort, url,
              anlagentyp, jahr, zaehler (Anzahl je Wert, z. B. Felder je Belag)
  formular    False: nicht im Formular (IDs, Herkunft)
  uebersicht  False: zählt nicht zur Vollständigkeit in der Übersicht
  einheit     wird hinter Zahlen angezeigt (z. B. m²); einheit_aus: aus einem anderen Feld
              (Baukosten → Währung)
  fuer        nur für diese Gruppen (anlagen.GRUPPEN) oder Typen von Sportanlagen gedacht
  legacy      Name des Feldes im alten Sportstättenatlas (für Übernahmen)
Regeln zwischen Feldern (prüft Basis, das Formular ebenso):
  braucht     dieses Feld braucht das genannte (Baukosten → Währung)
  teil_von    Werte müssen auch im genannten Feld stehen (Wettkampfeignung → Sportarten)
Zusätzlich als Hinweis (kein Fehler): passt der Typ einer Sportanlage zur Kategorie der
Sportstätte (KATEGORIE_ANLAGEN)?
"""

from __future__ import annotations

import json
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
# Art von Eigentümer und Betreiber (Legacy: organisation.typid) → Art auf der Karte
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

Kategorie = Literal[KATEGORIEN]
Betriebsstatus = Literal[BETRIEBSSTATUS]
Organisationstyp = Literal[tuple(ORGANISATIONSTYPEN)]
JaNein = Literal["ja", "nein"]
Anzahl = Annotated[int, Field(ge=0, le=10_000)]

# Welche Sportanlagen zu welcher Kategorie passen (Legacy: sst_san_rel, dort leer).
# Einträge: Gruppen aus anlagen.GRUPPEN oder einzelne Typen. Dazu passen immer
# IMMER_PASSEND. Kategorien ohne Eintrag: alles passt. Verstöße sind Hinweise, keine Fehler.
IMMER_PASSEND = ("neben", "sonstige Sportanlage")
KATEGORIE_ANLAGEN: dict[str, tuple[str, ...]] = {
    "Sportplatz": (
        "spielfeld",
        "leichtathletik",
        "Bouleanlage",
        "Calisthenicsanlage",
        "Bewegungsparcours",
    ),
    "Sporthalle": ("halle", "Kegelbahn", "Klettersporthalle", "Skatehalle"),
    "Tennissportstätte": ("tennis", "Squashhalle"),
    "Öffentlicher Sport- und Bewegungsraum": (
        "spielfeld",
        "freizeit",
        "Weit- und Dreisprunganlage",
        "Kurzstreckenbahn",
        "Mountainbikestrecke",
        "BMX-Strecke",
    ),
    "Reitsportstätte": ("reiten", "Rennbahn"),
    "Schwimmsportstätte": ("bad", "Volleyballfeld", "Beachvolleyballfeld"),
    "Schießsportstätte": ("schiessen",),
    "Fitnessstudio": (
        "Übungsraum",
        "Kurs-/Übungsraum",
        "Kraftraum",
        "Squashhalle",
        "Klettersporthalle",
    ),
    "Golfsportstätte": ("Golfplatz", "Bahnengolf"),
    "Roll- und Skatesportstätte": ("Skateplatz", "Skatehalle", "Rollsportplatz", "BMX-Strecke"),
    "Sportgelegenheiten in sonstigen Gebäuden": ("halle", "Kegelbahn", "Bowlingbahn"),
    "Radsportstätte": (
        "Mountainbikestrecke",
        "BMX-Strecke",
        "Radrennbahn",
        "Fahrparcours",
        "Rennbahn",
    ),
    "Flugsportstätte": ("luft",),
    "Wintersportstätte": ("winter",),
    "Wassersportstätte": ("wasser",),
    "Segelsportstätte": ("wasser", "luft"),
    "Klettersportstätte": ("Klettersportanlage Outdoor", "Klettersporthalle"),
    "Motorsportstätte": (
        "Motocross-Strecke",
        "Kartbahn",
        "Motorsport-Rennstrecke",
        "Rennbahn",
        "Fahrparcours",
        "Rundrennstrecke (Motorboot)",
    ),
    "Eissportstätte": ("Eissporthalle", "Eissportanlage ungedeckt"),
}

# Abschnitte des Formulars in dieser Reihenfolge
GRUPPEN = ("Sportstätte", "Adresse und Lage", "Nutzung", "Sportarten", "Eigentümer und Betreiber")
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

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

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
    strasse: str | None = _f("Straße", max_length=150, legacy="adresse.strasse")
    hausnummer: str | None = _f(
        "Hausnummer",
        "z. B. 12, 12a oder 2-4",
        max_length=12,
        pattern=r"^\d+\s?[a-zA-Z]?(\s?[-/]\s?\d+\s?[a-zA-Z]?)?$",
        legacy="adresse.hausnummer",
    )
    adresszusatz: str | None = _f(
        "Adresszusatz",
        "z. B. Eingang Schulhof",
        max_length=150,
        uebersicht=False,
        legacy="adresse.adresszusatz",
    )
    plz: str | None = _f("PLZ", "fünf Ziffern", pattern=r"^\d{5}$", legacy="adresse.postleitzahl")
    ort: str | None = _f("Ort", max_length=100, widget="ort", legacy="adresse.ort")


class Lage(Basis):
    """Immer WGS84 (EPSG:4326), Grad mit Dezimalstellen."""

    lon: float = _f(
        "Längengrad", "WGS84", pflicht=True, ge=5.8, le=9.0, legacy="utm32nrechts (umgerechnet)"
    )
    lat: float = _f(
        "Breitengrad", "WGS84", pflicht=True, ge=48.8, le=51.1, legacy="utm32nhoch (umgerechnet)"
    )


# Angaben je Feld der Sportanlage zusätzlich:
#   fuer    Gruppen aus anlagen.GRUPPEN oder Typen, für die das Feld gedacht ist (sonst alle);
#           das Formular zeigt nur diese, die Übersicht zählt die Befüllung nur unter ihnen
#   legacy  Name des Feldes im alten Sportstättenatlas (Laravel, Tabelle sportanlage)
_HALLEN = (
    "halle",
    "Tennishalle",
    "Reithalle",
    "Führ- und Longierhalle",
    "Eissporthalle",
    "Klettersporthalle",
    "Skatehalle",
)
_KLETTERN = ("halle", "Klettersportanlage Outdoor", "Klettersporthalle")
_FLAECHEN = ("spielfeld", "tennis", "halle", "leichtathletik", "reiten", "freizeit")
_DRAUSSEN = ("spielfeld", "tennis", "leichtathletik", "reiten", "freizeit", "rad_motor", "winter")


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
        "einheitlicher Typ aus src/sportstaettenatlas/anlagen.py, z. B. „Großspielfeld“; "
        "soll zur Kategorie der Sportstätte passen (KATEGORIE_ANLAGEN)",
        pflicht=True,
        min_length=1,
        max_length=100,
        widget="anlagentyp",
        uebersicht=False,
        legacy="typid",
    )
    bezeichnung: str | None = _a(
        "Name",
        "eigener Name der Anlage, z. B. „Halle 1“, „Kunstrasen B“",
        max_length=100,
        legacy="bezeichnung",
    )
    betriebsstatus: Betriebsstatus | None = _a("Betriebsstatus", legacy="betriebsstatustypid")
    baujahr: int | None = _a("Baujahr", ge=1800, le=2100, widget="jahr", legacy="baujahr")
    letzte_sanierung: int | None = _a(
        "Letzte Sanierung", "Jahr", ge=1800, le=2100, widget="jahr", legacy="letzteSanierung"
    )
    # Sportarten
    sportarten: list[str] = _a("Sportarten", gruppe="Sportarten", default_factory=list)
    wettkampf: list[str] = _a(
        "Wettkampfeignung",
        "Sportarten, für die die Anlage wettkampfgeeignet ist (müssen unter Sportarten stehen)",
        gruppe="Sportarten",
        default_factory=list,
        teil_von="sportarten",
        legacy="sportanlagesportart.wettkampfeignung",
    )
    # Maße
    laenge: float | None = _n(
        "Länge", "der Sportfläche", einheit="m", fuer=_FLAECHEN + ("bad",), legacy="laenge"
    )
    breite: float | None = _n(
        "Breite", "der Sportfläche", einheit="m", fuer=_FLAECHEN + ("bad",), legacy="breite"
    )
    hoehe: float | None = _n(
        "Höhe", "lichte Höhe der Halle", einheit="m", fuer=_HALLEN, legacy="hoehe"
    )
    flaeche: float | None = _n(
        "Fläche",
        "nutzbare Sportfläche, wenn nicht Länge × Breite (z. B. Reitplatz)",
        einheit="m²",
        legacy="groesse",
    )
    bahnlaenge: float | None = _n(
        "Bahnlänge",
        einheit="m",
        fuer=(
            "leichtathletik",
            "bad",
            "rad_motor",
            "winter",
            "wasser",
            "schiessen",
            "Kegelbahn",
            "Bowlingbahn",
        ),
        legacy="bahnlaenge",
    )
    bahnen: int | None = _n(
        "Bahnen",
        "Zahl der Lauf-, Schwimm-, Kegel- oder Schießbahnen",
        fuer=("leichtathletik", "bad", "schiessen", "Kegelbahn", "Bowlingbahn"),
        legacy="anzbahnen",
    )
    # Belag und Felder
    bodenbelag: Literal[BODENBELAEGE] | None = _a(
        "Bodenbelag", gruppe="Belag und Felder", fuer=_FLAECHEN, legacy="bodenbelagtypid"
    )
    felder_je_belag: dict[Literal[BODENBELAEGE], Anzahl] = _a(
        "Felder je Belag",
        "z. B. Tennisplätze: 3 Sand, 1 Kunstrasen",
        gruppe="Belag und Felder",
        default_factory=dict,
        widget="zaehler",
        fuer=("tennis", "spielfeld"),
        legacy="bodenbelag_anz_*",
    )
    spielfelder: int | None = _n(
        "Spielfelder",
        "Zahl, wenn nicht nach Sportart bekannt",
        gruppe="Belag und Felder",
        fuer=("spielfeld", "halle", "tennis"),
        legacy="anzspielfelder",
    )
    felder_je_sportart: dict[Literal[SPIELFELDER], Anzahl] = _a(
        "Spielfelder je Sportart",
        "markierte Felder, z. B. 3 Badminton, 1 Handball",
        gruppe="Belag und Felder",
        default_factory=dict,
        widget="zaehler",
        fuer=("spielfeld", "halle"),
        legacy="anz_feld_*",
    )
    kleinfelder_je_sportart: dict[Literal[KLEINFELDER], Anzahl] = _a(
        "Kleinfelder je Sportart",
        gruppe="Belag und Felder",
        default_factory=dict,
        widget="zaehler",
        fuer=("spielfeld", "halle"),
        legacy="anz_kleinfeld_*",
    )
    loecher: int | None = _n(
        "Löcher",
        "Golf, Bahnengolf",
        gruppe="Belag und Felder",
        fuer=("Golfplatz", "Bahnengolf"),
        legacy="anzloecher",
    )
    # Becken
    wasserflaeche: float | None = _n(
        "Wasserfläche",
        "gesamt",
        gruppe="Becken",
        einheit="m²",
        fuer=("bad",),
        legacy="wasserflaeche",
    )
    wasserflaeche_relevant: float | None = _n(
        "Relevante Wasserfläche",
        "ohne Kaltwassertret-, Warmsprudelbecken usw.",
        gruppe="Becken",
        einheit="m²",
        fuer=("bad",),
        legacy="relevante_wasserflaeche",
    )
    wasserflaeche_lehrbecken: float | None = _n(
        "Wasserfläche Lern- und Kursbecken",
        gruppe="Becken",
        einheit="m²",
        fuer=("bad",),
        legacy="wasserflaechelernundkursbecken",
    )
    becken_bis_25m: int | None = _n(
        "Becken bis 25 m", gruppe="Becken", fuer=("bad",), legacy="anzbeckenbis25"
    )
    becken_25_bis_50m: int | None = _n(
        "Becken 25 bis 50 m", gruppe="Becken", fuer=("bad",), legacy="anzbeckenbis25bis50"
    )
    becken_ueber_50m: int | None = _n(
        "Becken über 50 m", gruppe="Becken", fuer=("bad",), legacy="anzbeckenueber50"
    )
    becken_tiefer_3m: int | None = _n(
        "Becken tiefer als 3 m", gruppe="Becken", fuer=("bad",), legacy="anzbeckenue3m"
    )
    nichtschwimmerbecken: int | None = _n(
        "Nichtschwimmerbecken", gruppe="Becken", fuer=("bad",), legacy="anznichtschwimmer"
    )
    lehrbecken: int | None = _n(
        "Lehrbecken", gruppe="Becken", fuer=("bad",), legacy="anzlehrbecken"
    )
    kinderbecken: int | None = _n(
        "Kinderbecken", gruppe="Becken", fuer=("bad",), legacy="anzkinderbecken"
    )
    erholungsbecken: int | None = _n(
        "Erholungsbecken", gruppe="Becken", fuer=("bad",), legacy="anzerholungsbecken"
    )
    sprungturm: JaNein | None = _jn(
        "Sprungturm", "mindestens einer", gruppe="Becken", fuer=("bad",), legacy="sprungturm"
    )
    sprungtuerme_3m: int | None = _n(
        "Sprungtürme 3 m", gruppe="Becken", fuer=("bad",), legacy="anzturm3m"
    )
    sprungtuerme_5m: int | None = _n(
        "Sprungtürme 5 m", gruppe="Becken", fuer=("bad",), legacy="anztur5m"
    )
    sprungtuerme_10m: int | None = _n(
        "Sprungtürme 10 m", gruppe="Becken", fuer=("bad",), legacy="anztur10m"
    )
    baederleben_id: str | None = _a(
        "ID bei baederleben.de",
        gruppe="Becken",
        max_length=50,
        fuer=("bad",),
        uebersicht=False,
        legacy="baederlebenid",
    )
    # Ausstattung
    trennvorhang: JaNein | None = _jn(
        "Trennvorhang",
        "zur Hallenteilung oder für eine Bühne",
        fuer=("halle", "neben"),
        legacy="vorhangvorhanden",
    )
    bewaesserung: JaNein | None = _jn(
        "Bewässerung", fuer=("spielfeld", "tennis", "reiten", "Golfplatz"), legacy="bewaesserung"
    )
    hoehenverstellbares_netz: JaNein | None = _jn(
        "Höhenverstellbares Netz",
        fuer=("Volleyballfeld", "Beachvolleyballfeld"),
        legacy="hoehenverstellnetz",
    )
    kletterwand: JaNein | None = _jn("Kletterwand", fuer=_KLETTERN, legacy="kletterwand")
    boulderwand: JaNein | None = _jn("Boulderwand", fuer=_KLETTERN, legacy="boulderwand")
    dressurplatz: JaNein | None = _jn("Dressurplatz", fuer=("reiten",), legacy="dressurplatz")
    springplatz: JaNein | None = _jn("Springplatz", fuer=("reiten",), legacy="springplatz")
    schiessstaende_gedeckt: int | None = _n(
        "Schießstände gedeckt",
        gruppe="Ausstattung",
        fuer=("schiessen",),
        legacy="anzschiesstubgedeckt",
    )
    schiessstaende_teilgedeckt: int | None = _n(
        "Schießstände teilgedeckt",
        gruppe="Ausstattung",
        fuer=("schiessen",),
        legacy="anzschiesstuboteilgedeckt",
    )
    schiessstaende_offen: int | None = _n(
        "Schießstände offen", gruppe="Ausstattung", fuer=("schiessen",), legacy="anzschiesstuboffen"
    )
    lifte: int | None = _n("Lifte", gruppe="Ausstattung", fuer=("winter",), legacy="anzlift")
    spielgeraete: int | None = _n(
        "Spielgeräte", gruppe="Ausstattung", fuer=("freizeit",), legacy="anz_spielgeraete"
    )
    ausstattung: list[str] = _a(
        "Weitere Ausstattung",
        "z. B. Umkleiden, Anzeigetafel",
        gruppe="Ausstattung",
        default_factory=list,
    )
    # Licht
    flutlicht: JaNein | None = _jn("Flutlicht", gruppe="Licht", fuer=_DRAUSSEN, legacy="flutlicht")
    leuchtmittel: Literal[LEUCHTMITTEL] | None = _a(
        "Leuchtmittel", gruppe="Licht", legacy="leuchtmitteltypid"
    )
    lux: Literal[LUXWERTE] | None = _a(
        "Beleuchtungsstärke", gruppe="Licht", einheit="lx", legacy="luxwerttypid"
    )
    # Nutzung
    oeffnungsstunden: int | None = _n(
        "Öffnungsstunden",
        "im Jahr, insgesamt",
        gruppe="Nutzung",
        le=8784,
        einheit="h",
        legacy="oeffnungsstunden",
    )
    oeffnungsstunden_schule: int | None = _n(
        "davon Schulsport",
        "Stunden im Jahr",
        gruppe="Nutzung",
        le=8784,
        einheit="h",
        legacy="oeffnungsstundenschule",
    )
    oeffnungsstunden_verein: int | None = _n(
        "davon Vereine",
        "Stunden im Jahr",
        gruppe="Nutzung",
        le=8784,
        einheit="h",
        legacy="oeffnungsstundenverein",
    )
    altersempfehlung: str | None = _a(
        "Altersempfehlung",
        "z. B. 6–12 Jahre",
        gruppe="Nutzung",
        max_length=50,
        fuer=("freizeit",),
        legacy="altersempfehlung",
    )
    # Barrierefreiheit
    barrierefrei_erreichbar: JaNein | None = _jn(
        "Barrierefrei erreichbar", gruppe="Barrierefreiheit", legacy="barrierefreierreichbar"
    )
    geeignet_mobilitaet: JaNein | None = _jn(
        "Geeignet bei eingeschränkter Mobilität",
        gruppe="Barrierefreiheit",
        legacy="eignungparasport1",
    )
    geeignet_sehen: JaNein | None = _jn(
        "Geeignet bei Sehbeeinträchtigung", gruppe="Barrierefreiheit", legacy="eignungparasport2"
    )
    geeignet_kleinwuchs: JaNein | None = _jn(
        "Geeignet für Kleinwüchsige", gruppe="Barrierefreiheit", legacy="eignungparasport3"
    )
    geeignet_mental: JaNein | None = _jn(
        "Geeignet bei geistiger Beeinträchtigung",
        gruppe="Barrierefreiheit",
        legacy="eignungparasport4",
    )
    # Kosten
    baukosten: float | None = _n(
        "Baukosten",
        "damalige Kosten",
        gruppe="Kosten",
        braucht="waehrung",
        einheit_aus="waehrung",
        legacy="baukosten",
    )
    waehrung: Literal[WAEHRUNGEN] | None = _a(
        "Währung", "der Baukosten", gruppe="Kosten", uebersicht=False, legacy="waehrung"
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
        legacy="bezeichnung",
    )
    kategorie: Kategorie = _f(
        "Sportstättenkategorie", pflicht=True, gruppe="Sportstätte", legacy="typid"
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
        legacy="oeffentlich",
    )
    schulsport: JaNein | None = _f(
        "Schulsport", gruppe="Nutzung", widget="ja_nein", legacy="schulsport"
    )
    zuschauerplaetze: int | None = _f(
        "Zuschauerplätze", ge=0, le=100_000, gruppe="Nutzung", legacy="zuschauerplatzgesamt"
    )
    betriebsstatus: Betriebsstatus | None = _f(
        "Betriebsstatus", gruppe="Sportstätte", legacy="betriebsstatustypid"
    )
    eigentuemer: str | None = _f(
        "Eigentümer",
        "Name einer Organisation, keine Personen",
        max_length=200,
        gruppe="Eigentümer und Betreiber",
        widget="organisation",
        legacy="eignerbezeichnung",
    )
    eigentuemer_typ: Organisationstyp | None = _f(
        "Art des Eigentümers",
        gruppe="Eigentümer und Betreiber",
        braucht="eigentuemer",
        legacy="eignertyp",
    )
    betreiber: str | None = _f(
        "Betreiber",
        "Name einer Organisation, keine Personen",
        max_length=200,
        gruppe="Eigentümer und Betreiber",
        widget="organisation",
        legacy="betreiberbezeichnung",
    )
    betreiber_typ: Organisationstyp | None = _f(
        "Art des Betreibers",
        gruppe="Eigentümer und Betreiber",
        braucht="betreiber",
        legacy="betreibertyp",
    )
    website: str | None = _f(
        "Webseite",
        "vollständige Adresse mit https://",
        pattern=r"^https?://\S+\.\S+$",
        gruppe="Eigentümer und Betreiber",
        widget="url",
        legacy="url",
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
    art: Literal["neu", "aenderung", "anlagen"] = _f(
        "Art",
        "neu: neue Sportstätte mit Anlagen; aenderung: Angaben einer Sportstätte; "
        "anlagen: Sportanlagen einer Sportstätte",
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
    geaendert: list[str] = _f("Geänderte Felder", default_factory=list)
    gemeinde: str | None = _f("Gemeinde", "Regionalschlüssel der Gemeinde an der Lage")
    quelle: str | None = _f("Quelle", "z. B. „ALKIS ST000123“, wenn vorbelegt")
    dubletten_geprueft: list[str] = _f(
        "Geprüfte Doppelungen",
        "IDs ähnlicher Sportstätten, die als verschieden bestätigt wurden",
        default_factory=list,
    )

    @model_validator(mode="after")
    def _passt_zur_art(self):
        if self.art == "neu" and (self.sportstaette is None or self.anlagen is None):
            raise ValueError("neu: sportstaette und anlagen nötig")
        if self.art != "neu" and not self.sportstaette_id:
            raise ValueError(f"{self.art}: sportstaette_id nötig")
        if self.art == "aenderung" and self.sportstaette is None:
            raise ValueError("aenderung: sportstaette nötig")
        if self.art == "anlagen" and self.anlagen is None:
            raise ValueError("anlagen: anlagen nötig")
        return self


MODELLE = (Sportstaette, Sportanlage, Adresse, Lage, Vorschlag)


# --- Hilfen für den Code --------------------------------------------------------------


def angabe(modell: type[BaseModel], feld: str, schluessel: str, vorgabe=None):
    """Angabe für die Webseite (gruppe, widget, formular …) eines Feldes."""
    extra = modell.model_fields[feld].json_schema_extra or {}
    return extra.get(schluessel, vorgabe)


def datei_felder(modell: type[BaseModel]) -> list[str]:
    """Felder in der Reihenfolge der JSON-Dateien (ohne die, die nicht in der Datei stehen)."""
    return [f for f in modell.model_fields if angabe(modell, f, "datei", True)]


def passende_typen(kategorie: str | None) -> list[str] | None:
    """Anlagentypen, die zur Kategorie passen (KATEGORIE_ANLAGEN); None: alle passen."""
    eintraege = KATEGORIE_ANLAGEN.get(kategorie or "")
    if not eintraege:
        return None
    out = []
    for e in (*eintraege, *IMMER_PASSEND):
        out += list(anlagen.GRUPPEN[e][1]) if e in anlagen.GRUPPEN else [e]
    return list(dict.fromkeys(out))


def zuordnung_hinweise(kategorie: str | None, typen) -> list[str]:
    """Hinweise zu Sportanlagen, deren Typ nicht zur Kategorie der Sportstätte passt."""
    passend = passende_typen(kategorie)
    if passend is None:
        return []
    return [
        f"typ: „{t}“ passt nicht zur Kategorie „{kategorie}“"
        for t in dict.fromkeys(typen)
        if t not in passend
    ]


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
            reihe = get_args(get_args(info.annotation)[0])
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


def schema() -> dict:
    """JSON Schema aller Modelle (unter $defs) – für die Webseite (docs/daten/schema.json)."""
    _, s = models_json_schema([(m, "validation") for m in MODELLE], title="Sportstättenatlas")
    # Pydantic lässt den Titel bei Verweisen weg (z. B. lage → Lage); die Webseite braucht ihn
    for m in MODELLE:
        for name, feld in m.model_fields.items():
            s["$defs"][m.__name__]["properties"][name].setdefault("title", feld.title)
    s["$defs"]["Sportstaette"]["anlagen_je_kategorie"] = {
        k: passende_typen(k) for k in KATEGORIEN if passende_typen(k) is not None
    }
    s["$defs"]["Sportstaette"]["organisationstypen"] = ORGANISATIONSTYPEN
    s["description"] = "Datenmodell des Sportstättenatlas (aus src/sportstaettenatlas/modell.py)"
    return s


# --- Dokumentation: daten/README.md und Diagramm ---------------------------------------

ANFANG = (
    "<!-- modell:anfang – erzeugt aus src/sportstaettenatlas/modell.py, nicht von Hand ändern -->"
)
ENDE = "<!-- modell:ende -->"


def _typ_text(p: dict) -> str:
    teile = p.get("anyOf") or [p]
    texte = []
    for t in teile:
        if t.get("type") == "null":
            continue
        if "$ref" in t:
            texte.append(t["$ref"].rsplit("/", 1)[-1])
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
            out.append("Anzahl je " + ", ".join(f"„{w}“" for w in t["propertyNames"]["enum"]))
    for k, text in (
        ("braucht", "braucht `{}`"),
        ("teil_von", "Teil von `{}`"),
        ("einheit", "in {}"),
        ("einheit_aus", "Einheit aus `{}`"),
    ):
        if p.get(k):
            out.append(text.format(p[k]))
    if p.get("fuer"):
        out.append("nur für " + ", ".join(p["fuer"]))
    return "; ".join(out)


def felder_tabelle(modell: type[BaseModel]) -> str:
    s = modell.model_json_schema()
    pflicht = set(s.get("required", []))
    zeilen = [
        "| Feld | Bezeichnung | Typ | Pflicht | Regeln | Beschreibung | Legacy |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, p in s["properties"].items():
        legacy = angabe(modell, name, "legacy")
        zeilen.append(
            f"| `{name}` | {modell.model_fields[name].title or ''} | {_typ_text(p)} | "
            f"{'ja' if name in pflicht else ''} | {_regeln_text(p)} | "
            f"{(p.get('description') or '').replace('|', '/')} | "
            f"{f'`{legacy}`' if legacy else ''} |"
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
        (Vorschlag, "Vorschlag (Formular → LimeSurvey, Frage `data`)"),
    ):
        teile += [f"### {ueberschrift}", ""]
        if modell.__doc__:
            teile += [modell.__doc__.strip(), ""]
        teile += [felder_tabelle(modell), ""]
        beispiele = (modell.model_config.get("json_schema_extra") or {}).get("examples")
        if beispiele:
            teile += ["```json", json.dumps(beispiele[0], ensure_ascii=False, indent=2), "```", ""]
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
