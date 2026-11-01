"""Latausväli spritet -> sokeripala.

Sprite-ennätyksen jälkeen, kun sokeripalan alku latautuu, viimeiset logot (CR!SP ja ADAPT) haihtuvat tähdiksi
(tools/gfx/data/ryhmalogot/tahtivali/<logo>_haihtuu_xy.npy, 5 vaihetta, X+Y-laajennetut MC-spritet), tähdet
liukuvat sokeripalan kehyksen 0 31 tähden paikoille, ja taivas tulee esiin Bayer-ditherinä sokeripalan alkukuvan
väreissä. Leikkaus sokeripalaan on saumaton: sama taivas bittikarttana (sama $d016: MC, 38 saraketta, hienovieritys
7) ja tähdet samoissa pikseleissä.

Kahdeksan spriteä riittää 31 tähdelle: X-laajennettu hires-sprite on 48 x 21 pikseliä, ja tähti on yksi sen pikseli
(2 x 1, kuten MC-pikseli bittikartassa). Tähdet jaetaan kahdeksaan laatikkoon (kuusi rinnakkain taivaan poikki,
kaksi alemmille), ja jokainen laatikko lähtee yhdestä logon spriten puolikkaasta (2 logoa x 2 spriteä x ylä/ala =
8 ikkunaa): laatikon ja sen tähtien paikat interpoloidaan alusta loppuun samalla käyrällä, joten tähdet pysyvät
laatikossa koko matkan (kupera yhdistelmä).

  uv run --project tools/concept python -I tools/disk/tahtivali.py OUTDIR     # tv.inc, tv_logo.bin, tv2.prg, esikatselu.png
  python3 -I tools/disk/tahtivali.py syms LABELS OUT                          # sisääntulot kohtaustaululle
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "tools/gfx/data/tahtivali"
LOGOT = ROOT / "tools/gfx/data/ryhmalogot/tahtivali"      # ryhmälogojen haihtumisvaiheet (C64-sprite-data)
ALKUKUVA = DATA / "sokeripala-alkukuva.png"                # sokeripalan kehys 0 (VICE-kaappaus), 320 x 200
VICE = ["000000", "ffffff", "af3c58", "7ef3d6", "aa40f5", "62d532", "2c3dec", "ffff46",
        "b7631e", "775300", "ee7b95", "626262", "949494", "b7ff86", "7385ff", "cdcdcd"]
PAL = {tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)): k for k, h in enumerate(VICE)}
LOGOS = ("adapt", "crsp")                # vasemmalta oikealle
LOGO_X = (64, 168)                      # logon vasen reuna (kuvan x, 96 px leveä)
LOGO_Y = 120                            # logon yläreuna alussa (kuvan y, 42 riviä)
RISE = 1                                # logot nousevat rivin näin monen kehyksen välein (joka kehys liikettä)
PHASE_T = (0, 12, 20, 28, 36)           # haihtumisvaiheen alku (välin kehys)
T_HAND = 44                             # logot -> tähtispritet
GLIDE = 120                             # liu'un kesto kehyksinä
SKY_ROWS = range(3, 10)                 # taivaan merkkirivit bittikartassa (y 24-79)
SKY_STEPS = 4                           # Bayer-paljastus: askeleita (4 x 4 -matriisin tasot neljän ryhmissä; IRQ kevyt latauksen ajan)
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
BOX_W, BOX_H = 48, 21                   # X-laajennettu hires-sprite kuvan pikseleinä
TOP_Y = 25                              # ylärivin laatikot (rivit 25-45)
TV2_AT = 0xA000 + 15 * 320              # TV2: bittikartan rivit 15-24 (mustat värit, ei näy)


def sky_and_stars() -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Alkukuvan värit C64-indekseinä (320 x 200) ilman tähtiä ja tähdet (x, y; 2 px leveä valkoinen)."""
    im = np.asarray(Image.open(ALKUKUVA).convert("RGB"))
    idx = np.zeros(im.shape[:2], np.uint8)
    for rgb, k in PAL.items():
        idx[(im == rgb).all(axis=2)] = k
    stars = []
    for y, x in zip(*np.nonzero(idx == 1)):
        if x % 2 == 1 and idx[y, x + 1] == 1:
            stars.append((int(x), int(y)))
    for x, y in stars:                   # tähden alle taivaan väri (vasen tai oikea naapuripari)
        for nx in (x - 2, x + 2, x - 4, x + 4):
            if 0 <= nx < 320 and idx[y, nx] != 1:
                idx[y, x:x + 2] = idx[y, nx]
                break
    idx[idx == 15] = 0                   # yksittäinen vaalea piste kuvan alareunassa (ei taivasta)
    return idx, sorted(stars, key=lambda s: (s[1], s[0]))


