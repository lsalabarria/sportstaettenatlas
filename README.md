# Sportstättenatlas – ALKIS-Prototyp

Leitet aus offenen ALKIS-Daten (Liegenschaftskataster) zwei lokale Tabellen ab:
**Sportstätten** und **Sportanlagen**. Danach werden sie mit dem bisherigen
Sportstättenatlas RLP abgeglichen; dessen Angaben werden mit Herkunft übernommen.

**Begriffe**
- Eine **Sportstätte** ist der Standort, z. B. ein Sportpark, ein Schulsportzentrum oder ein
  Freibad. Name, Betreiber, Adresse, Website und Öffnungszeiten gehören zur Sportstätte und
  gelten für alle ihre Anlagen.
- Eine **Sportanlage** ist eine einzelne Einheit einer Sportstätte, z. B. eine Halle, ein
  Spielfeld oder ein Becken. Typ, Belag, Sportart und Fläche gehören zur Anlage. Jede
  Anlage gehört über `sportstaette_id` zu genau einer Sportstätte.

**Wie das Programm sie aus ALKIS ableitet**

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
`src/sportstaettenatlas/quellen.py` ergänzt.

## Installation

```bash
uv sync
```

## Nutzung

```bash
# Ausschnitt Koblenz-Innenstadt laden und Tabelle bauen
uv run sportstaettenatlas -v lauf

# ganzes Stadtgebiet Koblenz (grob)
uv run sportstaettenatlas -v lauf --gebiet koblenz

# ganz Rheinland-Pfalz (kachelweise, fortsetzbar – siehe unten)
uv run sportstaettenatlas -v lauf --gebiet rlp

# eigener Ausschnitt in EPSG:25832 (xmin,ymin,xmax,ymax)
uv run sportstaettenatlas lauf --bbox 397500,5576500,401500,5580500

# Karte aus dem vorhandenen Ergebnis erzeugen und im Browser öffnen
uv run sportstaettenatlas karte --oeffnen

# welche ALKIS-Werte kommen vor und wie werden sie zugeordnet?
uv run sportstaettenatlas werte --gebiet koblenz --alle
```

Die Schritte lassen sich auch einzeln ausführen: `laden` lädt die Daten und legt sie im
Cache unter `data/raw/` ab, `bauen` erzeugt daraus die Ergebnisse.

## Ganz Rheinland-Pfalz

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

## Ergebnis (`data/out/`)

- `sportstaetten.csv` und `sportanlagen.csv`: die beiden Tabellen; nach `anreichern`
  zusätzlich `*_angereichert.csv`
- `sportstaetten.gpkg`: dieselben Tabellen mit Geometrie (Layer `sportstaetten` und
  `sportanlagen`, nach `anreichern` zusätzlich `*_angereichert`) sowie der Layer `metadaten`.
  Öffnen z. B. in QGIS.
- `karte.html`: interaktive Karte, die man direkt im Browser öffnet (Leaflet, Hintergrund basemap.de des BKG, umschaltbar zwischen Grau und Farbe).
  - Beim Darüberfahren erscheinen die Metadaten der Sportanlage und ihrer Sportstätte.
  - Die Farben zeigen die Typgruppe; die Legende blendet Gruppen ein und aus.
  - Gestrichelte Objekte sind zu prüfen.
  - Weit herausgezoomt sieht man Punkte, ab Zoom 15 Umrisse und Sportstätten-Flächen.
  - Leaflet und Kartenkacheln kommen aus dem Internet, die Daten stecken in der Datei selbst.
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

## Abgleich mit dem Atlas (`anreichern`)

Der Befehl liest `data/out/sportstaetten.gpkg`, gleicht die Sportstätten mit dem
bisherigen Sportstättenatlas RLP ab und übernimmt dessen Angaben. Ergebnis sind
`sportstaetten_angereichert.csv`, der Layer `sportstaetten_angereichert` im GeoPackage,
`abgleich_altbestand.csv` und eine neue `karte.html`. Weitere Quellen (OSM, Wikidata,
Websites, Verbandsdaten) werden derzeit bewusst nicht genutzt.

### Abgleich mit dem bisherigen Sportstättenatlas RLP (`--altbestand`)

