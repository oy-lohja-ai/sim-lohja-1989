"""Krillin lataaja v194 lähteestä ca65/ld65:llä. Ladattua lähdettä ei ajeta: zip puretaan
Pythonilla väliaikaiseen hakemistoon, ja ca65/ld65 kutsutaan suoraan samoilla argumenteilla kuin lähteen Makefile
(`make PLATFORM=c64 prg INSTALL=... RESIDENT=... ZP=e0`). Linkkitiedosto ja symbolitiedosto (krill.inc) tehdään
tässä samassa muodossa kuin lähteen make-linkfile.pl ja make-loadersymbolsinc.pl.

  python3 -I tools/krill/koosta.py tarkista          # oletuskonfiguraatio: tavulleen sama kuin zipin valmiit binäärit
  python3 -I tools/krill/koosta.py OUTDIR [--resident 01fc] [--vahtikoira-pois] [--1541u-varoitus-pois]

Käytössä (tools/krill/): --vahtikoira-pois (DISABLE_WATCHDOG = 1, include/loader.inc), --1541u-varoitus-pois
(install.s: 1541U:lla ei punaista "Buggy 1541U firmware" -ruutua, vain asennusosa muuttuu) ja --resident 01fc:
resident kasvaa 4 tavua, joten se alkaa pinosivun lopusta ja päättyy samaan kohtaan kuin zipin valmis binääri ($0406).
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ZIP = ROOT / "third_party/downloads/loader-v194.zip"   # tools/fetch-third-party.sh (csdb.dk, release 226124)
ZIP_SHA = "c273980bb81eb5b16e6163869cec147fc76e27bdba6d03e8a3438b8251aa00f1"
INSTALL, ZP = 0x1000, 0xE0

LINK = """MEMORY
{{
 ZPRAM: start = ${zp:x}, size = ${zps:x};
 ZPRAM2: start = ${zp:x}, size = ${zps:x};
 INSTALLRAM: start = ${ins:x}, size = ${inss:x}, file = "{out}/install-c64.prg";
 RESIDENTRAM: start = ${res:x}, size = ${ress:x}, file = "{out}/loader-c64.prg";
 TRANSIENTRAM: start = $c000, size = $1000, file = "{out}/transient-c64.prg";
}}

