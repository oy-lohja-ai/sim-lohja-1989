"""Rasterikernelien yhteiset työkalut (build.py-generaattorit): VIC:n BA-malli, syklitarkka koodigeneraattori,
MC-merkistö ja asm-taulut. Käyttö: sys.path.insert(0, ROOT / "src/lib"); import raster.

BA-malli (PAL, 63 sykliä riviltä, syklit 1-63): badline (rivi 48-247, rivi & 7 == YSCROLL) pitää BA:n alhaalla
sykleillä 12-54; spritet (valinnainen) syklistä 55 seuraavan rivin sykliin 10. Lukusykli odottaa BA:n nousua,
kirjoitus ei odota (6510 pysähtyy vasta ensimmäiseen lukuun). Greetsien kernelin kaikki 124 I/O-kirjoitusta osuvat
mallissa samaan rivi:sykli-kohtaan kuin VICE:ssä.
"""
from __future__ import annotations

from typing import Callable

BA_BL = (12, 54)              # badlinen BA alhaalla (syklit)
BA_SPR = (55, 10)             # spritejen DMA: rivin sykli 55 -> seuraavan rivin sykli 10


class Vic:
    """BA-malli: yscroll (badlinen vaihe) ja valinnainen spritejen DMA-rivi-predikaatti."""

    def __init__(self, yscroll: int = 3, sprite_line: Callable[[int], bool] | None = None):
        self.yscroll = yscroll
        self.sprite_line = sprite_line or (lambda line: False)

    def badline(self, line: int) -> bool:
        return 48 <= line <= 247 and (line & 7) == self.yscroll

    def ba_low(self, line: int, cyc: int) -> bool:
        if self.badline(line) and BA_BL[0] <= cyc <= BA_BL[1]:
            return True
        if cyc >= BA_SPR[0] and self.sprite_line(line + 1):
            return True
        if cyc <= BA_SPR[1] and self.sprite_line(line):
            return True
        return False


class Sim:
    """CPU-syklit BA-mallilla: lukusykli odottaa, kunnes BA on ylhäällä; kirjoitus ei odota."""

    def __init__(self, vic: Vic, line: int, cyc: int):
        self.vic, self.line, self.cyc = vic, line, cyc
        self.writes: list[tuple[str, int, int]] = []

    def pos(self) -> tuple[int, int]:
        return self.line, self.cyc

    def step(self):
        self.cyc += 1
        if self.cyc > 63:
            self.cyc, self.line = 1, self.line + 1

    def run(self, pat: str, reg: str | None = None) -> tuple[int, int]:
        first = None
        for t in pat:
            if t == "R":
                while self.vic.ba_low(self.line, self.cyc):
                    self.step()
            if first is None:
                first = self.pos()
            if t == "W" and reg:
                self.writes.append((reg, self.line, self.cyc))
            self.step()
        return first


# Syklikuviot (R = luku, W = kirjoitus). Indeksoidut luvut olettavat, ettei sivu ylity (generaattori tarkistaa
# tauluilla .cerror- tai tasausehdoin); (zp),y samoin.
PAT = {"imm": "RR", "zp": "RRR", "zpw": "RRW", "abs": "RRRR", "absw": "RRRW", "impl": "RR", "indy": "RRRRR"}


def mode_of(asm: str) -> str:
    """Osoitusmuoto käskystä. Nollasivun muuttujat nimetään z_-alkuisiksi (tai zp-osoite $xx)."""
    op, _, arg = asm.partition(" ")
    if not arg:
        return "impl"
    if arg.startswith("("):
        return "indy"
    w = op in ("sta", "stx", "sty")
    if arg.startswith("#"):
        return "imm"
    zp = arg.startswith("z_") or (arg.startswith("$") and len(arg.split(",")[0]) == 3)
    if w:
        return "zpw" if zp else "absw"
    return "zp" if zp else "abs"


class Gen:
    """Koodi ja sen ajoitus: jokainen käsky simuloidaan heti; rivit asm-tekstinä kommentteineen (rivi:sykli)."""

    def __init__(self, sim: Sim):
        self.sim, self.lines = sim, []

    def i(self, asm: str, reg: str | None = None, note: str = "") -> tuple[int, int]:
        pat = PAT[mode_of(asm)]
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
        """Seuraavan käskyn ensimmäinen sykli kohtaan (line, cyc); väli ei saa sisältää BA:ta."""
        vic = self.sim.vic
        while vic.ba_low(*self.sim.pos()):    # seuraavan käskyn opkoodin luku odottaa joka tapauksessa
            self.sim.step()
        n = (line - self.sim.line) * 63 + (cyc - self.sim.cyc)
        if n < 0:
            raise ValueError(f"pad_to {line}:{cyc}: ollaan jo kohdassa {self.sim.pos()}")
        ln, cy = self.sim.pos()
        for _ in range(n):
            if vic.ba_low(ln, cy):
                raise ValueError(f"pad_to {line}:{cyc} ylittää BA:n kohdassa {ln}:{cy}")
            cy += 1
            if cy > 63:
                ln, cy = ln + 1, 1
        if n > 120:
            k = (n - 1 - 2 - 2) // 5            # ldy #k (2) + k * 5 - 1 + jäännös
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


def mc_byte(px) -> int:
    return (int(px[0]) << 6) | (int(px[1]) << 4) | (int(px[2]) << 2) | int(px[3])


class Charset:
    """Merkistö: solu (8 tavua) -> koodi, koodi 0 = tyhjä."""

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


def asm_bytes(label: str, data, per: int = 32) -> list[str]:
    data = bytes(data)
    out = [label]
    for i in range(0, len(data), per):
        out.append("        .byte " + ",".join(f"${b:02x}" for b in data[i:i + per]))
    return out
