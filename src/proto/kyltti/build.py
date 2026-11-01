"""Kyltti-rutiinin staattinen data: perspektiivitaulut, kirjaimisto kokoluokittain, siirtotaulut, tekstit ja
kyltin alla oleva taustakuva (bg_image).

  uv run --project tools/concept python src/proto/kyltti/build.py build/kyltti

Geometria: kyltti on pystysuora taso, jonka pystyviivat pysyvät pystyssä (kahden
pakopisteen perspektiivi). Silloin jokainen ruudun sarake on yhdellä syvyydellä: kyltin korkeus h(x) on
lineaarinen x:ssä, ja kyltin pituuskoordinaatti t kuvautuu ruudulle projektiivisesti
    x(t) = ((1 - t) xa + t k xb) / ((1 - t) + t k),   k = ha / hb,   h(t) = ha / (1 + t (k - 1)).
Kyltin fyysinen pituus kyltin korkeuksina saadaan polttovälistä f: Z = f / h, X = (x - cx) / h.
Tekstiavaruuden yksikkö u on 1/16 kirjainkorkeutta. Taulut u -> (x, kokoluokka, ylärivi) lasketaan tästä,
joten kirjaimen korkeus ja leveys pienenevät samassa suhteessa kuin oikea kirjain etääntyessään, ja
leveyteen tulee lisäksi oikea kulmasta johtuva kavennus.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools/gfx"))
sys.path.insert(0, str(ROOT / "tools/concept"))
sys.path.insert(0, str(HERE))

from c64fmt import Bitmap  # noqa: E402

import font  # noqa: E402

DATA = ROOT / "tools/gfx/data/hillner/lahi2"                 # lähikuva
AJO = ROOT / "tools/gfx/data/hillner/korkea2"                    # kamera-ajon kuva ja ajo.json (kyltti, kamera)
LINE0 = 75                    # rajauksen rivi 0 = rasteririvi (oletus 75 = merkkirivi 3 yscroll 3; pääbuild 72)
PIX_ASPECT = 0.936            # PAL: hires-pikselin leveys / rivin korkeus
POLE_GAP = 2                  # hires-px valopylvään oikean reunan ja tekstin alun välissä (ettei L ole pylvään päällä)


def geom_from(meta: Path, etuala: str | None = None, **style) -> dict:
    """Kyltin kaista kuvan metadatasta (avain "kyltti"): ensimmäinen ja viimeinen sisärivi suorina
    y = a + b (x - c) loppurajauksen koordinaateissa (MC-px, rajauksen rivi, kuvan viimeiset 144 riviä) ja
    kaistan x-väli. Pystyviivat pystyssä, lähin pää oikealla. Polttoväli on metadatan kameran (kamera.polttovali,
    hires-px), muuten 320. Jos metadatassa on etuala (rivit 0-143 = loppurajaus) ja se peittää sarakkeessa
    vähintään puolet kaistasta (valopylväs; johdot eivät), tekstille jää kaistan pisin peittämätön väli
    POLE_GAP-marginaalein. Tekstialue (NSPR
    spriteä) keskitetään väliin, mutta ei sen vasemman pään yli, ja näkyvät tavusarakkeet päättyvät välin
    oikeaan päähän. etuala: tiedosto metadatan etualan sijaan, False = ei etualaa (katuvalo kyltin edessä).
    style: cap (luku tai "fit"), vc, clear, bold (spriteglyfit 2 px:n vedoin kuten maalattu MC-teksti)."""
    m = json.loads(meta.read_text())
    k = m["kyltti"]
    lo = k["loppurajaus"]
    x0, x1 = k["kaista_x"]
    g = {"top": tuple(lo["kaista_yla"][c] for c in "abc"), "bot": tuple(lo["kaista_ala"][c] for c in "abc"),
         "band": (x0, x1), "meta": meta, "f": float(m.get("kamera", {}).get("polttovali", 320.0)), "cx": 160.0,
         **style}
    free = [True] * (x1 + 1 - x0)
    if "etuala" in m and etuala is not False:
        fg = np.load(meta.parent / (etuala or m["etuala"]["tiedosto"]))[:144] != 255
        free = [2 * fg[y0:y1 + 1, x].sum() < y1 + 1 - y0 for x, y0, y1 in band_rows(g)]
    runs, start = [], None                       # peittämättömät välit (a, b) mukaan lukien
    for i, f in enumerate(free + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            runs.append((x0 + start, x0 + i - 1))
            start = None
    fa, fb = max(runs, key=lambda r: r[1] - r[0])
    lo_h = 2 * fa + (POLE_GAP if fa > x0 else 0)
    hi_h = 2 * (fb + 1) - (POLE_GAP if fb < x1 else 0)
    g["text_xh"] = max(lo_h, fa + fb - NSPR * 24 // 2)     # hires: välin keskikohta - tekstialue / 2
    g["ncols"] = min(3 * NSPR, (hi_h - g["text_xh"]) // 8)
    return g


def band_rows(g: dict) -> list[tuple[int, int, int]]:
    """Kaistan sarakkeet (x, ensimmäinen, viimeinen rivi) loppurajauksessa: maalatun tekstin tyhjennys."""
    return [(x, int(math.ceil(lin(g["top"], x) - 0.5)), int(math.floor(lin(g["bot"], x) + 0.5)))
            for x in range(g["band"][0], g["band"][1] + 1)]


LAHI_NSPR = 7                 # lähikuva: hw-spritet 0-6 kyltille, 7 purkupallolle (purku.asm bsp); vieritysalue
                              # on pitkä, koska edellisessä kuvakulmassa teksti on pidemmällä alueella. Kangas
                              # $7a40-$7dbf, purun SPRB sen perässä
NSPR = LAHI_NSPR
AJO_NSPR = 8                  # kamera-ajo: kaikki 8 (kamera-ajon koodi vapauttaa spritet 6-7 kyltin ajaksi)
CAP_MAX = 0.75                # cap="fit": suurin kirjainkorkeus / kaistan korkeus
UNIT = 16                     # u-yksikköä per kirjainkorkeus
SPACING = 0.45                # kirjainväli kirjainkorkeuksina
EXT = 1.5                     # leveä groteski kuten 1960-luvun kyltissä: kirjainleveys x 1,5 (kaukopään
                              # kulma kaventaa kirjaimet 0,42-kertaisiksi, joten kapea kirjain ei erottuisi)
GUTTER = 16                   # x tallennetaan + GUTTER (vasemman reunan yli menevät kirjaimet piirretään kaatoalueelle);
                              # build kasvattaa 8:n välein, jos kirjain alkaa yli 16 px kankaan vasemmalta puolelta

CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÅ0123456789.,:!'-+/&"


# Kyltin skrolleri kertoo tarinan: LOHJAN RAUTA lähtee vierimään, perässä tarina, lopuksi palaa LOHJAN RAUTA ja tulee
# moukari. Teksti luetaan tekstit.yaml:sta (repon juuri): hillner-eka ajo-kyltille LOHJAN RAUTAn
# perään (LOHJAN RAUTA pidetään AJO_PITO kehystä, sitten teksti vierii leikkaukseen asti; moduuli $4400-$63ff,
# SAA VÄISTYÄ... mahtuu), hillner-toka lähikuvassa yhtenä vierityksenä, sitten LOHJAN RAUTA syttyy pitona moukariin
# asti. Pituudet: buildin tulostus "mahtuu noin N merkkiä". Tekstit ja käsikirjoitus kuvittain: select(). Dataan
# päätyvät vain teksteissä käytetyt merkit (GSET).
LOHJA_MIN = 60                # LOHJAN RAUTA lähikuvassa ennen purkua, kehyksiä (syttyy välkkeellä noin 50:ssä)


def tarina() -> list[str]:
    """Kyltin skrollerin teksti tekstit.yaml:sta isoin kirjaimin (kyltin kirjaimisto on versaali): [ajo-kyltin osa
    (hillner-eka), lähikuvan osa (hillner-toka)]."""
    sys.path.insert(0, str(ROOT / "tools"))
    import tekstit
    return [tekstit.lue("hillner-eka").upper(), tekstit.lue("hillner-toka").upper()]


SHOW, SCROLL, FALL = 0, 1, 2
SCROLL_SPEED = 0x0320         # u-yksikköä per kehys 8.8: mitoitusnopeus ("mahtuu noin N merkkiä")
SCROLL_MIN = 0x0315           # lähikuva: vähintään tämä, nopeammin vain jos tarina ei muuten mahdu ennen LOHJAN
                              # RAUTAa (LOHJA_MIN) ja purkua (lahi_speed); lyhyt tarina jättää LOHJAN RAUTAn pidemmäksi
SCROLL_MAX = 0x03c0           # vierityksen yläraja: pidempi tarina kaataa buildin (lyhennä tekstiä)
BEAT = 30                     # musiikin isku (tools/music: 100,25 BPM)
HOLD = 0xFFFF                 # viimeinen komento pysyy, kunnes kutsutaan kyltti_fall
# Käsikirjoitus: (tila, teksti, kesto kehyksinä; vierityksen kesto lasketaan tekstin pituudesta), iskuina.
FALL_HOLD = 4 * BEAT          # K_FALL_AT (script.json fall_at): viimeistä komentoa on näytetty näin kauan

# Kaksi kuvaa, sama koodi (tarinan alku isossa kuvassa, sitten leikkaus lähikuvaan):
#   ajo  = kamera-ajon loppukuva (hillner/korkea2, rivit 240-383): LOHJAN RAUTA ja hillner-eka, vierii leikkaukseen
#   lahi = matala lähikuva (täysvärikuva, rivit 96-239): hillner-toka ja LOHJAN RAUTA, pito purkuun
VARIANT = "lahi"


def select(variant: str) -> None:
    """Valitse kuva, kyltin geometria, tekstit ja käsikirjoitus (moduulin data); koodi on sama."""
    global VARIANT, TALL, TEXTS, GSET, SCRIPT, GEOM, NSPR
    VARIANT = variant
    if variant == "ajo":
        NSPR = AJO_NSPR
        # kamera-ajon kuva ilman maalattua tekstiä; jos sitä ei ole, maalattu teksti tyhjennetään kaistalta
        TALL = AJO / "taysvari.npy" if (AJO / "taysvari.npy").exists() else AJO / "kuva.npy"
        # LOHJAN RAUTA näkyy kuten maalattuna ja vierii pois, tarina tulee perässä; teksti ei ole valopylvään
        # päällä ja on kaistan yläosassa (vc 0,4). Kirjainkorkeus (cap="fit") on suurin, jolla pidettävä nimi
        # mahtuu näkyvään alueeseen (teksti täyttää kaistan).
        parts = ["LOHJAN RAUTA", tarina()[0]]                          # osa vierii loppuunsa (center),
        TEXTS = {"t_ajo": " ".join(parts)}                              # välit buildissa
        SCRIPT = ("AUTO", "t_ajo", parts)                               # ajastus: auto_plan()
        # katuvalo on oma kerros kyltin edessä (teksti sen takana, hillner/build.py katuvalo, glue_ajo.asm $D01B),
        # joten teksti käyttää koko kaistan
        # bold: spriteglyfien pystyvedot 2 px:n levyisiä kuten maalatussa MC-tekstissä (export_first käyttää
        # ohuita glyfejä MC-pareina), joten paksuus ei muutu vaihdossa ja vieritys etenee 1 px:n askelin
        # dy: teksti 1 px alemmas, ettei se kosketa kyltin yläreunaa
        GEOM = geom_from(AJO / "ajo.json", etuala=False, cap="fit", vc=0.4, dy=1, bold=True,
                         clear=TALL.name == "kuva.npy")
    else:
        NSPR = LAHI_NSPR
        TALL = DATA / "taysvari.npy"  # täysvärikuva, $D021 = 0
        # kirjainkorkeus enintään 0,52 kaistasta, pienempi jos valomainos (LOHJAN RAUTA) ei mahdu kankaalle
        # (lahi2:lla 0,52 leikkaisi L:n: "OHJAN RAUTA"). clear: lahi2:n kaistalla on maalattu oranssi lauta,
        # skrollerin tausta on musta; bg.* on levyn fin (tools/gfx/d64.py)
        GEOM = geom_from(DATA / "metadata.json", cap="fit", cap_max=0.52, clear=True)
        # lähikuvaa on TIM_CUE_LAHIKUVA - TIM_CUE_PURKU (960 kehystä): tarinan vieritys ja LOHJAN RAUTA ennen
        # purkua (build tarkistaa); LOHJAN RAUTA jatkuu purun laajassa kuvassa moukarin iskuun asti
        TEXTS = {"t_lohja": "LOHJAN RAUTA", "t_tarina": tarina()[1]}
        SCRIPT = [(SCROLL, "t_tarina", 0), (SHOW, "t_lohja", HOLD)]
    GSET = " " + "".join(sorted(set("".join(TEXTS.values())) - {" "}))


def bold(g: np.ndarray) -> np.ndarray:
    """Glyfi 1 px leveämmäksi oikealle: jokainen pikseli myös oikeaan naapuriinsa (2 px:n pystyvedot)."""
    out = np.zeros((g.shape[0], g.shape[1] + 1), bool)
    out[:, :-1] |= g.astype(bool)
    out[:, 1:] |= g.astype(bool)
    return out


def lin(p, x):
    a, b, c = p
    return a + b * (x - c)


select("lahi")


class Sign:
    def __init__(self, g: dict):
        self.g = g
        self.xa = g["text_xh"]                     # hires
        self.xb = self.xa + NSPR * 24
        self.ha = self.height(self.xa)
        self.hb = self.height(self.xb)
        self.k = self.ha / self.hb
        f, cx = g["f"], g["cx"]
        Xa, Za = (self.xa - cx) / self.ha, f / self.ha
        Xb, Zb = (self.xb - cx) / self.hb, f / self.hb
        self.L = math.hypot(Xb - Xa, Zb - Za)       # kyltin pituus kyltin korkeuksina
        self.NU = int(round(self.L / g["cap"] * UNIT))

    def height(self, xh: float) -> float:
        x = xh / 2
        return lin(self.g["bot"], x) - lin(self.g["top"], x) + 1

    def mid(self, xh: float) -> float:
        x = xh / 2
        vc = self.g.get("vc", 0.5)                  # kirjainrivin keskikohta kaistan korkeudesta (0 = ylä)
        return lin(self.g["top"], x) + vc * (lin(self.g["bot"], x) - lin(self.g["top"], x)) + self.g.get("dy", 0)

    def x_of_t(self, t: float) -> float:
        return ((1 - t) * self.xa + t * self.k * self.xb) / ((1 - t) + t * self.k)

    def h_of_t(self, t: float) -> float:
        return self.ha / (1 + t * (self.k - 1))

    def kx_of_t(self, t: float) -> float:
        """Vaakaskaala kirjainkorkeuteen nähden: px per fyysinen pituus / px per fyysinen korkeus."""
        e = 1e-4
        dxdt = (self.x_of_t(t + e) - self.x_of_t(t - e)) / (2 * e)
        return dxdt / (self.L * self.h_of_t(t)) / PIX_ASPECT

    def cap_of_t(self, t: float) -> float:
        return self.g["cap"] * self.h_of_t(t)


AJO_NOPEUS = 0x0175            # vierityksen nopeus 8.8 u/kehys; vieritys kestää kehyksiä eikä iskuja, joten nopeus on
                               # tarkka; loppu ikkunasta: viimeinen osa vierii pois
AJO_ETUMATKA = 4               # ensimmäinen spriteasento kehyksiä vierityksessä (noin 2 px kuten vierityksen askel)
AJO_EKA, K_PITO = None, 0      # auto_plan: maalattu pito (export_first) ja sen kesto (glue_ajo.asm)
AJO_PITO = 5                   # LOHJAN RAUTA paikallaan ennen vieritystä, kehyksiä (ei turhaa odotusta: vieritys alkaa
                               # 0,1 s:n kuluttua)
AUTO_HOLD = 0                  # pidot iskuina osien välissä ja viimeisen osan keskellä: 0, skrolleri ei pysähdy
                               # (1 isku pysäyttäisi skrollerin lähes sekunniksi)
VIS_U = 0                      # näkyvän alueen loppu tekstiavaruudessa (build)


def timing_symbols() -> dict:
    """Leikkauskohdat src/gen/timing.inc:stä; puuttuvat src/scene/hil.inc:n .weak-oletuksista."""
    import re
    syms = {}
    for f in (ROOT / "src/scene/hil.inc", ROOT / "src/gen/timing.inc"):     # jälkimmäinen voittaa
        if f.exists():
            for m in re.finditer(r"^(TIM_\w+)\s*=\s*(\d+)", f.read_text(), re.M):
                syms[m.group(1)] = int(m.group(2))
    return syms


def auto_plan(center, name: str, parts: list[str]) -> list[tuple[int, str, int, int, int]]:
    """Ajo-kyltti mahtuu aikajanan rajoihin: kyltti alkaa TIM_CUE_AJOKYLTTI:ssä ja leikkaus lähikuvaan on
    TIM_CUE_LAHIKUVA:ssa. Ensimmäinen osa paikallaan AJO_PITO kehystä, sitten vieritys nopeudella AJO_NOPEUS
    seuraavan keskelle ja pito AUTO_HOLD iskua; viimeinen osa pito AUTO_HOLD iskua ja vierii sitten samalla
    nopeudella vasemmalle leikkaukseen asti (lause jatkuu lähikuvassa; ei paikallaan seisovaa loppua).
    Jos aika ei riitä, build pysähtyy."""
    syms = timing_symbols()
    window = syms["TIM_CUE_LAHIKUVA"] - syms["TIM_CUE_AJOKYLTTI"]
    dist = [center(name, b) - center(name, a) for a, b in zip(parts, parts[1:])]
    moves = [-(-d * 256 // AJO_NOPEUS) for d in dist]               # kehyksiä, ylöspäin
    holds = [0] + [AUTO_HOLD * BEAT] * (len(parts) - 1)            # ensimmäinen pito AJO_PITO (maalattu)
    need = sum(holds) + sum(moves)
    if need > window:
        raise SystemExit(f"kyltti ajo: TIM_CUE_LAHIKUVA - TIM_CUE_AJOKYLTTI = {window} kehystä, tarvitaan "
                         f"{need}: lyhennä tekstit.yaml:n hillner-eka")
    # Ensimmäinen pito on maalattu teksti (glue_ajo.asm ajo_go odottaa K_PITO kehystä): spriteteksti tulee näkyviin
    # vasta liikkeessä, joten MC-maalauksen ja spritetekstin 1 px:n ero ei näy hyppynä paikallaan. Ensimmäinen
    # näkyvä spriteasento on jo AJO_ETUMATKA kehystä vierityksessä.
    global AJO_EKA, K_PITO
    plan = []
    end = 0                                                         # edellisen vierityksen loppu, 8.8 u
    for i, part in enumerate(parts):
        s0 = center(name, part)
        if i == 0:
            AJO_EKA, K_PITO = (SCROLL, name, AJO_PITO, s0, 0), AJO_PITO
            # ensimmäinen kuva (ajo_on) on tila s0 + d0; ajo_go esivierittää tilan K_RATE - 1 kehystä eteen
            # (kyltti.asm k_xroll), joten kuva näkyy samalla viiveellä kuin muut (K_LOCK, K_XLIIKE)
            d0 = AJO_ETUMATKA * AJO_NOPEUS // 256
            plan.append((SCROLL, name, moves[i] - AJO_ETUMATKA, s0 + d0, AJO_NOPEUS))
            end = (s0 + d0) * 256 + (moves[i] - AJO_ETUMATKA) * AJO_NOPEUS
            continue
        if holds[i]:
            plan.append((SCROLL, name, holds[i], s0, 0))
            start = s0
        else:                                                       # ilman pitoa vieritys jatkuu edellisen lopusta:
            start = end >> 8                                        # askel 0..1 kehyksen vieritys, ei taaksepäin
        if i == len(parts) - 1:
            plan.append((SCROLL, name, HOLD, start, AJO_NOPEUS))
            break
        n = -(-(center(name, parts[i + 1]) - start) * 256 // AJO_NOPEUS)
        plan.append((SCROLL, name, n, start, AJO_NOPEUS))
        end = start * 256 + n * AJO_NOPEUS
    off = window - need
    per = dist[-1] / max(1, len(parts[-1]))                         # u per merkki (osien välit mukana)
    print(f"  ajo-kyltti: ikkuna {window} kehystä: vieritys ${AJO_NOPEUS:04x} {moves} kehystä, pidot {holds}, "
          f"viimeinen osa vierii pois {off} kehystä ({off * AJO_NOPEUS // 256} u, näkyvä alue {VIS_U} u) ennen "
          f"leikkausta; rivi 1 mahtuisi noin {int((window - sum(holds)) * AJO_NOPEUS / 256 / per)} merkkiä")
    return plan


def lahi_window() -> int:
    """Lähikuvan kylttiaika kehyksinä: leikkauksesta purkuun, kyltti alkaa pyyhkäisyn jälkeen (glue_lahi.asm
    FADE_N = 24 + 2)."""
    syms = timing_symbols()
    return syms["TIM_CUE_PURKU"] - syms["TIM_CUE_LAHIKUVA"] - 26


LAHI_ALKU = 0                 # lähikuvan tarina alkaa näin monta u valmiiksi kyltillä (lahi_speed)


def lahi_speed(tlen: dict, NU: int) -> None:
    """Lähikuvan vieritys mahtuu lahi_window()-aikaan (LOHJAN RAUTA LOHJA_MIN kehystä, ehtii syttyä): ensin
    nopeudella SCROLL_MIN niin, että tarina alkaa enintään puolet kyltistä valmiiksi näkyvissä (LAHI_ALKU: lause
    jatkuu ajo-kyltistä, joten alku saa olla jo kyltillä pyyhkäisyn jälkeen), ja vasta sitten nopeammin."""
    global SCROLL_SPEED, LAHI_ALKU
    room = lahi_window() - LOHJA_MIN - sum(r[2] for r in SCRIPT if r[0] == SHOW and r[2] != HOLD)
    scroll = [r[1] for r in SCRIPT if r[0] == SCROLL]
    dist = sum(tlen[n] + NU for n in scroll)
    frames = lambda alku, spd: ((dist - alku) * 256 + spd - 1) // spd + len(scroll)
    spd, alku = SCROLL_MIN, 0
    while frames(alku, spd) > room and alku < NU // 2:
        alku += 1
    while frames(alku, spd) > room:
        spd += 1
    chars = sum(len(TEXTS[n]) for n in scroll)
    per = sum(tlen[n] for n in scroll) / max(1, chars)               # u per merkki tässä tekstissä
    fit = int((room * SCROLL_MIN // 256 - len(scroll) + NU // 2 - NU * len(scroll)) / per)
    print(f"  lähikuva: tarina {chars} merkkiä, nopeudella ${SCROLL_MIN:04x} mahtuu noin {fit} merkkiä "
          f"(lähikuvaa {lahi_window()} kehystä, LOHJAN RAUTA vähintään {LOHJA_MIN}); alku {alku} u valmiiksi "
          f"kyltillä (näkyvä alue {NU} u), vieritys ${spd:04x}")
    if spd > SCROLL_MAX:
        raise SystemExit(f"kyltti lahi: tarina {chars} merkkiä vaatisi vierityksen ${spd:04x} > ${SCROLL_MAX:04x} "
                         f"(luettava); nopeudella ${SCROLL_MIN:04x} mahtuu noin {fit} merkkiä: lyhennä "
                         f"tekstit.yaml:n hillner-toka")
    SCROLL_SPEED, LAHI_ALKU = spd, alku


def make_plan(tlen: dict, NU: int, adv: dict) -> list[tuple[int, str, int, int, int]]:
    """Käsikirjoitus koneen muotoon: (tila, teksti, kesto, alku-s, nopeus 8.8). Rivit:
    (SHOW, teksti, kesto): valomainos keskellä; (SCROLL, teksti, 0): vierii oikealta vasemmalle pois;
    ("STILL", teksti, osa, kesto): osa keskellä paikallaan (vieritys nopeudella 0, ei välkettä);
    ("MOVE", teksti, osasta, osaan, nopeus): vierii osan keskeltä toisen osan keskelle."""
    def center(name, sub):
        txt = TEXTS[name]
        i = txt.index(sub)
        u0 = sum(adv[c] for c in txt[:i])
        w = sum(adv[c] for c in sub)
        vis = VIS_U if SCRIPT[0] == "AUTO" else NU
        return u0 + ((w - vis) // 2 if w <= vis else w - vis)      # pitkä osa: loppu näkyvän alueen oikeaan reunaan
    if SCRIPT[0] == "AUTO":
        return auto_plan(center, SCRIPT[1], SCRIPT[2])
    plan = []
    for row in SCRIPT:
        kind, name = row[0], row[1]
        if kind == SHOW:
            plan.append((SHOW, name, row[2], (tlen[name] - NU) // 2, 0))
        elif kind == SCROLL:
            alku = LAHI_ALKU if row is SCRIPT[0] else 0                # vain ensimmäinen vieritys alkaa kyltiltä
            dur = ((tlen[name] + NU - alku) * 256 + SCROLL_SPEED - 1) // SCROLL_SPEED + 1
            plan.append((SCROLL, name, dur, alku - NU, SCROLL_SPEED))
        elif kind == "STILL":
            plan.append((SCROLL, name, row[3], center(name, row[2]), 0))
        else:                                       # MOVE
            sa, sb, spd = center(name, row[2]), center(name, row[3]), row[4]
            plan.append((SCROLL, name, max(1, ((sb - sa) * 256) // spd), sa, spd))
    return plan


SPRCOL = [1] * 8                # kyltti.asm k_sprcol


def export_first(out, first, adv, UM, NU, xrel, cidx, trows, sizes, glyphs, xa, row0) -> None:
    """Käsikirjoituksen ensimmäinen tila (ajo-kuvassa LOHJAN RAUTA paikallaan) kuvana kamera-ajon
    bittikarttaan: sama asettelu kuin kyltti.asm piirtää, kuvan rivi 0 = rasteririvi LINE0.
    lohja_text_hires.npy 144 x 320 (hires-asettelu), lohja_text_mc.npy 144 x 320 (MC-paksuus hires-leveydellä:
    maalattu ja monivärinen spriteteksti) ja lohja_text.npy 144 x 160 (MC: pikseli palaa,
    jos jompikumpi sen hires-pikseleistä palaa); 255 = läpinäkyvä, muuten C64-väri (spriten väri)."""
    _, name, _, s, _ = first
    part = SCRIPT[2][0] if SCRIPT[0] == "AUTO" else TEXTS[name]   # vain ensimmäinen osa (LOHJAN RAUTA)
    i0 = TEXTS[name].index(part)
    hires = np.full((144, 320), 255, np.uint8)
    u0 = 0
    for i, ch in enumerate(TEXTS[name]):
        a = adv[ch]
        idx = u0 - s + UM
        if idx > NU + UM:
            break
        if u0 + a - s >= 0 and ch != " ":
            x = int(xrel[idx])
            j = idx + a // 2
            size = sizes[int(cidx[j])]
            top = int(trows[j]) + row0                 # kuvan rivi
            g = glyphs[(size, ch)]
            for yy, xx in zip(*np.nonzero(g)):
                if 0 <= x + xx < NCOLS * 8 and i0 <= i < i0 + len(part):
                    hires[top + yy, xa + x + xx] = SPRCOL[(x + xx) // 24]
        u0 += a
    mc = np.full((144, 160), 255, np.uint8)
    for x in range(160):
        pair = hires[:, 2 * x:2 * x + 2]
        on = (pair != 255).any(axis=1)
        mc[on, x] = pair[on].min(axis=1)                # valkoinen (1) voittaa, jos värit eroavat
    np.save(out / "lohja_text_hires.npy", hires)
    np.save(out / "lohja_text.npy", mc)
    np.save(out / "lohja_text_mc.npy", mc.repeat(2, axis=1))  # hires-leveys, MC-paksuus: mitä ruudulla näkyy
    xs = np.nonzero((hires != 255).any(0))[0]                  # kirjainten hires-välit (MC-viitteessä O ja H koskettavat)
    boxes = [[int(g[0]), int(g[-1])] for g in np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1)]
    (out / "lohja_text_kirjaimet.json").write_text(json.dumps({"_doc": "LOHJAN RAUTA: kirjainten hires-x-välit "
                                                               "(mukaan lukien) viitteisiin lohja_text_hires.npy ja "
                                                               "lohja_text_mc.npy", "kirjaimet": boxes}) + "\n")


def advances() -> dict:
    """Merkkien etenemät u-yksikköinä (kirjainleveys x EXT + väli)."""
    return {ch: int(round((max(font.WIDTH[ch] * EXT, 0.16) + SPACING) * UNIT)) for ch in CHARS}


def vis_u(sg: Sign, ncols: int) -> int:
    """Suurin kirjaimen alku u, joka on vielä näkyvissä (x < ncols tavusaraketta kankaan alusta)."""
    u = sg.NU
    while round(sg.x_of_t(u / sg.NU) - sg.xa) >= ncols * 8:
        u -= 1
    while round(sg.x_of_t((u + 1) / sg.NU) - sg.xa) < ncols * 8:
        u += 1
    return u


def fit_cap(g: dict, parts: list[str]) -> dict:
    """cap="fit": suurin kirjainkorkeus (cap_max:sta, oletus CAP_MAX, 0,01:n välein alas), jolla jokainen pidettävä
    osa mahtuu näkyvään alueeseen puolen kirjaimen marginaalilla."""
    adv = advances()
    w = max(sum(adv[c] for c in pt) for pt in parts)
    cap = g.get("cap_max", CAP_MAX)
    while True:
        sg = Sign({**g, "cap": cap})
        if w <= vis_u(sg, g["ncols"]) - UNIT // 2:
            return {**g, "cap": cap}
        cap = round(cap - 0.01, 2)
        assert cap > 0.3, "kyltti: teksti ei mahdu kaistalle"


RAKO = {"ajo"}                # nauhalohkot sivutasattujen taulujen rakoihin (ajo-kyltin muisti $4400-$63ff, K_XLIIKE)
XLIIKE = {"lahi", "ajo"}             # kyltti.asm K_XLIIKE: 50 Hz:n vieritys spritejen X:llä piirtojen välissä


def fx_table(sg: Sign) -> list[int]:
    """k_fx (K_XLIIKE): px per u spriten keskisarakkeessa x 256. Tekstin kohta u näkyy x(u - s):ssä, joten s:n
    kasvaessa d:llä kirjain siirtyy noin d dx/du vasemmalle (perspektiivi: lähipää nopeammin)."""
    out = []
    for i in range(NSPR):
        xc, lo, hi = sg.xa + 24 * i + 12, 0.0, 1.0
        for _ in range(40):                                   # x(t) kasvaa t:n mukana
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if sg.x_of_t(mid) < xc else (lo, mid)
        e = 1e-4
        f = (sg.x_of_t(lo + e) - sg.x_of_t(lo - e)) / (2 * e) / sg.NU
        assert 0 < f < 1, ("k_fx", i, f)
        out.append(int(round(f * 256)))
    return out


def build(out: Path) -> None:
    global NCOLS, GEOM
    out.mkdir(parents=True, exist_ok=True)
    if GEOM["cap"] == "fit":                       # pidettävät osat: ajo-kyltin nimet, lähikuvan valomainokset
        GEOM = fit_cap(GEOM, SCRIPT[2][:1] if SCRIPT[0] == "AUTO" else [TEXTS[r[1]] for r in SCRIPT if r[0] == SHOW])
    sg = Sign(GEOM)
    NCOLS = sg.g["ncols"]                          # näkyvät tavusarakkeet kankaan alusta
    NU = sg.NU
    adv = advances()
    advmax = max(adv.values())
    UM = advmax                                    # tauluissa u = -UM .. NU + advmax
    us = np.arange(-UM, NU + advmax + 1)
    ts = us / NU
    xs = np.array([sg.x_of_t(t) for t in ts])
    caps = np.array([sg.cap_of_t(t) for t in ts])
    lo_t, hi_t = 0.0, 1.0
    sizes = sorted({int(round(sg.cap_of_t(t))) for t in np.linspace(lo_t, hi_t, 200)})
    cls = np.clip(np.round(caps).astype(int), sizes[0], sizes[-1])
    cidx = np.array([sizes.index(s) for s in cls])
    # kokoluokan vaakaskaala: luokan keskikohdan t
    kx = {}
    for s in sizes:
        tt = [t for t in np.linspace(0, 1, 400) if int(round(sg.cap_of_t(t))) == s]
        tm = float(np.mean(tt)) if tt else (0.0 if s == sizes[0] else 1.0)
        kx[s] = sg.kx_of_t(tm)
    # x (+GUTTER) ja kirjaimen ylärivi kankaalla
    xrel = np.round(xs - sg.xa).astype(int)
    global GUTTER
    GUTTER = max(16, -(int(xrel.min()) // 8) * 8)  # kaatoalue K_GUTTER / 8 tavusaraketta (sarakkeet i = 0..31)
    assert xrel.max() + GUTTER < 256 and 3 * NSPR + GUTTER // 8 <= 32, (xrel.min(), xrel.max(), GUTTER)
    global VIS_U
    VIS_U = vis_u(sg, NCOLS)
    if SCRIPT[0] == "AUTO":
        # pidossa nimi on yksin ja keskellä näkyvää aluetta: naapurit kokonaan näkyvän alueen ulkopuolella
        # (edellisen loppu <= 0, seuraavan alku > VIS_U), joten väli >= (VIS_U - leveys) / 2 molemmin puolin
        name, parts = SCRIPT[1], SCRIPT[2]
        w = [sum(adv[c] for c in pt) for pt in parts]
        sp = adv[" "]
        gaps = []
        for a, b in zip(w, w[1:]):
            need = max(VIS_U - a, VIS_U - b) // 2 + 2
            gaps.append(-(-need // sp))
        TEXTS[name] = parts[0] + "".join(" " * g + pt for g, pt in zip(gaps, parts[1:]))
    tops_img = []
    for x, s in zip(xs, cls):
        m = sg.mid(x)
        tops_img.append(int(round(m - (s - 1) / 2)))
    tops_img = np.array(tops_img)
    vis = (us >= 0) & (us <= NU)
    row0 = int(tops_img[vis].min())
    trows = np.clip(tops_img - row0, 0, 63)
    bottom = int((tops_img + cls)[vis].max())

    # kirjaimisto: luokka x merkki -> nauhat (8 px leveät pystysarakkeet)
    # kirjain mahtuu etenemäänsä (väli vähintään noin 1 px) luokan kapeimmassa kohdassa: pienissä
    # koissa pyöristys leventäisi kirjaimia, joten leveys rajataan tilaan
    glyphs = {}
    worst = 9.0
    for s in sizes:
        tt = [t for t in np.linspace(0, 1, 400) if int(round(sg.cap_of_t(t))) == s] or [0.0]
        pxu = min((sg.x_of_t(t + 1e-3) - sg.x_of_t(t)) / 1e-3 / NU for t in tt)
        for ch in GSET:
            room = adv[ch] * pxu
            glyphs[(s, ch)] = g = font.glyph(ch, s, kx[s] * EXT, wmax=int(room - 0.8), stem=kx[s])
            if g.any():
                worst = min(worst, room - g.shape[1] - bool(GEOM.get("bold")))
    sglyphs = {k: bold(g) for k, g in glyphs.items()} if GEOM.get("bold") else glyphs   # spritejen glyfit
    strips = []                   # (luokka, merkki, j, tavut[s], viimeinen sytytetty sarake 0..7)
    for ci, s in enumerate(sizes):
        for ch in GSET:
            g = sglyphs[(s, ch)]
            w = g.shape[1]
            nb = (w + 7) // 8 if g.any() else 0
            for j in range(nb):
                part = np.zeros((s, 8), bool)
                seg = g[:, 8 * j:8 * j + 8]
                part[:, :seg.shape[1]] = seg
                rows = [int("".join("1" if v else "0" for v in r), 2) for r in part]
                cols = np.nonzero(part.any(0))[0]
                strips.append((ci, ch, j, rows, int(cols.max()) if len(cols) else 0))
    dic = sorted({b for st in strips for b in st[3]})
    n = len(dic)
    assert n <= 127, ("sanakirja", n)
    lofs = n                                       # siirtotaulun sivulla R kohdassa 0 ja L kohdassa n
    dindex = {b: i for i, b in enumerate(dic)}
    rtab = [(dic[i] >> sh) for sh in range(8) for i in range(n)]
    ltab = [((dic[i] << (8 - sh)) & 0xFF) if sh else 0 for sh in range(8) for i in range(n)]
    # nauhat 3:n lomitukseen: saman luokan nauhat ovat yhtä pitkiä, kolme nauhaa per lohko
    # Samansisältöiset nauhat (esim. pystyvarsi) tallennetaan kerran.
    # Lohko (3 nauhaa) on itsenäinen: RAKO-varianteissa jokainen lohko on oma pieni taulunsa (k_sbN), joka pakataan
    # sivutasattujen taulujen rakoihin muiden pienten taulujen kanssa; muuten lohkot ovat peräkkäin strips.bin:ssä.
    blob = bytearray()
    saddr, blocks = {}, []
    for ci, s in enumerate(sizes):
        group = [st for st in strips if st[0] == ci]
        uniq = list(dict.fromkeys(tuple(st[3]) for st in group))
        where = {}
        for b0 in range(0, len(uniq), 3):
            base = len(blob)
            blob += bytes(3 * s)
            for lane, rows in enumerate(uniq[b0:b0 + 3]):
                for r, v in enumerate(rows):
                    blob[base + 3 * r + lane] = dindex[v]
                where[rows] = (len(blocks), base, lane)
            blocks.append(blob[base:])
        for st in group:
            saddr[(st[0], st[1], st[2])] = where[tuple(st[3])]
    order = [(st[0], st[1], st[2]) for st in strips]
    slast = {(st[0], st[1], st[2]): st[4] for st in strips}
    assert len(sizes) <= 8 and len(GSET) <= 32, (len(sizes), len(GSET))
    # k_ctt = kokoluokka << TBITS | ylärivi: jyrkällä kaistalla ylärivi tarvitsee 6 bittiä (enintään 4 kokoluokkaa)
    tbits = 5 if int(trows.max()) < 32 else 6
    assert len(sizes) <= 1 << (8 - tbits) and int(trows.max()) < 1 << tbits, (sizes, int(trows.max()))

    # spritekohtainen Y (porras): jokainen sprite alkaa omien kirjaintensa ylimmän rivin kohdalta, ja
    # vapaa tila jaetaan ylä- ja alapuolelle (kallistuksen vara). Rivit ovat suhteessa riviin K_ROW0.
    rows_of = [set() for _ in range(NCOLS)]
    for i, u in enumerate(us):                     # jokainen alku u ja merkki kuten kyltti.asm
        if u < -UM or u > NU:
            continue
        for ch in GSET[1:]:
            j = min(i + adv[ch] // 2, len(us) - 1)
            s, top = int(cls[j]), int(trows[j])
            w = sglyphs[(s, ch)].shape[1]
            for x in range(xrel[i], xrel[i] + w):
                c = x // 8
                if 0 <= c < NCOLS:
                    rows_of[c].update(range(top, top + s))
    ys, margin = [], 21
    for k in range(NSPR):
        rs = set().union(*rows_of[3 * k:3 * k + 3]) or {0}
        span = max(rs) + 1 - min(rs)
        assert span <= 21, ("sprite", k, "rivejä", span)
        ys.append(min(rs) - (21 - span) // 2)
        margin = min(margin, (21 - span) // 2)
    spr_lines = [f"K_TMARGIN = {margin}             ; kallistuksen vara riveinä spriteä kohden",
                 f"K_RTOP = {row0 + LINE0 + min(ys)}             ; ylin rasteririvi, jolla kyltin sprite voi olla (kallistus ja putoaminen vain alaspäin)"]

    lines = [
        "; generoitu: src/proto/kyltti/build.py (älä muokkaa käsin)",
        f"K_NU = {NU}", f"K_UM = {UM}", f"K_NT = {len(us)}", f"K_NG = {len(CHARS)}",
        f"K_NCLASS = {len(sizes)}", f"K_NDIC = {n}", f"K_ROW0 = {row0 + LINE0}", f"K_NSPR = {NSPR}",
        f"K_XA = {sg.xa}", f"K_GUTTER = {GUTTER}", f"K_NCOLS = {NCOLS}", f"K_LOFS = {lofs}", f"K_TBITS = {tbits}",
        f"; kokoluokat (kirjainkorkeus px): {sizes}, vaakaskaalat {[round(kx[s], 3) for s in sizes]}",
        f"; kyltin pituus {sg.L:.2f} korkeutta, korkeus {sg.ha:.2f} -> {sg.hb:.2f} px, väli vähintään {worst:.2f} px",
        f"; kankaan rivit kuvassa {row0}..{bottom - 1}",
    ]
    consts, lines = lines, ["; generoitu: src/proto/kyltti/build.py (älä muokkaa käsin)"]


    def emit(name, vals):
        """Taulu omalla nimellään; vals = luvut tai assemblerin lausekkeet."""
        if name:
            lines.append(name)
        vals = [v if isinstance(v, str) else f"${v & 0xFF:02x}" for v in vals]
        for i in range(0, len(vals), 16):
            lines.append("        .byte " + ", ".join(vals[i:i + 16]))

    # pienet taulut (blobit), jotka pakataan siirtotaulusivujen rakoihin
    tlen = {name: sum(adv[c] for c in txt) for name, txt in TEXTS.items()}
    blobs = [("k_ys", ys), ("k_adv", [adv[c] for c in GSET]), ("k_adv2", [adv[c] // 2 for c in GSET]),
             ("k_rnone", [0, 0])] + ([("k_fx", fx_table(sg))] if VARIANT in XLIIKE else [])
    # glyfitietue: [3 (s - 1), nauhoja, (nauha lo, hi, viimeinen sytytetty sarake) x nauhoja]; tyhjä =
    # k_rnone. Osoitteet tauluissa k_reclo/k_rechi indeksillä kokoluokka << 5 | merkki.
    rlo, rhi = ["<k_rnone"] * 256, [">k_rnone"] * 256
    for ci, s in enumerate(sizes):
        for gi, ch in enumerate(GSET):
            ks = [o for o in order if o[0] == ci and o[1] == ch]
            if not ks:
                continue
            rec = [3 * (s - 1), len(ks)]
            for o in ks:
                bi, base, lane = saddr[o]
                at = f"k_sb{bi} + {lane}" if VARIANT in RAKO else f"k_stripdata + {base + lane}"
                rec += [f"<({at})", f">({at})", slast[o]]
            blobs.append((f"k_r{ci}_{gi}", rec))
            rlo[ci << 5 | gi], rhi[ci << 5 | gi] = f"<k_r{ci}_{gi}", f">k_r{ci}_{gi}"
    m = len(sizes) << 5
    blobs += [("k_reclo", rlo[:m]), ("k_rechi", rhi[:m])]
    if VARIANT in RAKO:
        blobs += [(f"k_sb{bi}", list(b)) for bi, b in enumerate(blocks)]
    for name, txt in TEXTS.items():
        blobs.append((name, [GSET.index(c) for c in txt] + [0xFF]))
    if VARIANT == "lahi":
        lahi_speed(tlen, NU)
    plan = make_plan(tlen, NU, adv)
    script = []
    for mode, name, dur, s0, spd in plan:
        script += [mode, f"<{name}", f">{name}", dur & 0xFF, dur >> 8, s0 & 0xFF, (s0 >> 8) & 0xFF,
                   spd & 0xFF, spd >> 8]
    blobs.append(("k_script", script + [0xFF]))

    # Data alkaa sivun alusta (kyltti_all.asm: data ennen koodia). Sivutasatut taulut: k_xt ja k_ctt
    # (osoitin (zp),y, Y = indeksin alatavu) ja siirtotaulut (siirto sh omalla sivullaan, R kohdassa 0 ja
    # L kohdassa K_LOFS = n). Niiden loppuraot täytetään pienillä tauluilla (suurin ensin); loput ja nauhat
    # (ei tasausta) tulevat perään.
    pages = [("k_xt", [int(v) for v in xrel + GUTTER]), ("k_ctt", [int(v) for v in (cidx << tbits) | trows])]
    pages += [("k_shtab" if sh == 0 else "", rtab[sh * n:(sh + 1) * n] + ltab[sh * n:(sh + 1) * n])
              for sh in range(8)]
    free = [(-len(v)) % 256 for _, v in pages]
    placed = [[] for _ in pages]
    rest = []
    for bl in sorted(blobs, key=lambda b: -len(b[1])):
        for i in range(len(pages)):
            if len(bl[1]) <= free[i]:
                placed[i].append(bl)
                free[i] -= len(bl[1])
                break
        else:
            rest.append(bl)
    lines.append("        .cerror (* & $ff) != 0, \"kyltin data ei ala sivun alusta\"")
    for i, ((name, vals), pl) in enumerate(zip(pages, placed)):
        emit(name, vals)
        for bname, bvals in pl:
            emit(bname, bvals)
        if i < len(pages) - 1 or VARIANT != "ajo":  # ajo: viimeisen sivun rako nauhoille (muisti $4400-$63ff,
            lines.append("        .align 256")    # SAA VÄISTYÄ...); lähikuvan koodi pysyy osoitteissaan
    if VARIANT == "ajo":
        free[-1] = 0
    if VARIANT not in RAKO:
        lines.append("k_stripdata")
        lines.append("        .binary \"strips.bin\"")
    for name, vals in rest:
        emit(name, vals)
    print(f"  rakoihin {sum(len(b[1]) for p in placed for b in p)} B, muualle {sum(len(b[1]) for b in rest)} B, "
          f"rakoja jäi {sum(free)} B")
    (out / "kyltti_data.inc").write_text("\n".join(l for l in lines if l != "") + "\n")
    durs = [dur for _, _, dur, _, _ in plan[:-1]]
    if VARIANT == "lahi":                       # LOHJAN RAUTA syttyneenä lähikuvassa ennen purkua
        window = lahi_window()
        if sum(durs) + LOHJA_MIN > window:
            raise SystemExit(f"kyltti lahi: tarina vie {sum(durs)} kehystä, lähikuvaa {window}: LOHJAN RAUTA ei "
                             f"ehdi ennen purkua (lyhennä käsikirjoituksen tarinaa)")
        print(f"  lähikuva: tarina {sum(durs)} kehystä, LOHJAN RAUTA {window - sum(durs)} kehystä ennen purkua, "
              f"vieritys ${SCROLL_SPEED:04x}")
    FALL_AT = sum(durs) + FALL_HOLD
    (out / "script.json").write_text(json.dumps({
        "segments": [[pl[0], d] for pl, d in zip(plan, durs)] + [[plan[-1][0], FALL_HOLD]],
        "fall_at": FALL_AT}) + "\n")
    spr_lines.append(f"K_FALL_AT = {FALL_AT}           ; kehys: viimeisen komennon alku + FALL_HOLD")
    spr_lines.append(f"K_PITO = {K_PITO}              ; ajo: maalatun tekstin pito ennen spritetekstiä (glue_ajo.asm)")
    spr_lines.append("K_LOCK = 1              ; kuva vaihtuu vain piirtovälin vaiheessa (kyltti.asm)")
    spr_lines.append(f"K_XLIIKE = {int(VARIANT in XLIIKE)}            ; 50 Hz:n X-siirto piirtojen välissä (kyltti.asm k_xmove)")

    (out / "kyltti.inc").write_text("\n".join(consts) + "\n" + "\n".join(spr_lines) + "\n")
    # tyhjennyslista: jokaisen kankaan sarakkeen rivit spriten omassa rivistössä
    clr = []
    for c in range(NCOLS):
        for r in sorted(rows_of[c]):
            rr = r - ys[c // 3]
            assert 0 <= rr < 21
            clr.append(f"        sta K_CANVAS + ${128 * (c // 3) + c % 3 + 3 * rr:03x},x")
    (out / "clear.inc").write_text("; generoitu: build.py, kankaan tyhjennys (X = puskurin siirto)\n"
                                   + "\n".join(clr) + "\n")
    # nauha-osoitteet ovat suhteellisia k_stripdata-alkuun: hi-tavu lisätään .asm:ssä
    (out / "strips.bin").write_bytes(bytes(blob))
    # tarkistusta varten: sama asettelu Pythonilla
    import pickle
    with open(out / "layout.pkl", "wb") as fh:
        pickle.dump({"xt": (xrel + GUTTER).tolist(), "gutter": GUTTER, "ct": cidx.tolist(), "tt": trows.tolist(), "sizes": sizes,
                     "adv": adv, "chars": CHARS, "NU": NU, "UM": UM, "line0": row0 + LINE0, "fall_at": FALL_AT,
                     "xa": sg.xa, "glyphs": {f"{s}:{c}": g for (s, c), g in sglyphs.items()},
                     "texts": TEXTS, "plan": plan, "tlen": tlen, "speed": SCROLL_SPEED,
                     "bg": bg_image(out), "line_img0": LINE0, "ys": ys, "nspr": NSPR, "ncols": NCOLS}, fh)
    if VARIANT == "ajo":
        export_first(out, AJO_EKA, adv, UM, NU, xrel, cidx, trows, sizes, glyphs, sg.xa, row0)
    # kaistan geometria muille (hillner/build.py tyhjentää maalatun tekstin samoista riveistä): yksi lähde
    (out / "kaista.json").write_text(json.dumps({
        "_doc": "kyltti build.py: kyltin kaista loppurajauksessa (kuvan viimeiset 144 riviä, MC-px). rivit: "
                "[x, ensimmäinen, viimeinen] kaistan rivi sarakkeittain (mukaan lukien); kaista_yla/ala: "
                "y = a + b (x - c); text_xh: tekstialueen alku hires-px; ncols: näkyvät tavusarakkeet",
        "lahde": str(GEOM["meta"].relative_to(ROOT)),
        "kaista_x": list(GEOM["band"]), "kaista_yla": list(GEOM["top"]), "kaista_ala": list(GEOM["bot"]),
        "text_xh": sg.xa, "ncols": NCOLS, "rivit": [list(r) for r in band_rows(GEOM)]}) + "\n")
    print(f"kyltti: NU={NU} koot={sizes} kx={[round(kx[s], 2) for s in sizes]} sanakirja={n} nauhoja={len(order)} "
          f"nauhadata={len(blob)} B, rivit {row0}..{bottom - 1}, väli min {worst:.2f} px")


def bg_image(out: Path) -> np.ndarray:
    """Kyltin alla oleva kuva: loppurajaus (clear: kaista mustaksi). Lähikuvalla tämä on levyn fin (d64.py). Rasteritaivas (255 = %00) on luovutustilan
    mukaisesti $D021 = 0 (kamera-ajon luovutus), joten se näkyy mustana. Palauttaa MC-indeksikuvan."""
    img = np.load(TALL).astype(np.uint8)
    img[img == 255] = 0
    crop = img[-144:]                           # loppurajaus: kuvan viimeiset 144 riviä
    if GEOM.get("clear"):                       # maalattu teksti tai lauta pois kaistalta
        for x, y0, y1 in band_rows(GEOM):
            crop[y0:y1 + 1, x] = 0
    bm = Bitmap(crop, bg=0)
    (out / "bg.bmp").write_bytes(bytes(bm.bmp))
    (out / "bg.scr").write_bytes(bytes(bm.scr))
    (out / "bg.col").write_bytes(bytes(bm.col))
    return bm.image


if __name__ == "__main__":
    if len(sys.argv) > 2:                      # build.py OUT [LINE0 [ajo|lahi]]: pääbuildin kuva rivillä 72
        LINE0 = int(sys.argv[2])
    select(sys.argv[3] if len(sys.argv) > 3 else "lahi")
    build(Path(sys.argv[1]))
