"""Einträge aus daten/ entfernen (Tabelle mit art, id, begruendung; Befehl `bestand`).

Die Zeilen werden von oben nach unten abgearbeitet. Zeigt noch etwas auf den Eintrag (eine
Sportanlage oder ein Stützpunkt auf eine Sportstätte, eine Sportstätte auf ihren Sportkomplex
oder ihren Betreiber …), wird er mit einer Warnung übersprungen; was vorher Verweise löst, steht also weiter oben
oder in einer Tabelle, die `bestand` vorher einliest. Jede Entfernung kommt mit Datum und
Begründung nach daten/entfernt.csv, damit sie nachvollziehbar bleibt.
"""

from __future__ import annotations

import csv
import datetime
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import werte
from .bestand import (
    EMAIL,
    _laender,
    _lies_json,
    _staetten_dirs,
    komplex_dateien,
    org_dateien,
    org_schluessel,
    stuetzpunkt_dateien,
)

PROTOKOLL = "entfernt.csv"  # in daten/
SPALTEN = ("art", "id", "begruendung")
# Werte der Spalte art (ohne Groß-/Kleinschreibung, Umlaute, Leerzeichen; auch Mehrzahl)
ARTEN = {
    "sportstaette": "Sportstätte",
    "sportstaetten": "Sportstätte",
    "sportanlage": "Sportanlage",
    "sportanlagen": "Sportanlage",
    "anlage": "Sportanlage",
    "sportkomplex": "Sportkomplex",
    "sportkomplexe": "Sportkomplex",
    "stuetzpunkt": "Stützpunkt",
    "stuetzpunkte": "Stützpunkt",
    "organisation": "Organisation",
    "organisationen": "Organisation",
}


@dataclass
class Ergebnis:
    entfernt: list[tuple[str, str, str]] = field(default_factory=list)  # (Art, ID, Name)
    warnungen: list[str] = field(default_factory=list)


def ist_tabelle(normierte_spalten: set[str]) -> bool:
    return set(SPALTEN) <= normierte_spalten


def _norm(text: str) -> str:
    t = str(text or "").lower().strip()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    return "".join(c for c in t if c.isalnum())


def lies(pfad: Path) -> list[dict]:
    """Tabelle → [{"zeile", "art", "id", "begruendung"}] in der Reihenfolge der Datei."""
    zeilen = werte.zeilen(werte.text(Path(pfad).read_bytes()))
    out = []
    for i, z in enumerate(zeilen, start=2):  # Zeile 1: Kopf
        z = {_norm(k): (v or "").strip() for k, v in z.items() if k}
        if any(z.get(k) for k in SPALTEN):
            out.append({"zeile": i, **{k: z.get(k, "") for k in SPALTEN}})
    return out


class _Bestand:
    """Was in daten/ liegt und worauf es zeigt; nach jeder Entfernung nachgeführt."""

    def __init__(self, daten: Path):
        self.daten = Path(daten)
        self.staetten: dict[str, tuple[Path, dict]] = {}  # ID → (Ordner, Meta)
        self.anlagen: dict[str, tuple[Path, dict]] = {}  # ID → (Datei, Anlage)
        for land in _laender(self.daten):
            for ordner in _staetten_dirs(land):
                meta = ordner / f"{ordner.name}_meta.json"
                if not meta.exists():
                    continue
                self.staetten[ordner.name] = (ordner, _lies_json(meta))
                for p in ordner.glob("*.json"):
                    if p != meta:
                        self.anlagen[p.stem] = (p, _lies_json(p))
        self.komplexe = {p.stem: (p, _lies_json(p)) for p in komplex_dateien(self.daten)}
        self.stuetzpunkte = {p.stem: (p, _lies_json(p)) for p in stuetzpunkt_dateien(self.daten)}
        self.organisationen = {p.stem: (p, _lies_json(p)) for p in org_dateien(self.daten)}

    def sammlung(self, art: str) -> dict[str, tuple[Path, dict]]:
        return {
            "Sportstätte": self.staetten,
            "Sportanlage": self.anlagen,
            "Sportkomplex": self.komplexe,
            "Stützpunkt": self.stuetzpunkte,
            "Organisation": self.organisationen,
        }[art]

    def verweise(self, art: str, oid: str, d: dict) -> list[str]:
        """Was noch auf den Eintrag zeigt (lesbar, höchstens ein paar)."""
        out = []
        stp = [s for _, s in self.stuetzpunkte.values()]
        if art == "Sportstätte":
            ordner = self.staetten[oid][0]
            out += [
                f"Sportanlage „{a.get('typ')}“ ({i[:8]})"
                for i, (p, a) in self.anlagen.items()
                if p.parent == ordner
            ]
            out += [
                f"Stützpunkt „{s.get('name')}“"
                for s in stp
                if oid in (s.get("sportstaetten") or [])
            ]
        elif art == "Sportkomplex":
            out += [
                f"Sportstätte „{m.get('name')}“"
                for _, m in self.staetten.values()
                if m.get("sportkomplex") == oid
            ]
            out += [
                f"Stützpunkt „{s.get('name')}“"
                for s in stp
                if oid in (s.get("sportkomplexe") or [])
            ]
        elif art == "Organisation":
            namen = {
                org_schluessel(n) for n in [d.get("name"), *(d.get("weitere_namen") or [])] if n
            }
            for _, m in self.staetten.values():
                rollen = [m.get("eigentuemer"), m.get("betreiber"), *(m.get("nutzer") or [])]
                if any(org_schluessel(r) in namen for r in rollen if r):
                    out.append(f"Sportstätte „{m.get('name')}“")
            for s in stp:
                if any(
                    org_schluessel(s.get(k)) in namen
                    for k in ("traeger", "anerkannt_von")
                    if s.get(k)
                ):
                    out.append(f"Stützpunkt „{s.get('name')}“")
            for _, o in self.organisationen.values():
                if (
                    o.get("id") != oid
                    and o.get("uebergeordnet")
                    and (o["uebergeordnet"] == oid or org_schluessel(o["uebergeordnet"]) in namen)
                ):
                    out.append(f"Organisation „{o.get('name')}“")
        return out

    def entferne(self, art: str, oid: str) -> None:
        pfad, _ = self.sammlung(art).pop(oid)
        if art == "Sportstätte":  # nur noch die Meta-Datei: die Anlagen sind schon entfernt
            shutil.rmtree(pfad)
        else:
            pfad.unlink()


