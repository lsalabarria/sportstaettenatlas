"""Datenbestand (ein Ordner je Sportstätte, eine Datei je Sportanlage) – synthetische Daten."""

import json

import pytest

from sportstaettenatlas.bestand import (
    erkenne_format,
    lies_atlas_export,
    lies_bestand,
    schreibe_bestand,
    umstellen,
)

KOPF = (
    "ID,Name,Straße,Hausnummer,PLZ,Stadt,Sportstättenkategorie,Schulsport,"
    '"Öffentlicher Zugang","Zuschauerplätze Gesamt",Betriebsstatus,'
    '"Name des Eigentümers","Name des Betreibers",E-Mail,Webseite,Sportarten,'
    "Sportanlagen,Latitude,Longitude\n"
)
ZEILEN = (
    '101,"Sportplatz Musterdorf","Am Weg",1,11111,Musterdorf,Sportplatz,Ja,Nein,250,'
    '"in Betrieb","Ortsgemeinde Musterdorf","TuS Musterdorf",vorstand@tus.example,'
    'www.tus.example,"Fußball, Leichtathletik",'
    '"Großspielfeld (ab 5.000 m², Rasen), Rundlaufbahn",5514805.26,402741.96\n'
    '102,"Halle ohne Lage",,,11111,Musterdorf,Sporthalle,,,,,,,,,,Einfeldhalle,,\n'
    '103,"Reitplatz","Hof 2",,11111,Musterdorf,Reitsportstätte,,,,,'
    '"Kontakt: max@privat.example",,,,,Reitplatz,5515000.0,403000.0\n'
)


def _kreis(lon, lat):  # Ersatz für die Verwaltungsgebiete: westlich von 4.029 → Kreis A
    return "07111-kreis-a" if lon < 4.029 else "07137-kreis-b"


def _fake(x, y):  # Ersatz für pyproj: Umrechnung nachvollziehbar, aber ohne Geo-Bibliothek
    return round(x / 1e5, 6), round(y / 1e5, 6)


@pytest.fixture
def export(tmp_path):
    p = tmp_path / "sportstaetten_04112026.csv"
    p.write_text("﻿" + KOPF + ZEILEN, encoding="utf-8")
    return p


def test_atlas_export_lesen(export):
    assert erkenne_format(export) == "atlas-export"
    d = next(lies_atlas_export(export, "RP", umrechnen=_fake))
    assert d["id"] == "101"
    assert d["lage"] == {"lon": 4.027420, "lat": 55.148053}  # Latitude/Longitude waren UTM
    assert d["oeffentlicher_zugang"] == "nein" and d["schulsport"] == "ja"
    assert d["zuschauerplaetze"] == 250
    assert d["sportarten"] == ["Fußball", "Leichtathletik"]
    # einheitlicher Typ; die Schreibweise des Atlas bleibt als Quelle erhalten
    assert d["anlagen"] == [
        {
            "typ": "Großspielfeld (ab 5.000 m², Rasen)",
        },
        {"typ": "Rundlaufbahn"},
    ]
    assert d["quellen"]["atlas_rlp"] == {"id": "101", "datei": export.name, "stand": "2026-11-04"}
    assert "vorstand@tus.example" not in json.dumps(d)  # E-Mail-Spalte wird nie gelesen


def _lies(pfad):
    return json.loads(pfad.read_text(encoding="utf-8"))


