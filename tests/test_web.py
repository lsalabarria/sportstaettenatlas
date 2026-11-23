"""Die Webseite im Browser: Ansichten, Vorschlagsformular, Organisationssuche, Liste, Übersicht.

Baut die Seite aus synthetischen Daten, startet einen lokalen Webserver und steuert ein
unsichtbares Chromium (Playwright). Anfragen ins Internet (Kartenkacheln, Ortssuche) werden
blockiert. Ohne Playwright oder ohne installiertes Chromium werden die Tests übersprungen:

    uv sync && uv run playwright install chromium
"""

import functools
import http.server
import json
import shutil
import threading
import urllib.parse
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from sportstaettenatlas import gebiete as gb
from sportstaettenatlas import modell, seite

WURZEL = Path(__file__).resolve().parents[1]
UMFRAGE = "https://umfrage.example/index.php/1"

ORGANISATIONEN = [
    {"id": "o-tus", "name": "TuS Berg", "typ": "Sonstiger Sportverein"},
    {"id": "o-berg", "name": "Ortsgemeinde Berg (VG Tal)", "typ": "Ortsgemeinde"},
    {"id": "o-bergen", "name": "Ortsgemeinde Bergen", "typ": "Ortsgemeinde"},
    {
        "id": "o-vg",
        "name": "Verbandsgemeinde Tal",
        "typ": "Verbandsgemeinde",
        "weitere_namen": ["VG Tal"],
    },
]
BESTAND = [
    {
        "id": "11111111-1111-4111-8111-111111111111",
        "name": "Sportplatz Berg",
        "kategorie": "Sportplatz",
        "adresse": {"strasse": "Am Weg", "hausnummer": "1", "plz": "56068", "ort": "Berg"},
        "lage": {"lon": 7.5938, "lat": 50.3512},
        "betreiber": "TuS Berg",
        "sportkomplex": "dddddddd-4444-4444-8444-444444444444",
        "sportarten": ["Fußball"],
        "anlagen": [
            {
                "id": "aaaaaaaa-1111-4111-8111-111111111111",
                "typ": "Großspielfeld",
                "sportarten": ["Fußball"],
            },
            {"id": "bbbbbbbb-2222-4222-8222-222222222222", "typ": "Rundlaufbahn"},
        ],
    },
    {
        "id": "22222222-2222-4222-8222-222222222222",
        "name": "Tennisanlage Bergen",
        "kategorie": "Tennissportstätte",
        "lage": {"lon": 7.7012, "lat": 50.4034},
        "sportkomplex": "dddddddd-4444-4444-8444-444444444444",
        "sportarten": ["Tennis"],
        "anlagen": [{"id": "cccccccc-3333-4333-8333-333333333333", "typ": "Tennisplatz"}],
    },
    {  # ohne Sportkomplex und ohne Anlagen
        "id": "33333333-3333-4333-8333-333333333333",
        "name": "Bolzplatz Tal",
        "kategorie": "Sportplatz",
        "lage": {"lon": 7.8023, "lat": 50.2045},
    },
]
SID = BESTAND[0]["id"]
KOMPLEX = {"id": "dddddddd-4444-4444-8444-444444444444", "name": "Sportzentrum Berg"}
T3 = "33333333-3333-4333-8333-333333333333"
STUETZPUNKTE = [
    {  # über den Sportkomplex: Sportplatz Berg und Tennisanlage Bergen
        "id": "eeeeeeee-5555-4555-8555-555555555555",
        "name": "Bundesstützpunkt Tennis Berg",
        "art": "Bundesstützpunkt",
        "sportarten": ["Tennis"],
        "gueltig_bis": "2028-12-31",
        "sportkomplexe": [KOMPLEX["id"]],
    },
    {
        "id": "eeeeeeee-6666-4666-8666-666666666666",
        "name": "Landesstützpunkt Fußball Tal",
        "art": "Landesstützpunkt",
        "sportarten": ["Fußball"],
        "gueltig_bis": "2020-12-31",
        "sportstaetten": [T3],
    },
]


def _leaflet() -> Path:
    """Leaflet lokal: aus docs/vendor, sonst einmal nach results/cache geladen."""
    for ordner in (
        WURZEL / "docs" / "vendor" / "leaflet",
        WURZEL / "results" / "cache" / "leaflet",
    ):
        if all((ordner / d).exists() for d in seite.LEAFLET_DATEIEN):
            return ordner
    ziel = WURZEL / "results" / "cache" / "leaflet"
    if not seite.leaflet_lokal(ziel):
        pytest.skip("Leaflet nicht verfügbar (kein docs/vendor, kein Netz)")
    return ziel


