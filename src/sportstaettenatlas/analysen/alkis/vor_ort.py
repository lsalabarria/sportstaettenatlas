"""Was führt ALKIS dort, wo nur der Atlas eine Sportstätte kennt?

Der ALKIS-Download für den Abgleich ist vorgefiltert (Sportflächen, Sportgebäude). Für
Einträge ohne ALKIS-Sportstätte fragt dieses Modul den WFS an genau der Stelle ohne Filter
ab: die Nutzung der Fläche, in der der Punkt liegt, und die Gebäude im Umkreis von 25 m.
So sieht man z. B., dass eine Reitsportstätte im Kataster als Landwirtschaft geführt wird
oder dass ein Punkt auf einem Acker statt beim Hallenbad liegt.

Ergebnis je Ort in results/cache/alkis_vor_ort.json (Schlüssel: Dienst, Koordinate auf
0,1 m, Radius); ein zweiter Lauf fragt bekannte Orte nicht mehr an. Fehlgeschlagene
Abfragen werden nicht gespeichert und beim nächsten Lauf wiederholt.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import requests

from ...hilfen import ERGEBNISSE
from .quellen import WfsQuelle
from .wfs import WfsFehler, _lese_gml, getfeature_params

if TYPE_CHECKING:
    import geopandas as gpd

log = logging.getLogger(__name__)

RADIUS_M = 25  # Umkreis für Gebäude; Nutzung: Fläche, in der der Punkt liegt
SPEICHER = ERGEBNISSE / "cache" / "alkis_vor_ort.json"
SPALTEN = ("alkis_nutzung_vor_ort", "alkis_gebaeude_vor_ort")


def _lies(session, quelle: WfsQuelle, typename: str, bbox) -> gpd.GeoDataFrame | None:
    """Objekte im Ausschnitt; None = keine. Knappes Zeitlimit, damit ein hängender Server
    den Lauf nicht aufhält."""
    params = getfeature_params(typename, bbox, quelle.crs, 200, 0)
    for versuch in range(3):
        try:
            resp = session.post(quelle.url, data=params, timeout=(5, 30))
            resp.raise_for_status()
            if b"ExceptionReport" in resp.content[:3000]:
                raise WfsFehler(resp.text[:300])
            gdf = _lese_gml(resp.content)
            return None if gdf is None else gdf if gdf.crs else gdf.set_crs(quelle.crs)
        except (requests.RequestException, WfsFehler):
            if versuch == 2:
                raise
            time.sleep(2)
    return None


def _wert(zeile, *spalten) -> str | None:
    for s in spalten:
        v = zeile.get(s)
        if v is not None and str(v).strip() not in ("", "nan", "None"):
            return str(v).strip()
    return None


def beschreibe(punkt, nutzung, gebaeude, radius_m: float = RADIUS_M) -> dict:
    """Nutzung an der Stelle und Gebäude im Umkreis als lesbarer Text."""
    kein_gebaeude = f"kein Gebäude im Umkreis von {radius_m:.0f} m"
    erg = {"alkis_nutzung_vor_ort": None, "alkis_gebaeude_vor_ort": kein_gebaeude}
    if nutzung is not None and not nutzung.empty:
        drin = nutzung[nutzung.geometry.intersects(punkt)]
        if drin.empty:  # Punkt auf einer Grenze o. ä.: nächste Fläche
            drin = nutzung.iloc[[nutzung.geometry.distance(punkt).argmin()]]
        texte = []
        for _, z in drin.iterrows():
            t = _wert(z, "nutzart") or "?"
            if bez := _wert(z, "bez", "funktion"):
                t += f" ({bez})"
            if name := _wert(z, "name"):
                t += f" „{name}“"
            texte.append(t)
        erg["alkis_nutzung_vor_ort"] = "; ".join(dict.fromkeys(texte))
    if gebaeude is not None and not gebaeude.empty:
        abst = gebaeude.geometry.distance(punkt)
        nah = gebaeude[abst <= radius_m].assign(_d=abst).sort_values("_d")
        texte = []
        for _, z in nah.iterrows():
            f = _wert(z, "funktion", "gebnutzbez") or "Gebäude"
            name = _wert(z, "name")
            texte.append(f"{f}{f' „{name}“' if name else ''} ({z['_d']:.0f} m)")
        erg["alkis_gebaeude_vor_ort"] = "; ".join(dict.fromkeys(texte)) or kein_gebaeude
    return erg


def _schluessel(quelle: WfsQuelle, p, radius_m: float) -> str:
    return f"{quelle.url}|{p.x:.1f}|{p.y:.1f}|{radius_m:g}"


def _speichere(pfad: Path, speicher: dict) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(".tmp")
    tmp.write_text(json.dumps(speicher, ensure_ascii=False), "utf-8")
    tmp.replace(pfad)


def ergaenze(
    bericht,
    alt: gpd.GeoDataFrame,
    quelle: WfsQuelle,
    status: tuple[str, ...] = ("nicht in ALKIS", "nah"),
    radius_m: float = RADIUS_M,
    speicher_pfad: Path = SPEICHER,
):
    """Spalten alkis_nutzung_vor_ort / alkis_gebaeude_vor_ort für die Zeilen mit `status`."""
    from tqdm.auto import tqdm

    from ...hilfen import USER_AGENT

    speicher = json.loads(speicher_pfad.read_text("utf-8")) if speicher_pfad.exists() else {}
    bericht = bericht.copy()
    for s in SPALTEN:
        bericht[s] = None
    geom = alt.set_index("alt_id").geometry.to_crs(quelle.crs)
    zeilen = list(bericht.index[bericht["status"].isin(status)])
    neu = fehler = 0
    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        for i in tqdm(zeilen, desc="ALKIS vor Ort", unit="Ort", dynamic_ncols=True):
            p = geom.get(bericht.at[i, "alt_id"])
            if p is None:
                continue
            key = _schluessel(quelle, p, radius_m)
            if (werte := speicher.get(key)) is None:
                bbox = (p.x - radius_m, p.y - radius_m, p.x + radius_m, p.y + radius_m)
                try:
                    nutzung = _lies(session, quelle, quelle.typ_nutzung, bbox)
                    gebaeude = _lies(session, quelle, quelle.typ_gebaeude, bbox)
                except (requests.RequestException, WfsFehler) as exc:
                    log.warning("ALKIS vor Ort für %s: %s", bericht.at[i, "alt_id"], exc)
                    fehler += 1
                    continue
                werte = speicher[key] = beschreibe(p, nutzung, gebaeude, radius_m)
                neu += 1
                if neu % 50 == 0:  # Zwischenstand sichern, falls der Lauf abbricht
                    _speichere(speicher_pfad, speicher)
            for k, v in werte.items():
                bericht.at[i, k] = v
    if neu:
        _speichere(speicher_pfad, speicher)
    print(f"ALKIS vor Ort: {len(zeilen)} Orte, {neu} neu abgefragt, {fehler} fehlgeschlagen")
    return bericht
