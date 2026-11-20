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
function wertText(v) { return typeof v === "boolean" ? (v ? "ja" : "nein") : esc(v); }

// ---------- Datenmodell (daten/schema.json, erzeugt aus src/sportstaettenatlas/modell.py) ----
// Felder, Beschriftungen (title), Auswahllisten (enum), Regeln (minimum, pattern …) und
// Angaben für die Webseite (gruppe, widget, formular, uebersicht, einheit) stehen nur dort.
let SCHEMA = { $defs: {} };
// Zuordnungen und Regeln ohne eigenes Feld (modell.schema: "atlas"): Organisationstypen,
// ALKIS-Typgruppe → Kategorie, Muster für E-Mail-Adressen
const ATLAS = () => SCHEMA.atlas || {};
const enthaeltEmail = x => !!ATLAS().email && new RegExp(ATLAS().email).test(JSON.stringify(x));
// Felder eines Modells: [[Name, Eigenschaft, Pflicht, Typ]] – Typ ohne „oder leer“, Verweise
// aufgelöst (z. B. adresse → Adresse mit ref: "Adresse")
function modellFelder(modell) {
  const m = SCHEMA.$defs[modell] || { properties: {} };
  return Object.entries(m.properties).map(([k, p]) => [k, p, (m.required || []).includes(k), feldTyp(p)]);
}
function feldTyp(p) {
  const t = p.anyOf ? p.anyOf.find(x => x.type !== "null") || {} : p;
  const ref = (t.$ref || "").split("/").pop();
  return ref ? { ...SCHEMA.$defs[ref], ref } : t;
}
// Wert eines Feldes als Text (ohne HTML): Listen mit Komma, Zahlen mit Tausenderpunkt und
// Einheit (einheit, oder einheit_aus: aus einem anderen Feld des Datensatzes x), Anzahl je
// Wert als „3× Sand, 1× Rasen“
function feldText(p, t, v, x = {}) {
  if (p.widget === "sportkomplex") return leer(v) ? "" : komplexName(v);
  if (leer(v) || (typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length)) return "";
  if (Array.isArray(v)) {  // Liste von Werten oder von Objekten (Energieträger, Sanierungen …)
    if (!v.some(x => x && typeof x === "object")) return v.join(", ");
    return v.map(x => Object.values(x).filter(y => !leer(y)).join(" ")).join("; ");
  }
  if (typeof v === "object") return Object.entries(v).map(([k, n]) => `${zahl(n)}× ${k}`).join(", ");
  if ((t.type === "integer" || t.type === "number") && p.widget !== "jahr") {
    const einheit = p.einheit_aus ? x[p.einheit_aus] : p.einheit;
    return zahl(v) + (einheit ? " " + einheit : "");
  }
  return String(v);
}
// Ist ein Feld für diese Sportanlage gedacht? (Angabe fuer: Typen aus modell.MERKMALE). Bei
// einem Typ, den die Liste nicht kennt, gelten alle Felder.
function passtFuer(p, typ) {
  return !p.fuer || !typ || !(typ in ANLAGEN_TYPEN) || p.fuer.includes(typ);
}
// Felder, deren Wert nur als Einheit eines anderen Feldes erscheint (Währung der Baukosten)
function nurEinheit(modell) {
  return new Set(modellFelder(modell).map(([, p]) => p.einheit_aus).filter(Boolean));
}
// Regeln zwischen Feldern (braucht, teil_von) für ein Objekt nach dem Modell → Meldungen
function regelnZwischen(modell, o, praefix = "") {
  const out = [], titel = k => (SCHEMA.$defs[modell].properties[k] || {}).title || k;
  for (const [k, p] of modellFelder(modell)) {
    const w = o[k];
    if (p.braucht && !leer(w) && leer(o[p.braucht])) out.push(`${praefix}${titel(p.braucht)}: nötig, wenn ${p.title} angegeben ist`);
    if (p.nachkommastellen && typeof w === "number" && (String(w).split(".")[1] || "").length < p.nachkommastellen) {
      out.push(`${praefix}${p.title}: mindestens ${p.nachkommastellen} Nachkommastellen (${w} ist zu ungenau)`);
    }
    if (p.teil_von && Array.isArray(w)) {
      const fehlt = w.filter(x => !(o[p.teil_von] || []).includes(x));
      if (fehlt.length) out.push(`${praefix}${p.title}: ${fehlt.join(", ")} fehlt unter ${titel(p.teil_von)}`);
    }
  }
  return out;
}
// ---------- Organisationen (daten/organisationen.json): Vereine, Kommunen, Verbände … ----------
// Sportstätten nennen sie in eigentuemer, betreiber und nutzer beim Namen (auch weitere_namen).
let ORGANISATIONEN = [];
const ORG_NACH_NAME = new Map();
function setzeOrganisationen(liste) {
  ORGANISATIONEN = liste || [];
  ORG_NACH_NAME.clear();
  for (const o of ORGANISATIONEN) for (const n of [o.name, ...(o.weitere_namen || [])]) {
    const k = schluesselName(n);
    if (k && !ORG_NACH_NAME.has(k)) ORG_NACH_NAME.set(k, o);
  }
}
function orgVon(name) { return ORG_NACH_NAME.get(schluesselName(name)) || null; }
// Art auf der Karte (Verein, Kommune, sonstige) aus der Art im Verzeichnis; sonst "" (unbekannt,
// es wird nicht geschätzt)
function orgArt(name) {
  const o = orgVon(name), typen = ATLAS().organisationstypen || {};
  return o && o.typ && typen[o.typ] ? typen[o.typ] : "";
}
function schluesselName(s) { return String(s || "").trim().replace(/\s+/g, " ").toLowerCase(); }

