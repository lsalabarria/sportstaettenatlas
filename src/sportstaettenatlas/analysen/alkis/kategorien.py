"""Kategorien des Atlas ↔ Typgruppen der ALKIS-Regeln (regeln.toml).

Der Abgleich vergleicht über `gruppe` die Kategorie einer Sportstätte aus daten/ mit der
Typgruppe der ALKIS-Fläche. Umgekehrt bekommt eine ALKIS-Sportstätte über `kategorie` eine
Kategorie, mit der das Vorschlagsformular sie vorausfüllt.
"""

from __future__ import annotations

# Kategorie → Typgruppen; die erste zählt für den Vergleich. Leer: keine Gruppe.
GRUPPEN: dict[str, tuple[str, ...]] = {
    "Sportplatz": ("spielfeld", "leichtathletik"),
    "Sporthalle": ("halle",),
    "Tennissportstätte": ("spielfeld",),
    "Öffentlicher Sport- und Bewegungsraum": ("sportgelegenheit",),
    "Reitsportstätte": ("spezial",),
    "Schwimmsportstätte": ("becken",),
    "Schießsportstätte": ("spezial",),
    "Fitnessstudio": (),
    "Golfsportstätte": ("spezial",),
    "Roll- und Skatesportstätte": ("spezial",),
    "Sportgelegenheiten in sonstigen Gebäuden": ("sportgelegenheit",),
    "Radsportstätte": ("spezial",),
    "Flugsportstätte": ("spezial",),
    "Wintersportstätte": ("spezial",),
    "Wassersportstätte": ("spezial",),
    "Klettersportstätte": ("spezial",),
    "Motorsportstätte": ("spezial",),
    "Eissportstätte": ("eis",),
    "Leistungsstützpunkt": (),
    "Segelsportstätte": ("spezial",),
}


def gruppe(kategorie: str | None) -> str | None:
    """Typgruppe für eine Kategorie (Groß-/Kleinschreibung egal); None ohne."""
    k = (kategorie or "").strip().lower()
    gruppen = next((v for kat, v in GRUPPEN.items() if kat.lower() == k), ())
    return gruppen[0] if gruppen else None


def _kategorien() -> dict[str, str]:
    out: dict[str, str] = {}
    for kat, gruppen in GRUPPEN.items():
        for g in gruppen:
            if g != "spezial":  # sagt nichts über die Kategorie
                out.setdefault(g, kat)
    return out


KATEGORIE = _kategorien()


def kategorie(typgruppe: str | None) -> str | None:
    """Kategorie für eine ALKIS-Typgruppe; None, wenn sie keine eindeutig nennt."""
    return KATEGORIE.get(typgruppe or "")
