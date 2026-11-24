"""Werte aus Text lesen – gemeinsam für den Atlas-Export (pflege/atlas_export.py) und andere CSV (einlesen.py).

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


# --- Häufige Formfehler beheben (beim Einlesen und mit `migrieren --bereinigen`) -----------

_PLATZHALTER = {"-", "--", "/", "?", "k.a.", "k. a.", "keine", "nicht bekannt", "unbekannt"}
_DOMAIN = re.compile(r"^(?:www\.)?[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}(?:[/?#]\S*)?$", re.IGNORECASE)


# Monate, wie Excel sie in Hausnummern schreibt, die es für ein Datum hält („2-4“ → „02. Apr“)
_MONATE = {
    **dict.fromkeys(("jan", "januar", "january"), 1),
    **dict.fromkeys(("feb", "februar", "february"), 2),
    **dict.fromkeys(("mär", "mrz", "mar", "märz", "march"), 3),
    **dict.fromkeys(("apr", "april"), 4),
    **dict.fromkeys(("mai", "may"), 5),
    **dict.fromkeys(("jun", "juni", "june"), 6),
    **dict.fromkeys(("jul", "juli", "july"), 7),
    **dict.fromkeys(("aug", "august"), 8),
    **dict.fromkeys(("sep", "sept", "september"), 9),
    **dict.fromkeys(("okt", "oct", "oktober", "october"), 10),
    **dict.fromkeys(("nov", "november"), 11),
    **dict.fromkeys(("dez", "dec", "dezember", "december"), 12),
}
_TAG_MONAT = re.compile(r"(\d{1,2})\.?[ -]?([a-zäA-ZÄ]{3,9})\.?")  # „02. Apr“, „2-Apr“
_MONAT_ZAHL = re.compile(r"([a-zäA-ZÄ]{3,9})\.?[ -]?(\d{1,2})")  # „Aug 14“, „Aug-14“


def _hausnummer_aus_datum(t: str) -> str | None:
    """Von Excel zum Datum gemachte Hausnummer zurück: „02. Apr“ → „2-4“, „Aug 14“ → „8-14“
    (die kleinere Zahl vorne). None, wenn es nicht so aussieht."""
    for muster, monat_vorne in ((_TAG_MONAT, False), (_MONAT_ZAHL, True)):
        if m := muster.fullmatch(t):
            wort, zahl = (m.group(1), m.group(2)) if monat_vorne else (m.group(2), m.group(1))
            if (monat := _MONATE.get(wort.lower())) and int(zahl):
                a, b = sorted((monat, int(zahl)))
                return f"{a}-{b}"
    return None


def hausnummer(t: str) -> str | None:
    """„6.0“ (von Excel als Zahl gespeichert) → „6“; von Excel zum Datum gemacht („02. Apr“,
    „Aug 14“) → „2-4“, „8-14“; Platzhalter wie „-“ → None."""
    t = str(t).strip()
    if t.lower() in _PLATZHALTER:
        return None
    if m := re.fullmatch(r"(\d+)\.0+", t):
        return m.group(1)
    return _hausnummer_aus_datum(t) or t


def plz(t: str) -> str:
    """Vierstellige PLZ, deren führende Null verloren ging (als Zahl gespeichert): „4109“ →
    „04109“."""
    t = str(t).strip()
    return f"0{t}" if re.fullmatch(r"\d{4}", t) else t


def ort_aus_dict(adresse: dict) -> bool:
    """Ort, der als Text eines Python-Dicts gespeichert ist („{'ags': '07131006', 'ort': 'Bad
    Breisig, Stadt', 'postleitzahl': '53498'}“, Altsystem): Ort daraus, fehlende PLZ auch.
    True, wenn sich etwas geändert hat."""
    import ast

    t = adresse.get("ort")
    if not (isinstance(t, str) and t.strip().startswith("{")):
        return False
    try:
        d = ast.literal_eval(t.strip())
    except (ValueError, SyntaxError):
        return False
    if not isinstance(d, dict) or not str(d.get("ort") or "").strip():
        return False
    adresse["ort"] = str(d["ort"]).strip()
    if not adresse.get("plz") and str(d.get("postleitzahl") or "").strip():
        adresse["plz"] = str(d["postleitzahl"]).strip()
    return True


def website(t: str) -> str | None:
    """„www.verein.de“ → „https://www.verein.de“; Platzhalter wie „-“ → None. Was nicht wie
    eine einzelne Adresse aussieht (z. B. zwei durch Komma), bleibt, wie es ist."""
    t = str(t).strip()
    if t.lower() in _PLATZHALTER:
        return None
    return f"https://{t}" if _DOMAIN.fullmatch(t) else t


def flaeche_berechnet(d: dict) -> bool:
    """Sportanlage, deren `flaeche` nur Länge × Breite ist (auf 1 % genau) und nicht zu ihrem
    Typ gehört: im Altsystem bei Hallen so berechnet – ohne neue Angabe."""
    from .klassen import fuer_von

    f, lg, br = d.get("flaeche"), d.get("laenge"), d.get("breite")
    if not d.get("typ") or not all(isinstance(x, (int, float)) for x in (f, lg, br)):
        return False
    if d["typ"] in (fuer_von("flaeche") or ()):
        return False
    return lg * br > 0 and abs(f - lg * br) <= 0.01 * lg * br


def bereinige(d: dict) -> list[str]:
    """In einem Datensatz (Sportstätte, Sportkomplex, Organisation …) `website`,
    `adresse.hausnummer`, `adresse.plz` und einen Ort als Dict-Text (ort_aus_dict) bereinigen,
    bei einer Sportanlage eine nur berechnete `flaeche` (flaeche_berechnet) weglassen; liefert
    die Pfade, die sich geändert haben."""
    geaendert = []
    if flaeche_berechnet(d):
        del d["flaeche"]
        geaendert.append("flaeche")
    if isinstance(d.get("adresse"), dict) and ort_aus_dict(d["adresse"]):
        geaendert.append("adresse.ort")
    for pfad, regel in (
        ("website", website),
        ("adresse.hausnummer", hausnummer),
        ("adresse.plz", plz),
    ):
        alt = hole(d, pfad)
        if isinstance(alt, str) and (neu := regel(alt)) != alt:
            setze(d, pfad, neu)
            if isinstance(d.get("adresse"), dict) and not d["adresse"]:
                del d["adresse"]
            geaendert.append(pfad)
    return geaendert


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
