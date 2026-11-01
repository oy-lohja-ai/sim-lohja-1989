"""Lohjantähti 1991 sinisellä hetkellä (L-ruudut 8-9).

Muodot todellisen rakennuksen mukaan: pitkä kolmikerroksinen rapattu
rakennus (vaaleanpunainen rappaus, ramppi 9/2/10/15/1), katutasossa pylväskäytävä, neliöikkunat
riveissä, kulmassa lasinen torni kaksi kerrosta muuta korkeampi vinolla katolla. Ei tähteä taivaalla.

Kuvakulma (ei tasokuva): torin akselilta Sokeripalan suunnasta (tori.CAMERA): sama kamerapaikka kuin Hillnerin talolla 1964,
  lasitornin kulma samassa kohdassa ruutua. Rakennus vastavalossa ja varjossa, rajautuu reunojen yli;
  lasitorni hehkuu keltaisena (demon ensimmäinen keltainen, purkajan merkki) ja heijastuu märkään
  graniittiin. Etualalla valaisinpylväs.
Täysi ruutu MC-bittikarttana; pinnat liukuväreinä katkoviivaditherillä.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from .house import reduce_cells
from .persp import Camera, Tracer
from .pixel import (banded_sky, BLACK, BLUE, BROWN, DGREY, GREEN, GREY, LBLUE, LGREY, LRED, ORANGE, RED, WHITE, YELLOW, odither,
                    ramp_shades)

H, W = 200, 160
X1 = 20.0                                # kulma (sama kuin Hillnerin talon kulma)
LEN, DEP = 92.0, 84.0                    # julkisivun pituus, sivun syvyys
HB = 12.6                                # päärakennuksen räystäs
TW, TD, TH0, TH1 = 8.0, 8.0, 19.5, 23.5  # lasitornin leveys, syvyys, katon matala ja korkea reuna
ARC = 3.6                                # pylväskäytävän korkeus
PLASTER = (BROWN, RED, LRED, LGREY, WHITE)   # rappaus 9/2, 2/10, 10/15, 15/1

M_SKY, M_GROUND, M_FRONT, M_SIDE, M_TOWER_F, M_TOWER_S, M_TOWER_T = range(7)


def trace(cam: Camera) -> Tracer:
    tr = Tracer(cam)
    d, take = tr.d, tr.take
    t, p = cam.plane(d, 1, 0.0)
    take(t, np.ones((H, W), bool), M_GROUND, p[..., 0], p[..., 2], p)
    t, p = cam.plane(d, 2, 0.0)                                         # julkisivu tornin vasemmalla
    m = (p[..., 0] >= X1 - LEN) & (p[..., 0] <= X1 - TW) & (p[..., 1] >= 0) & (p[..., 1] <= HB)
    take(t, m, M_FRONT, p[..., 0] - (X1 - LEN), p[..., 1], p)
    t, p = cam.plane(d, 0, X1)                                          # sivu tornin takana
    m = (p[..., 2] <= -TD) & (p[..., 2] >= -DEP) & (p[..., 1] >= 0) & (p[..., 1] <= HB)
    take(t, m, M_SIDE, -p[..., 2], p[..., 1], p)
    # lasitorni kulmassa: etu- ja sivupinta, vino katto (matalampi takana vasemmalla)
    def top(x, z):
        return TH0 + (TH1 - TH0) * np.clip((x - (X1 - TW)) / TW, 0, 1)
    t, p = cam.plane(d, 2, 0.0)
    m = (p[..., 0] >= X1 - TW) & (p[..., 0] <= X1) & (p[..., 1] >= 0) & (p[..., 1] <= top(p[..., 0], 0))
    take(t, m, M_TOWER_F, p[..., 0] - (X1 - TW), p[..., 1], p)
    t, p = cam.plane(d, 0, X1)
    m = (p[..., 2] <= 0) & (p[..., 2] >= -TD) & (p[..., 1] >= 0) & (p[..., 1] <= TH1)
    take(t, m, M_TOWER_S, -p[..., 2], p[..., 1], p)
    return tr


NIGHT_RAMP = (BLACK, BLUE, DGREY, LBLUE)  # 0/6, 6/11, 11/14: vierekkäin <= 2 valoisuustasoa


def _sky(cam: Camera) -> np.ndarray:
    """Sininen hetki: isot rauhalliset kaistat. Ylhäällä lähes tasainen tumma (0 ja harva 6), alas
    kohti horisonttia vaalenee portaittain, kaistojen välissä kapea siirtymävyö."""
    h = cam.h
    bands = ((0, 0.0), (int(h * 0.30), 1 / 3), (int(h * 0.55), 2 / 3), (int(h * 0.78), 1.0))
    return banded_sky(h, cam.w, NIGHT_RAMP, bands, edge=16)


def _plaster(U, V, m, lit: float, img, front: bool):
    """Rappaus varjossa (vastavalo): liukuu alhaalta tummasta ylös vaaleampaan, räystäslista valossa,
    katutasossa pylväät ja pimeä käytävä valaistuin liikkein, kerroksissa neliöikkunat (osa valaistu 15/10)."""
    tone = 0.04 + 0.16 * (V / HB) + (0.04 if front else -0.02) + 0.03 * np.sin(U * 0.4)
    base, shade, light = ramp_shades(tone, PLASTER)
    img[m] = base[m]
    cor = m & (V > HB - 0.35)
    img[cor] = light[cor]
    img[m & (V > HB - 0.55) & (V <= HB - 0.35)] = BLACK
    # pylväskäytävä: pylväät 6 m välein, välissä pimeä ja valaistu liike
    col = (U % 6.0) < 0.9
    arc = m & (V < ARC)
    img[arc & ~col] = BLACK
    shop = arc & ~col & (V > 0.4) & (V < ARC - 0.9) & ((U % 6.0) > 1.4) & ((U % 6.0) < 5.4)
    img[shop] = odither(np.clip(0.35 + 0.35 * (V / ARC) + 0.1 * np.sin(U * 2.1), 0, 1), (BLACK, BROWN, ORANGE, LRED))[shop]
    img[shop & (((U % 6.0) % 1.0) < 0.12)] = BLACK                    # näyteikkunan puitteet
    goods = shop & (V < 1.2) & ((np.floor(U * 3) % 2) == 0)
    img[goods] = BLACK                                                 # hyllyt ja tavarat siluettina
    img[arc & col] = base[arc & col]
    img[arc & col & ((U % 6.0) > 0.7)] = shade[arc & col & ((U % 6.0) > 0.7)]
    # neliöikkunat kolmessa kerroksessa, joka ikkuna erilainen: pimeä, sininen heijastus tai valaistu
    rnd = (np.sin(np.floor(U / 3.0) * 12.9898 + np.floor(V / 3.0) * 78.233) * 43758.5453) % 1
    for v0 in (4.6, 7.6, 10.4):
        win = m & (V > v0) & (V < v0 + 1.5) & ((U % 3.0) > 0.75) & ((U % 3.0) < 2.25)
        img[win] = BLACK
        lit_w = win & (rnd < 0.28 * lit)
        img[lit_w] = odither(np.clip(0.7 - 0.3 * ((V - v0) / 1.5), 0, 1), (LRED, LGREY, WHITE))[lit_w]
        refl = win & (rnd > 0.75) & ((((U % 3.0) - 0.75) + (V - v0)) % 1.2 < 0.25)
        img[refl] = BLUE
        img[m & (V > v0 - 0.12) & (V <= v0) & ((U % 3.0) > 0.6) & ((U % 3.0) < 2.4)] = LGREY   # ikkunalauta


FLOOR_H = 3.3
# kerrosten luonne alhaalta ylös: (sisävalon sävy 0-1, ihmisiä, kasveja, heijastusta)
FLOOR_MOOD = [(0.72, 3, 0, 0.0), (0.58, 1, 0, 0.0), (0.80, 4, 0, 0.0), (0.50, 0, 0, 0.0), (0.66, 2, 0, 0.0),
              (0.45, 1, 0, 0.6), (0.40, 0, 0, 1.0)]                    # heijastus vain kahdessa ylimmässä


def _tower(U, V, m, lit: float, img, front: bool):
    """Lasitorni pikselitaitona: kerroslaatat (tumma laatta, alla kattovalojen
    rivi), sisätilat kerroksittain eri sävyisinä (lämmin 8/7/1), ihmisten ja kasvien siluetit, puitteiden
    rytmi 1,2 m (musta profiili + reunavalo), ylemmissä kerroksissa taivaan ja vastapäisten talojen
    heijastus (6/14, valkoinen Sokeripala), kulmassa reunavalo. lit: kerrokset syttyvät alhaalta ylös."""
    floor = np.clip(np.floor(V / FLOOR_H).astype(int), 0, len(FLOOR_MOOD) - 1)
    fv = (V % FLOOR_H) / FLOOR_H                                       # 0 lattia .. 1 katto
    on = floor < lit * len(FLOOR_MOOD)
    tone = np.array([f[0] for f in FLOOR_MOOD])[floor]
    refl = np.array([f[3] for f in FLOOR_MOOD])[floor]
    # sisävalo: kirkkain katon alla (valaisimet), tummuu lattiaa kohti, kerroksittain eri sävy
    inner = np.clip(tone + 0.2 - 0.3 * (1 - fv) + 0.08 * np.sin(U * 1.7 + floor), 0, 1)
    glass = odither(inner, (BLACK, BROWN, ORANGE, YELLOW))             # yksi lämmin perhe: ruskea-oranssi-keltainen
    img[m & on] = glass[m & on]
    # kattovalojen rivi laatan alla: lyhyet valkoiset pätkät
    lamps = m & on & (fv > 0.80) & (fv < 0.86) & (((U * 2.0) % 1) < 0.45)
    img[lamps] = YELLOW
    # ihmiset ja kasvit siluetteina (eri kerroksissa eri määrä)
    for k, (_, people, plants, _) in enumerate(FLOOR_MOOD):
        fm = m & on & (floor == k)
        for p in range(people):
            u0 = (0.9 + p * 2.3 + k * 0.7) % (TW - 0.6) + 0.3
            body = fm & (np.abs(U - u0) < 0.22) & (fv > 0.05) & (fv < 0.52)
            head = fm & (np.abs(U - u0) < 0.13) & (fv >= 0.52) & (fv < 0.62)
            img[body | head] = BLACK
        for p in range(plants):
            u0 = (2.1 + p * 2.9 + k * 1.3) % (TW - 0.6) + 0.3
            leaf = fm & (((U - u0) / 0.35) ** 2 + ((fv - 0.25) / 0.2) ** 2 < 1)
            img[leaf] = GREEN
            img[leaf & (fv > 0.3)] = BLACK
    # heijastus ylemmissä kerroksissa: taivas ja vastapäisten talojen siluetit (valkoinen Sokeripala)
    rmix = m & on & (refl > 0) & ((fv + 0.3 * refl) > 0.65 - 0.4 * refl)
    sk = odither(np.clip(0.3 + 0.5 * fv, 0, 1), (BLACK, BLUE, LBLUE, WHITE))
    img[rmix] = sk[rmix]
    sokeri = rmix & (np.abs(U - (TW * 0.35)) < 0.9) & (fv < 0.55)
    img[sokeri] = WHITE
    img[sokeri & (((fv * 9) % 1) < 0.3)] = BLACK                       # Sokeripalan nauhaikkunat
    # valaisematon lasi: tumma taivasheijastus
    dark = odither(np.clip(0.15 + 0.4 * (V / TH1), 0, 1), (BLACK, BLUE, LBLUE))
    img[m & ~on] = dark[m & ~on]
    # puitteet ja laatat
    mull = m & ((U % 1.2) < 0.1)
    img[mull] = BLACK
    edge = m & ((U % 1.2) >= 0.1) & ((U % 1.2) < 0.16) & on
    img[edge] = ORANGE                                                 # profiilin reunavalo
    slab = m & (fv < 0.07)
    img[slab] = BLACK
    img[m & (fv >= 0.07) & (fv < 0.1)] = BROWN if lit > 0 else BLACK
    corner = m & ((U > TW - 0.12) if front else (U < 0.12))
    img[corner] = WHITE if lit > 0 else LBLUE                          # kulman reunavalo
    img[m & (V < ARC) & ((U % 1.2) > 0.12)] = BLACK if lit < 0.15 else ORANGE


def _ground(cam: Camera, X, m, lit: float) -> np.ndarray:
    """Märkä punagraniitti sinisellä hetkellä: tumma liukuväri, lasitornin keltainen heijastus pystyinä
    katkoviivoina tornin alla, valaisinpylvään valokeila."""
    gx, gz = X[..., 0], X[..., 2]
    dist = np.hypot(gx - cam.pos[0], gz - cam.pos[2])
    tone = 0.26 + 0.50 * np.clip((dist - 3) / 45, 0, 1) + 0.06 * np.sin(gx * 0.21) * np.cos(gz * 0.17)
    tone = tone + 0.38 * np.clip(1 - gz / 5.0, 0, 1) * (gz > 0)     # liikkeiden valo lammikkona kiveyksellä
    tone = tone - 0.14 * ((((gz / 2.5) % 1) < 0.1) | (((gx / 2.5) % 1) < 0.1)) * (dist < 40)   # laattarivit
    img = odither(tone, (BLACK, DGREY, RED, GREY))
    refl = m & (gx > X1 - TW - 1.0) & (gx < X1 + 1.0) & (gz > 0.5) & (gz < 25) & (lit > 0)
    rows = (np.arange(H)[:, None] % 3) == 0
    img[refl & rows] = YELLOW
    img[refl & ~rows & ((np.arange(W)[None, :] % 4) == 0)] = ORANGE
    return img


def _lamp(img, cam: Camera, pos) -> None:
    """Valaisinpylväs etualalla: musta pylväs ja lyhty, valo 15/1."""
    (x0, y0), (x1, y1) = cam.project(pos), cam.project((pos[0], pos[1] + 5.5, pos[2]))
    for y in range(int(max(y1, 0)), int(min(y0, H))):
        for dx in (-1, 0, 1):
            x = int(round(x0)) + dx
            if 0 <= x < W:
                img[y, x] = BLACK
    hx, hy = int(round(x1)), int(round(y1))
    for dy in range(-4, 2):
        for dx in range(-3, 4):
            if 0 <= hy + dy < H and 0 <= hx + dx < W:
                img[hy + dy, hx + dx] = BLACK
    for dy in range(-2, 1):
        for dx in range(-2, 3):
            if 0 <= hy + dy < H and 0 <= hx + dx < W:
                img[hy + dy, hx + dx] = WHITE if dy == -1 else LGREY


@lru_cache(maxsize=16)
def render(cam: Camera, lit: float = 1.0, lamp: bool = True) -> np.ndarray:
    tr = trace(cam)
    mat, U, V, X = tr.mat, tr.U, tr.V, tr.X
    img = _sky(cam)
    g = mat == M_GROUND
    img[g] = _ground(cam, X, g, lit)[g]
    _plaster(U, V, mat == M_FRONT, lit, img, True)
    _plaster(U, V, mat == M_SIDE, lit, img, False)
    _tower(U, V, mat == M_TOWER_F, lit, img, True)
    _tower(U, V, mat == M_TOWER_S, lit, img, False)
    house = mat >= M_FRONT
    p = np.pad(house, 1, constant_values=False)
    img[house & ~(p[1:-1, 2:] & p[1:-1, :-2] & p[2:, 1:-1] & p[:-2, 1:-1])] = BLACK
    if lamp:
        _lamp(img, cam, (X1 + 9.0, 0.0, 22.0))
    render.changed = reduce_cells(img)
    return img
