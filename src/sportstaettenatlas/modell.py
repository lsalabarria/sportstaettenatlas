"""Datenmodell des Sportstättenatlas – die einzige Stelle, an der Felder und Regeln stehen.

Was daraus abgeleitet wird: README.md („Datenmodell im Code“); was die Felder bedeuten:
daten/README.md (zum Teil aus diesem Modul erzeugt).

Angaben je Feld (json_schema_extra, landen im Schema):
  gruppe      Abschnitt im Formular und in der Übersicht (Reihenfolge: GRUPPEN bzw.
              ANLAGE_GRUPPEN)
  widget      besondere Eingabe/Anzeige: ja_nein, karte, chips, organisation, ort, url,
              anlagentyp, jahr, zaehler (Anzahl je Wert, z. B. Felder je Belag),
              organisationen (Liste von Namen aus dem Verzeichnis der Organisationen)
  formular    False: nicht im Formular (IDs)
  uebersicht  False: zählt nicht zur Vollständigkeit in der Übersicht
  einheit     wird hinter Zahlen angezeigt (z. B. m²); einheit_aus: aus einem anderen Feld
              (Baukosten → Währung)
  (fuer       steht nicht am Feld: folgt aus MERKMALE, siehe fuer_von)
Regeln zwischen Feldern (prüft Basis, das Formular ebenso):
  braucht     dieses Feld braucht das genannte (Baukosten → Währung)
  teil_von    Werte müssen auch im genannten Feld stehen (Wettkampfeignung → Sportarten)
  nachkommastellen  Zahl braucht mindestens so viele (Koordinaten: 4, etwa 10 m)
"""

from __future__ import annotations

import inspect
import json
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal, get_args

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
# Arten von Stützpunkten, je Ebene (Übersicht und Filter der Webseite zählen nach Ebene)
STUETZPUNKTARTEN = {
    "Olympiastützpunkt": "Olympia",
    "Bundesstützpunkt": "Bund",
    "Bundesstützpunkt Nachwuchs": "Bund",
    "Bundesstützpunkt Para Sport": "Bund",
    "Landesleistungszentrum": "Land",
    "Landesstützpunkt": "Land",
}

