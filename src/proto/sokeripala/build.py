"""Sokeripalan aikataulut (data tools/gfx/data/sokeripala/): build.py OUT ->
OUT/sp.inc, OUT/sp_data.asm ja binäärit. Host antaa vain kuvat, solupalat ja aikataulut (milloin mikin solu
muuttuu, kursorin reitti); 6510 tekee muutokset joka kehys (src/proto/sokeripala/sokeripala.asm).

Kuva 0 (panoraama): pimeä kaupunki nousee esiin yötaivaan alta, panoraama vierii Lohjantähdestä Sokeripalaan ja
pysähtyy, ja Sokeripalan valaistut ikkunat sammuvat ikkuna kerrallaan (keltainen -> oranssi -> ruskea -> sininen).
Pysähdyksen tapahtuma = (kehys, osoite, arvo) ruutuun tai värimuistiin; host seuraa solujen tilaa, joten tavu
sisältää aina myös solun toisen värin.
Kuva 2 (lehti): lehti.py (pyörähdyksen sarakeprofiilit, merkistö ja asennot, kynän vedot pysähtyneelle sivulle).
Kuva 3 (peli): tapahtuma = solun kopio (8 tavua bittikarttaan + ruudun väri) lähdepalasta: ikkunat avautuvat
rivi kerrallaan, tekstit kirjoittuvat, Kulttuuriarvo laskee nollaan. Spritet kehyksittäin (5 tavua).
"""
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lehti as LE  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tools/gfx/data/sokeripala"
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
J = json.loads((DATA / "sokeripala.json").read_text())

# kuvat (kehykset kohtauksen alusta, isku 30, tahti 120)
T_ALKU = 30                                              # alku: yötaivas ja tähdet, pimeä kaupunki nousee esiin
VIERITYS = 480                                           # panoraama vierii T_ALKU..T_PYSAHTYY (1 px kehyksessä, 4 tahtia)
T_PYSAHTYY = T_ALKU - 1 + VIERITYS                       # vieritys alkaa kohdasta 1 kehyksellä T_ALKU
T_LEHTI = T_ALKU + VIERITYS + 30                               # Sokeripalan ikkunat sammuvat (isku), sitten lehti
T_SIVU, T_PELI, T_TAULU, T_LOPPU = (T_LEHTI + x for x in (180, 360, 840, 1080))
SIVU_EV, SIVU_SCR, SIVU_BMP = 0x4000, 0x5C00, 0x6000
SPIN_PROF = [0x9000 + k * LE.PROF_KOKO for k in range(LE.NP)]
SPIN_T19 = SPIN_PROF[-1] + LE.PROF_KOKO                  # 19 rivin taulu profiilien perässä
SPIN_POSE = SPIN_T19 + 19 * LE.NP * LE.N19               # asennot 5 t kehyksessä T19:n perässä (SP2A)
PELI_SCR, PELI_BMP, PELI_BLOB, PELI_SPR = 0x8C00, 0xA000, 0x9000, 0x9400
inc = [f"T_ALKU = {T_ALKU}", f"T_PYSAHTYY = {T_PYSAHTYY}", f"T_LEHTI = {T_LEHTI}", f"T_SIVU = {T_SIVU}", f"T_PELI = {T_PELI}", f"T_TAULU = {T_TAULU}",
       f"T_LOPPU = {T_LOPPU}", f"SPIN_POSE = ${SPIN_POSE:04x}", f"SPIN_T19 = ${SPIN_T19:04x}", f"SPIN_N19 = {LE.N19}", f"SPIN_JAKO = {LE.JAKO}", f"SPIN_R13 = {LE.R13[0]}", f"SPIN_R19 = {LE.R19[0]}", f"REUNUS = {LE.REUNUS}", f"HMAX = {LE.HMAX}", f"SPIN_D022 = {LE.D022}", f"SPIN_D023 = {LE.D023}"]
asm = []


def tavut(nimi: str, data) -> None:
    asm.append(f"{nimi} .byte " + ", ".join(str(int(v)) for v in data))


def tapahtumat(ev: list, alku: int, loppu: int) -> tuple[bytes, list[int]]:
    """(kehys, osoite, arvo) -> 4 t:n tapahtumat kehysjärjestyksessä (kehys alku..loppu-1, sama osoite samassa
    kehyksessä vain viimeinen), pääte $ff; ja kehykset ilman muutosta."""
    uniq = {}
    for i, (t, a, v) in enumerate(ev):
        if alku <= t < loppu:
            uniq[(t, a)] = (i, v)
    rivit = sorted(((t, a, v, i) for (t, a), (i, v) in uniq.items()), key=lambda e: (e[0], e[3]))
    blob = bytearray()
    for t, a, v, _ in rivit:
        blob += bytes([t, a & 255, a >> 8, v])
    kehykset = {e[0] for e in rivit}
    return bytes(blob + b"\xff"), [t for t in range(alku, loppu) if t not in kehykset]


# ---------------------------------------------------------------- kuva 0: panoraama Lohjantähdestä Sokeripalaan
# pano.npy: 144 riviä (merkkirivit 3-20) x 4 NCOL MC-px. Puskuri A pankissa 1 (ruutu $5c00, bittikartta $6000)
# näyttää aluksi sarakkeet 0-39, puskuri B pankissa 3 (ruutu $cc00, bittikartta $e000) täyttyy 6510:n kopiona
# (pankki 2 on lehden pyörähdyksen, ladataan panoraaman aikana). Uudet sarakkeet 40.. tietueina (18 solua:
# 8 bittikarttatavua, sitten 18 ruudun ja 18 värimuistin tavua) vapaissa väleissä: letterboxin rivien 0-2 ja 21-24
# bittikartta näkyy mustana, koska niiden ruutu ja värimuisti ovat nollia.
PR0, PR1 = 3, 21                                         # merkkirivit
pano = np.load(DATA / "pano.npy")
assert pano.shape[0] == (PR1 - PR0) * 8 and pano.shape[1] % 4 == 0
NCOL = pano.shape[1] // 4


