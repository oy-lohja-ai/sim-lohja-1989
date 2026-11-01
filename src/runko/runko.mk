# Demon runko: boot, resident, linkkiskripti, levynvaihto, siirtymät, MS-DOS-käynnistys, lopputekstit ja osalevyt.
# Juuren Makefile sisällyttää tämän. Koko demon levyt kokoaa tools/disk/kokoa.py, joka rakentaa jokaisen osan
# osalevynä (make part P=osa) ja käyttää niiden tiedostoja.
# Vaiheet: music.py build -> levy.py names (files.inc) -> payload.asm -> zx0.py boot -> boot.asm -> levy.py disk.
RB     = build/runko
RTASS  = 64tass -C -a -B -q -I src -I src/runko -I tools/krill
RSRC   = src/runko/payload.asm src/runko/runko.inc src/runko/resident.asm src/runko/unzx0.asm src/music/music.asm src/runko/haivytys.asm \
         tools/krill/krill.inc src/gen/timing.inc tools/disk/levy.py tools/disk/d64.py tools/disk/zx0.py
DSTART ?= 0

$(RB)/music.bin: tools/music/music.py tools/music/song.json
	@mkdir -p $(RB)
	@python3 -I tools/music/music.py build $(RB) --addr 0800 --zp c0 --buf 1700 > /dev/null

# MS-DOS-ruudun musiikki Appeltrad Act 0 (dos.asm): $a000-$aeff, nollasivu $c0 (pääbiisi alustaa omansa vasta
# DOS_ENDissä)
$(RB)/act0.bin: tools/music/music.py tools/music/song.json
	@mkdir -p $(RB)
	@python3 -I tools/music/music.py --laulu act0 build $(RB) --addr a000 --zp c0 > /dev/null

# $(1) = hakemisto, $(2) = levyn kuvaus, $(3) = lisäasetukset, $(4) = riippuvuudet (osat)
define runko
$(1)/payload.bin: $(RSRC) $(RB)/music.bin $(2) $(4) FORCE
	@mkdir -p $(1)
	@python3 -I tools/disk/levy.py names $(2)
	@$(RTASS) -I $(1) -I $(RB) $(3) $$(if $$(filter-out 0,$$(DSTART)),-D START=$$(DSTART)) -b --vice-labels -l $(1)/payload.labels -o $(1)/payload.new $$<
	@cmp -s $(1)/payload.new $$@ || cp $(1)/payload.new $$@
$(1)/boot.prg: src/runko/boot.asm src/runko/unzx0.asm $(1)/payload.bin
	@python3 -I tools/disk/zx0.py boot $(1)/payload.bin 1000 $(1)/payload.labels $(1)
	@$(RTASS) -I $(1) --vice-labels -l $(1)/boot.labels -o $$@ $$<
endef

# levynvaihtoruudut: make levynvaihto -> build/levynvaihto/lv1-4.prg + syms.inc; kokoa.py: muu tekstijärjestys omaan
# hakemistoonsa (make levynvaihto LV=<hakemisto> LV_TEKSTIT=2,1)
LV = build/levynvaihto
$(LV)/lv.inc: tools/disk/levynvaihto.py src/proto/kyltti/font.py tekstit.yaml tools/tekstit.py tools/gfx/data/levyke/levyke.npy tools/gfx/data/levyke/tausta.json
	@uv run -q --project tools/concept python -I tools/disk/levynvaihto.py $(LV) $(LV_TEKSTIT)
$(LV)/lv1.prg: src/runko/levynvaihto.asm src/runko/runko.inc $(LV)/lv.inc $(RB)/music.bin
	@$(RTASS) -I $(LV) -I $(RB) --vice-labels -l $(LV)/lv.labels --output-section=code -o $@ $<
	@$(RTASS) -I $(LV) -I $(RB) --output-section=speed -o $(LV)/lv2.prg $<
	@$(RTASS) -I $(LV) -I $(RB) --output-section=gfx -o $(LV)/lv3.prg $<
	@$(RTASS) -I $(LV) -I $(RB) --output-section=hold -o $(LV)/lv4.prg $<
	@python3 -I tools/disk/levynvaihto.py syms $(LV)/lv.labels $(LV)/syms.inc
