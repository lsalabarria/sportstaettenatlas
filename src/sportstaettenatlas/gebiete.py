"""Verwaltungsgebiete (Kreise, Verbandsgemeinden, Gemeinden) für die Gebietsauswahl der Karte.

Quelle: Verwaltungsgebiete 1:250 000 (VG250) des BKG, Stand 01.01., über den offenen
WFS https://sgx.geodatenzentrum.de/wfs_vg250 – Lizenz dl-de/by-2-0. Einmal geladen und
unter results/cache/ abgelegt. Alternativ eine heruntergeladene VG250-GeoPackage-Datei.

Der Amtliche Regionalschlüssel (ARS, 12 Stellen) ist hierarchisch:
    Land (2) · Regierungsbezirk (1) · Kreis (2) · Verbandsgemeinde (4) · Gemeinde (3)
Jede Sportstätte bekommt den ARS ihrer Gemeinde; für Kreis oder Verbandsgemeinde genügt
dann der Vergleich des Anfangs (07137 = Landkreis Mayen-Koblenz).

Nur das Laden braucht geopandas; Zuordnung und Ausgabe arbeiten mit GeoJSON und sind
ohne Geo-Bibliotheken testbar.
"""

from __future__ import annotations

import io
import json
import logging
import re
from collections import defaultdict
from pathlib import Path

log = logging.getLogger(__name__)

BKG_WFS = "https://sgx.geodatenzentrum.de/wfs_vg250"
QUELLENVERMERK = "© BKG ({jahr}) dl-de/by-2-0 (Verwaltungsgebiete VG250)"
# unsere Ebene → Kürzel der VG250-Ebene
EBENEN = {"kreis": "krs", "vg": "vwg", "gemeinde": "gem"}
EBENEN_TEXT = {"kreis": "Kreise", "vg": "Verbandsgemeinden", "gemeinde": "Gemeinden"}
STELLEN = {"kreis": 5, "vg": 9, "gemeinde": 12}
LAENDER = {"rp": "07"}  # Länderkürzel → Landesschlüssel
# Rechteck zum Abfragen (EPSG:25832), etwas größer als das Land
AUSSCHNITT = {"rp": (285_000, 5_420_000, 470_000, 5_650_000)}


def schluessel(ebene: str, ars: str) -> str:
    """Kurzschlüssel einer Ebene: so viele Stellen des ARS, wie die Ebene festlegt."""
    return str(ars)[: STELLEN[ebene]]


# --- Laden (braucht geopandas) ---------------------------------------------------------


def _aufbereiten(gdf, land: str, vereinfachen_m: float = 20) -> dict:
    """VG250-Ebene → GeoJSON (WGS84) mit ars, name, bez – nur Flächen des Landes."""
    import shapely

    gdf = gdf.rename(columns={c: c.upper() for c in gdf.columns if c != gdf.geometry.name})
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:25832")
    gdf = gdf[gdf["ARS"].astype(str).str.startswith(LAENDER[land])]
    if "GF" in gdf:  # 4 = Landflächen (2 = Gewässer, z. B. Bodensee) – sonst doppelt
        gf = gdf["GF"].astype(int)
        if (gf == 4).any():
            gdf = gdf[gf == 4]
    gdf = gdf.to_crs("EPSG:25832")
    gdf = gdf.dissolve(by="ARS", aggfunc={"GEN": "first", "BEZ": "first"}).reset_index()
    gdf = gdf.set_geometry(gdf.geometry.simplify(vereinfachen_m, preserve_topology=True))
    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf.set_geometry(shapely.set_precision(gdf.geometry.values, 1e-5))
    out = gdf[["ARS", "GEN", "BEZ", gdf.geometry.name]].rename(
        columns={"ARS": "ars", "GEN": "name", "BEZ": "bez"}
    )
    return json.loads(out.to_json(drop_id=True, na="null"))


def _typnamen(session, url: str) -> dict[str, str]:
    r = session.get(
        url,
        params={"SERVICE": "WFS", "REQUEST": "GetCapabilities", "VERSION": "2.0.0"},
        timeout=60,
    )
    r.raise_for_status()
    namen = re.findall(r"<(?:wfs:)?Name>\s*([^<\s]+)\s*</(?:wfs:)?Name>", r.text)
    out = {}
    for ebene, kurz in EBENEN.items():
        passend = [n for n in namen if re.search(rf"(^|:)vg250_{kurz}$", n)]
        if not passend:
            raise RuntimeError(f"{url}: Ebene vg250_{kurz} nicht in den Capabilities")
        out[ebene] = passend[0]
    return out


def _hole_ebene(session, url: str, typ: str, land: str, seite: int = 1000):
    import geopandas as gpd
    import pandas as pd

    xmin, ymin, xmax, ymax = AUSSCHNITT[land]
    teile, start, json_geht = [], 0, True
    while True:
        params = {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetFeature",
            "TYPENAMES": typ,
            "SRSNAME": "urn:ogc:def:crs:EPSG::25832",
            "BBOX": f"{xmin},{ymin},{xmax},{ymax},urn:ogc:def:crs:EPSG::25832",
            "COUNT": seite,
            "STARTINDEX": start,
        }
        if json_geht:
            params["OUTPUTFORMAT"] = "application/json"
        r = session.get(url, params=params, timeout=300)
        inhalt = r.content
        if json_geht and (not r.ok or b"ExceptionReport" in inhalt[:2000]):
            json_geht = False  # Dienst kann kein JSON → GML
            continue
        r.raise_for_status()
        if inhalt.lstrip()[:1] == b"{":
            fc = json.loads(inhalt)
            teil = gpd.GeoDataFrame.from_features(fc.get("features", []), crs="EPSG:25832")
        else:
            teil = gpd.read_file(io.BytesIO(inhalt))
        teile.append(teil)
        if len(teil) < seite:
            break
        start += seite
    return gpd.GeoDataFrame(pd.concat(teile, ignore_index=True), crs=teile[0].crs)


