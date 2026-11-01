"""Iso bulldozer romahduksen etualalle: spritepino 4 x 2
MC-spriteä = 48 x 42 MC-px laajentamattomana. Kone on etualalla vasemmassa alakulmassa samassa
3/4-kulmassa kuin purkutalo ja puskee kohti talon etuseinää (oikealle ylös); näkyvät takapää,
vasen kylki telaketjuineen, konepeitto, ohjaamo ja pakoputki, ja puskulevy kauimpana.

Kone mallinnetaan laatikoina metreinä ja projisoidaan 3/4-akseleille (eteenpäin oikealle ylös,
vasemmalle alas vasemmalle, ylös), näkyvät pinnat piirretään takaa eteen. Roolit:
%10 = runko (spritekohtainen väri, suositus purkajan keltainen 7), %01 = 9 varjo, tummat osat ja
ääriviiva (jaettu), %11 = 12 teräs: telan kynnet, pyörät, terä, ikkunan heijastus (jaettu).
Varjopinnat 2 rivin ruudukkoditherinä (kestää rivien tuplauksen). Telan kynnet liikkuvat kolmessa
vaiheessa (alarivin 4 spriteä per vaihe).
"""
from __future__ import annotations

import numpy as np

from .pixel import fill_poly

W, H = 48, 42
DARK, BODY, STEEL = 1, 2, 3
# projektio: MC-px ja rivit metriä kohti (MC-pikseli on kaksi kertaa leveä)
FX, FY = 7.5, -1.2                       # eteenpäin: oikealle, hieman ylös (pakenee kohti seinää)
LX, LY = -1.5, 2.5                       # vasemmalle (kameraa kohti): alas, hieman vasemmalle
UY = 8.8                                 # ylös
OX, OY = 6.0, 33.3                       # takaoikean pohjakulman paikka


def P(f: float, l: float, u: float) -> tuple[float, float]:
    return OX + f * FX + l * LX, OY + f * FY + l * LY - u * UY


def _box(img, f0, f1, l0, l1, u0, u1, top=BODY, side=BODY, rear=None):
    """Laatikon kameraan näkyvät pinnat: takapää (f0), vasen kylki (l1) ja katto (u1)."""
    if rear is not None:
        fill_poly(img, [P(f0, l0, u0), P(f0, l1, u0), P(f0, l1, u1), P(f0, l0, u1)], rear)
    fill_poly(img, [P(f0, l1, u0), P(f1, l1, u0), P(f1, l1, u1), P(f0, l1, u1)], side)
    fill_poly(img, [P(f0, l0, u1), P(f1, l0, u1), P(f1, l1, u1), P(f0, l1, u1)], top)


SHADE = 4                                # väliarvo: varjopinta ditheröidään lopuksi (runko/tumma)


def _track(img, l0, l1, phase: int, near: bool) -> None:
    """Telaketju: kylki tummana (9), päällä kynnet 12, pyörät 12-renkaina; vaihe siirtää kynsiä."""
    f0, f1, u1 = 0.1, 4.3, 0.95
    _box(img, f0, f1, l0, l1, 0.0, u1, top=DARK, side=DARK, rear=DARK)
    if not near:
        return
    step = 0.36
    for k in range(-1, 14):
        f = f0 + (k + phase / 3) * step
        if f0 < f < f1:                                                # kynnet kyljen ylä- ja alareunassa
            for u in (0.05, u1 - 0.08):
                x, y = P(f, l1, u)
                img[int(round(y)), int(round(x))] = STEEL
    for f in (0.55, 1.45, 2.35, 3.25, 3.95):                           # telapyörät
        cx, cy = P(f, l1, 0.42)
        for a in np.linspace(0, 2 * np.pi, 14, endpoint=False):
            x, y = cx + 1.6 * np.cos(a), cy + 1.6 * np.sin(a) * 1.0
            img[int(round(y)), int(round(x))] = STEEL
        img[int(round(cy)), int(round(cx))] = STEEL


