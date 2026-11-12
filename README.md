# Sportstättenatlas Rheinland-Pfalz

Ein offener Sportstättenatlas: Der **Datenbestand** liegt als eine JSON-Datei je Sportstätte
im Git, eine **statische Webseite** auf GitHub Pages zeigt ihn als Karte, Liste und
Übersicht und nimmt Vorschläge über LimeSurvey entgegen. **Analysen** reichern den Bestand
an oder prüfen ihn – zuerst der Abgleich mit dem Liegenschaftskataster (ALKIS). Sie rechnen
auf dem eigenen Rechner; ihre Ergebnisse erscheinen auf der Webseite im Reiter „Analysen“.

**Begriffe**
- Eine **Sportstätte** ist der Standort, z. B. ein Sportpark, ein Schulsportzentrum oder ein
  Freibad. Name, Betreiber, Adresse, Website und Öffnungszeiten gehören zur Sportstätte und
  gelten für alle ihre Anlagen.
- Eine **Sportanlage** ist eine einzelne Einheit einer Sportstätte, z. B. eine Halle, ein
  Spielfeld oder ein Becken. Typ, Belag, Sportart und Fläche gehören zur Anlage. Jede
  Anlage gehört über `sportstaette_id` zu genau einer Sportstätte.

## Aufbau

```
daten/                       Datenbestand: eine JSON-Datei je Sportstätte (daten/RP/RP-12345.json)
docs/                        Webseite für GitHub Pages (von `seite` erzeugt, siehe unten)
data/                        Arbeitsordner der Analysen: raw/, cache/, out/ (nicht im Git)
.github/ISSUE_TEMPLATE/      Vorlage für „Bug melden“ (fehler.yml)
src/sportstaettenatlas/
  cli.py                     Befehle `bestand`, `seite` und die Befehlsgruppen der Analysen
  bestand.py                 Datenbestand lesen und schreiben, Atlas-Export überführen
  atlas.py                   Exporte des bisherigen Sportstättenatlas RLP lesen
  gebiete.py                 Verwaltungsgebiete (VG250 des BKG) und Zuordnung zur Gemeinde
  seite.py                   Webseite nach docs/ schreiben
  http.py, hilfen.py         Webanfragen mit Zwischenspeicher, kleine Hilfen
  web/                       die Webseite selbst: index.html, stil.css, JavaScript, Vorlagen
  analysen/
    alkis/                   Analyse „ALKIS-Abgleich“ (Befehle `sportstaettenatlas alkis …`)
tests/
```

## Installation

```bash
uv sync
```

## Datenbestand im Git (`bestand`)

Der Bestand liegt als **eine JSON-Datei je Sportstätte** im Ordner `daten/`
(`daten/RP/RP-12345.json`). Ab der ersten Überführung sind diese Dateien die Quelle:
Änderungen werden dort vorgenommen – direkt auf GitHub oder per Pull Request – und sind
in der Git-Historie nachvollziehbar.

```bash
uv run sportstaettenatlas bestand pfad/zum/atlas-export.csv     # erstmalig überführen
git add daten && git commit -m "Bestand aus dem Atlas-Export übernommen"
```

- Die ID setzt sich aus Land und Atlas-ID zusammen (`RP-12345`) und bleibt stabil.
- **Standard (`--modus neu`)**: Nur fehlende Sportstätten werden angelegt; vorhandene
  Dateien werden nie verändert, weil sie inzwischen gepflegt sein können.
  `--modus aktualisieren` überschreibt sie mit dem Stand der Quelle (Änderungen zeigt
  danach `git diff`).
- Dateien, die in der Quelle fehlen, werden gezählt, aber nicht gelöscht.
- Kontaktdaten werden nie übernommen: Die Spalte E-Mail wird nicht gelesen, und jeder
  Wert, der eine E-Mail-Adresse enthält, entfällt.
- Im Export stehen unter `Latitude`/`Longitude` UTM-Werte (Hochwert/Rechtswert); das wird
  erkannt und umgerechnet.
