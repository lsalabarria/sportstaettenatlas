"""Datenmodell (modell.py): Regeln, Reihenfolge in den Dateien, Schema, Doku."""

import json
import re
from pathlib import Path

import pytest

from sportstaettenatlas import modell
from sportstaettenatlas.bestand import aufteilen, lies_bestand, schreibe_bestand

# synthetisch, im Aufbau wie eine Datei aus daten/
STAETTE = {
    "id": "11111111-1111-4111-8111-111111111111",
    "name": "Sportplatz Musterdorf",
    "kategorie": "Sportplatz",
    "adresse": {"strasse": "Am Weg", "hausnummer": "1", "plz": "56068", "ort": "Musterdorf"},
    "lage": {"lon": 7.5938, "lat": 50.3512},
    "oeffentlicher_zugang": "ja",
    "schulsport": "nein",
    "betriebsstatus": "in Betrieb",
    "sportarten": ["Fußball"],
}


def test_gueltige_sportstaette():
    assert modell.pruefe(modell.Sportstaette, STAETTE) == []
    assert modell.pruefe(modell.Sportanlage, {"typ": "Großspielfeld", "baujahr": 1998}) == []


def test_regelverstoesse_lesbar():
    falsch = {
        **STAETTE,
        "kategorie": "Bolzwiese",
        "adresse": {"plz": "535474", "hausnummer": "02. Apr"},
        "lage": {"lon": 7.5, "lat": 60},
        "website": "www.example.org",
        "zuschauerplaetze": -1,
        "farbe": "blau",
    }
    m = modell.pruefe(modell.Sportstaette, falsch)
    felder = {x.split(":")[0] for x in m}
    assert felder == {
        "kategorie",
        "adresse.plz",
        "adresse.hausnummer",
        "lage.lat",
        "website",
        "zuschauerplaetze",
        "farbe",
    }
    assert "adresse.plz: Format passt nicht: 535474" in m
    assert "farbe: unbekanntes Feld" in m
    assert modell.pruefe(modell.Sportanlage, {"typ": ""}) == ["typ: leer"]


def test_reihenfolge_in_den_dateien():
    """Dateien entstehen in der Reihenfolge des Modells, unabhängig von der Eingabe."""
    gemischt = dict(reversed(list(STAETTE.items())))
    gemischt["anlagen"] = [{"baujahr": 1998, "typ": "Großspielfeld"}]
    dateien = aufteilen(gemischt)
    meta = json.loads(dateien[f"{STAETTE['id']}_meta.json"])
    assert list(meta) == [f for f in modell.Sportstaette.model_fields if f in STAETTE]
    assert list(meta["adresse"]) == ["strasse", "hausnummer", "plz", "ort"]
    (anlage,) = [json.loads(t) for n, t in dateien.items() if not n.endswith("_meta.json")]
    assert list(anlage) == ["id", "typ", "baujahr"]


def test_lies_bestand_meldet_verstoesse_ohne_abbruch(tmp_path):
    falsch = {**STAETTE, "adresse": {"plz": "123"}}
    schreibe_bestand([falsch], tmp_path, "rp", lambda lon, lat: "07111-koblenz")
    verstoesse = []
    (d,) = lies_bestand(tmp_path, verstoesse)
    assert d["adresse"]["plz"] == "123"  # Wert bleibt, wie er ist
    assert [m for _, m in verstoesse] == ["adresse.plz: Format passt nicht: 123"]
    assert verstoesse[0][0].endswith("_meta.json")


def test_atlas_export_nutzt_nur_felder_des_modells():
    from sportstaettenatlas import atlas

    d = next(atlas.lies_export(_export(), lage_aus=lambda a, b: {"lon": b, "lat": a}))
    assert set(d) <= set(modell.Sportstaette.model_fields)
    assert set(d["adresse"]) <= set(modell.Adresse.model_fields)
    for a in d["anlagen"]:
        assert set(a) <= set(modell.Sportanlage.model_fields)


