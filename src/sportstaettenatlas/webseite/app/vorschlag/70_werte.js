// vorschlag/70_werte.js: Werte lesen und setzen; einen Vorschlag beginnen.
// Teil des Rumpfs von ansichtVorschlag – nur zusammen mit den anderen Teilen gültig
// (app/__init__.py setzt vorschlag/*.js der Reihe nach zu app/vorschlag.js zusammen).
  // --- Werte lesen und setzen (Sportstätte verschachtelt wie im Modell) ---
  function leseFeld(f) {
    if (f.p.widget === "sportkomplex" && F(f.pfad).value === NEUER_KOMPLEX) return null;
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
      neuer_sportkomplex: nkWerte(),
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
    nkStaetten = new Set();
    for (const f of KO_FELDER) F("nk." + f.k).value = "";
    zeigeNkStaetten();
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
    const was = F("art").value === "anlagen" ? "die Sportanlagen von" : "die Angaben und Sportanlagen von";
    g.innerHTML = original && !["organisation", "sportkomplex", "stuetzpunkt"].includes(F("art").value) ? `<div class="chip">Sie ändern ${was}: <b>${esc(original.p.name || original.kat)}</b> `
      + `<span class="q">${esc(verbinde([original.p.kategorie, original.p.adresse]))}</span>`
      + ` <button type="button">andere wählen</button></div>` : "";
    const b = g.querySelector("button");
    if (b) b.addEventListener("click", () => { original = null; zeigeGewaehlt();
      el.querySelector("#v-auswahl").hidden = false; el.querySelector("#v-suche").focus(); planePruefung(); });
    el.querySelector("#v-auswahl").hidden = !(["aenderung", "anlagen"].includes(F("art").value) && !original);
  }
  // Formular neu füllen: für eine neue Sportstätte (eintrag = null) oder eine vorhandene
  function beginne(art, eintrag, vorgabe) {
    original = eintrag;
    form.reset();
    F("art").value = art;
    fuelle(vorgabe);
    zeigeTeile();
    zeigeGewaehlt();
    el.querySelector("#v-ausgabe").innerHTML = "";
    el.querySelector("#v-fehler").hidden = true;
  }
  function neu(vorgabe = {}) {
    neueStaetten = []; neueOrgs.clear(); unter = null;
    beginne("neu", null, vorgabe);
  }
  function bearbeite(id, art = "aenderung") {
    const e = NACH_ID.get(id);
    if (!e) return;
    if (vkarte) vkarte.closePopup();
    beginne("aenderung", e, ausEintrag(e));
    if (art === "anlagen") el.querySelector("#v-teil-anlagen").scrollIntoView({ block: "start" });
  }

