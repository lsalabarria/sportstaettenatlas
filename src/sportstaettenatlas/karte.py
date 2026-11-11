"""Interaktive Karte (eine HTML-Datei, Leaflet) der Sportstätten und Sportanlagen."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import geopandas as gpd

FARBEN = {
    "halle": "#534AB7",
    "becken": "#185FA5",
    "spielfeld": "#3B6D11",
    "leichtathletik": "#993C1D",
    "eis": "#0F6E56",
    "spezial": "#854F0B",
    "sportgelegenheit": "#888780",
    "zubehoer": "#B4B2A9",
    "unbestimmt": "#5F5E5A",  # ALKIS-Sammelbegriff "Sportanlage"
}

# Kategorien des Atlas (Bestand): feste Reihenfolge der Farben, damit eine Kategorie
# immer dieselbe Farbe behält; die seltenen teilen sich Grau („weitere“).
KATEGORIE_FARBEN = {
    "Sportplatz": "#2a78d6",
    "Sporthalle": "#eb6834",
    "Tennissportstätte": "#1baf7a",
    "Öffentlicher Sport- und Bewegungsraum": "#eda100",
    "Reitsportstätte": "#e87ba4",
    "Schwimmsportstätte": "#008300",
    "Schießsportstätte": "#6250d6",
    "Fitnessstudio": "#e34948",
}
KATEGORIE_WEITERE = "#8a8984"

LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist"


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
    return json.loads(g.to_json(drop_id=True, na="null", default=str))


ATLAS_STATUS = ("nicht in ALKIS", "nah")  # was nur im Sportstättenatlas RLP steht

ATLAS_FELDER = {
    "alt_name": "Name",
    "alt_komplex": "Komplex",
    "alt_typ": "Typ",
    "alt_anlagentypen": "Anlagen",
    "alt_adresse": "Adresse",
    "alkis_nutzung_vor_ort": "ALKIS-Nutzung hier",
    "alkis_gebaeude_vor_ort": "ALKIS-Gebäude hier",
    "naechste_sportstaette_id": "nächste ALKIS-Sportstätte",
    "abstand_m": "Abstand m",
    "alkis_typgruppen": "ALKIS dort",
    "typ_passt": "Typ passt",
    "alt_betriebsstatus": "Betriebsstatus",
    "alt_datei": "Datei",
    "alt_atlas_id": "Atlas-ID",
    "alt_id": "Abgleich-ID",
}


def atlas_geojson(bericht) -> dict:
    """Einträge des Abgleichberichts, die nur im Altbestand stehen, als GeoJSON-Punkte.

    `bericht` ist der DataFrame aus altbestand.abgleich (oder die gelesene
    abgleich_altbestand.csv) mit Spalten lon/lat und status. Ohne Geo-Bibliotheken.
    """
    import pandas as pd

    if bericht is None or len(bericht) == 0 or "status" not in bericht:
        return {"type": "FeatureCollection", "features": []}
    teil = bericht[bericht["status"].isin(ATLAS_STATUS)]
    features = []
    for _, r in teil.iterrows():
        if pd.isna(r.get("lon")) or pd.isna(r.get("lat")):
            continue
        props = {"status": r["status"]}
        for k in ATLAS_FELDER:
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


def _einbetten(obj) -> str:
    # "</" darf in einem <script>-Block nicht vorkommen
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def html_seite(
    anlagen: dict | None,
    staetten: dict | None,
    titel: str,
    quellenvermerk: str,
    atlas: dict | None = None,
    webseite: bool = False,
    leaflet: str = LEAFLET,
) -> str:
    """Erzeugt die HTML-Seite. Reine Funktion – testbar ohne Geo-Bibliotheken.

    webseite=False: eine Datei mit eingebetteten ALKIS-Daten (lokal per Doppelklick zu
                    öffnen), nur Ansicht „Verifikation“.
    webseite=True:  Seite für GitHub Pages; lädt Kopfzeile/Links aus konfig.js und die
                    Daten aus daten/ nach: Bestand sofort, ALKIS erst in der Verifikation.
    """
    if webseite:
        # konfig.js wird auf GitHub von Hand bearbeitet: immer frisch laden, sonst zeigt der
        # Browser bis zu zehn Minuten (oder länger) den alten Stand aus dem Zwischenspeicher
        skript = (
            "<script>document.write('<script src=\"konfig.js?' + Date.now() + '\"><\\/script>');"
            "</script>\n"
            "<script>\nconst EINGEBETTET = null;"
        )
        laden = '<div id="laden"><span class="kreisel"></span><span>Sportstätten werden geladen …</span></div>'
    else:
        leer = {"type": "FeatureCollection", "features": []}
        skript = (
            "<script>\nconst EINGEBETTET = {\n"
            f'"sportanlagen.geojson": {_einbetten(anlagen)},\n'
            f'"sportstaetten.geojson": {_einbetten(staetten)},\n'
            f'"atlas_abgleich.geojson": {_einbetten(atlas or leer)}}};'
        )
        laden = ""
    return (
        _VORLAGE.replace("__TITEL__", html.escape(titel))
        .replace("__LADEN__", laden)
        .replace("__LEAFLET__", leaflet)
        .replace("__QUELLE_JSON__", _einbetten(quellenvermerk))
        .replace("__FARBEN__", _einbetten(FARBEN))
        .replace("__KATEGORIE_FARBEN__", _einbetten(KATEGORIE_FARBEN))
        .replace("__ATLAS_FELDER__", _einbetten(ATLAS_FELDER))
        .replace("__SKRIPT__", skript)  # zuletzt: Daten nie als Platzhalter lesen
    )


def schreibe_karte(
    anlagen: gpd.GeoDataFrame,
    staetten: gpd.GeoDataFrame,
    ziel: Path,
    titel: str = "Sportstättenatlas – Sportstätten und Sportanlagen aus ALKIS",
    quellenvermerk: str = "",
    abgleich_altbestand=None,
) -> Path:
    seite = html_seite(
        geojson(anlagen),
        geojson(staetten),
        titel,
        quellenvermerk,
        atlas_geojson(abgleich_altbestand),
    )
    ziel.write_text(seite, encoding="utf-8")
    return ziel


_VORLAGE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITEL__</title>
<link rel="stylesheet" href="__LEAFLET__/leaflet.css">
<style>
  html, body { height: 100%; margin: 0; }
  body { font: 13px/1.4 system-ui, sans-serif; display: flex; flex-direction: column; color: #222; }
  #bereich { position: relative; flex: 1; min-height: 0; }
  #karte { position: absolute; inset: 0; }
  #kopf { background: #fff; border-bottom: 3px solid #871D33; z-index: 1001; padding: 6px 14px 0; }
  #kopf .zeile { display: flex; align-items: center; gap: 6px 14px; flex-wrap: wrap; }
  #kopf h1 { font-size: 18px; margin: 0 auto 4px 0; font-weight: 700; }
  #links a { color: #333; text-decoration: none; font-size: 14px; margin-left: 14px; }
  #links a:hover { text-decoration: underline; }
  #links a.knopf { background: #871D33; color: #fff; padding: 5px 12px; border-radius: 6px; }
  #links a.knopf:hover { background: #6d1729; text-decoration: none; }
  #ansichten { display: flex; gap: 2px; margin-right: auto; }
  #ansichten button { font: inherit; font-size: 14px; border: 0; background: none; cursor: pointer;
    padding: 7px 12px 6px; border-bottom: 3px solid transparent; margin-bottom: -3px; color: #444; }
  #ansichten button:hover { color: #000; background: #f6f3f4; }
  #ansichten button[aria-selected="true"] { border-bottom-color: #871D33; color: #871D33;
    font-weight: 600; }
  #gebietwahl { display: flex; align-items: center; gap: 6px; padding: 3px 0 6px; }
  #gebietwahl select { font: inherit; padding: 3px 4px; max-width: 260px; border: 1px solid #bbb;
    border-radius: 4px; background: #fff; }
  #gebietwahl button { font: inherit; border: 1px solid #bbb; background: #f6f6f6; border-radius: 4px;
    cursor: pointer; padding: 2px 8px; }
  #laden { position: absolute; inset: 0; z-index: 1100; display: flex; align-items: center;
           justify-content: center; gap: 10px; background: rgba(255,255,255,.8);
           font-size: 15px; color: #333; text-align: center; padding: 20px; }
  #laden.fehler { color: #871D33; }
  #laden[hidden] { display: none; }
  .kreisel { width: 22px; height: 22px; border: 3px solid #ddd; border-top-color: #871D33;
             border-radius: 50%; animation: dreh 0.8s linear infinite; flex: none; }
  .fehler .kreisel { display: none; }
  @keyframes dreh { to { transform: rotate(360deg); } }
  .panel { background: #fff; padding: 8px 10px; border-radius: 6px;
           box-shadow: 0 1px 4px rgba(0,0,0,.25); max-width: 270px; }
  .panel h1 { font-size: 14px; margin: 0 0 6px; font-weight: 600; }
  .panel h2 { font-size: 12px; margin: 8px 0 4px; font-weight: 600; color: #444; }
  .panel label { display: flex; align-items: center; gap: 6px; cursor: pointer; }
  .panel .n { margin-left: auto; color: #666; font-variant-numeric: tabular-nums; padding-left: 6px; }
  .panel hr { border: 0; border-top: 1px solid #ddd; margin: 6px 0; }
  .filter { width: 260px; max-height: calc(100vh - 170px); overflow: auto; }
  .filter details { border-top: 1px solid #e3e3e3; padding: 4px 0; }
  .filter summary { cursor: pointer; font-weight: 600; color: #444; padding: 2px 0; }
  .filter .knoepfe { display: flex; gap: 8px; margin: 2px 0 4px; }
  .filter .knoepfe button, .chip button { font: inherit; font-size: 12px; border: 0; background: none;
    color: #185FA5; cursor: pointer; padding: 0; }
  .filter input[type=search] { width: 100%; box-sizing: border-box; padding: 3px 6px; font: inherit;
    border: 1px solid #bbb; border-radius: 4px; margin: 4px 0; }
  .sp-liste { max-height: 220px; overflow: auto; }
  .chip { background: #EEF2F7; border-radius: 4px; padding: 4px 6px; margin: 4px 0; }
  .swatch { width: 12px; height: 12px; border-radius: 50%; flex: none; }
  .art { display: inline-block; font-size: 11px; padding: 0 5px; border-radius: 4px;
         background: #EEF2F7; color: #333; margin-left: 4px; }
  .tip h3 { font-size: 13px; margin: 0 0 4px; }
  .tip h4 { font-size: 12px; margin: 8px 0 2px; color: #444; border-top: 1px solid #ddd;
            padding-top: 6px; }
  .meta { border-collapse: collapse; }
  .meta td { padding: 1px 6px 1px 0; vertical-align: top; }
  .meta td:first-child { color: #666; white-space: nowrap; }
  .q { color: #888; font-size: 11px; }
  .verif { display: inline-block; padding: 1px 6px; border-radius: 4px; font-weight: 600; }
  .stufe-0 { background: #F1EFE8; color: #444441; }
  .stufe-2 { background: #D3D1C7; color: #2C2C2A; }
  .schraffur { width: 16px; height: 16px; border-radius: 3px; flex: none;
               border: 1px solid #888; background-color: #B4B2A9; }
  .stufe-1 { background: #EAF3DE; color: #27500A; }
  .leaflet-tooltip { max-width: 420px; white-space: normal; }
  .leaflet-popup-content { margin: 10px 12px; font: 13px/1.4 system-ui, sans-serif;
                           user-select: text; max-height: 60vh; overflow: auto; }
  .pfeil { color: #854F0B; font-size: 22px; line-height: 22px; text-align: center;
           text-shadow: 0 0 2px #fff, 0 0 2px #fff; }
  .hinweis { color: #888; font-size: 11px; margin-top: 6px; }
  .koord { font-variant-numeric: tabular-nums; user-select: all; }
  .suche { width: 270px; }
  .suche form { display: flex; gap: 4px; }
  .suche input { flex: 1; min-width: 0; padding: 4px 6px; font: inherit;
                 border: 1px solid #bbb; border-radius: 4px; }
  .suche button { padding: 4px 8px; font: inherit; cursor: pointer; border: 1px solid #bbb;
                  border-radius: 4px; background: #f6f6f6; }
  .suche ul { list-style: none; margin: 6px 0 0; padding: 0; max-height: 45vh; overflow: auto; }
  .suche li { padding: 4px 4px; cursor: pointer; border-radius: 4px; }
  .suche li:hover, .suche li.aktiv { background: #EEF2F7; }
  .suche li small { display: block; color: #777; }
  .suche .gruppe { color: #888; font-size: 11px; padding: 6px 4px 2px; cursor: default; }
  .suche .gruppe:hover { background: none; }
  /* Liste und Übersicht liegen über der Karte */
  .seite { position: absolute; inset: 0; z-index: 1050; background: #fff; overflow: auto; }
  .seite[hidden] { display: none; }
  .inhalt { max-width: 1100px; margin: 0 auto; padding: 16px 20px 40px; font-size: 14px; }
  .inhalt h2 { font-size: 20px; margin: 4px 0 4px; }
  .inhalt h3 { font-size: 15px; margin: 26px 0 8px; }
  .unter { color: #666; margin: 0 0 14px; }
  .reiter { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin: 10px 0; }
  .reiter button { font: inherit; border: 1px solid #ccc; background: #fff; border-radius: 16px;
                   padding: 4px 12px; cursor: pointer; }
  .reiter button[aria-pressed="true"] { background: #871D33; border-color: #871D33; color: #fff; }
  .reiter input, .reiter select { font: inherit; padding: 4px 8px; border: 1px solid #bbb;
                                  border-radius: 4px; }
  .reiter input { min-width: 220px; }
  table.tabelle { border-collapse: collapse; width: 100%; }
  .tabelle th, .tabelle td { text-align: left; padding: 6px 10px 6px 0; border-bottom: 1px solid #e6e6e6;
                             vertical-align: top; }
  .tabelle th { color: #555; font-weight: 600; position: sticky; top: 0; background: #fff;
                cursor: pointer; user-select: none; white-space: nowrap; }
  .tabelle th.zahl, .tabelle td.zahl { text-align: right; font-variant-numeric: tabular-nums; }
  .tabelle tbody tr.zeile { cursor: pointer; }
  .tabelle tbody tr.zeile:hover { background: #f6f8fb; }
  .tabelle tr.offen td { background: #f6f8fb; }
  .tabelle tr.details td { background: #fbfbfb; padding: 4px 10px 10px 18px; }
  .tabelle .klein { color: #666; font-size: 13px; }
  .tabelle a { color: #185FA5; cursor: pointer; }
  .knopf2 { font: inherit; font-size: 13px; border: 1px solid #185FA5; color: #185FA5;
            background: #fff; border-radius: 4px; padding: 3px 10px; cursor: pointer; margin: 4px 0; }
  .kacheln { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px; }
  .kachel { border: 1px solid #e3e3e3; border-radius: 8px; padding: 12px 14px; }
  .kachel .label { color: #555; font-size: 13px; }
  .kachel .wert { font-size: 30px; font-weight: 600; font-variant-numeric: tabular-nums;
                  line-height: 1.2; }
  .kachel .zusatz { color: #666; font-size: 12px; }
  .spalten { display: grid; grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); gap: 0 36px; }
  table.balken { border-collapse: collapse; width: 100%; }
  .balken td { padding: 3px 0; vertical-align: middle; }
  .balken td.l { width: 42%; padding-right: 10px; }
  .balken td.w { width: 74px; text-align: right; font-variant-numeric: tabular-nums;
                 padding-left: 8px; color: #333; white-space: nowrap; }
  .balken .spur { height: 12px; }
  .balken .fuell { height: 12px; background: #2a78d6; border-radius: 0 4px 4px 0; min-width: 2px; }
  .balken tr:hover td { background: #f6f8fb; }
  .balken tr.klickbar { cursor: pointer; }
  /* Vorschlag */
  .vorschlag .raster { display: grid; grid-template-columns: minmax(0, 1fr) 400px; gap: 24px;
                       align-items: start; }
  @media (max-width: 900px) { .vorschlag .raster { grid-template-columns: 1fr; } }
  .vorschlag aside { position: sticky; top: 10px; }
  .vorschlag fieldset { border: 1px solid #e3e3e3; border-radius: 8px; margin: 0 0 14px;
                        padding: 10px 14px 12px; }
  .vorschlag legend { font-weight: 600; padding: 0 6px; color: #871D33; }
  .vorschlag .feld { display: flex; flex-direction: column; gap: 3px; margin: 6px 0; }
  .vorschlag .feld > span:first-child { color: #444; font-size: 13px; }
  .vorschlag .feld.klein input { max-width: 140px; }
  .vorschlag input:not([type=radio]):not([type=checkbox]), .vorschlag select,
  .vorschlag textarea { font: inherit; padding: 6px 8px; border: 1px solid #bbb; border-radius: 4px;
                        width: 100%; box-sizing: border-box; background: #fff; }
  .vorschlag input:focus, .vorschlag select:focus, .vorschlag textarea:focus {
    outline: 2px solid #185FA5; outline-offset: -1px; }
  .vorschlag .zwei { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
  .vorschlag .zwei.breit-links { grid-template-columns: 3fr 1fr; }
  .vorschlag .zwei.schmal-links { grid-template-columns: 1fr 3fr; }
  .vorschlag .radios { display: flex; gap: 6px 16px; flex-wrap: wrap; }
  .vorschlag .radios label { display: flex; gap: 5px; align-items: center; cursor: pointer; }
  .vorschlag .radios.gross { font-size: 15px; margin-bottom: 6px; }
  .vorschlag .zeile-feld { display: flex; gap: 14px; align-items: center; margin: 6px 0; flex-wrap: wrap; }
  .vorschlag .zeile-feld > span:first-child { color: #444; font-size: 13px; min-width: 150px; }
  .vorschlag .lage { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; }
  .vorschlag .lage .hinweis { flex-basis: 100%; margin: 0; }
  .vorschlag .chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 8px; }
  .chip-s { background: #EEF2F7; border-radius: 14px; padding: 3px 4px 3px 10px; display: inline-flex;
            align-items: center; gap: 4px; }
  .chip-s button, .anlagen .weg { border: 0; background: none; cursor: pointer; font-size: 16px;
                                  color: #666; padding: 0 4px; }
  .vorschlag .hinzu { display: flex; gap: 6px; }
  .vorschlag .hinzu input { flex: 1; }
  .vorschlag table.anlagen { border-collapse: collapse; width: 100%; margin-bottom: 6px; }
  .anlagen th { text-align: left; font-weight: 600; color: #555; font-size: 13px; padding: 2px 6px 2px 0; }
  .anlagen td { padding: 3px 6px 3px 0; }
  .anlagen td:nth-child(2) { width: 90px; }
  .anlagen td:nth-child(3) { width: 30px; }
  .vorschlag .feld .art { align-self: flex-start; }
  .vorschlag .feld .art[hidden] { display: none; }
  #v-karte { height: 380px; border-radius: 8px; border: 1px solid #ddd; }
  .nadel { width: 22px; height: 22px; background: #871D33; border: 2px solid #fff;
           border-radius: 50% 50% 50% 0; transform: rotate(-45deg); margin: 2px 0 0 2px;
           box-shadow: 0 1px 4px rgba(0,0,0,.4); }
  .treffer { list-style: none; margin: 6px 0 0; padding: 0; max-height: 260px; overflow: auto; }
  .treffer li { padding: 5px 6px; border-radius: 4px; cursor: pointer; }
  .treffer li:hover { background: #EEF2F7; }
  .treffer li small { display: block; color: #777; }
  .warnung { background: #FFF6E0; border: 1px solid #E8B64C; border-radius: 8px; padding: 10px 12px;
             margin: 10px 0; }
  .warnung ul { margin: 6px 0; padding-left: 18px; }
  .warnung li { margin: 4px 0 8px; }
  .warnung .grund { color: #7a4a00; font-size: 13px; }
  .warnung a, .ok a, .aenderungen a { color: #185FA5; }
  .ok { background: #EAF3DE; border: 1px solid #9BC27A; border-radius: 8px; padding: 8px 12px;
        margin: 10px 0; color: #27500A; }
  .fehlerbox { background: #FBEAEA; border: 1px solid #D88; border-radius: 8px; padding: 8px 12px;
               color: #7A1F1F; margin: 10px 0; }
  .fehlerbox ul { margin: 4px 0 0; padding-left: 18px; }
  .aenderungen { border: 1px solid #e3e3e3; border-radius: 8px; padding: 8px 12px; margin: 10px 0; }
  .bestaetigen { display: flex; gap: 6px; align-items: flex-start; font-weight: 600; cursor: pointer; }
  .weiter { display: flex; gap: 12px; align-items: center; margin: 8px 0; }
  .knopf-gross { font: inherit; font-size: 16px; font-weight: 600; background: #871D33; color: #fff;
                 border: 0; border-radius: 6px; padding: 10px 20px; cursor: pointer; }
  .knopf-gross:hover { background: #6d1729; }
  .umbruch { word-break: break-all; font-size: 12px; }
</style>
</head>
<body>
<header id="kopf">
  <div class="zeile"><h1>__TITEL__</h1><span id="links"></span></div>
  <div class="zeile">
    <nav id="ansichten" role="tablist" aria-label="Ansicht"></nav>
    <span id="gebietwahl" hidden>
      <label for="g-kreis">Gebiet</label>
      <select id="g-kreis" aria-label="Landkreis oder kreisfreie Stadt"></select>
      <select id="g-kommune" aria-label="Verbandsgemeinde oder Gemeinde" hidden></select>
      <button id="g-weg" type="button" title="Auswahl aufheben" hidden>×</button>
    </span>
  </div>
</header>
<div id="bereich"><div id="karte"></div>
<div id="seite-liste" class="seite" hidden></div>
<div id="seite-uebersicht" class="seite" hidden></div>
<div id="seite-vorschlag" class="seite" hidden></div>
__LADEN__</div>
<script src="__LEAFLET__/leaflet.js"></script>
__SKRIPT__
const KONFIG = window.KONFIG || {};
const ATLAS_FELDER = __ATLAS_FELDER__;
const FARBEN = __FARBEN__;
const KATEGORIE_FARBEN = __KATEGORIE_FARBEN__;
const WEITERE = "#8a8984";
const QUELLE = __QUELLE_JSON__;
const ZOOM_FLAECHEN = 15;
// Reihenfolge = CSS-Klasse stufe-<i>; LEGENDE = Reihenfolge in der Legende
const STUFEN = ["nur ALKIS", "bestätigt", "nur ALKIS – unbestimmt"];
const LEGENDE_STUFEN = ["nur ALKIS – unbestimmt", "nur ALKIS", "bestätigt"];
const ZAHL = new Intl.NumberFormat("de-DE");

// ---------- Hilfen ----------------------------------------------------------------------
function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;",
    '"': "&quot;", "'": "&#39;" }[c]));
}
function leer(v) {
  return v === null || v === undefined || v === "" || v === "nan"
    || (Array.isArray(v) && !v.length);
}
function zahl(n) { return ZAHL.format(n); }
function prozent(a, b) { return b ? Math.round(100 * a / b) : 0; }
function url(u) { return /^https?:\/\//i.test(u) ? u : "https://" + u; }

// Kopfzeile: Links aus konfig.js (nur Webseite); „vorschlagen“ öffnet das Formular
function kopfzeile() {
  if (EINGEBETTET !== null) return;
  const k = KONFIG, el = document.getElementById("links");
  const link = (u, text, klasse) => u ? `<a href="${esc(u)}"${klasse ? ` class="${klasse}"` : ""}`
    + `${/^https?:/.test(u) ? ' target="_blank" rel="noopener"' : ""}>${text}</a>` : "";
  if (k.titel) { document.querySelector("#kopf h1").textContent = k.titel; document.title = k.titel; }
  el.innerHTML = (ANSICHTEN.vorschlag
    ? `<a href="#ansicht=vorschlag" class="knopf" data-vorschlag-neu>Sportstätte vorschlagen</a>`
    : link(k.vorschlag_url, "Sportstätte vorschlagen", "knopf"))
    + link("daten/", "Daten herunterladen") + link(k.impressum_url, "Impressum")
    + link(k.datenschutz_url, "Datenschutz");
}

const ladenEl = document.getElementById("laden");
function zeigeLaden(text) {
  if (!ladenEl) return;
  ladenEl.className = ""; ladenEl.hidden = false;
  ladenEl.innerHTML = `<span class="kreisel"></span><span>${esc(text)}</span>`;
}
function fertig() { if (ladenEl) ladenEl.hidden = true; }
function zeigeFehler(text) {
  if (!ladenEl) { alert(text); return; }
  ladenEl.hidden = false; ladenEl.className = "fehler"; ladenEl.textContent = text;
}

// Daten: eingebettet (eine Datei) oder aus daten/ nachladen; fehlende Datei → null
async function holeJson(name) {
  if (EINGEBETTET) return EINGEBETTET[name] || null;
  const r = await fetch("daten/" + name);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
  return r.json();
}

// ---------- Karte -----------------------------------------------------------------------
const karte = L.map("karte", { preferCanvas: true, maxZoom: 19 });
const DATEN_HINWEIS = QUELLE ? " | Daten: " + esc(QUELLE) : "";
// basemap.de (BKG) erlaubt den Abruf auch aus lokal geöffneten Dateien (file://);
// die OSM-Kacheln verlangen dagegen einen Referer und liefern dort 403.
const BASEMAP = "https://sgx.geodatenzentrum.de/wmts_basemapde/tile/1.0.0/"
  + "{layer}/default/GLOBAL_WEBMERCATOR/{z}/{y}/{x}.png";
const BKG = '&copy; <a href="https://basemap.de">basemap.de</a> / BKG '
  + new Date().getFullYear() + " (CC BY 4.0)";
const hintergruende = {
  "basemap.de Grau": L.tileLayer(BASEMAP, { layer: "de_basemapde_web_raster_grau",
    maxNativeZoom: 18, maxZoom: 19, attribution: BKG + DATEN_HINWEIS }),
  "basemap.de Farbe": L.tileLayer(BASEMAP, { layer: "de_basemapde_web_raster_farbe",
    maxNativeZoom: 18, maxZoom: 19, attribution: BKG + DATEN_HINWEIS }),
  "OpenStreetMap (nur über http://)": L.tileLayer(
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      + DATEN_HINWEIS }),
};
hintergruende["basemap.de Grau"].addTo(karte);
L.control.layers(hintergruende, null, { position: "topleft" }).addTo(karte);
karte.setView([49.95, 7.45], 8);

const POPUP = { maxWidth: 460, minWidth: 260, autoPanPadding: [30, 30] };
const KOPIERHINWEIS = `<div class="hinweis">Text markieren und kopieren möglich</div>`;
function info(layer, html) {
  // Darüberfahren: kurze Vorschau; Klicken: bleibt stehen, Text lässt sich markieren.
  // html darf eine Funktion sein (Inhalt erst beim Anzeigen erzeugen – spart Zeit beim Start).
  layer.bindTooltip(html, { sticky: true });
  layer.bindPopup(typeof html === "function" ? () => html() + KOPIERHINWEIS
    : html + KOPIERHINWEIS, POPUP);
  layer.on("popupopen", () => layer.closeTooltip && layer.closeTooltip());
  return layer;
}
// Koordinaten im Format von Google Maps ("Breite, Länge"), zum Kopieren
function koord(lat, lon) {
  if (leer(lat) || leer(lon)) return "";
  const t = `${(+lat).toFixed(6)}, ${(+lon).toFixed(6)}`;
  return `<tr><td>Koordinaten</td><td><span class="koord">${t}</span> `
    + `<a href="https://www.google.com/maps?q=${encodeURIComponent(t)}" target="_blank" `
    + `rel="noopener">Google Maps</a></td></tr>`;
}
// Link zum Meldeformular (Adresse in konfig.js), optional mit Kennung der Sportstätte
function melden(kennung) {
  if (!KONFIG.vorschlag_url) return "";
  let u = KONFIG.vorschlag_url;
  if (KONFIG.vorschlag_parameter && !leer(kennung)) {
    u += (u.includes("?") ? "&" : "?") + encodeURIComponent(KONFIG.vorschlag_parameter)
      + "=" + encodeURIComponent(kennung);
  }
  return `<tr><td>Fehler?</td><td><a href="${esc(u)}" target="_blank" rel="noopener">`
    + `Änderung oder Fehler melden</a></td></tr>`;
}
function bboxVon(geom) {
  let w = 180, s = 90, o = -180, n = -90;
  const lauf = c => {
    if (typeof c[0] === "number") {
      w = Math.min(w, c[0]); o = Math.max(o, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]);
    } else c.forEach(lauf);
  };
  if (geom && geom.coordinates) lauf(geom.coordinates);
  return [w, s, o, n];
}
const svgRenderer = L.svg({ padding: 0.3 });

// ---------- Gebiete (Kreis, Verbandsgemeinde, Gemeinde) ---------------------------------
// Jedes Objekt trägt den Regionalschlüssel (ars) seiner Gemeinde; ein Gebiet passt, wenn
// der ars mit dem Schlüssel des Gebiets beginnt (Kreis 5, Verbandsgemeinde 9 Stellen).
let GEBIETE = [], GEBIET = null;
const NACH_S = {};
const umrisse = {};  // Ebene → Promise der Umrisse
const umrissEbene = L.layerGroup().addTo(karte);
// rechts Platz für das Filter-Panel lassen
const GEBIET_RAND = { paddingTopLeft: [20, 20], paddingBottomRight: [290, 20] };
const EBENE_TEXT = { kreis: "Kreis", vg: "Verbandsgemeinde", gemeinde: "Gemeinde" };
function imGebiet(ars) { return !GEBIET || (!!ars && ars.startsWith(GEBIET.s)); }
function gemeindeName(ars) {
  const g = ars && NACH_S[ars.slice(0, 12)];
  return g ? g.n : "";
}
function gebietName() { return GEBIET ? GEBIET.n : "Rheinland-Pfalz"; }
function gebietTitel(e) {
  const b = e.b && !e.n.startsWith(e.b) ? ` (${e.b})` : "";
  return e.n + b;
}
function grenzenVon(e) {
  return L.latLngBounds([e.bb[1], e.bb[0]], [e.bb[3], e.bb[2]]);
}
const wahl = {
  feld: document.getElementById("gebietwahl"),
  kreis: document.getElementById("g-kreis"),
  kommune: document.getElementById("g-kommune"),
  weg: document.getElementById("g-weg"),
};
function untergeordnet(e, ebene) {
  return GEBIETE.filter(x => x.e === ebene && x.s.startsWith(e.s));
}
function fuelleKommunen(kreis) {
  const k = wahl.kommune;
  if (!kreis) { k.hidden = true; k.innerHTML = ""; return; }
  const gemeinden = untergeordnet(kreis, "gemeinde");
  if (gemeinden.length <= 1) { k.hidden = true; k.innerHTML = ""; return; }
  let h = `<option value="">alle Gemeinden</option>`;
  for (const vg of untergeordnet(kreis, "vg")) {
    const gem = gemeinden.filter(g => g.s.startsWith(vg.s));
    if (gem.length > 1) {
      h += `<optgroup label="${esc(gebietTitel(vg))}">`
        + `<option value="${vg.s}">${esc(vg.n)} – gesamt</option>`
        + gem.map(g => `<option value="${g.s}">${esc(gebietTitel(g))}</option>`).join("")
        + `</optgroup>`;
    } else if (gem.length === 1) {
      h += `<option value="${gem[0].s}">${esc(gebietTitel(gem[0]))}</option>`;
    }
  }
  k.innerHTML = h; k.hidden = false;
}
function ladeUmrisse(ebene) {
  return umrisse[ebene] ??= holeJson(`gebiete_${ebene}.geojson`).catch(() => null);
}
async function zeigeUmriss(e) {
  umrissEbene.clearLayers();
  if (!e) return;
  const fc = await ladeUmrisse(e.e);
  if (!fc || GEBIET !== e) return;
  const f = fc.features.find(x => x.properties.s === e.s);
  if (f) L.geoJSON(f, { interactive: false, style: { color: "#871D33", weight: 2.5,
    dashArray: "6 4", fill: false } }).addTo(umrissEbene);
}
function setzeGebiet(e, zoomen = true) {
  GEBIET = e || null;
  const kreis = e ? NACH_S[e.s.slice(0, 5)] : null;
  wahl.kreis.value = kreis ? kreis.s : "";
  fuelleKommunen(kreis);
  if (e && e.e !== "kreis") wahl.kommune.value = e.s;
  wahl.weg.hidden = !e;
  zeigeUmriss(GEBIET);
  if (e && zoomen) karte.fitBounds(grenzenVon(e), GEBIET_RAND);
  merkeZustand();
  for (const a of Object.values(ANSICHTEN)) if (a.gestartet && a.gebietGeaendert) a.gebietGeaendert();
}
function starteGebietswahl(index) {
  GEBIETE = index && index.eintraege ? index.eintraege : [];
  if (!GEBIETE.length) return;
  for (const e of GEBIETE) NACH_S[e.s] = e;
  const kreise = GEBIETE.filter(e => e.e === "kreis");
  wahl.kreis.innerHTML = `<option value="">Rheinland-Pfalz (alle)</option>`
    + kreise.map(e => `<option value="${e.s}">${esc(gebietTitel(e))}</option>`).join("");
  wahl.kreis.addEventListener("change", () => setzeGebiet(NACH_S[wahl.kreis.value]));
  wahl.kommune.addEventListener("change", () =>
    setzeGebiet(NACH_S[wahl.kommune.value] || NACH_S[wahl.kreis.value]));
  wahl.weg.addEventListener("click", () => setzeGebiet(null, false));
  wahl.feld.hidden = false;
}

// ---------- Ansichten -------------------------------------------------------------------
const ANSICHTEN = {};
let AKTIV = null;
const nav = document.getElementById("ansichten");
function merkeZustand() {
  const teile = [];
  if (AKTIV && AKTIV !== STANDARD) teile.push("ansicht=" + AKTIV);
  if (GEBIET) teile.push("gebiet=" + GEBIET.s);
  const neu = teile.length ? "#" + teile.join("&") : location.pathname + location.search;
  try { history.replaceState(null, "", neu); } catch (_) { /* z. B. file:// */ }
}
let STANDARD = "bestand";
async function zeige(name) {
  const a = ANSICHTEN[name];
  if (!a || name === AKTIV) return;
  if (!a.gestartet) {
    try {
      await a.starte();
    } catch (fehler) {
      zeigeFehler(location.protocol === "file:"
        ? "Die Seite muss über einen Webserver geöffnet werden (lokal: sportstaettenatlas seite --vorschau)."
        : `Die Daten konnten nicht geladen werden (${fehler.message}).`);
      throw fehler;
    }
    a.gestartet = true;
  }
  const alt = ANSICHTEN[AKTIV];
  if (alt && alt.verbergen) alt.verbergen();
  sucheLeeren();
  AKTIV = name;
  for (const b of nav.querySelectorAll("button")) {
    b.setAttribute("aria-selected", b.dataset.ansicht === name ? "true" : "false");
  }
  a.zeigen();
  merkeZustand();
}
function knoepfe() {
  const namen = Object.keys(ANSICHTEN);
  nav.innerHTML = namen.length < 2 ? "" : namen.map(n =>
    `<button type="button" role="tab" data-ansicht="${n}" aria-selected="false">`
    + `${esc(ANSICHTEN[n].titel)}</button>`).join("");
  nav.querySelectorAll("button").forEach(b => b.addEventListener("click", () => zeige(b.dataset.ansicht)));
}

// ---------- Ansicht „Karte“: der Datenbestand -------------------------------------------
const ARTEN = ["Verein", "Kommune", "sonstige", "ohne Angabe"];
function artVon(p, rolle = "betreiber") { return p[rolle + "_art"] || "ohne Angabe"; }
function katFarbe(k) { return KATEGORIE_FARBEN[k] || WEITERE; }
function schluesselName(s) { return String(s || "").trim().replace(/\s+/g, " ").toLowerCase(); }

function ansichtBestand(fc) {
  const ebene = L.layerGroup();
  const eintraege = [];
  const katZahl = {}, artZahl = {}, spZahl = {};
  for (const f of fc.features) {
    const p = f.properties, [lon, lat] = f.geometry.coordinates;
    const kat = p.kategorie || "ohne Kategorie";
    katZahl[kat] = (katZahl[kat] || 0) + 1;
    const art = artVon(p);
    artZahl[art] = (artZahl[art] || 0) + 1;
    for (const s of p.sportarten || []) spZahl[s] = (spZahl[s] || 0) + 1;
    const e = { p, lat, lon, kat, art, an: false,
      sp: new Set(p.sportarten || []), betreiber: schluesselName(p.betreiber),
      eigentuemer: schluesselName(p.eigentuemer) };
    e.layer = info(L.circleMarker([lat, lon], { radius: 4, weight: 1, color: "#fff",
      fillColor: katFarbe(kat), fillOpacity: 0.95 }), () => tipBestand(e));
    eintraege.push(e);
  }
  const katAn = {}, artAn = {};
  for (const k of Object.keys(katZahl)) katAn[k] = true;
  for (const a of ARTEN) artAn[a] = true;
  const sportWahl = new Set();
  let betreiberWahl = null;  // { rolle, schluessel, name }

  function passt(e) {
    if (!katAn[e.kat] || !artAn[e.art] || !imGebiet(e.p.ars)) return false;
    if (betreiberWahl && e[betreiberWahl.rolle] !== betreiberWahl.schluessel) return false;
    if (sportWahl.size) {
      let ok = false;
      for (const s of sportWahl) if (e.sp.has(s)) { ok = true; break; }
      if (!ok) return false;
    }
    return true;
  }
  let zahlEl = null;
  function aktualisiere() {
    let n = 0;
    for (const e of eintraege) {
      const soll = passt(e);
      if (soll) n++;
      if (soll !== e.an) { e.an = soll; if (soll) ebene.addLayer(e.layer); else ebene.removeLayer(e.layer); }
    }
    if (zahlEl) zahlEl.textContent = n === eintraege.length ? `${zahl(n)} Sportstätten`
      : `${zahl(n)} von ${zahl(eintraege.length)} Sportstätten`;
    return n;
  }

  // Filter-Panel
  const panel = L.control({ position: "topright" });
  let panelEl = null;
  panel.onAdd = () => {
    const div = panelEl = L.DomUtil.create("div", "panel filter");
    L.DomEvent.disableClickPropagation(div);
    L.DomEvent.disableScrollPropagation(div);
    const kats = Object.keys(katZahl).sort((a, b) => katZahl[b] - katZahl[a]);
    const sps = Object.keys(spZahl).sort((a, b) => a.localeCompare(b, "de"));
    div.innerHTML = `<h1 id="b-zahl"></h1><div id="b-chip"></div>`
      + `<details open><summary>Kategorie</summary><div class="knoepfe">`
      + `<button type="button" data-alle="kat">alle</button><button type="button" data-keine="kat">keine</button></div>`
      + kats.map(k => `<label><input type="checkbox" data-k="${esc(k)}" checked>`
        + `<span class="swatch" style="background:${katFarbe(k)}"></span>${esc(k)}`
        + `<span class="n">${zahl(katZahl[k])}</span></label>`).join("") + `</details>`
      + `<details open><summary>Betreiber</summary>`
      + ARTEN.filter(a => artZahl[a]).map(a => `<label><input type="checkbox" data-a="${a}" checked>`
        + `${a === "Verein" ? "Vereine" : a === "Kommune" ? "Kommunen" : a}`
        + `<span class="n">${zahl(artZahl[a])}</span></label>`).join("")
      + `<div class="hinweis">Art aus dem Namen geschätzt (z. B. „e.V.“, „Ortsgemeinde“)</div></details>`
      + (sps.length ? `<details><summary>Sportarten <span id="b-sp-n"></span></summary>`
        + `<input type="search" placeholder="Sportart suchen" aria-label="Sportart suchen">`
        + `<div class="sp-liste">` + sps.map(s => `<label data-text="${esc(s.toLowerCase())}">`
          + `<input type="checkbox" data-s="${esc(s)}">${esc(s)}<span class="n">${zahl(spZahl[s])}</span></label>`).join("")
        + `</div><div class="knoepfe"><button type="button" data-keine="sp">Auswahl aufheben</button></div>`
        + `<div class="hinweis">Ohne Auswahl: alle. Mit Auswahl: Sportstätten mit mindestens einer davon.</div></details>`
        : "")
      + `<div class="hinweis">Klick auf einen Punkt: Angaben bleiben stehen · Rechtsklick: Koordinaten</div>`;
    zahlEl = div.querySelector("#b-zahl");
    div.querySelectorAll("input[data-k]").forEach(cb => cb.addEventListener("change", () => {
      katAn[cb.dataset.k] = cb.checked; aktualisiere(); }));
    div.querySelectorAll("input[data-a]").forEach(cb => cb.addEventListener("change", () => {
      artAn[cb.dataset.a] = cb.checked; aktualisiere(); }));
    const spN = div.querySelector("#b-sp-n");
    const spZeige = () => { if (spN) spN.textContent = sportWahl.size ? `(${sportWahl.size})` : ""; };
    div.querySelectorAll("input[data-s]").forEach(cb => cb.addEventListener("change", () => {
      if (cb.checked) sportWahl.add(cb.dataset.s); else sportWahl.delete(cb.dataset.s);
      spZeige(); aktualisiere(); }));
    div.querySelectorAll("[data-alle],[data-keine]").forEach(b => b.addEventListener("click", () => {
      const an = !!b.dataset.alle, was = b.dataset.alle || b.dataset.keine;
      if (was === "kat") {
        div.querySelectorAll("input[data-k]").forEach(cb => { cb.checked = an; katAn[cb.dataset.k] = an; });
      } else {
        div.querySelectorAll("input[data-s]").forEach(cb => { cb.checked = false; });
        sportWahl.clear(); spZeige();
      }
      aktualisiere();
    }));
    const suchSp = div.querySelector(".sp-liste") && div.querySelector("details input[type=search]");
    if (suchSp) suchSp.addEventListener("input", () => {
      const q = suchSp.value.trim().toLowerCase();
      div.querySelectorAll(".sp-liste label").forEach(l => { l.hidden = q && !l.dataset.text.includes(q); });
    });
    zeigeChip();
    aktualisiere();
    return div;
  };
  function zeigeChip() {
    const el = panelEl && panelEl.querySelector("#b-chip");
    if (!el) return;
    el.innerHTML = betreiberWahl ? `<div class="chip">${betreiberWahl.rolle === "betreiber"
      ? "Betreiber" : "Eigentümer"}: <b>${esc(betreiberWahl.name)}</b> `
      + `<button type="button" title="Filter aufheben">× aufheben</button></div>` : "";
    const b = el.querySelector("button");
    if (b) b.addEventListener("click", () => { betreiberWahl = null; zeigeChip(); aktualisiere(); });
  }

  // Ein gesuchter Eintrag soll sichtbar werden, auch wenn Filter ihn gerade ausblenden
  function filterZurueck() {
    betreiberWahl = null; sportWahl.clear();
    for (const k in katAn) katAn[k] = true;
    for (const a in artAn) artAn[a] = true;
    if (panelEl) {
      panelEl.querySelectorAll("input[data-k],input[data-a]").forEach(c => { c.checked = true; });
      panelEl.querySelectorAll("input[data-s]").forEach(c => { c.checked = false; });
      const spN = panelEl.querySelector("#b-sp-n");
      if (spN) spN.textContent = "";
    }
    zeigeChip();
  }
  function oeffne(e) {
    if (!imGebiet(e.p.ars)) setzeGebiet(null, false);
    if (!passt(e)) filterZurueck();
    aktualisiere();
    if (e.an) e.layer.openPopup();
  }

  function tipBestand(e) {
    const p = e.p, z = [];
    const zeile = (l, v) => { if (!leer(v)) z.push(`<tr><td>${l}</td><td>${v}</td></tr>`); };
    const art = a => a ? `<span class="art">${esc(a)}</span>` : "";
    zeile("Kategorie", leer(p.kategorie) ? "" : `<span class="swatch" style="display:inline-block;`
      + `background:${katFarbe(e.kat)};vertical-align:-1px"></span> ${esc(p.kategorie)}`);
    zeile("Adresse", leer(p.adresse) ? "" : esc(p.adresse));
    zeile("Gebiet", esc(gemeindeName(p.ars)));
    zeile("Sportarten", leer(p.sportarten) ? "" : esc(p.sportarten.join(", ")));
    if (!leer(p.anlagen)) {
      const n = {};
      for (const a of p.anlagen) n[a] = (n[a] || 0) + 1;
      zeile("Anlagen", Object.entries(n).map(([a, k]) => (k > 1 ? `${k}× ` : "") + esc(a)).join("<br>"));
    }
    zeile("Betreiber", leer(p.betreiber) ? "" : esc(p.betreiber) + art(p.betreiber_art));
    zeile("Eigentümer", leer(p.eigentuemer) ? "" : esc(p.eigentuemer) + art(p.eigentuemer_art));
    zeile("Öffentlich", esc(p.oeffentlicher_zugang || ""));
    zeile("Schulsport", esc(p.schulsport || ""));
    zeile("Zuschauer", leer(p.zuschauerplaetze) ? "" : zahl(p.zuschauerplaetze));
    zeile("Betrieb", esc(p.betriebsstatus || ""));
    zeile("Website", leer(p.website) ? "" : `<a href="${esc(url(p.website))}" target="_blank" `
      + `rel="noopener">${esc(p.website)}</a>`);
    zeile("ALKIS", esc(p.alkis || ""));
    zeile("ID", leer(p.id) ? "" : `<span class="koord">${esc(p.id)}</span>`);
    return `<div class="tip"><h3>${esc(p.name || p.kategorie || "Sportstätte")}</h3>`
      + `<table class="meta">${z.join("")}${koord(e.lat, e.lon)}${aendernLink(p.id) || melden(p.id)}</table></div>`;
  }

  const such = eintraege.map(e => ({
    titel: e.p.name || e.kat, sub: [e.p.kategorie, e.p.adresse, e.p.betreiber].filter(v => !leer(v)).join(" · "),
    text: [e.p.name, e.p.adresse, e.p.kategorie, e.p.betreiber, e.p.eigentuemer, e.p.id,
      ...(e.p.sportarten || [])].filter(v => !leer(v)).join(" ").toLowerCase(),
    grenzen: () => L.latLngBounds([[e.lat, e.lon], [e.lat, e.lon]]),
    oeffne: () => oeffne(e),
    ars: e.p.ars,
  }));
  let erstmals = true;
  return {
    titel: "Karte",
    eintraege,
    starte() {},
    zeigen() {
      ebene.addTo(karte); panel.addTo(karte); aktualisiere();
      if (erstmals && !GEBIET && eintraege.length) {
        karte.fitBounds(L.latLngBounds(eintraege.map(e => [e.lat, e.lon])), { padding: [20, 20] });
      }
      erstmals = false;
    },
    verbergen() { karte.removeLayer(ebene); panel.remove(); },
    aktualisiere() {},
    gebietGeaendert() { aktualisiere(); },
    suchindex: () => such,
    zeigeBetreiber(rolle, schluessel, name) {
      betreiberWahl = { rolle, schluessel, name };
      zeige("bestand").then(() => {
        zeigeChip();
        aktualisiere();
        const pkte = eintraege.filter(e => e.an).map(e => [e.lat, e.lon]);
        if (pkte.length) karte.fitBounds(L.latLngBounds(pkte).pad(0.15), { maxZoom: 16 });
      });
    },
    zeigeEintrag(e) {
      zeige("bestand").then(() => {
        karte.setView([e.lat, e.lon], Math.max(karte.getZoom(), 16));
        oeffne(e);
      });
    },
  };
}

// ---------- Ansicht „Liste“: Vereine und Kommunen als Betreiber -------------------------
function ansichtListe(bestand) {
  const el = document.getElementById("seite-liste");
  let art = "Verein", rolle = "betreiber", filterText = "", sortierung = { feld: "n", ab: true };
  const offen = new Set();
  function gruppen() {
    const g = new Map();
    for (const e of bestand.eintraege) {
      if (!imGebiet(e.p.ars) || artVon(e.p, rolle) !== art) continue;
      const s = e[rolle];
      if (!s) continue;
      let x = g.get(s);
      if (!x) g.set(s, x = { s, namen: {}, liste: [], orte: {}, kats: {} });
      const name = e.p[rolle].trim().replace(/\s+/g, " ");
      x.namen[name] = (x.namen[name] || 0) + 1;
      x.liste.push(e);
      if (e.p.ort) x.orte[e.p.ort] = (x.orte[e.p.ort] || 0) + 1;
      x.kats[e.kat] = (x.kats[e.kat] || 0) + 1;
    }
    const top = (o, n) => Object.entries(o).sort((a, b) => b[1] - a[1]).slice(0, n).map(x => x[0]);
    return [...g.values()].map(x => ({ ...x, name: top(x.namen, 1)[0], n: x.liste.length,
      ort: top(x.orte, 3).join(", ") + (Object.keys(x.orte).length > 3 ? " …" : ""),
      kat: top(x.kats, 3).join(", ") + (Object.keys(x.kats).length > 3 ? " …" : "") }));
  }
  function zaehle() {
    const z = {};
    for (const e of bestand.eintraege) if (imGebiet(e.p.ars)) {
      const a = artVon(e.p, rolle); if (e[rolle]) (z[a] ??= new Set()).add(e[rolle]);
    }
    return z;
  }
  function zeichne() {
    const z = zaehle();
    let liste = gruppen();
    if (filterText) liste = liste.filter(x => x.s.includes(filterText) || x.ort.toLowerCase().includes(filterText));
    const { feld, ab } = sortierung;
    liste.sort((a, b) => (feld === "n" ? a.n - b.n : String(a[feld]).localeCompare(String(b[feld]), "de"))
      * (ab ? -1 : 1) || a.name.localeCompare(b.name, "de"));
    const reiter = ["Verein", "Kommune", "sonstige"].map(a => `<button type="button" data-art="${a}" `
      + `aria-pressed="${a === art}">${a === "Verein" ? "Vereine" : a === "Kommune" ? "Kommunen" : "sonstige"}`
      + ` (${zahl(z[a] ? z[a].size : 0)})</button>`).join("");
    const pfeil = f => sortierung.feld === f ? (sortierung.ab ? " ▼" : " ▲") : "";
    const zeilen = liste.map(x => {
      const auf = offen.has(x.s);
      let h = `<tr class="zeile${auf ? " offen" : ""}" data-s="${esc(x.s)}"><td>${auf ? "▾" : "▸"} ${esc(x.name)}</td>`
        + `<td class="zahl">${zahl(x.n)}</td><td class="klein">${esc(x.ort)}</td><td class="klein">${esc(x.kat)}</td></tr>`;
      if (auf) {
        h += `<tr class="details"><td colspan="4"><button type="button" class="knopf2" data-karte="${esc(x.s)}">`
          + `Alle ${zahl(x.n)} auf der Karte zeigen</button><table class="tabelle">`
          + x.liste.slice().sort((a, b) => (a.p.ort || "").localeCompare(b.p.ort || "", "de")).map(e =>
            `<tr><td><a data-i="${bestand.eintraege.indexOf(e)}">${esc(e.p.name || e.kat)}</a></td>`
            + `<td class="klein">${esc(e.p.kategorie || "")}</td><td class="klein">${esc(e.p.adresse || "")}</td></tr>`).join("")
          + `</table></td></tr>`;
      }
      return h;
    }).join("");
    el.innerHTML = `<div class="inhalt"><h2>Betreiber und Eigentümer</h2>`
      + `<p class="unter">${esc(gebietName())} · Art aus dem Namen geschätzt („e.V.“, „TuS“, „Ortsgemeinde“, „Stadt“ …)</p>`
      + `<div class="reiter">${reiter}<select aria-label="Rolle"><option value="betreiber"${rolle === "betreiber" ? " selected" : ""}>als Betreiber</option>`
      + `<option value="eigentuemer"${rolle === "eigentuemer" ? " selected" : ""}>als Eigentümer</option></select>`
      + `<input type="search" placeholder="Name oder Ort filtern" value="${esc(filterText)}" aria-label="Filter"></div>`
      + `<table class="tabelle"><thead><tr><th data-sort="name">Name${pfeil("name")}</th>`
      + `<th class="zahl" data-sort="n">Sportstätten${pfeil("n")}</th><th data-sort="ort">Orte${pfeil("ort")}</th>`
      + `<th data-sort="kat">Kategorien${pfeil("kat")}</th></tr></thead><tbody>${zeilen
        || `<tr><td colspan="4" class="klein">Keine Einträge.</td></tr>`}</tbody></table></div>`;
    el.querySelectorAll("[data-art]").forEach(b => b.addEventListener("click", () => {
      art = b.dataset.art; offen.clear(); zeichne(); }));
    el.querySelector("select").addEventListener("change", ev => { rolle = ev.target.value; offen.clear(); zeichne(); });
    const feldEl = el.querySelector("input[type=search]");
    feldEl.addEventListener("input", () => {
      filterText = feldEl.value.trim().toLowerCase().replace(/\s+/g, " ");
      const pos = feldEl.selectionStart; zeichne();
      const neu = el.querySelector("input[type=search]"); neu.focus(); neu.setSelectionRange(pos, pos);
    });
    el.querySelectorAll("th[data-sort]").forEach(th => th.addEventListener("click", () => {
      const f = th.dataset.sort;
      sortierung = { feld: f, ab: sortierung.feld === f ? !sortierung.ab : f === "n" };
      zeichne();
    }));
    el.querySelectorAll("tr.zeile").forEach(tr => tr.addEventListener("click", () => {
      const s = tr.dataset.s; if (offen.has(s)) offen.delete(s); else offen.add(s); zeichne(); }));
    el.querySelectorAll("[data-karte]").forEach(b => b.addEventListener("click", () => {
      const x = liste.find(y => y.s === b.dataset.karte);
      bestand.zeigeBetreiber(rolle, x.s, x.name);
    }));
    el.querySelectorAll("a[data-i]").forEach(a => a.addEventListener("click", () =>
      bestand.zeigeEintrag(bestand.eintraege[+a.dataset.i])));
  }
  return {
    titel: "Liste",
    starte() {},
    zeigen() { el.hidden = false; zeichne(); },
    verbergen() { el.hidden = true; },
    gebietGeaendert() { if (!el.hidden) zeichne(); },
  };
}

// ---------- Ansicht „Übersicht“: kleines Dashboard über den Datenbestand ----------------
const FELDER = [
  ["Name", p => !leer(p.name)],
  ["Kategorie", p => !leer(p.kategorie)],
  ["Straße", p => !leer(p.strasse)],
  ["PLZ und Ort", p => !leer(p.plz) && !leer(p.ort)],
  ["Sportarten", p => !leer(p.sportarten)],
  ["Anlagen", p => !leer(p.anlagen)],
  ["Betreiber", p => !leer(p.betreiber)],
  ["Eigentümer", p => !leer(p.eigentuemer)],
  ["Öffentlicher Zugang", p => !leer(p.oeffentlicher_zugang)],
  ["Schulsport", p => !leer(p.schulsport)],
  ["Betriebsstatus", p => !leer(p.betriebsstatus)],
  ["Zuschauerplätze", p => !leer(p.zuschauerplaetze)],
  ["Website", p => !leer(p.website)],
];
function befuellung(liste) {
  if (!liste.length) return 0;
  let summe = 0;
  for (const e of liste) for (const [, test] of FELDER) if (test(e.p)) summe++;
  return summe / (liste.length * FELDER.length);
}
function balken(zeilen, gesamt, prozentual) {
  // zeilen: [label, wert, aktion?]; Breite relativ zu gesamt (Anteil) bzw. zum Maximum
  const max = prozentual ? gesamt : Math.max(1, ...zeilen.map(z => z[1]));
  return `<table class="balken">` + zeilen.map(([l, w, s]) => {
    const breite = Math.max(0, Math.min(100, 100 * w / (max || 1)));
    const text = prozentual ? `${prozent(w, gesamt)} %` : zahl(w);
    const titel = prozentual ? `${zahl(w)} von ${zahl(gesamt)}` : `${zahl(w)} Sportstätten`;
    return `<tr${s ? ` class="klickbar" data-g="${s}"` : ""} title="${esc(l)}: ${titel}"><td class="l">${esc(l)}</td>`
      + `<td><div class="spur"><div class="fuell" style="width:${breite.toFixed(1)}%"></div></div></td>`
      + `<td class="w">${text}</td></tr>`;
  }).join("") + `</table>`;
}
function ansichtUebersicht(bestand) {
  const el = document.getElementById("seite-uebersicht");
  function zeichne() {
    const liste = bestand.eintraege.filter(e => imGebiet(e.p.ars));
    const n = liste.length;
    const anlagen = liste.reduce((s, e) => s + (e.p.anlagen ? e.p.anlagen.length : 0), 0);
    const sportarten = new Set(liste.flatMap(e => e.p.sportarten || []));
    const betr = { Verein: new Set(), Kommune: new Set() };
    for (const e of liste) if (betr[e.art] && e.betreiber) betr[e.art].add(e.betreiber);
    const zaehl = f => { const z = {}; for (const e of liste) { const k = f(e); z[k] = (z[k] || 0) + 1; } return z; };
    const sortiert = z => Object.entries(z).sort((a, b) => b[1] - a[1]);
    const kachel = (label, wert, zusatz = "") => `<div class="kachel"><div class="label">${label}</div>`
      + `<div class="wert">${wert}</div><div class="zusatz">${zusatz}</div></div>`;
    let h = `<div class="inhalt"><h2>Übersicht: ${esc(gebietName())}</h2>`
      + `<p class="unter">Datenbestand der Karte (Ordner <code>daten/</code>)</p><div class="kacheln">`
      + kachel("Sportstätten", zahl(n))
      + kachel("Sportanlagen", zahl(anlagen), n ? `Ø ${(anlagen / n).toLocaleString("de-DE",
        { maximumFractionDigits: 1 })} je Sportstätte` : "")
      + kachel("Felder befüllt", `${Math.round(100 * befuellung(liste))} %`, `Durchschnitt über ${FELDER.length} Felder`)
      + kachel("Sportarten", zahl(sportarten.size), "verschiedene")
      + kachel("Vereine", zahl(betr.Verein.size), "als Betreiber (aus dem Namen geschätzt)")
      + kachel("Kommunen", zahl(betr.Kommune.size), "als Betreiber (aus dem Namen geschätzt)")
      + `</div>`;
    h += `<div class="spalten"><div><h3>Wie gut sind die Felder befüllt?</h3>`
      + balken(FELDER.map(([l, t]) => [l, liste.filter(e => t(e.p)).length]), n, true) + `</div>`
      + `<div><h3>Sportstätten nach Kategorie</h3>` + balken(sortiert(zaehl(e => e.kat)), n, false)
      + `<h3>Betreiber</h3>` + balken(ARTEN.map(a => [a === "Verein" ? "Vereine" : a === "Kommune"
        ? "Kommunen" : a, liste.filter(e => e.art === a).length]).filter(z => z[1]), n, true);
    const alkis = zaehl(e => e.p.alkis || "ohne Abgleich");
    if (Object.keys(alkis).some(k => k !== "ohne Abgleich")) {
      h += `<h3>Abgleich mit dem Liegenschaftskataster (ALKIS)</h3>`
        + balken(["in ALKIS", "ALKIS in der Nähe", "nicht in ALKIS", "ohne Abgleich"]
          .filter(k => alkis[k]).map(k => [k, alkis[k]]), n, true);
    }
    h += `</div></div>`;
    // Teilgebiete: Befüllung je Kreis bzw. je Verbandsgemeinde/Gemeinde
    const ebene = !GEBIET ? "kreis" : GEBIET.e === "kreis" ? "vg" : GEBIET.e === "vg" ? "gemeinde" : null;
    const teile = ebene ? GEBIETE.filter(g => g.e === ebene && (!GEBIET || g.s.startsWith(GEBIET.s))) : [];
    if (teile.length > 1) {
      const zeilen = teile.map(g => {
        const l = liste.filter(e => e.p.ars && e.p.ars.startsWith(g.s));
        return { g, n: l.length, b: befuellung(l) };
      }).sort((a, b) => b.n - a.n);
      h += `<h3>Nach ${ebene === "kreis" ? "Kreisen" : ebene === "vg" ? "Verbandsgemeinden" : "Gemeinden"}</h3>`
        + `<table class="tabelle"><thead><tr><th>Gebiet</th><th class="zahl">Sportstätten</th>`
        + `<th style="width:40%">Felder befüllt</th></tr></thead><tbody>` + zeilen.map(z =>
          `<tr class="zeile" data-g="${z.g.s}" title="Gebiet auswählen"><td>${esc(gebietTitel(z.g))}</td>`
          + `<td class="zahl">${zahl(z.n)}</td><td><table class="balken"><tr><td><div class="spur">`
          + `<div class="fuell" style="width:${(100 * z.b).toFixed(1)}%"></div></div></td>`
          + `<td class="w">${z.n ? Math.round(100 * z.b) + " %" : "–"}</td></tr></table></td></tr>`).join("")
        + `</tbody></table>`;
    }
    h += `<p class="hinweis">Sportkomplexe (mehrere Sportstätten an einem Ort) führt der Datenbestand `
      + `bisher nicht; gezählt werden Sportstätten und ihre Anlagen.</p></div>`;
    el.innerHTML = h;
    el.querySelectorAll("[data-g]").forEach(z => z.addEventListener("click", () => setzeGebiet(NACH_S[z.dataset.g])));
  }
  return {
    titel: "Übersicht",
    starte() {},
    zeigen() { el.hidden = false; zeichne(); },
    verbergen() { el.hidden = true; },
    gebietGeaendert() { if (!el.hidden) zeichne(); },
  };
}

// ---------- Ansicht „Verifikation“: ALKIS-Objekte und Abgleich mit dem Atlas ------------
function ansichtVerifikation() {
  const ebene = L.layerGroup();
  let legende = null, aktualisiere = () => {}, such = [], startGrenzen = null;
  async function starte() {
    if (!EINGEBETTET) zeigeLaden("ALKIS-Daten werden geladen (einige MB) …");
    const [ANLAGEN, STAETTEN, ATLAS] = await Promise.all(["sportanlagen.geojson",
      "sportstaetten.geojson", "atlas_abgleich.geojson"].map(holeJson));
    fertig();
    if (!ANLAGEN || !STAETTEN) throw new Error("ALKIS-Daten fehlen (sportanlagen.geojson)");
    baue(ANLAGEN, STAETTEN, ATLAS || { type: "FeatureCollection", features: [] });
  }
  function baue(ANLAGEN, STAETTEN, ATLAS) {
    function farbe(p) { return FARBEN[p.typgruppe] || "#D85A30"; }
    // Rohspalten des Atlas (alt_*) erscheinen nicht im Tooltip; ihre Werte
    // stecken in den zusammengeführten Feldern, deren Herkunft in Klammern steht.
    const ROH = /^(osm_|wd_|web_|verband_|alt_)|_quelle$|^verifikation|^(lon|lat|geometry|ars)$/;
    const LABEL = { flaeche_m2: "fläche m²", alkis_text: "ALKIS", alkis_oid: "ALKIS-OID",
      sportstaette_id: "Sportstätte", anlage_id: "Anlage", anzahl_anlagen: "Anlagen",
      oeffnungszeiten: "öffnungszeiten", pruefen: "zu prüfen", alkis_stand: "ALKIS-Stand",
      anlagen_laut_altbestand: "Anlagen (Altbestand)" };
    const ZUERST = ["name", "typ", "typgruppe", "betreiber", "eigentuemer", "adresse", "sportarten",
      "website", "email", "betriebsstatus"];
    function zeilen(p, ohne = new Set()) {
      const keys = Object.keys(p).filter(k => !ROH.test(k) && !ohne.has(k) && !leer(p[k]));
      keys.sort((a, b) => {
        const ia = ZUERST.indexOf(a), ib = ZUERST.indexOf(b);
        return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
      });
      return keys.map(k => {
        const q = p[k + "_quelle"];
        let v = typeof p[k] === "boolean" ? (p[k] ? "ja" : "nein") : esc(p[k]);
        if (k === "website" || k === "wikipedia") v = `<a href="${esc(p[k])}">${v}</a>`;
        return `<tr><td>${esc(LABEL[k] || k)}</td><td>${v}`
          + (q ? ` <span class="q">(${esc(q)})</span>` : "") + "</td></tr>";
      }).join("");
    }
    function verifikation(p) {
      if (leer(p.verifikation)) return "";
      const i = Math.max(0, STUFEN.indexOf(p.verifikation_stufe));
      const bezug = leer(p.alt_bezug) ? ""
        : ` <span class="q">(Atlas: ${esc(p.alt_bezug)})</span>`;
      return `<tr><td>Verifikation</td><td><span class="verif stufe-${i}">`
        + `${esc(p.verifikation_stufe || "")}</span> ${esc(p.verifikation)}${bezug}</td></tr>`;
    }
    const STAETTE = {};
    for (const f of STAETTEN.features) STAETTE[f.properties.sportstaette_id] = f.properties;
    VERIF_STAETTEN = STAETTE;
    function tipStaette(s) {
      // Als Kennung für das Meldeformular dient die ALKIS-Objektkennung: sie bleibt über
      // Neuberechnungen gleich, die laufende Nummer (ST000123) dagegen nicht.
      return `<table class="meta">${verifikation(s)}${zeilen(s)}${koord(s.lat, s.lon)}`
        + (ANSICHTEN.vorschlag ? `<tr><td>Vorschlag</td><td><a href="#" data-vorschlag-alkis=`
          + `"${esc(s.sportstaette_id)}">Als neue Sportstätte vorschlagen</a></td></tr>`
          : melden(!leer(s.alkis_oid) ? s.alkis_oid : s.sportstaette_id)) + `</table>`;
    }
    function tipAnlage(p) {
      const s = STAETTE[p.sportstaette_id];
      let h = `<div class="tip"><h3>Sportanlage: ${esc(p.typ || "")}</h3>`
        + `<table class="meta">${verifikation(p)}${zeilen(p, new Set(["sportstaette_id"]))}`
        + `${koord(p.lat, p.lon)}</table>`;
      if (s) {
        h += `<h4>Sportstätte ${esc(s.sportstaette_id)} – gilt für alle ihre Anlagen</h4>`
          + tipStaette(s);
      }
      return h + "</div>";
    }

    // Sportstätten (Flächen) als gestrichelter Umriss
    const staetten = L.geoJSON(STAETTEN, {
      style: { color: "#444", weight: 1, dashArray: "4 3", fillOpacity: 0.04 },
      onEachFeature: (f, l) => info(l,
        `<div class="tip"><h3>Sportstätte</h3>${tipStaette(f.properties)}</div>`)
    });

    // Schraffur je Verifikationsstufe: Die Füllfarbe zeigt die Klasse (Typgruppe), die
    // Schraffur darüber in Grautönen die Verifikation – dunkel = auch im bisherigen Atlas.
    // Einträge, die nur im Sportstättenatlas RLP stehen, sind gegenläufig schraffiert (−45°).
    const SCHRAFFUR = {
      "nur ALKIS – unbestimmt": { grau: "#F1EFE8", abstand: 6, breite: 1.2, winkel: 0 },
      "nur ALKIS":          { grau: "#F1EFE8", abstand: 10, breite: 1.5, winkel: 45 },
      "bestätigt":          { grau: "#5F5E5A", abstand: 7,  breite: 1.6, winkel: 45 },
      "nicht in ALKIS":     { grau: "#F1EFE8", abstand: 3,  breite: 1.1, winkel: -45 },
      "nah":                { grau: "#5F5E5A", abstand: 3,  breite: 1.1, winkel: -45 },
    };
    const SCHRAFFUR_ID = {};
    (function muster() {
      const ns = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(ns, "svg");
      svg.setAttribute("width", "0"); svg.setAttribute("height", "0");
      svg.style.position = "absolute";
      const defs = document.createElementNS(ns, "defs");
      Object.entries(SCHRAFFUR).forEach(([stufe, m], i) => {
        const id = "schraffur-" + i;
        SCHRAFFUR_ID[stufe] = id;
        const pat = document.createElementNS(ns, "pattern");
        pat.setAttribute("id", id);
        pat.setAttribute("patternUnits", "userSpaceOnUse");
        pat.setAttribute("width", m.abstand); pat.setAttribute("height", m.abstand);
        pat.setAttribute("patternTransform", `rotate(${m.winkel})`);
        const linie = document.createElementNS(ns, "line");
        linie.setAttribute("x1", 0); linie.setAttribute("y1", 0);
        linie.setAttribute("x2", 0); linie.setAttribute("y2", m.abstand);
        linie.setAttribute("stroke", m.grau); linie.setAttribute("stroke-width", m.breite);
        pat.appendChild(linie); defs.appendChild(pat);
      });
      svg.appendChild(defs);
      document.body.appendChild(svg);
    })();
    function schraffurCss(stufe) {
      const m = SCHRAFFUR[stufe];
      if (!m) return "";
      return `background-image: repeating-linear-gradient(${m.winkel}deg, ${m.grau} 0 ${m.breite}px, `
        + `transparent ${m.breite}px ${m.abstand * 0.7}px)`;
    }

    // Sportanlagen: je Typgruppe zwei Ebenen – Punkt (weit) und Umriss (nah)
    const gruppen = {};
    const stufeAn = { "nur ALKIS – unbestimmt": true, "nur ALKIS": true, "bestätigt": true, "": true };
    const gruppe = name => gruppen[name] ??= { punkte: [], flaechen: [], n: 0, an: true };
    function stufeVon(p) {
      const s = STAETTE[p.sportstaette_id];
      return (s && s.verifikation_stufe) || p.verifikation_stufe || "";
    }
    for (const f of ANLAGEN.features) {
      const p = f.properties;
      const g = gruppe(p.typgruppe || "unbekannt");
      g.n++;
      const stil = { color: farbe(p), weight: 1.5, fillColor: farbe(p), fillOpacity: 0.45,
                     dashArray: p.pruefen ? "3 3" : null };
      const tip = tipAnlage(p);
      const stufe = stufeVon(p);
      if (p.lat != null && p.lon != null) {
        g.punkte.push({ stufe, ars: p.ars, layer: info(L.circleMarker([p.lat, p.lon], { ...stil,
          weight: 1, radius: p.rolle === "zubehoer" ? 2 : 3.5, fillOpacity: 0.85 }), tip) });
      }
      if (f.geometry) {
        const basis = info(L.geoJSON(f, { style: { ...stil, renderer: svgRenderer },
          pointToLayer: (_, ll) => L.circleMarker(ll, stil) }), tip);
        const schicht = [basis];
        if (SCHRAFFUR_ID[stufe] && f.geometry.type !== "Point") {
          schicht.push(L.geoJSON(f, { style: { renderer: svgRenderer, stroke: false,
            fill: true, fillColor: `url(#${SCHRAFFUR_ID[stufe]})`, fillOpacity: 1,
            interactive: false } }));
        }
        g.flaechen.push({ stufe, ars: p.ars, bbox: bboxVon(f.geometry), layer: L.layerGroup(schicht) });
      }
    }
    const sichtbar = L.layerGroup().addTo(ebene);

    // Was nur im bisherigen Sportstättenatlas RLP steht (aus dem Abgleich mit ALKIS)
    const ATLAS_STIL = {
      "nicht in ALKIS": { color: "#A32D2D", fillColor: "#F09595", kurz: "nur Atlas",
        label: "nur im Sportstättenatlas RLP – kein ALKIS-Objekt im Umkreis von 200 m" },
      "nah": { color: "#854F0B", fillColor: "#FAC775", kurz: "nur Atlas, ALKIS in der Nähe",
        label: "im Sportstättenatlas RLP – nächste ALKIS-Sportstätte 100–200 m entfernt" },
    };
    const atlasAn = { "nicht in ALKIS": true, "nah": true };

    // Pfeil vom Atlas-Eintrag zur nächsten ALKIS-Sportstätte (bei Status "nah")
    const pfeilEbene = L.layerGroup().addTo(ebene);
    function zeigePfeil(von, s) {
      pfeilEbene.clearLayers();
      if (s.lat == null || s.lon == null) return;
      const nach = [s.lat, s.lon];
      L.polyline([von, nach], { color: "#854F0B", weight: 3, dashArray: "6 4",
        interactive: false }).addTo(pfeilEbene);
      // Pfeilspitze: Richtung aus projizierten Koordinaten (in Web-Mercator winkeltreu)
      const a = karte.project(von, 0), b = karte.project(nach, 0);
      const winkel = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
      L.marker(nach, { interactive: false, icon: L.divIcon({ className: "", iconSize: [22, 22],
        iconAnchor: [11, 11], html: `<div class="pfeil" style="transform:rotate(${winkel}deg)">➤</div>` })
      }).addTo(pfeilEbene);
      const f = STAETTEN.features.find(x => x.properties.sportstaette_id === s.sportstaette_id);
      if (f) {
        L.geoJSON(f, { style: { color: "#854F0B", weight: 3, fillOpacity: 0.1, renderer: svgRenderer },
          interactive: false }).addTo(pfeilEbene);
      }
      L.circleMarker(nach, { radius: 4, color: "#854F0B", fillOpacity: 1, interactive: false })
        .bindTooltip(`ALKIS: ${esc(s.name || s.sportstaette_id)}`, { permanent: true,
          direction: "right", offset: [8, 0] }).addTo(pfeilEbene);
      karte.fitBounds(L.latLngBounds([von, nach]).pad(0.6), { maxZoom: 17 });
    }
    karte.on("popupclose", () => pfeilEbene.clearLayers());
    const atlasPunkte = [];
    for (const f of ATLAS.features) {
      const p = f.properties, st = ATLAS_STIL[p.status] || ATLAS_STIL["nicht in ALKIS"];
      const [lon, lat] = f.geometry.coordinates;
      const zeilenA = Object.entries(ATLAS_FELDER).filter(([k]) => !leer(p[k])).map(([k, l]) =>
        `<tr><td>${esc(l)}</td><td>${typeof p[k] === "boolean" ? (p[k] ? "ja" : "nein")
          : esc(p[k])}</td></tr>`).join("");
      const tip = `<div class="tip"><h3>Sportstättenatlas RLP: ${esc(p.alt_name || "")}</h3>`
        + `<table class="meta"><tr><td>Verifikation</td><td><span class="verif" `
        + `style="background:${st.fillColor};color:${st.color}">${esc(st.kurz)}</span> `
        + `${esc(st.label)}</td></tr>${zeilenA}${koord(lat, lon)}`
        + `${leer(p.alt_atlas_id) ? "" : aendernLink("RP-" + p.alt_atlas_id, "Eintrag ändern")}</table></div>`;
      const kreis = { radius: 5, renderer: svgRenderer };
      const ziel = STAETTE[p.naechste_sportstaette_id];
      const pfeilHinweis = p.status === "nah" && ziel
        ? `<div class="hinweis">Klicken zeigt einen Pfeil zur nächsten ALKIS-Sportstätte</div>` : "";
      const basis = info(L.circleMarker([lat, lon], { ...kreis, color: st.color, weight: 1.5,
        fillColor: st.fillColor, fillOpacity: 0.85, dashArray: p.status === "nah" ? "2 2" : null }),
        tip.replace(/<\/div>$/, pfeilHinweis + "</div>"));
      if (p.status === "nah" && ziel) basis.on("click", () => zeigePfeil([lat, lon], ziel));
      const muster = L.circleMarker([lat, lon], { ...kreis, stroke: false, fill: true,
        fillColor: `url(#${SCHRAFFUR_ID[p.status] || SCHRAFFUR_ID["nicht in ALKIS"]})`,
        fillOpacity: 1, interactive: false });
      atlasPunkte.push({ status: p.status, ars: p.ars, layer: L.layerGroup([basis, muster]) });
    }

    // Nur Ebenen hinzufügen/entfernen, die sich ändern. Ein Neuaufbau würde offene Popups
    // schließen, z. B. wenn die Karte nach einem Klick zum Pfeil schwenkt.
    let aktuell = new Set();
    aktualisiere = () => {
      const nah = karte.getZoom() >= ZOOM_FLAECHEN;
      if (nah) staetten.addTo(ebene); else ebene.removeLayer(staetten);
      const b = karte.getBounds().pad(0.3);
      const [bw, bs, bo, bn] = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
      const imBild = e => !e.bbox || (e.bbox[0] <= bo && e.bbox[2] >= bw
                                      && e.bbox[1] <= bn && e.bbox[3] >= bs);
      const soll = new Set();
      for (const g of Object.values(gruppen)) {
        if (!g.an) continue;
        for (const e of (nah ? g.flaechen : g.punkte)) {
          if (stufeAn[e.stufe] !== false && imGebiet(e.ars) && (!nah || imBild(e))) soll.add(e.layer);
        }
      }
      for (const e of atlasPunkte) if (atlasAn[e.status] && imGebiet(e.ars)) soll.add(e.layer);
      for (const l of aktuell) if (!soll.has(l)) sichtbar.removeLayer(l);
      for (const l of soll) if (!aktuell.has(l)) sichtbar.addLayer(l);
      aktuell = soll;
    };

    // Legende: Typgruppen und – falls angereichert – Verifikationsstufen
    legende = L.control({ position: "topright" });
    legende.onAdd = () => {
      const div = L.DomUtil.create("div", "panel filter");
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);
      const namen = Object.keys(gruppen).sort((a, b) => gruppen[b].n - gruppen[a].n);
      const zaehl = {};
      for (const f of ANLAGEN.features) {
        const s = stufeVon(f.properties);
        if (s) zaehl[s] = (zaehl[s] || 0) + 1;
      }
      let h = `<h1>ALKIS: ${zahl(STAETTEN.features.length)} Sportstätten · ${zahl(ANLAGEN.features.length)} Anlagen</h1>`
        + namen.map(n => `<label><input type="checkbox" data-g="${esc(n)}" checked>`
          + `<span class="swatch" style="border-radius:3px;background:${FARBEN[n] || "#D85A30"}"></span>`
          + `${esc(n)}<span class="n">${zahl(gruppen[n].n)}</span></label>`).join("");
      const za = {};
      for (const e of atlasPunkte) za[e.status] = (za[e.status] || 0) + 1;
      if (Object.keys(zaehl).length || atlasPunkte.length) {
        h += `<h2>Verifikation</h2>` + LEGENDE_STUFEN.filter(s => zaehl[s]).map(s =>
          `<label><input type="checkbox" data-s="${esc(s)}" checked>`
          + `<span class="schraffur" style="${schraffurCss(s)}"></span>`
          + `<span class="verif stufe-${STUFEN.indexOf(s)}">${esc(s)}</span>`
          + `<span class="n">${zahl(zaehl[s])}</span></label>`).join("")
          + Object.keys(ATLAS_STIL).filter(k => za[k]).map(k =>
            `<label title="${esc(ATLAS_STIL[k].label)}"><input type="checkbox" data-a="${esc(k)}" checked>`
            + `<span class="swatch" style="background-color:${ATLAS_STIL[k].fillColor};`
            + `${schraffurCss(k)};width:14px;height:14px;border:2px solid ${ATLAS_STIL[k].color};`
            + `box-sizing:border-box"></span>`
            + `<span class="verif" style="background:${ATLAS_STIL[k].fillColor};`
            + `color:${ATLAS_STIL[k].color}">${esc(ATLAS_STIL[k].kurz)}</span>`
            + `<span class="n">${zahl(za[k])}</span></label>`).join("");
      }
      h += `<hr><span style="color:#666">Füllfarbe = Klasse, Schraffur = Verifikation `
        + `(ab Zoom ${ZOOM_FLAECHEN})<br>gestrichelt = zu prüfen`
        + (atlasPunkte.length ? `<br>rote/orange Kreise = nur im Sportstättenatlas RLP` : "")
        + `<br>ab Zoom ${ZOOM_FLAECHEN}: Umrisse und Sportstätten-Flächen</span>`;
      div.innerHTML = h;
      div.querySelectorAll("input[data-g]").forEach(cb => cb.addEventListener("change", () => {
        gruppen[cb.dataset.g].an = cb.checked; aktualisiere();
      }));
      div.querySelectorAll("input[data-s]").forEach(cb => cb.addEventListener("change", () => {
        stufeAn[cb.dataset.s] = cb.checked; aktualisiere();
      }));
      div.querySelectorAll("input[data-a]").forEach(cb => cb.addEventListener("change", () => {
        atlasAn[cb.dataset.a] = cb.checked; aktualisiere();
      }));
      return div;
    };

    for (const f of STAETTEN.features) {
      const p = f.properties;
      const titel = !leer(p.name) ? p.name : (p.typ || "Sportstätte");
      such.push({ titel, sub: [p.sportstaette_id, p.typ, leer(p.adresse) ? "" : p.adresse]
        .filter(Boolean).join(" · "), text: [p.name, p.adresse, p.sportstaette_id, p.typ,
        p.anlagentypen, p.betreiber, p.alt_name, p.alt_adresse, p.alt_typ, p.alt_atlas_id]
        .filter(v => !leer(v)).join(" ").toLowerCase(), ars: p.ars,
        grenzen: () => L.geoJSON(f).getBounds() });
    }
    for (const f of ATLAS.features) {
      const p = f.properties, [lon, lat] = f.geometry.coordinates;
      such.push({ titel: p.alt_name || "Atlas-Eintrag", sub: ["Sportstättenatlas RLP",
        p.alt_typ, p.alt_adresse].filter(v => !leer(v)).join(" · "), ars: p.ars,
        text: [p.alt_name, p.alt_adresse, p.alt_typ, p.alt_atlas_id, p.alt_id]
          .filter(v => !leer(v)).join(" ").toLowerCase(),
        grenzen: () => L.latLngBounds([[lat, lon], [lat, lon]]) });
    }
    const alle = L.geoJSON(ANLAGEN);
    if (alle.getLayers().length) startGrenzen = alle.getBounds();
  }
  let erstmals = true;
  return {
    titel: "Verifikation (ALKIS)",
    starte,
    zeigen() {
      ebene.addTo(karte); legende.addTo(karte);
      if (erstmals && !GEBIET && startGrenzen && !ANSICHTEN.bestand) {
        karte.fitBounds(startGrenzen, { padding: [20, 20] });
      }
      erstmals = false;
      aktualisiere();
    },
    verbergen() { karte.removeLayer(ebene); legende.remove(); },
    aktualisiere: () => aktualisiere(),
    gebietGeaendert: () => aktualisiere(),
    suchindex: () => such,
  };
}

// ---------- Ansicht „Vorschlag“: Sportstätte neu eintragen oder ändern ------------------
// Das Formular prüft auf Doppelungen und übergibt die Werte als URL-Parameter an die
// LimeSurvey-Umfrage (konfig.js: vorschlag_url). Dort wird der Vorschlag abgeschickt.
// Parameternamen = Fragecodes in LimeSurvey. Ist in konfig.js vorschlag_felder gesetzt,
// werden nur die dort genannten Felder übertragen ({ name: "Q00", lage: "G01Q04" }),
// sonst alle mit den Vorgabe-Codes unten.
const VORSCHLAG_FELDER = KONFIG.vorschlag_felder && Object.keys(KONFIG.vorschlag_felder).length
  ? KONFIG.vorschlag_felder : {
  art: "art", id: "id", quelle: "quelle", name: "name", kategorie: "kategorie",
  betriebsstatus: "status", strasse: "strasse", hausnummer: "hausnr", adresszusatz: "zusatz",
  plz: "plz", ort: "ort", ars: "ars", gemeinde: "gemeinde", lat: "lat", lon: "lon",
  oeffentlicher_zugang: "oeffentlich", schulsport: "schulsport", zuschauerplaetze: "zuschauer",
  sportarten: "sportarten", anlagen: "anlagen", eigentuemer: "eigentuemer",
  betreiber: "betreiber", website: "website", anmerkung: "anmerkung", geaendert: "geaendert",
  dubletten: "dubletten",
};
const FELD_TEXT = {
  name: "Name", kategorie: "Kategorie", betriebsstatus: "Betriebsstatus", strasse: "Straße",
  hausnummer: "Hausnummer", adresszusatz: "Adresszusatz", plz: "PLZ", ort: "Ort",
  lage: "Lage", oeffentlicher_zugang: "Öffentlicher Zugang", schulsport: "Schulsport",
  zuschauerplaetze: "Zuschauerplätze", sportarten: "Sportarten", anlagen: "Sportanlagen",
  eigentuemer: "Eigentümer", betreiber: "Betreiber", website: "Website",
};
const STATUS_WERTE = ["in Betrieb", "vorübergehend geschlossen", "außer Betrieb", "in Planung",
  "im Bau"];
// ALKIS-Typgruppe → Kategorie des Atlas (nur Vorbelegung, im Formular änderbar)
const GRUPPE_KATEGORIE = { halle: "Sporthalle", spielfeld: "Sportplatz",
  becken: "Schwimmsportstätte", leichtathletik: "Sportplatz" };

function normName(s) {
  return String(s || "").toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe")
    .replace(/ü/g, "ue").replace(/ß/g, "ss").replace(/[^a-z0-9]+/g, " ").trim();
}
function bigramme(s) {
  const t = ` ${normName(s)} `, out = new Map();
  for (let i = 0; i < t.length - 1; i++) {
    const b = t.slice(i, i + 2); out.set(b, (out.get(b) || 0) + 1);
  }
  return out;
}
// Ähnlichkeit zweier Namen (Dice-Koeffizient der Buchstabenpaare, 0 … 1)
function aehnlich(a, b) {
  if (!normName(a) || !normName(b)) return 0;
  const x = bigramme(a), y = bigramme(b);
  let gemeinsam = 0, n = 0;
  for (const [k, v] of x) { n += v; gemeinsam += Math.min(v, y.get(k) || 0); }
  for (const v of y.values()) n += v;
  return n ? 2 * gemeinsam / n : 0;
}
function abstand(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180, dlat = (lat2 - lat1) * r, dlon = (lon2 - lon1) * r;
  const h = Math.sin(dlat / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dlon / 2) ** 2;
  return 12742000 * Math.asin(Math.sqrt(h));
}
function imRing(x, y, ring) {
  let drin = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) drin = !drin;
  }
  return drin;
}
function punktIn(lon, lat, g) {
  const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
  return polys.some(p => p.length && imRing(lon, lat, p[0]) && !p.slice(1).some(l => imRing(lon, lat, l)));
}
// Name, unter dem eine Kommune als Eigentümer/Betreiber erscheint: "Ortsgemeinde X", "Stadt Y"
function kommunenName(g) {
  const bez = g.b === "Kreisfreie Stadt" ? "Stadt" : g.b === "Verbandsfreie Gemeinde" ? "Gemeinde" : g.b;
  if (!bez) return g.n;
  return g.n.toLowerCase().startsWith(bez.toLowerCase()) ? g.n : `${bez} ${g.n}`;
}
function zerlegeAdresse(text) {
  // "Musterstraße 12a, 56068 Koblenz" → Teile; sonst alles als Straße
  const m = /^\s*(.*?)(?:\s+(\d+\s?[a-zA-Z]?(?:\s?[-–]\s?\d+[a-zA-Z]?)?))?\s*,\s*(\d{5})\s+(.+?)\s*$/.exec(text || "");
  if (!m) return { strasse: text || "" };
  return { strasse: m[1] || "", hausnummer: m[2] || "", plz: m[3], ort: m[4] };
}

function ansichtVorschlag(bestand) {
  const el = document.getElementById("seite-vorschlag");
  const NACH_ID = new Map(bestand.eintraege.map(e => [e.p.id, e]));
  let form, vkarte = null, marke = null, nachbarn = null, original = null, quelle = "";
  let lage = null, ars = "", pruefen = 0, dubletten = [];
  const F = n => form.elements.namedItem(n);

  // Auswahllisten aus dem Datenbestand und den Gebieten
  function haeufig(werte) {
    const z = new Map();
    for (const w of werte) if (!leer(w)) {
      const k = schluesselName(w), x = z.get(k) || { n: 0, namen: new Map() };
      x.n++; x.namen.set(w.trim(), (x.namen.get(w.trim()) || 0) + 1); z.set(k, x);
    }
    return [...z.values()].map(x => [[...x.namen].sort((a, b) => b[1] - a[1])[0][0], x.n]);
  }
  const KATEGORIEN = haeufig(bestand.eintraege.map(e => e.p.kategorie)).sort((a, b) => b[1] - a[1]).map(x => x[0]);
  const SPORTARTEN = haeufig(bestand.eintraege.flatMap(e => e.p.sportarten || [])).map(x => x[0])
    .sort((a, b) => a.localeCompare(b, "de"));
  const ANLAGEN = haeufig(bestand.eintraege.flatMap(e => e.p.anlagen || [])).map(x => x[0])
    .sort((a, b) => a.localeCompare(b, "de"));
  const STATUS = [...new Set([...STATUS_WERTE, ...bestand.eintraege.map(e => e.p.betriebsstatus).filter(v => !leer(v))])];
  function organisationen() {
    const bisher = haeufig(bestand.eintraege.flatMap(e => [e.p.betreiber, e.p.eigentuemer]))
      .sort((a, b) => b[1] - a[1]).map(x => x[0]);
    const kommunen = GEBIETE.map(kommunenName);
    return [...new Map([...bisher, ...kommunen].map(n => [schluesselName(n), n])).values()];
  }
  const ORTE = () => [...new Set([...GEBIETE.filter(g => g.e === "gemeinde").map(g => g.n),
    ...bestand.eintraege.map(e => e.p.ort).filter(v => !leer(v))])].sort((a, b) => a.localeCompare(b, "de"));
  const optionen = liste => liste.map(v => `<option value="${esc(v)}"></option>`).join("");
  const auswahl = (name, werte, leerText = "– bitte wählen –") => `<select name="${name}">`
    + `<option value="">${leerText}</option>` + werte.map(v => `<option>${esc(v)}</option>`).join("") + `</select>`;
  const jaNein = name => `<span class="radios">` + [["ja", "Ja"], ["nein", "Nein"], ["", "Nicht bekannt"]]
    .map(([w, t]) => `<label><input type="radio" name="${name}" value="${w}"${w ? "" : " checked"}> ${t}</label>`).join("") + `</span>`;
  const feld = (label, inhalt, extra = "") => `<label class="feld${extra}"><span>${label}</span>${inhalt}</label>`;

  function baue() {
    el.innerHTML = `<div class="inhalt vorschlag"><h2>Vorschlag machen</h2>
      <p class="unter">Neue Sportstätte eintragen oder eine bestehende ändern. Im nächsten Schritt
      werden die Angaben an die Umfrage übergeben und dort abgeschickt; nach einer Prüfung erscheinen
      sie auf der Karte. Bitte keine personenbezogenen Daten (Namen, private Telefonnummern) eintragen.</p>
      <div class="raster"><form id="v-form" novalidate autocomplete="off">
      <fieldset><legend>Was möchten Sie tun?</legend>
        <span class="radios gross"><label><input type="radio" name="art" value="neu" checked> Neue Sportstätte vorschlagen</label>
        <label><input type="radio" name="art" value="aenderung"> Bestehende Sportstätte ändern</label></span>
        <div id="v-auswahl" hidden><input type="search" id="v-suche" placeholder="Name, Ort oder ID der Sportstätte suchen"
          aria-label="Sportstätte suchen"><ul id="v-treffer" class="treffer"></ul></div>
        <div id="v-gewaehlt"></div>
      </fieldset>
      <fieldset><legend>Sportstätte</legend>
        ${feld("Name *", `<input name="name" required maxlength="200">`)}
        <div class="zwei">${feld("Sportstättenkategorie *", auswahl("kategorie", KATEGORIEN))}
        ${feld("Betriebsstatus", auswahl("betriebsstatus", STATUS, "nicht bekannt"))}</div>
      </fieldset>
      <fieldset><legend>Adresse und Lage</legend>
        <div class="zwei breit-links">${feld("Straße", `<input name="strasse">`)}${feld("Hausnummer", `<input name="hausnummer" maxlength="12">`)}</div>
        ${feld("Adresszusatz", `<input name="adresszusatz" placeholder="z. B. Eingang Schulhof">`)}
        <div class="zwei schmal-links">${feld("PLZ", `<input name="plz" inputmode="numeric" maxlength="5" pattern="[0-9]{5}">`)}
        ${feld("Ort", `<input name="ort" list="v-orte">`)}</div>
        <div class="lage"><b>Lage *</b> <span id="v-lage">Bitte in der Karte rechts auf die Sportstätte klicken.</span>
          <button type="button" class="knopf2" id="v-geocode">Lage aus der Adresse suchen</button>
          <div id="v-gemeinde" class="hinweis"></div></div>
      </fieldset>
      <fieldset><legend>Nutzung</legend>
        <div class="zeile-feld"><span>Öffentlicher Zugang</span>${jaNein("oeffentlicher_zugang")}</div>
        <div class="zeile-feld"><span>Schulsport</span>${jaNein("schulsport")}</div>
        ${feld("Zuschauerplätze gesamt", `<input name="zuschauerplaetze" type="number" min="0" step="1">`, " klein")}
      </fieldset>
      <fieldset><legend>Sportarten</legend>
        <div id="v-sportarten" class="chips"></div>
        <div class="hinzu"><input id="v-sportart" list="v-sportarten-liste" placeholder="Sportart eingeben oder auswählen"
          aria-label="Sportart"><button type="button" class="knopf2" id="v-sportart-dazu">Hinzufügen</button></div>
      </fieldset>
      <fieldset><legend>Sportanlagen</legend>
        <p class="hinweis">Einzelne Anlagen der Sportstätte, z. B. Großspielfeld, Laufbahn, Hallenteil.</p>
        <table class="anlagen"><thead><tr><th>Bezeichnung</th><th>Anzahl</th><th></th></tr></thead><tbody id="v-anlagen"></tbody></table>
        <button type="button" class="knopf2" id="v-anlage-dazu">+ Anlage hinzufügen</button>
      </fieldset>
      <fieldset><legend>Eigentümer und Betreiber</legend>
        <p class="hinweis">Auswahl aus den bisherigen Eigentümern und Betreibern sowie allen Kommunen; neue Namen können eingetippt werden.</p>
        ${feld("Eigentümer", `<input name="eigentuemer" list="v-orgs"><span class="art" id="v-art-eigentuemer"></span>`)}
        ${feld("Betreiber", `<input name="betreiber" list="v-orgs"><span class="art" id="v-art-betreiber"></span>`)}
        ${feld("Webseite", `<input name="website" type="url" placeholder="https://">`)}
      </fieldset>
      <fieldset><legend>Anmerkung</legend>
        <textarea name="anmerkung" rows="3" maxlength="1000" placeholder="Was soll geändert werden, Quelle der Angaben …"></textarea>
      </fieldset>
      <div id="v-fehler" class="fehlerbox" hidden></div>
      <div class="weiter"><button type="submit" class="knopf-gross">Weiter zu LimeSurvey →</button>
        <button type="button" class="knopf2" id="v-leeren">Formular leeren</button></div>
      <div id="v-ausgabe"></div>
      </form>
      <aside><div id="v-karte" aria-label="Karte zur Lage"></div>
        <div class="hinweis">Klick in die Karte setzt die Lage, die Markierung lässt sich verschieben. Graue Punkte: vorhandene Sportstätten.</div>
        <div id="v-aenderungen"></div><div id="v-dubletten"></div></aside></div>
      <datalist id="v-orte">${optionen(ORTE())}</datalist>
      <datalist id="v-orgs">${optionen(organisationen())}</datalist>
      <datalist id="v-sportarten-liste">${optionen(SPORTARTEN)}</datalist>
      <datalist id="v-anlagen-liste">${optionen(ANLAGEN)}</datalist></div>`;
    form = el.querySelector("#v-form");
    form.addEventListener("input", () => { zeigeArten(); planePruefung(); });
    form.addEventListener("change", ev => {
      if (ev.target.name === "art") { const aend = F("art").value === "aenderung";
        el.querySelector("#v-auswahl").hidden = !aend || !!original;
        if (!aend) neu(); }
      planePruefung();
    });
    form.addEventListener("submit", ev => { ev.preventDefault(); weiter(); });
    el.querySelector("#v-leeren").addEventListener("click", () => neu());
    el.querySelector("#v-geocode").addEventListener("click", lageAusAdresse);
    const sp = el.querySelector("#v-sportart");
    const dazu = () => { const v = sp.value.trim(); if (v) { sportarten.add(v); sp.value = ""; zeigeSportarten(); planePruefung(); } };
    el.querySelector("#v-sportart-dazu").addEventListener("click", dazu);
    sp.addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); dazu(); } });
    el.querySelector("#v-anlage-dazu").addEventListener("click", () => { anlageZeile("", 1); planePruefung(); });
    const suche = el.querySelector("#v-suche"), treffer = el.querySelector("#v-treffer");
    suche.addEventListener("input", () => {
      const worte = normName(suche.value).split(" ").filter(Boolean);
      if (!worte.length) { treffer.innerHTML = ""; return; }
      const t = [];
      for (const e of bestand.eintraege) {
        const text = normName([e.p.name, e.p.ort, e.p.adresse, e.p.id].join(" "));
        if (worte.every(w => text.includes(w))) t.push(e);
        if (t.length >= 8) break;
      }
      treffer.innerHTML = t.map(e => `<li data-id="${esc(e.p.id)}">${esc(e.p.name || e.kat)}`
        + `<small>${esc([e.p.kategorie, e.p.adresse].filter(v => !leer(v)).join(" · "))}</small></li>`).join("")
        || `<li class="gruppe">Keine Sportstätte gefunden</li>`;
    });
    treffer.addEventListener("click", ev => {
      const li = ev.target.closest("li[data-id]");
      if (li) bearbeite(li.dataset.id);
    });
  }

  const sportarten = new Set();
  function zeigeSportarten() {
    const c = el.querySelector("#v-sportarten");
    c.innerHTML = [...sportarten].map(s => `<span class="chip-s">${esc(s)}<button type="button" `
      + `data-weg="${esc(s)}" aria-label="${esc(s)} entfernen">×</button></span>`).join("")
      || `<span class="hinweis">noch keine</span>`;
    c.querySelectorAll("[data-weg]").forEach(b => b.addEventListener("click", () => {
      sportarten.delete(b.dataset.weg); zeigeSportarten(); planePruefung(); }));
  }
  function anlageZeile(name, anzahl) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td><input list="v-anlagen-liste" value="${esc(name)}" aria-label="Bezeichnung"></td>`
      + `<td><input type="number" min="1" step="1" value="${anzahl}" aria-label="Anzahl"></td>`
      + `<td><button type="button" class="weg" aria-label="Anlage entfernen">×</button></td>`;
    tr.querySelector(".weg").addEventListener("click", () => { tr.remove(); planePruefung(); });
    el.querySelector("#v-anlagen").appendChild(tr);
  }
  function anlagenListe() {
    const z = new Map();
    for (const tr of el.querySelectorAll("#v-anlagen tr")) {
      const [a, n] = tr.querySelectorAll("input"), name = a.value.trim();
      if (name) z.set(name, (z.get(name) || 0) + Math.max(1, parseInt(n.value, 10) || 1));
    }
    return [...z].map(([a, n]) => (n > 1 ? `${n}× ` : "") + a);
  }
  function zeigeArten() {
    for (const r of ["eigentuemer", "betreiber"]) {
      const a = betreiberArt(F(r).value);
      el.querySelector("#v-art-" + r).textContent = a || "";
      el.querySelector("#v-art-" + r).hidden = !a;
    }
  }
  // dieselbe Schätzung wie in bestand.py (betreiber_art), vereinfacht
  function betreiberArt(n) {
    n = (n || "").trim();
    if (!n) return "";
    if (/e\.\s?v\b|\bev\b|verein|sport(gemeinde|gemeinschaft|freunde)|\b(tus|tsv|sv|fc|sc|sg|vfl|vfb|vfr|tv|tc|tsg|jsg|spvgg|fsv|ssv|djk|dlrg)\b|club|klub|schützen|gilde/i.test(n)) return "Verein";
    if (/gemeinde|\bstadt\b|städtisch|landkreis|kreisverwaltung|\bkreis\b|kommun|stadtwerk|zweckverband/i.test(n)) return "Kommune";
    return "sonstige";
  }

  // --- Karte im Formular ---
  function starteKarte() {
    if (vkarte) { vkarte.invalidateSize(); return; }
    vkarte = L.map("v-karte", { preferCanvas: true, maxZoom: 19 });
    L.tileLayer(BASEMAP, { layer: "de_basemapde_web_raster_farbe", maxNativeZoom: 18, maxZoom: 19,
      attribution: BKG }).addTo(vkarte);
    vkarte.fitBounds(karte.getBounds());
    nachbarn = L.layerGroup().addTo(vkarte);
    for (const e of bestand.eintraege) {
      L.circleMarker([e.lat, e.lon], { radius: 4, weight: 1, color: "#fff", fillColor: "#7a7975",
        fillOpacity: 0.9 }).bindTooltip(esc(e.p.name || e.kat)).bindPopup(() =>
        `<b>${esc(e.p.name || e.kat)}</b><br>${esc(e.p.kategorie || "")}<br>${esc(e.p.adresse || "")}`
        + `<br><a href="#" data-bearbeiten="${esc(e.p.id)}">Diese Sportstätte ändern</a>`).addTo(nachbarn);
    }
    vkarte.on("click", ev => setzeLage(ev.latlng.lat, ev.latlng.lng));
  }
  function setzeLage(lat, lon, zoomen = false) {
    lage = lat == null ? null : [+lat, +lon];
    if (marke) { marke.remove(); marke = null; }
    const t = el.querySelector("#v-lage");
    if (!lage) { t.textContent = "Bitte in der Karte rechts auf die Sportstätte klicken."; ars = "";
      el.querySelector("#v-gemeinde").textContent = ""; planePruefung(); return; }
    t.innerHTML = `<span class="koord">${lage[0].toFixed(6)}, ${lage[1].toFixed(6)}</span>`;
    if (vkarte) {
      marke = L.marker(lage, { draggable: true, keyboard: false, icon: L.divIcon({ className: "",
        iconSize: [26, 34], iconAnchor: [13, 32], html: `<div class="nadel"></div>` }) }).addTo(vkarte);
      marke.on("dragend", () => { const p = marke.getLatLng(); setzeLage(p.lat, p.lng); });
      if (zoomen) vkarte.setView(lage, Math.max(vkarte.getZoom(), 17));
    }
    bestimmeGemeinde();
    planePruefung();
  }
  async function bestimmeGemeinde() {
    const ziel = el.querySelector("#v-gemeinde");
    ars = "";
    if (!lage || !GEBIETE.length) { ziel.textContent = ""; return; }
    const fc = await ladeUmrisse("gemeinde"), [lat, lon] = lage;
    if (!fc || !lage || lage[0] !== lat) return;
    const f = fc.features.find(x => x.geometry && punktIn(lon, lat, x.geometry));
    const g = f && NACH_S[f.properties.s];
    ars = g ? g.s : "";
    ziel.textContent = g ? `Gemeinde: ${gebietTitel(g)}` : "Liegt außerhalb von Rheinland-Pfalz?";
    if (g && !F("ort").value.trim()) F("ort").value = g.n;
  }
  async function lageAusAdresse() {
    const q = [F("strasse").value + " " + F("hausnummer").value, F("plz").value + " " + F("ort").value]
      .map(s => s.trim()).filter(Boolean).join(", ");
    const b = el.querySelector("#v-geocode");
    if (!q) { zeigeFehlerliste(["Für die Suche bitte Straße und Ort eintragen."]); return; }
    b.disabled = true; b.textContent = "suche …";
    try {
      const t = await geocode(q);
      if (t.length) { const c = t[0].grenzen().getCenter(); setzeLage(c.lat, c.lng, true); }
      else zeigeFehlerliste(["Adresse nicht gefunden – bitte die Lage in der Karte setzen."]);
    } catch (_) { zeigeFehlerliste(["Adresssuche gerade nicht erreichbar – bitte die Lage in der Karte setzen."]); }
    b.disabled = false; b.textContent = "Lage aus der Adresse suchen";
  }

  // --- Werte lesen und setzen ---
  function werte() {
    const t = n => (F(n).value || "").trim();
    return {
      art: F("art").value, id: original ? original.p.id : "", quelle, name: t("name"), kategorie: t("kategorie"),
      betriebsstatus: t("betriebsstatus"), strasse: t("strasse"), hausnummer: t("hausnummer"),
      adresszusatz: t("adresszusatz"), plz: t("plz"), ort: t("ort"), ars,
      gemeinde: ars && NACH_S[ars] ? NACH_S[ars].n : "",
      lat: lage ? lage[0].toFixed(6) : "", lon: lage ? lage[1].toFixed(6) : "",
      oeffentlicher_zugang: F("oeffentlicher_zugang").value, schulsport: F("schulsport").value,
      zuschauerplaetze: t("zuschauerplaetze"), sportarten: [...sportarten], anlagen: anlagenListe(),
      eigentuemer: t("eigentuemer"), betreiber: t("betreiber"), website: t("website"),
      anmerkung: t("anmerkung"),
    };
  }
  function fuelle(v) {
    for (const n of ["name", "betriebsstatus", "strasse", "hausnummer", "adresszusatz", "plz", "ort",
      "zuschauerplaetze", "eigentuemer", "betreiber", "website", "anmerkung"]) F(n).value = v[n] ?? "";
    const k = F("kategorie");
    if (v.kategorie && ![...k.options].some(o => o.value === v.kategorie)) k.add(new Option(v.kategorie));
    k.value = v.kategorie || "";
    if (v.betriebsstatus && ![...F("betriebsstatus").options].some(o => o.value === v.betriebsstatus)) {
      F("betriebsstatus").add(new Option(v.betriebsstatus)); F("betriebsstatus").value = v.betriebsstatus;
    }
    for (const r of ["oeffentlicher_zugang", "schulsport"]) {
      const w = v[r] === "ja" || v[r] === "nein" ? v[r] : "";
      form.querySelectorAll(`input[name=${r}]`).forEach(i => { i.checked = i.value === w; });
    }
    sportarten.clear(); (v.sportarten || []).forEach(s => sportarten.add(s)); zeigeSportarten();
    el.querySelector("#v-anlagen").innerHTML = "";
    const z = new Map();
    for (const a of v.anlagen || []) z.set(a, (z.get(a) || 0) + 1);
    for (const [a, n] of z) anlageZeile(a, n);
    setzeLage(v.lat, v.lon, true);
    zeigeArten();
  }
  function ausEintrag(e) {
    const p = e.p;
    return { name: p.name, kategorie: p.kategorie, betriebsstatus: p.betriebsstatus, strasse: p.strasse,
      hausnummer: p.hausnummer, plz: p.plz, ort: p.ort, zuschauerplaetze: p.zuschauerplaetze,
      eigentuemer: p.eigentuemer, betreiber: p.betreiber, website: p.website,
      oeffentlicher_zugang: p.oeffentlicher_zugang, schulsport: p.schulsport,
      sportarten: p.sportarten || [], anlagen: p.anlagen || [], lat: e.lat, lon: e.lon };
  }
  function zeigeGewaehlt() {
    const g = el.querySelector("#v-gewaehlt");
    g.innerHTML = original ? `<div class="chip">Sie ändern: <b>${esc(original.p.name || original.kat)}</b> `
      + `<span class="q">${esc(original.p.id)}</span> <button type="button">andere wählen</button></div>` : "";
    const b = g.querySelector("button");
    if (b) b.addEventListener("click", () => { original = null; zeigeGewaehlt();
      el.querySelector("#v-auswahl").hidden = false; el.querySelector("#v-suche").focus(); planePruefung(); });
    el.querySelector("#v-auswahl").hidden = !(F("art").value === "aenderung" && !original);
  }
  function neu(vorgabe = {}, herkunft = "") {
    original = null; quelle = herkunft;
    form.reset();
    F("art").value = "neu";
    fuelle(vorgabe);
    zeigeGewaehlt();
    el.querySelector("#v-ausgabe").innerHTML = "";
    el.querySelector("#v-fehler").hidden = true;
  }
  function bearbeite(id) {
    const e = NACH_ID.get(id);
    if (!e) return;
    original = e; quelle = "";
    if (vkarte) vkarte.closePopup();
    form.reset();
    F("art").value = "aenderung";
    fuelle(ausEintrag(e));
    zeigeGewaehlt();
    el.querySelector("#v-ausgabe").innerHTML = "";
    el.querySelector("#v-fehler").hidden = true;
  }

  // --- Prüfungen ---
  function planePruefung() { clearTimeout(pruefen); pruefen = setTimeout(pruefe, 250); }
  function pruefe() {
    if (!form) return;
    const v = werte();
    dubletten = sucheDubletten(v);
    const box = el.querySelector("#v-dubletten");
    if (!dubletten.length) {
      box.innerHTML = v.name || lage ? `<div class="ok">✓ Keine ähnliche Sportstätte in der Nähe gefunden.</div>` : "";
    } else {
      box.innerHTML = `<div class="warnung"><b>Mögliche Doppelung</b> – ist die Sportstätte schon eingetragen?<ul>`
        + dubletten.map(d => `<li><b>${esc(d.e.p.name || d.e.kat)}</b> <span class="q">${esc(d.e.p.kategorie || "")}`
          + `${d.e.p.adresse ? " · " + esc(d.e.p.adresse) : ""}</span><br><span class="grund">${d.gruende.map(esc).join(" · ")}</span>`
          + `<br><a href="#" data-zeige="${esc(d.e.p.id)}">auf der Karte</a> · `
          + `<a href="#" data-bearbeiten="${esc(d.e.p.id)}">stattdessen diese ändern</a></li>`).join("")
        + `</ul>${v.art === "neu" ? `<label class="bestaetigen"><input type="checkbox" id="v-keine-doppelung"`
          + `${box.dataset.bestaetigt === "1" ? " checked" : ""}> Ich habe geprüft: Es ist eine andere Sportstätte.</label>` : ""}</div>`;
      const cb = box.querySelector("#v-keine-doppelung");
      if (cb) cb.addEventListener("change", () => { box.dataset.bestaetigt = cb.checked ? "1" : ""; });
      box.querySelectorAll("[data-zeige]").forEach(a => a.addEventListener("click", ev => {
        ev.preventDefault(); const e = NACH_ID.get(a.dataset.zeige);
        if (vkarte && e) vkarte.setView([e.lat, e.lon], 18); }));
    }
    zeigeAenderungen(v);
  }
  function sucheDubletten(v) {
    const out = [];
    // Beim Ändern nur prüfen, wenn Name oder Lage geändert wurden
    if (original && !aenderungen(v).some(([k]) => k === "name" || k === "lage")) return out;
    const adresse = normName(`${v.strasse} ${v.hausnummer}`);
    for (const e of bestand.eintraege) {
      if (original && e === original) continue;
      const g = [];
      let punkte = 0;
      const d = lage ? abstand(lage[0], lage[1], e.lat, e.lon) : null;
      const sim = aehnlich(v.name, e.p.name);
      const gleicheKat = v.kategorie && v.kategorie === e.p.kategorie;
      if (d !== null && d <= 60) { g.push(`nur ${Math.round(d)} m entfernt`); punkte += 3; }
      else if (d !== null && d <= 250 && gleicheKat) { g.push(`gleiche Kategorie, ${Math.round(d)} m entfernt`); punkte += 2; }
      const nahGenug = d === null ? (v.ort && normName(v.ort) === normName(e.p.ort)) || (v.plz && v.plz === e.p.plz) : d <= 3000;
      if (sim >= 0.8 && nahGenug) { g.push(sim >= 0.99 ? "gleicher Name" : "sehr ähnlicher Name"); punkte += 2; }
      if (adresse && v.hausnummer && adresse === normName(`${e.p.strasse || ""} ${e.p.hausnummer || ""}`)
          && (!v.plz || v.plz === e.p.plz)) { g.push("gleiche Adresse"); punkte += 2; }
      if (punkte) out.push({ e, gruende: g, punkte, d: d ?? 1e9 });
    }
    return out.sort((a, b) => b.punkte - a.punkte || a.d - b.d).slice(0, 6);
  }
  function aenderungen(v) {
    if (!original) return [];
    const alt = ausEintrag(original), out = [];
    const text = x => Array.isArray(x) ? x.join(", ") : (x == null ? "" : String(x));
    for (const k of Object.keys(FELD_TEXT)) {
      if (k === "lage") {
        const d = lage ? abstand(lage[0], lage[1], alt.lat, alt.lon) : 0;
        if (d > 5) out.push([k, "", `um ${Math.round(d)} m verschoben`]);
        continue;
      }
      const a = k === "anlagen" ? (() => { const z = new Map(); for (const x of alt.anlagen) z.set(x, (z.get(x) || 0) + 1);
        return [...z].map(([x, n]) => (n > 1 ? `${n}× ` : "") + x); })() : alt[k];
      const n = v[k];
      const ta = Array.isArray(a) ? [...a].sort().join(", ") : text(a), tn = Array.isArray(n) ? [...n].sort().join(", ") : text(n);
      if (ta.trim() !== tn.trim()) out.push([k, ta, tn]);
    }
    return out;
  }
  function zeigeAenderungen(v) {
    const box = el.querySelector("#v-aenderungen");
    if (!original) { box.innerHTML = ""; return; }
    const a = aenderungen(v);
    box.innerHTML = `<div class="aenderungen"><b>Ihre Änderungen</b>` + (a.length
      ? `<table class="meta">` + a.map(([k, alt, n]) => `<tr><td>${FELD_TEXT[k]}</td><td>`
        + (alt ? `<s>${esc(alt)}</s> → ` : "") + `${esc(n || "(leer)")}</td></tr>`).join("") + `</table>`
      : `<div class="hinweis">noch keine</div>`) + `</div>`;
  }
  function zeigeFehlerliste(liste) {
    const box = el.querySelector("#v-fehler");
    box.hidden = !liste.length;
    box.innerHTML = liste.length ? "<b>Bitte noch ergänzen:</b><ul>" + liste.map(f => `<li>${esc(f)}</li>`).join("") + "</ul>" : "";
    if (liste.length) box.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // --- Weiter zu LimeSurvey ---
  function weiter() {
    pruefe();
    const v = werte(), fehler = [];
    if (v.art === "aenderung" && !original) fehler.push("Welche Sportstätte soll geändert werden? (oben auswählen)");
    if (!v.name) fehler.push("Name der Sportstätte");
    if (!v.kategorie) fehler.push("Sportstättenkategorie");
    if (!lage) fehler.push("Lage: in der Karte auf die Sportstätte klicken");
    if (v.plz && !/^\d{5}$/.test(v.plz)) fehler.push("PLZ mit fünf Ziffern");
    if (v.website && !/^https?:\/\/\S+\.\S+/.test(v.website)) fehler.push("Webseite als vollständige Adresse (https://…)");
    if (/[\w.+-]+@[\w-]+\.[\w.]+/.test(Object.values(v).flat().join(" "))) fehler.push("Bitte keine E-Mail-Adressen eintragen");
    const geaendert = aenderungen(v).map(([k]) => k);
    if (original && !geaendert.length && !v.anmerkung) fehler.push("Änderung: mindestens ein Feld ändern oder eine Anmerkung schreiben");
    const cb = el.querySelector("#v-keine-doppelung");
    if (v.art === "neu" && dubletten.length && !(cb && cb.checked)) {
      fehler.push("Mögliche Doppelung prüfen (rechts) und bestätigen, dass es eine andere Sportstätte ist");
    }
    zeigeFehlerliste(fehler);
    if (fehler.length) return;
    const daten = { ...v, geaendert: geaendert.join(", "), lage: v.lat ? `${v.lat}, ${v.lon}` : "",
      adresse: [`${v.strasse} ${v.hausnummer}`.trim(), `${v.plz} ${v.ort}`.trim()].filter(Boolean).join(", "),
      dubletten: dubletten.length ? dubletten.map(d => d.e.p.id).join(", ") + (cb && cb.checked ? " (geprüft: andere Sportstätte)" : "") : "" };
    const params = new URLSearchParams();
    for (const [k, code] of Object.entries(VORSCHLAG_FELDER)) {
      if (!code) continue;
      const w = Array.isArray(daten[k]) ? daten[k].join("; ") : daten[k];
      if (!leer(w)) params.set(code, w);
    }
    const ausgabe = el.querySelector("#v-ausgabe");
    if (KONFIG.vorschlag_url) {
      const u = KONFIG.vorschlag_url + (KONFIG.vorschlag_url.includes("?") ? "&" : "?") + "newtest=Y&" + params;
      ausgabe.innerHTML = `<div class="ok">Die Umfrage wurde in einem neuen Tab geöffnet. Falls nicht: `
        + `<a href="${esc(u)}" target="_blank" rel="noopener">hier weiter zu LimeSurvey</a>.</div>`;
      window.open(u, "_blank", "noopener");
    } else {
      ausgabe.innerHTML = `<div class="warnung"><b>Der Link zur LimeSurvey-Umfrage ist noch nicht eingetragen</b> `
        + `(in <code>konfig.js</code>: <code>vorschlag_url</code>). Übertragen würden diese Werte:`
        + `<table class="meta">` + [...params].map(([k, w]) => `<tr><td><code>${esc(k)}</code></td><td>${esc(w)}</td></tr>`).join("")
        + `</table><details><summary>als URL-Parameter</summary><code class="umbruch">?${esc(params.toString())}</code></details></div>`;
      ausgabe.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  let gebaut = false;
  return {
    titel: "Vorschlag",
    starte() {},
    zeigen() {
      el.hidden = false;
      if (!gebaut) { baue(); gebaut = true; neu(); }
      starteKarte();
      if (marke) marke.addTo(vkarte);
      pruefe();
    },
    verbergen() { el.hidden = true; },
    gebietGeaendert() {},
    hat: id => NACH_ID.has(id),
    neu(vorgabe, herkunft) { zeige("vorschlag").then(() => { neu(vorgabe, herkunft); pruefe(); el.scrollTop = 0; }); },
    bearbeite(id) { zeige("vorschlag").then(() => { bearbeite(id); pruefe(); el.scrollTop = 0; }); },
  };
}
// Links in Popups: „ändern“, „als Vorschlag übernehmen“, „hier vorschlagen“
document.addEventListener("click", ev => {
  const a = ev.target.closest("[data-bearbeiten],[data-vorschlag-alkis],[data-vorschlag-hier],[data-vorschlag-neu]");
  const v = ANSICHTEN.vorschlag;
  if (!a || !v) return;
  ev.preventDefault();
  karte.closePopup();
  if (a.dataset.bearbeiten) v.bearbeite(a.dataset.bearbeiten);
  else if (a.dataset.vorschlagNeu !== undefined) v.neu();
  else if (a.dataset.vorschlagHier) {
    const [lat, lon] = a.dataset.vorschlagHier.split(",").map(Number);
    v.neu({ lat, lon });
  } else {
    const s = VERIF_STAETTEN[a.dataset.vorschlagAlkis];
    if (!s) return;
    v.neu({ name: s.name, kategorie: GRUPPE_KATEGORIE[s.typgruppe] || "", ...zerlegeAdresse(s.adresse),
      betreiber: s.betreiber, eigentuemer: s.eigentuemer, website: s.website, lat: s.lat, lon: s.lon,
      anmerkung: `Aus ALKIS übernommen (${s.typ || s.typgruppe || "Sportstätte"}).` },
      "ALKIS " + (s.alkis_oid || s.sportstaette_id));
  }
});
// Kennungen aus dem Datenbestand für die Popups der Verifikation (Atlas-ID → Bestand)
let VERIF_STAETTEN = {};
function aendernLink(id, text = "Ändern oder Fehler melden") {
  if (!ANSICHTEN.vorschlag || leer(id) || !ANSICHTEN.vorschlag.hat(id)) return "";
  return `<tr><td>Vorschlag</td><td><a href="#" data-bearbeiten="${esc(id)}">${text}</a></td></tr>`;
}

// ---------- Suche -----------------------------------------------------------------------
// Zuerst in den eigenen Daten (Name, Adresse, Betreiber, ID) und den Gebieten, mit Enter auch
// nach Orten und Adressen über den OSM-Geocoder Nominatim (Ausweich: Photon). Nur auf Enter
// bzw. Klick wird angefragt, nicht bei jedem Tastendruck (Nutzungsregeln von Nominatim).
const suchMarke = L.layerGroup().addTo(karte);
let sucheLeeren = () => {};
function springe(e) {
  suchMarke.clearLayers();
  if (e.gebiet) { setzeGebiet(e.gebiet); return; }
  const grenzen = e.grenzen();
  karte.fitBounds(grenzen.pad(0.2), { maxZoom: 17 });
  if (e.oeffne) { e.oeffne(); return; }
  L.circleMarker(grenzen.getCenter(), { radius: 14, color: "#185FA5", weight: 3, fill: false,
    interactive: false }).bindTooltip(esc(e.titel), { permanent: true, direction: "top",
    offset: [0, -12] }).addTo(suchMarke);
}
function lokaleTreffer(q) {
  const worte = q.toLowerCase().split(/\s+/).filter(Boolean);
  const out = [];
  for (const g of GEBIETE) {
    if (worte.every(w => g.n.toLowerCase().includes(w))) {
      out.push({ titel: g.n, sub: `${g.b || EBENE_TEXT[g.e]} – als Gebiet auswählen`, gebiet: g });
    }
    if (out.length >= 3) break;
  }
  const a = ANSICHTEN[AKTIV];
  const index = a && a.suchindex ? a.suchindex() : [];
  for (const e of index) {
    if (imGebiet(e.ars) && worte.every(w => e.text.includes(w))) out.push(e);
    if (out.length >= 10) break;
  }
  return out;
}
async function geocode(q) {
  if (KONFIG.ortssuche === false) return [];  // abschaltbar in konfig.js
  const b = karte.getBounds();
  const nominatim = "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6"
    + "&countrycodes=de&accept-language=de&q=" + encodeURIComponent(q)
    + `&viewbox=${b.getWest()},${b.getNorth()},${b.getEast()},${b.getSouth()}`;
  try {
    const r = await fetch(nominatim);
    if (!r.ok) throw new Error(r.status);
    return (await r.json()).map(t => ({ titel: t.name || t.display_name.split(",")[0],
      sub: t.display_name, grenzen: () => L.latLngBounds(
        [+t.boundingbox[0], +t.boundingbox[2]], [+t.boundingbox[1], +t.boundingbox[3]]) }));
  } catch (_) {
    const c = karte.getCenter();
    const r = await fetch("https://photon.komoot.io/api/?limit=6&lang=de&q="
      + encodeURIComponent(q) + `&lat=${c.lat}&lon=${c.lng}`);
    if (!r.ok) throw new Error("Geocoder nicht erreichbar");
    return (await r.json()).features.map(f => {
      const p = f.properties, [lon, lat] = f.geometry.coordinates, e = p.extent;
      return { titel: p.name || [p.street, p.housenumber].filter(Boolean).join(" "),
        sub: [p.street && p.name ? p.street : "", p.postcode, p.city, p.state]
          .filter(Boolean).join(", "),
        grenzen: () => e ? L.latLngBounds([e[1], e[0]], [e[3], e[2]])
          : L.latLngBounds([[lat, lon], [lat, lon]]) };
    });
  }
}
const suche = L.control({ position: "topleft" });
suche.onAdd = () => {
  const div = L.DomUtil.create("div", "panel suche");
  L.DomEvent.disableClickPropagation(div);
  L.DomEvent.disableScrollPropagation(div);
  div.innerHTML = `<form><input type="search" placeholder="Ort, Sportstätte, Verein …"
    aria-label="Suche"><button type="submit" title="Orte und Adressen suchen">Suchen</button>
    </form><ul></ul>`;
  const feld = div.querySelector("input"), liste = div.querySelector("ul");
  let treffer = [], geo = [], laeuft = false;
  const zeige = () => {
    const eintrag = (e, i) => `<li data-i="${i}">${esc(e.titel)}`
      + (e.sub ? `<small>${esc(e.sub)}</small>` : "") + "</li>";
    let h = "";
    if (treffer.length) h += `<li class="gruppe">In den Daten</li>` + treffer.map(eintrag).join("");
    if (geo.length) h += `<li class="gruppe">Orte (© OpenStreetMap-Mitwirkende)</li>`
      + geo.map((e, i) => eintrag(e, treffer.length + i)).join("");
    if (laeuft) h += `<li class="gruppe">Suche Orte …</li>`;
    else if (feld.value.trim().length >= 2 && !treffer.length && !geo.length)
      h += `<li class="gruppe">Nichts in den Daten – Enter sucht nach Orten</li>`;
    liste.innerHTML = h;
  };
  feld.addEventListener("input", () => {
    const q = feld.value.trim();
    geo = [];
    treffer = q.length >= 2 ? lokaleTreffer(q) : [];
    zeige();
  });
  div.querySelector("form").addEventListener("submit", async ev => {
    ev.preventDefault();
    const q = feld.value.trim();
    if (q.length < 2 || laeuft) return;
    laeuft = true; zeige();
    try { geo = await geocode(q); }
    catch (_) { geo = []; liste.insertAdjacentHTML("beforeend",
      `<li class="gruppe">Ortssuche gerade nicht erreichbar</li>`); }
    laeuft = false; zeige();
    if (!treffer.length && geo.length === 1) springe(geo[0]);
  });
  liste.addEventListener("click", ev => {
    const li = ev.target.closest("li[data-i]");
    if (!li) return;
    springe([...treffer, ...geo][+li.dataset.i]);
  });
  sucheLeeren = () => { feld.value = ""; treffer = geo = []; suchMarke.clearLayers(); zeige(); };
  feld.addEventListener("keydown", ev => { if (ev.key === "Escape") sucheLeeren(); });
  return div;
};
suche.addTo(karte);

// Rechtsklick: Koordinaten der Stelle kopieren ("Breite, Länge" wie bei Google Maps)
function kopiere(text) {
  const alt = () => {
    const t = document.createElement("textarea");
    t.value = text; t.style.position = "fixed"; t.style.opacity = "0";
    document.body.appendChild(t); t.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (_) { ok = false; }
    t.remove();
    return ok;
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text).then(() => true, alt);
  }
  return Promise.resolve(alt());
}
karte.on("contextmenu", e => {
  const t = `${e.latlng.lat.toFixed(6)}, ${e.latlng.lng.toFixed(6)}`;
  const link = `<a href="https://www.google.com/maps?q=${encodeURIComponent(t)}" `
    + `target="_blank" rel="noopener">in Google Maps öffnen</a>`;
  const popup = L.popup({ maxWidth: 300 }).setLatLng(e.latlng)
    .setContent(`<b class="koord">${t}</b><br>kopiere …`).openOn(karte);
  const hier = ANSICHTEN.vorschlag ? `<br><a href="#" data-vorschlag-hier="${e.latlng.lat},${e.latlng.lng}">`
    + `Hier eine Sportstätte vorschlagen</a>` : "";
  kopiere(t).then(ok => popup.setContent(`<b class="koord">${t}</b><br>`
    + (ok ? "in die Zwischenablage kopiert" : "zum Kopieren markieren (Strg+C)")
    + ` · ${link}${hier}`));
});
// auch nach Zoom; lädt Flächen des neuen Ausschnitts
karte.on("moveend", () => { const a = ANSICHTEN[AKTIV]; if (a && a.aktualisiere) a.aktualisiere(); });

// ---------- Start -----------------------------------------------------------------------
(async function start() {
  let bestand = null, index = null;
  if (!EINGEBETTET) {
    try {
      [bestand, index] = await Promise.all([holeJson("bestand.geojson"), holeJson("gebiete.json")]);
    } catch (fehler) {
      zeigeFehler(location.protocol === "file:"
        ? "Die Seite muss über einen Webserver geöffnet werden (lokal: sportstaettenatlas seite --vorschau)."
        : `Die Daten konnten nicht geladen werden (${fehler.message}).`);
      throw fehler;
    }
  }
  starteGebietswahl(index);
  if (bestand && bestand.features.length) {
    const b = ANSICHTEN.bestand = ansichtBestand(bestand);
    ANSICHTEN.liste = ansichtListe(b);
    ANSICHTEN.uebersicht = ansichtUebersicht(b);
    ANSICHTEN.vorschlag = ansichtVorschlag(b);
  } else {
    STANDARD = "verifikation";
  }
  ANSICHTEN.verifikation = ansichtVerifikation();
  knoepfe();
  kopfzeile();
  fertig();
  const hash = new URLSearchParams(location.hash.slice(1));
  const g = hash.get("gebiet");
  if (g && NACH_S[g]) setzeGebiet(NACH_S[g], false);
  const ziel = ANSICHTEN[hash.get("ansicht")] ? hash.get("ansicht") : STANDARD;
  await zeige(ziel);
  if (GEBIET) karte.fitBounds(grenzenVon(GEBIET), GEBIET_RAND);
})();
</script>
</body>
</html>
"""
