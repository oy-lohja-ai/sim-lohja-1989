# Sokeripala (demon loppu): make -C src/proto/sokeripala demo -> build/sokeripala/demo/sp*.prg + syms.inc,
# build/sokeripala/sp.labels. Data tools/gfx/data/sokeripala/, aikataulut build.py,
# taulu «JATKUU...» tekstit.yaml:n taulusta 3 (tools/gfx/taulu.py).
# Osalevy: make part P=sokeripala (src/runko/part-sokeripala.json, kohtaustaulu src/scene/sokeripala_glue.asm).
ROOT   = ../../..
OUT    = $(ROOT)/build/sokeripala
TFLAGS = -C -a -B -q
DATA   = $(wildcard $(ROOT)/tools/gfx/data/sokeripala/*)
TDATA  = $(wildcard $(ROOT)/tools/gfx/data/taulu/*)
PY     = PYTHONDONTWRITEBYTECODE=1 uv run -q --project $(ROOT)/tools/concept python -I

$(OUT)/sp.inc: build.py lehti.py $(DATA)
	@mkdir -p $(OUT)
	@$(PY) build.py $(OUT)

$(OUT)/taulu_jatkuu.inc: $(ROOT)/tools/gfx/taulu.py $(ROOT)/tekstit.yaml $(ROOT)/tools/tekstit.py $(TDATA) Makefile
	@mkdir -p $(OUT)
	@$(PY) $(ROOT)/tools/gfx/taulu.py $(OUT) jatkuu --taulu 3 --kesto 240 >/dev/null

$(OUT)/sp.prg: sokeripala.asm lehti.py $(ROOT)/src/lib/taulu.asm $(OUT)/sp.inc $(OUT)/taulu_jatkuu.inc
	@64tass $(TFLAGS) -I $(OUT) --vice-labels -l $(OUT)/sp.labels -o $@ sokeripala.asm

$(OUT)/demo/syms.inc: $(OUT)/sp.prg split.py
	@python3 -I split.py $(OUT)

demo: $(OUT)/demo/syms.inc

.PHONY: demo