def bitmap(idx: np.ndarray) -> tuple[bytes, bytes, bytes]:
    """Taivaan rivit MC-bittikarttana ($d016 = $17: MC-pikseli j sarakkeessa c kuvan x:ssä 7 + 8c + 2j), ruudun
    tavut ja värimuisti riveille SKY_ROWS (sarake 39 on piilossa)."""
    bm, scr, col = bytearray(), bytearray(), bytearray()
    for r in SKY_ROWS:
        rows_b = bytearray(320)
        for c in range(40):
            cell = [[int(idx[r * 8 + y, 7 + 8 * c + 2 * j]) if 7 + 8 * c + 2 * j < 320 else 0 for j in range(4)]
                    for y in range(8)]
            cs = sorted({v for row in cell for v in row} - {0}, key=lambda v: -sum(row.count(v) for row in cell))
            if len(cs) > 3:
                raise SystemExit(f"tahtivali: solussa ({c}, {r}) yli 3 väriä {cs}")
            cs += [0] * (3 - len(cs))
            role = {0: 0, cs[0]: 1, cs[1]: 2, cs[2]: 3} if cs[0] else {0: 0}
            for y in range(8):
                b = 0
                for j in range(4):
                    b |= role.get(cell[y][j], 0) << (6 - 2 * j)
                rows_b[c * 8 + y] = b
            scr.append(cs[0] << 4 | cs[1])
            col.append(cs[2])
        bm += rows_b
    return bytes(bm), bytes(scr), bytes(col)


