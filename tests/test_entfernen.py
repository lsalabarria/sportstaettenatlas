"""Einträge aus daten/ entfernen (entfernen.py, Befehl `bestand`) – synthetische Daten."""

import argparse
import csv
import json

from sportstaettenatlas.bestand import lies_bestand, lies_organisationen, lies_stuetzpunkte
from sportstaettenatlas.pflege import cli, entfernen

S1 = "11111111-1111-4111-8111-111111111111"  # Sportplatz, behält
S2 = "22222222-2222-4222-8222-222222222222"  # Doppelung von S1
A1 = "aaaaaaaa-1111-4111-8111-111111111111"
A2 = "bbbbbbbb-2222-4222-8222-222222222222"
K1 = "33333333-3333-4333-8333-333333333333"


def _json(pfad, d):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(d, ensure_ascii=False), "utf-8")


def _daten(tmp_path):
    daten = tmp_path / "daten"
    kreis = daten / "RP" / "07111-koblenz"
    _json(
        kreis / S1 / f"{S1}_meta.json",
        {"id": S1, "name": "Sportplatz Berg", "betreiber": "TuS Berg e.V."},
    )
    _json(kreis / S1 / f"{A1}.json", {"id": A1, "typ": "Großspielfeld"})
    _json(
        kreis / S2 / f"{S2}_meta.json",
        {"id": S2, "name": "Sportplatz Berg (Halle)", "sportkomplex": K1},
    )
    _json(kreis / S2 / f"{A2}.json", {"id": A2, "typ": "Einfeldhalle"})
    _json(kreis / "sportkomplexe" / f"{K1}.json", {"id": K1, "name": "Sportpark Berg"})
    _json(
        daten / "stuetzpunkte" / "sp1.json",
        {
            "id": "sp1",
            "name": "LSP Turnen",
            "art": "Landesstützpunkt",
            "sportstaetten": [S2],
            "anerkannt_von": "TuS Berg e.V.",  # freier Text: kein Verweis auf die Organisation
        },
    )
    _json(
        daten / "organisationen" / "RP" / "sonstiger-sportverein" / "o1.json",
        {"id": "o1", "name": "TuS Berg e.V.", "typ": "Sonstiger Sportverein"},
    )
    return daten


def _csv(pfad, zeilen):
    with pfad.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerows([["Art", "ID", "Begründung"], *zeilen])
    return pfad