- Der Export selbst gehört nicht ins Repository (er enthält Kontaktdaten).
- Weitere Quellformate: in `src/sportstaettenatlas/bestand.py` eine Lesefunktion
  ergänzen und in `LESER` eintragen (`--format`).

## Webseite veröffentlichen (GitHub Pages)

`seite` erzeugt aus dem Datenbestand (`daten/`) und den Ergebnissen der Analysen eine
statische Webseite im Ordner `docs/`. GitHub Pages liefert diesen Ordner direkt aus – ohne
Server und Datenbank.

```bash
uv run sportstaettenatlas seite              # docs/ erzeugen bzw. aktualisieren
uv run sportstaettenatlas seite --vorschau   # danach lokal ansehen (http://localhost:8000)
git add docs && git commit -m "Daten aktualisiert" && git push
```

Die Seite hat fünf Reiter. Reiter und Gebiet stehen in der Adresse, z. B.
`…/#ansicht=uebersicht&gebiet=07137`, und lassen sich so verlinken:

| Reiter | Inhalt |
|---|---|
| **Karte** (Start) | nur der Datenbestand aus `daten/`; Filter nach Kategorie, Betreiber-Art und Sportarten |
| **Liste** | Vereine und Kommunen als Betreiber bzw. Eigentümer, sortier- und filterbar; ein Klick zeigt ihre Sportstätten |
| **Übersicht** | Zahl der Sportstätten und Anlagen, Befüllung der Felder, Kategorien, Befüllung je Kreis |
| **Vorschlag** | Formular: neue Sportstätte eintragen oder eine bestehende ändern, mit Prüfung auf Doppelungen; „Weiter zu LimeSurvey“ übergibt die Werte an die Umfrage |
| **Analysen** | Ergebnisse der Analysen, derzeit der **ALKIS-Abgleich**; lädt erst beim Öffnen (für RLP rund 27 MB) |

In allen Reitern lässt sich oben ein **Gebiet** wählen: Landkreis bzw. kreisfreie Stadt,
darunter Verbandsgemeinde oder Gemeinde. Die Grenzen (VG250 des BKG, Stand 01.01.,
dl-de/by-2-0) lädt `seite` beim ersten Lauf über den WFS des BKG und legt sie unter
`data/cache/gebiete_rp.json` ab; jede Sportstätte bekommt den Regionalschlüssel ihrer
Gemeinde. Ohne Netz: `--gebiete pfad/zu/vg250.gpkg` (heruntergeladenes GeoPackage) oder
`--gebiete aus`. Die Grenzen sind auf 1:250 000 generalisiert; Sportstätten direkt an einer
Gemeindegrenze können der Nachbargemeinde zugeordnet sein.

**Suche:** Das Suchfeld oben links durchsucht beim Tippen die Daten des aktuellen Reiters
(Name, Adresse, Betreiber, ID) und die Gebiete. Mit Enter oder „Suchen“ werden zusätzlich
Orte und Adressen über Nominatim (OpenStreetMap) gesucht, bei Ausfall über Photon.
Angefragt wird nur auf Enter, nicht bei jedem Tastendruck. Escape leert die Suche.

**Koordinaten:** Jedes Popup zeigt „Koordinaten“ (Breite, Länge) mit Link zu Google Maps.
Ein Rechtsklick auf die Karte kopiert die Koordinaten der Stelle in die Zwischenablage und
bietet „Hier eine Sportstätte vorschlagen“ an.