Gelesen wird der **Export aus dem laufenden Atlas** (CSV, eine Zeile je Sportstätte, Spalten
`ID, Name, …, Sportanlagen, Latitude, Longitude`):

```bash
uv run sportstaettenatlas -v anreichern --altbestand pfad/zum/atlas-export.csv
```

Der Export gehört nicht ins Repository (er enthält Kontaktdaten); `data/` ist deshalb in
`.gitignore` ausgeschlossen. Statt einer Datei kann auch ein Ordner mit CSV-Dateien im
Import-Format des Altsystems übergeben werden.

- **Zuordnung:** Jede Altsystem-Sportstätte (Punkt) wird der ALKIS-Sportstätte zugeordnet,
  in der sie liegt oder die ihr am nächsten ist (max. 100 m).
- **Verifikation:** Sie erscheint als Quelle `Sportstättenatlas RLP`.
- **Nachbarflächen:** ALKIS zerlegt einen Standort oft in mehrere Flächen (z. B. Tennishalle
  und, durch einen Weg getrennt, die Plätze). Der Atlas-Punkt bestätigt deshalb auch
  Flächen, die an seine Fläche grenzen (Lücke bis 20 m, auch in Ketten, höchstens 250 m
  vom Punkt) und selbst keinen Atlas-Treffer haben. Sie tragen `alt_bezug` =
  „Nachbarfläche von ST…“; die Karte zeigt das bei der Verifikation an.
- **Zusammengeführte Felder:**
  - Name (Komplex- bzw. Stättenname) und Adresse
  - `anlagen_laut_altbestand`, z. B. „2× Großspielfeld; Weit- und Dreisprunganlage“
- **`abgleich_altbestand.csv`** ist die Sicht des Altbestands, eine Zeile je
  Altsystem-Sportstätte:
  - `status` = `zugeordnet` (bis 100 m), `nah` (100–200 m, Koordinate prüfen) oder
    `nicht in ALKIS`
  - `typ_passt`: Passt der Altsystem-Typ zu den Anlagen, die ALKIS dort kennt?
  - ALKIS-Sportstätten ohne Gegenstück im Altbestand findet man in
    `sportstaetten_angereichert.csv` an `verifikation` ohne „Sportstättenatlas RLP“.
- **Karte:** Was nur im Altbestand steht, erscheint als eigene Punkte. Rot heißt
  „nicht in ALKIS“, orange gestrichelt heißt „nah an ALKIS“ (100–200 m). Beim
  Darüberfahren sieht man Name, Typ, Anlagen, Adresse, die nächste ALKIS-Sportstätte und
  den Abstand. In der Legende lassen sich beide Gruppen ein- und ausblenden.
  `sportstaettenatlas karte` liest dafür `abgleich_altbestand.csv` mit ein.
- **ALKIS vor Ort:** Bei „nicht in ALKIS“ fragt `anreichern` den Katasterdienst an genau
  dieser Stelle ohne Vorfilter ab. Das Ergebnis landet in `alkis_nutzung_vor_ort` (z. B.
  „Landwirtschaft (Grünland)“) und `alkis_gebaeude_vor_ort` (Gebäude im Umkreis von 25 m
  mit Funktion und Abstand). Gespeichert werden die WFS-Antworten (`data/cache/http`) und das fertige Ergebnis je Ort
  (`data/cache/alkis_vor_ort.json`). Ein zweiter Lauf fragt bekannte Orte nicht mehr an;
  der Fortschrittsbalken zeigt `gespeichert`/`neu`/`fehler`. Fehlgeschlagene Orte werden
  beim nächsten Lauf wiederholt.
  Mit `--ohne-alkis-vor-ort` lässt sich der Schritt abschalten.
- **Klick auf ein Objekt:** Die Informationen bleiben als Popup stehen und lassen sich
  markieren und kopieren. Bei „nah an ALKIS“ zeigt ein Pfeil zur nächsten
  ALKIS-Sportstätte, deren Umriss hervorgehoben wird.

- Im Export stehen unter `Latitude`/`Longitude` UTM-Werte (Hochwert/Rechtswert); das wird
  erkannt und korrigiert.
