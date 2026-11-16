// Reiter „Vorschlag“: Sportstätte mit ihren Sportanlagen neu eintragen, die Angaben einer
// Sportstätte ändern oder ihre Sportanlagen ändern (hinzufügen, ändern, entfernen).
// Felder, Beschriftungen, Auswahllisten und Regeln kommen aus dem Datenmodell
// (daten/schema.json, erzeugt aus src/sportstaettenatlas/modell.py) – ein neues Feld dort
// erscheint hier von selbst. Das Formular prüft die Regeln und auf Doppelungen und öffnet
// dann die LimeSurvey-Umfrage (konfig.js: vorschlag_url): Der ganze Vorschlag steht als JSON
// (Modell „Vorschlag“) in der Frage „data“, die Anmerkung in der Frage „kommentar“.
const VORSCHLAG_FRAGEN = { data: "data", kommentar: "kommentar",
  ...(KONFIG.vorschlag_felder && KONFIG.vorschlag_felder.data ? KONFIG.vorschlag_felder : {}) };
const URL_HOECHSTENS = 8000;  // längere Adressen lehnen manche Webserver ab
// ALKIS-Typgruppe → Kategorie des Atlas (nur Vorbelegung, im Formular änderbar)
const GRUPPE_KATEGORIE = { halle: "Sporthalle", spielfeld: "Sportplatz",
  becken: "Schwimmsportstätte", leichtathletik: "Sportplatz" };

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
function kommunenName(g) {
  const bez = g.b === "Kreisfreie Stadt" ? "Stadt" : g.b === "Verbandsfreie Gemeinde" ? "Gemeinde" : g.b;
  if (!bez) return g.n;
  return g.n.toLowerCase().startsWith(bez.toLowerCase()) ? g.n : `${bez} ${g.n}`;
}
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

