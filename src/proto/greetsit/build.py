"""Greetsit (partti 4): harjun parallaksiajo auringonlaskussa ja sinusskrolleri runkojen takana.
Staattinen data ja generoitu koodi: merkistöt ja kaistojen kartat, kaistojen karkean siirron koodi, tien
rivikohtaiset siirtotaulut ja päivityskoodi, runkospritet, skrollerin teksti tasoina ja piirtokoodi sekä
rasterikerneli, jonka syklit lasketaan VIC:n BA-mallilla (spritejen DMA tahdistaa CPU:n joka rivillä).

  uv run --project tools/concept python src/proto/greetsit/build.py OUTDIR [--report]

Data: tools/gfx/data/greetsit/.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src/proto/kyltti"))
sys.path.insert(0, str(ROOT / "src/lib"))

import kehys  # noqa: E402
import lenkkeilija  # noqa: E402
import pyorailija  # noqa: E402

DATA = ROOT / "tools/gfx/data/greetsit/v5"
T = 255

# ---------------------------------------------------------------- ruutu ja kaistat
SCR0 = 51                     # ruudun rivi 0 = rasteririvi 51 (YSCROLL 3, badline kun rivi & 7 == 3)
BANDS = {                     # nimi: (ensimmäinen ruudun rivi, rivejä, merkistö)
    "taivas": (0, 80, "A"),
    "maet": (80, 16, "A"),
    "teksti": (96, 32, "X"),
    "kaupunki": (128, 40, "T"),
    "piennar": (168, 8, "T"),
    "tie": (176, 24, "R"),
}
MAP_BANDS = ("taivas", "maet", "kaupunki", "piennar")
SPEED = {"taivas": 0.125, "maet": 0.25, "kaupunki": 0.5, "piennar": 2.0, "teksti": 3.0,
         "lahi": 2.0, "kauka": 1.5}
# Teksti 3 hires px/kehys: nopeampi kuin rungot (2 ja 1,5), joten kirjaimet ohittavat rungot ja jokainen tulee
# näkyviin (samalla nopeudella rungon takana oleva kirjain pysyisi peitossa; siksi 3 eikä 2).
TXT_V = 3
# Tie: jokainen pikselirivi vierii omalla nopeudellaan (perspektiivi). Asfaltin raekuvio jaksolla 32 MC-px
# (8 merkkiä per merkkirivi); runkojen varjot eivät ole kuviossa vaan spriteinä, jotka kiertyvät rungon mukana.
ROAD_ROWS = [(8, None)] * 3
ROAD_BASE = [0, 8, 16]        # merkkirivin ensimmäinen merkki merkistössä R
ROAD_W = 32
ROAD_V = (2.0, 3.5)           # hires px/kehys: kaukainen reuna (rivi 176) .. lähin (199)
COLS = 39                     # kopioitavat sarakkeet (38 saraketta + hienovieritys)
COLOR_UNROLL = 8              # värimuistin vakiorivejä suorina kirjoituksina (color_u, 123 tavua/rivi)

# spritet: 8 pinoa x 21 riviä, ensimmäinen näkyvä rasteririvi 52 (ruudun rivi 1). Pinon vaihtorivit (R - 1)
# eivät osu badlineen (tarkistetaan).
SPR_R0, SPR_N, SPR_H = 52, 8, 21
N_NEAR, N_FAR = 5, 3          # spritet 0-4 lähimmät rungot, 5-7 kaukaiset (takana)

# ---------------------------------------------------------------- muisti (VIC-pankki 1)
BANK = 0x4000
S0, S1 = 0x4000, 0x4400
CS = {"A": 0x4800, "T": 0x5000, "R": 0x5800, "X0": 0x6000}
SPR_AREAS = [(0x5900, 0x6000), (0x6600, 0x8000)]   # X0 $6000-$65ff (TB_N sarakkeen kiertävä puskuri)
TEXT_ROWS = 4                 # tekstikaista 4 merkkiriviä (32 riviä)
GLYPH_H = 25                  # kirjain 24 riviä + varjo (teksti >= 1/8 kuvasta)
TXT_H, TXT_KX, TXT_A = 24, 0.6, 3.0

# ---------------------------------------------------------------- VIC:n BA-malli (Bauer, syklit 1-63)
BA_BL = (12, 54)              # badline: BA alhaalla 12-54
BA_SPR = (55, 10)             # 8 spriteä: BA alhaalla edellisen rivin 55:stä tämän rivin 10:een


def badline(line: int) -> bool:
    return SCR0 <= line < SCR0 + 200 and (line & 7) == (SCR0 & 7)


def spr_on(line: int) -> bool:
    return SPR_R0 <= line < SPR_R0 + SPR_N * SPR_H


def ba_low(line: int, cyc: int) -> bool:
    if badline(line) and BA_BL[0] <= cyc <= BA_BL[1]:
        return True
    if cyc >= BA_SPR[0] and spr_on(line + 1):
        return True
    if cyc <= BA_SPR[1] and spr_on(line):
        return True
    return False


class Sim:
    """CPU-syklit BA-mallilla: lukusykli odottaa, kunnes BA on ylhäällä; kirjoitus ei odota."""

    def __init__(self, line: int, cyc: int):
        self.line, self.cyc = line, cyc
        self.writes: list[tuple[str, int, int]] = []

    def pos(self):
        return self.line, self.cyc

    def step(self):
        self.cyc += 1
        if self.cyc > 63:
            self.cyc, self.line = 1, self.line + 1

    def run(self, pat: str, reg: str | None = None):
        first = None
        for t in pat:
            if t == "R":
                while ba_low(self.line, self.cyc):
                    self.step()
            if first is None:
                first = self.pos()
            if t == "W" and reg:
                self.writes.append((reg, self.line, self.cyc))
            self.step()
        return first


PAT = {"imm": "RR", "zp": "RRR", "zpw": "RRW", "abs": "RRRR", "absw": "RRRW", "impl": "RR"}


def mode_of(asm: str) -> str:
    op, _, arg = asm.partition(" ")
    if not arg:
        return "impl"
    w = op in ("sta", "stx", "sty")
    if arg.startswith("#"):
        return "imm"
    zp = arg.startswith("z_")
    if w:
        return "zpw" if zp else "absw"
    return "zp" if zp else "abs"


class Gen:
    """Koodi ja sen ajoitus: jokainen käsky simuloidaan heti."""

    def __init__(self, sim: Sim):
        self.sim, self.lines = sim, []
        self.fsites: list[tuple[str, int]] = []

    def i(self, asm: str, reg: str | None = None, note: str = ""):
        pat = PAT[mode_of(asm)]
        if reg == "fade":                       # värivakio: häivytys kirjoittaa operandin (fade_sites)
            lab = f"fk{len(self.fsites)}"
            self.fsites.append((lab, int(asm.split("#")[1])))
            self.lines.append(f"{lab} = * + 1")
            reg = None
        p = self.sim.run(pat, reg)
        self.lines.append(f"        {asm:<28}; {p[0]}:{p[1]:<2} {note}".rstrip())
        return p


    def pad(self, n: int):
        """n sykliä (n != 1) nop/bit-yhdistelmänä."""
        if n == 1 or n < 0:
            raise ValueError(f"pad {n}")
        while n:
            if n == 3 or n == 5:
                self.i("bit z_pad")
                n -= 3
            else:
                self.i("nop")
                n -= 2

    def pad_to(self, line: int, cyc: int):
        """Seuraavan käskyn ensimmäinen sykli kohtaan (line, cyc); väli ilman BA:ta."""
        while ba_low(*self.sim.pos()):    # seuraavan käskyn opkoodin luku odottaa joka tapauksessa
            self.sim.step()
        n = (line - self.sim.line) * 63 + (cyc - self.sim.cyc)
        if n < 0:
            raise ValueError(f"pad_to {line}:{cyc}: ollaan jo kohdassa {self.sim.pos()}")
        ln, cy = self.sim.pos()
        for _ in range(n):           # väli ei saa sisältää pysähdyksiä
            if ba_low(ln, cy):
                raise ValueError(f"pad_to {line}:{cyc} ylittää BA:n kohdassa {ln}:{cy}")
            cy += 1
            if cy > 63:
                ln, cy = ln + 1, 1
        if n > 120:
            k = (n - 1 - 2 - 2) // 5            # ldy #k (2) + k * 5 - 1 + jäännös (X on paikan arvo)
            rest = n - (2 + 5 * k - 1)
            if rest == 1:
                k -= 1
                rest += 5
            self.i(f"ldy #{k}")
            lab = f"_dl{len(self.lines)}"
            self.lines.append(f"{lab}   dey")
            self.lines.append(f"        bne {lab}")
            self.lines.append(f'        .cerror {lab} >> 8 != * >> 8, "viivesilmukka ylittää sivun"')
            self.sim.run("R" * (5 * k - 1))
            self.pad(rest)
        else:
            self.pad(n)


# ---------------------------------------------------------------- data
def load_data() -> dict:
    meta = json.loads((DATA / "metadata.json").read_text())
    d = {k: np.load(DATA / f"{k}.npy") for k in (*MAP_BANDS, "tie")}
    d["d021"] = np.load(DATA / "taivas_d021.npy")
    var = {p.stem: np.load(p) for p in sorted((DATA / "rungot").glob("*.npy"))}
    d["rungot"] = {"variantit": var, "lahi": meta["rungot_lahi"], "kauka": meta["rungot_kauka"],
                   "jakso_lahi": meta.get("jakso_lahi"), "jakso_kauka": meta.get("jakso_kauka")}
    d["meta"] = meta
    d["lahde"] = str(DATA.relative_to(ROOT))
    return d


def mc_byte(px) -> int:
    return (int(px[0]) << 6) | (int(px[1]) << 4) | (int(px[2]) << 2) | int(px[3])


class Charset:
    def __init__(self, name: str, reserve: int = 0):
        self.name, self.chars, self.index = name, [bytes(8)], {bytes(8): 0}
        self.chars += [bytes(8)] * reserve

    def add(self, b: bytes) -> int:
        if b not in self.index:
            self.index[b] = len(self.chars)
            self.chars.append(b)
        return self.index[b]

    def blob(self) -> bytes:
        if len(self.chars) > 256:
            raise SystemExit(f"merkistö {self.name}: {len(self.chars)} merkkiä (raja 256)")
        return b"".join(self.chars)


def encode_band(name: str, img: np.ndarray, meta: dict, cs: Charset, errs: list) -> dict:
    """Kaista merkeiksi: 4x8-solut, %00 = 255, %01 = d022, %10 = d023, %11 = solun oma väri (0-7) tai
    kaistan rivivari. Palauttaa kartan (rivit x sarakkeet merkkikoodeja) ja värimuistin."""
    h, w = img.shape
    if h % 8 or w % 4:
        raise SystemExit(f"{name}: koko {img.shape} (rivit 8:n, leveys 4:n monikerta)")
    d022, d023 = meta["d022"], meta["d023"]
    row_col = meta.get("rivivari")
    rows, cols = h // 8, w // 4
    codes = np.zeros((rows, cols), np.uint8)
    color = np.zeros((rows, cols), np.uint8)
    for r in range(rows):
        for c in range(cols):
            cell = img[r * 8:r * 8 + 8, c * 4:c * 4 + 4]
            own = sorted({int(v) for v in np.unique(cell)} - {T, d022, d023})
            if row_col is not None:
                bad = [v for v in own if v != row_col]
                own = [row_col]
            else:
                bad = [v for v in own if v > 7] + own[1:]
                own = [v for v in own if v <= 7][:1] or [0]
            if bad:
                errs.append(f"{name} solu rivi {r} sarake {c}: värit {sorted(set(bad))} eivät mahdu "
                            f"(d022 {d022}, d023 {d023}, oma {own[0]})")
            lut = {T: 0, d022: 1, d023: 2, own[0]: 3}
            bits = np.vectorize(lambda v: lut.get(int(v), 3))(cell)
            codes[r, c] = cs.add(bytes(mc_byte(bits[y]) for y in range(8)))
            color[r, c] = own[0] | 8
    # rivin vakioväri (kaikki solut samaa väriä) tai None = solukohtaiset värit (kopioidaan kaistan mukana)
    row_cols = [int(color[r, 0]) if (color[r] == color[r, 0]).all() else None for r in range(rows)]
    return {"codes": codes, "color": color, "rows": rows, "cols": cols, "row_cols": row_cols}


def check_seams(d: dict, errs: list):
    for name in ("taivas", "maet", "kaupunki", "piennar"):
        img = d[name]
        if (img[-1] != T).any():
            errs.append(f"{name}: alin rivi ei ole kokonaan %00 (sauma)")
    d21 = d["d021"]
    for s in (95, 127):
        if d21[s] != d21[s + 1]:
            errs.append(f"taivas_d021: rivi {s} ({d21[s]}) != rivi {s + 1} ({d21[s + 1]}) (sauma, $D018 vaihtuu)")


# ---------------------------------------------------------------- tie
def asphalt(img: np.ndarray, meta: dict) -> np.ndarray:
    """tie.npy ilman varjoja: varjot ovat %00-pikseleitä (tausta) riveillä 2-; ne korvataan
    asfaltin perusvärillä ($D022). Rivit 0-1 (reuna) ennallaan. Varjot piirtävät spritet."""
    out = img.copy()
    out[2:][out[2:] == T] = meta["d022"]
    return out


def road_tables(img: np.ndarray, meta: dict) -> tuple[list[bytes], list[str]]:
    """Riveittäin 4 alisiirtoa x 16 tavua: tab[s * 16 + m] = MC-tavu pikseleistä (4m + s + k) mod 32; rivin
    tavu j siirrolla o = 4q + s on tab[s * 16 + q + j]. Akku: rivin 8.8-paikka, yläbitit & 31 -> ox32."""
    lut = {T: 0, meta["d022"]: 1, meta["d023"]: 2, meta["rivivari"]: 3}
    bits = np.vectorize(lambda v: lut.get(int(v), 3))(img)
    w = img.shape[1]
    tabs = []
    for y in range(img.shape[0]):
        t = bytearray()
        for sft in range(4):
            for m in range(16):
                t.append(mc_byte([bits[y, (4 * m + sft + k) % w] for k in range(4)]))
        tabs.append(bytes(t))
    asm = []
    n = img.shape[0]
    for y in range(n):
        v = ROAD_V[0] + (ROAD_V[1] - ROAD_V[0]) * y / (n - 1)
        asm.append(f"RVEL{y} = {round(v / 2 * 256)}")
    asm.append("        .align 32")
    asm += asm_bytes("ox32", [((o & 3) << 4) | (o >> 2) for o in range(32)])
    return tabs, asm


# ---------------------------------------------------------------- teksti
# Greetsit: henkilöt tekstit.yaml:n kohdasta greets-harju (ryhmät ovat Lohjantähden kyljessä, henkilöt Lohjanharjun
# skrollerissa ja lopputeksteissä). Kirjoitusasu sieltä, kirjaimisto on versaali. Kohtauksen pituus seuraa
# nimiä (TXT_V px/kehys: viimeinen nimi kokonaan ruudulla); lista kiertää (gidtab toistaa sarakkeet).


def greets_text() -> str:
    sys.path.insert(0, str(ROOT / "tools"))
    import tekstit
    names = [n.strip() for n in tekstit.lista("greets-harju") if n.strip()]
    return " - ".join(n.upper() for n in names) + "   "


def text_columns(text: str) -> list[bytes]:
    """Teksti kyltin kirjaimistolla TXT_H riviä korkeana MC-pikseleinä, varjo (1, 1): sarakkeet 4 MC-px x
    GLYPH_H riviä. Jokainen kirjain alkaa 4 px:n rajalta (DYCP-sarakkeet kirjaimittain, erilaisia sarakkeita vähän).
    Arvot: teksti %11 (värimuisti), varjo %10 ($D023)."""
    import font  # src/proto/kyltti/font.py
    h, kx = TXT_H, TXT_KX
    out = []
    for ch in text:
        if ch == " ":
            out.append(bytes(GLYPH_H))
            continue
        if ch == "_":                                     # kirjaimistossa ei ole: viivan levyinen palkki pohjalla
            g = np.zeros_like(font.glyph("-", h, kx))
            g[h - font.pens(h)[1]:] = True
        else:
            g = font.glyph(ch, h, kx)
        w = (g.shape[1] + 2 + 3) // 4 * 4                 # varjo + väli
        img = np.zeros((GLYPH_H, w), np.uint8)
        img[0:h, 0:g.shape[1]][g] = 3
        sh = np.zeros_like(img)
        sh[1:h + 1, 1:g.shape[1] + 1] = np.where(g, 2, 0)
        img = np.where(img == 0, sh, img)
        out += [bytes(mc_byte(img[y, c * 4:c * 4 + 4]) for y in range(GLYPH_H)) for c in range(w // 4)]
    return out


# Kulkeva aalto (sulava siniliike, ei hidas eikä nykivä): kiertävän puskurin sarakkeen b pystysiirto
# WAVE[(CPH[b] + p) & 255], vaihe p pienenee WAVE_DP joka kehys (aalto kulkee tekstiä vastaan: kirjain nousee ja
# laskee 128 kehyksen jaksolla), jakso WAVE_COLS saraketta. Aalto on kiinni tekstissä (sarake b pitää siirtonsa
# karkeassa askeleessa), joten karkea askel ei piirrä sarakkeita uudelleen.
# TB_N on jakson monikerta: aalto jatkuu puskurin kierron yli. Siirto 1..6 (keskellä 3,5 +- 2,5): rivit 0 ja 31 tyhjiä.
WAVE_N, WAVE_COLS, WAVE_MID, WAVE_A, WAVE_DP = 256, 24, 3.5, 2.5, 2
TB_N = 2 * WAVE_COLS          # kiertävän puskurin sarakkeet: 40 ruudulla + seuraava + vara (X0 $6000-$65ff, 192 merkkiä)


def wave() -> list[int]:
    return [round(WAVE_MID + WAVE_A * math.sin(2 * math.pi * i / WAVE_N)) for i in range(WAVE_N)]


# sarakkeiden vaiheen hienosäätö (+-4 / 256 jaksosta, ei näy aallon muodossa): portaat osuvat eri kehyksille, joten
# pystyliikettä on 124 kehyksessä 128:sta (ilman säätöä 64) ja enintään 4 porrasta jakson sarakkeissa kehyksessä;
# haettu satunnaishaulla (siemen 1, 20 000 kierrosta)
WAVE_JIT = [-3, 4, 2, -4, 4, 2, 3, 0, 4, -3, -2, -1, 4, -4, 0, -2, -2, 4, 1, -4, -4, -1, 0, 2]


def wave_cph() -> list[int]:
    """puskurin sarakkeen vaihe (0..255); sarakkeet b ja b + WAVE_COLS samassa vaiheessa"""
    out = [(round(WAVE_N * (c % WAVE_COLS + 0.5) / WAVE_COLS) + WAVE_JIT[c % WAVE_COLS]) % WAVE_N for c in range(TB_N)]
    assert len(set(out[:WAVE_COLS])) == WAVE_COLS
    return out


def wave_steps(wv: list[int]) -> tuple[list[int], list[int]]:
    """aallon portaat: indeksit s, joissa wv[s] != wv[s - 1], ja arvot wv[s] (init laajentaa taulun)"""
    st = [s for s in range(WAVE_N) if wv[s] != wv[s - 1]]
    assert all(abs(wv[s] - wv[s - 1]) == 1 for s in st) and min(wv) >= 1 and max(wv) + GLYPH_H <= 31
    return st, [wv[s] for s in st]


# ---------------------------------------------------------------- spritet
UNEXP = 0                     # pinot 0..UNEXP-1 laajentamattomia (metadata laajentamattomat_pinot, latvukset)
TXT_ROWS = (92, 128)           # spritedatan rivit tekstikaistan kohdalla (ruudun rivi = data-rivi + 1)


def clean_text_band(img: np.ndarray) -> np.ndarray:
    """Tekstikaistan kohdalla runko on yhtenäinen pystypylväs: oksantyngät (sarakkeet, joissa pikseleitä alle
    puolella riveistä) pois ja rungon sarakkeiden aukot rungon värillä. Muuten oksien mustat pikselit
    pilkkovat kirjaimia ja kirjaimesta jää yksittäisiä pikseleitä rungon päälle (kehys 4900)."""
    out = img.copy()
    a, b = TXT_ROWS
    band = out[a:b]
    core = (band != 0).mean(0) >= 0.5
    band[:, ~core] = 0
    band[:, core] = np.where(band[:, core] == 0, 2, band[:, core])
    return out


def sprite_blocks(variants: dict) -> tuple[dict, list[bytes]]:
    blocks, index, ptrs = [], {}, {}
    for name, img in variants.items():
        img = clean_text_band(img)
        if img.shape != (SPR_N * SPR_H, 12):
            raise SystemExit(f"runko {name}: {img.shape}, pitää olla ({SPR_N * SPR_H}, 12)")
        p = []
        for k in range(SPR_N):
            b = bytearray()
            for y in range(SPR_H):
                row = img[k * SPR_H + y]
                for c in range(3):
                    b.append(mc_byte(row[c * 4:c * 4 + 4]))
            b.append(0)
            b = bytes(b)
            if b not in index:
                index[b] = len(blocks)
                blocks.append(b)
            p.append(index[b])
        ptrs[name] = p
    return ptrs, blocks


SH_K = 16                     # varjon kaltevuuksia
SH_M = 1.55                   # suurin kaltevuus hires px/rivi (noin 57 astetta pystystä; 24 rivillä mahtuu spriteen)
SH_XV = 194                   # aurinko (hires, näkyvän alueen vasemmasta reunasta): varjot osoittavat poispäin siitä
SH_R = 60                     # kaltevuus (tyvi - SH_XV) / SH_R: auringon kohdalla pysty, sivuilla pitkät viistot
SH_ROWS = 12                  # data-rivejä, Y-laajennettuna 24 riviä: tien rivit 227-250 alareunaan asti


def shadow_frames() -> tuple[list[bytes], list[int]]:
    """Runkojen varjot tiellä: X- ja Y-laajennettu hires-sprite (24 data-px = 48 hires, SH_ROWS data-riviä = 24
    riviä, tien yläreunasta ruudun alareunaan). Kehys k: kaltevuus m = -SH_M..SH_M hires px/rivi, nauha levenee
    3 -> 5 data-px (lähempänä leveämpi). Palauttaa lohkot ja yläreunan keskikohdan data-px:nä (spriten X = rungon
    tyvi - 2 * keski)."""
    blocks, tops = [], []
    for k in range(SH_K):
        m = -SH_M + 2 * SH_M * k / (SH_K - 1)
        rows = []
        for r in range(SH_ROWS):
            y = 2 * r + 1                              # näyttörivi data-rivin keskellä
            c = y * m / 2                              # data-px (X-laajennus: data-px = 2 hires)
            w = 3 + 2 * r / (SH_ROWS - 1)
            rows.append((c - w / 2, c + w / 2))
        lo = min(a for a, _ in rows)
        hi = max(b for _, b in rows)
        off = (24 - (hi - lo)) / 2 - lo                # keskitetään spriteen
        img = np.zeros((21, 24), np.uint8)             # rivit SH_ROWS.. tyhjiä (reunuksessa)
        for r, (a, b) in enumerate(rows):
            for x in range(24):
                if a + off <= x + 0.5 < b + off:
                    img[r, x] = 1
        b = bytearray()
        for r in range(21):
            for c in range(3):
                v = 0
                for bit in range(8):
                    v = v << 1 | int(img[r, c * 8 + bit])
                b.append(v)
        b.append(0)
        blocks.append(bytes(b))
        tops.append(round(off))
    return blocks, tops


def shadow_tables(tops: list[int]) -> list[str]:
    """sh_k[(tyvi + 32) >> 3]: kaltevuuskehys rungon tyven paikasta; sh_off[k]: spriten X = tyvi + 24 - sh_off."""
    ks = []
    for i in range(56):
        base = i * 8 - 32 + 4
        m = max(-SH_M, min(SH_M, (base - SH_XV) / SH_R))
        ks.append(round((m + SH_M) / (2 * SH_M) * (SH_K - 1)))
    return asm_bytes("sh_k", ks) + asm_bytes("sh_off", [2 * t for t in tops])


CORNER_R = 12                 # pyöristetyn alakulman säde (hires px)
CORNER_CH = 24                # alakulmien merkit merkistössä R (tien merkit 0-23, $5900- spritejä)


def corner_cells() -> list[tuple[int, list[int]]]:
    """Alakulmat tien merkeissä (eivät spriteinä): kehys.kulmamaski kuten spritellä
    (vasen X 31, oikea X 311, rivit 231-251) 38 sarakkeen tilassa, $D016 = $10 (sarake c = X 24 + 8c). Solut, joihin
    kaari osuu: (ruudun sarake, 8 rivin MC-maski, %11 = värimuisti musta). MC-pari on musta, jos sen yksikin
    näkyvä hires-pikseli on mustan alueella (kaari ei pienene)."""
    hx = np.zeros((256, 400), bool)                     # rasteri, X (spritekoordinaatit)
    for oikea, x0 in ((False, 31), (True, 311)):
        m = kehys.kulmamaski(CORNER_R, oikea, True)
        hx[231:252, x0:x0 + 24] |= m
    hx[:, :31] = hx[:, 335:] = False                    # 38 sarakkeen reunus
    out = []
    for c in range(40):
        rows = []
        for ll in range(8):
            line = 227 + 16 + ll                        # tien merkkirivi 24 (rasterit 243-250)
            v = 0
            for p in range(4):
                x = 24 + 8 * c + 2 * p
                v = v << 2 | (3 if hx[line, x:x + 2].any() else 0)
            rows.append(v)
        if any(rows):
            out.append((c, rows))
    if hx[227:243].any():
        raise SystemExit("alakulma ulottuu tien merkkiriville 23 (vain rivi 24 tuettu)")
    if len(out) > 8:
        raise SystemExit(f"alakulmien soluja {len(out)}, merkistössä R tilaa 8")
    return out


# lenkkeilijä ja koira: sprite 1 tien riveillä, kuva lenkkeilija.py
JOG_Y = 225                   # kuten pyöräilijä: rivit 226-246
JOG_V = 2                     # hires px/kehys vasemmalle: juoksee maata vasten noin 1,2 (pyöräilijä 2,2 ohittaa)


def jogger_consts() -> list[str]:
    """Askelparin kehysvauhti maan nopeudesta: maa kosketusrivillä ROAD_V:n mukaan, lenkkeilijä JOG_V, joten jalat
    kulkevat maata vasten (tie - JOG_V) px/kehys; askelpari = lenkkeilija.STRIDE px."""
    y = JOG_Y + 1 + lenkkeilija.GROUND - 227
    v = ROAD_V[0] + (ROAD_V[1] - ROAD_V[0]) * y / 23 - JOG_V
    return [f"JOG_Y = {JOG_Y}", f"JOG_V = {JOG_V}",
            f"JOG_DPH = {round(256 * lenkkeilija.FRAMES * v / lenkkeilija.STRIDE)}"]


# pyöräilijä: sprite 0 tien riveillä, kuva pyorailija.py
CYC_Y = 225                   # spriten Y: rivit 226-246 (koko ajaja tiellä; pientareen tumma kuvio söisi pään)
CYC_V = 1                     # hires px/kehys vasemmalle (rungot 2 ja 1,5, tie kosketusrivillä noin 3)


def cyclist_consts() -> list[str]:
    """Kammen kehysvauhti maan nopeudesta: tie liikkuu kosketusrivillä ROAD_V:n mukaan, pyöräilijä CYC_V, joten
    pyörä vierii (tie - CYC_V) px/kehys; pyörän kehä pi * 2 * ry, kammen kierros = GEAR pyörän kierrosta."""
    y = CYC_Y + 1 + pyorailija.H - 1 - 227               # pyörän kosketusrivi tien rivinä (tie alkaa riviltä 227)
    v = ROAD_V[0] + (ROAD_V[1] - ROAD_V[0]) * y / 23 - CYC_V
    crank = pyorailija.GEAR * math.pi * 2 * pyorailija.R_FRONT[1] / v
    return [f"CYC_Y = {CYC_Y}", f"CYC_V = {CYC_V}", f"CYC_DPH = {round(256 * pyorailija.FRAMES / crank)}"]


def place_sprites(blocks: list[bytes]) -> tuple[list[int], list[tuple[int, bytes]]]:
    """Lohkot vapaisiin spritealueisiin: palauttaa osoittimet ja (osoite, data)."""
    slots = [a for lo, hi in SPR_AREAS for a in range(lo, hi, 64)]
    if len(blocks) > len(slots):
        raise SystemExit(f"spritelohkoja {len(blocks)}, paikkoja {len(slots)}")
    return [(slots[i] - BANK) // 64 for i in range(len(blocks))], [(slots[i], b) for i, b in enumerate(blocks)]


# ---------------------------------------------------------------- rivien näyttömuisti
FLIPS = [SPR_R0 + SPR_H * k - 1 for k in range(1, SPR_N)]


def row_screen(r: int) -> int:
    """Merkkirivin r badlinen c-access-hetkellä aktiivinen ruutu (0 = S0, 1 = S1)."""
    bl = SCR0 + 8 * r
    return sum(1 for f in FLIPS if f < bl) & 1


def band_of_line(s: int) -> str:
    for n, (top, h, _) in BANDS.items():
        if top <= s < top + h:
            return n
    return "tie"


# ---------------------------------------------------------------- kerneli
def d018(screen: int, cset: str) -> int:
    return ((S0 if screen == 0 else S1) - BANK) // 0x400 << 4 | (CS[cset] - BANK) // 0x800 << 1


def road_filler() -> list:
    """Kernelin täyte: tien rivin 8.8-akku (ei haaroja, syklit tarkat) ja rivin 8 tavua siirtotaulusta
    (Y = rox_t+y). Tie näkyy kernelin jälkeen (rivit 227-250), joten merkit päivitetään kernelin tyhjäkäynnissä."""
    out = []
    for y in range(24):
        out.append([(f"lda racc_lo+{y}", None), ("clc", None), (f"adc #<RVEL{y}", None), (f"sta racc_lo+{y}", None)])
        out.append([(f"lda racc_hi+{y}", None), (f"adc #>RVEL{y}", None), ("and #31", None), (f"sta racc_hi+{y}", None)])
        out.append([(f"ldx racc_hi+{y}", None), ("lda ox32,x", None), (f"sta rox_t+{y}", None)])  # ei A:ta edellisestä
                                                                # (kiinteä tai joustava toimi voi tulla väliin)
    corners = corner_cells()
    for y in range(24):
        r, ll = y // 8, y % 8
        out.append([(f"ldy rox_t+{y}", None)])
        for j in range(8):
            item = [(f"lda road_tab_{y}+{j},y", None), (f"sta ${CS['R'] + (ROAD_BASE[r] + j) * 8 + ll:04x}", None)]
            for k, (c, rows) in enumerate(corners):     # alakulman solu (rivi 24, sarake c): sama tavu + musta kaari
                if r == 2 and c % 8 == j:
                    if any(a.startswith("ora") for a, _ in item):
                        item.append(item[0])
                    if rows[ll]:
                        item.append((f"ora #${rows[ll]:02x}", None))
                    item.append((f"sta ${CS['R'] + (CORNER_CH + k) * 8 + ll:04x}", None))
            out.append(item)
    return out


def kernel(d21: np.ndarray, sprite_rows: list[dict], start: tuple[int, int],
           filler: list | None = None) -> tuple[list[str], dict]:
    """Rivikohtainen kerneli rasteririveille 45..FLIPS[-1]. Jokainen rivi alkaa vapautuskäskyllä, joka
    pysähtyy edellisen rivin syklissä 55 (spritejen BA) ja kirjoittaa $D021:n tämän rivin vasempaan
    reunaan. Badlinea edeltävällä rivillä 'paikka' kirjoittaa X:n (badlinen $D021 tai saumassa $D018)
    badlinen syklissä 12. Muut kirjoitukset rivin keskellä (näkyvät vasta seuraavalla rivillä tai
    yksivärisellä saumarivillä)."""
    for f in FLIPS:
        if badline(f):
            raise SystemExit(f"spritepinon vaihtorivi {f} on badline")
    sim = Sim(*start)
    g = Gen(sim)
    last = FLIPS[-1]
    nlines = 129
    d21c = [int(v) for v in d21[:nlines]]

    def d21_of(line):
        s = line - SCR0
        return d21c[s] if 0 <= s < nlines else None

    # kiinteät toimet riveittäin: (asm-lista, rekisterit kirjoituksille)
    fixed: dict[int, list] = {}
    seams = {SCR0 + 79: "maet", SCR0 + 95: "teksti", SCR0 + 127: "kaupunki"}
    slot_d018 = {}
    for line, nb in seams.items():
        acts = [(f"lda z_dx_{nb}", None), ("sta $d016", "d016"),
                (f"lda #{BAND_COLS[nb]['d022']}", "fade"), ("sta $d022", "d022"),
                (f"lda #{BAND_COLS[nb]['d023']}", "fade"), ("sta $d023", "d023")]
        fixed.setdefault(line, []).extend(acts)
        if BANDS[nb][2] != BANDS[band_of_line(line - SCR0)][2]:
            slot_d018[line] = nb
    for k, f in enumerate(FLIPS, 1):
        acts = [(f"lda z_d18f{k}", None), ("sta $d018", "d018f")]
        for reg in ("d025", "d026"):
            if sprite_rows[k][reg] != sprite_rows[k - 1][reg]:
                acts += [(f"lda #{sprite_rows[k][reg]}", "fade"), (f"sta ${reg}", reg)]
        if k == UNEXP:                  # laajentamattomat latvuspinot loppuvat: X-laajennus päälle (tyhjä rivi)
            acts += [("lda #$ff", None), ("sta $d01d", "d01d")]
        fixed.setdefault(f, []).extend(acts)
    # joustavat: rivin k+1 Y ja osoittimet rivin k aikana
    flex = []
    for k in range(SPR_N - 1):
        r0, r1 = SPR_R0 + SPR_H * k, SPR_R0 + SPR_H * (k + 1) - 2
        y = SPR_R0 + SPR_H * (k + 1) - 1
        flex.append((r0, r1, [(f"lda #{y}", None)] + [(f"sta $d0{2 * i + 1:02x}", "y") for i in range(4)]))
        flex.append((r0, r1, [(f"lda #{y}", None)] + [(f"sta $d0{2 * i + 1:02x}", "y") for i in range(4, 8)]))
        scr = S0 if (k + 1) % 2 == 0 else S1
        for i in range(8):
            flex.append((r0, r1, [(f"lda ptrtab+{8 * (k + 1) + i}", None), (f"sta ${scr + 0x3f8 + i:04x}", "ptr")]))

    def act_cycles(acts):
        return sum(len(PAT[mode_of(a)]) for a, _ in acts)

    def end_seq(line):
        """Rivin loppujakso: (esilataukset, kohde (rivi, sykli), tallennukset, seuraava käsiteltävä rivi)."""
        nxt = line + 1
        if badline(nxt):
            after = nxt + 1
            slot = None
            if line in slot_d018:
                slot = ("ldx z_d18s_" + slot_d018[line], "d018s")
                if d21_of(nxt) is not None and d21_of(nxt) != d21_of(line):
                    raise SystemExit(f"sauma {line}: $D021 vaihtuu badlinella {nxt} ($D018-paikka varattu)")
            elif d21_of(nxt) is not None and d21_of(nxt) != d21_of(line):
                slot = (f"ldx fmap+{d21_of(nxt)}", f"d021:{nxt}")
            pre = [(slot[0], None, "")] if slot else []
            na = d21_of(after)
            if na is not None and after <= last:
                pre.append((f"lda fmap+{na}", None, ""))
            stores = []
            if slot:
                reg = "d018" if slot[1].startswith("d018") else "d021"
                stores.append((f"stx ${reg}", slot[1], f"paikka badline {nxt}"))
            if na is not None and after <= last:
                stores.append(("sta $d021", f"d021:{after}", f"vapautus {after}"))
            elif after <= last:
                stores.append(("nop", None, f"vapautus {after}"))
            return pre, (line, 53 if slot else 54), stores, after
        na = d21_of(nxt)
        if na is not None and na != d21_of(line):
            return ([(f"lda fmap+{na}", None, "")], (line, 54),
                    [("sta $d021", f"d021:{nxt}", f"vapautus {nxt}")], nxt)
        return [], (line, 54), [("nop", None, f"vapautus {nxt}")], nxt

    def end_gap(acts, line):
        if line == last:
            return None
        t = Sim(sim.line, sim.cyc)
        pre, target, _, _ = end_seq(line)
        for a, _ in acts:
            t.run(PAT[mode_of(a)])
        for a, _, _ in pre:
            t.run(PAT[mode_of(a)])
        while ba_low(t.line, t.cyc):
            t.step()
        return (target[0] - t.line) * 63 + target[1] - t.cyc

    # prologi: rivin 51 arvot ylärajan alla, sitten vapautus riville 52
    g.lines.append("; prologi (ylärajan alla): kaistan taivas rekisterit")
    for a, r in [("lda z_dx_taivas", None), ("sta $d016", "d016"), (f"lda #{d018(0, 'A')}", None),
                 ("sta $d018", "d018"), (f"lda #{BAND_COLS['taivas']['d022']}", "fade"), ("sta $d022", "d022"),
                 (f"lda #{BAND_COLS['taivas']['d023']}", "fade"), ("sta $d023", "d023"),
                 (f"lda fmap+{d21c[0]}", None), ("sta $d021", "d021:51")]:
        g.i(a, r)
    g.i(f"lda fmap+{d21c[1]}")
    g.pad_to(SCR0, 10)             # vapautuskäsky: op 51:10, lo 51:11, hi pysähtyy (badline) -> 52:11, W 52:12
    g.i("sta $d021", "d021:52", "vapautus 52")
    line = SCR0 + 1
    while line <= last:
        if badline(line):
            line += 1
            continue
        g.lines.append(f"; ---- rivi {line} (ruutu {line - SCR0})")
        cap_end = 44 if badline(line + 1) else 49     # toimet ennen loppujaksoa (lataukset + vapautus)
        acts = list(fixed.get(line, []))
        budget = cap_end - sim.cyc - act_cycles(acts)
        if budget < 0:
            raise SystemExit(f"rivi {line}: kiinteät toimet eivät mahdu ({act_cycles(acts)} sykliä)")
        took_flex = []
        for item in list(flex):
            r0, r1, fa = item
            if r0 <= line <= r1 and act_cycles(fa) <= budget:
                acts += fa
                budget -= act_cycles(fa)
                flex.remove(item)
                took_flex.append(item)
        for r0, r1, fa in flex:
            if line > r1:
                raise SystemExit(f"joustava toimi myöhästyi rivillä {line}: {fa}")
        took = []
        while filler and act_cycles(filler[0]) <= budget:
            budget -= act_cycles(filler[0])
            took.append(filler.pop(0))
            acts += took[-1]
        # loppujakson täyte ei saa olla 1 sykli: palauta täytettä jonoon, sitten joustava toimi seuraavalle
        # riville (jos sen ikkuna sallii); viimeisenä vapautuskäsky sykliin 55 (pysähtyy, kirjoitus syklissä 14)
        late = False
        while True:
            n = end_gap(acts, line)
            if n is None or n >= 0 and n != 1:
                break
            if took:
                back = took.pop()
                del acts[len(acts) - len(back):]
                filler.insert(0, back)
                continue
            mv = [it for it in took_flex if it[1] > line]
            if mv:
                it = mv[-1]
                took_flex.remove(it)
                for a in reversed(it[2]):                # toimi pois tämän rivin listasta (viimeinen esiintymä)
                    del acts[len(acts) - 1 - acts[::-1].index(a)]
                flex.insert(0, it)
                continue
            if not badline(line + 1):
                late = True
                break
            raise SystemExit(f"rivi {line}: loppujakson väli {n} sykliä")
        for a, r in acts:
            g.i(a, r)
        if line == last:
            break
        pre, target, stores, line = end_seq(line)
        for a, r, note in pre:
            g.i(a, r, note)
        if late:
            target = (target[0], target[1] + 1)
        g.pad_to(*target)
        for a, r, note in stores:
            g.i(a, r, note)
    if flex:
        raise SystemExit(f"joustavia toimia jäi: {flex}")
    if filler:
        raise SystemExit(f"kernelin täytettä jäi {len(filler)} osaa (tie ei mahdu)")
    return g.lines, {"writes": sim.writes, "end": sim.pos(), "fsites": g.fsites}


def check_writes(writes) -> list[str]:
    """Ikkunat: $D021 rivin L arvo rivin L-1 oikeassa reunassa (56-63) tai rivin L vasemmassa (1-15);
    $D018-paikka saumassa: saumarivin 55-63 tai badlinen 1-14; vaihto (d018f) rivin keskellä 11-54."""
    out = []
    for reg, line, cyc in writes:
        if reg.startswith("d021:"):
            tl = int(reg[5:])
            ok = (line == tl - 1 and cyc >= 56) or (line == tl and cyc <= 15)
            if tl == SCR0:
                ok = line < SCR0
            if not ok:
                out.append(f"{reg} kirjoitus {line}:{cyc}")
        elif reg == "d018s":
            pass
        elif reg == "d018f" and not (11 <= cyc <= 54):
            out.append(f"d018 vaihto {line}:{cyc}")
    return out


# ---------------------------------------------------------------- kaistojen siirtokoodi
def copy_code(name: str, band: dict, screen_rows: list[int]) -> list[str]:
    """copy_<nimi> (X = karkea paikka q): kaistan rivit ruutuun ja solukohtaiset väririvit värimuistiin, sarake
    kerrallaan (lda kartta,x / sta kohde,y; X = q + c <= W + 38 < 256), noin 9 sykliä/tavu. Staattinen koodi
    (ei generointia C64:llä). copys_<nimi> = vain ruutu (init: kodin kuva näkyy vielä, värit greetsit_go:ssa)."""
    top = BANDS[name][0] // 8
    assert band["cols"] + COLS <= 256
    scr = [(f"map_{name}_{r}", (S0 if screen_rows[top + r] == 0 else S1) + 40 * (top + r)) for r in range(band["rows"])]
    col = [(f"col_{name}_{r}", 0xd800 + 40 * (top + r)) for r in range(band["rows"]) if band["row_cols"][r] is None]

    def loop(pairs, mask=False):
        out = ["        ldy #0"]
        for k, (src, dst) in enumerate(pairs):
            out.append(f"{'-' if k == 0 else ' '}       lda {src},x")
            if mask:                                    # häivytys: solukohtaiset värit mustiksi (fade_sites)
                out += ["        and #$0f", f"fm_{src} = * - 1"]
            out.append(f"        sta ${dst:04x},y")
        return out + ["        inx", "        iny", f"        cpy #{COLS}", "        bne -"]
    out = [f"copy_{name}"]
    if not col:
        return out + [f"copys_{name}"] + loop(scr) + ["        rts"]
    # Värit: copyp_<nimi> (täysi väri, ei maskia: ei lisäsyklejä kopion kehykseen) tai häivytyksen aikana copym_<nimi>
    # (and #maski); fade_sites vaihtaa hypyn (fj_<nimi>). copyc_<nimi>: vain värit maskilla (häivytyksen fj_city).
    return (out + [f"        jmp copyp_{name}", f"fj_{name} = * - 2", f"copys_{name}"] + loop(scr) + ["        rts",
            f"copyp_{name}", "        stx sq"] + loop(col) + ["        ldx sq", f"        jmp copys_{name}",
            f"copym_{name}", f"        jsr copyc_{name}", f"        jmp copys_{name}",
            f"copyc_{name}", "        stx sq"] + loop(col, True) + ["        ldx sq", "        rts"])


def bands_code(names) -> list[str]:
    """bands_step: kaistan 8.8-paikka 0..2047 (8 px); ylitys = karkea askel ja kopio; $D016 = $10 | 7 - px."""
    out = ["bands_step"]
    for b in names:
        out += ["        clc", f"        lda pos_{b}", f"        adc #<V_{b}", f"        sta pos_{b}",
                f"        lda pos_{b}+1", f"        adc #>V_{b}", "        cmp #8", f"        bcc _ns_{b}",
                "        and #7", f"        sta pos_{b}+1", f"        ldx q_{b}", "        inx", f"        cpx #W_{b}",
                "        bcc +", "        ldx #0", f"+       stx q_{b}", f"        jsr copy_{b}", f"        lda pos_{b}+1",
                f"_ns_{b}", f"        sta pos_{b}+1", "        eor #7", "        ora #$10", f"        sta z_dx_{b}"]
    out.append("        rts")
    return out


# ---------------------------------------------------------------- häivytys mustasta ja mustaan
# Sisääntulo häivytyksenä mustasta (kuva ei lävähdä suoraan ruutuun). Kun viimeinen nimi on mennyt vasemmalta ulos
# (FD_OUT), kuva häivytetään samoilla tasoilla mustaan (F_OUT kehystä tasolta).
# Taso L = 0 (täysi väri) .. FD_N (musta): jokainen värivakio (kernelin ja IRQ:iden operandit, $D021-rivitaulu,
# värimuisti, runkojen värit) kulkee lumaketjua (kehys.LUMA_DOWN) pitkin niin, että värin luma on noin
# luma * (FD_N - L) / FD_N. Väri vaihtuu reaaliajassa (fade_run, greetsit.asm): taso vaihtuu F_IN kehyksen välein,
# ja tason työ (fj_*) tehdään kernelin ulkopuolella (fd_time) yhdessä tai kahdessa kehyksessä. Kerneli lukee rivien
# $D021-värit suoraan tason kartasta (lda fmap+väri), joten taivaan ja järven rivit vaihtuvat heti kartan mukana.
FD_N, F_IN, F_OUT = 8, 4, 3
LUMA = {0: 0, 6: 1, 9: 1, 2: 2, 11: 2, 4: 3, 8: 3, 12: 4, 14: 4, 5: 5, 10: 5, 3: 6, 15: 6, 7: 7, 13: 7, 1: 8}
# värimuisti on 0-7: oma ketju (valkoinen aurinko ja teksti keltaisen ja punaisen kautta)
LUMA_DOWN7 = [0, 7, 0, 5, 6, 4, 0, 2]
CRAM_CHUNK = 6                # värimuistin vakiorivejä yhdessä työssä (noin 1 600 sykliä)
FADE_ASM_SITES = 13 + 15      # greetsit.asm fade_asm (13 operandia ja runkojen värit, noin 120 sykliä)
FD_LINE = 50                  # työn kesto riveinä: syklejä rivillä (varovainen: tien spritet, IRQ:t)


def fade_col(c: int, lv: int, down: list[int]) -> int:
    """väri c tasolla lv: ketjun väri, jonka luma on lähinnä luma(c) * (FD_N - lv) / FD_N (tasapelissä tummempi)"""
    chain = [c]
    while chain[-1]:
        chain.append(down[chain[-1]])
    t = LUMA[c] * (FD_N - lv) / FD_N
    return min(chain, key=lambda v: (abs(LUMA[v] - t), LUMA[v]))


def fade_tables() -> tuple[list[int], list[int], list[int]]:
    """fade_tab ja fadec_tab ((FD_N + 1) x 16: rekisterit ja värimuisti, MC-bitti säilyy) ja fmask_tab: solukohtaiset
    värit (and #maski) ovat täysiä, kunnes ne ketjussa muuttuisivat mustiksi"""
    reg, cram, mask = [], [], []
    for lv in range(FD_N + 1):
        reg += [fade_col(c, lv, kehys.LUMA_DOWN) for c in range(16)]
        cram += [(v & 8) | fade_col(v & 7, lv, LUMA_DOWN7) for v in range(16)]
        mask.append(0x0f if fade_col(6, lv, LUMA_DOWN7) else 0x08)
    return reg, cram, mask


def check_mask(percell_vals: set[int], cram: list[int], mask: list[int]):
    for lv in range(FD_N + 1):
        for v in percell_vals:
            if cram[16 * lv + v] != v & mask[lv]:
                raise SystemExit(f"häivytys: solukohtainen väri {v} tasolla {lv} ei ole maskattavissa "
                                 f"({cram[16 * lv + v]} != {v & mask[lv]})")


def fade_code(ksites: list, csites: list, msites: list, cram_rows: dict[int, int]) -> list[str]:
    """fade_sites: operandit tason kartoista (fmap rekistereille, fmapc värimuistille, fmask solukohtaisille), sitten
    greetsit.asm:n IRQ-vakiot (fade_asm). color_u ja fj_c*: värimuistin vakiorivit. fj_city: solukohtaiset värit, vain
    kun maski muuttui. Työt järjestyksessä fj_lo/fj_hi (FJ_N), kesto riveinä fj_rows."""
    out = ["fade_sites"]
    for lab, c in ksites:
        out += [f"        lda fmap+{c}", f"        sta {lab}"]
    for lab, v in csites:
        out += [f"        lda fmapc+{v}", f"        sta {lab}"]
    if msites:
        out.append("        lda fmask")
        out += [f"        sta {lab}" for lab in msites]
        out += ["        ldx #<copym_kaupunki", "        ldy #>copym_kaupunki", "        cmp #$0f",
                "        bne +", "        ldx #<copyp_kaupunki", "        ldy #>copyp_kaupunki",
                "+       stx fj_kaupunki", "        sty fj_kaupunki+1"]
    out.append("        jmp fade_asm")
    jobs = ["fade_sites"]
    cyc = [8 * (len(ksites) + len(csites) + FADE_ASM_SITES) + 5 * len(msites) + 20]
    jobs.append("color_u")                              # värimuistin ylimmät vakiorivit (operandit yllä)
    cyc.append(4 * 40 * COLOR_UNROLL + 30)
    rows = sorted(cram_rows)
    for k in range(0, len(rows), CRAM_CHUNK):
        part = rows[k:k + CRAM_CHUNK]
        jobs.append(f"fj_c{k // CRAM_CHUNK}")
        out += [jobs[-1], "        ldx #39"]
        first = True
        for v in sorted({cram_rows[r] for r in part}):
            out.append(f"{'-' if first else ' '}       lda fmapc+{v}")
            first = False
            out += [f"        sta ${0xd800 + 40 * r:04x},x" for r in part if cram_rows[r] == v]
        out += ["        dex", "        bpl -", "        rts"]
        cyc.append(40 * (4 * len({cram_rows[r] for r in part}) + 5 * len(part) + 5) + 20)
    if msites:
        jobs.append("fj_city")
        cyc.append(COLS * (12 * len(msites) // 2 + 9) + 60)
        out += ["fj_city lda fmask", "        cmp fd_cm", "        beq +", "        sta fd_cm",
                "        ldx q_kaupunki", "        jsr copyc_kaupunki", "+       rts"]
    out.append("fj_lo   .byte " + ",".join(f"<{j}" for j in jobs))
    out.append("fj_hi   .byte " + ",".join(f">{j}" for j in jobs))
    out.append("fj_rows .byte " + ",".join(str(-(-c // FD_LINE) + 2) for c in cyc))   # kesto riveinä (fd_time)
    out.append(f"FJ_N = {len(jobs)}")
    return out


def dycp_code() -> list[str]:
    """Skrollerin piirtorungot: dycp_g<ryhmä> piirtää yhden sarakkeen (X = sarakkeen tasoindeksi,
    Y = 32 * (b % 8) + siirto). Ryhmän g (puskurin sarakkeet 8g..8g+7) merkit ovat sivulla X0 + 256g, joten kohde
    sta sivu + j,y ei ylitä sivua. Taulut dyg_lo/dyg_hi (rungon osoite sarakkeittain) ja dy_yo."""
    out = []
    for g in range(TB_N // 8):
        out.append(f"dycp_g{g}")
        for j in range(GLYPH_H):
            out.append(f"        lda plane{j},x")
            out.append(f"        sta ${CS['X0'] + 256 * g + j:04x},y")
        out.append("        rts")
    out.append("dyg_lo  .byte " + ",".join(f"<dycp_g{c // 8}" for c in range(TB_N)))
    out.append("dyg_hi  .byte " + ",".join(f">dycp_g{c // 8}" for c in range(TB_N)))
    yo = [32 * (c % 8) for c in range(TB_N)]             # sarakkeen alku; aallon siirto lisätään ajossa
    out.append("dy_yo   .byte " + ",".join(str(v) for v in yo))
    return out


def text_rows_code(ts: list[int]) -> list[str]:
    """text_rows (X = tb): tekstikaistan ruuturivit kiertävästä puskurista, ruudun sarake c näyttää puskurin sarakkeen
    (tb + c) mod TB_N, merkit 4b + k (rivi k). Ajetaan karkeassa askeleessa kehyksen logiikassa (kaista on näytetty)."""
    return ["text_rows",
            "        txa",
            "        clc",
            "        adc #<rot4",
            "        sta _r + 1",
            "        lda #>rot4",
            "        adc #0",
            "        sta _r + 2",
            "        ldx #39",
            "_r      lda rot4,x",
            f"        sta ${ts[0]:04x},x",
            "        ora #1",
            f"        sta ${ts[1]:04x},x",
            "        eor #3",
            f"        sta ${ts[2]:04x},x",
            "        ora #1",
            f"        sta ${ts[3]:04x},x",
            "        dex",
            "        bpl _r",
            "        rts"] + asm_bytes("rot4", [4 * (i % TB_N) for i in range(TB_N + 40)], 48)


def wave_code(wv: list[int]) -> list[str]:
    """kulkevan aallon taulut (GREETSIT3, greetsit.asm wave_init, vis_put, col_draw)"""
    st, sv = wave_steps(wv)
    cph = wave_cph()
    inv = [255] * WAVE_N                              # vaihe -> sarake 0..WAVE_COLS-1 (sarake + WAVE_COLS samassa vaiheessa)
    for c in range(WAVE_COLS):
        inv[cph[c]] = c
    pg = [(CS["X0"] >> 8) + c // 8 for c in range(TB_N)]
    # taulut valmiina, joten greetsit_init ei laske niitä (init noin 2 kehystä)
    return (["cph     .byte " + ",".join(str(v) for v in cph),
             "wst_i   .byte " + ",".join(str(v) for v in st),
             f"WST_N = {len(st)}",
             f"GLYPH_H = {GLYPH_H}", f"WAVE_COLS = {WAVE_COLS}", f"WAVE_DP = {WAVE_DP}", f"TB_N = {TB_N}",
             f"TXT_V = {TXT_V}"]
            + asm_bytes("wv_sin", wv, 64) + asm_bytes("wv_inv", inv, 64) + asm_bytes("wv_pg", pg, 48))


# ---------------------------------------------------------------- pää
BAND_COLS: dict = {}


def asm_bytes(label: str, data, per=32) -> list[str]:
    data = bytes(data)
    out = [label]
    for i in range(0, len(data), per):
        out.append("        .byte " + ",".join(f"${b:02x}" for b in data[i:i + per]))
    return out


def stagger(speeds: dict, frames: int = 2048) -> dict:
    """Kaistojen alkuvaiheet (8.8) niin, että karkeat askeleet eivät osu samaan kehykseen eivätkä skrollerin
    karkeaan askeleeseen (frame_logicin kutsu f = 0, 1, ...: tpos = TXT_V * (f + 1), askel kun se ylittää 8:n
    monikerran; ruuturivien kierto ja uusi sarake)."""
    order = ["piennar", "kaupunki", "maet", "taivas"]
    taken: set[int] = {f for f in range(frames) if TXT_V * (f + 1) // 8 != TXT_V * f // 8}
    out = {}
    for n in order:
        v = round(speeds[n] * 256)
        best = None
        for p0 in range(0, 8 * 256, 16):
            steps = {f for f in range(frames) if (p0 + v * (f + 1)) // 2048 != (p0 + v * f) // 2048}
            hit = len(steps & taken)
            if best is None or hit < best[0]:
                best = (hit, p0, steps)
            if hit == 0:
                break
        out[n] = best[1]
        taken |= best[2]
    return out


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    st = sys.argv[sys.argv.index("--start") + 1] if "--start" in sys.argv else "46:10"
    start = tuple(int(v) for v in st.split(":"))            # kernelin ensimmäinen sykli (mitattu)
    d = load_data()
    meta = d["meta"]
    errs: list[str] = []
    check_seams(d, errs)
    for n in ("taivas", "maet", "kaupunki", "piennar", "tie"):
        BAND_COLS[n] = meta[n]
    BAND_COLS["teksti"] = {"d022": meta["teksti"]["d022"], "d023": meta["teksti"]["varjo"]}

    # merkistöt ja kartat
    csA, csT = Charset("A"), Charset("T")
    bands = {}
    for n in MAP_BANDS:
        img = d[n]
        if img.shape[0] != BANDS[n][1]:
            raise SystemExit(f"{n}: {img.shape[0]} riviä, pitää olla {BANDS[n][1]}")
        bands[n] = encode_band(n, img, meta[n], csA if BANDS[n][2] == "A" else csT, errs)
    screen_rows = [row_screen(r) for r in range(25)]

    # tie
    rimg = d["tie"]
    if rimg.shape != (24, ROAD_W):
        raise SystemExit(f"tie: {rimg.shape}, pitää olla (24, {ROAD_W})")
    road_tabs, road_asm = road_tables(asphalt(rimg, meta["tie"]), meta["tie"])

    # teksti
    # skrolleri alkaa tyhjänä ja ensimmäinen nimi liukuu sisään oikeasta reunasta: ruudun levyinen tyhjä alkuun
    # ja loppuun ruudun levyinen tyhjä: viimeisen nimen jälkeen kuva häivytetään mustaan, eikä kiertävä lista saa
    # tuoda ensimmäistä nimeä takaisin oikeasta reunasta ennen kohtauksen loppua
    cols = [bytes(GLYPH_H)] * 40 + text_columns(greets_text()) + [bytes(GLYPH_H)] * 40
    tcols = cols
    ntc = len(tcols)
    uniq = sorted(set(tcols), key=tcols.index)
    if len(uniq) > 256:
        raise SystemExit(f"erilaisia tekstisarakkeita {len(uniq)} (raja 256)")
    gid = [uniq.index(tcols[g % ntc]) for g in range(ntc + 40)]
    planes = [bytes(u[j] for u in uniq) for j in range(GLYPH_H)]
    wv = wave()

    # spritet
    R = d["rungot"]
    ptrs_v, blocks = sprite_blocks(R["variantit"])
    sh_blocks, sh_tops = shadow_frames()
    n_trunk_blocks = len(blocks)
    i_empty = n_trunk_blocks + len(sh_blocks)
    cyc_blocks = pyorailija.blocks()                    # viimeisinä: runkojen ja varjojen paikat ennallaan
    jog_blocks = lenkkeilija.blocks()
    blocks = blocks + sh_blocks + [bytes(64)] + cyc_blocks + jog_blocks
    blk_ptr, blk_data = place_sprites(blocks)
    vnames = list(R["variantit"])
    sprite_rows = meta["sprite_pinot"]
    own = meta["oma_vari"]

    # kerneli
    global UNEXP
    UNEXP = int(meta.get("laajentamattomat_pinot", 0))
    if UNEXP:
        for v, img in R["variantit"].items():
            if (img[SPR_H * UNEXP - 1] != 0).any():
                errs.append(f"runko {v}: pinon {UNEXP - 1} viimeinen rivi ei ole tyhjä ($D01D vaihtuu sillä)")
    klines, kinfo = kernel(d["d021"], sprite_rows, start, road_filler())
    errs += [f"kerneli: {e}" for e in check_writes(kinfo["writes"])]

    # askelvaiheet
    ph = stagger(SPEED)

    inc = []
    inc.append(f"; generoitu: src/proto/greetsit/build.py (data: {d['lahde']})")
    for k, v in CS.items():
        inc.append(f"CS_{k} = ${v:04x}")
    inc += [f"S0 = ${S0:04x}", f"S1 = ${S1:04x}", f"SCR0 = {SCR0}", f"SPR_R0 = {SPR_R0}", f"SPR_H = {SPR_H}",
            f"N_NEAR = {N_NEAR}", f"N_FAR = {N_FAR}", f"NTC = {ntc}", f"FLIP_LAST = {FLIPS[-1]}",
            f"KSTART = {start[1]}", f"KLINE = {start[0]}", f"COLS = {COLS}"]
    inc += cyclist_consts()
    inc += jogger_consts()
    inc.append(f"D18_A0 = ${d018(0, 'A'):02x}")
    for k in range(1, SPR_N):
        inc.append(f"FLIP{k}_SCR = {k & 1}")
        cs = BANDS[band_of_line(FLIPS[k - 1] - SCR0)][2]
        inc.append(f"D18F{k} = ${d018(k & 1, 'X0' if cs == 'X' else cs):02x}")
    for name in ("teksti", "kaupunki"):
        line = SCR0 + BANDS[name][0] - 1
        inc.append(f"SEAM_{name.upper()}_SCR = {sum(1 for f in FLIPS if f < line) & 1}")
    for n in ("A", "T", "R", "X0"):
        inc.append(f"CSB_{n} = ${(CS[n] - BANK) // 0x800 << 1:02x}")
    inc.append(f"ROAD_D018 = ${d018(0, 'R'):02x}")      # tie ja varjospritet ruudusta S0
    inc.append(f"D18S_KAUPUNKI = ${d018(sum(1 for f in FLIPS if f < SCR0 + 127) & 1, 'T'):02x}")
    for n, b in bands.items():
        inc.append(f"W_{n} = {b['cols']}")
        inc.append(f"V_{n} = {round(SPEED[n] * 256)}")
        inc.append(f"P0_{n} = {ph[n]}")
    for n in ("teksti", "lahi", "kauka"):
        inc.append(f"V_{n} = {round(SPEED[n] * 256)}")
    for n in ("piennar", "tie", "kaupunki", "teksti"):
        for k in ("d022", "d023"):
            inc.append(f"{n.upper()}_{k.upper()} = {BAND_COLS[n][k]}")
    inc.append(f"KAUPUNKI_BG = {meta['kaupunki']['tausta']}")
    inc.append(f"TIE_BG = {meta['tie']['tausta']}")
    for n, (c, k) in (("TIE_V1_D022", (meta["tie"]["d022"], 1)), ("TIE_V1_D023", (meta["tie"]["d023"], 1)),
                      ("TIE_V2_D022", (meta["tie"]["d022"], 2)), ("TIE_V2_D023", (meta["tie"]["d023"], 2)),
                      ("TIE_V2_BG", (meta["tie"]["tausta"], 1))):
        inc.append(f"{n} = {kehys.luma_down(c, k)}")             # alareunan vinjetti (irq_v1, irq_v2)
    inc.append(f"ROW0_D025 = {sprite_rows[0]['d025']}")
    inc.append(f"ROW0_D026 = {sprite_rows[0]['d026']}")
    inc.append(f"SH_COL = {meta['tie']['tausta']}")
    inc.append(f"D01D_TOP = ${0 if UNEXP else 0xff:02x}")
    # viimeinen nimi kokonaan ulos vasemmalta: sarakkeen oikea reuna (c + 1) * 8 hires px <= TXT_V * kehys
    # (initin frame_step on tekstin ensimmäinen askel, fade_run:n fd_t = askel - 1: yksi kehys varaa)
    last = max(c for c, col in enumerate(tcols) if any(col))
    fd_out = -(-(last + 1) * 8 // TXT_V)
    inc += [f"FD_N = {FD_N}", f"F_IN = {F_IN}", f"F_OUT = {F_OUT}", f"FD_OUT = {fd_out}"]
    for r, (n, _) in enumerate(ROAD_ROWS):
        inc.append(f"ROAD_N{r} = {n}")
        inc.append(f"ROAD_B{r} = {ROAD_BASE[r]}")
    (out / "greetsit.inc").write_text("\n".join(inc) + "\n")

    # data: osoitteelliset taulut asm-tiedostoon
    dat = []
    dat += road_asm                                     # kerneli: indeksoidut luvut eivät ylitä sivua
    dat += asm_bytes("wave_tab", wv)
    rowcol, percell = [], {}                            # percell: ruudun rivi -> värikartta (kaista, rivi)
    for r in range(25):
        bn = band_of_line(r * 8)
        if bn == "teksti":
            rowcol.append(meta["teksti"]["vari"] | 8)
        elif bn == "tie":
            rowcol.append(meta["tie"]["rivivari"] | 8 if meta["tie"].get("rivivari") is not None else 8)
        else:
            k = r - BANDS[bn][0] // 8
            v = bands[bn]["row_cols"][k]
            rowcol.append(8 if v is None else v)
            if v is None:
                percell[r] = f"col_{bn}_{k}"
    # color_go: kodin kuvan päälle ei saa kirjoittaa initissä, joten greetsit_go kirjoittaa värimuistin rivit
    # 0-21 sarakkeittain (vakiot yhtenäisille riveille, solukohtaiset kartasta paikasta q = 0) ennen riviä 44.
    gor = range(0, 22)                                  # rivit 0-21 näkyvät kodin pidetyssä kuvassa
    # Ylimmät vakiorivit COLOR_UNROLL suorina kirjoituksina (sta abs 4 sykliä, color_u VIC-pankin 1 lopussa,
    # color_u.asm): pidon aikana greetsit_go:lla on rivistä 237 riviin 40 vain noin 7 000 sykliä.
    unr = [r for r in gor if r not in percell][:COLOR_UNROLL]
    cu = ["color_u"]
    csites = []                                         # häivytettävät värimuistin vakiot (fade_sites)
    for v in sorted({rowcol[r] for r in unr}):
        cu.append(f"        lda #{v}")
        if v & 7:
            cu.append(f"fcu_{v} = * - 1")
            csites.append((f"fcu_{v}", v))
        cu += [f"        sta ${0xd800 + 40 * r + c:04x}" for r in unr if rowcol[r] == v for c in range(40)]
    cu.append("        rts")
    cg = ["color_go", "        jsr color_u",
          "        ldx #0                  ; vasemmalta: jos kerneli (rivi 44) ehtii väliin, myöhästyvät oikeat sarakkeet"]
    first = True
    for v in sorted({rowcol[r] for r in gor if r not in percell and r not in unr}):
        cg.append(f"{'-' if first else ' '}       lda #{v}")
        first = False
        if v & 7:
            cg.append(f"fcg_{v} = * - 1")
            csites.append((f"fcg_{v}", v))
        cg += [f"        sta ${0xd800 + 40 * r:04x},x" for r in gor if r not in percell and r not in unr and rowcol[r] == v]
    msites = []                                         # solukohtaiset värit: and #maski (fade_sites)
    for r in gor:
        if r in percell:
            cg += [f"        lda {percell[r]},x", "        and #$0f", f"fmg_{percell[r]} = * - 1",
                   f"        sta ${0xd800 + 40 * r:04x},x"]
            msites += [f"fmg_{percell[r]}", f"fm_{percell[r]}"]
    if any(not n.startswith("col_kaupunki_") for n in percell.values()):
        raise SystemExit(f"häivytys: solukohtaisia värejä muualla kuin kaupungissa ({percell}), fj_city kopioi vain sen")
    fd_reg, fd_cram, fd_mask = fade_tables()
    check_mask({int(v) for v in np.unique(bands["kaupunki"]["color"])}, fd_cram, fd_mask)
    cram_rows = {r: rowcol[r] for r in gor if r not in percell and r not in unr and rowcol[r] & 7}   # color_u: ylimmät
    dat += asm_bytes("fade_tab", fd_reg, 16)
    dat += asm_bytes("fadec_tab", fd_cram, 16)
    dat += asm_bytes("fmask_tab", fd_mask)
    cg += ["        inx", "        cpx #40", "        bne -", "        rts"]
    # static_rows (init): tekstikaistan rivit (sarake c rivi k = 4c + k), tien rivit (ROAD_Bk + c mod 8, aina
    # ruudusta S0: varjospritejen osoittimet) ja tien värimuistin rivit 22-24 (eivät näy kodin pidetyssä kuvassa)
    assert TEXT_ROWS == 4 and ROAD_BASE == [0, 8, 16] and all(n == 8 for n, _ in ROAD_ROWS)
    t0 = BANDS["teksti"][0] // 8
    ts = [(S0 if screen_rows[t0 + k] == 0 else S1) + 40 * (t0 + k) for k in range(4)]
    sr = ["static_rows", "        ldx #0", "        lda #0", f"-       sta ${ts[0]:04x},x", "        ora #1",
          f"        sta ${ts[1]:04x},x", "        eor #3", f"        sta ${ts[2]:04x},x", "        ora #1",
          f"        sta ${ts[3]:04x},x", "        clc", "        adc #1", "        inx", "        cpx #40", "        bne -",
          "        ldx #39", "-       txa", "        and #7", f"        sta ${S0 + 40 * 22:04x},x", "        ora #8",
          f"        sta ${S0 + 40 * 23:04x},x", "        eor #24", f"        sta ${S0 + 40 * 24:04x},x"]
    for r in (22, 23, 24):
        sr += [f"        lda #{rowcol[r]}", f"        sta ${0xd800 + 40 * r:04x},x"]
    sr += ["        dex", "        bpl -"]
    if rowcol[24] & 7:
        raise SystemExit(f"tien rivin 24 värimuisti {rowcol[24]}: alakulmien %11 ei ole musta")
    for k, (c, _) in enumerate(corner_cells()):         # alakulmien merkit (kernel päivittää ne tien mukana)
        sr += [f"        lda #{CORNER_CH + k}", f"        sta ${S0 + 40 * 24 + c:04x}"]
    sr += ["        rts"]
    lo_extra = cg + sr
    # rungot: maailman järjestys
    for lay, key in (("near", "lahi"), ("far", "kauka")):
        lst = R[key]
        per = R.get(f"jakso_{key}") or (lst[-1][0] + 100)
        dat.append(f"N_{lay.upper()}_T = {len(lst)}")
        dat.append(f"P_{lay.upper()} = {per}")
        dat += asm_bytes(f"{lay}_xlo", [x & 0xff for x, _ in lst])
        dat += asm_bytes(f"{lay}_xhi", [x >> 8 for x, _ in lst])
        dat += asm_bytes(f"{lay}_var", [vnames.index(v) for _, v in lst])
        gaps = [(lst[(j + 1) % len(lst)][0] + (per if j + 1 == len(lst) else 0)) - lst[j][0] for j in range(len(lst))]
        dat += asm_bytes(f"{lay}_glo", [g & 0xff for g in gaps])
        dat += asm_bytes(f"{lay}_ghi", [g >> 8 for g in gaps])
    dat += asm_bytes("var_col", [own[v] for v in vnames])
    tx = []                                             # rungon tyven keskikohta hires spriten vasemmasta reunasta
    for v in vnames:
        img = R["variantit"][v]
        ys, xs = np.nonzero(img[-20:])
        tx.append(round((xs.mean() if len(xs) else 6) * 4 + 2))
    dat += asm_bytes("var_tx", tx)
    pt = []
    for v in vnames:
        pt += [blk_ptr[i] for i in ptrs_v[v]]
    dat += asm_bytes("var_ptr", pt)                       # 8 per variantti
    dat += asm_bytes("sh_ptr", blk_ptr[n_trunk_blocks:n_trunk_blocks + SH_K])
    dat.append(f"SH_EMPTY = {blk_ptr[i_empty]}")
    dat += shadow_tables(sh_tops)
    dat.append(f"CYC_N = {len(cyc_blocks)}")
    dat += asm_bytes("cyc_ptr", blk_ptr[i_empty + 1:i_empty + 1 + len(cyc_blocks)])
    dat.append(f"JOG_N = {len(jog_blocks)}")
    dat += asm_bytes("jog_ptr", blk_ptr[i_empty + 1 + len(cyc_blocks):])
    # taulut koodin perään (GREETSIT5), color_u VIC-pankin loppuun spritejen perään (GREETSIT7)
    (out / "tables.asm").write_text("\n".join(dat) + "\n")
    # Tasot, jotka mahtuvat VIC-pankin 1 loppuun color_u:n perään (GREETSIT7), sijoitetaan sinne, joten GREETSIT5
    # pienenee. color_u: lda # 2, sta abs 3, rts 1 tavua.
    spr_end = max(a for a, _ in blk_data) + 64
    cu_len = sum(2 if l.strip().startswith("lda #") else 3 if l.strip().startswith("sta ") else 0 if "=" in l else 1
                 for l in cu[1:])
    room = 0x8000 - spr_end - cu_len
    n_lo = min(GLYPH_H, max(0, room // max(1, len(planes[0]))))
    for j in range(n_lo):
        cu += asm_bytes(f"plane{j}", planes[j], 64)
    (out / "color_u.asm").write_text("\n".join(cu) + "\n")

    # kartat ja tasot omaan tiedostoon (isot)
    big = []
    for n, b in bands.items():
        for r in range(b["rows"]):
            row = [b["codes"][r, c % b["cols"]] for c in range(b["cols"] + COLS)]
            big += asm_bytes(f"map_{n}_{r}", row, 64)
            if b["row_cols"][r] is None:
                big += asm_bytes(f"col_{n}_{r}", [b["color"][r, c % b["cols"]] for c in range(b["cols"] + COLS)], 64)
    for j in range(n_lo, GLYPH_H):                      # tiiviisti (piirto on taustatyö: sivun ylitys vain sykli)
        big += asm_bytes(f"plane{j}", planes[j], 64)
    for y in range(24):                                 # kerneli: lda road_tab+j,y (y <= 63, j <= 7) ei saa ylittää sivua
        big.append("        .if (* & $ff) > 255 - 70")
        big.append("        .align 256")
        big.append("        .endif")
        big += asm_bytes(f"road_tab_{y}", road_tabs[y], 64)
    (out / "maps.asm").write_text("\n".join(big) + "\n")

    lo = bands_code(MAP_BANDS) + lo_extra                # koodialueelle
    hi = []                                              # karttojen perään ($8000-)
    for n in MAP_BANDS:
        lo += copy_code(n, bands[n], screen_rows)
    lo += fade_code(kinfo["fsites"], csites, msites, cram_rows)
    hi += dycp_code()
    (out / "gen_lo.asm").write_text("\n".join(lo) + "\n")
    (out / "gen_hi.asm").write_text("\n".join(hi) + "\n")
    (out / "wave.asm").write_text("\n".join(wave_code(wv) + text_rows_code(ts) + [f"G_BLANK = {uniq.index(bytes(GLYPH_H))}"]
                                            + asm_bytes("gidtab", gid, 64)) + "\n")   # gidtab GREETSIT3:een
    (out / "kernel.asm").write_text("\n".join(klines) + "\n")

    # VIC-pankin data binääreinä
    (out / "cs_a.bin").write_bytes(csA.blob())
    (out / "cs_t.bin").write_bytes(csT.blob())
                                                        # spr_end: tämän jälkeen pankin loppu color_u:lle ja tasoille
    sp = bytearray(spr_end - 0x5900)
    for a, b in blk_data:
        sp[a - 0x5900:a - 0x5900 + 64] = b
    (out / "sprites.bin").write_bytes(bytes(sp))
    (out / "layout.inc").write_text(f"SPR_END = ${spr_end:04x}\n")

    rep = [f"data: {d['lahde']}", f"merkistö A {len(csA.chars)}, T {len(csT.chars)}",
           f"spritelohkoja {len(blocks)}", f"tekstisarakkeita {ntc}", f"kerneli loppuu {kinfo['end']}",
           f"askelvaiheet {ph}", f"häivytys mustaan kehyksestä {fd_out} (viimeinen nimi ulos), musta noin "
           f"{fd_out + FD_N * F_OUT + 2}", f"rivien ruudut {screen_rows}", f"tasoja GREETSIT7:ssä {n_lo}/{GLYPH_H}"]
    if errs:
        rep.append(f"VIRHEET ({len(errs)}):")
        rep += ["  " + e for e in errs[:40]]
    (out / "report.txt").write_text("\n".join(rep) + "\n")
    if "--report" in sys.argv:
        print("\n".join(rep))
        for reg, line, cyc in kinfo["writes"]:
            print(f"  W {reg:10} {line}:{cyc}")
    if any(not e.startswith(("taivas solu", "maet solu", "kaupunki solu", "piennar solu")) for e in errs):
        print("\n".join(errs), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
