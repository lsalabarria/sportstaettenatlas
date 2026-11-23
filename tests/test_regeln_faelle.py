"""Gemeinsame Testfälle (regeln_faelle.json) auf der Python-Seite; test_web.py prüft dieselben
Fälle im Formular. So können Python und JavaScript nicht unbemerkt auseinanderlaufen."""

import json
from pathlib import Path

import pytest

from sportstaettenatlas import modell
from sportstaettenatlas.validate import abstand_m, aehnlich, norm_name, org_kern

FAELLE = json.loads((Path(__file__).parent / "regeln_faelle.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(("name", "erwartet"), FAELLE["norm_name"])
def test_norm_name(name, erwartet):
    assert norm_name(name) == erwartet


@pytest.mark.parametrize(("name", "erwartet"), FAELLE["org_kern"])
def test_org_kern(name, erwartet):
    assert org_kern(name) == erwartet


@pytest.mark.parametrize(("a", "b", "erwartet"), FAELLE["aehnlich"])
def test_aehnlich(a, b, erwartet):
    assert aehnlich(a, b) == pytest.approx(erwartet, abs=1e-9)


@pytest.mark.parametrize("fall", FAELLE["abstand_m"])
def test_abstand_m(fall):
    *lagen, erwartet = fall
    assert abstand_m(*lagen) == pytest.approx(erwartet, abs=1e-3)


@pytest.mark.parametrize("fall", FAELLE["zwischen_feldern"])
def test_zwischen_feldern(fall):
    funde = modell.zwischen_feldern(getattr(modell, fall["modell"]), fall["objekt"])
    assert [[r, f] for r, f, _ in funde] == fall["funde"]


def test_meldungen_im_modell():
    # dieselben Vorlagen in der Fehlermeldung von Pydantic und im Schema für das Formular
    with pytest.raises(ValueError, match="waehrung: nötig, wenn Kosten angegeben ist"):
        modell.Sanierung(jahr=2010, kosten=1000)
    atlas = modell.schema()["atlas"]
    assert atlas["meldungen"] == modell.MELDUNGEN and atlas["pruefung"] == modell.PRUEFUNG
