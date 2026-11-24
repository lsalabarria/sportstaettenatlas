// vorschlag/20_anlagen.js: Sportanlagen einer Sportstätte: Liste, Eingabe, Änderungen; welche Teile sichtbar sind.
// Teil des Rumpfs von ansichtVorschlag – nur zusammen mit den anderen Teilen gültig
// (app/__init__.py setzt vorschlag/*.js der Reihe nach zu app/vorschlag.js zusammen).
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
      + ` placeholder="z. B. Großspielfeld"></td>`
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
  const anlageGeaendert = a => ["typ", "bezeichnung", ...ANLAGE_EINGABEN.map(e => e.k)]
    .some(k => (a[k] || "") !== ((a.alt || {})[k] || ""));
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
      const felder = ["typ", "bezeichnung", ...ANLAGE_EINGABEN.map(e => e.k)].filter(k => (a[k] || "") !== (alt[k] || ""));  // wie anlageGeaendert
      if (felder.length) {
        out.push(`ändern [${a.id}] ${anlageKurz(alt)}: ` + felder.map(k =>
          `${titel(k)} ${alt[k] || "(leer)"} → ${a[k] || "(leer)"}`).join("; "));
      }
    }
    return out;
  }
  // Teile des Formulars je nach Art des Vorschlags
  function zeigeTeile() {
    const art = F("art").value, eigen = ["organisation", "sportkomplex", "stuetzpunkt"].includes(art);
    el.querySelector("#v-teil-staette").hidden = art === "anlagen" || eigen;
    el.querySelector("#v-teil-anlagen").hidden = eigen;
    el.querySelector("#v-art").hidden = !!unter;
    el.querySelector("#v-leeren").hidden = !!unter;
    el.querySelector(".knopf-gross").textContent = unter ? "Sportstätte übernehmen" : "Weiter zu LimeSurvey →";
    const ub = el.querySelector("#v-unter");
    ub.hidden = !unter;
    if (unter) ub.querySelector("b").textContent = unter.ziel === "sportkomplex" ? "den Sportkomplex" : "den Stützpunkt";
    el.querySelector("#v-teil-org").hidden = art !== "organisation";
    el.querySelector("#v-teil-komplex").hidden = art !== "sportkomplex";
    el.querySelector("#v-teil-stp").hidden = art !== "stuetzpunkt";
    el.querySelector("#v-stp-weg").hidden = !spOriginal;
    el.querySelector(".vorschlag aside").hidden = eigen;
    el.querySelector("#v-org-weg").hidden = !(orgOriginal && orgOriginal.imVerzeichnis);
    el.querySelector("#v-ko-weg").hidden = !koOriginal;
  }

