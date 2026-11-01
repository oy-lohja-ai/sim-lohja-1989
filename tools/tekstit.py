"""Ruudun tekstit tekstit.yaml:sta (repon juuri): buildien yhteinen lukija.

Kaikki arvot luetaan tekstinä (yaml.BaseLoader: 1989 ei muutu luvuksi eikä "no" totuusarvoksi). Lukijat:
tools/gfx/taulu.py (taulut), src/proto/kyltti/build.py (hillner-eka, hillner-toka), tools/disk/levynvaihto.py
(levynvaihdot), src/proto/greetsit/build.py (greets-harju), src/proto/koti/build.py (tekijat), tools/disk/loppu.py
(lopputekstit), tools/disk/dos.py (dos).
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TIEDOSTO = ROOT / "tekstit.yaml"


def lue(avain: str):
    """tekstit.yaml:n avaimen arvo (merkkijono, lista tai sanakirja, jonka avaimet ovat merkkijonoja)."""
    d = yaml.load(TIEDOSTO.read_text(encoding="utf-8"), Loader=yaml.CBaseLoader)
    if not isinstance(d, dict) or avain not in d:
        raise SystemExit(f"{TIEDOSTO.relative_to(ROOT)}: avain {avain!r} puuttuu")
    return d[avain]


def lista(avain: str) -> list[str]:
    """Avaimen arvo tekstilistana (yksittäinen teksti on yhden alkion lista)."""
    v = lue(avain)
    v = [v] if isinstance(v, str) else v
    if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
        raise SystemExit(f"{TIEDOSTO.relative_to(ROOT)}: {avain}: odotettiin lista tekstejä")
    return v
