"""Kopiorutiini siirretylle esilataukselle (6510-konekieli tavuina): tiedosto ladataan edellisen kohtauksen aikana
muualle ja kohtauksen taulu kopioi sen paikalleen (`kokoa.py` siirto, greetsit `split.py`). Rutiini on tiedoston
perässä, joten se ei koske kopion kohteeseen."""
from __future__ import annotations


def kopio(at: int, moves: list[tuple[int, int, int]]) -> bytes:
    """Rutiini osoitteeseen at: jokainen (lähde, kohde, tavuja) kopioidaan alusta loppuun ($01 = $35 kopion ajan:
    lähde voi olla $e000-:ssa RAMissa), rts. Lähde ja kohde eivät saa mennä päällekkäin."""
    out = bytearray(b"\xa5\x01\x48\xa9\x35\x85\x01")          # lda $01, pha, lda #$35, sta $01
    for src, dst, n in moves:
        full, rem = divmod(n, 256)
        if full:
            lp = at + len(out) + 4                              # ldx #full, ldy #0 ennen silmukkaa
            out += bytes([0xA2, full, 0xA0, 0x00,
                          0xB9, src & 255, src >> 8, 0x99, dst & 255, dst >> 8,     # lda src,y / sta dst,y
                          0xC8, 0xD0, 0xF7,                                         # iny / bne lp
                          0xEE, (lp + 2) & 255, (lp + 2) >> 8, 0xEE, (lp + 5) & 255, (lp + 5) >> 8,   # sivu eteenpäin
                          0xCA, 0xD0, 0xEE])                                        # dex / bne lp
        if rem:                                                 # viimeinen vajaa sivu tavulleen (ei kohteen yli)
            s, d = src + full * 256, dst + full * 256
            out += bytes([0xA0, 0x00, 0xB9, s & 255, s >> 8, 0x99, d & 255, d >> 8,   # ldy #0, lda s,y / sta d,y
                          0xC8, 0xC0, rem, 0xD0, 0xF5])                             # iny / cpy #rem / bne
    return bytes(out + b"\x68\x85\x01\x60")                    # pla, sta $01, rts
