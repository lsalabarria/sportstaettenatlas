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


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    docs = tmp_path_factory.mktemp("docs")
    shutil.copytree(_leaflet(), docs / "vendor" / "leaflet")
    seite.schreibe_webseite(
        docs, bestand=BESTAND, organisationen=ORGANISATIONEN, sportkomplexe=[KOMPLEX]
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
    assert d["art"] == "anlagen" and d["sportstaette_id"] == SID
    assert sorted(a["typ"] for a in d["anlagen"]) == [
        "Großspielfeld",
        "Kleinspielfeld",
        "Rundlaufbahn",
    ]
    assert {a.get("id") for a in d["anlagen"]} >= {"aaaaaaaa", "bbbbbbbb"}  # vorhandene: Kurz-ID


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
