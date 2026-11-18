"""Sportkomplexe: Ablage, Zuordnung, Einordnen und Prüfungen – synthetische Daten."""

import json

import pytest

from sportstaettenatlas.bestand import (
    einordnen,
    finde_staette,
    lies_bestand,
    lies_sportkomplexe,
    migriere_bestand,
    ordne_sportkomplex_zu,
    schreibe_bestand,
    schreibe_sportkomplex,
    sportkomplexe_einordnen,
)
from sportstaettenatlas.validate import pruefe

S1, S2, S3, S4, S5 = (f"{i}{i}{i}{i}{i}{i}{i}{i}-2222-4222-8222-222222222222" for i in range(1, 6))
K1, K2 = "aaaaaaaa-0000-4000-8000-000000000001", "aaaaaaaa-0000-4000-8000-000000000002"


def _st(sid, lon, lat, **mehr):
    return {
        "id": sid,
        "name": f"Halle {sid[:2]}",
        "kategorie": "Sporthalle",
        "lage": {"lon": lon, "lat": lat},
        "anlagen": [{"typ": "Einfachsporthalle"}],
        **mehr,
    }


def _kreis(lon, lat):
    return "07111-koblenz" if lon < 7.7 else "07141-rhein-lahn-kreis"


@pytest.fixture
def daten(tmp_path):
    d = tmp_path / "daten"
    bestand = [
        _st(S1, 7.6001, 50.3501, sportkomplex=K1),
        _st(S2, 7.6011, 50.3505, sportkomplex=K1),
        _st(S3, 7.6021, 50.3509),
        _st(S4, 7.6031, 50.3513, sportkomplex=K2),  # K2 allein: kleiner Komplex
        _st(
            S5, 7.6041, 50.3517, sportkomplex="bbbbbbbb-0000-4000-8000-000000000009"
        ),  # gibt es nicht
    ]
    schreibe_bestand(bestand, d, "RP", _kreis)
    schreibe_sportkomplex(d, {"id": K1, "name": "Sportzentrum Berg"}, "07111-koblenz")
    schreibe_sportkomplex(d, {"id": K2, "name": "Kleiner Komplex"}, "07111-koblenz")
    return d


def test_ablage_stoert_den_bestand_nicht(daten):
    assert (daten / "RP/07111-koblenz/sportkomplexe" / f"{K1}.json").exists()
    bestand = list(lies_bestand(daten))  # der Ordner sportkomplexe ist keine Sportstätte
    assert sorted(d["id"] for d in bestand) == sorted([S1, S2, S3, S4, S5])
    komplexe = lies_sportkomplexe(daten)
    assert [(k["name"], k["_ordner"]) for k in komplexe] == [
        ("Sportzentrum Berg", "07111-koblenz"),
        ("Kleiner Komplex", "07111-koblenz"),
    ]
    assert migriere_bestand(daten, probe=True).dateien == 0  # Reihenfolge stimmt schon


def test_zuordnen_und_entfernen(daten):
    assert finde_staette(daten, S3[:8]).name == S3
    ordne_sportkomplex_zu(daten, K1, [S3])
    meta = json.loads((finde_staette(daten, S3) / f"{S3}_meta.json").read_text())
    assert meta["sportkomplex"] == K1
    ordne_sportkomplex_zu(daten, None, [S3])
    meta = json.loads((finde_staette(daten, S3) / f"{S3}_meta.json").read_text())
    assert "sportkomplex" not in meta
    with pytest.raises(ValueError):
        finde_staette(daten, "1111")  # zu kurz


def test_einordnen_folgt_den_sportstaetten(daten):
    # ohne eigene Lage gehört der Komplex in den Kreis seiner Sportstätten
    for sid in (S1, S2):
        meta = finde_staette(daten, sid) / f"{sid}_meta.json"
        d = json.loads(meta.read_text())
        d["lage"] = {"lon": 7.8001, "lat": 50.3501}
        meta.write_text(json.dumps(d))
    assert einordnen(daten, _kreis) == 2
    assert sportkomplexe_einordnen(daten, _kreis) == 1
    assert (daten / "RP/07141-rhein-lahn-kreis/sportkomplexe" / f"{K1}.json").exists()
    assert not (daten / "RP/07111-koblenz/sportkomplexe" / f"{K1}.json").exists()
    # mit eigener Lage zählt die
    k = {"id": K2, "name": "Kleiner Komplex", "lage": {"lon": 7.8501, "lat": 50.3}}
    schreibe_sportkomplex(daten, k, "07111-koblenz")
    assert sportkomplexe_einordnen(daten, _kreis) == 1
    assert (daten / "RP/07141-rhein-lahn-kreis/sportkomplexe" / f"{K2}.json").exists()


def test_pruefungen(daten):
    bestand = list(lies_bestand(daten))
    meldungen = {(p, m) for _, p, m in pruefe(bestand, [], None, daten)}
    assert (
        "Sportkomplex",
        "sportkomplex: bbbbbbbb-0000-4000-8000-000000000009 gibt es nicht",
    ) in meldungen
    assert (
        "Kleiner Sportkomplex",
        "name: „Kleiner Komplex“ hat 1 Sportstätte – ein Sportkomplex braucht mindestens 2",
    ) in meldungen
    assert not any(p == "Ausdehnung des Sportkomplexes" for p, _ in meldungen)

    # weit verstreut; drei auf einer Koordinate im selben Komplex: eigene Meldung
    for sid in (S1, S2, S3):
        meta = finde_staette(daten, sid) / f"{sid}_meta.json"
        d = json.loads(meta.read_text())
        d["lage"] = {"lon": 7.6201, "lat": 50.3501}
        d["sportkomplex"] = K1
        meta.write_text(json.dumps(d))
    meta = finde_staette(daten, S4) / f"{S4}_meta.json"
    d = json.loads(meta.read_text())
    d["sportkomplex"] = K1
    meta.write_text(json.dumps(d))
    bestand = list(lies_bestand(daten))
    meldungen = [(p, m) for _, p, m in pruefe(bestand, [], None, daten)]
    assert (
        "Ausdehnung des Sportkomplexes",
        "lage: Sportstätten von „Sportzentrum Berg“ liegen bis zu 1214 m auseinander",
    ) in meldungen
    gleich = [m for p, m in meldungen if p == "Gleiche Koordinate"]
    assert len(gleich) == 3 and all("des Sportkomplexes „Sportzentrum Berg“" in m for m in gleich)
