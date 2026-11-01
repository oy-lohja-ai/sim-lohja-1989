"""Rajasolujen värit: `reduce_cells` pitää MC-solussa mustan lisäksi 3 tärkeintä väriä (prioriteetti x
pinta-ala) ja vaihtaa harvinaiset lähimpään kirkkauden mukaan. Perspektiivikuvissa yhteen soluun osuu usein
useampi materiaali.
"""
from __future__ import annotations


import numpy as np

from .pixel import (BLACK, BLUE, BROWN, DGREY, GREEN, GREY, LBLUE, LGREEN, LGREY, LRED, ORANGE, RED, T, WHITE)


# ------------------------------------------------------------------ solut

PRIO = {BLACK: 0, WHITE: 9, LGREY: 6, LBLUE: 4, BLUE: 4, RED: 7, BROWN: 7, LRED: 5, GREY: 6, DGREY: 6,
        ORANGE: 5, GREEN: 6, LGREEN: 5}


def reduce_cells(img: np.ndarray, locked: np.ndarray | None = None) -> int:
    """Rajasolut, joissa perspektiivissä kohtaa useampi materiaali: pidetään 3 tärkeintä väriä
    (prioriteetti x pinta-ala, mustan lisäksi), harvinaiset lähimpään kirkkauden mukaan."""
    from .c64 import palette
    lum = palette().astype(float) @ np.array([0.299, 0.587, 0.114])
    n = 0
    for cy in range(img.shape[0] // 8):
        for cx in range(img.shape[1] // 4):
            cell = img[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
            cols, cnt = np.unique(cell[(cell != BLACK) & (cell != T)], return_counts=True)
            if len(cols) <= 3:
                continue
            lk = set() if locked is None else set(np.unique(cell[locked[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]]).tolist())
            score = [cnt[i] * (1 + PRIO.get(int(c), 5) / 3) + (1e9 if int(c) in lk else 0) for i, c in enumerate(cols)]
            keep = [int(cols[i]) for i in np.argsort(score)[::-1][:3]]
            for c in cols:
                if int(c) not in keep:
                    m = (cell == c) if locked is None else (cell == c) & ~locked[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
                    cell[m] = min(keep, key=lambda k: abs(lum[k] - lum[int(c)]))
                    n += int(m.sum())
    return n
