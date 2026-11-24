// vorschlag/00_hilfen.js: Hilfen für das Formular: Namen vergleichen, Abstand, Lage im Gebiet, Pfade, Regeln je Feld.
// Reiter „Vorschlag“: Sportstätte mit ihren Sportanlagen neu eintragen, die Angaben einer
// Sportstätte ändern oder ihre Sportanlagen ändern (hinzufügen, ändern, entfernen).
// Felder, Beschriftungen, Auswahllisten und Regeln kommen aus dem Datenmodell
// (daten/schema.json, erzeugt aus src/sportstaettenatlas/modell/) – ein neues Feld dort
// erscheint hier von selbst. Das Formular prüft die Regeln und auf Doppelungen und öffnet
// dann die LimeSurvey-Umfrage (konfig.js: vorschlag_url): Der ganze Vorschlag steht als JSON
// (Modell „Vorschlag“) in der Frage „data“, die Anmerkung in der Frage „kommentar“.
const VORSCHLAG_FRAGEN = { data: "data", kommentar: "kommentar",
  ...(KONFIG.vorschlag_felder && KONFIG.vorschlag_felder.data ? KONFIG.vorschlag_felder : {}) };
const URL_HOECHSTENS = 8000;  // längere Adressen lehnen manche Webserver ab

// norm_name, aehnlich, abstand_m und org_kern rechnen in bestand/pruefung.py (Python) genauso;
// tests/regeln_faelle.json prüft beide
function normName(s) {
  return String(s || "").toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe")
    .replace(/ü/g, "ue").replace(/ß/g, "ss").replace(/[^a-z0-9]+/g, " ").trim();
}
function bigramme(s) {
  const t = ` ${normName(s)} `, out = new Map();
  for (let i = 0; i < t.length - 1; i++) {
    const b = t.slice(i, i + 2); out.set(b, (out.get(b) || 0) + 1);
  }
  return out;
}
// Ähnlichkeit zweier Namen (Dice-Koeffizient der Buchstabenpaare, 0 … 1)
function aehnlich(a, b) {
  if (!normName(a) || !normName(b)) return 0;
  const x = bigramme(a), y = bigramme(b);
  let gemeinsam = 0, n = 0;
  for (const [k, v] of x) { n += v; gemeinsam += Math.min(v, y.get(k) || 0); }
  for (const v of y.values()) n += v;
  return n ? 2 * gemeinsam / n : 0;
}
// Name einer Organisation ohne Rechtsform („TuS Berg e.V.“ → „tus berg“)
const orgKern = n => normName(n).replace(new RegExp(PRUEFUNG().rechtsform, "g"), " ")
  .replace(/\s+/g, " ").trim();
function abstand(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180, dlat = (lat2 - lat1) * r, dlon = (lon2 - lon1) * r;
  const h = Math.sin(dlat / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dlon / 2) ** 2;
  return 12742000 * Math.asin(Math.sqrt(h));
}
function imRing(x, y, ring) {
  let drin = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) drin = !drin;
  }
  return drin;
}
function punktIn(lon, lat, g) {
  const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
  return polys.some(p => p.length && imRing(lon, lat, p[0]) && !p.slice(1).some(l => imRing(lon, lat, l)));
}
// Name, unter dem eine Kommune als Eigentümer/Betreiber erscheint: "Ortsgemeinde X", "Stadt Y"
function zerlegeAdresse(text) {
  // "Musterstraße 12a, 56068 Koblenz" → Teile; sonst alles als Straße
  const m = /^\s*(.*?)(?:\s+(\d+\s?[a-zA-Z]?(?:\s?[-–]\s?\d+[a-zA-Z]?)?))?\s*,\s*(\d{5})\s+(.+?)\s*$/.exec(text || "");
  if (!m) return { strasse: text || "" };
  return { strasse: m[1] || "", hausnummer: m[2] || "", plz: m[3], ort: m[4] };
}

// Werte in verschachtelten Objekten über Pfade wie "adresse.plz"
function hole(o, pfad) { return pfad.split(".").reduce((x, k) => (x == null ? undefined : x[k]), o); }
function setze(o, pfad, w) {
  const teile = pfad.split(".");
  let x = o;
  for (const k of teile.slice(0, -1)) x = x[k] ??= {};
  x[teile[teile.length - 1]] = w;
}
// leere Werte weglassen (wie beim Speichern in daten/)
function ohneLeere(o) {
  if (Array.isArray(o)) return o.map(ohneLeere).filter(v => !leer(v));
  if (o && typeof o === "object") {
    const r = {};
    for (const [k, v] of Object.entries(o)) {
      const w = ohneLeere(v);
      if (!leer(w) && !(w && typeof w === "object" && !Array.isArray(w) && !Object.keys(w).length)) r[k] = w;
    }
    return r;
  }
  return o;
}
const listeAus = x => String(x || "").split(/[,;]/).map(t => t.trim()).filter(Boolean);
// Regeln eines Feldes aus dem Datenmodell → Liste von Meldungen
function regelFehler(f, w, label) {
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

const NEUER_KOMPLEX = "__neu";  // Auswahl „neuer Sportkomplex“ bei einer Sportstätte

