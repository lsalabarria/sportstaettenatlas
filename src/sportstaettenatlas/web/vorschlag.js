// Reiter „Vorschlag“: Sportstätte mit ihren Sportanlagen neu eintragen, die Angaben einer
// Sportstätte ändern oder ihre Sportanlagen ändern (hinzufügen, ändern, entfernen).
// Das Formular prüft auf Doppelungen und übergibt die Werte als URL-Parameter an die
// LimeSurvey-Umfrage (konfig.js: vorschlag_url). Dort wird der Vorschlag abgeschickt.
// Parameternamen = Fragecodes in LimeSurvey. Ist in konfig.js vorschlag_felder gesetzt,
// werden nur die dort genannten Felder übertragen ({ name: "Q00", lage: "G01Q04" }),
// sonst alle mit den Vorgabe-Codes unten.
const VORSCHLAG_FELDER = KONFIG.vorschlag_felder && Object.keys(KONFIG.vorschlag_felder).length
  ? KONFIG.vorschlag_felder : {
  art: "art", id: "id", quelle: "quelle", name: "name", kategorie: "kategorie",
  betriebsstatus: "status", strasse: "strasse", hausnummer: "hausnr", adresszusatz: "zusatz",
  plz: "plz", ort: "ort", ars: "ars", gemeinde: "gemeinde", lat: "lat", lon: "lon",
  oeffentlicher_zugang: "oeffentlich", schulsport: "schulsport", zuschauerplaetze: "zuschauer",
  sportarten: "sportarten", anlagen: "anlagen", anlagen_aenderung: "anlagen_aenderung",
  eigentuemer: "eigentuemer",
  betreiber: "betreiber", website: "website", anmerkung: "anmerkung", geaendert: "geaendert",
  dubletten: "dubletten",
};
const FELD_TEXT = {
  name: "Name", kategorie: "Kategorie", betriebsstatus: "Betriebsstatus", strasse: "Straße",
  hausnummer: "Hausnummer", adresszusatz: "Adresszusatz", plz: "PLZ", ort: "Ort",
  lage: "Lage", oeffentlicher_zugang: "Öffentlicher Zugang", schulsport: "Schulsport",
  zuschauerplaetze: "Zuschauerplätze", sportarten: "Sportarten", anlagen: "Sportanlagen",
  eigentuemer: "Eigentümer", betreiber: "Betreiber", website: "Website",
};
const STATUS_WERTE = ["in Betrieb", "vorübergehend geschlossen", "außer Betrieb", "in Planung",
  "im Bau"];
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

