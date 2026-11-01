"""Koti (demon kohtaus 2): kamera nousee kissan korkeudelta portailta, ja Lohjanjärvi paljastuu aidan ja
naapurien kattojen takaa. Staattinen data: kuva riveittäin, asettelut, kaukaisen kerroksen $D021-muutokset,
spritelohkot ja instanssitaulut, värimuistin kopiokoodi ja liikekäyrä.

  uv run --project tools/concept python src/proto/koti/build.py build/koti [--integrated]

Data: tools/gfx/data/koti/ (metadata.json, bittikartta_keltainen.npy 160 x (144 + vieritys), 255 = MC 00 =
rivin $D021; rasteri.npy; kissa3_kehykset.npy ja kissa3.json (etualan kissa); ilta_v4.json ja ilta_v4_maski.npy
(ilta); ranta_spritet.npy). Moottori src/lib/crunch.asm.
"""
from __future__ import annotations

import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/gfx"))
sys.path.insert(0, str(ROOT / "tools/concept"))

from c64fmt import _lab_dist, encode_layers  # noqa: E402

DATA = ROOT / "tools/gfx/data/koti"
TRANSP = 255
WIN = 144                     # ikkuna 320 x 144 (rivit 72-215)
T_LINE = 72                   # ikkunan ensimmäinen rasteririvi (crunch.asm)
SPR_TOP, SPR_BOT = 73, 215    # spritet vain näillä riveillä (koti.asm)
LINE_BOT = 213                # alareunan IRQ (koti.asm): tapahtumat ennen sitä
CMAX = 6
BANK_ROWS = 25
CODE_BASE = 0x1A00
REC_LIMIT = 0x8000            # koodi, spritelohkojen lähde ja kuvan tietueet $1a00:sta tähän asti
BSS_DEMO = 0x4000             # ajonaikaiset taulukot demossa ($4000-$47ff, COLSTAGE $9000; greetsit esiladataan $4800-)
BSS_PROTO = 0x0900            # erillisohjelmassa (musiikki on $9000:ssa, purkupuskuri $1700-)
MUSIC_ADDR = 0x9000           # erillisohjelman musiikki (pankin 2 merkkiROM-kohta, ei VIC:n käytössä)
MSTART = 12123                # biisin kehys kellon alussa
SPR_OFS = 0x0400              # spritelohkot molemmissa pankeissa samassa kohdassa ($8400 ja $c400): sama osoitin
SPR_END = 0x1000              # pankin 2 merkkiROM alkaa $9000:sta
N_CLIP = 32                   # leikkauspuskurit: 2 joukkoa x 2 reunaa x 8 spriteä
SPR_COL = (11, 15)            # $D025, $D026 (metadata.json: roolit 1 ja 3)
N_MAIN = (SPR_END - SPR_OFS) // 64 - N_CLIP   # spritelohkot leikkauspuskurien jälkeen (16)
N_XTRA = 16                   # loput lohkot yläreunan leikkauspuskureihin (joukko 0 $8400/$c400 spr_xsrc, joukko 1
                              # $8800/$c800 spr_ysrc): yläreunaa (rivi 73) ei ylitä mikään (build tarkistaa), ja vain
                              # kissan aikana käytetyt; koti_quiet kirjoittaa pitomoottorin niiden päälle myöhemmin
BIRD_LOW = 16                 # kissan näkyessä pääskysen 21 rivin ikkuna alkaa näin monta riviä aiemmin (data spriten
                              # alarivillä, sama kuva): sprite vapautuu kissan alemmille viipaleille (silmät + 3
                              # viipaletta + 3 pääskystä tarvitsisivat muuten 9 spriteä kissan rivin 100 kohdalla)

# Etualan kissa 3 (kissa3*.npy ja kissa3.json; lähempänä ruutua ja ylempänä syvyysvaikutelman vuoksi): 36 x 98 MC-px
# MC-spriteinä ilman laajennusta, solut 12 x 21 kolmessa
# sarakkeessa porrastettuina (sarakkeiden solurajat 7 rivin välein: vain yksi sarake vaihtaa spriteä kerrallaan, joten
# kissa, 3 pääskystä ja vaihdot mahtuvat 8 spriteen). Kissan kehyksissä $D025 = 0 (musta) ja $D026 = 1 (valkoinen),
# solun oma väri kissa3.json:sta (runko 15, silmät 13, korvan sisus 10). Pää (solut (0, 0) ja (0, 21)) ja häntä
# (solu (1, 77)) elävät eri tahdeissa: tilat kehyksittäin kohtauksen alusta (an_head, an_tail).
CAT_COL = (0, 1)              # $D025, $D026 kissan kehyksissä
# Koti ja loppu yhteen (talo häviää kokonaan kuvasta, jäljelle jää Lohjanjärven maisema, jonka värit vaihtuvat
# paletilla iltaan): kuvan yläpuolelle EXTRA tyhjää riviä
# (MC 00 = kaukainen kerros), joten talo vierii nousun aikana kokonaan ulos alareunasta. Kuvan
# alimmat CUT riviä jäävät pois (aloituskuva 16 px ylempänä), jotta p mahtuu 8 bittiin (p_max = 248).
EXTRA = 144
MDIV = 16                     # liikekäyrän arvo MDIV kehyksen välein (KOTI1:n tila illan maskille)
PSUB = 256                    # kameran paikka 1/256 px (16 bittiä, p_max 248): hitaassa alussa (noin 0,04 px/kehys)
                              # nopeus on tarkka, joten kamera ei pysähdy 16 kehykseksi, kuten 1/16 px:n tarkkuudella
                              # pysähtyisi (nopeus 0 tai 1: kissan liike nykisi). Bittikartan paikka
                              # pyöristettynä (koti.asm lf_place: (pos + 128) >> 8), kissa tarkasta paikasta
CUT = 16
HORIZ = 40                    # vastarannan yläreuna ikkunan rivinä (p = 0): taivas sen yläpuolella
D21EV_MAX = 138               # $D021-tapahtumat (taivassilmukan alla) riville 138 asti (koti.asm _d21ev)
SKY_LAST = 72                 # taivassilmukka enintään ikkunan riville 72 (rasteri 144): pidempi silmukka vie
                              # pääsilmukalta asettelun rakentamisen ajan, ja hyvin pitkä myöhästyttää alareunan IRQ:n;
                              # rivit 73- jatkavat rivin 72 väriä, alemmat tapahtumina (koti.asm _d21ev)
MOVE_END = 495                # kamera perillä (p = 0) samalla vauhdilla (ei hidastusta järven jälkeen):
                              # tekijät piirtyvät käsialana heti pysähdyksen jälkeen; taivas on 40 riviä, joten nimet
                              # pysyvät siinä vain kameran seistessä
ILTA_F = 656                  # ilta maalautuu taivaalle ylhäältä alas (ilta_step) tästä kehyksestä, heti kun tekijät
                              # ovat valmiit (652)
SUNSET_F = -8                 # sunset_step askel 1/kehys alkaen 8 kehystä ennen kuin maalaus on kimallusriveillä
SUNSET_STEP = 1               # (sunset_f maalausjärjestyksestä; askel 8: kimallus lämpimäksi, 10: Liessaari tummaksi).
                              # Iltavärit tulevat ilta_stepin maalauksen mukana
BIRD_RET = 450                # pääskyset tulevat järven ylle nousun jarrutuksessa (liike loppuun asti, myös
                              # tekijäjaksossa) ja kiertävät spriteillä 0-2
BIRD_GONE = -40               # ja ovat poissa ruudulta tähän mennessä, kohtauksen lopusta (kodin pituudella 960 lokit
                              # kiertävät reunan taakse kaikki yhtä aikaa kehyksestä 907, bird_gaps) (bird_out: lopun
                              # kehys 0 ilman pääskysiä; scene_len)
BIRD_RROWS = [88, 92, 96]     # paluun rivit järven yllä nimien välissä (lokki siipineen rivit r - 1 .. r + 8,
                              # VICE; dipe 56-86, patemathic 106-138, CRED_TOP), spritet 0-2 (spriteillä 3-7 21 rivin
                              # DMA rivin alussa myöhästyttäisi illan $D021-tapahtumat 91, 99, 115 ja 123: harmaa
                              # piste vasemmassa reunassa)
DUSK_END, DUSK_STEP, DUSK_N = -10, 50, 2   # tummuminen illan jälkeen: DUSK_N askelta DUSK_STEP kehyksen välein, viimeinen
DK_B = 20                     # valmis DUSK_END kehystä ennen kohtauksen loppua (dusk_step); askel merkkirivi kerrallaan, DK_B
                              # ruututavua kehyksessä (40 / DK_B kehystä riviltä; hitaampi askel pitäisi kuvan liian
                              # kauan paikallaan ja lyhentäisi iltaa)
DUSK = [0, 15, 9, 14, 11, 9, 6, 10, 2, 9, 8, 11, 11, 5, 4, 12]   # väri -> tummempi: luma alas, ja kaistojen parit
#        pysyvät eri väreinä kahden askeleen jälkeen (4 -> 11, ei 6: järven violetti heijastus ei liukene siniseen)
SKY_MAX = WIN - 1             # ilta_step kirjoittaa $D021:n koko ikkunaan (ilta_v4.json: rivistä 123 alas musta)
EVE_D025, EVE_D026 = 0, 11    # Liessaari tummaksi siluetiksi askeleesta 10

HEAD_STATES = ["perus", "korva", "silmat_kiinni", "katse_kuistille"]
TAIL_STATES = ["perus", "hanta_maassa", "hanta_koukku"]
HEAD_SEQ = [(20, "korva"), (62, "silmat"), (96, "katse"), (128, "silmat"), (178, "korva")]  # (kehys, kissa3.json rytmi)

# Lokit (siipiasennot BIRD_ART) ovat poissa ruudulta paluuseen (BIRD_RET) asti: lokit lentävät taivaalla eivätkä
# portailla. (ikkunan rivi, lähtö-X hires, nopeus 1/16 px/kehys, vaihe). Rivit taivasvyöhykkeen alla
# (SKY_T - p <= 101), jotta spritet 3-7 eivät myöhästytä taivassilmukan $D021-kirjoitusta. X kiertää 9 bittiä:
# oikean reunan takaa vasemmalle.
BIRDS = [(104, 40, 26, 0), (111, 300, -22, 11), (118, 170, 31, 21)]

# Tekstit alemmassa letterboxissa hires-spriteinä 0-3 (alareunan IRQ ohjelmoi ne ikkunan jälkeen ja multiplekserin
# seuraavan kehyksen spritet vasta tekstien jälkeen): (teksti, X hires, väri).
# "1959" ei voi olla kuvan yläpuolella: yläreunan rivit 47-72 ovat linecrunchin sekvensserin (ei spritejä).
TEXTS = [("1959", 304 - 32, 0)]   # "1959" piilossa: väri 0 = musta mustalla letterboxilla
                                  # (tekstispritet säilyvät)
TEXT_LINE = 226               # ensimmäinen rivi (ikkunan alareuna 215, teksti noin riveillä 226-233)
MAX_HW = 8
TXT_HW = 0                    # koti.asm TXT_HW: tekstien ensimmäinen sprite
CT_HW = (4, 5, 6, 0, 1, 2, 3, 7)   # koti.asm ct_hw: kissan alareunan instanssien sprite (vapaa riviltä 191)
BIRD_WAVE = (0, 2)            # koti.asm bd_fw: pääskysen rivin aalto + 1 (rivit br_line = 72 + r - 1)
# Lokkien siivenlyönti (lokit liikuttavat siipiä eivätkä vain pompi): viisi asentoa (# musta, + harmaa), ruumis
# rivillä 4, siivenkärjet riveillä 0-7
# jyrkkinä (X-laajennettu pikseli on 4 hires-pikseliä leveä). Kierto 32 kehystä: lyönti alas (ylhäällä, puoliylhäällä,
# vaaka, puolialhaalla, alhaalla, 3 kehystä kukin) nostaa riviä ylemmäs, nosto takaisin ja 8 kehyksen liito laskee.
# Linnut eri vaiheissa (BIRDS: vaihe).
BIRD_ART = [
    ["#.........#",
     ".#.......#.",
     ".##.....##.",
     "..##...##..",
     "....#+#...."],
    ["...........",
     "...........",
     "##.......##",
     ".+##...##+.",
     "....#+#...."],
    ["...........",
     "...........",
     "...........",
     ".##.....##.",
     "#+.##+##.+#"],
    ["...........",
     "...........",
     "...........",
     "...........",
     "..###+###..",
     ".#+.....+#.",
     "#.........#"],
    ["...........",
     "...........",
     "...........",
     "...........",
     "...##+##...",
     "..#+...+#..",
     ".##.....##.",
     ".#.......#."],
]
BIRD_SEQ = [0] * 3 + [1] * 3 + [2] * 3 + [3] * 3 + [4] * 3 + [3] * 3 + [2] * 3 + [1] * 3 + [2] * 8   # lyönti 24, liito 8
BIRD_DY = [1] * 3 + [0] * 6 + [-1] * 15 + [0] * 4 + [1] * 4         # rivi: lyönti alas nostaa, liito laskee
GL_STEP = 8                   # järven kimallus: kehystä per väriaskel rivillä; rivien askeleet
                              # porrastettu eri kehyksiin, joten jokin rivi vaihtuu joka kehys

