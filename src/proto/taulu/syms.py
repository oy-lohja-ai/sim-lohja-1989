"""Kohtaustaulun sisääntulot taulu.labels:sta: syms.py KANSIO -> KANSIO/syms.inc (taulu_init, taulu_go)."""
import re
import sys
from pathlib import Path

d = Path(sys.argv[1])
lab = {m[2]: int(m[1], 16) for m in re.finditer(r"^al ([0-9a-fA-F]+) \.(\S+)$", (d / "taulu.labels").read_text(), re.M)}
(d / "syms.inc").write_text("".join(f"{n} = ${lab[n]:04x}\n" for n in ("taulu_init", "taulu_go", "taulu_show", "taulu_jalki", "taulu_sauma") if n in lab))