def lade(land: str, cache: Path, quelle: str | Path | None = None) -> dict[str, dict]:
    """Ebenen als {ebene: GeoJSON}. `quelle`: VG250-GeoPackage statt WFS. Mit Cache."""
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    import geopandas as gpd

    out = {}
    if quelle:
        import pyogrio

        layer = [n for n, _ in pyogrio.list_layers(quelle)]
        for ebene, kurz in EBENEN.items():
            name = next((n for n in layer if n.lower().endswith(f"vg250_{kurz}")), None)
            if name is None:
                raise SystemExit(f"{quelle}: Ebene vg250_{kurz} fehlt (VG250-GeoPackage?)")
            out[ebene] = _aufbereiten(gpd.read_file(quelle, layer=name), land)
    else:
        import requests

        from .http import USER_AGENT

        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        for ebene, typ in _typnamen(s, BKG_WFS).items():
            log.info("Verwaltungsgebiete: lade %s (%s)", ebene, typ)
            out[ebene] = _aufbereiten(_hole_ebene(s, BKG_WFS, typ, land), land)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


# --- Zuordnung und Ausgabe (ohne Geo-Bibliotheken) --------------------------------------


def _ringe(geom: dict) -> list[list[list[list[float]]]]:
    """Polygon/MultiPolygon → Liste von Polygonen (je Liste von Ringen)."""
    if not geom:
        return []
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return list(geom["coordinates"])
    return []


def _bbox(geom: dict) -> tuple[float, float, float, float]:
    xs = [p[0] for poly in _ringe(geom) for p in poly[0]]
    ys = [p[1] for poly in _ringe(geom) for p in poly[0]]
    return (min(xs), min(ys), max(xs), max(ys))


def _im_ring(x: float, y: float, ring) -> bool:
    drin, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            drin = not drin
        j = i
    return drin


def punkt_in(x: float, y: float, geom: dict) -> bool:
    for poly in _ringe(geom):
        if poly and _im_ring(x, y, poly[0]) and not any(_im_ring(x, y, loch) for loch in poly[1:]):
            return True
    return False


class Zuordnung:
    """Findet zu einem Punkt (lon, lat) den ARS der Gemeinde – mit Gitter als Vorfilter."""

    ZELLE = 0.05  # Grad, etwa 4–5 km

    def __init__(self, gemeinden: dict):
        self.flaechen = []
        self.gitter: dict[tuple[int, int], list[int]] = defaultdict(list)
        for f in gemeinden.get("features", []):
            g, ars = f.get("geometry"), (f.get("properties") or {}).get("ars")
            if not g or not ars or not _ringe(g):
                continue
            w, s, o, n = _bbox(g)
            i = len(self.flaechen)
            self.flaechen.append((str(ars), (w, s, o, n), g))
            for gx in range(int(w // self.ZELLE), int(o // self.ZELLE) + 1):
                for gy in range(int(s // self.ZELLE), int(n // self.ZELLE) + 1):
                    self.gitter[(gx, gy)].append(i)

    def ars(self, lon, lat) -> str | None:
        if lon is None or lat is None:
            return None
        try:
            x, y = float(lon), float(lat)
        except (TypeError, ValueError):
            return None
        for i in self.gitter.get((int(x // self.ZELLE), int(y // self.ZELLE)), ()):
            ars, (w, s, o, n), g = self.flaechen[i]
            if w <= x <= o and s <= y <= n and punkt_in(x, y, g):
                return ars
        return None


def index(gebiete: dict[str, dict]) -> list[dict]:
    """Kleine Liste für die Auswahl: Schlüssel, Ebene, Name, Bezeichnung, Ausdehnung."""
    out = []
    for ebene in EBENEN:
        for f in gebiete.get(ebene, {}).get("features", []):
            p, g = f.get("properties") or {}, f.get("geometry")
            if not p.get("ars") or not g or not _ringe(g):
                continue
            w, s, o, n = _bbox(g)
            out.append(
                {
                    "s": schluessel(ebene, p["ars"]),
                    "e": ebene,
                    "n": p.get("name") or "",
                    "b": p.get("bez") or "",
                    "bb": [round(w, 4), round(s, 4), round(o, 4), round(n, 4)],
                }
            )
    out.sort(key=lambda e: (list(EBENEN).index(e["e"]), e["n"]))
    return out


def umrisse(gebiete: dict[str, dict], ebene: str) -> dict:
    """Umrisse einer Ebene für die Karte, nur mit dem Schlüssel als Eigenschaft."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"s": schluessel(ebene, f["properties"]["ars"])},
                "geometry": f["geometry"],
            }
            for f in gebiete.get(ebene, {}).get("features", [])
            if (f.get("properties") or {}).get("ars") and f.get("geometry")
        ],
    }
