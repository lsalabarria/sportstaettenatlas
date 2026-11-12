// Einstellungen der Webseite. Diese Datei kann direkt auf GitHub bearbeitet werden
// (Stift-Symbol); nach dem Speichern ist die Änderung nach ein bis zwei Minuten online.
// `sportstaettenatlas seite` überschreibt sie nicht.
window.KONFIG = {
  titel: "Sportstättenatlas Rheinland-Pfalz",

  // Link zur LimeSurvey-Umfrage. Der Reiter „Vorschlag“ übergibt die Werte seines Formulars
  // als URL-Parameter (Fragecodes, siehe vorschlag_felder). Leer = Knopf „Weiter zu
  // LimeSurvey“ zeigt nur an, was übertragen würde.
  // Beispiel: "https://limesurvey.hs-koblenz.de/index.php/123456?lang=de"
  vorschlag_url: "",
  // Welche Felder des Formulars in welche Frage der Umfrage gehen: Feld: "Fragecode".
  // Nur die hier genannten werden übertragen. Leer = alle Felder, Fragecode = Feldname.
  // Felder: art id quelle name kategorie betriebsstatus strasse hausnummer adresszusatz plz
  // ort adresse ars gemeinde lat lon lage ("Breite, Länge") oeffentlicher_zugang schulsport
  // zuschauerplaetze sportarten anlagen eigentuemer betreiber website anmerkung geaendert
  // dubletten
  vorschlag_felder: {},

  // Knopf „Bug melden“: neues Ticket im GitHub-Repository mit der Vorlage
  // .github/ISSUE_TEMPLATE/fehler.yml. Leer = kein Knopf.
  // Beispiel: "https://github.com/BENUTZER/sportstaettenatlas/issues/new?template=fehler.yml"
  fehler_url: "",

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
