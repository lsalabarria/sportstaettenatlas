// Weiter zu LimeSurvey: Vorschlag prüfen, als JSON übergeben.
import { z } from "./zustand.js";
import { neueOrgDaten, nkFehler, uebernimmUnter } from "./neue_objekte.js";
import { orgAenderungen, orgFehler } from "./organisationen.js";
import { aenderungen, pruefe, regelVerstoesse, vorschlagDaten, zeigeFehlerliste } from "./pruefung.js";
import { weiterKomplex } from "./sportkomplexe.js";
import { weiterStuetzpunkt } from "./stuetzpunkte.js";
import { werte } from "./werte.js";
import { URL_HOECHSTENS, VORSCHLAG_FRAGEN } from "./hilfen.js";
import { enthaeltEmail } from "../../daten/schema.js";
import { esc } from "../../lib/text.js";
import { KONFIG } from "../../seite.js";

// Beim Anlegen der Ansicht (ansichtVorschlag), in dieser Reihenfolge
export function starte() {
  z.gebaut = false;
}

// --- Weiter zu LimeSurvey ---
export function weiter() {
  pruefe();
  const v = werte(), fehler = [];
  if (z.unter) return uebernimmUnter(v);
  if (v.art === "organisation") return weiterOrg(v);
  if (v.art === "sportkomplex") return weiterKomplex(v);
  if (v.art === "stuetzpunkt") return weiterStuetzpunkt(v);
  if (v.art !== "neu" && !z.original) fehler.push("Welche Sportstätte soll geändert werden? (oben auswählen)");
  fehler.push(...regelVerstoesse(v));
  if (enthaeltEmail(v)) fehler.push("Bitte keine E-Mail-Adressen eintragen");
  const alle = aenderungen(v).map(([k]) => k);
  const geaendert = alle.filter(k => k !== "anlagen" && k !== "neuer_sportkomplex");
  if (z.original && !alle.length && !v.anmerkung) {
    fehler.push("Änderung: mindestens ein Feld oder eine Sportanlage ändern oder eine Anmerkung schreiben");
  }
  if (v.neuer_sportkomplex) fehler.push(...nkFehler(v));
  const cb = z.el.querySelector("#v-keine-doppelung");
  if (v.art === "neu" && z.dubletten.length && !(cb && cb.checked)) {
    fehler.push("Mögliche Doppelung prüfen (rechts) und bestätigen, dass es eine andere Sportstätte ist");
  }
  const daten = vorschlagDaten(v, geaendert, v.art === "neu" && cb && cb.checked ? z.dubletten.map(d => d.e.p.id) : []);
  sende(daten, v, fehler);
}
// Vorschlag als JSON an LimeSurvey (Frage data), Anmerkung in kommentar
export function sende(daten, v, fehler) {
  if (!daten.loeschen) {
    const orgs = neueOrgDaten(v, fehler);
    if (orgs.length) daten.neue_organisationen = orgs;
  }
  const params = new URLSearchParams();
  params.set(VORSCHLAG_FRAGEN.data, JSON.stringify(daten));
  if (v.anmerkung && VORSCHLAG_FRAGEN.kommentar) params.set(VORSCHLAG_FRAGEN.kommentar, v.anmerkung);
  const u = KONFIG.vorschlag_url ? KONFIG.vorschlag_url + (KONFIG.vorschlag_url.includes("?") ? "&" : "?")
    + "newtest=Y&" + params : "";
  if (u.length > URL_HOECHSTENS) {
    fehler.push("Der Vorschlag ist zu umfangreich für eine Übergabe – bitte auf mehrere Vorschläge aufteilen "
      + "(z. B. erst die Angaben, dann die Sportanlagen, oder neue Sportstätten einzeln).");
  }
  zeigeFehlerliste(fehler);
  if (fehler.length) return;
  const ausgabe = z.el.querySelector("#v-ausgabe");
  if (u) {
    ausgabe.innerHTML = `<div class="ok">Die Umfrage wurde in einem neuen Tab geöffnet. Falls nicht: `
      + `<a href="${esc(u)}" target="_blank" rel="noopener">hier weiter zu LimeSurvey</a>.</div>`;
    window.open(u, "_blank", "noopener");
  } else {
    ausgabe.innerHTML = `<div class="warnung"><b>Der Link zur LimeSurvey-Umfrage ist noch nicht eingetragen</b> `
      + `(in <code>konfig.js</code>: <code>vorschlag_url</code>). Übertragen würde in der Frage `
      + `<code>${esc(VORSCHLAG_FRAGEN.data)}</code>:<pre class="umbruch">${esc(JSON.stringify(daten, null, 2))}</pre>`
      + (v.anmerkung ? `und in <code>${esc(VORSCHLAG_FRAGEN.kommentar)}</code>: ${esc(v.anmerkung)}` : "") + `</div>`;
    ausgabe.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}
export function weiterOrg(v) {
  const fehler = orgFehler(v.organisation, v.loeschen);
  const geaendert = orgAenderungen(v.organisation);
  if (z.orgOriginal && z.orgOriginal.imVerzeichnis && !v.loeschen && !geaendert.length && !v.anmerkung) {
    fehler.push("Änderung: mindestens ein Feld ändern, löschen wählen oder eine Anmerkung schreiben");
  }
  if (enthaeltEmail(v.organisation)) fehler.push("Bitte keine E-Mail-Adressen eintragen");
  const daten = { version: 1, art: "organisation" };
  if (z.orgOriginal && z.orgOriginal.imVerzeichnis) daten.organisation_id = z.orgOriginal.o.id;
  if (v.loeschen) daten.loeschen = true;
  else daten.organisation = v.organisation;
  if (!v.loeschen && geaendert.length && z.orgOriginal) daten.geaendert = geaendert;
  sende(daten, v, fehler);
}
