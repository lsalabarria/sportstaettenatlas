// Organisationen: Suche im Verzeichnis, Nutzung, Änderungen.
import { z } from "./zustand.js";
import { zeigeTeile } from "./anlagen.js";
import { F, haeufig } from "./formular.js";
import { planePruefung } from "./pruefung.js";
import { regelFehler } from "./hilfen.js";
import { ORGANISATIONEN, orgVon } from "../../daten/organisationen.js";
import { regelnZwischen } from "../../daten/schema.js";
import { esc, leer, schluesselName, verbinde, zahl } from "../../lib/text.js";
import { listeAus } from "../../lib/vergleich.js";

// Beim Anlegen der Ansicht (ansichtVorschlag), in dieser Reihenfolge
export function starte() {
  // --- Organisationen ---
  // Wer nennt welche Organisation? Einmal aufgebaut: Name (schluesselName) → Rolle → Sportstätten
  z.nutzungsIndex = null; z.orgListeCache = null;
}

export function index() {
  if (z.nutzungsIndex) return z.nutzungsIndex;
  z.nutzungsIndex = new Map();
  const dazu = (name, rolle, e) => {
    const k = schluesselName(name);
    if (!k) return;
    if (!z.nutzungsIndex.has(k)) z.nutzungsIndex.set(k, { eigentuemer: new Set(), betreiber: new Set(), nutzer: new Set() });
    z.nutzungsIndex.get(k)[rolle].add(e);
  };
  for (const e of z.bestand.eintraege) {
    dazu(e.p.eigentuemer, "eigentuemer", e);
    dazu(e.p.betreiber, "betreiber", e);
    for (const n of e.p.nutzer || []) dazu(n, "nutzer", e);
  }
  return z.nutzungsIndex;
}
// Verzeichnis und Namen aus dem Bestand, die (noch) nicht darin stehen (einmal berechnet)
export function orgListe() {
  if (z.orgListeCache) return z.orgListeCache;
  const eintrag = (name, o) => {
    const alle = [name, ...(o ? o.weitere_namen || [] : [])];
    return { name, o, alle, namen: alle.map(schluesselName), n: nutzung(name).n };
  };
  // dazu Namen, die Sportstätten nennen, die aber nicht im Verzeichnis stehen (häufigste
  // Schreibweise)
  const bestandNamen = haeufig(z.bestand.eintraege.flatMap(e => [e.p.betreiber, e.p.eigentuemer, ...(e.p.nutzer || [])]));
  return z.orgListeCache = [...ORGANISATIONEN.map(o => eintrag(o.name, o)),
    ...bestandNamen.filter(([n]) => !orgVon(n)).map(([n]) => eintrag(n, null))];
}
// Organisationen zu einem Suchtext, für alle Eingaben gleich: genauer Name vor Anfang des
// Namens vor Wortanfängen vor Teilen davon; weitere Schreibweisen zählen etwas weniger. Bei
// gleichem Rang zuerst, was Sportstätten schon nennen, dann der kürzere Name.
export function sucheOrg(text, n = 8) {
  const q = schluesselName(text), worte = q.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  if (!worte.length) return [];
  // „Ortsgemeinde Berg (VG Altenahr)“ zählt für „berg“ wie ein genauer Name
  const kern = k => k.replace(/^(ortsgemeinde|verbandsgemeinde|gemeinde|stadt|landkreis|kreis) /, "");
  const ganz = (k, w) => k === w || (k.startsWith(w) && /[^\p{L}\p{N}]/u.test(k[w.length]));
  const rang = k => {
    if (k === q) return 0;
    if (ganz(kern(k), q)) return 1;
    if (k.startsWith(q) || kern(k).startsWith(q)) return 2;
    const teile = k.split(/[^\p{L}\p{N}]+/u);
    if (worte.every(w => teile.includes(w))) return 3;
    if (worte.every(w => teile.some(t => t.startsWith(w)))) return 4;
    return worte.every(w => k.includes(w)) ? 5 : 9;
  };
  const out = [];
  for (const x of orgListe()) {
    let best = 9, alias = "";
    x.namen.forEach((k, i) => {
      const r = rang(k) + (i ? 0.5 : 0);
      if (r < best) { best = r; alias = i ? x.alle[i] : ""; }
    });
    if (best < 9) out.push({ ...x, rang: Math.floor(best), alias });
  }
  return out.sort((a, b) => a.rang - b.rang || b.n - a.n || a.name.length - b.name.length
    || a.name.localeCompare(b.name, "de")).slice(0, n);
}
export const orgZusatz = x => verbinde([x.alias && `auch „${x.alias}“`,
  x.o ? x.o.typ || "im Verzeichnis, ohne Art" : "noch nicht im Verzeichnis", nutzungText(x.name)]);
