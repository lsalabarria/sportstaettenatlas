// Organisationen (daten/organisationen.json): Vereine, Kommunen, Verbände …
// Sportstätten nennen sie in eigentuemer, betreiber und nutzer beim Namen (auch weitere_namen).
import { schluesselName } from "../lib/text.js";
import { normName } from "../lib/vergleich.js";
import { ATLAS, PRUEFUNG } from "./schema.js";

export let ORGANISATIONEN = [];
const ORG_NACH_NAME = new Map();
export function setzeOrganisationen(liste) {
  ORGANISATIONEN = liste || [];
  ORG_NACH_NAME.clear();
  for (const o of ORGANISATIONEN) for (const n of [o.name, ...(o.weitere_namen || [])]) {
    const k = schluesselName(n);
    if (k && !ORG_NACH_NAME.has(k)) ORG_NACH_NAME.set(k, o);
  }
}
export function orgVon(name) { return ORG_NACH_NAME.get(schluesselName(name)) || null; }
// Art auf der Karte (Verein, Kommune, sonstige) aus der Art im Verzeichnis; sonst "" (unbekannt,
// es wird nicht geschätzt)
export function orgArt(name) {
  const o = orgVon(name), typen = ATLAS().organisationstypen || {};
  return o && o.typ && typen[o.typ] ? typen[o.typ] : "";
}
// Name einer Organisation ohne Rechtsform („TuS Berg e.V.“ → „tus berg“; Muster aus dem Modell)
export const orgKern = n => normName(n).replace(new RegExp(PRUEFUNG().rechtsform, "g"), " ")
  .replace(/\s+/g, " ").trim();
