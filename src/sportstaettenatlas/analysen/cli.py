"""Befehle der Analysen: ALKIS-Abgleich (`alkis`) und die Suche nach Webseiten von Vereinen
(`crawler`). Analysen lesen daten/ nur; ihre Ergebnisse landen in results/."""

from __future__ import annotations

from . import crawler
from .alkis import cli as alkis_cli


def befehle(sub) -> None:
    """Befehle dieses Teils an den Parser von `sportstaettenatlas` hängen."""
    sp = sub.add_parser(
        "crawler",
        help="Webseiten für Vereine ohne Webseite suchen (OSM, Wikidata, Domains raten) → "
        "results/vereinswebseiten.csv",
    )
    crawler.argumente(sp)
    sp.set_defaults(func=lambda a: crawler.ausfuehren(a))
    alkis_cli.befehle(sub)