class _Leise(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keine Zeile je Anfrage in der Testausgabe
        pass


def _rechteck(ars, name, bez, w, s, o, n):
    return {
        "type": "Feature",
        "properties": {"ars": ars, "name": name, "bez": bez},
        "geometry": {"type": "Polygon", "coordinates": [[[w, s], [o, s], [o, n], [w, n], [w, s]]]},
    }


def _ebene(*features):
    return {"type": "FeatureCollection", "features": list(features)}


# Ein Kreis mit einer Gemeinde, darin alle drei Sportstätten (synthetisch, ein Rechteck)
GEBIETE = {
    "kreis": _ebene(_rechteck("071370000000", "Kreis Berg", "Landkreis", 7.5, 50.1, 7.9, 50.5)),
    "vg": _ebene(_rechteck("071375001000", "VG Berg", "Verbandsgemeinde", 7.5, 50.1, 7.9, 50.5)),
    "gemeinde": _ebene(_rechteck("071375001001", "Bergland", "Ortsgemeinde", 7.5, 50.1, 7.9, 50.5)),
}


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    docs = tmp_path_factory.mktemp("docs")
    shutil.copytree(_leaflet(), docs / "vendor" / "leaflet")
    seite.schreibe_webseite(
        docs,
        bestand=BESTAND,
        organisationen=ORGANISATIONEN,
        sportkomplexe=[KOMPLEX],
        stuetzpunkte=STUETZPUNKTE,
        gebiete=GEBIETE,
        ars_von=gb.Zuordnung(GEBIETE["gemeinde"]).ars,
    )
    konfig = docs / "konfig.js"
    konfig.write_text(
        konfig.read_text("utf-8").replace('vorschlag_url: ""', f'vorschlag_url: "{UMFRAGE}"'),
        "utf-8",
    )
    handler = functools.partial(_Leise, directory=str(docs))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001 – Chromium nicht installiert
            pytest.skip(
                f"Chromium nicht verfügbar ({exc.__class__.__name__}): playwright install chromium"
            )
        yield b
        b.close()


@pytest.fixture
def oeffne(browser, url):
    """oeffne("#ansicht=…") → Seite, fertig geladen. Jeder JavaScript-Fehler lässt den Test
    scheitern; window.open merkt sich die Adresse, statt einen Tab zu öffnen."""
    kontext = browser.new_context(viewport={"width": 1400, "height": 1000})
    kontext.route("https://**", lambda r: r.abort())
    fehler: list[str] = []

    def oeffne_(hash_: str = ""):
        page = kontext.new_page()
        page.on("pageerror", lambda e: fehler.append(str(e)))
        page.add_init_script(
            "window.__url = null; window.open = u => { window.__url = u; };"
            "Element.prototype.scrollIntoView = function () {};"
        )
        page.goto(url + hash_)
        page.wait_for_selector("#laden", state="hidden", timeout=30_000)
        return page

    yield oeffne_
    kontext.close()
    assert fehler == [], fehler


def _gesendet(page) -> dict:
    """Der Vorschlag, den das Formular an die Umfrage übergeben hat."""
    u = page.evaluate("window.__url")
    assert u and u.startswith(UMFRAGE), page.inner_text("#v-fehler")
    return json.loads(dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(u).query))["data"])


def _senden(page) -> None:
    page.click(".knopf-gross")
    page.wait_for_timeout(100)


# --- Ansichten -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hash_",
    ["", "#ansicht=liste", "#ansicht=uebersicht", "#ansicht=vorschlag", "#ansicht=analysen"],
)
def test_ansicht_laedt_ohne_fehler(oeffne, hash_):
    page = oeffne(hash_)
    assert page.title()


def test_koordinaten_mit_google_maps_und_luftbild(oeffne):
    page = oeffne()
    zeile = page.evaluate("koord(50.4555, 7.2885)")
    assert "google.com/maps?q=50.455500%2C%207.288500" in zeile and ">Luftbild</a>" in zeile
    url = page.evaluate("luftbildUrl(50.4555, 7.2885)")
    assert url.startswith("https://geo4.service24.rlp.de/wms/rp_dop20.fcgi?")
    bbox = [
        float(x)
        for x in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["BBOX"][0].split(",")
    ]
    assert (
        abs((bbox[0] + bbox[2]) / 2 - 7.2885) < 1e-6
        and abs((bbox[1] + bbox[3]) / 2 - 50.4555) < 1e-6
    )
    assert round((bbox[3] - bbox[1]) * 111320) == 200  # etwa 200 m hoch