// ---------- Sportkomplexe (daten/sportkomplexe.json): Klammer um mehrere Sportstätten ----------
// Sportstätten verweisen in sportkomplex auf die ID. Mitglieder und, ohne eigene Lage, der
// Mittelpunkt kommen aus dem Bestand.
const SPORTKOMPLEXE = new Map();  // id → { id, name, adresse, lat, lon, mitglieder: [{ id, name, lat, lon }] }
function setzeSportkomplexe(liste, features) {
  SPORTKOMPLEXE.clear();
  for (const k of liste || []) SPORTKOMPLEXE.set(k.id, { ...k, mitglieder: [] });
  for (const f of features || []) {
    const k = SPORTKOMPLEXE.get(f.properties.sportkomplex);
    const [lon, lat] = f.geometry.coordinates;
    if (k) k.mitglieder.push({ id: f.properties.id, name: f.properties.name || f.properties.kategorie, lat, lon });
  }
  for (const k of SPORTKOMPLEXE.values()) {
    const m = k.mitglieder;
    if (k.lat == null && m.length) {
      k.lat = m.reduce((s, x) => s + x.lat, 0) / m.length;
      k.lon = m.reduce((s, x) => s + x.lon, 0) / m.length;
    }
  }
}
// Auswahl „Sportkomplex“ für Filter: alle, in irgendeinem Komplex oder ein bestimmter (nach Namen)
const IN_KOMPLEX = "*";
function komplexeNachName() {
  return [...SPORTKOMPLEXE.values()].sort((a, b) => a.name.localeCompare(b.name, "de"));
}
function komplexAuswahlHtml(wert) {
  const opt = (v, text) => `<option value="${esc(v)}"${v === wert ? " selected" : ""}>${esc(text)}</option>`;
  return `<select data-f="komplex" aria-label="Sportkomplex">${opt("", "alle, mit und ohne Sportkomplex")}`
    + opt(IN_KOMPLEX, "nur in einem Sportkomplex")
    + komplexeNachName().map(k => opt(k.id, k.name)).join("") + `</select>`;
}
function komplexName(id) { const k = SPORTKOMPLEXE.get(id); return k ? k.name : String(id); }
// Zeile im Popup: Name des Komplexes und die anderen Sportstätten darin (öffnen ihre Angaben)
function komplexZeile(id, ohne) {
  const k = SPORTKOMPLEXE.get(id);
  if (!k) return esc(id);
  const andere = k.mitglieder.filter(m => m.id !== ohne);
  return `<b>${esc(k.name)}</b>` + (andere.length ? ", mit " + andere.map(m =>
    `<a href="#" data-details="${esc(m.id)}">${esc(m.name)}</a>`).join(", ") : "")
    + ` · <a href="#" data-nur-komplex="${esc(k.id)}" title="Nur die Sportstätten dieses Komplexes zeigen">`
    + `alle auf der Karte</a>`;
}

