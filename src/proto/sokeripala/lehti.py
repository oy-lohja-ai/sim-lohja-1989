"""Lehden pyörähdyksen data (build.py kutsuu): sivu pyörii pystyakselinsa ympäri perspektiivissä ja tulee lähelle,
6510 piirtää sen joka kehys MC-merkkitilaan sarakkeittain (src/proto/sokeripala/sokeripala.asm, `spin`).

Host tekee vain staattisen datan:
  - sarakeprofiilit: sivun pystykaistale (8 etusivun, takasivu ja reunus) skaalattuna jokaiseen korkeuteen
    H = 2..152 merkkikoodeina (13 riviä, kun H <= 104, muuten 19), merkistö 256 merkkiä (reunuksen 16 merkkiä ja
    niiden kapeat versiot sivun reunasarakkeisiin, loput lähimmät sisältömerkit)
  - asennot kehyksittäin: sivun reunojen x ja korkeus ruudulla, kumpi puoli näkyy (kameran kulku kuten
    kaupungintalon s-taulu); 6510 laskee sarakkeiden korkeuden, perspektiivin u:n (log/exp-taulut) ja valitsee
    profiilin ja korkeuden jokaiselle sarakkeelle
  - kynän vedot pysähtyneelle sivulle (alleviivaus ja ympyrä) bittikartan tavuina kehyksittäin
"""
from __future__ import annotations

import math

import numpy as np

from concept.pixel import DASH

NP = 10                          # profiilit: 0-7 etusivu, 8 takasivu, 9 reunus
REUNUS = 9
H_N = 76                         # korkeusindeksi i: H = 2 (i + 1) <= 152
JAKO = 52                        # i < JAKO: rivit 8-20 (13), muuten 6-24 (19)
R13 = range(8, 21)
R19 = range(6, 25)
HMAX = 2 * H_N
# Pyörähdyksen viimeinen asento on sama kuin terävän sivun ensimmäinen kuva (sama x, y, leveys ja korkeus). Terävä sivu
# alkaa FLD:llä SIVU_FLD0 = 48 (sivun yläreuna rivillä 99 = merkkirivi 6), joten siitä näkyy ylimmät HC = 152 riviä
# koko leveydeltä. Pyörivä sivu on tämä rajaus (HC x 320), lopussa täysikokoinen (40 saraketta, korkeus 152) rivillä
# 6-24. Yläreuna y0 = (296 - h) / 3: h = 152 -> 48, h = 104 -> 64 (13 riviä 8-20); yläreuna ja alareuna ovat
# lineaarisia h:ssa, joten perspektiivin reunat pysyvät suorina (horisontti y = 98,7).
HC = 152
SIVU_FLD0 = 48
assert 51 + SIVU_FLD0 == 51 + 8 * R19[0] and SIVU_FLD0 + HC == 200
TUMMA, HARMAA, VAALEA, VALK = 0, 11, 15, 1    # %00 $d021, %01 $d022, %10 $d023, %11 värimuisti: vierekkäiset parit
KOODI = {TUMMA: 0, HARMAA: 1, VAALEA: 2, VALK: 3}  # valoisuudeltaan lähekkäin: musta/tummanharmaa,
D022, D023 = HARMAA, VAALEA                        # vaaleanharmaa/valkoinen


def pituus(i: int) -> int:
    return 13 if i < JAKO else 19


def siirto(i: int) -> int:
    return sum(pituus(k) for k in range(i))


PROF_KOKO = siirto(JAKO)                 # profiilissa vain 13 rivin korkeudet (i < JAKO)
N19 = H_N - JAKO                         # 19 rivin korkeudet T19:ssä rivi kerrallaan: T19[j][N19 p + i - JAKO]
assert NP * N19 <= 256                   # (6510: lda T19 + 240 j,y, 4 sykliä riviltä (zp),y:n ja iny:n sijaan)


def pura_hires(bmp: bytes, scr: bytes) -> np.ndarray:
    img = np.zeros((200, 320), np.int16)
    for c in range(1000):
        cy, cx = divmod(c, 40)
        fg, bg = scr[c] >> 4, scr[c] & 15
        for y in range(8):
            b = bmp[c * 8 + y]
            for x in range(8):
                img[cy * 8 + y, cx * 8 + x] = fg if b & (0x80 >> x) else bg
    return img


PAPERI, TEKSTI, MUSTE, LOGO, KUVA, TYHJA = range(6)          # pyörivän sivun pinnat


