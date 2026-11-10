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

    webseite=False: eine Datei mit eingebetteten Daten (lokal per Doppelklick zu öffnen).
    webseite=True:  Seite für GitHub Pages; lädt Kopfzeile/Links aus konfig.js und die
                    Daten aus daten/*.geojson (mit Ladehinweis).
    """
    if webseite:
        skript = _WEBSEITE_SKRIPT
        kopf = '<header id="kopf"><h1>' + html.escape(titel) + "</h1></header>\n"
        laden = '<div id="laden"><span class="kreisel"></span>Sportstätten werden geladen …</div>'
    else:
        skript = (
            "<script>\n"
            f"const ANLAGEN = {_einbetten(anlagen)};\n"
            f"const STAETTEN = {_einbetten(staetten)};\n"
            f"const ATLAS = {_einbetten(atlas or {'type': 'FeatureCollection', 'features': []})};"
        )
        kopf = laden = ""
    return (
        _VORLAGE.replace("__TITEL__", html.escape(titel))
        .replace("__KOPF__", kopf)
        .replace("__LADEN__", laden)
        .replace("__LEAFLET__", leaflet)
        .replace("__QUELLE_JSON__", _einbetten(quellenvermerk))
        .replace("__FARBEN__", _einbetten(FARBEN))
        .replace("__ATLAS_FELDER__", _einbetten(ATLAS_FELDER))
        .replace("__SKRIPT__", skript)  # zuletzt: Daten nie als Platzhalter lesen
    )


# Webseite: Kopfzeile aus konfig.js, Daten nachladen (Modul-Skript erlaubt await)
_WEBSEITE_SKRIPT = r"""<script src="konfig.js"></script>
<script type="module">
{
  const k = window.KONFIG || {}, kopf = document.getElementById("kopf");
  const link = (url, text, klasse) => url ? `<a href="${url}"${klasse ? ` class="${klasse}"` : ""}`
    + `${/^https?:/.test(url) ? ' target="_blank" rel="noopener"' : ""}>${text}</a>` : "";
  if (k.titel) { kopf.querySelector("h1").textContent = k.titel; document.title = k.titel; }
  kopf.insertAdjacentHTML("beforeend", link(k.vorschlag_url, "Sportstätte vorschlagen", "knopf")
    + link("daten/", "Daten herunterladen") + link(k.impressum_url, "Impressum")
    + link(k.datenschutz_url, "Datenschutz"));
}
async function ladeJson(datei) {
  const r = await fetch(datei);
  if (!r.ok) throw new Error(`${datei}: HTTP ${r.status}`);
  return r.json();
}
const [ANLAGEN, STAETTEN, ATLAS] = await Promise.all([
  ladeJson("daten/sportanlagen.geojson"),
  ladeJson("daten/sportstaetten.geojson"),
  ladeJson("daten/atlas_abgleich.geojson"),
]).catch(fehler => {
  const el = document.getElementById("laden");
  el.className = "fehler";
  el.textContent = location.protocol === "file:"
    ? "Die Seite muss über einen Webserver geöffnet werden (lokal: sportstaettenatlas seite --vorschau)."
    : `Die Daten konnten nicht geladen werden (${fehler.message}).`;
  throw fehler;
});
document.getElementById("laden").remove();"""


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
  body { font: 13px/1.4 system-ui, sans-serif; display: flex; flex-direction: column; }
  #bereich { position: relative; flex: 1; min-height: 0; }
  #karte { position: absolute; inset: 0; }
  #kopf { display: flex; align-items: center; gap: 8px 14px; flex-wrap: wrap;
          padding: 8px 14px; background: #fff; border-bottom: 3px solid #871D33; z-index: 1001; }
  #kopf h1 { font-size: 18px; margin: 0 auto 0 0; font-weight: 700; }
  #kopf a { color: #333; text-decoration: none; font-size: 14px; }
  #kopf a:hover { text-decoration: underline; }
  #kopf a.knopf { background: #871D33; color: #fff; padding: 6px 12px; border-radius: 6px; }
  #kopf a.knopf:hover { background: #6d1729; text-decoration: none; }
  #laden { position: absolute; inset: 0; z-index: 1000; display: flex; align-items: center;
           justify-content: center; gap: 10px; background: rgba(255,255,255,.75);
           font-size: 15px; color: #333; }
  #laden.fehler { color: #871D33; }
  .kreisel { width: 22px; height: 22px; border: 3px solid #ddd; border-top-color: #871D33;
             border-radius: 50%; animation: dreh 0.8s linear infinite; }
  @keyframes dreh { to { transform: rotate(360deg); } }
  .panel { background: #fff; padding: 8px 10px; border-radius: 6px;
           box-shadow: 0 1px 4px rgba(0,0,0,.25); max-width: 270px; }
  .panel h1 { font-size: 14px; margin: 0 0 6px; font-weight: 600; }
  .panel h2 { font-size: 12px; margin: 8px 0 4px; font-weight: 600; color: #444; }
  .panel label { display: flex; align-items: center; gap: 6px; cursor: pointer; }
  .panel .n { margin-left: auto; color: #666; font-variant-numeric: tabular-nums; }
  .swatch { width: 12px; height: 12px; border-radius: 3px; flex: none; }
  .panel hr { border: 0; border-top: 1px solid #ddd; margin: 6px 0; }
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
               border: 1px solid #888; background-color: #B4B2A9; }  /* wie eine Fläche */
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
</style>
</head>
<body>
__KOPF__<div id="bereich"><div id="karte"></div>__LADEN__</div>
<script src="__LEAFLET__/leaflet.js"></script>
__SKRIPT__
const KONFIG = window.KONFIG || {};
const ATLAS_FELDER = __ATLAS_FELDER__;
const FARBEN = __FARBEN__;
const QUELLE = __QUELLE_JSON__;
const ZOOM_FLAECHEN = 15;
// Reihenfolge = CSS-Klasse stufe-<i>; LEGENDE = Reihenfolge in der Legende
const STUFEN = ["nur ALKIS", "bestätigt", "nur ALKIS – unbestimmt"];
const LEGENDE_STUFEN = ["nur ALKIS – unbestimmt", "nur ALKIS", "bestätigt"];

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

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;",
    '"': "&quot;", "'": "&#39;" }[c]));
}
const POPUP = { maxWidth: 460, minWidth: 260, autoPanPadding: [30, 30] };
function info(layer, html) {
  // Darüberfahren: kurze Vorschau; Klicken: bleibt stehen, Text lässt sich markieren
  layer.bindTooltip(html, { sticky: true });
  layer.bindPopup(html + `<div class="hinweis">Text markieren und kopieren möglich</div>`, POPUP);
  layer.on("popupopen", () => layer.closeTooltip && layer.closeTooltip());
  return layer;
}
function farbe(p) { return FARBEN[p.typgruppe] || "#D85A30"; }
function leer(v) { return v === null || v === undefined || v === "" || v === "nan"; }

