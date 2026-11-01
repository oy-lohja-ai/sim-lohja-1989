"""Spritet: rivikernelin generaattori (plan.py:n aikataulu 6510-koodiksi), kuvadata ja musiikin rekisterivirta.

  python3 -I src/proto/spritet/build.py OUTDIR SIDDIR

Kerneli on syklitarkka koko kehyksen ajan ilman keskeytyksiä: jokaisella rivillä kaikki 8 spriteä ovat DMA:ssa,
joten CPU:lle jää rivillä tasan LINE = 44 sykliä (mitattu), ja rivin koodi on täsmälleen sen mittainen. Rivi:
  sta $d017 (A = 0): crunch syklillä 15
  lda #maski / sta $d017: seuraavan rivin crunch-spritet
  ldy $d012 / lda d11tab,y / sta $d011: DEN pois (ei badlineja), RSEL 0 riveillä 248-251, joten pystyreunan kiikku
      ei asetu ja spritet näkyvät koko kehyksen
  vaihtorivillä (k = 1, uuden instanssin ensimmäinen näyttörivi): osoitin, väri ja X kohteesta g; $d010 on vakio
      (spritet 0-5 X < 256, spritet 6-7 X >= 256), joten rivillä on 8 vapaata sykliä: musiikki
  Y-rivillä (k = KY[i]): seuraava aloitusrivi taulusta $d012:n ja rasterin bitin 8 mukaan (tasapainotettu haara)
  vapaalla rivillä (yksi 17:stä, 20 sykliä): kello ja rekisterivirran osoitin
  lda #0, täyte
Runko on BODY = 18 x 17 riviä (jatkuva aika t mod 306) ja kiertää loputtomiin. Joka kierroksella jokaisella spritellä
on 18 instanssia, ja instanssi m näyttää kohteen g = 18 i + m (taulut SX, SP, SC). Koska kierros on 306 riviä ja
kehys 312, kohteet nousevat 6 riviä kehyksessä.

Musiikki (soitin ei mahdu kerneliin): hostin laskema SID-virta (sidvirta.py), tietue kehystä kohden (kehyksen d
muuttuvien rekisterien arvot, 16 t (enintään 16 rekisteriä) tai 32 t, fp = 16 tai 8 tietuetta sivulla).
Kierroksen järjestys rungossa:
  R0 kello: $d019:n rasterilippu (rivi 250) -> C, DFRAME += C (kierros 306 riviä, kehys 312: lippu on asettunut
     yhden kerran jokaista kierrosta kohden paitsi joka 52:nnella, haaraton)
  R1 DFRAME+1 += C, X = tietueen siirros sivulla (d mod fp) x 16|32
  R2-R3 sivu ZH = pagemap[d / fp - S / fp]
  vaihtoriveillä: ZH jokaisen kirjoituskäskyn osoitteen ylätavuun, sitten lda sivu+r,x / sta $d4rr
  R4-R5 loppu: DFRAME >= E -> rungon viimeinen jmp osoittamaan spr_exitiin
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import plan  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
ENTRY = 108                    # kernelin ensimmäinen rivi (jatkuva aika t = rivi kehyksessä 0); 40 + 4 x 17
LINE = 44                      # CPU-syklit rivillä, kun 8 spriteä on DMA:ssa (mitattu)
REPS = 18                      # instansseja spriteä kohden kierroksella
BODY = REPS * plan.PERIOD
PATH = "nnnccnnnnnnnncnnc"     # 17 rivin crunch-polku (plan.CRUNCH = c:n paikat)
SWITCH_K = 1                   # osoitin ja X uuden instanssin ensimmäisellä näyttörivillä: vanhan viimeinen rivi on
                               # piirretty X:llä, ja uuden ensimmäinen kuvarivi on tyhjä (kuvat alkavat riviltä 1)
SCREEN = 0x4000                # VIC-pankki 1: ruutu (vain osoittimet, DEN pois)
SPR_BASE = 0x4400              # spritekuvat
KERNEL_AT = 0x8000             # kernelin osoite (haarojen sivurajat lasketaan tästä)
D010 = 0xC0                    # spritet 6-7 oikealla (X 256-320)
CODE_TOP = 0x3500             # koodi ja taulut $1a00-$34ff (spritet.asm tarkistaa), sitten vapaat sivut
CODE_TOP_TIIVIS = 0x2900      # + rakettiryhmien sivut (rimgK): tiivis: palautus taulukkona, ei nz- eikä CT-taulua, koodi
# Tilarivi: kiinteä suomenkielinen rivi alareunassa, luku = kehyksen todellinen käynnistysmäärä
TEXT = ["SPRITEJÄ {}"]           # rivit (muunnos: teksti), {} = käynnistysmäärä
TEXT_SPR = (0, 1, 6, 7)        # 3 merkkiä spriteä kohden (4 MC-pikseliä merkki), spritet vierekkäin; sprite 0:n
                               # vaihtorivi on vapaan rivin perässä (Y ei ole rasteri), joten se hakee taulusta
TEXT_X = (208, 232, 256, 280)  # 6-7 X >= 256 ($d010 vakio)
LIGHT_X0 = [(185, 256)] * 2 + [(24, 185)] * 4 + [(256, 321)] * 2   # rakettien X spriteittäin: 2-5 tilarivin vasemmalla
LIGHT_X = LIGHT_X0             # muunnos voi vaihtaa (apply_variant)
# Ilotulitus Lohjan yllä 2026: kohde on raketti, ja sen kuva riippuu korkeudesta (instanssin
# alkurivin alatavu = vaihtorivin Y edellisen rivin ldy $d012:sta): nousu ja kipinävana, hidastuva vana, räjähdys
# kolmessa vaiheessa, hiipuvat kipinät, hehku. Ryhmillä eri räjähdyskorkeus (rimgK-taulut, 256 t, jaetut).
BURST = (96, 116, 136, 156, 176, 196)   # räjähdyksen alkurivi ryhmittäin
ROCKET_COL = (10, 4, 14, 3, 13, 8, 15)  # oma väri instansseittain (keltainen 7 vain purkamiselle)
SKY, SKY_FLASH = 0, (6, 4, 4, 6)        # yö, välähdys rummun iskulla (biisin ääni 2), riveillä 56-255
CT_AHEAD = 4                            # taivaan väri kirjoitetaan renkaaseen 4 kehystä etukäteen
SPARK_A, SPARK_B = (15, 14, 3, 1), (1,)   # $d025 kipinät vilkkuvat kehyksittäin, $d026 valkoinen (myös tilarivi)
TEXT_Y = 262                   # rivin ylin rasteririvi (6 riviä: Ä:n pisteet ja 5 riviä kirjainta)
NPH = 52                       # vaiheet: 52 kierrosta = 51 kehystä = 15 912 riviä
FONT = {                       # 3 x 6 MC-pikseliä (rivi 0: Ä:n pisteet), 3 = $d026
    "S": ["...", ".##", "#..", ".#.", "..#", "##."], "P": ["...", "##.", "#.#", "##.", "#..", "#.."],
    "R": ["...", "##.", "#.#", "##.", "#.#", "#.#"], "I": ["...", "###", ".#.", ".#.", ".#.", "###"],
    "T": ["...", "###", ".#.", ".#.", ".#.", ".#."], "E": ["...", "###", "#..", "##.", "#..", "###"],
    "J": ["...", "..#", "..#", "..#", "#.#", ".#."], "Ä": ["#.#", ".#.", "#.#", "###", "#.#", "#.#"],
    " ": ["..."] * 6, "1": ["...", ".#.", "##.", ".#.", ".#.", "###"], "4": ["...", "#.#", "#.#", "###", "..#", "..#"],
    "6": ["...", ".##", "#..", "###", "#.#", "###"], "7": ["...", "###", "..#", ".#.", ".#.", ".#."],
    "-": ["...", "...", "...", "###", "...", "..."],
    "5": ["...", "###", "#..", "##.", "..#", "##."], "8": ["...", "###", "#.#", "###", "#.#", "###"],
    "0": ["...", "###", "#.#", "#.#", "#.#", "###"], "2": ["...", "##.", "..#", ".#.", "#..", "###"],
    "3": ["...", "##.", "..#", ".#.", "..#", "##."], "9": ["...", "###", "#.#", "###", "..#", "##."],
    ":": ["...", "...", ".#.", "...", ".#.", "..."], "K": ["...", "#.#", "#.#", "##.", "#.#", "#.#"],
    "L": ["...", "#..", "#..", "#..", "#..", "###"],
}
# Iso kirjasin laskurille: 4 x 9 MC-pikseliä (rivi 0: Ä:n pisteet, kirjain riveillä 1-8), merkkiväli 5, joten
# «SPRITEJÄ:» (44 px) mahtuu neljälle spritelle (48 px)
FONT_ISO = {
    "S": [".##.", "#..#", "#...", ".##.", "...#", "...#", "#..#", ".##."],
    "P": ["###.", "#..#", "#..#", "###.", "#...", "#...", "#...", "#..."],
    "R": ["###.", "#..#", "#..#", "###.", "#.#.", "#..#", "#..#", "#..#"],
    "I": ["###.", ".#..", ".#..", ".#..", ".#..", ".#..", ".#..", "###."],
    "T": ["###.", ".#..", ".#..", ".#..", ".#..", ".#..", ".#..", ".#.."],
    "E": ["####", "#...", "#...", "###.", "#...", "#...", "#...", "####"],
    "J": ["...#", "...#", "...#", "...#", "...#", "#..#", "#..#", ".##."],
    "Ä": [".##.", "#..#", "#..#", "#..#", "####", "#..#", "#..#", "#..#"],
    ":": ["....", "....", ".#..", ".#..", "....", "....", ".#..", ".#.."],
    "K": ["#..#", "#..#", "#.#.", "##..", "##..", "#.#.", "#..#", "#..#"],
    "L": ["#...", "#...", "#...", "#...", "#...", "#...", "#...", "####"],
    " ": ["...."] * 8,
    "0": [".##.", "#..#", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."],
    "1": [".#..", "##..", ".#..", ".#..", ".#..", ".#..", ".#..", "###."],
    "2": [".##.", "#..#", "...#", "..#.", ".#..", "#...", "#...", "####"],
    "3": [".##.", "#..#", "...#", ".##.", "...#", "...#", "#..#", ".##."],
    "4": ["#..#", "#..#", "#..#", "####", "...#", "...#", "...#", "...#"],
    "5": ["####", "#...", "#...", "###.", "...#", "...#", "#..#", ".##."],
    "6": [".##.", "#...", "#...", "###.", "#..#", "#..#", "#..#", ".##."],
    "7": ["####", "...#", "...#", "..#.", ".#..", ".#..", ".#..", ".#.."],
    "8": [".##.", "#..#", "#..#", ".##.", "#..#", "#..#", "#..#", ".##."],
    "9": [".##.", "#..#", "#..#", ".###", "...#", "...#", "...#", ".##."],
}
FONT_ISO = {k: ["#..#" if k == "Ä" else "...."] + v for k, v in FONT_ISO.items()}


GROUP: dict[int, int] = {}     # kohde -> rakettiryhmä (main täyttää ennen kernelin tuottamista)
LOGO_PTR: dict[int, int] = {}  # kohde -> logon palan osoitin (lda #osoitin, ei rakettitaulua)
WOB: dict[int, tuple[str, str]] = {}   # kohde -> logon sarakkeen X-taulu ja logon tila (ldy ZK + n / lda flxC,y)
IMMC: dict[int, int] = {}      # kohde -> väri lda #:llä (2 sykliä vapaaksi X-taululle tai kierroslaskurille)
LOGO_DIR = Path(os.environ.get("SPRITET_LOGOT", ROOT / "tools/gfx/data/ryhmalogot/spritet"))   # testi: muu hakemisto
# Muunnokset (make VARIANT=...): sama kerneli, eri sisältö. Logo: (nimi, ensimmäinen sprite,
# yläreunan rungon rivi, X). Logot spriteillä 2-5 (ei tilarivin spritejä), kaistojen välissä vähintään 17 riviä,
# jotta yksikään instanssi ei kuulu kahteen logoon; X + leveys <= 208 (tilarivi 208-303).
VARIANTS: dict[str, dict] = {
    # perus: ei taivaan välähdystä kuten lentavat (välähdys välkkyisi sinisenä, ja koko ruutu välähtäisi violettina)
    "": {"logos": [], "flash": ()},
    "seisoo": {"logos": [], "still": ("hedelmae", (0, 1), 110, 148)},
    # hidas: kolmen kehyksen runko 55 x 17 = 935 riviä = 936 - 1, joten kaikki nousee 1/3 riviä
    # kehyksessä (17 px/s); kopiot kolmeen kehykseen (+312, +624), muut instanssit tähtinä kopioina
    "hidas": {"reps": 55, "copies": [0, 312, 624], "text_spr": (), "flytext": (2, 250, 60),
              "logos": [("nuori_lohja", 2, 40, 48), ("hedelmae", 2, 130, 100)]},
    # putoavat: kahden kehyksen runko 37 x 17 = 629 riviä = 624 + 5, joten kaikki laskeutuu 2,5 riviä
    # kehyksessä (125 px/s); kopiot molempiin kehyksiin (+312), muut instanssit putoavina kipinöinä
    "putoavat": {"reps": 37, "copies": [0, 312], "text_spr": (), "flytext": (5, 270, 232), "sparks": True,
                 "logos": [("crsp", 0, 10, 40), ("nuori_lohja", 0, 80, 100), ("afwd", 0, 150, 60),
                           ("gray_marchers", 0, 210, 80), ("hedelmae", 4, 100, 200)]},
    "pyyhkaisy": {"logos": [], "flash": (), "text_spr": ()},
    # lentavat: ei taivaan välähdystä (se välkkyisi sinisenä), taivas pysyy yönä. Logot leijuvat sivuttain koko
    # ruudun leveydeltä ilotulitteiden päällä: ilotulitus kaikilla spriteillä ja ryhmälogot kerran kierroksella
    # spriteillä 0-3, jotka piirtyvät rakettien päälle (float: järjestys alhaalta ylös, jakso kierroksina, vaiheet
    # jakson kuudesosina); tilarivi spriteillä 4-7, joiden raketit täyttävät leveyden (0-3 ovat enimmäkseen logoja);
    # kaksi räjähdyskorkeutta (muisti: tiivis virta integraatiossa ja varatut sivut $c0-$cf vapaina). Sivuttaisnopeus
    # on pieni, jotta logoista saa selvää; pystyliike on hilan (6 riviä kehyksessä, ennätyskernelin oma). Logot eivät
    # liiku sivuttain samassa tahdissa: vaihe logon paikasta rungossa
    # (aalto: yksi jakso rungon 306 rivillä, sauma ehjä), joten logopino on kulkeva sinikäyrä; jakso 132 ja vasen
    # reuna x 76-196 (huippunopeus 2,9 px kierroksessa). Nopeus kasvaa hiljalleen, kunnes liike on kuin tehosekoitin:
    # jokaisella logolla oma laskuri (float_step), askelsivu (KNP) virrasta kehyksittäin (float_program): alku
    # ennallaan, sitten huippunopeus kasvaa tasaisesti eksponentiaalisesti (kiihdytys), alueelta 1 keskikohdan
    # ylityksellä alueelle 2 (koko leveys, jakso 58, paikka eikä nopeus hyppää) ja vaihe kahdella kertoen alueelle 3
    # (kaksi aaltoa rungossa), loppu noin 36 px kierroksessa. Kiihdytys on nopea, jotta kohtaus pysyy lyhyenä:
    # rauhallinen alku 0-149, kiihdytys 150-420, tehosekoitin 420-479 (osa 480 kehystä).
    # Laskuri kuten latauksen ilotulituksessa: kaksi riviä SPRITEJÄ: / N KPL (N = kehyksen käynnistykset), sama
    # kirjasin ja paikka.
    # Laskuri oikeassa reunassa: spritet 4-7 X 248-343, rivit tasattu oikeaan reunaan (oikein pikseli X 342-343),
    # sprite 5 X >= 256 ($d010 $e0, sen raketit oikealla). Isompi kirjasin: FONT_ISO 4 x 9, rivit 232-240 ja 242-250.
    # Luku on vakio 146, jotta se ei vilku (jokaisessa kehyksessä käynnistyksiä on vähintään 146, mitattu)
    "lentavat": {"bursts": (96, 166), "flash": (), "logos": [], "text_spr": (4, 5, 6, 7), "teksti": ["SPRITEJÄ:", "{} KPL"], "text_y": 232, "kirjasin": "iso", "luku": 146,
                 "text_x": (248, 272, 296, 320), "tasaus": "oikea", "d010": 0xE0,
                 "light_x": [(24, 233)] * 4 + [(24, 256)] + [(256, 321)] * 3,
                 "float": {"spr": (0, 1, 2, 3), "logos": ["crsp", "afwd", "jml", "adapt", "gray_marchers", "pwp"],
                           "aalto": 1, "varattu": (0xC0, 0xD0),   # $c000-$cfff ei ladata (glue, split.py)
                           # tila-alueet (jakso, vasemman reunan ääret); tiloja yhteensä <= 248 (knA $4300-$43f7)
                           "alueet": [(132, (76, 196)), (58, (24, 248)), (58, (24, 248))],
                           # askelsivut: sääntö alueittain (float_step)
                           "sivut": {"A": [1, 1, 1], "B": [2, 2, 2], "C": [("x", 4, 1), 1, 1],
                                     "D": [4, ("m", 2, 2, 3), 3]},
                           # huippunopeus (px kierroksessa) kasvaa eksponentiaalisesti kehyksestä a kehykseen b
                           # nopeuteen v (ennen a alueen 1 askel 1)
                           "kiihdytys": (150, 420, 36.0),
                           # alueet järjestyksessä: askel sivuittain ja siirtymäsivu kehyksiksi, kun nopeus ylittää
                           # alueen suurimman askeleen
                           "vaiheet": [({"A": 1, "B": 2, "D": 4}, ("C", 24)), ({"A": 1, "B": 2}, ("D", 2)),
                                       ({"A": 1, "B": 2, "D": 3}, None)]}},
}
# Kasvu (vaihtoehto: spritejä lisätään yksi kerrallaan, ja laskuri vain kasvaa): kuten lentavat, mutta jokainen
# instanssi on alussa piilossa ja kytkeytyy päälle yksi kerrallaan
# kiihtyen iskuilla (kasvu: ensimmäinen kehys, iskun kehykset, nopeus iskuittain instanssia kehyksessä), täysi
# ennätys viimeistään puolivälissä. Piilotus: rakettien X ja logojen osoitin
# RAM-taulusta kv_tab + g (raketti reunan alle, logo tyhjään kuvaan); virta kirjoittaa kehyksen päälle tulevat
# itse: kirjoituksen sta kv_tab osoitteen alatavu (g) ja arvo (Stream, kasvu_tabs). Ei tilarivin
# vaihetauluja (kaikki 8 spriteä piilotettavissa): laskuri «SPRITEJÄ: / 146 KPL» on hilan mukana kulkeva teksti
# (flytext) spriteillä 4-7, ja se kytkeytyy viimeisenä, kun kaikki ovat päällä. Käynnistyksiä 146-147 koko ajan.
# Logot kokonaisina yksi kerrallaan: leijuva logo n on alussa omassa piilotilassaan ZH + n (kaikki sarakkeet X 0
# reunan alla, askelsivut pitävät sen siinä). Virta kirjoittaa askelsivun paikkaan ZH + n logon oikean tilan, ja
# logon oma laskuri (rivi logon kaaren ulkopuolella) siirtää logon siihen, joten koko logo syttyy samassa
# kierroksessa. Laskurin sarakkeen instanssit lukevat X:n samasta kv_tab-tavusta, ja sen neljä kirjoitusta ovat
# samassa tietueessa riveillä, jotka ovat laskurin kaaren ulkopuolella (kasvu_schedule).
VARIANTS["kasvu"] = {**VARIANTS["lentavat"], "text_spr": (), "teksti": ["SPRITEJÄ:", "146 KPL"],
                     "flytext": (4, 120, 248), "kasvu": (0, 30, (1 / 8, 1 / 4, 1 / 2, 1, 2, 3)),
                     # piilotilat ZH + n tarvitsevat 6 taulun paikkaa (tiloja <= 248): alue 1 jakso 132 -> 126
                     "float": {**VARIANTS["lentavat"]["float"],
                               "alueet": [(126, (76, 196)), (58, (24, 248)), (58, (24, 248))]}}
VARIANT = ""
KASVU: dict = {}               # kasvu-muunnos: {"cfg"} (apply_variant), floats lisää "zh", "arcs" ja "rows",
                               # kasvu_tabs "xidx", "sched", "at" ja "valmis"
KASVU_MID = (60, 240)          # kasvu: laskuri syttyy, kun sen rivit ovat näillä rasteririveillä (keskellä ruutua;
                               # rungon rivi b kehyksessä d rivillä b - 312 d mod BODY, VICE:ssä 2-3 kehyksen viive
                               # ja malli 2-3 kehystä edellä kumoavat toisensa)
KASVU_KW = 4                   # kasvu: kytkentäkanavia kehyksessä (virran tietueessa 3 t kanavaa kohden; laskuri 4)
KERNEL_REGIONS = [(0x8000, 0xD000), (0xE000, 0xFF00)]   # kerneli jatkuu seuraavaan alueeseen jmp:llä


def apply_variant(variant: str) -> None:
    """Muunnoksen rungon pituus (reps x 17 riviä: 18 = yksi kehys, 6 riviä ylös kehyksessä), tilarivin spritet
    (tyhjä: ei vaihetauluja), tilarivin rivi ja rakettien X-alueet."""
    global VARIANT, REPS, BODY, TEXT, TEXT_SPR, TEXT_X, TEXT_Y, LIGHT_X, FLOAT_SPR, D010
    cfg = VARIANTS[variant]
    FLOAT_SPR = cfg.get("float", {}).get("spr", (2, 3, 4, 5))
    FLOAT_R[:] = []
    for p, (lo, hi) in cfg.get("float", {}).get("alueet", []):
        FLOAT_R.append((sum(r[1] for r in FLOAT_R), p, lo, hi))
    VARIANT, REPS = variant, cfg.get("reps", 18)
    BODY = REPS * plan.PERIOD
    TEXT_SPR = cfg.get("text_spr", (0, 1, 6, 7))
    TEXT_Y = cfg.get("text_y", 262)
    TEXT = cfg.get("teksti", ["SPRITEJÄ {}"])
    TEXT_X = cfg.get("text_x", (208, 232, 256, 280))
    D010 = cfg.get("d010", 0xC0)
    KASVU.clear()
    KASVU.update({"cfg": cfg["kasvu"]} if "kasvu" in cfg else {})
    LIGHT_X = cfg.get("light_x", LIGHT_X0)


# Leijuvat logot (lentavat): ryhmälogot ilotulituksen päällä neljällä peräkkäisellä
# spritellä (FLOAT_SPR, muunnoksen float.spr), jokainen logo kerran kierroksella. Logon n tila ZK + n on X-taulujen
# indeksi: tila-alueet (FLOAT_R) ovat kosineja omalla jaksolla ja heilunnalla, ja tila etenee kerran kierroksessa
# askelsivun mukaan (float_step). Sarakkeiden 1-3 $d010-bitit vaihtuvat logon mukaan kahdella kirjoituksella: W =
# viimeisen sarakkeen ensimmäinen logon vaihtorivi (kaikki sarakkeet ovat jo logon instansseissa ja tyhjiä riville W
# asti) kirjoittaa logon bitit taulusta tilan mukaan, ja E = ensimmäinen logon jälkeinen vaihto missä tahansa
# sarakkeessa (logo on piirretty) kirjoittaa vakion D010. Logon rivit W + 1..W + H.
FLOAT_SPR = (2, 3, 4, 5)
FLOAT_R: list[tuple[int, int, int, int]] = []   # tila-alueet: (ensimmäinen tila, jakso, vasen reuna min, max)
D010W: dict[int, list[I]] = {}  # kohde -> $d010-kirjoitus vaihtorivillä X:n jälkeen (W: taulusta, E: vakio)
RESERVED: set[int] = set()      # rungon rivit j, joille roles ei laita virtaa ($d010-kirjoitus, laskurit)


def float_region(z: int) -> int:
    return next(n for n, r in enumerate(FLOAT_R) if r[0] <= z < r[0] + r[1])


def float_x(z: int) -> int:
    """Logon vasen reuna tilassa z (alueen kosini reunasta reunaan)."""
    base, p, lo, hi = FLOAT_R[float_region(z)]
    return lo + round((hi - lo) * (1 - math.cos(2 * math.pi * (z - base) / p)) / 2)


def float_step(z: int, rules: list) -> int:
    """Tilan z seuraaja askelsivulla (sääntö alueittain): k = askel k alueen sisällä; ("x", k, kohde) = askel k, ja
    keskikohdan (vaihe 1/4 tai 3/4, vasen reuna keskellä) ylittävä logo siirtyy kohdealueelle samaan vaiheeseen (paikka
    ei hyppää, nopeus ja heilunta kasvavat; logot ylittävät eri kehyksissä); ("m", kerroin, kohde, k) = askel k ja
    vaihe kertoimella kohdealueelle (vaihe-erot kasvavat, paikka hyppää). Kohdealueella sama sivu jatkaa sen omalla
    säännöllä, joten sivu voi olla päällä monta kehystä (virta ja laskurit eivät ole samassa tahdissa)."""
    r = float_region(z)
    base, p = FLOAT_R[r][:2]
    rule, u = rules[r], z - base

    def to(dst: int, ph: float) -> int:
        return FLOAT_R[dst][0] + round(ph * FLOAT_R[dst][1]) % FLOAT_R[dst][1]
    if isinstance(rule, int):
        return base + (u + rule) % p
    if rule[0] == "x":
        _, k, dst = rule
        if any(u < q <= u + k for q in (p / 4, 3 * p / 4)):
            return to(dst, (u + k) / p % 1)
        return base + (u + k) % p
    _, m, dst, k = rule
    return to(dst, m * (u + k) / p % 1)


def kasvu_n(d: int) -> int:
    """Kasvu: päällä olevien instanssien määrä kehyksessä d (0..REPS * 8): nopeus (instanssia kehyksessä) iskuittain
    cfg[2] ensimmäisestä kehyksestä cfg[0] alkaen, isku cfg[1] kehystä; viimeinen nopeus jatkuu, kunnes kaikki ovat
    päällä."""
    d0, beat, rates = KASVU["cfg"]
    acc = sum(rates[min((f - d0) // beat, len(rates) - 1)] for f in range(d0, d + 1))
    return min(REPS * 8, int(acc + 1e-9)) if d >= d0 else 0


def float_speed(r: int) -> float:
    """Alueen r huippunopeus askeleella 1 (px kierroksessa): kosinin derivaatta keskikohdassa."""
    _, p, lo, hi = FLOAT_R[r]
    return math.pi * (hi - lo) / p


def float_program(s: int, e: int) -> dict[int, str]:
    """Askelsivu kehyksille s..e + 2: tavoitenopeus v(d) kasvaa eksponentiaalisesti (hiljalleen, sama suhde joka
    kehys), askel = v / alueen nopeus, ja murto-osa sekoitetaan kahden lähimmän askeleen sivusta (Bresenham). Kun
    askel ylittää alueen suurimman, siirtymäsivu on päällä annetun määrän kehyksiä ja seuraava alue alkaa."""
    cfg = VARIANTS[VARIANT]["float"]
    d0, d1, vmax = cfg["kiihdytys"]
    v0 = float_speed(0)
    out, k, acc, d = {}, 0, 0.0, s
    while d <= e + 2:
        t = min(max((d - d0) / (d1 - d0), 0.0), 1.0)
        step = v0 * (vmax / v0) ** t / float_speed(k)
        steps, exit_ = cfg["vaiheet"][k]
        if exit_ and step >= max(steps.values()):
            out.update({d + n: exit_[0] for n in range(exit_[1])})
            d, k, acc = d + exit_[1], k + 1, 0.0
            continue
        opts = sorted(steps.items(), key=lambda x: x[1])
        step = min(max(step, opts[0][1]), opts[-1][1])
        lo = max((o for o in opts if o[1] <= step), key=lambda o: o[1])
        hi = min((o for o in opts if o[1] >= step), key=lambda o: o[1])
        acc += 0.0 if hi == lo else (step - lo[1]) / (hi[1] - lo[1])
        out[d] = hi[0] if acc >= 1 else lo[0]
        acc -= acc >= 1
        d += 1
    assert k == len(cfg["vaiheet"]) - 1, "leijuvat logot: ohjelma ei ehdi viimeiselle alueelle"
    return {x: out[x] for x in range(s, e + 3)}


def float_sim(init: list[int], prog: dict[int, str], lag: int = 0) -> list[list[int]]:
    """Logojen tilat kehyksittäin hostissa (yksi askel kehyksessä, lag: sivu kehystä myöhemmin)."""
    pages = VARIANTS[VARIANT]["float"]["sivut"]
    zs, out = list(init), []
    ds = sorted(prog)
    for d in ds:
        page = pages[prog[ds[max(0, ds.index(d) - lag)]]]
        zs = [float_step(z, page) for z in zs]
        out.append(list(zs))
    return out


def float_msb(left: int) -> int:
    """$d010, kun logon vasen reuna on left (sarakkeet 24 px:n välein spriteillä FLOAT_SPR)."""
    return D010 | sum(1 << i for c, i in enumerate(FLOAT_SPR) if left + 24 * c >= 256)
ROLE_LABELS: list[str] = []    # virran kirjoituskäskyt, joiden ylätavu alustetaan (patch.inc)
MIDLINE: set[int] = set()      # rivit, joiden Y-haara ylittäisi sivun (main siirtää koodia aiempaa riviä pidentämällä)


class I(tuple):
    """Käsky: teksti, syklit, tavut, nimiö."""
    def __new__(cls, text: str, cyc: int, size: int, label: str = ""):
        return super().__new__(cls, (text, cyc, size, label))


def crunch(b: int, m: int) -> int:
    return ((0x2A & (b & m)) | (0x15 & (b | m))) & 63


def row_offsets() -> list[int]:
    """Instanssin näytettävien rivien tavuosoite lohkossa (crunch järjestää rivit uudelleen)."""
    b, rows = 0, []
    for op in PATH:
        rows.append(b)
        m = (b + 3) & 63
        b = m if op == "n" else crunch(b, m)
    assert b == 63 and len(rows) == plan.PERIOD
    return rows


def y_offsets() -> list[int]:
    """Y-päivityksen rivi käynnistyksestä (2..16) niin, että se ei osu vaihtoriveille eikä toisen Y:n riville."""
    busy = {(ph + SWITCH_K) % plan.PERIOD for ph in plan.PHASE}
    ky = []
    for ph in plan.PHASE:
        k = next(k for k in range(2, plan.PERIOD) if (ph + k) % plan.PERIOD not in busy)
        busy.add((ph + k) % plan.PERIOD)
        ky.append(k)
    return ky


KY = y_offsets()


def kind(t: int) -> tuple[str, int]:
    """Rivin laji hilassa ja sprite: vaihto (s), Y (y) tai vapaa (p, -1)."""
    for i, ph in enumerate(plan.PHASE):
        k = (t - ph) % plan.PERIOD
        if k == SWITCH_K:
            return "s", i
        if k == KY[i]:
            return "y", i
    return "p", -1


def switch_runs_ok() -> None:
    """Reuna: rivien 248-251 joukossa pitää olla vaihdoton rivi (vaihtorivit eivät kirjoita $d011:tä)."""
    sw = {(ph + SWITCH_K) % plan.PERIOD for ph in plan.PHASE}
    for t in range(plan.PERIOD):
        assert not all((t + d) % plan.PERIOD in sw for d in range(4)), "neljä vaihtoriviä peräkkäin"


def first_starts() -> list[int]:
    """Spriten i ensimmäinen hilan aloitus ENTRYn jälkeen (rivi > ENTRY)."""
    return [ENTRY + 1 + ((ph - ENTRY - 1) % plan.PERIOD) for ph in plan.PHASE]


def line_code(t: int, first: list[int], jump: I | None, addr: int, role: list[I],
              text: bool = False, shift: int = 0) -> tuple[list[str], int]:
    """Rivin t (jatkuva aika) koodi osoitteesta addr; role: vapaiden syklien käskyt (vaihto- tai vapaa rivi); jump:
    rivin lopussa hyppy (3 sykliä). Palauttaa rivit ja seuraavan osoitteen. Y-lohkon haara ei saa ylittää sivua
    (otettu haara + 1 sykli)."""
    mask, ys, sw = 0, None, None
    for i, ph in enumerate(plan.PHASE):
        k = (t - ph) % plan.PERIOD
        if t - k < first[i]:                    # instanssi alkoi ennen hilaa (lämmittely tai ei mitään)
            continue
        if k in plan.CRUNCH:
            mask |= 1 << i
        if k == KY[i]:
            ys = i
        if k == SWITCH_K:
            sw = (i, REPS * i + ((t - ph) // plan.PERIOD) % REPS)
    head = [I("sta $d017", 4, 3), I(f"lda #${mask:02x}", 2, 2), I("sta $d017", 4, 3)]   # A = 0: crunch 4. syklillä
    d11 = [I("ldy $d012", 4, 3), I("lda d11tab,y", 4, 3), I("sta $d011", 4, 3)]
    body = []
    if sw is not None:                          # uuden instanssin ensimmäisellä näyttörivillä (kuvarivi 0 on tyhjä):
        i, g = sw                               # osoitin, väri ja X; ei $d011:tä (vaihtorivit eivät ole peräkkäin,
        d11 = []                                # joten reunan rivit 248-251 saavat RSEL 0)
        b = t % BODY
        sp, sx = (f"tsp{b},y", f"tsx{b},y") if text else (f"rimg{GROUP.get(g, 0)},y", f"sx_tab + {g}")
        body = [I("ldy ZPH", 3, 2)] if text else []     # tilarivin spritet: osoitin ja X vaiheen ZPH taulusta
        own = not text                          # Y on vapaa: seuraava rivi lataa sen itse (vaihdot eivät ole peräkkäin)
        if KASVU and own:                       # kasvu: rakettien ja laskurin X piilotettavasta taulusta
            sx = f"kv_tab + {KASVU.get('xidx', {}).get(g, g)}"
        body += [I(f"lda #${LOGO_PTR[g]:02x}", 2, 2) if g in LOGO_PTR and own else I(f"lda {sp}", 4, 3)]
        body += [
                 I(f"sta ${SCREEN + 0x3f8 + i:04x}", 4, 3),
                 I(f"lda #${IMMC[g]:02x}", 2, 2) if g in IMMC and own else I(f"lda sc_tab + {g}", 4, 3),
                 I(f"sta $d{0x27 + i:03x}", 4, 3)]
        body += [I(f"ldy {WOB[g][1]}", 3, 2), I(f"lda {WOB[g][0]},y", 4, 3)] if g in WOB and own \
            else [I(f"lda {sx}", 4, 3)]
        body += [I(f"sta $d{2 * i:03x}", 4, 3)] + (D010W.get(g, []) if own else [])   # leijuvat logot: $d010 (Y = tila)
    yblk = []
    if ys is not None:
        k = KY[ys]
        yblk = [I("bit $d011", 4, 3), I("bmi +", 0, 2), I(f"lda yn0_{k},y", 0, 3), I("jmp ++", 0, 3),
                I(f"+lda yn1_{k},y", 0, 3), I("nop", 0, 1), I(f"+sta $d{1 + 2 * ys:03x}", 13, 3)]
    cyc = sum(x[1] for x in head + d11 + body + yblk + role)
    rest = LINE - cyc - 2 - (jump[1] if jump else 0)
    if rest < 0:
        raise SystemExit(f"rivi {t}: {cyc} sykliä" + (f" {[x[0] for x in head + d11 + body + yblk + role]}"
                                                     if KASVU else ""))
    fin = [I("lda ZERO", 3, 2)] if rest == 1 else [I("lda #0", 2, 2)]   # A = 0 seuraavan rivin crunchiin
    rest = 0 if rest == 1 else rest
    pad = [I("bit $ea", 3, 2)] if rest % 2 else []
    pad += [I("nop", 2, 1)] * ((rest - 3 * len(pad)) // 2)
    for n in range(len(pad)):                   # shift: täyte tavun pidemmäksi (seuraavan rivin Y-haaran sivuraja)
        if shift and pad[n][0] == "nop":
            pad[n], shift = I("lda #0", 2, 2), shift - 1
        elif shift and pad[n][0] == "bit $ea":
            pad[n], shift = I("jmp *+3", 3, 3), shift - 1
    fin += [jump] if jump else []
    # $d011 rivin viimeisillä CPU-sykleillä (sykli 52, ennen lda #0:aa): tilan vaihto (taivaan reuna) osuu rivin
    # oikeaan päähän. Viimeiseksi käskyksi se ei voi tulla: kirjoitus syklissä 55 ei pysäytä CPU:ta DMA:han, ja
    # seuraavan rivin crunch-kirjoitus siirtyisi sykliin 14 (mitattu: lukko hajoaa). ldy $d012 alussa Y-riveillä.
    early, late = (d11[:1], d11[1:]) if yblk else ([], d11)
    pads = [pad] + ([[I("jmp *+3", 3, 3)] + pad[1:]] if pad and pad[0][0] == "bit $ea" else [])   # 1 tavu lisää
    orders = [[head, early, p[:k], yblk, body, role, p[k:], late, fin] for p in pads for k in range(len(p) + 1)]
    MIDLINE.discard(t)
    for order in orders:
        seq = [x for part in order for x in part]
        a, ok = addr, True
        for ins in seq:
            if ins[0].startswith("bmi") and ((a + 2) >> 8) != ((a + 8) >> 8):
                ok = False
            a += ins[2]
        if ok:
            break
    else:                                       # Y-haara ylittää sivun: main pidentää aiempaa riviä
        MIDLINE.add(t)
    out = []
    for text, _, _, label in seq:
        if text.startswith("+"):
            out.append("+       " + text[1:])
        else:
            out.append(f"{label:<8}{text}" if label else "        " + text)
    return out, a


def ytable(k: int, hi: int) -> list[int]:
    """Seuraava aloitusrivi (Y) rivillä L + k luetusta $d012:sta D: (L + 17) mod 312, alatavu."""
    return [((d + 256 * hi - k + plan.PERIOD) % plan.LINES) & 0xFF for d in range(256)]


def byte_lines(label: str, data: list[int]) -> list[str]:
    out = [label] if label else []
    for i in range(0, len(data), 32):
        out.append("        .byte " + ",".join(f"${b:02x}" for b in data[i:i + 32]))
    return out


def pack_px(p: list[int]) -> bytes:
    """12 MC-pikseliä (0-3) spriten rivin kolmeksi tavuksi."""
    v = 0
    for q in p:
        v = v << 2 | q
    return v.to_bytes(3, "big")


def sprite_img(pts: dict[tuple[int, int], int]) -> bytes:
    """Kuva pisteistä (x 0..11 MC, y 1..15 näyttöriviä) crunchin rivijärjestykseen; rivit 0 ja 16 tyhjiä."""
    offs = row_offsets()
    blk = bytearray(64)
    for y in range(1, 16):
        bits = 0
        for x in range(12):
            bits |= pts.get((x, y), 0) << (22 - 2 * x)
        blk[offs[y]:offs[y] + 3] = bits.to_bytes(3, "big")
    return bytes(blk)


def rocket_frames() -> dict[str, bytes]:
    """Raketin vaiheet: 1 = $d025 kipinä, 2 = oma väri, 3 = $d026 kuuma. Keskikohta x 5, räjähdys rivillä 8."""
    import math
    f = {}
    for v, trail in (("a", [(5, 5), (6, 6), (4, 7), (5, 8), (6, 10), (3, 11), (7, 13), (4, 15)]),
                     ("b", [(5, 5), (4, 6), (6, 7), (5, 9), (3, 10), (6, 12), (8, 14), (5, 15)])):
        f["nousu" + v] = sprite_img({(5, 1): 3, (5, 2): 2, (5, 3): 2, (4, 4): 1, (6, 4): 1, **{p: 1 for p in trail}})
    for v, trail in (("a", [(5, 5), (4, 6), (6, 8)]), ("b", [(5, 5), (6, 6), (4, 8)])):
        f["vana" + v] = sprite_img({(5, 2): 3, (5, 3): 2, (5, 4): 1, **{p: 1 for p in trail}})

    def ring(r: float, n: int, col: int, droop: int = 0, inner: int = 0) -> dict:
        pts = {}
        for k in range(n):
            a = 2 * math.pi * (k + 0.5 * (r > 4)) / n
            x, y = round(5 + r * math.cos(a) / 2), round(8 + r * math.sin(a)) + droop
            if 0 <= x < 12 and 1 <= y <= 15:
                pts[(x, y)] = col
            if inner:
                xi, yi = round(5 + (r - 2) * math.cos(a) / 2), round(8 + (r - 2) * math.sin(a)) + droop
                if 0 <= xi < 12 and 1 <= yi <= 15:
                    pts[(xi, yi)] = inner
        return pts
    f["puhkeaa"] = sprite_img({**ring(2, 8, 2), (5, 8): 3, (5, 7): 3, (5, 9): 3})
    f["avautuu"] = sprite_img({**ring(4.5, 12, 2, 0, 3), (5, 8): 3})
    f["taysi"] = sprite_img(ring(7, 16, 1, 0, 2))
    f["hiipuu"] = sprite_img({p: c for p, c in ring(7, 12, 2, 1).items()})
    f["kipinat"] = sprite_img({p: 1 for k, p in enumerate(ring(7.5, 10, 1, 3)) if k % 2 == 0})
    f["hehkua"] = sprite_img({(4, 9): 1, (7, 12): 1})
    f["hehkub"] = sprite_img({(6, 10): 1, (3, 13): 1})
    return f


def rocket_table(burst: int, names: list[str]) -> list[int]:
    """Ryhmän kuva instanssin alkurivin alatavun mukaan (rivit 256-311 ja 0-55 samat: hehku). Kohde nousee 6 riviä
    kehyksessä, joten jokainen 6 rivin kaista on yksi kehys ja a/b vuorottelevat."""
    out = []
    for r in range(256):
        ab = "ab"[(r // 6) % 2]
        if r < 56:
            n = "hehku" + ab
        elif r > burst + 36:
            n = "nousu" + ab
        elif r > burst:
            n = "vana" + ab
        else:
            k = (burst - r) // 6
            n = (["puhkeaa", "avautuu", "taysi", "taysi"] + ["hiipuu"] * 3 + ["kipinat"] * 4)[k] if k < 11 else "hehku" + ab
        out.append(names.index(n))
    return out


def glue_path(variant: str) -> Path:
    return ROOT / f"src/scene/spritet{'-' + variant if variant else ''}_glue.asm"


def scene(variant: str | None = None) -> tuple[int, int, int]:
    """Kohtauksen kehykset S..E (src/scene/spritet-<muunnos>_glue.asm) ja biisin alku (src/gen/timing.inc)."""
    glue = glue_path(VARIANT if variant is None else variant).read_text()
    tim = (ROOT / "src/gen/timing.inc").read_text()
    val = lambda txt, n: int(re.search(rf"^{n}\s*=\s*(\d+)", txt, re.M)[1])   # noqa: E731
    return val(glue, "SCENE_START"), val(glue, "SCENE_END"), val(tim, "TIM_SONG_START")


def sky(recs: dict[int, bytes]) -> dict[int, tuple[int, int]]:
    """Ilotulituksen värit kehyksittäin ($d021, $d025): taivas välähtää biisin rummun mukaan (äänen 2 gate päälle,
    30 kehyksen välein: SKY_FLASH, sitten yö), kipinävärit vilkkuvat joka kehys."""
    rnd = random.Random(2026)
    seq = VARIANTS[VARIANT].get("flash", SKY_FLASH)   # muunnos voi poistaa välähdyksen
    out, flash = {}, 99
    for d in sorted(recs):
        if d - 1 in recs and recs[d][0x0B] & 1 and not recs[d - 1][0x0B] & 1:
            flash = 0
        out[d] = (seq[flash] if flash < len(seq) else SKY, rnd.choice(SPARK_A))
        flash += 1
    return out


EXIT_LEAD = 3                 # trampoliini jo tietueessa E - 3: virran laskuri ja tietueen osoite kulkevat kierroksen
                              # (noin kehyksen) kellon perässä, joten E:ssä paluu tulisi DFRAMEssa E + 2 ja kuva
                              # näkyisi 3-4 kehystä yli SCENE_ENDin; spr_exit kirjoittaa tietueen E


class MemoryFull(Exception):
    pass


class Stream:
    """Rekisterivirta: tietue kehykselle d = S..E (biisin kehys TIM_SONG_START + d - 1, sidvirta.py). Kirjoituskohteet
    REGS: muuttuvat SID-rekisterit, $d025 ja rungon viimeisen jmp:n ylätavu (tietueessa E: spr_exitin trampoliini),
    viimeisenä tavuna taivaan väri kehykselle d + CT_AHEAD (kerneli kirjoittaa sen CT-renkaaseen). Sivulla fp kehystä:
    kehyksen d lohko on dhi[d >> 8] + dlo[d & 255] (256 kehyksen jakso alkaa uudesta lohkosta), pagemap: lohkon sivu.
    Tiivis (integraatio, biisin tiheä kohta, kun tavallinen ei mahdu): tietueessa vain SID ja jmp:n ylätavu, fp =
    256 // tietue (ei kahden potenssi). Taivas on silloin vakio (ei välähdystä: CTw lukee CT:tä itseään, nollia), ja
    $d025 luetaan trampoliinisivulta tietueen siirroksen mukaan (kipinän väri vaihtuu joka kehys fp:n jaksossa)."""

    def __init__(self, sid: Path, compact: bool = False):
        s, e, _ = scene()
        self.s, self.e = s, e
        raw = (sid / "sid.bin").read_bytes()
        assert len(raw) == 25 * (e - s + 1), "sid.bin ei vastaa kohtauksen kehyksiä (make uudelleen)"
        sidrec = {s + n: raw[25 * n:25 * n + 25] for n in range(e - s + 1)}
        varying = [r for r in range(25) if len({x[r] for x in sidrec.values()}) > 1]
        self.col = sky(sidrec)
        self.compact = compact
        sidregs = [f"${0xD400 + r:04x}" for r in varying]
        # leijuvat logot: askelsivun ylätavu (KNP, laskurien lda (KNP),y) kehyksittäin ohjelman mukaan
        self.knp = {d: f">kn{x}" for d, x in float_program(s, e).items()} if FLOAT_R else {}
        kreg = ["@w KNP+1"] if self.knp else []
        # kasvu: kehyksessä d päälle tulevat (enintään KW) dynaamisilla kirjoituksilla: ensin osoitteiden alatavut
        # (kvs{k}+1, aiemmin kierroksessa), sitten arvot (sta kv_tab, label kvs{k})
        self.kw = KASVU_KW if KASVU else 0
        kreg += [f"@w kvs{k}+{o}" for o in (1, 2) for k in range(self.kw)] + [f"kv_tab:kvs{k}" for k in range(self.kw)]
        if compact:
            assert len({c[0] for c in self.col.values()}) == 1, "tiivis virta vaatii vakiotaivaan (ei välähdystä)"
            self.regs = sidregs + ["kjmp+2"] + kreg
            self.vals = {d: bytes(sidrec[d][r] for r in varying) for d in sidrec}
            self.rec = len(self.regs)
            self.fp = 256 // self.rec
        else:
            self.regs = sidregs + ["$d025", "kjmp+2"] + kreg
            self.vals = {d: bytes(sidrec[d][r] for r in varying) + bytes([self.col[d][1]]) for d in sidrec}
            self.rec = 16 if len(self.regs) + 1 <= 16 else 32   # tietue: 16 tai 32 t, sivulla fp kehystä
            self.fp = 256 // self.rec
        self.exitregs = sidregs + ["$d025"]
        self.last = bytes(sidrec[e][r] for r in varying) + bytes([self.col[e][1]])
        self.first_sid = sidrec[s]
        self.bps = -(-256 // self.fp)                       # lohkoja 256 kehyksen jaksossa
        self.blocks = self.block(e + 2) + 1                 # E + 1, E + 2 = E (kierros voi edetä yli)
        assert self.blocks <= 256, "kohtaus liian pitkä"

    def block(self, d: int) -> int:
        return ((d >> 8) - (self.s >> 8)) * self.bps + (d & 255) // self.fp - (self.s & 255) // self.fp

    def sky_at(self, d: int) -> int:
        return self.col[min(max(d, self.s), self.e)][0]

    def tables(self, pages: list[int], znext: list[int]) -> list[str]:
        s, e, fp = self.s, self.e, self.fp
        out = [f"S_FRAME = {s}", f"E_FRAME = {e}", f"NV = {len(self.regs)}", f"CT_AHEAD = {CT_AHEAD}",
               "EXITREG = [" + ", ".join(self.exitregs) + "]"]
        out += ["        .align 256"]                  # kernelin Y-indeksoidut taulut sivun alussa (ei sivunylitystä)
        out += byte_lines("xrec", [(d % fp) * self.rec for d in range(256)])
        out += byte_lines("dlo", [d // fp for d in range(256)])
        out += byte_lines("dhi", [self.block(d << 8) & 0xFF for d in range(256)])
        out += [f"TIIVIS = {int(self.compact)}"]
        if not self.compact:                         # tiivis: S0 ilman taulua, taivas vakio (ei rengasta)
            out += byte_lines("nz", [0] + [1] * 255)    # s += (s != DFRAME)
            out += ["CT      .fill 256"]                  # taivaan väri DFRAMEn alatavun mukaan (rengas)
        out += ["pagemap", "        .byte " + ",".join(f"${p:02x}" for p in pages)]
        out += byte_lines("znext", znext)            # tilarivin vaihe (ldy ZPH / lda znext,y)
        out += byte_lines("last_rec", list(self.last))
        out += byte_lines("ct_init", [self.sky_at(s + k) for k in range(CT_AHEAD + 1)])
        out += byte_lines("first_all", list(self.first_sid))        # proto: koko SID alussa (ei soitinta)
        out += ["        .cerror (>pagemap) != (>(znext + len(znext) - 1)), \"pagemap/znext sivun yli\"",
                "        .align 256"]
        return out

    def pages(self, pages: list[int], loop_hi: str, exit_hi: str) -> list[str]:
        out = [f"spg{b} = ${p:02x}00" for b, p in enumerate(pages)]
        for d in range(self.s, self.e + 3):
            v = [f"${x:02x}" for x in self.vals[min(d, self.e)]] + [exit_hi if d >= self.e - EXIT_LEAD else loop_hi]
            v += [self.knp[d]] if self.knp else []
            if self.kw:                              # kasvu: kanavittain osoite ja arvo (tyhjä: kv_tab + 255)
                w = KASVU["sched"].get(d, {})
                adr = [w.get(k, ("kv_tab + 255",))[0] for k in range(self.kw)]
                v += [f"<({a})" for a in adr] + [f">({a})" for a in adr]
                v += [f"${w[k][1] if k in w else 0:02x}" for k in range(self.kw)]
            if not self.compact:
                v.append(f"${self.sky_at(d + CT_AHEAD):02x}")
            assert len(v) <= self.rec
            out.append(f"        * = ${pages[self.block(d)]:02x}00 + {(d & 255) % self.fp * self.rec}")
            out.append("        .byte " + ",".join(v))
        return out

    def sparks(self, page: int, kloop_lo: int) -> list[str]:
        """Tiivis: $d025 trampoliinisivulta tietueen siirroksella (ei jmp spr_exitin tavujen päälle, siellä väri on
        jmp:n tavun alanibble)."""
        out = []
        for q in range(self.fp):
            off = q * self.rec
            if not kloop_lo <= off <= kloop_lo + 2:
                out += [f"        * = ${page:02x}00 + {off}", f"        .byte ${self.col[self.s + q][1]:02x}"]
        return out


def restore(sid: Path, compact: bool = False) -> list[str]:
    """Soittimen tila kohtauksen lopussa: kirjoitukset tavuihin, jotka eroavat alun tilasta (sidvirta.py tila0.bin ja
    tila.bin; soitin ei käy kohtauksen aikana). Noin 6 sykliä tavua kohden, joten runko jatkaa samassa kehyksessä.
    Tiivis: ajot taulukkona (pituus, osoite, arvot; enintään 4 tavun aukot yhdistetty) ja kopiosilmukka, noin 15
    sykliä tavua kohden (biisin tiheässä kohdassa avattu koodi ei mahdu CODE_TOP:n alle)."""
    sym = {}
    for line in (sid / "music.inc").read_text().splitlines():
        m = re.match(r"(\w+)\s*=\s*\$([0-9a-fA-F]+)", line)
        if m:
            sym[m[1]] = int(m[2], 16)
    addrs = [*range(sym["MUSIC_LOAD"], sym["MUSIC_END"]), *range(sym["MUSIC_BUF"], sym["MUSIC_BUF_END"]),
             *range(sym["MUSIC_ZP"], sym["MUSIC_ZP"] + 16)]
    a, b = (sid / "tila0.bin").read_bytes(), (sid / "tila.bin").read_bytes()
    assert len(a) == len(b) == len(addrs)
    if compact:
        runs: list[list[int]] = []                  # [ensimmäinen indeksi, viimeinen]
        for i in (i for i, (x, y) in enumerate(zip(a, b)) if x != y):
            if runs and i - runs[-1][1] <= 3 and addrs[i] - addrs[runs[-1][1]] == i - runs[-1][1] \
                    and i - runs[-1][0] < 255:
                runs[-1][1] = i
            else:
                runs.append([i, i])
        tab = []
        for i0, i1 in runs:
            tab += [f"        .byte {i1 - i0 + 1}", f"        .word ${addrs[i0]:04x}"] + byte_lines("", b[i0:i1 + 1])
        return ["; Generoitu: src/proto/spritet/build.py (soittimen tilan erot ajoina, tiivis)",
                "        lda #<rst_tab", "        sta ZS0", "        lda #>rst_tab", "        sta ZS1",
                "rs_run  ldy #0", "        lda (ZS0),y", "        beq rs_done", "        tax", "        iny",
                "        lda (ZS0),y", "        sta rs_st+1", "        iny", "        lda (ZS0),y", "        sta rs_st+2",
                "        lda ZS0", "        clc", "        adc #3", "        sta ZS0", "        bcc +", "        inc ZS1",
                "+       ldy #0", "rs_cp   lda (ZS0),y", "rs_st   sta $ffff,y", "        iny", "        dex",
                "        bne rs_cp", "        tya", "        clc", "        adc ZS0", "        sta ZS0",
                "        bcc rs_run", "        inc ZS1", "        bne rs_run", "rst_tab"] + tab + \
               ["        .byte 0", "rs_done"]
    out, acc = ["; Generoitu: src/proto/spritet/build.py (soittimen tilan erot kohtauksen alusta loppuun)"], None
    for adr, x, y in zip(addrs, a, b):
        if x != y:
            if y != acc:
                out.append(f"        lda #${y:02x}")
                acc = y
            out.append(f"        sta ${adr:04x}")
    return out


def roles(kinds: list[tuple[str, int]], regs: list[str], compact: bool = False) -> tuple[dict[int, list[I]], int]:
    """Rungon rivien (järjestysnumero j, laji kinds[j]) lisäkäskyt. Vapaat rivit (18, joka 17. rivi) kiertävät
    kuviota [C, H, x]: C = kello ($d019:n lippu -> DFRAME, joka 51. rivi, joten DFRAME kasvaa riveillä 250-301 ennen
    kehysnäytettä rivillä 304), H = DFRAME+1 C:n muistinumerolla ja taivaan väri $d021 = CT[DFRAME]: väri vaihtuu
    vasta kellon jälkeisellä H:lla, joka on aina riveillä 267-318, eli mustalla kaistalla (d11tab: alatavut 0-55
    epäkelpo tila), x = virran laskuri ja osoitin:
      S0  s += (s != DFRAME), virran oma laskuri: enintään yksi tietue kierroksessa, ei ohita yhtään
      S1  s:n ylätavu DFRAMEsta, B lohko, ZH sivu ja tilarivin vaihe ZPH, X tietueen siirros sivulla,
      CTw taivaan väri renkaaseen CT[s + CT_AHEAD]
    Vaihtoriveillä (muut kuin tilarivin spritet) ZH:n jälkeen ylätavut, X:n jälkeen kirjoitukset, ennen seuraavaa ZH:ta.
    Rungon loppu: kirjoituskohde kjmp+2 (tietueessa E trampoliini spr_exitiin). Palauttaa myös vaiheen rivin j."""
    nv = len(regs)
    C = [I("lda $d019", 4, 3), I("sta $d019", 4, 3), I("lsr a", 2, 1), I("lda DFRAME", 3, 2), I("adc #0", 2, 2),
         I("sta DFRAME", 3, 2)]
    H = [I("lda DFRAME+1", 3, 2), I("adc #0", 2, 2), I("sta DFRAME+1", 3, 2), I("ldy DFRAME", 3, 2),
         I("lda CT,y", 4, 3), I("sta $d021", 4, 3)]
    S0 = [I("lda DFRAME", 3, 2), I("eor ZS0", 3, 2), I("tay", 2, 1), I("lda nz,y", 4, 3),     # C = 0 (H:n adc)
          I("adc ZS0", 3, 2), I("sta ZS0", 3, 2)]
    if compact:                                 # tiivis: C = (s != DFRAME) cmp #1:llä (nz-taulu pois, sivu virralle),
        S0 = [I("lda DFRAME", 3, 2), I("eor ZS0", 3, 2), I("cmp #1", 2, 2), I("lda ZS0", 3, 2),   # taivas vakio
              I("adc #0", 2, 2), I("sta ZS0", 3, 2)]
        H = H[:3]                               # $D021 = SKY spr_go:ssa (kirjoitus kesken rivin tekisi harmaan pisteen)
    S1 = [I("lda DFRAME", 3, 2), I("cmp ZS0", 3, 2), I("lda DFRAME+1", 3, 2), I("sbc #0", 2, 2), I("sta ZS1", 3, 2)]
    B = [I("ldy ZS1", 3, 2), I("lda dhi,y", 4, 3), I("ldy ZS0", 3, 2), I("clc", 2, 1), I("adc dlo,y", 4, 3),
         I("sta ZBLK", 3, 2)]
    ZH = [I("ldy ZBLK", 3, 2), I("lda pagemap,y", 4, 3), I("sta ZH", 3, 2),
          I("ldy ZPH", 3, 2), I("lda znext,y", 4, 3), I("sta ZPH", 3, 2)]
    X = [I("ldy ZS0", 3, 2), I("ldx xrec,y", 4, 3)]
    CTW = [] if compact else [I("lda ZS0", 3, 2), I("clc", 2, 1), I("adc #CT_AHEAD", 2, 2), I("tay", 2, 1),
                              I(f"lda $ff00 + {nv},x", 4, 3, "sct"), I("sta CT,y", 5, 3)]
    plain = [j for j in range(BODY - 1) if kinds[j][0] == "p"]
    npipe = len(plain) // 18                    # monen kehyksen runko: putki joka kehykselle
    assert npipe >= 1 and (npipe == 1 or not TEXT_SPR), f"vapaita rivejä {len(plain)}"
    out, used, labels = {}, set(), []
    for k in range(npipe):
        sfx = f"_{k}" if k else ""
        ctw = [I(x[0], x[1], x[2], f"sct{sfx}" if x[3] else "") for x in CTW]
        zh = ZH if k == 0 else ZH[:3]           # tilarivin vaihe vain ensimmäisessä putkessa
        seq_p = [C, H, S0, C, H, S1, C, H, B, C, H, zh, C, H, X, C, H, ctw]
        pl = plain[18 * k:18 * k + 18]
        out.update({j: seq_p[n] for n, j in enumerate(pl)})
        j_zh, j_x, j_ct = pl[11], pl[14], pl[17]
        j_next = plain[(18 * (k + 1) + 11) % (18 * npipe)] if npipe > 1 else j_zh   # seuraava ZH
        cyc = lambda j: (j - j_zh) % BODY       # noqa: E731
        sw = sorted((j for j in range(BODY - 1) if kinds[j][0] == "s" and kinds[j][1] not in TEXT_SPR
                     and j not in used and 0 < cyc(j) < (cyc(j_next) or BODY)), key=cyc)
        sw = [j for j in sw if j not in RESERVED]   # leijuvien logojen $d010-rivit
        names = [f"ss{r}{sfx}" for r in range(nv)] + ([] if compact else [f"sct{sfx}"])
        patch = [[I("lda ZH", 3, 2), I(f"sta {lab}+2", 4, 3)] for lab in names]
        pj = sw[:len(patch)]
        if cyc(pj[-1]) >= cyc(j_ct):            # tavallinen virta: tiivis (vähemmän kohteita) uudessa prosessissa
            raise MemoryFull("ylätavut eivät ehdi ennen CTw:tä")
        slots = [[I(f"lda $ff00 + {r},x", 4, 3, f"ss{r}{sfx}"),
                  I(f"sta {regs[r].split(':')[0]}", 4, 3, regs[r].split(':')[1] + sfx if ':' in regs[r] else "")]
                 for r in range(nv)]
        assert npipe == 1 or not any(':' in r for r in regs), "kasvu: dynaamiset kirjoitukset vain yhdessä putkessa"
        if compact:                             # kipinän väri trampoliinisivulta (ei ylätavun päivitystä)
            slots.append([I("lda spk,x", 4, 3), I("sta $d025", 4, 3)])
        sj = [j for j in sw[len(patch):] if cyc(j) > cyc(j_x)][:len(slots)]
        if len(sj) != len(slots):
            raise MemoryFull(f"kirjoituksia {len(sj)}/{len(slots)} ennen seuraavaa ZH:ta")
        out.update({j: patch[n] for n, j in enumerate(pj)})
        out.update({j: slots[n] for n, j in enumerate(sj)})
        used.update(pj + sj)
        labels += names
    ROLE_LABELS[:] = labels
    return out, plain[11]


def text_rows(lines: list[str], oikea: int = 0, font: dict | None = None) -> list[list[int]]:
    """Tekstirivit kirjasimella font (oletus FONT 3 x 6, FONT_ISO 4 x 9 MC-pikseliä; 3 = $d026), merkkiväli leveys + 1,
    rivien väli 1 pikselirivi, leveys 12:n monikerraksi. oikea = leveys: rivit tasataan oikeaan reunaan (viimeisen
    merkin jälkeen ei väliä), vasemmalla tyhjää."""
    font = font or FONT
    gw, gh = len(font["0"][0]), len(font["0"])
    w = oikea or max(len(t) for t in lines) * (gw + 1)
    w += -w % 12
    rows = []
    for t in lines:
        for r in range(gh):
            row = []
            for ch in t:
                row += [3 if c == "#" else 0 for c in font[ch][r]] + [0]
            rows.append([0] * (w - len(row) + 1) + row[:-1] if oikea else row + [0] * (w - len(row)))
        rows.append([0] * w)
    return rows[:-1]


def strip(n: int) -> list[list[int]]:
    """Tilarivi kehyksen luvulla n: rivit TEXT (6 pikseliriviä ja 1 väli kukin) x 12 MC-pikseliä spriteä kohden."""
    w = 12 * len(TEXT_SPR)
    rows = text_rows([t.format(n) for t in TEXT], w if VARIANTS[VARIANT].get("tasaus") == "oikea" else 0,
                     FONT_ISO if VARIANTS[VARIANT].get("kirjasin") == "iso" else FONT)
    assert all(len(r) <= w for r in rows), "tilarivi ei mahdu spriteille"
    return [r + [0] * (w - len(r)) for r in rows]


def frame_starts(f: int) -> int:
    """Käynnistykset kehyksessä f (jatkuva aika: kehys 0 = kernelin ensimmäinen, hilassa)."""
    return sum(1 for ph in plan.PHASE for t in range(312 * f, 312 * f + 312) if (t - ph) % plan.PERIOD == 0)


def text_tables(geo: dict, obj: dict, light_sp, light_sx: list[int], still=None) -> tuple[dict, list[bytes]]:
    """Tilarivin spritejen vaihtorivit (rungon rivi b): vaiheittain (ZPH 0..NPH + 1) kuva ja X. Kierroksen I rivi j
    on jatkuvassa ajassa T = t0 + 306 I + j (t0 = rivin j_e aika kierroksella 0); ZPH kasvaa rivillä j_ph (znext:
    NPH -> NPH + 1 -> 0 -> 1 ...), joten kierros 0 ja sen jälkeen vaiheen rivit ennen j_ph:tä näkevät tyhjät vaiheet
    NPH ja NPH + 1 (ei tekstiä ensimmäisessä kehyksessä, jossa spritet vasta alkavat). Instanssin kuvarivit 1-16
    näkyvät riveillä L + 2..L + 17 ja tavut 0-2 seuraavan instanssin rivillä 0 (L + 18, vanha osoitin), kun L on
    käynnistysrivi (vaihto L + 1). Isäntä = instanssi, jonka kuvariveillä on tekstiä; seuraava instanssi saa myös
    tekstin X:n, jos tavut 0-2 ovat tekstiä (sen rivi 0 piirtyy kesken X:n vaihdon). still: paikallaan seisova logo
    (rivit, spritet, ylin rasteririvi, X) samoilla vaihetauluilla (muunnos seisoo)."""
    offs = row_offsets()
    t0, j_e, j_ph = geo["t0"], geo["j_e"], geo["j_ph"]
    lines = {j: i for j, (k, i) in enumerate(geo["kinds"]) if k == "s" and i in TEXT_SPR}

    def seen(it: int, j: int) -> int:
        n = it + (1 if j > j_ph else 0) - (1 if j_ph < j_e else 0)
        return NPH if n <= 0 else NPH + 1 if n == 1 else (n - 2) % NPH

    def content(i: int, lam: int) -> tuple[list[int], int] | None:
        f, ras = divmod(lam, 312)
        if f < 1:
            return None
        if still and i in still[1] and 0 <= ras - still[2] < len(still[0]):
            c = still[1].index(i)
            return still[0][ras - still[2]][12 * c:12 * c + 12], (still[3] + 24 * c) & 0xFF
        if not TEXT_Y <= ras < TEXT_Y + len(strip(0)):
            return None
        c = TEXT_SPR.index(i)
        return strip(VARIANTS[VARIANT].get("luku") or frame_starts(f))[ras - TEXT_Y][12 * c:12 * c + 12], TEXT_X[c] & 0xFF

    hosts, order = {}, []
    for it in range(2 * NPH + 4):
        for j, i in lines.items():
            if it == 0 and j < j_e:
                continue
            L = t0 + BODY * it + j - j_e - 1            # käynnistysrivi (vaihto L + 1)
            img = bytearray(64)
            has, hx = False, None
            for r in range(1, 17):
                cx = content(i, L + 1 + r)
                if cx:
                    img[offs[r]:offs[r] + 3] = pack_px(cx[0])
                    has, hx = True, cx[1]
            cx = content(i, L + 18)
            if cx:
                img[0:3] = pack_px(cx[0])
                has, hx = True, cx[1]
            hosts[(i, L)] = (has, bool(cx), bytes(img), hx)
            order.append((it, j, i, L))
    want: dict[int, dict[int, tuple | None]] = {j: {} for j in lines}
    for it, j, i, L in order:
        has, _, img, hx = hosts[(i, L)]
        prev = hosts.get((i, L - plan.PERIOD))
        xhost = has or (prev is not None and prev[1])
        v = (img, hx if has else prev[3]) if xhost else ("valo", (L % 312) & 0xFF)
        z = seen(it, j)
        if z >= NPH:                                    # tyhjä vaihe: kierros 0-1 (ensimmäinen kehys)
            want[j].setdefault(z, ("valo", (L % 312) & 0xFF))
            continue
        if it >= 2:
            old = want[j].get(z, v)
            assert old == v, f"vaihe {z} rivillä {j} ei ole jaksollinen"
            want[j][z] = v
    imgs: list[bytes] = []
    tabs = {}
    for j, i in lines.items():
        b = (geo["b0"] + j) % BODY
        g = obj[b]
        sp, sx = [], []
        for z in range(NPH + 2):
            v = want[j].get(z, ("valo", 0))             # vaihe, jota rivi ei koskaan näe
            if v[0] == "valo":                          # raketti instanssin korkeuden mukaan
                sp.append(light_sp(g, v[1]))
                sx.append(light_sx[g] & 0xFF)
            else:
                if v[0] not in imgs:
                    imgs.append(v[0])
                sp.append(-1 - imgs.index(v[0]))         # tekstikuva: osoitin lasketaan sijoituksen jälkeen
                sx.append(v[1])
        tabs[b] = (sp, sx)
    return tabs, imgs


def load_logo(name: str) -> tuple[list[list[int]], int]:
    """Logo MC-resoluutiolla (tools/gfx/data/ryhmalogot/spritet/NIMI.png): pikselit 0 tausta (musta tai
    läpinäkyvä), 3 valkoinen ($d026), 2 logon oma väri; palauttaa rivit ja oman värin (C64-indeksi)."""
    from PIL import Image
    sys.path.insert(0, str(ROOT / "tools/concept"))
    from concept.c64 import palette             # noqa: E402 (Colodore)
    pal = [tuple(int(v) for v in c) for c in palette()]
    im = Image.open(LOGO_DIR / f"{name}.png").convert("RGBA")
    near = lambda c: min(range(16), key=lambda k: sum((a - b) ** 2 for a, b in zip(c, pal[k])))   # noqa: E731
    rows, own = [], {}
    for y in range(im.height):
        row = []
        for x in range(im.width):
            r, g, b_, a = im.getpixel((x, y))
            k = 0 if a < 128 else near((r, g, b_))
            row.append(0 if k == 0 else 3 if k == 1 else 2)
            if k not in (0, 1):
                own[k] = own.get(k, 0) + 1
        rows.append(row)
    assert im.width % 12 == 0, f"{name}: leveys {im.width} ei ole 12:n monikerta"
    return rows, max(own, key=own.get) if own else 1


def logo_pieces(logos: list, owner: dict | None = None) -> tuple[dict[int, tuple[bytes, int, int]], list[bytes]]:
    """Logot rungon koordinaateissa (lentävät hilan mukana): jokaiselle palan instanssille kuva, X ja väri. Instanssin
    alkurivi s (vaihto s + 1): kuvarivit 1-16 riveillä s + 2..s + 17, tavut 0-2 seuraavan instanssin rivillä 0
    (s + 18). Isäntä = kuvariveillä logoa; seuraava instanssi saa logon X:n, jos tavut 0-2 ovat logoa. owner: kohde ->
    (logon järjestysnumero, sarake)."""
    offs = row_offsets()
    out: dict[int, tuple[bytes, int, int]] = {}
    imgs: list[bytes] = []
    for n_logo, (name, i0, top, x0) in enumerate(logos):
        rows, col = load_logo(name) if isinstance(name, str) else name if isinstance(name, tuple) else (name, 1)
        cols = len(rows[0]) // 12
        for c in range(cols):
            i = i0 + c
            ph = plan.PHASE[i]

            def px(line: int) -> list[int] | None:
                y = (line - top) % BODY
                return rows[y][12 * c:12 * c + 12] if y < len(rows) else None
            pieces = {}
            for m in range(REPS):
                s0 = (ph + SWITCH_K + plan.PERIOD * m - 1) % BODY      # alkurivi rungossa
                img, has = bytearray(64), False
                for r in range(1, 17):
                    p = px(s0 + 1 + r)
                    if p:
                        img[offs[r]:offs[r] + 3] = pack_px(p)
                        has = True
                p = px(s0 + 18)
                if p:
                    img[0:3] = pack_px(p)
                    has = True
                pieces[s0] = (has, bool(p), bytes(img))
            for s0, (has, _, img) in pieces.items():
                prev = pieces.get((s0 - plan.PERIOD) % BODY)
                if has or (prev and prev[1]):
                    b = (s0 + 1) % BODY
                    g = REPS * i + ((BODY * 10 + b - ph) // plan.PERIOD) % REPS
                    if g in out:
                        raise ValueError(f"{name if isinstance(name, str) else 'teksti'}: instanssi kahdessa logossa")
                    if img not in imgs:
                        imgs.append(img)
                    out[g] = (img, x0 + 24 * c, col)
                    if owner is not None:
                        owner[g] = (n_logo, c)
    return out, imgs


STARS = [[[0, 2, 0], [2, 3, 2], [0, 2, 0]], [[2, 3, 2]]]   # tähdet: kuvia = muoto x 17 kohtaa (VIC:n katto 240)
SPARKS = [[[0, 1, 0], [0, 2, 0], [0, 3, 0]], [[0, 1, 0], [0, 3, 0]]]   # putoavat kipinät: kuuma pää alhaalla


def add_stars(pieces: dict, limgs: list, copies: list[int], rnd) -> tuple[dict, list]:
    """Monen kehyksen rungossa (hidas) muut instanssit tähtinä: tähti rasterissa (rungon rivi y + kopiot), jokaisessa
    kehyksessä sen kattava instanssi, sama X ja väri. Jäljelle jäävät (ei tähteä) saavat yhden pisteen."""
    for i in range(8):
        ph = plan.PHASE[i]
        for m in range(REPS):
            y = (ph + plan.PERIOD * m + 6 + rnd.randrange(6)) % BODY
            if y >= copies[1] if len(copies) > 1 else False:
                continue                            # tähdet ensimmäisen kehyksen riveiltä, kopiot muihin
            shape = rnd.choice(SPARKS if VARIANTS[VARIANT].get("sparks") else STARS)
            w = len(shape[0])
            x0 = 4
            rows = [[0] * x0 + r + [0] * (12 - x0 - w) for r in shape]
            lo, hi = LIGHT_X[i]
            x = rnd.randrange(lo, hi)
            try:
                new, nimg = logo_pieces([((rows, rnd.choice(ROCKET_COL)), i, (y + c) % BODY, x - 0) for c in copies])
            except ValueError:
                continue
            if set(new) & set(pieces):
                continue
            for g, v in new.items():
                pieces[g] = v
                if v[0] not in limgs:
                    limgs.append(v[0])
    dot = sprite_img({(5, 8): 1})
    limgs.append(dot)
    for g in range(REPS * 8):
        if g not in pieces:
            pieces[g] = (dot, rnd.randrange(*LIGHT_X[g // REPS]), rnd.choice(ROCKET_COL))
    return pieces, limgs


def float_cols(w: int, h: int) -> dict[int, list[int]]:
    """Logon instanssien alkurivit s sarakkeittain (rivit ei modulo): X-jakso (vaihto s + 1 .. s + 17) leikkaa rivit
    W..W + H (myös tyhjät instanssit, jotta $d010-kirjoitusten välissä ei ole raketteja)."""
    return {i: [s for s in range(w - plan.PERIOD, w + h) if (s - plan.PHASE[i]) % plan.PERIOD == 0] for i in FLOAT_SPR}


def float_layout(heights: list[int], w0: int) -> list[tuple[int, dict[int, list[int]], int]]:
    """Logojen paikat kierroksella alkaen riviltä w0 (viimeisen sarakkeen vaihtorivi): (W, sarakkeiden instanssit,
    E). Seuraava W aikaisintaan, kun jokaisen sarakkeen edellisen logon instanssit ovat loppuneet ja E on ennen sitä;
    kierroksen ylimääräiset 17 rivin jaksot jaetaan tasaisesti väleihin (raketit logojen spriteillä ja kierroslaskuri)."""
    P = plan.PERIOD
    assert (w0 - 1 - plan.PHASE[FLOAT_SPR[-1]]) % P == 0
    end = lambda cs: min(max(v) + P + 1 for v in cs.values())   # noqa: E731
    slots = []
    for h in heights:
        cs, w2 = float_cols(w0, h), w0 + P
        while not (w2 > end(cs) and all(min(float_cols(w2, 1)[i]) > max(cs[i]) for i in FLOAT_SPR)):
            w2 += P
        slots.append(w2 - w0)
    units = (BODY - sum(slots)) // P
    assert units >= 1, f"leijuvat logot eivät mahdu kierrokseen ({sum(slots)} riviä)"
    for k in range(units):
        slots[(k * len(slots)) // units] += P
    out, w = [], w0
    for h, sl in zip(heights, slots):
        cs = float_cols(w, h)
        out.append((w, cs, end(cs)))
        w += sl
    return out


def floats(obj: dict[int, int], b0: int, w0: int) -> tuple:
    """Leijuvat logot (lentavat): palat (kohde -> kuva, X, väri), X-, $d010- ja askeltaulut, logojen vaihtorivit j
    (kaaret, laskurien paikat niiden ulkopuolelta), $d010-kirjoitukset (rivi b -> vakio tai None), kohteiden logot ja
    tilojen alkuarvot. Logon n sarake c lukee flxC,y (Y = ZK + n), ja tila on X-taulujen indeksi (tiloja <= 248, ei
    sivunylitystä). Alkutila on logon paikasta rungossa (aalto: jaksoja rungon matkalla, x = sin(z + aalto k y)):
    logopino on kulkeva sinikäyrä, ja rungon sauma on ehjä, koska aalto on kokonaisluku."""
    cfg = VARIANTS[VARIANT]["float"]
    names = cfg["logos"]
    logos = [load_logo(n) for n in names]
    assert all(len(r[0]) == 12 * len(FLOAT_SPR) for r, _ in logos), "leijuvat logot: leveys 4 spriteä"
    lay = float_layout([len(r) for r, _ in logos], w0)
    p0 = FLOAT_R[0][1]
    init = [round(p0 * cfg["aalto"] * (w - lay[0][0]) / BODY) % p0 for w, _, _ in lay]
    n = sum(r[1] for r in FLOAT_R)
    nh = len(logos) if KASVU else 0             # kasvu: logojen piilotilat
    assert n + nh <= 0xF8, f"leijuvat logot: tiloja {n} + {nh} (knA $4300-$43f7)"
    roff = row_offsets()
    pieces: dict[int, tuple[bytes, int, int]] = {}
    arcs, writes, goff = [], {}, {}
    KASVU.pop("arcs", None)
    KASVU.pop("rows", None)
    for k, ((rows, col), (w, cs, e)) in enumerate(zip(logos, lay)):
        arc = []
        for c, i in enumerate(FLOAT_SPR):
            def px(line: int) -> list[int]:
                y = line - w - 1
                return rows[y][12 * c:12 * c + 12] if 0 <= y < len(rows) else [0] * 12
            for s in cs[i]:
                img = bytearray(64)
                for r in range(1, 17):
                    img[roff[r]:roff[r] + 3] = pack_px(px(s + 1 + r))
                img[0:3] = pack_px(px(s + 18))
                g = obj[(s + 1) % BODY]
                assert g not in pieces, "leijuvat logot: instanssi kahdessa logossa"
                pieces[g] = (bytes(img), float_x(init[k]) + 24 * c, col)
                WOB[g], IMMC[g], goff[g] = (f"flx{c}", f"ZK + {k}"), col, k
                arc.append((s + 1 - b0) % BODY)
        gw, ge = obj[w % BODY], obj[e % BODY]
        assert gw in pieces and ge not in D010W, "leijuvat logot: $d010-rivit"
        D010W[gw] = [I("lda flmsb,y", 4, 3), I("sta $d010", 4, 3)]
        D010W[ge] = [I(f"lda #${D010:02x}", 2, 2), I("sta $d010", 4, 3)]
        RESERVED.update({(w - b0) % BODY, (e - b0) % BODY})
        writes.update({w % BODY: None, e % BODY: D010})
        arcs.append(arc)
        if KASVU:                               # kasvu: logon kaari $d010-riveineen (kytkentärivi sen ulkopuolelle)
            KASVU.setdefault("arcs", []).append(arc + [(w - b0) % BODY, (e - b0) % BODY])
            KASVU.setdefault("rows", []).append([(w + 1 + y) % BODY for y in range(len(rows))])
    tabs = [(f"flx{c}", [(float_x(z) + 24 * c) & 0xFF for z in range(n)]) for c in range(len(FLOAT_SPR))]
    tabs += [("flmsb", [float_msb(float_x(z)) for z in range(n)])]
    tabs += [(f"kn{name}", [float_step(z, rules) for z in range(n)]) for name, rules in cfg["sivut"].items()]
    if KASVU:                                   # kasvu: piilotilat ZH + k = n + k (X 0 reunan alla, askelsivut
        KASVU["zh"] = n                         # pitävät logon siinä, kunnes virta kirjoittaa paikkaan tilan)
        tabs = [(lab, tab + [n + k if lab.startswith("kn") else D010 if lab == "flmsb" else 0 for k in range(nh)])
                for lab, tab in tabs]
    return pieces, tabs, arcs, writes, goff, init


def arc_outside(j: int, rows: list[int]) -> bool:
    """Rivi j on kaaren (vaihtorivit rungon järjestyksessä, lyhin kaari, joka kattaa ne) ulkopuolella."""
    rows = sorted(set(rows))
    size, start = max(((rows[(k + 1) % len(rows)] - rows[k] - 1) % BODY, rows[k]) for k in range(len(rows)))
    return 0 < (j - start) % BODY <= size


def float_counters(arcs: list[list[int]], obj: dict[int, int], b0: int, kinds: list[tuple[str, int]]) -> dict[int, int]:
    """Logon n laskuri ZK + n etenee raketin vaihtorivillä logojen spriteillä logon n kaaren ulkopuolella (logon kaikki
    instanssit saavat saman X:n ja $d010:n): ldy ZK + n / lda (KNP),y / sta ZK + n, 11 sykliä, joten raketin osoitin ja
    väri lda #:llä (rivi tasan 44 sykliä). Rivit (rivi j -> logo n) varataan ennen virtaa."""
    out: dict[int, int] = {}
    for n, arc in enumerate(arcs):
        for j in range(BODY - 1):               # ei rungon viimeistä riviä (jmp)
            kd, i = kinds[j]
            g = obj.get((b0 + j) % BODY)
            if kd == "s" and i in FLOAT_SPR and j not in RESERVED and j not in out and g not in WOB \
                    and arc_outside(j, arc):
                out[j] = n
                break
        else:
            raise SystemExit(f"logon {n} laskurille ei vapaata vaihtoriviä kaaren ulkopuolella")
    RESERVED.update(out)
    return out


