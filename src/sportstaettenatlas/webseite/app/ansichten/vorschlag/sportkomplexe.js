// Sportkomplexe; Auswahl der Art des Vorschlags.
import { z } from "./zustand.js";
import { zeigeTeile } from "./anlagen.js";
import { F } from "./formular.js";
import { neueStaette, neueStaettenDaten } from "./neue_objekte.js";
import { sende } from "./senden.js";
import { neuChip } from "./stuetzpunkte.js";
import { regelFehler } from "./hilfen.js";
import { orgVon } from "../../daten/organisationen.js";
import { enthaeltEmail } from "../../daten/schema.js";
import { SPORTKOMPLEXE, komplexName } from "../../daten/sportkomplexe.js";
import { esc, leer } from "../../lib/text.js";
import { hole, setze } from "../../lib/vergleich.js";

// --- Sportkomplexe ---
// Komplex zum Ändern wählen (ID) oder null für einen neuen, dann mit den Sportstätten `vorbelegt`
export function waehleKomplex(id, vorbelegt = []) {
  z.koOriginal = id ? SPORTKOMPLEXE.get(id) || null : null;
  for (const f of z.KO_FELDER) { const w = z.koOriginal ? hole(z.koOriginal, f.k) : ""; F(f.pfad).value = leer(w) ? "" : w; }
  z.koStaetten = new Set(z.koOriginal ? z.koOriginal.mitglieder.map(m => m.id) : vorbelegt);
  z.neueStaetten = z.neueStaetten.filter(n => n.ziel !== "sportkomplex");
  if (F("ko-loeschen")) F("ko-loeschen").checked = false;
  const g = z.el.querySelector("#v-ko-gewaehlt");
  g.innerHTML = z.koOriginal ? `<div class="chip">Sie ändern: <b>${esc(z.koOriginal.name)}</b> `
    + `<button type="button">stattdessen einen neuen</button></div>` : "";
  const b = g.querySelector("button");
  if (b) b.addEventListener("click", () => { waehleKomplex(null); zeigeTeile(); });
  zeigeKoStaetten();
}
export function zeigeKoStaetten() {
  const c = z.el.querySelector("#v-ko-staetten");
  c.innerHTML = [...z.koStaetten].map(id => {
    const e = z.NACH_ID.get(id), anders = e && e.p.sportkomplex && (!z.koOriginal || e.p.sportkomplex !== z.koOriginal.id);
    if (neueStaette(id)) return neuChip(id, "sportkomplex", "data-ko-weg");
    return `<span class="chip-s">${esc(e ? e.p.name || e.kat : id)}`
      + (anders ? ` <small>(bisher in ${esc(komplexName(e.p.sportkomplex))})</small>` : "")
      + `<button type="button" data-ko-weg="${esc(id)}" aria-label="entfernen">×</button></span>`;
  }).join("") || `<span class="hinweis">noch keine</span>`;
  c.querySelectorAll("[data-ko-weg]").forEach(b => b.addEventListener("click", () => {
    z.koStaetten.delete(b.dataset.koWeg); zeigeKoStaetten(); }));
}
export function koWerte() {
  const k = {};
  for (const f of z.KO_FELDER) { const x = String(F(f.pfad).value || "").trim(); if (x) setze(k, f.k, x); }
  return k;
}
export function weiterKomplex(v) {
  const k = koWerte(), loeschen = !!(F("ko-loeschen") && F("ko-loeschen").checked), fehler = [];
  if (!loeschen) {
    for (const f of z.KO_FELDER) fehler.push(...regelFehler(f, hole(k, f.k), f.p.title));
    if (z.koStaetten.size < 2) fehler.push("Sportstätten: mindestens zwei – ein Sportkomplex fasst mehrere zusammen");
  }
  if (enthaeltEmail(k)) fehler.push("Bitte keine E-Mail-Adressen eintragen");
  const geaendert = z.koOriginal ? z.KO_FELDER.map(f => f.k).filter(x => (hole(z.koOriginal, x) || "") !== (hole(k, x) || "")) : [];
  const vorher = new Set(z.koOriginal ? z.koOriginal.mitglieder.map(m => m.id) : []);
  const gleich = vorher.size === z.koStaetten.size && [...z.koStaetten].every(id => vorher.has(id));
  if (z.koOriginal && !loeschen && !geaendert.length && gleich && !v.anmerkung) {
    fehler.push("Änderung: Name, Adresse oder Sportstätten ändern, auflösen wählen oder eine Anmerkung schreiben");
  }
  const daten = { version: 1, art: "sportkomplex" };
  if (z.koOriginal) daten.sportkomplex_id = z.koOriginal.id;
  if (loeschen) daten.loeschen = true;
  else {
    daten.sportkomplex = k;
    daten.sportstaetten = [...z.koStaetten];
    const neue = neueStaettenDaten(z.koStaetten);
    if (neue.length) daten.neue_sportstaetten = neue;
    if (z.koOriginal && geaendert.length) daten.geaendert = geaendert;
  }
  sende(daten, v, fehler);
}
// Eigentümer/Betreiber: steht die Organisation im Verzeichnis, ihre Art übernehmen (wenn
// noch keine gewählt ist); dahinter steht, ob sie im Verzeichnis ist (geschätzt wird nicht)
export function zeigeArten() {
  for (const f of z.FELDER.filter(x => x.p.widget === "organisation")) {
    const name = F(f.pfad).value, o = orgVon(name), s = z.el.querySelector(`[data-art="${f.pfad}"]`);
    const typ = F(f.pfad + "_typ");
    // die Art aus dem Verzeichnis folgt dem Namen, solange niemand sie selbst gewählt hat
    const vonVerzeichnis = typ && typ.dataset.vonOrg && typ.value === typ.dataset.vonTyp;
    if (typ && (vonVerzeichnis || !typ.value) && typ.dataset.vonOrg !== name) {
      typ.value = o && o.typ ? o.typ : vonVerzeichnis ? "" : typ.value;
      typ.dataset.vonOrg = o && o.typ ? name : "";
      typ.dataset.vonTyp = typ.value;
    }
    const a = !name.trim() ? "" : o ? "im Verzeichnis" + (o.typ ? "" : ", ohne Art") : "nicht im Verzeichnis";
    s.textContent = a; s.hidden = !a;
  }
}
