// Einstellungen der Webseite. Diese Datei kann direkt auf GitHub bearbeitet werden
// (Stift-Symbol); nach dem Speichern ist die Änderung nach ein bis zwei Minuten online.
// `sportstaettenatlas seite` überschreibt sie nicht.
window.KONFIG = {
  titel: "Sportstättenatlas Rheinland-Pfalz",

  // LimeSurvey-Umfrage für Vorschläge. „Weiter zu LimeSurvey“ im Reiter „Vorschlag“ öffnet
  // sie und füllt die Fragen mit den Werten des Formulars (newtest=Y hängt die Seite an).
  vorschlag_url: "https://limesurvey.hs-koblenz.de/index.php/992924?lang=de",
  // Welches Feld des Formulars in welche Frage geht: Feld: "Fragecode". Nur diese Felder
  // werden übertragen. Weitere Felder: art id quelle strasse hausnummer adresszusatz plz ort
  // adresse ars gemeinde lat lon oeffentlicher_zugang schulsport zuschauerplaetze sportarten
  // anlagen eigentuemer betreiber website anmerkung geaendert dubletten
  vorschlag_felder: {
    name: "Q00",              // Name der Sportstätte
    kategorie: "G01Q02",      // Sportstättenkategorie
    betriebsstatus: "G01Q03", // Betriebsstatus
    lage: "G01Q04",           // Lage als "Breite, Länge"
  },
  // Nur für die Karte ohne Bestand (eine Datei): Parameter für die Kennung der Sportstätte
  vorschlag_parameter: "",

  // Pflichtangaben für öffentliche Webseiten. Entwürfe liegen als impressum.html und
  // datenschutz.html bei (gelb markierte Stellen ergänzen). Alternativ hier die Adressen
  // der Seiten der Hochschule eintragen.
  impressum_url: "impressum.html",
  datenschutz_url: "datenschutz.html",

  // Lizenz der Daten (Download-Seite). Vorschlag: dieselbe Lizenz wie die ALKIS-Daten.
  // Vorher klären, ob die Rechte am bisherigen Atlas-Bestand das zulassen.
  lizenz: "Datenlizenz Deutschland – Namensnennung – Version 2.0 (dl-de/by-2-0)",
  lizenz_url: "https://www.govdata.de/dl-de/by-2-0",
  // So sollen Nutzende die Quelle nennen (ergänzt um den Quellenvermerk der ALKIS-Daten)
  namensnennung: "Sportstättenatlas Rheinland-Pfalz",

  // Ortssuche über OpenStreetMap (Nominatim/Photon). false = nur Suche in den eigenen Daten.
  ortssuche: true,
};
