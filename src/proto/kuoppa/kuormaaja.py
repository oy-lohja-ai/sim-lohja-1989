"""Kuva 1: pyöräkuormaaja kuopan penkereellä (kuoppa2.kuoppa_v2:n kamera ja kone). Host tekee vain staattisen
datan: koneen rungon kuvan (bittikartan solumuodossa, neljä MC-esisiirtoa ja maski), ohjaamon lasin spriteiksi,
nostovarsien ja kauhan kärkipisteiden projektiotaulut kulman funktiona, napojen pulttien kehät, ajon kulku
avainkehyksistä ja taustan, jonka koneen alue on koneen paletissa 0/9/8/7 (ei värimuistin vaihtoja).

6510 piirtää joka päivityksessä: rungon (siirto ja maski), nostovarret ja kauhan monikulmioina (täyttö
katkoviivaditherillä, musta ääriviiva, näkyvyys ja sävy kulman mukaan), pyörivät pultit, hiekan kauhassa ja
valuvat jyvät, jotka leivotaan taustaan luiskalle. Esikatselu model() tekee saman Pythonissa.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from concept import kuoppa2 as k2
from concept.persp import Camera
from concept.pixel import (BLACK, BLUE, BROWN, DASH, DGREY, GREY, LBLUE, LGREY, ORANGE, WHITE, YELLOW, T)
from concept.house import reduce_cells

H, W = 144, 160
CAM = k2.PIT_CAM
YAW = k2.LOADER_YAW
REF = (-30.5, k2.BENCH[0] - 0.1, -4.0)        # vertailupaikka (konseptikuvan kohta), s = 0
FWD = (math.cos(YAW), -math.sin(YAW))          # paikallinen +x maailmassa (x, z)
PAD = 64                                       # rungon piirtokankaan reunus (kone ei leikkaudu)
SAND4 = (BLACK, BROWN, ORANGE, YELLOW)         # koneen alueen paletti: kone ja hiekka samoilla väreillä
ROLE = {BLACK: 0, BROWN: 1, ORANGE: 2, YELLOW: 3}
GLASS = (BLUE, LGREY, LBLUE)                   # spritet: $d025 = 6 (%01), oma 15 (%10), $d026 = 14 (%11)

# ------------------------------------------------------------------ kinematiikka (paikalliset metrit)
PIVOT = (-0.2, 1.9)                            # nostovarsien nivel runkoon
ARM_L = 2.85
ARM_Z = 0.85                                   # varret kummallakin puolella
ARM_T = 0.2                                    # varren puolipaksuus (y)
BUCKET = [(-0.2, -1.1), (0.9, -1.1), (1.1, -0.7), (0.6, 0.4), (-0.1, 0.5)]   # tappiin nähden, suu v2-v3
BUCKET_Z = 1.45
NA = 64                                        # nostokulman askeleet
A_LO, A_HI = math.radians(-11), math.radians(38)
NP = 32                                        # kauhan kallistuksen askeleet
P_LO, P_HI = math.radians(-70), math.radians(25)   # -70 = kippaus (suu alas), +25 = kuormattuna taakse
WHEEL_R = 0.85
WHEELS = [(-3.0, 1.35 + 0.32), (0.2, 1.35 + 0.32)]  # lähipuolen navat (x, z), näkyvät
NT = 16                                        # pyörän kulma-askeleet


def alpha(i: int) -> float:
    return A_LO + (A_HI - A_LO) * i / (NA - 1)


def phi(i: int) -> float:
    return P_LO + (P_HI - P_LO) * i / (NP - 1)


def rot_y(yaw: float) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def world(local, org=REF) -> np.ndarray:
    return rot_y(YAW) @ np.array(local, float) + np.array(org, float)


def proj(p, cam=CAM) -> np.ndarray:
    return np.array(cam.project(p))


def origin(s: float) -> tuple:
    return (REF[0] + FWD[0] * s, REF[1], REF[2] + FWD[1] * s)


def pin(a: float) -> tuple:
    return (PIVOT[0] + ARM_L * math.cos(a), PIVOT[1] + ARM_L * math.sin(a))


# ------------------------------------------------------------------ ajon kulku (osan kehykset 0-599)
# (kehys, s metreinä, nostokulman indeksi, kallistuksen indeksi, kuorma 0-1)
KEYS = [(0, -4.0, 8, 26, 1.0), (35, -1.6, 14, 27, 1.0), (70, 0.3, 8, 28, 1.0),          # ajaa sisään, kauha keinuu
        (90, 0.35, 12, 28, 1.0), (150, 0.45, 56, 26, 1.0), (170, 0.45, 60, 24, 1.0),     # jarrutus, nosto
        (250, 0.45, 60, 2, 0.0), (262, 0.45, 58, 6, 0.0), (275, 0.45, 60, 2, 0.0),       # kippaus, ravistus
        (330, -1.5, 10, 20, 0.0), (360, -0.6, 4, 16, 0.0), (390, 0.0, 6, 28, 1.0),       # peruutus, kauha kasaan
        (430, -1.0, 24, 28, 1.0), (470, 0.2, 40, 26, 1.0), (500, 0.3, 36, 27, 1.0),      # kuorma ylös, ajaa
        (550, -1.8, 20, 28, 1.0), (600, -4.2, 14, 26, 1.0)]                              # peruuttaa ulos


def ease(u: float) -> float:
    return u * u * (3 - 2 * u)


def state(f: float) -> tuple[float, float, float, float]:
    for (f0, *a), (f1, *b) in zip(KEYS, KEYS[1:]):
        if f <= f1:
            u = ease((f - f0) / (f1 - f0))
            return tuple(x + (y - x) * u for x, y in zip(a, b))
    return tuple(KEYS[-1][1:])


# ------------------------------------------------------------------ tausta
def background() -> np.ndarray:
    """Konseptin maasto koneen paletilla (hiekka 0/9/8/7 ilta-auringossa), torin talot ja tolppa."""
    old = k2.SAND
    k2.SAND = SAND4
    try:
        img, t, _ = k2._terrain(CAM)
    finally:
        k2.SAND = old
    zbuf = np.where(np.isfinite(t), t, 1e9)
    k2.draw_faces(img, CAM, k2._town(CAM), zbuf=zbuf.copy())
    k2._post(img)
    reduce_cells(img)
    return img


def to_palette(img: np.ndarray, cells: np.ndarray) -> int:
    """Alueen solut koneen palettiin 0/9/8/7: muu väri lähimpään valoisuudeltaan. Palauttaa muutetut pikselit."""
    from concept.c64 import palette
    lum = palette().astype(float) @ np.array([0.299, 0.587, 0.114])
    keep = list(ROLE)
    near = {c: min(keep, key=lambda k: abs(lum[k] - lum[c])) for c in range(16)}
    n = 0
    for cy, cx in zip(*np.nonzero(cells)):
        cell = img[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
        for c in np.unique(cell):
            if int(c) not in ROLE:
                m = cell == c
                cell[m] = near[int(c)]
                n += int(m.sum())
    return n


# ------------------------------------------------------------------ runko ja lasi
@dataclass
class Body:
    img: np.ndarray            # MC-kuva (T = läpinäkyvä), koneen värit ROLE-avaimina
    glass: np.ndarray          # lasin värit (T muualla)
    ox: int                    # kuvan vasen yläkulma suhteessa ankkuriin (origon projektio)
    oy: int


def _faces(lift_parts: bool = False) -> list[dict]:
    """Konseptin kone ilman varsia ja kauhaa, paletti rajattu: keltainen runko 9/8/7, renkaat 0/9, lasi erikseen."""
    F = k2._loader(REF, YAW, 0.0)
    out = []
    for f in F:
        kind = f["kind"]
        if kind.startswith(("varsi", "kauha", "tera")) and not lift_parts:
            continue
        r = f["ramp"]
        if r == (BROWN, ORANGE, YELLOW, WHITE):
            f["ramp"] = (BROWN, ORANGE, YELLOW, YELLOW)    # sama sävyjako kuin konseptissa, valkoinen keltaiseksi
        elif r == (BLACK, DGREY, GREY):
            f["ramp"] = (BLACK, BLACK, BROWN)
        out.append(f)
    return out


def render_body() -> Body:
    cam = Camera(CAM.pos, CAM.target, CAM.focal, CAM.shift, h=H + 2 * PAD, w=W + 2 * PAD)
    img = np.full((cam.h, cam.w), T, np.int16)
    lay = np.zeros(img.shape, int)
    faces = _faces()
    c = np.array(cam.pos, float)
    order = sorted(range(len(faces)), key=lambda i: -np.linalg.norm(faces[i]["pts"].mean(0) - c))
    for i in order:
        k2.draw_faces(img, cam, [faces[i]], lay=lay, lay_id=i + 1)
    glass_ids = {i + 1 for i, f in enumerate(faces) if f["ramp"][1] == BLUE}
    gl = np.isin(lay, list(glass_ids)) & np.isin(img, GLASS)
    glass = np.where(gl, img, T)
    for a, b in ((BLUE, BLACK), (LBLUE, BROWN), (LGREY, ORANGE)):    # lasi: tumma, ilta-auringon heijastus
        img[gl & (img == a)] = b
    img = np.where((img != T) & ~np.isin(img, list(ROLE)), BLACK, img)
    for a, b in ((DGREY, BROWN), (GREY, ORANGE), (LGREY, YELLOW), (WHITE, YELLOW)):
        img[(img == a) & ~gl] = b
    img = np.where(np.isin(img, list(ROLE)) | (img == T), img, BLACK)
    ys, xs = np.nonzero(img != T)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    ax, ay = proj(REF, cam)
    return Body(img[y0:y1, x0:x1].copy(), glass[y0:y1, x0:x1].copy(), int(x0 - round(ax)), int(y0 - round(ay)))


# ------------------------------------------------------------------ projektiotaulut (MC-px ankkurista)
LIGHT = k2.LIGHT
FILL_ROLES = (0, 0, 2, 3)                      # 6510:n PAT: ruskea mustaksi (spritekankaan rooli 1 = läpinäkyvä)


def _anchor() -> np.ndarray:
    return proj(REF)


def pin_table() -> np.ndarray:
    """[ia] -> tapin (keskilinja) siirtymä ankkurista."""
    a0 = _anchor()
    return np.array([proj(world((*pin(alpha(i)), 0.0))) - a0 for i in range(NA)])


def arm_table() -> np.ndarray:
    """[ia, varsi 0 kauempi / 1 lähempi, kärki 0-3] -> nelikulmion kärjet ankkurista (nivel ylä, ala, tappi ala, ylä)."""
    a0 = _anchor()
    out = np.zeros((NA, 2, 4, 2))
    for i in range(NA):
        px, py = pin(alpha(i))
        for j, z in enumerate((-ARM_Z, ARM_Z)):
            pts = [(PIVOT[0], PIVOT[1] + ARM_T, z), (PIVOT[0], PIVOT[1] - ARM_T, z), (px, py - ARM_T, z), (px, py + ARM_T, z)]
            out[i, j] = [proj(world(p)) - a0 for p in pts]
    return out


PIN0 = pin(alpha(NA // 2))                       # kauhan linearisointikohta


def bucket_table() -> np.ndarray:
    """[ip, kärki 0-4, puoli 0 (-z) / 1 (+z)] -> kärjen siirtymä tapista (affiini, PIN0:n kohdalla)."""
    c0 = proj(world((*PIN0, 0.0)))
    out = np.zeros((NP, 5, 2, 2))
    for i in range(NP):
        p = phi(i)
        c, s = math.cos(p), math.sin(p)
        for kk, (x, y) in enumerate(BUCKET):
            for j, z in enumerate((-BUCKET_Z, BUCKET_Z)):
                out[i, kk, j] = proj(world((PIN0[0] + c * x - s * y, PIN0[1] + s * x + c * y, z))) - c0
    return out


def bucket_faces() -> list[tuple]:
    """Kauhan pinnat kärkien (kärki, puoli) listoina: kyljet ja vaipan nauhat; nauha 2 (v2-v3) on suu."""
    F = [tuple((kk, 0) for kk in range(5))[::-1], tuple((kk, 1) for kk in range(5))]
    for kk in range(5):
        n = (kk + 1) % 5
        F.append(((kk, 0), (n, 0), (n, 1), (kk, 1)))
    return F


MOUTH = 2 + 2                                    # bucket_faces-indeksi suun nauhalle


def face_shades() -> tuple[np.ndarray, np.ndarray]:
    """[ip, pinta] -> näkyvyys (kameraa kohti) ja sävy 0-6 valosta (Lambert kuten draw_faces)."""
    F = bucket_faces()
    vis = np.zeros((NP, len(F)), bool)
    tone = np.zeros((NP, len(F)), int)
    cam = np.array(CAM.pos, float)
    for i in range(NP):
        p = phi(i)
        c, s = math.cos(p), math.sin(p)
        P = {}
        for kk, (x, y) in enumerate(BUCKET):
            for j, z in enumerate((-BUCKET_Z, BUCKET_Z)):
                P[kk, j] = world((PIN0[0] + c * x - s * y, PIN0[1] + s * x + c * y, z))
        for fi, f in enumerate(F):
            q = np.array([P[v] for v in f])
            n = np.cross(q[1] - q[0], q[2] - q[0])
            n /= np.linalg.norm(n)
            cen = q.mean(0)
            vis[i, fi] = np.dot(n, cam - cen) > 0
            lam = max(0.0, float(np.dot(n, LIGHT)))
            tone[i, fi] = int(round(np.clip(0.25 + 0.6 * lam + 0.32, 0, 1) * 6))
    return vis, tone


def hub_table() -> np.ndarray:
    """[pyörä, kulma 0-NT, pultti 0-2] -> pultin siirtymä ankkurista (navan kehä r = 0,35 m)."""
    a0 = _anchor()
    out = np.zeros((len(WHEELS), NT, 3, 2))
    for w, (x, z) in enumerate(WHEELS):
        for t in range(NT):
            for b in range(3):
                a = 2 * math.pi * (t / NT + b / 3)
                out[w, t, b] = proj(world((x + 0.33 * math.cos(a), WHEEL_R + 0.33 * math.sin(a), z))) - a0
    return out


def path_anchor(s: float) -> np.ndarray:
    return proj(origin(s))


def wheel_turn(s: float) -> int:
    """Pyörän kulma-askel ajetusta matkasta (eteenpäin ajaessa pultit kiertävät myötäpäivään)."""
    return int(math.floor(-s / (2 * math.pi * WHEEL_R) * NT)) % NT


def tables() -> dict:
    vis, tone = face_shades()
    return {"pin": pin_table(), "arm": arm_table(), "bucket": bucket_table(), "vis": vis, "tone": tone,
            "hub": hub_table()}


# ------------------------------------------------------------------ vienti 6510:lle
ZONE_ROWS = (7, 18)                              # merkkirivit, joilla kone, varret, kauha ja hiekka liikkuvat
ZONE_COLS = 21                                   # sarakkeet 0-20 (lätäkkö alkaa sarakkeesta 21)
STEP = 4                                         # kulun taulu joka 4. kehys
FRAMES = 600
NSHIFT = 4
BODY_COLS = 16


def shot_background() -> tuple[np.ndarray, int]:
    img = background()
    cells = np.zeros((H // 8, W // 4), bool)
    cells[ZONE_ROWS[0]:ZONE_ROWS[1], :ZONE_COLS] = True
    n = to_palette(img, cells)
    return img, n


def shape_planes(body: Body) -> list[bytes]:
    """Rungon kuva neljällä MC-esisiirrolla solumuodossa: rivi r, sarake c -> (r >> 3) * 128 + c * 8 + (r & 7).
    Maski (00 = koneen pikseli, 11 = tausta näkyy) ja data (roolit %01-%11, musta %00)."""
    h, w = body.img.shape
    assert w + NSHIFT - 1 <= BODY_COLS * 4, w
    groups = (h + 7) // 8
    out = []
    for sh in range(NSHIFT):
        mask = bytearray(b"\xff" * groups * 128)
        data = bytearray(groups * 128)
        for r in range(h):
            for x in range(w):
                c = int(body.img[r, x])
                if c == T:
                    continue
                X = x + sh
                o = (r >> 3) * 128 + (X >> 2) * 8 + (r & 7)
                b = 6 - 2 * (X & 3)
                mask[o] &= ~(3 << b) & 255
                data[o] |= ROLE[c] << b
        out.append(bytes(mask) + bytes(data))
    return out


EXHAUST = (-3.8, 3.15, 0.65)                   # pakoputken suu paikallisissa metreissä (kuoppa2._loader)


def puff_sprites() -> bytes:
    """Pakokaasun savu kolmena hires-spritenä (pieni, keski, iso): katkoviivadither pyöreässä pilvessä."""
    out = bytearray()
    for r in (3.0, 5.5, 8.5):
        spr = bytearray(64)
        for y in range(21):
            for x in range(24):
                dx, dy = (x - 11.5) / 1.0, (y - 10) * 1.6
                d = math.hypot(dx, dy) / r
                if d < 1.0 and DASH[y % 4, x % 8] < 0.85 - 0.5 * d:
                    spr[y * 3 + x // 8] |= 0x80 >> (x % 8)
        out += spr
    return bytes(out)


def clip_body(body: Body) -> Body:
    """Rungon rivit, jotka voivat näkyä kuva-alueella koko ajon aikana (alempana kuvan alareunan alla)."""
    ymin = min(int(round(path_anchor(state(f)[0])[1])) for f in range(0, FRAMES + 1, STEP))
    h = H - (ymin + body.oy)
    return Body(body.img[:h].copy(), body.glass[:h].copy(), body.ox, body.oy)


ARM_TONE = 5                                   # nostovarsien sävy (PAT)
GRAINS = 180                                   # kippauksen jyvät yhteensä
POUR_MAX = 14                                  # uusia jyviä enintään askelta (4 kehystä) kohden
SHAKE = (250, 278)                             # ravistus: yksittäisiä jyviä joka toinen askel
LANES = 8                                      # jyvän paikka kauhan huulella (puolelta 0 puolelle 1)
DUMP = (0.45, 60, 10)                          # kippauksen asento (s, nostokulma, kallistus) putoamiskohtiin


def landing() -> tuple[list[int], list[int], int, int]:
    """Huulen kaistojen putoamiskohdat maastoon (ruudun y) kippausasennossa ja valumisen suunta luiskaa alas
    (8.8 MC-px kehyksessä, noin 0,5 px)."""
    s, ia, ip = DUMP
    org = origin(s)
    px, py = pin(alpha(ia))
    p = phi(ip)
    c, sn = math.cos(p), math.sin(p)
    x, y = BUCKET[2]
    a = world((px + c * x - sn * y, py + sn * x + c * y, -BUCKET_Z), org)
    b = world((px + c * x - sn * y, py + sn * x + c * y, BUCKET_Z), org)
    xs, ys, dirs = [], [], []
    for t in range(LANES):
        w = a + (b - a) * (t + 0.5) / LANES
        h = float(k2.pit_h(np.array(w[0]), np.array(w[2])))
        g = np.array((w[0], h, w[2]))
        sx_, sy_ = proj(g)
        xs.append(int(round(sx_)))
        ys.append(min(int(round(sy_)), H - 1))
        e = 0.2
        gx = float(k2.pit_h(np.array(g[0] + e), np.array(g[2])) - k2.pit_h(np.array(g[0] - e), np.array(g[2]))) / (2 * e)
        gz = float(k2.pit_h(np.array(g[0]), np.array(g[2] + e)) - k2.pit_h(np.array(g[0]), np.array(g[2] - e))) / (2 * e)
        d = np.array((-gx, 0.0, -gz))
        d = d / (np.linalg.norm(d) + 1e-9) * 0.3
        d[1] = -0.3 * math.hypot(gx, gz)
        dirs.append(proj(g + d) - proj(g))
    v = np.mean(dirs, 0)
    v = v / (np.linalg.norm(v) + 1e-9) * 0.5
    return xs, ys, int(round(v[0] * 256)), int(round(v[1] * 256))


def _sb(v) -> int:
    v = int(round(float(v)))
    assert -128 <= v < 128, v
    return v & 255


def export(out) -> dict:
    """Kuvan 1 data: k1.bin (tausta), k1shape0-3.bin, k1puff.bin (savu), k1*.asm ja kpcommon.asm (taulut ja vakiot)."""
    from pathlib import Path
    out = Path(out)
    bg, changed = shot_background()
    body = clip_body(render_body())
    (out / "k1puff.bin").write_bytes(puff_sprites())
    Tb = tables()
    for sh, plane in enumerate(shape_planes(body)):
        (out / f"k1shape{sh}.bin").write_bytes(plane)
    L = []
    LB = []                                        # pankin 1 data ($5a00-, kp1c): kankaan ja varsien taulut
    LS = []                                        # pankin 2 data ($9a00-, kp1b): kulun taulut
    LT = []                                        # pankin 1 data ($7e10-, kp1c): pinnat ja pultit
    LC = []                                        # pankin 3 data ($c000-, kp1d): varsien kärjet

    def tab(name, vals, out_=None):
        vals = list(vals)
        L_ = L if out_ is None else out_
        L_.append(f"{name}")
        for i in range(0, len(vals), 16):
            L_.append("        .byte " + ", ".join(f"${v & 255:02x}" for v in vals[i:i + 16]))

    consts = {}
    steps = [state(f) for f in range(0, FRAMES + STEP, STEP)]
    anc = [np.round(path_anchor(s)).astype(int) for s, *_ in steps]
    tab("ST_AX", [a[0] for a in anc], LS)
    tab("ST_AY", [a[1] for a in anc], LS)
    steps2 = [state(f) for f in range(0, FRAMES + 2, 2)]             # asennot 2 kehyksen välein
    tab("ST_IA", [int(round(ia)) for _, ia, _, _ in steps2], LS)
    tab("ST_IP", [int(round(ip)) for _, _, ip, _ in steps2], LS)
    tab("ST_WT", [wheel_turn(s) for s, *_ in steps], LS)
    tab("ST_LD", [1 if ld > 0.05 else 0 for *_, ld in steps], LS)
    pour, acc, prev = [], 0.0, steps[0][3]
    for i, (*_, ld) in enumerate(steps):           # kipattavat jyvät askelta kohden: kuorman väheneminen (ease:
        acc += max(0.0, prev - ld) * GRAINS        # virta alkaa ohuena, paksunee ja ohenee) ja ravistuksen valuma
        prev = ld
        n = min(int(acc), POUR_MAX)
        acc -= n
        if not n and SHAKE[0] <= i * STEP < SHAKE[1] and i % 2:
            n = 1
        pour.append(n)
    tab("ST_PR", pour)
    tab("FALL", [min(255, int(round(0.5 * 0.226 * a * a))) for a in range(64)])   # putoamismatka iän mukaan (MC-px, LB)
    lx, ly, sdx, sdy = landing()
    tab("LAND_X", lx, LB)
    tab("LAND_Y", ly, LB)
    consts.update({"SLIDE_DX": sdx, "SLIDE_DY": sdy, "LANES": LANES})
    arm = Tb["arm"]
    for j in range(2):                             # varren j kärki k nostokulman mukaan (pankki 3 $c000-)
        for kk in range(4):
            tab(f"AX{j}{kk}", [_sb(arm[i, j, kk, 0]) for i in range(NA)], LC)
            tab(f"AY{j}{kk}", [_sb(arm[i, j, kk, 1]) for i in range(NA)], LC)
    tab("PINX", [_sb(v) for v in Tb["pin"][:, 0]], LS)
    tab("PINY", [_sb(v) for v in Tb["pin"][:, 1]], LS)
    bk = Tb["bucket"]
    for j in range(2):                         # puolittain, jotta indeksi ip * 5 + kärki mahtuu 8 bittiin
        tab(f"BKX{j}", [_sb(bk[i, kk, j, 0]) for i in range(NP) for kk in range(5)])
        tab(f"BKY{j}", [_sb(bk[i, kk, j, 1]) for i in range(NP) for kk in range(5)])
    F = bucket_faces()
    tab("FTONE", [(int(Tb["tone"][i, fi]) if Tb["vis"][i, fi] else 255) for i in range(NP) for fi in range(len(F))], LT)
    verts = []
    for f in F:
        verts += [kk * 2 + j for kk, j in f] + [255] * (5 - len(f))
    tab("FVERT", verts, LB)
    hub = Tb["hub"]
    tab("HUBX", [_sb(hub[w, t, b, 0]) for w in range(len(WHEELS)) for t in range(NT) for b in range(3)], LT)
    tab("HUBY", [_sb(hub[w, t, b, 1]) for w in range(len(WHEELS)) for t in range(NT) for b in range(3)], LT)
    pat = []
    yy, xx = np.mgrid[0:4, 0:8]
    for tone in range(7):
        lo, frac = tone // 2, (tone % 2) * 0.5
        px = np.where(frac > DASH[yy, xx], FILL_ROLES[min(lo + 1, 3)], FILL_ROLES[lo])   # roolit 0, 2, 3
        for r in range(4):
            for half in range(2):
                b = 0
                for q in range(4):
                    b |= int(px[r, half * 4 + q]) << (6 - 2 * q)
                pat.append(b)
    bar = []                                     # varren kuvio sarakkeen pikseliin: [(x & 7) * 8 + rivi & 7]
    for c in range(8):
        for r in range(8):
            b = pat[ARM_TONE * 8 + (r & 3) * 2 + ((c >> 2) & 1)]
            bar.append(b & (3 << (6 - 2 * (c & 3))))
    tab("BARTAB", bar, LB)
    (out / "kpcommon.asm").write_text("; kuormaaja.py export: täytön kuviot (kaikki kuvat)\nPAT\n" + "".join(
        "        .byte " + ", ".join(f"${v:02x}" for v in pat[i:i + 8]) + "\n" for i in range(0, len(pat), 8)))
    h, w = body.img.shape
    consts |= {"BODY_H": h, "BODY_COLS": BODY_COLS, "BODY_OX": body.ox, "BODY_OY": body.oy, "NSTEP": len(steps),
              "ZONE_Y0": ZONE_ROWS[0] * 8, "ZONE_Y1": ZONE_ROWS[1] * 8, "NFACE": len(F), "MOUTH": MOUTH,
              "NT": NT, "NWHEEL": len(WHEELS), "STEP": STEP}
    ex, ey = proj(world(EXHAUST)) - _anchor()
    consts |= {"EXH_DX": int(round(ex)), "EXH_DY": int(round(ey))}
    # spritekankaat (24 x 42 MC-px): varsien origo nostokulman, kauhan origo (tapista) kallistuksen mukaan
    used_ia = {int(round(ia)) for _, ia, _, _ in steps2}
    used_ip = {int(round(ip)) for _, _, ip, _ in steps2}
    ao = []
    for i in range(NA):
        v = np.round(arm[i]).reshape(-1, 2)
        lo, hi = v.min(0), v.max(0)
        assert i not in used_ia or ((hi - lo)[0] < 24 and (hi - lo)[1] < 42), (i, hi - lo)
        ao.append(lo)
    tab("ARH", [min(42, int(np.round(arm[i]).reshape(-1, 2)[:, 1].max() - ao[i][1]) + 2) for i in range(NA)], LB)
    tab("AOX", [_sb(o[0]) for o in ao], LS)
    tab("AOY", [_sb(o[1]) for o in ao], LS)
    bo = []
    for i in range(NP):
        v = np.round(bk[i]).reshape(-1, 2)
        lo, hi = v.min(0), v.max(0)
        assert i not in used_ip or ((hi - lo)[0] < 24 and (hi - lo)[1] < 42), (i, hi - lo)
        bo.append(lo)
    tab("BKH", [min(42, int(np.round(bk[i]).reshape(-1, 2)[:, 1].max() - bo[i][1]) + 2) for i in range(NP)], LB)
    tab("BOX", [_sb(o[0]) for o in bo])
    tab("BOY", [_sb(o[1]) for o in bo])
    hc = hub[:, :, :, :].mean(axis=(1, 2))                     # navan keskikohta pyörittäin
    tab("HCX", [_sb(c[0]) for c in hc])
    tab("HCY", [_sb(c[1]) for c in hc])
    trs = []                                       # kangas -> MC-sprite: 0 musta -> %01, 1 tyhjä -> %00,
    for b in range(256):                           # 2 oranssi -> %11 ($d026), 3 keltainen -> %10 (oma)
        o = 0
        for q in range(4):
            r = (b >> (6 - 2 * q)) & 3
            o |= (1, 0, 3, 2)[r] << (6 - 2 * q)
        trs.append(o)
    tab("TRS", trs, LB)
    head = [f"{k} = {v}" for k, v in consts.items()]
    (out / "k1data.asm").write_text("; kuormaaja.py export (kuva 1)\n" + "\n".join(head + L) + "\n")
    (out / "k1arm.asm").write_text("; kuormaaja.py export (kuva 1, pankki 3 $c000-)\n" + "\n".join(LC) + "\n")
    (out / "k1t2.asm").write_text("; kuormaaja.py export (kuva 1, pankki 1 $7e10-)\n" + "\n".join(LT) + "\n")
    (out / "k1st.asm").write_text("; kuormaaja.py export (kuva 1, pankki 2 $9a00-)\n" + "\n".join(LS) + "\n")
    (out / "k1bank.asm").write_text("; kuormaaja.py export (kuva 1, pankki 1 $5a00-)\n" + "\n".join(LB) + "\n")
    return {"changed_px": changed, "body": (h, w), "steps": len(steps), "bg": bg}
