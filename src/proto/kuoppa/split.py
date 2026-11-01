"""Kuopan palat levylle ja sisääntulot kohtaustaululle (src/scene/kuoppa_glue.asm):

  python3 -I src/proto/kuoppa/split.py build/kuoppa/demo

kuoppa.prg + kuoppa.labels -> kp0.prg, kp0s.prg (kuoppa-kyltit: kp0c.prg, koko ydin), kp1.prg (koodi ja taulut, ks.
esilataus alla), kp1c.prg (kuva 1 pankissa 1, esisiirrot 0-1, spritet), kp1bs.prg ja kp1ds.prg (esisiirrot 2-3,
varsien kärjet välialueella). Kuvat 2 ja 3 suoraan build.py:n bin-tiedostoista (bittikartta 5760, ruutu 720, värit
720): kp2a.prg (ruutu $c478), kp2b.prg (bittikartta $e3c0, värit $fa40), kpy.prg (pyyhkäisy $fd10), kp3.prg (ruutu
$8478, värit $8800, koodi ja julkisivut) ja kp3b.prg (bittikartta $a3c0). syms.inc: sisääntulot. levy.json:n
names_from lukee nimet glue-tiedoston S_LOAD-riveistä.
"""
import json
import re
import sys
from pathlib import Path

ENTRIES = ["kp_stage", "kp_init", "kp_show", "kp_go"]
ENTRIES2 = ["kp2_init", "kp2_go", "py_init"]
ENTRIES3 = ["kp3_go", "kp3_init", "kp3_show", "kp3_col", "kp3_vic", "kp3_start", "kp_tauko", "kp_jatka"]
ENTRIES4 = ["kp4_go"]
BMP, SCR = 18 * 320, 18 * 40

if sys.argv[1] == "core":                       # core.inc kuvien 2-3 koodille: ytimen labelit
    d = Path(sys.argv[2])
    lab = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "kuoppa.labels").read_text(), re.M)}
    defs = set(re.findall(r"^([A-Za-z_]\w*)\s", (Path(__file__).parent / "kp_defs.inc").read_text(), re.M))
    lines = [f"{n} = ${a:04x}" for n, a in sorted(lab.items(), key=lambda t: t[1])
             if re.fullmatch(r"[A-Za-z]\w*", n) and 0x1a00 <= a <= lab["core_end"] and n not in defs]
    (d / "core.inc").write_text("; split.py core: kuoppa.asm:n ydin\n" + "\n".join(lines) + "\n")
    sys.exit(0)
if sys.argv[1] == "k3":                         # k3.inc kuoppa4:lle: kuvan 3 ryhmien vaihto ja tila (täyte)
    d = Path(sys.argv[2])
    lab3 = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "kuoppa3.labels").read_text(),
                                                       re.M)}
    (d / "k3.inc").write_text("; split.py k3: kuoppa3.asm\n" + "".join(f"{n} = ${lab3[n]:04x}\n"
                                                                         for n in ("toggle", "gstate", "ovr", "ntog", "kp_df")))
    sys.exit(0)
d = Path(sys.argv[1])
lab = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "kuoppa.labels").read_text(), re.M)}
b = (d / "kuoppa.prg").read_bytes()
a0 = b[0] | b[1] << 8
assert a0 == 0x1a00, hex(a0)


def prg(name: str, parts: list[tuple[int, bytes]]) -> None:
    """Osat (osoite, data) yhdeksi PRG:ksi, välit nollia; ei $d000-$dfff:ää (Krill ei lataa sinne)."""
    lo = min(a for a, _ in parts)
    hi = max(a + len(x) for a, x in parts)
    assert 0x1a00 <= lo and hi <= 0xfffa and (hi <= 0xd000 or lo >= 0xe000), (name, hex(lo), hex(hi))
    mem = bytearray(hi - lo)
    for a, x in parts:
        mem[a - lo:a - lo + len(x)] = x
    (d / f"{name}.prg").write_bytes(bytes([lo & 255, lo >> 8]) + bytes(mem))


def piece(s: int, e: int) -> tuple[int, bytes]:
    return s, b[2 + s - a0:2 + e - a0]


