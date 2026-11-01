"""Mykkäelokuvan kerrontataulu (src/lib/taulu.asm): host tekee vain staattisen datan, 6510 tekee esiin kirjoittumisen,
välkkeen, naarmut ja pölyn reaaliajassa.

  uv run -q --project tools/concept python -I tools/gfx/taulu.py OUT NIMI (--teksti "RIVI 1|RIVI 2" | --taulu N)
      [--kesto 240] [--koko 17] [--fontti tools/gfx/data/taulu/Cinzel.ttf] [--kulma tools/gfx/data/taulu/kulma.png]
      [--glue] [--pankki 2|3] [--merkki AJO [--lataus OSOITE]]

--taulu N lukee tekstin tekstit.yaml:n taulut-kohdasta, avain N (uusi taulu = rivi sinne).
Teksti rivitetään |-merkeistä tai tasapainotetusti automaattisesti. Tulos OUT/:
  taulu_NIMI.bin    hires-bittikartta 8000 t (musta tausta, valkoinen piirto; värit tulevat ruudusta)
  taulu_NIMI.inc    vakiot ja taulut: kehyksen solut, tekstin solut esiin kirjoittumisjärjestyksessä alkukehyksineen,
                    spritet (naarmu, pölyhiukkaset)
  taulu_NIMI_chr.bin, taulu_NIMI_scr.bin
                    sama kuva merkkitilana (src/proto/taulu MERKKI): solujen merkistö (tyhjä solu = 0, enintään 256)
                    ja ruudun merkkikoodit; värit värimuistiin, tausta $d021 musta, joten kuva on pikselilleen sama
  taulu_NIMI.png    esikatselu
  NIMI_glue.asm     (--glue) osalevyn kohtaustaulu: make part P=tauluN (src/proto/taulu)

Kirjasin: Cinzel (SIL Open Font License 1.1, tools/gfx/data/taulu/OFL-Cinzel.txt). Kulmakoriste: kulma.png (1-bittinen,
vasen yläkulma, peilataan).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "tools/gfx/data/taulu"
W, H = 320, 200
REUNA = 10                  # kehyksen viiva näin monta px ruudun reunasta
NOUSU = 8                   # kehyksiä, joissa solu valottuu mustasta valkoiseksi (4 askelta)


def kehys(img: np.ndarray, kulma: np.ndarray) -> None:
    """Ohut kaksoiskehys ja kulmakoriste. Kulman oma viiva (rivi 0 ja sarake 0) osuu
    ulkoviivaan; sisempi viiva alkaa vasta koristeen jälkeen, ettei se risteä kiemuroiden kanssa."""
    r = REUNA
    kh, kw = kulma.shape
    img[r, r:W - r] = True
    img[H - 1 - r, r:W - r] = True
    img[r:H - r, r] = True
    img[r:H - r, W - 1 - r] = True
    img[r + 3, r + kw:W - r - kw] = True
    img[H - 4 - r, r + kw:W - r - kw] = True
    img[r + kh:H - r - kh, r + 3] = True
    img[r + kh:H - r - kh, W - 4 - r] = True
    for flip_x in (False, True):
        for flip_y in (False, True):
            k = kulma[:, ::-1] if flip_x else kulma
            k = k[::-1] if flip_y else k
            x0 = W - r - kw if flip_x else r
            y0 = H - r - kh if flip_y else r
            img[y0:y0 + kh, x0:x0 + kw] |= k


def _sanat(osa: str) -> list[str]:
    """Rivityksen yksiköt: yhdysmerkillä alkava sana ("PC -TIETOKONE") liimataan edelliseen."""
    sanat = []
    for s in osa.split():
        if s.startswith("-") and sanat:
            sanat[-1] += "\u00a0" + s
        else:
            sanat.append(s)
    return sanat


def rivita(teksti: str, font: ImageFont.FreeTypeFont, leveys: int) -> list[str] | None:
    """Kaunis rivitys: |-merkit pakottavat rivinvaihdon; muuten rivit tasapainotetaan (pienin neliöllinen
    vajaus, viimeinen rivi mukaan lukien), eikä kahden lyhyen sanan väliin katkaista (IBM PC pysyy yhdessä)."""
    rivit = []
    for osa in teksti.split("|"):
        w = _sanat(osa)
        n = len(w)
        best = [0.0] + [math.inf] * n
        prev = [0] * (n + 1)
        for j in range(1, n + 1):
            for i in range(j):
                rivi = " ".join(w[i:j])
                L = font.getlength(rivi.replace("\u00a0", " "))
                if L > leveys and j - i > 1:
                    continue
                if j < n and len(w[j - 1].replace("\u00a0", " ").split()[-1]) <= 3 and len(w[j].split("\u00a0")[0]) <= 3:
                    continue                            # kahden lyhyen sanan väliin ei katkaista (IBM | PC)
                cost = best[i] + (leveys - L) ** 2
                if cost < best[j]:
                    best[j], prev[j] = cost, i
        if best[n] == math.inf:
            return None
        cut, j = [], n
        while j > 0:
            cut.append((prev[j], j))
            j = prev[j]
        rivit += [" ".join(w[a:b]).replace("\u00a0", " ") for a, b in reversed(cut)]
    return rivit


def taulun_teksti(n: str) -> str:
    """tekstit.yaml, avain taulut: taulun n teksti sellaisenaan."""
    sys.path.insert(0, str(ROOT / "tools"))
    import tekstit
    taulut = tekstit.lue("taulut")
    if n not in taulut:
        raise SystemExit(f"tekstit.yaml: kerrontataulua {n} ei ole (taulut: {', '.join(taulut)})")
    return taulut[n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("nimi")
    ap.add_argument("--teksti", help="teksti (| = rivinvaihto); puuttuessa --taulu")
    ap.add_argument("--taulu", help="taulun tunnus (1, 1b, 2, ...) tekstit.yaml:n taulut-kohdasta")
    ap.add_argument("--glue", action="store_true", help="kirjoita osalevyn kohtaustaulu OUT/NIMI_glue.asm")
    ap.add_argument("--pankki", type=int, default=2, choices=[2, 3],
                    help="VIC-pankki (src/proto/taulu/taulu.asm PANKKI; 3: bittikartta omana tiedostonaan taulub)")
    ap.add_argument("--merkki", default="", help="merkkitila: taulun 8 kt:n lohko (heksana, esim. a000; glue)")
    ap.add_argument("--lataus", default="", help="merkkitilan tiedoston latausosoite, jos eri (taulu_init kopioi)")
    ap.add_argument("--p3", default="", help="PANKKI 3: koodin ja bittikartan latausosoitteet KOODI,BITTI (heksana; taulu_init kopioi; glue)")
    ap.add_argument("--kesto", type=int, default=240)
    ap.add_argument("--koko", type=int, default=0, help="kirjasimen koko (0 = suurin, jolla teksti mahtuu)")
    ap.add_argument("--paino", type=int, default=700)
    ap.add_argument("--fontti", default=str(DATA / "Cinzel.ttf"))
    ap.add_argument("--kulma", default=str(DATA / "kulma.png"))
    ap.add_argument("--alku", type=int, default=24, help="ensimmäisen kirjaimen kehys")
    ap.add_argument("--loppu", type=int, default=0, help="viimeinen kirjain valmis (0 = 60 %% kestosta)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    teksti_in = a.teksti if a.teksti is not None else taulun_teksti(a.taulu)

    def fontti(koko):
        f = ImageFont.truetype(a.fontti, koko)
        try:
            f.set_variation_by_axes([a.paino])
        except OSError:
            pass
        return f
    leveys = W - 2 * REUNA - 24

    def uniikit(bits):
        """Eri 8x8-solukuviot (tyhjä mukaan): merkkitilan merkistön koko."""
        return {bits[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8].tobytes() for cy in range(25) for cx in range(40)} | {bytes(64)}

    def piirra(koko):
        """Teksti kokoa koko: (rivit, bittikuva, kirjaimet (rivi, x0, x1, y), riviväli) tai None, jos ei mahdu."""
        font = fontti(koko)
        rivit = rivita(teksti_in, font, leveys)
        if rivit is None:
            return None
        vali = int(koko * 1.45)
        asc, _ = font.getmetrics()
        korkeus = vali * (len(rivit) - 1) + asc
        if any(font.getlength(r) > leveys for r in rivit) or korkeus > H - 2 * REUNA - 40:
            return None
        y0 = (H - korkeus) // 2
        teksti = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(teksti)
        kirjaimet = []
        for i, r in enumerate(rivit):
            x = (W - font.getlength(r)) / 2
            y = y0 + i * vali
            d.text((x, y), r, font=font, fill=255)
            for k, ch in enumerate(r):
                if ch != " ":
                    _, t, _, b = font.getbbox(ch)          # kirjaimen oma korkeus (ääkkösten pisteet mukaan)
                    kirjaimet.append((i, x + font.getlength(r[:k]), x + font.getlength(r[:k + 1]), y + t, y + b))
        tbit = np.asarray(teksti) > 110
        if tbit.reshape(25, 8, 40, 8).any((1, 3)).sum() > 256:
            return None                                 # tekstin soluja enintään 256 (taulu.asm 8-bittinen)
        if len(uniikit(tbit | kbit)) > 256:
            return None                                 # merkkitilan merkistö: eri solukuvioita enintään 256
        return rivit, tbit, kirjaimet, vali
    kulma = np.asarray(Image.open(a.kulma).convert("1"), bool)
    kbit = np.zeros((H, W), bool)
    kehys(kbit, kulma)
    for koko in ([a.koko] if a.koko else range(28, 11, -1)):
        r = piirra(koko)
        if r:
            break
    assert r, "teksti ei mahdu tauluun"
    rivit, tbit, kirjaimet, vali = r
    a.koko = koko
    img = tbit | kbit
    # solut: kehyksen solut (näkyvät alusta) ja tekstin solut kirjoitusjärjestyksessä (kirjain, jonka keskikohta)
    cells_t = (tbit.reshape(25, 8, 40, 8).any((1, 3)))
    cells_k = (kbit.reshape(25, 8, 40, 8).any((1, 3))) & ~cells_t
    loppu = a.loppu or int(a.kesto * 0.6)
    n_k = len(kirjaimet)
    alku = {}
    for j, (rivi, xa, xb, yt, yb) in enumerate(kirjaimet):
        f = a.alku + (loppu - NOUSU - a.alku) * j / max(n_k - 1, 1)
        for cx in range(int(xa) // 8, int(math.ceil(xb)) // 8 + 1):
            for cy in range(int(yt) // 8, min(25, int(yb) // 8 + 1)):
                if 0 <= cx < 40 and cells_t[cy, cx] and (cy, cx) not in alku:
                    alku[(cy, cx)] = int(f)
    for cy, cx in zip(*np.nonzero(cells_t)):           # kirjaimen ulkopuolelle jääneet (yläviivat) lähimmän mukaan
        if (cy, cx) not in alku:
            # lähin kirjain; tasatilanteessa myöhempi (ääkkösten pisteet kuuluvat alemman rivin kirjaimeen)
            alku[(int(cy), int(cx))] = -min((abs(c - cx) + 3 * abs(r - cy), -f) for (r, c), f in alku.items())[1]
    teksti_solut = sorted((f, cy * 40 + cx) for (cy, cx), f in alku.items())
    kehys_solut = [int(cy) * 40 + int(cx) for cy, cx in zip(*np.nonzero(cells_k))]
    assert len(teksti_solut) <= 256 and len(kehys_solut) <= 256, (len(teksti_solut), len(kehys_solut))
    # hires-bittikartta
    bmp = bytearray(8000)
    for cy in range(25):
        for cx in range(40):
            for yy in range(8):
                v = 0
                for xx in range(8):
                    v = (v << 1) | int(img[cy * 8 + yy, cx * 8 + xx])
                bmp[(cy * 40 + cx) * 8 + yy] = v
    (out / f"taulu_{a.nimi}.bin").write_bytes(bytes(bmp))
    # merkkitila: solujen merkistö (tyhjä = 0) ja ruudun koodit
    merkit = {bytes(8): 0}
    scr = bytes(merkit.setdefault(bytes(bmp[c * 8:c * 8 + 8]), len(merkit)) for c in range(1000))
    assert len(merkit) <= 256, f"taulun soluja {len(merkit)} > 256: merkkitila ei mahdu yhteen merkistöön"
    (out / f"taulu_{a.nimi}_chr.bin").write_bytes(b"".join(merkit))
    (out / f"taulu_{a.nimi}_scr.bin").write_bytes(scr)
    # spritet: naarmu (1 px pystyviiva koko spriten korkeudelta) ja kolme pölyhiukkasta
    def spr(rows):
        b = bytearray(64)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    b[y * 3 + x // 8] |= 0x80 >> (x % 8)
        return bytes(b)
    naarmu = spr(["#" if y % 9 != 4 else "" for y in range(21)])
    poly = [spr(["", "", " ##", "###", " #"]), spr(["", "", "", " #", "##"]), spr(["", " #", "  #", "  ##", "   #"])]
    L = [f"; generoitu: tools/gfx/taulu.py {a.nimi} ({len(rivit)} riviä, kirjasin {Path(a.fontti).name})",
         f"; rivit: {' | '.join(rivit)}",
         f'TAULU_BIN = "taulu_{a.nimi}.bin"',
         f'TAULU_CHR = "taulu_{a.nimi}_chr.bin"', f'TAULU_SCR = "taulu_{a.nimi}_scr.bin"',
         f"TAULU_KESTO = {a.kesto}", f"TAULU_NOUSU = {NOUSU}",
         f"TAULU_NT = {len(teksti_solut)}", f"TAULU_NK = {len(kehys_solut)}"]
    tab = [("taulu_t_lo", [c & 255 for _, c in teksti_solut]), ("taulu_t_hi", [c >> 8 for _, c in teksti_solut]),
           ("taulu_t_f", [f for f, _ in teksti_solut]),
           ("taulu_k_lo", [c & 255 for c in kehys_solut]), ("taulu_k_hi", [c >> 8 for c in kehys_solut])]
    data = [f"{n} .byte " + ", ".join(str(v) for v in vals) for n, vals in tab]
    data.append("taulu_spr .byte " + ", ".join(f"${v:02x}" for v in naarmu + b"".join(poly)))
    (out / f"taulu_{a.nimi}.inc").write_text("\n".join(L) + "\n")
    (out / f"taulu_{a.nimi}_data.asm").write_text("\n".join(data) + "\n")
    prev = np.where(img, 255, 0).astype(np.uint8)
    Image.fromarray(prev).resize((W * 2, H * 2), Image.NEAREST).save(out / f"taulu_{a.nimi}.png")
    if a.glue:
        (out / f"{a.nimi}_glue.asm").write_text("\n".join([
            f"; generoitu: tools/gfx/taulu.py ({'tekstit.yaml taulu ' + str(a.taulu) if a.taulu else 'teksti'})"
            f": {' / '.join(rivit)}",
            "SCENE_START = 0", f"SCENE_END = {a.kesto}",
            '        .include "syms.inc"',
            *([f"        #S_LOAD f_taulu                 ; ${a.lataus or a.merkki}-: merkistö, ruutu, koodi ja taulut "
               f"(src/proto/taulu MERKKI ${a.merkki})"] if a.merkki else
              ["        #S_LOAD f_taulu                 ; $9800-$bf3f: koodi, taulut ja bittikartta (src/proto/taulu)"]
              if a.pankki == 2 else
              [f"        #S_LOAD f_taulub                ; ${a.p3.split(',')[1] if a.p3 else 'e000'}-: bittikartta (src/proto/taulu, PANKKI 3"
               + (", taulu_init kopioi $e000:aan)" if a.p3 else ")"),
               f"        #S_LOAD f_taulu                 ; ${a.p3.split(',')[0] if a.p3 else 'c100'}-: koodi ja taulut "
               + ("(taulu_init kopioi $c100:aan; ruutu $cc00, spritet $c000)" if a.p3 else "(ruutu $cc00, spritet $c000)")]),
            "        #S_CALL taulu_init",
            *(["        #S_SHOW taulu_show              ; kopio ajoalueelle ennen kelloa (jatkuvassa saumassa taulu_go)"]
              if a.merkki and a.lataus and a.lataus != a.merkki else []),
            "        #S_START SCENE_START", "        #S_CALL taulu_go",
            *([f"        #S_FREE f_taulu                 ; kopioitu ${a.merkki}:een: latausalue vapaa"]
              if a.merkki and a.lataus and a.lataus != a.merkki else []),
            *(["        #S_FREE f_taulu                 ; kopioitu: latausalue vapaa"] if a.p3 else []),
            *(["        #S_FREE f_taulub"] if a.p3 and a.p3.split(",")[1].lower() != "e000" else []), ""]))
    print(f"taulu {a.nimi}: {' / '.join(rivit)}; tekstin soluja {len(teksti_solut)}, kehyksen {len(kehys_solut)}")


if __name__ == "__main__":
    main()
