// Einstellungen der Webseite. Diese Datei kann direkt auf GitHub bearbeitet werden
// (Stift-Symbol); nach dem Speichern ist die Änderung nach ein bis zwei Minuten online.
// `sportstaettenatlas seite` überschreibt sie nicht.
window.KONFIG = {
  titel: "Sportstättenatlas Rheinland-Pfalz",

  // LimeSurvey-Umfrage für Vorschläge. „Weiter zu LimeSurvey“ im Reiter „Vorschlag“ öffnet
  // sie und füllt die Fragen mit den Werten des Formulars (newtest=Y hängt die Seite an).
  vorschlag_url: "https://limesurvey.hs-koblenz.de/index.php/718524?lang=de",
  // Welches Feld des Formulars in welche Frage geht: Feld: "Fragecode". Nur diese Felder
  // werden übertragen (passend zur Umfrage sportstaette_vorschlagen.lss).
  vorschlag_felder: {
    art: "SSart", id: "SSid", geaendert: "SSgeaendert", quelle: "SSquelle",
    name: "SSname", kategorie: "SSkategorie", betriebsstatus: "SSstatus",
    strasse: "SSstrasse", hausnummer: "SShausnr", adresszusatz: "SSzusatz",
    plz: "SSplz", ort: "SSort", gemeinde: "SSgemeinde", ars: "SSars",
    lat: "SSlat", lon: "SSlon",
    oeffentlicher_zugang: "SSoeffentlich", schulsport: "SSschulsport",
    zuschauerplaetze: "SSzuschauer", sportarten: "SSsportarten", anlagen: "SSanlagen",
    eigentuemer: "SSeigentuemer", betreiber: "SSbetreiber", website: "SSwebsite",
    anmerkung: "SSanmerkung", dubletten: "SSdubletten",
  },

  // Knopf „Bug melden“: neues Ticket auf GitHub mit der Vorlage .github/ISSUE_TEMPLATE/fehler.yml.
  // Leer = kein Knopf.
  fehler_url: "https://github.com/lsalabarria/sportstaettenatlas/issues/new?template=fehler.yml",

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
