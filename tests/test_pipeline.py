"""Ende-zu-Ende-Test mit synthetischen ALKIS-Daten (benötigt geopandas)."""

import pytest

gpd = pytest.importorskip("geopandas")
from shapely.geometry import box

from sportstaettenatlas.pipeline import baue

CRS = "EPSG:25832"
X, Y = 399_000, 5_578_000


def _nutzung():
    return gpd.GeoDataFrame(
        {
            "oid": ["N1", "N2", "N3", "N4"],
            "nutzart": ["Sport-, Freizeit- und Erholungsfläche"] * 3 + ["Wohnbaufläche"],
            "bez": ["Sportanlage", "Sportanlage", "Grünanlage", None],
            "name": ["Sportpark Nord", None, None, None],
        },
        geometry=[
            box(X, Y, X + 200, Y + 150),  # Sportpark mit Halle
            box(X + 500, Y, X + 620, Y + 80),  # Sportplatz ohne Gebäude
            box(X + 1000, Y, X + 1100, Y + 100),  # Park
            box(X + 2000, Y, X + 2100, Y + 100),  # Wohnen
        ],
        crs=CRS,
    )


def _gebaeude():
    return gpd.GeoDataFrame(
        {
            "oid": ["G1", "G2", "G3", "G4", "G5", "G6"],
            "funktion": [
                "Sport-, Turnhalle",
                "Gebäude zum Sportplatz",
                "Wohnhaus",
                "Sport-, Turnhalle",
                "Hallenbad",
                "Tribüne",
            ],
            "gmdschl": ["7111000"] * 6,
            "name": [None, None, None, "Schulturnhalle", None, None],
        },
        geometry=[
            box(X + 10, Y + 10, X + 55, Y + 37),
            box(X + 100, Y + 100, X + 120, Y + 110),
            box(X + 2010, Y + 10, X + 2020, Y + 20),
            box(X + 3000, Y, X + 3030, Y + 20),  # freistehende Schulturnhalle …
            box(X + 3040, Y, X + 3070, Y + 25),  # … mit Lehrschwimmhalle 10 m daneben
            box(X + 5000, Y, X + 5010, Y + 10),  # Tribüne ohne Sportfläche → verworfen
        ],
        crs=CRS,
    )


def test_baue():
    erg = baue(_nutzung(), _gebaeude())
    st, an = erg.sportstaetten, erg.sportanlagen
    # 2 Flächen-Sportstätten + 1 Cluster aus Turnhalle und Hallenbad
    assert len(st) == 3
    park = st[st["alkis_oid"] == "N1"].iloc[0]
    assert park["name"] == "Sportpark Nord" and park["anzahl_anlagen"] == 1
    assert park["gemeindeschluessel"] == "07111000"
    cluster = st[st["quelle"] == "alkis_gebaeude"].iloc[0]
    assert cluster["anzahl_anlagen"] == 2 and cluster["name"] == "Schulturnhalle"
    assert set(cluster["anlagentypen"].split("; ")) == {"sporthalle", "hallenbad"}

    halle = an[an["alkis_oid"] == "G1"].iloc[0]
    assert halle["sportstaette_id"] == park["sportstaette_id"] and halle["typ"] == "sporthalle"
    assert an.loc[an["alkis_oid"] == "G2", "rolle"].iat[0] == "zubehoer"
    assert not {"G3", "G6"} & set(an["alkis_oid"])
    # Sportplatz ohne Gebäude wird als Anlage aus der Fläche übernommen
    flaeche = an[an["quelle"] == "alkis_nutzung"]
    assert list(flaeche["alkis_oid"]) == ["N2"]
    assert an["sportstaette_id"].notna().all() and an["anlage_id"].is_unique
    assert an["lon"].between(7, 8.5).all() and an["lat"].between(49, 51.5).all()


def test_karte_mit_datumsspalte(tmp_path):
    import json

    import pandas as pd

    from sportstaettenatlas.karte import geojson, schreibe_karte

    erg = baue(_nutzung(), _gebaeude())
    an = erg.sportanlagen.copy()
    an["alkis_stand"] = pd.to_datetime("2025-03-26")
    fc = geojson(an)
    assert fc["features"][0]["properties"]["alkis_stand"] == "2025-03-26"
    json.dumps(fc)
    pfad = schreibe_karte(an, erg.sportstaetten, tmp_path / "karte.html")
    assert "2025-03-26" in pfad.read_text(encoding="utf-8")
