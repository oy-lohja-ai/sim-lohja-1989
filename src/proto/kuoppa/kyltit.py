"""Kuva 3: ryhmälogokyltit perspektiivissä valmiin Lohjantähden tornissa ja siivessä (isoina, tornissa päällekkäin).
Kyltti on suorakaide pinnan koordinaateissa (metreinä): tornissa ympärysmitta a kulmasta
(etupinta -8..0, sivupinta 0..8), siivessä julkisivun u, ja korkeus v. Jokainen MC-pikseli näytteistetään 4 x 4
säteellä konseptin kamerasta (tori.CAMERA, star.trace), joten kyltin reunat kapenevat samaan pakopisteeseen kuin pinta
ja kiertyvät tornin kulman ympäri. Tornissa logo on suoraan MC-pikseleinä (tekstit kyltin kirjaimistolla, kuvat
tekstilogot kyltin kirjaimistolla), lyhenee sivupinnalla ja kallistuu levyn mukaan (_perspektiivi). Kuvalogojen (ADAPT,
AFWD, JML, PWP) roolit C64-tarkkuudella ovat tiedostossa tools/gfx/data/ryhmalogot/kyltit_roolit.npz.

Kyltin kuvat ovat sen solusuorakaiteen kokoisia: kyltin ulkopuoliset pikselit ovat sitä, mitä bittikartassa on
laskeutumishetkellä (rakennus, torni.py: ryhmien tila, ja alemmat kyltit), joten moduuli (src/lib/kylttipudotus)
kirjoittaa suorakaiteen sellaisenaan ja spritet näyttävät vain kyltin (maski). Tornin kyltit ovat kiinni toisissaan,
joten perspektiivin kallistamat reunat jakavat soluja: ylempi kyltti kirjoittaa ne viimeisenä (alempi pysyy niissä
sellaisenaan, ks. myohemmat).
"""
from __future__ import annotations

import dataclasses
import sys
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import numpy as np

from concept import kuoppa as k1
from concept import star
from concept.tori import CAMERA

ROOT = Path(__file__).resolve().parents[3]
VALMIIT = ROOT / "tools/gfx/data/ryhmalogot/kyltit_roolit.npz"   # kuvalogokylttien roolit C64-tarkkuudella
TEKSTILOGOT = ("CR!SP", "HEDELMAE", "GRAY MARCHERS")  # osat(): kyltin kirjaimistolla, muut valmiista rooleista
H, W = 144, 160
ROW0 = 3                                       # kuva-alue alkaa merkkiriviltä 3
SS = 4                                         # näytteitä pikselin sivulla
REUNAVALI = 1                                  # tyhjää logon ja kyltin ylä- ja alareunan välissä (MC-pikseliä)

# Roolit (kuvan arvot): levy, reuna (kyltin ääriviiva), logon tasot 1 ja 2. Värit (palaa, pois): sammunut neon on
# harmaa putki, maalattu levy pysyy (JML:n tummanharmaa laatta; turkoosi syvyys on reunan neonia, solussa 3 väriä).
LEVY, REUNA, T1, T2 = 0, 1, 2, 3


class Kyltti(NamedTuple):
    ryhma: str
    pinta: str                                  # "torni" (ympärysmitta a kulmasta) tai "siipi" (julkisivun u)
    ala: tuple[float, float, float, float]     # (a0, a1, v0, v1) metreinä pinnalla
    laskeutuu: int                              # osalevyn kehys
    varit: dict[int, tuple[int, int]]           # roolin värit (palaa, pois)
    lahtee: int = 0                             # osalevyn kehys, jolla logo irtoaa ja lentää taivaalle
    putoaa: int = 0                             # pudotuksen kesto kehyksinä (0 = moduulin FALL_T)


