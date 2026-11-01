"""Levynvaihtoruutujen data (src/runko/levynvaihto.asm).

Ruutu on MC-bittikartta: yläosassa taivas, alhaalla pöytä ja teksti. Keskellä 5,25" levyke (pinta
tools/gfx/data/levyke/levyke.npy, 40 x 80 MC-px) pyörii 3D:nä pystyakselinsa ympäri perspektiivissä, ja 6510 piirtää
sen joka kehys pikselisarakkeittain: tavusarakkeen neljä pikseliä ovat pinnan sarakkeet q..q+3 (pintasarake, lv_init
generoi), rivit v-kartasta aukikirjoitetulla koodilla. Tämä tiedosto tekee staattisen datan (tausta, tekstit
puolitavuina, projektion taulut, U-taulu, pintasarakkeiden lähde ja osoitteet) ja `Levy`:n, joka on 6510-piirron
viitemalli (samat kokonaisluvut ja kirjoitukset). Tekstit ja vaihtojen järjestys
luetaan tekstit.yaml:n kohdasta levynvaihdot.

  uv run --project tools/concept python -I tools/disk/levynvaihto.py OUTDIR   # lv.inc, lv_ut.inc, lv_defs.inc, lv_tausta.bin, lv_ruutu.bin
  python3 -I tools/disk/levynvaihto.py syms LABELS OUT                        # sisääntulot kohtaustaululle
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/proto/kyltti"))
import font  # noqa: E402

LEVYKE = ROOT / "tools/gfx/data/levyke/levyke.npy"     # pinta
NC, NR = 32, 104                # levyn alue: 32 tavusaraketta x 104 riviä
C0, R0 = 4, 24                  # alueen vasen tavusarake ja ylin rivi bittikartassa
CY = 52                         # levyn keskirivi alueessa
CX2 = 128                       # levyn keskikohta alueessa puolikkaina MC-pikseleinä (bittikartan pikseli 80)
HORIZON = 128                   # pöydän reuna (bittikartan rivi)
TEXT_ROW = 19                   # tekstin ensimmäinen merkkirivi (2 riviä)
TEXT_H = 15                     # kirjainkorkeus
KX = 1 / 0.936
# Projektio: kameran etäisyys D = 3,5 levyn puolileveyttä, Z
# yksikössä 1/32 puolileveyttä (ZD = 112). Reunan x puolikkaina pikseleinä = cos * R2[Z] / 256, puolikorkeus
# neljännesriveinä HH4[Z] (enintään 52 riviä: alue). Pinnan sarake u pikselin kohdalla perspektiivikorjattuna
# U-taulusta (k = kauemman ja lähemmän reunan korkeuksien suhde, t = osuus leveydestä).
ZD = 112
HH4MAX = 4 * CY
TH0 = -25 & 255                 # lepokulma noin -35 astetta (256 = täysi kierros)
PER = 300                       # kehyksiä vaihtoa kohden (lv_go: kaikki vaihdot peräkkäin)
FLIP = 150                      # kääntö: lepo 90, kääntö 60 kehystä
ENT = 48                        # lv_init0 + lv_swap: levy kääntyy syrjästä (-90 astetta) lepoon näin monessa kehyksessä
MARGIN = 4                      # v-kartta jatkaa reunariviä (v 0 / 79) näin monta riviä tavusarakkeen puolikorkeuden yli
# pintasarakejoukot (puoli, tason sarakkeita): leveä levy tasolla 40, kapeneva 20 ja 10 (mip), syrjällään 5..1
# yhteiset (takapuolen pinta: tarra ei näy alle 14 pikselin levyssä). Joukko = puoli * 3 + taso (40, 20, 10), 6..10
# tasot 5..1; etupuolen taso 10 on sama kuin takapuolen (muisti: nopea koodi sarakkeelle 10)
SETS = ((0, 40), (0, 20), (1, 10), (1, 40), (1, 20), (1, 10), (1, 5), (1, 4), (1, 3), (1, 2), (1, 1))
GEN = tuple(dict.fromkeys(SETS))        # generoitavat joukot (lv_init), qaddrs-järjestys
QPAD = 3                        # tason vasemmalla puolella taustasarakkeita (tavun pikselit q..q+3, q >= -3)
HMIN = 13                       # v-kartan pienin puolikorkeus (sarakkeet HMIN..CY)
NH = CY + 1 - HMIN
FC0, NF = 10, 11                # nopea aukikirjoitettu koodi alueen sarakkeille FC0..FC0+NF-1, muille yleinen
# muistin sivut: pintasarakkeet (3 sivulla, 81 t) ja v-kartta, generoidaan lv_initissä; $b000-$b1ff tunnistetiedosto
QPAGES = [*range(0xA9, 0xB0), *range(0xC3, 0xD0), *range(0xE0, 0x100), *range(0x58, 0x60)]
VM = 0xB200
VB = 80                         # taustarivi pintasarakkeessa (v-kartta: rivi levyn ulkopuolella)
NK, NT = 32, 128                # U-taulu: k-tasot (0,5..1) ja t-tasot


def texts() -> list[tuple[str, str]]:
    """(teksti, animaatio) tekstit.yaml:n levynvaihdoista järjestyksessä: animaatio "kaanto" tai "vaihto"."""
    sys.path.insert(0, str(ROOT / "tools"))
    import tekstit
    out = []
    for n, v in tekstit.lue("levynvaihdot").items():
        if v.get("animaatio") not in ("kääntö", "vaihto") or not v.get("teksti"):
            raise SystemExit(f"levynvaihto: tekstit.yaml levynvaihdot {n}: tarvitaan teksti ja animaatio kääntö tai vaihto")
        out.append((v["teksti"], "kaanto" if v["animaatio"] == "kääntö" else "vaihto"))
    if not out:
        raise SystemExit("levynvaihto: tekstit.yaml: levynvaihdot puuttuu")
    return out


def sin_tab() -> list[int]:
    return [round(127 * math.sin(2 * math.pi * i / 256)) for i in range(256 + 64)]


def ease(n: int) -> list[int]:
    return [round(255 * (3 * (i / (n - 1)) ** 2 - 2 * (i / (n - 1)) ** 3)) for i in range(n)]


def texture() -> np.ndarray:
    """(2, 80, 40) bittiparit: etu- ja takapuoli kasvokkain (takapuoli takaa nähtynä), 1 = tausta näkyy läpi."""
    return np.load(LEVYKE)


def level_cols(nw: int) -> list[int]:
    """Tason nw sarakkeen m näyte pinnan sarakkeista (keskikohta)."""
    return [int((m + .5) * 40 / nw) for m in range(nw)]


def quad(tex: np.ndarray, side: int, nw: int, q: int) -> bytes:
    """Pintasarake: tavu riveittäin v 0..79 (+ taustarivi VB), pikselit = tason nw sarakkeet q..q+3."""
    cols = level_cols(nw)
    out = bytearray()
    for v in range(VB + 1):
        px = [tex[side, v, cols[m]] if v < VB and 0 <= m < nw else 1 for m in range(q, q + 4)]
        out.append(mc_byte(px))
    return bytes(out)


def vmap() -> np.ndarray:
    """v-kartta [rivi][puolikorkeus]: pinnan rivi 40 + (2 r - 103) * 20 // h (reunarivi jatkuu MARGIN riviä),
    VB = tausta. 6510 laskee saman lv_initissä (vm_gen)."""
    m = np.full((NR, 64), VB, np.uint8)
    for r in range(NR):
        d = 2 * r + 1 - 2 * CY
        for h in range(1, 64):
            if abs(d) < 2 * h + 2 * MARGIN:
                m[r, h] = min(VB - 1, max(0, 40 + d * 20 // h))
    return m


def utab() -> np.ndarray:
    """U-taulu [k][t]: 4 u (neljännessarakkeina) pikselille, jonka osuus leveydestä on t, kun vasemman ja oikean
    reunan korkeuksien suhde on k <= 1 (oikea lähempänä): u = 40 t / (k + (1 - k) t). Peilattu k > 1: 160 - U[1/k][127 - t]."""
    out = np.zeros((NK, NT), np.uint8)
    for kk in range(NK):
        k = (kk + 32) / 64
        for ti in range(NT):
            t = (ti + .5) / NT
            out[kk, ti] = min(159, round(4 * 40 * t / (k + (1 - k) * t)))
    return out


def geom() -> dict:
    """Projektion taulut (6510 käyttää samoja)."""
    return {
        "sin": [v for v in sin_tab()],
        "hh4": [min(HH4MAX, round(4 * 40 * ZD / z)) if z else HH4MAX for z in range(256)],
        "r2": [min(255, round(2 * 20 * ZD * 32 * 256 / 127 / z / 32)) if z else 255 for z in range(256)],
        "dt1": [min(65535, 32768 // w) if w else 65535 for w in range(256)],
        "ut": utab(),
        "vm": vmap(),
    }


def ent_tab() -> list[int]:
    """Esiinkäännön kulman lisäys kehyksittäin (indeksi = kehyksiä jäljellä): syrjästä (-64) lepoon (TH0), pehmeästi."""
    off = -64 - (TH0 - 256 if TH0 > 127 else TH0)
    return [round(off * (3 * (i / (ENT - 1)) ** 2 - 2 * (i / (ENT - 1)) ** 3)) & 255 for i in range(ENT)]


LIT_L = (12, 15, 15, 1)         # tarran väri (%11, värimuisti) valoisuuden |cos| / 32 mukaan
LIT_L_UUSI = (9, 8, 7, 7)       # uusi levy: keltainen tarra


def mc_byte(px: list[int]) -> int:
    return px[0] << 6 | px[1] << 4 | px[2] << 2 | px[3]


TAUSTA = ROOT / "tools/gfx/data/levyke/tausta.json"   # tausta: rivitavut ja merkkirivien värit
GREY = 11                       # levyn harmaa: levyn soluissa %10 (levy käyttää %00, %10 ja %11, taustalle jää %01)
BAND = range(R0 // 8, (R0 + NR - 1) // 8 + 1)          # merkkirivit, joihin levy voi piirtää


def tausta() -> tuple[list[int], list[tuple[int, int]]]:
    """Rivitavut (200, sama tavu koko leveydellä) ja merkkirivien värit (%01, %10) taustasta (TAUSTA)
    sovitettuna renderöijään:
    - tekstiriveillä tasainen %01 (text_step kirjoittaa kirjaimet $55:n päälle): tekstirivin siirtymä siirtyy
      edelliseen merkkiriviin, jos se on tasainen samaa väriä;
    - levyn merkkiriveillä %10 = 11: siirtymä a -> b kulkee harmaan kautta (a -> 11 merkkirivin lopussa ja peilattuna
      11 -> b seuraavan alussa), jolloin seuraavan merkkirivin oma siirtymä jää pois (kova raja)."""
    import json
    d = json.loads(TAUSTA.read_text(encoding="utf-8"))
    tavut = [int(t.lstrip("$"), 16) for t in d["rivitavut"]]
    varit = [tuple(v) for v in d["merkkirivit"]]
    if len(tavut) != 200 or len(varit) != 25:
        raise SystemExit(f"levynvaihto: {TAUSTA}: {len(tavut)} rivitavua / {len(varit)} merkkiriviä, odotettiin 200 / 25")

    def rows(k):
        return tavut[8 * k:8 * k + 8]

    for k in (TEXT_ROW, TEXT_ROW + 1):
        if rows(k) != [0x55] * 8:
            a, b = varit[k]
            if varit[k - 1] != (a, a) or rows(k - 1) != [0x55] * 8:
                raise SystemExit(f"levynvaihto: tekstirivin {k} siirtymää ei voi siirtää merkkiriville {k - 1}")
            tavut[8 * k - 8:8 * k + 8] = rows(k) + [0x55] * 8
            varit[k - 1], varit[k] = (a, b), (b, b)
    for k in BAND:
        a, b = varit[k]
        if b not in (a, GREY):
            tavut[8 * k + 8:8 * k + 16] = rows(k)[::-1]
            varit[k + 1] = (b, GREY)
        varit[k] = (a, GREY)
    return tavut, varit


def background() -> np.ndarray:
    """Bittikartan tausta (200 x 160 bittiparit)."""
    tavut, _ = tausta()
    return np.array([[t >> (6 - 2 * (x % 4)) & 3 for x in range(160)] for t in tavut], np.uint8)


def screen() -> np.ndarray:
    """Näyttömuisti (25 x 40): merkkirivin %01 ylänibble, %10 alanibble."""
    return np.array([[a << 4 | b] * 40 for a, b in tausta()[1]], np.uint8)


def region_bg() -> tuple[list[int], int, int]:
    """Renderöijän taustarivit: alueen yläpuoliskon rivitavut (rivit 0..CY-1) ja rivit TR0..TR1, joilla tavu ei ole
    $55. Peilirivit (alapuolisko) ja tekstirivit ovat $55, ja levyn soluissa %10 = 11 (build pysähtyy muuten)."""
    tavut, varit = tausta()
    bad = []
    if any(t != 0x55 for t in tavut[R0 + CY:R0 + NR]):
        bad.append(f"levyn alueen alapuoliskolla (rivit {R0 + CY}..{R0 + NR - 1}) muuta kuin $55")
    if any(t != 0x55 for t in tavut[TEXT_ROW * 8:TEXT_ROW * 8 + 16]):
        bad.append(f"tekstiriveillä {TEXT_ROW * 8}..{TEXT_ROW * 8 + 15} muuta kuin $55")
    if any(varit[k][1] != GREY for k in BAND):
        bad.append(f"levyn merkkiriveillä %10 muu kuin {GREY}")
    if bad:
        raise SystemExit("levynvaihto: tausta rikkoo renderöijän rajoitteet: " + "; ".join(bad))
    bgr = tavut[R0:R0 + CY]
    tr = [r for r in range(CY) if bgr[r] != 0x55]
    return (bgr, tr[0], tr[-1]) if tr else (bgr, CY, CY - 1)


def mc_glyph(c: str) -> np.ndarray:
    """Kirjain MC-pikseleinä: kyltin kirjaimisto puolella leveydellä (MC-pikseli on kaksi leveä). Ä- ja Ö-pisteet
    sulautuisivat puolessa leveydessä viivaksi: pisteet erikseen varsien kohdalle. Runko (A, O) piirretään muiden
    kirjainten vedolla: fontin oma Ä on matalampi, joten sen veto ohenee yhteen MC-pikseliin ja kirjain näyttää
    rikkinäiseltä."""
    if c not in "ÄÖ":
        return font.glyph(c, TEXT_H, KX / 2)
    body = TEXT_H - max(3, round(TEXT_H * 0.2))         # rungon korkeus kuten fontin Ä:ssä
    b = font.glyph("A" if c == "Ä" else "O", body, KX / 2 * TEXT_H / body, stem=TEXT_H / (0.936 * body))
    w = b.shape[1]
    g = np.zeros((TEXT_H, w), bool)
    g[TEXT_H - body:] = b
    g[:TEXT_H - body - 1, 1] = True
    g[:TEXT_H - body - 1, w - 2] = True
    return g


def text_img(t: str) -> np.ndarray:
    """Teksti MC-pikseleinä (16 x 160)."""
    gl = [None if c == " " else mc_glyph(c) for c in t]
    gap, space = 1, 3
    w = sum(space if g is None else g.shape[1] for g in gl) + gap * (len(gl) - 1)
    if w > 156:
        raise SystemExit(f"levynvaihto: teksti {t!r} {w} MC-px > 156")
    out = np.zeros((16, 160), bool)
    x = (160 - w) // 2
    for g in gl:
        if g is None:
            x += space + gap
            continue
        out[0:TEXT_H, x:x + g.shape[1]] = g
        x += g.shape[1] + gap
    return out


def encode(img: np.ndarray) -> bytes:
    """MC-kuva (200 x 160, bittiparit) -> bittikartta 8000 t."""
    out = bytearray(8000)
    for cy in range(25):
        for cx in range(40):
            for r in range(8):
                out[cy * 320 + cx * 8 + r] = mc_byte(list(img[cy * 8 + r, cx * 4:cx * 4 + 4]))
    return bytes(out)


def qaddrs() -> list[int]:
    """Pintasarakkeiden osoitteet (3 sivulla) joukkojen ja q:n järjestyksessä (lv_init generoi samaan järjestykseen)."""
    n = sum(nw + QPAD for _, nw in GEN)
    slots = [p * 256 + 81 * i for p in QPAGES for i in range(3)]
    if n > len(slots):
        raise SystemExit(f"levynvaihto: {n} pintasaraketta > {len(slots)} paikkaa")
    return slots[:n]


def text_nibbles(t: str) -> bytes:
    """Teksti kahtena merkkirivinä (640 bittikartan tavua taustalla $55, kirjaimet %11) puolitavuina: bitti 3 - i =
    pikseli i on kirjainta. text_step muuntaa takaisin (nibmc)."""
    ti = text_img(t)
    bits = []
    for cy in range(2):
        for cx in range(40):
            for r in range(8):
                bits.append(sum(8 >> i for i in range(4) if ti[cy * 8 + r, cx * 4 + i]))
    return bytes(bits[i] << 4 | bits[i + 1] for i in range(0, 640, 2))


def byte_lines(name: str, data, fmt: str = "${:02x}", per: int = 32) -> list[str]:
    data = list(data)
    out = []
    for i in range(0, len(data), per):
        out.append((name if i == 0 else " " * len(name)) + " .byte " + ", ".join(fmt.format(v) for v in data[i:i + per]))
    return out


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    tx = texts()
    if len(sys.argv) > 2 and sys.argv[2]:     # tekstien valinta (kokoa.py, LV_TEKSTIT): vaihto k näyttää rivin order[k]
        order = [int(n) for n in sys.argv[2].split(",")]
        if not all(1 <= n <= len(tx) for n in order) or len(order) > len(tx):
            raise SystemExit(f"levynvaihto: tekstit {order}: tekstit.yaml:n levynvaihdoissa rivit 1-{len(tx)}")
        tx = [tx[n - 1] for n in order] + tx[len(order):]
    bgr, tr0, tr1 = region_bg()
    bg = encode(background())
    assert all(len({bg[(y >> 3) * 320 + cx * 8 + (y & 7)] for cx in range(40)}) == 1 for y in range(200)), \
        "levynvaihto: tausta ei ole rivivakio (levynvaihto.asm lv_bg täyttää bittikartan rivitavuista)"
    (out / "lv_tausta.bin").write_bytes(bg)
    (out / "lv_ruutu.bin").write_bytes(screen().tobytes())
    g = geom()
    tex = texture()
    qa = qaddrs()
    D = ["; Generoitu: tools/disk/levynvaihto.py (src/runko/levynvaihto.asm): vakiot"]
    D += [f"{k} = {v}" for k, v in (
        ("NC", NC), ("NR", NR), ("C0", C0), ("R0", R0), ("CY", CY), ("CX2", CX2), ("TEXT_ROW", TEXT_ROW),
        ("NVAIHTO", len(tx)), ("NK", NK), ("HORIZON", HORIZON), ("ZD", ZD), ("TH0", TH0), ("PER", PER), ("FLIP", FLIP),
        ("MARGIN", MARGIN), ("HMIN", HMIN), ("NH", NH), ("FC0", FC0), ("NF", NF), ("VM", f"${VM:04x}"),
        ("VB", VB), ("NSETS", len(GEN)), ("NQ", len(qa)), ("NT", NT), ("HH4MAX", HH4MAX), ("TR0", tr0), ("TR1", tr1), ("ENT", ENT),
        ("BGR", "[" + ", ".join(f"${b:02x}" for b in bgr) + "]"))]
    L = ["; Generoitu: tools/disk/levynvaihto.py (src/runko/levynvaihto.asm): taulut"]
    L.append("vaihto_anim .byte " + ", ".join("1" if a == "vaihto" else "0" for _, a in tx))
    first: dict[str, int] = {}
    for i, (t, _) in enumerate(tx):
        if t in first:              # sama teksti kahdesti (kääntö 1 ja 5): yksi kopio, LV1 on täynnä ($1a00-$43ff)
            L.append(f"text{i} = text{first[t]}")
            L.append(f"tcol{i} = tcol{first[t]}")
            continue
        first[t] = i
        ti = text_img(t)
        cols = [c for c in range(40) if ti[:, c * 4:c * 4 + 4].any()]
        L.append(f"; {t}")
        L += byte_lines(f"text{i}", text_nibbles(t))
        L.append(f"tcol{i}  .byte {cols[0]}, {cols[-1]}")
    for k in ("text", "tcol"):
        L.append(f"{k}_lo .byte " + ", ".join(f"<{k}{i}" for i in range(len(tx))))
        L.append(f"{k}_hi .byte " + ", ".join(f">{k}{i}" for i in range(len(tx))))
    L += byte_lines("sintab", (v & 255 for v in g["sin"]))
    L += byte_lines("hh4tab", g["hh4"], "{}")
    L += byte_lines("r2tab", g["r2"], "{}")
    L += byte_lines("dt1_lo", (v & 255 for v in g["dt1"]))
    L += byte_lines("dt1_hi", (v >> 8 for v in g["dt1"]))
    L += byte_lines("ease60", ease(60), "{}")
    L += byte_lines("ease70", ease(70), "{}")
    L.append("ent_tab  .byte " + ", ".join(str(v) for v in ent_tab()))
    L.append("lit_lab  .byte " + ", ".join(map(str, LIT_L)))
    L.append("lit_lab2 .byte " + ", ".join(map(str, LIT_L_UUSI)))
    # lähde: tason 40 pintasarakkeet q = 0, 4, .., 36 kummallekin puolelle (2 x 10 x 80 t); lv_init generoi kaikki
    # pintasarakkeet (joukko, q) rullaamalla edellisestä: tavu = edellinen << 2 | uusi pikseli
    L += byte_lines("srcq", b"".join(quad(tex, side, 40, 4 * j)[:VB] for side in (0, 1) for j in range(10)))
    L.append("set_nw   .byte " + ", ".join(str(nw) for _, nw in GEN))
    L.append("set_side .byte " + ", ".join(str(sd) for sd, _ in GEN))
    uo, ul = [], []
    for _, nw in GEN:
        uo.append(len(ul))
        ul += level_cols(nw)
    L.append("set_uoff .byte " + ", ".join(map(str, uo)))
    L += byte_lines("set_u", ul, "{}")
    gb, n = [], 0
    for _, nw in GEN:
        gb.append(n)
        n += nw + QPAD
    L.append("qbase    .byte " + ", ".join(str(gb[GEN.index(st)]) for st in SETS))
    L += byte_lines("qcol_lo", (a & 255 for a in qa))
    L += byte_lines("qcol_hi", (a >> 8 for a in qa))
    L += byte_lines("bgr", bgr)        # taustan rivitavut alueen yläpuoliskolla (alapuolisko $55)
    L += byte_lines("r8lo", (8 * r & 255 for r in range(NR + 1)))
    L += byte_lines("r8hi", (8 * r >> 8 for r in range(NR + 1)))
    L += byte_lines("r11lo", (11 * r & 255 for r in range(NR + 1)))
    L += byte_lines("r11hi", (11 * r >> 8 for r in range(NR + 1)))
    (out / "lv.inc").write_text("\n".join(L) + "\n")
    (out / "lv_ut.inc").write_text("\n".join(byte_lines("ut", g["ut"].flatten(), "{}")) + "\n")
    (out / "lv_defs.inc").write_text("\n".join(D) + "\n")
    # seuraavien levyjen tunnistetiedostot (levynvaihto.asm id_names/id_sigs): $b000, allekirjoitus ja täyte yli lohkon
    sys.path.insert(0, str(ROOT / "tools/disk"))
    import d64
    for fname, sig in (("levy2", "SIMLOHJA LEVY 2 "), ("levy2b", "SIMLOHJA LEVY2 B"), ("levy3", "SIMLOHJA LEVY 3 "),
                       ("levy3b", "SIMLOHJA LEVY3 B")):
        (out / f"id_{fname}.prg").write_bytes(bytes([0x00, 0xB0]) + d64.petscii(sig) + bytes(400))


def syms(labels: Path, out: Path) -> None:
    """lv_init ja lv_go VICE-labelsista kohtaustaulun includeksi (muut nimet eivät saa näkyä rungolle)."""
    want = {"lv_init", "lv_init0", "lv_show", "lv_lead", "lv_song", "lv_go", "lv_swap0", "lv_swap1", "lv_swap2", "lv_swap3", "lv_swap4"}
    lines = []
    for ln in labels.read_text().splitlines():
        a, name = ln.split()[1], ln.split()[2].lstrip(".")
        if name in want:
            lines.append(f"{name} = ${a}")
            want.discard(name)
    if want:
        raise SystemExit(f"levynvaihto: {labels}: puuttuu {sorted(want)}")
    out.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "syms":
        syms(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        main()
