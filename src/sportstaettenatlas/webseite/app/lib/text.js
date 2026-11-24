// Kleine Hilfen für Text und Zahlen (ohne Seite, ohne Karte).
const ZAHL = new Intl.NumberFormat("de-DE");
export function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;",
    '"': "&quot;", "'": "&#39;" }[c]));
}
export function leer(v) {
  return v === null || v === undefined || v === "" || v === "nan"
    || (Array.isArray(v) && !v.length);
}
export function zahl(n) { return ZAHL.format(n); }
export function prozent(a, b) { return b ? Math.round(100 * a / b) : 0; }
export function url(u) { return /^https?:\/\//i.test(u) ? u : "https://" + u; }
export function wertText(v) { return typeof v === "boolean" ? (v ? "ja" : "nein") : esc(v); }

// Werte zählen: ["a", "b", "a"] → { a: 2, b: 1 }
export function zaehle(werte) {
  const z = {};
  for (const w of werte) z[w] = (z[w] || 0) + 1;
  return z;
}
// Gefüllte Teile verbinden (Untertitel, Suchtext)
export function verbinde(teile, trenner = " · ") { return teile.filter(v => !leer(v)).join(trenner); }
export function suchtext(teile) { return verbinde(teile, " ").toLowerCase(); }
// Schlüssel für Namen: ohne Groß-/Kleinschreibung und doppelte Leerzeichen
export function schluesselName(s) { return String(s || "").trim().replace(/\s+/g, " ").toLowerCase(); }
