"""Dateien des ALKIS-Abgleichs für die Webseite (Reiter „Analysen“ → „ALKIS-Abgleich“).

`webdaten` liefert sie; `seite` schreibt sie nach docs/daten/analysen/alkis/.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    import geopandas as gpd

TITEL = "ALKIS-Abgleich"
DATEIEN = {  # Datei → Beschreibung auf der Download-Seite
    "sportstaetten.geojson": "ALKIS: Sportstätten (Standorte mit Umriss)",
    "sportanlagen.geojson": "ALKIS: Sportanlagen (Hallen, Spielfelder, Becken …)",
    "atlas_abgleich.geojson": "Einträge des Atlas ohne passende ALKIS-Fläche",
    "zusammenfassung.json": "Atlas-Einträge je Gemeinde: in ALKIS, in der Nähe, nicht in ALKIS",
}
# Status im Abgleich (abgleich.atlas_bericht) → Text auf der Karte
STATUS = {"zugeordnet": "in ALKIS", "nah": "in der Nähe", "nicht in ALKIS": "nicht in ALKIS"}
NUR_ATLAS = ("nicht in ALKIS", "nah")  # diese Einträge erscheinen als eigene Punkte
# Rohspalten des Bestands, die die Karte an ALKIS-Objekten noch braucht (Suche, Verweis);
# alle anderen alt_* stecken schon in den zusammengeführten Feldern
ALT_BEHALTEN = {"alt_bezug", "alt_name", "alt_adresse", "alt_typ", "alt_atlas_id", "alt_id"}
UEBERFLUESSIG = {"verifikation_sportstaette", "verifikation_anzahl"}
# Spalten des Abgleichs, die die Karte zu jedem Atlas-Punkt zeigt (Beschriftung: analysen.js)
ATLAS_SPALTEN = (
    "alt_name",
    "alt_typ",
    "alt_anlagentypen",
    "alt_adresse",
    "naechste_sportstaette_id",
    "abstand_m",
    "alkis_typgruppen",
    "typ_passt",
    "alt_betriebsstatus",
    "alt_datei",
    "alt_atlas_id",
    "alt_id",
)


def geojson(gdf: gpd.GeoDataFrame, praezision: float = 1e-6, vereinfachen_m: float = 0) -> dict:
    """GeoDataFrame → GeoJSON-Dict in WGS84 mit gerundeten Koordinaten.

    `vereinfachen_m`: Umrisse vorher um bis zu so viele Meter glätten (nur bei metrischem
    Koordinatensystem, z. B. EPSG:25832) – spart bei der Webseite viel Datenmenge.
    """
    import pandas as pd
    import shapely

    if gdf.empty:
        return {"type": "FeatureCollection", "features": []}
    if vereinfachen_m and gdf.crs is not None and gdf.crs.is_projected:
        gdf = gdf.set_geometry(gdf.geometry.simplify(vereinfachen_m, preserve_topology=True))
    g = gdf.to_crs("EPSG:4326")
    g = g.set_geometry(shapely.set_precision(g.geometry.values, praezision))
    # Datums-/Zeitspalten (z. B. alkis_stand) als lesbaren Text ausgeben
    for spalte in g.columns:
        if spalte != g.geometry.name and pd.api.types.is_datetime64_any_dtype(g[spalte]):
            g[spalte] = g[spalte].dt.strftime("%Y-%m-%d")
    # default=str fängt übrige Sondertypen ab (einzelne Timestamps, Decimal …)
    fc = json.loads(g.to_json(drop_id=True, na="null", default=str))
    for f in fc["features"]:  # leere und doppelte Angaben weglassen (spart rund ein Drittel)
        f["properties"] = {
            k: v
            for k, v in f["properties"].items()
            if v not in (None, "")
            and k not in UEBERFLUESSIG
            and (not k.startswith("alt_") or k in ALT_BEHALTEN)
        }
    return fc


def _zeilen(bericht):
    """Zeilen des Abgleichs mit Koordinate (DataFrame aus atlas_bericht bzw. der CSV)."""
    import pandas as pd

    if bericht is None or len(bericht) == 0 or "status" not in bericht:
        return []
    return [
        r for _, r in bericht.iterrows() if not pd.isna(r.get("lon")) and not pd.isna(r.get("lat"))
    ]


def atlas_geojson(bericht) -> dict:
    """Atlas-Einträge ohne passende ALKIS-Fläche als GeoJSON-Punkte (ohne Geo-Bibliotheken)."""
    import pandas as pd

    features = []
    for r in _zeilen(bericht):
        if r["status"] not in NUR_ATLAS:
            continue
        props = {"status": r["status"]}
        for k in ATLAS_SPALTEN:
            v = r.get(k)
            if not pd.isna(v) and v != "":
                props[k] = v.item() if hasattr(v, "item") else v
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def zusammenfassung(bericht, ars_von: Callable | None = None) -> dict | None:
    """Wie viele Atlas-Einträge je Gemeinde in ALKIS stehen, in der Nähe oder fehlen."""
    zeilen = _zeilen(bericht)
    if not zeilen:
        return None
    status = list(STATUS)
    je_gemeinde: dict[str, list[int]] = {}
    ohne = [0] * len(status)
    for r in zeilen:
        if r["status"] not in STATUS:
            continue
        ars = ars_von(r["lon"], r["lat"]) if ars_von else None
        zaehler = je_gemeinde.setdefault(ars, [0] * len(status)) if ars else ohne
        zaehler[status.index(r["status"])] += 1
    return {"status": list(STATUS.values()), "je_gemeinde": je_gemeinde, "ohne_gemeinde": ohne}


def _ars_setzen(fc: dict, ars_von: Callable, erben: dict | None = None) -> None:
    """Jedem Objekt den Regionalschlüssel seiner Gemeinde geben (Punkt bzw. lon/lat)."""
    for f in fc["features"]:
        p = f["properties"]
        ars = (erben or {}).get(p.get("sportstaette_id"))
        if ars is None:
            g = f.get("geometry") or {}
            lon, lat = (
                g["coordinates"][:2] if g.get("type") == "Point" else (p.get("lon"), p.get("lat"))
            )
            ars = ars_von(lon, lat)
        if ars:
            p["ars"] = ars


def webdaten(staetten, anlagen, bericht, ars_von: Callable | None = None) -> dict[str, dict]:
    """Die Dateien für die Webseite: {Dateiname: Inhalt} (siehe DATEIEN).

    `ars_von(lon, lat)` liefert den Regionalschlüssel der Gemeinde (gebiete.Zuordnung) –
    damit lassen sich die Objekte auf der Karte nach Kreis oder Gemeinde filtern.
    Sportanlagen erben den Schlüssel ihrer Sportstätte.
    """
    st = geojson(staetten, praezision=1e-5, vereinfachen_m=1.0)
    an = geojson(anlagen, praezision=1e-5, vereinfachen_m=1.0)
    atlas = atlas_geojson(bericht)
    if ars_von:
        _ars_setzen(st, ars_von)
        erben = {
            f["properties"].get("sportstaette_id"): f["properties"].get("ars")
            for f in st["features"]
        }
        _ars_setzen(an, ars_von, erben)
        _ars_setzen(atlas, ars_von)
    dateien = {
        "sportstaetten.geojson": st,
        "sportanlagen.geojson": an,
        "atlas_abgleich.geojson": atlas,
    }
    if (z := zusammenfassung(bericht, ars_von)) is not None:
        dateien["zusammenfassung.json"] = z
    return dateien
