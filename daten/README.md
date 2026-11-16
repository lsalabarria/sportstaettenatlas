# Datenbestand

Die Quelle der Daten des Sportstättenatlas: Änderungen werden hier vorgenommen – direkt auf
GitHub oder per Pull Request – und landen beim nächsten Erzeugen der Webseite
(`uv run sportstaettenatlas seite`) auf der Karte. Wer wann was geändert hat, steht in der
Git-Historie.

```
RP/                                       Land
└─ 07111-koblenz/                         Kreis (aus der Lage bestimmt)
   └─ 9c24bfa6-…/                         Sportstätte
      ├─ 9c24bfa6-…_meta.json             ihre Angaben: Name, Kategorie, Adresse, Lage …
      ├─ 17abb3c4-….json                  eine Sportanlage, z. B. ein Großspielfeld
      └─ 1fb06acd-….json                  eine Sportanlage, z. B. eine Rundlaufbahn
```

- Eine **Sportstätte** ist der Standort, z. B. ein Sportpark, ein Schulsportzentrum oder ein
  Freibad – ein Punkt auf der Karte. Name, Kategorie, Adresse, Lage, Betreiber und
  Eigentümer gehören zur Sportstätte und gelten für alle ihre Anlagen.
- Eine **Sportanlage** ist eine einzelne Einheit einer Sportstätte, z. B. ein Großspielfeld,
  eine Rundlaufbahn, eine Halle oder ein Becken. Typ, Sportarten, Baujahr, Baukosten und
  Ausstattung gehören zur Anlage.
- **Jede Sportanlage gehört zu genau einer Sportstätte:** Sie liegt in deren Ordner und nennt
  sie in `sportstaette_id`. Eine Sportstätte kann (noch) ohne Anlagen sein.
- Der **Kreis-Ordner** ergibt sich aus der Lage (Verwaltungsgebiete VG250). Sportstätten
  außerhalb von Rheinland-Pfalz liegen in `ohne-kreis`. Liegt eine Sportstätte nach einer
  Änderung ihrer Lage in einem anderen Kreis, bringt `uv run sportstaettenatlas einordnen`
  ihren Ordner dorthin.
- **Sportkomplexe** (mehrere Sportstätten an einem Ort, wie im bisherigen Atlas) bildet das
  Modell vorerst nicht ab.

**Ändern:**
- Angaben einer Sportstätte oder Anlage: die JSON-Datei bearbeiten.
- Neue Sportanlage: neue Datei im Ordner der Sportstätte, mit einer neuen UUID als Namen und
  als `id`, dazu `sportstaette_id` und `typ`.
- Neue Sportstätte: neuer Ordner (neue UUID) im Ordner ihres Kreises mit `<id>_meta.json`.
- Kontaktdaten (E-Mail-Adressen, Telefonnummern von Personen) gehören nicht hierher.

`seite` und `alkis` prüfen den Aufbau beim Lesen und nennen die betroffene Datei, wenn etwas
nicht passt. Werte, die nicht zu den Regeln des [Datenmodells](#datenmodell) passen (z. B. eine
PLZ mit sechs Ziffern), brechen nichts ab und stehen in `results/regelverstoesse.csv`.

## Datenmodell

Felder, Auswahllisten und Regeln stehen an einer Stelle: `src/sportstaettenatlas/modell.py`.
Der folgende Teil bis zur nächsten Überschrift „Typen und Gruppen“ wird daraus erzeugt
(`uv run sportstaettenatlas modell`, läuft auch bei `seite` mit) – bitte nicht hier ändern,
sondern im Modell.

- **Pflicht** heißt: ohne den Wert ist der Datensatz unvollständig. In den Dateien sind
  außerdem `id` (Sportstätte und Anlage) und `sportstaette_id` (Anlage) Pflicht.
- **Regeln** prüfen `seite`, `alkis` und das Formular. Werte, die nicht passen, brechen nichts
  ab; sie stehen nach `seite` in `results/regelverstoesse.csv`.
