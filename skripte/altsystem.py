"""Einmaliger Import aus dem Altsystem (Datenbank-Export als CSV) nach daten/.

    uv run python skripte/altsystem.py ../legacy_data --probe   # nur zählen, daten/ bleibt
    uv run python skripte/altsystem.py ../legacy_data           # übernehmen

Der Ordner enthält die Tabellen als `dbs…_table_<name>.csv` (mit Spaltennamen) und
`public_submissions.csv`. Gelesen werden nur die Tabellen unten; Kontaktdaten (E-Mail,
Telefon, Ansprechpartner) liest das Skript nie, Werte mit E-Mail-Adresse entfernt
`bestand.bereinigen`. Gelöschte Einträge (`geloeschtam`) bleiben weg.

- Organisationen: die Vereine mit LSB-Nummer und alle, auf die eine Sportstätte verweist
  (Eigentümer, Betreiber, Nutzer). Kommunen und Kreise findet der Name im Verzeichnis.
- Sportstätten: alle. Liegt die Koordinate außerhalb von Rheinland-Pfalz und sagt auch der
  Gemeindeschlüssel nicht RLP, kommt sie nach daten/outside/<Land>/. Vorhandene werden
  ergänzt (leere Felder gefüllt, fehlende Anlagen angelegt); ihre Anlagen bekommen die IDs
  wie beim Einlesen des Atlas-Exports (n-te Anlage eines Typs), neue behalten die alte ID.
- Sportkomplexe mit mindestens zwei Sportstätten; zugeordnet werden nur Sportstätten, die
  noch keinen Sportkomplex haben.
- Stützpunkte so, wie sie in der Datenbank stehen: ein Eintrag je Zeile.
- Offene Vorschläge („pending“) werden zu einem LimeSurvey-Export
  results/altsystem_vorschlaege.csv; den prüft `sportstaettenatlas vorschlaege … --probe`.

Mehrfach ausführen ändert nichts mehr (Modus „ergaenzen“).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import sys
import tempfile
import uuid
from collections import Counter, defaultdict
from pathlib import Path

from sportstaettenatlas import anlagen as anlagen_typen
from sportstaettenatlas import atlas, modell
from sportstaettenatlas.bestand import (
    OHNE_KREIS,
    OUTSIDE,
    _laender,
    _staetten_dirs,
    anlage_id,
    kreis_ordner,
    lies_bestand,
    lies_organisationen,
    schreibe_bestand,
    schreibe_organisationen,
    schreibe_sportkomplexe,
    schreibe_stuetzpunkte,
)
from sportstaettenatlas.kommunen import _kern
from sportstaettenatlas.vorschlaege import _NAMENSRAUM

csv.field_size_limit(10**9)

# Gemeindeschlüssel (erste zwei Stellen) → Kürzel des Landes für daten/outside/<Land>/
LAENDER = {
    "01": "SH", "02": "HH", "03": "NI", "04": "HB", "05": "NW", "06": "HE", "07": "RP",
    "08": "BW", "09": "BY", "10": "SL", "11": "BE", "12": "BB", "13": "MV", "14": "SN",
    "15": "ST", "16": "TH",
}  # fmt: skip
UNBEKANNT = "unbekannt"

# Beschriftungen des Altsystems → Werte im Modell, wo sie abweichen
ORG_TYPEN = {
    "Stadt / Gemeinde": "Stadt/Gemeinde",
    "Privatwirtschaftlich / kommerziell": "Privatwirtschaftlich/kommerziell",
    "LSB RLP - Sportverein": "Sportverein im LSB RLP",
    "LSB RLP - Sportverband": "Sportverband im LSB RLP",
}
WAEHRUNGEN = {"Euro": "€", "D-Mark": "DM", "DDR-Mark": "DDR-Mark", "Reichsmark": "RM"}
BODENBELAEGE = {"Hartplatz / Tenne": "Hartplatz/Tenne"}
FUNKTIONSRAEUME = {
    "Umkleideraum": "Umkleide- und Sanitärräume - Sporttreibende",
    "Umkleide Personal": "Umkleide- und Sanitärräume - Personal",
    "Sanitärraum": "Sanitärräume - Publikum",
    "Erste Hilfe Raum": "Erste-Hilfe-Räume",
    "Verwaltung": "Büro- und Verwaltungsräume",
    "Lagerraum": "Material- und Lagerräume",
    "Geräteraum": "Geräteräume",
    "Haustechnikraum": "Technikräume",
    "Schulungsraum": "Schulungs- / Seminarraum",
    "Gastronomie": "Gastronomie",
    "Sauna": "Sauna",
}
ENERGIEBEREICHE = {"HEIZUNG": "Heizung", "WASSER": "Warmwasser", "STROM": "Strom"}
ENERGIETRAEGER = {
    "Holz": "Holz/Pellets/Hackschnitzel",
    "Umweltwärme": "Umweltwärme (Wärmepumpe)",
    "Heizanlage": "Betrieb über Heizanlage",
}
STROM_ALS = {  # „Strom“ heißt je Bereich anders
    "Heizung": "Strom (z.B. Nachtspeicherofen, Konvektoren etc.)",
    "Warmwasser": "Strom (z.B. Durchlauferhitzer, Boiler)",
}
VERBRAUCHSARTEN = {"Holz": "Holz/Pellets/Hackschnitzel"}
EINHEITEN = {"KWh": "kWh"}
STUETZPUNKTE = {"OSP": "Olympiastützpunkt", "BSP": "Bundesstützpunkt", "LSP": "Landesstützpunkt"}

# Spalten der Sportanlage: Altsystem → Modell (Zahlen); die erste befüllte gewinnt
ANLAGE_ZAHLEN = {
    "laenge": ("laenge",),
    "breite": ("breite",),
    "hoehe": ("hoehe",),
    "flaeche": ("nutzflaeche", "groesse"),
    "bahnlaenge": ("bahnlaenge",),
    "wasserflaeche_relevant": ("relevante_wasserflaeche",),
    "wasserflaeche_lehrbecken": ("wasserflaechelernundkursbecken",),
    "baukosten": ("baukosten",),
}
ANLAGE_GANZZAHLEN = {
    "bahnen": ("anzbahnen",),
    "spielfelder": ("anzspielfelder", "anztennisfelder"),
    "loecher": ("anzloecher",),
    "becken_bis_25m": ("anzbeckenbis25",),
    "becken_25_bis_50m": ("anzbeckenbis25bis50",),
    "becken_ueber_50m": ("anzbeckenueber50",),
    "becken_tiefer_3m": ("anzbeckenue3m",),
    "nichtschwimmerbecken": ("anznichtschwimmer", "nichtschwimmer"),
    "lehrbecken": ("anzlehrbecken", "lehrbecken"),
    "kinderbecken": ("anzkinderbecken", "kinderbecken"),
    "erholungsbecken": ("anzerholungsbecken", "erholungsbecken"),
    "sprungtuerme_3m": ("anzturm3m",),
    "sprungtuerme_5m": ("anztur5m",),
    "sprungtuerme_10m": ("anztur10m",),
    "schiessstaende_gedeckt": ("anzschiesstubgedeckt",),
    "schiessstaende_teilgedeckt": ("anzschiesstuboteilgedeckt", "anzschiesstubteilgedeckt"),
    "schiessstaende_offen": ("anzschiesstuboffen",),
    "lifte": ("anzlift",),
    "spielgeraete": ("anz_spielgeraete",),
    "oeffnungsstunden": ("oeffnungsstunden",),
    "oeffnungsstunden_schule": ("oeffnungsstundenschule",),
    "oeffnungsstunden_verein": ("oeffnungsstundenverein",),
}
ANLAGE_JA_NEIN = {
    "sprungturm": "sprungturm",
    "trennvorhang": "vorhangvorhanden",
    "bewaesserung": "bewaesserung",
    "hoehenverstellbares_netz": "hoehenverstellnetz",
    "kletterwand": "kletterwand",
    "boulderwand": "boulderwand",
    "dressurplatz": "dressurplatz",
    "springplatz": "springplatz",
    "flutlicht": "flutlicht",
    "barrierefrei_erreichbar": "barrierefreierreichbar",
}
FELDER_JE_BELAG = {
    "sportparkett": "Sportparkett",
    "rasen": "Rasen",
    "kunstrasen": "Kunstrasen",
    "hartplatz_tenne": "Hartplatz/Tenne",
    "beton": "Beton",
    "sand": "Sand",
    "kunststoff": "Kunststoff",
    "teppich": "Teppich",
    "granulat": "Granulat",
    "sonstiges": "Sonstiges",
}
FELDER_JE_SPORTART = {
    "badminton": "Badminton",
    "basketball": "Basketball",
    "faustball": "Faustball",
    "funino": "Funino",
    "fussball": "Fußball",
    "futsal": "Futsal",
    "hallenhockey": "Hallenhockey",
    "handball": "Handball",
    "volleyball": "Volleyball",
    "sonstige": "Sonstige",
    "americanfootball": "American Football",
    "baseball": "Baseball",
    "beachvolleyball": "Beachvolleyball",
    "cricket": "Cricket",
    "feldhockey": "Feldhockey",
    "rugby": "Rugby",
    "softball": "Softball",
    "streetball": "Streetball",
}
KLEINFELDER = {
    "fussball": "Fußball",
    "hockey": "Hockey",
    "basketball": "Basketball",
    "streetball": "Streetball",
    "sonstige": "Sonstige",
}


# --- Lesen ------------------------------------------------------------------------------


def lies_tabelle(ordner: Path, name: str) -> list[dict]:
    """Tabelle `name` (dbs…_table_<name>.csv) ohne gelöschte Zeilen; NULL wird leer."""
    treffer = sorted(ordner.glob(f"*_table_{name}.csv")) or sorted(ordner.glob(f"{name}.csv"))
    if not treffer:
        return []
    text = treffer[0].read_bytes().decode("utf-8-sig")
    zeilen = []
    for z in csv.DictReader(io.StringIO(text)):
        z = {k: ("" if v in ("NULL", "\\N", None) else v) for k, v in z.items()}
        if not z.get("geloeschtam"):
            zeilen.append(z)
    return zeilen


def _leer(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _zahl(v) -> float | None:
    if _leer(v):
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def _ganz(v) -> int | None:
    z = _zahl(v)
    return None if z is None else round(z)


def _jahr(v) -> int | None:
    j = _ganz(v)
    return j if j and j > 0 else None


def _ja_nein(v) -> str | None:
    """1/0 (auch true/false) → ja/nein; -1 und Leeres heißen keine Angabe."""
    if isinstance(v, bool):
        return "ja" if v else "nein"
    j = _ganz(v)
    return {1: "ja", 0: "nein"}.get(j)


def _text(v) -> str | None:
    if isinstance(v, float) and v.is_integer():  # Zahlen aus dem Formular, z. B. Hausnummer 100
        v = int(v)
    return None if _leer(v) else str(v).strip()


def _url(v) -> str | None:
    u = _text(v)
    if not u:
        return None
    return u if u.startswith(("http://", "https://")) else f"https://{u}"


def _ohne_leere(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


class Altsystem:
    """Die Tabellen des Altsystems und ihre Umrechnung ins Modell."""

    def __init__(self, ordner: Path, lage_aus=atlas.lage):
        self.ordner = Path(ordner)
        self.lage_aus = lage_aus
        t = lambda n: lies_tabelle(self.ordner, n)
        self.typen = {z["id"].lower(): z for z in t("typenum")}
        self.adressen = {z["id"]: z for z in t("adresse")}
        self.organisationen = {z["id"]: z for z in t("organisation")}
        self.staetten = {z["id"]: z for z in t("sportstaette")}
        self.anlagen: dict[str, list[dict]] = defaultdict(list)
        for z in sorted(t("sportanlage"), key=lambda z: (z.get("erstelltam") or "", z["id"])):
            if z.get("sportstaetteid") in self.staetten:
                self.anlagen[z["sportstaetteid"]].append(z)
        self.anlage_staette = {a["id"]: sid for sid, al in self.anlagen.items() for a in al}
        self.sportarten: dict[str, list[dict]] = defaultdict(list)  # Anlage → Sportarten
        for z in t("sportanlagesportart"):
            self.sportarten[z["sportanlageid"]].append(z)
        self.je_staette: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        for name in ("funktionsraum", "energietraeger", "jahresverbrauch", "sportstaettenutzer"):
            for z in t(name):
                self.je_staette[name][z["sportstaetteid"]].append(z)
        self.kosten: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        for name in ("sanierung", "foerderung"):
            for z in t(name):
                self.kosten[name][z["entity_id"]].append(z)
        self.komplexe = {z["id"]: z for z in t("sportkomplex")}
        self.stuetzpunkte = t("leistungssport_stuetzpunkt")
        self.org_name: dict[str, str] = {}  # ID im Altsystem → Name im Verzeichnis
        self.neue_anlage_ids: dict[str, str] = {}  # ID im Altsystem → ID in daten/

    # --- Auswahllisten ----------------------------------------------------------------

    def typ(self, tid) -> dict:
        return self.typen.get(str(tid or "").lower(), {})

    def bezeichnung(self, tid) -> str | None:
        return _text(self.typ(tid).get("bezeichnung"))

    def kategorie(self, tid) -> str | None:
        t = self.typ(tid)
        return _text(t.get("label")) or _text(t.get("bezeichnung"))

    def org_typ(self, tid) -> str | None:
        t = self.typ(tid)
        label = _text(t.get("label")) or _text(t.get("bezeichnung"))
        return ORG_TYPEN.get(label, label) if label else None

    def waehrung(self, tid) -> str | None:
        b = self.bezeichnung(tid)
        return WAEHRUNGEN.get(b, b) if b else None

    # --- Organisationen -----------------------------------------------------------------

    def organisation(self, z: dict) -> dict:
        typ = self.org_typ(z.get("typid"))
        lsb = _text(z.get("extref"))
        lsb = lsb if lsb and lsb.isdigit() and len(lsb) == 7 else None
        if lsb and typ in (None, "Sonstiger Sportverein"):
            typ = "Sportverein im LSB RLP"
        return _ohne_leere(
            {
                "id": z["id"],
                "name": _text(z.get("bezeichnung")),
                "typ": typ,
                "website": _url(z.get("webseite")),
                "lsb_nummer": lsb,
            }
        )

    def benoetigte_organisationen(self) -> list[dict]:
        """Vereine mit LSB-Nummer und alle, auf die eine Sportstätte verweist."""
        verwiesen = {
            z.get(k) for z in self.staetten.values() for k in ("eignerorgaid", "betreiberorgaid")
        }
        verwiesen |= {
            n.get("organisationid")
            for ns in self.je_staette["sportstaettenutzer"].values()
            for n in ns
        }
        out = []
        for oid, z in self.organisationen.items():
            o = self.organisation(z)
            if o.get("name") and (oid in verwiesen or o.get("lsb_nummer")):
                out.append(o)
        return out

    def ordne_kommunen_zu(self, orgs: list[dict], vorhanden: list[dict]) -> int:
        """Kommunen und Kreise des Altsystems tragen oft nur den Kurznamen („Andernach“);
        passt der Name ohne Zusätze genau zu einer Kommune im Verzeichnis (mit gleichem
        Anfang des Schlüssels), bekommt der Eintrag deren Namen. Liefert die Zahl."""
        kommunal = [
            o for o in vorhanden if modell.ORGANISATIONSTYPEN.get(o.get("typ") or "") == "Kommune"
        ]
        n = 0
        for o in orgs:
            if modell.ORGANISATIONSTYPEN.get(o.get("typ") or "") != "Kommune":
                continue
            ags = _text(self.organisationen[o["id"]].get("ags")) or ""
            kern = _kern(o["name"])[0]
            treffer = [
                k
                for k in kommunal
                if str(k.get("ars") or "").startswith(ags[:5])
                and kern in {_kern(x)[0] for x in [k["name"], *(k.get("weitere_namen") or [])]}
            ]
            if len(treffer) == 1 and treffer[0]["name"] != o["name"]:
                o["name"], o["typ"] = treffer[0]["name"], treffer[0].get("typ")
                n += 1
        return n

    def name_der_org(self, oid) -> str | None:
        if isinstance(oid, dict):  # im Formular: {"id", "bezeichnung", …}
            return self.org_name.get(oid.get("id")) or _text(oid.get("bezeichnung"))
        return self.org_name.get(oid) or _text(self.organisationen.get(oid, {}).get("bezeichnung"))

    # --- Sportstätten -------------------------------------------------------------------

    def adresse(self, z: dict) -> dict:
        a = z.get("adresse") if isinstance(z.get("adresse"), dict) else None
        a = a or self.adressen.get(z.get("adresseid") or "", {})
        return _ohne_leere(
            {
                "strasse": _text(a.get("strasse")),
                "hausnummer": _text(a.get("hausnummer")),
                "adresszusatz": _text(a.get("adresszusatz")),
                "plz": _text(a.get("postleitzahl")),
                "ort": _text(a.get("ort")),
            }
        )

    def ags(self, z: dict) -> str:
        return _text(self.adressen.get(z.get("adresseid") or "", {}).get("ags")) or ""

    def lage(self, z: dict) -> dict | None:
        hoch, rechts = _zahl(z.get("utm32nhoch")), _zahl(z.get("utm32nrechts"))
        return self.lage_aus(hoch, rechts) if hoch and rechts else None

    def funktionsraeume(self, raeume: list[dict]) -> dict:
        out: Counter = Counter()
        for r in raeume:
            name = self.bezeichnung(r.get("typid") or r.get("identifier")) or _text(r.get("label"))
            name = re.sub(r"\s+-\s+[0-9a-fA-F-]{36}$", "", name or "")  # „… - <ID>“
            name = FUNKTIONSRAEUME.get(name, name)
            anzahl = _ganz(r.get("anzahl"))
            anzahl = 1 if anzahl is None else anzahl
            if name and anzahl > 0:
                out[name] += anzahl
        return dict(out)

    def energietraeger(self, zeilen: list[dict]) -> list[dict]:
        out = []
        for z in zeilen:
            t = self.typ(z.get("energietraegertypid") or z.get("identifier"))
            bereich = ENERGIEBEREICHE.get(t.get("prog") or z.get("typ") or "")
            art = _text(t.get("bezeichnung")) or _text(z.get("bezeichnung"))
            if not art:
                continue
            art = STROM_ALS.get(bereich, art) if art == "Strom" else ENERGIETRAEGER.get(art, art)
            out.append(
                _ohne_leere(
                    {
                        "bereich": bereich,
                        "art": art,
                        "einbaujahr": _jahr(z.get("einbaujahr")),
                        "beschreibung": _text(z.get("beschreibung")),
                    }
                )
            )
        return out

    def verbraeuche(self, zeilen: list[dict]) -> list[dict]:
        out = []
        for z in zeilen:
            art = self.bezeichnung(z.get("energieverbrauchtypid") or z.get("identifier"))
            art = art or _text(z.get("bezeichnung"))
            if not art:
                continue
            einheit = self.bezeichnung(z.get("energieeinheittypid"))
            out.append(
                _ohne_leere(
                    {
                        "art": VERBRAUCHSARTEN.get(art, art),
                        "menge": _zahl(z.get("menge")),
                        "einheit": EINHEITEN.get(einheit, einheit),
                    }
                )
            )
        return out

    def sanierungen(self, zeilen: list[dict]) -> list[dict]:
        return [
            s
            for z in zeilen
            if (
                s := _ohne_leere(
                    {
                        "jahr": _jahr(z.get("sanierungsjahr")),
                        "kosten": _zahl(z.get("sanierungskosten")),
                        "waehrung": self.waehrung(z.get("waehrung")),
                        "beschreibung": _text(z.get("sanierungsbeschreibung")),
                    }
                )
            )
        ]

    def foerderungen(self, zeilen: list[dict]) -> list[dict]:
        return [
            f
            for z in zeilen
            if (
                f := _ohne_leere(
                    {
                        "programm": _text(z.get("foerderprogramm")),
                        "jahr": _jahr(z.get("foerderjahr")),
                        "hoehe": _zahl(z.get("foerderhoehe")),
                        "waehrung": self.waehrung(z.get("waehrung")),
                    }
                )
            )
        ]

    def nutzer(self, zeilen: list[dict]) -> list[str]:
        namen = [
            self.name_der_org(z.get("organisationid")) or _text(z.get("nutzername")) for z in zeilen
        ]
        return list(dict.fromkeys(n for n in namen if n))

    def staette(self, z: dict, mit_listen: bool = True) -> dict:
        """Zeile der Tabelle sportstaette (oder Formulardaten mit denselben Namen) → Sportstätte
        ohne Anlagen. `mit_listen`: Räume, Energie, Kosten und Nutzer aus den Tabellen."""
        sid = z.get("id")
        eigner = self.name_der_org(z.get("eignerorgaid")) if z.get("eignerorgaid") else None
        betreiber = (
            self.name_der_org(z.get("betreiberorgaid")) if z.get("betreiberorgaid") else None
        )
        st = {
            "id": sid,
            "name": _text(z.get("bezeichnung")),
            "kategorie": self.kategorie(z.get("typid")),
            "adresse": self.adresse(z),
            "lage": self.lage(z),
            "entfernung_oepnv": _ganz(z.get("entfernungoepnv")),
            "oeffentlicher_zugang": _ja_nein(z.get("oeffentlich")),
            "schulsport": _ja_nein(z.get("schulsport")),
            "wlan": _ja_nein(z.get("wlan")),
            "zuschauerplaetze": _ganz(z.get("zuschauerplatzgesamt")),
            "betriebsstatus": self.bezeichnung(z.get("betriebsstatustypid")),
            "eigentuemer": eigner or _text(z.get("eignerbezeichnung")),
            "betreiber": betreiber or _text(z.get("betreiberbezeichnung")),
            "website": _url(z.get("url")),
            "wettkampfanlage": self.bezeichnung(z.get("wettkampfanlage")),
            "baujahr": _jahr(z.get("baujahr")),
            "letzte_sanierung": _jahr(z.get("letzteSanierung")),
            "fassadenmaterial": self.bezeichnung(z.get("fassadenmaterial")),
        }
        for rolle, spalte in (("eigentuemer", "eignertyp"), ("betreiber", "betreibertyp")):
            st[f"{rolle}_typ"] = self.org_typ(z.get(spalte))
        if mit_listen and sid in self.staetten:
            js = self.je_staette
            st |= {
                "funktionsraeume": self.funktionsraeume(js["funktionsraum"].get(sid, [])),
                "energietraeger": self.energietraeger(js["energietraeger"].get(sid, [])),
                "verbraeuche": self.verbraeuche(js["jahresverbrauch"].get(sid, [])),
                "sanierungen": self.sanierungen(self.kosten["sanierung"].get(sid, [])),
                "foerderungen": self.foerderungen(self.kosten["foerderung"].get(sid, [])),
                "nutzer": self.nutzer(js["sportstaettenutzer"].get(sid, [])),
                "sportarten": list(
                    dict.fromkeys(
                        s
                        for a in self.anlagen.get(sid, [])
                        for s in self.anlage_sportarten(self.sportarten.get(a["id"], []))[0]
                    )
                ),
            }
        return _ohne_leere(st)

    def anlage_sportarten(self, zeilen: list[dict]) -> tuple[list[str], list[str]]:
        """→ (Sportarten, davon wettkampfgeeignet)."""
        alle, wettkampf = [], []
        for z in zeilen:
            if z.get("state") == "DELETED":
                continue
            s = self.bezeichnung(z.get("sportartid")) or _text(z.get("bezeichnung"))
            if s and s not in alle:
                alle.append(s)
                if _ganz(z.get("wettkampfeignung")) == 1:
                    wettkampf.append(s)
        return alle, wettkampf

    def anlage(self, z: dict, sportarten: list[dict] | None = None) -> dict:
        """Zeile der Tabelle sportanlage (oder `model` aus dem Formular) → Sportanlage."""
        roh = self.bezeichnung(z.get("typid")) or _text(z.get("typ")) or "sonstige Sportanlage"
        typ = anlagen_typen.typ(roh) or "sonstige Sportanlage"
        a: dict = {"typ": typ}
        name = _text(z.get("bezeichnung"))
        if name and name not in (roh, typ):
            a["bezeichnung"] = name
        a["betriebsstatus"] = self.bezeichnung(z.get("betriebsstatustypid"))
        a["baujahr"] = _jahr(z.get("baujahr"))
        a["letzte_sanierung"] = _jahr(z.get("letzteSanierung"))
        alle, wettkampf = self.anlage_sportarten(
            sportarten if sportarten is not None else self.sportarten.get(z.get("id"), [])
        )
        a["sportarten"], a["wettkampf"] = alle, wettkampf
        for feld, spalten in ANLAGE_ZAHLEN.items():
            a[feld] = next((w for s in spalten if (w := _zahl(z.get(s)))), None)
        wasser = _zahl(z.get("wasserflaeche"))
        a["wasserflaeche"] = wasser or None  # 0 ist im Altsystem die Vorgabe
        for feld, spalten in ANLAGE_GANZZAHLEN.items():
            a[feld] = next((w for s in spalten if (w := _ganz(z.get(s)))), None)  # 0: Vorgabe
        for feld, spalte in ANLAGE_JA_NEIN.items():
            a[feld] = _ja_nein(z.get(spalte))
        belag = self.bezeichnung(z.get("bodenbelagtypid"))
        a["bodenbelag"] = BODENBELAEGE.get(belag, belag) if belag else None
        a["felder_je_belag"] = {
            n: w for k, n in FELDER_JE_BELAG.items() if (w := _ganz(z.get(f"bodenbelag_anz_{k}")))
        }
        a["felder_je_sportart"] = {
            n: w for k, n in FELDER_JE_SPORTART.items() if (w := _ganz(z.get(f"anz_feld_{k}")))
        }
        a["kleinfelder_je_sportart"] = {
            n: w for k, n in KLEINFELDER.items() if (w := _ganz(z.get(f"anz_kleinfeld_{k}")))
        }
        a["leuchtmittel"] = self.bezeichnung(z.get("leuchtmitteltypid"))
        a["lux"] = _ganz(self.bezeichnung(z.get("luxwerttypid")))
        a["baederleben_id"] = _text(z.get("baederlebenid"))
        a["altersempfehlung"] = _text(z.get("altersempfehlung"))
        a["waehrung"] = self.waehrung(z.get("waehrung")) if a.get("baukosten") else None
        if z.get("id"):
            a["sanierungen"] = self.sanierungen(self.kosten["sanierung"].get(z["id"], []))
            a["foerderungen"] = self.foerderungen(self.kosten["foerderung"].get(z["id"], []))
        return _ohne_leere(a)

    def mit_anlagen(self, sid: str, ordner: Path | None) -> dict:
        """Sportstätte mit Anlagen. Neue Sportstätten (ohne `ordner`) und solche, die schon aus
        dem Altsystem stammen, behalten die alten IDs der Anlagen; bei den übrigen vorhandenen
        bekommen sie die ID wie beim Einlesen des Atlas-Exports (n-te Anlage eines Typs)."""
        alte_ids = {a["id"] for a in self.anlagen.get(sid, [])}
        vorhanden = ordner is not None and not alte_ids & {p.stem for p in ordner.glob("*.json")}
        st = self.staette(self.staetten[sid])
        st["anlagen"] = []
        nr: Counter = Counter()
        for z in self.anlagen.get(sid, []):
            a = self.anlage(z)
            nr[a["typ"]] += 1
            a["id"] = anlage_id(sid, a["typ"], nr[a["typ"]]) if vorhanden else z["id"]
            self.neue_anlage_ids[z["id"]] = a["id"]
            st["anlagen"].append(a)
        return st


# --- Vorschläge (public_submissions) ----------------------------------------------------


def _mit_status(alt: list, eintraege: list[dict], aus, schluessel) -> list:
    """Liste nach dem Formular: DELETED entfernt, ADDED/CHANGED ersetzt bzw. dazu."""
    out = list(alt)
    for e in eintraege or []:
        status = e.get("state")
        if status not in ("ADDED", "CHANGED", "DELETED"):
            continue
        neu = aus([e])
        k = schluessel(neu[0]) if neu else None
        out = [x for x in out if schluessel(x) != k] if k is not None else out
        if status != "DELETED":
            out += neu
    return out


def vorschlaege(alt: Altsystem, ordner: Path, komplexe: set[str]) -> tuple[list[dict], Counter]:
    """Offene Vorschläge → Zeilen eines LimeSurvey-Exports („Antwort ID“, „Vorschlag“)."""
    pfad = ordner / "public_submissions.csv"
    if not pfad.exists():
        return [], Counter()
    text = pfad.read_bytes().decode("utf-8-sig")
    zeilen, n = [], Counter()

    def antwort(aid: str, v: dict) -> None:
        zeilen.append(
            {"Antwort ID": aid, "Vorschlag": json.dumps({"version": 1, **v}, ensure_ascii=False)}
        )
        n[v["art"]] += 1

    for z in csv.DictReader(io.StringIO(text)):
        if z.get("status") != "pending":
            continue
        n["offen"] += 1
        form = json.loads(z.get("form_data") or "{}")
        sid = _text(z.get("sportstaette_id"))
        sid = sid if sid not in (None, "NULL") else None
        aid = f"alt-{z['id']}"
        if sid and sid not in alt.staetten:
            n["Sportstätte fehlt"] += 1
            continue
        vorher = alt.staette(alt.staetten[sid]) if sid else {}
        gesetzt = {k: v for k, v in form.items() if v is not None}  # null: nicht geändert
        neu = alt.staette({**(alt.staetten.get(sid) or {}), **gesetzt, "id": sid}, mit_listen=False)
        if "adresse" in form:  # das Formular schickt nur die geänderten Teile
            neu["adresse"] = {**(vorher.get("adresse") or {}), **(neu.get("adresse") or {})}
        listen = {
            "funktionsraeume": (form.get("funktionaleRaeume") or [])
            + (form.get("sonstigeRaeume") or []),
            "energietraeger": form.get("energietraeger"),
            "verbraeuche": form.get("jahresverbrauch"),
            "nutzer": form.get("sportstaettenutzer"),
            "sanierungen": [
                s for s in form.get("sanierung") or [] if str(s.get("entity_type")) == "1"
            ],
            "foerderungen": [
                s for s in form.get("foerderung") or [] if str(s.get("entity_type")) == "1"
            ],
        }
        if listen["funktionsraeume"]:
            raeume = Counter(vorher.get("funktionsraeume") or {})
            for r in listen["funktionsraeume"]:
                for name, anzahl in alt.funktionsraeume(
                    [{**r, "anzahl": r.get("anzahl") or 1}]
                ).items():
                    if r.get("state") == "DELETED":
                        raeume.pop(name, None)
                    elif r.get("state") in ("ADDED", "CHANGED"):
                        raeume[name] = (
                            anzahl if r.get("state") == "CHANGED" else raeume[name] + anzahl
                        )
            neu["funktionsraeume"] = dict(raeume)
        for feld, aus, schluessel in (
            ("energietraeger", alt.energietraeger, lambda x: (x.get("bereich"), x.get("art"))),
            ("verbraeuche", alt.verbraeuche, lambda x: x.get("art")),
            ("nutzer", alt.nutzer, lambda x: x),
            ("sanierungen", alt.sanierungen, lambda x: (x.get("jahr"), x.get("beschreibung"))),
            ("foerderungen", alt.foerderungen, lambda x: (x.get("jahr"), x.get("programm"))),
        ):
            if listen[feld]:
                neu[feld] = _mit_status(vorher.get(feld) or [], listen[feld], aus, schluessel)
        for k in form.get("sportkomplex") or []:
            if k.get("state") == "SELECTED" and k.get("id") in komplexe:
                neu["sportkomplex"] = k["id"]
        neu = _ohne_leere(neu)
        for rolle in ("eigentuemer", "betreiber"):  # eine Art ohne Namen lässt das Modell nicht zu
            if not (neu.get(rolle) or vorher.get(rolle)):
                neu.pop(f"{rolle}_typ", None)

        anlagen_form = form.get("sportanlage") or []
        kosten_anlage = defaultdict(lambda: defaultdict(list))  # Anlage → sanierung/foerderung
        for art in ("sanierung", "foerderung"):
            for s in form.get(art) or []:
                if str(s.get("entity_type")) == "2" and s.get("state") != "DELETED":
                    kosten_anlage[s.get("entity_id")][art].append(s)

        def anlage_aus(e: dict, kosten_anlage=kosten_anlage) -> dict:
            m = e.get("model") or {}
            a = alt.anlage({**m, "id": None}, e.get("sportanlagesportart") or [])
            if k := kosten_anlage.get(m.get("id")):
                a["sanierungen"] = alt.sanierungen(k["sanierung"])
                a["foerderungen"] = alt.foerderungen(k["foerderung"])
            return _ohne_leere(a)

        if not sid:  # neue Sportstätte
            if not neu.get("name") or not neu.get("lage"):
                n["neu ohne Name oder Lage"] += 1
            antwort(
                aid,
                {
                    "art": "neu",
                    "sportstaette": {k: v for k, v in neu.items() if k != "id"},
                    "anlagen": [anlage_aus(e) for e in anlagen_form if e.get("state") != "DELETED"],
                },
            )
            neue_sid = str(uuid.uuid5(_NAMENSRAUM, f"limesurvey/{aid}"))
        else:
            neue_sid = sid
            geaendert = []
            for k, w in neu.items():
                if k == "id":
                    continue
                if k == "adresse":
                    geaendert += [
                        f"adresse.{x}"
                        for x, y in w.items()
                        if (vorher.get("adresse") or {}).get(x) != y
                    ]
                elif vorher.get(k) != w:
                    geaendert.append(k)
            if geaendert:
                antwort(
                    aid,
                    {
                        "art": "aenderung",
                        "sportstaette_id": sid,
                        "sportstaette": {k: v for k, v in {**vorher, **neu}.items() if k != "id"},
                        "geaendert": geaendert,
                    },
                )
            liste, weg = [], []
            for e in anlagen_form:
                m = e.get("model") or {}
                eigene = alt.neue_anlage_ids.get(m.get("id") or "")
                if e.get("state") == "ADDED":
                    liste.append(anlage_aus(e))
                elif e.get("state") == "CHANGED" and eigene:
                    bisher = next((x for x in alt.anlagen.get(sid, []) if x["id"] == m["id"]), {})
                    a = {**alt.anlage(bisher), **anlage_aus(e)}
                    liste.append({**a, "id": eigene})
                elif e.get("state") == "DELETED" and eigene:
                    weg.append(eigene)
                elif e.get("state") in ("CHANGED", "DELETED"):
                    n["Anlage fehlt"] += 1
            if liste or weg:
                antwort(
                    f"{aid}-anlagen",
                    {
                        "art": "anlagen",
                        "sportstaette_id": sid,
                        "anlagen": liste,
                        "entfernte_anlagen": weg,
                    },
                )
        for i, s in enumerate(form.get("leistungssportStuetzpunkt") or []):
            if s.get("state") != "ADDED":
                continue
            antwort(
                f"{aid}-stuetzpunkt-{i + 1}",
                {
                    "art": "stuetzpunkt",
                    "stuetzpunkt": _ohne_leere(
                        {
                            "name": _text(s.get("bezeichnung")) or _text(s.get("label")),
                            "art": STUETZPUNKTE.get(_text(s.get("label")) or ""),
                            "sportstaetten": [neue_sid],
                        }
                    ),
                },
            )
    return zeilen, n


def schreibe_export(zeilen: list[dict], pfad: Path) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with pfad.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Antwort ID", "Vorschlag"])
        w.writeheader()
        w.writerows(zeilen)


# --- alles zusammen ---------------------------------------------------------------------


def importiere(
    ordner: Path, daten: Path, kreis_von, vorschlaege_csv: Path, lage_aus=atlas.lage
) -> list[str]:
    """Altsystem → daten/ und den Export der Vorschläge. Liefert die Zeilen des Berichts."""
    alt = Altsystem(ordner, lage_aus)
    bericht: list[str] = []

    # Organisationen
    orgs = alt.benoetigte_organisationen()
    umbenannt = alt.ordne_kommunen_zu(orgs, lies_organisationen(daten))
    e = schreibe_organisationen(orgs, daten, "ergaenzen")
    alt.org_name = {o["id"]: o["name"] for o in orgs}
    for o in lies_organisationen(daten):  # vorhandene behalten ihren Namen
        alt.org_name.setdefault(o["id"], o["name"])
    bericht.append(
        f"Organisationen: {len(orgs)} übernommen ({e.neu} neu, {e.aktualisiert} ergänzt, "
        f"{e.unveraendert} unverändert, {umbenannt} Kommunen mit amtlichem Namen), "
        f"{len(alt.organisationen) - len(orgs)} ohne LSB-Nummer und ohne Verweis weggelassen"
    )

    # Sportstätten
    wo = {p.name: (o.name, p.parent.name, p) for o in _laender(daten) for p in _staetten_dirs(o)}
    gruppen: dict[tuple[str, str], list[dict]] = defaultdict(list)  # (Land, Land unter outside)
    for sid, z in alt.staetten.items():
        st = alt.mit_anlagen(sid, wo[sid][2] if sid in wo else None)
        if sid in wo:  # bleibt, wo sie ist
            land, unter, _ = wo[sid]
            gruppen[(land, unter if land == OUTSIDE else "")].append(st)
            continue
        drin = st.get("lage") and kreis_von(st["lage"]["lon"], st["lage"]["lat"]) != OHNE_KREIS
        ags = alt.ags(z)
        if drin or ags.startswith("07") or not st.get("lage"):
            gruppen[("RP", "")].append(st)
        else:
            gruppen[(OUTSIDE, LAENDER.get(ags[:2], UNBEKANNT))].append(st)
    for (land, unter), liste in sorted(gruppen.items()):
        kv = (lambda lon, lat, u=unter: u) if land == OUTSIDE else kreis_von
        e = schreibe_bestand(liste, daten, land, kv, modus="ergaenzen")
        bericht.append(
            f"Sportstätten {land}{'/' + unter if unter else ''}: {len(liste)} ({e.neu} neu, {e.aktualisiert} ergänzt, "
            f"{e.unveraendert} unverändert, {e.ohne_lage} ohne Lage übersprungen; "
            f"Anlagen {e.anlagen_neu} neu, {e.anlagen_geaendert} ergänzt)"
        )

    # Sportkomplexe: nur mit mindestens zwei Sportstätten
    bestand = {d["id"]: d for d in lies_bestand(daten)}
    mitglieder: dict[str, list[str]] = defaultdict(list)
    for sid, z in alt.staetten.items():
        if z.get("sportkomplexid") in alt.komplexe and sid in bestand:
            mitglieder[z["sportkomplexid"]].append(sid)
    komplexe = []
    for kid, ids in mitglieder.items():
        if len(ids) < 2:
            continue
        k = alt.komplexe[kid]
        frei = [s for s in ids if bestand[s].get("sportkomplex") in (None, "", kid)]
        komplexe.append(
            _ohne_leere(
                {
                    "id": kid,
                    "name": _text(k.get("bezeichnung")),
                    "adresse": alt.adresse(k),
                    "sportstaetten": frei,
                }
            )
        )
    e = schreibe_sportkomplexe(komplexe, daten, kreis_von, modus="ergaenzen")
    bericht.append(
        f"Sportkomplexe: {len(komplexe)} mit mindestens zwei Sportstätten ({e.neu} neu), "
        f"{e.zugeordnet} Sportstätten zugeordnet; {len(alt.komplexe) - len(komplexe)} weggelassen"
    )

    # Stützpunkte, wie sie in der Datenbank stehen
    sp = [
        _ohne_leere(
            {
                "id": z["id"],
                "name": _text(z.get("bezeichnung")),
                "art": STUETZPUNKTE.get(alt.bezeichnung(z.get("typid")) or ""),
                "sportstaetten": [z["sportstaetteid"]] if z.get("sportstaetteid") else [],
            }
        )
        for z in alt.stuetzpunkte
    ]
    e = schreibe_stuetzpunkte(sp, daten, modus="ergaenzen")
    bericht.append(
        f"Stützpunkte: {len(sp)} ({e.neu} neu, {e.ohne_sportstaette} Verweise auf unbekannte "
        "Sportstätten)"
    )

    # offene Vorschläge
    zeilen, n = vorschlaege(alt, ordner, {k["id"] for k in komplexe})
    schreibe_export(zeilen, vorschlaege_csv)
    arten = ", ".join(f"{k}: {v}" for k, v in sorted(n.items()) if k != "offen")
    bericht.append(
        f"Vorschläge: {n['offen']} offen → {len(zeilen)} Antworten in {vorschlaege_csv} ({arten})"
    )
    return bericht


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("ordner", type=Path, help="Ordner mit dem Export des Altsystems")
    p.add_argument("--daten", type=Path, default=Path("daten"))
    p.add_argument("--probe", action="store_true", help="in einer Kopie von daten/, nur zählen")
    args = p.parse_args(argv)

    from sportstaettenatlas import gebiete as gb
    from sportstaettenatlas.hilfen import ERGEBNISSE

    kreis_von = kreis_ordner(gb.lade("rp"))
    ziel = ERGEBNISSE / "altsystem_vorschlaege.csv"
    if args.probe:
        with tempfile.TemporaryDirectory() as tmp:
            kopie = Path(tmp) / "daten"
            shutil.copytree(args.daten, kopie)
            bericht = importiere(args.ordner, kopie, kreis_von, Path(tmp) / ziel.name)
        print("Probe – daten/ bleibt unverändert:")
    else:
        bericht = importiere(args.ordner, args.daten, kreis_von, ziel)
    print("\n".join(f"  {z}" for z in bericht))
    if not args.probe:
        print(
            "Weiter: uv run sportstaettenatlas pruefen; Vorschläge mit "
            f"uv run sportstaettenatlas vorschlaege {ziel} --probe ansehen."
        )


if __name__ == "__main__":
    sys.exit(main())