def test_sportkomplex_im_popup_und_formular(oeffne):
    page = oeffne()
    zeile = page.evaluate(f"komplexZeile('{KOMPLEX['id']}', '{SID}')")
    assert "<b>Sportzentrum Berg</b>" in zeile and 'data-details="22222222' in zeile
    assert "Sportplatz Berg" not in zeile  # die Sportstätte selbst steht nicht in der Liste
    page.evaluate(f"ANSICHTEN.vorschlag.bearbeite('{SID}')")
    feld = page.locator('#seite-vorschlag select[name="sportkomplex"]')
    assert feld.input_value() == KOMPLEX["id"]
    assert feld.locator("option:checked").inner_text().startswith("Sportzentrum Berg")
    # neue Sportstätte mitten im Komplex: er steht zur Auswahl, gewählt ist keiner
    page.evaluate("ANSICHTEN.vorschlag.neu({ lage: { lat: 50.3773, lon: 7.6475 } })")
    assert feld.input_value() == ""
    assert [o.split(" (")[0] for o in feld.locator("option").all_inner_texts()] == [
        "kein Sportkomplex",
        "Sportzentrum Berg",
        "+ neuer Sportkomplex …",
    ]


def test_uebersicht_zeigt_bestand_und_befuellung(oeffne):
    page = oeffne("#ansicht=uebersicht")
    titel = page.locator("#seite-uebersicht h2.teil-titel").all_inner_texts()
    assert titel == ["Bestand", "Befüllung"]
    kacheln = dict(
        zip(
            page.locator("#seite-uebersicht .kachel .label").all_inner_texts(),
            page.locator("#seite-uebersicht .kachel .wert").all_inner_texts(),
        )
    )
    assert kacheln["Sportstätten"] == "3" and kacheln["Sportanlagen"] == "3"
    assert kacheln["Sportkomplexe"] == "1"
    assert (
        kacheln["Olympiastützpunkte"],
        kacheln["Bundesstützpunkte"],
        kacheln["Landesstützpunkte"],
    ) == ("0", "1", "1")
    page.select_option("[data-u-sport]", "Tennis")
    page.wait_for_timeout(100)
    kacheln = dict(
        zip(
            page.locator("#seite-uebersicht .kachel .label").all_inner_texts(),
            page.locator("#seite-uebersicht .kachel .wert").all_inner_texts(),
        )
    )
    assert kacheln["Sportstätten"] == "1" and kacheln["Bundesstützpunkte"] == "1"
    assert kacheln["Landesstützpunkte"] == "0"
    # auch ohne Sportkomplexe: Auswahl in der Liste und Kachel bleiben
    page.evaluate("SPORTKOMPLEXE.clear()")
    assert 'data-f="komplex"' in page.evaluate("komplexAuswahlHtml('')")


def test_liste_filtert_nach_sportart(oeffne):
    page = oeffne("#ansicht=liste")
    assert page.locator("table.liste tr.zeile").count() == 3
    page.select_option('[data-f="sportart"]', "Tennis")
    page.wait_for_timeout(100)
    zeilen = page.locator("table.liste tr.zeile").all_inner_texts()
    assert len(zeilen) == 1 and "Tennisanlage Bergen" in zeilen[0]


def test_nach_sportkomplex_filtern(oeffne):
    page = oeffne("#ansicht=liste")
    page.select_option('[data-f="komplex"]', "*")
    page.wait_for_timeout(100)
    assert page.locator("table.liste tr.zeile").count() == 2
    page.select_option('[data-f="komplex"]', KOMPLEX["id"])
    page.wait_for_timeout(100)
    namen = page.locator("table.liste tr.zeile td:first-child").all_inner_texts()
    assert sorted(namen) == ["Sportplatz Berg", "Tennisanlage Bergen"]
    assert "komplex=dddddddd" in page.evaluate("location.hash")
    # Teil „Sportkomplexe“: Klick auf eine Zeile zeigt ihre Sportstätten
    page.click('[data-teil="komplexe"]')
    zeilen = page.locator("table.liste tr.zeile").all_inner_texts()
    assert len(zeilen) == 1 and "Sportzentrum Berg" in zeilen[0] and "\t2\t" in zeilen[0]
    page.click("table.liste tr[data-komplex]")
    assert page.locator("table.liste tr.zeile").count() == 2
    assert page.input_value('[data-f="komplex"]') == KOMPLEX["id"]

    page = oeffne()  # Karte
    page.locator("details:has(#b-ko-n) summary").click()
    page.locator('input[data-ko="*"]').check()
    assert page.locator("#b-zahl").inner_text() == "2 von 3 Sportstätten"
    page.locator('input[data-ko=""]').check()
    assert page.locator("#b-zahl").inner_text() == "3 Sportstätten"
    # im Popup: „alle auf der Karte“ zeigt nur die Sportstätten des Komplexes
    page.evaluate(
        f"ANSICHTEN.bestand.zeigeEintrag(ANSICHTEN.bestand.eintraege.find(e => e.p.id === '{SID}'))"
    )
    page.locator(".leaflet-popup [data-nur-komplex]").click()
    assert page.locator("#b-zahl").inner_text() == "2 von 3 Sportstätten"
    assert page.locator('input[data-ko="dddddddd-4444-4444-8444-444444444444"]').is_checked()


