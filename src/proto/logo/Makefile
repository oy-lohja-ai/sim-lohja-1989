# Alkuruutu (Oy Lohja AI): make -C src/proto/logo demo. Data: tools/gfx/logo/build.py (taulut, täyttöketjut, nimiruutu).
ROOT   = ../../..
OUT    = $(ROOT)/build/logo
TASS   = 64tass
TFLAGS = -C -a -B -q
GEN    = $(ROOT)/tools/gfx/logo
SRC    = logo.asm proj.asm render.asm mark.asm alue.asm hand.asm gaps.asm bss.asm

DEMO   = $(OUT)/demo

all: demo

# demon osa: INTEGRATED, FRAME_HOOK $0408, levylle alku1.prg ($1a00-) ja alku2.prg ($f600-),
# sisääntulot syms.inc (src/scene/alku_glue.asm)
$(DEMO)/consts.inc: $(GEN)/build.py $(GEN)/model.py $(GEN)/timeline.py $(GEN)/mesh.py $(GEN)/name.py $(GEN)/title.py title.asm $(wildcard $(GEN)/data/*) $(wildcard $(ROOT)/tools/gfx/data/nimi/*) $(ROOT)/src/gen/timing.inc
	@python3 -I $(GEN)/build.py $(DEMO) --integrated

$(DEMO)/alku.prg: $(SRC) $(DEMO)/consts.inc
	@$(TASS) $(TFLAGS) -I $(DEMO) -D INTEGRATED=1 --vice-labels -l $(DEMO)/alku.labels -o $@ logo.asm
	@python3 -I $(GEN)/build.py --syms $(DEMO)/alku.labels $(DEMO)/syms.inc logo_init logo_go title_go titleb_go title2_go
	@python3 -I $(GEN)/build.py --split $@ $(DEMO)/alku1.prg $(DEMO)/alku1b.prg $(DEMO)/alku2.prg

demo: $(DEMO)/alku.prg

.PHONY: all demo
