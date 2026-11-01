"""Partti 5: Lohjantähden kuoppa 1989 Hillnerin talon paikalla ja torni nousee (Rinteenhammas).

Avainkuva 3 (`torni`): valmis torni tuijottaa Sokeripalaa (1991, sininen hetki) samalta torin akselilta kuin
Hillner 1964 ja Lohjantähti 1991 (tori.CAMERA): star.render ja etualalla oikeassa reunassa Sokeripalan
valkoinen kulma nauhaikkunoineen, joihin lasitornin keltainen valo heijastuu. Kuopan ja rungon kuvat ovat
kuoppa2.py:ssä.

Valo vasemmalta ylhäältä, pinnat liukuväreinä katkoviivaditherillä, keltainen 7 vain rakentajissa ja
lasitornissa. Kuvat 160 x 144 MC-px (letterbox).
"""
from __future__ import annotations


import numpy as np

from . import star
from .house import reduce_cells
from .pixel import (BLACK, BLUE, DGREY, GREY, LBLUE, LGREY, WHITE, YELLOW,
                    DASH, odither)

H, W = 144, 160
CROP = 28                                # tori.CAMERA (200 riviä) -> 144 riviä


SUN = np.array([-0.55, 0.45, 0.70])      # ilta-aurinko vasemmalta (lännestä) takaa
SUN /= np.linalg.norm(SUN)


# ------------------------------------------------------------------ 3. valmis torni tuijottaa Sokeripalaa

def torni(lit: float = 1.0) -> np.ndarray:
    """Avainkuva 3: valmis Lohjantähti sinisellä hetkellä (star.render) ja etualalla oikeassa reunassa
    Sokeripalan valkoinen kulma: rappaus varjossa 12/15, nauhaikkunat 0/6 pakenevat oikealle, ikkunoissa
    lasitornin keltainen heijastus (7). Sokeripala katsoo torin yli Rinteenhampaaseen."""
    from .tori import CAMERA
    img = star.render(CAMERA, lit, lamp=False).copy()[CROP:CROP + H]
    yy, xx = np.mgrid[0:H, 0:W]
    edge = 138 + (yy - H) * 0.05                                        # kulman pystysärmä hieman vinossa
    wall = xx >= edge
    vpx, vpy = 360.0, 118.0                                             # nauhaikkunoiden pakopiste oikealla
    f = np.clip((xx - edge) / (vpx - edge), 0, 0.95)
    v = (yy - vpy * f) / (1 - f)                                        # rivi, jolta viiva lähtee kulmasta
    tone = 0.30 + 0.30 * (xx - edge) / 22.0 + 0.08 * np.sin(yy * 0.13)
    img[wall] = odither(np.clip(tone, 0, 1), (DGREY, GREY, LGREY, WHITE))[wall]
    band = wall & ((v % 30) > 17) & ((v % 30) < 26)
    img[band] = odither(np.clip(0.2 + 0.2 * ((v % 30) - 17) / 9, 0, 1), (BLACK, BLUE, LBLUE))[band]
    glint = band & ((v % 30) > 19) & ((v % 30) < 21.5) & ((xx - edge) < 10) & (DASH[yy % 4, xx % 8] < 0.6)
    img[glint] = YELLOW                                                 # tornin heijastus
    img[wall & ((v % 30) > 26) & ((v % 30) < 27.2)] = WHITE              # ikkunalauta valossa
    img[wall & (np.abs(xx - edge) < 1)] = WHITE                         # särmän reunavalo
    img[wall & (np.abs(xx - edge - 1) < 1)] = BLACK
    reduce_cells(img)
    return img
