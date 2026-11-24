// Karte im Formular: Lage setzen, Gemeinde bestimmen, Lage aus der Adresse.
import { z } from "./zustand.js";
import { F } from "./formular.js";
import { zeigeNk } from "./neue_objekte.js";
import { planePruefung, zeigeFehlerliste } from "./pruefung.js";
import { NEUER_KOMPLEX } from "./hilfen.js";
import { PRUEFUNG } from "../../daten/schema.js";
import { SPORTKOMPLEXE, komplexName } from "../../daten/sportkomplexe.js";
import { GEBIETE, NACH_S, gebietTitel, ladeUmrisse } from "../../karte/gebiete.js";
import { BASEMAP, BKG, karte } from "../../karte/karte.js";
import { esc } from "../../lib/text.js";
import { abstand, punktIn } from "../../lib/vergleich.js";
import { geocode } from "../suche.js";

// --- Karte im Formular ---
export function starteKarte() {
  if (z.vkarte) { z.vkarte.invalidateSize(); return; }
  z.vkarte = L.map("v-karte", { preferCanvas: true, maxZoom: 19 });
  L.tileLayer(BASEMAP, { layer: "de_basemapde_web_raster_farbe", maxNativeZoom: 18, maxZoom: 19,
    attribution: BKG }).addTo(z.vkarte);
  z.vkarte.fitBounds(karte.getBounds());
  z.nachbarn = L.layerGroup().addTo(z.vkarte);
  for (const e of z.bestand.eintraege) {
    L.circleMarker([e.lat, e.lon], { radius: 4, weight: 1, color: "#fff", fillColor: "#7a7975",
      fillOpacity: 0.9 }).bindTooltip(esc(e.p.name || e.kat)).bindPopup(() =>
      `<b>${esc(e.p.name || e.kat)}</b><br>${esc(e.p.kategorie || "")}<br>${esc(e.p.adresse || "")}`
      + `<br><a href="#" data-bearbeiten="${esc(e.p.id)}">Diese Sportstätte ändern</a>`).addTo(z.nachbarn);
  }
  z.vkarte.on("click", ev => setzeLage(ev.latlng.lat, ev.latlng.lng));
}
// Auswahl der Sportkomplexe: die in der Nähe der Lage (PRUEFUNG().komplex_nah_m), nach
// Abstand; der gewählte bleibt
export function komplexAuswahl() {
  const e = z.FELD_KOMPLEX && F(z.FELD_KOMPLEX.pfad);
  if (!e) return;
  const alt = e.value;
  const nah = [...SPORTKOMPLEXE.values()]
    .map(k => [k, z.lage && k.lat != null ? abstand(z.lage[0], z.lage[1], k.lat, k.lon) : Infinity])
    .filter(([k, d]) => d <= PRUEFUNG().komplex_nah_m || k.id === alt)
    .sort((a, b) => a[1] - b[1]);
  if (alt && !nah.some(([k]) => k.id === alt)) nah.unshift([{ id: alt, name: komplexName(alt) }, Infinity]);
  const weg = d => !isFinite(d) ? "" : ` (${d < 1000 ? Math.round(d) + " m" : (d / 1000).toFixed(1) + " km"})`;
  e.innerHTML = `<option value="">kein Sportkomplex</option>`
    + nah.map(([k, d]) => `<option value="${esc(k.id)}">${esc(k.name)}${weg(d)}</option>`).join("")
    + (z.unter ? "" : `<option value="${NEUER_KOMPLEX}">+ neuer Sportkomplex …</option>`);
  e.value = alt;
  zeigeNk();
}
export function setzeLage(lat, lon, zoomen = false) {
  z.lage = lat == null ? null : [+lat, +lon];
  komplexAuswahl();
  if (z.marke) { z.marke.remove(); z.marke = null; }
  const t = z.el.querySelector("#v-lage");
  if (!z.lage) { t.textContent = "Bitte in der Karte rechts auf die Sportstätte klicken."; z.ars = "";
    z.el.querySelector("#v-gemeinde").textContent = ""; planePruefung(); return; }
  t.innerHTML = `<span class="koord">${z.lage[0].toFixed(6)}, ${z.lage[1].toFixed(6)}</span>`;
  if (z.vkarte) {
    z.marke = L.marker(z.lage, { draggable: true, keyboard: false, icon: L.divIcon({ className: "",
      iconSize: [26, 34], iconAnchor: [13, 32], html: `<div class="nadel"></div>` }) }).addTo(z.vkarte);
    z.marke.on("dragend", () => { const p = z.marke.getLatLng(); setzeLage(p.lat, p.lng); });
    if (zoomen) z.vkarte.setView(z.lage, Math.max(z.vkarte.getZoom(), 17));
  }
  bestimmeGemeinde();
  planePruefung();
}
export async function bestimmeGemeinde() {
  const ziel = z.el.querySelector("#v-gemeinde");
  z.ars = "";
  if (!z.lage || !GEBIETE.length) { ziel.textContent = ""; return; }
  const fc = await ladeUmrisse("gemeinde"), [lat, lon] = z.lage;
  if (!fc || !z.lage || z.lage[0] !== lat) return;
  const f = fc.features.find(x => x.geometry && punktIn(lon, lat, x.geometry));
  const g = f && NACH_S[f.properties.s];
  z.ars = g ? g.s : "";
  ziel.textContent = g ? `Gemeinde: ${gebietTitel(g)}` : "Liegt außerhalb von Rheinland-Pfalz?";
  const ort = F("adresse.ort");
  if (g && ort && !ort.value.trim()) ort.value = g.n;
}
export async function lageAusAdresse() {
  const w = n => (F(`adresse.${n}`) ? F(`adresse.${n}`).value : "");
  const q = [w("strasse") + " " + w("hausnummer"), w("plz") + " " + w("ort")]
    .map(s => s.trim()).filter(Boolean).join(", ");
  const b = z.el.querySelector("#v-geocode");
  if (!q) { zeigeFehlerliste(["Für die Suche bitte Straße und Ort eintragen."]); return; }
  b.disabled = true; b.textContent = "suche …";
  try {
    const t = await geocode(q);
    if (t.length) { const c = t[0].grenzen().getCenter(); setzeLage(c.lat, c.lng, true); }
    else zeigeFehlerliste(["Adresse nicht gefunden – bitte die Lage in der Karte setzen."]);
  } catch (_) { zeigeFehlerliste(["Adresssuche gerade nicht erreichbar – bitte die Lage in der Karte setzen."]); }
  b.disabled = false; b.textContent = "Lage aus der Adresse suchen";
}
