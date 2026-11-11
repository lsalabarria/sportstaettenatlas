"""Datenbestand (eine JSON-Datei je Sportstätte) – synthetische Daten."""

import json

import pytest

from sportstaettenatlas.bestand import erkenne_format, lies_atlas_export, schreibe_bestand

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
    assert d["id"] == "RP-101"
    assert d["lage"] == {"lon": 4.027420, "lat": 55.148053}  # Latitude/Longitude waren UTM
    assert d["oeffentlicher_zugang"] == "nein" and d["schulsport"] == "ja"
    assert d["zuschauerplaetze"] == 250
    assert d["sportarten"] == ["Fußball", "Leichtathletik"]
    assert d["anlagen"] == [
        {"bezeichnung": "Großspielfeld (ab 5.000 m², Rasen)"},
        {"bezeichnung": "Rundlaufbahn"},
    ]
    assert d["quellen"]["atlas_rlp"] == {"id": "101", "datei": export.name, "stand": "2026-11-04"}
    assert "vorstand@tus.example" not in json.dumps(d)  # E-Mail-Spalte wird nie gelesen


def test_schreiben_und_modi(export, tmp_path):
    ziel = tmp_path / "daten"
    e = schreibe_bestand(lies_atlas_export(export, "RP", umrechnen=_fake), ziel, "RP")
    assert (e.neu, e.ohne_lage) == (2, 1)
    assert e.entfernt == {"eigentuemer": 1}  # Wert mit E-Mail-Adresse fliegt raus
    datei = ziel / "RP" / "RP-101.json"
    d = json.loads(datei.read_text(encoding="utf-8"))
    assert "hausnummer" in d["adresse"] and "kategorie" in d
    reit = json.loads((ziel / "RP" / "RP-103.json").read_text(encoding="utf-8"))
    assert "eigentuemer" not in reit and "betriebsstatus" not in reit  # leer → weggelassen

    # von Hand gepflegt: Modus "neu" lässt die Datei in Ruhe
    d["name"] = "Sportpark Musterdorf"
    datei.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    e = schreibe_bestand(lies_atlas_export(export, "RP", umrechnen=_fake), ziel, "RP")
    assert (e.neu, e.behalten) == (0, 2)
    assert json.loads(datei.read_text(encoding="utf-8"))["name"] == "Sportpark Musterdorf"

    # "aktualisieren" übernimmt den Stand der Quelle
    e = schreibe_bestand(
        lies_atlas_export(export, "RP", umrechnen=_fake), ziel, "RP", modus="aktualisieren"
    )
    assert (e.aktualisiert, e.unveraendert) == (1, 1)
    assert json.loads(datei.read_text(encoding="utf-8"))["name"] == "Sportplatz Musterdorf"

    # Datei, die nicht (mehr) in der Quelle steht, wird gezählt, nicht gelöscht
    (ziel / "RP" / "RP-999.json").write_text("{}", encoding="utf-8")
    e = schreibe_bestand(lies_atlas_export(export, "RP", umrechnen=_fake), ziel, "RP")
    assert e.nicht_mehr_in_quelle == 1 and (ziel / "RP" / "RP-999.json").exists()


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
