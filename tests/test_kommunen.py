"""Gebietskörperschaften als Organisationen – synthetische Gebiete."""

import json

from sportstaettenatlas.bestand import (
    lies_organisationen,
    org_dateien,
    organisationen_einordnen,
    schreibe_organisation,
)
from sportstaettenatlas.pflege.kommunen import aus_gebieten, lege_an


def _fc(*eintraege):
    return {"features": [{"properties": dict(zip(("ars", "name", "bez"), e))} for e in eintraege]}


# Land 07: Landkreis 07901 mit VG 079015001 und
# verbandsfreier Stadt 079010002; Landkreis 07903 mit VG 079035001 (zweites „Berg“);
# kreisfreie Stadt 07902 (in VG250 auch als
# verbandsfreie Gemeinde und als Gemeinde geführt)
GEBIETE = {
    "kreis": _fc(
        ("07901", "Musterland", "Landkreis"),
        ("07902", "Musterstadt", "Kreisfreie Stadt"),
        ("07903", "Talland", "Landkreis"),
    ),
    "vg": _fc(
        ("079015001", "Am Berg", "Verbandsgemeinde"),
        ("079010002", "Neustadt", "Verbandsfreie Gemeinde"),
        ("079020000", "Musterstadt", "Verbandsfreie Gemeinde"),
        ("079035001", "Tal", "Verbandsgemeinde"),
    ),
    "gemeinde": _fc(
        ("079015001001", "Berg", "Gemeinde"),
        ("079015001002", "Burgstadt", "Stadt"),
        ("079010002002", "Neustadt", "Stadt"),
        ("079020000000", "Musterstadt", "Stadt"),
        ("079035001001", "Berg", "Gemeinde"),
    ),
}


def test_aus_gebieten():
    o = {x["ars"]: x for x in aus_gebieten(GEBIETE)}
    assert {k: (v["name"], v["typ"]) for k, v in o.items()} == {
        "07901": ("Landkreis Musterland", "Landkreis"),
        "07902": ("Stadt Musterstadt", "Kreisfreie Stadt"),  # nur einmal
        "07903": ("Landkreis Talland", "Landkreis"),
        "079015001": ("Verbandsgemeinde Am Berg", "Verbandsgemeinde"),
        "079010002": ("Stadt Neustadt", "Verbandsfreie Gemeinde"),
        "079035001": ("Verbandsgemeinde Tal", "Verbandsgemeinde"),
        "079015001001": ("Ortsgemeinde Berg (VG Am Berg)", "Ortsgemeinde"),
        "079015001002": ("Stadt Burgstadt", "Verbandsangehörige Stadt"),
        "079035001001": ("Ortsgemeinde Berg (VG Tal)", "Ortsgemeinde"),
    }
    assert o["079015001002"]["uebergeordnet"] == "Verbandsgemeinde Am Berg"
    assert o["079015001"]["uebergeordnet"] == "Landkreis Musterland"
    assert o["079015001"]["weitere_namen"] == ["VG Am Berg"]
    assert o["07902"]["weitere_namen"] == ["Musterstadt"]
    assert "weitere_namen" not in o["079015001001"]  # „Gemeinde Berg“ gäbe es zweimal


def test_lege_an_und_ordner(tmp_path):
    daten = tmp_path / "daten"
    schreibe_organisation(daten, {"id": "a1", "name": "Musterstadt"})  # Ebene erkennt der Name
    schreibe_organisation(
        daten, {"id": "a2", "name": "Musterland, Landkreis", "website": "https://k.example"}
    )
    schreibe_organisation(daten, {"id": "a3", "name": "TuS Berg", "typ": "Sonstiger Sportverein"})
    (daten / "organisationen" / "alt.json").write_text(json.dumps({"id": "alt", "name": "X"}))

    assert organisationen_einordnen(daten) == 1  # die Datei aus dem alten flachen Aufbau
    b = lege_an(daten, GEBIETE)
    assert (b.neu, b.ergaenzt, b.mehrdeutig) == (7, 2, [])
    assert sorted(b.umbenannt) == [
        ("Musterland, Landkreis", "Landkreis Musterland"),
        ("Musterstadt", "Stadt Musterstadt"),
    ]
    verstoesse = []
    orgs = {o["id"]: o for o in lies_organisationen(daten, verstoesse)}
    assert verstoesse == []
    assert orgs["a1"]["typ"] == "Kreisfreie Stadt" and orgs["a1"]["weitere_namen"] == [
        "Musterstadt"
    ]
    assert orgs["a2"]["website"] == "https://k.example"
    assert "Musterland, Landkreis" in orgs["a2"]["weitere_namen"]
    pfade = {p.stem: p.relative_to(daten).as_posix() for p in org_dateien(daten)}
    assert pfade["a1"] == "organisationen/RP/kreisfreie-stadt/a1.json"
    assert pfade["a3"] == "organisationen/RP/sonstiger-sportverein/a3.json"
    assert pfade["alt"] == "organisationen/RP/ohne-art/alt.json"

    assert lege_an(daten, GEBIETE).unveraendert == 9  # zweiter Lauf: nichts zu tun

    # Art geändert → Datei zieht um; liegt sie falsch, meldet lies_organisationen das
    schreibe_organisation(daten, {**orgs["a3"], "typ": "Sportverein im LSB RLP"})
    assert {p.stem: p.parent.name for p in org_dateien(daten)}["a3"] == "sportverein-im-lsb-rlp"
    falsch = daten / "organisationen" / "RP" / "landkreis" / "a3.json"
    (daten / "organisationen" / "RP" / "sportverein-im-lsb-rlp" / "a3.json").rename(falsch)
    verstoesse = []
    lies_organisationen(daten, verstoesse)
    assert [m for _, m in verstoesse] == ["Ordner passt nicht zur Art (einordnen)"]
    assert organisationen_einordnen(daten) == 1
