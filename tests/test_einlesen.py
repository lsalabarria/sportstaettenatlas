"""CSV-Dateien einlesen (einlesen.py) und in daten/ zusammenführen – synthetische Daten."""

import json

from sportstaettenatlas import einlesen, modell
from sportstaettenatlas.bestand import lies_bestand, schreibe_bestand


def _fake(a, b):  # Ersatz für pyproj
    return {"lon": round(b / 1e5, 6), "lat": round(a / 1e5, 6)} if a > 1e5 else {"lon": b, "lat": a}


def _kreis(lon, lat):
    return "07111-kreis-a"


def _csv(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="cp1252" if "ansi" in name else "utf-8")
    return p


STAETTEN = (
    "Name;Sportstättenkategorie;PLZ;Ort;Breitengrad;Längengrad;Schulsport;Zuschauerplätze;"
    "Betriebsstatus;Betreiber;Art des Betreibers;E-Mail;Farbe;Sportanlagen\n"
    "Sportplatz Musterdorf;sportplatz;11111;Musterdorf;50,35;7,59;X;1.200;IN BETRIEB;"
    'TuS Musterdorf;Sonstiger Sportverein;info@tus.example;blau;"Großspielfeld; Rundlaufbahn"\n'
    "Halle Musterdorf;Sporthalle;11111;Musterdorf;5514805,26;402741,96;0;viele;;;;;;\n"
)


def test_sportstaetten_lesen(tmp_path):
    p = _csv(tmp_path, "staetten_ansi.csv", STAETTEN)
    d, b = einlesen.lies_csv(p, lage_aus=_fake)
    assert b.art == "sportstaetten" and b.zeilen == 2
    assert b.kontakt == ["E-Mail"] and b.ignoriert == ["Farbe"]
    assert (
        b.spalten["Längengrad"] == "lage.lon" and b.spalten["Art des Betreibers"] == "betreiber_typ"
    )
    platz, halle = d
    assert platz["kategorie"] == "Sportplatz" and platz["betriebsstatus"] == "in Betrieb"
    assert platz["schulsport"] == "ja" and halle["schulsport"] == "nein"
    assert platz["zuschauerplaetze"] == 1200 and platz["lage"] == {"lon": 7.59, "lat": 50.35}
    assert platz["adresse"] == {"plz": "11111", "ort": "Musterdorf"}
    assert [a["typ"] for a in platz["anlagen"]] == ["Großspielfeld", "Rundlaufbahn"]
    assert halle["lage"] == {"lon": 4.027420, "lat": 55.148053}  # UTM erkannt
    assert halle["zuschauerplaetze"] == "viele" and b.nicht_lesbar == {"zuschauerplaetze": 1}
    assert "info@" not in json.dumps(d)
    # ohne ID: feste ID aus Name und Lage – gleiche Datei, gleiche IDs
    assert [x["id"] for x in einlesen.lies_csv(p, lage_aus=_fake)[0]] == [x["id"] for x in d]


def test_werte():
    p = modell.schema()["$defs"]["Sportanlage"]["properties"]
    assert einlesen.wert("Sand: 3; rasen=1", p["felder_je_belag"]) == {"Sand": 3, "Rasen": 1}
    assert einlesen.wert("2× Handball", p["felder_je_sportart"]) == {"Handball": 2}
    assert einlesen.wert("1.200.000", p["baukosten"]) == 1_200_000
    assert einlesen.wert("1.234,5", p["laenge"]) == 1234.5
    assert einlesen.wert("200", p["lux"]) == 200
    assert einlesen.wert("Fußball, Handball", p["sportarten"]) == ["Fußball", "Handball"]
    assert einlesen.wert("wahr", p["flutlicht"]) == "ja"


def test_sportanlagen_zusammenfuehren(tmp_path):
    ziel = tmp_path / "daten"
    platz = {
        "id": "s1",
        "name": "Sportplatz Musterdorf",
        "kategorie": "Sportplatz",
        "lage": {"lon": 7.5, "lat": 50.0},
        "betreiber": "TuS Musterdorf",
        "anlagen": [{"typ": "Großspielfeld"}, {"typ": "Rundlaufbahn"}],
    }
    schreibe_bestand([platz], ziel, "RP", _kreis)
    (vorher,) = lies_bestand(ziel)
    gross = next(a for a in vorher["anlagen"] if a["typ"] == "Großspielfeld")

    p = _csv(
        tmp_path,
        "anlagen.csv",
        "sportstaette_id,id,typ,Länge,bodenbelag_anz_sand,bodenbelag_anz_rasen,Flutlicht\n"
        f's1,{gross["id"][:8]},Großspielfeld,"105,5",,1,ja\n'
        "s1,,Kleinspielfeld,40,2,,\n"
        "s9,,Tennisplatz,,,,\n",
    )
    d, b = einlesen.lies_csv(p)
    assert b.art == "sportanlagen" and b.spalten["bodenbelag_anz_sand"] == "felder_je_belag[Sand]"
    e = schreibe_bestand(d, ziel, "RP", _kreis, modus="neu")
    assert (e.anlagen_neu, e.anlagen_geaendert, e.ohne_sportstaette) == (1, 0, 1)
    assert e.nicht_mehr_in_quelle == 0  # nur Anlagen eingelesen: zählt nicht
    e = schreibe_bestand(d, ziel, "RP", _kreis, modus="ergaenzen")
    assert (e.anlagen_neu, e.anlagen_geaendert) == (0, 1)
    (nachher,) = lies_bestand(ziel)
    a = {x["typ"]: x for x in nachher["anlagen"]}
    assert a["Großspielfeld"]["id"] == gross["id"]  # über die Kurz-ID gefunden
    assert a["Großspielfeld"]["laenge"] == 105.5 and a["Großspielfeld"]["flutlicht"] == "ja"
    assert a["Großspielfeld"]["felder_je_belag"] == {"Rasen": 1}
    assert a["Kleinspielfeld"]["felder_je_belag"] == {"Sand": 2}
    assert set(a) == {"Großspielfeld", "Rundlaufbahn", "Kleinspielfeld"}


