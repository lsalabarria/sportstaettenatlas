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
    assert '<script src="konfig.js"></script>' in seite and 'type="module"' in seite
    assert "daten/sportstaetten.geojson" in seite and 'id="laden"' in seite
    assert "<h1>Atlas &lt;RLP&gt;</h1>" in seite
    assert "__" not in seite.split("<body>")[1].replace("__log", "")


def test_eine_datei_bleibt_wie_bisher():
    seite = html_seite(_fc({"name": "</script>x"}), _fc(), "T", "Q")
    assert (
        seite.count("</script>") == 2
        and 'src="konfig.js"' not in seite
        and 'id="laden"' not in seite
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
