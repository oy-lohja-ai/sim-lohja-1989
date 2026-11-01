"""Kyltin kirjaimisto kokoluokittain: versaaligroteski piirrettynä kynänvetoina ja rasteroituna jokaiseen
kirjainkorkeuteen erikseen (vedot naulataan pikseliruutuun ennen rasterointia, joten pystyvarret
ja vaakapalkit ovat jokaisessa koossa ehjiä, eikä mikään koko ole toisen skaalaus).

Kirjain määritellään keskiviivoina (janat ja kaaret) solun murto-osina: x 0 = vasemman varren keskiviiva,
1 = oikean; y 0 = ylä-, 1 = alapalkin keskiviiva. Kynä on tv px leveä ja th px korkea (pystyvarsi ja
vaakapalkki). Rasterointi näytteistää jokaisen pikselin 6 x 6 pisteellä ja sytyttää pikselin, kun puolet
pisteistä on kynän sisällä. 1 px:n vedoista poistetaan L-kulmat (pixel perfect -siivous), jotta vinot
vedot ovat portaita eivätkä paksuja.

  uv run --project tools/concept python src/proto/kyltti/font.py NÄYTE.png   # näytearkki kaikista koista
"""
from __future__ import annotations

import math

import numpy as np

# Leveys kirjainkorkeuden suhteena (neliöpikseleinä, ennen perspektiivin kavennusta).
WIDTH = {
    "A": .78, "B": .68, "C": .70, "D": .72, "E": .60, "F": .58, "G": .74, "H": .72, "I": 0, "J": .56,
    "K": .70, "L": .56, "M": .88, "N": .74, "O": .78, "P": .66, "Q": .78, "R": .68, "S": .66, "T": .66,
    "U": .72, "V": .76, "W": 1.04, "X": .74, "Y": .72, "Z": .64, "Ä": .78, "Ö": .78, "Å": .78,
    "0": .64, "1": .40, "2": .62, "3": .62, "4": .66, "5": .62, "6": .64, "7": .60, "8": .64, "9": .64,
    ".": 0, ",": 0, ":": 0, "!": 0, "'": 0, "-": .40, "+": .50, "/": .50, "&": .74, "#": .66, " ": .36,
}


STROKE = 0.11                 # vedon paksuus kirjainkorkeuksina


def pens(h: int, stem: float | None = None) -> tuple[int, int]:
    """(pystyvarren leveys, vaakapalkin korkeus) kirjainkorkeudelle h. stem = perspektiivin vaakaskaala
    pikseleinä (leveä kirjaimisto ei paksunna vetoa): pystyvarsi kapenee kulmassa samoin kuin kirjain,
    vaakapalkki ei. Ilman stem-arvoa suora näkymä (pikselin muoto 0,936)."""
    k = (1 / 0.936) if stem is None else stem
    return max(1, round(STROKE * h * k)), max(1, round(STROKE * h))