def _export(tmp=Path(__file__).parent):
    pfad = tmp / "_export_modell.csv"
    pfad.write_text(
        "ID;Name;Sportstättenkategorie;Latitude;Longitude;Straße;Hausnummer;PLZ;Stadt;"
        "Sportanlagen;Sportarten;Öffentlicher Zugang;Schulsport;Zuschauerplätze Gesamt;"
        "Betriebsstatus;Name des Eigentümers;Name des Betreibers;Webseite\n"
        "abc;Platz;Sportplatz;50,35;7,59;Am Weg;1;56068;Musterdorf;Großspielfeld;Fußball;"
        "ja;nein;100;in Betrieb;Gemeinde;TuS;https://example.org\n",
        encoding="utf-8",
    )
    return pfad


@pytest.fixture(autouse=True)
def _aufraeumen():
    yield
    (Path(__file__).parent / "_export_modell.csv").unlink(missing_ok=True)


def test_schema_fuer_die_webseite():
    s = modell.schema()
    st = s["$defs"]["Sportstaette"]
    assert st["required"] == ["name", "kategorie", "lage"]
    assert st["gruppen"][0] == "Sportstätte"
    assert st["properties"]["sportarten"]["widget"] == "chips"
    assert "quellen" not in st["properties"]
    assert "Sportplatz" in st["properties"]["kategorie"]["enum"]
    # jedes Feld im Formular hat eine Beschriftung und eine bekannte Gruppe
    for p in st["properties"].values():
        assert p["title"]
        if p.get("formular") is not False:
            assert p["gruppe"] in modell.GRUPPEN
    json.dumps(s)


@pytest.mark.parametrize(
    "daten, fehler",
    [
        ({"art": "neu", "sportstaette": STAETTE, "anlagen": [{"typ": "Großspielfeld"}]}, False),
        ({"art": "aenderung", "sportstaette_id": "x", "sportstaette": STAETTE}, False),
        (
            {"art": "anlagen", "sportstaette_id": "x", "anlagen": [], "entfernte_anlagen": ["1"]},
            False,
        ),
        ({"art": "anlagen", "anlagen": []}, True),  # welche Sportstätte?
        ({"art": "neu", "sportstaette": STAETTE}, True),  # Anlagen fehlen
        ({"art": "loeschen", "sportstaette_id": "x"}, True),
    ],
)
def test_vorschlag(daten, fehler):
    assert bool(modell.pruefe(modell.Vorschlag, daten)) is fehler


