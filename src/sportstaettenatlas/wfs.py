"""WFS-2.0-Client: Kacheln, serverseitiger Filter, Paging und fortsetzbarer Cache."""

from __future__ import annotations

import io
import logging
import math
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

import requests

from .quellen import WfsQuelle

if TYPE_CHECKING:  # Geo-Bibliotheken erst bei Bedarf laden
    import geopandas as gpd

log = logging.getLogger(__name__)

USER_AGENT = "sportstaettenatlas/0.1 (Forschungsprototyp)"
BBox = tuple[float, float, float, float]


def _urn(crs: str) -> str:
    return f"urn:ogc:def:crs:EPSG::{crs.split(':')[-1]}"


def kacheln(bbox: BBox, kachel_m: float) -> list[BBox]:
    """Zerlegt einen Ausschnitt in quadratische Kacheln (Randkacheln kleiner)."""
    xmin, ymin, xmax, ymax = bbox
    nx = max(1, math.ceil((xmax - xmin) / kachel_m))
    ny = max(1, math.ceil((ymax - ymin) / kachel_m))
    return [
        (
            xmin + i * kachel_m,
            ymin + j * kachel_m,
            min(xmin + (i + 1) * kachel_m, xmax),
            min(ymin + (j + 1) * kachel_m, ymax),
        )
        for i in range(nx)
        for j in range(ny)
    ]


def fes_filter(bbox: BBox, crs: str, feld: str | None, muster: Iterable[str]) -> str:
    """FES-2.0-Filter: BBOX UND (feld LIKE *m1* ODER feld LIKE *m2* ...).

    Bei gesetztem FILTER darf der KVP-Parameter BBOX nicht mitgeschickt werden,
    deshalb steckt der Ausschnitt im Filter selbst.
    """
    xmin, ymin, xmax, ymax = bbox
    box = (
        f'<fes:BBOX><gml:Envelope srsName="{_urn(crs)}">'
        f"<gml:lowerCorner>{xmin} {ymin}</gml:lowerCorner>"
        f"<gml:upperCorner>{xmax} {ymax}</gml:upperCorner>"
        f"</gml:Envelope></fes:BBOX>"
    )
    muster = [m for m in muster if m]
    if feld and muster:
        likes = "".join(
            '<fes:PropertyIsLike wildCard="*" singleChar="." escapeChar="!" matchCase="false">'
            f"<fes:ValueReference>{feld}</fes:ValueReference>"
            f"<fes:Literal>*{escape(m)}*</fes:Literal></fes:PropertyIsLike>"
            for m in muster
        )
        bedingung = likes if len(muster) == 1 else f"<fes:Or>{likes}</fes:Or>"
        inhalt = f"<fes:And>{box}{bedingung}</fes:And>"
    else:
        inhalt = box
    return (
        '<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0" '
        f'xmlns:gml="http://www.opengis.net/gml/3.2">{inhalt}</fes:Filter>'
    )


def getfeature_params(
    typename: str,
    bbox: BBox,
    crs: str,
    count: int,
    startindex: int,
    filter_xml: str | None = None,
) -> dict[str, str]:
    """Parameter für eine GetFeature-Anfrage (WFS 2.0, GML 3.2)."""
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": typename,
        "SRSNAME": _urn(crs),
        "COUNT": str(count),
        "STARTINDEX": str(startindex),
    }
    if filter_xml:
        params["FILTER"] = filter_xml
    else:
        xmin, ymin, xmax, ymax = bbox
        # EPSG:25832 hat Achsreihenfolge Ost/Nord, daher keine Vertauschung nötig
        params["BBOX"] = f"{xmin},{ymin},{xmax},{ymax},{_urn(crs)}"
    return params


class WfsFehler(RuntimeError):
    pass


def _anfrage(session: requests.Session, quelle: WfsQuelle, params: dict, versuche=4) -> bytes:
    for versuch in range(1, versuche + 1):
        try:
            # POST (formularkodiert), weil lange Filter die URL-Länge sprengen können
            resp = session.post(quelle.url, data=params, timeout=600)
            resp.raise_for_status()
            if b"ExceptionReport" in resp.content[:3000]:
                raise WfsFehler(resp.text[:800])
            return resp.content
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            if versuch == versuche:
                raise
            warte = 5 * 2 ** (versuch - 1)
            log.warning("Anfrage fehlgeschlagen (%s), neuer Versuch in %ss", exc, warte)
            time.sleep(warte)
    raise AssertionError("unerreichbar")


