"""Alkuruudun (Oy Lohja AI -emblem) bittitarkka malli 6510-toteutuksen rinnalle.

Kaikki laskenta on samaa kokonaislukuaritmetiikkaa kuin src/proto/logo/logo.asm:ssa, joten VICE-kaappausta voi
verrata malliin pikseleittäin. Malli ei ole dataa: build.py vie levylle vain taulut (verkko, sini,
kertolaskun neliötaulut, perspektiivi, kuviot, värikartat), ja 6510 laskee jokaisen kuvan itse.

Putki (yksi 3D-kuva):
  1. tila aikajanasta (timeline.state): yaw, pitch, mittakaava S, valo, viivojen kasvu, tahkojen täyttö
  2. kertoimet: A_ij = R_ij * Sk >> 7 (8 bittiä), Z-rivi R_2j (Q7); tulot erillisille koordinaattiarvoille
  3. verteksit: X = sum(v8 * A) (Q9 MC px), Y (Q8 riviä), Z:n ylätavu -> perspektiivikorjaus g (Q8)
  4. näkyvyys: ruudun kiertosuunta lävistäjien ristitulosta
  5. sävy: mallikoordinaatiston valo (R^T L) pistetulona normaalin kanssa + kappaleen paikka -> taso 0..12
  6. merkit: jokainen särmä, jonka puolien kuviot eroavat, XOR:aa erotuksen pikselisarakkeisiinsa (rivi, jolta
     alempi tahko alkaa); pystysuora XOR-täyttö sarakkeittain tekee tahkoista umpinaisia (blitterin
     yhden kierroksen täyttö käännettynä pystyyn: bittikartan sarake on 8 tavun välein, X-rekisteri = sarake)
  7. viivat (lankamalli) ja heijastus samoilla rutiineilla
"""
from __future__ import annotations

import math

import timeline as tl
from mesh import Mesh, load_mesh

