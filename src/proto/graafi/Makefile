# Graafi (paluu kaupungintalon peliin Hillnerin purun jälkeen): make -C src/proto/graafi demo ->
# build/graafi/graafi.prg + graafi.labels + syms.inc. Data tools/gfx/data/graafi/, taulut
# build.py. Osalevy make part P=graafi (src/runko/part-graafi.json, kohtaustaulu src/scene/graafi_glue.asm).
ROOT   = ../../..
OUT    = $(ROOT)/build/graafi
TFLAGS = -C -a -B -q
DATA   = $(wildcard $(ROOT)/tools/gfx/data/graafi/*)

$(OUT)/graafi.inc: build.py $(DATA)
	@mkdir -p $(OUT)
	@PYTHONDONTWRITEBYTECODE=1 uv run -q --project $(ROOT)/tools/concept python -I build.py $(OUT)

$(OUT)/graafi.prg: graafi.asm $(OUT)/graafi.inc syms.py
	@64tass $(TFLAGS) -I $(OUT) --vice-labels -l $(OUT)/graafi.labels -o $@ graafi.asm
	@python3 -I syms.py $(OUT)

demo: $(OUT)/graafi.prg

.PHONY: demo
