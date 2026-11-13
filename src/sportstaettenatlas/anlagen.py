"""Sportanlagen einer Sportstätte: einheitliche Typen und Gruppen für Karte und Filter.

Eine Sportstätte (ein Punkt auf der Karte) enthält eine oder mehrere Sportanlagen, z. B.
ein Sportplatz mit Großspielfeld, Rundlaufbahn und Weitsprunganlage. Der Atlas schreibt
dieselbe Anlage oft verschieden ("Großspielfeld (ab 5.000 m²)", "Nichtnormiertes
Spielfeld"). `typ` macht daraus einen einheitlichen Typ, `GRUPPEN` ordnet die Typen für
den Filter der Karte. Unbekannte Bezeichnungen bleiben, wie sie sind, und landen über
Stichwörter bzw. unter „Weitere“.
"""

from __future__ import annotations

import re

# Gruppe → (Beschriftung, Typen). Die Reihenfolge ist die im Filter.
GRUPPEN: dict[str, tuple[str, tuple[str, ...]]] = {
    "spielfeld": (
        "Spielfelder",
        (
            "Großspielfeld",
            "Kleinspielfeld",
            "Nicht normiertes Spielfeld",
            "Volleyballfeld",
            "Beachvolleyballfeld",
            "Rollsportplatz",
        ),
    ),
    "tennis": ("Tennis", ("Tennisplatz", "Tennishalle", "Ballwand", "Paddleplatz")),
    "halle": (
        "Hallen und Räume",
        (
            "Sporthalle (Größe unbekannt)",
            "Sport-/Turnhalle",
            "Sport-/Turnhalle untermaßig",
            "Einfachsporthalle",
            "Zweifachsporthalle",
            "Dreifachsporthalle",
            "Großsporthalle",
            "Sporthalle Sondermaße",
            "Übungsraum",
            "Kurs-/Übungsraum",
            "Kraftraum",
            "Squashhalle",
        ),
    ),
    "leichtathletik": (
        "Leichtathletik",
        (
            "Rundlaufbahn",
            "Kurzstreckenbahn",
            "Weit- und Dreisprunganlage",
            "Hochsprunganlage",
            "Stabhochsprunganlage",
            "Kugelstoßanlage",
            "Speerwurfanlage",
            "Diskus- und Hammerwurfanlage",
            "Hindernislauf mit Wassergraben",
        ),
    ),
    "bad": ("Bäder", ("Freibad", "Hallenbad", "Naturbad", "Kombibad", "Cabriobad")),
    "reiten": (
        "Reiten",
        (
            "Reitplatz",
            "Reithalle",
            "Springparcours",
            "Geländeparcours",
            "Führ- und Longierplatz",
            "Führ- und Longierhalle",
        ),
    ),
    "schiessen": ("Schießen", ("Schießstand", "Bogenschießanlage")),
    "freizeit": (
        "Freizeit und Bewegung",
        (
            "Bouleanlage",
            "Skateplatz",
            "Skatehalle",
            "Bahnengolf",
            "Calisthenicsanlage",
            "Bewegungsparcours",
            "Klettersportanlage Outdoor",
            "Klettersporthalle",
            "Tischtennistisch",
            "Spielplatz",
        ),
    ),
    "rad_motor": (
        "Rad- und Motorsport",
        (
            "Mountainbikestrecke",
            "BMX-Strecke",
            "Radrennbahn",
            "Rennbahn",
            "Motocross-Strecke",
            "Kartbahn",
            "Motorsport-Rennstrecke",
            "Fahrparcours",
        ),
    ),
    "wasser": (
        "Wassersport",
        (
            "Regattastrecke",
            "Rudersportanlage",
            "Sporthafen",
            "Wildwasseranlage",
            "Rundrennstrecke (Motorboot)",
        ),
    ),
    "winter": (
        "Eis- und Wintersport",
        (
            "Eissporthalle",
            "Eissportanlage ungedeckt",
            "Skilanglauf- und Biathlonanlage",
            "Alpine Skianlage",
            "Bob-/Rodelbahn",
        ),
    ),
    "luft": ("Luftsport", ("Sportflugplatz", "Segelfluggelände", "Sonderlandeplatz")),
    "neben": (
        "Nebenräume und Zubehör",
        ("Geräteraum", "Gerätebereich", "Stall", "Bootshaus/-halle", "Bühne"),
    ),
    "weitere": (
        "Weitere",
        ("Golfplatz", "Kegelbahn", "Bowlingbahn", "sonstige Sportanlage"),
    ),
}
GRUPPE_VON = {t: g for g, (_, typen) in GRUPPEN.items() for t in typen}


