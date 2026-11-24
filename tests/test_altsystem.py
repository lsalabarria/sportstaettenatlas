"""Einmaliger Import aus dem Altsystem (skripte/altsystem.py) – synthetische Daten."""

import csv
import importlib.util
import json
from pathlib import Path

from sportstaettenatlas.bestand import (
    OHNE_KREIS,
    anlage_id,
    lies_bestand,
    lies_organisationen,
    lies_sportkomplexe,
    lies_stuetzpunkte,
    schreibe_bestand,
)
from sportstaettenatlas.pflege.vorschlaege import lies_export

_spec = importlib.util.spec_from_file_location(
    "altsystem", Path(__file__).parents[1] / "skripte" / "altsystem.py"
)
altsystem = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(altsystem)

S1, S2, S3, S4 = (f"{i}{i}{i}{i}{i}{i}{i}{i}-1111-4111-8111-111111111111" for i in range(1, 5))
A1, A2, A3 = (f"a{i}a{i}a{i}a{i}-2222-4222-8222-222222222222" for i in range(1, 4))
O1, O2, O3 = (f"0000000{i}-3333-4333-8333-333333333333" for i in range(1, 4))
K1 = "44444444-4444-4444-8444-444444444444"
T = {  # typenum: Bezeichnung → (ID, prog, label)
    "Sportplatz": ("t-sst", "SST", "Sportplatz"),
    "Sonstige": ("t-sonst", "SST", "Sportgelegenheiten in sonstigen Gebäuden"),
    "Großspielfeld (ab 5.000 m²)": ("t-gsf", "san", ""),
    "Tennisplatz": ("t-tennis", "SAN", ""),
    "Fußball": ("t-fb", "SAR", ""),
    "Verein": ("t-verein", "ORG", "LSB RLP - Sportverein"),
    "Kommune": ("t-kommune", "ORG", "Stadt / Gemeinde"),
    "in Betrieb": ("t-betrieb", "BESTATUS", ""),
    "Putz": ("t-putz", "FASS", ""),
    "Umkleideraum": ("t-umkleide", "FRA", ""),
    "Strom": ("t-strom-w", "WASSER", ""),
    "Erdgas": ("t-gas", "EVERBRAUCH", ""),
    "KWh": ("t-kwh", "EEINHEIT", ""),
    "Euro": ("t-eur", "WAE", ""),
    "BSP": ("t-bsp", "OSP", ""),
    "LSP": ("t-lsp", "OSP", ""),
}
TID = {k: v[0] for k, v in T.items()}


def _csv(pfad: Path, zeilen: list[dict]) -> None:
    spalten = list(dict.fromkeys(k for z in zeilen for k in z)) + ["geloeschtam"]
    with pfad.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=spalten, quoting=csv.QUOTE_ALL, restval="NULL")
        w.writeheader()
        w.writerows(zeilen)


