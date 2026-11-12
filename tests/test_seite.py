"""Webseite für GitHub Pages – ohne Geo-Bibliotheken testbar (synthetische Daten)."""

import json
import shutil
import subprocess

import pytest

from sportstaettenatlas import web
from sportstaettenatlas.seite import oeffentlich, schreibe_webseite


def _fc(*props):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": dict(p),
                "geometry": {"type": "Point", "coordinates": [7.6, 50.35]},
            }
            for p in props
        ],
    }


def _lies(pfad):
    return json.loads(pfad.read_text(encoding="utf-8"))


def test_kontaktdaten_werden_entfernt():
    fc, weg = oeffentlich(
        _fc(
            {
                "name": "Sportpark",
                "email": "info@verein.example",
                "email_quelle": "Atlas",
                "alt_email": "max.muster@example.org",
                "telefon": "0261 123456",
                "betreiber": "TuS Test (kontakt: vorstand@tus.example)",
                "alt_name": "Sportpark alt",
                "alt_stand": "2024",
                "verifikation": "ALKIS",
                "verifikation_sportstaette": "ALKIS",
            }
        )
    )
    p = fc["features"][0]["properties"]
    assert p == {"name": "Sportpark", "alt_name": "Sportpark alt", "verifikation": "ALKIS"}
    assert weg["email"] == 1 and weg["alt_email"] == 1 and weg["telefon"] == 1
    assert weg["E-Mail-Adresse in „betreiber“"] == 1


def test_webseite_verlinkt_app_und_laedt_daten_nach():
    seite = web.html_seite(
        "Atlas <RLP>", "©GeoBasis-DE / LVermGeoRP 2026", leaflet="vendor/leaflet"
    )
    assert '<script src="vendor/leaflet/leaflet.js"></script>' in seite
    assert "konfig.js?' + Date.now()" in seite and "const EINGEBETTET = null;" in seite
    assert '<link rel="stylesheet" href="app/stil.css?v=' in seite
    for name in web.SKRIPTE:
        assert f'<script src="app/{name}?v=' in seite
    assert 'id="laden"' in seite and 'id="analysewahl"' in seite
    assert "<h1>Atlas &lt;RLP&gt;</h1>" in seite
    assert "__" not in seite.split("<body>")[1].replace("__log", "")


def test_vorlagen():
    konfig = web.vorlage("konfig.js", "Mein Atlas")
    assert konfig.strip().startswith("//") and "window.KONFIG = {" in konfig
    assert konfig.rstrip().endswith("};") and 'titel: "Mein Atlas"' in konfig
    assert 'fehler_url: ""' in konfig and "ISSUE_TEMPLATE/fehler.yml" in konfig
    assert "vorschlag_parameter" not in konfig
    impressum = web.vorlage("impressum.html", "A & B")
    assert "Impressum – A &amp; B" in impressum and "__" not in impressum


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js nicht installiert")
def test_skripte_sind_gueltiges_javascript(tmp_path):
    for name in [*web.SKRIPTE, "vorlagen/konfig.js"]:
        datei = tmp_path / name.replace("/", "_")
        datei.write_text(web.datei(name), encoding="utf-8")
        ergebnis = subprocess.run(
            ["node", "--check", str(datei)], capture_output=True, text=True, check=False
        )
        assert ergebnis.returncode == 0, f"{name}: {ergebnis.stderr}"


def test_schreibe_webseite(tmp_path):
    docs = tmp_path / "docs"
    info = schreibe_webseite(
        docs, bestand=[_datensatz(1, 7.2, 50.5)], titel="Mein Atlas", leaflet_laden=False
    )
    assert (docs / ".nojekyll").exists() and (docs / "daten" / "index.html").exists()
    assert sorted(p.name for p in (docs / "app").iterdir()) == sorted([web.STIL, *web.SKRIPTE])
    assert info["neu_angelegt"] == ["konfig.js", "impressum.html", "datenschutz.html"]
    assert "GitHub Pages" in (docs / "datenschutz.html").read_text(encoding="utf-8")
    assert "unpkg.com/leaflet" in (docs / "index.html").read_text(encoding="utf-8")
    assert not (docs / "daten" / "analysen").exists()  # ohne Analysen kein Reiter
    # Datenbestand ohne ALKIS-Angaben (die stehen nur im Reiter „Analysen“)
    p = _lies(docs / "daten" / "bestand.geojson")["features"][0]["properties"]
    assert p["id"] == "RP-1" and "alkis" not in p

    # von Hand gepflegte Dateien werden nicht überschrieben, veraltete App-Dateien entfernt
    (docs / "konfig.js").write_text("window.KONFIG = {vorschlag_url: 'x'};", encoding="utf-8")
    (docs / "app" / "alt.js").write_text("", encoding="utf-8")
    info = schreibe_webseite(docs, leaflet_laden=False)
    assert info["neu_angelegt"] == []
    assert (docs / "konfig.js").read_text(
        encoding="utf-8"
    ) == "window.KONFIG = {vorschlag_url: 'x'};"
    assert not (docs / "app" / "alt.js").exists()


