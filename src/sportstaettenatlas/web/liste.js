// Ansicht „Liste“: alle Sportstätten, alle Sportanlagen (beide nach Sportart, Kategorie bzw.
// Typ filterbar), Organisationen (Eigentümer, Betreiber, Nutzer). Klick auf eine Zeile öffnet rechts alle bisher
// befüllten Angaben der Sportstätte und ihrer Anlagen; von dort geht es zur Karte oder zum
// Vorschlag. Die Auswahl steht in der Adresse der Seite (#ansicht=liste&teil=anlagen&sportart=…).

const LISTE_SCHRITT = 200;  // so viele Zeilen auf einmal, „weitere zeigen“ lädt nach

function ansichtListe(bestand) {
  const el = document.getElementById("seite-liste");
  const start = new URLSearchParams(location.hash.slice(1));
  const z = {  // Zustand, landet in der Adresse
    teil: ["staetten", "anlagen", "betreiber"].includes(start.get("teil")) ? start.get("teil") : "staetten",
    q: start.get("q") || "", sportart: start.get("sportart") || "", kategorie: start.get("kategorie") || "",
    typ: start.get("typ") || "", sort: start.get("sort") || "", ab: start.get("ab") === "1",
    id: start.get("id") || "", anlage: start.get("anlage") || "", leere: false,
  };
  let zeigen = LISTE_SCHRITT, gezeichnet = false;
  const NACH_ID = new Map(bestand.eintraege.map(e => [e.p.id, e]));
  const betreiber = teilBetreiber(bestand, document.createElement("div"));

  // Anlagen mit ihrer Sportstätte; Sportarten der Anlage, sonst die der Sportstätte (geerbt)
  const ANLAGEN = bestand.eintraege.flatMap(e => e.anlagen.map(a => {
    const eigene = a.sportarten || [];
    return { a, e, sp: eigene.length ? eigene : [...(e.p.sportarten || [])], geerbt: !eigene.length };
  }));
  const SPORTARTEN = [...new Set(bestand.eintraege.flatMap(e => [...e.sp]))].sort((x, y) => x.localeCompare(y, "de"));
  const KATEGORIEN = [...new Set(bestand.eintraege.map(e => e.kat))].sort((x, y) => x.localeCompare(y, "de"));
  const TYPEN = [...new Set(ANLAGEN.map(x => x.a.typ))].sort((x, y) =>
    ANLAGEN_GRUPPEN.findIndex(g => g[0] === anlagenGruppe(x)) - ANLAGEN_GRUPPEN.findIndex(g => g[0] === anlagenGruppe(y))
    || x.localeCompare(y, "de"));

  // Befüllung: Anteil der Felder mit Wert (bei Anlagen nur die, die zum Typ passen)
  const anteilVon = (x, felder) => {
    let ja = 0, n = 0;
    for (const f of felder) if (!f.fuer || f.fuer(x)) { n++; if (f.test(x)) ja++; }
    return n ? ja / n : 0;
  };
  const balkenKlein = b => `<span class="mini"><span style="width:${Math.round(100 * b)}%"></span></span>`
    + `<span class="w">${Math.round(100 * b)} %</span>`;
  const sportText = (liste, geerbt) => liste.length
    ? `<span${geerbt ? ` class="geerbt" title="Sportarten der Sportstätte (die Anlage hat keine eigenen)"` : ""}>`
      + esc(liste.join(", ")) + `</span>` : "";
  const suchtextE = e => (e._such ??= suchtext([e.p.name, e.p.adresse, e.p.kategorie, e.p.id, e.p.betreiber, e.p.eigentuemer, ...(e.p.nutzer || [])]));
  const worte = () => z.q.toLowerCase().split(/\s+/).filter(Boolean);

  // --- Zeilen der beiden Listen ---
  function staettenZeilen() {
    const w = worte();
    return bestand.eintraege.filter(e => imGebiet(e.p.ars)
      && (!z.sportart || e.sp.has(z.sportart))
      && (!z.kategorie || e.kat === z.kategorie)
      && (!z.typ || e.typen.has(z.typ))
      && (!w.length || w.every(x => suchtextE(e).includes(x))));
  }
  function anlagenZeilen() {
    const w = worte();
    return ANLAGEN.filter(x => imGebiet(x.e.p.ars)
      && (!z.sportart || x.sp.includes(z.sportart))
      && (!z.kategorie || x.e.kat === z.kategorie)
      && (!z.typ || x.a.typ === z.typ)
      && (!w.length || w.every(t => (suchtextE(x.e) + " " + suchtext([x.a.typ, x.a.bezeichnung, x.a.id])).includes(t))));
  }
  const SPALTEN = {
    staetten: [
      ["name", "Name", e => e.p.name || ""],
      ["kategorie", "Kategorie", e => e.kat],
      ["ort", "Ort", e => e.p.ort || ""],
      ["sportarten", "Sportarten", e => [...e.sp].join(", ")],
      ["anlagen", "Anlagen", e => e.anlagen.length, true],
      ["befuellt", "Angaben", e => e._b ??= anteilVon(e.p, FELDER_STAETTE()), true],
    ],
    anlagen: [
      ["typ", "Sportanlage", x => x.a.typ + (x.a.bezeichnung ? ` (${x.a.bezeichnung})` : "")],
      ["staette", "Sportstätte", x => x.e.p.name || x.e.kat],
      ["ort", "Ort", x => x.e.p.ort || ""],
      ["sportarten", "Sportarten", x => x.sp.join(", ")],
      ["befuellt", "Angaben", x => x._b ??= anteilVon(x.a, FELDER_ANLAGE()), true],
    ],
  };
  function sortiere(liste) {
    const sp = SPALTEN[z.teil].find(s => s[0] === z.sort);
    if (!sp) return liste;
    const [, , wert, zahlig] = sp;
    return liste.slice().sort((x, y) => (zahlig ? wert(x) - wert(y)
      : String(wert(x)).localeCompare(String(wert(y)), "de")) * (z.ab ? -1 : 1));
  }
  function tabelle(liste) {
    const sp = SPALTEN[z.teil], pfeil = k => z.sort === k ? (z.ab ? " ▼" : " ▲") : "";
    const kopf = sp.map(([k, t, , zahlig]) => `<th data-sort="${k}"${zahlig ? ` class="zahl"` : ""}>${t}${pfeil(k)}</th>`).join("")
      + `<th></th>`;
    const zeile = z.teil === "staetten"
      ? e => `<tr class="zeile${e.p.id === z.id ? " offen" : ""}" data-id="${esc(e.p.id)}">`
        + `<td>${esc(e.p.name || e.kat)}</td><td class="klein"><span class="swatch" style="background:${katFarbe(e.kat)}"></span>${esc(e.kat)}</td>`
        + `<td class="klein">${esc(e.p.ort || "")}</td><td class="klein">${sportText([...e.sp])}</td>`
        + `<td class="zahl">${e.anlagen.length}</td><td class="zahl">${balkenKlein(SPALTEN.staetten[5][2](e))}</td>`
        + `<td><a data-karte="${esc(e.p.id)}" title="Auf der Karte zeigen">Karte</a></td></tr>`
      : x => `<tr class="zeile${x.e.p.id === z.id && x.a.id === z.anlage ? " offen" : ""}" data-id="${esc(x.e.p.id)}" data-anlage="${esc(x.a.id)}">`
        + `<td>${esc(x.a.typ)}${x.a.bezeichnung ? ` <span class="klein">(${esc(x.a.bezeichnung)})</span>` : ""}`
        + `${typPasst(x.e.p.kategorie, x.a.typ) ? "" : ` <span class="warn" title="Typ passt nicht zur Kategorie „${esc(x.e.kat)}“">!</span>`}</td>`
        + `<td class="klein">${esc(x.e.p.name || x.e.kat)}</td><td class="klein">${esc(x.e.p.ort || "")}</td>`
        + `<td class="klein">${sportText(x.sp, x.geerbt)}</td><td class="zahl">${balkenKlein(SPALTEN.anlagen[4][2](x))}</td>`
        + `<td><a data-karte="${esc(x.e.p.id)}" title="Sportstätte auf der Karte zeigen">Karte</a></td></tr>`;
    const mehr = liste.length > zeigen ? `<button type="button" class="knopf2" data-mehr>weitere ${zahl(Math.min(LISTE_SCHRITT,
      liste.length - zeigen))} von ${zahl(liste.length - zeigen)} zeigen</button>` : "";
    return `<table class="tabelle liste"><thead><tr>${kopf}</tr></thead><tbody>`
      + (liste.slice(0, zeigen).map(zeile).join("") || `<tr><td colspan="${sp.length + 1}" class="klein">Keine Einträge.</td></tr>`)
      + `</tbody></table>${mehr}`;
  }

  // --- Ansicht aller Angaben einer Sportstätte und ihrer Anlagen ---
  function feldZeilen(modell, x, gruppeVon, leere, typ) {
    const einheiten = nurEinheit(modell), out = new Map();
    for (const [k, p, , t] of modellFelder(modell)) {
      if (p.formular === false || einheiten.has(k) || t.ref || p.widget === "karte") continue;
      if (modell === "Sportanlage" && (k === "typ" || k === "bezeichnung")) continue;
      let text = feldText(p, t, x[k], x);
      if (p.widget === "url" && text) text = `<a href="${esc(url(text))}" target="_blank" rel="noopener">${esc(text)}</a>`;
      else text = esc(text);
      if (!text && !(leere && passtFuer(p, typ))) continue;
      const g = gruppeVon(p);
      if (!out.has(g)) out.set(g, []);
      out.get(g).push(`<tr${text ? "" : ` class="leer"`}><td>${esc(p.title)}</td><td>${text || "–"}</td></tr>`);
    }
    return out;
  }
  function gruppenTabellen(reihe, zeilen) {
    const alle = [...new Set([...reihe, ...zeilen.keys()])];
    return alle.filter(g => zeilen.has(g)).map(g => `<h5>${esc(g)}</h5><table class="meta">${zeilen.get(g).join("")}</table>`).join("");
  }
  function details() {
    const e = NACH_ID.get(z.id);
    if (!e) return "";
    const p = e.p, leere = z.leere;
    const zeilen = feldZeilen("Sportstaette", p, f => f.gruppe || "Weitere Angaben", leere);
    const lage = (zeilen.get("Adresse und Lage") || []);
    lage.unshift(`<tr><td>Adresse</td><td>${esc(p.adresse || "–")}</td></tr>`, `<tr><td>Gebiet</td><td>${esc(gemeindeName(p.ars) || "–")}</td></tr>`);
    lage.push(koord(e.lat, e.lon));
    zeilen.set("Adresse und Lage", lage);
    const bs = anteilVon(p, FELDER_STAETTE());
    const vorschlag = ANSICHTEN.vorschlag
      ? ` <a class="knopf2" href="#" data-bearbeiten="${esc(p.id)}">Angaben ändern</a>`
        + ` <a class="knopf2" href="#" data-bearbeiten="${esc(p.id)}" data-teil="anlagen">Sportanlagen ändern</a>` : "";
    const anlagen = e.anlagen.map(a => {
      const za = feldZeilen("Sportanlage", a, f => f.gruppe || "Allgemein", leere, a.typ);
      const passt = typPasst(p.kategorie, a.typ);
      return `<details class="anlage-details" data-anlage="${esc(a.id)}"${a.id === z.anlage ? " open" : ""}>`
        + `<summary><b>${esc(a.typ)}</b>${a.bezeichnung ? ` (${esc(a.bezeichnung)})` : ""} <span class="q">${esc(a.id)}</span>`
        + `<span class="w">${Math.round(100 * anteilVon(a, FELDER_ANLAGE()))} %</span></summary>`
        + (passt ? "" : `<div class="warnung klein">Typ passt nicht zur Kategorie „${esc(e.kat)}“.</div>`)
        + (za.size ? gruppenTabellen(SCHEMA.$defs.Sportanlage.gruppen || [], za) : `<div class="hinweis">Keine weiteren Angaben.</div>`)
        + `</details>`;
    }).join("");
    return `<div class="details-kopf"><h3>${esc(p.name || e.kat)}</h3>`
      + `<button type="button" class="zu" data-zu title="Schließen">×</button></div>`
      + `<div class="knoepfe"><a class="knopf2" href="#" data-karte="${esc(p.id)}">Auf der Karte</a>${vorschlag}</div>`
      + `<label class="hinweis"><input type="checkbox" data-leere${leere ? " checked" : ""}> auch leere Felder zeigen</label>`
      + `<h4>Sportstätte <span class="w">${Math.round(100 * bs)} % der Angaben befüllt</span></h4>`
      + gruppenTabellen(SCHEMA.$defs.Sportstaette.gruppen || [], zeilen)
      + `<table class="meta"><tr><td>ID</td><td><span class="koord">${esc(p.id)}</span></td></tr></table>`
      + `<h4>${e.anlagen.length === 1 ? "1 Sportanlage" : `${zahl(e.anlagen.length)} Sportanlagen`}</h4>`
      + (anlagen || `<div class="hinweis">Keine Sportanlagen eingetragen.</div>`);
  }

  // --- Zeichnen ---
  function zeichne() {
    gezeichnet = true;
    const zaehlen = { staetten: staettenZeilen, anlagen: anlagenZeilen };
    const reiter = [["staetten", "Sportstätten"], ["anlagen", "Sportanlagen"], ["betreiber", "Organisationen"]]
      .map(([k, t]) => `<button type="button" data-teil="${k}" aria-pressed="${z.teil === k}">${t}</button>`).join("");
    let h = `<div class="inhalt liste-inhalt"><h2>Liste: ${esc(gebietName())}</h2><div class="reiter teile">${reiter}</div>`;
    if (z.teil === "betreiber") {
      h += `<div id="l-betreiber"></div></div>`;
      el.innerHTML = h;
      el.querySelector("#l-betreiber").replaceWith(betreiber.el);
      betreiber.zeichne();
    } else {
      const liste = sortiere(zaehlen[z.teil]());
      // Auswahl aus der Adresse, die es im Bestand (des Gebiets) nicht gibt, bleibt sichtbar
      const optionen = (werte, w, leerText) => `<option value="">${leerText}</option>`
        + (w && !werte.includes(w) ? [w, ...werte] : werte)
          .map(v => `<option${v === w ? " selected" : ""}>${esc(v)}</option>`).join("");
      h += `<div class="reiter filter-zeile">`
        + `<input type="search" data-f="q" value="${esc(z.q)}" placeholder="Name, Ort, ID suchen" aria-label="Suchen">`
        + `<select data-f="sportart" aria-label="Sportart">${optionen(SPORTARTEN, z.sportart, "alle Sportarten")}</select>`
        + `<select data-f="kategorie" aria-label="Kategorie">${optionen(KATEGORIEN, z.kategorie, "alle Kategorien")}</select>`
        + `<select data-f="typ" aria-label="Typ der Sportanlage">${optionen(TYPEN, z.typ, "alle Sportanlagen")}</select>`
        + (z.q || z.sportart || z.kategorie || z.typ ? `<button type="button" data-zuruecksetzen>Filter aufheben</button>` : "")
        + `</div><p class="unter">${zahl(liste.length)} ${z.teil === "staetten" ? "Sportstätten" : "Sportanlagen"}`
        + (z.sportart && z.teil === "anlagen" ? ` · Sportart der Anlage, sonst die ihrer Sportstätte (<span class="geerbt">so</span>)` : "")
        + (z.sportart && z.teil === "staetten" ? ` · Sportart der Sportstätte oder einer ihrer Anlagen` : "")
        + ` · Klick auf eine Zeile: alle Angaben</p>`
        + `<div class="liste-raster${z.id ? " mit-details" : ""}"><div>${tabelle(liste)}</div>`
        + `<aside class="details" ${z.id ? "" : "hidden"}>${details()}</aside></div></div>`;
      el.innerHTML = h;
      // gewählte Anlage in der Ansicht rechts zeigen (nur dort scrollen, nicht die Seite)
      const aside = el.querySelector("aside.details"), offen = aside.querySelector("details[open]");
      if (offen) aside.scrollTop = offen.offsetTop - aside.offsetTop - 8;
    }
    merkeZustand();
  }
  // Eingaben: Filter neu anwenden, Fokus im Suchfeld behalten
  el.addEventListener("input", ev => {
    const f = ev.target.dataset.f;
    if (f !== "q") return;
    z.q = ev.target.value; zeigen = LISTE_SCHRITT;
    const pos = ev.target.selectionStart; zeichne();
    const neu = el.querySelector('[data-f="q"]'); neu.focus(); neu.setSelectionRange(pos, pos);
  });
  el.addEventListener("change", ev => {
    const f = ev.target.dataset.f;
    if (f && f !== "q") { z[f] = ev.target.value; zeigen = LISTE_SCHRITT; zeichne(); }
    if (ev.target.matches("[data-leere]")) { z.leere = ev.target.checked; zeichne(); }
  });
  el.addEventListener("click", ev => {
    const t = ev.target;
    const teil = t.closest("[data-teil]:not([data-bearbeiten])");
    if (teil && teil.closest(".teile")) { z.teil = teil.dataset.teil; z.sort = ""; zeigen = LISTE_SCHRITT; zeichne(); return; }
    const karteLink = t.closest("[data-karte]");
    if (karteLink && karteLink.closest(".liste-inhalt") && !karteLink.closest("#l-betreiber, .betreiber")) {
      ev.preventDefault();
      const e = NACH_ID.get(karteLink.dataset.karte);
      if (e) bestand.zeigeEintrag(e);
      return;
    }
    if (t.closest("[data-mehr]")) { zeigen += LISTE_SCHRITT; zeichne(); return; }
    if (t.closest("[data-zuruecksetzen]")) { z.q = z.sportart = z.kategorie = z.typ = ""; zeichne(); return; }
    if (t.closest("[data-zu]")) { z.id = z.anlage = ""; zeichne(); return; }
    const th = t.closest("th[data-sort]");
    if (th && th.closest(".liste")) {
      const k = th.dataset.sort;
      z.ab = z.sort === k ? !z.ab : SPALTEN[z.teil].find(s => s[0] === k)[3] === true;
      z.sort = k; zeichne(); return;
    }
    const zeile = t.closest("table.liste tr.zeile");
    if (zeile) { z.id = zeile.dataset.id; z.anlage = zeile.dataset.anlage || ""; zeichne(); }
  });
  return {
    titel: "Liste",
    zeigen() { el.hidden = false; zeichne(); },
    verbergen() { el.hidden = true; },
    gebietGeaendert() { if (!el.hidden) { zeigen = LISTE_SCHRITT; zeichne(); } },
    zustand() {
      const teile = [["teil", z.teil !== "staetten" ? z.teil : ""], ["q", z.q], ["sportart", z.sportart],
        ["kategorie", z.kategorie], ["typ", z.typ], ["sort", z.sort], ["ab", z.sort && z.ab ? "1" : ""],
        ["id", z.teil !== "betreiber" ? z.id : ""], ["anlage", z.teil !== "betreiber" ? z.anlage : ""]];
      return teile.filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");
    },
    // Alle Angaben einer Sportstätte (aus Popup oder Betreiber-Liste); anlage: Kurz-ID
    details(id, anlage = "") {
      z.id = id; z.anlage = anlage;
      if (z.teil === "betreiber") z.teil = anlage ? "anlagen" : "staetten";
      if (AKTIV === "liste") zeichne(); else zeige("liste");
    },
  };
}
// Link „Alle Angaben“ in Popups der Karte
document.addEventListener("click", ev => {
  const a = ev.target.closest("[data-details]");
  if (!a || !ANSICHTEN.liste) return;
  ev.preventDefault();
  karte.closePopup();
  ANSICHTEN.liste.details(a.dataset.details, a.dataset.anlage || "");
});

