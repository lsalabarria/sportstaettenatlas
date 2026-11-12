"""Ausgaben des ALKIS-Abgleichs für die Karte – ohne Geo-Bibliotheken (synthetische Daten)."""

import pandas as pd

from sportstaettenatlas.analysen.alkis.karte import atlas_geojson, zusammenfassung
from sportstaettenatlas.web import html_seite


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
            "abstand_m": [0.0, None, 230.5, 80.0],
            "typ_passt": [True, None, False, True],
            "lon": [7.6, 7.7, 7.8, None],
            "lat": [50.3, 50.4, 50.5, None],
        }
    )


def test_eine_datei_bettet_daten_sicher_ein():
    seite = html_seite(
        "Titel <i>",
        "©GeoBasis-DE / LVermGeoRP 2026",
        eingebettet={"analysen/alkis/sportanlagen.geojson": _fc({"name": "</script><b>x</b>"})},
    )
    # jedes Skript endet genau einmal: Leaflet, Werte, die fünf Skripte der Seite
    assert seite.count("</script>") == 7
    assert "<\\/script><b>x<\\/b>" in seite
    assert "<title>Titel &lt;i&gt;</title>" in seite
    assert "LVermGeoRP 2026" in seite and "leaflet@1.9.4" in seite
    assert '<div id="laden"' not in seite and "konfig.js?" not in seite
    assert "function analyseAlkis" in seite and "<style>" in seite
    assert "__" not in seite.split("<body>")[1].replace("__log", "")  # keine Platzhalter übrig


def test_atlas_punkte():
    fc = atlas_geojson(_bericht())
    # nur „nicht in ALKIS“ und „nah“ mit Koordinate
    assert [f["properties"]["alt_id"] for f in fc["features"]] == ["A2", "A3"]
    assert "abstand_m" not in fc["features"][0]["properties"]  # leer → weggelassen
    assert fc["features"][1]["properties"]["typ_passt"] is False
    assert atlas_geojson(None)["features"] == []


def test_zusammenfassung_je_gemeinde():
    z = zusammenfassung(_bericht(), lambda lon, lat: "071110000000" if lon < 7.75 else None)
    assert z["status"] == ["in ALKIS", "in der Nähe", "nicht in ALKIS"]
    assert z["je_gemeinde"] == {"071110000000": [1, 0, 1]}
    assert z["ohne_gemeinde"] == [0, 1, 0]  # A3 außerhalb, A4 ohne Koordinate fehlt
    assert zusammenfassung(_bericht())["ohne_gemeinde"] == [1, 1, 1]
    assert zusammenfassung(None) is None
