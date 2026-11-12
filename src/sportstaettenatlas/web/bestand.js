// Ansichten zum Datenbestand des Atlas (daten/): Karte, Liste, Übersicht.

// Kategorien des Atlas: feste Farben, damit eine Kategorie immer dieselbe Farbe behält;
// die seltenen teilen sich Grau („weitere“).
const KATEGORIE_FARBEN = {
  "Sportplatz": "#2a78d6",
  "Sporthalle": "#eb6834",
  "Tennissportstätte": "#1baf7a",
  "Öffentlicher Sport- und Bewegungsraum": "#eda100",
  "Reitsportstätte": "#e87ba4",
  "Schwimmsportstätte": "#008300",
  "Schießsportstätte": "#6250d6",
  "Fitnessstudio": "#e34948",
};
const WEITERE = "#8a8984";

// ---------- Ansicht „Karte“: der Datenbestand -------------------------------------------
const ARTEN = ["Verein", "Kommune", "sonstige", "ohne Angabe"];
function artVon(p, rolle = "betreiber") { return p[rolle + "_art"] || "ohne Angabe"; }
function katFarbe(k) { return KATEGORIE_FARBEN[k] || WEITERE; }
function schluesselName(s) { return String(s || "").trim().replace(/\s+/g, " ").toLowerCase(); }

