"""Gebietskörperschaften als Organisationen (Befehl `organisationen --gebiete`).

Aus den Verwaltungsgebieten (gebiete.lade, BKG VG250) wird für jeden Landkreis, jede
kreisfreie Stadt, Verbandsgemeinde, verbandsfreie Gemeinde, verbandsangehörige Stadt und
Ortsgemeinde eine Organisation mit amtlichem Namen, Art und Regionalschlüssel (`ars`).
Gemeinden, die zugleich kreisfreie Stadt oder verbandsfreie Gemeinde sind, gibt es nur einmal.
`uebergeordnet` nennt die Verbandsgemeinde bzw. den Landkreis.

Vorhandene Einträge findet der Regionalschlüssel, sonst der Name ohne Zusätze wie „Stadt“
oder „Landkreis“ – nur, wenn das eindeutig ist und die Organisation keine andere Art hat.
Sie bekommen amtlichen Namen, Art und Schlüssel; der bisherige Name bleibt als weitere
Schreibweise. Mehrfach ausführen ändert nichts mehr.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ..bestand import (
    lies_organisationen,
    org_dateien,
    org_schluessel,
    organisation_id,
    schreibe_organisation,
)
from ..bestand.gebiete import schluessel
from ..modell import ORGANISATIONSTYPEN

# Wörter, die beim Vergleich vorhandener Namen nicht zählen, und welche Art sie nahelegen
_ZUSATZ = {
    "landkreis": {"Landkreis"},
    "kreis": {"Landkreis"},
    "kreisfreie": {"Kreisfreie Stadt"},
    "verbandsgemeinde": {"Verbandsgemeinde"},
    "vg": {"Verbandsgemeinde"},
    "verbandsfreie": {"Verbandsfreie Gemeinde"},
    "ortsgemeinde": {"Ortsgemeinde"},
    "og": {"Ortsgemeinde"},
    "gemeinde": {"Ortsgemeinde", "Verbandsfreie Gemeinde"},
    "stadt": {"Kreisfreie Stadt", "Verbandsfreie Gemeinde", "Verbandsangehörige Stadt"},
}


@dataclass
class Bericht:
    neu: int = 0
    ergaenzt: int = 0  # vorhanden, um Art, Schlüssel usw. ergänzt
    umbenannt: list[tuple[str, str]] = field(default_factory=list)  # (bisher, amtlich)
    unveraendert: int = 0
    mehrdeutig: list[tuple[str, list[str]]] = field(default_factory=list)
    je_art: Counter = field(default_factory=Counter)


def _kern(name: str) -> tuple[str, set[str]]:
    """Name ohne Zusätze (zum Vergleichen) und die Arten, die die Zusätze nahelegen."""
    woerter = re.sub(r"[^\wäöüß]+", " ", name.lower()).split()
    arten: set[str] = set()
    rest = []
    for w in woerter:
        if w in _ZUSATZ:
            arten = (arten & _ZUSATZ[w]) or _ZUSATZ[w] if arten else set(_ZUSATZ[w])
        else:
            rest.append(w)
    return " ".join(rest), arten


def _features(gebiete: dict, ebene: str) -> list[dict]:
    """Eigenschaften einer Ebene, je Schlüssel einmal, mit Kurzschlüssel `s`."""
    out: dict[str, dict] = {}
    for f in gebiete[ebene]["features"]:
        p = f.get("properties") or {}
        if p.get("ars"):
            out.setdefault(schluessel(ebene, p["ars"]), {**p, "s": schluessel(ebene, p["ars"])})
    return list(out.values())


def aus_gebieten(gebiete: dict) -> list[dict]:
    """Organisationen der Gebietskörperschaften (ohne id), sortiert nach Schlüssel."""
    kreise = _features(gebiete, "kreis")
    vgs = _features(gebiete, "vg")
    gemeinden = _features(gebiete, "gemeinde")
    kreisfrei = {k["s"] for k in kreise if k.get("bez") == "Kreisfreie Stadt"}
    vfg = {v["s"] for v in vgs if v.get("bez") == "Verbandsfreie Gemeinde"}
    out: list[dict] = []
    kreis_name: dict[str, str] = {}
    vg_name: dict[str, str] = {}
    for k in kreise:
        if k["s"] in kreisfrei:
            o = {"name": f"Stadt {k['name']}", "typ": "Kreisfreie Stadt", "ars": k["s"]}
        else:
            name = k["name"] if "kreis" in k["name"].lower() else f"Landkreis {k['name']}"
            o = {"name": name, "typ": "Landkreis", "ars": k["s"]}
        kreis_name[k["s"]] = o["name"]
        out.append(o)
    bez_vfg = {g["s"][:9]: g.get("bez") for g in gemeinden if g["s"][:9] in vfg}
    for v in vgs:
        if v["s"][:5] in kreisfrei:
            continue  # kreisfreie Städte führt VG250 auch als verbandsfreie Gemeinde
        if v["s"] in vfg:
            art = "Stadt" if bez_vfg.get(v["s"]) == "Stadt" else "Gemeinde"
            o = {"name": f"{art} {v['name']}", "typ": "Verbandsfreie Gemeinde"}
        else:
            o = {"name": f"Verbandsgemeinde {v['name']}", "typ": "Verbandsgemeinde"}
        o |= {"ars": v["s"], "uebergeordnet": kreis_name.get(v["s"][:5])}
        vg_name[v["s"]] = o["name"]
        out.append(o)
    for g in gemeinden:
        if g["s"][:5] in kreisfrei or g["s"][:9] in vfg:
            continue  # schon als kreisfreie Stadt bzw. verbandsfreie Gemeinde da
        stadt = g.get("bez") == "Stadt"
        out.append(
            {
                "name": f"{'Stadt' if stadt else 'Ortsgemeinde'} {g['name']}",
                "typ": "Verbandsangehörige Stadt" if stadt else "Ortsgemeinde",
                "ars": g["s"],
                "uebergeordnet": vg_name.get(g["s"][:9]),
            }
        )
    # die übliche Kurzform als weitere Schreibweise, wenn sie eindeutig ist (vor dem
    # Unterscheiden gleicher Namen: „Gemeinde Berg“ gibt es dann zweimal und entfällt)
    kurz = {o["ars"]: _kurzformen(o) for o in out}
    # gleiche Namen (z. B. zwei Ortsgemeinden „Berg“) unterscheidet die übergeordnete Ebene
    zahl = Counter(org_schluessel(o["name"]) for o in out)
    for o in out:
        if zahl[org_schluessel(o["name"])] > 1:
            oben = o.get("uebergeordnet") or ""
            oben = re.sub(r"^Verbandsgemeinde ", "VG ", oben)
            o["name"] = f"{o['name']} ({oben})" if oben else o["name"]
    zahl = Counter(org_schluessel(n) for v in kurz.values() for n in v)
    zahl.update(org_schluessel(o["name"]) for o in out)
    for o in out:
        if weitere := [n for n in kurz[o["ars"]] if zahl[org_schluessel(n)] == 1]:
            o["weitere_namen"] = weitere
    return sorted(out, key=lambda o: (len(o["ars"]), o["ars"]))


def _kurzformen(o: dict) -> list[str]:
    n = o["name"]
    if o["typ"] == "Landkreis":
        rest = n.removeprefix("Landkreis ")
        return [f"Kreis {rest}", f"{rest}, Landkreis"] if rest != n else []
    if o["typ"] == "Verbandsgemeinde":
        return ["VG " + n.removeprefix("Verbandsgemeinde ")]
    if o["typ"] == "Ortsgemeinde":
        return ["Gemeinde " + n.removeprefix("Ortsgemeinde ")]
    if o["typ"] == "Kreisfreie Stadt":
        return [n.removeprefix("Stadt ")]
    return []


def lege_an(daten: Path, gebiete: dict) -> Bericht:
    """Gebietskörperschaften ins Verzeichnis daten/organisationen/ (siehe oben)."""
    b = Bericht()
    dateien = {p.stem: p for p in org_dateien(daten)}
    vorhanden = lies_organisationen(daten)
    nach_ars = {o["ars"]: o for o in vorhanden if o.get("ars")}
    nach_kern: dict[str, list[dict]] = {}
    for o in vorhanden:
        if not o.get("ars") and ORGANISATIONSTYPEN.get(o.get("typ") or "") in (None, "Kommune"):
            for n in [o["name"], *(o.get("weitere_namen") or [])]:
                nach_kern.setdefault(_kern(n)[0], []).append(o)
    neu = aus_gebieten(gebiete)
    kandidaten: dict[str, list[dict]] = {}  # id vorhandener → passende amtliche
    for k in neu:
        for o in nach_kern.get(_kern(k["name"])[0], []):
            if o["id"] not in {x["id"] for x in nach_ars.values()}:
                kandidaten.setdefault(o["id"], []).append(k)
    zuordnung: dict[str, dict] = {}  # ars → vorhandene
    nach_id = {o["id"]: o for o in vorhanden}
    for oid, liste in kandidaten.items():
        o = nach_id[oid]
        arten = _kern(o["name"])[1] or ({o["typ"]} if o.get("typ") in _arten() else set())
        passend = [k for k in liste if not arten or k["typ"] in arten]
        if len(passend) == 1 and passend[0]["ars"] not in zuordnung:
            zuordnung[passend[0]["ars"]] = o
        else:
            b.mehrdeutig.append((o["name"], [k["name"] for k in passend or liste]))
    for k in neu:
        b.je_art[k["typ"]] += 1
        alt = nach_ars.get(k["ars"]) or zuordnung.get(k["ars"])
        if alt is None:
            o = {**k, "id": organisation_id(k["name"])}
            if o["id"] in dateien:  # gleicher Name schon bei einer anderen Art
                b.mehrdeutig.append((k["name"], ["Name schon vergeben"]))
                continue
            schreibe_organisation(daten, o, dateien)
            b.neu += 1
            continue
        namen = [alt["name"], *(alt.get("weitere_namen") or []), *(k.get("weitere_namen") or [])]
        weitere = list(
            dict.fromkeys(n for n in namen if org_schluessel(n) != org_schluessel(k["name"]))
        )
        ergebnis = {**alt, **k, "id": alt["id"]}
        ergebnis.pop("weitere_namen", None)
        if weitere:
            ergebnis["weitere_namen"] = weitere
        if alt.get("website"):
            ergebnis["website"] = alt["website"]
        if ergebnis == alt:
            b.unveraendert += 1
            continue
        b.ergaenzt += 1
        if alt["name"] != k["name"]:
            b.umbenannt.append((alt["name"], k["name"]))
        schreibe_organisation(daten, ergebnis, dateien)
    return b


def _arten() -> set[str]:
    return {a for v in _ZUSATZ.values() for a in v}
