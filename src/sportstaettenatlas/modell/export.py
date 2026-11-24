"""Schema des Datenmodells für die Webseite (docs/daten/schema.json): Felder, Auswahllisten,
Angaben fürs Formular, Grenzwerte der Prüfungen (PRUEFUNG) und Meldungen (MELDUNGEN)."""

from __future__ import annotations

from pydantic.json_schema import models_json_schema

from .klassen import EMAIL_MUSTER, MELDUNGEN, MODELLE, ORGANISATIONSTYPEN, PRUEFUNG, fuer_von


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
    s["description"] = "Datenmodell des Sportstättenatlas (aus src/sportstaettenatlas/modell/)"
    return s
