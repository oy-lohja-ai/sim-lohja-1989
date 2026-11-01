"""Greetsien lenkkeilijä ja koira: hires-sprite (24 x 21, ei laajennusta) tien riveillä pyöräilijän tapaan, FRAMES
kehystä yhdestä askelparista.

Host laskee vain staattisen datan. 3/4-kulma eteen oikealle kuten pyöräilijällä: kaukainen jalka ja käsi ohuina
vartalon takana, lähin jalka kahden pikselin levyisenä. Juoksija nojaa eteen, jalat seuraavat askelrataa (tukivaihe
maassa taaksepäin, heilahdus ilmassa kantapää ylhäällä, polvi kahden luun IK:lla), vartalo pomppaa askeleen
tahdissa. Lähin käsi pitää hihnaa, jonka toisessa päässä ravaava koira (ristiaskel, kaksi askelta juoksijan
askeleella). Yksi väri (vastavalo kuten pyöräilijä).
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

FRAMES = 8                    # askelpari (muisti: VIC-pankin 1 spritetila)
W, H = 24, 21
STRIDE = 14.0                 # askelparin pituus hires px (kahden askeleen matka maata vasten)

GROUND = 20                   # jalkapohjat
HIP = (5.5, 10.5)
SHOULDER = (6.5, 5.0)

# pää ja vartalo käsin pikseleinä (nojaa eteen; käsivarret ja jalat lasketaan)
UPPER = """
.......##...
......####..
......####..
.......##...
.....####...
.....####...
.....####...
....####....
....###.....
....###.....
....###.....
"""
THIGH, SHIN = 5.2, 5.2
UARM, FARM = 2.8, 2.8
HAND = (11.5, 8.5)            # hihnakäsi (lähin), heiluu vain vähän

# koira: vartalo, pää ja jalkojen kiinnityskohdat (oikealle)
DOG_BODY = (14.5, 14.0, 20.5, 16.0)
DOG_LEGS = (15.2, 16.3, 19.2, 20.2)      # takajalat 15/16, etujalat 19/20
DOG_COLLAR = (20.0, 13.5)


def knee(hip, foot, a_len, b_len, forward=1):
    """Kahden luun IK: nivel (polvi tai kyynärpää) suuntaan forward (+1 = eteen, -1 = taakse)."""
    dx, dy = foot[0] - hip[0], foot[1] - hip[1]
    L = max(min(math.hypot(dx, dy), a_len + b_len - 0.01), 0.01)
    a = (a_len ** 2 - b_len ** 2 + L ** 2) / (2 * L)
    h = math.sqrt(max(a_len ** 2 - a ** 2, 0.0))
    ux, uy = dx / L, dy / L
    px, py = -uy, ux
    if px * forward < 0:
        px, py = -px, -py
    return hip[0] + ux * a + px * h, hip[1] + uy * a + py * h


def foot(phase: float, hip) -> tuple[float, float]:
    """Askelrata: tukivaihe (sin > 0) maassa taaksepäin, heilahdus ilmassa eteen kantapää ylhäällä."""
    s, c = math.sin(phase), math.cos(phase)
    x = hip[0] + 0.5 + 3.6 * c
    if s >= 0:
        return x, GROUND
    return x - 1.2 * (-s), GROUND - 4.2 * (-s) ** 0.8


def raster(t: float) -> np.ndarray:
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)

    def line(a, b, w=1):
        d.line([a, b], fill=1, width=w)

    ph = 2 * math.pi * t
    bob = -1 if abs(math.cos(ph)) > 0.6 else 0              # lentovaihe ylhäällä (kaksi kertaa askelparissa)
    hip = (HIP[0], HIP[1] + bob)
    sh = (SHOULDER[0], SHOULDER[1] + bob)

    # kaukainen jalka ja käsi (vartalon takana)
    f = foot(ph + math.pi, hip)
    k = knee(hip, f, THIGH, SHIN)
    line(hip, k)
    line(k, f)
    line(f, (f[0] + 1, f[1]))
    sw = 0.9 * math.cos(ph)                                  # kaukainen käsi heiluu jalan vastavaiheessa
    hand = (sh[0] + 3.0 * math.sin(sw) + 0.5, sh[1] + 4.0)
    e = knee(sh, hand, UARM, FARM, -1)
    line(sh, e)
    line(e, hand)

    # vartalo ja pää
    up = np.array([[c == "#" for c in r] for r in UPPER.strip().splitlines()], np.uint8)
    a = np.asarray(img).copy()
    y0 = 1 + bob
    a[y0:y0 + up.shape[0], :up.shape[1]] |= up
    img = Image.fromarray(a)
    d = ImageDraw.Draw(img)

    # lähin jalka
    f = foot(ph, hip)
    k = knee(hip, f, THIGH, SHIN)
    line(hip, k, 2)
    line(k, f, 2)
    line(f, (f[0] + 1.5, f[1]))

    # koira: ravi, kaksi askelta juoksijan askeleella; pää ja häntä pomppaavat
    dp = 2 * ph
    dbob = -0.6 * abs(math.sin(dp))
    x0, y0, x1, y1 = DOG_BODY
    d.ellipse([x0, y0 + dbob, x1, y1 + dbob], fill=1)
    d.polygon([(19.5, 13.5 + dbob), (21.0, 11.0 + dbob), (22.5, 11.5 + dbob), (23.5, 13.0 + dbob),
               (21.5, 14.2 + dbob)], fill=1)                    # pää ja kuono
    line((21.0, 11.0 + dbob), (20.6, 9.8 + dbob))               # korva
    line((14.6, 14.4 + dbob), (13.0, 12.0 + dbob + 0.8 * math.sin(dp)))   # häntä
    for j, lx in enumerate(DOG_LEGS):
        pair = (0, 1, 1, 0)[j]                                   # ristiaskel: takavasen + etuoikea
        a = dp + math.pi * pair
        fx = lx + 1.4 * math.cos(a)
        fy = GROUND - (1.2 * -math.sin(a) if math.sin(a) < 0 else 0.0)
        line((lx, 15.5 + dbob), (fx, fy))

    # hihna: lähin käsi (vartalon edessä) koiran kaulaan, löysä kaari
    hand = (HAND[0] + 0.4 * math.sin(ph), HAND[1] + bob)
    e = knee(sh, hand, UARM + 0.4, FARM + 0.4, -1)
    line(sh, e, 2)
    line(e, hand)
    cx, cy = DOG_COLLAR[0], DOG_COLLAR[1] + dbob
    pts = []
    for i in range(9):
        u = i / 8
        sag = 2.2 * 4 * u * (1 - u)
        pts.append((hand[0] + (cx - hand[0]) * u, hand[1] + (cy - hand[1]) * u + sag))
    d.line(pts, fill=1, width=1)
    return np.asarray(img).astype(np.uint8)


def frames() -> list[np.ndarray]:
    return [raster(i / FRAMES) for i in range(FRAMES)]


def blocks() -> list[bytes]:
    out = []
    for img in frames():
        b = bytearray()
        for r in range(H):
            for c in range(3):
                v = 0
                for bit in range(8):
                    v = v << 1 | int(img[r, c * 8 + bit])
                b.append(v)
        b.append(0)
        out.append(bytes(b))
    return out


if __name__ == "__main__":
    import sys
    fs = frames()
    sheet = np.full((H + 2, (W + 4) * len(fs)), 170, np.uint8)
    for i, f in enumerate(fs):
        sheet[1:H + 1, i * (W + 4) + 2:i * (W + 4) + 2 + W][f > 0] = 0
    z = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    Image.fromarray(sheet).resize((sheet.shape[1] * z, sheet.shape[0] * z), Image.NEAREST).save(sys.argv[1])