SEGMENTS
{{
 DISKIO_ZP: load = ZPRAM, type = zp;
 DISKIO_PLUGIN_ZP: load = ZPRAM2, type = zp, optional = yes;
 DISKIO: load = RESIDENTRAM;
 DISKIO_PLUGIN: load = TRANSIENTRAM, optional = yes;
 DISKIO_INSTALL: load = INSTALLRAM;
}}
"""


# Tarkat tekstipaikkaukset puretun lähteen kopioon: (tiedosto, vanha, uusi). Kaatuu, jos vanha ei löydy täsmälleen kerran.
PATCHES = {
    "vahtikoira-pois": ("loader/include/loader.inc", "\nDISABLE_WATCHDOG = 0 ", "\nDISABLE_WATCHDOG = 1 "),
    # Ultimate/1541U: install tulostaa punaiselle ruudulle "WARNING: Buggy 1541U firmware detected" (message-rutiini).
    # Vain tulostus pois: 1541U-haara jatkuu suoraan plp:hen kuten muut asemat, drivetype-tunnistus ennallaan.
    "1541u-varoitus-pois": ("loader/src/install.s",
                            "            bne :+\n            ldx #warnemubug - messages\n            jsr message\n\n:           plp",
                            "            bne :+\n\n:           plp"),
}


def patch(tmp: Path, name: str, log: list[str]) -> None:
    rel, old, new = PATCHES[name]
    f = tmp / rel
    text = f.read_text(encoding="latin-1")
    if text.count(old) != 1:
        raise SystemExit(f"krill: paikkauksen {name} tekstiä ei löytynyt täsmälleen kerran tiedostosta {rel}")
    f.write_text(text.replace(old, new), encoding="latin-1")
    log.append(f"{rel}: paikkaus {name}")


def run(cmd: list[str], cwd: Path, log: list[str]) -> None:
    log.append(" ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def build(out: Path, resident: int, patches: list[str]) -> list[str]:
    """Kokoaa install-c64.prg, loader-c64.prg ja loader-c64.map hakemistoon out. Palauttaa ajetut komennot."""
    data = ZIP.read_bytes()
    if hashlib.sha256(data).hexdigest() != ZIP_SHA:
        raise SystemExit(f"krill: {ZIP} sha256 ei täsmää")
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    with tempfile.TemporaryDirectory(prefix="krill-") as tmpd:
        tmp = Path(tmpd)
        with zipfile.ZipFile(ZIP) as z:
            z.extractall(tmp)
        src = tmp / "loader/src"
        for name in patches:
            patch(tmp, name, log)
        inc = [".", "../../shared", "../include"]
        flags = ["--cpu", "6502X", "-g", "-t", "c64", "-D", "PLATFORM=64"] + [a for i in inc for a in ("-I", i)]
        (tmp / "binary.link").write_text(LINK.format(zp=ZP, zps=0x100 - ZP, ins=INSTALL - 2, inss=0x10002 - INSTALL,
                                                     res=resident - 2, ress=0x10002 - resident, out=out))
        run(["ca65", *flags, "-D", f"RESIADDR=0x{resident:04x}", "-o", str(tmp / "loader.o"), "resident.s"], src, log)
        run(["ca65", *flags, "-D", f"INSTADDR=0x{INSTALL:04x}", "-o", str(tmp / "install.o"), "install.s"], src, log)
        run(["ld65", "-C", str(tmp / "binary.link"), "-vm", "-m", str(out / "loader-c64.map"), "--dbgfile",
             str(out / "loader-c64.dbg"), str(tmp / "loader.o"), str(tmp / "install.o")], src, log)
    (out / "transient-c64.prg").unlink(missing_ok=True)
    return log


def symbols(mapfile: Path, resident: int) -> str:
    """krill.inc kuten make-loadersymbolsinc.pl (prg-kohde), tyhjät rivit pois."""
    seg, sym, cur = {}, {}, ""
    for line in mapfile.read_text().splitlines():
        if re.search(r"list.*?:", line):
            cur = line
        elif "Segment" in cur:
            m = re.match(r"(DISKIO\w*)\s+(\w+)\s+(\w+)", line)
            if m:
                seg[m.group(1).lower() + "_start"] = int(m.group(2), 16)
                seg[m.group(1).lower() + "_end"] = int(m.group(3), 16)
        elif "Exports" in cur:
            m = re.match(r"(\w+)\s+(\w+)\s+\w+\s+(\w+)\s+(\w+)", line)
            if m:
                sym[m.group(1)] = int(m.group(2), 16)
                sym[m.group(3)] = int(m.group(4), 16)
            else:
                m = re.match(r"(\w+)\s+(\w+)\s+\w+", line)
                if m:
                    sym[m.group(1)] = int(m.group(2), 16)
    host, decomp = {}, ""
    inside = lambda a, k: seg.get(k + "_start", -1) <= a <= seg.get(k + "_end", -2)
    for name, a in sym.items():
        if a and not re.search(r"fix|fix1|[A-Z]|1$", name):
            if any(inside(a, k) for k in ("diskio", "diskio_plugin", "diskio_install", "diskio_zp", "diskio_plugin_zp")):
                host[name] = a
        elif "config_" in name or "status_" in name:
            host[name] = a
        elif m := re.match(r"DECOMPRESSOR_(\S+)", name):
            decomp = m.group(1)
    hexs = lambda n, a: f"{n:<31} = ${a:02x}" if a < 256 else f"{n:<31} = ${a:04x}"
    by_addr = sorted(host, key=lambda n: host[n])
    out = [f"; repository version 194, koottu tools/krill/koosta.py:llä (ca65/ld65 suoraan) for project \"loader\" using",
           f"; make PLATFORM=c64 prg INSTALL={INSTALL:04x} RESIDENT={resident:04x} ZP={ZP:02x} PROJECT=", "; configuration"]
    for n in sorted(h for h in host if "config_" in h):
        out.append(f"{n:<31} = {host[n]}" + (f"; {decomp}" if n == "config_DECOMPRESSOR" else ""))
    out.append("; status codes")
    out += [hexs(n, host[n]) for n in by_addr if "status_" in n]
    left = {n: host[n] for n in by_addr if not re.search(r"config_|status_|loader_zp_first", n)}

    def take(lo: int, hi: int) -> list[str]:
        rows = [hexs(n, a) for n, a in left.items() if a and lo <= a <= hi]
        for n, a in list(left.items()):
            if a and lo <= a <= hi:
                left[n] = 0
        return rows
    out.append(f"; zeropage ${seg['diskio_zp_start']:02x}-${seg['diskio_zp_end'] + 1:02x}")
    out.append(hexs("loader_zp_first", host["loader_zp_first"]))
    out += take(seg["diskio_zp_start"], seg["diskio_zp_end"])
    out.append(f"; install ${seg['diskio_install_start'] + 2:04x}-${seg['diskio_install_end'] + 1:04x}")
    out += take(seg["diskio_install_start"] + 2, seg["diskio_install_start"] + 2)
    out.append(f"; resident ${seg['diskio_start'] + 2:04x}-${seg['diskio_end'] + 1:04x}")
    out += take(seg["diskio_start"] + 2, seg["diskio_end"])
    return "\n".join(out) + "\n"


def main() -> None:
    if sys.argv[1] == "tarkista":
        with tempfile.TemporaryDirectory(prefix="krill-out-") as d:
            build(Path(d), 0x0200, [])
            (Path(d) / "loader-c64.dbg").unlink()
            with zipfile.ZipFile(ZIP) as z:
                for f in ("install-c64.prg", "loader-c64.prg"):
                    same = (Path(d) / f).read_bytes() == z.read(f"loader/build/{f}")
                    print(f"{f}: {'tavulleen sama kuin zipin valmis binääri' if same else 'ERI'}")
                inc = symbols(Path(d) / "loader-c64.map", 0x0200).splitlines()[2:]
                ref = [l for l in z.read("loader/build/loadersymbols-c64.inc").decode().splitlines()[2:] if l.strip()]
                print(f"krill.inc: {'sama' if inc == ref else 'ERI'} (otsikkorivejä lukuun ottamatta)")
        return
    out = Path(sys.argv[1])
    res = int(sys.argv[sys.argv.index("--resident") + 1], 16) if "--resident" in sys.argv else 0x0200
    log = build(out, res, [n for n in PATCHES if f"--{n}" in sys.argv])
    dbg = (out / "loader-c64.dbg").read_text()
    internal = [f"{n:<31} = ${int(re.search(rf'name=\"{n}\",[^\n]*val=0x([0-9A-F]+)', dbg).group(1), 16):04x}"
                for n in ("decompress",)]
    (out / "krill.inc").write_text(symbols(out / "loader-c64.map", res) + "; sisäiset\n" +
                                   "\n".join(internal) + "\n")
    (out / "loader-c64.map").unlink()
    (out / "loader-c64.dbg").unlink()
    print("\n".join(log))
    for f in ("install-c64.prg", "loader-c64.prg", "krill.inc"):
        print(f"{f} sha256 {hashlib.sha256((out / f).read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
