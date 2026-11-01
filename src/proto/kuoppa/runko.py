"""Kuva 2: Lohjantähden runko nousee (kuoppa2.runko_v2:n kamera ja rakennus). Host tekee staattisen datan: alkukuvan
(perustus, kerrokset 0) ja valmiin kuvan (3 kerrosta, torni 5) yhteisellä solupaletilla, jotta 6510 voi paljastaa
valmiin kuvan pikseleitä ilman värimuistin vaihtoja, ja rakennusjärjestyksen tavusarakkeiden ajoina: pilarit
kasvavat kerros kerrallaan alhaalta ylös aaltona julkisivua pitkin, välipohja valetaan pilarilta toiselle, sisus
täyttyy välipohjan alta, tornin ydin nousee koko ajan. 6510 kuljettaa ajoja reaaliajassa (kuoppa2.asm).
"""
from __future__ import annotations

import numpy as np

from concept import kuoppa2 as k2
from concept import star
from concept.c64 import lab, palette

H, W = 144, 160
FLOORS, TOWER = 3, 5
FL = k2.FL
STEP = 4                                       # ajan yksikkö (kehystä)
T_FLOOR = [100, 200, 300]                      # kerroksen pilarit alkavat (kuvan 2 kehykset; data latautuu ~100:aan)
T_PILLAR = 45                                  # pilarin kasvu
T_SLAB = 50                                    # välipohjan valu julkisivun yli
T_TOWER = (100, 545)                           # tornin ydin ja teräsrunko


# ------------------------------------------------------------------ nosturi (6510 piirtää puomin spriteihin)
CB = (6.0, -46.0, 34.0)                        # nosturin masto (x, z) ja huippu (kuoppa2._crane2)
SLEW = (-50.0, 20.0)                           # kääntö asteina konseptin asennosta (puomi kohti vasenta)
NS = 64                                        # kääntöaskeleet
SPR_X0, SPR_Y0 = 44, 0                         # spritelohko (4 x 2 X-levennettyä hires-spriteä, 96 x 42 MC-px)
SPR_W, SPR_H = 96, 42


def mast_only(img, cam) -> None:
    """Nosturista bittikarttaan vain masto ja huipun pukki (kuoppa2._crane2:n mastoviivat); puomi, vastapuomi,
    vaunu ja palkki piirretään spriteihin."""
    from concept.pixel import ORANGE, YELLOW
    bx, bz, top = CB
    for dx in (-0.9, 0.9):
        k2._line(img, cam, (bx + dx, 0, bz), (bx + dx, top, bz), YELLOW if dx < 0 else ORANGE)
    for k in range(int(top / 1.8)):
        k2._line(img, cam, (bx - 0.9, k * 1.8, bz), (bx + 0.9, k * 1.8 + 1.8, bz), ORANGE)
        k2._line(img, cam, (bx - 0.9, k * 1.8, bz), (bx + 0.9, k * 1.8, bz), ORANGE)
    k2._line(img, cam, (bx, top, bz), (bx, top + 7.0, bz), YELLOW)


def render(floors: int, tower: int) -> np.ndarray:
    """runko_v2 ilman puomia ja jalankulkijaa (6510 piirtää ne spriteihin)."""
    old, oldp = k2._crane2, k2._person
    k2._crane2 = mast_only
    k2._person = lambda img, cam, pos: None
    try:
        return k2.runko_v2(floors, tower)
    finally:
        k2._crane2, k2._person = old, oldp


WALK = (60, 599, 22.0, 42.5, 26.5)              # jalankulkija: kehykset, maailman x alku ja loppu, z


def walk_table() -> list[tuple[int, int, int, int]]:
    """Jalankulkija 4 kehyksen välein: (keskikohta x MC-px + 32, pään rivi, korkeus px, askelvaihe 0-15)."""
    import math
    f0, f1, xa, xb, z = WALK
    cam = k2.RUNKO_CAM
    out = []
    for f in range(0, 600 + STEP, STEP):
        u = min(max((f - f0) / (f1 - f0), 0.0), 1.0)
        wx = xa + (xb - xa) * u
        x0, y0 = cam.project((wx, 0.0, z))
        _, y1 = cam.project((wx, 1.75, z))
        h = min(int(round(y0 - y1)), 42)
        yb = y0 - k2.RUNKO_CROP
        ph = int(math.floor((wx - xa) / 0.7 * 8)) & 15           # askel 0,7 m: puoli vaihetta
        out.append((max(0, min(255, int(round(x0)) + 32)), max(0, int(round(yb)) - h), h, ph))
    return out


