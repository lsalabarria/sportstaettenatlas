// vorschlag/40_sportkomplexe.js: Sportkomplexe; Auswahl der Art des Vorschlags.
// Teil des Rumpfs von ansichtVorschlag – nur zusammen mit den anderen Teilen gültig
// (app/__init__.py setzt vorschlag/*.js der Reihe nach zu app/vorschlag.js zusammen).
  // --- Sportkomplexe ---
  // Komplex zum Ändern wählen (ID) oder null für einen neuen, dann mit den Sportstätten `vorbelegt`
  function waehleKomplex(id, vorbelegt = []) {
    koOriginal = id ? SPORTKOMPLEXE.get(id) || null : null;
    for (const f of KO_FELDER) { const w = koOriginal ? hole(koOriginal, f.k) : ""; F(f.pfad).value = leer(w) ? "" : w; }
    koStaetten = new Set(koOriginal ? koOriginal.mitglieder.map(m => m.id) : vorbelegt);
    neueStaetten = neueStaetten.filter(n => n.ziel !== "sportkomplex");
    if (F("ko-loeschen")) F("ko-loeschen").checked = false;
    const g = el.querySelector("#v-ko-gewaehlt");
    g.innerHTML = koOriginal ? `<div class="chip">Sie ändern: <b>${esc(koOriginal.name)}</b> `
      + `<button type="button">stattdessen einen neuen</button></div>` : "";
    const b = g.querySelector("button");
    if (b) b.addEventListener("click", () => { waehleKomplex(null); zeigeTeile(); });
    zeigeKoStaetten();
  }
  function zeigeKoStaetten() {
    const c = el.querySelector("#v-ko-staetten");
    c.innerHTML = [...koStaetten].map(id => {
      const e = NACH_ID.get(id), anders = e && e.p.sportkomplex && (!koOriginal || e.p.sportkomplex !== koOriginal.id);
      if (neueStaette(id)) return neuChip(id, "sportkomplex", "data-ko-weg");
      return `<span class="chip-s">${esc(e ? e.p.name || e.kat : id)}`
        + (anders ? ` <small>(bisher in ${esc(komplexName(e.p.sportkomplex))})</small>` : "")
        + `<button type="button" data-ko-weg="${esc(id)}" aria-label="entfernen">×</button></span>`;
    }).join("") || `<span class="hinweis">noch keine</span>`;
    c.querySelectorAll("[data-ko-weg]").forEach(b => b.addEventListener("click", () => {
      koStaetten.delete(b.dataset.koWeg); zeigeKoStaetten(); }));
  }
  function koWerte() {
    const k = {};
    for (const f of KO_FELDER) { const x = String(F(f.pfad).value || "").trim(); if (x) setze(k, f.k, x); }
    return k;
  }
  function weiterKomplex(v) {
    const k = koWerte(), loeschen = !!(F("ko-loeschen") && F("ko-loeschen").checked), fehler = [];
    if (!loeschen) {
      for (const f of KO_FELDER) fehler.push(...regelFehler(f, hole(k, f.k), f.p.title));
      if (koStaetten.size < 2) fehler.push("Sportstätten: mindestens zwei – ein Sportkomplex fasst mehrere zusammen");
    }
    if (enthaeltEmail(k)) fehler.push("Bitte keine E-Mail-Adressen eintragen");
    const geaendert = koOriginal ? KO_FELDER.map(f => f.k).filter(x => (hole(koOriginal, x) || "") !== (hole(k, x) || "")) : [];
    const vorher = new Set(koOriginal ? koOriginal.mitglieder.map(m => m.id) : []);
    const gleich = vorher.size === koStaetten.size && [...koStaetten].every(id => vorher.has(id));
    if (koOriginal && !loeschen && !geaendert.length && gleich && !v.anmerkung) {
      fehler.push("Änderung: Name, Adresse oder Sportstätten ändern, auflösen wählen oder eine Anmerkung schreiben");
    }
    const daten = { version: 1, art: "sportkomplex" };
    if (koOriginal) daten.sportkomplex_id = koOriginal.id;
    if (loeschen) daten.loeschen = true;
    else {
      daten.sportkomplex = k;
      daten.sportstaetten = [...koStaetten];
      const neue = neueStaettenDaten(koStaetten);
      if (neue.length) daten.neue_sportstaetten = neue;
      if (koOriginal && geaendert.length) daten.geaendert = geaendert;
    }
    sende(daten, v, fehler);
  }
  // Eigentümer/Betreiber: steht die Organisation im Verzeichnis, ihre Art übernehmen (wenn
  // noch keine gewählt ist); dahinter steht, ob sie im Verzeichnis ist (geschätzt wird nicht)
  function zeigeArten() {
    for (const f of FELDER.filter(x => x.p.widget === "organisation")) {
      const name = F(f.pfad).value, o = orgVon(name), s = el.querySelector(`[data-art="${f.pfad}"]`);
      const typ = F(f.pfad + "_typ");
      // die Art aus dem Verzeichnis folgt dem Namen, solange niemand sie selbst gewählt hat
      const vonVerzeichnis = typ && typ.dataset.vonOrg && typ.value === typ.dataset.vonTyp;
      if (typ && (vonVerzeichnis || !typ.value) && typ.dataset.vonOrg !== name) {
        typ.value = o && o.typ ? o.typ : vonVerzeichnis ? "" : typ.value;
        typ.dataset.vonOrg = o && o.typ ? name : "";
        typ.dataset.vonTyp = typ.value;
      }
      const a = !name.trim() ? "" : o ? "im Verzeichnis" + (o.typ ? "" : ", ohne Art") : "nicht im Verzeichnis";
      s.textContent = a; s.hidden = !a;
    }
  }

