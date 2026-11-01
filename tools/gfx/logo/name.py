"""Nimi "OY LOHJA AI" spriteinä ja sen ajoitus, kirjaimisto ja asettelu emblemin alkuperäisen animaation pitokuvasta.

Kahdeksan hires-spriteä: O Y L O H J A ja viimeisenä AI yhdessä (yhdeksän kirjainta ei mahdu kahdeksaan
spriteen samalla rivillä). Kirjain putoaa ylhäältä ylitykseen ja asettuu, väri nousee harmaasta valkoiseksi;
seuraava kirjain puolen iskun päästä. Purun jälkeen kirjaimet putoavat pois yksi kerrallaan ruudun alareunan alle.

Sama data 6510:lle (build.py: sprites.asm, vakiot) ja vertailumallille (sprite_layer).
"""
from __future__ import annotations


import numpy as np

# alkuperäisen animaation nimen kirjaimet (13 lähteen riviä) 11 rivinä: rivit 2 ja 9
# pois (pystysuunta 0,83 kuten emblemillä)
GLYPH = {
    "O": [".####.", "######", "##..##", "##..##", "##..##", "##..##", "##..##", "##..##", "##..##", "######", ".####."],
    "Y": ["#..##", "#..##", "#.##.", "####.", "####.", ".##..", ".##..", ".##..", ".##..", ".##..", ".##.."],
    "L": ["##...", "##...", "##...", "##...", "##...", "##...", "##...", "##...", "##...", "#####", "#####"],
    "H": ["##..##", "##..##", "##..##", "##..##", "##..##", "######", "######", "##..##", "##..##", "##..##", "##..##"],
    "J": ["..##", "..##", "..##", "..##", "..##", "..##", "..##", "..##", "..##", "####", "###."],
    "A": ["...#...", "..###..", "..###..", "..#.#..", "..#.#..", ".##.##.", ".##.##.", ".#####.", ".#...#.", "##...##",
          "##...##"],
    "I": ["##"] * 11,
}
TEXT = ["O", "Y", "L", "O", "H", "J", "A", "AI"]   # sprite kerrallaan
# kirjainten vasemmat reunat (hires): alkuperäisen animaation sarakkeet 89 103 129 144 159 174 188 214 (I 230) kuvattuna
# x -> 160 + (x - 160) * 0,922; AI-spritessä I 15 px A:n jälkeen
XS = [94, 107, 131, 145, 159, 173, 186, 210]
AI_I = 15
ROW = 176                                          # yläreuna ruudun rivinä (alkuperäisen animaation rivi 226)
NSTEP = 15                                         # kirjainten väli kehyksinä (puoli iskua)
DROP = [-24, -21, -17, -12, -6, 0, 3, 4, 3, 1, -1, -1, 0, 0, 0, 0]   # pystysiirtymä putoamisen kehyksillä
RAMP = [11, 11, 12, 12, 15, 15, 1, 1]              # väri putoamisen kehyksillä, sitten 1 (alkuperäinen: valkoinen)
# purun jälkeen kirjaimet putoavat pois yksi kerrallaan (väli ei ole musta, peilaa putoamista sisään): pieni hyppy
# ylös, sitten painovoimalla alareunan alle (rivi 200 on reunan takana)
OSTEP = 8                                          # kirjainten väli kehyksinä
ODROP = [-1, -3, -4, -4, -3, -1, 2, 6, 11, 17, 24, 32]
OCOL = [1, 1, 1, 15, 15, 15, 12, 12, 11, 11, 11, 11]


def glyphs():
    """[(sprite 21 x 24 bool), x ruudulla (hires)]"""
    out = []
    for s, x0 in zip(TEXT, XS):
        img = np.zeros((21, 24), bool)
        x = 0
        for ch in s:
            g = np.array([[c == "#" for c in r] for r in GLYPH[ch]])
            img[:g.shape[0], x:x + g.shape[1]] = g
            x += AI_I
        assert img.any(), s
        out.append((img, x0))
    return out


def sprite_bytes(img):
    rows = []
    for r in range(21):
        bits = img[r]
        rows += [int("".join("1" if b else "0" for b in bits[k * 8:k * 8 + 8]), 2) for k in range(3)]
    return rows + [0]
