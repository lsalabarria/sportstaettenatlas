// Formular: Felder aus dem Modell und Auswahllisten (im Zustand z), Aufbau des Formulars.
import { z } from "./zustand.js";
import { anlageZeile, zeigeTeile } from "./anlagen.js";
import { lageAusAdresse } from "./karte.js";
import { endeUnter, ersetzeOrg, staettenSuche, starteUnter, zeigeNk, zeigeNkStaetten } from "./neue_objekte.js";
import { orgListeVon, orgZusatz, sucheOrg, waehleOrg, waehleOrgVorschlag, zeigeOrgVorschlaege } from "./organisationen.js";
import { planePruefung } from "./pruefung.js";
import { weiter } from "./senden.js";
import { waehleKomplex, zeigeArten, zeigeKoStaetten } from "./sportkomplexe.js";
import { waehleStuetzpunkt, zeigeSpStaetten } from "./stuetzpunkte.js";
import { ausEintrag, bearbeite, fuelle, neu, zeigeGewaehlt } from "./werte.js";
import { ANLAGEN_GRUPPEN, ANLAGEN_TYPEN, anlagenGruppe, gruppenText } from "../../daten/anlagen.js";
import { SCHEMA, modellFelder } from "../../daten/schema.js";
import { komplexeNachName } from "../../daten/sportkomplexe.js";
import { STP_JE_STAETTE, stuetzpunkteNachName } from "../../daten/stuetzpunkte.js";
import { GEBIETE } from "../../karte/gebiete.js";
import { esc, leer, schluesselName, verbinde, zaehle, zahl } from "../../lib/text.js";
import { normName } from "../../lib/vergleich.js";