// Rohspalten des Atlas (alt_*) erscheinen nicht im Tooltip; ihre Werte
// stecken in den zusammengeführten Feldern, deren Herkunft in Klammern steht.
const ROH = /^(osm_|wd_|web_|verband_|alt_)|_quelle$|^verifikation|^(lon|lat|geometry)$/;
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

// Koordinaten im Format von Google Maps ("Breite, Länge"), zum Kopieren
function koord(lat, lon) {
  if (leer(lat) || leer(lon)) return "";
  const t = `${(+lat).toFixed(6)}, ${(+lon).toFixed(6)}`;
  return `<tr><td>Koordinaten</td><td><span class="koord">${t}</span> `
    + `<a href="https://www.google.com/maps?q=${encodeURIComponent(t)}" target="_blank" `
    + `rel="noopener">Google Maps</a></td></tr>`;
}
// Link zum Meldeformular (nur auf der Webseite, Adresse in konfig.js). Als Kennung dient
// die ALKIS-Objektkennung: sie bleibt über Neuberechnungen gleich, die laufende Nummer
// (ST000123) dagegen nicht.
function melden(s) {
  if (!KONFIG.vorschlag_url) return "";
  let url = KONFIG.vorschlag_url;
  const kennung = !leer(s.alkis_oid) ? s.alkis_oid : s.sportstaette_id;
  if (KONFIG.vorschlag_parameter && !leer(kennung)) {
    url += (url.includes("?") ? "&" : "?") + encodeURIComponent(KONFIG.vorschlag_parameter)
      + "=" + encodeURIComponent(kennung);
  }
  return `<tr><td>Fehler?</td><td><a href="${esc(url)}" target="_blank" rel="noopener">`
    + `Änderung oder Fehler melden</a></td></tr>`;
}
function tipStaette(s) {
  return `<table class="meta">${verifikation(s)}${zeilen(s)}${koord(s.lat, s.lon)}`
    + `${melden(s)}</table>`;
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

// Sportanlagen: je Typgruppe zwei Ebenen – Punkt (weit) und Umriss (nah)
// Schraffur je Verifikationsstufe: Die Füllfarbe zeigt die Klasse (Typgruppe), die
// Schraffur darüber in Grautönen die Verifikation – dunkel = auch im bisherigen Atlas.
// Einträge, die nur im Sportstättenatlas RLP stehen, sind gegenläufig schraffiert (−45°):
// hell = nur der Atlas kennt sie, mittelgrau = ALKIS hat in der Nähe etwas.
const SCHRAFFUR = {
  "nur ALKIS – unbestimmt": { grau: "#F1EFE8", abstand: 6, breite: 1.2, winkel: 0 },
  "nur ALKIS":          { grau: "#F1EFE8", abstand: 10, breite: 1.5, winkel: 45 },
  "bestätigt":          { grau: "#5F5E5A", abstand: 7,  breite: 1.6, winkel: 45 },
  "nicht in ALKIS":     { grau: "#F1EFE8", abstand: 4,  breite: 1.3, winkel: -45 },
  "nah":                { grau: "#5F5E5A", abstand: 4,  breite: 1.3, winkel: -45 },
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
// Flächen brauchen den SVG-Renderer (Canvas kann keine Muster); Punkte bleiben auf Canvas
const svgRenderer = L.svg({ padding: 0.3 });

function bbox(geom) {
  let w = 180, s = 90, o = -180, n = -90;
  const lauf = c => {
    if (typeof c[0] === "number") {
      w = Math.min(w, c[0]); o = Math.max(o, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]);
    } else c.forEach(lauf);
  };
  if (geom && geom.coordinates) lauf(geom.coordinates);
  return [w, s, o, n];
}

const gruppen = {};
const stufeAn = { "nur ALKIS – unbestimmt": true, "nur ALKIS": true, "bestätigt": true,
  "": true };
function gruppe(name) {
  return gruppen[name] ??= { punkte: [], flaechen: [], n: 0, an: true };
}
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
    g.punkte.push({ stufe, layer: info(L.circleMarker([p.lat, p.lon], { ...stil,
      radius: p.rolle === "zubehoer" ? 3 : 5, fillOpacity: 0.8 }), tip) });
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
    g.flaechen.push({ stufe, bbox: bbox(f.geometry), layer: L.layerGroup(schicht) });
  }
}
const sichtbar = L.layerGroup().addTo(karte);

