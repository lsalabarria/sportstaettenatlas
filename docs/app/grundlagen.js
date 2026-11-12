// Grundlagen: Hilfen, Karte, Gebietsauswahl und Umschalten der Ansichten.
// Wird als erstes Skript geladen; die übrigen Dateien bauen darauf auf.

const KONFIG = window.KONFIG || {};
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

// Kopfzeile: Links aus konfig.js (nur Webseite). „Sportstätte vorschlagen“ öffnet das
// Formular, „Bug melden“ ein neues Ticket auf GitHub (konfig.js: fehler_url).
function kopfzeile() {
  const k = KONFIG, el = document.getElementById("links");
  const link = (u, text, extra = "") => u ? `<a href="${esc(u)}"${extra}`
    + `${/^https?:/.test(u) ? ' target="_blank" rel="noopener"' : ""}>${text}</a>` : "";
  if (k.titel) { document.querySelector("#kopf h1").textContent = k.titel; document.title = k.titel; }
  el.innerHTML = (ANSICHTEN.vorschlag
    ? `<a href="#ansicht=vorschlag" class="knopf" data-vorschlag-neu>Sportstätte vorschlagen</a>` : "")
    + link("daten/", "Daten herunterladen") + link(k.fehler_url, "Bug melden", " data-fehler")
    + link(k.impressum_url, "Impressum") + link(k.datenschutz_url, "Datenschutz");
  // Adresse der Seite und Browser in die Ticket-Vorlage übernehmen (Felder in
  // .github/ISSUE_TEMPLATE/fehler.yml); erst beim Klick, damit Ansicht und Gebiet stimmen
  const bug = el.querySelector("[data-fehler]");
  if (bug) bug.addEventListener("click", () => {
    const u = new URL(k.fehler_url, location.href);
    u.searchParams.set("seite", location.href);
    u.searchParams.set("browser", navigator.userAgent);
    bug.href = u.toString();
  });
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
function ladeFehler(fehler) {
  zeigeFehler(location.protocol === "file:"
    ? "Die Seite muss über einen Webserver geöffnet werden (lokal: sportstaettenatlas seite --vorschau)."
    : `Die Daten konnten nicht geladen werden (${fehler.message}).`);
}

// Daten: eingebettet (Karte als eine Datei) oder aus daten/ nachladen; fehlt → null
async function holeJson(name) {
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
// Jede Ansicht ist ein Objekt mit titel, starte() (einmal, darf Daten laden), zeigen(),
// verbergen() und optional aktualisiere() (Karte verschoben), gebietGeaendert(),
// suchindex() und zustand() (Zusatz für die Adresse, z. B. "analyse=alkis").
const ANSICHTEN = {};
let AKTIV = null, STANDARD = "bestand";
const nav = document.getElementById("ansichten");
function merkeZustand() {
  const teile = [];
  if (AKTIV && AKTIV !== STANDARD) teile.push("ansicht=" + AKTIV);
  const extra = AKTIV && ANSICHTEN[AKTIV].zustand && ANSICHTEN[AKTIV].zustand();
  if (extra) teile.push(extra);
  if (GEBIET) teile.push("gebiet=" + GEBIET.s);
  const neu = teile.length ? "#" + teile.join("&") : location.pathname + location.search;
  try { history.replaceState(null, "", neu); } catch (_) { /* z. B. file:// */ }
}
async function zeige(name) {
  const a = ANSICHTEN[name];
  if (!a || name === AKTIV) return;
  if (!a.gestartet) {
    try {
      await a.starte();
    } catch (fehler) {
      ladeFehler(fehler);
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
