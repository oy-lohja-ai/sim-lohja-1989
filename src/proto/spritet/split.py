"""Spritet osalevylle: build/spritet-lentavat/demo/spritet.prg (INTEGRATED, $1a00-) -> spr1.prg ($1a00-$7eff: koodi,
taulut, soittimen lopputila, spritekuvat, virran sivut), spr2.prg ($8000-$cfff tai $bfff, jos $c000-$cfff on vapaa:
kerneli, virran sivut) ja syms.inc (sisääntulot). Tiedostot vastaavat kohtaustaulun
src/scene/spritet-lentavat_glue.asm S_LOAD-rivejä.

  python3 -I src/proto/spritet/split.py build/spritet-lentavat/demo lentavat
"""
import json
import re
import sys
from pathlib import Path

ENTRIES = ["spr_init", "spr_show", "spr_go", "spr_hiljaa"]
FILES = [("spr1", 0x1A00, 0x7F00), ("spr2", 0x8000, 0xD000), ("spr3", 0xE000, 0xFF00)]
WIPE_FILES = [("py1", 0x1A00, 0x4000), ("py2", 0x4000, 0x8000), ("py3", 0x8000, 0xC000), ("py4", 0xC000, 0xD000),
              ("py5", 0xE000, 0xFF40)]          # koodi, pankki 1 (A), kerneli, pankki 3 (B)
d = Path(sys.argv[1])
lab = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "spritet.labels").read_text(), re.M)}
b = (d / "spritet.prg").read_bytes()
a0, end = b[0] | b[1] << 8, (b[0] | b[1] << 8) + len(b) - 2
assert a0 == 0x1A00, hex(a0)
variant = sys.argv[2] if len(sys.argv) > 2 else ""
if variant == "pyyhkaisy":
    FILES = WIPE_FILES
glue = Path(__file__).resolve().parents[2] / f"scene/spritet{'-' + variant if variant else ''}_glue.asm"
want = re.findall(r"^\s*#S_LOAD f_(\w+)", glue.read_text(), re.M)
made = []
if variant != "pyyhkaisy" and end > 0xFF00:          # vajaa viimeinen logotaulusivu $ff00- (ennen vektoreita)
    assert end <= 0xFFFA, hex(end)
    FILES = FILES[:-1] + [("spr3", 0xE000, end)]
if variant != "pyyhkaisy" and end > 0x7F00 and any(b[2 + 0x7F00 - a0:2 + 0x7FFF - a0]):
    FILES = [("spr1", 0x1A00, 0x8000)] + FILES[1:]   # tiivis virta käyttää sivua $7f ($7fff = 0 jää ennalleen)
free = set(json.loads((d.parent / "vapaat.json").read_text())) if (d.parent / "vapaat.json").exists() else set()
if "spr2b" in want:                                               # spr2 $8000-$bfff ja spr2b $c000-$cfff, jonka
    i = [n for n, _, _ in FILES].index("spr2")                    # glue lataa erikseen spr_hiljaan jälkeen
    FILES[i:i + 1] = [("spr2", 0x8000, 0xC000), ("spr2b", 0xC000, 0xD000)]
elif variant in ("lentavat", "kasvu"):       # $c000-$cfff ei ladata (ilotulitus $c400-$cdff ennätyksen yli)
    assert not any(b[2 + 0xC000 - a0:2 + 0xD000 - a0]), "lentavat: dataa $c000-$cfff:ssä, mutta glue ei lataa sitä"
    FILES = [(n, lo, 0xC000 if n == "spr2" else hi) for n, lo, hi in FILES]
elif variant != "pyyhkaisy" and set(range(0xC0, 0xD0)) <= free:
    FILES = [(n, lo, 0xC000 if n == "spr2" else hi) for n, lo, hi in FILES]   # $c000-$cfff vapaa: ei levylle
for name, lo, hi in FILES:
    hi = min(hi, end)
    if hi > lo:
        data = b[2 + lo - a0:2 + hi - a0]
        if len(data) + 2 <= 254:                # yksi lohko: Krill ei lataa sitä oikein, joten sivun loppuun nollilla
            data += bytes(-hi % 256 or 256)     # (sama sivu, kaksi lohkoa)
        (d / f"{name}.prg").write_bytes(bytes([lo & 255, lo >> 8]) + data)
        made.append(name)
for name, lo, _ in FILES:                       # glue lataa, mutta data ei yllä alueelle: sivu nollia, kaksi lohkoa
    if name in want and name not in made:       # (osajoukko tiedoston alueesta)
        (d / f"{name}.prg").write_bytes(bytes([lo & 255, lo >> 8]) + bytes(256))
        made.append(name)
assert sorted(made) == sorted(want), f"split.py tekee {made}, {glue.name} lataa {want}"
(d / "syms.inc").write_text("".join(f"{n} = ${lab[n]:04x}\n" for n in ENTRIES if n in lab))
