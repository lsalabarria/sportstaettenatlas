// Einstellungen der Übergabe an LimeSurvey, Regeln je Feld.
import { leer } from "../../lib/text.js";
import { KONFIG } from "../../seite.js";

export const VORSCHLAG_FRAGEN = { data: "data", kommentar: "kommentar",
  ...(KONFIG.vorschlag_felder && KONFIG.vorschlag_felder.data ? KONFIG.vorschlag_felder : {}) };
export const URL_HOECHSTENS = 8000;  // längere Adressen lehnen manche Webserver ab

// Regeln eines Feldes aus dem Datenmodell → Liste von Meldungen
export function regelFehler(f, w, label) {
  const { p, t, pflicht } = f;
  if (leer(w)) return pflicht ? [`${label}: bitte angeben`] : [];
  const out = [];
  if (t.type === "integer" || t.type === "number") {
    if (typeof w !== "number" || Number.isNaN(w) || (t.type === "integer" && !Number.isInteger(w))) {
      return [`${label}: als ${t.type === "integer" ? "ganze " : ""}Zahl`];
    }
  }
  const werte = Array.isArray(w) ? w : [w];
  for (const x of werte) {
    if (t.enum && !t.enum.includes(x) && !t.enum.includes(Number(x))) out.push(`${label}: bitte aus der Liste wählen`);
    if (t.minimum !== undefined && x < t.minimum) out.push(`${label}: mindestens ${t.minimum}`);
    if (t.maximum !== undefined && x > t.maximum) out.push(`${label}: höchstens ${t.maximum}`);
    if (t.pattern && typeof x === "string" && !new RegExp(t.pattern).test(x)) {
      out.push(`${label}: ${p.description || "Format passt nicht"}`);
    }
    if (t.maxLength && String(x).length > t.maxLength) out.push(`${label}: höchstens ${t.maxLength} Zeichen`);
  }
  return out;
}

export const NEUER_KOMPLEX = "__neu";  // Auswahl „neuer Sportkomplex“ bei einer Sportstätte
