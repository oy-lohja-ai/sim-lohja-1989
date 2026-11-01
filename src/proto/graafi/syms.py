"""Kohtaustaulun sisääntulot ja levyn palat graafi.labels:sta: syms.py KANSIO -> KANSIO/syms.inc (graafi_init,
graafi_show, graafi_go), KANSIO/graafi1.prg (neuvonantaja $2000-kt_data_end) ja graafi2.prg (ruutu, koodi, taulut
ja bittikartta graafi2-graafi_end). Väliä ei ladata, jotta seuraavan kohtauksen palat voi esiladata graafin aikana."""
import re
import sys
from pathlib import Path

d = Path(sys.argv[1])
lab = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "graafi.labels").read_text(), re.M)}
(d / "syms.inc").write_text("".join(f"{n} = ${lab[n]:04x}\n" for n in ("graafi_init", "graafi_show", "graafi_go")))
b = (d / "graafi.prg").read_bytes()
a0 = b[0] | b[1] << 8
for nimi, lo, hi in (("graafi1", a0, lab["kt_data_end"]), ("graafi2", lab["graafi2"], lab["graafi_end"])):
    (d / f"{nimi}.prg").write_bytes(bytes([lo & 255, lo >> 8]) + b[2 + lo - a0:2 + hi - a0])
