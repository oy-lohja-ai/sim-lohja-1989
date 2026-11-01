"""Koko demon kokoaja (integraatio): järjestys src/runko/jarjestys.json:sta, osat omien
osalevyjensä kohtaustauluista, levypuolet ja levynvaihdot. Tulos build/integraatio/: simlohja-<n>.d64 (ja
simlohja-<n>-b.d64), labels, kokoa.txt (puolet, täyttöaste, kohtausten pituudet).

  python3 -I tools/disk/kokoa.py [--tahdistus 30] [--ei-make]

- Järjestys ja valinnat: src/runko/jarjestys.json ("jarjestys": osat, "valinnat": {osa: osalevy}); osa, jota ei ole
  valittu, on osalevy itse.
- Lähtötila: timing/integraatio/ (kompoversion RC10 muistikartoitus muisti.json, latausmittaus mittaus.json ja kernelin
  T kohdat.json, mitattu VICE-ajoista) kopioidaan tyhjään build/integraatio/:hin ennen kokoamista, joten levyt ovat
  samat joka buildissa.
- Osa: src/runko/part-<osalevy>.json (tiedostot, sisääntulot) ja sen kohtaustaulu (names_from, src/scene/<osa>_glue.asm
  tai nimetyn osan taulu, NAMED). Kohtauksen taulu kopioidaan omaan .blockiinsa sellaisenaan, paitsi että
  ensimmäisen kohtauksen jälkeen S_START -> I_START (kello kohtauksen omaan alkukehykseen iskun vaiheessa) ja
  S_SHOW -> I_SHOW (src/runko/kulku.asm). Loppu: S_WAIT loppukehys, ku_cut (pimeys reunuksessa), seuraavan taulu.
- Taulu ei mahdu residenttiin: kohtauksen taulu nimineen on levyllä tiedostona KU<n> (256 t, link.asm PART 97
  lataa sen ikkunaan s_tab); ensimmäinen on residentissä.
- Levypuolet: kohtaukset järjestyksessä puolelle niin kauan kuin mahtuu (664 lohkoa, levynvaihtoruudun tiedostot
  varattuna), sitten levynvaihto (src/runko/levynvaihto.asm, lv_swap<k>) ja seuraava puoli (tunnistetiedosto ensin).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import d64  # noqa: E402
import levy  # noqa: E402
from kopio import kopio  # noqa: E402

ROOT = levy.ROOT
OUT = ROOT / "build/integraatio"
SIDE_BLOCKS = 664
ISKU_VARA = 25                          # lataukset valmiit vähintään näin monta kehystä ennen iskua (oikealla 1541:llä
                                        # kiertovaihe on satunnainen, lataus voi viedä 21 kehystä enemmän)
ISKU_PIDA = 15                          # kernelin vanha T pidetään, kun vara on alle ISKU_VARA + isku + tämä (virran koko
                                        # muuttaa latausaikaa, joten T voisi muuten vuorotella mittauksesta toiseen,
                                        # esim. 11730 vara 16 <-> 11760 vara 56)
TAHDISTUS = 30                          # kohtauksen alku tämän jakson vaiheeseen (isku)
BOOT_RESERVE = 32                       # bootin lohkot (rakennetaan vasta taulujen jälkeen; osalevyillä 28-30)
# MS-DOS-käynnistys RUNin jälkeen (src/runko/dos.asm): payload lataa COMMAND.COMin ennen musiikkia, ja ensimmäisen
# kohtauksen taulu kutsuu DOS_ENDin omien alkulatausten jälkeen (latautuvat DOS-ruudun aikana). Lohkot puolen 1A
# loppuun, joten muiden tiedostojen paikat levyllä eivät muutu.
DOS = {"name": "COMMAND.COM", "label": "f_dos", "boot": True, "src": "build/runko/dos/dos.prg", "pack": True,
       "loppuun": True}
# DOS-ruudun musiikki Appeltrad Act 0: payload lataa sen ennen COMMAND.COMia, soitin $a000-$aeff
ACT0 = {"name": "ACT 0", "label": "f_act0", "boot": True, "bin": "build/runko/act0.bin", "at": "a000", "pack": True,
        "loppuun": True}
DOS_RESERVE = 12 + 12                   # COMMAND.COMin (pakattuna 10) ja ACT 0:n lohkot
DOS_MEM = [(0x5C00, 0x8000), (0xA000, 0xAF00), (0xC000, None)]   # puskuri B, act 0, A $c000- ja ohjelma $e400- (None: dos_top)
DOS_STEP = re.compile(r"^[ \t]*#S_(CALL|SHOW|START)\b", re.M)   # DOS_END ennen ensimmäistä näistä
dos_on = True
TASS = ["64tass", "-C", "-a", "-B", "-q", "-I", "src", "-I", "src/runko", "-I", "tools/krill"]
INCDIRS = ["src/scene", "build/d64", "src", "src/runko", "build/runko"]
# nimetyt osat (link.asm PART 1-5): kohtaustaulu, loppukehys ja taulua edeltävät includet; muilla SCENE_END
NAMED = {
    "alku": {"glue": "src/scene/alku_glue.asm", "end": "TIM_SCENE_ALKU_END"},
    "hillner": {"glue": "src/scene/hil_glue.asm", "end": "HIL_END", "pre": ["src/scene/hil.inc", "build/d64/parts.inc"]},
    "koti": {"glue": "src/scene/koti_glue.asm", "end": "TIM_SCENE_KOTI_END"},
    "greetsit": {"glue": "src/scene/greetsit_glue.asm", "end": "TIM_SCENE_GREETSIT_END"},
    "loppu": {"glue": "src/runko/loppu_glue.asm", "end": "TIM_SCENE_LOPPU_END"},
}
# levynvaihdot (levynvaihto.asm id_names): vaihto k vie puolelle k + 1, jonka ensimmäinen tiedosto tunnistaa sen
SIDE_IDS = [("PUOLI B", "build/runko/kaansi/puolib.prg"), ("LEVY 2", "build/levynvaihto/id_levy2.prg"),
            ("LEVY 2 B", "build/levynvaihto/id_levy2b.prg"), ("LEVY 3", "build/levynvaihto/id_levy3.prg"),
            ("LEVY 3 B", "build/levynvaihto/id_levy3b.prg")]
LV = "build/levynvaihto"
LV1_END = 0x5C00                        # LV1:n esiladattava osa päättyy viimeistään tähän (purun vapaa alue $1a00-$5bff), loppu LV3:na
# siirtymäefektit kohtausten väliin (src/runko/siirtymat.json, part-json "siirtyma"):
# edellinen taulu lataa efektin tiedostot ja käynnistää sen pimennyksen jälkeen, seuraavan I_SHOW lopettaa sen juuri
# ennen omaa ensimmäistä kuvaansa
SIIRTYMAT = {k: {**v, "nimi": k} for k, v in json.loads((ROOT / "src/runko/siirtymat.json").read_text()).items()
             if not k.startswith("_")}


JARJESTYS = ROOT / "src/runko/jarjestys.json"
TILA = ROOT / "timing/integraatio"
TILA_TIEDOSTOT = ("muisti.json", "mittaus.json", "kohdat.json")


def order() -> list[str]:
    """Demon osat järjestyksessä (src/runko/jarjestys.json)."""
    out = json.loads(JARJESTYS.read_text())["jarjestys"]
    if not out:
        raise SystemExit("kokoa: järjestys on tyhjä")
    return out


def choices() -> dict[str, str]:
    """Osien valitut osalevyt (src/runko/jarjestys.json "valinnat")."""
    return dict(json.loads(JARJESTYS.read_text()).get("valinnat", {}))


def seed_state() -> None:
    """Tyhjä build/integraatio/ ja siihen kompoversion tila (timing/integraatio/)."""
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    for n in TILA_TIEDOSTOT:
        shutil.copy2(TILA / n, OUT / n)


MAKE_KAATUI = 3                         # exit-koodi: osan build kaatui


def make(*args: str) -> None:
    """Osan build. Kaatuu myös, jos tulosteessa on "build kesken" (kohtauksen build jatkoi kaatumisen jälkeen
    edellisellä tiedostolla): integraatiossa kaikki osat ovat samasta buildista."""
    p = subprocess.run(["make", "-s", *args], cwd=ROOT, capture_output=True, text=True)
    out = p.stdout + p.stderr
    kesken = [x for x in out.splitlines() if "build kesken" in x]
    if p.returncode or kesken:
        print(f"kokoa: make {' '.join(args)} kaatui:\n{out[-2000:]}", file=sys.stderr)
        sys.exit(MAKE_KAATUI)


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if p.returncode:
        raise SystemExit(f"kokoa: {' '.join(cmd[:3])} ...:\n{(p.stdout + p.stderr)[-3000:]}")


class File:
    """Levyn tiedosto: levy.json-muotoinen kuvaus, levylle menevä data, nimi levyllä (yksikäsitteinen)."""

    def __init__(self, f: dict, name: str):
        self.f, self.name, self.label = f, name, f["label"]
        self.txt = name                 # kirjanpidon nimi (S_LOAD, S_FREE); siirretyllä esilatauksella alkuperäisen
        raw = levy.prg(f)
        self.lo = raw[0] | raw[1] << 8
        self.hi = self.lo + len(raw) - 2
        self.data, self.packed = levy.payload(f)
        self.blocks = levy.blocks(self.data)

    def entry(self) -> dict:
        return {**{k: v for k, v in self.f.items() if k not in ("syms", "consts", "label")}, "name": self.name}

    def block(self) -> list[str]:
        return [f"{self.label} .block", f"packed  = {int(self.packed)}", f"lo      = ${self.lo:04x}",
                f"hi      = ${self.hi:04x}", f'txt     = "{self.txt}"', f"name    = nm_{self.label}", "        .endblock"]

    def alias(self) -> "File":
        """Sama tiedosto edellisen kohtauksen taulussa (esilataus): oma label, sama nimi (S_LOAD tunnistaa nimestä)."""
        a = object.__new__(File)
        a.__dict__.update(self.__dict__, label=f"p_{self.label}")
        return a

    def name_bytes(self) -> str:
        nm = d64.petscii(self.name)
        return f"nm_{self.label} .byte {', '.join(f'${b:02x}' for b in nm)}, 0   ; \"{self.name}\""


class Scene:
    def __init__(self, osa: str, part: str, used: set[str], song_at: int | None = None, root: Path = ROOT,
                 old: str | None = None):
        self.osa, self.part, self.root, self.old = osa, part, root, old   # old: osa vanhasta commitista (root = sen puu)
        self.song_at = song_at          # kerneliosa (spritet): rakennettu alkamaan tästä biisin kehyksestä
        self.alt = (f"build/{part}/demo", f"build/integraatio/{part}-{song_at}/demo") if song_at else None
        self.spec_path = root / f"src/runko/part-{part}.json"
        if root != ROOT:                # vanha versio: polut absoluuttisiksi sen puuhun (levy.py lukee työkopiosta)
            raw = json.loads(self.spec_path.read_text())
            ab = lambda x: str(root / x) if isinstance(x, str) and (x.startswith("build/") or x.startswith("src/")) else x
            raw["labels"] = [ab(x) for x in raw["labels"]]
            raw["dir"] = [{k: ab(v) for k, v in e.items()} if isinstance(e, dict) else e for e in raw["dir"]]
            self.spec_path = OUT / f"part-{part}-vanha.json"
            self.spec_path.write_text(json.dumps(raw, ensure_ascii=False))
        spec = levy.spec(self.spec_path)
        self.labels = [p for p in spec["labels"][1:]]
        named = NAMED.get(part)
        if named:
            self.glue = root / named["glue"]
            self.end = named["end"]
            self.pre = named.get("pre", [])
        else:
            src = json.loads(self.spec_path.read_text())["dir"]
            nf = [e["names_from"] for e in src if isinstance(e, dict) and "names_from" in e]
            if len(nf) != 1:
                raise SystemExit(f"kokoa: {self.spec_path.name}: ei yhtä names_from-kohtaustaulua")
            self.glue = root / nf[0]
            self.end, self.pre = "SCENE_END", []
        self.files: list[File] = []
        self.syms: list[str] = []
        for f in spec["dir"][1:]:
            if not isinstance(f, dict) or f.get("boot") or f.get("seq") or f.get("raw") or "label" not in f:
                continue
            name, k = f["name"], 2
            while name in used:              # sama nimi aiemmassa osassa (vuosi1989/vuosi2026: VUOSI1)
                name, k = f"{f['name'][:15 - len(str(k))]}{k}", k + 1
            used.add(name)
            if self.alt and f.get("src", "").startswith(self.alt[0]):
                f = {**f, "src": f["src"].replace(*self.alt)}
            self.files.append(File(f, name))
            self.syms += levy.sym_lines(f)
        self.text = self.glue.read_text()
        m = re.search(r"^\s*#S_START\s+(.+?)\s*(;.*)?$", self.text, re.M)
        self.start = m.group(1)
        before = set(re.findall(r"^\s*#S_LOAD\s+(f_\w+)", self.text[:m.start()], re.M))
        self.prestart = [f for f in self.files if f.label in before]   # ladataan ennen kohtauksen alkua
        raw = json.loads(self.spec_path.read_text())
        self.jatkuva = raw.get("jatkuva", [])     # osat, joista tämä jatkuu saumatta
        self.siirtyma = raw.get("siirtyma")       # {"efekti", "edellinen"}: siirtymäefekti tämän alkuun
        self.seam_wait = raw.get("jatkuva_odota")   # jatkuvassa alustus vasta N kehystä ennen edellisen loppua
        self.lv_ennen = raw.get("levynvaihto_ennen", False)   # levynvaihto juuri ennen tätä (ellei valittu toisin)
        self.seam_init = raw.get("jatkuva_alustus")   # jatkuvassa alustus vasta sauman jälkeen tällä rutiinilla
        self.vali_pre = False                     # siirtymän (seuraavan "siirtyma", "esilataus") tiedostot tämän aikana
        self.seam_show = raw.get("jatkuva_show")   # [ennen, jälkeen]: jatkuvassa S_SHOWn tilalla edellisen aikana ja kellon vaihdon jälkeen
        self.writes_prev = {p for r in raw.get("kirjoittaa_edellisen_aikana", [])   # jatkuvassa x_init edellisen aikana
                            for p in range(int(r.split("-")[0], 16) >> 8, (int(r.split("-")[1], 16) >> 8) + 1)}
        self.after_cut = raw.get("pimennyksen_jalkeen", [])   # taulun rivit ku_cutin jälkeen (oma latausväli)
        self.tail = {x.upper() for x in raw.get("loppuun", [])}   # tiedostot levypuolen loppuun (hakemisto ja lohkot)
        self.after_mem = [(int(r.split("-")[0], 16), int(r.split("-")[1], 16) + 1)   # muisti, jota latausväli käyttää
                          for r in raw.get("pimennyksen_jalkeen_muisti", [])]       # pyöriessään (koodi rungon IRQ:ssa)
        self.after_pages = {q for lo, hi in self.after_mem for q in range(lo >> 8, ((hi - 1) >> 8) + 1)}  # ei esilatauksia
        self.free_end = {p for r in raw.get("vapaana_lopussa", [])  # osan ilmoittamat vapaat alueet taulun jälkeen
                         for p in range(int(r.split("-")[0], 16) >> 8, (int(r.split("-")[1], 16) >> 8) + 1)}
        self.free_ranges = [(int(r.split("-")[0], 16), int(r.split("-")[1], 16) + 1) for r in raw.get("vapaana_lopussa", [])]
        # esilatausten kehyksiä lohkolta tämän kohtauksen aikana (raskas kerneli jättää lataajalle vähän: greetsien
        # aikana TAULU8S 11 lohkoa 708 kehystä, KOTI3 18 lohkoa 544 kehystä, kun oletus LOAD_FRAMES on 3)
        self.load_rate = raw.get("lataus_kehysta_lohkolle", LOAD_FRAMES)
        self.free_at = raw.get("vapaana_kehyksesta")   # vapaana_lopussa vasta tästä kehyksestä (symboli tai luku)
        # alueet, jotka ovat vapaita jo kesken taulun: [{"ennen": "taulun rivi", "alueet": ["c000-cfff"]}]; esilataus
        # ennen sitä riviä (osan tyhjäkäynti S_WAITissa), kun loppuosan aika ei riitä kaikkiin seuraavan tiedostoihin
        self.mid = [(m["ennen"], {p for r in m["alueet"]
                                  for p in range(int(r.split("-")[0], 16) >> 8, (int(r.split("-")[1], 16) >> 8) + 1)})
                    for m in raw.get("vapaana_kesken", [])]
        self.mid_at: dict[str, str] = {}   # preloads(): esiladattavan tiedoston label -> taulun rivi, jonka eteen
        self.chunk_at: int | None = None   # preloads(): sivu, jolle seuraavan taulu KU<n> esiladataan (I_CHUNK kopioi)
        self.chunk_line: str | None = None  # taulun rivi, jonka eteen se ladataan (vapaana_kesken), None: lopussa
        self.chunk_two = False              # taulu ladataan jo edellisen aikana (jatkuva siirtymä: tämän loppu ladataan)
        self.two: list[File] = []           # preloads(): kahden kohtauksen päästä alkavan tiedostot tämän aikana
        self.wait_at: int | None = None     # forced_beats(): I_SONGAT, alku aikaisintaan tässä biisin kehyksessä
        self.moved: dict[str, File] = {}    # preloads(): siirretty esilataus (label -> tiedosto muualla, kopioidaan)
        self.split: dict[str, list[File]] = {}   # preloads(): osittain esiladattu (label -> palat järjestyksessä)
        self.extra: list[File] = []         # preloads(): osittaisen esilatauksen palat, jotka tämä lataa itse
        # esilatausten arvioitu aika saa ylittää osan lopun näin monta kehystä (taulu: loppu on mustaa ja IRQ ei piirrä
        # lopun jälkeen, joten myöhästynyt ku_cut ei näy; muuten PRE_MARGIN varaa ajan)
        self.over = raw.get("esilataus_yli", 0)
        self.seam_from: int | None = None   # preloads(): edellinen kohtaus, jos siirtymä on jatkuva
        self.music_own = part.startswith("spritet")   # kerneli soittaa biisin itse ja palauttaa osalevyn tilan

    @property
    def blocks(self) -> int:
        return sum(f.blocks for f in self.files)

    def include(self, name: str) -> str:
        for d in [self.glue.parent, self.root / f"build/{self.part}", *(self.root / d for d in INCDIRS)]:
            if (d / name).exists():
                p = str((d / name).resolve())
                return p.replace(*self.alt) if self.alt else p
        raise SystemExit(f"kokoa: {self.glue.name}: include {name} ei löydy")

    def value(self, expr: str) -> int | None:
        """Kehysluku lausekkeesta kuten "s.KAM_LOPPU + 2" taulun ja sen includejen vakioista, muuten None."""
        texts = [self.text] + [Path(self.include(inc)).read_text()
                               for inc in re.findall(r'^\s*\.include\s+"([^"]+)"', self.text, re.M)]

        def sym(m: re.Match) -> str:
            for t in texts:
                v = re.search(rf"^{m.group(1)}\s*=\s*(\$[0-9a-fA-F]+|\d+)\s*(;.*)?$", t, re.M)
                if v:
                    return str(int(v.group(1)[1:], 16) if v.group(1)[0] == "$" else int(v.group(1)))
            raise KeyError(m.group(1))
        try:
            e = re.sub(r"(?:\bs\.)?\b([A-Za-z_]\w*)", sym, expr)
            if not re.fullmatch(r"[\d\s+-]+", e):
                return None
            return sum(int(x) for x in re.findall(r"[+-]?\s*\d+", e.replace(" ", "")))
        except (KeyError, SyntaxError, ValueError):
            return None

    def wait250(self, name: str) -> int:
        """Kohtauksen show-rutiinin alun rivin 250 odotuksen pituus (bit $d011 / bpl / lda $d012 / cmp #n / bne,
        12 t), muuten 0. Latausvälin jälkeen ku_start kutsuu showta jo reunuksessa rivin 250 IRQ:n jälkeen; odotus
        veisi kehyksen ja ku_start hakisi iskun uudelleen (esim. sokeripala alkaisi 87 kehystä myöhemmin)."""
        for inc in re.findall(r'^\s*\.include\s+"([^"]+)"', self.text, re.M):
            m = re.search(rf"^{name}\s*=\s*\$([0-9a-fA-F]+)", Path(self.include(inc)).read_text(), re.M)
            if m:
                at = int(m.group(1), 16)
                for f in self.files:
                    if f.lo <= at < f.hi:
                        b = levy.prg(f.f)[2 + at - f.lo:2 + at - f.lo + 12]
                        ok = (b[:5] == bytes([0x2C, 0x11, 0xD0, 0x10, 0xFB]) and b[5:8] == bytes([0xAD, 0x12, 0xD0])
                              and b[8] == 0xC9 and b[10:12] == bytes([0xD0, 0xF9]))
                        return 12 if ok else 0
        return 0

    def table(self, first: bool) -> list[str]:
        """Kohtauksen oma taulu omassa blockissaan: includet absoluuttisiksi, alku I_STARTiksi (paitsi demon alku)."""
        text = re.sub(r'^(\s*)\.include\s+"([^"]+)"', lambda m: f'{m.group(1)}.include "{self.include(m.group(2))}"',
                      self.text, flags=re.M)
        if self.seam_from is not None:   # jatkuva: edellisen viimeisen kehyksen jälkeen, ei pimennystä eikä S_SHOWta
            prev = f"k{self.seam_from:02d}.s.KU_LOPPU"
            # jatkuva_show [näkymätön, vic]: S_SHOWn osat edellisen aikana ja sen viimeisen kutsun edellä (osalevyllä
            # kuva on näkyvissä kehystä ennen kelloa, joten VIC vaihtuu edellisen viimeiseksi kehykseksi)
            before, vic = self.seam_show or ("", "")
            # jatkuva_odota N: alustus (ensimmäinen S_CALL) vasta edellisen loppu - N:ssä, kun edellisen muisti ei ole
            # enää käytössä. Sokeripala -> koti: koti_init1 nollaa bss:n $4000-$4771 ja nollasivun
            # $02-$9f ja asettaa spritet; sokeripalan taulun häivytyksessä (8 viimeistä kehystä) spritet ovat pois ja
            # taulun IRQ ($4800-) käyttää nollasivusta vain kehyksen alussa asetettavia (muuten jatkuva jäisi jumiin).
            if self.seam_wait:
                text = re.sub(r"^(\s*)(#S_CALL\b)", lambda m: f"{m.group(1)}#S_WAIT {prev} - {self.seam_wait}\n"
                              f"{m.group(1)}{m.group(2)}", text, count=1, flags=re.M)
            # jatkuva_alustus R: edellinen käyttää muistia viimeiseen kehykseensä asti, joten alun S_CALLit jäävät pois
            # ja R (alustus rungon IRQ:n alla ja kiinniotto kelloon) ajetaan sauman jälkeen. Kuoppa-kyltit -> vuosi2026
            # vuosi_init tarvitsee $2400-$3fff:n, jossa kylttien ydin ja moduuli pyörivät.
            if self.seam_init:
                head, sep, tail = text.partition("#S_START")
                text = re.sub(r"^[ \t]*#S_CALL\b.*\n", "", head, flags=re.M) + sep + tail
                text = re.sub(r"^(\s*#S_START\b.*)$", lambda m: m.group(1) + f"\n        #S_CALL {self.seam_init}",
                              text, count=1, flags=re.M)
            text = re.sub(r"^(\s*)#S_START\s+(.+?)\s*(;.*)?$",
                          lambda m: f"valmis\n{m.group(1)}#S_WAIT {prev} - 2\nalkaa"
                                    f"{vic and chr(10) + m.group(1) + '#S_CALL ' + vic}"
                                    f"\n{m.group(1)}#I_SEAM {m.group(2)}\n{m.group(1)}#S_FREE_ALL", text, count=1,
                          flags=re.M)
            text = re.sub(r"^(\s*)#S_SHOW\b.*$", lambda m: before and f"{m.group(1)}#S_CALL {before}", text,
                          flags=re.M)
        elif not first:
            text = re.sub(r"^(\s*)#S_START\b", r"valmis\nalkaa\n\1#I_START", text, count=1, flags=re.M)
            text = re.sub(r"#S_SHOW\b", "#I_SHOW", text)

        for lab, rel in self.moved.items():   # siirretty esilataus: kopio paikalleen (ei latausta)
            text = re.sub(rf"^([ \t]*)#S_LOAD\s+{lab}\b.*$", lambda m: (
                f"{m.group(1)}#S_CALL ${rel.copier:04x}      ; {rel.txt} esiladattu ${rel.lo:04x}-, kopio paikalleen\n"
                f"{m.group(1)}#S_FREE {lab}\n{m.group(1)}#S_HAVE {lab}"), text, count=1, flags=re.M)
        for lab, parts in self.split.items():   # osittain esiladattu: loput palat, kirjanpito koko tiedostolle
            own = [x for x in parts if x in self.extra]
            text = re.sub(rf"^([ \t]*)#S_LOAD\s+{lab}\b.*$", lambda m: "\n".join(
                [f"{m.group(1)}#S_LOAD {x.label}            ; {x.txt}: pala, muut esiladattu" for x in own]
                + [f"{m.group(1)}#S_FREE {x.label if x in own else x.ref}" for x in parts]
                + [f"{m.group(1)}#S_HAVE {lab}"]), text, count=1,
                flags=re.M)
        # ladattu: viimeisen oman latauksen jälkeen ennen valmista (iskuvara levyltä lataamisesta; alustus on CPU:ta
        # eikä riipu asemasta), taulun alussa, jos kaikki esiladattiin
        if (v := text.find("valmis\n")) >= 0:
            loads = list(re.finditer(r"^[ \t]*#S_LOAD\b.*\n", text[:v], re.M))
            at = loads[-1].end() if loads else 0
            text = text[:at] + "ladattu\n" + text[at:]
        at = ([f"        #I_SONGAT {self.song_at}           ; kerneli soittaa biisin tästä kohdasta"] if self.song_at else
              [f"        #I_SONGAT {self.wait_at}           ; iskuvara_pakota (kokoa.py forced_beats)"]
              if self.wait_at else [])
        return ["s       .block", *self.syms, *at, text.rstrip("\n"), f"KU_ALKU = {self.start}",
                f"KU_LOPPU = {self.end}", "        .endblock"]


def t_ok(t: int, seen: int, tahdistus: int = TAHDISTUS) -> bool:
    """Kerneliosan T kelpaa (kernel_song), kun T - seen on ISKU_VARA - ISKU_VARA + isku + ISKU_PIDA (seen + ISKU_VARA
    = aikaisin T: viimeinen lataus + ISKU_VARA ja alustus + 5)."""
    return ISKU_VARA <= t - seen < ISKU_VARA + tahdistus + ISKU_PIDA


def kernel_song(parts: list[tuple[str, str]], tahdistus: int) -> dict[str, int]:
    """Kerneliosat (spritet) soittavat biisin omana SID-virtanaan: virta rakennetaan alkamaan biisin kehyksestä T,
    ja kohtaus odottaa tasan siihen (I_SONGAT). T = ensimmäinen iskun vaiheen kohta (kuten osalevyllä), joka on
    vähintään ISKU_VARA kehystä sen jälkeen, kun taulu mittauksessa saapui kohtauksen alkuun (mittaus.json
    "saapui"), joten oikean 1541:n hitaampikin lataus ehtii. Sama T pidetään (kohdat.json), kun vara on yhä
    ISKU_VARA - ISKU_VARA + 29 + ISKU_PIDA kehystä (virran koko muuttaa latausaikaa)."""
    try:
        m = json.loads((OUT / "mittaus.json").read_text())
        seen = {k: max(v + 5, m.get("ladattu", {}).get(k, v) + ISKU_VARA) - ISKU_VARA for k, v in m["saapui"].items()}
    except (OSError, KeyError, ValueError):
        return {}
    song0 = int(re.search(r"^TIM_SONG_START\s*=\s*(\d+)", (ROOT / "src/gen/timing.inc").read_text(), re.M).group(1))
    p = OUT / "kohdat.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    out = {}
    for osa, part in parts:
        if not part.startswith("spritet") or osa not in seen:
            continue
        start = int(re.search(r"^SCENE_START\s*=\s*(\d+)", (ROOT / f"src/scene/{part}_glue.asm").read_text(), re.M).group(1))
        t = old.get(part)
        if t is None or not t_ok(t, seen[osa], tahdistus):
            t = seen[osa] + ISKU_VARA
            t += (song0 + start - t) % tahdistus
        variant = part[len("spritet-"):] if part != "spritet" else ""
        for k in range(4):                      # virta ei mahdu tästä kohdasta (muisti loppui): seuraava isku, ettei
            tk = t + k * tahdistus              # musiikki hyppää (osalevyn virta alkaa biisin toisesta kohdasta, esim.
            d = ROOT / f"build/integraatio/{part}-{tk}"   # -9570 kehystä); make joka kerta (ei vanhaa merkkiä)
            r = subprocess.run(["make", "-s", "-C", "src/proto/spritet", "demo", f"OUT={d}", f"BIISI={tk}",
                                *([f"VARIANT={variant}"] if variant else [])], cwd=ROOT, capture_output=True, text=True)
            if not r.returncode:
                out[osa] = old[part] = tk
                break
            why = next((x for x in (r.stdout + r.stderr).splitlines() if "muisti loppui" in x), "build kaatui")
            print(f"kokoa: {part} biisin kohdasta {tk} ei onnistu ({why.strip()})"
                  + (", seuraava isku" if k < 3 else ", osalevyn SID-virta (musiikki hyppää)"))
    p.write_text(json.dumps(old) + "\n")
    return out


def relocate(f: File, free: set[int], budget: int, rate: float) -> File | None:
    """Siirretty esilataus (esimerkiksi greetsit -> taulu3b: TAULU8 $6000- osuu greetsien muistiin, ja mustassa
    ladattuna iskuvara jäisi 3 kehykseen): seuraavan kohtauksen alun tiedosto, joka ei mahdu omaan paikkaansa,
    edellisen vapaille sivuille (ei seuraavan omien tiedostojen sivuille, jotta lähde säilyy kopioon asti), perässä
    kopiorutiini (kopio.py). Seuraavan taulussa S_LOAD -> S_CALL rutiini, S_FREE ja S_HAVE (Scene.table). Levylle
    nimellä + kirjain (fresh_name); None: ei mahdu tai ehdi."""
    raw = levy.prg(f.f)[2:]
    size = len(raw) + len(kopio(0, [(0, 0, len(raw))]))
    n = (size + 255) >> 8
    ok = sorted(p for p in free if 0x1a <= p < 0xd0 or 0xe0 <= p < 0xff)
    start = next((p for p in ok if all(p + k in free and (p + k < 0xd0 or p + k >= 0xe0) and p + k < 0xff
                                       for k in range(n))), None)
    if start is None or f.blocks * rate + 5 > budget:
        return None
    lo = start << 8
    path = OUT / "siirto" / f"{f.name.lower()}.prg"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(bytes([lo & 255, lo >> 8]) + raw + kopio(lo + len(raw), [(lo, f.lo, len(raw))]))
    entry = {k: v for k, v in f.f.items() if k not in ("bin", "at", "range", "labels", "syms", "consts")}
    name = fresh_name(f.name)
    rel = File({**entry, "src": str(path.relative_to(ROOT)), "name": name}, name)
    if rel.blocks * rate + 5 > budget:
        return None
    rel.txt, rel.copier = f.txt, lo + len(raw)
    return rel


NAMES_USED: set[int] = set()            # levynimien tiivisteet (Krill): siirron ja palojen nimet eivät saa törmätä


def fresh_name(base: str) -> str:
    """Levynimi base + kirjain (A-Z), jonka Krillin tiiviste ei törmää aiempiin (d64.name_hash)."""
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        name = base[:15] + c
        h = d64.name_hash(bytes(d64.petscii(name)))
        if h not in NAMES_USED:
            NAMES_USED.add(h)
            return name
    raise SystemExit(f"kokoa: {base}: ei vapaata levynimeä")


SPLIT_MIN = 8                           # osittainen esilataus: vähintään näin monta vapaata sivua yhtenäisenä palana


def split_file(f: File, free: set[int]) -> list[tuple[File, bool]]:
    """Osittainen esilataus (tiedosto ei mahdu edellisen vapaille sivuille kokonaan, ja kokonaan pimennyksen jälkeen
    ladattuna väliin jäisi mustaa): tiedosto paloiksi sivurajoilta niin, että vähintään SPLIT_MIN sivun yhtenäiset
    edellisen vapaat jaksot ovat omia palojaan (True: esiladattavissa omaan paikkaansa), loput palat (False) seuraava
    lataa itse. Palat ovat alkuperäisen tiedoston alueita (levy.py range), levyllä nimi + A, B, ...; [] jos ei jaettavaa."""
    if "src" not in f.f or "bin" in f.f:
        return []
    pages = sorted(pg for pg in free if f.lo >> 8 <= pg <= (f.hi - 1) >> 8)
    runs, cur = [], []
    for pg in pages:
        if cur and pg != cur[-1] + 1:
            runs.append(cur)
            cur = []
        cur.append(pg)
    runs = sorted((r for r in runs + ([cur] if cur else []) if len(r) >= SPLIT_MIN), key=len)[-1:]   # suurin: vähiten
    if not runs:                                                    # paloja (levytila: jokainen pala pakataan erikseen)
        return []
    cuts = sorted({f.lo, f.hi} | {max(f.lo, r[0] << 8) for r in runs} | {min(f.hi, (r[-1] + 1) << 8) for r in runs})
    out = []
    for k, (lo, hi) in enumerate(zip(cuts, cuts[1:])):
        name = fresh_name(f.name[:14])
        x = File({**{k2: v for k2, v in f.f.items() if k2 not in ("syms", "consts")}, "name": name,
                  "label": f"{f.label}_{chr(97 + k)}", "range": [f"{lo:04x}", f"{hi:04x}"]}, name)
        x.txt = name
        out.append((x, any(r[0] << 8 <= lo and hi <= (r[-1] + 1) << 8 for r in runs)))
    return out


def forced_need(part: str) -> int | None:
    """part-json "iskuvara_pakota": kehyksiä viimeisestä latauksesta alkuun (true = ISKU_VARA), None: ei pakotettu."""
    need = json.loads((ROOT / f"src/runko/part-{part}.json").read_text()).get("iskuvara_pakota")
    return None if not need else ISKU_VARA if need is True else int(need)


def forced_ok(t: int, lad: int, need: int) -> bool:
    """Pakotetun iskuvaran T kelpaa: alku vähintään need ja enintään need + isku + ISKU_PIDA latauksen jälkeen."""
    return need <= t - lad < need + TAHDISTUS + ISKU_PIDA


def forced_beats(parts: list[tuple[str, str]]) -> dict[str, int]:
    """Pakotettu iskuvara (part-json "iskuvara_pakota": N kehystä, true = ISKU_VARA; vara vähintään 25 myös 295 rpm:n
    asemalla, jolla lataukset venyvät): kohtaus alkaa aikaisintaan ensimmäisellä iskulla, jota ennen sen
    viimeinen lataus valmistui mittauksessa vähintään N kehystä (mittaus.json "ladattu", "biisi_alussa");
    I_SONGAT T, ja sama T pidetään kuten kernelin T (kohdat.json "isku:<osa>"), ettei se vuorottele mittauksesta
    toiseen."""
    try:
        m = json.loads((OUT / "mittaus.json").read_text())
    except (OSError, ValueError):
        return {}
    p = OUT / "kohdat.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    out = {}
    for osa, part in parts:
        need = forced_need(part)
        lad, start = m.get("ladattu", {}).get(osa), m.get("biisi_alussa", {}).get(osa)
        if not need or lad is None or start is None:
            continue
        t = old.get(f"isku:{osa}")
        if t is None or not forced_ok(t, lad, need):   # iskun vaiheessa (start), aikaisintaan lad + need (myös vanhaa
            t = start + -(-(lad + need - start) // TAHDISTUS) * TAHDISTUS   # T:tä aiemmin, kun edeltävät lyhenivät)
        out[osa] = old[f"isku:{osa}"] = t
    p.write_text(json.dumps(old) + "\n")
    return out


def lv_files() -> list[File]:
    """Levynvaihtoruudun tiedostot latausjärjestyksessä: LV1 = koodi ($1a00-) ja LV3:n alku (ruutu $4400, U-taulu)
    LV1_ENDiin asti (esiladattavissa purun vapauttamaan alueeseen), LV3 = LV3:n loppu (bittikartta
    $6000-, mustassa ennen ruutua) ja LV2 = aukikirjoitettu piirto ($8000-, lv_show:n jälkeen ruudun näkyessä)."""
    b1, b3, b2 = ((ROOT / f"{LV}/{n}.prg").read_bytes() for n in ("lv1", "lv3", "lv2"))
    a1, a3 = b1[0] | b1[1] << 8, b3[0] | b3[1] << 8
    if a1 + len(b1) - 2 > a3 or a3 >= LV1_END:
        raise SystemExit("kokoa: LV1 ja LV3 menevät päällekkäin tai LV3 alkaa LV1_ENDin jälkeen")
    cut = min(LV1_END, a3 + len(b3) - 2)
    (OUT / "lv1.prg").write_bytes(b1 + bytes(a3 - a1 - len(b1) + 2) + b3[2:2 + cut - a3])
    (OUT / "lv3.prg").write_bytes(bytes([cut & 255, cut >> 8]) + b3[2 + cut - a3:])
    (OUT / "lv2.prg").write_bytes(b2)
    (OUT / "lv4.prg").write_bytes((ROOT / f"{LV}/lv4.prg").read_bytes())   # biisin pysähdys vaihdon ajaksi ($5f00-)
    names = ["lv1", *(["lv3"] if len(b3) - 2 > cut - a3 else []), "lv4", "lv2"]   # LV3 kokonaan LV1:ssä: ei tiedostoa
    return [File({"name": n.upper(), "label": f"f_{n}", "src": f"build/integraatio/{n}.prg", "pack": True}, n.upper())
            for n in names]


def vali_files(e: dict) -> list[File]:
    """Siirtymäefektin tiedostot (siirtymat.json tiedostot: <dir>/<nimi>.prg) latausjärjestyksessä."""
    return [File({"name": n, "label": f"f_{n.lower()}", "src": f"{e['dir']}/{n.lower()}.prg", "pack": True}, n)
            for n in e["tiedostot"]]


def vali_after(scenes: list[Scene], sides: list[int], i: int) -> list[File]:
    """Kohtauksen i pimennyksen jälkeen (sen taulussa) ladattavat siirtymän tiedostot (ei "esilataus")."""
    e = gap_before(scenes, sides, i)
    return vali_files(e) if e and not e.get("esilataus") else []


def vali_pre(scenes: list[Scene], sides: list[int], i: int) -> list[File]:
    """Kohtauksen i aikana esiladattavat siirtymän tiedostot (siirtymat.json "esilataus")."""
    e = gap_before(scenes, sides, i)
    return vali_files(e) if e and e.get("esilataus") else []


def pre_image(f: File) -> str:
    """Esiladatun tiedoston sisältö muistissa (build/integraatio/esilataus/, polku kokoa.json:iin): edellinen kohtaus
    ei saa kirjoittaa sen päälle."""
    p = OUT / "esilataus" / f"{f.name}.bin"
    p.parent.mkdir(exist_ok=True)
    p.write_bytes(levy.prg(f.f)[2:])
    return str(p.relative_to(ROOT))


def gap_before(scenes: list[Scene], sides: list[int], i: int) -> dict | None:
    """Siirtymäefekti kohtauksen i + 1 alkuun (sen part-json "siirtyma"), kun edellinen on se osa, samalla levypuolella
    eikä siirtymä ole jatkuva; muuten None."""
    if i + 1 >= len(scenes) or not scenes[i + 1].siirtyma or scenes[i + 1].seam_from == i:
        return None
    s = scenes[i + 1].siirtyma
    if s["efekti"] not in SIIRTYMAT:
        raise SystemExit(f"kokoa: {scenes[i + 1].osa}: siirtymää {s['efekti']} ei ole (src/runko/siirtymat.json)")
    e = SIIRTYMAT[s["efekti"]]
    ok = (sides[i] == sides[i + 1] and scenes[i].part.startswith(s["edellinen"])
          and (scenes[i].vali_pre or not e.get("esilataus")))   # esiladattava: vain jos tiedostot mahtuivat edellisen aikaan
    return e if ok else None


def running(scenes: list[Scene], sides: list[int], i: int) -> list[list[int]]:
    """Alueet [lo, hi), jotka pyörivät vielä kohtauksen i taulun jälkeen (kokoa.json "kaynnissa"): oma latausväli kuten
    greetsien ilta, siirtymän tiedostot kuten tahtivalin TV. Siirtymä ilman tiedostoja (filmi) pyörii kohtauksen
    omassa muistissa, joten silloin kohtauksen omat alueet ovat mukana."""
    s, e = scenes[i], gap_before(scenes, sides, i)
    own = ((s.after_cut and i + 1 < len(scenes) and sides[i + 1] == sides[i])
           or (e is not None and not e["tiedostot"] and not e.get("ajoalueet")))   # uusivuosi: vain ajoalueet
    # latausväli, joka ilmoittaa muistinsa (pimennyksen_jalkeen_muisti: greetsien ilta $c000-$cfff), pyörii vain siinä:
    # muut kohtauksen tiedostot eivät ole käynnissä, ja seuraava (taulu3b) näkee ne vapaina
    mine = ([[lo, hi] for lo, hi in s.after_mem] if s.after_cut and s.after_mem else [[f.lo, f.hi] for f in s.files])
    return ((mine if own else []) + [[f.lo, f.hi] for f in (vali_files(e) if e else [])]
            + [[int(lo, 16), int(hi, 16)] for lo, hi in (e or {}).get("ajoalueet", [])])   # siirtymän kopio (crt)


def gap_frames(scenes: list[Scene], i: int) -> int:
    """Arvio kehyksistä kohtauksen i lopusta seuraavan alkuun mittauksesta (seuraava kerneliosa: sen biisin
    kohta; mittaus.json ja edellinen kokoa.json), 0 = ei tiedossa. Enintään 255."""
    try:
        start = json.loads((OUT / "mittaus.json").read_text())["biisi_alussa"][scenes[i].osa]
        prev = {x["osa"]: x["loppu"] - x["alku"] for x in json.loads((OUT / "kokoa.json").read_text())["scenes"]}
        nxt = scenes[i + 1].song_at
        return max(0, min(255, nxt - start - prev[scenes[i].osa])) if nxt else 0
    except (OSError, KeyError, ValueError):
        return 0


def chunk_name(n: int) -> str:
    """Kohtauksen n taulu levyllä: KUA, KUB, ... (kulku.asm ku_chunk kirjoittaa kirjaimen nimeen)."""
    return f"KU{chr(64 + n)}"


def chunk_file(n: int, at: int = 0) -> File:
    """Taulun tiedosto; at = esilatauksen osoite (0: paikka ennen kokoamista, ladataan suoraan ikkunaan)."""
    p = OUT / f"kulku{n}.prg"
    if at or not p.exists():            # koko on aina KU_WIN + 2; sisältö kirjoitetaan kokoamisen jälkeen
        p.write_bytes(bytes([at & 255, at >> 8]) + bytes(256))
    return File({"name": chunk_name(n), "label": f"f_kulku{n}", "src": f"build/integraatio/kulku{n}.prg"}, chunk_name(n))


def plan(scenes: list[Scene], lv: list[File]) -> list[int]:
    """Puoli kullekin kohtaukselle: kohtaukset järjestyksessä, puolet täyteen enintään 664 lohkoa (vaihtoruudun
    tiedostot varattuna puolelle, jota seuraa vaihto). Vaihtokohdat valitaan niin, että vaihdon jälkeen alkavien
    kohtausten alun tiedostot ovat mahdollisimman pienet: niitä ei voi esiladata edellisen aikana (eri puoli),
    joten ne latautuvat levynvaihdon perään."""
    lvb = sum(f.blocks for f in lv)
    n = len(scenes)
    need = [s.blocks + (2 if i else 0) for i, s in enumerate(scenes)]
    cost = [sum(f.blocks for f in s.prestart) for s in scenes]
    best: dict[tuple[int, int], tuple[int, list[int]] | None] = {}

    def solve(i: int, side: int) -> tuple[int, list[int]] | None:
        """kohtaukset i.. puolelta side alkaen: (hinta, puolet)"""
        if (i, side) in best:
            return best[i, side]
        if side > len(SIDE_IDS):
            return None
        used, out = side_reserve(side), None
        for k in range(i, n):           # kohtaukset i..k tälle puolelle
            used += need[k]
            if used + (lvb if k < n - 1 else 0) > SIDE_BLOCKS:
                break
            if k == n - 1:
                cand = (0, [side] * (k - i + 1))
            else:
                rest = solve(k + 1, side + 1)
                cand = (rest[0] + cost[k + 1], [side] * (k - i + 1) + rest[1]) if rest else None
            if cand and (out is None or cand[0] < out[0]):
                out = cand
        best[i, side] = out
        return out

    got = solve(0, 0)
    if got is None:
        raise SystemExit("kokoa: kohtaukset eivät mahdu levypuolille")
    return got[1]


def swap_choice() -> list[dict] | None:
    """Valitut levynvaihdot (ZOO_LEVYNVAIHDOT=polku: {"vaihdot": [{"jalkeen": osa, "teksti": tekstit.yaml:n
    levynvaihdot-rivi}]}), None ilman: vaihto part-jsonin levynvaihto_ennen-osan edellä."""
    p = os.environ.get("ZOO_LEVYNVAIHDOT")
    if not p:
        return None
    return [{"jalkeen": str(v["jalkeen"]), "teksti": int(v["teksti"])} for v in json.loads(Path(p).read_text())["vaihdot"]]


def chosen_sides(scenes: list[Scene], lv: list[File], swaps: list[dict]) -> list[int]:
    """Puoli kullekin kohtaukselle valittujen levynvaihtojen mukaan (vaihto valitun osan jälkeen), lohkot kuten plan():
    virhe, jos osaa ei ole, vaihto on viimeisen jälkeen tai puoli ei mahdu."""
    osat = [s.osa for s in scenes]
    cut = []
    for v in swaps:
        if v["jalkeen"] not in osat[:-1]:
            raise SystemExit(f"kokoa: ZOO_LEVYNVAIHDOT: ei vaihtoa osan {v['jalkeen']} jälkeen (osat {', '.join(osat)})")
        cut.append(osat.index(v["jalkeen"]))
    if sorted(set(cut)) != cut or len(cut) > len(SIDE_IDS):
        raise SystemExit(f"kokoa: ZOO_LEVYNVAIHDOT: vaihdot {[v['jalkeen'] for v in swaps]} eivät ole järjestyksessä "
                         f"tai niitä on yli {len(SIDE_IDS)}")
    sides = [sum(1 for c in cut if c < i) for i in range(len(scenes))]
    lvb = sum(f.blocks for f in lv)
    for side in range(len(cut) + 1):
        ks = [i for i in range(len(scenes)) if sides[i] == side]
        used = side_reserve(side) + sum(scenes[i].blocks + (2 if i else 0) for i in ks) \
            + (lvb if side < len(cut) else 0)
        if used > SIDE_BLOCKS:
            raise SystemExit(f"kokoa: ZOO_LEVYNVAIHDOT: puoli {side + 1} ({scenes[ks[0]].osa} .. {scenes[ks[-1]].osa}) "
                             f"{used} / {SIDE_BLOCKS} lohkoa, ei mahdu")
    return sides


def lv_dir(swaps: list[dict] | None) -> str:
    """Levynvaihtoruutujen rakennus: vaihto k näyttää valitun tekstit.yaml:n levynvaihdot-rivin (levynvaihto.py:n
    tekstijärjestys omaan hakemistoonsa, make levynvaihto LV=... LV_TEKSTIT=...); oletusjärjestys: build/levynvaihto."""
    order = [v["teksti"] for v in swaps or []]
    if order == list(range(1, len(order) + 1)):
        return "build/levynvaihto"
    d = "build/integraatio/lv-" + "-".join(map(str, order))
    make("levynvaihto", f"LV={d}", f"LV_TEKSTIT={','.join(map(str, order))}")
    return d


LOAD_FRAMES = 3                         # esilatauksen arvio kehyksinä lohkoa kohden kohtauksen pyöriessä (väleissä noin 1,6)
PRE_MARGIN = 25


def preloads(scenes: list[Scene], sides: list[int], lv: list[File]) -> tuple[dict[int, list[File]], list[str]]:
    """Seuraavan kohtauksen alun tiedostot (ennen S_STARTia), jotka mahtuvat sivuille, joihin edellinen kohtaus ei
    koske lainkaan (kartoitus muisti.json) tai jotka osa ilmoittaa vapaiksi taulunsa jälkeen
    (part-json "vapaana_lopussa": ["8000-bfff", ...]), ja ehtivät ladata sen omien askelten jälkeen
    (mittaus.json: jaljella = kehyksiä loppuun, kun taulu on tehty). Levynvaihdon edellä samoin levynvaihtoruudun
    tiedostot (LV1, LV3, LV2) järjestyksessä: ruutu tulee aikaisemmin."""
    try:
        free = json.loads((OUT / "muisti.json").read_text())["vapaat"]
        left = json.loads((OUT / "mittaus.json").read_text())["jaljella"]
    except (OSError, KeyError, ValueError):
        return {}, ["esilataukset: ei kartoitusta (muisti.json) tai mittausta, ei esilatauksia"]
    pg = lambda f: set(range(f.lo >> 8, ((f.hi - 1) >> 8) + 1))
    NAMES_USED.update(d64.name_hash(bytes(d64.petscii(n))) for n in
                      [f.name for s in scenes for f in s.files] + [f.name for f in lv]
                      + [chunk_name(k) for k in range(1, len(scenes) + 1)]
                      + ["SIM LOHJA 1989", "INFO", "MUSIIKKI", "COMMAND.COM", *(nm for nm, _ in SIDE_IDS)])

    def freep(s: Scene) -> set[int]:
        """kartoituksen vapaat sivut ja osan ilmoittamat (vapaana_lopussa); kohtauksen loppuun asti pidettyjen (ei
        S_FREE) tiedostojen sivut eivät ole kartoituksesta vapaita (kartoitus voi olla toisesta järjestyksestä, jolloin
        esilataus voisi osua pidetyn tiedoston päälle ja build kaatuisi)"""
        kept = [f for f in s.files if not re.search(rf"^\s*#S_FREE\s+{f.label}\b", s.text, re.M)]   # loppuun asti
        return (set(free.get(s.osa, [])) - {q for f in kept for q in pg(f)}) | s.free_end

    out, rows = {}, []
    for i in range(len(scenes) - 1):
        a, b = scenes[i], scenes[i + 1]
        swap = sides[i] != sides[i + 1]
        if a.osa not in left or (a.osa not in free and not a.free_end):
            continue
        pages, budget, got = freep(a) - a.after_pages, left[a.osa] - PRE_MARGIN + a.over, []
        # pimennyksen jälkeen ladattavan siirtymän sivuille vain tiedosto, jonka päälle se on tehty (vaatii_esiladatut):
        # kartoitus näkee ne vapaina (ilotulitus SPR2B:n vapailla sivuilla)
        e = gap_before(scenes, sides, i)
        vpages = {p for f in vali_after(scenes, sides, i) for p in pg(f)}
        fits = lambda f, ps: pg(f) <= ps and (f.name in (e or {}).get("vaatii_esiladatut", []) or not pg(f) & vpages)
        held = []                       # esiladattavan siirtymän tiedostot (siirtymat.json "esilataus") ensin
        a.vali_pre = True
        if not swap and (e := gap_before(scenes, sides, i)) and e.get("esilataus"):
            held = vali_files(e)
            cost = sum(f.blocks * a.load_rate + 5 for f in held)
            if all(set(range(f.lo >> 8, ((f.hi - 1) >> 8) + 1)) <= pages for f in held) and cost <= budget:
                budget -= cost
            else:
                a.vali_pre, held = False, []
                rows.append(f"VIRHE: {a.osa} -> {b.osa}: siirtymän {e['nimi']} tiedostot eivät mahdu kohtauksen {a.osa} "
                            "vapaille sivuille tai aika ei riitä, väli pimeänä")
        if not swap:                    # kesken taulun vapaat alueet ensin (ladataan aikaisemmin)
            for line, mp in a.mid:
                for f in b.prestart:
                    if f not in got and fits(f, mp):
                        got.append(f)
                        a.mid_at[f.label] = line
        at, end = (a.value(str(a.free_at)), a.value(a.end)) if a.free_at else (None, None)
        if at is not None and end is not None:   # vapaa alue vasta kehyksestä at: aikaa siitä loppuun
            budget = min(left[a.osa], end - at) - PRE_MARGIN
        for f in (lv if swap else b.prestart):
            cost = f.blocks * a.load_rate + 5
            if f in got:
                continue
            if fits(f, pages) and cost <= budget and not any(g.lo < f.hi and f.lo < g.hi for g in got + held):
                got.append(f)
                budget -= cost
            elif swap:                  # levynvaihdon tiedostot vain järjestyksessä (LV3 ja LV2 LV1:n jälkeen)
                break
        if not swap and a.part not in b.jatkuva:   # ei mahdu omaan paikkaansa: muualle ja kopio (jatkuvassa ei: kohde on
            for f in b.prestart:                    # edellisen käytössä)
                if f in got:
                    continue
                taken = {p for g in got + held for p in pg(g)} | {p for g in b.files for p in pg(g)}
                rel = relocate(f, pages - taken - vpages, budget, a.load_rate)   # ei siirtymän sivuille
                if rel:
                    got.append(rel)
                    b.moved[f.label] = rel
                    budget -= rel.blocks * a.load_rate + 5
                elif parts := split_file(f, pg(f) & (pages - {q for g in got + held for q in pg(g)}
                                                       - {q for g in b.files if g is not f for q in pg(g)})):
                    pre = []                # palat, jotka mahtuvat edellisen vapaille sivuille, aikaa riittää
                    for x, free_part in parts:
                        if free_part and x.blocks * a.load_rate + 5 <= budget:
                            pre.append(x)
                            budget -= x.blocks * a.load_rate + 5
                    if pre:
                        got += pre
                        b.split[f.label] = [x for x, _ in parts]
                        b.extra += [x for x, _ in parts if x not in pre]
        if swap:
            if got:
                out[i] = got
            rows.append(f"esilataus {a.osa} -> levynvaihto: {' '.join(f.name for f in got) or '-'}"
                        f" / {' '.join(f.name for f in lv)} (aikaa {left[a.osa]} kehystä)")
            continue
        if got:
            out[i] = got
        if a.part in b.jatkuva:          # jatkuva siirtymä vain, jos kaikki alun tiedostot esiladataan
            ok_pages = pages | {p for _, mp in a.mid for p in mp}
            clash = sorted(b.writes_prev - ok_pages)
            if clash:                    # seuraavan x_init kirjoittaisi edellisen käytössä olevaan muistiin
                rows.append(f"VIRHE: {a.osa} -> {b.osa} jatkuva ei onnistu: {b.osa} kirjoittaa kohtauksen {a.osa} aikana sivuille "
                            + " ".join(f"${x:02x}" for x in clash) + f", joita {a.osa} ei ilmoita vapaiksi "
                            "(part-json vapaana_lopussa tai kartoitus), siirtymä pimennyksellä")   # (esim. KOTI5
            elif len(got) == len(b.prestart):                                           # $5810 asti: JAM)
                b.seam_from = i
            else:
                rows.append(f"VIRHE: {a.osa} -> {b.osa} jatkuva ei onnistu: alun tiedostot eivät mahdu kohtauksen "
                            f"{a.osa} vapaille sivuille tai aika ei riitä, siirtymä pimennyksellä")
        # seuraavan taulu (KU<n>, 256 t) vapaalle sivulle esiladattujen perään: I_CHUNK kopioi sen ikkunaan tiedoston
        # avaamisen sijaan (4-14 kehystä mustassa). Vain kun ku_cutin ja I_CHUNKin välissä ei ladata eikä piirretä.
        # Jatkuvassa myös (koti -> loppu: taulu kodin alussa, kodin lopussa lataus on hidasta).
        # Siirtymä ilman tiedostoja (filmi) piirtää vain edellisen muistiin: taulu esiladataan (taulu2 -> hillner:
        # KUG levyltä mustassa jätti latausvaraksi iskuun 21 kehystä). Esiladatun siirtymän (crt)
        # kanssa myös: sen askeleet vain kutsuvat (IRQ piirtää, pääsäie kopioi taulun).
        # Siirtymä, jonka tiedostot ladataan välissä (ilotulitus), ei estä: sen sivut eivät kelpaa taululle.
        e = gap_before(scenes, sides, i)
        if not a.after_cut:
            vali = vali_files(e) if e and not e.get("esilataus") else []
            used = {p for g in got + held + vali for p in range(g.lo >> 8, ((g.hi - 1) >> 8) + 1)}
            ok = lambda ps: [p for p in ps - used if 0x1a <= p < 0xd0 or 0xe0 <= p < 0xff]
            for line, mp in a.mid:      # kesken taulun ensin: ei loppuosan aikaa
                if ok(mp):
                    a.chunk_at, a.chunk_line = max(ok(mp)), line
                    break
            else:
                if ok(pages) and budget >= 2 * a.load_rate + 5:
                    a.chunk_at = max(ok(pages))
        rows.append(f"esilataus {a.osa} -> {b.osa}: {' '.join(f.name + ('*' if f.label in a.mid_at else '') for f in got) or '-'}"
                    f" / {' '.join(f.name for f in b.prestart)} (aikaa {left[a.osa]} kehystä)"
                    + (" JATKUVA" if b.seam_from == i else "")
                    + (f", taulu {chunk_name(i + 1)} ${a.chunk_at:02x}00" if a.chunk_at is not None else ""))
    # b ehtii ladata c:n alun (ja taulun) puolessa vapaasta ajastaan: kaksi edellä ei tarvita, vaikka c on jatkuva
    # (kuoppa-kyltit 659 kehystä -> vuosi2026: VUOSI12 ja KUL taulu2b:n aikana myöhästyttäisivät kylttien saumaa)
    ample = lambda b, c: 2 * (sum(f.blocks * b.load_rate + 5 for f in c.prestart) + 2 * b.load_rate + 5) <= \
        left.get(b.osa, 0) - PRE_MARGIN
    for i in range(len(scenes) - 2):    # kaksi edellä: seuraavan aikana suunniteltu tiedosto jo tämän aikana, jos sen
        a, b, c = scenes[i:i + 3]       # sivut ovat vapaita tämän lopussa ja koko seuraavan ajan (kartoitus) eikä
        if (len({sides[i], sides[i + 1], sides[i + 2]}) > 1
                or a.osa not in left or b.osa not in free or a.after_cut or gap_before(scenes, sides, i)
                or (len(out.get(i + 1, [])) == len(c.prestart) and (c.seam_from != i + 1 or ample(b, c)))):
            continue                    # seuraavan aika riitä niihin kaikkiin (taulu1 -> kaupungintalo-ikkuna; jatkuva:
                                        # aina, koska sauma tarvitsee kaiken ennen edellisen loppua, vuosi2026 -> greetsit)
        mine = [f for f in out.get(i, [])]
        budget = (left[a.osa] - PRE_MARGIN - sum(f.blocks * a.load_rate + 5 for f in mine if f.label not in a.mid_at)
                  - (2 * a.load_rate + 5 if a.chunk_at is not None and a.chunk_line is None else 0))
        at, end = (a.value(str(a.free_at)), a.value(a.end)) if a.free_at else (None, None)
        if at is not None and end is not None:
            budget = min(budget, end - at - PRE_MARGIN)
        pages_a = freep(a) - a.after_pages - {p for f in mine for p in pg(f)}
        if a.chunk_at is not None and a.chunk_line is not None:   # loppuun valittu taulun sivu siirtyy (alla)
            pages_a.discard(a.chunk_at)
        pages_b = set(free[b.osa]) - {p for f in b.files for p in pg(f)}
        if b.chunk_at is not None:
            pages_b.discard(b.chunk_at)
        for f in list(out.get(i + 1, [])):
            if f.label in b.mid_at:
                continue
            cost = f.blocks * a.load_rate + 5
            if pg(f) <= pages_a & pages_b and cost <= budget:
                a.two.append(f)
                out[i + 1].remove(f)
                budget -= cost
        taken = {p for f in mine + a.two for p in pg(f)}
        if a.two and a.chunk_at in taken and a.chunk_line is None:   # taulun sivu tiedostojen alta pois
            cand = [p for p in pages_a - taken if 0x1a <= p < 0xd0 or 0xe0 <= p < 0xff]
            a.chunk_at = max(cand) if cand else None
        if a.two:                       # seuraavan vapautunut aika puuttuviin (suunnitellut ensin, sitten loput)
            got = out.setdefault(i + 1, [])
            spare = (left[b.osa] - PRE_MARGIN + b.over - sum(f.blocks * b.load_rate + 5 for f in got if f.label not in b.mid_at)
                     - (2 * b.load_rate + 5 if b.chunk_at is not None and b.chunk_line is None else 0))
            for f in c.prestart:
                cost = f.blocks * b.load_rate + 5
                if (f not in got and f not in a.two and f.label not in c.moved and pg(f) <= freep(b)
                        and cost <= spare and not any(g.lo < f.hi and f.lo < g.hi for g in got)):
                    got.append(f)
                    spare -= cost
            used = {p for f in got for p in pg(f)}
            if b.chunk_at in used and b.chunk_line is None:   # taulun sivu uusien tiedostojen alta pois
                cand = [p for p in freep(b) - used if 0x1a <= p < 0xd0 or 0xe0 <= p < 0xff]
                b.chunk_at = max(cand) if cand else None
            if (b.part in c.jatkuva and c.seam_from is None and len(got) + len(a.two) == len(c.prestart)
                    and not (c.writes_prev - freep(b))):   # nyt kaikki ehtivät
                c.seam_from = i + 1
                rows[:] = [r for r in rows if not r.startswith(f"VIRHE: {b.osa} -> {c.osa} jatkuva")]
            rows.append(f"esilataus kaksi edellä {a.osa} -> {c.osa}: {' '.join(f.name for f in a.two)}; "
                        f"{b.osa} -> {c.osa}: {' '.join(f.name for f in got)}")
    # jatkuvan siirtymän taulu kaksi edellä: b lataa seuraavan alun pyöriessään, joten c:n taulu (KU, I_CHUNK kopioi)
    # ladataan jo a:n aikana. Myös kun b on itse jatkuva a:sta (vuosi1989 -> taulu1 -> ikkuna: KUC vuoden aikana, taulun
    # lataukset KT1 ja KT6 valmiit ajoissa). Lopusta alkuun: myöhemmän sauman taulu saa sivun ensin
    # (alku -> vuosi1989 -> taulu1 ei vie sitä), ja c:n jo saama sivu on varattu.
    for i in reversed(range(len(scenes) - 2)):
        a, b, c = scenes[i:i + 3]
        # myös, kun b lataisi taulun kesken omaa tauluaan (chunk_line), vaikka b ehtisi: kesken ladattu taulu viivästää
        # b:n omaa pääsäikeen työtä (koti: KUU ennen f_koti4:ää myöhästyttäisi koti_buildia ja kamera seisoisi omat
        # kehykset 191-196; KUU koti_buildin jälkeen venyttäisi kodin loppua, ja koti -> loppu pimenisi)
        if (c.seam_from != i + 1 or b.chunk_two or len({sides[i], sides[i + 1], sides[i + 2]}) > 1
                or a.after_cut or gap_before(scenes, sides, i) or b.osa not in free
                or (ample(b, c) and b.chunk_line is None)):
            continue
        used = {p for f in out.get(i, []) + a.two + out.get(i + 1, []) + b.files + b.two + c.files for p in pg(f)}
        used |= {a.chunk_at} if a.chunk_at is not None else set()
        used |= {c.chunk_at} if c.chunk_two else set()
        cand = [p for p in (freep(a) - a.after_pages) & set(free[b.osa]) - used
                if 0x1a <= p < 0xd0 or 0xe0 <= p < 0xff]
        if cand:
            b.chunk_at, b.chunk_two, b.chunk_line = max(cand), True, None
            rows.append(f"esilataus kaksi edellä {a.osa} -> {c.osa}: taulu {chunk_name(i + 2)} ${b.chunk_at:02x}00")
    return out, rows


def side_reserve(side: int) -> int:
    """Puolen lohkot ennen kohtauksia: boot, INFO, MUSIIKKI ja COMMAND.COM puolella 1A, muilla tunnistetiedosto."""
    return BOOT_RESERVE + 5 + 12 + (DOS_RESERVE if dos_on else 0) if side == 0 else 2


def dos_hit(s: Scene) -> list[str]:
    """Ensimmäisen kohtauksen ennen DOS_ENDia ladattavat tiedostot, jotka osuisivat DOS-ruudun muistiin."""
    top = levy.labels(ROOT / "build/runko/dos/dos.labels")["dos_top"]
    m = DOS_STEP.search(s.text)
    early = set(re.findall(r"^\s*#S_LOAD\s+(f_\w+)", s.text[:m.start() if m else len(s.text)], re.M))
    return [f.name for f in s.files if f.label in early and any(f.lo < (hi or top) and lo < f.hi for lo, hi in DOS_MEM)]


def chunks(scenes: list[Scene], sides: list[int], lv: list[File], pre: dict[int, list[File]],
) -> tuple[str, str]:
    """kulku0.asm (residentissä) ja kulku_n.asm (payloadin perässä, kokoa.py irrottaa tiedostoiksi)."""
    texts = []
    for i, s in enumerate(scenes):
        last = i == len(scenes) - 1
        files = list(s.files) + s.extra
        body = [f"; {i}: {s.osa}" + (f" ({s.part})" if s.part != s.osa else "") + f", {s.glue.relative_to(ROOT)}",
                f"k{i:02d}    .block"]
        steps = [*s.table(first=i == 0), "oma                             ; kohtauksen omat askeleet tehty (kokoa.json: oma)"]
        if i == 0 and dos_on:           # MS-DOS-käynnistys pyörii alun latausten ajan, sitten kuva pimeäksi
            text = "\n".join(steps)
            m = DOS_STEP.search(text)
            steps = (text[:m.start()] + "        #S_CALL DOS_END               ; MS-DOS-käynnistys loppuun (src/runko/dos.asm)\n"
                     + text[m.start():]).split("\n")
        if i and scenes[i - 1].chunk_at is not None:   # taulu kopioitiin esiladatulta sivulta: sivu vapaa
            steps.insert(0, f"        #S_FREE k{i - 1 - scenes[i - 1].chunk_two:02d}.p_f_kulku{i}")
        mids = [(f, s.mid_at.get(f.label)) for f in pre.get(i, [])]
        if s.chunk_line is not None:
            mids.append((chunk_file(i + 1, s.chunk_at << 8), s.chunk_line))
        for f, line in mids:            # esilataus kesken taulun (vapaana_kesken): seuraavan kohtauksen tiedostoksi
            if line is None:
                continue
            text = "\n".join(steps)
            m = re.search(rf"^[ \t]*{re.escape(line)}", text, re.M)
            if not m:
                raise SystemExit(f"kokoa: {s.osa}: vapaana_kesken: riviä {line!r} ei löydy taulusta")
            files.append(f.alias())
            text = (text[:m.start()] + "S_G.SCENE := S_G.SCENE + 1    ; (S_NEXT) tiedosto kuuluu seuraavalle\n"
                    f"        #S_LOAD p_{f.label}            ; esilataus kesken: {scenes[i + 1].osa}\n"
                    "S_G.SCENE := S_G.SCENE - 1\n" + text[m.start():])
            steps = text.split("\n")
        stub = []
        e = gap_before(scenes, sides, i - 1) if i else None   # siirtymä päättyy juuri ennen ensimmäistä kuvaa
        text = "\n".join(steps)
        show = re.search(r"#I_SHOW\s+(\S+)", text)
        if e and not show and e.get("loppu"):
            raise SystemExit(f"kokoa: {s.osa}: latausväli tarvitsee I_SHOW:n")
        if e:
            prev = f"k{i - 1:02d}"
            text = re.sub(r"^(\s*#I_START\b.*)$", lambda m: m.group(1) + "".join(
                f"\n        #S_FREE {prev}.{f.label}" for f in vali_files(e)), text, count=1, flags=re.M)
        # ku_start kutsuu showta aina reunuksessa rivin 250 IRQ:n jälkeen: shown oma rivin 250 odotus veisi kehyksen ja
        # ku_start hakisi iskun uudelleen (myös ilman siirtymää: taulu2f -> sokeripala 29 seisovaa kehystä)
        skip = s.wait250(show.group(1)) if show else 0
        loppu = e.get("loppu") if e else None      # ilman loppu-rutiinia (filmi) seuraava ottaa näytön alussaan itse
        if show and (loppu or skip):
            text = text.replace(show.group(0), "#I_SHOW vshow", 1)
            stub += ([f"vshow   jsr k{i - 1:02d}.{e['lohko']}.{loppu}            ; siirtymä pois (kuva jää)"] if loppu
                     else ["vshow"])
            stub.append(f"        jmp s.{show.group(1)}" + (f" + {skip}   ; rivin 250 odotus ohi: ku_start kutsuu reunuksessa"
                                                         if skip else ""))
        steps = text.split("\n")
        if s.music_own:                 # kerneli palautti soittimen kohtaan, jonka sen SID-virta päättää
            off = f"{s.song_at} - s.KU_ALKU" if s.song_at else "TIM_SONG_START"
            steps.append(f"        #I_SONG {off}")
        if last:
            steps += ["        #S_WAIT s.KU_LOPPU", "        #S_CALL part_end              ; pimeys ja musiikin häivytys"]
        else:
            steps.append("        #S_NEXT")
            if (pre.get(i) or s.chunk_at is not None) and s.free_ranges:
                if s.free_at:               # osan vapaa alue vapautuu vasta myöhemmin (purku: kyltti leikkaukseen asti)
                    steps.append(f"        #S_WAIT {s.free_at}")
                for f in s.files:           # buildin kirjanpito: osan tiedostot vapaalla alueella eivät ole enää käytössä
                    for lo, hi in s.free_ranges:
                        if f.lo < hi and lo < f.hi:
                            steps.append(f"        #S_FREE_RANGE {f.label}, ${lo:04x}, ${hi:04x}")
            for f in pre.get(i, []):        # seuraavan kohtauksen alun tiedostot tämän aikana (esilataus)
                if f.label in s.mid_at:
                    continue
                files.append(f.alias())
                f.ref = f"k{i:02d}.p_{f.label}"     # osittaisen esilatauksen kirjanpito seuraavan taulussa
                steps.append(f"        #S_LOAD p_{f.label}            ; esilataus: {scenes[i + 1].osa}")
            for f in s.two:                 # kahden kohtauksen päästä alkavan tiedostot (sen kirjanpitoon)
                files.append(f.alias())
                f.ref = f"k{i:02d}.p_{f.label}"
                steps += ["S_G.SCENE := S_G.SCENE + 1    ; tiedosto kuuluu kahden päästä alkavalle",
                          f"        #S_LOAD p_{f.label}            ; esilataus kaksi edellä: {scenes[i + 2].osa}",
                          "S_G.SCENE := S_G.SCENE - 1"]
            if i + 2 < len(scenes) and scenes[i + 1].chunk_two:   # jatkuvan siirtymän taulu kaksi edellä
                ku = chunk_file(i + 2, scenes[i + 1].chunk_at << 8).alias()
                files.append(ku)
                steps += ["S_G.SCENE := S_G.SCENE + 1    ; taulu kuuluu kahden päästä alkavalle",
                          f"        #S_LOAD {ku.label}            ; esilataus kaksi edellä: {scenes[i + 2].osa}:n taulu",
                          "S_G.SCENE := S_G.SCENE - 1"]
            if s.chunk_at is not None and s.chunk_line is None and not s.chunk_two:   # seuraavan taulu esiladattujen
                ku = chunk_file(i + 1, s.chunk_at << 8).alias()                     # perään (ku_chunk kopioi)
                files.append(ku)
                steps.append(f"        #S_LOAD {ku.label}            ; esilataus: {scenes[i + 1].osa}:n taulu")
            # siirtymän tiedostot viimeisenä (S_NEXTin jälkeen: S_FREE_ALL ei vapauta, seuraava vapauttaa); ne ovat
            # hakemiston lopussa, ja seuraava lataus (seuraavan oma) hakee hakemiston alusta kuten ilman siirtymää
            steps += [f"        #S_LOAD {f.label}            ; esilataus: siirtymä" for f in vali_pre(scenes, sides, i)]
            if scenes[i + 1].seam_from != i:   # jatkuvassa seuraava taulu odottaa tämän lopun itse (I_SEAM)
                steps += ["        #S_WAIT s.KU_LOPPU - 2         ; ku_cut odottaa viimeisen kehyksen ja pimentää sen jälkeen",
                          # kerneli (spritet) palaa loppukehyksessä ilman IRQ:ta: ei odotusta kohtauksen kutsulle
                          f"        #S_CALL {'ku_cut2' if s.music_own else 'ku_cut'}", "        #S_FREE_ALL"]
                # latausväli pyörii seuraavan latautuessa: jos seuraavan välissä ladattava tiedosto osuu sen muistiin
                # (esim. spritetin SPR2 $cfff:ään asti osuisi greetsien illan $c400- päälle: JAM), ei latausväliä
                # vain ennen seuraavan ensimmäistä S_CALLia ladattavat: sen jälkeen seuraava on ottanut koneen (spritet
                # spr_hiljaa pysäyttää illan ennen SPR2B:tä $c000-)
                first = scenes[i + 1].text.split("#S_CALL", 1)[0]
                early = set(re.findall(r"#S_LOAD\s+(f_\w+)", first))
                hit = [f.name for f in scenes[i + 1].files if f.label in early and f not in pre.get(i, [])
                       and f not in s.two for lo, hi in s.after_mem if f.lo < hi and lo < f.hi]
                if hit and s.after_cut:
                    print(f"VIRHE: {s.osa} -> {scenes[i + 1].osa}: latausväli pois, {' '.join(hit)} osuu sen muistiin "
                          f"(pimennyksen_jalkeen_muisti), väli pimeänä")
                if sides[i + 1] == sides[i] and not hit:   # osan oma latausväli (part-json "pimennyksen_jalkeen", esim. greetsien ilta)
                    vali = gap_frames(scenes, i)   # {vali}: arvio kehyksistä seuraavan alkuun; #S_CALL_A osoite, arvo:
                    for x in s.after_cut:          # kutsu A = arvo (tynkä taulun perässä)
                        x = x.replace("{vali}", str(vali))
                        m = re.match(r"#S_CALL_A\s+([^,]+),\s*([^;]+?)\s*(;.*)?$", x)
                        if m:
                            stub += [f"cala{len(stub)} lda #{m.group(2)}", f"        jmp {m.group(1)}"]
                            x = f"#S_CALL cala{len(stub) - 2}   {m.group(3) or ''}"
                        steps.append(f"        {x}")
            if e := gap_before(scenes, sides, i):    # siirtymäefekti (siirtymat.json)
                files += vali_files(e)
                steps += [f"{e['lohko']:<8}.block", f'        .include "{(ROOT / e["dir"] / "syms.inc").resolve()}"',
                          "        .endblock", *(f"        {x}" for x in e["askeleet"])]
            if sides[i + 1] != sides[i]:
                files += lv
                # lv_lead: kehyksiä ruudun lopusta seuraavan alkuun (taulu levyltä noin 5, alun tiedostot 3 / lohko + 5,
                # alustus ja varaus 5): ruutu jatkuu, kunnes seuraavan lataus päättyy juuri ennen sen iskua
                lead = 5 + sum(f.blocks * LOAD_FRAMES + 5 for f in scenes[i + 1].prestart) + 5
                # lv_song: biisin kehys - DFRAME, josta lv_swap laskee tahdin alun (sama tahti soi silmukkana)
                stub += [f"lvlead  lda #{min(lead, 255)}", "        sta lv.lv_lead", "        lda ku_song",
                         "        sta lv.lv_song", "        lda ku_song+1", "        sta lv.lv_song+1", "        rts"]
                steps += ["lv      .block", f'        .include "{(ROOT / LV / "syms.inc").resolve()}"', "        .endblock",
                          *(f"        #S_LOAD {f.label}" for f in lv if f.name != "LV2"),   # LV4 ennen lv_show:ta
                          "        #S_CALL lv.lv_init0",                                        # (sirq kutsuu sitä)
                          "        #S_CALL lv.lv_show            ; tausta ja teksti näkyviin, piirto latautuu",
                          "        #S_LOAD f_lv2",
                          "        #S_CALL lvlead                ; vaihtoruutu loppuu seuraavan iskun mukaan, tahti",
                          f"        #S_CALL lv.lv_swap{sides[i]}", "lvret                           ; run_i vaihdon aikana (kokoa.json: vaihdot)",
                          *(f"        #S_FREE {f.label}" for f in lv)]
            page = f" | ${s.chunk_at:02x} << 8" if s.chunk_at is not None else ""
            steps.append(f"        #I_CHUNK ${ord(chunk_name(i + 1)[-1]):02x}{page}         ; {chunk_name(i + 1)}")
        for f in files:
            body += f.block()
        body += steps + stub + [f.name_bytes() for f in files]
        body += [f'        .cerror * - s_tab > KU_WIN, "kokoa: kohtauksen {s.part} taulu ", * - s_tab, " tavua"',
                 "        .endblock"]
        texts.append("\n".join(body))
    head = "; Generoitu: tools/disk/kokoa.py (järjestys src/runko/jarjestys.json).\n"
    # nimettyjen osien yhteiset includet tasolle 0 (hil.inc:n .weak-oletukset eivät saa peittää aikajanaa blockissa)
    pre = [f'        .include "{(ROOT / p).resolve()}"' for p in dict.fromkeys(p for s in scenes for p in s.pre)]
    k0 = head + "\n".join(pre) + "\nKULKU_START = k00.s.KU_ALKU\n" + texts[0] + "\n"
    tail = [head.splitlines()[0], "kulku_tail                              ; payload.bin päättyy tähän"]
    for i, t in enumerate(texts[1:], 1):
        tail += [f"kulku_img{i}", "        .logical s_tab", t, "        .fill s_tab + KU_WIN - *, 0", "        .endlogical"]
    for i in range(len(scenes)):        # kohtausten kehykset raporttiin (labels)
        tail += [f"        .virtual k{i:02d}.s.KU_ALKU", f"ku_alku{i}", "        .endv",
                 f"        .virtual k{i:02d}.s.KU_LOPPU", f"ku_loppu{i}", "        .endv"]
    return k0, "\n".join(tail) + "\n"


def main() -> None:
    global LV, dos_on
    ap = argparse.ArgumentParser()
    ap.add_argument("--tahdistus", type=int, default=TAHDISTUS, help="kohtauksen alku tämän jakson vaiheeseen (isku 30)")
    ap.add_argument("--ei-make", action="store_true", help="osat on jo rakennettu")
    ap.add_argument("--ei-dos", action="store_true", help="ilman MS-DOS-käynnistystä (payload kuten osalevyillä)")
    a = ap.parse_args()
    dos_on = not a.ei_dos
    seed_state()
    ch = choices()
    parts, missing = [], []
    for osa in order():                 # osa, jolla ei vielä ole osalevyä, jätetään pois (raportissa)
        part = ch.get(osa, osa)
        (parts if (ROOT / f"src/runko/part-{part}.json").exists() else missing).append((osa, part))
    for osa, part in missing:
        print(f"kokoa: {osa}: ei osalevyä (src/runko/part-{part}.json), jätetään pois")
    if not a.ei_make:
        for _, p in parts:
            make("part", f"P={p}")
        make("levynvaihto")
        for e in SIIRTYMAT.values():
            make(*([e["make"]] if isinstance(e["make"], str) else e["make"]))
    if dos_on and (not a.ei_make or not (ROOT / DOS["src"]).exists()):
        make("dos")
    used: set[str] = {"SIM LOHJA 1989", "INFO", "MUSIIKKI", DOS["name"], ACT0["name"], "LV1", "LV2", "LV3", "LV4", *(n for n, _ in SIDE_IDS),
                      *(n for e in SIIRTYMAT.values() for n in e["tiedostot"])}
    used |= {chunk_name(i) for i in range(1, len(parts))}
    song_at = kernel_song(parts, a.tahdistus)
    scenes = [Scene(osa, p, used, song_at.get(osa)) for osa, p in parts]
    forced = forced_beats(parts)
    for sc in scenes:
        sc.wait_at = forced.get(sc.osa)
    dos_rows = []
    if dos_on and (hit := dos_hit(scenes[0])):   # ennen DOS_ENDia ladattava osuisi DOS-ruutuun: ilman DOS-osaa
        dos_on = False
        dos_rows = [f"VIRHE: MS-DOS-käynnistys pois: {scenes[0].osa}n {' '.join(hit)} latautuu DOS-ruudun muistiin "
                    f"($5c00-$7fff, $a000-$aeff, $c000-, src/runko/dos.asm) ennen DOS_ENDia"]
        print(dos_rows[0])
    elif dos_on:
        dos_rows = [f"MS-DOS-käynnistys: {DOS['name']} ennen musiikkia, DOS_END ennen kohtauksen {scenes[0].osa} alustusta"]
    swaps = swap_choice()
    if swaps is None and any(s.lv_ennen for s in scenes[1:]):   # part-json levynvaihto_ennen (vaihto
        swaps = [{"jalkeen": scenes[i - 1].osa, "teksti": k + 1}   # Hillnerin jälkeen, ennen taulua 2d)
                 for k, i in enumerate(i for i in range(1, len(scenes)) if scenes[i].lv_ennen)]
    LV = lv_dir(swaps)
    lv = lv_files()
    sides = plan(scenes, lv) if swaps is None else chosen_sides(scenes, lv, swaps)
    pre, pre_rows = preloads(scenes, sides, lv)
    for i in range(len(scenes) - 1):    # siirtymä, joka pyörii seuraavan tiedoston muistissa, vain jos se esiladattiin
        e = gap_before(scenes, sides, i)  # (ilotulitus $c400-: SPR2B ladattuna sen päälle kaataisi)
        got = {f.name for f in pre.get(i, [])}   # tämän taulun esilataukset (askeleet viittaavat p_f_-nimiin)
        if e and (miss := [n for n in e.get("vaatii_esiladatut", []) if n not in got]):
            pre_rows.append(f"VIRHE: {scenes[i].osa} -> {scenes[i + 1].osa}: siirtymä {e['nimi']} vaatii esiladatut "
                            f"{' '.join(miss)}, väli pimeänä")
            scenes[i + 1].siirtyma = None
        elif e and (need := e.get("vaatii_siirtyma")) and (scenes[i].siirtyma or {}).get("efekti") != need:
            pre_rows.append(f"VIRHE: {scenes[i].osa} -> {scenes[i + 1].osa}: siirtymä {e['nimi']} vaatii kohtauksen "
                            f"{scenes[i].osa} alkuun siirtymän {need} (sen muisti), väli pimeänä")
            scenes[i + 1].siirtyma = None
    if swaps is not None:                 # valitut levynvaihdot (ZOO_LEVYNVAIHDOT tai levynvaihto_ennen)
        valinta = ", ".join(f"{v['jalkeen']} jälkeen teksti {v['teksti']}" for v in swaps) or "ei vaihtoja"
        pre_rows = [f"levynvaihdot valinnasta (ZOO_LEVYNVAIHDOT) tai part-jsonista (levynvaihto_ennen): {valinta}",
                    *(f"HUOMIO: {a.osa} -> {b.osa} jatkuva siirtymä on levynvaihto, joten pimennyksellä"
                      for i, (a, b) in enumerate(zip(scenes, scenes[1:])) if sides[i] != sides[i + 1] and a.part in b.jatkuva),
                    *pre_rows]
    k0, kn = chunks(scenes, sides, lv, pre)
    (OUT / "kulku0.asm").write_text(k0)
    (OUT / "kulku_n.asm").write_text(kn)
    main_spec = json.loads((ROOT / "src/runko/levy.json").read_text())
    music = next(e for e in main_spec["dir"] if isinstance(e, dict) and e.get("boot"))
    boot = {"name": "SIM LOHJA 1989", "src": "build/integraatio/boot.prg"}
    levy.names({"inc": "build/integraatio/files.inc", "dir": [boot, music, *([ACT0, DOS] if dos_on else [])]})
    # payload: residentti ja ensimmäinen taulu; muut taulut payloadin perässä irrotetaan tiedostoiksi
    run([*TASS, "-I", "build/integraatio", "-I", "build/runko", "-I", "src/scene", "-I", "build/d64", "-D", "PART=97", "-D", f"KU_BEAT={a.tahdistus}",
         "-b", "--vice-labels", "-l", "build/integraatio/payload.labels", "-o", "build/integraatio/payload.full",
         "src/runko/payload.asm"])
    lab = levy.labels(OUT / "payload.labels")
    full = (OUT / "payload.full").read_bytes()
    cut = lab["kulku_tail"] - 0x1000
    (OUT / "payload.bin").write_bytes(full[:cut])
    win = lab["s_tab"]
    for i in range(1, len(scenes)):
        o = lab[f"kulku_img{i}"] - 0x1000
        at = scenes[i - 1].chunk_at << 8 if scenes[i - 1].chunk_at is not None else win
        (OUT / f"kulku{i}.prg").write_bytes(bytes([at & 255, at >> 8]) + full[o:o + 256])
    run(["python3", "-I", "tools/disk/zx0.py", "boot", "build/integraatio/payload.bin", "1000",
         "build/integraatio/payload.labels", "build/integraatio"])
    run([*TASS, "-I", "build/integraatio", "--vice-labels", "-l", "build/integraatio/boot.labels",
         "-o", "build/integraatio/boot.prg", "src/runko/boot.asm"])
    # levypuolet: tiedostot latausjärjestyksessä, puolen vaihtuessa tunnistetiedosto ensin
    side_dirs: list[list] = [[boot] + [e for e in main_spec["dir"] if isinstance(e, dict) and (e.get("seq") or e.get("boot"))]]
    if dos_on:                          # hakemistossa ennen MUSIIKKIa (latausjärjestys), lohkot puolen loppuun
        side_dirs[0][side_dirs[0].index(music):0] = [ACT0, DOS]
    for i, s in enumerate(scenes):
        if sides[i] >= len(side_dirs):
            nm, src = SIDE_IDS[sides[i] - 1]
            side_dirs.append([{"name": nm, "src": src, "raw": True}])
        # edellisen kohtauksen aikana esiladatut ennen taulua KU<n>: lataukset etenevät levyllä ja hakemistossa
        # eteenpäin (Krill selaa hakemistoa 11 tiedoston paloina vain eteenpäin; taaksepäin taulu latautuisi 44-79
        # kehystä)
        early = [f for f in pre.get(i - 1, []) if f.name not in ("LV1", "LV2", "LV3", "LV4")]
        ku = [chunk_file(i).entry()] if i and not scenes[i - 1].chunk_two else []
        two = scenes[i - 1].two if i else []    # kaksi edellä: edellisen aikana, sen omien esilatausten perässä
        early = early + two
        if i + 1 < len(scenes) and scenes[i].chunk_two:   # jatkuvan siirtymän taulu edellisen aikana
            early = early + [chunk_file(i + 1)]
        k = sum(1 for f in early if f.label in scenes[i - 1].mid_at) if i and scenes[i - 1].chunk_line else len(early)
        before = scenes[i - 2].two if i > 1 else []
        # esiladattava siirtymä (ladataan edellisen viimeisenä): hakemistossa seuraavan esilatausten ja taulun perään,
        # lohkot levyn loppuun (loppuun), joten muiden tiedostojen paikat eivät muutu (raidalla 1 CRT1 siirtäisi
        # puolen B tiedostoja 2 lohkoa, ja kuoppa -> taulu2b, spritet -> sokeripala ja koti -> loppu hidastuisivat
        # iskun yli; hakemiston lopussa Krillin 11 tiedoston puskurin kierto muuttuisi, kuoppa -> taulu2b)
        vali = [{**f.entry(), "loppuun": True} for f in (vali_pre(scenes, sides, i - 1) if i else [])]
        side_dirs[sides[i]] += ([f.entry() for f in early[:k]] + ku + [f.entry() for f in early[k:]]   # latausjärjestys
                                + vali + [f.entry() for f in s.files if f not in early and f not in before
                                            and f.label not in s.moved and f.label not in s.split]
                                + [f.entry() for f in s.extra])   # siirretty tai osittain esiladattu: palat levyllä
        if (e := gap_before(scenes, sides, i)) and not e.get("esilataus"):   # siirtymän tiedostot kohtauksen
            side_dirs[sides[i]] += [f.entry() for f in vali_files(e)]                # jälkeen, ennen seuraavan taulua
        if i + 1 < len(scenes) and sides[i + 1] != sides[i]:
            side_dirs[sides[i]] += [f.entry() for f in lv]
    # part-json "loppuun": tiedostot hakemiston ja levypuolen loppuun, jolloin muiden paikat levyllä ja hakemistossa
    # eivät muutu (muuten esim. kuopan KPN siirtäisi puolen B tiedostoja 3 lohkoa, ja taulu2b -> kuoppa-kyltit -sauman
    # lataukset hidastuisivat 17 kehystä, jolloin sauma pimenisi)
    tail = {n for s in scenes for n in s.tail}
    for k, sd in enumerate(side_dirs):
        moved = [e for e in sd if isinstance(e, dict) and e.get("name") in tail]
        side_dirs[k] = [e for e in sd if e not in moved] + [{**e, "loppuun": True} for e in moved]
    # dirart hakemiston loppuun (DEL-rivit eivät vie lohkoja eivätkä muuta Krillin tiedostopuskuria), B-puolille omansa;
    # piilota: muut kuin boot ja INFO tyyppitavulla 0, joten LOAD"$" + LIST näyttää vain taiteen
    side_dirs[0] += [e for e in main_spec["dir"] if isinstance(e, str)]
    for k in range(1, len(side_dirs), 2):
        side_dirs[k] += main_spec.get("dirart_b", [])
    labels = ["build/integraatio/payload.labels", *dict.fromkeys(p for s in scenes for p in s.labels),
              f"{LV}/lv.labels", *(f"{e['dir']}/{e['labels']}" for e in SIIRTYMAT.values())]
    report = []
    for d in range(0, len(side_dirs), 2):
        spec = {"name": main_spec["name"], "id": main_spec["id"], "out": f"build/integraatio/simlohja-{d // 2 + 1}.d64",
                "labels": labels, "dir": side_dirs[d], "piilota": main_spec.get("piilota", False)}
        if d + 1 < len(side_dirs):
            spec["b"] = {"name": main_spec.get("name_b", main_spec["name"]), "id": main_spec["id"], "dir": side_dirs[d + 1]}
        levy.disk(spec)
        report += (OUT / f"simlohja-{d // 2 + 1}.txt").read_text().splitlines() + [""]
    images = [f"build/integraatio/simlohja-{d // 2 + 1}{'-b' if d % 2 else ''}.d64" for d in range(len(side_dirs))]
    summary = {"exe": images[0], "labels": "build/integraatio/simlohja-1.labels", "images": images,
               "scenes": [{"osa": s.osa, "part": s.part, "puoli": sides[i], "kirjain": chunk_name(i)[-1] if i else "?",
                           "alku": lab[f"ku_alku{i}"], "loppu": lab[f"ku_loppu{i}"], "oma": lab[f"k{i:02d}:oma"] - win,
                           "alkaa": lab.get(f"k{i:02d}:s:alkaa", win) - win,
                           # lataukset ja alustus valmiit (jatkuvassa ennen S_WAIT edellinen loppu - 2): iskuvara
                           "valmis": lab.get(f"k{i:02d}:s:valmis", win) - win,
                           "ladattu": lab.get(f"k{i:02d}:s:ladattu", lab.get(f"k{i:02d}:s:valmis", win)) - win,
                           "jatkuva": s.seam_from is not None,   # edellinen pyörii vielä taulun latautuessa
                           # alueet, jotka pyörivät vielä tämän taulun jälkeen (oma latausväli kuten greetsien ilta tai
                           # tahtivalin TV)
                           "kaynnissa": running(scenes, sides, i),
                           # siirtymän tiedostot, jotka tämän taulu lataa pimennyksen jälkeen (ilotulitus): niiden sivut
                           # eivät ole kohtauksen käyttämiä (muuten SPR2B ei esiladattu ILOT:n alle)
                           "siirtyma_alueet": [[f.lo, f.hi] for f in vali_after(scenes, sides, i)],
                           "osalevy": str((s.root / f"build/part-{s.part}").relative_to(ROOT)) if s.root.is_relative_to(ROOT)
                           else str(s.root / f"build/part-{s.part}"), "vanha": s.old,
                           "tiedostot": [[f.name, f.lo, f.hi] for f in s.files],
                           # siirretyt esilataukset seuraavalle (lähde on vapaa seuraavan aikana, jos koskematon)
                           "siirrot": [[f.lo, f.hi, pre_image(f)] for f in pre.get(i, []) if getattr(f, "copier", None)],
                           "esilataa": [[f.name, f.lo, f.hi, pre_image(f)]
                                        for f in pre.get(i, []) + s.two + (scenes[i - 1].two if i else [])]
                           # siirtymä kirjoittaa muuttujiinsa: ilman sisältöä (pre_image)
                           + [[f.name, f.lo, f.hi] for f in vali_pre(scenes, sides, i)]
                           + ([[chunk_name(i + 1), s.chunk_at << 8, (s.chunk_at + 1) << 8, pre_image(chunk_file(i + 1))]]
                              if s.chunk_at is not None else [])
                           + ([[chunk_name(i + 2), scenes[i + 1].chunk_at << 8, (scenes[i + 1].chunk_at + 1) << 8,
                                pre_image(chunk_file(i + 2))]] if i + 2 < len(scenes) and scenes[i + 1].chunk_two else [])}
                          for i, s in enumerate(scenes)],
               "osoitteet": {k: v for k, v in {**lab, **levy.labels(ROOT / LV / "lv.labels")}.items()
                             if k in ("ku_chunk", "part_end", "clock0", "run_i", "ku_name", "ku_song", "ku_start")
                             or k.startswith("lv_swap")},
               "vaihdot": [{"kohtaus": i, "run_i": lab[f"k{i:02d}:lvret"] - win, "levy": images[sides[i + 1]], "k": sides[i]}
                           for i in range(len(scenes) - 1) if sides[i + 1] != sides[i]],
               "resident_vapaana": lab["res_limit"] - lab["res_end"],
               "dos": dos_on}               # MS-DOS-käynnistys ennen kelloa
    # levynvaihtojen valintaa varten: kohtauksen lohkot (omat tiedostot ja taulu KU), puolen vakio-osa
    # (boot, INFO, MUSIIKKI, LV*, tunnistetiedosto, siirtymät: käytetty - kohtausten lohkot) ja rajat, joilla vaihto käy
    free = [int(m.group(1)) for m in re.finditer(r"^vapaana (\d+) lohkoa", "\n".join(report), re.M)]
    for i, (s, sc) in enumerate(zip(scenes, summary["scenes"])):
        sc["lohkot"] = s.blocks + (2 if i else 0)
    summary["puolet"] = [{"puoli": ["1A", "1B", "2A", "2B", "3A", "3B"][k], "levy": Path(images[k]).name,
                          "lohkot": SIDE_BLOCKS - free[k],
                          "vakio": SIDE_BLOCKS - free[k] - sum(sc["lohkot"] for sc in summary["scenes"] if sc["puoli"] == k)}
                         for k in range(min(len(images), len(free)))]
    summary["vaihto_ok"] = [s.osa for i, s in enumerate(scenes[:-1]) if scenes[i + 1].seam_from != i]
    (OUT / "kokoa.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    write_report(scenes, sides, lab, [f"PUUTTUU (ei osalevyä): {osa}" for osa, _ in missing] + dos_rows + pre_rows + [""] + report
                 + [f"resident vapaana {summary['resident_vapaana']} t"])


def write_report(scenes: list[Scene], sides: list[int], lab: dict[str, int], disks: list[str]) -> None:
    names = ["1A", "1B", "2A", "2B", "3A", "3B"]
    rows = ["Integraatio (tools/disk/kokoa.py): kohtaukset, omat kehykset (osalevyn kello) ja levypuoli", ""]
    total = 0
    for i, s in enumerate(scenes):
        a, b = lab[f"ku_alku{i}"], lab[f"ku_loppu{i}"]
        total += b - a
        rows.append(f"{i:2} {s.osa:<14} {s.part:<18} puoli {names[sides[i]]}  kehykset {a}-{b} ({b - a}, "
                    f"{(b - a) / 50.125:.1f} s)  {s.blocks} lohkoa, {len(s.files)} tiedostoa")
    rows += ["", f"kohtaukset yhteensä {total} kehystä ({total / 50.125 / 60:.2f} min) ilman välejä", "", *disks]
    (OUT / "kokoa.txt").write_text("\n".join(rows) + "\n")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
