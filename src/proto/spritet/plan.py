"""Spritet (samanaikaisten spritejen ennätys): aikataulu ja hostin todennus ennen 6510-koodia.

  python3 -I src/proto/spritet/plan.py OUTDIR [KEHYKSIÄ]

Jokainen laitteistosprite käynnistyy 17 rivin välein katkeamatta myös kehysrajan (rivi 311 -> 0) yli, ja crunch
lyhentää jokaisen instanssin 17 riviin (polku CRUNCH). Koska 312 = 18 x 17 + 6, kehykseen
osuu spriteä kohden 18 tai 19 käynnistystä (19, kun ensimmäinen on riveillä 0-5), ja kaistat siirtyvät 6 riviä
kehyksessä. Vaiheet PHASE porrastettu niin, että joka kehyksessä vähintään kahdella spritellä on 19 käynnistystä:
vähintään 146 käynnistystä kehyksessä.

Kirjoittaa OUTDIRiin VIC-rekisterien alkutilan ja suunnitellut rekisterikirjoitukset sarkaineroteltuna aikajanana:
joka rivi $D017 = 0 syklillä 14 (crunch, jos bitti oli päällä ja kiikku 0) ja $D017 = seuraavan rivin crunch-maski
syklillä 40, käynnistyksen jälkeen Y = seuraava käynnistysrivi.
"""
from __future__ import annotations


PERIOD = 17
CRUNCH = (3, 4, 13, 16)          # crunch-päivitykset (indeksi i = rivi L + 1 + i, kun käynnistys rivillä L)
PHASE = (2, 4, 6, 8, 10, 12, 14, 16)   # käynnistysrivit = PHASE[i] + 17 m (jatkuva aika, rivi 0 = kehys 0)
LINES = 312
