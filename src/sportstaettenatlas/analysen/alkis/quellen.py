"""ALKIS-Dienst des Landes und Ausschnitte.

ALKIS gibt es in allen Ländern im "vereinfachten Schema" (AdV); die Feature-Typen heißen
überall `Nutzung` und `GebaeudeBauwerk`. Für ein weiteres Land genügt eine weitere
WfsQuelle (Endpunkt, Lizenz, Quellenvermerk).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WfsQuelle:
    name: str
    url: str
    typ_nutzung: str
    typ_gebaeude: str
    crs: str  # Abfrage- und Ausgabe-CRS (metrisch, für Flächenberechnung)
    seitengroesse: int
    lizenz: str
    quellenvermerk: str


RP = WfsQuelle(
    name="WFS RP ALKIS Vereinfacht (LVermGeo)",
    url="https://geo5.service24.rlp.de/wfs/alkis_rp.fcgi",
    typ_nutzung="ave:Nutzung",
    typ_gebaeude="ave:GebaeudeBauwerk",
    crs="EPSG:25832",
    seitengroesse=5000,
    lizenz="Datenlizenz Deutschland – Namensnennung – Version 2.0",
    quellenvermerk="©GeoBasis-DE / LVermGeoRP {jahr}, dl-de/by-2-0, www.lvermgeo.rlp.de "
    "[Daten bearbeitet]",
)

# Ausschnitte in EPSG:25832 (xmin, ymin, xmax, ymax)
GEBIETE: dict[str, tuple[float, float, float, float]] = {
    "rlp": (285_000, 5_420_000, 470_000, 5_650_000),  # ganz Rheinland-Pfalz (Rechteck)
    "koblenz-innenstadt": (397_500, 5_576_500, 401_500, 5_580_500),  # zum Ausprobieren
}
