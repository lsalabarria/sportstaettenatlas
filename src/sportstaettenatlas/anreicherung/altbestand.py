"""Altbestand: Daten des bisherigen Sportstättenatlas RLP.

Zwei CSV-Formate werden gelesen:

1. Import-Format: einheitliche Spalten sportkomplex_*, sportstaette_* (mit
   utm32nrechts/utm32nhoch = EPSG:25832) und sportanlage_*; je Zeile eine Sportanlage.
   Die IDs gelten nur innerhalb einer Datei. Mehrere Dateien (ein Ordner) werden
   zusammengeführt; kommt eine Sportstätte mehrfach vor, gewinnt die jüngste Datei
   (Datum im Dateinamen).

Achtung Begriffe: Das Altsystem hat Sportkomplex → Sportstätte → Sportanlage. Eine
Altsystem-"Sportstätte" (z. B. "Sportplatz Musterdorf" mit Großspielfeld und
Laufbahn) entspricht in etwa unserer Sportstätte.

2. Export aus dem laufenden Atlas (eine Zeile je Sportstätte, Spalten ID, Name, …,
   Sportanlagen, Latitude, Longitude). Achtung: Unter "Latitude"/"Longitude" stehen dort
   UTM-Koordinaten (Hochwert/Rechtswert, EPSG:25832); echte Grad-Werte werden erkannt
   und umgerechnet.

Die Dateien enthalten Kontaktdaten und gehören nicht ins Repository.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pandas as pd

QUELLE = "Sportstättenatlas RLP"

PFLICHT = {"sportstaette_id", "sportstaette_bezeichnung", "utm32nrechts", "utm32nhoch"}

# grobe Zuordnung Altsystem-Sportstättentyp → unsere Typgruppe (für den Typvergleich)
TYP_ZU_GRUPPE = {
    "sportplatz": "spielfeld",
    "sporthalle": "halle",
    "schwimmsportstätte": "becken",
    "tennissportstätte": "spielfeld",
    "reitsportstätte": "spezial",
    "schießsportstätte": "spezial",
    "roll- und skatesportstätte": "spezial",
    "öffentlicher sport- und bewegungsraum": "sportgelegenheit",
    "golfsportstätte": "spezial",
    "eissportstätte": "eis",
    "leichtathletiksportstätte": "leichtathletik",
    "flugsportstätte": "spezial",
    "radsportstätte": "spezial",
    "wassersportstätte": "spezial",
    "sportgelegenheiten in sonstigen gebäuden": "sportgelegenheit",
    "wintersportstätte": "spezial",
    "klettersportstätte": "spezial",
    "motorsportstätte": "spezial",
    "segelsportstätte": "spezial",
    # Fitnessstudios führt ALKIS nicht als Sportobjekt → bewusst ohne Gruppe
}


def _text(roh: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return roh.decode(enc)
        except UnicodeDecodeError:
            continue
    return roh.decode("utf-8", errors="replace")


def _zeilen(text: str) -> list[dict]:
    try:
        dialekt = csv.Sniffer().sniff(text[:5000], delimiters=";,")
    except csv.Error:
        dialekt = csv.excel
    return list(csv.DictReader(io.StringIO(text), dialect=dialekt))


def dateien(pfad: Path) -> list[tuple[str, bytes]]:
    """(Dateiname, Inhalt) der zu lesenden CSVs: eine CSV-Datei oder alle CSVs eines Ordners."""
    pfad = Path(pfad).expanduser()
    if not pfad.exists():
        raise FileNotFoundError(
            f"{pfad} nicht gefunden (Pfad prüfen, z. B. mit `ls {pfad.parent}`)"
        )
    if pfad.is_file() and pfad.suffix.lower() == ".csv":
        return [(pfad.name, pfad.read_bytes())]
    if pfad.is_dir():
        return [(p.name, p.read_bytes()) for p in sorted(pfad.glob("*.csv")) if p.is_file()]
    raise FileNotFoundError(f"{pfad} ist weder eine CSV-Datei noch ein Ordner mit CSV-Dateien")


def _zahl(v: str | None) -> float | None:
    if not v or not str(v).strip():
        return None
    try:
        return float(str(v).strip().replace(",", "."))
    except ValueError:
        return None


def _adresse(z: dict, praefix: str) -> str | None:
    g = lambda k: (z.get(f"{praefix}_{k}") or "").strip()
    strasse = " ".join(x for x in (g("strasse"), g("hn")) if x)
    ort = " ".join(x for x in (g("plz"), g("ort")) if x)
    return ", ".join(x for x in (strasse, ort) if x) or None


def _ags(v: str | None) -> str | None:
    s = (v or "").strip().split(".")[0]
    return s.zfill(8) if s.isdigit() else (s or None)


def _datum(name: str) -> str:
    if m := re.search(r"(\d{4}-\d{2}-\d{2})", name):
        return m.group(1)
    if m := re.search(r"(?<!\d)(\d{2})(\d{2})(20\d{2})(?!\d)", name):  # TTMMJJJJ
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return ""


EXPORT_PFLICHT = {"ID", "Name", "Sportstättenkategorie", "Latitude", "Longitude"}
# Export-Spalte → unsere Spalte (Zusatzangaben, die im Import-Format fehlen)
EXPORT_FELDER = {
    "ID": "alt_atlas_id",
    "Schulsport": "alt_schulsport",
    "Öffentlicher Zugang": "alt_oeffentlich",
    "Zuschauerplätze Gesamt": "alt_zuschauer",
    "Betriebsstatus": "alt_betriebsstatus",
    "Name des Eigentümers": "alt_eigentuemer",
    "Name des Betreibers": "alt_betreiber",
    "E-Mail": "alt_email",
    "Webseite": "alt_website",
    "Sportarten": "alt_sportarten",
}


def _utm(a: float, b: float) -> tuple[float, float]:
    """(x, y) in EPSG:25832 aus den Export-Spalten Latitude=a, Longitude=b."""
    if a > 1e5 and b > 1e5:  # UTM, nur falsch beschriftet: a = Hochwert, b = Rechtswert
        return (b, a) if a > b else (a, b)
    from pyproj import Transformer  # echte Grad-Werte

    return Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True).transform(b, a)


def _aus_export(name: str, zeilen: list[dict]) -> list[dict]:
    out = []
    for z in zeilen:
        a, b = _zahl(z.get("Latitude")), _zahl(z.get("Longitude"))
        if a is None or b is None:
            continue
        x, y = _utm(a, b)

        def g(k: str, z: dict = z) -> str:
            return (z.get(k) or "").strip()

        strasse = " ".join(v for v in (g("Straße"), g("Hausnummer")) if v)
        ort = " ".join(v for v in (g("PLZ"), g("Stadt")) if v)
        st = {
            "alt_name": g("Name") or None,
            "alt_typ": g("Sportstättenkategorie") or None,
            "alt_komplex": None,
            "alt_adresse": ", ".join(v for v in (strasse, ort) if v) or None,
            "alt_ags": None,
            "alt_datei": name,
            "alt_stand": _datum(name),
            "x": x,
            "y": y,
            # Liste "A, B, C"; Klammern wie "Großspielfeld (ab 5.000 m²)" bleiben ganz
            "_anlagen": [
                t.strip() for t in re.split(r",\s*(?![^()]*\))", g("Sportanlagen")) if t.strip()
            ],
        }
        for spalte, ziel in EXPORT_FELDER.items():
            st[ziel] = g(spalte) or None
        out.append(st)
    return out


def lade_tabelle(pfad: Path, land_ags: str = "07") -> pd.DataFrame:
    """Eine Zeile je Altsystem-Sportstätte (über alle Import-Dateien dedupliziert)."""
    staetten: dict[tuple, dict] = {}
    for name, roh in dateien(pfad):
        zeilen = _zeilen(_text(roh))
        if zeilen and EXPORT_PFLICHT <= set(zeilen[0]):
            for st in _aus_export(name, zeilen):  # Export: eine Zeile je Sportstätte, ID eindeutig
                staetten[("id", st["alt_atlas_id"])] = st
            continue
        if not zeilen or not PFLICHT <= set(zeilen[0]):
            continue
        je_id: dict[str, dict] = {}
        for z in zeilen:
            x, y = _zahl(z.get("utm32nrechts")), _zahl(z.get("utm32nhoch"))
            if x is None or y is None:
                continue
            sid = (z.get("sportstaette_id") or "").strip()
            st = je_id.setdefault(
                sid,
                {
                    "alt_name": (z.get("sportstaette_bezeichnung") or "").strip() or None,
                    "alt_typ": (z.get("sportstaette_typ_text") or "").strip() or None,
                    "alt_komplex": (z.get("sportkomplex_bezeichnung") or "").strip() or None,
                    "alt_adresse": _adresse(z, "sportstaette") or _adresse(z, "sportkomplex"),
                    "alt_ags": _ags(z.get("AGS")),
                    "alt_datei": name,
                    "alt_stand": _datum(name),
                    "x": x,
                    "y": y,
                    "_anlagen": [],
                },
            )
            if typ := (z.get("sportanlage_typ_text") or "").strip():
                st["_anlagen"].append(typ)
        for st in je_id.values():
            # gleiche Stätte in mehreren Import-Runden: jüngste Datei gewinnt
            schluessel = (round(st["x"]), round(st["y"]), (st["alt_name"] or "").casefold())
            alt = staetten.get(schluessel)
            if alt is None or st["alt_stand"] >= alt["alt_stand"]:
                staetten[schluessel] = st

    df = pd.DataFrame(list(staetten.values()))
    if not df.empty and "alt_ags" in df:
        # Der Bäder-Import enthält auch NRW; nur Rheinland-Pfalz (AGS 07…) behalten
        df = df[df["alt_ags"].isna() | df["alt_ags"].str.startswith(land_ags)]
    if df.empty:
        return pd.DataFrame(columns=["alt_id", "alt_name", "alt_typ", "x", "y"])
    df["alt_anzahl_anlagen"] = df["_anlagen"].map(len)
    df["alt_anlagentypen"] = df["_anlagen"].map(
        lambda a: (
            "; ".join(
                f"{n}× {t}" if n > 1 else t
                for t, n in pd.Series(a, dtype=object).value_counts().items()
            )
            or None
        )
    )
    df["alt_typgruppe"] = df["alt_typ"].map(
        lambda t: TYP_ZU_GRUPPE.get(str(t).strip().lower()) if t else None  # lower: ß bleibt
    )
    df = df.drop(columns="_anlagen").sort_values(["alt_stand", "alt_datei"]).reset_index(drop=True)
    df.insert(0, "alt_id", [f"ALT{i + 1:06d}" for i in range(len(df))])
    return df


def lade(pfad: Path, crs: str = "EPSG:25832", land_ags: str = "07"):
    """Altbestand als GeoDataFrame (Punkte in UTM32)."""
    import geopandas as gpd

    df = lade_tabelle(pfad, land_ags)
    return gpd.GeoDataFrame(
        df.drop(columns=["x", "y"]), geometry=gpd.points_from_xy(df["x"], df["y"]), crs=crs
    )


def abgleich(alt, staetten, anlagen, zuordnung, max_nah_m: float = 200) -> pd.DataFrame:
    """Bericht aus Sicht des Altbestands: Wo liegt jede Altsystem-Sportstätte in ALKIS?

    `zuordnung` ist das Ergebnis von je_objekt (welche unserer Sportstätten welches
    Altsystem-Objekt bekommen hat). Status:
    - zugeordnet           – einer ALKIS-Sportstätte zugeordnet
    - nah                  – nächste ALKIS-Sportstätte 100–200 m entfernt (Koordinate prüfen)
    - nicht in ALKIS       – im Umkreis von 200 m keine ALKIS-Sportstätte
    `typ_passt` vergleicht den Altsystem-Typ mit den Typgruppen der Anlagen vor Ort.
    """
    import geopandas as gpd

    bericht = alt.drop(columns="geometry").copy()
    punkte = alt.geometry.to_crs("EPSG:4326")
    bericht["lon"], bericht["lat"] = punkte.x.round(6).values, punkte.y.round(6).values
    # wer hat welches Objekt bekommen?
    hat = {}
    if "alt_id" in zuordnung:
        for sid, ids in zip(staetten["sportstaette_id"], zuordnung["alt_id"]):
            for i in str(ids).split(" | ") if isinstance(ids, str) else []:
                hat[i] = sid
    bericht["sportstaette_id"] = bericht["alt_id"].map(hat)

    naechste = (
        gpd.sjoin_nearest(
            alt[["alt_id", "geometry"]],
            staetten[["sportstaette_id", "geometry"]],
            how="left",
            max_distance=max_nah_m,
            distance_col="abstand_m",
        )
        .drop_duplicates("alt_id")
        .set_index("alt_id")
    )
    bericht["naechste_sportstaette_id"] = bericht["alt_id"].map(naechste["sportstaette_id"])
    bericht["abstand_m"] = bericht["alt_id"].map(naechste["abstand_m"]).round(1)
    bericht["status"] = "nicht in ALKIS"
    bericht.loc[bericht["naechste_sportstaette_id"].notna(), "status"] = "nah"
    bericht.loc[bericht["sportstaette_id"].notna(), "status"] = "zugeordnet"

    gruppen = anlagen.groupby("sportstaette_id")["typgruppe"].agg(lambda s: set(s.dropna()))
    ort = bericht["sportstaette_id"].fillna(bericht["naechste_sportstaette_id"])
    bericht["alkis_typgruppen"] = ort.map(
        lambda s: "; ".join(sorted(gruppen.get(s, set()))) if isinstance(s, str) else None
    )

    def passt(o, g):
        vor_ort = gruppen.get(o, set()) - {"unbestimmt"}  # Sammelbegriff sagt nichts
        if not isinstance(o, str) or not g or not vor_ort:
            return None
        return g in vor_ort

    bericht["typ_passt"] = [passt(o, g) for o, g in zip(ort, bericht["alt_typgruppe"])]
    spalten = [
        "alt_id",
        "status",
        "sportstaette_id",
        "naechste_sportstaette_id",
        "abstand_m",
        "typ_passt",
        "alt_typ",
        "alt_typgruppe",
        "alkis_typgruppen",
        "alt_name",
        "alt_komplex",
        "alt_adresse",
        "alt_anlagentypen",
        "alt_betriebsstatus",
        "alt_atlas_id",
        "alt_datei",
        "lon",
        "lat",
    ]
    return bericht[[c for c in spalten if c in bericht.columns]]