def test_stuetzpunkte(oeffne):
    page = oeffne()
    assert "Bundesstützpunkt Tennis Berg" in page.evaluate(f"stpZeile('{SID}')")
    assert "(bis 31.12.2028)" in page.evaluate(f"stpZeile('{SID}')")
    page.locator("details:has(#b-stp-n) summary").click()
    page.locator('input[data-sp="e:Bund"]').check()
    assert page.locator("#b-zahl").inner_text() == "2 von 3 Sportstätten"
    page.locator('input[data-sp="e:Land"]').check()
    assert page.locator("#b-zahl").inner_text() == "1 von 3 Sportstätten"

    page = oeffne("#ansicht=liste&teil=stuetzpunkte")
    zeilen = page.locator("table.liste tr.zeile")
    assert zeilen.count() == 2
    assert page.locator("td.abgelaufen").inner_text() == "31.12.2020"
    page.click('tr[data-stp="eeeeeeee-5555-4555-8555-555555555555"]')
    assert sorted(page.locator("table.liste tr.zeile td:first-child").all_inner_texts()) == [
        "Sportplatz Berg",
        "Tennisanlage Bergen",
    ]
    assert page.input_value('[data-f="stp"]') == "eeeeeeee-5555-4555-8555-555555555555"


def test_stuetzpunkt_vorschlagen(oeffne):
    page = oeffne("#ansicht=vorschlag")
    # von einer Sportstätte mit genau einem Stützpunkt: dieser zum Ändern
    page.evaluate(f"ANSICHTEN.vorschlag.stuetzpunktVon('{T3}')")
    page.wait_for_timeout(200)
    assert page.locator("#v-teil-stp").is_visible()
    assert page.input_value("input[name='sp.name']") == "Landesstützpunkt Fußball Tal"
    page.fill("input[name='sp.gueltig_bis']", "2030-12-31")
    _senden(page)
    d = _gesendet(page)
    assert modell.pruefe(modell.Vorschlag, d) == []
    assert d["stuetzpunkt_id"] == "eeeeeeee-6666-4666-8666-666666666666" and d["geaendert"] == [
        "gueltig_bis"
    ]
    # neu: Sportkomplex statt einzelner Sportstätten
    page.evaluate("window.__url = null")
    page.evaluate("ANSICHTEN.vorschlag.stuetzpunkt(null)")
    page.wait_for_timeout(200)
    page.fill("input[name='sp.name']", "Olympiastützpunkt Berg")
    page.select_option("select[name='sp.art']", "Olympiastützpunkt")
    _senden(page)
    assert "mindestens eine Sportstätte" in page.inner_text("#v-fehler")
    page.fill("#v-stp-staette-suche", "Sportzentrum")
    page.click("#v-stp-staette-treffer li[data-ko]")
    _senden(page)
    d = _gesendet(page)
    assert modell.pruefe(modell.Vorschlag, d) == []
    assert d["stuetzpunkt"] == {
        "name": "Olympiastützpunkt Berg",
        "art": "Olympiastützpunkt",
        "sportkomplexe": [KOMPLEX["id"]],
    }


# --- Vorschläge: was das Formular sendet, muss das Modell annehmen --------------------------


def test_neue_sportstaette(oeffne):
    page = oeffne("#ansicht=vorschlag")
    page.evaluate("ANSICHTEN.vorschlag.neu({ lage: { lat: 50.0012, lon: 7.0034 } })")
    page.wait_for_timeout(200)
    page.fill("input[name=name]", "Neue Halle")
    page.select_option("select[name=kategorie]", "Sporthalle")
    page.click("#v-anlage-dazu")
    page.locator("#v-anlagen tr.anlage").last.locator("input[data-f=typ]").fill("Einfeldhalle")
    _senden(page)
    d = _gesendet(page)
    assert modell.pruefe(modell.Vorschlag, d) == []
    assert d["art"] == "neu" and d["sportstaette"]["name"] == "Neue Halle"
    assert [a["typ"] for a in d["anlagen"]] == ["Einfeldhalle"]


