"""Demon osa paloiksi levylle ja sisääntulot kohtaustaululle (src/scene/koti_glue.asm):

  python3 -I src/proto/koti/split.py build/koti/demo

koti.prg + koti.labels -> purun aikana ladattavat koti1.prg ($1a00-koti1_end: koodi, taulut ja ylimmän asettelun
värit), koti2.prg ($c000-koti2_end: ylimmän asettelun ruutu ja spritelohkot) ja koti3.prg ($e000-koti3_end: ylimmän
asettelun bittikartta) sekä kodin pyöriessä ladattava koti4.prg (rec_first-rec_end: alempien asettelujen
uudet rivit, $4800-; vapaa koti_buildin palattua), koti5.prg (illan maski $4800-, koti_buildin jälkeen) ja syms.inc (koti_init1, koti_go, koti_build, koti_quiet). levy.json:n names_from lukee nimet glue-tiedoston
S_LOAD-riveistä.
"""
import re
import sys
from pathlib import Path

ENTRIES = ["koti_init1", "koti_show", "koti_go", "koti_build", "koti_quiet"]
PRE = [(0x1A00, 0x4000), (0xC000, 0xD000), (0xE000, 0xFFFA)]   # purun aikana vapaat
LATE = (0x4800, 0x8000)                                         # purun näyttöpankki 1: vapaa vasta kodin alettua

d = Path(sys.argv[1])
lab = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "koti.labels").read_text(), re.M)}
b = (d / "koti.prg").read_bytes()
a0 = b[0] | b[1] << 8
parts = [(a0, lab["koti1_end"]), (0xC000, lab["koti2_end"]), (0xE000, lab["koti3_end"]), (lab["rec_first"], lab["rec_end"])]
for (lo, hi), (plo, phi) in zip(parts, PRE + [LATE]):
    assert plo <= lo < hi <= phi, f"pala ${lo:04x}-${hi:04x} ei ole alueella ${plo:04x}-${phi:04x}"
    assert 2 + hi - a0 <= len(b), f"koti.prg loppuu ennen ${hi:04x}"
for i, (lo, hi) in enumerate(parts, 1):
    (d / f"koti{i}.prg").write_bytes(bytes([lo & 255, lo >> 8]) + b[2 + lo - a0:2 + hi - a0])
k5, n5 = lab["koti5_phys"], lab["koti5_end"] - lab["koti5"]    # KOTI5: illan maski koti_buildin jälkeen tietueiden päälle
assert lab["koti5"] == LATE[0] and lab["koti5_end"] <= lab["cred_data"] and 2 + k5 + n5 - a0 <= len(b)
(d / "koti5.prg").write_bytes(bytes([0x00, 0x48]) + b[2 + k5 - a0:2 + k5 + n5 - a0])
(d / "syms.inc").write_text("".join(f"{n} = ${lab[n]:04x}\n" for n in ENTRIES)
                            + f"koti4_live = ${lab['cred_data']:04x}\n")   # KOTI4:stä käytössä loppuun (tekijät)