// Beim Anlegen der Ansicht (ansichtVorschlag), in dieser Reihenfolge
export function starte() {
  z.el = document.getElementById("seite-vorschlag");
  z.NACH_ID = new Map(z.bestand.eintraege.map(e => [e.p.id, e]));
  z.form = undefined; z.vkarte = null; z.marke = null; z.nachbarn = null; z.original = null;
  z.lage = null; z.ars = ""; z.pruefen = 0; z.dubletten = [];
  // Felder der Sportstätte aus dem Modell: [{ pfad, p, pflicht, t, gruppe }]; die Teile eines
  // Unterobjekts (Adresse) einzeln als "adresse.plz", die Lage als ein Feld (Karte)
  z.FELDER = [];
  for (const [k, p, pflicht, t] of modellFelder("Sportstaette")) {
    if (p.formular === false) continue;
    if (t.ref && p.widget !== "karte") {
      for (const [k2, p2, pf2, t2] of modellFelder(t.ref)) {
        if (p2.formular !== false) z.FELDER.push({ pfad: `${k}.${k2}`, p: p2, pflicht: pf2, t: t2, gruppe: p.gruppe });
      }
    } else z.FELDER.push({ pfad: k, p, pflicht, t, gruppe: p.gruppe });
  }
  z.TITEL = Object.fromEntries(z.FELDER.map(f => [f.pfad, f.p.title || f.pfad]));
  z.TITEL.anlagen = "Sportanlagen";
  z.TITEL.neuer_sportkomplex = "Neuer Sportkomplex";
  z.FELD_LAGE = z.FELDER.find(f => f.p.widget === "karte");
  z.FELD_KOMPLEX = z.FELDER.find(f => f.p.widget === "sportkomplex");
  // Angaben einer Sportanlage neben Typ und Name (Baujahr, Maße, Belag …), nach Abschnitten
  z.ANLAGE_DETAILS = modellFelder("Sportanlage")
    .filter(([k, p]) => p.formular !== false && k !== "typ" && k !== "bezeichnung")
    .map(([k, p, pflicht, t], i) => ({ pfad: k, p, pflicht, t, i }));
  z.ANLAGE_ABSCHNITTE = SCHEMA.$defs.Sportanlage.gruppen || ["Allgemein"];
  // Einzelne Eingaben: ein Feld, bei „Anzahl je Wert“ (zaehler) eine je Wert ("pfad|Wert")
  z.ANLAGE_EINGABEN = z.ANLAGE_DETAILS.flatMap(d => d.p.widget === "zaehler"
    ? d.t.propertyNames.enum.map(w => ({ k: `${d.pfad}|${w}`, d, wert: w, titel: `${d.p.title}: ${w}` }))
    : [{ k: d.pfad, d, titel: d.p.title }]);
  // Felder einer Organisation; Namen mit "org." davor, damit sie nicht mit der Sportstätte kollidieren
  z.ORG_FELDER = modellFelder("Organisation").filter(([, p]) => p.formular !== false)
    .map(([k, p, pflicht, t]) => ({ pfad: "org." + k, k, p, pflicht, t }));
  z.orgOriginal = null;  // { o: Eintrag im Verzeichnis oder { name } aus dem Bestand, imVerzeichnis }
  // Felder eines Sportkomplexes ("ko." davor), die Adresse je Teil; die Lage folgt aus den Sportstätten
  z.KO_FELDER = [];
  for (const [k, p, pflicht, t] of modellFelder("Sportkomplex")) {
    if (p.formular === false || k === "lage") continue;
    if (t.ref) {
      for (const [k2, p2, pf2, t2] of modellFelder(t.ref)) {
        if (p2.formular !== false) z.KO_FELDER.push({ pfad: `ko.${k}.${k2}`, k: `${k}.${k2}`, p: p2, pflicht: pf2, t: t2 });
      }
    } else z.KO_FELDER.push({ pfad: "ko." + k, k, p, pflicht, t });
  }
  // Felder eines Stützpunkts ("sp." davor); Sportstätten und Sportkomplexe wählt man eigens aus
  z.SP_FELDER = modellFelder("Stuetzpunkt").filter(([, p]) => p.formular !== false)
    .map(([k, p, pflicht, t]) => ({ pfad: "sp." + k, k, p, pflicht, t }));
  z.spOriginal = null;  // gewählter Stützpunkt oder null für einen neuen
  z.spStaetten = new Set(); z.spKomplexe = new Set();
  z.koOriginal = null;  // gewählter Sportkomplex (aus sportkomplexe.json) oder null für einen neuen
  z.koStaetten = new Set();  // IDs der Sportstätten des Komplexes nach der Änderung
  z.nkStaetten = new Set();  // weitere Sportstätten eines neuen Sportkomplexes (bei einer Sportstätte)
  // Neue Sportstätten für einen Sportkomplex oder Stützpunkt: { ref, ziel, sportstaette, anlagen }
  z.neueStaetten = []; z.neuNr = 0; z.unter = null;  // unter: { ziel, ref, anmerkung } beim Eintragen
  z.neueOrgs = new Map();  // schluesselName → { name, eintragen, typ, website, geprueft }
  z.FELD_TYP = (() => { const x = modellFelder("Sportanlage").find(([k]) => k === "typ");
    return { pfad: "typ", p: x[1], pflicht: true, t: x[3] }; })();
  z.SPORTARTEN = haeufig(z.bestand.eintraege.flatMap(e => [...e.sp])).map(x => x[0])
    .sort((a, b) => a.localeCompare(b, "de"));
  // Typen der Sportanlagen (alle bekannten und die im Bestand): nach Gruppe, darin nach Häufigkeit;
  // bei gewählter Kategorie zuerst die Typen, die im Bestand bei ihr vorkommen (typListe)
  z.ANLAGEN = (() => {
    const zahlen = zaehle(z.bestand.eintraege.flatMap(e => e.p.anlagen));
    const reihe = ANLAGEN_GRUPPEN.map(g => g[0]);
    return [...new Set([...Object.keys(ANLAGEN_TYPEN), ...Object.keys(zahlen)])].sort((a, b) =>
      reihe.indexOf(anlagenGruppe(a)) - reihe.indexOf(anlagenGruppe(b)) || (zahlen[b] || 0) - (zahlen[a] || 0));
  })();
  z.typListeFuer = undefined;
  z.typenJeKategorie = null;  // Kategorie → { Typ: Zahl der Sportstätten }
  // Felder mit widget "chips" (Sportarten): Liste zum Hinzufügen und Entfernen
  z.chips = {};
  for (const f of [...z.FELDER, ...z.SP_FELDER]) if (f.p.widget === "chips" || f.p.widget === "organisationen") z.chips[f.pfad] = new Set();
}