**Vorschläge:** Das Formular im Reiter „Vorschlag“ erreicht man auch über „Sportstätte
vorschlagen“ oben, über „Ändern oder Fehler melden“ im Fenster einer Sportstätte, über „Als
neue Sportstätte vorschlagen“ bei ALKIS-Objekten im ALKIS-Abgleich und per Rechtsklick in
die Karte. Eigentümer und Betreiber lassen sich aus den bisherigen Namen und allen Kommunen
(aus den Verwaltungsgebieten) wählen. Doppelungen meldet das Formular, wenn eine vorhandene
Sportstätte höchstens 60 m entfernt liegt, dieselbe Kategorie in 250 m Umkreis hat, einen
sehr ähnlichen Namen trägt oder dieselbe Adresse hat; dann muss man bestätigen, dass es eine
andere ist. „Weiter zu LimeSurvey“ öffnet `vorschlag_url` aus `konfig.js` mit den Werten als
URL-Parametern (`?newtest=Y&<Fragecode>=…`). Welches Feld in welche Frage geht, steht in
`konfig.js` unter `vorschlag_felder` (Feld: "Fragecode"); nur diese Felder werden übertragen.
Ist `vorschlag_felder` leer, gehen alle Felder mit ihrem Namen als Code. Solange
`vorschlag_url` leer ist, zeigt der Knopf nur an, was übertragen würde.

**Bug melden:** Ist in `konfig.js` `fehler_url` eingetragen, steht oben der Link „Bug
melden“. Er öffnet auf GitHub ein neues Ticket mit der Vorlage
`.github/ISSUE_TEMPLATE/fehler.yml` und trägt die Adresse der Seite (mit Reiter und Gebiet)
und den Browser schon ein. Zum Melden braucht man ein GitHub-Konto; die Tickets sind
öffentlich. Falsche oder fehlende Sportstätten gehören in den Reiter „Vorschlag“.

**Verein oder Kommune** wird aus dem Namen des Betreibers bzw. Eigentümers geschätzt
(„e.V.“, „TuS“, „SV“, „Verein“ → Verein; „Ortsgemeinde“, „Stadt“, „Kreisverwaltung“ →
Kommune; sonst „sonstige“). Die Regeln stehen in `bestand.py` (`betreiber_art`).

Inhalt von `docs/`:

| Datei | Zweck |
|---|---|
| `index.html` | die Seite; lädt die Daten nach und zeigt solange einen Ladehinweis |
| `app/` | Stil und Skripte, Kopie von `src/sportstaettenatlas/web/` – bei jedem Lauf neu |
| `konfig.js` | Titel, Links zur Umfrage und zu „Bug melden“, Impressum, Datenschutz, Lizenz – **wird nur beim ersten Mal angelegt** und danach nie überschrieben |
| `impressum.html`, `datenschutz.html` | Entwürfe der Rechtstexte – ebenfalls nur einmal angelegt |
| `daten/bestand.geojson` | der Datenbestand (Karte, Liste, Übersicht, Vorschlag) |
| `daten/gebiete.json`, `gebiete_*.geojson` | Gebietsauswahl und Umrisse (werden erst bei Bedarf geladen) |
| `daten/analysen/index.json` | welche Analysen der Reiter „Analysen“ zeigt |
| `daten/analysen/alkis/` | Dateien des ALKIS-Abgleichs (siehe unten) |
| `daten/index.html` | Download-Seite mit Quellenvermerk |
| `vendor/leaflet/` | Kartenbibliothek, lokal abgelegt (keine Anfragen an fremde Server) |

Fehlt ein Analyse-Ergebnis (z. B. `data/out/sportstaetten.gpkg` auf einem anderen Rechner),
erneuert `seite` nur den Bestand; die Dateien der Analyse in `docs/` bleiben, wie sie sind.
Frühere Fassungen legten die ALKIS-Dateien direkt in `docs/daten/` ab; `seite` verschiebt sie
beim nächsten Lauf nach `docs/daten/analysen/alkis/`.

**Einmalig auf GitHub einrichten:** Repository → *Settings* → *Pages* → *Build and
deployment*: Source „Deploy from a branch“, Branch `main`, Ordner `/docs`. Nach ein bis
zwei Minuten ist die Seite unter `https://<benutzer>.github.io/<repository>/` erreichbar.
Mit einem kostenlosen GitHub-Konto geht das nur für öffentliche Repositorys.