# ---------------------------------------------------------------- kangas
COLS = 20                       # tavusarakkeet (4 MC px), ruudun sarakkeet 10..29
ROWS = 168                      # kankaan rivit, ruudun rivit Y0..Y0+167
Y0 = 0                          # kankaan rivi 0 näyttöikkunan rivillä 0 (solurivin monikerta)
X0 = 10                         # kankaan sarake 0 ruudun merkkisarakkeessa 10
W = COLS * 4                    # 80 MC px
HZ = 119                        # vaakaviivan kankaan rivi (solurivin 14 alin rivi: heijastus alkaa solurivistä 15)
assert tl.HZ == HZ and HZ & 7 == 7
CXQ9 = (W // 2 - 2) << 9        # emblemin keskikohta Q9 MC px: 4 hires px keskeltä vasemmalle kuten alkuperäisessä animaatiossa
XS = 1.055                      # ruudun X-venytys alkuperäisen animaation pitokuvan muotoon pikselisuhteilla (lähde 26/25,
#                                 C64 0,936), vain kantojen ja keskipisteiden X
GAP = 80                        # heijastustaso GAP yksikköä palikoiden alapinnan alla: musta rako alakulmista kuten
#                                 alkuperäisessä animaatiossa (rako 220 perspektiivillä: pidon alussa 7-12, lopussa 3-5 riviä)

# ---------------------------------------------------------------- taulut
SIN = [round(127 * math.sin(i * 2 * math.pi / 1024)) for i in range(1024)]


def sin8(a):
    return SIN[a & 1023]


def cos8(a):
    return SIN[(a + 256) & 1023]


def v8(v):
    """mallin yksiköt -> 8 bittiä (+-1024 -> +-127)"""
    return int(round(v * 127 / 1024))


def n7(n):
    """normaali Q14 -> Q7 tavuksi (+16384 >> 7 = 128 ei mahdu: 127)"""
    return tuple(max(-127, min(127, x >> 7)) for x in n)


def s8(v):
    """tavu etumerkillisenä"""
    v &= 255
    return v - 256 if v > 127 else v


# 13 sävytasoa: musta, 25/50/75 % c1, c1, ... c3 (MC-koodit 00 tausta, 01 c1, 10 c2, 11 c3). Pystyraidat:
# sama tavu joka rivillä (pystysuora XOR-täyttö pitää tahkon sisällä vakion).
def _pat(codes):
    return (codes[0] << 6) | (codes[1] << 4) | (codes[2] << 2) | codes[3]


LEVELS = 13
PATTERN = []
for _lv in range(LEVELS):
    _base, _k = divmod(_lv, 4)
    _hi = min(_base + 1, 3)
    PATTERN.append(_pat([_hi if j < _k else _base for j in (0, 2, 1, 3)]) if _k else _pat([_base] * 4))
MASK = [0xC0, 0x30, 0x0C, 0x03]
RLEN = [0] + [65536 // n for n in range(1, 4096)]
RQ = [0, 65536] + [65536 // d for d in range(2, 256)]
FULL = [max(1, min(LEVELS - 3, (i * (LEVELS - 1) + 64) >> 7)) for i in range(256)]   # enintään 50 % keltaista: oranssin
#                                                 ja keltaisen sekoitus (alkuperäisen animaation vaalea oranssi), ei sitruunankeltaista
FULLS = [FULL[i * 5 >> 3] for i in range(256)]   # sivu- ja ylätahkot 5/8 kirkkaudella (3D-tuntu: etutahkot erottuvat)
CHECKER = True                  # True: parittomilla riveillä kuvio pyöritetty (shakkiruutu, kaksi ketjua ja kaksi
#                                 merkkiä per pikseli); False: pystyraidat, yksi ketju (25 %:n kuviot
#                                 näkyvät paksuina pystypalkkeina; 6510-koodi tukee vain True)


def rot1(b):
    return ((b >> 2) | (b << 6)) & 255


def rot2(b):
    return ((b >> 4) | (b << 4)) & 255


# 4 x 2 -laatta: 50 % shakkiruutu (pariton rivi 1 px siirrettynä), 25 ja 75 % 2 px siirrettynä
PATTERN_ODD = [(rot1(p) if lv % 4 == 2 else rot2(p)) if CHECKER else p for lv, p in enumerate(PATTERN)]


def toggle(e, y, x, de, do):
    """merkki pikselisarakkeeseen x riviltä y alkaen: yksi ketju (rivi y) tai shakkiruudulla kaksi (y ja y + 1)"""
    if CHECKER:
        assert y + 1 < ODDMAX or not do & MASK[x & 3], (y, x)   # pariton ketju ei käy ODDMAXin alla
        e[y][x >> 2] ^= (de if not y & 1 else do) & MASK[x & 3]
        e[y + 1][x >> 2] ^= (do if not y & 1 else de) & MASK[x & 3]
    else:
        e[y][x >> 2] ^= de & MASK[x & 3]


def dpair(l0, l1):
    """kahden tason kuvioiden erotus (parillinen, pariton rivi)"""
    return PATTERN[l0] ^ PATTERN[l1], PATTERN_ODD[l0] ^ PATTERN_ODD[l1]


REFL_COLORS = [(9, 9, 9)] * 2 + [(9, 0, 0)] * 3 + [(0, 0, 0)]   # heijastus (vain parilliset rivit) tummuu alkuperäisen animaation
#                                                 tapaan: ruskea, puolet ruskeasta (%10 musta), rivistä HZ + 41 musta
BEV = [0] + [1] * (LEVELS - 1)   # viisteen taso: tumma (25 % ruskea, 75 % musta; alkuperäisen animaation tumma viiste)
BW = 2                          # viisteen leveys (MC px)
REFL_SOLID = [0, 1, 1, 2, 2] + [6] * (LEVELS - 5)   # heijastus: taso 6 = %10 ja %01 vuorotellen, tummuminen solurivien
#                                 väreistä; täytön alussa (etutahkon taso alle 5) 25 ja 50 % ruskeaa (pidossa tasot 7-)


DET_MIN = 32                    # näkyvän tahkon kantadeterminantin alaraja
# kappaleiden välit ruudulla (välejä kasvatettu):
# etusärmien ero, tyhjää on yksi vähemmän. Alkuperäisen animaation pito (13,2 s) C64:n kuvauksella:
# alapalikat 2,8 hires px, vasen pino 2,5 riviä, timantti ja vasen ylä 3,5 hires px, timantti ja oikea ala 4,2 riviä
VALI_X = 3                      # palikat 0 -> 1 ja palikka 2 -> timantti: 2 tyhjää MC px
VALI_Y = 4                      # palikka 0 -> 2: 3 tyhjää riviä
VALI_DY = 5                     # palikka 1 -> timantti: 4 tyhjää riviä
DOFF = (7, 0, 0)                # timantin keskipisteen siirto (v8): lukituksessa x-väli valmiiksi oikein
DFLY = 3                        # lentävä timantti tämän verran ylempänä: lukituksessa y-väli valmiiksi oikein
ODDMAX = HZ + 6                 # pariton ketju päättyy tähän (palikoiden alakulmat + 1); heijastus vain parillisille
#                                 riveille (täysriviheijastus pudottaisi pidon alle 10 kuvan/s)


# ---------------------------------------------------------------- 3D
class Frame:
    """Yhden 3D-kuvan välitulokset (6510:n muistin vastineet)"""

    def __init__(self, m: Mesh):
        n = len(m.world)
        self.sx = [0] * n           # kankaan MC px
        self.sy = [0] * n           # kankaan rivi
        self.vis = [0] * len(m.faces)
        self.level = [0] * len(m.faces)
        self.rx = {}                # heijastuksen verteksit
        self.ry = {}


class Model:
    def __init__(self):
        self.m = load_mesh()
        m = self.m
        # kappaleet (palikat 0-2, timantti 3): keskipiste ja puolikanta v8-yksiköinä, verteksi = keskipiste +
        # sum(c_k * h_k * e_k), c_k = -1, 0, +1 (palikka: laatikko, timantti: 45 asteen neliö)
        self.ocen, self.oh, self.vc = [], [], [0] * len(m.world)
        for k in range(4):
            vs = [i for i in range(len(m.world)) if m.vblk[i] == k]
            if k < 3:
                p8 = [tuple(v8(c) for c in m.world[i]) for i in vs]
                lo = [min(p[j] for p in p8) for j in range(3)]
                h = [(max(p[j] for p in p8) - lo[j]) // 2 for j in range(3)]
                cen = [lo[j] + h[j] for j in range(3)]
                for i, p in zip(vs, p8):
                    self.vc[i] = tuple((p[j] > cen[j]) - (p[j] < cen[j]) for j in range(3))
            else:
                cen = [v8(c) + o for c, o in zip(m.snap, DOFF)]
                loc = [tuple(v8(c) for c in m.local[i]) for i in vs]
                h = [max(abs(p[j]) for p in loc) for j in range(3)]
                for i, p in zip(vs, loc):
                    assert all(p[j] in (-h[j], 0, h[j]) for j in range(3)), p
                    self.vc[i] = tuple((p[j] > 0) - (p[j] < 0) for j in range(3))
            self.ocen.append(tuple(cen))
            self.oh.append(tuple(h))
        # X-kannat ja -keskipisteet venytettyinä (Y ennallaan): bx = hx * mx, xc = cxs * a00
        self.ohx = [tuple(round(v * XS) for v in h) for h in self.oh]
        # välien verteksit (etutahkon kulmat, vc): palikka 0 oikea ala ja vasen ylä, palikka 1 vasen ala ja yläkulmat,
        # palikka 2 vasen ja oikea ala, timantin vasen ja ala kulma
        v = lambda k, c: next(i for i in range(len(m.world)) if m.vblk[i] == k and self.vc[i] == c)
        self.gapv = dict(r0=v(0, (1, -1, 1)), t0=v(0, (-1, 1, 1)), l1=v(1, (-1, -1, 1)), tl1=v(1, (-1, 1, 1)),
                         tr1=v(1, (1, 1, 1)), b2=v(2, (-1, -1, 1)), r2=v(2, (1, -1, 1)), dl=m.dfc[3], db=m.dfc[0])
        self.ocxs = [round(c[0] * XS) for c in self.ocen]
        self.kk = 2 * v8(1024 + GAP)                # heijastus: y' = -y - kk
        self.dets = [[0, 0, 0] for _ in range(4)]
        # tahkon näkyvyys: kulmien kerroinvektoreista lävistäjät a, b; ruudun ristitulo = -sum(f_kl D_kl),
        # f_kl = a_k b_l - a_l b_k (etumerkki riittää: tahko on yhdessä tasossa)
        self.fsgn = []
        for f in m.faces:
            c = [self.vc[j] for j in f["v"]]
            a = [c[2][q] - c[0][q] for q in range(3)]
            b = [c[3][q] - c[1][q] for q in range(3)]
            fk = [a[i] * b[j] - a[j] * b[i] for i, j in ((0, 1), (0, 2), (1, 2))]
            self.fsgn.append([(x > 0) - (x < 0) for x in fk])
        self.ai_vy = self.ai_sizes()
        self.ai_stamps = [self.ai_stamp(vy) for vy in self.ai_vy]

    # ------------------------------------------------------------ kertoimet ja verteksit
    @staticmethod
    def coeffs(st):
        """R = Rx(pitch) Ry(yaw): ruutukertoimet A (X- ja Y-rivit, 8 bittiä) ja Z-rivi Q7"""
        sp, cp, sy, cy = sin8(st.pitch), cos8(st.pitch), sin8(st.yaw), cos8(st.yaw)
        r7 = [[cy, 0, sy],
              [(sp * sy) >> 7, cp, -((sp * cy) >> 7)],
              [-((cp * sy) >> 7), sp, (cp * cy) >> 7]]
        sk = st.sk
        a = [[(r7[i][j] * sk) >> 7 for j in range(3)] for i in range(2)]
        return a, r7

    @staticmethod
    def scale(v, g):
        """perspektiivikorjaus Q8: v + s8(v >> 8) * g"""
        return v + s8(v >> 8) * g

    def project_obj(self, st, k, mx, my, xc, yc, zc, refl=False, dox=0, doy=0):
        """kappale k: keskipiste ruudulla (xc Q9, yc Q8), sarakkeet mx/my (8 bittiä) -> verteksit.
        Rinnakkaisprojektio: kaltevuudet pieniä (yaw +-30, pitch 9 astetta), perspektiivi ei näkyisi 80 px
        kankaalla mutta maksaisi kolmanneksen verteksilaskennasta. zc jää syvyyden mittariksi."""
        h, hx = self.oh[k], self.ohx[k]
        bx = [hx[j] * mx[j] for j in range(3)]
        by = [h[j] * my[j] for j in range(3)]
        if refl:
            by[1] = -by[1]
        else:                                       # näkyvyys: kantaparien determinantit ylätavuista
            hb = [(s8(bx[j] >> 8), s8(by[j] >> 8)) for j in range(3)]
            self.dets[k] = [hb[i][0] * hb[j][1] - hb[i][1] * hb[j][0] for i, j in ((0, 1), (0, 2), (1, 2))]
        out = {}
        for i, c in enumerate(self.vc):
            if self.m.vblk[i] != k:
                continue
            xs = xc + sum(c[j] * bx[j] for j in range(3))
            ys = yc + sum(c[j] * by[j] for j in range(3))
            x = ((CXQ9 + xs + 256) >> 9) + dox
            y = ((st.ybq8 - ys + 128) >> 8) - doy
            out[i] = (x, y)
        return out

    def centre(self, k, a, r7, refl=False):
        cx, cy, cz = self.ocen[k]
        xc = self.ocxs[k] * a[0][0]                 # cz = 0 (build.py)
        yc = cx * a[1][0] + cy * a[1][1] + cz * a[1][2]
        zc = cx * r7[2][0] + cy * r7[2][1] + cz * r7[2][2]
        if refl:                                    # y' = -cy - kk (syvyys ja g kappaleen omat)
            yc -= (2 * cy + self.kk) * a[1][1]
        return xc, yc, zc

    def transform(self, st, fr):
        m = self.m
        a, r7 = self.coeffs(st)
        fr.a, fr.r7 = a, r7
        mx, my = (a[0][0], 0, a[0][2]), tuple(a[1])
        nk = 3 if (st.dmode == tl.D_FLY or not st.dvis) else 4
        for k in range(nk):
            for i, (x, y) in self.project_obj(st, k, mx, my, *self.centre(k, a, r7)).items():
                assert 0 <= x < W and 0 <= y < ROWS, (k, x, y)      # 6510 ei leikkaa
                fr.sx[i], fr.sy[i] = x, y
        self.gaps(st, fr)
        assert all(0 <= fr.sx[i] < W and 0 <= fr.sy[i] < ROWS for i in range(len(m.world))
                   if m.vblk[i] < nk), "välit veivät kankaan ulkopuolelle"
        if st.dvis and st.dmode == tl.D_FLY:
            self.transform_flight(st, fr, a, r7)

    def gaps(self, st, fr):
        """välit tarkalleen VALI_*: kappale siirtyy edellisen mukaan (maailman rako on noin 1,2 px, ja kappaleiden
        erillinen pyöristys liimaisi särmät kiinni ja irti kameran mukaan). Palikka 1 x (ja sen heijastus),
        palikka 2 y, lukittu timantti x ja y. Siirrot fr.gsh (heijastus käyttää palikan 1 x-siirtoa)."""
        m, g, c = self.m, self.gapv, tl.cues()
        sx, sy = fr.sx, fr.sy

        def move(k, arr, d):
            for i in range(len(m.world)):
                if m.vblk[i] == k:
                    arr[i] += d
        fr.gsh = 0
        if st.exiting:                              # purun kuvia ei näytetä (purku pyyhkii kuvan EX0 - 1)
            return
        if st.t >= c.land[1]:
            fr.gsh = sx[g['r0']] + VALI_X - sx[g['l1']]
            move(1, sx, fr.gsh)
        if st.t >= c.land[2]:
            move(2, sy, sy[g['t0']] - VALI_Y - sy[g['b2']])
        if st.dvis and st.dmode == tl.D_LOCK:
            move(3, sx, sx[g['r2']] + VALI_X - sx[g['dl']])
            move(3, sy, ((sy[g['tl1']] + sy[g['tr1']]) >> 1) - VALI_DY - sy[g['db']])

    def transform_flight(self, st, fr, a, r7):
        """lentävä timantti (lankamalli): oma kierto D (Q7) skaalattuna dsc:llä, M = R D', kappaleen
        perspektiivi ja ruutusiirtymä oikealta ylhäältä (e = 252..0)"""
        sx_, cx_ = sin8(st.drx), cos8(st.drx)
        sy_, cy_ = sin8(st.dry), cos8(st.dry)
        sz_, cz_ = sin8(st.drz), cos8(st.drz)
        yz = [[(cy_ * cz_) >> 7, -((cy_ * sz_) >> 7), sy_],
              [sz_, cz_, 0],
              [-((sy_ * cz_) >> 7), (sy_ * sz_) >> 7, cy_]]
        d = [yz[0], [(cx_ * yz[1][j] - sx_ * yz[2][j]) >> 7 for j in range(3)],
             [(sx_ * yz[1][j] + cx_ * yz[2][j]) >> 7 for j in range(3)]]
        dd = [[(d[i][j] * (st.dsc >> 1)) >> 7 for j in range(3)] for i in range(3)]
        mx = [(a[0][0] * dd[0][j] + a[0][2] * dd[2][j]) >> 7 for j in range(3)]
        my = [(a[1][0] * dd[0][j] + a[1][1] * dd[1][j] + a[1][2] * dd[2][j]) >> 7 for j in range(3)]
        for i, (x, y) in self.project_obj(st, 3, mx, my, *self.centre(3, a, r7), dox=st.dox, doy=st.doy + DFLY).items():
            fr.sx[i], fr.sy[i] = max(0, min(W - 1, x)), max(0, min(ROWS - 1, y))

    # ------------------------------------------------------------ näkyvyys ja sävy
    def cull_shade(self, st, fr):
        m = self.m
        lx, ly, lz = st.light_model(fr.r7)
        for i, f in enumerate(m.faces):
            fr.vis[i] = 0
            fr.level[i] = 0
            if m.inner[i] or f["n"][2] < -16000:
                continue
            if f["obj"] and not st.dvis:
                continue
            v = f["v"]
            dk = self.dets[m.vblk[v[0]]]
            if sum(q * d for q, d in zip(self.fsgn[i], dk)) <= DET_MIN:
                continue                      # ylätavujen tarkkuudella alle ~1 px suikale: ei näy
            fr.vis[i] = 1
            if f["obj"] and st.dmode == tl.D_FLY:
                continue                      # lankamalli: ei täyttöä
            w = st.face_level(i)
            if not w:
                continue
            n = n7(f["n"])
            dot = (n[0] * lx + n[1] * ly + n[2] * lz) >> 7
            inten = tl.AMBIENT + ((max(0, dot) * tl.DIFFUSE) >> 7) + st.obj[m.vblk[v[0]]]
            full = (FULL if f["n"][2] > 16000 else FULLS)[max(0, min(255, inten))]
            fr.level[i] = full if w == 255 else max(1, (full * (w >> 1) + 64) >> 7)

    # ------------------------------------------------------------ merkit ja täyttö
    @staticmethod
    def mark_edge(e, d, xa, ya, xb, yb):
        """särmä (xa, ya)-(xb, yb): pikselisarakkeet [min, max), merkki riville, jolta alempi puoli alkaa.
        Kaltevuus Q8 käänteistaulusta: |slope| = |dy| * RQ[dx] >> 8 (etumerkki dy:n), rivi = (acc >> 8), acc
        alkaa ya * 256 + slope / 2 + 127 (pikselin keskikohta, ceil(y - 0,5)). Rivit pysyvät päätepisteiden
        välissä (kankaalla), joten 6510 ei leikkaa; alemman rivin merkki voi osua varariville ROWS."""
        if xa == xb or not any(d):
            return 0
        if xa > xb:
            xa, ya, xb, yb = xb, yb, xa, ya
        dx, dy = xb - xa, yb - ya
        assert -128 <= dy <= 127, dy
        slope = (abs(dy) * RQ[dx]) >> 8
        if dy < 0:
            slope = -slope
        acc = ya * 256 + (slope >> 1) + 127
        de, do = d
        n = 0
        for x in range(xa, xb):
            y = acc >> 8
            acc += slope
            assert min(ya, yb) <= y <= max(ya, yb), (xa, ya, xb, yb, y)
            toggle(e, y, x, de, do)
            n += 1
        return n

    def render(self, t, out=None):
        """yksi kuva: palauttaa kankaan tavut [rivi][sarake] ja tilastot"""
        m = self.m
        st = tl.state(t)
        fr = Frame(m)
        self.transform(st, fr)
        self.cull_shade(st, fr)
        e = [[0] * COLS for _ in range(ROWS + 1)]          # + vararivi
        marks = 0
        pat = lambda f: fr.level[f] if f != 255 and fr.vis[f] else 0
        for a_, b_, f0, f1, _s, _l in m.edges:
            d = dpair(pat(f0), pat(f1))
            if any(d):
                marks += self.mark_edge(e, d, fr.sx[a_], fr.sy[a_], fr.sx[b_], fr.sy[b_])
        # viisteet: etutahkon varjon puolen reuna (palikoilla vasen, timantilla vasen ala) tummana BW MC px suikaleena
        # (alkuperäisen mallin LOD1-viisteet, 3D-tuntu); suikaleen pystyreunat eivät maksa merkkejä
        for f, a_, b_ in self.bevels():
            lv = fr.level[f] if fr.vis[f] else 0
            if lv:
                d = dpair(lv, BEV[lv])
                xa, ya, xb, yb = fr.sx[a_], fr.sy[a_], fr.sx[b_], fr.sy[b_]
                for p, q in (((xa, ya), (xb, yb)), ((xb, yb), (xb + BW, yb)), ((xb + BW, yb), (xa + BW, ya)),
                             ((xa + BW, ya), (xa, ya))):
                    marks += self.mark_edge(e, d, *p, *q)
        # kaiverrettu AI: kirjainten rajojen merkit valmiista leimasta (ai_stamp) etutahkon keskelle
        if st.ai and fr.vis[m.dfront] and fr.level[m.dfront]:
            lf = fr.level[m.dfront]
            la = max(1, (lf * 9) >> 4)
            de, do = dpair(lf, la)
            cx, cy, k = self.ai_place(fr)
            for dy, x in self.ai_stamps[k]:
                y, xx = cy + dy, cx + x
                toggle(e, y, xx, de, do)
                marks += 1
        # heijastus
        if any(st.refl_level):
            marks += self.reflection(st, fr, e)
        img = [[0] * COLS for _ in range(ROWS)]
        for c in range(COLS):
            acc = [0, 0]
            for y in range(ROWS):
                p = y & 1 if CHECKER else 0
                acc[p] ^= e[y][c]
                img[y][c] = acc[p]
        # viivat päälle
        self.strokes(st, fr, img)
        fr.img = img
        fr.st = st
        fr.marks = marks
        return fr

    def wipe(self):
        """purku pyyhkäisynä (src/proto/logo/hand.asm): viimeinen kuva (kehys ex0 - 1) jää, ja näkyvä alue on
        ruudun rivit [tb, rb): tb kulkee emblemin yläreunasta viivan alle c.wipet kehyksessä, rb heijastuksen alareunasta
        viivan alle c.wipe kehyksessä (kiihtyvät käyrät). Palauttaa listat tb, rb (c.wipe + 1 kehystä) ruudun riveinä
        (näyttöikkunan rivi 0 = 0)."""
        c = tl.cues()
        st = tl.state(c.ex0 - 1)
        fr = Frame(self.m)
        self.transform(st, fr)
        top = min(fr.sy[i] for i in range(len(self.m.world)) if st.dvis or i < self.m.nb)
        e = [[0] * COLS for _ in range(ROWS + 1)]
        self.reflection(st, fr, e)
        bot = max(y for _x, y in fr.rv.values()) + 2
        tb, rb = [], []
        # kiihtyy loppua kohti (kuva ei jää viivaksi: SMOOTH-käyrällä viimeiset kuvat olisivat lähes mustia), alkaa
        # 3/4 nopeudella (puhdas k^2 seisoisi alussa)
        acc = lambda k, n: min(k, n) * (min(k, n) + 3 * n) * 255 // (4 * n * n)    # noqa: E731
        for k in range(c.wipe + 1):
            tb.append(Y0 + top + (HZ + 1 - top) * acc(k, c.wipet) // 255)   # myös viivan rivi pois (ei jää viivaksi)
            rb.append(Y0 + bot - (bot - HZ - 1) * acc(k, c.wipe) // 255)
        return tb, rb

    def ai_sizes(self):
        """etutahkon pystylävistäjät (riviä) lukituksesta kohtauksen loppuun: leimojen koot"""
        c, b, t_ = tl.cues(), self.m.dfc[0], self.m.dfc[2]
        vys = set()
        for t in range(c.lock, c.length):
            st = tl.state(t)
            if st.dvis and st.dmode == tl.D_LOCK:
                fr = Frame(self.m)
                self.transform(st, fr)
                vys.add(fr.sy[b] - fr.sy[t_])
        return list(range(min(vys), max(vys) + 1))

    def ai_place(self, fr):
        """AI-leiman paikka: etutahkon keskipiste (ala- ja yläkulman keskikohta) ja koko pystylävistäjästä"""
        b, _r, t_, _l = self.m.dfc
        k = max(0, min(len(self.ai_vy) - 1, fr.sy[b] - fr.sy[t_] - self.ai_vy[0]))
        return (fr.sx[b] + fr.sx[t_]) >> 1, (fr.sy[b] + fr.sy[t_]) >> 1, k

    def ai_stamp(self, vy):
        """AI (mesh.ai_loops, etutahkon lävistäjien osina) rasteroituna MC-pikseleihin, kun vaakalävistäjä on
        (vy + 1) // 2 MC px (neliö: MC-pikseli on kaksi riviä leveä) ja pystylävistäjä vy riviä: (rivi, x) suhteessa keskipisteeseen jokaiselle sarakkeen
        sisä/ulko-vaihdolle (XOR-täytön merkit)."""
        m = self.m
        poly = [(a / 16384, b / 16384) for a, b in m.ai_v]
        ux = (round(vy * XS) + 1) // 2

        def inside(px, py):
            a, b = px / ux, -py / vy
            c = False
            for i0, i1 in m.ai_e:
                (xa, ya), (xb, yb) = poly[i0], poly[i1]
                if (ya > b) != (yb > b) and a < xa + (b - ya) * (xb - xa) / (yb - ya):
                    c = not c
            return c
        hx, hy = ux // 2 + 1, vy // 2 + 1
        out = []
        for x in range(-hx, hx + 1):
            prev = False
            for y in range(-hy, hy + 2):
                cur = inside(x + 0.5, y + 0.5) if y <= hy else False
                if cur != prev:
                    out.append((y, x))
                prev = cur
        return sorted(out)

    def bevels(self):
        """viisteet (tahko, ylä-, alakulma): etutahkojen (n_z suuri) vasen reuna v[3] -> v[0] (kulmat BL, BR, TR, TL;
        timantilla vasen -> ala)"""
        return [(i, f["v"][3], f["v"][0]) for i, f in enumerate(self.m.faces) if f["n"][2] > 16000]

    def refl_faces(self):
        """heijastuvat tahkot: alapalikoiden (0, 1) etutahkot"""
        m = self.m
        return [i for i, f in enumerate(m.faces) if not f["obj"] and m.vblk[f["v"][0]] <= 1 and f["n"][2] > 16000]

    def reflection(self, st, fr, e):
        """alapalikoiden etutahkojen peilikuva tason y = -1024 - GAP läpi (tosi heijastus kuten alkuperäisessä animaatiossa), kunkin
        palikan oma etutahkon taso (sävy peilautuu), vain parillisille riveille (vesi: parittomat rivit mustia,
        parittoman ketjun merkit 0); tummuminen solurivien väreistä (cell_colors)"""
        m = self.m
        a, r7 = fr.a, fr.r7
        mx, my = (a[0][0], 0, a[0][2]), tuple(a[1])
        rv = {}
        for k in (0, 1):
            for i, (x, y) in self.project_obj(st, k, mx, my, *self.centre(k, a, r7, True), refl=True).items():
                assert 0 <= x < W and HZ - 255 < y < 256, (k, x, y)    # 6510: rivi tavuna, ei leikkausta
                rv[i] = (x + (fr.gsh if k else 0), max(HZ + 1, min(ROWS - 1, y)))   # horisontin alle, kankaan loppuun
        n = 0
        for f in self.refl_faces():
            if not fr.level[f]:
                continue
            d = (PATTERN[REFL_SOLID[fr.level[f]]], 0)
            v = m.faces[f]["v"]
            for j in range(4):
                a_, b_ = v[j], v[(j + 1) & 3]
                n += self.mark_edge(e, d, rv[a_][0], rv[a_][1], rv[b_][0], rv[b_][1])
        fr.rv = rv
        return n

    def strokes(self, st, fr, img):
        m = self.m
        for a_, b_, f0, f1, start, ln in m.edges:
            dia = a_ >= m.nb or b_ >= m.nb
            if dia and st.dmode == tl.D_FLY:
                if not st.dvis:
                    continue
                p = 256
            else:
                s0 = st.solid(f0)
                s1 = True if f1 == 255 else st.solid(f1)
                if s0 and s1:
                    continue
                if dia and not st.exiting:
                    p = 256                     # lukittu timantti rautalankana täyttöön asti
                else:
                    g = st.grow[m.vblk[a_]] - start
                    if g <= 0:
                        continue
                    p = 256 if g >= ln else (g * RLEN[ln]) >> 8
            if not (fr.vis[f0] or (f1 != 255 and fr.vis[f1])):
                continue                                # takasärmät pois (myös lentävästä timantista)
            self.line(img, *self.part(fr.sx[a_], fr.sy[a_], fr.sx[b_], fr.sy[b_], p))

    @staticmethod
    def part(ax, ay, bx, by, p):
        """särmän kasvanut osa: p = 256 koko särmä, muuten loppupiste (b - a) * (p >> 1) >> 7"""
        if p == 256:
            return ax, ay, bx, by
        return ax, ay, ax + (((bx - ax) * (p >> 1)) >> 7), ay + (((by - ay) * (p >> 1)) >> 7)

    @staticmethod
    def line(img, x0, y0, x1, y1):
        """MC-viiva värillä 11 (OR) vasemmalta oikealle, Bresenham pääakselin mukaan, virhe 8-bittisenä
        0..d-1 (6510: lainaus = sivuaskel). Päätepisteet ovat kankaalla."""
        if x0 > x1:
            x0, y0, x1, y1 = x1, y1, x0, y0
        dx, dy, sy = x1 - x0, abs(y1 - y0), (1 if y1 >= y0 else -1)
        if dx >= dy:
            err = dx >> 1
            for x in range(x0, x1 + 1):
                img[y0][x >> 2] |= MASK[x & 3]
                err -= dy
                if err < 0:
                    err += dx
                    y0 += sy
        else:
            err = dy >> 1
            for _ in range(dy + 1):
                img[y0][x0 >> 2] |= MASK[x0 & 3]
                y0 += sy
                err -= dx
                if err < 0:
                    err += dy
                    x0 += 1


# ---------------------------------------------------------------- värit ja kuva
# solurivin värit (%01, %10, %11), kankaan solurivit 0..20; muut solut mustia
def cell_colors(cr):
    row = cr * 8
    if row + 7 <= HZ:
        return (9, 8, 7)                    # ruskea, oranssi, keltainen
    k = (row - HZ) // 8                     # heijastus: tummuva meripihka solurivi kerrallaan
    return REFL_COLORS[min(k, len(REFL_COLORS) - 1)]
