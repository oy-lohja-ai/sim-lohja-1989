"""C64-muodot: MC-bittikartta letterboxiin, MC-spritet, merkistö. Syöte indeksikuvina (Colodore-indeksit)."""
from __future__ import annotations

import numpy as np

from concept import c64

TRANSP = 255


def _lab_dist(a: int, b: int) -> float:
    pal = c64.lab(c64.palette().astype(np.float64))
    return float(((pal[a] - pal[b]) ** 2).sum())


class Bitmap:
    """(4*cols)x(8*rows) MC-pikselin indeksikuva -> bittikartta, ruutu ja värimuisti ($D021 = bg).
    Muistijärjestys kuten VIC:n 40 merkin rivi, kun cols = 40; leveämmässä kuvassa rivin pituus on cols."""

    def __init__(self, img: np.ndarray, bg: int = 0, forced: dict | None = None):
        """forced: {(cy, cx): (a, b, c)}: solun värit rooleihin %01, %10, %11 kiinteästi (värikierto)."""
        forced = forced or {}
        h, w = img.shape
        assert w % 4 == 0 and h % 8 == 0, img.shape
        self.rows = h // 8
        self.cols = cols = w // 4
        self.bmp = bytearray(self.rows * cols * 8)
        self.scr = bytearray(self.rows * cols)
        self.col = bytearray(self.rows * cols)
        self.fixes = 0
        self.fixed_cells: list[tuple[int, int]] = []
        out = img.copy()
        for cy in range(self.rows):
            for cx in range(cols):
                cell = img[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
                if (cy, cx) in forced:
                    seq = forced[(cy, cx)]
                    role = {c: k + 1 for k, c in enumerate(seq)}
                    assert set(np.unique(cell).tolist()) <= set(seq), (cy, cx, np.unique(cell))
                    self.scr[cy * cols + cx] = (seq[0] << 4) | seq[1]
                    self.col[cy * cols + cx] = seq[2]
                    for y in range(8):
                        b = 0
                        for x in range(4):
                            b |= role[int(cell[y, x])] << (6 - 2 * x)
                        self.bmp[cy * cols * 8 + cx * 8 + y] = b
                    continue
                vals, counts = np.unique(cell, return_counts=True)
                order = [int(v) for v, _ in sorted(zip(vals, counts), key=lambda t: -t[1]) if v != bg]
                keep = order[:3]
                if len(order) > 3:
                    self.fixes += 1
                    self.fixed_cells.append((cy, cx))
                    cell = cell.copy()
                    for v in order[3:]:
                        near = min(keep + [bg], key=lambda k: _lab_dist(v, k))
                        cell[cell == v] = near
                    out[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4] = cell
                keep = sorted(keep)                     # kiinteä järjestys: pienin -> %01, sitten %10, %11
                while len(keep) < 3:
                    keep.append(0)
                role = {bg: 0}
                for k, v in enumerate(keep):
                    role.setdefault(v, k + 1)
                c01, c10, c11 = keep
                self.scr[cy * cols + cx] = (c01 << 4) | c10
                self.col[cy * cols + cx] = c11
                for y in range(8):
                    b = 0
                    for x in range(4):
                        b |= role[int(cell[y, x])] << (6 - 2 * x)
                    self.bmp[cy * cols * 8 + cx * 8 + y] = b
        self.image = out


def sprite_bytes(im: np.ndarray) -> bytes:
    """12x21 MC-pikselin roolikuva (0 läpinäkyvä, 1 $D025, 2 oma väri, 3 $D026) -> 64 tavua."""
    assert im.shape == (21, 12), im.shape
    out = bytearray(64)
    for y in range(21):
        for bx in range(3):
            b = 0
            for x in range(4):
                b |= int(im[y, bx * 4 + x]) << (6 - 2 * x)
            out[y * 3 + bx] = b
    return bytes(out)


def glyph_bytes(ch: str) -> bytes:
    g = c64.glyph(ch)
    return bytes(int("".join("1" if v else "0" for v in row), 2) for row in g)


def encode_layers(img: np.ndarray, sky_t: int, front: np.ndarray | None = None
                  ) -> tuple[bytes, bytes, bytes, np.ndarray, int]:
    """Linecrunch-kuva (src/lib/crunch.asm), jossa $D021 vaihtelee riveittäin: leveys 160, rivit VIC-muodossa
    (320 + 40 + 40 tavua per merkkirivi). Rivit 0..sky_t-1 ovat taivasrivejä: 255 -> %00 (rivin $D021), ja musta
    tarvitsee solussa oman värin. Alemmilla riveillä musta 0 -> %00 ($D021 = 0) eikä 255 ole sallittu. Yli 3
    väriä: harvinaisin lähimpään. front (H x 160, bool): pikselit, joiden takana voi olla sprite ($D01B): sprite näkyy
    %00- ja %01-pikseleiden läpi, joten %01:ksi valitaan solun väri, jolla on vähiten front-pikseleitä.
    Palauttaa bmp, scr, col, näytettävän kuvan (255 säilyy) ja korjatut solut."""
    h = img.shape[0]
    assert img.shape[1] == 160 and h % 8 == 0, img.shape
    bmp, scr, col = bytearray(h * 40), bytearray(h // 8 * 40), bytearray(h // 8 * 40)
    out = img.copy()
    fixes = 0
    sky = np.arange(h) < sky_t
    for cy in range(h // 8):
        for cx in range(40):
            cell = out[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
            srow = sky[cy * 8:cy * 8 + 8, None].repeat(4, 1)
            vals, cnt = np.unique(cell[(cell != TRANSP) & ((cell != 0) | srow)], return_counts=True)
            order = [int(v) for v, _ in sorted(zip(vals, cnt), key=lambda t: -t[1])]
            keep = order[:3]
            if len(order) > 3:
                fixes += 1
                bgs = [0] if not srow.any() else []
                for v in order[3:]:
                    near = min(keep + bgs, key=lambda k: _lab_dist(v, k))
                    cell[cell == v] = near
            if front is not None and len(keep) == 3:          # %01 = väri, jonka takana vähiten spritejä
                fm = front[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
                keep = sorted(keep, key=lambda v: (int((fm & (cell == v)).sum()), v))
                keep = [keep[0]] + sorted(keep[1:])
            elif front is not None:                             # vajaa solu: %01 jää käyttämättä
                keep = [0] * (3 - len(keep)) + sorted(keep)
            else:
                keep = sorted(keep)
            keep = keep + [0] * (3 - len(keep))
            role = {v: k + 1 for k, v in enumerate(keep) if (v != 0 or 0 in order[:3])}
            scr[cy * 40 + cx] = (keep[0] << 4) | keep[1]
            col[cy * 40 + cx] = keep[2]
            for y in range(8):
                b = 0
                for x in range(4):
                    v = int(cell[y, x])
                    b |= role.get(v, 0) << (6 - 2 * x)
                    assert v == TRANSP or v in role or (v == 0 and not srow[y, 0]), (cy, cx, y, v)
                bmp[cy * 320 + cx * 8 + y] = b
    return bytes(bmp), bytes(scr), bytes(col), out, fixes
