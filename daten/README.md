# Datenbestand

Die Quelle der Daten des Sportstättenatlas. Änderungen werden hier gemacht – direkt auf
GitHub, per Pull Request, mit einer CSV-Datei oder über einen Vorschlag auf der Webseite – und
erscheinen nach `uv run sportstaettenatlas seite` auf der Karte. Wer wann was geändert hat,
steht in der Git-Historie. Kontaktdaten gehören nicht hierher ([README](../README.md#kontaktdaten)).

```
RP/                                       Land
└─ 07111-koblenz/                         Kreis (aus der Lage bestimmt)
   └─ 9c24bfa6-…/                         Sportstätte
      ├─ 9c24bfa6-…_meta.json             ihre Angaben: Name, Kategorie, Adresse, Lage …
      ├─ 17abb3c4-….json                  eine Sportanlage, z. B. ein Großspielfeld
      └─ 1fb06acd-….json                  eine Sportanlage, z. B. eine Rundlaufbahn
   └─ sportkomplexe/                      nur in Kreisen, die Sportkomplexe haben
      └─ b1f3e6a2-….json                  ein Sportkomplex (Name, Adresse, Lage)
organisationen/RP/<Art>/                  Verzeichnis der Organisationen, je Art ein Ordner
└─ 3f0c2a8e-….json                        ein Verein, eine Gemeinde, ein Verband …
stuetzpunkte/                             Stützpunkte des Leistungssports
└─ c4d2a7e1-….json                        z. B. ein Bundesstützpunkt (Art, Sportarten, Sportstätten)
outside/                                  Sportstätten außerhalb von Rheinland-Pfalz
└─ NW/                                    Land (aus dem Gemeindeschlüssel), aufgebaut wie ein Kreis
```

## Begriffe

- Eine **Sportstätte** ist der Standort, z. B. ein Sportpark, ein Schulsportzentrum oder ein
  Freibad – ein Punkt auf der Karte. Ihre Angaben gelten für alle ihre Anlagen.
- Eine **Sportanlage** ist eine Einheit einer Sportstätte, z. B. ein Großspielfeld, eine
  Rundlaufbahn, eine Halle oder ein Becken. Zu welcher Sportstätte sie gehört, sagt allein der
  Ordner, in dem ihre Datei liegt. Eine Sportstätte kann (noch) ohne Anlagen sein.
- Eine **Organisation** ist ein Verein, eine Kommune, ein Verband oder ein Unternehmen, das
  Sportstätten besitzt (`eigentuemer`), betreibt (`betreiber`) oder nutzt (`nutzer`). Sie steht
  einmal in `organisationen/`; die Sportstätten nennen sie beim Namen, auch in einer ihrer
  weiteren Schreibweisen. Ihre **Art** (Stadt/Gemeinde, Sportverein im LSB RLP …) steht bei der
  Sportstätte (`betreiber_typ`, `eigentuemer_typ`) oder sonst im Verzeichnis; fehlt sie, ist
  sie unbekannt – aus dem Namen wird nichts geschätzt. Auf der Karte zählt sie als Verein,
  Kommune oder sonstige (`ORGANISATIONSTYPEN` in `modell/klassen.py`).
- Der **Kreis-Ordner** ergibt sich aus der Lage (Verwaltungsgebiete VG250). Sportstätten
  ohne passenden Kreis liegen in `ohne-kreis`; nach einer Änderung der Lage bringt
  `uv run sportstaettenatlas einordnen` den Ordner in den richtigen Kreis.
- Sportstätten **außerhalb von Rheinland-Pfalz** liegen in `outside/<Land>/`, ihre
  Sportkomplexe in `outside/<Land>/sportkomplexe/`. Sie erscheinen nicht auf der Webseite,
  `einordnen` lässt sie liegen, und die Prüfungen des Landes (Ort, Rheinland-Pfalz, PLZ,
  Kreis-Ordner, Eigentum der Kommune) entfallen.
- Ein **Sportkomplex** fasst mehrere Sportstätten an einem Ort zusammen, z. B. ein
  Sportzentrum mit Halle, Stadion und Freibad. Er ist optional: Die meisten Sportstätten
  gehören zu keinem. Die Sportstätten verweisen in `sportkomplex` auf seine ID; er selbst hat
  nur Name, Adresse und (optional) Lage – Eigentümer, Betreiber und Anlagen bleiben bei den
  Sportstätten. Siehe [Sportkomplexe](#sportkomplexe).
- Ein **Stützpunkt** ist die Anerkennung als Olympiastützpunkt, Bundesstützpunkt (auch
  Nachwuchs, Para Sport), Landesleistungszentrum oder Landesstützpunkt für bestimmte Sportarten.
  Er nennt seine Sportstätten in `sportstaetten` und, wenn alle Sportstätten eines Sportkomplexes
  dazugehören, diesen in `sportkomplexe`. Eine Sportstätte kann zu mehreren Stützpunkten
  gehören. Siehe [Stützpunkte](#stützpunkte).

## Sportkomplexe

Ein Sportkomplex lohnt sich nur, wenn **mindestens zwei** Sportstätten zusammengehören –
`pruefen` meldet kleinere („Kleiner Sportkomplex“) und solche, deren Sportstätten mehr als
1 km auseinanderliegen. Ein gemischtes Gelände mit einem Betreiber bleibt eine Sportstätte mit
mehreren Anlagen.

```bash
# neu anlegen und zuordnen (IDs oder ihr Anfang, ab 8 Zeichen)
uv run sportstaettenatlas sportkomplex 9c24bfa6 17abb3c4 --name "Sportzentrum Musterdorf"
# weitere Sportstätte dazu; mit --name auch umbenennen
uv run sportstaettenatlas sportkomplex 1fb06acd --zu b1f3e6a2
# herausnehmen
uv run sportstaettenatlas sportkomplex 1fb06acd --entfernen
```

Die Datei liegt in `<Kreis>/sportkomplexe/` des Kreises, in dem die meisten seiner
Sportstätten liegen, oder – mit eigener `lage` – in dem seiner Lage; `einordnen` verschiebt sie.
Adresse und Lage danach von Hand in der Datei ergänzen. Viele auf einmal: als CSV mit der
Vorlage `vorlage_sportkomplexe.csv` ([CSV einlesen](#csv-einlesen)). Einen Sportkomplex
löschen: die Datei entfernen und `sportkomplex` aus den Sportstätten nehmen (`--entfernen`).

Auf der Webseite: Im Formular einer Sportstätte steht unter „Sportkomplex“ eine Auswahl der
Komplexe in der Nähe (3 km). Die Art „Sportkomplex“ des Vorschlags legt einen neuen an, ändert
Name, Adresse und Sportstätten eines vorhandenen oder löst ihn auf; `vorschlaege` trägt das
direkt ein.

## Stützpunkte

Ein Stützpunkt steht in `stuetzpunkte/<id>.json` mit Name, Art, Sportarten, Träger (eine
Organisation aus dem Verzeichnis), anerkannt von, Gültigkeit (`gueltig_ab`, `gueltig_bis`,
als Datum `2028-12-31`), Quelle der Anerkennung und den Sportstätten bzw. Sportkomplexen.
`pruefen` meldet:

- eine abgelaufene Anerkennung („Stützpunkt abgelaufen“) – dann `gueltig_bis` verlängern oder
  den Stützpunkt löschen,
- Sportstätten oder Sportkomplexe, die es nicht gibt („Stützpunkt-Verweis“),
- Sportstätten, die zusätzlich über ihren Sportkomplex dazugehören („Stützpunkt doppelt“),
- einen Träger, der nicht im Verzeichnis steht („Träger des Stützpunkts“).

Viele auf einmal: als CSV mit der Vorlage `vorlage_stuetzpunkte.csv` ([CSV einlesen](#csv-einlesen)).
Auf der Webseite: Filter auf der Karte, eigener Teil in der Liste, Zahlen je Ebene in der
Übersicht; die Art „Stützpunkt“ des Vorschlags trägt einen neuen ein, ändert oder löscht ihn,
und `vorschlaege` übernimmt das direkt.

## Ändern

**Von Hand:** die JSON-Datei bearbeiten. Eine neue Sportanlage ist eine neue Datei im Ordner
der Sportstätte (neue UUID als Name und `id`, dazu `typ`), eine neue
Sportstätte ein neuer Ordner im Ordner ihres Kreises mit `<id>_meta.json`, eine neue
Organisation eine Datei in `organisationen/`.

`seite` und `alkis` prüfen den Aufbau beim Lesen und nennen die betroffene Datei, wenn etwas
nicht passt. Werte gegen die Regeln des [Datenmodells](#datenmodell) (z. B. eine PLZ mit sechs
Ziffern) brechen nichts ab und stehen in [`erzeugt/regelverstoesse.csv`](erzeugt/regelverstoesse.csv).

### CSV einlesen

`uv run sportstaettenatlas bestand DATEI.csv …` schreibt CSV-Dateien direkt in die
JSON-Dateien. `--probe` zeigt vorher, welche Spalte in welches Feld geht. Erkannt werden:

- der **Export des bisherigen Atlas** (Spalten ID, Name, Sportstättenkategorie, …, Latitude,
  Longitude),
- eine Tabelle der **Sportstätten** (eine Zeile je Sportstätte; `anlagen` darf die Typen ihrer
  Sportanlagen nennen),
- eine Tabelle der **Sportanlagen** (eine Zeile je Anlage, mit `sportstaette_id`: in welchen
  Ordner sie kommt; `id` für vorhandene, auch die Kurz-ID von der Webseite),
- eine Tabelle der **Sportkomplexe** (eine Zeile je Komplex mit `name` und der Spalte
  `sportstaetten`: die IDs seiner Sportstätten, auch die Kurz-ID; ohne `id` folgt sie aus Name
  und Ort, gleiche Zeile, gleiche ID). Die Sportstätten bekommen den Komplex in `sportkomplex`,
  in jedem Modus; herausgenommen wird keine.
- eine Tabelle der **Stützpunkte** (eine Zeile je Stützpunkt mit `name`, `art` und den Spalten
  `sportstaetten` bzw. `sportkomplexe`: IDs, auch die Kurz-ID; Datum als `31.12.2028` oder
  `2028-12-31`; ohne `id` folgt sie aus dem Namen). Unbekannte IDs werden gezählt und übersprungen.
- eine Tabelle der **Organisationen** (`name` und `typ` bzw. „Art“, ohne Kategorie und Lage).
- eine Tabelle zum **Entfernen** (Spalten `art`, `id`, `begruendung`; Art: Sportstätte,
  Sportanlage, Sportkomplex, Stützpunkt oder Organisation; ID auch die Kurz-ID). Sie kommt nach
  allen anderen Dateien desselben Aufrufs dran, die Zeilen von oben nach unten. Übersprungen
  wird mit Warnung, was keine Begründung hat, nicht eindeutig ist oder worauf noch etwas
  zeigt (eine Sportanlage oder ein Stützpunkt auf eine Sportstätte, eine Sportstätte auf ihren
  Sportkomplex oder ihre Organisationen). Vor einer Sportstätte stehen also ihre Sportanlagen
  in der Tabelle, jede mit eigener Begründung. Jede Entfernung steht
  mit Datum und Begründung in `daten/entfernt.csv` – die Datei ist öffentlich, also nur
  Sachliches und keine Personen. Eine Doppelung zusammenführen: im selben Aufruf die
  Tabelle der Sportanlagen für die richtige Sportstätte und die Tabelle zum Entfernen der
  überzähligen angeben.

**Spalten** heißen wie das Feld (`plz` oder `adresse.plz`) oder wie seine Beschriftung („PLZ“);
Groß-/Kleinschreibung, Umlaute und Satzzeichen sind egal. Eine Anzahl je Wert steht in einer
Spalte (`felder_je_belag`: `Sand: 3; Rasen: 1`) oder in einer Spalte je Wert
(`felder_je_belag_sand`: `3`). Das Trennzeichen (`;`, `,` oder Tab) und die Kodierung
(UTF-8 oder Windows-1252) werden erkannt. `uv run sportstaettenatlas vorlage` schreibt je
Tabelle eine Vorlage mit allen Spalten und einer Beispielzeile (vor dem Einlesen löschen).

**Werte:**

| Feld | so schreiben |
|---|---|
| Liste | mit `;` getrennt (ohne `;` auch mit Komma): `Fußball; Leichtathletik` |
| Anzahl je Wert | `Sand: 3; Rasen: 1` oder `3× Sand` |
| ja/nein | `ja`, `nein`, auch `x`, `1`/`0`, `wahr`/`falsch` |
| Zahl | `12,5` oder `12.5`; `1.200.000`; ganze Zahlen auch `1.200` |
| Auswahl | wie im Modell, Groß-/Kleinschreibung egal |
| Lage | `lat`/`lon` in Grad (WGS84); UTM-Werte (EPSG:25832) werden umgerechnet |
| Hausnummer | `12`, `12a`, `2-4`; `6.0` (von Excel als Zahl gespeichert) wird `6` |
| Webseite | mit `https://`; `www.verein.de` bekommt es vorangestellt |

Platzhalter wie `-` oder `k. A.` bei Hausnummer und Webseite gelten als leer. Für den
vorhandenen Bestand macht das `uv run sportstaettenatlas migrieren --bereinigen`.

Ein Wert, der nicht passt, wird übernommen, wie er ist, und erscheint unter den
Regelverstößen.

**Vorhandenes:**

| `--modus` | neue Einträge | vorhandene: leere Felder | vorhandene: gefüllte Felder |
|---|---|---|---|
| `neu` (Standard) | anlegen | – | – |
| `ergaenzen` | anlegen | füllen | bleiben |
| `aktualisieren` | anlegen | füllen | überschreiben |

Gelöscht wird nie etwas, leere Zellen ändern nichts. Eine **Änderung** braucht nur die `id`
(auch die Kurz-ID) und die Spalten, die sich ändern, mit `--modus aktualisieren`. Eine
Tabelle der Sportanlagen legt auch
im Modus `neu` Anlagen bei vorhandenen Sportstätten an. Vorhandene Anlagen findet die ID
(auch die Kurz-ID); ohne ID ist die n-te Anlage eines Typs in der Tabelle die n-te dieses Typs
der Sportstätte. Organisationen findet die ID oder der Name.

## Datenmodell

Alle Felder mit Typ und Regeln, die Felder je Anlagentyp, die Auswahllisten und das
Diagramm stehen in **[erzeugt/datenmodell.md](erzeugt/datenmodell.md)**. Die Datei wird aus
`src/sportstaettenatlas/modell/` erzeugt (`uv run sportstaettenatlas modell`) – bitte dort
ändern, nicht in der erzeugten Datei.

- **Pflicht:** ohne den Wert ist der Datensatz unvollständig. In den Dateien ist außerdem `id`
  Pflicht. Leere Angaben werden weggelassen; ein unbekanntes
  Feld ist ein Regelverstoß.
- **nur für bestimmte Typen:** welche, steht unter [Felder je Anlagentyp](erzeugt/datenmodell.md#felder-je-anlagentyp)
  (`MERKMALE` in `modell/klassen.py`). Das Formular zeigt das Feld nur dort, die Übersicht zählt es nur
  unter ihnen; erlaubt ist es überall.
- **Auswahl:** die Werte stehen einmal unter [Auswahllisten](erzeugt/datenmodell.md#auswahllisten).


## Typen und Gruppen der Sportanlagen

`typ` kommt aus einer festen Liste in `src/sportstaettenatlas/modell/anlagen.py` (Typen in Gruppen,
nach denen Karte, Formular und Übersicht ordnen). Exporte schreiben dieselbe Anlage oft
verschieden („Nichtnormiertes Spielfeld“, „Großspielfeld (ab 5.000 m²)“); beim Einlesen wird
daraus ein Typ. Ein unbekannter Typ ist
erlaubt und landet über Stichwörter in einer Gruppe oder unter „Weitere“. Neue Typen kommen in
`anlagen.py`.

Die **Kategorie** einer Sportstätte und der **Typ** einer Sportanlage sind getrennte Listen,
ohne Regel, welcher Typ zu welcher Kategorie gehört: Ein „Sportplatz“ kann ein Großspielfeld,
eine Rundlaufbahn und auch Tennisplätze enthalten. Das Formular schlägt zuerst die Typen vor, die im Bestand
bei der gewählten Kategorie vorkommen.

## IDs

- **Sportstätte:** die UUID aus der Quelle, stabil über Änderungen hinweg. Neue bekommen
  eine neue UUID; aus einer CSV ohne `id` eine feste aus Name und Lage.
- **Sportanlage:** beim Einlesen aus Sportstätte, Typ und laufender Nummer abgeleitet (ein
  zweites Einlesen ergibt dieselben IDs); von Hand angelegte bekommen eine neue UUID. Webseite
  und Vorschläge nennen kurz den Anfang der UUID (z. B. `17abb3c4`).
- **Organisation:** aus dem Namen abgeleitet, wenn sie aus dem Bestand oder einer CSV entsteht.

Woher eine Angabe stammt, wer sie geändert hat und wann, steht in der Git-Historie.
