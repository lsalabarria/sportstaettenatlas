// Gruppen der Sportanlagen (aus modell/anlagen.py; stehen in bestand.geojson).
export let ANLAGEN_GRUPPEN = [], ANLAGEN_TYPEN = {};
export function setzeAnlagengruppen(fc) {
  ANLAGEN_GRUPPEN = fc.anlagengruppen || [["weitere", "Weitere"]];
  ANLAGEN_TYPEN = fc.anlagentypen || {};
}
export function anlagenGruppe(t) { return ANLAGEN_TYPEN[t] || "weitere"; }
export function gruppenText(g) { const x = ANLAGEN_GRUPPEN.find(y => y[0] === g); return x ? x[1] : g; }
