"""Graafin taulut (data tools/gfx/data/graafi/): build.py OUT -> OUT/graafi.inc, graafi_data.asm
ja binäärit. Host antaa vain käyrien y-arvot, vuodet askeleittain ja kuvapalat; 6510 piirtää pisteet."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tools/gfx/data/graafi"
BITMAP, SCREEN = 0xA000, 0x8C00

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
for f in ("graafi.bin", "graafi_scr.bin", "numerot.bin", "neuvo.bin", "neuvo_teksti.bin"):
    shutil.copy(DATA / f, out / f)
d = json.loads((DATA / "graafi.json").read_text())
n = d["askeleet"]
gx0, gx1, gy0, gy1 = d["kaavio"]
v0, v1 = d["vuodet"]
r0, c0, r1, c1 = d["neuvo"]
inc = [f"ASKELEET = {n}", f"GX0 = {gx0}", f"VUOSI_RIVI = {d['vuosi_solu'][0]}", f"VUOSI_SAR = {d['vuosi_solu'][1]}",
       f"NEUVO_R0 = {r0}", f"NEUVO_C0 = {c0}", f"NEUVO_H = {r1 - r0}", f"NEUVO_W = {c1 - c0}",
       f"NEUVO_N = {len(d['neuvo_solut'])}"]
for k, c in d["varit"].items():
    inc.append(f"VARI_{k.upper()} = {c}")
a = []
for k in ("puutalot", "laatikot", "kulttuuri"):
    a.append(f"y_{k} .byte " + ", ".join(str(v) for v in d["kayrat"][k]))
# vuosi askeleittain: kaavion x-akseli 1960-2026, otsikossa nykyhetki 1989 alkaen
vuodet = [max(1989, round(v0 + (v1 - v0) * i / (n - 1))) for i in range(n)]
a.append("v_sat .byte " + ", ".join(str(y // 100 % 10) for y in vuodet))      # 9 tai 0 (1900 / 2000)
a.append("v_kym .byte " + ", ".join(str(y // 10 % 10) for y in vuodet))
a.append("v_yks .byte " + ", ".join(str(y % 10) for y in vuodet))
a.append("v_tuh .byte " + ", ".join(str(y // 1000) for y in vuodet))
a.append("row_lo .byte " + ", ".join(f"<{BITMAP + (y >> 3) * 320 + (y & 7)}" for y in range(200)))
a.append("row_hi .byte " + ", ".join(f">{BITMAP + (y >> 3) * 320 + (y & 7)}" for y in range(200)))
a.append("crow_lo .byte " + ", ".join(f"<{SCREEN + r * 40}" for r in range(25)))
a.append("crow_hi .byte " + ", ".join(f">{SCREEN + r * 40}" for r in range(25)))
cells = d["neuvo_solut"]
a.append("nt_lo .byte " + ", ".join(str(c & 255) for c in cells))
a.append("nt_hi .byte " + ", ".join(str(c >> 8) for c in cells))
(out / "graafi.inc").write_text("\n".join(inc) + "\n")
(out / "graafi_data.asm").write_text("\n".join(a) + "\n")