// ---------- Stützpunkte (daten/stuetzpunkte.json) ----------
// Je Stützpunkt die Sportstätten: einzeln genannte und die seiner Sportkomplexe
const STUETZPUNKTE = new Map();  // id → { …, alle: Set der Sportstätten-IDs, ebene }
const STP_JE_STAETTE = new Map();  // Sportstätten-ID → [Stützpunkt]
const STP_EBENEN = [["Olympia", "Olympiastützpunkte"], ["Bund", "Bundesstützpunkte"], ["Land", "Landesstützpunkte"]];
const stpEbene = art => /^Olympia/.test(art) ? "Olympia" : /^Bundes/.test(art) ? "Bund" : "Land";
function setzeStuetzpunkte(liste) {
  STUETZPUNKTE.clear(); STP_JE_STAETTE.clear();
  for (const sp of liste || []) {
    const alle = new Set(sp.sportstaetten || []);
    for (const kid of sp.sportkomplexe || []) {
      const k = SPORTKOMPLEXE.get(kid);
      if (k) for (const m of k.mitglieder) alle.add(m.id);
    }
    const x = { ...sp, alle, ebene: stpEbene(sp.art || "") };
    STUETZPUNKTE.set(sp.id, x);
    for (const id of alle) { if (!STP_JE_STAETTE.has(id)) STP_JE_STAETTE.set(id, []); STP_JE_STAETTE.get(id).push(x); }
  }
}
const stuetzpunkteNachName = () => [...STUETZPUNKTE.values()].sort((a, b) => a.name.localeCompare(b.name, "de"));
const datumText = d => leer(d) ? "" : String(d).split("-").reverse().join(".");
// Popup: die Stützpunkte einer Sportstätte (mit Ende der Anerkennung)
function stpZeile(staetteId) {
  return (STP_JE_STAETTE.get(staetteId) || []).map(sp => esc(sp.name)
    + (sp.gueltig_bis ? ` <span class="details">(bis ${esc(datumText(sp.gueltig_bis))})</span>` : "")).join("<br>");
}
// Filter: "" alle, "*" an einem Stützpunkt, "e:Olympia|Bund|Land" je Ebene, sonst die ID
function stpPasst(staetteId, wert) {
  if (!wert) return true;
  const sp = STP_JE_STAETTE.get(staetteId) || [];
  if (wert === "*") return sp.length > 0;
  if (wert.startsWith("e:")) return sp.some(x => x.ebene === wert.slice(2));
  return sp.some(x => x.id === wert);
}
function stpAuswahlHtml(wert) {
  const opt = (v, text) => `<option value="${esc(v)}"${v === wert ? " selected" : ""}>${esc(text)}</option>`;
  return `<select data-f="stp" aria-label="Stützpunkt">${opt("", "alle, mit und ohne Stützpunkt")}`
    + opt("*", "nur an einem Stützpunkt") + STP_EBENEN.map(([e, t]) => opt("e:" + e, "nur " + t)).join("")
    + stuetzpunkteNachName().map(sp => opt(sp.id, sp.name)).join("") + `</select>`;
}

