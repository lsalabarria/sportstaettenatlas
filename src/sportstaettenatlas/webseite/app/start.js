// Start der Seite: Daten laden, Ansichten anlegen, die gewünschte zeigen (Einstieg).
import { ANALYSEN, ansichtAnalysen } from "./ansichten/analysen.js";
import { ansichtBestand } from "./ansichten/bestand.js";
import { ansichtListe } from "./ansichten/liste.js";
import { ansichtUebersicht } from "./ansichten/uebersicht.js";
import {
  AKTIV, ANSICHTEN, STANDARD, knoepfe, setzeStandard, zeige,
} from "./ansichten/umschalten.js";
import { ansichtVorschlag } from "./ansichten/vorschlag/ansicht.js";
import { setzeAnlagengruppen } from "./daten/anlagen.js";
import { setzeOrganisationen } from "./daten/organisationen.js";
import { setzeSchema } from "./daten/schema.js";
import { setzeSportkomplexe } from "./daten/sportkomplexe.js";
import { setzeStuetzpunkte } from "./daten/stuetzpunkte.js";
import {
  GEBIET, GEBIET_RAND, NACH_S, grenzenVon, setzeGebiet, starteGebietswahl,
} from "./karte/gebiete.js";
import { karte } from "./karte/karte.js";
import { fertig, holeJson, kopfzeile, ladeFehler, zeigeFehler } from "./seite.js";

// auch nach Zoom; lädt Flächen des neuen Ausschnitts
karte.on("moveend", () => { const a = ANSICHTEN[AKTIV]; if (a && a.aktualisiere) a.aktualisiere(); });

// ---------- Start -----------------------------------------------------------------------
(async function start() {
  let bestand, gebiete, analysen, schema, organisationen, komplexe, stuetzpunkte;
  try {
    [bestand, gebiete, analysen, schema, organisationen, komplexe, stuetzpunkte] = await Promise.all(["bestand.geojson",
      "gebiete.json", "analysen/index.json", "schema.json", "organisationen.json",
      "sportkomplexe.json", "stuetzpunkte.json"].map(holeJson));
  } catch (fehler) {
    ladeFehler(fehler);
    throw fehler;
  }
  if (schema) setzeSchema(schema);
  setzeOrganisationen(organisationen && organisationen.eintraege);
  setzeSportkomplexe(komplexe && komplexe.eintraege, bestand && bestand.features);
  setzeStuetzpunkte(stuetzpunkte && stuetzpunkte.eintraege);
  const hash = new URLSearchParams(location.hash.slice(1));
  starteGebietswahl(gebiete);
  if (bestand && bestand.features.length) {
    setzeAnlagengruppen(bestand);
    const b = ANSICHTEN.bestand = ansichtBestand(bestand);
    ANSICHTEN.liste = ansichtListe(b);
    ANSICHTEN.uebersicht = ansichtUebersicht(b);
    ANSICHTEN.vorschlag = ansichtVorschlag(b);
  }
  const namen = (analysen && analysen.analysen || []).map(a => a.name).filter(n => ANALYSEN[n]);
  if (namen.length) ANSICHTEN.analysen = ansichtAnalysen(namen, hash.get("analyse"));
  setzeStandard(Object.keys(ANSICHTEN)[0]);
  if (!STANDARD) { zeigeFehler("Keine Daten vorhanden (daten/bestand.geojson fehlt)."); return; }
  knoepfe();
  kopfzeile(!!ANSICHTEN.vorschlag);
  fertig();
  const g = hash.get("gebiet");
  if (g && NACH_S[g]) setzeGebiet(NACH_S[g], false);
  const gewuenscht = hash.get("ansicht");
  await zeige(ANSICHTEN[gewuenscht] ? gewuenscht : STANDARD);
  if (GEBIET) karte.fitBounds(grenzenVon(GEBIET), GEBIET_RAND);
})();
