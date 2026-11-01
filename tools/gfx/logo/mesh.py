"""Oy Lohja AI -emblemin verkko ja sen staattinen johdannaisdata.

Verkon käsittely (load_mesh, _edges_of, _grow_order, _components, _inner_faces, _block_order) ja ai_loops kuten
emblemin alkuperäisessä animaatiossa, sellaisinaan tai C64:lle supistettuina. Verkot tools/gfx/logo/data/
(blocks3_lod0.json + diamond_lod0.json: 18 + 6 tahkoa = 24; LOD1:n viisteet olisivat C64:n 80 px kankaalla 1 px:n
suikaleita, jotka kaksinkertaistavat särmät).
"""
from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRIDGE = 160            # virtuaalilinkin enimmäispituus erillisten palikoiden välillä (mallin yksiköt)
INNER_REACH, INNER_PAD = 600, 150


def ai_loops():
    """"AI" kaiverrettuna timantin etutahkoon (puolilävistäjä 467): tasapäinen A (ääriviiva ja
    poikkipalkin alla lovi, reikä omana silmukkanaan) ja I, 361 yksikköä korkea. Silmukat (x, y)
    timantin omassa koordinaatistossa. AI_LEFT = 18 (yhden pikselin vasemmalle) kuten alkuperäisessä animaatiossa."""
    AI_LEFT = 18
    S, xa, gap = 0.95, -60 - AI_LEFT, 48
    h = 380 * S
    y0, y1 = -h / 2, h / 2
    hw, ht, t = 150 * S, 22 * S, 74 * S
    s = (hw - ht) / h
    xl = lambda y: xa - hw + t + s * (y - y0)
    xr = lambda y: xa + hw - t - s * (y - y0)
    yb0 = -95 * S
    yb1 = yb0 + 62 * S
    a = [(xa - hw, y0), (xa - hw + t, y0), (xl(yb0), yb0), (xr(yb0), yb0), (xa + hw - t, y0), (xa + hw, y0),
         (xa + ht, y1), (xa - ht, y1)]
    counter = [(xl(yb1), yb1), (xr(yb1), yb1), (xa, y0 + (hw - t) / s)]
    xi, wi = xa + hw + gap, 74 * S
    i = [(xi, y0), (xi + wi, y0), (xi + wi, y1), (xi, y1)]
    loops = [[(int(round(x)), int(round(y))) for x, y in lp] for lp in (a, counter, i)]
    assert all(abs(x) + abs(y) <= 467 - 60 for lp in loops for x, y in lp), "AI tahkon ulkopuolella"
    return loops


@dataclass
class Mesh:
    local: list            # verteksit: palikat maailmassa, timantti omassa koordinaatistossaan (keskitetty)
    world: list            # kaikki maailmassa (timantti snap-siirrettynä)
    faces: list            # dict: v (4), n (Q14), c (0 etu, 1 viiste, 2 sivu), obj (0 palikat, 1 timantti)
    nb: int                # palikoiden verteksit (timantti alkaa tästä)
    snap: tuple
    edges: list = field(default_factory=list)   # (a, b, f0, f1, start, len): kasvujärjestyksessä, f1 255 = ei
    inner: list = field(default_factory=list)
    vblk: list = field(default_factory=list)    # verteksin palikka laskeutumisjärjestyksessä (0 BL, 1 BR, 2 TL, 3 timantti)
    fill: list = field(default_factory=list)    # tahkon täyttöaika (viivayksiköinä)
    blk_d0: list = field(default_factory=list)
    blk_d1: list = field(default_factory=list)
    dfront: int = 0
    dfc: tuple = ()        # etutahkon kulmat ala, oikea, ylä, vasen
    ai_v: list = field(default_factory=list)    # AI:n kulmat Q14-osina etutahkon lävistäjästä
    ai_e: list = field(default_factory=list)


def load_mesh() -> Mesh:
    b = json.loads((HERE / "data/blocks3_lod0.json").read_text())
    d = json.loads((HERE / "data/diamond_lod0.json").read_text())
    snap = tuple(d["snap_offset"])
    nb = len(b["vertices"])
    local = [tuple(v) for v in b["vertices"]] + [tuple(v) for v in d["vertices"]]
    faces = [dict(f, obj=0) for f in b["faces"]] + [dict(f, obj=1, v=[i + nb for i in f["v"]]) for f in d["faces"]]
    world = local[:nb] + [(x + snap[0], y + snap[1], z + snap[2]) for x, y, z in local[nb:]]
    m = Mesh(local, world, faces, nb, snap)
    _derive(m)
    return m


def _edges_of(faces):
    e = {}
    for fi, f in enumerate(faces):
        vs = f["v"]
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            e.setdefault((min(a, b), max(a, b)), []).append(fi)
    return e


