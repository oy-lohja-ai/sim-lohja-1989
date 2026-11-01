"""D64-levykuva Krillin lataajalle (v194). Puhdasta Pythonia.

Tiedostot sijoitetaan latausjärjestyksessä nousevasti raidalta 1 alkaen (raita 18 ohitetaan), sektorilomitus 4
ja raidan sisällä `(sektori + lomitus) % sektoreita` kuten Krillin README ("Optimising for speed") ja cc1541.
Hakemiston lopussa 00 ff, dirartin rivit ovat DEL-merkintöjä raidalla 0 (README "Dir-art"), oikeiden tiedostojen
lohkomäärät ovat oikeat, ja nimien 16-bittiset tiivisteet tarkistetaan (cc1541 filenamehash) törmäysten varalta.
Piilotettu tiedosto (Entry.hidden) on hakemistossa tyyppitavulla 0 (poistettu, scratch): 1541:n DOS ei listaa sitä
LOAD"$":ssa, mutta Krill tunnistaa tiedostot pelkästä alkuraidasta tyypistä välittämättä (drivecode-common.inc
getdirloop, README "Dir-art": «Program files are recognised by the loader regardless of their apparent type»).
"""
from __future__ import annotations

from dataclasses import dataclass

SECTORS = [0] + [21] * 17 + [19] * 7 + [18] * 6 + [17] * 5     # raidat 1-35
DIRTRACK = 18
INTERLEAVE = 4
DIR_INTERLEAVE = 3
PAD = 0xA0
TYPES = {"del": 0x80, "seq": 0x81, "prg": 0x82}


# dirartin grafiikkamerkit (isot kirjaimet/grafiikka -tila) Unicodena: PETSCII-koodi
GRAPHICS = {"▌": 0xA1, "▄": 0xA2, "▔": 0xA3, "▁": 0xA4, "▏": 0xA5, "▒": 0xA6, "▕": 0xA7, "◤": 0xA9, "├": 0xAB,
            "▗": 0xAC, "└": 0xAD, "┐": 0xAE, "▂": 0xAF, "┌": 0xB0, "┴": 0xB1, "┬": 0xB2, "┤": 0xB3, "▎": 0xB4,
            "▍": 0xB5, "▃": 0xB9, "▖": 0xBB, "▝": 0xBC, "┘": 0xBD, "▘": 0xBE, "▚": 0xBF, "─": 0xC0, "♠": 0xC1,
            "╮": 0xC9, "╰": 0xCA, "╯": 0xCB, "╲": 0xCD, "╱": 0xCE, "●": 0xD1, "♥": 0xD3, "╭": 0xD5, "╳": 0xD6,
            "○": 0xD7, "♣": 0xD8, "♦": 0xDA, "┼": 0xDB, "│": 0xDD, "π": 0xDE, "◥": 0xDF}


def petscii(s: str) -> bytes:
    """Teksti hakemistoon ja SEQ-tiedostoon (isot kirjaimet/grafiikka): a-z ja A-Z -> $41-$5a, ä/ö/å -> A/O/A,
    grafiikkamerkit GRAPHICS (À = $c0 merkkikoodinaan)."""
    out = bytearray()
    for ch in s:
        if ch in GRAPHICS:
            out.append(GRAPHICS[ch])
            continue
        ch = {"ä": "a", "ö": "o", "å": "a", "Ä": "A", "Ö": "O", "Å": "A", "\n": "\r"}.get(ch, ch)
        o = ord(ch)
        if 0x61 <= o <= 0x7A:
            o -= 0x20
        if o > 0xFF:
            raise SystemExit(f"d64: merkki {ch!r} ei ole PETSCII:ssä")
        out.append(o)
    return bytes(out)


def name_hash(name: bytes) -> int:
    """Krillin aseman hakemistopuskurin tiiviste (cc1541.c filenamehash, FILENAME_MAXLENGTH 16)."""
    name = name[:16].rstrip(bytes([PAD]))
    lo = hi = len(name)
    carry = 1
    for c in reversed(name):
        s = lo + c + carry
        carry = s >> 8
        lo = s & 255
        s = lo + hi + carry
        carry = s >> 8
        hi = s & 255
    return hi << 8 | lo


@dataclass
class Entry:
    name: bytes              # PETSCII, enintään 16
    kind: str = "prg"        # prg, seq, del (dirart)
    data: bytes = b""        # tiedoston sisältö (PRG: latausosoite mukana)
    track: int = 0
    sector: int = 0
    blocks: int = 0
    hidden: bool = False     # tyyppitavu 0: ei näy DOS:n listauksessa, Krill lataa


