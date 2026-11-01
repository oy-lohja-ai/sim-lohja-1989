"""Greetsien pyöräilijä: hires-sprite (24 x 21, ei laajennusta) tien riveillä, FRAMES kehystä yhdestä kammen
kierroksesta.

Host laskee vain staattisen datan. Piirros on pikselitasolla (ei ylinäytteistystä): 3/4-kulma eteen oikealle,
joten pyörät ovat soikioita (takapyörä kauempana ja ylempänä) ja kaukainen
jalka on lähimmän takana. Kampi kiertää soikiota (kammen taso kääntynyt), jalat seuraavat polkimia (polvi
kahden luun IK:lla), pyörien pinnat kiertävät GEAR kertaa kammen kierroksella. Yksi väri (vastavalo: ilta-aurinko
on puiden takana). MC (12 px leveä) olisi liian karkea: pyörä 3 pikseliä.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

FRAMES = 12                   # kammen kierros (muisti: VIC-pankin 1 spritetila täynnä)
GEAR = 2.5                    # pyörän kierrosta kammen kierroksella
W, H = 24, 21

# ajajan ylävartalo, pää ja lähin käsivarsi käsin pikseleinä (kaukainen käsi vartalon takana)
UPPER = """
..............###.......
.............#####......
.............#####......
.........#####.##.......
.......########.........
......#########.........
......########.#........
......######....#.......
.......####......#......
"""
REAR, R_REAR = (5.0, 14.5), (3.0, 4.0)        # keskipiste ja säteet (x, y): kauempana, pienempi ja ylempänä
FRONT, R_FRONT = (18.5, 15.5), (3.0, 4.5)
BB = (11.5, 14.5)                              # keskiö
CRANK = (2.5, 1.7)                             # kammen soikio (3/4: taso kääntynyt)
SEAT = (8.0, 9.0)
HEADTUBE = (16.5, 9.0)
HIP = (8.5, 8.0)
THIGH, SHIN = 5.0, 5.2
SPOKES = 1                                     # halkaisijoita pyörää kohden


def knee(hip, foot):
    dx, dy = foot[0] - hip[0], foot[1] - hip[1]
    L = min(math.hypot(dx, dy), THIGH + SHIN - 0.01)
    a = (THIGH ** 2 - SHIN ** 2 + L ** 2) / (2 * L)
    h = math.sqrt(max(THIGH ** 2 - a ** 2, 0.0))
    ux, uy = dx / L, dy / L
    px, py = -uy, ux                                   # kohtisuora: polvi eteen (x+)
    if px < 0:
        px, py = -px, -py
    return hip[0] + ux * a + px * h, hip[1] + uy * a + py * h


def raster(phase: float) -> np.ndarray:
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)

    def line(a, b, w=1):
        d.line([a, b], fill=1, width=w)

    ca = 2 * math.pi * phase
    wa = ca * GEAR
    pedal = lambda a: (BB[0] + CRANK[0] * math.cos(a), BB[1] + CRANK[1] * math.sin(a))
    near, far = pedal(ca), pedal(ca + math.pi)
    k = knee(HIP, far)                                  # kaukainen jalka
    line(k, far)
    line(HIP, k)
    for (cx, cy), (rx, ry) in ((REAR, R_REAR), (FRONT, R_FRONT)):   # pyörät
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=1)
        for j in range(SPOKES):
            t = wa + j * math.pi / SPOKES               # myötäpäivään (ajaa oikealle)
            sx, sy = (rx - 1) * math.cos(t), (ry - 1) * math.sin(t)
            line((cx - sx, cy - sy), (cx + sx, cy + sy))
    line(REAR, BB)                                      # runko
    line(REAR, SEAT)
    line(SEAT, BB)
    line(SEAT, HEADTUBE)
    line(HEADTUBE, BB)
    line(HEADTUBE, FRONT)
    up = np.array([[c == "#" for c in r] for r in UPPER.strip().splitlines()], np.uint8)
    a = np.asarray(img).copy()
    a[:up.shape[0]] |= up
    img = Image.fromarray(a)
    d = ImageDraw.Draw(img)
    k = knee(HIP, near)                                 # lähin jalka ja kampi
    line(HIP, k, 2)
    line(k, near, 2)
    line(BB, near)
    line(near, (near[0] + 1, near[1]))
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
    n = int(sys.argv[2]) if len(sys.argv) > 2 else len(fs)
    sheet = np.full((H + 2, (W + 4) * n), 170, np.uint8)
    for i, f in enumerate(fs[:n]):
        sheet[1:H + 1, i * (W + 4) + 2:i * (W + 4) + 2 + W][f > 0] = 0
    z = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    Image.fromarray(sheet).resize((sheet.shape[1] * z, sheet.shape[0] * z), Image.NEAREST).save(sys.argv[1])