def test_angaben_aendern(oeffne):
    page = oeffne("#ansicht=vorschlag")
    page.evaluate(f"ANSICHTEN.vorschlag.bearbeite('{SID}')")
    page.wait_for_timeout(200)
    page.fill("input[name=zuschauerplaetze]", "120")
    _senden(page)
    d = _gesendet(page)
    assert modell.pruefe(modell.Vorschlag, d) == []
    assert (d["art"], d["sportstaette_id"]) == ("aenderung", SID)
    assert d["geaendert"] == ["zuschauerplaetze"] and d["sportstaette"]["zuschauerplaetze"] == 120


def test_sportanlagen_aendern(oeffne):
    page = oeffne("#ansicht=vorschlag")
    page.evaluate(f"ANSICHTEN.vorschlag.bearbeite('{SID}', 'anlagen')")
    page.wait_for_timeout(200)
    page.click("#v-anlage-dazu")
    page.locator("#v-anlagen tr.anlage").last.locator("input[data-f=typ]").fill("Kleinspielfeld")
    _senden(page)
    d = _gesendet(page)
    assert modell.pruefe(modell.Vorschlag, d) == []
    # nur Anlagen geändert: ohne die Angaben der Sportstätte, nur die neue Anlage
    assert d["art"] == "anlagen" and d["sportstaette_id"] == SID and "sportstaette" not in d
    assert d["anlagen"] == [{"typ": "Kleinspielfeld"}]


def test_angaben_und_anlagen_zusammen(oeffne):
    page = oeffne("#ansicht=vorschlag")
    page.evaluate(f"ANSICHTEN.vorschlag.bearbeite('{SID}')")
    page.wait_for_timeout(200)
    assert page.locator("#v-teil-anlagen").is_visible()
    page.fill("input[name=zuschauerplaetze]", "120")
    page.locator("#v-anlagen tr.anlage").last.locator(".weg").click()  # Rundlaufbahn entfernen
    _senden(page)
    d = _gesendet(page)
    assert modell.pruefe(modell.Vorschlag, d) == []
    assert (d["art"], d["geaendert"]) == ("aenderung", ["zuschauerplaetze"])
    assert d["anlagen"] == [] and d["entfernte_anlagen"] == ["bbbbbbbb"]


def test_neue_organisation_mit_warnung(oeffne):
    page = oeffne("#ansicht=vorschlag")
    page.evaluate("ANSICHTEN.vorschlag.neu({ lage: { lat: 50.0012, lon: 7.0034 } })")
    page.wait_for_timeout(200)
    page.fill("input[name=name]", "Neue Halle")
    page.select_option("select[name=kategorie]", "Sporthalle")
    page.fill("input[name=betreiber]", "TuS Berg 1")
    page.fill("input[name=eigentuemer]", "Stadtwerke Tal")
    page.wait_for_timeout(400)
    neu = page.locator("#v-teil-neue-orgs")
    assert neu.is_visible() and "TuS Berg 1" in neu.inner_text()
    assert "Mögliche Doppelung" in page.locator('.neue-org[data-k="tus berg 1"]').inner_text()
    assert (
        "Mögliche Doppelung" not in page.locator('.neue-org[data-k="stadtwerke tal"]').inner_text()
    )
    page.locator('.neue-org[data-k="stadtwerke tal"] select[data-no=typ]').select_option(
        "Kommunales Unternehmen"
    )
    _senden(page)
    assert "Organisation „TuS Berg 1“ prüfen" in page.inner_text("#v-fehler")
    page.check('.neue-org[data-k="tus berg 1"] input[data-no=geprueft]')
    _senden(page)
    d = _gesendet(page)
    assert modell.pruefe(modell.Vorschlag, d) == []
    assert d["neue_organisationen"] == [  # in der Reihenfolge der Felder: Eigentümer, Betreiber
        {"name": "Stadtwerke Tal", "typ": "Kommunales Unternehmen"},
        {"name": "TuS Berg 1"},
    ]
    # „stattdessen diese“: der vorhandene Name ersetzt den neuen
    page.evaluate("window.__url = null")
    page.click('.neue-org[data-k="tus berg 1"] [data-org-statt="TuS Berg"]')
    assert page.input_value("input[name=betreiber]") == "TuS Berg"
    _senden(page)
    d = _gesendet(page)
    assert [o["name"] for o in d["neue_organisationen"]] == ["Stadtwerke Tal"]