HOLD0 = 0                     # ei pitoa: nousu kestää koko kohtauksen (ei kuollutta kuvaa)
MOVE = 300                    # nousu (oletus; aikajanalla kohtauksen pituudesta, scene_move())
HOLD_END = 0
                              # kuva ylhäällä (pääskyset ja kimallus jatkuvat)
ACC = 110
DEC = 90
SLOW = 120                    # nousun hidas alku (KOTI4 latautuu), V_SLOW px/kehys
V_SLOW = 0.04
V_MIN = 0.4                   # pienin nopeus suhteessa huippuun (kohtaus alkaa ja loppuu leikkaukseen liikkeessä)


def px(q: int) -> int:
    """Bittikartan paikka (kokonaiset pikselit) kameran paikasta 1/PSUB px (koti.asm lf_place)."""
    return (int(q) + PSUB // 2) // PSUB


def ilta_tables() -> dict:
    """Iltataivas ja järvi ditherinä: ilta_v4_maski.npy (144 x 160 MC-px, kuva
    p = 0) %00/%01-maskina ja ilta_v4.json kaistoina ($D021 ja maskin väri). Maski on suunniteltu lopun merkkiriveille
    (ikkunan rivit 3 + 8k); kodissa p = 0:ssa merkkirivit ovat ikkunan rivit 8k, joten merkkirivissä voi olla kahden
    siirtymän maskiväri: ylempi %01 (ruudun ylänibble), alempi %10 (alanibble). Tekijät %11 (värimuisti).
    Palauttaa rivien $D021:n (0..SKY_MAX), merkkirivien ruututavut, maskirivit (20 tavua, bitti = MC-pikseli)
    ja maalauslistan (rivi | 128 * %10, maskirivin indeksi)."""
    ilta = json.loads((DATA / "ilta_v4.json").read_text())         # v4: järven alaosa ditherinä
    mask = np.load(DATA / "ilta_v4_maski.npy").astype(bool)
    d021, c01 = [0] * WIN, [0] * WIN
    for b in ilta["kaistat"]:
        for y in range(*b["rivit"]):
            d021[y], c01[y] = b["d021_ilta"], b["c01_ilta"]
    nb = next(b["rivit"][0] for b in ilta["kaistat"] if b["rivit"][0] > SKY_LAST)   # kaistaraja heti silmukan jälkeen
    for y in range(SKY_LAST, nb):                           # (75) tapahtumana myöhästyisi riville 77 kesken rivin:
        d021[y] = d021[nb]                                  # raja silmukkaan (maski on niillä riveillä jo lähes c01)
    rows = [y for y in range(WIN) if mask[y].any()]
    assert max(rows) < 128 and all(d021[y] == 0 for y in range(SKY_MAX, WIN))
    scr, slot = [], {}
    for k in range((max(rows) >> 3) + 1):
        cols: list[int] = []
        for y in range(8 * k, 8 * k + 8):
            if y in rows and c01[y] not in cols:
                cols.append(c01[y])
        assert len(cols) <= 2, (k, cols)
        for y in range(8 * k, 8 * k + 8):
            if y in rows:
                slot[y] = cols.index(c01[y])
        cols += [0] * (2 - len(cols))
        scr.append(cols[0] << 4 | cols[1])
    bits = [bytes(int("".join("1" if v else "0" for v in mask[y, 8 * j:8 * j + 8]), 2) for j in range(20)) for y in rows]
    uniq = list(dict.fromkeys(bits))
    img = np.full((WIN, 160), TRANSP, np.uint8)            # lopun kuvan maskipikselit väreinä
    for y in rows:
        img[y][mask[y]] = c01[y]
    return {"d021": d021[:SKY_MAX + 1], "scr": scr, "uniq": uniq, "img": img, "c01": c01, "mask": mask, "slot": slot,
            "list": [(y | 128 * slot[y], uniq.index(bits[i])) for i, y in enumerate(rows)]}


def bird_gaps(bx: list[int], out: int) -> list[int]:
    """Kehykset BIRD_RET + 10 .. BIRD_GONE - 14, joina yksikään palannut pääskynen ei ole ruudulla (X-laajennettu
    näkyy, kun X < 344 tai X > 488; kehyksestä out alkaen piiloon mennyt ei palaa, koti.asm)."""
    gone, gaps, end = [False] * len(BIRDS), [], scene_len() + BIRD_GONE
    for f in range(BIRD_RET, end):
        n = 0
        for i, ((_, _, dx, _), x0) in enumerate(zip(BIRDS, bx)):
            x = ((16 * x0 + dx * (f - BIRD_RET)) & 0x1FFF) >> 4
            gone[i] |= f >= out and 352 <= x < 480
            n += not gone[i] and (x < 344 or x > 488)
        if not n and BIRD_RET + 10 <= f <= end - 14:
            gaps.append(f)
    return gaps


def bird_out(bx: list[int]) -> int:
    """Myöhäisin kehys, josta alkaen pääskynen ei enää palaa reunan takaa (koti.asm: X-laajennettu sprite on kokonaan
    piilossa, kun 352 <= X < 480), niin että kaikki ovat poissa ennen BIRD_GONE:a (runko: lopun kehys 0 ilman
    pääskysiä, lopun spritet ovat tekstirivien käytössä)."""
    def last(out: int) -> int:                              # piilossa vielä 8 kehystä: koodin frame voi olla
        worst = 0                                           # kehyksen tai pari tästä mallista jäljessä
        for (_, _, dx, _), x0 in zip(BIRDS, bx):
            hid = [352 <= ((16 * x0 + dx * (f - BIRD_RET)) & 0x1FFF) >> 4 < 480 for f in range(BIRD_RET, 4000)]
            worst = max(worst, next(f for f in range(out, 3990) if all(hid[f - BIRD_RET:f - BIRD_RET + 9])))
        return worst
    end = scene_len() + BIRD_GONE
    return next(o for o in range(end, BIRD_RET, -1) if last(o) <= end)


VALKE = ROOT / "tools/gfx/data/loppu/maisema.json"   # järven välke kuten lopussa (sauma jatkuu)
VK_DT = 6                     # kehystä vaihetta kohden (tools/disk/loppu.py VK_DT)
GL_LEN = 1440                 # kodin viitepituus: kimalluksen vaihe lopussa sen mukaan (gl_add), joten lopun kuva
                              # ei riipu kodin pituudesta
VK_F = ILTA_F + 152           # alkaa, kun ilta on maalattu (ilta_step ILTA_F .. ILTA_F + 150, main tarkistaa)
VK_PARTS = 6                  # vaihdos kuudessa kehyksessä (koko vaihe; kolmessa spritelaskennan pelivara jäisi
                              # alle 1 000 syklin)
VD_ROW = 48                   # päivän välke (tekijäjaksossa järvi ei seiso) kameran pysähdyksestä iltaan:
                              # vain järven rivit (ylempänä vastarannan kaistat), samat vaiheet kuin illalla
VR_LEAD = 3                   # nousun välkkeen värimuisti viimeisen asettelun vaihdon (ja sen värikopion) jälkeen
VR_PR_MIN = 30                # nousun välke viimeistään ppx:stä 30 (osalevyllä KOTI5 on ladattu noin ppx 26:ssa)
VD_COL = {14: 1, 6: 14}       # päiväjärven väri ($D021) -> välkkeen väri (%11): vaalea kaista valkoinen, sininen vaaleansininen


def valke(il: dict, scene_len: int, bmp: bytes, far: np.ndarray, cred: list[tuple[int, int, int]],
          crbs: list[tuple[int, int, int, int]]) -> tuple[list[str], list[str], np.ndarray, np.ndarray, list]:
    """Järven välke (maisema.json valke_vaiheet, vaakaviivat ikkunan riveillä) kodin loppukuvaan p = 0: vaiheen
    pikselit MC %11 bittikarttaan (värimuisti = solun yleisin viivaväri, taivaan rivit 0-39 pois). Vaihe
    ((DFRAME - TIM_SCENE_KOTI_START + VK_OF) mod VK_N * VK_DT) // VK_DT, VK_OF = KOTI_START - LOPPU_START, eli
    sama vaihe demon kellosta kuin loppu.asm vk_stepissä (rel), myös lopun latausvälin yli. Vaihdoksen p - 1 -> p
    tavut (osoite, uusi arvo: maalatun maskin tavu ja uuden vaiheen %11) listassa vk_l<p>; sama lista aloittaa välkkeen
    myös välkkeettömästä kuvasta (edellisen vaiheen solut saavat maskin tavun). Päivällä (koti.asm vk_md) samat listat
    alkaen riviltä VD_ROW (vk_d0) ja tavusta vain %11 (maski on %01/%10), värimuisti päiväjärven värin mukaan (VD_COL:
    solut 0..VD_K-1 vaalealla kaistalla). Tekijöiden merkkisoluista välke pois: välkkeen tavu pyyhkisi nimet, ja %11:n
    värimuisti on solulle yhteinen (nimet valkoisia; lopun käsiala on kuvan valkoiset pikselit, tools/disk/loppu.py).
    Päivällä cred_step värittää nimien suorakaiteet crbs = [(rivi0, rivi1, sarake0, leveys)] alussa ja taukonsa jälkeen,
    joten niiden välke on silloin valkoista. Palauttaa (koti.inc, taulut KOTI5:een, illan ja päivän mallin pikselit)."""
    m = json.loads(VALKE.read_text(encoding="utf-8"))
    mask, slot = il["mask"], il["slot"]

    def byte(y: int, cx: int) -> int:                       # maalatun maskin tavu (MC-pikselit 4cx..4cx+3)
        b = 0
        for i in range(4):
            if mask[y, 4 * cx + i]:
                b |= (2 if slot[y] else 1) << (6 - 2 * i)
        return b
    ccell = {(y >> 3, x >> 2) for y, x, _ in cred}
    phases, vcol, model = [], {}, []
    for ph in m["valke_vaiheet"]:
        byt: dict = {}
        for ln in ph:
            y = ln["rivi"]
            if not 40 <= y < WIN:                           # taivas (rivit 0-39) pois
                continue
            for x in range(max(0, ln["x0"]), min(159, ln["x1"]) + 1):
                if (y >> 3, x >> 2) in ccell:               # tekijöiden merkkisolu: ei välkettä
                    continue
                vcol.setdefault((y >> 3, x >> 2), []).append(ln["vari"])
                byt[(y, x >> 2)] = byt.get((y, x >> 2), 0) | 3 << (6 - 2 * (x & 3))
                model.append((y, x, 0))
        phases.append(byt)
    ccol = {k: max(set(v), key=v.count) for k, v in vcol.items()}
    assert not any(bmp[(y >> 3) * 320 + cx * 8 + (y & 7)] for y in range(40, WIN) if y not in slot for cx in range(40))
    model = [(y, x, ccol[(y >> 3, x >> 2)]) for y, x, _ in model]
    n = len(phases)
    tim = timing()
    of = (tim.get("TIM_SCENE_KOTI_START", 0) - tim.get("TIM_SCENE_LOPPU_START", scene_len)) % (VK_DT * n)

    def lst(old: dict, new: dict) -> list[tuple[int, int, int]]:   # rivijärjestyksessä (päivä alkaa riviltä VD_ROW)
        return [(y, 0xE000 + (y >> 3) * 320 + cx * 8 + (y & 7), byte(y, cx) | new.get((y, cx), 0))   # pankki 3 (+ badj)
                for y, cx in sorted(set(old) | set(new))]
    lists = [lst(phases[p - 1], phases[p]) for p in range(n)]
    assert max(len(v) for v in lists) <= 85
    assert all(far[y] in VD_COL for y in range(VD_ROW, max(y for y, _, _ in model) + 1)) and far[VD_ROW - 1] not in VD_COL
    tab = []
    for k, v in enumerate(lists):
        tab += [f"vk_l{k}  .byte " + ", ".join(f"${a & 255:02x}, ${a >> 8:02x}, ${b:02x}" for _, a, b in v)]
    tab += byte_lines("vk_d0", [3 * next((i for i, (y, _, _) in enumerate(v) if y >= VD_ROW), len(v)) for v in lists])
    tab += ["vk_llo  .byte " + ", ".join(f"<vk_l{k}" for k in range(len(lists)))]
    tab += ["vk_lhi  .byte " + ", ".join(f">vk_l{k}" for k in range(len(lists)))]
    tab += byte_lines("vk_ln", [3 * len(v) for v in lists])
    cells = sorted(ccol)
    tab += byte_lines("vk_clo", [(cy * 40 + cx) & 255 for cy, cx in cells])
    tab += byte_lines("vk_chi", [(cy * 40 + cx) >> 8 for cy, cx in cells])
    tab += byte_lines("vk_ccol", [ccol[c] for c in cells])
    # päivä: solun väri sen alimman välkerivin päiväjärven mukaan (solut ilman rivejä >= VD_ROW: ei välkettä päivällä);
    # vaalea kaista on ylempänä, joten raja on yksi indeksi
    dcol = [VD_COL[far[max((y for y, x, _ in model if (y >> 3, x >> 2) == c and y >= VD_ROW), default=VD_ROW)]]
            for c in cells]
    vd_k = dcol.index(VD_COL[6]) if VD_COL[6] in dcol else len(cells)
    assert dcol == [VD_COL[14]] * vd_k + [VD_COL[6]] * (len(cells) - vd_k), dcol
    vk_k = max(1, -(-max(len(v) for v in lists) // VK_PARTS))
    inc = [f"VK_N = {n}", f"VK_M = {VK_DT * n}", f"VK_DT = {VK_DT}", f"VK_F = {VK_F}", f"VK_OF = {of}", f"VK_CELLS = {len(cells)}",
           f"VK_K3 = {3 * vk_k}", f"VD_K = {vd_k}", f"VD_C1 = {VD_COL[14]}", f"VD_C2 = {VD_COL[6]}"]
    day = [(y, x, dcol[cells.index((y >> 3, x >> 2))]) for y, x, _ in model if y >= VD_ROW]
    day += [(y, x, CRED_COL) for y, x, _ in model if y >= VD_ROW   # nimien suorakaiteissa päivänkin välke nimien väriä
            and any(r0 <= y >> 3 <= r1 and c0 <= x >> 2 < c0 + cw for r0, r1, c0, cw in crbs)]
    return inc, tab, np.array(model, np.int32).reshape(-1, 3), np.array(day, np.int32).reshape(-1, 3), lists


def rise_valke(lists: list, bmp: bytes) -> tuple[list[str], int, int]:
    """Päivän välke jo nousun lopussa (ei vasta tekijöiden aikana), koti.asm vr_gate, vr_list, vr_part: järvi on
    $D021:tä ja paikallaan,
    bittikartta nousee, joten vk_step kirjoittaa päivän välkkeen listat kuvan riville y + ppx viimeisessä asettelussa,
    kun ppx <= VR_PR. VR_PR: kaikki kohdesolut ovat merkkiriveillä VR_CR0..VR_CR0 + VR_CRN - 1, jotka ovat kuvassa
    koko leveydeltä tyhjiä (alempana koivu), joten niiden värimuisti (VD_C2) kirjoitetaan ensin kokonaan; vaalea kaista
    saa VD_C1:n vk_stepin välkesoluissa."""
    rows = [y for v in lists for y, a, b in v if y >= VD_ROW and b & (b >> 1) & 0x55]
    r0 = min(rows) >> 3
    r1 = next(r for r in range(r0, 25) if any(bmp[r * 320:(r + 1) * 320])) - 1   # ensimmäinen ei-tyhjä merkkirivi
    pr = 8 * r1 + 7 - max(rows)
    assert pr >= VR_PR_MIN, f"nousun välke vasta ppx {pr}:stä"
    return [f"VR_PR = {pr}", f"VR_CR0 = {r0}", f"VR_CRN = {r1 - r0 + 1}"], pr, r1 - r0 + 1


def sunset(far: np.ndarray) -> tuple[list[int], list[int], list[int], list[int]]:
    """sunset_stepin taulut: iltavärit tulevat ilta_stepin maalauksen mukana (ei $D021-raitoja nousun
    aikana), joten askeleet eivät kirjoita rivejä (ne kumoaisivat maalauksen)."""
    eve = [int(c) for c in far]
    return eve, eve, [17] * len(far), [17] * len(far)      # askel 17: ei koskaan (sunset_step vain s <= 16)


# Kissan jalusta (ilman sitä kissa leijuisi): puutarhan kivilaatta kissan alla samaa etualan kerrosta (sama
# parallaksi), päällä kissan varjo. Laatan etureuna on ikkunan alla koko ajan (build.py tarkistaa PED_BASE), joten
# laatan pohja ja maavarjo eivät näy kaukaisen nurmen päällä: laatta jatkuu kuvan alareunan alle kuin etualan kivi.
# Kissan kangas siirtyy CAT_UP:n verran (ylarivi - CAT_UP), joten laatan yläpinta (rivit 83-97) on tassujen (87) ja
# hännän kaaren (96) alla. Laatta on piirretty kissan alimpiin soluihin (oma väri 15, kaikki kehykset, kissan taakse),
# ja vain vasen etukulma, jota yksikään kissan solu ei kata, on omassa X-laajennetussa solussa (rivit PED_ROW..+20).
# Kaksi omaa laattasolua riviltä 82 tekisi alareunaan liikaa instansseja (cat_alloc).
CAT_UP = -1
PED_BASE = 98                 # laatan ensimmäinen piirtämätön rivi kissan kankaassa: aina ikkunan alla
BIRCH_H, BIRCH_W, BIRCH_CX = 36, 46, 21   # koivun latva: rivit, leveys ja keskikohta (MC-x) kuvan vasemmassa yläkulmassa
PED_ROW = 91                  # vasemman etukulman solu: kissan solu sarakkeessa 0 päättyy riville 90
PED_COL = 15                  # = kissan alimpien solujen oma väri
PED_X = 38                    # = kissa3.json x: solu sarakkeessa 0
PED_W = 18                    # laatan leveys puolella vaakatarkkuudella (x 38-73: sarakkeet 0-2)


def pedestal(cat: dict, fr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Laatta kissan kehyksiin (kissan solujen alueella, kissan taakse) ja vasemman etukulman solu (kehykset, rivit
    0..PED_ROW + 20) kissa3.json:n soluihin."""
    assert int(cat["x"]) == PED_X
    yy, hx = np.mgrid[82:PED_BASE, 0:PED_W]                 # puolen tarkkuuden ruudukko, x = PED_X + 2 * hx
    r, dx = yy, hx + 0.5 - PED_W / 2
    top = (dx / 8.6) ** 4 + ((r - 91.0) / 8.5) ** 4 <= 1.0  # yläpinta 3/4-kulmassa: rivit 83-97, etureuna ikkunan alla
    chk = (hx + yy) % 2 == 0
    slab = np.full(top.shape, TRANSP, np.uint8)
    slab[top] = PED_COL
    edge = top & ~(np.roll(top, 1, 0) & np.roll(top, 1, 1) & np.roll(top, -1, 1))   # tausta- ja sivureunat
    slab[edge] = 0
    slab[top & ~edge & (r <= 85) & chk] = 1                 # valo vasemmalta ylhäältä: takareuna
    slab[top & ~edge & (r >= 89) & (dx >= -6) & (dx <= 4 + (r - 89) // 2) & chk] = 0   # kissan varjo oikealle eteen
    img = np.full(fr.shape[1:], TRANSP, np.uint8)
    img[82:PED_BASE, PED_X:PED_X + 2 * PED_W] = np.repeat(slab, 2, axis=1)
    cov = np.zeros(fr.shape[1:], bool)                      # kissan solujen alue
    for cell in cat["solut"]:
        x = PED_X + 12 * cell["sarake"]
        cov[max(cell["ylarivi"], 0):cell["ylarivi"] + 21, x:x + 12] = True
    cat_fr = fr.copy()
    put = (cat_fr == TRANSP) & (img != TRANSP) & cov
    cat_fr[put] = np.broadcast_to(img, fr.shape)[put]
    rest = (img != TRANSP) & ~cov
    out = np.full((fr.shape[0], PED_ROW + 21, fr.shape[2]), TRANSP, np.uint8)
    out[:, :fr.shape[1]][:, rest] = img[rest]
    ys, xs = np.nonzero(rest)
    assert ys.min() >= PED_ROW and xs.max() < PED_X + 24, "laatan pikseleitä kissan ja kulmasolun ulkopuolella"
    cat["solut"] = list(cat["solut"]) + [{"sarake": 0, "ylarivi": PED_ROW, "oma": PED_COL, "xe": 1}]
    return cat_fr, out


def birch_top(img: np.ndarray) -> np.ndarray:
    """Koivun latva kuvan sisään: kuvan yläreuna leikkaisi muuten koivun suoraksi
    viivaksi, joka näkyisi nousun aikana. Ylimmät BIRCH_H riviä rajataan pyöreäksi latvaksi (pikselit pois, taivas
    näkyy), ja rungon kohdalle ylimmille riveille vasemman puolen lehvästöä, joten runko päättyy lehvien sisään.
    Vain poistoja ja saman rivin siirtoja: solujen värit pysyvät."""
    img = img.copy()
    rng = np.random.default_rng(7)
    xs = np.arange(BIRCH_W)
    for y in range(BIRCH_H):
        t = (BIRCH_H - y) / BIRCH_H
        hw = 25 * np.sqrt(max(0.0, 1 - t ** 2.2)) + rng.integers(-1, 2)
        row = img[y, :BIRCH_W].copy()
        if y < 12:
            row[16:25] = img[y, 4:13]
        row[np.abs(xs + 0.5 - BIRCH_CX) > hw] = TRANSP
        img[y, :BIRCH_W] = row
    return img


def load() -> dict:
    meta = json.loads((DATA / "metadata.json").read_text())
    cat = json.loads((DATA / "kissa3.json").read_text())
    k = float(cat["kerroin"])                               # parallaksi: rivejä per kuvan pikseli
    scroll = int(meta["kuva"]["vieritys"])
    img = birch_top(np.load(DATA / "bittikartta_keltainen.npy").astype(np.uint8))
    img = np.vstack([np.full((EXTRA, img.shape[1]), TRANSP, np.uint8), img[:img.shape[0] - CUT]])
    cat["ylarivi"] -= CAT_UP
    cat_fr, ped_fr = pedestal(cat, np.load(DATA / "kissa3_kehykset.npy").astype(np.uint8))
    return {"img": img,
            "far": np.load(DATA / "rasteri.npy").astype(np.uint8), "scroll": scroll + EXTRA - CUT,
            "cat": cat, "cat_frames": cat_fr, "ped_frames": ped_fr,
            "fg_t0": cat["ylarivi"] + k * (scroll + EXTRA - CUT), "fg_k": k,   # etualan ylärivi ikkunassa: fg_t0 - fg_k * p
            "shore": np.load(DATA / "ranta_spritet.npy"),
            "shore_pos": next(k for k in meta["kerrokset"] if "ranta_spritet" in k["tekniikka"])["paikat"],
            "glit": meta.get("kimallus_d021", {})}


def timing() -> dict[str, int]:
    """Aikajanan symbolit (src/gen/timing.inc), tyhjä ilman sitä."""
    inc = ROOT / "src/gen/timing.inc"
    v = {}
    for line in inc.read_text().splitlines() if inc.exists() else []:
        m = re.match(r"(TIM_\w+)\s*=\s*(\d+)", line)
        if m:
            v[m.group(1)] = int(m.group(2))
    return v


def scene_len() -> int:
    """Kodin pituus aikajanalta: TIM_SCENE_KOTI_START..seuraava kohtaus (lopun sauma: loppukuva, pääskyset,
    tummuminen)."""
    return scene_move() + HOLD0 + HOLD_END


def scene_move() -> int:
    """Nousun pituus aikajanalta (src/gen/timing.inc): kohtaus koti TIM_SCENE_KOTI_START..seuraava kohtaus,
    josta pois alun pito HOLD0 ja lopun pito HOLD_END. Ilman kotia aikajanalla MOVE."""
    v = timing()
    start = v.get("TIM_SCENE_KOTI_START")
    if start is None:
        return MOVE
    ends = [f for k, f in v.items() if k.startswith("TIM_SCENE_") and k.endswith("_START") and f > start]
    end = min(ends + [v.get("TIM_FRAMES", start + HOLD0 + MOVE + HOLD_END)])
    return max(150, end - start - HOLD0 - HOLD_END)


def motion(p_max: int, move: int = MOVE, slow: bool = True) -> list[int]:
    """Nousun nopeus kehyksittäin 1/PSUB px:n tarkkuudella (pos -= v): smoothstep-rampit (kuten Hillner) V_MIN:n päälle.
    Lyhyt nousu (RISE): ensimmäiset SLOW kehystä hitaasti (V_SLOW px/kehys), koska
    KOTI4:n tietueet (etualan spritejoukot) latautuvat vasta koti_go:n jälkeen, sitten kiihdytys."""
    def ss(x: np.ndarray) -> np.ndarray:
        x = np.clip(x, 0.0, 1.0)
        return x * x * (3 - 2 * x)
    t = np.arange(move) + 0.5                              # ei pysähdystä alussa eikä lopussa (liike joka 1 s:n
    if slow and move >= 3 * SLOW:                          # ikkunassa)
        lo, hi = 0.0, 1.0
        for _ in range(40):                                # hidas vaihe V_SLOW px/kehys
            vs = (lo + hi) / 2
            w = vs + (1 - vs) * ss((t - SLOW) / ACC) * ss((move - t) / min(DEC, move // 3))
            if vs * p_max / w.sum() > V_SLOW:
                hi = vs
            else:
                lo = vs
    else:
        w = V_MIN + (1 - V_MIN) * ss(t / min(ACC, move // 3)) * ss((move - t) / min(DEC, move // 3))
    s = np.round(np.concatenate([[0], np.cumsum(w)]) / w.sum() * p_max * PSUB).astype(int)
    v = np.diff(s)
    assert v.max() < 256 and v.min() >= 0
    return [int(x) for x in v]


CRED_FONT = DATA / "Caveat.ttf"   # SIL OFL 1.1 (OFL-Caveat.txt), Google Fonts ofl/caveat
CRED_SIZE = 40
CRED_TOP = (56, 106)              # nimien ylin rivi (ikkunan rivi, p = 0): molemmat järvellä vinosti porrastettuna:
                                  # dipe heti horisontin alla (rivit 56-86), patemathic järven alaosassa (106-138);
                                  # pääskyset välissä (BIRD_RROWS)
CRED_CX = (56, 119)               # nimien keskikohdat (MC-x): dipe vasemmalla keskellä (kuvan leveydestä noin 27-43 %),
                                  # patemathic oikealla (noin 55-95 %)
CRED_WAIT = 1                     # kehystä kameran pysähdyksen jälkeen (järvi kokonaan näkyvissä; ilta_step säilyttää
                                  # nimien %11-pikselit, koti.asm il_put)
CRED_PF = 3                       # pikseliä kehyksessä: noin 3 s molemmat (tavoite 3-4 s), valmis ennen kehystä 690
CRED_PAUSE = 30                   # tauko "dipe"n jälkeen ennen "patemathic"ia
CRED_COL = 1                      # vaalea, erottuu iltataivaasta: %11, värimuisti merkkiriveillä 0-4


def credit_names() -> list[str]:
    """Tekijät tekstit.yaml:n kohdasta tekijat."""
    sys.path.insert(0, str(ROOT / "tools"))
    import tekstit
    return [n.strip() for n in tekstit.lista("tekijat")]


def thin(img: np.ndarray) -> np.ndarray:
    """Zhang-Suen-ohennus: 0/1-kuvan luuranko."""
    img = img.copy()
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            p = np.pad(img, 1)
            n = [p[0:-2, 1:-1], p[0:-2, 2:], p[1:-1, 2:], p[2:, 2:], p[2:, 1:-1], p[2:, 0:-2], p[1:-1, 0:-2],
                 p[0:-2, 0:-2]]
            b = sum(n)
            a = sum(((n[k] == 0) & (n[(k + 1) % 8] == 1)).astype(int) for k in range(8))
            c = ((n[0] * n[2] * n[4] == 0) & (n[2] * n[4] * n[6] == 0)) if step == 0 else \
                ((n[0] * n[2] * n[6] == 0) & (n[0] * n[4] * n[6] == 0))
            m = (img == 1) & (b >= 2) & (b <= 6) & (a == 1) & c
            if m.any():
                img[m] = 0
                changed = True
    return img


def name_letters(name: str, font) -> tuple[list[set[tuple[int, int]]], int, int]:
    """Nimi Caveat-fonttina luurangoksi hires-tarkkuudella ja MC-pikseleiksi, pikselit kirjaimittain (kirjain = glyfi,
    jonka muoto pikselin kattaa; kaunokirjoituksen sidos kuuluu glyfiin, jossa se on). Lisäksi x-korkeuden ylärivi ja
    perusviiva nimen riveinä."""
    from PIL import Image, ImageDraw
    w = int(font.getlength(name)) + 40

    def ink(text: str, x: float) -> np.ndarray:
        im = Image.new("L", (w, 70), 0)
        ImageDraw.Draw(im).text((2 + x, 2), text, font=font, fill=255)
        return np.asarray(im)
    a = (ink(name, 0) > 128).astype(np.uint8)
    glyph = np.stack([ink(ch, font.getlength(name[:i])) for i, ch in enumerate(name)])
    ys, xs = np.nonzero(a)
    crop = (slice(ys.min(), ys.max() + 1), slice(xs.min() // 2 * 2, xs.max() + 2))
    a, glyph = a[crop], glyph[(slice(None),) + crop]
    lab = np.argmax(glyph, axis=0)                  # peittävin glyfi (päällekkäin: aiempi kirjain)
    sk = thin(a)
    letters: list[set] = [set() for _ in name]
    for y, x in zip(*np.nonzero(sk[:, :sk.shape[1] // 2 * 2])):
        letters[lab[y, x]].add((int(y), int(x) // 2))
    seen: set = set()                               # MC-pikseli kahdesta hires-pikselistä: aiempaan kirjaimeen
    for s in letters:
        s -= seen
        seen |= s
    xt = font.getbbox("x", anchor="ls")[1]           # x-korkeuden ylärivi suhteessa perusviivaan
    asc = font.getbbox(name, anchor="ls")[1]            # nimen ylin musteen rivi suhteessa perusviivaan
    return [s for s in letters if s], xt - asc, -asc


PEN_UP = 1.5                      # pen_order: hinta pystysuorasta askeleesta ylöspäin (varret vedetään alas)
PEN_LEFT = 0.3                    # pen_order: hinta alun etäisyydestä kirjaimen vasemmasta reunasta (pikseliä kohti)


def pen_order(pts: set[tuple[int, int]]) -> list[tuple[int, int]]:
    """Kirjaimen pikselit kynän järjestyksessä. Yhtenäiset osat suurimmasta alkaen (i:n piste viimeisenä). Osan veto
    (walk) kokeillaan jokaisesta alkupikselistä ja -suunnasta, ja valitaan halvin: hypyt (etäisyys yli vierekkäisen),
    pystyaskeleet ylöspäin (PEN_UP: varret ylhäältä alas kuten käsin) ja alku kaukana vasemmasta reunasta (PEN_LEFT)."""
    comps, rest = [], set(pts)
    while rest:
        c, todo = set(), [min(rest)]
        while todo:
            q = todo.pop()
            if q in rest:
                rest.discard(q)
                c.add(q)
                todo += [(q[0] + dy, q[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
        comps.append(c)
    if len(comps) > 1:
        return [q for c in sorted(comps, key=lambda c: (-len(c), min(x for _, x in c))) for q in pen_order(c)]
    x0 = min(x for _, x in pts)

    def cost(o: list[tuple[int, int]]) -> float:
        jump = sum(max(0.0, np.hypot(b[0] - a[0], b[1] - a[1]) - 1.5) for a, b in zip(o, o[1:]))
        up = sum(b[0] - a[0] == -1 and b[1] == a[1] for a, b in zip(o, o[1:]))
        return jump + PEN_UP * up + PEN_LEFT * (o[0][1] - x0)
    return min((walk(pts, q, d) for q in sorted(pts) for d in ((1.0, 0.0), (0.0, -1.0), (0.0, 1.0))), key=cost)


def walk(pts: set[tuple[int, int]], start: tuple[int, int], d: tuple[float, float]) -> list[tuple[int, int]]:
    """Kynän veto start:sta suuntaan d. Haarassa kynä vetää ensin lyhyemmän haaran (silmukan loppu, häntä), sitten
    pidemmän, joten kirjain valmistuu ilman paluuta kauas taaksepäin; tasoissa suorin. Porrasaskeleessa kohtisuora
    naapuri ensin, ettei viistoon oikaistu pikseli jää jälkeen. Kun jälki loppuu, jatko lähimmästä piirtämättömästä
    (päätepiste ensin)."""
    near = lambda q, s: [(q[0] + dy, q[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)   # noqa: E731
                         if (dy or dx) and (q[0] + dy, q[1] + dx) in s]

    def branches(q, s) -> list[tuple[int, int]]:
        """q:n piirtämättömät naapurit haaroittain (toisiinsa koskevat samaa haaraa), haaran alku kohtisuora."""
        cand, out = near(q, s), []
        while cand:
            grp, todo = set(), [cand[0]]
            while todo:
                r = todo.pop()
                if r not in grp:
                    grp.add(r)
                    todo += [t for t in near(r, s) if t in cand]
            cand = [r for r in cand if r not in grp]
            out.append(min(grp, key=lambda r: (abs(r[0] - q[0]) + abs(r[1] - q[1]), r)))
        return out

    def run(q, r) -> int:
        """Haaran pituus q:sta r:n kautta seuraavaan haarautumaan tai päähän."""
        s, n = set(left) - {q}, 0
        while n < 60:
            s -= set(near(q, s)) - {r}
            s.discard(r)
            q, n = r, n + 1
            nx = branches(q, s)
            if len(nx) != 1:
                break
            r = nx[0]
        return n

    left = set(pts) - {start}
    out, cur = [start], start
    while left:
        cand = branches(cur, left)
        if cand:
            straight = lambda r: ((r[0] - cur[0]) * d[0] + (r[1] - cur[1]) * d[1]) / np.hypot(r[0] - cur[0],   # noqa
                                                                                               r[1] - cur[1])
            nxt = min(cand, key=lambda r: (run(cur, r), -straight(r))) if len(cand) > 1 else cand[0]
        else:
            nxt = min(left, key=lambda q: (np.hypot(q[0] - cur[0], q[1] - cur[1]) + 2 * (len(near(q, left)) > 1), q))
        left.discard(nxt)
        out.append(nxt)
        if len(out) >= 3 and cand:
            dy, dx = nxt[0] - out[-3][0], nxt[1] - out[-3][1]
            d = (dy / np.hypot(dy, dx), dx / np.hypot(dy, dx)) if (dy or dx) else d
        cur = nxt
    return out


def credits(shore_pos: list[dict]) -> list[tuple[int, int, int]]:
    """Tekijät käsialana järvelle kahdelle riville vinosti (CRED_CX, ylimmät rivit CRED_TOP): ensimmäinen nimi
    vasemmalle heti horisontin alle, toinen oikealle järven alaosaan. Piirto kirjain kerrallaan vasemmalta oikealle, kirjaimen
    sisällä kynän järjestyksessä (pen_order). Palauttaa (rivi, MC-x, kirjain) piirtojärjestyksessä (kirjain < 0:
    ensimmäinen nimi, >= 0: toinen)."""
    from PIL import ImageFont
    font = ImageFont.truetype(str(CRED_FONT), CRED_SIZE)
    names = [name_letters(n, font)[0] for n in credit_names()]
    out: list[tuple[int, int, int]] = []
    k = -len(names[0])
    for letters, top, cx in zip(names, CRED_TOP, CRED_CX):
        pts = set().union(*letters)
        oy = top - min(y for y, _ in pts)
        ox = cx - (min(x for _, x in pts) + max(x for _, x in pts)) // 2
        for s in letters:
            out += [(oy + y, ox + x, k) for y, x in pen_order(s)]
            k += 1
    assert all(HORIZ + 8 <= y < WIN and 0 <= x < 160 for y, x, _ in out), "nimi järven ulkopuolella"
    rows = [(min(y for y, _, k in out if (k < 0) == f), max(y for y, _, k in out if (k < 0) == f)) for f in (True, False)]
    h = max(len(a) for a in BIRD_ART)
    for r in BIRD_RROWS:                            # lokit (r + min(dy) .. r + max(dy) + h - 1) nimien välissä
        assert all(r + max(BIRD_DY) + h - 1 < a or r + min(BIRD_DY) > b for a, b in rows), f"lokki rivillä {r} nimen päällä"
    for sp in shore_pos:                            # Liessaari näkyy bittikartan %01:n läpi: ei saaren kohdalle
        assert not any(sp["y"] <= y < sp["y"] + 21 and sp["x"] <= x < sp["x"] + 24 for y, x, _ in out), "tekijät saaren päällä"
    return out


def cred_steps(cred: list[tuple[int, int, int]]) -> list[int]:
    """Tekijöiden pikselit koti.asm cred_stepille kynän askelina: tavu (dy + 8) << 4 | (dx + 8) edellisestä pikselistä
    (-8..7), muuten (ensimmäinen ja vetojen väliset hypyt) $88, rivi, MC-x. Kaksi tavua pikseliltä ei mahtuisi
    KOTI4:ään (isot nimet, 401 pikseliä)."""
    out: list[int] = []
    prev = None
    for y, x, _ in cred:
        if prev is not None:
            dy, dx = y - prev[0], x - prev[1]
            if -8 <= dy <= 7 and -8 <= dx <= 7 and (dy, dx) != (0, 0):
                out.append((dy + 8) << 4 | (dx + 8))
                prev = (y, x)
                continue
        out += [0x88, y, x]
        prev = (y, x)
    return out


def layout_bases(p_max: int) -> list[int]:
    """Asettelujen alkurivit nousevasti 0, 7, 14, ... (CMAX + 1 riviä välein), kunnes ylin kattaa p_max:n. Kamera
    nousee (p pienenee): vaihto edelliseen, kun p < 8 * kanta, ja uusi plyt = 8 * 7 - 1 = 55 (c = 6), joten
    vaihtokehyksessä kirjoitetaan vain väririvit 6..24 (koti.asm col_frame)."""
    bases = [0]
    while 8 * bases[-1] + 8 * CMAX + 7 < p_max:
        bases.append(bases[-1] + CMAX + 1)
    assert 8 * bases[-1] <= p_max
    return bases


def byte_lines(label: str, data, per: int = 32) -> list[str]:
    out = [label] if label else []
    data = [int(b) & 0xFF for b in data]
    for i in range(0, len(data), per):
        out.append("        .byte " + ",".join(f"${b:02x}" for b in data[i:i + per]))
    return out


def mc_block(roles: np.ndarray) -> bytes:
    """21 x 12 roolikuva (0..3) -> 64 tavua."""
    out = bytearray(64)
    for y in range(21):
        for x in range(12):
            out[y * 3 + x // 4] |= int(roles[y, x]) << (6 - 2 * (x % 4))
    return bytes(out)


def unpack(b: bytes) -> np.ndarray:
    return np.array([[(b[y * 3 + x // 4] >> (6 - 2 * (x % 4))) & 3 for x in range(12)] for y in range(21)], np.uint8)


def cat_anim(cat: dict) -> tuple[list[int], list[int]]:
    """Kissan tilat kehyksittäin: pää 256 kehystä (HEAD_SEQ, sitten perus), häntä 64 kehyksen kierto. Kestot
    kissa3.json:n rytmistä."""
    ry = cat["rytmi"]
    head = [0] * 256
    for f0, name in HEAD_SEQ:
        f = f0
        for st, n in zip(ry[name]["jarjestys"], ry[name]["kesto"]):
            head[f:f + n] = [HEAD_STATES.index(st)] * n
            f += n
    tail = []
    for st, n in zip(ry["hanta"]["jarjestys"], ry["hanta"]["kesto"]):
        tail += [TAIL_STATES.index(st)] * n
    assert len(head) == 256 and len(tail) == 64, len(tail)
    return head, tail


def cat_sprites(d: dict) -> tuple[list[bytes], list[dict], int]:
    """Kissa 3: kissa3.json:n solut (sarake, ylärivi, oma väri) MC-spriteinä (12 x 21), 0 = $D025, 1 = $D026, muu =
    solun oma väri. Jokaisella instanssilla 4 muunnelmaa tilan mukaan (an: 0 pää, 1 ei, 2 häntä; kehykset, joissa
    solu muuttuu). Palauttaa lohkot (perus ensin), instanssit rivijärjestyksessä ja peruslohkojen määrän."""
    cat, fr = d["cat"], d["cat_frames"]
    x0 = int(cat["x"])
    names = [k["nimi"] for k in cat["kehykset"]]
    blocks: list[bytes] = []
    later: list[bytes] = []

    def blk(b: bytes | None, base: bool) -> int | None:
        if b is None:                                       # solu tyhjä tässä kehyksessä: ei instanssia
            return None
        if b not in blocks + later:
            (blocks if base else later).append(b)
        return (blocks + later).index(b) if b in blocks else -1 - later.index(b)

    def mc(img: np.ndarray, r0: int, c: int, own: int, xe: int = 0) -> bytes | None:
        px = np.full((21, 12), TRANSP, np.uint8)
        lo = max(r0, 0)
        px[lo - r0:min(21, img.shape[0] - r0)] = img[lo:r0 + 21, x0 + 12 * c:x0 + 12 * c + 12 + 12 * xe:1 + xe]
        roles = np.zeros((21, 12), np.uint8)
        roles[px == CAT_COL[0]] = 1
        roles[px == CAT_COL[1]] = 3
        rest = (px != TRANSP) & (px != CAT_COL[0]) & (px != CAT_COL[1])
        assert (px[rest] == own).all(), f"solussa ({c}, {r0}) muu kuin oma väri {own}"
        roles[rest] = 2
        return mc_block(roles) if roles.any() else None
    hf = [names.index(n) for n in HEAD_STATES]
    tf = [names.index(n) for n in TAIL_STATES]
    changed = {}                                            # solu -> pää tai häntä (kehykset, joissa se muuttuu)
    for k in cat["kehykset"]:
        for cell in k["solut"]:
            changed[(cell["sarake"], cell["ylarivi"])] = "head" if k["nimi"] in HEAD_STATES else "tail"
    state_frame = {"head": hf, "tail": tf + [tf[0]], "none": [0] * 4}
    inst = []
    for cell in sorted(cat["solut"], key=lambda c: (c["ylarivi"], c["sarake"])):
        c, r, own = cell["sarake"], cell["ylarivi"], cell["oma"]
        an = changed.get((c, r), "none")
        xe = cell.get("xe", 0)                              # jalustan solut omasta kuvastaan
        src = d["ped_frames"] if xe else fr
        inst.append({"row": r, "x": x0 + 12 * c, "an": an, "hires": 0, "xe": xe, "col": own,
                     "var": [blk(mc(src[f], r, c, own, xe), f == 0) for f in state_frame[an]]})
    for f in range(len(fr)):                                # muunnelmat muuttavat vain ilmoitettuja soluja
        for e in inst:
            if e["an"] == "none":
                src = d["ped_frames"] if e["xe"] else fr
                c = (e["x"] - x0) // 12
                assert mc(src[f], e["row"], c, e["col"], e["xe"]) == mc(src[0], e["row"], c, e["col"], e["xe"]), \
                    (f, e["row"], e["x"])
    n = len(blocks)
    for e in inst:                                          # myöhemmät lohkot perään
        e["var"] = [v if v is None or v >= 0 else n - 1 - v for v in e["var"]]
    return blocks + later, inst, n


def cat_alloc(finst: list[dict], fg_lines: list[int], n_txt: int) -> None:
    """koti.asm cat_set: kissan instanssi i spritellä i & 3, pääskyset spriteillä 5-7 (alaversio) ja alareunan
    instanssit (alku >= SPR_BOT - 19: alku SPR_BOT - 20, päättyvät riville SPR_BOT) ensimmäiselle vapaalle spritelle
    järjestyksessä CT_HW. Tarkistaa kaikilla kissan riveillä (fg_lines: rivin 0 näyttörivi), pääskysten aalloilla ja
    korvan kärjen tiloilla, että sprite on vapaa (edellinen päättynyt vähintään 4 riviä ennen), kierron tapahtumat ovat
    käsittelyjärjestyksessä, kaikki tapahtumat ennen alareunan IRQ:ta ja jalusta (X-laajennus) ei ole kierron
    alkuinstanssi."""
    rows = [e["row"] for e in finst]
    assert rows == sorted(rows) and all(None not in e["var"] for e in finst[4:]), "kissa: kierto"
    assert TXT_HW + n_txt <= MAX_HW
    skips = [False, True] if None in finst[0]["var"] else [False]
    for fgl in sorted(set(fg_lines)):
        for skip0 in skips:
            for w in itertools.product(range(BIRD_WAVE[0], BIRD_WAVE[1] + 1), repeat=len(BIRDS)):
                end, keys, tail = [None] * MAX_HW, [], []
                for b, (row, _, _, _) in enumerate(BIRDS):
                    end[5 + b] = T_LINE + row - BIRD_LOW + w[b] + 20
                for i, r in enumerate(rows):
                    s = fgl + r
                    if s > SPR_BOT or (skip0 and i == 0):
                        continue
                    if s >= SPR_BOT - 19:
                        h = next((h for h in CT_HW if (end[h] or 0) + 4 <= SPR_BOT - 20), None)
                        assert h is not None, f"kissa: alareunan instanssille ei spriteä (fgl {fgl}, aallot {w})"
                        if end[h] is not None:
                            tail.append(end[h] + 1)
                        end[h] = SPR_BOT
                        continue
                    h = i & 3
                    if end[h] is None:
                        assert not finst[i]["xe"], f"kissa: jalusta kierron alkuinstanssina (fgl {fgl})"
                    else:
                        assert end[h] + 4 <= s, f"kissa: kierto ({fgl}, {i})"
                        keys.append(end[h] + 1)
                    end[h] = s + 20
                assert keys == sorted(keys), f"kissa: kierron tapahtumat eivät järjestyksessä (fgl {fgl})"
                assert all(k < LINE_BOT - 1 for k in keys + tail), f"kissa: tapahtuma alareunan IRQ:n kohdalla (fgl {fgl})"


def text_sprites() -> tuple[list[bytes], list[tuple]]:
    """Tekstit hires-spriteinä (24 px leveitä paloja): lohkot ja (X, väri) per sprite."""
    from c64fmt import glyph_bytes
    blocks, inst = [], []
    for text, x0, col in TEXTS:
        rows = [bytearray() for _ in range(8)]
        for ch in text:
            for y, b in enumerate(glyph_bytes(ch)):
                rows[y].append(b)
        w = len(text)
        for part in range(0, w, 3):
            blk = bytearray(64)
            for y in range(8):
                chunk = rows[y][part:part + 3]
                blk[y * 3:y * 3 + len(chunk)] = chunk
            blocks.append(bytes(blk))
            inst.append((x0 + 8 * part, col))
    assert len(inst) <= 4, inst
    return blocks, inst


def statics(d: dict) -> tuple[list[bytes], list[dict]]:
    """Kiinteät spritet: vastaranta (bittikartan takana, X-laajennettu, leikataan taivasvyöhykkeeseen) ja pääskyset
    (edessä, X ja rivi liikkuvat, siipiasento vaihtuu). Instanssit rivijärjestyksessä (pääskysen aalto +-2 riviä)."""
    blocks, out = [], []
    for s, pos in enumerate(d["shore_pos"]):
        out.append({"row": int(pos["y"]), "x": int(pos["x"]), "blk": len(blocks), "col": int(pos["oma"]), "bird": 0})
        blocks.append(mc_block(d["shore"][s]))
    b0 = len(blocks)
    for a in BIRD_ART:                                       # musta = oma väri 0, harmaa -> $D025 (11)
        roles = np.zeros((21, 12), np.uint8)
        for y, line in enumerate(a):
            for x, ch in enumerate(line):
                roles[y, x] = {"#": 2, "+": 1}.get(ch, 0)
        blocks.append(mc_block(roles))
    for i, (row, x, dx, ph) in enumerate(BIRDS):
        out.append({"row": row, "x": 0, "blk": b0, "col": 0, "bird": i + 1})
    out.sort(key=lambda e: (e["row"], e["x"]))
    rows = [e["row"] for e in out if e["bird"]]
    assert all(b - a >= 5 for a, b in zip(rows, rows[1:])), "pääskysten rivit vähintään 5 välein"
    return blocks, out


def front_mask(img: np.ndarray, roles: list[np.ndarray], st: list[dict], p_max: int, sky_t: int) -> np.ndarray:
    """Kuvan pikselit, joiden takana kiinteän spriten pikseli näkyisi eri värisenä jossain nousun kohdassa p (saari
    leikataan taivasvyöhykkeeseen, joten vain rivit < sky_t). Saman värinen sprite %01-pikselin takana ei näy."""
    scr = np.zeros((WIN, 160), np.uint16)                   # spritejen värit ruudun pikseleittäin (bitit)
    for e in st:
        r = np.repeat(roles[e["blk"]], 2, axis=1)            # X-laajennettu: data-px = 2 MC-px
        cols = np.choose(r, [0, 1 << SPR_COL[0], 1 << e["col"], 1 << SPR_COL[1]]).astype(np.uint16)
        x0, x1 = max(e["x"], 0), min(e["x"] + 24, 160)
        scr[e["row"]:e["row"] + 21, x0:x1] |= cols[:, x0 - e["x"]:x1 - e["x"]]
    m = np.zeros(img.shape, np.uint16)
    for p in range(p_max + 1):
        m[p:p + WIN] |= scr
    own = np.left_shift(np.uint16(1), np.where(img == TRANSP, 0, img).astype(np.uint16))
    out = (m & ~own) != 0
    out[sky_t:] = False
    return out


def bmp_roles(bmp: bytes, h: int) -> np.ndarray:
    """Bittikartan roolit (0-3) MC-pikseleittäin."""
    b = np.frombuffer(bmp, np.uint8).reshape(h // 8, 40, 8).transpose(0, 2, 1).reshape(h, 40)
    return np.stack([(b >> (6 - 2 * i)) & 3 for i in range(4)], axis=2).reshape(h, 160)


def encode_hidden(img: np.ndarray, enc_t: int, front: np.ndarray) -> tuple[bytes, bytes, bytes, np.ndarray, int, int]:
    """encode_layers niin, ettei takana oleva sprite näy %01-pikseleiden läpi (kuten Hillnerin kirkko,
    src/proto/hillner/build.py encode): kolmen värin solussa, jossa sprite näkyisi, %01:ksi valitaan väri, jonka
    front-pikseleiden vaihto solun lähimpään muuhun väriin muuttaa kuvaa vähiten (Lab), ja ne pikselit vaihdetaan.
    Palauttaa encode_layersin arvot ja vaihdettujen pikseleiden määrän."""
    img = img.copy()
    h = img.shape[0]
    changed = 0
    for _ in range(4):
        bmp, scr, col, shown, fixes = encode_layers(img, enc_t, front)
        leak = (bmp_roles(bmp, h) == 1) & front
        if not leak.any():
            return bmp, scr, col, shown, fixes, changed
        for cy, cx in sorted({(y // 8, x // 4) for y, x in zip(*np.nonzero(leak))}):
            c = cy * 40 + cx
            cols = [scr[c] >> 4, scr[c] & 15, col[c]]
            sl = (slice(cy * 8, cy * 8 + 8), slice(cx * 4, cx * 4 + 4))
            cell, fm = shown[sl], front[sl]
            best = None
            for v in cols:
                hit = fm & (cell == v)
                to = min((u for u in cols if u != v), key=lambda u: _lab_dist(v, u))
                cost = int(hit.sum()) * _lab_dist(v, to)
                if best is None or cost < best[0]:
                    best = (cost, hit, to)
            img[sl][best[1]] = best[2]
            changed += int(best[1].sum())
    raise AssertionError("vuoto jäi")


def loppukuva(out: Path, eve: list[int], ring2: list[int], gl_add: list[int], g0: int, g1: int, d: dict, st: list[dict],
              sblocks: list[bytes], cred: list, gph: int, ilta: np.ndarray | None = None) -> None:
    """Kodin viimeinen kuva lopun saumaan (runko): build/koti/demo/loppukuva.npy (200 x 320 C64-värejä,
    rasteririvit 51-250, hires-px) ja loppukuva.json. Kamera p = 0, aurinko laskenut, bittikartta tyhjä tekijöitä
    lukuun ottamatta (käsiala valkoisena järvellä): ikkunan rivit ovat kaukaisen kerroksen iltavärejä ($D021 riveittäin:
    taivassilmukka riville SKY_LAST, sen alla tapahtumat riville D21EV_MAX, alarivit jatkavat sen väriä),
    kimallusrivit gl_ring2:n vaiheessa gph, Liessaari tummana. Ei heijastusta (aurinko laskenut) eikä 1959:ää
    (pois talon mukana). Tarkistaa, että 4 x 8 -solussa on enintään 3 väriä mustan lisäksi (lopun bittikartta)."""
    img = np.zeros((200, 320), np.uint8)
    for w in range(WIN):
        c = eve[min(w, D21EV_MAX)]
        if g0 <= w < g1:
            c = ring2[((gph + gl_add[w - g0]) & 255) // GL_STEP]
        img[T_LINE + w - 51] = c
    if ilta is not None:                                    # maskin dither (ilta_tables)
        for w in range(WIN):
            m = ilta[w] != TRANSP
            img[T_LINE + w - 51][np.repeat(m, 2)] = np.repeat(ilta[w], 2)[np.repeat(m, 2)]
    for e in st:
        if e["bird"]:
            continue
        roles = unpack(sblocks[e["blk"]])
        cols = {1: EVE_D025, 2: e["col"], 3: EVE_D026}
        for y in range(21):
            for x in range(12):
                r = roles[y, x]
                if r:
                    xx = 2 * e["x"] + 4 * x
                    img[T_LINE + e["row"] + y - 51, max(0, xx):xx + 4] = cols[r]
    np.save(out / "loppukuva_tausta.npy", img)          # ilman tekijöitä: lopun käsiala liukenee tähän (loppu.py kasiala)
    for y, x, _ in cred:
        img[T_LINE + y - 51, 2 * x:2 * x + 2] = CRED_COL
    bad = []
    for cy in range(25):
        for cx in range(40):
            cols = set(img[8 * cy:8 * cy + 8, 8 * cx:8 * cx + 8].ravel().tolist()) - {0}
            if len(cols) > 3:
                bad.append((cy, cx, sorted(cols)))
    np.save(out / "loppukuva.npy", img)
    (out / "loppukuva.json").write_text(json.dumps({
        "kehys": scene_len() - 1, "rasteririvit": [51, 250], "ikkuna_rasteririvit": [T_LINE, T_LINE + WIN - 1],
        "aurinko": None, "liessaari": [{"x_hires": 2 * e["x"], "rasteririvi": T_LINE + e["row"]} for e in st
                                       if not e["bird"]],
        "kimallus": {"ikkunan_rivit": [g0, g1 - 1], "ring2": ring2, "gl_add": gl_add, "gph": gph, "GL_STEP": GL_STEP,
                     "kaava": "väri = ring2[((gph + gl_add[rivi - ensimmäinen]) & 255) // GL_STEP], gph + 1 kehyksessä"},
        "yli_3_varin_solut": [{"merkkirivi": cy, "sarake": cx, "varit": c} for cy, cx, c in bad],
        "huom": "kodin viimeinen kuva (p = 0): bittikartassa vain tekijöiden käsiala (musta), kaukaisen kerroksen "
                "$D021 riveittäin iltaväreissä, Liessaari tummana, letterbox musta (1959 poistuu talon mukana); "
                "värimuistia ($d800) käsialan solut eivät tarvitse (%01 = ruutumuistin musta)"}, ensure_ascii=False, indent=1))
    if bad:
        print(f"loppukuva: {len(bad)} solua yli 3 värin (mustan lisäksi): {bad[:4]}")


def demo_top(rows: list[bytes], sprs: list[str], xsprs: list[str], ysprs: list[str]) -> list[str]:
    """Demon ylin asettelu valmiina pankki 3 -muodossa, ladataan purun aikana: värit l2col koodin perään (KOTI1,
    $1a00-$3fff; koti_go kirjoittaa ne $d800:aan), ruutu $c000 ja spritelohkot $cc00 (KOTI2), kissan lisälohkot ja
    tilataulut yläreunan leikkauspuskureissa $c400 ja $c800 (KOTI2, vain kissan aikana: koti_quiet kirjoittaa
    pitomoottorin päälle), bittikartta $e000 ja sen perään koti_show (KOTI3). Kodin pyöriessä ladattavat tietueet
    alkavat $4800:sta (KOTI4)."""
    assert len(rows) == BANK_ROWS
    spr_at = 0xC000 + SPR_OFS + 64 * N_CLIP
    block = lambda lo, hi: byte_lines("", b"".join(r[lo:hi] for r in rows))
    return (["l2col"] + block(360, 400) +
            ["koti1_end", '        .cerror * > $4000, "KOTI1 yli $4000:n: ", format("$%04x", *)',
             "        * = $c000", "l2scr"] + block(320, 360) +
            [f"        * = ${0xC000 + SPR_OFS:04x}"] + xsprs +
            [f"        * = ${0xC000 + SPR_OFS + 64 * 16:04x}"] + ysprs +
            [f'        .cerror * > ${0xC000 + SPR_OFS + 64 * 24:04x}, "yläreunan puskurit (joukko 1) täynnä"'] +
            [f"        * = ${spr_at:04x}"] + sprs +
            ['        .cerror * > $d000, "spritelohkot yli $d000:n"', "koti2_end",
             "        * = $e000", "l2bmp"] + block(0, 320) +
            ["        #koti_show_code", '        .cerror * > $fffa, "KOTI3 yli $fffa:n"', "koti3_end", "        * = $4800"])


def colfast() -> list[str]:
    """Värimuistin kopio COLSTAGE -> $d800 sarakkeittain (X = 39..0), rivit auki kirjoitettuna (9 sykliä per tavu).
    Rivin r lohko cf_r{r} (6 tavua); koti.asm kirjoittaa lopetusrivin alkuun jmp cf_end:n ja hyppää aloitusriville."""
    out = ["cf_loop"]
    for r in range(BANK_ROWS):
        out += [f"cf_r{r}", f"        lda COLSTAGE + {40 * r},x", f"        sta $d800 + {40 * r},x"]
    out += [f"cf_r{BANK_ROWS}", "cf_end  dex", "        bmi +", "cf_jmp  jmp cf_loop", "+       rts",
            "cf_lo   .byte " + ",".join(f"<cf_r{r}" for r in range(BANK_ROWS + 1)),
            "cf_hi   .byte " + ",".join(f">cf_r{r}" for r in range(BANK_ROWS + 1))]
    return out


def music(out: Path) -> list[str]:
    r = subprocess.run([sys.executable, "-I", str(ROOT / "tools/music/music.py"), "build", str(out), "--addr",
                        f"{MUSIC_ADDR:04x}", "--zp", "c0", "--buf", "1700"], capture_output=True, text=True)
    if r.returncode:
        print(r.stdout + r.stderr)
        (out / "music.inc").write_text("HAVE_MUSIC = 0\n")
    return [f"MSTART = {MSTART}"]


def main(out: Path, integrated: bool = False) -> None:
    out.mkdir(parents=True, exist_ok=True)
    d = load()
    img, far = d["img"], d["far"]
    far[SKY_LAST + 1:] = far[SKY_LAST]                      # päiväjärvi silmukan viimeisen rivin värinen:
    # rasteri.npy:n mustat aaltorivit olisivat tiheitä $D021-tapahtumia (myöhästyvät, kovat raidat)
    assert img.shape[1] == 160 and img.shape[0] % 8 == 0 and img.shape[0] >= WIN, img.shape
    rows255 = np.nonzero((img == TRANSP).any(axis=1))[0]
    sky_t = int(rows255.max()) + 1
    nrows = img.shape[0] // 8
    p_max = nrows * 8 - WIN
    assert p_max == d["scroll"], (p_max, d["scroll"])
    bases = layout_bases(p_max)

    fblocks, finst, _ = cat_sprites(d)
    sblocks, st = statics(d)
    sroles = [unpack(b) for b in sblocks]
    # Kiinteät spritet ovat bittikartan takana: bittikartan %00 ja %01 näyttävät ne. Rivit, jotka voivat olla niiden
    # edessä, koodataan taivasrivien tapaan (musta on oma värinsä), ja %01:ksi valitaan solun väri, jolla on
    # vähiten spritejen edessä olevia pikseleitä. Takana olevat spritet leikataan lisäksi taivasvyöhykkeeseen.
    enc_t = sky_t                                           # takana olevat leikataan taivasvyöhykkeeseen (koti.asm)
    front = front_mask(img, sroles, [e for e in st if not e["bird"]], p_max, sky_t)
    bmp, scr, col, shown, fixes, hidden = encode_hidden(img, min(enc_t, img.shape[0]), front)
    np.save(out / "shown.npy", shown)
    np.save(out / "far.npy", far)
    # $D021: taivassilmukka (crunch.asm) ikkunan riveille 0..SKY_T - p - 1 taulusta far_tab, kimallusriveillä g0..g1
    # väri kiertää väriliukujonoa; alempana 0 (siellä vain mustat %00-pikselit)
    g0, g1 = d["glit"].get("rivit", [0, -1])
    g1 += 1
    ring = d["glit"].get("kierto", [0] * 32)
    assert len(ring) * GL_STEP == 256, "kimalluksen vaihe kiertää 8 bittiä"
    # rivi x: väri gl_ring[((gph + gl_add[x]) & 255) / GL_STEP], gl_add = rivin vaihe (x * 11 askelta) ja porrastus
    # + GL_LEN - scene_len(): viimeisen kehyksen kimallus (lopun kuva) on sama kuin GL_LEN-pituisessa kodissa
    gl_add = [(GL_STEP * x * 11 + (i * 3) % GL_STEP + GL_LEN - scene_len()) & 255 for i, x in enumerate(range(g0, g1))]
    # spritelohkot: leikkauspuskurit, sitten kiinteät, etuala ja tekstit; molempiin pankkeihin samaan kohtaan
    tblocks, tinst = text_sprites()
    # pääskysten alaversioita (kissan aikana, BIRD_LOW) ei tarvita: lokit ovat poissa (bd_gone) paluuseen asti, ja kissa
    # on poissa ennen sitä (tarkistus alla), joten BIRD_LPTR0 = BIRD_PTR0 (lohkot lokkien viidelle asennolle)
    lblocks = []
    move = min(scene_move(), MOVE_END)
    mv = motion(p_max, move)                                # yksi nousu: ei hidastusta järven jälkeen

    def quant(mv: list[int]) -> tuple[list[int], int]:
        """MDIV kehyksen välein vaihtuva nopeus (taulu 1/MDIV: koko kohtauksen käyrä ei mahdu KOTI1:een); summa ei
        ylitä nousua (pos ei mene alle 0)."""
        mv4, done = [], 0
        for i in range(0, len(mv), MDIV):
            n = min(MDIV, len(mv) - i)
            v = (sum(mv[:i + n]) - done) // n
            mv4.append(v)
            done += v * n
        return mv4, done
    # kamera perillä heti, kun bittikartta on paikassa 0 (lf_place pyöristää): jarrutuksen loppu alle puolen pikselin
    # ei näy, joten tekijät ja päivän välke alkavat siitä (ei seisovaa sekuntia ennen nimiä)
    move = next(f for f in range(1, len(mv) + 1) if px(PSUB * p_max - quant(mv[:f])[1]) == 0)
    mv = mv[:move]
    mv4, done = quant(mv)
    assert done <= PSUB * p_max and PSUB * p_max - done < PSUB and max(mv4) < 256
    mv = [mv4[i // MDIV] for i in range(move)]
    fg_t0 = int(round(d["fg_t0"]))
    fg_k16 = int(round(d["fg_k"] * 16))                     # etualan siirto: (fg_k16 * pos) >> 12 riviä (pos 1/256 px)
    # lohkot: N_MAIN leikkauspuskurien jälkeen (spr_src), loput yläreunan puskureihin (spr_xsrc, spr_ysrc)
    pb = [fblocks[e["var"][0]] for e in finst if e["xe"]]   # jalusta
    assert len(pb) == 1
    t0 = len(sblocks) + len(pb)                             # tekstien ensimmäinen lohko
    nmf = N_MAIN - t0 - len(tblocks)                        # kissan lohkoja päälohkoihin (perus ensin)
    fb = [b for b in fblocks if b not in pb]
    blocks = sblocks + pb + tblocks + fb[:nmf] + lblocks + fb[nmf:]
    fidx = lambda v: blocks.index(fblocks[v])                                            # noqa: E731
    n_blk = N_CLIP + len(blocks)
    assert len(blocks) <= N_MAIN + N_XTRA, f"spritelohkot eivät mahdu ({len(blocks)}: {len(sblocks)}, {len(tblocks)}, {len(lblocks)}, {len(fblocks)})"
    ptr0 = SPR_OFS // 64
    xslot = lambda j: j if j < 8 else j + 8                 # yläreunan puskurit: joukko 0 (0-7), joukko 1 (16-23)  # noqa
    sptr = lambda i: ptr0 + N_CLIP + i if i < N_MAIN else ptr0 + xslot(i - N_MAIN)        # noqa: E731
    ssrc = lambda i: (f"spr_src + {64 * i}" if i < N_MAIN else f"spr_xsrc + {64 * (i - N_MAIN)}" if i < N_MAIN + 8
                      else f"spr_ysrc + {64 * (i - N_MAIN - 8)}")                        # noqa: E731
    bird_ptr0 = ptr0 + N_CLIP + next(e['blk'] for e in st if e['bird'])

    recs = [bmp[r * 320:(r + 1) * 320] + scr[r * 40:(r + 1) * 40] + col[r * 40:(r + 1) * 40] for r in range(nrows)]
    # tietueet tarvejärjestyksessä: ylimmän asettelun rivit ensin, sitten seuraavan uudet rivit jne. Muut rivit
    # alemmat asettelut kopioivat näkyvästä pankista (koti.asm cr_row). Demossa ylin asettelu on valmiina pankissa 3
    # (purun aikana ladattava kuva, demo_top), joten sen tietueita ei ole.
    groups = []                                             # (asettelu, sen uudet rivit) ylimmästä alkaen
    seen = set()
    for k in range(len(bases) - 1, -1, -1):
        rows = [r for r in range(bases[k], min(bases[k] + BANK_ROWS, nrows)) if r not in seen]
        seen |= set(rows)
        groups.append((k, [r for r in rows if any(recs[r])]))   # tyhjä rivi: osoitin 0, koti.asm nollaa
    if integrated:
        groups = groups[1:]
    have = {r for _, rows in groups for r in rows}
    rt = [min(r, nrows - 1) for r in range(bases[-1] + BANK_ROWS)]
    fg_top = [T_LINE + fg_t0 - (fg_k16 * pos >> 12) for pos in range(PSUB * p_max + 1)]
    assert min(fg_top) + min(e["row"] for e in finst) >= SPR_TOP and all(T_LINE + e["row"] - 2 >= SPR_TOP for e in st), \
        "yläreunan leikkaus tarvitaan (N_XTRA-lohkot ovat sen puskureissa)"
    shore_p = sky_t - 1 - min(e["row"] for e in st if not e["bird"])   # saari näkyy, kun p <= shore_p
    assert all(fg_top[pos] > SPR_BOT for pos in range(PSUB * shore_p + PSUB)), "saari ja kissa samassa kuvassa ($D025)"
    assert all(fg_top[pos] >= T_LINE + sky_t - px(pos) for pos in range(PSUB * min(sky_t, p_max + 1))), \
        "kissa taivasvyöhykkeellä (siellä vain spritet 0-2)"
    cat_vis = SPR_BOT - min(e["row"] for e in finst)        # koti.asm cat_set: kissa näkyy, kun fgl <= CAT_VIS
    assert min(fg_top) + PED_BASE > SPR_BOT, f"jalustan pohja ikkunassa (fgl {min(fg_top)}): leijuu nurmen päällä"
    cat_pos = [q for q in range(PSUB * p_max + 1) if fg_top[q] <= cat_vis]
    cat_alloc(finst, [fg_top[q] for q in cat_pos], len(tinst))
    cat_end = HOLD0 + next(f for f, q in enumerate(PSUB * p_max - np.cumsum([0] + mv)) if fg_top[q] > cat_vis)
    assert cat_end < BIRD_RET, "lokit kissan aikana (alaversiot puuttuvat, BIRD_LPTR0 = BIRD_PTR0)"
    assert all(sky_t - px(q) <= SKY_LAST + 1 for q in cat_pos), "kissan aikana $D021-tapahtumia (cat_set ei tee niitä)"
    assert all(px(q) >= 8 * bases[-1] for q in cat_pos), "kissan aikana asettelu vaihtuu (cat_clip kirjoittaa vain pankkiin 3)"
    head, tail = cat_anim(d["cat"])
    inc = [f"IMG_ROWS = {nrows}", f"P_MAX = {p_max}", f"LAYOUTS = {len(bases)}", f"LAY_TOP = {bases[-1]}", f"SKY_T = {sky_t}",
           f"ENC_T = {enc_t}", f"HOLD0 = {HOLD0}", f"MOVE_N = {move}", f"MDIV = {MDIV}", f"PSUB = {PSUB}", f"CODE_BASE = ${CODE_BASE:04x}",
           f"MUSIC_ADDR = ${MUSIC_ADDR:04x}", f"REC_LIMIT = ${REC_LIMIT:04x}",
           f"BSS_BASE = ${BSS_DEMO if integrated else BSS_PROTO:04x}", f"FIXES = {fixes}", f"GL0 = {g0}", f"GL1 = {g1}",
           f"FG_T0 = {fg_t0}", f"FG_K16 = {fg_k16}", f"CAT_VIS = {cat_vis}", f"N_FI = {len(finst)}", f"N_ST = {len(st)}",
           f"N_BIRD = {len(BIRDS)}", f"BIRD_PTR0 = {bird_ptr0}",
           f"N_BLK = {min(len(blocks), N_MAIN)}", f"N_XBLK = {min(8, max(0, len(blocks) - N_MAIN))}",
           f"N_YBLK = {max(0, len(blocks) - N_MAIN - 8)}", f"SPR_OFS = ${SPR_OFS:04x}",
           f"CAT_D025 = {CAT_COL[0]}", f"CAT_D026 = {CAT_COL[1]}", f"BIRD_LOW = {BIRD_LOW}", f"BIRD_LPTR0 = {bird_ptr0}",
           f"CLIP_PTR0 = {ptr0}", f"N_CLIP = {N_CLIP}", f"MAX_HW = {MAX_HW}", f"N_TXT = {len(tinst)}",
           f"TXT_LINE = {TEXT_LINE}",
           f"TXT_010 = {sum(1 << (TXT_HW + i) for i, (x, _) in enumerate(tinst) if x >= 256)}", f"SPR_D025 = {SPR_COL[0]}", f"SPR_D026 = {SPR_COL[1]}"]
    inc += [f"MSTART = {MSTART}"] if integrated else music(out)
    if integrated:
        (out / "music.inc").write_text("HAVE_MUSIC = 0\n")
    tabs = ["row_lo  .byte " + ",".join(f"<rec_r{r}" if r in have else "0" for r in rt),
            "row_hi  .byte " + ",".join(f">rec_r{r}" if r in have else "0" for r in rt)]
    tabs += byte_lines("r320_lo", [(320 * j) & 0xFF for j in range(BANK_ROWS)])
    tabs += byte_lines("r320_hi", [(320 * j) >> 8 for j in range(BANK_ROWS)])
    tabs += byte_lines("motion_v", mv4)
    tabs += byte_lines("lay_row", bases) + byte_lines("lay_px_lo", [(8 * b) & 0xFF for b in bases])
    tabs += byte_lines("lay_px_hi", [(8 * b) >> 8 for b in bases])
    tabs += byte_lines("far_tab", far)
    # auringonlasku (koti.asm sunset_step): rivin väri päivä -> c1 askeleesta t1 -> c2 askeleesta t2
    sc1, sc2, st1, st2 = sunset(far)
    assert sc1 == sc2 and st1 == st2                        # yksi vaihto riviä kohden
    step = [max(t, 1) for t in st2]                         # askel s = 1..16, jossa rivi vaihtuu illaksi: koti.asm
    il = ilta_tables()                                      # lopun ilta ditherinä (koti.asm ilta_step)
    sc_end = il["d021"] + [il["d021"][-1]] * (len(sc2) - SKY_MAX - 1)   # lopun kuva: silmukan jälkeen sen väri
    iltab = [line for k, u in enumerate(il["uniq"]) for line in byte_lines(f"il_m{k}", u)]
    iltab += ["il_mlo  .byte " + ",".join(f"<il_m{k}" for _, k in il["list"])]
    iltab += ["il_mhi  .byte " + ",".join(f">il_m{k}" for _, k in il["list"])]
    iltab += byte_lines("il_row", [y for y, _ in il["list"]]) + byte_lines("il_d021", il["d021"])
    iltab += byte_lines("il_scr", il["scr"])
    cred = credits(d["shore_pos"])                   # tekijät: pankin 3 bittikarttaan, MC %11 (cred_step)
    crbs = []                                        # nimien merkkisolut järvellä: värimuisti suorakaiteina
    for f in (True, False):
        nm = [(y, x) for y, x, k in cred if (k < 0) == f]
        crbs.append((min(y for y, _ in nm) >> 3, max(y for y, _ in nm) >> 3, min(x for _, x in nm) >> 2,
                     (max(x for _, x in nm) >> 2) - (min(x for _, x in nm) >> 2) + 1))
    vk_inc, vk_tab, vk_model, vd_model, vk_lists = valke(il, scene_len(), bmp, far, cred, crbs)   # välke KOTI5:een
    inc += [f"CR{n}_{k} = {v}" for n, crb in zip("AB", crbs) for k, v in zip(("R0", "R1", "C0", "W"), crb)]
    inc += vk_inc
    iltab += vk_tab
    ild = il["d021"]                                # illan $D021-rajat taivassilmukan alla (_d21ev ilta_stepin aikana
    evr = [r for r in range(SKY_LAST + 1, D21EV_MAX + 1) if ild[r] != ild[r - 1]]   # ilman rivien läpikäyntiä)
    iltab += byte_lines("il_evr", evr) + byte_lines("il_evl", [72 + r - 3 for r in evr])
    iltab += byte_lines("il_evc", [ild[r] for r in evr])
    inc += [f"IL_EVN = {len(evr)}", f"DAY_LO = {int(far[SKY_LAST + 1])}"]
    assert all(int(c) == int(far[SKY_LAST + 1]) for c in far[SKY_LAST + 1:])   # päiväjärvi yhtä väriä (DAY_LO)
    inc += [f"IL_N = {len(il['list'])}", f"IL_SCR_N = {len(il['scr'])}"]
    tabs += byte_lines("ss_c", sc2) + byte_lines("ss_rows", sorted(range(len(step)), key=step.__getitem__))
    tabs += byte_lines("ss_beg", [sum(t <= k for t in step) for k in range(17)])   # käy vain ne (koko silmukka
    # 144 riviä askeleen kehyksessä venyttäisi logic_framen seuraavaan kehykseen ja katkaisisi ketjun)
    ring2 = [{14: 8, 15: 7, 1: 7, 3: 10}.get(c, c) for c in ring]
    tabs += byte_lines("gl_ring2", ring2)
    pos = PSUB * p_max - np.concatenate([[0], np.cumsum(mv)])
    gi = next(i for i, (y, _) in enumerate(il["list"]) if (y & 127) >= g0)   # maalaus kimallusriveillä (2 kehystä/rivi)
    sunset_f = ILTA_F + len(il["scr"]) + 2 * gi + SUNSET_F
    # päivän välke jatkuu, kunnes maalaus lähestyy järveä: tyhjennys (VK_PARTS kehystä) valmis ennen riviä VD_ROW
    vd_end = ILTA_F + len(il["scr"]) + 2 * next(i for i, (y, _) in enumerate(il["list"]) if (y & 127) >= VD_ROW) - VK_PARTS - 2
    assert MOVE_END < vd_end and ILTA_F <= vd_end
    assert ILTA_F + len(il["scr"]) + 2 * len(il["list"]) + 2 <= VK_F, "illan välke ennen kuin ilta on maalattu"
    assert 40 % DK_B == 0
    dusk_f = scene_len() + DUSK_END - (DUSK_N - 1) * DUSK_STEP - (len(il["scr"]) + 1) * 40 // DK_B
    assert VK_F + VK_PARTS + 8 <= dusk_f and (len(il["scr"]) + 1) * 40 // DK_B < DUSK_STEP, "tummuminen ennen välkettä"
    inc += [f"VD_END = {vd_end}"]
    # päivän välkkeen värimuisti jo ennen pysähdystä (VKC_F), kun viimeinen asettelu on näkyvissä: välke alkaa heti
    # pysähdyksestä eikä noin 20 kehystä myöhemmin; järven bittikartta on silloin vielä tyhjä
    sw_last = next(f for f, q in enumerate(pos) if px(q) < 8 * bases[1])
    # ja jo nousun lopussa: järven rivien värimuisti VR_F:stä (vr_step, rivi kehyksessä), sitten
    # vk_step VKC_F:stä (välkesolut, listat siirrolla), kun ppx <= VR_PR (kohdesolut tyhjiä)
    vr_inc, vr_pr, vr_crn = rise_valke(vk_lists, bmp)
    vr_f = sw_last + VR_LEAD
    vkc_f = max(vr_f + vr_crn + 1, next(f for f, q in enumerate(pos) if px(q) <= vr_pr))
    assert vkc_f < move - 30, "nousun välke liian myöhään"
    inc += vr_inc + [f"VR_F = {vr_f}", f"VKC_F = {vkc_f}"]
    inc += [f"SUNSET_F = {sunset_f}", f"SUNSET_STEP = {SUNSET_STEP}",
            f"ILTA_F = {ILTA_F}", f"SKY_LAST = {SKY_LAST}", f"SKY_MAX = {SKY_MAX}", f"D21EV_MAX = {D21EV_MAX}", f"BIRD_RET = {BIRD_RET}",
            f"DUSK_F = {dusk_f}", f"DUSK_STEP = {DUSK_STEP}", f"DUSK_N = {DUSK_N}", f"DK_B = {DK_B}", f"EVE_D025 = {EVE_D025}", f"EVE_D026 = {EVE_D026}"]
    tabs += byte_lines("gl_ring", ring)
    tabs += byte_lines("gl_add", gl_add) if gl_add else []
    tabs += colfast()
    # etualan instanssit riviin järjestettyinä: osoitin ja leikkauksen lähde RAMissa
    tabs += byte_lines("fi_rlo", [e["row"] & 0xFF for e in finst]) + byte_lines("fi_rhi", [e["row"] >> 8 for e in finst])
    tabs += byte_lines("fi_xlo", [(24 + 2 * e["x"]) & 0xFF for e in finst])
    tabs += byte_lines("fi_bits", [(24 + 2 * e["x"]) >> 8 | 2 * e["xe"] | 8 * e["hires"] | 16 * e.get("behind", 0)
                                   for e in finst])         # bitti 1 X-laajennus, 3 hires, 4 silmien takana
    tabs += byte_lines("fi_col", [e["col"] for e in finst])
    tabs += byte_lines("fi_an", [["head", "none", "tail"].index(e["an"]) for e in finst])
    tabs += byte_lines("an_mul", [len(finst) * s for s in range(4)])
    # muunnelmat tilan mukaan: indeksi tila * N_FI + instanssi, osoitin 0 = ei instanssia
    var = [e["var"][s] for s in range(4) for e in finst]
    tabs += byte_lines("fi_ptr", [0 if v is None else sptr(fidx(v)) for v in var])
    assert all(v is None or ssrc(fidx(v)).startswith(("spr_src", "spr_xsrc", "spr_ysrc")) for v in var)   # cat_set:
    # leikkauksen lähde on osoittimen lohko (BANK3_SCR + 64 * osoitin)
    head = head[:max(i for i, v in enumerate(head) if v) + 1]   # sen jälkeen perus (AN_N)
    pack = lambda t: [sum(v << 2 * i for i, v in enumerate(t[j:j + 4])) for j in range(0, len(t), 4)]   # noqa
    tabs += byte_lines("an_head", pack(head)) + byte_lines("an_tail", pack(tail))
    anim = []
    inc += [f"AN_N = {len(head)}"]
    # kiinteät instanssit (st_bird = pääskynen + 1, sen X ja rivi lasketaan ajossa; vastaranta 0)
    tabs += byte_lines("st_line", [72 + e["row"] for e in st])
    tabs += byte_lines("st_xlo", [(24 + 2 * e["x"]) & 0xFF for e in st])
    tabs += byte_lines("st_xhi", [((24 + 2 * e["x"]) >> 8) & 1 for e in st])
    tabs += byte_lines("st_ptr", [sptr(e["blk"]) for e in st]) + byte_lines("st_col", [e["col"] for e in st])
    tabs += byte_lines("st_bird", [e["bird"] for e in st])
    bsi = [next(i for i, e in enumerate(st) if e["bird"] == k + 1) for k in range(len(BIRDS))]   # paluu (BIRD_RET):
    bx = [436, 344, 484]                                    # rivit BIRD_RROWS, lähtö ruudun ulkopuolelta porrastettuna:
    # haettu niin, että ensimmäinen näkyy 6 kehyksen päästä ja BIRD_RET + 10 .. BIRD_GONE - 14 aina vähintään yksi
    assert BIRD_RROWS == sorted(BIRD_RROWS) and bsi == sorted(bsi)
    tabs += byte_lines("br_si", bsi) + byte_lines("br_line", [72 + r - 1 for r in BIRD_RROWS])
    tabs += byte_lines("br_xlo", [(16 * x) & 0xFF for x in bx]) + byte_lines("br_xhi", [(16 * x) >> 8 for x in bx])
    b_out = bird_out(bx)
    assert not bird_gaps(bx, b_out), f"pääskysten paluussa ruutu ilman pääskystä: {bird_gaps(bx, b_out)[:5]}"
    inc += [f"BIRD_OUT = {b_out}"]
    tabs += byte_lines("dusk_tab", DUSK)
    tabs += byte_lines("dusk_hi", [c << 4 for c in DUSK])                  # dusk_step: ylänibble
    dk, ild = list(range(16)), il["d021"]                   # dusk_step päivittää $D021-tapahtumista vain värit
    for _ in range(DUSK_N):                                 # (fc_sync), joten kaistarajat eivät saa muuttua
        dk = [DUSK[c] for c in dk]
        assert all((ild[y] == ild[y + 1]) == (dk[ild[y]] == dk[ild[y + 1]]) for y in range(SKY_LAST, D21EV_MAX)), "DUSK"
    tabs += ["st_slo  .byte " + ",".join(f"<(spr_src + {64 * e['blk']})" for e in st)]
    tabs += ["st_shi  .byte " + ",".join(f">(spr_src + {64 * e['blk']})" for e in st)]
    tabs += byte_lines("bd_x0lo", [(16 * b[1]) & 0xFF for b in BIRDS]) + byte_lines("bd_x0hi", [(16 * b[1]) >> 8 for b in BIRDS])
    tabs += byte_lines("bd_dx", [b[2] & 0xFF for b in BIRDS]) + byte_lines("bd_ph", [b[3] for b in BIRDS])
    assert len(BIRD_SEQ) == len(BIRD_DY) == 32 and set(BIRD_DY) <= {-1, 0, 1}
    inc += ["BD_FW = [" + ", ".join(str(4 * a + dy + 1) for a, dy in zip(BIRD_SEQ, BIRD_DY)) + "]"]   # aalto + 1, asento << 2
    tabs += byte_lines("tx_xlo", [x & 0xFF for x, _ in tinst]) + byte_lines("tx_xhi", [x >> 8 for x, _ in tinst])
    tabs += byte_lines("tx_ptr", [sptr(t0 + i) for i in range(len(tinst))])
    tabs += byte_lines("tx_col", [c for _, c in tinst])
    sprs = ["spr_src"]                                       # kiinteät lohkot: kopioidaan pankkeihin alustuksessa
    for b in blocks[:N_MAIN]:
        sprs += byte_lines("", b)
    xsprs = ["spr_xsrc"]
    for b in blocks[N_MAIN:N_MAIN + 8]:
        xsprs += byte_lines("", b)
    ysprs = ["spr_ysrc"]
    for b in blocks[N_MAIN + 8:]:
        ysprs += byte_lines("", b)
    if integrated:
        data = demo_top([recs[min(r, nrows - 1)] for r in range(bases[-1], bases[-1] + BANK_ROWS)], sprs, xsprs,
                        ysprs + anim)
    else:
        data = sprs + xsprs + ysprs
    data.append("rec_first")                                # KOTI4:n alku (split.py)
    for k, rows in groups:
        data.append(f"rec_lay{k}")                           # asettelun k ensimmäinen uusi tietue
        for r in rows:
            data.append(f"rec_r{r}")
            data += byte_lines("", recs[r])
    data.append("rec_end")
    # malli (model.npz): bittikartan roolit pikseleittäin, etuala ja kiinteät spritet
    role = bmp_roles(bmp, nrows * 8)
    np.savez(out / "model.npz", role=role, enc_t=enc_t, sky_t=sky_t, fg_t0=fg_t0, fg_k16=fg_k16,
             fi_xe=np.array([e["xe"] for e in finst]),
             fi=np.array([(e["row"], e["x"], e["col"], ["head", "none", "tail"].index(e["an"])) for e in finst],
                         np.int32),
             fi_roles=np.array([[np.zeros((21, 12), np.uint8) if v is None else unpack(fblocks[v]) for v in e["var"]]
                                for e in finst]),
             cat_d025=CAT_COL[0], cat_d026=CAT_COL[1],
             ss=np.array([sc2, sc_end]), ilta=il["img"], ilta_d021=np.array(sc_end), sky_last=SKY_LAST, ring2=np.array(ring2),
             eve_col=np.array([EVE_D025, EVE_D026]),
             st=np.array([(e["row"], e["x"], e["col"], -1) for e in st if not e["bird"]], np.int32),
             st_roles=np.array([sroles[e["blk"]] for e in st if not e["bird"]]),
             valke=vk_model, valke_d=vd_model, birds=np.array([b[0] for b in BIRDS] + BIRD_RROWS), dusk=np.array(DUSK), dusk_n=DUSK_N,
             gl=np.array([g0, g1]), ring=np.array(ring), spr_col=np.array(SPR_COL),
             txt_line=TEXT_LINE, txt=np.array([[x, (blk[y * 3 + j // 8] >> (7 - j % 8)) & 1, y, j]
                                               for (x, _), blk in zip(tinst, tblocks)
                                               for y in range(8) for j in range(24)], np.int32))
    cred_wait = CRED_WAIT                           # tekijät valmiina ennen kuin ilta_step maalaa toisen nimen rivit
    paint = ILTA_F + len(il["scr"]) + 2 * next(i for i, (y, _) in enumerate(il["list"]) if (y & 127) >= min(CRED_TOP))
    assert MOVE_END + cred_wait + (len(cred) + CRED_PF - 1) // CRED_PF + CRED_PAUSE + 2 < paint, "tekijät kesken maalauksen"
    inc += [f"CRED_N = {len(cred)}", f"CRED_WAIT = {cred_wait}", f"CRED_PF = {CRED_PF}", f"CRED_PAUSE = {CRED_PAUSE}",
            f"CRED_N2 = {sum(k >= 0 for _, _, k in cred)}", f"CRED_COL = {CRED_COL}"]
    credtab = ["cred_data"] + byte_lines("", cred_steps(cred))
    if integrated:                                  # demossa KOTI4:n perässä (käytössä kodin loppuun)
        i = data.index("rec_end")                   # tekijät KOTI5:n jälkeen (ladataan tietueiden päälle)
        data[i:i] = ["        .fill koti5_end > * ? koti5_end - * : 0"] + credtab
        data += ["koti5_phys", "        .logical $4800", "koti5"] + iltab + ["        .dsection koti5code"] + [   # KOTI5: koti_buildin jälkeen
            "koti5_end", "        .endlogical",                               # tietueiden päälle (KOTI1-4 täynnä)
            '        .cerror koti5_end > cred_data, "KOTI5 tekijöiden päällä"']
    else:
        tabs += credtab + iltab + ["        .dsection koti5code"]
    np.save(out / "credits.npy", np.array(cred, np.int32))
    txt_off = next(f for f, q in enumerate(pos) if px(q) + WIN <= 8 * 27)   # talo (kuvan rivit 216-) ulos
    inc += [f"TXT_OFF = {txt_off}"]
    dk = list(range(16))                                    # lopun kuva tummumisen jälkeen (dusk_step DUSK_N kertaa)
    for _ in range(DUSK_N):
        dk = [DUSK[c] for c in dk]
    ilta_end = np.where(il["img"] == TRANSP, TRANSP, np.array(dk, np.uint8)[np.minimum(il["img"], 15)])
    loppukuva(out, [dk[c] for c in sc_end], ring2, gl_add, g0, g1, d, st, sblocks, cred, gph=(scene_len() + 1) & 255,
              ilta=ilta_end)
    (out / "koti.inc").write_text("\n".join(inc) + "\n")
    (out / "tables.inc").write_text("\n".join(tabs) + "\n")
    (out / "records.inc").write_text("\n".join(data) + "\n")
    print(f"koti: {nrows} riviä, p_max {p_max}, asettelut {bases}, sky_t {sky_t}, enc_t {enc_t}, korjattuja soluja "
          f"{fixes}, saaren takaa piilotettuja pikseleitä {hidden}, etuala {len(finst)} instanssia, kiinteitä {len(st)}, lohkoja {n_blk}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), "--integrated" in sys.argv)