# Viisi samankokoista nauhaa koko tornin leveydeltä päällekkäin katutasosta lasikruunun (v > 16,6) alle, pino täyttyy
# alhaalta ylös: kyltti putoaa edellisen päälle, joka toinen isku (60 kehystä). Nauhan reunat kallistuvat sitä
# jyrkemmin mitä ylempänä (kulman huippu nousee ylimmässä noin 10 px), joten kahden rivin logo on alimpana. JML
# siiven julkisivulla tornin vieressä sivun reunassa, viimeisenä.
V_ALA, V_YLA = 1.0, 16.6                       # alin kyltti katutason ovien yllä (alareuna solurivin 20 yllä)
TORNI = [("GRAY MARCHERS", {LEVY: (0, 0), REUNA: (2, 11), T1: (7, 12), T2: (1, 12)}),
         ("HEDELMAE", {LEVY: (0, 0), REUNA: (5, 11), T1: (7, 12)}),
         ("AFWD", {LEVY: (0, 0), REUNA: (10, 11), T1: (7, 12)}),
         ("ADAPT", {LEVY: (0, 0), REUNA: (4, 11), T1: (1, 12)}),
         ("CR!SP", {LEVY: (0, 0), REUNA: (14, 11), T1: (1, 12)})]
NAUHA = (V_YLA - V_ALA) / len(TORNI)
# Aikataulu: ryhmät ovat kuin Lohjantähteen avautuvia liikkeitä, jotka lentävät sitten kohti taivasta; rakennus
# tyhjenee, ja logot siirtyvät sprite-ennätykseen, jossa ne lentävät ylöspäin. Kyltit laskeutuvat joka toinen isku
# LASKEUTUU0:sta, ovat auki hetken ja irtoavat yksi kerrallaan LAHTO0:sta ylimmästä alkaen, JML viimeisenä;
# viimeinen lähtee kuvasta juuri ennen osan loppua. Seitsemän kylttiä (PWP siiven julkisivulle JML:n vasemmalle
# puolelle): laskeutumiset (LASKEUTUU0) ja lähdöt (LAHTO0) on ajoitettu niin, että kaikki ehtivät.
LASKEUTUU0, LAHTO0 = 1320, 1738       # lähdöt (ja niiden hiipuminen) kerrontataulun 2c jälkeen; viimeinen lento päättyy
                                       # osan loppuun (liike joka kehys)
# Kaikkoaminen on nopea (logot lentävät ylöspäin nopeasti ja useampi samaan aikaan): lähtö 8 kehyksen välein ja
# lento LENTO_T kehyksessä, kaksi lentoa yhtä aikaa (kylttipudotus: kaksi spritepaikkaa vuorotellen, 4 spriteä
# kumpikin)
LAHTO_VALI, LENTO_T = 8, 14
LENTO_VAIHEET = ((0, 2),)              # puolikkaana heti (täysi koko veisi 4 spriteä ja 1,8 kt; KP4 alle $6000:n)
LAHTO = {"CR!SP": 0, "ADAPT": 1, "AFWD": 2, "HEDELMAE": 3, "GRAY MARCHERS": 4, "PWP": 5,
         "JML": 6}                                              # LAHTO_VALI-välejä LAHTO0:sta
KYLTIT = [Kyltti(r, "torni", (-8.0, 8.0, V_ALA + k * NAUHA, V_ALA + (k + 1) * NAUHA), LASKEUTUU0 + 60 * k, c,
                 LAHTO0 + LAHTO_VALI * LAHTO[r]) for k, (r, c) in enumerate(TORNI)]
# Ensimmäinen kyltti laskeutuu hitaasti ylhäältä PUTOAA0 kehystä (kuoppa-kylttien alussa kuva ei saa seistä,
# osan kehykset 40-90): laskeutuminen alkaa kuoppa-kylttien kehyksellä 10, muut putoavat moduulin FALL_T:ssä.
PUTOAA0 = LASKEUTUU0 - 1270
KYLTIT[0] = KYLTIT[0]._replace(putoaa=PUTOAA0)
KYLTIT.append(Kyltti("JML", "siipi", (66.6, 83.4, 6.5, 12.05), LASKEUTUU0 + 60 * len(TORNI),
                     {LEVY: (11, 11), REUNA: (3, 11), T1: (3, 11), T2: (1, 12)}, LAHTO0 + LAHTO_VALI * LAHTO["JML"]))