def pinnat(sivu: np.ndarray) -> np.ndarray:
    """Sivun solut (25, 40) pinnoiksi: piirretty yksinkertaistus, ei kuvan pikseleitä (pyörivä sivu on graafinen kuten
    elokuvan liike-epäterävä lehti): tunnus keltainen, nimiö ja otsikko mustana, leipäteksti harmaana, kuva
    musta-harmaana ruutuna, muu paperia."""
    out = np.full((25, 40), PAPERI, np.int16)
    for cy in range(25):
        for cx in range(40):
            cell = sivu[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8]
            muste = (cell == 0).mean()
            if (cell == 7).mean() > 0.3:
                out[cy, cx] = LOGO
            elif 12 <= cy <= 22 and 1 <= cx <= 22:
                out[cy, cx] = KUVA
            elif muste > (0.3 if cy == 0 else 0.05):     # rivi 0 on paperin yläreuna (pisteviiva): paperia, jotta
                                                         # sivun yläreuna näkyy mustalla pohjalla kuten terävällä sivulla
                out[cy, cx] = MUSTE if (cy <= 3 or 7 <= cy <= 10) else TEKSTI
    return out


def kaistaleet(sivu: np.ndarray) -> list[np.ndarray]:
    """Profiilien lähde: pinnat (200, 4) MC-pikseleittäin (sivun rivi, MC-sarake kaistaleessa)."""
    pin = pinnat(sivu)
    out = []
    for k in range(8):                                   # etusivu: 5 solun kaistaleet, rivin pinta = yleisin
        rivi = []                                        # (muste voittaa paperin, jotta otsikon loppu näkyy)
        for cy in range(25):
            v = pin[cy, 5 * k:5 * k + 5]
            n = np.bincount(v, minlength=6)
            n[PAPERI] = n[PAPERI] * 2 // 3
            rivi.append(int(np.argmax(n)))
        out.append(np.repeat(np.array(rivi, np.int16)[:, None], 8, 0) * np.ones((1, 4), np.int16))
    rows = np.arange(200)[:, None] // 8
    m = np.where((rows % 2 == 0) & (rows > 0) & (rows < 24), TEKSTI, PAPERI) * np.ones((1, 4), np.int16)
    m[8:24, :] = MUSTE                                   # takasivu: otsikko, palstat ja ilmoitus
    m[56:136, 1:] = KUVA
    out.append(m.astype(np.int16))
    out.append(np.full((200, 4), PAPERI, np.int16))     # reunus
    return out


def sarake(lahde: np.ndarray, h: int) -> np.ndarray:
    """Profiili korkeudella h: (200, 4) väreinä, sivun ylimmät HC riviä ruudun riveillä y0 .. y0 + h - 1, y0 =
    (296 - h) / 3 (lähimmän rivin pinta, kuva-ala ruudukkona ruudun koordinaateissa, jotta kuvio ei ui)."""
    out = np.full((200, 4), TUMMA, np.int16)
    y0 = (296 - h) // 3
    for y in range(y0, y0 + h):
        src = min(HC - 1, int((y - y0 + 0.5) * HC / h))
        for x in range(4):
            v = lahde[src, x]
            out[y, x] = {PAPERI: VAALEA if (2 * x + y) % 8 == 0 else VALK, TEKSTI: VAALEA, MUSTE: TUMMA,
                         LOGO: VAALEA, KUVA: HARMAA if DASH[y % 4, x] < 0.5 else TUMMA}[int(v)]
            # paperissa harva syy, kuva-ala katkoviivaditherinä, ei shakkiruutua
    return out


def merkki(col: np.ndarray, r: int) -> tuple:
    return tuple(KOODI[int(v)] for v in col[8 * r:8 * r + 8].ravel())


def reunus_merkit() -> list[tuple]:
    """Koodit 0-15: tyhjä, paperi, yläreuna k = 1-7 (k riviä tyhjää), alareuna k = 1-7 (k riviä paperia)."""
    out = [tuple([0] * 32), tuple([3] * 32)]
    for k in range(1, 8):
        out.append(tuple(([0] * 4) * k + ([3] * 4) * (8 - k)))
    for k in range(1, 8):
        out.append(tuple(([3] * 4) * k + ([0] * 4) * (8 - k)))
    return out


def kapea(m: tuple, p: int, vasen: bool) -> tuple:
    """Reunasarake: sivu peittää p MC-pikseliä (vasen reuna: oikealta, oikea reuna: vasemmalta)."""
    out = list(m)
    for y in range(8):
        for x in range(4):
            if (x < 4 - p) if vasen else (x >= p):
                out[y * 4 + x] = 0
    return tuple(out)


