"""Herkunft der Werte und Verifikation ALKIS ↔ bisheriger Sportstättenatlas (nur pandas).

Eine Sportstätte aus ALKIS gilt als bestätigt, wenn der bisherige Sportstättenatlas RLP
sie ebenfalls führt (direkt oder als Nachbarfläche einer zugeordneten Stätte).

- `verifikation`        "ALKIS" oder "ALKIS, Sportstättenatlas RLP"
- `verifikation_anzahl` Anzahl der Quellen (1 oder 2)
- `verifikation_stufe`  "nur ALKIS" | "bestätigt" (auch im Atlas)
                        | "nur ALKIS – unbestimmt": nur ALKIS und ALKIS nennt nur den
                        Sammelbegriff "Sportanlage" (sportanlage_unbestimmt) – oft
                        Nebenflächen, Parkplätze o. ä.; zuerst prüfen

Einträge, die nur im Atlas stehen, erscheinen im Bericht abgleich_altbestand.csv.
Sportanlagen übernehmen die Verifikation ihrer Sportstätte, weil der Atlas Punkte je
Sportstätte führt. Für zusammengeführte Felder steht die Herkunft in `<feld>_quelle`;
die Rohwerte des Atlas bleiben mit Präfix alt_* erhalten.
"""

from __future__ import annotations

import pandas as pd

QUELLE_ALKIS = "ALKIS"
QUELLE_ALT = "Sportstättenatlas RLP"
STUFE_NUR_ALKIS = "nur ALKIS"
STUFE_BESTAETIGT = "bestätigt"
STUFE_UNBESTIMMT = "nur ALKIS – unbestimmt"
TYP_UNBESTIMMT = "sportanlage_unbestimmt"

# Feld → Kandidaten in Prioritätsreihenfolge (Spalte, Quelle)
FELDER_STAETTE: dict[str, list[tuple[str, str]]] = {
    "name": [("name", QUELLE_ALKIS), ("alt_name", QUELLE_ALT)],
    "betreiber": [("alt_betreiber", QUELLE_ALT)],
    "eigentuemer": [("alt_eigentuemer", QUELLE_ALT)],
    "website": [("alt_website", QUELLE_ALT)],
    "adresse": [("alt_adresse", QUELLE_ALT)],
    "email": [("alt_email", QUELLE_ALT)],
    "sportarten": [("alt_sportarten", QUELLE_ALT)],
    "betriebsstatus": [("alt_betriebsstatus", QUELLE_ALT)],
    "anlagen_laut_altbestand": [("alt_anlagentypen", QUELLE_ALT)],
}
FELDER_ANLAGE: dict[str, list[tuple[str, str]]] = {
    "name": [("name", QUELLE_ALKIS)],
}


def _gefuellt(s: pd.Series) -> pd.Series:
    return s.notna() & (s.astype(str).str.strip() != "") & (s.astype(str) != "nan")


def zusammenfuehren(df: pd.DataFrame, felder: dict[str, list[tuple[str, str]]]) -> pd.DataFrame:
    """Für jedes Feld den ersten vorhandenen Wert übernehmen und die Quelle vermerken."""
    df = df.copy()
    for feld, kandidaten in felder.items():
        wert = pd.Series([None] * len(df), index=df.index, dtype="object")
        quelle = pd.Series([None] * len(df), index=df.index, dtype="object")
        for spalte, q in kandidaten:
            if spalte not in df.columns:
                continue
            neu = wert.isna() & _gefuellt(df[spalte])
            wert[neu] = df.loc[neu, spalte].astype(str)
            quelle[neu] = q
        df[feld] = wert
        df[f"{feld}_quelle"] = quelle
    return df


def _hat(df: pd.DataFrame, spalte: str) -> pd.Series:
    return _gefuellt(df[spalte]) if spalte in df.columns else pd.Series(False, index=df.index)


def verifiziere(staetten: pd.DataFrame, anlagen: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Verifikationsspalten für Sportstätten und Sportanlagen."""
    staetten = staetten.copy()
    anlagen = anlagen.copy()

    im_atlas = _hat(staetten, "alt_id")
    staetten["verifikation"] = [
        f"{QUELLE_ALKIS}, {QUELLE_ALT}" if a else QUELLE_ALKIS for a in im_atlas
    ]
    staetten["verifikation_anzahl"] = [2 if a else 1 for a in im_atlas]
    staetten["verifikation_stufe"] = [STUFE_BESTAETIGT if a else STUFE_NUR_ALKIS for a in im_atlas]

    ids = staetten["sportstaette_id"]
    # "nur ALKIS" + ALKIS kennt nur den Sammelbegriff "Sportanlage" → eigene Stufe
    if "typ" in anlagen and len(anlagen):
        rolle = anlagen["rolle"] if "rolle" in anlagen else pd.Series(None, index=anlagen.index)
        eigen = anlagen[rolle.ne("zubehoer")]
        nur_unbestimmt = eigen.groupby("sportstaette_id")["typ"].agg(
            lambda t: bool(len(t)) and (t == TYP_UNBESTIMMT).all()
        )
        u_st = (staetten["verifikation_stufe"] == STUFE_NUR_ALKIS) & ids.map(nur_unbestimmt).fillna(
            False
        ).astype(bool)
        staetten.loc[u_st, "verifikation_stufe"] = STUFE_UNBESTIMMT

    # Sportanlagen übernehmen die Verifikation ihrer Sportstätte
    je = staetten.set_index("sportstaette_id")
    for spalte in ("verifikation", "verifikation_anzahl", "verifikation_stufe"):
        anlagen[spalte] = anlagen["sportstaette_id"].map(je[spalte])
    if "typ" in anlagen:
        u_an = (anlagen["verifikation_stufe"].isin([STUFE_NUR_ALKIS, STUFE_UNBESTIMMT])) & (
            anlagen["typ"] == TYP_UNBESTIMMT
        )
        anlagen.loc[u_an, "verifikation_stufe"] = STUFE_UNBESTIMMT
        andere = (anlagen["verifikation_stufe"] == STUFE_UNBESTIMMT) & (
            anlagen["typ"] != TYP_UNBESTIMMT
        )
        anlagen.loc[andere, "verifikation_stufe"] = STUFE_NUR_ALKIS
    anlagen["verifikation_sportstaette"] = anlagen["verifikation"]
    return staetten, anlagen