// Was nur im bisherigen Sportstättenatlas RLP steht (aus dem Abgleich mit ALKIS)
const ATLAS_STIL = {
  "nicht in ALKIS": { color: "#A32D2D", fillColor: "#F09595", kurz: "nur Atlas",
    label: "nur im Sportstättenatlas RLP – kein ALKIS-Objekt im Umkreis von 200 m" },
  "nah": { color: "#854F0B", fillColor: "#FAC775", kurz: "nur Atlas, ALKIS in der Nähe",
    label: "im Sportstättenatlas RLP – nächste ALKIS-Sportstätte 100–200 m entfernt" },
};
const atlasAn = { "nicht in ALKIS": true, "nah": true };

// Pfeil vom Atlas-Eintrag zur nächsten ALKIS-Sportstätte (bei Status "nah")
const pfeilEbene = L.layerGroup().addTo(karte);
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
    + `${esc(st.label)}</td></tr>${zeilenA}${koord(lat, lon)}</table></div>`;
  const kreis = { radius: 8, renderer: svgRenderer };
  const ziel = STAETTE[p.naechste_sportstaette_id];
  const pfeilHinweis = p.status === "nah" && ziel
    ? `<div class="hinweis">Klicken zeigt einen Pfeil zur nächsten ALKIS-Sportstätte</div>` : "";
  const basis = info(L.circleMarker([lat, lon], { ...kreis, color: st.color, weight: 2,
    fillColor: st.fillColor, fillOpacity: 0.85, dashArray: p.status === "nah" ? "3 2" : null }),
    tip.replace(/<\/div>$/, pfeilHinweis + "</div>"));
  if (p.status === "nah" && ziel) basis.on("click", () => zeigePfeil([lat, lon], ziel));
  const muster = L.circleMarker([lat, lon], { ...kreis, stroke: false, fill: true,
    fillColor: `url(#${SCHRAFFUR_ID[p.status] || SCHRAFFUR_ID["nicht in ALKIS"]})`,
    fillOpacity: 1, interactive: false });
  atlasPunkte.push({ status: p.status, layer: L.layerGroup([basis, muster]) });
}