def float_check(pieces: dict[int, tuple[bytes, int, int]], sx: list[int], obj: dict[int, int],
                writes: dict[int, int | None], logo: dict[int, int], init: list[int]) -> None:
    """Simuloi logojen spritejen näytön rivit kierroksella jokaisessa tilassa: jokaisen ei-tyhjän pikselirivin X
    ($d010-bitti viimeisestä kirjoituksesta, alatavu instanssin vaihtoriviltä) on sama kuin sen instanssin tarkoittama.
    Raketin rivit 1-15 lasketaan ei-tyhjiksi. $d010-kirjoitusrivillä muuttuvan bitin sarake on tyhjä. writes: rivi b ->
    vakio tai None (logon taulu, kohteen logo logo[g]). Lisäksi ohjelma hostissa: kaikki logot käyvät alueet läpi
    järjestyksessä myös, kun sivu vaihtuu kehystä myöhemmin."""
    roff = row_offsets()
    inst = {}                                   # (sprite, b) -> (kohde, jonka X-jaksossa rivi b on, rivi jaksossa)
    for i in FLOAT_SPR:
        for m in range(REPS):
            s = plan.PHASE[i] + plan.PERIOD * m
            for k in range(17):
                inst[(i, (s + 1 + k) % BODY)] = (obj[(s + 1) % BODY], k)

    def nonblank(g: int, r: int) -> bool:
        if g in pieces:
            o = 0 if r == 0 else roff[r]
            return any(pieces[g][0][o:o + 3])
        return 1 <= r <= 15

    def want_x(g: int, i: int, z: int) -> int:
        if g in logo:
            return float_x(z) + 24 * FLOAT_SPR.index(i)
        return sx[g]
    for z in range(sum(r[1] for r in FLOAT_R)):
        msb = D010
        for k in range(2 * BODY):              # kaksi kierrosta: ensimmäinen asettaa tilan
            b, old = k % BODY, msb
            if b in writes:
                v = writes[b]
                msb = v if v is not None else float_msb(want_x(obj[b], FLOAT_SPR[-1], z) - 24 * (len(FLOAT_SPR) - 1))
            for i in FLOAT_SPR:
                g, kk = inst[(i, b)]
                src, r = (inst[(i, (b - 1) % BODY)][0], 0) if kk == 0 else (g, kk)
                if not nonblank(src, r):
                    continue
                if (msb ^ old) & (1 << i):
                    raise SystemExit(f"leijuvat logot: $d010 muuttuu näkyvällä rivillä b {b}, sprite {i}")
                if (src in logo) != (g in logo) or (src in logo and logo[src] != logo[g]):
                    raise SystemExit(f"leijuvat logot: rivin 0 pikselit toisen instanssin X:llä b {b}, sprite {i}")
                want = want_x(g, i, z)
                got = (want & 0xFF) + (256 if msb & (1 << i) else 0)
                if k >= BODY and got != want:
                    raise SystemExit(f"leijuvat logot: X {got} != {want} rivillä b {b}, sprite {i}, tila {z}")
    s, e, _ = scene()
    prog = float_program(s, e)
    for lag in (0, 1, 2):
        sim = float_sim(init, prog, lag)
        for n in range(len(init)):
            regs = [float_region(st[n]) for st in sim]
            assert regs == sorted(regs) and regs[-1] == len(FLOAT_R) - 1, f"leijuvat logot: logo {n} alueet {set(regs)}"