KYLTIT.append(Kyltti("PWP", "siipi", (46.0, 62.0, 6.5, 12.05), LASKEUTUU0 + 60 * (len(TORNI) + 1),
                     {LEVY: (0, 0), REUNA: (8, 11), T1: (1, 12)}, LAHTO0 + LAHTO_VALI * LAHTO["PWP"]))
SPR_H = 42                                     # kyltti enintään 2 spriteriviä (pudotus alkaa letterboxin takaa)


def tunnus(ryhma: str) -> str:
    return "".join(ch for ch in ryhma.lower().replace(" ", "_") if ch.isalnum() or ch == "_")


def _font():
    """Kyltin kirjaimisto (src/proto/kyltti/font.py)."""
    sys.path.insert(0, str(ROOT / "src/proto/kyltti"))
    import font
    return font


@lru_cache(maxsize=None)
def _rays() -> tuple[np.ndarray, np.ndarray]:
    """Kameran sijainti ja näytesäteet kuva-alueelle (H * SS, W * SS, 3)."""
    cam = dataclasses.replace(CAMERA, focal=CAMERA.focal * SS, shift=CAMERA.shift * SS, h=CAMERA.h * SS,
                              w=CAMERA.w * SS)
    d = cam.rays()[k1.CROP * SS:(k1.CROP + H) * SS]
    return np.array(cam.pos, float), d


@lru_cache(maxsize=None)
def _trace() -> np.ndarray:
    return star.trace(CAMERA).mat[k1.CROP:k1.CROP + H]


