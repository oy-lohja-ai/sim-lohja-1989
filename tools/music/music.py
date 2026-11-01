"""Demon musiikki: Blackbird-laulu (bb.*, Patemathic) soittimeksi demon osille.

Biisi nimetään vain tiedostossa tools/music/song.json, laulut ovat hakemistossa music/. Laulu on Blackbird 1.2
-trackerin tiedosto (lft). Soitin tehdään Birdcruncherilla (Blackbird 1.2:n Export-työkalu, ei tässä repossa:
tools/fetch-third-party.sh hakee ja kääntää sen hakemistoon third_party/blackbird/). `crunch` ajaa Birdcruncherin
kerran per biisi ja tekee soittimesta relokaatiodatan, jonka jälkeen `build` siirtää soittimen mihin tahansa
Pythonilla.

  crunch                 (Birdcruncher) third_party/blackbird/player/LAULU/: soitin + relokaatio, .sid molemmille
                         malleille, Python-siirron tarkistus Birdcruncheria vastaan
  build OUT --addr 4f00 [--zp e0] [--buf HEX]
                         OUT/music.bin (latausosoite MUSIC_LOAD) ja OUT/music.inc (64tass-symbolit).
                         --buf: 3 sivun purkupuskuri erilleen (oletus heti soittimen perässä)
  --laulu AVAIN KOMENTO   muu laulu song.json:n "laulut"-avaimesta (act0: MS-DOS-intro); build tekee silloin
                         OUT/AVAIN.bin ja OUT/AVAIN.inc, symbolit AVAIN_* (ACT0_PLAY, ...)
  mut                    soittimen muuttuvat tavut (src/music/mut.asm, VICE x64sc) music/LAULU.mut.json:iin
                         (levynvaihdon tahtisilmukka, src/runko/levynvaihto.asm)

Ajo: python3 -I tools/music/music.py KOMENTO.
"""
import argparse
import hashlib
import json
import pathlib
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
BLACKBIRD = ROOT / "third_party/blackbird"      # tools/fetch-third-party.sh: Blackbird 1.2 ja Birdcruncher
# Laulu: oletus demon biisi, --laulu AVAIN song.json:n "laulut"-avaimesta (act0: DOS-intro, src/runko/dos.asm)
LAULU = None
PREFIX = "MUSIC_"                       # music.inc:n symbolien etuliite (--laulu act0: ACT0_)


def song_cfg() -> dict:
    s = json.loads((HERE / "song.json").read_text())
    return s if LAULU is None else s["laulut"][LAULU]


def song_stem() -> str:
    return pathlib.PurePath(song_cfg()["song"]).name.removesuffix(".prg")


def player_dir() -> pathlib.Path:
    """Soitin per laulu (Birdcruncherin tulos, ei repossa)."""
    return BLACKBIRD / "player" / song_stem()


def mut_file() -> pathlib.Path:
    """Soittimen muuttuvat tavut (music.py mut): music/LAULU.mut.json."""
    return ROOT / "music" / f"{song_stem()}.mut.json"


PLAYER = player_dir()
CRUNCHER = BLACKBIRD / "birdcruncher"
PAL_FPS = 985248 / (63 * 312)

sys.path.insert(0, str(HERE))
import bbsong  # noqa: E402

# Relokaation mittausajot: (soitin, nollasivu, puskuri). Erot perusajoon kertovat, mitkä tavut ovat
# soittimen osoitteen ylätavuja, puskurin ylätavuja tai nollasivuosoitteita.
BASE = (0x1000, 0xE0, 0x4000)
PROBES = {"addr": (0x2300, 0xE0, 0x4000), "buf": (0x1000, 0xE0, 0x5700), "zp": (0x1000, 0xE4, 0x4000)}
CHECK = (0x3600, 0xC0, 0x0800)


def song() -> dict:
    s = dict(song_cfg())
    path = ROOT / s["song"]
    if not path.exists():
        raise SystemExit(f"{path} puuttuu")
    if hashlib.sha256(path.read_bytes()).hexdigest() != s["sha256"]:
        raise SystemExit(f"{path}: sha256 ei vastaa song.json:ia")
    s["path"] = path
    s["parsed"] = bbsong.parse(path.read_bytes())
    s["lines"], s["frames"] = bbsong.timing(s["parsed"])
    tempo = int(s["lines"][0]["tempo"], 16)
    s["beat"] = 2 * (2 * (tempo & 15) + (tempo >> 4 & 3))      # 4 riviä, swing joka toisella
    s["loop"] = s["parsed"]["loop"]
    if len({l["tempo"] for l in s["lines"]}) > 1:
        print("varoitus: biisissä on tempovaihdoksia, ruudukko ensimmäisen tempon mukaan", file=sys.stderr)
    return s