def crane_points(d: float) -> dict:
    """Puomin päät kääntökulmalla d (astetta): MC-px kuva-alueella."""
    import math
    bx, bz, top = CB
    a = math.atan2(4.0, -48.0) + math.radians(d)
    cam = k2.RUNKO_CAM

    def P(p):
        x, y = cam.project(p)
        return np.array((x, y - k2.RUNKO_CROP))
    return {"pT": P((bx, top + 1.2, bz)), "pB": P((bx, top, bz)), "apex": P((bx, top + 7.0, bz)),
            "tT": P((bx + 48 * math.cos(a), top + 1.2, bz + 48 * math.sin(a))),
            "tB": P((bx + 48 * math.cos(a), top, bz + 48 * math.sin(a))),
            "cT": P((bx - 14 * math.cos(a), top + 1.2, bz - 14 * math.sin(a))),
            "cB": P((bx - 14 * math.cos(a), top, bz - 14 * math.sin(a)))}


def images() -> tuple[np.ndarray, np.ndarray]:
    """Alku- ja valmis kuva yhteisellä paletilla (nosturista vain masto)."""
    return joint(render(0, 0), render(FLOORS, TOWER))


def joint(E: np.ndarray, F: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Kaksi kuvaa yhteisellä solupaletilla: soluissa, joissa liitto ylittää 3 väriä (musta on tausta),
    harvinaisimmat lähimpään (Lab) molemmissa kuvissa."""
    E, F = E.copy(), F.copy()
    L = lab(palette().astype(float))
    for cy in range(H // 8):
        for cx in range(W // 4):
            sl = (slice(cy * 8, cy * 8 + 8), slice(cx * 4, cx * 4 + 4))
            e, f = E[sl], F[sl]
            if (e == f).all():
                continue
            cols, cnt = np.unique(np.concatenate([e.ravel(), f.ravel()]), return_counts=True)
            nz = [(int(c), int(n)) for c, n in zip(cols, cnt) if c != 0]
            if len(nz) <= 3:
                continue
            keep = [c for c, _ in sorted(nz, key=lambda t: -t[1])[:3]]
            for arr in (E, F):
                cell = arr[sl]
                for c, _ in nz:
                    if c not in keep:
                        cell[cell == c] = min(keep + [0], key=lambda q: float(((L[c] - L[q]) ** 2).sum()))
    return E, F


def schedule(E: np.ndarray, F: np.ndarray) -> np.ndarray:
    """Jokaiselle muuttuvalle pikselille paljastuskehys (kuvan 2 paikallinen), muille -1."""
    tr = star.trace(k2.RUNKO_CAM)
    cr = slice(k2.RUNKO_CROP, k2.RUNKO_CROP + H)
    mat, U, V = tr.mat[cr], tr.U[cr], tr.V[cr]
    d = E != F
    t = np.full((H, W), -1.0)
    long_ = (mat == star.M_FRONT) | (mat == star.M_SIDE)
    umax = max(float(U[long_].max()), 1.0)
    un = U / umax
    k = np.clip(np.floor(V / FL), 0, FLOORS).astype(int)
    fv = V - k * FL
    pillar = (U % 6.0) < 0.75
    pidx = np.floor(U / 6.0)
    slab = fv < 0.55
    tf = np.array(T_FLOOR + [T_FLOOR[-1] + 100])
    t_p = tf[np.clip(k, 0, FLOORS)] + T_PILLAR * np.clip(fv / FL, 0, 1) + 1.5 * (pidx % 12)
    t_s = tf[np.clip(k - 1, 0, FLOORS)] + T_PILLAR + T_SLAB * un
    t_b = tf[np.clip(k, 0, FLOORS)] + T_PILLAR + T_SLAB * un + 18 + 12 * np.clip(fv / FL, 0, 1)
    tl = np.where(slab & (k >= 1), t_s, np.where(pillar, t_p, t_b))
    t = np.where(d & long_, tl, t)
    tower = (mat == star.M_TOWER_F) | (mat == star.M_TOWER_S)
    vt = float(V[tower & d].max()) if (tower & d).any() else 1.0
    t = np.where(d & tower, T_TOWER[0] + (T_TOWER[1] - T_TOWER[0]) * np.clip(V / vt, 0, 1), t)
    rest = d & (t < 0)                                                 # muut (esim. telineiden peitto): rivin mukaan
    yy = np.mgrid[0:H, 0:W][0]
    t = np.where(rest, T_TOWER[0] + (T_TOWER[1] - T_TOWER[0]) * (1 - yy / H), t)
    return t


def runs(E: np.ndarray, F: np.ndarray, t: np.ndarray) -> list[tuple]:
    """Tavusarakkeiden ajot: (aika STEP-yksikköinä, sarake, rivi, rivejä, maski, kehyksiä riviä kohden).
    Peräkkäiset rivit, joilla sama sarake ja maski ja aika kasvaa tasaisesti ylöspäin tai on sama, yhdistetään."""
    rows = []
    for c in range(W // 4):
        cells = {}
        for y in range(H):
            px = t[y, c * 4:c * 4 + 4]
            m = 0
            tt = []
            for q in range(4):
                if px[q] >= 0:
                    m |= 3 << (6 - 2 * q)
                    tt.append(px[q])
            if m:
                cells[y] = (m, min(tt))
        ys = sorted(cells)[::-1]                                       # alhaalta ylös
        cur = None
        for y in ys:
            m, tt = cells[y]
            if cur and cur["m"] == m and cur["y"] - 1 == y and tt >= cur["tlast"] - 0.5 and tt - cur["tlast"] <= 6:
                cur["y"] = y
                cur["n"] += 1
                cur["tlast"] = tt
            else:
                if cur:
                    rows.append(cur)
                cur = {"c": c, "y": y, "y0": y, "n": 1, "m": m, "t0": tt, "tlast": tt}
        if cur:
            rows.append(cur)
    out = []
    for r in rows:
        dur = r["tlast"] - r["t0"]
        rate = int(round(dur / max(r["n"] - 1, 1))) if r["n"] > 1 else 0
        out.append((int(r["t0"] // STEP), r["c"], r["y0"], r["n"], r["m"], min(rate, 15)))
    out.sort()
    return out


def encode_pair(E: np.ndarray, F: np.ndarray, back: tuple = (), back_rows: int = 0
                ) -> tuple[bytes, bytes, bytes, bytes]:
    """Molemmat kuvat samoilla solujen väreillä (ruutu ja värimuisti yhteiset): bittikartta E, bittikartta F,
    ruutu, värit VIC-järjestyksessä (40 saraketta, 18 riviä). back: taustavärit, jotka saavat roolin %01 riveillä
    < back_rows (spritet taustan edessä, rakennuksen takana: $d01b)."""
    bE, bF, scr, col = bytearray(H * 40), bytearray(H * 40), bytearray(H * 5), bytearray(H * 5)
    for cy in range(H // 8):
        for cx in range(W // 4):
            sl = (slice(cy * 8, cy * 8 + 8), slice(cx * 4, cx * 4 + 4))
            cols = sorted((set(np.unique(E[sl]).tolist()) | set(np.unique(F[sl]).tolist())) - {0})
            assert len(cols) <= 3, (cy, cx, cols)
            if cy * 8 < back_rows:
                cols.sort(key=lambda c: (c not in back, c))
            cols += [0] * (3 - len(cols))
            role = {0: 0}
            for i, c in enumerate(cols):
                role.setdefault(c, i + 1)
            scr[cy * 40 + cx] = cols[0] << 4 | cols[1]
            col[cy * 40 + cx] = cols[2]
            for img, bm in ((E, bE), (F, bF)):
                cell = img[sl]
                for y in range(8):
                    b = 0
                    for x in range(4):
                        b |= role[int(cell[y, x])] << (6 - 2 * x)
                    bm[cy * 320 + cx * 8 + y] = b
    return bytes(bE), bytes(bF), bytes(scr), bytes(col)


# ------------------------------------------------------------------ jalankulkijan puhekupla
KUPLA_TEKSTI = ("MÄÄ NUKKUSI", "KU HEI HERÄTTIVÄ")   # kuplan kaksi riviä
KUPLA_KARKI = 43                                 # nuolen kärki (MC-px kuplan vasemmasta reunasta): hahmon pään kohta
KUPLA_N = 6                                      # spritejä vierekkäin (12 MC-px kukin)
_GLYF = {"E": ("###", "#..", "##.", "#..", "###"), "I": ("###", ".#.", ".#.", ".#.", "###"),
         "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#"), "A": (".##.", "#..#", "####", "#..#", "#..#"),
         "R": ("###.", "#..#", "###.", "#.#.", "#..#"), "T": ("###", ".#.", ".#.", ".#.", ".#."),
         "Ä": (".##.", "#..#", "####", "#..#", "#..#"), " ": (".", ".", ".", ".", "."),
         "N": ("#..#", "##.#", "#.##", "#..#", "#..#"), "U": ("#..#", "#..#", "#..#", "#..#", ".##."),
         "K": ("#..#", "#.#.", "##..", "#.#.", "#..#"), "S": (".##", "#..", ".#.", "..#", "##."),
         "H": ("#..#", "#..#", "####", "#..#", "#..#"), "V": ("#.#", "#.#", "#.#", "#.#", ".#.")}


def kupla() -> bytes:
    """Puhekupla KUPLA_N MC-spritenä vierekkäin (12 * KUPLA_N x 21 MC-px): ligne claire -ääriviiva ja teksti
    mustana (%01, $d025), sisus valkoisena (%10, spriten väri), nuoli alas hahmon päähän (kärki KUPLA_KARKI, rivi 20).
    Rivit: 0 ja 16 ääriviiva, teksti 2-6 ja 9-13 (Ä:n pisteet riviä ylempänä), nuoli 17-20."""
    W, H = 12 * KUPLA_N, 21
    g = np.zeros((H, W), np.uint8)
    for y in range(17):                          # pyöristetty suorakaide
        a = 2 if y in (0, 16) else 1 if y in (1, 15) else 0
        g[y, a:W - a] = 2
        if y in (0, 16):
            g[y, a:W - a] = 1
        else:
            g[y, a] = g[y, W - 1 - a] = 1
    k = KUPLA_KARKI
    for i, y in enumerate(range(16, 20)):        # nuoli: vasen reuna vinosti kärkeen, oikea pystysuoraan
        l, r = k - 4 + i, k + 1
        g[y, l:r + 1] = 2
        g[y, l] = g[y, r] = 1
    g[20, k] = 1
    for rivi, teksti in zip((2, 9), KUPLA_TEKSTI):
        lev = sum(len(_GLYF[c][0]) + 1 for c in teksti) - 1
        x = (W - lev) // 2
        for c in teksti:
            gl = _GLYF[c]
            if c == "Ä":
                g[rivi - 1, x] = g[rivi - 1, x + 3] = 1
            for yy, s in enumerate(gl):
                for xx, ch in enumerate(s):
                    if ch == "#":
                        g[rivi + yy, x + xx] = 1
            x += len(gl[0]) + 1
        assert x - 1 <= W - 2, (teksti, x)
    out = bytearray()
    for s in range(KUPLA_N):                     # spritet vasemmalta oikealle, 63 tavua + täyte
        for y in range(H):
            for b in range(3):
                v = 0
                for q in range(4):
                    v |= int(g[y, s * 12 + b * 4 + q]) << (6 - 2 * q)
                out.append(v)
        out.append(0)
    return bytes(out)


def export(out) -> dict:
    """k2.bin (alkukuva: bittikartta, ruutu, värit), k2runs.bin (ajot ja valmiin kuvan tavut) ja k2data.asm."""
    from pathlib import Path
    out = Path(out)
    E, F = images()
    t = schedule(E, F)
    R = runs(E, F, t)
    L = ["; runko.py export (kuva 2)", f"NRUN = {len(R)}"]
    from concept.pixel import BLUE, DGREY, LBLUE
    bE, bF, scr, col = encode_pair(E, F, back=(BLUE, LBLUE, DGREY), back_rows=SPR_Y0 + SPR_H)
    rb = bytearray()                       # ajo: aika / 4, sarake, alin rivi, rivejä, ~maski, kehystä/rivi, rivien tavut
    for tt, c, y0, n, m, r in R:           # (valmis & maski) alhaalta ylös
        assert max(tt, c, y0, n, m, r) < 256
        rb += bytes((tt, c, y0, n, m ^ 255, r))
        for i in range(n):
            y = y0 - i
            rb.append(bF[(y >> 3) * 320 + c * 8 + (y & 7)] & m)
    (out / "k2runs.bin").write_bytes(bytes(rb))
    import math
    sb = lambda v: int(round(float(v))) & 255                          # noqa: E731
    pts = [crane_points(SLEW[0] + (SLEW[1] - SLEW[0]) * i / (NS - 1)) for i in range(NS)]
    for key in ("tT", "tB", "cT", "cB"):
        for ax, nm in ((0, "X"), (1, "Y")):
            off = SPR_X0 if ax == 0 else SPR_Y0
            L.append(f"CR_{key.upper()}{nm} .byte " + ", ".join(str(sb(p[key][ax] - off)) for p in pts))
    p0 = pts[0]
    for key in ("pT", "pB", "apex"):
        L.append(f"CR_{key.upper()}X = {int(round(p0[key][0] - SPR_X0))}")
        L.append(f"CR_{key.upper()}Y = {int(round(p0[key][1] - SPR_Y0))}")
    # kääntö ja vaunu ajan funktiona (8 kehyksen välein): hidas edestakainen kääntö, vaunu ajaa ulos ja sisään
    sl, tu = [], []
    for f in range(0, 600 + 8, 8):
        u = f / 600.0
        sl.append(int(round((NS - 1) * (0.5 - 0.5 * math.cos(2 * math.pi * u * 1.0)))))
        tu.append(int(round(4 + 10 * (0.5 - 0.5 * math.cos(2 * math.pi * u * 2.0)))))
    wt = walk_table()
    W_ = ["; runko.py export: jalankulkija (kp2r)"]
    for i, nm in enumerate(("PW_X", "PW_Y", "PW_H", "PW_P")):
        W_.append(f"{nm}    .byte " + ", ".join(str(w[i]) for w in wt))
    # hahmon mittasuhteet korkeuden mukaan (konseptin _person): hiukset, kasvot, takki, jalat (kolmannekset), puolileveys
    rows = {"PF_HAIR": [], "PF_FACE": [], "PF_COAT": [], "PF_LEG": [], "PF_LEG2": [], "PF_W": []}
    for h in range(43):
        rows["PF_HAIR"].append(max(1, round(0.05 * h)))
        rows["PF_FACE"].append(max(2, round(0.13 * h)))
        rows["PF_COAT"].append(max(2, round(0.16 * h)))
        rows["PF_LEG"].append(round(0.58 * h))
        rows["PF_LEG2"].append(round(0.79 * h))
        rows["PF_W"].append(max(1, round(2.6 * h / 34)))
    for nm, v in rows.items():
        W_.append(f"{nm} .byte " + ", ".join(map(str, v)))
    (out / "k2walk.asm").write_text("\n".join(W_) + "\n")
    L.append("CR_S    .byte " + ", ".join(map(str, sl)))
    L.append("CR_U    .byte " + ", ".join(map(str, tu)))
    hx = [24 + 2 * (SPR_X0 + 24 * (i % 4)) for i in range(8)]
    L += [f"SPR_X0 = {SPR_X0}", f"SPR_Y0 = {SPR_Y0}", f"NSTEP2 = {len(sl)}",
          "SPR_HX = [" + ", ".join(map(str, hx)) + "]",
          "SPR_YS = [" + ", ".join(str(74 + SPR_Y0 + 21 * (i // 4)) for i in range(8)) + "]",
          f"SPR_MSB = {sum(1 << i for i, x in enumerate(hx) if x > 255)}"]
    (out / "k2data.asm").write_text("\n".join(L) + "\n")
    (out / "k2.bin").write_bytes(bE + scr + col)
    (out / "k2kupla.bin").write_bytes(kupla())
    return {"E": E, "F": F, "runs": len(R), "tmax": int(t.max())}
