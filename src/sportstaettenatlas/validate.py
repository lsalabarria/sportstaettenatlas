"""Prüfungen über das Datenmodell hinaus – Auffälligkeiten für results/regelverstoesse.csv.

Das Datenmodell (modell.py) prüft jeden Datensatz für sich: Pflichtfelder, Formate,
Auswahllisten, `braucht` und `teil_von`. Hier stehen Prüfungen, die mehr brauchen – das
Verzeichnis der Organisationen, die Verwaltungsgebiete, andere Sportstätten oder die Felder je
Anlagentyp. Alle laufen offline über den ganzen Bestand (wenige Sekunden) und melden nur; sie
ändern nichts an den Daten.

- Organisation: Betreiber und Eigentümer stehen im Verzeichnis der Organisationen
- Ort: die Gemeinde an der Koordinate (VG250) passt zu `adresse.ort`
- Rheinland-Pfalz: die Koordinate liegt in einer Gemeinde des Landes
- Doppelung: keine zwei Sportstätten mit ähnlichem Namen näher als 60 m (Regel wie im Formular)
- Sanierung: die letzte Sanierung liegt nicht vor dem Baujahr
- Anlagentyp: kein Feld befüllt, das nicht zum Typ der Sportanlage passt (modell.MERKMALE)
- Sportarten: die Sportarten einer Anlage stehen auch bei ihrer Sportstätte

Ergebnis: Liste (Datei, Meldung); die Meldung beginnt wie die des Modells mit dem Feld.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from . import modell
from .bestand import _laender, _staetten_ordner, org_schluessel, org_verzeichnis
from .gebiete import Zuordnung

NAH_M = 60  # Doppelung: höchstens so weit auseinander …
AEHNLICH = 0.8  # … und mindestens so ähnliche Namen (wie im Formular, vorschlag.js)
ROLLEN = ("betreiber", "eigentuemer")


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


def organisationen_bekannt(st: dict, verzeichnis: dict) -> Iterable[str]:
    for rolle in ROLLEN:
        name = st.get(rolle)
        if isinstance(name, str) and name.strip() and org_schluessel(name) not in verzeichnis:
            yield f"{rolle}: „{name}“ steht nicht im Verzeichnis der Organisationen"


def ort_und_land(st: dict, gemeinde_von, gemeinde_name: dict) -> Iterable[str]:
    lage = _lage(st)
    if lage is None:
        return
    ars = gemeinde_von(lage[1], lage[0])
    if ars is None:
        yield "lage: liegt in keiner Gemeinde von Rheinland-Pfalz"
        return
    ort = (st.get("adresse") or {}).get("ort")
    gemeinde = gemeinde_name.get(ars, "")
    if ort and gemeinde and not ort_passt(ort, gemeinde):
        yield f"adresse.ort: „{ort}“, die Koordinate liegt aber in {gemeinde}"


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


# --- alles zusammen -------------------------------------------------------------------------


def pruefe(
    bestand: list[dict],
    organisationen: list[dict],
    gemeinden: dict | None,
    daten: Path,
) -> list[tuple[str, str]]:
    """Alle Prüfungen über den Bestand. `gemeinden`: GeoJSON der Gemeinden (gebiete.lade(…)
    ["gemeinde"]); ohne entfallen Ort und Rheinland-Pfalz."""
    ordner = {k: v for land in _laender(daten) for k, v in _staetten_ordner(land).items()}

    def datei(st: dict, anlage: dict | None = None) -> str:
        o = ordner.get(st.get("id"), Path(daten) / "?" / str(st.get("id")))
        return str(o / (f"{anlage.get('id')}.json" if anlage else f"{o.name}_meta.json"))

    verzeichnis = org_verzeichnis(organisationen)
    bekannte_typen = {t for typen, _ in modell.MERKMALE for t in typen}
    if gemeinden:
        gemeinde_von = Zuordnung(gemeinden).ars
        gemeinde_name = {
            str(f["properties"]["ars"]): f["properties"].get("name", "")
            for f in gemeinden.get("features", [])
            if (f.get("properties") or {}).get("ars")
        }
    out: list[tuple[str, str]] = []
    for st in bestand:
        meldungen = [*organisationen_bekannt(st, verzeichnis), *sanierung(st)]
        if gemeinden:
            meldungen += ort_und_land(st, gemeinde_von, gemeinde_name)
        out += [(datei(st), m) for m in meldungen]
        for a in st.get("anlagen") or []:
            meldungen = [
                *sanierung(a),
                *felder_zum_typ(a, bekannte_typen),
                *sportarten_der_anlage(a, st),
            ]
            out += [(datei(st, a), m) for m in meldungen]
    for a, b, d in doppelungen(bestand):
        for x, y in ((a, b), (b, a)):
            kat = y.get("kategorie") or "ohne Kategorie"
            text = f"„{y.get('name')}“ ({kat}, {y.get('id')}), {d:.0f} m entfernt"
            out.append((datei(x), f"name: ähnlich wie {text} – Doppelung?"))
    return out