def _protokolliere(daten: Path, zeilen: list[list[str]]) -> None:
    pfad = Path(daten) / PROTOKOLL
    neu = not pfad.exists()
    with pfad.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        if neu:
            w.writerow(["datum", "art", "id", "name", "begruendung"])
        w.writerows(zeilen)


def entferne(eintraege: list[dict], daten: Path, probe: bool = False) -> Ergebnis:
    """Einträge von oben nach unten entfernen; übersprungen wird mit Warnung, was unbekannt
    ist, keine Begründung hat oder worauf noch etwas zeigt. `probe`: nur prüfen."""
    b, e, protokoll = _Bestand(daten), Ergebnis(), []
    heute = datetime.datetime.now().astimezone().date().isoformat()
    for z in eintraege:
        wo = f"Zeile {z['zeile']}"
        art = ARTEN.get(_norm(z["art"]))
        if not art:
            e.warnungen.append(f"{wo}: unbekannte Art „{z['art']}“ (übersprungen)")
            continue
        if not z["begruendung"]:
            e.warnungen.append(f"{wo}: ohne Begründung (übersprungen)")
            continue
        if EMAIL.search(z["begruendung"]):
            e.warnungen.append(f"{wo}: Begründung mit E-Mail-Adresse (übersprungen)")
            continue
        kurz = z["id"]
        treffer = [
            i for i in b.sammlung(art) if i == kurz or (len(kurz) >= 8 and i.startswith(kurz))
        ]
        if len(treffer) != 1:
            grund = "mehrdeutig" if treffer else "nicht gefunden"
            e.warnungen.append(f"{wo}: {art} {kurz or '(ohne ID)'} {grund} (übersprungen)")
            continue
        oid = treffer[0]
        d = b.sammlung(art)[oid][1]
        name = d.get("name") or d.get("typ") or ""
        if verweise := b.verweise(art, oid, d):
            mehr = f" und {len(verweise) - 3} weitere" if len(verweise) > 3 else ""
            e.warnungen.append(
                f"{wo}: {art} „{name}“ ({oid[:8]}) – noch verwendet von "
                f"{', '.join(verweise[:3])}{mehr} (übersprungen)"
            )
            continue
        if not probe:
            b.entferne(art, oid)
        else:
            b.sammlung(art).pop(oid)  # damit spätere Zeilen den Stand danach sehen
        e.entfernt.append((art, oid, name))
        protokoll.append([heute, art, oid, name, z["begruendung"]])
    if protokoll and not probe:
        _protokolliere(daten, protokoll)
    return e


def schreibe_vorlage(pfad: Path) -> Path:
    """vorlage_entfernen.csv mit einer Beispielzeile (; getrennt, mit BOM für Excel)."""
    with Path(pfad).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(SPALTEN)
        w.writerow(["Sportstätte", "5e6f7a8b", "Doppelung: gehört als Anlage zu Sportplatz Berg"])
    return Path(pfad)