def _schluessel(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


# Schreibweisen des Atlas → Typ (Schlüssel: klein, ohne Leerzeichen, siehe _schluessel)
_VARIANTEN = {
    "großspielfeld(ab5.000m²)": "Großspielfeld",
    "kleinspielfeld(<5.000m²)": "Kleinspielfeld",
    "nichtnormiertesspielfeld": "Nicht normiertes Spielfeld",
    "beachvolleyballfeld": "Beachvolleyballfeld",
    "sporthallegrößeunbekannt": "Sporthalle (Größe unbekannt)",
    "sport-turnhalle": "Sport-/Turnhalle",
    "sport-/turnhalle": "Sport-/Turnhalle",
    "sport-/turnhalleuntermaßig(größeiundii)": "Sport-/Turnhalle untermaßig",
    "einfach-sporthalleohnetrennvorhang(größeiii)": "Einfachsporthalle",
    "einfach-sporthalle": "Einfachsporthalle",
    "zweifach-sporthalle(größeiv)": "Zweifachsporthalle",
    "zweifach-sporthalle": "Zweifachsporthalle",
    "dreifach-sporthalle(größev)": "Dreifachsporthalle",
    "dreifach-sporthalle": "Dreifachsporthalle",
    "großsporthalle(größevi)": "Großsporthalle",
    "kurs-/übungsraum": "Kurs-/Übungsraum",
    "weit-,dreisprunganlage": "Weit- und Dreisprunganlage",
    "diskus-,hammerwurfanlage": "Diskus- und Hammerwurfanlage",
    "wassergraben-,hindernislauf": "Hindernislauf mit Wassergraben",
    "wassergrabenhindernislauf": "Hindernislauf mit Wassergraben",
    "führ-undlogierplatz": "Führ- und Longierplatz",
    "führ-undlogierhalle": "Führ- und Longierhalle",
    "bahnengolf(minigolf)": "Bahnengolf",
    "golfsportstätte": "Golfplatz",
}
# Typen ohne eigene Variante, aber in anderer Groß-/Kleinschreibung
_VARIANTEN.update({_schluessel(t): t for t in GRUPPE_VON})

# Für Bezeichnungen, die keiner kennt: Gruppe über Stichwörter
_STICHWOERTER = (
    (r"tennis", "tennis"),
    (r"bad\b|becken|schwimm", "bad"),
    (r"reit|pferd|longier", "reiten"),
    (r"schieß|schiess|bogen", "schiessen"),
    (r"halle|raum", "halle"),
    (r"sprung|wurf|stoß|laufbahn|leichtathletik", "leichtathletik"),
    (r"spielfeld|platz|court", "spielfeld"),
    (r"eis|ski|rodel", "winter"),
)


def typ(bezeichnung: str) -> str:
    """Einheitlicher Typ einer Anlage; unbekannte Bezeichnungen bleiben (bereinigt) erhalten."""
    text = re.sub(r"\s+", " ", (bezeichnung or "").strip())
    return _VARIANTEN.get(_schluessel(text), text)


def gruppe(anlagentyp: str) -> str:
    """Gruppe eines Typs (siehe GRUPPEN) – bekannte Typen fest, sonst über Stichwörter."""
    if anlagentyp in GRUPPE_VON:
        return GRUPPE_VON[anlagentyp]
    klein = anlagentyp.lower()
    for muster, g in _STICHWOERTER:
        if re.search(muster, klein):
            return g
    return "weitere"


def zusammenfuegen(bezeichnungen: list[str]) -> list[str]:
    """Teile mit Bindestrich am Ende gehören zum nächsten ("Weit-", "Dreisprunganlage")."""
    out: list[str] = []
    for b in bezeichnungen:
        b = (b or "").strip()
        if not b:
            continue
        if out and out[-1].endswith("-"):
            out[-1] = f"{out[-1]}, {b}"
        else:
            out.append(b)
    return out
