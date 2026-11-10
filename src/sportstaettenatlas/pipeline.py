"""Baut aus ALKIS-Rohdaten die Tabellen Sportstätten und Sportanlagen.

Begriffe:
- Sportstätte: Standort (Sportpark, Schulsportzentrum, Freibad). Geometrie ist die
  ALKIS-Nutzungsfläche "Sport-, Freizeit- und Erholungsfläche" oder – bei freistehenden
  Hallen/Bädern ohne solche Fläche – die Hülle der Gebäude, die nah beieinander stehen.
- Sportanlage: einzelne Einheit einer Sportstätte (Halle, Spielfeld, Becken …).
  Jede Sportanlage gehört zu genau einer Sportstätte (`sportstaette_id`).
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

from .hilfen import datum_text as _datum_text
from .klassifikation import Regelwerk
from .quellen import WfsQuelle

log = logging.getLogger(__name__)

CLUSTER_ABSTAND_M = 20  # freistehende Anlagen, die näher beieinander liegen, = eine Sportstätte

SPALTEN_STAETTEN = [
    "sportstaette_id",
    "quelle",
    "alkis_oid",
    "alkis_text",
    "name",
    "typ",
    "anzahl_anlagen",
    "anlagentypen",
    "pruefen",
    "gemeindeschluessel",
    "flaeche_m2",
    "lon",
    "lat",
    "alkis_stand",
]
SPALTEN_ANLAGEN = [
    "anlage_id",
    "sportstaette_id",
    "quelle",
    "alkis_oid",
    "alkis_text",
    "name",
    "typgruppe",
    "typ",
    "rolle",
    "pruefen",
    "gemeindeschluessel",
    "flaeche_m2",
    "lon",
    "lat",
    "alkis_stand",
]


@dataclass
class Ergebnis:
    sportstaetten: gpd.GeoDataFrame
    sportanlagen: gpd.GeoDataFrame


def _spalte(gdf: gpd.GeoDataFrame, *namen: str) -> pd.Series:
    """Erste vorhandene Spalte (Feldnamen variieren leicht zwischen Ländern)."""
    for n in namen:
        if n in gdf.columns:
            return gdf[n]
    return pd.Series([None] * len(gdf), index=gdf.index, dtype="object")


def _ags(wert: object) -> str | None:
    """Gemeindeschlüssel auf 8 Stellen normieren (führende Null geht oft verloren)."""
    if wert is None or str(wert) in ("", "nan", "None"):
        return None
    s = str(wert).split(".")[0].strip()
    return s.zfill(8) if s.isdigit() else s


def sportflaechen(nutzung: gpd.GeoDataFrame, regeln: Regelwerk) -> gpd.GeoDataFrame:
    """Nutzungsflächen mit Sportbezug – die Flächen der Sportstätten."""
    spalten = ["alkis_oid", "alkis_text", "name", "typgruppe", "typ", "pruefen", "alkis_stand"]
    if nutzung.empty or "nutzart" not in nutzung.columns:
        return gpd.GeoDataFrame(
            columns=[*spalten, "geometry"], geometry="geometry", crs=nutzung.crs
        )
    maske = nutzung["nutzart"].map(regeln.ist_sportflaeche).fillna(False).astype(bool)
    df = nutzung.loc[maske].copy()
    treffer = [
        regeln.nutzung(b, n) for b, n in zip(_spalte(df, "bez", "funktion"), _spalte(df, "name"))
    ]
    df["typgruppe"] = [t.typgruppe if t else None for t in treffer]
    df["typ"] = [t.typ if t else None for t in treffer]
    df["pruefen"] = [t.pruefen if t else True for t in treffer]
    df = df[df["typ"].notna()].copy()  # Parks, Kleingärten, Camping fallen raus
    df["alkis_oid"] = _spalte(df, "oid")
    df["alkis_text"] = _spalte(df, "bez", "funktion")
    df["name"] = _spalte(df, "name")
    df["alkis_stand"] = _spalte(df, "aktualit", "timePosition")
    return df[[*spalten, "geometry"]].reset_index(drop=True)


def sport_gebaeude(gebaeude: gpd.GeoDataFrame, regeln: Regelwerk) -> gpd.GeoDataFrame:
    """Gebäude und Bauwerke mit Sportbezug."""
    treffer = [
        regeln.gebaeude(f, n)
        for f, n in zip(_spalte(gebaeude, "funktion"), _spalte(gebaeude, "name"))
    ]
    df = gebaeude.copy()
    df["_t"] = treffer
    df = df[df["_t"].notna()].copy()
    for feld in ("typgruppe", "typ", "rolle", "pruefen"):
        df[feld] = [getattr(t, feld) for t in df["_t"]]
    df["alkis_oid"] = _spalte(df, "oid")
    df["alkis_text"] = _spalte(df, "funktion")
    df["name"] = _spalte(df, "name")
    df["gemeindeschluessel"] = _spalte(df, "gmdschl").map(_ags)
    df["alkis_stand"] = _spalte(df, "aktualit", "timePosition")
    df["quelle"] = "alkis_gebaeude_bauwerk"
    return df.drop(columns="_t").reset_index(drop=True)


def ordne_flaechen_zu(objekte: gpd.GeoDataFrame, flaechen: gpd.GeoDataFrame) -> pd.Series:
    """Index der Fläche mit der größten Überlappung je Objekt (gemischte Geometrien ok)."""
    leer = pd.Series([pd.NA] * len(objekte), index=objekte.index, dtype="Int64")
    if objekte.empty or flaechen.empty:
        return leer
    links = gpd.GeoDataFrame(
        {"_i": objekte.index}, geometry=objekte.geometry.values, crs=objekte.crs
    )
    rechts = flaechen[["geometry"]].reset_index(drop=True)
    paare = gpd.sjoin(links, rechts, how="inner", predicate="intersects")
    if paare.empty:
        return leer
    fgeom = rechts.geometry.iloc[paare["index_right"].to_numpy()].to_numpy()
    schnitt = paare.geometry.intersection(gpd.GeoSeries(fgeom, index=paare.index, crs=paare.crs))
    paare["_mass"] = schnitt.area * 1e6 + schnitt.length + 1
    beste = paare.sort_values("_mass", ascending=False).drop_duplicates("_i")
    return beste.set_index("_i")["index_right"].reindex(objekte.index).astype("Int64")


def _cluster(geb: gpd.GeoDataFrame, abstand: float) -> pd.Series:
    """Gruppennummer für Objekte, die näher als `abstand` beieinander liegen."""
    if geb.empty:
        return pd.Series(dtype="Int64")
    huellen = gpd.GeoSeries(geb.geometry.buffer(abstand / 2).union_all(), crs=geb.crs)
    teile = huellen.explode(index_parts=False).reset_index(drop=True)
    gruppen = gpd.GeoDataFrame(geometry=teile, crs=geb.crs)
    zuordnung = gpd.sjoin(
        gpd.GeoDataFrame(
            {"_i": geb.index}, geometry=geb.geometry.representative_point().values, crs=geb.crs
        ),
        gruppen,
        how="left",
        predicate="within",
    ).drop_duplicates("_i")
    return zuordnung.set_index("_i")["index_right"].reindex(geb.index)


def baue(
    nutzung: gpd.GeoDataFrame,
    gebaeude: gpd.GeoDataFrame,
    regeln: Regelwerk | None = None,
) -> Ergebnis:
    regeln = regeln or Regelwerk.laden()
    crs = nutzung.crs or gebaeude.crs
    if gebaeude.crs and crs and gebaeude.crs != crs:
        gebaeude = gebaeude.to_crs(crs)

    flaechen = sportflaechen(nutzung, regeln)
    geb = sport_gebaeude(gebaeude, regeln)
    geb["_f"] = ordne_flaechen_zu(geb, flaechen)
    # Nebengebäude zählen nur innerhalb einer Sportstätten-Fläche
    geb = geb[~((geb["rolle"] == "zubehoer") & geb["_f"].isna())].reset_index(drop=True)

    # --- Sportstätten aus Flächen ------------------------------------------
    st_flaeche = flaechen.copy()
    st_flaeche["quelle"] = "alkis_nutzung"
    st_flaeche["_f"] = st_flaeche.index

    # --- Sportstätten aus freistehenden Anlagen (z. B. Schulturnhalle) -------
    frei = geb[geb["_f"].isna()].copy()
    frei["_c"] = _cluster(frei, CLUSTER_ABSTAND_M)
    cluster_zeilen = []
    for _, gruppe in frei.groupby("_c"):
        haupt = gruppe.loc[gruppe.geometry.area.idxmax()]  # größtes Gebäude bestimmt den Typ
        cluster_zeilen.append(
            {
                "quelle": "alkis_gebaeude",
                "alkis_oid": None,
                "alkis_text": "; ".join(dict.fromkeys(gruppe["alkis_text"].dropna())),
                "name": next(iter(gruppe["name"].dropna()), None),
                "typ": haupt["typ"],
                "pruefen": bool(gruppe["pruefen"].all()),
                "alkis_stand": None,
                "_c": gruppe["_c"].iat[0],
                "geometry": gruppe.geometry.union_all().convex_hull,
            }
        )
    st_cluster = (
        gpd.GeoDataFrame(cluster_zeilen, geometry="geometry", crs=crs)
        if cluster_zeilen
        else gpd.GeoDataFrame(columns=["quelle", "_c", "geometry"], geometry="geometry", crs=crs)
    )

    staetten = pd.concat([st_flaeche, st_cluster], ignore_index=True)
    staetten = gpd.GeoDataFrame(staetten, geometry="geometry", crs=crs)
    staetten["sportstaette_id"] = [f"ST{i + 1:06d}" for i in range(len(staetten))]
    id_je_flaeche = staetten.dropna(subset=["_f"]).set_index("_f")["sportstaette_id"]
    id_je_cluster = staetten.dropna(subset=["_c"]).set_index("_c")["sportstaette_id"]

    # --- Sportanlagen --------------------------------------------------------
    geb["sportstaette_id"] = geb["_f"].map(id_je_flaeche)
    fehlt = geb["sportstaette_id"].isna()
    geb.loc[fehlt, "sportstaette_id"] = frei["_c"].reindex(geb.index[fehlt]).map(id_je_cluster)

    # Sportstätten-Flächen ohne erkannte Sportanlage werden selbst zur Sportanlage
    # (typisch: Sportplatz, der nur als Nutzungsfläche geführt ist).
    belegt = set(geb.loc[geb["rolle"] == "sportanlage", "sportstaette_id"].dropna())
    aus_flaeche = staetten[
        (staetten["quelle"] == "alkis_nutzung") & ~staetten["sportstaette_id"].isin(belegt)
    ].copy()
    aus_flaeche["quelle"] = "alkis_nutzung"
    aus_flaeche["rolle"] = "sportanlage"
    aus_flaeche["pruefen"] = True  # typgruppe/typ stammen aus der Flächenregel

    anlagen = pd.concat([geb, aus_flaeche], ignore_index=True)
    anlagen = gpd.GeoDataFrame(anlagen, geometry="geometry", crs=crs)
    if "gemeindeschluessel" not in anlagen:
        anlagen["gemeindeschluessel"] = None

    # Gemeindeschlüssel je Sportstätte (häufigster Wert ihrer Gebäude)
    ags = (
        anlagen.dropna(subset=["gemeindeschluessel"])
        .groupby("sportstaette_id")["gemeindeschluessel"]
        .agg(lambda s: s.mode().iat[0])
    )
    staetten["gemeindeschluessel"] = staetten["sportstaette_id"].map(ags)
    fehlt = anlagen["gemeindeschluessel"].isna()
    anlagen.loc[fehlt, "gemeindeschluessel"] = anlagen.loc[fehlt, "sportstaette_id"].map(ags)

    # Kennzahlen der Sportstätten aus ihren Anlagen
    echte = anlagen[anlagen["rolle"] != "zubehoer"]
    staetten["anzahl_anlagen"] = (
        staetten["sportstaette_id"]
        .map(echte.groupby("sportstaette_id").size())
        .fillna(0)
        .astype(int)
    )
    staetten["anlagentypen"] = staetten["sportstaette_id"].map(
        echte.groupby("sportstaette_id")["typ"].agg(lambda s: "; ".join(sorted(set(s.dropna()))))
    )
    namen = anlagen.dropna(subset=["name"]).groupby("sportstaette_id")["name"].first()
    staetten["name"] = staetten["name"].fillna(staetten["sportstaette_id"].map(namen))

    for gdf in (staetten, anlagen):
        gdf["flaeche_m2"] = gdf.geometry.area.round(1)
        if not gdf.empty:
            punkte = gdf.geometry.representative_point().to_crs("EPSG:4326")
            gdf["lon"], gdf["lat"] = punkte.x.round(6), punkte.y.round(6)

    anlagen = anlagen.sort_values(["sportstaette_id", "typgruppe", "typ"], na_position="last")
    anlagen = anlagen.reset_index(drop=True)
    anlagen["anlage_id"] = [f"SA{i + 1:07d}" for i in range(len(anlagen))]

    def ordnen(gdf, spalten):
        for s in spalten:
            if s not in gdf.columns:
                gdf[s] = None
        gdf["alkis_stand"] = _datum_text(gdf["alkis_stand"])
        return gpd.GeoDataFrame(gdf[[*spalten, "geometry"]], geometry="geometry", crs=crs)

    return Ergebnis(
        sportstaetten=ordnen(staetten, SPALTEN_STAETTEN),
        sportanlagen=ordnen(anlagen, SPALTEN_ANLAGEN),
    )


def schreibe(
    ergebnis: Ergebnis, ziel: Path, quelle: WfsQuelle, bbox
) -> tuple[Path, Path, Path, Path]:
    """GeoPackage, zwei CSV-Tabellen und die Karte schreiben."""
    from .karte import schreibe_karte

    ziel.mkdir(parents=True, exist_ok=True)
    gpkg = ziel / "sportstaetten.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    ergebnis.sportstaetten.to_file(gpkg, layer="sportstaetten", driver="GPKG")
    ergebnis.sportanlagen.to_file(gpkg, layer="sportanlagen", driver="GPKG")

    jahr = dt.datetime.now(dt.UTC).year
    vermerk = quelle.quellenvermerk.format(jahr=jahr)
    meta = pd.DataFrame(
        {
            "schluessel": ["quelle", "url", "lizenz", "quellenvermerk", "bbox", "erstellt"],
            "wert": [
                quelle.name,
                quelle.url,
                quelle.lizenz,
                vermerk,
                ",".join(str(v) for v in bbox),
                dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            ],
        }
    )
    pyogrio.write_dataframe(meta, gpkg, layer="metadaten", driver="GPKG")
    (ziel / "QUELLENVERMERK.txt").write_text(
        f"{vermerk}\nLizenz: {quelle.lizenz}\n", encoding="utf-8"
    )

    csv_st = ziel / "sportstaetten.csv"
    csv_an = ziel / "sportanlagen.csv"
    ergebnis.sportstaetten.drop(columns="geometry").to_csv(csv_st, index=False, encoding="utf-8")
    ergebnis.sportanlagen.drop(columns="geometry").to_csv(csv_an, index=False, encoding="utf-8")
    # Altlast aus früheren Versionen entfernen, damit nichts Veraltetes herumliegt
    (ziel / "sportstaetten_kandidaten.csv").unlink(missing_ok=True)

    karte = schreibe_karte(
        ergebnis.sportanlagen, ergebnis.sportstaetten, ziel / "karte.html", quellenvermerk=vermerk
    )
    return gpkg, csv_st, csv_an, karte
