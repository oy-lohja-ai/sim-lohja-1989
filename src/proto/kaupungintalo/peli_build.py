"""Kaupungintalon pelin (osan kehykset NAYTTO_LOPPU-839) taulut: host tekee vain datan ja aikataulun, 6510 piirtää.

  uv run -q --project tools/concept python src/proto/kaupungintalo/peli_build.py OUT

Lähde tools/gfx/data/kaupungintalo/peli_*. Tulos OUT/:
  peli.inc        vakiot (rivit, vaiheiden kartan alkurivit, spritelohkot)
  peli_data.asm   käyttöliittymäpalojen taulut, tapahtumat (pelin kehys, toiminto, argumentti), spritejen reitit
                  kahden kehyksen välein, vierityksen kulku, Hillnerin vilkkuvat solut, spritet
  *.bin           merkistöt ja kartan koodit ja värit sellaisinaan

Pelin kehys T = DFRAME - PELI_ALKU (osan kehys T + PELI_ALKU; isku, kun osan kehys on 30:n monikerta). Vaiheet:
P1 Katastrofit-valikko 0-119, P2 vieritys Hillnerille 120-239, P3 tuhoa-työkalu, Hillnerin valinta ja vasta sitten
neuvonantajan varoitus ja Ohita 240-547 (varoituksen ehtii lukea), P4 548-719: ikkuna sulkeutuu suoraan P4:n
ruutuun, purkaja ajaa ja tulee työkalupalkin alta.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tools/gfx/data/kaupungintalo"
PELI_ALKU = 118                         # kt.asm PELI_VAIHTO: ensimmäinen pelikuva osan kehyksessä 119
PELI_PITUUS = 726                       # SCENE_END - PELI_ALKU + varaus (taulut kattavat lopun)
SPR_BASE = 0x5800                       # spritelohkot VIC-pankissa 1
GAP = 1                                 # FLD-rako otsikon alla aina vähintään 1 rivi ($D018-vaihto rakoon)
SPRITET = ["johtaja_taytto", "johtaja_reuna", "timantti0", "timantti1", "purkaja0a", "purkaja0b", "purkaja1a",
           "purkaja1b", "kaista", "purkaja_ma", "purkaja_mb"]      # _ma/_mb: palkin kohdalta maskattu purkaja (peli.asm)
OPS = {"END": 0, "DRAW": 1, "RESTORE": 2, "PREP": 3, "SWAP": 4, "TYPE": 5, "FLASH": 6, "BAND": 7, "VARIT": 8,
       "KOODIT": 9}
RAJA = 0x80                             # VARIT: pala | RAJA = alla olevan kartan värit (restore)
PALATYOT = {"DRAW", "RESTORE", "PREP", "SWAP", "TYPE", "KOODIT"}
VAIHE_NRO = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}


def smooth(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return a + (b - a) * u


def sprite_bytes(img: np.ndarray, mc: bool, shared: tuple[int, int]) -> bytes:
    b = bytearray(64)
    for y in range(min(21, img.shape[0])):
        if mc:
            for x in range(min(12, img.shape[1])):
                c = int(img[y, x])
                if c < 0:
                    continue
                v = 1 if c == shared[0] else 3 if c == shared[1] else 2      # %01 $D025, %11 $D026, %10 oma
                b[y * 3 + x // 4] |= v << (6 - 2 * (x % 4))
        else:
            for x in range(min(24, img.shape[1])):
                if img[y, x] >= 0:
                    b[y * 3 + x // 8] |= 0x80 >> (x % 8)
    return bytes(b)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    d = json.loads((DATA / "kaupungintalo.json").read_text())["peli"]
    for f in DATA.glob("peli_*.bin"):
        shutil.copy(f, out / f.name)
    rivit = d["rivit"]
    ui = d["ui"]
    names = list(ui)
    idx = {n: k for k, n in enumerate(names)}
    a = ["; generoitu: src/proto/kaupungintalo/peli_build.py"]
    inc = [f"PELI_ALKU = {PELI_ALKU}", f"PELI_PITUUS = {PELI_PITUUS}", f"PELI_RIVIT = {rivit}", f"GAP = {GAP}",
           f"SPR_LOHKO = {(SPR_BASE & 0x3FFF) // 64}"] + [f"D02{k + 1} = {c}" for k, c in enumerate(d["globaalit"])]
    for k, n in enumerate(SPRITET):
        inc.append(f"SL_{n.upper()} = SPR_LOHKO + {k}")
    # käyttöliittymäpalat: rivi, sarake, korkeus, leveys, datan osoite (koodit h*w, sitten värit h*w)
    a.append("osa_rivi .byte " + ", ".join(str(ui[n]["rivi"]) for n in names))
    a.append("osa_sar  .byte " + ", ".join(str(ui[n]["sarake"]) for n in names))
    a.append("osa_kork .byte " + ", ".join(str(ui[n]["korkeus"]) for n in names))
    a.append("osa_lev  .byte " + ", ".join(str(ui[n]["leveys"]) for n in names))
    a.append("osa_lo   .byte " + ", ".join(f"<(PELI_UI+{ui[n]['kohta']})" for n in names))
    a.append("osa_hi   .byte " + ", ".join(f">(PELI_UI+{ui[n]['kohta']})" for n in names))
    for n in names:
        inc.append(f"O_{n.upper()} = {idx[n]}")

    # ---------------------------------------------------------------- aikataulu
    ev: list[tuple[int, str, int]] = []
    cur = {}                                  # T -> (tyyppi, x, y)  tyyppi 0 piilossa, 1 johtaja, 2 timantti
    doz = {}                                  # T -> (x, y, kehys)
    T_VAL0, T_ITEM, T_CLICK = 4, 9, 70
    col = d["valikko_sarake"]
    xk = 24 + d["valikko_x"] + 20
    item_x = 24 + (col + 13) * 8
    item_y = lambda k: 50 + (2 + k) * 8 - 6
    ev.append((0, "DRAW", idx["valikkorivi_k"]))
    ev.append((0, "DRAW", idx["otsikko0"]))
    ev.append((0, "DRAW", idx["valikko_yla"]))
    ev.append((0, "DRAW", idx["valikko"]))
    for T in range(0, 120):
        if T < T_VAL0:
            cur[T] = (1, xk, 46)
        elif T < T_VAL0 + T_ITEM * 6:
            u = (T - T_VAL0) / (T_ITEM * 6)
            cur[T] = (1, round(lerp(xk, item_x, smooth(u * 3))), round(lerp(item_y(0) - 4, item_y(6), u)))
        elif T < 84:
            cur[T] = (1, item_x, item_y(6))
        elif T < 112:
            u = smooth((T - 84) / 28)
            cur[T] = (1, round(lerp(item_x, 180, u)), round(lerp(item_y(6), 210, u)))
        else:
            cur[T] = (0, 0, 0)
    for k in range(len([n for n in names if n.startswith("valinta")])):
        t = T_VAL0 + T_ITEM * k
        ev.append((t, "DRAW", idx[f"valinta{k}"]))
        if k:
            ev.append((t, "DRAW", idx[f"rivi{k - 1}"]))
    ev.append((T_CLICK + 2, "DRAW", idx["rivi6"]))           # välähdys: valinta pois ja takaisin (klikkaus)
    ev.append((T_CLICK + 5, "DRAW", idx["valinta6"]))
    ev.append((80, "DRAW", idx["valikkorivi"]))              # ylärivit ensin: ne piirtyvät ennen sädettä, ja
    ev.append((80, "DRAW", idx["otsikko0"]))                 # valikon alue riveiltä 2 alkaen ehtii sen jälkeen
    ev.append((80, "RESTORE", idx["valikko"]))
    # P2: vieritys 0 -> 8 * (rivit - 25) px
    smax = 8 * (rivit - 25)
    ev.append((118, "PREP", VAIHE_NRO["P2"]))
    ev.append((120, "SWAP", VAIHE_NRO["P2"]))
    ev.append((120, "BAND", 1))
    scroll = [round(smax * smooth((T - 124) / 108)) for T in range(120, 240)]
    for T in range(120, 240):
        cur[T] = (0, 0, 0)
    # P3: tuhoa-työkalu ja Hillnerin valinta, vasta sitten neuvonantajan varoitus ja Ohita. Iskut: T + PELI_ALKU on
    # 30:n monikerta (T = 242, 272, 332, 362, 542). Teksti on valmis T 438, ja ikkuna on auki T_OHI + 6 asti: koko
    # teksti näkyy 110 kehystä, jotta sen ehtii lukea. Aika on otettu purkajan ajosta (T_D0-T_D1, 146 kehystä).
    T_TYO, T_SEL, T_NEUVO, T_OHI = 272, 332, 362, 542
    T_P4 = T_OHI + 6                                         # ikkuna sulkeutuu suoraan P4:n ruutuun
    T_D0, T_D1 = T_P4 + 6, 700                               # purkaja ajaa, sitten paikallaan osan loppuun
    T_KURSORI = T_NEUVO + 82                                 # kursori tulee näkyviin, kun teksti on valmis (T 438)
    ev.append((236, "PREP", VAIHE_NRO["P3"]))
    ev.append((240, "SWAP", VAIHE_NRO["P3"]))
    ev.append((240, "BAND", 0))
    ev.append((242, "DRAW", idx["tyokalut0"]))
    ev.append((244, "DRAW", idx["tila_purku"]))
    ev.append((T_TYO + 2, "DRAW", idx["tyokalut3"]))         # tuhoa-työkalu pohjaan klikkauksesta
    ev.append((T_SEL, "FLASH", 1))
    ev.append((T_SEL + 22, "FLASH", 0))                      # vilkku seis omissa väreissään (kirjoitus T % 16 == 0)
    # iso ikkuna vaihtuu yhdessä kehyksessä: värit säteen perässä kehystä ennen (VARIT, peli.asm cjobs), koodit
    # rajalla (avautuessa KOODIT, sulkeutuessa P4:n valmis ruutu); muuten avauksen ensimmäisessä kehyksessä muotokuva
    # ja napit näkyisivät kartan väreillä, ja sulkeutuessa työkalupalkki olisi vajaa ja alarivi näkyisi
    ev.append((T_NEUVO - 1, "VARIT", idx["neuvo"]))
    ev.append((T_NEUVO, "KOODIT", idx["neuvo"]))
    ev.append((T_NEUVO + 6, "TYPE", idx["neuvo0"]))
    ev.append((T_NEUVO + 28, "TYPE", idx["neuvo1"]))
    ev.append((T_NEUVO + 58, "TYPE", idx["neuvo2"]))
    ev.append((T_OHI, "DRAW", idx["ohita_pohjassa"]))
    ev.append((T_P4 - 1, "VARIT", idx["neuvo"] | RAJA))      # ikkunan alle kartan värit, koodit P4:n ruudusta
    # P4: ikkuna sulkeutuu ja purkaja lähtee; ikkunan tilalla tarkempi kartta, palkki ja tilarivi P4:n merkistöllä
    # samassa kehyksessä
    ev.append((T_P4 - 4, "PREP", VAIHE_NRO["P4"]))
    ev.append((T_P4, "SWAP", VAIHE_NRO["P4"]))
    ev.append((T_P4, "DRAW", idx["tyokalut"]))
    ev.append((T_P4, "DRAW", idx["tila_matkalla"]))
    ev.append((T_P4, "DRAW", idx["otsikko1"]))               # rahat vähenevät, kun purku on määrätty
    ev.append((T_P4, "FLASH", 1))
    hx, hy = d["hillner_keski"]
    hil_x, hil_y = 24 + 2 * hx - 16, 51 + hy - smax + GAP - 8
    tool_x, tool_y = 24 + 8, 51 + 3 * 8 + GAP + 2
    ohita_x, ohita_y = 24 + 27 * 8, 50 + 15 * 8 - 6 + GAP
    for T in range(240, 720):
        if T < 248:
            cur[T] = (0, 0, 0)
        elif T < T_TYO:
            u = smooth((T - 248) / (T_TYO - 248))
            cur[T] = (1, round(lerp(200, tool_x, u)), round(lerp(160, tool_y, u)))
        elif T < T_TYO + 10:
            cur[T] = (1, tool_x, tool_y + (1 if T < T_TYO + 4 else 0))
        elif T < T_SEL - 10:
            u = smooth((T - T_TYO - 10) / (T_SEL - T_TYO - 20))
            cur[T] = (2, round(lerp(tool_x + 20, hil_x, u)), round(lerp(tool_y + 10, hil_y, u)))
        elif T < T_NEUVO - 4:
            cur[T] = (2, hil_x, hil_y + (1 if T_SEL <= T < T_SEL + 4 else 0))
        elif T < T_KURSORI:
            cur[T] = (0, 0, 0)                               # ikkuna peittää Hillnerin: kursori piiloon
        elif T < T_OHI - 8:
            # tekstin luvun ajan kursori lähestyy hitaasti Ohita-nappia ikkunan alareunan alta (ei tekstin yli)
            u = smooth((T - T_KURSORI) / (T_OHI - 8 - T_KURSORI))
            cur[T] = (1, round(lerp(ohita_x - 60, ohita_x, u)), round(lerp(ohita_y + 44, ohita_y, u)))
        elif T < T_OHI + 6:
            cur[T] = (1, ohita_x, ohita_y + (1 if T_OHI <= T < T_OHI + 6 else 0))
        elif T < T_P4:
            cur[T] = (0, 0, 0)
        else:
            cur[T] = (2, hil_x, hil_y)                       # valittu talo: timantti paikallaan purun ajan
    (sx, sy), (ex, ey) = d["purkajan_reitti"]
    for T in range(T_D0, PELI_PITUUS):
        u = smooth((T - T_D0) / (T_D1 - T_D0))
        x, y = lerp(sx, ex, u), lerp(sy, ey, u)
        doz[T] = (max(0, round(24 + 2 * x - 24)), round(51 + y - smax + GAP - 16), (T // 4) % 2 if T < T_D1 else 0)
    # purkaja tulee työkalupalkin alta eikä sen päältä:
    # peli.asm doz_maski tyhjentää palkin kohdalla (spriten X < PAL_X1) olevat MC-pikselit; maski vain X:n mukaan, joten
    # purkajan rivit ovat palkin riveillä aina, kun se on palkin kohdalla
    tk = ui["tyokalut"]
    pal_x1 = 24 + 8 * (tk["sarake"] + tk["leveys"])
    pal_y0, pal_y1 = 51 + 8 * tk["rivi"] + GAP, 51 + 8 * (tk["rivi"] + tk["korkeus"]) + GAP
    for T, (x, y, _f) in doz.items():
        assert x >= pal_x1 or pal_y0 <= y + 1 and y + 22 <= pal_y1, (T, x, y, pal_y0, pal_y1)
    inc.append(f"PAL_X1 = {pal_x1}")
    a.append("pal_mt   .byte " + ", ".join(
        f"${sum(3 << (6 - 2 * q) for q in range(4) if 4 * k + q >= h):02x}" for h in range(13) for k in range(3)))
    ev.sort(key=lambda e: e[0])
    # VARIT: värityö ajetaan seuraavan kehyksen irq_splitissä logiikan osoittimilla, joten samassa kehyksessä ei muita
    # palatöitä eikä kirjoitusta kesken; enintään 2 työtä (z_cj), ja KOODIT seuraa heti
    for t, op, arg in ev:
        if op == "VARIT":
            assert not [e for e in ev if e[0] == t and e[1] in PALATYOT], (t, "palatyö VARIT-kehyksessä")
            assert sum(1 for e in ev if e[0] == t and e[1] == "VARIT") <= 2, t
            assert (t + 1, "SWAP" if arg & RAJA else "KOODIT", VAIHE_NRO["P4"] if arg & RAJA else arg) in ev, (t, arg)
            assert not any(e[1] == "TYPE" and e[0] < t <= e[0] + ui[names[e[2]]]["leveys"] for e in ev), t
    ev.append((0xFFFF, "END", 0))
    a.append("ev_t_lo  .byte " + ", ".join(f"<{t}" for t, _, _ in ev))
    a.append("ev_t_hi  .byte " + ", ".join(f">{t}" for t, _, _ in ev))
    a.append("ev_op    .byte " + ", ".join(str(OPS[o]) for _, o, _ in ev))
    a.append("ev_arg   .byte " + ", ".join(str(g) for _, _, g in ev))
    for k, v in OPS.items():
        inc.append(f"OP_{k} = {v}")
    # kursorin reitti kahden kehyksen välein (i = T // 2): P1 i < 60, P3:sta alkaen taulun indeksi i - 60 (P2:ssa
    # kaista, kursoria ei lueta), viimeinen (T_P4) pysyy; purkaja joka kehys T >= DOZ0 (ennen piilossa).
    # Molemmat 8-bittisellä indeksillä
    assert all(cur[T][0] == 0 for T in range(120, 248))
    ct = [cur[2 * i] for i in range(60)] + [cur[2 * i] for i in range(120, T_P4 // 2 + 1)]
    dz = [doz[T] for T in range(T_D0, PELI_PITUUS)]
    assert len(ct) <= 256 and len(dz) <= 256
    inc += [f"CUR_N = {len(ct)}", f"DOZ0 = {T_D0}"]
    a.append("cur_t    .byte " + ", ".join(str(c[0]) for c in ct))
    a.append("cur_xl   .byte " + ", ".join(str(c[1] & 255) for c in ct))
    a.append("cur_xh   .byte " + ", ".join(str(c[1] >> 8) for c in ct))
    a.append("cur_y    .byte " + ", ".join(str(c[2]) for c in ct))
    a.append("doz_xl   .byte " + ", ".join(str(z[0] & 255) for z in dz))
    a.append("doz_xh   .byte " + ", ".join(str(z[0] >> 8) for z in dz))
    a.append("doz_y    .byte " + ", ".join(str(z[1]) for z in dz))
    a.append("doz_f    .byte " + ", ".join(str(z[2]) for z in dz))
    a.append("vier     .byte " + ", ".join(str(s) for s in scroll))
    inc.append(f"SMAX = {smax}")
    # Hillnerin solut näkymässä rivit - 25 (ruudun rivi = kartan rivi - (rivit - 25), värit peli_varit.bin:stä)
    varit = (DATA / "peli_varit.bin").read_bytes()
    top = rivit - 25
    cells = [(r, c) for r, c in d["hillner_solut"] if r - top >= 2]
    a.append("hil_lo   .byte " + ", ".join(f"<${0xD800 + (r - top) * 40 + c:04x}" for r, c in cells))
    a.append("hil_hi   .byte " + ", ".join(f">${0xD800 + (r - top) * 40 + c:04x}" for r, c in cells))
    a.append("hil_c    .byte " + ", ".join(str(varit[r * 40 + c]) for r, c in cells))
    a.append("hil_v    .byte " + ", ".join(str(1 | (varit[r * 40 + c] & 8)) for r, c in cells))
    inc.append(f"HIL_N = {len(cells)}")
    sp = np.load(DATA / "peli_spritet.npz")
    shared = (0, 11)                      # $D025 musta, $D026 tummanharmaa (purkajan MC-spritet)
    spr = []
    for n in SPRITET:
        mc = n.startswith("purkaja")
        spr.append(f"; {n}")
        data = sprite_bytes(sp[n], mc, shared) if n in sp else bytes(64)   # maskatut kopiot: peli.asm täyttää
        spr.append(".byte " + ", ".join(f"${v:02x}" for v in data))
    (out / "peli.inc").write_text("\n".join(inc) + "\n")
    (out / "peli_data.asm").write_text("\n".join(a) + "\n")
    (out / "peli_spritet.asm").write_text("\n".join(spr) + "\n")


if __name__ == "__main__":
    main()
