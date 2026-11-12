"""Atlas-Export lesen – synthetische Daten."""

import json

import pytest

from sportstaettenatlas.atlas import _liste, lage, lies_export

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


def _fake(a, b):  # Ersatz für pyproj: nachvollziehbar, aber ohne Geo-Bibliothek
    return {"lon": round(b / 1e5, 6), "lat": round(a / 1e5, 6)}


@pytest.fixture
def export(tmp_path):
    p = tmp_path / "sportstaetten_04112026.csv"
    p.write_text("\ufeff" + KOPF + ZEILEN, encoding="utf-8")
    return p


def test_export_lesen(export):
    d = next(lies_export(export, lage_aus=_fake))
    assert d["id"] == "101"
    assert d["lage"] == {"lon": 4.02742, "lat": 55.148053}
    assert d["oeffentlicher_zugang"] == "nein" and d["schulsport"] == "ja"
    assert d["zuschauerplaetze"] == 250
    assert d["sportarten"] == ["Fußball", "Leichtathletik"]
    assert d["anlagen"] == [{"typ": "Großspielfeld (ab 5.000 m², Rasen)"}, {"typ": "Rundlaufbahn"}]
    assert d["quellen"]["atlas_rlp"] == {"id": "101", "datei": export.name, "stand": "2026-11-04"}
    assert "vorstand@tus.example" not in json.dumps(d)  # E-Mail-Spalte wird nie gelesen
    halle = list(lies_export(export, lage_aus=_fake))[1]
    assert halle["lage"] is None


def test_kein_export(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="kein Atlas-Export"):
        list(lies_export(p))


def test_echte_umrechnung():
    pytest.importorskip("pyproj")
    g = lage(5578000, 398000)  # Koblenz, Hochwert/Rechtswert unter Latitude/Longitude
    assert 7.55 < g["lon"] < 7.6 and 50.33 < g["lat"] < 50.36
    assert lage(50.35, 7.59) == {"lon": 7.59, "lat": 50.35}  # schon Grad


def test_liste_haelt_anlagen_mit_bindestrich_zusammen():
    assert _liste("Großspielfeld, Weit-, Dreisprunganlage, Feld (A, B)") == [
        "Großspielfeld",
        "Weit-, Dreisprunganlage",
        "Feld (A, B)",
    ]
