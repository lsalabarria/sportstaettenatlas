// Neuer Sportkomplex, neue Sportstätten und neue Organisationen innerhalb eines Vorschlags.
import { z } from "./zustand.js";
import { anlageModell, zeigeTeile } from "./anlagen.js";
import { F, zeigeChips } from "./formular.js";
import { komplexAuswahl } from "./karte.js";
import { planePruefung, regelVerstoesse, zeigeFehlerliste } from "./pruefung.js";
import { zeigeArten, zeigeKoStaetten } from "./sportkomplexe.js";
import { zeigeSpStaetten } from "./stuetzpunkte.js";
import { fuelle, zeigeGewaehlt } from "./werte.js";
import { NEUER_KOMPLEX, regelFehler } from "./hilfen.js";
import { ORGANISATIONEN, orgKern, orgVon } from "../../daten/organisationen.js";
import { PRUEFUNG, enthaeltEmail } from "../../daten/schema.js";
import { komplexName } from "../../daten/sportkomplexe.js";
import { esc, schluesselName, verbinde, zahl } from "../../lib/text.js";
import { aehnlich, hole, normName, ohneLeere, setze } from "../../lib/vergleich.js";

// Beim Anlegen der Ansicht (ansichtVorschlag), in dieser Reihenfolge
export function starte() {
  // --- Neue Organisationen: Namen in den Feldern, die nicht im Verzeichnis stehen ---
  z.ORG_TYPEN = (z.ORG_FELDER.find(f => f.k === "typ") || { t: {} }).t.enum || [];
  z.neueOrgsZuletzt = "";
}

// --- Neuer Sportkomplex bei einer Sportstätte ---
export function zeigeNk() {
  const box = z.el.querySelector("#v-nk");
  if (box) box.hidden = !(z.FELD_KOMPLEX && F(z.FELD_KOMPLEX.pfad).value === NEUER_KOMPLEX);
}
export function nkWerte() {
  if (!z.FELD_KOMPLEX || F(z.FELD_KOMPLEX.pfad).value !== NEUER_KOMPLEX) return null;
  const k = {};
  for (const f of z.KO_FELDER) { const x = String(F("nk." + f.k).value || "").trim(); if (x) setze(k, f.k, x); }
  return k;
}
export const komplexText = v => verbinde([v.neuer_sportkomplex.name || "(ohne Name)",
  `mit ${zahl(z.nkStaetten.size)} weiteren Sportstätten`]);
export function nkFehler(v) {
  const fehler = [];
  for (const f of z.KO_FELDER) fehler.push(...regelFehler(f, hole(v.neuer_sportkomplex, f.k), `Neuer Sportkomplex: ${f.p.title}`));
  if (!z.nkStaetten.size) fehler.push("Neuer Sportkomplex: mindestens eine weitere Sportstätte wählen");
  if (enthaeltEmail(v.neuer_sportkomplex)) fehler.push("Bitte keine E-Mail-Adressen eintragen");
  return fehler;
}
export function zeigeNkStaetten() {
  const c = z.el.querySelector("#v-nk-staetten");
  if (!c) return;
  c.innerHTML = [...z.nkStaetten].map(id => { const e = z.NACH_ID.get(id);
    return `<span class="chip-s">${esc(e ? e.p.name || e.kat : id)}`
      + (e && e.p.sportkomplex ? ` <small>(bisher in ${esc(komplexName(e.p.sportkomplex))})</small>` : "")
      + `<button type="button" data-nk-weg="${esc(id)}" aria-label="entfernen">×</button></span>`; }).join("")
    || `<span class="hinweis">noch keine</span>`;
  c.querySelectorAll("[data-nk-weg]").forEach(b => b.addEventListener("click", () => {
    z.nkStaetten.delete(b.dataset.nkWeg); zeigeNkStaetten(); planePruefung(); }));
}
// Suchfeld für Sportstätten (Name, Ort, ID) mit Trefferliste; waehle(id) bei Klick
export function staettenSuche(eing, ul, ohne, waehle) {
  eing.addEventListener("input", () => {
    const worte = normName(eing.value).split(" ").filter(Boolean), t = [];
    if (worte.length) for (const e of z.bestand.eintraege) {
      if (ohne(e.p.id)) continue;
      if (worte.every(w => normName([e.p.name, e.p.ort, e.p.adresse, e.p.id].join(" ")).includes(w))) t.push(e);
      if (t.length >= 8) break;
    }
    ul.innerHTML = !worte.length ? "" : t.map(e => `<li data-st="${esc(e.p.id)}">${esc(e.p.name || e.kat)}`
      + `<small>${esc(verbinde([e.p.kategorie, e.p.adresse]))}</small></li>`).join("")
      || `<li class="gruppe">Keine Sportstätte gefunden</li>`;
  });
  ul.addEventListener("click", ev => {
    const li = ev.target.closest("li[data-st]");
    if (!li) return;
    eing.value = ""; ul.innerHTML = "";
    waehle(li.dataset.st);
  });
}
// --- Neue Sportstätten für einen Sportkomplex oder Stützpunkt ---
// Das Formular der Sportstätte dient dafür; Angaben des Komplexes bzw. Stützpunkts bleiben stehen.
export const neueStaette = ref => z.neueStaetten.find(n => n.ref === ref);
export const staettenName = id => { const n = neueStaette(id), e = z.NACH_ID.get(id);
  return n ? `${n.sportstaette.name || n.sportstaette.kategorie || "?"} (neu)` : e ? e.p.name || e.kat : id; };