**`konfig.js` bearbeiten:** am einfachsten direkt auf GitHub (Datei öffnen → Stift-Symbol →
*Commit changes*). Die Seite ist danach nach ein bis zwei Minuten aktualisiert, ohne dass
`seite` neu laufen muss; die Seite lädt `konfig.js` immer frisch.

- `vorschlag_url`, `vorschlag_felder`: Umfrage für Vorschläge (siehe oben).
- `fehler_url`: Link für „Bug melden“, z. B.
  `https://github.com/<benutzer>/<repository>/issues/new?template=fehler.yml`. Leer = kein Link.
- `impressum_url`, `datenschutz_url`: für eine öffentliche Seite Pflicht. `seite` legt
  einmalig Entwürfe an (`impressum.html`, `datenschutz.html`, Platzhalter gelb markiert):
  ergänzen, von der Hochschule prüfen lassen und den gelben Entwurfshinweis oben löschen.
  Die Datenschutzerklärung deckt GitHub Pages, die Hintergrundkarte (basemap.de, BKG), die
  Ortssuche über OpenStreetMap, die Umfrage (LimeSurvey) und „Bug melden“ (GitHub) ab.
  Statt der Entwürfe kann man auch auf die Seiten der Hochschule verlinken.
- `lizenz`, `lizenz_url`, `namensnennung`: Vorschlag ist die Datenlizenz Deutschland –
  Namensnennung 2.0, wie bei den ALKIS-Daten. Vorher klären, ob die Rechte am bisherigen
  Atlas-Bestand das zulassen.
- `ortssuche`: `false` schaltet die Suche über OpenStreetMap ab.

**Was nicht veröffentlicht wird:** E-Mail-Adressen und Telefonnummern (auch aus dem Atlas)
sowie jeder Wert, der eine E-Mail-Adresse enthält – im Bestand wie in den Analysen. Die
Rohspalten des Atlas (`alt_*`) erscheinen nur, soweit die Karte sie braucht. Umrisse werden
auf etwa 1 m geglättet.

**Größe:** Für ganz RLP sind die Daten zusammen rund 30–35 MB. Beim Öffnen lädt die Seite
nur den Bestand (rund 4 MB, komprimiert unter 1 MB); die ALKIS-Daten erst im Reiter
„Analysen“. Im Git kostet die erste Fassung rund 3–4 MB, jede weitere Veröffentlichung nur
die Unterschiede: gemessen 2 kB für 30 geänderte Sportstätten, 140 kB, wenn sich alle
laufenden Nummern verschieben. Häufiges Veröffentlichen ist also unproblematisch. Teuer wird
nur, wenn sich das Format aller Objekte ändert (z. B. eine andere Rundung der Koordinaten).

**An der Seite arbeiten:** HTML, Stil und Skripte liegen in `src/sportstaettenatlas/web/`
(Übersicht im Kopf von `web/__init__.py`). Es sind normale Browser-Skripte ohne
Build-Schritt; nach einer Änderung `seite --vorschau` ausführen.

## Analysen

Eine Analyse ist ein Ordner unter `src/sportstaettenatlas/analysen/` mit eigenen Befehlen
(`sportstaettenatlas <name> …`). Sie rechnet auf dem eigenen Rechner, schreibt ihr
Ergebnis nach `data/out/` und liefert `seite` die Dateien für die Webseite. Diese landen in
`docs/daten/analysen/<name>/`; der Reiter „Analysen“ zeigt dann einen Knopf je Analyse.

Eine neue Analyse braucht:
1. einen Ordner `analysen/<name>/` mit `cli.py` (Funktion `befehle(sub)` für die
   Befehlsgruppe und eine Funktion, die `(Titel, {Datei: Inhalt}, {Datei: Beschreibung})`
   für die Webseite liefert) und den Aufruf in `cli.py` (`befehle` und `cmd_seite`),
2. in `web/analysen.js` einen Eintrag in `ANALYSEN` mit Titel und einer Funktion, die die
   Darstellung auf der Karte baut (siehe `analyseAlkis`).

## Analyse: ALKIS-Abgleich (`sportstaettenatlas alkis …`)

