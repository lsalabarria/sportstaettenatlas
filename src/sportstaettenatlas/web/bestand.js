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
const ART_MEHRZAHL = { Verein: "Vereine", Kommune: "Kommunen" };
function artText(a) { return ART_MEHRZAHL[a] || a; }
function artVon(p, rolle = "betreiber") { return p[rolle + "_art"] || "ohne Angabe"; }
function katFarbe(k) { return KATEGORIE_FARBEN[k] || WEITERE; }
function schluesselName(s) { return String(s || "").trim().replace(/\s+/g, " ").toLowerCase(); }

// Gruppen der Sportanlagen (aus anlagen.py, stehen in bestand.geojson)
let ANLAGEN_GRUPPEN = [], ANLAGEN_TYPEN = {};
function anlagenGruppe(t) { return ANLAGEN_TYPEN[t] || "weitere"; }
function gruppenText(g) { const x = ANLAGEN_GRUPPEN.find(y => y[0] === g); return x ? x[1] : g; }
// Weitere Angaben einer Sportanlage als kurzer Text
function anlageDetails(a) {
  return [a.sportarten && a.sportarten.length ? a.sportarten.join(", ") : "",
    a.baujahr ? `Baujahr ${a.baujahr}` : "",
    a.baukosten_eur ? `Baukosten ${zahl(a.baukosten_eur)} €` : "",
    a.ausstattung && a.ausstattung.length ? a.ausstattung.join(", ") : ""].filter(Boolean).join(" · ");
}
// Anlagen einer Sportstätte nach Gruppe: [[Gruppe, [[Text, Anzahl, Typ, Angaben], …]], …]
function anlagenNachGruppe(liste) {
  const z = new Map();
  for (const a of liste) {
    const text = a.name ? `${a.typ} (${a.name})` : a.typ, details = anlageDetails(a);
    // Anlagen mit eigenen Angaben einzeln, sonst gleiche Typen zusammengefasst
    const k = text + (details ? `\u0000${a.id}` : "");
    const x = z.get(k) || { typ: a.typ, n: 0, text, details };
    x.n++; z.set(k, x);
  }
  const g = new Map();
  for (const { typ, n, text, details } of z.values()) {
    const k = anlagenGruppe(typ);
    if (!g.has(k)) g.set(k, []);
    g.get(k).push([text, n, typ, details]);
  }
  const reihe = ANLAGEN_GRUPPEN.map(x => x[0]);
  return [...g].sort((a, b) => reihe.indexOf(a[0]) - reihe.indexOf(b[0]));
}

