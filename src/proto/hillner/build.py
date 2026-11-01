"""Hillner-kameranajon (crane down) staattinen data: kuva riveittäin, etualan spritet, liikekäyrä, musiikki.

  uv run --project tools/concept python src/proto/hillner/build.py build/hilint --integrated

Kuva: tools/gfx/data/hillner/korkea2/ (kuva.npy 160 x H MC-indeksit, kerros.npy taivas = 255,
katuvalo_v4.npy, ajo.json). MC-bittikartta, $D021 = 0 paitsi taivasriveillä. Jokainen merkkirivi on 400 tavun
tietue [bittikartta 320 | ruutu 40 | väri 40], tietueet sijoitetaan vapaisiin muistialueisiin ja niihin
osoitetaan rivitaululla.

Spritet vuorollaan: taustarivistö (0-4, talot ja kirkko), pääskyset (0-2) ja katuvalo (0-6, 1,5 x julkisivu,
loppukuvassa leivottuna).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/gfx"))
sys.path.insert(0, str(ROOT / "tools/concept"))

from c64fmt import _lab_dist  # noqa: E402

# Kuva-aineisto: kamera-ajon kuva, taivas, kirkko, katuvalo ja otsikko; --aineisto NIMI (tools/gfx/data/NIMI) valitsee
# vaihtoehtoisen datan samalla koodilla
AJO_MAIN = ROOT / "tools/gfx/data/hillner/korkea2"
AJO = ROOT / "tools/gfx/data" / (sys.argv[sys.argv.index("--aineisto") + 1] if "--aineisto" in sys.argv
                                 else "hillner/korkea2")


def ajo(name: str) -> Path:
    """Kamera-ajon datatiedosto aineistosta, tai pääversion korkea2:sta, jos aineistossa ei ole sitä (ei kopioita)."""
    return AJO / name if (AJO / name).exists() else AJO_MAIN / name


META = json.loads(ajo("ajo.json").read_text())
LOHJA = ROOT / "build/kyltti-ajo/mod/lohja_text.npy"      # kyltti-greets: ajo-kyltin LOHJAN RAUTA (MC, loppurajaus)
KAISTA = ROOT / "build/kyltti-ajo/mod/kaista.json"        # samasta buildista: kyltin kaista loppurajauksessa
SWALLOWS = [ROOT / f"tools/gfx/data/hillner/paaskynen-{i}.npy" for i in range(3)]
OTSIKKO = ajo("otsikko.npy")                             # HILLNERIN KAUPPATALO kuvamallilla (MC kuvan
                                                          # koordinaateissa, 255 läpinäkyvä)
OT_ROW = None                 # otsikon ylin kuvan rivi (None = tiedoston paikka eli 74): kokonaan ruudussa kehyksestä 14
                              # vähintään 150 kehystä vaatii ppx <= ylin rivi kehyksellä 164
KATUVALO = ajo("katuvalo_v4.npy")                        # katuvalo omana kerroksena (loppurajauksen koordinaatit,
                                                          # pylväs x 56-59, lyhty vasemmalla x 44-55)
MSTART = 2880                 # biisin kehys kellon alussa (Hillner, purkupallo: K1 A t5)

WIN_ROWS = 18                 # ikkuna 320 x 144 (rivit 72-215)
CMAX = 6                      # linecrunch-rivejä per pankkiasettelu (6 + 18 + 1 = 25 riviä = 1000 solua)
BANK_ROWS = 25
REC = 400
SPR_BASE = 0x0400             # spritelohkot pankin sisällä (molemmissa pankeissa samat)
N_BLOCKS = 5                  # taustarivistö (5); pääskyset ja katuvalo kopioidaan samoihin lohkoihin vuorollaan
# vapaat alueet tietueille: koodi $0801-$21ff, musiikki $4f00-$5bff (soitin + puskuri), ruutu + spritet
# $8000-$8cbf/$c000-$ccbf, bittikartat $a000/$e000
CODE_END = 0x2200
# Loppukuvan rivit (luovutus) sijoitetaan ensimmäisinä, koska pääsilmukka kopioi ne kameran pysähdyttyä.
# Musiikin alue (music.inc: soitin ja purkupuskuri) poistetaan alueista buildissa.
REGIONS = [(CODE_END, 0x4F00), (0x8000 + SPR_BASE + N_BLOCKS * 64, 0x9000), (0x9000, 0xA000),
           (0xC000 + SPR_BASE + N_BLOCKS * 64, 0xD000), (0x5C00, 0x8000)]
# Pääbuildin moduuli: Krill $0200-$0407, integraattori $0408-$07ff, musiikki $0800-$19ff, koodi $1a00-, tietueet
# koodin perästä VIC-pankkien 2 ja 3 ruutujen ja spritejen ulkopuolelle; bittikartat $a000/$e000 ajonaikaisia.
INT_CODE_END = 0x4400
# ajo-kyltti (8 spriteä, Makefile K_BASE/K_END) ladataan, kun viimeinen asettelu näkyy: sen jälkeen luetaan
# tietueista vain luovutuksen rivit (FIN_IMG0 - 1..), joten ne eivät saa olla tällä alueella.
INT_AJO_LO, INT_AJO_END = 0x4400, 0x6400
# Pankissa 2 vasta luovutuskuvan ruudun ($8800-$8bff, INT_FIN_SCR) jälkeen.
INT_REGIONS = [(0xC000 + SPR_BASE + N_BLOCKS * 64, 0xD000), (INT_AJO_END, 0x8000),   # luovutuksen rivit ensin
               (0x8C00, 0xA000), (INT_CODE_END, INT_AJO_END)]
# Luovutus: loppukuva tavallisena MC-bittikarttana VIC-pankkiin 2, joka on lopussa takapankki (viimeinen
# asettelu on pankissa 3). Kuvan rivit merkkiriveille 3-20 (yscroll 0, rivit 72-215 kuten ikkuna).
FIN_BMP, FIN_SCR, FIN_ROW0, FIN_DD00 = 0xA000, 0x8000, 3, 0b01
# pääbuildissa luovutuskuvan ruutu $8800: ajo-kyltin kangas $8000-$86bf (src/scene/kyltti_part.asm). Pankin 2 spritelohkot
# ovat lopussa vapaat, koska viimeinen asettelu (spritet ja leikkauspuskurit) on pankissa 3.
INT_FIN_SCR = 0x8800

HOLD0 = 0                     # pito katolla (kehystä): kamera lähtee heti hiljaa liikkeelle savun tupruttaessa
MOVE = 415                    # laskeutuminen (kamera pysähtyy kehyksellä HOLD0 + MOVE, sitten luovutus)
ACC = 120                     # kiihdytys
DEC = 40                      # jarrutus (lyhyt: ei pitkää hidastumista)
HOLD1 = 110                   # pito kyltissä

TRANSP = 255
# Taustarivistö (kirkon lisäksi muita taloja taustalle):
# 5 MC-spriteä (talot 0-2 X- ja Y-laajennettuina, kirkko 3-4) bittikartan takana, rata
# taustarivisto_rata.json kamera-ajon kohdissa s (8 px:n välein, ruudun rivi, nakyy). Spritet 0-4 ovat ainoat,
# jotka toimivat taivasriveillä. Pääskyset lentävät samoilla spriteillä 0-2 vasta rivistön jälkeen (swallow_plan).
RIVI = json.loads(ajo("taustarivisto_rata.json").read_text())["spritet"]
SW_ROWS = (34, 54, 74)        # pääskysten ruudun rivi lennon puolivälissä (talon edessä katon alla)

# Taivas $D021:ssä rivi riviltä (hillner.asm): kuvan rivit 0..SKY_T-1 ovat taivasrivejä, joilla bittikartan
# läpinäkyvät pikselit (kerros.npy 255, MC 00) näyttävät ruudun rivin taivaan (horisontti pysyy ruudulla paikallaan:
# ajo.json taivas_ruutu). Alempana $D021 = 0.
SKY_T = META["SKY_T"]
SKG_GAP = 8                   # taivassegmentit: värinvaihdot alle näin monen rivin välein samaan segmenttiin


def sky_rows() -> list[int]:
    """Taivas ruudun riveittäin (ikkunan 144 riviä): ajo.json taivas_ruutu."""
    t = [int(v) for v in META["taivas_ruutu"]]
    assert len(t) == WIN_ROWS * 8, len(t)
    return t


def sky_segments() -> list[tuple[int, int]]:
    """Ruudun rivit (alku, loppu poissuljettu), joilla taivaan väri vaihtuu (hillner.asm irq_sky): vaihtorivit
    yhdistettynä, kun väli on alle SKG_GAP riviä. Muilla riveillä $D021 pysyy edellisen rivin värissä."""
    t = sky_rows()
    segs: list[list[int]] = []
    for r in (r for r in range(1, len(t)) if t[r] != t[r - 1]):
        if segs and r - segs[-1][1] < SKG_GAP:
            segs[-1][1] = r + 1
        else:
            segs.append([r, r + 1])
    return [(72 + a, 72 + b) for a, b in segs]


def erase_band(win: np.ndarray) -> None:
    """Kyltin kaista mustaksi loppurajauksessa (kuvan viimeiset 144 riviä): kyltti-greetsin kaista.json,
    sarakkeittain [x, ensimmäinen, viimeinen] mukaan lukien."""
    for x, a, b in json.loads(KAISTA.read_text())["rivit"]:
        win[a:b + 1, x] = 0


def image() -> np.ndarray:
    """Talo indeksikuvana: kuva.npy (ilman katuvaloa, joka on spritekerros: katuvalo()), taivasriveillä
    (0..SKY_T-1) kerros.npy:n taivas 255 ($D021)."""
    img = np.load(ajo("kuva.npy")).astype(np.uint8)
    assert img.shape[1] == 160 and img.shape[0] % 8 == 0 and img.shape[0] == META["korkeus"], img.shape
    assert img.shape[0] - WIN_ROWS * 8 == META["vieritys"] == META["loppurajaus_rivit"][0]
    sky = np.load(ajo("kerros.npy")) == TRANSP
    sky[SKY_T:] = False
    img[sky] = TRANSP
    t = title_layer(img.shape[0])                          # otsikko katon yllä, vierii talon mukana
    img[t != TRANSP] = t[t != TRANSP]
    # Kirkon spritet 3-4 myöhästyttävät taivassilmukan $D021-kirjoitusta niin, että ikkunan ensimmäinen
    # pikseli näyttää edellisen rivin värin (mitattu: tasan 1 hires-px). Taivasrivien
    # vasen MC-pikseli on siksi musta: ikkuna alkaa niillä 2 px myöhemmin mustaa reunaa vasten.
    sky = img[:SKY_T, 0] == TRANSP
    img[:SKY_T, 0][sky] = 0
    # Kyltin teksti (kyltissä lukee LOHJAN RAUTA): maalattu teksti pois kaistalta ja tilalle ajo-kyltin
    # LOHJAN RAUTA samassa paikassa ja muodossa kuin spritet sen näyttävät (kyltti-greets, pylvään oikealla puolella).
    if LOHJA.exists():
        y0 = img.shape[0] - WIN_ROWS * 8                  # loppurajauksen ensimmäinen kuvan rivi
        win = img[y0:]
        erase_band(win)
        t = np.load(LOHJA)
        ink = t != 255
        win[ink] = t[ink]
        # Tekstin solut MC-kelpoisiksi (musta = %00 ja enintään 3 muuta väriä) muuttamalla muita värejä, jotta
        # koodaus ei vaihda tekstin pikseleitä (encode: harvinaisin väri lähimpään).
        for cy, cx in {(y // 8, x // 4) for y, x in zip(*np.nonzero(ink))}:
            cell = win[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
            keep = cell[ink[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]]
            while True:
                vals, cnt = np.unique(cell[cell != 0], return_counts=True)
                if len(vals) <= 3:
                    break
                v = min((c, v) for v, c in zip(vals, cnt) if v not in keep)[1]
                cell[cell == v] = min((u for u in vals if u != v), key=lambda u: _lab_dist(v, u))
    return img


def title_layer(h: int) -> np.ndarray:
    """Otsikko (HILLNERIN KAUPPATALO kuvamallilla hienolla fontilla kahdelle riville) kuvan kokoisena kerroksena
    (TRANSP läpinäkyvä), siirrettynä niin, että ylin rivi on OT_ROW. Sama kerros tallennetaan myös viitteeksi
    (build/hilint/otsikko.npy, koodattuna: kirkon takana encode vaihtaa %01-värin pikselit)."""
    t = np.load(OTSIKKO).astype(np.uint8)
    assert t.shape == (h, 160), t.shape
    if OT_ROW is not None:
        t = np.roll(t, OT_ROW - int(np.nonzero((t != TRANSP).any(1))[0].min()), 0)
    return t


def strip_mask(shape: tuple[int, int]) -> np.ndarray:
    """Kuvan pikselit, joiden kohdalla taustarivistön sprite (bittikartan takana) voi näkyä jossain kamera-ajon
    kohdassa: rata taustarivisto_rata.json (ruudun rivi kohdassa s = ppx, kun nakyy), kuvan rivi = ruudun rivi + s."""
    spr = np.load(ajo("taustarivisto.npy"))
    m = np.zeros(shape, bool)
    for a, sp in zip(spr, RIVI):
        ys, xs = np.nonzero(a)
        fx, fy = 1 + sp["x_laajennus"], 1 + sp["y_laajennus"]
        for t in (t for t in sp["rata"] if t["nakyy"]):
            for s in range(t["s"], t["s"] + 8):
                for dy in range(fy):
                    for dx in range(fx):
                        m[np.clip(ys * fy + dy + t["y"] + s, 0, shape[0] - 1),
                          np.clip(xs * fx + dx + t["x"], 0, 159)] = True
    return m


def encode(img: np.ndarray, behind: np.ndarray | None = None,
           front: np.ndarray | None = None) -> tuple[bytes, bytes, bytes, np.ndarray, int]:
    """MC-bittikartta, jossa $D021 vaihtelee riveittäin: 255 -> %00 (taivasrivit), musta 0 -> %00 vain riveillä
    >= SKY_T ($D021 = 0). Taivasrivin musta tarvitsee solussa oman värin. Yli 3 väriä: harvinaisin lähimpään
    (kuten Bitmap). behind (bool, kuvan kokoinen): pikselit, joiden takana voi olla bittikartan takainen sprite
    (kirkko, $D01B). Sprite näkyy %00- ja %01-pikseleiden läpi, joten niissä soluissa mustakin saa oman värin,
    %01 on väri, jota behind-pikseleissä on vähiten, ja sen behind-pikselit vaihdetaan lähimpään muuhun (alle
    3 värin solussa %01 jää käyttämättä). front (bool): pikselit, joita ei saa muuttaa (otsikko): niiden solussa
    %01 on musta ääriviiva, jonka läpi sprite saa näkyä, eikä värejä vaihdeta. Palauttaa bmp, scr, col,
    näytettävän kuvan (255 säilyy) ja korjattujen solujen määrän."""
    h = img.shape[0]
    bmp, scr, col = bytearray(h * 40), bytearray(h // 8 * 40), bytearray(h // 8 * 40)
    out = img.copy()
    fixes = 0
    sky = np.arange(h) < SKY_T
    for cy in range(h // 8):
        for cx in range(40):
            cell = out[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4]
            srow = sky[cy * 8:cy * 8 + 8, None].repeat(4, 1)
            bm = behind[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4] & (cell != TRANSP) if behind is not None else None
            hide = bm is not None and bm.any()
            if hide:                                       # musta %00 näyttäisi kirkon: oma väri
                srow = srow | bm
            vals, cnt = np.unique(cell[(cell != TRANSP) & ((cell != 0) | srow)], return_counts=True)
            order = [int(v) for v, _ in sorted(zip(vals, cnt), key=lambda t: -t[1])]
            keep = order[:3]
            if len(order) > 3:
                fixes += 1
                bgs = [0] if not srow.any() else []
                for v in order[3:]:
                    near = min(keep + bgs, key=lambda k: _lab_dist(v, k))
                    cell[cell == v] = near
            keep_front = (hide and front is not None and len(keep) == 3 and 0 in keep
                          and front[cy * 8:cy * 8 + 8, cx * 4:cx * 4 + 4].any())
            if keep_front:                                 # otsikko: ääriviiva %01, kirjaimet ennallaan
                keep = [0] + sorted(v for v in keep if v != 0)
                role = {v: k + 1 for k, v in enumerate(keep)}
            elif hide:
                n = {v: int((bm & (cell == v)).sum()) for v in keep}
                keep = sorted(keep, key=lambda v: (n[v], v))
                if len(keep) == 3 and n[keep[0]]:          # %01:n väri rivistön kohdalta lähimpään muuhun
                    near = min(keep[1:], key=lambda k: _lab_dist(keep[0], k))
                    cell[bm & (cell == keep[0])] = near
                if len(keep) < 3:                          # %01 käyttämättä: kirkko näkyy vain taivaan läpi
                    pad = next(v for v in range(1, 16) if v not in keep)
                    keep = [pad] + keep + [pad] * (2 - len(keep))
                role = {v: k + 1 for k, v in enumerate(keep) if v in order[:3]}
            else:
                keep = sorted(keep) + [0] * (3 - len(keep))
                role = {v: k + 1 for k, v in enumerate(keep) if (v != 0 or 0 in order[:3])}
            scr[cy * 40 + cx] = (keep[0] << 4) | keep[1]
            col[cy * 40 + cx] = keep[2]
            for y in range(8):
                b = 0
                for x in range(4):
                    v = int(cell[y, x])
                    b |= role.get(v, 0) << (6 - 2 * x)
                    assert v == TRANSP or v in role or (v == 0 and not srow[y, x]), (cy, cx, y, v)
                bmp[cy * 320 + cx * 8 + y] = b
    return bytes(bmp), bytes(scr), bytes(col), out, fixes


def motion(p_max: int) -> list[int]:
    """Laskeutumisen nopeus kehyksittäin 1/16 px:n tarkkuudella (pos += v): pitkä pehmeä kiihdytys (ACC
    kehystä), tasainen vauhti ja lyhyt jarrutus (DEC kehystä: ei pitkää hidastumista pysähdykseen). Nopeus
    smoothstep-ramppeina, joten kiihtyvyys alkaa ja loppuu nollasta. Pyöristys kertymästä, loppupaikka tarkka."""
    def ss(x: np.ndarray) -> np.ndarray:
        x = np.clip(x, 0.0, 1.0)
        return x * x * (3 - 2 * x)
    t = np.arange(MOVE) + 0.5
    w = ss(t / ACC) * ss((MOVE - t) / DEC)
    s = np.round(np.concatenate([[0], np.cumsum(w)]) / w.sum() * p_max * 16).astype(int)
    v = np.diff(s)
    assert v.max() < 256 and v.min() >= 0
    return [int(x) for x in v]


def music(out: Path) -> list[str]:
    """Demon biisi yhteisellä musiikkimoduulilla: soitin $4f00-$58ff, puskuri $5900-$5bff. Proto aloittaa biisin
    kehyksestä MSTART (Hillnerin kohtaus)."""
    import subprocess
    r = subprocess.run([sys.executable, "-I", str(ROOT / "tools/music/music.py"), "build", str(out), "--addr", "4f00"],
                       capture_output=True, text=True)
    if r.returncode:
        print(r.stdout + r.stderr)
        (out / "music.inc").write_text("HAVE_MUSIC = 0\n")
        return [f"MSTART = {MSTART}"]
    return [f"MSTART = {MSTART}"]


def music_area(out: Path) -> tuple[int, int]:
    """Musiikin muistialue music.inc:stä (soitin MUSIC_LOAD.. ja purkupuskuri ..MUSIC_BUF_END), muuten tyhjä."""
    inc = out / "music.inc"
    if not inc.exists() or "HAVE_MUSIC = 1" not in inc.read_text():
        return 0x10000, 0x10000
    v = {line.split("=")[0].strip(): int(line.split("=")[1].split(";")[0].strip().lstrip("$"), 16)
         for line in inc.read_text().splitlines() if line.startswith("MUSIC_") and "$" in line}
    return min(v["MUSIC_LOAD"], v["MUSIC_BUF"]), max(v["MUSIC_END"], v["MUSIC_BUF_END"])


def mc_block(px: np.ndarray, roles: dict[int, int]) -> bytes:
    """21 x 12 MC-pikseliä (TRANSP = 0) -> 64 tavua; roles: väri -> %01/%10/%11."""
    out = bytearray(64)
    for y in range(min(21, px.shape[0])):
        for x in range(min(12, px.shape[1])):
            v = int(px[y, x])
            if v != TRANSP:
                out[y * 3 + x // 4] |= roles[v] << (6 - 2 * (x % 4))
    return bytes(out)


def sprite_blocks() -> tuple[list[bytes], list[bytes]]:
    """Lohkot 0-4: taustarivistö (roolit 1-3 kuten kirkossa: $d025 = 0, oma, $d026 = 12). Pääskysten 3 siipiasentoa
    erikseen (sw_blk): sprites.asm kopioi ne lohkoihin 0-2, kun rivistö on piilossa."""
    blocks = [mc_block(np.where(a == 0, TRANSP, a), {1: 1, 2: 2, 3: 3}) for a in np.load(ajo("taustarivisto.npy"))]
    assert len(blocks) == N_BLOCKS == len(RIVI), len(blocks)
    sw = []
    for p in SWALLOWS:
        a = np.load(p).astype(np.uint8)
        pad = np.full((21, 12), TRANSP, np.uint8)
        pad[:a.shape[0], :a.shape[1]] = a
        sw.append(mc_block(pad, {0: 1, 12: 3, 11: 3, 15: 3, 1: 3}))
    return blocks, sw


def ppx_series(mv: list[int]) -> list[int]:
    """Kameran kokonaiset pikselit kehyksittäin (hillner.asm: pos += v, ppx = pos >> 4)."""
    out, pos = [], 0
    for v in mv + [0]:
        out.append(pos // 16)
        pos += v
    return out


def strip_last(px: list[int]) -> int:
    """Ensimmäinen kehys, jolla koko taustarivistö on piilossa (indeksi ppx >> 3 jokaisen spriten viimeisen
    näkyvän kohdan jälkeen)."""
    last = max(max(i for i, t in enumerate(sp["rata"]) if t["nakyy"]) for sp in RIVI)
    return next(f for f, p in enumerate(px) if p >> 3 > last)


def swallow_plan(px: list[int], f_pole: int) -> list[tuple[int, int, int, int, int]]:
    """Pääskyset (alkukehys, X hires-px, nopeus 1/16 px/kehys, kuvan rivi, siiven vaihe) rivistön jälkeen ja ennen
    katuvaloa: vuorotellen vasemmalta ja oikealta, nopeus niin, että lento päättyy ennen katuvaloa, kuvan rivi niin,
    että lento on puolivälissään ruudun rivillä SW_ROWS."""
    f0 = strip_last(px) + 1
    out = []
    for i, row in enumerate(SW_ROWS):
        t0 = f0 + 4 * i                  # 4 kehyksen porras: rivistön ja katuvalon väliin jää vähän aikaa
        n = f_pole - 4 - t0
        assert n >= 40, f"pääskysille liian vähän aikaa ({n} kehystä) rivistön ja katuvalon välissä"
        dx = -(-340 * 16 // n)
        assert dx <= 127, f"pääskynen liian nopea ({dx}/16 px/kehys, {n} kehystä)"
        x0, dx = (4, dx) if i % 2 == 0 else (340, -dx)
        mid = t0 + 340 * 16 // abs(dx) // 2
        out.append((t0, x0, dx, row + px[mid], (0, 5, 9)[i]))
        assert 3 <= out[-1][3] < 259, out[-1]
    return out


KV_BOT = 194                  # alimman spriten ensimmäinen rivi (päättyy riville 214)


def katuvalo() -> tuple[list[bytes], dict, np.ndarray]:
    """Katuvalon spritelohkot (pää A, pää B, runko), vakiot ja spritejen näyttämä kerros loppurajauksessa
    (144 x 160, TRANSP läpinäkyvä) leivottavaksi. Kerros on kaksi 12 px:n lohkoa: A on se, jossa runko jatkuu
    (alin rivi), B toinen (lyhty tai varsi, kummalla puolella tahansa). Roolit: %01 = 0 ($D025), %11 = 12 ($D026),
    %10 = lohkon oma väri (muut värit lähimpään)."""
    lay = np.load(KATUVALO).astype(np.uint8)[:WIN_ROWS * 8]
    ys, xs = np.nonzero(lay != TRANSP)
    x0, bot = int(xs.min()), int(ys.max())
    assert xs.max() < x0 + 24, f"katuvalo yli 24 MC px leveä: {x0}-{xs.max()}"
    xa, xb = (x0, x0 + 12) if (lay[bot, x0:x0 + 12] != TRANSP).any() else (x0 + 12, x0)
    a, b = lay[:, xa:xa + 12], lay[:, xb:xb + 12]

    def first_row(px: np.ndarray) -> int:
        return int(np.nonzero((px != TRANSP).any(1))[0].min())
    top, btop = first_row(a), first_row(b)
    rows = [tuple(r) for r in a[top + 21:bot + 1]]
    body = np.array(max(set(rows), key=rows.count), np.uint8)        # rungon yleisin rivi toistuu
    off = sum(r != tuple(body) for r in rows)
    assert not (b[btop + 21:] != TRANSP).any(), "katuvalon pää B yli 21 rivin"

    def roles(px: np.ndarray) -> tuple[dict[int, int], int]:
        vals = [int(v) for v in np.unique(px) if v != TRANSP and v not in (0, 12)]
        own = max(vals, key=lambda v: int((px == v).sum())) if vals else 11
        return {0: 1, 12: 3, **{v: 2 for v in vals}}, own
    ra, ca = roles(a[top:top + 21])
    rb, cb = roles(b[btop:btop + 21])
    body_px = np.repeat(body[None, :], 21, 0)
    rc, cc = roles(body_px)
    blocks = [mc_block(a[top:top + 21], ra), mc_block(b[btop:btop + 21], rb), mc_block(body_px, rc)]
    shown = np.full((WIN_ROWS * 8, 160), TRANSP, np.uint8)            # spritejen näyttämä kerros
    shown[top + 21:bot + 1, xa:xa + 12] = body                        # runko riviin 143 asti (leivottuna)
    for px, y0, x1, own in ((b, btop, xb, cb), (a, top, xa, ca)):     # A edessä (sprite 0)
        blk = px[y0:y0 + 21]
        m = blk != TRANSP
        col = np.where(blk == 0, 0, np.where(blk == 12, 12, own))
        shown[y0:y0 + 21, x1:x1 + 12][m] = col[m]
    first = 72 + top                                                  # pään A rivi loppukuvassa
    nb = (KV_BOT - first) // 21 + 1                                   # runkospriteja (alin rivillä KV_BOT)
    assert 2 + nb <= 8, nb
    xr, xrb = 24 + 2 * xa, 24 + 2 * xb
    info = {"KV_X": xr, "KV_XB": xrb, "KV_Y0": first, "KV_BOT": KV_BOT, "KV_DB": btop - top, "KV_NB": nb,
            "KV_CA": ca, "KV_CB": cb, "KV_CC": cc, "KV_010": (1 if xr >= 256 else 0) | (2 if xrb >= 256 else 0)}
    print(f"  katuvalo: A x {xa} rivit {top}-{bot}, B x {xb} +{btop - top}, runkospriteja {nb}, "
          f"värit {ca}/{cb}/{cc}, rungon poikkeavia rivejä {off}")
    return blocks, info, shown


def kv_first(px: list[int], p_max: int, kv: dict) -> int:
    """Ensimmäinen kehys, jolla katuvalo on ruudussa (sprites.asm pole)."""
    return next(f for f, p in enumerate(px) if kv["KV_Y0"] + (p_max - p) + (p_max - p) // 2 <= KV_BOT + 20)


def kv_check(px: list[int], p_max: int, kv: dict, sw: list) -> None:
    """Katuvalon spritet eivät saa olla taivasriveillä eivätkä rivistön tai pääskysten kanssa samassa kehyksessä
    (sprites.asm: samat spritet 0-4 ja lohkot)."""
    sw_end = 0
    for t0, x0, dx, _, _ in sw:                            # pääskynen ruudulla, kun 1 <= X < 344
        f = t0
        while 16 <= x0 * 16 + dx * (f - t0) < 344 * 16:
            f += 1
        sw_end = max(sw_end, f)
    fp = kv_first(px, p_max, kv)
    for f in range(fp, len(px)):
        d = p_max - px[f]
        first = kv["KV_Y0"] + d + d // 2
        sky_end = 72 + SKY_T - px[f]                       # ensimmäinen ei-taivasrivi
        assert first >= sky_end, f"katuvalo taivasriveillä kehyksellä {f} (rivi {first}, taivas {sky_end})"
    assert fp > sw_end and fp > strip_last(px), f"katuvalo {fp}, pääskyset {sw_end}, rivistö {strip_last(px)}"
    print(f"  spritet: rivistö kehykseen {strip_last(px)}, pääskyset {sw[0][0]}-{sw_end}, katuvalo {fp}-")


def layout_bases(p_max: int) -> list[int]:
    """Asettelujen ensimmäiset rivit: peräkkäin enintään CMAX riviä."""
    bases = [0]
    while bases[-1] * 8 + CMAX * 8 + 7 < p_max:
        bases.append(bases[-1] + CMAX)
    if len(bases) % 2:                                     # viimeinen asettelu pankkiin 3 (luovutus pankkiin 2):
        bases.insert(1, max(1, bases[1] // 2))             # ensimmäinen väli kahtia
    return bases


def final_patch(shown: np.ndarray, fin0: int, bmp: bytes, scr: bytes, col: bytes, pole: np.ndarray,
                erase_sign: bool = False) -> tuple[list, list, np.ndarray]:
    """Luovutuksen loppukuva: kuvan rivit fin0.. bittikarttana ($D021 = 0) ja katuvalo (pole, spritejen kerros)
    leivottuna. Palauttaa muuttuneet solut [(solu 0..999 ruudulla, 8 bittikarttatavua + ruutu + väri)], kyltin
    tyhjennyksen solut (erase_sign: kaistan maalattu teksti pois, hil_sign ajo-kyltin alussa) ja lopullisen kuvan
    (144 x 160) tarkistusta varten. Tietueiden tavut pysyvät muuten sellaisinaan."""
    from c64fmt import Bitmap
    kv = pole != TRANSP
    win = shown[fin0 * 8:fin0 * 8 + WIN_ROWS * 8].copy()
    win[kv] = pole[kv]

    def compose(img: np.ndarray, wy0: int = 0) -> Bitmap:
        bm = Bitmap(img.copy(), bg=0)
        pole_front(bm, img, kv)
        return bm

    def cell(bm: Bitmap, cy: int, cx: int) -> bytes:
        o = cy * 320 + cx * 8
        return bytes(bm.bmp[o:o + 8]) + bytes([bm.scr[cy * 40 + cx], bm.col[cy * 40 + cx]])

    base = compose(win)
    if erase_sign:                                         # pääbuild: maalattu LOHJAN RAUTA täsmälleen kyltin
        t = np.load(LOHJA)                                 # viennin muoto ja paikka myös MC-koodauksen jälkeen
        kvc = kv.reshape(WIN_ROWS, 8, 40, 4).any((1, 3)).repeat(8, 0).repeat(4, 1)
        ink = (t != TRANSP) & ~kvc                         # katuvalo soluineen on tekstin edessä (pole_front)
        got = base.image[:t.shape[0], :t.shape[1]]
        if t.shape != win.shape or (got[ink] != t[ink]).any():
            raise SystemExit(f"maalattu LOHJAN RAUTA eroaa kyltin viennistä ({LOHJA.relative_to(ROOT)}): "
                             f"{int((got[ink] != t[ink]).sum())}/{int(ink.sum())} pikseliä, muoto {t.shape}")
    patch = []
    for cy in range(WIN_ROWS):
        for cx in range(40):
            r = fin0 + cy
            old = bmp[r * 320 + cx * 8:r * 320 + cx * 8 + 8] + bytes([scr[r * 40 + cx], col[r * 40 + cx]])
            if old != cell(base, cy, cx):
                patch.append(((FIN_ROW0 + cy) * 40 + cx, cell(base, cy, cx)))
    if not erase_sign:
        return patch, [], base.image.astype(np.uint8)
    blank = win.copy()                                     # pääbuild: maalattu LOHJAN RAUTA pois kyltin kaistalta,
    erase_band(blank)                                      # greetsit tulevat spriteinä;
    blank[kv] = pole[kv]                                   # katuvalo jää kaistan eteen
    b = compose(blank)
    sign = [((FIN_ROW0 + cy) * 40 + cx, cell(b, cy, cx)) for cy in range(WIN_ROWS) for cx in range(40)
            if cell(b, cy, cx) != cell(base, cy, cx)]
    assert sign, "kyltin kaistalla ei maalattua tekstiä"
    return patch, sign, b.image.astype(np.uint8)


def pole_front(bm, img: np.ndarray, kv: np.ndarray) -> None:
    """Katuvalon solut uudelleen: pylvään värit (muut kuin musta) rooleihin %10 ja %11, jotta ajo-kyltin spritet
    ($D01B, bittikartan takana) kulkevat pylvään takana. %01 on solun yleisin muu väri, muut lähimpään."""
    from collections import Counter
    for cy in range(img.shape[0] // 8):
        for cx in range(img.shape[1] // 4):
            sl = (slice(cy * 8, cy * 8 + 8), slice(cx * 4, cx * 4 + 4))
            cell, m = img[sl].copy(), kv[sl]
            fg = sorted({int(v) for v in cell[m]} - {0})
            if not fg:
                continue
            assert len(fg) <= 2, (cy, cx, fg)
            other = [v for v, _ in Counter(int(v) for v in cell[~m] if v != 0 and v not in fg).most_common()]
            c01 = other[0] if other else next(v for v in range(1, 16) if v not in fg)
            fg += other[1:3 - len(fg)] or [fg[0]] * (2 - len(fg))
            keep = [c01] + fg
            for v in {int(v) for v in cell.flat} - set(keep) - {0}:
                cell[cell == v] = min(keep + [0], key=lambda k: _lab_dist(v, k))
            role = {0: 0, c01: 1, fg[0]: 2, fg[1]: 3}
            o = cy * 320 + cx * 8
            for y in range(8):
                bm.bmp[o + y] = sum(role[int(cell[y, x])] << (6 - 2 * x) for x in range(4))
            bm.scr[cy * 40 + cx] = (c01 << 4) | fg[0]
            bm.col[cy * 40 + cx] = fg[1]
            bm.image[sl] = cell


# Savupiippujen savu: 6510 piirtää savupallot kuvan taivaspikseleihin
# (MC 00) joka toinen kehys ja palauttaa ne tietueista (hillner.asm, smoke). Host antaa vain staattisen datan:
# solujen savuroolit (vapaa väripari 11 tumma / 12 vaalea), pallojen maskit neljällä siirrolla ja taivasmaskin.
SMOKE_SRC = [(round(x), round(y)) for x, y in META["savupiiput"]]   # piippujen suut (MC-px, kuvan rivi)
# savualue: solusarakkeet C0..C1-1 (tuuli oikealle; tavun paikka rivillä 8 * sarake + rivi < 256, siis C1 <= 32),
# solurivit 0..R1-1 (savu nousee kuvan yläreunaan; asettelu 0)
SMOKE_C0 = max(0, (min(x for x, _ in SMOKE_SRC) - 8) // 4)
SMOKE_C1 = min(32, (max(x for x, _ in SMOKE_SRC) + 40) // 4)
SMOKE_R1 = max(y for _, y in SMOKE_SRC) // 8 + 1
assert SMOKE_R1 <= BANK_ROWS
SMOKE_DARK, SMOKE_LIGHT = 11, 12
# savupallon vaiheet iän mukaan: (säde MC-px, tiheys 0..1, tumma)
SMOKE_STAGES = [(2.0, 1.0, True), (3.0, 1.0, True), (4.0, 0.9, True), (4.8, 0.75, False), (5.4, 0.55, False),
                (5.8, 0.32, False)]
SMOKE_W, SMOKE_H = 4, 12                                  # maskin tavuja ja rivejä (12 MC-px + siirto 0 tai 2)


def smoke_roles(bmp: bytes, scr: bytearray, col: bytearray) -> tuple[list[int], list[int]]:
    """Savualueen soluille tumman ja vaalean savun bittiparit ($00/$55/$aa/$ff; 0 = ei savua solussa). Savu
    peittää vain taivaan (MC 00), ei kattoa, antenneja eikä piippuja. Väri, joka solussa jo on, käytetään
    sellaisenaan; muuten vapaa rooli saa värin (ruutu tai värimuisti)."""
    dark, light = [], []
    for cy in range(SMOKE_R1):
        for cx in range(SMOKE_C0, SMOKE_C1):
            i = cy * 40 + cx
            roles = {1: scr[i] >> 4, 2: scr[i] & 15, 3: col[i] & 15}
            used = {(b >> k) & 3 for b in bmp[cy * 320 + cx * 8:cy * 320 + cx * 8 + 8] for k in (0, 2, 4, 6)} - {0}
            out = []
            for want in (SMOKE_DARK, SMOKE_LIGHT):
                r = next((r for r in used if roles[r] == want), None)
                if r is None:
                    r = next((r for r in (1, 2, 3) if r not in used), None)
                    if r is not None:
                        used.add(r)
                        roles[r] = want
                out.append(0 if r is None else r * 0x55)
            if not out[1]:                                   # yksi savuväri riittää: vaalea tummalla ja päinvastoin
                out[1] = out[0]
            if not out[0]:
                out[0] = out[1]
            scr[i] = (roles[1] << 4) | roles[2]
            col[i] = roles[3]
            dark.append(out[0])
            light.append(out[1])
    return dark, light


def smoke_masks() -> list[int]:
    """Pallomaskit: vaihe x siirto (0 tai 2 MC-px, x & 2) x SMOKE_H riviä x SMOKE_W tavua, bittiparit %11
    peitetyille pikseleille; tiheys järjestetyllä 4 x 4 -ditherillä (pallo harvenee reunoilta ja vanhetessaan)."""
    bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16
    out = []
    for rad, dens, _ in SMOKE_STAGES:
        for sh in (0, 2):
            for y in range(SMOKE_H):
                row = [0] * SMOKE_W
                for x in range(12):
                    d = np.hypot(x + 0.5 - 6, y + 0.5 - 6) / rad
                    if d < 1 and bayer[y & 3, x & 3] < dens * (1.15 - 0.5 * d * d):
                        px = x + sh
                        row[px >> 2] |= 3 << (6 - 2 * (px & 3))
                out += row
    return out


def byte_lines(label: str, data: bytes | list[int], per: int = 32) -> list[str]:
    out = [label] if label else []
    for i in range(0, len(data), per):
        out.append("        .byte " + ",".join(f"${b & 0xff:02x}" for b in data[i:i + per]))
    return out


def main(out: Path, integrated: bool = False) -> None:
    """integrated: pääbuildin moduuli (koodi CODE_BASE:sta, tietueet sen perään, ei omaa musiikkia)."""
    global CODE_END, REGIONS, FIN_SCR
    if integrated:
        CODE_END = INT_CODE_END
        REGIONS = INT_REGIONS
        FIN_SCR = INT_FIN_SCR
    out.mkdir(parents=True, exist_ok=True)
    if integrated and not LOHJA.exists():
        raise SystemExit(f"kyltin vienti puuttuu: {LOHJA.relative_to(ROOT)} (make -C src/proto/kyltti module VARIANT=ajo)")
    img = image()
    bmp, scr, col, shown, fixes = encode(img, strip_mask(img.shape), title_layer(img.shape[0]) != TRANSP)
    scr, col = bytearray(scr), bytearray(col)
    smk_dark, smk_light = smoke_roles(bmp, scr, col)
    nrows = img.shape[0] // 8
    p_max = nrows * 8 - WIN_ROWS * 8

    # tietueet alueisiin; kuvan alapuoliset rivit (viimeisessä asettelussa) eivät koskaan näy
    recs = [bmp[r * 320:(r + 1) * 320] + scr[r * 40:(r + 1) * 40] + col[r * 40:(r + 1) * 40] for r in range(nrows)]
    fin0 = p_max // 8                                          # loppurajauksen ensimmäinen kuvan merkkirivi
    addr, blocks_out = [0] * nrows, []
    music_inc = music(out) if not integrated else [f"MSTART = {MSTART}"]
    if integrated:
        (out / "music.inc").write_text("HAVE_MUSIC = 0\n")
    m_lo, m_hi = music_area(out)
    reg = []
    for a, b in REGIONS:                                       # musiikin alue pois
        for lo, hi in ((a, min(b, m_lo)), (max(a, m_hi), b)):
            if hi > lo:
                reg.append([lo, hi])
    sblocks, sw_blocks = sprite_blocks()
    info = {"BLK_SW": 0}                                   # pääskyset kopioidaan lohkoihin 0-2
    bases = layout_bases(p_max)
    # Tietueet tiedostoihin tarpeen mukaan (kohtaustaulu src/scene/hil_glue.asm), jotta ennen kelloa ladattava osa
    # on pieni ja loput latautuvat kamera-ajon aikana:
    #   CRANE1  $4400-: asettelujen 0-2 rivit heti koodin perään (hil_prep ja hil_main1)
    #   CRANE2  pankin 3 alue ($c540-): seuraavat 6 riviä (asettelu 3), esiladataan kuten koodi
    #   CRANE1B crane1_end-$7fff: asettelun 4 rivit, ladataan kun asettelu 3 on rakennettu (noin kehys 160)
    #   CRANE1C $8c00-$9fff: loput rivit ja luovutuksen solut, kun asettelu 4 on rakennettu (noin 220)
    # Luovutuksen rivit (loppurajaus, late) luetaan vielä, kun ajo-kyltti on ladattu
    # $4400-$63ff:een: build tarkistaa, ettei yksikään ole siellä.
    late = list(range(fin0, nrows))
    in_ajo = lambda r: integrated and r[0] < INT_AJO_END and r[1] > INT_AJO_LO   # noqa: E731
    order = list(range(nrows))
    n1 = bases[2] + BANK_ROWS                                  # CRANE1: asettelut 0-2
    bank3 = next(r for r in reg if r[0] >= 0xC000)
    plan = [(INT_CODE_END, 0x8000, order[:n1]), (bank3[0], bank3[1], None), (None, 0x8000, None), (0x8C00, 0xA000, None)]
    rest = order[n1:]
    bounds = []
    for lo, hi, rows in plan:
        lo = bounds[0][1] if lo is None else lo                # CRANE1B jatkaa CRANE1:n perästä
        if rows is None:
            rows, rest = rest[:(hi - lo) // REC], rest[(hi - lo) // REC:]
        a = lo
        for i in rows:
            addr[i] = a
            blocks_out.append((a, recs[i]))
            a += REC
        assert a <= hi, (hex(lo), hex(hi), rows)
        bounds.append((lo, a))
    if rest:
        raise SystemExit(f"tietueet eivät mahdu: rivit {rest}")
    crane1_end = bounds[0][1]
    for r in reg:                                              # käytetyt alueet pois vapaista
        for lo, a in bounds:
            if r[0] <= lo < r[1] or lo <= r[0] < a:
                r[0] = max(r[0], min(a, r[1]))

    kv_blocks, kv_info, kv_shown = katuvalo()
    fin_patch, sign_patch, fin_img = final_patch(shown, fin0, bmp, scr, col, kv_shown, erase_sign=integrated)

    layouts = len(bases)
    assert layouts % 2 == 0, "viimeinen asettelu pitää olla pankissa 3 (luovutus pankkiin 2)"
    rt = [addr[r] if r < nrows else addr[0] for r in range(bases[-1] + BANK_ROWS)]
    if integrated:                                             # ajo-kyltti ladataan viimeisen asettelun näkyessä
        bad = [addr[i] for i in late if addr[i] < INT_AJO_END and addr[i] + REC > INT_AJO_LO]
        if bad:
            raise SystemExit(f"luovutuksen tietueet ajo-kyltin alueella: {[hex(a) for a in bad]}")
        keep = sorted(addr[i] for i in late)                    # muistikartta: luovutuksen tietueet
        (out / "last_records.txt").write_text("".join(f"${a:04x}-${a + REC - 1:04x}\n" for a in keep))
    mv = motion(p_max)
    inc = [f"CODE_END = ${CODE_END:04x}", f"FIN_DD00 = {FIN_DD00}", f"IMG_ROWS = {nrows}", f"P_MAX = {p_max}", f"LAYOUTS = {layouts}", f"HOLD0 = {HOLD0}",
           f"MOVE_N = {MOVE}", f"HOLD1 = {HOLD1}", f"FRAMES = {HOLD0 + MOVE + HOLD1}",
           f"SPR_BASE = ${SPR_BASE:04x}", f"SPR_PTR0 = {SPR_BASE // 64}", f"N_BLOCKS = {N_BLOCKS}",
           f"SKY_T = {SKY_T}",
           f"FIN_BMP = ${FIN_BMP:04x}", f"FIN_SCR = ${FIN_SCR:04x}", f"FIN_ROW0 = {FIN_ROW0}", f"FIN_IMG0 = {fin0}",
           f"FIN_ROWS = {WIN_ROWS}", f"FIN_N = {len(fin_patch)}",
           f"FIN_SN = {len(sign_patch)}", f"CRANE1_END = ${crane1_end:04x}", f"CRANE1B_END = ${bounds[2][1]:04x}",
           ] + [f"{k} = {v}" for k, v in info.items()] + music_inc
    tabs = byte_lines("row_lo", [a & 0xFF for a in rt]) + byte_lines("row_hi", [a >> 8 for a in rt])
    tabs += byte_lines("motion_v", mv)
    px = ppx_series(mv)
    SW = swallow_plan(px, kv_first(px, p_max, kv_info))
    kv_check(px, p_max, kv_info, SW)
    inc += [f"{k} = {v}" for k, v in kv_info.items()]
    tabs += byte_lines("kv_blk", [b for blk in kv_blocks for b in blk])
    tabs += byte_lines("sky_tab", sky_rows())
    tabs += byte_lines("lay_row", bases) + byte_lines("lay_px_lo", [(8 * b) & 0xFF for b in bases])
    tabs += byte_lines("lay_px_hi", [(8 * b) >> 8 for b in bases])
    sw_f0 = SW[0][0]                                       # pääskysten kello (sprites.asm swallows)
    inc += [f"N_SW = {len(SW)}", f"SW_F0 = {sw_f0}"]
    tabs += byte_lines("sw_t0", [w[0] - sw_f0 for w in SW]) + byte_lines("sw_x0lo", [(w[1] * 16) & 0xFF for w in SW])
    tabs += byte_lines("sw_x0hi", [(w[1] * 16) >> 8 for w in SW]) + byte_lines("sw_dx", [w[2] & 0xFF for w in SW])
    tabs += byte_lines("sw_row", [w[3] - 3 for w in SW]) + byte_lines("sw_ph", [w[4] for w in SW])
    tabs += byte_lines("sw_blk", [b for blk in sw_blocks for b in blk])
    n = len(RIVI[0]["rata"])                               # taustarivistö: rivi kohdittain (5 tavua, $ff = piilossa)
    for sp in RIVI:
        assert [t["s"] for t in sp["rata"]] == list(range(0, 8 * n, 8)) and len({t["x"] for t in sp["rata"]}) == 1
    assert not RIVI[3]["y_laajennus"] and all(a["y"] == b["y"] for a, b in zip(RIVI[3]["rata"], RIVI[4]["rata"]))
    tabs += byte_lines("rv_y", [sp["rata"][i]["y"] if sp["rata"][i]["nakyy"] else 0xFF for i in range(n) for sp in RIVI])
    rx = [24 + 2 * sp["rata"][0]["x"] for sp in RIVI]
    tabs += byte_lines("rv_x", [x & 0xFF for x in rx]) + byte_lines("rv_c", [sp["oma_vari"] for sp in RIVI])
    tabs += byte_lines("rv_hi", [(1 << k) if x >= 256 else 0 for k, x in enumerate(rx)])
    tabs += byte_lines("rv_xx", [(1 << k) if sp["x_laajennus"] else 0 for k, sp in enumerate(RIVI)])
    tabs += byte_lines("rv_yx", [(1 << k) if sp["y_laajennus"] else 0 for k, sp in enumerate(RIVI)])
    inc += [f"RV_N = {n}"]
    tabs += byte_lines("smk_dark", smk_dark) + byte_lines("smk_light", smk_light)
    tabs += byte_lines("smk_mask", smoke_masks())
    tabs += byte_lines("smk_sky", [sum(3 << (6 - 2 * k) for k in range(4) if (b >> (6 - 2 * k)) & 3 == 0)
                                   for b in range(256)])
    tabs += byte_lines("smk_srcx", [x for x, _ in SMOKE_SRC]) + byte_lines("smk_srcy", [y for _, y in SMOKE_SRC])
    tabs += byte_lines("smk_dk", [1 if d else 0 for _, _, d in SMOKE_STAGES])
    inc += [f"SMOKE_C0 = {SMOKE_C0}", f"SMOKE_C1 = {SMOKE_C1}", f"SMOKE_R1 = {SMOKE_R1}",
            f"SMOKE_NS = {len(SMOKE_STAGES)}", f"SMOKE_W = {SMOKE_W}", f"SMOKE_H = {SMOKE_H}",
            f"SMOKE_NSRC = {len(SMOKE_SRC)}"]
    ch = json.loads(ajo("taustarivisto_rata.json").read_text())["rooli_varit"]
    assert ch["1"] == "$d025 0" and ch["3"] == "$d026 12", ch   # yhteiset värit (hil_prep)
    segs = sky_segments()
    tabs += byte_lines("skg_s", [a for a, _ in segs]) + byte_lines("skg_e", [b for _, b in segs])
    inc += [f"SKG_N = {len(segs)}"]
    # luovutus ja kyltin tyhjennys (hil_sign): koodin perässä ei ole tilaa, joten solut menevät tietueiden
    # jälkeiseen vapaaseen tilaan alueelle, jota ajo-kyltti ei lataa yli (hil_sign on viimeinen käyttäjä)
    cells = fin_patch + sign_patch
    fin_tab = (byte_lines("fin_cell_lo", [(c & 0xFF) for c, _ in cells]) +
               byte_lines("fin_cell_hi", [(c >> 8) for c, _ in cells]) +
               byte_lines("fin_data", [b for _, d in cells for b in d]))
    need = 12 * len(cells)
    safe = [r for r in reg if not in_ajo(r)]
    spot = next((r for r in safe if r[1] - r[0] >= need), None)
    if spot is None:
        raise SystemExit(f"luovutuksen solut ({need} tavua) eivät mahdu tietueiden perään: "
                         f"{[(hex(a), b - a) for a, b in safe]}")
    data = [f"        * = ${spot[0]:04x}"] + fin_tab
    spot[0] += need
    for a, rec in blocks_out:
        data.append(f"        * = ${a:04x}")
        data += byte_lines("", rec)
    data.append(f"        * = ${0xC000 + SPR_BASE:04x}")      # pankki 3 (CRANE2); hil_prep kopioi pankkiin 2
    for b in sblocks:
        data += byte_lines("", b)

    (out / "hillner.inc").write_text("\n".join(inc) + "\n")
    (out / "tables.inc").write_text("\n".join(tabs) + "\n")
    (out / "records.inc").write_text("\n".join(data) + "\n")
    from PIL import Image
    from concept import c64
    pal = c64.palette()
    prev = shown.copy()
    bgc = np.array(sky_rows() + [0] * (nrows * 8 - WIN_ROWS * 8), np.uint8)   # taivas paikassa p = 0
    prev = np.where(prev == TRANSP, bgc[:, None], prev)
    Image.fromarray(np.repeat(pal[prev], 2, axis=1).astype(np.uint8)).save(out / "preview.png")
    np.save(out / "index.npy", shown.astype(np.uint8))
    np.save(out / "final.npy", fin_img)
    t = title_layer(img.shape[0])                                # otsikon viite:
    np.save(out / "otsikko.npy", np.where(t != TRANSP, shown, TRANSP).astype(np.uint8))   # koodattu (kirkon solut)
    np.savez(out / "bg.npz", sky=np.array(sky_rows(), np.uint8), sky_t=SKY_T)
    print(f"hillner: {nrows} riviä ({nrows * 8} px), korjattuja soluja {fixes}, liike {p_max} px, "
          f"asettelut {bases}, tietueita {len(recs)}, taivas {SKY_T} riviä, savu {SMOKE_SRC}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), "--integrated" in sys.argv[2:])
