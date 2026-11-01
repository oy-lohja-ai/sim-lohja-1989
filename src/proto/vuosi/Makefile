# Vuosipartti (vuosi1989 / vuosi2026, sama koodi): make -C src/proto/vuosi demo VUOSI=1989
# -> build/<AINEISTO>/1989/demo/vuosi1.prg + syms.inc (vuosi_init, vuosi_go) + vuosi.labels.
# Data tools/gfx/data/<AINEISTO>/<VUOSI>/ (AINEISTO = vuosi, piirretty).
# Osalevy: make part P=vuosi1989 (part-json:n make-avain, kohtaustaulu src/scene/vuosi1989_glue.asm).
# KSTART: kernelin ensimmäinen rivi:sykli (mitattu, build.py --start).
ROOT   = ../../..
VUOSI ?= 1989
AINEISTO ?= vuosi
OUT    = $(ROOT)/build/$(AINEISTO)/$(VUOSI)
DEMO   = $(OUT)/demo
KSTART ?= 47:10
TFLAGS = -C -a -B -q
DATA   = $(wildcard $(ROOT)/tools/gfx/data/$(AINEISTO)/$(VUOSI)/*)

$(OUT)/vuosi.inc: build.py $(ROOT)/src/lib/raster.py $(DATA)
	@mkdir -p $(OUT)
	@PYTHONDONTWRITEBYTECODE=1 uv run -q --project $(ROOT)/tools/concept python build.py $(OUT) --vuosi $(VUOSI) --aineisto $(AINEISTO) --start $(KSTART) $(if $(KAISTAT),--kaistat $(KAISTAT))

$(DEMO)/vuosi.prg: vuosi.asm $(OUT)/vuosi.inc split.py
	@mkdir -p $(DEMO)
	@64tass $(TFLAGS) -I $(OUT) --vice-labels -l $(DEMO)/vuosi.labels -o $@ vuosi.asm
	@python3 -I split.py $(DEMO)

demo: $(DEMO)/vuosi.prg

.PHONY: demo
