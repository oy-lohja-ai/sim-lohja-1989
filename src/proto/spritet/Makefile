# Spritet: make -C src/proto/spritet demo VARIANT=lentavat -> build/spritet-lentavat/demo/spr1-3.prg + syms.inc
# (osalevy: make part P=spritet-lentavat, src/runko/part-spritet-lentavat.json, kohtaustaulu
# src/scene/spritet-lentavat_glue.asm). Demossa muunnos lentavat (ryhmälogot).
# Integraatio (tools/disk/kokoa.py): make demo OUT=<hakemisto> BIISI=T, kohtaus alkaa biisin kehyksessä T.
# Aikataulu plan.py, kerneli ja data build.py, SID-virta ja soittimen lopputila sidvirta.py (VICE x64sc, kohtauksen
# kehykset glue-tiedostosta), logot tools/gfx/data/ryhmalogot/spritet/.
ROOT   = ../../..
VARIANT ?=
BIISI  ?=
SUF    = $(if $(VARIANT),-$(VARIANT))
OUT    = $(ROOT)/build/spritet$(SUF)
SID    = $(OUT)/sid
DEMO   = $(OUT)/demo
TASS   = 64tass
TFLAGS = -C -a -B -q -I $(OUT) -I $(SID)
GLUE   = $(ROOT)/src/scene/spritet$(SUF)_glue.asm
LOGOS  = $(wildcard $(ROOT)/tools/gfx/data/ryhmalogot/spritet/*.png)
GEN    = build.py
ASM    = spritet.asm
STAMP  = $(OUT)/kernel.inc
DATA   = $(LOGOS)

all: demo

$(SID)/sid.bin: sidvirta.py sidvirta.asm $(GLUE) $(ROOT)/src/gen/timing.inc $(ROOT)/tools/music/music.py $(ROOT)/tools/music/song.json
	@python3 -I sidvirta.py $(SID) $(VARIANT) $(if $(BIISI),--biisi $(BIISI))

$(STAMP): $(GEN) build.py plan.py $(SID)/sid.bin $(DATA)
	@python3 -I $(GEN) $(OUT) $(SID) $(VARIANT)

$(DEMO)/spritet.prg: $(ASM) split.py $(STAMP)
	@mkdir -p $(DEMO)
	@$(TASS) $(TFLAGS) -D INTEGRATED=1 --vice-labels -l $(DEMO)/spritet.labels -o $@ $(ASM)
	@python3 -I split.py $(DEMO) $(VARIANT)

demo: $(DEMO)/spritet.prg

.PHONY: all demo
