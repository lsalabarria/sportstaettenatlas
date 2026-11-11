"""Gebietszuordnung ohne Geo-Bibliotheken."""

from sportstaettenatlas.gebiete import Zuordnung, index, punkt_in, schluessel


def _quadrat(w, s, groesse=1.0, loch=None):
    ringe = [[[w, s], [w + groesse, s], [w + groesse, s + groesse], [w, s + groesse], [w, s]]]
    if loch:
        lw, ls, lg = loch
        ringe.append([[lw, ls], [lw + lg, ls], [lw + lg, ls + lg], [lw, ls + lg], [lw, ls]])
    return {"type": "Polygon", "coordinates": ringe}


def test_punkt_in_polygon_mit_loch_und_multipolygon():
    g = _quadrat(7.0, 50.0, loch=(7.4, 50.4, 0.2))
    assert punkt_in(7.1, 50.1, g) and not punkt_in(7.5, 50.5, g) and not punkt_in(8.5, 50.5, g)
    multi = {
        "type": "MultiPolygon",
        "coordinates": [_quadrat(7, 50)["coordinates"], _quadrat(9, 50)["coordinates"]],
    }
    assert punkt_in(9.5, 50.5, multi) and not punkt_in(8.5, 50.5, multi)


def test_zuordnung_und_index():
    gem = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"ars": "071375001001", "name": "A"},
                "geometry": _quadrat(7.0, 50.0, 0.5),
            },
            {
                "type": "Feature",
                "properties": {"ars": "071375001002", "name": "B"},
                "geometry": _quadrat(7.5, 50.0, 0.5),
            },
            {
                "type": "Feature",
                "properties": {"ars": "071375001003", "name": "leer"},
                "geometry": None,
            },
        ],
    }
    z = Zuordnung(gem)
    assert z.ars(7.2, 50.2) == "071375001001" and z.ars(7.7, 50.2) == "071375001002"
    assert z.ars(6.0, 50.2) is None and z.ars(None, 50.0) is None and z.ars("x", 1) is None
    eintraege = index({"gemeinde": gem})
    assert [e["n"] for e in eintraege] == ["A", "B"]
    assert schluessel("kreis", "071375001001") == "07137"
    assert schluessel("vg", "071375001001") == "071375001"
