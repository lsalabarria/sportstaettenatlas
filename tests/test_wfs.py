import xml.etree.ElementTree as ET

from sportstaettenatlas.klassifikation import Regelwerk
from sportstaettenatlas.quellen import GEBIETE, QUELLEN
from sportstaettenatlas.wfs import fes_filter, getfeature_params, kacheln


def test_getfeature_params_bbox():
    q = QUELLEN["rp"]
    p = getfeature_params(q.typ_gebaeude, GEBIETE["koblenz-innenstadt"], q.crs, 100, 200)
    assert p["TYPENAMES"] == "ave:GebaeudeBauwerk"
    assert p["BBOX"].endswith("urn:ogc:def:crs:EPSG::25832")
    assert p["STARTINDEX"] == "200" and p["COUNT"] == "100"


def test_getfeature_params_filter_ersetzt_bbox():
    p = getfeature_params("ave:Nutzung", (0, 0, 1, 1), "EPSG:25832", 10, 0, "<x/>")
    assert "BBOX" not in p and p["FILTER"] == "<x/>"


def test_gebiete_plausibel():
    for xmin, ymin, xmax, ymax in GEBIETE.values():
        assert xmin < xmax and ymin < ymax
        assert 280_000 <= xmin < 920_000 and 5_200_000 < ymin < 6_100_000  # UTM32, Deutschland


def test_kacheln_decken_ab():
    bbox = (0, 0, 25_000, 10_000)
    k = kacheln(bbox, 10_000)
    assert len(k) == 3
    assert k[-1] == (20_000, 0, 25_000, 10_000)
    assert len(kacheln(GEBIETE["rlp"], 10_000)) == 19 * 23


def test_fes_filter_ist_wohlgeformt():
    regeln = Regelwerk.laden()
    xml = fes_filter((1, 2, 3, 4), "EPSG:25832", "funktion", regeln.stichwoerter_gebaeude())
    wurzel = ET.fromstring(xml)
    ns = {"fes": "http://www.opengis.net/fes/2.0"}
    assert wurzel.find("fes:And/fes:BBOX", ns) is not None
    likes = wurzel.findall("fes:And/fes:Or/fes:PropertyIsLike", ns)
    assert len(likes) == len(regeln.stichwoerter_gebaeude()) > 3
    nur_box = ET.fromstring(fes_filter((1, 2, 3, 4), "EPSG:25832", None, []))
    assert nur_box.find("fes:BBOX", ns) is not None


def test_stichwoerter_ohne_redundanz():
    w = Regelwerk.laden().stichwoerter_gebaeude()
    assert "sport" in w and "sporthalle" not in w and "hallenbad" in w
