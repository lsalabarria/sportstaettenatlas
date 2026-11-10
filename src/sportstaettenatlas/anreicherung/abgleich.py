"""Räumlicher Abgleich externer Objekte mit Sportstätten/Sportanlagen und Gesamtablauf."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import geopandas as gpd
    import pandas as pd

    from .http import Sitzung

log = logging.getLogger(__name__)


def _paare(kandidaten: gpd.GeoDataFrame, objekte: gpd.GeoDataFrame, max_m: float):
    """Alle Paare (Kandidat, Objekt) im Abstand <= max_m mit Abstand und Überlappungsgrad."""
    import geopandas as gpd

    links = gpd.GeoDataFrame(
        {"_k": kandidaten.index}, geometry=kandidaten.geometry.buffer(max_m), crs=kandidaten.crs
    )
    rechts = objekte.reset_index(drop=True)
    p = gpd.sjoin(links, rechts[["geometry"]], how="inner", predicate="intersects")
    if p.empty:
        return p
    p = p.rename(columns={"index_right": "_o"})[["_k", "_o"]].reset_index(drop=True)
    gk = gpd.GeoSeries(kandidaten.geometry.loc[p["_k"]].to_numpy(), crs=kandidaten.crs)
    go = gpd.GeoSeries(rechts.geometry.iloc[p["_o"]].to_numpy(), crs=kandidaten.crs)
    p["abstand_m"] = gk.distance(go).round(1).to_numpy()
    schnitt = gk.intersection(go).area.to_numpy()
    fk, fo = gk.area.to_numpy(), go.area.to_numpy()
    p["ueberlappung"] = [
        s / min(a, b) if min(a, b) > 0 else 0.0 for s, a, b in zip(schnitt, fk, fo)
    ]
    iou = [s / (a + b - s) if (a + b - s) > 0 else 0.0 for s, a, b in zip(schnitt, fk, fo)]
    # Überlappende Paare schlagen benachbarte immer; bei gleicher Überlappung
    # gewinnt die ähnlichere Form (IoU), z. B. Laufbahn-Fläche vor Teilspielfeld.
    p["score"] = [
        1 + u + 0.5 * j if d == 0 else 1 / (1 + d)
        for u, j, d in zip(p["ueberlappung"], iou, p["abstand_m"])
    ]
    return p


def je_objekt(
    kandidaten: gpd.GeoDataFrame,
    objekte: gpd.GeoDataFrame,
    spalten: list[str],
    praefix: str,
    max_m: float = 250,
) -> pd.DataFrame:
    """Jedes Objekt (z. B. Atlas-Punkt) genau einem Kandidaten zuordnen.

    Bevorzugt Kandidaten, die das Objekt enthalten; bei Punkten in einer großen
    Sportanlage gewinnt die Anlage. Mehrere Objekte je Kandidat werden verkettet.
    """
    import pandas as pd

    leer = pd.DataFrame(index=kandidaten.index)
    if kandidaten.empty or objekte.empty:
        return leer
    objekte = objekte.to_crs(kandidaten.crs).reset_index(drop=True)
    p = _paare(kandidaten, objekte, max_m)
    if p.empty:
        return leer
    beste = p.sort_values("score", ascending=False).drop_duplicates("_o")
    zeilen = objekte.iloc[beste["_o"].to_numpy()][spalten].copy()
    zeilen["_k"] = beste["_k"].to_numpy()
    zeilen[f"{praefix}abstand_m"] = beste["abstand_m"].to_numpy()

    def verketten(s):
        w = [str(v) for v in s.dropna() if str(v) != ""]
        return " | ".join(dict.fromkeys(w)) if w else None

    return zeilen.groupby("_k").agg(verketten).reindex(kandidaten.index)


def nachbarn_mitbestaetigen(
    kandidaten: gpd.GeoDataFrame,
    objekte: gpd.GeoDataFrame,
    zuordnung: pd.DataFrame,
    spalten: list[str],
    praefix: str,
    max_luecke_m: float = 20,  # wie CLUSTER_ABSTAND_M beim Bauen der Sportstätten
    max_abstand_m: float = 250,
) -> pd.DataFrame:
    """Ein Objekt bestätigt auch die angrenzenden Flächen seiner Sportstätte.

    ALKIS teilt einen Standort oft in mehrere Flächen (z. B. Tennishalle und, durch
    einen Weg getrennt, die Plätze als eigene Nutzungsflächen). Der Atlas-Punkt liegt nur in einer davon.
    Flächen, die an die zugeordnete Fläche grenzen (Lücke ≤ `max_luecke_m`, auch über
    mehrere Flächen hinweg) und selbst kein Objekt haben, bekommen dasselbe Objekt –
    sofern sie höchstens `max_abstand_m` vom Objekt entfernt sind. Herkunft steht in
    `<praefix>bezug` ("Nachbarfläche von ST…").
    """
    import geopandas as gpd
    import pandas as pd

    id_spalte = f"{praefix}id"
    if zuordnung.empty or id_spalte not in zuordnung:
        return zuordnung
    erg = zuordnung.copy()
    erg[f"{praefix}bezug"] = None
    belegt = erg[id_spalte].notna()
    if not belegt.any():
        return erg
    puffer = kandidaten.geometry.buffer(max_luecke_m / 2)
    paare = gpd.sjoin(
        gpd.GeoDataFrame(geometry=puffer, crs=kandidaten.crs),
        gpd.GeoDataFrame(geometry=puffer, crs=kandidaten.crs),
        predicate="intersects",
    )
    nachbarn: dict = {}
    for a, b in zip(paare.index, paare["index_right"]):
        if a != b:
            nachbarn.setdefault(a, set()).add(b)
    objekt_geo = objekte.to_crs(kandidaten.crs).set_index(id_spalte).geometry
    for k in erg.index[belegt]:
        ids = str(erg.at[k, id_spalte]).split(" | ")
        punkte = objekt_geo[objekt_geo.index.isin(ids)]
        if punkte.empty:
            continue
        sid = kandidaten.at[k, "sportstaette_id"] if "sportstaette_id" in kandidaten else k
        gesehen, offen = {k}, [k]
        while offen:  # angrenzende Flächen, auch über Ketten hinweg
            for n in nachbarn.get(offen.pop(), ()):
                if n in gesehen:
                    continue
                gesehen.add(n)
                if punkte.distance(kandidaten.geometry.loc[n]).min() > max_abstand_m:
                    continue
                if not pd.isna(erg.at[n, id_spalte]):
                    continue  # hat eigenes Objekt: nicht überschreiben, nicht weiter
                offen.append(n)
                for c in spalten + [f"{praefix}abstand_m"]:
                    if c in erg:
                        erg.at[n, c] = erg.at[k, c]
                erg.at[n, f"{praefix}bezug"] = f"Nachbarfläche von {sid}"
    return erg


# ---------------------------------------------------------------------------


@dataclass
class Bericht:
    zeilen: list[str] = field(default_factory=list)
    lizenzen: list[str] = field(default_factory=list)
    abgleich_altbestand: object = None  # DataFrame mit dem Abgleich Atlas ↔ ALKIS

    def __call__(self, text: str) -> None:
        log.info(text)
        self.zeilen.append(text)


def anreichern(
    staetten: gpd.GeoDataFrame,
    anlagen: gpd.GeoDataFrame,
    sitzung: Sitzung,
    altbestand: Path,
    alkis_quelle=None,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, Bericht]:
    """Gleicht die ALKIS-Sportstätten mit dem bisherigen Sportstättenatlas ab,
    übernimmt dessen Angaben und setzt Herkunft + Verifikation."""
    from shapely.geometry import box

    from . import altbestand as alt_modul
    from .verifikation import FELDER_ANLAGE, FELDER_STAETTE, verifiziere, zusammenfuehren

    bericht = Bericht()
    st, an = staetten.copy(), anlagen.copy()

    _status(f"{alt_modul.QUELLE}: lese {altbestand.name} …")
    ab = alt_modul.lade(altbestand, crs=st.crs)
    # nur Atlas-Einträge im bearbeiteten Gebiet (sonst wären bei einem Kreis alle
    # übrigen Einträge des Landes "nicht in ALKIS" und würden nachgeschlagen)
    x0, y0, x1, y1 = st.total_bounds
    rand = 500
    im_gebiet = ab.geometry.within(box(x0 - rand, y0 - rand, x1 + rand, y1 + rand))
    if not im_gebiet.all():
        _status(f"{alt_modul.QUELLE}: {int(im_gebiet.sum())} von {len(ab)} im Gebiet")
        ab = ab[im_gebiet.to_numpy()].copy()

    spalten = [c for c in ab.columns if c.startswith("alt_")]
    zuordnung = je_objekt(st, ab, spalten, "alt_", max_m=100)
    direkt = zuordnung.copy()  # Bericht: nur echte Treffer, keine Nachbarflächen
    zuordnung = nachbarn_mitbestaetigen(st, ab, zuordnung, spalten, "alt_")
    st = st.join(zuordnung)
    bericht.abgleich_altbestand = alt_modul.abgleich(ab, st, an, direkt)
    if alkis_quelle is not None:
        from . import vor_ort

        bericht.abgleich_altbestand = vor_ort.ergaenze(
            bericht.abgleich_altbestand, ab, sitzung, alkis_quelle
        )
    z = bericht.abgleich_altbestand["status"].value_counts().to_dict()
    bericht(
        f"{alt_modul.QUELLE}: {len(ab)} Sportstätten im Altbestand; "
        + ", ".join(f"{k}: {v}" for k, v in z.items())
        + f"; {_anzahl(st, 'alt_id')} ALKIS-Sportstätten bestätigt"
        + f" (davon {_anzahl(st, 'alt_bezug')} als Nachbarfläche)"
    )
    bericht.lizenzen.append(alt_modul.QUELLE)

    st = zusammenfuehren(st, FELDER_STAETTE)
    an = zusammenfuehren(an, FELDER_ANLAGE)
    st, an = verifiziere(st, an)
    stufen = st["verifikation_stufe"].value_counts().to_dict()
    bericht("Verifikation Sportstätten: " + ", ".join(f"{k}: {v}" for k, v in stufen.items()))
    return gpd_aus(st, staetten.crs), gpd_aus(an, anlagen.crs), bericht


def _status(text: str) -> None:
    """Statuszeile, die laufende Fortschrittsbalken nicht zerreißt."""
    try:
        from tqdm.auto import tqdm

        tqdm.write(text)
    except ImportError:  # pragma: no cover
        print(text, flush=True)


def gpd_aus(df, crs):
    import geopandas as gpd

    return gpd.GeoDataFrame(df, geometry="geometry", crs=crs)


def _anzahl(df, spalte: str) -> int:
    return int(df[spalte].notna().sum()) if spalte in df.columns else 0
