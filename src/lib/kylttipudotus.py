"""Kylttien pudotus, buildin puoli (6510-moduuli src/lib/kylttipudotus.asm): ryhmälogot putoavat spriteinä
paikalleen MC-bittikarttaan, pomppaavat, siirtyvät bittikarttaan sammuneina ja syttyvät neonputken välkkeellä.

    sys.path.insert(0, str(ROOT / "src/lib")); import kylttipudotus
    asm, raportti = kylttipudotus.rakenna([{"ryhma": "CR!SP", "koko": "torni", "sarake": 12, "rivi": 4,
                                            "laskeutuu": 1290, "kuvat": {...}}, ...], tausta=0, loppu=1680)
    (out / "kp_data.asm").write_text(asm)

Kylttien tilat ovat pelkkiä värejä: logon bittikuvio on palavan kuvan solujako, ja sammunut (pois-kuva)
sekä himmeä ovat sen värien kuvauksia, joten bittikartta kirjoitetaan kerran laskeutuessa ja tilan vaihto kopioi
ruudun ja värimuistin (2 tavua solulta).
"""
from __future__ import annotations

import random

import numpy as np

from raster import asm_bytes, mc_byte


FALL_T = 24                       # pudotus kehyksinä (kiihtyvä)
LASKU_V = 1.2                     # pidemmän pudotuksen (putoaa) hidas laskeutuminen ennen sitä, px/kehys
BOUNCE = [-3, -5, -5, -3, -1, 0]  # pomppu laskeutumisen jälkeen (spriten Y, px)
NY = FALL_T + 1 + len(BOUNCE)     # Y-taulun pituus: pudotus, laskeutuminen, pomppu
Y_RIVI0 = 50                      # spriten Y, jolla sen ylin rivi on bittikartan rivillä 0 ($d011 = $3b)
X_SARAKE0 = 24                    # spriten X bittikartan sarakkeelle 0
# Neonputken syttyminen: askel kehys kerrallaan,
# 0 sammunut, 1 himmeä, 2 palava; neljä kuviota, kyltti k saa kuvion (7k + 3) & 3
START = [[2, 2, 0, 0, 0, 2, 0, 0, 0, 1, 1, 0, 0, 2, 2, 2],
         [0, 2, 0, 2, 2, 0, 0, 0, 0, 0, 2, 1, 0, 2, 2, 2],
         [1, 0, 0, 2, 0, 0, 2, 2, 2, 0, 0, 0, 1, 2, 2, 2],
         [2, 0, 0, 0, 0, 1, 0, 2, 0, 2, 2, 0, 2, 2, 2, 2]]
# himmeä: palavan värit tummemmiksi väreittäin (solun värimäärä ei kasva)
DIM = {1: 15, 7: 8, 8: 9, 15: 12, 13: 5, 3: 14, 10: 2, 14: 6, 12: 11, 5: 11, 4: 6, 2: 9, 9: 0, 6: 0, 11: 0, 0: 0}
LUMA = [0, 15, 5, 10, 6, 9, 3, 12, 6, 3, 9, 5, 8, 12, 8, 10]   # karkea valoisuus spritevärien lähimmälle
T_LAND, T_FALL = 1, 0             # tapahtumatyypit (kylttipudotus.asm kp_do); tila s = 2 + s
T_JULKI = 0x80                     # lähtö: kyltin paikalle julkisivu (kuvat["julkisivu"], oma bittikartta, värit tila 4)
# Lähtö (isännän "lahtee"): kyltti irtoaa palavana spriteinä ja lentää kiihtyen ylös kuvasta (perspektiivissä
# pienenee: LENTO_VAIHEET kokoina), ja sen paikka bittikartassa vaihtuu tilaan "tyhja" (isännän kuva).
LENTO_T = 29                      # lento kehyksinä: kyltin alareuna ohittaa kuvan yläreunan (rivi 75) tällä kehyksellä
LENTO_VAIHEET = ((0, 1), (14, 2)) # (alkukehys lennosta, pienennys): täysi koko pudotuksen spriteillä, sitten puolet
LENTO_V0 = 1.0                    # alkunopeus px/kehys (liike joka kehys), sitten kiihtyy
KUVA_Y0 = 75                      # kuvan ylin rivi (spriten Y): sen yläpuolella spritet ovat letterboxin takana
# ennen lähtöä neon hiipuu ja välkkyy kuin lama-ajan liike (liike ei menestynyt, kyltti lentää taivaalle):
# tila kehys kerrallaan, viimeinen sammunut; lähtiessä logo nousee sammuneena
SAMMUU = [2, 2, 1, 2, 2, 1, 1, 2, 1, 0, 2, 1, 0, 0, 1, 0, 0, 2, 0, 0, 0, 1, 0, 0]


