"""Dokumentation aus dem Modell: Feldtabellen (daten/erzeugt/felder.md) und Diagramm
(daten/erzeugt/datenmodell.svg) – Befehl `modell`."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from pydantic import BaseModel

from . import anlagen
from .klassen import (
    AUSWAHL,
    MERKMALE,
    Adresse,
    Energietraeger,
    Foerderung,
    Lage,
    NeueSportstaette,
    Organisation,
    Sanierung,
    Sportanlage,
    Sportkomplex,
    Sportstaette,
    Stuetzpunkt,
    Verbrauch,
    Vorschlag,
    fuer_von,
)

ERZEUGT = "erzeugt"  # daten/erzeugt/: aus Code erzeugt, im Git (für alle ohne Installation)
DATENMODELL_MD = "datenmodell.md"
DIAGRAMM = "datenmodell.svg"
KOPF = (
    "<!-- erzeugt aus src/sportstaettenatlas/modell/ mit `uv run sportstaettenatlas modell` – "
    "nicht von Hand ändern -->"
)
# früher stand der erzeugte Teil in daten/README.md zwischen diesen Markierungen
ALT_ANFANG = "<!-- modell:anfang"
ALT_ENDE = "<!-- modell:ende -->"
VERWEIS = (
    "Alle Felder mit Typ und Regeln, die Felder je Anlagentyp, die Auswahllisten und das "
    f"Diagramm stehen in [{ERZEUGT}/{DATENMODELL_MD}]({ERZEUGT}/{DATENMODELL_MD}) – erzeugt aus "
    "dem Code mit `uv run sportstaettenatlas modell`."
)


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
    """Inhalt von daten/erzeugt/datenmodell.md: alle Felder, Felder je Anlagentyp,
    Auswahllisten, das Diagramm."""
    teile = [KOPF, "", "# Datenmodell", "", f"![Datenmodell]({DIAGRAMM})", ""]
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
    return "\n".join(teile)


def aktualisiere_readme(pfad: Path) -> bool:
    """daten/erzeugt/datenmodell.md neu schreiben (`pfad`); True, wenn sich etwas änderte."""
    text = pfad.read_text("utf-8") if pfad.exists() else ""
    neu = readme_block()
    if neu == text:
        return False
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(neu, "utf-8")
    return True


def alten_block_ersetzen(readme: Path) -> bool:
    """Steht in daten/README.md noch der früher erzeugte Teil, wird er durch einen Verweis auf
    daten/erzeugt/datenmodell.md ersetzt (einmalig). True, wenn sich etwas änderte."""
    if not readme.exists():
        return False
    text = readme.read_text("utf-8")
    if ALT_ANFANG not in text or ALT_ENDE not in text:
        return False
    a, e = text.index(ALT_ANFANG), text.index(ALT_ENDE) + len(ALT_ENDE)
    readme.write_text(text[:a] + VERWEIS + text[e:], "utf-8")
    return True


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
    """fuer_text, gekürzt für das Diagramm (die volle Liste steht in datenmodell.md)."""
    text = fuer_text(typen)
    if len(text) <= hoechstens:
        return text
    return f"{len(typen)} Typen: " + text[: hoechstens - 1].rsplit(", ", 1)[0] + " …"


def schreibe_doku(ordner: Path) -> list[str]:
    """daten/erzeugt/datenmodell.md und daten/erzeugt/datenmodell.svg aus dem Modell (`ordner`
    ist daten/). Liefert Hinweise."""
    hinweise = []
    ziel = ordner / ERZEUGT
    if aktualisiere_readme(ziel / DATENMODELL_MD):
        hinweise.append(f"{ziel}/{DATENMODELL_MD}: Datenmodell aktualisiert")
    if alten_block_ersetzen(ordner / "README.md"):
        hinweise.append(f"{ordner}/README.md: erzeugter Teil durch Verweis ersetzt")
    if zeichne(ziel / DIAGRAMM):
        hinweise.append(f"{ziel}/{DIAGRAMM} geschrieben")
    else:
        hinweise.append(
            "Diagramm nicht erzeugt: erdantic fehlt (sudo apt install graphviz graphviz-dev; "
            "uv sync --extra doku)"
        )
    return hinweise
