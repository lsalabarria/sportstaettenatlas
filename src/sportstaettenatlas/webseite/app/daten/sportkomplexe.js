// Sportkomplexe (daten/sportkomplexe.json): Klammer um mehrere Sportstätten
// Sportstätten verweisen in sportkomplex auf die ID. Mitglieder und, ohne eigene Lage, der
// Mittelpunkt kommen aus dem Bestand.
import { esc } from "../lib/text.js";

export const SPORTKOMPLEXE = new Map();  // id → { id, name, adresse, lat, lon, mitglieder: [{ id, name, lat, lon }] }
export function setzeSportkomplexe(liste, features) {
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
export const IN_KOMPLEX = "*";
export function komplexeNachName() {
  return [...SPORTKOMPLEXE.values()].sort((a, b) => a.name.localeCompare(b.name, "de"));
}
export function komplexAuswahlHtml(wert) {
  const opt = (v, text) => `<option value="${esc(v)}"${v === wert ? " selected" : ""}>${esc(text)}</option>`;
  return `<select data-f="komplex" aria-label="Sportkomplex">${opt("", "alle, mit und ohne Sportkomplex")}`
    + opt(IN_KOMPLEX, "nur in einem Sportkomplex")
    + komplexeNachName().map(k => opt(k.id, k.name)).join("") + `</select>`;
}
export function komplexName(id) { const k = SPORTKOMPLEXE.get(id); return k ? k.name : String(id); }
// Zeile im Popup: Name des Komplexes und die anderen Sportstätten darin (öffnen ihre Angaben)
export function komplexZeile(id, ohne) {
  const k = SPORTKOMPLEXE.get(id);
  if (!k) return esc(id);
  const andere = k.mitglieder.filter(m => m.id !== ohne);
  return `<b>${esc(k.name)}</b>` + (andere.length ? ", mit " + andere.map(m =>
    `<a href="#" data-details="${esc(m.id)}">${esc(m.name)}</a>`).join(", ") : "")
    + ` · <a href="#" data-nur-komplex="${esc(k.id)}" title="Nur die Sportstätten dieses Komplexes zeigen">`
    + `alle auf der Karte</a>`;
}
