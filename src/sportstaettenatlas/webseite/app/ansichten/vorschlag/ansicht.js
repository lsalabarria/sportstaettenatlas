// Ansicht „Vorschlag“: Sportstätte mit ihren Sportanlagen neu eintragen, die Angaben einer
// Sportstätte ändern oder ihre Sportanlagen ändern (hinzufügen, ändern, entfernen); dazu
// Sportkomplexe, Stützpunkte und Organisationen.
// Felder, Beschriftungen, Auswahllisten und Regeln kommen aus dem Datenmodell
// (daten/schema.json, erzeugt aus src/sportstaettenatlas/modell/) – ein neues Feld dort
// erscheint hier von selbst. Das Formular prüft die Regeln und auf Doppelungen und öffnet
// dann die LimeSurvey-Umfrage (konfig.js: vorschlag_url): Der ganze Vorschlag steht als JSON
// (Modell „Vorschlag“) in der Frage „data“, die Anmerkung in der Frage „kommentar“.
// Teile: formular.js (Felder, Aufbau), anlagen.js, stuetzpunkte.js, sportkomplexe.js,
// organisationen.js, karte.js, werte.js, neue_objekte.js, pruefung.js, senden.js; alle
// lesen und ändern den Zustand z (zustand.js), den ansichtVorschlag anlegt.
import { z } from "./zustand.js";
import { starte as starteFormular, F, baue } from "./formular.js";
import { starte as starteOrganisationen, waehleOrg } from "./organisationen.js";
import { starte as starteNeueObjekte } from "./neue_objekte.js";
import { starte as starteSenden } from "./senden.js";
import { zeigeTeile } from "./anlagen.js";
import { setzeLage, starteKarte } from "./karte.js";
import { pruefe } from "./pruefung.js";
import { waehleKomplex } from "./sportkomplexe.js";
import { waehleStuetzpunkt } from "./stuetzpunkte.js";
import { bearbeite, neu, zeigeGewaehlt } from "./werte.js";
import { STP_JE_STAETTE } from "../../daten/stuetzpunkte.js";
import { zeige } from "../umschalten.js";

export function ansichtVorschlag(bestand) {
  z.bestand = bestand;
  starteFormular();
  starteOrganisationen();
  starteNeueObjekte();
  starteSenden();

  return {
    titel: "Vorschlag",
    zeigen() {
      z.el.hidden = false;
      if (!z.gebaut) { baue(); z.gebaut = true; neu(); }
      starteKarte();
      if (z.marke) z.marke.addTo(z.vkarte);
      pruefe();
    },
    verbergen() { z.el.hidden = true; },
    hat: id => z.NACH_ID.has(id),
    lage: (lat, lon) => setzeLage(lat, lon),  // wie ein Klick in die Karte
    neu(vorgabe) { zeige("vorschlag").then(() => { neu(vorgabe); pruefe(); z.el.scrollTop = 0; }); },
    bearbeite(id, art) { zeige("vorschlag").then(() => { bearbeite(id, art); pruefe(); z.el.scrollTop = 0; }); },
    // Sportkomplex ändern (ID) oder neu, vorbelegt mit Sportstätten; von einer Sportstätte aus:
    // ihr Komplex, sonst ein neuer mit ihr
    komplex(id, vorbelegt = []) {
      zeige("vorschlag").then(() => {
        F("art").value = "sportkomplex"; waehleKomplex(id || null, vorbelegt);
        zeigeTeile(); zeigeGewaehlt(); z.el.querySelector("#v-ausgabe").innerHTML = "";
        z.el.querySelector("#v-fehler").hidden = true; z.el.scrollTop = 0;
      });
    },
    // Stützpunkt ändern (ID) oder neu, vorbelegt mit Sportstätten; von einer Sportstätte aus:
    // ihr einziger Stützpunkt, sonst ein neuer mit ihr
    stuetzpunkt(id, vorbelegt = []) {
      zeige("vorschlag").then(() => {
        F("art").value = "stuetzpunkt"; waehleStuetzpunkt(id || null, vorbelegt);
        zeigeTeile(); zeigeGewaehlt(); z.el.querySelector("#v-ausgabe").innerHTML = "";
        z.el.querySelector("#v-fehler").hidden = true; z.el.scrollTop = 0;
      });
    },
    stuetzpunktVon(sid) {
      const sp = STP_JE_STAETTE.get(sid) || [];
      this.stuetzpunkt(sp.length === 1 ? sp[0].id : null, sp.length === 1 ? [] : [sid]);
    },
    komplexVon(sid) {
      const e = z.NACH_ID.get(sid);
      this.komplex(e && e.p.sportkomplex ? e.p.sportkomplex : null, e && !e.p.sportkomplex ? [sid] : []);
    },
    // Organisation ändern oder löschen (Name wie bei den Sportstätten); ohne Namen: neue
    organisation(name) {
      zeige("vorschlag").then(() => {
        F("art").value = "organisation"; waehleOrg(name || null);
        zeigeTeile(); zeigeGewaehlt(); z.el.querySelector("#v-ausgabe").innerHTML = "";
        z.el.querySelector("#v-fehler").hidden = true; z.el.scrollTop = 0;
      });
    },
  };
}
