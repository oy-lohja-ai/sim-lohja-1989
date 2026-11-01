"""Kahden pakopisteen perspektiivi C64-kuville: säteet MC-pikseleille ja tasoleikkaukset.

Katse on vaakasuora (pystyviivat pysyvät pystyssä, arkkitehtuurikuvan tapaan), ja rajaus tehdään
objektiivin siirrolla (shift, hires-px). MC-pikseli on kaksi hires-pikseliä leveä; hires-pikselin
kuvasuhde huomioidaan kertoimella ASPECT.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ASPECT = 1.07


@dataclass(frozen=True)
class Camera:
    pos: tuple
    target: tuple                        # vain vaakasuunta käytetään
    focal: float                         # hires-pikseleinä
    shift: float = 0.0                   # objektiivin siirto ylös (hires-px)
    h: int = 144
    w: int = 160                         # MC-pikseleinä

    def rays(self) -> np.ndarray:
        c, t = np.array(self.pos, float), np.array(self.target, float)
        f = t - c
        f[1] = 0.0
        f /= np.linalg.norm(f)
        r = np.cross(f, [0.0, 1.0, 0.0])
        r /= np.linalg.norm(r)
        up = np.array([0.0, 1.0, 0.0])
        yy, xx = np.mgrid[0:self.h, 0:self.w]
        hx = (2 * xx + 1) - self.w
        hy = self.h / 2 - (yy + 0.5) + self.shift
        d = f * self.focal + r * hx[..., None] + up * hy[..., None] * ASPECT
        return d / np.linalg.norm(d, axis=-1, keepdims=True)

    def plane(self, d: np.ndarray, axis: int, value: float):
        """Säteen ja tason axis = value leikkaus: (t, osumapiste); ohi menevät t = inf."""
        c = np.array(self.pos, float)
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (value - c[axis]) / d[..., axis]
        t = np.where(t > 1e-3, t, np.inf)
        p = c + d * np.where(np.isfinite(t), t, 0)[..., None]
        return t, p


    def project(self, p) -> tuple[float, float]:
        """Maailman piste MC-pikselikoordinaateiksi (x, y)."""
        c, t = np.array(self.pos, float), np.array(self.target, float)
        f = t - c
        f[1] = 0.0
        f /= np.linalg.norm(f)
        r = np.cross(f, [0.0, 1.0, 0.0])
        r /= np.linalg.norm(r)
        v = np.array(p, float) - c
        z = v @ f
        hx = (v @ r) / z * self.focal
        hy = v[1] / z * self.focal / ASPECT
        return (hx + self.w - 1) / 2, self.h / 2 - 0.5 + self.shift - hy


class Tracer:
    """Lähimmän pinnan valinta: take(t, mask, materiaali, u, v)."""

    def __init__(self, cam: Camera):
        self.cam = cam
        self.d = cam.rays()
        h, w = cam.h, cam.w
        self.best = np.full((h, w), np.inf)
        self.mat = np.zeros((h, w), np.int16)
        self.U = np.zeros((h, w))
        self.V = np.zeros((h, w))
        self.X = np.zeros((h, w, 3))

    def take(self, t, m, mid, u, v, p):
        hit = m & (t < self.best)
        self.best = np.where(hit, t, self.best)
        self.mat[hit] = mid
        self.U[hit] = u[hit]
        self.V[hit] = v[hit]
        self.X[hit] = p[hit]
