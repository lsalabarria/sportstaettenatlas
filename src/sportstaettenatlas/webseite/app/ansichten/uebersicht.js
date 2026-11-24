// Ansicht „Übersicht“: kleines Dashboard über den Datenbestand.
// Befüllung der Angaben, getrennt für Sportstätten und ihre Sportanlagen
// Felder aus dem Datenmodell (ohne uebersicht: false) → [{ titel, test, gruppe, fuer }];
// die Teile der Adresse einzeln (sie stehen flach in den Eigenschaften der Karte) in der
// Gruppe der Adresse. fuer: Feld ist nur für diese Sportanlagen gedacht (passtFuer).
import { ANLAGEN_GRUPPEN, anlagenGruppe } from "../daten/anlagen.js";
import { ORGANISATIONEN, orgVon } from "../daten/organisationen.js";
import { ATLAS, SCHEMA, modellFelder, passtFuer } from "../daten/schema.js";
import { SPORTKOMPLEXE, komplexName } from "../daten/sportkomplexe.js";
import { STP_EBENEN, STUETZPUNKTE } from "../daten/stuetzpunkte.js";
import {
  GEBIET, GEBIETE, NACH_S, gebietName, gebietTitel, imGebiet, setzeGebiet,
} from "../karte/gebiete.js";
import { esc, leer, prozent, zaehle, zahl } from "../lib/text.js";
import { ARTEN, artText } from "./bestand.js";

