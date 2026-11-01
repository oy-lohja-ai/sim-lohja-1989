"""Kaupungintalon generoitu koodi ja taulut (host tekee vain staattisen datan, liike 6510:llä):

  uv run -q --project tools/concept python src/proto/kaupungintalo/build.py OUT

VARIANT (kaupungintalo kahtena osalevynä): "" = kaupungintalo (näytön lähikuva ja peli, osan
kehys 0 = näytön alku), "ikkuna" = kaupungintalo-ikkuna (kamera-ajo ja huone, johtaja pelaa). "ikkuna-rajaus"
tekee kamera-ajon rajausvaihtoehdon taulut, mutta vaihtoehdon 6510-koodi ei ole mukana.

Lähde tools/gfx/data/kaupungintalo/. Tulos OUT/:
  kt.inc       vakiot (taustat, vierityksen rajat, ajat)
  huone.kla    huoneen Koala, kuvaruudun solut kiinteillä väreillä
  huone_nauhat.asm, huone_piirto.asm   PC:n kuvaruudun piirto: nauhat ja speedcode
  naytto.kla, naytto_peli.kla, naytto.asm   näytön lähikuva, pelin ruutu bittikarttana, kursorin reitti ja
               kuvaruudun laajenemisen solut kehyksittäin
  paat.asm     pään asennot: kopiorutiini per asento (ylä- ja alarivit erikseen, jotta säde ei ohita), data ja
               tapahtumataulu (kehys, asento)
  kadet.asm    johtajan kädet: käsien tilat soluina ja tapahtumataulu (kehys, tila), kt.asm kad_copy
  aukio.kla, kamera_tab.asm, kamera_vak.asm, kamera_d.asm, kamera_gen.asm   kamera-ajon ulkonäkymä, taulut ja
               palkkien lohkolista (kamera.py)
  kooste.kla   kamera-ajon alkukuva (ulkonäkymä aukio.kla, kamera.generoi), KT6 ja KT0
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/concept"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from concept import sprites as spr  # noqa: E402
import kamera  # noqa: E402
DATA = ROOT / "tools/gfx/data/kaupungintalo"
BITMAP, SCREEN = 0x6000, 0x5C00         # huone: VIC-pankki 1
ISKU = 30
IKKUNA_LOPPU = 420                      # kaupungintalo-ikkuna: osan pituus (PITUUS, main asettaa)
# VARIANT -> (kamera.T_END, IKKUNA_LOPPU): ikkunassa kamera-ajo 0-179 ja huone 180-359 (taulu1b:n TAULU2 ja
# kaupungintalon KT3 esiladataan huoneen aikana)
PITUUS = {"": (240, 420), "ikkuna": (180, 360), "ikkuna-rajaus": (240, 420)}
NAYTTO_PITUUS = 120                     # kaupungintalo: näytön lähikuva 0-119, peli 120- (peli_build.py PELI_ALKU)
RUUTU_ASKEL = 3                         # pienoisruutu vierii rivin RUUTU_ASKEL kehyksen välein
N_MOVE = 120                            # kursori kulkee lähikuvan alusta Katastrofit-valikolle (peli kehyksestä 120)
N_KURSORI = ((150, 160), (230, 46))     # sprite-koordinaatit: kuvaruudun keskeltä Katastrofit-valikolle (peli_build.py)


def mc_byte(px: list[int]) -> int:
    b = 0
    for v in px:
        b = (b << 2) | v
    return b


def paat(meta: dict, out: list[str]) -> None:
    cx0, cx1, cy0, cy1 = meta["solut"]
    w, h = cx1 - cx0, cy1 - cy0
    n = len(meta["asennot"])
    size = meta["tavua_asento"]
    assert size == w * h * 10
    split = h // 2 + 1
    out.append(f"PAA_N = {n}")
    for k in range(n):
        base = f"paa{k}"
        out.append(f"paa_copy{k}")
        for rows in (range(0, split), range(split, h)):
            out.append(f"        ldx #{w * 8 - 1}")
            out.append("-")
            for r in rows:
                out.append(f"        lda {base}+{r * w * 8},x")
                out.append(f"        sta ${BITMAP + (cy0 + r) * 320 + cx0 * 8:04x},x")
            out.append("        dex")
            out.append("        bpl -")
        out.append(f"        ldx #{w - 1}")
        out.append("-")
        for r in range(h):
            out.append(f"        lda {base}+{w * h * 8 + r * w},x")
            out.append(f"        sta ${SCREEN + (cy0 + r) * 40 + cx0:04x},x")
            out.append(f"        lda {base}+{w * h * 9 + r * w},x")
            out.append(f"        sta ${0xD800 + (cy0 + r) * 40 + cx0:04x},x")
        out.append("        dex")
        out.append("        bpl -")
        out.append("        rts")
    out.append("paa_lo  .byte " + ", ".join(f"<paa_copy{k}" for k in range(n)))
    out.append("paa_hi  .byte " + ", ".join(f">paa_copy{k}" for k in range(n)))
    for k in range(n):
        out.append(f'paa{k}    .binary "paat.bin", {k * size}, {size}')


def ruutu(nimi: str, meta: dict, kla: bytearray, bitmap: int, step: int, nauhat: list[str], out: list[str],
          inc: list[str]) -> None:
    """Pienoisruutu: nauha pakataan solusarakkeittain (4 MC-px tavuun), ja jokaiselle ruudun sisällä olevalle
    bittikartan tavulle tulee lda <nimi>_nauha_c+r,y / [and, ora] / sta. Y = vierityksen rivi. step 2: vain joka
    toinen rivi (kuvaputken juovat), välirivit tyhjennetään kla:han taustaväriksi kerran."""
    r_meta, cols = meta["ruutu"], meta["ruutu_varit"]
    mask = np.load(DATA / f"{nimi}_ruutu_maski.npy")
    nauha = np.load(DATA / f"{nimi}_ruutu_nauha.npy")[::step]
    slot = {c: k for k, c in enumerate(cols)}
    x0, w, ytop = r_meta["x0"], r_meta["leveys"], r_meta["ylareuna"]
    H = nauha.shape[0]
    cx0, cx1, cy0, cy1 = r_meta["solut"]
    rows_vis = 0
    for cx in range(cx0, cx1):
        col = []
        for r in range(H):
            px = []
            for x in range(cx * 4, cx * 4 + 4):
                i = min(max(x - x0, 0), w - 1)
                px.append(slot[int(nauha[r, i])])
            col.append(mc_byte(px))
        nauhat.append(f"{nimi}_nauha{cx} .byte " + ", ".join(f"${b:02x}" for b in col))
    out.append(f"{nimi}_piirto")
    n = 0
    for cy in range(cy0, cy1):
        for cx in range(cx0, cx1):
            for yy in range(8):
                y = cy * 8 + yy
                inside = mask[y, cx * 4:cx * 4 + 4]
                if not inside.any():
                    continue
                yt = ytop[min(max(cx * 4 + 2 - x0, 0), len(ytop) - 1)]
                r = max(int(round(y - yt)), 0)
                k = 2 + (cy * 40 + cx) * 8 + yy
                m = mc_byte([3 if v else 0 for v in inside])
                if r % step:
                    kla[k] &= ~m & 0xFF                 # juova: tausta (%00)
                    continue
                r //= step
                rows_vis = max(rows_vis, r + 1)
                out.append(f"        lda {nimi}_nauha{cx}+{r},y")
                if not inside.all():
                    out.append(f"        and #${m:02x}")
                    out.append(f"        ora #${kla[k] & (~m & 0xFF):02x}")
                out.append(f"        sta ${bitmap + (cy * 40 + cx) * 8 + yy:04x}")
                n += 1
    out.append("        rts")
    inc.append(f"{nimi.upper()}_MAX = {H - rows_vis}          ; suurin Y (nauhan rivit {H}, näkyvissä {rows_vis}, tavuja {n})")


def sprite_bytes(img: np.ndarray) -> bytes:
    """Hires-sprite 24 x 21 (img >= 0 = pikseli) -> 64 tavua."""
    b = bytearray(64)
    for y in range(min(21, img.shape[0])):
        for x in range(min(24, img.shape[1])):
            if img[y, x] >= 0:
                b[y * 3 + x // 8] |= 0x80 >> (x % 8)
    return bytes(b)


def spritet(out: list[str]) -> None:
    """Näytön lähikuvan spritet: kaupunginjohtajakursori (täyttö, reuna) ja sen reitti (smoothstep)."""
    edge, fill = spr.mayor_cursor()
    for name, img in (("spr_fill", fill), ("spr_edge", edge)):
        out.append(f"{name} .byte " + ", ".join(f"${v:02x}" for v in sprite_bytes(img)))
    out.append("spr_col .byte 1, 0              ; täyttö valkoinen, reuna musta")
    (x0, y0), (x1, y1) = N_KURSORI
    e = [(k / N_MOVE) ** 2 * (3 - 2 * k / N_MOVE) for k in range(N_MOVE + 1)]
    out.append(f"N_MOVE = {N_MOVE}")
    out.append("kur_x .byte " + ", ".join(str(round(x0 + (x1 - x0) * v)) for v in e))
    out.append("kur_y .byte " + ", ".join(str(round(y0 + (y1 - y0) * v)) for v in e))


def paljastus(meta: dict, out: list[str], inc: list[str]) -> None:
    """Kuvaruudun laajeneminen: solut paljastusjärjestyksessä (indeksi 0-999, ala- ja ylätavu) ja kunkin kehyksen
    viimeinen solu (naytto_paljastus.bin, kaupungintalo.json naytto)."""
    raw = (DATA / "naytto_paljastus.bin").read_bytes()
    n = meta["paljastus_soluja"]
    loppu = meta["paljastus_loppu"]
    out.append(f'pal_lo  .binary "naytto_paljastus.bin", 0, {n}')
    out.append(f'pal_hi  .binary "naytto_paljastus.bin", {n}, {n}')
    out.append("pal_end_lo .byte " + ", ".join(f"<{v}" for v in loppu))
    out.append("pal_end_hi .byte " + ", ".join(f">{v}" for v in loppu))
    inc.append(f"PALJASTUS = {meta['paljastus_kehyksia']}")
    assert len(raw) == 2 * n


def kiinnita_varit(kla: bytes, bg: int, cols: list[int], cells: list[int]) -> bytes:
    """Ruudun solut kiinteillä paikoilla (cols[k] = bittipari k), jotta speedcode voi kirjoittaa nauhan tavut
    suoraan. Koalan solukohtainen järjestys koodataan uudelleen."""
    b = bytearray(kla)
    assert cols[0] == bg
    cx0, cx1, cy0, cy1 = cells
    for cy in range(cy0, cy1):
        for cx in range(cx0, cx1):
            k = cy * 40 + cx
            sc, co = b[8002 + k], b[9002 + k] & 15
            old = {0: bg, 1: sc >> 4, 2: sc & 15, 3: co}
            new = {c: i for i, c in enumerate(cols)}
            for yy in range(8):
                v = b[2 + k * 8 + yy]
                px = [(v >> (6 - 2 * i)) & 3 for i in range(4)]
                b[2 + k * 8 + yy] = mc_byte([new[old[q]] for q in px])
            b[8002 + k] = (cols[1] << 4) | cols[2]
            b[9002 + k] = cols[3]
    return bytes(b)


def tapahtumat(n_pose: int) -> list[tuple[int, int]]:
    """Pään liike iskuihin: nyökkäys joka iskulla, toisella puoliskolla nojaa näyttöä kohti, lopussa nojaa
    taakse tyytyväisenä. Kopio ei saa osua vierityksen kehykseen (f % RUUTU_ASKEL == 0). Kamera-ajon aikana
    (ennen kamera.T_END) pää pysyy alkuasennossa: kooste on kopioinut huoneen solut, eikä niitä päivitetä."""
    ev = []
    beats = IKKUNA_LOPPU // ISKU
    for b in range(beats):
        f = b * ISKU
        if b < beats // 2:
            seq = [(0, 1), (6, 2), (14, 0)]
        elif b < beats - 1:
            seq = [(0, 4), (6, 5), (14, 1)]
        else:
            seq = [(0, 0), (8, 3)]
        for dt, p in seq:
            g = f + dt
            if g % RUUTU_ASKEL == 0:
                g += 1
            if g >= kamera.T_END:
                ev.append((g, min(p, n_pose - 1)))
    return ev


KADET_TAKA = ("perus", "naputus_a", "naputus_b", "naputus_ab")     # takakäsi näppäilee
KADET_ETU = ("perus", "klikkaus", "hiiri_vasen")                     # etukäsi hiirellä
# käsien iskut (kehys iskun alusta, käsi 0 taka / 1 etu, asento; kadet.json "tahti"): näppäily, näppäily ja hiiren
# nykäisy, hiiren liike edestakaisin, klikkaus iskulle ja näppäily jatkuu
NAPPAILY = [(2, 0, 1), (7, 0, 2), (12, 0, 1), (17, 0, 3), (22, 0, 2), (27, 0, 1)]
NYKAISY = [(2, 0, 2), (7, 0, 1), (10, 1, 2), (12, 0, 3), (17, 0, 2), (22, 1, 0), (24, 0, 1), (28, 0, 0)]
HIIRI = [(3, 1, 2), (9, 1, 0), (15, 1, 2), (21, 1, 0), (26, 1, 2)]
KLIKKAUS = [(0, 1, 1), (6, 1, 0), (9, 0, 1), (14, 0, 2), (19, 0, 3), (24, 0, 1), (29, 0, 0)]
KADET_KULKU = (NAPPAILY, NYKAISY, HIIRI, KLIKKAUS, NAPPAILY, NYKAISY)     # huoneen iskut kamera.T_END - IKKUNA_LOPPU


def kadet(kla: bytes, varattu: set[int], out: list[str]) -> list[tuple[int, int, int]]:
    """Johtajan kädet huoneessa (kamera.T_END - IKKUNA_LOPPU): asennot bittikarttasoluina (kadet.bin, kadet.json:
    huone.kla:n soluvärit ja bittiparit, ruutu ja värit ennallaan). Tila = käden kaikkien solujen tavut; tapahtuma
    kopioi yhden käden tilan. Kehykset KADET_KULKU:sta, siirrettynä pois vierityksen ja pään kopion kehyksistä
    (varattu). kt.asm kad_copy. Palauttaa tapahtumat (kehys, käsi, asento)."""
    meta = json.loads((DATA / "kadet.json").read_text())["asennot"]
    blob = (DATA / "kadet.bin").read_bytes()
    orig = (DATA / "huone.kla").read_bytes()
    kadet_solut = []
    for nimet in (KADET_TAKA, KADET_ETU):
        kadet_solut.append(sorted({c for n in nimet for c in meta[n]["solut"]}))
    assert not set(kadet_solut[0]) & set(kadet_solut[1])
    solut = kadet_solut[0] + kadet_solut[1]
    for c in solut:      # kadet.bin on huone.kla:n bittipareina: build ei saa koodata näitä soluja uudelleen
        assert kla[8002 + c] == orig[8002 + c] and kla[9002 + c] == orig[9002 + c], c
    out.append("; generoitu: build.py kadet() (tools/gfx/data/kaupungintalo/kadet.bin, kadet.json)")
    out.append("kad_dlo .byte " + ", ".join(f"<${BITMAP + (c // 40) * 320 + (c % 40) * 8 - 8 * i:04x}"
                                            for i, c in enumerate(solut)))
    out.append("kad_dhi .byte " + ", ".join(f">${BITMAP + (c // 40) * 320 + (c % 40) * 8 - 8 * i:04x}"
                                            for i, c in enumerate(solut)))
    tilat, i0 = [], 0
    for kasi, nimet in enumerate((KADET_TAKA, KADET_ETU)):
        ks = kadet_solut[kasi]
        for nimi in nimet:
            a = meta[nimi]
            data = []
            for c in ks:
                if c in a["solut"]:
                    o = a["offset"] + 8 * a["solut"].index(c)
                    data += list(blob[o:o + 8])
                else:
                    data += list(kla[2 + 8 * c:10 + 8 * c])
            tilat.append((nimi, i0, i0 + len(ks), data))
        i0 += len(ks)
    for k, (nimi, a, _b, data) in enumerate(tilat):
        out.append(f"kad_t{k}  .byte " + ", ".join(f"${v:02x}" for v in data) + f"    ; {nimi}")
    out.append("kad_slo .byte " + ", ".join(f"<(kad_t{k} - {8 * a})" for k, (_n, a, _b, _d) in enumerate(tilat)))
    out.append("kad_shi .byte " + ", ".join(f">(kad_t{k} - {8 * a})" for k, (_n, a, _b, _d) in enumerate(tilat)))
    out.append("kad_c0  .byte " + ", ".join(str(a) for _n, a, _b, _d in tilat))
    out.append("kad_y0  .byte " + ", ".join(str(8 * a) for _n, a, _b, _d in tilat))
    out.append("kad_y1  .byte " + ", ".join(str(8 * b) for _n, _a, b, _d in tilat))
    ev, edell = [], kamera.T_END
    for isku, kulku in enumerate(KADET_KULKU[:(IKKUNA_LOPPU - kamera.T_END) // ISKU]):
        for dt, kasi, asento in kulku:
            f = max(kamera.T_END + isku * ISKU + dt, edell + 1)
            while f in varattu or f % RUUTU_ASKEL == 0:
                f += 1
            assert f < IKKUNA_LOPPU, f
            ev.append((f, kasi, asento))
            edell = f
    tila = [k * len(KADET_TAKA) + a for f, k, a in ev]
    out.append("kad_f_lo .byte " + ", ".join(f"<{f}" for f, _k, _a in ev) + ", $ff")
    out.append("kad_f_hi .byte " + ", ".join(f">{f}" for f, _k, _a in ev) + ", $ff")
    out.append("kad_s   .byte " + ", ".join(map(str, tila)))
    return ev


def main() -> None:
    global IKKUNA_LOPPU
    out_dir = Path(sys.argv[1])
    variant = sys.argv[2] if len(sys.argv) > 2 else ""
    kamera.T_END, IKKUNA_LOPPU = PITUUS[variant]
    ikkuna = variant.startswith("ikkuna")
    out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads((DATA / "kaupungintalo.json").read_text())
    pc_z0 = (IKKUNA_LOPPU - kamera.T_END) // RUUTU_ASKEL     # PC:n kuvaruutu kamera-ajon ajan, vierii huoneessa riviin 0
    inc = [f"; generoitu: src/proto/kaupungintalo/build.py ({DATA.relative_to(ROOT)})",
           f"ISKU = {ISKU}", f"RUUTU_ASKEL = {RUUTU_ASKEL}", f"KT_IKKUNA = {int(ikkuna)}",
           f"HUONE_LOPPU = {IKKUNA_LOPPU if ikkuna else 0}", f"NAYTTO_LOPPU = {NAYTTO_PITUUS}", f"KAM_PC_Z0 = {pc_z0}"]
    meta = data["huone"]
    kla = bytearray(kiinnita_varit((DATA / "huone.kla").read_bytes(), meta["tausta"], meta["ruutu_varit"],
                                   meta["ruutu"]["solut"]))
    rt, na = [], []
    ruutu("huone", meta, kla, BITMAP, 1, na, rt, inc)
    (out_dir / "huone.kla").write_bytes(kla)
    (out_dir / "huone_nauhat.asm").write_text("\n".join(na) + "\n")
    (out_dir / "huone_piirto.asm").write_text("\n".join(rt) + "\n")
    inc.append(f"HUONE_BG = {meta['tausta']}")
    nm = data["naytto"]
    inc.append(f"NAYTTO_BG = {nm['tausta']}")
    for f in ("naytto.kla", "naytto_peli.kla", "naytto_paljastus.bin", "aukio.kla"):
        shutil.copy(DATA / f, out_dir / f)
    nt = []
    spritet(nt)
    paljastus(nm, nt, inc)
    (out_dir / "paat.bin").write_bytes((DATA / "paat.bin").read_bytes())
    meta = data["huone"]
    paa = []
    paat(meta["paat"], paa)
    ev = tapahtumat(len(meta["paat"]["asennot"]))
    ev.append((0xFFFF, 0))
    paa.append("ev_f_lo .byte " + ", ".join(f"<{f}" for f, _ in ev))
    paa.append("ev_f_hi .byte " + ", ".join(f">{f}" for f, _ in ev))
    paa.append("ev_pose .byte " + ", ".join(str(p) for _, p in ev))
    kad = []
    kadet(kla, {f for f, _ in ev}, kad)
    (out_dir / "kadet.asm").write_text("\n".join(kad) + "\n")
    tab, vak, dtab, gen, ra = [], [], [], [], []
    g = kamera.generoi(DATA, tab, vak, dtab, gen, inc, ra,
                       "rajaus" if variant.endswith("rajaus") else "")
    (out_dir / "kooste.kla").write_bytes(g["kooste"])                       # koosteen alkukuva (KT6, KT0)
    for f, rivit in (("kamera_tab.asm", tab), ("kamera_vak.asm", vak), ("kamera_d.asm", dtab), ("kamera_gen.asm", gen),
                     ("kamera_ra.asm", ra)):
        (out_dir / f).write_text("\n".join(rivit) + "\n")
    (out_dir / "kt.inc").write_text("\n".join(inc) + "\n")
    (out_dir / "paat.asm").write_text("\n".join(paa) + "\n")
    (out_dir / "naytto.asm").write_text("\n".join(nt) + "\n")


if __name__ == "__main__":
    main()
