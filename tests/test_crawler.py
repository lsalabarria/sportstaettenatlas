"""Crawler für Vereinswebseiten – ohne Netz: Abrufe und DNS sind ersetzt (synthetische Daten)."""

import csv
import json

from sportstaettenatlas.analysen import crawler
from sportstaettenatlas.analysen.crawler import Abrufer, Verein, domain_kandidaten, kennwoerter

S1 = "11111111-1111-4111-8111-111111111111"


def _daten(tmp_path):
    org = tmp_path / "organisationen" / "RP" / "sportverein-im-lsb-rlp"
    org.mkdir(parents=True)
    for i, name, web in (
        ("o1", "TuS Berg 1926 e.V.", None),
        ("o2", "SV Tal e.V.", "https://sv-tal.de"),  # hat schon eine
        ("o3", "Reitverein Bergland e.V.", None),
    ):
        o = {"id": i, "name": name, "typ": "Sportverein im LSB RLP"}
        (org / f"{i}.json").write_text(json.dumps({**o, "website": web} if web else o), "utf-8")
    kommune = tmp_path / "organisationen" / "RP" / "ortsgemeinde"
    kommune.mkdir()
    (kommune / "k1.json").write_text(
        json.dumps({"id": "k1", "name": "Ortsgemeinde Berg", "typ": "Ortsgemeinde"}), "utf-8"
    )
    st = tmp_path / "RP" / "07111-koblenz" / S1
    st.mkdir(parents=True)
    (st / f"{S1}_meta.json").write_text(
        json.dumps(
            {
                "id": S1,
                "name": "Sportplatz Berg",
                "adresse": {"ort": "Koblenz"},
                "lage": {"lat": 50.3512, "lon": 7.5938},
                "nutzer": ["TuS Berg 1926 e.V."],
            }
        ),
        "utf-8",
    )


def test_vereine_ohne_webseite(tmp_path):
    _daten(tmp_path)
    vereine = crawler.vereine_ohne_webseite(tmp_path)
    assert [v.id for v in vereine] == ["o3", "o1"]  # nach Namen; o2 hat eine, k1 kein Verein
    tus = vereine[1]
    assert tus.orte == {"Koblenz"} and tus.lagen == [(50.3512, 7.5938)]
    assert [v.id for v in crawler.vereine_ohne_webseite(tmp_path, kreis="07111")] == ["o1"]


def test_kennwoerter_und_domains():
    assert kennwoerter("TuS Berg 1926 e.V.") == ["berg", "1926"]
    d = domain_kandidaten("TuS Berg 1926 e.V.")
    assert d[:4] == ["tus-berg.de", "tusberg.de", "tus-berg-1926.de", "tusberg1926.de"]
    assert "sv-bergland.de" in domain_kandidaten("Sportverein SV Bergland e. V.")
    assert all(x.endswith(".de") and len(x) <= 66 for x in d)
    # Kürzel aus Anfangsbuchstaben, Ordnungszahl vorn am Kürzel, bekannter Ort ausgeschrieben
    assert domain_kandidaten("1. Badminton-Club Westerburg e.V.")[:3] == [
        "bc-westerburg.de", "1bc-westerburg.de", "bcwesterburg.de"
    ]  # fmt: skip
    assert (
        domain_kandidaten("Allgemeiner Sportverein 1946 Birkenheide eV")[0] == "asv-birkenheide.de"
    )
    assert domain_kandidaten("Turnverein Bad Ems", {"Bad Ems"})[0] == "tv-bad-ems.de"
    assert domain_kandidaten("1906") == []


def test_osm_und_wikidata_treffer():
    tus = Verein("o1", "TuS Berg 1926 e.V.", "Verein", "", {"Koblenz"}, [(50.3512, 7.5938)])
    osm = [
        {"tags": {"operator": "TuS Berg 1926", "website": "https://tus-berg.de"},
         "center": {"lat": 50.352, "lon": 7.594}},
        {"tags": {"operator": "TuS Berg 1926", "website": "https://weit-weg.de"},
         "center": {"lat": 49.0, "lon": 8.0}},  # zu weit von seinen Sportstätten
        {"tags": {"operator": "TuS Berg 1926"}, "lat": 50.35, "lon": 7.59},  # ohne Webseite
        {"tags": {"name": "Tennisclub Tal", "website": "https://tc-tal.de"},
         "lat": 50.35, "lon": 7.59},
    ]  # fmt: skip
    t = crawler.osm_treffer([tus], osm)
    assert [(x.website, x.quelle) for x in t] == [("https://tus-berg.de", "openstreetmap")]
    wd = [{"itemLabel": {"value": "TuS Berg 1926"}, "website": {"value": "https://tus.de"}}]
    assert [x.website for x in crawler.wikidata_treffer([tus], wd)] == ["https://tus.de"]