function ansichtBestand(fc) {
  ANLAGEN_GRUPPEN = fc.anlagengruppen || [["weitere", "Weitere"]];
  ANLAGEN_TYPEN = fc.anlagentypen || {};
  const ebene = L.layerGroup();
  const eintraege = [];
  for (const f of fc.features) {
    const p = f.properties, [lon, lat] = f.geometry.coordinates;
    // Anlagen: [Typ, Kurz-ID, Name?, {Angaben}?] → Objekte; p.anlagen bleibt die Liste der Typen
    const anlagen = (p.anlagen || []).map(a => ({ typ: a[0], id: a[1] || "", name: a[2] || "", ...a[3] }));
    p.anlagen = anlagen.map(a => a.typ);
    const kat = p.kategorie || "ohne Kategorie";
    const e = { p, lat, lon, kat, art: artVon(p), an: false, typen: new Set(p.anlagen), anlagen,
      // Sportarten: die der Sportstätte und die ihrer Anlagen
      sp: new Set([...(p.sportarten || []), ...anlagen.flatMap(a => a.sportarten || [])]),
      betreiber: schluesselName(p.betreiber), eigentuemer: schluesselName(p.eigentuemer) };
    e.layer = info(L.circleMarker([lat, lon], { radius: 4, weight: 1, color: "#fff",
      fillColor: katFarbe(kat), fillOpacity: 0.95 }), () => tipBestand(e));
    eintraege.push(e);
  }
  // Zahl der Sportstätten je Kategorie, Sportart und Anlagentyp (ganzes Land)
  const katAlle = zaehle(eintraege.map(e => e.kat));
  const spAlle = zaehle(eintraege.flatMap(e => [...e.sp]));
  const anAlle = zaehle(eintraege.flatMap(e => [...e.typen]));
  const katAn = {}, artAn = {};
  for (const k of Object.keys(katAlle)) katAn[k] = true;
  for (const a of ARTEN) artAn[a] = true;
  const sportWahl = new Set(), anlagenWahl = new Set();
  let betreiberWahl = null;  // { rolle, schluessel, name }

  const mitEinem = (wahl, menge) => { for (const x of wahl) if (menge.has(x)) return true; return false; };
  function passt(e) {
    if (!katAn[e.kat] || !artAn[e.art] || !imGebiet(e.p.ars)) return false;
    if (betreiberWahl && e[betreiberWahl.rolle] !== betreiberWahl.schluessel) return false;
    if (sportWahl.size && !mitEinem(sportWahl, e.sp)) return false;
    if (anlagenWahl.size && !mitEinem(anlagenWahl, e.typen)) return false;
    return true;
  }
  let zahlEl = null;
  function aktualisiere() {
    let n = 0, gebiet = 0;
    for (const e of eintraege) {
      const soll = passt(e);
      if (soll) n++;
      if (imGebiet(e.p.ars)) gebiet++;
      if (soll !== e.an) { e.an = soll; if (soll) ebene.addLayer(e.layer); else ebene.removeLayer(e.layer); }
    }
    if (zahlEl) zahlEl.textContent = n === gebiet ? `${zahl(n)} Sportstätten`
      : `${zahl(n)} von ${zahl(gebiet)} Sportstätten`;
    return n;
  }
  // Zahlen im Filter: Sportstätten im gewählten Gebiet
  function zaehleGebiet() {
    if (!panelEl) return;
    const z = {};
    const plus = k => { z[k] = (z[k] || 0) + 1; };
    for (const e of eintraege) {
      if (!imGebiet(e.p.ars)) continue;
      plus("k:" + e.kat); plus("a:" + e.art);
      for (const s of e.sp) plus("s:" + s);
      const gruppen = new Set();
      for (const t of e.typen) { plus("t:" + t); gruppen.add(anlagenGruppe(t)); }
      for (const g of gruppen) plus("g:" + g);
    }
    setzeZahlen(panelEl, z);
  }

  // Filter-Panel
  const panel = L.control({ position: "topright" });
  let panelEl = null;
  function anlagenFilterHtml() {
    const typenJe = {};
    for (const t of Object.keys(anAlle)) (typenJe[anlagenGruppe(t)] ??= []).push(t);
    const gruppen = ANLAGEN_GRUPPEN.filter(([g]) => typenJe[g]);
    if (!gruppen.length) return "";
    return `<details open class="anlagen-filter"><summary>Sportanlagen darin <span id="b-an-n"></span></summary>`
      + `<div class="hinweis">Eine Sportstätte enthält eine oder mehrere Sportanlagen. Auswahl: `
      + `Sportstätten mit mindestens einer davon. Zahl = Sportstätten.</div>`
      + `<input type="search" placeholder="Sportanlage suchen, z. B. Rundlaufbahn" aria-label="Sportanlage suchen">`
      + `<div class="an-liste">` + gruppen.map(([g, text]) => {
        const typen = typenJe[g].sort((a, b) => anAlle[b] - anAlle[a]);
        return `<div class="an-gruppe" data-gruppe="${esc(g)}"><div class="an-kopf">`
          + `<button type="button" class="auf" aria-expanded="false" title="Typen zeigen">▸</button>`
          + `<label><input type="checkbox" data-ag="${esc(g)}"><b>${esc(text)}</b>${nSpan("g:" + g)}</label></div>`
          + `<div class="an-typen" hidden>` + typen.map(t => `<label data-text="${esc(t.toLowerCase())}">`
            + `<input type="checkbox" data-t="${esc(t)}">${esc(t)}${nSpan("t:" + t)}</label>`).join("")
          + `</div></div>`;
      }).join("") + `</div><div class="knoepfe"><button type="button" data-keine="an">Auswahl aufheben</button></div></details>`;
  }
  panel.onAdd = () => {
    const div = panelEl = panelDiv("filter");
    const kats = Object.keys(katAlle).sort((a, b) => katAlle[b] - katAlle[a]);
    const sps = Object.keys(spAlle).sort((a, b) => a.localeCompare(b, "de"));
    div.innerHTML = `<h1 id="b-zahl"></h1><div id="b-chip"></div>`
      + `<details><summary>Sportstätten nach Kategorie <span id="b-kat-n"></span></summary><div class="knoepfe">`
      + `<button type="button" data-alle="kat">alle</button><button type="button" data-keine="kat">keine</button></div>`
      + kats.map(k => `<label><input type="checkbox" data-k="${esc(k)}" checked>`
        + `<span class="swatch" style="background:${katFarbe(k)}"></span>${esc(k)}${nSpan("k:" + k)}</label>`).join("")
      + `</details>`
      + anlagenFilterHtml()
      + `<details open><summary>Betreiber</summary>`
      + ARTEN.filter(a => eintraege.some(e => e.art === a)).map(a => `<label><input type="checkbox" data-a="${a}" checked>`
        + `${artText(a)}${nSpan("a:" + a)}</label>`).join("")
      + `<div class="hinweis">Art aus dem Namen geschätzt (z. B. „e.V.“, „Ortsgemeinde“)</div></details>`
      + (sps.length ? `<details><summary>Sportarten <span id="b-sp-n"></span></summary>`
        + `<input type="search" placeholder="Sportart suchen" aria-label="Sportart suchen">`
        + `<div class="sp-liste">` + sps.map(s => `<label data-text="${esc(s.toLowerCase())}">`
          + `<input type="checkbox" data-s="${esc(s)}">${esc(s)}${nSpan("s:" + s)}</label>`).join("")
        + `</div><div class="knoepfe"><button type="button" data-keine="sp">Auswahl aufheben</button></div>`
        + `<div class="hinweis">Ohne Auswahl: alle. Mit Auswahl: Sportstätten mit mindestens einer davon.</div></details>`
        : "")
      + `<div class="hinweis">Klick auf einen Punkt: Angaben bleiben stehen · Rechtsklick: Koordinaten</div>`;
    zahlEl = div.querySelector("#b-zahl");
    // Häkchen: bei jeder Änderung `setze(Häkchen)` aufrufen, dann Karte und Zähler erneuern
    const beiAenderung = (auswahl, setze) => div.querySelectorAll(auswahl).forEach(cb =>
      cb.addEventListener("change", () => { setze(cb); zeigeWahl(); aktualisiere(); }));
    const schalte = (menge, wert, an) => { if (an) menge.add(wert); else menge.delete(wert); };
    beiAenderung("input[data-k]", cb => { katAn[cb.dataset.k] = cb.checked; });
    beiAenderung("input[data-a]", cb => { artAn[cb.dataset.a] = cb.checked; });
    beiAenderung("input[data-s]", cb => schalte(sportWahl, cb.dataset.s, cb.checked));
    // Sportanlagen: Gruppe wählt alle ihre Typen, einzelne Typen nach Aufklappen
    beiAenderung("input[data-t]", cb => schalte(anlagenWahl, cb.dataset.t, cb.checked));
    beiAenderung("input[data-ag]", cb => cb.closest(".an-gruppe").querySelectorAll("input[data-t]")
      .forEach(t => schalte(anlagenWahl, t.dataset.t, cb.checked)));
    const klappe = (gruppe, auf) => {
      gruppe.querySelector(".an-typen").hidden = !auf;
      const b = gruppe.querySelector(".auf");
      b.textContent = auf ? "▾" : "▸"; b.setAttribute("aria-expanded", auf);
    };
    div.querySelectorAll(".an-gruppe .auf").forEach(b => b.addEventListener("click", () => {
      const g = b.closest(".an-gruppe"); klappe(g, g.querySelector(".an-typen").hidden); }));
    div.querySelectorAll("[data-alle],[data-keine]").forEach(b => b.addEventListener("click", () => {
      const an = !!b.dataset.alle, was = b.dataset.alle || b.dataset.keine;
      if (was === "kat") {
        div.querySelectorAll("input[data-k]").forEach(cb => { cb.checked = an; katAn[cb.dataset.k] = an; });
      } else if (was === "an") {
        anlagenWahl.clear();
      } else {
        sportWahl.clear();
      }
      zeigeWahl(); aktualisiere();
    }));
    const suchSp = div.querySelector(".sp-liste") && div.querySelector(".sp-liste").previousElementSibling;
    if (suchSp) suchSp.addEventListener("input", () => {
      const q = suchSp.value.trim().toLowerCase();
      div.querySelectorAll(".sp-liste label").forEach(l => { l.hidden = q && !l.dataset.text.includes(q); });
    });
    const suchAn = div.querySelector(".anlagen-filter input[type=search]");
    if (suchAn) suchAn.addEventListener("input", () => {
      const q = suchAn.value.trim().toLowerCase();
      div.querySelectorAll(".an-gruppe").forEach(g => {
        let treffer = 0;
        g.querySelectorAll(".an-typen label").forEach(l => {
          const ok = !q || l.dataset.text.includes(q);
          l.hidden = !ok; if (ok) treffer++;
        });
        g.hidden = q && !treffer;
        klappe(g, !!q && treffer > 0);
      });
    });
    zeigeChip();
    zeigeWahl();
    zaehleGebiet();
    aktualisiere();
    return div;
  };
  // Häkchen und Zähler passend zur Auswahl (auch nach Klick im Popup)
  function zeigeWahl() {
    if (!panelEl) return;
    panelEl.querySelectorAll("input[data-s]").forEach(c => { c.checked = sportWahl.has(c.dataset.s); });
    panelEl.querySelectorAll("input[data-t]").forEach(c => { c.checked = anlagenWahl.has(c.dataset.t); });
    panelEl.querySelectorAll("input[data-ag]").forEach(cb => {
      const typen = [...cb.closest(".an-gruppe").querySelectorAll("input[data-t]")];
      const n = typen.filter(t => t.checked).length;
      cb.checked = n > 0 && n === typen.length;
      cb.indeterminate = n > 0 && n < typen.length;
    });
    const spN = panelEl.querySelector("#b-sp-n"), anN = panelEl.querySelector("#b-an-n");
    const katN = panelEl.querySelector("#b-kat-n"), aus = Object.values(katAn).filter(v => !v).length;
    if (katN) katN.textContent = aus ? `(${zahl(aus)} ausgeblendet)` : "(alle)";
    if (spN) spN.textContent = sportWahl.size ? `(${sportWahl.size} gewählt)` : "";
    if (anN) anN.textContent = anlagenWahl.size ? `(${anlagenWahl.size} gewählt)` : "";
  }
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
    betreiberWahl = null; sportWahl.clear(); anlagenWahl.clear();
    for (const k in katAn) katAn[k] = true;
    for (const a in artAn) artAn[a] = true;
    if (panelEl) panelEl.querySelectorAll("input[data-k],input[data-a]").forEach(c => { c.checked = true; });
    zeigeChip(); zeigeWahl();
  }
  function oeffne(e) {
    if (!imGebiet(e.p.ars)) setzeGebiet(null, false);
    if (!passt(e)) filterZurueck();
    aktualisiere();
    if (e.an) e.layer.openPopup();
  }
  // Klick auf eine Anlage im Popup: alle Sportstätten mit dieser Anlage zeigen
  function nurAnlage(typ) {
    karte.closePopup();
    anlagenWahl.clear(); anlagenWahl.add(typ);
    zeigeWahl(); aktualisiere();
  }
  document.addEventListener("click", ev => {
    const a = ev.target.closest("[data-nur-anlage]");
    if (!a || AKTIV !== "bestand") return;
    ev.preventDefault();
    nurAnlage(a.dataset.nurAnlage);
  });

  function tipBestand(e) {
    const p = e.p, z = [];
    const zeile = (l, v) => { if (!leer(v)) z.push(`<tr><td>${l}</td><td>${v}</td></tr>`); };
    const art = a => a ? `<span class="art">${esc(a)}</span>` : "";
    zeile("Kategorie", leer(p.kategorie) ? "" : `<span class="swatch" style="display:inline-block;`
      + `background:${katFarbe(e.kat)};vertical-align:-1px"></span> ${esc(p.kategorie)}`);
    zeile("Adresse", leer(p.adresse) ? "" : esc(p.adresse));
    zeile("Gebiet", esc(gemeindeName(p.ars)));
    zeile("Betreiber", leer(p.betreiber) ? "" : esc(p.betreiber) + art(p.betreiber_art));
    zeile("Eigentümer", leer(p.eigentuemer) ? "" : esc(p.eigentuemer) + art(p.eigentuemer_art));
    zeile("Sportarten", leer(p.sportarten) ? "" : esc(p.sportarten.join(", ")));
    zeile("Öffentlich", esc(p.oeffentlicher_zugang || ""));
    zeile("Schulsport", esc(p.schulsport || ""));
    zeile("Zuschauer", leer(p.zuschauerplaetze) ? "" : zahl(p.zuschauerplaetze));
    zeile("Betrieb", esc(p.betriebsstatus || ""));
    zeile("Website", leer(p.website) ? "" : `<a href="${esc(url(p.website))}" target="_blank" `
      + `rel="noopener">${esc(p.website)}</a>`);
    zeile("ID", leer(p.id) ? "" : `<span class="koord">${esc(p.id)}</span>`);
    const n = (p.anlagen || []).length;
    const anlagen = n ? `<div class="anlagen-tip"><h4>${n === 1 ? "1 Sportanlage" : `${n} Sportanlagen`}</h4>`
      + anlagenNachGruppe(e.anlagen).map(([g, typen]) => `<div><span class="gr">${esc(gruppenText(g))}</span> `
        + typen.map(([text, k, t, d]) => `<a href="#" data-nur-anlage="${esc(t)}" title="Alle Sportstätten mit `
          + `${esc(t)} zeigen">${k > 1 ? `${k}× ` : ""}${esc(text)}</a>`
          + (d ? ` <span class="details">(${esc(d)})</span>` : "")).join(", ") + `</div>`).join("")
      + `</div>` : `<div class="anlagen-tip leer">Keine Sportanlagen eingetragen</div>`;
    return `<div class="tip"><h3>${esc(p.name || p.kategorie || "Sportstätte")}</h3>${anlagen}`
      + `<table class="meta">${z.join("")}${koord(e.lat, e.lon)}${aendernLink(p.id)}</table></div>`;
  }

  const such = eintraege.map(e => ({
    titel: e.p.name || e.kat, sub: verbinde([e.p.kategorie, e.p.adresse, e.p.betreiber]),
    text: suchtext([e.p.name, e.p.adresse, e.p.kategorie, e.p.betreiber, e.p.eigentuemer, e.p.id,
      ...(e.p.sportarten || []), ...e.typen]),
    grenzen: () => punktGrenzen(e.lat, e.lon),
    oeffne: () => oeffne(e),
    ars: e.p.ars,
  }));
  let erstmals = true;
  return {
    titel: "Karte",
    eintraege,
    zeigen() {
      ebene.addTo(karte); panel.addTo(karte); aktualisiere();
      if (erstmals && !GEBIET && eintraege.length) {
        karte.fitBounds(L.latLngBounds(eintraege.map(e => [e.lat, e.lon])), { padding: [20, 20] });
      }
      erstmals = false;
    },
    verbergen() { karte.removeLayer(ebene); panel.remove(); },
    gebietGeaendert() { zaehleGebiet(); aktualisiere(); },
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
      + `aria-pressed="${a === art}">${artText(a)}`
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
    zeigen() { el.hidden = false; zeichne(); },
    verbergen() { el.hidden = true; },
    gebietGeaendert() { if (!el.hidden) zeichne(); },
  };
}

