"""Partti 5, v2: kuoppa ja runko Hillnerin kuvien tasolla.

1. Kuoppa v2: kamera kuopan reunalla yläkulmassa. Kuoppa on porrastettu (penger 4 m:n syvyydessä), ja
   jyrkät seinämät liukuvat valoisasta reunasta (10/8) varjoiseen pohjaan (9/0) katkoviivaditherinä.
   Seinämissä on maakerrokset, pohjalla pyöränjäljet ja lätäköt. Pyöräkuormaaja on etualalla isona
   (yli neljäsosa kuvan leveydestä) ligne claire -piirroksena: musta ääriviiva, keltainen runko kolmella
   sävyllä, ohjaamo laseineen, nostovarret ja kauha teräreunoineen, renkaat napoineen. Takana kuopan
   reunalla ovat torin vanhat talot (Hillnerin naapurit), ja kuvassa on yksi aidan tolppa reunassa.
2. Runko v2: Lohjantähden siluetti torin akselilta (pitkä kolmikerroksinen runko ja kulman torni, tori.CAMERA
   laajemmalla objektiivilla). Betonilaattojen reunat ovat valkoisina viivoina, ja niiden alla on varjo ja
   pimeät aukot. Julkisivun edessä on telineet lankkuineen, tornissa teräsrunko ja hissikuilu, ja nosturin
   puomi ylittää taivaan. Maatasolla on työmaa-aita, ja ihmismittakaavan antavat jalankulkija ja
   valaisinpylväs etualalla.

Piirto: 3D-pinnat projisoidaan monikulmioiksi (maalarin algoritmi, ääriviiva 1 px musta), maasto
säteenseurannalla. Kuvat 160 x 144 MC-px.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from . import star
from .house import reduce_cells
from .persp import Camera, Tracer
from .pixel import (BLACK, BLUE, BROWN, DGREY, GREEN, GREY, LBLUE, LGREEN, LGREY, LRED, ORANGE, RED, WHITE, YELLOW,
                    DASH, banded_sky, odither)

H, W = 144, 160
LIGHT = np.array([-0.6, 0.65, 0.45])     # valo vasemmalta ylhäältä, ilta
LIGHT /= np.linalg.norm(LIGHT)


# ------------------------------------------------------------------ monikulmiopiirto

def _rot(yaw: float) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def box_faces(lo, hi, ramp, org=(0, 0, 0), yaw=0.0, kind="", skip=()) -> list[dict]:
    """Laatikon kuusi sivua maailman koordinaateissa (paikallinen lo/hi, kierto yaw, siirto org)."""
    R = _rot(yaw)
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    quads = {"x0": ([(x0, y0, z1), (x0, y0, z0), (x0, y1, z0), (x0, y1, z1)], (-1, 0, 0)),
             "x1": ([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], (1, 0, 0)),
             "y1": ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
             "y0": ([(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)], (0, -1, 0)),
             "z0": ([(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)], (0, 0, -1)),
             "z1": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1))}
    out = []
    for k, (pts, n) in quads.items():
        if k in skip:
            continue
        P = np.array(pts, float) @ R.T + np.array(org, float)
        out.append({"pts": P, "n": R @ np.array(n, float), "ramp": ramp, "kind": kind, "side": k})
    return out


def prism_faces(poly2d, z0, z1, ramp, org=(0, 0, 0), yaw=0.0, kind="") -> list[dict]:
    """Monikulmio xy-tasossa puristettuna z-suuntaan (pyörät, kauhan kyljet)."""
    R = _rot(yaw)
    out = []
    for z, sgn in ((z1, 1), (z0, -1)):
        P = np.array([(x, y, z) for x, y in poly2d], float) @ R.T + np.array(org, float)
        out.append({"pts": P, "n": R @ np.array((0, 0, sgn), float), "ramp": ramp, "kind": kind + "_kylki"})
    n = len(poly2d)
    for i in range(n):
        (xa, ya), (xb, yb) = poly2d[i], poly2d[(i + 1) % n]
        P = np.array([(xa, ya, z0), (xb, yb, z0), (xb, yb, z1), (xa, ya, z1)], float) @ R.T + np.array(org, float)
        nn = np.array((yb - ya, -(xb - xa), 0.0))
        nn /= np.linalg.norm(nn) + 1e-9
        out.append({"pts": P, "n": R @ nn, "ramp": ramp, "kind": kind + "_vaippa"})
    return out


def draw_faces(img, cam: Camera, faces: list[dict], outline: bool = True, lay=None, lay_id: int = 0,
               zbuf=None) -> None:
    """Pinnat kauimmasta lähimpään: sävy valosta (lambert) ja pinnan pystyliukuma rampin
    katkoviivaditherillä, ääriviiva 1 px musta (ligne claire). Takapinnat karsitaan."""
    c = np.array(cam.pos, float)
    items = []
    for f in faces:
        cen = f["pts"].mean(0)
        if np.dot(f["n"], c - cen) <= 0:
            continue
        pr = [cam.project(p) for p in f["pts"]]
        items.append((np.linalg.norm(cen - c), f, pr))
    items.sort(key=lambda a: -a[0])
    yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    for dist, f, pr in items:
        im = Image.new("1", (img.shape[1], img.shape[0]), 0)
        ImageDraw.Draw(im).polygon([(float(x), float(y)) for x, y in pr], fill=1)
        m = np.array(im, bool)
        if zbuf is not None:
            m &= dist < zbuf
        if not m.any():
            continue
        lam = max(0.0, float(np.dot(f["n"], LIGHT)))
        ys = [p[1] for p in pr]
        y0, y1 = min(ys), max(ys) + 1e-3
        grad = (yy - y0) / (y1 - y0)
        tone = f.get("tone", 0.25 + 0.6 * lam) - 0.12 * grad + f.get("bias", 0.0)
        img[m] = odither(np.clip(tone, 0, 1), f["ramp"])[m]
        if f.get("paint"):
            f["paint"](img, m, xx, yy)
        if lay is not None:
            lay[m] = lay_id
        if zbuf is not None:
            zbuf[m] = dist
        if outline and f.get("outline", True):
            ol = Image.new("1", (img.shape[1], img.shape[0]), 0)
            ImageDraw.Draw(ol).polygon([(float(x), float(y)) for x, y in pr], outline=1)
            o = np.array(ol, bool) & m
            img[o] = BLACK


# ------------------------------------------------------------------ 1. kuoppa v2

DEPTH = 8.0
BENCH = (-4.0, 2.0, 6.0)                 # penkereen korkeus, ylä- ja alaluiskan vaakaleveys
RIM = (-72.0, 20.0, -84.0, 0.0)


def pit_h(x, z):
    """Porrastettu kuoppa: reunalta jyrkkä luiska 4 m alas penkereelle (leveys 4 m), toinen luiska
    pohjalle 8 m:iin. Pohjalla kaksi hiekkakasaa ja ajoramppi vasemmalla."""
    x0, x1, z0, z1 = RIM
    d = np.minimum.reduce([x - x0, x1 - x, z - z0, z1 - z])
    hb, s1, s2 = BENCH
    h = np.where(d <= 0, 0.0,
                 np.where(d < s1, hb * d / s1,
                          np.where(d < s2, hb - 0.3 * (d - s1) / (s2 - s1),
                                   np.where(d < s2 + 2.5, hb - 0.3 + (-DEPTH - hb + 0.3) * (d - s2) / 2.5, -DEPTH))))
    pile = 2.4 * np.exp(-(((x + 52) / 6.0) ** 2 + ((z + 40) / 5.0) ** 2)) \
        + 1.6 * np.exp(-(((x + 18) / 5.0) ** 2 + ((z + 58) / 6.0) ** 2))
    h = np.where(d > s2 + 2.5, h + pile + 0.15 * np.sin(x * 0.9) * np.sin(z * 0.7), h)
    return h


PIT_CAM = Camera(pos=(-20.0, 3.0, 3.0), target=(-52.0, 3.0, -52.0), focal=170.0, shift=-36.0, h=H, w=W)


def _march(cam: Camera, hf, tmax=200.0, step=0.2):
    tr = Tracer(cam)
    d = tr.d
    o = np.array(cam.pos, float)
    t = np.full(d.shape[:2], np.inf)
    alive = d[..., 1] < 0.05
    for s in np.arange(0.3, tmax, step):
        p = o + d * s
        hit = alive & ~np.isfinite(t) & (p[..., 1] <= hf(p[..., 0], p[..., 2]))
        t = np.where(hit, s, t)
    ok = np.isfinite(t)
    p = o + d * np.where(ok, t, 0)[..., None]
    e = 0.25
    gx = (hf(p[..., 0] + e, p[..., 2]) - hf(p[..., 0] - e, p[..., 2])) / (2 * e)
    gz = (hf(p[..., 0], p[..., 2] + e) - hf(p[..., 0], p[..., 2] - e)) / (2 * e)
    n = np.stack([-gx, np.ones_like(gx), -gz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return t, p, n, ok


SAND = (BLACK, BROWN, ORANGE, LRED, LGREY)       # 0/9, 9/8, 8/10, 10/15


def _terrain(cam: Camera) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t, p, n, ok = _march(cam, pit_h)
    yy, xx = np.mgrid[0:H, 0:W]
    img = banded_sky(H, W, (LBLUE, LGREY, WHITE), ((0, 0.0), (18, 0.5), (34, 1.0)), edge=6)
    cl = ((np.sin(xx / 9.0 + yy / 3.5) > 0.55) & (yy < 22) & (np.sin(xx / 29.0 + 1) > 0.1))
    img[cl & (DASH[yy % 4, xx % 8] < 0.6)] = WHITE
    y = p[..., 1]
    lam = np.clip(n @ LIGHT, 0, 1)
    wall = ok & (n[..., 1] < 0.75) & (y < -0.2)
    flat_in = ok & (n[..., 1] >= 0.75) & (y < -0.2)
    out = ok & (y >= -0.2)
    depth_t = np.clip((y + DEPTH) / DEPTH, 0, 1)                       # 1 reunalla .. 0 pohjalla
    px_, pz_ = p[..., 0], p[..., 2]
    # seinämät: liukuväri valoisasta reunasta varjoiseen pohjaan, maakerrokset vinoina juovina
    tone = 0.08 + 0.55 * depth_t + 0.3 * lam + 0.04 * np.sin(px_ * 1.3 + pz_ * 0.9)
    img[wall] = odither(np.clip(tone, 0, 1), SAND)[wall]
    strata = wall & ((((y + 0.25 * np.sin(px_ * 0.4 + pz_ * 0.3)) * 1.4) % 1) < 0.12)
    img[strata] = np.where(np.isin(img[strata], (LRED, LGREY)), ORANGE, np.where(img[strata] == ORANGE, BROWN, BLACK))
    stones = wall & ((np.sin(px_ * 6.1) * np.sin(pz_ * 5.3) * np.sin(y * 7.7)) > 0.55)
    img[stones] = np.where(lam[stones] > 0.4, LGREY, BLACK)
    # penger ja pohja: penger valoisampi, pohja varjossa ja kostea, pyöränjäljet, lätäköt
    bench = flat_in & (y > -5.0)
    tone_f = np.where(bench, 0.55 + 0.2 * lam, 0.22 + 0.25 * lam) + 0.05 * np.sin(px_ * 0.8) * np.cos(pz_ * 1.1)
    img[flat_in] = odither(np.clip(tone_f, 0, 1), SAND)[flat_in]
    bottom = flat_in & ~bench
    trk = bottom & (np.abs(((pz_ + 0.45 * px_) % 4.6) - 2.3) < 0.28)
    img[trk] = BROWN
    trk2 = bottom & (np.abs(((pz_ + 0.45 * px_) % 4.6) - 1.7) < 0.22)
    img[trk2] = BROWN
    tread = trk & (((px_ * 2.6) % 1) < 0.35)
    img[tread] = BLACK
    pud = bottom & ((((px_ + 30) / 7.0) ** 2 + ((pz_ + 30) / 3.0) ** 2 < 1) |
                    (((px_ + 8) / 4.0) ** 2 + ((pz_ + 50) / 2.0) ** 2 < 1))
    img[pud] = np.where(DASH[yy % 4, xx % 8] < 0.5, LBLUE, BLUE)[pud]   # lätäkkö heijastaa taivasta
    img[pud & (((yy + xx) % 7) == 0)] = WHITE
    # kuopan ulkopuoli: työmaan sora ja tallattu maa, reunalla kuiva nurmi
    g = odither(np.clip(0.35 + 0.35 * lam + 0.06 * np.sin(px_ * 1.7) * np.cos(pz_ * 1.3), 0, 1), (BLACK, BROWN, DGREY, GREY))
    img[out] = g[out]
    grass = out & (np.minimum.reduce([px_ - RIM[0], RIM[1] - px_, pz_ - RIM[2], RIM[3] - pz_]) > -1.5) & ((xx + yy * 3) % 4 == 0)
    img[grass] = GREEN
    # ilta-auringon varjo: läntinen reuna varjostaa pohjaa ja seinämiä (säde valoa kohti osuu maastoon)
    sh = np.zeros_like(ok)
    q = p.copy()
    for k in range(1, 70):
        q = p + LIGHT * (k * 0.6)
        sh |= ok & (q[..., 1] < pit_h(q[..., 0], q[..., 2]) - 0.05)
    shade = sh & (y < -0.2)
    img[shade & np.isin(img, (LGREY, LRED))] = ORANGE
    img[shade & (img == ORANGE) & (DASH[yy % 4, xx % 8] < 0.6)] = BROWN
    img[shade & (img == BROWN) & (DASH[yy % 4, xx % 8] < 0.35)] = BLACK
    # ligne claire: syvyyshyppy (reunan siluetti) mustana
    tt = np.where(np.isfinite(t), t, 400.0)
    jump = np.zeros_like(ok)
    jump[:-1] |= (tt[1:] - tt[:-1]) > 3.0
    jump[:, :-1] |= np.abs(tt[:, 1:] - tt[:, :-1]) > 4.0
    img[jump & ok] = BLACK
    return img, t, p


def _loader(org, yaw: float, lift: float = 0.6) -> list[dict]:
    """Pyöräkuormaaja (noin 8 m) paikallisissa koordinaateissa: +x eteenpäin, +z vasemmalle."""
    Y = (BROWN, ORANGE, YELLOW, WHITE)                                 # keltainen kone: 9/8 varjo, 8/7, 7/1 valo
    Yd = (BLACK, BROWN, ORANGE, YELLOW)
    G = (BLACK, BLUE, LBLUE, LGREY)
    T = (BLACK, DGREY, GREY)
    F = []
    F += box_faces((-4.2, 0.9, -1.15), (-1.3, 2.3, 1.15), Y, org, yaw, "takarunko")
    F += box_faces((-4.35, 1.0, -0.9), (-4.2, 2.1, 0.9), T, org, yaw, "jaahdytin")
    F += box_faces((-1.3, 0.8, -0.95), (0.9, 1.9, 0.95), Yd, org, yaw, "etukehys")
    cab = box_faces((-2.6, 2.3, -1.0), (-0.9, 4.0, 1.0), Y, org, yaw, "ohjaamo")
    for f in cab:
        if f["side"] in ("x1", "z0", "z1", "x0"):
            f["ramp"] = G
            f["bias"] = 0.1
            f["paint"] = _glass_paint
    F += cab
    F += box_faces((-2.75, 4.0, -1.15), (-0.75, 4.2, 1.15), Y, org, yaw, "katto")
    F += box_faces((-3.9, 2.3, 0.55), (-3.7, 3.1, 0.75), T, org, yaw, "pakoputki")
    for zs in (-0.85, 0.85):                                           # nostovarret
        arm = [(-0.2, 1.7 + lift * 0.2), (2.6, 1.2 + lift), (2.6, 1.6 + lift), (-0.2, 2.1 + lift * 0.2)]
        F += prism_faces(arm, zs - 0.12, zs + 0.12, Yd, org, yaw, "varsi")
    by = 0.3 + lift
    bucket = [(2.4, by), (3.5, by), (3.7, by + 0.4), (3.2, by + 1.5), (2.5, by + 1.6)]
    for f in prism_faces(bucket, -1.45, 1.45, Y, org, yaw, "kauha"):
        F.append(f)
    edge = box_faces((3.45, by - 0.05, -1.45), (3.75, by + 0.15, 1.45), (GREY, LGREY, WHITE), org, yaw, "tera")
    F += edge
    for xw in (-3.0, 0.2):                                             # renkaat
        for zw, sgn in ((-1.35, -1), (1.35, 1)):
            oct_ = [(xw + 0.85 * math.cos(a), 0.85 + 0.85 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 11)[:-1]]
            tyre = prism_faces(oct_, zw - 0.32, zw + 0.32, T, org, yaw, "rengas")
            for f in tyre:
                if f["kind"].endswith("vaippa"):
                    f["paint"] = _tread_paint
                else:
                    f["paint"] = _hub_paint
            F += tyre
    for f in F:                                                        # keltainen maali kirkkaana myös varjopuolella
        if f["ramp"] in (Y, Yd):
            f["bias"] = f.get("bias", 0.0) + 0.32
    return F


def _glass_paint(img, m, xx, yy):
    """Ohjaamon lasi: taivaan heijastus ja vino valojuova, puitteet."""
    refl = m & (((xx + yy) % 9) < 2)
    img[refl] = LGREY
    img[m & ((yy % 7) == 0)] = BLACK


def _tread_paint(img, m, xx, yy):
    img[m & (((xx * 2 + yy) % 4) == 0)] = DGREY


def _hub_paint(img, m, xx, yy):
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return
    cy, cx = ys.mean(), xs.mean()
    r = ((xs - cx) / max(np.ptp(xs) / 2, 1)) ** 2 + ((ys - cy) / max(np.ptp(ys) / 2, 1)) ** 2
    hub = r < 0.25
    img[ys[hub], xs[hub]] = YELLOW
    img[ys[(r >= 0.25) & (r < 0.36)], xs[(r >= 0.25) & (r < 0.36)]] = ORANGE


def _town(cam: Camera) -> list[dict]:
    """Kuopan takareunan takana torin vanhat talot (1989): rapattu kaksikerroksinen liiketalo, vihreä puinen
    kaksikerroksinen talo harjakattoineen, kerrostalo parvekkeineen ja Sokeripalan valkoinen kulma."""
    F = []
    plaster = (BROWN, RED, LRED, LGREY)
    F += box_faces((-80, 0, -110), (-58, 8, -94), plaster, kind="liiketalo")
    F += box_faces((-52, 0, -112), (-32, 7.2, -98), (BLACK, DGREY, GREEN, LGREEN), kind="puutalo")
    roof = [(-53, 7.2, -112), (-31, 7.2, -112), (-31, 10.8, -105), (-53, 10.8, -105)]
    F.append({"pts": np.array(roof, float), "n": np.array([0, 0.89, -0.45]), "ramp": (BLACK, DGREY, GREY), "kind": "katto"})
    roof2 = [(-53, 7.2, -98), (-53, 10.8, -105), (-31, 10.8, -105), (-31, 7.2, -98)]
    F.append({"pts": np.array(roof2, float), "n": np.array([0, 0.89, 0.45]), "ramp": (BLACK, DGREY, GREY), "kind": "katto"})
    F += box_faces((-26, 0, -116), (4, 15, -100), (DGREY, GREY, LGREY, WHITE), kind="kerrostalo")
    F += box_faces((10, 0, -104), (24, 12, -92), (GREY, LGREY, WHITE), kind="sokeripala")
    for f in F:
        f["paint"] = _facade_paint(f["kind"])
    return F


def _facade_paint(kind):
    def paint(img, m, xx, yy):
        if kind == "kerrostalo":
            img[m & ((yy % 5) == 0)] = WHITE                           # parvekelaatat
            img[m & ((yy % 5) == 2) & ((xx % 4) < 2)] = BLACK
        elif kind in ("liiketalo", "puutalo"):
            img[m & ((yy % 6) == 3) & ((xx % 5) < 2)] = BLACK          # ikkunat
            img[m & ((yy % 6) == 2) & ((xx % 5) < 2)] = WHITE          # puitteet
        elif kind == "sokeripala":
            img[m & ((yy % 6) == 3)] = BLACK                           # nauhaikkunat
    return paint


LOADER_YAW = math.radians(60.0)


def _post(img) -> None:
    """Yksi aidan tolppa oikeassa reunassa (sinkitty putki: valoreuna 1, 15, 12, varjo 11)."""
    for k, c in enumerate((WHITE, LGREY, GREY, GREY, DGREY)):
        img[:, 153 + k] = c
    img[(np.arange(H) % 19) == 0, 153:158] = DGREY


# ------------------------------------------------------------------ 2. runko v2

RUNKO_CAM = Camera(pos=(46.0, 1.7, 36.0), target=(4.0, 1.7, -10.0), focal=250.0, shift=46.0, h=200, w=W)
RUNKO_CROP = 44
FL = 3.3


def runko_v2(floors: int = 3, tower_floors: int = 5) -> np.ndarray:
    """Avainkuva 2 v2: Lohjantähden runko torilta jalankulkijan silmin (tori-akselin suunta, laajempi
    objektiivi, jotta pitkä kolmikerroksinen runko ja kulman torni näkyvät kokonaan siluettina).
    Betonilaattojen reunat valkoisina, niiden alla varjo, aukoissa pimeä sisus takapilareineen ja
    työvalot; julkisivun vasemmalla telineet lankkuineen; tornissa teräsrunko ja hissikuilu kiipeävine
    muotteineen; torninosturi puomeineen taivasta vasten, vaijerissa palkki. Maatasolla työmaa-aita, ja
    ihmismittakaavan antavat jalankulkija ja valaisinpylväs."""
    cam = RUNKO_CAM
    tr = star.trace(cam)
    mat, U, V, X = tr.mat, tr.U, tr.V, tr.X
    yy, xx = np.mgrid[0:cam.h, 0:W]
    sky = star._sky(cam)
    img = sky.copy()
    g = mat == star.M_GROUND
    img[g] = star._ground(cam, X, g, 0.0)[g]
    hb = floors * FL
    for mid, front in ((star.M_FRONT, True), (star.M_SIDE, False)):
        m = mat == mid
        col = (U % 6.0) < 0.75
        slab = (V % FL) < 0.4
        built = m & (V <= hb + 0.4)
        bay = built & ~col & ~slab
        depth = np.clip((V % FL) / FL, 0, 1)
        inner = odither(np.clip(0.1 + 0.3 * depth, 0, 1), (BLACK, BROWN, DGREY))
        img[bay] = inner[bay]
        backcol = bay & (((U + 3.0) % 6.0) < 0.35)                     # takapilarit pimeässä
        img[backcol] = DGREY
        rnd = (np.sin(np.floor(U / 6.0) * 12.9898 + np.floor(V / FL) * 78.233) * 43758.5453) % 1
        lit = bay & (rnd < 0.25) & (np.abs((U % 6.0) - 3.4) < 1.8)
        img[lit] = odither(np.clip(0.3 + 0.5 * depth, 0, 1), (BROWN, ORANGE, LRED))[lit]   # työvalo
        img[lit & ((V % FL) > 2.7) & ((V % FL) < 2.85) & (np.abs((U % 6.0) - 3.4) < 0.3)] = WHITE
        conc = odither(np.clip(0.5 + (0.25 if front else -0.1) - 0.3 * ((U % 6.0) / 0.75), 0, 1), (DGREY, GREY, LGREY))
        c = built & col
        img[c] = conc[c]
        img[c & ((U % 6.0) < 0.12)] = WHITE if front else LGREY        # pilarin valoreuna
        s_ = built & slab
        img[s_] = np.where((V % FL)[s_] > 0.22, WHITE, LGREY)          # laatan reuna valkoisena
        img[built & ((V % FL) >= 0.4) & ((V % FL) < 0.55) & ~col] = BLACK   # laatan alla varjo
        top = m & (V > hb + 0.4) & (V <= hb + FL) & col & (np.floor(U / 6.0) % 3 != 1)   # ylimmän kerroksen pilarit
        img[top] = conc[top]
        rebar = m & (V > hb + 0.4) & (V <= hb + 1.3) & ~col & ((U % 0.9) < 0.1)
        img[rebar] = BLACK
    th = tower_floors * FL
    for mid, front in ((star.M_TOWER_F, True), (star.M_TOWER_S, False)):
        m = mat == mid
        core = m & (U > 2.4) & (U < 5.6) & (V <= th + FL + 1.0)
        ct = np.clip(0.4 + (0.25 if front else -0.1) + 0.06 * np.sin(V * 2.0), 0, 1)
        img[core] = odither(np.full(m.shape, ct), (DGREY, GREY, LGREY))[core]
        img[core & ((V % 1.1) < 0.1)] = DGREY
        climb = core & (V > th + FL - 0.4)
        img[climb] = np.where((np.floor(U * 3) % 2) == 0, ORANGE, BROWN)[climb]
        img[core & (np.abs(V - th - FL - 1.0) < 0.18)] = YELLOW
        steel = m & (V <= th + 1.0) & (((U % 2.0) < 0.22) | ((V % FL) < 0.3) |
                                        ((np.abs((U % 2.0) - (V % FL) / FL * 2.0) < 0.18) & (np.floor(V / FL) % 2 == 0)))
        img[steel & ~core] = BLACK
        img[steel & ~core & ((U % 2.0) >= 0.12) & ((U % 2.0) < 0.22)] = ORANGE
        slab_t = m & ((V % FL) < 0.3) & (V <= th)
        img[slab_t & ~core] = LGREY
    _scaffold(img, cam)
    _crane2(img, cam)
    _hoarding(img, cam)
    _person(img, cam, (37.5, 0.0, 26.5))
    _lamp2(img, cam, (43.5, 0.0, 26.0))
    img = img[RUNKO_CROP:RUNKO_CROP + H].copy()
    reduce_cells(img)
    return img


def _line(img, cam, a, b, col, every=1):
    (x0, y0), (x1, y1) = cam.project(a), cam.project(b)
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for k in range(0, n + 1, every):
        t = k / n
        x, y = int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t))
        if 0 <= x < img.shape[1] and 0 <= y < img.shape[0]:
            img[y, x] = col


def _scaffold(img, cam) -> None:
    """Telineet julkisivun edessä (z = +1,2) vasemmalla puolella: pystyputket 2,5 m välein (12, varjo 11),
    lankkutasot 2 m välein (9/8), vinotuet."""
    z = 1.2
    for x in np.arange(-34.0, -6.0, 2.5):
        _line(img, cam, (x, 0, z), (x, 10.5, z), GREY)
    for y in np.arange(2.0, 10.6, 2.0):
        _line(img, cam, (-34.0, y, z), (-6.5, y, z), ORANGE)
        _line(img, cam, (-34.0, y - 0.15, z), (-6.5, y - 0.15, z), BROWN)
    for k, x in enumerate(np.arange(-34.0, -9.0, 5.0)):
        _line(img, cam, (x, 2.0 * (k % 2), z), (x + 5.0, 2.0 * (k % 2) + 4.0, z), DGREY)


def _crane2(img, cam) -> None:
    """Torninosturi rakennuksen takana: ristikkomasto (7 valo, 8 varjo), puomi vasemmalle taivaan yli,
    vastapuomi painoineen oikealle, ohjaamo, vaunu ja vaijerissa teräspalkki, huipun punainen valo."""
    bx, bz, top = 6.0, -46.0, 34.0
    for dx in (-0.9, 0.9):
        _line(img, cam, (bx + dx, 0, bz), (bx + dx, top, bz), YELLOW if dx < 0 else ORANGE)
    for k in range(int(top / 1.8)):
        _line(img, cam, (bx - 0.9, k * 1.8, bz), (bx + 0.9, k * 1.8 + 1.8, bz), ORANGE)
        _line(img, cam, (bx - 0.9, k * 1.8, bz), (bx + 0.9, k * 1.8, bz), ORANGE)
    j0, j1 = (bx + 14.0, top + 1.2, bz), (bx - 48.0, top + 1.2, bz + 4.0)
    _line(img, cam, j0, j1, YELLOW)
    _line(img, cam, (bx + 14.0, top, bz), (bx - 48.0, top, bz + 4.0), ORANGE)
    for k in range(0, 62, 3):                                          # puomin ristikko
        a = (bx + 14.0 - k, top, bz + 4.0 * k / 62)
        b = (bx + 14.0 - k - 1.5, top + 1.2, bz + 4.0 * (k + 1.5) / 62)
        _line(img, cam, a, b, ORANGE)
    _line(img, cam, (bx, top + 7.0, bz), j1, DGREY)                    # vetotangot
    _line(img, cam, (bx, top + 7.0, bz), j0, DGREY)
    _line(img, cam, (bx, top, bz), (bx, top + 7.0, bz), YELLOW)
    cx, cy = cam.project((bx + 11.0, top - 1.0, bz))                   # vastapaino
    cx, cy = int(cx), int(cy)
    if 0 <= cy < img.shape[0] - 3:
        img[cy:cy + 3, max(cx - 2, 0):cx + 3] = DGREY
        img[cy, max(cx - 2, 0):cx + 3] = GREY
    kx, ky = cam.project((bx - 1.5, top - 1.5, bz + 0.5))              # ohjaamo
    kx, ky = int(kx), int(ky)
    if 0 <= ky < img.shape[0] - 2:
        img[ky:ky + 2, kx:kx + 2] = LBLUE
    hook = (bx - 30.0, top, bz + 2.0)
    _line(img, cam, hook, (hook[0], 19.0, hook[2]), BLACK)
    _line(img, cam, (hook[0] - 4.0, 19.0, hook[2]), (hook[0] + 4.0, 19.0, hook[2]), BLACK)
    _line(img, cam, (hook[0] - 4.0, 19.3, hook[2]), (hook[0] + 4.0, 19.3, hook[2]), ORANGE)
    rx, ry = cam.project((bx, top + 7.2, bz))
    if 0 <= int(ry) < img.shape[0]:
        img[int(ry), int(rx)] = RED


def _hoarding(img, cam) -> None:
    """Työmaa-aita torin puolella (z = +5, x -40..27, korkeus 2,2 m): vanerilevyt vuorotellen 12/11,
    yläreuna valossa 15, saumat 0, aidassa julisteita (2/10, 1) ja portti kulmassa."""
    from PIL import Image as _I, ImageDraw as _D
    pts = [(-40.0, 0.0, 5.0), (27.0, 0.0, 5.0), (27.0, 2.2, 5.0), (-40.0, 2.2, 5.0)]
    side = [(27.0, 0.0, 5.0), (27.0, 0.0, -30.0), (27.0, 2.2, -30.0), (27.0, 2.2, 5.0)]
    for quad, base in ((pts, 0.55), (side, 0.3)):
        pr = [cam.project(p) for p in quad]
        im = _I.new("1", (img.shape[1], img.shape[0]), 0)
        _D.Draw(im).polygon([(float(x), float(y)) for x, y in pr], fill=1)
        m = np.array(im, bool)
        yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
        img[m] = odither(np.clip(base + 0.1 * np.sin(xx * 0.9), 0, 1), (DGREY, GREY, LGREY))[m]
        img[m & (xx % 6 == 0)] = BLACK                                 # levyjen saumat
        ys = np.nonzero(m.any(1))[0]
        if len(ys):
            topr = m & (yy <= np.array([np.nonzero(m[:, x])[0].min() if m[:, x].any() else 0 for x in range(img.shape[1])])[None, :])
            img[topr] = WHITE
        poster = m & (((xx // 9) % 4) == 1) & (yy > ys.min() + 2 if len(ys) else False) & (yy < ys.max() - 1 if len(ys) else False)
        img[poster] = np.where(((yy + xx) % 5) < 2, LRED, RED)[poster]
        img[poster & ((yy % 3) == 0) & ((xx % 2) == 0)] = WHITE


def _person(img, cam, pos) -> None:
    """Jalankulkija (1,75 m) torilla: punainen takki (2, valoreuna 10 vasemmalla, varjo 9), pää (iho 10/9,
    hiukset 0), tummat housut ja kengät, kassi. Mittakaava rakennukselle."""
    x0, y0 = cam.project(pos)
    _, y1 = cam.project((pos[0], 1.75, pos[2]))
    hgt = y0 - y1
    cx = int(round(x0))
    k = hgt / 34.0
    for r in range(int(hgt)):
        y = int(round(y1 + r))
        f = r / hgt
        if f < 0.04:
            cols = [(0, BLACK)]                                        # hiukset
        elif f < 0.12:
            cols = [(-1, LRED), (0, LRED), (1, BROWN)]                 # kasvot
        elif f < 0.15:
            cols = [(0, BROWN)]                                        # kaula
        elif f < 0.58:
            w = int(round((2.2 + 0.8 * (f - 0.15)) * k))
            cols = [(dx, LRED if dx == -w else (BROWN if dx == w else RED)) for dx in range(-w, w + 1)]
        else:
            step = int(round(1.2 * k * (f - 0.58) / 0.42))             # jalat hieman haarallaan (kävelee)
            cols = [(-1 - step, BLACK), (-step, DGREY), (1 + step, BLACK)]
        for dx, c in cols:
            x = cx + dx
            if 0 <= x < img.shape[1] and 0 <= y < img.shape[0]:
                img[y, x] = c
    by = int(round(y1 + hgt * 0.42))
    if 0 <= by < img.shape[0] - 4 and 0 <= cx + 4 < img.shape[1]:
        img[by:by + 4, cx + 3:cx + 5] = LGREY                          # kassi
        img[by, cx + 3:cx + 5] = BLACK


def _lamp2(img, cam, pos) -> None:
    """Valaisinpylväs etualalla: musta pylväs valoreunalla, lyhty 15/1 ja valokeila."""
    (x0, y0), (x1, y1) = cam.project(pos), cam.project((pos[0], pos[1] + 6.0, pos[2]))
    for y in range(int(max(y1, 0)), int(min(y0, img.shape[0]))):
        for dx, c in ((-1, GREY), (0, BLACK), (1, BLACK)):
            x = int(round(x0)) + dx
            if 0 <= x < img.shape[1]:
                img[y, x] = c
    hx, hy = int(round(x1)), int(round(y1))
    for dy in range(-3, 2):
        for dx in range(-3, 4):
            if 0 <= hy + dy < img.shape[0] and 0 <= hx + dx < img.shape[1]:
                img[hy + dy, hx + dx] = BLACK
    for dx in range(-2, 3):
        if 0 <= hy < img.shape[0] and 0 <= hx + dx < img.shape[1]:
            img[hy, hx + dx] = WHITE if abs(dx) < 2 else LGREY