def _lese_gml(inhalt: bytes) -> gpd.GeoDataFrame | None:
    import geopandas as gpd

    if b'numberReturned="0"' in inhalt[:3000]:
        return None
    try:
        return gpd.read_file(io.BytesIO(inhalt))
    except Exception as exc:
        raise WfsFehler("GML-Antwort konnte nicht gelesen werden") from exc


def _seiten(
    session: requests.Session,
    quelle: WfsQuelle,
    typename: str,
    bbox: BBox,
    filter_xml: str | None,
) -> Iterator[gpd.GeoDataFrame]:
    start = 0
    while True:
        params = getfeature_params(
            typename, bbox, quelle.crs, quelle.seitengroesse, start, filter_xml
        )
        seite = _lese_gml(_anfrage(session, quelle, params))
        if seite is None or seite.empty:
            return
        yield seite
        if len(seite) < quelle.seitengroesse:
            return
        start += len(seite)


def _lade_kachel(session, quelle, typename, bbox, feld, muster) -> gpd.GeoDataFrame | None:
    import geopandas as gpd
    import pandas as pd

    filter_xml = fes_filter(bbox, quelle.crs, feld, muster) if feld else None
    try:
        seiten = list(_seiten(session, quelle, typename, bbox, filter_xml))
    except WfsFehler as exc:
        if not filter_xml:
            raise
        log.warning("Server lehnt Filter ab (%s) – lade Kachel ungefiltert", str(exc)[:200])
        seiten = list(_seiten(session, quelle, typename, bbox, None))
    if not seiten:
        return None
    gdf = gpd.GeoDataFrame(pd.concat(seiten, ignore_index=True), crs=seiten[0].crs)
    return gdf if gdf.crs else gdf.set_crs(quelle.crs)


def lade(
    quelle: WfsQuelle,
    typename: str,
    bbox: BBox,
    ziel: Path,
    feld: str | None = None,
    muster: Iterable[str] = (),
    kachel_m: float = 10_000,
    neu: bool = False,
) -> gpd.GeoDataFrame:
    """Lädt einen Feature-Typ kachelweise und führt die Kacheln zu `ziel` (GeoPackage) zusammen.

    Jede Kachel wird einzeln unter `<ziel>_kacheln/` gespeichert. Ein abgebrochener
    Lauf setzt beim nächsten Aufruf dort fort, wo er aufgehört hat.
    `feld`/`muster` schränken serverseitig ein (z. B. funktion LIKE *sport*); die
    endgültige Auswahl trifft danach das Regelwerk.
    """
    import geopandas as gpd
    import pandas as pd

    if ziel.exists() and not neu:
        log.info("Nutze Cache %s", ziel)
        return gpd.read_file(ziel)

    ordner = ziel.parent / f"{ziel.stem}_kacheln"
    ordner.mkdir(parents=True, exist_ok=True)
    liste = kacheln(bbox, kachel_m)
    muster = list(muster)
    teile = []

    from .hilfen import Fortschritt

    fb = Fortschritt(len(liste), f"ALKIS {typename}", "Kachel")
    with requests.Session() as s, fb:
        s.headers["User-Agent"] = USER_AGENT
        for nr, k in enumerate(liste, 1):
            fb.weiter()
            datei = ordner / f"{int(k[0])}_{int(k[1])}.gpkg"
            leer = datei.with_suffix(".leer")
            if not neu and leer.exists():
                continue
            if not neu and datei.exists():
                teile.append(gpd.read_file(datei))
                continue
            gdf = _lade_kachel(s, quelle, typename, k, feld, muster)
            if gdf is None or gdf.empty:
                leer.touch()
            else:
                gdf.to_file(datei, driver="GPKG")
                teile.append(gdf)
            log.debug(
                "%s Kachel %d/%d: %d Objekte",
                typename,
                nr,
                len(liste),
                0 if gdf is None else len(gdf),
            )

    if teile:
        gdf = gpd.GeoDataFrame(pd.concat(teile, ignore_index=True), crs=teile[0].crs)
    else:
        gdf = gpd.GeoDataFrame(geometry=[], crs=quelle.crs)
    # Objekte an Kachel- und Seitengrenzen kommen mehrfach vor
    if "oid" in gdf.columns:
        gdf = gdf.drop_duplicates(subset="oid")
    gdf.to_file(ziel, driver="GPKG")
    log.info("%s: %d Objekte gesamt", typename, len(gdf))
    return gdf