function ansichtBestand(fc) {
  const ebene = L.layerGroup();
  const eintraege = [];
  const katZahl = {}, artZahl = {}, spZahl = {};
  for (const f of fc.features) {
    const p = f.properties, [lon, lat] = f.geometry.coordinates;
    const kat = p.kategorie || "ohne Kategorie";
    katZahl[kat] = (katZahl[kat] || 0) + 1;
    const art = artVon(p);
    artZahl[art] = (artZahl[art] || 0) + 1;
    for (const s of p.sportarten || []) spZahl[s] = (spZahl[s] || 0) + 1;
    const e = { p, lat, lon, kat, art, an: false,
      sp: new Set(p.sportarten || []), betreiber: schluesselName(p.betreiber),
      eigentuemer: schluesselName(p.eigentuemer) };
    e.layer = info(L.circleMarker([lat, lon], { radius: 4, weight: 1, color: "#fff",
      fillColor: katFarbe(kat), fillOpacity: 0.95 }), () => tipBestand(e));
    eintraege.push(e);
  }
  const katAn = {}, artAn = {};
  for (const k of Object.keys(katZahl)) katAn[k] = true;
  for (const a of ARTEN) artAn[a] = true;
  const sportWahl = new Set();
  let betreiberWahl = null;  // { rolle, schluessel, name }

  function passt(e) {
    if (!katAn[e.kat] || !artAn[e.art] || !imGebiet(e.p.ars)) return false;
    if (betreiberWahl && e[betreiberWahl.rolle] !== betreiberWahl.schluessel) return false;
    if (sportWahl.size) {
      let ok = false;
      for (const s of sportWahl) if (e.sp.has(s)) { ok = true; break; }
      if (!ok) return false;
    }
    return true;
  }
  let zahlEl = null;
  function aktualisiere() {
    let n = 0;
    for (const e of eintraege) {
      const soll = passt(e);
      if (soll) n++;
      if (soll !== e.an) { e.an = soll; if (soll) ebene.addLayer(e.layer); else ebene.removeLayer(e.layer); }
    }
    if (zahlEl) zahlEl.textContent = n === eintraege.length ? `${zahl(n)} Sportstätten`
      : `${zahl(n)} von ${zahl(eintraege.length)} Sportstätten`;
    return n;
  }

  // Filter-Panel
  const panel = L.control({ position: "topright" });
  let panelEl = null;
  panel.onAdd = () => {
    const div = panelEl = L.DomUtil.create("div", "panel filter");
    L.DomEvent.disableClickPropagation(div);
    L.DomEvent.disableScrollPropagation(div);
    const kats = Object.keys(katZahl).sort((a, b) => katZahl[b] - katZahl[a]);
    const sps = Object.keys(spZahl).sort((a, b) => a.localeCompare(b, "de"));
    div.innerHTML = `<h1 id="b-zahl"></h1><div id="b-chip"></div>`
      + `<details open><summary>Kategorie</summary><div class="knoepfe">`
      + `<button type="button" data-alle="kat">alle</button><button type="button" data-keine="kat">keine</button></div>`
      + kats.map(k => `<label><input type="checkbox" data-k="${esc(k)}" checked>`
        + `<span class="swatch" style="background:${katFarbe(k)}"></span>${esc(k)}`
        + `<span class="n">${zahl(katZahl[k])}</span></label>`).join("") + `</details>`
      + `<details open><summary>Betreiber</summary>`
      + ARTEN.filter(a => artZahl[a]).map(a => `<label><input type="checkbox" data-a="${a}" checked>`
        + `${a === "Verein" ? "Vereine" : a === "Kommune" ? "Kommunen" : a}`
        + `<span class="n">${zahl(artZahl[a])}</span></label>`).join("")
      + `<div class="hinweis">Art aus dem Namen geschätzt (z. B. „e.V.“, „Ortsgemeinde“)</div></details>`
      + (sps.length ? `<details><summary>Sportarten <span id="b-sp-n"></span></summary>`
        + `<input type="search" placeholder="Sportart suchen" aria-label="Sportart suchen">`
        + `<div class="sp-liste">` + sps.map(s => `<label data-text="${esc(s.toLowerCase())}">`
          + `<input type="checkbox" data-s="${esc(s)}">${esc(s)}<span class="n">${zahl(spZahl[s])}</span></label>`).join("")
        + `</div><div class="knoepfe"><button type="button" data-keine="sp">Auswahl aufheben</button></div>`
        + `<div class="hinweis">Ohne Auswahl: alle. Mit Auswahl: Sportstätten mit mindestens einer davon.</div></details>`
        : "")
      + `<div class="hinweis">Klick auf einen Punkt: Angaben bleiben stehen · Rechtsklick: Koordinaten</div>`;
    zahlEl = div.querySelector("#b-zahl");
    div.querySelectorAll("input[data-k]").forEach(cb => cb.addEventListener("change", () => {
      katAn[cb.dataset.k] = cb.checked; aktualisiere(); }));
    div.querySelectorAll("input[data-a]").forEach(cb => cb.addEventListener("change", () => {
      artAn[cb.dataset.a] = cb.checked; aktualisiere(); }));
    const spN = div.querySelector("#b-sp-n");
    const spZeige = () => { if (spN) spN.textContent = sportWahl.size ? `(${sportWahl.size})` : ""; };
    div.querySelectorAll("input[data-s]").forEach(cb => cb.addEventListener("change", () => {
      if (cb.checked) sportWahl.add(cb.dataset.s); else sportWahl.delete(cb.dataset.s);
      spZeige(); aktualisiere(); }));
    div.querySelectorAll("[data-alle],[data-keine]").forEach(b => b.addEventListener("click", () => {
      const an = !!b.dataset.alle, was = b.dataset.alle || b.dataset.keine;
      if (was === "kat") {
        div.querySelectorAll("input[data-k]").forEach(cb => { cb.checked = an; katAn[cb.dataset.k] = an; });
      } else {
        div.querySelectorAll("input[data-s]").forEach(cb => { cb.checked = false; });
        sportWahl.clear(); spZeige();
      }
      aktualisiere();
    }));
    const suchSp = div.querySelector(".sp-liste") && div.querySelector("details input[type=search]");
    if (suchSp) suchSp.addEventListener("input", () => {
      const q = suchSp.value.trim().toLowerCase();
      div.querySelectorAll(".sp-liste label").forEach(l => { l.hidden = q && !l.dataset.text.includes(q); });
    });
    zeigeChip();
    aktualisiere();
    return div;
  };
  function zeigeChip() {
    const el = panelEl && panelEl.querySelector("#b-chip");
    if (!el) return;
    el.innerHTML = betreiberWahl ? `<div class="chip">${betreiberWahl.rolle === "betreiber"
      ? "Betreiber" : "Eigentümer"}: <b>${esc(betreiberWahl.name)}</b> `
      + `<button type="button" title="Filter aufheben">× aufheben</button></div>` : "";
    const b = el.querySelector("button");
    if (b) b.addEventListener("click", () => { betreiberWahl = null; zeigeChip(); aktualisiere(); });
  }

  // Ein gesuchter Eintrag soll sichtbar werden, auch wenn Filter ihn gerade ausblenden
  function filterZurueck() {
    betreiberWahl = null; sportWahl.clear();
    for (const k in katAn) katAn[k] = true;
    for (const a in artAn) artAn[a] = true;
    if (panelEl) {
      panelEl.querySelectorAll("input[data-k],input[data-a]").forEach(c => { c.checked = true; });
      panelEl.querySelectorAll("input[data-s]").forEach(c => { c.checked = false; });
      const spN = panelEl.querySelector("#b-sp-n");
      if (spN) spN.textContent = "";
    }
    zeigeChip();
  }
  function oeffne(e) {
    if (!imGebiet(e.p.ars)) setzeGebiet(null, false);
    if (!passt(e)) filterZurueck();
    aktualisiere();
    if (e.an) e.layer.openPopup();
  }

  function tipBestand(e) {
    const p = e.p, z = [];
    const zeile = (l, v) => { if (!leer(v)) z.push(`<tr><td>${l}</td><td>${v}</td></tr>`); };
    const art = a => a ? `<span class="art">${esc(a)}</span>` : "";
    zeile("Kategorie", leer(p.kategorie) ? "" : `<span class="swatch" style="display:inline-block;`
      + `background:${katFarbe(e.kat)};vertical-align:-1px"></span> ${esc(p.kategorie)}`);
    zeile("Adresse", leer(p.adresse) ? "" : esc(p.adresse));
    zeile("Gebiet", esc(gemeindeName(p.ars)));
    zeile("Sportarten", leer(p.sportarten) ? "" : esc(p.sportarten.join(", ")));
    if (!leer(p.anlagen)) {
      const n = {};
      for (const a of p.anlagen) n[a] = (n[a] || 0) + 1;
      zeile("Anlagen", Object.entries(n).map(([a, k]) => (k > 1 ? `${k}× ` : "") + esc(a)).join("<br>"));
    }
    zeile("Betreiber", leer(p.betreiber) ? "" : esc(p.betreiber) + art(p.betreiber_art));
    zeile("Eigentümer", leer(p.eigentuemer) ? "" : esc(p.eigentuemer) + art(p.eigentuemer_art));
    zeile("Öffentlich", esc(p.oeffentlicher_zugang || ""));
    zeile("Schulsport", esc(p.schulsport || ""));
    zeile("Zuschauer", leer(p.zuschauerplaetze) ? "" : zahl(p.zuschauerplaetze));
    zeile("Betrieb", esc(p.betriebsstatus || ""));
    zeile("Website", leer(p.website) ? "" : `<a href="${esc(url(p.website))}" target="_blank" `
      + `rel="noopener">${esc(p.website)}</a>`);
    zeile("ID", leer(p.id) ? "" : `<span class="koord">${esc(p.id)}</span>`);
    return `<div class="tip"><h3>${esc(p.name || p.kategorie || "Sportstätte")}</h3>`
      + `<table class="meta">${z.join("")}${koord(e.lat, e.lon)}${aendernLink(p.id)}</table></div>`;
  }

  const such = eintraege.map(e => ({
    titel: e.p.name || e.kat, sub: [e.p.kategorie, e.p.adresse, e.p.betreiber].filter(v => !leer(v)).join(" · "),
    text: [e.p.name, e.p.adresse, e.p.kategorie, e.p.betreiber, e.p.eigentuemer, e.p.id,
      ...(e.p.sportarten || [])].filter(v => !leer(v)).join(" ").toLowerCase(),
    grenzen: () => L.latLngBounds([[e.lat, e.lon], [e.lat, e.lon]]),
    oeffne: () => oeffne(e),
    ars: e.p.ars,
  }));
  let erstmals = true;
  return {
    titel: "Karte",
    eintraege,
    starte() {},
    zeigen() {
      ebene.addTo(karte); panel.addTo(karte); aktualisiere();
      if (erstmals && !GEBIET && eintraege.length) {
        karte.fitBounds(L.latLngBounds(eintraege.map(e => [e.lat, e.lon])), { padding: [20, 20] });
      }
      erstmals = false;
    },
    verbergen() { karte.removeLayer(ebene); panel.remove(); },
    gebietGeaendert() { aktualisiere(); },
    suchindex: () => such,
    zeigeBetreiber(rolle, schluessel, name) {
      betreiberWahl = { rolle, schluessel, name };
      zeige("bestand").then(() => {
        zeigeChip();
        aktualisiere();
        const pkte = eintraege.filter(e => e.an).map(e => [e.lat, e.lon]);
        if (pkte.length) karte.fitBounds(L.latLngBounds(pkte).pad(0.15), { maxZoom: 16 });
      });
    },
    zeigeEintrag(e) {
      zeige("bestand").then(() => {
        karte.setView([e.lat, e.lon], Math.max(karte.getZoom(), 16));
        oeffne(e);
      });
    },
  };
}

