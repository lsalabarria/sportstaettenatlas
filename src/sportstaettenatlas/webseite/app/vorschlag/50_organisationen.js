// vorschlag/50_organisationen.js: Organisationen: Suche im Verzeichnis, Nutzung, Änderungen.
// Teil des Rumpfs von ansichtVorschlag – nur zusammen mit den anderen Teilen gültig
// (app/__init__.py setzt vorschlag/*.js der Reihe nach zu app/vorschlag.js zusammen).
  // --- Organisationen ---
  // Wer nennt welche Organisation? Einmal aufgebaut: Name (schluesselName) → Rolle → Sportstätten
  let nutzungsIndex = null, orgListeCache = null;
  function index() {
    if (nutzungsIndex) return nutzungsIndex;
    nutzungsIndex = new Map();
    const dazu = (name, rolle, e) => {
      const k = schluesselName(name);
      if (!k) return;
      if (!nutzungsIndex.has(k)) nutzungsIndex.set(k, { eigentuemer: new Set(), betreiber: new Set(), nutzer: new Set() });
      nutzungsIndex.get(k)[rolle].add(e);
    };
    for (const e of bestand.eintraege) {
      dazu(e.p.eigentuemer, "eigentuemer", e);
      dazu(e.p.betreiber, "betreiber", e);
      for (const n of e.p.nutzer || []) dazu(n, "nutzer", e);
    }
    return nutzungsIndex;
  }
  // Verzeichnis und Namen aus dem Bestand, die (noch) nicht darin stehen (einmal berechnet)
  function orgListe() {
    if (orgListeCache) return orgListeCache;
    const eintrag = (name, o) => {
      const alle = [name, ...(o ? o.weitere_namen || [] : [])];
      return { name, o, alle, namen: alle.map(schluesselName), n: nutzung(name).n };
    };
    // dazu Namen, die Sportstätten nennen, die aber nicht im Verzeichnis stehen (häufigste
    // Schreibweise)
    const bestandNamen = haeufig(bestand.eintraege.flatMap(e => [e.p.betreiber, e.p.eigentuemer, ...(e.p.nutzer || [])]));
    return orgListeCache = [...ORGANISATIONEN.map(o => eintrag(o.name, o)),
      ...bestandNamen.filter(([n]) => !orgVon(n)).map(([n]) => eintrag(n, null))];
  }
  // Organisationen zu einem Suchtext, für alle Eingaben gleich: genauer Name vor Anfang des
  // Namens vor Wortanfängen vor Teilen davon; weitere Schreibweisen zählen etwas weniger. Bei
  // gleichem Rang zuerst, was Sportstätten schon nennen, dann der kürzere Name.
  function sucheOrg(text, n = 8) {
    const q = schluesselName(text), worte = q.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
    if (!worte.length) return [];
    // „Ortsgemeinde Berg (VG Altenahr)“ zählt für „berg“ wie ein genauer Name
    const kern = k => k.replace(/^(ortsgemeinde|verbandsgemeinde|gemeinde|stadt|landkreis|kreis) /, "");
    const ganz = (k, w) => k === w || (k.startsWith(w) && /[^\p{L}\p{N}]/u.test(k[w.length]));
    const rang = k => {
      if (k === q) return 0;
      if (ganz(kern(k), q)) return 1;
      if (k.startsWith(q) || kern(k).startsWith(q)) return 2;
      const teile = k.split(/[^\p{L}\p{N}]+/u);
      if (worte.every(w => teile.includes(w))) return 3;
      if (worte.every(w => teile.some(t => t.startsWith(w)))) return 4;
      return worte.every(w => k.includes(w)) ? 5 : 9;
    };
    const out = [];
    for (const x of orgListe()) {
      let best = 9, alias = "";
      x.namen.forEach((k, i) => {
        const r = rang(k) + (i ? 0.5 : 0);
        if (r < best) { best = r; alias = i ? x.alle[i] : ""; }
      });
      if (best < 9) out.push({ ...x, rang: Math.floor(best), alias });
    }
    return out.sort((a, b) => a.rang - b.rang || b.n - a.n || a.name.length - b.name.length
      || a.name.localeCompare(b.name, "de")).slice(0, n);
  }
  const orgZusatz = x => verbinde([x.alias && `auch „${x.alias}“`,
    x.o ? x.o.typ || "im Verzeichnis, ohne Art" : "noch nicht im Verzeichnis", nutzungText(x.name)]);
  // Vorschlagsliste unter jeder Eingabe für eine Organisation (data-orgs): Pfeiltasten, Enter,
  // Klick; Esc oder Verlassen schließt sie
  function orgListeVon(eing) {
    let ul = eing.parentElement.querySelector(":scope > ul.org-vorschlaege");
    if (!ul) {
      ul = document.createElement("ul"); ul.className = "treffer org-vorschlaege"; ul.hidden = true;
      eing.insertAdjacentElement("afterend", ul);
    }
    return ul;
  }
  function zeigeOrgVorschlaege(eing) {
    const ul = orgListeVon(eing), t = sucheOrg(eing.value);
    ul.innerHTML = t.map(x => `<li data-name="${esc(x.name)}">${esc(x.name)}<small>${esc(orgZusatz(x))}</small></li>`).join("");
    ul.hidden = !t.length;
  }
  function waehleOrgVorschlag(eing, name) {
    eing.value = name;
    const box = eing.closest("[data-chips]");
    if (box) box.querySelector("button").click();  // Nutzer: gleich als Chip übernehmen
    else eing.dispatchEvent(new Event("input", { bubbles: true }));
    orgListeVon(eing).hidden = true;  // auch wenn das input-Ereignis sie wieder geöffnet hat
  }
  // Wie oft nennen Sportstätten diese Organisation (alle Schreibweisen)?
  function nutzung(name) {
    const o = orgVon(name), ix = index();
    const namen = new Set([name, ...(o ? [o.name, ...(o.weitere_namen || [])] : [])].map(schluesselName));
    const je = { eigentuemer: new Set(), betreiber: new Set(), nutzer: new Set() }, alle = new Set();
    for (const k of namen) {
      const x = ix.get(k);
      if (x) for (const r in je) for (const e of x[r]) { je[r].add(e); alle.add(e); }
    }
    return { eigentuemer: je.eigentuemer.size, betreiber: je.betreiber.size, nutzer: je.nutzer.size, n: alle.size };
  }
  function nutzungText(name) {
    const z = nutzung(name);
    return z.n ? `${zahl(z.n)} Sportstätten (` + [["eigentuemer", "Eigentümer"], ["betreiber", "Betreiber"], ["nutzer", "Nutzer"]]
      .filter(([k]) => z[k]).map(([k, t]) => `${t} ${zahl(z[k])}`).join(", ") + ")" : "keine Sportstätte nennt sie";
  }
  // Organisation zum Ändern wählen (Name aus der Liste) oder null für eine neue
  function waehleOrg(name) {
    const o = name ? orgVon(name) : null;
    orgOriginal = name ? { o: o || { name }, imVerzeichnis: !!o } : null;
    const werte = orgOriginal ? orgOriginal.o : {};
    for (const f of ORG_FELDER) {
      const e = F(f.pfad), w = werte[f.k];
      e.value = leer(w) ? "" : Array.isArray(w) ? w.join(", ") : w;
    }
    if (F("org-loeschen")) F("org-loeschen").checked = false;
    const g = el.querySelector("#v-org-gewaehlt");
    g.innerHTML = orgOriginal ? `<div class="chip">${orgOriginal.imVerzeichnis ? "Sie ändern" : "Noch nicht im Verzeichnis, Sie tragen ein"}: `
      + `<b>${esc(orgOriginal.o.name)}</b> <span class="q">${esc(nutzungText(orgOriginal.o.name))}</span>`
      + ` <button type="button">stattdessen eine neue</button></div>` : "";
    const b = g.querySelector("button");
    if (b) b.addEventListener("click", () => { waehleOrg(null); zeigeTeile(); planePruefung(); });
  }
  function orgWerte() {
    const o = {};
    for (const f of ORG_FELDER) {
      const x = String(F(f.pfad).value || "").trim();
      if (x) o[f.k] = f.t.type === "array" ? listeAus(x) : x;
    }
    return o;
  }
  function orgFehler(o, loeschen) {
    if (loeschen) return [];
    const fehler = [];
    for (const f of ORG_FELDER) fehler.push(...regelFehler(f, o[f.k], f.p.title));
    fehler.push(...regelnZwischen("Organisation", o));
    // Name oder Schreibweise schon bei einer anderen Organisation im Verzeichnis?
    const eigene = orgOriginal && orgOriginal.imVerzeichnis ? orgOriginal.o.id : null;
    for (const n of [o.name, ...(o.weitere_namen || [])]) {
      const andere = orgVon(n);
      if (n && andere && andere.id !== eigene) fehler.push(`„${n}“ steht schon im Verzeichnis (${andere.name}) – bitte oben suchen und ändern`);
    }
    return fehler;
  }
  function orgAenderungen(o) {
    if (!orgOriginal) return Object.keys(o);
    const alt = orgOriginal.o, text = x => Array.isArray(x) ? x.join(", ") : (x || "");
    return ORG_FELDER.map(f => f.k).filter(k => text(alt[k]) !== text(o[k]));
  }

