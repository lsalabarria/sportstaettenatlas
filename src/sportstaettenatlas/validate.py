"""Prüfungen über das Datenmodell hinaus – Auffälligkeiten für results/regelverstoesse.csv.

Das Datenmodell (modell.py) prüft jeden Datensatz für sich: Pflichtfelder, Formate,
Auswahllisten, Nachkommastellen, `braucht` und `teil_von`. Hier stehen Prüfungen, die mehr
brauchen – das Verzeichnis der Organisationen, die Verwaltungsgebiete, andere Sportstätten oder
die Felder je Anlagentyp. Alle laufen offline über den ganzen Bestand (wenige Sekunden) und
melden nur; sie ändern nichts an den Daten. Die Liste der Prüfungen steht in README.md
(„Prüfungen“).

Ergebnis: Liste (Datei, Meldung); die Meldung beginnt wie die des Modells mit dem Feld.
"""

from __future__ import annotations

import itertools
import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from . import modell
from .bestand import (
    _laender,
    _staetten_ordner,
    falsch_einsortiert,
    komplex_dateien,
    komplex_kreis,
    kreis_ordner,
    lies_sportkomplexe,
    org_dateien,
    org_schluessel,
    org_verzeichnis,
)
from .gebiete import EBENEN, Zuordnung, _ringe, schluessel

NAH_M = 60  # Doppelung: höchstens so weit auseinander …
ORT_TOLERANZ_M = 250  # Ort: VG250 ist generalisiert (1:250 000) – Grenzen weichen so weit ab
AEHNLICH = 0.8  # … und mindestens so ähnliche Namen (wie im Formular, vorschlag.js)
ROLLEN = ("betreiber", "eigentuemer")
GLEICHE_LAGE_AB = 3  # so viele Sportstätten auf exakt einer Koordinate: wohl ein Ersatzwert
FLAECHE_ABWEICHUNG = 0.25  # Fläche gegenüber Länge × Breite: höchstens 25 % mehr oder weniger
GESCHLOSSEN = ("stillgelegt/geschlossen",)
KOMPLEX_AB = 2  # so viele Sportstätten braucht ein Sportkomplex mindestens
KOMPLEX_AUSDEHNUNG_M = 1000  # Sportstätten eines Komplexes höchstens so weit auseinander  # Betriebsstatus ohne Öffnungszeiten
# Postleitzahlen in Rheinland-Pfalz beginnen so (Ränder zu NRW, Hessen, Saarland, Baden)
PLZ_RLP = (
    "515",
    "534",
    "535",
    "536",
    "54",
    "55",
    "56",
    "575",
    "576",
    "655",
    "656",
    "664",
    "665",
    "668",
    "669",
    "67",
    "767",
    "768",
)
# eine Zahl am Ende der Straße, die keine Hausnummer ist („Bundesstraße 412“, „K 85“)
STRASSENNUMMER = re.compile(
    r"(bundes|landes|kreis|staats)stra(ss|ß)e\s*\d+$|\b[blk]\s*\d+$|geb(ä|ae)ude\s*\d+$",
    re.IGNORECASE,
)
# Arten, die mit „Stadt/Gemeinde“ (Ebene unbekannt) zusammenpassen
GEMEINDE_EBENEN = {
    "Stadt/Gemeinde",
    "Kreisfreie Stadt",
    "Verbandsgemeinde",
    "Verbandsfreie Gemeinde",
    "Verbandsangehörige Stadt",
    "Ortsgemeinde",
}
RECHTSFORM = re.compile(
    r"\b(e\s*v|g?gmbh|mbh|ggmbh|ag|kg|gbr)\b\.?", re.IGNORECASE
)  # zählt beim Vergleich nicht


# --- Hilfen ---------------------------------------------------------------------------------


