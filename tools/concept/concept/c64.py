"""C64:n paletti ja ROM-fontti (VICE:n chargen) suomen lisämerkeillä."""
from __future__ import annotations

import glob
from functools import lru_cache

import numpy as np

# Värit VICE:n palettitiedostoista colodore ja pepto-pal
PALETTES = {
    "colodore": ["000000", "ffffff", "96282e", "5bd6ce", "9f2dad", "41b936", "2724c4", "eff347",
                 "9f4815", "5e3500", "da5f66", "474747", "787878", "91ff84", "6864ff", "aeaeae"],
    "pepto": ["000000", "ffffff", "68372b", "70a4b2", "6f3d86", "588d43", "352879", "b8c76f",
              "6f4f25", "433900", "9a6759", "444444", "6c6c6c", "9ad284", "6c5eb5", "959595"],
}

BLACK, WHITE, RED, CYAN, PURPLE, GREEN, BLUE, YELLOW = range(8)


def palette(name: str = "colodore") -> np.ndarray:
    return np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in PALETTES[name]], np.uint8)


def to_rgb(idx: np.ndarray, pal: str = "colodore") -> np.ndarray:
    return palette(pal)[idx]


def _srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def lab(rgb: np.ndarray) -> np.ndarray:
    return _srgb_to_lab(rgb)


# ------------------------------------------------------------------ fontti

# Lisämerkit 8x8 (bitti 7 = vasen pikseli). Suomen ä, ö, å ja euro.
EXTRA_GLYPHS = {
    "ä": [0x66, 0x00, 0x3C, 0x06, 0x3E, 0x66, 0x3E, 0x00],
    "ö": [0x66, 0x00, 0x3C, 0x66, 0x66, 0x66, 0x3C, 0x00],
    "å": [0x18, 0x00, 0x3C, 0x06, 0x3E, 0x66, 0x3E, 0x00],
    "Ä": [0x66, 0x00, 0x3C, 0x66, 0x7E, 0x66, 0x66, 0x00],
    "Ö": [0x66, 0x00, 0x3C, 0x66, 0x66, 0x66, 0x3C, 0x00],
    "Å": [0x18, 0x00, 0x3C, 0x66, 0x7E, 0x66, 0x66, 0x00],
    "€": [0x1E, 0x30, 0x7C, 0x30, 0x7C, 0x30, 0x1E, 0x00],
    "'": [0x18, 0x18, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00],
    "_": [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF],
    "|": [0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18],
    "◆": [0x10, 0x38, 0x7C, 0xFE, 0x7C, 0x38, 0x10, 0x00],
    "▶": [0x60, 0x78, 0x7E, 0x7F, 0x7E, 0x78, 0x60, 0x00],
    "◀": [0x06, 0x1E, 0x7E, 0xFE, 0x7E, 0x1E, 0x06, 0x00],
    "█": [0xFF] * 8,
}


@lru_cache(maxsize=1)
def chargen() -> bytes:
    hits = sorted(glob.glob("/opt/homebrew/Cellar/vice/*/share/vice/C64/chargen-901225-01.bin"))
    if not hits:
        raise FileNotFoundError("VICE:n chargen-901225-01.bin puuttuu (brew install vice)")
    return open(hits[-1], "rb").read()


def _screen_code_mixed(ch: str) -> int:
    """ASCII -> näyttökoodi pienaakkosmerkistössä (ROM $0800)."""
    o = ord(ch)
    if "a" <= ch <= "z":
        return o - 96
    if "A" <= ch <= "Z":
        return o - 65 + 65
    if ch == "@":
        return 0
    if 32 <= o <= 63:
        return o
    return 32


@lru_cache(maxsize=None)
def glyph(ch: str) -> np.ndarray:
    """8x8 bool-taulukko merkistä (C64:n ROM-fontti, pienaakkossetti)."""
    rows = EXTRA_GLYPHS.get(ch)
    if rows is None:
        code = _screen_code_mixed(ch)
        rows = chargen()[0x800 + code * 8:0x800 + code * 8 + 8]
    return np.array([[(r >> (7 - b)) & 1 for b in range(8)] for r in rows], bool)