def _altsystem(ordner: Path) -> Path:
    ordner.mkdir()
    t = lambda name, zeilen: _csv(ordner / f"dbs1_table_{name}.csv", zeilen)
    t(
        "typenum",
        [{"id": i, "bezeichnung": b, "prog": p, "label": lab} for b, (i, p, lab) in T.items()],
    )
    t(
        "adresse",
        [
            {"id": "ad1", "strasse": "Am Platz", "hausnummer": "1", "postleitzahl": "56068",
             "ort": "Koblenz", "ags": "07111000"},
            {"id": "ad2", "strasse": "Weg", "postleitzahl": "50667", "ort": "Köln",
             "ags": "05315000"},
        ],
    )  # fmt: skip
    t(
        "organisation",
        [
            {"id": O1, "bezeichnung": "TuS Berg e.V.", "typid": TID["Verein"], "extref": "1234567",
             "email": "geheim@example.org", "telefonnummer": "0261 1"},
            {"id": O2, "bezeichnung": "Koblenz", "typid": TID["Kommune"], "ags": "07111"},
            {"id": O3, "bezeichnung": "Test Betreiber", "typid": TID["Kommune"]},
        ],
    )  # fmt: skip
    t(
        "sportstaette",
        [
            {"id": S1, "bezeichnung": "Sportplatz Berg", "typid": TID["Sportplatz"],
             "utm32nhoch": "50.35", "utm32nrechts": "7.6", "adresseid": "ad1",
             "eignerorgaid": O2, "betreiberorgaid": O1, "wlan": "1", "schulsport": "-1",
             "baujahr": "1970", "fassadenmaterial": TID["Putz"],
             "betriebsstatustypid": TID["in Betrieb"], "sportkomplexid": K1,
             "email": "platz@example.org"},
            {"id": S2, "bezeichnung": "Halle Berg", "typid": TID["Sonstige"],
             "utm32nhoch": "50.351", "utm32nrechts": "7.601", "adresseid": "ad1",
             "sportkomplexid": K1, "baujahr": "0"},
            {"id": S3, "bezeichnung": "Platz Köln", "typid": TID["Sportplatz"],
             "utm32nhoch": "50.94", "utm32nrechts": "6.95", "adresseid": "ad2"},
            {"id": S4, "bezeichnung": "ohne Lage", "typid": TID["Sportplatz"]},
        ],
    )  # fmt: skip
    t(
        "sportanlage",
        [
            {"id": A1, "sportstaetteid": S1, "typid": TID["Großspielfeld (ab 5.000 m²)"],
             "baujahr": "1972", "flutlicht": "-1", "anz_feld_fussball": "1",
             "erstelltam": "2020-01-01"},
            {"id": A2, "sportstaetteid": S1, "typid": TID["Tennisplatz"],
             "erstelltam": "2020-01-02", "baukosten": "50000.000", "waehrung": TID["Euro"]},
            {"id": A3, "sportstaetteid": S3, "typid": TID["Tennisplatz"]},
        ],
    )  # fmt: skip
    t(
        "sportanlagesportart",
        [{"id": "x1", "sportanlageid": A1, "sportartid": TID["Fußball"], "wettkampfeignung": "1"}],
    )
    t(
        "funktionsraum",
        [
            {"id": "f1", "sportstaetteid": S1, "typid": TID["Umkleideraum"], "anzahl": "2"},
            {"id": "f2", "sportstaetteid": S1, "typid": TID["Umkleideraum"], "anzahl": "0"},
        ],
    )
    t(
        "energietraeger",
        [
            {
                "id": "e1",
                "sportstaetteid": S1,
                "energietraegertypid": TID["Strom"],
                "einbaujahr": "2001",
            }
        ],
    )
    t(
        "jahresverbrauch",
        [{"id": "j1", "sportstaetteid": S1, "energieverbrauchtypid": TID["Erdgas"], "menge": "1000",
          "energieeinheittypid": TID["KWh"]}],
    )  # fmt: skip
    t(
        "sanierung",
        [{"id": "s1", "sanierungskosten": "1000.00", "waehrung": TID["Euro"],
          "sanierungsjahr": "2019", "entity_type": "2", "entity_id": A1}],
    )  # fmt: skip
    t("foerderung", [{"id": "g1", "foerderhoehe": "500.00", "waehrung": TID["Euro"],
                      "foerderprogramm": "Goldener Plan", "foerderjahr": "2019",
                      "entity_type": "1", "entity_id": S1}])  # fmt: skip
    t("sportstaettenutzer", [{"id": "n1", "sportstaetteid": S1, "nutzername": "SG Berg"}])
    t("sportkomplex", [{"id": K1, "bezeichnung": "Sportpark Berg", "adresseid": "ad1"}])
    t(
        "leistungssport_stuetzpunkt",
        [
            {"id": "sp1", "sportstaetteid": S1, "typid": TID["BSP"], "bezeichnung": "DFB"},
            {"id": "sp2", "sportstaetteid": S3, "typid": TID["LSP"], "bezeichnung": "demo"},
        ],
    )
    form_aenderung = {
        "wlan": 0,
        "adresse": {"hausnummer": "2"},
        "email": "melder@example.org",
        "sportanlage": [
            {"state": "CHANGED", "sportanlagesportart": [],
             "model": {"id": A2, "typid": TID["Tennisplatz"], "flutlicht": 1}},
            {"state": "ADDED", "sportanlagesportart": [],
             "model": {"id": None, "typid": TID["Tennisplatz"]}},
            {"state": "DELETED", "model": {"id": A1, "typid": TID["Großspielfeld (ab 5.000 m²)"]}},
        ],
        "leistungssportStuetzpunkt": [{"label": "LSP", "bezeichnung": "Tennis", "state": "ADDED"}],
    }  # fmt: skip
    form_neu = {
        "bezeichnung": "Neuer Platz",
        "typid": TID["Sportplatz"],
        "utm32nhoch": 50.36,
        "utm32nrechts": 7.61,
        "adresse": {"postleitzahl": "56068", "ort": "Koblenz"},
        "telefonnummer": "0261 2",
        "funktionaleRaeume": [{"label": "Umkleideraum", "anzahl": 3, "state": "ADDED"}],
        "sportanlage": [
            {"state": "ADDED", "sportanlagesportart": [
                {"sportartid": TID["Fußball"], "wettkampfeignung": 0, "state": "ADDED"}],
             "model": {"id": None, "typid": TID["Großspielfeld (ab 5.000 m²)"]}},
        ],
    }  # fmt: skip
    _csv(
        ordner / "public_submissions.csv",
        [
            {"id": "1", "sportstaette_id": S1, "form_data": json.dumps(form_aenderung),
             "public_email": "melder@example.org", "status": "pending"},
            {"id": "2", "sportstaette_id": "NULL", "form_data": json.dumps(form_neu),
             "status": "pending"},
            {"id": "3", "sportstaette_id": S1, "form_data": json.dumps({"wlan": 0}),
             "status": "approved"},
        ],
    )  # fmt: skip
    return ordner