levynvaihto: $(LV)/lv1.prg $(RB)/kaansi/kaansi.inc
.PHONY: levynvaihto

# MS-DOS-käynnistys: make dos -> build/runko/dos/dos.prg (+ dos.labels), tekstit tekstit.yaml:n dos-avaimesta; koko
# demon levy (kokoa.py) lataa sen ennen musiikkia
DOSD = $(RB)/dos
$(DOSD)/dos.prg: src/runko/dos.asm src/runko/dos.inc src/runko/haivytys.asm src/music/music.asm tools/disk/dos.py tools/tekstit.py tekstit.yaml $(RB)/music.bin $(RB)/act0.bin
	@python3 -I tools/disk/dos.py $(DOSD) build/dos/dos_glue.asm > /dev/null
	@$(RTASS) -I $(DOSD) -I $(RB) --vice-labels -l $(DOSD)/dos.labels -o $@ $<
dos: $(DOSD)/dos.prg
.PHONY: dos

# latausväli spritet -> sokeripala: make tahtivali -> build/tahtivali/tv1.prg, tv2.prg, syms.inc; kokoa.py lataa ne
# sprite-ennätyksen jälkeen (tv_go, tv_sky) ja sokeripalan I_SHOW lopettaa (tv_end)
TVD = build/tahtivali
$(TVD)/tv.inc: tools/disk/tahtivali.py $(wildcard tools/gfx/data/tahtivali/*) $(wildcard tools/gfx/data/ryhmalogot/tahtivali/*)
	@uv run -q --project tools/concept python -I tools/disk/tahtivali.py $(TVD) > /dev/null
$(TVD)/tv1.prg: src/runko/tahtivali.asm src/runko/runko.inc $(TVD)/tv.inc
	@$(RTASS) -I $(TVD) --vice-labels -l $(TVD)/tv.labels -o $@ $<
	@python3 -I tools/disk/tahtivali.py syms $(TVD)/tv.labels $(TVD)/syms.inc
tahtivali: $(TVD)/tv1.prg
.PHONY: tahtivali

# siirtymä graafi -> kuoppa: make crt -> build/crt/crt1.prg, syms.inc; kokoa.py esilataa CRT1:n graafin aikana,
# graafin taulu kutsuu crt_go:n ku_cutin jälkeen ja kuopan I_SHOW crt_endin
CRTD = build/crt
$(CRTD)/crt.inc: tools/disk/crt.py
	@python3 -I tools/disk/crt.py $(CRTD)
$(CRTD)/crt1.prg: src/runko/crt.asm src/runko/runko.inc $(CRTD)/crt.inc
	@$(RTASS) -I $(CRTD) --vice-labels -l $(CRTD)/crt.labels -o $@ $<
	@python3 -I tools/disk/crt.py syms $(CRTD)/crt.labels $(CRTD)/syms.inc
crt: $(CRTD)/crt1.prg
.PHONY: crt

# siirtymä kuoppa-kyltit -> spritet: make ilotulitus -> build/ilotulitus/ilot.prg, syms.inc; kylttien taulu lataa
# ILOT:n ku_cutin jälkeen ja kutsuu it_go:n, spritetin spr_hiljaa lopettaa
ITD = build/ilotulitus
$(ITD)/it.inc: tools/disk/ilotulitus.py src/proto/spritet/build.py
	@PYTHONDONTWRITEBYTECODE=1 python3 -I tools/disk/ilotulitus.py $(ITD)
$(ITD)/ilot.prg: src/runko/ilotulitus.asm src/runko/runko.inc $(ITD)/it.inc
	@$(RTASS) -I $(ITD) --vice-labels -l $(ITD)/it.labels -o $@ $<
	@python3 -I tools/disk/ilotulitus.py syms $(ITD)/it.labels $(ITD)/syms.inc
ilotulitus: $(ITD)/ilot.prg
.PHONY: ilotulitus

# levynkääntöruudun kirjaimet (kyltin kirjaimistosta) ja puolen B tunnistetiedosto
$(RB)/kaansi/kaansi.inc: tools/disk/kaansi.py src/proto/kyltti/font.py tools/disk/d64.py
	@uv run -q --project tools/concept python -I tools/disk/kaansi.py $(RB)/kaansi

# lopputekstit: data tools/disk/loppu.py, koodi src/runko/loppu.asm
$(RB)/loppu/loppu.inc: tools/disk/loppu.py src/proto/kyltti/font.py src/gen/timing.inc tekstit.yaml tools/tekstit.py build/koti/demo/koti.prg
	@uv run -q --project tools/concept python -I tools/disk/loppu.py $(RB)/loppu
$(RB)/loppu/loppu.prg: src/runko/loppu.asm src/runko/runko.inc src/gen/timing.inc $(RB)/loppu/loppu.inc
	@$(RTASS) -I $(RB)/loppu --vice-labels -l $(RB)/loppu/loppu.labels -o $@ $<
LOPPU = $(RB)/loppu/loppu.prg

# kohtaukset: koti, greetsit ja alku juuren Makefilen säännöillä (INTEGRATED = 1, FRAME_HOOK = $0408)
KOTI_PRG = build/koti/demo/koti.prg
GREETS_SYMS = build/greetsit/demo/syms.inc
ALKU_SYMS = build/logo/demo/syms.inc

# osalevy: make part P=hillner|koti|loppu|greetsit|alku|<muu> -> build/part-P.d64 + .labels, vain yksi kohtaus,
# kello ja musiikki kohtauksen alusta. Kuvaus src/runko/part-P.json. kokoa.py rakentaa jokaisen osan näin.
PART_ID_hillner = 1
PART_ID_koti = 2
PART_ID_loppu = 3
PART_ID_greetsit = 4
PART_ID_alku = 5
# muu P: yleinen osalevy (PART 99): kohtauksen taulu src/scene/P_glue.asm tai tehty build/P/P_glue.asm (määrittelee
# SCENE_START ja SCENE_END), kohtauksen palat rakentaa part-P.json:n "make"-avaimen komento (levy.py prep)
ifdef P
PID = $(or $(PART_ID_$(P)),99)
PGEN = $(if $(PART_ID_$(P)),,-D PART_GLUE='"$(P)_glue.asm"')
PSCENE = $(if $(PART_ID_$(P)),,$(RB)/part-$(P)/scene.stamp)
$(RB)/part-$(P)/scene.stamp: FORCE
	@mkdir -p $(RB)/part-$(P)
	@python3 -I tools/disk/levy.py prep src/runko/part-$(P).json $(P)
	@touch $@
$(eval $(call runko,$(RB)/part-$(P),src/runko/part-$(P).json,-I src/scene -I build/$(P) -I build/d64 -D PART=$(PID) $(PGEN) -D HAVE_KOTI=$$$$(test -f $(KOTI_PRG) && echo 1 || echo 0) -D HAVE_GREETSIT=$$$$(test -f $(GREETS_SYMS) -a -f src/scene/greetsit_glue.asm && echo 1 || echo 0) -D HAVE_ALKU=$$$$(test -f $(ALKU_SYMS) && echo 1 || echo 0),src/runko/link.asm src/scene/hil.inc src/scene/hil_glue.asm build/d64/parts.inc $(HDEMO) $(KDEMO) $(GDEMO) $(LOPPU) $(if $(filter alku,$(P)),$(ADEMO)) $(PSCENE)))
build/part-$(P).d64: $(RB)/part-$(P)/boot.prg FORCE
	@python3 -I tools/disk/levy.py disk src/runko/part-$(P).json
part: build/part-$(P).d64
endif

.PHONY: part FORCE
