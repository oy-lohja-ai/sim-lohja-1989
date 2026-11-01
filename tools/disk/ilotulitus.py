"""Siirtymä kuoppa-kyltit -> spritet: ilotulitus alkaa (logojen lento jatkuu ilotulitukseen).
Kylttien logot ovat lentäneet taivaalle, ja mustalle yötaivaalle nousee raketteja, jotka
räjähtävät samoina kuvina, korkeuksilla ja väreillä kuin sprite-ennätyksen ilotulitus (src/proto/spritet/build.py
rocket_frames, rocket_table): laukaisuja tihenee, kunnes sprite-ennätys alkaa.

Staattista dataa: kuvat (tavallisina spritelohkoina, ennätyksen crunch-rivijärjestyksestä), kuvasarja raketin iän
mukaan kummallekin räjähdyskorkeudelle ja laukaisulista. 6510 (src/runko/ilotulitus.asm) liikuttaa spritejä
rungon IRQ:n R_TICKissä.

  python3 -I tools/disk/ilotulitus.py OUTDIR                 # it.inc
  python3 -I tools/disk/ilotulitus.py syms LABELS OUT        # sisääntulot kohtaustaululle
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/proto/spritet"))
import build as spritet  # noqa: E402

BURSTS = spritet.VARIANTS["lentavat"]["bursts"]       # räjähdyskorkeudet kuten ennätyksessä
ROCKET_X = [(24, 104), (96, 184), (176, 256), (248, 320)]   # rakettispritet 0-3 (4-7 laskuri), X spriteittäin
TEXT = ["SPRITEJÄ:", "{} KPL"]  # laskuri kuten ennätyksessä: sama kirjasin ja paikka (spritet.FONT 3 x 6 MC px,
TEXT_SPR0 = 4                   # %11 = $d026 valkoinen; spritet 4-7 X 248-320 (oikea reuna), FONT_ISO 4 x 9 MC px,
TEXT_X0, TEXT_Y = 248, 231      # rasteririvit 232-240 ja 242-250: Y-rekisteri 231, sprite näkyy rekisteriä
                                # seuraavalta riviltä)
Y0 = 252                        # laukaisu ruudun alareunan alta; nousu 6 riviä kehyksessä kuten ennätyksessä
Y_END = 30                      # yläreunan takana: sprite vapaa
STEP = 6
LIFE = (Y0 - Y_END) // STEP + 1
FRAMES = 254                    # lista 1: laukaisuja tähän asti (t ei kierrä; spritetin I_START lopettaa)
STAGE0, STAGE = 10, 30          # lista 1: raketti k aloittaa kehyksellä STAGE0 + k STAGE ja laukeaa uudelleen samassa
                                # kehyksessä, jossa edellinen poistuu: laskuri kasvaa yksi kerrallaan 4 -> 8 eikä
                                # pienene, ja ennätys jatkaa ylöspäin
FRAMES2 = 76                    # lista 2 (spritet -> vuosi2026, it_jatko): laukaisut loppuvat, viimeinen raketti
GAP20, GAP21 = 3, 12            # räjähtää ennen vuoden alkua (väli 120 kehystä, iskuvara_pakota), välit harvenevat


def images() -> tuple[list[str], list[bytes]]:
    """Ennätyksen raketin kuvat tavallisina 64 t:n spritelohkoina (rivi y tavuissa 3y..3y+2)."""
    fr = spritet.rocket_frames()
    offs = spritet.row_offsets()
    names = sorted(fr)
    out = []
    for n in names:
        blk = bytearray(64)
        for y, o in enumerate(offs):
            blk[3 * y:3 * y + 3] = fr[n][o:o + 3]
        out.append(bytes(blk))
    return names, out


def sequences(names: list[str]) -> list[list[int]]:
    """Kuva raketin iän mukaan kummallekin räjähdyskorkeudelle: ennätyksen taulu riviltä Y0 - 6 x ikä, loppu $ff."""
    out = []
    for b in BURSTS:
        tab = spritet.rocket_table(b, names)
        out.append([tab[Y0 - STEP * a] for a in range(LIFE)] + [0xFF])
    return out


def staged() -> list[tuple[int, int, int, int, int]]:
    """Lista 1: rakettispritet aloittavat yksi kerrallaan ja laukeavat heti uudelleen (aina LIFE kehyksen välein)."""
    rnd = random.Random(2026)
    out = []
    for s in range(len(ROCKET_X)):
        out += [(t, s) for t in range(STAGE0 + STAGE * s, FRAMES, LIFE)]
    out.sort()
    return [(t, s, rnd.randrange(*ROCKET_X[s]), rnd.randrange(len(BURSTS)), rnd.choice(spritet.ROCKET_COL))
            for t, s in out]


def launches(frames: int, gap0: int, gap1: int, seed: int = 2026, t: int = 2,
             ramp: int = 120) -> list[tuple[int, int, int, int, int]]:
    """(kehys, sprite, x, räjähdyskorkeus, väri): välit muuttuvat gap0 -> gap1 ramp kehyksessä, vapaa sprite
    (edellinen poistunut)."""
    rnd = random.Random(seed)
    free_at = [0] * len(ROCKET_X)
    out = []
    while t < frames:
        spr = min(range(len(ROCKET_X)), key=lambda s: (free_at[s], rnd.random()))
        t = max(t, free_at[spr])
        if t >= frames:
            break
        x = rnd.randrange(*ROCKET_X[spr])
        out.append((t, spr, x, rnd.randrange(len(BURSTS)), rnd.choice(spritet.ROCKET_COL)))
        free_at[spr] = t + LIFE + 1
        t += round(gap0 + (gap1 - gap0) * min(1.0, t / ramp))
    return out


def counter() -> tuple[list[bytes], list[int], int, list[int]]:
    """Laskurin «SPRITEJÄ: / N KPL» spritelohkot, kun N = tekstispritet + näkyvät raketit (0-4): lohkot (kiinteät ensin,
    sitten numeron sarakkeen versiot), kiinteiden sarakkeiden lohkot, numeron sarake ja sen lohkot N:n mukaan."""
    nr = len(ROCKET_X)
    cols = {}
    for k in range(nr + 1):
        n = 8 - nr + k
        w = 12 * (8 - nr)                       # tekstispritet TEXT_SPR0-7, rivit tasattu oikeaan reunaan kuten ennätyksessä
        rows = spritet.text_rows([t.format(n) for t in TEXT], oikea=w, font=spritet.FONT_ISO)   # (vain luku muuttuu)
        assert max(len(r) for r in rows) <= w, (rows, nr)
        for c in range(w // 12):
            blk = bytearray(64)
            for r in range(len(rows)):
                px = (rows[r] + [0] * w)[12 * c:12 * c + 12]
                for b in range(3):
                    blk[3 * r + b] = sum(v << (6 - 2 * i) for i, v in enumerate(px[4 * b:4 * b + 4]))
            cols.setdefault(c, []).append(bytes(blk))
    vary = [c for c, v in cols.items() if len(set(v)) > 1]
    assert len(vary) == 1, vary
    dc = vary[0]
    blocks = [cols[c][0] for c in sorted(cols) if c != dc] + cols[dc]
    fixed = [i for i in range(len(cols) - 1)]
    return blocks, fixed, dc, list(range(len(cols) - 1, len(blocks)))


def write(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    names, imgs = images()
    tblocks, fixed, dc, dblk = counter()
    NIMG0 = len(imgs)           # laskurin lohkot rakettien kuvien perässä (lohko BLK0 + NIMG0 + i)
    seqs = sequences(names)
    l1 = staged()
    l2 = launches(FRAMES2, GAP20, GAP21, seed=2027, t=1, ramp=FRAMES2)
    for ls in (l1, l2):
        assert all(a < b for (a, *_), (b, *_) in zip(ls, ls[1:])), "laukaisut kehysjärjestyksessä, yksi kehyksessä"
    ls = l1 + [(0, 0, 0, 0, 0)] + l2            # listat peräkkäin, l_t:n 0 lopettaa (t on aina 1-255)
    assert len(ls) < 256
    byt = lambda v: ", ".join(f"${x:02x}" for x in v)   # noqa: E731
    rnd = random.Random(1989)
    seq_off = [sum(len(s) for s in seqs[:k]) for k in range(len(seqs))]
    (d / "it.inc").write_text(
        "; tools/disk/ilotulitus.py: raketin kuvasarjat, laukaisut ja kipinävärit\n"
        f"NIMG = {len(imgs)}\nY0 = {Y0}\nSTEP = {STEP}\nL2 = {len(l1) + 1}\nNR = {len(ROCKET_X)}\n"
        f"TSPR0 = {TEXT_SPR0}\nTY = {TEXT_Y}\nDSPR = {TEXT_SPR0 + dc}\n"
        f"t_xlo  .byte {byt([(TEXT_X0 + 24 * c) & 255 for c in range(8 - TEXT_SPR0)])}\n"
        f"TMSB = ${sum(1 << (TEXT_SPR0 + c) for c in range(8 - TEXT_SPR0) if TEXT_X0 + 24 * c > 255):02x}\n"
        f"TMASK = ${sum(1 << s for s in range(TEXT_SPR0, 8)):02x}\n"
        f"t_blk  .byte {byt([NIMG0 + fixed[c - (c > dc)] if c != dc else 0 for c in range(8 - TEXT_SPR0)])}\n"
        f"d_blk  .byte {byt([NIMG0 + b for b in dblk])}\n"
        f"seq    .byte {byt(sum(seqs, []))}\n"
        f"l_t    .byte {byt([t for t, *_ in ls] + [0])}\n"   # (lista 1:n loppumerkki 0 välissä)
        f"l_s    .byte {byt([s for _, s, *_ in ls])}\n"
        f"l_xlo  .byte {byt([x & 255 for _, _, x, *_ in ls])}\n"
        f"l_xhi  .byte {byt([x >> 8 for _, _, x, *_ in ls])}\n"
        f"l_seq  .byte {byt([seq_off[b] for *_, b, _ in ls])}\n"
        f"l_col  .byte {byt([c for *_, c in ls])}\n"
        f"spark  .byte {byt([rnd.choice(spritet.SPARK_A) for _ in range(16)])}\n")
    (d / "it_kuvat.inc").write_text("; tools/disk/ilotulitus.py: " + " ".join(names) + ", laskuri\n" + "\n".join(
        f"        .byte {byt(b)}" for b in imgs + tblocks) + "\n")
    print(f"ilotulitus: {len(imgs)} kuvaa, {len(l1)} + {len(l2)} laukaisua, elinaika {LIFE} kehystä")


if __name__ == "__main__":
    if sys.argv[1] == "syms":
        sys.path.insert(0, str(Path(__file__).parent))
        import crt
        crt.syms(Path(sys.argv[2]), Path(sys.argv[3]), {"it_go", "it_jatko", "it_end"})
    else:
        write(Path(sys.argv[1]))