// ---------- Ansicht „Liste“: Vereine und Kommunen als Betreiber -------------------------
function ansichtListe(bestand) {
  const el = document.getElementById("seite-liste");
  let art = "Verein", rolle = "betreiber", filterText = "", sortierung = { feld: "n", ab: true };
  const offen = new Set();
  function gruppen() {
    const g = new Map();
    for (const e of bestand.eintraege) {
      if (!imGebiet(e.p.ars) || artVon(e.p, rolle) !== art) continue;
      const s = e[rolle];
      if (!s) continue;
      let x = g.get(s);
      if (!x) g.set(s, x = { s, namen: {}, liste: [], orte: {}, kats: {} });
      const name = e.p[rolle].trim().replace(/\s+/g, " ");
      x.namen[name] = (x.namen[name] || 0) + 1;
      x.liste.push(e);
      if (e.p.ort) x.orte[e.p.ort] = (x.orte[e.p.ort] || 0) + 1;
      x.kats[e.kat] = (x.kats[e.kat] || 0) + 1;
    }
    const top = (o, n) => Object.entries(o).sort((a, b) => b[1] - a[1]).slice(0, n).map(x => x[0]);
    return [...g.values()].map(x => ({ ...x, name: top(x.namen, 1)[0], n: x.liste.length,
      ort: top(x.orte, 3).join(", ") + (Object.keys(x.orte).length > 3 ? " …" : ""),
      kat: top(x.kats, 3).join(", ") + (Object.keys(x.kats).length > 3 ? " …" : "") }));
  }
  function zaehle() {
    const z = {};
    for (const e of bestand.eintraege) if (imGebiet(e.p.ars)) {
      const a = artVon(e.p, rolle); if (e[rolle]) (z[a] ??= new Set()).add(e[rolle]);
    }
    return z;
  }
  function zeichne() {
    const z = zaehle();
    let liste = gruppen();
    if (filterText) liste = liste.filter(x => x.s.includes(filterText) || x.ort.toLowerCase().includes(filterText));
    const { feld, ab } = sortierung;
    liste.sort((a, b) => (feld === "n" ? a.n - b.n : String(a[feld]).localeCompare(String(b[feld]), "de"))
      * (ab ? -1 : 1) || a.name.localeCompare(b.name, "de"));
    const reiter = ["Verein", "Kommune", "sonstige"].map(a => `<button type="button" data-art="${a}" `
      + `aria-pressed="${a === art}">${a === "Verein" ? "Vereine" : a === "Kommune" ? "Kommunen" : "sonstige"}`
      + ` (${zahl(z[a] ? z[a].size : 0)})</button>`).join("");
    const pfeil = f => sortierung.feld === f ? (sortierung.ab ? " ▼" : " ▲") : "";
    const zeilen = liste.map(x => {
      const auf = offen.has(x.s);
      let h = `<tr class="zeile${auf ? " offen" : ""}" data-s="${esc(x.s)}"><td>${auf ? "▾" : "▸"} ${esc(x.name)}</td>`
        + `<td class="zahl">${zahl(x.n)}</td><td class="klein">${esc(x.ort)}</td><td class="klein">${esc(x.kat)}</td></tr>`;
      if (auf) {
        h += `<tr class="details"><td colspan="4"><button type="button" class="knopf2" data-karte="${esc(x.s)}">`
          + `Alle ${zahl(x.n)} auf der Karte zeigen</button><table class="tabelle">`
          + x.liste.slice().sort((a, b) => (a.p.ort || "").localeCompare(b.p.ort || "", "de")).map(e =>
            `<tr><td><a data-i="${bestand.eintraege.indexOf(e)}">${esc(e.p.name || e.kat)}</a></td>`
            + `<td class="klein">${esc(e.p.kategorie || "")}</td><td class="klein">${esc(e.p.adresse || "")}</td></tr>`).join("")
          + `</table></td></tr>`;
      }
      return h;
    }).join("");
    el.innerHTML = `<div class="inhalt"><h2>Betreiber und Eigentümer</h2>`
      + `<p class="unter">${esc(gebietName())} · Art aus dem Namen geschätzt („e.V.“, „TuS“, „Ortsgemeinde“, „Stadt“ …)</p>`
      + `<div class="reiter">${reiter}<select aria-label="Rolle"><option value="betreiber"${rolle === "betreiber" ? " selected" : ""}>als Betreiber</option>`
      + `<option value="eigentuemer"${rolle === "eigentuemer" ? " selected" : ""}>als Eigentümer</option></select>`
      + `<input type="search" placeholder="Name oder Ort filtern" value="${esc(filterText)}" aria-label="Filter"></div>`
      + `<table class="tabelle"><thead><tr><th data-sort="name">Name${pfeil("name")}</th>`
      + `<th class="zahl" data-sort="n">Sportstätten${pfeil("n")}</th><th data-sort="ort">Orte${pfeil("ort")}</th>`
      + `<th data-sort="kat">Kategorien${pfeil("kat")}</th></tr></thead><tbody>${zeilen
        || `<tr><td colspan="4" class="klein">Keine Einträge.</td></tr>`}</tbody></table></div>`;
    el.querySelectorAll("[data-art]").forEach(b => b.addEventListener("click", () => {
      art = b.dataset.art; offen.clear(); zeichne(); }));
    el.querySelector("select").addEventListener("change", ev => { rolle = ev.target.value; offen.clear(); zeichne(); });
    const feldEl = el.querySelector("input[type=search]");
    feldEl.addEventListener("input", () => {
      filterText = feldEl.value.trim().toLowerCase().replace(/\s+/g, " ");
      const pos = feldEl.selectionStart; zeichne();
      const neu = el.querySelector("input[type=search]"); neu.focus(); neu.setSelectionRange(pos, pos);
    });
    el.querySelectorAll("th[data-sort]").forEach(th => th.addEventListener("click", () => {
      const f = th.dataset.sort;
      sortierung = { feld: f, ab: sortierung.feld === f ? !sortierung.ab : f === "n" };
      zeichne();
    }));
    el.querySelectorAll("tr.zeile").forEach(tr => tr.addEventListener("click", () => {
      const s = tr.dataset.s; if (offen.has(s)) offen.delete(s); else offen.add(s); zeichne(); }));
    el.querySelectorAll("[data-karte]").forEach(b => b.addEventListener("click", () => {
      const x = liste.find(y => y.s === b.dataset.karte);
      bestand.zeigeBetreiber(rolle, x.s, x.name);
    }));
    el.querySelectorAll("a[data-i]").forEach(a => a.addEventListener("click", () =>
      bestand.zeigeEintrag(bestand.eintraege[+a.dataset.i])));
  }
  return {
    titel: "Liste",
    starte() {},
    zeigen() { el.hidden = false; zeichne(); },
    verbergen() { el.hidden = true; },
    gebietGeaendert() { if (!el.hidden) zeichne(); },
  };
}

