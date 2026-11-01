"""Spritet: biisin SID-rekisterivirta ja soittimen lopputila kohtauksen kehyksille (staattinen data kernelille).

  python3 -I src/proto/spritet/sidvirta.py OUTDIR [MUUNNOS | P0 N] [--biisi T]   -> OUTDIR/sid.bin (N x 25 t), tila.bin, music.inc
  python3 -I src/proto/spritet/sidvirta.py --tilasto OUTDIR  (muuttuvat rekisterit, muutoksia kehyksessä)

Oletuksena kohtauksen kehykset (build.py scene(): src/scene/spritet-lentavat_glue.asm SCENE_START S ja SCENE_END E,
TIM_SONG_START): P0 = TIM_SONG_START + S - 1, N = E - S + 1, eli tietue kehykselle d on biisin kehyksen
TIM_SONG_START + d - 1 arvot (rungon frame_hook soittaa kehyksen ja kasvattaa sitten DFRAMEa), ja tila on
TIM_SONG_START + E soiton jälkeen: runko jatkaa soittamalla kehyksen E.

Soitin ajetaan vain VICE:ssä (tools/music/music.py): sidvirta.asm soittaa P0 kehystä hiljaa ja tallentaa seuraavien
N kehyksen SID-arvot (I/O:n alla oleva RAM $d400-$d418 jokaisen play-kutsun jälkeen, kuten music_seek) sekä
soittimen tilan P0 + N kehyksen kohdalla (binääri, purkupuskuri, nollasivu). Soitin on osalevyn osoitteessa
(tools/music/music.py build --addr 0800 --zp c0 --buf 1700), joten tila kopioidaan demossa sellaisenaan.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
NREG = 25
TAB = 0x1A00


def symbols(inc: Path) -> dict[str, int]:
    out = {}
    for line in inc.read_text().splitlines():
        parts = line.split(";")[0].split("=")
        if len(parts) == 2:
            v = parts[1].strip()
            out[parts[0].strip()] = int(v[1:], 16) if v.startswith("$") else int(v)
    return out


def regions(sym: dict[str, int]) -> list[tuple[int, int]]:
    """Soittimen tila: binääri, purkupuskuri ja nollasivu (alku, loppu)."""
    zp = sym["MUSIC_ZP"]
    return [(sym["MUSIC_LOAD"], sym["MUSIC_END"]), (sym["MUSIC_BUF"], sym["MUSIC_BUF_END"]), (zp, zp + 16)]


def dump(out: Path, p0: int, n: int, alku: bool = True) -> None:
    """sid.bin, tila.bin (P0 + N soiton jälkeen) ja alku: tila0.bin (P0 + 1 soiton jälkeen, kohtauksen alun tila;
    spr_exit palauttaa vain erot, koska soitin ei käy kohtauksen aikana)."""
    out.mkdir(parents=True, exist_ok=True)
    if alku:
        dump(out / "alku", p0, 1, False)
        (out / "alku/tila.bin").replace(out / "tila0.bin")
    subprocess.run(["python3", "-I", str(ROOT / "tools/music/music.py"), "build", str(out), "--addr", "0800",
                    "--zp", "c0", "--buf", "1700"], check=True, stdout=subprocess.DEVNULL)
    prg, lbl = out / "sidvirta.prg", out / "sidvirta.labels"
    subprocess.run(["64tass", "-C", "-a", "-B", "-q", "-I", str(out), "-D", f"P0={p0}", "-D", f"N={n}",
                    str(HERE / "sidvirta.asm"), "-o", str(prg), "--vice-labels", "-l", str(lbl)], check=True)
    labels = {w[2]: int(w[1], 16) for w in (x.split() for x in lbl.read_text().splitlines())}
    sym = symbols(out / "music.inc")
    files = [(out / "sid.raw", TAB, TAB + NREG * n)] + [(out / f"tila{i}.raw", a, b)
                                                         for i, (a, b) in enumerate(regions(sym))]
    mon = out / "sidvirta.mon"
    mon.write_text("".join(f'bsave "{f}" 0 {a:04x} {b - 1:04x}\n' for f, a, b in files) + "quit\n")
    for f, _, _ in files:
        f.unlink(missing_ok=True)
    subprocess.run(["x64sc", "-default", "+sound", "-warp", "-console", "-nativemonitor",
                    "-autostartprgmode", "1", "-limitcycles", "400000000", "-initbreak", f"0x{labels['.halt']:04x}",
                    "-moncommands", str(mon), "-autostart", str(prg)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    raws = [f.read_bytes() for f, _, _ in files]
    for (f, a, b), r in zip(files, raws):
        if len(r) != b - a:
            raise SystemExit(f"sidvirta: {f.name} {len(r)} t, odotettiin {b - a} (VICE-ajo epäonnistui)")
    (out / "sid.bin").write_bytes(raws[0])
    (out / "tila.bin").write_bytes(b"".join(raws[1:]))
    for f, _, _ in files:
        f.unlink()


if __name__ == "__main__":
    if len(sys.argv) > 3 and "--biisi" not in sys.argv:
        dump(Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]))
    else:                                       # OUTDIR [MUUNNOS] [--biisi T]: kohtauksen kehykset glue-tiedostosta;
        sys.path.insert(0, str(HERE))           # --biisi: kohtauksen alku biisin kehyksessä T (integraatio,
        from build import scene                 # tools/disk/kokoa.py), oletus TIM_SONG_START + S kuten osalevyllä
        args = sys.argv[2:]
        song_at = int(args[args.index("--biisi") + 1]) if "--biisi" in args else None
        args = [x for i, x in enumerate(args) if x != "--biisi" and (i == 0 or args[i - 1] != "--biisi")]
        s, e, song = scene(args[0] if args else "")
        dump(Path(sys.argv[1]), (song + s if song_at is None else song_at) - 1, e - s + 1)
