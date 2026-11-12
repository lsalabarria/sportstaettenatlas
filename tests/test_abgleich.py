"""Räumlicher Abgleich (benötigt geopandas)."""

import pytest

gpd = pytest.importorskip("geopandas")
from shapely.geometry import Point, box

from sportstaettenatlas.analysen.alkis.abgleich import je_objekt

CRS = "EPSG:25832"
X, Y = 399_000, 5_578_000


def _kandidaten():
    return gpd.GeoDataFrame(
        {"kandidat_id": ["SK1", "SK2"], "quelle": ["alkis_nutzung", "alkis_gebaeude_bauwerk"]},
        geometry=[box(X, Y, X + 200, Y + 150), box(X + 500, Y, X + 540, Y + 25)],
        crs=CRS,
    )


def test_je_objekt_punkt_geht_an_einen_kandidaten():
    wd = gpd.GeoDataFrame(
        {"wd_id": ["Q1"], "wd_name": ["Stadion"]},
        geometry=[Point(X + 100, Y + 75)],
        crs=CRS,
    ).to_crs("EPSG:4326")
    erg = je_objekt(_kandidaten(), wd, ["wd_id", "wd_name"], "wd_")
    assert erg.loc[0, "wd_id"] == "Q1"
    assert erg["wd_id"].notna().sum() == 1


def test_anreichern_mit_bestand():
    """Datenbestand → Abgleich, Gebietsfilter, Herkunft und Verifikation."""
    from sportstaettenatlas.analysen.alkis import abgleich

    st = _kandidaten().rename(columns={"kandidat_id": "sportstaette_id"})
    st["name"] = [None, None]
    an = gpd.GeoDataFrame(
        {
            "anlage_id": ["SA1", "SA2"],
            "sportstaette_id": ["SK1", "SK2"],
            "typgruppe": ["spielfeld", "unbestimmt"],
            "typ": ["sportplatz", "sportanlage_unbestimmt"],
            "rolle": ["sportanlage", "sportanlage"],
        },
        geometry=[box(X + 10, Y + 10, X + 50, Y + 40), box(X + 501, Y + 1, X + 539, Y + 24)],
        crs=CRS,
    )
    # Datenbestand (wie aus bestand.lies_bestand); Lage in WGS84
    wgs = gpd.GeoSeries([Point(X + 100, Y + 75), Point(X + 9000, Y)], crs=CRS).to_crs("EPSG:4326")
    bestand = [
        {
            "id": "a-1",
            "name": "Sportplatz Test",
            "kategorie": "Sportplatz",
            "betreiber": "TuS Test",
            "betriebsstatus": "in Betrieb",
            "lage": {"lon": wgs.iloc[0].x, "lat": wgs.iloc[0].y},
            "_ordner": "07111-koblenz",
            "anlagen": [
                {"id": "x1", "sportstaette_id": "a-1", "typ": "Großspielfeld"},
                {
                    "id": "x2",
                    "sportstaette_id": "a-1",
                    "typ": "Großspielfeld",
                    "sportarten": ["Fußball"],
                },
            ],
        },
        {
            "id": "a-2",
            "name": "Weit weg",
            "kategorie": "Sportplatz",
            "lage": {"lon": wgs.iloc[1].x, "lat": wgs.iloc[1].y},
            "anlagen": [],
        },
    ]
    atlas = abgleich.aus_bestand(bestand)
    assert atlas.crs == CRS and list(atlas["alt_id"]) == ["a-1", "a-2"]
    assert atlas.loc[0, "alt_anlagentypen"] == "2× Großspielfeld"
    assert atlas.loc[0, "alt_sportarten"] == "Fußball"  # aus der Anlage
    assert atlas.loc[0, "alt_datei"] == "07111-koblenz/a-1"
    assert atlas.loc[0, "alt_typgruppe"] == "spielfeld"

    erg_st, erg_an, bericht = abgleich.anreichern(st, an, sitzung=None, atlas=atlas)
    assert len(bericht.abgleich_altbestand) == 1  # a-2 liegt außerhalb des Gebiets
    assert erg_st.loc[0, "verifikation"] == "ALKIS, Sportstättenatlas RLP"
    assert erg_st.loc[0, "verifikation_stufe"] == "bestätigt"
    assert erg_st.loc[0, "name"] == "Sportplatz Test"
    assert erg_st.loc[0, "name_quelle"] == "Sportstättenatlas RLP"
    assert erg_st.loc[0, "betreiber"] == "TuS Test"
    assert erg_st.loc[1, "verifikation_stufe"] == "nur ALKIS – unbestimmt"
    assert erg_an.loc[0, "verifikation_stufe"] == "bestätigt"  # von der Sportstätte
    assert erg_an.loc[1, "verifikation_stufe"] == "nur ALKIS – unbestimmt"
    assert not any(c.startswith(("osm_", "wd_", "web_")) for c in erg_st.columns)