- Leere Angaben werden weggelassen. Unbekannte Felder melden die Regeln als Fehler – ein
  neues Feld also zuerst im Modell eintragen.

<!-- modell:anfang – erzeugt aus src/sportstaettenatlas/modell.py, nicht von Hand ändern -->

![Datenmodell](datenmodell.svg)

### Sportstätte (`<id>_meta.json`)

Der Standort, z. B. ein Sportpark, ein Schulsportzentrum oder ein Freibad.

| Feld | Bezeichnung | Typ | Pflicht | Regeln | Beschreibung |
|---|---|---|---|---|---|
| `id` | ID | Text |  |  | UUID, zugleich Name des Ordners (in der Datei Pflicht) |
| `name` | Name | Text | ja | höchstens 200 Zeichen; nicht leer |  |
| `kategorie` | Sportstättenkategorie | Auswahl | ja | „Sportplatz“, „Sporthalle“, „Tennissportstätte“, „Öffentlicher Sport- und Bewegungsraum“, „Reitsportstätte“, „Schwimmsportstätte“, „Schießsportstätte“, „Fitnessstudio“, „Golfsportstätte“, „Roll- und Skatesportstätte“, „Sportgelegenheiten in sonstigen Gebäuden“, „Radsportstätte“, „Flugsportstätte“, „Wintersportstätte“, „Wassersportstätte“, „Klettersportstätte“, „Motorsportstätte“, „Eissportstätte“, „Leistungsstützpunkt“, „Segelsportstätte“ |  |
| `adresse` | Adresse | Adresse |  |  |  |
| `lage` | Lage | Lage | ja |  | bestimmt Kreis und Gemeinde |
| `oeffentlicher_zugang` | Öffentlicher Zugang | Auswahl |  | „ja“, „nein“ |  |
| `schulsport` | Schulsport | Auswahl |  | „ja“, „nein“ |  |
| `zuschauerplaetze` | Zuschauerplätze | ganze Zahl |  | ≥ 0; ≤ 100000 |  |
| `betriebsstatus` | Betriebsstatus | Auswahl |  | „in Betrieb“, „vorübergehend geschlossen“, „stillgelegt/geschlossen“, „im Bau“, „in Planung“ |  |
| `eigentuemer` | Eigentümer | Text |  | höchstens 200 Zeichen | Name einer Organisation, keine Personen |
| `betreiber` | Betreiber | Text |  | höchstens 200 Zeichen | Name einer Organisation, keine Personen |
| `website` | Webseite | Text |  | Muster `^https?://\S+\.\S+$` | vollständige Adresse mit https:// |
| `sportarten` | Sportarten | Liste von Text |  |  |  |
| `quellen` | Herkunft | Objekt |  |  | je Quelle, z. B. ID, Datei und Stand im Atlas |
| `anlagen` | Sportanlagen | Liste von Sportanlage |  |  | stehen als eigene Dateien im Ordner der Sportstätte, nicht in `<id>_meta.json` |

```json
{
  "id": "9c24bfa6-71c1-4164-b226-061f0a139997",
  "name": "Sportplatz Musterdorf",
  "kategorie": "Sportplatz",
  "adresse": {
    "strasse": "Am Weg",
    "hausnummer": "1",
    "plz": "56068",
    "ort": "Koblenz"
  },
  "lage": {
    "lon": 7.59,
    "lat": 50.35
  },
  "betreiber": "TuS Musterdorf e.V.",
  "sportarten": [
    "Fußball",
    "Leichtathletik"
  ],
  "quellen": {
    "atlas_rlp": {
      "id": "9c24bfa6-…",
      "datei": "sportstaetten_04112026.csv",
      "stand": "2026-11-04"
    }
  }
}
```

### Adresse

