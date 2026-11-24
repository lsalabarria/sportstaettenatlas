"""Aufbau des Pakets: jeder Teil importiert nur, was unter ihm liegt.

    hilfen   ← alle
    modell   ← bestand ← pflege
                       ← analysen ← webseite (zeigt Ergebnisse der Analysen)
    cli.py (oben) darf alles

Pflege verändert daten/; Analysen und Webseite lesen nur – sie importieren nie aus pflege.
"""

import ast
from pathlib import Path

PAKET = Path(__file__).parents[1] / "src" / "sportstaettenatlas"
ERLAUBT = {
    "hilfen": set(),
    "modell": {"hilfen"},
    "bestand": {"hilfen", "modell"},
    "pflege": {"hilfen", "modell", "bestand"},
    "analysen": {"hilfen", "modell", "bestand"},
    "webseite": {"hilfen", "modell", "bestand", "analysen"},
}


def _teil(pfad: Path) -> str | None:
    teile = pfad.relative_to(PAKET).parts
    if len(teile) == 1:
        return "hilfen" if teile[0] == "hilfen.py" else None  # cli.py, __init__.py: alles
    return teile[0]


def _importe(pfad: Path):
    """Absolute Ziele aller Importe innerhalb des Pakets (auch die in Funktionen)."""
    modul = ["sportstaettenatlas", *pfad.relative_to(PAKET).with_suffix("").parts]
    if modul[-1] == "__init__":
        modul = modul[:-1]
    paket = modul if pfad.name == "__init__.py" else modul[:-1]
    for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
        if isinstance(knoten, ast.ImportFrom):
            if knoten.level:
                basis = paket[: len(paket) - knoten.level + 1]
                ziel = [*basis, *(knoten.module.split(".") if knoten.module else [])]
            elif knoten.module and knoten.module.startswith("sportstaettenatlas"):
                ziel = knoten.module.split(".")
            else:
                continue
            if len(ziel) == 1:  # from sportstaettenatlas import modell, …
                for n in knoten.names:
                    yield n.name, knoten.lineno
            else:
                yield ziel[1], knoten.lineno
        elif isinstance(knoten, ast.Import):
            for n in knoten.names:
                if n.name.startswith("sportstaettenatlas."):
                    yield n.name.split(".")[1], knoten.lineno


def test_teile_importieren_nur_nach_unten():
    verstoesse = []
    for pfad in sorted(PAKET.rglob("*.py")):
        teil = _teil(pfad)
        if teil is None:
            continue
        for ziel, zeile in _importe(pfad):
            ziel = ziel.removesuffix(".py")
            if ziel != teil and ziel in ERLAUBT and ziel not in ERLAUBT[teil]:
                verstoesse.append(f"{pfad.relative_to(PAKET)}:{zeile}: {teil} → {ziel}")
    assert not verstoesse, "Import gegen den Aufbau:\n" + "\n".join(verstoesse)


def test_alle_teile_vorhanden():
    # Ordner ohne Python-Dateien (z. B. nur noch __pycache__ nach dem Verschieben) zählen nicht
    teile = {p.name for p in PAKET.iterdir() if p.is_dir() and any(p.rglob("*.py"))}
    assert teile == {
        "modell", "bestand", "pflege", "analysen", "webseite"
    }  # fmt: skip