def mc_solu(cell: np.ndarray) -> tuple[bytes, int, int]:
    own = sorted(int(v) for v in np.unique(cell) if v != 0)
    assert len(own) <= 3, own
    own += [0] * (3 - len(own))
    slot = {0: 0, own[0]: 1, own[1]: 2, own[2]: 3}
    b = bytes(sum(slot[int(cell[y, x])] << (6 - 2 * x) for x in range(4)) for y in range(8))
    return b, (own[0] << 4) | own[1], own[2]


solut = [[mc_solu(pano[(r - PR0) * 8:(r - PR0) * 8 + 8, c * 4:c * 4 + 4]) for c in range(NCOL)] for r in range(PR0, PR1)]
VIIM = VIERITYS // 8 + 39                                 # viimeinen sarake, joka kopioidaan puskuriin
assert VIIM < NCOL, (VIIM, NCOL)
PA_SA, PA_BA = 0x5C00, 0x6000
m1, m3 = bytearray(0x10000), bytearray(0x10000)
alkuvarit = bytearray(1000)
for r in range(PR0, PR1):                                # puskuri A: ikkuna 0
    for c in range(40):
        b, sc, co = solut[r - PR0][c]
        m1[PA_BA + r * 320 + c * 8:PA_BA + r * 320 + c * 8 + 8] = b
        m1[PA_SA + r * 40 + c] = sc
        alkuvarit[r * 40 + c] = co                       # alkuvärimuisti ytimessä (sp_init kopioi)
# alku (siirtymä spritejen logoista tähtiin): ikkunassa 0 näkyy aluksi vain yötaivas ja tähdet, kaupungin
# värit ovat mustia (solun paikat, joiden pikselit ovat enimmäkseen muuta kuin taivasta); kaupunki nousee esiin
# alhaalta ylös kehyksissä 1 .. T_ALKU-1 (tietue: kehys, solu, oikea ruudun ja värimuistin tavu)
taivas = np.load(DATA / "pano_taivas.npy")
nousu = []
for r in range(PR0, PR1):
    for c in range(40):
        b, sc, co = solut[r - PR0][c]
        cell = pano[(r - PR0) * 8:(r - PR0) * 8 + 8, c * 4:c * 4 + 4]
        tv = taivas[(r - PR0) * 8:(r - PR0) * 8 + 8, c * 4:c * 4 + 4]
        paikka = np.array([[(b[y] >> (6 - 2 * x)) & 3 for x in range(4)] for y in range(8)])
        tumma = [sc >> 4, sc & 15, co]
        for k in range(1, 4):
            pk = paikka == k
            if pk.any() and (~tv & pk).sum() * 2 >= pk.sum():
                tumma[k - 1] = 0
        ts, tc = (tumma[0] << 4) | tumma[1], tumma[2]
        if (ts, tc) != (sc, co):
            m1[PA_SA + r * 40 + c] = ts
            alkuvarit[r * 40 + c] = tc
            nousu.append((r, c, sc, co))
rnd_n = np.random.default_rng(1991)
nousu.sort(key=lambda e: (-e[0] + rnd_n.random() * 1.5, e[1]))
NOUSU0 = 0xC000                                          # SPPI: ennen kelloa, SPP3 latautuu myöhemmin päälle
iblob = bytearray()
for i, (r, c, sc, co) in enumerate(nousu):
    f = 1 + i * (T_ALKU - 1) // len(nousu)
    cell = r * 40 + c
    iblob += bytes([f, cell & 255, cell >> 8, sc, co])
iblob += b"\xff"
(OUT / "pano_nousu.bin").write_bytes(bytes(iblob))
inc += [f"NOUSU0 = ${NOUSU0:04x}"]
# puskutraktori: kaupunginjohtajan eli Hillnerin purkajan kone (concept/dozer.py: 4 x 2 MC-spriteä, 48 x 42 MC-px,
# ylärivi ja alarivin kolme telavaihetta) ajaa torin etualalla oikealle kameran suuntaan ja pysähtyy uhkaavasti
# Sokeripalan eteen. Maailman paikka W (hires,
# panoraaman x + sprite-X:n 24 + 7): ajo W0 + 13/4 dt (ruudulla 9/4 px kehyksessä, tausta vierii 1 px vasemmalle, joten
# etuala liikkuu eri nopeudella kuin tausta), jarrutus tasaisesti TRAK_DN kehystä ryömintään 1/2 px kehyksessä (ruudulla
# huippu ennen oikeaa reunaa, kone ei karkaa kuvasta), ryömintä TRAK_CN kehystä Sokeripalan eteen, sitten seis WS:
# ruudulla x = W - l (l vierityskohta), joten pysähtynyt kone liikkuu taustan mukana kuin maassa seisova esine. Telavaihe
# W / 4 mod 3,
# ylärivi värisee moottorin tahdissa, ajossa kone pomppaa töyssyissä, seis ei pompi (vain ylärivi värisee tyhjäkäynnillä). Tulee vasemmalta,
# kun lähin katto (panoraaman vasen alakulma) on poistunut kuvasta, ja pysyy kuvassa lehteen asti. Spritelohkot
# (samat yhteen, 14) SPP2:n alussa (pankki 1) ja tiedostossa SPT puskurin B letterboxissa (pankki 3, rivit 21-24,
# lohkojen perässä trak_irq ja taulut, TRAK_IRQ); kehyksen laskenta SPP3:ssa tietueiden perässä (TRAK_KOODI).
from concept import dozer  # noqa: E402