| Feld | Bezeichnung | Typ | Pflicht | Regeln | Beschreibung |
|---|---|---|---|---|---|
| `strasse` | Straße | Text |  | höchstens 150 Zeichen |  |
| `hausnummer` | Hausnummer | Text |  | Muster `^\d+\s?[a-zA-Z]?(\s?[-/]\s?\d+\s?[a-zA-Z]?)?$`; höchstens 12 Zeichen | z. B. 12, 12a oder 2-4 |
| `adresszusatz` | Adresszusatz | Text |  | höchstens 150 Zeichen | z. B. Eingang Schulhof |
| `plz` | PLZ | Text |  | Muster `^\d{5}$` | fünf Ziffern |
| `ort` | Ort | Text |  | höchstens 100 Zeichen |  |

### Lage

| Feld | Bezeichnung | Typ | Pflicht | Regeln | Beschreibung |
|---|---|---|---|---|---|
| `lon` | Längengrad | Zahl | ja | ≥ 5.8; ≤ 9 | WGS84 |
| `lat` | Breitengrad | Zahl | ja | ≥ 48.8; ≤ 51.1 | WGS84 |

### Sportanlage (`<anlage-id>.json`)

Eine Einheit einer Sportstätte, z. B. ein Großspielfeld, eine Halle oder ein Becken.

| Feld | Bezeichnung | Typ | Pflicht | Regeln | Beschreibung |
|---|---|---|---|---|---|
| `id` | ID | Text |  |  | UUID, zugleich der Dateiname (in der Datei Pflicht) |
| `sportstaette_id` | Sportstätte | Text |  |  | ID der Sportstätte, zu der die Anlage gehört, = Name des Ordners (in der Datei Pflicht) |
| `typ` | Typ | Text | ja | höchstens 100 Zeichen; nicht leer | einheitlicher Typ aus src/sportstaettenatlas/anlagen.py, z. B. „Großspielfeld“ |
| `bezeichnung` | Name | Text |  | höchstens 100 Zeichen | eigener Name der Anlage, z. B. „Halle 1“, „Kunstrasen B“ |
| `sportarten` | Sportarten | Liste von Text |  |  |  |
| `baujahr` | Baujahr | ganze Zahl |  | ≥ 1800; ≤ 2100 |  |
| `baukosten_eur` | Baukosten | ganze Zahl |  | ≥ 0 | in Euro |
| `ausstattung` | Ausstattung | Liste von Text |  |  | z. B. Flutlicht, Beregnung, Umkleiden |
| `quellen` | Herkunft | Objekt |  |  | je Quelle, z. B. die Schreibweise im Atlas |

```json
{
  "id": "17abb3c4-7493-5549-a6ca-f432ef00fba3",
  "sportstaette_id": "9c24bfa6-71c1-4164-b226-061f0a139997",
  "typ": "Großspielfeld",
  "bezeichnung": "Kunstrasen B",
  "sportarten": [
    "Fußball"
  ],
  "baujahr": 1998,
  "baukosten_eur": 1200000,
  "ausstattung": [
    "Flutlicht",
    "Beregnung"
  ]
}
```

### Vorschlag (Formular → LimeSurvey, Frage `data`)

Was das Formular „Vorschlag“ als JSON in die LimeSurvey-Frage „data“ schreibt.

| Feld | Bezeichnung | Typ | Pflicht | Regeln | Beschreibung |
|---|---|---|---|---|---|
| `version` | Version des Formats | Auswahl |  | „1“ |  |
| `art` | Art | Auswahl | ja | „neu“, „aenderung“, „anlagen“ | neu: neue Sportstätte mit Anlagen; aenderung: Angaben einer Sportstätte; anlagen: Sportanlagen einer Sportstätte |
| `sportstaette_id` | Sportstätte | Text |  |  | ID der geänderten Sportstätte |
| `sportstaette` | Angaben der Sportstätte | Sportstaette |  |  | vollständig, nach der Änderung (bei neu und aenderung) |
| `anlagen` | Sportanlagen | Liste von Sportanlage |  |  | alle Anlagen nach der Änderung (bei neu und anlagen); vorhandene mit ihrer Kurz-ID (Anfang der UUID), neue ohne |
| `entfernte_anlagen` | Entfernte Sportanlagen | Liste von Text |  |  | Kurz-IDs |
| `geaendert` | Geänderte Felder | Liste von Text |  |  |  |
| `gemeinde` | Gemeinde | Text |  |  | Regionalschlüssel der Gemeinde an der Lage |
| `quelle` | Quelle | Text |  |  | z. B. „ALKIS ST000123“, wenn vorbelegt |
| `dubletten_geprueft` | Geprüfte Doppelungen | Liste von Text |  |  | IDs ähnlicher Sportstätten, die als verschieden bestätigt wurden |

