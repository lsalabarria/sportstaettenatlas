"""Vorschläge aus einem LimeSurvey-Export übernehmen – synthetische Daten."""

import csv
import json

from sportstaettenatlas.bestand import (
    lies_bestand,
    lies_organisationen,
    schreibe_bestand,
    schreibe_organisation,
)
from sportstaettenatlas.vorschlaege import UEBERNOMMEN, lies_export, uebernimm

SID = "11111111-1111-4111-8111-111111111111"
A1 = "aaaaaaaa-1111-4111-8111-111111111111"
A2 = "bbbbbbbb-2222-4222-8222-222222222222"


def _kreis(lon, lat):
    return "07111-kreis-a"


def _bestand(tmp_path):
    daten = tmp_path / "daten"
    st = {
        "id": SID,
        "name": "Sportplatz Musterdorf",
        "kategorie": "Sportplatz",
        "adresse": {"strasse": "Am Weg", "plz": "56068", "ort": "Musterdorf"},
        "lage": {"lon": 7.59, "lat": 50.35},
        "betreiber": "TuS Musterdorf",
        "anlagen": [
            {"id": A1, "typ": "Großspielfeld", "baujahr": 1990},
            {"id": A2, "typ": "Rundlaufbahn"},
        ],
    }
    schreibe_bestand([st], daten, "RP", _kreis)
    schreibe_organisation(daten, {"id": "o1", "name": "TuS Musterdorf", "typ": "Sportverein"})
    return daten


def _export(tmp_path, vorschlaege):
    p = tmp_path / "results-survey1.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(
            [
                "Antwort ID",
                "Datum Abgeschickt",
                "Letzte Seite",
                "Vorschlag (vom Formular)",
                "Kommentar (optional)",
            ]
        )
        for i, (v, kommentar) in enumerate(vorschlaege, 1):
            w.writerow([i, "1980-01-01 00:00:00", 1, json.dumps(v), kommentar])
    return p


AENDERUNG = {"version": 1, "art": "aenderung", "sportstaette_id": SID}


def test_vorschlaege_uebernehmen(tmp_path):
    daten = _bestand(tmp_path)
    neu = {
        "version": 1,
        "art": "neu",
        "sportstaette": {
            "name": "Freibad Neu",
            "kategorie": "Schwimmsportstätte",
            "adresse": {"ort": "Sargenroth"},
            "lage": {"lon": 7.546234, "lat": 49.907184},
        },
        "anlagen": [{"typ": "Freibad"}],
        "gemeinde": "071405008134",
    }
    staette = {
        "name": "Sportplatz Musterdorf",
        "kategorie": "Sportplatz",
        "lage": {"lon": 7.59, "lat": 50.35},
    }
    p = _export(
        tmp_path,
        [
            (neu, "Bitte prüfen"),
            (
                {
                    **AENDERUNG,
                    "sportstaette": {**staette, "betreiber": "SV Eins"},
                    "geaendert": ["betreiber"],
                },
                "",
            ),
            (
                {
                    **AENDERUNG,
                    "sportstaette": {
                        **staette,
                        "betreiber": "SV Zwei",
                        "adresse": {"plz": "56070"},
                    },
                    "geaendert": ["betreiber", "adresse.plz", "adresse.strasse"],
                },
                "",
            ),
            (
                {
                    "version": 1,
                    "art": "anlagen",
                    "sportstaette_id": SID,
                    "anlagen": [
                        {"id": A1[:8], "typ": "Großspielfeld", "baujahr": 1998},
                        {"typ": "Kleinspielfeld"},
                    ],
                    "entfernte_anlagen": [A2[:8]],
                },
                "",
            ),
            (
                {
                    "version": 1,
                    "art": "organisation",
                    "organisation_id": "o1",
                    "organisation": {"name": "TuS Musterdorf", "website": "https://tus.example"},
                    "geaendert": ["website"],
                },
                "",
            ),
            ({"version": 1, "art": "aenderung"}, ""),  # ohne sportstaette_id
        ],
    )
    antworten = lies_export(p)
    assert [a.id for a in antworten] == ["1", "2", "3", "4", "5", "6"]

    vorher = sorted(x.read_text("utf-8") for x in daten.rglob("*.json"))
    e = uebernimm(antworten, daten, _kreis, probe=True)
    assert sorted(x.read_text("utf-8") for x in daten.rglob("*.json")) == vorher
    assert not (daten / UEBERNOMMEN).exists()

    e = uebernimm(antworten, daten, _kreis)
    assert dict(e.uebernommen) == {"neu": 1, "aenderung": 2, "anlagen": 1, "organisation": 1}
    assert e.kommentare == [("1", "Bitte prüfen")]
    assert len(e.warnungen) == 2
    assert "Antworten 2, 3" in e.warnungen[0] and "SV Eins|SV Zwei" in e.warnungen[0]
    assert e.warnungen[1].startswith("Antwort 6: passt nicht zum Modell")

    bestand = {d["id"]: d for d in lies_bestand(daten)}
    alt = bestand[SID]
    assert alt["betreiber"] == "SV Eins|SV Zwei"  # widersprüchlich: beide Werte
    assert alt["adresse"] == {"plz": "56070", "ort": "Musterdorf"}  # Straße geleert
    typen = {a["typ"]: a for a in alt["anlagen"]}
    assert set(typen) == {"Großspielfeld", "Kleinspielfeld"}  # Rundlaufbahn entfernt
    assert typen["Großspielfeld"]["baujahr"] == 1998 and typen["Großspielfeld"]["id"] == A1
    (neue_id,) = e.neue_ids
    assert bestand[neue_id]["name"] == "Freibad Neu"
    assert [a["typ"] for a in bestand[neue_id]["anlagen"]] == ["Freibad"]
    assert "Bitte prüfen" not in json.dumps(bestand[neue_id])  # Kommentar nie gespeichert
    (o,) = lies_organisationen(daten)
    assert o["website"] == "https://tus.example" and o["typ"] == "Sportverein"
    assert (daten / UEBERNOMMEN).read_text("utf-8").split() == ["1", "2", "3", "4", "5"]

    # zweiter Lauf mit demselben Export: nichts mehr zu tun
    e = uebernimm(lies_export(p), daten, _kreis)
    assert e.uebersprungen == 5 and not e.uebernommen and len(e.neue_ids) == 0
    assert len(list(lies_bestand(daten))) == 2


def test_beispiel_aus_limesurvey(tmp_path):
    p = tmp_path / "export.csv"
    p.write_text(
        '﻿"Antwort ID","Datum Abgeschickt","Letzte Seite","Start-Sprache",'
        '"Zufallsstartwert","Vorschlag (wird vom Formular des Sportstättenatlas ausgefüllt)",'
        '"Kommentar (optional)"\n'
        '"1","1980-01-01 00:00:00","1","de","274602745","{""version"":1,""art"":""neu"",'
        '""sportstaette"":{""name"":""test"",""kategorie"":""Schwimmsportstätte"",'
        '""adresse"":{""ort"":""Sargenroth""},""lage"":{""lon"":7.546234,""lat"":49.907184}},'
        '""anlagen"":[],""gemeinde"":""071405008134""}",""\n',
        encoding="utf-8",
    )
    (a,) = lies_export(p)
    assert a.id == "1" and a.vorschlag["art"] == "neu" and a.kommentar == ""
    daten = tmp_path / "daten"
    e = uebernimm([a], daten, _kreis)
    assert e.uebernommen["neu"] == 1 and not e.warnungen
    (d,) = lies_bestand(daten)
    assert d["name"] == "test" and d["anlagen"] == []
