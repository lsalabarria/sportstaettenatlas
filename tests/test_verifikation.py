import pandas as pd

from sportstaettenatlas.analysen.alkis.verifikation import (
    FELDER_ANLAGE,
    FELDER_STAETTE,
    verifiziere,
    zusammenfuehren,
)


def _daten():
    staetten = pd.DataFrame(
        {
            "sportstaette_id": ["ST1", "ST2", "ST3"],
            "name": ["Sportpark Oberwerth", None, None],
            "alt_id": ["A1", "A2", None],
            "alt_name": ["Stadion Oberwerth", "Freibad Test", None],
            "alt_betreiber": ["Stadtwerke", None, None],
            "alt_website": [None, "www.bad.example", None],
        }
    )
    anlagen = pd.DataFrame(
        {
            "anlage_id": ["SA1", "SA2", "SA3", "SA4"],
            "sportstaette_id": ["ST1", "ST1", "ST2", "ST3"],
            "name": ["Kunstrasen", None, None, None],
            "typ": ["sportplatz", "laufbahn", "freibad", "tennisanlage"],
        }
    )
    return staetten, anlagen


def test_zusammenfuehren_mit_quelle():
    st, an = _daten()
    st = zusammenfuehren(st, FELDER_STAETTE)
    assert st.loc[0, "name"] == "Sportpark Oberwerth" and st.loc[0, "name_quelle"] == "ALKIS"
    assert st.loc[1, "name"] == "Freibad Test"
    assert st.loc[1, "name_quelle"] == "Sportstättenatlas RLP"
    assert st.loc[0, "betreiber"] == "Stadtwerke"
    assert st.loc[1, "website_quelle"] == "Sportstättenatlas RLP"
    assert st.loc[2, "name"] is None and st.loc[2, "name_quelle"] is None
    an = zusammenfuehren(an, FELDER_ANLAGE)
    assert an.loc[0, "name_quelle"] == "ALKIS" and an.loc[1, "name_quelle"] is None


def test_verifikation():
    st, an = _daten()
    st, an = verifiziere(st, an)
    assert st.loc[0, "verifikation"] == "ALKIS, Sportstättenatlas RLP"
    assert st.loc[0, "verifikation_anzahl"] == 2
    assert list(st["verifikation_stufe"]) == ["bestätigt", "bestätigt", "nur ALKIS"]
    assert set(st["verifikation_stufe"]) <= {"nur ALKIS", "bestätigt", "nur ALKIS – unbestimmt"}
    # Anlagen übernehmen die Verifikation ihrer Sportstätte
    assert list(an["verifikation_stufe"]) == ["bestätigt", "bestätigt", "bestätigt", "nur ALKIS"]
    assert an.loc[2, "verifikation_sportstaette"] == "ALKIS, Sportstättenatlas RLP"


def test_datum_text_gemischt():
    import datetime as dt

    from sportstaettenatlas.hilfen import datum_text as _datum_text

    s = pd.Series([pd.Timestamp("2025-03-26"), None, dt.date(2024, 1, 2), "2022-04-19", "unklar"])
    assert list(_datum_text(s)) == ["2025-03-26", None, "2024-01-02", "2022-04-19", "unklar"]


def test_fortschritt_ohne_fehler():
    from sportstaettenatlas.hilfen import Fortschritt, logging_mit_balken

    with logging_mit_balken(), Fortschritt(3, "Test", "Schritt") as fb:
        for _ in range(3):
            fb.info(ok=1, fehler=0)
            fb.text("Test: läuft")
            fb.weiter()


def test_nur_alkis_unbestimmt():
    st = pd.DataFrame(
        {"sportstaette_id": ["S1", "S2", "S3", "S4"], "alt_id": [None, None, "A1", None]}
    )
    an = pd.DataFrame(
        {
            "anlage_id": ["A1", "A2", "A3", "A4", "A5", "A6"],
            "sportstaette_id": ["S1", "S2", "S2", "S3", "S4", "S4"],
            "typ": [
                "sportanlage_unbestimmt",
                "sportanlage_unbestimmt",
                "sporthalle",
                "sportanlage_unbestimmt",
                "sportanlage_unbestimmt",
                "nebengebaeude_sport",
            ],
            "rolle": ["sportanlage"] * 5 + ["zubehoer"],
        }
    )
    st, an = verifiziere(st, an)
    stufe = dict(zip(st["sportstaette_id"], st["verifikation_stufe"]))
    assert stufe["S1"] == "nur ALKIS – unbestimmt"
    assert stufe["S2"] == "nur ALKIS"  # Halle darin: kein Sammelbegriff allein
    assert stufe["S3"] == "bestätigt"  # der Atlas kennt sie
    assert stufe["S4"] == "nur ALKIS – unbestimmt"  # Nebengebäude zählt nicht
    assert an.loc[2, "verifikation_stufe"] == "nur ALKIS"
    assert an.loc[0, "verifikation_stufe"] == "nur ALKIS – unbestimmt"
