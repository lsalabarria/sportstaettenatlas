"""Dateien des ALKIS-Abgleichs für die Webseite – ohne Geo-Bibliotheken (synthetische Daten)."""

import re
from pathlib import Path

import pandas as pd

from sportstaettenatlas import modell
from sportstaettenatlas.analysen.alkis import kategorien
from sportstaettenatlas.analysen.alkis.webdaten import (
    _kategorie_setzen,
    atlas_geojson,
    zusammenfassung,
)


def _fc(props):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": [7.6, 50.35]},
            }
        ],
    }


def _bericht():
    return pd.DataFrame(
        {
            "alt_id": ["A1", "A2", "A3", "A4"],
            "status": ["zugeordnet", "nicht in ALKIS", "nah", "nah"],
            "alt_name": ["Platz", "Reitanlage Hof", None, "Bad"],
            "alkis_nutzung_vor_ort": [None, "Landwirtschaft (Grünland)", None, None],
            "abstand_m": [0.0, None, 230.5, 80.0],
            "typ_passt": [True, None, False, True],
            "lon": [7.6, 7.7, 7.8, None],
            "lat": [50.3, 50.4, 50.5, None],
        }
    )


def test_atlas_punkte():
    fc = atlas_geojson(_bericht())
    # nur „nicht in ALKIS“ und „nah“ mit Koordinate
    assert [f["properties"]["alt_id"] for f in fc["features"]] == ["A2", "A3"]
    assert "abstand_m" not in fc["features"][0]["properties"]  # leer → weggelassen
    assert fc["features"][0]["properties"]["alkis_nutzung_vor_ort"] == "Landwirtschaft (Grünland)"
    assert "alkis_nutzung_vor_ort" not in fc["features"][1]["properties"]
    assert fc["features"][1]["properties"]["typ_passt"] is False
    assert atlas_geojson(None)["features"] == []


def test_zusammenfassung_je_gemeinde():
    z = zusammenfassung(_bericht(), lambda lon, lat: "071110000000" if lon < 7.75 else None)
    assert z["status"] == ["in ALKIS", "in der Nähe", "nicht in ALKIS"]
    assert z["je_gemeinde"] == {"071110000000": [1, 0, 1]}
    assert z["ohne_gemeinde"] == [0, 1, 0]  # A3 außerhalb, A4 ohne Koordinate fehlt
    assert zusammenfassung(_bericht())["ohne_gemeinde"] == [1, 1, 1]
    assert zusammenfassung(None) is None


def test_kategorien_und_typgruppen():
    regeln = Path(kategorien.__file__).parent / "regeln.toml"
    gruppen = set(re.findall(r'typgruppe = "([a-z_]+)"', regeln.read_text("utf-8")))
    assert set(kategorien.GRUPPEN) == set(modell.KATEGORIEN)  # jede Kategorie genau einmal
    for g in (g for v in kategorien.GRUPPEN.values() for g in v):
        assert g in gruppen, g
    assert kategorien.gruppe("sportplatz") == "spielfeld"
    assert kategorien.gruppe("Fitnessstudio") is None
    assert kategorien.kategorie("leichtathletik") == "Sportplatz"
    assert kategorien.kategorie("halle") == "Sporthalle"
    assert kategorien.kategorie("spezial") is None


def test_alkis_sportstaette_bekommt_kategorie():
    fc = _fc({"typgruppe": "becken"})
    fc["features"].append({"type": "Feature", "properties": {"typgruppe": "spezial"}})
    _kategorie_setzen(fc)
    assert [f["properties"].get("kategorie") for f in fc["features"]] == [
        "Schwimmsportstätte",
        None,
    ]
