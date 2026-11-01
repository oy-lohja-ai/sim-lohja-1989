"""Alkuruudun (Oy Lohja AI) staattinen data 6510:lle: vakiot, taulut ja generoidut täyttöketjut.

    python3 -I tools/gfx/logo/build.py OUTDIR [--integrated]

Tuottaa OUTDIR/consts.inc (vakiot, aikajanan iskut), tables.asm (verkko, sini, kertolaskun neliötaulut,
perspektiivi, sävy- ja kuviotaulut, rivien osoitteet) ja fill.asm (pystysuoran XOR-täytön aukikirjoitetut
ketjut molemmille puskureille). Ei kuvia eikä ratoja: 6510 laskee jokaisen kuvan itse (model.py on sen
bittitarkka vertailumalli). Erillisohjelmalle myös musiikki (tools/music/music.py build, $0a00).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import model as md  # noqa: E402
import name as nm  # noqa: E402
import timeline as tl  # noqa: E402
import title as ttl  # noqa: E402

BMP = {"A": 0x6000, "B": 0xA000}
SCR = {"A": 0x4000, "B": 0xBC00}            # ruutu B bittikartan B perässä: alun lopussa $a000-$bfff riittää
EBUF = 0xE000
MUSIC_ADDR = 0x0A00                         # omassa ohjelmassa käynnistyksen perään (demossa rungon $0800); pankki 3 on purun kuvan


def timing():
    """kohtauksen alku ja pituus aikajanalta (src/gen/timing.inc), oletuksena 8 tahtia"""
    sym = {}
    p = ROOT / "src/gen/timing.inc"
    if p.exists():
        for line in p.read_text().splitlines():
            m = re.match(r"(\w+)\s*=\s*(-?\d+)", line)
            if m:
                sym[m[1]] = int(m[2])
    song = sym.get("TIM_SONG_START", 2400)
    if "TIM_SCENE_ALKU_START" in sym:
        start = sym["TIM_SCENE_ALKU_START"]
        nxt = sorted(v for k, v in sym.items() if re.match(r"TIM_SCENE_\w+_START$", k) and v > start)
        length = (nxt[0] if nxt else sym.get("TIM_FRAMES", start + tl.L_SCENE)) - start
        return start, length, song + start
    return 0, tl.L_SCENE, song - tl.L_SCENE


def b80(v):
    """etumerkillinen tavu kertolaskun Y-indeksiksi (v ^ $80)"""
    return (v & 255) ^ 0x80


def drow(buf, r):
    return BMP[buf] + (md.Y0 // 8 + (r >> 3)) * 320 + 80 + (r & 7)


def erow(r):
    return EBUF + (r >> 3) * 256 + (r & 7)


def bytes_(label, vals, per=16):
    vals = [v & 255 for v in vals]
    out = [label] if label else []
    for i in range(0, len(vals), per):
        out.append("        .byte " + ",".join(f"${v:02x}" for v in vals[i:i + per]))
    if not vals:
        out.append("        ; (tyhjä)")
    return out


def lohi(label, vals):
    return bytes_(label + "_l", [v & 255 for v in vals]) + bytes_(label + "_h", [(v >> 8) & 255 for v in vals])


def tables(m: md.Model) -> list[str]:
    mesh = m.m
    c = tl.cues()
    ft, ut = tl.face_times()
    out = ["; generoitu: tools/gfx/logo/build.py (älä muokkaa)", "", "        .align 256"]
    out += bytes_("fulltab", md.FULL) + bytes_("fullside", md.FULLS)
    out += bytes_("fside", [0 if f["n"][2] > 16000 else 1 for f in mesh.faces])
    out += bytes_("smooth", tl.SMOOTH) + bytes_("ease3", tl.EASE3)
    out += bytes_("dift", [(d * tl.DIFFUSE) >> 7 for d in range(128)])
    out += lohi("rq", [min(65535, md.RQ[d]) for d in range(80)])
    def kc1(dx, dy):                        # |dy| = 1: montako pikseliä alkurivillä (Model.mark_edge)
        sl = (md.RQ[dx]) >> 8
        sl = -sl if dy < 0 else sl
        acc = 10 * 256 + (sl >> 1) + 127
        rows = [(acc + k * sl) >> 8 for k in range(dx)]
        assert rows[0] == 10 and all(r in (10, 10 + dy) for r in rows) and rows == sorted(rows, reverse=dy < 0)
        return rows.count(10)
    out += bytes_("kc1d", [kc1(d, 1) if d > 1 else 0 for d in range(80)])
    out += bytes_("kc1u", [kc1(d, -1) if d > 1 else 0 for d in range(80)])
    out += bytes_("slt3", [(3 * md.RQ[d]) >> 8 if d > 3 else 0 for d in range(80)])   # |dy| = 3 loiva
    out += bytes_("xlm", [[0xFF, 0x3F, 0x0F, 0x03][x & 3] for x in range(md.W)])   # pikselit x..tavun loppu
    out += bytes_("xrm", [[0xC0, 0xF0, 0xFC, 0xFF][x & 3] for x in range(md.W)])   # tavun alku..x
    out += bytes_("xc8", [(x >> 2) * 8 for x in range(md.W)])
    out += bytes_("ephi", [erow(r) >> 8 for r in range(md.ROWS + 1)])
    out += lohi("drowa", [drow("A", min(r, md.ROWS - 1)) for r in range(md.ROWS)])
    # verkko; ryhmien (palikat 0-2, timantti 3) verteksit peräkkäin
    grp = [[i for i in range(len(mesh.world)) if mesh.vblk[i] == k] for k in range(4)]
    assert all(g == list(range(g[0], g[-1] + 1)) for g in grp), "ryhmän verteksit eivät ole peräkkäin"
    out += bytes_("gfirst", [g[0] for g in grp]) + bytes_("glast", [g[-1] for g in grp])
    # kappaleet (proj.asm): keskipisteet, kulmien indeksit X- ja Y-tauluihin
    assert all(c[2] == 0 for c in m.ocen), "kappaleen keskipisteen z ei ole 0"
    assert m.oh[0] == m.oh[1] == m.oh[2] and m.oh[0][0] == m.oh[0][1] and m.oh[3][0] == m.oh[3][1]
    out += bytes_("ocx", [c[0] for c in m.ocen]) + bytes_("ocy", [c[1] for c in m.ocen])
    out += bytes_("ocxs", m.ocxs)                   # X-keskipisteet venytettyinä (model.XS)
    # kannat (proj.asm basis, X = 0 palikat, 1 timantti): X-rivin h1 ja h3 venytettyinä, Y-rivin ennallaan
    out += bytes_("hbx1", [m.ohx[0][0], m.ohx[3][0]]) + bytes_("hbx3", [m.ohx[0][2], m.ohx[3][2]])
    out += bytes_("hby1", [m.oh[0][0], m.oh[3][0]]) + bytes_("hby3", [m.oh[0][2], m.oh[3][2]])
    ring = {(0, -1): 0, (1, 0): 1, (0, 1): 2, (-1, 0): 3}
    vxidx, vyidx = [], []
    for i, vc in enumerate(m.vc):
        if mesh.vblk[i] < 3:
            vxidx.append((vc[0] > 0) * 2 + (vc[2] > 0))
            vyidx.append((vc[0] > 0) * 4 + (vc[1] > 0) * 2 + (vc[2] > 0))
        else:
            vxidx.append(ring[vc[:2]] * 2 + (vc[2] > 0))
            vyidx.append(vxidx[-1])
    out += bytes_("vxidx", vxidx) + bytes_("vyidx", vyidx)
    nids, fnid = [], []
    for f in mesh.faces:
        n7 = md.n7(f["n"])
        if n7 not in nids:
            nids.append(n7)
        fnid.append(nids.index(n7))
    for k in range(4):
        out += bytes_(f"fv{k}", [f["v"][k] for f in mesh.faces])
    cand = [0 if (mesh.inner[i] or f["n"][2] < -16000) else (1 + f["obj"]) for i, f in enumerate(mesh.faces)]
    # näkyvyys: determinanttitermit (indeksi kappale * 3 + i, etumerkki 0 = +, 1 = -), toinen termi tai $ff
    fda, fsa, fdb, fsb = [], [], [], []
    for i, f in enumerate(mesh.faces):
        tr = [(3 * mesh.vblk[f["v"][0]] + j, q) for j, q in enumerate(m.fsgn[i]) if q]
        assert 1 <= len(tr) <= 2
        fda.append(tr[0][0]); fsa.append(tr[0][1] < 0)
        fdb.append(tr[1][0] if len(tr) > 1 else 255); fsb.append(len(tr) > 1 and tr[1][1] < 0)
    out += bytes_("fda", fda) + bytes_("fsa", fsa) + bytes_("fdb", fdb) + bytes_("fsb", fsb)
    out += bytes_("fcand", cand) + bytes_("fnid", fnid) + bytes_("fblk", [mesh.vblk[f["v"][0]] for f in mesh.faces])
    out += lohi("ft", ft) + lohi("ut", ut)
    out += bytes_("nx7", [b80(n[0]) for n in nids]) + bytes_("ny7", [b80(n[1]) for n in nids])
    out += bytes_("nz7", [b80(n[2]) for n in nids])
    e = mesh.edges
    assert all(x[3] != 255 for x in e), "avoin särmä (marks olettaa kaksi tahkoa)"
    out += bytes_("ea", [x[0] for x in e]) + bytes_("eb", [x[1] for x in e])
    out += bytes_("ef0", [x[2] for x in e]) + bytes_("ef1", [x[3] for x in e])
    out += lohi("est", [x[4] for x in e]) + lohi("eln", [x[5] for x in e])
    out += lohi("erl", [md.RLEN[x[5]] for x in e])
    out += bytes_("edia", [1 if (x[0] >= mesh.nb or x[1] >= mesh.nb) else 0 for x in e])
    de = [k for k, x in enumerate(e) if x[0] >= mesh.nb or x[1] >= mesh.nb]
    nfb = sum(1 for f in mesh.faces if not f["obj"])
    assert all(f["obj"] == (i >= nfb) for i, f in enumerate(mesh.faces)), "palikoiden tahkot ensin"
    out += bytes_("dedge", de) + [f"NDE = {len(de)}", f"NFB = {nfb}"]
    out += bytes_("eblk", [mesh.vblk[x[0]] for x in e])
    # AI-leima: koko k ja keskipisteen x & 3 = s -> merkit (rivi, tavusarake, maski) keskipisteen suhteen
    ent, first = [], []
    for st_ in m.ai_stamps:
        for sh in range(4):
            first.append(len(ent))
            grp = {}
            for dy, x in st_:
                xx = x + sh
                grp[(dy, xx >> 2)] = grp.get((dy, xx >> 2), 0) | md.MASK[xx & 3]
            ent += [(dy, b, mk) for (dy, b), mk in sorted(grp.items())]
    first.append(len(ent))
    assert max(b - a for a, b in zip(first, first[1:])) * 3 < 256
    out += bytes_("aist", [v for e in ent for v in e])          # tietueet: rivi, tavusarake, maski
    out += lohi("aisp", [f"aist + {3 * i}" for i in first]) if False else []
    out += ["aisp_l .byte " + ",".join(f"<(aist + {3 * i})" for i in first),
            "aisp_h .byte " + ",".join(f">(aist + {3 * i})" for i in first)]
    out += bytes_("pat", md.PATTERN) + bytes_("pato", md.PATTERN_ODD)
    out += bytes_("aidim", [max(1, (lv * 9) >> 4) for lv in range(md.LEVELS)])
    out += bytes_("kyaw", tl.KYAW) + bytes_("kpitch", tl.KPITCH) + bytes_("kscale", tl.KSCALE)
    out += lohi("kicks", c.kicks)
    out += bytes_("objcx", [b80(x) for x, _ in tl.OBJC]) + bytes_("objcy", [b80(y) for _, y in tl.OBJC])
    out += bytes_("maskt", md.MASK)
    out += lohi("scrrow", [SCR["A"] + 40 * (md.Y0 // 8 + r) for r in range(md.ROWS // 8)])
    cc = [md.cell_colors(r) for r in range(md.ROWS // 8)]
    out += bytes_("cellscr", [(a << 4) | b for a, b, _ in cc]) + bytes_("cellcol", [c3 for _, _, c3 in cc])
    out += [f"CELLSCR = {[(a << 4) | b for a, b, _ in cc]}", f"CELLCOL = {[c3 for _, _, c3 in cc]}"]
    # heijastus: alapalikoiden 0 ja 1 etutahkot, kulmat kiertojärjestyksessä (heijastusindeksi palikka * 4 + j)
    rf = sorted(m.refl_faces(), key=lambda f: mesh.vblk[mesh.faces[f]["v"][0]])
    assert [mesh.vblk[mesh.faces[f]["v"][0]] for f in rf] == [0, 1]
    out += bytes_("rfv", [v for f in rf for v in mesh.faces[f]["v"]]) + bytes_("rff", rf)
    out += bytes_("rsolid", [md.PATTERN[s] for s in md.REFL_SOLID])
    out += bytes_("fin", tl.fill_ramp())                     # tahkon täyttöpaino täytön alusta (timeline.fill_ramp)
    out += lohi("landt", c.land)
    bv = m.bevels()
    out += bytes_("bvf", [f for f, _a, _b in bv]) + bytes_("bva", [a for _f, a, _b in bv]) + bytes_("bvb", [b for _f, _a, b in bv])
    out += bytes_("bevp", [md.PATTERN[md.BEV[lv]] for lv in range(md.LEVELS)])
    out += bytes_("bevpo", [md.PATTERN_ODD[md.BEV[lv]] for lv in range(md.LEVELS)])
    out += [f"NBEV = {len(bv)}"]
    out += [f"NNID = {len(nids)}", "NRV = 8"]
    return out


def tables2(m: md.Model) -> list[str]:
    """$f600-: valon suunnat ja |dy| = 2 -segmentit (vain piirto), sitten T3:sta (pankin 3 bittikartan rivit 22-24,
    säilyy purun kuvan alla) aaltoilu, purun pyyhkäisy ja nimiruudun avautuminen; demossa oma tiedosto"""
    c = tl.cues()
    out = ["; generoitu: tools/gfx/logo/build.py (älä muokkaa)"]
    out += bytes_("lcamx", [b80(l[0]) for l in tl.LCAM]) + bytes_("lcamy", [b80(l[1]) for l in tl.LCAM])
    out += bytes_("lcamz", [b80(l[2]) for l in tl.LCAM])

    def kc2(dx, dy):                        # |dy| = 2 (dx >= 3): kahden ensimmäisen rivin pikselit (Model.mark_edge)
        sl = (2 * md.RQ[dx]) >> 8
        sl = -sl if dy < 0 else sl
        acc = 10 * 256 + (sl >> 1) + 127
        rows = [(acc + k * sl) >> 8 for k in range(dx)]
        s1 = 1 if dy > 0 else -1
        assert rows[0] == 10 and all(r in (10, 10 + s1, 10 + 2 * s1) for r in rows) and rows == sorted(rows, reverse=dy < 0)
        return rows.count(10), rows.count(10 + s1)
    k2d = [kc2(d, 2) if d > 2 else (0, 0) for d in range(80)]
    k2u = [kc2(d, -2) if d > 2 else (0, 0) for d in range(80)]
    out += bytes_("kc2d0", [a for a, _ in k2d]) + bytes_("kc2d1", [b for _, b in k2d])
    out += bytes_("kc2u0", [a for a, _ in k2u]) + bytes_("kc2u1", [b for _, b in k2u])
    tb, rb = m.wipe()
    out += ["        .fill T3 - *, 0                 ; purun ajan taulut pankin 3 bittikartan alle (hand.asm)"]
    out += bytes_("wtb", [51 + y for y in tb]) + bytes_("wrb", [51 + y for y in rb])
    n = c.topen                              # nimiruutu avautuu viivasta hidastuen (jatkaa purun kiihtyvää liikettä,
    ot = [255 - (n - min(n, k + 1)) ** 2 * 255 // (n * n) for k in range(n + 1)]   # heti ensimmäisessä kehyksessä)
    out += bytes_("otb", [51 + ttl.LINE - ttl.LINE * u // 255 for u in ot])
    out += bytes_("orb", [51 + ttl.LINE + 1 + (198 - ttl.LINE - 1) * u // 255 for u in ot])   # rivit 0-197: RB
    #                                                 ennen riviä 250 (hw_250)
    out += bytes_("rtab", ripple())
    out += [f"RIPA = {RIPA}", f"RIPP = {RIPP}"]
    return out


def big_tables() -> tuple[list[str], list[str]]:
    """sivutetut taulut: sinin neljännes (256 t) ja kertolaskun neliötaulut (2 kt)"""
    assert all(md.SIN[(i + 512) % 1024] == -md.SIN[i] and md.SIN[(256 + i) % 1024] == md.SIN[(256 - i) % 1024]
               for i in range(1024))
    sin = ["; generoitu: tools/gfx/logo/build.py (neljännesaalto, logo.asm sin8_of)", "        .align 256"]
    sin += bytes_("squart", md.SIN[:256])
    # Q1[i] = (i - 256)^2 / 4, Q2[i] = (i - 255)^2 / 4: etumerkillinen 8x8 -> 16 (logo.asm SETMUL/MULY)
    q1 = [(i - 256) ** 2 // 4 for i in range(512)]
    q2 = [(i - 255) ** 2 // 4 for i in range(512)]
    q = ["; generoitu: tools/gfx/logo/build.py", "        .align 256"]
    q += bytes_("q1l", [v & 255 for v in q1]) + bytes_("q1h", [v >> 8 for v in q1])
    q += bytes_("q2l", [v & 255 for v in q2]) + bytes_("q2h", [v >> 8 for v in q2])
    return sin, q


def consts(m: md.Model, start: int, length: int, mstart: int) -> list[str]:
    mesh = m.m
    c = tl.cues()
    K = lambda a, b: tl.kfac(a, b)
    assert m.ocen[0][1] == m.ocen[1][1] and 0 < 2 * m.ocen[0][1] + m.kk < 256
    assert m.ocen[0][1] == m.ocen[1][1] and 0 < 2 * m.ocen[0][1] + m.kk < 256
    sym = {
        "SCENE_START": start, "SCENE_LEN": length, "MSTART": mstart,
        "ROWS": md.ROWS, "COLS": md.COLS, "HZ": md.HZ, "Y0": md.Y0, "X0": md.X0, "CXQ9": md.CXQ9,
        "NV": len(mesh.world), "NB": mesh.nb, "NF": len(mesh.faces), "NE": len(mesh.edges),
        "QR": 2 * m.ocen[0][1] + m.kk, "W": md.W, "AI_VY0": m.ai_vy[0], "AI_NK": len(m.ai_vy),
        "DFRONT": mesh.dfront, "DF_B": mesh.dfc[0], "DF_R": mesh.dfc[1], "DF_T": mesh.dfc[2], "DF_L": mesh.dfc[3],
        "ODDMAX": md.ODDMAX, "BW": md.BW, "DET_MIN": md.DET_MIN,
        "VALI_X": md.VALI_X, "VALI_Y": md.VALI_Y, "VALI_DY": md.VALI_DY, "DFLY": md.DFLY,
        **{f"G_{k.upper()}": v for k, v in m.gapv.items()},
        "PUSH0": c.push0, "PUSH1": c.push1, "KPUSH": K(c.push0, c.push1),
        "FLY0": c.fly0, "LOCK": c.lock, "KFLY": K(c.fly0, c.lock), "FLASH": c.flash, "NAME": c.name, "SW0": c.sw0, "RL": c.rl,
        "EX0": c.ex0, "EX1": c.ex1, "EXG0": c.exg0, "EXG1": c.exg1, "KEXG": K(c.exg0, c.exg1),
        "GALL2": tl.span(tl.grow_all()), "DONE1": c.done[1], "NKICK": len(c.kicks),
        "AMBIENT": tl.AMBIENT, "LAT": tl.LAT, "BEAT": tl.BEAT, "WIPE": c.wipe, "S4_BASE": tl.S4_BASE, "S4_PUSH": tl.S4_PUSH,
        "EBUF": EBUF, "BMPA": BMP["A"], "BMPB": BMP["B"], "SCRA": SCR["A"], "SCRB": SCR["B"],
        "MUSIC_ADDR": MUSIC_ADDR, "SPRA": SPR["A"], "SPRB": SPR["B"],
        "NM_NAME": c.name, "NM_OUT": c.nout, "NM_STEP": nm.NSTEP, "NM_N": len(nm.TEXT), "NM_DROPN": len(nm.DROP),
        "NM_RAMPN": len(nm.RAMP), "NM_ODROPN": len(nm.ODROP), "SPR3": 0xC400,
        "RIP0": RIP0, "RIPN": RIPN, "RIPD": RIPD,
        "TITLE0": c.title0, "TOPEN": c.topen, "TCODE": ttl.TCODE, "TSPR": ttl.TCODE + 3,
        "TSEVN": ttl.TCODE + 6, "T2RDY": ttl.TCODE + 7, "TSEVL": ttl.TCODE + 9, "TLRDY": ttl.TCODE + 8,
    }
    ft, ut = tl.face_times()
    sym["FTEND"], sym["UTBEG"] = max(ft) + c.rl, min(ut)    # viimeinenkin tahko täysi
    for k in range(3):
        sym[f"GFULL{k}"] = mesh.blk_d0[k] + ((tl.span(mesh.blk_d1[k] - mesh.blk_d0[k]) * tl.SMOOTH[255]) >> 8)
        sym[f"LAND{k}"] = c.land[k]
        sym[f"DONE{k}"] = c.done[k]
        sym[f"KBLK{k}"] = K(c.land[k], c.done[k])
        sym[f"D0_{k}"] = mesh.blk_d0[k]
        sym[f"SPAN{k}"] = tl.span(mesh.blk_d1[k] - mesh.blk_d0[k])
    return ["; generoitu: tools/gfx/logo/build.py (älä muokkaa)"] + [f"{k} = {v}" for k, v in sym.items()]


def fill_chains() -> list[str]:
    """pystysuora XOR-täyttö: X = sarake * 8, A = kertymä, Y = 0 (shy nollaa merkkipuskurin).
    Rivi r: eor E_r,x / sta D_r,x / shy E_r,x. Ketju per puskuri ja pariteetti, sisääntulo rivin kohdalta,
    poistuminen paikkaamalla rts seuraavan saman pariteetin rivin kohdalle."""
    out = ["; generoitu: tools/gfx/logo/build.py (älä muokkaa)"]
    for buf in "AB":
        for p in (0, 1):
            out.append(f"fill{buf}{p}")
            for r in range(p, md.ROWS, 2):
                e, d = erow(r), drow(buf, r)
                out += [f"f{buf}_{r}  eor ${e:04x},x", f"        sta ${d:04x},x",
                        f"        .byte $9c, <${e:04x}, >${e:04x}   ; shy"]
            out.append(f"f{buf}_{md.ROWS + p}  rts")
        ents = [f"f{buf}_{r}" for r in range(md.ROWS + 2)]
        out += [f"fent{buf}_l .byte " + ",".join(f"<{x}" for x in ents[i:i + 1]) for i in range(0)]
        out.append(f"fent{buf}_l")
        for i in range(0, len(ents), 8):
            out.append("        .byte " + ",".join(f"<{x}" for x in ents[i:i + 8]))
        out.append(f"fent{buf}_h")
        for i in range(0, len(ents), 8):
            out.append("        .byte " + ",".join(f">{x}" for x in ents[i:i + 8]))
    return out


SPR = {"A": 0x4400, "B": 0x8400}            # nimen spritet kummassakin VIC-pankissa (osoitin $10..);
#                                             pankki 2: VIC näkee $9000-$9fff merkistö-ROMina, siksi $8400
RIP0, RIPD = 51 + md.Y0 + md.HZ + 3, 4           # heijastuksen aaltoilu: ensimmäinen rasteririvi (viivan alla rivi
#                                                 suoraan), kaistan korkeus (2 juovaa; pariton rivi musta: vaihto siinä)
RIPN = (md.Y0 + md.ROWS + 51 - RIP0) // RIPD      # kaistat kankaan loppuun
RIPC = [3, 5, 6, 7]                                # amplitudiluokat (hires px huipusta huippuun; T3:n tila)
RIPA = [min(len(RIPC) - 1, (k + 1) // 2) for k in range(RIPN)]   # kaistan luokka: syvemmällä isompi (heijastus rivit
#                                                 HZ + 5..HZ + 32 eli kaistat 0-7, alkuperäisen animaation +-3,5 px)
RIPP = [(k * 23) & 63 for k in range(RIPN)]       # kaistan vaihe: aalto kulkee rivien läpi
assert (RIP0 - 51 - md.Y0) % 2 == 0 and RIPD % 2 == 0   # kaista alkaa parillisella rivillä: vaihto edellisellä mustalla


def ripple():
    """$d016-arvot amplitudiluokittain (RIPC), 64 vaihetta (hand.asm ripcalc: (vaihe + RIPP[k]) & 63):
    MC + 40 saraketta + hienovieritys 0..7"""
    import math
    out = []
    for amp in RIPC:
        for ph in range(64):
            xs = round((1 + math.sin(2 * math.pi * ph / 64)) * amp / 2)
            out.append(0x18 | max(0, min(7, xs)))
    return out


def sprites() -> list[str]:
    gl = nm.glyphs()
    out = ["; generoitu: tools/gfx/logo/build.py (nimi: tools/gfx/logo/name.py)"]
    for bank in "AB":
        out += [f"        * = ${SPR[bank]:04x}"]
        for img, _x in gl:
            out += bytes_("", nm.sprite_bytes(img))
    return out


def name_tables() -> list[str]:
    gl = nm.glyphs()
    xs = [x + 24 for _img, x in gl]
    out = bytes_("nm_xl", [x & 255 for x in xs])
    out += [f"NM_XMSB = ${sum(1 << i for i, x in enumerate(xs) if x > 255):02x}"]
    out += bytes_("nm_drop", [(nm.ROW + 50 + d) & 255 for d in nm.DROP])
    out += bytes_("nm_ramp", nm.RAMP)
    out += bytes_("nm_odrop", [(nm.ROW + 50 + d) & 255 for d in nm.ODROP]) + bytes_("nm_ocol", nm.OCOL)
    out += bytes_("nm_ost", [i * nm.OSTEP for i in range(len(nm.TEXT))]) + bytes_("nm_bit", [1 << i for i in range(len(nm.TEXT))])
    return out


def music(out: Path, integrated: bool) -> list[str]:
    if integrated:                          # demossa musiikki on rungon (frame_hook), nollasivu $c0-
        (out / "music.inc").write_text("HAVE_MUSIC = 0\nMUSIC_ZP = $c0\n")
        return []
    r = subprocess.run([sys.executable, "-I", str(ROOT / "tools/music/music.py"), "build", str(out), "--addr",
                        f"{MUSIC_ADDR:04x}", "--zp", "c0", "--buf", "c400"], capture_output=True, text=True)
    if r.returncode:
        print(r.stdout + r.stderr)
        (out / "music.inc").write_text("HAVE_MUSIC = 0\n")
    return []


def syms(labels: Path, out: Path, names: list[str]) -> None:
    """kohtaustaulun sisääntulot (src/scene/alku_glue.asm) VICE-labeleista; ALKU_FREE = kohtauksen kehys, jolla
    logo_go palaa (VICE: purun kuva kopioitu pankkiin 3 ja näkyvissä, EX0 + 12): siitä alku käyttää vain $c000-$c3e7
    ja $e000-$fff9 (purun pyyhkäisy IRQ:na), joten $1a00-$bfff on vapaa. ALKU_LASTWRITE = kohtauksen kehys, jonka
    jälkeen nimiruutu ei kirjoita muistiin (viimeinen lappunen TITLE0 + POPS[-1]; solut valmiit aiemmin): vain
    $d011/$d016/$dd00/$d018 riviltä 250, kunnes Hillnerin S_START ottaa IRQ:n. hil_prep pankkiin 2 vasta sen jälkeen.
    ALKU_TITLE0 = nimiruudun ensimmäinen kehys (pankki 2): siitä purun pankin 3 ruutu ja bittikartta ovat vapaita."""
    lab = {n[1:]: a for _al, a, n in (ln.split() for ln in labels.read_text().splitlines())}
    cs = (labels.parent / "consts.inc").read_text()
    ex0 = int(re.search(r"^EX0 = (\d+)", cs, re.M)[1])
    t0 = int(re.search(r"^TITLE0 = (\d+)", cs, re.M)[1])
    assert int(ttl.logo_t().max()) < ttl.POPS[-1]
    out.write_text("; generoitu: tools/gfx/logo/build.py --syms\n" + "".join(f"{n} = ${lab[n]}\n" for n in names)
                   + f"ALKU_FREE = {ex0 + 12}\nALKU_LASTWRITE = {t0 + ttl.POPS[-1]}\nALKU_TITLE0 = {t0}\n")


def split(prg: Path, out1: Path, out1b: Path, out2: Path) -> None:
    """demon osa kolmeksi tiedostoksi (lataaja ei kirjoita $d000-$dfff:ään): $1a00-$7fff, $8000-$9fff (vapautetaan
    heti logo_go:n jälkeen nimiruudun tieltä, alku_glue.asm) ja taulut 2 $f600-"""
    d = prg.read_bytes()
    base = d[0] | d[1] << 8
    body = d[2:]
    t2 = EBUF + 0x1600
    a = body[:0x8000 - base].rstrip(b"\0")
    ab = body[0x8000 - base:0xA000 - base].rstrip(b"\0")
    b = body[t2 - base:]
    assert not any(body[0xA000 - base:t2 - base]), "tietoa $a000-$f5ff:ssä"
    out1.write_bytes(bytes([base & 255, base >> 8]) + a)
    out1b.write_bytes(bytes([0x00, 0x80]) + ab)
    out2.write_bytes(bytes([t2 & 255, t2 >> 8]) + b)
    print(f"alku: {out1.name} ${base:04x}-${base + len(a) - 1:04x}, {out1b.name} $8000-${0x8000 + len(ab) - 1:04x}, "
          f"{out2.name} ${t2:04x}-${t2 + len(b) - 1:04x}")


def main():
    if sys.argv[1] == "--split":
        split(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5]))
        return
    if sys.argv[1] == "--syms":
        syms(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:])
        return
    out = Path(sys.argv[1])
    integrated = "--integrated" in sys.argv
    out.mkdir(parents=True, exist_ok=True)
    start, length, mstart = timing()
    tl.setup(length)
    m = md.Model()
    (out / "consts.inc").write_text("\n".join(consts(m, start, length, mstart)) + "\n")
    (out / "tables.asm").write_text("\n".join(tables(m) + name_tables()) + "\n")
    (out / "tables2.asm").write_text("\n".join(tables2(m)) + "\n")
    if integrated:
        a, b, c = ttl.split3(ttl.build(out))
        (out / "title.prg").write_bytes(a)
        (out / "titleb.prg").write_bytes(b)
        (out / "titlec.prg").write_bytes(c)
    (out / "sprites.asm").write_text("\n".join(sprites()) + "\n")
    (out / "fill.asm").write_text("\n".join(fill_chains()) + "\n")
    sin, q = big_tables()
    (out / "sintab.asm").write_text("\n".join(sin) + "\n")
    (out / "qtab.asm").write_text("\n".join(q) + "\n")
    music(out, integrated)
    print(f"logo: kohtaus {start}+{length}, biisi {mstart}")


if __name__ == "__main__":
    main()