def birdcruncher(s: dict, addr: int, zp: int, buf: int, model: str = "8580") -> bytes:
    """Yksi Birdcruncher-ajo omassa hakemistossaan (third_party/blackbird/run). Palauttaa koko .sid:n."""
    if not CRUNCHER.exists():
        raise SystemExit(f"{CRUNCHER} puuttuu: tools/fetch-third-party.sh")
    run = BLACKBIRD / "run"
    run.mkdir(exist_ok=True)
    out = run / "out.sid"
    out.unlink(missing_ok=True)
    subprocess.run([str(CRUNCHER), "-t", "sid", "-a", f"{addr:04x}", "-z", f"{zp:02x}", "-u", f"{buf:04x}",
                    "-O" if model == "6581" else "-N", "-o", str(out), str(s["path"])],
                   check=True, stderr=subprocess.DEVNULL, cwd=run, env={})
    return out.read_bytes()


def sid_body(raw: bytes, addr: int) -> bytes:
    off = struct.unpack(">H", raw[6:8])[0]
    assert struct.unpack("<H", raw[off:off + 2])[0] == addr
    return raw[off + 2:]


def relocate(rel: dict, base: bytes, addr: int, zp: int, buf: int) -> bytes:
    if addr & 0xFF or buf & 0xFF:
        raise SystemExit("soitin ja puskuri sivun rajalle")
    out = bytearray(base)
    for key, delta in (("addr", (addr - BASE[0]) >> 8), ("buf", (buf - BASE[2]) >> 8), ("zp", zp - BASE[1])):
        for i in rel[key]:
            v = out[i] + delta
            if not 0 <= v <= 0xFF:
                raise SystemExit(f"osoite ei mahdu ({key}, tavu {i})")
            out[i] = v
    return bytes(out)


def crunch() -> None:
    s = song()
    PLAYER.mkdir(parents=True, exist_ok=True)
    raw = birdcruncher(s, *BASE)
    header, base = raw[:struct.unpack(">H", raw[6:8])[0]], sid_body(raw, BASE[0])
    rel = {}
    for key, cfg in PROBES.items():
        other = sid_body(birdcruncher(s, *cfg), cfg[0])
        assert len(other) == len(base)
        delta = ((cfg[0] - BASE[0]) >> 8, cfg[1] - BASE[1], (cfg[2] - BASE[2]) >> 8)[("addr", "zp", "buf").index(key)]
        diff = [i for i in range(len(base)) if base[i] != other[i]]
        bad = [i for i in diff if (other[i] - base[i]) & 0xFF != delta]
        if bad:
            raise SystemExit(f"relokaatio {key}: odottamaton ero tavuissa {bad[:8]}")
        rel[key] = diff
    if set(rel["addr"]) & set(rel["buf"]) or set(rel["addr"]) & set(rel["zp"]) or set(rel["buf"]) & set(rel["zp"]):
        raise SystemExit("relokaatioluokat menevät päällekkäin")
    want = sid_body(birdcruncher(s, *CHECK), CHECK[0])
    if relocate(rel, base, *CHECK) != want:
        raise SystemExit("Python-siirto ei vastaa Birdcruncheria")
    (PLAYER / "base.bin").write_bytes(base)
    meta = {"song": s["song"], "sha256": s["sha256"], "base": BASE, **rel}
    (PLAYER / "player.json").write_text(json.dumps(meta))
    (PLAYER / "header.bin").write_bytes(header)
    write_sids(meta, header, base)
    print(f"{PLAYER}: soitin {len(base)} t, relokoitavia tavuja: soitin {len(rel['addr'])}, "
          f"puskuri {len(rel['buf'])}, nollasivu {len(rel['zp'])}; Python-siirto = Birdcruncher (tarkistettu)")


def write_sids(rel: dict, header: bytes, base: bytes) -> None:
    """Kuunteluun ja kaappaukseen .sid molemmille malleille Pythonilla (soitin $1000, puskuri perässä
    nollina mukana, jotta vsid ei sijoita ajuriaan sinne). Mallin ainoa ero on PSID-lippujen bitit 4-5."""
    buf = 0x1000 + (len(base) + 0xFF & ~0xFF)
    body = relocate(rel, base, 0x1000, 0xE0, buf)
    body += bytes(buf + 0x300 - 0x1000 - len(body))
    for model, bits in (("6581", 0x10), ("8580", 0x20)):
        h = bytearray(header)
        h[0x77] = h[0x77] & 0xCF | bits
        h[0x78:0x7A] = b"\0\0"                   # vapaat sivut: perusajossa puskurin takia, vsid laskee itse
        (PLAYER / f"biisi-{model}.sid").write_bytes(bytes(h) + struct.pack("<H", 0x1000) + body)