def encode(states: list[np.ndarray], bg: int, name: str) -> tuple[bytes, list[bytes]]:
    """Kyltin bittikartta (rivit peräkkäin, w*8 tavua riviltä) ja tilojen värit (ruutu h*w, sitten värimuisti h*w).
    states = tilojen kuvat [sammunut, himmeä, palava, ...]; pikselin kynä on sen värit kaikissa tiloissa. Kynä, joka on
    kaikissa tiloissa taustaväri, on %00; muut saavat paikan yleisin ensin (tasapelissä palavan värin mukaan: %01
    ruudun ylänibbli, %10 alanibbli, %11 värimuisti), enintään 3 solua kohden."""
    h, w = states[0].shape[0] // 8, states[0].shape[1] // 4
    ns = len(states)
    pens = np.stack([s.astype(int) for s in states], -1)
    bmp = bytearray()
    scr = [bytearray() for _ in range(ns)]
    col = [bytearray() for _ in range(ns)]
    for r in range(h):
        for c in range(w):
            cell = pens[r * 8:r * 8 + 8, c * 4:c * 4 + 4]
            cnt: dict[tuple, int] = {}
            for p in map(tuple, cell.reshape(-1, ns).tolist()):
                cnt[p] = cnt.get(p, 0) + 1
            own = sorted((p for p in cnt if any(v != bg for v in p)), key=lambda p: (-cnt[p], p[min(2, ns - 1)], p))
            if len(own) > 3:
                raise SystemExit(f"kylttipudotus: {name} solu ({c}, {r}): {len(own)} väriä "
                                 f"{[p[min(2, ns - 1)] for p in own]}, enintään 3 + tausta {bg}")
            lut = {p: i + 1 for i, p in enumerate(own)}
            for y in range(8):
                bmp.append(mc_byte([lut.get(tuple(v), 0) for v in cell[y].tolist()]))
            for s in range(ns):
                cs = [p[s] for p in own] + [0] * (3 - len(own))
                scr[s].append(cs[0] << 4 | cs[1])
                col[s].append(cs[2])
    # rivijärjestys: bittikartta rivi kerrallaan (solut vasemmalta, 8 tavua kukin) = näytön järjestys
    return bytes(bmp), [bytes(scr[s] + col[s]) for s in range(ns)]