def kasvu_schedule(chan: list[int], logos: list[tuple[int, list[int]]],
                   text: tuple[list[tuple[str, int]], list[int], list[int]], rockets: list[tuple[str, int]],
                   pages: dict[int, str], s: int, e: int) -> tuple[dict[int, dict[int, tuple[str, int]]], dict]:
    """Kasvu: kehys -> {kanava: (osoite, arvo)} ja logon kytkentäkehys. chan: kanavan kirjoitusrivi j (sta, label
    kvs{k}). Logo (instansseja, pikselirivit) i aikaisimmassa kehyksessä, jossa tavoitemäärä kasvu_n ylittää
    (i + 1) / (L + 1) muista ja logo on keskellä ruutua (vuoroon logo, joka ehtii ensin); sen kirjoitukset (yksi
    kutakin kehyksissä d - 1..d + 1 käytettyä askelsivua kohden) kasvu_tabs täyttää. Raketit yksitellen
    tavoitekäyrän mukaan vapailla kanavilla. Laskuri (kirjoitukset, kaaren rivit, pikselirivit) puoli iskua viimeisen
    muun jälkeen yhdessä tietueessa kanavilla, joiden rivit ovat sen kaaren ulkopuolella (kaikki sen instanssit
    näkevät saman arvon), kun se on keskellä ruutua (KASVU_MID)."""
    out: dict[int, dict[int, tuple[str, int]]] = {}

    def put(ws: list, arc: list[int] | None, d: int, rows: list[int], take: bool = True) -> int:
        while d <= e:
            ok = [k for k in range(KASVU_KW) if k not in out.get(d, {}) and (arc is None or arc_outside(chan[k], arc))]
            mid = all(KASVU_MID[0] <= (b - 312 * f) % BODY <= KASVU_MID[1] for b in rows for f in range(d, d + 4))
            if len(ok) >= len(ws) and mid:
                if take:
                    out.setdefault(d, {}).update(zip(ok, ws))
                return d
            d += 1
        raise SystemExit("kasvu: ryhmälle ei kehystä (kanavat kaaren ulkopuolella, keskellä ruutua)")

    def npages(d: int) -> list[None]:
        return [None] * len({pages[x] for x in (d - 1, d, d + 1) if x in pages})

    n_other = sum(n for n, _ in logos) + len(rockets)
    last, at, left = s, {}, list(range(len(logos)))
    for i in range(len(logos)):
        due = next(d for d in range(s, e + 1) if kasvu_n(d) >= n_other * (i + 1) / (len(logos) + 1))
        k = min(left, key=lambda k: put(npages(due), None, due, logos[k][1], take=False))
        left.remove(k)
        d = put(npages(due), None, due, logos[k][1], take=False)
        at[k] = put(npages(d), None, d, logos[k][1])
        last = max(last, at[k])
    on = 0
    for d in range(s, e + 1):
        want = min(len(rockets), round(len(rockets) * kasvu_n(d) / n_other))
        free = [k for k in range(KASVU_KW) if k not in out.get(d, {})]
        for k in free[:max(0, want - on)]:
            out.setdefault(d, {})[k] = rockets[on]
            on += 1
            last = d
    assert on == len(rockets), "kasvu: raketit eivät ehdi"
    last = put(text[0], text[1], last + KASVU["cfg"][1] // 2, text[2])
    assert last < (s + e) // 2, f"kasvu: kaikki päällä vasta kehyksessä {last}"
    KASVU["valmis"] = last
    return out, at


def kasvu_tabs(sx: list[int], owner: dict, text_logo: int, text_rows_: list[int], flogo: dict[int, int],
               obj: dict[int, int], b0: int, role: dict[int, list[I]], finit: list[int], rnd, s: int,
               e: int) -> list[int]:
    """Kasvu: kv_tab:n alkuarvot (raketti ja laskurin sarake reunan alle) ja kytkentäaikataulu (KASVU["sched"],
    kasvu_schedule): raketti kv_tab + g := X; logo n: askelsivun paikka ZH + n := logon tila kytkentäkehyksessä
    (float_sim) niillä sivuilla, jotka ovat käytössä kehyksissä d - 1..d + 1, ja logon laskuri siirtää logon siihen;
    laskurin sarake c: kv_tab + sarakkeen ensimmäinen instanssi := X (KASVU["xidx"]: sarakkeen instanssit lukevat
    sen)."""
    text = sorted(g for g in range(REPS * 8) if owner.get(g, (-1,))[0] == text_logo)
    cols: dict[int, list[int]] = {}
    for g in text:
        cols.setdefault(owner[g][1], []).append(g)
    KASVU["xidx"] = {g: gs[0] for gs in cols.values() for g in gs}
    jrow = {g: (b - b0) % BODY for b, g in obj.items()}
    chan = [next(j for j, ins in role.items() if any(x[3] == f"kvs{k}" for x in ins)) for k in range(KASVU_KW)]
    prog = float_program(s, e)
    sim = float_sim(finit, prog)
    rockets = [g for g in range(REPS * 8) if g not in flogo and g not in text]
    rnd.shuffle(rockets)
    logos = [(sum(1 for g in flogo if flogo[g] == k), rows) for k, rows in enumerate(KASVU["rows"])]
    sched, at = kasvu_schedule(chan, logos,
                               ([(f"kv_tab + {gs[0]}", sx[gs[0]] & 0xFF) for _, gs in sorted(cols.items())],
                                [jrow[g] for g in text], text_rows_),
                               [(f"kv_tab + {g}", sx[g] & 0xFF) for g in rockets], prog, s, e)
    for k, d in at.items():                             # logo: tila kytkentäkehyksessä varatuille kanaville
        free = [c for c, w in sched[d].items() if w is None]
        for c, pg in zip(free, sorted({prog[x] for x in (d - 1, d, d + 1) if x in prog})):
            sched[d][c] = (f"kn{pg} + {KASVU['zh'] + k}", sim[d - s][k])
    assert all(w is not None for v in sched.values() for w in v.values())
    KASVU["sched"], KASVU["at"] = sched, at
    hide = [100 if D010 >> (g // REPS) & 1 else 0 for g in range(REPS * 8)]
    return hide + [0] * (256 - REPS * 8)


def body_code(b0: int, addr: int, role: dict[int, list[I]], tabs: dict) -> tuple[list[str], list[tuple[int, int]], int]:
    """Rungon rivit kb{b} järjestyksessä b0, b0 + 1, ... (viimeinen hyppää kb{b0}:aan) osoitteesta addr alueittain
    KERNEL_REGIONS (alue loppuu: jmp seuraavaan). role: rivin j lisäkäskyt, tabs: tilarivin vaiherivit. Palauttaa
    koodirivit, käytetyt alueet ja loppuosoitteen."""
    shifts: dict[int, int] = {}                 # rivi j -> täytteen pidennys tavuina (Y-haaran sivurajat)
    a0 = addr
    for _ in range(64):
        addr, body, bad, reg, ranges = a0, [], None, 0, []
        start = KERNEL_AT
        for j in range(BODY):
            b = (b0 + j) % BODY
            t = BODY * 10 + b                   # jatkuva aika kaukana alusta (kaikki hilassa)
            jump = I(f"jmp kb{b0}", 3, 3, "kjmp") if j == BODY - 1 else None
            seg = None
            if jump is None and addr > KERNEL_REGIONS[reg][1] - 160:    # alue loppuu: jmp seuraavaan
                try:
                    code, nxt = line_code(t, [0] * 8, I(f"jmp kseg{reg + 1}", 3, 3), addr, role.get(j, []),
                                          b in tabs, shifts.get(j, 0))
                    seg = reg + 1
                except SystemExit:
                    pass
            if seg is None:
                code, nxt = line_code(t, [0] * 8, jump, addr, role.get(j, []), b in tabs, shifts.get(j, 0))
            assert nxt <= KERNEL_REGIONS[reg][1], "kernelin alue loppui"
            body.append((addr, code, nxt - addr, seg))
            if t in MIDLINE and bad is None:
                bad = j
            addr = nxt
            if seg is not None:
                ranges.append((start, addr))
                reg = seg
                start = addr = KERNEL_REGIONS[reg][0]
        ranges.append((start, addr))
        if bad is None:
            break
        for k in range(bad - 1, -1, -1):       # lähin aiempi rivi, jonka täyte pitenee
            b = (b0 + k) % BODY
            jump = I(f"jmp kb{b0}", 3, 3, "kjmp") if k == BODY - 1 else None
            _, n2 = line_code(BODY * 10 + b, [0] * 8, jump, 0, role.get(k, []), b in tabs, shifts.get(k, 0) + 1)
            if n2 > body[k][2] and body[k][3] is None:
                shifts[k] = shifts.get(k, 0) + 1
                break
    lines = []
    for j, (_, code, _, seg) in enumerate(body):
        lines += [f"kb{(b0 + j) % BODY}"] + code
        if seg is not None:
            lines += [f"        * = ${KERNEL_REGIONS[seg][0]:04x}", f"kseg{seg}"]
    return lines, ranges, addr


def main(out: Path, sid: Path, compact: bool = False) -> None:
    global CODE_TOP
    if compact:
        CODE_TOP = CODE_TOP_TIIVIS + 0x100 * len(VARIANTS[VARIANT].get("bursts", BURST))
    out.mkdir(parents=True, exist_ok=True)
    first = first_starts()
    st = Stream(sid, compact)
    consts = ["; Generoitu: src/proto/spritet/build.py (älä muokkaa)",
              f"ENTRY = {ENTRY}", f"LINE = {LINE}", f"SCREEN = ${SCREEN:04x}", f"SPR_BASE = ${SPR_BASE:04x}",
              f"KERNEL_AT = ${KERNEL_AT:04x}", f"D010 = ${D010:02x}", f"NPH = {NPH}", f"KASVU = {int(bool(KASVU))}",
              f"WARM = [{', '.join(str(s - 21) for s in first)}]",      # lämmittely: täyskorkea instanssi
              f"FIRST = [{', '.join(str(s) for s in first)}]"]          # päättyy hilan ensimmäiseen aloitukseen
    (out / "kernel.inc").write_text("\n".join(consts) + "\n")

    def fits(t: int, fst: list[int]) -> bool:  # rivin loppuun mahtuu jmp (3 sykliä)
        try:
            line_code(t, fst, I("jmp x", 3, 3), 0, [])
            return True
        except SystemExit:
            return False
    n_entry = next(n for n in range(plan.PERIOD, 3 * plan.PERIOD) if fits(ENTRY + n - 1, first))
    b0 = next(b for b in range(BODY) if fits(BODY * 10 + (b - 1) % BODY, [0] * 8)   # rungon hyppy halvalta riviltä,
              and kind(BODY * 10 + (b - 1) % BODY)[0] != "p")                     # ei vapaalta (kuvio [C, H, x])
    kinds = [kind(BODY * 10 + (b0 + j) % BODY) for j in range(BODY)]                 # rungon järjestyksessä j
    obj = {}                                        # rungon vaihtorivi b -> kohde
    for b in range(BODY):
        for i, ph in enumerate(plan.PHASE):
            t = BODY * 10 + b
            if (t - ph) % plan.PERIOD == SWITCH_K:
                obj[b] = REPS * i + ((t - ph) // plan.PERIOD) % REPS
    for d in (WOB, IMMC, D010W, LOGO_PTR):
        d.clear()
    RESERVED.clear()
    fl_cfg = VARIANTS[VARIANT].get("float")
    if fl_cfg:                                      # leijuvat logot: $d010-rivit varataan ennen virtaa
        fpieces, wtabs, arcs, fwrites, flogo, finit = floats(obj, b0, plan.PHASE[FLOAT_SPR[-1]] + 1)
        fcount = float_counters(arcs, obj, b0, kinds)
    role, j_ph = roles(kinds, st.regs, compact)
    geo = {"t0": ENTRY + n_entry, "j_e": ((ENTRY + n_entry) % BODY - b0) % BODY, "j_ph": j_ph, "b0": b0,
           "kinds": kinds}

    # raketit: kohde g = 18 i + m (spriten i instanssi m kierroksella), ryhmä = räjähdyskorkeus
    frames = rocket_frames()
    names, lights = list(frames), list(frames.values())
    rnd = random.Random(1959)
    switch_runs_ok()
    sx = [rnd.randrange(*LIGHT_X[g // REPS]) for g in range(REPS * 8)]
    sc = [rnd.choice(ROCKET_COL) for _ in range(REPS * 8)]
    GROUP.clear()
    bursts = VARIANTS[VARIANT].get("bursts", BURST)   # rakettiryhmät (räjähdyksen alkurivi, taulu 256 t kukin)
    GROUP.update({g: rnd.randrange(len(bursts)) for g in range(REPS * 8)})
    base = SPR_BASE // 64 % 256
    rtabs = [[base + n for n in rocket_table(h, names)] for h in bursts]
    items = [it for it in VARIANTS[VARIANT]["logos"]]
    if VARIANTS[VARIANT].get("flytext"):            # tilarivi hilan mukana (ei vaihetauluja): "SPRITEJÄ 146-147"
        sp_, top_, x_ = VARIANTS[VARIANT]["flytext"]
        items.append((text_rows(TEXT, 48, FONT_ISO) if KASVU else text_rows(["SPRITEJÄ", "146-147"]), sp_, top_, x_))
    copies = VARIANTS[VARIANT].get("copies", [0])   # monen kehyksen runko: kopio jokaiseen kehykseen
    owner: dict[int, tuple[int, int]] = {}
    pieces, limgs = logo_pieces([(n, i0, (top + c) % BODY, x0) for n, i0, top, x0 in items for c in copies], owner)
    if len(copies) > 1:                             # monen kehyksen runko: jokainen kohde näkyy vain omassa kehyksessään,
        pieces, limgs = add_stars(pieces, limgs, copies, rnd)   # joten raketit ovat tähtiä kopioina, ei välkettä
    if fl_cfg:
        for g, v in fpieces.items():
            pieces[g] = v
            if v[0] not in limgs:
                limgs.append(v[0])
    for g, (img, x, col) in pieces.items():
        LOGO_PTR[g] = base + len(lights) + limgs.index(img)
        sx[g], sc[g] = x, col
    if 0 not in TEXT_SPR:                           # spriten 0 vaihtorivi on vapaan rivin perässä (Y ei ole rasteri):
        for g in range(REPS):                       # sen raketit nousevat kiinteällä kuvalla
            LOGO_PTR.setdefault(g, base + names.index("nousua"))
    lights = lights + limgs                         # logojen kuvat rakettien perään (tekstikuvat sitten)
    if fl_cfg:                                      # logojen laskurit: raketin osoitin ja väri lda #:llä
        for j, n in fcount.items():
            g = obj[(b0 + j) % BODY]
            LOGO_PTR[g], IMMC[g] = base + names.index("nousua"), sc[g]
            role[j] = [I(f"ldy ZK + {n}", 3, 2), I("lda (KNP),y", 5, 2), I(f"sta ZK + {n}", 3, 2)]
        float_check(pieces, sx, obj, fwrites, flogo, finit)
        consts += [f"ZK_INIT = [{', '.join(str(KASVU['zh'] + k if KASVU else z) for k, z in enumerate(finit))}]"]
        (out / "kernel.inc").write_text("\n".join(consts) + "\n")
    else:
        wtabs = []
    if KASVU:
        kv_init = kasvu_tabs(sx, owner, len(items) - 1, [(items[-1][2] + y) % BODY for y in range(len(items[-1][0]))],
                             flogo, obj, b0, role, finit, rnd, st.s, st.e)
    still = VARIANTS[VARIANT].get("still")
    if still:                                       # oma väri haetaan kohteesta (sc_tab + g): logon spritejen
        rows, col = load_logo(still[0])             # kaikki kohteet logon värisiä (myös niiden raketit)
        for g in range(REPS * 8):
            if g // REPS in still[1]:
                sc[g] = col
        still = (rows,) + still[1:]
    tabs, timgs = text_tables(geo, obj, lambda g, r: rtabs[GROUP[g]][r], sx, still)
    imgs = lights + timgs
    assert SPR_BASE + 64 * len(imgs) <= 0x7F00, f"spritekuvia {len(imgs)}"
    for b, (tsp, _) in tabs.items():
        tsp[:] = [x if x >= 0 else SPR_BASE // 64 % 256 + len(lights) - 1 - x for x in tsp]

    img_end = (SPR_BASE + 64 * len(imgs) + 255) & ~255
    KERNEL_REGIONS[:] = [(0x8000, 0xD000), (0xE000, 0xFF00), (img_end, 0x7F00), (CODE_TOP, 0x4000)]
    lines = ["; Generoitu: src/proto/spritet/build.py (älä muokkaa)", f"        * = ${KERNEL_AT:04x}", "kentry"]
    addr = KERNEL_AT
    for t in range(ENTRY, ENTRY + n_entry):
        last = t == ENTRY + n_entry - 1
        code, addr = line_code(t, first, I(f"jmp kb{(t + 1) % BODY}", 3, 3) if last else None, addr, [])
        lines += [f"; t = {t}"] + code
    kloop_at = addr                                 # kb{b0}: rungon ensimmäinen rivi
    body_lines, ranges, addr = body_code(b0, addr, role, tabs)
    lines += body_lines
    lines += [f"kloop = kb{b0}", f"kernel_end = ${addr:04x}", f"        .cerror * != kernel_end, \"build.py:n osoitelaskenta\""]
    (out / "kernel_code.inc").write_text("\n".join(lines) + "\n")

    # sivut: koodin jälkeen, kuvien jälkeen pankissa 1, kernelin jälkeen, $e000-: ensin tilarivin taulut (2 per sivu),
    # sitten virta
    kpages = {p for lo, hi in ranges for p in range(lo >> 8, (hi + 255) >> 8)}
    # tiivis: myös $7f (tyhjän tilan tavu $7fff = 0 jää koskematta (taulut, tietueet ja trampoliini päättyvät ennen $fe:tä, X-taulut
    # eivät tule tälle sivulle, koska ne jaetaan viimeisinä); $ff: vain viimeinen X-taulusivu, jos se päättyy ennen
    # vektoreita ($fffa)
    order = [*range(0x80, 0xC0), *range(0xE0, 0xFF), *range(0xC0, 0xD0)] if fl_cfg else [*range(0x80, 0xD0), *range(0xE0, 0xFF)]
    # lentavat: $c000-$cfff viimeisenä, jotta se jää vapaaksi, jos mahtuu (koko demossa siellä näkyy edellisen osan kuva
    # tai esiladataan seuraavaa spritetin latautuessa)
    # lentavat: ruudun $4000-$43f7 sivut ovat vapaita (DEN pois, VIC lukee vain osoittimet $43f8-), ja varatut sivut
    # (varattu) jäävät vapaiksi: koko demossa siirtymän ilotulitus pyörii $c400-$cdff:ssä spritetin latautuessa
    screen = [0x40, 0x41, 0x42] if fl_cfg else []
    varattu = set(range(*fl_cfg.get("varattu", (0, 0)))) if fl_cfg else set()
    free = [p for p in [*screen, *range(CODE_TOP >> 8, 0x40), *range(img_end >> 8, 0x80 if compact else 0x7F), *order]
            if p not in kpages and p not in varattu]
    tlines, ntab = [], len(tabs)
    tpages = free[:(ntab + 1) // 2]               # instanssi: osoittimet +0, X +64 (ldy ZPH: ei sivunylitystä)
    for n, (b, (tsp, tsx)) in enumerate(sorted(tabs.items())):
        a = tpages[n // 2] * 256 + 128 * (n % 2)
        tlines += [f"        * = ${a:04x}"] + byte_lines(f"tsp{b}", tsp)
        tlines += [f"        * = ${a + 64:04x}"] + byte_lines(f"tsx{b}", tsx)
    spages = free[len(tpages):len(tpages) + st.blocks]
    tramp = free[len(tpages) + st.blocks:len(tpages) + st.blocks + 1]      # spr_exitin trampoliini (jmp:n alatavu sama)
    if not (len(spages) == st.blocks and tramp):
        raise MemoryFull(f"muisti loppui: virta {st.blocks} sivua, vapaana {len(free) - len(tpages)}"
                         + (" (tiivis)" if compact else ""))
    tlines += [f"        * = ${tramp[0]:02x}00 + <kloop", "        jmp spr_exit", f"spk = ${tramp[0]:02x}00",
               f"        .cerror kloop != ${kloop_at:04x}, \"build.py: kloop\""]
    if compact:
        tlines += st.sparks(tramp[0], kloop_at & 0xFF)
    used = len(tpages) + st.blocks + 1
    wpages: list[list[int]] = []                    # logojen taulut sivuille (ei sivunylitystä: lda flxC,y)
    for lab, tab in sorted(wtabs, key=lambda x: -len(x[1])):
        if lab == "knA" and fl_cfg:                 # ruudun viimeiselle sivulle ennen osoittimia ($43f8)
            assert len(tab) <= 0xF8
            tlines += ["        * = $4300"] + byte_lines(lab, tab)
            continue
        pg = next((w for w in wpages if w[1] + len(tab) <= (0xFA if w[0] == 0xFF else 256)), None)
        if pg is None:
            nxt = free[used + len(wpages):used + len(wpages) + 1] or ([0xFF] if len(tab) <= 0xFA else [])
            if not nxt or 0xFF in (w[0] for w in wpages):     # tavallinen virta: tiivis uudessa prosessissa
                raise MemoryFull(f"muisti loppui: logojen tauluja {len(wtabs)} (tilarivi {len(tpages)}, virta "
                                 f"{st.blocks} sivua, kuvat -${img_end:04x}, kernel "
                                 f"{' '.join(f'${lo:04x}-${hi:04x}' for lo, hi in ranges)})")
            pg = [nxt[0], 0]                        # $ff: vain ennen vektoreita
            wpages.append(pg)
        tlines += [f"        * = ${pg[0]:02x}00 + {pg[1]}"] + byte_lines(lab, tab)
        if lab.startswith("kn"):                    # lda (KNP),y: virta kirjoittaa vain ylätavun
            tlines += [f"        .cerror (<{lab}) != 0, \"build.py: askelsivu {lab} sivun alkuun\""]
        pg[1] += len(tab)
    assert 0x7F not in (w[0] for w in wpages)
    wpages = [w[0] for w in wpages]
    if KASVU:                                       # kv_tab, kv_real ja järjestystaulut omille sivuilleen
        ktabs = [("kv_tab", kv_init)]
        kp = [p for p in free[used + len(wpages):] if p != 0xFF][:len(ktabs)]
        if len(kp) < len(ktabs):
            raise MemoryFull(f"muisti loppui: kasvun taulut {len(ktabs)} sivua")
        KASVU["page"] = kp[0]
        for (lab, tab), pg in zip(ktabs, kp):
            tlines += [f"        * = ${pg:02x}00"] + byte_lines(lab, tab)
        wpages += kp
    znext = [(z + 1) % NPH for z in range(NPH)] + [NPH + 1, 0]
    data = ["; Generoitu: src/proto/spritet/build.py", "        .align 256"]
    for k, tab in enumerate(rtabs):                 # rakettiryhmien kuvat alkurivin mukaan (lda rimgK,y)
        data += byte_lines(f"rimg{k}", tab)
    for k in sorted(set(KY)):
        data += byte_lines(f"yn0_{k}", ytable(k, 0)) + byte_lines(f"yn1_{k}", ytable(k, 1))
    data += byte_lines("sx_tab", [x & 0xFF for x in sx]) + byte_lines("sc_tab", sc)
    (out / "data.inc").write_text("\n".join(data) + "\n")
    (out / "stream.inc").write_text("\n".join(["; Generoitu: src/proto/spritet/build.py (SID-virta)"] +
                                              st.tables(spages, znext)) + "\n")
    (out / "tila.inc").write_text("\n".join(restore(sid, compact)) + "\n")
    (out / "patch.inc").write_text("".join(f"        sta {lab}+2\n" for lab in ROLE_LABELS))
    (out / "pages.inc").write_text("\n".join(["; Generoitu: src/proto/spritet/build.py (tilarivin taulut ja SID-virran "
                                             "sivut)", "        .cerror NPH + 2 > 64"] + tlines + st.pages(spages, ">kloop", f"${tramp[0]:02x}")) + "\n")
    (out / "sprites.inc").write_text("\n".join(["; Generoitu: src/proto/spritet/build.py (spritekuvat: valot, tilarivi)"] +
                                               [x for b in imgs for x in byte_lines("", list(b))]) + "\n")
    consts_top = f"CODE_TOP = ${CODE_TOP:04x}\nWOBBLE = {int(bool(wtabs))}"
    (out / "kernel.inc").write_text((out / "kernel.inc").read_text() + consts_top + "\n")
    assert not MIDLINE, f"Y-haara ylittää sivun riveillä {sorted(MIDLINE)}"
    print(f"spritet: KY {KY}, kuvia {len(lights)} + {len(timgs)}, runko {BODY} riviä, virran kohteita {len(st.regs)}"
          f"{' (tiivis, tietue ' + str(st.rec) + ' t)' if compact else ''}, "
          f"kernel {' '.join(f'${lo:04x}-${hi:04x}' for lo, hi in ranges)}, sivuja vapaana {len(free) - used - len(wpages)}")
    left = sorted({p for p in free[used:] if p not in wpages} | varattu)   # vapaat sivut (runko: esilataus kohtauksen
                                                                          # aikana; varattu: ennätys ei koske niihin)
    runs = []
    for p in left:
        if runs and runs[-1][1] == p - 1:
            runs[-1][1] = p
        else:
            runs.append([p, p])
    print("spritet: vapaana " + (", ".join(f"${a:02x}00-${b:02x}ff" for a, b in runs) or "-"))
    (out / "vapaat.json").write_text(json.dumps(left) + "\n")   # split.py: täysin vapaa $c000-$cfff ei SPR2:een


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--tiivis"]
    apply_variant(args[2] if len(args) > 2 else "")
    try:
        main(Path(args[0]), Path(args[1]), "--tiivis" in sys.argv)
    except MemoryFull as err:                       # tavallinen virta ei mahdu: tiivis uudessa prosessissa (moduulin
        if "--tiivis" in sys.argv:                  # tila puhtaana)
            raise SystemExit(str(err))
        print(f"spritet: {err}, tiivis virta")
        os.execv(sys.executable, [sys.executable, "-I", __file__, *sys.argv[1:], "--tiivis"])