class FalschesNetz(Abrufer):
    def __init__(self, seiten, domains):
        super().__init__()
        self.seiten, self.domains, self.abgerufen = seiten, domains, []

    def hole_roh(self, url):
        self.abgerufen.append(url)
        if url.endswith("/robots.txt"):
            return (
                (200, url, "User-agent: *\nDisallow: /intern/")
                if "tus-berg" in url
                else (404, url, "")
            )
        if url in self.seiten:
            return 200, url, self.seiten[url]
        return 404, url, ""

    def existiert(self, domain):
        return domain in self.domains


def test_suche_und_pruefe(tmp_path, monkeypatch):
    monkeypatch.setattr(crawler, "JE_WEBSEITE_S", 0)
    tus = Verein("o1", "TuS Berg 1926 e.V.", "Verein", "", {"Koblenz"}, [])
    reiter = Verein("o3", "Reitverein Bergland e.V.", "Verein", "", set(), [])
    netz = FalschesNetz(
        {
            "https://tus-berg.de": '<a href="/impressum">Impressum</a> Willkommen',
            "https://tus-berg.de/impressum": "<p>TuS Berg 1926 e.V., 56070 Koblenz, "
            "Vereinsregister VR 1234, Vorstand: Max Muster, max@tus-berg.de</p>",
            "https://reitverein-bergland.de": "<p>Reiterhof – Ferien auf dem Land</p>",
        },
        {"tus-berg.de", "reitverein-bergland.de"},
    )
    wd = [{"itemLabel": {"value": "Reitverein Bergland"},
           "website": {"value": "https://www.facebook.com/reitverein"}}]  # fmt: skip
    treffer = crawler.suche([tus, reiter], [], wd, abrufer=netz, meldung=lambda _: None)
    nach = {(t.verein.id, t.website): t for t in treffer}
    gut = nach[("o1", "https://tus-berg.de")]
    assert gut.punkte == 4 and gut.quelle == "domain geraten"
    assert gut.nachweis == "Name in Impressum, Ort, Vereinsregister/e. V."
    assert "Max" not in gut.nachweis and "@" not in gut.nachweis  # nichts aus dem Impressum
    fb = nach[("o3", "https://www.facebook.com/reitverein")]
    assert fb.punkte == 0 and "soziales Netzwerk" in fb.nachweis
    assert not any("facebook" in u for u in netz.abgerufen)  # nicht geladen
    # geraten wird nur ohne Treffer aus OSM/Wikidata: für den Reitverein also nicht
    assert ("o3", "https://reitverein-bergland.de") not in nach
    ziel = tmp_path / "ergebnis.csv"
    assert crawler.schreibe(treffer, ziel) == len([t for t in treffer if t.punkte >= 0])
    zeilen = list(csv.DictReader(ziel.open(encoding="utf-8")))
    assert list(zeilen[0]) == ["id", "name", "typ", "website", "quelle", "punkte", "nachweis",
                               "orte"]  # fmt: skip
    assert zeilen[0]["typ"] == "Verein"  # mit typ und name: bestand erkennt Organisationen


def test_robots_und_sperrliste(monkeypatch):
    monkeypatch.setattr(crawler, "JE_WEBSEITE_S", 0)
    netz = FalschesNetz({"https://tus-berg.de/intern/x": "geheim"}, set())
    v = Verein("o1", "TuS Berg", "Verein", "")
    t = crawler.pruefe(crawler.Treffer(v, "https://tus-berg.de/intern/x", "osm"), netz)
    assert "robots.txt" in t.nachweis and "https://tus-berg.de/intern/x" not in netz.abgerufen
    t = crawler.suche(
        [v], [{"tags": {"operator": "TuS Berg", "website": "https://www.fussball.de/verein/x"}}],
        None, raten=False, abrufer=netz, meldung=lambda _: None,
    )  # fmt: skip
    assert t == []  # Verzeichnis: fällt weg, wird nicht geladen


def test_kontakt_nur_ascii(monkeypatch):
    import importlib

    from sportstaettenatlas import hilfen

    for roh, soll in (
        ("…", ""),
        ("atlas@example.org", "atlas@example.org"),
        ("a…b@x.de", "ab@x.de"),
    ):
        monkeypatch.setenv("SPORTSTAETTENATLAS_KONTAKT", roh)
        h = importlib.reload(hilfen)
        assert h.KONTAKT == soll
        h.USER_AGENT.encode("latin-1")  # als HTTP-Header gültig
    monkeypatch.delenv("SPORTSTAETTENATLAS_KONTAKT")
    importlib.reload(hilfen)