export function starteUnter(ziel, ref = null) {
  const n = ref ? neueStaette(ref) : null;
  z.unter = { ziel, ref, anmerkung: F("anmerkung").value };
  z.original = null;
  F("art").value = "neu";
  fuelle(n ? { ...n.sportstaette, anlagen: n.anlagen } : {});
  F("anmerkung").value = z.unter.anmerkung;
  z.el.querySelector("#v-dubletten").dataset.bestaetigt = "";
  zeigeTeile(); zeigeGewaehlt(); zeigeFehlerliste([]);
  z.el.querySelector("#v-ausgabe").innerHTML = "";
  planePruefung();
}
export function endeUnter() {
  const ziel = z.unter.ziel;
  F("anmerkung").value = z.unter.anmerkung;
  z.unter = null;
  F("art").value = ziel;
  komplexAuswahl();
  zeigeTeile(); zeigeGewaehlt(); zeigeFehlerliste([]);
  if (ziel === "sportkomplex") zeigeKoStaetten(); else zeigeSpStaetten();
  planePruefung();
}
export function uebernimmUnter(v) {
  const fehler = [...regelVerstoesse(v), ...orgDublettenFehler(v)];
  if (enthaeltEmail(v)) fehler.push("Bitte keine E-Mail-Adressen eintragen");
  const cb = z.el.querySelector("#v-keine-doppelung");
  if (z.dubletten.length && !(cb && cb.checked)) {
    fehler.push("Mögliche Doppelung prüfen (rechts) und bestätigen, dass es eine andere Sportstätte ist");
  }
  zeigeFehlerliste(fehler);
  if (fehler.length) return;
  const st = ohneLeere(v.sportstaette);
  if (z.unter.ziel === "sportkomplex") delete st.sportkomplex;
  const anlagen = v.anlagenliste.filter(a => !a.entfernt && a.typ)
    .flatMap(a => Array.from({ length: a.n }, () => anlageModell(a)));
  const ref = z.unter.ref || `neu-${++z.neuNr}`, n = { ref, ziel: z.unter.ziel, sportstaette: st, anlagen };
  z.neueStaetten = [...z.neueStaetten.filter(x => x.ref !== ref), n];
  (z.unter.ziel === "sportkomplex" ? z.koStaetten : z.spStaetten).add(ref);
  endeUnter();
}
export const neueStaettenDaten = ids => z.neueStaetten.filter(n => ids.has(n.ref))
  .map(n => ({ ref: n.ref, sportstaette: n.sportstaette, anlagen: n.anlagen }));
