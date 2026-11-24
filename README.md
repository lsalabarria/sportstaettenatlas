# Sportstättenatlas Rheinland-Pfalz

Ein offener Sportstättenatlas. Der **Datenbestand** liegt im Git: nach Kreisen geordnet, ein
Ordner je Sportstätte mit einer Datei je Sportanlage, dazu ein Verzeichnis der Organisationen.
Eine **statische Webseite** auf GitHub Pages zeigt ihn als Karte, Liste und Übersicht und nimmt
Vorschläge über LimeSurvey entgegen. Der **ALKIS-Abgleich** prüft den Bestand gegen das
Liegenschaftskataster.

Was im Datenbestand steht, alle Felder und wie man Daten ändert oder einliest:
**[daten/README.md](daten/README.md)**.

## Inhalt

- [Aufbau](#aufbau)
- [Installation](#installation)
- [Befehle](#befehle)
- [Datenmodell im Code](#datenmodell-im-code)
- [Prüfungen](#prüfungen)
- [Webseite](#webseite)
- [Kontaktdaten](#kontaktdaten)
- [ALKIS-Abgleich](#alkis-abgleich)
- [Code](#code)
- [Tests](#tests)

## Aufbau

```
daten/      Datenbestand (im Git, von Hand gepflegt): Sportstätten, Sportkomplexe, Stützpunkte,
            Organisationen – siehe daten/README.md
webseite/   für die Webseite, was sich nicht aus daten/ erzeugen lässt (im Git): konfig.js,
            Impressum, Datenschutz und unter analysen/ das Ergebnis des ALKIS-Abgleichs
docs/       Webseite (von `seite` erzeugt, nicht im Git; auf GitHub baut sie die Action)
results/    Arbeitsordner: Downloads, Zwischenspeicher, Ergebnis des ALKIS-Abgleichs (nicht im Git)
src/        Code (siehe „Code“)
```

```
CSV-Dateien ──bestand──▶ daten/ ────────────────────────────────────────────┐
                            │                                                ├──seite──▶ docs/ ──▶ GitHub Pages
ALKIS (WFS) ──alkis──▶ results/out/ ──seite──▶ webseite/analysen/ ───────────┘
```

## Installation

Nötig sind:

- **Git**, um das Repository zu klonen
- **[uv](https://docs.astral.sh/uv/)**, verwaltet Python und alle Pakete:
  `curl -LsSf https://astral.sh/uv/install.sh | sh` (Windows: siehe Link)
- **Python 3.12 oder neuer**: Fehlt es, lädt `uv sync` es selbst herunter.

```bash
git clone https://github.com/lsalabarria/sportstaettenatlas.git
cd sportstaettenatlas
uv sync                                   # legt .venv an, mit allen Paketen und dev-Werkzeugen
uv run sportstaettenatlas --help
```

Optional:

- **Node.js**: Die Tests prüfen damit die Skripte der Webseite.
- **Chromium für Playwright**: Damit laufen die Browser-Tests (siehe [Tests](#tests)).
- **Graphviz**: Damit wird das Diagramm des Datenmodells gezeichnet (siehe unten).

Für das Diagramm des Datenmodells (`daten/erzeugt/datenmodell.svg`) zusätzlich Graphviz und erdantic:

```bash
sudo apt install graphviz graphviz-dev
uv sync --extra doku
```

## Befehle

Alle mit `uv run sportstaettenatlas …`; `--help` zeigt die Optionen.

| Befehl | macht |
|---|---|
| `bestand DATEI.csv …` | CSV-Dateien in `daten/` übernehmen, auch Einträge entfernen (`--probe`, `--modus`; Regeln: [CSV einlesen](daten/README.md#csv-einlesen)) |
| `vorschlaege EXPORT.csv` | Vorschläge aus einem LimeSurvey-Export in `daten/` übernehmen (`--probe`, `--alle`; siehe [Vorschläge](#vorschläge)) |
| `vorlage` | Vorlagen für eigene CSV-Dateien nach `results/vorlagen/` |
| `organisationen` | Stand des Verzeichnisses; `--gebiete` legt alle Landkreise, Städte, Verbands- und Ortsgemeinden an, `--aus-bestand` fehlende Eigentümer, Betreiber und Nutzer |
| `einordnen` | Sportstätten und Sportkomplexe in den Ordner ihres Kreises, Organisationen in den ihrer Art verschieben |
| `sportkomplex ID ID …` | Sportkomplex anlegen (`--name`) oder ergänzen (`--zu KOMPLEX`) und die Sportstätten zuordnen; `--entfernen` nimmt sie heraus (siehe [Sportkomplexe](daten/README.md#sportkomplexe)) |
| `modell` | Feldtabellen (`daten/erzeugt/datenmodell.md`) und Diagramm schreiben |
| `migrieren` | Felder in allen Dateien von `daten/` umbenennen oder entfernen (`--umbenennen ALT=NEU`, `--entfernen FELD`, `--probe`); `--bereinigen` behebt Formfehler (Hausnummer `6.0` oder als Datum wie `Aug 14` → `8-14`, PLZ ohne führende Null, Ort als Dict-Text, Webseite ohne `https://`, Fläche einer Halle, die nur Länge × Breite ist) |
| `pruefen` | Bestand prüfen, ohne die Webseite zu bauen (Liste in `daten/erzeugt/regelverstoesse.csv`) |
| `seite` | Webseite nach `docs/` (`--vorschau`: lokal ansehen); prüft dabei mit |
| `-v alkis` | ALKIS-Abgleich (siehe unten) |
| `crawler` | Webseiten für Vereine ohne Webseite suchen (siehe unten) |

Danach: `git add -A daten webseite && git commit -m "…" && git push` – die Webseite baut
die GitHub Action (siehe „Auf GitHub einrichten“).

**Webseiten für Vereine suchen:** `uv run sportstaettenatlas crawler` sucht für
Vereine ohne Webseite in OpenStreetMap und Wikidata und rät Domains (`tus-berg.de` …). Jede
Webseite wird am Impressum geprüft (Name, Ort, Vereinsregister → Punkte); gespeichert wird
davon nichts. Ergebnis: `results/vereinswebseiten.csv` zum Prüfen; passende Zeilen behalten,
dann `bestand --modus ergaenzen`. Probelauf: `--max 20` (zufällige, wiederholbare Stichprobe). Beachtet robots.txt,
fragt je Webseite höchstens einmal pro Sekunde, fragt Verzeichnisse wie fussball.de nicht ab
und lädt keine Seiten sozialer Netzwerke. Kontakt im User-Agent: `SPORTSTAETTENATLAS_KONTAKT`.

## Datenmodell im Code

Das Modell steht an **einer** Stelle: `src/sportstaettenatlas/modell/` (Pydantic) – Felder,
Auswahllisten, Regeln, die Felder je Anlagentyp (`MERKMALE`) und die Zuordnungen ohne eigenes
Feld (Organisationstypen, Muster für Kontaktdaten). Daraus folgt:

- `bestand`, `seite` und `alkis` prüfen `daten/` beim Lesen. Ein Fehler im Aufbau bricht ab,
  ein Wert gegen die Regeln nicht; er steht in `daten/erzeugt/regelverstoesse.csv`.
- `seite` schreibt `docs/daten/schema.json`. Formular, Popup, Liste und Übersicht der Webseite
  nehmen Felder, Beschriftungen, Regeln und Zuordnungen von dort.
- `modell` erzeugt `daten/erzeugt/datenmodell.md` (alle Felder, Felder je Anlagentyp,
  Auswahllisten) und das Diagramm daneben; ein Test meldet, wenn die Datei nicht mehr passt. Die Tabellen hängen von der Pydantic-Version ab – also mit der aus `uv.lock`
  erzeugen.

Ein neues Feld ist eine Zeile in `modell/klassen.py`, danach `modell` und `seite`. Wird ein Feld
umbenannt oder gestrichen, passt `migrieren` die Dateien an, z. B.
`migrieren --umbenennen baukosten_eur=baukosten` oder `migrieren --entfernen quellen`.

## Prüfungen

`seite` und `pruefen` schreiben alle Auffälligkeiten nach `daten/erzeugt/regelverstoesse.csv` (Datei,
Name, Prüfung, Meldung, sortiert; Name einer Sportanlage: Typ, Bezeichnung und ihre Sportstätte); sie brechen nicht ab. Die Datei gehört ins Git: Wer nichts
installiert hat, sieht sie auf GitHub als durchsuchbare Tabelle. Nach jedem Batch mit
`pruefen` erneuern und mit committen – der Commit zeigt dann, welche Meldungen weg und welche
neu sind. Die Spalte `pruefung` nennt eine der Prüfungen unten
oder „Datenmodell“. Zu den Regeln des Datenmodells (Pflichtfelder, Formate,
Auswahllisten, mindestens 4 Nachkommastellen bei Koordinaten, `braucht`, `teil_von`) prüft
`src/sportstaettenatlas/bestand/pruefung.py`:

- **Organisation:** Betreiber, Eigentümer und Nutzer stehen im Verzeichnis der Organisationen.
- **Art der Organisation:** `betreiber_typ`/`eigentuemer_typ` widerspricht nicht der Art im Verzeichnis.
- **Eigentum der Kommune:** Eine Kommune als Eigentümer – die Sportstätte liegt in ihrem Gebiet (höchstens 250 m davor).
- **Ort:** Die Koordinate liegt in der Gemeinde aus `adresse.ort` oder höchstens 250 m davor (VG250 ist vereinfacht).
- **Rheinland-Pfalz:** Die Koordinate liegt in einer Gemeinde des Landes.
- **Kreis-Ordner:** Sportstätte und Sportkomplex liegen im Ordner ihres Kreises (`einordnen` verschiebt).
- **Gleiche Koordinate:** Höchstens zwei Sportstätten auf genau derselben Koordinate (sonst wohl ein Ersatzwert; im selben Sportkomplex wohl dessen Lage).
- **Doppelung:** Keine zwei Sportstätten mit ähnlichem Namen näher als 60 m (Regel wie im Formular); im selben Sportkomplex nur bei gleichem Namen.
- **PLZ:** Die Postleitzahl beginnt wie eine in Rheinland-Pfalz.
- **Straße und Hausnummer:** Keine Hausnummer in der Straße, keine Hausnummer ohne Straße.
- **Sanierung:** Die letzte Sanierung liegt nicht vor dem Baujahr.
- **Baujahr:** Keine Sportanlage ist älter als ihre Sportstätte (gleiches Jahr ist in Ordnung, fehlende Jahre zählen nicht).
- **Anlagentyp:** Kein Feld ist befüllt, das nicht zum Typ der Sportanlage passt (`MERKMALE`).
- **Sportarten:** Die Sportarten einer Anlage stehen auch bei ihrer Sportstätte.
- **Schreibweise der Sportarten:** Keine Varianten wie „Fussball“ neben „Fußball“.
- **Licht:** Kein Lux-Wert oder Leuchtmittel, wenn Flutlicht „nein“ ist.
- **Fläche:** Weicht höchstens 25 % von Länge × Breite ab.
- **Betriebsstatus:** Keine Öffnungsstunden, wenn die Anlage stillgelegt ist.
- **Organisation ohne Art:** Jede Organisation im Verzeichnis hat eine Art.
- **Fast gleiche Organisationen:** Keine zwei Einträge mit fast gleichem Namen (ohne Rechtsform wie „e.V.“); zwei Vereine mit LSB-Nummer gelten als verschieden.
- **Sportkomplex:** Der Sportkomplex in `sportkomplex` gibt es.
- **Kleiner Sportkomplex:** Zu jedem Sportkomplex gehören mindestens zwei Sportstätten.
- **Ausdehnung des Sportkomplexes:** Seine Sportstätten liegen höchstens 1 km auseinander.
- **Stützpunkt abgelaufen:** `gueltig_bis` eines Stützpunkts liegt nicht in der Vergangenheit.
- **Stützpunkt-Verweis:** Die Sportstätten und Sportkomplexe eines Stützpunkts gibt es.
- **Stützpunkt doppelt:** Eine Sportstätte steht nicht zusätzlich einzeln drin, wenn ihr Sportkomplex schon dazugehört.
- **Träger des Stützpunkts:** Der Träger steht im Verzeichnis der Organisationen.

Sportstätten und Sportkomplexe unter `daten/outside/<Land>/` liegen außerhalb von
Rheinland-Pfalz. Für sie entfallen Ort, Rheinland-Pfalz, PLZ, Kreis-Ordner und Eigentum der
Kommune; `einordnen` lässt sie liegen, und `seite` zeigt sie nicht an.
Liegt die Lage einer Sportstätte unter `daten/RP/` in keiner Gemeinde des Landes (Ordner
`ohne-kreis`), zeigt `seite` sie ebenfalls nicht an und meldet sie als Regelverstoß: entweder
ist die Koordinate falsch, oder die Sportstätte gehört nach `daten/outside/<Land>/`.

## Webseite

`seite` liest `daten/` und `webseite/` und schreibt die Webseite nach `docs/`. GitHub Pages
liefert den Ordner aus, ohne Server und Datenbank. Lokal ansehen: `seite --vorschau`.

### Reiter

| Reiter | Inhalt |
|---|---|
| **Karte** | ein Punkt je Sportstätte, herausgezoomt zusammengefasst je Kreis (bis Zoomstufe 9) und je Gemeinde (bis 12), mit dem Umriss beim Darüberfahren; außerhalb von Rheinland-Pfalz grau; Filter nach Sportanlagen (nach Gruppen), Kategorie, Art des Betreibers, Sportarten, Sportkomplex und Stützpunkt (je Ebene oder einzeln); das Fenster einer Sportstätte listet ihre Anlagen und Stützpunkte |
| **Liste** | alle Sportstätten, Sportanlagen, Sportkomplexe, Stützpunkte bzw. Organisationen (als Eigentümer, Betreiber oder Nutzer), filterbar nach Sportart, Kategorie, Typ, Sportkomplex, Stützpunkt und Text, sortierbar (auch nach Befüllung); ein Klick zeigt alle Angaben, „Karte“ springt zum Punkt |
| **Übersicht** | Zahlen (auch Olympia-, Bundes- und Landesstützpunkte), filterbar nach Sportart; Befüllung der Angaben nach Abschnitten (Felder nur unter den Anlagen, für die sie gedacht sind), Kategorien und Typen, je Kreis |
| **Vorschlag** | Formular für neue Sportstätten, Änderungen, Organisationen, Sportkomplexe und Stützpunkte, weiter zu LimeSurvey |
| **Analysen** | der ALKIS-Abgleich; lädt erst beim Öffnen |

Oben lässt sich ein Kreis, eine Verbandsgemeinde oder Gemeinde wählen. Reiter, Gebiet und
Auswahl stehen in der Adresse (`…/#ansicht=liste&teil=anlagen&sportart=Fußball&gebiet=07137`).
Die Suche oben links findet Sportstätten, Anlagentypen und Gebiete; mit Enter auch Orte über
OpenStreetMap.

### Vorschläge

Das Formular kennt fünf Arten: **neue Sportstätte** mit ihren Sportanlagen, **Sportstätte
ändern** (Angaben, Sportkomplex und Sportanlagen: hinzufügen, ändern, entfernen),
**Organisation** eintragen, ändern oder löschen, **Sportkomplex** anlegen, ändern (Name,
Adresse, welche Sportstätten dazugehören) oder auflösen und **Stützpunkt** eintragen (Art,
Sportarten, Träger, Gültigkeit, Sportstätten oder Sportkomplexe), ändern oder löschen.

Neues lässt sich im selben Vorschlag mit anlegen:

- **Organisationen:** Steht ein Eigentümer, Betreiber, Nutzer, Träger oder eine übergeordnete
  Organisation noch nicht im Verzeichnis, bietet das Formular an, sie mit Art und Webseite
  einzutragen (`neue_organisationen`).
- **Sportstätten** beim Sportkomplex und beim Stützpunkt: „+ neue Sportstätte“ öffnet das
  Formular der Sportstätte, „Sportstätte übernehmen“ führt zurück (`neue_sportstaetten`).
- **Sportkomplex** bei einer Sportstätte: „+ neuer Sportkomplex …“ mit Name, Adresse und den
  weiteren Sportstätten (`neuer_sportkomplex`).

Das Formular prüft die Regeln des Modells und meldet mögliche Doppelungen (höchstens 60 m
entfernt, gleiche Kategorie in 250 m, sehr ähnlicher Name oder gleiche Adresse; bei
Organisationen: Name schon im Verzeichnis oder sehr ähnlich). Eine mögliche Doppelung muss
man bestätigen, bevor der Vorschlag weitergeht.

„Weiter zu LimeSurvey“ öffnet die Umfrage aus `konfig.js`. Sie hat zwei Fragen: `data`
(versteckt) bekommt den ganzen Vorschlag als JSON nach dem Modell `Vorschlag` (Felder in
[daten/erzeugt/datenmodell.md](daten/erzeugt/datenmodell.md)), `kommentar` die Anmerkung. Ändert sich das
Datenmodell, bleibt die Umfrage, wie sie ist. Die Umfrage zum Importieren:
`sportstaette_vorschlagen.lss` (nicht im Repository, enthält die Adresse der Verwaltung).

**Übernehmen:** In LimeSurvey die Antworten als CSV exportieren, dann
`uv run sportstaettenatlas vorschlaege EXPORT.csv --probe` (zeigt nur) und ohne `--probe`
(schreibt). Eine Änderung überschreibt den Wert in `daten/`. Setzen zwei Vorschläge dasselbe
Feld verschieden, steht dort „a|b“ mit einer Warnung – von Hand auflösen; `seite` meldet solche
Werte als Regelverstoß, bis sie aufgelöst sind. Übernommene Antwort-IDs stehen in
`daten/vorschlaege_uebernommen.txt` und werden beim nächsten Export übersprungen. Kommentare
zeigt der Befehl nur an, gespeichert werden sie nicht. Liegt eine geänderte Lage danach in
einem anderen Kreis, verschiebt `einordnen` die Sportstätte. Ein vorgeschlagener Sportkomplex
wird angelegt und bei seinen Sportstätten eingetragen; Sportstätten, die ein Vorschlag aus
einem Komplex nimmt, verlieren ihn, ein aufgelöster Komplex verschwindet ganz. Ein Stützpunkt
wird angelegt, geändert (die geänderten Felder) oder gelöscht. Was ein Vorschlag mit anlegt,
kommt zuerst: neue Organisationen (steht der Name schon im Verzeichnis, nur eine Warnung) und
neue Sportstätten (die Listen des Sportkomplexes bzw. Stützpunkts bekommen ihre IDs).

„Bug melden“ oben öffnet ein öffentliches Ticket auf GitHub (Vorlage
`.github/ISSUE_TEMPLATE/fehler.yml`).

### Einstellungen (konfig.js)

`webseite/konfig.js` wird beim ersten `seite` angelegt und danach nie überschrieben; am
einfachsten auf GitHub bearbeiten. `seite` kopiert sie nach `docs/`, die Seite lädt sie
immer frisch.

- `vorschlag_url`: Umfrage für Vorschläge; `vorschlag_felder` nur, wenn die Fragen dort nicht
  `data` und `kommentar` heißen
- `fehler_url`: Link für „Bug melden“; leer = kein Link
- `impressum_url`, `datenschutz_url`: Pflicht für eine öffentliche Seite, hier die Seiten der
  Hochschule Koblenz. Verweisen sie auf `impressum.html` bzw. `datenschutz.html`, legt `seite`
  einmalig Entwürfe in `webseite/` an (Platzhalter gelb markiert) und veröffentlicht sie.
- `lizenz`, `lizenz_url`, `namensnennung`: Lizenz der Daten
- `ortssuche`: `false` schaltet die Suche über OpenStreetMap ab

### Auf GitHub einrichten

Repository → *Settings* → *Pages*: Source „GitHub Actions“. Die Action
`.github/workflows/seite.yml` läuft bei jedem Push und Pull Request:

1. **Tests**: `pytest` mit den Browser-Tests
2. **Webseite**: `seite` baut `docs/` aus `daten/` und `webseite/`; die dabei neu erzeugte
   `regelverstoesse.csv` liegt zusätzlich unter *Actions* → Lauf → *Artifacts*
3. **Veröffentlichen**: nur für `main`, wenn 1. und 2. durchlaufen

Einige Minuten nach dem Push ist die Seite unter
`https://<benutzer>.github.io/<repository>/` aktuell. Schlägt ein Schritt fehl, bleibt die
alte Seite stehen. Von Hand starten: *Actions* → *Tests und Webseite* → *Run workflow*.

## Kontaktdaten

E-Mail-Adressen und Telefonnummern werden weder gespeichert noch veröffentlicht – im Bestand,
im Verzeichnis der Organisationen, in Vorschlägen und im ALKIS-Abgleich. Felder und Spalten,
die so heißen, werden nie gelesen, und jeder Wert mit einer E-Mail-Adresse entfällt (Muster
`EMAIL_MUSTER` und `KONTAKT_NAME` in `modell/klassen.py`). Exporte und andere CSV-Dateien mit solchen
Angaben gehören nicht ins Repository.

## ALKIS-Abgleich

```bash
uv run sportstaettenatlas -v alkis   # ALKIS laden, Sportstätten bauen, mit daten/ abgleichen
uv run sportstaettenatlas seite      # Ergebnis auf die Webseite bringen
```

Der Abgleich leitet aus dem Liegenschaftskataster (ALKIS, WFS des LVermGeo RLP,
dl-de/by-2-0) eigene Sportstätten und Sportanlagen ab und vergleicht sie mit `daten/`. Er
schreibt nur nach `results/`, nie nach `daten/`; was er findet, kommt über einen Vorschlag
in den Bestand.

1. **Laden:** Sport-, Freizeit- und Erholungsflächen sowie Gebäude und Bauwerke mit
   Sportfunktion, kachelweise für ganz Rheinland-Pfalz. Der erste Lauf dauert lange; danach
   kommen die Daten aus `results/raw/` (`--neu` lädt neu). Zum Ausprobieren:
   `--gebiet koblenz-innenstadt`.
2. **Bauen:** Eine Sportfläche wird zur Sportstätte, die Gebäude und Plätze darauf zu ihren
   Sportanlagen. Welche ALKIS-Werte als was gelten, steht in
   `src/sportstaettenatlas/analysen/alkis/regeln.toml`, welche Typgruppe zu welcher Kategorie
   des Atlas passt in `kategorien.py`.
3. **Abgleichen:** Jede Sportstätte aus `daten/` wird der ALKIS-Fläche zugeordnet, in der sie
   liegt oder die ihr am nächsten ist (bis 100 m); die unter `daten/outside/` nicht, ALKIS
   deckt nur Rheinland-Pfalz ab. Ergebnis je Sportstätte: „in ALKIS“, „in
   der Nähe“ (100–200 m, Lage prüfen) oder „nicht in ALKIS“. ALKIS-Flächen ohne Gegenstück
   im Bestand sind Kandidaten für neue Sportstätten.

Nicht jede Sport-, Freizeit- und Erholungsfläche wird zur Sportstätte: Bezeichnungen ohne
Regel („Grünanlage“, „Campingplatz“ …) bleiben außen vor. Eine „Freizeitanlage“ zählt nur,
wenn eine Sportstätte des Bestands darin liegt (`nur_mit_bestand` in `regeln.toml`).

Für Sportstätten des Bestands ohne ALKIS-Sportstätte fragt der Abgleich ALKIS an genau
dieser Stelle ab: Nutzung der Fläche und Gebäude im Umkreis von 25 m (Spalten
`alkis_nutzung_vor_ort` und `alkis_gebaeude_vor_ort`, auf der Karte „ALKIS-Nutzung hier“
und „ALKIS-Gebäude hier“). Daran sieht man, ob eine Regel fehlt oder die Lage falsch ist.
Die Antworten liegen in `results/cache/alkis_vor_ort.json`; ein neuer Lauf fragt nur neue
Orte ab.

Das Ergebnis steht in `results/out/` (`sportstaetten.gpkg` zum Öffnen in QGIS,
`abgleich_altbestand.csv` mit einer Zeile je Sportstätte des Bestands). `seite` legt die
Dateien für die Webseite daraus in `webseite/analysen/alkis/` ab (ohne Kontaktdaten); erst
mit diesem Ordner im Git zeigt auch die Seite auf GitHub den neuen Stand. Nur nach einem
Lauf für ganz Rheinland-Pfalz einchecken, nicht nach `--gebiet koblenz-innenstadt`. Auf der Webseite
zeigt der Reiter „Analysen“ ALKIS-Flächen und -Anlagen, die Sportstätten des Bestands ohne
passende Fläche und je Gebiet, wie viele im Kataster stehen. Von dort führt „Als neue
Sportstätte vorschlagen“ ins Formular.

ALKIS kennt Lage, Umriss und einen groben Typ, aber keine Betreiber, Beläge oder Sportarten.
Ein Bad besteht dort oft aus mehreren Gebäudeteilen, und auch private Becken heißen
„Hallenbad“.

## Code

Vier Teile, jeder mit klarer Aufgabe. Ein Teil importiert nur aus den Teilen darüber;
`tests/test_aufbau.py` meldet, wenn jemand das verletzt.

```
src/sportstaettenatlas/
  hilfen.py          Ordner, User-Agent – für alle
  modell/            Daten: das Datenmodell (importiert nichts aus den anderen Teilen)
    klassen.py         Modelle, Auswahllisten, Regeln, Grenzwerte der Prüfungen
    anlagen.py         Typen und Gruppen der Sportanlagen
    werte.py           Werte aus Text lesen und bereinigen
    export.py          schema.json für die Webseite
    doku.py            daten/erzeugt/datenmodell.md und Diagramm (Befehl `modell`)
  bestand/           Daten: daten/ lesen, schreiben, prüfen (Befehle `pruefen`, `einordnen`,
                     `sportkomplex`)
    ablage.py          Ordner, Dateien, Organisationen, Sportkomplexe, Stützpunkte
    pruefung.py        Prüfungen über das Modell hinaus → daten/erzeugt/regelverstoesse.csv
    gebiete.py         Verwaltungsgebiete (VG250) und Zuordnung zur Gemeinde
  pflege/            Befüllung und Integration – verändert daten/ (Befehle `bestand`,
                     `organisationen`, `vorschlaege`, `vorlage`, `migrieren`)
    einlesen.py        CSV-Dateien lesen (Spalten über das Modell), Vorlagen
    entfernen.py       Einträge entfernen (Tabelle art, id, begruendung)
    vorschlaege.py     Vorschläge aus dem Formular übernehmen
    kommunen.py        Gebietskörperschaften als Organisationen
    atlas_export.py    Export des bisherigen Atlas lesen
  analysen/          Auswertungen – lesen daten/ nur (Befehle `alkis`, `crawler`)
    alkis/             ALKIS-Abgleich (Aufbau im Kopf von __init__.py)
    crawler.py         Webseiten für Vereine suchen
  webseite/          Darstellung (Befehl `seite`)
    bauen.py           docs/ schreiben, Analysen in webseite/ ablegen
    app/               die Seite: HTML, JavaScript, Stil, Schrift, Vorlagen; das Formular
                       liegt in Teilen in app/vorschlag/ (siehe app/__init__.py)
  cli.py             verteilt auf die Befehle der Teile (jeder Teil hat seine cli.py)
```

Erzeugte Dateien, die ins Git gehören, liegen in `daten/erzeugt/`
(`regelverstoesse.csv`, `datenmodell.md`, `datenmodell.svg`); der Rest von `daten/` ist der
Bestand und von Hand geschriebener Text.

## Tests

```bash
uv run pytest
```

Die Tests nutzen nur ausgedachte Daten. Die Skripte der Webseite werden mit `node --check`
geprüft, wenn Node.js installiert ist.

`tests/test_web.py` öffnet die Webseite in einem unsichtbaren Browser (Playwright): Jede
Ansicht lädt ohne JavaScript-Fehler, jede Art von Vorschlag ergibt JSON, das das Modell
`Vorschlag` annimmt, das Formular lehnt ab, was das Modell ablehnt, dazu Organisationssuche,
Liste und Übersicht. Einmalig den Browser installieren, sonst werden diese Tests übersprungen:

```bash
uv run playwright install chromium        # unter Linux ggf. mit --with-deps
uv run pytest tests/test_web.py           # nur die Browser-Tests (gut 30 Sekunden)
```

Manche Regeln rechnen Python und das Formular je für sich: die Regeln zwischen Feldern
(`braucht`, `nachkommastellen`, `teil_von`) und die Hilfen für Doppelungen (Namen
normalisieren, Ähnlichkeit, Abstand, Name ohne Rechtsform). Grenzwerte und Meldungen stehen
nur in `modell/klassen.py` (`PRUEFUNG`, `MELDUNGEN`) und kommen über `schema.json` ins Formular.
`tests/regeln_faelle.json` enthält Testfälle, die beide Seiten prüfen
(`test_regeln_faelle.py` und `test_web.py`); wer eine dieser Regeln ändert, ergänzt dort
einen Fall.

Leaflet kommt dabei aus `docs/vendor/leaflet` oder wird einmal nach `results/cache/` geladen.