export const F = n => z.form.elements.namedItem(n);
// Auswahllisten aus dem Datenbestand und den Gebieten
export function haeufig(werte) {
  const zahlen = new Map();
  for (const w of werte) if (!leer(w)) {
    const k = schluesselName(w), x = zahlen.get(k) || { n: 0, namen: new Map() };
    x.n++; x.namen.set(w.trim(), (x.namen.get(w.trim()) || 0) + 1); zahlen.set(k, x);
  }
  return [...zahlen.values()].map(x => [[...x.namen].sort((a, b) => b[1] - a[1])[0][0], x.n]);
}
export const kategorie = () => F("art").value === "anlagen" ? (z.original && z.original.p.kategorie) : F("kategorie").value;
export function typListe() {
  const k = kategorie();
  if (k === z.typListeFuer) return;
  z.typListeFuer = k;
  if (!z.typenJeKategorie) {
    z.typenJeKategorie = {};
    for (const e of z.bestand.eintraege) for (const t of e.typen) {
      const zahlen = z.typenJeKategorie[e.kat] ??= {};
      zahlen[t] = (zahlen[t] || 0) + 1;
    }
  }
  const zahlen = (k && z.typenJeKategorie[k]) || {};
  const haeufig = Object.keys(zahlen).sort((a, b) => zahlen[b] - zahlen[a]);
  const liste = [...haeufig, ...z.ANLAGEN.filter(t => !(t in zahlen))];
  z.el.querySelector("#v-anlagen-liste").innerHTML = liste.map(t => `<option value="${esc(t)}">`
    + esc(gruppenText(anlagenGruppe(t))) + (zahlen[t] ? ` – bei ${zahl(zahlen[t])} ${esc(k)}` : "") + `</option>`).join("");
}
export const ORTE = () => [...new Set([...GEBIETE.filter(g => g.e === "gemeinde").map(g => g.n),
  ...z.bestand.eintraege.map(e => e.p.ort).filter(v => !leer(v))])].sort((a, b) => a.localeCompare(b, "de"));
export const optionen = liste => liste.map(v => `<option value="${esc(v)}"></option>`).join("");
export const auswahl = (name, werte, leerText) => `<select name="${esc(name)}">`
  + `<option value="">${leerText}</option>` + werte.map(v => `<option>${esc(v)}</option>`).join("") + `</select>`;
export const jaNein = name => `<span class="radios">` + [["ja", "Ja"], ["nein", "Nein"], ["", "Nicht bekannt"]]
  .map(([w, t]) => `<label><input type="radio" name="${esc(name)}" value="${w}"${w ? "" : " checked"}> ${t}</label>`).join("") + `</span>`;
