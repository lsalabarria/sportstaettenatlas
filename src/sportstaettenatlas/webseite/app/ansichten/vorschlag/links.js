// Links aus Popups und Liste in das Formular.
// Links „Stützpunkt“ (Popups): ihr Stützpunkt oder ein neuer mit ihr
import { karte } from "../../karte/karte.js";
import { esc, leer } from "../../lib/text.js";
import { zerlegeAdresse } from "../../lib/vergleich.js";
import { ALKIS_STAETTEN } from "../analysen.js";
import { ANSICHTEN } from "../umschalten.js";

document.addEventListener("click", ev => {
  const a = ev.target.closest("[data-stp-von]");
  if (!a || !ANSICHTEN.vorschlag) return;
  ev.preventDefault();
  karte.closePopup();
  ANSICHTEN.vorschlag.stuetzpunktVon(a.dataset.stpVon);
});
// Links „Sportkomplex“ (Popups): der Komplex der Sportstätte oder ein neuer mit ihr
document.addEventListener("click", ev => {
  const a = ev.target.closest("[data-komplex-von]");
  if (!a || !ANSICHTEN.vorschlag) return;
  ev.preventDefault();
  karte.closePopup();
  ANSICHTEN.vorschlag.komplexVon(a.dataset.komplexVon);
});
// Links „Organisation ändern“ (Liste, Popups)
document.addEventListener("click", ev => {
  const a = ev.target.closest("[data-org-aendern]");
  if (!a || !ANSICHTEN.vorschlag) return;
  ev.preventDefault();
  karte.closePopup();
  ANSICHTEN.vorschlag.organisation(a.dataset.orgAendern);
});
// Links in Popups: „ändern“, „als Vorschlag übernehmen“, „hier vorschlagen“
document.addEventListener("click", ev => {
  const a = ev.target.closest("[data-bearbeiten],[data-vorschlag-alkis],[data-vorschlag-hier],[data-vorschlag-neu]");
  const v = ANSICHTEN.vorschlag;
  if (!a || !v) return;
  ev.preventDefault();
  karte.closePopup();
  if (a.dataset.bearbeiten) v.bearbeite(a.dataset.bearbeiten, a.dataset.teil);
  else if (a.dataset.vorschlagNeu !== undefined) v.neu();
  else if (a.dataset.vorschlagHier) {
    const [lat, lon] = a.dataset.vorschlagHier.split(",").map(Number);
    v.neu({ lage: { lat, lon } });
  } else {
    const s = ALKIS_STAETTEN[a.dataset.vorschlagAlkis];
    if (!s) return;
    v.neu({ name: s.name, kategorie: s.kategorie || "", adresse: zerlegeAdresse(s.adresse),
      betreiber: s.betreiber, eigentuemer: s.eigentuemer, website: s.website, lage: { lat: s.lat, lon: s.lon },
      anmerkung: `Aus ALKIS übernommen (${s.typ || s.typgruppe || "Sportstätte"}).` });
  }
});
// Zeile „Angaben ändern · Sportanlagen ändern“ für Popups (Karte und ALKIS-Abgleich), nur
// für Sportstätten, die im Datenbestand stehen
export function aendernLink(id) {
  if (!ANSICHTEN.vorschlag || leer(id) || !ANSICHTEN.vorschlag.hat(id)) return "";
  return `<tr><td>Vorschlag</td><td><a href="#" data-bearbeiten="${esc(id)}">Angaben ändern</a> · `
    + `<a href="#" data-bearbeiten="${esc(id)}" data-teil="anlagen">Sportanlagen ändern</a> · `
    + `<a href="#" data-komplex-von="${esc(id)}">Sportkomplex</a> · `
    + `<a href="#" data-stp-von="${esc(id)}">Stützpunkt</a></td></tr>`;
}
