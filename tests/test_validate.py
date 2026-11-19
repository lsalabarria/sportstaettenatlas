"""Prüfungen aus validate.py – synthetische Daten."""

import re
from pathlib import Path

from sportstaettenatlas.bestand import schreibe_bestand, schreibe_organisation
from sportstaettenatlas.validate import PRUEFUNGEN, aehnlich, ort_passt, pruefe


def _quadrat(ars, name, w, s, o, n):
    ring = [[w, s], [o, s], [o, n], [w, n], [w, s]]
    return {
        "type": "Feature",
        "properties": {"ars": ars, "name": name},
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


GEMEINDEN = {
    "type": "FeatureCollection",
    "features": [
        _quadrat("071110000000", "Koblenz", 7.5, 50.3, 7.7, 50.4),
        _quadrat("071415001001", "Berg (Pfalz)", 7.7, 50.3, 7.9, 50.4),
        _quadrat("073150000000", "Mainz", 8.2, 49.95, 8.3, 50.05),
    ],
}
ORGS = [
    {
        "id": "o1",
        "name": "TuS Berg",
        "typ": "Sonstiger Sportverein",
        "weitere_namen": ["TuS Berg e.V."],
    }
]
S1, S2, S3, S4, S5, S6 = (
    f"{i}{i}{i}{i}{i}{i}{i}{i}-1111-4111-8111-111111111111" for i in range(1, 7)
)


def _st(sid, name, lon, lat, **mehr):
    return {
        "id": sid,
        "name": name,
        "kategorie": "Sportplatz",
        "lage": {"lon": lon, "lat": lat},
        **mehr,
    }


def test_hilfen_wie_im_formular():
    assert aehnlich("Sportplatz Berg", "Sportplatz Berg") == 1
    assert aehnlich("Dr. Darge-Halle", "Dr. Darge Halle") >= 0.8
    assert aehnlich("Sportplatz Berg", "Tennishalle Tal") < 0.8
    assert ort_passt("Koblenz, Stadt", "Koblenz")
    assert ort_passt("Koblenz-Metternich", "Koblenz")
    assert ort_passt("Berg", "Berg (Pfalz)")
    assert not ort_passt("Mainz, Stadt", "Koblenz")


def test_pruefe(tmp_path):
    daten = tmp_path / "daten"
    bestand = [
        _st(
            S1,
            "Sportplatz Koblenz",
            7.6,
            50.35,
            adresse={"ort": "Koblenz, Stadt"},
            betreiber="TuS Berg e.V.",
            eigentuemer="Stadt Nirgendwo",
            sportarten=["Fußball"],
            anlagen=[
                {
                    "id": "a1",
                    "typ": "Großspielfeld",
                    "sportarten": ["Fußball", "Rugby"],
                    "baujahr": 1990,
                    "letzte_sanierung": 1985,
                },
                {"id": "a2", "typ": "Tennisplatz", "bahnlaenge": 25},  # Becken-Feld
                {"id": "a3", "typ": "Freibad", "bahnlaenge": 50},  # passt
                {"id": "a4", "typ": "Eigenbau", "bahnlaenge": 10},  # Typ unbekannt: erlaubt
            ],
        ),
        _st(S2, "Sportplatz Koblenz ", 7.6003, 50.3502, adresse={"ort": "Mainz"}),  # 31 m
        _st(S3, "Sportplatz Koblenz", 7.6, 50.36),  # 1,1 km: keine Doppelung
        _st(S4, "Sportplatz Draußen", 6.0, 49.0),  # außerhalb
        # in Koblenz, 0,0014° ≈ 100 m vor Berg: innerhalb der Toleranz (VG250 ist generalisiert)
        _st(S5, "Halle am Rand", 7.6986, 50.32, adresse={"ort": "Berg"}),
        _st(S6, "Halle im Ortsteil", 7.6, 50.32, adresse={"ort": "Niederberg"}),  # keine Gemeinde
    ]
    schreibe_bestand(bestand, daten, "RP", lambda lon, lat: "07111-koblenz")
    meldungen = pruefe(bestand, ORGS, {"gemeinde": GEMEINDEN}, daten)
    assert {p for _, p, _ in meldungen} <= set(PRUEFUNGEN)
    nach = {}
    for datei, _, m in meldungen:
        nach.setdefault(datei.rsplit("/", 1)[-1], []).append(m)

    assert nach[f"{S1}_meta.json"] == [
        "eigentuemer: „Stadt Nirgendwo“ steht nicht im Verzeichnis der Organisationen",
        f"name: ähnlich wie „Sportplatz Koblenz “ (Sportplatz, {S2}), 31 m entfernt – Doppelung?",
    ]
    assert nach["a1.json"] == [
        "letzte_sanierung: 1985 liegt vor dem Baujahr 1990",
        "sportarten: Rugby fehlt bei der Sportstätte",
    ]
    assert nach["a2.json"] == ["bahnlaenge: ist befüllt, gehört aber nicht zum Typ „Tennisplatz“"]
    assert "a3.json" not in nach and "a4.json" not in nach
    assert nach[f"{S2}_meta.json"][0] == (
        "adresse.ort: „Mainz“, die Koordinate liegt aber in Koblenz, 54,1 km außerhalb von Mainz"
    )
    assert f"{S5}_meta.json" not in nach
    assert nach[f"{S6}_meta.json"] == [
        "adresse.ort: „Niederberg“ ist keine Gemeinde, die Koordinate liegt in Koblenz"
    ]
    assert nach[f"{S4}_meta.json"] == ["lage: liegt in keiner Gemeinde von Rheinland-Pfalz"]
    assert f"{S3}_meta.json" not in nach

    # ohne Gemeinden entfallen Ort und Rheinland-Pfalz, der Rest bleibt
    ohne = pruefe(bestand, ORGS, None, daten)
    assert not any(m.startswith(("adresse.ort", "lage")) for _, _, m in ohne)
    assert len(ohne) == len(meldungen) - 3


def test_weitere_pruefungen(tmp_path):
    daten = tmp_path / "daten"
    orgs = [
        {"id": "o1", "name": "TuS Berg e.V.", "typ": "Sonstiger Sportverein"},
        {"id": "o2", "name": "TuS Berg", "typ": "Sonstiger Sportverein"},  # fast gleich wie o1
        {"id": "o3", "name": "Ortsgemeinde Berg", "typ": "Ortsgemeinde", "ars": "071415001001"},
        {"id": "o4", "name": "Freunde des Sports"},  # ohne Art
    ]
    for o in orgs:
        schreibe_organisation(daten, o)
    licht_und_mass = {
        "id": "a1",
        "typ": "Spielfeld Eigenbau",  # Typ unbekannt: Fläche und Länge erlaubt
        "flutlicht": "nein",
        "lux": 200,
        "laenge": 100,
        "breite": 60,
        "flaeche": 9000,
        "sportarten": ["Fussball"],
    }
    zu = {"id": "a2", "typ": "Kleinspielfeld", "oeffnungsstunden": 500}
    bestand = [
        _st(
            S1,
            "Platz A",
            7.6012,
            50.3512,
            eigentuemer="Ortsgemeinde Berg",  # liegt in Koblenz
            eigentuemer_typ="Stadt/Gemeinde",  # passt zur Ortsgemeinde: kein Widerspruch
            betreiber="TuS Berg",
            betreiber_typ="Ortsgemeinde",  # widerspricht dem Verzeichnis
            nutzer=["TuS Berg", "SV Unbekannt"],
            sportarten=["Fußball", "Fussball"],
            adresse={"strasse": "Am Weg 12", "plz": "10115", "ort": "Koblenz"},
            anlagen=[licht_und_mass],
        ),
        _st(
            S2,
            "Platz B",
            7.6012,
            50.3512,
            sportarten=["Fußball"],
            adresse={"hausnummer": "3", "strasse": "", "plz": "56068", "ort": "Koblenz"},
        ),
        _st(
            S3,
            "Halle C",
            7.6012,
            50.3512,
            betriebsstatus="stillgelegt/geschlossen",
            adresse={"strasse": "Bundesstraße 412", "ort": "Koblenz"},
            anlagen=[zu],
        ),
        _st(
            S4,
            "Platz D",
            7.8012,
            50.3512,
            eigentuemer="Ortsgemeinde Berg",
            sportarten=["Fußball"],
            adresse={"ort": "Berg"},
        ),  # in Berg: passt
    ]
    schreibe_bestand(bestand, daten, "RP", lambda lon, lat: "07111-koblenz")
    nach = {}
    meldungen = pruefe(bestand, orgs, {"gemeinde": GEMEINDEN}, daten)
    assert {p for _, p, _ in meldungen} <= set(PRUEFUNGEN)
    for datei, _, m in meldungen:
        nach.setdefault(datei.rsplit("/", 1)[-1], []).append(m)

    assert nach[f"{S1}_meta.json"] == [
        "betreiber_typ: „Ortsgemeinde“, im Verzeichnis ist „TuS Berg“ aber „Sonstiger Sportverein“",
        "nutzer: „SV Unbekannt“ steht nicht im Verzeichnis der Organisationen",
        "adresse.plz: 10115 ist keine Postleitzahl in Rheinland-Pfalz",
        "adresse.strasse: „Am Weg 12“ – steht die Hausnummer in der Straße?",
        "sportarten: „Fussball“ – sonst meist „Fußball“ (3×)",
        "lage: Koordinate teilen sich 3 Sportstätten – Ersatzwert?",
        "eigentuemer: „Ortsgemeinde Berg“, die Sportstätte liegt aber in Koblenz, 7,0 km außerhalb",
    ]
    assert nach["a1.json"] == [
        "sportarten: „Fussball“ – sonst meist „Fußball“ (3×)",
        "lux: angegeben, aber Flutlicht „nein“",
        "flaeche: 9000 m², Länge × Breite ergibt aber 6000 m²",
    ]
    assert nach[f"{S2}_meta.json"] == [
        "adresse.hausnummer: angegeben, aber keine Straße",
        "lage: Koordinate teilen sich 3 Sportstätten – Ersatzwert?",
    ]
    assert nach[f"{S3}_meta.json"] == ["lage: Koordinate teilen sich 3 Sportstätten – Ersatzwert?"]
    assert nach["a2.json"] == [
        "oeffnungsstunden: angegeben, aber Betriebsstatus „stillgelegt/geschlossen“"
    ]
    assert f"{S4}_meta.json" not in nach
    assert nach["o4.json"] == ["typ: Art der Organisation fehlt"]
    assert nach["o1.json"] == ["name: fast gleich wie „TuS Berg“ (o2) – doppelt?"]
    assert nach["o2.json"] == ["name: fast gleich wie „TuS Berg e.V.“ (o1) – doppelt?"]
    assert "o3.json" not in nach
    pruefung = {m: p for _, p, m in meldungen}
    assert pruefung["adresse.plz: 10115 ist keine Postleitzahl in Rheinland-Pfalz"] == "PLZ"
    assert pruefung["lux: angegeben, aber Flutlicht „nein“"] == "Licht"
    assert pruefung["typ: Art der Organisation fehlt"] == "Organisation ohne Art"
    assert {p for m, p in pruefung.items() if m.startswith("betreiber_typ")} == {
        "Art der Organisation"
    }


def test_pruefungen_heissen_wie_in_der_readme():
    """Die Spalte „pruefung“ nennt die Prüfungen so wie der Abschnitt „Prüfungen“ der README."""
    readme = (Path(__file__).parents[1] / "README.md").read_text("utf-8")
    abschnitt = readme.split("## Prüfungen", 1)[1].split("\n## ", 1)[0]
    assert tuple(re.findall(r"^- \*\*(.+?):\*\*", abschnitt, re.MULTILINE)) == PRUEFUNGEN


def test_fast_gleiche_organisationen():
    from sportstaettenatlas.validate import fast_gleiche_organisationen

    orgs = [
        {"id": "a", "name": "SV Alsdorf e.V."},
        {"id": "b", "name": "SSV Alsdorf"},
        {"id": "c", "name": "TuS Berg", "lsb_nummer": "1000001"},
        {"id": "d", "name": "TuS Berg 1", "lsb_nummer": "1000002"},  # beide beim LSB: verschieden
        {"id": "e", "name": "TuS Berg e.V."},
        {"id": "f", "name": "Stadt Berg", "ars": "071110000000"},
    ]
    paare = [(x["id"], y["id"]) for x, y in fast_gleiche_organisationen(orgs)]
    assert paare == [("a", "b"), ("c", "e")]