Leitet aus offenen ALKIS-Daten (Liegenschaftskataster) zwei Tabellen ab, **Sportstätten**
und **Sportanlagen**, und gleicht sie mit dem Atlas ab. So zeigt sich, was der Atlas kennt,
was nur das Kataster kennt (Kandidaten für Vorschläge) und welche Atlas-Einträge im Kataster
fehlen oder daneben liegen.

| ALKIS | Verwendung |
|---|---|
| `Nutzung` mit Nutzungsart „Sport-, Freizeit- und Erholungsfläche“ | Fläche einer **Sportstätte** |
| `GebaeudeBauwerk` mit Funktion Sporthalle, Hallenbad, Spielfeld … | **Sportanlage** (Tribüne, Vereinsheim = `zubehoer`) |

- Jede Sportanlage gehört zu der Sportstätten-Fläche, mit der sie sich am stärksten
  überlappt.
- Freistehende Anlagen ohne Sportfläche, etwa eine Schulturnhalle auf dem Schulgelände,
  bilden eine eigene Sportstätte. Liegen mehrere näher als 20 m beieinander, werden sie zu
  einer Sportstätte zusammengefasst.
- Sportstätten-Flächen ohne erkanntes Gebäude werden selbst zur Sportanlage, mit
  `pruefen = true`. Das betrifft typischerweise Sportplätze.

Datenquelle ist zunächst Rheinland-Pfalz: *WFS RP ALKIS Vereinfacht* des LVermGeo,
lizenziert unter Datenlizenz Deutschland – Namensnennung 2.0. Weitere Länder werden in
`src/sportstaettenatlas/analysen/alkis/quellen.py` ergänzt.

```bash
# Ausschnitt Koblenz-Innenstadt laden und Tabellen bauen
uv run sportstaettenatlas -v alkis lauf

# ganzes Stadtgebiet Koblenz (grob) bzw. ganz Rheinland-Pfalz (kachelweise, fortsetzbar)
uv run sportstaettenatlas -v alkis lauf --gebiet koblenz
uv run sportstaettenatlas -v alkis lauf --gebiet rlp

# eigener Ausschnitt in EPSG:25832 (xmin,ymin,xmax,ymax)
uv run sportstaettenatlas alkis lauf --bbox 397500,5576500,401500,5580500

# mit dem Atlas abgleichen
uv run sportstaettenatlas -v alkis abgleich --atlas pfad/zum/atlas-export.csv

# Karte (data/out/karte.html) aus dem vorhandenen Ergebnis erzeugen und öffnen
uv run sportstaettenatlas alkis karte --oeffnen

# welche ALKIS-Werte kommen vor und wie werden sie zugeordnet?
uv run sportstaettenatlas alkis werte --gebiet koblenz --alle

# Ergebnis auf die Webseite bringen
uv run sportstaettenatlas seite
```

`lauf` besteht aus `laden` (lädt die Daten in den Cache unter `data/raw/`) und `bauen`
(erzeugt daraus die Tabellen); beide lassen sich auch einzeln ausführen.

### Ganz Rheinland-Pfalz

`--gebiet rlp` umfasst das ganze Land, ca. 185 × 230 km in 437 Kacheln zu je 10 km.
Damit das machbar bleibt, gilt Folgendes:

- **Serverseitiger Vorfilter:** Bei der Nutzung werden nur Sport-, Freizeit- und
  Erholungsflächen geladen. Bei Gebäuden und Bauwerken werden nur Objekte geladen, deren
  `funktion` eines der Stichwörter aus `regeln.toml` enthält. Ohne Filter wären es landesweit
  über 3 Mio. Gebäude. Lehnt der Server den Filter ab, wird die betroffene Kachel
  automatisch ungefiltert geladen; das dauert dann deutlich länger.
- **Fortsetzbar:** Jede Kachel landet in `data/raw/<land>_<gebiet>_<typ>_kacheln/`. Nach
  einem Abbruch (Netz, Strg+C) setzt derselbe Befehl bei der nächsten fehlenden Kachel fort.
  `--neu` lädt alles neu.