function feldTests(modell, gruppe) {
  const out = [];
  for (const [k, p, , t] of modellFelder(modell)) {
    if (p.uebersicht === false) continue;
    if (t.ref) out.push(...feldTests(t.ref, p.gruppe || gruppe));
    else out.push({ k, titel: p.title || k, gruppe: gruppe || p.gruppe || "Weitere Angaben",
      fuer: p.fuer ? x => passtFuer(p, x.typ) : null,
      test: x => !leer(x[k]) && !(typeof x[k] === "object" && !Array.isArray(x[k]) && !Object.keys(x[k]).length) });
  }
  return out;
}
let _felder, _anlageFelder, _orgFelder, _komplexFelder;
export const FELDER_STAETTE = () => _felder ??= feldTests("Sportstaette");
export const FELDER_ANLAGE = () => _anlageFelder ??= feldTests("Sportanlage");
// Regionalschlüssel nur bei Kommunen, Vereinsnummer im LSB nur bei Vereinen gedacht
const FELDER_ORG = () => _orgFelder ??= feldTests("Organisation", "Angaben").map(f => {
  const nur = { ars: "Kommune", lsb_nummer: "Verein" }[f.k];
  return nur ? { ...f, fuer: o => (ATLAS().organisationstypen || {})[o.typ] === nur } : f;
});
const FELDER_KOMPLEX = () => _komplexFelder ??= feldTests("Sportkomplex", "Angaben");
// Organisationen der Auswahl: ohne Gebiet und Sportart das ganze Verzeichnis; sonst die
// Eigentümer, Betreiber und Nutzer der Sportstätten (und mit Gebiet die Kommunen darin)
function orgsDerAuswahl(liste, alle) {
  if (alle) return ORGANISATIONEN;
  const out = new Set();
  for (const e of liste) for (const n of [e.p.betreiber, e.p.eigentuemer, ...(e.p.nutzer || [])]) {
    const o = !leer(n) && orgVon(n);
    if (o) out.add(o);
  }
  if (GEBIET) for (const o of ORGANISATIONEN) if (o.ars && o.ars.startsWith(GEBIET.s)) out.add(o);
  return [...out];
}
// Sportkomplex für die Befüllung: Angaben flach wie bei den Sportstätten (Adresse in Teilen)
function komplexAngaben(id) {
  const k = SPORTKOMPLEXE.get(id);
  return k ? { name: k.name, ...(k.adresse || {}) } : null;
}
// Befüllung eines Feldes: [befüllt, gedacht für] – nur unter den Einträgen, für die es gedacht ist
function befuellt(liste, f) {
  let ja = 0, n = 0;
  for (const x of liste) if (!f.fuer || f.fuer(x)) { n++; if (f.test(x)) ja++; }
  return [ja, n];
}
// Anteil befüllter Angaben über alle Felder (je Eintrag nur die Felder, die zu ihm passen)
function anteil(liste, felder) {
  let ja = 0, n = 0;
  for (const f of felder) { const [a, b] = befuellt(liste, f); ja += a; n += b; }
  return n ? ja / n : 0;
}
function befuellung(liste) { return anteil(liste.map(e => e.p), FELDER_STAETTE()); }
// Befüllung nach Abschnitten des Modells (gruppen): aufklappbar, je Feld ein Balken
function befuellungNachGruppe(modell, liste, felder, einheit) {
  const reihe = [...(SCHEMA.$defs[modell].gruppen || [])];
  for (const f of felder) if (!reihe.includes(f.gruppe)) reihe.push(f.gruppe);
  return reihe.map((g, i) => {
    const fs = felder.filter(f => f.gruppe === g);
    if (!fs.length) return "";
    const zeilen = fs.map(f => { const [ja, n] = befuellt(liste, f); return [f.titel, ja, n]; })
      .filter(z => z[2]);
    if (!zeilen.length) return "";
    const b = anteil(liste, fs);
    return `<details class="befuellung"${i === 0 ? " open" : ""}><summary><b>${esc(g)}</b>`
      + `<span class="w">${Math.round(100 * b)} %</span></summary>`
      + `<table class="balken">` + zeilen.map(([l, ja, n]) => {
        const breite = n ? 100 * ja / n : 0;
        const nur = n < liste.length ? ` (nur ${zahl(n)} ${einheit}, für die das Feld gedacht ist)` : "";
        return `<tr title="${esc(l)}: ${zahl(ja)} von ${zahl(n)}${esc(nur)}"><td class="l">${esc(l)}`
          + `${nur ? ` <span class="q">· ${zahl(n)}</span>` : ""}</td>`
          + `<td><div class="spur"><div class="fuell" style="width:${breite.toFixed(1)}%"></div></div></td>`
          + `<td class="w">${prozent(ja, n)} %</td></tr>`;
      }).join("") + `</table></details>`;
  }).join("");
}
export function balken(zeilen, gesamt, prozentual, einheit = "Sportstätten") {
  // zeilen: [label, wert]; Breite relativ zu gesamt (Anteil) bzw. zum größten Wert
  const max = prozentual ? gesamt : Math.max(1, ...zeilen.map(z => z[1]));
  return `<table class="balken">` + zeilen.map(([l, w]) => {
    const breite = Math.max(0, Math.min(100, 100 * w / (max || 1)));
    const text = prozentual ? `${prozent(w, gesamt)} %` : zahl(w);
    const titel = prozentual ? `${zahl(w)} von ${zahl(gesamt)}` : `${zahl(w)} ${einheit}`;
    return `<tr title="${esc(l)}: ${titel}"><td class="l">${esc(l)}</td>`
      + `<td><div class="spur"><div class="fuell" style="width:${breite.toFixed(1)}%"></div></div></td>`
      + `<td class="w">${text}</td></tr>`;
  }).join("") + `</table>`;
}
export function ansichtUebersicht(bestand) {
  const el = document.getElementById("seite-uebersicht");
  let sport = "";  // Filter nach Sportart ("": alle)
  el.addEventListener("change", ev => {
    if (ev.target.matches("[data-u-sport]")) { sport = ev.target.value; zeichne(); }
  });
  function zeichne() {
    const imG = bestand.eintraege.filter(e => imGebiet(e.p.ars));
    const liste = sport ? imG.filter(e => e.sp.has(sport)) : imG;
    const sportWahlHtml = `<label class="u-sport">Sportart <select data-u-sport><option value="">alle</option>`
      + [...new Set(imG.flatMap(e => [...e.sp]))].sort((a, b) => a.localeCompare(b, "de"))
        .map(s => `<option${s === sport ? " selected" : ""}>${esc(s)}</option>`).join("") + `</select></label>`;
    // Stützpunkte mit mindestens einer dieser Sportstätten (bei Sportart: für diese Sportart)
    const ids = new Set(liste.map(e => e.p.id));
    const stp = [...STUETZPUNKTE.values()].filter(x => [...x.alle].some(i => ids.has(i))
      && (!sport || !(x.sportarten || []).length || x.sportarten.includes(sport)));
    const stpKachel = ([eb, text]) => {
      const sp = stp.filter(x => x.ebene === eb);
      const an = new Set(sp.flatMap(x => [...x.alle].filter(i => ids.has(i))));
      return kachel(text, zahl(sp.length), sp.length ? `an ${zahl(an.size)} Sportstätten` : "keine eingetragen");
    };
    const anlagen = liste.flatMap(e => e.anlagen);
    const n = liste.length, na = anlagen.length;
    const sportarten = new Set(liste.flatMap(e => [...e.sp]));
    const betr = { Verein: new Set(), Kommune: new Set() };
    for (const e of liste) if (betr[e.art] && e.betreiber) betr[e.art].add(e.betreiber);
    const sortiert = z => Object.entries(z).sort((a, b) => b[1] - a[1]);
    const kachel = (label, wert, zusatz = "") => `<div class="kachel"><div class="label">${label}</div>`
      + `<div class="wert">${wert}</div><div class="zusatz">${zusatz}</div></div>`;
    const ohneAnlagen = liste.filter(e => !e.anlagen.length).length;
    // Sportkomplexe mit mindestens einer Sportstätte im Gebiet: Name → Zahl dieser Sportstätten
    const imKomplex = liste.filter(e => e.p.sportkomplex);
    const jeKomplex = sortiert(zaehle(imKomplex.map(e => komplexName(e.p.sportkomplex))));
    const angegeben = rolle => liste.map(e => e.p[rolle + "_typ"]).filter(v => !leer(v));
    const artBalken = rolle => {
      const z = angegeben(rolle);
      return z.length ? `<h4>Art des ${rolle === "betreiber" ? "Betreibers" : "Eigentümers"} (angegeben)</h4>`
        + balken(sortiert(zaehle(z)), z.length, false) : "";
    };
    // Teil 1: was im Bestand steht
    let h = `<div class="inhalt"><div class="u-kopf"><h2>Übersicht: ${esc(gebietName())}${sport ? ` · ${esc(sport)}` : ""}</h2>${sportWahlHtml}</div>`
      + `<section class="teil"><h2 class="teil-titel">Bestand</h2>`
      + `<p class="unter">Was der Datenbestand (Ordner <code>daten/</code>) enthält: Sportstätten, `
      + `die Sportanlagen darin und wer sie betreibt</p><div class="kacheln drei">`
      + kachel("Sportstätten", zahl(n), ohneAnlagen ? `${zahl(ohneAnlagen)} ohne eingetragene Sportanlage` : "alle mit Sportanlagen")
      + kachel("Sportanlagen", zahl(na), n ? `Ø ${(na / n).toLocaleString("de-DE",
        { maximumFractionDigits: 1 })} je Sportstätte` : "")
      + kachel("Sportkomplexe", zahl(jeKomplex.length), jeKomplex.length
        ? `mit ${zahl(imKomplex.length)} Sportstätten (${prozent(imKomplex.length, n)} %)` : "noch keine eingetragen")
      + kachel("Sportarten", zahl(sportarten.size), "verschiedene")
      + kachel("Vereine", zahl(betr.Verein.size), "als Betreiber (mit angegebener Art)")
      + kachel("Kommunen", zahl(betr.Kommune.size), "als Betreiber (mit angegebener Art)")
      + STP_EBENEN.map(stpKachel).join("")
      + `</div><div class="spalten"><div><h3>Sportstätten</h3>`
      + `<h4>Nach Kategorie</h4>` + balken(sortiert(zaehle(liste.map(e => e.kat))), n, false)
      + `<h4>Betreiber</h4>` + balken(ARTEN.map(a => [artText(a), liste.filter(e => e.art === a).length])
        .filter(z => z[1]), n, true)
      + `<div class="hinweis">Art angegeben bei ${zahl(angegeben("betreiber").length)} Sportstätten (bei der Sportstätte oder im Verzeichnis der Organisationen)</div>`
      + artBalken("betreiber") + artBalken("eigentuemer")
      + (jeKomplex.length ? `<h4>Größte Sportkomplexe</h4>` + balken(jeKomplex.slice(0, 10), 0, false) : "")
      + `</div><div><h3>Sportanlagen</h3>`
      + `<h4>Nach Gruppe</h4>` + balken(ANLAGEN_GRUPPEN.map(([g, text]) =>
        [text, anlagen.filter(a => anlagenGruppe(a.typ) === g).length]).filter(z => z[1])
        .sort((a, b) => b[1] - a[1]), 0, false, "Sportanlagen")
      + `<h4>Häufigste Typen</h4>` + balken(sortiert(zaehle(anlagen.map(a => a.typ))).slice(0, 12), 0, false, "Sportanlagen")
      + `<h4>Sportanlagen je Sportstätte</h4>` + balken(sortiert(zaehle(liste.map(e =>
        e.anlagen.length >= 5 ? "5 und mehr" : String(e.anlagen.length)))).sort((a, b) => a[0].localeCompare(b[0])), 0, false)
      + `</div></div></section>`;
    // Teil 2: wie vollständig die Angaben sind
    const komplexe = [...new Set(imKomplex.map(e => e.p.sportkomplex))].map(komplexAngaben).filter(Boolean);
    const alleOrgs = !GEBIET && !sport, orgs = orgsDerAuswahl(liste, alleOrgs);
    h += `<section class="teil"><h2 class="teil-titel">Befüllung</h2>`
      + `<p class="unter">Wie vollständig die Angaben im Bestand sind: Anteil der befüllten Felder `
      + `des Datenmodells</p><div class="kacheln">`
      + kachel("Angaben Sportstätten", `${Math.round(100 * befuellung(liste))} %`, `befüllt, Durchschnitt über ${FELDER_STAETTE().length} Felder`)
      + kachel("Angaben Sportanlagen", `${Math.round(100 * anteil(anlagen, FELDER_ANLAGE()))} %`,
        `befüllt, Durchschnitt über die Felder, die zum Typ passen (bis ${FELDER_ANLAGE().length})`)
      + kachel("Angaben Sportkomplexe", komplexe.length ? `${Math.round(100 * anteil(komplexe, FELDER_KOMPLEX()))} %` : "–",
        komplexe.length ? `befüllt bei ${zahl(komplexe.length)} ${komplexe.length === 1 ? "Sportkomplex" : "Sportkomplexen"}, Durchschnitt über ${FELDER_KOMPLEX().length} Felder` : "keine eingetragen")
      + kachel("Angaben Organisationen", orgs.length ? `${Math.round(100 * anteil(orgs, FELDER_ORG()))} %` : "–",
        orgs.length ? `befüllt bei ${zahl(orgs.length)} ${orgs.length === 1 ? "Organisation" : "Organisationen"}, Durchschnitt über ${FELDER_ORG().length} Felder` : alleOrgs ? "keine im Verzeichnis" : "keine zu dieser Auswahl")
      + `</div><div class="spalten"><div><h3>Sportstätten</h3>`
      + befuellungNachGruppe("Sportstaette", liste.map(e => e.p), FELDER_STAETTE(), "Sportstätten")
      + `</div><div><h3>Sportanlagen</h3>`
      + `<div class="hinweis">Felder, die nur für bestimmte Sportanlagen gedacht sind (z. B. Becken für Bäder), `
      + `zählen nur unter diesen; die Zahl dahinter nennt, wie viele es sind.</div>`
      + befuellungNachGruppe("Sportanlage", anlagen, FELDER_ANLAGE(), "Sportanlagen")
      + `</div></div><div class="spalten"><div><h3>Sportkomplexe</h3>`
      + (komplexe.length ? `<div class="hinweis">Sportkomplexe mit mindestens einer Sportstätte der Auswahl</div>`
        + befuellungNachGruppe("Sportkomplex", komplexe, FELDER_KOMPLEX(), "Sportkomplexe")
        : `<div class="hinweis">Keine Sportkomplexe eingetragen.</div>`)
      + `</div><div><h3>Organisationen</h3>`
      + (orgs.length ? `<div class="hinweis">${alleOrgs ? "Alle im Verzeichnis der Organisationen"
        : "Eigentümer, Betreiber und Nutzer der Sportstätten der Auswahl" + (GEBIET ? " und die Kommunen im Gebiet" : "")}</div>`
        + befuellungNachGruppe("Organisation", orgs, FELDER_ORG(), "Organisationen")
        : `<div class="hinweis">${alleOrgs ? "Keine Organisationen im Verzeichnis." : "Keine Organisationen zu dieser Auswahl."}</div>`)
      + `</div></div>`;
    // Teilgebiete: Befüllung je Kreis bzw. je Verbandsgemeinde/Gemeinde
    const ebene = !GEBIET ? "kreis" : GEBIET.e === "kreis" ? "vg" : GEBIET.e === "vg" ? "gemeinde" : null;
    const teile = ebene ? GEBIETE.filter(g => g.e === ebene && (!GEBIET || g.s.startsWith(GEBIET.s))) : [];
    if (teile.length > 1) {
      const spur = b => `<table class="balken"><tr><td><div class="spur"><div class="fuell" `
        + `style="width:${(100 * b).toFixed(1)}%"></div></div></td><td class="w">${Math.round(100 * b)} %</td></tr></table>`;
      const zeilen = teile.map(g => {
        const l = liste.filter(e => e.p.ars && e.p.ars.startsWith(g.s)), a = l.flatMap(e => e.anlagen);
        return { g, n: l.length, na: a.length, b: befuellung(l), ba: anteil(a, FELDER_ANLAGE()) };
      }).sort((a, b) => b.n - a.n);
      h += `<h3>Befüllung nach ${ebene === "kreis" ? "Kreisen" : ebene === "vg" ? "Verbandsgemeinden" : "Gemeinden"}</h3>`
        + `<table class="tabelle"><thead><tr><th>Gebiet</th><th class="zahl">Sportstätten</th>`
        + `<th class="zahl">Sportanlagen</th><th style="width:24%">Angaben Sportstätten</th>`
        + `<th style="width:24%">Angaben Sportanlagen</th></tr></thead><tbody>` + zeilen.map(z =>
          `<tr class="zeile" data-g="${z.g.s}" title="Gebiet auswählen"><td>${esc(gebietTitel(z.g))}</td>`
          + `<td class="zahl">${zahl(z.n)}</td><td class="zahl">${zahl(z.na)}</td>`
          + `<td>${z.n ? spur(z.b) : "–"}</td><td>${z.na ? spur(z.ba) : "–"}</td></tr>`).join("")
        + `</tbody></table>`;
    }
    h += `</section></div>`;
    el.innerHTML = h;
    el.querySelectorAll("[data-g]").forEach(z => z.addEventListener("click", () => setzeGebiet(NACH_S[z.dataset.g])));
  }
  return {
    titel: "Übersicht",
    zeigen() { el.hidden = false; zeichne(); },
    verbergen() { el.hidden = true; },
    gebietGeaendert() { if (!el.hidden) zeichne(); },
  };
}
