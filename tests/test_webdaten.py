"""Dateien des ALKIS-Abgleichs für die Webseite – ohne Geo-Bibliotheken (synthetische Daten)."""

import pandas as pd

from sportstaettenatlas.analysen.alkis.webdaten import atlas_geojson, zusammenfassung


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
            "alkis_vor_ort": [None, "Freizeitanlage", None, None],
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
    assert fc["features"][0]["properties"]["alkis_vor_ort"] == "Freizeitanlage"
    assert "alkis_vor_ort" not in fc["features"][1]["properties"]
    assert fc["features"][1]["properties"]["typ_passt"] is False
    assert atlas_geojson(None)["features"] == []


def test_zusammenfassung_je_gemeinde():
    z = zusammenfassung(_bericht(), lambda lon, lat: "071110000000" if lon < 7.75 else None)
    assert z["status"] == ["in ALKIS", "in der Nähe", "nicht in ALKIS"]
    assert z["je_gemeinde"] == {"071110000000": [1, 0, 1]}
    assert z["ohne_gemeinde"] == [0, 1, 0]  # A3 außerhalb, A4 ohne Koordinate fehlt
    assert zusammenfassung(_bericht())["ohne_gemeinde"] == [1, 1, 1]
    assert zusammenfassung(None) is None
