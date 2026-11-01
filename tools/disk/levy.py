"""Demon levy: tiedostonimet linkkiskriptille, pakkaus ja D64.

  python3 -I tools/disk/levy.py names [SPEC]   # files.inc: nimet, pakkauslippu ja osien symbolit linkkiskriptille
  python3 -I tools/disk/levy.py disk [SPEC [D64]] # D64, .labels (yhdistetyt VICE-labelit), .txt (sijainnit, koot)
  python3 -I tools/disk/levy.py list [D64]     # hakemisto ja tiedostojen sijainnit
  python3 -I tools/disk/levy.py prep SPEC NIMI # yleisen osalevyn kohtauksen palat (make-avain tai src/proto/NIMI)

Kuvaus: src/runko/levy.json (oletus). Avaimet: name, id (levyn nimi ja tunnus), out (D64), inc (files.inc),
labels (yhdistettävät VICE-labelit), dir. Hakemiston järjestys = levyn järjestys = latausjärjestys. Merkkijono
on dirartin rivi (DEL, raita 0), olio on tiedosto: name (levyllä, PETSCII), label (linkkiskriptin lohko),
src (PRG) tai bin + at (raaka binääri ja osoite heksana), pack (ZX0, Krillin loadcompd), seq (UTF-8-teksti ->
PETSCII SEQ), b (puoli B: name, id, dir; levy OUT-b.d64), piilota (true: hakemiston PRG-tiedostot tyyppitavulla 0, eli
LOAD"$" näyttää vain bootin, SEQ-tiedostot ja dirartin; Krill lataa ne silti, d64.py), labels + syms (+ prefix) (osan
sisääntulot linkkiskriptille), consts {file, names} (vakiot osan includesta), boot (nimi payloadissa, ei residentissä:
vain käynnistyksen lataus), range [alku, loppu] (pala PRG:stä, heksana tai labels-tiedoston nimenä), optional
(ohitetaan, jos lähdettä ei ole), raw (osa lataa itse loadraw:lla, esim. PUOLI B), loppuun (lohkot muiden jälkeen,
hakemistossa paikallaan: muiden paikat levyllä eivät muutu).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import d64  # noqa: E402
import zx0  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "src/runko/levy.json"


def spec(path: Path) -> dict:
    """Kuvaus; {"names_from": ASM, "prg_dir": DIR, ...} laajenee kohtaustiedoston tiedostoiksi latausjärjestyksessä:
    kohtaustaulun #S_LOAD f_x -rivit (levyllä X, tiedosto DIR/<x>.prg, lohko f_x). "loppuun": [NIMET] näille lohkot
    muiden jälkeen. Muut avaimet jokaiselle."""
    s = json.loads(path.read_text())
    s["dir"] = expand(s["dir"])
    if "b" in s:
        s["b"]["dir"] = expand(s["b"]["dir"])
    return s


def expand(entries: list) -> list:
    out = []
    for f in entries:
        if isinstance(f, dict) and f.get("optional") and "src" in f and not (ROOT / f["src"]).exists():
            continue                   # kohtaus ei vielä buildissa
        if isinstance(f, dict) and "names_from" in f:
            if not (ROOT / f["names_from"]).exists():
                if f.get("optional"):
                    continue
                raise SystemExit(f"levy: {f['names_from']} puuttuu")
            src = (ROOT / f["names_from"]).read_text()
            extra = {k: v for k, v in f.items() if k not in ("names_from", "prg_dir", "optional", "loppuun")}
            table = list(dict.fromkeys(re.findall(r"^\s*#S_LOAD\s+f_(\w+)", src, re.M)))
            files = [{"name": n.upper(), "label": f"f_{n}", "src": f"{f['prg_dir']}/{n}.prg", **extra,
                      **({"loppuun": True} if n.upper() in f.get("loppuun", []) else {})} for n in table]
            if f.get("optional") and not all((ROOT / e["src"]).exists() for e in files):
                continue               # kohtaus ei vielä buildissa
            out += files
        else:
            out.append(f)
    return out


def labels(path: Path) -> dict[str, int]:
    out = {}
    for line in path.read_text().splitlines():
        m = re.match(r"al ([0-9a-fA-F]+) \.(\S+)$", line)
        if m:
            out[m.group(2)] = int(m.group(1), 16)
    return out


def prg(f: dict) -> bytes:
    if "bin" in f:
        at = int(f["at"], 16)
        return bytes([at & 255, at >> 8]) + (ROOT / f["bin"]).read_bytes()
    b = (ROOT / f["src"]).read_bytes()
    if "range" in f:                   # osa PRG:stä: [alku, loppu) heksana (kohtauksen lataus paloina)
        a0 = b[0] | b[1] << 8
        lab = labels(ROOT / f["labels"]) if "labels" in f else {}
        lo, hi = (lab[x] if x in lab else int(x, 16) for x in f["range"])   # heksa tai labelin nimi
        hi = min(hi, a0 + len(b) - 2)
        if not a0 <= lo < hi:
            raise SystemExit(f"levy: {f['name']}: alue {f['range']} ei ole tiedostossa ${a0:04x}-")
        return bytes([lo & 255, lo >> 8]) + b[2 + lo - a0:2 + hi - a0]
    return b


def blocks(data: bytes) -> int:
    return (len(data) + 253) // 254


def payload(f: dict) -> tuple[bytes, bool]:
    """Levylle menevä data ja pakkaus. Krill v194 (valmis binääri) tallentaa yhden lohkon tiedostosta vain osan
    (VICE, true drive): jokainen ladattava tiedosto on vähintään 2 lohkoa. Jos pakattu mahtuisi yhteen lohkoon,
    tiedosto menee raakana."""
    raw = prg(f)
    if f.get("pack"):
        z = zx0.pack(raw[2:], raw[0] | raw[1] << 8)
        if blocks(z) >= 2:
            return z, True
    if blocks(raw) < 2:
        raise SystemExit(f"levy: {f['name']}: {len(raw) - 2} t on yksi lohko, Krill ei lataa sitä oikein: yhdistä toiseen tiedostoon")
    return raw, False


def alldir(s: dict) -> list:
    """Molempien levypuolten tiedostot (linkkiskripti lataa kummaltakin samoilla nimillä)."""
    return s["dir"] + (s["b"]["dir"] if "b" in s else [])


def sym_lines(f: dict) -> list[str]:
    """Tiedoston mukana tulevat symbolit linkkiskriptille: consts {file, names} (vakiot osan includesta) ja
    syms (+ prefix) (sisääntulot osan labelseista)."""
    lines = []
    if f.get("consts"):
        text = (ROOT / f["consts"]["file"]).read_text()
        for n in f["consts"]["names"]:
            m = re.search(rf"^{n}\s*=\s*([-$%0-9a-fA-F]+)", text, re.M)
            if not m:
                raise SystemExit(f"levy: {f['consts']['file']}: ei vakiota {n}")
            lines.append(f"{n} = {m.group(1)}")
    if f.get("syms"):
        lab = labels(ROOT / f["labels"])
        for n in f["syms"]:
            if n not in lab:
                raise SystemExit(f"levy: {f['labels']}: ei symbolia {n}")
            lines.append(f"{f.get('prefix', '')}{n} = ${lab[n]:04x}")
    return lines


def names(s: dict) -> None:
    lines = [f"; Generoitu: tools/disk/levy.py names. Tiedostot (name, packed = ZX0, muistialue lo..hi-1, txt) ja osien"
             f" sisääntulot."]
    for f in alldir(s):
        if isinstance(f, dict) and f.get("label"):
            nm = d64.petscii(f["name"])
            raw = prg(f)
            lo = raw[0] | raw[1] << 8
            boot = f.get("boot")         # vain payloadin käynnistyksessä (musiikki): nimi ei vie residentin tilaa
            lines += (["        .section boot_names"] if boot else []) + [
                f"{f['label']} .block", f"packed = {1 if payload(f)[1] else 0}",
                f"lo      = ${lo:04x}", f"hi      = ${lo + len(raw) - 2:04x}", f"txt     = \"{f['name']}\"",
                f"name    .byte {', '.join(f'${b:02x}' for b in nm)}, 0   ; \"{f['name']}\"", "        .endblock"] + (
                ["        .endsection"] if boot else [])
        if isinstance(f, dict):
            lines += sym_lines(f)
    boot = next(f for f in s["dir"] if isinstance(f, dict))      # KERNAL lataa, ei Krill (eikä ole vielä olemassa)
    for f in alldir(s):                # kohtaustiedostot ladataan residentin loadilla aina pakattuina
        if isinstance(f, dict) and f is not boot and not f.get("seq") and "label" not in f \
                and not f.get("raw") and not payload(f)[1]:
            raise SystemExit(f"levy: {f['name']}: kohtauksen tiedosto ei pakkaudu yli yhden lohkon (load on aina "
                             f"pakattu): yhdistä toiseen tiedostoon")
    out = ROOT / s["inc"]
    out.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    if not out.exists() or out.read_text() != text:
        out.write_text(text)


def image(name: str, ident: str, entries: list, piilota: bool = False,
          boot: dict | None = None) -> tuple[bytes, list[str], int]:
    """piilota: PRG-tiedostot paitsi boot (KERNALin LOAD"*" ja LOAD"SIM LOHJA 1989" etsivät näkyvää) piiloon."""
    img = d64.D64(d64.petscii(name), d64.petscii(ident))
    report = []
    for f in entries:
        if isinstance(f, str):
            img.add(d64.Entry(d64.petscii(f), "del"))
            continue
        if f.get("seq"):
            data = d64.petscii((ROOT / f["seq"]).read_text())
            kind, packed = "seq", False
        else:
            raw = prg(f)
            data, packed = payload(f)
            kind = "prg"
        e = d64.Entry(d64.petscii(f["name"]), kind, data, hidden=piilota and kind == "prg" and f is not boot)
        img.add(e, loppuun=f.get("loppuun", False))
        load = data[0] | data[1] << 8
        if kind == "prg" and packed:
            info = f"${raw[0] | raw[1] << 8:04x}-${(raw[0] | raw[1] << 8) + len(raw) - 2:04x} pakattu {len(raw) - 2} -> {len(data) - 2} t (lataus ${load:04x})"
        elif kind == "prg":
            info = f"${load:04x}-${load + len(data) - 2:04x} raaka {len(data) - 2} t" + (" (pakattu olisi 1 lohko)" if f.get("pack") else "")
        else:
            info = f"teksti {len(data)} t"
        report.append((f["name"], e, info))
    data = img.finish()                 # (loppuun-tiedostojen lohkot vasta tässä)
    report = [f"{n:<16} {e.blocks:>3} lohkoa  raita {e.track:>2}/{e.sector:<2} {info}" for n, e, info in report]
    report.append(f"vapaana {img.free_blocks()} lohkoa")
    return data, report, img.free_blocks()


def disk(s: dict, out: Path | None = None) -> None:
    out = out or ROOT / s["out"]
    boot = next(f for f in s["dir"] if isinstance(f, dict))
    data, report, free = image(s["name"], s["id"], s["dir"], s.get("piilota", False), boot)
    out.write_bytes(data)
    msg = f"d64: {len([f for f in s['dir'] if isinstance(f, dict)])} tiedostoa, vapaana {free} lohkoa"
    if "b" in s:                       # puoli B: sama nimi -b-päätteellä
        b = s["b"]
        data, rep_b, free_b = image(b.get("name", s["name"]), b.get("id", s["id"]), b["dir"], s.get("piilota", False))
        out.with_name(out.stem + "-b.d64").write_bytes(data)
        report += ["", "puoli B:"] + rep_b
        msg += f", puoli B {len([f for f in b['dir'] if isinstance(f, dict)])} tiedostoa"
    lab, seen = [], set()
    for p in s["labels"]:              # sama nimi useassa osassa (clock0): myöhemmät osan nimellä etuliitettynä
        for line in (ROOT / p).read_text().splitlines():
            m = re.match(r"al ([0-9a-fA-F]+) \.(\S+)$", line)
            if m and m.group(2) in seen:
                line = f"al {m.group(1)} .{Path(p).stem}_{m.group(2)}"
            elif m:
                seen.add(m.group(2))
            lab.append(line)
    res = labels(ROOT / s["labels"][0])  # payload: residentin koko (build pysähtyy ylityksessä, payload.asm)
    if "res_limit" in res:
        msg += f", resident -${res['res_end'] - 1:04x} vapaana {res['res_limit'] - res['res_end']} t"
    out.with_suffix(".labels").write_text("\n".join(lab) + "\n")
    out.with_suffix(".txt").write_text("\n".join(report) + "\n")
    print(msg)


def prep(path: Path, name: str) -> None:
    """Yleisen osalevyn kohtauksen palat: kuvauksen "make"-avaimen argumentit (esim. ["-C", "src/proto/vuosi", "demo",
    "VUOSI=1989"]) tai src/proto/NIMI/Makefile:n demo-kohde, jos sellainen on."""
    import subprocess
    args = json.loads(path.read_text()).get("make")
    if args is None and (ROOT / f"src/proto/{name}/Makefile").exists():
        args = ["-C", f"src/proto/{name}", "demo"]
    if args:
        subprocess.run(["make", "-s", *args], cwd=ROOT, check=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    arg = Path(sys.argv[2]) if len(sys.argv) > 2 else SPEC
    if cmd == "prep":
        prep(arg, sys.argv[3])
    elif cmd == "names":
        names(spec(arg))
    elif cmd == "disk":
        disk(spec(arg), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
    else:
        raise SystemExit(f"levy.py: tuntematon komento {cmd}")