// Vorschlagsliste unter jeder Eingabe für eine Organisation (data-orgs): Pfeiltasten, Enter,
// Klick; Esc oder Verlassen schließt sie
export function orgListeVon(eing) {
  let ul = eing.parentElement.querySelector(":scope > ul.org-vorschlaege");
  if (!ul) {
    ul = document.createElement("ul"); ul.className = "treffer org-vorschlaege"; ul.hidden = true;
    eing.insertAdjacentElement("afterend", ul);
  }
  return ul;
}
export function zeigeOrgVorschlaege(eing) {
  const ul = orgListeVon(eing), t = sucheOrg(eing.value);
  ul.innerHTML = t.map(x => `<li data-name="${esc(x.name)}">${esc(x.name)}<small>${esc(orgZusatz(x))}</small></li>`).join("");
  ul.hidden = !t.length;
}
export function waehleOrgVorschlag(eing, name) {
  eing.value = name;
  const box = eing.closest("[data-chips]");
  if (box) box.querySelector("button").click();  // Nutzer: gleich als Chip übernehmen
  else eing.dispatchEvent(new Event("input", { bubbles: true }));
  orgListeVon(eing).hidden = true;  // auch wenn das input-Ereignis sie wieder geöffnet hat
}
// Wie oft nennen Sportstätten diese Organisation (alle Schreibweisen)?
export function nutzung(name) {
  const o = orgVon(name), ix = index();
  const namen = new Set([name, ...(o ? [o.name, ...(o.weitere_namen || [])] : [])].map(schluesselName));
  const je = { eigentuemer: new Set(), betreiber: new Set(), nutzer: new Set() }, alle = new Set();
  for (const k of namen) {
    const x = ix.get(k);
    if (x) for (const r in je) for (const e of x[r]) { je[r].add(e); alle.add(e); }
  }
  return { eigentuemer: je.eigentuemer.size, betreiber: je.betreiber.size, nutzer: je.nutzer.size, n: alle.size };
}
export function nutzungText(name) {
  const zahlen = nutzung(name);
  return zahlen.n ? `${zahl(zahlen.n)} Sportstätten (` + [["eigentuemer", "Eigentümer"], ["betreiber", "Betreiber"], ["nutzer", "Nutzer"]]
    .filter(([k]) => zahlen[k]).map(([k, t]) => `${t} ${zahl(zahlen[k])}`).join(", ") + ")" : "keine Sportstätte nennt sie";
}
// Organisation zum Ändern wählen (Name aus der Liste) oder null für eine neue
export function waehleOrg(name) {
  const o = name ? orgVon(name) : null;
  z.orgOriginal = name ? { o: o || { name }, imVerzeichnis: !!o } : null;
  const werte = z.orgOriginal ? z.orgOriginal.o : {};
  for (const f of z.ORG_FELDER) {
    const e = F(f.pfad), w = werte[f.k];
    e.value = leer(w) ? "" : Array.isArray(w) ? w.join(", ") : w;
  }
  if (F("org-loeschen")) F("org-loeschen").checked = false;
  const g = z.el.querySelector("#v-org-gewaehlt");
  g.innerHTML = z.orgOriginal ? `<div class="chip">${z.orgOriginal.imVerzeichnis ? "Sie ändern" : "Noch nicht im Verzeichnis, Sie tragen ein"}: `
    + `<b>${esc(z.orgOriginal.o.name)}</b> <span class="q">${esc(nutzungText(z.orgOriginal.o.name))}</span>`
    + ` <button type="button">stattdessen eine neue</button></div>` : "";
  const b = g.querySelector("button");
  if (b) b.addEventListener("click", () => { waehleOrg(null); zeigeTeile(); planePruefung(); });
}
export function orgWerte() {
  const o = {};
  for (const f of z.ORG_FELDER) {
    const x = String(F(f.pfad).value || "").trim();
    if (x) o[f.k] = f.t.type === "array" ? listeAus(x) : x;
  }
  return o;
}
export function orgFehler(o, loeschen) {
  if (loeschen) return [];
  const fehler = [];
  for (const f of z.ORG_FELDER) fehler.push(...regelFehler(f, o[f.k], f.p.title));
  fehler.push(...regelnZwischen("Organisation", o));
  // Name oder Schreibweise schon bei einer anderen Organisation im Verzeichnis?
  const eigene = z.orgOriginal && z.orgOriginal.imVerzeichnis ? z.orgOriginal.o.id : null;
  for (const n of [o.name, ...(o.weitere_namen || [])]) {
    const andere = orgVon(n);
    if (n && andere && andere.id !== eigene) fehler.push(`„${n}“ steht schon im Verzeichnis (${andere.name}) – bitte oben suchen und ändern`);
  }
  return fehler;
}
export function orgAenderungen(o) {
  if (!z.orgOriginal) return Object.keys(o);
  const alt = z.orgOriginal.o, text = x => Array.isArray(x) ? x.join(", ") : (x || "");
  return z.ORG_FELDER.map(f => f.k).filter(k => text(alt[k]) !== text(o[k]));
}
