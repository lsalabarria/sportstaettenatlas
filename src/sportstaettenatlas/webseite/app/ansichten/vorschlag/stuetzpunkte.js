// Stützpunkte.
import { z } from "./zustand.js";
import { zeigeTeile } from "./anlagen.js";
import { F, zeigeChips } from "./formular.js";
import { neueStaette, neueStaettenDaten, staettenName } from "./neue_objekte.js";
import { sende } from "./senden.js";
import { regelFehler } from "./hilfen.js";
import { enthaeltEmail } from "../../daten/schema.js";
import { SPORTKOMPLEXE, komplexName } from "../../daten/sportkomplexe.js";
import { STUETZPUNKTE } from "../../daten/stuetzpunkte.js";
import { esc, leer } from "../../lib/text.js";

// --- Stützpunkte ---
export function waehleStuetzpunkt(id, vorbelegt = []) {
  z.spOriginal = id ? STUETZPUNKTE.get(id) || null : null;
  for (const f of z.SP_FELDER) {
    const w = z.spOriginal ? z.spOriginal[f.k] : null;
    if (f.p.widget === "chips") { z.chips[f.pfad] = new Set(w || []); zeigeChips(f.pfad); continue; }
    F(f.pfad).value = leer(w) ? "" : w;
  }
  z.spStaetten = new Set(z.spOriginal ? z.spOriginal.sportstaetten || [] : vorbelegt);
  z.neueStaetten = z.neueStaetten.filter(n => n.ziel !== "stuetzpunkt");
  z.spKomplexe = new Set(z.spOriginal ? z.spOriginal.sportkomplexe || [] : []);
  if (F("stp-loeschen")) F("stp-loeschen").checked = false;
  const g = z.el.querySelector("#v-stp-gewaehlt");
  g.innerHTML = z.spOriginal ? `<div class="chip">Sie ändern: <b>${esc(z.spOriginal.name)}</b> `
    + `<button type="button">stattdessen einen neuen</button></div>` : "";
  const b = g.querySelector("button");
  if (b) b.addEventListener("click", () => { waehleStuetzpunkt(null); zeigeTeile(); });
  zeigeSpStaetten();
}
export const neuChip = (ref, ziel, weg) => `<span class="chip-s neu"><a href="#" data-neu-bearbeiten="${esc(ref)}" `
  + `data-ziel="${ziel}" title="Angaben ändern">${esc(staettenName(ref))}</a>`
  + `<button type="button" ${weg}="${esc(ref)}" aria-label="entfernen">×</button></span>`;
export function zeigeSpStaetten() {
  const c = z.el.querySelector("#v-stp-staetten");
  const imKo = new Set([...z.spKomplexe].flatMap(k => (SPORTKOMPLEXE.get(k) || { mitglieder: [] }).mitglieder.map(m => m.id)));
  c.innerHTML = [...z.spKomplexe].map(id => `<span class="chip-s">Sportkomplex ${esc(komplexName(id))}`
    + `<button type="button" data-sp-ko-weg="${esc(id)}" aria-label="entfernen">×</button></span>`).join("")
    + [...z.spStaetten].map(id => {
      const e = z.NACH_ID.get(id);
      if (neueStaette(id)) return neuChip(id, "stuetzpunkt", "data-sp-st-weg");
      return `<span class="chip-s">${esc(e ? e.p.name || e.kat : id)}`
        + (imKo.has(id) ? ` <small>(schon über den Sportkomplex)</small>` : "")
        + `<button type="button" data-sp-st-weg="${esc(id)}" aria-label="entfernen">×</button></span>`;
    }).join("") || `<span class="hinweis">noch keine</span>`;
  c.querySelectorAll("[data-sp-ko-weg]").forEach(b => b.addEventListener("click", () => {
    z.spKomplexe.delete(b.dataset.spKoWeg); zeigeSpStaetten(); }));
  c.querySelectorAll("[data-sp-st-weg]").forEach(b => b.addEventListener("click", () => {
    z.spStaetten.delete(b.dataset.spStWeg); zeigeSpStaetten(); }));
}
export function spWerte() {
  const sp = {};
  for (const f of z.SP_FELDER) {
    const w = f.p.widget === "chips" ? [...z.chips[f.pfad]] : String(F(f.pfad).value || "").trim();
    if (!leer(w) && !(Array.isArray(w) && !w.length)) sp[f.k] = w;
  }
  if (z.spStaetten.size) sp.sportstaetten = [...z.spStaetten];
  if (z.spKomplexe.size) sp.sportkomplexe = [...z.spKomplexe];
  return sp;
}
export function weiterStuetzpunkt(v) {
  const sp = spWerte(), loeschen = !!(F("stp-loeschen") && F("stp-loeschen").checked), fehler = [];
  if (!loeschen) {
    for (const f of z.SP_FELDER) fehler.push(...regelFehler(f, sp[f.k], f.p.title));
    if (!z.spStaetten.size && !z.spKomplexe.size) fehler.push("Sportstätten: mindestens eine Sportstätte oder einen Sportkomplex wählen");
    if (sp.gueltig_ab && sp.gueltig_bis && sp.gueltig_bis < sp.gueltig_ab) fehler.push("Gültig bis: liegt vor „Gültig ab“");
  }
  if (enthaeltEmail(sp)) fehler.push("Bitte keine E-Mail-Adressen eintragen");
  const gleich = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
  const felder = [...z.SP_FELDER.map(f => f.k), "sportstaetten", "sportkomplexe"];
  const geaendert = z.spOriginal ? felder.filter(k => !gleich(
    Array.isArray(z.spOriginal[k]) && !z.spOriginal[k].length ? undefined : z.spOriginal[k], sp[k])) : [];
  if (z.spOriginal && !loeschen && !geaendert.length && !v.anmerkung) {
    fehler.push("Änderung: Angaben oder Sportstätten ändern, löschen wählen oder eine Anmerkung schreiben");
  }
  const daten = { version: 1, art: "stuetzpunkt" };
  if (z.spOriginal) daten.stuetzpunkt_id = z.spOriginal.id;
  if (loeschen) daten.loeschen = true;
  else {
    daten.stuetzpunkt = sp;
    if (z.spOriginal && geaendert.length) daten.geaendert = geaendert;
    const neue = neueStaettenDaten(z.spStaetten);
    if (neue.length) daten.neue_sportstaetten = neue;
  }
  sende(daten, v, fehler);
}
