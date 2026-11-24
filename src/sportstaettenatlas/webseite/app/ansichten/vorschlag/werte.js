// Werte lesen und setzen; einen Vorschlag beginnen.
import { z } from "./zustand.js";
import { anlageZeile, anlagenListe, zeigeTeile } from "./anlagen.js";
import { F, istZahl, zeigeChips } from "./formular.js";
import { setzeLage } from "./karte.js";
import { nkWerte, zeigeNkStaetten } from "./neue_objekte.js";
import { orgWerte } from "./organisationen.js";
import { planePruefung } from "./pruefung.js";
import { zeigeArten } from "./sportkomplexe.js";
import { NEUER_KOMPLEX } from "./hilfen.js";
import { esc, leer, verbinde } from "../../lib/text.js";
import { hole, listeAus, setze } from "../../lib/vergleich.js";

// --- Werte lesen und setzen (Sportstätte verschachtelt wie im Modell) ---
export function leseFeld(f) {
  if (f.p.widget === "sportkomplex" && F(f.pfad).value === NEUER_KOMPLEX) return null;
  if (f.p.widget === "karte") return z.lage ? { lon: +z.lage[1].toFixed(6), lat: +z.lage[0].toFixed(6) } : null;
  if (f.p.widget === "chips" || f.p.widget === "organisationen") return [...z.chips[f.pfad]];
  const x = String(F(f.pfad).value || "").trim();
  if (x === "") return f.t.type === "array" ? [] : null;
  if (istZahl(f.t)) return Number(x.replace(",", "."));
  return f.t.type === "array" ? listeAus(x) : x;
}
export function werte() {
  const s = {};
  for (const f of z.FELDER) setze(s, f.pfad, leseFeld(f));
  return { art: F("art").value, sportstaette: s, anlagenliste: anlagenListe(), organisation: orgWerte(),
    neuer_sportkomplex: nkWerte(),
    loeschen: !!(F("org-loeschen") && F("org-loeschen").checked),
    anmerkung: (F("anmerkung").value || "").trim() };
}
export function fuelle(v) {
  for (const f of z.FELDER) {
    const w = hole(v, f.pfad);
    if (f.p.widget === "karte") continue;
    if (f.p.widget === "chips" || f.p.widget === "organisationen") { z.chips[f.pfad] = new Set(w || []); zeigeChips(f.pfad); continue; }
    if (f.p.widget === "ja_nein") {
      const x = w === "ja" || w === "nein" ? w : "";
      z.form.querySelectorAll(`input[name="${f.pfad}"]`).forEach(i => { i.checked = i.value === x; });
      continue;
    }
    const e = F(f.pfad);
    if (e.tagName === "SELECT" && !leer(w) && ![...e.options].some(o => o.value === w)) e.add(new Option(w));
    e.value = leer(w) ? "" : Array.isArray(w) ? w.join(", ") : w;
  }
  F("anmerkung").value = v.anmerkung || "";
  z.nkStaetten = new Set();
  for (const f of z.KO_FELDER) F("nk." + f.k).value = "";
  zeigeNkStaetten();
  z.el.querySelector("#v-anlagen").innerHTML = "";
  for (const a of v.anlagen || []) anlageZeile(a);
  setzeLage(v.lage ? v.lage.lat : null, v.lage ? v.lage.lon : null, true);
  zeigeArten();
}
// Sportstätte aus dem Datenbestand → Werte für das Formular (Teile der Adresse stehen flach)
export function ausEintrag(e) {
  const s = {};
  for (const f of z.FELDER) {
    setze(s, f.pfad, f.p.widget === "karte" ? { lon: e.lon, lat: e.lat } : e.p[f.pfad.split(".").pop()]);
  }
  return { ...s, anlagen: e.anlagen || [] };
}
export function zeigeGewaehlt() {
  const g = z.el.querySelector("#v-gewaehlt");
  const was = F("art").value === "anlagen" ? "die Sportanlagen von" : "die Angaben und Sportanlagen von";
  g.innerHTML = z.original && !["organisation", "sportkomplex", "stuetzpunkt"].includes(F("art").value) ? `<div class="chip">Sie ändern ${was}: <b>${esc(z.original.p.name || z.original.kat)}</b> `
    + `<span class="q">${esc(verbinde([z.original.p.kategorie, z.original.p.adresse]))}</span>`
    + ` <button type="button">andere wählen</button></div>` : "";
  const b = g.querySelector("button");
  if (b) b.addEventListener("click", () => { z.original = null; zeigeGewaehlt();
    z.el.querySelector("#v-auswahl").hidden = false; z.el.querySelector("#v-suche").focus(); planePruefung(); });
  z.el.querySelector("#v-auswahl").hidden = !(["aenderung", "anlagen"].includes(F("art").value) && !z.original);
}
// Formular neu füllen: für eine neue Sportstätte (eintrag = null) oder eine vorhandene
export function beginne(art, eintrag, vorgabe) {
  z.original = eintrag;
  z.form.reset();
  F("art").value = art;
  fuelle(vorgabe);
  zeigeTeile();
  zeigeGewaehlt();
  z.el.querySelector("#v-ausgabe").innerHTML = "";
  z.el.querySelector("#v-fehler").hidden = true;
}
export function neu(vorgabe = {}) {
  z.neueStaetten = []; z.neueOrgs.clear(); z.unter = null;
  beginne("neu", null, vorgabe);
}
export function bearbeite(id, art = "aenderung") {
  const e = z.NACH_ID.get(id);
  if (!e) return;
  if (z.vkarte) z.vkarte.closePopup();
  beginne("aenderung", e, ausEintrag(e));
  if (art === "anlagen") z.el.querySelector("#v-teil-anlagen").scrollIntoView({ block: "start" });
}