def test_readme_block(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Datenbestand\n\nText davor.\n", encoding="utf-8")
    assert modell.aktualisiere_readme(readme)
    text = readme.read_text("utf-8")
    assert text.startswith("# Datenbestand\n\nText davor.")
    assert "| `plz` | PLZ | Text |" in text and "datenmodell.svg" in text
    assert not modell.aktualisiere_readme(readme)  # zweiter Lauf: nichts zu tun
    readme.write_text(text.replace("| `plz` | PLZ", "| `plz` | Postleitzahl"), "utf-8")
    assert modell.aktualisiere_readme(readme)  # Handänderung im Block wird ersetzt
    assert readme.read_text("utf-8") == text


def test_readme_im_repository_ist_aktuell():
    """daten/README.md muss zum Modell passen: sonst `sportstaettenatlas modell` ausführen."""
    pfad = Path(__file__).parents[1] / "daten" / "README.md"
    if not pfad.exists():
        pytest.skip("kein daten/README.md")
    assert modell.readme_block() in pfad.read_text("utf-8"), (
        "daten/README.md passt nicht zum Modell – `uv run sportstaettenatlas modell` ausführen"
    )


def test_regeln_zwischen_feldern():
    anlage = {"typ": "Großspielfeld", "baukosten": 1_200_000, "sportarten": ["Fußball"]}
    assert modell.pruefe(modell.Sportanlage, {**anlage, "waehrung": "DM"}) == []
    assert modell.pruefe(modell.Sportanlage, anlage) == [
        "waehrung: nötig, wenn Baukosten angegeben ist"
    ]
    assert modell.pruefe(
        modell.Sportanlage, {**anlage, "waehrung": "€", "wettkampf": ["Rugby"]}
    ) == ["wettkampf: Rugby fehlt unter Sportarten"]
    assert modell.pruefe(modell.Sportstaette, {**STAETTE, "betreiber_typ": "Zweckverband"}) == [
        "betreiber: nötig, wenn Art des Betreibers angegeben ist"
    ]


def test_anzahl_je_wert():
    a = {"typ": "Tennisplatz", "felder_je_belag": {"Sand": 3, "Rasen": 1}}
    assert modell.pruefe(modell.Sportanlage, a) == []
    assert list(modell.ordne(a, modell.Sportanlage)["felder_je_belag"]) == ["Rasen", "Sand"]
    assert modell.pruefe(modell.Sportanlage, {**a, "felder_je_belag": {"Holz": 1}}) == [
        "felder_je_belag.Holz: nicht in der Auswahl: Holz"
    ]


def test_merkmale_je_anlagentyp():
    from sportstaettenatlas import anlagen

    felder = set(modell.Sportanlage.model_fields)
    assert set(modell.MERKMALE_ALLE) <= felder
    for typen, fs in modell.MERKMALE:
        assert set(fs) <= felder, set(fs) - felder
        for t in typen:
            assert t in anlagen.GRUPPE_VON, t
    assert "Tennisplatz" in modell.fuer_von("felder_je_belag")
    assert "Großspielfeld" not in modell.fuer_von("felder_je_belag")
    assert modell.fuer_von("flutlicht") is None  # für alle Typen
    assert modell.fuer_von("barrierefrei_erreichbar") is None
    assert set(modell.fuer_von("sprungturm")) == set(anlagen.GRUPPEN["bad"][1])
    # im Schema für die Webseite
    p = modell.schema()["$defs"]["Sportanlage"]["properties"]
    assert p["hoehe"]["fuer"] == modell.fuer_von("hoehe") and "fuer" not in p["baujahr"]


def test_angaben_der_anlagenfelder():

    for name, feld in modell.Sportanlage.model_fields.items():
        extra = feld.json_schema_extra or {}
        if extra.get("formular") is False:
            continue
        assert extra.get("gruppe") in modell.ANLAGE_GRUPPEN, name
        assert "fuer" not in extra, name  # folgt aus MERKMALE


def test_migrieren(tmp_path):
    import pytest

    from sportstaettenatlas.bestand import migriere_bestand

    ordner = tmp_path / "RP" / "07111-koblenz" / STAETTE["id"]
    ordner.mkdir(parents=True)
    staette = {**STAETTE, "quellen": {"atlas_rlp": {"stand": "2026-11-04"}}}
    (ordner / f"{STAETTE['id']}_meta.json").write_text(json.dumps(staette), "utf-8")
    alt = {"id": "a1", "sportstaette_id": STAETTE["id"], "typ": "Großspielfeld", "kosten": 5}
    alt["waehrung"] = "€"
    alt["quellen"] = {"atlas_rlp": {"bezeichnung": "Großspielfeld (Rasen)"}}
    (ordner / "a1.json").write_text(json.dumps(alt), "utf-8")
    beide = {"id": "a2", "sportstaette_id": STAETTE["id"], "typ": "Halle", "kosten": 1}
    (ordner / "a2.json").write_text(json.dumps({**beide, "baukosten": 2}), "utf-8")
    org = tmp_path / "organisationen" / "o1.json"
    org.parent.mkdir()
    org.write_text(json.dumps({"name": "TuS", "id": "o1", "quellen": {}}), "utf-8")

    with pytest.raises(ValueError, match="nicht im Modell"):
        migriere_bestand(tmp_path, {"kosten": "gibtsnicht"})
    vorher = (ordner / "a1.json").read_text("utf-8")
    weg = {"quellen", "sportstaette_id"}  # sportstaette_id: früher in jeder Sportanlage
    probe = migriere_bestand(tmp_path, {"kosten": "baukosten"}, weg, probe=True)
    assert probe.dateien == 4 and (ordner / "a1.json").read_text("utf-8") == vorher

    e = migriere_bestand(tmp_path, {"kosten": "baukosten"}, weg)
    assert e.dateien == 4 and e.entfernt["quellen"] == 3 and e.entfernt["sportstaette_id"] == 2
    assert e.umbenannt["kosten → baukosten"] == 1
    assert [(a, n) for _, a, n in e.konflikte] == [("kosten", "baukosten")]  # a2 hat schon beides
    a = json.loads((ordner / "a1.json").read_text("utf-8"))
    assert a["baukosten"] == 5 and "kosten" not in a and "quellen" not in a
    s = json.loads((ordner / f"{STAETTE['id']}_meta.json").read_text("utf-8"))
    assert "quellen" not in s and s["name"] == STAETTE["name"]
    assert list(json.loads(org.read_text("utf-8"))) == ["id", "name"]  # Reihenfolge des Modells
    assert migriere_bestand(tmp_path, {"kosten": "baukosten"}, weg).dateien == 0
    (ordner / "a2.json").unlink()
    verstoesse = []
    list(lies_bestand(tmp_path, verstoesse))
    assert verstoesse == []


def test_art_von_eigentuemer_und_betreiber():
    from sportstaettenatlas.seite import betreiber_art

    assert betreiber_art("Stadtwerke X GmbH", "Kommunales Unternehmen") == "Kommune"
    assert betreiber_art("TuS Musterdorf e.V.") is None  # ohne Art: unbekannt
    assert betreiber_art("Stadt X", "Privatwirtschaftlich/kommerziell") == "sonstige"
    assert set(modell.ORGANISATIONSTYPEN.values()) == {"Verein", "Kommune", "sonstige"}


def test_kontaktdaten_an_einer_stelle():
    from sportstaettenatlas import bestand, einlesen, seite

    assert bestand.EMAIL.pattern == modell.EMAIL_MUSTER
    assert einlesen.KONTAKT.pattern == seite.KONTAKT.pattern == modell.KONTAKT_NAME
    assert modell.schema()["atlas"]["email"] == modell.EMAIL_MUSTER
    k = re.compile(modell.KONTAKT_NAME, re.IGNORECASE)
    for name in ("E-Mail", "alt_email", "Telefon", "Fax", "Ansprechpartner"):
        assert k.search(name), name
    for m in modell.MODELLE:  # kein Feld des Modells sieht wie Kontaktdaten aus
        for name, f in m.model_fields.items():
            assert not k.search(name) and not k.search(f.title or ""), name


def test_auswahllisten_einmal():
    """Im Modell sind Auswahllisten Enums (einmal benannt), im Schema stehen sie am Feld."""
    s = modell.schema()
    assert not any("enum" in d for d in s["$defs"].values())  # keine eigene Definition
    p = s["$defs"]["Sportanlage"]["properties"]
    assert p["felder_je_belag"]["propertyNames"]["enum"][0] == "Sportparkett"
    assert p["lux"]["anyOf"][0]["enum"][0] == 100
    b = modell.readme_block()
    assert b.count("„Sportparkett“") == 1  # die Liste steht einmal, unter „Auswahllisten“
    assert "Auswahl [Bodenbelag](#auswahllisten)" in b


def test_bereinigen():
    from sportstaettenatlas import werte

    assert werte.hausnummer("6.0") == "6" and werte.hausnummer("12a") == "12a"
    assert werte.hausnummer("-") is None and werte.hausnummer("2.5") == "2.5"  # bleibt (Regel)
    assert werte.website("www.tv-arzheim.de") == "https://www.tv-arzheim.de"
    assert werte.website("bendelit.de/verein") == "https://bendelit.de/verein"
    assert werte.website("http://a.de") == "http://a.de" and werte.website("-") is None
    zwei = "https://rsv-ga.de, radsportverein-gau-algesheim.de"
    assert werte.website(zwei) == zwei  # zwei Adressen: von Hand
    d = {"name": "X", "website": "www.x.de", "adresse": {"hausnummer": "-"}}
    assert sorted(werte.bereinige(d)) == ["adresse.hausnummer", "website"]
    assert d == {"name": "X", "website": "https://www.x.de"}
    # Hausnummer, die Excel zum Datum gemacht hat: kleinere Zahl vorne
    assert werte.hausnummer("02. Apr") == "2-4" and werte.hausnummer("Aug 14") == "8-14"
    assert werte.hausnummer("14. Aug") == "8-14" and werte.hausnummer("Mär-03") == "3-3"
    assert werte.hausnummer("Mai 2") == "2-5" and werte.hausnummer("12 b") == "12 b"
    assert werte.hausnummer("Augustastraße 2") == "Augustastraße 2"  # kein Monat
    # PLZ ohne führende Null; Ort als Dict-Text (Altsystem)
    assert werte.plz("4109") == "04109" and werte.plz("56068") == "56068"
    d = {
        "name": "X",
        "adresse": {
            "plz": "9125",
            "ort": "{'ags': '07131006', 'ort': 'Bad Breisig, Stadt', 'postleitzahl': '53498'}",
        },
    }
    assert sorted(werte.bereinige(d)) == ["adresse.ort", "adresse.plz"]
    assert d["adresse"] == {"plz": "09125", "ort": "Bad Breisig, Stadt"}  # PLZ bleibt die eigene
    ohne = {"adresse": {"ort": "{'ort': 'Worms, Stadt', 'postleitzahl': '67547'}"}}
    assert werte.bereinige(ohne) == ["adresse.ort"]
    assert ohne["adresse"] == {"ort": "Worms, Stadt", "plz": "67547"}
    kaputt = {"adresse": {"ort": "{kein dict"}}
    assert werte.bereinige(kaputt) == [] and kaputt["adresse"]["ort"] == "{kein dict"
    # Fläche einer Halle, nur Länge × Breite (Altsystem): fällt weg; beim Reitplatz bleibt sie
    halle = {"typ": "Dreifachsporthalle", "laenge": 45.0, "breite": 27.0, "flaeche": 1215.0}
    assert werte.bereinige(halle) == ["flaeche"] and "flaeche" not in halle
    anders = {"typ": "Dreifachsporthalle", "laenge": 45.0, "breite": 27.0, "flaeche": 1400.0}
    assert werte.bereinige(anders) == []  # weicht ab: bleibt, die Prüfung meldet sie
    reitplatz = {"typ": "Reitplatz", "laenge": 40.0, "breite": 20.0, "flaeche": 800.0}
    assert werte.bereinige(reitplatz) == []


def test_diagramm_zeigt_felder_je_typ(tmp_path, monkeypatch):
    import sys
    import types

    gezeichnet = {}

    def feld(name):
        return types.SimpleNamespace(name=name, type_name="Optional[float]")

    anlage = types.SimpleNamespace(
        name="Sportanlage", fields={n: feld(n) for n in ("bezeichnung", "trennvorhang")}
    )

    def create(*_):
        d = types.SimpleNamespace(models={"x.Sportanlage": anlage})
        d.draw = lambda out: gezeichnet.setdefault("out", out)
        return d

    monkeypatch.setitem(sys.modules, "erdantic", types.SimpleNamespace(create=create))
    assert modell.zeichne(tmp_path / "d.svg") and gezeichnet["out"] == tmp_path / "d.svg"
    assert anlage.fields["trennvorhang"].type_name == "Optional[float] · nur Bühne"
    assert anlage.fields["bezeichnung"].type_name == "Optional[float]"  # für alle Typen


def test_migrieren_bereinigen(tmp_path):
    from sportstaettenatlas.bestand import migriere_bestand

    ordner = tmp_path / "RP" / "07111-koblenz" / STAETTE["id"]
    ordner.mkdir(parents=True)
    st = {
        **STAETTE,
        "website": "www.verein.de",
        "adresse": {**STAETTE["adresse"], "hausnummer": "6.0"},
    }
    (ordner / f"{STAETTE['id']}_meta.json").write_text(json.dumps(st), "utf-8")
    org = tmp_path / "organisationen" / "RP" / "ohne-art" / "o1.json"
    org.parent.mkdir(parents=True)
    org.write_text(json.dumps({"id": "o1", "name": "TuS", "website": "tus.de"}), "utf-8")
    probe = migriere_bestand(tmp_path, bereinigen=True, probe=True)
    assert probe.bereinigt == {"website": 2, "adresse.hausnummer": 1}
    e = migriere_bestand(tmp_path, bereinigen=True)
    assert e.dateien == 2
    neu = json.loads((ordner / f"{STAETTE['id']}_meta.json").read_text("utf-8"))
    assert neu["website"] == "https://www.verein.de" and neu["adresse"]["hausnummer"] == "6"
    assert json.loads(org.read_text("utf-8"))["website"] == "https://tus.de"
    assert migriere_bestand(tmp_path, bereinigen=True).dateien == 0
