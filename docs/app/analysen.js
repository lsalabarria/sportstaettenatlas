// Reiter „Analysen“: Auswertungen, deren Code in src/sportstaettenatlas/analysen/ liegt.
// Jede Analyse liefert ihre Dateien nach docs/daten/analysen/<name>/ und steht in
// docs/daten/analysen/index.json. Hier steht, wie sie auf der Karte erscheint: ein
// Eintrag in ANALYSEN mit Titel und einer Funktion, die ein Objekt wie eine Ansicht
// liefert (starte, zeigen, verbergen, aktualisiere, gebietGeaendert, suchindex).

const ANALYSEN = {
  alkis: { titel: "ALKIS-Abgleich", erzeuge: () => analyseAlkis() },
};
// Sportstätten aus ALKIS, für „Als neue Sportstätte vorschlagen“ (vorschlag.js)
let ALKIS_STAETTEN = {};

function ansichtAnalysen(namen, gewuenscht) {
  namen = namen.filter(n => ANALYSEN[n]);
  const inst = {};
  let aktiv = null, aktivName = null;
  const wahl = document.getElementById("analysewahl");
  wahl.innerHTML = namen.map(n => `<button type="button" data-analyse="${n}">`
    + `${esc(ANALYSEN[n].titel)}</button>`).join("");
  wahl.querySelectorAll("button").forEach(b => b.addEventListener("click", () =>
    waehle(b.dataset.analyse).catch(ladeFehler)));
  async function waehle(name) {
    if (!namen.includes(name)) name = namen[0];
    const a = inst[name] ??= ANALYSEN[name].erzeuge();
    if (!a.gestartet) { await a.starte(); a.gestartet = true; }
    if (aktiv && aktiv !== a) aktiv.verbergen();
    aktiv = a; aktivName = name;
    wahl.querySelectorAll("button").forEach(b =>
      b.setAttribute("aria-pressed", b.dataset.analyse === name ? "true" : "false"));
    if (AKTIV === "analysen") { a.zeigen(); merkeZustand(); }
  }
  return {
    titel: "Analysen",
    starte: () => waehle(gewuenscht),
    zeigen() { wahl.hidden = namen.length < 2; if (aktiv) aktiv.zeigen(); },
    verbergen() { wahl.hidden = true; if (aktiv) aktiv.verbergen(); },
    aktualisiere() { if (aktiv && aktiv.aktualisiere) aktiv.aktualisiere(); },
    gebietGeaendert() { for (const a of Object.values(inst)) if (a.gestartet) a.gebietGeaendert(); },
    suchindex: () => (aktiv ? aktiv.suchindex() : []),
    zustand: () => (namen.length > 1 && aktivName ? "analyse=" + aktivName : ""),
  };
}

// ---------- Analyse „ALKIS-Abgleich“: Kataster und Atlas im Vergleich --------------------
// Zeigt Sportstätten und -anlagen aus ALKIS mit ihrer Verifikationsstufe und die
// Atlas-Einträge ohne passende ALKIS-Fläche. Code: analysen/alkis/.
const FARBEN = {
  halle: "#534AB7", becken: "#185FA5", spielfeld: "#3B6D11", leichtathletik: "#993C1D",
  eis: "#0F6E56", spezial: "#854F0B", sportgelegenheit: "#888780", zubehoer: "#B4B2A9",
  unbestimmt: "#5F5E5A",  // ALKIS-Sammelbegriff "Sportanlage"
};
// Felder der Atlas-Einträge im Popup (Spalten aus analysen/alkis/karte.py: ATLAS_SPALTEN)
const ATLAS_FELDER = {
  alt_name: "Name", alt_komplex: "Komplex", alt_typ: "Typ", alt_anlagentypen: "Anlagen",
  alt_adresse: "Adresse", alkis_nutzung_vor_ort: "ALKIS-Nutzung hier",
  alkis_gebaeude_vor_ort: "ALKIS-Gebäude hier", naechste_sportstaette_id: "nächste ALKIS-Sportstätte",
  abstand_m: "Abstand m", alkis_typgruppen: "ALKIS dort", typ_passt: "Typ passt",
  alt_betriebsstatus: "Betriebsstatus", alt_datei: "Datei", alt_atlas_id: "Atlas-ID",
  alt_id: "Abgleich-ID",
};
const ZOOM_FLAECHEN = 15;
// Reihenfolge = CSS-Klasse stufe-<i>; LEGENDE = Reihenfolge in der Legende
const STUFEN = ["nur ALKIS", "bestätigt", "nur ALKIS – unbestimmt"];
const LEGENDE_STUFEN = ["nur ALKIS – unbestimmt", "nur ALKIS", "bestätigt"];

