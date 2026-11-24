// vorschlag/10_formular.js: Beginn von ansichtVorschlag: Zustand, Felder aus dem Modell, Aufbau des Formulars.
// Teil des Rumpfs von ansichtVorschlag – nur zusammen mit den anderen Teilen gültig
// (app/__init__.py setzt vorschlag/*.js der Reihe nach zu app/vorschlag.js zusammen).
function ansichtVorschlag(bestand) {
  const el = document.getElementById("seite-vorschlag");
  const NACH_ID = new Map(bestand.eintraege.map(e => [e.p.id, e]));
  let form, vkarte = null, marke = null, nachbarn = null, original = null;
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
  TITEL.neuer_sportkomplex = "Neuer Sportkomplex";
  const FELD_LAGE = FELDER.find(f => f.p.widget === "karte");
  const FELD_KOMPLEX = FELDER.find(f => f.p.widget === "sportkomplex");
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
  // Felder eines Sportkomplexes ("ko." davor), die Adresse je Teil; die Lage folgt aus den Sportstätten
  const KO_FELDER = [];
  for (const [k, p, pflicht, t] of modellFelder("Sportkomplex")) {
    if (p.formular === false || k === "lage") continue;
    if (t.ref) {
      for (const [k2, p2, pf2, t2] of modellFelder(t.ref)) {
        if (p2.formular !== false) KO_FELDER.push({ pfad: `ko.${k}.${k2}`, k: `${k}.${k2}`, p: p2, pflicht: pf2, t: t2 });
      }
    } else KO_FELDER.push({ pfad: "ko." + k, k, p, pflicht, t });
  }
  // Felder eines Stützpunkts ("sp." davor); Sportstätten und Sportkomplexe wählt man eigens aus
  const SP_FELDER = modellFelder("Stuetzpunkt").filter(([, p]) => p.formular !== false)
    .map(([k, p, pflicht, t]) => ({ pfad: "sp." + k, k, p, pflicht, t }));
  let spOriginal = null;  // gewählter Stützpunkt oder null für einen neuen
  let spStaetten = new Set(), spKomplexe = new Set();
  let koOriginal = null;  // gewählter Sportkomplex (aus sportkomplexe.json) oder null für einen neuen
  let koStaetten = new Set();  // IDs der Sportstätten des Komplexes nach der Änderung
  let nkStaetten = new Set();  // weitere Sportstätten eines neuen Sportkomplexes (bei einer Sportstätte)
  // Neue Sportstätten für einen Sportkomplex oder Stützpunkt: { ref, ziel, sportstaette, anlagen }
  let neueStaetten = [], neuNr = 0, unter = null;  // unter: { ziel, ref, anmerkung } beim Eintragen
  const neueOrgs = new Map();  // schluesselName → { name, eintragen, typ, website, geprueft }
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
  // bei gewählter Kategorie zuerst die Typen, die im Bestand bei ihr vorkommen (typListe)
  const ANLAGEN = (() => {
    const z = zaehle(bestand.eintraege.flatMap(e => e.p.anlagen));
    const reihe = ANLAGEN_GRUPPEN.map(g => g[0]);
    return [...new Set([...Object.keys(ANLAGEN_TYPEN), ...Object.keys(z)])].sort((a, b) =>
      reihe.indexOf(anlagenGruppe(a)) - reihe.indexOf(anlagenGruppe(b)) || (z[b] || 0) - (z[a] || 0));
  })();
  const kategorie = () => F("art").value === "anlagen" ? (original && original.p.kategorie) : F("kategorie").value;
  let typListeFuer;
  let typenJeKategorie = null;  // Kategorie → { Typ: Zahl der Sportstätten }
  function typListe() {
    const k = kategorie();
    if (k === typListeFuer) return;
    typListeFuer = k;
    if (!typenJeKategorie) {
      typenJeKategorie = {};
      for (const e of bestand.eintraege) for (const t of e.typen) {
        const z = typenJeKategorie[e.kat] ??= {};
        z[t] = (z[t] || 0) + 1;
      }
    }
    const z = (k && typenJeKategorie[k]) || {};
    const haeufig = Object.keys(z).sort((a, b) => z[b] - z[a]);
    const liste = [...haeufig, ...ANLAGEN.filter(t => !(t in z))];
    el.querySelector("#v-anlagen-liste").innerHTML = liste.map(t => `<option value="${esc(t)}">`
      + esc(gruppenText(anlagenGruppe(t))) + (z[t] ? ` – bei ${zahl(z[t])} ${esc(k)}` : "") + `</option>`).join("");
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
          mindestens einer weiteren.</p>${KO_FELDER.map(f => eingabe({ ...f, pfad: "nk." + f.k })).join("")}
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
      <fieldset id="v-teil-komplex" hidden><legend>Sportkomplex</legend>
        <p class="hinweis">Ein Sportkomplex fasst mehrere Sportstätten an einem Ort zusammen, z. B. ein
        Sportzentrum mit Halle, Stadion und Freibad – mindestens zwei. Eigentümer, Betreiber und Sportanlagen
        bleiben bei den Sportstätten.</p>
        <input type="search" id="v-ko-suche" placeholder="vorhandenen Sportkomplex suchen (leer lassen für einen neuen)"
          aria-label="Sportkomplex suchen"><ul id="v-ko-treffer" class="treffer"></ul>
        <div id="v-ko-gewaehlt"></div>
        <div id="v-ko-felder">${KO_FELDER.map(eingabe).join("")}</div>
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
        <div id="v-stp-felder">${SP_FELDER.map(eingabe).join("")}</div>
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
      <datalist id="v-sportarten-liste">${optionen(SPORTARTEN)}</datalist>
      <datalist id="v-anlagen-liste"></datalist></div>`;
    form = el.querySelector("#v-form");
    form.addEventListener("input", () => { zeigeArten(); planePruefung(); });
    form.addEventListener("change", ev => {
      if (ev.target.name === "art") {
        const art = F("art").value;
        if (art === "organisation") { waehleOrg(null); zeigeTeile(); zeigeGewaehlt(); planePruefung(); return; }
        if (art === "stuetzpunkt") {
          const e = original, sp = e ? STP_JE_STAETTE.get(e.p.id) || [] : [];
          waehleStuetzpunkt(sp.length === 1 ? sp[0].id : null, e && sp.length !== 1 ? [e.p.id] : []);
          zeigeTeile(); zeigeGewaehlt(); return;
        }
        if (art === "sportkomplex") {
          const e = original;
          waehleKomplex(e && e.p.sportkomplex ? e.p.sportkomplex : null, e ? [e.p.id] : []);
          zeigeTeile(); zeigeGewaehlt(); return;
        }
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
      orgTreffer.innerHTML = q ? sucheOrg(q).map(x =>
        `<li data-org="${esc(x.name)}">${esc(x.name)}<small>${esc(orgZusatz(x))}</small></li>`).join("")
        || `<li class="gruppe">Nichts gefunden – unten als neue Organisation eintragen</li>` : "";
    });
    el.addEventListener("input", ev => {
      if (ev.target.matches("input[data-orgs]")) zeigeOrgVorschlaege(ev.target);
    });
    el.addEventListener("focusout", ev => {
      if (ev.target.matches("input[data-orgs]")) orgListeVon(ev.target).hidden = true;
    });
    el.addEventListener("mousedown", ev => {
      const li = ev.target.closest("ul.org-vorschlaege li[data-name]");
      if (!li) return;
      ev.preventDefault();  // Eingabe behält den Fokus
      waehleOrgVorschlag(li.parentElement.previousElementSibling, li.dataset.name);
    });
    el.addEventListener("keydown", ev => {  // vor den eigenen Tasten der Eingabe (capture)
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
    const spSuche = el.querySelector("#v-stp-suche"), spTreffer = el.querySelector("#v-stp-treffer");
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
    const spStSuche = el.querySelector("#v-stp-staette-suche"), spStTreffer = el.querySelector("#v-stp-staette-treffer");
    spStSuche.addEventListener("input", () => {
      const worte = normName(spStSuche.value).split(" ").filter(Boolean);
      if (!worte.length) { spStTreffer.innerHTML = ""; return; }
      const ko = komplexeNachName().filter(k => !spKomplexe.has(k.id)
        && worte.every(w => normName([k.name, k.id].join(" ")).includes(w))).slice(0, 4);
      const st = [];
      for (const e of bestand.eintraege) {
        if (spStaetten.has(e.p.id)) continue;
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
      if (li.dataset.ko) spKomplexe.add(li.dataset.ko); else spStaetten.add(li.dataset.st);
      zeigeSpStaetten();
    });
    // Sportkomplex: vorhandenen suchen; Sportstätten dazu suchen
    const koSuche = el.querySelector("#v-ko-suche"), koTreffer = el.querySelector("#v-ko-treffer");
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
    const stSuche = el.querySelector("#v-ko-staette-suche"), stTreffer = el.querySelector("#v-ko-staette-treffer");
    stSuche.addEventListener("input", () => {
      const worte = normName(stSuche.value).split(" ").filter(Boolean);
      const t = [];
      if (worte.length) for (const e of bestand.eintraege) {
        if (koStaetten.has(e.p.id)) continue;
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
      koStaetten.add(li.dataset.st); zeigeKoStaetten();
    });
    orgTreffer.addEventListener("click", ev => {
      const li = ev.target.closest("li[data-org]");
      if (!li) return;
      orgSuche.value = ""; orgTreffer.innerHTML = "";
      waehleOrg(li.dataset.org); zeigeTeile(); planePruefung();
    });
    // neuer Sportkomplex bei einer Sportstätte
    if (FELD_KOMPLEX) {
      F(FELD_KOMPLEX.pfad).addEventListener("change", zeigeNk);
      staettenSuche(el.querySelector("#v-nk-suche"), el.querySelector("#v-nk-treffer"),
        id => nkStaetten.has(id) || (original && original.p.id === id),
        id => { nkStaetten.add(id); zeigeNkStaetten(); planePruefung(); });
    }
    // neue Sportstätten für Sportkomplex und Stützpunkt
    el.querySelectorAll("[data-neue-staette]").forEach(b => b.addEventListener("click", () => starteUnter(b.dataset.neueStaette)));
    el.querySelector("#v-unter-ab").addEventListener("click", () => endeUnter());
    el.addEventListener("click", ev => {
      const a = ev.target.closest("[data-neu-bearbeiten]");
      if (a) { ev.preventDefault(); starteUnter(a.dataset.ziel, a.dataset.neuBearbeiten); }
      const statt = ev.target.closest("[data-org-statt]");
      if (statt) {
        ev.preventDefault();
        ersetzeOrg(statt.closest(".neue-org") ? neueOrgs.get(statt.closest(".neue-org").dataset.k).name : "", statt.dataset.orgStatt);
      }
    });
    // Angaben neuer Organisationen
    const no = el.querySelector("#v-neue-orgs");
    const merke = ev => {
      const i = ev.target.closest("[data-no]"), box = ev.target.closest(".neue-org");
      if (!i || !box) return;
      const o = neueOrgs.get(box.dataset.k);
      o[i.dataset.no] = i.type === "checkbox" ? i.checked : i.value;
    };
    no.addEventListener("input", merke);
    no.addEventListener("change", merke);
  }

  // Felder mit widget "chips" (Sportarten): Liste zum Hinzufügen und Entfernen
  const chips = {};
  for (const f of [...FELDER, ...SP_FELDER]) if (f.p.widget === "chips" || f.p.widget === "organisationen") chips[f.pfad] = new Set();
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
