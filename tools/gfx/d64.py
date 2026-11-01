"""Hillnerin osien tiedostot demon rungolle (levy: tools/disk/levy.py; kulku src/scene/hil_glue.asm):
raakadatan PRG:t ja osien sisääntulot kohtaustaululle.

  python3 tools/gfx/d64.py parts    # build/d64: music, fin, crane1, crane1b, crane1c, crane2, purku2, purku3 (.prg)
  python3 tools/gfx/d64.py syms     # build/d64/parts.inc: sisääntulot (src/runko/link.asm)
  python3 tools/gfx/d64.py kylsym   # build/d64/kylsym.inc: lähikuvan kyltin sisääntulot purulle
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
B = ROOT / "build"
D = B / "d64"
P = B / "purku"

KYL = ["kyltti_init", "kyltti_tick", "kyltti_render", "kyltti_fall"]
SYMS = [(B / "hilint/hillner.labels", ["hil_prep", "hil_go", "hil_main1", "hil_main2", "hil_main", "hil_fin", "hil_sign"], ""), (D / "kyltti.labels", KYL, ""),
        (D / "ajo.labels", KYL, "ajo_"), (D / "ajo.labels", ["ajo_on", "ajo_go"], ""),
        (D / "kyltti.labels", ["lahi_prep", "lahi_go", "lahi_on", "lahi_end"], ""), (D / "purku1.labels", ["purku_init", "purku_go", "purku_quiet", "purku_free_at", "purku_free_lo", "purku_free_end"], "")]


def prg(path: Path, addr: int, data: bytes) -> None:
    path.write_bytes(bytes([addr & 255, addr >> 8]) + data)


def labels(path: Path) -> dict[str, int]:
    out = {}
    for line in path.read_text().splitlines():
        m = re.match(r"al ([0-9a-fA-F]+) \.(\S+)$", line)
        if m:
            out[m.group(2)] = int(m.group(1), 16)
    return out


FADE_N = 24                     # src/proto/hillner/glue_lahi.asm
BAYER4 = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]


def fade_order() -> bytes:
    """Solujen askel 0..FADE_N-1 (rivit 3-20 riveittäin): vinoviiva vasemmalta ylhäältä oikealle alas, reunassa
    4 x 4 Bayer-kohina (pyyhkäisyn reuna on dither eikä suora viiva). glue_lahi.asm lahi_prep tekee tästä
    askelittaiset solulistat."""
    out = bytearray()
    for r in range(18):
        for c in range(40):
            u = (c + 1.6 * r) / (39 + 1.6 * 17)
            out.append(min(FADE_N - 1, int(u * (FADE_N - 4)) + BAYER4[(r & 3) * 4 + (c & 3)] // 4))
    return bytes(out)


def parts() -> None:
    D.mkdir(parents=True, exist_ok=True)
    music = (D / "music.bin").read_bytes()
    prg(D / "music.prg", 0x0800, music)
    # lähikuva siirtymää varten $e000: ruutu, bittikartta ja värit riveiltä 3-20 sekä pyyhkäisyn järjestys;
    # kuva kyltin buildista (kaista mustana skrollerin alla, src/proto/kyltti/build.py bg_image)
    K = B / "kyltti/mod"
    prg(D / "fin.prg", 0xE000, (K / "bg.scr").read_bytes() + (K / "bg.bmp").read_bytes() +
        (K / "bg.col").read_bytes() + fade_order())
    pieces, tausta = (P / "pieces.bin").read_bytes(), (P / "tausta.bin").read_bytes()
    assert 0x9800 + len(pieces) <= 0xBE40                # ajonaikaiset taulut $be40- (purku.asm ROWA)
    spr = (P / "sprites.bin").read_bytes()               # lohkot 0-14 purku3:n, loput purku2:n lopussa
    prg(D / "purku2.prg", 0x9800, pieces + bytes(0xC000 - 0x9800 - len(pieces)) + tausta + spr[15 * 64:])
    # kamera-ajo kahtena tiedostona: ajonaikaiset bittikartta $a000- ja ruutu $c000- jäävät lataamatta
    c = (B / "hilint/hillner.prg").read_bytes()
    a0 = c[0] | c[1] << 8
    body = c[2:]
    lab = labels(B / "hilint/hillner.labels")             # tiedostojen rajat: src/proto/hillner/build.py
    c1, c1b = lab["crane1_end"], lab["crane1b_end"]
    prg(D / "crane1.prg", a0, body[:c1 - a0])
    prg(D / "crane1b.prg", c1, body[c1 - a0:c1b - a0])
    prg(D / "crane1c.prg", 0x8C00, body[0x8C00 - a0:0xA000 - a0])
    prg(D / "crane2.prg", 0xC400, body[0xC400 - a0:])
    prg(D / "purku3.prg", 0xE000, (P / "rom3.bin").read_bytes() + spr[:15 * 64])  # BG2, värit, spritet 0-14


def syms() -> None:
    lines = ["; Generoitu: tools/gfx/d64.py syms (osien sisääntulot bootille)"]
    for path, names, prefix in SYMS:
        lab = labels(path)
        lines += [f"{prefix}{n} = ${lab[n]:04x}" for n in names if n in lab]
    inc = (P / "purku.inc").read_text()
    m = re.search(r"^BALL_SWING = (\d+)", inc, re.M)
    lines.append(f"BALL_SWING = {m.group(1)}")
    (D / "parts.inc").write_text("\n".join(lines) + "\n")


def kylsym() -> None:
    """Lähikuvan kyltin sisääntulot purulle (purku.asm: kyltti jatkuu purun alusta osuman jälkeiseen putoamiseen)."""
    lab = labels(D / "kyltti.labels")
    names = {"KYL_TICK": "kyltti_tick", "KYL_RENDER": "kyltti_render", "KYL_FALL": "kyltti_fall", "KYL_SPLIT": "kyl_split"}
    nspr = re.search(r"^K_NSPR = (\d+)", (B / "kyltti/mod/kyltti.inc").read_text(), re.M).group(1)
    (D / "kylsym.inc").write_text("; Generoitu: tools/gfx/d64.py kylsym\n" +
                                  "".join(f"{k} = ${lab[v]:04x}\n" for k, v in names.items()) +
                                  f"KYL_NSPR = {nspr}              ; kyltin hw-spritet 0..KYL_NSPR-1\n")


if __name__ == "__main__":
    {"parts": parts, "syms": syms, "kylsym": kylsym}[sys.argv[1]]()
