# Greetsit (partti 4): make -C src/proto/greetsit demo -> build/greetsit/demo/greetsit3.prg, greetsit5.prg,
# greetsit6.prg, greetsit7.prg ja syms.inc (INTEGRATED, FRAME_HOOK $0408, sisääntulot greetsit_init ja greetsit_go;
# palat split.py, kohtaustaulu src/scene/greetsit_glue.asm). Data tools/gfx/data/greetsit/.
# KSTART: kernelin ensimmäinen rivi:sykli (mitattu, build.py --start).
ROOT   = ../../..
OUT    = $(ROOT)/build/greetsit
TASS   = 64tass
KSTART ?= 46:10
TFLAGS = -C -a -B -q
DATA   = $(wildcard $(ROOT)/tools/gfx/data/greetsit/v5/* $(ROOT)/tools/gfx/data/greetsit/v5/rungot/*)
GEN    = $(OUT)/greetsit.inc $(OUT)/kernel.asm $(OUT)/tables.asm $(OUT)/color_u.asm $(OUT)/gen_lo.asm $(OUT)/gen_hi.asm $(OUT)/maps.asm $(OUT)/wave.asm

all: demo

$(OUT)/greetsit.inc: build.py pyorailija.py lenkkeilija.py $(DATA) $(ROOT)/src/proto/kyltti/font.py $(ROOT)/tekstit.yaml $(ROOT)/tools/tekstit.py
	@PYTHONDONTWRITEBYTECODE=1 uv run -q --project $(ROOT)/tools/concept python build.py $(OUT) --start $(KSTART)

DEMO   = $(OUT)/demo

$(DEMO)/greetsit.prg: greetsit.asm $(OUT)/greetsit.inc $(ROOT)/src/gen/timing.inc split.py
	@mkdir -p $(DEMO)
	@$(TASS) $(TFLAGS) -I $(OUT) -I $(ROOT)/src/gen -D INTEGRATED=1 --vice-labels -l $(DEMO)/greetsit.labels -o $@ greetsit.asm
	@python3 -I split.py $(DEMO)

demo: $(DEMO)/greetsit.prg

.PHONY: all demo
