# Kyltti-rutiini (greetsit Hillnerin kylttiin perspektiivissä). DEBUG=1: piirto reunavärinä.
# VARIANT = lahi (matala lähikuva, oletus) tai ajo (kamera-ajon loppukuva): sama koodi, eri data.
# make -C src/proto/kyltti module [VARIANT=..] [KBASE=8000] [KPREFIX=ajo_]
#   -> build/kyltti[-ajo]/mod/kyltti.prg (lataajalle) + kyltti_sym.inc (symbolit KPREFIX-etuliitteellä)
ROOT   = ../../..
VARIANT ?= lahi
SUF    = $(if $(filter ajo,$(VARIANT)),-ajo,)
OUT    = $(ROOT)/build/kyltti$(SUF)
MOD    = $(OUT)/mod
TASS   = 64tass
DEBUG ?= 0
KBASE ?= 8000
KPREFIX ?=
TFLAGS = -C -a -B -q -D DEBUG=$(DEBUG)
DATA   = $(ROOT)/tools/gfx/data/hillner/lahi2
AJO    = $(ROOT)/tools/gfx/data/hillner/korkea2
DEPS   = build.py font.py $(ROOT)/tekstit.yaml $(ROOT)/tools/tekstit.py $(DATA)/taysvari.npy $(DATA)/metadata.json $(AJO)/kuva.npy $(AJO)/ajo.json

all: module

# ladattava moduuli pääbuildin kuvan asemaan (kuvan rivi 0 = rasteririvi 72)
$(MOD)/kyltti.inc: $(DEPS) FORCE
	@uv run -q --project $(ROOT)/tools/concept python build.py $(MOD) 72 $(VARIANT)
$(MOD)/kyltti.prg: module.asm kyltti.asm kyltti_all.asm $(MOD)/kyltti.inc
	$(TASS) $(TFLAGS) -I $(MOD) -D 'K_BASE=$$$(KBASE)' -l $(MOD)/kyltti.labels -o $@ module.asm
	@grep -E '^(kyltti_|k_shown|k_ycur|k_yoff|k_tilt|k_sprcol|k_busy|k_gone|K_)' $(MOD)/kyltti.labels | sed 's/^/$(KPREFIX)/' > $(MOD)/kyltti_sym.inc
module: $(MOD)/kyltti.prg

.PHONY: all module FORCE
