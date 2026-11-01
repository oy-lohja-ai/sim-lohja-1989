"""Spritet: kaupunginjohtajakursori (2 hires-spriteä, 24 x 21)."""
from __future__ import annotations


import numpy as np

from .c64 import BLACK, WHITE


# ---------------------------------------------------------------- pöly ja räjähdys


MAYOR = [
    "...kkkkk.......",
    "...kkkkk.......",
    "...kkkkk.......",
    ".kkkkkkkkk.....",
    "...............",
    "....kwwwk......",
    "...kwkwkwk.....",
    "...kwwwwwk..kk.",
    "....kwkwk..kwk.",
    "...kkkkkkkkwk..",
    "..kwwwwwwwkk...",
    "..kwwwkwwwk....",
    "..kwwwkwwwk....",
    "..kwwwkwwwk....",
    "...kkkkkkk.....",
    "...kwk.kwk.....",
    "...kkk.kkk.....",
]


def mayor_cursor(color: int = WHITE) -> list[np.ndarray]:
    """SC2K:n Rewards-kursori: kaupunginjohtaja nostaa hattuaan (2 hires-spriteä: reuna ja täyttö)."""
    a = np.array([[{"k": BLACK, "w": color}.get(ch, -1) for ch in row] for row in MAYOR], np.int16)
    return [np.where(a == BLACK, BLACK, -1), np.where(a == color, color, -1)]
