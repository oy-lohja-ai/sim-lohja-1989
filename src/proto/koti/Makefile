# Koti (kohtaus 2): make -C src/proto/koti = demon osa (osalevy make part P=koti).
# Demon osa: make -C src/proto/koti demo -> build/koti/demo/koti.prg + koti.labels (INTEGRATED, FRAME_HOOK $0408),
# levyn palat koti1-5.prg ja kohtaustaulun sisääntulot syms.inc (split.py, src/scene/koti_glue.asm).
# DEBUG=1: IRQ-vaiheet reunaväreinä.
ROOT   = ../../..
OUT    = $(ROOT)/build/koti
DEMO   = $(OUT)/demo
TASS   = 64tass
DEBUG ?= 0
TFLAGS = -C -a -B -q -D DEBUG=$(DEBUG)
DATA   = $(wildcard $(ROOT)/tools/gfx/data/koti/*)
SCRIPT = $(ROOT)/tekstit.yaml $(ROOT)/tools/tekstit.py   # tekijät taivaalle (build.py credit_names)
SRC    = koti.asm $(ROOT)/src/lib/crunch.asm

all: demo

$(DEMO)/koti.inc: build.py $(DATA) $(SCRIPT) $(ROOT)/tools/gfx/c64fmt.py $(ROOT)/src/gen/timing.inc
	@uv run -q --project $(ROOT)/tools/concept python build.py $(DEMO) --integrated

$(DEMO)/koti.prg: $(SRC) $(DEMO)/koti.inc split.py
	@$(TASS) $(TFLAGS) -I $(DEMO) -I $(ROOT)/src/gen -D INTEGRATED=1 -D 'FRAME_HOOK=$$0408' --vice-labels -l $(DEMO)/koti.labels -o $@ koti.asm
	@python3 -I split.py $(DEMO)

demo: $(DEMO)/koti.prg

.PHONY: all demo
