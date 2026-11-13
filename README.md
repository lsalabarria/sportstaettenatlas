# Sportstättenatlas Rheinland-Pfalz

Ein offener Sportstättenatlas. Der **Datenbestand** liegt im Git: nach Kreisen geordnet, ein
Ordner je Sportstätte mit einer Datei je Sportanlage. Eine **statische Webseite** auf GitHub
Pages zeigt ihn als Karte, Liste und Übersicht und nimmt Vorschläge über LimeSurvey entgegen.
Der **ALKIS-Abgleich** prüft den Bestand gegen das Liegenschaftskataster.

## Inhalt

- [Aufbau](#aufbau)
- [Installation](#installation)
- [Datenmodell](#datenmodell)
- [Datenbestand pflegen](#datenbestand-pflegen)
- [Webseite](#webseite)
  - [Reiter](#reiter)
  - [Vorschläge](#vorschläge)
  - [Einstellungen (konfig.js)](#einstellungen-konfigjs)
  - [Auf GitHub einrichten](#auf-github-einrichten)
  - [Was nicht veröffentlicht wird](#was-nicht-veröffentlicht-wird)
- [ALKIS-Abgleich](#alkis-abgleich)
- [Code](#code)
- [Tests](#tests)

## Aufbau

```
daten/      Datenbestand: Kreis / Sportstätte / Sportanlagen (im Git, von Hand gepflegt)
docs/       Webseite für GitHub Pages (von `seite` erzeugt, im Git)
results/    Arbeitsordner: Downloads, Zwischenspeicher, Ergebnis des ALKIS-Abgleichs (nicht im Git)
src/        Code (siehe Abschnitt „Code“)
```

```
Atlas-Export ──bestand──▶ daten/ ──────────────────────────────┐
                            │                                   ├──seite──▶ docs/ ──▶ GitHub Pages
ALKIS (WFS) ──alkis──▶ results/out/ (Abgleich mit daten/) ──────┘
```

## Installation

```bash
uv sync
```

## Datenmodell

Der Atlas kennt zwei Arten von Objekten: **Sportstätten** und ihre **Sportanlagen**.

```
daten/RP/07111-koblenz/          Kreis – nur Ordnung im Git, ergibt sich aus der Lage
  <id>/<id>_meta.json            Sportstätte: der Standort, ein Punkt auf der Karte
  <id>/<anlage-id>.json          Sportanlage (0 … n): eine Einheit darin, z. B. ein Spielfeld
```

- Eine **Sportstätte** ist der Standort (Sportpark, Schulsportzentrum, Freibad …) mit Name,
  Kategorie, Adresse, Lage, Betreiber und Eigentümer.
- Eine **Sportanlage** ist eine Einheit darin (Großspielfeld, Rundlaufbahn, Halle, Becken …)
  mit Typ, Sportarten, Baujahr, Baukosten und Ausstattung.
- Jede Sportanlage gehört zu genau einer Sportstätte.

Felder, Beispiele, Typen der Anlagen und Regeln zum Ändern: **[daten/README.md](daten/README.md)**.

## Datenbestand pflegen

Die Dateien in `daten/` sind die Quelle. Änderungen werden dort gemacht – direkt auf GitHub
oder per Pull Request – und erscheinen beim nächsten `seite` auf der Karte.

```bash
uv run sportstaettenatlas bestand pfad/zum/atlas-export.csv   # Atlas-Export übernehmen
uv run sportstaettenatlas einordnen                           # Sportstätten in ihren Kreis verschieben
```

- `bestand` legt nur fehlende Sportstätten an; vorhandene bleiben unverändert, weil sie
  inzwischen gepflegt sein können. `--modus aktualisieren` überschreibt sie mit dem Export.
- Die E-Mail-Spalte des Exports wird nie gelesen, und jeder Wert mit einer E-Mail-Adresse
  entfällt. Der Export selbst gehört nicht ins Repository.
- Der Kreis-Ordner ergibt sich aus der Lage (Verwaltungsgebiete VG250 des BKG, beim ersten
  Lauf geladen und unter `results/cache/` abgelegt). Liegt eine Sportstätte nach einer
  Änderung ihrer Lage in einem anderen Kreis, weist `seite` darauf hin; `einordnen`
  verschiebt sie.

## Webseite

```bash
uv run sportstaettenatlas seite --vorschau   # docs/ erzeugen und lokal ansehen
git add -A daten docs && git commit -m "Daten aktualisiert" && git push
```

`seite` liest `daten/` und das Ergebnis des ALKIS-Abgleichs und schreibt die Webseite nach
`docs/`. GitHub Pages liefert den Ordner aus, ohne Server und Datenbank.

### Reiter

| Reiter | Inhalt |
|---|---|
| **Karte** | ein Punkt je Sportstätte; Filter nach den Sportanlagen darin (nach Gruppen), Kategorie, Betreiber-Art und Sportarten; das Fenster einer Sportstätte listet ihre Anlagen |
| **Liste** | Vereine und Kommunen als Betreiber bzw. Eigentümer; ein Klick zeigt ihre Sportstätten |
| **Übersicht** | Sportstätten und Sportanlagen: Zahlen, Befüllung der Angaben, Kategorien, Typen, je Kreis |
| **Vorschlag** | Formular für neue Sportstätten und Änderungen, weiter zu LimeSurvey |
| **Analysen** | der ALKIS-Abgleich; lädt erst beim Öffnen |

In allen Reitern lässt sich oben ein Kreis, eine Verbandsgemeinde oder Gemeinde wählen.
Reiter und Gebiet stehen in der Adresse (`…/#ansicht=uebersicht&gebiet=07137`). Die Suche
oben links findet Sportstätten, Anlagentypen und Gebiete; mit Enter auch Orte über
OpenStreetMap. Verein oder Kommune wird aus dem Namen des Betreibers geschätzt
(`betreiber_art` in `seite.py`).

### Vorschläge

Das Formular kennt drei Arten: eine **neue Sportstätte** mit ihren Sportanlagen, die
**Angaben einer Sportstätte ändern** oder ihre **Sportanlagen ändern** (hinzufügen, ändern,
entfernen). Es meldet mögliche Doppelungen (höchstens 60 m entfernt, gleiche Kategorie in
250 m, sehr ähnlicher Name oder gleiche Adresse). „Weiter zu LimeSurvey“ öffnet die Umfrage
aus `konfig.js` und überträgt die Werte als URL-Parameter; welches Feld in welche Frage geht,
steht in `vorschlag_felder`. Die Sportanlagen gehen mit einer Zeile je Anlage: `anlagen` ist
der Stand nach dem Vorschlag, `anlagen_aenderung` beschreibt die Änderung. Die Kennung in
eckigen Klammern (`[17abb3c4]`) ist der Anfang des Dateinamens der Anlage.

„Bug melden“ oben öffnet ein Ticket auf GitHub (Vorlage `.github/ISSUE_TEMPLATE/fehler.yml`).
Tickets sind öffentlich.

### Einstellungen (konfig.js)

`docs/konfig.js` wird beim ersten `seite` angelegt und danach nie überschrieben; am
einfachsten auf GitHub bearbeiten. Die Seite lädt sie immer frisch.

- `vorschlag_url`, `vorschlag_felder`: Umfrage für Vorschläge
- `fehler_url`: Link für „Bug melden“; leer = kein Link
- `impressum_url`, `datenschutz_url`: Pflicht für eine öffentliche Seite. `seite` legt einmalig
  Entwürfe an (`impressum.html`, `datenschutz.html`, Platzhalter gelb markiert).
- `lizenz`, `lizenz_url`, `namensnennung`: Lizenz der Daten
- `ortssuche`: `false` schaltet die Suche über OpenStreetMap ab

### Auf GitHub einrichten

Repository → *Settings* → *Pages*: Source „Deploy from a branch“, Branch `main`, Ordner
`/docs`. Nach ein bis zwei Minuten ist die Seite unter
`https://<benutzer>.github.io/<repository>/` erreichbar.

### Was nicht veröffentlicht wird

E-Mail-Adressen und Telefonnummern sowie jeder Wert, der eine E-Mail-Adresse enthält – im
Bestand wie im ALKIS-Abgleich.

## ALKIS-Abgleich

```bash
uv run sportstaettenatlas -v alkis   # ALKIS laden, Sportstätten bauen, mit daten/ abgleichen
uv run sportstaettenatlas seite      # Ergebnis auf die Webseite bringen
```

Der Abgleich leitet aus dem Liegenschaftskataster (ALKIS, WFS des LVermGeo RLP,
dl-de/by-2-0) eigene Sportstätten und Sportanlagen ab und vergleicht sie mit `daten/`:

1. **Laden:** Sport-, Freizeit- und Erholungsflächen sowie Gebäude und Bauwerke mit
   Sportfunktion, kachelweise für ganz Rheinland-Pfalz. Der erste Lauf dauert lange; danach
   kommen die Daten aus `results/raw/` (`--neu` lädt neu). Zum Ausprobieren:
   `--gebiet koblenz-innenstadt`.
2. **Bauen:** Eine Sportfläche wird zur Sportstätte, die Gebäude und Plätze darauf zu ihren
   Sportanlagen. Welche ALKIS-Werte als was gelten, steht in
   `src/sportstaettenatlas/analysen/alkis/regeln.toml`.
3. **Abgleichen:** Jede Sportstätte aus `daten/` wird der ALKIS-Fläche zugeordnet, in der sie
   liegt oder die ihr am nächsten ist (bis 100 m). Ergebnis je Sportstätte: „in ALKIS“, „in
   der Nähe“ (100–200 m, Lage prüfen) oder „nicht in ALKIS“. ALKIS-Flächen ohne Gegenstück
   im Bestand sind Kandidaten für neue Sportstätten.

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
  cli.py          Befehle bestand, einordnen, seite, alkis
  atlas.py        Atlas-Export lesen
  bestand.py      daten/ lesen und schreiben, Kreis-Ordner
  anlagen.py      Typen und Gruppen der Sportanlagen
  gebiete.py      Verwaltungsgebiete (VG250) und Zuordnung zur Gemeinde
  seite.py        Webseite nach docs/ schreiben
  hilfen.py       Arbeitsordner, User-Agent
  web/            die Webseite: index.html, stil.css, Skripte, Vorlagen (konfig.js …)
  analysen/alkis/ ALKIS-Abgleich (Aufbau im Kopf von __init__.py)
```

Die Skripte der Webseite sind normale Browser-Skripte ohne Build-Schritt (Übersicht im Kopf
von `web/__init__.py`).

## Tests

```bash
uv run pytest
```

Die Tests nutzen nur ausgedachte Daten. Die Skripte der Webseite werden mit `node --check`
geprüft, wenn Node.js installiert ist.
