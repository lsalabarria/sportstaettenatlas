// Stützpunkte (daten/stuetzpunkte.json)
// Je Stützpunkt die Sportstätten: einzeln genannte und die seiner Sportkomplexe
import { esc, leer } from "../lib/text.js";
import { SPORTKOMPLEXE } from "./sportkomplexe.js";

export const STUETZPUNKTE = new Map();  // id → { …, alle: Set der Sportstätten-IDs, ebene }
export const STP_JE_STAETTE = new Map();  // Sportstätten-ID → [Stützpunkt]
export const STP_EBENEN = [["Olympia", "Olympiastützpunkte"], ["Bund", "Bundesstützpunkte"], ["Land", "Landesstützpunkte"]];
const stpEbene = art => /^Olympia/.test(art) ? "Olympia" : /^Bundes/.test(art) ? "Bund" : "Land";
export function setzeStuetzpunkte(liste) {
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
export const stuetzpunkteNachName = () => [...STUETZPUNKTE.values()].sort((a, b) => a.name.localeCompare(b.name, "de"));
export const datumText = d => leer(d) ? "" : String(d).split("-").reverse().join(".");
// Popup: die Stützpunkte einer Sportstätte (mit Ende der Anerkennung)
export function stpZeile(staetteId) {
  return (STP_JE_STAETTE.get(staetteId) || []).map(sp => esc(sp.name)
    + (sp.gueltig_bis ? ` <span class="details">(bis ${esc(datumText(sp.gueltig_bis))})</span>` : "")).join("<br>");
}
// Filter: "" alle, "*" an einem Stützpunkt, "e:Olympia|Bund|Land" je Ebene, sonst die ID
export function stpPasst(staetteId, wert) {
  if (!wert) return true;
  const sp = STP_JE_STAETTE.get(staetteId) || [];
  if (wert === "*") return sp.length > 0;
  if (wert.startsWith("e:")) return sp.some(x => x.ebene === wert.slice(2));
  return sp.some(x => x.id === wert);
}
export function stpAuswahlHtml(wert) {
  const opt = (v, text) => `<option value="${esc(v)}"${v === wert ? " selected" : ""}>${esc(text)}</option>`;
  return `<select data-f="stp" aria-label="Stützpunkt">${opt("", "alle, mit und ohne Stützpunkt")}`
    + opt("*", "nur an einem Stützpunkt") + STP_EBENEN.map(([e, t]) => opt("e:" + e, "nur " + t)).join("")
    + stuetzpunkteNachName().map(sp => opt(sp.id, sp.name)).join("") + `</select>`;
}
