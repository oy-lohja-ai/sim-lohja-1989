"""Alkuruudun aikajana: kohtauksen kehys t (0 = kohtauksen alku) -> 3D-kuvan tila.

Oy Lohja AI -emblemin alkuperäisen animaation C64-versio: sama tahtirakenne (yksi palikka per tahdin alku, timantti
lentää lankamallina ja lukittuu välähdyksellä, nimi putoaa, lopussa tahkot tyhjenevät ja viivat vetäytyvät viivaan).
Kaikki on samaa kokonaislukulaskentaa kuin logo.asm:n state-rutiinissa: rampit vakiokertoimella
((t - a) * K) >> 8, K = 65536 // (b - a), käyrät ja iskun vaimeneminen tauluista.

Kohtauksen pituus L (kehyksiä) tulee aikajanalta (build.py: TIM_SCENE_ALKU_START..seuraava). Tahdit:
0 viiva leviää, 1-3 palikat, 4 lukitus, 5 nimi, viimeinen tahti purku; pito venyy väliin.
"""
from __future__ import annotations

import math

import mesh as _mesh

BAR = 120
BEAT = 30
LAT = 3                         # isku kuuluu 3 kehystä play-kutsun jälkeen
D_FLY, D_LOCK = 0, 1
L_SCENE = 960                   # oletuspituus (8 tahtia), build.py korvaa aikajanalta

