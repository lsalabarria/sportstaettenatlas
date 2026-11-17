"""Prüfungen aus validate.py – synthetische Daten."""

from sportstaettenatlas.bestand import schreibe_bestand
from sportstaettenatlas.validate import aehnlich, ort_passt, pruefe


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
    ],
}
ORGS = [{"id": "o1", "name": "TuS Berg", "weitere_namen": ["TuS Berg e.V."]}]
S1, S2, S3, S4 = (f"{i}{i}{i}{i}{i}{i}{i}{i}-1111-4111-8111-111111111111" for i in range(1, 5))


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
    ]
    schreibe_bestand(bestand, daten, "RP", lambda lon, lat: "07111-koblenz")
    meldungen = pruefe(bestand, ORGS, GEMEINDEN, daten)
    nach = {}
    for datei, m in meldungen:
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
    assert (
        nach[f"{S2}_meta.json"][0] == "adresse.ort: „Mainz“, die Koordinate liegt aber in Koblenz"
    )
    assert nach[f"{S4}_meta.json"] == ["lage: liegt in keiner Gemeinde von Rheinland-Pfalz"]
    assert f"{S3}_meta.json" not in nach

    # ohne Gemeinden entfallen Ort und Rheinland-Pfalz, der Rest bleibt
    ohne = pruefe(bestand, ORGS, None, daten)
    assert not any(m.startswith(("adresse.ort", "lage")) for _, m in ohne)
    assert len(ohne) == len(meldungen) - 2
