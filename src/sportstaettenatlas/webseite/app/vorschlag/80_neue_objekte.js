// vorschlag/80_neue_objekte.js: Neuer Sportkomplex, neue Sportstätten und neue Organisationen innerhalb eines Vorschlags.
// Teil des Rumpfs von ansichtVorschlag – nur zusammen mit den anderen Teilen gültig
// (app/__init__.py setzt vorschlag/*.js der Reihe nach zu app/vorschlag.js zusammen).
  // --- Neuer Sportkomplex bei einer Sportstätte ---
  function zeigeNk() {
    const box = el.querySelector("#v-nk");
    if (box) box.hidden = !(FELD_KOMPLEX && F(FELD_KOMPLEX.pfad).value === NEUER_KOMPLEX);
  }
  function nkWerte() {
    if (!FELD_KOMPLEX || F(FELD_KOMPLEX.pfad).value !== NEUER_KOMPLEX) return null;
    const k = {};
    for (const f of KO_FELDER) { const x = String(F("nk." + f.k).value || "").trim(); if (x) setze(k, f.k, x); }
    return k;
  }
  const komplexText = v => verbinde([v.neuer_sportkomplex.name || "(ohne Name)",
    `mit ${zahl(nkStaetten.size)} weiteren Sportstätten`]);
  function nkFehler(v) {
    const fehler = [];
    for (const f of KO_FELDER) fehler.push(...regelFehler(f, hole(v.neuer_sportkomplex, f.k), `Neuer Sportkomplex: ${f.p.title}`));
    if (!nkStaetten.size) fehler.push("Neuer Sportkomplex: mindestens eine weitere Sportstätte wählen");
    if (enthaeltEmail(v.neuer_sportkomplex)) fehler.push("Bitte keine E-Mail-Adressen eintragen");
    return fehler;
  }
  function zeigeNkStaetten() {
    const c = el.querySelector("#v-nk-staetten");
    if (!c) return;
    c.innerHTML = [...nkStaetten].map(id => { const e = NACH_ID.get(id);
      return `<span class="chip-s">${esc(e ? e.p.name || e.kat : id)}`
        + (e && e.p.sportkomplex ? ` <small>(bisher in ${esc(komplexName(e.p.sportkomplex))})</small>` : "")
        + `<button type="button" data-nk-weg="${esc(id)}" aria-label="entfernen">×</button></span>`; }).join("")
      || `<span class="hinweis">noch keine</span>`;
    c.querySelectorAll("[data-nk-weg]").forEach(b => b.addEventListener("click", () => {
      nkStaetten.delete(b.dataset.nkWeg); zeigeNkStaetten(); planePruefung(); }));
  }
  // Suchfeld für Sportstätten (Name, Ort, ID) mit Trefferliste; waehle(id) bei Klick
  function staettenSuche(eing, ul, ohne, waehle) {
    eing.addEventListener("input", () => {
      const worte = normName(eing.value).split(" ").filter(Boolean), t = [];
      if (worte.length) for (const e of bestand.eintraege) {
        if (ohne(e.p.id)) continue;
        if (worte.every(w => normName([e.p.name, e.p.ort, e.p.adresse, e.p.id].join(" ")).includes(w))) t.push(e);
        if (t.length >= 8) break;
      }
      ul.innerHTML = !worte.length ? "" : t.map(e => `<li data-st="${esc(e.p.id)}">${esc(e.p.name || e.kat)}`
        + `<small>${esc(verbinde([e.p.kategorie, e.p.adresse]))}</small></li>`).join("")
        || `<li class="gruppe">Keine Sportstätte gefunden</li>`;
    });
    ul.addEventListener("click", ev => {
      const li = ev.target.closest("li[data-st]");
      if (!li) return;
      eing.value = ""; ul.innerHTML = "";
      waehle(li.dataset.st);
    });
  }

  // --- Neue Sportstätten für einen Sportkomplex oder Stützpunkt ---
  // Das Formular der Sportstätte dient dafür; Angaben des Komplexes bzw. Stützpunkts bleiben stehen.
  const neueStaette = ref => neueStaetten.find(n => n.ref === ref);
  const staettenName = id => { const n = neueStaette(id), e = NACH_ID.get(id);
    return n ? `${n.sportstaette.name || n.sportstaette.kategorie || "?"} (neu)` : e ? e.p.name || e.kat : id; };
  function starteUnter(ziel, ref = null) {
    const n = ref ? neueStaette(ref) : null;
    unter = { ziel, ref, anmerkung: F("anmerkung").value };
    original = null;
    F("art").value = "neu";
    fuelle(n ? { ...n.sportstaette, anlagen: n.anlagen } : {});
    F("anmerkung").value = unter.anmerkung;
    el.querySelector("#v-dubletten").dataset.bestaetigt = "";
    zeigeTeile(); zeigeGewaehlt(); zeigeFehlerliste([]);
    el.querySelector("#v-ausgabe").innerHTML = "";
    planePruefung();
  }
  function endeUnter() {
    const ziel = unter.ziel;
    F("anmerkung").value = unter.anmerkung;
    unter = null;
    F("art").value = ziel;
    komplexAuswahl();
    zeigeTeile(); zeigeGewaehlt(); zeigeFehlerliste([]);
    if (ziel === "sportkomplex") zeigeKoStaetten(); else zeigeSpStaetten();
    planePruefung();
  }
  function uebernimmUnter(v) {
    const fehler = [...regelVerstoesse(v), ...orgDublettenFehler(v)];
    if (enthaeltEmail(v)) fehler.push("Bitte keine E-Mail-Adressen eintragen");
    const cb = el.querySelector("#v-keine-doppelung");
    if (dubletten.length && !(cb && cb.checked)) {
      fehler.push("Mögliche Doppelung prüfen (rechts) und bestätigen, dass es eine andere Sportstätte ist");
    }
    zeigeFehlerliste(fehler);
    if (fehler.length) return;
    const st = ohneLeere(v.sportstaette);
    if (unter.ziel === "sportkomplex") delete st.sportkomplex;
    const anlagen = v.anlagenliste.filter(a => !a.entfernt && a.typ)
      .flatMap(a => Array.from({ length: a.n }, () => anlageModell(a)));
    const ref = unter.ref || `neu-${++neuNr}`, n = { ref, ziel: unter.ziel, sportstaette: st, anlagen };
    neueStaetten = [...neueStaetten.filter(x => x.ref !== ref), n];
    (unter.ziel === "sportkomplex" ? koStaetten : spStaetten).add(ref);
    endeUnter();
  }
  const neueStaettenDaten = ids => neueStaetten.filter(n => ids.has(n.ref))
    .map(n => ({ ref: n.ref, sportstaette: n.sportstaette, anlagen: n.anlagen }));

  // --- Neue Organisationen: Namen in den Feldern, die nicht im Verzeichnis stehen ---
  const ORG_TYPEN = (ORG_FELDER.find(f => f.k === "typ") || { t: {} }).t.enum || [];
  // Namen mit vorgeschlagener Art aus den Feldern der Sportstätte (auch neuer Sportstätten
  // eines Komplexes bzw. Stützpunkts), des Stützpunkts oder der Organisation
  function orgNamen(v) {
    const out = [];
    const ausStaette = (st, typ) => {
      for (const f of FELDER) {
        if (f.p.widget === "organisation") out.push([hole(st, f.pfad), typ ? typ(f) : hole(st, f.pfad + "_typ")]);
        if (f.p.widget === "organisationen") for (const n of hole(st, f.pfad) || []) out.push([n, ""]);
      }
    };
    if (v.art === "neu" || v.art === "aenderung") ausStaette(v.sportstaette);
    if (v.art === "stuetzpunkt") {
      for (const f of SP_FELDER) if (f.p.widget === "organisation") out.push([F(f.pfad).value, ""]);
    }
    if (v.art === "organisation" && !v.loeschen) {
      for (const f of ORG_FELDER) if (f.p.widget === "organisation") out.push([F(f.pfad).value, ""]);
    }
    if (!unter && (v.art === "sportkomplex" || v.art === "stuetzpunkt")) {
      const ids = v.art === "sportkomplex" ? koStaetten : spStaetten;
      for (const n of neueStaetten) if (ids.has(n.ref)) ausStaette(n.sportstaette);
    }
    const gesehen = new Map();
    for (const [name, typ] of out) {
      const k = schluesselName(name);
      if (k && !orgVon(name) && !gesehen.has(k)) gesehen.set(k, [String(name).trim(), typ || ""]);
    }
    return gesehen;
  }
  // Ähnliche Einträge im Verzeichnis (wie bei der Prüfung „Fast gleiche Organisationen“)
  function aehnlicheOrgs(name) {
    const k = orgKern(name);
    return ORGANISATIONEN.filter(o => [o.name, ...(o.weitere_namen || [])].some(n => aehnlich(k, orgKern(n)) >= PRUEFUNG().aehnlich)).slice(0, 4);
  }
  let neueOrgsZuletzt = "";
  function zeigeNeueOrgs(v) {
    const namen = orgNamen(v), teil = el.querySelector("#v-teil-neue-orgs");
    for (const [k, [name, typ]] of namen) {
      if (!neueOrgs.has(k)) neueOrgs.set(k, { name, eintragen: true, typ: ORG_TYPEN.includes(typ) ? typ : "", website: "", geprueft: false });
    }
    teil.hidden = !namen.size;
    const schluessel = [...namen.keys()].join("|");
    if (schluessel === neueOrgsZuletzt) return;  // sonst verlöre die Eingabe den Fokus
    neueOrgsZuletzt = schluessel;
    el.querySelector("#v-neue-orgs").innerHTML = [...namen.keys()].map(k => {
      const o = neueOrgs.get(k), aehnlich = aehnlicheOrgs(o.name);
      return `<div class="neue-org" data-k="${esc(k)}"><label><input type="checkbox" data-no="eintragen"${o.eintragen ? " checked" : ""}>
        <b>${esc(o.name)}</b> eintragen</label>
        <label class="feld klein"><span>Art</span><select data-no="typ"><option value="">nicht bekannt</option>`
        + ORG_TYPEN.map(t => `<option${t === o.typ ? " selected" : ""}>${esc(t)}</option>`).join("") + `</select></label>
        <label class="feld"><span>Webseite</span><input data-no="website" type="url" value="${esc(o.website)}" placeholder="https://"></label>`
        + (aehnlich.length ? `<div class="warnung"><b>Mögliche Doppelung</b> – steht die Organisation schon im Verzeichnis?<ul>`
          + aehnlich.map(x => `<li><b>${esc(x.name)}</b> <span class="q">${esc(x.typ || "ohne Art")}</span> · `
            + `<a href="#" data-org-statt="${esc(x.name)}">stattdessen diese</a></li>`).join("")
          + `</ul><label class="bestaetigen"><input type="checkbox" data-no="geprueft"${o.geprueft ? " checked" : ""}>
            Ich habe geprüft: Es ist eine andere Organisation.</label></div>` : "") + `</div>`;
    }).join("");
  }
  // Name in allen Feldern des Vorschlags ersetzen (Auswahl „stattdessen diese“)
  function ersetzeOrg(alt, neuName) {
    const k = schluesselName(alt);
    for (const f of [...FELDER, ...SP_FELDER, ...ORG_FELDER]) {
      if (f.p.widget === "organisation" && F(f.pfad) && schluesselName(F(f.pfad).value) === k) F(f.pfad).value = neuName;
      if (f.p.widget === "organisationen" && chips[f.pfad]) {
        chips[f.pfad] = new Set([...chips[f.pfad]].map(n => schluesselName(n) === k ? neuName : n));
        zeigeChips(f.pfad);
      }
    }
    for (const n of neueStaetten) for (const f of FELDER) {
      if (f.p.widget === "organisation" && schluesselName(hole(n.sportstaette, f.pfad)) === k) setze(n.sportstaette, f.pfad, neuName);
      if (f.p.widget === "organisationen" && hole(n.sportstaette, f.pfad)) {
        setze(n.sportstaette, f.pfad, hole(n.sportstaette, f.pfad).map(x => schluesselName(x) === k ? neuName : x));
      }
    }
    neueOrgsZuletzt = "";
    zeigeArten(); planePruefung();
  }
  function orgDublettenFehler(v) {
    const fehler = [];
    for (const k of orgNamen(v).keys()) {
      const o = neueOrgs.get(k);
      if (o && o.eintragen && !o.geprueft && aehnlicheOrgs(o.name).length) {
        fehler.push(`Mögliche Doppelung bei der Organisation „${o.name}“ prüfen und bestätigen, dass es eine andere ist`);
      }
    }
    return fehler;
  }
  // → [Organisation] für neue_organisationen; Fehler kommen nach `fehler`
  function neueOrgDaten(v, fehler) {
    const out = [];
    for (const k of orgNamen(v).keys()) {
      const o = neueOrgs.get(k);
      if (!o || !o.eintragen) continue;
      const org = ohneLeere({ name: o.name, typ: o.typ, website: o.website.trim() });
      for (const f of ORG_FELDER) if (f.k in org) fehler.push(...regelFehler(f, org[f.k], `Neue Organisation „${o.name}“: ${f.p.title}`));
      out.push(org);
    }
    fehler.push(...orgDublettenFehler(v));
    return out;
  }

