// Ansichten zum Datenbestand des Atlas (daten/): Karte, Übersicht (Liste: liste.js).

// Alle Sportstätten in einer Farbe: was man sucht, zeigen die Filter (viele Farben auf
// tausenden Punkten lassen sich nicht auseinanderhalten).
const PUNKT_FARBE = "#871D33";

// ---------- Ansicht „Karte“: der Datenbestand -------------------------------------------
// Art von Betreiber bzw. Eigentümer: aus der Angabe bei der Sportstätte oder dem Verzeichnis der
// Organisationen (seite.py, betreiber_art); ohne Art "unbekannt", ohne Namen "ohne Angabe"
const ARTEN = ["Verein", "Kommune", "sonstige", "unbekannt", "ohne Angabe"];
const ART_MEHRZAHL = { Verein: "Vereine", Kommune: "Kommunen", unbekannt: "Art unbekannt" };
function artText(a) { return ART_MEHRZAHL[a] || a; }
function artVon(p, rolle = "betreiber") {
  return p[rolle + "_art"] || (leer(p[rolle]) ? "ohne Angabe" : "unbekannt");
}

// Gruppen der Sportanlagen (aus anlagen.py, stehen in bestand.geojson)
let ANLAGEN_GRUPPEN = [], ANLAGEN_TYPEN = {};
function anlagenGruppe(t) { return ANLAGEN_TYPEN[t] || "weitere"; }
function gruppenText(g) { const x = ANLAGEN_GRUPPEN.find(y => y[0] === g); return x ? x[1] : g; }
// Weitere Angaben einer Sportanlage als kurzer Text: alle Felder des Modells außer Typ, Name,
// IDs; Listen ohne, Einzelwerte mit Beschriftung („Baujahr 1998“)
function anlageDetails(a) {
  const einheiten = nurEinheit("Sportanlage");
  return modellFelder("Sportanlage")
    .filter(([k, p, , t]) => p.formular !== false && k !== "typ" && k !== "bezeichnung"
      && !einheiten.has(k) && feldText(p, t, a[k]))
    .map(([k, p, , t]) => (t.type === "array" && k !== "wettkampf" ? "" : p.title + " ")
      + feldText(p, t, a[k], a))
    .join(" · ");
}
// Anlagen einer Sportstätte nach Gruppe: [[Gruppe, [[Text, Anzahl, Typ, Angaben], …]], …]
function anlagenNachGruppe(liste) {
  const z = new Map();
  for (const a of liste) {
    const text = a.bezeichnung ? `${a.typ} (${a.bezeichnung})` : a.typ, details = anlageDetails(a);
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
  const kreisVon = new Map();  // Punkt → Schlüssel seines Kreises (5 Stellen des ars)
  const ebene = haufen({
    gruppe: layer => kreisVon.get(layer) || null,
    name: k => (NACH_S[k] ? gebietTitel(NACH_S[k]) : ""),
    grenzen: k => (NACH_S[k] ? grenzenVon(NACH_S[k]) : null),
  });
  const eintraege = [];
  for (const f of fc.features) {
    const p = f.properties, [lon, lat] = f.geometry.coordinates;
    // Anlagen: [Typ, Kurz-ID, Name?, {Angaben}?] → Objekte; p.anlagen bleibt die Liste der Typen
    const anlagen = (p.anlagen || []).map(a => ({ typ: a[0], id: a[1] || "", bezeichnung: a[2] || "", ...a[3] }));
    p.anlagen = anlagen.map(a => a.typ);
    const kat = p.kategorie || "ohne Kategorie";
    const e = { p, lat, lon, kat, art: artVon(p), an: false, typen: new Set(p.anlagen), anlagen,
      // Sportarten: die der Sportstätte und die ihrer Anlagen
      sp: new Set([...(p.sportarten || []), ...anlagen.flatMap(a => a.sportarten || [])]),
      betreiber: schluesselName(p.betreiber), eigentuemer: schluesselName(p.eigentuemer) };
    e.layer = info(L.circleMarker([lat, lon], { radius: 4, weight: 1, color: "#fff",
      fillColor: PUNKT_FARBE, fillOpacity: 0.95 }), () => tipBestand(e));
    if (p.ars && p.ars.length >= 5) kreisVon.set(e.layer, p.ars.slice(0, 5));
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
  let komplexWahl = "";  // "": alle, IN_KOMPLEX: in irgendeinem Sportkomplex, sonst dessen ID
  let stpWahl = "";  // Stützpunkte: "", "*", "e:<Ebene>" oder die ID (stpPasst)
  let betreiberWahl = null;  // { rolle, schluessel, name }

  const mitEinem = (wahl, menge) => { for (const x of wahl) if (menge.has(x)) return true; return false; };
  function passt(e) {
    if (!katAn[e.kat] || !artAn[e.art] || !imGebiet(e.p.ars)) return false;
    if (betreiberWahl && !(betreiberWahl.ids ? betreiberWahl.ids.has(e.p.id)
      : e[betreiberWahl.rolle] === betreiberWahl.schluessel)) return false;
    if (sportWahl.size && !mitEinem(sportWahl, e.sp)) return false;
    if (anlagenWahl.size && !mitEinem(anlagenWahl, e.typen)) return false;
    if (komplexWahl && !(komplexWahl === IN_KOMPLEX ? e.p.sportkomplex : e.p.sportkomplex === komplexWahl)) return false;
    if (stpWahl && !stpPasst(e.p.id, stpWahl)) return false;
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
      if (e.p.sportkomplex) { plus("ko:" + IN_KOMPLEX); plus("ko:" + e.p.sportkomplex); }
      const sp = STP_JE_STAETTE.get(e.p.id) || [];
      if (sp.length) plus("sp:*");
      for (const eb of new Set(sp.map(x => x.ebene))) plus("sp:e:" + eb);
      for (const x of sp) plus("sp:" + x.id);
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
        + `${esc(k)}${nSpan("k:" + k)}</label>`).join("")
      + `</details>`
      + anlagenFilterHtml()
      + `<details open><summary>Betreiber</summary>`
      + ARTEN.filter(a => eintraege.some(e => e.art === a)).map(a => `<label><input type="checkbox" data-a="${a}" checked>`
        + `${artText(a)}${nSpan("a:" + a)}</label>`).join("")
      + `<div class="hinweis">Art bei der Sportstätte oder im Verzeichnis der Organisationen angegeben; sonst unbekannt</div></details>`
      + (sps.length ? `<details><summary>Sportarten <span id="b-sp-n"></span></summary>`
        + `<input type="search" placeholder="Sportart suchen" aria-label="Sportart suchen">`
        + `<div class="sp-liste">` + sps.map(s => `<label data-text="${esc(s.toLowerCase())}">`
          + `<input type="checkbox" data-s="${esc(s)}">${esc(s)}${nSpan("s:" + s)}</label>`).join("")
        + `</div><div class="knoepfe"><button type="button" data-keine="sp">Auswahl aufheben</button></div>`
        + `<div class="hinweis">Ohne Auswahl: alle. Mit Auswahl: Sportstätten mit mindestens einer davon.</div></details>`
        : "")
      + `<details><summary>Sportkomplexe <span id="b-ko-n"></span></summary>`
        + `<label><input type="radio" name="b-ko" data-ko="" checked>alle, mit und ohne Sportkomplex</label>`
        + `<label><input type="radio" name="b-ko" data-ko="${IN_KOMPLEX}">nur in einem Sportkomplex${nSpan("ko:" + IN_KOMPLEX)}</label>`
        + `<input type="search" placeholder="Sportkomplex suchen" aria-label="Sportkomplex suchen">`
        + `<div class="ko-liste">` + komplexeNachName().map(k => `<label data-text="${esc(k.name.toLowerCase())}">`
          + `<input type="radio" name="b-ko" data-ko="${esc(k.id)}">${esc(k.name)}${nSpan("ko:" + k.id)}</label>`).join("")
          + (SPORTKOMPLEXE.size ? "" : `<div class="hinweis">Noch keine Sportkomplexe eingetragen.</div>`)
        + `</div><div class="hinweis">Mehrere Sportstätten an einem Ort, z. B. ein Sportzentrum</div></details>`
      + `<details><summary>Stützpunkte <span id="b-stp-n"></span></summary>`
        + `<label><input type="radio" name="b-sp" data-sp="" checked>alle, mit und ohne Stützpunkt</label>`
        + `<label><input type="radio" name="b-sp" data-sp="*">nur an einem Stützpunkt${nSpan("sp:*")}</label>`
        + STP_EBENEN.map(([eb, t]) => `<label><input type="radio" name="b-sp" data-sp="e:${eb}">nur ${t}${nSpan("sp:e:" + eb)}</label>`).join("")
        + `<input type="search" placeholder="Stützpunkt suchen" aria-label="Stützpunkt suchen">`
        + `<div class="ko-liste sp-liste-st">` + stuetzpunkteNachName().map(x => `<label data-text="${esc(x.name.toLowerCase())}">`
          + `<input type="radio" name="b-sp" data-sp="${esc(x.id)}">${esc(x.name)}${nSpan("sp:" + x.id)}</label>`).join("")
          + (STUETZPUNKTE.size ? "" : `<div class="hinweis">Noch keine Stützpunkte eingetragen.</div>`)
        + `</div><div class="hinweis">Olympia-, Bundes- und Landesstützpunkte des Leistungssports</div></details>`
      + `<div class="hinweis">Klick auf einen Punkt: Angaben bleiben stehen · Rechtsklick: Koordinaten</div>`;
    zahlEl = div.querySelector("#b-zahl");
    // Häkchen: bei jeder Änderung `setze(Häkchen)` aufrufen, dann Karte und Zähler erneuern
    const beiAenderung = (auswahl, setze) => div.querySelectorAll(auswahl).forEach(cb =>
      cb.addEventListener("change", () => { setze(cb); zeigeWahl(); aktualisiere(); }));
    const schalte = (menge, wert, an) => { if (an) menge.add(wert); else menge.delete(wert); };
    beiAenderung("input[data-k]", cb => { katAn[cb.dataset.k] = cb.checked; });
    beiAenderung("input[data-a]", cb => { artAn[cb.dataset.a] = cb.checked; });
    beiAenderung("input[data-s]", cb => schalte(sportWahl, cb.dataset.s, cb.checked));
    beiAenderung("input[data-ko]", cb => { if (cb.checked) komplexWahl = cb.dataset.ko; });
    beiAenderung("input[data-sp]", cb => { if (cb.checked) stpWahl = cb.dataset.sp; });
    div.querySelectorAll(".ko-liste").forEach(liste => {
      const such = liste.previousElementSibling;
      such.addEventListener("input", () => {
        const q = such.value.trim().toLowerCase();
        liste.querySelectorAll("label").forEach(l => { l.hidden = q && !l.dataset.text.includes(q); });
      });
    });
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
    panelEl.querySelectorAll("input[data-ko]").forEach(c => { c.checked = c.dataset.ko === komplexWahl; });
    panelEl.querySelectorAll("input[data-sp]").forEach(c => { c.checked = c.dataset.sp === stpWahl; });
    const stpN = panelEl.querySelector("#b-stp-n");
    if (stpN) stpN.textContent = !stpWahl ? "" : stpWahl === "*" ? "(nur an einem)"
      : stpWahl.startsWith("e:") ? `(${STP_EBENEN.find(x => "e:" + x[0] === stpWahl)[1]})`
      : `(${(STUETZPUNKTE.get(stpWahl) || {}).name || stpWahl})`;
    const koN = panelEl.querySelector("#b-ko-n");
    if (koN) koN.textContent = !komplexWahl ? "" : komplexWahl === IN_KOMPLEX ? "(nur in einem)"
      : `(${komplexName(komplexWahl)})`;
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
    el.innerHTML = betreiberWahl ? `<div class="chip">${{ betreiber: "Betreiber", eigentuemer: "Eigentümer",
      nutzer: "Nutzer" }[betreiberWahl.rolle]}: <b>${esc(betreiberWahl.name)}</b> `
      + `<button type="button" title="Filter aufheben">× aufheben</button></div>` : "";
    const b = el.querySelector("button");
    if (b) b.addEventListener("click", () => { betreiberWahl = null; zeigeChip(); aktualisiere(); });
  }

  // Ein gesuchter Eintrag soll sichtbar werden, auch wenn Filter ihn gerade ausblenden
  function filterZurueck() {
    betreiberWahl = null; sportWahl.clear(); anlagenWahl.clear(); komplexWahl = ""; stpWahl = "";
    for (const k in katAn) katAn[k] = true;
    for (const a in artAn) artAn[a] = true;
    if (panelEl) panelEl.querySelectorAll("input[data-k],input[data-a]").forEach(c => { c.checked = true; });
    zeigeChip(); zeigeWahl();
  }
  function oeffne(e) {
    if (!imGebiet(e.p.ars)) setzeGebiet(null, false);
    if (!passt(e)) filterZurueck();
    aktualisiere();
    if (e.an) { ebene.einzeln(e.layer); e.layer.openPopup(); }
  }
  // Klick auf eine Anlage im Popup: alle Sportstätten mit dieser Anlage zeigen
  function nurAnlage(typ) {
    karte.closePopup();
    anlagenWahl.clear(); anlagenWahl.add(typ);
    zeigeWahl(); aktualisiere();
  }
  // Klick auf „alle auf der Karte“ beim Sportkomplex: nur seine Sportstätten, auf sie zoomen
  document.addEventListener("click", ev => {
    const a = ev.target.closest("[data-nur-komplex]");
    if (!a || AKTIV !== "bestand") return;
    ev.preventDefault();
    karte.closePopup();
    komplexWahl = a.dataset.nurKomplex;
    zeigeWahl(); aktualisiere();
    const pkte = eintraege.filter(e => e.an).map(e => [e.lat, e.lon]);
    if (pkte.length) karte.fitBounds(L.latLngBounds(pkte).pad(0.3), { maxZoom: 18 });
  });
  document.addEventListener("click", ev => {
    const a = ev.target.closest("[data-nur-anlage]");
    if (!a || AKTIV !== "bestand") return;
    ev.preventDefault();
    nurAnlage(a.dataset.nurAnlage);
  });

  function tipBestand(e) {
    const p = e.p, z = [];
    const zeile = (l, v) => { if (!leer(v)) z.push(`<tr><td>${esc(l)}</td><td>${v}</td></tr>`); };
    // Zeilen in der Reihenfolge des Datenmodells; der Name steht in der Überschrift
    for (const [k, f, , t] of modellFelder("Sportstaette")) {
      if (k === "name" || k === "id" || f.formular === false || t.ref === "Lage") continue;
      if (k === "kategorie") {
        zeile(f.title, leer(p.kategorie) ? "" : esc(p.kategorie));
      } else if (t.ref) {  // Adresse: als ein Text, dazu das Gebiet
        zeile(f.title, leer(p[k]) ? "" : esc(p[k]));
        zeile("Gebiet", esc(gemeindeName(p.ars)));
      } else if (f.widget === "sportkomplex") {
        zeile(f.title, leer(p[k]) ? "" : komplexZeile(p[k], p.id));
      } else if (f.widget === "url") {
        zeile(f.title, leer(p[k]) ? "" : `<a href="${esc(url(p[k]))}" target="_blank" `
          + `rel="noopener">${esc(p[k])}</a>`);
      } else {
        const text = esc(feldText(f, t, p[k]));
        zeile(f.title, text);
      }
    }
    zeile("Stützpunkte", stpZeile(p.id));
    zeile("ID", leer(p.id) ? "" : `<span class="koord">${esc(p.id)}</span>`);
    const n = (p.anlagen || []).length;
    const anlagen = n ? `<div class="anlagen-tip"><h4>${n === 1 ? "1 Sportanlage" : `${n} Sportanlagen`}</h4>`
      + anlagenNachGruppe(e.anlagen).map(([g, typen]) => `<div><span class="gr">${esc(gruppenText(g))}</span> `
        + typen.map(([text, k, t, d]) => `<a href="#" data-nur-anlage="${esc(t)}" title="Alle Sportstätten mit `
          + `${esc(t)} zeigen">${k > 1 ? `${k}× ` : ""}${esc(text)}</a>`
          + (d ? ` <span class="details">(${esc(d)})</span>` : "")).join(", ") + `</div>`).join("")
      + `</div>` : `<div class="anlagen-tip leer">Keine Sportanlagen eingetragen</div>`;
    const alle = `<tr><td>Angaben</td><td><a href="#" data-details="${esc(p.id)}">alle Angaben ansehen</a></td></tr>`;
    return `<div class="tip"><h3>${esc(p.name || p.kategorie || "Sportstätte")}</h3>${anlagen}`
      + `<table class="meta">${z.join("")}${koord(e.lat, e.lon)}${alle}${aendernLink(p.id)}</table></div>`;
  }

  const such = eintraege.map(e => ({
    titel: e.p.name || e.kat, sub: verbinde([e.p.kategorie, e.p.adresse, e.p.betreiber]),
    text: suchtext([e.p.name, e.p.adresse, e.p.kategorie, e.p.betreiber, e.p.eigentuemer, e.p.id,
      e.p.sportkomplex ? komplexName(e.p.sportkomplex) : "",
      ...(e.p.nutzer || []),
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
    verbergen() { ebene.remove(); panel.remove(); },
    gebietGeaendert() { zaehleGebiet(); aktualisiere(); },
    suchindex: () => such,
    // Sportstätten einer Organisation zeigen; ids: die Sportstätten (sonst über den Namen)
    zeigeBetreiber(rolle, schluessel, name, ids = null) {
      betreiberWahl = { rolle, schluessel, name, ids };
      zeige("bestand").then(() => {
        zeigeChip();
        aktualisiere();
        const pkte = eintraege.filter(e => e.an).map(e => [e.lat, e.lon]);
        if (pkte.length) karte.fitBounds(L.latLngBounds(pkte).pad(0.15), { maxZoom: 16 });
      });
    },
    // nur die Sportstätten eines Stützpunkts zeigen und auf sie zoomen
    zeigeStuetzpunkt(id) {
      zeige("bestand").then(() => {
        stpWahl = id;
        zeigeWahl(); aktualisiere();
        const pkte = eintraege.filter(e => e.an).map(e => [e.lat, e.lon]);
        if (pkte.length) karte.fitBounds(L.latLngBounds(pkte).pad(0.3), { maxZoom: 17 });
      });
    },
    // nur die Sportstätten eines Sportkomplexes zeigen und auf sie zoomen
    zeigeKomplex(id) {
      zeige("bestand").then(() => {
        komplexWahl = id;
        zeigeWahl(); aktualisiere();
        const pkte = eintraege.filter(e => e.an).map(e => [e.lat, e.lon]);
        if (pkte.length) karte.fitBounds(L.latLngBounds(pkte).pad(0.3), { maxZoom: 18 });
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

// ---------- Ansicht „Übersicht“: kleines Dashboard über den Datenbestand ----------------
// Befüllung der Angaben, getrennt für Sportstätten und ihre Sportanlagen
// Felder aus dem Datenmodell (ohne uebersicht: false) → [{ titel, test, gruppe, fuer }];
// die Teile der Adresse einzeln (sie stehen flach in den Eigenschaften der Karte) in der
// Gruppe der Adresse. fuer: Feld ist nur für diese Sportanlagen gedacht (passtFuer).
function feldTests(modell, gruppe) {
  const out = [];
  for (const [k, p, , t] of modellFelder(modell)) {
    if (p.uebersicht === false) continue;
    if (t.ref) out.push(...feldTests(t.ref, p.gruppe));
    else out.push({ titel: p.title || k, gruppe: gruppe || p.gruppe || "Weitere Angaben",
      fuer: p.fuer ? x => passtFuer(p, x.typ) : null,
      test: x => !leer(x[k]) && !(typeof x[k] === "object" && !Array.isArray(x[k]) && !Object.keys(x[k]).length) });
  }
  return out;
}
let _felder, _anlageFelder;
const FELDER_STAETTE = () => _felder ??= feldTests("Sportstaette");
const FELDER_ANLAGE = () => _anlageFelder ??= feldTests("Sportanlage");
// Befüllung eines Feldes: [befüllt, gedacht für] – nur unter den Einträgen, für die es gedacht ist
function befuellt(liste, f) {
  let ja = 0, n = 0;
  for (const x of liste) if (!f.fuer || f.fuer(x)) { n++; if (f.test(x)) ja++; }
  return [ja, n];
}
// Anteil befüllter Angaben über alle Felder (je Eintrag nur die Felder, die zu ihm passen)
function anteil(liste, felder) {
  let ja = 0, n = 0;
  for (const f of felder) { const [a, b] = befuellt(liste, f); ja += a; n += b; }
  return n ? ja / n : 0;
}
function befuellung(liste) { return anteil(liste.map(e => e.p), FELDER_STAETTE()); }
// Befüllung nach Abschnitten des Modells (gruppen): aufklappbar, je Feld ein Balken
function befuellungNachGruppe(modell, liste, felder, einheit) {
  const reihe = [...(SCHEMA.$defs[modell].gruppen || [])];
  for (const f of felder) if (!reihe.includes(f.gruppe)) reihe.push(f.gruppe);
  return reihe.map((g, i) => {
    const fs = felder.filter(f => f.gruppe === g);
    if (!fs.length) return "";
    const zeilen = fs.map(f => { const [ja, n] = befuellt(liste, f); return [f.titel, ja, n]; })
      .filter(z => z[2]);
    if (!zeilen.length) return "";
    const b = anteil(liste, fs);
    return `<details class="befuellung"${i === 0 ? " open" : ""}><summary><b>${esc(g)}</b>`
      + `<span class="w">${Math.round(100 * b)} %</span></summary>`
      + `<table class="balken">` + zeilen.map(([l, ja, n]) => {
        const breite = n ? 100 * ja / n : 0;
        const nur = n < liste.length ? ` (nur ${zahl(n)} ${einheit}, für die das Feld gedacht ist)` : "";
        return `<tr title="${esc(l)}: ${zahl(ja)} von ${zahl(n)}${esc(nur)}"><td class="l">${esc(l)}`
          + `${nur ? ` <span class="q">· ${zahl(n)}</span>` : ""}</td>`
          + `<td><div class="spur"><div class="fuell" style="width:${breite.toFixed(1)}%"></div></div></td>`
          + `<td class="w">${prozent(ja, n)} %</td></tr>`;
      }).join("") + `</table></details>`;
  }).join("");
}
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
  let sport = "";  // Filter nach Sportart ("": alle)
  el.addEventListener("change", ev => {
    if (ev.target.matches("[data-u-sport]")) { sport = ev.target.value; zeichne(); }
  });
  function zeichne() {
    const imG = bestand.eintraege.filter(e => imGebiet(e.p.ars));
    const liste = sport ? imG.filter(e => e.sp.has(sport)) : imG;
    const sportWahlHtml = `<label class="u-sport">Sportart <select data-u-sport><option value="">alle</option>`
      + [...new Set(imG.flatMap(e => [...e.sp]))].sort((a, b) => a.localeCompare(b, "de"))
        .map(s => `<option${s === sport ? " selected" : ""}>${esc(s)}</option>`).join("") + `</select></label>`;
    // Stützpunkte mit mindestens einer dieser Sportstätten (bei Sportart: für diese Sportart)
    const ids = new Set(liste.map(e => e.p.id));
    const stp = [...STUETZPUNKTE.values()].filter(x => [...x.alle].some(i => ids.has(i))
      && (!sport || !(x.sportarten || []).length || x.sportarten.includes(sport)));
    const stpKachel = ([eb, text]) => {
      const sp = stp.filter(x => x.ebene === eb);
      const an = new Set(sp.flatMap(x => [...x.alle].filter(i => ids.has(i))));
      return kachel(text, zahl(sp.length), sp.length ? `an ${zahl(an.size)} Sportstätten` : "keine eingetragen");
    };
    const anlagen = liste.flatMap(e => e.anlagen);
    const n = liste.length, na = anlagen.length;
    const sportarten = new Set(liste.flatMap(e => [...e.sp]));
    const betr = { Verein: new Set(), Kommune: new Set() };
    for (const e of liste) if (betr[e.art] && e.betreiber) betr[e.art].add(e.betreiber);
    const sortiert = z => Object.entries(z).sort((a, b) => b[1] - a[1]);
    const kachel = (label, wert, zusatz = "") => `<div class="kachel"><div class="label">${label}</div>`
      + `<div class="wert">${wert}</div><div class="zusatz">${zusatz}</div></div>`;
    const ohneAnlagen = liste.filter(e => !e.anlagen.length).length;
    // Sportkomplexe mit mindestens einer Sportstätte im Gebiet: Name → Zahl dieser Sportstätten
    const imKomplex = liste.filter(e => e.p.sportkomplex);
    const jeKomplex = sortiert(zaehle(imKomplex.map(e => komplexName(e.p.sportkomplex))));
    const angegeben = rolle => liste.map(e => e.p[rolle + "_typ"]).filter(v => !leer(v));
    const artBalken = rolle => {
      const z = angegeben(rolle);
      return z.length ? `<h4>Art des ${rolle === "betreiber" ? "Betreibers" : "Eigentümers"} (angegeben)</h4>`
        + balken(sortiert(zaehle(z)), z.length, false) : "";
    };
    // Teil 1: was im Bestand steht
    let h = `<div class="inhalt"><div class="u-kopf"><h2>Übersicht: ${esc(gebietName())}${sport ? ` · ${esc(sport)}` : ""}</h2>${sportWahlHtml}</div>`
      + `<section class="teil"><h2 class="teil-titel">Bestand</h2>`
      + `<p class="unter">Was der Datenbestand (Ordner <code>daten/</code>) enthält: Sportstätten, `
      + `die Sportanlagen darin und wer sie betreibt</p><div class="kacheln drei">`
      + kachel("Sportstätten", zahl(n), ohneAnlagen ? `${zahl(ohneAnlagen)} ohne eingetragene Sportanlage` : "alle mit Sportanlagen")
      + kachel("Sportanlagen", zahl(na), n ? `Ø ${(na / n).toLocaleString("de-DE",
        { maximumFractionDigits: 1 })} je Sportstätte` : "")
      + kachel("Sportkomplexe", zahl(jeKomplex.length), jeKomplex.length
        ? `mit ${zahl(imKomplex.length)} Sportstätten (${prozent(imKomplex.length, n)} %)` : "noch keine eingetragen")
      + kachel("Sportarten", zahl(sportarten.size), "verschiedene")
      + kachel("Vereine", zahl(betr.Verein.size), "als Betreiber (mit angegebener Art)")
      + kachel("Kommunen", zahl(betr.Kommune.size), "als Betreiber (mit angegebener Art)")
      + STP_EBENEN.map(stpKachel).join("")
      + `</div><div class="spalten"><div><h3>Sportstätten</h3>`
      + `<h4>Nach Kategorie</h4>` + balken(sortiert(zaehle(liste.map(e => e.kat))), n, false)
      + `<h4>Betreiber</h4>` + balken(ARTEN.map(a => [artText(a), liste.filter(e => e.art === a).length])
        .filter(z => z[1]), n, true)
      + `<div class="hinweis">Art angegeben bei ${zahl(angegeben("betreiber").length)} Sportstätten (bei der Sportstätte oder im Verzeichnis der Organisationen)</div>`
      + artBalken("betreiber") + artBalken("eigentuemer")
      + (jeKomplex.length ? `<h4>Größte Sportkomplexe</h4>` + balken(jeKomplex.slice(0, 10), 0, false) : "")
      + `</div><div><h3>Sportanlagen</h3>`
      + `<h4>Nach Gruppe</h4>` + balken(ANLAGEN_GRUPPEN.map(([g, text]) =>
        [text, anlagen.filter(a => anlagenGruppe(a.typ) === g).length]).filter(z => z[1])
        .sort((a, b) => b[1] - a[1]), 0, false, "Sportanlagen")
      + `<h4>Häufigste Typen</h4>` + balken(sortiert(zaehle(anlagen.map(a => a.typ))).slice(0, 12), 0, false, "Sportanlagen")
      + `<h4>Sportanlagen je Sportstätte</h4>` + balken(sortiert(zaehle(liste.map(e =>
        e.anlagen.length >= 5 ? "5 und mehr" : String(e.anlagen.length)))).sort((a, b) => a[0].localeCompare(b[0])), 0, false)
      + `</div></div></section>`;
    // Teil 2: wie vollständig die Angaben sind
    h += `<section class="teil"><h2 class="teil-titel">Befüllung</h2>`
      + `<p class="unter">Wie vollständig die Angaben im Bestand sind: Anteil der befüllten Felder `
      + `des Datenmodells</p><div class="kacheln">`
      + kachel("Angaben Sportstätten", `${Math.round(100 * befuellung(liste))} %`, `befüllt, Durchschnitt über ${FELDER_STAETTE().length} Felder`)
      + kachel("Angaben Sportanlagen", `${Math.round(100 * anteil(anlagen, FELDER_ANLAGE()))} %`,
        `befüllt, Durchschnitt über die Felder, die zum Typ passen (bis ${FELDER_ANLAGE().length})`)
      + `</div><div class="spalten"><div><h3>Sportstätten</h3>`
      + befuellungNachGruppe("Sportstaette", liste.map(e => e.p), FELDER_STAETTE(), "Sportstätten")
      + `</div><div><h3>Sportanlagen</h3>`
      + `<div class="hinweis">Felder, die nur für bestimmte Sportanlagen gedacht sind (z. B. Becken für Bäder), `
      + `zählen nur unter diesen; die Zahl dahinter nennt, wie viele es sind.</div>`
      + befuellungNachGruppe("Sportanlage", anlagen, FELDER_ANLAGE(), "Sportanlagen")
      + `</div></div>`;
    // Teilgebiete: Befüllung je Kreis bzw. je Verbandsgemeinde/Gemeinde
    const ebene = !GEBIET ? "kreis" : GEBIET.e === "kreis" ? "vg" : GEBIET.e === "vg" ? "gemeinde" : null;
    const teile = ebene ? GEBIETE.filter(g => g.e === ebene && (!GEBIET || g.s.startsWith(GEBIET.s))) : [];
    if (teile.length > 1) {
      const spur = b => `<table class="balken"><tr><td><div class="spur"><div class="fuell" `
        + `style="width:${(100 * b).toFixed(1)}%"></div></div></td><td class="w">${Math.round(100 * b)} %</td></tr></table>`;
      const zeilen = teile.map(g => {
        const l = liste.filter(e => e.p.ars && e.p.ars.startsWith(g.s)), a = l.flatMap(e => e.anlagen);
        return { g, n: l.length, na: a.length, b: befuellung(l), ba: anteil(a, FELDER_ANLAGE()) };
      }).sort((a, b) => b.n - a.n);
      h += `<h3>Befüllung nach ${ebene === "kreis" ? "Kreisen" : ebene === "vg" ? "Verbandsgemeinden" : "Gemeinden"}</h3>`
        + `<table class="tabelle"><thead><tr><th>Gebiet</th><th class="zahl">Sportstätten</th>`
        + `<th class="zahl">Sportanlagen</th><th style="width:24%">Angaben Sportstätten</th>`
        + `<th style="width:24%">Angaben Sportanlagen</th></tr></thead><tbody>` + zeilen.map(z =>
          `<tr class="zeile" data-g="${z.g.s}" title="Gebiet auswählen"><td>${esc(gebietTitel(z.g))}</td>`
          + `<td class="zahl">${zahl(z.n)}</td><td class="zahl">${zahl(z.na)}</td>`
          + `<td>${z.n ? spur(z.b) : "–"}</td><td>${z.na ? spur(z.ba) : "–"}</td></tr>`).join("")
        + `</tbody></table>`;
    }
    h += `</section></div>`;
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
