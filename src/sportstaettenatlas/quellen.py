"""Konfiguration der Datenquellen je Bundesland.

Alle Länder bieten ALKIS im "vereinfachten Schema" (AdV-Produktspezifikation
ALKIS-WFS) an. Die Feature-Typen heißen dort einheitlich `Nutzung`,
`GebaeudeBauwerk` und `Flurstueck`; nur Endpunkt, Namensraum-Präfix und Lizenz
unterscheiden sich. Weitere Länder werden hier ergänzt.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WfsQuelle:
    land: str
    name: str
    url: str
    typ_nutzung: str
    typ_gebaeude: str
    crs: str  # Abfrage- und Ausgabe-CRS (metrisch, für Flächenberechnung)
    seitengroesse: int
    lizenz: str
    quellenvermerk: str


QUELLEN: dict[str, WfsQuelle] = {
    "rp": WfsQuelle(
        land="Rheinland-Pfalz",
        name="WFS RP ALKIS Vereinfacht (LVermGeo)",
        url="https://geo5.service24.rlp.de/wfs/alkis_rp.fcgi",
        typ_nutzung="ave:Nutzung",
        typ_gebaeude="ave:GebaeudeBauwerk",
        crs="EPSG:25832",
        seitengroesse=5000,
        lizenz="Datenlizenz Deutschland – Namensnennung – Version 2.0",
        quellenvermerk="©GeoBasis-DE / LVermGeoRP {jahr}, dl-de/by-2-0, www.lvermgeo.rlp.de "
        "[Daten bearbeitet]",
    ),
    # Beispiel für weitere Länder (Endpunkt prüfen, bevor man es aktiviert):
    # "nw": WfsQuelle(
    #     land="Nordrhein-Westfalen",
    #     name="WFS NW ALKIS vereinfacht",
    #     url="https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht",
    #     typ_nutzung="ave:Nutzung",
    #     typ_gebaeude="ave:GebaeudeBauwerk",
    #     crs="EPSG:25832",
    #     seitengroesse=5000,
    #     lizenz="Datenlizenz Deutschland – Zero – Version 2.0",
    #     quellenvermerk="Geobasis NRW {jahr}",
    # ),
}

# Grobe Ausschnitte in EPSG:25832 (xmin, ymin, xmax, ymax) zum schnellen Testen.
# Bewusst etwas größer als das Stadtgebiet; exakte Grenzen kommen später über
# Verwaltungseinheiten.
GEBIETE: dict[str, tuple[float, float, float, float]] = {
    # Rheinland-Pfalz gesamt (umschließendes Rechteck, ca. 185 x 230 km)
    "rlp": (285_000, 5_420_000, 470_000, 5_650_000),
    "koblenz": (391_000, 5_570_000, 409_000, 5_589_000),
    "koblenz-innenstadt": (397_500, 5_576_500, 401_500, 5_580_500),
    # Landkreis Bad Kreuznach (Rechteck, enthält Randstücke der Nachbarkreise;
    # der Atlas-Abgleich berücksichtigt nur Einträge in diesem Rechteck)
    "kreis-bad-kreuznach": (376_000, 5_498_000, 427_000, 5_540_000),
}