DZ = dozer.collapse_dozer()
TRAK_LOHKOT, trak_ptr = [], []                            # ylärivi 4, sitten alarivi 4 kullekin telavaiheelle
for rooli in DZ["body"][0] + [s for vaihe in DZ["tracks"] for s in vaihe]:
    role = np.asarray(rooli)
    b = bytes(sum(int(role[y, 4 * k + j]) << (6 - 2 * j) for j in range(4)) for y in range(21) for k in range(3)) + b"\0"
    if b not in TRAK_LOHKOT:
        TRAK_LOHKOT.append(b)
    trak_ptr.append(TRAK_LOHKOT.index(b))
TRAK_SPR = b"".join(TRAK_LOHKOT)
TRAK_A, TRAK_B = 0x4000, 0xE000 + PR1 * 320                # pankki 1 (SPP2) ja pankki 3 (SPT)
m1[TRAK_A:TRAK_A + len(TRAK_SPR)] = TRAK_SPR
(OUT / "trak_spr.bin").write_bytes(TRAK_SPR)
pa, pb = (TRAK_A & 0x3FFF) // 64, (TRAK_B & 0x3FFF) // 64
trak_osoittimet = []                                      # telavaihe v: ruutu A 8, ruutu B 8 (hw 0-3 ylärivi, 4-7 alarivi)
for v in range(3):
    lohkot = trak_ptr[:4] + trak_ptr[4 + 4 * v:8 + 4 * v]
    trak_osoittimet += [pa + k for k in lohkot] + [pb + k for k in lohkot]
TRAK_T0, TRAK_X0, TRAK_Y = 200, -70, 173                  # tulee kuvaan (katto pois), x vasemmasta reunasta, ylärivin y
TRAK_N = T_LEHTI - TRAK_T0                                # kuvassa lehteen asti
TRAK_W0 = TRAK_X0 + TRAK_T0 - (T_ALKU - 1)                # W = x + l


def trak_w_ajo(dt: int) -> int:
    return TRAK_W0 + 3 * dt + dt // 4                     # kuten trak (6510)