function analyseAlkis() {
  const ebene = L.layerGroup();
  let legende = null, aktualisiere = () => {}, zeigeZusammenfassung = () => {}, startGrenzen = null;
  const such = [];
  async function starte() {
    if (!EINGEBETTET) zeigeLaden("ALKIS-Daten werden geladen (einige MB) …");
    const [ANLAGEN, STAETTEN, ATLAS, ZUSAMMEN] = await Promise.all(["sportanlagen.geojson",
      "sportstaetten.geojson", "atlas_abgleich.geojson", "zusammenfassung.json"]
      .map(n => holeJson("analysen/alkis/" + n)));
    fertig();
    if (!ANLAGEN || !STAETTEN) throw new Error("ALKIS-Daten fehlen (sportanlagen.geojson)");
    baue(ANLAGEN, STAETTEN, ATLAS || { type: "FeatureCollection", features: [] }, ZUSAMMEN);
  }
  function baue(ANLAGEN, STAETTEN, ATLAS, ZUSAMMEN) {
    function farbe(p) { return FARBEN[p.typgruppe] || "#D85A30"; }
    // Rohspalten des Atlas (alt_*) erscheinen nicht im Tooltip; ihre Werte
    // stecken in den zusammengeführten Feldern, deren Herkunft in Klammern steht.
    const ROH = /^alt_|_quelle$|^verifikation|^(lon|lat|geometry|ars)$/;
    const LABEL = { flaeche_m2: "fläche m²", alkis_text: "ALKIS", alkis_oid: "ALKIS-OID",
      sportstaette_id: "Sportstätte", anlage_id: "Anlage", anzahl_anlagen: "Anlagen",
      pruefen: "zu prüfen", alkis_stand: "ALKIS-Stand", anlagen_laut_altbestand: "Anlagen (Atlas)" };
    const ZUERST = ["name", "typ", "typgruppe", "betreiber", "eigentuemer", "adresse", "sportarten",
      "website", "email", "betriebsstatus"];
    function zeilen(p, ohne = new Set()) {
      const keys = Object.keys(p).filter(k => !ROH.test(k) && !ohne.has(k) && !leer(p[k]));
      keys.sort((a, b) => {
        const ia = ZUERST.indexOf(a), ib = ZUERST.indexOf(b);
        return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
      });
      return keys.map(k => {
        const q = p[k + "_quelle"];
        let v = typeof p[k] === "boolean" ? (p[k] ? "ja" : "nein") : esc(p[k]);
        if (k === "website") v = `<a href="${esc(url(p[k]))}" target="_blank" rel="noopener">${v}</a>`;
        return `<tr><td>${esc(LABEL[k] || k)}</td><td>${v}`
          + (q ? ` <span class="q">(${esc(q)})</span>` : "") + "</td></tr>";
      }).join("");
    }
    function verifikation(p) {
      if (leer(p.verifikation)) return "";
      const i = Math.max(0, STUFEN.indexOf(p.verifikation_stufe));
      const bezug = leer(p.alt_bezug) ? ""
        : ` <span class="q">(Atlas: ${esc(p.alt_bezug)})</span>`;
      return `<tr><td>Verifikation</td><td><span class="verif stufe-${i}">`
        + `${esc(p.verifikation_stufe || "")}</span> ${esc(p.verifikation)}${bezug}</td></tr>`;
    }
    const STAETTE = {};
    for (const f of STAETTEN.features) STAETTE[f.properties.sportstaette_id] = f.properties;
    ALKIS_STAETTEN = STAETTE;
    function tipStaette(s) {
      return `<table class="meta">${verifikation(s)}${zeilen(s)}${koord(s.lat, s.lon)}`
        + (ANSICHTEN.vorschlag ? `<tr><td>Vorschlag</td><td><a href="#" data-vorschlag-alkis=`
          + `"${esc(s.sportstaette_id)}">Als neue Sportstätte vorschlagen</a></td></tr>` : "")
        + `</table>`;
    }
    function tipAnlage(p) {
      const s = STAETTE[p.sportstaette_id];
      let h = `<div class="tip"><h3>Sportanlage: ${esc(p.typ || "")}</h3>`
        + `<table class="meta">${verifikation(p)}${zeilen(p, new Set(["sportstaette_id"]))}`
        + `${koord(p.lat, p.lon)}</table>`;
      if (s) {
        h += `<h4>Sportstätte ${esc(s.sportstaette_id)} – gilt für alle ihre Anlagen</h4>`
          + tipStaette(s);
      }
      return h + "</div>";
    }

    // Sportstätten (Flächen) als gestrichelter Umriss
    const staetten = L.geoJSON(STAETTEN, {
      style: { color: "#444", weight: 1, dashArray: "4 3", fillOpacity: 0.04 },
      onEachFeature: (f, l) => info(l,
        `<div class="tip"><h3>Sportstätte</h3>${tipStaette(f.properties)}</div>`)
    });

    // Schraffur je Verifikationsstufe: Die Füllfarbe zeigt die Klasse (Typgruppe), die
    // Schraffur darüber in Grautönen die Verifikation – dunkel = auch im bisherigen Atlas.
    // Einträge, die nur im Sportstättenatlas RLP stehen, sind gegenläufig schraffiert (−45°).
    const SCHRAFFUR = {
      "nur ALKIS – unbestimmt": { grau: "#F1EFE8", abstand: 6, breite: 1.2, winkel: 0 },
      "nur ALKIS":          { grau: "#F1EFE8", abstand: 10, breite: 1.5, winkel: 45 },
      "bestätigt":          { grau: "#5F5E5A", abstand: 7,  breite: 1.6, winkel: 45 },
      "nicht in ALKIS":     { grau: "#F1EFE8", abstand: 3,  breite: 1.1, winkel: -45 },
      "nah":                { grau: "#5F5E5A", abstand: 3,  breite: 1.1, winkel: -45 },
    };
    const SCHRAFFUR_ID = {};
    (function muster() {
      const ns = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(ns, "svg");
      svg.setAttribute("width", "0"); svg.setAttribute("height", "0");
      svg.style.position = "absolute";
      const defs = document.createElementNS(ns, "defs");
      Object.entries(SCHRAFFUR).forEach(([stufe, m], i) => {
        const id = "schraffur-" + i;
        SCHRAFFUR_ID[stufe] = id;
        const pat = document.createElementNS(ns, "pattern");
        pat.setAttribute("id", id);
        pat.setAttribute("patternUnits", "userSpaceOnUse");
        pat.setAttribute("width", m.abstand); pat.setAttribute("height", m.abstand);
        pat.setAttribute("patternTransform", `rotate(${m.winkel})`);
        const linie = document.createElementNS(ns, "line");
        linie.setAttribute("x1", 0); linie.setAttribute("y1", 0);
        linie.setAttribute("x2", 0); linie.setAttribute("y2", m.abstand);
        linie.setAttribute("stroke", m.grau); linie.setAttribute("stroke-width", m.breite);
        pat.appendChild(linie); defs.appendChild(pat);
      });
      svg.appendChild(defs);
      document.body.appendChild(svg);
    })();
    function schraffurCss(stufe) {
      const m = SCHRAFFUR[stufe];
      if (!m) return "";
      return `background-image: repeating-linear-gradient(${m.winkel}deg, ${m.grau} 0 ${m.breite}px, `
        + `transparent ${m.breite}px ${m.abstand * 0.7}px)`;
    }

    // Sportanlagen: je Typgruppe zwei Ebenen – Punkt (weit) und Umriss (nah)
    const gruppen = {};
    const stufeAn = { "nur ALKIS – unbestimmt": true, "nur ALKIS": true, "bestätigt": true, "": true };
    const gruppe = name => gruppen[name] ??= { punkte: [], flaechen: [], n: 0, an: true };
    function stufeVon(p) {
      const s = STAETTE[p.sportstaette_id];
      return (s && s.verifikation_stufe) || p.verifikation_stufe || "";
    }
    for (const f of ANLAGEN.features) {
      const p = f.properties;
      const g = gruppe(p.typgruppe || "unbekannt");
      g.n++;
      const stil = { color: farbe(p), weight: 1.5, fillColor: farbe(p), fillOpacity: 0.45,
                     dashArray: p.pruefen ? "3 3" : null };
      const tip = () => tipAnlage(p);  // erst beim Anzeigen bauen
      const stufe = stufeVon(p);
      if (p.lat != null && p.lon != null) {
        g.punkte.push({ stufe, ars: p.ars, layer: info(L.circleMarker([p.lat, p.lon], { ...stil,
          weight: 1, radius: p.rolle === "zubehoer" ? 2 : 3.5, fillOpacity: 0.85 }), tip) });
      }
      if (f.geometry) {
        const basis = info(L.geoJSON(f, { style: { ...stil, renderer: svgRenderer },
          pointToLayer: (_, ll) => L.circleMarker(ll, stil) }), tip);
        const schicht = [basis];
        if (SCHRAFFUR_ID[stufe] && f.geometry.type !== "Point") {
          schicht.push(L.geoJSON(f, { style: { renderer: svgRenderer, stroke: false,
            fill: true, fillColor: `url(#${SCHRAFFUR_ID[stufe]})`, fillOpacity: 1,
            interactive: false } }));
        }
        g.flaechen.push({ stufe, ars: p.ars, bbox: bboxVon(f.geometry), layer: L.layerGroup(schicht) });
      }
    }
    const sichtbar = L.layerGroup().addTo(ebene);

    // Was nur im bisherigen Sportstättenatlas RLP steht (aus dem Abgleich mit ALKIS)
    const ATLAS_STIL = {
      "nicht in ALKIS": { color: "#A32D2D", fillColor: "#F09595", kurz: "nur Atlas",
        label: "nur im Sportstättenatlas RLP – kein ALKIS-Objekt im Umkreis von 200 m" },
      "nah": { color: "#854F0B", fillColor: "#FAC775", kurz: "nur Atlas, ALKIS in der Nähe",
        label: "im Sportstättenatlas RLP – nächste ALKIS-Sportstätte 100–200 m entfernt" },
    };
    const atlasAn = { "nicht in ALKIS": true, "nah": true };

    // Pfeil vom Atlas-Eintrag zur nächsten ALKIS-Sportstätte (bei Status "nah")
    const pfeilEbene = L.layerGroup().addTo(ebene);
    function zeigePfeil(von, s) {
      pfeilEbene.clearLayers();
      if (s.lat == null || s.lon == null) return;
      const nach = [s.lat, s.lon];
      L.polyline([von, nach], { color: "#854F0B", weight: 3, dashArray: "6 4",
        interactive: false }).addTo(pfeilEbene);
      // Pfeilspitze: Richtung aus projizierten Koordinaten (in Web-Mercator winkeltreu)
      const a = karte.project(von, 0), b = karte.project(nach, 0);
      const winkel = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
      L.marker(nach, { interactive: false, icon: L.divIcon({ className: "", iconSize: [22, 22],
        iconAnchor: [11, 11], html: `<div class="pfeil" style="transform:rotate(${winkel}deg)">➤</div>` })
      }).addTo(pfeilEbene);
      const f = STAETTEN.features.find(x => x.properties.sportstaette_id === s.sportstaette_id);
      if (f) {
        L.geoJSON(f, { style: { color: "#854F0B", weight: 3, fillOpacity: 0.1, renderer: svgRenderer },
          interactive: false }).addTo(pfeilEbene);
      }
      L.circleMarker(nach, { radius: 4, color: "#854F0B", fillOpacity: 1, interactive: false })
        .bindTooltip(`ALKIS: ${esc(s.name || s.sportstaette_id)}`, { permanent: true,
          direction: "right", offset: [8, 0] }).addTo(pfeilEbene);
      karte.fitBounds(L.latLngBounds([von, nach]).pad(0.6), { maxZoom: 17 });
    }
    karte.on("popupclose", () => pfeilEbene.clearLayers());
    const atlasPunkte = [];
    for (const f of ATLAS.features) {
      const p = f.properties, st = ATLAS_STIL[p.status] || ATLAS_STIL["nicht in ALKIS"];
      const [lon, lat] = f.geometry.coordinates;
      const zeilenA = Object.entries(ATLAS_FELDER).filter(([k]) => !leer(p[k])).map(([k, l]) =>
        `<tr><td>${esc(l)}</td><td>${typeof p[k] === "boolean" ? (p[k] ? "ja" : "nein")
          : esc(p[k])}</td></tr>`).join("");
      const tip = `<div class="tip"><h3>Sportstättenatlas RLP: ${esc(p.alt_name || "")}</h3>`
        + `<table class="meta"><tr><td>Verifikation</td><td><span class="verif" `
        + `style="background:${st.fillColor};color:${st.color}">${esc(st.kurz)}</span> `
        + `${esc(st.label)}</td></tr>${zeilenA}${koord(lat, lon)}`
        + `${leer(p.alt_atlas_id) ? "" : aendernLink("RP-" + p.alt_atlas_id, "Eintrag ändern")}</table></div>`;
      const kreis = { radius: 5, renderer: svgRenderer };
      const ziel = STAETTE[p.naechste_sportstaette_id];
      const pfeilHinweis = p.status === "nah" && ziel
        ? `<div class="hinweis">Klicken zeigt einen Pfeil zur nächsten ALKIS-Sportstätte</div>` : "";
      const basis = info(L.circleMarker([lat, lon], { ...kreis, color: st.color, weight: 1.5,
        fillColor: st.fillColor, fillOpacity: 0.85, dashArray: p.status === "nah" ? "2 2" : null }),
        tip.replace(/<\/div>$/, pfeilHinweis + "</div>"));
      if (p.status === "nah" && ziel) basis.on("click", () => zeigePfeil([lat, lon], ziel));
      const muster = L.circleMarker([lat, lon], { ...kreis, stroke: false, fill: true,
        fillColor: `url(#${SCHRAFFUR_ID[p.status] || SCHRAFFUR_ID["nicht in ALKIS"]})`,
        fillOpacity: 1, interactive: false });
      atlasPunkte.push({ status: p.status, ars: p.ars, layer: L.layerGroup([basis, muster]) });
    }

    // Nur Ebenen hinzufügen/entfernen, die sich ändern. Ein Neuaufbau würde offene Popups
    // schließen, z. B. wenn die Karte nach einem Klick zum Pfeil schwenkt.
    let aktuell = new Set();
    aktualisiere = () => {
      const nah = karte.getZoom() >= ZOOM_FLAECHEN;
      if (nah) staetten.addTo(ebene); else ebene.removeLayer(staetten);
      const b = karte.getBounds().pad(0.3);
      const [bw, bs, bo, bn] = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
      const imBild = e => !e.bbox || (e.bbox[0] <= bo && e.bbox[2] >= bw
                                      && e.bbox[1] <= bn && e.bbox[3] >= bs);
      const soll = new Set();
      for (const g of Object.values(gruppen)) {
        if (!g.an) continue;
        for (const e of (nah ? g.flaechen : g.punkte)) {
          if (stufeAn[e.stufe] !== false && imGebiet(e.ars) && (!nah || imBild(e))) soll.add(e.layer);
        }
      }
      for (const e of atlasPunkte) if (atlasAn[e.status] && imGebiet(e.ars)) soll.add(e.layer);
      for (const l of aktuell) if (!soll.has(l)) sichtbar.removeLayer(l);
      for (const l of soll) if (!aktuell.has(l)) sichtbar.addLayer(l);
      aktuell = soll;
    };

    // Legende: Typgruppen und – falls angereichert – Verifikationsstufen
    legende = L.control({ position: "topright" });
    legende.onAdd = () => {
      const div = L.DomUtil.create("div", "panel filter");
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);
      const namen = Object.keys(gruppen).sort((a, b) => gruppen[b].n - gruppen[a].n);
      const zaehl = {};
      for (const f of ANLAGEN.features) {
        const s = stufeVon(f.properties);
        if (s) zaehl[s] = (zaehl[s] || 0) + 1;
      }
      let h = `<h1>ALKIS-Abgleich</h1><div class="zusammenfassung"></div>`
        + `<h2>ALKIS: ${zahl(STAETTEN.features.length)} Sportstätten · ${zahl(ANLAGEN.features.length)} Anlagen</h2>`
        + namen.map(n => `<label><input type="checkbox" data-g="${esc(n)}" checked>`
          + `<span class="swatch" style="border-radius:3px;background:${FARBEN[n] || "#D85A30"}"></span>`
          + `${esc(n)}<span class="n">${zahl(gruppen[n].n)}</span></label>`).join("");
      const za = {};
      for (const e of atlasPunkte) za[e.status] = (za[e.status] || 0) + 1;
      if (Object.keys(zaehl).length || atlasPunkte.length) {
        h += `<h2>Verifikation</h2>` + LEGENDE_STUFEN.filter(s => zaehl[s]).map(s =>
          `<label><input type="checkbox" data-s="${esc(s)}" checked>`
          + `<span class="schraffur" style="${schraffurCss(s)}"></span>`
          + `<span class="verif stufe-${STUFEN.indexOf(s)}">${esc(s)}</span>`
          + `<span class="n">${zahl(zaehl[s])}</span></label>`).join("")
          + Object.keys(ATLAS_STIL).filter(k => za[k]).map(k =>
            `<label title="${esc(ATLAS_STIL[k].label)}"><input type="checkbox" data-a="${esc(k)}" checked>`
            + `<span class="swatch" style="background-color:${ATLAS_STIL[k].fillColor};`
            + `${schraffurCss(k)};width:14px;height:14px;border:2px solid ${ATLAS_STIL[k].color};`
            + `box-sizing:border-box"></span>`
            + `<span class="verif" style="background:${ATLAS_STIL[k].fillColor};`
            + `color:${ATLAS_STIL[k].color}">${esc(ATLAS_STIL[k].kurz)}</span>`
            + `<span class="n">${zahl(za[k])}</span></label>`).join("");
      }
      h += `<hr><span style="color:#666">Füllfarbe = Klasse, Schraffur = Verifikation `
        + `(ab Zoom ${ZOOM_FLAECHEN})<br>gestrichelt = zu prüfen`
        + (atlasPunkte.length ? `<br>rote/orange Kreise = nur im Sportstättenatlas RLP` : "")
        + `<br>ab Zoom ${ZOOM_FLAECHEN}: Umrisse und Sportstätten-Flächen</span>`;
      div.innerHTML = h;
      div.querySelectorAll("input[data-g]").forEach(cb => cb.addEventListener("change", () => {
        gruppen[cb.dataset.g].an = cb.checked; aktualisiere();
      }));
      div.querySelectorAll("input[data-s]").forEach(cb => cb.addEventListener("change", () => {
        stufeAn[cb.dataset.s] = cb.checked; aktualisiere();
      }));
      div.querySelectorAll("input[data-a]").forEach(cb => cb.addEventListener("change", () => {
        atlasAn[cb.dataset.a] = cb.checked; aktualisiere();
      }));
      return div;
    };

    for (const f of STAETTEN.features) {
      const p = f.properties;
      const titel = !leer(p.name) ? p.name : (p.typ || "Sportstätte");
      such.push({ titel, sub: [p.sportstaette_id, p.typ, leer(p.adresse) ? "" : p.adresse]
        .filter(Boolean).join(" · "), text: [p.name, p.adresse, p.sportstaette_id, p.typ,
        p.anlagentypen, p.betreiber, p.alt_name, p.alt_adresse, p.alt_typ, p.alt_atlas_id]
        .filter(v => !leer(v)).join(" ").toLowerCase(), ars: p.ars,
        grenzen: () => L.geoJSON(f).getBounds() });
    }
    for (const f of ATLAS.features) {
      const p = f.properties, [lon, lat] = f.geometry.coordinates;
      such.push({ titel: p.alt_name || "Atlas-Eintrag", sub: ["Sportstättenatlas RLP",
        p.alt_typ, p.alt_adresse].filter(v => !leer(v)).join(" · "), ars: p.ars,
        text: [p.alt_name, p.alt_adresse, p.alt_typ, p.alt_atlas_id, p.alt_id]
          .filter(v => !leer(v)).join(" ").toLowerCase(),
        grenzen: () => L.latLngBounds([[lat, lon], [lat, lon]]) });
    }
    if (STAETTEN.features.length) startGrenzen = staetten.getBounds();

    // Zusammenfassung: Wie viele Atlas-Einträge findet das Kataster? (für das gewählte Gebiet)
    zeigeZusammenfassung = () => {
      const el = legende && legende.getContainer && legende.getContainer()
        && legende.getContainer().querySelector(".zusammenfassung");
      if (!el || !ZUSAMMEN) return;
      const summe = ZUSAMMEN.status.map(() => 0);
      for (const [ars, werte] of Object.entries(ZUSAMMEN.je_gemeinde)) {
        if (imGebiet(ars)) werte.forEach((w, i) => { summe[i] += w; });
      }
      if (!GEBIET) ZUSAMMEN.ohne_gemeinde.forEach((w, i) => { summe[i] += w; });
      const n = summe.reduce((a, b) => a + b, 0);
      el.innerHTML = `<h2>Atlas-Einträge im Kataster · ${esc(gebietName())}</h2>`
        + balken(ZUSAMMEN.status.map((s, i) => [s, summe[i]]), n, true)
        + `<div class="hinweis">${zahl(n)} Einträge des Atlas; „in der Nähe“ = nächste `
        + `ALKIS-Sportstätte 100–200 m entfernt</div>`;
    };
  }
  let erstmals = true;
  return {
    starte,
    zeigen() {
      ebene.addTo(karte); legende.addTo(karte);
      if (erstmals && !GEBIET && startGrenzen && !ANSICHTEN.bestand) {
        karte.fitBounds(startGrenzen, { padding: [20, 20] });
      }
      erstmals = false;
      aktualisiere();
      zeigeZusammenfassung();
    },
    verbergen() { karte.removeLayer(ebene); legende.remove(); },
    aktualisiere: () => aktualisiere(),
    gebietGeaendert: () => { aktualisiere(); zeigeZusammenfassung(); },
    suchindex: () => such,
  };
}
