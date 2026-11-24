// Die Karte: Hintergründe, Popups, Links zu Luftbild und Google Maps, Panel für Filter.
import { esc, leer, zahl } from "../lib/text.js";

export const karte = L.map("karte", { preferCanvas: true, maxZoom: 19 });
const DATEN_HINWEIS = QUELLE ? " | Daten: " + esc(QUELLE) : "";
// basemap.de (BKG) erlaubt den Abruf auch aus lokal geöffneten Dateien (file://);
// die OSM-Kacheln verlangen dagegen einen Referer und liefern dort 403.
export const BASEMAP = "https://sgx.geodatenzentrum.de/wmts_basemapde/tile/1.0.0/"
  + "{layer}/default/GLOBAL_WEBMERCATOR/{z}/{y}/{x}.png";
export const BKG = '&copy; <a href="https://basemap.de">basemap.de</a> / BKG '
  + new Date().getFullYear() + " (CC BY 4.0)";
// Standard: die farbige Karte, etwas zurückgenommen (Klasse „sanft“, stil.css), damit sich die
// Punkte abheben; die graue bleibt zur Auswahl
const hintergruende = {
  "basemap.de Farbe": L.tileLayer(BASEMAP, { layer: "de_basemapde_web_raster_farbe",
    maxNativeZoom: 18, maxZoom: 19, className: "sanft", attribution: BKG + DATEN_HINWEIS }),
  "basemap.de Grau": L.tileLayer(BASEMAP, { layer: "de_basemapde_web_raster_grau",
    maxNativeZoom: 18, maxZoom: 19, attribution: BKG + DATEN_HINWEIS }),
  "OpenStreetMap (nur über http://)": L.tileLayer(
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      + DATEN_HINWEIS }),
};
hintergruende["basemap.de Farbe"].addTo(karte);
L.control.layers(hintergruende, null, { position: "topleft" }).addTo(karte);
karte.setView([49.95, 7.45], 8);

const POPUP = { maxWidth: 460, minWidth: 260, autoPanPadding: [30, 30] };
const KOPIERHINWEIS = `<div class="hinweis">Text markieren und kopieren möglich</div>`;
export function info(layer, html) {
  // Darüberfahren: kurze Vorschau; Klicken: bleibt stehen, Text lässt sich markieren.
  // html darf eine Funktion sein (Inhalt erst beim Anzeigen erzeugen – spart Zeit beim Start).
  layer.bindTooltip(html, { sticky: true });
  layer.bindPopup(typeof html === "function" ? () => html() + KOPIERHINWEIS
    : html + KOPIERHINWEIS, POPUP);
  layer.on("popupopen", () => layer.closeTooltip && layer.closeTooltip());
  return layer;
}
// Punkt beim Darüberfahren größer, mit hellem Ring, und vor den anderen
const HERVOR = { radius: 7, weight: 2.5, color: "#fff" };
export function hervorheben(layer) {
  const normal = { radius: layer.getRadius(), weight: layer.options.weight, color: layer.options.color };
  layer.on("mouseover", () => { layer.setStyle(HERVOR); layer.bringToFront(); });
  layer.on("mouseout", () => layer.setStyle(normal));
  return layer;
}
// Amtliches Luftbild (DOP20, LVermGeo RLP, dl-de/by-2-0): Bild von etwa 200 × 200 m mit der
// Stelle in der Mitte, direkt vom WMS des Landes
const LUFTBILD_WMS = "https://geo4.service24.rlp.de/wms/rp_dop20.fcgi";
export function luftbildUrl(lat, lon, halbeSeiteM = 100) {
  const dLat = halbeSeiteM / 111320, dLon = dLat / Math.cos(lat * Math.PI / 180);
  const bbox = [lon - dLon, lat - dLat, lon + dLon, lat + dLat].map(x => x.toFixed(6)).join(",");
  return `${LUFTBILD_WMS}?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=rp_dop20&STYLES=`
    + `&SRS=EPSG:4326&BBOX=${bbox}&WIDTH=1000&HEIGHT=1000&FORMAT=image/jpeg`;
}
// Links zu Google Maps und zum Luftbild für eine Stelle
export function kartenLinks(lat, lon) {
  const t = `${(+lat).toFixed(6)}, ${(+lon).toFixed(6)}`;
  return `<a href="https://www.google.com/maps?q=${encodeURIComponent(t)}" target="_blank" `
    + `rel="noopener">Google Maps</a> · <a href="${luftbildUrl(+lat, +lon)}" target="_blank" `
    + `rel="noopener" title="Amtliches Luftbild (DOP20, © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0), `
    + `etwa 200 × 200 m, die Stelle in der Mitte">Luftbild</a>`;
}
// Koordinaten im Format von Google Maps ("Breite, Länge"), zum Kopieren
export function koord(lat, lon) {
  if (leer(lat) || leer(lon)) return "";
  const t = `${(+lat).toFixed(6)}, ${(+lon).toFixed(6)}`;
  return `<tr><td>Koordinaten</td><td><span class="koord">${t}</span> `
    + `${kartenLinks(lat, lon)}</td></tr>`;
}
export function bboxVon(geom) {
  let w = 180, s = 90, o = -180, n = -90;
  const lauf = c => {
    if (typeof c[0] === "number") {
      w = Math.min(w, c[0]); o = Math.max(o, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]);
    } else c.forEach(lauf);
  };
  if (geom && geom.coordinates) lauf(geom.coordinates);
  return [w, s, o, n];
}
export function punktGrenzen(lat, lon) { return L.latLngBounds([[lat, lon], [lat, lon]]); }
export const svgRenderer = L.svg({ padding: 0.3 });

// Panel rechts oben (Filter, Legende): Klicks und Scrollen gehen nicht an die Karte.
// Zahlen stehen in <span class="n" data-n="schlüssel"> und werden je Gebiet neu gesetzt.
export function panelDiv(klasse) {
  const div = L.DomUtil.create("div", "panel " + klasse);
  L.DomEvent.disableClickPropagation(div);
  L.DomEvent.disableScrollPropagation(div);
  return div;
}
export function nSpan(k) { return `<span class="n" data-n="${esc(k)}"></span>`; }
export function setzeZahlen(div, zaehler) {
  div.querySelectorAll("[data-n]").forEach(el => {
    const w = zaehler[el.dataset.n] || 0;
    el.textContent = zahl(w);
    el.closest("label").classList.toggle("null", !w);
  });
}