TRAK_D0, TRAK_DN, TRAK_CN = 102, 84, 68                  # jarrutus alkaa (dt), kestää (13/4 -> 1/2), ryömintä
TRAK_D1 = TRAK_D0 + TRAK_DN
TRAK_WD = trak_w_ajo(TRAK_D0)
trak_jarru = [round(3.25 * s - 2.75 * s * s / (2 * TRAK_DN)) for s in range(TRAK_DN)]
TRAK_WC = TRAK_WD + round(1.875 * TRAK_DN)                # ryömintä W = WC + s / 2
TRAK_WS = TRAK_WC + TRAK_CN // 2
trak_wx = [(trak_w_ajo(dt) if dt < TRAK_D0 else TRAK_WD + trak_jarru[dt - TRAK_D0] if dt < TRAK_D1 else
            TRAK_WC + (dt - TRAK_D1) // 2 if dt < TRAK_D1 + TRAK_CN else TRAK_WS)
           - min(TRAK_T0 - 1 + dt - (T_ALKU - 2), T_PYSAHTYY - T_ALKU + 1) for dt in range(1, TRAK_N + 1)]
assert TRAK_D1 < 256 and TRAK_CN < 256 and all(b - a in range(0, 5) for a, b in zip(trak_jarru, trak_jarru[1:]))
assert trak_jarru[-1] <= TRAK_WC - TRAK_WD and max(trak_wx) <= 236 and trak_wx[-1] in range(120, 200), (max(trak_wx), trak_wx[-1])
print(f"traktori: ruudun x huippu {max(trak_wx)}, seis kehyksellä {TRAK_T0 - 1 + TRAK_D1 + TRAK_CN}, lopussa x {trak_wx[-1]}")
assert TRAK_Y + 42 + 1 <= 75 + (PR1 - PR0) * 8, "traktori letterboxissa"
inc += [f"TRAK_OSOITTIMET = {trak_osoittimet}", f"TRAK_A = ${TRAK_A:04x}", f"TRAK_B = ${TRAK_B:04x}",
        f"TRAK_IRQ = ${TRAK_B + len(TRAK_SPR):04x}", f"TRAK_T0 = {TRAK_T0}", f"TRAK_N = {TRAK_N}", f"TRAK_Y = {TRAK_Y}",
        f"TRAK_W0 = {TRAK_W0}", f"TRAK_D0 = {TRAK_D0}", f"TRAK_DN = {TRAK_DN}", f"TRAK_WD = {TRAK_WD}",
        f"TRAK_D1 = {TRAK_D1}", f"TRAK_CN = {TRAK_CN}", f"TRAK_WC = {TRAK_WC}", f"TRAK_WS = {TRAK_WS}",
        f"TRAK_JARRU = {trak_jarru}"]
# järjestys = käyttöjärjestys: ensimmäiset tietueet puskurin A bittikartan väleihin (SPP1, ennen kelloa), loput
# panoraaman aikana ladattaviin (SPP2 $4000-, SPP3 $c000-); $7f40-: sivun FLD:n tyhjä tavu $7fff
VAPAAT = [(m1, PA_BA, PA_BA + PR0 * 320), (m1, PA_BA + PR1 * 320, 0x7F40), (m1, TRAK_A + len(TRAK_SPR), PA_SA),
          (m3, 0xC000, 0xCC00)]
TIETUE = (PR1 - PR0) * 10
osoitteet = []
vi, kohta = 0, VAPAAT[0][1]
for c in range(40, VIIM + 1):
    while kohta + TIETUE > VAPAAT[vi][2]:
        vi += 1
        kohta = VAPAAT[vi][1]
    mm = VAPAAT[vi][0]
    rec = b"".join(solut[r][c][0] for r in range(PR1 - PR0)) + bytes(solut[r][c][1] for r in range(PR1 - PR0)) + \
        bytes(solut[r][c][2] for r in range(PR1 - PR0))
    mm[kohta:kohta + TIETUE] = rec
    osoitteet.append(kohta)
    kohta += TIETUE
TRAK_KOODI = max(a + TIETUE for a in osoitteet if a >= 0xC000)       # puskutraktorin koodi SPP3:ssa
inc += [f"TRAK_KOODI = ${TRAK_KOODI:04x}"]
(OUT / "pano_p1.bin").write_bytes(bytes(m1[PA_SA:0x7F40]))
(OUT / "pano_p2.bin").write_bytes(bytes(m1[0x4000:PA_SA]))
(OUT / "pano_col.bin").write_bytes(bytes(alkuvarit))
alku_n = sum(1 for a in osoitteet if PA_SA <= a < 0x7F40)
inc += [f"PANO_ALKU_N = {alku_n}"]
(OUT / "pano_p3c.bin").write_bytes(bytes(m3[0xC000:0xCC00]))   # puskurin B ruudun nollaa sp_init
tavut("pa_lo", [a & 255 for a in osoitteet])
tavut("pa_hi", [a >> 8 for a in osoitteet])
tavut("pa_rb_lo", [(r * 320) & 255 for r in range(PR0, PR1)])
tavut("pa_rb_hi", [(r * 320) >> 8 for r in range(PR0, PR1)])
inc += [f"PR0 = {PR0}", f"PR1 = {PR1}"]

# pysähdys: Sokeripalan valaistut ikkunat sammuvat ikkuna kerrallaan (keltainen -> oranssi -> ruskea -> sininen
# heijastus) kehyksissä T_PYSAHTYY+1 .. T_LEHTI-1; loppuikkuna k = T_PYSAHTYY / 8 näkyy puskurissa A (k parillinen)
valot = np.load(DATA / "pano_valot.npy")
K_LOPPU = VIERITYS // 8
assert K_LOPPU % 2 == 0
TUMMUU = {7: 8, 8: 9, 9: 6}                              # keltainen -> oranssi -> ruskea -> sininen
askeleet = []                                            # (ikkunan x, solu, paikka, uusi väri)
for r in range(PR0, PR1):
    for c in range(K_LOPPU + 1, K_LOPPU + 39):
        cell = pano[(r - PR0) * 8:(r - PR0) * 8 + 8, c * 4:c * 4 + 4]
        vm = valot[(r - PR0) * 8:(r - PR0) * 8 + 8, c * 4:c * 4 + 4]
        if not vm.any():
            continue
        b, sc, co = solut[r - PR0][c]
        varit = [sc >> 4, sc & 15, co]
        for k, v in enumerate(varit):
            pik = cell == v
            if v in TUMMUU and pik.any() and (vm & pik).sum() >= 0.5 * pik.sum():
                while v in TUMMUU:
                    v = TUMMUU[v]
                    askeleet.append((c, r * 40 + c - K_LOPPU, k, v))
askeleet.sort(key=lambda e: (e[0], e[3] != 8))
N_PYS = T_LEHTI - T_PYSAHTYY - 1
tila = {}
pev = []
for i, (_, solu, k, v) in enumerate(askeleet):
    f = 1 + i * N_PYS // max(len(askeleet), 1)
    rr, cc = divmod(solu, 40)
    b, sc, co = solut[rr - PR0][cc + K_LOPPU]
    t = tila.setdefault(solu, [sc >> 4, sc & 15, co])
    t[k] = v
    if k == 2:
        pev.append((f, 0xD800 + solu, v))
    else:
        pev.append((f, PA_SA + solu, (t[0] << 4) | t[1]))
pblob, ptyhjat = tapahtumat(pev, 1, N_PYS + 1)
tavut("pano_ev", pblob)
# nimi SOKERIPALA Hillnerin otsikon fontilla: 8 MC-spriteä (nimi_spr.bin)
# letterboxin yläkaistalla Sokeripalan katon yllä kuten Hillnerin otsikko. Maailman koordinaatti: ruudun x =
# X - l + 7 (l = vierityskohta), joten nimi tulee kuvaan talon mukana ja pysähtyy sen kanssa. Data kopioidaan
# kehyksissä NIMI_KOPIO + 8 b (vierityksen kevyet kehykset l & 7 = 7) puskurien A ja B yläkaistan bittikarttaan
# (ruutu ja värimuisti nollia), kun puskurin A tietueet 0-4 on käytetty.
NIMI_LEVEYS = 192                                         # hires-px, 8 x 24
nimi_xs = valot.any(0).nonzero()[0]
nimi_keski = int(nimi_xs.min() + nimi_xs.max() + 1)                 # Sokeripalan ikkunoiden keskikohta (hires)
NIMI_X = nimi_keski - NIMI_LEVEYS // 2 + 24 + 7 + T_ALKU - 1        # spriten 0 x = NIMI_X - min(kehys, T_PYSAHTYY)
NIMI_KOPIO, NIMI_Y = 100, 54                               # rasterit 54-70 (yläkaista 51-74, kuva alkaa 75)
assert (NIMI_KOPIO - (T_ALKU - 1)) & 7 == 7 and NIMI_KOPIO - (T_ALKU - 1) >= 8 * 6
NIMI_XMAX = 400                                           # spriten x < 400 (ruudun x 376, PAL-kuvan ulkopuolella)
assert NIMI_KOPIO + 56 < 256 and NIMI_X - (NIMI_KOPIO + 56) >= NIMI_XMAX, "nimi päällä ennen kopiota"
nv = J["nimi"]["varit"]
inc += [f"NIMI_X = {NIMI_X}", f"NIMI_KOPIO = {NIMI_KOPIO}", f"NIMI_Y = {NIMI_Y}", f"NIMI_XMAX = {NIMI_XMAX}", f"NIMI_D025 = {nv['d025']}",
        f"NIMI_D026 = {nv['d026']}", f"NIMI_VARI = {nv['sprite']}"]
shutil.copy(DATA / "nimi_spr.bin", OUT / "nimi_spr.bin")
# sini-heilunta: nimi kelluu
# pystysuunnassa kokonaisena (kaikki spritet samassa y:ssä, joten kirjaimet eivät repeä spritejen rajoilla) kahden
# iskun jaksolla iskusta NIMI_KELLU alkaen (amplitudi kasvaa iskun ajan, ennen sitä y = NIMI_Y), y 51-56 (nimi pysyy
# yläkaistalla 51-74).
NIMI_KELLU, NIMI_JAKSO = 450, 60
nimi_bob = [round(NIMI_Y - 0.5 + 2.5 * min(1, i / 30) * math.cos(2 * math.pi * i / NIMI_JAKSO)) for i in range(T_LEHTI - NIMI_KELLU)]
assert nimi_bob[0] == NIMI_Y and min(nimi_bob) >= 51 and max(nimi_bob) + 20 < 77, nimi_bob
tavut("nimi_bob", nimi_bob)
# hyppy: kun Sokeripala on tullut kuvaan, kuva hyppii iskun tahdissa (heittoparaabeli, laskeutuu iskulle, ylhäällä
# iskujen puolivälissä): kuva alempana HYPPY_H (alhaalla) .. 0 (ylhäällä = alkuperäinen paikka) riviä kahdella
# YSCROLL-kirjoituksella letterboxissa (sokeripala.asm hyppy, kumpikin enintään HYPPY_A riviä). Alkaa ylhäältä
# kehyksellä HYPPY_ALKU, joten kuva ei nyi. Kuvan alareuna enintään rivillä 218 + HYPPY_H (letterbox), nimi pysyy
# paikallaan yläkaistalla.
HYPPY_ALKU, HYPPY_H, HYPPY_A = 315, 0, 5    # HYPPY_H = 0: pomppiminen pois kokonaan
assert HYPPY_ALKU % 30 == 15 and HYPPY_H <= 2 * HYPPY_A and 218 + HYPPY_H < 247
hyppy_fld = []
for t in range(HYPPY_ALKU, T_LEHTI):
    p = (t % 30) / 30
    hyppy_fld.append(round(HYPPY_H * (1 - 4 * p * (1 - p))))
assert hyppy_fld[0] == 0
tavut("hyppy_fld", hyppy_fld)
inc += [f"NIMI_KELLU = {NIMI_KELLU}", f"HYPPY_ALKU = {HYPPY_ALKU}", f"HYPPY_A = {HYPPY_A}"]
print(f"nimi: spriten 0 x lopussa {NIMI_X - T_PYSAHTYY} (ruudun x {NIMI_X - T_PYSAHTYY - 24}), "
      f"ensimmäinen sprite päälle kehyksellä {NIMI_X - NIMI_XMAX + 1}")
print(f"pysähdys: {len(askeleet)} ikkuna-askelta, kehyksiä ilman muutosta {len(ptyhjat)}: {ptyhjat[:20]}")
print(f"panoraama: alussa nousee {len(nousu)} solua ({len(iblob)} t), {NCOL} saraketta, tietueita {len(osoitteet)} ({vi + 1}/{len(VAPAAT)} väliä käytössä), "
      f"ennen kelloa {alku_n} (kehykseen {8 * alku_n})")

# ---------------------------------------------------------------- kuva 2: lehti
lb, ls = (DATA / "lehti.bin").read_bytes(), (DATA / "lehti_scr.bin").read_bytes()
sivu = LE.pura_hires(lb, ls)
cs, prof, t19, rep = LE.merkisto(sivu)
(OUT / "spin_t19.bin").write_bytes(t19)
(OUT / "spin_cs.bin").write_bytes(cs)
for k, b in enumerate(prof):
    (OUT / f"spin_p{k}.bin").write_bytes(b)
N_SPIN = T_SIVU - T_LEHTI
pose = LE.asennot(N_SPIN, s0=0.2)
(OUT / "spin_pose.bin").write_bytes(bytes(v for p in pose for v in p))
assert SPIN_POSE + 5 * N_SPIN <= 0xC000
tavut("sp_plo", [a & 255 for a in SPIN_PROF])
tavut("sp_phi", [a >> 8 for a in SPIN_PROF])
tavut("sp_olo", [LE.siirto(i) & 255 for i in range(LE.JAKO)])
tavut("sp_ohi", [LE.siirto(i) >> 8 for i in range(LE.JAKO)])
tavut("sp_p19", [LE.N19 * p for p in range(LE.NP)])
tavut("sp_kartta", LE.kartta(False) + LE.kartta(True))
# log/exp: u = s * hr / h = exp(log s + log hr - log h), log2 * 32
tavut("sp_log", [0] + [min(255, int(round(32 * math.log2(v)))) for v in range(1, 256)])
tavut("sp_exp", [min(255, int(round(2 ** ((k - 256) / 32)))) for k in range(768)])
# 1024 / W (8.8): sarakkeen (4 MC-px) askel s:ssä, s = 256 sivun leveydellä
rw = [65535] + [min(65535, int(round(262144 / w))) for w in range(1, 161)]
tavut("sp_rwl", [v & 255 for v in rw])
tavut("sp_rwh", [v >> 8 for v in rw])
# terävä sivu: kamera kulkee otsikosta alas kynän perässä, kuva nousee SIVU_FLD0 = 48 -> 1 riviä (alku sama kuin
# pyörähdyksen viimeinen asento, lehti.py HC)
fld_sivu = [1 + int(round((LE.SIVU_FLD0 - 1) * (1 - u) ** 1.6)) for u in (t / (T_PELI - T_SIVU - 1) for t in range(T_PELI - T_SIVU))]
assert fld_sivu[0] == LE.SIVU_FLD0 and pose[-1][:4] == (0, 160, LE.HC, LE.HC), pose[-1]
tavut("fld_sivu", fld_sivu)
kev = LE.kyna(sivu, ls, lb, T_PELI - T_SIVU, SIVU_BMP, SIVU_SCR)
kblob, ktyhjat = tapahtumat(kev, 1, T_PELI - T_SIVU)
(OUT / "sivu_ev.bin").write_bytes(kblob)
assert SIVU_EV + len(kblob) <= SIVU_SCR
(OUT / "sivu_bmp.bin").write_bytes(lb)
(OUT / "sivu_scr.bin").write_bytes(ls)
print(f"lehti: sisältömerkkejä {rep['sisaltomerkit']} ({rep['erilaisia']} erilaista), kynä {len(kblob) // 4} "
      f"tapahtumaa, kehyksiä ilman muutosta {len(ktyhjat)}: {ktyhjat[:20]}")

# ---------------------------------------------------------------- kuva 3: peli
P = J["peli"]
kerr = {}
for n in ("pohja", "ikkunat", "valmis", "sso"):
    b = (DATA / f"peli_{n}.bin").read_bytes()
    s = (DATA / f"peli_{n}_scr.bin").read_bytes()
    kerr[n] = [b[c * 8:c * 8 + 8] + s[c:c + 1] for c in range(1000)]
num = (DATA / "peli_numerot.bin").read_bytes()
numero = [num[i * 9:i * 9 + 9] for i in range(11)]      # " ", "0".."9"
ilm = (DATA / "peli_ilmeet.bin").read_bytes()
ilmeet = [ilm[i * 9:i * 9 + 9] for i in range(len(ilm) // 9)]
shutil.copy(DATA / "peli_pohja.bin", OUT / "peli_bmp.bin")
shutil.copy(DATA / "peli_pohja_scr.bin", OUT / "peli_scr.bin")
shutil.copy(DATA / "peli_spritet.bin", OUT / "peli_spr.bin")

# museovirasto varoittaa, SSO:n edustaja välkkyy sen tilalle ja puhuu, budjetti, Kulttuuriarvo
L_KLIKKI = 30
L_NEUVO, L_NTEKSTI = 36, 48
L_SSO, L_POIS, L_STEKSTI = 148, 150, 174
L_BUDJ, L_BTEKSTI = 262, 272
L_RAHA = 316
L_ARVO = 344
L_OHITA, L_VALI = 336, 416                               # kursori epäröi Ohitan päällä, sitten OK:n ja Ohitan välissä
L_ISKU = 444
N_PELI = T_TAULU - T_PELI
kop = []                                                 # (kehys, solu, 9 tavua)
ikk = [c for c in range(1000) if kerr["pohja"][c] != kerr["ikkunat"][c]]
IKKUNA_AUKI = 8                                          # ikkuna kasvaa keskeltä reunoille kehyksissä


def kasvu(c: int, rect) -> int:
    c0, r0, c1, r1 = rect
    cy, cx = divmod(c, 40)
    d = max(abs(cx + 0.5 - (c0 + c1) / 2) / ((c1 - c0) / 2), abs(cy + 0.5 - (r0 + r1) / 2) / ((r1 - r0) / 2))
    return min(IKKUNA_AUKI - 1, int(d * IKKUNA_AUKI))


for c in ikk:
    if c // 40 <= P["neuvo"][3]:
        kop.append((L_NEUVO + kasvu(c, P["neuvo"]), c, kerr["ikkunat"][c]))
    else:
        kop.append((L_BUDJ + kasvu(c, P["budjetti"]), c, kerr["ikkunat"][c]))
arvo = {P["arvo"][1] * 40 + P["arvo"][0] + i for i in range(2)}
raha = [P["raha"][1] * 40 + P["raha"][0] + i for i in range(len(P["raha"][2]))]


def kirjoitus(tekstit, kerros: str) -> list[list[int]]:
    """Tekstien solut kirjoitusjärjestyksessä riveittäin (välilyönnit, joissa kerros ei muutu, pois)."""
    rivit = []
    for sar, rivi, s in tekstit:
        rivit.append([rivi * 40 + sar + i for i in range(len(s))
                      if kerr[kerros][rivi * 40 + sar + i] != kerr["ikkunat"][rivi * 40 + sar + i]])
    return rivit


museo = [r for r in kirjoitus(P["tekstit"], "valmis") if r and r[0] // 40 <= P["neuvo"][3]]
budj = [r for r in kirjoitus(P["tekstit"], "valmis") if r and r[0] // 40 > P["neuvo"][3]]
sso = kirjoitus(P["sso_tekstit"], "sso")
teksti = {c for c in range(1000) if kerr["ikkunat"][c] != kerr["valmis"][c] and c not in arvo and c not in raha}
assert sorted(teksti) == sorted(c for r in museo + budj for c in r)
t = L_NTEKSTI
for c in (c for r in museo for c in r):                  # museovirasto kirjoittuu, 2 kehystä merkille
    kop.append((t, c, kerr["valmis"][c]))
    t += 2
assert t <= L_POIS
k0, r0, kw, kh = P["sso_kuva"]
kuva = [(r0 + y) * 40 + k0 + x for y in range(kh) for x in range(kw)]
lk, lr, lw, lh = P["sso_logo"]
kuva += [(lr + y) * 40 + lk + x for y in range(lh) for x in range(lw)]   # SSO:n tunnus välkkyy samalla
for r in museo:                                          # ja pyyhkiytyy lopusta alkuun kaikilla riveillä yhtä aikaa
    for i, c in enumerate(reversed(r)):                  # (tunnuksen alle jäävät solut välke korvaa)
        if c not in kuva:
            kop.append((L_POIS + i, c, kerr["ikkunat"][c]))
rng = np.random.default_rng(26)
for c in kuva:                                           # muotokuva välkkyy rivi kerrallaan uuteen (vanha, uusi, ...)
    t0 = L_SSO + 2 * (c // 40 - r0) + int(rng.integers(0, 5))
    for dt, kerros in ((0, "sso"), (2, "ikkunat"), (3, "sso")):
        kop.append((t0 + dt, c, kerr[kerros][c]))
assert max(f for f, c, _ in kop if c in kuva) < L_STEKSTI
puhe = []                                                # (kehys, suun tila) kirjoituksen tahdissa
t = L_STEKSTI
for r, (sar, _, s) in zip(sso, P["sso_tekstit"]):
    for c in r:
        kop.append((t, c, kerr["sso"][c]))
        ch = s[c % 40 - sar].lower()
        puhe.append((t, "auki" if ch in "aeiouyäö" else "pieni" if ch in " .,:!" else "puoli"))
        t += 2
    t += 2
L_SLOPPU = t
assert L_SLOPPU <= L_BUDJ, L_SLOPPU
t = L_BTEKSTI
for c in (c for r in budj for c in r):                   # budjetti kirjoittuu, kehys merkille
    kop.append((t, c, kerr["valmis"][c]))
    t += 1
L_ARVO_NAKYY = t
for i, c in enumerate(raha):
    kop.append((L_RAHA + 8 * i, c, kerr["valmis"][c]))
a0 = min(arvo)
ARVO0 = 87
for v in range(ARVO0, -1, -1):                          # kymmenet vain kun ne vaihtuvat (taulun tila)
    tt = L_ARVO_NAKYY if v == ARVO0 else L_ARVO + (ARVO0 - v)
    if v == ARVO0 or v % 10 == 9:
        kop.append((tt, a0, numero[1 + v // 10] if v >= 10 else numero[0]))
    kop.append((tt, a0 + 1, numero[1 + v % 10]))
# SSO-miehen ilme: silmät ja suu soluina (peli_ilmeet.bin), kasvot muuttuvat vähintään sekunnin välein
silmat = [(L_STEKSTI + 26, "kiinni"), (L_STEKSTI + 30, "keski"), (L_STEKSTI + 48, "oikea"), (L_STEKSTI + 62, "keski"),
          (L_SLOPPU + 2, "oikea"), (L_SLOPPU + 30, "keski"), (L_SLOPPU + 44, "kiinni"), (L_SLOPPU + 48, "vasen"),
          (L_ARVO, "keski"), (L_OHITA + 4, "oikea"), (L_OHITA + 30, "kiinni"), (L_OHITA + 34, "oikea"),
          (L_OHITA + 62, "kiinni"), (L_OHITA + 66, "keski"), (L_ISKU, "isku"), (L_ISKU + 14, "keski"),
          (L_ISKU + 30, "kiinni"), (L_ISKU + 34, "keski")]
suut = puhe + [(L_SLOPPU, "virne"), (L_SLOPPU + 36, "pieni"), (L_SLOPPU + 40, "virne"), (L_ARVO + 40, "auki"),
               (L_ARVO + 44, "virne"), (L_OHITA + 2, "pieni"), (L_VALI + 10, "virne")]
for tilat, nimet, solut, i0 in ((silmat, P["silmat"], P["silma_solut"], 0),
                                (suut, P["suut"], P["suu_solut"], len(P["silmat"]) * len(P["silma_solut"]))):
    ed = None
    for f, tila in sorted(tilat):
        if tila == ed:
            continue
        ed = tila
        for j, (r, c) in enumerate(solut):
            kop.append((f, (r0 + r) * 40 + k0 + c, ilmeet[i0 + nimet.index(tila) * len(solut) + j]))
kop.sort(key=lambda e: e[0])
lahde, paikka = bytearray(), {}
LAHDE2 = PELI_SPR + 5 * N_PELI                          # lähdepalojen jatko spritetaulun perässä (SP3)
n1 = (PELI_SPR - PELI_BLOB) // 9 * 9
for _, _, d in kop:
    if d not in paikka:
        n = len(lahde)
        paikka[d] = PELI_BLOB + n if n < n1 else LAHDE2 + n - n1
        lahde += d
assert LAHDE2 + len(lahde) - n1 <= PELI_BMP, f"pelin lähdepalat {len(lahde)} t"
(OUT / "peli_blob.bin").write_bytes(bytes(lahde[:n1]))
(OUT / "peli_blob2.bin").write_bytes(bytes(lahde[n1:]))
rec = []
for f, c, d in kop:
    rec += [f & 255, f >> 8, (PELI_BMP + 8 * c) & 255, (PELI_BMP + 8 * c) >> 8, (PELI_SCR + c) & 255,
            (PELI_SCR + c) >> 8, paikka[d] & 255, paikka[d] >> 8]
rec += [255, 255]
assert 0xE000 + len(rec) <= 0xFFFA, len(rec)
(OUT / "pe_tab.bin").write_bytes(bytes(rec))


# kursorit: kaupunginjohtaja (hiiri) ja timantti, joka hyppää ruudukossa hiiren alle
def ease(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


sx, sy = P["sokeripala"]
KJ_JALAT = (7, 16)                                       # kaupunginjohtajan jalat suhteessa spriten kulmaan
alku = (300.0, 186.0)
klikki = (sx - KJ_JALAT[0], sy - KJ_JALAT[1] - 2)
ok = (P["ok"][0] * 8 + 8.0, P["ok"][1] * 8 - 6.0)
ohita = (P["ohita"][0] * 8 + 20.0, P["ohita"][1] * 8 - 6.0)
vali = ((ok[0] + ohita[0]) / 2 - 7, ok[1])               # jalat nappien väliin (OK solut 9-12, Ohita 16-22)
lepo = (sx - 30.0, sy - 40.0)


def lerp(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def vaeltaa(L: int) -> tuple[float, float]:
    """Käsi lepää hiirellä: pieni jatkuva liike (noin pikseli kehyksessä)."""
    return (9 * math.sin(L / 9.0), 5 * math.sin(L / 6.5))


def kj(L: int) -> tuple[float, float]:
    if L < L_KLIKKI - 6:
        return lerp(alku, klikki, ease(L / (L_KLIKKI - 6)))
    if L < L_KLIKKI + 8:
        return (klikki[0], klikki[1] + (1 if L_KLIKKI <= L < L_KLIKKI + 4 else 0))
    u0 = L_KLIKKI + 8
    if L < L_OHITA:                                      # odottaa kartalla Sokeripalan yllä
        p = lerp(klikki, lepo, ease((L - u0) / 40))
        w = vaeltaa(L - u0)
        return (p[0] + w[0], p[1] + w[1])
    if L < L_VALI:                                       # Ohitan päälle, epäröi
        w0 = vaeltaa(L_OHITA - u0)
        p = lerp((lepo[0] + w0[0], lepo[1] + w0[1]), ohita, ease((L - L_OHITA) / 50))
        w = (L - L_OHITA) / 3.0
        return (p[0] + 2 * math.sin(w), p[1] + 1.5 * math.cos(w * 1.3))
    w = (L_VALI - L_OHITA) / 3.0
    p0 = (ohita[0] + 2 * math.sin(w), ohita[1] + 1.5 * math.cos(w * 1.3))
    u = ease((L - L_VALI) / 36)
    p = lerp(p0, vali, u)
    w = (L - L_VALI) / 13.0                              # päätöstä ei ole tehty: epäröi nappien välissä, ei paina
    return (p[0] + u * (2 * math.sin(w) + 1.5 * math.sin(w * 5.2)), p[1] + u * (math.sin(w * 1.4) + 1.5 * math.cos(w * 7.1)))


def kopteri(L: int, toinen: bool = False) -> tuple[int, int]:
    """Uutiskopterit (2 kertaa levennetyt spritet, 48 x 42) kiertävät Sokeripalaa isometrisinä ellipseinä kartan
    oikealla puolella ikkunoiden ulkopuolella, noin pikseli kehyksessä, toinen vastakkaiseen suuntaan."""
    a = 2 * math.pi * (L % KIERROS) / KIERROS + 0.6
    if toinen:
        a = -a + 2.4
        cx, cy = sx + 12 + 22 * math.cos(a), sy + 10 + 22 * math.sin(a)
    else:
        cx, cy = sx + 8 + 26 * math.cos(a), sy - 40 + 14 * math.sin(a)
    return int(round(cx - 24)), int(round(cy - 21))


KIERROS = 180                                            # kopterin kierros kehyksinä (taulu yhdelle kierrokselle)
HELI = 0x8900                                            # kopterien paikat pelin spritejen perässä (SP3)
spr = []
prev, paikallaan = None, []
kop_f = {f for f, _, _ in kop}
for L in range(N_PELI):
    x, y = kj(L)
    x, y = int(round(x)), int(round(y))
    if (x, y) == prev and L not in kop_f and L > 0:
        paikallaan.append(L)                             # muuttuu silti: valintatimantin viiva kiertää
    prev = (x, y)
    fx, fy = x + KJ_JALAT[0] - sx, y + KJ_JALAT[1] - sy   # timantti ruudukossa jalkojen alle
    i, j = round((fx / 16 + fy / 8) / 2), round((fy / 8 - fx / 16) / 2)
    dx, dy = sx + 16 * (i - j) - 16, sy + 8 * (i + j) - 8
    if L >= L_KLIKKI:
        dx, dy = sx - 16, sy - 8
    X0, X1, XK = dx + 24, dx + 48, x + 24
    hx, hy = kopteri(L)
    hx2 = kopteri(L, True)[0]
    msb = (3 if XK > 255 else 0) | (0x14 if X0 > 255 else 0) | (0x28 if X1 > 255 else 0) | \
        (0x40 if hx + 24 > 255 else 0) | (0x80 if hx2 + 24 > 255 else 0)
    spr += [XK & 255, y + 50, X0 & 255, dy + 50, msb]
assert PELI_SPR + len(spr) <= 0xA000
(OUT / "peli_sprt.bin").write_bytes(bytes(spr))
hb = bytes([(kopteri(L)[0] + 24) & 255 for L in range(KIERROS)] + [kopteri(L)[1] + 50 for L in range(KIERROS)] +
           [(kopteri(L, True)[0] + 24) & 255 for L in range(KIERROS)] + [kopteri(L, True)[1] + 50 for L in range(KIERROS)])
assert 0x8000 + len((DATA / "peli_spritet.bin").read_bytes()) <= HELI and HELI + len(hb) <= PELI_SCR
(OUT / "peli_heli.bin").write_bytes(hb)
inc += [f"KIERROS = {KIERROS}", f"HELI = ${HELI:04x}"]
print(f"peli: {len(kop)} solukopiota, lähdepalat {len(lahde)} t, kehyksiä ilman muutosta {len(paikallaan)}: {paikallaan}")

inc += [f"PELI_SPR = ${PELI_SPR:04x}", f"N_PELI = {N_PELI}", f"PELI_BLOB2 = ${LAHDE2:04x}"]
(OUT / "sp.inc").write_text("\n".join(inc) + "\n")
(OUT / "sp_data.asm").write_text("\n".join(asm) + "\n")
