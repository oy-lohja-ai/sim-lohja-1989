"""Hillnerin purun (src/purku/purku.asm) staattinen data.

- taysvari.*: lähikuva (loppurajaus, `tools/gfx/data/hillner/lahi2`)
- purku.inc: pallon geometria (lähikuva ja laaja kuva), kappaleiden taulut, osoitteet
- pieces.bin ($9800): kappaleiden rivit, kasan solut siivittäin ja pallon rata (kulma ja nosturin x per kehys)
- tausta.bin ($c000): sisus kappaleiden takana (tausta_v2: huoneet, välipohjat, puurunko, aukoissa maisema); rom3.bin ($e000): laaja kuva (BG2), sen ruutu ja värit

Laaja purkukuva on `tools/gfx/data/hillner/purku2` (koko julkisivu, kolme iskua: vasen pääty,
oikea pääty, keskusta). Kehykset luetaan src/gen/timing.inc:stä.

  uv run --project tools/concept python tools/gfx/purku.py build/purku
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from c64fmt import Bitmap, _lab_dist, sprite_bytes  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).parent / "data/hillner/lahi2"       # lähikuva (fin) ja sen pallo
PDATA = Path(__file__).parent / "data/hillner/purku2"     # laaja purkukuva
TIMING = ROOT / "src/gen/timing.inc"
CROP_H = 144                             # loppurajauksen rivit (merkkirivit 3-20)
UNIT = 90.0 / 128                        # pallon kulmayksikkö: 128 = 90 astetta (taulu ball_sin 0..128)
CLOSE_N = 86                             # lähikuvan heilahdus ennen leikkausta: lepoon (alin kohta) neljännesjaksossa


def timing() -> dict[str, int]:
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"^(TIM_\w+) = (\d+)", TIMING.read_text(), re.M)}


def load(d: Path, name: str) -> np.ndarray:
    a = np.load(d / f"{name}.npy").astype(np.int16)
    if d == PDATA and name in WIRE_IMAGES:
        a = no_wires(a)
    elif d == PDATA and name == "kappaleet":
        no_wires(a[:1, :1])                         # maski valmiiksi
        a = np.where(_WIRES, 0, a)                  # vaijerinpätkät eivät kuulu kappaleisiin
    return a


WIRE_IMAGES = {"ilman_taloa", "kasa", "kasa3", "tausta", "tausta_v2", "taysvari", "taysvari_teksti", "romahdus"}


_WIRES = None


def no_wires(a: np.ndarray) -> np.ndarray:
    """Konseptikuvan taivaalle jääneet mustat vaijerinpätkät (ilman_taloa, rivit 0-16, x 60-100) pois kaikista
    laajan kuvan kerroksista: ne eivät liity palloon. Pikseli saa rivin lähimmän ei-mustan naapurin värin."""
    global _WIRES
    if _WIRES is None:
        t = np.load(PDATA / "ilman_taloa.npy")
        m = np.zeros(t.shape, bool)
        m[:17, 60:101] = t[:17, 60:101] == 0
        _WIRES = m
    a = a.copy()
    if a.shape != _WIRES.shape:
        return a
    for y, x in zip(*np.nonzero(_WIRES & (a == 0))):
        for d in range(1, 8):
            for xx in (x - d, x + d):
                if 0 <= xx < a.shape[1] and a[y, xx] != 0 and not _WIRES[y, xx]:
                    a[y, x] = a[y, xx]
                    break
            else:
                continue
            break
    return a


def arm(meta: dict, crop0: int) -> tuple[float, float, float, float]:
    """Heilurin tukipiste (x, rivi rajauksessa) ja varsi (vaaka MC-px, pysty rivejä): mittakaavat eroavat."""
    sx, sy = meta["pallo"]["kameran_mittakaava_px_per_m"]
    px, pyt = meta["pallo"]["ketjun_yla_ruutu"]
    _, ryt = meta["pallo"]["lepo_ruutu"]
    lm = ryt - pyt
    return px, pyt - crop0, lm / sy * sx, lm


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    tim = timing()
    meta = json.loads((DATA / "metadata.json").read_text())
    crop0 = meta["kuva"]["loppurajaus_rivit"][0]
    close = load(DATA, "taysvari")[crop0:crop0 + CROP_H]
    bm = Bitmap(close)
    assert bm.fixes == 0
    for ext, data in (("bmp", bm.bmp), ("scr", bm.scr), ("col", bm.col)):
        (out / f"taysvari.{ext}").write_bytes(bytes(data))
    cpx, cpy, clx, cly = arm(meta, crop0)
    wmeta = json.loads((PDATA / "metadata.json").read_text())
    wpx, wpy, wlx, wly = arm(wmeta, 0)
    rest = wpy + wly                     # pidempi heiluri: tukipiste ylemmäs, sama lepopaikka
    wpy, wlx, wly = rest - wly * ARM_W, wlx * ARM_W, wly * ARM_W
    # spritet: murska 6, pöly 6 + 6, pallo (pallo_x: lähikuvassa X- ja Y-laajennettuna hw 7, laajassa ilman)
    ballx = [sprite_bytes(np.load(PDATA / "pallo_x_roles.npy").astype(int))]
    murska = [sprite_bytes(s.astype(int)) for s in np.load(PDATA / "murska.npy")]
    poly = [sprite_bytes(s.astype(int)) for s in np.load(PDATA / "poly.npy")]
    polyx = [sprite_bytes(s.astype(int)) for s in np.load(PDATA / "poly_x.npy")]
    (out / "sprites.bin").write_bytes(b"".join(murska + poly + polyx + ballx))
    sintab = [min(255, round(255 * math.sin(math.radians(i * UNIT)))) for i in range(129)]
    t_go = tim["TIM_CUE_PURKU"] - CLOSE_N
    inc = ["; Generoitu: tools/gfx/purku.py. Älä muokkaa käsin.",
           f"T_GO = {t_go}                 ; purku_go: lähikuvan pallo lähtee (demon kehys)",
           f"BALL_SWING = {tim['TIM_CUE_OSUMA'] - t_go}       ; hil_glue: purku_go kehyksellä HIL_HIT - BALL_SWING - 2",
           f"CL_PX = {round(cpx)}", f"CL_PY = {round(cpy)}", f"CL_LX = {round(clx)}", f"CL_LY = {round(cly)}",
           f"W_PY = {round(wpy)}", f"W_LX = {round(wlx)}", f"W_LY = {round(wly)}",

           "SPR_MURSKA = 0", "SPR_POLY = 6", "SPR_POLYX = 12", "SPR_BALLX = 18", "SPR_N = 19"]
    pinc, blob = pieces3(out, tim)
    inc += pinc
    th, px, hits = ball_path(tim, (cpx, cpy, clx, cly), (wpx, wpy, wlx, wly))
    inc += [f"TAB_AT = ${PIECE_AT + len(blob):04x}", f"TAB_N = {len(th)}"]
    blob += bytes(v & 255 for v in th) + bytes(px[CLOSE_N:])       # nosturin x vain laajaan kuvaan
    inc.append(f"ball_sin = ${PIECE_AT + len(blob):04x}")       # sin 0..90 astetta (129 t)
    blob += bytes(sintab)
    inc += ["hit_x .byte " + ",".join(str(round(x)) for x, _ in hits),
            "hit_y .byte " + ",".join(str(round(y)) for _, y in hits)]
    assert PIECE_AT + len(blob) <= PIECE_END, hex(PIECE_AT + len(blob))
    (out / "pieces.bin").write_bytes(bytes(blob))
    (out / "purku.inc").write_text("\n".join(inc) + "\n")
    print(f"purku: data $9800-${PIECE_AT + len(blob):04x}, rata {len(th)} kehystä, lähikuvan varsi {clx:.0f} x "
          f"{cly:.0f}, laajan {wlx:.0f} x {wly:.0f}")


# ---------------------------------------------------------------- pallon rata
# Kulma (128 = 90 astetta, + = tukipisteen oikealla) ja nosturin x (MC-px) jokaiselle kehykselle T_GO..purun loppu.
# Lähikuva: pallo vapautetaan ylävasemmalta ja on leikkauksessa alimmassa kohdassa (heiluri, neljännesjakso).
# Laaja kuva: jokainen isku tulee omalta puoleltaan (vasen pääty vasemmalta, oikea oikealta, keskusta
# vasemmalta), pallo kimpoaa, heilahtaa taakse ja tulee seuraavaan iskuun; nosturi kääntyy iskujen välissä.
# Iskun kehyksellä pallon keskipiste on iskukohdassa. Viimeisen iskun jälkeen pallo kimpoaa ja nostetaan.
SIDE = (1, -1, 1)                        # mistä isku tulee: 1 = vasemmalta (kulma kasvaa), -1 = oikealta
BACK = 52.0                              # takaheilahdus (astetta tukipisteen toisella puolella)
ARM_W = 1.6                              # laajan kuvan heilurin pituus x metadatan varsi (moukarille pidemmät
                                         # liikkeet: pidempi heiluri, suurempi kaari, hitaat ääripäät)


def ball_path(tim: dict, close: tuple, wide: tuple) -> tuple[list[int], list[int], list[tuple[float, float]]]:
    cut, end = tim["TIM_CUE_PURKU"], tim["TIM_SCENE_HILLNER_PURKU_END"]
    hf = [tim["TIM_CUE_OSUMA"], tim["TIM_CUE_OSUMA2"], tim["TIM_CUE_OSUMA3"]]
    km = json.loads((PDATA / "kappaleet.json").read_text())
    hits = [tuple(km["iskukohdat"][str(k + 1)]) for k in range(3)]
    _, wpy, wlx, wly = wide
    ang, piv = [], []                    # kulma asteina ja x per iskun kohde
    for (hx, hy), d in zip(hits, SIDE):
        a = math.degrees(math.acos(max(-1.0, min(1.0, (hy - wpy) / wly))))
        ang.append(d * a)                # isku vasemmalta: pallo tukipisteen oikealla
        piv.append(hx - wlx * math.sin(math.radians(d * a)))
    t0 = cut - CLOSE_N
    th = [0.0] * (end - t0)
    px = [0.0] * (end - t0)

    def seg(a: int, b: int, f0: float, f1: float, ease) -> None:
        for t in range(a, b):
            u = (t - a) / (b - a)
            th[t - t0] = f0 + (f1 - f0) * ease(u)

    hit_in = lambda u: 1 - math.cos(math.pi / 2 * u)       # noqa: E731  levosta iskuun (kiihtyy)
    rebound = lambda u: math.sin(math.pi / 2 * u)          # noqa: E731  iskusta lepoon (hidastuu)
    swing = lambda u: (1 - math.cos(math.pi * u)) / 2      # noqa: E731  levosta lepoon
    seg(t0, cut, -34.0, 0.0, hit_in)                        # lähikuva
    for t in range(t0, cut):
        px[t - t0] = close[0]
    seg(cut, hf[0], -BACK * SIDE[0] * 0.8, ang[0], hit_in)
    for t in range(cut, hf[0]):
        px[t - t0] = piv[0]
    for k in range(2):
        a, b = hf[k], hf[k + 1]
        n = b - a
        apex = ang[k] - SIDE[k] * 18.0                      # kimpoaa iskun suunnasta poispäin
        back = -SIDE[k + 1] * BACK                          # seuraavan iskun takaheilahdus
        t1, t2 = a + n * 24 // 120, a + n * 66 // 120
        seg(a, t1, ang[k], apex, rebound)
        seg(t1, t2, apex, back, swing)
        seg(t2, b, back, ang[k + 1], hit_in)
        s0, s1 = a + n * 8 // 120, a + n * 70 // 120        # nosturi kääntyy
        for t in range(a, b):
            u = min(1.0, max(0.0, (t - s0) / (s1 - s0)))
            px[t - t0] = piv[k] + (piv[k + 1] - piv[k]) * (3 * u * u - 2 * u * u * u)
    a = hf[2]
    apex = ang[2] - SIDE[2] * 20.0
    seg(a, a + 20, ang[2], apex, rebound)
    seg(a + 20, end, apex, apex * -0.4, swing)
    for t in range(a, end):
        px[t - t0] = piv[2]
    qt = [max(-127, min(127, round(v / UNIT))) for v in th]
    qp = [max(0, min(255, round(v))) for v in px]
    for k in range(3):                                      # isku tarkasti iskukohdassa (pyöristetty taulu)
        t = hf[k] - t0
        x = qp[t] + wlx * math.sin(math.radians(qt[t] * UNIT))
        y = wpy + wly * math.cos(math.radians(qt[t] * UNIT))
        assert abs(x - hits[k][0]) < 2 and abs(y - hits[k][1]) < 2, (k, x, y, hits[k])
    return qt, qp, hits


# ---------------------------------------------------------------- kolmen iskun romahdus (kappaleet)
# Aineisto purku2: romahdusalue (alueen soluissa valoisuusluokat 0/2/9/15), kappaleet (6, kaksi
# iskua kohden: yläosa katon kanssa ja alaosa), tausta (sisus, puurunko ja keskitornin reunoilta riippuva pelti)
# ja kasa3 (lopputila: leveä kasa katuun asti ja takapiha). Kappaleiden pikselit ovat bittipareina, joten ne voi
# piirtää mihin tahansa alueen soluun. Rivit tallennetaan bbox-levyisinä tavuina 4 px:n rajaan kohdistettuina
# (kappale liikkuu vaakasuunnassa tavuittain) sekä rivin ensimmäinen ja viimeinen pikseli.
PAL3 = (0, 2, 9, 15)                     # %00 %01 %10 %11
PIECE_AT, TAUSTA_AT, ROM_AT = 0x9800, 0xC000, 0xE000
PIECE_END, TAUSTA_END = 0xBE40, 0xD000   # ROWA $be40- (purku.asm)
LAJI = {"kaatuu": 0, "putoaa": 2}       # alaosa kaatuu kadulle (purku.asm laji 0), yläosa painuu (laji 2); alaosa
                                         # ensin järjestyksessä (piirretään eteen)
SINK = (110, 118, 80)                     # kappaleet painuvat näin monessa kehyksessä iskuittain: tasainen
                                         # jäykkä liike koko iskujen välin; keskusta nopeammin, jotta kasa on
                                         # valmis ja purku_quiet palaa ennen seuraavan kohtauksen latauksia
V0_3 = 3                                 # isku 3: alkunopeus riviä per askel (torni murtuu iskussa ja hidastuu
                                         # pc_vm:ään), muut lähtevät levosta
DEL_LO3 = 10                             # isku 3: tornin yläosa rysähtää ensin rakennuksen sisään, alaosa perässä
DEL_UP = 6                               # siipi painuu kasaan: alaosa heti, yläosa 6 kehystä perässä (väliin aukeaa
                                         # sisus), molemmat jäykkinä pohjan rivin alle (purku.asm laji 2)
MASK_L, MASK_R = (0xFF, 0x3F, 0x0F, 0x03), (0xC0, 0xF0, 0xFC, 0xFF)
PILE_Y = 85                              # kasa3:n kasa alkaa tältä riviltä (yläpuolella pölypilvi)
RIGHT_X = 93                             # oikean päädyn kappaleet alkavat tästä (aineistossa 105)
WINGS = (18, 23)                         # kasan siivet solusarakkeittain: vasen < 18, keskusta 18-23, oikea > 23
WING_HIT = (1, 3, 2)                     # siiven isku (vasen, keskusta, oikea)
PYSTYYN = {"keski_ala_0"}                # jää pystyyn (viimeinen seinän pala jää seisomaan, historiallisesti tarkka):
                                         # keskustan alaosa oli viimeinen kaatuva pala; isku 3 painaa tornin yläosan
                                         # sen yläreunan alle, ja siivet liukenevat kasaksi sen ympärille


def cell_roles(orig: np.ndarray, rom: np.ndarray, reg: np.ndarray, house: np.ndarray) -> tuple[np.ndarray, dict]:
    """Romahdusalueen solujen bittiparit ja värit alkuperäisestä kuvasta (talo ei saa muuttua
    osumassa litteäksi pinkiksi). Talon soluissa (house: kappaleiden solut) paletti on {0, 2, 9, X}: %01 ja %10
    ovat kaikissa samat, joten putoava kappale pitää värinsä solusta toiseen (jäykkä liike), ja %11 = X on
    solun oma (vihreä katto, valkoiset ikkunat, oranssi kyltti); pikseli on lähin näistä neljästä. Muissa
    alueen soluissa bittipari on sama valoisuusluokka kuin aineiston romahdusalueessa (2 = %01 keski,
    9 = %10 tumma, 15 = %11 vaalea) ja solun värit alkuperäisen kuvan värit. Toinen samaan luokkaan osuva
    väri siirtyy vapaaseen bittipariin (lähin luokan väri), muuten lähimpään. Vapaa bittipari saa alueen
    yleisimmän värin siinä luokassa. Palauttaa bittiparikuvan (0-3) ja solujen värit {(cy, cx): [%01, %10, %11]}."""
    role = {c: i for i, c in enumerate(PAL3)}
    R = np.zeros(orig.shape, np.int16)
    pal, common = {}, [Counter() for _ in PAL3]
    dist = np.array([[_lab_dist(a, b) for b in range(16)] for a in range(16)])
    for cy, cx in zip(*np.nonzero(reg & house)):
        oc = orig[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
        P = min(([0, PAL3[1], PAL3[2], x] for x in range(16)), key=lambda P: dist[oc][..., P].min(-1).sum())
        R[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4] = dist[oc][..., P].argmin(-1)
        pal[(int(cy), int(cx))] = P
    for cy, cx in zip(*np.nonzero(reg & ~house)):
        oc = orig[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
        rc = rom[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
        vals, cnt = np.unique(oc[oc != 0], return_counts=True)
        cols: list[int | None] = [0, None, None, None]
        to = {0: 0}
        for c in [int(v) for v, _ in sorted(zip(vals, cnt), key=lambda t: -t[1])]:
            k = role[int(Counter(rc[oc == c].tolist()).most_common(1)[0][0])]
            if k == 0 or cols[k] is not None:
                free = [j for j in (1, 2, 3) if cols[j] is None]
                if not free:
                    to[c] = min((d for d in cols if d is not None), key=lambda d: _lab_dist(c, d))
                    continue
                k = min(free, key=lambda j: _lab_dist(c, PAL3[j]))
            cols[k] = to[c] = c
        rmap = {c: cols.index(to[c]) for c in to}
        R[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4] = np.vectorize(lambda v: rmap[int(v)])(oc)
        pal[(int(cy), int(cx))] = cols
        for j in (1, 2, 3):
            if cols[j] is not None:
                common[j][cols[j]] += 1
    for cols in pal.values():
        for j in (1, 2, 3):
            if cols[j] is None:
                cols[j] = common[j].most_common(1)[0][0]
    return R, {k: v[1:] for k, v in pal.items()}


def kasa_cells(orig: np.ndarray, touched: np.ndarray, pysyy: np.ndarray) -> tuple[list[str], bytes]:
    """Kasan solut siivittäin liukenemisjärjestyksessä: ylhäältä alas Bayer-kohinalla. Solut: kasa3 eroaa
    laajasta kuvasta, tai kappale tai kaatunut seinä voi koskea soluun (touched). Solu = ruudun siirtymä (2),
    bittikartta (8), ruutu, väri. Siipi liukenee, kun sen iskun kappaleet ovat maassa (purku.asm dissolve)."""
    # lopputila: talon takainen maisema (ilman_taloa), sen päällä kasa3:n kasa riviltä PILE_Y alas ja etuala
    # (pylväs, johdot). kasa3:n talon kohdalle maalattu pölypilvi ei lue maisemana, joten se jää pois;
    # pölyn tekevät spritet.
    tausta = load(PDATA, "ilman_taloa")
    k3 = load(PDATA, "kasa3")
    fg = load(PDATA, "etuala")
    rows = np.arange(k3.shape[0])[:, None] >= PILE_Y
    kasa = np.where(rows & (k3 != tausta), k3, tausta)
    kasa = np.where(fg != 255, fg, kasa)
    kbm = Bitmap(kasa, bg=0)
    diff = ((kasa != orig).reshape(18, 8, 40, 4).any(axis=(1, 3)) | touched) & ~pysyy   # pystyyn jäävä torni ennallaan
    bayer = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]
    wings: dict[int, list] = {1: [], 2: [], 3: []}
    for cy, cx in zip(*np.nonzero(diff)):
        w = 0 if cx < WINGS[0] else 2 if cx > WINGS[1] else 1
        wings[WING_HIT[w]].append((cy * 4 + bayer[(cy & 3) * 4 + (cx & 3)] // 2, int(cy), int(cx)))
    blob, starts = bytearray(), []
    for h in (1, 2, 3):
        starts.append(len(blob) // 12)
        for _, cy, cx in sorted(wings[h]):
            o = cy * 40 + cx
            blob += bytes((o & 255, o >> 8)) + bytes(kbm.bmp[cy * 320 + cx * 8:cy * 320 + cx * 8 + 8])
            blob += bytes((kbm.scr[o], kbm.col[o]))
    starts.append(len(blob) // 12)
    return ([f"KASA_N = {starts[-1]}", "kasa_w0 .word " + ",".join(map(str, starts[:3])),
             "kasa_w1 .word " + ",".join(map(str, starts[1:]))], bytes(blob))


PALKKI_VARIT = (8, 10)                  # laajan kuvan kylttipalkki: oranssi lauta ja sen poikki menevät vaaleat viivat


def musta_palkki(orig: np.ndarray) -> np.ndarray:
    """Laajan purkukuvan kylttipalkki mustaksi kuten ajo-kyltissä ja lähikuvassa: palkki on LOHJAN RAUTA -tekstin
    pikseleistä (taysvari_teksti != taysvari) 4-naapureittain leviävä yhtenäinen alue väreissä PALKKI_VARIT ja
    tekstin pikseleissä; alue mustaksi, tekstin valkoinen jää. Muu kuva pysyy pikselilleen (kappaleet ja romahdus
    käyttävät tätä kuvaa, joten palkki hajoaa julkisivun mukana)."""
    teksti = orig != load(PDATA, "taysvari")
    sallittu = np.isin(orig, PALKKI_VARIT) | teksti
    alue = teksti.copy()
    while True:
        k = alue.copy()
        k[1:] |= alue[:-1]
        k[:-1] |= alue[1:]
        k[:, 1:] |= alue[:, :-1]
        k[:, :-1] |= alue[:, 1:]
        k &= sallittu
        if (k == alue).all():
            break
        alue = k
    return np.where(alue & (orig != 1), 0, orig).astype(orig.dtype)  # vain valkoinen teksti jää


def pieces3(out: Path, tim: dict) -> tuple[list[str], bytearray]:
    """Kappaleiden data (pieces.bin $9800: kappaleet ja kasan solut), tausta.bin $c000, rom3.bin $e000
    (bittikartta, ruutu, värit) ja taulut purku.inc:iin. Alueen solujen värit ja bittiparit cell_roles."""
    meta = json.loads((PDATA / "kappaleet.json").read_text())
    assert tuple(meta["paletti"]) == PAL3
    orig = musta_palkki(load(PDATA, "taysvari_teksti"))
    rom = load(PDATA, "romahdusalue")
    lab = load(PDATA, "kappaleet")
    # isku 2 (oikea pääty) isommaksi, jotta se näkyy selvästi: keskustan kappaleiden pikselit x >= RIGHT_X oikean
    # päädyn kappaleille (yläosa / alaosa saman rajan kohdalta kuin aineiston jako), torni kapenee
    cols = np.arange(lab.shape[1])[None, :] >= RIGHT_X
    upper_c, lower_c = (next(q["kappale"] for q in meta["kappaleet"] if q["isku"] == 3 and q["laji"] == l)
                        for l in ("putoaa", "kaatuu"))
    upper_r, lower_r = (next(q["kappale"] for q in meta["kappaleet"] if q["isku"] == 2 and q["laji"] == l)
                        for l in ("putoaa", "kaatuu"))
    lab = np.where(cols & (lab == upper_c), upper_r, np.where(cols & (lab == lower_c), lower_r, lab))
    for q in meta["kappaleet"]:                    # bbox kappaleista
        ys, xs = np.nonzero(lab == q["kappale"])
        q["bbox"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    tau = load(PDATA, "tausta_v2")                  # sisus ja aukoissa talon takainen maisema
    vapaa = np.load(PDATA / "tausta_v2_vapaa.npy").astype(bool)
    reg = np.array(meta["alue_solut"], bool)
    role = {c: i for i, c in enumerate(PAL3)}
    house = (lab > 0).reshape(18, 8, 40, 4).any(axis=(1, 3))
    R, pal = cell_roles(orig, rom, reg, house)
    regpx = reg.repeat(8, 0).repeat(4, 1)

    def encode3(roles: np.ndarray) -> Bitmap:
        """Alueen ulkopuoli alkuperäisenä bittikarttana, alueen solut bittipareista roles ja soluväreistä pal."""
        n = roles.shape[0]
        bm = Bitmap(np.where(regpx[:n], 0, orig[:n]), bg=0)
        for (cy, cx), cols in pal.items():
            if cy * 8 >= n:
                continue
            bm.scr[cy * 40 + cx] = (cols[0] << 4) | cols[1]
            bm.col[cy * 40 + cx] = cols[2]
            for y in range(8):
                bm.bmp[cy * 320 + cx * 8 + y] = sum(int(roles[cy * 8 + y, cx * 4 + x]) << (6 - 2 * x) for x in range(4))
        return bm

    rbm = encode3(R)
    assert rbm.fixes == 0
    (out / "rom3.bin").write_bytes(bytes(rbm.bmp) + bytes(rbm.scr) + bytes(rbm.col))
    ylast = max(int(np.nonzero(lab)[0].max()), 0)
    trows = ylast // 8 + 1
    troles = np.where(lab > 0, np.vectorize(lambda v: role.get(int(v), 0))(tau), R)
    tbm = encode3(troles[:trows * 8])
    # vapaat solut (maisema täysvärinä): koko solu omalla paletillaan sisukseen; solun värit vaihtuvat, kun sen
    # päällä ollut kappale on painunut solun alle (purku.asm vfree)
    vcells = sorted({(int(y) // 8, int(x) // 4) for y, x in zip(*np.nonzero(vapaa)) if y < trows * 8})
    vrec = []
    for cy, cx in vcells:
        cb = Bitmap(tau[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4].copy(), bg=0)
        tbm.bmp[cy * 320 + cx * 8:cy * 320 + cx * 8 + 8] = cb.bmp
        vrec.append((cy, cx, cb.scr[0], cb.col[0]))
    assert len(tbm.bmp) == trows * 320
    (out / "tausta.bin").write_bytes(bytes(tbm.bmp))
    assert TAUSTA_AT + len(tbm.bmp) <= TAUSTA_END
    # järjestys: iskuittain, alaosa (kaatuu) ensin: pienempi indeksi piirretään viimeisenä eli eteen
    order = sorted((p for p in meta["kappaleet"] if p["nimi"] not in PYSTYYN), key=lambda p: (p["isku"], LAJI[p["laji"]]))
    pysyy = np.isin(lab, [p["kappale"] for p in meta["kappaleet"] if p["nimi"] in PYSTYYN])
    pysyy = pysyy.reshape(18, 8, 40, 4).any(axis=(1, 3))
    base = {h: max(p["bbox"][3] for p in order if p["isku"] == h) + 1 for h in {p["isku"] for p in order}}
    blob, tabs = bytearray(), {k: [] for k in ("kind", "hit", "del", "x0", "y0", "h", "wb", "d0", "sp",
                                                  "fl", "nx", "px", "lo", "vm", "v0")}
    for p in order:
        k = p["kappale"]
        ys, xs = np.nonzero(lab == k)
        x0, x1, y0, y1 = int(xs.min()) & ~3, int(xs.max()), int(ys.min()), int(ys.max())
        h = y1 - y0 + 1
        wb = (x1 - x0 + 1 + 3) // 4
        sp_at = PIECE_AT + len(blob)          # rivit: ensimmäinen tavu, (tavuja - 1) * 8, reunamaskit
        assert h < 64
        rows = []
        for y in range(h):
            xr = np.nonzero(lab[y0 + y, x0:x1 + 1] == k)[0]
            a, b = int(xr.min()), int(xr.max())
            row = bytearray(wb)
            for x in range(a, b + 1):                  # aukot rivin sisällä: lähin oma pikseli (kupera rivi)
                src = x if lab[y0 + y, x0 + x] == k else xr[np.argmin(abs(xr - x))]
                assert reg[(y0 + y) // 8, (x0 + x) // 4], (k, y, x)
                row[x >> 2] |= int(R[y0 + y, x0 + src]) << (6 - 2 * (x & 3))
            blob += bytes((a >> 2, ((b >> 2) - (a >> 2)) * 8, MASK_L[a & 3], MASK_R[b & 3]))
            rows.append(row)
        d0 = PIECE_AT + len(blob)
        for row in rows:
            blob += row
        # saman iskun alaosa (leikkaus sen yläreunaan, kun se on paikallaan); pystyyn jäävän alaosan yläosa itse,
        # jolloin leikkaus on pohja pc_fl = pystyyn jäävän yläreuna
        lo = next((i for i, q in enumerate(order) if q["isku"] == p["isku"] and LAJI[q["laji"]] == 0),
                  order.index(p))
        upper = LAJI[p["laji"]] == 2
        dist = base[p["isku"]] - y0                    # yläreuna pohjan alle
        vm = min(0x7FFF, round(dist / SINK[p["isku"] - 1] * 2 * 256))   # 8.8 riviä per askel (2 kehystä)
        v0 = 0 if p["isku"] == 1 else V0_3         # iskut 2 ja 3: yläosa rysähtää heti
        cx = (x0 + x1) / 2
        for key, v in (("kind", LAJI[p["laji"]]), ("nx", max(-127, min(127, round((cx - 88) / 80 * 24)))),
                       ("hit", p["isku"]), ("del", (DEL_UP if upper else 0) if p["isku"] < 3 else (0 if upper else DEL_LO3)), ("lo", lo), ("vm", vm), ("v0", v0),
                       ("x0", x0), ("y0", y0), ("h", h), ("wb", wb), ("d0", d0), ("sp", sp_at),
                       ("fl", base[p["isku"]]), ("px", round(p["painopiste"][0]))):
            tabs[key].append(v)
    touched = np.zeros((18, 40), bool)             # kappaleiden solut ja kaatuneen seinän alue kadulla
    for p in order:
        bx0, by0, bx1, by1 = p["bbox"]
        touched[by0 // 8:min(18, (by1 + 1 + (by1 + 1 - by0) * 2 // 5) // 8 + 1), bx0 // 4 - 1:bx1 // 4 + 2] = True
    kinc, kblob = kasa_cells(orig, touched & reg, pysyy)
    kasa_at = PIECE_AT + len(blob)
    blob += kblob
    # vapaat solut kappaleittain (myöhäisin isku, sitten yläosa) riveittäin ylhäältä alas
    owner = {}
    for cy, cx, sc, co in vrec:
        ks = [i for i, p in enumerate(order) if (lab[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4] == p["kappale"]).any()]
        if not ks:                                # kappale ei peitä solua: se ei paljastu koskaan
            continue
        owner.setdefault(max(ks, key=lambda i: (order[i]["isku"], LAJI[order[i]["laji"]])), []).append(
            (cy * 8 + 8, cy * 40 + cx, sc, co))
    # sisuksen solut kappaleittain merkkiriveittäin (16 bitin maski sarakkeista x0/4..): kun kappale on painunut
    # rivin alle, rivin solut sisukseksi romahdusalueen paletilla 0/2/9/15 (tausta_v2:n sisus). Jaettu solu kuuluu
    # myöhemmin lähtevälle kappaleelle; vapaat solut (maisema) omalla listallaan.
    vset = {(cy, cx) for cy, cx, _, _ in vrec}
    later = lambda ks: max(ks, key=lambda i: (order[i]["isku"], LAJI[order[i]["laji"]]))  # noqa: E731
    cellk = {}
    for i, p in enumerate(order):
        for cy, cx in zip(*np.nonzero((lab == p["kappale"]).reshape(18, 8, 40, 4).any(axis=(1, 3)))):
            cellk.setdefault((int(cy), int(cx)), []).append(i)
    mlo, mhi, m0, r0 = [], [], [], []
    for i, p in enumerate(order):
        c0, y0 = tabs["x0"][i] // 4, tabs["y0"][i]
        m0.append(len(mlo))
        r0.append(y0 // 8)
        for cy in range(y0 // 8, (y0 + tabs["h"][i] - 1) // 8 + 1):
            m = sum(1 << b for b in range(16) if (cy, c0 + b) in cellk and later(cellk[(cy, c0 + b)]) == i
                    and (cy, c0 + b) not in vset)
            mlo.append(m & 255)
            mhi.append(m >> 8)
    m0.append(len(mlo))
    sm_at = PIECE_AT + len(blob)
    blob += bytes(mlo) + bytes(mhi)
    kinc += [f"sm_lo = ${sm_at:04x}", f"sm_hi = ${sm_at + len(mlo):04x}",
             "pc_m0 .byte " + ",".join(map(str, m0)), "pc_r0 .byte " + ",".join(map(str, r0)),
             f"PAL3_SCR = ${(PAL3[1] << 4) | PAL3[2]:02x}", f"PAL3_COL = {PAL3[3]}"]
    vlist, vs, ve = [], [], []
    for i in range(len(order)):
        vs.append(len(vlist))
        vlist += sorted(owner.get(i, []))
        ve.append(len(vlist))
    assert len(vlist) < 256
    vf_at = PIECE_AT + len(blob)
    for k in range(4):
        blob += bytes((r[1] & 255, r[1] >> 8, r[2], r[3])[k] for r in vlist)
    blob += bytes(r[0] for r in vlist)
    kinc += [f"VF_AT = ${vf_at:04x}", f"VF_N = {len(vlist)}", "pc_vs .byte " + ",".join(map(str, vs)),
             "pc_ve .byte " + ",".join(map(str, ve))]
    inc = [f"NPIECE = {len(order)}", f"TAUSTA_ROWS = {trows}",
           f"PIECE_AT = ${PIECE_AT:04x}", f"KASA_AT = ${kasa_at:04x}", f"TAUSTA_AT = ${TAUSTA_AT:04x}",
           f"ROM_AT = ${ROM_AT:04x}"] + kinc
    for key in ("kind", "hit", "del", "x0", "y0", "h", "wb", "fl", "lo"):
        inc.append(f"pc_{key} .byte " + ",".join(str(v) for v in tabs[key]))
    # taulut datan perään (koodin tila on täynnä): 16-bittiset ala- ja ylätavuina, nx etumerkillisenä
    for key, vals in [(f"pc_{k}{h}", [(v & 255) if h == "lo" else (v >> 8) for v in tabs[k]])
                      for k in ("d0", "sp", "vm") for h in ("lo", "hi")] + \
            [("pc_nx", [v & 255 for v in tabs["nx"]]), ("pc_v0", tabs["v0"]), ("pc_px", tabs["px"])]:
        inc.append(f"{key} = ${PIECE_AT + len(blob):04x}")
        blob += bytes(vals)
    print(f"purku: {len(order)} kappaletta ({kasa_at - PIECE_AT} t), kasan soluja {len(kblob) // 12}, "
          f"tausta {trows} solua")
    return inc, blob


if __name__ == "__main__":
    main(Path(sys.argv[1]))