// Nur Ebenen hinzufügen/entfernen, die sich ändern. Ein Neuaufbau würde offene Popups
// schließen, z. B. wenn die Karte nach einem Klick zum Pfeil schwenkt.
let aktuell = new Set();
function aktualisiere() {
  const nah = karte.getZoom() >= ZOOM_FLAECHEN;
  if (nah) staetten.addTo(karte); else karte.removeLayer(staetten);
  const b = karte.getBounds().pad(0.3);
  const [bw, bs, bo, bn] = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
  const imBild = e => !e.bbox || (e.bbox[0] <= bo && e.bbox[2] >= bw
                                  && e.bbox[1] <= bn && e.bbox[3] >= bs);
  const soll = new Set();
  for (const g of Object.values(gruppen)) {
    if (!g.an) continue;
    for (const e of (nah ? g.flaechen : g.punkte)) {
      if (stufeAn[e.stufe] !== false && (!nah || imBild(e))) soll.add(e.layer);
    }
  }
  for (const e of atlasPunkte) if (atlasAn[e.status]) soll.add(e.layer);
  for (const l of aktuell) if (!soll.has(l)) sichtbar.removeLayer(l);
  for (const l of soll) if (!aktuell.has(l)) sichtbar.addLayer(l);
  aktuell = soll;
}

