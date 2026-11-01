"""Torin akseli: vastakuva Sokeripalalta torin yli, sama kamerapaikka joka ajassa.

Sokeripala on torin lounaiskulmassa, Hillnerin kauppatalo (1964) ja sen paikalle noussut Lohjantähti
(1991) koillislaidalla. Kamera on Sokeripalan toisen kerroksen ikkunan korkeudella (4,5 m) noin 70 m
päässä, teleobjektiivilla: kulma (Hillnerin talon kulma = Lohjantähden lasitornin kulma, x = 20 m,
z = 0) osuu ruudun oikeaan kolmannekseen samaan kohtaan molemmissa ajoissa, joten vaihto on kuvaliitos.
Lohjantähti ei mahdu ruutuun vaan rajautuu yli reunojen.
"""
from __future__ import annotations

from .persp import Camera

H, W = 200, 160
CAMERA = Camera(pos=(44.0, 3.2, 34.0), target=(4.0, 3.2, -10.0), focal=330.0, shift=48.0, h=H, w=W)
