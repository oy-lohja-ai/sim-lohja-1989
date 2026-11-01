"""Demon osa paloiksi levylle ja sisääntulot kohtaustaululle (src/scene/greetsit_glue.asm):

  python3 -I src/proto/greetsit/split.py build/greetsit/demo

greetsit.prg + greetsit.labels -> greetsit6.prg ja greetsit7.prg (VIC-pankin 1 data $4800-$7fff: merkistöt A ja T,
runko- ja varjospritet, color_u; ladataan muualle, greetsit_kopio siirtää paikalleen), greetsit5.prg (koodi, kerneli,
kartat, tasot ja taulut $8000-code_end; ruudut, tien merkistö ja skrollerin puskurit ovat ajonaikaisia),
greetsit3.prg (kulkeva aalto $1b00-code3_end) ja syms.inc (greetsit_init, greetsit_go, greetsit_kopio).
levy.json:n names_from lukee nimet glue-tiedoston S_LOAD-riveistä.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools/disk"))
from kopio import kopio  # noqa: E402

ENTRIES = ["greetsit_init", "greetsit_go"]

d = Path(sys.argv[1])
lab = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "greetsit.labels").read_text(), re.M)}
b = (d / "greetsit.prg").read_bytes()
a0 = b[0] | b[1] << 8
# $4800-code_end: VIC-pankin 1 osa $4800-$7fff ladataan muualle ja kopioidaan paikalleen greetsitin alussa (koko
# demossa sokeripalan "JATKUU..."-taulu käyttää $4000-$7fff loppuun asti, joten paikalleen ladattuna osa latautuisi
# vasta sen jälkeen, ja sauma sokeripala -> greetsit olisi 90 kehystä mustaa): GREETSIT6 = $4800-$64ff
# osoitteeseen $2300-$3fff, GREETSIT7 = $6500-$7fff osoitteeseen $e000-$faff ja sen perään kopiorutiini
# greetsit_kopio ($fb00, tools/disk/kopio.py); sokeripala ilmoittaa ne vapaiksi taulunsa aikana
# (part-sokeripala.json vapaana_lopussa). GREETSIT5 = $8000-code_end ja GREETSIT3 = code3-code3_end suoraan paikalleen.
KOPIO = [(0x2300, 0x4800, 29), (0xE000, 0x6500, 27)]   # (lähde, kohde, sivuja): yhteensä $4800-$7fff
K_AT = 0xFB00
G_LO, G_HI = 0x4800, 0x8000
assert sum(n for *_, n in KOPIO) * 256 == G_HI - G_LO
cuts = {3: (lab["code3"], lab["code3_end"]), 5: (G_HI, lab["code_end"])}
assert a0 == lab["code3"] and G_HI < lab["code_end"] <= 0xC000, (hex(a0), hex(lab["code_end"]))
for i, (lo, hi) in cuts.items():
    (d / f"greetsit{i}.prg").write_bytes(bytes([lo & 255, lo >> 8]) + b[2 + lo - a0:2 + hi - a0])
for i, (src, dst, n) in zip((6, 7), KOPIO):
    data = b[2 + dst - a0:2 + dst + n * 256 - a0]
    tail = kopio(K_AT, [(s_, d_, n_ * 256) for s_, d_, n_ in KOPIO]) if i == 7 else b""
    assert i != 7 or src + n * 256 <= K_AT
    pad = bytes(K_AT - src - n * 256) if tail else b""
    (d / f"greetsit{i}.prg").write_bytes(bytes([src & 255, src >> 8]) + data + pad + tail)
lab["greetsit_kopio"] = K_AT
ENTRIES.append("greetsit_kopio")
(d / "syms.inc").write_text("".join(f"{n} = ${lab[n]:04x}\n" for n in ENTRIES))