// Werte zählen: ["a", "b", "a"] → { a: 2, b: 1 }
function zaehle(werte) {
  const z = {};
  for (const w of werte) z[w] = (z[w] || 0) + 1;
  return z;
}
// Gefüllte Teile verbinden (Untertitel, Suchtext)
function verbinde(teile, trenner = " · ") { return teile.filter(v => !leer(v)).join(trenner); }
function suchtext(teile) { return verbinde(teile, " ").toLowerCase(); }

// Kopfzeile: Links aus konfig.js. „Sportstätte vorschlagen“ öffnet das Formular,
// „Bug melden“ ein neues Ticket auf GitHub (konfig.js: fehler_url).
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
  ladenEl.className = ""; ladenEl.hidden = false;
  ladenEl.innerHTML = `<span class="kreisel"></span><span>${esc(text)}</span>`;
}
function fertig() { ladenEl.hidden = true; }
function zeigeFehler(text) {
  ladenEl.hidden = false; ladenEl.className = "fehler"; ladenEl.textContent = text;
}
function ladeFehler(fehler) {
  zeigeFehler(location.protocol === "file:"
    ? "Die Seite muss über einen Webserver geöffnet werden (lokal: sportstaettenatlas seite --vorschau)."
    : `Die Daten konnten nicht geladen werden (${fehler.message}).`);
}

// Datei aus daten/ laden; fehlt sie → null
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

