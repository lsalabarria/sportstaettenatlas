// Umschalten zwischen den Ansichten. Jede Ansicht ist ein Objekt mit titel, zeigen(),
// verbergen() und optional starte() (einmal, darf Daten laden), aktualisiere() (Karte
// verschoben), gebietGeaendert(), suchindex() und zustand() (Zusatz für die Adresse, z. B.
// "analyse=alkis").
import { GEBIET, beiGebietswechsel } from "../karte/gebiete.js";
import { esc } from "../lib/text.js";
import { ladeFehler } from "../seite.js";
import { sucheLeeren } from "./suche.js";

export const ANSICHTEN = {};
beiGebietswechsel(() => {
  merkeZustand();
  for (const a of Object.values(ANSICHTEN)) if (a.gestartet && a.gebietGeaendert) a.gebietGeaendert();
});
export let AKTIV = null, STANDARD = "bestand";
// Die erste Ansicht ist die Standardansicht (ohne #ansicht= in der Adresse)
export function setzeStandard(name) { STANDARD = name; }
const nav = document.getElementById("ansichten");
export function merkeZustand() {
  const teile = [];
  if (AKTIV && AKTIV !== STANDARD) teile.push("ansicht=" + AKTIV);
  const extra = AKTIV && ANSICHTEN[AKTIV].zustand && ANSICHTEN[AKTIV].zustand();
  if (extra) teile.push(extra);
  if (GEBIET) teile.push("gebiet=" + GEBIET.s);
  const neu = teile.length ? "#" + teile.join("&") : location.pathname + location.search;
  try { history.replaceState(null, "", neu); } catch (_) { /* in manchen eingebetteten Ansichten nicht erlaubt */ }
}
export async function zeige(name) {
  const a = ANSICHTEN[name];
  if (!a || name === AKTIV) return;
  if (!a.gestartet) {
    try {
      if (a.starte) await a.starte();
    } catch (fehler) {
      ladeFehler(fehler);
      throw fehler;
    }
    a.gestartet = true;
  }
  const alt = ANSICHTEN[AKTIV];
  if (alt && alt.verbergen) alt.verbergen();
  sucheLeeren();
  AKTIV = name;
  for (const b of nav.querySelectorAll("button")) {
    b.setAttribute("aria-selected", b.dataset.ansicht === name ? "true" : "false");
  }
  a.zeigen();
  merkeZustand();
}
export function knoepfe() {
  const namen = Object.keys(ANSICHTEN);
  nav.innerHTML = namen.length < 2 ? "" : namen.map(n =>
    `<button type="button" role="tab" data-ansicht="${n}" aria-selected="false">`
    + `${esc(ANSICHTEN[n].titel)}</button>`).join("");
  nav.querySelectorAll("button").forEach(b => b.addEventListener("click", () => zeige(b.dataset.ansicht)));
}