# Art einer Organisation → Art auf der Karte; die Art bestimmt auch den Ordner in
# daten/organisationen/<LAND>/ (bestand.org_pfad)
ORGANISATIONSTYPEN = {
    "Bund": "sonstige",
    "Land Rheinland-Pfalz": "sonstige",
    "Landkreis": "Kommune",
    "Kreisfreie Stadt": "Kommune",
    "Verbandsgemeinde": "Kommune",
    "Verbandsfreie Gemeinde": "Kommune",
    "Verbandsangehörige Stadt": "Kommune",
    "Ortsgemeinde": "Kommune",
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
WAEHRUNGEN = ("€", "DM", "DDR-Mark", "RM")
FASSADEN = (
    "Klinker",
    "Vorhangfassade",
    "Putz",
    "Sichtbeton",
    "Glas",
    "Wärmedämmverbundsystem",
    "Holz",
    "Mauerwerk mit Anstrich",
    "Sonstiges",
    "nicht zutreffend",
)
WETTKAMPFANLAGEN = (
    "keine Wettkampfanlage",
    "Wettkampfanlage Typ A",
    "Wettkampfanlage Typ B",
    "Wettkampfanlage Typ C",
)
FUNKTIONSRAEUME = (
    "Umkleide- und Sanitärräume - Sporttreibende",
    "Umkleide- und Sanitärräume - Personal",
    "Sanitärräume - Publikum",
    "Erste-Hilfe-Räume",
    "Büro- und Verwaltungsräume",
    "Material- und Lagerräume",
    "Geräteräume",
    "Technikräume",
    "Schulungs- / Seminarraum",
    "Gastronomie",
    "Sauna",
)
ENERGIEBEREICHE = ("Heizung", "Warmwasser", "Strom")
ENERGIETRAEGER = (
    "Erdgas",
    "Flüssiggas",
    "Heizöl",
    "Holz/Pellets/Hackschnitzel",
    "Fernwärme",
    "Umweltwärme (Wärmepumpe)",
    "Solarthermie",
    "Strom (z.B. Nachtspeicherofen, Konvektoren etc.)",
    "Strom (z.B. Durchlauferhitzer, Boiler)",
    "Betrieb über Heizanlage",
    "Photovoltaik-Anlage",
    "Windkraftanlage",
    "Sonstige",
)
VERBRAUCHSARTEN = (
    "Erdgas",
    "Fernwärme",
    "Flüssiggas",
    "Heizöl",
    "Holz/Pellets/Hackschnitzel",
    "Strom",
)
EINHEITEN = ("kWh", "Liter", "m³", "Festmeter", "Tonnen", "Schüttraummeter")
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
Stuetzpunktart = _auswahl("Stuetzpunktart", STUETZPUNKTARTEN)
Fassade = _auswahl("Fassade", FASSADEN)
Wettkampfanlage = _auswahl("Wettkampfanlage", WETTKAMPFANLAGEN)
Funktionsraum = _auswahl("Funktionsraum", FUNKTIONSRAEUME)
Energiebereich = _auswahl("Energiebereich", ENERGIEBEREICHE)
Energietraegerart = _auswahl("Energietraegerart", ENERGIETRAEGER)
Verbrauchsart = _auswahl("Verbrauchsart", VERBRAUCHSARTEN)
Einheit = _auswahl("Einheit", EINHEITEN)
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
    Stuetzpunktart,
    Fassade,
    Wettkampfanlage,
    Funktionsraum,
    Energiebereich,
    Energietraegerart,
    Verbrauchsart,
    Einheit,
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
UUID_MUSTER = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

# Grenzen und Muster der Prüfungen auf Doppelungen. Sie gelten in validate.py und im Formular
# (schema.json → atlas.pruefung); tests/regeln_faelle.json prüft, dass beide gleich rechnen.
PRUEFUNG = {
    "aehnlich": 0.8,  # Namen mindestens so ähnlich (Dice-Koeffizient der Buchstabenpaare) …
    "nah_m": 60,  # … und höchstens so weit auseinander: wohl dieselbe Sportstätte
    "gleicher_name": 0.99,  # Formular: ab hier „gleicher Name“
    "kategorie_nah_m": 250,  # Formular: gleiche Kategorie so nah – mögliche Doppelung
    "name_nah_m": 3000,  # Formular: ein ähnlicher Name zählt nur so nah
    "komplex_nah_m": 3000,  # Formular: Sportkomplexe in diesem Umkreis zur Auswahl
    # Rechtsform, zählt beim Vergleich von Organisationen nicht (auf den Namen nach norm_name)
    "rechtsform": r"\b(e ?v|g?gmbh|mbh|ag|kg|ug|gbr)\b",
}
# Meldungen der Regeln zwischen Feldern (zwischen_feldern; im Formular grundlagen.js). {feld}
# ist in Python der Name des Feldes (die Regelverstöße zählen danach), im Formular sein Titel.
MELDUNGEN = {
    "braucht": "{feld}: nötig, wenn {wenn} angegeben ist",
    "nachkommastellen": "{feld}: mindestens {n} Nachkommastellen ({wert} ist zu ungenau)",
    "teil_von": "{feld}: {fehlt} fehlt unter {unter}",
}

# Abschnitte des Formulars in dieser Reihenfolge
GRUPPEN = (
    "Sportstätte",
    "Adresse und Lage",
    "Nutzung",
    "Sportarten",
    "Organisationen",
    "Gebäude und Energie",
    "Kosten",
)
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


def _field(titel: str, beschreibung: str | None = None, pflicht: bool = False, **angaben):
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
        werte = {name: getattr(self, name) for name in type(self).model_fields}
        if fehler := zwischen_feldern(type(self), werte):
            raise ValueError("; ".join(m for _, _, m in fehler))
        return self


def _leer(w) -> bool:
    return w in (None, "", [], {})


def zwischen_feldern(modell: type[BaseModel], werte: dict) -> list[tuple[str, str, str]]:
    """Regeln zwischen Feldern (Angaben braucht, nachkommastellen, teil_von) für die Werte eines
    Objekts → [(Regel, Feld, Meldung)]. Dieselbe Rechnung wie regelFunde in grundlagen.js."""
    felder = modell.model_fields
    out = []
    for name, feld in felder.items():
        extra = feld.json_schema_extra or {}
        wert = werte.get(name)
        if extra.get("braucht") and not _leer(wert) and _leer(werte.get(extra["braucht"])):
            m = MELDUNGEN["braucht"].format(feld=extra["braucht"], wenn=feld.title)
            out.append(("braucht", extra["braucht"], m))
        n = extra.get("nachkommastellen")
        zahl = isinstance(wert, (int, float)) and not isinstance(wert, bool)
        if n and zahl and len(repr(wert).partition(".")[2]) < n:  # 50.35: nur auf ~1 km genau
            m = MELDUNGEN["nachkommastellen"].format(feld=name, n=n, wert=wert)
            out.append(("nachkommastellen", name, m))
        if extra.get("teil_von") and isinstance(wert, list) and wert:
            alle = werte.get(extra["teil_von"]) or []
            if fehlt := [w for w in wert if w not in alle]:
                m = MELDUNGEN["teil_von"].format(
                    feld=name,
                    fehlt=", ".join(map(str, fehlt)),
                    unter=felder[extra["teil_von"]].title,
                )
                out.append(("teil_von", name, m))
    return out


# --- Datenbestand -----------------------------------------------------------------------


class Adresse(Basis):
    strasse: str | None = _field("Straße", max_length=150)
    hausnummer: str | None = _field(
        "Hausnummer",
        "z. B. 12, 12a oder 2-4",
        max_length=12,
        pattern=r"^\d+\s?[a-zA-Z]?(\s?[-/]\s?\d+\s?[a-zA-Z]?)?$",
    )
    adresszusatz: str | None = _field(
        "Adresszusatz",
        "z. B. Eingang Schulhof",
        max_length=150,
        uebersicht=False,
    )
    plz: str | None = _field("PLZ", "fünf Ziffern", pattern=r"^\d{5}$")
    ort: str | None = _field("Ort", max_length=100, widget="ort")


class Lage(Basis):
    """Immer WGS84 (EPSG:4326), Grad mit Dezimalstellen."""

    lon: float = _field("Längengrad", "WGS84", pflicht=True, ge=5.8, le=9.0, nachkommastellen=4)
    lat: float = _field("Breitengrad", "WGS84", pflicht=True, ge=48.8, le=51.1, nachkommastellen=4)


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
    (("Tennisplatz",), ("bodenbelag", "bewaesserung", "felder_je_belag")),
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
            "kinderbecken",
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


def _general(titel, beschreibung=None, gruppe="Allgemein", **angaben):
    return _field(titel, beschreibung, gruppe=gruppe, **angaben)


def _yesno(titel, beschreibung=None, gruppe="Ausstattung", **angaben):
    return _general(titel, beschreibung, gruppe, widget="ja_nein", **angaben)


def _numeric(titel, beschreibung=None, gruppe="Maße", **angaben):
    return _general(titel, beschreibung, gruppe, ge=0, **angaben)


class Energietraeger(Basis):
    """Ein Energieträger einer Sportstätte, z. B. Erdgas für die Heizung."""

    bereich: Energiebereich | None = _field("Bereich", "Heizung, Warmwasser oder Strom")
    art: Energietraegerart = _field("Art", pflicht=True)
    einbaujahr: int | None = _field("Einbaujahr", ge=1800, le=2100, widget="jahr")
    beschreibung: str | None = _field("Beschreibung", max_length=500)


class Verbrauch(Basis):
    """Ein Jahresverbrauch einer Sportstätte (Menge und Einheit)."""

    art: Verbrauchsart = _field("Art", pflicht=True)
    menge: float = _field("Menge", pflicht=True, ge=0)
    einheit: Einheit | None = _field("Einheit")
    jahr: int | None = _field("Jahr", ge=1990, le=2100, widget="jahr")


class Sanierung(Basis):
    """Eine Sanierung (Sportstätte oder Sportanlage)."""

    jahr: int | None = _field("Jahr", ge=1800, le=2100, widget="jahr")
    kosten: float | None = _field("Kosten", ge=0, braucht="waehrung")
    waehrung: Waehrung | None = _field("Währung")
    beschreibung: str | None = _field("Beschreibung", max_length=1000)


class Foerderung(Basis):
    """Eine Förderung (Sportstätte oder Sportanlage)."""

    programm: str | None = _field("Programm", max_length=300)
    jahr: int | None = _field("Jahr", ge=1800, le=2100, widget="jahr")
    hoehe: float | None = _field("Höhe", ge=0, braucht="waehrung")
    waehrung: Waehrung | None = _field("Währung")


class Sportanlage(Basis):
    """Eine Einheit einer Sportstätte, z. B. ein Großspielfeld, eine Halle oder ein Becken.
    Zu welcher Sportstätte sie gehört, sagt der Ordner, in dem ihre Datei liegt."""

    model_config = ConfigDict(
        json_schema_extra={
            "gruppen": list(ANLAGE_GRUPPEN),
            "examples": [
                {
                    "id": "17abb3c4-7493-5549-a6ca-f432ef00fba3",
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

    id: str | None = _field(
        "ID",
        "UUID, zugleich der Dateiname (in der Datei Pflicht)",
        formular=False,
        uebersicht=False,
    )
    # Sportanlage
    typ: str = _general(
        "Typ",
        "einheitlicher Typ aus src/sportstaettenatlas/anlagen.py, z. B. „Großspielfeld“",
        pflicht=True,
        min_length=1,
        max_length=100,
        widget="anlagentyp",
        uebersicht=False,
    )
    bezeichnung: str | None = _general(
        "Name",
        "eigener Name der Anlage, z. B. „Halle 1“, „Kunstrasen B“",
        max_length=100,
    )
    betriebsstatus: Betriebsstatus | None = _general("Betriebsstatus")
    baujahr: int | None = _general("Baujahr", ge=1800, le=2100, widget="jahr")
    letzte_sanierung: int | None = _general(
        "Letzte Sanierung", "Jahr", ge=1800, le=2100, widget="jahr"
    )
    # Sportarten
    sportarten: list[str] = _general("Sportarten", gruppe="Sportarten", default_factory=list)
    wettkampf: list[str] = _general(
        "Wettkampfeignung",
        "Sportarten, für die die Anlage wettkampfgeeignet ist (müssen unter Sportarten stehen)",
        gruppe="Sportarten",
        default_factory=list,
        teil_von="sportarten",
    )
    # Maße
    laenge: float | None = _numeric("Länge", "der Sportfläche", einheit="m")
    breite: float | None = _numeric("Breite", "der Sportfläche", einheit="m")
    hoehe: float | None = _numeric("Höhe", "lichte Höhe der Halle", einheit="m")
    flaeche: float | None = _numeric(
        "Fläche",
        "nutzbare Sportfläche, wenn nicht Länge × Breite (z. B. Reitplatz)",
        einheit="m²",
    )
    bahnlaenge: float | None = _numeric("Bahnlänge", einheit="m")
    bahnen: int | None = _numeric("Bahnen", "Zahl der Lauf-, Schwimm-, Kegel- oder Schießbahnen")
    # Belag und Felder
    bodenbelag: Bodenbelag | None = _general("Bodenbelag", gruppe="Belag und Felder")
    felder_je_belag: dict[Bodenbelag, Anzahl] = _general(
        "Felder je Belag",
        "z. B. Tennisplätze: 3 Sand, 1 Kunstrasen",
        gruppe="Belag und Felder",
        default_factory=dict,
        widget="zaehler",
    )
    spielfelder: int | None = _numeric(
        "Spielfelder",
        "Zahl, wenn nicht nach Sportart bekannt",
        gruppe="Belag und Felder",
    )
    felder_je_sportart: dict[Spielfeldart, Anzahl] = _general(
        "Spielfelder je Sportart",
        "markierte Felder, z. B. 3 Badminton, 1 Handball",
        gruppe="Belag und Felder",
        default_factory=dict,
        widget="zaehler",
    )
    kleinfelder_je_sportart: dict[Kleinfeldart, Anzahl] = _general(
        "Kleinfelder je Sportart",
        gruppe="Belag und Felder",
        default_factory=dict,
        widget="zaehler",
    )
    loecher: int | None = _numeric("Löcher", "Golf, Bahnengolf", gruppe="Belag und Felder")
    # Becken
    wasserflaeche: float | None = _numeric("Wasserfläche", "gesamt", gruppe="Becken", einheit="m²")
    wasserflaeche_relevant: float | None = _numeric(
        "Relevante Wasserfläche",
        "ohne Kaltwassertret-, Warmsprudelbecken usw.",
        gruppe="Becken",
        einheit="m²",
    )
    wasserflaeche_lehrbecken: float | None = _numeric(
        "Wasserfläche Lern- und Kursbecken",
        gruppe="Becken",
        einheit="m²",
    )
    becken_bis_25m: int | None = _numeric("Becken bis 25 m", gruppe="Becken")
    becken_25_bis_50m: int | None = _numeric("Becken 25 bis 50 m", gruppe="Becken")
    becken_ueber_50m: int | None = _numeric("Becken über 50 m", gruppe="Becken")
    becken_tiefer_3m: int | None = _numeric("Becken tiefer als 3 m", gruppe="Becken")
    nichtschwimmerbecken: int | None = _numeric("Nichtschwimmerbecken", gruppe="Becken")
    lehrbecken: int | None = _numeric("Lehrbecken", gruppe="Becken")
    kinderbecken: int | None = _numeric("Kinderbecken", gruppe="Becken")
    erholungsbecken: int | None = _numeric("Erholungsbecken", gruppe="Becken")
    sprungturm: JaNein | None = _yesno("Sprungturm", "mindestens einer", gruppe="Becken")
    sprungtuerme_3m: int | None = _numeric("Sprungtürme 3 m", gruppe="Becken")
    sprungtuerme_5m: int | None = _numeric("Sprungtürme 5 m", gruppe="Becken")
    sprungtuerme_10m: int | None = _numeric("Sprungtürme 10 m", gruppe="Becken")
    baederleben_id: str | None = _general(
        "ID bei baederleben.de",
        gruppe="Becken",
        max_length=50,
        uebersicht=False,
    )
    # Ausstattung
    trennvorhang: JaNein | None = _yesno("Trennvorhang", "zur Hallenteilung oder für eine Bühne")
    bewaesserung: JaNein | None = _yesno("Bewässerung")
    hoehenverstellbares_netz: JaNein | None = _yesno("Höhenverstellbares Netz")
    kletterwand: JaNein | None = _yesno("Kletterwand")
    boulderwand: JaNein | None = _yesno("Boulderwand")
    dressurplatz: JaNein | None = _yesno("Dressurplatz")
    springplatz: JaNein | None = _yesno("Springplatz")
    schiessstaende_gedeckt: int | None = _numeric("Schießstände gedeckt", gruppe="Ausstattung")
    schiessstaende_teilgedeckt: int | None = _numeric(
        "Schießstände teilgedeckt", gruppe="Ausstattung"
    )
    schiessstaende_offen: int | None = _numeric("Schießstände offen", gruppe="Ausstattung")
    lifte: int | None = _numeric("Lifte", gruppe="Ausstattung")
    spielgeraete: int | None = _numeric("Spielgeräte", gruppe="Ausstattung")
    ausstattung: list[str] = _general(
        "Weitere Ausstattung",
        "z. B. Umkleiden, Anzeigetafel",
        gruppe="Ausstattung",
        default_factory=list,
    )
    # Licht
    flutlicht: JaNein | None = _yesno("Flutlicht", gruppe="Licht")
    leuchtmittel: Leuchtmittel | None = _general("Leuchtmittel", gruppe="Licht")
    lux: Luxwert | None = _general("Beleuchtungsstärke", gruppe="Licht", einheit="lx")
    # Nutzung
    oeffnungsstunden: int | None = _numeric(
        "Öffnungsstunden",
        "im Jahr, insgesamt",
        gruppe="Nutzung",
        le=8784,
        einheit="h",
    )
    oeffnungsstunden_schule: int | None = _numeric(
        "davon Schulsport",
        "Stunden im Jahr",
        gruppe="Nutzung",
        le=8784,
        einheit="h",
    )
    oeffnungsstunden_verein: int | None = _numeric(
        "davon Vereine",
        "Stunden im Jahr",
        gruppe="Nutzung",
        le=8784,
        einheit="h",
    )
    altersempfehlung: str | None = _general(
        "Altersempfehlung",
        "z. B. 6–12 Jahre",
        gruppe="Nutzung",
        max_length=50,
    )
    # Barrierefreiheit
    barrierefrei_erreichbar: JaNein | None = _yesno(
        "Barrierefrei erreichbar", gruppe="Barrierefreiheit"
    )
    geeignet_mobilitaet: JaNein | None = _yesno(
        "Geeignet bei eingeschränkter Mobilität",
        gruppe="Barrierefreiheit",
    )
    geeignet_sehen: JaNein | None = _yesno(
        "Geeignet bei Sehbeeinträchtigung", gruppe="Barrierefreiheit"
    )
    geeignet_kleinwuchs: JaNein | None = _yesno(
        "Geeignet für Kleinwüchsige", gruppe="Barrierefreiheit"
    )
    geeignet_mental: JaNein | None = _yesno(
        "Geeignet bei geistiger Beeinträchtigung",
        gruppe="Barrierefreiheit",
    )
    # Kosten
    baukosten: float | None = _numeric(
        "Baukosten",
        "damalige Kosten",
        gruppe="Kosten",
        braucht="waehrung",
        einheit_aus="waehrung",
    )
    waehrung: Waehrung | None = _general(
        "Währung", "der Baukosten", gruppe="Kosten", uebersicht=False
    )
    sanierungen: list[Sanierung] = _general(
        "Sanierungen", gruppe="Kosten", default_factory=list, formular=False
    )
    foerderungen: list[Foerderung] = _general(
        "Förderungen", gruppe="Kosten", default_factory=list, formular=False
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
                    "lage": {"lon": 7.5938, "lat": 50.3512},
                    "betreiber": "TuS Musterdorf e.V.",
                    "betreiber_typ": "Sportverein im LSB RLP",
                    "sportarten": ["Fußball", "Leichtathletik"],
                }
            ],
        }
    )

    id: str | None = _field(
        "ID",
        "UUID, zugleich Name des Ordners (in der Datei Pflicht)",
        formular=False,
        uebersicht=False,
    )
    name: str = _field(
        "Name",
        pflicht=True,
        min_length=1,
        max_length=200,
        gruppe="Sportstätte",
    )
    kategorie: Kategorie = _field("Sportstättenkategorie", pflicht=True, gruppe="Sportstätte")
    adresse: Adresse = _field("Adresse", default_factory=Adresse, gruppe="Adresse und Lage")
    lage: Lage = _field(
        "Lage",
        "bestimmt Kreis und Gemeinde",
        pflicht=True,
        gruppe="Adresse und Lage",
        widget="karte",
        uebersicht=False,
    )
    entfernung_oepnv: int | None = _field(
        "Entfernung zum ÖPNV",
        "zur nächsten Haltestelle",
        ge=0,
        le=100_000,
        gruppe="Adresse und Lage",
        einheit="m",
    )
    oeffentlicher_zugang: JaNein | None = _field(
        "Öffentlicher Zugang",
        gruppe="Nutzung",
        widget="ja_nein",
    )
    schulsport: JaNein | None = _field("Schulsport", gruppe="Nutzung", widget="ja_nein")
    wlan: JaNein | None = _field("WLAN", gruppe="Nutzung", widget="ja_nein")
    zuschauerplaetze: int | None = _field("Zuschauerplätze", ge=0, le=100_000, gruppe="Nutzung")
    betriebsstatus: Betriebsstatus | None = _field("Betriebsstatus", gruppe="Sportstätte")
    sportkomplex: str | None = _field(
        "Sportkomplex",
        "ID eines Sportkomplexes (daten/<LAND>/<Kreis>/sportkomplexe/), nur wenn mehrere "
        "Sportstätten an einem Ort zusammengehören",
        pattern=UUID_MUSTER,
        gruppe="Sportstätte",
        widget="sportkomplex",
    )
    eigentuemer: str | None = _field(
        "Eigentümer",
        "Name einer Organisation (Verzeichnis daten/organisationen/), keine Personen",
        max_length=200,
        gruppe="Organisationen",
        widget="organisation",
    )
    eigentuemer_typ: Organisationstyp | None = _field(
        "Art des Eigentümers",
        gruppe="Organisationen",
        braucht="eigentuemer",
    )
    betreiber: str | None = _field(
        "Betreiber",
        "Name einer Organisation (Verzeichnis daten/organisationen/), keine Personen",
        max_length=200,
        gruppe="Organisationen",
        widget="organisation",
    )
    betreiber_typ: Organisationstyp | None = _field(
        "Art des Betreibers",
        gruppe="Organisationen",
        braucht="betreiber",
    )
    website: str | None = _field(
        "Webseite",
        "vollständige Adresse mit https://",
        pattern=r"^https?://\S+\.\S+$",
        gruppe="Organisationen",
        widget="url",
    )
    nutzer: list[str] = _field(
        "Nutzer",
        "Vereine und andere Organisationen, die die Sportstätte nutzen (Verzeichnis "
        "daten/organisationen/)",
        default_factory=list,
        gruppe="Organisationen",
        widget="organisationen",
    )
    sportarten: list[str] = _field(
        "Sportarten", default_factory=list, gruppe="Sportarten", widget="chips"
    )
    wettkampfanlage: Wettkampfanlage | None = _field("Wettkampfanlage", gruppe="Sportarten")
    baujahr: int | None = _field(
        "Baujahr",
        "des Gebäudes bzw. Geländes",
        ge=1800,
        le=2100,
        gruppe="Gebäude und Energie",
        widget="jahr",
    )
    letzte_sanierung: int | None = _field(
        "Letzte Sanierung", "Jahr", ge=1800, le=2100, gruppe="Gebäude und Energie", widget="jahr"
    )
    fassadenmaterial: Fassade | None = _field("Fassadenmaterial", gruppe="Gebäude und Energie")
    funktionsraeume: dict[Funktionsraum, Anzahl] = _field(
        "Funktionsräume",
        "Anzahl je Art, z. B. 4 Umkleiden",
        default_factory=dict,
        gruppe="Gebäude und Energie",
        widget="zaehler",
        formular=False,
    )
    energietraeger: list[Energietraeger] = _field(
        "Energieträger", default_factory=list, gruppe="Gebäude und Energie", formular=False
    )
    verbraeuche: list[Verbrauch] = _field(
        "Jahresverbräuche", default_factory=list, gruppe="Gebäude und Energie", formular=False
    )
    sanierungen: list[Sanierung] = _field(
        "Sanierungen", default_factory=list, gruppe="Kosten", formular=False
    )
    foerderungen: list[Foerderung] = _field(
        "Förderungen", default_factory=list, gruppe="Kosten", formular=False
    )
    anlagen: list[Sportanlage] = _field(
        "Sportanlagen",
        "stehen als eigene Dateien im Ordner der Sportstätte, nicht in `<id>_meta.json`",
        default_factory=list,
        formular=False,
        datei=False,
        gruppe="Sportstätte",
    )


class Sportkomplex(Basis):
    """Optionale Klammer um mehrere Sportstätten an einem Ort, z. B. ein Sportzentrum mit
    Halle, Stadion und Freibad (daten/<LAND>/<Kreis>/sportkomplexe/<id>.json). Die
    Sportstätten verweisen in `sportkomplex` auf ihn; Eigentümer, Betreiber und Anlagen
    stehen weiter bei den Sportstätten. Nur anlegen, wenn mindestens zwei Sportstätten
    dazugehören."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "b1f3e6a2-4c8d-4e1f-9a7b-2d5c0e8f1a36",
                    "name": "Sportzentrum Musterdorf",
                    "adresse": {"strasse": "Am Weg", "plz": "56068", "ort": "Koblenz"},
                    "lage": {"lon": 7.5941, "lat": 50.3515},
                }
            ]
        }
    )

    id: str | None = _field(
        "ID",
        "UUID, zugleich der Dateiname (in der Datei Pflicht)",
        formular=False,
        uebersicht=False,
    )
    name: str = _field("Name", pflicht=True, min_length=1, max_length=200)
    adresse: Adresse = _field("Adresse", default_factory=Adresse)
    lage: Lage | None = _field(
        "Lage",
        "Mittelpunkt; ohne Lage bestimmen die Sportstätten den Kreis-Ordner",
        uebersicht=False,
    )


class Stuetzpunkt(Basis):
    """Anerkennung als Stützpunkt des Leistungssports (Olympia-, Bundes-, Landesstützpunkt,
    Landesleistungszentrum) für Sportarten an einer oder mehreren Sportstätten
    (daten/stuetzpunkte/<id>.json). Eine Sportstätte kann zu mehreren Stützpunkten gehören.
    Statt einzelner Sportstätten kann ein Sportkomplex stehen, wenn alle seine Sportstätten
    dazugehören."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "c4d2a7e1-5b3f-4a9c-8e6d-1f0b2c3d4e5f",
                    "name": "Bundesstützpunkt Leichtathletik Musterdorf",
                    "art": "Bundesstützpunkt",
                    "sportarten": ["Leichtathletik"],
                    "traeger": "TuS Musterdorf e.V.",
                    "anerkannt_von": "BMI und DOSB",
                    "gueltig_ab": "2025-01-01",
                    "gueltig_bis": "2028-12-31",
                    "quelle": "https://www.example.org/bundesstuetzpunkte",
                    "sportstaetten": ["9c24bfa6-3d2e-4b8f-a1c7-5e6f7a8b9c0d"],
                }
            ]
        }
    )

    id: str | None = _field(
        "ID",
        "UUID, zugleich der Dateiname (in der Datei Pflicht)",
        formular=False,
        uebersicht=False,
    )
    name: str = _field("Name", pflicht=True, min_length=1, max_length=200)
    art: Stuetzpunktart = _field("Art", pflicht=True)
    sportarten: list[str] = _field("Sportarten", default_factory=list, widget="chips")
    traeger: str | None = _field(
        "Träger",
        "Name einer Organisation (Verzeichnis daten/organisationen/)",
        max_length=200,
        widget="organisation",
    )
    anerkannt_von: str | None = _field(
        "Anerkannt von", "z. B. BMI und DOSB, MdI und LSB", max_length=200
    )
    gueltig_ab: date | None = _field("Gültig ab")
    gueltig_bis: date | None = _field("Gültig bis", "Ende der Anerkennung")
    quelle: str | None = _field(
        "Quelle",
        "Veröffentlichung der Anerkennung, vollständige Adresse mit https://",
        pattern=r"^https?://\S+\.\S+$",
        widget="url",
    )
    sportstaetten: list[str] = _field(
        "Sportstätten", "IDs der Sportstätten", default_factory=list, formular=False
    )
    sportkomplexe: list[str] = _field(
        "Sportkomplexe",
        "IDs von Sportkomplexen, deren Sportstätten alle dazugehören",
        default_factory=list,
        formular=False,
    )


