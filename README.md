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
- [Webseite](#webseite)
- [Kontaktdaten](#kontaktdaten)
- [ALKIS-Abgleich](#alkis-abgleich)
- [Code](#code)
- [Tests](#tests)

## Aufbau

```
daten/      Datenbestand (im Git, von Hand gepflegt) – siehe daten/README.md
docs/       Webseite für GitHub Pages (von `seite` erzeugt, im Git)
results/    Arbeitsordner: Downloads, Zwischenspeicher, Ergebnis des ALKIS-Abgleichs (nicht im Git)
src/        Code (siehe „Code“)
```

```
CSV-Dateien ──bestand──▶ daten/ ───────────────────────────────┐
                            │                                   ├──seite──▶ docs/ ──▶ GitHub Pages
ALKIS (WFS) ──alkis──▶ results/out/ (Abgleich mit daten/) ──────┘
```

## Installation

```bash
uv sync
```

Für das Diagramm des Datenmodells (`daten/datenmodell.svg`) zusätzlich Graphviz und erdantic:

```bash
sudo apt install graphviz graphviz-dev
uv sync --extra doku
```

## Befehle

Alle mit `uv run sportstaettenatlas …`; `--help` zeigt die Optionen.

| Befehl | macht |
|---|---|
| `bestand DATEI.csv …` | CSV-Dateien in `daten/` übernehmen (`--probe`, `--modus`; Regeln: [CSV einlesen](daten/README.md#csv-einlesen)) |
| `vorschlaege EXPORT.csv` | Vorschläge aus einem LimeSurvey-Export in `daten/` übernehmen (`--probe`, `--alle`; siehe [Vorschläge](#vorschläge)) |
| `vorlage` | Vorlagen für eigene CSV-Dateien nach `results/vorlagen/` |
| `organisationen` | Stand des Verzeichnisses; `--gebiete` legt alle Landkreise, Städte, Verbands- und Ortsgemeinden an, `--aus-bestand` fehlende Eigentümer, Betreiber und Nutzer |
| `einordnen` | Sportstätten in den Ordner ihres Kreises, Organisationen in den ihrer Art verschieben |
| `modell` | Feldtabellen in `daten/README.md` und Diagramm schreiben |
| `migrieren` | Felder in allen Dateien von `daten/` umbenennen oder entfernen (`--umbenennen ALT=NEU`, `--entfernen FELD`, `--probe`) |
| `seite` | Webseite nach `docs/` (`--vorschau`: lokal ansehen) |
| `-v alkis` | ALKIS-Abgleich (siehe unten) |

Danach: `git add -A daten docs && git commit -m "…" && git push`.

## Datenmodell im Code

Das Modell steht an **einer** Stelle: `src/sportstaettenatlas/modell.py` (Pydantic) – Felder,
Auswahllisten, Regeln, die Felder je Anlagentyp (`MERKMALE`) und die Zuordnungen ohne eigenes
Feld (Organisationstypen, Muster für Kontaktdaten). Daraus folgt:

- `bestand`, `seite` und `alkis` prüfen `daten/` beim Lesen. Ein Fehler im Aufbau bricht ab,
  ein Wert gegen die Regeln nicht; er steht in `results/regelverstoesse.csv`.
- `seite` schreibt `docs/daten/schema.json`. Formular, Popup, Liste und Übersicht der Webseite
  nehmen Felder, Beschriftungen, Regeln und Zuordnungen von dort.
- `modell` erzeugt den Teil „Datenmodell“ in `daten/README.md`; ein Test meldet, wenn er nicht
  mehr passt. Die Tabellen hängen von der Pydantic-Version ab – also mit der aus `uv.lock`
  erzeugen.

Ein neues Feld ist eine Zeile in `modell.py`, danach `modell` und `seite`. Wird ein Feld
umbenannt oder gestrichen, passt `migrieren` die Dateien an, z. B.
`migrieren --umbenennen baukosten_eur=baukosten` oder `migrieren --entfernen quellen`.

## Webseite

`seite` liest `daten/` und das Ergebnis des ALKIS-Abgleichs und schreibt die Webseite nach
`docs/`. GitHub Pages liefert den Ordner aus, ohne Server und Datenbank.

### Reiter

| Reiter | Inhalt |
|---|---|
| **Karte** | ein Punkt je Sportstätte; Filter nach Sportanlagen (nach Gruppen), Kategorie, Art des Betreibers und Sportarten; das Fenster einer Sportstätte listet ihre Anlagen |
| **Liste** | alle Sportstätten, Sportanlagen bzw. Organisationen (als Eigentümer, Betreiber oder Nutzer), filterbar nach Sportart, Kategorie, Typ und Text, sortierbar (auch nach Befüllung); ein Klick zeigt alle Angaben, „Karte“ springt zum Punkt |
| **Übersicht** | Zahlen, Befüllung der Angaben nach Abschnitten (Felder nur unter den Anlagen, für die sie gedacht sind), Kategorien und Typen, je Kreis |
| **Vorschlag** | Formular für neue Sportstätten, Änderungen und Organisationen, weiter zu LimeSurvey |
| **Analysen** | der ALKIS-Abgleich; lädt erst beim Öffnen |

Oben lässt sich ein Kreis, eine Verbandsgemeinde oder Gemeinde wählen. Reiter, Gebiet und
Auswahl stehen in der Adresse (`…/#ansicht=liste&teil=anlagen&sportart=Fußball&gebiet=07137`).
Die Suche oben links findet Sportstätten, Anlagentypen und Gebiete; mit Enter auch Orte über
OpenStreetMap.

### Vorschläge

Das Formular kennt vier Arten: **neue Sportstätte** mit ihren Sportanlagen, **Angaben einer
Sportstätte ändern**, ihre **Sportanlagen ändern** (hinzufügen, ändern, entfernen) und
**Organisation** eintragen, ändern oder löschen. Es prüft die Regeln des Modells und meldet
mögliche Doppelungen (höchstens 60 m entfernt, gleiche Kategorie in 250 m, sehr ähnlicher
Name oder gleiche Adresse; bei Organisationen: Name schon im Verzeichnis).

„Weiter zu LimeSurvey“ öffnet die Umfrage aus `konfig.js`. Sie hat zwei Fragen: `data`
(versteckt) bekommt den ganzen Vorschlag als JSON nach dem Modell `Vorschlag` (Felder in
[daten/README.md](daten/README.md#datenmodell)), `kommentar` die Anmerkung. Ändert sich das
Datenmodell, bleibt die Umfrage, wie sie ist. Die Umfrage zum Importieren:
`sportstaette_vorschlagen.lss` (nicht im Repository, enthält die Adresse der Verwaltung).

**Übernehmen:** In LimeSurvey die Antworten als CSV exportieren, dann
`uv run sportstaettenatlas vorschlaege EXPORT.csv --probe` (zeigt nur) und ohne `--probe`
(schreibt). Eine Änderung überschreibt den Wert in `daten/`. Setzen zwei Vorschläge dasselbe
Feld verschieden, steht dort „a|b“ mit einer Warnung – von Hand auflösen; `seite` meldet solche
Werte als Regelverstoß, bis sie aufgelöst sind. Übernommene Antwort-IDs stehen in
`daten/vorschlaege_uebernommen.txt` und werden beim nächsten Export übersprungen. Kommentare
zeigt der Befehl nur an, gespeichert werden sie nicht. Liegt eine geänderte Lage danach in
einem anderen Kreis, verschiebt `einordnen` die Sportstätte.

„Bug melden“ oben öffnet ein öffentliches Ticket auf GitHub (Vorlage
`.github/ISSUE_TEMPLATE/fehler.yml`).

### Einstellungen (konfig.js)

`docs/konfig.js` wird beim ersten `seite` angelegt und danach nie überschrieben; am
einfachsten auf GitHub bearbeiten. Die Seite lädt sie immer frisch.

- `vorschlag_url`: Umfrage für Vorschläge; `vorschlag_felder` nur, wenn die Fragen dort nicht
  `data` und `kommentar` heißen
- `fehler_url`: Link für „Bug melden“; leer = kein Link
- `impressum_url`, `datenschutz_url`: Pflicht für eine öffentliche Seite. `seite` legt einmalig
  Entwürfe an (`impressum.html`, `datenschutz.html`, Platzhalter gelb markiert).
- `lizenz`, `lizenz_url`, `namensnennung`: Lizenz der Daten
- `ortssuche`: `false` schaltet die Suche über OpenStreetMap ab

### Auf GitHub einrichten

Repository → *Settings* → *Pages*: Source „Deploy from a branch“, Branch `main`, Ordner
`/docs`. Nach ein bis zwei Minuten ist die Seite unter
`https://<benutzer>.github.io/<repository>/` erreichbar.

## Kontaktdaten

E-Mail-Adressen und Telefonnummern werden weder gespeichert noch veröffentlicht – im Bestand,
im Verzeichnis der Organisationen, in Vorschlägen und im ALKIS-Abgleich. Felder und Spalten,
die so heißen, werden nie gelesen, und jeder Wert mit einer E-Mail-Adresse entfällt (Muster
`EMAIL_MUSTER` und `KONTAKT_NAME` in `modell.py`). Exporte und andere CSV-Dateien mit solchen
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
   liegt oder die ihr am nächsten ist (bis 100 m). Ergebnis je Sportstätte: „in ALKIS“, „in
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
`abgleich_altbestand.csv` mit einer Zeile je Sportstätte des Bestands). Auf der Webseite
zeigt der Reiter „Analysen“ ALKIS-Flächen und -Anlagen, die Sportstätten des Bestands ohne
passende Fläche und je Gebiet, wie viele im Kataster stehen. Von dort führt „Als neue
Sportstätte vorschlagen“ ins Formular.

ALKIS kennt Lage, Umriss und einen groben Typ, aber keine Betreiber, Beläge oder Sportarten.
Ein Bad besteht dort oft aus mehreren Gebäudeteilen, und auch private Becken heißen
„Hallenbad“.

## Code

```
src/sportstaettenatlas/
  modell.py       Datenmodell (Pydantic): Felder, Regeln, Zuordnungen, Schema, Doku
  cli.py          Befehle (siehe „Befehle“)
  bestand.py      daten/ lesen, schreiben und zusammenführen; Kreis-Ordner; Organisationen
  einlesen.py     CSV-Dateien lesen (Spalten über das Modell), Vorlagen
  atlas.py        Export des bisherigen Atlas lesen
  werte.py        Werte aus Text lesen (Zahlen, ja/nein, Listen), CSV-Dateien öffnen
  anlagen.py      Typen und Gruppen der Sportanlagen
  gebiete.py      Verwaltungsgebiete (VG250) und Zuordnung zur Gemeinde
  seite.py        Webseite nach docs/ schreiben
  hilfen.py       Arbeitsordner, User-Agent
  web/            die Webseite (Dateien im Kopf von web/__init__.py)
  analysen/alkis/ ALKIS-Abgleich (Aufbau im Kopf von __init__.py)
```

## Tests

```bash
uv run pytest
```

Die Tests nutzen nur ausgedachte Daten. Die Skripte der Webseite werden mit `node --check`
geprüft, wenn Node.js installiert ist.