- Zusätzlich übernommen (mit Quelle `Sportstättenatlas RLP`): Betreiber, Eigentümer,
  Website, E-Mail, Sportarten, Betriebsstatus; die Atlas-`ID` steht in
  `alt_atlas_id`.

### Suche auf der Karte

Oben links gibt es ein Suchfeld. Beim Tippen durchsucht es die eigenen Daten (Name,
Adresse, Typ, ID von Sportstätten und Atlas-Einträgen). Mit Enter oder „Suchen" werden
zusätzlich Orte und Adressen über Nominatim (OpenStreetMap) gesucht, bei Ausfall über
Photon. Angefragt wird nur auf Enter, nicht bei jedem Tastendruck. Escape leert die Suche.

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

### Koordinaten auf der Karte

Jedes Popup zeigt „Koordinaten“ (Breite, Länge) mit Link zu Google Maps. Ein Rechtsklick
auf die Karte kopiert die Koordinaten der Stelle in die Zwischenablage, im Format, das
Google Maps im Suchfeld versteht.

### Zwischenspeicher

Alles liegt unter `data/cache/`; ein zweiter Lauf ist dadurch schnell:

- `http/`: jede Antwort des ALKIS-WFS (30 Tage)
- `alkis_vor_ort.json`: Nutzung und Gebäude je Atlas-Ort

Zum Neuladen einfach die jeweilige Datei bzw. den Ordner löschen.

### Herkunft und Verifikation

- **Herkunft:** Die Rohwerte des Atlas stehen mit Präfix `alt_*`. Daraus entstehen
  zusammengeführte Felder wie `name`, `betreiber`, `eigentuemer`, `adresse`, `website`,
  `email`, `sportarten`, `betriebsstatus`. Neben jedem Feld steht in `<feld>_quelle`, woher
  der Wert kommt (`ALKIS` oder `Sportstättenatlas RLP`); der ALKIS-Name hat Vorrang.
- **Verifikation:** Eine ALKIS-Sportstätte gilt als bestätigt, wenn der Atlas sie führt –
  direkt oder als angrenzende Fläche einer zugeordneten Stätte.
  - `verifikation`: `ALKIS` oder `ALKIS, Sportstättenatlas RLP`; `verifikation_anzahl` 1 oder 2.
  - `verifikation_stufe`: `nur ALKIS`, `nur ALKIS – unbestimmt` (ALKIS nennt nur den
    Sammelbegriff „Sportanlage“) oder `bestätigt`.
  - Sportanlagen übernehmen die Verifikation ihrer Sportstätte, weil der Atlas Punkte je
    Sportstätte führt (`verifikation_sportstaette`).
  - Was nur im Atlas steht, zeigt `abgleich_altbestand.csv` (`nicht in ALKIS`, `nah`).
- **Karte:** Beim Darüberfahren steht die Verifikation ganz oben, jeder Wert zeigt seine
  Quelle in Klammern. Bei einer Sportanlage folgt der Abschnitt „Sportstätte – gilt für alle
  ihre Anlagen“. In der Legende lässt sich nach Verifikationsstufe filtern.

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
- Weitere Quellformate: in `src/sportstaettenatlas/bestand.py` eine Lesefunktion
  ergänzen und in `LESER` eintragen (`--format`).

## Webseite veröffentlichen (GitHub Pages)

`seite` erzeugt aus dem Datenbestand (`daten/`) und dem ALKIS-Ergebnis (`data/out/`) eine
statische Webseite im Ordner `docs/`. GitHub Pages liefert diesen Ordner direkt aus – ohne
Server und Datenbank.

```bash
uv run sportstaettenatlas seite              # docs/ erzeugen bzw. aktualisieren
uv run sportstaettenatlas seite --vorschau   # danach lokal ansehen (http://localhost:8000)
git add docs && git commit -m "Daten aktualisiert" && git push
```

Die Seite hat vier Ansichten (oben umschaltbar, die gewählte Ansicht und das Gebiet stehen
in der Adresse, z. B. `…/#ansicht=uebersicht&gebiet=07137`, und lassen sich so verlinken):

