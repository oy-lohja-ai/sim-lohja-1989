"""Lohjantähden kuoppa (partti 5): staattinen data konseptin generaattoreista (tools/concept/concept/kuoppa2.py,
kuoppa.py, star.py). Host tekee vain kuvia ja tauluja; liike on 6510:n koodissa (kuoppa.asm).

  uv run --project tools/concept python src/proto/kuoppa/build.py build/kuoppa

Tulos OUT/: k1.bin, k2.bin, k3.bin (kuva-alue 18 merkkiriviä: bittikartta 5760 + ruutu 720 + värit 720) ja
kuoppa.inc (vakiot). Esikatselu OUT/k*.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/gfx"))
sys.path.insert(0, str(Path(__file__).parent))

from c64fmt import Bitmap  # noqa: E402
from concept.c64 import to_rgb  # noqa: E402

import kuormaaja  # noqa: E402
import runko  # noqa: E402
import torni  # noqa: E402


def pack(img: np.ndarray, fixed: dict | None = None) -> tuple[bytes, Bitmap]:
    """160 x 144 -> bittikartta, ruutu ja värit VIC-järjestyksessä (40 saraketta, 18 riviä). fixed: {(cy, cx):
    {väri: rooli}} solut, joiden roolit ovat kiinteät (liikkuva kone piirtää samoilla rooleilla)."""
    bm = Bitmap(img, bg=0)
    assert bm.fixes == 0, bm.fixed_cells[:8]
    for (cy, cx), role in (fixed or {}).items():
        cell = img[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
        inv = {r: c for c, r in role.items()}
        bm.scr[cy * 40 + cx] = inv[1] << 4 | inv[2]
        bm.col[cy * 40 + cx] = inv[3]
        for y in range(8):
            b = 0
            for x in range(4):
                b |= role[int(cell[y, x])] << (6 - 2 * x)
            bm.bmp[cy * 320 + cx * 8 + y] = b
    return bytes(bm.bmp) + bytes(bm.scr) + bytes(bm.col), bm


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    k1info = kuormaaja.export(out)
    runko.export(out)                  # k2.bin ja k2runs.bin (valmiin kuvan tavut) yhteisellä paletilla
    torni.export(out)                  # k3.bin ja XOR-ryhmät
    shots = {"k1": k1info["bg"]}
    fixed = {"k1": {(cy, cx): kuormaaja.ROLE for cy in range(*kuormaaja.ZONE_ROWS) for cx in range(kuormaaja.ZONE_COLS)}}
    for name, img in shots.items():
        data, bm = pack(img, fixed.get(name))
        (out / f"{name}.bin").write_bytes(data)
        Image.fromarray(to_rgb(np.repeat(np.repeat(bm.image.astype(int), 2, 1), 1, 0))).save(out / f"{name}.png")
    (out / "kuoppa.inc").write_text("; build.py\nPIC_BYTES = 7200\n")


if __name__ == "__main__":
    main()