export const feld = (label, inhalt, extra = "") => `<label class="feld${extra}"><span>${label}</span>${inhalt}</label>`;
export const istZahl = t => t.type === "integer" || t.type === "number";
// Eingabe für ein Feld des Modells, nach Typ und widget
export function eingabe(f) {
  const { pfad, p, pflicht, t } = f, n = esc(pfad);
  const label = esc(p.title || pfad) + (pflicht ? " *" : "");
  const hilfe = p.description ? ` placeholder="${esc(p.description)}" title="${esc(p.description)}"` : "";
  if (p.widget === "karte") {
    return `<div class="lage"><b>${label}</b> <span id="v-lage"></span>
        <button type="button" class="knopf2" id="v-geocode">Lage aus der Adresse suchen</button>
        <div id="v-gemeinde" class="hinweis"></div></div>`;
  }
  if (p.widget === "chips" || p.widget === "organisationen") {
    const liste = p.widget === "organisationen" ? `data-orgs autocomplete="off"` : `list="v-sportarten-liste"`;
    return `<div class="chips-feld" data-chips="${n}"><span class="chips-titel">${label}</span><div class="chips"></div>
        <div class="hinzu"><input ${liste} placeholder="${label} eingeben oder auswählen"
        aria-label="${label}"><button type="button" class="knopf2">Hinzufügen</button></div></div>`;
  }
  if (p.widget === "ja_nein") return `<div class="zeile-feld"><span>${label}</span>${jaNein(pfad)}</div>`;
  if (p.widget === "sportkomplex") {
    return feld(label, `<select name="${n}" title="Nur wählen, wenn mehrere Sportstätten an einem Ort `
      + `zusammengehören."></select>`)
      + `<div id="v-nk" class="nk" hidden><p class="hinweis">Neuer Sportkomplex mit dieser Sportstätte und
          mindestens einer weiteren.</p>${z.KO_FELDER.map(f => eingabe({ ...f, pfad: "nk." + f.k })).join("")}
          <div class="chips-feld"><span class="chips-titel">Weitere Sportstätten des Sportkomplexes *</span>
          <div class="chips" id="v-nk-staetten"></div><div class="hinzu"><input type="search" id="v-nk-suche"
          placeholder="Sportstätte hinzufügen: Name, Ort oder ID" aria-label="Sportstätte zum neuen Sportkomplex hinzufügen"></div>
          <ul id="v-nk-treffer" class="treffer"></ul></div></div>`;
  }
  if (t.enum) return feld(label, auswahl(pfad, t.enum, pflicht ? "– bitte wählen –" : "nicht bekannt"));
  if (istZahl(t)) {
    return feld(label, `<input name="${n}" type="number" step="1"`
      + (t.minimum !== undefined ? ` min="${t.minimum}"` : "") + (t.maximum !== undefined ? ` max="${t.maximum}"` : "")
      + `>`, " klein");
  }
  if (t.type === "array") return feld(label, `<input name="${n}" placeholder="mehrere mit Komma trennen">`);
  if (t.format === "date") return feld(label, `<input name="${n}" type="date">`, " klein");
  const liste = p.widget === "organisation" ? ` data-orgs autocomplete="off"` : p.widget === "ort" ? ` list="v-orte"` : "";
  const art = p.widget === "organisation" ? `<span class="art" data-art="${n}" hidden></span>` : "";
  return feld(label, `<input name="${n}"${p.widget === "url" ? ` type="url"` : ""}${liste}`
    + (t.maxLength ? ` maxlength="${t.maxLength}"` : "") + `${hilfe}>${art}`);
}
// Abschnitte in der Reihenfolge des Modells (gruppen); Felder ohne Gruppe am Ende
export function abschnitte() {
  const gruppen = [...(SCHEMA.$defs.Sportstaette.gruppen || [])];
  for (const f of z.FELDER) if (!gruppen.includes(f.gruppe || "Weitere Angaben")) gruppen.push(f.gruppe || "Weitere Angaben");
  return gruppen.map(g => {
    const fs = z.FELDER.filter(f => (f.gruppe || "Weitere Angaben") === g);
    return fs.length ? `<fieldset><legend>${esc(g)}</legend>${fs.map(eingabe).join("")}</fieldset>` : "";
  }).join("");
}
export function baue() {
  z.el.innerHTML = `<div class="inhalt vorschlag"><h2>Vorschlag machen</h2>
      <p class="unter">Neue Sportstätte mit ihren Sportanlagen eintragen, die Angaben einer Sportstätte
      ändern, ihre Sportanlagen hinzufügen, ändern und entfernen, eine Organisation (Verein, Eigentümer,
      Betreiber), einen Sportkomplex oder einen Stützpunkt eintragen, ändern und löschen. Im nächsten Schritt
      werden die Angaben an die Umfrage übergeben und dort abgeschickt; nach einer Prüfung erscheinen
      sie auf der Karte. Bitte keine personenbezogenen Daten (Namen, private Telefonnummern) eintragen.</p>
      <div class="raster"><form id="v-form" novalidate autocomplete="off">
      <fieldset id="v-art"><legend>Was möchten Sie tun?</legend>
        <span class="radios gross"><label><input type="radio" name="art" value="neu" checked> Neue Sportstätte mit ihren Sportanlagen eintragen</label>
        <label><input type="radio" name="art" value="aenderung"> Sportstätte ändern: Angaben (Name, Adresse, Betreiber …) und Sportanlagen</label>
        <label><input type="radio" name="art" value="organisation"> Organisation (Verein, Eigentümer, Betreiber …) eintragen, ändern oder löschen</label>
        <label><input type="radio" name="art" value="sportkomplex"> Sportkomplex (mehrere Sportstätten an einem Ort) anlegen, ändern oder auflösen</label>
        <label><input type="radio" name="art" value="stuetzpunkt"> Stützpunkt (Olympia-, Bundes-, Landesstützpunkt) eintragen, ändern oder löschen</label></span>
        <div id="v-auswahl" hidden><input type="search" id="v-suche" placeholder="Name, Ort oder ID der Sportstätte suchen"
          aria-label="Sportstätte suchen"><ul id="v-treffer" class="treffer"></ul></div>
        <div id="v-gewaehlt"></div>
      </fieldset>
      <div id="v-unter" class="warnung" hidden>Neue Sportstätte für <b></b>: Angaben und Sportanlagen
        eintragen, dann „Sportstätte übernehmen“. <button type="button" class="knopf2" id="v-unter-ab">Abbrechen</button></div>
      <div id="v-teil-staette">${abschnitte()}</div>
      <fieldset id="v-teil-anlagen"><legend>Sportanlagen</legend>
        <p class="hinweis">Die einzelnen Anlagen der Sportstätte, z. B. Großspielfeld, Rundlaufbahn, Hallenteil.
        Jede Sportanlage gehört zu genau dieser Sportstätte. Name nur, wenn die Anlage einen eigenen hat
        (z. B. „Halle 1“, „Kunstrasen B“).</p>
        <table class="anlagen"><thead><tr><th>${esc(z.FELD_TYP.p.title)} *</th><th>${esc(modellFelder("Sportanlage")
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
        <div id="v-org-felder">${z.ORG_FELDER.map(eingabe).join("")}</div>
        <label class="bestaetigen" id="v-org-weg" hidden><input type="checkbox" name="org-loeschen">
          Diese Organisation aus dem Verzeichnis löschen (z. B. aufgelöst oder doppelt)</label>
      </fieldset>
      <fieldset id="v-teil-komplex" hidden><legend>Sportkomplex</legend>
        <p class="hinweis">Ein Sportkomplex fasst mehrere Sportstätten an einem Ort zusammen, z. B. ein
        Sportzentrum mit Halle, Stadion und Freibad – mindestens zwei. Eigentümer, Betreiber und Sportanlagen
        bleiben bei den Sportstätten.</p>
        <input type="search" id="v-ko-suche" placeholder="vorhandenen Sportkomplex suchen (leer lassen für einen neuen)"
          aria-label="Sportkomplex suchen"><ul id="v-ko-treffer" class="treffer"></ul>
        <div id="v-ko-gewaehlt"></div>
        <div id="v-ko-felder">${z.KO_FELDER.map(eingabe).join("")}</div>
        <div class="chips-feld"><span class="chips-titel">Sportstätten des Sportkomplexes *</span>
          <div class="chips" id="v-ko-staetten"></div>
          <div class="hinzu"><input type="search" id="v-ko-staette-suche" placeholder="Sportstätte hinzufügen: Name, Ort oder ID"
            aria-label="Sportstätte hinzufügen"><button type="button" class="knopf2" data-neue-staette="sportkomplex">+ neue Sportstätte</button></div>
          <ul id="v-ko-staette-treffer" class="treffer"></ul></div>
        <label class="bestaetigen" id="v-ko-weg" hidden><input type="checkbox" name="ko-loeschen">
          Diesen Sportkomplex auflösen (die Sportstätten bleiben, nur die Klammer entfällt)</label>
      </fieldset>
      <fieldset id="v-teil-stp" hidden><legend>Stützpunkt</legend>
        <p class="hinweis">Anerkennung als Stützpunkt des Leistungssports für Sportarten an einer oder mehreren
        Sportstätten. Gehören alle Sportstätten eines Sportkomplexes dazu, reicht der Sportkomplex.</p>
        <input type="search" id="v-stp-suche" placeholder="vorhandenen Stützpunkt suchen (leer lassen für einen neuen)"
          aria-label="Stützpunkt suchen"><ul id="v-stp-treffer" class="treffer"></ul>
        <div id="v-stp-gewaehlt"></div>
        <div id="v-stp-felder">${z.SP_FELDER.map(eingabe).join("")}</div>
        <div class="chips-feld"><span class="chips-titel">Sportstätten und Sportkomplexe *</span>
          <div class="chips" id="v-stp-staetten"></div>
          <div class="hinzu"><input type="search" id="v-stp-staette-suche" placeholder="Sportstätte oder Sportkomplex hinzufügen: Name, Ort oder ID"
            aria-label="Sportstätte oder Sportkomplex hinzufügen"><button type="button" class="knopf2" data-neue-staette="stuetzpunkt">+ neue Sportstätte</button></div>
          <ul id="v-stp-staette-treffer" class="treffer"></ul></div>
        <label class="bestaetigen" id="v-stp-weg" hidden><input type="checkbox" name="stp-loeschen">
          Diesen Stützpunkt löschen (die Anerkennung besteht nicht mehr)</label>
      </fieldset>
      <fieldset id="v-teil-neue-orgs" hidden><legend>Neue Organisationen</legend>
        <p class="hinweis">Diese Namen stehen noch nicht im Verzeichnis der Organisationen. Mit Häkchen
        werden sie mit diesem Vorschlag eingetragen. Keine Personen und keine Kontaktdaten.</p>
        <div id="v-neue-orgs"></div></fieldset>
      <fieldset id="v-anmerkung"><legend>Anmerkung</legend>
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
      <datalist id="v-sportarten-liste">${optionen(z.SPORTARTEN)}</datalist>
      <datalist id="v-anlagen-liste"></datalist></div>`;
  z.form = z.el.querySelector("#v-form");
  z.form.addEventListener("input", () => { zeigeArten(); planePruefung(); });
  z.form.addEventListener("change", ev => {
    if (ev.target.name === "art") {
      const art = F("art").value;
      if (art === "organisation") { waehleOrg(null); zeigeTeile(); zeigeGewaehlt(); planePruefung(); return; }
      if (art === "stuetzpunkt") {
        const e = z.original, sp = e ? STP_JE_STAETTE.get(e.p.id) || [] : [];
        waehleStuetzpunkt(sp.length === 1 ? sp[0].id : null, e && sp.length !== 1 ? [e.p.id] : []);
        zeigeTeile(); zeigeGewaehlt(); return;
      }
      if (art === "sportkomplex") {
        const e = z.original;
        waehleKomplex(e && e.p.sportkomplex ? e.p.sportkomplex : null, e ? [e.p.id] : []);
        zeigeTeile(); zeigeGewaehlt(); return;
      }
      if (art === "neu") neu();
      else if (z.original && z.original.art !== art) { z.original.art = art; fuelle(ausEintrag(z.original)); }
      zeigeTeile(); zeigeGewaehlt();
    }
    planePruefung();
  });
  z.form.addEventListener("submit", ev => { ev.preventDefault(); weiter(); });
  z.el.querySelector("#v-leeren").addEventListener("click", () => neu());
  const geo = z.el.querySelector("#v-geocode");
  if (geo) geo.addEventListener("click", lageAusAdresse);
  for (const box of z.el.querySelectorAll("[data-chips]")) {
    const pfad = box.dataset.chips, eing = box.querySelector("input");
    const dazu = () => { const v = eing.value.trim(); if (v) { z.chips[pfad].add(v); eing.value = ""; zeigeChips(pfad); planePruefung(); } };
    box.querySelector("button").addEventListener("click", dazu);
    eing.addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); dazu(); } });
  }
  z.el.querySelector("#v-anlage-dazu").addEventListener("click", () => {
    anlageZeile({ typ: "", bezeichnung: "", id: "" }, 1); planePruefung();
    const zahlen = z.el.querySelectorAll("#v-anlagen tr"); zahlen[zahlen.length - 1].querySelector("input").focus();
  });
  const suche = z.el.querySelector("#v-suche"), treffer = z.el.querySelector("#v-treffer");
  suche.addEventListener("input", () => {
    const worte = normName(suche.value).split(" ").filter(Boolean);
    if (!worte.length) { treffer.innerHTML = ""; return; }
    const t = [];
    for (const e of z.bestand.eintraege) {
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
  const orgSuche = z.el.querySelector("#v-org-suche"), orgTreffer = z.el.querySelector("#v-org-treffer");
  orgSuche.addEventListener("input", () => {
    const q = schluesselName(orgSuche.value);
    orgTreffer.innerHTML = q ? sucheOrg(q).map(x =>
      `<li data-org="${esc(x.name)}">${esc(x.name)}<small>${esc(orgZusatz(x))}</small></li>`).join("")
      || `<li class="gruppe">Nichts gefunden – unten als neue Organisation eintragen</li>` : "";
  });
  z.el.addEventListener("input", ev => {
    if (ev.target.matches("input[data-orgs]")) zeigeOrgVorschlaege(ev.target);
  });
  z.el.addEventListener("focusout", ev => {
    if (ev.target.matches("input[data-orgs]")) orgListeVon(ev.target).hidden = true;
  });
  z.el.addEventListener("mousedown", ev => {
    const li = ev.target.closest("ul.org-vorschlaege li[data-name]");
    if (!li) return;
    ev.preventDefault();  // Eingabe behält den Fokus
    waehleOrgVorschlag(li.parentElement.previousElementSibling, li.dataset.name);
  });
  z.el.addEventListener("keydown", ev => {  // vor den eigenen Tasten der Eingabe (capture)
    const eing = ev.target;
    if (!eing.matches || !eing.matches("input[data-orgs]")) return;
    const ul = orgListeVon(eing), lis = [...ul.querySelectorAll("li")];
    if (ul.hidden || !lis.length) return;
    const i = lis.findIndex(li => li.classList.contains("aktiv"));
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
      ev.preventDefault();
      const j = (i + (ev.key === "ArrowDown" ? 1 : lis.length - 1 + (i < 0 ? 1 : 0))) % lis.length;
      lis.forEach((li, k) => li.classList.toggle("aktiv", k === j));
    } else if (ev.key === "Enter" && i >= 0) {
      ev.preventDefault(); ev.stopPropagation();
      waehleOrgVorschlag(eing, lis[i].dataset.name);
    } else if (ev.key === "Escape") {
      ul.hidden = true;
    }
  }, true);
  // Stützpunkt: vorhandenen suchen; Sportstätten und Sportkomplexe dazu suchen
  const spSuche = z.el.querySelector("#v-stp-suche"), spTreffer = z.el.querySelector("#v-stp-treffer");
  spSuche.addEventListener("input", () => {
    const worte = normName(spSuche.value).split(" ").filter(Boolean);
    const t = worte.length ? stuetzpunkteNachName().filter(x => worte.every(w => normName([x.name, x.art,
      ...(x.sportarten || [])].join(" ")).includes(w))).slice(0, 8) : [];
    spTreffer.innerHTML = !worte.length ? "" : t.map(x => `<li data-stp="${esc(x.id)}">${esc(x.name)}`
      + `<small>${esc(x.art || "")}</small></li>`).join("")
      || `<li class="gruppe">Nichts gefunden – unten einen neuen eintragen</li>`;
  });
  spTreffer.addEventListener("click", ev => {
    const li = ev.target.closest("li[data-stp]");
    if (!li) return;
    spSuche.value = ""; spTreffer.innerHTML = "";
    waehleStuetzpunkt(li.dataset.stp); zeigeTeile();
  });
  const spStSuche = z.el.querySelector("#v-stp-staette-suche"), spStTreffer = z.el.querySelector("#v-stp-staette-treffer");
  spStSuche.addEventListener("input", () => {
    const worte = normName(spStSuche.value).split(" ").filter(Boolean);
    if (!worte.length) { spStTreffer.innerHTML = ""; return; }
    const ko = komplexeNachName().filter(k => !z.spKomplexe.has(k.id)
      && worte.every(w => normName([k.name, k.id].join(" ")).includes(w))).slice(0, 4);
    const st = [];
    for (const e of z.bestand.eintraege) {
      if (z.spStaetten.has(e.p.id)) continue;
      if (worte.every(w => normName([e.p.name, e.p.ort, e.p.adresse, e.p.id].join(" ")).includes(w))) st.push(e);
      if (st.length >= 8) break;
    }
    spStTreffer.innerHTML = ko.map(k => `<li data-ko="${esc(k.id)}">${esc(k.name)}<small>Sportkomplex, `
      + `${zahl(k.mitglieder.length)} Sportstätten</small></li>`).join("")
      + st.map(e => `<li data-st="${esc(e.p.id)}">${esc(e.p.name || e.kat)}`
      + `<small>${esc(verbinde([e.p.kategorie, e.p.adresse]))}</small></li>`).join("")
      || `<li class="gruppe">Nichts gefunden</li>`;
  });
  spStTreffer.addEventListener("click", ev => {
    const li = ev.target.closest("li[data-st], li[data-ko]");
    if (!li) return;
    spStSuche.value = ""; spStTreffer.innerHTML = "";
    if (li.dataset.ko) z.spKomplexe.add(li.dataset.ko); else z.spStaetten.add(li.dataset.st);
    zeigeSpStaetten();
  });
  // Sportkomplex: vorhandenen suchen; Sportstätten dazu suchen
  const koSuche = z.el.querySelector("#v-ko-suche"), koTreffer = z.el.querySelector("#v-ko-treffer");
  koSuche.addEventListener("input", () => {
    const worte = normName(koSuche.value).split(" ").filter(Boolean);
    const t = worte.length ? komplexeNachName().filter(k => worte.every(w => normName(k.name).includes(w))).slice(0, 8) : [];
    koTreffer.innerHTML = !worte.length ? "" : t.map(k => `<li data-ko="${esc(k.id)}">${esc(k.name)}`
      + `<small>${zahl(k.mitglieder.length)} Sportstätten</small></li>`).join("")
      || `<li class="gruppe">Nichts gefunden – unten einen neuen eintragen</li>`;
  });
  koTreffer.addEventListener("click", ev => {
    const li = ev.target.closest("li[data-ko]");
    if (!li) return;
    koSuche.value = ""; koTreffer.innerHTML = "";
    waehleKomplex(li.dataset.ko); zeigeTeile();
  });
  const stSuche = z.el.querySelector("#v-ko-staette-suche"), stTreffer = z.el.querySelector("#v-ko-staette-treffer");
  stSuche.addEventListener("input", () => {
    const worte = normName(stSuche.value).split(" ").filter(Boolean);
    const t = [];
    if (worte.length) for (const e of z.bestand.eintraege) {
      if (z.koStaetten.has(e.p.id)) continue;
      const text = normName([e.p.name, e.p.ort, e.p.adresse, e.p.id].join(" "));
      if (worte.every(w => text.includes(w))) t.push(e);
      if (t.length >= 8) break;
    }
    stTreffer.innerHTML = !worte.length ? "" : t.map(e => `<li data-st="${esc(e.p.id)}">${esc(e.p.name || e.kat)}`
      + `<small>${esc(verbinde([e.p.kategorie, e.p.adresse]))}</small></li>`).join("")
      || `<li class="gruppe">Keine Sportstätte gefunden</li>`;
  });
  stTreffer.addEventListener("click", ev => {
    const li = ev.target.closest("li[data-st]");
    if (!li) return;
    stSuche.value = ""; stTreffer.innerHTML = "";
    z.koStaetten.add(li.dataset.st); zeigeKoStaetten();
  });
  orgTreffer.addEventListener("click", ev => {
    const li = ev.target.closest("li[data-org]");
    if (!li) return;
    orgSuche.value = ""; orgTreffer.innerHTML = "";
    waehleOrg(li.dataset.org); zeigeTeile(); planePruefung();
  });
  // neuer Sportkomplex bei einer Sportstätte
  if (z.FELD_KOMPLEX) {
    F(z.FELD_KOMPLEX.pfad).addEventListener("change", zeigeNk);
    staettenSuche(z.el.querySelector("#v-nk-suche"), z.el.querySelector("#v-nk-treffer"),
      id => z.nkStaetten.has(id) || (z.original && z.original.p.id === id),
      id => { z.nkStaetten.add(id); zeigeNkStaetten(); planePruefung(); });
  }
  // neue Sportstätten für Sportkomplex und Stützpunkt
  z.el.querySelectorAll("[data-neue-staette]").forEach(b => b.addEventListener("click", () => starteUnter(b.dataset.neueStaette)));
  z.el.querySelector("#v-unter-ab").addEventListener("click", () => endeUnter());
  z.el.addEventListener("click", ev => {
    const a = ev.target.closest("[data-neu-bearbeiten]");
    if (a) { ev.preventDefault(); starteUnter(a.dataset.ziel, a.dataset.neuBearbeiten); }
    const statt = ev.target.closest("[data-org-statt]");
    if (statt) {
      ev.preventDefault();
      ersetzeOrg(statt.closest(".neue-org") ? z.neueOrgs.get(statt.closest(".neue-org").dataset.k).name : "", statt.dataset.orgStatt);
    }
  });
  // Angaben neuer Organisationen
  const no = z.el.querySelector("#v-neue-orgs");
  const merke = ev => {
    const i = ev.target.closest("[data-no]"), box = ev.target.closest(".neue-org");
    if (!i || !box) return;
    const o = z.neueOrgs.get(box.dataset.k);
    o[i.dataset.no] = i.type === "checkbox" ? i.checked : i.value;
  };
  no.addEventListener("input", merke);
  no.addEventListener("change", merke);
}
export function zeigeChips(pfad) {
  const c = z.el.querySelector(`[data-chips="${pfad}"] .chips`);
  c.innerHTML = [...z.chips[pfad]].map(s => `<span class="chip-s">${esc(s)}<button type="button" `
    + `data-weg="${esc(s)}" aria-label="${esc(s)} entfernen">×</button></span>`).join("")
    || `<span class="hinweis">noch keine</span>`;
  c.querySelectorAll("[data-weg]").forEach(b => b.addEventListener("click", () => {
    z.chips[pfad].delete(b.dataset.weg); zeigeChips(pfad); planePruefung(); }));
}
