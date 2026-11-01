"""Levynkääntöruudun data (kaansi.inc): kirjaimet spriteinä kyltin kirjaimistosta (src/proto/kyltti/font.py,
sama versaaligroteski ja Ä), sijainnit ja taustan ditteröity liukuväri. Teksti Lohjan murretta: "KÄÄN SI LEVY".

  uv run --project tools/concept python -I tools/disk/kaansi.py OUTDIR    # OUTDIR/kaansi.inc ja puolib.prg
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/proto/kyltti"))
import font  # noqa: E402

H = 19                      # kirjainkorkeus (sprite 21 riviä: 1 rivi tyhjää ylä- ja alapuolelle)
KX = 1 / 0.936              # PAL-pikselin muoto
GAP = 3                     # kirjainväli spritejen välillä
PAIR_GAP = 1                # kirjainväli saman spriten parissa (SI, LE: L:n avoin oikea puoli antaa ilmaa)
SPACE = 7                   # sanaväli
X0 = 24 + 160               # ruudun keskikohta spritekoordinaateissa
ID_AT = 0xB000              # puolen B tunnistetiedosto (src/runko/levynvaihto.asm ID_AT)

# kirjainryhmät spriteihin (kokonaiset kirjaimet: aalto liikuttaa spriteä, joten kirjain ei saa jakautua)
TEXTS = {"kaansi": ["K", "Ä", "Ä", "N", " ", "SI", " ", "LE", "V", "Y"],
         "kiitos": ["K", "I", "I", "T", "O", "S"]}


def group(chars: str) -> np.ndarray:
    gl = [font.glyph(c, H, KX) for c in chars]
    w = sum(g.shape[1] for g in gl) + PAIR_GAP * (len(gl) - 1)
    out = np.zeros((H, w), bool)
    x = 0
    for g in gl:
        out[:, x:x + g.shape[1]] = g
        x += g.shape[1] + PAIR_GAP
    return out


def sprite(g: np.ndarray) -> bytes:
    if g.shape[1] > 24:
        raise SystemExit(f"kaansi: kirjainryhmä {g.shape[1]} px > 24")
    s = np.zeros((21, 24), bool)
    x = (24 - g.shape[1]) // 2
    s[1:1 + H, x:x + g.shape[1]] = g
    out = bytearray()
    for r in s:
        for b in range(3):
            out.append(int("".join("1" if v else "0" for v in r[b * 8:b * 8 + 8]), 2))
    return bytes(out) + b"\0"


def layout(groups: list[str]) -> tuple[list[bytes], list[int]]:
    """Spritet ja niiden x-keskikohdat: ryhmät vierekkäin, välilyönti = SPACE."""
    sprites, centres, x = [], [], 0
    widths = [SPACE if gname == " " else group(gname).shape[1] for gname in groups]
    total = sum(widths) + GAP * (len(groups) - 1)
    x = -total // 2
    for gname, w in zip(groups, widths):
        if gname != " ":
            sprites.append(sprite(group(gname)))
            centres.append(X0 + x + w // 2)
        x += w + GAP
    return sprites, centres


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    lines = ["; Generoitu: tools/disk/kaansi.py"]
    for name, groups in TEXTS.items():
        spr, cx = layout(groups)
        if len(spr) > 8:
            raise SystemExit(f"kaansi: {name}: {len(spr)} spriteä")
        xs = [c - 12 for c in cx]
        lines.append(f"{name.upper()}_N = {len(spr)}")
        lines.append(f"{name}_xlo .byte " + ", ".join(f"${x & 255:02x}" for x in xs))
        lines.append(f"{name}_msb .byte ${sum(1 << i for i, x in enumerate(xs) if x > 255):02x}")
        lines.append(f"        .align 64")
        lines.append(f"{name}_spr")
        for s in spr:
            lines.append("        .byte " + ", ".join(f"${b:02x}" for b in s))
    # taustan liukuväri: jokaisella merkkirivillä oma merkki, jonka 8 pikseliriviä ovat Bayer 4x4 -ditteriä
    # jatkuvasta tiheydestä (ei porrasta merkkirivien välissä), musta $d021 = 0. Ylhäällä yötaivas mustasta
    # siniseen 6 tekstin taakse, sitten tumma kaista ja alhaalla järvi tummanharmaana 11 (luma lähellä mustaa).
    bayer = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]

    def density(y: int) -> tuple[float, int]:
        if y < 104:
            return 0.62 * (y / 104) ** 1.4, 6
        if y < 128:
            return 0.62 * (1 - (y - 104) / 24) ** 2, 6
        return 0.75 * ((y - 128) / 72) ** 0.8, 11

    chars, cols = [], []
    for r in range(25):
        rowbytes = []
        for yy in range(8):
            y = r * 8 + yy
            d, _ = density(y)
            bits = "".join("1" if bayer[y % 4][x % 4] < d * 16 else "0" for x in range(8))
            rowbytes.append(int(bits, 2))
        chars.append(rowbytes)
        cols.append(density(r * 8 + 4)[1])
    lines[1:1] = ["bg_chars"] + ["        .byte " + ", ".join(f"${b:02x}" for b in c) for c in chars]
    lines.append("bg_col  .byte " + ", ".join(str(c) for c in cols))
    (out / "kaansi.inc").write_text("\n".join(lines) + "\n")
    # puolen B tunnistetiedosto: allekirjoitus (src/runko/levynvaihto.asm s_puolib) ja täyte yli yhden lohkon
    sys.path.insert(0, str(ROOT / "tools/disk"))
    import d64
    body = d64.petscii("SIMLOHJA PUOLI B") + bytes(400)
    (out / "puolib.prg").write_bytes(bytes([ID_AT & 255, ID_AT >> 8]) + body)


if __name__ == "__main__":
    main()