// ---------- Teil „Organisationen“: Vereine, Kommunen … als Eigentümer, Betreiber, Nutzer ----
function teilBetreiber(bestand, el) {
  el.className = "betreiber";
  let art = "Verein", rolle = "betreiber", filterText = "", sortierung = { feld: "n", ab: true };
  const offen = new Set();
  // Organisationen einer Sportstätte in der gewählten Rolle: [[Schlüssel, Name, Art]]; was im
  // Verzeichnis steht, fasst alle Schreibweisen unter einem Schlüssel zusammen
  function namenVon(e, r) {
    const roh = r === "nutzer" ? e.p.nutzer || [] : leer(e.p[r]) ? [] : [e.p[r]];
    return roh.map(n => {
      const o = orgVon(n);
      return [o ? "org:" + o.id : schluesselName(n), o ? o.name : n.trim().replace(/\s+/g, " "),
        (r === "nutzer" ? orgArt(n) : artVon(e.p, r)) || "ohne Angabe"];
    });
  }
  function gruppen() {
    const g = new Map();
    for (const e of bestand.eintraege) for (const [s, name, a] of imGebiet(e.p.ars) ? namenVon(e, rolle) : []) {
      if (a !== art) continue;
      let x = g.get(s);
      if (!x) g.set(s, x = { s, namen: {}, liste: [], orte: {}, kats: {} });
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
      for (const [s, , a] of namenVon(e, rolle)) (z[a] ??= new Set()).add(s);
    }
    return z;
  }
  const artZelle = x => {
    const o = x.s.startsWith("org:") ? orgVon(x.name) : null;
    return o ? esc(o.typ || "im Verzeichnis, ohne Art") : `<span class="geerbt" title="nicht im Verzeichnis">geschätzt</span>`;
  };
  function zeichne() {
    const z = zaehle();
    let liste = gruppen();
    if (filterText) liste = liste.filter(x => x.name.toLowerCase().includes(filterText) || x.ort.toLowerCase().includes(filterText));
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
        + `<td class="klein">${artZelle(x)}</td>`
        + `<td class="zahl">${zahl(x.n)}</td><td class="klein">${esc(x.ort)}</td><td class="klein">${esc(x.kat)}</td></tr>`;
      if (auf) {
        const imVerzeichnis = x.s.startsWith("org:");
        h += `<tr class="details"><td colspan="5"><button type="button" class="knopf2" data-karte="${esc(x.s)}">`
          + `Alle ${zahl(x.n)} auf der Karte zeigen</button> `
          + (ANSICHTEN.vorschlag ? `<button type="button" class="knopf2" data-org-aendern="${esc(x.name)}">`
            + (imVerzeichnis ? "Organisation ändern oder löschen" : "ins Verzeichnis eintragen") + `</button>` : "")
          + `<table class="tabelle">`
          + x.liste.slice().sort((a, b) => (a.p.ort || "").localeCompare(b.p.ort || "", "de")).map(e =>
            `<tr><td><a data-i="${bestand.eintraege.indexOf(e)}">${esc(e.p.name || e.kat)}</a></td>`
            + `<td class="klein">${esc(e.p.kategorie || "")}</td><td class="klein">${esc(e.p.adresse || "")}</td></tr>`).join("")
          + `</table></td></tr>`;
      }
      return h;
    }).join("");
    const im = ORGANISATIONEN.length;
    el.innerHTML = `<p class="unter">${esc(gebietName())} · Vereine, Kommunen und andere Organisationen als Eigentümer, `
      + `Betreiber oder Nutzer von Sportstätten. Art aus dem Verzeichnis der Organisationen (${zahl(im)} Einträge), `
      + `sonst aus dem Namen geschätzt („e.V.“, „TuS“, „Ortsgemeinde“ …)`
      + (ANSICHTEN.vorschlag ? ` · <a href="#" data-org-aendern="">neue Organisation eintragen</a>` : "") + `</p>`
      + `<div class="reiter">${reiter}<select aria-label="Rolle">`
      + [["betreiber", "als Betreiber"], ["eigentuemer", "als Eigentümer"], ["nutzer", "als Nutzer"]].map(([k, t]) =>
        `<option value="${k}"${rolle === k ? " selected" : ""}>${t}</option>`).join("") + `</select>`
      + `<input type="search" placeholder="Name oder Ort filtern" value="${esc(filterText)}" aria-label="Filter"></div>`
      + `<table class="tabelle"><thead><tr><th data-sort="name">Name${pfeil("name")}</th><th>Art</th>`
      + `<th class="zahl" data-sort="n">Sportstätten${pfeil("n")}</th><th data-sort="ort">Orte${pfeil("ort")}</th>`
      + `<th data-sort="kat">Kategorien${pfeil("kat")}</th></tr></thead><tbody>${zeilen
        || `<tr><td colspan="5" class="klein">Keine Einträge.</td></tr>`}</tbody></table>`;
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
      bestand.zeigeBetreiber(rolle, x.s, x.name, new Set(x.liste.map(e => e.p.id)));
    }));
    el.querySelectorAll("a[data-i]").forEach(a => a.addEventListener("click", () =>
      ANSICHTEN.liste.details(bestand.eintraege[+a.dataset.i].p.id)));
  }
  return { zeichne, el };
}
