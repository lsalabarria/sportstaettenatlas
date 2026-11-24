// vorschlag/90_pruefung.js: Prüfungen: Regeln, Doppelungen, Änderungen anzeigen.
// Teil des Rumpfs von ansichtVorschlag – nur zusammen mit den anderen Teilen gültig
// (app/__init__.py setzt vorschlag/*.js der Reihe nach zu app/vorschlag.js zusammen).
  // --- Prüfungen ---
  function planePruefung() { clearTimeout(pruefen); pruefen = setTimeout(pruefe, 250); }
  function pruefe() {
    if (!form) return;
    const v = werte();
    zeigeNeueOrgs(v);
    if (["organisation", "sportkomplex", "stuetzpunkt"].includes(v.art)) return;
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
      const P = PRUEFUNG();
      if (d !== null && d <= P.nah_m) { g.push(`nur ${Math.round(d)} m entfernt`); punkte += 3; }
      else if (d !== null && d <= P.kategorie_nah_m && gleicheKat) { g.push(`gleiche Kategorie, ${Math.round(d)} m entfernt`); punkte += 2; }
      const nahGenug = d === null ? (a.ort && normName(a.ort) === normName(e.p.ort)) || (a.plz && a.plz === e.p.plz) : d <= P.name_nah_m;
      if (sim >= P.aehnlich && nahGenug) { g.push(sim >= P.gleicher_name ? "gleicher Name" : "sehr ähnlicher Name"); punkte += 2; }
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
    const a = anlagenAenderung(v.anlagenliste);
    if (a.length) out.push(["anlagen", "", a.join("\n")]);
    if (v.neuer_sportkomplex) out.push(["neuer_sportkomplex", "", komplexText(v)]);
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
    return [...new Set(fehler)];
  }
  // Der Vorschlag nach dem Modell „Vorschlag“ (modell/)
  // Neu: alle Anlagen; beim Ändern nur neue und geänderte (die übrigen bleiben, wie sie sind).
  // Ändern sich nur Anlagen, geht der Vorschlag ohne die Angaben der Sportstätte (art anlagen).
  function vorschlagDaten(v, geaendert, geprueft) {
    const nurAnlagen = v.art === "aenderung" && !geaendert.length && !v.neuer_sportkomplex;
    const d = { version: 1, art: nurAnlagen ? "anlagen" : v.art };
    if (original) d.sportstaette_id = original.p.id;
    if (!nurAnlagen) d.sportstaette = ohneLeere(v.sportstaette);
    const liste = v.anlagenliste.filter(a => !a.entfernt && a.typ && (v.art === "neu" || !a.id || anlageGeaendert(a)));
    const weg = v.anlagenliste.filter(a => a.entfernt && a.id).map(a => a.id);
    if (v.art === "neu" || liste.length || weg.length) {
      d.anlagen = liste.flatMap(a => Array.from({ length: a.id ? 1 : a.n }, () => anlageModell(a)));
    }
    if (weg.length) d.entfernte_anlagen = weg;
    if (v.neuer_sportkomplex) { d.neuer_sportkomplex = v.neuer_sportkomplex; d.sportstaetten = [...nkStaetten]; }
    if (geaendert.length) d.geaendert = geaendert;
    if (ars) d.gemeinde = ars;
    if (geprueft.length) d.dubletten_geprueft = geprueft;
    return d;
  }

