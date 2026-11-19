"""Stützpunkte: Ablage, CSV, Prüfungen – synthetische Daten."""

import datetime as dt

from sportstaettenatlas.bestand import (
    lies_bestand,
    lies_stuetzpunkte,
    migriere_bestand,
    schreibe_bestand,
    schreibe_organisationen,
    schreibe_sportkomplex,
    schreibe_stuetzpunkt,
    schreibe_stuetzpunkte,
)
from sportstaettenatlas.einlesen import lies_csv
from sportstaettenatlas.validate import pruefe, stuetzpunkte

S1, S2, S3 = (f"{i * 8}-2222-4222-8222-222222222222" for i in "123")
K1 = "aaaaaaaa-0000-4000-8000-000000000001"
P1 = "eeeeeeee-0000-4000-8000-000000000001"


def _st(sid, **mehr):
    return {
        "id": sid,
        "name": f"Halle {sid[:2]}",
        "kategorie": "Sporthalle",
        "lage": {"lon": 7.6001, "lat": 50.3501},
        **mehr,
    }


def _daten(tmp_path):
    d = tmp_path / "daten"
    schreibe_bestand(
        [_st(S1, sportkomplex=K1), _st(S2, sportkomplex=K1), _st(S3)],
        d,
        "RP",
        lambda lon, lat: "07111-koblenz",
    )
    schreibe_sportkomplex(d, {"id": K1, "name": "Sportzentrum Berg"}, "07111-koblenz")
    schreibe_organisationen([{"name": "TuS Berg e.V.", "typ": "Sportverein im LSB RLP"}], d)
    return d


def test_ablage_und_pruefungen(tmp_path):
    d = _daten(tmp_path)
    sp = {
        "id": P1,
        "name": "Bundesstützpunkt Leichtathletik Berg",
        "art": "Bundesstützpunkt",
        "traeger": "TuS Berg e.V.",
        "gueltig_bis": "2024-12-31",
        "sportstaetten": [S1, S3, "99999999-0000-4000-8000-000000000000"],
        "sportkomplexe": [K1, "bbbbbbbb-0000-4000-8000-000000000000"],
    }
    schreibe_stuetzpunkt(d, sp)
    assert (d / "stuetzpunkte" / f"{P1}.json").exists()
    assert len(list(lies_bestand(d))) == 3  # der Ordner stuetzpunkte ist kein Land
    assert migriere_bestand(d, probe=True).dateien == 0
    (gelesen,) = lies_stuetzpunkte(d)
    from sportstaettenatlas.bestand import lies_organisationen, lies_sportkomplexe, org_verzeichnis

    verzeichnis = org_verzeichnis(lies_organisationen(d))
    meldungen = {
        (p, m)
        for _, p, m in stuetzpunkte(
            [gelesen],
            list(lies_bestand(d)),
            lies_sportkomplexe(d),
            verzeichnis,
            heute=dt.date(2026, 1, 1),
        )
    }
    assert meldungen == {
        ("Stützpunkt abgelaufen", "gueltig_bis: Anerkennung endete am 2024-12-31"),
        (
            "Stützpunkt-Verweis",
            "sportstaetten: Sportstätte 99999999-0000-4000-8000-000000000000 gibt es nicht",
        ),
        (
            "Stützpunkt-Verweis",
            "sportkomplexe: Sportkomplex bbbbbbbb-0000-4000-8000-000000000000 gibt es nicht",
        ),
        (
            "Stützpunkt doppelt",
            f"sportstaetten: {S1} gehört schon über den Sportkomplex „Sportzentrum Berg“ dazu",
        ),
    }
    gelesen["traeger"] = "SV Tal"
    namen = {p for _, p, _ in stuetzpunkte([gelesen], [], [], verzeichnis)}
    assert "Träger des Stützpunkts" in namen
    # über pruefe: mit Datei
    alle = pruefe(list(lies_bestand(d)), lies_organisationen(d), None, d)
    assert any(p == "Stützpunkt-Verweis" and datei.endswith(f"{P1}.json") for datei, p, _ in alle)


def test_csv(tmp_path):
    d = _daten(tmp_path)
    csv = tmp_path / "stp.csv"
    csv.write_text(
        "name;art;sportarten;gueltig_bis;sportstaetten;sportkomplexe\n"
        f'Landesstützpunkt Turnen Berg;Landesstützpunkt;Turnen;31.12.2028;"{S3[:8]}; 77777777";{K1[:8]}\n',
        "utf-8",
    )
    datensaetze, b = lies_csv(csv)
    assert b.art == "stuetzpunkte" and not b.nicht_lesbar
    e = schreibe_stuetzpunkte(datensaetze, d)
    assert (e.neu, e.ohne_sportstaette) == (1, 1)
    (sp,) = lies_stuetzpunkte(d)
    assert sp["gueltig_bis"] == "2028-12-31"
    assert (sp["sportstaetten"], sp["sportkomplexe"]) == ([S3], [K1])
    # noch einmal: gleiche ID aus dem Namen, nichts Neues
    e = schreibe_stuetzpunkte(lies_csv(csv)[0], d)
    assert (e.neu, e.behalten) == (0, 1)