def _find(parent, i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def _grow_order(world, edges):
    parent = list(range(len(world)))
    for a, b in edges:
        parent[_find(parent, a)] = _find(parent, b)
    adj = {i: [] for i in range(len(world))}
    for a, b in edges:
        w = math.dist(world[a], world[b])
        adj[a].append((b, w))
        adj[b].append((a, w))

    def link(i, j):
        w = math.dist(world[i], world[j])
        adj[i].append((j, w))
        adj[j].append((i, w))
    linked = set()
    for i in range(len(world)):
        for j in range(i + 1, len(world)):
            if _find(parent, i) != _find(parent, j) and math.dist(world[i], world[j]) < BRIDGE:
                link(i, j)
                linked |= {_find(parent, i), _find(parent, j)}
    for c in {_find(parent, i) for i in range(len(world))} - linked:
        own = [i for i in range(len(world)) if _find(parent, i) == c]
        lo = min(world[i][1] for i in own)
        for i in (i for i in own if world[i][1] == lo):
            link(i, min((j for j in range(len(world)) if _find(parent, j) != c),
                        key=lambda j: math.dist(world[i], world[j])))
    ymin = min(v[1] for v in world)
    dd = [math.inf] * len(world)
    pq = []
    for i, v in enumerate(world):
        if v[1] == ymin:
            dd[i] = 0.0
            pq.append((0.0, i))
    heapq.heapify(pq)
    while pq:
        x, i = heapq.heappop(pq)
        if x > dd[i]:
            continue
        for j, w in adj[i]:
            if x + w < dd[j]:
                dd[j] = x + w
                heapq.heappush(pq, (dd[j], j))
    assert all(x < math.inf for x in dd), "verteksi, johon ei pääse"
    return dd


def _components(n, edges):
    parent = list(range(n))
    for a, b in edges:
        parent[_find(parent, a)] = _find(parent, b)
    return [_find(parent, i) for i in range(n)]


def _inner_faces(world, faces, comp):
    boxes = {}
    for i, c in enumerate(comp):
        lo, hi = boxes.get(c, ([1e9] * 3, [-1e9] * 3))
        boxes[c] = ([min(a, b) for a, b in zip(lo, world[i])], [max(a, b) for a, b in zip(hi, world[i])])
    out = []
    for f in faces:
        n = [x / 16384 for x in f["n"]]
        own = comp[f["v"][0]]
        if abs(n[2]) > 0.1:
            out.append(0)
            continue
        c = [sum(world[i][k] for i in f["v"]) / len(f["v"]) for k in range(3)]
        hit = 0
        for t in range(10, INNER_REACH, 10):
            p = [c[k] + n[k] * t for k in range(3)]
            for oc, (lo, hi) in boxes.items():
                if oc != own and all(lo[k] - INNER_PAD <= p[k] <= hi[k] + INNER_PAD for k in range(2)):
                    hit = 1
        out.append(hit)
    return out


def _block_order(world, comp, nb):
    ids = sorted(set(comp))

    def centre(c):
        vs = [world[i] for i in range(len(world)) if comp[i] == c]
        return sum(v[0] for v in vs) / len(vs), sum(v[1] for v in vs) / len(vs)
    dia = comp[nb]
    blocks = [c for c in ids if c != dia]
    bl = min(blocks, key=lambda c: centre(c)[0] + centre(c)[1])
    tl = max(blocks, key=lambda c: centre(c)[1])
    br = [c for c in blocks if c not in (bl, tl)][0]
    rank = {bl: 0, br: 1, tl: 2, dia: 3}
    return [rank[c] for c in comp]


def _derive(m: Mesh) -> None:
    emap = _edges_of(m.faces)
    keys = sorted(emap)
    dd = _grow_order(m.world, keys)
    q = lambda v: int(round(v))
    edges = []
    for a, b in keys:
        if dd[b] < dd[a]:
            a, b = b, a
        fs = emap[(min(a, b), max(a, b))] + [255]
        edges.append((a, b, fs[0], fs[1], q(dd[a]), q(math.dist(m.world[a], m.world[b]))))
    edges.sort(key=lambda e: e[4])
    m.edges = edges
    m.fill = [q(max(dd[i] for i in f["v"])) for f in m.faces]
    comp = _components(len(m.world), keys)
    m.inner = _inner_faces(m.world, m.faces, comp)
    m.vblk = _block_order(m.world, comp, m.nb)
    m.blk_d0 = [q(min(dd[i] for i in range(len(m.world)) if m.vblk[i] == k)) for k in range(4)]
    m.blk_d1 = [q(max(e[4] + e[5] for e in edges if m.vblk[e[0]] == k)) for k in range(4)]
    loops = ai_loops()
    m.ai_v = [p for lp in loops for p in lp]
    base = 0
    for lp in loops:
        m.ai_e += [(base + k, base + (k + 1) % len(lp)) for k in range(len(lp))]
        base += len(lp)
    m.dfront = next(i for i, f in enumerate(m.faces) if f["obj"] == 1 and f["n"][2] > 16000)
    fv = m.faces[m.dfront]["v"]
    corner = {(round(m.local[i][0] / 100), round(m.local[i][1] / 100)): i for i in fv}
    r = max(m.local[i][0] for i in fv)
    rr = round(r / 100)
    m.dfc = (corner[(0, -rr)], corner[(rr, 0)], corner[(0, rr)], corner[(-rr, 0)])
    m.ai_v = [(int(round(x * 16384 / (2 * r))), int(round(y * 16384 / (2 * r)))) for x, y in m.ai_v]


if __name__ == "__main__":
    m = load_mesh()
    print(f"{len(m.world)} verteksiä, {len(m.faces)} tahkoa, {len(m.edges)} särmää, sisätahkot "
          f"{[i for i, x in enumerate(m.inner) if x]}, palikat {m.blk_d0} {m.blk_d1}, AI {len(m.ai_v)} kulmaa")
