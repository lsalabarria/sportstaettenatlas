"""Höfliche HTTP-Sitzung: Disk-Cache, Pause je Host, robots.txt, Wiederholungen."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)

# Kontakt für den User-Agent (für Abfragen beim Katasterdienst).
# Setzen mit: export SPORTSTAETTENATLAS_KONTAKT="name@example.org"
KONTAKT = os.environ.get("SPORTSTAETTENATLAS_KONTAKT", "")
USER_AGENT = "sportstaettenatlas/0.1 (Forschungsprototyp Sportstaettenatlas" + (
    f"; {KONTAKT})" if KONTAKT else ")"
)
UA_ROBOTS = "sportstaettenatlas"


@dataclass
class Antwort:
    url: str
    status: int
    inhalt: bytes
    content_type: str = ""
    aus_cache: bool = False

    def text(self) -> str:
        return self.inhalt.decode("utf-8", errors="replace")

    def json(self):
        return json.loads(self.inhalt)


class RobotsVerbot(Exception):
    pass


class Zeitueberschreitung(Exception):
    """Gesamtfrist für eine Website abgelaufen."""


@dataclass
class Profil:
    """Zeitverhalten einer Anfrage. APIs: großzügig; Websites: knapp mit Gesamtfrist."""

    timeout: float | tuple[float, float] = 60
    versuche: int = 3
    max_pause: float = 120  # längste Wartezeit bei 429/503 bzw. zwischen Versuchen
    frist: float | None = None  # time.monotonic()-Zeitpunkt, ab dem abgebrochen wird
    max_bytes: int = 50 * 1024 * 1024

    @classmethod
    def website(cls, gesamt_s: float = 60) -> Profil:
        return cls(
            timeout=(10, 20),
            versuche=2,
            max_pause=5,
            frist=time.monotonic() + gesamt_s,
            max_bytes=3 * 1024 * 1024,
        )

    def pruefe_frist(self, url: str) -> None:
        if self.frist is not None and time.monotonic() > self.frist:
            raise Zeitueberschreitung(url)


class Sitzung:
    """GET/POST mit Cache. `robots=True` prüft robots.txt (für Websites, nicht für APIs)."""

    def __init__(
        self,
        cache: Path,
        pause_s: float = 1.0,
        timeout: float = 200,  # große WFS-Kacheln brauchen teils lange
        versuche: int = 3,
        cache_tage: float = 30,
    ):
        self.cache = cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self.pause_s = pause_s
        self.timeout = timeout
        self.versuche = versuche
        self.cache_s = cache_tage * 86400
        self._letzter: dict[str, float] = {}
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self.s.headers["Accept-Language"] = "de,en;q=0.5"

    # --- Cache -------------------------------------------------------------
    def _schluessel(self, methode: str, url: str, daten) -> Path:
        roh = json.dumps([methode, url, daten], sort_keys=True, ensure_ascii=False)
        h = hashlib.sha256(roh.encode()).hexdigest()
        return self.cache / h[:2] / f"{h}.json"

    def _aus_cache(self, pfad: Path) -> Antwort | None:
        if not pfad.exists() or time.time() - pfad.stat().st_mtime > self.cache_s:
            return None
        d = json.loads(pfad.read_text("utf-8"))
        return Antwort(
            d["url"],
            d["status"],
            d["inhalt"].encode("utf-8", "surrogateescape"),
            d.get("content_type", ""),
            aus_cache=True,
        )

    def _in_cache(self, pfad: Path, a: Antwort) -> None:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(
            json.dumps(
                {
                    "url": a.url,
                    "status": a.status,
                    "content_type": a.content_type,
                    "inhalt": a.inhalt.decode("utf-8", "surrogateescape"),
                }
            ),
            "utf-8",
        )

    # --- Höflichkeit -------------------------------------------------------
    def _warte(self, host: str) -> None:
        seit = time.time() - self._letzter.get(host, 0)
        if seit < self.pause_s:
            time.sleep(self.pause_s - seit)
        self._letzter[host] = time.time()

    def darf(self, url: str, profil: Profil | None = None) -> bool:
        teile = urlsplit(url)
        basis = f"{teile.scheme}://{teile.netloc}"
        if basis not in self._robots:
            rp = robotparser.RobotFileParser()
            try:
                a = self._roh("GET", basis + "/robots.txt", None, robots=False, profil=profil)
                if a.status >= 400:
                    rp = None  # keine robots.txt = alles erlaubt
                else:
                    rp.parse(a.text().splitlines())
            except (requests.RequestException, Zeitueberschreitung):
                rp = None
            self._robots[basis] = rp
        rp = self._robots[basis]
        return True if rp is None else rp.can_fetch(UA_ROBOTS, url)

    # --- Abruf -------------------------------------------------------------
    def _lies(self, r: requests.Response, profil: Profil) -> bytes:
        """Antwort stückweise lesen – mit Gesamtfrist und Größenlimit."""
        teile, groesse = [], 0
        for stueck in r.iter_content(64 * 1024):
            teile.append(stueck)
            groesse += len(stueck)
            if profil.frist is not None and time.monotonic() > profil.frist:
                r.close()
                raise Zeitueberschreitung(r.url)
            if groesse > profil.max_bytes:
                break  # für Metadaten reicht der Anfang der Seite
        return b"".join(teile)

    def _roh(
        self, methode: str, url: str, daten, robots: bool, profil: Profil | None = None
    ) -> Antwort:
        profil = profil or Profil(timeout=self.timeout, versuche=self.versuche)
        pfad = self._schluessel(methode, url, daten)
        if (a := self._aus_cache(pfad)) is not None:
            return a
        if robots and not self.darf(url, profil):
            raise RobotsVerbot(url)
        host = urlsplit(url).netloc
        for versuch in range(1, profil.versuche + 1):
            profil.pruefe_frist(url)
            self._warte(host)
            try:
                if methode == "POST":
                    r = self.s.post(url, data=daten, timeout=profil.timeout, stream=True)
                else:
                    r = self.s.get(url, params=daten, timeout=profil.timeout, stream=True)
                if r.status_code in (429, 502, 503, 504) and versuch < profil.versuche:
                    warte = min(
                        float(r.headers.get("Retry-After", 10 * versuch) or 0), profil.max_pause
                    )
                    r.close()
                    log.warning("%s: HTTP %s, warte %ss", host, r.status_code, warte)
                    time.sleep(warte)
                    continue
                inhalt = self._lies(r, profil)
                a = Antwort(r.url, r.status_code, inhalt, r.headers.get("Content-Type", ""))
                if r.status_code < 500:
                    self._in_cache(pfad, a)
                return a
            except (requests.ConnectionError, requests.Timeout):
                if versuch == profil.versuche:
                    raise
                time.sleep(min(5 * versuch, profil.max_pause))
        raise AssertionError("unerreichbar")

    def get(
        self,
        url: str,
        params: dict | None = None,
        robots: bool = False,
        profil: Profil | None = None,
    ) -> Antwort:
        return self._roh("GET", url, params, robots, profil)

    def post(self, url: str, daten: dict, versuche: int | None = None) -> Antwort:
        profil = Profil(timeout=self.timeout, versuche=versuche or self.versuche)
        return self._roh("POST", url, daten, robots=False, profil=profil)