def merkisto(sivu: np.ndarray) -> tuple[bytes, list[bytes], bytes, dict]:
    """(merkistö 2048 t, profiilien 13 rivin taulut NP x PROF_KOKO, 19 rivin taulu T19 19 x NP N19, raportti)."""
    lahteet = kaistaleet(sivu)
    reunus = reunus_merkit()
    kiinteat = {m: i for i, m in enumerate(reunus)}
    taulut = [[[None] * pituus(i) for i in range(H_N)] for _ in range(NP)]
    paino: dict[tuple, int] = {}
    for p in range(NP):
        for i in range(H_N):
            col = sarake(lahteet[p], 2 * (i + 1))
            rivit = R13 if i < JAKO else R19
            for j, r in enumerate(rivit):
                m = merkki(col, r)
                if p == REUNUS and m not in kiinteat:    # matala sivu: ylä- ja alareuna samassa merkissä
                    m = min(reunus, key=lambda q: sum(abs(x - y) for x, y in zip(q, m)))
                taulut[p][i][j] = m
                if m not in kiinteat:
                    paino[m] = paino.get(m, 0) + 1
    n_vapaa = 256 - 7 * 16
    uniq = list(paino)
    X = np.array(uniq, float)
    lum = np.array([0.0, 0.5, 0.75, 1.0])
    XL = lum[X.astype(int)]
    w = np.array([paino[m] for m in uniq], float)
    k = min(n_vapaa, len(uniq))
    cen = XL[np.argsort(-w)[:k]].copy()
    for _ in range(20):
        d = np.abs(XL[:, None, :] - cen[None, :, :]).sum(2)
        a = d.argmin(1)
        for j in range(k):
            sel = a == j
            if sel.any():
                cen[j] = (XL[sel] * w[sel, None]).sum(0) / w[sel].sum()
    d = np.abs(XL[:, None, :] - cen[None, :, :]).sum(2)
    a = d.argmin(1)
    medoid = []
    for j in range(k):                                   # keskus -> lähin oikea merkki (painotettu)
        sel = np.flatnonzero(a == j)
        if len(sel) == 0:
            medoid.append(uniq[int(np.argmax(w))])
            continue
        dd = np.abs(XL[sel] - cen[j]).sum(1) - 0.01 * w[sel]
        medoid.append(uniq[int(sel[np.argmin(dd)])])
    merkit = list(reunus)
    for v in range(1, 7):
        merkit += [kapea(m, (v - 1) % 3 + 1, v <= 3) for m in reunus]
    merkit += medoid
    merkit += [tuple([0] * 32)] * (256 - len(merkit))
    MX = lum[np.array(merkit[112:112 + k], int)]
    koodi = dict(kiinteat)
    for m in uniq:
        koodi[m] = 112 + int(np.abs(MX - lum[np.array(m, int)]).sum(1).argmin())
    cs = bytearray()
    for m in merkit:
        for y in range(8):
            v = 0
            for x in range(4):
                v = (v << 2) | m[y * 4 + x]
            cs.append(v)
    prof = []
    for p in range(NP):
        b = bytearray()
        for i in range(JAKO):
            b += bytes(koodi[m] for m in taulut[p][i])
        assert len(b) == PROF_KOKO
        if p == REUNUS:
            assert max(b) < 16
        prof.append(bytes(b))
    t19 = bytes(koodi[taulut[p][i][j]] for j in range(19) for p in range(NP) for i in range(JAKO, H_N))
    assert max(t19[N19 * REUNUS + j * NP * N19 + d] for j in range(19) for d in range(N19)) < 16
    return bytes(cs), prof, t19, {"erilaisia": len(uniq), "sisaltomerkit": k}


