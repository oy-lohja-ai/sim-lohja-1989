# Kaupungintalo: make -C src/proto/kaupungintalo demo [VARIANT=ikkuna] -> build/kaupungintalo[-VARIANT]/demo/
# kt0-6.prg + syms.inc + kt.labels, peli.labels (huone, näyttö ja ydin kt.asm, peli peli.asm). Data
# tools/gfx/data/kaupungintalo/, generoitu koodi build.py. Osalevyt:
# make part P=kaupungintalo (näytön lähikuva ja peli) ja P=kaupungintalo-ikkuna (kamera-ajo ja huone),
# src/runko/part-*.json ja src/scene/*_glue.asm.
ROOT   = ../../..
VARIANT ?=
SUF    = $(if $(VARIANT),-$(VARIANT))
OUT    = $(ROOT)/build/kaupungintalo$(SUF)
DEMO   = $(OUT)/demo
TFLAGS = -C -a -B -q
DATA   = $(wildcard $(ROOT)/tools/gfx/data/kaupungintalo/*)

$(OUT)/kt.inc: build.py kamera.py $(DATA)
	@mkdir -p $(OUT)
	@PYTHONDONTWRITEBYTECODE=1 uv run -q --project $(ROOT)/tools/concept python -I build.py $(OUT) $(VARIANT)

$(OUT)/peli.inc: peli_build.py $(DATA)
	@mkdir -p $(OUT)
	@PYTHONDONTWRITEBYTECODE=1 uv run -q --project $(ROOT)/tools/concept python -I peli_build.py $(OUT)

$(DEMO)/kt.prg: kt.asm kadet_copy.asm kamera.asm kamera_b.asm kamera_c.asm kamera_init.asm $(OUT)/kt.inc
	@mkdir -p $(DEMO)
	@64tass $(TFLAGS) -I $(OUT) --vice-labels -l $(DEMO)/kt.labels -o $@ kt.asm

$(DEMO)/peli.prg: peli.asm $(OUT)/peli.inc
	@mkdir -p $(DEMO)
	@64tass $(TFLAGS) -I $(OUT) --vice-labels -l $(DEMO)/peli.labels -o $@ peli.asm

$(DEMO)/syms.inc: $(DEMO)/kt.prg $(DEMO)/peli.prg split.py
	@python3 -I split.py $(DEMO)

demo: $(DEMO)/syms.inc

.PHONY: demo