- **Dubletten:** Objekte, die über eine Kachelgrenze reichen, kommen mehrfach vor und werden
  über `oid` entfernt.
- `--kachel-km 5` verkleinert die Kacheln, falls der Server bei großen Antworten abbricht.

Hinweis: Der Vorfilter berücksichtigt nur das Feld `funktion`. Gebäude, die nur über ihren
Namen als Sportstätte erkennbar wären, fehlen dadurch landesweit. Wenn man die Regeln
ändert, muss man mit `--neu` neu laden, weil der Vorfilter aus den Regeln erzeugt wird.

### Ergebnis (`data/out/`)

- `sportstaetten.csv` und `sportanlagen.csv`: die beiden Tabellen; nach `abgleich`
  zusätzlich `*_angereichert.csv`
- `sportstaetten.gpkg`: dieselben Tabellen mit Geometrie (Layer `sportstaetten` und
  `sportanlagen`, nach `abgleich` zusätzlich `*_angereichert`) sowie der Layer `metadaten`.
  Öffnen z. B. in QGIS.
- `abgleich_altbestand.csv`: der Abgleich aus Sicht des Atlas (siehe unten)
- `karte.html`: dieselbe Darstellung wie im Reiter „Analysen“, als eine Datei mit allen Daten
  darin – per Doppelklick im Browser zu öffnen (Leaflet und Kartenkacheln kommen aus dem
  Internet)
- `QUELLENVERMERK.txt`: der Quellenvermerk, den die Lizenz verlangt

Wichtige Spalten:

| Spalte | Bedeutung |
|---|---|
| `sportstaette_id`, `anlage_id` | laufende IDs dieses Laufs (nicht dauerhaft) |
| `quelle` | `alkis_nutzung`, `alkis_gebaeude_bauwerk` oder `alkis_gebaeude` (Gruppe freistehender Anlagen) |
| `alkis_oid` | ALKIS-Objektidentifikator, dauerhafter Bezug zum Kataster |
| `alkis_text` | ALKIS-Funktion bzw. -Bezeichnung im Original |
| `typgruppe`, `typ` | Zuordnung nach `regeln.toml` (halle, spielfeld, becken, …) |
| `rolle` | `sportanlage`, `gesamtanlage` (z. B. Stadionbauwerk) oder `zubehoer` |
| `pruefen` | unsichere Zuordnung, manuell kontrollieren |
| `anzahl_anlagen`, `anlagentypen` | nur Sportstätten: Anzahl und Typen ihrer Anlagen |
| `gemeindeschluessel` | AGS (8-stellig) |
| `flaeche_m2`, `lon`, `lat` | Fläche, Lagepunkt (WGS84) |

### Abgleich mit dem Atlas (`alkis abgleich`)

Der Befehl liest `data/out/sportstaetten.gpkg`, gleicht die Sportstätten mit dem Export
des bisherigen Sportstättenatlas RLP ab (CSV, eine Zeile je Sportstätte, Spalten
`ID, Name, …, Sportanlagen, Latitude, Longitude`) und übernimmt dessen Angaben mit Herkunft.
Statt einer Datei kann auch ein Ordner mit CSV-Dateien im Import-Format des Altsystems
übergeben werden. Der Export gehört nicht ins Repository; `data/` ist deshalb in
`.gitignore` ausgeschlossen.

- **Zuordnung:** Jeder Atlas-Eintrag (Punkt) wird der ALKIS-Sportstätte zugeordnet,
  in der er liegt oder die ihm am nächsten ist (max. 100 m).
- **Nachbarflächen:** ALKIS zerlegt einen Standort oft in mehrere Flächen (z. B. Tennishalle
  und, durch einen Weg getrennt, die Plätze). Der Atlas-Punkt bestätigt deshalb auch
  Flächen, die an seine Fläche grenzen (Lücke bis 20 m, auch in Ketten, höchstens 250 m
  vom Punkt) und selbst keinen Atlas-Treffer haben. Sie tragen `alt_bezug` =
  „Nachbarfläche von ST…“.