// Punkte zu Haufen zusammenfassen, je nach Zoomstufe:
// - unter KREISE_BIS: ein Haufen je Kreis (gruppe(layer) → Schlüssel des Kreises), an der
//   Sportstätte, die dem Mittel seiner Punkte am nächsten liegt (liegt also im Kreis);
// - unter HAUFEN_BIS: alle Punkte bis HAUFEN_PX Bildpunkte um den ersten Punkt eines Haufens
//   (wie Leaflet.markercluster);
// - darüber jeder Punkt einzeln.
// Ein Klick zoomt hinein. Dieselben Methoden wie eine L.layerGroup (addLayer, removeLayer),
// dazu einzeln(layer): diesen Punkt immer zeigen (z. B. für sein Popup), bis das Popup zu ist.
// optionen: gruppe(layer) → Schlüssel oder null, name(schluessel), grenzen(schluessel) → Bounds
const KREISE_BIS = 10, HAUFEN_BIS = 12, HAUFEN_PX = 50;
function haufen(optionen = {}) {
  const punkte = new Set(), sicht = L.layerGroup();
  let karteH = null, geheftet = null, geplant = false;
  const plane = () => {
    if (!karteH || geplant) return;
    geplant = true;
    requestAnimationFrame(() => { geplant = false; zeichne(); });
  };
  function zeichne() {
    if (!karteH) return;
    sicht.clearLayers();
    const z = karteH.getZoom(), rand = karteH.getBounds().pad(0.5);
    if (z >= HAUFEN_BIS) {
      for (const p of punkte) if (p === geheftet || rand.contains(p.getLatLng())) sicht.addLayer(p);
      return;
    }
    // Kreise: alle Punkte (auch außerhalb des Bildes), damit die Zahl den ganzen Kreis zählt
    const kreise = new Map(), rest = [];
    for (const p of punkte) {
      if (p === geheftet) { sicht.addLayer(p); continue; }
      const k = z < KREISE_BIS && optionen.gruppe ? optionen.gruppe(p) : null;
      if (k) (kreise.get(k) || kreise.set(k, []).get(k)).push(p);
      else rest.push(p);
    }
    zeigeKreise(kreise, z);
    // Raster von HAUFEN_PX nur zum schnellen Finden: ein Punkt kommt zum ersten Haufen, dessen
    // Mitte (sein erster Punkt) in den 3 × 3 Nachbarzellen höchstens HAUFEN_PX entfernt ist
    const raster = new Map(), alle = [], r2 = HAUFEN_PX * HAUFEN_PX;
    for (const p of rest) {
      const ll = p.getLatLng();
      if (!rand.contains(ll)) continue;
      const pt = karteH.project(ll, z), cx = Math.floor(pt.x / HAUFEN_PX), cy = Math.floor(pt.y / HAUFEN_PX);
      let ziel = null;
      for (let dx = -1; dx <= 1 && !ziel; dx++) for (let dy = -1; dy <= 1 && !ziel; dy++) {
        for (const h of raster.get((cx + dx) + ":" + (cy + dy)) || []) {
          if ((h.x - pt.x) ** 2 + (h.y - pt.y) ** 2 <= r2) { ziel = h; break; }
        }
      }
      if (ziel) { ziel.g.push(p); continue; }
      const h = { x: pt.x, y: pt.y, g: [p] }, k = cx + ":" + cy;
      (raster.get(k) || raster.set(k, []).get(k)).push(h);
      alle.push(h);
    }
    const zellen = alle.map(h => h.g);
    for (const g of zellen) {
      if (g.length === 1) { sicht.addLayer(g[0]); continue; }
      let lat = 0, lon = 0;
      for (const p of g) { const ll = p.getLatLng(); lat += ll.lat; lon += ll.lng; }
      const m = kreis([lat / g.length, lon / g.length], g.length, "haufen",
        `${zahl(g.length)} Sportstätten – hineinzoomen`);
      m.on("click", () => karteH.fitBounds(L.latLngBounds(g.map(p => p.getLatLng())).pad(0.2),
        { maxZoom: HAUFEN_BIS + 1 }));
      sicht.addLayer(m);
    }
  }
  const groesse = n => (n < 10 ? 28 : n < 100 ? 34 : n < 1000 ? 40 : 46);
  function kreis(ll, n, klasse, titel) {
    const gr = groesse(n);
    return L.marker(ll, { icon: L.divIcon({ className: klasse, html: `<span>${zahl(n)}</span>`,
      iconSize: [gr, gr] }), keyboard: false, title: titel });
  }
  // Ein Haufen je Kreis; liegen zwei zu dicht (kreisfreie Stadt im Landkreis), schieben sie
  // sich auseinander, bis sie sich nicht mehr überdecken
  function zeigeKreise(kreise, z) {
    const blasen = [];
    for (const [k, g] of kreise) {
      if (g.length === 1) { sicht.addLayer(g[0]); continue; }
      let lat = 0, lon = 0;
      for (const p of g) { const ll = p.getLatLng(); lat += ll.lat; lon += ll.lng; }
      lat /= g.length; lon /= g.length;
      let ort = null, best = Infinity;
      for (const p of g) {
        const ll = p.getLatLng(), d = (ll.lat - lat) ** 2 + ((ll.lng - lon) * 0.64) ** 2;
        if (d < best) { best = d; ort = ll; }
      }
      blasen.push({ k, g, pt: karteH.project(ort, z), r: groesse(g.length) / 2 });
    }
    for (let runde = 0; runde < 40; runde++) {
      let bewegt = false;
      for (let i = 0; i < blasen.length; i++) for (let j = i + 1; j < blasen.length; j++) {
        const a = blasen[i], b = blasen[j], dx = b.pt.x - a.pt.x, dy = b.pt.y - a.pt.y;
        const d = Math.hypot(dx, dy) || 0.01, soll = a.r + b.r + 3;
        if (d >= soll) continue;
        const s = (soll - d) / 2 / d;
        a.pt = L.point(a.pt.x - dx * s, a.pt.y - dy * s);
        b.pt = L.point(b.pt.x + dx * s, b.pt.y + dy * s);
        bewegt = true;
      }
      if (!bewegt) break;
    }
    for (const { k, g, pt } of blasen) {
      const name = optionen.name ? optionen.name(k) : "";
      const m = kreis(karteH.unproject(pt, z), g.length, "haufen kreis",
        `${name ? name + ": " : ""}${zahl(g.length)} Sportstätten – hineinzoomen`);
      const grenzen = (optionen.grenzen && optionen.grenzen(k))
        || L.latLngBounds(g.map(p => p.getLatLng())).pad(0.1);
      m.on("click", () => karteH.fitBounds(grenzen, { maxZoom: HAUFEN_BIS - 1 }));
      sicht.addLayer(m);
    }
  }
  const ebene = {
    addLayer(p) { punkte.add(p); plane(); return ebene; },
    removeLayer(p) { punkte.delete(p); if (p === geheftet) geheftet = null; plane(); return ebene; },
    hasLayer: p => punkte.has(p),
    einzeln(p) {
      geheftet = p;
      p.once("popupclose", () => { if (geheftet === p) { geheftet = null; plane(); } });
      zeichne();
    },
    addTo(m) {
      karteH = m; sicht.addTo(m); m.on("zoomend moveend", plane); zeichne(); return ebene;
    },
    remove() {
      if (karteH) { karteH.off("zoomend moveend", plane); karteH.removeLayer(sicht); }
      karteH = null; return ebene;
    },
  };
  return ebene;
}

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
// Amtliches Luftbild (DOP20, LVermGeo RLP, dl-de/by-2-0): Bild von etwa 200 × 200 m mit der
// Stelle in der Mitte, direkt vom WMS des Landes
const LUFTBILD_WMS = "https://geo4.service24.rlp.de/wms/rp_dop20.fcgi";
function luftbildUrl(lat, lon, halbeSeiteM = 100) {
  const dLat = halbeSeiteM / 111320, dLon = dLat / Math.cos(lat * Math.PI / 180);
  const bbox = [lon - dLon, lat - dLat, lon + dLon, lat + dLat].map(x => x.toFixed(6)).join(",");
  return `${LUFTBILD_WMS}?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=rp_dop20&STYLES=`
    + `&SRS=EPSG:4326&BBOX=${bbox}&WIDTH=1000&HEIGHT=1000&FORMAT=image/jpeg`;
}
// Links zu Google Maps und zum Luftbild für eine Stelle
function kartenLinks(lat, lon) {
  const t = `${(+lat).toFixed(6)}, ${(+lon).toFixed(6)}`;
  return `<a href="https://www.google.com/maps?q=${encodeURIComponent(t)}" target="_blank" `
    + `rel="noopener">Google Maps</a> · <a href="${luftbildUrl(+lat, +lon)}" target="_blank" `
    + `rel="noopener" title="Amtliches Luftbild (DOP20, © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0), `
    + `etwa 200 × 200 m, die Stelle in der Mitte">Luftbild</a>`;
}
// Koordinaten im Format von Google Maps ("Breite, Länge"), zum Kopieren
function koord(lat, lon) {
  if (leer(lat) || leer(lon)) return "";
  const t = `${(+lat).toFixed(6)}, ${(+lon).toFixed(6)}`;
  return `<tr><td>Koordinaten</td><td><span class="koord">${t}</span> `
    + `${kartenLinks(lat, lon)}</td></tr>`;
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
function punktGrenzen(lat, lon) { return L.latLngBounds([[lat, lon], [lat, lon]]); }
const svgRenderer = L.svg({ padding: 0.3 });

// Panel rechts oben (Filter, Legende): Klicks und Scrollen gehen nicht an die Karte.
// Zahlen stehen in <span class="n" data-n="schlüssel"> und werden je Gebiet neu gesetzt.
function panelDiv(klasse) {
  const div = L.DomUtil.create("div", "panel " + klasse);
  L.DomEvent.disableClickPropagation(div);
  L.DomEvent.disableScrollPropagation(div);
  return div;
}
function nSpan(k) { return `<span class="n" data-n="${esc(k)}"></span>`; }
function setzeZahlen(div, zaehler) {
  div.querySelectorAll("[data-n]").forEach(el => {
    const w = zaehler[el.dataset.n] || 0;
    el.textContent = zahl(w);
    el.closest("label").classList.toggle("null", !w);
  });
}

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
// Jede Ansicht ist ein Objekt mit titel, zeigen(), verbergen() und optional starte()
// (einmal, darf Daten laden), aktualisiere() (Karte verschoben), gebietGeaendert(),
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
      if (a.starte) await a.starte();
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