```json
{
  "version": 1,
  "art": "anlagen",
  "sportstaette_id": "9c24bfa6-71c1-4164-b226-061f0a139997",
  "anlagen": [
    {
      "id": "17abb3c4",
      "typ": "Großspielfeld",
      "baujahr": 1998
    },
    {
      "typ": "Kleinspielfeld"
    }
  ],
  "entfernte_anlagen": [
    "1fb06acd"
  ]
}
```

<!-- modell:ende -->

## Typen und Gruppen der Sportanlagen

`typ` kommt aus einer festen Liste in `src/sportstaettenatlas/anlagen.py`: derzeit 84 Typen
in 14 Gruppen, nach denen Karte, Formular und Übersicht ordnen – Spielfelder, Tennis, Hallen
und Räume, Leichtathletik, Bäder, Reiten, Schießen, Freizeit und Bewegung, Rad- und
Motorsport, Wassersport, Eis- und Wintersport, Luftsport, Nebenräume und Zubehör, Weitere.
Der Atlas schreibt dieselbe Anlage oft verschieden („Nichtnormiertes Spielfeld“, „Nicht
normiertes Spielfeld“, „Großspielfeld (ab 5.000 m²)“); beim Einlesen wird daraus ein Typ,
die ursprüngliche Schreibweise bleibt unter `quellen`. Ein unbekannter Typ ist erlaubt; er
wird über Stichwörter einer Gruppe zugeordnet oder landet unter „Weitere“. Neue Typen
trägt man in `anlagen.py` ein.

Die **Kategorie** einer Sportstätte (Sportplatz, Sporthalle …) und der **Typ** einer
Sportanlage sind getrennte Listen: Ein „Sportplatz“ kann ein Großspielfeld, eine Rundlaufbahn
und eine Weitsprunganlage enthalten.

## IDs und Herkunft

- **Sportstätte:** die UUID aus dem Atlas, stabil auch über Änderungen hinweg. Neue
  Sportstätten bekommen eine neue UUID.
- **Sportanlage:** beim Einlesen aus Sportstätte, Typ und laufender Nummer abgeleitet; ein
  zweites Einlesen ergibt dieselben IDs. Von Hand angelegte Anlagen bekommen eine neue UUID.
  Auf der Webseite und in Vorschlägen steht kurz der Anfang der UUID (z. B. `[17abb3c4]`);
  das genügt, um die Datei im Ordner der Sportstätte zu finden.
- **`quellen`:** woher eine Angabe stammt. Verlauf und Urheber jeder Änderung stehen in der
  Git-Historie.
- **Nicht gespeichert** werden Kontaktdaten (E-Mail-Adressen, Telefonnummern) und jeder Wert,
  der eine E-Mail-Adresse enthält.

## Verhältnis zum ALKIS-Abgleich

Der ALKIS-Abgleich ([README](../README.md#analyse-alkis-abgleich)) hat eigene Sportstätten (Flächen der
Nutzung) und Sportanlagen (Gebäude und Bauwerke) mit laufenden Nummern. Sie stehen nur in
`results/` und auf der Webseite im Reiter „Analysen“, nie in `daten/`. Verbunden werden beide
über die Lage. Was der Abgleich findet, kommt über einen Vorschlag auf der Webseite in
den Bestand.