def test_neuer_sportkomplex_bei_sportstaette(oeffne):
    page = oeffne("#ansicht=vorschlag")
    page.evaluate(f"ANSICHTEN.vorschlag.bearbeite('{T3}')")
    page.wait_for_timeout(200)
    page.select_option("select[name=sportkomplex]", "__neu")
    page.fill("input[name='nk.name']", "Sportpark Tal")
    _senden(page)
    assert "mindestens eine weitere Sportstätte" in page.inner_text("#v-fehler")
    page.fill("#v-nk-suche", "Tennisanlage")
    page.click("#v-nk-treffer li[data-st]")
    _senden(page)
    d = _gesendet(page)
    assert modell.pruefe(modell.Vorschlag, d) == []
    assert d["art"] == "aenderung" and d["sportstaette_id"] == T3
    assert d["neuer_sportkomplex"] == {"name": "Sportpark Tal"}
    assert d["sportstaetten"] == ["22222222-2222-4222-8222-222222222222"]


def test_neue_sportstaette_im_sportkomplex(oeffne):
    page = oeffne("#ansicht=vorschlag")
    page.evaluate(f"ANSICHTEN.vorschlag.komplexVon('{T3}')")
    page.wait_for_timeout(200)
    page.fill("input[name='ko.name']", "Sportpark Tal")
    page.click('[data-neue-staette="sportkomplex"]')
    page.wait_for_timeout(200)
    assert page.locator("#v-unter").is_visible() and page.locator("#v-teil-komplex").is_hidden()
    page.fill("input[name=name]", "Halle Tal")
    page.select_option("select[name=kategorie]", "Sporthalle")
    page.evaluate("ANSICHTEN.vorschlag.lage(50.2051, 7.8031)")
    page.fill("input[name=betreiber]", "Hallenverein Tal")
    page.click("#v-anlage-dazu")
    page.locator("#v-anlagen tr.anlage").last.locator("input[data-f=typ]").fill("Einfeldhalle")
    page.wait_for_timeout(400)
    _senden(page)  # übernimmt die Sportstätte in den Komplex
    page.wait_for_timeout(200)
    assert page.locator("#v-teil-komplex").is_visible()
    assert page.input_value("input[name='ko.name']") == "Sportpark Tal"
    assert "Halle Tal (neu)" in page.inner_text("#v-ko-staetten")
    assert "Hallenverein Tal" in page.inner_text("#v-teil-neue-orgs")
    _senden(page)
    d = _gesendet(page)
    assert modell.pruefe(modell.Vorschlag, d) == []
    assert d["sportstaetten"] == [T3, "neu-1"]
    [n] = d["neue_sportstaetten"]
    assert n["ref"] == "neu-1" and n["sportstaette"]["name"] == "Halle Tal"
    assert n["anlagen"] == [{"typ": "Einfeldhalle"}]
    assert d["neue_organisationen"] == [{"name": "Hallenverein Tal"}]


def test_organisation_aendern(oeffne):
    page = oeffne("#ansicht=vorschlag")
    page.evaluate("ANSICHTEN.vorschlag.organisation('TuS Berg')")
    page.wait_for_timeout(200)
    page.fill("input[name='org.website']", "https://tus-berg.example")
    _senden(page)
    d = _gesendet(page)
    assert modell.pruefe(modell.Vorschlag, d) == []
    assert (d["art"], d["organisation_id"]) == ("organisation", "o-tus")
    assert d["geaendert"] == ["website"]


