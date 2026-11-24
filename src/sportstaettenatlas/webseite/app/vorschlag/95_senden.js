// vorschlag/95_senden.js: Weiter zu LimeSurvey; Ende von ansichtVorschlag (Methoden für die anderen Ansichten).
// Teil des Rumpfs von ansichtVorschlag – nur zusammen mit den anderen Teilen gültig
// (app/__init__.py setzt vorschlag/*.js der Reihe nach zu app/vorschlag.js zusammen).
  // --- Weiter zu LimeSurvey ---
  function weiter() {
    pruefe();
    const v = werte(), fehler = [];
    if (unter) return uebernimmUnter(v);
    if (v.art === "organisation") return weiterOrg(v);
    if (v.art === "sportkomplex") return weiterKomplex(v);
    if (v.art === "stuetzpunkt") return weiterStuetzpunkt(v);
    if (v.art !== "neu" && !original) fehler.push("Welche Sportstätte soll geändert werden? (oben auswählen)");
    fehler.push(...regelVerstoesse(v));
    if (enthaeltEmail(v)) fehler.push("Bitte keine E-Mail-Adressen eintragen");
    const alle = aenderungen(v).map(([k]) => k);
    const geaendert = alle.filter(k => k !== "anlagen" && k !== "neuer_sportkomplex");
    if (original && !alle.length && !v.anmerkung) {
      fehler.push("Änderung: mindestens ein Feld oder eine Sportanlage ändern oder eine Anmerkung schreiben");
    }
    if (v.neuer_sportkomplex) fehler.push(...nkFehler(v));
    const cb = el.querySelector("#v-keine-doppelung");
    if (v.art === "neu" && dubletten.length && !(cb && cb.checked)) {
      fehler.push("Mögliche Doppelung prüfen (rechts) und bestätigen, dass es eine andere Sportstätte ist");
    }
    const daten = vorschlagDaten(v, geaendert, v.art === "neu" && cb && cb.checked ? dubletten.map(d => d.e.p.id) : []);
    sende(daten, v, fehler);
  }
  // Vorschlag als JSON an LimeSurvey (Frage data), Anmerkung in kommentar
  function sende(daten, v, fehler) {
    if (!daten.loeschen) {
      const orgs = neueOrgDaten(v, fehler);
      if (orgs.length) daten.neue_organisationen = orgs;
    }
    const params = new URLSearchParams();
    params.set(VORSCHLAG_FRAGEN.data, JSON.stringify(daten));
    if (v.anmerkung && VORSCHLAG_FRAGEN.kommentar) params.set(VORSCHLAG_FRAGEN.kommentar, v.anmerkung);
    const u = KONFIG.vorschlag_url ? KONFIG.vorschlag_url + (KONFIG.vorschlag_url.includes("?") ? "&" : "?")
      + "newtest=Y&" + params : "";
    if (u.length > URL_HOECHSTENS) {
      fehler.push("Der Vorschlag ist zu umfangreich für eine Übergabe – bitte auf mehrere Vorschläge aufteilen "
        + "(z. B. erst die Angaben, dann die Sportanlagen, oder neue Sportstätten einzeln).");
    }
    zeigeFehlerliste(fehler);
    if (fehler.length) return;
    const ausgabe = el.querySelector("#v-ausgabe");
    if (u) {
      ausgabe.innerHTML = `<div class="ok">Die Umfrage wurde in einem neuen Tab geöffnet. Falls nicht: `
        + `<a href="${esc(u)}" target="_blank" rel="noopener">hier weiter zu LimeSurvey</a>.</div>`;
      window.open(u, "_blank", "noopener");
    } else {
      ausgabe.innerHTML = `<div class="warnung"><b>Der Link zur LimeSurvey-Umfrage ist noch nicht eingetragen</b> `
        + `(in <code>konfig.js</code>: <code>vorschlag_url</code>). Übertragen würde in der Frage `
        + `<code>${esc(VORSCHLAG_FRAGEN.data)}</code>:<pre class="umbruch">${esc(JSON.stringify(daten, null, 2))}</pre>`
        + (v.anmerkung ? `und in <code>${esc(VORSCHLAG_FRAGEN.kommentar)}</code>: ${esc(v.anmerkung)}` : "") + `</div>`;
      ausgabe.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }
  function weiterOrg(v) {
    const fehler = orgFehler(v.organisation, v.loeschen);
    const geaendert = orgAenderungen(v.organisation);
    if (orgOriginal && orgOriginal.imVerzeichnis && !v.loeschen && !geaendert.length && !v.anmerkung) {
      fehler.push("Änderung: mindestens ein Feld ändern, löschen wählen oder eine Anmerkung schreiben");
    }
    if (enthaeltEmail(v.organisation)) fehler.push("Bitte keine E-Mail-Adressen eintragen");
    const daten = { version: 1, art: "organisation" };
    if (orgOriginal && orgOriginal.imVerzeichnis) daten.organisation_id = orgOriginal.o.id;
    if (v.loeschen) daten.loeschen = true;
    else daten.organisation = v.organisation;
    if (!v.loeschen && geaendert.length && orgOriginal) daten.geaendert = geaendert;
    sende(daten, v, fehler);
  }
  let gebaut = false;
  return {
    titel: "Vorschlag",
    zeigen() {
      el.hidden = false;
      if (!gebaut) { baue(); gebaut = true; neu(); }
      starteKarte();
      if (marke) marke.addTo(vkarte);
      pruefe();
    },
    verbergen() { el.hidden = true; },
    hat: id => NACH_ID.has(id),
    lage: (lat, lon) => setzeLage(lat, lon),  // wie ein Klick in die Karte
    neu(vorgabe) { zeige("vorschlag").then(() => { neu(vorgabe); pruefe(); el.scrollTop = 0; }); },
    bearbeite(id, art) { zeige("vorschlag").then(() => { bearbeite(id, art); pruefe(); el.scrollTop = 0; }); },
    // Sportkomplex ändern (ID) oder neu, vorbelegt mit Sportstätten; von einer Sportstätte aus:
    // ihr Komplex, sonst ein neuer mit ihr
    komplex(id, vorbelegt = []) {
      zeige("vorschlag").then(() => {
        F("art").value = "sportkomplex"; waehleKomplex(id || null, vorbelegt);
        zeigeTeile(); zeigeGewaehlt(); el.querySelector("#v-ausgabe").innerHTML = "";
        el.querySelector("#v-fehler").hidden = true; el.scrollTop = 0;
      });
    },
    // Stützpunkt ändern (ID) oder neu, vorbelegt mit Sportstätten; von einer Sportstätte aus:
    // ihr einziger Stützpunkt, sonst ein neuer mit ihr
    stuetzpunkt(id, vorbelegt = []) {
      zeige("vorschlag").then(() => {
        F("art").value = "stuetzpunkt"; waehleStuetzpunkt(id || null, vorbelegt);
        zeigeTeile(); zeigeGewaehlt(); el.querySelector("#v-ausgabe").innerHTML = "";
        el.querySelector("#v-fehler").hidden = true; el.scrollTop = 0;
      });
    },
    stuetzpunktVon(sid) {
      const sp = STP_JE_STAETTE.get(sid) || [];
      this.stuetzpunkt(sp.length === 1 ? sp[0].id : null, sp.length === 1 ? [] : [sid]);
    },
    komplexVon(sid) {
      const e = NACH_ID.get(sid);
      this.komplex(e && e.p.sportkomplex ? e.p.sportkomplex : null, e && !e.p.sportkomplex ? [sid] : []);
    },
    // Organisation ändern oder löschen (Name wie bei den Sportstätten); ohne Namen: neue
    organisation(name) {
      zeige("vorschlag").then(() => {
        F("art").value = "organisation"; waehleOrg(name || null);
        zeigeTeile(); zeigeGewaehlt(); el.querySelector("#v-ausgabe").innerHTML = "";
        el.querySelector("#v-fehler").hidden = true; el.scrollTop = 0;
      });
    },
  };
}
