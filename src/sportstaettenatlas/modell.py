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

Angaben je Feld für die Webseite (json_schema_extra, landen im Schema):
  gruppe      Abschnitt im Formular (Reihenfolge: GRUPPEN)
  widget      besondere Eingabe/Anzeige: ja_nein, karte, chips, organisation, ort, url,
              anlagentyp, jahr
  formular    False: nicht im Formular (IDs, Herkunft)
  uebersicht  False: zählt nicht zur Vollständigkeit in der Übersicht
  einheit     wird hinter Zahlen angezeigt (z. B. €)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic.json_schema import models_json_schema

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
Kategorie = Literal[KATEGORIEN]
Betriebsstatus = Literal[BETRIEBSSTATUS]
JaNein = Literal["ja", "nein"]

# Abschnitte des Formulars in dieser Reihenfolge
GRUPPEN = ("Sportstätte", "Adresse und Lage", "Nutzung", "Sportarten", "Eigentümer und Betreiber")


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
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --- Datenbestand -----------------------------------------------------------------------


class Adresse(Basis):
    strasse: str | None = _f("Straße", max_length=150)
    hausnummer: str | None = _f(
        "Hausnummer",
        "z. B. 12, 12a oder 2-4",
        max_length=12,
        pattern=r"^\d+\s?[a-zA-Z]?(\s?[-/]\s?\d+\s?[a-zA-Z]?)?$",
    )
    adresszusatz: str | None = _f(
        "Adresszusatz", "z. B. Eingang Schulhof", max_length=150, uebersicht=False
    )
    plz: str | None = _f("PLZ", "fünf Ziffern", pattern=r"^\d{5}$")
    ort: str | None = _f("Ort", max_length=100, widget="ort")


class Lage(Basis):
    lon: float = _f("Längengrad", "WGS84", pflicht=True, ge=5.8, le=9.0)
    lat: float = _f("Breitengrad", "WGS84", pflicht=True, ge=48.8, le=51.1)


class Sportanlage(Basis):
    """Eine Einheit einer Sportstätte, z. B. ein Großspielfeld, eine Halle oder ein Becken."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "17abb3c4-7493-5549-a6ca-f432ef00fba3",
                    "sportstaette_id": "9c24bfa6-71c1-4164-b226-061f0a139997",
                    "typ": "Großspielfeld",
                    "bezeichnung": "Kunstrasen B",
                    "sportarten": ["Fußball"],
                    "baujahr": 1998,
                    "baukosten_eur": 1200000,
                    "ausstattung": ["Flutlicht", "Beregnung"],
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
    sportstaette_id: str | None = _f(
        "Sportstätte",
        "ID der Sportstätte, zu der die Anlage gehört, = Name des Ordners (in der Datei Pflicht)",
        formular=False,
        uebersicht=False,
    )
    typ: str = _f(
        "Typ",
        "einheitlicher Typ aus src/sportstaettenatlas/anlagen.py, z. B. „Großspielfeld“",
        pflicht=True,
        min_length=1,
        max_length=100,
        widget="anlagentyp",
        uebersicht=False,
    )
    bezeichnung: str | None = _f(
        "Name", "eigener Name der Anlage, z. B. „Halle 1“, „Kunstrasen B“", max_length=100
    )
    sportarten: list[str] = _f("Sportarten", default_factory=list)
    baujahr: int | None = _f("Baujahr", ge=1800, le=2100, widget="jahr")
    baukosten_eur: int | None = _f("Baukosten", "in Euro", ge=0, einheit="€")
    ausstattung: list[str] = _f(
        "Ausstattung", "z. B. Flutlicht, Beregnung, Umkleiden", default_factory=list
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
    name: str = _f("Name", pflicht=True, min_length=1, max_length=200, gruppe="Sportstätte")
    kategorie: Kategorie = _f("Sportstättenkategorie", pflicht=True, gruppe="Sportstätte")
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
        "Öffentlicher Zugang", gruppe="Nutzung", widget="ja_nein"
    )
    schulsport: JaNein | None = _f("Schulsport", gruppe="Nutzung", widget="ja_nein")
    zuschauerplaetze: int | None = _f("Zuschauerplätze", ge=0, le=100_000, gruppe="Nutzung")
    betriebsstatus: Betriebsstatus | None = _f("Betriebsstatus", gruppe="Sportstätte")
    eigentuemer: str | None = _f(
        "Eigentümer",
        "Name einer Organisation, keine Personen",
        max_length=200,
        gruppe="Eigentümer und Betreiber",
        widget="organisation",
    )
    betreiber: str | None = _f(
        "Betreiber",
        "Name einer Organisation, keine Personen",
        max_length=200,
        gruppe="Eigentümer und Betreiber",
        widget="organisation",
    )
    website: str | None = _f(
        "Webseite",
        "vollständige Adresse mit https://",
        pattern=r"^https?://\S+\.\S+$",
        gruppe="Eigentümer und Betreiber",
        widget="url",
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


def ordne(d: dict, modell: type[BaseModel]) -> dict:
    """Schlüssel in der Reihenfolge des Modells; unbekannte bleiben, hinten angehängt."""
    out = {k: d[k] for k in modell.model_fields if k in d}
    out.update({k: v for k, v in d.items() if k not in out})
    for feld, unter in (("adresse", Adresse), ("lage", Lage)):
        if modell is Sportstaette and isinstance(out.get(feld), dict):
            out[feld] = ordne(out[feld], unter)
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
            feld = ".".join(str(x) for x in e["loc"]) or "(Datensatz)"
            if e["type"] == "value_error":
                out.append(f"{feld}: {(e.get('ctx') or {}).get('error', e['msg'])}")
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
                    "string": "Text",
                    "integer": "ganze Zahl",
                    "number": "Zahl",
                    "object": "Objekt",
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
    return "; ".join(out)


def felder_tabelle(modell: type[BaseModel]) -> str:
    s = modell.model_json_schema()
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
