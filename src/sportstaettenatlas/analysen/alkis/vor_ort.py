"""Was steht im Kataster an einer Stelle? (für Einträge, die nur im Altbestand stehen)

Der normale ALKIS-Download ist auf Sportflächen und Sportgebäude vorgefiltert. Für
Atlas-Einträge ohne ALKIS-Sportobjekt fragt dieses Modul den WFS an genau dieser Stelle
ohne Filter ab: Welche Nutzung hat die Fläche, welche Gebäude stehen dort? So sieht
man z. B., dass eine "Reitsportstätte" im Kataster als Landwirtschaft geführt wird.

Zwischenspeicher auf zwei Ebenen: die WFS-Antworten (data/cache/http) und das fertige
Ergebnis je Ort (data/cache/alkis_vor_ort.json, Schlüssel: Dienst, Koordinate auf 0,1 m,
Radius). Ein zweiter Lauf fragt bekannte Orte also gar nicht mehr an. Fehlgeschlagene
Abfragen werden nicht gespeichert und beim nächsten Lauf wiederholt.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from ...http import Profil
from .quellen import WfsQuelle
from .wfs import getfeature_params

if TYPE_CHECKING:
    import geopandas as gpd

    from ...http import Sitzung

log = logging.getLogger(__name__)

RADIUS_M = 25  # Umkreis für Gebäude; Nutzung: Fläche, in der der Punkt liegt


class AbfrageFehler(Exception):
    """WFS-Antwort unbrauchbar (HTTP-Fehler, ExceptionReport)."""


def ABFRAGE_PROFIL() -> Profil:
    """Je Anfrage: 5 s Verbindungsaufbau, 15 s ohne Daten, 3 Versuche mit höchstens 3 s
    Pause dazwischen, max. 60 s gesamt."""
    return Profil(timeout=(5, 15), versuche=3, max_pause=3, frist=time.monotonic() + 60)


def _lies(sitzung: Sitzung, quelle: WfsQuelle, typename: str, bbox) -> gpd.GeoDataFrame | None:
    """Objekte im Ausschnitt; None = Dienst hat geantwortet, aber nichts gefunden."""
    from .wfs import _lese_gml

    params = getfeature_params(typename, bbox, quelle.crs, 200, 0)
    # kleine Ausschnitte: knappes Zeitlimit, damit ein hängender Server den Lauf
    # nicht minutenlang aufhält (gescheiterte Orte werden beim nächsten Lauf wiederholt)
    a = sitzung.get(quelle.url, params, profil=ABFRAGE_PROFIL())
    if a.status != 200 or b"ExceptionReport" in a.inhalt[:3000]:
        raise AbfrageFehler(f"WFS {typename}: HTTP {a.status}")
    gdf = _lese_gml(a.inhalt)
    if gdf is not None and gdf.crs is None:
        gdf = gdf.set_crs(quelle.crs)
    return gdf


def _wert(zeile, *spalten) -> str | None:
    for s in spalten:
        v = zeile.get(s)
        if v is not None and str(v).strip() not in ("", "nan", "None"):
            return str(v).strip()
    return None


def beschreibe(
    punkt,
    nutzung: gpd.GeoDataFrame | None,
    gebaeude: gpd.GeoDataFrame | None,
    radius_m: float = RADIUS_M,
) -> dict:
    """Nutzung an der Stelle und Gebäude im Umkreis als lesbarer Text (rein räumlich)."""
    erg = {"alkis_nutzung_vor_ort": None, "alkis_gebaeude_vor_ort": None}
    if nutzung is not None and not nutzung.empty:
        drin = nutzung[nutzung.geometry.intersects(punkt)]
        if drin.empty:  # Punkt auf einer Grenze o. ä.: nächste Fläche
            drin = nutzung.iloc[[nutzung.geometry.distance(punkt).argmin()]]
        texte = []
        for _, z in drin.iterrows():
            art, bez, name = _wert(z, "nutzart"), _wert(z, "bez", "funktion"), _wert(z, "name")
            t = art or "?"
            if bez:
                t += f" ({bez})"
            if name:
                t += f" „{name}“"
            texte.append(t)
        erg["alkis_nutzung_vor_ort"] = "; ".join(dict.fromkeys(texte)) or None
    if gebaeude is None or gebaeude.empty:
        erg["alkis_gebaeude_vor_ort"] = f"kein Gebäude im Umkreis von {radius_m:.0f} m"
    else:
        abst = gebaeude.geometry.distance(punkt)
        nah = gebaeude[abst <= radius_m].assign(_d=abst[abst <= radius_m]).sort_values("_d")
        texte = []
        for _, z in nah.iterrows():
            f = _wert(z, "funktion") or _wert(z, "gebnutzbez") or "Gebäude"
            name = _wert(z, "name")
            texte.append(f"{f}{f' „{name}“' if name else ''} ({z['_d']:.0f} m)")
        erg["alkis_gebaeude_vor_ort"] = "; ".join(dict.fromkeys(texte)) or (
            f"kein Gebäude im Umkreis von {radius_m:.0f} m"
        )
    return erg


def _schluessel(quelle: WfsQuelle, p, radius_m: float) -> str:
    return f"{quelle.url}|{p.x:.1f}|{p.y:.1f}|{radius_m:g}"


def _lade_speicher(pfad: Path | None) -> dict:
    if pfad is None or not pfad.exists():
        return {}
    try:
        return json.loads(pfad.read_text("utf-8"))
    except (OSError, ValueError):
        log.warning("%s unlesbar, wird neu aufgebaut", pfad)
        return {}


def _schreibe_speicher(pfad: Path | None, speicher: dict) -> None:
    if pfad is None:
        return
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(".tmp")
    tmp.write_text(json.dumps(speicher, ensure_ascii=False), "utf-8")
    tmp.replace(pfad)


def _meldung(text: str) -> None:
    """Statuszeile, die laufende Fortschrittsbalken nicht zerreißt."""
    try:
        from tqdm.auto import tqdm

        tqdm.write(text)
    except ImportError:  # pragma: no cover
        print(text, flush=True)


def ergaenze(
    bericht,
    alt: gpd.GeoDataFrame,
    sitzung: Sitzung,
    quelle: WfsQuelle,
    status: tuple[str, ...] = ("nicht in ALKIS",),
    radius_m: float = RADIUS_M,
    speicher_pfad: Path | None = None,
):
    """Hängt alkis_nutzung_vor_ort / alkis_gebaeude_vor_ort an die Zeilen mit `status` an.

    `speicher_pfad`: JSON mit fertigen Ergebnissen je Ort (Standard: neben dem
    HTTP-Cache der Sitzung, data/cache/alkis_vor_ort.json).
    """
    from ...hilfen import Fortschritt

    if speicher_pfad is None and getattr(sitzung, "cache", None) is not None:
        speicher_pfad = Path(sitzung.cache).parent / "alkis_vor_ort.json"
    speicher = _lade_speicher(speicher_pfad)
    gespeichert = neu = fehler = 0

    bericht = bericht.copy()
    for spalte in ("alkis_nutzung_vor_ort", "alkis_gebaeude_vor_ort"):
        bericht[spalte] = None
    geom = alt.set_index("alt_id").geometry.to_crs(quelle.crs)
    zeilen = bericht.index[bericht["status"].isin(status)]
    punkte = [geom.get(bericht.at[i, "alt_id"]) for i in zeilen]
    vorhanden = sum(
        1 for p in punkte if p is not None and _schluessel(quelle, p, radius_m) in speicher
    )
    _meldung(
        f"ALKIS vor Ort: {len(zeilen)} Atlas-Einträge „{' / '.join(status)}“ – "
        f"{vorhanden} aus dem Zwischenspeicher, {len(zeilen) - vorhanden} werden abgefragt …"
    )
    with Fortschritt(len(zeilen), "ALKIS vor Ort", "Ort") as fb:
        for i in zeilen:
            p = geom.get(bericht.at[i, "alt_id"])
            if p is None:
                fb.weiter()
                continue
            key = _schluessel(quelle, p, radius_m)
            if (werte := speicher.get(key)) is not None:
                gespeichert += 1
            else:
                bbox = (p.x - radius_m, p.y - radius_m, p.x + radius_m, p.y + radius_m)
                try:
                    nutzung = _lies(sitzung, quelle, quelle.typ_nutzung, bbox)
                    gebaeude = _lies(sitzung, quelle, quelle.typ_gebaeude, bbox)
                except Exception as exc:  # noqa: BLE001 – einzelne Orte dürfen scheitern
                    log.warning("ALKIS vor Ort für %s: %s", bericht.at[i, "alt_id"], exc)
                    fehler += 1
                    fb.info(gespeichert=gespeichert, neu=neu, fehler=fehler)
                    fb.weiter()
                    continue
                werte = beschreibe(p, nutzung, gebaeude, radius_m)
                speicher[key] = werte
                neu += 1
                if neu % 50 == 0:  # Zwischenstand sichern, falls der Lauf abbricht
                    _schreibe_speicher(speicher_pfad, speicher)
            for k, v in werte.items():
                bericht.at[i, k] = v
            fb.info(gespeichert=gespeichert, neu=neu, fehler=fehler)
            fb.weiter()
    if neu:
        _schreibe_speicher(speicher_pfad, speicher)
    log.info(
        "ALKIS vor Ort: %s aus Zwischenspeicher, %s neu, %s fehlgeschlagen",
        gespeichert,
        neu,
        fehler,
    )
    return bericht
