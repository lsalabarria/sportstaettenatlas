"""Altbestand (synthetische Daten im Import- bzw. Export-Format des bisherigen Atlas)."""

from sportstaettenatlas.atlas import dateien, lade_tabelle

KOPF = (
    "sportkomplex_id;sportkomplex_bezeichnung;sportkomplex_strasse;sportkomplex_hn;"
    "sportkomplex_plz;sportkomplex_ort;sportstaette_id;sportstaette_bezeichnung;"
    "sportstaette_typ_text;utm32nrechts;utm32nhoch;sportstaette_strasse;sportstaette_hn;"
    "sportstaette_plz;sportstaette_ort;sportanlage_id;sportanlage_typ_text\n"
)
ALT = KOPF + (
    "1;Sportpark Nord;Am Park;1;56068;Koblenz;1;Sportplatz Nord;Sportplatz;399100;5578050;"
    "Am Park;1;56068;Koblenz;1;Großspielfeld (ab 5.000 m²)\n"
    "1;Sportpark Nord;Am Park;1;56068;Koblenz;1;Sportplatz Nord;Sportplatz;399100;5578050;"
    "Am Park;1;56068;Koblenz;2;Weit- und Dreisprunganlage\n"
    "2;Halle X;;;;;2;Halle X;Sporthalle;;;;;;;3;Sporthalle (Größe unbekannt)\n"
)
NEU = KOPF + (
    "1;Sportpark Nord;Am Park;1;56068;Koblenz;1;Sportplatz Nord;Sportplatz;399100.4;5578049.8;"
    "Am Park;1;56068;Koblenz;1;Großspielfeld (ab 5.000 m²)\n"
    "1;Sportpark Nord;Am Park;1;56068;Koblenz;1;Sportplatz Nord;Sportplatz;399100.4;5578049.8;"
    "Am Park;1;56068;Koblenz;2;Großspielfeld (ab 5.000 m²)\n"
    "3;Schützen;;;;;3;Schießstand Süd;Schießsportstätte;401000;5579000;;;;;4;Schießstand\n"
)


def _ordner(tmp_path):
    p = tmp_path / "importe"
    p.mkdir()
    (p / "import_2024-09-18.csv").write_text(ALT, encoding="utf-8")
    (p / "import_2025-08-19.csv").write_text(NEU, encoding="utf-8")
    (p / "notizen.txt").write_text("keine CSV", encoding="utf-8")
    return p


def test_dateien(tmp_path):
    ordner = _ordner(tmp_path)
    assert [n for n, _ in dateien(ordner)] == ["import_2024-09-18.csv", "import_2025-08-19.csv"]
    assert [n for n, _ in dateien(ordner / "import_2025-08-19.csv")] == ["import_2025-08-19.csv"]


def test_lade_tabelle(tmp_path):
    df = lade_tabelle(_ordner(tmp_path))
    # Sportplatz Nord in zwei Importen → einmal, jüngste Datei gewinnt; Halle ohne Koordinate fehlt
    assert len(df) == 2
    nord = df[df["alt_name"] == "Sportplatz Nord"].iloc[0]
    assert nord["alt_datei"] == "import_2025-08-19.csv"
    assert nord["alt_anlagentypen"] == "2× Großspielfeld (ab 5.000 m²)"
    assert nord["alt_adresse"] == "Am Park 1, 56068 Koblenz"
    assert nord["alt_typgruppe"] == "spielfeld"
    schuetzen = df[df["alt_typ"] == "Schießsportstätte"].iloc[0]
    assert schuetzen["alt_typgruppe"] == "spezial"  # ß darf beim Nachschlagen nicht stören
    assert df["alt_id"].is_unique


def test_export_format(tmp_path):
    from sportstaettenatlas import atlas as altbestand

    kopf = (
        "ID,Name,Straße,Hausnummer,PLZ,Stadt,Sportstättenkategorie,Schulsport,"
        '"Öffentlicher Zugang","Zuschauerplätze Gesamt",Betriebsstatus,'
        '"Name des Eigentümers","Name des Betreibers",E-Mail,Webseite,Sportarten,'
        "Sportanlagen,Latitude,Longitude\n"
    )
    zeilen = (
        'a-1,Tennisplatz,"Am Weg",,11111,Musterdorf,Tennissportstätte,Nein,Nein,,'
        '"in Betrieb",,,,www.tc-muster.example,,"Tennisplatz, Tennishalle",5514805.26,402741.96\n'
        'a-2,"Sportplatz X",,,11111,Musterdorf,Sportplatz,Nein,Nein,,,,,,,,'
        '"Großspielfeld (ab 5.000 m², Rasen), Rundlaufbahn",5515000.0,403000.0\n'
    )
    datei = tmp_path / "sportstaetten_04112026.csv"
    datei.write_text("﻿" + kopf + zeilen, encoding="utf-8")
    df = altbestand.lade_tabelle(datei)
    assert len(df) == 2
    t = df[df["alt_atlas_id"] == "a-1"].iloc[0]
    assert (t["x"], t["y"]) == (402741.96, 5514805.26)  # Latitude/Longitude vertauscht → UTM
    assert t["alt_stand"] == "2026-11-04"
    assert t["alt_website"] == "www.tc-muster.example"
    assert t["alt_anzahl_anlagen"] == 2
    s = df[df["alt_atlas_id"] == "a-2"].iloc[0]
    assert s["alt_anzahl_anlagen"] == 2  # Komma in Klammern trennt nicht