# Esilataus graafin aikana (kp_stage): paikalleen latautuvat KP0 ($1a00-STG_A), KP1 (stg_b-code_end) ja KP1C;
# graafin muistin päälle osuvat välialueille: KP0S (STG_A-stg_b) $c000:aan, KP1BS ja KP1DS $e000:aan.
STG_A, stg_b = 0x2000, lab["stg_b"]
prg("kp0", [piece(0x1a00, STG_A)])
prg("kp0c", [piece(0x1a00, lab["core_end"])])                    # kuoppa-kyltit: ydin kerralla paikalleen
prg("kp0s", [(0xc000, piece(STG_A, stg_b)[1])])
prg("kp1", [piece(stg_b, lab["code_end"])])
b2 = (d / "kuoppa2.prg").read_bytes()
lab2 = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "kuoppa2.labels").read_text(), re.M)}
a2 = b2[0] | b2[1] << 8
assert a2 == lab["core_end"], hex(a2)
prg("kp2r", [(a2, b2[2:2 + lab2["kp2r_end"] - a2])])
prg("kp2w", [(lab2["kp2w"], b2[2 + lab2["kp2w"] - a2:2 + lab2["kp2w_end"] - a2])])
prg("kp1c", [piece(lab["kp1c"], lab["kp1c_end"])])
prg("kp1bs", [(0xe000, piece(lab["kp1b"], lab["kp1b_end"])[1])])
prg("kp1ds", [(0xe000 + lab["kp1b_end"] - lab["kp1b"], piece(lab["kp1d"], lab["kp1d_end"])[1])])
k2 = (d.parent / "k2.bin").read_bytes()
k3 = (d.parent / "k3.bin").read_bytes()
prg("kp2a", [(0xc478, k2[BMP:BMP + SCR]), (0xc800, b2[2 + 0xc800 - a2:2 + lab2["kp2_end"] - a2])])
prg("kp2b", [(0xe000, b2[2 + 0xe000 - a2:2 + lab2["kp2t_end"] - a2]), (0xe3c0, k2[:BMP]), (0xfa40, k2[BMP + SCR:])])
prg("kpy", [(0xfd10, b2[2 + 0xfd10 - a2:2 + lab2["py_end"] - a2])])           # pyyhkäisy kuvasta 1 (levyn loppuun)
b3 = (d / "kuoppa3.prg").read_bytes()
lab3 = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "kuoppa3.labels").read_text(), re.M)}
assert (b3[0] | b3[1] << 8) == 0x8ad0
assert lab3["kp3_end"] <= 0x9D00, "kp3_end yli $9d00 (torni.py JULKI_ALUEET)"
julki = [(a, bytes.fromhex(h)) for a, h in json.loads((d.parent / "kp_julki.json").read_text())]
# kuva 3 kahtena tiedostona: koko demossa toinen esiladataan kuopan kuvan 2 aikana, jossa lataus on
# hidasta (noin 12 kehystä lohkolta), ja loput taulu2b:n aikana: koko KP3 kuopan aikana myöhästyttäisi taulu2b:n saumaa
p3 = [(0x8478, k3[BMP:BMP + SCR]), (0x8800, k3[BMP + SCR:]), (0x8ad0, b3[2:2 + lab3["kp3_end"] - 0x8ad0]),
      (0xa3c0, k3[:BMP]), *julki]   # julkisivut (torni.py JULKI_ALUEET)
assert all(a + len(x) <= 0xa000 or a >= 0xa000 for a, x in p3)
prg("kp3", [(a, x) for a, x in p3 if a < 0xa000])      # $8200-: ruutu, värit, koodi, julkisivut
prg("kp3b", [(a, x) for a, x in p3 if a >= 0xa000])    # $a3c0-$bf3f: bittikartta (ja julkisivut)
b4 = (d / "kuoppa4.prg").read_bytes()
lab4 = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "kuoppa4.labels").read_text(), re.M)}
assert (b4[0] | b4[1] << 8) == 0x2800
prg("kp4", [(0x2800, b4[2:2 + lab4["kp4_end"] - 0x2800])])      # kuoppa-kyltit: kyltit ja liike (kuva 3)
(d / "syms.inc").write_text("".join(f"{n} = ${lab[n]:04x}\n" for n in ENTRIES) +
                            "".join(f"{n} = ${lab2[n]:04x}\n" for n in ENTRIES2) +
                            "".join(f"{n} = ${lab3[n]:04x}\n" for n in ENTRIES3) +
                            "".join(f"{n} = ${lab4[n]:04x}\n" for n in ENTRIES4))