SMOOTH = [int(round(255 * (x / 255) ** 2 * (3 - 2 * x / 255))) for x in range(256)]
EASE3 = [int(round(255 * (1 - (1 - x / 255) ** 3))) for x in range(256)]
# iskun nykäisy: d = 0..19 kehystä iskusta, (20 - d)^2 = 400..1
KYAW = [(20 - d) ** 2 * 7 // 400 for d in range(20)]
KPITCH = [(20 - d) ** 2 * 5 // 400 for d in range(20)]
KSCALE = [(20 - d) ** 2 * 4 // 400 for d in range(20)]
AMBIENT, DIFFUSE = 20, 95       # etutahkot tasoilla 8-10 valon kiertäessä (ei kyllästy maksimiin: sävy elää)
HZ = 119                        # = model.HZ (vaakaviivan kankaan rivi)
S4_BASE, S4_PUSH = 208, 24       # mittakaava alussa ja lähestymisen lisäys (Q2)
FILLSTAGES = 5                  # täytön porrastus: tahkojen keskipisteiden korkeudet ylhäältä alas (palikan 2 kansi,
#                                 timantin yläviiste, timantin etutahko, palikan 2 etu- ja sivutahkot, alapalikat)
FILLSTEP = 8                    # porrastuksen väli (kehyksiä): täytön ja rautalangan yhteiset kuvat ovat raskaimpia
#                                 (~108k sykliä, pito ~87k), joten porrastus lyhyt ja täyttö pitkä
FIN0 = 80                       # täytön ensimmäinen paino: etutahko 75 % ruskea (taso 3), kun rautalanka väistyy
#                                 (rautalanka täyttyvän tahkon päällä maksaisi ~38k sykliä kuvassa: alle 7 kuvaa/s)


def _lcam(i):
    """valon suunta kameran koordinaatistossa kulmalla i * 4 (alkuperäisen animaation pistevalo keskeltä katsottuna), Q7"""
    a = i * 4 * 2 * math.pi / 1024
    lx, ly, lz = math.sin(a) * 800, 600, 1800 + math.cos(a) * 700   # edestä (etutahkot kirkkaat, sivut
    #                                                                 tummemmat: alkuperäisen animaation 3D-tuntu)
    n = math.sqrt(lx * lx + ly * ly + lz * lz)
    return tuple(int(round(c / n * 127)) for c in (lx, ly, lz))


LCAM = [_lcam(i) for i in range(256)]
# kappaleen paikka valon suhteen (vasen ala, oikea ala, vasen ylä, timantti): obj = (cx * lx + cy * ly) >> 9
OBJC = [(-70, -70), (55, -70), (-70, 55), (63, 63)]


def kfac(a, b):
    return 65536 // (b - a)


def ramp(t, a, b):
    """0..255: 0 alussa, 255 lopussa"""
    if t <= a:
        return 0
    if t >= b:
        return 255
    return min(255, ((t - a) * kfac(a, b)) >> 8)


def span(d):
    """kasvu niin, että u = 255 riittää koko matkaan: d * 256 / 255 ylöspäin"""
    return -(-d * 256 // 255)


class Cues:
    def __init__(self, length=L_SCENE):
        self.length = length
        nbar = max(6, length // BAR)
        self.nbar = nbar
        B = lambda n: n * BAR + LAT
        # palikka joka tahdin alussa kuten alkuperäisessä animaatiossa: 1. nousee viivasta jo sen levitessä, 2. ja 3.
        # tahtien 1 ja 2 alussa, timantti lentää tahdilla 2 ja lukittuu tahdin 3 alkuun
        self.land = [LAT + BEAT, B(1), B(2)]
        self.done = [x + BAR * 2 // 5 for x in self.land]
        self.lock = B(3) - 2
        self.flash = B(3)
        self.fly0 = B(2) + BAR * 2 // 5
        # kaikki palikat ja timantti rautalankoina, kunnes koko emblemi on ruudussa (lukitus), sitten värit ja
        # heijastus tulevat ylhäältä alas (sw0..sw0 + swn). Emblem ei pysähdy täytön ajaksi: se liikkuu koko ajan, ja
        # tahkot täyttyvät liikkeen aikana ylhäältä alas porrastettuina (face_times), kukin ruskeasta lopulliseen
        # sävyyn lumaketjua pitkin rl kehyksessä (fill_ramp)
        self.sw0 = self.flash + BEAT
        # värit ja nimi samaan aikaan: nimi alkaa täytön kanssa, ja täyttö kestää, kunnes viimeinen kirjain on
        # pudonnut paikalleen
        import name as _nm
        self.name = self.sw0
        self.swn = (len(_nm.TEXT) - 1) * _nm.NSTEP + _nm.DROP.index(0) + 1
        self.fill0 = self.sw0 - 12                  # täyttö alkaa iskun nykäisyn jälkeen: muuten rautalankakuvat
        #                                             378-392 olisivat pikselilleen samat (kääntyminen alle 1 px)
        self.rl = self.sw0 + self.swn - self.fill0 - (FILLSTAGES - 1) * FILLSTEP   # tahkon täyttö: viimeinen täysi swn:ssä
        # pito 2 tahtia lukituksesta, sitten pyyhkäisy ja nimiruutu (alkuun demon nimi kuten alkuperäisessä
        # animaatiossa)
        self.ex0 = B(5) if nbar >= 7 else B(nbar - 1)
        self.ex1 = length - 6
        # purku: emblem pyyhkiytyy ylhäältä viivaan wipet kehyksessä, ja aaltoileva heijastus kutistuu viivaan
        # nimiruudun avautumiseen asti (wipe kehystä: TITLE ja TITLEC latautuvat purun aikana, osalevyllä valmiina
        # noin EX0 + 98, varaa hitaammalle asemalle)
        self.wipet = 45
        self.wipe = BAR
        self.title0 = self.ex0 + self.wipe         # nimiruutu avautuu viivasta (hand.asm title, title.py)
        # nimi jää purun ajaksi (spritet pankkiin 3, bank3) ja putoaa pois kirjain kerrallaan emblemin pyyhkäisyn
        # jälkeen (hand.asm hw_250 -> nmout), viimeinen ennen nimiruudun avautumista (sen spritet)
        self.nout = self.ex0 + self.wipet + 2
        assert self.nout + (len(_nm.TEXT) - 1) * _nm.OSTEP + len(_nm.ODROP) < self.title0
        self.topen = 36
        self.exg0, self.exg1 = self.ex0 + BAR * 3 // 10, self.ex1 - 6
        self.push0, self.push1 = B(1), self.ex0
        self.kicks = [B(n) for n in range(1, min(6, nbar - 1))]


class State:
    pass


_M = None
_CUES = Cues()
_FILL = None


def setup(length=L_SCENE):
    global _CUES, _FILL
    _CUES = Cues(length)
    _FILL = None


def cues():
    return _CUES


def mesh():
    global _M
    if _M is None:
        _M = _mesh.load_mesh()
    return _M


def face_times():
    """tahkon täyttö- ja tyhjennysaika (kehyksiä) kuten alkuperäisessä animaatiossa; täyttö porrastettuna
    ylhäältä alas"""
    global _FILL
    if _FILL is None:
        m, c = mesh(), _CUES
        fmax = max(m.fill)
        yc = [sum(m.world[v][1] for v in f["v"]) for f in m.faces]
        lv = sorted({y for i, y in enumerate(yc) if not m.inner[i] and m.faces[i]["n"][1] > -16000}, reverse=True)
        ft, ut = [], []
        for i, f in enumerate(m.faces):
            fl = m.fill[i]
            rank = min(FILLSTAGES - 1, sum(y > yc[i] for y in lv))
            ft.append(c.fill0 + rank * FILLSTEP)
            ut.append(c.ex0 + BAR * 32 // 100 * (fmax - fl) // fmax)
        _FILL = ft, ut
    return _FILL


def fill_ramp():
    """tahkon täyttöpaino täytön alusta (0..rl - 1 kehystä), sitten 255"""
    rl = _CUES.rl
    return [FIN0 + (d + 1) * (255 - FIN0) // rl for d in range(rl)]


def grow_all():
    return max(e[4] + e[5] for e in mesh().edges)


def state(t):
    from model import sin8   # noqa: E402  (sama taulu kuin 6510:llä)
    m, c = mesh(), _CUES
    s = State()
    s.t = t
    kd, side = -1, 1
    for n, k in enumerate(c.kicks):
        d = t - k
        if 0 <= d < 20:
            kd, side = d, (1 if n & 1 else -1)
    ky, kp, ks = (KYAW[kd], KPITCH[kd], KSCALE[kd]) if kd >= 0 else (0, 0, 0)
    push = SMOOTH[ramp(t, c.push0, c.push1)]
    tp = max(0, t - c.push0)
    sway = ((tp * 546) >> 8) & 1023
    s.yaw = (-72 + (124 * push >> 8) + (sin8(sway) * 10 >> 7) + side * ky) & 1023
    s.pitch = 26 + kp
    s.light = (((tp * 1092) >> 8) + 200) & 1023
    S4 = S4_BASE + (S4_PUSH * push >> 8) + ks       # mittakaava Q2 (hires px per 1024 yksikköä)
    s.sk = (S4 * 129) >> 8                          # S * 2,0157
    s.ybq8 = (HZ - (S4 >> 2)) << 8                  # malli y = -1024 vaakaviivalle (HZ)
    s.exiting = t >= c.ex0
    s.grow = [0, 0, 0, 0]
    if not s.exiting:
        for k in range(3):
            u = SMOOTH[ramp(t, c.land[k], c.done[k])]
            s.grow[k] = m.blk_d0[k] + (span(m.blk_d1[k] - m.blk_d0[k]) * u >> 8)
    else:
        g = span(grow_all()) * (255 - SMOOTH[ramp(t, c.exg0, c.exg1)]) >> 8
        s.grow = [g] * 4
    u = ramp(t, c.fly0, c.lock)
    s.dvis = u > 0
    s.dmode = D_FLY if t < c.lock else D_LOCK
    e = 255 - EASE3[u]
    s.dry, s.drx, s.drz = (e * 10) & 1023, (e * 5) & 1023, (e * 3 >> 1) & 1023
    s.dsc = 255 - (e * 150 >> 8)                     # lennon skaala Q8 (0,41..1)
    s.dox, s.doy = e * 40 >> 8, e * 56 >> 8          # ruutusiirtymä oikealle (MC px) ja ylös (riviä)
    s.ai = True
    s.flash = c.flash <= t < c.flash + 2
    s.text = c.name <= t < c.ex1
    s.name_t = t - c.name
    ft, ut = face_times()
    fin = fill_ramp()
    w = []
    for i, f in enumerate(m.faces):
        a, b = t - ft[i], t - ut[i]
        lv = 0 if a < 0 else (fin[a] if a < c.rl else 255)
        ex = 255 if b < 0 else (0 if b >= 5 else 255 - b * 51)
        w.append(min(lv, ex))
    s.w = w
    s.face_level = lambda i: w[i]
    s.solid = lambda i: w[i] != 0
    s.lcam = LCAM[s.light >> 2]
    s.refl_level = [6, 6] if t >= c.sw0 and not s.exiting else [0, 0]   # täytön mukana

    def light_model(r7):
        lc = s.lcam
        return tuple((r7[0][j] * lc[0] + r7[1][j] * lc[1] + r7[2][j] * lc[2]) >> 7 for j in range(3))
    s.light_model = light_model
    s.obj = [(cx * s.lcam[0] + cy * s.lcam[1]) >> 9 for cx, cy in OBJC]
    return s