def asennot(n: int, kierrokset: float = 1.5, s0: float = 0.05, A: float = 0.5, kmax: float = 1.0,
            loppunopeus: float = 0.22) -> list[tuple[int, int, int, int, int]]:
    """Kehyksittäin (xl, xr, hl, hr, takapuoli): sivu pyörii kierrokset hidastuen ja tulee etäisyydeltä 1/s0 lähelle.
    Viimeisessä kehyksessä sivu on täsmälleen vaakana katsojaa kohti (kulma 0), kmax ruudun leveydestä (korkeus HC
    kmax: lopussa sama kuin terävän sivun alku); kulma pienenee loppuun asti, joten ylilyöntiä ei
    ole. Kulma (1 - loppunopeus) v^2 + loppunopeus v, v = jäljellä oleva aika: pehmeä hidastus, jonka loppunopeus
    (noin 0,7 astetta kehyksessä) on pienin, jolla jokainen kehys vielä eroaa edellisestä (sivu on lopussa jo täysikokoinen,
    joten vain kääntyminen liikuttaa sitä). Leikkaus terävään sivuun, kun pyörähdys päättyy. Kooltaan piirto mahtuu
    kehykseen. A = sivun puolileveys / loppuetäisyys (perspektiivin voima)."""
    out = []
    for t in range(n):
        u = t / (n - 1)
        th = 2 * math.pi * kierrokset * ((1 - loppunopeus) * (1 - u) ** 2 + loppunopeus * (1 - u))
        s = s0 + (1 - s0) * (0.85 * (1 - (1 - u) ** 2.2) + 0.15 * u)
        z = max(1 / s, 1 + A * abs(math.sin(th)) + 1e-6)
        pts = []
        for xi in (-1.0, 1.0):
            zz = z + xi * A * math.sin(th)
            x = 80 + 80 * kmax * xi * math.cos(th) / zz
            h = HC * kmax / zz
            pts.append((x, h))
        takana = math.cos(th) < 0
        (x0, h0), (x1, h1) = sorted(pts)
        xl, xr = int(round(x0)), int(round(x1))
        hl = max(2, min(HMAX, 2 * int(round(h0 / 2))))
        hr = max(2, min(HMAX, 2 * int(round(h1 / 2))))
        out.append((max(0, xl), min(160, xr), hl, hr, int(takana)))
    return out


def kartta(takana: bool) -> list[int]:
    """u (0-255 sivun leveydellä ruudun vasemmalta) -> profiili."""
    if takana:
        return [8] * 256
    return [min(7, u * 8 // 256) for u in range(256)]


def kyna(sivu: np.ndarray, scr: bytes, bmp: bytes, kehykset: int, osoite_bmp: int, osoite_scr: int) -> list[tuple[int, int, int]]:
    """Kynän vedot pysähtyneelle sivulle: alleviivaus «purkuluvan» ja ympyrä «Kulttuuriarvo 0»:n ympäri. Punainen
    solussa, jossa ei ole painomustetta, muuten musta. Tapahtumat (kehys 1.., osoite, tavu)."""
    pts = []
    for x in range(6, 94):                               # alleviivaus, käsi heiluu hiukan
        pts.append((x, 91 + (1 if math.sin(x / 9.0) > 0.6 else 0)))
    cx, cy, rx, ry = 250, 166, 64, 12
    n = 330
    for k in range(n):                                   # ympyrä yli alkukohdan, hiukan auki
        a = math.pi * 1.05 - 2 * math.pi * 1.08 * k / n   # ylitse ensin: alakaari näkyy vasta kameran laskeuduttua
        r = 1 + 0.06 * k / n
        pts.append((int(round(cx + rx * r * math.cos(a))), int(round(cy - ry * r * math.sin(a)))))
    seen, uniq = set(), []
    for p in pts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    bm = bytearray(bmp)
    sc = bytearray(scr)
    ink = np.zeros(1000, bool)
    for c in range(1000):
        cy_, cx_ = divmod(c, 40)
        cell = sivu[cy_ * 8:cy_ * 8 + 8, cx_ * 8:cx_ * 8 + 8]
        ink[c] = (cell != 1).any()
    ev = []
    def uusi(x, y):                                      # piirtää näkyvän pikselin (ei painomusteen päälle)
        return any(0 <= x < 320 and 0 <= yy < 200 and sivu[yy, x] == 1 for yy in (y, y + 1))
    n_uusi = sum(1 for p in uniq if uusi(*p))
    per = n_uusi / (kehykset - 1)
    j = -1
    for x, y in uniq:
        if uusi(x, y):
            j += 1
        f = 1 + int(max(j, 0) / per)                     # jokaisessa kehyksessä uusi näkyvä pikseli
        for yy in (y, y + 1):
            if not (0 <= x < 320 and 0 <= yy < 200):
                continue
            c = (yy // 8) * 40 + x // 8
            if not ink[c] and sc[c] != 0x21:
                sc[c] = 0x21                             # punainen valkoisella
                ev.append((f, osoite_scr + c, 0x21))
            a = c * 8 + yy % 8
            bm[a] |= 0x80 >> (x % 8)
            ev.append((f, osoite_bmp + a, bm[a]))
    return ev
