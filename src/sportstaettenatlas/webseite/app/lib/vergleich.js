// Namen vergleichen, Abstände, Lage in Flächen, Pfade in Objekten (wie bestand/pruefung.py).
// norm_name, aehnlich, abstand_m und org_kern rechnen in bestand/pruefung.py (Python) genauso;
// tests/regeln_faelle.json prüft beide
import { leer } from "./text.js";

export function normName(s) {
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
export function aehnlich(a, b) {
  if (!normName(a) || !normName(b)) return 0;
  const x = bigramme(a), y = bigramme(b);
  let gemeinsam = 0, n = 0;
  for (const [k, v] of x) { n += v; gemeinsam += Math.min(v, y.get(k) || 0); }
  for (const v of y.values()) n += v;
  return n ? 2 * gemeinsam / n : 0;
}
export function abstand(lat1, lon1, lat2, lon2) {
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
export function punktIn(lon, lat, g) {
  const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
  return polys.some(p => p.length && imRing(lon, lat, p[0]) && !p.slice(1).some(l => imRing(lon, lat, l)));
}
// Name, unter dem eine Kommune als Eigentümer/Betreiber erscheint: "Ortsgemeinde X", "Stadt Y"
export function zerlegeAdresse(text) {
  // "Musterstraße 12a, 56068 Koblenz" → Teile; sonst alles als Straße
  const m = /^\s*(.*?)(?:\s+(\d+\s?[a-zA-Z]?(?:\s?[-–]\s?\d+[a-zA-Z]?)?))?\s*,\s*(\d{5})\s+(.+?)\s*$/.exec(text || "");
  if (!m) return { strasse: text || "" };
  return { strasse: m[1] || "", hausnummer: m[2] || "", plz: m[3], ort: m[4] };
}

// Werte in verschachtelten Objekten über Pfade wie "adresse.plz"
export function hole(o, pfad) { return pfad.split(".").reduce((x, k) => (x == null ? undefined : x[k]), o); }
export function setze(o, pfad, w) {
  const teile = pfad.split(".");
  let x = o;
  for (const k of teile.slice(0, -1)) x = x[k] ??= {};
  x[teile[teile.length - 1]] = w;
}
// leere Werte weglassen (wie beim Speichern in daten/)
export function ohneLeere(o) {
  if (Array.isArray(o)) return o.map(ohneLeere).filter(v => !leer(v));
  if (o && typeof o === "object") {
    const r = {};
    for (const [k, v] of Object.entries(o)) {
      const w = ohneLeere(v);
      if (!leer(w) && !(w && typeof w === "object" && !Array.isArray(w) && !Object.keys(w).length)) r[k] = w;
    }
    return r;
  }
  return o;
}
export const listeAus = x => String(x || "").split(/[,;]/).map(t => t.trim()).filter(Boolean);