// Legende: Typgruppen und – falls angereichert – Verifikationsstufen
const legende = L.control({ position: "topright" });
legende.onAdd = () => {
  const div = L.DomUtil.create("div", "panel");
  L.DomEvent.disableClickPropagation(div);
  const namen = Object.keys(gruppen).sort((a, b) => gruppen[b].n - gruppen[a].n);
  const zaehl = {};
  for (const f of ANLAGEN.features) {
    const s = stufeVon(f.properties);
    if (s) zaehl[s] = (zaehl[s] || 0) + 1;
  }
  let h = `<h1>${STAETTEN.features.length} Sportstätten · ${ANLAGEN.features.length} Anlagen</h1>`
    + namen.map(n => `<label><input type="checkbox" data-g="${esc(n)}" checked>`
      + `<span class="swatch" style="background:${FARBEN[n] || "#D85A30"}"></span>`
      + `${esc(n)}<span class="n">${gruppen[n].n}</span></label>`).join("");
  const za = {};
  for (const e of atlasPunkte) za[e.status] = (za[e.status] || 0) + 1;
  if (Object.keys(zaehl).length || atlasPunkte.length) {
    h += `<h2>Verifikation</h2>` + LEGENDE_STUFEN.filter(s => zaehl[s]).map(s =>
      `<label><input type="checkbox" data-s="${esc(s)}" checked>`
      + `<span class="schraffur" style="${schraffurCss(s)}"></span>`
      + `<span class="verif stufe-${STUFEN.indexOf(s)}">${esc(s)}</span>`
      + `<span class="n">${zaehl[s]}</span></label>`).join("")
      + Object.keys(ATLAS_STIL).filter(k => za[k]).map(k =>
        `<label title="${esc(ATLAS_STIL[k].label)}"><input type="checkbox" data-a="${esc(k)}" checked>`
        + `<span class="swatch" style="background-color:${ATLAS_STIL[k].fillColor};`
        + `${schraffurCss(k)};width:16px;height:16px;border:2px solid ${ATLAS_STIL[k].color};`
        + `border-radius:50%;box-sizing:border-box"></span>`
        + `<span class="verif" style="background:${ATLAS_STIL[k].fillColor};`
        + `color:${ATLAS_STIL[k].color}">${esc(ATLAS_STIL[k].kurz)}</span>`
        + `<span class="n">${za[k]}</span></label>`).join("");
  }
  h += `<hr><span style="color:#666">Füllfarbe = Klasse, Schraffur = Verifikation `
    + `(ab Zoom ${ZOOM_FLAECHEN})<br>gestrichelt = zu prüfen`
    + (atlasPunkte.length ? `<br>rote/orange Kreise, gegenläufig schraffiert = nur im `
      + `Sportstättenatlas RLP` : "")
    + `<br>Klick: Infos bleiben stehen · Rechtsklick: Koordinaten kopieren`
    + `<br>`
    + `ab Zoom ${ZOOM_FLAECHEN}: Umrisse und Sportstätten-Flächen</span>`;
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
legende.addTo(karte);

// Suche: zuerst in den eigenen Daten (Name, Adresse, ID), mit Enter auch nach Orten
// und Adressen über den OSM-Geocoder Nominatim (Ausweich: Photon). Nur auf Enter bzw.
// Klick wird angefragt, nicht bei jedem Tastendruck (Nutzungsregeln von Nominatim).
const SUCHINDEX = [];
for (const f of STAETTEN.features) {
  const p = f.properties;
  const titel = !leer(p.name) ? p.name : (p.typ || "Sportstätte");
  SUCHINDEX.push({ titel, sub: [p.sportstaette_id, p.typ, leer(p.adresse) ? "" : p.adresse]
    .filter(Boolean).join(" · "), text: [p.name, p.adresse, p.sportstaette_id, p.typ,
    p.anlagentypen, p.betreiber, p.alt_name, p.alt_adresse, p.alt_typ, p.alt_atlas_id]
    .filter(v => !leer(v)).join(" ").toLowerCase(),
    grenzen: () => L.geoJSON(f).getBounds() });
}
for (const f of ATLAS.features) {
  const p = f.properties, [lon, lat] = f.geometry.coordinates;
  SUCHINDEX.push({ titel: p.alt_name || "Atlas-Eintrag", sub: ["Sportstättenatlas RLP",
    p.alt_typ, p.alt_adresse].filter(v => !leer(v)).join(" · "),
    text: [p.alt_name, p.alt_adresse, p.alt_typ, p.alt_atlas_id, p.alt_id]
      .filter(v => !leer(v)).join(" ").toLowerCase(),
    grenzen: () => L.latLngBounds([[lat, lon], [lat, lon]]) });
}
const suchMarke = L.layerGroup().addTo(karte);
function springe(grenzen, titel) {
  suchMarke.clearLayers();
  const c = grenzen.getCenter();
  karte.fitBounds(grenzen.pad(0.2), { maxZoom: 17 });
  L.circleMarker(c, { radius: 14, color: "#185FA5", weight: 3, fill: false,
    interactive: false }).bindTooltip(esc(titel), { permanent: true, direction: "top",
    offset: [0, -12] }).addTo(suchMarke);
}
function lokaleTreffer(q) {
  const worte = q.toLowerCase().split(/\s+/).filter(Boolean);
  const out = [];
  for (const e of SUCHINDEX) {
    if (worte.every(w => e.text.includes(w))) out.push(e);
    if (out.length >= 8) break;
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
  div.innerHTML = `<form><input type="search" placeholder="Ort, Adresse oder Sportstätte"
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
    if (!treffer.length && geo.length === 1) springe(geo[0].grenzen(), geo[0].titel);
  });
  liste.addEventListener("click", ev => {
    const li = ev.target.closest("li[data-i]");
    if (!li) return;
    const e = [...treffer, ...geo][+li.dataset.i];
    springe(e.grenzen(), e.titel);
  });
  feld.addEventListener("keydown", ev => {
    if (ev.key === "Escape") { feld.value = ""; treffer = geo = []; suchMarke.clearLayers();
      zeige(); }
  });
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
  kopiere(t).then(ok => popup.setContent(`<b class="koord">${t}</b><br>`
    + (ok ? "in die Zwischenablage kopiert" : "zum Kopieren markieren (Strg+C)")
    + ` · ${link}`));
});

karte.on("moveend", aktualisiere);  // auch nach Zoom; lädt Flächen des neuen Ausschnitts
const alle = L.geoJSON(ANLAGEN);
if (alle.getLayers().length) karte.fitBounds(alle.getBounds(), { padding: [20, 20] });
else karte.setView([49.9, 7.4], 8);
aktualisiere();
</script>
</body>
</html>
"""