def test_modi(tmp_path):
    ziel = tmp_path / "daten"
    alt = {
        "id": "s1",
        "name": "Alt",
        "kategorie": "Sportplatz",
        "lage": {"lon": 7.5, "lat": 50.0},
        "adresse": {"strasse": "Am Weg", "plz": "11111"},
    }
    schreibe_bestand([alt], ziel, "RP", _kreis)
    neu = {
        "id": "s1",
        "name": "Neu",
        "betreiber": "TuS",
        "adresse": {"plz": "22222", "ort": "X"},
        "website": "",
    }

    def staette():
        return next(lies_bestand(ziel))

    assert schreibe_bestand([neu], ziel, "RP", _kreis, "neu").behalten == 1
    assert staette()["name"] == "Alt"
    schreibe_bestand([neu], ziel, "RP", _kreis, "ergaenzen")
    s = staette()
    assert (s["name"], s["betreiber"]) == ("Alt", "TuS")
    assert s["adresse"] == {"strasse": "Am Weg", "plz": "11111", "ort": "X"}
    schreibe_bestand([neu], ziel, "RP", _kreis, "aktualisieren")
    s = staette()
    assert s["name"] == "Neu" and s["adresse"] == {"strasse": "Am Weg", "plz": "22222", "ort": "X"}
    assert s["kategorie"] == "Sportplatz"  # fehlt in der Quelle: bleibt


def test_vorlage_laesst_sich_einlesen(tmp_path):
    staetten, anlagen, orgs = einlesen.schreibe_vorlage(tmp_path)
    kopf = staetten.read_text("utf-8-sig").splitlines()[0].split(";")
    assert {"name", "kategorie", "lat", "lon", "betreiber_typ", "anlagen"} <= set(kopf)
    d, b = einlesen.lies_csv(staetten)
    assert b.ignoriert == [] and not b.nicht_lesbar
    assert (
        modell.pruefe(modell.Sportstaette, {k: v for k, v in d[0].items() if k != "anlagen"}) == []
    )
    d, b = einlesen.lies_csv(anlagen)
    assert b.art == "sportanlagen" and b.ignoriert == [] and not b.nicht_lesbar
    assert modell.pruefe(modell.Sportanlage, d[0]["anlagen"][0]) == []
    d, b = einlesen.lies_csv(orgs)
    assert b.art == "organisationen" and b.ignoriert == [] and not b.nicht_lesbar
    assert modell.pruefe(modell.Organisation, d[0]) == []


def test_organisationen(tmp_path):
    from sportstaettenatlas.bestand import (
        lies_organisationen,
        organisationen_aus_bestand,
        schreibe_organisationen,
    )
    from sportstaettenatlas.seite import bestand_geojson

    ziel = tmp_path / "daten"
    platz = {
        "id": "s1",
        "name": "Sportplatz",
        "kategorie": "Sportplatz",
        "lage": {"lon": 7.5, "lat": 50.0},
        "eigentuemer": "Ortsgemeinde Musterdorf",
        "betreiber": "TuS  Musterdorf",
        "nutzer": ["SV Nachbarort", "TuS Musterdorf"],
    }
    schreibe_bestand([platz], ziel, "RP", _kreis)
    bestand = list(lies_bestand(ziel))
    assert organisationen_aus_bestand(bestand, ziel) == 3  # TuS nur einmal
    assert organisationen_aus_bestand(bestand, ziel) == 0
    namen = sorted(o["name"] for o in lies_organisationen(ziel))
    assert namen == ["Ortsgemeinde Musterdorf", "SV Nachbarort", "TuS Musterdorf"]

    p = _csv(
        tmp_path,
        "vereine.csv",
        "Name;Art;Webseite;Weitere Schreibweisen\n"
        "tus musterdorf;Sportverein im LSB RLP;https://tus.example;TuS Musterdorf e.V.\n"
        "Neuer Verein;sonstiger sportverein;;\n",
    )
    d, b = einlesen.lies_csv(p)
    assert b.art == "organisationen"
    e = schreibe_organisationen(d, ziel, "ergaenzen")
    assert (e.neu, e.aktualisiert) == (1, 1)
    orgs = {o["name"]: o for o in lies_organisationen(ziel)}
    tus = orgs["TuS Musterdorf"]  # über den Namen gefunden, Name bleibt
    assert tus["typ"] == "Sportverein im LSB RLP" and tus["weitere_namen"] == [
        "TuS Musterdorf e.V."
    ]
    assert orgs["Neuer Verein"]["typ"] == "Sonstiger Sportverein"

    # Art aus dem Verzeichnis, wenn die Sportstätte keine nennt
    fc = bestand_geojson(bestand, organisationen=list(orgs.values()))
    p0 = fc["features"][0]["properties"]
    assert p0["betreiber_typ"] == "Sportverein im LSB RLP" and p0["betreiber_art"] == "Verein"
    assert p0["nutzer"] == ["SV Nachbarort", "TuS Musterdorf"]


def test_trennzeichen_aus_der_kopfzeile():
    from sportstaettenatlas.werte import trenner as _trenner

    assert _trenner('id;name;"Art, Typ"\n1;"a, b; c";x\n') == ";"
    assert _trenner('ID,Name,"Öffentlicher Zugang"\n1,"x; y",z\n') == ","
    assert _trenner("id\tname\n1\tx\n") == "\t"
