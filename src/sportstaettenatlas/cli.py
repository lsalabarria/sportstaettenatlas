"""Kommandozeile `sportstaettenatlas` – die Befehle stehen in README.md („Befehle“) und
unter `sportstaettenatlas --help`. Jeder Teil bringt seine Befehle selbst mit (cli.py in
pflege/, bestand/, webseite/, modell/, analysen/).
"""

from __future__ import annotations

import argparse
import logging

from .analysen import cli as analysen_cli
from .bestand import cli as bestand_cli
from .modell import cli as modell_cli
from .pflege import cli as pflege_cli
from .webseite import cli as webseite_cli


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="sportstaettenatlas", description="Offener Sportstättenatlas.")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="befehl", required=True)
    for teil in (pflege_cli, bestand_cli, webseite_cli, modell_cli, analysen_cli):
        teil.befehle(sub)

    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    from tqdm.contrib.logging import logging_redirect_tqdm

    with logging_redirect_tqdm():  # Log-Zeilen erscheinen über dem Fortschrittsbalken
        args.func(args)


if __name__ == "__main__":
    main()
