from sportstaettenatlas.karte import html_seite


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


def test_html_seite_bettet_daten_sicher_ein():
    seite = html_seite(
        _fc({"name": "</script><b>x</b>", "typgruppe": "halle", "lon": 7.6, "lat": 50.35}),
        _fc({"komplex_id": "K1"}),
        "Titel <i>",
        "©GeoBasis-DE / LVermGeoRP 2026",
    )
    assert seite.count("</script>") == 2  # nur Leaflet und das eigene Skript
    assert "<\\/script><b>x<\\/b>" in seite
    assert "<title>Titel &lt;i&gt;</title>" in seite
    assert "LVermGeoRP 2026" in seite and "leaflet@1.9.4" in seite
    assert "__" not in seite.split("<body>")[1].replace("__log", "")  # keine Platzhalter übrig


def test_atlas_punkte():
    import pandas as pd

    from sportstaettenatlas.karte import atlas_geojson

    b = pd.DataFrame(
        {
            "alt_id": ["A1", "A2", "A3"],
            "status": ["zugeordnet", "nicht in ALKIS", "nah"],
            "alt_name": ["Platz", "Reitanlage Hof", None],
            "abstand_m": [0.0, None, 230.5],
            "typ_passt": [True, None, False],
            "lon": [7.6, 7.7, 7.8],
            "lat": [50.3, 50.4, 50.5],
        }
    )
    fc = atlas_geojson(b)
    assert [f["properties"]["alt_id"] for f in fc["features"]] == ["A2", "A3"]
    assert "abstand_m" not in fc["features"][0]["properties"]  # leer → weggelassen
    assert fc["features"][1]["properties"]["typ_passt"] is False
    seite = html_seite(_fc({"typgruppe": "halle", "lon": 7.6, "lat": 50.3}), _fc({}), "T", "", fc)
    assert "Reitanlage Hof" in seite and "__ATLAS" not in seite