def sprite_mc(img: np.ndarray, colors: dict[int, int]) -> bytes:
    """21 x 12 MC-pikseliä -> 63 tavua (+ täyte)."""
    out = bytearray(64)
    for y in range(21):
        for x in range(12):
            v = int(img[y, x])
            if v:
                out[y * 3 + x // 4] |= colors[v] << (6 - 2 * (x % 4))
    return bytes(out)


def logo_y(t: int) -> int:
    return LOGO_Y - t // RISE


def windows() -> list[tuple[int, int, list[tuple[int, int]]]]:
    """8 ikkunaa (logo, puoli, ylä/ala): vasen yläkulma kuvan pikseleinä luovutuskehyksellä ja tähtien lähteet
    ikkunan sisällä (x, y suhteessa ikkunaan; vaiheen 4 pisteet, tyhjässä vaiheen 3)."""
    out = []
    ly = logo_y(T_HAND)
    for li, name in enumerate(LOGOS):
        ph = np.load(LOGOT / f"{name}_haihtuu_xy.npy")
        for side in (0, 1):
            for half in (0, 1):
                wx, wy = LOGO_X[li] + 48 * side, ly + 21 * half
                src = []
                for p in (4, 3, 2):
                    for r, cc in zip(*np.nonzero(ph[p])):
                        if cc // 12 != side or (r > 10) != bool(half):
                            continue
                        x = (int(cc) - 12 * side) * 4 + 1          # MC-pikselin (4 px) keskeltä, pariton
                        y = int(r) * 2 - 21 * half
                        src.append((x, min(y, 20)))
                    if src:
                        break
                out.append((wx, wy, src))
    return out


def boxes(stars: list[tuple[int, int]]) -> list[tuple[int, int, list[int]]]:
    """Tähdet 8 laatikkoon: kuusi rinnakkain riveille 25-45 (x 9 + 48k), loput (y >= 46) kahteen alempaan."""
    out = [(9 + 48 * k, TOP_Y, []) for k in range(6)]
    low = [i for i, (x, y) in enumerate(stars) if y >= TOP_Y + BOX_H]
    for i, (x, y) in enumerate(stars):
        if i not in low:
            out[(x - 9) // 48][2].append(i)
    low.sort(key=lambda i: stars[i][0])
    groups: list[list[int]] = [[]]
    for i in low:                       # alemmat vasemmalta: uusi laatikko, kun ei mahdu edelliseen
        if groups[-1] and stars[i][0] - stars[groups[-1][0]][0] >= BOX_W:
            groups.append([])
        groups[-1].append(i)
    if len(groups) > 2:
        raise SystemExit("tahtivali: alemmat tähdet eivät mahdu kahteen laatikkoon")
    for g in groups + [[]] * (2 - len(groups)):
        if g:
            x0 = stars[g[0]][0]
            y1 = max(stars[i][1] for i in g)
            out.append((x0, y1 - BOX_H + 1, g))
        else:
            out.append((9, TOP_Y, []))
    for bx, by, g in out:
        for i in g:
            x, y = stars[i]
            assert bx <= x < bx + BOX_W and (x - bx) % 2 == 0 and by <= y < by + BOX_H, (bx, by, stars[i])
    return out


def ease(n: int) -> list[int]:
    """Kehysten lisäykset (summa 256) smoothstep-käyrälle."""
    e = [round(256 * (3 * (f / n) ** 2 - 2 * (f / n) ** 3)) for f in range(n + 1)]
    return [e[f + 1] - e[f] for f in range(n)]


def plan() -> dict:
    idx, stars = sky_and_stars()
    if len(stars) != 31:
        raise SystemExit(f"tahtivali: alkukuvassa {len(stars)} tähteä (odotettu 31)")
    win, box = windows(), boxes(stars)
    # ikkunat laatikoihin: pienin neliöetäisyyksien summa (8! vaihtoehtoa)
    cost = lambda w, b: (w[0] - b[0]) ** 2 + (w[1] - b[1]) ** 2
    perm = min(itertools.permutations(range(8)), key=lambda p: sum(cost(win[p[k]], box[k]) for k in range(8)))
    st = []                             # tähti: laatikko, alku (sprite-px x, y), loppu
    for k in range(8):
        wx, wy, src = win[perm[k]]
        bx, by, g = box[k]
        if g and not src:
            raise SystemExit(f"tahtivali: ikkunassa {perm[k]} ei lähteitä laatikolle {k}")
        for n, i in enumerate(g):
            sx, sy = src[n % len(src)]
            x, y = stars[i]
            st.append((k, sx // 2, sy, (x - bx) // 2, y - by))
    return {"idx": idx, "stars": stars, "win": win, "box": box, "perm": perm, "st": st}


def write(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    p = plan()
    bm, scr, col = bitmap(p["idx"])
    colors = {1: 1, 3: 2, 15: 3}        # %01 = $d025 valkoinen, %10 = spriten väri 3, %11 = $d026 vaaleanharmaa
    logo = bytearray()
    for name in LOGOS:
        ph = np.load(LOGOT / f"{name}_haihtuu_xy.npy")
        if set(np.unique(ph)) - {0, 1, 3, 15}:
            raise SystemExit(f"tahtivali: {name}: värit {sorted(np.unique(ph))}, odotettu 1, 3, 15")
        for f in range(5):
            for side in (0, 1):
                logo += sprite_mc(ph[f][:, 12 * side:12 * side + 12], colors)
    (out / "tv_logo.bin").write_bytes(bytes(logo))
    (out / "tv2.prg").write_bytes(bytes([TV2_AT & 255, TV2_AT >> 8]) + bm + scr + col)   # tahtivali.asm SKY_SRC
    win, box, perm, st = p["win"], p["box"], p["perm"], p["st"]
    de = ease(GLIDE)
    L = ["; Generoitu: tools/disk/tahtivali.py (latausväli spritet -> sokeripala)",
         f"NSTAR   = {len(st)}", f"T_HAND  = {T_HAND}", f"GLIDE   = {GLIDE}", f"RISE    = {RISE}",
         f"SKY_R0  = {SKY_ROWS.start}", f"SKY_NR  = {len(SKY_ROWS)}", f"SKY_STEPS = {SKY_STEPS}",
         f"LOGO_Y0 = {LOGO_Y + 50}",
         f"logo_x  .byte {', '.join(str((LOGO_X[li] + 48 * s + 24) & 255) for li in range(2) for s in (0, 1))}",
         f"logo_xh .byte {sum(1 << (2 * li + s) for li in range(2) for s in (0, 1) if LOGO_X[li] + 48 * s + 24 > 255)}",
         f"phase_t .byte {', '.join(map(str, PHASE_T))}, 255",
         f"de_tab  .byte {', '.join(map(str, de))}"]
    # laatikot: alku ja muutos (VIC-koordinaatit; x 16 bittiä etumerkillä, y 8)
    bx0 = [win[perm[k]][0] + 24 for k in range(8)]
    by0 = [win[perm[k]][1] + 50 for k in range(8)]
    dx = [box[k][0] + 24 - bx0[k] for k in range(8)]
    dy = [box[k][1] + 50 - by0[k] for k in range(8)]
    L += [f"bx0_lo  .byte {', '.join(str(v & 255) for v in bx0)}",
          f"bx0_hi  .byte {', '.join(str(v >> 8) for v in bx0)}",
          f"by0     .byte {', '.join(map(str, by0))}",
          f"bdx_lo  .byte {', '.join(str(v & 255) for v in dx)}",
          f"bdx_hi  .byte {', '.join(str((v >> 8) & 255) for v in dx)}",
          f"bdy     .byte {', '.join(str(v & 255) for v in dy)}"]
    L += [f"s_box   .byte {', '.join(str(s[0]) for s in st)}",
          f"s_x0    .byte {', '.join(str(s[1]) for s in st)}",
          f"s_y0    .byte {', '.join(str(s[2]) for s in st)}",
          f"s_dx    .byte {', '.join(str((s[3] - s[1]) & 255) for s in st)}",
          f"s_dy    .byte {', '.join(str((s[4] - s[2]) & 255) for s in st)}"]
    masks = []
    for step in range(1, SKY_STEPS + 1):
        th = step * 16 // SKY_STEPS
        for yy in range(4):
            b = 0
            for j in range(4):
                if BAYER[yy][j] < th:
                    b |= 3 << (6 - 2 * j)
            masks.append(b)
    L.append(f"sky_mask .byte {', '.join(f'${m:02x}' for m in masks)}")
    (out / "tv.inc").write_text("\n".join(L) + "\n")
    preview(out / "esikatselu.png", p)
    print(f"tahtivali: {len(st)} tähteä, laatikot {[len(b[2]) for b in box]}, taivas {len(bm)} t")


def preview(path: Path, p: dict) -> None:
    """Viitemalli: kehykset T_HAND, puoliväli ja loppu (tähdet laatikoissaan), alla alkukuva."""
    win, box, perm, st = p["win"], p["box"], p["perm"], p["st"]
    de = ease(GLIDE)
    frames = []
    for f in (0, GLIDE // 3, 2 * GLIDE // 3, GLIDE):
        e = sum(de[:f])
        im = np.zeros((200, 320), np.uint8)
        for k, x0, y0, x1, y1 in st:
            bx = win[perm[k]][0] * 256 + (box[k][0] - win[perm[k]][0]) * e
            by = win[perm[k]][1] * 256 + (box[k][1] - win[perm[k]][1]) * e
            sx = (x0 * 256 + (x1 - x0) * e) >> 8
            sy = (y0 * 256 + (y1 - y0) * e) >> 8
            X, Y = (bx >> 8) + 2 * sx, (by >> 8) + sy
            if 0 <= Y < 200 and 0 <= X < 319:
                im[Y, X:X + 2] = 1
        frames.append(im)
    frames.append(p["idx"])
    rgb = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in VICE], np.uint8)
    sheet = np.concatenate([rgb[f] for f in frames], axis=0)
    Image.fromarray(sheet).resize((640, 400 * len(frames) // 2), Image.NEAREST).save(path)


def syms(labels: Path, out: Path) -> None:
    """Sisääntulot VICE-labelsista kohtaustaulun includeksi."""
    want = {"tv_go", "tv_sky", "tv_end"}
    lines = []
    for ln in labels.read_text().splitlines():
        a, name = ln.split()[1], ln.split()[2].lstrip(".")
        if name in want:
            lines.append(f"{name} = ${a}")
            want.discard(name)
    if want:
        raise SystemExit(f"tahtivali: {labels}: puuttuu {sorted(want)}")
    out.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "syms":
        syms(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        write(Path(sys.argv[1]))