def test_von_oben_nach_unten(tmp_path):
    daten = _daten(tmp_path)
    tabelle = _csv(
        tmp_path / "entfernen.csv",
        [
            [
                "Sportstätte",
                S2[:8],
                "Doppelung: Halle gehört zu Sportplatz Berg",
            ],  # Stützpunkt zeigt drauf
            ["Stützpunkt", "sp1", "aufgelöst"],
            ["Sportstätte", S2[:8], "Doppelung: Halle gehört zu Sportplatz Berg"],  # Anlage da
            ["Sportanlage", A2[:8], "Doppelung: als Anlage bei Sportplatz Berg"],
            ["Sportstätte", S2[:8], "Doppelung: Halle gehört zu Sportplatz Berg"],  # jetzt frei
            ["Sportkomplex", K1, "nur noch eine Sportstätte"],  # S2 ist weg: frei
            ["Organisation", "o1", "Doppelung"],  # Sportplatz Berg nennt den Betreiber
            ["Sportanlage", A1[:8], ""],  # ohne Begründung
            ["Halle", "x", "?"],
            ["Sportanlage", "ffffffff", "gibt es nicht"],
            ["Sportanlage", A1, "Kontakt: a@b.de"],
        ],
    )
    eintraege = entfernen.lies(tabelle)

    probe = entfernen.entferne(eintraege, daten, probe=True)
    assert [(a, i[:8]) for a, i, _ in probe.entfernt] == [
        ("Stützpunkt", "sp1"),
        ("Sportanlage", "bbbbbbbb"),
        ("Sportstätte", "22222222"),
        ("Sportkomplex", "33333333"),
    ]
    assert (daten / "RP" / "07111-koblenz" / S2).is_dir()  # Probe: nichts gelöscht
    assert not (daten / entfernen.PROTOKOLL).exists()

    e = entfernen.entferne(eintraege, daten)
    assert [w.split(":")[0] for w in e.warnungen] == [
        f"Zeile {i}" for i in (2, 4, 8, 9, 10, 11, 12)
    ]
    anlage = "Sportanlage „Einfeldhalle“ (bbbbbbbb)"
    assert f"noch verwendet von {anlage}, Stützpunkt „LSP Turnen“" in e.warnungen[0]
    assert f"noch verwendet von {anlage} (übersprungen)" in e.warnungen[1]
    assert "noch verwendet von Sportstätte „Sportplatz Berg“" in e.warnungen[2]
    assert {d["id"] for d in lies_bestand(daten)} == {S1}
    assert lies_stuetzpunkte(daten) == [] and len(lies_organisationen(daten)) == 1
    assert not list((daten / "RP").glob("*/sportkomplexe/*.json"))

    with (daten / entfernen.PROTOKOLL).open(encoding="utf-8") as f:
        protokoll = list(csv.DictReader(f, delimiter=";"))
    assert [(z["art"], z["id"][:8], z["name"]) for z in protokoll] == [
        ("Stützpunkt", "sp1", "LSP Turnen"),
        ("Sportanlage", "bbbbbbbb", "Einfeldhalle"),
        ("Sportstätte", "22222222", "Sportplatz Berg (Halle)"),
        ("Sportkomplex", "33333333", "Sportpark Berg"),
    ]
    assert protokoll[2]["begruendung"].startswith("Doppelung")


def test_bestand_entfernt_nach_den_uebrigen_dateien(tmp_path, monkeypatch, capsys):
    """Erst die Anlage bei der richtigen Sportstätte eintragen, dann die Doppelung entfernen –
    auch wenn die Tabelle zum Entfernen zuerst genannt wird."""
    daten = _daten(tmp_path)
    monkeypatch.setattr(cli, "DATEN", daten)
    weg = _csv(
        tmp_path / "weg.csv",
        [
            ["Stützpunkt", "sp1", "aufgelöst"],
            ["Sportanlage", A2, "Doppelung"],
            ["Sportstätte", S2, "Doppelung"],
        ],
    )
    anlagen = tmp_path / "anlagen.csv"
    anlagen.write_text(f"sportstaette_id;typ\n{S1};Einfeldhalle\n", "utf-8")
    args = argparse.Namespace(dateien=[str(weg), str(anlagen)], modus="ergaenzen", probe=False)
    cli.cmd_bestand(args)
    [s1] = list(lies_bestand(daten))
    assert sorted(a["typ"] for a in s1["anlagen"]) == ["Einfeldhalle", "Großspielfeld"]
    aus = capsys.readouterr().out
    assert aus.index("anlagen.csv →") < aus.index("weg.csv → entfernen: 3")


def test_anerkannt_von_ist_kein_verweis(tmp_path):
    daten = tmp_path / "daten"
    _json(
        daten / "stuetzpunkte" / "sp1.json",
        {
            "id": "sp1",
            "name": "LSP Turnen",
            "anerkannt_von": "Landessportbund RLP",
            "traeger": "Turnverband",
        },
    )
    for oid, name in (("o1", "Landessportbund RLP"), ("o2", "Turnverband")):
        _json(
            daten / "organisationen" / "RP" / "ohne-art" / f"{oid}.json", {"id": oid, "name": name}
        )
    tabelle = _csv(
        tmp_path / "e.csv", [["Organisation", "o1", "Test"], ["Organisation", "o2", "Test"]]
    )
    e = entfernen.entferne(entfernen.lies(tabelle), daten)
    assert [i for _, i, _ in e.entfernt] == ["o1"]  # nur im Text genannt: wird entfernt
    assert "Stützpunkt „LSP Turnen“" in e.warnungen[0]  # Träger: bleibt
