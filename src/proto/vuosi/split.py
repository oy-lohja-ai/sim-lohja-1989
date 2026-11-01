"""Vuosipartin pala levylle ja sisääntulot kohtaustaululle (src/scene/vuosi<VUOSI>_glue.asm):

  python3 -I src/proto/vuosi/split.py build/vuosi/<VUOSI>/demo

vuosi.prg + vuosi.labels -> vuosi1.prg (merkistöt $2800-vic_end, VIC-pankki 0; ladataan vuosi.inc:n STAGEen,
vuosi_init kopioi), vuosi2.prg (taulut ja tapahtumataulu DATA_BASE-data_end) ja vuosi3.prg (IRQ, kerneli, init ja
kehyksen logiikka $e000-code_end) sekä
syms.inc.
levy.json:n names_from lukee nimen glue-tiedoston S_LOAD-rivistä.
"""
import re
import sys
from pathlib import Path

ENTRIES = ["vuosi_init", "vuosi_go", "vuosi_sauma"]   # vuosi_sauma vain STAGE-versiossa (2026)

d = Path(sys.argv[1])
lab = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "vuosi.labels").read_text(), re.M)}
b = (d / "vuosi.prg").read_bytes()
a0 = b[0] | b[1] << 8
assert a0 == 0x2400, hex(a0)
inc = {m[1]: int(m[2], 16) for m in re.finditer(r"^(\w+) = \$([0-9a-f]+)$", (d.parent / "vuosi.inc").read_text(), re.M)}
for i, (lo, hi, at) in enumerate([(inc["CHARSET"], lab["vic_end"], inc["STAGE"]), (lab["data_start"], lab["data_end"], None),
                                  (lab["irq_top"], lab["code_end"], None)], 1):
    at = lo if at is None else at       # VUOSI1 ladataan STAGEen (vuosi_init kopioi $2800:aan), ruutu ei ole levyllä
    (d / f"vuosi{i}.prg").write_bytes(bytes([at & 255, at >> 8]) + b[2 + lo - a0:2 + hi - a0])
(d / "syms.inc").write_text("".join(f"{n} = ${lab[n]:04x}\n" for n in ENTRIES if n in lab))