def player(s: dict) -> tuple[dict, bytes]:
    meta = json.loads((PLAYER / "player.json").read_text()) if (PLAYER / "player.json").exists() else {}
    if meta.get("sha256") != s["sha256"]:
        raise SystemExit("soitinta ei ole tehty tälle biisille: tools/fetch-third-party.sh (music.py crunch)")
    return meta, (PLAYER / "base.bin").read_bytes()


def mut_symbols(s: dict, addr: int) -> list[str]:
    """Muuttuvat tavut (music.py mut) levynvaihdon tahtisilmukalle: 256 tavun ikkuna + enintään yksi erillinen tavu."""
    f = mut_file()
    m = json.loads(f.read_text()) if f.exists() else {}
    if m.get("sha256") != s["sha256"]:
        return []
    offs = m["mut"]
    win = min(offs, key=lambda w: sum(not w <= o < w + 256 for o in offs))
    rest = [o for o in offs if not win <= o < win + 256]
    if len(rest) > 1:
        raise SystemExit(f"muuttuvat tavut eivät mahdu ikkunaan + yhteen tavuun: {rest}")
    one = rest[0] if rest else win
    return [f"MUSIC_MUT_WIN = ${addr + win:04x}       ; muuttuvat tavut (music.py mut, {len(offs)} t): 256 t tästä",
            f"MUSIC_MUT_BYTE = ${addr + one:04x}      ; ja tämä tavu (src/runko/levynvaihto.asm tallentaa ne)"]


def build(out: pathlib.Path, addr: int, zp: int, buf: int | None) -> None:
    s = song()
    meta, base = player(s)
    if buf is None:
        buf = addr + (len(base) + 0xFF & ~0xFF)
    body = relocate(meta, base, addr, zp, buf)
    end = addr + len(body)
    if buf < end and buf + 0x300 > addr:
        raise SystemExit("puskuri menee soittimen päälle")
    out.mkdir(parents=True, exist_ok=True)
    stem = LAULU or "music"                     # --laulu act0: OUT/act0.bin ja OUT/act0.inc
    (out / f"{stem}.bin").write_bytes(body)
    beat, loop = s["beat"], s["frames"]
    loop_to = loop if s["loop"] is None else s["lines"][s["loop"]]["start"]
    d418 = [i for i in range(len(body) - 2) if body[i:i + 3] == bytes([0x8D, 0x18, 0xD4])]
    inc = [
        f"; Generoitu: tools/music/music.py build ({s['title']} / {s['author']}, {pathlib.Path(s['song']).name})",
        "; Blackbird 1.2 -soitin (lft). Kutsu: jsr MUSIC_INIT (A = 0), jsr MUSIC_PLAY kerran kehyksessä.",
        "HAVE_MUSIC = 1",
        f"MUSIC_LOAD = ${addr:04x}          ; soitin + data (music.bin)",
        f"MUSIC_END = ${end:04x}           ; music.bin päättyy (ei mukana)",
        f"MUSIC_INIT = ${addr:04x}",
        f"MUSIC_PLAY = ${addr + 3:04x}",
        f"MUSIC_BUF = ${buf:04x}           ; purkupuskuri 3 sivua, ajonaikainen (ei ladata)",
        f"MUSIC_BUF_END = ${buf + 0x300:04x}",
        f"MUSIC_ZP = ${zp:02x}             ; nollasivu 16 tavua MUSIC_ZP..MUSIC_ZP+15",
        f"MUSIC_SYNC = ${zp + 13:02x}           ; syncpoint-tavu (ei käytössä ilman syncpointeja)",
        f"MUSIC_LOOP_FRAMES = {loop}     ; biisin pituus kehyksinä ({loop / PAL_FPS:.2f} s)"
        + (", sitten luuppi" if s["loop"] is not None else ", sitten hiljaa"),
        f"MUSIC_LOOP_TO = {loop_to}     ; luuppi: kehys MUSIC_LOOP_FRAMES + n soi kuin kehys MUSIC_LOOP_TO + n"
        + (" (= MUSIC_LOOP_FRAMES: ei luuppia)" if s["loop"] is None else ""),
        f"MUSIC_BEAT_FRAMES = {beat}      ; isku ({60 * PAL_FPS / beat:.2f} BPM), tahti 4 iskua",
        f"MUSIC_LINE_FRAMES = {s['lines'][0]['frames']}     ; ensimmäinen laulurivi",
    ] + ([f"MUSIC_D418_OP = ${addr + d418[0] + 1:04x}       ; soittimen ainoan STA $D418:n operandi (häivytys, src/runko/haivytys.asm)"]
         if len(d418) == 1 else []) + mut_symbols(s, addr)
    text = "\n".join(inc) + "\n"
    if PREFIX != "MUSIC_":
        text = text.replace("MUSIC_", PREFIX).replace("HAVE_MUSIC", "HAVE_" + PREFIX[:-1])
    (out / f"{stem}.inc").write_text(text)
    print(f"{out}/{stem}.bin ${addr:04x}-${end - 1:04x} ({len(body)} t), puskuri ${buf:04x}-${buf + 0x2ff:04x}, "
          f"nollasivu ${zp:02x}-${zp + 15:02x}, biisi {loop} kehystä, isku {beat}")