def test_sportkomplex_vorschlagen(oeffne):
    page = oeffne("#ansicht=vorschlag")
    # neu, von einer Sportstätte ohne Komplex aus: sie ist vorbelegt, eine zweite dazu suchen
    page.evaluate("ANSICHTEN.vorschlag.komplexVon('33333333-3333-4333-8333-333333333333')")
    page.wait_for_timeout(200)
    assert page.locator("#v-teil-komplex").is_visible()
    assert page.locator("#v-teil-staette").is_hidden()
    page.fill("input[name='ko.name']", "Sportpark Tal")
    _senden(page)
    assert "mindestens zwei" in page.inner_text("#v-fehler")
    page.fill("#v-ko-staette-suche", "Sportplatz Berg")
    page.click("#v-ko-staette-treffer li[data-st]")
    assert "(bisher in Sportzentrum Berg)" in page.inner_text("#v-ko-staetten")
    _senden(page)
    d = _gesendet(page)
    assert modell.pruefe(modell.Vorschlag, d) == []
    assert d["art"] == "sportkomplex" and "sportkomplex_id" not in d
    assert d["sportkomplex"] == {"name": "Sportpark Tal"}
    assert d["sportstaetten"] == ["33333333-3333-4333-8333-333333333333", SID]

    # vorhandenen ändern: die Sportstätten sind vorbelegt
    page.evaluate("window.__url = null")
    page.evaluate(f"ANSICHTEN.vorschlag.komplex('{KOMPLEX['id']}')")
    page.wait_for_timeout(200)
    assert page.input_value("input[name='ko.name']") == "Sportzentrum Berg"
    page.fill("input[name='ko.adresse.ort']", "Berg")
    _senden(page)
    d = _gesendet(page)
    assert modell.pruefe(modell.Vorschlag, d) == []
    assert (d["sportkomplex_id"], d["geaendert"]) == (KOMPLEX["id"], ["adresse.ort"])
    assert sorted(d["sportstaetten"]) == [SID, "22222222-2222-4222-8222-222222222222"]
    # auflösen
    page.evaluate("window.__url = null")
    page.check("input[name='ko-loeschen']")
    _senden(page)
    d = _gesendet(page)
    assert d == {
        "version": 1,
        "art": "sportkomplex",
        "sportkomplex_id": KOMPLEX["id"],
        "loeschen": True,
    }


@pytest.mark.parametrize(
    ("feld", "wert"),
    [("adresse.plz", "5606"), ("name", "Halle (info@verein.example)")],
)
def test_formular_lehnt_ab_was_das_modell_ablehnt(oeffne, feld, wert):
    page = oeffne("#ansicht=vorschlag")
    page.evaluate("ANSICHTEN.vorschlag.neu({ lage: { lat: 50.0012, lon: 7.0034 } })")
    page.wait_for_timeout(200)
    page.fill("input[name=name]", "Neue Halle")
    page.select_option("select[name=kategorie]", "Sporthalle")
    page.fill(f"input[name='{feld}']", wert)
    _senden(page)
    assert page.evaluate("window.__url") is None
    assert page.inner_text("#v-fehler").strip()


# --- Organisationssuche --------------------------------------------------------------------


def test_organisationssuche_rangfolge_und_auswahl(oeffne):
    page = oeffne("#ansicht=vorschlag")
    page.evaluate("ANSICHTEN.vorschlag.neu({ lage: { lat: 50.0012, lon: 7.0034 } })")
    page.wait_for_timeout(200)
    liste = page.locator("input[name=betreiber] + ul.org-vorschlaege li")

    page.type("input[name=betreiber]", "berg")
    namen = [t.split("\n")[0] for t in liste.all_inner_texts()]
    assert namen[0] == "Ortsgemeinde Berg (VG Tal)"  # genauer Ortsname vor Wortteilen
    assert set(namen) == {"Ortsgemeinde Berg (VG Tal)", "Ortsgemeinde Bergen", "TuS Berg"}

    page.fill("input[name=betreiber]", "")
    page.type("input[name=betreiber]", "VG Tal")  # weitere Schreibweise
    assert liste.first.inner_text().startswith("Verbandsgemeinde Tal")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    assert page.input_value("input[name=betreiber]") == "Verbandsgemeinde Tal"
    assert (
        page.input_value("select[name=betreiber_typ]") == "Verbandsgemeinde"
    )  # aus dem Verzeichnis


def test_organisationen_auch_ohne_sportstaette(oeffne):
    page = oeffne("#ansicht=liste&teil=betreiber")
    page.wait_for_selector("#seite-liste .betreiber .reiter")
    teil = page.locator("#seite-liste .betreiber")
    assert "Vereine (1)" in teil.inner_text()  # TuS Berg betreibt den Sportplatz Berg
    teil.locator("[data-art=Kommune]").click()
    zeilen = teil.locator("tr.zeile")
    assert zeilen.count() == 3  # die Kommunen des Verzeichnisses, ohne Sportstätte als Betreiber
    assert "Verbandsgemeinde Tal" in teil.inner_text()
    zeilen.first.click()
    assert "Keine Sportstätte als Betreiber" in teil.inner_text()
    teil.locator("[data-ohne]").uncheck()
    assert "Keine Einträge" in teil.inner_text()


