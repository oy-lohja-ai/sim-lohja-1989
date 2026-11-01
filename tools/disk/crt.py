"""Siirtymä graafi -> kuoppa: kuvaputki sammuu (siirtymä kohtausvälin mustan tilalla). Graafi on tietokoneen ruutu
(SimCity-käyttöliittymä), joten se sammuu kuin vanha näyttö: kuva
painuu kahdessa kehyksessä vaakaviivaksi, viiva kutistuu keskelle pisteeksi ja piste hiipuu jälkihehkuna
(valkoinen -> vaaleanharmaa -> harmaa -> tummanharmaa), ja kuoppa alkaa iskulle.

Kehystaulu on staattista dataa (kaistan korkeus, viivan leveys, väri); 6510 (src/runko/crt.asm) asettaa joka
kehys rasterikeskeytykset ja spritet sen mukaan. Viiva on enintään 7 tasavälein limittäistä spriteä neljästä
yksirivisestä muodosta (X-laajennus tuplaa leveyden, `layout`), korkeus Y-laajennuksella.

  python3 -I tools/disk/crt.py OUTDIR                 # crt.inc, crt_ajo.inc, crt_muodot.inc
  python3 -I tools/disk/crt.py syms LABELS OUT        # sisääntulot kohtaustaululle
"""
from __future__ import annotations

import sys
from pathlib import Path

CY = 150                                # keskirivi (rasteri), kuvan keskellä
CX = 24 + 160                           # keskikohta spritekoordinaateissa
BAND = [60, 14]                         # kehykset 0-1: graafin kaistan puolikorkeus (kp_stage kirjoittaa graafin
                                        # ruudun päälle noin kehyksestä 2)
WHITE, LGREY, GREY, DGREY = 1, 15, 12, 11
# kehykset 2-: (leveys, korkeus, väri); jokainen tila enintään 2 kehystä (ei seisovaa kuvaa)
LINE = [(w, 2, WHITE) for w in (320, 300, 256, 200, 148, 104, 70, 46, 30, 24, 10)] + [
    (6, 2, WHITE), (4, 2, WHITE), (4, 2, LGREY), (4, 2, LGREY), (3, 2, LGREY), (3, 2, LGREY), (3, 2, GREY),
    (3, 2, GREY), (2, 2, GREY), (2, 2, GREY), (2, 1, GREY), (2, 1, GREY), (2, 1, DGREY), (2, 1, DGREY),
    (1, 1, DGREY), (1, 1, DGREY)]       # piste hiipuu kehykseen 28, kehys 29 musta, kuoppa iskulle (30)
SHAPES = [24, 5, 3, 1]                  # yksirivisiä muotoja (vasemmalle tasattu), X-laajennus tuplaa: 4 lohkoa


def layout(w: int) -> tuple[int, int, int, int]:
    """Leveys w spriteinä: (spritejä, X-laajennus, muoto, askel). Vähiten spritejä, jotka peittävät tasan w:n."""
    best = None
    for shape in SHAPES:
        for xexp in (1, 0):
            unit = shape << xexp
            if unit > w:
                continue
            n = 1 if unit == w else -(-(w - unit) // unit) + 1
            if n == 1 and unit != w or n > 7:
                continue
            step = round((w - unit) / (n - 1)) if n > 1 else 0
            if best is None or n < best[0]:
                best = (n, xexp, shape, step)
    assert best, w
    return best


def frames() -> list[tuple[int, ...]]:
    """(spritejä, X-laajennus, muoto, väri, Y-laajennus, vasen x, askel) joka viivakehykselle."""
    out = []
    for w, h, c in LINE:
        n, xexp, shape, step = layout(w)
        out.append((n, xexp, SHAPES.index(shape), c, int(h == 2), CX - w // 2, step))
    return out


def write(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for w in SHAPES:
        bits = (1 << 24) - (1 << (24 - w))
        rows.append(f"        .byte ${bits >> 16:02x}, ${bits >> 8 & 255:02x}, ${bits & 255:02x}\n"
                    "        .fill 61, 0")
    fr = frames()
    col = lambda k: ", ".join(str(f[k]) for f in fr)
    # ln_mode: bitit 0-2 spritejä, 3 X-laajennus, 4 vasemman x:n 9. bitti, 7 Y-laajennus
    mode = ", ".join(f"${n | xexp << 3 | (left >> 8) << 4 | yexp << 7:02x}" for n, xexp, _, _, yexp, left, _ in fr)
    (d / "crt.inc").write_text(
        "; tools/disk/crt.py: vakiot ja kaistan taulut (latausalue)\n"
        f"CY = {CY}\nNBAND = {len(BAND)}\nNLINE = {len(fr)}\nNSHAPE = {len(SHAPES)}\n"
        f"band_top .byte {', '.join(str(CY - h) for h in BAND)}\n"
        f"band_bot .byte {', '.join(str(CY + h) for h in BAND)}\n")
    (d / "crt_ajo.inc").write_text(
        "; tools/disk/crt.py: viivan kehystaulu (ajoalue)\n"
        f"ln_mode .byte {mode}\nln_ptr  .byte {col(2)}\nln_col  .byte {col(3)}\n"
        f"ln_xlo  .byte {', '.join(str(f[5] & 255) for f in fr)}\nln_step .byte {col(6)}\n")
    (d / "crt_muodot.inc").write_text("; tools/disk/crt.py: muodot (64 t:n lohkot)\n" + "\n".join(rows) + "\n")


def syms(labels: Path, out: Path, want: set[str] | None = None) -> None:
    """Sisääntulot VICE-labelsista kohtaustaulun includeksi (myös ilotulitus.py)."""
    want = set(want or {"crt_go", "crt_end"})
    lines = []
    for ln in labels.read_text().splitlines():
        a, name = ln.split()[1], ln.split()[2].lstrip(".")
        if name in want:
            lines.append(f"{name} = ${a}")
            want.discard(name)
    if want:
        raise SystemExit(f"syms: {labels}: puuttuu {sorted(want)}")
    out.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "syms":
        syms(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        write(Path(sys.argv[1]))
