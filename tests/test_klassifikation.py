from sportstaettenatlas.analysen.alkis.klassifikation import Regelwerk

R = Regelwerk.laden()


def test_hallen():
    assert R.gebaeude("Sport-, Turnhalle").typ == "sporthalle"
    assert R.gebaeude("Hallenbad").typgruppe == "becken"
    assert R.gebaeude("Tennishalle").typ == "tennishalle"


def test_nebengebaeude_vor_sportplatz():
    t = R.gebaeude("Gebäude zum Sportplatz")
    assert t.rolle == "zubehoer"
    assert R.gebaeude("Gebäude im Stadion").rolle == "zubehoer"
    assert R.gebaeude("Tribüne").rolle == "zubehoer"


def test_unbestimmt_wird_geprueft():
    t = R.gebaeude("Gebäude für Sportzwecke")
    assert t.typ == "sportgebaeude_unbestimmt" and t.pruefen


def test_kein_sport():
    assert R.gebaeude("Wohnhaus") is None
    assert R.gebaeude(None) is None
    assert R.gebaeude("nan") is None


def test_name_hilft():
    assert R.gebaeude("Gebäude für öffentliche Zwecke", "Sporthalle Süd").typ == "sporthalle"


def test_nutzung():
    assert R.ist_sportflaeche("Sport-, Freizeit- und Erholungsfläche")
    assert not R.ist_sportflaeche("Wohnbaufläche")
    assert R.nutzung("Sportanlage").typ == "sportanlage_unbestimmt"
    assert R.nutzung("Golfplatz").typ == "golfplatz"
    assert R.nutzung("Schwimmbad, Freibad").typ == "freibad"
    assert R.nutzung("Grünanlage") is None
    assert R.nutzung("Freizeitanlage").nur_mit_bestand
    assert not R.nutzung("Sportplatz").nur_mit_bestand
    assert R.nutzung("Kleingarten") is None


def test_echte_werte_koblenz():
    # Fälle aus dem ersten Lauf Koblenz-Innenstadt
    assert R.nutzung("Parken", "Moselbad Koblenz") is None
    assert R.nutzung("Schwimmen", "Freibad Oberwerth").typ == "freibad"
    assert R.nutzung("Tennis").typ == "tennisanlage"
    t = R.nutzung("Spielplatz, Bolzplatz")
    assert t.typgruppe == "sportgelegenheit" and t.pruefen
    assert R.nutzung(None, "Sportpark Nord").typ == "sportanlage_unbestimmt"


def test_nuerburgring_und_sammelbegriffe():
    assert R.nutzung("Rennbahn", "Nürburgring").typ == "rennbahn"
    assert R.nutzung("Modellfluggelände").typ == "modellfluggelaende"
    assert R.nutzung("Eis-, Rollschuhbahn").typgruppe == "eis"
    assert R.nutzung("Sportplatz").typ == "sportplatz"
    t = R.nutzung("Sportanlage")
    assert t.typgruppe == "unbestimmt" and t.pruefen
    assert R.nutzung("Gebäude- und Freifläche Sport").typgruppe == "unbestimmt"
    assert R.nutzung("Parken", "Nürburgring") is None
    assert R.nutzung("Verkehrsübungsplatz, Testgelände, Fahrsicherheit") is None
    assert R.nutzung("Campingplatz", "Camping am Nürburgring") is None
    assert R.gebaeude("Rennbahn").typ == "rennbahn"