class Pen:
    """Yhden kirjaimen piirtoympäristö: solun leveys w ja korkeus h pikseleinä, naulatut koordinaatit."""

    def __init__(self, w: int, h: int, tv: int, th: int):
        self.w, self.h, self.tv, self.th = w, h, tv, th
        self.segs: list[tuple[float, float, float, float]] = []
        self.corners: list[tuple[float, float, int, int]] = []     # pyöristetyt kulmat (pienet koot)
        self.r = max(1.0, round(min(w, h) * 0.24))          # kulmien pyöristys keskiviivalla

    def X(self, f: float) -> float:
        return self.tv / 2 + round(f * (self.w - self.tv))

    def Y(self, f: float) -> float:
        return self.th / 2 + round(f * (self.h - self.th))

    def line(self, *pts):
        """Murtoviiva naulatuista pisteistä (x, y murto-osina)."""
        p = [(self.X(x), self.Y(y)) for x, y in zip(pts[::2], pts[1::2])]
        for (x0, y0), (x1, y1) in zip(p, p[1:]):
            self.segs.append((x0, y0, x1, y1))

    def raw(self, x0, y0, x1, y1):
        self.segs.append((x0, y0, x1, y1))

    def arc(self, cx, cy, rx, ry, a0, a1, n=12):
        """Kaari pikselikoordinaateissa, kulmat asteina (0 = oikea, 90 = alas)."""
        pts = [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            self.segs.append((x0, y0, x1, y1))

    def corner(self, xf, yf, sx, sy):
        """Pyöristetty kulma kohdassa (xf, yf): sx, sy = suunnat, joihin kulman vedot jatkuvat (+1/-1)."""
        self.corners.append((xf, yf, sx, sy))
        x, y = self.X(xf), self.Y(yf)
        r = min(self.r, (self.w - self.tv) / 2, (self.h - self.th) / 2)
        cx, cy = x + sx * r, y + sy * r
        a = {(1, 1): 180, (-1, 1): 270, (1, -1): 90, (-1, -1): 0}[(sx, sy)]
        self.arc(cx, cy, r, r, a, a + 90)
        return r

    def hbar(self, yf, x0f, x1f, r0=0, r1=0):
        """Vaakapalkki, päät lyhennettyinä pyöristyksen verran (r0 vasen, r1 oikea, pikseleinä)."""
        y = self.Y(yf)
        self.raw(self.X(x0f) + r0, y, self.X(x1f) - r1, y)

    def vbar(self, xf, y0f, y1f, r0=0, r1=0):
        x = self.X(xf)
        self.raw(x, self.Y(y0f) + r0, x, self.Y(y1f) - r1)

    def rbox(self, x0, y0, x1, y1, tl=1, tr=1, br=1, bl=1, sides="tlrb"):
        """Pyöristetty suorakaide murto-osina; kulmaliput 1 = pyöreä, sides = piirrettävät sivut."""
        rr = {}
        for key, flag, xf, yf, sx, sy in (("tl", tl, x0, y0, 1, 1), ("tr", tr, x1, y0, -1, 1),
                                          ("br", br, x1, y1, -1, -1), ("bl", bl, x0, y1, 1, -1)):
            rr[key] = self.corner(xf, yf, sx, sy) if flag else 0
        if "t" in sides:
            self.hbar(y0, x0, x1, rr["tl"], rr["tr"])
        if "b" in sides:
            self.hbar(y1, x0, x1, rr["bl"], rr["br"])
        if "l" in sides:
            self.vbar(x0, y0, y1, rr["tl"], rr["bl"])
        if "r" in sides:
            self.vbar(x1, y0, y1, rr["tr"], rr["br"])


def _draw(ch: str, p: Pen) -> None:
    L, V, H, B = p.line, p.vbar, p.hbar, p.rbox
    mid = 0.5
    if ch in "AÄÅ" and p.h <= 11:             # pienessä koossa vino jalka ei mahdu: pyöreäkattoinen A
        B(0, 0, 1, 1, bl=0, br=0, sides="tlr")
        H(0.55, 0, 1)
    elif ch in "AÄÅ":
        L(0, 1, 0.30, 0, 0.70, 0, 1, 1)
        # poikkipalkki jalkojen väliin
        y = p.Y(0.62)
        t = (y - p.Y(0)) / (p.Y(1) - p.Y(0))
        xa = p.X(0.30) + (p.X(0) - p.X(0.30)) * t
        xb = p.X(0.70) + (p.X(1) - p.X(0.70)) * t
        p.raw(xa, y, xb, y)
    elif ch == "B":
        V(0, 0, 1)
        r = p.corner(0.86, 0, -1, 1)
        H(0, 0, 0.86, 0, r)
        r2 = p.corner(0.86, mid, -1, -1)
        p.raw(p.X(0.86), p.Y(0) + r, p.X(0.86), p.Y(mid) - r2)
        H(mid, 0, 0.86, 0, r2)
        r3 = p.corner(1, mid, -1, 1)
        r4 = p.corner(1, 1, -1, -1)
        p.raw(p.X(1), p.Y(mid) + r3, p.X(1), p.Y(1) - r4)
        H(1, 0, 1, 0, r4)
        p.raw(p.X(0.86), p.Y(mid), p.X(1) - r3, p.Y(mid))
    elif ch == "C":
        B(0, 0, 1, 1, sides="tlb")
    elif ch == "D":
        B(0, 0, 1, 1, tl=0, bl=0)
    elif ch == "E":
        V(0, 0, 1)
        H(0, 0, 1)
        H(mid, 0, 0.82)
        H(1, 0, 1)
    elif ch == "F":
        V(0, 0, 1)
        H(0, 0, 1)
        H(mid, 0, 0.82)
    elif ch == "G":
        B(0, 0, 1, 1, sides="tlb", br=0)
        V(1, 0.55, 1)
        H(0.55, 0.55, 1)
    elif ch == "H":
        V(0, 0, 1)
        V(1, 0, 1)
        H(mid, 0, 1)
    elif ch == "I":
        V(0, 0, 1)
    elif ch == "J":
        r = p.corner(1, 1, -1, -1)
        V(1, 0, 1, 0, r)
        r2 = p.corner(0, 1, 1, -1)
        H(1, 0, 1, r2, r)
        V(0, 0.68, 1, 0, r2)
    elif ch == "K":
        V(0, 0, 1)
        L(0, 0.58, 1, 0)
        L(0.38, 0.40, 1, 1)
    elif ch == "L":
        V(0, 0, 1)
        H(1, 0, 1)
    elif ch == "M":
        V(0, 0, 1)
        V(1, 0, 1)
        L(0, 0, 0.5, 0.62, 1, 0)
    elif ch == "N":
        V(0, 0, 1)
        V(1, 0, 1)
        L(0, 0, 1, 1)
    elif ch in "OÖQ0":
        B(0, 0, 1, 1)
        if ch == "Q":
            L(0.58, 0.70, 1.05, 1.08)
    elif ch == "P":
        V(0, 0, 1)
        B(0, 0, 1, 0.55, tl=0, bl=0, sides="trb")
    elif ch == "R":
        V(0, 0, 1)
        B(0, 0, 1, 0.52, tl=0, bl=0, sides="trb")
        L(0.48, 0.52, 1, 1)
    elif ch == "S":
        r = p.corner(0, 0, 1, 1)
        H(0, 0, 1, r, 0)
        r2 = p.corner(0, mid, 1, -1)
        V(0, 0, mid, r, r2)
        r3 = p.corner(1, mid, -1, 1)
        H(mid, 0, 1, r2, r3)
        r4 = p.corner(1, 1, -1, -1)
        V(1, mid, 1, r3, r4)
        H(1, 0, 1, 0, r4)
    elif ch == "T":
        H(0, 0, 1)
        V(mid, 0, 1)
    elif ch == "U":
        B(0, 0, 1, 1, tl=0, tr=0, sides="lrb")
    elif ch == "V":
        L(0, 0, 0.5, 1, 1, 0)
    elif ch == "W":
        L(0, 0, 0.22, 1, 0.5, 0.30, 0.78, 1, 1, 0)
    elif ch == "X":
        L(0, 0, 1, 1)
        L(1, 0, 0, 1)
    elif ch == "Y":
        L(0, 0, 0.5, 0.52, 1, 0)
        V(mid, 0.52, 1)
    elif ch == "Z":
        H(0, 0, 1)
        L(1, 0, 0, 1)
        H(1, 0, 1)
    elif ch == "1":
        V(0.72, 0, 1)
        L(0, 0.26, 0.72, 0)
    elif ch == "2":
        r = p.corner(1, 0, -1, 1)
        H(0, 0, 1, 0, r)
        V(1, 0, 0.45, r, 0)
        L(1, 0.45, 0, 1)
        H(1, 0, 1)
    elif ch == "3":
        r = p.corner(1, 0, -1, 1)
        H(0, 0, 1, 0, r)
        r4 = p.corner(1, 1, -1, -1)
        V(1, 0, 1, r, r4)
        H(1, 0, 1, 0, r4)
        H(mid, 0.3, 1)
    elif ch == "4":
        V(0.8, 0, 1)
        L(0.8, 0, 0, 0.68)
        H(0.68, 0, 1)
    elif ch == "5":
        H(0, 0, 1)
        V(0, 0, 0.45)
        r = p.corner(1, 0.45, -1, 1)
        H(0.45, 0, 1, 0, r)
        r4 = p.corner(1, 1, -1, -1)
        V(1, 0.45, 1, r, r4)
        H(1, 0, 1, 0, r4)
    elif ch == "6":
        B(0, 0, 1, 1, sides="tlb", tr=0)
        B(0, 0.48, 1, 1, sides="tr", tl=0, bl=0)
    elif ch == "7":
        H(0, 0, 1)
        L(1, 0, 0.35, 1)
    elif ch == "8":
        B(0.06, 0, 0.94, mid)
        B(0, mid, 1, 1)
    elif ch == "9":
        B(0, 0, 1, 1, sides="trb", bl=0)
        B(0, 0, 1, 0.52, sides="lb", tr=0, tl=1, br=0)
    elif ch == ".":
        H(1, 0, 1)
    elif ch == ",":
        H(1, 0, 1)
    elif ch == ":":
        H(1, 0, 1)
        H(0.35, 0, 1)
    elif ch == "!":
        V(0, 0, 0.62)
        H(1, 0, 1)
    elif ch == "'":
        V(0, 0, 0.25)
    elif ch == "-":
        H(0.55, 0, 1)
    elif ch == "+":
        H(0.55, 0, 1)
        V(mid, 0.25, 0.85)
    elif ch == "/":
        L(1, 0, 0, 1)
    elif ch == "#":
        V(0.25, 0, 1)
        V(0.75, 0, 1)
        H(0.32, 0, 1)
        H(0.72, 0, 1)
    elif ch == "&":
        B(0.05, 0, 0.75, 0.42, sides="tlr")
        L(0.05, 0.42 - 0.1, 1, 1)
        L(0.75, 0.42 - 0.1, 0, 0.85)
        B(0, 0.6, 0.75, 1, sides="lb", tl=0, br=0)
    elif ch == " ":
        pass
    else:
        raise KeyError(ch)


def _raster(p: Pen, segs=None) -> np.ndarray:
    S = 6
    segs = p.segs if segs is None else segs
    img = np.zeros((p.h, p.w), bool)
    if not segs:
        return img
    off = (np.arange(S) + 0.5) / S
    ys, xs = np.mgrid[0:p.h, 0:p.w]
    px = (xs[..., None, None] + off[None, None, None, :]).astype(np.float64)
    py = (ys[..., None, None] + off[None, None, :, None]).astype(np.float64)
    px = np.broadcast_to(px, (p.h, p.w, S, S)) / p.tv
    py = np.broadcast_to(py, (p.h, p.w, S, S)) / p.th
    inside = np.zeros((p.h, p.w, S, S), bool)
    for x0, y0, x1, y1 in segs:
        ax, ay, bx, by = x0 / p.tv, y0 / p.th, x1 / p.tv, y1 / p.th
        dx, dy = bx - ax, by - ay
        ll = dx * dx + dy * dy
        if ll == 0:
            t = 0.0
        else:
            t = np.clip(((px - ax) * dx + (py - ay) * dy) / ll, 0, 1)
        d2 = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
        inside |= d2 <= 0.25 + 1e-9
    return inside.mean(axis=(2, 3)) >= 0.5


def _pixel_perfect(g: np.ndarray, keep: np.ndarray | None = None) -> np.ndarray:
    """1 px:n vedot portaiksi: poista L-kulman kärkipikseli, kun sillä on tasan yksi pysty- ja yksi
    vaakanaapuri, niiden välinen vinonaapuri puuttuu ja kulma ei ole kahden suoran vedon oikea kulma
    (molemmat naapurit jatkuvat suoraan 2 px). keep = suorien vetojen pikselit, joita ei poisteta
    (vinon vedon ja palkin liitos, esim. Z:n kulmat)."""
    g = g.copy()
    h, w = g.shape

    def at(yy, xx):
        return 0 <= yy < h and 0 <= xx < w and bool(g[yy, xx])
    changed = True
    while changed:
        changed = False
        for y in range(h):
            for x in range(w):
                if not g[y, x]:
                    continue
                n, s, e, wv = at(y - 1, x), at(y + 1, x), at(y, x + 1), at(y, x - 1)
                if n + s + e + wv != 2 or (n and s) or (e and wv):
                    continue
                vy = -1 if n else 1
                hx = 1 if e else -1
                if at(y + vy, x + hx):
                    continue
                if at(y + 2 * vy, x) and at(y, x + 2 * hx):
                    continue
                if keep is not None and keep[y, x]:
                    continue
                g[y, x] = False
                changed = True
    return g


def _cut_corners(g: np.ndarray, p: Pen) -> None:
    """Pienissä koissa kaaren säde on alle pikselin: pyöristetty kulma = kulmapikseli pois, kun molemmat
    sen viereiset vedot ovat olemassa (O erottuu D:stä, C ja G pyöreinä)."""
    h, w = g.shape
    for xf, yf, sx, sy in p.corners:
        x = int(p.X(xf) - p.tv / 2) if sx == 1 else int(p.X(xf) + p.tv / 2) - 1
        y = int(p.Y(yf) - p.th / 2) if sy == 1 else int(p.Y(yf) + p.th / 2) - 1
        if 0 <= x < w and 0 <= y < h and 0 <= x + sx < w and 0 <= y + sy < h:
            if g[y, x + sx] and g[y + sy, x]:
                g[y, x] = False


def glyph(ch: str, h: int, kx: float, wmax: int | None = None, stem: float | None = None) -> np.ndarray:
    """Kirjain ch kirjainkorkeudella h: bool-matriisi (h, w). kx = vaakaskaala (perspektiivin kavennus
    ja pikselin muoto), leveys = WIDTH * h * kx pikseleinä, enintään wmax."""
    tv, th = pens(h, stem)
    if ch in "ÄÖ":
        body = h - 2 if h < 12 else h - max(3, round(h * 0.2))
        g0 = glyph("A" if ch == "Ä" else "O", body, kx * h / body, wmax, stem)
        w = g0.shape[1]
        out = np.zeros((h, w), bool)
        out[h - body:] = g0
        dw = max(1, tv)
        a, b = round(w * 0.28) - dw // 2, round(w * 0.72) - (dw + 1) // 2
        dh = 1 if h < 14 else th
        out[0:dh, a:a + dw] = True
        out[0:dh, b:b + dw] = True
        return out
    if ch == "Å":
        body = h - 2 if h < 12 else h - max(3, round(h * 0.2))
        g0 = glyph("A", body, kx * h / body, wmax, stem)
        w = g0.shape[1]
        out = np.zeros((h, w), bool)
        out[h - body:] = g0
        c = w // 2
        out[0, max(0, c - 1):c + 1] = True
        return out
    if WIDTH[ch] == 0:
        w = tv
    else:
        w = round(WIDTH[ch] * h * kx)
        if wmax is not None:
            w = min(w, wmax)
        w = max(tv * 2 + (3 if ch in "MW" else 1), w)      # M ja W tarvitsevat keskikärjen
    if ch in ".,:!'":
        w = tv
    p = Pen(w, h, tv, th)
    if ch == ".":
        p.raw(tv / 2, h - th / 2, tv / 2, h - th / 2)
    elif ch == ",":
        p.raw(tv / 2, h - th / 2, tv / 2, h + 0.4)
    elif ch == ":":
        p.raw(tv / 2, h - th / 2, tv / 2, h - th / 2)
        y = round(h * 0.35)
        p.raw(tv / 2, y + th / 2, tv / 2, y + th / 2)
    elif ch == "!":
        p.raw(tv / 2, th / 2, tv / 2, round(h * 0.62))
        p.raw(tv / 2, h - th / 2, tv / 2, h - th / 2)
    elif ch == "'":
        p.raw(tv / 2, 0.5, tv / 2, max(1.5, h * 0.25))
    else:
        _draw(ch, p)
    g = _raster(p)
    if tv == 1 and th == 1:
        orth = _raster(p, [sg for sg in p.segs if sg[0] == sg[2] or sg[1] == sg[3]])
        g = _pixel_perfect(g, orth)
    if h <= 12:
        _cut_corners(g, p)
    return g