class D64:
    def __init__(self, name: bytes, ident: bytes) -> None:
        self.img = bytearray(sum(SECTORS) * 256)
        self.used = [set() for _ in SECTORS]
        self.name, self.ident = name, ident
        self.entries: list[Entry] = []
        self.deferred: list[Entry] = []   # lohkot levyn loppuun (add(..., loppuun=True)), hakemistossa paikallaan
        self.track, self.sector = 1, 0

    def off(self, t: int, s: int) -> int:
        return (sum(SECTORS[:t]) + s) * 256

    def _next_block(self) -> tuple[int, int]:
        while True:
            if self.track == DIRTRACK:
                self.track, self.sector = DIRTRACK + 1, 0
            if self.track >= len(SECTORS):
                raise SystemExit("d64: levy täynnä")
            n = SECTORS[self.track]
            for k in range(n):
                s = (self.sector + k) % n
                if s not in self.used[self.track]:
                    self.used[self.track].add(s)
                    self.sector = (s + INTERLEAVE) % n
                    return self.track, s
            self.track, self.sector = self.track + 1, 0

    def add(self, e: Entry, loppuun: bool = False) -> None:
        """Tiedosto hakemiston seuraavaksi; lohkot heti (latausjärjestyksessä) tai loppuun=True: muiden jälkeen
        (finish), jolloin muiden tiedostojen paikat ovat samat kuin ilman tätä."""
        if e.kind != "del":
            if not e.data:
                raise SystemExit(f"d64: tyhjä tiedosto {e.name!r}")
            if loppuun:
                self.deferred.append(e)
            else:
                self._alloc(e)
        self.entries.append(e)

    def _alloc(self, e: Entry) -> None:
        chunks = [e.data[i:i + 254] for i in range(0, len(e.data), 254)]
        blocks = [self._next_block() for _ in chunks]
        for k, (chunk, (t, s)) in enumerate(zip(chunks, blocks)):
            o = self.off(t, s)
            if k + 1 < len(blocks):
                self.img[o:o + 2] = bytes(blocks[k + 1])
            else:
                self.img[o:o + 2] = bytes([0, len(chunk) + 1])
            self.img[o + 2:o + 2 + len(chunk)] = chunk
        e.track, e.sector = blocks[0]
        e.blocks = len(blocks)

    def finish(self) -> bytes:
        for e in self.deferred:
            self._alloc(e)
        self.deferred = []
        files = [e for e in self.entries if e.kind != "del"]
        if len(files) < 2:
            raise SystemExit("d64: Krill vaatii vähintään 2 tiedostoa")
        seen: dict[int, bytes] = {}
        for e in files:
            h = name_hash(e.name)
            if h in seen:
                raise SystemExit(f"d64: nimien tiiviste törmää: {seen[h]!r} ja {e.name!r}")
            seen[h] = e.name
        # hakemisto 18/1, 18/4, ...
        n = SECTORS[DIRTRACK]
        dsecs = []
        s = 1
        for _ in range((len(self.entries) + 7) // 8):
            while s in dsecs or s == 0:
                s = (s + 1) % n
            dsecs.append(s)
            s = (s + DIR_INTERLEAVE) % n
        if len(dsecs) > n - 1:
            raise SystemExit("d64: hakemisto täynnä")
        for k, ds in enumerate(dsecs):
            o = self.off(DIRTRACK, ds)
            self.img[o:o + 2] = bytes([DIRTRACK, dsecs[k + 1]]) if k + 1 < len(dsecs) else bytes([0, 0xFF])
            for j, e in enumerate(self.entries[k * 8:k * 8 + 8]):
                p = o + j * 32
                self.img[p + 2] = 0 if e.hidden else TYPES[e.kind]
                self.img[p + 3] = e.track
                self.img[p + 4] = e.sector
                self.img[p + 5:p + 21] = e.name.ljust(16, bytes([PAD]))[:16]
                self.img[p + 30] = e.blocks & 255
                self.img[p + 31] = e.blocks >> 8
        # BAM 18/0
        self.used[DIRTRACK] |= {0, *dsecs}
        o = self.off(DIRTRACK, 0)
        bam = bytearray(256)
        bam[0:4] = bytes([DIRTRACK, dsecs[0], 0x41, 0])
        for t in range(1, len(SECTORS)):
            free = [s for s in range(SECTORS[t]) if s not in self.used[t]]
            bits = sum(1 << s for s in free)
            bam[4 * t:4 * t + 4] = bytes([len(free), bits & 255, bits >> 8 & 255, bits >> 16 & 255])
        bam[0x90:0xA0] = self.name.ljust(16, bytes([PAD]))[:16]
        # tunnus: 2 merkkiä (+ $a0 "2A") tai koko otsikon 5 merkin loppu ("OY AI": ID "OY", Krill vertaa vain ID:tä)
        tail = self.ident[:5].ljust(5, b" ") if len(self.ident) > 2 else self.ident.ljust(2, b" ") + bytes([PAD]) + b"2A"
        bam[0xA0:0xAB] = bytes([PAD, PAD]) + tail + bytes([PAD] * 4)
        self.img[o:o + 256] = bam
        return bytes(self.img)

    def free_blocks(self) -> int:
        return sum(SECTORS[t] - len(self.used[t]) for t in range(1, len(SECTORS)) if t != DIRTRACK)
