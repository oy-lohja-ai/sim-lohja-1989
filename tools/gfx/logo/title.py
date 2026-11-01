"""Alun nimiruutu (tools/gfx/data/nimi: SIM LOHJA 1989 Lohjan yllä + lappuset) pankin 2 kuvaksi,
logon maalaukseksi ilmakuvan päälle ja lappusten ponnahduksiksi.

Logo ilman mustaa taustaa (repaint ja spritet): ilmakuva ilman logoa (nimi_ilmakuva.kla) avautuu koko ruudulle, ja logo
maalautuu sen päälle vedoittain: logon solu vaihtuu ilmakuvasta ilmakuva + logo -soluksi (repaint: logon pikselit
ilmakuvan päälle, ilmakuvan pikselit ennallaan). Jos solun väreihin (tausta + 3) ei mahdu ilmakuva ja logon värit,
bittikarttaan jää ilmakuva ja logon kohdalla musta (tausta), ja logon keltainen ja vaaleanpunainen tulevat MC-
spriteistä (3 solua x 2 solun riviä spriteä kohden, kaistoittain multipleksattuna: hand.asm ev_irq -> TSPR).

  title.prg  $8000 näkyvä ruutu (nollia), $8400 värimuistin lähde, $8800 ruudun lähde (ilmakuvan avauduttua
             spritelohkot, SPR), $8c00 IRQ-koodi title.asm (TCODE), LCNT logon soluja kehyksittäin, LREC logon
             solut maalausjärjestyksessä, $a000 bittikartta (ilmakuva)
  title2.prg TPOP- (ennen $8000:aa, CRANE1:n $746f yläpuolella): lappusten ponnahdukset (ladataan title_go:n jälkeen)

Solutietue (LREC ja TPOP): ruudun siirros o (alatavu, ylätavu | $80 = spritetavut perässä), ruutu, väri, 8 tavua
bittikarttaa ($a000 + 8 o), [spritetavujen osoite, 8 tavua 3 tavun välein].

Paljastus kehyksinä nimiruudun alusta (nimiruutu ei ole still: logo maalautuu siveltimenvetoina esiin ja lappuset
ponnahtavat tahdissa):

  ilmakuva avautuu viivan solurivistä ylös ja alas 0-32 (t = 2 |cy - LR| + (3 cx) % 5, title.asm laskee),
  logo maalautuu vedoittain keskeltä reunoille 36-115 (logo_t), lappuset ponnahtavat kahden iskun välein 120, 180, 240, 300

  python3 -I tools/gfx/logo/title.py OUT.prg     # data ilman koodia (tarkistus)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tools/gfx/data/nimi"
LINE = 119                      # alun horisontin rivi: sen solurivi näkyy heti, ilmakuva avautuu siitä
LR = LINE // 8
SPR = 0x8800                    # spritelohkot ruudun lähteen paikalla (se on käytetty, kun ilmakuva on auki)
TCODE = 0x8C00                  # title.asm (ruudun lähteen $8800-$8be7 perässä)
LCNT, LREC = 0x9000, 0x9100     # logon soluja kehyksittäin (256), logon solutietueet
TPOP_END = 0x8000               # title2.prg loppuu title.prg:n alkuun
CRANE1_END = 0x7470             # Hillnerin CRANE1 ($1a00-$746f) latautuu nimiruudun aikana
INFO = json.loads((DATA / "nimi.json").read_text(encoding="utf-8"))
LOGO_X, LOGO_Y = INFO["logon_paikka_nimiruudulla"]["x"], INFO["logon_paikka_nimiruudulla"]["y"]
YELLOW, LRED = INFO["logon_varit"]["keltainen"], INFO["logon_varit"]["siveltimen_tummat"]
POPS = [120, 180, 240, 300]     # lappusten kehykset nimiruudun alusta, kahden iskun välein (pidempi
                                # väli, etenee hitaammin; alku 1080 kehystä)
AEND = 2 * max(LR, 24 - LR) + 4  # ilmakuvan viimeinen kehys
LBUD = 12                       # logon soluja enintään kutsussa (myöhästynyt lataus purkautuu kehyksittäin)
LOGO0, LPAINT = 36, 80          # logon maalaus: alku ja kesto (kehyksiä nimiruudun alusta)


def koala(path: Path = DATA / "nimi.kla") -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    d = path.read_bytes()[2:]
    return (np.frombuffer(d[:8000], np.uint8), np.frombuffer(d[8000:9000], np.uint8),
            np.frombuffer(d[9000:10000], np.uint8), d[10000])


def cell_px(bmp, scr, col, bg: int, o: int) -> np.ndarray:
    """solun o (cy * 40 + cx) värit 8 x 4 MC-pikselinä"""
    b = np.asarray(bmp[o * 8:o * 8 + 8], np.uint8)
    sh = np.array([6, 4, 2, 0])
    v = (b[:, None] >> sh) & 3
    lut = np.array([bg, scr[o] >> 4, scr[o] & 15, col[o] & 15], np.uint8)
    return lut[v]


def encode(px: np.ndarray, bg: int) -> tuple[bytes, int, int]:
    """8 x 4 MC-pikseliä (enintään 3 väriä taustan lisäksi) -> 8 tavua, ruutu, väri"""
    cols = [int(c) for c, _ in sorted(zip(*np.unique(px[px != bg], return_counts=True)), key=lambda t: -t[1])]
    assert len(cols) <= 3, cols
    cols += [0] * (3 - len(cols))
    code = {bg: 0}
    for i, c in enumerate(cols):
        code.setdefault(c, i + 1)
    bits = np.vectorize(code.get)(px).astype(np.uint8)
    return bytes(int((r[0] << 6) | (r[1] << 4) | (r[2] << 2) | r[3]) for r in bits), (cols[0] << 4) | cols[1], cols[2]


def logo_layer() -> np.ndarray:
    """logo ruudun kokoisena (200 x 160, 255 = ei logoa)"""
    lg = np.load(DATA / "logo.npy")
    out = np.full((200, 160), 255, np.uint8)
    out[LOGO_Y:LOGO_Y + lg.shape[0], LOGO_X:LOGO_X + lg.shape[1]] = lg
    return out


def label_cells() -> list[list[tuple[int, int]]]:
    solut = [[(cy, cx) for cy, cx in cells] for cells in INFO["lappusten_solut"]]
    assert len(solut) == len(POPS), (len(solut), len(POPS))
    return solut


def logo_t() -> np.ndarray:
    """logon solun maalauskehys (25 x 40, -1 = ei logoa): vedoittain keskeltä reunoille (järjestys: etäisyys
    keskeltä ja rivien viive rdel), tasaisesti LPAINT kehykseen LOGO0:sta, joten joka kehys maalaa"""
    lm = (logo_layer() != 255).reshape(25, 8, 40, 4).any(axis=(1, 3))
    rdel = [((r * 7) % 11) + (r // 3) * 2 for r in range(25)]
    cells = sorted(zip(*np.nonzero(lm)), key=lambda c: (abs(2 * c[1] - 39) * 5 + rdel[c[0]], c[0], c[1]))
    t = np.full((25, 40), -1, np.int32)
    for k, (cy, cx) in enumerate(cells):
        t[cy, cx] = LOGO0 + k * LPAINT // len(cells)
    assert t[lm].min() > AEND and t.max() < POPS[0]
    return t


def logo_cells() -> dict:
    """logon solut ilmakuvan päälle: o -> (8 tavua, ruutu, väri, spritepikselit 8 x 4 tai None)"""
    bmp, scr, col, bg = koala(DATA / "nimi_ilmakuva.kla")
    lay = logo_layer()
    out = {}
    for cy, cx in zip(*np.nonzero(logo_t() >= 0)):
        o = int(cy) * 40 + int(cx)
        a = cell_px(bmp, scr, col, bg, o)
        lg = lay[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
        px = np.where(lg != 255, lg, a)
        if len(set(px[px != bg].tolist())) <= 3:
            out[o] = (*encode(px, bg), None)
        else:                                       # logon värit spriteen, bittikarttaan ilmakuva ja musta
            out[o] = (*encode(np.where(lg != 255, bg, a), bg), np.where(lg != 255, lg, bg))
    return out


def sprites(cells: dict) -> tuple[list[dict], dict]:
    """spritelaatikot (3 x 2 solua) kaistoittain: [{b0, cx0, n, blk}], solu -> laatikko. Laitteistosprite n
    valitaan niin, että sen edellinen käyttö on näkynyt ennen kaistan tapahtumaa (hand.asm ev_irq, TSPR)."""
    prob = sorted(o for o, c in cells.items() if c[3] is not None)
    rows = sorted({o // 40 for o in prob})
    boxes, of = [], {}
    if not prob:
        return boxes, of
    for b0 in range(rows[0], rows[-1] + 1, 2):
        end = -1
        for o in sorted(p for p in prob if b0 <= p // 40 < b0 + 2):
            if o % 40 > end:
                boxes.append({"b0": b0, "cx0": min(o % 40, 37)})
                end = boxes[-1]["cx0"] + 2
            of[o] = len(boxes) - 1
    last = {}                                       # n -> edellisen käytön kaistan b0
    for b0 in sorted({b["b0"] for b in boxes}):
        used = set()
        for i, b in enumerate(boxes):
            if b["b0"] != b0:
                continue
            free = [n for n in range(8) if n not in used and (n not in last or b0 - last[n] >= 4)]
            assert free, f"spritet loppuvat kaistalla {b0}"
            b["n"], b["blk"] = free[0], i
            used.add(free[0])
        for n in used:
            last[n] = b0
    assert len(boxes) <= 16, len(boxes)             # SPR $8800-$8bff
    return boxes, of


def sprite_bytes(px: np.ndarray) -> bytes:
    """solun spritepikselit (8 x 4, tausta = ei) MC-spriten tavuiksi: keltainen %10 (oma väri), LRED %01 ($d025)"""
    code = np.where(px == YELLOW, 2, np.where(px == LRED, 1, 0)).astype(np.uint8)
    assert ((px == YELLOW) | (px == LRED) | (code == 0)).all()
    return bytes(int((r[0] << 6) | (r[1] << 4) | (r[2] << 2) | r[3]) for r in code)


def rec(o: int, bm: bytes, s: int, c: int, spr: tuple[int, bytes] | None = None) -> bytes:
    out = bytes([o & 255, (o >> 8) | (0x80 if spr else 0), s, c]) + bytes(bm)
    if spr:
        out += bytes([spr[0] & 255, spr[0] >> 8]) + spr[1]
    return out


def spr_addr(box: dict, o: int) -> int:
    """solun o ensimmäisen spritetavun osoite laatikossa (rivit 3 tavun välein)"""
    return SPR + 64 * box["blk"] + 24 * (o // 40 - box["b0"]) + (o % 40 - box["cx0"])


def logo_recs(cells: dict, boxes: list[dict], of: dict) -> tuple[np.ndarray, bytes]:
    """LCNT (256) ja LREC: logon solut maalausjärjestyksessä"""
    t = logo_t().flatten()
    order = [o for o in np.argsort(t, kind="stable") if t[o] >= 0]
    out = bytearray()
    for o in order:
        bm, s, c, sp = cells[o]
        out += rec(int(o), bm, s, c, (spr_addr(boxes[of[o]], o), sprite_bytes(sp)) if sp is not None else None)
    return np.bincount(t[t >= 0], minlength=256).astype(np.uint8), bytes(out)


def pops(boxes: list[dict], of: dict) -> bytes:
    """TPOP: lappusittain määrä ja solut (nimi.kla:n solu; logon spritesolun spritetavut nollaan, lappunen päällä)"""
    bmp, scr, col, _ = koala()
    lt = logo_t().flatten()
    out = bytearray()
    for n, cells in enumerate(label_cells()):
        out.append(len(cells))
        for cy, cx in cells:
            o = cy * 40 + cx
            assert lt[o] < POPS[n], (o, lt[o])      # logo ennen lappusta
            spr = (spr_addr(boxes[of[o]], o), bytes(8)) if o in of else None
            out += rec(o, bmp[o * 8:o * 8 + 8], scr[o], col[o], spr)
    return bytes(out)


def plan() -> dict:
    cells = logo_cells()
    boxes, of = sprites(cells)
    lcnt, lrec = logo_recs(cells, boxes, of)
    pt = pops(boxes, of)
    return {"cells": cells, "boxes": boxes, "of": of, "lcnt": lcnt, "lrec": lrec, "pops": pt,
            "tpop": TPOP_END - len(pt)}


def prg(p: dict, code: bytes = b"") -> bytes:
    bmp, scr, col, _bg = koala(DATA / "nimi_ilmakuva.kla")
    assert LREC + len(p["lrec"]) <= 0xA000, hex(LREC + len(p["lrec"]))
    assert len(code) <= LCNT - TCODE, len(code)
    mem = np.zeros(0xBF40 - 0x8000, np.uint8)
    mem[0x400:0x400 + 1000] = col
    mem[0x800:0x800 + 1000] = scr
    mem[TCODE - 0x8000:TCODE - 0x8000 + len(code)] = np.frombuffer(code, np.uint8)
    mem[LCNT - 0x8000:LCNT - 0x8000 + 256] = p["lcnt"]
    mem[LREC - 0x8000:LREC - 0x8000 + len(p["lrec"])] = np.frombuffer(p["lrec"], np.uint8)
    mem[0x2000:0x2000 + 8000] = bmp
    return bytes([0x00, 0x80]) + mem.tobytes()


def split3(full: bytes) -> tuple[bytes, bytes, bytes]:
    """title.prg kolmeksi latauksen järjestykseen (yhteensopivuus: avautuminen ei saa riippua
    latauksen kestosta): TITLE $8000-$8fff (ruutu, värien ja ruudun lähteet, TCODE) ja TITLEC $a000-$bf3f
    (ilmakuva) ennen TITLE0:aa, TITLEB $9000- (LCNT, LREC) vasta logon maalaukseen (TITLE0 + 36, TLRDY)."""
    mem = full[2:]
    lend = max(i for i in range(0x1000, 0x2000) if mem[i]) + 1
    return (bytes([0x00, 0x80]) + mem[:0x1000], bytes([0x00, 0x90]) + mem[0x1000:lend],
            bytes([0x00, 0xA0]) + mem[0x2000:])


def prg2(p: dict) -> bytes:
    assert p["tpop"] >= CRANE1_END, hex(p["tpop"])
    return bytes([p["tpop"] & 255, p["tpop"] >> 8]) + p["pops"]


def tables(p: dict) -> str:
    """title_tab.asm: vakiot, rivien siirrokset, spritekaistat (byb: Y ilman vieritystä, bi: laatikot) ja laatikot"""
    boxes = p["boxes"]
    bands = sorted({b["b0"] for b in boxes})
    order = sorted(range(len(boxes)), key=lambda i: (boxes[i]["b0"], boxes[i]["n"]))
    byb = [47 + 8 * b0 for b0 in bands]             # sprite alkaa rivillä Y + 1; bittikartan rivi 0 rivillä 48 + ys
    sevl = [y - 9 for y in byb]                     # tapahtuma (IRQ riviä ennen): edellinen käyttö loppunut, ehtii
    for k, b0 in enumerate(bands):                  # ennen riviä Y (ys = 0); laatikon rivit 16-20 tyhjiä
        for j in range(k):
            if {b["n"] for b in boxes if b["b0"] == bands[j]} & {b["n"] for b in boxes if b["b0"] == b0}:
                assert byb[j] + 3 + 16 < sevl[k] - 1, (bands[j], b0)
        assert sevl[k] - 1 + 8 <= byb[k] and (k == 0 or sevl[k] > sevl[k - 1])
    bi = [0]
    for b0 in bands:
        bi.append(bi[-1] + sum(1 for b in boxes if b["b0"] == b0))
    ob = [boxes[i] for i in order]
    mask = 0
    for b in boxes:
        mask |= 1 << b["n"]

    def row(name, vals):
        return f"{name} .byte {', '.join(str(v) for v in vals)}\n" if vals else f"{name}\n"
    return ("; generoitu: tools/gfx/logo/title.py\n"
            f"TLROW = {LR}\nAEND = {AEND}\nLBUD = {LBUD}\nSPR = ${SPR:04x}\nTLCNT = ${LCNT:04x}\nTLREC = ${LREC:04x}\n"
            f"TPOP = ${p['tpop']:04x}\nNPOP = {len(POPS)}\nNBAND = {len(bands)}\nSMASK = {mask}\n"
            f"SYELLOW = {YELLOW}\nSLRED = {LRED}\n"
            + row("popkl", [k & 255 for k in POPS]) + row("popkh", [k >> 8 for k in POPS]) + row("rlo", [(r * 40) & 255 for r in range(25)])
            + row("rhi", [(r * 40) >> 8 for r in range(25)]) + row("cx5", [(2 * m) % 5 for m in range(5)])
            + f"SEVL = [{', '.join(str(v) for v in sevl)}]\n" + row("byb", byb) + row("bi", bi)
            + row("sreg", [2 * b["n"] for b in ob]) + row("snum", [b["n"] for b in ob])
            + row("smsk", [1 << b["n"] for b in ob])
            + row("sxl", [(24 + 8 * b["cx0"]) & 255 for b in ob]) + row("sxh", [(24 + 8 * b["cx0"]) >> 8 for b in ob])
            + row("sptr", [(SPR - 0x8000) // 64 + b["blk"] for b in ob]))


def build(out: Path) -> bytes:
    """title_tab.asm ja title.asm koodiksi (64tass, raaka) -> title.prg:n tavut; title2.prg (lappuset) samaan
    hakemistoon"""
    p = plan()
    (out / "title_tab.asm").write_text(tables(p))
    binp = out / "title_code.bin"
    src = ROOT / "src/proto/logo/title.asm"
    subprocess.run(["64tass", "-C", "-a", "-B", "-q", "-b", "-I", str(out), "-o", str(binp), str(src)], check=True)
    (out / "title2.prg").write_bytes(prg2(p))
    nb = len({b["b0"] for b in p["boxes"]})
    print(f"nimiruutu: logon soluja {len(p['cells'])}, joista spritein {len(p['of'])}; spritejä {len(p['boxes'])} "
          f"{nb} kaistassa; LREC ${LREC:04x}-${LREC + len(p['lrec']) - 1:04x}, title2 ${p['tpop']:04x}-$7fff")
    return prg(p, binp.read_bytes())


if __name__ == "__main__":
    Path(sys.argv[1]).write_bytes(prg(plan()))