TEST = ROOT / "build/music-test"


def assemble(name: str, *defs: str) -> tuple[pathlib.Path, dict]:
    build(TEST, *BASE[:2], None)
    prg, lbl = TEST / f"{name}.prg", TEST / f"{name}.labels"
    subprocess.run(["64tass", "-C", "-a", "-B", "-q", "-I", str(TEST), "-I", str(ROOT / "src/music"),
                    *[x for d in defs for x in ("-D", d)], str(ROOT / f"src/music/{name}.asm"),
                    "-o", str(prg), "--vice-labels", "-l", str(lbl)], check=True)
    return prg, dict(line.split()[2:0:-1] for line in lbl.read_text().splitlines())


def run_vice(name: str, start: str, end: str, limit: int = 200_000_000) -> bytes:
    """Ajaa src/music/NAME.asm:n x64sc:ssä JAM-käskyyn `halt` asti ja palauttaa muistin START..END."""
    prg, labels = assemble(name)
    mon, res = TEST / f"{name}.mon", TEST / f"{name}.bin"
    a, b = int(labels[start], 16), int(labels[end], 16)
    mon.write_text(f'bsave "{res}" 0 {a:04x} {b - 1:04x}\nquit\n')
    res.unlink(missing_ok=True)
    subprocess.run(["x64sc", "-default", "+sound", "-warp", "-console", "-nativemonitor",
                    "-autostartprgmode", "1", "-limitcycles", str(limit), "-initbreak", f"0x{labels['.halt']}",
                    "-moncommands", str(mon), "-autostart", str(prg)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return res.read_bytes()


def mut() -> None:
    """Soittimen muuttuvat tavut (src/music/mut.asm): offsetit MUSIC_LOADista tiedostoon music/LAULU.mut.json.
    Levynvaihdon tahtisilmukka tallentaa ne (music.inc MUSIC_MUT_*, src/runko/levynvaihto.asm)."""
    s = song()
    frames = 2 * s["frames"] - (s["frames"] if s["loop"] is None else s["lines"][s["loop"]]["start"]) + 60
    mask = run_vice("mut", ".mask", ".mask_end", 60_000 * frames)
    offs = [i for i, v in enumerate(mask) if v]
    mut_file().write_text(json.dumps({"sha256": s["sha256"], "frames": frames, "mut": offs}))
    runs, a = [], None
    for i, o in enumerate(offs):
        if a is None:
            a = o
        if i + 1 == len(offs) or offs[i + 1] != o + 1:
            runs.append((a, o))
            a = None
    print(f"{mut_file()}: {len(offs)} muuttuvaa tavua {frames} kehyksessä: "
          + " ".join(f"+${a:03x}" + (f"..+${b:03x}" if b > a else "") for a, b in runs))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--laulu", default=None, help="song.json:n laulut-avain (oletus demon biisi)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("crunch")
    b = sub.add_parser("build")
    b.add_argument("out", type=pathlib.Path)
    b.add_argument("--addr", type=lambda v: int(v, 16), default=0x1000)
    b.add_argument("--zp", type=lambda v: int(v, 16), default=0xE0)
    b.add_argument("--buf", type=lambda v: int(v, 16), default=None)
    sub.add_parser("mut")
    a = ap.parse_args()
    if a.laulu:
        global LAULU, PLAYER, PREFIX
        LAULU, PREFIX = a.laulu, a.laulu.upper() + "_"
        PLAYER = player_dir()
    if a.cmd == "build":
        build(a.out, a.addr, a.zp, a.buf)
    else:
        {"crunch": crunch, "mut": mut}[a.cmd]()


if __name__ == "__main__":
    main()
