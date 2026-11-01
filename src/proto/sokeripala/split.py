"""Sokeripalan palat levylle ja sisääntulot kohtaustaululle (src/scene/sokeripala_glue.asm):

  python3 -I src/proto/sokeripala/split.py build/sokeripala

sp.prg + sp.labels -> demo/sp0.prg (ydin), sp2a.prg (pyörähdys) ja sp4k.prg (taulun ajonaikainen koodi);
binääreistä (build.py) sppi.prg, spp1.prg, spp2.prg ja spp3.prg (panoraama), spt.prg (puskutraktorin spritet),
sp2d.prg (sivu), sp3.prg (peli), sp3b.prg (pelin solukopiot) ja sp4.prg (taulun bittikartta, taulu_jatkuu.bin),
spp3.prg:hen ja spt.prg:hen lisäksi puskutraktorin koodi sp.prg:stä (PAALLE); demo/syms.inc (sisääntulot ja kuvien
kehykset sp.inc:stä).
"""
import re
import sys
from pathlib import Path

PALAT = {"sp0.prg": (0x1A00, "sp0_end"), "sp2a.prg": (0x8000, "sp2a_end"), "sp4k.prg": (0x4800, "sp4k_end")}
KOOTUT = {"sppi.prg": [(0xC000, "pano_nousu.bin")], "spp1.prg": [(0x5C00, "pano_p1.bin")], "spp2.prg": [(0x4000, "pano_p2.bin")],
          "spp3.prg": [(0xC000, "pano_p3c.bin")], "spt.prg": [("TRAK_B", "trak_spr.bin")],
          "sp2d.prg": [(0x4000, "sivu_ev.bin"), (0x5C00, "sivu_scr.bin"), (0x6000, "sivu_bmp.bin")],
          "sp3.prg": [(0x8000, "peli_spr.bin"), (0x8900, "peli_heli.bin"), (0x8C00, "peli_scr.bin"), (0x9000, "peli_blob.bin"),
                      (0x9400, "peli_sprt.bin"), ("PELI_BLOB2", "peli_blob2.bin"), (0xA000, "peli_bmp.bin")],
          "sp3b.prg": [(0xE000, "pe_tab.bin")],
          "sp4.prg": [(0x6000, "taulu_jatkuu.bin")]}
ENTRIES = ["sp_init", "sp_show", "sp_go", "sp_lehti", "sp_sivu", "sp_taulu", "sp_trak"]
PAALLE = {"spp3.prg": ("TRAK_KOODI", "trak_end"), "spt.prg": ("TRAK_IRQ", "trak_irq_end")}  # koodi sp.prg:stä koottuun (puskutraktori)

d = Path(sys.argv[1])
inc = dict(ln.split(" = ") for ln in (d / "sp.inc").read_text().splitlines())
KOOTUT = {n: [(int(inc[a][1:], 16) if isinstance(a, str) else a, f) for a, f in osat] for n, osat in KOOTUT.items()}
demo = d / "demo"
demo.mkdir(exist_ok=True)
lab = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "sp.labels").read_text(), re.M)}
b = (d / "sp.prg").read_bytes()
a0 = b[0] | b[1] << 8
for name, (lo, end) in PALAT.items():
    hi = lab[end]
    assert a0 <= lo < hi and not (lo < 0xE000 and hi > 0xD000), (name, hex(lo), hex(hi))
    (demo / name).write_bytes(bytes([lo & 255, lo >> 8]) + b[2 + lo - a0:2 + hi - a0])
for name, osat in KOOTUT.items():
    lo = osat[0][0]
    data = bytearray()
    for a, f in osat:
        assert lo + len(data) <= a, (name, f)
        data += bytes(a - lo - len(data)) + (d / f).read_bytes()[:8000 if f.endswith(("bmp.bin", "jatkuu.bin")) else None]
    if name in PAALLE:
        a, end = int(inc[PAALLE[name][0]][1:], 16), lab[PAALLE[name][1]]
        data += bytes(max(0, end - lo - len(data)))
        assert lo <= a < end and not any(data[a - lo:end - lo]), (name, hex(a), hex(end))
        data[a - lo:end - lo] = b[2 + a - a0:2 + end - a0]
    assert not (lo < 0xE000 and lo + len(data) > 0xD000) and lo + len(data) <= 0xFFFA, name
    (demo / name).write_bytes(bytes([lo & 255, lo >> 8]) + data)
syms = [f"{n} = ${lab[n]:04x}\n" for n in ENTRIES] + [ln + "\n" for ln in (d / "sp.inc").read_text().splitlines()
                                                    if ln.startswith("T_")]
(demo / "syms.inc").write_text("".join(syms))
