// Gebiete (Kreis, Verbandsgemeinde, Gemeinde)
// Jedes Objekt trägt den Regionalschlüssel (ars) seiner Gemeinde; ein Gebiet passt, wenn
// der ars mit dem Schlüssel des Gebiets beginnt (Kreis 5, Verbandsgemeinde 9 Stellen).
import { esc } from "../lib/text.js";
import { holeJson } from "../seite.js";
import { karte } from "./karte.js";

export let GEBIETE = [], GEBIET = null;
export const NACH_S = {};
const umrisse = {};  // Ebene → Promise der Umrisse
const umrissEbene = L.layerGroup().addTo(karte);
// rechts Platz für das Filter-Panel lassen
export const GEBIET_RAND = { paddingTopLeft: [20, 20], paddingBottomRight: [290, 20] };
export const EBENE_TEXT = { kreis: "Kreis", vg: "Verbandsgemeinde", gemeinde: "Gemeinde" };
export function imGebiet(ars) { return !GEBIET || (!!ars && ars.startsWith(GEBIET.s)); }
export function gemeindeName(ars) {
  const g = ars && NACH_S[ars.slice(0, 12)];
  return g ? g.n : "";
}
export function gebietName() { return GEBIET ? GEBIET.n : "Rheinland-Pfalz"; }
export function gebietTitel(e) {
  const b = e.b && !e.n.startsWith(e.b) ? ` (${e.b})` : "";
  return e.n + b;
}
export function grenzenVon(e) {
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
export function ladeUmrisse(ebene) {
  return umrisse[ebene] ??= holeJson(`gebiete_${ebene}.geojson`).catch(() => null);
}
// Umriss eines Gebiets beim Darüberfahren (z. B. über einen Haufen); umrissZeigen(null) nimmt
// ihn weg. Die Umrisse einer Ebene werden beim ersten Mal geladen.
export const hoverEbene = L.layerGroup().addTo(karte);
const umrissNach = {};  // Ebene → Promise einer Map Schlüssel → Feature
let hoverSoll = null;
function umrissVon(ebene, s) {
  umrissNach[ebene] ??= ladeUmrisse(ebene).then(fc =>
    new Map((fc ? fc.features : []).map(f => [f.properties.s, f])));
  return umrissNach[ebene].then(m => m.get(s));
}
export async function umrissZeigen(ebene, s) {
  hoverSoll = ebene ? ebene + ":" + s : null;
  hoverEbene.clearLayers();
  if (!ebene) return;
  const f = await umrissVon(ebene, s);
  if (!f || hoverSoll !== ebene + ":" + s) return;
  L.geoJSON(f, { interactive: false, style: { color: "#871D33", weight: 2, opacity: 0.9,
    fillColor: "#871D33", fillOpacity: 0.07 } }).addTo(hoverEbene);
}
// Außerhalb des Landes grau (gebiete_land.geojson): ein Rechteck um die Welt mit dem Land als
// Loch, in einer eigenen Ebene über der Hintergrundkarte und unter Umrissen und Punkten
karte.createPane("maske").style.zIndex = 350;
const maskeRenderer = L.svg({ pane: "maske", padding: 0.5 });
function zeigeMaske(fc) {
  const loecher = [];
  for (const f of (fc && fc.features) || []) {
    const g = f.geometry;
    const polygone = !g ? [] : g.type === "Polygon" ? [g.coordinates] : g.coordinates;
    for (const p of polygone) loecher.push(p[0].map(([lon, lat]) => [lat, lon]));
  }
  if (!loecher.length) return;
  const welt = [[-85, -180], [85, -180], [85, 180], [-85, 180]];
  const art = { pane: "maske", renderer: maskeRenderer, interactive: false };
  L.polygon([welt, ...loecher], { ...art, stroke: false, fillColor: "#5f5f5f", fillOpacity: 0.38 })
    .addTo(karte);
  L.polygon(loecher, { ...art, fill: false, color: "#871D33", weight: 1.5, opacity: 0.55 })
    .addTo(karte);
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
export function setzeGebiet(e, zoomen = true) {
  GEBIET = e || null;
  const kreis = e ? NACH_S[e.s.slice(0, 5)] : null;
  wahl.kreis.value = kreis ? kreis.s : "";
  fuelleKommunen(kreis);
  if (e && e.e !== "kreis") wahl.kommune.value = e.s;
  wahl.weg.hidden = !e;
  zeigeUmriss(GEBIET);
  if (e && zoomen) karte.fitBounds(grenzenVon(e), GEBIET_RAND);
  beimWechsel();
}
// Was bei einem Wechsel des Gebiets außerdem geschieht (umschalten.js: Adresse, Ansichten)
let beimWechsel = () => {};
export function beiGebietswechsel(fn) { beimWechsel = fn; }
export function starteGebietswahl(index) {
  GEBIETE = index && index.eintraege ? index.eintraege : [];
  if (!GEBIETE.length) return;
  for (const e of GEBIETE) NACH_S[e.s] = e;
  holeJson("gebiete_land.geojson").then(zeigeMaske).catch(() => {});
  const kreise = GEBIETE.filter(e => e.e === "kreis");
  wahl.kreis.innerHTML = `<option value="">Rheinland-Pfalz (alle)</option>`
    + kreise.map(e => `<option value="${e.s}">${esc(gebietTitel(e))}</option>`).join("");
  wahl.kreis.addEventListener("change", () => setzeGebiet(NACH_S[wahl.kreis.value]));
  wahl.kommune.addEventListener("change", () =>
    setzeGebiet(NACH_S[wahl.kommune.value] || NACH_S[wahl.kreis.value]));
  wahl.weg.addEventListener("click", () => setzeGebiet(null, false));
  wahl.feld.hidden = false;
}
