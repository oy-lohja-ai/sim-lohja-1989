"""Kaupungintalon palat levylle ja sisääntulot kohtaustaululle (src/scene/kaupungintalo_glue.asm):

  python3 -I src/proto/kaupungintalo/split.py build/kaupungintalo/demo

kt.prg + kt.labels -> kt1.prg (huone ja kamera-ajo), kt2.prg (näyttö), kt0.prg (ydin), kt3.prg (pelin ruutu
bittikarttana); kt6.prg = kamera-ajon alkukuvan bittikartta ($e000-$ff3f, ennen KT3:a, ../kooste.kla: ulkonäkymä);
peli.prg + peli.labels -> kt4.prg ja kt5.prg (peli); syms.inc (sisääntulot).
levy.json:n names_from lukee nimen glue-tiedoston S_LOAD-rivistä.
"""
import re
import sys
from pathlib import Path

# lähde -> sisääntulot ja palat: tiedosto -> (alku, lopun label); Krill ei lataa $d000-$dfff:ään
LAHTEET = {
    "kt": (["kt_init", "kt_go", "kt_peli_ok"],
           {"kt1.prg": (0x1A00, "kt1_data_end"), "kt2.prg": (0x8000, "kt2_data_end"),
            "kt0.prg": (0xC000, "kt0_end"), "kt3.prg": (0xE000, "kt3_end")}),
    "peli": (["peli_init"], {"kt4.prg": (0x2000, "kt4_end"), "kt5.prg": (0x6000, "kt5_end")}),
}

d = Path(sys.argv[1])
syms = []
for src, (entries, palat) in LAHTEET.items():
    lab = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / f"{src}.labels").read_text(), re.M)}
    b = (d / f"{src}.prg").read_bytes()
    a0 = b[0] | b[1] << 8
    assert all(lo >= a0 for lo, _ in palat.values()), (src, hex(a0))
    for name, (lo, end) in palat.items():
        hi = lab[end]
        assert lo < hi and not (lo < 0xE000 and hi > 0xD000), (name, hex(lo), hex(hi))
        (d / name).write_bytes(bytes([lo & 255, lo >> 8]) + b[2 + lo - a0:2 + hi - a0])
    syms += [f"{n} = ${lab[n]:04x}\n" for n in entries + ["kt_show"] if n in lab]     # kt_show ei rajauksessa
kla = (d.parent / "kooste.kla").read_bytes()
(d / "kt6.prg").write_bytes(bytes([0x00, 0xE0]) + kla[2:8002])          # kt6: alkukuvan bittikartta $e000-$ff3f
kam = re.search(r"^KAM_LOPPU = (\d+)", (d.parent / "kt.inc").read_text(), re.M)
syms.append(f"KAM_LOPPU = {kam[1]}\n")
(d / "syms.inc").write_text("".join(syms))
