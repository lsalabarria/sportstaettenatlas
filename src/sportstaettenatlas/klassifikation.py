"""Regelbasierte Zuordnung von ALKIS-Texten zu Sportstätten-Typen (ohne Geo-Abhängigkeiten)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class Regel:
    enthaelt: tuple[str, ...]
    typgruppe: str
    typ: str
    rolle: str = "sportanlage"
    pruefen: bool = False

    def passt(self, text: str) -> bool:
        t = text.casefold()
        return any(stichwort.casefold() in t for stichwort in self.enthaelt)


@dataclass(frozen=True)
class Treffer:
    typgruppe: str
    typ: str
    rolle: str
    pruefen: bool
    stichwort_regel: str


@dataclass(frozen=True)
class Regelwerk:
    nutzart: str
    regeln_nutzung: tuple[Regel, ...]
    regeln_gebaeude: tuple[Regel, ...]

    @classmethod
    def laden(cls, pfad: Path | None = None) -> Regelwerk:
        if pfad is None:
            text = resources.files("sportstaettenatlas").joinpath("regeln.toml").read_text("utf-8")
        else:
            text = Path(pfad).read_text("utf-8")
        daten = tomllib.loads(text)

        def baue(eintraege: list[dict]) -> tuple[Regel, ...]:
            return tuple(
                Regel(
                    enthaelt=tuple(e["enthaelt"]),
                    typgruppe=e["typgruppe"],
                    typ=e["typ"],
                    rolle=e.get("rolle", "sportanlage"),
                    pruefen=bool(e.get("pruefen", False)),
                )
                for e in eintraege
            )

        return cls(
            nutzart=daten["nutzung"]["nutzart"],
            regeln_nutzung=baue(daten["nutzung"].get("regel", [])),
            regeln_gebaeude=baue(daten.get("gebaeude", {}).get("regel", [])),
        )

    @staticmethod
    def _erste(regeln: tuple[Regel, ...], *texte: object) -> Treffer | None:
        text = " | ".join(str(t) for t in texte if t is not None and str(t) not in ("", "nan"))
        if not text:
            return None
        for regel in regeln:
            if regel.passt(text):
                return Treffer(
                    regel.typgruppe, regel.typ, regel.rolle, regel.pruefen, ",".join(regel.enthaelt)
                )
        return None

    def stichwoerter_gebaeude(self) -> list[str]:
        """Alle Stichwörter der Gebäuderegeln (für den serverseitigen Vorfilter)."""
        gesehen: dict[str, None] = {}
        for regel in self.regeln_gebaeude:
            for wort in regel.enthaelt:
                gesehen.setdefault(wort.lower(), None)  # lower statt casefold: ß bleibt ß
        # Wörter, die ein anderes Stichwort enthalten, sind überflüssig ("sporthalle" ⊃ "sport")
        woerter = list(gesehen)
        return [w for w in woerter if not any(a != w and a in w for a in woerter)]

    def ist_sportflaeche(self, nutzart: object) -> bool:
        return str(nutzart).strip().casefold() == self.nutzart.casefold()

    def nutzung(self, bez: object, name: object = None) -> Treffer | None:
        """Typ einer Sport-/Freizeitfläche.

        Maßgeblich ist die ALKIS-Bezeichnung. Der Name wird nur genutzt, wenn keine
        Bezeichnung vorliegt (sonst wird z. B. der Parkplatz "Moselbad" zum Freibad).
        """
        if _leer(bez):
            return self._erste(self.regeln_nutzung, name)
        return self._erste(self.regeln_nutzung, bez)

    def gebaeude(self, funktion: object, name: object = None) -> Treffer | None:
        """Typ eines Gebäudes/Bauwerks: zuerst die Funktion, dann ersatzweise der Name."""
        return self._erste(self.regeln_gebaeude, funktion) or self._erste(
            self.regeln_gebaeude, name
        )


def _leer(wert: object) -> bool:
    return wert is None or str(wert).strip() in ("", "nan", "None")
