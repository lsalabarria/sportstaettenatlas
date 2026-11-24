// Suche über Karte und Daten, Rechtsklick-Menü (Koordinaten kopieren).
// ---------- Suche -----------------------------------------------------------------------
// Zuerst in den eigenen Daten (Name, Adresse, Betreiber, ID) und den Gebieten, mit Enter auch
// nach Orten und Adressen über den OSM-Geocoder Nominatim. Nur auf Enter
// bzw. Klick wird angefragt, nicht bei jedem Tastendruck (Nutzungsregeln von Nominatim).
import { EBENE_TEXT, GEBIETE, imGebiet, setzeGebiet } from "../karte/gebiete.js";
import { karte, kartenLinks } from "../karte/karte.js";
import { esc } from "../lib/text.js";
import { KONFIG } from "../seite.js";
import { AKTIV, ANSICHTEN } from "./umschalten.js";

const suchMarke = L.layerGroup().addTo(karte);
export let sucheLeeren = () => {};
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
export async function geocode(q) {
  if (KONFIG.ortssuche === false) return [];  // abschaltbar in konfig.js
  const b = karte.getBounds();
  const nominatim = "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6"
    + "&countrycodes=de&accept-language=de&q=" + encodeURIComponent(q)
    + `&viewbox=${b.getWest()},${b.getNorth()},${b.getEast()},${b.getSouth()}`;
  const r = await fetch(nominatim);
  if (!r.ok) throw new Error("Ortssuche nicht erreichbar");
  return (await r.json()).map(t => ({ titel: t.name || t.display_name.split(",")[0],
    sub: t.display_name, grenzen: () => L.latLngBounds(
      [+t.boundingbox[0], +t.boundingbox[2]], [+t.boundingbox[1], +t.boundingbox[3]]) }));
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
    let ok;
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
  const link = kartenLinks(e.latlng.lat, e.latlng.lng);
  const popup = L.popup({ maxWidth: 300 }).setLatLng(e.latlng)
    .setContent(`<b class="koord">${t}</b><br>kopiere …`).openOn(karte);
  const hier = ANSICHTEN.vorschlag ? `<br><a href="#" data-vorschlag-hier="${e.latlng.lat},${e.latlng.lng}">`
    + `Hier eine Sportstätte vorschlagen</a>` : "";
  kopiere(t).then(ok => popup.setContent(`<b class="koord">${t}</b><br>`
    + (ok ? "in die Zwischenablage kopiert" : "zum Kopieren markieren (Strg+C)")
    + ` · ${link}${hier}`));
});
