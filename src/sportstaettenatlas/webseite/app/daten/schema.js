// Datenmodell (daten/schema.json, erzeugt aus src/sportstaettenatlas/modell/)
// Felder, Beschriftungen (title), Auswahllisten (enum), Regeln (minimum, pattern …) und
// Angaben für die Webseite (gruppe, widget, formular, uebersicht, einheit) stehen nur dort.
import { leer, zahl } from "../lib/text.js";
import { ANLAGEN_TYPEN } from "./anlagen.js";
import { komplexName } from "./sportkomplexe.js";

export let SCHEMA = { $defs: {} };
export function setzeSchema(schema) { SCHEMA = schema; }
// Zuordnungen und Regeln ohne eigenes Feld (modell.schema: "atlas"): Organisationstypen,
// ALKIS-Typgruppe → Kategorie, Muster für E-Mail-Adressen
export const ATLAS = () => SCHEMA.atlas || {};
export const enthaeltEmail = x => !!ATLAS().email && new RegExp(ATLAS().email).test(JSON.stringify(x));
// Felder eines Modells: [[Name, Eigenschaft, Pflicht, Typ]] – Typ ohne „oder leer“, Verweise
// aufgelöst (z. B. adresse → Adresse mit ref: "Adresse")
export function modellFelder(modell) {
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
export function feldText(p, t, v, x = {}) {
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
export function passtFuer(p, typ) {
  return !p.fuer || !typ || !(typ in ANLAGEN_TYPEN) || p.fuer.includes(typ);
}
// Felder, deren Wert nur als Einheit eines anderen Feldes erscheint (Währung der Baukosten)
export function nurEinheit(modell) {
  return new Set(modellFelder(modell).map(([, p]) => p.einheit_aus).filter(Boolean));
}
// Grenzen und Muster der Prüfungen (modell.PRUEFUNG) und Meldungen (modell.MELDUNGEN)
export const PRUEFUNG = () => ATLAS().pruefung || {};
const meldung = (regel, werte) =>
  (ATLAS().meldungen || {})[regel].replace(/\{(\w+)\}/g, (_, k) => werte[k]);
// Regeln zwischen Feldern (braucht, nachkommastellen, teil_von) für ein Objekt nach dem Modell
// → [{ regel, feld, text }]. Dieselbe Rechnung wie modell.zwischen_feldern (Python);
// tests/regeln_faelle.json prüft beide. Im Text steht der Titel des Feldes, nicht sein Name.
export function regelFunde(modell, o, praefix = "") {
  const out = [], titel = k => (SCHEMA.$defs[modell].properties[k] || {}).title || k;
  for (const [k, p] of modellFelder(modell)) {
    const w = o[k];
    if (p.braucht && !leer(w) && leer(o[p.braucht])) {
      out.push({ regel: "braucht", feld: p.braucht,
        text: praefix + meldung("braucht", { feld: titel(p.braucht), wenn: p.title }) });
    }
    if (p.nachkommastellen && typeof w === "number"
        && (String(w).split(".")[1] || "").length < p.nachkommastellen) {
      out.push({ regel: "nachkommastellen", feld: k,
        text: praefix + meldung("nachkommastellen", { feld: p.title, n: p.nachkommastellen, wert: w }) });
    }
    if (p.teil_von && Array.isArray(w) && w.length) {
      const fehlt = w.filter(x => !(o[p.teil_von] || []).includes(x));
      if (fehlt.length) out.push({ regel: "teil_von", feld: k,
        text: praefix + meldung("teil_von", { feld: p.title, fehlt: fehlt.join(", "), unter: titel(p.teil_von) }) });
    }
  }
  return out;
}
export const regelnZwischen = (modell, o, praefix = "") => regelFunde(modell, o, praefix).map(f => f.text);
