"""Kuva 3: valmis Lohjantähti sinisellä hetkellä tuijottaa Sokeripalaa (kuoppa.torni). Host tekee pimeän (lit 0) ja
valaistun (lit 1) kuvan yhteisellä solupaletilla ja niiden eron ryhmittäin XOR-ajoina: tornin kerrokset (7),
kerrostalon ikkunat yksitellen ja torin heijastus. 6510 sytyttää ryhmät reaaliajassa: kerrokset alhaalta ylös
(kuvan 3 alussa vasemmalta oikealle sarakkeittain, ilman välkettä), ikkunat satunnaisessa järjestyksessä (kuoppa3.asm).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

from concept import kuoppa as k1
from concept import star
from concept.tori import CAMERA

import kyltit as ky
import runko

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))               # kylttipudotus

H, W = 144, 160
STEP = 2                                       # ryhmän alkuaika kehyksinä / 2
T_FLOOR0, T_FLOOR_GAP = 4, 31                  # kerros k syttyy 4 + 31 k (kuvan 3 kehykset): heti leikkauksen jälkeen, kuoppa-kylttien alussa (osan kehykset 0-120) kerros noin 31 kehyksen välein ennen ensimmäistä kylttiä (kuva ei seiso)
PAT_TUBE, PAT_LAMP, PAT_LATE, PAT_GLINT = 0, 1, 2, 3   # välkekuviot (kuoppa3.asm PATS)
FIRST_N = 60                                   # kehykset 0..FIRST_N: joka kehys muuttuu (näkyy kehystä myöhemmin)
SWEEP = 31                                     # kuvan 3 alun kerros syttyy näin monessa sarakeryhmässä kehys kerrallaan
SHOT3 = 1200                                   # kp_defs.inc: kuvan 3 alku osalevyn kehyksinä
# Ryhmälogokyltit valmiiseen Lohjantähteen (isot ja perspektiivissä, logot päällekkäin: torniin mahtuu ainakin 6):
# paikat, koot ja värit kyltit.py (perspektiivikyltit pinona tornin
# kyljessä), src/lib/kylttipudotus pudottaa ne. Kerrokset ovat syttyneet noin 1420; pudotus joka toinen isku
# (60 kehystä) kyltit.py LASKEUTUU0:sta alkaen, pino täyttyy alhaalta ylös; lasikruunu jää näkyviin.
Y0_KYLTTI = 33                                 # pudotuksen alku: 2 spriterivin kyltti (42 px) heti letterboxin (raster 51-74)
                                               # takana, ei piilossa kuluvia kehyksiä (reunuksesta 8 noin 15)
END = 1800                                     # kuoppa-kylttien loppu kuopan kehyksinä (1260 + 780 - taulun 240)
T_GLINT = 40                                   # Sokeripalan ikkunoiden heijastus alkaa (kuvan 3 kehys): väreilee kuoppa-kylttien alusta loppuun (kuva ei seiso ennen ensimmäistä kylttiä)


def groups(U: np.ndarray, L: np.ndarray) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Pikselin ryhmä (-1 = ei muutu) ja ryhmien (alkuaika, kuvio)."""
    tr = star.trace(CAMERA)
    cr = slice(k1.CROP, k1.CROP + H)
    mat, V = tr.mat[cr], tr.V[cr]
    d = U != L
    g = np.full((H, W), -1)
    info = []
    tower = d & ((mat == star.M_TOWER_F) | (mat == star.M_TOWER_S) | (mat == star.M_SKY))
    fl = np.clip(np.floor(V / star.FLOOR_H), 0, len(star.FLOOR_MOOD) - 1).astype(int)
    fl = np.where(mat == star.M_SKY, len(star.FLOOR_MOOD) - 1, fl)
    inr = in_rects()
    ulko = []
    for k in range(len(star.FLOOR_MOOD)):                               # kerros kahtena ryhmänä: kylttien alla ja muualla
        t0 = T_FLOOR0 + T_FLOOR_GAP * k                                 # (pimennys sammuttaa vain muualla olevan)
        g[tower & (fl == k) & inr] = len(info)
        info.append((t0, PAT_TUBE))
        osa = tower & (fl == k) & ~inr
        # kuvan 3 alussa (ennen kylttejä) kerros syttyy vasemmalta oikealle sarake kerrallaan joka kehys (ilman
        # välkettä, mutta joka kehys muuttuu): SWEEP ryhmää, pimennys yhtenä
        xs = np.nonzero(osa.any(axis=0))[0]
        n = SWEEP if t0 < FIRST_N and len(xs) >= SWEEP else 1
        cuts = ([xs[len(xs) * j // n] for j in range(n)] if n > 1 else [0]) + [W]
        for j in range(n):
            seg = osa & (np.arange(W)[None, :] >= cuts[j]) & (np.arange(W)[None, :] < cuts[j + 1])
            g[seg] = len(info)
            info.append((t0 + j, PAT_TUBE))
        ulko.append(len(info) - n)
    ground = d & (mat == star.M_GROUND)
    g[ground & inr] = 0                                                 # torin heijastus alimman kerroksen mukana
    g[ground & ~inr] = ulko[0]
    win = d & ((mat == star.M_FRONT) | (mat == star.M_SIDE))
    lab, n = ndimage.label(win, structure=np.ones((3, 3)))
    rng = np.random.default_rng(1991)
    wins = []
    for i in range(1, n + 1):
        g[lab == i] = len(info)
        late = rng.random() < 0.3                                       # osa sammuu ja syttyy uudelleen lopussa
        wins.append(len(info))
        info.append((int(rng.integers(10, 300 if late else 400)), PAT_LATE if late else PAT_LAMP))
    first_frames(info, wins)
    clear_signs(g, info, wins)
    glint = d & (mat == star.M_SKY) & (np.arange(W)[None, :] >= 130)   # Sokeripalan seinä (ei jäljitetty)
    glint |= d & (np.arange(W)[None, :] >= 136) & (g == -1)
    if glint.any():
        g[glint] = len(info)
        info.append((T_GLINT, PAT_GLINT))
    rest = d & (g == -1)
    g[rest] = len(info) - 1 if info else 0
    g[g == CLEARED] = -1                                                # kyltin alla pysyy pimeänä (ei XOR:ia)
    return g, info


GLINT1 = [3, 1, 1, 0, 5, 1, 1, 0, 2, 1, 2, 0, 7, 1, 1, 0, 4, 1, 1, 0, 3, 1, 2, 0, 6, 1, 1, 0, 2, 1, 1, 0]
GLINT2 = [5, 1, 1, 0, 3, 1, 2, 0, 8, 1, 1, 0, 4, 1, 1, 0, 2, 1, 1, 0, 6, 1, 2, 0, 3, 1, 1, 0]
# Välkekuviot (kesto askelina eli 2 kehystä, tila) ..., (0, lopputila); export vie ne k3data.asm:ään (pat_lo, pat_hi).
# Kerrokset ja ikkunat syttyvät suoraan ilman loisteputken naksumista ja lampun välähdystä.
PAT_STEPS = {PAT_TUBE: [0, 1],                                          # kerros syttyy
             PAT_LAMP: [0, 1],                                          # ikkunan lamppu syttyy
             PAT_LATE: [63, 1, 25, 0, 0, 1],                            # lamppu, joka sammuu hetkeksi ja syttyy uudelleen
             PAT_GLINT: (GLINT1 + GLINT2) * 5 + [0, 1]}                 # heijastus väreilee kuvan loppuun asti
T_INC = 0                                      # kuoppa3.asm job3i koko kuvan 3 (kuvioiden kohta muistissa: työ valmis ajoissa)


def inc_state(t: int, p: int) -> tuple[int, int]:
    """(gidx, gacc) kehyksellä T_INC: kello (T_INC - vaihe) / 2, kulunut kello - t // 2."""
    e = ((T_INC - t % STEP) >> 1) - t // STEP
    y = acc = 0
    steps = PAT_STEPS[p]
    if e < 0:
        return 0, 0
    while steps[y] != 0 and e - acc >= steps[y]:
        acc += steps[y]
        y += 2
    return y, acc


def changes(t: int, pat: int) -> list[int]:
    """Kehykset (kuvan 3 alusta), joilla ryhmän tila vaihtuu: alku t ja jokaisen vaiheen loppu (kuvioiden tila
    vuorottelee, kesto askelina eli 2 kehystä, 0 = loppuun asti)."""
    out = [t]
    for d in PAT_STEPS.get(pat, [0])[::2]:
        if d == 0:
            break
        t += STEP * d
        out.append(t)
    return out


CLEARED = -2                                   # groups: kyltin alta poistettu ryhmän pikseli (ei muutu)


def sign_rects() -> list[tuple[slice, slice, int]]:
    """Kylttien solusuorakaiteet kuva-alueen pikseleinä (rivit, sarakkeet) ja laskeutuminen kuvan 3 kehyksenä."""
    return [(*ky.rect(i), k.laskeutuu - SHOT3) for i, k in enumerate(ky.KYLTIT)]


def clear_signs(g: np.ndarray, info: list[tuple[int, int]], wins: list[int]) -> None:
    """Kyltin soluissa ei XOR-vaihtoa laskeutumisen jälkeen (kylttipudotus: XOR sotkisi kyltin bittikartan): ikkuna
    syttyy ja jää palamaan ennen laskeutumista, muiden ryhmien (kerrokset, heijastus) pikselit kyltin alla eivät muutu."""
    for ys, xs, land in sign_rects():
        for gi in sorted(set(np.unique(g[ys, xs])) - {-1, CLEARED}):
            t, p = info[gi]
            if max(changes(t, p)) < land - 2 and p != PAT_GLINT:
                continue
            if gi in wins and land > 20:
                info[gi] = (min(t, land - 20), PAT_LAMP)
            else:
                sub = g[ys, xs]
                sub[sub == gi] = CLEARED


def at_landing(U: np.ndarray, L: np.ndarray, g: np.ndarray, info: list[tuple[int, int]], land: int) -> np.ndarray:
    """Kuva-alue bittikartassa, kun kyltti kirjoitetaan siihen (kylttipudotus: laskeutuminen + 6): ryhmä on valaistu,
    kun sen tila on vaihtunut parittoman määrän kertoja (alussa kaikki pimeinä); täyteikkunat kyltin suorakaiteessa
    eivät vaihdu (fill_data)."""
    out = U.copy()
    for gi, (t, p) in enumerate(info):
        if sum(f <= land + 6 for f in changes(t, p)) & 1:
            out[g == gi] = L[g == gi]
    return out


FILL_GAP = 30                                  # kuoppa4: saman ikkunan valonvaihtojen väli vähintään (kehystä)
FILL_MARGIN = 3                                # ei vaihtoa ikkunan oman kuvion aikana +- tämä


PIMEA0 = 1736                                  # rakennus pimenee (osan kehys, jaollinen 4:llä): kaupat lähtevät taivaalle (kyltit.py LAHTO0)
PIMEA_VALI = 4                                 # ryhmä sammuu joka PIMEA_VALI. kehys


def in_rects() -> np.ndarray:
    """Kylttien solusuorakaiteiden pikselit kuva-alueella (moduuli kirjoittaa ne kokonaan)."""
    m = np.zeros((H, W), bool)
    for ys, xs, _ in sign_rects():
        m[ys, xs] = True
    return m


def dark_data(g: np.ndarray, info: list[tuple[int, int]]) -> str:
    """kuoppa4:n pimennys (lopuksi rakennus on tyhjä ja pimeä): PIMEA0:sta joka PIMEA_VALI. kehys yksi
    Lohjantähden valoryhmä sammuu pysyvästi, ikkunat satunnaisessa järjestyksessä, sitten kerrokset ylhäältä alas.
    Sokeripalan heijastus (toinen talo) jatkuu. Vain ryhmät, joilla ei ole pikseleitä kylttien suorakaiteissa (XOR
    sotkisi kyltin tai tyhjän paikan)."""
    inr = in_rects()
    ok = [i for i in range(len(info)) if (g == i).any() and not (inr & (g == i)).any()]
    floors = [i for i in ok if info[i][1] == PAT_TUBE]
    wins = [i for i in ok if info[i][1] in (PAT_LAMP, PAT_LATE)]
    np.random.default_rng(1740).shuffle(wins)
    steps = [[i] for i in wins]
    for i in floors[::-1]:              # kerroksen sarakeryhmät (SWEEP, peräkkäiset alkuajat) sammuvat samalla askeleella
        if steps and len(steps) > len(wins) and info[steps[-1][-1]][0] == info[i][0] + 1:
            steps[-1].append(i)
        else:
            steps.append([i])
    order = [i for s in steps for i in s]
    last = [int(j == len(s) - 1) for s in steps for j in range(len(s))]
    if PIMEA0 + PIMEA_VALI * len(steps) > END:
        raise SystemExit(f"torni: pimennys ({len(steps)} askelta) ei ehdi ennen loppua")
    return (f"PIMEA0 = {PIMEA0}\nPIMEA_VALI = {PIMEA_VALI}\nNDARK = {len(order)}\n"
            "kp4_dark .byte " + ", ".join(map(str, order)) + "\n"
            "kp4_dend .byte " + ", ".join(map(str, last)) + "\n")


def fill_data(g: np.ndarray, info: list[tuple[int, int]]) -> str:
    """kuoppa4:n täyte: kyltin Y, josta sen alareuna on letterboxin alla (raster 75), ja ikkunat, joiden valo
    syttyy tai sammuu pysyvästi kehyksellä, jolla kuva ei muuten muuttuisi. Ikkuna kelpaa, kun sen oma kuvio ei ole
    käynnissä (kiireinen osan kehyksillä blo..bhi) eikä sen päälle laskeutuva kyltti ole vielä tulossa (asti: L - 25);
    kuoppa4 lisäksi pitää saman ikkunan vaihdot FILL_GAP:n päässä toisistaan. Ei yhden kehyksen tiloja. Ikkuna, joka
    näkyy kyltin solusuorakaiteessa kyltin vieressä, palautetaan omaan tilaansa (kp4_rest) kehyksellä R = L - 40 (tai
    ennen omaa kuviotaan), koska kyltti kirjoittaa suorakaiteeseen laskeutumishetken tilan (at_landing); sen viimeinen
    täytevaihto on viimeistään R - FILL_GAP."""
    import kylttipudotus
    vis = [76 - kylttipudotus.sprite_box(ky.maski(i))[2] for i in range(len(ky.KYLTIT))]
    wins = [i for i, (_, p) in enumerate(info) if p in (PAT_LAMP, PAT_LATE) and (g == i).any()]
    asti, rest = {}, {}
    for i, (ys, xs, land) in enumerate(sign_rects()):
        gs = g[ys, xs]
        for w in set(np.unique(gs)) & set(wins):
            asti[w] = min(asti.get(w, 1 << 16), SHOT3 + land - 25)
            if (gs[~ky.maski(i)] == w).any():
                rest[w] = min(rest.get(w, 1 << 16), SHOT3 + land - 40)
    np.random.default_rng(26).shuffle(wins)
    blo = [SHOT3 + min(changes(*info[w])) - FILL_MARGIN for w in wins]
    bhi = [SHOT3 + max(changes(*info[w])) + FILL_MARGIN for w in wins]
    for j, w in enumerate(wins):
        if w in rest:
            if blo[j] <= rest[w] <= bhi[j]:
                rest[w] = blo[j] - 1
            asti[w] = min(asti[w], rest[w] - FILL_GAP)
    ul = [asti.get(w, 0xffff) for w in wins]
    rs = sorted((r, w) for w, r in rest.items())
    out = [f"NFILL = {len(wins)}", f"FILL_GAP = {FILL_GAP}", "kp4_vis .byte " + ", ".join(map(str, vis)),
           "kp4_fill .byte " + ", ".join(map(str, wins))]
    for nm, v in (("kp4_bll", [x & 255 for x in blo]), ("kp4_blh", [x >> 8 for x in blo]),
                  ("kp4_bhl", [x & 255 for x in bhi]), ("kp4_bhh", [x >> 8 for x in bhi]),
                  ("kp4_ul", [x & 255 for x in ul]), ("kp4_uh", [x >> 8 for x in ul])):
        out.append(f"{nm} .byte " + ", ".join(map(str, v)))
    out += [f"NREST = {len(rs)}", "kp4_rw .byte " + ", ".join(str(w) for _, w in rs) if rs else "kp4_rw",
            "kp4_rl .byte " + ", ".join(str(r & 255) for r, _ in rs) if rs else "kp4_rl",
            "kp4_rh .byte " + ", ".join(str(r >> 8) for r, _ in rs) if rs else "kp4_rh"]
    return "\n".join(out) + "\n"


# Neonin hengitys (kuoppa4): syttyneen kyltin solu kerrallaan sukulaisväriin ja takaisin (väri -> väri).
BREATH = {1: 7, 7: 1, 13: 7, 15: 1, 12: 15, 11: 12, 6: 14, 14: 6, 3: 14, 4: 6, 2: 10, 10: 2, 8: 10, 9: 8, 5: 13}
BREATH_ON = 6 + 1 + 16 + 1                     # kylttipudotus: bittikarttaan L + 6, syttyminen 16 kehystä


def breath_data(imgs: list[dict]) -> str:
    """Hengityksen taulut kylteittäin laskeutumisjärjestyksessä: alkukehys ja solut (tilan datan indeksi, ruutusiirtymä,
    sukulaisvärin ruutu- ja värimuistitavu) sarakkeittain vasemmalta (väri kulkee aaltona kyltin yli), vain solut,
    joiden väri vaihtuu. Sukulaisväri vain kyltin neonille (kyltit.kuvat hengitys), rakennus solussa pysyy. Solu, jonka
    ylempi kyltti kirjoittaa myöhemmin (kyltit.myohemmat), ei hengitä: ylemmän koodaus on siinä toinen."""
    import kylttipudotus
    lines = ["kp4_on_lo .byte " + ", ".join(f"<{k.laskeutuu + BREATH_ON}" for k in ky.KYLTIT),
             "kp4_on_hi .byte " + ", ".join(f">{k.laskeutuu + BREATH_ON}" for k in ky.KYLTIT),
             # hengitys loppuu, kun neon alkaa hiipua ennen lähtöä (kylttipudotus.SAMMUU)
             "kp4_off_lo .byte " + ", ".join(f"<{k.lahtee - len(kylttipudotus.SAMMUU) - 1}" for k in ky.KYLTIT),
             "kp4_off_hi .byte " + ", ".join(f">{k.lahtee - len(kylttipudotus.SAMMUU) - 1}" for k in ky.KYLTIT)]
    nc, whs = [], []
    for i, im in enumerate(imgs):
        _, st = kylttipudotus.encode([im[t] for t in ("pois", "himmea", "palaa", "tyhja", "hengitys")], 0,
                                     ky.KYLTIT[i].ryhma)      # sama paikkajako kuin moduulin tiloilla (etuliite)
        h, w = im["palaa"].shape[0] // 8, im["palaa"].shape[1] // 4
        wh = h * w
        on, br = st[2], st[4]
        later = ky.myohemmat(i)
        cells = [(y, x) for y in range(h) for x in range(w) if not later[y, x] and
                 (on[y * w + x] != br[y * w + x] or on[wh + y * w + x] != br[wh + y * w + x])]
        cells.sort(key=lambda yx: (yx[1], yx[0]))                  # aalto vasemmalta oikealle
        if 2 * wh > 256 or (h - 1) * 40 + w > 256 or 4 * len(cells) > 252:
            raise SystemExit(f"torni: kyltin {ky.KYLTIT[i].ryhma} hengitys ei mahdu tavuindekseihin ({w} x {h}, "
                             f"{len(cells)} solua)")
        nc.append(len(cells))
        whs.append(wh)
        lines.append(f"kp4_c{i} .byte " + ", ".join(
            f"{y * w + x}, {y * 40 + x}, {br[y * w + x]}, {br[wh + y * w + x]}" for y, x in cells))
    lines += ["kp4_nc .byte " + ", ".join(str(4 * n) for n in nc),            # tavuina (4 solua kohden)
              "kp4_wh .byte " + ", ".join(map(str, whs)),
              "kp4_cl .byte " + ", ".join(f"<kp4_c{i}" for i in range(len(imgs))),
              "kp4_ch .byte " + ", ".join(f">kp4_c{i}" for i in range(len(imgs)))]
    return "\n".join(lines) + "\n"


def first_frames(info: list[tuple[int, int]], wins: list[int]) -> None:
    """Leikkauksesta (kehys 1) kehykseen FIRST_N jokaisella kehyksellä jokin ryhmä vaihtuu: kattamattomalle kehykselle
    ikkuna syttyy juuri silloin. Ikkunat otetaan myöhäisimmistä (kylttien aikana muuta liikettä on runsaasti), jotta
    alun jälkeen ei jää aukkoja."""
    free = sorted((i for i in wins if info[i][0] > FIRST_N), key=lambda i: -info[i][0])
    gaps = [f for f in range(FIRST_N + 1) if not any(f in changes(t, p) for t, p in info)]
    # ilman välkettä ikkunoita on vähemmän kuin kattamattomia kehyksiä: tasaisesti koko alkuun
    # (ikkuna syttyy noin joka toinen kehys), ei kaikkia alkuun ja loppua tyhjäksi
    for n, i in enumerate(free[:len(gaps)]):
        info[i] = (gaps[n * len(gaps) // min(len(free), len(gaps))], info[i][1])


def xor_runs(bU: bytes, bL: bytes, g: np.ndarray, gi: int) -> bytes:
    """Ryhmän XOR-tavut ajoina: (siirtymä lo, hi, määrä, arvot...) kuva-alueen bittikartassa; loppu määrä 0."""
    vals = {}
    for y, x in zip(*np.nonzero(g == gi)):
        o = (y >> 3) * 320 + (x >> 2) * 8 + (y & 7)
        m = 3 << (6 - 2 * (x & 3))
        v = (bU[o] ^ bL[o]) & m
        if v:
            vals[o] = vals.get(o, 0) | v
    out = bytearray()
    offs = sorted(vals)
    i = 0
    while i < len(offs):
        j = i
        while j + 1 < len(offs) and offs[j + 1] == offs[j] + 1 and j - i < 250:
            j += 1
        out += bytes([offs[i] & 255, offs[i] >> 8, j - i + 1]) + bytes(vals[o] for o in offs[i:j + 1])
        i = j + 1
    return bytes(out) + b"\x00\x00\x00"


# Lähteneiden kylttien julkisivut (kylttipudotus T_JULKI: erilliset solut, solukartat ja värit noin 2,4 kt) pankin 2
# vapaille alueille kp3:n tiedostoon: bittikartan näkymättömät rivit 21-24, spritepuskurin perässä ennen ruutua ja
# kuvan 3 koodin perässä ($9d00-, kuoppa3 kp3_end <= $9d00). KP4 ($2800-) ei kasva: koko demossa VUOSI12 esiladataan
# $6000:aan kylttien aikana.
JULKI_ALUEET = [(0xBA40, 0xBF40), (0x8200, 0x8400), (0x9D00, 0xA000)]   # ensimmäinen: solut (kylttipudotus.julki_sijoitus);
# ruudun rivejä 0-2 ($8400-$8477) ei: kp3_init nollaa ne


def export(out) -> dict:
    """k3.bin (pimeä kuva: bittikartta, ruutu, värit) ja k3data.asm (ryhmät ja XOR-ajot)."""
    from pathlib import Path
    out = Path(out)
    U, L = k1.torni(0.0), k1.torni(1.0)
    from concept.pixel import BLUE, YELLOW
    sok = np.arange(W)[None, :] >= 136                                 # Sokeripalan heijastus vain valaistussa
    U = np.where(sok & (U == YELLOW), BLUE, U)
    U, L = runko.joint(U, L)
    bU, bL, scr, col = runko.encode_pair(U, L)
    (out / "k3.bin").write_bytes(bU + scr + col)
    g, info = groups(U, L)
    lines = ["; torni.py export (kuva 3)", f"NGRP = {len(info)}"]
    lines.append("GR_T    .byte " + ", ".join(str(t // STEP) for t, _ in info))
    lines.append("GR_PH   .byte " + ", ".join(str(t % STEP) for t, _ in info))   # vaihe: ryhmän kello kehyksen myöhässä
    lines.append("GR_P    .byte " + ", ".join(str(p) for _, p in info))
    st = [inc_state(t, p) for t, p in info]
    lines.append(f"T_INC = {T_INC}")
    lines.append("gidx    .byte " + ", ".join(str(y) for y, _ in st))      # job3i: kuvion kohta ja sen alun aika
    lines.append("gacc_lo .byte " + ", ".join(str(a & 255) for _, a in st))
    lines.append("gacc_hi .byte " + ", ".join(str(a >> 8) for _, a in st))
    names = ["pat_tube", "pat_lamp", "pat_late", "pat_glint"]
    lines.append("pat_lo  .byte " + ", ".join(f"<{n}" for n in names))
    lines.append("pat_hi  .byte " + ", ".join(f">{n}" for n in names))
    for n, k in zip(names, (PAT_TUBE, PAT_LAMP, PAT_LATE, PAT_GLINT)):
        lines.append(f"{n} .byte " + ", ".join(map(str, PAT_STEPS[k])))
    lines.append("GR_LO   .byte " + ", ".join(f"<gr{i}" for i in range(len(info))))
    lines.append("GR_HI   .byte " + ", ".join(f">gr{i}" for i in range(len(info))))
    total = 0
    for i in range(len(info)):
        r = xor_runs(bU, bL, g, i)
        total += len(r)
        lines.append(f"gr{i}")
        for j in range(0, len(r), 16):
            lines.append("        .byte " + ", ".join(f"${v:02x}" for v in r[j:j + 16]))
    (out / "k3data.asm").write_text("\n".join(lines) + "\n")
    import kylttipudotus
    ky.tarkista()
    imgs, sk, muutettu = [], [], []
    for i, (ryhma, _, _, L_, *_) in enumerate(ky.KYLTIT):
        bg = at_landing(U, L, g, info, L_ - SHOT3)
        for j, im in enumerate(imgs):                                  # alemmat kyltit palavina (jaetut solut)
            bg[ky.rect(j)] = im["palaa"]
        im, n = ky.kuvat(i, bg, kylttipudotus.DIM, BREATH, U)
        r, c, _, _ = ky.solut(i)
        imgs.append(im)
        muutettu.append(n)
        sk.append({"ryhma": ryhma, "sarake": c, "rivi": r, "laskeutuu": L_, "kuvat": im,
                   **({"lahtee": ky.KYLTIT[i].lahtee} if ky.KYLTIT[i].lahtee else {}),
                   **({"putoaa": ky.KYLTIT[i].putoaa} if ky.KYLTIT[i].putoaa else {})})
    julki: list = []                                                  # julkisivut kp3:n tiedostoon (split.py)
    asm, rep = kylttipudotus.rakenna(sk, tausta=0, y0=Y0_KYLTTI, loppu=END,
                                     hurina=False, lento_t=ky.LENTO_T, lento_vaiheet=ky.LENTO_VAIHEET,   # hurinan tilalla hengitys (kuoppa4)
                                     julki_alueet=list(JULKI_ALUEET), julki_out=julki)
    (out / "kp_data.asm").write_text(asm)
    import json
    (out / "kp_julki.json").write_text(json.dumps([[a, b.hex()] for a, b in julki]))
    (out / "kp4fill.asm").write_text(fill_data(g, info) + breath_data(imgs) + dark_data(g, info))
    return {"groups": len(info), "bytes": total, "kyltit": rep, "rakennuspikseleitä muutettu": muutettu}
