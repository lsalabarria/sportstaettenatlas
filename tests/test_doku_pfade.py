"""Die Pfade, die in den READMEs stehen, gibt es auch.

Geprüft werden Links ([Text](pfad)) und Pfade in `Backticks` (mit „/“; ein bloßer
Dateiname wie `kategorien.py` ist meist nur erwähnt). Ein Pfad gilt als vorhanden,
wenn es ihn vom Ordner der README aus, von der Wurzel des Repositorys aus oder im Paket
(src/sportstaettenatlas/) gibt. Nicht geprüft werden Adressen, Platzhalter (<Land>, …) und
was nur lokal entsteht (results/, docs/, _transfer/).
"""

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
READMES = [WURZEL / "README.md", WURZEL / "daten" / "README.md"]
NUR_LOKAL = ("results/", "docs/", "_transfer/")  # nicht im Git (siehe .gitignore)

LINK = re.compile(r"\]\(([^)\s]+)\)")
CODE = re.compile(r"`([^`\n]+)`")


def _ist_pfad(t: str) -> bool:
    if any(z in t for z in (" ", "<", ">", "…", "*", "://", "=", "@")):
        return False
    if t.startswith(("/", "-", "#", "mailto:")) or t in (".", ".."):
        return False
    return "/" in t


def pfade(readme: Path) -> list[str]:
    text = re.sub(r"```.*?```", "", readme.read_text(encoding="utf-8"), flags=re.DOTALL)
    links = [z.split("#")[0] for z in LINK.findall(text) if not z.startswith(("#", "http"))]
    code = [z for z in CODE.findall(text) if _ist_pfad(z)]
    return sorted({p for p in links + code if p and not p.startswith(NUR_LOKAL)})


def _gibt_es(readme: Path, pfad: str) -> bool:
    basen = (readme.parent, WURZEL, WURZEL / "src" / "sportstaettenatlas")
    return any((b / pfad.rstrip("/")).exists() for b in basen)


@pytest.mark.parametrize("readme", READMES, ids=lambda p: str(p.relative_to(WURZEL)))
def test_pfade_in_der_readme_gibt_es(readme):
    if not readme.exists():
        pytest.skip(f"{readme.relative_to(WURZEL)} fehlt")
    fehlen = [p for p in pfade(readme) if not _gibt_es(readme, p)]
    assert not fehlen, f"in {readme.relative_to(WURZEL)} genannt, aber nicht vorhanden: {fehlen}"


def test_pfade_erkennen(tmp_path):
    r = tmp_path / "README.md"
    r.write_text(
        "Siehe [Modell](erzeugt/datenmodell.md#felder) und `modell/klassen.py`, "
        "`outside/<Land>/`, `https://x.example/a`, `results/out/`, `uv run pytest`, "
        "[oben](#anfang), `pyproject.toml`, [Lizenz](LICENSE).\n```\ngit mv daten/alt.csv daten/neu/\n```\n",
        encoding="utf-8",
    )
    assert pfade(r) == ["LICENSE", "erzeugt/datenmodell.md", "modell/klassen.py"]
