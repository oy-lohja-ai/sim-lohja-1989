"""Lopputekstien data (src/runko/loppu.asm): kirjaimisto 6510:n piirrettäväksi, tekstirivit ja taustan MC-bittikartta
(auringonlasku Lohjanjärven yllä).

Tekstiä ei esipiirretä: 6510 piirtää jokaisen rivin spriteihin juuri ennen kuin rivi tulee ruutuun. Kirjaimet ovat
kyltin kirjaimistosta (src/proto/kyltti/font.py, sama versaaligroteski kuin greetseissä ja levynkäännössä).
Taustan liukuvärit ovat leveitä kaistoja ja kapeita katkoviivasiirtymiä lähiluma-pareilla.
Veden välkkeet ja tähdet ovat värimuistin rooleja (%11), joita 6510 vaihtaa joka kehys.

  uv run --project tools/concept python -I tools/disk/loppu.py OUTDIR
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/proto/kyltti"))
sys.path.insert(0, str(ROOT / "tools/disk"))
sys.path.insert(0, str(ROOT / "tools/concept"))
import font  # noqa: E402
import zx0  # noqa: E402

KX = 1 / 0.936                  # PAL-pikselin muoto
SMALL, MID, BIG = 9, 13, 17     # kirjainkorkeudet (rasteririvejä); MID = keski
STRIP = 192                     # spriterivin leveys: 8 spriteä x 24 px
GAP = 1                         # kirjainväli
SPACE = {SMALL: 4, MID: 5, BIG: 7}
ROW_H = 24                      # spriterivien väli (21 riviä spriteä + 3 tyhjää)
SMALL_Y = (0, 12)               # pienen tekstin kaksi riviä spriterivissä: tasainen 12 rivin riviväli
BIG_Y = 2
MID_Y = 4                       # keskikokoinen rivi spriterivin keskellä (21 - 13) / 2
KIND_H = {"iso": BIG, "keski": MID, "pieni": SMALL}
KIND_Y = {"iso": (BIG_Y,), "keski": (MID_Y,), "pieni": SMALL_Y}

LAST_ROWS = 3
SPONSOR_PAD = 5                 # tyhjiä rivejä tukijoiden jälkeen (ks. _credits)


def _lopputekstit() -> dict:
    """tekstit.yaml:n kohta lopputekstit."""
    sys.path.insert(0, str(ROOT / "tools"))
    import tekstit
    return tekstit.lue("lopputekstit")


def _rivi(r) -> tuple:
    """tekstit.yaml:n lopputekstirivi spriteriviksi: {iso: T} -> ("iso", T), {keski: T} -> ("keski", T) (keskikoko:
    pienempi kuin iso, suurempi kuin pieni), [A, B] -> ("pieni", A, B), "T" -> ("pieni", T, "") ("" = tyhjä)."""
    if isinstance(r, dict) and len(r) == 1 and list(r)[0] in ("iso", "keski"):
        k = list(r)[0]
        return (k, r[k])
    if isinstance(r, list) and len(r) == 2 and all(isinstance(x, str) for x in r):
        return ("pieni", r[0], r[1])
    if isinstance(r, str):
        return ("pieni", r, "")
    raise SystemExit(f"loppu: tekstit.yaml lopputekstit: rivi {r!r} ei ole 'iso: T', 'keski: T', [RIVI1, RIVI2] eikä 'T'")


# Tekstit spriteriveinä: ("iso", rivi) tai ("pieni", rivi1, rivi2); "" = tyhjä. Suomeksi, ä ja ö
# kirjaimistossa. Tekstit tekstit.yaml:sta: alku, sitten _credits() (TERVEISET ja nimet, tukijalogot teksteineen) ja
# loppu. Viimeinen rivi pysähtyy ruudun keskelle loppukortiksi.
LT = _lopputekstit()
TEXT = [_rivi(r) for r in LT["alku"]]
LOPPU_ROWS = [_rivi(r) for r in LT["loppu"]] + [
    ("pieni", "", ""),
    ("pieni", "", ""),
    ("pieni", "", ""),              # loppukortti vie kolme tyhjää (layout), vaikka väleihin ei jäisi täytettä
    ("iso", "2026"),                # skrollin mitoitus: loppukortti korvaa nämä kolme riviä niin,
    ("iso", "ZOO"),                 # että sen keskikohta pysähtyy samaan kohtaan ja aiemmat rivit kulkevat ennallaan
    ("iso", "OY LOHJA AI"),
]


_GW = {}


def name_width(name: str, h: int = SMALL) -> int:
    """Nimen leveys pikseleinä kuten line_width (kirjaimisto suoraan, glyphs()-taulua ei vielä ole)."""
    for ch in name:
        if ch != " " and (ch, h) not in _GW:
            _GW[(ch, h)] = glyph(ch, h).shape[1]
    return sum(SPACE[h] if ch == " " else _GW[(ch, h)] for ch in name) + GAP * max(0, len(name) - 1)


COL_X = (32, 96, 160)           # terveisten sarakkeiden keskikohdat (192 px kolmeen)
COL_GAP = 8                     # nimien väli vähintään


def name_cols(names: list[str], h: int = SMALL) -> list[int] | None:
    """Rivin nimien vasemmat reunat: kolme nimeä sarakkeiden keskelle, jos mahtuvat väleineen, muuten (ja kahdella)
    tasavälein keskitettynä; None, jos väli jää alle COL_GAP:n."""
    ws = [name_width(n, h) for n in names]
    if len(names) == 3:
        xs = [c - w // 2 for c, w in zip(COL_X, ws)]
        if xs[0] >= 0 and xs[2] + ws[2] <= STRIP - 1 and all(xs[i + 1] >= xs[i] + ws[i] + COL_GAP for i in range(2)):
            return xs
    g = (STRIP - 1 - sum(ws)) // (len(names) + 1)
    if g < COL_GAP:
        return None
    xs, x = [], g
    for w in ws:
        xs.append(x)
        x += w + g
    return xs


def greets_rows() -> list[list[tuple]]:
    """Greetsit lopputeksteihin tekstit.yaml:n lopputeksteistä: ryhmät terveiset (henkilöt) ja muut järjestyksessä,
    versaalina (kirjaimisto). Kolme nimeä riviin riittävin välein: sarakkeet COL_X, ja jos kolme ei mahdu väleineen,
    kaksi (aakkosjärjestys säilyy); rivillä nimet "|"-erottimella (name_cols), kaksi riviä spriteriviin (tasainen 12
    rivin riviväli). Lohjanharjun nimet (greets-harju) eivät tule tänne."""
    out = []
    for key in ("terveiset", "muut"):
        names = [n.strip().upper() for n in LT[key] if n.strip()]
        lines, i = [], 0
        while i < len(names):
            k = 3 if i + 3 <= len(names) and name_cols(names[i:i + 3]) else 2 if i + 2 <= len(names) and name_cols(names[i:i + 2]) else 1
            lines.append("|".join(names[i:i + k]))
            i += k
        lines += [""] * (len(lines) % 2)
        out.append([("pieni", a, b) for a, b in zip(lines[::2], lines[1::2])])
    return out


def sponsors() -> list[tuple[str, str]]:
    """Tukijat tekstit.yaml:n lopputeksteistä: (logo, teksti)."""
    return [(t["logo"], t["teksti"]) for t in LT["tukijat"]]


def wrap(text: str, h: int = SMALL) -> list[str]:
    """Teksti riveiksi, jotka mahtuvat spriteriviin (STRIP - 1 px)."""
    gl = glyphs([("pieni", text)])
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}" if cur else w
        if cur and line_width(t, h, gl) > STRIP - 1:
            lines.append(cur)
            t = w
        cur = t
    return lines + [cur]


TUNNUKSET = ROOT / "tools/gfx/data/ryhmalogot/tukijat.npz"   # tukijoiden tunnukset C64-tarkkuudella (sponsor_emblem)


def sponsor_emblem(name: str) -> np.ndarray:
    """Tukijan tunnus hires-pikseleinä (SPR_LINES x w, bool) tiedostosta TUNNUKSET (C64-tarkkuus, mittasuhteet
    PAL-pikselin mukaan)."""
    return np.load(TUNNUKSET)[name.lower().replace(" ", "_")].astype(bool)


def sponsor_logo(name: str) -> np.ndarray:
    """Tukijan logo yksivärisenä hires-spriterivinä (SPR_LINES x 192, valkoinen kuten elokuvan lopputeksteissä):
    tunnus (sponsor_emblem) ja nimen kaksi riviä kyltin kirjaimistolla (kuten kyltit.py), keskitettynä."""
    em = sponsor_emblem(name)
    h, w = em.shape
    words = name.split()
    top, bot = [font.glyph(c, SMALL, KX) if c != " " else None for c in words[0]], \
        [font.glyph(c, SMALL, KX) if c != " " else None for c in " ".join(words[1:])]
    def strip(gl):
        return np.hstack([g if i == len(gl) - 1 else np.hstack([g, np.zeros((SMALL, GAP), bool)])
                          for i, g in enumerate(gl)])
    t0, t1 = strip(top), strip(bot)
    gap = max(3, round(w / 4))
    tw = max(t0.shape[1], t1.shape[1])
    out = np.zeros((h, 192), np.uint8)
    x = (192 - (w + gap + tw)) // 2
    out[:, x:x + w] = em
    out[0:SMALL, x + w + gap:x + w + gap + t0.shape[1]] = t0
    out[h - SMALL:h, x + w + gap:x + w + gap + t1.shape[1]] = t1
    return out


def _credits(text: list, loppu: list) -> tuple[list, set]:
    """TEXT (tekijät ja tekoälyn ilmoitus), jonka perään elokuvan tapaan TERVEISET (nimet), tukijat (logo ja teksti
    pienellä) ja loppu, ja rivit, joiden perään ei tule tyhjää (otsikko, ryhmä, logo ja teksti yhtenäisinä)."""
    i = len(text)
    out, nogap = text + [("pieni", LT["terveiset-otsikko"], "")], {i}
    for grp in greets_rows():
        nogap |= set(range(len(out), len(out) + len(grp) - 1))
        out += grp
    out += [("pieni", "", "")] * 3                 # kunnolla väliä, ettei uusi osio tule liian nopeasti
    for logo, t in sponsors():
        ls = wrap(t.upper())
        ls += [""] * (len(ls) % 2)
        nogap |= set(range(len(out), len(out) + len(ls) // 2 + 1))
        out += [("pieni", a, b) for a, b in zip(ls[::2], ls[1::2])]  # teksti ennen logoa
        out.append(("pieni", "", ""))              # väli tekstin ja logon välissä (noin 1 cm)
        out.append(("logo", logo))
        out += [("pieni", "", "")] * 3
    # tukijat luetaan ennen valojen sammumista (FADE0 = STOP - 300): KIITOS-rivi tulee yksin sammuvaan kuvaan
    nogap |= set(range(len(out) - 1, len(out) - 1 + SPONSOR_PAD))
    out += [("pieni", "", "")] * SPONSOR_PAD
    return out + loppu, nogap


END_TEXT = ("pieni", LT["loppukortti"], "")    # loppukortin viimeinen rivi (logojen alla)
# valojen sammutus (pehmeä häivytys mustaan): jokainen väri kulkee oman tummuusketjunsa läpi
# mustaan, taso l = kirkkaus (NFADE - l) / NFADE alkuperäisestä (pyöristys lähimpään), kiertävä pyyhkäisy rivi kerrallaan
CHAINS = [[1, 15, 12, 11, 0], [7, 10, 8, 2, 9, 0], [13, 5, 11, 0], [3, 14, 6, 0], [15, 12, 11, 0], [10, 8, 2, 9, 0],
          [5, 11, 0], [14, 6, 0], [12, 11, 0], [8, 2, 9, 0], [4, 6, 0], [2, 9, 0], [11, 0], [9, 0], [6, 0], [0]]
YCENTER = 162                   # viimeisen rivin yläreuna lopussa (spriten Y; ruudun rivi = Y - 50): kolmen ison rivin lohko keskellä
STOP = 1170                     # loppukortti pysähtyy keskelle tällä kehyksellä (skrolli 1 px/kehys); pito
                                # HOLD = pituus - STOP (kortti seisoo 5 s ennen häivytystä mustaan: 1440 -> pito 270,
                                # josta kortti seisoo 250 kehystä ja häipyy, kiilto liikkuu)
HOLD_MIN = 30
BASE = STOP + 30                # tähtien ja hämärän osuudet 1200 kehyksen mitoituksesta (eivät riipu pidosta)
# otsikkorivin yläreuna alussa: alareunan alla mustana (FADE_Y 0 riveillä 264-271, loppu.asm YB 272), kehys 0 = kodin
# kuva; reunat auki, joten teksti nousee alareunan alta
Y0_MIN, Y0, Y0_MAX = 264, 276, 288


def scene_len() -> int:
    """Kohtauksen pituus aikajanalta (src/gen/timing.inc)."""
    import re
    t = (ROOT / "src/gen/timing.inc").read_text()
    v = {k: int(n) for k, n in re.findall(r"^(TIM_SCENE_LOPPU_(?:START|END))\s*=\s*(\d+)", t, re.M)}
    n = v["TIM_SCENE_LOPPU_END"] - v["TIM_SCENE_LOPPU_START"]
    if n - STOP < HOLD_MIN:
        raise SystemExit(f"loppu: pituus {n}, loppukortti pysähtyy {STOP}: pito alle {HOLD_MIN} kehystä")
    return n


def rows_padded() -> tuple[list, int]:
    """Teksti tasan 1 px kehyksessä (pehmeä vieritys): matka
    ROW_H * (rivit - 1) - YCENTER + y0 = STOP. Tyhjiä rivejä lisätään tasan jokaisen rivin perään loppulohkoon asti
    (ruudulla on aina tekstiä, osioiden välit pidempiä), ja jakojäännös menee otsikon alkukorkeuteen y0 (lähellä Y0:aa)."""
    travel = STOP
    gaps = [i for i in range(len(TEXT) - LAST_ROWS) if i not in NOGAP]  # rivien perään (greets-ryhmät ja loppulohko yhtenäisiä)
    n = round((travel + YCENTER - Y0) / ROW_H) + 1        # rivejä yhteensä (otsikko lähellä Y0:aa)
    extra = n - len(TEXT)
    if extra < 0 or not gaps:
        raise SystemExit(f"loppu: teksti ei mahdu {STOP} kehykseen 1 px/kehys ({len(TEXT)} riviä)")
    out = []
    for i, r in enumerate(TEXT):
        out.append(r)
        if i in gaps:
            k = gaps.index(i)
            out += [("pieni", "", "")] * (extra // len(gaps) + (k < extra % len(gaps)))
    y0 = travel + YCENTER - ROW_H * (len(out) - 1)
    if not Y0_MIN <= y0 <= Y0_MAX:
        raise SystemExit(f"loppu: otsikon alku Y0 {y0} ei välillä {Y0_MIN}-{Y0_MAX}")
    return out, y0
LOGO_DIR = Path(os.environ.get("LOPPU_LOGOT", ROOT / "tools/gfx/data/loppu"))   # testi: LOPPU_LOGOT=hakemisto
LOGO_AT = 0xE000                # LOPPU3: logojen spriterivit ja myöhemmät rivit (ladataan lopun alussa, koti käytti $e000-)
LOGO_GAP = 10                   # rivejä logojen välissä
SPR_LINES = 21


def sprite_rows(bits: np.ndarray) -> list[bytes]:
    """Bittikuva (rivit x 192 bittiä, MC:ssä 96 paria) -> spriterivit: 8 spriteä x 63 tavua (21 riviä x 3 tavua)."""
    n = (bits.shape[0] + SPR_LINES - 1) // SPR_LINES
    pad = np.zeros((n * SPR_LINES, 192), np.uint8)
    pad[:bits.shape[0]] = bits
    out = []
    for r in range(n):
        blk = bytearray()
        for i in range(8):
            for y in range(SPR_LINES):
                row = pad[r * SPR_LINES + y, i * 24:(i + 1) * 24]
                blk += bytes(int("".join(str(int(b)) for b in row[k * 8:(k + 1) * 8]), 2) for k in range(3))
        out.append(bytes(blk))
    return out


def end_logos() -> list[dict]:
    """Loppukortti (ZOO '26 -logo, SIM LOHJA 1989 -logo kannesta, OY LOHJA AI 2026):
    logot spriteriveinä (21 rivin välein ilman rakoja). ZOO '26 hires yhdellä värillä, SIM LOHJA 1989 MC-spriteinä
    (7 = oma väri %10, 10 = $d025 %01, muu läpinäkyvä). Leveys enintään 8 spriteä (192 px / 96 MC px)."""
    def crop(a, ink):
        ys, xs = np.where(ink)
        return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1], ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    zoo = np.load(LOGO_DIR / "zoo_192.npy")
    zoo, zink = crop(zoo, zoo == 3)
    if zoo.shape[1] > 192:
        raise SystemExit(f"loppu: zoo_192.npy {zoo.shape[1]} px leveä, spritejä enintään 192 px (8 x 24)")
    zb = np.zeros((zoo.shape[0], 192), np.uint8)
    x0 = (192 - zoo.shape[1]) // 2
    zb[:, x0:x0 + zoo.shape[1]] = zink
    sim = np.load(LOGO_DIR / "simlohja.npy")
    sim, sink = crop(sim, (sim == 7) | (sim == 10))
    if sim.shape[1] > 96:
        raise SystemExit(f"loppu: simlohja.npy {sim.shape[1]} MC px leveä, MC-spritejä enintään 96")
    sb = np.zeros((sim.shape[0], 192), np.uint8)
    x0 = (96 - sim.shape[1]) // 2
    for y in range(sim.shape[0]):
        for x in range(sim.shape[1]):
            c = sim[y, x]
            # kaksivärinen, ei roskapikseleitä: väri 10 (reunojen 57 pikseliä) keltaiseksi, logo keltainen mustalla
            pair = (1, 0) if c in (7, 10) else (0, 0)
            sb[y, 2 * (x0 + x):2 * (x0 + x) + 2] = pair
    sim_ink = np.zeros((sim.shape[0], 192), bool)       # hires-maski viitteeksi (MC-pikseli = 2 hires-pikseliä)
    sim_ink[:, 2 * x0:2 * (x0 + sim.shape[1])] = np.repeat(sink, 2, axis=1)
    return [{"name": "zoo", "bits": zb, "mc": False, "col": 3, "mc1": 0, "h": zoo.shape[0], "ink": zb.astype(bool)},
            {"name": "simlohja", "bits": sb, "mc": True, "col": 7, "mc1": 10, "h": sim.shape[0], "ink": sim_ink}]


def layout() -> tuple[list, int, int, int]:
    """Rivit (dict: kind text/logo, pitch = väli seuraavaan riviin, ...) skrollin mitoituksella: rivit loppukortin
    eteen kuten rows_padded, ja loppukortin keskikohta pysähtyy siihen, missä rows_padded:n kolmen ison rivin lohkon
    keskikohta olisi. Palauttaa rivit, y0, YCENTER (viimeisen rivin yläreuna lopussa) ja loppukortin
    ensimmäisen rivin indeksin."""
    old, y0 = rows_padded()
    n = len(old)
    blk, t = [], 0
    for L in end_logos():
        rows = sprite_rows(L["bits"])
        for r, data in enumerate(rows):
            blk.append({"kind": "logo", "data": data, "mc": L["mc"], "col": L["col"], "mc1": L["mc1"], "top": t + r * SPR_LINES,
                        "cont": r > 0, "ink": L["ink"][r * SPR_LINES:(r + 1) * SPR_LINES], "name": L["name"]})
        t = max(t + L["h"] + LOGO_GAP, t + SPR_LINES * (len(rows) - 1) + ROW_H)
    blk.append({"kind": "text", "row": END_TEXT, "top": t, "cont": False, "col": 1})
    height = t + SMALL
    c_old = (YCENTER - 2 * ROW_H + BIG_Y + YCENTER + BIG_Y + BIG) / 2
    top = round(c_old - height / 2)                      # loppukortin yläreuna lopussa (spriten Y)
    gap = ROW_H - ((YCENTER - 2 * ROW_H) - top)           # viimeisestä edeltävästä rivistä kortin alkuun
    pre = [{"kind": "slogo", "data": sprite_rows(sponsor_logo(r[1]))[0], "pitch": ROW_H} if r[0] == "logo"
           else {"kind": "text", "row": r, "pitch": ROW_H} for r in old[:n - LAST_ROWS]]
    while gap < ROW_H:
        if pre[-1].get("row") != ("pieni", "", ""):
            raise SystemExit("loppu: loppukortti ei mahdu KIITOS-rivin alle")
        pre.pop()
        gap += ROW_H
    pre[-1]["pitch"] = gap
    for a, b in zip(blk, blk[1:]):
        a["pitch"] = b["top"] - a["top"]
    blk[-1]["pitch"] = ROW_H
    rows = pre + blk
    ycenter = top + blk[-1]["top"]
    travel = sum(r["pitch"] for r in rows[:-1]) - ycenter + y0
    if travel != STOP:
        raise SystemExit(f"loppu: matka {travel} != {STOP}")
    return rows, y0, ycenter, len(pre)


ROWS_EARLY = 12                 # rivit 0..11 LOPPU1:ssä (loppu.asm NSLOT: loppu_go piirtää ne ennen LOPPU3:a)
NFADE = 8                       # valojen sammutuksen tasot (loppu.asm fade_level, FADE_DT kehyksen välein)

# ---------------------------------------------------------------- tausta

W, H = 160, 200                 # MC-pikselit, kuva-alue rivit 0-199 (rasteri 51-250)
# Maisema on kodin viimeinen kuva (koti ja loppu yhtenä, ei mustaa väliä): kodin build vie sen
# tiedostoon KOTI_KUVA (loppukuva.npy (200, 320) C64-värit rasteririveiltä 51-250 ja loppukuva.json:n ikkuna). Lopun kehys 0
# on täsmälleen se (letterbox mustana), ja letterbox avautuu OPEN_N kehyksessä: yläpuolelle tumma taivas, alle järvi
# tummuu mustaan. Testi VICE-kaappauksesta (PNG 384 x 272): LOPPU_KOTIKUVA=polku.
KOTI_KUVA = Path(os.environ.get("LOPPU_KOTIKUVA", ROOT / "build/koti/demo/loppukuva.npy"))
EXT_TOP = 14                    # letterboxin yläpuolelle: siirtymä mustasta taivaan väriin näin monella rivillä
EXT_BOT = 22                    # alapuolelle: järvi tummuu mustaan näin monella rivillä
OPEN_N = 40                     # letterbox avautuu kehyksissä 1..OPEN_N
WAVE = 1                        # järven $d016-aalto (merkkiriveittäin, 38 saraketta kehyksestä 1, aalto kun letterbox auki)
WBASE = 0x18                    # $d016 kehyksellä 0: MC, 40 saraketta kuten kodissa
DUSK = (45, 110)                # taivas tummuu iltaruskosta yöhön: taustan valotasot 1-2 (kehys tai osuus pituudesta). Kodin
                                # v4-kuva on jo kahden tummumisaskeleen jälkeen: tasot 3-4 eivät muuttaisi kuvaa, vain
                                # pyyhkäisyn saumat näkyisivät; yö jatkuu tähdillä
HW_T0 = 4                       # kodin käsiala liukenee taivaaseen letterboxin auetessa kehyksestä HW_T0 niin, että se on
HW_END = 33                     # poissa kehykseen HW_END mennessä (HW_PF pikseliä kehyksessä, main): alin nimi ensin, koska
                                # lopun ensimmäinen teksti nousee alhaalta järven alareunaan kehyksellä ~30 (kodin
                                # patemathic siellä: 401 px, 14 kehyksessä, alin nimi poissa ~25)
HW_JITTER = 10                  # kirjoitussuunnassa vasemmalta oikealle, hajonta MC-pikseleinä
MAISEMA = ROOT / "tools/gfx/data/loppu/maisema.json"   # tähdet ja järven välkkeen vaiheet
TAHDET = ROOT / "tools/gfx/data/loppu/tahdet.json"     # tähdet (x, y, t, koko)
HW_1440 = ROOT / "tools/gfx/data/loppu/kasiala_1440.json"   # liuenneen käsialan pikselit ja kohdevärit (kasiala)
TAUSTA: list = []               # kodin loppukuva ilman tekijöitä MC-pikseleinä (koti_kuva), jos kodin build antaa sen
HW_ROWS = range(2, 7)           # merkkirivit, joiden ROWMASKiin tulevat valkoisen tasot aina (pyyhkäisyn ajoitus ei
                                # riipu käsialan paikasta); muualla käsialan valkoinen ei hidasta pyyhkäisyä (main)
TAHDET_POIS = {(145, 32), (100, 37), (123, 40), (48, 44), (55, 44)}   # (x, y): nämä 5 tähteä pois, jotta LOPPU1
# mahtuu (ne toisivat 2 dyn-taulua, noin 300 tavua)
STAR_AT: list = []              # tähtiryhmien syttyminen osuuksina pituudesta (tahdet.json:n t-arvot)
VALKE: list = []                # välkkeen vaiheet: kuvapikselit (y, x), background täyttää
VK_DT = 6                       # kehyksiä välkkeen vaihetta kohden
GLINT_PX = 16                   # kuvassa: tähden pikseli, rooli %11 (värimuisti = tähden väri, pois päältä = pohja)
LUMA = {0: 0, 6: 1, 9: 1, 2: 2, 11: 2, 4: 3, 8: 3, 12: 4, 14: 4, 5: 5, 10: 5, 3: 6, 15: 6, 7: 7, 13: 7, 1: 8}


def dash(x: int, y: int, d: float) -> bool:
    """Vaakasuora katkoviivadither: keskimäärin 8 MC-px:n jakso, viivan pituus d * 8, rivit porrastettuina. Viivojen
    päät huojuvat hiukan (sini), jotta solut eivät toistu 8 px:n välein (käsin asetellun näköinen, ei kohinaa)."""
    import math
    return (x * 0.125 + y * 0.375 + 0.12 * math.sin(x * 0.9 + y * 1.7)) % 1 < d


def darker(c: int, l: int) -> int:
    """Väri c valotasolla l (FADE_TAB): tummuusketjussa lähin, jonka luma <= alkuperäinen (NFADE - l) / NFADE (tummat
    eivät katoa heti). Hämärän tasoilla 1..len(DUSK) väri ei mene mustaksi (kodin v4-kuva on jo tummennettu: harmaa 11
    jäisi mustiksi raidoiksi), vasta valojen sammuessa."""
    chain = next(ch for ch in CHAINS if ch[0] == c)
    e = next(e for e in chain if LUMA[e] <= LUMA[c] * (NFADE - l) / NFADE + 0.5)
    return chain[-2] if e == 0 and c != 0 and l <= len(DUSK) else e


def koti_kuva() -> tuple[np.ndarray, int, int, int]:
    """Kodin viimeinen kuva MC-pikseleinä (200, 160), ikkunan kuvarivit wy0..wy1-1 (letterbox mustaksi) ja järven
    ensimmäinen kuvarivi (Liessaaren alla)."""
    if not KOTI_KUVA.exists():
        raise SystemExit(f"loppu: {KOTI_KUVA} puuttuu (kodin build: make -C src/proto/koti demo)")
    if KOTI_KUVA.suffix == ".npy":
        img = np.load(KOTI_KUVA).astype(np.uint8)
        meta = json.loads(KOTI_KUVA.with_suffix(".json").read_text(encoding="utf-8"))
        r0, r1 = meta["ikkuna_rasteririvit"]
        wy0, wy1 = r0 - 51, r1 - 51 + 1
        lake = max(e["rasteririvi"] for e in meta["liessaari"]) + 21 - 51
    else:
        from concept import c64
        from PIL import Image
        rgb = np.asarray(Image.open(KOTI_KUVA).convert("RGB")).astype(int)[35:235, 32:352]
        pal = c64.palette().astype(int)
        img = ((rgb[:, :, None, :] - pal[None, None]) ** 2).sum(3).argmin(2).astype(np.uint8)
        lit = np.where((img != 0).sum(1) > 200)[0]
        wy0, wy1 = int(lit.min()), int(lit.max()) + 1
        lake = (wy0 + wy1) // 2
    out = img[:, ::2].copy()
    out[:wy0] = 0
    out[wy1:] = 0
    tausta = KOTI_KUVA.with_name("loppukuva_tausta.npy")     # sama ilman tekijöitä (kodin build): käsiala liukenee
    if KOTI_KUVA.suffix == ".npy" and tausta.exists():         # oikeaan taustaan, myös järvellä
        TAUSTA[:] = [np.load(tausta).astype(np.uint8)[:, ::2]]
    return out, wy0, wy1, lake


def fit_cells(img: np.ndarray) -> None:
    """Solussa enintään 3 väriä mustan lisäksi: harvinaisin ylimääräinen väri lähimpään (luma) jäljelle jäävään."""
    for cy in range(25):
        for cx in range(40):
            cell = img[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
            while True:
                cs, n = np.unique(cell[cell != 0], return_counts=True)
                if len(cs) <= 3:
                    break
                drop = int(cs[n.argmin()])
                keep = [int(c) for c in cs if c != drop]
                cell[cell == drop] = min(keep, key=lambda c: abs(LUMA[c] - LUMA[drop]))


def background() -> tuple[np.ndarray, dict, list, int, int]:
    """Kodin viimeinen kuva ja letterboxin taakse jatkeet (avautuvat lopun alussa), järveen välkkeet (%11)."""
    img, wy0, wy1, lake = koti_kuva()
    rng = np.random.default_rng(1959)
    fit_cells(img)

    def major(y):
        v, n = np.unique(img[y], return_counts=True)
        return int(v[n.argmax()])
    ctop, cbot = major(wy0), major(wy1 - 1)
    for y in range(wy0 - EXT_TOP, wy0):                    # taivas jatkuu ylös ja tummuu mustaan
        for x in range(W):
            img[y, x] = ctop if dash(x, y, (y - (wy0 - EXT_TOP) + 1) / (EXT_TOP + 1)) else 0
    for y in range(wy1, min(H, wy1 + EXT_BOT)):              # järvi jatkuu alas ja tummuu mustaan
        for x in range(W):
            img[y, x] = cbot if dash(x, y, 1 - (y - wy1 + 1) / (EXT_BOT + 1)) else 0
    # elävä maisema datasta (MAISEMA, ikkunan rivit -> kuvarivit + wy0): välkkeen vaiheet ja tähdet,
    # molemmat roolissa %11 soluissa, joissa on enintään 2 väriä mustan lisäksi (muut jäävät pois, kerrotaan buildissa)
    m = json.loads(MAISEMA.read_text(encoding="utf-8"))
    forced, dyn, dropped = {}, [], []

    def free(cy, cx):
        cell = img[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
        cols = sorted(set(np.unique(cell).tolist()) - {0, GLINT_PX})
        return cols if len(cols) <= 2 else None
    # välke: vaiheen p viivojen pikselit (bittikartassa vaihe kerrallaan, valke_entries); solun %11 = viivojen väri
    phases = []
    vcol: dict = {}
    for ph in m["valke_vaiheet"]:
        px = []
        for ln in ph:
            y = ln["rivi"] + wy0
            for x in range(ln["x0"], ln["x1"] + 1):
                if 0 <= x < W and 0 <= y < H:
                    px.append((y, x))
                    vcol.setdefault((y // 8, x // 4), []).append(ln["vari"])
        phases.append(px)
    vcell = {}
    for (cy, cx), cs in vcol.items():
        cols = free(cy, cx)
        if cols is None:
            dropped.append(("välke", cy, cx))
            continue
        while len(cols) < 2:
            cols.append(cols[0] if cols else 0)
        c11 = max(set(cs), key=cs.count)
        forced[(cy, cx)] = (cols[0], cols[1], c11)
        vcell[(cy, cx)] = c11
    VALKE[:] = [[(y, x) for y, x in px if (y // 8, x // 4) in vcell] for px in phases]
    # tähdet (tahdet.json: x MC-px, y kuvarivi, t osuus pituudesta, koko): ryhmä = sama t, risti = keskus
    # ja neljä sakaraa; pois päältä pohjan väri
    stars = json.loads(TAHDET.read_text(encoding="utf-8"))
    STAR_AT[:] = sorted({t["t"] for t in stars})
    for t in stars:
        if (t["x"], t["y"]) in TAHDET_POIS:
            continue
        g = STAR_AT.index(t["t"])
        y0, x0 = t["y"], t["x"]
        pix = [(y0, x0)] + ([(y0, x0 - 1), (y0, x0 + 1), (y0 - 1, x0), (y0 + 1, x0)] if t["koko"] == 2 else [])
        cells = {(y // 8, x // 4) for y, x in pix}
        ok = all((c not in forced or forced[c][3:] == (("tähti", g),)) and free(*c) is not None for c in cells)
        if ok and len({int(img[y, x]) for y, x in pix}) != 1:
            ok = False
        if not ok:
            dropped.append(("tähti", t["x"], t["y"]))
            continue
        base = int(img[pix[0]])
        on = [base] * 8 + [6, 14, 15, 1, 15, 14, 6] + [base]
        for c in cells:
            cols = free(*c)
            while len(cols) < 2:
                cols.append(cols[0] if cols else 0)
            if c not in forced:
                forced[c] = (cols[0], cols[1], base, ("tähti", g))
                dyn.append((c[0], c[1], [base] * 16, int(rng.integers(0, 16)), ("tähti", g, base, tuple(on)), on))
        for y, x in pix:
            img[y, x] = GLINT_PX
    if dropped:
        print(f"loppu: maisema.json: {len(dropped)} pois (solussa yli 2 väriä): {dropped[:8]}", file=sys.stderr)
    forced = {k: v[:3] for k, v in forced.items()}
    global DIS_R0
    DIS_R0 = (lake + 7) // 8
    return img, forced, dyn, wy0, wy1


def encode(img: np.ndarray, forced: dict) -> tuple[bytes, bytes, bytes]:
    """MC-bittikartta, ruutu ja värimuisti ($d021 = 0). forced {(cy, cx): (c01, c10, c11)}: solun roolit
    kiinteästi (c11 = värimuisti, jota 6510 vaihtaa). Muut solut: värit yleisyysjärjestyksessä, yli 3 = virhe."""
    bmp, scr, col = bytearray(8000), bytearray(1000), bytearray(1000)
    for cy in range(25):
        for cx in range(40):
            cell = img[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
            used = [int(v) for v in np.unique(cell) if v and v != GLINT_PX]
            seq = forced.get((cy, cx))
            if seq is None:
                if len(used) > 3:
                    raise SystemExit(f"loppu: solussa {cy},{cx} värit {used} (yli 3)")
                seq = tuple(used + [used[-1] if used else 0] * (3 - len(used)))
            role = {0: 0, GLINT_PX: 3}
            for k, c in enumerate(seq):
                role.setdefault(c, k + 1)
            if set(used) - set(role):
                raise SystemExit(f"loppu: solun {cy},{cx} värit {used} eivät ole rooleissa {seq}")
            scr[cy * 40 + cx] = (seq[0] << 4) | seq[1]
            col[cy * 40 + cx] = seq[2]
            for y in range(8):
                b = 0
                for x in range(4):
                    b |= role[int(cell[y, x])] << (6 - 2 * x)
                bmp[cy * 320 + cx * 8 + y] = b
    return bytes(bmp), bytes(scr), bytes(col)


def kasiala(img: np.ndarray, bmp: bytes, scr: bytes, col: bytes, forced: dict) -> tuple[bytes, list]:
    """Kodin tekijöiden käsiala (kuvan valkoiset pikselit) liukenee taivaaseen, jotta lopputekstit luetaan.
    Pikselin alle taivaan väri samalta riviltä lähimmästä saman pariteetin pikselistä, solun rooleista
    (väri, jota solussa ei ole: lähin luma; %11 vain soluissa, joiden värimuistia 6510 ei vaihda). Palauttaa bittikartan
    ilman käsialaa ja tietueet (osoite, uusi tavu) kirjoitusjärjestyksessä vasemmalta oikealle pienellä hajonnalla:
    yksi tietue tavua kohden sen viimeisen pikselin kohdalla. Kodin kuvan ilman tekijöitä (TAUSTA) kanssa pikselin
    väri on sen oikea tausta, ja HW_1440:n paikoissa sen kohdeväri: lopun kuva kehyksestä 41 ei riipu siitä,
    missä kodin tekijät ovat."""
    rng = np.random.default_rng(2026)
    tgt = {}                                                # lopputila HW_1440:n mukaan, jos kodin
    if TAUSTA and HW_1440.exists():                         # kuva ilman tekijöitä on (HW_1440:n paikat)
        tgt = {(y, x): c for y, x, c in json.loads(HW_1440.read_text(encoding="utf-8"))["pikselit"]}
    new = set(zip(*(v.tolist() for v in np.where(img == 1))))
    pts = sorted(new | {q for q, c in tgt.items() if q not in new and int(img[q]) != c})
    ys, xs = np.array([y for y, _ in pts], int), np.array([x for _, x in pts], int)
    cur = bytearray(bmp)
    recs = {}
    key = xs + rng.uniform(0, HW_JITTER, len(xs))
    rows = np.unique(ys)                                    # nimet: yli 8 tyhjän kuvarivin välein, alin ensin (HW_END)
    band = np.concatenate([[0], np.cumsum(np.diff(rows) > 8)])
    key -= 2 * W * band[np.searchsorted(rows, ys)]
    for k in np.argsort(key, kind="stable"):
        y, x = int(ys[k]), int(xs[k])
        if (y, x) in tgt:
            sky = tgt[(y, x)]
        elif TAUSTA:                                        # kodin kuva ilman tekijöitä: pikselin oikea tausta
            sky = int(TAUSTA[0][y, x])
        else:
            sky = 0
            for d in range(2, W, 2):
                v = [int(img[y, x + s]) for s in (-d, d) if 0 <= x + s < W and img[y, x + s] not in (0, 1, GLINT_PX)]
                if v:
                    sky = v[0]
                    break
        cy, cx = y // 8, x // 4
        s = scr[cy * 40 + cx]
        roles = {1: s >> 4, 2: s & 15} | ({} if (cy, cx) in forced else {3: col[cy * 40 + cx] & 15})
        roles = {r: c for r, c in roles.items() if c != 1} or {0: 0}
        if TAUSTA:                                          # %00 = $d021 = musta (järven alaosa illalla)
            roles.setdefault(0, 0)
        role = min(roles, key=lambda r: (roles[r] != sky, abs(LUMA[roles[r]] - LUMA[sky])))
        a = cy * 320 + cx * 8 + y % 8
        sh = 6 - 2 * (x % 4)
        cur[a] = cur[a] & ~(3 << sh) & 255 | role << sh
        recs.pop(a, None)                                   # tavu kerran (LOPPU1:n tila), viimeisen pikselinsä kohdalla
        recs[a] = cur[a]
    return bytes(cur), [(a, v) for a, v in recs.items() if bmp[a] != v]


# ---------------------------------------------------------------- kirjaimisto ja rivit

def glyph(ch: str, h: int) -> np.ndarray:
    """Kirjaimiston kirjain; pilkku omana (kyltin kirjaimistossa pilkku on piste, koska häntä jäisi kirjainkorkeuden
    alle; tässä piste ja sen alla 1-2 pikselin häntä vasemmalle alas):
    "," = piste perusviivalla ja häntä riviä alempana (kirjain h + t riviä), "¸" = sama kirjainkorkeuden sisällä
    pienen tekstin toiselle riville, joka päättyy spriterivin viimeiselle riville (encode_line valitsee)."""
    if ch not in ",¸":
        return font.glyph(ch, h, KX)
    t = 1 if h < 12 else 2                                # vedon paksuus kuten pisteessä (kyltin kynä)
    b = h if ch == "," else h - t                         # pisteen alareuna
    g = np.zeros((b + t, 2 * t), bool)
    g[b - t:b, t:2 * t] = True                            # piste
    g[b:b + t, 0:t] = True                                # häntä vasemmalle alas
    return g


def line_chars(line: str, k: int, kind: str) -> str:
    """Rivin merkit kirjaimistolle: pienen tekstin toisella rivillä pilkku kirjainkorkeuden sisällä ("¸")."""
    return line.replace(",", "¸") if k == 1 and kind == "pieni" else line


def glyphs(text_rows: list) -> dict:
    out = {}
    for row in text_rows:
        if row[0] == "logo":
            continue
        h = KIND_H[row[0]]
        for k, line in enumerate(row[1:]):
            for ch in line_chars(line, k, row[0]):
                if (ch, h) not in out and ch not in " |":
                    out[(ch, h)] = glyph(ch, h)
    return out


def line_width(line: str, h: int, gl: dict) -> int:
    if "|" in line:                                       # terveiset sarakkeittain (name_cols)
        names = line.split("|")
        xs = name_cols(names, h)
        return xs[-1] + line_width(names[-1], h, gl) if xs else 999
    w = sum(SPACE[h] if ch == " " else gl[(ch, h)].shape[1] for ch in line)
    return w + GAP * max(0, len(line) - 1)


TEXT, NOGAP = _credits(TEXT, LOPPU_ROWS)        # kirjaimiston funktiot (wrap) ovat yllä


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    gl = glyphs(TEXT[:-LAST_ROWS] + [END_TEXT])           # isot rivit korvautuvat loppukortilla
    keys = sorted(gl, key=lambda k: (k[1], k[0]))
    index = {k: i for i, k in enumerate(keys)}
    lines = ["; Generoitu: tools/disk/loppu.py (src/runko/loppu.asm). Kirjaimisto, tekstirivit, taustan värisolut."]
    # kirjain: leveys, korkeus, tavuja riviltä (1-3, vasemmalle tasattu), data riveittäin
    data = []
    for k in keys:
        g = gl[k]
        h, w = g.shape
        nb = (w + 7) // 8
        bts = []
        for r in range(h):
            bits = list(g[r]) + [False] * (nb * 8 - w)
            for b in range(nb):
                bts.append(int("".join("1" if v else "0" for v in bits[b * 8:b * 8 + 8]), 2))
        data.append((k, w, h, nb, bts))
    lines.append(f"GLYPHS  = {len(keys)}")
    lines.append("gl_w    .byte " + ", ".join(str(d[1] + GAP) for d in data))
    lines.append("gl_h    .byte " + ", ".join(str(d[2]) for d in data))
    lines.append("gl_nb   .byte " + ", ".join(str(d[3]) for d in data))
    lines.append("gl_lo   .byte " + ", ".join(f"<gl_{i}" for i in range(len(data))))
    lines.append("gl_hi   .byte " + ", ".join(f">gl_{i}" for i in range(len(data))))
    for i, (k, w, h, nb, bts) in enumerate(data):
        lines.append(f"gl_{i}    .byte " + ", ".join(f"${b:02x}" for b in bts) + f"   ; {k[0]!r} {k[1]}")
    # tekstirivit: spriterivi = rivit (x, sprite-rivi, kirjaimet..., $fe = väli h px) $ff; tyhjä spriterivi = $ff
    rows, y0, ycenter, keep = layout()
    lines.append(f"YCENTER = {ycenter}")
    lines.append(f"HOLD    = {scene_len() - STOP}")
    lines.append(f"Y0      = {y0}")
    lines.append(f"ROWS    = {len(rows)}")
    lines.append(f"ROWSPAN = {sum(r['pitch'] for r in rows[:-1])}")
    lines.append(f"KEEP_FROM = {keep}               ; loppukortti: ei himmennetä")
    lines.append(f"LOGO_AT = ${LOGO_AT:04x}")
    # rivit ROWS_EARLY- LOPPU3:een (rivit.inc): loppu_go piirtää NSLOT (12) ensimmäistä ennen LOPPU3:n latausta, ja
    # LOPPU1 on täynnä vektoreihin asti; tyhjät rivit jakavat yhden $ff:n
    rl = ["; Generoitu: tools/disk/loppu.py (src/runko/loppu.asm, LOPPU3). Tekstirivit ROWS_EARLY-."]
    lines.append(f"ROWS_EARLY = {ROWS_EARLY}")
    blank = {i for i, r in enumerate(rows) if r["kind"] == "text" and not any(r["row"][1:])}
    lines.append("row_lo  .byte " + ", ".join("<row_blank" if i in blank else f"<row_{i}" for i in range(len(rows))))
    lines.append("row_hi  .byte " + ", ".join(">row_blank" if i in blank else f">row_{i}" for i in range(len(rows))))
    lines.append("row_blank .byte $ff")
    lines.append("ROWH    = [" + ", ".join(str(r["pitch"]) for r in rows) + "]")
    lines.append("ROWF    = [" + ", ".join(str((1 if r.get("cont") else 0) | (2 if r.get("mc") else 0) | (0x40 if i >= keep else 0)
                                             | (0x80 if r["kind"] == "logo" else 0)) for i, r in enumerate(rows)) + "]")
    # tapahtuman etumatka: tekstiriveillä 6 (loppu.asm TXT_LEAD); loppukortin muut rivit 14 (set_ptr:n kortin polku on
    # hidas, edellisen rivin muste on jo ohi) ja yhtenäiset 20 (valmistelu heti edellisen alettua)
    lines.append("ROWL    = [" + ", ".join(str(20 if r.get("cont") else 14 if i >= keep else 6) for i, r in enumerate(rows)) + "]")
    lines.append("ROWC    = [" + ", ".join(str(r.get("col", 0)) for r in rows) + "]")
    lines.append("ROWM    = [" + ", ".join(str(r.get("mc1", 0)) for r in rows) + "]")
    blob = bytearray()
    for i, r in enumerate(rows):
        if r["kind"] in ("logo", "slogo"):                # slogo: tukijalogo vierityksessä (tekstirivin värit)
            if i < ROWS_EARLY:
                raise SystemExit(f"loppu: logorivi {i} < ROWS_EARLY: sen data (LOPPU3) ei ole vielä ladattu")
            a = LOGO_AT + len(blob)
            blob += r["data"]
            (rl if i >= ROWS_EARLY else lines).append(f"row_{i}   .byte $fc, ${a & 255:02x}, ${a >> 8:02x}")
            continue
        row = r["row"]
        if i in blank:
            continue
        h = KIND_H[row[0]]
        ys = list(KIND_Y[row[0]])
        enc = []
        for k, (line, y) in enumerate(zip(row[1:], ys)):
            if not line:
                continue
            line = line_chars(line, k, row[0])
            w = line_width(line, h, gl)
            if w > STRIP - 1:
                raise SystemExit(f"loppu: rivi {line!r} {w} px > {STRIP - 1}")
            if "|" in line:                        # sarakkeet: nimien välit $fe-väleinä (render: gx kasvaa)
                names = line.split("|")
                xs = name_cols(names, h)
                enc += [xs[0], y]
                for k, name in enumerate(names):
                    if k:                          # render: kirjain gx += leveys + GAP, väli gx += SPACE
                        gx = xs[k - 1] + sum(SPACE[h] if ch == " " else gl[(ch, h)].shape[1] + GAP for ch in names[k - 1])
                        enc += [0xFE, xs[k] - gx]
                    for ch in name:
                        enc += [0xFE, SPACE[h]] if ch == " " else [index[(ch, h)]]
                enc.append(0xFD)
                continue
            enc += [(STRIP - w) // 2, y]
            for ch in line:
                enc += [0xFE, SPACE[h]] if ch == " " else [index[(ch, h)]]
            enc.append(0xFD)                       # rivin loppu
        enc.append(0xFF)
        (rl if i >= ROWS_EARLY else lines).append(f"row_{i}   .byte " + ", ".join(f"${b:02x}" for b in enc))
    # logorivien rivi 20 (8 spriteä x 3 tavua): badline-vaihdossa uuden rivin lohkoihin edellisen rivin rivi 20 ja rivin
    # alettua takaisin oma (loppu.asm put20). Valmiit rutiinit lda #/sta abs (vakiodata, nopea IRQ:ssa), LOPPU2:n perässä.
    logo_rows = [i for i, r in enumerate(rows) if r["kind"] == "logo"]
    if logo_rows != list(range(keep, keep + len(logo_rows))):
        raise SystemExit("loppu: logorivit eivät ole yhtenäisesti loppukortin alussa")
    l20 = {i: [rows[i]["data"][s * 63 + 60 + j] for s in range(8) for j in range(3)] for i in logo_rows}
    code = ["; Generoitu: tools/disk/loppu.py. Loppukortin logorivien lohkojen rivi 20 (put20, loppu.asm)."]
    names = []
    for kind, src_of in (("p", lambda i: i - 1), ("r", lambda i: i)):
        for i in logo_rows:
            nm = f"l20{kind}_{i}"
            names.append(nm)
            code.append(nm)
            if rows[i].get("cont"):
                last = None
                for k, v in enumerate(l20[src_of(i)]):
                    if v != last:
                        code.append(f"        lda #${v:02x}")
                        last = v
                    code.append(f"        sta SPR + ({i} % NSLOT) * 512 + {k // 3 * 64 + 60 + k % 3}")
            code.append("        rts")
    code.append("l20v_lo .byte " + ", ".join(f"<{n}" for n in names))
    code.append("l20v_hi .byte " + ", ".join(f">{n}" for n in names))
    lines.append(f"L20_ROW0 = {keep}")
    lines.append(f"L20_N   = {len(logo_rows)}")
    (out / "l20.inc").write_text("\n".join(code) + "\n")
    (out / "rivit.inc").write_text("\n".join(rl) + "\n")
    (out / "logot.bin").write_bytes(bytes(blob))
    export_last(out, gl, rows, ycenter)
    img, forced, dyn, wy0, wy1 = background()
    lines.append(f"WAVE    = {WAVE}")
    lines.append(f"WBASE   = ${WBASE:02x}")
    lines.append(f"HORIZON_ROW = {DIS_R0}")
    lines.append(f"LAST_ROWS = {LAST_ROWS}")
    lines.append(f"NFADE   = {NFADE}")
    lines.append("FADE_TAB = [" + ", ".join(str(darker(c, l)) for l in range(NFADE + 1) for c in range(16)) + "]")
    bmp, scr, col = encode(img, forced)
    hwc = {(y // 8, x // 4) for y, x in zip(*np.where(img == 1))}
    full, hw = kasiala(img, bmp, scr, col, forced)
    lines.append(f"HW_N    = {len(hw)}")
    lines.append(f"HW_T0   = {HW_T0}")
    lines.append(f"HW_PF   = {-(-len(hw) // (HW_END - HW_T0))}")
    (out / "kasiala.bin").write_bytes(bytes(b for a, v in hw for b in (a & 255, 0x60 + (a >> 8), v)))
    # letterbox: kehys 0 = kodin kuva (rivit wy0..wy1-1), muut kuvarivit mustina bittikartassa; open.bin = niiden oikeat
    # tavut avautumisjärjestyksessä (ylä- ja alareuna yhtä aikaa ikkunasta poispäin), OPEN_CNT[t] = auki kehyksellä t
    top = [(y, (k + 1) / wy0) for k, y in enumerate(range(wy0 - 1, -1, -1))]
    bot = [(y, 0.15 * (k + 1) / (H - wy1)) for k, y in enumerate(range(wy1, H))]   # alareuna ensin: teksti nousee sieltä
    order = [y for y, _ in sorted(top + bot, key=lambda e: e[1])]
    bmp = bytearray(bmp)
    opened = bytearray()
    for y in order:
        for cx in range(40):
            a = (y // 8) * 320 + cx * 8 + y % 8
            opened.append(bmp[a])
            bmp[a] = 0
    bmp = bytes(bmp)
    (out / "open.bin").write_bytes(bytes(opened))
    def ease(u):
        return 1 - (1 - u) ** 2
    lines.append(f"OPEN_N  = {OPEN_N}")
    # järvi liukenee mustaan Bayer 2 x 2 -järjestyksessä MC-pikseleittäin (askel k: pikselit, joiden kynnys <= k pois)
    bay = [[0, 2], [3, 1]]
    lines.append(f"DIS_R0  = {DIS_R0}")
    lines.append("DIS_M   = [" + ", ".join(f"${sum(3 << (6 - 2 * x) for x in range(4) if bay[py][x % 2] > k):02x}"
                                           for k in range(4) for py in range(2)) + "]")
    lines.append(f"OPEN_L  = {len(order)}")
    lines.append("OPEN_CNT = [" + ", ".join(str(round(len(order) * ease(t / OPEN_N))) for t in range(OPEN_N + 1)) + "]")
    lines.append("OPEN_LO = [" + ", ".join(f"<(BMP + {(y // 8) * 320 + y % 8})" for y in order) + "]")
    lines.append("OPEN_HI = [" + ", ".join(f">(BMP + {(y // 8) * 320 + y % 8})" for y in order) + "]")
    # tekstin taso Y / 8:n mukaan (Y 0-271, reunat auki): rivi syntyy alareunassa ja poistuu yläreunassa mustana
    # (loppu.asm YB 272 ja YTOP 4), muualla valkoinen; reunan neljä tasoa 8 rivin välein
    lines.append("FADE_Y  = [" + ", ".join(str(v) for v in [0, 1, 2, 3] + [4] * 26 + [3, 2, 1, 0]) + "]")
    # aurinko laski jo kodissa: lopun sun_set ei tee mitään (SUN_R = 0)
    lines += ["SUN_CX0 = 0", "SUN_NC  = 1", "SUN_Y0  = 0", "SUN_YN  = 1", "SUN_TOP = 0", "SUN_R   = 0",
              "SUN_SKY = [0]", "SUN_BITS = [0]", "SUN_MASK = [$ff]"]
    # rivien muutostasot: bitti l - 1, jos jokin rivin väreistä (ruutu ja värimuisti) vaihtuu tasolla l (fade_row ohittaa muut)
    ft = [darker(c, l) for l in range(NFADE + 1) for c in range(16)]
    rmask = []
    # käsialan soluissa vain liukenemisen jälkeen käytetyt roolit (ja %11, jos 6510 vaihtaa sitä): valkoinen on poissa
    # ennen hämärää. Rivit HW_ROWS aina, joten pyyhkäisyn ajoitus ei riipu käsialan paikasta
    for r in range(25):
        cs = set()
        for c in range(40):
            b = scr[r * 40 + c]
            rc = {1: b >> 4, 2: b & 15, 3: col[r * 40 + c] & 15}
            if (r, c) in hwc:
                used = {full[r * 320 + c * 8 + y] >> sh & 3 for y in range(8) for sh in (0, 2, 4, 6)}
                rc = {k: v for k, v in rc.items() if k in used or (k == 3 and (r, c) in forced)}
            cs |= set(rc.values()) | ({1} if r in HW_ROWS else set())
        rmask.append(sum(1 << (l - 1) for l in range(1, NFADE + 1) if any(ft[l * 16 + c] != ft[(l - 1) * 16 + c] for c in cs)))
    lines.append("ROWMASK = [" + ", ".join(str(m) for m in rmask) + "]")
    (out / "tausta.bmp").write_bytes(bmp)
    # LOPPU2 (bittikartta) puretaan paikallaan, ja pakattu virta latautuu bittikartan loppuun (vesi): rivit TAIL_ROW-
    # voivat olla roskaa ennen purkua
    start = 0x6000 + len(bmp) - len(zx0.pack(bmp, 0x6000)) + 2
    tail = min(wy1 // 8 + 1, (start - 0x6000) // 320)
    (out / "tausta.scr").write_bytes(scr)
    lines.append(f"TAIL_ROW = {tail}")
    (out / "tausta.col").write_bytes(col)
    # vaihtuvat solut: värimuistin osoite, taulu (16 väriä) ja vaihe
    keys, tables, ons = [], [], []
    for _, _, t, _, key, on in dyn:
        if key not in keys:
            keys.append(key)
            tables.append(t)
            ons.append(on)
    # 6510 kirjoittaa joka kehys: värimuisti[DYN_A] = rot[DYN_P], rot = taulut kierrettynä kehyksen mukaan
    lines.append("DYN_A   = [" + ", ".join(f"$d800 + {cy * 40 + cx}" for cy, cx, *_ in dyn) + "]")
    lines.append("DYN_P   = [" + ", ".join(str(keys.index(k) * 16 + ph) for _, _, _, ph, k, _ in dyn) + "]")
    lines.append(f"DYN_TABS = {len(tables)}")
    lines.append("SUN_T   = 255")                             # ei auringon heijastusta
    lines.append("dyn_tab .byte " + ", ".join(str(c) for t in tables for c in t + t))   # 32 t / taulu
    # tähtiryhmät syttyvät: kehys (kohtauksen alusta), taulun indeksi ja 32 tavua (tuike pohjan päällä)
    st = sorted([(round(STAR_AT[k[1]] * BASE), i, ons[i]) for i, k in enumerate(keys) if k[0] == "tähti"])
    lines.append(f"STARS_N = {len(st)}")
    lines.append("STAR_T  = [" + ", ".join(str(t) for t, _, _ in st) + "]")
    lines.append("STAR_I  = [" + ", ".join(str(i * 32) for _, i, _ in st) + "]")
    lines.append("STAR_ON = [" + ", ".join(str(c) for _, _, on in st for c in on + on) + "]")
    # järven välke: vaiheittain tavut (osoite, päällä, pois) kuvan tavuista; vaihe vaihtuu VK_DT kehyksen välein
    ve, starts = [], []
    for px in VALKE:
        starts.append(len(ve))
        byt: dict = {}
        for y, x in px:
            a = (y // 8) * 320 + (x // 4) * 8 + y % 8
            byt[a] = byt.get(a, 0) | 3 << (6 - 2 * (x % 4))
        for a, mk in sorted(byt.items()):
            ve.append((0x6000 + a, full[a] | mk, full[a]))
    starts.append(len(ve))
    both = {a for a, _ in hw} & {a - 0x6000 for a, _, _ in ve}
    if both:
        print(f"loppu: käsiala ja välke samoissa tavuissa: {len(both)}", file=sys.stderr)
    vk = ["; Generoitu: tools/disk/loppu.py (src/runko/loppu.asm, LOPPU1). Järven välkkeen vaiheet (tools/gfx/data/loppu/maisema.json)."]
    vk.append(f"VK_N = {len(VALKE)}")
    vk.append(f"VK_DT = {VK_DT}")
    vk.append(f"VK_M = {VK_DT * len(VALKE)}")
    vk.append("vk_lo .byte " + ", ".join(f"<(vk_rec + {4 * i})" for i in starts))
    vk.append("vk_hi .byte " + ", ".join(f">(vk_rec + {4 * i})" for i in starts))
    vk.append("vk_rec .byte " + ", ".join(f"${a & 255:02x}, ${a >> 8:02x}, ${on:02x}, ${off:02x}" for a, on, off in ve))
    (out / "valke.inc").write_text("\n".join(vk) + "\n")
    # taivas tummuu: taustan valotasot 1..len(DUSK) kehyksillä (ennen valojen sammumista FADE0 = STOP - 300)
    dk = [d if d >= 1 else round(d * BASE) for d in DUSK]
    if dk[-1] >= STOP - 300:
        raise SystemExit(f"loppu: hämärä {dk} osuu valojen sammumiseen")
    lines.append(f"DUSK_N  = {len(dk)}")
    lines.append("DUSK_T  = [" + ", ".join(str(t) for t in dk) + "]")
    (out / "loppu.inc").write_text("\n".join(lines) + "\n")


def export_last(out: Path, gl: dict, rows: list, ycenter: int) -> None:
    """Viitemaskit (viite_*.npy): loppukortin logot ja tekstirivi loppukohdassaan
    (viimeisen rivin yläreuna ycenter) kuten 6510 ne piirtää: koko ruutu 200 x 320 hires, 1 = muste,
    OUT/viite_<osa>.npy (zoo, simlohja, oylohjaai2026)."""
    last_top = ycenter - (rows[-1]["top"] if "top" in rows[-1] else 0)
    masks = {}
    for r in rows:
        if "top" not in r:
            continue
        y = last_top + r["top"] - 50                      # ruudun rivi
        if r["kind"] == "logo":
            m = masks.setdefault(r["name"], np.zeros((200, 320), np.uint8))
            ink = r["ink"]
            m[y:y + ink.shape[0], 64:64 + 192][ink] = 1
        else:
            row = r["row"]
            h = KIND_H[row[0]]
            line = row[1]
            m = masks.setdefault(line.replace(" ", "").lower(), np.zeros((200, 320), np.uint8))
            x = 64 + (STRIP - line_width(line, h, gl)) // 2
            yy = y + KIND_Y[row[0]][0]
            for ch in line:
                if ch == " ":
                    x += SPACE[h]
                    continue
                g = gl[(ch, h)]
                m[yy:yy + g.shape[0], x:x + g.shape[1]][g] = 1
                x += g.shape[1] + GAP
    for old in out.glob("viite_*.npy"):                   # vanhan asettelun viitteet pois
        if old.stem[6:] not in masks:
            old.unlink()
    for name, m in masks.items():
        np.save(out / f"viite_{name}.npy", m)


if __name__ == "__main__":
    main()
