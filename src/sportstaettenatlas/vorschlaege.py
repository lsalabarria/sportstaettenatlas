"""Vorschläge aus einem LimeSurvey-Export in daten/ übernehmen (Befehl `vorschlaege`).

Der Export ist eine CSV mit einer Zeile je Antwort; die Spalte „Vorschlag …“ enthält das JSON,
das das Formular der Webseite schreibt (modell.Vorschlag). Übernommen wird in der Reihenfolge
der Antwort-ID:

- neu:          neue Sportstätte mit ihren Anlagen
- aenderung:    die geänderten Felder (`geaendert`) der Sportstätte; ein Feld, das dort steht,
                aber fehlt, wird geleert
- anlagen:      die genannten Anlagen (vorhandene über die Kurz-ID, ganz ersetzt), neue dazu,
                `entfernte_anlagen` gelöscht
- organisation: Organisation anlegen, die geänderten Felder ändern oder löschen
- sportkomplex: Sportkomplex anlegen oder seine geänderten Felder ändern; die genannten
                Sportstätten bekommen ihn in `sportkomplex`, bisherige, die fehlen, verlieren
                ihn; `loeschen` löst ihn auf (Datei weg, Verweise entfernt)
- stuetzpunkt:  Stützpunkt anlegen, seine geänderten Felder ändern (auch die Listen der
                Sportstätten und Sportkomplexe) oder löschen

Eine Änderung überschreibt den Wert in daten/. Setzen zwei Vorschläge im Export dasselbe Feld
verschieden, steht dort „a|b“ (mit | getrennt), und es gibt eine Warnung. Übernommene
Antwort-IDs stehen in daten/vorschlaege_uebernommen.txt und werden beim nächsten Mal
übersprungen. Die Spalte „Kommentar“ wird nur angezeigt, nie gespeichert.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import werte
from .bestand import (
    OHNE_KREIS,
    _laender,
    _lies_ordner,
    _staetten_ordner,
    aufteilen,
    bereinigen,
    finde_organisation,
    komplex_dateien,
    lies_bestand,
    lies_sportkomplexe,
    lies_stuetzpunkte,
    loesche_stuetzpunkt,
    organisation_id,
    schreibe_bestand,
    schreibe_organisation,
    schreibe_sportkomplex,
    schreibe_stuetzpunkt,
    sportkomplexe_einordnen,
)
from .modell import Vorschlag, pruefe

UEBERNOMMEN = "vorschlaege_uebernommen.txt"
_NAMENSRAUM = uuid.UUID("5d0c7a52-6b8e-4c1f-9a3e-2f4b8c6d1e07")
_FEST = ("id", "sportstaette_id")  # bleiben beim Ersetzen einer Anlage


@dataclass
class Antwort:
    id: str
    vorschlag: dict
    kommentar: str = ""


@dataclass
class Ergebnis:
    uebernommen: Counter = field(default_factory=Counter)  # Art → Anzahl
    uebersprungen: int = 0  # schon früher übernommen
    warnungen: list[str] = field(default_factory=list)
    kommentare: list[tuple[str, str]] = field(default_factory=list)
    neue_ids: list[str] = field(default_factory=list)


def lies_export(pfad: Path) -> list[Antwort]:
    """LimeSurvey-Export (CSV) → Antworten mit Vorschlag, nach Antwort-ID sortiert."""
    zeilen = werte.zeilen(werte.text(Path(pfad).read_bytes()))
    if not zeilen:
        return []
    kopf = list(zeilen[0])

    def spalte(*anfaenge: str) -> str | None:
        return next((k for k in kopf if k and k.strip().lower().startswith(anfaenge)), None)

    s_id, s_vorschlag = spalte("antwort id", "id"), spalte("vorschlag", "data")
    s_kommentar = spalte("kommentar")
    if not s_id or not s_vorschlag:
        raise ValueError(f"{Path(pfad).name}: Spalten „Antwort ID“ und „Vorschlag“ nicht gefunden")
    out = []
    for z in zeilen:
        text = (z.get(s_vorschlag) or "").strip()
        if not text:
            continue
        try:
            v = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Antwort {z.get(s_id)}: Vorschlag ist kein JSON ({exc})") from None
        kommentar = (z.get(s_kommentar) or "").strip() if s_kommentar else ""
        out.append(Antwort(str(z.get(s_id) or "").strip(), v, kommentar))
    return sorted(out, key=lambda a: (len(a.id), a.id))


def _text(w) -> str:
    if w is None:
        return ""
    if isinstance(w, list):
        return "; ".join(map(str, w))
    if isinstance(w, dict):
        return json.dumps(w, ensure_ascii=False, separators=(",", ":"))
    return str(w)


class _Uebernahme:
    """Hält die berührten Sportstätten und Organisationen und merkt sich je Feld, welche
    Vorschläge es gesetzt haben – für die Kennzeichnung „a|b“."""

    def __init__(self, daten: Path, e: Ergebnis):
        self.daten = daten
        self.e = e
        self.vorhanden = {
            k: v for land in _laender(daten) for k, v in _staetten_ordner(land).items()
        }
        self.staetten: dict[str, dict] = {}  # id → Sportstätte mit "anlagen"
        self.neu: set[str] = set()
        self.entfernt: dict[str, set[str]] = {}  # Sportstätte → IDs entfernter Anlagen
        self.orgs: dict[str, dict | None] = {}  # id → Organisation; None: löschen
        self.komplexe: dict[str, dict | None] = {}  # id → Sportkomplex; None: auflösen
        self.stuetzpunkte: dict[str, dict | None] = {}  # id → Stützpunkt; None: löschen
        self._mitglieder: dict[str, set[str]] | None = None  # Komplex → Sportstätten in daten/
        self.gesetzt: dict[tuple[str, str], list[tuple[str, object]]] = {}

    def setze(self, ziel: str, obj: dict, pfad: str, w, antwort: str, name: str) -> None:
        werte_ = self.gesetzt.setdefault((ziel, pfad), [])
        if any(_text(x) == _text(w) for _, x in werte_):
            return
        werte_.append((antwort, w))
        if len(werte_) == 1:
            werte.setze(obj, pfad, w)
            return
        werte.setze(obj, pfad, "|".join(_text(x) for _, x in werte_))
        quellen = ", ".join(a for a, _ in werte_)
        self.e.warnungen.append(
            f"Antworten {quellen}: {name}, {pfad} widersprüchlich – „"
            + "|".join(_text(x) for _, x in werte_)
            + "“ eingetragen"
        )

    def staette(self, sid: str) -> dict | None:
        if sid not in self.staetten and sid in self.vorhanden:
            self.staetten[sid] = _lies_ordner(self.vorhanden[sid])
        return self.staetten.get(sid)

    # --- je Art ---

    def neu_anlegen(self, a: Antwort, v: dict) -> None:
        sid = str(uuid.uuid5(_NAMENSRAUM, f"limesurvey/{a.id}"))
        st = self.staette(sid)
        if st is None:
            anlagen = [
                {**x, "id": str(uuid.uuid5(_NAMENSRAUM, f"limesurvey/{a.id}/{i}"))}
                for i, x in enumerate(v.get("anlagen") or [])
            ]
            self.staetten[sid] = {**v["sportstaette"], "id": sid, "anlagen": anlagen}
            self.neu.add(sid)
            self.e.neue_ids.append(sid)
            return
        self._felder(a, st, v["sportstaette"], None)  # schon da (z. B. mit --alle)

    def aendern(self, a: Antwort, v: dict) -> None:
        st = self.staette(v["sportstaette_id"])
        if st is None:
            self.e.warnungen.append(f"Antwort {a.id}: Sportstätte {v['sportstaette_id']} fehlt")
            return
        self._felder(a, st, v["sportstaette"], v.get("geaendert") or None)

    def _felder(self, a: Antwort, st: dict, neu: dict, geaendert: list[str] | None) -> None:
        if geaendert is None:  # ohne Liste: alle angegebenen Felder, die Adresse je Teil
            geaendert = []
            for k, w in neu.items():
                if k == "adresse" and isinstance(w, dict):
                    geaendert += [f"adresse.{k2}" for k2 in w]
                elif k not in ("id", "anlagen"):
                    geaendert.append(k)
        name = f"Sportstätte {st.get('name') or st['id']}"
        for pfad in geaendert:
            self.setze(st["id"], st, pfad, werte.hole(neu, pfad), a.id, name)

    def anlagen(self, a: Antwort, v: dict) -> None:
        sid = v["sportstaette_id"]
        st = self.staette(sid)
        if st is None:
            self.e.warnungen.append(f"Antwort {a.id}: Sportstätte {sid} fehlt")
            return

        def finde(kurz: str) -> dict | None:
            treffer = [x for x in st["anlagen"] if str(x.get("id", "")).startswith(kurz)]
            return treffer[0] if len(treffer) == 1 else None

        for i, neu in enumerate(v.get("anlagen") or []):
            kurz = str(neu.get("id") or "")
            if not kurz:
                aid = str(uuid.uuid5(_NAMENSRAUM, f"limesurvey/{a.id}/{i}"))
                if not any(x.get("id") == aid for x in st["anlagen"]):
                    st["anlagen"].append({**neu, "id": aid, "sportstaette_id": sid})
                continue
            alt = finde(kurz)
            if alt is None:
                self.e.warnungen.append(f"Antwort {a.id}: Anlage {kurz} in {sid} nicht gefunden")
                continue
            name = f"Anlage {alt.get('typ')} {kurz} ({st.get('name') or sid})"
            for k in sorted(({*alt, *neu} - set(_FEST)), key=list({**alt, **neu}).index):
                self.setze(alt["id"], alt, k, neu.get(k), a.id, name)
        for kurz in v.get("entfernte_anlagen") or []:
            alt = finde(kurz)
            if alt is None:
                continue
            if any(z == alt["id"] for z, _ in self.gesetzt):
                self.e.warnungen.append(
                    f"Antwort {a.id}: Anlage {kurz} ({st.get('name') or sid}) soll weg, ein "
                    "anderer Vorschlag ändert sie – bleibt, bitte von Hand prüfen"
                )
                continue
            st["anlagen"].remove(alt)
            self.entfernt.setdefault(sid, set()).add(alt["id"])

    def organisation(self, a: Antwort, v: dict) -> None:
        oid = v.get("organisation_id") or organisation_id(v["organisation"]["name"])
        if oid not in self.orgs:
            pfad = finde_organisation(self.daten, oid)
            self.orgs[oid] = json.loads(pfad.read_text("utf-8")) if pfad else None
        if v.get("loeschen"):
            if any(z == oid for z, _ in self.gesetzt):
                self.e.warnungen.append(
                    f"Antwort {a.id}: Organisation {oid} soll weg, ein anderer Vorschlag ändert "
                    "sie – bleibt, bitte von Hand prüfen"
                )
            else:
                self.orgs[oid] = None
            return
        neu = v["organisation"]
        o = self.orgs[oid]
        if o is None:
            self.orgs[oid] = {**neu, "id": oid}
            for k in neu:
                self.gesetzt.setdefault((oid, k), []).append((a.id, neu[k]))
            return
        name = f"Organisation {o.get('name') or oid}"
        for k in v.get("geaendert") or [k for k in neu if k != "id"]:
            self.setze(oid, o, k, neu.get(k), a.id, name)

    def mitglieder(self, kid: str) -> set[str]:
        """Sportstätten mit diesem Sportkomplex: in daten/ und in diesem Lauf geändert."""
        if self._mitglieder is None:
            self._mitglieder = {}
            for d in lies_bestand(self.daten):
                if d.get("sportkomplex"):
                    self._mitglieder.setdefault(d["sportkomplex"], set()).add(d["id"])
        out = {
            sid
            for sid in self._mitglieder.get(kid, set())
            if sid not in self.staetten or self.staetten[sid].get("sportkomplex") == kid
        }
        return out | {sid for sid, st in self.staetten.items() if st.get("sportkomplex") == kid}

    def sportkomplex(self, a: Antwort, v: dict) -> None:
        kid = v.get("sportkomplex_id") or str(uuid.uuid5(_NAMENSRAUM, f"limesurvey/{a.id}/komplex"))
        if kid not in self.komplexe:
            alt = {k["id"]: k for k in lies_sportkomplexe(self.daten)}.get(kid)
            self.komplexe[kid] = alt
        k = self.komplexe[kid]
        name = f"Sportkomplex {(k or v.get('sportkomplex') or {}).get('name') or kid}"
        bisher = self.mitglieder(kid)
        if v.get("loeschen"):
            if k is None:
                self.e.warnungen.append(f"Antwort {a.id}: Sportkomplex {kid} gibt es nicht")
                return
            self.komplexe[kid] = None
            for sid in sorted(bisher):
                if st := self.staette(sid):
                    self.setze(
                        sid, st, "sportkomplex", None, a.id, f"Sportstätte {st.get('name') or sid}"
                    )
            return
        neu = v["sportkomplex"]
        if k is None:
            k = self.komplexe[kid] = {**neu, "id": kid}
            for feld in neu:
                self.gesetzt.setdefault((kid, feld), []).append((a.id, neu[feld]))
        else:
            for feld in v.get("geaendert") or [x for x in neu if x != "id"]:
                self.setze(kid, k, feld, werte.hole(neu, feld), a.id, name)
        soll = set(v.get("sportstaetten") or [])
        for sid in sorted(soll | bisher):
            st = self.staette(sid)
            if st is None:
                self.e.warnungen.append(f"Antwort {a.id}: Sportstätte {sid} fehlt ({name})")
                continue
            w = kid if sid in soll else None
            self.setze(sid, st, "sportkomplex", w, a.id, f"Sportstätte {st.get('name') or sid}")

    def stuetzpunkt(self, a: Antwort, v: dict) -> None:
        sid = v.get("stuetzpunkt_id") or str(
            uuid.uuid5(_NAMENSRAUM, f"limesurvey/{a.id}/stuetzpunkt")
        )
        if sid not in self.stuetzpunkte:
            self.stuetzpunkte[sid] = {x["id"]: x for x in lies_stuetzpunkte(self.daten)}.get(sid)
        alt = self.stuetzpunkte[sid]
        if v.get("loeschen"):
            if alt is None:
                self.e.warnungen.append(f"Antwort {a.id}: Stützpunkt {sid} gibt es nicht")
            else:
                self.stuetzpunkte[sid] = None
            return
        neu = v["stuetzpunkt"]
        if alt is None:
            self.stuetzpunkte[sid] = {**neu, "id": sid}
            for feld in neu:
                self.gesetzt.setdefault((sid, feld), []).append((a.id, neu[feld]))
            return
        name = f"Stützpunkt {alt.get('name') or sid}"
        for feld in v.get("geaendert") or [x for x in neu if x != "id"]:
            self.setze(sid, alt, feld, werte.hole(neu, feld), a.id, name)

    # --- schreiben ---

    def schreibe(self, kreis_von: Callable) -> None:
        for sid, st in self.staetten.items():
            if sid in self.neu:
                schreibe_bestand([st], self.daten, "RP", kreis_von, modus="neu")
                continue
            ordner = self.vorhanden[sid]
            for aid in self.entfernt.get(sid, ()):
                (ordner / f"{aid}.json").unlink(missing_ok=True)
            for name, text in aufteilen(st).items():
                pfad = ordner / name
                if not pfad.exists() or pfad.read_text(encoding="utf-8") != text:
                    pfad.write_text(text, encoding="utf-8")
        for oid, o in self.orgs.items():
            if o is not None:
                schreibe_organisation(self.daten, o)
            elif pfad := finde_organisation(self.daten, oid):
                pfad.unlink()
        for sid, sp in self.stuetzpunkte.items():
            if sp is not None:
                schreibe_stuetzpunkt(self.daten, sp)
            else:
                loesche_stuetzpunkt(self.daten, sid)
        if not self.komplexe:
            return
        dateien = {p.stem: p for p in komplex_dateien(self.daten)}
        for kid, k in self.komplexe.items():
            if k is not None:  # erst in den bisherigen Kreis, einordnen sucht den richtigen
                alt = dateien.get(kid)
                ordner = alt.parent.parent.name if alt else OHNE_KREIS
                land = alt.parent.parent.parent.name if alt else None
                schreibe_sportkomplex(self.daten, k, ordner, land)
            elif kid in dateien:
                dateien[kid].unlink()
                if not any(dateien[kid].parent.iterdir()):
                    dateien[kid].parent.rmdir()
        sportkomplexe_einordnen(self.daten, kreis_von)


def uebernimm(
    antworten: list[Antwort],
    daten: Path,
    kreis_von: Callable,
    probe: bool = False,
    alle: bool = False,
) -> Ergebnis:
    """Vorschläge in daten/ übernehmen (siehe oben). Mit probe wird nichts geschrieben;
    mit alle auch Antworten, die schon übernommen sind."""
    daten = Path(daten)
    e = Ergebnis()
    liste = daten / UEBERNOMMEN
    frueher = set(liste.read_text("utf-8").split()) if liste.exists() else set()
    u = _Uebernahme(daten, e)
    neu_uebernommen = []
    for a in antworten:
        if a.id in frueher and not alle:
            e.uebersprungen += 1
            continue
        v = bereinigen(a.vorschlag, Counter())  # ohne leere Angaben und E-Mail-Adressen
        if isinstance(a.vorschlag.get("anlagen"), list):
            v.setdefault("anlagen", [])  # „keine Anlagen“ ist eine Angabe
        if fehler := pruefe(Vorschlag, v):
            e.warnungen.append(f"Antwort {a.id}: passt nicht zum Modell – " + "; ".join(fehler))
            continue
        art = v["art"]
        {
            "neu": u.neu_anlegen,
            "aenderung": u.aendern,
            "anlagen": u.anlagen,
            "sportkomplex": u.sportkomplex,
            "stuetzpunkt": u.stuetzpunkt,
        }.get(art, u.organisation)(a, v)
        e.uebernommen[art] += 1
        if a.kommentar:
            e.kommentare.append((a.id, a.kommentar))
        neu_uebernommen.append(a.id)
    if not probe:
        u.schreibe(kreis_von)
        if neu_uebernommen:
            ids = sorted(frueher | set(neu_uebernommen), key=lambda x: (len(x), x))
            liste.write_text("\n".join(ids) + "\n", encoding="utf-8")
    return e
