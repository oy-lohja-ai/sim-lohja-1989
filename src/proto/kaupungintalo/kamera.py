"""Kamera-ajo patsaalta ikkunan läpi huoneeseen, host-puoli: build.py kutsuu.

Kamera peruuttaa lasittoman ikkunan tasosta huoneeseen. Ikkunan kehys (oikea karmi, välikarmi ja ikkunalauta; vasen
karmi ja ylälista jäävät ruudun ulkopuolelle) on 6510:n spritejä, jotka skaalautuvat pisteen C ympäri kertoimella s
(S0 -> S_LOPPU) ja tulevat ruudun reunoilta. Ikkunan taso on yksi jäykkä kappale: karmit, aukon reuna ja seinä
liikkuvat samalla s:llä (jos vain karmit liikkuisivat ikkunan pysyessä paikallaan, ne lävistäisivät
kaupunginjohtajan pään). Ulkonäkymä (aukio.kla, sama mittakaava kuin ikkunasta) on kymmeniä metrejä kauempana,
joten se ei metrin peruutuksessa skaalaudu. Johtaja, PC ja pöytä ovat kameran takana koko ajon (kamera pysähtyy
ennen kuin ohittaa ne, s = S_LOPPU), joten mikään etualan kohde ei ole liikkuvien karmien kanssa samassa kuvassa:
paikallaan oleva pää ja liikkuva karmi olisi mahdoton syvyysjärjestys kummin päin tahansa. Kehyksessä T_END leikkaus
huoneeseen (s = 1, pankki 1), jossa johtaja pelaa.

Ruutu on bittikartta pankissa 3: alussa koko ruutu on ulkonäkymää, ja 6510 vaihtaa solun seinäksi (SEINA) sitä
mukaa kuin skaalattu ikkuna väistyy sen päältä (paljastus()). Jokainen paljastusraja on palkin alla: odotettu seinä
(odotettu_seina()) lasketaan samoista pyöristetyistä reunoista kuin palkit, joten solu vaihtuu, kun palkki peittää
sen kokonaan, eikä aukon reuna näy palkin ulkopuolella.

Palkkien spritelohkot: 6510 tekee ne alustuksessa (kam_gen) RAMiin $d000-$dfff (VIC-pankki 3 näkee sen) tämän
moduulin lohkolistasta: pystypalkin sarakekuvio näytteistettynä N pikseliin (MC-sprite tai X-laajennettu), leveän
välikarmin alkupää (tumma ja valkoinen raita n pikseliä) ja vaakapalkin rivikuvio T riviin (6510 laskee rivit kuviosta). Joka kehys 6510 laskee
palkkien reunat s:stä ja valitsee lohkon leveyden mukaan; leveä palkki ja vaakapalkki peitetään limittäin
asetelluilla spriteillä (viimeinen oikean reunan mukaan), joten reunat liikkuvat hires-pikselin tarkkuudella.

Host laskee vain taulut: s kehyksittäin, solujen paljastusjärjestys ja kehysten paljastusmäärät, palkkien vakiot,
kanavajonot ja lohkolista. simuloi() käy kaikki kehykset läpi samalla kokonaislukulaskennalla kuin 6510 ja
tarkistaa, että jokainen valittu lohko on olemassa ja kanavat riittävät.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

T_END = 240                         # kehys, jossa ydin leikkaa huoneeseen (osan kehyksinä; build.py PITUUS)
T_MALLI = 240                       # ajo lasketaan tälle pituudelle ja ajetaan T_ENDissä (nopeus T_MALLI / T_END)
ALKUVAIHE = {"": 0, "rajaus": 100}  # vaihtoehto (VARIANT) -> alkuvaiheen pituus: maisema ennen karmeja
RAJAUS_U0 = 0.25                    # rajauksen alussa näkyy neljännes ruudusta patsaan ympäriltä
S0 = 10.5                           # alussa kamera on juuri ikkunan tasossa: välikarmi tulee ruutuun heti
S_LOPPU = 1.95                      # kamera-ajon loppu: kamera on vielä johtajan ja PC:n edessä (ne ovat sen takana),
                                    # joten kuvassa on vain ikkunan taso; kehyksessä T_END leikkaus huoneeseen (s = 1)
REV_MAX = 16                        # kamera.asm KAM_REV_MAX: paljastettavat solut pystytahdissa kehystä kohden
SEINA = 8                           # huoneen seinä (oranssi): paljastus vaihtaa skaalatun ikkunan ulkopuolen tähän
C = (22, 64)                        # skaalauksen keskipiste MC-px (patsas, kameran akseli)
YE_MAX = 210                        # pystypalkin loppu tätä alempana = ruudun alareunan yli
BLK0 = 0xD000                       # lohkot $d000-$dfff (osoitin 64 + lohko)
LAUTA = 112                         # ikkunan alareuna (laudan yläreuna) huoneen kuvassa

# pystypalkit: (nimi, x0, x1 MC-px, alapää rivi, sarakkeiden värit 1:1 huoneen kuvasta, kanavajono)
PYSTY = [
    ("lj", 6, 8, 122, (12, 15), (0,)),                                   # vasen karmi
    ("rj", 63, 69, LAUTA + 8, (15, 1, 15, 1, 15, 12), (1,)),             # oikea karmi laudan alareunaan
    ("mu", 35, 43, LAUTA, (12, 1, 15, 15, 15, 15, 15, 15), (2, 3, 4)),   # välikarmi laudan yläreunaan
]
# vaakapalkit: (nimi, x0, x1, y0, y1 MC-px, rivien värit, kanavajono). Järjestys ylhäältä alas: kanavan kopiot
# Y-järjestyksessä.
VAAKA = [
    ("yl", 8, 63, 8, 18, (15, 15, 15, 15, 15, 15, 12, 15, 12, 12), (6, 5, 4, 3)),   # ylälista
    ("la", 6, 63, 112, 120, (12, 15, 15, 1, 15, 15, 15, 15), (7, 6, 5, 0, 4, 3)),  # lauta oikean karmin sisäreunaan
]
# spritejen MC-värit: %01 = $d025, %10 = oma väri, %11 = $d026
D025, OMA, D026 = 12, 15, 1
KOODI = {12: 1, 15: 2, 1: 3}


def kla_kuva(kla: bytes) -> np.ndarray:
    """Koala värinumeroina 200 x 320 (hires-pikseleinä)."""
    bg = kla[10002]
    bmp = np.frombuffer(kla[2:8002], np.uint8).reshape(25, 40, 8)
    scr = np.frombuffer(kla[8002:9002], np.uint8).reshape(25, 40)
    col = np.frombuffer(kla[9002:10002], np.uint8).reshape(25, 40)
    pal = np.stack([np.full((25, 40), bg, np.uint8), scr >> 4, scr & 15, col & 15], -1)    # (25, 40, 4)
    img = np.zeros((25, 8, 40, 4), np.uint8)
    pal8 = np.repeat(pal[:, :, None, :], 8, 2)                                       # (25, 40, 8, 4)
    for j in range(4):
        koodi = (bmp >> (6 - 2 * j)) & 3                                             # (25, 40, 8): solu, rivi
        img[:, :, :, j] = np.take_along_axis(pal8, koodi[..., None], -1)[..., 0].transpose(0, 2, 1)
    return np.repeat(img.reshape(200, 160), 2, 1)


def odotettu_seina(s8: int) -> np.ndarray:
    """Pikselit (200 x 320), joissa kehyksen s:llä kuuluu näkyä seinä: ikkunan ulkopuolella, kun ikkuna on vasemman
    karmin oikean reunan, oikean karmin vasemman reunan ja laudan yläreunan välissä (samat pyöristetyt reunat kuin
    palkeilla, joten raja on täsmälleen palkin alla; välikarmi ja ylälista ovat ikkunan sisällä)."""
    e = reunat(s8)
    xs, ys = np.arange(320)[None, :], np.arange(200)[:, None]
    return ~((xs >= e["lj"][1]) & (xs < e["rj"][0]) & (ys < e["la"][2]))


def paljastus(H: np.ndarray, C: np.ndarray, ss8: list[int]) -> tuple[list[int], list[int]]:
    """Solujen paljastuskehykset: solu, jossa seinä H ja koosteen alkukuva C eroavat, vaihtuu seinäksi kehyksessä t,
    joka minimoi palkkien ulkopuolella näkyvän virheen (ennen t:tä pikselit, joissa kuuluisi näkyä seinä, jälkeen
    pikselit, joissa kuuluisi näkyä ulkonäkymä; palkit peitto():sta, odotettu seinä samoista reunoista, joten solulla on
    nollavirheen kehysten jakso eikä koko sarake osu samaan kehykseen). Tasatilanteessa kehys, jossa on vähiten
    paljastuksia. Palauttaa (solut järjestyksessä, paljastusmäärä kehyksittäin)."""
    ero = H != C
    ei, rev = np.zeros((T_END, 1000), np.int64), np.zeros((T_END, 1000), np.int64)
    for t in range(T_END):
        huone = odotettu_seina(ss8[t])
        nak = ero & ~peitto(ss8[t], ss8)
        ei[t] = (nak & huone).reshape(25, 8, 40, 8).sum((1, 3)).ravel()
        rev[t] = (nak & ~huone).reshape(25, 8, 40, 8).sum((1, 3)).ravel()
    # virhe, jos solu paljastetaan kehyksessä t (t = T_END: vasta vaihdossa huoneeseen)
    virhe = np.concatenate([np.zeros((1, 1000), np.int64), np.cumsum(ei, 0)]) + \
        np.concatenate([np.cumsum(rev[::-1], 0)[::-1], np.zeros((1, 1000), np.int64)])
    solut = [k for k in range(1000) if ero.reshape(25, 8, 40, 8)[k // 40, :, k % 40, :].any()]
    valit = []
    for k in solut:
        ok = np.nonzero(virhe[:, k] == virhe[:, k].min())[0]
        valit.append((len(ok), int(ok[0]), [int(t) for t in ok], k))
    maara = [0] * (T_END + 1)
    jono = []
    for _n, _t0, ok, k in sorted(valit):
        if T_END in ok:                             # ei tarvitse paljastaa (esim. palkin alla loppuun asti)
            continue
        t = min(ok, key=lambda u: (maara[u], u))
        maara[t] += 1
        jono.append((t, k))
    jono.sort()
    assert max(maara) < 256, max(maara)
    return [k for _, k in jono], maara


# ---------------------------------------------------------------- 6510:n laskenta kokonaisluvuin (simuloi)
def reunamaaritys() -> list[tuple[str, int, int, int]]:
    """Reunat järjestyksessä: (palkki, k, vakio, pohja): e = (pohja < 0 ? 0 : e[pohja]) + vakio + round(k * s).
    Palkin toinen reuna lasketaan ensimmäisestä (leveys * s), jos sen kertoimessa on vähemmän ykkösbittejä."""
    cx, cy = C
    out: list[tuple[str, int, int, int]] = []

    def lisaa(nimi, k_suora, c, k_ketju, pohja):
        if k_ketju is not None and bin(abs(k_ketju)).count("1") < bin(abs(k_suora)).count("1"):
            out.append((nimi, k_ketju, 0, pohja))
        else:
            out.append((nimi, k_suora, c, -1))
    for nimi, x0, x1, ye, *_ in PYSTY:
        i = len(out)
        lisaa(nimi, 2 * (x0 - cx), 2 * cx, None, -1)
        lisaa(nimi, 2 * (x1 - cx), 2 * cx, 2 * (x1 - x0), i)
        lisaa(nimi, ye - cy, cy, None, -1)
    for nimi, x0, x1, y0, y1, *_ in VAAKA:
        i = len(out)
        lisaa(nimi, 2 * (x0 - cx), 2 * cx, None, -1)
        lisaa(nimi, 2 * (x1 - cx), 2 * cx, 2 * (x1 - x0), i)
        lisaa(nimi, y0 - cy, cy, None, -1)
        lisaa(nimi, y1 - cy, cy, y1 - y0, i + 2)
    return out


def reunaindeksi(nimi: str) -> int:
    return next(i for i, r in enumerate(reunamaaritys()) if r[0] == nimi)


def reunat(s8: int) -> dict[str, list[int]]:
    """Palkkien reunat kuten kam_edge (s 8.8)."""
    e: list[int] = []
    for _n, k, c, pohja in reunamaaritys():
        r = (abs(k) * s8 + 128) >> 8
        b = c + (0 if pohja < 0 else e[pohja])
        e.append(b - r if k < 0 else b + r)
    out: dict[str, list[int]] = {}
    for (nimi, *_), v in zip(reunamaaritys(), e):
        out.setdefault(nimi, []).append(v)
    return out


_RAJAT: dict[tuple[str, int], int] = {}


def s_raja(nimi: str, ss8: list[int]) -> int:
    """Palkki voi näkyä vain, kun s:n kokonaisosa < raja (muuten 6510 ohittaa sen reunat)."""
    avain = (nimi, hash(tuple(ss8)))
    if avain not in _RAJAT:
        _RAJAT[avain] = _s_raja(nimi, ss8)
    return _RAJAT[avain]


def _s_raja(nimi: str, ss8: list[int]) -> int:
    vis = []
    for s8 in ss8:
        e = reunat(s8)[nimi]
        if len(e) == 3:
            if e[1] > 0 and e[0] < 320 and e[2] > 0:
                vis.append(s8 >> 8)
        elif e[3] > 0 and e[2] < 200 and e[1] > 0:
            vis.append(s8 >> 8)
    return max(vis) + 1 if vis else 0           # 0: ei koskaan ruudulla (vasen karmi ja ylälista, kun s >= S_LOPPU)


def pysty_tila(x0: int, x1: int, s8: int) -> tuple[str, int]:
    """kam_vbar: (tila, N): 'u' MC-sprite N px, 'x' X-laajennettu N px, 'w' leveä (N = alkupään raidan leveys)."""
    w = x1 - x0
    if w <= 24:
        return "u", (w + 1) >> 1
    if w <= 48:
        return "x", (w + 2) >> 2
    return "w", ((s8 >> 8) + 1) >> 1


def vaaka_tila(y0: int, y1: int) -> tuple[str, int]:
    """T <= 20 riviä tavallisena, muuten Y-laajennettuna (lauta jakaa silloin kanavan oikean karmin kanssa)."""
    t = y1 - y0
    return ("t", t) if t <= 20 else ("y", (t + 1) >> 1)


def leveat(xs: int, xe: int, pw: int) -> list[int]:
    """Limittäiset spritet [xs, xe):lle: xs + pw * i, viimeinen xe - pw."""
    n = max(1, -(-(xe - xs) // pw))
    return [xs + pw * i for i in range(n - 1)] + [xe - pw if n > 1 else xs]


def vaaka_valit(xs: int, xe: int) -> list[tuple[int, int, int]]:
    """kam_hbar: piirrettävä väli (alku, loppu, spriten leveys 48 = X-laajennettu): kapea (6-47) palkki on yksi
    X-laajennettu sprite oikean reunan mukaan (jos xe >= 24), alle 6 jää pois."""
    if xe - xs >= 48:
        return [(xs, xe, 48)]
    return [(xe - 48, xe, 48)] if xe - xs >= 6 and xe >= 24 else []


MUX = [30 + 36 * i for i in range(6)]   # = kamera.asm MUX0, MUX_DY, MUX_N


def peitto(s8: int, ss8: list[int]) -> np.ndarray:
    """Palkkien alue (200 x 320): pystypalkit [x0, x1) x [0, ye), vaakapalkit piirrettävinä väleinä."""
    m = np.zeros((200, 320), bool)
    e = reunat(s8)

    def rect(x0, x1, y0, y1):
        m[max(y0, 0):max(min(y1, 200), 0), max(x0, 0):max(min(x1, 320), 0)] = True
    for nimi, *_r in PYSTY:
        x0, x1, ye = e[nimi]
        ye = min(ye, YE_MAX)
        if (s8 >> 8) < s_raja(nimi, ss8) and x1 > 0 and x0 < 320 and ye > 0:
            rect(x0, x1, 0, ye)
    for nimi, *_r in VAAKA:
        x0, x1, y0, y1 = e[nimi]
        if (s8 >> 8) >= s_raja(nimi, ss8) or not (y1 > 0 and y0 < 200 and x1 > 0):
            continue
        for xs, xe, _pw in vaaka_valit(max(x0, 0), min(x1, 344)):
            rect(xs, xe, y0, y1)
    return m


def simuloi(ss8: list[int]) -> dict[tuple[str, str], set[int]]:
    """Kaikki kehykset: tarvittavat lohkot (palkki, tila) -> N:t. Tarkistaa kanavat: samat laajennukset ja X:n
    yläbitti, enintään 6 kopiota; pystypalkin kopiot vaihtuvat alun jälkeen (sama kuva), muut vasta kun edellinen
    kopio on piirretty: multipleksausrivi edellisen lopun jälkeen ja >= 3 riviä ennen seuraavan alkua."""
    tarve: dict[tuple[str, str], set[int]] = {}
    for s8 in ss8:
        e = reunat(s8)
        kaytto: list[list] = [[] for _ in range(8)]       # (kopioita, X-l, Y-l, Y-rekisteri, vaihtorivi, X:n yläbitti)
        for nimi, *_r, chs in PYSTY:
            x0, x1, ye = e[nimi]
            if (s8 >> 8) >= s_raja(nimi, ss8) or not (x1 > 0 and x0 < 320 and ye > 0):
                continue
            tila, n = pysty_tila(x0, x1, s8)
            tarve.setdefault((nimi, tila), set()).add(n)
            assert x0 >= -24, (nimi, x0)
            ye = min(ye, YE_MAX)
            viim = 51 + ye - 42
            ensin = viim
            while ensin >= 51:
                ensin -= 42
            paikat = leveat(x0, min(x1, 344), 48) if tila == "w" else [x0]
            assert len(paikat) <= len(chs), (nimi, s8)
            for i, p in enumerate(paikat):
                kaytto[chs[i]].append(((viim - ensin) // 42 + 1, tila != "u", True, ensin, viim, (p + 24) >> 8))
        for nimi, *_r, chs in VAAKA:
            x0, x1, y0, y1 = e[nimi]
            if (s8 >> 8) >= s_raja(nimi, ss8) or not (y1 > 0 and y0 < 200 and x1 > 0):
                continue
            tila, n = vaaka_tila(y0, y1)
            assert y0 >= -51 and 51 + y0 < 256, (nimi, y0)
            j = 0
            for xs, xe, pw in vaaka_valit(max(x0, 0), min(x1, 344)):
                tarve.setdefault((nimi, tila), set()).add(n)
                for _p in leveat(xs, xe, pw):
                    assert j < len(chs), (nimi, s8, x0, x1)
                    kaytto[chs[j]].append((1, pw == 48, tila == "y", 51 + y0, 51 + y1, (_p + 24) >> 8))
                    j += 1
        for k in kaytto:
            ok = sum(a[0] for a in k) <= 6 and all(a[1:3] == k[0][1:3] and a[5] == k[0][5] for a in k)
            ok = ok and all(any(a[4] < m and m + 3 < b[3] for m in MUX) for a, b in zip(k, k[1:]))
            assert ok, (s8, kaytto)
    return tarve


def s_taulu(t_a: int = 0) -> list[float]:
    """Kamera peruuttaa ikkunan tasosta huoneeseen: s = S0 kehyksissä 0 - t_a ja S_LOPPU kehyksessä T_END (leikkaus
    huoneeseen kameran yhä liikkuessa). Joka kehys nopein näkyvä suoraan s:stä laskettu reuna liikkuu vähintään pikselin
    (askel >= ceil(256 / k): joka kehys muuttuu). Askelprofiili s:n funktiona on jatkuva: oikean karmin tullessa
    ruutuun (pienin sallittu putoaa, s = b) askel on vain välikarmin pienin sallittu a0 ja pienenee siitä tasaisesti
    pienimpään sallittuun S_LOPPUssa (seinän paljastus osuu tähän jaksoon, joten sen tahti on vaihtoehdoissa sama).
    Ennen b:tä askel kasvaa s:n mukana a0:sta a0 (1 + m):ään S0:ssa: m >= 0 haetaan niin, että s = S_LOPPU
    kehyksessä T_END (pääosassa m = 0, lyhyemmässä vaihtoehdossa ikkuna tulee nopeammin ja hidastuu kuin kamera
    peruuttaisi tasaisesti). Vaihtoehdoissa alkuvaihe t < t_a (maisema) pitää s:n alussa. Ajo lasketaan T_MALLI
    kehykselle ja näytteistetään T_ENDiin: sama ajo T_MALLI / T_END kertaa nopeammin (ikkuna 1,33)."""
    def kmax(s: float) -> float:
        """Näkyvien suoraan s:stä laskettujen reunojen suurin |k| (px / s): ketjutettu reuna voi pyöristyä paikalleen
        samassa kehyksessä kuin pohjansa."""
        e = reunat(int(s * 256))
        k = 1.0
        i = 0
        for nimi, kk, _c, pohja in reunamaaritys():
            v = e[nimi]
            j = i - next(n for n, r in enumerate(reunamaaritys()) if r[0] == nimi)
            i += 1
            if pohja >= 0:
                continue
            lim = 320 if (j < 2) else 200
            if 0 <= v[j] < lim and (len(v) == 3 and v[1] > 0 and v[0] < 320 or len(v) == 4 and v[3] > 0 and v[2] < 200):
                k = max(k, abs(kk))
        return k

    def minimi(s8: int) -> int:
        return -(-256 // int(kmax(s8 / 256)))
    a8, e8 = int(S0 * 256), int(S_LOPPU * 256)
    a0, a1 = minimi(a8), minimi(e8)
    b8 = a8
    while b8 > e8 and minimi(b8 - 1) == a0:
        b8 -= 1

    def aja(m: float) -> list[int]:
        """s 8.8-kokonaislukuina kehyksille 0 ... T_END."""
        ss8 = [a8] * (t_a + 1)
        for _ in range(T_MALLI - t_a):
            s8 = ss8[-1]
            if s8 >= b8:
                ask = a0 * (1 + m * (s8 - b8) / (a8 - b8))
            else:
                ask = a1 + (a0 - a1) * (s8 - e8) / (b8 - e8)
            ss8.append(max(s8 - max(int(ask), minimi(s8)), 128))
        return ss8
    assert aja(0.0)[-1] >= e8, f"T_END {T_END} liian pieni: hitainkin sujuva ajo ehtii S_LOPPUun ennen sitä"
    lo, hi = 0.0, 64.0
    for _ in range(40):
        m = (lo + hi) / 2
        if aja(m)[-1] > e8:
            lo = m
        else:
            hi = m
    ss = [v / 256 for v in aja(hi)]
    if T_MALLI != T_END:                # sama ajo nopeammin: s kehyksessä t = mallin s kehyksessä t * T_MALLI / T_END
        ss = [float(v) for v in np.interp(np.arange(T_END + 1) * T_MALLI / T_END, np.arange(T_MALLI + 1), ss)]
    ss[-1] = S_LOPPU
    return [max(s, S_LOPPU) for s in ss]


def kuvio_px(cols: tuple, n: int) -> list[int]:
    """Sarakekuvio näytteistettynä n pikseliin (vasen reuna, kuten huoneen kuvan sarakkeet), koodeina."""
    return [KOODI[cols[(j * len(cols)) // n]] for j in range(n)]


def tavut(px: list[int]) -> list[int]:
    px = (px + [0] * 12)[:12]
    return [px[4 * b] << 6 | px[4 * b + 1] << 4 | px[4 * b + 2] << 2 | px[4 * b + 3] for b in range(3)]


def rajaus_u(t_a: int) -> list[int]:
    """Rajaus (VARIANT=rajaus): näkyvä alue = ruutu kerrottuna u:lla patsaan kohdan ympäri, u8 = 256 u kasvaa
    U0:sta 255:een alkuvaiheessa (hidastuen 1,45 -> 0,55 kertaa keskinopeus, vähintään 1 kehyksessä, joten reunat
    liikkuvat joka kehys)."""
    u = []
    for t in range(t_a):
        x = t / (t_a - 1)
        v = int(round(RAJAUS_U0 * 256 + (255 - RAJAUS_U0 * 256) * (1.45 * x - 0.45 * x * x)))
        u.append(max(v, u[-1] + 1) if u else v)
    assert u[-1] <= 255, u[-1]
    u[-1] = 255
    return u


def generoi(data: Path, tab: list[str], vak: list[str], dtab: list[str], gen: list[str], inc: list[str],
            ra: list[str], variant: str = "") -> dict:
    """tab: paljastustaulut KT1:n alkuun ($1a00), vak: reunojen vakiot, palkkien tietueet ja kanavajonot (huoneen
    bittikartan perään), dtab: s:n askeleet kehyksittäin ja vakioiden ylätavut KT0:n loppuun, gen: lohkolista (kam_gen)
    ja kanavajonot (KT1), ra: vaihtoehdon alkuvaiheen taulut (KT0)."""
    t_a = ALKUVAIHE[variant]
    ss = s_taulu(t_a)
    ss8 = [min(int(round(s * 256)), 0xFFFF) for s in ss]
    C = (data / "aukio.kla").read_bytes()    # alkukuva: johtaja ja PC ovat kameran takana koko ajon (S_LOPPU)
    solut, maara = paljastus(np.full((200, 320), SEINA), kla_kuva(C), ss8)
    assert max(maara) <= REV_MAX, (max(maara), "seinän paljastus ei ehdi pystytahdissa")
    inc += [f"KAM_SEINA = {SEINA}", f"KAM_TA = {t_a}", f"KAM_VAR = {list(ALKUVAIHE).index(variant)}",
            f"KAM_LOPPU = {T_END}", f"KAM_YE_MAX = {YE_MAX}", f"KAM_D025 = {D025}", f"KAM_D026 = {D026}",
            f"KAM_OMA = {OMA}", f"KAM_REV_N = {len(solut)}", f"KAM_BLK0 = ${BLK0:04x}"]
    ds = [0] + [a - b for a, b in zip(ss8, ss8[1:])]
    assert all(0 <= v < 256 for v in ds), ds
    inc.append(f"KAM_S0 = {ss8[0]}")
    dtab.append("kam_ds  .byte " + ", ".join(str(v) for v in ds))         # s(t) = s(t - 1) - kam_ds[t]
    tab.append("kam_rev_n .byte " + ", ".join(str(v) for v in maara))
    tab.append("kam_rev_lo .byte " + ", ".join(f"${k & 255:02x}" for k in solut))
    hi = [k >> 8 for k in solut] + [0, 0, 0]
    tab.append("kam_rev_hi .byte " + ", ".join(
        f"${hi[i] | hi[i + 1] << 2 | hi[i + 2] << 4 | hi[i + 3] << 6:02x}" for i in range(0, len(solut), 4)))
    # reunat: kam_e[i] = (pohja) + vakio + etumerkki * k * s (X hires-px:nä ruudun vasemmasta reunasta, Y riveinä)
    rm = reunamaaritys()
    assert all(0 <= abs(k) < 128 and -32768 <= c < 32768 for _n, k, c, _p in rm)
    vak.append("kam_eka .byte " + ", ".join(str(abs(k) >> 4) for _n, k, _c, _p in rm))
    vak.append("kam_ekb .byte " + ", ".join(str(abs(k) & 15) for _n, k, _c, _p in rm))
    vak.append("kam_es  .byte " + ", ".join(str(int(k < 0)) for _n, k, _c, _p in rm))
    vak.append("kam_ec  .byte " + ", ".join(str(c & 255) for _n, _k, c, _p in rm))
    dtab.append("kam_ech .byte " + ", ".join(str((c >> 8) & 255) for _n, _k, c, _p in rm))
    vak.append("kam_eb  .byte " + ", ".join(str(p & 255) for _n, _k, _c, p in rm))
    inc.append(f"KAM_REUNOJA = {len(rm)}")
    # lohkot: ensin pystypalkkien (3 tavua, kaikki 21 riviä samat), sitten vaakapalkkien (21 rivitavua)
    tarve = simuloi(ss8)
    pv, hv, chs = [], [], []
    vblk, hblk = [], []

    def vali(nimi: str, tila: str) -> tuple[int, int]:
        ns = tarve.get((nimi, tila), set())
        return (min(ns), max(ns)) if ns else (1, 0)
    for nimi, x0, x1, ye, cols, jono in PYSTY:
        offs = []
        for tila in ("u", "x", "w"):
            n0, n1 = vali(nimi, tila)
            offs.append((64 + len(vblk) - n0) & 255)
            for n in range(n0, n1 + 1):
                if tila == "w":
                    tasa = next(k for k in range(len(cols)) if len(set(cols[k:])) == 1)
                    px = [KOODI[c] for c in cols[:tasa] for _ in range(n)]
                    px += [KOODI[cols[-1]]] * (12 - len(px))
                    assert len(px) == 12, (nimi, n)
                    vblk.append(tavut(px))
                else:
                    vblk.append(tavut(kuvio_px(cols, n)))
        tasa_blk = 0
        if (nimi, "w") in tarve:
            tasa_blk = 64 + len(vblk)
            vblk.append(tavut([KOODI[cols[-1]]] * 12))
        pv.append(f"        .byte {s_raja(nimi, ss8)}, {reunaindeksi(nimi)}, {offs[0]}, {offs[1]}, {offs[2]}, "
                  f"{tasa_blk}, {len(chs)}     ; {nimi}")
        chs += list(jono)
    nv = len(vblk)
    ghk: list[int] = []
    for nimi, x0, x1, y0, y1, rws, jono in VAAKA:
        offs = []
        k0 = len(ghk)
        ghk += [KOODI[c] * 0x55 for c in rws]
        for tila in ("t", "y"):
            n0, n1 = vali(nimi, tila)
            offs.append((64 + nv + len(hblk) - n0) & 255)
            for n in range(n0, n1 + 1):
                hblk.append([k0, len(rws), n])          # kam_gen: rivi r < n = kuvio[r * len / n]
        hv.append(f"        .byte {s_raja(nimi, ss8)}, {reunaindeksi(nimi)}, {offs[0]}, {offs[1]}, {len(chs)}     ; {nimi}")
        chs += list(jono)
    assert nv + len(hblk) <= 64, (nv, len(hblk))
    vak.append("; pystypalkit: s-raja, ensimmäinen reuna, lohkon siirto tiloille u/x/w, tasainen lohko, kanavajono")
    vak.append("kam_pv")
    vak += pv
    vak.append("; vaakapalkit: s-raja, ensimmäinen reuna, lohkon siirto tiloille t/y, kanavajono")
    vak.append("kam_hv")
    vak += hv
    if variant == "rajaus":                     # rajauksen mustat sivut: kanava 0 vasen, 1-6 oikea
        inc.append(f"KAM_MASKCS = {len(chs)}")
        chs += [1, 2, 3, 4, 5, 6]
        ra.append("kam_u   .byte " + ", ".join(map(str, rajaus_u(t_a))))
    gen.append("kam_chs .byte " + ", ".join(map(str, chs)))
    inc.append(f"KAM_NPV = {len(PYSTY)}")
    inc.append(f"KAM_NHV = {len(VAAKA)}")
    gen.append(f"KAM_NV = {nv}")
    gen.append(f"KAM_NH = {len(hblk)}")
    gen.append("kam_gv  .byte " + ", ".join(f"${b:02x}" for t in vblk for b in t))
    gen.append("kam_gh  .byte " + ", ".join(str(b) for t in hblk for b in t))
    gen.append("kam_ghk .byte " + ", ".join(f"${b:02x}" for b in ghk))
    return {"solut": len(solut), "max_kehyksessa": max(maara), "lohkoja": nv + len(hblk), "s0": ss[0],
            "s_puoli": ss[T_END // 2], "kooste": C}