- **Zusammengeführte Felder:** Name (Komplex- bzw. Stättenname), Adresse, Betreiber,
  Eigentümer, Website, Sportarten, Betriebsstatus und `anlagen_laut_altbestand`, z. B.
  „2× Großspielfeld; Weit- und Dreisprunganlage“; die Atlas-`ID` steht in `alt_atlas_id`.
- **`abgleich_altbestand.csv`** ist die Sicht des Atlas, eine Zeile je Atlas-Eintrag:
  - `status` = `zugeordnet` (bis 100 m), `nah` (100–200 m, Koordinate prüfen) oder
    `nicht in ALKIS`
  - `typ_passt`: Passt der Atlas-Typ zu den Anlagen, die ALKIS dort kennt?
  - ALKIS-Sportstätten ohne Gegenstück im Atlas findet man in
    `sportstaetten_angereichert.csv` an `verifikation` ohne „Sportstättenatlas RLP“.
- **ALKIS vor Ort:** Bei „nicht in ALKIS“ fragt `abgleich` den Katasterdienst an genau
  dieser Stelle ohne Vorfilter ab. Das Ergebnis landet in `alkis_nutzung_vor_ort` (z. B.
  „Landwirtschaft (Grünland)“) und `alkis_gebaeude_vor_ort` (Gebäude im Umkreis von 25 m
  mit Funktion und Abstand). Ein zweiter Lauf fragt bekannte Orte nicht mehr an; der
  Fortschrittsbalken zeigt `gespeichert`/`neu`/`fehler`. Fehlgeschlagene Orte werden beim
  nächsten Lauf wiederholt. Mit `--ohne-alkis-vor-ort` lässt sich der Schritt abschalten.

### Darstellung (Reiter „Analysen“ → „ALKIS-Abgleich“ und `karte.html`)

- Die Farben zeigen die Typgruppe; die Legende blendet Gruppen und Verifikationsstufen ein
  und aus. Gestrichelte Objekte sind zu prüfen.
- Weit herausgezoomt sieht man Punkte, ab Zoom 15 Umrisse und Sportstätten-Flächen.
- Beim Darüberfahren steht die Verifikation ganz oben, jeder Wert zeigt seine Quelle in
  Klammern. Bei einer Sportanlage folgt der Abschnitt „Sportstätte – gilt für alle ihre
  Anlagen“. Ein Klick lässt die Angaben als Popup stehen.
- Was nur im Atlas steht, erscheint als eigene Punkte: rot „nicht in ALKIS“, orange
  gestrichelt „in der Nähe“ (100–200 m). Bei „in der Nähe“ zeigt ein Pfeil zur nächsten
  ALKIS-Sportstätte, deren Umriss hervorgehoben wird.
- Die Legende fasst zusammen, wie viele Atlas-Einträge im gewählten Gebiet in ALKIS stehen,
  in der Nähe liegen oder fehlen (`zusammenfassung.json`).
- Bei ALKIS-Sportstätten ohne Atlas-Eintrag führt „Als neue Sportstätte vorschlagen“ ins
  Formular, bei Atlas-Punkten „Eintrag ändern“.

Dateien auf der Webseite (`docs/daten/analysen/alkis/`): `sportstaetten.geojson`,
`sportanlagen.geojson`, `atlas_abgleich.geojson` (Atlas-Einträge ohne passende ALKIS-Fläche)
und `zusammenfassung.json` (Zahlen je Gemeinde). Code: `analysen/alkis/karte.py` (Dateien) und
`web/analysen.js` (Darstellung).

### Typen aus ALKIS: was „Sportanlage“ bedeutet

- **„Sportanlage“** ist in ALKIS ein Sammelbegriff für das ganze Gelände, oft mit
  Nebenflächen wie Parkplätzen. Solche Flächen bekommen die eigene Gruppe `unbestimmt`
  (grau) und werden zur Prüfung markiert. Ebenso „Gebäude- und Freifläche Sport“.