// Namen mit vorgeschlagener Art aus den Feldern der Sportstätte (auch neuer Sportstätten
// eines Komplexes bzw. Stützpunkts), des Stützpunkts oder der Organisation
export function orgNamen(v) {
  const out = [];
  const ausStaette = (st, typ) => {
    for (const f of z.FELDER) {
      if (f.p.widget === "organisation") out.push([hole(st, f.pfad), typ ? typ(f) : hole(st, f.pfad + "_typ")]);
      if (f.p.widget === "organisationen") for (const n of hole(st, f.pfad) || []) out.push([n, ""]);
    }
  };
  if (v.art === "neu" || v.art === "aenderung") ausStaette(v.sportstaette);
  if (v.art === "stuetzpunkt") {
    for (const f of z.SP_FELDER) if (f.p.widget === "organisation") out.push([F(f.pfad).value, ""]);
  }
  if (v.art === "organisation" && !v.loeschen) {
    for (const f of z.ORG_FELDER) if (f.p.widget === "organisation") out.push([F(f.pfad).value, ""]);
  }
  if (!z.unter && (v.art === "sportkomplex" || v.art === "stuetzpunkt")) {
    const ids = v.art === "sportkomplex" ? z.koStaetten : z.spStaetten;
    for (const n of z.neueStaetten) if (ids.has(n.ref)) ausStaette(n.sportstaette);
  }
  const gesehen = new Map();
  for (const [name, typ] of out) {
    const k = schluesselName(name);
    if (k && !orgVon(name) && !gesehen.has(k)) gesehen.set(k, [String(name).trim(), typ || ""]);
  }
  return gesehen;
}
// Ähnliche Einträge im Verzeichnis (wie bei der Prüfung „Fast gleiche Organisationen“)
export function aehnlicheOrgs(name) {
  const k = orgKern(name);
  return ORGANISATIONEN.filter(o => [o.name, ...(o.weitere_namen || [])].some(n => aehnlich(k, orgKern(n)) >= PRUEFUNG().aehnlich)).slice(0, 4);
}
export function zeigeNeueOrgs(v) {
  const namen = orgNamen(v), teil = z.el.querySelector("#v-teil-neue-orgs");
  for (const [k, [name, typ]] of namen) {
    if (!z.neueOrgs.has(k)) z.neueOrgs.set(k, { name, eintragen: true, typ: z.ORG_TYPEN.includes(typ) ? typ : "", website: "", geprueft: false });
  }
  teil.hidden = !namen.size;
  const schluessel = [...namen.keys()].join("|");
  if (schluessel === z.neueOrgsZuletzt) return;  // sonst verlöre die Eingabe den Fokus
  z.neueOrgsZuletzt = schluessel;
  z.el.querySelector("#v-neue-orgs").innerHTML = [...namen.keys()].map(k => {
    const o = z.neueOrgs.get(k), aehnlich = aehnlicheOrgs(o.name);
    return `<div class="neue-org" data-k="${esc(k)}"><label><input type="checkbox" data-no="eintragen"${o.eintragen ? " checked" : ""}>
        <b>${esc(o.name)}</b> eintragen</label>
        <label class="feld klein"><span>Art</span><select data-no="typ"><option value="">nicht bekannt</option>`
      + z.ORG_TYPEN.map(t => `<option${t === o.typ ? " selected" : ""}>${esc(t)}</option>`).join("") + `</select></label>
        <label class="feld"><span>Webseite</span><input data-no="website" type="url" value="${esc(o.website)}" placeholder="https://"></label>`
      + (aehnlich.length ? `<div class="warnung"><b>Mögliche Doppelung</b> – steht die Organisation schon im Verzeichnis?<ul>`
        + aehnlich.map(x => `<li><b>${esc(x.name)}</b> <span class="q">${esc(x.typ || "ohne Art")}</span> · `
          + `<a href="#" data-org-statt="${esc(x.name)}">stattdessen diese</a></li>`).join("")
        + `</ul><label class="bestaetigen"><input type="checkbox" data-no="geprueft"${o.geprueft ? " checked" : ""}>
            Ich habe geprüft: Es ist eine andere Organisation.</label></div>` : "") + `</div>`;
  }).join("");
}
// Name in allen Feldern des Vorschlags ersetzen (Auswahl „stattdessen diese“)
export function ersetzeOrg(alt, neuName) {
  const k = schluesselName(alt);
  for (const f of [...z.FELDER, ...z.SP_FELDER, ...z.ORG_FELDER]) {
    if (f.p.widget === "organisation" && F(f.pfad) && schluesselName(F(f.pfad).value) === k) F(f.pfad).value = neuName;
    if (f.p.widget === "organisationen" && z.chips[f.pfad]) {
      z.chips[f.pfad] = new Set([...z.chips[f.pfad]].map(n => schluesselName(n) === k ? neuName : n));
      zeigeChips(f.pfad);
    }
  }
  for (const n of z.neueStaetten) for (const f of z.FELDER) {
    if (f.p.widget === "organisation" && schluesselName(hole(n.sportstaette, f.pfad)) === k) setze(n.sportstaette, f.pfad, neuName);
    if (f.p.widget === "organisationen" && hole(n.sportstaette, f.pfad)) {
      setze(n.sportstaette, f.pfad, hole(n.sportstaette, f.pfad).map(x => schluesselName(x) === k ? neuName : x));
    }
  }
  z.neueOrgsZuletzt = "";
  zeigeArten(); planePruefung();
}
export function orgDublettenFehler(v) {
  const fehler = [];
  for (const k of orgNamen(v).keys()) {
    const o = z.neueOrgs.get(k);
    if (o && o.eintragen && !o.geprueft && aehnlicheOrgs(o.name).length) {
      fehler.push(`Mögliche Doppelung bei der Organisation „${o.name}“ prüfen und bestätigen, dass es eine andere ist`);
    }
  }
  return fehler;
}
// → [Organisation] für neue_organisationen; Fehler kommen nach `fehler`
export function neueOrgDaten(v, fehler) {
  const out = [];
  for (const k of orgNamen(v).keys()) {
    const o = z.neueOrgs.get(k);
    if (!o || !o.eintragen) continue;
    const org = ohneLeere({ name: o.name, typ: o.typ, website: o.website.trim() });
    for (const f of z.ORG_FELDER) if (f.k in org) fehler.push(...regelFehler(f, org[f.k], `Neue Organisation „${o.name}“: ${f.p.title}`));
    out.push(org);
  }
  fehler.push(...orgDublettenFehler(v));
  return out;
}