def _lage(hoch, rechts):  # synthetisch: die „UTM-Werte“ sind schon Grad
    return {"lon": rechts, "lat": hoch}


def _kreis(lon, lat):
    return "07111-koblenz" if lon > 7 else OHNE_KREIS


def test_altsystem(tmp_path):
    ordner = _altsystem(tmp_path / "alt")
    daten = tmp_path / "daten"
    # S1 gibt es schon (aus dem Atlas-Export, mit einem Tennisplatz)
    schreibe_bestand(
        [{"id": S1, "name": "Sportplatz Berg", "kategorie": "Sportplatz",
          "lage": {"lon": 7.6, "lat": 50.35}, "wlan": "nein", "anlagen": [{"typ": "Tennisplatz"}]}],
        daten, "RP", _kreis,
    )  # fmt: skip
    export = tmp_path / "vorschlaege.csv"
    bericht = altsystem.importiere(ordner, daten, _kreis, export, lage_aus=_lage)
    assert any("ohne LSB-Nummer und ohne Verweis weggelassen" in z for z in bericht)

    orgs = {o["name"]: o for o in lies_organisationen(daten)}
    assert orgs["TuS Berg e.V."]["lsb_nummer"] == "1234567"
    assert orgs["TuS Berg e.V."]["typ"] == "Sportverein im LSB RLP"
    assert "Test Betreiber" not in orgs  # ohne Verweis und ohne LSB-Nummer
    alles = json.dumps(list(lies_organisationen(daten)) + list(lies_bestand(daten)))
    assert "example.org" not in alles and "0261" not in alles

    bestand = {d["id"]: d for d in lies_bestand(daten)}
    assert set(bestand) == {S1, S2, S3}  # S4 ohne Lage
    s1 = bestand[S1]
    assert s1["wlan"] == "nein"  # vorhandener Wert bleibt
    assert "schulsport" not in s1  # -1: keine Angabe
    assert s1["eigentuemer"] == "Koblenz" and s1["betreiber"] == "TuS Berg e.V."
    assert s1["fassadenmaterial"] == "Putz" and s1["baujahr"] == 1970
    assert s1["funktionsraeume"] == {"Umkleide- und Sanitärräume - Sporttreibende": 2}
    assert s1["energietraeger"] == [
        {
            "bereich": "Warmwasser",
            "art": "Strom (z.B. Durchlauferhitzer, Boiler)",
            "einbaujahr": 2001,
        }
    ]
    assert s1["verbraeuche"] == [{"art": "Erdgas", "menge": 1000.0, "einheit": "kWh"}]
    assert s1["foerderungen"] == [
        {"programm": "Goldener Plan", "jahr": 2019, "hoehe": 500.0, "waehrung": "€"}
    ]
    assert s1["nutzer"] == ["SG Berg"] and s1["sportarten"] == ["Fußball"]
    assert s1["adresse"]["strasse"] == "Am Platz"
    anlagen = {a["typ"]: a for a in s1["anlagen"]}
    assert len(s1["anlagen"]) == 2  # Tennisplatz wiedergefunden, Großspielfeld neu
    assert anlagen["Tennisplatz"]["id"] == anlage_id(S1, "Tennisplatz", 1)
    assert anlagen["Tennisplatz"]["baukosten"] == 50000.0
    gsf = anlagen["Großspielfeld"]
    assert gsf["id"] == anlage_id(S1, "Großspielfeld", 1)
    assert gsf["sportarten"] == ["Fußball"] and gsf["wettkampf"] == ["Fußball"]
    assert "flutlicht" not in gsf and gsf["felder_je_sportart"] == {"Fußball": 1}
    assert gsf["sanierungen"] == [{"jahr": 2019, "kosten": 1000.0, "waehrung": "€"}]
    s2 = bestand[S2]
    assert s2["kategorie"] == "Sportgelegenheiten in sonstigen Gebäuden" and "baujahr" not in s2
    s3 = bestand[S3]
    assert (s3["_land"], s3["_ordner"]) == ("outside", "NW")
    assert [a["id"] for a in s3["anlagen"]] == [A3]  # neue behalten die alte ID

    [k] = lies_sportkomplexe(daten)
    assert (k["id"], k["name"], k["_ordner"]) == (K1, "Sportpark Berg", "07111-koblenz")
    assert s1["sportkomplex"] == K1 and s2["sportkomplex"] == K1

    sp = {s["id"]: s for s in lies_stuetzpunkte(daten)}
    assert sp["sp1"] == {
        "id": "sp1", "name": "DFB", "art": "Bundesstützpunkt", "sportstaetten": [S1]
    }  # fmt: skip
    assert sp["sp2"]["art"] == "Landesstützpunkt" and sp["sp2"]["sportstaetten"] == [S3]

    # offene Vorschläge als LimeSurvey-Export
    assert "example.org" not in export.read_text("utf-8")
    antworten = {a.id: a.vorschlag for a in lies_export(export)}
    assert set(antworten) == {"alt-1", "alt-1-anlagen", "alt-1-stuetzpunkt-1", "alt-2"}
    aenderung = antworten["alt-1"]
    assert aenderung["art"] == "aenderung" and aenderung["sportstaette_id"] == S1
    assert sorted(aenderung["geaendert"]) == ["adresse.hausnummer", "wlan"]
    assert aenderung["sportstaette"]["adresse"] == {
        "strasse": "Am Platz", "hausnummer": "2", "plz": "56068", "ort": "Koblenz"
    }  # fmt: skip
    a = antworten["alt-1-anlagen"]
    assert a["entfernte_anlagen"] == [gsf["id"]]
    geaendert, neu = a["anlagen"]
    assert geaendert["id"] == anlagen["Tennisplatz"]["id"] and geaendert["flutlicht"] == "ja"
    assert geaendert["baukosten"] == 50000.0  # bisherige Angaben bleiben
    assert neu == {"typ": "Tennisplatz"}
    assert antworten["alt-1-stuetzpunkt-1"]["stuetzpunkt"] == {
        "name": "Tennis", "art": "Landesstützpunkt", "sportstaetten": [S1]
    }  # fmt: skip
    n = antworten["alt-2"]
    assert n["art"] == "neu" and n["sportstaette"]["name"] == "Neuer Platz"
    assert n["sportstaette"]["funktionsraeume"] == {
        "Umkleide- und Sanitärräume - Sporttreibende": 3
    }
    assert n["anlagen"] == [{"typ": "Großspielfeld", "sportarten": ["Fußball"]}]

    # ein zweiter Lauf ändert nichts mehr
    vorher = {p: p.read_text("utf-8") for p in daten.rglob("*.json")}
    altsystem.importiere(ordner, daten, _kreis, export, lage_aus=_lage)
    assert {p: p.read_text("utf-8") for p in daten.rglob("*.json")} == vorher
