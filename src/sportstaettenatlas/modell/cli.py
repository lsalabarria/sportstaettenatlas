"""Befehl `modell`: Feldtabellen und Diagramm aus dem Datenmodell nach daten/erzeugt/."""

from __future__ import annotations

from ..hilfen import DATEN


def cmd_modell(args):
    """Datenmodell (modell/) als Feldtabellen und Diagramm nach daten/erzeugt/."""
    from . import schreibe_doku

    for hinweis in schreibe_doku(DATEN):
        print(hinweis)


def befehle(sub) -> None:
    """Befehle dieses Teils an den Parser von `sportstaettenatlas` hängen."""
    sp = sub.add_parser(
        "modell", help="Feldtabellen und Diagramm des Datenmodells nach daten/erzeugt/ schreiben"
    )
    sp.set_defaults(func=cmd_modell)