@lru_cache(maxsize=None)
def _surface(pinta: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Näytteiden pinnan koordinaatit (a, v) ja pikselit, joissa pinta näkyy (keskipisteen materiaali)."""
    c, d = _rays()
    mat = _trace()
    with np.errstate(divide="ignore", invalid="ignore"):
        tf = (0.0 - c[2]) / d[..., 2]                                  # etutaso z = 0 (siipi ja tornin etupinta)
        pf = c + d * tf[..., None]
        ts = (star.X1 - c[0]) / d[..., 0]                              # sivutaso x = X1
        ps = c + d * ts[..., None]
    if pinta == "siipi":
        return pf[..., 0] - (star.X1 - star.LEN), pf[..., 1], mat == star.M_FRONT
    front = pf[..., 0] <= star.X1                                      # kamera on kulman edessä oikealla
    a = np.where(front, pf[..., 0] - star.X1, -ps[..., 2])
    v = np.where(front, pf[..., 1], ps[..., 1])
    return a, v, (mat == star.M_TOWER_F) | (mat == star.M_TOWER_S)


def _box(n: np.ndarray) -> np.ndarray:
    """Näytteiden osuus pikselissä: (H * SS, W * SS) -> (H, W)."""
    return n.reshape(H, SS, W, SS).mean((1, 3))


def _inside(i: int) -> np.ndarray:
    a0, a1, v0, v1 = KYLTIT[i].ala
    a, v, _ = _surface(KYLTIT[i].pinta)
    return (a >= a0) & (a <= a1) & (v >= v0) & (v < v1)


@lru_cache(maxsize=None)
def _omistaja() -> np.ndarray:
    """Pikselin kyltti (-1 = ei kylttiä): suurin näyteosuus pinnalla, joka pikselissä näkyy, vähintään puolet;
    kiinni olevien kylttien rajalla tasapelissä alempi (aiempi)."""
    cov = np.stack([_box(_inside(i)) * _surface(k.pinta)[2] for i, k in enumerate(KYLTIT)])
    own = np.argmax(cov, 0)
    return np.where(cov.max(0) >= 0.5, own, -1)


PX = 2 / 0.936                                 # MC-pikselin leveys korkeuksina (PAL)
LYHENNYS = (0.6, 0.45, 0.3, 0.15, 0.0)         # tornin sivupinnan lyhenemisestä logoon (0 litteä, 1 pinnan mukaan),
                                               # suurin, jolla jokainen kirjain mahtuu


def _glyfit(text: str, h: int, w: int, track: int = 1) -> list[np.ndarray]:
    """Kyltin kirjaimiston (src/proto/kyltti/font.py) kirjaimet korkeudella h niin leveinä kuin mahtuu leveyteen w
    (kirjainväli track): vedot naulattuina pikseliruutuun."""
    f = _font()
    best = None
    for kx in np.arange(0.2, 1.6, 0.02):
        gl = [f.glyph(c, h, float(kx), stem=1 / PX) if c != " " else np.zeros((h, max(2, h // 3)), bool) for c in text]
        if best is not None and sum(g.shape[1] for g in gl) + track * (len(gl) - 1) > w:
            break
        best = gl
    return best


def _glyfi(ch: str, h: int, n: int) -> np.ndarray:
    """Kirjain korkeudella h enintään n sarakkeen levyisenä (mahdollisimman leveä)."""
    f = _font()
    best = f.glyph(ch, h, 0.2, stem=1 / PX)
    for kx in np.arange(0.2, 1.6, 0.02):
        g = f.glyph(ch, h, float(kx), stem=1 / PX)
        if g.shape[1] > n:
            break
        best = g
    return best


# Logon osa litteänä (laji, data, rivi, sarake, korkeus, leveys): "teksti" (teksti, lihava, taso) tai "kuva" (ryhmä).
Osa = tuple[str, tuple, int, int, int, int]


def osat(ryhma: str, h: int, w: int) -> list[Osa]:
    """Logon osat litteänä h x w -alueella. Nauha on matala ja leveä, joten korkeat logot asetellaan sen mittasuhteisiin
    isompina: CR!SP lihavana tekstinä, HEDELMAE nimenä, GRAY ja MARCHERS päällekkäin koko leveydeltä."""
    def teksti(t: str, hh: int, ww: int, lihava: bool = False) -> int:
        gl = _glyfit(t, hh, ww - (len(t) if lihava else 0), 2 if lihava else 1)
        return sum(g.shape[1] + (1 if lihava else 0) for g in gl) + (2 if lihava else 1) * (len(gl) - 1)
    if ryhma == "CR!SP":                                              # väli reunaan kummallakin sivulla
        tw = teksti("CR!SP", h, w - 2, True)
        return [("teksti", ("CR!SP", True, 1), 0, (w - tw) // 2, h, tw)]
    if ryhma == "HEDELMAE":                                           # pelkkä nimi (ananaksen kuva
        tw = teksti("HEDELMAE", h, w - 2)                             # puuroutuisi liikaa)
        return [("teksti", ("HEDELMAE", False, 1), 0, (w - tw) // 2, h, tw)]
    if ryhma == "GRAY MARCHERS":
        h1 = (h - 1) * 5 // 9
        w1, w2 = teksti("GRAY", h1, w), teksti("MARCHERS", h - 1 - h1, w)
        return [("teksti", ("GRAY", False, 1), 0, (w - w1) // 2, h1, w1),
                ("teksti", ("MARCHERS", False, 2), h1 + 1, (w - w2) // 2, h - 1 - h1, w2)]
    raise SystemExit(f"kyltit: {ryhma}: ei tekstilogo")


@lru_cache(maxsize=None)
def _sarakkeet(i: int) -> tuple[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Tornikyltin sarakkeet: vasen sarake x0, yläreuna, paksuus (riveinä), pinnan a sarakkeen keskellä ja nauhan
    keskiviiva (rivi, suora kummallakin pinnalla: logon rivit portaina ilman pikselikohinaa)."""
    m = _omistaja() == i
    ys, xs = np.nonzero(m)
    x0, x1 = xs.min(), xs.max()
    top = np.array([ys[xs == x].min() for x in range(x0, x1 + 1)])
    paksuus = np.array([(xs == x).sum() for x in range(x0, x1 + 1)])
    a = _surface("torni")[0]
    yc = top + paksuus // 2
    acol = np.array([a[y * SS:(y + 1) * SS, x * SS:(x + 1) * SS].mean() for x, y in zip(range(x0, x1 + 1), yc)])
    xs = np.arange(len(acol))
    mid = top + (paksuus - 1) / 2
    ymid = np.empty(len(acol))
    for face in (acol < 0, acol >= 0):
        ymid[face] = np.polyval(np.polyfit(xs[face], mid[face], 1), xs[face])
    return x0, top, paksuus, acol, ymid


def _perspektiivi(i: int, h: int, lyhennys: float) -> dict[tuple[int, int], int] | None:
    """Tornikyltin logo perspektiivissä: {(rivi, sarake): taso}, None jos se ei mahdu reunojen sisään. Logo
    asetellaan litteänä (osat) nauhan käyttösarakkeisiin ja litteä sarake vastaa pinnan a:ta tasavälein, joten
    kirjaimet ja kuvat lyhenevät tornin sivupinnalla ja taittuvat kulmassa; jokainen sarake on omalla korkeudellaan
    levyn yläreunan mukaan (kallistuvat samaan pakopisteeseen kuin levy). Kirjain piirretään suoraan sille osuvien
    sarakkeiden levyisenä (vedot ehjinä), kuvan sarake on lähteen sille osuvan kaistan pinta-ala. None myös, jos
    kirjain ei mahdu sarakkeisiinsa (lyhennys liian suuri tiiviille tekstille)."""
    x0, top, paksuus, acol, ymid = _sarakkeet(i)
    js = np.arange(1, len(acol) - 1)                                   # sivuilla reuna
    w = len(js)
    edge = np.concatenate([[acol[js[0]] - (acol[js[0] + 1] - acol[js[0]]) / 2],
                           (acol[js[:-1]] + acol[js[1:]]) / 2,
                           [acol[js[-1]] + (acol[js[-1]] - acol[js[-2]]) / 2]])
    # litteä sijainti 0..w: pinnan a:n (lyhennys 1) ja näytön sarakkeen (0) välissä, jotta sivupinnan kirjaimet eivät
    # kapene luettavuuden alle
    edge = w * (lyhennys * (edge - edge[0]) / (edge[-1] - edge[0]) + (1 - lyhennys) * np.arange(w + 1) / w)
    pos = (edge[:-1] + edge[1:]) / 2

    def cols(c0: float, c1: float) -> np.ndarray:
        """Käyttösarakkeet, joiden keskikohta osuu litteälle välille c0..c1."""
        return np.flatnonzero((pos >= c0) & (pos < c1))

    flat: dict[tuple[int, int], int] = {}                              # (logon rivi, käyttösarake) -> taso
    for laji, data, r0, c0, hh, ww in osat(KYLTIT[i].ryhma, h, w):
        if laji == "teksti":
            text, lihava, taso = data
            track = 2 if lihava else 1
            gl = _glyfit(text, hh, ww - (len(text) if lihava else 0), track)
            x = c0
            for k, (ch, g) in enumerate(zip(text, gl)):
                gw = g.shape[1] + (1 if lihava else 0)
                tr = track if k < len(text) - 1 else 0                # kirjainväli kuuluu kirjaimen sarakkeisiin
                cs = cols(x, x + gw + tr)
                n = max(1, len(cs) - tr)
                if ch != " ":
                    gg = _glyfi(ch, hh, n - (1 if lihava else 0))
                    if gg.shape[1] + (1 if lihava else 0) > n:
                        return None
                    if lihava:
                        gg = np.pad(gg, ((0, 0), (0, 1))) | np.pad(gg, ((0, 0), (1, 0)))
                    off = (n - gg.shape[1]) // 2
                    for r, k in zip(*np.nonzero(gg)):
                        if off + k < len(cs):
                            flat[(r0 + r, cs[off + k])] = taso
                x += gw + track
    out = {}
    for (r, j), t in flat.items():
        x = js[j]
        y = int(np.floor(ymid[x] - (h - 1) / 2 + 0.5)) + r
        if y < top[x] + 1 or y > top[x] + paksuus[x] - 2:
            return None
        out[(y, x0 + x)] = t
    return out


@lru_cache(maxsize=None)
def roolit(i: int) -> np.ndarray:
    """Kyltin roolit koko kuva-alueella (H, W): -1 ei kylttiä, muuten LEVY / REUNA / T1 / T2. Levy ja reunat ovat
    perspektiivissä (näytteistetty pinnalta). Tornissa logo on niin korkea kuin mahtuu reunojen sisään
    (_perspektiivi). Kuvalogot: valmiit roolit (VALMIIT)."""
    if KYLTIT[i].ryhma not in TEKSTILOGOT:
        return np.load(VALMIIT)[tunnus(KYLTIT[i].ryhma)].astype(int)
    m = _omistaja() == i
    out = np.full((H, W), -1)
    out[m] = LEVY
    paksuus = _sarakkeet(i)[2]
    for h, ly in ((h, ly) for h in range(int(paksuus[2:-2].min()) - 2 * (1 + REUNAVALI), 4, -1)
                  for ly in LYHENNYS):                             # reuna ja väli ylä- ja alapuolella
        lg = _perspektiivi(i, h, ly)
        if lg is not None:
            break
    else:
        raise SystemExit(f"kyltit: {KYLTIT[i].ryhma}: logo ei mahdu nauhaan")
    for (y, x), t in lg.items():
        out[y, x] = (T1, T2)[t - 1]
    p = np.pad(m, 1)
    edge = m & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
    # Alemman kyltin päällä alareunaa ei piirretä: alemman yläreuna erottaa kyltit, ja jaetuissa soluissa riittää
    # kyniä alemman reunalle ja logolle (muuten ylempi värittäisi ne uudelleen laskeutuessaan).
    own = np.pad(_omistaja(), 1, constant_values=-1)
    alla = (own[2:, 1:-1] >= 0) & (own[2:, 1:-1] < i)
    out[edge & ~alla] = REUNA                                          # kulman taite näkyy reunojen kulmasta
    if KYLTIT[i].pinta == "torni":                                     # taite: kyltti kiertää kulman
        mat = _trace()
        seam = np.zeros((H, W), bool)
        seam[:, 1:] = (mat[:, 1:] == star.M_TOWER_S) & (mat[:, :-1] == star.M_TOWER_F)
        out[seam & (out == LEVY)] = REUNA
    return out


def solut(i: int) -> tuple[int, int, int, int]:
    """Kyltin solusuorakaide (rivi ruudulla, sarake, korkeus, leveys soluina)."""
    ys, xs = np.nonzero(roolit(i) >= 0)
    r0, r1, c0, c1 = ys.min() // 8, ys.max() // 8, xs.min() // 4, xs.max() // 4
    return ROW0 + r0, c0, r1 - r0 + 1, c1 - c0 + 1


def myohemmat(i: int) -> np.ndarray:
    """Kyltin i solut (korkeus, leveys), jotka myöhemmin laskeutuva kyltti kirjoittaa uudelleen (jaetut reunasolut):
    niissä kyltti i ei saa muuttua enää syttymisensä jälkeen (kuoppa4: ei hengitystä)."""
    r, c, h, w = solut(i)
    out = np.zeros((25, 40), bool)
    for j in range(i + 1, len(KYLTIT)):
        rj, cj, hj, wj = solut(j)
        out[rj:rj + hj, cj:cj + wj] = True
    return out[r:r + h, c:c + w]


def tarkista() -> None:
    """Kyltit laskeutuvat järjestyksessä vähintään 31 kehyksen välein (kylttipudotus: myöhempi kirjoittaa jaetut solut
    viimeisenä) ja kyltti mahtuu kahteen spriteriviin (pudotus alkaa letterboxin takaa)."""
    for i in range(len(KYLTIT)):
        if i and KYLTIT[i].laskeutuu - KYLTIT[i - 1].laskeutuu < 31:
            raise SystemExit(f"kyltit: {KYLTIT[i].ryhma} laskeutuu alle 31 kehystä edellisen jälkeen")
        ys = np.nonzero((roolit(i) >= 0).any(1))[0]
        if ys.max() - ys.min() + 1 > SPR_H:
            raise SystemExit(f"kyltit: {KYLTIT[i].ryhma} on {ys.max() - ys.min() + 1} px korkea, enintään {SPR_H}")


def rect(i: int) -> tuple[slice, slice]:
    """Solusuorakaide kuva-alueen pikseleinä."""
    r, c, h, w = solut(i)
    return slice((r - ROW0) * 8, (r - ROW0 + h) * 8), slice(c * 4, (c + w) * 4)


def maski(i: int) -> np.ndarray:
    ys, xs = rect(i)
    return roolit(i)[ys, xs] >= 0


LUMA = [0, 15, 5, 10, 6, 9, 3, 12, 6, 3, 9, 5, 8, 12, 8, 10]


def kuvat(i: int, tausta: np.ndarray, dim: dict[int, int], hengitys: dict[int, int],
          pimea: np.ndarray | None = None) -> tuple[dict, int]:
    """Kyltin tilakuvat solusuorakaiteessa: {"pois", "himmea", "palaa", "tyhja", "hengitys", "maski"} ja muutettujen
    rakennuspikselien määrä. tausta = kuva-alue laskeutumishetkellä, pimea = pimeä rakennus (tyhjän paikan kuva). Solussa enintään 3 kynää (värit kaikissa tiloissa)
    mustan lisäksi: kyltin kynät ensin, rakennuksen harvinaisimmat värit lähimpään jäljelle jäävään (valoisuus)."""
    ys, xs = rect(i)
    rol = roolit(i)[ys, xs]
    bg = tausta[ys, xs].astype(int)
    col = KYLTIT[i].varit
    on = np.where(rol >= 0, np.vectorize(lambda r: col.get(r, (0, 0))[0])(np.maximum(rol, 0)), bg)
    off = np.where(rol >= 0, np.vectorize(lambda r: col.get(r, (0, 0))[1])(np.maximum(rol, 0)), bg)
    lit = (rol >= 0) & (on != off)                                     # neon (syttyy ja hengittää)
    dm = np.where(lit, np.vectorize(lambda c: dim.get(int(c), int(c)))(on), on)
    br = np.where(lit, np.vectorize(lambda c: hengitys.get(int(c), int(c)))(on), on)
    # tyhjä (logo lentänyt pois): logon neon levyn väriksi, reunan neon sammuneeksi. Lähtöön kuitenkin julkisivu
    # (pimea annettu): kyltin paikalle rakennus valaisemattomana omalla bittikartallaan (pimeät kerrokset, rakennuksen
    # muoto ilman logojen roskia)
    ty = np.where(lit & (rol == REUNA), off, np.where(lit, col.get(LEVY, (0, 0))[0], on))
    muutettu = 0
    for r in range(0, on.shape[0], 8):
        for c in range(0, on.shape[1], 4):
            cs = (slice(r, r + 8), slice(c, c + 4))
            pens: dict[tuple, int] = {}
            sign = set()
            for p, s in zip(zip(off[cs].ravel(), dm[cs].ravel(), on[cs].ravel(), ty[cs].ravel(), br[cs].ravel()),
                            (rol[cs] >= 0).ravel()):
                if any(p):
                    pens[p] = pens.get(p, 0) + 1
                    if s:
                        sign.add(p)
            if len(pens) <= 3:
                continue
            keep = sorted(pens, key=lambda p: (p not in sign, -pens[p]))[:3]
            if any(p in sign for p in pens if p not in keep):
                raise SystemExit(f"kyltit: {KYLTIT[i].ryhma} solu ({c // 4}, {r // 8}): kyltissä yli 3 väriä")
            alt = [p for p in keep if len(set(p)) == 1] + [(0, 0, 0, 0, 0)]
            for y in range(8):
                for x in range(4):
                    yy, xx = r + y, c + x
                    p = (off[yy, xx], dm[yy, xx], on[yy, xx], ty[yy, xx], br[yy, xx])
                    if any(p) and p not in keep:
                        q = min(alt, key=lambda a: abs(LUMA[a[2]] - LUMA[p[2]]))
                        off[yy, xx], dm[yy, xx], on[yy, xx], ty[yy, xx], br[yy, xx] = q
                        muutettu += 1
    m = rol >= 0
    out = {"pois": off.astype(np.uint8), "himmea": dm.astype(np.uint8), "palaa": on.astype(np.uint8),
           "tyhja": ty.astype(np.uint8), "hengitys": br.astype(np.uint8), "maski": m}
    if pimea is not None:
        out["julkisivu"] = pimea[ys, xs].astype(np.uint8)
    return out, muutettu
