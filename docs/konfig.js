// Einstellungen der Webseite. Diese Datei kann direkt auf GitHub bearbeitet werden
// (Stift-Symbol); nach dem Speichern ist die Änderung nach ein bis zwei Minuten online.
// `sportstaettenatlas seite` überschreibt sie nicht.
window.KONFIG = {
  titel: "Sportstättenatlas Rheinland-Pfalz",

  // Link zum Meldeformular (LimeSurvey). Leer lassen = kein Knopf „Sportstätte vorschlagen“.
  // Beispiel: "https://limesurvey.hs-koblenz.de/index.php/123456?lang=de"
  vorschlag_url: "",
  // Optional: Name des URL-Parameters, mit dem das Formular die Nummer der Sportstätte
  // vorbelegt (Link „Änderung oder Fehler melden“ bei jeder Sportstätte). Leer = ohne.
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