// ---------- Ansicht „Übersicht“: kleines Dashboard über den Datenbestand ----------------
const FELDER = [
  ["Name", p => !leer(p.name)],
  ["Kategorie", p => !leer(p.kategorie)],
  ["Straße", p => !leer(p.strasse)],
  ["PLZ und Ort", p => !leer(p.plz) && !leer(p.ort)],
  ["Sportarten", p => !leer(p.sportarten)],
  ["Anlagen", p => !leer(p.anlagen)],
  ["Betreiber", p => !leer(p.betreiber)],
  ["Eigentümer", p => !leer(p.eigentuemer)],
  ["Öffentlicher Zugang", p => !leer(p.oeffentlicher_zugang)],
  ["Schulsport", p => !leer(p.schulsport)],
  ["Betriebsstatus", p => !leer(p.betriebsstatus)],
  ["Zuschauerplätze", p => !leer(p.zuschauerplaetze)],
  ["Website", p => !leer(p.website)],
];
function befuellung(liste) {
  if (!liste.length) return 0;
  let summe = 0;
  for (const e of liste) for (const [, test] of FELDER) if (test(e.p)) summe++;
  return summe / (liste.length * FELDER.length);
}
function balken(zeilen, gesamt, prozentual) {
  // zeilen: [label, wert]; Breite relativ zu gesamt (Anteil) bzw. zum größten Wert
  const max = prozentual ? gesamt : Math.max(1, ...zeilen.map(z => z[1]));
  return `<table class="balken">` + zeilen.map(([l, w]) => {
    const breite = Math.max(0, Math.min(100, 100 * w / (max || 1)));
    const text = prozentual ? `${prozent(w, gesamt)} %` : zahl(w);
    const titel = prozentual ? `${zahl(w)} von ${zahl(gesamt)}` : `${zahl(w)} Sportstätten`;
    return `<tr title="${esc(l)}: ${titel}"><td class="l">${esc(l)}</td>`
      + `<td><div class="spur"><div class="fuell" style="width:${breite.toFixed(1)}%"></div></div></td>`
      + `<td class="w">${text}</td></tr>`;
  }).join("") + `</table>`;
}
function ansichtUebersicht(bestand) {
  const el = document.getElementById("seite-uebersicht");
  function zeichne() {
    const liste = bestand.eintraege.filter(e => imGebiet(e.p.ars));
    const n = liste.length;
    const anlagen = liste.reduce((s, e) => s + (e.p.anlagen ? e.p.anlagen.length : 0), 0);
    const sportarten = new Set(liste.flatMap(e => e.p.sportarten || []));
    const betr = { Verein: new Set(), Kommune: new Set() };
    for (const e of liste) if (betr[e.art] && e.betreiber) betr[e.art].add(e.betreiber);
    const zaehl = f => { const z = {}; for (const e of liste) { const k = f(e); z[k] = (z[k] || 0) + 1; } return z; };
    const sortiert = z => Object.entries(z).sort((a, b) => b[1] - a[1]);
    const kachel = (label, wert, zusatz = "") => `<div class="kachel"><div class="label">${label}</div>`
      + `<div class="wert">${wert}</div><div class="zusatz">${zusatz}</div></div>`;
    let h = `<div class="inhalt"><h2>Übersicht: ${esc(gebietName())}</h2>`
      + `<p class="unter">Datenbestand der Karte (Ordner <code>daten/</code>)</p><div class="kacheln">`
      + kachel("Sportstätten", zahl(n))
      + kachel("Sportanlagen", zahl(anlagen), n ? `Ø ${(anlagen / n).toLocaleString("de-DE",
        { maximumFractionDigits: 1 })} je Sportstätte` : "")
      + kachel("Felder befüllt", `${Math.round(100 * befuellung(liste))} %`, `Durchschnitt über ${FELDER.length} Felder`)
      + kachel("Sportarten", zahl(sportarten.size), "verschiedene")
      + kachel("Vereine", zahl(betr.Verein.size), "als Betreiber (aus dem Namen geschätzt)")
      + kachel("Kommunen", zahl(betr.Kommune.size), "als Betreiber (aus dem Namen geschätzt)")
      + `</div>`;
    h += `<div class="spalten"><div><h3>Wie gut sind die Felder befüllt?</h3>`
      + balken(FELDER.map(([l, t]) => [l, liste.filter(e => t(e.p)).length]), n, true) + `</div>`
      + `<div><h3>Sportstätten nach Kategorie</h3>` + balken(sortiert(zaehl(e => e.kat)), n, false)
      + `<h3>Betreiber</h3>` + balken(ARTEN.map(a => [a === "Verein" ? "Vereine" : a === "Kommune"
        ? "Kommunen" : a, liste.filter(e => e.art === a).length]).filter(z => z[1]), n, true);
    h += `</div></div>`;
    // Teilgebiete: Befüllung je Kreis bzw. je Verbandsgemeinde/Gemeinde
    const ebene = !GEBIET ? "kreis" : GEBIET.e === "kreis" ? "vg" : GEBIET.e === "vg" ? "gemeinde" : null;
    const teile = ebene ? GEBIETE.filter(g => g.e === ebene && (!GEBIET || g.s.startsWith(GEBIET.s))) : [];
    if (teile.length > 1) {
      const zeilen = teile.map(g => {
        const l = liste.filter(e => e.p.ars && e.p.ars.startsWith(g.s));
        return { g, n: l.length, b: befuellung(l) };
      }).sort((a, b) => b.n - a.n);
      h += `<h3>Nach ${ebene === "kreis" ? "Kreisen" : ebene === "vg" ? "Verbandsgemeinden" : "Gemeinden"}</h3>`
        + `<table class="tabelle"><thead><tr><th>Gebiet</th><th class="zahl">Sportstätten</th>`
        + `<th style="width:40%">Felder befüllt</th></tr></thead><tbody>` + zeilen.map(z =>
          `<tr class="zeile" data-g="${z.g.s}" title="Gebiet auswählen"><td>${esc(gebietTitel(z.g))}</td>`
          + `<td class="zahl">${zahl(z.n)}</td><td><table class="balken"><tr><td><div class="spur">`
          + `<div class="fuell" style="width:${(100 * z.b).toFixed(1)}%"></div></div></td>`
          + `<td class="w">${z.n ? Math.round(100 * z.b) + " %" : "–"}</td></tr></table></td></tr>`).join("")
        + `</tbody></table>`;
    }
    h += `<p class="hinweis">Sportkomplexe (mehrere Sportstätten an einem Ort) führt der Datenbestand `
      + `bisher nicht; gezählt werden Sportstätten und ihre Anlagen.</p></div>`;
    el.innerHTML = h;
    el.querySelectorAll("[data-g]").forEach(z => z.addEventListener("click", () => setzeGebiet(NACH_S[z.dataset.g])));
  }
  return {
    titel: "Übersicht",
    starte() {},
    zeigen() { el.hidden = false; zeichne(); },
    verbergen() { el.hidden = true; },
    gebietGeaendert() { if (!el.hidden) zeichne(); },
  };
}