def test_ordner_je_sportstaette(export, tmp_path):
    ziel = tmp_path / "daten"
    e = schreibe_bestand(lies_atlas_export(export, "RP", umrechnen=_fake), ziel, "RP", _kreis)
    assert (e.neu, e.ohne_lage) == (2, 1)
    assert e.entfernt == {"eigentuemer": 1}  # Wert mit E-Mail-Adresse fliegt raus
    ordner = ziel / "RP" / "07111-kreis-a" / "101"
    meta = _lies(ordner / "101_meta.json")
    assert "anlagen" not in meta and "hausnummer" in meta["adresse"] and meta["id"] == "101"
    anlagen = [_lies(p) for p in sorted(ordner.glob("*.json")) if p.name != "101_meta.json"]
    assert sorted(a["typ"] for a in anlagen) == [
        "Großspielfeld (ab 5.000 m², Rasen)",
        "Rundlaufbahn",
    ]
    for a, pfad in zip(anlagen, sorted(p for p in ordner.glob("*.json") if "_meta" not in p.name)):
        assert a["sportstaette_id"] == "101" and pfad.stem == a["id"]
    reit = _lies(ziel / "RP" / "07137-kreis-b" / "103" / "103_meta.json")
    assert "eigentuemer" not in reit and "betriebsstatus" not in reit  # leer → weggelassen

    # Lesen setzt Sportstätte und Anlagen wieder zusammen
    b = {d["id"]: d for d in lies_bestand(ziel)}
    assert set(b) == {"101", "103"} and len(b["101"]["anlagen"]) == 2

    # von Hand gepflegt: Modus "neu" lässt den Ordner in Ruhe
    meta["name"] = "Sportpark Musterdorf"
    (ordner / "101_meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    e = schreibe_bestand(lies_atlas_export(export, "RP", umrechnen=_fake), ziel, "RP", _kreis)
    assert (e.neu, e.behalten) == (0, 2)
    assert _lies(ordner / "101_meta.json")["name"] == "Sportpark Musterdorf"

    # "aktualisieren" übernimmt den Stand der Quelle; gleiche IDs der Anlagen
    ids = sorted(p.name for p in ordner.glob("*.json"))
    e = schreibe_bestand(
        lies_atlas_export(export, "RP", umrechnen=_fake), ziel, "RP", _kreis, modus="aktualisieren"
    )
    assert (e.aktualisiert, e.unveraendert) == (1, 1)
    assert _lies(ordner / "101_meta.json")["name"] == "Sportplatz Musterdorf"
    assert sorted(p.name for p in ordner.glob("*.json")) == ids

    # Sportstätte, die nicht (mehr) in der Quelle steht, wird gezählt, nicht gelöscht
    (ziel / "RP" / "07111-kreis-a" / "999").mkdir()
    e = schreibe_bestand(lies_atlas_export(export, "RP", umrechnen=_fake), ziel, "RP", _kreis)
    assert e.nicht_mehr_in_quelle == 1 and (ziel / "RP" / "07111-kreis-a" / "999").exists()


def test_jede_anlage_braucht_ihre_sportstaette(tmp_path):
    st = tmp_path / "RP" / "07111-koblenz" / "abc"
    st.mkdir(parents=True)
    (st / "abc_meta.json").write_text('{"id": "abc", "lage": {"lon": 7, "lat": 50}}', "utf-8")
    (st / "a1.json").write_text(
        '{"id": "a1", "sportstaette_id": "xyz", "typ": "Tennisplatz"}', "utf-8"
    )
    with pytest.raises(ValueError, match="im Ordner ihrer Sportstätte"):
        list(lies_bestand(tmp_path))
    (st / "a1.json").write_text(
        '{"id": "a1", "sportstaette_id": "abc", "typ": "Tennisplatz"}', "utf-8"
    )
    assert [a["typ"] for a in next(lies_bestand(tmp_path))["anlagen"]] == ["Tennisplatz"]
    # Ordner ohne Sportstätte
    (tmp_path / "RP" / "07111-koblenz" / "def").mkdir()
    (tmp_path / "RP" / "07111-koblenz" / "def" / "a2.json").write_text('{"id": "a2"}', "utf-8")
    with pytest.raises(ValueError, match="ohne Sportstätte"):
        list(lies_bestand(tmp_path))


def test_umstellen_aus_altem_format(tmp_path):
    alt = {
        "id": "RP-9c24bfa6-71c1-4164-b226-061f0a139997",
        "name": "Sportplatz",
        "lage": {"lon": 7.0, "lat": 50.0},
        "anlagen": [
            {"bezeichnung": "Großspielfeld (ab 5.000 m²)"},
            {"bezeichnung": "Weit-"},  # früher getrennt eingelesen
            {"bezeichnung": "Dreisprunganlage"},
            {"bezeichnung": "Tennisplatz"},
            {"bezeichnung": "Tennisplatz"},
        ],
    }
    (tmp_path / "RP").mkdir()
    (tmp_path / "RP" / "RP-9c24bfa6-71c1-4164-b226-061f0a139997.json").write_text(
        json.dumps(alt), "utf-8"
    )
    with pytest.raises(ValueError, match="umstellen"):
        list(lies_bestand(tmp_path))
    u = umstellen(tmp_path, lambda lon, lat: "07111-koblenz")
    assert (u.umgestellt, u.anlagen, u.verschoben) == (1, 4, 0)
    assert not list((tmp_path / "RP").glob("*.json"))
    assert (tmp_path / "RP" / "07111-koblenz" / alt["id"].removeprefix("RP-")).is_dir()
    d = next(lies_bestand(tmp_path))
    assert d["id"] == "9c24bfa6-71c1-4164-b226-061f0a139997" and d["name"] == "Sportplatz"
    typen = sorted(a["typ"] for a in d["anlagen"])
    assert typen == ["Großspielfeld", "Tennisplatz", "Tennisplatz", "Weit- und Dreisprunganlage"]
    gross = next(a for a in d["anlagen"] if a["typ"] == "Großspielfeld")
    assert gross["quellen"] == {"atlas_rlp": {"bezeichnung": "Großspielfeld (ab 5.000 m²)"}}
    assert len({a["id"] for a in d["anlagen"]}) == 4  # zwei Tennisplätze, zwei IDs


def test_unbekanntes_format(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Format nicht erkannt"):
        erkenne_format(p)


def test_echte_umrechnung():
    pytest.importorskip("pyproj")
    from sportstaettenatlas.bestand import utm32_nach_wgs84

    lon, lat = utm32_nach_wgs84(398000, 5578000)  # Koblenz
    assert 7.55 < lon < 7.6 and 50.33 < lat < 50.36


def test_betreiber_art():
    from sportstaettenatlas.bestand import betreiber_art

    assert betreiber_art("TuS Koblenz 1911 e.V.") == "Verein"
    assert betreiber_art("Turnverein Ortsgemeinde X") == "Verein"
    assert betreiber_art("Ortsgemeinde Musterdorf") == "Kommune"
    assert betreiber_art("Stadt Mainz") == "Kommune"
    assert betreiber_art("Kreisverwaltung Mayen-Koblenz") == "Kommune"
    assert betreiber_art("Fitness GmbH") == "sonstige"
    assert betreiber_art("  ") is None and betreiber_art(None) is None


def test_liste_haelt_anlagen_mit_bindestrich_zusammen():
    from sportstaettenatlas.bestand import _liste

    assert _liste("Großspielfeld, Weit-, Dreisprunganlage, Feld (A, B)") == [
        "Großspielfeld",
        "Weit-, Dreisprunganlage",
        "Feld (A, B)",
    ]


def test_anlagentypen():
    from sportstaettenatlas import anlagen

    assert anlagen.typ(" Nichtnormiertes  Spielfeld") == "Nicht normiertes Spielfeld"
    assert anlagen.typ("Dreifach-Sporthalle (Größe V)") == "Dreifachsporthalle"
    assert anlagen.typ("Kunsteisbahn") == "Kunsteisbahn"  # unbekannt: bleibt
    assert anlagen.gruppe("Rundlaufbahn") == "leichtathletik"
    assert anlagen.gruppe("Kunsteisbahn") == "winter"  # über Stichwort
    assert anlagen.gruppe("Irgendwas") == "weitere"
    assert anlagen.zusammenfuegen(["Diskus-", "Hammerwurfanlage", "Feld"]) == [
        "Diskus-, Hammerwurfanlage",
        "Feld",
    ]


def test_bestand_geojson_mit_anlagen():
    from sportstaettenatlas.bestand import bestand_geojson

    d = {
        "id": "abc",
        "lage": {"lon": 7.0, "lat": 50.0},
        "anlagen": [
            {"id": "11111111-x", "typ": "Tennisplatz"},
            {"id": "22222222-x", "typ": "Rundlaufbahn", "baujahr": 1980, "sportarten": []},
            {"id": "33333333-x", "typ": "Großspielfeld", "bezeichnung": "Kunstrasen B"},
        ],
    }
    fc = bestand_geojson([d])
    # nach Gruppe sortiert: Spielfelder, Tennis, Leichtathletik; leere Angaben entfallen
    assert fc["features"][0]["properties"]["anlagen"] == [
        ["Großspielfeld", "33333333", "Kunstrasen B"],
        ["Tennisplatz", "11111111"],
        ["Rundlaufbahn", "22222222", "", {"baujahr": 1980}],
    ]
    assert fc["anlagentypen"]["Rundlaufbahn"] == "leichtathletik"
    assert ["bad", "Bäder"] in fc["anlagengruppen"]


def test_umstellen_ordnet_nach_kreis(tmp_path):
    from sportstaettenatlas.bestand import falsch_einsortiert

    # Ordner einer Sportstätte ohne Kreis-Ebene (Zwischenstand) und einer im falschen Kreis
    for pfad, sid in ((tmp_path / "RP" / "s1", "s1"), (tmp_path / "RP" / "07111-a" / "s2", "s2")):
        pfad.mkdir(parents=True)
        (pfad / f"{sid}_meta.json").write_text(
            json.dumps({"id": sid, "lage": {"lon": 7.5, "lat": 50.0}}), "utf-8"
        )
        (pfad / "a1.json").write_text(
            json.dumps({"id": "a1", "sportstaette_id": sid, "typ": "Tennisplatz"}), "utf-8"
        )
    with pytest.raises(ValueError, match="umstellen"):
        list(lies_bestand(tmp_path))
    u = umstellen(tmp_path, lambda lon, lat: "07137-b")
    assert u.verschoben == 2 and not (tmp_path / "RP" / "07111-a").exists()  # leer → weg
    bestand = list(lies_bestand(tmp_path))
    assert {d["_ordner"] for d in bestand} == {"07137-b"}
    assert falsch_einsortiert(bestand, lambda lon, lat: "07137-b") == []
    assert falsch_einsortiert(bestand, lambda lon, lat: "07111-a")[0] == (
        "s1",
        "07137-b",
        "07111-a",
    )
    assert umstellen(tmp_path, lambda lon, lat: "07137-b").verschoben == 0  # nichts mehr zu tun


def test_kreis_ordner():
    from sportstaettenatlas.bestand import kreis_ordner

    def flaeche(ars, name, bez, w, o):
        return {
            "type": "Feature",
            "properties": {"ars": ars, "name": name, "bez": bez},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[w, 49.0], [o, 49.0], [o, 50.0], [w, 50.0], [w, 49.0]]],
            },
        }

    gebiete = {
        "kreis": {
            "features": [
                flaeche("07312", "Kaiserslautern", "Kreisfreie Stadt", 7.0, 7.5),
                flaeche("07335", "Kaiserslautern", "Landkreis", 7.5, 8.0),
            ]
        },
        "gemeinde": {
            "features": [
                flaeche("073120000000", "Kaiserslautern", "Stadt", 7.0, 7.5),
                flaeche("073355001001", "Südort", "Ortsgemeinde", 7.5, 8.0),
            ]
        },
    }
    k = kreis_ordner(gebiete)
    assert k(7.2, 49.5) == "07312-kaiserslautern-stadt"
    assert k(7.7, 49.5) == "07335-kaiserslautern"
    assert k(9.0, 49.5) == "ohne-kreis"


def test_readme_des_datenbestands(tmp_path):
    from sportstaettenatlas.bestand import README_DATEN, schreibe_readme

    assert README_DATEN.startswith("# Datenbestand") and "sportstaette_id" in README_DATEN
    assert schreibe_readme(tmp_path) and not schreibe_readme(tmp_path)  # nur bei Änderung
    (tmp_path / "README.md").write_text("alt", encoding="utf-8")
    assert schreibe_readme(tmp_path)
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == README_DATEN