class Organisation(Basis):
    """Verein, Kommune, Verband, Unternehmen … als Eigentümer, Betreiber oder Nutzer von
    Sportstätten (daten/organisationen/<LAND>/<Ordner der Art>/<id>.json). Sportstätten nennen sie in
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

    id: str | None = _field(
        "ID",
        "UUID, zugleich der Dateiname (in der Datei Pflicht)",
        formular=False,
        uebersicht=False,
    )
    name: str = _field(
        "Name",
        "wie er bei den Sportstätten steht",
        pflicht=True,
        min_length=1,
        max_length=200,
    )
    typ: Organisationstyp | None = _field(
        "Art", "bestimmt auch den Ordner in daten/organisationen/"
    )
    ars: str | None = _field(
        "Regionalschlüssel",
        "amtlicher Schlüssel einer Gebietskörperschaft: Kreis 5, Verbandsgemeinde 9, "
        "Gemeinde 12 Stellen",
        pattern=r"^\d{5}(\d{4}(\d{3})?)?$",
        formular=False,
    )
    website: str | None = _field(
        "Webseite",
        "vollständige Adresse mit https://",
        pattern=r"^https?://\S+\.\S+$",
        widget="url",
    )
    lsb_nummer: str | None = _field(
        "Vereinsnummer im LSB", "siebenstellig", pattern=r"^\d{7}$", formular=False
    )
    uebergeordnet: str | None = _field(
        "Übergeordnet",
        "Name der übergeordneten Organisation, z. B. des Verbands",
        max_length=200,
        widget="organisation",
    )
    weitere_namen: list[str] = _field(
        "Weitere Schreibweisen",
        "andere Namen, unter denen Sportstätten sie nennen",
        default_factory=list,
    )


# --- Vorschlag (Formular → LimeSurvey) ------------------------------------------------


class NeueSportstaette(Basis):
    """Eine neue Sportstätte innerhalb eines Vorschlags für einen Sportkomplex oder Stützpunkt;
    dessen Liste der Sportstätten nennt sie mit `ref`, die ID vergibt erst die Übernahme."""

    ref: str = _field("Verweis", "im Vorschlag, z. B. neu-1", pflicht=True, pattern=r"^neu-\d+$")
    sportstaette: Sportstaette = _field("Angaben der Sportstätte", pflicht=True)
    anlagen: list[Sportanlage] = _field("Sportanlagen", default_factory=list)


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

    version: Literal[1] = _field("Version des Formats", default=1)
    art: Literal["neu", "aenderung", "anlagen", "organisation", "sportkomplex", "stuetzpunkt"] = (
        _field(
            "Art",
            "neu: neue Sportstätte mit Anlagen; aenderung: Angaben einer Sportstätte und, wenn "
            "angegeben, ihre Sportanlagen; anlagen: nur Sportanlagen einer Sportstätte; organisation: Organisation anlegen, "
            "ändern oder löschen; sportkomplex: Sportkomplex anlegen, ändern oder auflösen; "
            "stuetzpunkt: Stützpunkt anlegen, ändern oder löschen",
            pflicht=True,
        )
    )
    sportstaette_id: str | None = _field("Sportstätte", "ID der geänderten Sportstätte")
    sportstaette: Sportstaette | None = _field(
        "Angaben der Sportstätte", "vollständig, nach der Änderung (bei neu und aenderung)"
    )
    anlagen: list[Sportanlage] | None = _field(
        "Sportanlagen",
        "bei neu alle Anlagen; bei aenderung und anlagen die geänderten (vorhandene mit ihrer "
        "Kurz-ID, dem Anfang der UUID) und neuen (ohne ID)",
    )
    entfernte_anlagen: list[str] = _field(
        "Entfernte Sportanlagen", "Kurz-IDs", default_factory=list
    )
    organisation_id: str | None = _field(
        "Organisation", "ID der geänderten oder gelöschten Organisation (fehlt bei einer neuen)"
    )
    organisation: Organisation | None = _field(
        "Angaben der Organisation", "vollständig, nach der Änderung (nicht beim Löschen)"
    )
    sportkomplex_id: str | None = _field(
        "Sportkomplex", "ID des geänderten oder aufgelösten Sportkomplexes (fehlt bei einem neuen)"
    )
    sportkomplex: Sportkomplex | None = _field(
        "Angaben des Sportkomplexes", "vollständig, nach der Änderung (nicht beim Auflösen)"
    )
    sportstaetten: list[str] = _field(
        "Sportstätten des Sportkomplexes",
        "IDs aller Sportstätten nach der Änderung (mindestens zwei)",
        default_factory=list,
    )
    stuetzpunkt_id: str | None = _field(
        "Stützpunkt", "ID des geänderten oder gelöschten Stützpunkts (fehlt bei einem neuen)"
    )
    stuetzpunkt: Stuetzpunkt | None = _field(
        "Angaben des Stützpunkts",
        "vollständig, nach der Änderung, mit Sportstätten und Sportkomplexen",
    )
    loeschen: bool = _field(
        "Löschen",
        "die Organisation aus dem Verzeichnis entfernen, den Sportkomplex auflösen bzw. den "
        "Stützpunkt löschen",
        default=False,
    )
    neue_organisationen: list[Organisation] = _field(
        "Neue Organisationen",
        "trägt der Vorschlag mit ein, z. B. den Betreiber einer neuen Sportstätte (jede Art); "
        "steht der Name schon im Verzeichnis, gibt es nur eine Warnung",
        default_factory=list,
    )
    neue_sportstaetten: list[NeueSportstaette] = _field(
        "Neue Sportstätten",
        "bei sportkomplex und stuetzpunkt: neue Sportstätten mit ihren Anlagen; `sportstaetten` "
        "bzw. `stuetzpunkt.sportstaetten` nennen sie mit ihrem `ref`",
        default_factory=list,
    )
    neuer_sportkomplex: Sportkomplex | None = _field(
        "Neuer Sportkomplex",
        "bei neu und aenderung: neuer Sportkomplex der Sportstätte; weitere vorhandene "
        "Sportstätten des Komplexes in `sportstaetten`",
    )
    geaendert: list[str] = _field("Geänderte Felder", default_factory=list)
    gemeinde: str | None = _field("Gemeinde", "Regionalschlüssel der Gemeinde an der Lage")
    dubletten_geprueft: list[str] = _field(
        "Geprüfte Doppelungen",
        "IDs ähnlicher Sportstätten, die als verschieden bestätigt wurden",
        default_factory=list,
    )

    @model_validator(mode="after")
    def _passt_zur_art(self):
        refs = [n.ref for n in self.neue_sportstaetten]
        if refs and self.art not in ("sportkomplex", "stuetzpunkt"):
            raise ValueError(f"{self.art}: neue_sportstaetten nur bei sportkomplex und stuetzpunkt")
        if len(set(refs)) != len(refs):
            raise ValueError("neue_sportstaetten: ref doppelt")
        genannt = set(self.sportstaetten) | set(
            self.stuetzpunkt.sportstaetten if self.stuetzpunkt else []
        )
        if fehlt := [r for r in refs if r not in genannt]:
            raise ValueError(f"neue_sportstaetten: {', '.join(fehlt)} gehört nirgends dazu")
        if self.neuer_sportkomplex is not None and self.art not in ("neu", "aenderung"):
            raise ValueError(f"{self.art}: neuer_sportkomplex nur bei neu und aenderung")
        if self.art == "neu" and (self.sportstaette is None or self.anlagen is None):
            raise ValueError("neu: sportstaette und anlagen nötig")
        if self.art == "stuetzpunkt":
            if self.loeschen and not self.stuetzpunkt_id:
                raise ValueError("stuetzpunkt: zum Löschen stuetzpunkt_id nötig")
            if not self.loeschen and self.stuetzpunkt is None:
                raise ValueError("stuetzpunkt: stuetzpunkt nötig")
            if not self.loeschen and not (
                self.stuetzpunkt.sportstaetten or self.stuetzpunkt.sportkomplexe
            ):
                raise ValueError(
                    "stuetzpunkt: mindestens eine Sportstätte oder ein Sportkomplex nötig"
                )
            return self
        if self.art == "sportkomplex":
            if self.loeschen and not self.sportkomplex_id:
                raise ValueError("sportkomplex: zum Auflösen sportkomplex_id nötig")
            if not self.loeschen and self.sportkomplex is None:
                raise ValueError("sportkomplex: sportkomplex nötig")
            if not self.loeschen and len(set(self.sportstaetten)) < 2:
                raise ValueError("sportkomplex: mindestens zwei Sportstätten nötig")
            return self
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


MODELLE = (
    Sportstaette,
    Sportanlage,
    Adresse,
    Lage,
    Energietraeger,
    Verbrauch,
    Sanierung,
    Foerderung,
    Sportkomplex,
    Stuetzpunkt,
    Organisation,
    NeueSportstaette,
    Vorschlag,
)


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


def ordne(d: dict, modell: type[BaseModel]) -> dict:
    """Schlüssel in der Reihenfolge des Modells; unbekannte bleiben, hinten angehängt."""
    out = {k: d[k] for k in modell.model_fields if k in d}
    out.update({k: v for k, v in d.items() if k not in out})
    for feld, unter in (("adresse", Adresse), ("lage", Lage)):
        if modell in (Sportstaette, Sportkomplex) and isinstance(out.get(feld), dict):
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
        "pruefung": PRUEFUNG,
        "meldungen": MELDUNGEN,
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
        ("nachkommastellen", "mindestens {} Nachkommastellen"),
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
        "| Feld | Bezeichnung | Typ | Pflicht | Regeln | Beschreibung |",
        "|---|---|---|---|---|---|",
    ]
    for name, p in s["properties"].items():
        zeilen.append(
            f"| `{name}` | {modell.model_fields[name].title or ''} | {_typ_text(p)} | "
            f"{'ja' if name in pflicht else ''} | {_regeln_text(p)} | "
            f"{(p.get('description') or '').replace('|', '/')} |"
        )
    return "\n".join(zeilen)


def readme_block() -> str:
    """Teil von daten/README.md, der aus dem Modell erzeugt wird."""
    teile = [ANFANG, "", "![Datenmodell](datenmodell.svg)", ""]
    for modell, ueberschrift in (
        (Sportstaette, "Sportstätte (`<id>_meta.json`)"),
        (Adresse, "Adresse"),
        (Lage, "Lage"),
        (Energietraeger, "Energieträger"),
        (Verbrauch, "Jahresverbrauch"),
        (Sanierung, "Sanierung"),
        (Foerderung, "Förderung"),
        (Sportanlage, "Sportanlage (`<anlage-id>.json`)"),
        (Sportkomplex, "Sportkomplex (`<Kreis>/sportkomplexe/<id>.json`)"),
        (Stuetzpunkt, "Stützpunkt (`stuetzpunkte/<id>.json`)"),
        (Organisation, "Organisation (`organisationen/<LAND>/<Art>/<id>.json`)"),
        (Vorschlag, "Vorschlag (Formular → LimeSurvey, Frage `data`)"),
        (NeueSportstaette, "Neue Sportstätte im Vorschlag"),
    ):
        teile += [f"### {ueberschrift}", ""]
        if modell.__doc__:
            teile += [inspect.cleandoc(modell.__doc__), ""]  # ohne Einrückung: sonst Code-Block
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
    """Diagramm mit erdantic (braucht Graphviz). False, wenn erdantic fehlt. Felder der
    Sportanlage, die nur zu bestimmten Anlagentypen gehören, tragen „· nur …“ hinter ihrem Typ."""
    try:
        import erdantic as erd
    except ImportError:
        return False
    diagramm = erd.create(Vorschlag)
    try:  # bei der Sportanlage: hinter dem Typ eines Feldes, für welche Anlagentypen es ist
        for m in diagramm.models.values():
            if m.name == "Sportanlage":
                for name, f in m.fields.items():
                    if typen := fuer_von(name):
                        f.type_name = f"{f.type_name} · nur {nur_fuer(typen)}"
    except (AttributeError, TypeError):  # andere Version von erdantic: ohne diese Angabe
        pass
    diagramm.draw(out=ziel)
    return True


def nur_fuer(typen: list[str], hoechstens: int = 48) -> str:
    """fuer_text, gekürzt für das Diagramm (die volle Liste steht in daten/README.md)."""
    text = fuer_text(typen)
    if len(text) <= hoechstens:
        return text
    return f"{len(typen)} Typen: " + text[: hoechstens - 1].rsplit(", ", 1)[0] + " …"


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
