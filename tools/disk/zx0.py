"""ZX0 Krillin lataajalle (v194, DECOMPRESSOR = ZX0, dali-muoto): pakkaus, purku ja tarkistus. Puhdasta Pythonia.

Muoto (Krillin lataajan v194 lähteen `loader/tools/dali/dali.c`, purkaja `src/decompress/zx0decomp.s`):
  PRG-latausosoite (pakatun datan alku, valitaan niin että pakattu data päättyy purettuun loppuun),
  purun osoite big endian (hi, lo), virta. Virta on ZX0 v2 -virta dalin uudelleenkoodauksella: bitit tavuun
  vähiten merkitsevästä alkaen, Eliaksen lomitettu gamma ilman käännettyjä bittejä, ja yli 8 databitin luvuissa
  alatavun bitit ensin. Purku tehdään paikallaan: kun purkukohta saavuttaa lukukohdan ottelun jälkeen, loput
  tavut ovat valmiiksi paikoillaan raakana (dalin `copy_inplace_literal`).

  python3 -I tools/disk/zx0.py pack IN.prg OUT.zx0        # PRG -> Krillin pakattu PRG
  python3 -I tools/disk/zx0.py unpack IN.zx0 OUT.prg      # takaisin (tarkistus)
  python3 -I tools/disk/zx0.py boot BIN DEST LABELS OUTDIR  # bootin payload.zx0 ja payload.inc (src/runko/boot.asm)
  python3 -I tools/disk/zx0.py test                       # Krillin testilevyn p1/p2 ja omat kierrokset
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

MAX_OFFSET = 32640              # ((o - 1) >> 7) + 1 <= 255, 256 on loppumerkki
MAX_LEN = 65535
ARRIVALS = 6                    # tiloja per kohta (eri toisto-offset), salvadorin "arrivals"
CHAIN = 48                      # ehdokkaita per kohta hajautusketjusta
LONG = 96                       # tätä pidempi ottelu otetaan sellaisenaan ja sen sisäkohdat ohitetaan
CACHE = Path(__file__).resolve().parents[2] / "build" / "zx0cache"


def elias_len(v: int) -> int:
    return 2 * (v.bit_length() - 1) + 1


class BitWriter:
    def __init__(self) -> None:
        self.out = bytearray()
        self.mask = 0
        self.at = 0

    def bit(self, b: int) -> None:
        if not self.mask & 255:
            self.mask = 1
            self.at = len(self.out)
            self.out.append(0)
        if b:
            self.out[self.at] |= self.mask
        self.mask <<= 1

    def byte(self, b: int) -> None:
        self.out.append(b)

    def elias(self, v: int, skip: bool = False) -> None:
        bits = v.bit_length() - 1
        i = 1 << bits
        if bits >= 8:
            v &= ~i
            v = (v >> 8) | ((v & 0xFF) << (bits - 8))
        i >>= 1
        while i:
            if not skip:
                self.bit(0)
            skip = False
            self.bit(1 if v & i else 0)
            i >>= 1
        if not skip:
            self.bit(1)


# ---------------------------------------------------------------------------------------------------- jäsennys

def _matches(data: bytes, i: int, heads: dict, prev: list) -> list[tuple[int, int]]:
    """Portaikko [(pituus, offset)]: jokaiselle pituudelle pienin offset, pituudet kasvavat."""
    n = len(data)
    out = []
    best = 1
    cand = heads.get(data[i:i + 2], -1)
    tries = CHAIN
    while cand >= 0 and tries:
        off = i - cand
        if off > MAX_OFFSET:
            break
        k = best + 1
        if i + k <= n and data[cand:cand + k] == data[i:i + k]:
            hi = min(n - i, MAX_LEN)
            lo = k
            step = 16
            while lo < hi:                     # laukkaava haku viipalevertailulla
                t = min(hi, lo + step)
                if data[cand + lo:cand + t] == data[i + lo:i + t]:
                    lo = t
                    step *= 2
                else:
                    hi = t - 1 if step == 1 else hi
                    step = max(1, step // 2)
                    if step == 1 and data[cand + lo] != data[i + lo]:
                        break
            best = lo
            out.append((best, off))
            if best >= LONG:
                break
        cand = prev[cand]
        tries -= 1
    return out


def parse(data: bytes) -> list[tuple]:
    """Lähes optimaalinen jäsennys: eteenpäin kulkeva DP, kohdassa enintään ARRIVALS tilaa (kustannus bitteinä,
    toisto-offset, literaalijonon pituus). Palauttaa merkit ('L', n) / ('R', n) / ('M', n, offset)."""
    n = len(data)
    arr: list[list] = [[] for _ in range(n + 1)]   # [kustannus, rep, litlen, edellinen kohta, edellinen tila, merkki]
    arr[0].append([0, 1, 0, -1, -1, None])
    heads: dict = {}
    prev = [-1] * n

    def put(pos: int, cost: int, rep: int, lit: int, fp: int, fs: int, tok) -> None:
        a = arr[pos]
        key = lit > 0
        for s in a:
            if s[1] == rep and (s[2] > 0) == key:
                if cost < s[0]:
                    s[:] = [cost, rep, lit, fp, fs, tok]
                return
        if len(a) < ARRIVALS:
            a.append([cost, rep, lit, fp, fs, tok])
            return
        w = max(range(len(a)), key=lambda j: a[j][0])
        if cost < a[w][0]:
            a[w] = [cost, rep, lit, fp, fs, tok]

    skip_to = 0
    for i in range(n):
        if i >= 1:
            k = data[i - 1:i + 1]
            prev[i - 1] = heads.get(k, -1)
            heads[k] = i - 1
        a = arr[i]
        if not a or i < skip_to:
            continue
        a.sort(key=lambda s: s[0])
        del a[ARRIVALS:]
        # literaali: yksi tavu lisää
        for si, (c, rep, lit, _, _, _) in enumerate(a):
            if lit:
                cost = c + 8 + elias_len(lit + 1) - elias_len(lit)
            else:
                cost = c + 8 + elias_len(1) + (1 if i else 0)
            if lit < MAX_LEN:
                put(i + 1, cost, rep, lit + 1, i, si, ('L',))
        if i == 0:
            continue
        # toisto vain literaalin jälkeen
        for si, (c, rep, lit, _, _, _) in enumerate(a):
            if not lit or rep > i:
                continue
            m = 0
            lim = min(n - i, MAX_LEN)
            while m < lim and data[i + m] == data[i + m - rep]:
                m += 1
            for ln in range(1, m + 1):
                put(i + ln, c + 1 + elias_len(ln), rep, 0, i, si, ('R', ln))
        # uusi offset: vain paras tila ratkaisee (rep nollautuu)
        c0 = a[0][0]
        lo = 2
        for ln_max, off in _matches(data, i, heads, prev):
            oc = c0 + 1 + elias_len(((off - 1) >> 7) + 1) + 8 - 1
            if ln_max >= LONG:
                put(i + ln_max, oc + elias_len(ln_max - 1), off, 0, i, 0, ('M', ln_max, off))
                skip_to = i + ln_max
                lo = ln_max + 1
                break
            for ln in range(lo, ln_max + 1):
                put(i + ln, oc + elias_len(ln - 1), off, 0, i, 0, ('M', ln, off))
            lo = ln_max + 1
    # takaisinjäljitys
    best = min(range(len(arr[n])), key=lambda j: arr[n][j][0])
    toks = []
    pos, si = n, best
    while pos > 0:
        s = arr[pos][si]
        toks.append((s[5], pos))
        pos, si = s[3], s[4]
    toks.reverse()
    out: list[tuple] = []
    for tok, end in toks:
        if tok[0] == 'L':
            if out and out[-1][0] == 'L':
                out[-1] = ('L', out[-1][1] + 1)
            else:
                out.append(('L', 1))
        else:
            out.append(tok)
    return out


# ---------------------------------------------------------------------------------------------------- koodaus

def encode(data: bytes, toks: list[tuple]) -> bytes:
    """Virta dalin tapaan paikallaan purettavaksi: kun purku saavuttaisi lukukohdan, loput raakana."""
    n = len(data)
    w = BitWriter()
    marks = []                       # (purettu kohta, virran pituus) jokaisen merkin jälkeen
    u = 0
    for k, t in enumerate(toks):
        if t[0] == 'L':
            if k:
                w.bit(0)
            w.elias(t[1])
            w.out += data[u:u + t[1]]
            u += t[1]
        elif t[0] == 'R':
            w.bit(0)
            w.elias(t[1])
            u += t[1]
        else:
            _, ln, off = t
            w.bit(1)
            w.elias(((off - 1) >> 7) + 1)
            w.byte((((off - 1) & 0x7F) << 1) | (1 if ln == 2 else 0))
            if ln != 2:
                w.elias(ln - 1, skip=True)
            u += ln
        marks.append((t[0], u, len(w.out)))
    total = len(w.out)
    # dali: overwrite = u - (n - total + p); literaali joka ylittäisi -> palataan edelliseen turvakohtaan
    safe_u, safe_p = 0, 0
    for kind, u, p in marks:
        if u - (n - total + p) >= 0:
            if kind == 'L':
                u, p = safe_u, safe_p
            return bytes(w.out[:p]) + data[u:]
        safe_u, safe_p = u, p
    raise SystemExit("zx0: ei paikallaan purettavaa loppua")


def pack(data: bytes, dest: int) -> bytes:
    """Raaka data osoitteeseen dest -> Krillin pakattu PRG."""
    key = hashlib.sha256(b"zx0v1" + bytes([dest & 255, dest >> 8]) + data).hexdigest()
    hit = CACHE / key
    if hit.exists():
        return hit.read_bytes()
    stream = encode(data, parse(data))
    if len(stream) + 2 > len(data):
        raise SystemExit("zx0: pakattu on suurempi kuin alkuperäinen")
    load = dest + len(data) - len(stream) - 2
    out = bytes([load & 255, load >> 8, dest >> 8, dest & 255]) + stream
    unpacked = unpack(out)
    if unpacked != (dest, data):
        raise SystemExit("zx0: tarkistuspurku ei täsmää")
    CACHE.mkdir(parents=True, exist_ok=True)
    hit.write_bytes(out)
    return out


# ---------------------------------------------------------------------------------------------------- purku

def unpack(prg: bytes) -> tuple[int, bytes]:
    """Purku kuten Krillin zx0decomp.s paikallaan: muisti mallinnetaan, loppuehto dst == src ottelun jälkeen."""
    load = prg[0] | prg[1] << 8
    mem = bytearray(65536)
    mem[load:load + len(prg) - 2] = prg[2:]
    src = load
    dest = mem[src] << 8 | mem[src + 1]
    src += 2
    dst = dest
    bits = 0
    nb = 0

    def bit() -> int:
        nonlocal bits, nb, src
        if nb == 0:
            bits = mem[src]
            src += 1
            nb = 8
        b = bits & 1
        bits >>= 1
        nb -= 1
        return b

    def elias(skip: bool = False) -> int:
        d = []
        while skip or not bit():
            skip = False
            d.append(bit())
        if len(d) < 8:
            v = 1
            for b in d:
                v = v << 1 | b
            return v
        lo = 0
        for b in d[:8]:
            lo = lo << 1 | b
        hi = 1
        for b in d[8:]:
            hi = hi << 1 | b
        return hi << 8 | lo

    rep = 1
    while True:
        ln = elias()                    # literaali; tyyppibitti luettiin jo (ensimmäisellä ei ole)
        mem[dst:dst + ln] = mem[src:src + ln]
        dst += ln
        src += ln
        if not bit():                   # toisto
            ln = elias()
            for _ in range(ln):
                mem[dst] = mem[dst - rep]
                dst += 1
            if dst == src:
                break
            if not bit():
                continue
        while True:                     # uusi offset
            hi = elias()
            if hi >= 256:
                raise SystemExit("zx0: loppumerkki paikallaan purettavassa")
            b = mem[src]
            src += 1
            rep = (((hi - 1) << 7) | (b >> 1)) + 1
            ln = 2 if b & 1 else elias(skip=True) + 1
            for _ in range(ln):
                mem[dst] = mem[dst - rep]
                dst += 1
            if dst == src or not bit():
                break
        if dst == src:
            break
    return dest, bytes(mem[dest:load + len(prg) - 2])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "pack":
        b = Path(sys.argv[2]).read_bytes()
        Path(sys.argv[3]).write_bytes(pack(b[2:], b[0] | b[1] << 8))
    elif cmd == "boot":                 # BIN DEST LABELS OUTDIR: bootin payload.zx0 ja payload.inc
        b = Path(sys.argv[2]).read_bytes()
        dest = int(sys.argv[3], 16)
        lab = Path(sys.argv[4]).read_text()
        start = int(re.search(r"^al ([0-9a-fA-F]+) \.start$", lab, re.M).group(1), 16)
        out = Path(sys.argv[5])
        z = pack(b, dest)
        (out / "payload.zx0").write_bytes(z)
        (out / "payload.inc").write_text(
            f"PAY_AT = ${z[0] | z[1] << 8:04x}\nPAY_LEN = {len(z) - 2}\nPAY_DEST = ${dest:04x}\nPAY_START = ${start:04x}\n")
    elif cmd == "unpack":
        d, data = unpack(Path(sys.argv[2]).read_bytes())
        Path(sys.argv[3]).write_bytes(bytes([d & 255, d >> 8]) + data)
    else:
        raise SystemExit(f"zx0.py: tuntematon komento {cmd}")
