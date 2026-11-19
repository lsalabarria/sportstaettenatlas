"""Sportstätten außerhalb von RLP (daten/outside/<Land>/) und die Prüfung „Baujahr“ –
synthetische Daten."""

import json

from sportstaettenatlas.bestand import einordnen, lies_bestand, lies_sportkomplexe
from sportstaettenatlas.seite import ohne_outside
from sportstaettenatlas.validate import baujahr, pruefe

DRIN = "11111111-1111-4111-8111-111111111111"
DRAUSSEN = "22222222-2222-4222-8222-222222222222"
KOMPLEX = "33333333-3333-4333-8333-333333333333"


def _schreibe(pfad, d):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(d), "utf-8")


def _daten(tmp_path):
    daten = tmp_path / "daten"
    _schreibe(
        daten / "RP" / "07111-koblenz" / DRIN / f"{DRIN}_meta.json",
        {"id": DRIN, "name": "Halle Koblenz", "lage": {"lon": 7.6, "lat": 50.35}},
    )
    _schreibe(
        daten / "outside" / "NW" / DRAUSSEN / f"{DRAUSSEN}_meta.json",
        {
            "id": DRAUSSEN,
            "name": "Halle Köln",
            "lage": {"lon": 6.95, "lat": 50.94},
            "adresse": {"plz": "50667", "ort": "Köln"},
            "sportkomplex": KOMPLEX,
        },
    )
    _schreibe(
        daten / "outside" / "NW" / "sportkomplexe" / f"{KOMPLEX}.json",
        {"id": KOMPLEX, "name": "Sportpark Köln"},
    )
    return daten


def test_outside_wird_gelesen_aber_nicht_einsortiert(tmp_path):
    daten = _daten(tmp_path)
    land = {d["id"]: (d["_land"], d["_ordner"]) for d in lies_bestand(daten)}
    assert land == {DRIN: ("RP", "07111-koblenz"), DRAUSSEN: ("outside", "NW")}
    assert [k["_land"] for k in lies_sportkomplexe(daten)] == ["outside"]
    assert einordnen(daten, lambda lon, lat: "07111-koblenz") == 0
    assert (daten / "outside" / "NW" / DRAUSSEN).is_dir()

    # die Grenzen der Lage gelten für Rheinland-Pfalz, nicht unter outside/
    berlin = {"id": DRAUSSEN, "name": "Halle Berlin", "kategorie": "Sporthalle",
              "lage": {"lon": 13.4, "lat": 52.52}}  # fmt: skip
    _schreibe(daten / "outside" / "NW" / DRAUSSEN / f"{DRAUSSEN}_meta.json", berlin)
    _schreibe(daten / "RP" / "07111-koblenz" / DRIN / f"{DRIN}_meta.json", {**berlin, "id": DRIN})
    verstoesse = []
    list(lies_bestand(daten, verstoesse))
    assert [(DRIN in d, m.split(":")[0]) for d, m in verstoesse] == [
        (True, "lage.lon"),
        (True, "lage.lat"),
    ]


def test_outside_ohne_pruefungen_des_landes(tmp_path):
    daten = _daten(tmp_path)
    bestand = list(lies_bestand(daten))
    gemeinden = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"ars": "071110000000", "name": "Koblenz"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[7.5, 50.3], [7.7, 50.3], [7.7, 50.4], [7.5, 50.4], [7.5, 50.3]]
                    ],
                },
            }
        ],
    }
    meldungen = pruefe(bestand, [], {"gemeinde": gemeinden}, daten)
    draussen = [(p, m) for datei, p, m in meldungen if DRAUSSEN in datei]
    assert not any(p in ("Ort", "Rheinland-Pfalz", "PLZ", "Kreis-Ordner") for p, _ in draussen)
    # ein Sportkomplex mit einer Sportstätte bleibt trotzdem auffällig
    assert any(p == "Kleiner Sportkomplex" for _, p, _ in meldungen)


def test_outside_nicht_auf_der_webseite(tmp_path):
    daten = _daten(tmp_path)
    stuetzpunkte = [
        {"id": "sp1", "name": "nur draußen", "sportstaetten": [DRAUSSEN]},
        {"id": "sp2", "name": "beides", "sportstaetten": [DRIN, DRAUSSEN]},
        {"id": "sp3", "name": "ohne Verweis"},
    ]
    bestand, komplexe, sp = ohne_outside(
        list(lies_bestand(daten)), lies_sportkomplexe(daten), stuetzpunkte
    )
    assert [d["id"] for d in bestand] == [DRIN]
    assert komplexe == []
    assert [(s["id"], s["sportstaetten"]) for s in sp] == [("sp2", [DRIN]), ("sp3", [])]


def test_baujahr():
    st = {
        "baujahr": 1990,
        "anlagen": [
            {"id": "a1", "baujahr": 1985},  # älter als die Sportstätte
            {"id": "a2", "baujahr": 1990},  # gleich: in Ordnung
            {"id": "a3", "baujahr": 2001},
            {"id": "a4"},  # ohne Jahr
        ],
    }
    assert list(baujahr(st)) == [
        ("a1", "baujahr: 1985 liegt vor dem Baujahr der Sportstätte (1990)")
    ]
    assert list(baujahr({"anlagen": [{"id": "a1", "baujahr": 1985}]})) == []