function ansichtVorschlag(bestand) {
  const el = document.getElementById("seite-vorschlag");
  const NACH_ID = new Map(bestand.eintraege.map(e => [e.p.id, e]));
  let form, vkarte = null, marke = null, nachbarn = null, original = null, quelle = "";
  let lage = null, ars = "", pruefen = 0, dubletten = [];
  const F = n => form.elements.namedItem(n);

  // Auswahllisten aus dem Datenbestand und den Gebieten
  function haeufig(werte) {
    const z = new Map();
    for (const w of werte) if (!leer(w)) {
      const k = schluesselName(w), x = z.get(k) || { n: 0, namen: new Map() };
      x.n++; x.namen.set(w.trim(), (x.namen.get(w.trim()) || 0) + 1); z.set(k, x);
    }
    return [...z.values()].map(x => [[...x.namen].sort((a, b) => b[1] - a[1])[0][0], x.n]);
  }
  const KATEGORIEN = haeufig(bestand.eintraege.map(e => e.p.kategorie)).sort((a, b) => b[1] - a[1]).map(x => x[0]);
  const SPORTARTEN = haeufig(bestand.eintraege.flatMap(e => e.p.sportarten || [])).map(x => x[0])
    .sort((a, b) => a.localeCompare(b, "de"));
  // Typen der Sportanlagen: nach Gruppe, darin nach Häufigkeit
  const ANLAGEN = (() => {
    const z = {};
    for (const e of bestand.eintraege) for (const t of e.p.anlagen || []) z[t] = (z[t] || 0) + 1;
    const reihe = ANLAGEN_GRUPPEN.map(g => g[0]);
    return Object.keys(z).sort((a, b) => reihe.indexOf(anlagenGruppe(a)) - reihe.indexOf(anlagenGruppe(b))
      || z[b] - z[a]);
  })();
  const STATUS = [...new Set([...STATUS_WERTE, ...bestand.eintraege.map(e => e.p.betriebsstatus).filter(v => !leer(v))])];
  function organisationen() {
    const bisher = haeufig(bestand.eintraege.flatMap(e => [e.p.betreiber, e.p.eigentuemer]))
      .sort((a, b) => b[1] - a[1]).map(x => x[0]);
    const kommunen = GEBIETE.map(kommunenName);
    return [...new Map([...bisher, ...kommunen].map(n => [schluesselName(n), n])).values()];
  }
  const ORTE = () => [...new Set([...GEBIETE.filter(g => g.e === "gemeinde").map(g => g.n),
    ...bestand.eintraege.map(e => e.p.ort).filter(v => !leer(v))])].sort((a, b) => a.localeCompare(b, "de"));
  const optionen = liste => liste.map(v => `<option value="${esc(v)}"></option>`).join("");
  const auswahl = (name, werte, leerText = "– bitte wählen –") => `<select name="${name}">`
    + `<option value="">${leerText}</option>` + werte.map(v => `<option>${esc(v)}</option>`).join("") + `</select>`;
  const jaNein = name => `<span class="radios">` + [["ja", "Ja"], ["nein", "Nein"], ["", "Nicht bekannt"]]
    .map(([w, t]) => `<label><input type="radio" name="${name}" value="${w}"${w ? "" : " checked"}> ${t}</label>`).join("") + `</span>`;
  const feld = (label, inhalt, extra = "") => `<label class="feld${extra}"><span>${label}</span>${inhalt}</label>`;

  function baue() {
    el.innerHTML = `<div class="inhalt vorschlag"><h2>Vorschlag machen</h2>
      <p class="unter">Neue Sportstätte mit ihren Sportanlagen eintragen, die Angaben einer Sportstätte
      ändern oder ihre Sportanlagen hinzufügen, ändern und entfernen. Im nächsten Schritt
      werden die Angaben an die Umfrage übergeben und dort abgeschickt; nach einer Prüfung erscheinen
      sie auf der Karte. Bitte keine personenbezogenen Daten (Namen, private Telefonnummern) eintragen.</p>
      <div class="raster"><form id="v-form" novalidate autocomplete="off">
      <fieldset><legend>Was möchten Sie tun?</legend>
        <span class="radios gross"><label><input type="radio" name="art" value="neu" checked> Neue Sportstätte mit ihren Sportanlagen eintragen</label>
        <label><input type="radio" name="art" value="aenderung"> Angaben einer Sportstätte ändern (Name, Adresse, Betreiber …)</label>
        <label><input type="radio" name="art" value="anlagen"> Sportanlagen einer Sportstätte ändern (hinzufügen, ändern, entfernen)</label></span>
        <div id="v-auswahl" hidden><input type="search" id="v-suche" placeholder="Name, Ort oder ID der Sportstätte suchen"
          aria-label="Sportstätte suchen"><ul id="v-treffer" class="treffer"></ul></div>
        <div id="v-gewaehlt"></div>
      </fieldset>
      <div id="v-teil-staette">
      <fieldset><legend>Sportstätte</legend>
        ${feld("Name *", `<input name="name" required maxlength="200">`)}
        <div class="zwei">${feld("Sportstättenkategorie *", auswahl("kategorie", KATEGORIEN))}
        ${feld("Betriebsstatus", auswahl("betriebsstatus", STATUS, "nicht bekannt"))}</div>
      </fieldset>
      <fieldset><legend>Adresse und Lage</legend>
        <div class="zwei breit-links">${feld("Straße", `<input name="strasse">`)}${feld("Hausnummer", `<input name="hausnummer" maxlength="12">`)}</div>
        ${feld("Adresszusatz", `<input name="adresszusatz" placeholder="z. B. Eingang Schulhof">`)}
        <div class="zwei schmal-links">${feld("PLZ", `<input name="plz" inputmode="numeric" maxlength="5" pattern="[0-9]{5}">`)}
        ${feld("Ort", `<input name="ort" list="v-orte">`)}</div>
        <div class="lage"><b>Lage *</b> <span id="v-lage">Bitte in der Karte rechts auf die Sportstätte klicken.</span>
          <button type="button" class="knopf2" id="v-geocode">Lage aus der Adresse suchen</button>
          <div id="v-gemeinde" class="hinweis"></div></div>
      </fieldset>
      <fieldset><legend>Nutzung</legend>
        <div class="zeile-feld"><span>Öffentlicher Zugang</span>${jaNein("oeffentlicher_zugang")}</div>
        <div class="zeile-feld"><span>Schulsport</span>${jaNein("schulsport")}</div>
        ${feld("Zuschauerplätze gesamt", `<input name="zuschauerplaetze" type="number" min="0" step="1">`, " klein")}
      </fieldset>
      <fieldset><legend>Sportarten</legend>
        <div id="v-sportarten" class="chips"></div>
        <div class="hinzu"><input id="v-sportart" list="v-sportarten-liste" placeholder="Sportart eingeben oder auswählen"
          aria-label="Sportart"><button type="button" class="knopf2" id="v-sportart-dazu">Hinzufügen</button></div>
      </fieldset>
      </div>
      <fieldset id="v-teil-anlagen"><legend>Sportanlagen</legend>
        <p class="hinweis">Die einzelnen Anlagen der Sportstätte, z. B. Großspielfeld, Rundlaufbahn, Hallenteil.
        Jede Sportanlage gehört zu genau dieser Sportstätte. Name nur, wenn die Anlage einen eigenen hat
        (z. B. „Halle 1“, „Kunstrasen B“).</p>
        <table class="anlagen"><thead><tr><th>Typ *</th><th>Name</th><th>Anzahl</th><th>weitere Angaben</th></tr></thead><tbody id="v-anlagen"></tbody></table>
        <button type="button" class="knopf2" id="v-anlage-dazu">+ Sportanlage hinzufügen</button>
      </fieldset>
      <div id="v-teil-staette2">
      <fieldset><legend>Eigentümer und Betreiber</legend>
        <p class="hinweis">Auswahl aus den bisherigen Eigentümern und Betreibern sowie allen Kommunen; neue Namen können eingetippt werden.</p>
        ${feld("Eigentümer", `<input name="eigentuemer" list="v-orgs"><span class="art" id="v-art-eigentuemer"></span>`)}
        ${feld("Betreiber", `<input name="betreiber" list="v-orgs"><span class="art" id="v-art-betreiber"></span>`)}
        ${feld("Webseite", `<input name="website" type="url" placeholder="https://">`)}
      </fieldset>
      </div>
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
        <div id="v-aenderungen"></div><div id="v-dubletten"></div></aside></div>
      <datalist id="v-orte">${optionen(ORTE())}</datalist>
      <datalist id="v-orgs">${optionen(organisationen())}</datalist>
      <datalist id="v-sportarten-liste">${optionen(SPORTARTEN)}</datalist>
      <datalist id="v-anlagen-liste">${ANLAGEN.map(t => `<option value="${esc(t)}">`
        + `${esc(gruppenText(anlagenGruppe(t)))}</option>`).join("")}</datalist></div>`;
    form = el.querySelector("#v-form");
    form.addEventListener("input", () => { zeigeArten(); planePruefung(); });
    form.addEventListener("change", ev => {
      if (ev.target.name === "art") {
        const art = F("art").value;
        if (art === "neu") neu();
        else if (original && original.art !== art) { original.art = art; fuelle(ausEintrag(original)); }
        zeigeTeile(); zeigeGewaehlt();
      }
      planePruefung();
    });
    form.addEventListener("submit", ev => { ev.preventDefault(); weiter(); });
    el.querySelector("#v-leeren").addEventListener("click", () => neu());
    el.querySelector("#v-geocode").addEventListener("click", lageAusAdresse);
    const sp = el.querySelector("#v-sportart");
    const dazu = () => { const v = sp.value.trim(); if (v) { sportarten.add(v); sp.value = ""; zeigeSportarten(); planePruefung(); } };
    el.querySelector("#v-sportart-dazu").addEventListener("click", dazu);
    sp.addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); dazu(); } });
    el.querySelector("#v-anlage-dazu").addEventListener("click", () => {
      anlageZeile({ typ: "", name: "", id: "" }, 1); planePruefung();
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
        + `<small>${esc([e.p.kategorie, e.p.adresse].filter(v => !leer(v)).join(" · "))}</small></li>`).join("")
        || `<li class="gruppe">Keine Sportstätte gefunden</li>`;
    });
    treffer.addEventListener("click", ev => {
      const li = ev.target.closest("li[data-id]");
      if (li) bearbeite(li.dataset.id, F("art").value);
    });
  }

  const sportarten = new Set();
  function zeigeSportarten() {
    const c = el.querySelector("#v-sportarten");
    c.innerHTML = [...sportarten].map(s => `<span class="chip-s">${esc(s)}<button type="button" `
      + `data-weg="${esc(s)}" aria-label="${esc(s)} entfernen">×</button></span>`).join("")
      || `<span class="hinweis">noch keine</span>`;
    c.querySelectorAll("[data-weg]").forEach(b => b.addEventListener("click", () => {
      sportarten.delete(b.dataset.weg); zeigeSportarten(); planePruefung(); }));
  }
  // Eine Zeile je Sportanlage, darunter aufklappbar ihre weiteren Angaben. Vorhandene Anlagen
  // (mit Kurz-ID) lassen sich ändern oder zum Entfernen markieren; neue lassen sich mit Anzahl
  // eintragen (z. B. 3× Tennisplatz).
  const liste = x => String(x || "").split(/[,;]/).map(t => t.trim()).filter(Boolean);
  const angaben = a => ({ typ: a.typ || "", name: a.name || "", sportarten: (a.sportarten || []).join(", "),
    baujahr: a.baujahr ? String(a.baujahr) : "", baukosten_eur: a.baukosten_eur ? String(a.baukosten_eur) : "",
    ausstattung: (a.ausstattung || []).join(", ") });
  function anlageZeile(a, anzahl = 1) {
    const tr = document.createElement("tr"), mehr = document.createElement("tr");
    const vorhanden = !!a.id, alt = angaben(a);
    tr.className = "anlage"; mehr.className = "anlage-mehr"; mehr.hidden = true;
    tr.dataset.id = a.id || ""; tr.dataset.alt = JSON.stringify(alt);
    tr.innerHTML = `<td><input data-f="typ" list="v-anlagen-liste" value="${esc(alt.typ)}" aria-label="Typ"`
      + ` placeholder="z. B. Großspielfeld"></td>`
      + `<td><input data-f="name" value="${esc(alt.name)}" aria-label="Name" placeholder="optional"></td>`
      + `<td>${vorhanden ? `<span class="q" title="Kennung der Anlage">${esc(a.id)}</span>`
        : `<input data-f="anzahl" type="number" min="1" step="1" value="${anzahl}" aria-label="Anzahl">`}</td>`
      + `<td class="aktionen"><button type="button" class="mehr" aria-expanded="false" title="weitere Angaben">Angaben ▸</button>`
      + `<button type="button" class="weg" aria-label="${vorhanden ? "Anlage entfernen" : "Zeile löschen"}"`
      + ` title="${vorhanden ? "Diese Anlage gibt es nicht mehr" : "Zeile löschen"}">×</button></td>`;
    mehr.innerHTML = `<td colspan="4"><div class="anlage-felder">`
      + `<label>Sportarten<input data-f="sportarten" list="v-sportarten-liste" value="${esc(alt.sportarten)}" placeholder="z. B. Fußball, Leichtathletik"></label>`
      + `<label>Baujahr<input data-f="baujahr" type="number" min="1800" max="2100" step="1" value="${esc(alt.baujahr)}"></label>`
      + `<label>Baukosten (€)<input data-f="baukosten_eur" type="number" min="0" step="1000" value="${esc(alt.baukosten_eur)}"></label>`
      + `<label class="breit">Ausstattung<input data-f="ausstattung" value="${esc(alt.ausstattung)}" placeholder="z. B. Flutlicht, Beregnung, Umkleiden"></label>`
      + `</div></td>`;
    const knopf = tr.querySelector(".mehr");
    const klappe = auf => { mehr.hidden = !auf; knopf.textContent = auf ? "Angaben ▾" : "Angaben ▸";
      knopf.setAttribute("aria-expanded", auf); };
    knopf.addEventListener("click", () => klappe(mehr.hidden));
    if (alt.sportarten || alt.baujahr || alt.baukosten_eur || alt.ausstattung) knopf.classList.add("hat");
    tr.querySelector(".weg").addEventListener("click", () => {
      if (!vorhanden) { tr.remove(); mehr.remove(); }
      else {
        const weg = !tr.classList.contains("entfernt");
        tr.classList.toggle("entfernt", weg);
        [tr, mehr].forEach(z => z.querySelectorAll("input").forEach(i => { i.disabled = weg; }));
        if (weg) klappe(false);
        const b = tr.querySelector(".weg");
        b.textContent = weg ? "↺" : "×"; b.title = weg ? "doch behalten" : "Diese Anlage gibt es nicht mehr";
      }
      planePruefung();
    });
    const ziel = el.querySelector("#v-anlagen");
    ziel.appendChild(tr); ziel.appendChild(mehr);
  }
  // [{ id, typ, name, sportarten, baujahr, baukosten_eur, ausstattung, n, entfernt, alt }]
  function anlagenListe() {
    const out = [];
    for (const tr of el.querySelectorAll("#v-anlagen tr.anlage")) {
      const w = {};
      for (const z of [tr, tr.nextElementSibling]) z.querySelectorAll("[data-f]").forEach(i => { w[i.dataset.f] = i.value.trim(); });
      const a = { id: tr.dataset.id, typ: w.typ, name: w.name, sportarten: w.sportarten,
        baujahr: w.baujahr, baukosten_eur: w.baukosten_eur, ausstattung: w.ausstattung,
        n: w.anzahl ? Math.max(1, parseInt(w.anzahl, 10) || 1) : 1,
        entfernt: tr.classList.contains("entfernt"), alt: JSON.parse(tr.dataset.alt) };
      if (a.typ || a.id) out.push(a);
    }
    return out;
  }
  const DETAIL_TEXT = { sportarten: "Sportarten", baujahr: "Baujahr", baukosten_eur: "Baukosten €",
    ausstattung: "Ausstattung" };
  const anlageKurz = a => (a.n > 1 ? `${a.n}× ` : "") + a.typ + (a.name ? ` (${a.name})` : "");
  const anlageDetailText = a => Object.entries(DETAIL_TEXT).filter(([k]) => a[k])
    .map(([k, l]) => `${l}: ${a[k]}`).join("; ");
  const anlageText = a => anlageKurz(a) + (anlageDetailText(a) ? ` – ${anlageDetailText(a)}` : "");
  // Ergebnis: alle Anlagen nach der Änderung, vorhandene mit Kennung, neue mit „neu:“ (je Zeile eine)
  function anlagenText(liste) {
    return liste.filter(a => !a.entfernt)
      .map(a => (a.id ? `[${a.id}] ` : "neu: ") + anlageText(a)).join("\n");
  }
  // Was sich an den Anlagen ändert (für die Prüfung des Vorschlags)
  function anlagenAenderung(liste) {
    const out = [];
    for (const a of liste) {
      if (!a.id) { out.push(`neu: ${anlageText(a)}`); continue; }
      const alt = { ...a.alt, n: 1 };
      if (a.entfernt) { out.push(`entfernen [${a.id}]: ${anlageKurz(alt)}`); continue; }
      const felder = ["typ", "name", ...Object.keys(DETAIL_TEXT)].filter(k => (a[k] || "") !== (alt[k] || ""));
      if (felder.length) {
        out.push(`ändern [${a.id}] ${anlageKurz(alt)}: ` + felder.map(k =>
          `${k === "typ" ? "Typ" : k === "name" ? "Name" : DETAIL_TEXT[k]} ${alt[k] || "(leer)"} → ${a[k] || "(leer)"}`).join("; "));
      }
    }
    return out;
  }
  // Teile des Formulars je nach Art des Vorschlags
  function zeigeTeile() {
    const art = F("art").value;
    el.querySelector("#v-teil-staette").hidden = art === "anlagen";
    el.querySelector("#v-teil-staette2").hidden = art === "anlagen";
    el.querySelector("#v-teil-anlagen").hidden = art === "aenderung";
  }
  function zeigeArten() {
    for (const r of ["eigentuemer", "betreiber"]) {
      const a = betreiberArt(F(r).value);
      el.querySelector("#v-art-" + r).textContent = a || "";
      el.querySelector("#v-art-" + r).hidden = !a;
    }
  }
  // dieselbe Schätzung wie in bestand.py (betreiber_art), vereinfacht
  function betreiberArt(n) {
    n = (n || "").trim();
    if (!n) return "";
    if (/e\.\s?v\b|\bev\b|verein|sport(gemeinde|gemeinschaft|freunde)|\b(tus|tsv|sv|fc|sc|sg|vfl|vfb|vfr|tv|tc|tsg|jsg|spvgg|fsv|ssv|djk|dlrg)\b|club|klub|schützen|gilde/i.test(n)) return "Verein";
    if (/gemeinde|\bstadt\b|städtisch|landkreis|kreisverwaltung|\bkreis\b|kommun|stadtwerk|zweckverband/i.test(n)) return "Kommune";
    return "sonstige";
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
    if (g && !F("ort").value.trim()) F("ort").value = g.n;
  }
  async function lageAusAdresse() {
    const q = [F("strasse").value + " " + F("hausnummer").value, F("plz").value + " " + F("ort").value]
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

  // --- Werte lesen und setzen ---
  function werte() {
    const t = n => (F(n).value || "").trim();
    return {
      art: F("art").value, id: original ? original.p.id : "", quelle, name: t("name"), kategorie: t("kategorie"),
      betriebsstatus: t("betriebsstatus"), strasse: t("strasse"), hausnummer: t("hausnummer"),
      adresszusatz: t("adresszusatz"), plz: t("plz"), ort: t("ort"), ars,
      gemeinde: ars && NACH_S[ars] ? NACH_S[ars].n : "",
      lat: lage ? lage[0].toFixed(6) : "", lon: lage ? lage[1].toFixed(6) : "",
      oeffentlicher_zugang: F("oeffentlicher_zugang").value, schulsport: F("schulsport").value,
      zuschauerplaetze: t("zuschauerplaetze"), sportarten: [...sportarten], anlagenliste: anlagenListe(),
      eigentuemer: t("eigentuemer"), betreiber: t("betreiber"), website: t("website"),
      anmerkung: t("anmerkung"),
    };
  }
  function fuelle(v) {
    for (const n of ["name", "betriebsstatus", "strasse", "hausnummer", "adresszusatz", "plz", "ort",
      "zuschauerplaetze", "eigentuemer", "betreiber", "website", "anmerkung"]) F(n).value = v[n] ?? "";
    const k = F("kategorie");
    if (v.kategorie && ![...k.options].some(o => o.value === v.kategorie)) k.add(new Option(v.kategorie));
    k.value = v.kategorie || "";
    if (v.betriebsstatus && ![...F("betriebsstatus").options].some(o => o.value === v.betriebsstatus)) {
      F("betriebsstatus").add(new Option(v.betriebsstatus)); F("betriebsstatus").value = v.betriebsstatus;
    }
    for (const r of ["oeffentlicher_zugang", "schulsport"]) {
      const w = v[r] === "ja" || v[r] === "nein" ? v[r] : "";
      form.querySelectorAll(`input[name=${r}]`).forEach(i => { i.checked = i.value === w; });
    }
    sportarten.clear(); (v.sportarten || []).forEach(s => sportarten.add(s)); zeigeSportarten();
    el.querySelector("#v-anlagen").innerHTML = "";
    for (const a of v.anlagen || []) anlageZeile(typeof a === "string" ? { typ: a, name: "", id: "" } : a);
    setzeLage(v.lat, v.lon, true);
    zeigeArten();
  }
  function ausEintrag(e) {
    const p = e.p;
    return { name: p.name, kategorie: p.kategorie, betriebsstatus: p.betriebsstatus, strasse: p.strasse,
      hausnummer: p.hausnummer, plz: p.plz, ort: p.ort, zuschauerplaetze: p.zuschauerplaetze,
      eigentuemer: p.eigentuemer, betreiber: p.betreiber, website: p.website,
      oeffentlicher_zugang: p.oeffentlicher_zugang, schulsport: p.schulsport,
      sportarten: p.sportarten || [], anlagen: e.anlagen || [], lat: e.lat, lon: e.lon };
  }
  function zeigeGewaehlt() {
    const g = el.querySelector("#v-gewaehlt");
    const was = F("art").value === "anlagen" ? "die Sportanlagen von" : "die Angaben von";
    g.innerHTML = original ? `<div class="chip">Sie ändern ${was}: <b>${esc(original.p.name || original.kat)}</b> `
      + `<span class="q">${esc([original.p.kategorie, original.p.adresse].filter(v => !leer(v)).join(" · "))}</span>`
      + ` <button type="button">andere wählen</button></div>` : "";
    const b = g.querySelector("button");
    if (b) b.addEventListener("click", () => { original = null; zeigeGewaehlt();
      el.querySelector("#v-auswahl").hidden = false; el.querySelector("#v-suche").focus(); planePruefung(); });
    el.querySelector("#v-auswahl").hidden = !(F("art").value !== "neu" && !original);
  }
  function neu(vorgabe = {}, herkunft = "") {
    original = null; quelle = herkunft;
    form.reset();
    F("art").value = "neu";
    fuelle(vorgabe);
    zeigeTeile();
    zeigeGewaehlt();
    el.querySelector("#v-ausgabe").innerHTML = "";
    el.querySelector("#v-fehler").hidden = true;
  }
  function bearbeite(id, art = "aenderung") {
    const e = NACH_ID.get(id);
    if (!e) return;
    original = e; quelle = "";
    if (vkarte) vkarte.closePopup();
    form.reset();
    F("art").value = art === "anlagen" ? "anlagen" : "aenderung";
    fuelle(ausEintrag(e));
    zeigeTeile();
    zeigeGewaehlt();
    el.querySelector("#v-ausgabe").innerHTML = "";
    el.querySelector("#v-fehler").hidden = true;
  }

  // --- Prüfungen ---
  function planePruefung() { clearTimeout(pruefen); pruefen = setTimeout(pruefe, 250); }
  function pruefe() {
    if (!form) return;
    const v = werte();
    dubletten = sucheDubletten(v);
    const box = el.querySelector("#v-dubletten");
    if (!dubletten.length) {
      box.innerHTML = v.art !== "anlagen" && (v.name || lage)
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
  }
  function sucheDubletten(v) {
    const out = [];
    // Beim Ändern nur prüfen, wenn Name oder Lage geändert wurden
    if (v.art === "anlagen") return out;
    if (original && !aenderungen(v).some(([k]) => k === "name" || k === "lage")) return out;
    const adresse = normName(`${v.strasse} ${v.hausnummer}`);
    for (const e of bestand.eintraege) {
      if (original && e === original) continue;
      const g = [];
      let punkte = 0;
      const d = lage ? abstand(lage[0], lage[1], e.lat, e.lon) : null;
      const sim = aehnlich(v.name, e.p.name);
      const gleicheKat = v.kategorie && v.kategorie === e.p.kategorie;
      if (d !== null && d <= 60) { g.push(`nur ${Math.round(d)} m entfernt`); punkte += 3; }
      else if (d !== null && d <= 250 && gleicheKat) { g.push(`gleiche Kategorie, ${Math.round(d)} m entfernt`); punkte += 2; }
      const nahGenug = d === null ? (v.ort && normName(v.ort) === normName(e.p.ort)) || (v.plz && v.plz === e.p.plz) : d <= 3000;
      if (sim >= 0.8 && nahGenug) { g.push(sim >= 0.99 ? "gleicher Name" : "sehr ähnlicher Name"); punkte += 2; }
      if (adresse && v.hausnummer && adresse === normName(`${e.p.strasse || ""} ${e.p.hausnummer || ""}`)
          && (!v.plz || v.plz === e.p.plz)) { g.push("gleiche Adresse"); punkte += 2; }
      if (punkte) out.push({ e, gruende: g, punkte, d: d ?? 1e9 });
    }
    return out.sort((a, b) => b.punkte - a.punkte || a.d - b.d).slice(0, 6);
  }
  function aenderungen(v) {
    if (!original) return [];
    const alt = ausEintrag(original), out = [];
    const text = x => Array.isArray(x) ? x.join(", ") : (x == null ? "" : String(x));
    if (v.art === "anlagen") {
      const a = anlagenAenderung(v.anlagenliste);
      return a.length ? [["anlagen", "", a.join("\n")]] : [];
    }
    for (const k of Object.keys(FELD_TEXT)) {
      if (k === "anlagen") continue;  // eigene Art des Vorschlags
      if (k === "lage") {
        const d = lage ? abstand(lage[0], lage[1], alt.lat, alt.lon) : 0;
        if (d > 5) out.push([k, "", `um ${Math.round(d)} m verschoben`]);
        continue;
      }
      const a = alt[k], n = v[k];
      const ta = Array.isArray(a) ? [...a].sort().join(", ") : text(a), tn = Array.isArray(n) ? [...n].sort().join(", ") : text(n);
      if (ta.trim() !== tn.trim()) out.push([k, ta, tn]);
    }
    return out;
  }
  function zeigeAenderungen(v) {
    const box = el.querySelector("#v-aenderungen");
    if (!original) { box.innerHTML = ""; return; }
    const a = aenderungen(v);
    box.innerHTML = `<div class="aenderungen"><b>Ihre Änderungen</b>` + (a.length
      ? `<table class="meta">` + a.map(([k, alt, n]) => `<tr><td>${FELD_TEXT[k]}</td><td>`
        + (alt ? `<s>${esc(alt)}</s> → ` : "") + `${esc(n || "(leer)").replace(/\n/g, "<br>")}</td></tr>`).join("") + `</table>`
      : `<div class="hinweis">noch keine</div>`) + `</div>`;
  }
  function zeigeFehlerliste(liste) {
    const box = el.querySelector("#v-fehler");
    box.hidden = !liste.length;
    box.innerHTML = liste.length ? "<b>Bitte noch ergänzen:</b><ul>" + liste.map(f => `<li>${esc(f)}</li>`).join("") + "</ul>" : "";
    if (liste.length) box.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // --- Weiter zu LimeSurvey ---
  function weiter() {
    pruefe();
    const v = werte(), fehler = [];
    if (v.art !== "neu" && !original) fehler.push("Welche Sportstätte soll geändert werden? (oben auswählen)");
    if (v.anlagenliste.some(a => !a.entfernt && !a.typ)) fehler.push("Typ jeder Sportanlage");
    if (v.anlagenliste.some(a => a.baujahr && !/^(18|19|20)\d\d$/.test(a.baujahr))) fehler.push("Baujahr als Jahreszahl, z. B. 1998");
    if (!v.name) fehler.push("Name der Sportstätte");
    if (!v.kategorie) fehler.push("Sportstättenkategorie");
    if (!lage) fehler.push("Lage: in der Karte auf die Sportstätte klicken");
    if (v.plz && !/^\d{5}$/.test(v.plz)) fehler.push("PLZ mit fünf Ziffern");
    if (v.website && !/^https?:\/\/\S+\.\S+/.test(v.website)) fehler.push("Webseite als vollständige Adresse (https://…)");
    if (/[\w.+-]+@[\w-]+\.[\w.]+/.test(Object.values(v).flat().join(" "))) fehler.push("Bitte keine E-Mail-Adressen eintragen");
    const geaendert = aenderungen(v).map(([k]) => k);
    if (original && !geaendert.length && !v.anmerkung) {
      fehler.push(v.art === "anlagen" ? "Änderung: mindestens eine Sportanlage hinzufügen, ändern oder entfernen"
        : "Änderung: mindestens ein Feld ändern oder eine Anmerkung schreiben");
    }
    const cb = el.querySelector("#v-keine-doppelung");
    if (v.art === "neu" && dubletten.length && !(cb && cb.checked)) {
      fehler.push("Mögliche Doppelung prüfen (rechts) und bestätigen, dass es eine andere Sportstätte ist");
    }
    zeigeFehlerliste(fehler);
    if (fehler.length) return;
    const daten = { ...v, geaendert: geaendert.map(k => FELD_TEXT[k] || k).join(", "),
      lage: v.lat ? `${v.lat}, ${v.lon}` : "",
      anlagen: anlagenText(v.anlagenliste),
      anlagen_aenderung: v.art === "neu" ? "" : anlagenAenderung(v.anlagenliste).join("\n"),
      adresse: [`${v.strasse} ${v.hausnummer}`.trim(), `${v.plz} ${v.ort}`.trim()].filter(Boolean).join(", "),
      dubletten: dubletten.length ? dubletten.map(d => d.e.p.id).join(", ") + (cb && cb.checked ? " (geprüft: andere Sportstätte)" : "") : "" };
    const params = new URLSearchParams();
    for (const [k, code] of Object.entries(VORSCHLAG_FELDER)) {
      if (!code) continue;
      const w = Array.isArray(daten[k]) ? daten[k].join("; ") : daten[k];
      if (!leer(w)) params.set(code, w);
    }
    const ausgabe = el.querySelector("#v-ausgabe");
    if (KONFIG.vorschlag_url) {
      const u = KONFIG.vorschlag_url + (KONFIG.vorschlag_url.includes("?") ? "&" : "?") + "newtest=Y&" + params;
      ausgabe.innerHTML = `<div class="ok">Die Umfrage wurde in einem neuen Tab geöffnet. Falls nicht: `
        + `<a href="${esc(u)}" target="_blank" rel="noopener">hier weiter zu LimeSurvey</a>.</div>`;
      window.open(u, "_blank", "noopener");
    } else {
      ausgabe.innerHTML = `<div class="warnung"><b>Der Link zur LimeSurvey-Umfrage ist noch nicht eingetragen</b> `
        + `(in <code>konfig.js</code>: <code>vorschlag_url</code>). Übertragen würden diese Werte:`
        + `<table class="meta">` + [...params].map(([k, w]) => `<tr><td><code>${esc(k)}</code></td><td>${esc(w)}</td></tr>`).join("")
        + `</table><details><summary>als URL-Parameter</summary><code class="umbruch">?${esc(params.toString())}</code></details></div>`;
      ausgabe.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  let gebaut = false;
  return {
    titel: "Vorschlag",
    starte() {},
    zeigen() {
      el.hidden = false;
      if (!gebaut) { baue(); gebaut = true; neu(); }
      starteKarte();
      if (marke) marke.addTo(vkarte);
      pruefe();
    },
    verbergen() { el.hidden = true; },
    gebietGeaendert() {},
    hat: id => NACH_ID.has(id),
    neu(vorgabe, herkunft) { zeige("vorschlag").then(() => { neu(vorgabe, herkunft); pruefe(); el.scrollTop = 0; }); },
    bearbeite(id, art) { zeige("vorschlag").then(() => { bearbeite(id, art); pruefe(); el.scrollTop = 0; }); },
  };
}
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
    v.neu({ lat, lon });
  } else {
    const s = ALKIS_STAETTEN[a.dataset.vorschlagAlkis];
    if (!s) return;
    v.neu({ name: s.name, kategorie: GRUPPE_KATEGORIE[s.typgruppe] || "", ...zerlegeAdresse(s.adresse),
      betreiber: s.betreiber, eigentuemer: s.eigentuemer, website: s.website, lat: s.lat, lon: s.lon,
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
