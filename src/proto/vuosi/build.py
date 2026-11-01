"""Vuosipartti (vuosi1989 / vuosi2026, sama koodi): data (tools/gfx/data/<aineisto>/<vuosi>/, aineisto vuosi =
piirretty) -> kaistojen merkistöt, numeroiden rivitaulut, liukutapahtumat, rivikerneli ja kehystaulut
(build/<aineisto>/<vuosi>/).

  uv run --project tools/concept python src/proto/vuosi/build.py OUT --vuosi 1989 [--aineisto vuosi]
      [--start 47:10] [--kaistat N (vähintään N merkistökaistaa, testi)] [--report]

Data: rooli.npy (200, 160) 0 tausta, 1 kromi ($D022 riveittäin), 2 ekstruusio ($D023 riveittäin), 3 reunavalo
(värimuisti); numero.npy (200, 160) 1-4 vasemmalta; rivivarit.json d021/d022/d023 riveittäin.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/lib"))
from raster import Charset, Gen, Sim, Vic, asm_bytes, mc_byte  # noqa: E402

SCR0 = 51                     # ruudun rivi 0 = rasteririvi 51 (YSCROLL 3)
SCREEN = 0x2400               # VIC-pankki 0: ruutu $2400, merkistöt $2800, $3000, $3800 (greetsit esiladataan
CHARSET = 0x2800              # vuosi2026:n aikana: $1a00-$22bf ja $4800-$bfff vapaina)
DATA_BASE = {("vuosi", 1989): 0x3000,   # taulut ja tapahtumataulu (enintään $cfff, $3000:ssa $3fff): vuosi1989 merkistön perässä,
             ("vuosi", 2026): 0x4000}   # jolloin $c000-$cfff on vapaa kaupungintalo-ikkunan KT0:lle (esiladataan vuoden aikana,
                              # latausvara taulu1 -> ikkuna); vuosi2026 $4000 (alle $5000), koska
                              # spritetin jälkeen ilotulitus pyörii $c400-$cabf:ssä vuoden latautuessa;
                              # muuten $c000
CODE_BASE = 0xE000            # IRQ, kerneli, vuosi_init ja kehyksen logiikka, enintään $faff (alun nimiruutu $fb00-)
STAGE = {2026: 0x6000}        # VUOSI1:n (merkistöt) latausosoite, jos ei paikallaan: vuosi2026
                              # esiladataan kuoppa-kylttien aikana sen vapaaseen $5f00-$7fff:ään, vuosi_init kopioi
ROWS, COLS = 25, 40
NDIG = 4
D016_BASE = 0x18 | 4          # MC, 40 saraketta, hienovieritys 4
FRAMES = 256                  # kehystaulut (kohtaus 240 kehystä, loput pitävät viimeisen tilan)
BEAT = 30                     # isku 30 kehystä (100,25 BPM)

# Kernelin kirjoitusikkunat (rivin L arvot): $D018 ennen näyttöä (rivin L-1 sykli 50 .. rivin L sykli 12),
# värit näkymättömissä sarakkeissa (numerot ovat sarakkeissa 2-36: rivin L-1 sykli 53 .. rivin L sykli 17)
WIN_D018 = ((-1, 50), (0, 12))
WIN_COL = ((-1, 53), (0, 17))
SLIDE_BUDGET = 4600           # liukujen arvioitu hinta kehyksessä (sykliä; kernelin jälkeen vapaana noin 5 500)


# ---------------------------------------------------------------- data
def load(aineisto: str, vuosi: str) -> dict:
    d = ROOT / "tools/gfx/data" / aineisto / vuosi
    if not d.exists():
        raise SystemExit(f"data puuttuu: {d.relative_to(ROOT)}")
    rv = json.loads((d / "rivivarit.json").read_text())
    return {"rooli": np.load(d / "rooli.npy"), "numero": np.load(d / "numero.npy"),
            "solun_vari": np.load(d / "solun_vari.npy"), "rv": rv, "lahde": str(d.relative_to(ROOT))}


def cell(img: np.ndarray, r: int, c: int) -> bytes:
    return bytes(mc_byte(img[r * 8 + y, c * 4:c * 4 + 4]) for y in range(8))


def digits(data: dict) -> list[dict]:
    """Numerot: sarakkeet (c0..c1), rivit (r0..r1), naapurit, joiden kanssa sarake on yhteinen."""
    num = data["numero"]
    out = []
    for k in range(1, NDIG + 1):
        ys, xs = np.nonzero(num == k)
        out.append({"k": k - 1, "c0": xs.min() // 4, "c1": xs.max() // 4, "r0": ys.min() // 8, "r1": ys.max() // 8})
        if out[-1]["c0"] < 2 or out[-1]["c1"] > 36:
            raise SystemExit(f"numero {k}: sarakkeet {out[-1]['c0']}-{out[-1]['c1']} (sallittu 2-36: kernelin "
                             f"värien kirjoitusikkuna osuu sarakkeisiin 0-1 ja 37-39)")
    for c in range(COLS):
        ks = sorted(set(np.unique(num[:, c * 4:c * 4 + 4])) - {0})
        if len(ks) > 2:
            raise SystemExit(f"sarakkeessa {c} kolme numeroa {ks} (moottori sallii kaksi)")
    return out


def overlap(dg: list[dict], k: int, j: int) -> list[int]:
    a, b = dg[k], dg[j]
    return [c for c in range(max(a["c0"], b["c0"]), min(a["c1"], b["c1"]) + 1)]


# ---------------------------------------------------------------- liike (kehystaulut)
STEPS = [3] * 16 + [2, 2, 1, 1]               # liukuaskeleet sarakkeina (24-8 px/kehys): tarkat 8 px:n monikerrat
LIGHTER = {6: 14, 9: 8, 2: 10, 11: 12, 4: 14, 8: 10, 12: 15}   # sama sävy kirkkaampana (etupinta ekstruusion edessä)
EXIT_STEPS = list(reversed(STEPS))            # poistumisaskeleet: tulon käänteisinä (lähtee hitaasti ja kiihtyy)
EXIT_BEAT = 4                                 # ensimmäinen poistuminen tällä iskulla (numerot tulevat iskuilla 0-3)


def timeline(vuosi: str, dg: list[dict]) -> dict:
    """Kehyksittäin: numeroiden vaakasiirto o (sarakkeina lopullisesta, None = ei ruudussa) ja kromin vaihe.
    Numero k liukuu iskulla (1989 oikealta numerot 1-4, 2026 vasemmalta numerot 4-1) ja pysähtyy paikalleen:
    rivit eivät muutu, joten jokainen näkyvä solu on oman kaistansa merkistössä (ei likimääräisiä merkkejä), ja
    askel on aina kokonainen merkki (8 px), joten reunat ovat terävät. Liike koko ajan: kromin heijastus."""
    from_right = vuosi != "2026"
    order = range(NDIG) if from_right else range(NDIG - 1, -1, -1)
    off = [[None] * FRAMES for _ in range(NDIG)]
    for i, k in enumerate(order):
        d = dg[k]
        dist = (COLS - d["c0"]) if from_right else (d["c1"] + 1)          # alku kokonaan ruudun ulkopuolella
        steps = list(STEPS)
        while sum(steps) > dist:                                          # lyhyt matka: hitaat loppuaskeleet säilyvät
            steps.pop(0)
        if sum(steps) < dist:
            steps = [dist - sum(steps)] + steps
        f0 = BEAT * i - 1 if i == 0 else BEAT * i - len(steps) + 4        # ensimmäinen näkyy kehyksessä 0
        o = dist
        for t, st in enumerate(steps):
            f = f0 + t
            o -= st
            if 0 <= f < FRAMES:
                off[k][f] = o if from_right else -o
        for f in range(max(0, f0 + len(steps)), FRAMES):
            off[k][f] = 0
    # poistuminen (kun numerot ovat ruudussa, ne poistuvat yksi kerrallaan ykkösestä alkaen):
    # samassa järjestyksessä samaan suuntaan kuin tulivat (1989 vasemmalle, 2026 oikealle) samalla liikkeellä
    # käänteisenä (EXIT_STEPS: kiihtyy); numero on kokonaan poissa iskuilla 5-8 (kehys iskun jälkeen), joten viimeinen lähtee
    # juuri ennen kohtauksen loppua eikä ruutu jää tyhjäksi
    exits = {}
    for i, k in enumerate(order):
        d = dg[k]
        dist = (d["c1"] + 1) if from_right else (COLS - d["c0"])
        steps = list(EXIT_STEPS)
        while sum(steps) < dist:
            steps.append(EXIT_STEPS[-1])
        n = next(t for t in range(len(steps)) if sum(steps[:t + 1]) >= dist) + 1
        f0 = BEAT * (EXIT_BEAT + 1 + i) + 1 - n + 1
        exits[k] = f0
        o = 0
        for t, st in enumerate(steps):
            o += st
            for f in range(f0 + t, FRAMES):
                off[k][f] = -o if from_right else o
            if o >= dist:
                break
    chrome = [round(22 * math.sin(2 * math.pi * f / (4 * BEAT))) * (1 if from_right else -1) for f in range(FRAMES)]
    return {"off": off, "chrome": chrome, "order": list(order), "exits": exits}


# ---------------------------------------------------------------- taulut
def chrome_table(lines: list[int], ext: int = 28) -> list[int]:
    """256 riviä (sivutasattu, Y-indeksi = ruudun rivi + kromin vaihe): rivit 0-199 datasta, sitten alareunan
    jatko ja loppuun yläreunan jatko (vaihe +-ext riviä näyttää horisontin siirtyvän)."""
    t = list(lines[:200])
    t += [lines[200 - ext + i] for i in range(ext)]                 # alaosan jatko (sama dither)
    t += [lines[i] for i in range(256 - len(t))]                     # yläosan jatko
    assert len(t) == 256
    return t


def shifted(t: list[int]) -> list[int]:
    """Taulu yhdellä rivillä eteenpäin: badlinen jälkeinen rivi lukee tätä kasvattamattomalla indeksillä."""
    return t[1:] + t[:1]


# ---------------------------------------------------------------- kerneli
def kernel(start: tuple[int, int], band_rows: list[int], l0: int, l1: int) -> tuple[list[str], dict]:
    """Rivit l0..l1-1 (numeroiden merkkirivit; muilla riveillä on vain tyhjiä soluja, koodi 0 joka kaistassa, joten
    rekisterien arvoilla ei ole väliä ja pääsäie saa niiden ajan latauksille): rivin L $D022 ja $D023 (kromista Y:llä) kirjoitetaan rivin L-1 oikean reunan ja rivin L
    vasemman reunan välissä. Taulut sivutasattuja, joten indeksoidut luvut eivät ylitä sivua: Y kasvaa riveittäin ja
    kiertää 256:ssa. Badlinen vapaa aika ei riitä kasvatukseen; badlinen jälkeinen rivi lukee yhdellä siirretyt taulut
    (*1) ja kasvattaa kahdesti. Merkistökaistan rajalla (band_rows[1:], merkkirivin ensimmäinen rivi) myös $D018."""
    vic = Vic(3)
    sim = Sim(vic, *start)
    g = Gen(sim)
    win_err = []
    g.pad_to(l0 - 1, 30)                            # viivesilmukat käyttävät Y:tä: indeksi vasta tämän jälkeen
    g.i("lda z_d016")
    g.i("sta $d016", "d016:0")
    if len(band_rows) > 1:
        g.i("lda #D18_B0")
        g.i("sta $d018", "d018:0")
    g.i("lda z_y0")                                 # rivi L lukee taulujen alkion z_y0 + L - SCR0
    g.i("clc")
    g.i(f"adc #{l0 - SCR0}")
    g.i("tay")
    seam = {SCR0 + 8 * r: b for b, r in enumerate(band_rows) if b}
    for L in range(l0, l1):
        s = L - SCR0
        g.lines.append(f"; ---- rivi {L} (ruutu {s})")
        tgt = (L - 1, 54 if L in seam else 56)       # ensimmäinen lataus, aikaisintaan nyt
        while vic.ba_low(*sim.pos()):
            sim.step()
        cur = sim.pos()
        gap = (tgt[0] - cur[0]) * 63 + tgt[1] - cur[1]
        if gap == 1:                                    # 1 syklin täytettä ei ole: sykli myöhemmin
            tgt, gap = (tgt[0], tgt[1] + 1), 2
        crosses = any(vic.ba_low(cur[0] + (cur[1] + i - 1) // 63, (cur[1] + i - 1) % 63 + 1) for i in range(max(0, gap)))
        if gap > 0 and not crosses:                     # badlinen pysähdys ajoittaa muuten seuraavan latauksen
            g.pad_to(*tgt)
        sfx = "1" if vic.badline(L - 1) else ""
        acts = [(f"lda #D18_B{seam[L]}", "d018", WIN_D018)] if L in seam else []
        acts += [(f"lda d22t{sfx},y", "d022", WIN_COL), (f"lda d23t{sfx},y", "d023", WIN_COL)]
        for ld, reg, win in acts:
            g.i(ld)
            g.i(f"sta ${reg}", f"{reg}:{L}")
            w = sim.writes[-1]
            lo = (L + win[0][0], win[0][1])
            hi = (L + win[1][0], win[1][1])
            if not (lo <= (w[1], w[2]) <= hi):
                win_err.append(f"{reg} rivi {L}: kirjoitus {w[1]}:{w[2]} ikkunan {lo}-{hi} ulkopuolella")
        if not vic.badline(L):
            for _ in range(2 if sfx else 1):
                g.i("iny")
    return g.lines, {"writes": sim.writes, "end": sim.pos(), "errors": win_err}


# ---------------------------------------------------------------- merkistöt
MAX_BANDS = 3


def band_of(band_rows: list[int], r: int) -> int:
    return sum(1 for b in band_rows[1:] if r >= b)


def own_cells(data: dict, dg: list[dict]) -> dict:
    """Numeron k omat solut {(r, c): tavut}: vain numeron k pikselit (myös naapurin kanssa jaetuissa sarakkeissa:
    liukuva numero näkyy tarkkana, ja naapuri ilman sitä)."""
    rooli, num = data["rooli"], data["numero"]
    own = {}
    for d in dg:
        k = d["k"]
        img = np.where(num == k + 1, rooli, 0)
        own[k] = {(r, c): b for r in range(ROWS) for c in range(d["c0"], d["c1"] + 1)
                  if (b := cell(img, r, c)) != bytes(8)}
    return own


def split_bands(data: dict, own: dict, min_bands: int = 1) -> list[int]:
    """Kaistojen ensimmäiset merkkirivit: vähiten kaistoja (enintään MAX_BANDS), joilla jokaisen kaistan solut
    (lopullinen kuva ja numeroiden omat solut, rivit eivät liu'u) mahtuvat 256 merkkiin; tasaisin jako."""
    import itertools
    rows = []
    for r in range(ROWS):
        st = {cell(data["rooli"], r, c) for c in range(COLS)} | {b for m in own.values() for (rr, _), b in m.items()
                                                               if rr == r}
        rows.append(st | {bytes(8)})
    best = None
    for nb in range(min_bands, MAX_BANDS + 1):
        best = None
        for cut in itertools.combinations(range(1, ROWS), nb - 1):
            bounds = [0, *cut, ROWS]
            size = max(len(set().union(*rows[a:b])) for a, b in zip(bounds, bounds[1:]))
            if best is None or size < best[0]:
                best = (size, [0, *cut])
        if best[0] <= 256:
            return best[1]
    raise SystemExit(f"merkistö: {MAX_BANDS} kaistaa ei riitä (suurin kaista {best[0]} solua > 256)")


def build_chars(data: dict, dg: list[dict], own: dict, band_rows: list[int]) -> dict:
    """Kaistojen merkistöt (kaikki solut tarkkoina): lopullinen kartta ja omat koodit {k: {(r, c): koodi}}."""
    css = [Charset(f"V{b}") for b in range(len(band_rows))]
    final = np.zeros((ROWS, COLS), np.int32)
    for r in range(ROWS):
        for c in range(COLS):
            final[r, c] = css[band_of(band_rows, r)].add(cell(data["rooli"], r, c))
    code = {d["k"]: {rc: css[band_of(band_rows, rc[0])].add(b) for rc, b in own[d["k"]].items()} for d in dg}
    for cs in css:
        if len(cs.chars) > 256:
            raise SystemExit(f"merkistö {cs.name}: {len(cs.chars)} merkkiä")
    return {"css": css, "final": final, "code": code}


# ---------------------------------------------------------------- liukutapahtumat
PAD = max(STEPS[0], 8)        # rivitaulun tyhjät reunat (edellinen asema tyhjennetään samalla kopiolla)


def row_tables(dg: list[dict], ch: dict) -> tuple[list[str], dict]:
    """Numeron k rivitaulu rows_k: rivit r0..r1 peräkkäin, rivi = PAD tyhjää, sarakkeet c0..c1, PAD tyhjää
    (askel S = leveys + 2 PAD). Kopion lähde sarakkeelle x asemassa o: rows_k + i * S + (x - o - c0 + PAD)."""
    out, geo = [], {}
    for d in dg:
        k = d["k"]
        S = d["c1"] - d["c0"] + 1 + 2 * PAD
        data = []
        for r in range(d["r0"], d["r1"] + 1):
            data += [0] * PAD + [ch["code"][k].get((r, c), 0) for c in range(d["c0"], d["c1"] + 1)] + [0] * PAD
        out += asm_bytes(f"rows_{k}", data, 64)
        geo[k] = S
    return out, geo


def fixup(dg: list[dict], ch: dict, k: int, landed: list[int]) -> list[str]:
    """fix_k_<naapurit>: yhteisissä sarakkeissa laskeutuneen naapurin solu sinne, missä liukuvan numeron solu on tyhjä."""
    out = [f"fix_{k}_{''.join(map(str, landed))}"]
    for j in landed:
        for c in overlap(dg, k, j):
            for r in range(ROWS):
                v = ch["code"][j].get((r, c))
                if v:
                    a = SCREEN + 40 * r + c
                    out += [f"        lda ${a:04x}", "        bne +", f"        lda #{v}", f"        sta ${a:04x}", "+"]
    return out + ["        rts"]


def settle(dg: list[dict], ch: dict, k: int, landed: list[int]) -> list[str]:
    """settle_k_<naapurit>: lopulliset yhdistelmäsolut yhteisiin sarakkeisiin (numero k paikallaan, naapurit
    laskeutuneet)."""
    out = [f"settle_{k}_{''.join(map(str, landed))}"]
    for j in landed:
        for c in overlap(dg, k, j):
            for r in range(ROWS):
                if (r, c) in ch["code"][k] and (r, c) in ch["code"][j]:
                    out += [f"        lda #{int(ch['final'][r, c])}", f"        sta ${SCREEN + 40 * r + c:04x}"]
    return out + ["        rts"]


def events(dg: list[dict], tl: dict, geo: dict) -> tuple[list[tuple], set]:
    """Kehyksittäiset kutsut: slide (lähde, kohde, leveys, rivit) numeron uudelle asemalle ja edellisen aseman
    tyhjennys samalla kopiolla, fix_k (yhteiset sarakkeet laskeutuneen naapurin kanssa) ja settle_k (lopullinen)."""
    ev, used = [], set()
    prev = [None] * NDIG
    landed_at = {k: next((f for f in range(FRAMES) if tl["off"][k][f] == 0), None) for k in range(NDIG)}
    for f in range(FRAMES):
        cost = 0
        for k in range(NDIG):
            o, po = tl["off"][k][f], prev[k]
            prev[k] = o
            if o == po or o is None:
                continue
            d = dg[k]
            lo = d["c0"] + (o if po is None else min(o, po))
            hi = d["c1"] + (o if po is None else max(o, po))
            a, b = max(0, lo), min(COLS - 1, hi)
            if a <= b:
                n, R = b - a + 1, d["r1"] - d["r0"] + 1
                src = f"rows_{k}+{a - o - d['c0'] + PAD}"
                assert 0 <= a - o - d["c0"] + PAD and b - o - d["c0"] + PAD < geo[k], (k, f, o, po)
                ev.append((f, "slide", (src, SCREEN + 40 * d["r0"] + a, n, R, geo[k])))
                cost += R * (n * 16 + 40)
            landed = [j for j in (k - 1, k + 1) if 0 <= j < NDIG and overlap(dg, k, j)
                      and landed_at[j] is not None and landed_at[j] < f and f < tl["exits"].get(j, FRAMES)]
            if landed and a <= max(c for j in landed for c in overlap(dg, k, j)) + 0 and b >= min(
                    c for j in landed for c in overlap(dg, k, j)):
                name = f"fix_{k}_{''.join(map(str, landed))}"
                ev.append((f, name, None))
                used.add(("fix", k, tuple(landed)))
            if o == 0 and po is not None and po != 0 and landed:
                ev.append((f, f"settle_{k}_{''.join(map(str, landed))}", None))
                used.add(("settle", k, tuple(landed)))
        if cost > SLIDE_BUDGET:
            raise SystemExit(f"kehys {f}: liukujen hinta noin {cost} sykliä > {SLIDE_BUDGET}")
    return ev, used


# ---------------------------------------------------------------- pää
def main():
    out = Path(sys.argv[1])
    vuosi = sys.argv[sys.argv.index("--vuosi") + 1] if "--vuosi" in sys.argv else "1989"
    aineisto = sys.argv[sys.argv.index("--aineisto") + 1] if "--aineisto" in sys.argv else "vuosi"
    st = sys.argv[sys.argv.index("--start") + 1] if "--start" in sys.argv else "47:10"
    out.mkdir(parents=True, exist_ok=True)
    data = load(aineisto, vuosi)
    rv = data["rv"]
    if len(set(rv["d021"])) != 1 or len(np.unique(data["solun_vari"])) != 1:
        raise SystemExit("moottori olettaa yhden taustavärin ($D021) ja yhden reunavalon värin")
    dg = digits(data)
    own = own_cells(data, dg)
    band_rows = split_bands(data, own, int(sys.argv[sys.argv.index("--kaistat") + 1]) if "--kaistat" in sys.argv else 1)
    ch = build_chars(data, dg, own, band_rows)
    tl = timeline(vuosi, dg)
    rows_asm, geo = row_tables(dg, ch)
    ev, used = events(dg, tl, geo)

    used_rows = [r for r in range(ROWS) if ch["final"][r].any() or any(rc[0] == r for m in own.values() for rc in m)]
    l0, l1 = SCR0 + 8 * min(used_rows), SCR0 + 8 * (max(used_rows) + 1)   # kernelin rivit (numeroiden merkkirivit)
    st0 = tuple(int(v) for v in st.split(":"))      # --start mitattu, kun kerneli alkaa riviltä SCR0 (IRQ rivillä 45):
    start = (st0[0] + l0 - SCR0, st0[1])            # IRQ LINE_TOP = l0 - 6 (sama rivi mod 8, ei badlinea)
    klines, kinfo = kernel(start, band_rows, l0, l1)
    if kinfo["errors"]:
        raise SystemExit("kerneli:\n" + "\n".join(kinfo["errors"][:20]))

    code = []
    for kind, k, landed in sorted(used):
        code += fixup(dg, ch, k, list(landed)) if kind == "fix" else settle(dg, ch, k, list(landed))
    # tapahtumataulu: kehys (16 b), rutiini - 1, 7 parametria (slide: lähde, kohde, leveys, rivit, rivitaulun askel)
    tab = ["ev_tab"]
    for f, name, par in ev:
        src, dst, n, R, S = par if par else ("0", 0, 0, 0, 0)
        tab.append(f"        .word {f}, {name} - 1, {src}, {dst}")
        tab.append(f"        .byte {n}, {R}, {S}")
    tab.append("        .word $ffff")
    data_asm = ["        .align 256"]
    d023 = list(rv["d023"])
    if aineisto == "vuosi":             # ekstruusio yläreunan yli (muuten taustalla siirtyvä sininen ekstruusio
        top = next(i for i, v in enumerate(d023) if v)   # loppuisi ylhäällä kesken): kromin vaihe
        d023[:top] = [d023[top]] * top  # siirtää taulua jopa 22 riviä, ja datan rivit 0-34 ovat mustia
    d22, d23 = chrome_table(rv["d022"]), chrome_table(d023)
    # 3D-vaikutelma säilyy heijastuksen heilahtaessa (muuten se rikkoutuisi taustan liikkuessa): riveillä, joilla kromi
    # ja ekstruusio ovat samaa väriä (1989: sininen 6/6 yläosassa, ruskea 9/9 horisontin alla), etupinta on kirkkaampi
    # sävy; heilahdus siirtää nämä rivit numeroiden pinnoille. 2026:ssa tällaisia rivejä ei ole (kuva ennallaan).
    # Vain piirretty aineisto (vuosi).
    if aineisto == "vuosi":
        d22 = [LIGHTER.get(a, a) if a == b else a for a, b in zip(d22, d23)]
        assert all(a != b for a, b in zip(d22, d23)), "kromi ja ekstruusio samaa väriä"
    for name, t in (("d22t", d22), ("d23t", d23)):
        data_asm += asm_bytes(name, t) + asm_bytes(name + "1", shifted(t))
    data_asm += asm_bytes("ch_ph", [v & 255 for v in tl["chrome"]])
    data_asm += rows_asm

    data_base = DATA_BASE.get((aineisto, int(vuosi)), 0xC000)
    inc = [f"; generoitu: src/proto/vuosi/build.py (data: {data['lahde']})", f"VUOSI = {vuosi}",
           f"SCREEN = ${SCREEN:04x}", f"CHARSET = ${CHARSET:04x}", f"KLINE = {start[0]}", f"KSTART = {start[1]}", f"LINE_TOP = {l0 - 6}", f"LINE_END = {kinfo['end'][0] + 1}", f"OFF_FRAME = {max(f for f, _, _ in ev) + 2}",
           f"D016_BASE = ${D016_BASE:02x}", f"D021_BG = {rv['d021'][0]}", f"CELL_COL = {int(data['solun_vari'][0, 0])}",
           f"NFRAMES = {FRAMES}", f"STAGE = ${STAGE.get(int(vuosi), CHARSET):04x}", f"CODE_BASE = ${CODE_BASE:04x}", f"DATA_BASE = ${data_base:04x}"]
    assert CHARSET + 0x800 * len(band_rows) <= 0x4000, "merkistöt yli VIC-pankin 0"
    assert CHARSET + 0x800 * len(band_rows) <= data_base or data_base >= 0x4000, \
        "merkistöt osuvat tauluihin (DATA_BASE)"
    inc += [f"D18_B{b} = ${(SCREEN & 0x3fff) >> 6 | (CHARSET + 0x800 * b & 0x3fff) >> 10:02x}"
            for b in range(len(band_rows))]
    (out / "vuosi.inc").write_text("\n".join(inc) + "\n")
    (out / "kernel.asm").write_text("\n".join(klines) + "\n")
    (out / "code.asm").write_text("\n".join(code) + "\n")
    (out / "evtab.asm").write_text("\n".join(tab) + "\n")
    (out / "data.asm").write_text("\n".join(data_asm) + "\n")
    css = ch["css"]                                     # kaistojen merkistöt peräkkäin 2 kt:n välein
    (out / "charset.bin").write_bytes(b"".join(cs.blob().ljust(0x800, b"\0") for cs in css[:-1]) + css[-1].blob())
    rep = [f"data {data['lahde']}", f"kaistat (ensimmäiset merkkirivit) {band_rows}",
           f"merkkejä {[len(cs.chars) for cs in css]}", f"kernelin rivit {l0}-{l1 - 1}, loppuu {kinfo['end']}",
           f"numerot {[(int(d['c0']), int(d['c1']), int(d['r0']), int(d['r1'])) for d in dg]}",
           f"tapahtumia {len(ev)}", f"rutiinit {sorted(used)}"]
    (out / "report.txt").write_text("\n".join(rep) + "\n")
    if "--report" in sys.argv:
        print("\n".join(rep))


if __name__ == "__main__":
    main()