def norm_name(s) -> str:
    """Wie normName in vorschlag.js: klein, Umlaute ausgeschrieben, nur a-z, 0-9, Leerzeichen."""
    t = str(s or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def aehnlich(a, b) -> float:
    """Wie aehnlich in vorschlag.js: Dice-Koeffizient der Buchstabenpaare (0 … 1)."""

    def paare(s):
        t = f" {norm_name(s)} "
        return Counter(t[i : i + 2] for i in range(len(t) - 1))

    if not norm_name(a) or not norm_name(b):
        return 0.0
    x, y = paare(a), paare(b)
    n = sum(x.values()) + sum(y.values())
    return 2 * sum((x & y).values()) / n if n else 0.0


def abstand_m(lat1, lon1, lat2, lon2) -> float:
    r = math.pi / 180
    h = (
        math.sin((lat2 - lat1) * r / 2) ** 2
        + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin((lon2 - lon1) * r / 2) ** 2
    )
    return 12_742_000 * math.asin(math.sqrt(h))


def _ort_kern(t: str) -> str:
    """„Koblenz, Stadt“, „Berg (Pfalz)“, „Stadt Daun“ → „koblenz“, „berg“, „daun“."""
    t = re.sub(r"\(.*?\)|,.*$", "", str(t or ""))
    return " ".join(
        w for w in norm_name(t).split() if w not in ("stadt", "gemeinde", "ortsgemeinde")
    )


def ort_passt(ort: str, gemeinde: str) -> bool:
    """Passt der Ort der Adresse zur Gemeinde an der Koordinate? Auch Ortsteile, die mit dem
    Gemeindenamen beginnen („Koblenz-Metternich“), und Gemeinden mit Zusatz zählen."""
    o, g = _ort_kern(ort), _ort_kern(gemeinde)
    if not o or not g:
        return True
    return o == g or o.split()[0] == g.split()[0] or g in o.split() or o in g.split()


def _lage(d: dict) -> tuple[float, float] | None:
    lage = d.get("lage") or {}
    try:
        return float(lage["lat"]), float(lage["lon"])
    except (KeyError, TypeError, ValueError):
        return None


def _liste(v) -> list:
    return v if isinstance(v, list) else [v] if v else []


# --- die Prüfungen --------------------------------------------------------------------------


def organisationen_der_staette(st: dict, verzeichnis: dict) -> Iterable[str]:
    """Betreiber, Eigentümer und Nutzer stehen im Verzeichnis; ihre Art an der Sportstätte
    widerspricht der im Verzeichnis nicht."""
    for rolle in (*ROLLEN, "nutzer"):
        for name in _liste(st.get(rolle)):
            if not isinstance(name, str) or not name.strip():
                continue
            o = verzeichnis.get(org_schluessel(name))
            if o is None:
                yield f"{rolle}: „{name}“ steht nicht im Verzeichnis der Organisationen"
                continue
            typ, im_verzeichnis = st.get(f"{rolle}_typ"), o.get("typ")
            if (
                typ
                and im_verzeichnis
                and typ != im_verzeichnis
                and not (
                    "Stadt/Gemeinde" in (typ, im_verzeichnis)
                    and {typ, im_verzeichnis} <= GEMEINDE_EBENEN
                )
            ):
                yield (
                    f"{rolle}_typ: „{typ}“, im Verzeichnis ist „{o['name']}“ aber "
                    f"„{im_verzeichnis}“"
                )


def abstand_zum_rand_m(lon: float, lat: float, geom: dict) -> float:
    """Kürzester Abstand eines Punkts zur Grenze einer Fläche, in Metern (genähert)."""
    k = math.cos(math.radians(lat))
    best = math.inf
    for polygon in _ringe(geom):
        for ring in polygon:
            for (ax, ay), (bx, by) in itertools.pairwise(ring):
                ax, bx, px = ax * k, bx * k, lon * k
                dx, dy = bx - ax, by - ay
                t = ((px - ax) * dx + (lat - ay) * dy) / (dx * dx + dy * dy or 1)
                t = min(1.0, max(0.0, t))
                best = min(best, math.hypot(px - ax - t * dx, lat - ay - t * dy))
    return best * 111_320


class Gebiete:
    """Verwaltungsgebiete aus VG250: Gemeinde an einem Punkt, Namen und Flächen je Schlüssel."""

    def __init__(self, gebiete: dict):
        self.von = Zuordnung(gebiete.get("gemeinde") or {}).ars
        self.name: dict[str, str] = {}  # Gemeinde-ARS → Name
        self.flaeche: dict[str, dict] = {}  # Schlüssel jeder Ebene (5, 9, 12 Stellen) → Fläche
        for ebene in EBENEN:
            for f in (gebiete.get(ebene) or {}).get("features", []):
                p = f.get("properties") or {}
                if p.get("ars"):
                    k = schluessel(ebene, p["ars"])
                    self.flaeche.setdefault(k, f.get("geometry"))
                    if ebene == "gemeinde":
                        self.name[k] = p.get("name", "")

    def abstand_zu(self, ort: str, lon: float, lat: float) -> float | None:
        """Abstand zur nächsten Gemeinde, deren Name zu `ort` passt; None, wenn keine passt."""
        ars = [a for a, n in self.name.items() if ort_passt(ort, n)]
        return min((abstand_zum_rand_m(lon, lat, self.flaeche[a]) for a in ars), default=None)


def _entfernung(m: float) -> str:
    return f"{m / 1000:.1f} km".replace(".", ",") if m >= 1000 else f"{m:.0f} m"


def ort_und_land(st: dict, gemeinden: Gebiete) -> Iterable[str]:
    lage = _lage(st)
    if lage is None:
        return
    lat, lon = lage
    ars = gemeinden.von(lon, lat)
    if ars is None:
        yield "lage: liegt in keiner Gemeinde von Rheinland-Pfalz"
        return
    ort = (st.get("adresse") or {}).get("ort")
    gemeinde = gemeinden.name.get(ars, "")
    if not ort or not gemeinde or ort_passt(ort, gemeinde):
        return
    d = gemeinden.abstand_zu(ort, lon, lat)
    if d is None:
        yield f"adresse.ort: „{ort}“ ist keine Gemeinde, die Koordinate liegt in {gemeinde}"
    elif d > ORT_TOLERANZ_M:
        yield (
            f"adresse.ort: „{ort}“, die Koordinate liegt aber in {gemeinde}, "
            f"{_entfernung(d)} außerhalb von {re.sub(r',.*$', '', ort).strip()}"
        )


def sanierung(d: dict) -> Iterable[str]:
    bau, san = d.get("baujahr"), d.get("letzte_sanierung")
    if isinstance(bau, int) and isinstance(san, int) and san < bau:
        yield f"letzte_sanierung: {san} liegt vor dem Baujahr {bau}"


def felder_zum_typ(a: dict, bekannte_typen: set[str]) -> Iterable[str]:
    typ = a.get("typ")
    if typ not in bekannte_typen:  # unbekannter Typ: alle Felder erlaubt (wie im Formular)
        return
    for feld, wert in a.items():
        if wert in (None, "", [], {}) or feld not in modell.Sportanlage.model_fields:
            continue
        fuer = modell.fuer_von(feld)
        if fuer and typ not in fuer:
            yield f"{feld}: ist befüllt, gehört aber nicht zum Typ „{typ}“"


def sportarten_der_anlage(a: dict, st: dict) -> Iterable[str]:
    bei_staette = {norm_name(s) for s in _liste(st.get("sportarten"))}
    fehlen = [s for s in _liste(a.get("sportarten")) if norm_name(s) not in bei_staette]
    if fehlen:
        yield f"sportarten: {', '.join(fehlen)} fehlt bei der Sportstätte"


def adresse(st: dict) -> Iterable[str]:
    a = st.get("adresse") or {}
    plz, strasse = str(a.get("plz") or ""), str(a.get("strasse") or "").strip()
    if plz and not plz.startswith(PLZ_RLP):
        yield f"adresse.plz: {plz} ist keine Postleitzahl in Rheinland-Pfalz"
    if a.get("hausnummer") and not strasse:
        yield "adresse.hausnummer: angegeben, aber keine Straße"
    if re.search(r"\s\d+\s*[a-z]?$", strasse, re.IGNORECASE) and not STRASSENNUMMER.search(strasse):
        yield f"adresse.strasse: „{strasse}“ – steht die Hausnummer in der Straße?"


def eigentum_der_kommune(st: dict, verzeichnis: dict, gebiete: Gebiete) -> Iterable[str]:
    """Eine Kommune als Eigentümer: die Sportstätte liegt in ihrem Gebiet (Verbandsgemeinde und
    Landkreis: im ganzen Gebiet) oder höchstens ORT_TOLERANZ_M davor."""
    o = (
        verzeichnis.get(org_schluessel(st.get("eigentuemer") or ""))
        if st.get("eigentuemer")
        else None
    )
    lage = _lage(st)
    if not o or not o.get("ars") or lage is None:
        return
    ars = gebiete.von(lage[1], lage[0])
    if ars is None or ars.startswith(o["ars"]):
        return
    flaeche = gebiete.flaeche.get(o["ars"])
    d = abstand_zum_rand_m(lage[1], lage[0], flaeche) if flaeche else None
    if d is None or d > ORT_TOLERANZ_M:
        wo = gebiete.name.get(ars, ars)
        weit = f", {_entfernung(d)} außerhalb" if d is not None else ""
        yield f"eigentuemer: „{o['name']}“, die Sportstätte liegt aber in {wo}{weit}"


def licht(a: dict) -> Iterable[str]:
    if a.get("flutlicht") == "nein":
        for feld in ("lux", "leuchtmittel"):
            if a.get(feld) not in (None, ""):
                yield f"{feld}: angegeben, aber Flutlicht „nein“"


def flaeche(a: dict) -> Iterable[str]:
    l, b, f = a.get("laenge"), a.get("breite"), a.get("flaeche")
    if all(isinstance(x, int | float) and x > 0 for x in (l, b, f)):
        soll = l * b
        if abs(f - soll) > FLAECHE_ABWEICHUNG * soll:
            yield f"flaeche: {f:g} m², Länge × Breite ergibt aber {soll:g} m²"


def geschlossen_mit_oeffnungszeiten(a: dict, st: dict) -> Iterable[str]:
    status = a.get("betriebsstatus") or st.get("betriebsstatus")
    if status in GESCHLOSSEN:
        for feld in ("oeffnungsstunden", "oeffnungsstunden_schule", "oeffnungsstunden_verein"):
            if a.get(feld):
                yield f"{feld}: angegeben, aber Betriebsstatus „{status}“"


def gleiche_lage(bestand: list[dict]) -> dict[str, int]:
    """Sportstätte → Zahl der Sportstätten auf genau ihrer Koordinate (ab GLEICHE_LAGE_AB)."""
    zahl = Counter(_lage(st) for st in bestand if _lage(st))
    return {
        st["id"]: zahl[_lage(st)] for st in bestand if zahl.get(_lage(st), 0) >= GLEICHE_LAGE_AB
    }


def _sportart_kern(s) -> str:
    return norm_name(s).replace(" ", "")  # „Beach-Volleyball“ = „Beachvolleyball“


def sportarten_schreibweisen(bestand: list[dict]) -> dict[str, tuple[str, int]]:
    """Seltenere Schreibweise einer Sportart → (häufigste Schreibweise, wie oft)."""
    zahl = Counter(
        s
        for st in bestand
        for x in [st, *(st.get("anlagen") or [])]
        for s in _liste(x.get("sportarten"))
        if isinstance(s, str)
    )
    gruppen: dict[str, list[str]] = defaultdict(list)
    for s in zahl:
        gruppen[_sportart_kern(s)].append(s)
    out = {}
    for namen in gruppen.values():
        if len(namen) > 1:
            haeufig = max(namen, key=lambda n: (zahl[n], n))
            out |= {n: (haeufig, zahl[haeufig]) for n in namen if n != haeufig}
    return out


def _org_kern(name) -> str:
    return norm_name(RECHTSFORM.sub(" ", str(name or "")))


def fast_gleiche_organisationen(organisationen: list[dict]) -> Iterable[tuple[dict, dict]]:
    """Paare mit sehr ähnlichem Namen (ohne Rechtsform wie „e.V.“). Gebietskörperschaften
    (mit Regionalschlüssel) werden nicht untereinander verglichen – ihre Namen sind amtlich."""
    ohne_ars = [o for o in organisationen if not o.get("ars")]
    for i, a in enumerate(ohne_ars):
        for b in [*ohne_ars[i + 1 :], *(o for o in organisationen if o.get("ars"))]:
            if aehnlich(_org_kern(a.get("name")), _org_kern(b.get("name"))) >= AEHNLICH:
                yield a, b


def doppelungen(bestand: list[dict]) -> Iterable[tuple[dict, dict, float]]:
    """Paare von Sportstätten mit ähnlichem Namen, die höchstens NAH_M auseinander liegen."""
    zelle = 0.001  # Grad, etwa 70–110 m: Nachbarn liegen in derselben oder einer Nachbarzelle
    gitter: dict[tuple[int, int], list[tuple[dict, float, float]]] = defaultdict(list)
    for st in bestand:
        if lage := _lage(st):
            gitter[(int(lage[0] // zelle), int(lage[1] // zelle))].append((st, *lage))
    for (gx, gy), hier in gitter.items():
        for dx in (0, 1):
            for dy in (-1, 0, 1) if dx else (0, 1):
                dort = hier if (dx, dy) == (0, 0) else gitter.get((gx + dx, gy + dy), [])
                for i, (a, la, oa) in enumerate(hier):
                    for b, lb, ob in dort[i + 1 :] if dort is hier else dort:
                        d = abstand_m(la, oa, lb, ob)
                        if d <= NAH_M and aehnlich(a.get("name"), b.get("name")) >= AEHNLICH:
                            yield a, b, d


def sportkomplexe(bestand: list[dict], komplexe: list[dict]) -> Iterable[tuple[str, str, str]]:
    """(id einer Sportstätte oder eines Komplexes, Prüfung, Meldung): Verweis auf einen
    Komplex, den es nicht gibt; Komplex mit zu wenigen Sportstätten; zu weit verstreut."""
    nach_id = {k["id"]: k for k in komplexe}
    mitglieder: dict[str, list[dict]] = defaultdict(list)
    for st in bestand:
        kid = st.get("sportkomplex")
        if not kid:
            continue
        if kid in nach_id:
            mitglieder[kid].append(st)
        else:
            yield st["id"], "Sportkomplex", f"sportkomplex: {kid} gibt es nicht"
    for k in komplexe:
        st = mitglieder.get(k["id"], [])
        if len(st) < KOMPLEX_AB:
            yield (
                k["id"],
                "Kleiner Sportkomplex",
                (
                    f"name: „{k.get('name')}“ hat {len(st)} Sportstätte{'n' if len(st) != 1 else ''}"
                    f" – ein Sportkomplex braucht mindestens {KOMPLEX_AB}"
                ),
            )
        lagen = [_lage(x) for x in st if _lage(x)]
        weit = max(
            (abstand_m(*a, *b) for a, b in itertools.combinations(lagen, 2)),
            default=0,
        )
        if weit > KOMPLEX_AUSDEHNUNG_M:
            yield (
                k["id"],
                "Ausdehnung des Sportkomplexes",
                (
                    f"lage: Sportstätten von „{k.get('name')}“ liegen bis zu {weit:.0f} m auseinander"
                ),
            )


# --- alles zusammen -------------------------------------------------------------------------


DATENMODELL = "Datenmodell"  # Prüfung der Meldungen aus modell.py (Pflichtfelder, Formate …)
# die Prüfungen dieser Datei, wie sie in der Spalte „pruefung“ und in README.md heißen
PRUEFUNGEN = (
    "Organisation",
    "Art der Organisation",
    "Eigentum der Kommune",
    "Ort",
    "Rheinland-Pfalz",
    "Kreis-Ordner",
    "Gleiche Koordinate",
    "Doppelung",
    "PLZ",
    "Straße und Hausnummer",
    "Sanierung",
    "Anlagentyp",
    "Sportarten",
    "Schreibweise der Sportarten",
    "Licht",
    "Fläche",
    "Betriebsstatus",
    "Organisation ohne Art",
    "Fast gleiche Organisationen",
    "Sportkomplex",
    "Kleiner Sportkomplex",
    "Ausdehnung des Sportkomplexes",
)


def pruefe(
    bestand: list[dict],
    organisationen: list[dict],
    gebiete: dict | None,
    daten: Path,
) -> list[tuple[str, str, str]]:
    """Alle Prüfungen über den Bestand → (Datei, Prüfung, Meldung); die Namen der Prüfungen
    sind die aus README.md. `gebiete`: Verwaltungsgebiete (gebiete.lade); ohne entfallen die
    Prüfungen, die sie brauchen (Ort, Land, Kreis-Ordner, Eigentum)."""
    ordner = {k: v for land in _laender(daten) for k, v in _staetten_ordner(land).items()}
    org_datei = {p.stem: str(p) for p in org_dateien(daten)}
    komplexe = lies_sportkomplexe(daten)
    komplex_datei = {p.stem: str(p) for p in komplex_dateien(daten)}
    komplex_name = {k["id"]: k.get("name") for k in komplexe}

    def datei(st: dict, anlage: dict | None = None) -> str:
        o = ordner.get(st.get("id"), Path(daten) / "?" / str(st.get("id")))
        return str(o / (f"{anlage.get('id')}.json" if anlage else f"{o.name}_meta.json"))

    verzeichnis = org_verzeichnis(organisationen)
    bekannte_typen = {t for typen, _ in modell.MERKMALE for t in typen}
    gebiete_ = Gebiete(gebiete) if gebiete else None
    gleich = gleiche_lage(bestand)
    komplexe_je_lage: dict[tuple, set] = defaultdict(set)  # Koordinate → Sportkomplexe dort
    for st in bestand:
        if st["id"] in gleich:
            komplexe_je_lage[_lage(st)].add(st.get("sportkomplex"))
    schreibweise = sportarten_schreibweisen(bestand)

    def sportarten(x: dict) -> Iterable[str]:
        for s in _liste(x.get("sportarten")):
            if s in schreibweise:
                haeufig, n = schreibweise[s]
                yield f"sportarten: „{s}“ – sonst meist „{haeufig}“ ({n}×)"

    def ort(st: dict) -> Iterable[tuple[str, str]]:  # Ort und Land aus einer Prüfung
        for m in ort_und_land(st, gebiete_):
            yield ("Rheinland-Pfalz" if m.startswith("lage:") else "Ort"), m

    out: list[tuple[str, str, str]] = []
    for st in bestand:
        meldungen: list[tuple[str, str]] = [
            *(
                ("Art der Organisation" if m.split(":")[0].endswith("_typ") else "Organisation", m)
                for m in organisationen_der_staette(st, verzeichnis)
            ),
            *(
                ("PLZ" if m.startswith("adresse.plz") else "Straße und Hausnummer", m)
                for m in adresse(st)
            ),
            *(("Sanierung", m) for m in sanierung(st)),
            *(("Schreibweise der Sportarten", m) for m in sportarten(st)),
        ]
        if st["id"] in gleich:
            n = gleich[st["id"]]
            dort = komplexe_je_lage[_lage(st)]
            if len(dort) == 1 and (kid := next(iter(dort))):
                m = (
                    f"lage: Koordinate teilen sich {n} Sportstätten des Sportkomplexes "
                    f"„{komplex_name.get(kid, kid)}“ – vermutlich seine Lage, bitte einzeln verorten"
                )
            else:
                m = f"lage: Koordinate teilen sich {n} Sportstätten – Ersatzwert?"
            meldungen.append(("Gleiche Koordinate", m))
        if gebiete_:
            meldungen += [
                *ort(st),
                *(
                    ("Eigentum der Kommune", m)
                    for m in eigentum_der_kommune(st, verzeichnis, gebiete_)
                ),
            ]
        out += [(datei(st), p, m) for p, m in meldungen]
        for a in st.get("anlagen") or []:
            meldungen = [
                *(("Sanierung", m) for m in sanierung(a)),
                *(("Anlagentyp", m) for m in felder_zum_typ(a, bekannte_typen)),
                *(("Sportarten", m) for m in sportarten_der_anlage(a, st)),
                *(("Schreibweise der Sportarten", m) for m in sportarten(a)),
                *(("Licht", m) for m in licht(a)),
                *(("Fläche", m) for m in flaeche(a)),
                *(("Betriebsstatus", m) for m in geschlossen_mit_oeffnungszeiten(a, st)),
            ]
            out += [(datei(st, a), p, m) for p, m in meldungen]
    for a, b, d in doppelungen(bestand):
        for x, y in ((a, b), (b, a)):
            kat = y.get("kategorie") or "ohne Kategorie"
            text = f"„{y.get('name')}“ ({kat}, {y.get('id')}), {d:.0f} m entfernt"
            out.append((datei(x), "Doppelung", f"name: ähnlich wie {text} – Doppelung?"))
    for i, pruefung, m in sportkomplexe(bestand, komplexe):
        ziel = komplex_datei.get(i) or datei({"id": i})
        out.append((ziel, pruefung, m))
    if gebiete and gebiete.get("kreis"):
        kreis_von = kreis_ordner(gebiete)
        for sid, ist, soll in falsch_einsortiert(bestand, kreis_von):
            m = f"lage: liegt im Kreis {soll}, die Datei aber unter {ist} (einordnen)"
            out.append((str(ordner.get(sid, sid)), "Kreis-Ordner", m))
        for k in komplexe:
            if (soll := komplex_kreis(k, bestand, kreis_von)) != k["_ordner"]:
                m = f"Sportkomplex gehört in den Kreis {soll}, die Datei liegt unter {k['_ordner']} (einordnen)"
                out.append((komplex_datei[k["id"]], "Kreis-Ordner", m))
    for o in organisationen:
        if not o.get("typ"):
            out.append(
                (
                    org_datei.get(o["id"], o["id"]),
                    "Organisation ohne Art",
                    "typ: Art der Organisation fehlt",
                )
            )
    for a, b in fast_gleiche_organisationen(organisationen):
        for x, y in ((a, b), (b, a)):
            m = f"name: fast gleich wie „{y['name']}“ ({y['id']}) – doppelt?"
            out.append((org_datei.get(x["id"], x["id"]), "Fast gleiche Organisationen", m))
    return out
