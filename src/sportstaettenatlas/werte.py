"""Werte aus Text lesen – gemeinsam für den Atlas-Export (atlas.py) und andere CSV (einlesen.py).

Die Regeln für Zellen (Zahlen, ja/nein, Listen) beschreibt daten/README.md („CSV einlesen“).
Jede Funktion wirft ValueError, wenn der Text nicht passt; `oder_none` macht daraus None.
"""

from __future__ import annotations

import csv
import io
import re

from . import anlagen as anlagen_typen

JA = {"ja", "j", "1", "x", "true", "wahr", "yes", "y"}
NEIN = {"nein", "n", "0", "false", "falsch", "no"}


# --- Dateien -----------------------------------------------------------------------------


def text(roh: bytes) -> str:
    """Inhalt einer CSV: UTF-8 (mit oder ohne BOM), sonst Windows-1252 (Excel)."""
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return roh.decode(enc)
        except UnicodeDecodeError:
            continue
    return roh.decode("utf-8", errors="replace")


def trenner(inhalt: str) -> str:
    """Trennzeichen aus der Kopfzeile: das häufigste von ; , und Tab (außerhalb von
    Anführungszeichen). Fester als csv.Sniffer, dessen Ergebnis je nach Python-Version und
    Inhalt der ersten Zeilen schwankt."""
    kopf = re.sub(r'"[^"]*"', "", inhalt.split("\n", 1)[0])
    zahl_je = {t: kopf.count(t) for t in (";", ",", "\t")}
    return max(zahl_je, key=zahl_je.get) if any(zahl_je.values()) else ","


def zeilen(inhalt: str) -> list[dict]:
    """CSV-Text → Zeilen als {Spalte: Text}."""
    return list(csv.DictReader(io.StringIO(inhalt), delimiter=trenner(inhalt)))


# --- Zellen ------------------------------------------------------------------------------


def zahl(t: str) -> float:
    """12,5 · 12.5 · 1.234,5 · 1.200.000 → Zahl."""
    t = str(t).replace(" ", "").replace(" ", "")
    if "," in t and "." in t:  # 1.234,5
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    elif t.count(".") > 1:  # 1.200.000
        t = t.replace(".", "")
    return float(t)


def ganzzahl(t: str) -> int:
    """Wie zahl, aber ganz; „1.200“ ist hier 1200 (Tausenderpunkt)."""
    t = str(t).strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    z = zahl(t)
    if z != int(z):
        raise ValueError(t)
    return int(z)


def ja_nein(t: str) -> str:
    """ja, X, 1, wahr … → "ja"; nein, 0, falsch … → "nein"."""
    w = str(t).strip().lower()
    if w in JA:
        return "ja"
    if w in NEIN:
        return "nein"
    raise ValueError(t)


def liste(t: str) -> list[str]:
    """Mit ; getrennt; ohne ; mit Komma, aber nicht in Klammern („Großspielfeld (ab 5.000 m²,
    Rasen)“ bleibt eins) und nicht nach Bindestrich („Weit-, Dreisprunganlage“)."""
    t = t or ""
    teile = t.split(";") if ";" in t else re.split(r",\s*(?![^()]*\))", t)
    return [x for x in anlagen_typen.zusammenfuegen(teile) if x]


def oder_none(lesen, t: str | None):
    """lesen(t), aber None statt ValueError und für leeren Text."""
    if t is None or not str(t).strip():
        return None
    try:
        return lesen(str(t).strip())
    except ValueError:
        return None


def slug(text: str) -> str:
    """Text → Ordnername: klein, Umlaute ausgeschrieben, sonst nur a-z, 0-9 und -."""
    t = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


# --- Pfade in verschachtelten Angaben („adresse.plz“) -------------------------------------


def hole(d: dict, pfad: str):
    """Wert unter einem Pfad wie "adresse.plz"; None, wenn er fehlt."""
    for teil in pfad.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(teil)
    return d


def setze(d: dict, pfad: str, w) -> None:
    """Wert unter einem Pfad setzen (fehlende Ebenen entstehen); ein leerer Wert entfernt ihn."""
    *vorne, letzter = pfad.split(".")
    for teil in vorne:
        d = d.setdefault(teil, {})
    if w in (None, "", [], {}):
        d.pop(letzter, None)
    else:
        d[letzter] = w