| Ansicht | Inhalt |
|---|---|
| **Karte** (Start) | der Datenbestand aus `daten/`; Filter nach Kategorie, Betreiber-Art und Sportarten |
| **Liste** | Vereine und Kommunen als Betreiber bzw. Eigentümer, sortier- und filterbar; ein Klick zeigt ihre Sportstätten |
| **Übersicht** | Zahl der Sportstätten und Anlagen, Befüllung der Felder, Kategorien, Abgleich mit ALKIS, Befüllung je Kreis |
| **Vorschlag** | Formular: neue Sportstätte eintragen oder eine bestehende ändern, mit Prüfung auf Doppelungen; „Weiter zu LimeSurvey“ übergibt die Werte an die Umfrage |
| **Verifikation (ALKIS)** | ALKIS-Sportstätten und -Anlagen und der Abgleich mit dem Atlas; lädt erst beim Öffnen (rund 27 MB) |

In allen Ansichten lässt sich oben ein **Gebiet** wählen: Landkreis bzw. kreisfreie Stadt,
darunter Verbandsgemeinde oder Gemeinde. Die Grenzen (VG250 des BKG, Stand 01.01.,
dl-de/by-2-0) lädt `seite` beim ersten Lauf über den WFS des BKG und legt sie unter
`data/cache/gebiete_rp.json` ab; jede Sportstätte bekommt den Regionalschlüssel ihrer
Gemeinde. Ohne Netz: `--gebiete pfad/zu/vg250.gpkg` (heruntergeladenes GeoPackage) oder
`--gebiete aus`. Die Grenzen sind auf 1:250 000 generalisiert; Sportstätten direkt an einer
Gemeindegrenze können der Nachbargemeinde zugeordnet sein.

**Vorschläge:** Das Formular im Reiter „Vorschlag“ erreicht man auch über „Sportstätte
vorschlagen“ oben, über „Ändern oder Fehler melden“ im Fenster einer Sportstätte, über „Als
neue Sportstätte vorschlagen“ bei ALKIS-Objekten in der Verifikation und per Rechtsklick in
die Karte. Eigentümer und Betreiber lassen sich aus den bisherigen Namen und allen Kommunen
(aus den Verwaltungsgebieten) wählen. Doppelungen meldet das Formular, wenn eine vorhandene
Sportstätte höchstens 60 m entfernt liegt, dieselbe Kategorie in 250 m Umkreis hat, einen
sehr ähnlichen Namen trägt oder dieselbe Adresse hat; dann muss man bestätigen, dass es eine
andere ist. „Weiter zu LimeSurvey“ öffnet `vorschlag_url` aus `konfig.js` mit den Werten als
URL-Parametern (`?newtest=Y&Q00=…&G01Q02=…`). Welches Feld in welche Frage geht, steht in
`konfig.js` unter `vorschlag_felder` (Feld: "Fragecode"); nur diese Felder werden übertragen.
Ist `vorschlag_felder` leer, gehen alle Felder mit ihrem Namen als Code. Solange `vorschlag_url` leer ist, zeigt der Knopf nur an,
was übertragen würde.

**Verein oder Kommune** wird aus dem Namen des Betreibers bzw. Eigentümers geschätzt
(„e.V.“, „TuS“, „SV“, „Verein“ → Verein; „Ortsgemeinde“, „Stadt“, „Kreisverwaltung“ →
Kommune; sonst „sonstige“). Die Regeln stehen in `bestand.py` (`betreiber_art`).

Ohne ALKIS-Ergebnis (`data/out/sportstaetten.gpkg` fehlt) erneuert `seite` nur Karte,
Liste und Übersicht; die Dateien der Verifikation bleiben, wie sie sind.

Inhalt von `docs/`:

| Datei | Zweck |
|---|---|
| `index.html` | die Karte; lädt die Daten nach und zeigt solange einen Ladehinweis |
| `konfig.js` | Titel, Link zum Meldeformular, Impressum, Datenschutz, Lizenz – **wird nur beim ersten Mal angelegt** und danach nie überschrieben |
| `impressum.html`, `datenschutz.html` | Entwürfe der Rechtstexte – ebenfalls nur einmal angelegt |
| `daten/bestand.geojson` | der Datenbestand (Karte, Liste, Übersicht) |
| `daten/sportstaetten.geojson`, `sportanlagen.geojson`, `atlas_abgleich.geojson` | ALKIS und Abgleich (Verifikation) |
| `daten/gebiete.json`, `gebiete_*.geojson` | Gebietsauswahl und Umrisse (werden erst bei Bedarf geladen) |
| `daten/index.html` | Download-Seite mit Quellenvermerk |
| `vendor/leaflet/` | Kartenbibliothek, lokal abgelegt (keine Anfragen an fremde Server) |