def _gebiete():
    """Zwei Gemeinden einer Verbandsgemeinde in einem Kreis (Rechtecke)."""

    def fc(ars, name, bez, w, s, o, n):
        return {
            "type": "Feature",
            "properties": {"ars": ars, "name": name, "bez": bez},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[w, s], [o, s], [o, n], [w, n], [w, s]]],
            },
        }

    return {
        "kreis": {
            "type": "FeatureCollection",
            "features": [fc("071370000000", "Mayen-Koblenz", "Landkreis", 7.0, 50.0, 8.0, 51.0)],
        },
        "vg": {
            "type": "FeatureCollection",
            "features": [fc("071375001000", "Maifeld", "Verbandsgemeinde", 7.0, 50.0, 8.0, 51.0)],
        },
        "gemeinde": {
            "type": "FeatureCollection",
            "features": [
                fc("071375001001", "Ort A", "Ortsgemeinde", 7.0, 50.0, 7.5, 51.0),
                fc("071375001002", "Ort B", "Ortsgemeinde", 7.5, 50.0, 8.0, 51.0),
            ],
        },
    }


def _datensatz(i, lon, lat, **mehr):
    return {
        "id": f"RP-{i}",
        "name": f"Platz {i}",
        "kategorie": "Sportplatz",
        "lage": {"lon": lon, "lat": lat},
        "quellen": {"atlas_rlp": {"id": str(i)}},
        **mehr,
    }


def test_webseite_mit_bestand_gebieten_und_analyse(tmp_path):
    from sportstaettenatlas import gebiete as gb

    gebiete = _gebiete()
    ars_von = gb.Zuordnung(gebiete["gemeinde"]).ars
    bestand = [
        _datensatz(1, 7.2, 50.5, betreiber="TuS Ort A e.V.", sportarten=["Fußball"]),
        _datensatz(2, 7.7, 50.5, betreiber="Ortsgemeinde Ort B", eigentuemer="kontakt@x.example"),
        _datensatz(3, 9.0, 50.5),
    ]
    analyse = (
        "ALKIS-Abgleich",
        {"punkte.geojson": _fc({"name": "A", "email": "a.b@example.org"}), "zahlen.json": {"n": 1}},
        {"punkte.geojson": "Punkte der Analyse"},
    )
    docs = tmp_path / "docs"
    info = schreibe_webseite(
        docs,
        bestand=bestand,
        gebiete=gebiete,
        analysen={"alkis": analyse},
        ars_von=ars_von,
        quellenvermerk="Q",
        leaflet_laden=False,
    )
    daten = docs / "daten"
    b = {
        f["properties"]["id"]: f["properties"] for f in _lies(daten / "bestand.geojson")["features"]
    }
    assert b["RP-1"]["ars"] == "071375001001" and b["RP-2"]["ars"] == "071375001002"
    assert "ars" not in b["RP-3"]  # außerhalb aller Gemeinden
    assert b["RP-1"]["betreiber_art"] == "Verein" and b["RP-2"]["betreiber_art"] == "Kommune"
    assert "eigentuemer" not in b["RP-2"]  # E-Mail-Adresse entfernt
    assert info["entfernt"] == {"E-Mail-Adresse in „eigentuemer“": 1, "email": 1}
    index = {e["s"]: e for e in _lies(daten / "gebiete.json")["eintraege"]}
    assert set(index) == {"07137", "071375001", "071375001001", "071375001002"}
    assert index["07137"]["e"] == "kreis" and index["07137"]["bb"] == [7.0, 50.0, 8.0, 51.0]
    assert _lies(daten / "gebiete_gemeinde.geojson")["features"][0]["properties"] == {
        "s": "071375001001"
    }
    # Analyse: eigener Ordner, Verzeichnis für den Reiter, Kontaktdaten entfernt
    assert _lies(daten / "analysen" / "index.json") == {
        "analysen": [
            {"name": "alkis", "titel": "ALKIS-Abgleich", "dateien": analyse[2]},
        ]
    }
    assert _lies(daten / "analysen/alkis/punkte.geojson")["features"][0]["properties"] == {
        "name": "A"
    }
    download = (daten / "index.html").read_text(encoding="utf-8")
    assert "bestand.geojson" in download and "analysen/alkis/punkte.geojson" in download
    assert "Punkte der Analyse" in download


def test_ohne_neue_analyse_bleibt_der_alte_stand(tmp_path):
    docs = tmp_path / "docs"
    daten = docs / "daten"
    daten.mkdir(parents=True)
    alt = '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":null}]}'
    # Ablage früherer Versionen direkt unter daten/ → wandert nach analysen/alkis/
    (daten / "sportanlagen.geojson").write_text(alt, encoding="utf-8")
    (daten / "gebiete.json").write_text("{}", encoding="utf-8")
    info = schreibe_webseite(docs, bestand=[_datensatz(1, 7.2, 50.5)], leaflet_laden=False)
    assert not (daten / "sportanlagen.geojson").exists()
    assert (daten / "analysen/alkis/sportanlagen.geojson").read_text(encoding="utf-8") == alt
    assert _lies(daten / "analysen/index.json")["analysen"][0]["name"] == "alkis"
    assert not (daten / "gebiete.json").exists()  # veraltete Auswahl entfernt
    assert [n for n, *_ in info["dateien"]] == [
        "bestand.geojson",
        "analysen/alkis/sportanlagen.geojson",
    ]

    # eine neue Rechnung ersetzt den ganzen Ordner der Analyse
    schreibe_webseite(
        docs, analysen={"alkis": ("ALKIS-Abgleich", {"neu.json": {}}, {})}, leaflet_laden=False
    )
    assert sorted(p.name for p in (daten / "analysen/alkis").iterdir()) == ["neu.json"]
