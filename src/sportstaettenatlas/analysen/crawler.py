"""Webseiten für Vereine suchen, die noch keine haben – zum Prüfen, nicht direkt in die Daten.

    uv run sportstaettenatlas crawler            # alle Vereine ohne Webseite
    uv run sportstaettenatlas crawler --max 20   # Probelauf (zufällige Stichprobe)

1. Vereine (Art „Verein“, z. B. „Sportverein im LSB RLP“) ohne `website` aus
   daten/organisationen/; Orte und Lagen ihrer Sportstätten (Eigentümer, Betreiber, Nutzer)
   helfen beim Abgleich.
2. OpenStreetMap (Overpass: Sportobjekte in RLP mit Webseite, Name oder Betreiber ähnlich)
   und Wikidata (Sportvereine in RLP mit offizieller Webseite, P856).
3. Domains raten: aus dem Namen „TuS Berg 1926 e.V.“ → tus-berg.de, tusberg.de, …; nur, was
   im DNS existiert.

Jede gefundene Webseite wird geprüft: Startseite und Impressum laden und schauen, ob dort der
Name des Vereins (und sein Ort) steht. Vom Impressum wird nichts gespeichert, nur ob es passt
– keine Personen, Mail-Adressen, Telefonnummern.

Ergebnis: results/vereinswebseiten.csv (id, name, typ, website, quelle, punkte, nachweis,
orte), je Verein die besten Treffer zuerst. Nach dem Prüfen (passende Zeilen behalten, den
Rest löschen) einlesen mit `sportstaettenatlas bestand --modus ergaenzen`; die Spalten
quelle, punkte, nachweis und orte werden dabei ignoriert.

Rücksicht: robots.txt wird beachtet, je Webseite höchstens eine Anfrage pro Sekunde (parallel
nur über verschiedene Webseiten), User-Agent mit Kontakt aus SPORTSTAETTENATLAS_KONTAKT.
Verzeichnisse wie fussball.de werden nicht abgefragt; Seiten in sozialen Netzwerken werden
notiert, aber nicht geladen. Antworten von Overpass und Wikidata liegen in results/cache/.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import random
import re
import socket
import sys
import threading
import time
import urllib.robotparser
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .. import modell
from ..bestand import ROLLEN, lies_organisationen, org_pfad
from ..bestand.pruefung import abstand_m, aehnlich, norm_name, org_kern, ort_passt
from ..hilfen import _ROH as KONTAKT_ROH
from ..hilfen import ERGEBNISSE, KONTAKT, USER_AGENT

ERGEBNIS = ERGEBNISSE / "vereinswebseiten.csv"
CACHE = ERGEBNISSE / "cache" / "crawler"
OVERPASS = "https://overpass-api.de/api/interpreter"
WIKIDATA = "https://query.wikidata.org/sparql"

VEREINSTYPEN = {t for t, g in modell.ORGANISATIONSTYPEN.items() if g == "Verein"}
AEHNLICH_OSM = 0.85  # Name oder Betreiber in OSM so ähnlich wie der Verein (ohne Rechtsform)
NAH_OSM_M = 5000  # … und so nah an einer seiner Sportstätten (wenn er welche hat)
JE_WEBSEITE_S = 1.0  # Abstand zwischen zwei Anfragen an dieselbe Webseite
ZEITLIMIT_S = 10

# Verzeichnisse, Suchmaschinen, Karten: keine Vereinsseiten, werden nicht abgefragt
SPERRLISTE = {
    "fussball.de", "handball.net", "kicker.de", "transfermarkt.de", "vereinsfinder.de",
    "gelbeseiten.de", "dasoertliche.de", "11880.com", "cylex.de", "meinestadt.de",
    "wikipedia.org", "wikidata.org", "openstreetmap.org", "google.com", "google.de",
    "tripadvisor.de", "yelp.de", "northdata.de",
}  # fmt: skip
# soziale Netzwerke: als Treffer notieren, aber nicht laden
SOZIAL = {"facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com", "tiktok.com"}

# Wörter, die in Vereinsnamen nichts unterscheiden (für den Abgleich und die Domains)
FUELLWOERTER = {
    "der", "die", "das", "von", "vom", "im", "am", "an", "auf", "und", "in", "zu", "zur", "zum",
    "fuer", "e", "v",
}  # fmt: skip
ALLGEMEIN = {
    "sportverein", "turnverein", "sportclub", "fussballverein", "verein", "sport", "sv", "tv",
    "tus", "tsv", "fc", "sc", "sg", "vfl", "vfb", "djk", "ssv", "fsv", "spvgg", "turn",
    "sportgemeinschaft", "spielvereinigung", "club", "klub", "ev",
}  # fmt: skip


@dataclass
class Verein:
    id: str
    name: str
    typ: str
    datei: str
    orte: set[str] = field(default_factory=set)
    lagen: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class Treffer:
    verein: Verein
    website: str
    quelle: str
    punkte: int = 0
    nachweis: str = ""


# übliche Kürzel in Vereinsnamen und Wörter, für die ein Kürzel steht (für geratene Domains)
KUERZEL = {"sv", "tv", "tus", "tsv", "fc", "sc", "sg", "vfl", "vfb", "djk", "ssv", "fsv", "spvgg",
           "tc", "ttc", "rv", "fv", "asv", "bsv", "esv", "psv", "tg", "tsg"}  # fmt: skip
ABKUERZUNG = {
    "sportverein": "sv", "turnverein": "tv", "tennisclub": "tc", "tennisverein": "tv",
    "sportclub": "sc", "fussballverein": "fv", "fussballclub": "fc", "reitverein": "rv",
    "schwimmverein": "sv", "tischtennisclub": "ttc", "spielvereinigung": "spvgg",
    "sportgemeinschaft": "sg", "turngemeinde": "tg", "turnerschaft": "ts",
}  # fmt: skip


# --- 1. Vereine ohne Webseite -------------------------------------------------------------


def vereine_ohne_webseite(daten: Path, kreis: str | None = None) -> list[Verein]:
    """Vereine ohne `website`; mit den Orten und Lagen der Sportstätten, bei denen sie
    Eigentümer, Betreiber oder Nutzer sind. Mit `kreis` (Schlüssel, z. B. 07111) nur
    Vereine, die eine Sportstätte in diesem Kreis haben."""
    vereine, namen = {}, {}
    for o in lies_organisationen(daten):
        if o.get("typ") in VEREINSTYPEN and not (o.get("website") or "").strip():
            v = Verein(o["id"], o["name"], o["typ"], str(org_pfad(daten, o)))
            vereine[v.id] = v
            for n in [o["name"], *(o.get("weitere_namen") or [])]:
                namen.setdefault(_schluessel(n), v)
    im_kreis = set()
    for meta in sorted(Path(daten).glob("RP/*/*/*_meta.json")):
        st = json.loads(meta.read_text(encoding="utf-8"))
        ort = ((st.get("adresse") or {}).get("ort") or "").strip()
        lage = st.get("lage") or {}
        for rolle in ROLLEN:
            werte = st.get(rolle) or []
            for n in [werte] if isinstance(werte, str) else werte:
                if v := namen.get(_schluessel(n)):
                    if ort:
                        v.orte.add(ort)
                    if lage.get("lat") is not None and lage.get("lon") is not None:
                        v.lagen.append((float(lage["lat"]), float(lage["lon"])))
                    if kreis and meta.parent.parent.name.startswith(kreis):
                        im_kreis.add(v.id)
    out = sorted(vereine.values(), key=lambda v: v.name.lower())
    return [v for v in out if v.id in im_kreis] if kreis else out


def _schluessel(name) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip()).lower()


def kennwoerter(name: str) -> list[str]:
    """Wörter, die einen Verein ausmachen: ohne Rechtsform, Füllwörter und Allerweltswörter
    („TuS Berg 1926 e.V.“ → [„berg“, „1926“])."""
    return [w for w in org_kern(name).split() if w not in FUELLWOERTER | ALLGEMEIN]


# --- 2. OpenStreetMap und Wikidata ---------------------------------------------------------

OVERPASS_ABFRAGE = """[out:json][timeout:180];
area["ISO3166-2"="DE-RP"]->.rp;
(
  nwr(area.rp)["club"="sport"];
  nwr(area.rp)["leisure"~"^(sports_centre|stadium|pitch|sports_hall|track|ice_rink)$"]["operator"];
  nwr(area.rp)["building"="sports_hall"]["operator"];
);
out tags center;"""

# Sportvereine und Fußballvereine mit offizieller Webseite, deren Ort (P131) oder Sitz (P159)
# eine Gemeinde in RLP ist (Gemeindeschlüssel P439 beginnt mit 07). Ohne transitive Pfade
# (P131*, P279*): die liefen beim Abfragedienst in das Zeitlimit.
WIKIDATA_ABFRAGE = """SELECT DISTINCT ?item ?itemLabel ?website WHERE {
  VALUES ?art { wd:Q847017 wd:Q476028 }
  ?ort wdt:P439 ?ags .
  FILTER(STRSTARTS(?ags, "07"))
  ?item wdt:P31 ?art ;
        wdt:P856 ?website ;
        (wdt:P131|wdt:P159) ?ort .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "de,en". }
}"""


def webseite_aus_tags(tags: dict) -> str | None:
    for k in ("website", "contact:website", "url"):
        if (w := (tags.get(k) or "").strip()) and re.match(r"^(https?://|www\.)", w):
            return w.split(";")[0].strip()
    return None


def osm_treffer(vereine: list[Verein], elemente: list[dict]) -> list[Treffer]:
    """OSM-Objekte mit Webseite, deren Name oder Betreiber dem Verein ähnelt (ohne
    Rechtsform, mindestens AEHNLICH_OSM) – und, wenn der Verein Sportstätten hat, höchstens
    NAH_OSM_M von einer entfernt; sonst muss der Ort (addr:city) passen, falls angegeben."""
    index: dict[str, list[tuple[str, str, dict]]] = defaultdict(list)
    for el in elemente:
        tags = el.get("tags") or {}
        if not (web := webseite_aus_tags(tags)):
            continue
        for n in {tags.get("operator"), tags.get("name")} - {None, ""}:
            for w in kennwoerter(n):
                if len(w) >= 3:
                    index[w].append((n, web, el))
    out = []
    for v in vereine:
        kern = org_kern(v.name)
        gesehen = set()
        for w in kennwoerter(v.name):
            for n, web, el in index.get(w, []):
                if web in gesehen or aehnlich(kern, org_kern(n)) < AEHNLICH_OSM:
                    continue
                if not _passt_raeumlich(v, el):
                    continue
                gesehen.add(web)
                out.append(Treffer(v, web, "openstreetmap", nachweis=f"OSM: „{n}“"))
    return out


def _passt_raeumlich(v: Verein, el: dict) -> bool:
    mitte = el.get("center") or el
    lat, lon = mitte.get("lat"), mitte.get("lon")
    if v.lagen and lat is not None and lon is not None:
        return any(abstand_m(la, lo, lat, lon) <= NAH_OSM_M for la, lo in v.lagen)
    stadt = ((el.get("tags") or {}).get("addr:city") or "").strip()
    return not (stadt and v.orte) or any(ort_passt(o, stadt) for o in v.orte)


def wikidata_treffer(vereine: list[Verein], zeilen: list[dict]) -> list[Treffer]:
    """Sportvereine aus Wikidata (in RLP, mit P856), deren Name dem Verein ähnelt."""
    out = []
    eintraege = [
        (z["itemLabel"]["value"], z["website"]["value"])
        for z in zeilen
        if z.get("itemLabel") and z.get("website")
    ]
    for v in vereine:
        kern = org_kern(v.name)
        for n, web in eintraege:
            if aehnlich(kern, org_kern(n)) >= AEHNLICH_OSM:
                out.append(Treffer(v, web, "wikidata", nachweis=f"Wikidata: „{n}“"))
    return out


# --- 3. Domains raten ----------------------------------------------------------------------


def domain_kandidaten(name: str, orte=(), hoechstens: int = 10) -> list[str]:
    """Domains, die ein Verein wahrscheinlich hat (nur .de), die üblichen zuerst:
    „TuS Berg 1926 e.V.“ → tus-berg.de, tusberg.de, …; „1. Badminton-Club Westerburg e.V.“ →
    bc-westerburg.de, 1bc-westerburg.de, bcwesterburg.de, badminton-club-westerburg.de, …
    Kürzel aus den Anfangsbuchstaben, der Ort (aus `orte` oder das letzte Wort) bleibt
    ausgeschrieben; eine führende Ordnungszahl („1.“) fällt weg oder steht vorn am Kürzel."""
    woerter = [w for w in org_kern(name).split() if w not in FUELLWOERTER]
    nummer = woerter.pop(0) if woerter and re.fullmatch(r"\d{1,2}", woerter[0]) else ""
    jahr = re.compile(r"(18|19|20)\d\d|\d\d")
    ohne_jahr = [w for w in woerter if not jahr.fullmatch(w)]
    if not ohne_jahr:
        return []
    bekannte = {norm_name(o.split(",")[0]) for o in orte} - {""}
    ort_teile = next((b.split() for b in bekannte if " ".join(ohne_jahr).endswith(b)), None)
    ort_teile = ort_teile or ohne_jahr[-1:]
    vorn = ohne_jahr[: len(ohne_jahr) - len(ort_teile)]
    ort = "-".join(ort_teile)
    varianten = []
    kuerzel = [w for w in vorn if w in KUERZEL]
    kenn = [w for w in vorn if w not in ALLGEMEIN]
    if kuerzel:  # „sv-berg“
        rest = kenn + ort_teile
        varianten += [f"{kuerzel[0]}-{'-'.join(rest)}", kuerzel[0] + "".join(rest)]
    # Anfangsbuchstaben: „badminton club“ → „bc“, „allgemeiner sportverein“ → „asv“
    if 2 <= len(vorn) <= 5 or (len(vorn) == 1 and vorn[0] in ABKUERZUNG):
        k = "".join(ABKUERZUNG.get(w, w if w in KUERZEL else w[0]) for w in vorn)
        varianten += [
            f"{k}-{ort}",
            f"{nummer}{k}-{ort}" if nummer else "",
            f"{k}{ort.replace('-', '')}",
        ]
    for teile in (ohne_jahr, woerter):
        varianten += ["-".join(teile), "".join(teile)]
    if nummer:
        varianten.append(f"{nummer}-{'-'.join(ohne_jahr)}")
    out = []
    for v in varianten:
        if v and 4 <= len(v) <= 63 and v not in out and not v.startswith("-"):
            out.append(v)
    return [f"{v}.de" for v in out[:hoechstens]]


# --- Webseiten laden und prüfen ------------------------------------------------------------


class Abrufer:
    """Lädt Seiten höflich: robots.txt, je Webseite höchstens eine Anfrage pro JE_WEBSEITE_S,
    User-Agent mit Kontakt. Für Tests lassen sich `hole_roh` und `existiert` ersetzen."""

    def __init__(self):
        self._sperre = threading.Lock()
        self._zuletzt: dict[str, float] = {}
        self._host_sperren: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def hole_roh(self, url: str) -> tuple[int, str, str]:
        """(Status, URL nach Weiterleitungen, Text)."""
        import requests

        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=ZEITLIMIT_S)
        r.encoding = r.encoding or r.apparent_encoding
        return r.status_code, r.url, r.text if "html" in r.headers.get("content-type", "") else ""

    def existiert(self, domain: str) -> bool:
        try:
            socket.getaddrinfo(domain, 443)
            return True
        except (OSError, UnicodeError):
            return False

    def hole(self, url: str) -> tuple[int, str, str]:
        host = urlparse(url).netloc.lower()
        with self._host_sperren[host]:  # dieselbe Webseite nie gleichzeitig
            if not self._erlaubt(url):
                return 0, url, ""
            with self._sperre:
                warten = self._zuletzt.get(host, 0) + JE_WEBSEITE_S - time.monotonic()
            if warten > 0:
                time.sleep(warten)
            try:
                return self.hole_roh(url)
            except Exception:  # noqa: BLE001 – Netzfehler, Zertifikat, Zeitlimit: kein Treffer
                return -1, url, ""
            finally:
                with self._sperre:
                    self._zuletzt[host] = time.monotonic()

    def _erlaubt(self, url: str) -> bool:
        teile = urlparse(url)
        basis = f"{teile.scheme}://{teile.netloc}"
        if basis not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                status, _, text = self.hole_roh(basis + "/robots.txt")
                rp.parse(text.splitlines() if status == 200 else [])
            except Exception:  # noqa: BLE001 – keine robots.txt: erlaubt
                rp.parse([])
            self._robots[basis] = rp
        return self._robots[basis].can_fetch(USER_AGENT, url)


def domain_von(url: str) -> str:
    host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    return host.removeprefix("www.")


def _gesperrt(domain: str, liste: set[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in liste)


_IMPRESSUM = re.compile(
    r"""<a\b[^>]*href=["']([^"'#]+)["'][^>]*>(.*?)</a>""", re.IGNORECASE | re.DOTALL
)


def _text(seite: str) -> str:
    seite = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", seite)
    return norm_name(html.unescape(re.sub(r"<[^>]+>", " ", seite)))


def pruefe(t: Treffer, abrufer: Abrufer) -> Treffer:
    """Startseite und Impressum laden; Punkte: Name im Impressum 2 (alle Kennwörter) oder 1
    (die Hälfte; Jahreszahlen zählen nicht), Ort 1, Vereinsregister oder „e. V.“ 1. Der Text wird nicht gespeichert."""
    url = t.website if "://" in t.website else f"https://{t.website}"
    domain = domain_von(url)
    if _gesperrt(domain, SOZIAL):
        t.nachweis = _plus(t.nachweis, "soziales Netzwerk, nicht geprüft")
        return t
    status, endurl, start = abrufer.hole(url)
    if status != 200 and url.startswith("https://"):
        status, endurl, start = abrufer.hole("http://" + url.removeprefix("https://"))
    if status == 0:
        t.nachweis = _plus(t.nachweis, "robots.txt verbietet das Laden")
        return t
    if status != 200 or not start:
        t.nachweis, t.punkte = _plus(t.nachweis, f"nicht erreichbar ({status})"), -1
        return t
    if _gesperrt(domain_von(endurl), SPERRLISTE | SOZIAL):
        t.nachweis, t.punkte = _plus(t.nachweis, f"leitet weiter auf {domain_von(endurl)}"), -1
        return t
    t.website = endurl
    impressum, quelle = start, "Startseite"
    for href, beschriftung in _IMPRESSUM.findall(start):
        if "impressum" in (href + beschriftung).lower():
            s, _, text = abrufer.hole(urljoin(endurl, href.strip()))
            if s == 200 and text:
                impressum, quelle = text, "Impressum"
            break
    text = _text(impressum)
    woerter = set(text.split())
    kenn = [w for w in kennwoerter(t.verein.name) if not re.fullmatch(r"\d+", w)]
    kenn = kenn or org_kern(t.verein.name).split()
    gefunden = sum(w in woerter for w in kenn)
    punkte, belege = 0, []
    if kenn and gefunden == len(kenn):
        punkte, belege = 2, [f"Name in {quelle}"]
    elif kenn and gefunden * 2 >= len(kenn):
        punkte, belege = 1, [f"Name teilweise in {quelle}"]
    orte = {norm_name(o.split(",")[0]) for o in t.verein.orte} - {""}  # „Worms, Stadt“
    if any(re.search(rf"\b{re.escape(o)}\b", text) for o in orte):
        punkte, belege = punkte + 1, [*belege, "Ort"]
    if re.search(r"\b(vereinsregister|vr \d+|e v)\b", text):
        punkte, belege = punkte + 1, [*belege, "Vereinsregister/e. V."]
    t.punkte, t.nachweis = punkte, _plus(t.nachweis, ", ".join(belege) or "Name nicht gefunden")
    return t


def _plus(a: str, b: str) -> str:
    return f"{a}; {b}" if a else b


# --- Ablauf --------------------------------------------------------------------------------


def _lade_json(name: str, holen, neu: bool, versuche: int = 3):
    """Antwort aus dem Cache oder neu holen (bis zu `versuche` Mal, mit Pause dazwischen –
    Overpass und Wikidata antworten bei Last mit 429, 502, 503 oder 504). Klappt es nicht,
    None: die Quelle fällt für diesen Lauf weg, der Rest läuft weiter."""
    CACHE.mkdir(parents=True, exist_ok=True)
    pfad = CACHE / name
    if pfad.exists() and not neu:
        return json.loads(pfad.read_text(encoding="utf-8"))
    for versuch in range(1, versuche + 1):
        try:
            daten = holen()
        except Exception as exc:  # noqa: BLE001 – Netz, Zeitlimit, HTTP-Fehler
            print(f"{name}: Versuch {versuch}/{versuche} fehlgeschlagen: {exc}", file=sys.stderr)
            if versuch < versuche:
                time.sleep(PAUSE_S * versuch)
            continue
        pfad.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
        return daten
    print(f"{name}: übersprungen – später mit --neu erneut versuchen", file=sys.stderr)
    return None


PAUSE_S = 20


def hole_osm(neu: bool = False) -> list[dict] | None:
    import requests

    def holen():
        r = requests.post(
            OVERPASS, data={"data": OVERPASS_ABFRAGE}, headers={"User-Agent": USER_AGENT},
            timeout=300,
        )  # fmt: skip
        r.raise_for_status()
        return r.json().get("elements", [])

    return _lade_json("osm_rp.json", holen, neu)


def hole_wikidata(neu: bool = False) -> list[dict] | None:
    import requests

    def holen():
        r = requests.get(
            WIKIDATA, params={"query": WIKIDATA_ABFRAGE, "format": "json"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
            timeout=120,
        )  # fmt: skip
        r.raise_for_status()
        return r.json()["results"]["bindings"]

    return _lade_json("wikidata_rp.json", holen, neu)


def suche(
    vereine: list[Verein],
    osm: list[dict] | None,
    wikidata: list[dict] | None,
    raten: bool = True,
    parallel: int = 16,
    abrufer: Abrufer | None = None,
    meldung=print,
    fortschritt: bool = False,
) -> list[Treffer]:
    """Kandidaten sammeln (OSM, Wikidata, geratene Domains), parallel prüfen; Verzeichnisse
    (SPERRLISTE) fallen weg. Geraten wird nur für Vereine ohne Treffer aus OSM/Wikidata."""
    abrufer = abrufer or Abrufer()
    kandidaten = []
    if osm is not None:
        kandidaten += osm_treffer(vereine, osm)
    if wikidata is not None:
        kandidaten += wikidata_treffer(vereine, wikidata)
    kandidaten = [t for t in kandidaten if not _gesperrt(domain_von(t.website), SPERRLISTE)]
    je_quelle = Counter(t.quelle for t in kandidaten)
    meldung(
        f"OpenStreetMap: {je_quelle['openstreetmap']} Kandidaten, "
        f"Wikidata: {je_quelle['wikidata']} Kandidaten"
    )
    if raten:
        mit = {t.verein.id for t in kandidaten}
        geraten = [
            (v, d) for v in vereine if v.id not in mit for d in domain_kandidaten(v.name, v.orte)
        ]
        da = _parallel(
            lambda vd: abrufer.existiert(vd[1]), geraten, parallel, "DNS prüfen",
            fortschritt, lambda ok: "existieren" if ok else None,
        )  # fmt: skip
        neu = [
            Treffer(v, d, "domain geraten") for (v, d), ok in zip(geraten, da, strict=True) if ok
        ]
        n_vereine = len({v.id for v, _ in geraten})
        meldung(
            f"Domains geraten für {n_vereine} Vereine: {len(geraten)} versucht, "
            f"{len(neu)} existieren"
        )
        kandidaten += neu
    # eine Webseite je Verein nur einmal prüfen
    einmal = {}
    for t in kandidaten:
        einmal.setdefault((t.verein.id, domain_von(t.website)), t)
    return _parallel(
        lambda t: pruefe(t, abrufer), list(einmal.values()), parallel, "Webseiten prüfen",
        fortschritt, einstufung,
    )  # fmt: skip


def einstufung(t: Treffer) -> str:
    """Für Fortschritt und Zusammenfassung: wie verlässlich ist ein geprüfter Treffer?"""
    if t.punkte < 0:
        return "weg"  # nicht erreichbar oder Weiterleitung auf ein Verzeichnis
    if "soziales Netzwerk" in t.nachweis:
        return "sozial"
    if "robots.txt" in t.nachweis:
        return "robots"
    return "sicher" if t.punkte >= 3 else "wahrscheinlich" if t.punkte == 2 else "unsicher"


def _parallel(fn, werte: list, parallel: int, text: str, fortschritt: bool, art=None) -> list:
    """`fn` für alle `werte` parallel; Ergebnisse in der Reihenfolge der Werte. Mit
    `fortschritt` ein Balken (tqdm, auf stderr), der laufend zählt, was `art(ergebnis)`
    liefert (z. B. „sicher=12 weg=30“)."""
    out = [None] * len(werte)
    zaehler: Counter = Counter()
    balken = None
    if fortschritt and werte:
        from tqdm import tqdm

        balken = tqdm(total=len(werte), desc=text, unit=" ", dynamic_ncols=True, smoothing=0.05)
    with ThreadPoolExecutor(parallel) as pool:
        laeufe = {pool.submit(fn, w): i for i, w in enumerate(werte)}
        for f in as_completed(laeufe):
            out[laeufe[f]] = ergebnis = f.result()
            if balken is not None:
                if art and (k := art(ergebnis)):
                    zaehler[k] += 1
                    balken.set_postfix_str(
                        " ".join(f"{k}={n}" for k, n in sorted(zaehler.items())), refresh=False
                    )
                balken.update()
    if balken is not None:
        balken.close()
    return out


def zusammenfassung(treffer: list[Treffer], vereine: int) -> str:
    """Kurze Übersicht am Ende: Treffer nach Einstufung und Quelle, Vereine mit gutem Treffer."""
    stufen = ("sicher", "wahrscheinlich", "unsicher", "sozial", "robots", "weg")
    quellen = sorted({t.quelle for t in treffer})
    zeilen = [f"{'':16}" + "".join(f"{q:>16}" for q in quellen) + f"{'zusammen':>12}"]
    for s in stufen:
        n = [sum(t.quelle == q and einstufung(t) == s for t in treffer) for q in quellen]
        if sum(n):
            zeilen.append(f"{s:16}" + "".join(f"{x:>16}" for x in n) + f"{sum(n):>12}")
    beste: dict[str, int] = {}
    for t in treffer:
        beste[t.verein.id] = max(beste.get(t.verein.id, -1), t.punkte)
    gut = sum(p >= 3 for p in beste.values())
    eher = sum(p == 2 for p in beste.values())
    zeilen.append(
        f"Vereine: {vereine}; mit sicherem Treffer (3–4 Punkte) {gut}, mit wahrscheinlichem "
        f"(2 Punkte) {eher}, ohne {vereine - gut - eher}"
    )
    return "\n".join(zeilen)


def schreibe(treffer: list[Treffer], ziel: Path = ERGEBNIS) -> int:
    """CSV zum Prüfen: je Verein die besten Treffer zuerst; nicht erreichbare fallen weg."""
    zeilen = sorted(
        (t for t in treffer if t.punkte >= 0),
        key=lambda t: (t.verein.name.lower(), t.verein.id, -t.punkte, t.website),
    )
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "typ", "website", "quelle", "punkte", "nachweis", "orte"])
        for t in zeilen:
            v = t.verein
            w.writerow(
                [v.id, v.name, v.typ, t.website, t.quelle, t.punkte, t.nachweis,
                 "; ".join(sorted(v.orte))]
            )  # fmt: skip
    return len(zeilen)


def argumente(p: argparse.ArgumentParser) -> None:
    """Optionen des Befehls `sportstaettenatlas crawler`."""
    p.add_argument("--daten", type=Path, default=Path("daten"))
    p.add_argument("--kreis", help="nur Vereine mit Sportstätte in diesem Kreis (z. B. 07111)")
    p.add_argument(
        "--max", type=int, help="Probelauf: so viele zufällig gewählte Vereine (immer dieselben)"
    )
    p.add_argument("--parallel", type=int, default=16, help="gleichzeitige Abrufe (Standard 16)")
    p.add_argument("--ohne-osm", action="store_true")
    p.add_argument("--ohne-wikidata", action="store_true")
    p.add_argument("--ohne-raten", action="store_true", help="keine Domains raten")
    p.add_argument("--neu", action="store_true", help="OSM und Wikidata neu abfragen (Cache)")
    p.add_argument("--ziel", type=Path, default=ERGEBNIS)


def ausfuehren(a) -> int:
    if not KONTAKT:
        grund = "ungültig (nur ASCII-Zeichen)" if KONTAKT_ROH.strip() else "nicht gesetzt"
        print(
            f"Hinweis: SPORTSTAETTENATLAS_KONTAKT ist {grund} – Overpass und Wikidata bitten "
            "um einen Kontakt im User-Agent, z. B. eine Mail-Adresse des Projekts.",
            file=sys.stderr,
        )
    elif KONTAKT != KONTAKT_ROH.strip():
        print(f"Hinweis: Kontakt im User-Agent ohne Sonderzeichen: {KONTAKT}", file=sys.stderr)
    vereine = vereine_ohne_webseite(a.daten, a.kreis)
    if a.max and a.max < len(vereine):  # Stichprobe über das ganze Alphabet, wiederholbar
        vereine = sorted(random.Random(a.max).sample(vereine, a.max), key=lambda v: v.name.lower())
    print(f"Vereine ohne Webseite: {len(vereine)}")
    osm = None if a.ohne_osm else hole_osm(a.neu)
    wd = None if a.ohne_wikidata else hole_wikidata(a.neu)
    treffer = suche(vereine, osm, wd, raten=not a.ohne_raten, parallel=a.parallel, fortschritt=True)
    n = schreibe(treffer, a.ziel)
    print(zusammenfassung(treffer, len(vereine)))
    print(f"{a.ziel}: {n} Treffer zum Prüfen (ohne „weg“)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="sportstaettenatlas crawler",
        description="Webseiten für Vereine ohne Webseite suchen → results/vereinswebseiten.csv",
    )
    argumente(p)
    return ausfuehren(p.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