function ansichtVorschlag(bestand) {
  const el = document.getElementById("seite-vorschlag");
  const NACH_ID = new Map(bestand.eintraege.map(e => [e.p.id, e]));
  let form, vkarte = null, marke = null, nachbarn = null, original = null, quelle = "";
  let lage = null, ars = "", pruefen = 0, dubletten = [];
  const F = n => form.elements.namedItem(n);

  // Felder der Sportstätte aus dem Modell: [{ pfad, p, pflicht, t, gruppe }]; die Teile eines
  // Unterobjekts (Adresse) einzeln als "adresse.plz", die Lage als ein Feld (Karte)
  const FELDER = [];
  for (const [k, p, pflicht, t] of modellFelder("Sportstaette")) {
    if (p.formular === false) continue;
    if (t.ref && p.widget !== "karte") {
      for (const [k2, p2, pf2, t2] of modellFelder(t.ref)) {
        if (p2.formular !== false) FELDER.push({ pfad: `${k}.${k2}`, p: p2, pflicht: pf2, t: t2, gruppe: p.gruppe });
      }
    } else FELDER.push({ pfad: k, p, pflicht, t, gruppe: p.gruppe });
  }
  const TITEL = Object.fromEntries(FELDER.map(f => [f.pfad, f.p.title || f.pfad]));
  TITEL.anlagen = "Sportanlagen";
  const FELD_LAGE = FELDER.find(f => f.p.widget === "karte");
  // Angaben einer Sportanlage neben Typ und Name (Baujahr, Maße, Belag …), nach Abschnitten
  const ANLAGE_DETAILS = modellFelder("Sportanlage")
    .filter(([k, p]) => p.formular !== false && k !== "typ" && k !== "bezeichnung")
    .map(([k, p, pflicht, t], i) => ({ pfad: k, p, pflicht, t, i }));
  const ANLAGE_ABSCHNITTE = SCHEMA.$defs.Sportanlage.gruppen || ["Allgemein"];
  // Einzelne Eingaben: ein Feld, bei „Anzahl je Wert“ (zaehler) eine je Wert ("pfad|Wert")
  const ANLAGE_EINGABEN = ANLAGE_DETAILS.flatMap(d => d.p.widget === "zaehler"
    ? d.t.propertyNames.enum.map(w => ({ k: `${d.pfad}|${w}`, d, wert: w, titel: `${d.p.title}: ${w}` }))
    : [{ k: d.pfad, d, titel: d.p.title }]);
  // Felder einer Organisation; Namen mit "org." davor, damit sie nicht mit der Sportstätte kollidieren
  const ORG_FELDER = modellFelder("Organisation").filter(([, p]) => p.formular !== false)
    .map(([k, p, pflicht, t]) => ({ pfad: "org." + k, k, p, pflicht, t }));
  let orgOriginal = null;  // { o: Eintrag im Verzeichnis oder { name } aus dem Bestand, imVerzeichnis }
  const FELD_TYP = (() => { const x = modellFelder("Sportanlage").find(([k]) => k === "typ");
    return { pfad: "typ", p: x[1], pflicht: true, t: x[3] }; })();

  // Auswahllisten aus dem Datenbestand und den Gebieten
  function haeufig(werte) {
    const z = new Map();
    for (const w of werte) if (!leer(w)) {
      const k = schluesselName(w), x = z.get(k) || { n: 0, namen: new Map() };
      x.n++; x.namen.set(w.trim(), (x.namen.get(w.trim()) || 0) + 1); z.set(k, x);
    }
    return [...z.values()].map(x => [[...x.namen].sort((a, b) => b[1] - a[1])[0][0], x.n]);
  }
  const SPORTARTEN = haeufig(bestand.eintraege.flatMap(e => [...e.sp])).map(x => x[0])
    .sort((a, b) => a.localeCompare(b, "de"));
  // Typen der Sportanlagen (alle bekannten und die im Bestand): nach Gruppe, darin nach Häufigkeit;
  // zur gewählten Kategorie passende zuerst (typListe)
  const ANLAGEN = (() => {
    const z = zaehle(bestand.eintraege.flatMap(e => e.p.anlagen));
    const reihe = ANLAGEN_GRUPPEN.map(g => g[0]);
    return [...new Set([...Object.keys(ANLAGEN_TYPEN), ...Object.keys(z)])].sort((a, b) =>
      reihe.indexOf(anlagenGruppe(a)) - reihe.indexOf(anlagenGruppe(b)) || (z[b] || 0) - (z[a] || 0));
  })();
  const kategorie = () => F("art").value === "anlagen" ? (original && original.p.kategorie) : F("kategorie").value;
  let typListeFuer;
  function typListe() {
    const k = kategorie(), passend = passendeTypen(k);
    if (k === typListeFuer) return;
    typListeFuer = k;
    const liste = passend ? [...ANLAGEN.filter(t => passend.includes(t)), ...ANLAGEN.filter(t => !passend.includes(t))] : ANLAGEN;
    el.querySelector("#v-anlagen-liste").innerHTML = liste.map(t => `<option value="${esc(t)}">`
      + `${esc(gruppenText(anlagenGruppe(t)))}${passend && !passend.includes(t) ? ` – passt nicht zu „${esc(k)}“` : ""}</option>`).join("");
  }
  function organisationen() {
    const verzeichnis = ORGANISATIONEN.map(o => o.name);
    const bisher = haeufig(bestand.eintraege.flatMap(e => [e.p.betreiber, e.p.eigentuemer, ...(e.p.nutzer || [])]))
      .sort((a, b) => b[1] - a[1]).map(x => x[0]);
    const kommunen = GEBIETE.map(kommunenName);
    // erste Schreibweise gewinnt: Verzeichnis vor Bestand vor Kommunen
    const m = new Map();
    for (const n of [...verzeichnis, ...bisher, ...kommunen]) if (!m.has(schluesselName(n))) m.set(schluesselName(n), n);
    return [...m.values()];
  }
  const ORTE = () => [...new Set([...GEBIETE.filter(g => g.e === "gemeinde").map(g => g.n),
    ...bestand.eintraege.map(e => e.p.ort).filter(v => !leer(v))])].sort((a, b) => a.localeCompare(b, "de"));
  const optionen = liste => liste.map(v => `<option value="${esc(v)}"></option>`).join("");
  const auswahl = (name, werte, leerText) => `<select name="${esc(name)}">`
    + `<option value="">${leerText}</option>` + werte.map(v => `<option>${esc(v)}</option>`).join("") + `</select>`;
  const jaNein = name => `<span class="radios">` + [["ja", "Ja"], ["nein", "Nein"], ["", "Nicht bekannt"]]
    .map(([w, t]) => `<label><input type="radio" name="${esc(name)}" value="${w}"${w ? "" : " checked"}> ${t}</label>`).join("") + `</span>`;
  const feld = (label, inhalt, extra = "") => `<label class="feld${extra}"><span>${label}</span>${inhalt}</label>`;
  const istZahl = t => t.type === "integer" || t.type === "number";

  // Eingabe für ein Feld des Modells, nach Typ und widget
  function eingabe(f) {
    const { pfad, p, pflicht, t } = f, n = esc(pfad);
    const label = esc(p.title || pfad) + (pflicht ? " *" : "");
    const hilfe = p.description ? ` placeholder="${esc(p.description)}" title="${esc(p.description)}"` : "";
    if (p.widget === "karte") {
      return `<div class="lage"><b>${label}</b> <span id="v-lage"></span>
        <button type="button" class="knopf2" id="v-geocode">Lage aus der Adresse suchen</button>
        <div id="v-gemeinde" class="hinweis"></div></div>`;
    }
    if (p.widget === "chips" || p.widget === "organisationen") {
      const liste = p.widget === "organisationen" ? "v-orgs" : "v-sportarten-liste";
      return `<div class="chips-feld" data-chips="${n}"><span class="chips-titel">${label}</span><div class="chips"></div>
        <div class="hinzu"><input list="${liste}" placeholder="${label} eingeben oder auswählen"
        aria-label="${label}"><button type="button" class="knopf2">Hinzufügen</button></div></div>`;
    }
    if (p.widget === "ja_nein") return `<div class="zeile-feld"><span>${label}</span>${jaNein(pfad)}</div>`;
    if (t.enum) return feld(label, auswahl(pfad, t.enum, pflicht ? "– bitte wählen –" : "nicht bekannt"));
    if (istZahl(t)) {
      return feld(label, `<input name="${n}" type="number" step="1"`
        + (t.minimum !== undefined ? ` min="${t.minimum}"` : "") + (t.maximum !== undefined ? ` max="${t.maximum}"` : "")
        + `>`, " klein");
    }
    if (t.type === "array") return feld(label, `<input name="${n}" placeholder="mehrere mit Komma trennen">`);
    const liste = p.widget === "organisation" ? ` list="v-orgs"` : p.widget === "ort" ? ` list="v-orte"` : "";
    const art = p.widget === "organisation" ? `<span class="art" data-art="${n}" hidden></span>` : "";
    return feld(label, `<input name="${n}"${p.widget === "url" ? ` type="url"` : ""}${liste}`
      + (t.maxLength ? ` maxlength="${t.maxLength}"` : "") + `${hilfe}>${art}`);
  }
  // Abschnitte in der Reihenfolge des Modells (gruppen); Felder ohne Gruppe am Ende
  function abschnitte() {
    const gruppen = [...(SCHEMA.$defs.Sportstaette.gruppen || [])];
    for (const f of FELDER) if (!gruppen.includes(f.gruppe || "Weitere Angaben")) gruppen.push(f.gruppe || "Weitere Angaben");
    return gruppen.map(g => {
      const fs = FELDER.filter(f => (f.gruppe || "Weitere Angaben") === g);
      return fs.length ? `<fieldset><legend>${esc(g)}</legend>${fs.map(eingabe).join("")}</fieldset>` : "";
    }).join("");
  }

  function baue() {
    el.innerHTML = `<div class="inhalt vorschlag"><h2>Vorschlag machen</h2>
      <p class="unter">Neue Sportstätte mit ihren Sportanlagen eintragen, die Angaben einer Sportstätte
      ändern, ihre Sportanlagen hinzufügen, ändern und entfernen oder eine Organisation (Verein, Eigentümer,
      Betreiber) eintragen, ändern und löschen. Im nächsten Schritt
      werden die Angaben an die Umfrage übergeben und dort abgeschickt; nach einer Prüfung erscheinen
      sie auf der Karte. Bitte keine personenbezogenen Daten (Namen, private Telefonnummern) eintragen.</p>
      <div class="raster"><form id="v-form" novalidate autocomplete="off">
      <fieldset><legend>Was möchten Sie tun?</legend>
        <span class="radios gross"><label><input type="radio" name="art" value="neu" checked> Neue Sportstätte mit ihren Sportanlagen eintragen</label>
        <label><input type="radio" name="art" value="aenderung"> Angaben einer Sportstätte ändern (Name, Adresse, Betreiber …)</label>
        <label><input type="radio" name="art" value="anlagen"> Sportanlagen einer Sportstätte ändern (hinzufügen, ändern, entfernen)</label>
        <label><input type="radio" name="art" value="organisation"> Organisation (Verein, Eigentümer, Betreiber …) eintragen, ändern oder löschen</label></span>
        <div id="v-auswahl" hidden><input type="search" id="v-suche" placeholder="Name, Ort oder ID der Sportstätte suchen"
          aria-label="Sportstätte suchen"><ul id="v-treffer" class="treffer"></ul></div>
        <div id="v-gewaehlt"></div>
      </fieldset>
      <div id="v-teil-staette">${abschnitte()}</div>
      <fieldset id="v-teil-anlagen"><legend>Sportanlagen</legend>
        <p class="hinweis">Die einzelnen Anlagen der Sportstätte, z. B. Großspielfeld, Rundlaufbahn, Hallenteil.
        Jede Sportanlage gehört zu genau dieser Sportstätte. Name nur, wenn die Anlage einen eigenen hat
        (z. B. „Halle 1“, „Kunstrasen B“).</p>
        <table class="anlagen"><thead><tr><th>${esc(FELD_TYP.p.title)} *</th><th>${esc(modellFelder("Sportanlage")
          .find(([k]) => k === "bezeichnung")[1].title)}</th><th>Anzahl</th><th>weitere Angaben</th></tr></thead>
          <tbody id="v-anlagen"></tbody></table>
        <button type="button" class="knopf2" id="v-anlage-dazu">+ Sportanlage hinzufügen</button>
      </fieldset>
      <fieldset id="v-teil-org" hidden><legend>Organisation</legend>
        <p class="hinweis">Vereine, Kommunen, Verbände, Unternehmen, die Sportstätten besitzen, betreiben oder
        nutzen. Sportstätten nennen sie beim Namen. Keine Personen und keine Kontaktdaten.</p>
        <input type="search" id="v-org-suche" placeholder="vorhandene Organisation suchen (leer lassen für eine neue)"
          aria-label="Organisation suchen"><ul id="v-org-treffer" class="treffer"></ul>
        <div id="v-org-gewaehlt"></div>
        <div id="v-org-felder">${ORG_FELDER.map(eingabe).join("")}</div>
        <label class="bestaetigen" id="v-org-weg" hidden><input type="checkbox" name="org-loeschen">
          Diese Organisation aus dem Verzeichnis löschen (z. B. aufgelöst oder doppelt)</label>
      </fieldset>
      <fieldset><legend>Anmerkung</legend>
        <textarea name="anmerkung" rows="3" maxlength="1000" placeholder="Was soll geändert werden, Quelle der Angaben …"></textarea>
      </fieldset>
      <div id="v-fehler" class="fehlerbox" hidden></div>
      <div class="weiter"><button type="submit" class="knopf-gross">Weiter zu LimeSurvey →</button>
        <button type="button" class="knopf2" id="v-leeren">Formular leeren</button></div>
      <div id="v-ausgabe"></div>
      </form>
      <aside><div id="v-karte" aria-label="Karte zur Lage"></div>
        <div class="hinweis">Klick in die Karte setzt die Lage, die Markierung lässt sich verschieben. Graue Punkte: vorhandene Sportstätten.</div>
        <div id="v-aenderungen"></div><div id="v-hinweise"></div><div id="v-dubletten"></div></aside></div>
      <datalist id="v-orte">${optionen(ORTE())}</datalist>
      <datalist id="v-orgs">${optionen(organisationen())}</datalist>
      <datalist id="v-sportarten-liste">${optionen(SPORTARTEN)}</datalist>
      <datalist id="v-anlagen-liste"></datalist></div>`;
    form = el.querySelector("#v-form");
    form.addEventListener("input", () => { zeigeArten(); planePruefung(); });
    form.addEventListener("change", ev => {
      if (ev.target.name === "art") {
        const art = F("art").value;
        if (art === "organisation") { waehleOrg(null); zeigeTeile(); zeigeGewaehlt(); planePruefung(); return; }
        if (art === "neu") neu();
        else if (original && original.art !== art) { original.art = art; fuelle(ausEintrag(original)); }
        zeigeTeile(); zeigeGewaehlt();
      }
      planePruefung();
    });
    form.addEventListener("submit", ev => { ev.preventDefault(); weiter(); });
    el.querySelector("#v-leeren").addEventListener("click", () => neu());
    const geo = el.querySelector("#v-geocode");
    if (geo) geo.addEventListener("click", lageAusAdresse);
    for (const box of el.querySelectorAll("[data-chips]")) {
      const pfad = box.dataset.chips, eing = box.querySelector("input");
      const dazu = () => { const v = eing.value.trim(); if (v) { chips[pfad].add(v); eing.value = ""; zeigeChips(pfad); planePruefung(); } };
      box.querySelector("button").addEventListener("click", dazu);
      eing.addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); dazu(); } });
    }
    el.querySelector("#v-anlage-dazu").addEventListener("click", () => {
      anlageZeile({ typ: "", bezeichnung: "", id: "" }, 1); planePruefung();
      const z = el.querySelectorAll("#v-anlagen tr"); z[z.length - 1].querySelector("input").focus();
    });
    const suche = el.querySelector("#v-suche"), treffer = el.querySelector("#v-treffer");
    suche.addEventListener("input", () => {
      const worte = normName(suche.value).split(" ").filter(Boolean);
      if (!worte.length) { treffer.innerHTML = ""; return; }
      const t = [];
      for (const e of bestand.eintraege) {
        const text = normName([e.p.name, e.p.ort, e.p.adresse, e.p.id].join(" "));
        if (worte.every(w => text.includes(w))) t.push(e);
        if (t.length >= 8) break;
      }
      treffer.innerHTML = t.map(e => `<li data-id="${esc(e.p.id)}">${esc(e.p.name || e.kat)}`
        + `<small>${esc(verbinde([e.p.kategorie, e.p.adresse]))}</small></li>`).join("")
        || `<li class="gruppe">Keine Sportstätte gefunden</li>`;
    });
    treffer.addEventListener("click", ev => {
      const li = ev.target.closest("li[data-id]");
      if (li) bearbeite(li.dataset.id, F("art").value);
    });
    const orgSuche = el.querySelector("#v-org-suche"), orgTreffer = el.querySelector("#v-org-treffer");
    orgSuche.addEventListener("input", () => {
      const q = schluesselName(orgSuche.value);
      orgTreffer.innerHTML = q ? orgListe().filter(x => x.such.includes(q)).slice(0, 8).map(x =>
        `<li data-org="${esc(x.name)}">${esc(x.name)}<small>${esc(verbinde([x.o ? x.o.typ || "im Verzeichnis, ohne Art"
          : "noch nicht im Verzeichnis", nutzungText(x.name)]))}</small></li>`).join("")
        || `<li class="gruppe">Nichts gefunden – unten als neue Organisation eintragen</li>` : "";
    });
    orgTreffer.addEventListener("click", ev => {
      const li = ev.target.closest("li[data-org]");
      if (!li) return;
      orgSuche.value = ""; orgTreffer.innerHTML = "";
      waehleOrg(li.dataset.org); zeigeTeile(); planePruefung();
    });
  }

  // Felder mit widget "chips" (Sportarten): Liste zum Hinzufügen und Entfernen
  const chips = {};
  for (const f of FELDER) if (f.p.widget === "chips" || f.p.widget === "organisationen") chips[f.pfad] = new Set();
  function zeigeChips(pfad) {
    const c = el.querySelector(`[data-chips="${pfad}"] .chips`);
    c.innerHTML = [...chips[pfad]].map(s => `<span class="chip-s">${esc(s)}<button type="button" `
      + `data-weg="${esc(s)}" aria-label="${esc(s)} entfernen">×</button></span>`).join("")
      || `<span class="hinweis">noch keine</span>`;
    c.querySelectorAll("[data-weg]").forEach(b => b.addEventListener("click", () => {
      chips[pfad].delete(b.dataset.weg); zeigeChips(pfad); planePruefung(); }));
  }
  // Eine Zeile je Sportanlage, darunter aufklappbar ihre weiteren Angaben (aus dem Modell, nach
  // Abschnitten). Gezeigt werden die Felder, die zum Typ passen (Angabe fuer), und alle mit Wert.
  // Vorhandene Anlagen (mit Kurz-ID) lassen sich ändern oder zum Entfernen markieren; neue
  // lassen sich mit Anzahl eintragen (z. B. 3× Tennisplatz).
  const alsText = w => leer(w) ? "" : Array.isArray(w) ? w.join(", ") : String(w);
  const angaben = a => {
    const o = { typ: a.typ || "", bezeichnung: a.bezeichnung || "" };
    for (const e of ANLAGE_EINGABEN) o[e.k] = alsText(e.wert ? (a[e.d.pfad] || {})[e.wert] : a[e.k]);
    return o;
  };
  const zahlAttr = t => ` type="number" step="${t.type === "integer" ? 1 : "any"}"`
    + (t.minimum !== undefined ? ` min="${t.minimum}"` : "") + (t.maximum !== undefined ? ` max="${t.maximum}"` : "");
  function detailEingabe(d, alt) {
    const { pfad, p, t } = d, n = esc(pfad);
    const label = esc(p.title || pfad) + (p.einheit ? ` (${esc(p.einheit)})` : "");
    const hilfe = p.description ? ` title="${esc(p.description)}"` : "";
    const huelle = (inhalt, klasse = "") => `<label class="${klasse}" data-d="${d.i}"${hilfe}>${label}${inhalt}</label>`;
    const auswahl = (werte, w) => `<select data-f="${n}"><option value="">–</option>` + werte.map(x =>
      `<option${String(x) === w ? " selected" : ""}>${esc(x)}</option>`).join("") + `</select>`;
    if (p.widget === "zaehler") {
      return `<div class="zaehler" data-d="${d.i}"${hilfe}><span>${label}</span><div>` + t.propertyNames.enum.map(w =>
        `<label>${esc(w)}<input data-f="${n}|${esc(w)}" value="${esc(alt[`${pfad}|${w}`])}"${zahlAttr(t.additionalProperties || {})}></label>`).join("")
        + `</div></div>`;
    }
    if (p.widget === "ja_nein") return huelle(auswahl(["ja", "nein"], alt[pfad]));
    if (t.enum) return huelle(auswahl(t.enum, alt[pfad]));
    const attr = istZahl(t) ? zahlAttr(t)
      : t.type === "array" ? ` placeholder="${esc(p.description || "mehrere mit Komma trennen")}"`
        + (pfad === "sportarten" || pfad === "wettkampf" ? ` list="v-sportarten-liste"` : "")
      : (p.description ? ` placeholder="${esc(p.description)}"` : "");
    return huelle(`<input data-f="${n}" value="${esc(alt[pfad])}"${attr}>`, t.type === "array" && p.widget !== "jahr" ? "breit" : "");
  }
  // Felder zeigen, die zum Typ passen; mit Häkchen „alle Felder“ auch die übrigen
  function zeigePassend(tr, mehr) {
    const typ = tr.querySelector('[data-f="typ"]').value.trim(), alle = mehr.querySelector(".alle input").checked;
    let verborgen = 0;
    mehr.querySelectorAll("[data-d]").forEach(x => {
      const d = ANLAGE_DETAILS[+x.dataset.d], hatWert = [...x.querySelectorAll("[data-f]")].some(i => i.value);
      x.hidden = !(alle || hatWert || passtFuer(d.p, typ));
      if (x.hidden) verborgen++;
    });
    mehr.querySelectorAll(".anlage-abschnitt").forEach(g => { g.hidden = ![...g.querySelectorAll("[data-d]")].some(x => !x.hidden); });
    const hin = mehr.querySelector(".alle span");
    hin.textContent = alle ? "alle Felder zeigen" : `auch ${zahl(verborgen)} Felder zeigen, die nicht zu diesem Typ passen`;
    mehr.querySelector(".alle").hidden = !alle && !verborgen;
  }
  function anlageZeile(a, anzahl = 1) {
    const tr = document.createElement("tr"), mehr = document.createElement("tr");
    const vorhanden = !!a.id, alt = angaben(a);
    tr.className = "anlage"; mehr.className = "anlage-mehr"; mehr.hidden = true;
    tr.dataset.id = a.id || ""; tr.dataset.alt = JSON.stringify(alt);
    tr.innerHTML = `<td><input data-f="typ" list="v-anlagen-liste" value="${esc(alt.typ)}" aria-label="Typ"`
      + ` placeholder="z. B. Großspielfeld"><div class="typ-hinweis hinweis" hidden></div></td>`
      + `<td><input data-f="bezeichnung" value="${esc(alt.bezeichnung)}" aria-label="Name" placeholder="optional"></td>`
      + `<td>${vorhanden ? `<span class="q" title="Kennung der Anlage">${esc(a.id)}</span>`
        : `<input data-f="anzahl" type="number" min="1" step="1" value="${anzahl}" aria-label="Anzahl">`}</td>`
      + `<td class="aktionen"><button type="button" class="mehr" aria-expanded="false" title="weitere Angaben">Angaben ▸</button>`
      + `<button type="button" class="weg" aria-label="${vorhanden ? "Anlage entfernen" : "Zeile löschen"}"`
      + ` title="${vorhanden ? "Diese Anlage gibt es nicht mehr" : "Zeile löschen"}">×</button></td>`;
    mehr.innerHTML = `<td colspan="4">` + ANLAGE_ABSCHNITTE.map(g => {
      const ds = ANLAGE_DETAILS.filter(d => (d.p.gruppe || "Allgemein") === g);
      return ds.length ? `<div class="anlage-abschnitt"><h5>${esc(g)}</h5>`
        + `<div class="anlage-felder">${ds.map(d => detailEingabe(d, alt)).join("")}</div></div>` : "";
    }).join("") + `<label class="alle hinweis"><input type="checkbox"> <span></span></label></td>`;
    const knopf = tr.querySelector(".mehr");
    const klappe = auf => { mehr.hidden = !auf; knopf.textContent = auf ? "Angaben ▾" : "Angaben ▸";
      knopf.setAttribute("aria-expanded", auf); };
    knopf.addEventListener("click", () => klappe(mehr.hidden));
    if (ANLAGE_EINGABEN.some(e => alt[e.k])) knopf.classList.add("hat");
    tr.querySelector('[data-f="typ"]').addEventListener("input", () => zeigePassend(tr, mehr));
    mehr.querySelector(".alle input").addEventListener("change", () => zeigePassend(tr, mehr));
    tr.querySelector(".weg").addEventListener("click", () => {
      if (!vorhanden) { tr.remove(); mehr.remove(); }
      else {
        const weg = !tr.classList.contains("entfernt");
        tr.classList.toggle("entfernt", weg);
        [tr, mehr].forEach(z => z.querySelectorAll("input, select").forEach(i => { i.disabled = weg; }));
        if (weg) klappe(false);
        const b = tr.querySelector(".weg");
        b.textContent = weg ? "↺" : "×"; b.title = weg ? "doch behalten" : "Diese Anlage gibt es nicht mehr";
      }
      planePruefung();
    });
    const ziel = el.querySelector("#v-anlagen");
    ziel.appendChild(tr); ziel.appendChild(mehr);
    zeigePassend(tr, mehr);
  }
  // [{ id, typ, bezeichnung, …Angaben als Text (Schlüssel wie ANLAGE_EINGABEN), n, entfernt, alt }]
  function anlagenListe() {
    const out = [];
    for (const tr of el.querySelectorAll("#v-anlagen tr.anlage")) {
      const w = {};
      for (const z of [tr, tr.nextElementSibling]) z.querySelectorAll("[data-f]").forEach(i => { w[i.dataset.f] = i.value.trim(); });
      const a = { ...w, id: tr.dataset.id, n: w.anzahl ? Math.max(1, parseInt(w.anzahl, 10) || 1) : 1,
        entfernt: tr.classList.contains("entfernt"), alt: JSON.parse(tr.dataset.alt) };
      delete a.anzahl;
      if (a.typ || a.id) out.push(a);
    }
    return out;
  }
  // Angabe einer Anlage (Text aus dem Formular) → Wert nach dem Modell
  const zahlAus = x => Number(String(x).replace(",", "."));
  function detailWert(d, a) {
    if (d.p.widget === "zaehler") {
      const o = {};
      for (const w of d.t.propertyNames.enum) { const x = a[`${d.pfad}|${w}`]; if (!leer(x)) o[w] = zahlAus(x); }
      return Object.keys(o).length ? o : null;
    }
    const x = a[d.pfad];
    if (leer(x)) return null;
    if (istZahl(d.t) || (d.t.enum && typeof d.t.enum[0] === "number")) return zahlAus(x);
    return d.t.type === "array" ? listeAus(x) : x;
  }
  // Sportanlage als Objekt nach dem Modell (für den Vorschlag); id = Kurz-ID vorhandener Anlagen.
  // Sportarten mit Wettkampfeignung kommen auch unter die Sportarten (Regel teil_von).
  function anlageModell(a) {
    const o = { typ: a.typ };
    if (a.id) o.id = a.id;
    if (a.bezeichnung) o.bezeichnung = a.bezeichnung;
    for (const d of ANLAGE_DETAILS) { const w = detailWert(d, a); if (!leer(w)) o[d.pfad] = w; }
    for (const d of ANLAGE_DETAILS) if (d.p.teil_von && o[d.pfad]) {
      o[d.p.teil_von] = [...new Set([...(o[d.p.teil_von] || []), ...o[d.pfad]])];
    }
    return o;
  }
  const anlageKurz = a => (a.n > 1 ? `${a.n}× ` : "") + a.typ + (a.bezeichnung ? ` (${a.bezeichnung})` : "");
  const anlageDetailText = a => ANLAGE_EINGABEN.filter(e => a[e.k]).map(e => `${e.titel}: ${a[e.k]}`).join("; ");
  const anlageText = a => anlageKurz(a) + (anlageDetailText(a) ? ` – ${anlageDetailText(a)}` : "");
  // Was sich an den Anlagen ändert (für die Anzeige „Ihre Änderungen“)
  function anlagenAenderung(liste) {
    const out = [];
    const titel = k => k === "typ" ? FELD_TYP.p.title : k === "bezeichnung" ? "Name"
      : ANLAGE_EINGABEN.find(e => e.k === k).titel;
    for (const a of liste) {
      if (!a.id) { out.push(`neu: ${anlageText(a)}`); continue; }
      const alt = { ...a.alt, n: 1 };
      if (a.entfernt) { out.push(`entfernen [${a.id}]: ${anlageKurz(alt)}`); continue; }
      const felder = ["typ", "bezeichnung", ...ANLAGE_EINGABEN.map(e => e.k)].filter(k => (a[k] || "") !== (alt[k] || ""));
      if (felder.length) {
        out.push(`ändern [${a.id}] ${anlageKurz(alt)}: ` + felder.map(k =>
          `${titel(k)} ${alt[k] || "(leer)"} → ${a[k] || "(leer)"}`).join("; "));
      }
    }
    return out;
  }
  // Teile des Formulars je nach Art des Vorschlags
  function zeigeTeile() {
    const art = F("art").value;
    el.querySelector("#v-teil-staette").hidden = art === "anlagen" || art === "organisation";
    el.querySelector("#v-teil-anlagen").hidden = art === "aenderung" || art === "organisation";
    el.querySelector("#v-teil-org").hidden = art !== "organisation";
    el.querySelector(".vorschlag aside").hidden = art === "organisation";
    el.querySelector("#v-org-weg").hidden = !(orgOriginal && orgOriginal.imVerzeichnis);
  }
  // Eigentümer/Betreiber: steht die Organisation im Verzeichnis, ihre Art übernehmen (wenn
  // noch keine gewählt ist); dahinter steht, ob sie im Verzeichnis ist (geschätzt wird nicht)
  function zeigeArten() {
    for (const f of FELDER.filter(x => x.p.widget === "organisation")) {
      const name = F(f.pfad).value, o = orgVon(name), s = el.querySelector(`[data-art="${f.pfad}"]`);
      const typ = F(f.pfad + "_typ");
      if (o && o.typ && typ && !typ.value && typ.dataset.vonOrg !== name) {
        typ.value = o.typ; typ.dataset.vonOrg = name;
      }
      const a = !name.trim() ? "" : o ? "im Verzeichnis" + (o.typ ? "" : ", ohne Art") : "nicht im Verzeichnis";
      s.textContent = a; s.hidden = !a;
    }
  }

  // --- Organisationen ---
  // Wer nennt welche Organisation? Einmal aufgebaut: Name (schluesselName) → Rolle → Sportstätten
  let nutzungsIndex = null, orgListeCache = null;
  function index() {
    if (nutzungsIndex) return nutzungsIndex;
    nutzungsIndex = new Map();
    const dazu = (name, rolle, e) => {
      const k = schluesselName(name);
      if (!k) return;
      if (!nutzungsIndex.has(k)) nutzungsIndex.set(k, { eigentuemer: new Set(), betreiber: new Set(), nutzer: new Set() });
      nutzungsIndex.get(k)[rolle].add(e);
    };
    for (const e of bestand.eintraege) {
      dazu(e.p.eigentuemer, "eigentuemer", e);
      dazu(e.p.betreiber, "betreiber", e);
      for (const n of e.p.nutzer || []) dazu(n, "nutzer", e);
    }
    return nutzungsIndex;
  }
  // Verzeichnis und Namen aus dem Bestand, die (noch) nicht darin stehen (einmal berechnet)
  function orgListe() {
    if (orgListeCache) return orgListeCache;
    const out = ORGANISATIONEN.map(o => ({ name: o.name, o,
      such: [o.name, ...(o.weitere_namen || [])].map(schluesselName).join(" ") }));
    const da = new Set(ORG_NACH_NAME.keys()), ix = index();
    for (const n of organisationen()) {
      const k = schluesselName(n);
      if (!da.has(k) && ix.has(k)) { da.add(k); out.push({ name: n, o: null, such: k }); }
    }
    return orgListeCache = out;
  }
  // Wie oft nennen Sportstätten diese Organisation (alle Schreibweisen)?
  function nutzung(name) {
    const o = orgVon(name), ix = index();
    const namen = new Set([name, ...(o ? [o.name, ...(o.weitere_namen || [])] : [])].map(schluesselName));
    const je = { eigentuemer: new Set(), betreiber: new Set(), nutzer: new Set() }, alle = new Set();
    for (const k of namen) {
      const x = ix.get(k);
      if (x) for (const r in je) for (const e of x[r]) { je[r].add(e); alle.add(e); }
    }
    return { eigentuemer: je.eigentuemer.size, betreiber: je.betreiber.size, nutzer: je.nutzer.size, n: alle.size };
  }
  function nutzungText(name) {
    const z = nutzung(name);
    return z.n ? `${zahl(z.n)} Sportstätten (` + [["eigentuemer", "Eigentümer"], ["betreiber", "Betreiber"], ["nutzer", "Nutzer"]]
      .filter(([k]) => z[k]).map(([k, t]) => `${t} ${zahl(z[k])}`).join(", ") + ")" : "keine Sportstätte nennt sie";
  }
  // Organisation zum Ändern wählen (Name aus der Liste) oder null für eine neue
  function waehleOrg(name) {
    const o = name ? orgVon(name) : null;
    orgOriginal = name ? { o: o || { name }, imVerzeichnis: !!o } : null;
    const werte = orgOriginal ? orgOriginal.o : {};
    for (const f of ORG_FELDER) {
      const e = F(f.pfad), w = werte[f.k];
      e.value = leer(w) ? "" : Array.isArray(w) ? w.join(", ") : w;
    }
    if (F("org-loeschen")) F("org-loeschen").checked = false;
    const g = el.querySelector("#v-org-gewaehlt");
    g.innerHTML = orgOriginal ? `<div class="chip">${orgOriginal.imVerzeichnis ? "Sie ändern" : "Noch nicht im Verzeichnis, Sie tragen ein"}: `
      + `<b>${esc(orgOriginal.o.name)}</b> <span class="q">${esc(nutzungText(orgOriginal.o.name))}</span>`
      + ` <button type="button">stattdessen eine neue</button></div>` : "";
    const b = g.querySelector("button");
    if (b) b.addEventListener("click", () => { waehleOrg(null); zeigeTeile(); planePruefung(); });
  }
  function orgWerte() {
    const o = {};
    for (const f of ORG_FELDER) {
      const x = String(F(f.pfad).value || "").trim();
      if (x) o[f.k] = f.t.type === "array" ? listeAus(x) : x;
    }
    return o;
  }
  function orgFehler(o, loeschen) {
    if (loeschen) return [];
    const fehler = [];
    for (const f of ORG_FELDER) fehler.push(...regelFehler(f, o[f.k], f.p.title));
    fehler.push(...regelnZwischen("Organisation", o));
    // Name oder Schreibweise schon bei einer anderen Organisation im Verzeichnis?
    const eigene = orgOriginal && orgOriginal.imVerzeichnis ? orgOriginal.o.id : null;
    for (const n of [o.name, ...(o.weitere_namen || [])]) {
      const andere = orgVon(n);
      if (n && andere && andere.id !== eigene) fehler.push(`„${n}“ steht schon im Verzeichnis (${andere.name}) – bitte oben suchen und ändern`);
    }
    return fehler;
  }
  function orgAenderungen(o) {
    if (!orgOriginal) return Object.keys(o);
    const alt = orgOriginal.o, text = x => Array.isArray(x) ? x.join(", ") : (x || "");
    return ORG_FELDER.map(f => f.k).filter(k => text(alt[k]) !== text(o[k]));
  }

  // --- Karte im Formular ---
  function starteKarte() {
    if (vkarte) { vkarte.invalidateSize(); return; }
    vkarte = L.map("v-karte", { preferCanvas: true, maxZoom: 19 });
    L.tileLayer(BASEMAP, { layer: "de_basemapde_web_raster_farbe", maxNativeZoom: 18, maxZoom: 19,
      attribution: BKG }).addTo(vkarte);
    vkarte.fitBounds(karte.getBounds());
    nachbarn = L.layerGroup().addTo(vkarte);
    for (const e of bestand.eintraege) {
      L.circleMarker([e.lat, e.lon], { radius: 4, weight: 1, color: "#fff", fillColor: "#7a7975",
        fillOpacity: 0.9 }).bindTooltip(esc(e.p.name || e.kat)).bindPopup(() =>
        `<b>${esc(e.p.name || e.kat)}</b><br>${esc(e.p.kategorie || "")}<br>${esc(e.p.adresse || "")}`
        + `<br><a href="#" data-bearbeiten="${esc(e.p.id)}">Diese Sportstätte ändern</a>`).addTo(nachbarn);
    }
    vkarte.on("click", ev => setzeLage(ev.latlng.lat, ev.latlng.lng));
  }
  function setzeLage(lat, lon, zoomen = false) {
    lage = lat == null ? null : [+lat, +lon];
    if (marke) { marke.remove(); marke = null; }
    const t = el.querySelector("#v-lage");
    if (!lage) { t.textContent = "Bitte in der Karte rechts auf die Sportstätte klicken."; ars = "";
      el.querySelector("#v-gemeinde").textContent = ""; planePruefung(); return; }
    t.innerHTML = `<span class="koord">${lage[0].toFixed(6)}, ${lage[1].toFixed(6)}</span>`;
    if (vkarte) {
      marke = L.marker(lage, { draggable: true, keyboard: false, icon: L.divIcon({ className: "",
        iconSize: [26, 34], iconAnchor: [13, 32], html: `<div class="nadel"></div>` }) }).addTo(vkarte);
      marke.on("dragend", () => { const p = marke.getLatLng(); setzeLage(p.lat, p.lng); });
      if (zoomen) vkarte.setView(lage, Math.max(vkarte.getZoom(), 17));
    }
    bestimmeGemeinde();
    planePruefung();
  }
  async function bestimmeGemeinde() {
    const ziel = el.querySelector("#v-gemeinde");
    ars = "";
    if (!lage || !GEBIETE.length) { ziel.textContent = ""; return; }
    const fc = await ladeUmrisse("gemeinde"), [lat, lon] = lage;
    if (!fc || !lage || lage[0] !== lat) return;
    const f = fc.features.find(x => x.geometry && punktIn(lon, lat, x.geometry));
    const g = f && NACH_S[f.properties.s];
    ars = g ? g.s : "";
    ziel.textContent = g ? `Gemeinde: ${gebietTitel(g)}` : "Liegt außerhalb von Rheinland-Pfalz?";
    const ort = F("adresse.ort");
    if (g && ort && !ort.value.trim()) ort.value = g.n;
  }
  async function lageAusAdresse() {
    const w = n => (F(`adresse.${n}`) ? F(`adresse.${n}`).value : "");
    const q = [w("strasse") + " " + w("hausnummer"), w("plz") + " " + w("ort")]
      .map(s => s.trim()).filter(Boolean).join(", ");
    const b = el.querySelector("#v-geocode");
    if (!q) { zeigeFehlerliste(["Für die Suche bitte Straße und Ort eintragen."]); return; }
    b.disabled = true; b.textContent = "suche …";
    try {
      const t = await geocode(q);
      if (t.length) { const c = t[0].grenzen().getCenter(); setzeLage(c.lat, c.lng, true); }
      else zeigeFehlerliste(["Adresse nicht gefunden – bitte die Lage in der Karte setzen."]);
    } catch (_) { zeigeFehlerliste(["Adresssuche gerade nicht erreichbar – bitte die Lage in der Karte setzen."]); }
    b.disabled = false; b.textContent = "Lage aus der Adresse suchen";
  }

  // --- Werte lesen und setzen (Sportstätte verschachtelt wie im Modell) ---
  function leseFeld(f) {
    if (f.p.widget === "karte") return lage ? { lon: +lage[1].toFixed(6), lat: +lage[0].toFixed(6) } : null;
    if (f.p.widget === "chips" || f.p.widget === "organisationen") return [...chips[f.pfad]];
    const x = String(F(f.pfad).value || "").trim();
    if (x === "") return f.t.type === "array" ? [] : null;
    if (istZahl(f.t)) return Number(x.replace(",", "."));
    return f.t.type === "array" ? listeAus(x) : x;
  }
  function werte() {
    const s = {};
    for (const f of FELDER) setze(s, f.pfad, leseFeld(f));
    return { art: F("art").value, sportstaette: s, anlagenliste: anlagenListe(), organisation: orgWerte(),
      loeschen: !!(F("org-loeschen") && F("org-loeschen").checked),
      anmerkung: (F("anmerkung").value || "").trim() };
  }
  function fuelle(v) {
    for (const f of FELDER) {
      const w = hole(v, f.pfad);
      if (f.p.widget === "karte") continue;
      if (f.p.widget === "chips" || f.p.widget === "organisationen") { chips[f.pfad] = new Set(w || []); zeigeChips(f.pfad); continue; }
      if (f.p.widget === "ja_nein") {
        const x = w === "ja" || w === "nein" ? w : "";
        form.querySelectorAll(`input[name="${f.pfad}"]`).forEach(i => { i.checked = i.value === x; });
        continue;
      }
      const e = F(f.pfad);
      if (e.tagName === "SELECT" && !leer(w) && ![...e.options].some(o => o.value === w)) e.add(new Option(w));
      e.value = leer(w) ? "" : Array.isArray(w) ? w.join(", ") : w;
    }
    F("anmerkung").value = v.anmerkung || "";
    el.querySelector("#v-anlagen").innerHTML = "";
    for (const a of v.anlagen || []) anlageZeile(a);
    setzeLage(v.lage ? v.lage.lat : null, v.lage ? v.lage.lon : null, true);
    zeigeArten();
  }
  // Sportstätte aus dem Datenbestand → Werte für das Formular (Teile der Adresse stehen flach)
  function ausEintrag(e) {
    const s = {};
    for (const f of FELDER) {
      setze(s, f.pfad, f.p.widget === "karte" ? { lon: e.lon, lat: e.lat } : e.p[f.pfad.split(".").pop()]);
    }
    return { ...s, anlagen: e.anlagen || [] };
  }
  function zeigeGewaehlt() {
    const g = el.querySelector("#v-gewaehlt");
    const was = F("art").value === "anlagen" ? "die Sportanlagen von" : "die Angaben von";
    g.innerHTML = original && F("art").value !== "organisation" ? `<div class="chip">Sie ändern ${was}: <b>${esc(original.p.name || original.kat)}</b> `
      + `<span class="q">${esc(verbinde([original.p.kategorie, original.p.adresse]))}</span>`
      + ` <button type="button">andere wählen</button></div>` : "";
    const b = g.querySelector("button");
    if (b) b.addEventListener("click", () => { original = null; zeigeGewaehlt();
      el.querySelector("#v-auswahl").hidden = false; el.querySelector("#v-suche").focus(); planePruefung(); });
    el.querySelector("#v-auswahl").hidden = !(["aenderung", "anlagen"].includes(F("art").value) && !original);
  }
  // Formular neu füllen: für eine neue Sportstätte (eintrag = null) oder eine vorhandene
  function beginne(art, eintrag, vorgabe, herkunft = "") {
    original = eintrag; quelle = herkunft;
    form.reset();
    F("art").value = art;
    fuelle(vorgabe);
    zeigeTeile();
    zeigeGewaehlt();
    el.querySelector("#v-ausgabe").innerHTML = "";
    el.querySelector("#v-fehler").hidden = true;
  }
  function neu(vorgabe = {}, herkunft = "") { beginne("neu", null, vorgabe, herkunft); }
  function bearbeite(id, art = "aenderung") {
    const e = NACH_ID.get(id);
    if (!e) return;
    if (vkarte) vkarte.closePopup();
    beginne(art === "anlagen" ? "anlagen" : "aenderung", e, ausEintrag(e));
  }

  // --- Prüfungen ---
  function planePruefung() { clearTimeout(pruefen); pruefen = setTimeout(pruefe, 250); }
  function pruefe() {
    if (!form) return;
    const v = werte();
    if (v.art === "organisation") return;
    dubletten = sucheDubletten(v);
    const box = el.querySelector("#v-dubletten");
    if (!dubletten.length) {
      box.innerHTML = v.art !== "anlagen" && (v.sportstaette.name || lage)
        ? `<div class="ok">✓ Keine ähnliche Sportstätte in der Nähe gefunden.</div>` : "";
    } else {
      box.innerHTML = `<div class="warnung"><b>Mögliche Doppelung</b> – ist die Sportstätte schon eingetragen?<ul>`
        + dubletten.map(d => `<li><b>${esc(d.e.p.name || d.e.kat)}</b> <span class="q">${esc(d.e.p.kategorie || "")}`
          + `${d.e.p.adresse ? " · " + esc(d.e.p.adresse) : ""}</span><br><span class="grund">${d.gruende.map(esc).join(" · ")}</span>`
          + `<br><a href="#" data-zeige="${esc(d.e.p.id)}">auf der Karte</a> · `
          + `<a href="#" data-bearbeiten="${esc(d.e.p.id)}">stattdessen diese ändern</a></li>`).join("")
        + `</ul>${v.art === "neu" ? `<label class="bestaetigen"><input type="checkbox" id="v-keine-doppelung"`
          + `${box.dataset.bestaetigt === "1" ? " checked" : ""}> Ich habe geprüft: Es ist eine andere Sportstätte.</label>` : ""}</div>`;
      const cb = box.querySelector("#v-keine-doppelung");
      if (cb) cb.addEventListener("change", () => { box.dataset.bestaetigt = cb.checked ? "1" : ""; });
      box.querySelectorAll("[data-zeige]").forEach(a => a.addEventListener("click", ev => {
        ev.preventDefault(); const e = NACH_ID.get(a.dataset.zeige);
        if (vkarte && e) vkarte.setView([e.lat, e.lon], 18); }));
    }
    zeigeAenderungen(v);
    zeigeHinweise(v);
  }
  // Hinweise, die das Abschicken nicht verhindern: Typ einer Sportanlage passt nicht zur Kategorie
  function zeigeHinweise(v) {
    const k = kategorie(), box = el.querySelector("#v-hinweise"), liste = [];
    for (const tr of el.querySelectorAll("#v-anlagen tr.anlage")) {
      const typ = tr.querySelector('[data-f="typ"]').value.trim(), h = tr.querySelector(".typ-hinweis");
      const passt = v.art === "aenderung" || tr.classList.contains("entfernt") || typPasst(k, typ);
      h.hidden = passt; h.textContent = passt ? "" : `passt nicht zu „${k}“`;
      if (!passt) liste.push(typ);
    }
    box.innerHTML = liste.length ? `<div class="warnung"><b>Bitte prüfen</b> – diese Sportanlagen passen nicht `
      + `zur Kategorie „${esc(k)}“: ${[...new Set(liste)].map(esc).join(", ")}. Gehören sie zu einer anderen `
      + `Sportstätte, oder stimmt die Kategorie nicht? Abschicken geht trotzdem.</div>` : "";
    typListe();
  }
  function sucheDubletten(v) {
    const out = [];
    // Beim Ändern nur prüfen, wenn Name oder Lage geändert wurden
    if (v.art === "anlagen") return out;
    if (original && !aenderungen(v).some(([k]) => k === "name" || k === FELD_LAGE.pfad)) return out;
    const s = v.sportstaette, a = s.adresse || {};
    const adresse = normName(`${a.strasse || ""} ${a.hausnummer || ""}`);
    for (const e of bestand.eintraege) {
      if (original && e === original) continue;
      const g = [];
      let punkte = 0;
      const d = lage ? abstand(lage[0], lage[1], e.lat, e.lon) : null;
      const sim = aehnlich(s.name, e.p.name);
      const gleicheKat = s.kategorie && s.kategorie === e.p.kategorie;
      if (d !== null && d <= 60) { g.push(`nur ${Math.round(d)} m entfernt`); punkte += 3; }
      else if (d !== null && d <= 250 && gleicheKat) { g.push(`gleiche Kategorie, ${Math.round(d)} m entfernt`); punkte += 2; }
      const nahGenug = d === null ? (a.ort && normName(a.ort) === normName(e.p.ort)) || (a.plz && a.plz === e.p.plz) : d <= 3000;
      if (sim >= 0.8 && nahGenug) { g.push(sim >= 0.99 ? "gleicher Name" : "sehr ähnlicher Name"); punkte += 2; }
      if (adresse && a.hausnummer && adresse === normName(`${e.p.strasse || ""} ${e.p.hausnummer || ""}`)
          && (!a.plz || a.plz === e.p.plz)) { g.push("gleiche Adresse"); punkte += 2; }
      if (punkte) out.push({ e, gruende: g, punkte, d: d ?? 1e9 });
    }
    return out.sort((a, b) => b.punkte - a.punkte || a.d - b.d).slice(0, 6);
  }
  // Geänderte Felder: [[Pfad, alter Text, neuer Text]]
  function aenderungen(v) {
    if (!original) return [];
    const alt = ausEintrag(original), out = [];
    const text = x => Array.isArray(x) ? [...x].sort().join(", ") : (x == null ? "" : String(x));
    if (v.art === "anlagen") {
      const a = anlagenAenderung(v.anlagenliste);
      return a.length ? [["anlagen", "", a.join("\n")]] : [];
    }
    for (const f of FELDER) {
      if (f.p.widget === "karte") {
        const d = lage ? abstand(lage[0], lage[1], alt.lage.lat, alt.lage.lon) : 0;
        if (d > 5) out.push([f.pfad, "", `um ${Math.round(d)} m verschoben`]);
        continue;
      }
      const ta = text(hole(alt, f.pfad)), tn = text(hole(v.sportstaette, f.pfad));
      if (ta.trim() !== tn.trim()) out.push([f.pfad, ta, tn]);
    }
    return out;
  }
  function zeigeAenderungen(v) {
    const box = el.querySelector("#v-aenderungen");
    if (!original) { box.innerHTML = ""; return; }
    const a = aenderungen(v);
    box.innerHTML = `<div class="aenderungen"><b>Ihre Änderungen</b>` + (a.length
      ? `<table class="meta">` + a.map(([k, alt, n]) => `<tr><td>${esc(TITEL[k] || k)}</td><td>`
        + (alt ? `<s>${esc(alt)}</s> → ` : "") + `${esc(n || "(leer)").replace(/\n/g, "<br>")}</td></tr>`).join("") + `</table>`
      : `<div class="hinweis">noch keine</div>`) + `</div>`;
  }
  function zeigeFehlerliste(liste) {
    const box = el.querySelector("#v-fehler");
    box.hidden = !liste.length;
    box.innerHTML = liste.length ? "<b>Bitte noch ergänzen:</b><ul>" + liste.map(f => `<li>${esc(f)}</li>`).join("") + "</ul>" : "";
    if (liste.length) box.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  // Alle Verstöße gegen die Regeln des Datenmodells
  function regelVerstoesse(v) {
    const fehler = [];
    if (v.art !== "anlagen") {
      for (const f of FELDER) {
        const w = hole(v.sportstaette, f.pfad);
        if (f.p.widget === "karte") {
          if (!w) { if (f.pflicht) fehler.push(`${f.p.title}: in der Karte auf die Sportstätte klicken`); continue; }
          for (const [k, p, , t] of modellFelder(f.t.ref)) fehler.push(...regelFehler({ p, t }, w[k], `${f.p.title} (${p.title})`));
          continue;
        }
        fehler.push(...regelFehler(f, w, f.p.title));
      }
      fehler.push(...regelnZwischen("Sportstaette", v.sportstaette));
    }
    if (v.art !== "aenderung") {
      for (const a of v.anlagenliste.filter(x => !x.entfernt)) {
        const name = `Sportanlage „${a.typ || "?"}“`;
        fehler.push(...regelFehler(FELD_TYP, a.typ, `${name}: ${FELD_TYP.p.title}`));
        for (const d of ANLAGE_DETAILS) {
          const w = detailWert(d, a);
          if (d.p.widget === "zaehler") {
            for (const [k, n] of Object.entries(w || {})) {
              fehler.push(...regelFehler({ p: d.p, t: d.t.additionalProperties || {} }, n, `${name}: ${d.p.title} (${k})`));
            }
          } else fehler.push(...regelFehler(d, w, `${name}: ${d.p.title}`));
        }
        fehler.push(...regelnZwischen("Sportanlage", anlageModell(a), `${name}: `));
      }
    }
    return [...new Set(fehler)];
  }
  // Der Vorschlag nach dem Modell „Vorschlag“ (modell.py)
  function vorschlagDaten(v, geaendert, geprueft) {
    const d = { version: 1, art: v.art };
    if (original) d.sportstaette_id = original.p.id;
    if (v.art !== "anlagen") d.sportstaette = ohneLeere(v.sportstaette);
    if (v.art !== "aenderung") {
      d.anlagen = v.anlagenliste.filter(a => !a.entfernt && a.typ)
        .flatMap(a => Array.from({ length: a.id ? 1 : a.n }, () => anlageModell(a)));
      const weg = v.anlagenliste.filter(a => a.entfernt && a.id).map(a => a.id);
      if (weg.length) d.entfernte_anlagen = weg;
    }
    if (geaendert.length) d.geaendert = geaendert;
    if (ars) d.gemeinde = ars;
    if (quelle) d.quelle = quelle;
    if (geprueft.length) d.dubletten_geprueft = geprueft;
    return d;
  }

  // --- Weiter zu LimeSurvey ---
  function weiter() {
    pruefe();
    const v = werte(), fehler = [];
    if (v.art === "organisation") return weiterOrg(v);
    if (v.art !== "neu" && !original) fehler.push("Welche Sportstätte soll geändert werden? (oben auswählen)");
    fehler.push(...regelVerstoesse(v));
    if (/[\w.+-]+@[\w-]+\.[\w.]+/.test(JSON.stringify(v))) fehler.push("Bitte keine E-Mail-Adressen eintragen");
    const geaendert = aenderungen(v).map(([k]) => k);
    if (original && !geaendert.length && !v.anmerkung) {
      fehler.push(v.art === "anlagen" ? "Änderung: mindestens eine Sportanlage hinzufügen, ändern oder entfernen"
        : "Änderung: mindestens ein Feld ändern oder eine Anmerkung schreiben");
    }
    const cb = el.querySelector("#v-keine-doppelung");
    if (v.art === "neu" && dubletten.length && !(cb && cb.checked)) {
      fehler.push("Mögliche Doppelung prüfen (rechts) und bestätigen, dass es eine andere Sportstätte ist");
    }
    const daten = vorschlagDaten(v, geaendert, v.art === "neu" && cb && cb.checked ? dubletten.map(d => d.e.p.id) : []);
    sende(daten, v, fehler);
  }
  // Vorschlag als JSON an LimeSurvey (Frage data), Anmerkung in kommentar
  function sende(daten, v, fehler) {
    const params = new URLSearchParams();
    params.set(VORSCHLAG_FRAGEN.data, JSON.stringify(daten));
    if (v.anmerkung && VORSCHLAG_FRAGEN.kommentar) params.set(VORSCHLAG_FRAGEN.kommentar, v.anmerkung);
    const u = KONFIG.vorschlag_url ? KONFIG.vorschlag_url + (KONFIG.vorschlag_url.includes("?") ? "&" : "?")
      + "newtest=Y&" + params : "";
    if (u.length > URL_HOECHSTENS) {
      fehler.push("Der Vorschlag ist zu umfangreich für eine Übergabe – bitte auf mehrere Vorschläge aufteilen "
        + "(z. B. erst die Angaben, dann die Sportanlagen).");
    }
    zeigeFehlerliste(fehler);
    if (fehler.length) return;
    const ausgabe = el.querySelector("#v-ausgabe");
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
  function weiterOrg(v) {
    const fehler = orgFehler(v.organisation, v.loeschen);
    const geaendert = orgAenderungen(v.organisation);
    if (orgOriginal && orgOriginal.imVerzeichnis && !v.loeschen && !geaendert.length && !v.anmerkung) {
      fehler.push("Änderung: mindestens ein Feld ändern, löschen wählen oder eine Anmerkung schreiben");
    }
    if (/[\w.+-]+@[\w-]+\.[\w.]+/.test(JSON.stringify(v.organisation))) fehler.push("Bitte keine E-Mail-Adressen eintragen");
    const daten = { version: 1, art: "organisation" };
    if (orgOriginal && orgOriginal.imVerzeichnis) daten.organisation_id = orgOriginal.o.id;
    if (v.loeschen) daten.loeschen = true;
    else daten.organisation = v.organisation;
    if (!v.loeschen && geaendert.length && orgOriginal) daten.geaendert = geaendert;
    sende(daten, v, fehler);
  }
  let gebaut = false;
  return {
    titel: "Vorschlag",
    zeigen() {
      el.hidden = false;
      if (!gebaut) { baue(); gebaut = true; neu(); }
      starteKarte();
      if (marke) marke.addTo(vkarte);
      pruefe();
    },
    verbergen() { el.hidden = true; },
    hat: id => NACH_ID.has(id),
    neu(vorgabe, herkunft) { zeige("vorschlag").then(() => { neu(vorgabe, herkunft); pruefe(); el.scrollTop = 0; }); },
    bearbeite(id, art) { zeige("vorschlag").then(() => { bearbeite(id, art); pruefe(); el.scrollTop = 0; }); },
    // Organisation ändern oder löschen (Name wie bei den Sportstätten); ohne Namen: neue
    organisation(name) {
      zeige("vorschlag").then(() => {
        F("art").value = "organisation"; waehleOrg(name || null);
        zeigeTeile(); zeigeGewaehlt(); el.querySelector("#v-ausgabe").innerHTML = "";
        el.querySelector("#v-fehler").hidden = true; el.scrollTop = 0;
      });
    },
  };
}
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
    v.neu({ name: s.name, kategorie: GRUPPE_KATEGORIE[s.typgruppe] || "", adresse: zerlegeAdresse(s.adresse),
      betreiber: s.betreiber, eigentuemer: s.eigentuemer, website: s.website, lage: { lat: s.lat, lon: s.lon },
      anmerkung: `Aus ALKIS übernommen (${s.typ || s.typgruppe || "Sportstätte"}).` },
      "ALKIS " + (s.alkis_oid || s.sportstaette_id));
  }
});
// Zeile „Angaben ändern · Sportanlagen ändern“ für Popups (Karte und ALKIS-Abgleich), nur
// für Sportstätten, die im Datenbestand stehen
function aendernLink(id) {
  if (!ANSICHTEN.vorschlag || leer(id) || !ANSICHTEN.vorschlag.hat(id)) return "";
  return `<tr><td>Vorschlag</td><td><a href="#" data-bearbeiten="${esc(id)}">Angaben ändern</a> · `
    + `<a href="#" data-bearbeiten="${esc(id)}" data-teil="anlagen">Sportanlagen ändern</a></td></tr>`;
}