// ---------- Ansicht „Übersicht“: kleines Dashboard über den Datenbestand ----------------
// Befüllung der Angaben, getrennt für Sportstätten und ihre Sportanlagen
// { Beschriftung: Feld oder [Felder] } → [[Beschriftung, Test "ist befüllt"], …]
function feldTests(namen) {
  return Object.entries(namen).map(([text, f]) => [text, x => [].concat(f).every(k => !leer(x[k]))]);
}
const FELDER = feldTests({
  "Name": "name", "Kategorie": "kategorie", "Straße": "strasse", "PLZ und Ort": ["plz", "ort"],
  "Sportanlagen eingetragen": "anlagen", "Sportarten": "sportarten", "Betreiber": "betreiber",
  "Eigentümer": "eigentuemer", "Öffentlicher Zugang": "oeffentlicher_zugang",
  "Schulsport": "schulsport", "Betriebsstatus": "betriebsstatus",
  "Zuschauerplätze": "zuschauerplaetze", "Website": "website",
});
const ANLAGE_FELDER = feldTests({ "Name": "name", "Sportarten": "sportarten", "Baujahr": "baujahr",
  "Baukosten": "baukosten_eur", "Ausstattung": "ausstattung" });
function anteil(liste, felder) {
  if (!liste.length) return 0;
  let summe = 0;
  for (const x of liste) for (const [, test] of felder) if (test(x)) summe++;
  return summe / (liste.length * felder.length);
}
function befuellung(liste) { return anteil(liste.map(e => e.p), FELDER); }
function balken(zeilen, gesamt, prozentual, einheit = "Sportstätten") {
  // zeilen: [label, wert]; Breite relativ zu gesamt (Anteil) bzw. zum größten Wert
  const max = prozentual ? gesamt : Math.max(1, ...zeilen.map(z => z[1]));
  return `<table class="balken">` + zeilen.map(([l, w]) => {
    const breite = Math.max(0, Math.min(100, 100 * w / (max || 1)));
    const text = prozentual ? `${prozent(w, gesamt)} %` : zahl(w);
    const titel = prozentual ? `${zahl(w)} von ${zahl(gesamt)}` : `${zahl(w)} ${einheit}`;
    return `<tr title="${esc(l)}: ${titel}"><td class="l">${esc(l)}</td>`
      + `<td><div class="spur"><div class="fuell" style="width:${breite.toFixed(1)}%"></div></div></td>`
      + `<td class="w">${text}</td></tr>`;
  }).join("") + `</table>`;
}
function ansichtUebersicht(bestand) {
  const el = document.getElementById("seite-uebersicht");
  function zeichne() {
    const liste = bestand.eintraege.filter(e => imGebiet(e.p.ars));
    const anlagen = liste.flatMap(e => e.anlagen);
    const n = liste.length, na = anlagen.length;
    const sportarten = new Set(liste.flatMap(e => [...e.sp]));
    const betr = { Verein: new Set(), Kommune: new Set() };
    for (const e of liste) if (betr[e.art] && e.betreiber) betr[e.art].add(e.betreiber);
    const sortiert = z => Object.entries(z).sort((a, b) => b[1] - a[1]);
    const kachel = (label, wert, zusatz = "") => `<div class="kachel"><div class="label">${label}</div>`
      + `<div class="wert">${wert}</div><div class="zusatz">${zusatz}</div></div>`;
    const ohneAnlagen = liste.filter(e => !e.anlagen.length).length;
    let h = `<div class="inhalt"><h2>Übersicht: ${esc(gebietName())}</h2>`
      + `<p class="unter">Datenbestand der Karte (Ordner <code>daten/</code>): Sportstätten und die `
      + `Sportanlagen darin</p><div class="kacheln">`
      + kachel("Sportstätten", zahl(n), ohneAnlagen ? `${zahl(ohneAnlagen)} ohne eingetragene Sportanlage` : "alle mit Sportanlagen")
      + kachel("Sportanlagen", zahl(na), n ? `Ø ${(na / n).toLocaleString("de-DE",
        { maximumFractionDigits: 1 })} je Sportstätte` : "")
      + kachel("Angaben Sportstätten", `${Math.round(100 * befuellung(liste))} %`, `befüllt, Durchschnitt über ${FELDER.length} Felder`)
      + kachel("Angaben Sportanlagen", `${Math.round(100 * anteil(anlagen, ANLAGE_FELDER))} %`, `befüllt, Durchschnitt über ${ANLAGE_FELDER.length} Felder`)
      + kachel("Sportarten", zahl(sportarten.size), "verschiedene")
      + kachel("Vereine", zahl(betr.Verein.size), "als Betreiber (aus dem Namen geschätzt)")
      + kachel("Kommunen", zahl(betr.Kommune.size), "als Betreiber (aus dem Namen geschätzt)")
      + `</div>`;
    h += `<div class="spalten"><div><h3>Sportstätten</h3><h4>Wie gut sind die Angaben befüllt?</h4>`
      + balken(FELDER.map(([l, t]) => [l, liste.filter(e => t(e.p)).length]), n, true)
      + `<h4>Nach Kategorie</h4>` + balken(sortiert(zaehle(liste.map(e => e.kat))), n, false)
      + `<h4>Betreiber</h4>` + balken(ARTEN.map(a => [artText(a), liste.filter(e => e.art === a).length])
        .filter(z => z[1]), n, true)
      + `</div><div><h3>Sportanlagen</h3><h4>Wie gut sind die Angaben befüllt?</h4>`
      + balken(ANLAGE_FELDER.map(([l, t]) => [l, anlagen.filter(t).length]), na, true, "Sportanlagen")
      + `<h4>Nach Gruppe</h4>` + balken(ANLAGEN_GRUPPEN.map(([g, text]) =>
        [text, anlagen.filter(a => anlagenGruppe(a.typ) === g).length]).filter(z => z[1])
        .sort((a, b) => b[1] - a[1]), 0, false, "Sportanlagen")
      + `<h4>Häufigste Typen</h4>` + balken(sortiert(zaehle(anlagen.map(a => a.typ))).slice(0, 12), 0, false, "Sportanlagen")
      + `<h4>Sportanlagen je Sportstätte</h4>` + balken(sortiert(zaehle(liste.map(e =>
        e.anlagen.length >= 5 ? "5 und mehr" : String(e.anlagen.length)))).sort((a, b) => a[0].localeCompare(b[0])), 0, false)
      + `</div></div>`;
    // Teilgebiete: Befüllung je Kreis bzw. je Verbandsgemeinde/Gemeinde
    const ebene = !GEBIET ? "kreis" : GEBIET.e === "kreis" ? "vg" : GEBIET.e === "vg" ? "gemeinde" : null;
    const teile = ebene ? GEBIETE.filter(g => g.e === ebene && (!GEBIET || g.s.startsWith(GEBIET.s))) : [];
    if (teile.length > 1) {
      const spur = b => `<table class="balken"><tr><td><div class="spur"><div class="fuell" `
        + `style="width:${(100 * b).toFixed(1)}%"></div></div></td><td class="w">${Math.round(100 * b)} %</td></tr></table>`;
      const zeilen = teile.map(g => {
        const l = liste.filter(e => e.p.ars && e.p.ars.startsWith(g.s)), a = l.flatMap(e => e.anlagen);
        return { g, n: l.length, na: a.length, b: befuellung(l), ba: anteil(a, ANLAGE_FELDER) };
      }).sort((a, b) => b.n - a.n);
      h += `<h3>Nach ${ebene === "kreis" ? "Kreisen" : ebene === "vg" ? "Verbandsgemeinden" : "Gemeinden"}</h3>`
        + `<table class="tabelle"><thead><tr><th>Gebiet</th><th class="zahl">Sportstätten</th>`
        + `<th class="zahl">Sportanlagen</th><th style="width:24%">Angaben Sportstätten</th>`
        + `<th style="width:24%">Angaben Sportanlagen</th></tr></thead><tbody>` + zeilen.map(z =>
          `<tr class="zeile" data-g="${z.g.s}" title="Gebiet auswählen"><td>${esc(gebietTitel(z.g))}</td>`
          + `<td class="zahl">${zahl(z.n)}</td><td class="zahl">${zahl(z.na)}</td>`
          + `<td>${z.n ? spur(z.b) : "–"}</td><td>${z.na ? spur(z.ba) : "–"}</td></tr>`).join("")
        + `</tbody></table>`;
    }
    h += `</div>`;
    el.innerHTML = h;
    el.querySelectorAll("[data-g]").forEach(z => z.addEventListener("click", () => setzeGebiet(NACH_S[z.dataset.g])));
  }
  return {
    titel: "Übersicht",
    zeigen() { el.hidden = false; zeichne(); },
    verbergen() { el.hidden = true; },
    gebietGeaendert() { if (!el.hidden) zeichne(); },
  };
}
