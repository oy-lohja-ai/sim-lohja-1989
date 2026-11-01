"""Kuvan kehys kohtauksille. Käyttö build.py:ssä:
sys.path.insert(0, ROOT / "src/lib"); import kehys.

- `luma_down(c, n)`: väri n askelta tummemmaksi lumaketjussa (1 -> 15 -> 12 -> 11 -> 0, 7 -> 8 -> 2 -> 9 -> 0, ...).
- `kulmamaski(r, oikea, ala)`: pyöristetyn kulman spritemaski (21 x 24 hires), musta neljänneskaaren ulkopuolella.
"""
from __future__ import annotations

import numpy as np

# väri -> seuraava tummempi (C64-paletin luma: 0 < 6,9 < 2,11 < 4,8 < 12,14 < 5,10 < 3,15 < 7,13 < 1)
LUMA_DOWN = [0, 15, 9, 14, 6, 8, 0, 8, 9, 0, 2, 0, 11, 5, 6, 12]


def luma_down(c: int, n: int = 1) -> int:
    for _ in range(n):
        c = LUMA_DOWN[c]
    return c


def kulmamaski(r: int, oikea: bool, ala: bool) -> np.ndarray:
    """Sprite (21, 24): musta neljänneskaaren (säde r hires px) ulkopuolella kulman puolella."""
    img = np.zeros((21, 24), bool)
    for y in range(21):
        for x in range(24):
            cx = 23 - x if oikea else x                     # etäisyys pystyreunasta
            cy = 20 - y if ala else y                       # etäisyys vaakareunasta
            if cx < r and cy < r and (r - cx - 0.5) ** 2 + (r - cy - 0.5) ** 2 > r * r:
                img[y, x] = True
    return img