def test_atlas_bericht(tmp_path):
    from sportstaettenatlas.analysen.alkis import abgleich
    from sportstaettenatlas.analysen.alkis.abgleich import je_objekt

    st = _kandidaten().rename(columns={"kandidat_id": "sportstaette_id"})
    an = gpd.GeoDataFrame(
        {
            "anlage_id": ["A1", "A2"],
            "sportstaette_id": ["SK1", "SK2"],
            "typgruppe": ["spielfeld", "halle"],
        },
        geometry=[box(X + 10, Y + 10, X + 50, Y + 40), box(X + 501, Y + 1, X + 539, Y + 24)],
        crs=CRS,
    )
    alt = gpd.GeoDataFrame(
        {
            "alt_id": ["ALT1", "ALT2", "ALT3"],
            "alt_name": ["Sportplatz", "Halle", "Fitness"],
            "alt_typgruppe": ["spielfeld", "spielfeld", None],
        },
        geometry=[Point(X + 100, Y + 75), Point(X + 700, Y + 10), Point(X + 5000, Y)],
        crs=CRS,
    )
    z = je_objekt(st, alt, ["alt_id", "alt_name", "alt_typgruppe"], "alt_", max_m=100)
    b = abgleich.atlas_bericht(alt, st, an, z).set_index("alt_id")
    assert b.loc["ALT1", "status"] == "zugeordnet" and b.loc["ALT1", "typ_passt"]
    assert b.loc["ALT2", "status"] == "nah"  # ~160 m neben SK2 (Grenze 200 m)
    assert not b.loc["ALT2", "typ_passt"]  # dort steht eine Halle, kein Spielfeld
    assert b.loc["ALT3", "status"] == "nicht in ALKIS"
    # Koordinaten für die Karte (WGS84) müssen im Bericht stehen
    assert b["lon"].between(7, 8.5).all() and b["lat"].between(49, 51.5).all()


def test_alkis_vor_ort_beschreibung():
    from sportstaettenatlas.analysen.alkis.vor_ort import beschreibe

    nutzung = gpd.GeoDataFrame(
        {"nutzart": ["Landwirtschaft", "Wald"], "bez": ["Grünland", None], "name": [None, None]},
        geometry=[box(X, Y, X + 100, Y + 100), box(X + 100, Y, X + 200, Y + 100)],
        crs=CRS,
    )
    gebaeude = gpd.GeoDataFrame(
        {
            "funktion": ["Land- und forstwirtschaftliches Betriebsgebäude", "Wohnhaus"],
            "name": ["Reithalle Hof", None],
        },
        geometry=[box(X + 40, Y + 40, X + 60, Y + 60), box(X + 90, Y + 90, X + 95, Y + 95)],
        crs=CRS,
    )
    e = beschreibe(Point(X + 30, Y + 50), nutzung, gebaeude, radius_m=25)
    assert e["alkis_nutzung_vor_ort"] == "Landwirtschaft (Grünland)"
    assert e["alkis_gebaeude_vor_ort"].startswith(
        "Land- und forstwirtschaftliches Betriebsgebäude „Reithalle Hof“ (10 m)"
    )
    assert "Wohnhaus" not in e["alkis_gebaeude_vor_ort"]  # > 25 m entfernt
    leer = beschreibe(Point(X + 30, Y + 50), nutzung, gebaeude.iloc[0:0], radius_m=25)
    assert leer["alkis_gebaeude_vor_ort"] == "kein Gebäude im Umkreis von 25 m"


def test_nachbarflaechen_werden_mitbestaetigt():
    from sportstaettenatlas.analysen.alkis.abgleich import nachbarn_mitbestaetigen

    st = gpd.GeoDataFrame(
        {"sportstaette_id": ["ST1", "ST2", "ST3", "ST4"]},
        geometry=[
            box(X, Y, X + 60, Y + 40),  # Tennishalle, Atlas-Punkt liegt hier
            box(X + 77, Y, X + 100, Y + 40),  # Plätze, 17 m Lücke (Weg)
            box(X + 100, Y, X + 140, Y + 40),  # weitere Plätze, grenzt an ST2
            box(X + 400, Y, X + 440, Y + 40),  # anderer Standort
        ],
        crs=CRS,
    )
    alt = gpd.GeoDataFrame(
        {"alt_id": ["ALT1"], "alt_name": ["Tennisplatz"]},
        geometry=[Point(X + 30, Y + 20)],
        crs=CRS,
    )
    z = je_objekt(st, alt, ["alt_id", "alt_name"], "alt_", max_m=100)
    assert z["alt_id"].notna().sum() == 1
    erg = nachbarn_mitbestaetigen(st, alt, z, ["alt_id", "alt_name"], "alt_")
    assert erg["alt_id"].isna().iloc[3]
    assert erg["alt_id"].iloc[:3].tolist() == ["ALT1"] * 3
    assert erg["alt_bezug"].iloc[0] is None
    assert erg["alt_bezug"].iloc[2] == "Nachbarfläche von ST1"


def test_alkis_vor_ort_zwischenspeicher(tmp_path, monkeypatch):
    import pandas as pd

    from sportstaettenatlas.analysen.alkis import vor_ort
    from sportstaettenatlas.analysen.alkis.quellen import QUELLEN

    aufrufe = []

    def falsch_lies(sitzung, quelle, typename, bbox):
        aufrufe.append(typename)

    monkeypatch.setattr(vor_ort, "_lies", falsch_lies)
    alt = gpd.GeoDataFrame({"alt_id": ["A1"]}, geometry=[Point(X, Y)], crs=CRS)
    bericht = pd.DataFrame({"alt_id": ["A1"], "status": ["nicht in ALKIS"]})
    speicher = tmp_path / "vor_ort.json"
    q = QUELLEN["rp"]
    e1 = vor_ort.ergaenze(bericht, alt, None, q, speicher_pfad=speicher)
    assert len(aufrufe) == 2 and speicher.exists()
    e2 = vor_ort.ergaenze(bericht, alt, None, q, speicher_pfad=speicher)
    assert len(aufrufe) == 2  # zweiter Lauf: nichts angefragt
    assert e1.equals(e2)
    assert e2.at[0, "alkis_gebaeude_vor_ort"].startswith("kein Gebäude")
