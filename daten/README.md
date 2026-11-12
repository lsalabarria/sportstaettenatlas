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
nicht passt.

## Sportstätte (`<id>_meta.json`)

```json
{
  "id": "9c24bfa6-71c1-4164-b226-061f0a139997",
  "name": "Sportplatz Musterdorf",
  "kategorie": "Sportplatz",
  "adresse": {"strasse": "Am Weg", "hausnummer": "1", "plz": "56068", "ort": "Koblenz"},
  "lage": {"lon": 7.59, "lat": 50.35},
  "betreiber": "TuS Musterdorf e.V.",
  "sportarten": ["Fußball", "Leichtathletik"],
  "quellen": {"atlas_rlp": {"id": "9c24bfa6-…", "datei": "sportstaetten_04112026.csv", "stand": "2026-11-04"}}
}
```

| Feld | Inhalt |
|---|---|
| `id` | UUID, zugleich Name des Ordners; aus dem Atlas übernommen |
| `name`, `kategorie` | Name und Kategorie des Atlas (Sportplatz, Sporthalle, Tennissportstätte …) |
| `adresse` | `strasse`, `hausnummer`, `plz`, `ort` |
| `lage` | **Pflicht:** `lon`, `lat` in WGS84; bestimmt Kreis und Gemeinde |
| `oeffentlicher_zugang`, `schulsport` | `ja` oder `nein` |
| `zuschauerplaetze`, `betriebsstatus` | Zahl; z. B. „in Betrieb“ |
| `eigentuemer`, `betreiber`, `website` | Namen (keine Personen) und Webseite |
| `sportarten` | Sportarten der Sportstätte, wie der Atlas sie führt |
| `quellen` | Herkunft je Quelle, z. B. ID, Datei und Stand im Atlas |

## Sportanlage (`<anlage-id>.json`)

```json
{
  "id": "17abb3c4-7493-5549-a6ca-f432ef00fba3",
  "sportstaette_id": "9c24bfa6-71c1-4164-b226-061f0a139997",
  "typ": "Großspielfeld",
  "bezeichnung": "Kunstrasen B",
  "sportarten": ["Fußball"],
  "baujahr": 1998,
  "baukosten_eur": 1200000,
  "ausstattung": ["Flutlicht", "Beregnung"],
  "quellen": {"atlas_rlp": {"bezeichnung": "Großspielfeld (ab 5.000 m²)"}}
}
```

| Feld | Inhalt |
|---|---|
| `id` | UUID, zugleich der Dateiname |
| `sportstaette_id` | **Pflicht:** die Sportstätte, zu der die Anlage gehört (= Name des Ordners) |
| `typ` | **Pflicht:** einheitlicher Typ, z. B. „Großspielfeld“, „Rundlaufbahn“ (siehe unten) |
| `bezeichnung` | eigener Name der Anlage, z. B. „Halle 1“, „Kunstrasen B“ |
| `sportarten` | was auf dieser Anlage betrieben wird |
| `baujahr`, `baukosten_eur` | Baujahr; Baukosten in Euro |
| `ausstattung` | z. B. „Flutlicht“, „Beregnung“, „Umkleiden“ |
| `quellen` | Herkunft, z. B. die Schreibweise im Atlas |

Sportarten gibt es auf beiden Ebenen: Der Atlas kennt sie nur je Sportstätte, gepflegt werden
sie künftig je Anlage. Karte und Abgleich nehmen beide zusammen.

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
