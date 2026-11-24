// Seite: Einstellungen aus konfig.js, Kopfzeile, Laden und Fehler, Dateien aus daten/.
import { esc } from "./lib/text.js";

export const KONFIG = window.KONFIG || {};

// Kopfzeile: Links aus konfig.js. „Sportstätte vorschlagen“ öffnet das Formular,
// „Bug melden“ ein neues Ticket auf GitHub (konfig.js: fehler_url).
export function kopfzeile(mitVorschlag) {
  const k = KONFIG, el = document.getElementById("links");
  const link = (u, text, extra = "") => u ? `<a href="${esc(u)}"${extra}`
    + `${/^https?:/.test(u) ? ' target="_blank" rel="noopener"' : ""}>${text}</a>` : "";
  if (k.titel) { document.querySelector("#kopf h1").textContent = k.titel; document.title = k.titel; }
  el.innerHTML = (mitVorschlag
    ? `<a href="#ansicht=vorschlag" class="knopf" data-vorschlag-neu>Sportstätte vorschlagen</a>` : "")
    + link("daten/", "Daten herunterladen") + link(k.fehler_url, "Bug melden", " data-fehler")
    + link(k.impressum_url, "Impressum") + link(k.datenschutz_url, "Datenschutz");
  // Adresse der Seite und Browser in die Ticket-Vorlage übernehmen (Felder in
  // .github/ISSUE_TEMPLATE/fehler.yml); erst beim Klick, damit Ansicht und Gebiet stimmen
  const bug = el.querySelector("[data-fehler]");
  if (bug) bug.addEventListener("click", () => {
    const u = new URL(k.fehler_url, location.href);
    u.searchParams.set("seite", location.href);
    u.searchParams.set("browser", navigator.userAgent);
    bug.href = u.toString();
  });
}

const ladenEl = document.getElementById("laden");
export function zeigeLaden(text) {
  ladenEl.className = ""; ladenEl.hidden = false;
  ladenEl.innerHTML = `<span class="kreisel"></span><span>${esc(text)}</span>`;
}
export function fertig() { ladenEl.hidden = true; }
export function zeigeFehler(text) {
  ladenEl.hidden = false; ladenEl.className = "fehler"; ladenEl.textContent = text;
}
export function ladeFehler(fehler) {
  zeigeFehler(`Die Daten konnten nicht geladen werden (${fehler.message}).`);
}

// Datei aus daten/ laden; fehlt sie → null
export async function holeJson(name) {
  const r = await fetch("daten/" + name);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
  return r.json();
}
