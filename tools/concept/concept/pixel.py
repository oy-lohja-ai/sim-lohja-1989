"""Pikselitaidon työkalut: vaakaviivoitus sävykentästä, katkoviivat, pisteet ja
solutarkistus. Kaikki MC-resoluutiolla (solu 4 x 8), musta 0 on jokaisen solun vapaa väri ($D021)."""
from __future__ import annotations

import numpy as np

BLACK, WHITE, RED, CYAN, PURPLE, GREEN, BLUE, YELLOW = 0, 1, 2, 3, 4, 5, 6, 7
ORANGE, BROWN, LRED, DGREY, GREY, LGREEN, LBLUE, LGREY = 8, 9, 10, 11, 12, 13, 14, 15
T = 255                                  # läpinäkyvä


def _dash_matrix() -> np.ndarray:
    """Vaakasuora katkoviivadither: 4 riviä x 8 saraketta. Jokaisella rivillä yksi
    pätkä, joka kasvaa symmetrisesti keskeltään; rivien keskikohdat 0, 4, 2, 6 (tiililadonta), joten
    25 % = 2 px pätkät, 50 % = 4 px, 75 % = 6 px tasavälein ilman pystysuuntaisia jonoja."""
    m = np.zeros((4, 8))
    rank = [0, 2, 1, 3]
    centre = [0, 4, 2, 6]
    order = [0, 1, -1, 2, -2, 3, -3, 4]
    for r in range(4):
        for k, d in enumerate(order):
            m[r, (centre[r] + d) % 8] = (k * 4 + rank[r]) / 32.0
    return m + 1 / 64


DASH = _dash_matrix()


BAND = 0.3                               # siirtymävyön osuus porrasvälistä (leveät kaistat, kapeat siirtymät)


def odither(tone: np.ndarray, ramp: tuple, ox: int = 0, oy: int = 0, accent: float = 0.0,
            band: float | None = BAND, matrix: np.ndarray = DASH) -> np.ndarray:
    """Liukuväri vaakasuoralla katkoviivaditherillä (DASH): tone 0..1 kulkee rampin värien läpi,
    vierekkäisten värien välissä sekoitussuhde ditherinä. Rampissa vierekkäin kannattaa olla
    valoisuudeltaan lähekkäisiä värejä (Colodore-parit 6/9, 11/2, 8/4, 14/12, 10/5, 15/3), jolloin
    kuvio ei näy kirkkausvaihteluna vaan uutena sävynä."""
    h, w = tone.shape
    mh, mw = matrix.shape
    thr = np.tile(matrix, (h // mh + 2, w // mw + 2))[oy:oy + h, ox:ox + w]
    pos = np.clip(tone, 0, 1) * (len(ramp) - 1)
    i = np.minimum(pos.astype(int), len(ramp) - 2)
    frac = pos - i
    if band is not None:                                               # leveä tasainen kaista, kapea dithersiirtymä
        frac = np.clip((frac - 0.5) / band + 0.5, 0, 1)
    r = np.array(ramp)
    out = np.where(frac > thr, r[i + 1], r[i])
    if accent > 0:
        # kolmas sävy harvoina 1-2 px pätkinä (eri vaiheessa kuin pääkuvio): pinnassa on aina kolme
        # valoisuustasoa, ja kuvio pysyy säännöllisenä vaakaviivana
        thr2 = np.roll(np.roll(thr, 2, axis=0), 4, axis=1)
        third = np.where(frac > 0.5, r[np.minimum(i + 2, len(ramp) - 1)], r[np.maximum(i - 1, 0)])
        out = np.where(thr2 < accent, third, out)
    return out.astype(np.int16)


def fill_poly(img: np.ndarray, pts, color: int) -> None:
    """Täytetty monikulmio MC-pikselikoordinaateissa."""
    from PIL import Image, ImageDraw
    im = Image.new("1", (img.shape[1], img.shape[0]), 0)
    ImageDraw.Draw(im).polygon([(float(x), float(y)) for x, y in pts], fill=1)
    img[np.array(im, bool)] = color


def ramp_shades(tone: np.ndarray, ramp: tuple, accent: float = 0.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pinta rampista: (perus liukuvärinä ditherillä, varjosävy askel alempana, valosävy askel ylempänä).
    Paikallisesti käytössä on vain kolme vierekkäistä rampin väriä, joten solun värit pysyvät rajoissa."""
    r = np.array(ramp)
    pos = np.clip(tone, 0, 1) * (len(ramp) - 1)
    i = np.minimum(pos.astype(int), len(ramp) - 2)
    shade = r[np.maximum(i - 1, 0)]
    base = odither(tone, ramp)
    h, w = tone.shape
    thr2 = np.roll(np.roll(np.tile(DASH, (h // 4 + 1, w // 8 + 1))[:h, :w], 2, axis=0), 4, axis=1)
    base = np.where(thr2 < accent, shade, base).astype(np.int16)       # harvat varjopätkät: 3 sävyä pinnassa
    return base, shade, r[i + 1]


def banded_sky(h: int, w: int, ramp: tuple, bands: tuple, edge: int = 4, accent: float = 0.0) -> np.ndarray:
    """Yötaivas isoina rauhallisina kaistoina: bands = ((alkurivi, sävy), ...) ylhäältä alas; kaistan
    sisällä sävy on vakio (sama katkoviivatiheys koko kaistalla), kaistojen välissä vain edge rivin
    siirtymävyö."""
    yy = np.arange(h)[:, None].astype(float)
    tone = np.full((h, 1), bands[0][1])
    for (y0, t0), (y1, t1) in zip(bands, bands[1:]):
        f = np.clip((yy - (y1 - edge / 2)) / max(edge, 1), 0, 1)
        tone = np.where(yy >= y1 - edge / 2, t0 + (t1 - t0) * f, tone)
    return odither(np.repeat(np.clip(tone, 0, 1), w, axis=1), ramp, accent=accent, band=None)