def test_quelle_faellt_weg_statt_abzubrechen(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(crawler, "CACHE", tmp_path)
    monkeypatch.setattr(crawler, "PAUSE_S", 0)
    versuche = []

    def kaputt():
        versuche.append(1)
        raise OSError("502 Server Error: Bad Gateway")

    assert crawler._lade_json("wd.json", kaputt, neu=True) is None
    assert len(versuche) == 3 and not (tmp_path / "wd.json").exists()  # nichts im Cache
    assert "übersprungen" in capsys.readouterr().err
    ok = iter([OSError("503"), [{"x": 1}]])

    def einmal_kaputt():
        w = next(ok)
        if isinstance(w, Exception):
            raise w
        return w

    assert crawler._lade_json("wd.json", einmal_kaputt, neu=True) == [{"x": 1}]
    assert crawler._lade_json("wd.json", kaputt, neu=False) == [{"x": 1}]  # aus dem Cache


def test_fortschritt_und_zusammenfassung(monkeypatch):
    import sys
    import types

    balken = []

    class FalscherBalken:
        def __init__(self, total, desc, **_):
            self.total, self.desc, self.n, self.postfix = total, desc, 0, ""
            balken.append(self)

        def set_postfix_str(self, s, refresh=True):
            self.postfix = s

        def update(self):
            self.n += 1

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "tqdm", types.SimpleNamespace(tqdm=FalscherBalken))
    v = Verein("o1", "TuS Berg", "Verein", "")
    treffer = [
        crawler.Treffer(v, "a.de", "domain geraten", 4),
        crawler.Treffer(v, "b.de", "openstreetmap", -1),
        crawler.Treffer(Verein("o2", "SV Tal", "Verein", ""), "c.de", "wikidata", 2),
    ]
    out = crawler._parallel(lambda t: t, treffer, 4, "Webseiten prüfen", True, crawler.einstufung)
    assert out == treffer  # Reihenfolge wie die Werte, auch wenn parallel
    b = balken[0]
    assert (b.desc, b.total, b.n) == ("Webseiten prüfen", 3, 3)
    assert b.postfix == "sicher=1 wahrscheinlich=1 weg=1"
    text = crawler.zusammenfassung(treffer, vereine=5)
    assert "sicher" in text and "weg" in text
    assert text.splitlines()[-1] == (
        "Vereine: 5; mit sicherem Treffer (3–4 Punkte) 1, mit wahrscheinlichem (2 Punkte) 1, ohne 3"
    )


def _z(i, website, punkte=3, nachweis="Name in Impressum"):
    return {"id": i, "name": f"Verein {i}", "typ": "Sportverein im LSB RLP",
            "website": website, "quelle": "domain geraten", "punkte": str(punkte),
            "nachweis": nachweis, "orte": ""}  # fmt: skip


def test_auswahl_nur_eindeutige_sichere_startseiten():
    zeilen = [
        _z("a", "https://tus-a.de/"),
        _z("a", "http://www.tus-a.de"),  # dieselbe Seite: bleibt ein Treffer, https gewinnt
        _z("a", "https://tusa.de/", punkte=2),  # nur wahrscheinlich: zählt nicht
        _z("b", "https://sv-b.de/"),
        _z("b", "https://svb.de/"),  # zwei sichere Seiten: von Hand
        _z("c", "https://schuetzen.de/"),
        _z("d", "https://www.schuetzen.de"),  # zwei Vereine, eine Seite: von Hand
        _z("e", "https://gemeinde-e.de/vereine/tus.html"),  # Unterseite: von Hand
        _z("f", "https://f.example/", punkte=0),
        _z("g", "https://facebook.com/tusg", nachweis="soziales Netzwerk"),
    ]
    sicher, weg = crawler.auswahl(zeilen)
    assert sicher == [
        {
            "id": "a",
            "name": "Verein a",
            "typ": "Sportverein im LSB RLP",
            "website": "https://tus-a.de/",
        }
    ]
    assert weg == {
        "mehrere sichere Webseiten": 1,
        "Webseite auch bei einem anderen Verein": 2,
        "Unterseite statt Startseite": 1,
    }


def test_auswahl_einlesen_fuellt_nur_die_webseite(tmp_path):
    """Die Auswahl lässt sich mit `bestand --modus ergaenzen` einlesen: die Organisation
    bekommt ihre Webseite, sonst ändert sich nichts und nichts kommt neu dazu."""
    from sportstaettenatlas.bestand import lies_organisationen, schreibe_organisationen
    from sportstaettenatlas.pflege.einlesen import lies_csv

    _daten(tmp_path)
    quelle = tmp_path / "vereinswebseiten.csv"
    with quelle.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(_z("o1", "").keys()))
        w.writeheader()
        w.writerow({**_z("o1", "https://tus-berg.de/"), "name": "TuS Berg 1926 e.V."})
    ziel = tmp_path / "sicher.csv"
    assert crawler.schreibe_auswahl(quelle, ziel)[0] == 1
    datensaetze, bericht = lies_csv(ziel)
    assert bericht.art == "organisationen"
    e = schreibe_organisationen(datensaetze, tmp_path, "ergaenzen")
    assert (e.neu, e.aktualisiert) == (0, 1)
    o1 = next(o for o in lies_organisationen(tmp_path) if o["id"] == "o1")
    assert o1["website"] == "https://tus-berg.de/" and o1["name"] == "TuS Berg 1926 e.V."
