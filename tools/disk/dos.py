"""MS-DOS-käynnistyksen data (src/runko/dos.asm): PC-henkinen 4x8-kirjasin
80 sarakkeeseen ja kirjoituskäsikirjoitus tekstit.yaml:n avaimesta dos.

  python3 -I tools/disk/dos.py OUT [GLUE]   # OUT/dos_data.inc (kirjasin, käsikirjoitus, DOS_FRAMES); GLUE: osalevyn
                                            # dos kohtaustaulu (SCENE_END literaalina)

Käsikirjoitus on tapahtumia [viive kehyksinä, op, ...]: 0 loppu, 1 tulosta (n, merkit), 2 rivinvaihto,
3 näppäin (merkki, kohinan taajuus, tömähdyksen AD; merkki $0d = Enter, $08 = askelpalautin), 4 tyhjä (pitkä tauko).
Kirjoitusvarianssi ja naputuksen sävy tulevat kiinteällä siemenellä, joten sama teksti antaa saman ajon.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import tekstit  # noqa: E402

COLS = 80
SEED = 1989
PART_TAIL = 50                          # osalevyn SCENE_END: käsikirjoitus + vierityksien IRQ:n viemät kehykset + pimeä

# 4x8-solu, kirjain 3 px leveä (oikea sarake on väli) kuten IBM PC:n 8x8-kirjasin puoliksi kavennettuna: versaalit
# riveillä 0-6, gemenat 2-6, alapidennys rivillä 7. Rivit "/":lla erotettuna, puuttuvat rivit tyhjiä.
FONT = {
    " ": "",
    "!": ".#./.#./.#./.#./.#./.../.#.",
    '"': "#.#/#.#",
    "#": ".../#.#/###/#.#/###/#.#",
    "$": ".#./.##/#../.#./..#/##./.#.",
    "%": "#../#.#/..#/.#./#../#.#/..#",
    "&": ".#./#.#/.#./##./#.#/#.#/.##",
    "'": ".#./.#.",
    "(": "..#/.#./#../#../#../.#./..#",
    ")": "#../.#./..#/..#/..#/.#./#..",
    "*": ".../#.#/.#./###/.#./#.#",
    "+": ".../.#./.#./###/.#./.#.",
    ",": ".../.../.../.../.../##./##./#..",
    "-": ".../.../.../###",
    ".": ".../.../.../.../.../##./##.",            # 2x2 kuten CGA:ssa: 1 px piste hukkuisi (".." näyttäisi tyhjältä)
    "/": "..#/..#/.#./.#./.#./#../#..",
    "0": ".#./#.#/#.#/#.#/#.#/#.#/.#.",
    "1": ".#./##./.#./.#./.#./.#./###",
    "2": "##./..#/..#/.#./#../#../###",
    "3": "##./..#/..#/.#./..#/..#/##.",
    "4": "#.#/#.#/#.#/###/..#/..#/..#",
    "5": "###/#../#../##./..#/..#/##.",
    "6": ".##/#../##./#.#/#.#/#.#/.#.",
    "7": "###/..#/..#/.#./.#./.#./.#.",
    "8": ".#./#.#/#.#/.#./#.#/#.#/.#.",
    "9": ".#./#.#/#.#/.##/..#/..#/##.",
    ":": ".../.../.#./.../.../.#.",
    ";": ".../.../.#./.../.../.#./#..",
    "<": ".../..#/.#./#../.#./..#",
    "=": ".../.../###/.../###",
    ">": ".../#../.#./..#/.#./#..",
    "?": "##./..#/..#/.#./.#./.../.#.",
    "@": ".#./#.#/###/###/##./#../.##",
    "A": ".#./#.#/#.#/###/#.#/#.#/#.#",
    "B": "##./#.#/#.#/##./#.#/#.#/##.",
    "C": ".##/#../#../#../#../#../.##",
    "D": "##./#.#/#.#/#.#/#.#/#.#/##.",
    "E": "###/#../#../##./#../#../###",
    "F": "###/#../#../##./#../#../#..",
    "G": ".##/#../#../#.#/#.#/#.#/.##",
    "H": "#.#/#.#/#.#/###/#.#/#.#/#.#",
    "I": "###/.#./.#./.#./.#./.#./###",
    "J": "..#/..#/..#/..#/..#/#.#/.#.",
    "K": "#.#/#.#/##./#../##./#.#/#.#",
    "L": "#../#../#../#../#../#../###",
    "M": "#.#/###/###/#.#/#.#/#.#/#.#",
    "N": "##./#.#/#.#/#.#/#.#/#.#/#.#",
    "O": ".##/#.#/#.#/#.#/#.#/#.#/##.",
    "P": "##./#.#/#.#/##./#../#../#..",
    "Q": ".#./#.#/#.#/#.#/#.#/##./.##",
    "R": "##./#.#/#.#/##./#.#/#.#/#.#",
    "S": ".##/#../#../.#./..#/..#/##.",
    "T": "###/.#./.#./.#./.#./.#./.#.",
    "U": "#.#/#.#/#.#/#.#/#.#/#.#/###",
    "V": "#.#/#.#/#.#/#.#/#.#/.#./.#.",
    "W": "#.#/#.#/#.#/#.#/###/###/#.#",
    "X": "#.#/#.#/.#./.#./.#./#.#/#.#",
    "Y": "#.#/#.#/#.#/.#./.#./.#./.#.",
    "Z": "###/..#/..#/.#./#../#../###",
    "[": "##./#../#../#../#../#../##.",
    "\\": "#../#../.#./.#./.#./..#/..#",
    "]": ".##/..#/..#/..#/..#/..#/.##",
    "^": ".#./#.#",
    "_": ".../.../.../.../.../.../.../###",
    "`": "#../.#.",
    "a": ".../.../##./..#/.##/#.#/.##",
    "b": "#../#../##./#.#/#.#/#.#/##.",
    "c": ".../.../.##/#../#../#../.##",
    "d": "..#/..#/.##/#.#/#.#/#.#/.##",
    "e": ".../.../.#./#.#/###/#../.##",
    "f": ".##/.#./###/.#./.#./.#./.#.",
    "g": ".../.../.##/#.#/#.#/.##/..#/##.",
    "h": "#../#../##./#.#/#.#/#.#/#.#",
    "i": ".#./.../##./.#./.#./.#./###",
    "j": "..#/.../..#/..#/..#/..#/#.#/.#.",
    "k": "#../#../#.#/#.#/##./#.#/#.#",
    "l": "##./.#./.#./.#./.#./.#./###",
    "m": ".../.../###/###/#.#/#.#/#.#",
    "n": ".../.../##./#.#/#.#/#.#/#.#",
    "o": ".../.../.#./#.#/#.#/#.#/.#.",
    "p": ".../.../##./#.#/#.#/##./#../#..",
    "q": ".../.../.##/#.#/#.#/.##/..#/..#",
    "r": ".../.../#.#/##./#../#../#..",
    "s": ".../.../.##/#../.#./..#/##.",
    "t": ".#./.#./###/.#./.#./.#./..#",
    "u": ".../.../#.#/#.#/#.#/#.#/.##",
    "v": ".../.../#.#/#.#/#.#/.#./.#.",
    "w": ".../.../#.#/#.#/###/###/#.#",
    "x": ".../.../#.#/#.#/.#./#.#/#.#",
    "y": ".../.../#.#/#.#/#.#/.##/..#/##.",
    "z": ".../.../###/..#/.#./#../###",
    "{": "..#/.#./.#./#../.#./.#./..#",
    "|": ".#./.#./.#./.#./.#./.#./.#./.#.",
    "}": "#../.#./.#./..#/.#./.#./#..",
    "~": ".../.../#../###/..#",
}


def glyph(ch: str) -> list[int]:
    rows = (FONT[ch].split("/") if FONT[ch] else []) + ["..."] * 8
    out = []
    for r in rows[:8]:
        out.append(sum(1 << (3 - i) for i, c in enumerate(r) if c == "#"))   # bitit 3..1, bitti 0 väli
    return out


def font() -> list[int]:
    """Merkit $20-$7f puolitavun alabiteissä (dos.asm putc siirtää vasemman sarakkeen ylös)."""
    lo = []
    for code in range(32, 128):
        lo += glyph(chr(code)) if chr(code) in FONT else [0] * 8
    return lo


class Script:
    def __init__(self) -> None:
        self.ev: list[int] = []
        self.wait = 0                   # viive seuraavaan tapahtumaan
        self.frames = 0

    def emit(self, *op: int) -> None:
        while self.wait > 255:
            self.ev += [255, 4]
            self.frames += 255
            self.wait -= 255
        self.ev += [self.wait, *op]
        self.frames += self.wait
        self.wait = 0


# Musiikki: Patemathicin Appeltrad Act 0 aivan alkuun.
# Intro on laulurivit 0-4 (kehykset 0-1200: riffi äänellä 2, rivi 4 nousu),
# rivistä 5 pääbiisin groove. Kelaus ACT0_SEEK = ACT0_INTRO - DOS_FRAMES, joten DOS_END osuu nousun loppuun.
# Näppäinten kohinanaksahdus vain äänellä 1 ja vain ennen act 0:n kehystä ACT0_V1 (äänen 1 ensimmäinen nuotti on
# rivin 4 rivillä 23 = kehys noin 1132; vara soittimen hard restartille), tömähdys (ääni 2, act 0:n riffi) pois.
# Act 0 häivytetään nollaan ennen rivin 4 nousua (nousu kuulostaisi biisin väärältä alulta; se alkaa act 0:n
# kehyksessä noin 1140): taso 15 -> 0 kehyksissä ACT0_FADE .. ACT0_FADE + 32, sen jälkeen hiljaa DOS_ENDiin asti,
# jolloin ainoa alku on pääbiisin häivytys sisään.
ACT0_INTRO = 1200
ACT0_V1 = 1110
ACT0_FADE = 1078


def build(items: list[str]) -> tuple[list[int], int, int]:
    rng = random.Random(SEED)
    s = Script()
    s.wait = 1
    after_enter = False
    lines = 0

    def key(ch: int, fhi: int, ad: int) -> None:
        s.emit(3, ch, fhi, ad)

    for item in items:
        if item.startswith("[tauko") and item.endswith("]"):
            s.wait += round(float(item[6:-1].strip().replace(",", ".")) * 50)
            continue
        printed, bar, typed = item.partition("|")
        if len(printed) + len(typed.replace("<", "")) > COLS - 1:
            raise SystemExit(f"tekstit.yaml dos: rivi yli {COLS - 1} merkkiä: {item!r}")
        for ch in printed + typed:
            if ch not in FONT and ch != "<":
                raise SystemExit(f"tekstit.yaml dos: merkkiä {ch!r} ei ole kirjasimessa (tools/disk/dos.py FONT): {item!r}")
        # komento ajetaan Enterin jälkeen (levy, hakemisto), seuraavat rivit tulevat tasaisesti
        s.wait += rng.randint(8, 14) if after_enter else 2
        after_enter = False
        lines += 1
        if printed:
            data = printed.encode("ascii")
            s.emit(1, len(data), *data)
        if not bar:
            s.emit(2)
            continue
        # kirjoitus: miettiminen kehotteen jälkeen, näppäinväli 4-14 kehystä, sanan jälkeen pidempi,
        # kirjoitusvirheen huomaaminen ennen askelpalautinta, tauko ennen Enteriä
        s.wait += rng.randint(40, 70) if not typed else rng.randint(22, 40)
        prev = ""
        for ch in typed:
            if ch == "<":
                s.wait += rng.randint(18, 28) if prev != "<" else rng.randint(5, 8)
                key(8, rng.randint(0x34, 0x58), 0x01)
            else:
                if prev == "<":
                    s.wait += rng.randint(9, 14)
                elif prev:
                    s.wait += max(4, min(14, round(rng.triangular(4, 14, 6))))
                    if prev == " ":
                        s.wait += rng.randint(3, 8)
                if ch == " ":
                    key(32, rng.randint(0x1c, 0x28), 0x02)
                else:
                    key(ord(ch), rng.randint(0x38, 0x68), rng.choice((0x00, 0x01)))
            prev = ch
        if typed:
            s.wait += rng.randint(12, 22)
        key(13, rng.randint(0x10, 0x18), 0x03)
        after_enter = True
    s.wait += 1
    s.emit(0)
    return s.ev, s.frames, lines


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    ev, frames, lines = build(tekstit.lista("dos"))
    seek = ACT0_INTRO - frames
    if seek < 0:
        raise SystemExit(f"tekstit.yaml dos: {frames} kehystä, act 0:n intro vain {ACT0_INTRO} (DOS_END nousun jälkeen)")
    lo = font()

    def rows(name: str, data: list[int]) -> list[str]:
        r = [name]
        for i in range(0, len(data), 16):
            r.append("        .byte " + ", ".join(f"${b:02x}" for b in data[i:i + 16]))
        return r

    text = ["; Generoitu: tools/disk/dos.py (tekstit.yaml dos). Älä muokkaa.",
            f"DOS_FRAMES = {frames}                ; käsikirjoituksen kesto kehyksinä ({frames / 50:.1f} s)",
            f"ACT0_SEEK = {seek}                ; act 0 kelataan tähän DOS_GOssa: DOS_END kehyksellä {ACT0_INTRO}",
            f"CLICK_END = {max(0, ACT0_V1 - seek)}                ; naksahdukset (ääni 1) vain ennen tätä IRQ:ta",
            f"FADE_AT = {max(0, ACT0_FADE - seek)}                ; act 0:n häivytys nollaan alkaa tästä IRQ:sta",
            *rows("font", lo), *rows("script", ev)]
    (out / "dos_data.inc").write_text("\n".join(text) + "\n")
    print(f"dos: {lines} riviä, käsikirjoitus {len(ev)} t, {frames} kehystä ({frames / 50:.1f} s)")
    if len(sys.argv) > 2:
        glue = Path(sys.argv[2])
        glue.parent.mkdir(parents=True, exist_ok=True)
        glue.write_text(GLUE.format(end=frames + PART_TAIL))


GLUE = """; Generoitu: tools/disk/dos.py (osalevy dos, runko PART 99). Älä muokkaa.
; MS-DOS-käynnistys omana osalevynään: kello alkaa DOS-ruudun alussa (koko demossa DOS on ennen
; kelloa). SCENE_END = käsikirjoitus + vara, literaalina.
SCENE_START = 0
SCENE_END = {end}
        #S_LOAD f_act0                  ; act 0 $a000- (DOS-ruudun musiikki, tools/music/music.py --laulu act0)
        #S_LOAD f_command               ; $e400- (src/runko/dos.asm), bittikartat $c000- ja $6000- DOS_GOssa
        #S_START SCENE_START
        #S_CALL DOS_PART                ; koko DOS-ruutu, palaa pimeänä
"""


if __name__ == "__main__":
    main()
