// Einstellungen der Webseite. Diese Datei kann direkt auf GitHub bearbeitet werden
// (Stift-Symbol); nach dem Speichern ist die Änderung nach ein bis zwei Minuten online.
// `sportstaettenatlas seite` überschreibt sie nicht.
window.KONFIG = {
  titel: "Sportstättenatlas Rheinland-Pfalz",

  // Link zur LimeSurvey-Umfrage (sportstaette_vorschlagen.lss). „Weiter zu LimeSurvey“ im
  // Reiter „Vorschlag“ öffnet sie und schreibt den ganzen Vorschlag als JSON in die Frage
  // „data“, die Anmerkung in die Frage „kommentar“. Aufbau des JSON: Modell „Vorschlag“ in
  // daten/README.md. Ändert sich das Datenmodell, bleibt die Umfrage, wie sie ist.
  // Leer = der Knopf zeigt nur an, was übertragen würde.
  // Beispiel: "https://limesurvey.hs-koblenz.de/index.php/123456?lang=de"
  vorschlag_url: "",
  // Nur nötig, wenn die Fragen in der Umfrage anders heißen: { data: "…", kommentar: "…" }
  vorschlag_felder: { data: "data", kommentar: "kommentar" },

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

  // Ortssuche über OpenStreetMap (Nominatim). false = nur Suche in den eigenen Daten.
  ortssuche: true,
};