def test_haufen_je_kreis_und_gemeinde(oeffne):
    page = oeffne("")
    page.wait_for_timeout(500)  # erst die Startansicht (passt die Karte an den Bestand an)
    assert page.locator(".leaflet-maske-pane path").count() == 2  # außerhalb grau, Landesgrenze

    def zoom(z):
        page.evaluate(f"void karte.setView([50.3, 7.7], {z}, {{ animate: false }})")
        page.wait_for_timeout(300)

    zoom(8)  # Kreise
    kreise = page.locator(".haufen.kreis")
    assert kreise.count() == 1 and kreise.inner_text() == "3"
    assert kreise.get_attribute("title") == "Kreis Berg (Landkreis): 3 Sportstätten – hineinzoomen"
    kreise.hover()  # Umriss des Kreises
    page.wait_for_function("hoverEbene.getLayers().length === 1")
    page.mouse.move(5, 300)
    page.wait_for_function("hoverEbene.getLayers().length === 0")
    kreise.click()  # mindestens bis zu den Gemeinden
    page.wait_for_timeout(400)
    assert 10 <= page.evaluate("karte.getZoom()") < 13

    zoom(11)  # Gemeinden
    assert page.locator(".haufen.kreis").count() == 0
    gemeinden = page.locator(".haufen.gemeinde")
    assert gemeinden.count() == 1 and gemeinden.inner_text() == "3"
    assert "Bergland (Ortsgemeinde)" in gemeinden.get_attribute("title")
    gemeinden.hover()
    page.wait_for_function("hoverEbene.getLayers().length === 1")
    # nur noch zwei Sportstätten (Filter Sportkomplex): zu wenige für einen Haufen, also Punkte
    page.locator("details:has(#b-ko-n) summary").click()
    page.locator('input[data-ko="*"]').check()
    page.wait_for_timeout(300)
    assert page.locator(".haufen").count() == 0
    page.locator('input[data-ko=""]').check()
    page.wait_for_timeout(300)
    page.locator(".haufen.gemeinde").click()  # bis zu den Sportstätten
    page.wait_for_timeout(400)
    assert page.evaluate("karte.getZoom()") >= 13
    assert page.locator(".haufen").count() == 0


def test_punkt_beim_darueberfahren(oeffne):
    page = oeffne("")
    page.wait_for_timeout(500)
    page.evaluate("void karte.setView([50.3512, 7.5938], 15, { animate: false })")
    page.wait_for_timeout(300)
    radius = (
        "ANSICHTEN.bestand.eintraege.find(e => e.p.name === 'Sportplatz Berg').layer.getRadius()"
    )
    assert page.evaluate(radius) == 4
    mitte = page.evaluate(
        "(() => { const p = karte.latLngToContainerPoint([50.3512, 7.5938]),"
        " r = karte.getContainer().getBoundingClientRect(); return [r.x + p.x, r.y + p.y]; })()"
    )
    page.mouse.move(*mitte)
    page.wait_for_timeout(200)
    assert page.evaluate(radius) == 7  # größer, mit hellem Ring
    page.mouse.move(5, 300)
    page.wait_for_timeout(200)
    assert page.evaluate(radius) == 4


def test_regeln_wie_in_python(oeffne):
    """Dieselben Testfälle wie tests/test_regeln_faelle.py, im Formular gerechnet."""
    faelle = json.loads((Path(__file__).parent / "regeln_faelle.json").read_text(encoding="utf-8"))
    page = oeffne("#ansicht=vorschlag")
    ergebnis = page.evaluate(
        """f => ({
          norm_name: f.norm_name.map(([n]) => normName(n)),
          org_kern: f.org_kern.map(([n]) => orgKern(n)),
          aehnlich: f.aehnlich.map(([a, b]) => aehnlich(a, b)),
          abstand_m: f.abstand_m.map(([a, b, c, d]) => abstand(a, b, c, d)),
          zwischen_feldern: f.zwischen_feldern.map(x =>
            regelFunde(x.modell, x.objekt).map(r => [r.regel, r.feld])),
          texte: regelnZwischen("Sanierung", { jahr: 2010, kosten: 1000 }),
        })""",
        faelle,
    )
    assert ergebnis["norm_name"] == [e for _, e in faelle["norm_name"]]
    assert ergebnis["org_kern"] == [e for _, e in faelle["org_kern"]]
    for wert, (*_, e) in zip(ergebnis["aehnlich"], faelle["aehnlich"], strict=True):
        assert wert == pytest.approx(e, abs=1e-9)
    for wert, (*_, e) in zip(ergebnis["abstand_m"], faelle["abstand_m"], strict=True):
        assert wert == pytest.approx(e, abs=1e-3)
    assert ergebnis["zwischen_feldern"] == [x["funde"] for x in faelle["zwischen_feldern"]]
    assert ergebnis["texte"] == ["Währung: nötig, wenn Kosten angegeben ist"]  # mit Titeln