- **„Sportplatz“** ist ein eigener Typ (`sportplatz`, Gruppe `spielfeld`).
- **Neu erfasst:** Rennbahn (z. B. Nürburgring), Modellfluggelände, Eis-/Rollschuhbahn.
- **Bewusst nicht erfasst:** Parken, Campingplatz, Verkehrsübungsplatz, Grünanlage, Garten.
- **Verifikation „nur ALKIS – unbestimmt“:** Sportstätten, die keine andere Quelle kennt
  und in denen ALKIS nur „Sportanlage“ führt (Nebengebäude zählen nicht). Sie sind
  waagerecht schraffiert und lassen sich in der Legende getrennt ein- und ausblenden.
- Beim Typvergleich mit dem Atlas zählt `unbestimmt` nicht (`typ_passt` bleibt leer).
- **„Hallenbad“:** ALKIS führt jeden Gebäudeteil eines Bades als eigenes Bauwerk; ein Bad
  erscheint deshalb oft als mehrere Anlagen. Auch private Becken (Hotels, Kliniken) heißen in
  ALKIS „Hallenbad“.

### Herkunft und Verifikation

- **Herkunft:** Die Rohwerte des Atlas stehen mit Präfix `alt_*`. Daraus entstehen
  zusammengeführte Felder wie `name`, `betreiber`, `eigentuemer`, `adresse`, `website`,
  `sportarten`, `betriebsstatus`. Neben jedem Feld steht in `<feld>_quelle`, woher
  der Wert kommt (`ALKIS` oder `Sportstättenatlas RLP`); der ALKIS-Name hat Vorrang.
- **Verifikation:** Eine ALKIS-Sportstätte gilt als bestätigt, wenn der Atlas sie führt –
  direkt oder als angrenzende Fläche einer zugeordneten Stätte.
  - `verifikation`: `ALKIS` oder `ALKIS, Sportstättenatlas RLP`; `verifikation_anzahl` 1 oder 2.
  - `verifikation_stufe`: `nur ALKIS`, `nur ALKIS – unbestimmt` (ALKIS nennt nur den
    Sammelbegriff „Sportanlage“) oder `bestätigt`.
  - Sportanlagen übernehmen die Verifikation ihrer Sportstätte, weil der Atlas Punkte je
    Sportstätte führt (`verifikation_sportstaette`).

### Zwischenspeicher

Alles liegt unter `data/cache/`; ein zweiter Lauf ist dadurch schnell:

- `http/`: jede Antwort des ALKIS-WFS (30 Tage)
- `alkis_vor_ort.json`: Nutzung und Gebäude je Atlas-Ort
- `gebiete_rp.json`: Verwaltungsgebiete für die Webseite

Zum Neuladen einfach die jeweilige Datei bzw. den Ordner löschen.

### Regeln anpassen

Die Zuordnung steht in `src/sportstaettenatlas/analysen/alkis/regeln.toml`. Die Regeln
vergleichen Stichwörter ohne Groß-/Kleinschreibung; die erste passende Regel gewinnt. Am
einfachsten geht man so vor: `alkis werte --alle` zeigt alle tatsächlich vorkommenden
ALKIS-Texte, danach ergänzt man Regeln in einer eigenen Kopie und übergibt sie mit
`--regeln meine_regeln.toml`.

### Grenzen

ALKIS liefert Lage, Umriss und einen groben Typ. Betreiber, Belag, Maße nach DIN,
Sportarten und Zustand stehen nicht darin; sie kommen derzeit nur aus dem Atlas. Ob ein
Spielfeld als eigenes Bauwerk erfasst ist, unterscheidet sich zwischen Katasterämtern.
Viele Sportplätze sind nur als Nutzungsfläche geführt.

## Tests

```bash
uv run pytest
```

Die Tests nutzen nur ausgedachte Daten. Die Prüfung der Skripte der Webseite
(`node --check`) läuft, wenn Node.js installiert ist.
