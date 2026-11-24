"""Datenbestand (Kreis / Sportstätte / Sportanlagen) – synthetische Daten."""

import json

import pytest

from sportstaettenatlas.bestand import einordnen, lies_bestand, schreibe_bestand
from sportstaettenatlas.pflege.atlas_export import lies_export

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


def _fake(a, b):
    return {"lon": round(b / 1e5, 6), "lat": round(a / 1e5, 6)}


def _kreis(lon, lat):  # Ersatz für die Verwaltungsgebiete: westlich von 4.029 → Kreis A
    return "07111-kreis-a" if lon < 4.029 else "07137-kreis-b"


@pytest.fixture
def export(tmp_path):
    p = tmp_path / "sportstaetten_04112026.csv"
    p.write_text(KOPF + ZEILEN, encoding="utf-8")
    return p


def _lies(pfad):
    return json.loads(pfad.read_text(encoding="utf-8"))


def test_ordner_je_sportstaette(export, tmp_path):
    ziel = tmp_path / "daten"
    e = schreibe_bestand(lies_export(export, lage_aus=_fake), ziel, "RP", _kreis)
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
    for a, pfad in zip(
        anlagen, sorted(p for p in ordner.glob("*.json") if "_meta" not in p.name), strict=True
    ):
        assert "sportstaette_id" not in a and pfad.stem == a["id"]  # die Sportstätte: der Ordner
    reit = _lies(ziel / "RP" / "07137-kreis-b" / "103" / "103_meta.json")
    assert "eigentuemer" not in reit and "betriebsstatus" not in reit  # leer → weggelassen

    # Lesen setzt Sportstätte und Anlagen wieder zusammen
    b = {d["id"]: d for d in lies_bestand(ziel)}
    assert set(b) == {"101", "103"} and len(b["101"]["anlagen"]) == 2

    # von Hand gepflegt: Modus "neu" lässt den Ordner in Ruhe
    meta["name"] = "Sportpark Musterdorf"
    (ordner / "101_meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    e = schreibe_bestand(lies_export(export, lage_aus=_fake), ziel, "RP", _kreis)
    assert (e.neu, e.behalten) == (0, 2)
    assert _lies(ordner / "101_meta.json")["name"] == "Sportpark Musterdorf"

    # "aktualisieren" übernimmt den Stand der Quelle; gleiche IDs der Anlagen
    ids = sorted(p.name for p in ordner.glob("*.json"))
    e = schreibe_bestand(
        lies_export(export, lage_aus=_fake), ziel, "RP", _kreis, modus="aktualisieren"
    )
    assert (e.aktualisiert, e.unveraendert) == (1, 1)
    assert _lies(ordner / "101_meta.json")["name"] == "Sportplatz Musterdorf"
    assert sorted(p.name for p in ordner.glob("*.json")) == ids

    # Sportstätte, die nicht (mehr) in der Quelle steht, wird gezählt, nicht gelöscht
    (ziel / "RP" / "07111-kreis-a" / "999").mkdir()
    e = schreibe_bestand(lies_export(export, lage_aus=_fake), ziel, "RP", _kreis)
    assert e.nicht_mehr_in_quelle == 1 and (ziel / "RP" / "07111-kreis-a" / "999").exists()


def test_jede_anlage_braucht_ihre_sportstaette(tmp_path):
    st = tmp_path / "RP" / "07111-koblenz" / "abc"
    st.mkdir(parents=True)
    (st / "abc_meta.json").write_text('{"id": "abc", "lage": {"lon": 7, "lat": 50}}', "utf-8")
    (st / "a1.json").write_text('{"id": "a1", "typ": "Tennisplatz"}', "utf-8")
    assert [a["typ"] for a in next(lies_bestand(tmp_path))["anlagen"]] == ["Tennisplatz"]
    # das frühere Feld sportstaette_id meldet das Modell (uv run sportstaettenatlas migrieren)
    (st / "a1.json").write_text(
        '{"id": "a1", "sportstaette_id": "abc", "typ": "Tennisplatz"}', "utf-8"
    )
    verstoesse = []
    list(lies_bestand(tmp_path, verstoesse))
    assert [m.split(":")[0] for _, m in verstoesse if "a1.json" in _] == ["sportstaette_id"]
    # Ordner ohne Sportstätte
    (tmp_path / "RP" / "07111-koblenz" / "def").mkdir()
    (tmp_path / "RP" / "07111-koblenz" / "def" / "a2.json").write_text('{"id": "a2"}', "utf-8")
    with pytest.raises(ValueError, match="ohne Sportstätte"):
        list(lies_bestand(tmp_path))


def test_einordnen(tmp_path):
    from sportstaettenatlas.bestand import falsch_einsortiert

    pfad = tmp_path / "RP" / "07111-a" / "s1"
    pfad.mkdir(parents=True)
    (pfad / "s1_meta.json").write_text(
        json.dumps({"id": "s1", "lage": {"lon": 7.5, "lat": 50.0}}), "utf-8"
    )
    (pfad / "a1.json").write_text(json.dumps({"id": "a1", "typ": "Tennisplatz"}), "utf-8")
    bestand = list(lies_bestand(tmp_path))
    assert falsch_einsortiert(bestand, lambda lon, lat: "07137-b") == [("s1", "07111-a", "07137-b")]
    assert einordnen(tmp_path, lambda lon, lat: "07137-b") == 1
    assert not (tmp_path / "RP" / "07111-a").exists()  # leer geworden → entfernt
    assert [d["_ordner"] for d in lies_bestand(tmp_path)] == ["07137-b"]
    assert einordnen(tmp_path, lambda lon, lat: "07137-b") == 0


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


def test_anlagentypen():
    from sportstaettenatlas.modell import anlagen

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


def test_aendern_mit_id_und_einzelnen_feldern(tmp_path):
    """Eine Zeile mit der ID (auch der Kurz-ID) und nur den Feldern, die sich ändern."""
    from sportstaettenatlas.pflege.einlesen import lies_csv

    sid = "11111111-1111-4111-8111-111111111111"
    staette = {
        "id": sid,
        "name": "Platz",
        "kategorie": "Sportplatz",
        "lage": {"lon": 7.6, "lat": 50.35},
        "adresse": {"strasse": "Am Weg", "hausnummer": "1", "plz": "56068", "ort": "Koblenz"},
        "anlagen": [{"typ": "Tennisplatz"}],
    }
    kreis = lambda lon, lat: "07111-koblenz"
    schreibe_bestand([staette], tmp_path, "RP", kreis)
    tabelle = tmp_path / "aenderung.csv"
    tabelle.write_text(f"id;hausnummer\n{sid[:8]};2\n99999999;5\n", "utf-8")
    d, _ = lies_csv(tabelle)
    e = schreibe_bestand(d, tmp_path, "RP", kreis, modus="ergaenzen")
    assert (e.aktualisiert, e.unveraendert, e.unbekannt) == (0, 1, 1)  # ergaenzen: 1 bleibt
    e = schreibe_bestand(d, tmp_path, "RP", kreis, modus="aktualisieren")
    assert (e.aktualisiert, e.neu, e.unbekannt) == (1, 0, 1)
    [x] = lies_bestand(tmp_path)
    assert x["adresse"] == {
        "strasse": "Am Weg",
        "hausnummer": "2",
        "plz": "56068",
        "ort": "Koblenz",
    }
    assert len(x["anlagen"]) == 1 and x["name"] == "Platz"
