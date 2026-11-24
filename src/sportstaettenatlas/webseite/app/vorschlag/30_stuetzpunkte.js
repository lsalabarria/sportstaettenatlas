// vorschlag/30_stuetzpunkte.js: Stützpunkte.
// Teil des Rumpfs von ansichtVorschlag – nur zusammen mit den anderen Teilen gültig
// (app/__init__.py setzt vorschlag/*.js der Reihe nach zu app/vorschlag.js zusammen).
  // --- Stützpunkte ---
  function waehleStuetzpunkt(id, vorbelegt = []) {
    spOriginal = id ? STUETZPUNKTE.get(id) || null : null;
    for (const f of SP_FELDER) {
      const w = spOriginal ? spOriginal[f.k] : null;
      if (f.p.widget === "chips") { chips[f.pfad] = new Set(w || []); zeigeChips(f.pfad); continue; }
      F(f.pfad).value = leer(w) ? "" : w;
    }
    spStaetten = new Set(spOriginal ? spOriginal.sportstaetten || [] : vorbelegt);
    neueStaetten = neueStaetten.filter(n => n.ziel !== "stuetzpunkt");
    spKomplexe = new Set(spOriginal ? spOriginal.sportkomplexe || [] : []);
    if (F("stp-loeschen")) F("stp-loeschen").checked = false;
    const g = el.querySelector("#v-stp-gewaehlt");
    g.innerHTML = spOriginal ? `<div class="chip">Sie ändern: <b>${esc(spOriginal.name)}</b> `
      + `<button type="button">stattdessen einen neuen</button></div>` : "";
    const b = g.querySelector("button");
    if (b) b.addEventListener("click", () => { waehleStuetzpunkt(null); zeigeTeile(); });
    zeigeSpStaetten();
  }
  const neuChip = (ref, ziel, weg) => `<span class="chip-s neu"><a href="#" data-neu-bearbeiten="${esc(ref)}" `
    + `data-ziel="${ziel}" title="Angaben ändern">${esc(staettenName(ref))}</a>`
    + `<button type="button" ${weg}="${esc(ref)}" aria-label="entfernen">×</button></span>`;
  function zeigeSpStaetten() {
    const c = el.querySelector("#v-stp-staetten");
    const imKo = new Set([...spKomplexe].flatMap(k => (SPORTKOMPLEXE.get(k) || { mitglieder: [] }).mitglieder.map(m => m.id)));
    c.innerHTML = [...spKomplexe].map(id => `<span class="chip-s">Sportkomplex ${esc(komplexName(id))}`
      + `<button type="button" data-sp-ko-weg="${esc(id)}" aria-label="entfernen">×</button></span>`).join("")
      + [...spStaetten].map(id => {
        const e = NACH_ID.get(id);
        if (neueStaette(id)) return neuChip(id, "stuetzpunkt", "data-sp-st-weg");
        return `<span class="chip-s">${esc(e ? e.p.name || e.kat : id)}`
          + (imKo.has(id) ? ` <small>(schon über den Sportkomplex)</small>` : "")
          + `<button type="button" data-sp-st-weg="${esc(id)}" aria-label="entfernen">×</button></span>`;
      }).join("") || `<span class="hinweis">noch keine</span>`;
    c.querySelectorAll("[data-sp-ko-weg]").forEach(b => b.addEventListener("click", () => {
      spKomplexe.delete(b.dataset.spKoWeg); zeigeSpStaetten(); }));
    c.querySelectorAll("[data-sp-st-weg]").forEach(b => b.addEventListener("click", () => {
      spStaetten.delete(b.dataset.spStWeg); zeigeSpStaetten(); }));
  }
  function spWerte() {
    const sp = {};
    for (const f of SP_FELDER) {
      const w = f.p.widget === "chips" ? [...chips[f.pfad]] : String(F(f.pfad).value || "").trim();
      if (!leer(w) && !(Array.isArray(w) && !w.length)) sp[f.k] = w;
    }
    if (spStaetten.size) sp.sportstaetten = [...spStaetten];
    if (spKomplexe.size) sp.sportkomplexe = [...spKomplexe];
    return sp;
  }
  function weiterStuetzpunkt(v) {
    const sp = spWerte(), loeschen = !!(F("stp-loeschen") && F("stp-loeschen").checked), fehler = [];
    if (!loeschen) {
      for (const f of SP_FELDER) fehler.push(...regelFehler(f, sp[f.k], f.p.title));
      if (!spStaetten.size && !spKomplexe.size) fehler.push("Sportstätten: mindestens eine Sportstätte oder einen Sportkomplex wählen");
      if (sp.gueltig_ab && sp.gueltig_bis && sp.gueltig_bis < sp.gueltig_ab) fehler.push("Gültig bis: liegt vor „Gültig ab“");
    }
    if (enthaeltEmail(sp)) fehler.push("Bitte keine E-Mail-Adressen eintragen");
    const gleich = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
    const felder = [...SP_FELDER.map(f => f.k), "sportstaetten", "sportkomplexe"];
    const geaendert = spOriginal ? felder.filter(k => !gleich(
      Array.isArray(spOriginal[k]) && !spOriginal[k].length ? undefined : spOriginal[k], sp[k])) : [];
    if (spOriginal && !loeschen && !geaendert.length && !v.anmerkung) {
      fehler.push("Änderung: Angaben oder Sportstätten ändern, löschen wählen oder eine Anmerkung schreiben");
    }
    const daten = { version: 1, art: "stuetzpunkt" };
    if (spOriginal) daten.stuetzpunkt_id = spOriginal.id;
    if (loeschen) daten.loeschen = true;
    else {
      daten.stuetzpunkt = sp;
      if (spOriginal && geaendert.length) daten.geaendert = geaendert;
      const neue = neueStaettenDaten(spStaetten);
      if (neue.length) daten.neue_sportstaetten = neue;
    }
    sende(daten, v, fehler);
  }

