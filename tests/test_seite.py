"""Webseite für GitHub Pages – ohne Geo-Bibliotheken testbar (synthetische Daten)."""

import json

from sportstaettenatlas import karte
from sportstaettenatlas.karte import html_seite
from sportstaettenatlas.seite import KONFIG_VORLAGE, oeffentlich, schreibe_webseite


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


def test_webseite_laedt_daten_nach():
    seite = html_seite(
        None,
        None,
        "Atlas <RLP>",
        "©GeoBasis-DE / LVermGeoRP 2026",
        webseite=True,
        leaflet="vendor/leaflet",
    )
    assert '<script src="vendor/leaflet/leaflet.js"></script>' in seite
    assert '<script src="konfig.js"></script>' in seite and "const EINGEBETTET = null;" in seite
    assert '"sportstaetten.geojson"' in seite and "bestand.geojson" in seite
    assert 'id="laden"' in seite
    assert "<h1>Atlas &lt;RLP&gt;</h1>" in seite
    assert "__" not in seite.split("<body>")[1].replace("__log", "")


def test_eine_datei_bleibt_wie_bisher():
    seite = html_seite(_fc({"name": "</script>x"}), _fc(), "T", "Q")
    assert (
        seite.count("</script>") == 2
        and 'src="konfig.js"' not in seite
        and 'id="laden"' not in seite
        and '"sportanlagen.geojson": {' in seite
    )
    assert "<\\/script>x" in seite


def test_schreibe_webseite(tmp_path, monkeypatch):
    reihe = iter([_fc({"name": "Halle", "email": "a.b@example.org"}), _fc({"typ": "sporthalle"})])
    monkeypatch.setattr(karte, "geojson", lambda gdf, **kw: next(reihe))
    info = schreibe_webseite(
        None, None, tmp_path / "docs", "Quelle", None, titel="Mein Atlas", leaflet_laden=False
    )
    docs = tmp_path / "docs"
    assert (docs / ".nojekyll").exists() and (docs / "daten" / "index.html").exists()
    st = json.loads((docs / "daten" / "sportstaetten.geojson").read_text(encoding="utf-8"))
    assert st["features"][0]["properties"] == {"name": "Halle"}
    assert info["entfernt"] == {"email": 1}
    assert info["neu_angelegt"] == ["konfig.js", "impressum.html", "datenschutz.html"]
    impressum = (docs / "impressum.html").read_text(encoding="utf-8")
    assert "Impressum – Mein Atlas" in impressum and "<mark>" in impressum and "__" not in impressum
    assert "GitHub Pages" in (docs / "datenschutz.html").read_text(encoding="utf-8")
    assert 'titel: "Mein Atlas"' in (docs / "konfig.js").read_text(encoding="utf-8")
    assert "unpkg.com/leaflet" in (docs / "index.html").read_text(encoding="utf-8")

    # konfig.js wird beim nächsten Lauf nicht überschrieben
    (docs / "konfig.js").write_text("window.KONFIG = {vorschlag_url: 'x'};", encoding="utf-8")
    reihe = iter([_fc(), _fc()])
    monkeypatch.setattr(karte, "geojson", lambda gdf, **kw: next(reihe))
    info = schreibe_webseite(None, None, docs, leaflet_laden=False)
    assert info["neu_angelegt"] == []
    assert (docs / "konfig.js").read_text(
        encoding="utf-8"
    ) == "window.KONFIG = {vorschlag_url: 'x'};"


def test_konfig_vorlage_ist_gueltiges_javascript():
    assert KONFIG_VORLAGE.strip().startswith("//") and "window.KONFIG = {" in KONFIG_VORLAGE
    assert KONFIG_VORLAGE.rstrip().endswith("};")


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


def test_webseite_mit_bestand_und_gebieten(tmp_path, monkeypatch):
    import pandas as pd

    reihe = iter(
        [
            _fc({"sportstaette_id": "ST1", "lon": 7.6, "lat": 50.35}),
            _fc({"sportstaette_id": "ST1", "typ": "halle"}),
        ]
    )
    monkeypatch.setattr(karte, "geojson", lambda gdf, **kw: next(reihe))
    abgleich = pd.DataFrame(
        {
            "alt_atlas_id": ["1", "2"],
            "status": ["zugeordnet", "nah"],
            "lon": [7.2, 7.7],
            "lat": [50.5, 50.5],
        }
    )
    bestand = [
        _datensatz(1, 7.2, 50.5, betreiber="TuS Ort A e.V.", sportarten=["Fußball"]),
        _datensatz(2, 7.7, 50.5, betreiber="Ortsgemeinde Ort B", eigentuemer="kontakt@x.example"),
        _datensatz(3, 9.0, 50.5),
    ]
    docs = tmp_path / "docs"
    info = schreibe_webseite(
        None, None, docs, "Q", abgleich, bestand=bestand, gebiete=_gebiete(), leaflet_laden=False
    )
    lies = lambda n: json.loads((docs / "daten" / n).read_text(encoding="utf-8"))
    b = {f["properties"]["id"]: f["properties"] for f in lies("bestand.geojson")["features"]}
    assert b["RP-1"]["ars"] == "071375001001" and b["RP-2"]["ars"] == "071375001002"
    assert "ars" not in b["RP-3"]  # außerhalb aller Gemeinden
    assert b["RP-1"]["betreiber_art"] == "Verein" and b["RP-2"]["betreiber_art"] == "Kommune"
    assert b["RP-1"]["alkis"] == "in ALKIS" and b["RP-2"]["alkis"] == "ALKIS in der Nähe"
    assert b["RP-3"]["alkis"] == "ohne Abgleich"
    assert "eigentuemer" not in b["RP-2"] and info["entfernt"]  # E-Mail-Adresse entfernt
    # Anlagen erben den Schlüssel ihrer Sportstätte
    assert lies("sportanlagen.geojson")["features"][0]["properties"]["ars"] == "071375001002"
    index = {e["s"]: e for e in lies("gebiete.json")["eintraege"]}
    assert set(index) == {"07137", "071375001", "071375001001", "071375001002"}
    assert index["07137"]["e"] == "kreis" and index["07137"]["bb"] == [7.0, 50.0, 8.0, 51.0]
    assert lies("gebiete_gemeinde.geojson")["features"][0]["properties"] == {"s": "071375001001"}
    assert "bestand.geojson" in (docs / "daten" / "index.html").read_text(encoding="utf-8")


def test_ohne_pipeline_bleibt_verifikation_erhalten(tmp_path):
    docs = tmp_path / "docs"
    (docs / "daten").mkdir(parents=True)
    alt = '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":null}]}'
    (docs / "daten" / "sportanlagen.geojson").write_text(alt, encoding="utf-8")
    (docs / "daten" / "gebiete.json").write_text("{}", encoding="utf-8")
    info = schreibe_webseite(
        None,
        None,
        docs,
        bestand=[_datensatz(1, 7.2, 50.5)],
        verifikation=False,
        leaflet_laden=False,
    )
    assert (docs / "daten" / "sportanlagen.geojson").read_text(encoding="utf-8") == alt
    assert not (docs / "daten" / "gebiete.json").exists()  # veraltete Auswahl entfernt
    assert [n for n, *_ in info["dateien"]] == ["bestand.geojson", "sportanlagen.geojson"]