def sprite_layout(wpx: int, hpx: int, nspr: int) -> tuple[int, int, int, int]:
    """(laajennus x, laajennus y, sarakkeita, rivejä): tarkin, joka mahtuu nspr spriteen."""
    for ex, ey in ((0, 0), (1, 0), (1, 1)):
        cols = -(-wpx // (12 << ex))
        rows = -(-hpx // (21 << ey))
        if cols * rows <= nspr:
            return ex, ey, cols, rows
    raise SystemExit(f"kylttipudotus: kyltti {wpx} x {hpx} MC-px ei mahdu {nspr} spriteen")


def sprite_box(mask: np.ndarray) -> tuple[int, int, int, int]:
    """Maskin rajaus (dy, dx, korkeus, leveys) MC-pikseleinä kyltin vasemmasta yläkulmasta."""
    ys, xs = np.nonzero(mask)
    return int(ys.min()), int(xs.min()), int(ys.max() - ys.min() + 1), int(xs.max() - xs.min() + 1)


def sprite_blocks(off: np.ndarray, nspr: int, mask: np.ndarray | None = None) -> tuple[bytes, dict]:
    """Sammunut logo spriteinä: musta %01 ($d025 = 0), yleisin muu väri %10 (oma), toinen %11 ($d026), muut
    lähimpään valoisuudella, maskin ulkopuoli läpinäkyvä (spritet alkavat maskin rajauksesta: lay dx, dy). Laajennetussa
    spritessä pikseli on logon 2 x 1 tai 2 x 2 pikselin alueen yleisin väri (tasapelissä ei-musta)."""
    if mask is None:
        mask = np.ones(off.shape, bool)
    dy, dx, hpx, wpx = sprite_box(mask)
    off = off[dy:dy + hpx, dx:dx + wpx]
    mask = mask[dy:dy + hpx, dx:dx + wpx]
    ex, ey, cols, rows = sprite_layout(wpx, hpx, nspr)
    vals, cnt = np.unique(off[mask & (off != 0)], return_counts=True)
    order = [int(v) for v, _ in sorted(zip(vals, cnt), key=lambda x: -x[1])]
    own = order[0] if order else 12
    c26 = order[1] if len(order) > 1 else own
    pal = {0: 1, own: 2, c26: 3}

    def code(v: int) -> int:
        if v < 0:
            return 0
        if v in pal:
            return pal[v]
        return min(((1, 0), (2, own), (3, c26)), key=lambda kc: abs(LUMA[kc[1]] - LUMA[v]))[0]

    img = np.where(mask, off.astype(int), -1)
    sx, sy = 1 << ex, 1 << ey
    data = bytearray()
    for r in range(rows):
        for c in range(cols):
            for y in range(21):
                for b in range(3):
                    px = []
                    for k in range(4):
                        x0, y0 = (c * 12 + b * 4 + k) * sx, (r * 21 + y) * sy
                        if x0 >= wpx or y0 >= hpx:
                            px.append(0)
                            continue
                        v, n = np.unique(img[y0:y0 + sy, x0:x0 + sx], return_counts=True)
                        best = max(zip(n.tolist(), v.tolist()), key=lambda nv: (nv[0], nv[1] > 0))[1]
                        px.append(code(int(best)))
                    data.append(mc_byte(px))
            data.append(0)
    lay = {"ex": ex, "ey": ey, "cols": cols, "rows": rows, "own": own, "c26": c26, "n": cols * rows, "dx": dx,
           "dy": dy, "h": hpx, "w": wpx}
    return bytes(data), lay


def fall_y(y_end: int, y0: int, ft: int = FALL_T) -> list[int]:
    """Spritejen ylimmän rivin Y kehyksittäin: kiihtyvä pudotus y0 -> y_end (FALL_T kehystä), pomppu. Pidempi ft:
    ensin laskeutuu hitaasti ylhäältä (LASKU_V px/kehys, ft - FALL_T kehystä), sitten sama pudotus."""
    hidas = [round(y0 + LASKU_V * t) for t in range(ft - FALL_T)]
    y1 = y0 + LASKU_V * len(hidas)
    if y1 >= y_end:
        raise SystemExit(f"kylttipudotus: hidas laskeutuminen {ft} kehystä menee kohteen ({y_end}) ohi")
    ys = [round(y1 + (y_end - y1) * (t / FALL_T) ** 2) for t in range(FALL_T + 1)]
    return hidas + ys + [y_end + d for d in BOUNCE]


def neon(i: int, f0: int, loppu: int, rnd: random.Random, hurina: bool) -> list[tuple[int, int]]:
    """Tilamuutokset (kehys, tila) kyltin siirryttyä bittikarttaan kehyksellä f0 (sammuneena): syttyminen START-
    kuviolla, sitten palaa ja hurisee (lyhyt himmeä notkahdus 2-3 kehystä satunnaisin välein, joskus kaksoisvälke)."""
    seq = [(f0 + 1 + t, s) for t, s in enumerate(START[(i * 7 + 3) & 3])]
    f = f0 + 1 + len(START[0]) + rnd.randint(40, 120)
    while hurina and f < loppu - 6:
        d = rnd.choice([2, 2, 3])
        seq += [(f, 1), (f + d, 2)]
        if rnd.random() < 0.3:
            seq += [(f + d + 2, 1), (f + d + 3, 2)]
        f += rnd.randint(90, 220)
    out, state = [], 0
    for f, s in sorted(seq):
        if s != state and f < loppu:
            out.append((f, s))
            state = s
    return out


def pienenna(img: np.ndarray, mask: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Kuva ja maski k-kertaa pienempänä: k x k -lohkon yleisin maskin väri (lohko kuuluu maskiin, jos puolet)."""
    h, w = img.shape[0] // k * k, img.shape[1] // k * k
    blk = lambda a: a[:h, :w].reshape(h // k, k, w // k, k).transpose(0, 2, 1, 3).reshape(h // k, w // k, k * k)
    ib, mb = blk(img), blk(mask)
    out = np.zeros(ib.shape[:2], img.dtype)
    for y in range(out.shape[0]):
        for x in range(out.shape[1]):
            v = ib[y, x][mb[y, x]]
            if len(v):
                vals, cnt = np.unique(v, return_counts=True)
                out[y, x] = vals[np.argmax(cnt)]
    return out, mb.mean(-1) >= 0.5


def julki_sijoitus(julkit: list[tuple[int, bytes, bytes]], alueet: list[tuple[int, int]],
                   out: list[tuple[int, bytes]]) -> list[str]:
    """Julkisivut isännän alueille (out: (osoite, data)): erilliset 8 t solut kahteen yhtenäiseen joukkoon (ensimmäinen
    alue KP_JC_A:sta niin monta kuin mahtuu, loput KP_JC_B:stä), kylttien solukartat (kp_j<i>, solun numero
    riveittäin) ja värit (kp_s<i>_4) mihin tahansa alueelle. Palauttaa vakiot kp_data.asm:ään."""
    alueet = [list(a) for a in alueet]
    cells: dict[bytes, int] = {}
    maps = {}
    for i, jb, _ in julkit:
        m = []
        for c in range(0, len(jb), 8):
            m.append(cells.setdefault(jb[c:c + 8], len(cells)))
        maps[i] = bytes(m)
    uniq = sorted(cells, key=cells.get)
    if len(uniq) > 255:
        raise SystemExit(f"kylttipudotus: julkisivujen soluja {len(uniq)}, enintään 255")
    lo, hi = alueet[0]
    na = min(len(uniq), (hi - lo) // 8)
    lines = [f"KP_JC_N = {na}", f"KP_JC_A = ${lo:04x}"]
    out.append((lo, b"".join(uniq[:na])))
    alueet[0][0] += 8 * na

    def paikka(n: int) -> int:
        k = next((k for k, (a, b) in enumerate(alueet) if b - a >= n), None)
        if k is None:
            raise SystemExit(f"kylttipudotus: julkisivujen data ei mahdu alueisiin ({n} t)")
        a = alueet[k][0]
        alueet[k][0] += n
        return a
    rest = b"".join(uniq[na:])
    b_ = paikka(len(rest)) if rest else 0
    lines.append(f"KP_JC_B = ${b_:04x}")
    if rest:
        out.append((b_, rest))
    for i, _, jc in julkit:
        for lbl, blk in ((f"kp_j{i}", maps[i]), (f"kp_s{i}_4", jc)):
            a = paikka(len(blk))
            lines.append(f"{lbl} = ${a:04x}")
            out.append((a, bytes(blk)))
    return lines


def rakenna(kyltit: list[dict], tausta: int = 0, spriteja: int = 8, y0: int = 8, loppu: int | None = None,
            siemen: int = 26, hurina: bool = True, lento_t: int = LENTO_T,
            lento_vaiheet: tuple = LENTO_VAIHEET, julki_alueet: list[tuple[int, int]] | None = None,
            julki_out: list[tuple[int, bytes]] | None = None) -> tuple[str, list[str]]:
    """Moduulin data ja tapahtumataulu 64tass-lähteenä (kp_*-symbolit; isäntä määrittelee KP_SCREEN, KP_BITMAP,
    KP_SPRBUF, KP_SPR0 ja KP_ZP, ks. kylttipudotus.asm) sekä raportti.

    kyltit: [{"ryhma": "CR!SP", "koko": "torni" | "siipi", "sarake": 0-39, "rivi": 0-24, "laskeutuu": kehys,
    "kuvat": {"pois", "himmea", "palaa", ["tyhja",] "maski", ["julkisivu"]}}, ...]
    (sarake ja rivi = kyltin vasen yläsolu, laskeutuu = isännän kehys, jolla kyltti osuu paikalleen, kuvat = isännän
    tilakuvat MC-väri-indekseinä ja spritejen maski; valinnainen
    putoaa = pudotuksen kesto kehyksinä, oletus FALL_T: pidempi laskeutuu hitaasti ylhäältä).
    tausta = isännän $d021, spriteja = moduulin käyttämät spritet (KP_SPR0..), y0 = pudotuksen alun Y (8 = ylä-
    reunuksen takana), loppu = viimeinen kehys (hurinan tapahtumat sitä ennen)."""
    if not 1 <= spriteja <= 8:
        raise SystemExit("kylttipudotus: spriteja 1-8")
    rnd = random.Random(siemen)
    ks = sorted(kyltit, key=lambda k: k["laskeutuu"])
    tab = {k: [] for k in ("ny", "w", "h", "boff_lo", "boff_hi", "soff_lo", "soff_hi", "stb", "ns", "en", "xe", "ye", "d010",
                           "col", "c26", "ib", "slot", "sb", "mk", "mkn")}
    lennot = []                                                         # (kyltti, lähtökehys, palava, maski, keskikohta)
    sx_lo, yo, data, ev, rep = [], [], [], [], []
    st_lbl, bmp_lbl, spr_lbl, y_lbl, jb_lbl = [], [], [], [], []
    julkit: list[tuple[int, bytes, bytes]] = []                         # (kyltti, bittikartta, värit)
    vapaa = None
    for i, k in enumerate(ks):
        name = f"{k['ryhma']} {k.get('koko', '')}".strip()
        states = [k["kuvat"][t] for t in ("pois", "himmea", "palaa", "tyhja") if t in k["kuvat"]]   # isännän tilakuvat
        mask = k["kuvat"]["maski"]
        on, off = states[2], states[0]
        h, w = on.shape[0] // 8, on.shape[1] // 4
        c0, r0 = k["sarake"], k["rivi"]
        if c0 < 0 or r0 < 0 or c0 + w > 40 or r0 + h > 25:
            raise SystemExit(f"kylttipudotus: {name} ({w} x {h} solua) ei mahdu ruutuun kohtaan ({c0}, {r0})")
        if w * 8 > 128:
            raise SystemExit(f"kylttipudotus: {name} leveys {w} solua, enintään 16")
        bmp, states = encode(states, tausta, name)
        spr, lay = sprite_blocks(off, spriteja, mask)
        y_end = Y_RIVI0 + r0 * 8 + lay["dy"]
        ft = k.get("putoaa", FALL_T)
        ys = fall_y(y_end, y0, ft)
        ny = len(ys)                                                    # Y-taulun pituus (kp_ny): pudotus ja pomppu
        if ny > 255:
            raise SystemExit(f"kylttipudotus: {name}: pudotus {ft} kehystä, enintään {255 - 1 - len(BOUNCE)}")
        rowh = 21 << lay["ey"]
        if max(ys) + (lay["rows"] - 1) * rowh > 255:
            raise SystemExit(f"kylttipudotus: {name}: spritejen Y yli 255 (rivi {r0} liian alhaalla)")
        L = k["laskeutuu"]
        fs = L - ft
        if fs < 0:
            raise SystemExit(f"kylttipudotus: {name}: pudotus alkaisi ennen kehystä 0 (laskeutuu {L})")
        if vapaa is not None and fs < vapaa:
            raise SystemExit(f"kylttipudotus: {name}: putoaa ennen kuin edellinen on bittikartassa ({fs} < {vapaa})")
        vapaa = fs + ny
        boff, soff = r0 * 320 + c0 * 8, r0 * 40 + c0
        n = lay["n"]
        tab["ns"].append(str(n))
        en = (1 << n) - 1
        xs = [X_SARAKE0 + c0 * 8 + 2 * lay["dx"] + (j % lay["cols"]) * (24 << lay["ex"]) for j in range(n)]
        for kk, v in (("ny", ny), ("w", w), ("h", h), ("boff_lo", boff & 255), ("boff_hi", boff >> 8), ("soff_lo", soff & 255),
                      ("soff_hi", soff >> 8), ("stb", len(st_lbl)), ("col", lay["own"]), ("c26", lay["c26"]),
                      ("ib", i * spriteja), ("slot", 0), ("sb", 0)):
            tab[kk].append(str(v))
        tab["mk"].append(f"{(1 << spriteja) - 1} << KP_SPR0")            # pudotus: kaikki moduulin spritet
        tab["mkn"].append(f"$ff ^ ({(1 << spriteja) - 1} << KP_SPR0)")
        tab["en"].append(f"{en} << KP_SPR0")
        tab["xe"].append(f"{en if lay['ex'] else 0} << KP_SPR0")
        tab["ye"].append(f"{en if lay['ey'] else 0} << KP_SPR0")
        tab["d010"].append(f"{sum(1 << j for j, x in enumerate(xs) if x > 255)} << KP_SPR0")
        sx_lo += [x & 255 for x in xs] + [0] * (spriteja - n)
        yo += [(j // lay["cols"]) * rowh for j in range(n)] + [0] * (spriteja - n)
        bmp_lbl.append(f"kp_b{i}")
        spr_lbl.append(f"kp_p{i}")
        y_lbl.append(f"kp_y{i}")
        data += asm_bytes(f"kp_b{i}", bmp, 64) + asm_bytes(f"kp_p{i}", spr[:n * 64], 64)
        data += asm_bytes(f"kp_y{i}", ys, 64)
        for s, sd in enumerate(states):
            st_lbl.append(f"kp_s{i}_{s}")
            data += asm_bytes(f"kp_s{i}_{s}", sd, 64)
        julki = k.get("kuvat", {}).get("julkisivu")
        if julki is not None:                                           # lähteneen paikalle julkisivu: solukartta ja
            assert len(states) == 4, f"{name}: julkisivun värit ovat tila 4"   # värit (tila 4), sijoitus lopussa
            assert julki_alueet is not None, f"{name}: julkisivu tarvitsee julki_alueet"
            jb, (jc,) = encode([julki], tausta, f"{name} julkisivu")
            st_lbl.append(f"kp_s{i}_4")
            jb_lbl.append(f"kp_j{i}")
            julkit.append((i, jb, jc))
        else:
            jb_lbl.append(f"kp_b{i}")
        ev += [(fs, i, T_FALL), (fs + ny - 1, i, T_LAND)]
        ev += [(f, i, 2 + s) for f, s in neon(i, fs + ny - 1, k.get("lahtee", loppu if loppu is not None else 1 << 15),
                                               rnd, hurina)]
        if "lahtee" in k:
            if len(states) < 4:                                         # (koodatut tilat: tyhjä on neljäs)
                raise SystemExit(f"kylttipudotus: {name}: lähtö tarvitsee tilakuvan 'tyhja'")
            if k["lahtee"] < fs + ny + 16:
                raise SystemExit(f"kylttipudotus: {name}: lähtee {k['lahtee']} ennen kuin on syttynyt")
            seq, st_ = [], 2
            for t, sv in enumerate(SAMMUU):
                if sv != st_:
                    seq.append((k["lahtee"] - len(SAMMUU) + t, i, 2 + sv))
                    st_ = sv
            ev += seq + [(k["lahtee"], i, T_JULKI if julki is not None else 2 + 3)]
            lennot.append((i, k["lahtee"], on, mask if mask is not None else on != 0, (c0, r0), off))
        size = len(bmp) + sum(map(len, states)) + n * 64 + len(ys)
        rep.append(f"{name}: solut ({c0}, {r0}) {w} x {h}, laskeutuu {L} (putoaa {fs}-, bittikarttaan {fs + ny - 1}),"
                   f" spritet {lay['cols']} x {lay['rows']} laajennus x{lay['ex']} y{lay['ey']}, data {size} t")
    # lennot: virtuaaliset kyltit (indeksit kylttien perässä), joilla on vain spritet, värit ja Y-taulu
    nv = len(ks)
    lennot.sort(key=lambda x: x[1])
    # lennot kahdessa spritepaikassa vuorotellen (4 spriteä kumpikin, useampi lento samaan aikaan):
    # saman paikan lennot eivät saa mennä päällekkäin
    lsp = max(1, spriteja // 2)
    for k_, ((i, f0, pal, msk, (c0, r0), off), nxt) in enumerate(zip(lennot, [x[1] for x in lennot[2:]] + [1 << 16] * 2)):
        if nxt - f0 <= lento_t:
            raise SystemExit(f"kylttipudotus: saman paikan lennot menevät päällekkäin ({f0}, {nxt}): väli yli {lento_t}")
        slot = k_ % 2 if spriteja >= 2 * lsp else 0
        sb = slot * lsp
        ys_, xs_ = np.nonzero(msk)
        cy = Y_RIVI0 + r0 * 8 + (ys_.min() + ys_.max() + 1) / 2         # keskikohta (spriten Y, X pikseleinä)
        cx = X_SARAKE0 + c0 * 8 + (xs_.min() + xs_.max() + 1)           # MC-px -> 2 px
        h_last = (ys_.max() - ys_.min() + 1) / lento_vaiheet[-1][1]   # viimeisen vaiheen korkeus
        acc = (cy - (KUVA_Y0 - h_last / 2) - LENTO_V0 * lento_t) / lento_t ** 2
        for t0, kz in ((t * lento_t // LENTO_T, kz) for t, kz in lento_vaiheet):   # vaiheet lennon mittaan
            img, m2 = (off, msk) if kz == 1 else pienenna(off, msk, kz)
            spr, lay = sprite_blocks(img, lsp, m2)                     # paikan spritet (täysi koko laajennettuna)
            lbl = f"kp_p{nv}"
            data += asm_bytes(lbl, spr[:lay["n"] * 64], 64)
            col, c26 = lay["own"], lay["c26"]
            n = lay["n"]
            tab["ns"].append(str(n))
            en = (1 << n) - 1
            x0 = round(cx - lay["w"])                                   # kuvan keskikohta kyltin keskikohtaan
            xs = [x0 + (j % lay["cols"]) * (24 << lay["ex"]) for j in range(n)]
            yl = [max(0, min(255, round(cy - LENTO_V0 * t - acc * t * t - lay["h"] / 2))) for t in range(t0, t0 + NY)]
            for kk, v in (("ny", NY), ("col", col), ("c26", c26), ("ib", nv * spriteja), ("slot", slot), ("sb", sb)):
                tab[kk].append(str(v))
            sh = f"(KP_SPR0 + {sb})"
            tab["en"].append(f"{en} << {sh}")
            tab["xe"].append(f"{en if lay['ex'] else 0} << {sh}")
            tab["ye"].append(f"{en if lay['ey'] else 0} << {sh}")
            tab["d010"].append(f"{sum(1 << j for j, x in enumerate(xs) if x > 255)} << {sh}")
            tab["mk"].append(f"{(1 << lsp) - 1} << {sh}")
            tab["mkn"].append(f"$ff ^ ({(1 << lsp) - 1} << {sh})")
            sx_lo += [x & 255 for x in xs] + [0] * (spriteja - n)
            yo += [(j // lay["cols"]) * (21 << lay["ey"]) for j in range(n)] + [0] * (spriteja - n)
            spr_lbl.append(lbl)
            y_lbl.append(f"kp_y{nv}")
            data += asm_bytes(f"kp_y{nv}", yl, 64)
            ev.append((f0 + t0, nv, T_FALL))
            rep.append(f"{ks[i]['ryhma']}: lento {f0 + t0}- koko 1/{kz}, paikka {slot}, spritet {lay['cols']} x {lay['rows']}")
            nv += 1
    ev.sort()
    jl = julki_sijoitus(julkit, julki_alueet, julki_out) if julkit else ["KP_JC_N = 1", "KP_JC_A = 0", "KP_JC_B = 0"]
    lines = ["; generoitu: src/lib/kylttipudotus.py (moduuli src/lib/kylttipudotus.asm)", *jl,
             f"KP_NSIGN = {len(ks)}", f"KP_NSPR = {spriteja}", f"KP_NY = {NY}", f"KP_BG = {tausta}",
             "KP_MASK = ((1 << KP_NSPR) - 1) << KP_SPR0"]
    for kk, vals in tab.items():
        lines.append(f"kp_{kk} .byte " + ", ".join(vals))
    for nm, lbl in (("bmp", bmp_lbl), ("spr", spr_lbl), ("ytab", y_lbl), ("jb", jb_lbl)):
        lines += [f"kp_{nm}_lo .byte " + ", ".join(f"<{x}" for x in lbl),
                  f"kp_{nm}_hi .byte " + ", ".join(f">{x}" for x in lbl)]
    lines += ["kp_st_lo .byte " + ", ".join(f"<{x}" for x in st_lbl),
              "kp_st_hi .byte " + ", ".join(f">{x}" for x in st_lbl)]
    lines += asm_bytes("kp_sx", sx_lo) + asm_bytes("kp_yo", yo)
    lines += ["kp_ev"] + [f"        .word {f}\n        .byte {i}, {t}" for f, i, t in ev] + ["        .word $ffff"]
    lines += data
    rep.append(f"tapahtumia {len(ev)}, kylttejä {len(ks)}, spriteja {spriteja}")
    return "\n".join(lines) + "\n", rep