**Einmalig auf GitHub einrichten:** Repository → *Settings* → *Pages* → *Build and
deployment*: Source „Deploy from a branch“, Branch `main`, Ordner `/docs`. Nach ein bis
zwei Minuten ist die Seite unter `https://<benutzer>.github.io/<repository>/` erreichbar.
Mit einem kostenlosen GitHub-Konto geht das nur für öffentliche Repositorys.

**`konfig.js` bearbeiten:** am einfachsten direkt auf GitHub (Datei öffnen → Stift-Symbol →
*Commit changes*). Die Seite ist danach nach ein bis zwei Minuten aktualisiert, ohne dass
`seite` neu laufen muss.

- `vorschlag_url`: Link zur LimeSurvey-Umfrage. Ist er gesetzt, erscheint oben der Knopf
  „Sportstätte vorschlagen“.
- `vorschlag_parameter`: optional; dann bekommt jede Sportstätte einen Link „Änderung oder
  Fehler melden“, der die ALKIS-Objektkennung an die Umfrage übergibt (z. B. `nr`).
- `impressum_url`, `datenschutz_url`: für eine öffentliche Seite Pflicht. `seite` legt
  einmalig Entwürfe an (`impressum.html`, `datenschutz.html`, Platzhalter gelb markiert):
  ergänzen, von der Hochschule prüfen lassen und den gelben Entwurfshinweis oben löschen.
  Die Datenschutzerklärung deckt GitHub Pages, die Hintergrundkarte (basemap.de, BKG) und
  die Ortssuche über OpenStreetMap ab. Statt der Entwürfe kann man auch auf die Seiten der
  Hochschule verlinken.
- `lizenz`, `lizenz_url`, `namensnennung`: Vorschlag ist die Datenlizenz Deutschland –
  Namensnennung 2.0, wie bei den ALKIS-Daten. Vorher klären, ob die Rechte am bisherigen
  Atlas-Bestand das zulassen.

**Was nicht veröffentlicht wird:** E-Mail-Adressen und Telefonnummern (auch aus dem Atlas)
sowie jeder Wert, der eine E-Mail-Adresse enthält. Die Rohspalten des Atlas (`alt_*`)
erscheinen nur, soweit die Karte sie braucht. Umrisse werden auf etwa 1 m geglättet.

**Größe:** Für ganz RLP sind die Daten zusammen rund 30–35 MB. Beim Öffnen lädt die Seite
nur den Bestand (rund 4 MB, komprimiert unter 1 MB); die ALKIS-Daten erst in der
Verifikation. Im Git kostet die erste Fassung rund 3–4 MB, jede weitere Veröffentlichung nur
die Unterschiede: gemessen 2 kB für 30 geänderte Sportstätten, 140 kB, wenn sich alle
laufenden Nummern verschieben. Häufiges Veröffentlichen ist also unproblematisch. Teuer wird
nur, wenn sich das Format aller Objekte ändert (z. B. eine andere Rundung der Koordinaten).

## Regeln anpassen

Die Zuordnung steht in `src/sportstaettenatlas/regeln.toml`. Die Regeln vergleichen
Stichwörter ohne Groß-/Kleinschreibung; die erste passende Regel gewinnt. Am einfachsten
geht man so vor: `werte --alle` zeigt alle tatsächlich vorkommenden ALKIS-Texte, danach
ergänzt man Regeln in einer eigenen Kopie und übergibt sie mit `--regeln meine_regeln.toml`.

## Grenzen

ALKIS liefert Lage, Umriss und einen groben Typ. Betreiber, Belag, Maße nach DIN,
Sportarten und Zustand stehen nicht darin; sie kommen derzeit nur aus dem Atlas. Ob ein Spielfeld als eigenes Bauwerk erfasst ist,
unterscheidet sich zwischen Katasterämtern. Viele Sportplätze sind nur als Nutzungsfläche
geführt.

## Tests

```bash
uv run pytest
```