def render(phase: int = 0) -> np.ndarray:
    """Roolikartta (42, 48): 0 läpinäkyvä, 1 = 9, 2 = runko, 3 = 12."""
    img = np.zeros((H, W), np.int16)
    _track(img, 0.0, 0.6, phase, near=False)                           # kaukainen tela
    # puskulevy kauimpana: yläreuna ja vasen pää näkyvät konepeiton takaa, terä 12
    fill_poly(img, [P(4.45, -0.3, 0.0), P(4.45, 3.3, 0.0), P(4.45, 3.3, 1.35), P(4.45, -0.3, 1.35)], BODY)
    fill_poly(img, [P(4.45, -0.3, 1.35), P(4.65, -0.3, 1.45), P(4.65, 3.3, 1.45), P(4.45, 3.3, 1.35)], STEEL)
    fill_poly(img, [P(4.45, 3.1, 0.0), P(4.45, 3.3, 0.0), P(4.45, 3.3, 1.35), P(4.45, 3.1, 1.35)], SHADE)
    # työntövarret levyyn telan yläpuolella
    fill_poly(img, [P(2.6, 2.7, 0.7), P(4.45, 2.9, 0.5), P(4.45, 2.9, 0.75), P(2.6, 2.7, 0.95)], SHADE)
    # runko ja konepeitto: katto valossa, kylki valossa, takapää varjossa; jäähdyttimen säleikkö ei näy
    _box(img, 0.35, 4.1, 0.5, 2.5, 0.6, 1.75, top=BODY, side=BODY, rear=SHADE)
    for f in np.arange(1.9, 3.9, 0.45):                                # konepeiton tuuletusraot kyljessä
        a, b = P(f, 2.5, 1.2), P(f + 0.25, 2.5, 1.2)
        fill_poly(img, [a, b, (b[0], b[1] + 1.2), (a[0], a[1] + 1.2)], DARK)
    # pakoputki ja sadehattu
    _box(img, 2.75, 2.92, 1.25, 1.42, 1.75, 2.75, top=DARK, side=DARK, rear=DARK)
    x, y = P(2.8, 1.35, 2.78)
    img[int(y), int(x) - 1:int(x) + 2] = STEEL
    # ohjaamo (ROPS): runko, ikkunat tummina, heijastus 12, katto valossa
    _box(img, 0.3, 1.75, 0.65, 2.35, 1.75, 3.15, top=BODY, side=BODY, rear=SHADE)
    # sivuikkuna heijastaa taivasta (12), kuljettaja tummana siluettina, karmit rungon väriä
    fill_poly(img, [P(0.5, 2.35, 2.1), P(1.55, 2.35, 2.1), P(1.55, 2.35, 2.95), P(0.5, 2.35, 2.95)], STEEL)
    hx, hy = P(0.95, 2.35, 2.1)
    fill_poly(img, [(hx - 1.5, hy), (hx + 1.5, hy), (hx + 1.2, hy - 3.5), (hx + 0.2, hy - 5.5), (hx - 1.0, hy - 4.0)], DARK)
    img[int(P(1.0, 2.35, 2.5)[1]), int(P(1.0, 2.35, 2.5)[0]):int(P(1.55, 2.35, 2.5)[0])] = DARK
    # lähin tela viimeisenä
    _track(img, 2.45, 3.05, phase, near=True)
    # takapään ripperin piikki
    fill_poly(img, [P(-0.25, 1.3, 0.2), P(0.1, 1.3, 0.5), P(0.1, 1.5, 0.5), P(-0.25, 1.5, 0.2)], STEEL)
    # varjopinnat: runko/tumma 2 rivin ruudukossa
    yy, xx = np.mgrid[0:H, 0:W]
    grid = (((yy // 2) + xx) % 2) == 0
    img[(img == SHADE) & grid] = DARK
    img[img == SHADE] = BODY
    # ääriviiva: rungon reunapikselit tummiksi (spritessä ei ole mustaa)
    body = img > 0
    p = np.pad(body, 1)
    rim = body & ~(p[2:, 1:-1] & p[:-2, 1:-1] & p[1:-1, 2:] & p[1:-1, :-2])
    img[rim & (img == BODY)] = DARK
    return img


def blade_hit() -> tuple[int, int]:
    """Puskulevyn terän keskikohta (x, y) MC-px spritepinon vasemmasta yläkulmasta: isku kohdistetaan tähän."""
    x, y = P(4.6, 1.5, 0.1)
    return int(round(x)), int(round(y))


def split(img: np.ndarray) -> list[list[np.ndarray]]:
    """2 riviä x 4 spriteä (21 x 12)."""
    return [[img[r * 21:(r + 1) * 21, c * 12:(c + 1) * 12].copy() for c in range(4)] for r in range(2)]


def collapse_dozer() -> dict:
    """body: 2 x 4 roolitaulukkoa (vaihe 0); tracks: 3 vaihetta x alarivin 4 roolitaulukkoa; hit: terän piste."""
    return {"body": split(render(0)), "tracks": [split(render(k))[1] for k in range(3)], "hit": blade_hit()}
