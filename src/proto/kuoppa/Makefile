# Lohjantähden kuoppa (partti 5): make -C src/proto/kuoppa demo [VARIANT=kyltit] -> build/kuoppa/demo[-VARIANT]/kp0-4.prg
# + syms.inc + kuoppa.labels. Data build.py konseptin generaattoreista (tools/concept/concept/kuoppa2.py, kuoppa.py,
# star.py), yhteinen molemmille. Osalevyt: make part P=kuoppa (kuoppa, runko ja valmis torni)
# ja P=kuoppa-kyltit (VARIANT=kyltit: kuva 3 kuopan kehyksestä KP_ALKU, kyltit), src/runko/part-*.json ja
# src/scene/*_glue.asm.
ROOT   = ../../..
VARIANT ?=
OUT    = $(ROOT)/build/kuoppa
DEMO   = $(OUT)/demo$(if $(VARIANT),-$(VARIANT))
KP_ALKU_kyltit = 1260
# kuoppa-kyltit: kerrontataulu 2c (src/proto/taulu N=2c, pankki 3, TAULU_DF0 = KP_TAULU) osan kehyksistä 450
# 240 kehystä, kuopan kello seisoo sen ajan (kp_tauko, kp_jatka); taulun tiedostot kpt.prg ja kptb.prg
KP_TAUKO_kyltit = 240
TFLAGS = -C -a -B -q $(if $(VARIANT),-D KP_ALKU=$(KP_ALKU_$(VARIANT)) -D KP_TAUKO=$(KP_TAUKO_$(VARIANT)))
TAULU  = $(ROOT)/build/taulu2c
CONCEPT = $(addprefix $(ROOT)/tools/concept/concept/,kuoppa.py kuoppa2.py star.py house.py persp.py pixel.py c64.py tori.py) \
		$(ROOT)/src/proto/kyltti/font.py

$(OUT)/kuoppa.inc: build.py kuormaaja.py runko.py torni.py kyltit.py $(CONCEPT) $(ROOT)/tools/gfx/c64fmt.py \
		$(ROOT)/src/lib/kylttipudotus.py $(ROOT)/tools/gfx/data/ryhmalogot/kyltit_roolit.npz
	@mkdir -p $(OUT)
	@PYTHONDONTWRITEBYTECODE=1 uv run -q --project $(ROOT)/tools/concept python build.py $(OUT)

$(DEMO)/kuoppa.prg: kuoppa.asm kuoppa2.asm kuoppa3.asm kuoppa4.asm kp_defs.inc $(OUT)/kuoppa.inc split.py \
		$(ROOT)/src/lib/kylttipudotus.asm kp_nousu.asm $(ROOT)/src/lib/haivytys.asm
	@mkdir -p $(DEMO)
	@64tass $(TFLAGS) -I $(OUT) --vice-labels -l $(DEMO)/kuoppa.labels -o $@ kuoppa.asm
	@python3 -I split.py core $(DEMO)
	@awk '$$3 ~ /^\.(spr1|spos)$$/ {print substr($$3, 2) " = $$" $$2}' $(DEMO)/kuoppa.labels > $(DEMO)/kp1_syms.inc
	@64tass $(TFLAGS) -I $(OUT) -I $(DEMO) --vice-labels -l $(DEMO)/kuoppa2.labels -o $(DEMO)/kuoppa2.prg kuoppa2.asm
	@64tass $(TFLAGS) -I $(OUT) -I $(DEMO) --vice-labels -l $(DEMO)/kuoppa3.labels -o $(DEMO)/kuoppa3.prg kuoppa3.asm
	@python3 -I split.py k3 $(DEMO)
	@64tass $(TFLAGS) -I $(OUT) -I $(DEMO) -I $(ROOT)/src/lib --vice-labels -l $(DEMO)/kuoppa4.labels -o $(DEMO)/kuoppa4.prg kuoppa4.asm
	@python3 -I split.py $(DEMO)
	@awk '$$3 ~ /^\.(irqhook|spr1|COL1|fbank)$$/ {print substr($$3, 2) " = $$" $$2}' $(DEMO)/kuoppa.labels > $(DEMO)/nousu_syms.inc
	@64tass $(TFLAGS) -I $(DEMO) --vice-labels -l $(DEMO)/kp_nousu.labels -o $(DEMO)/kpn.prg kp_nousu.asm
	@awk '$$3 ~ /^\.(kpn_prep|kpn_show|kpn_go)$$/ {print substr($$3, 2) " = $$" $$2}' $(DEMO)/kp_nousu.labels >> $(DEMO)/syms.inc

taulu2c:
	@$(MAKE) -s -C ../taulu demo N=2c
	@mkdir -p $(DEMO)
	@cp -p $(TAULU)/taulu.prg $(DEMO)/kpt.prg
	@cp -p $(TAULU)/taulub.prg $(DEMO)/kptb.prg
	@cp -p $(TAULU)/syms.inc $(DEMO)/kpt_syms.inc

demo: $(DEMO)/kuoppa.prg $(if $(filter kyltit,$(VARIANT)),taulu2c)

.PHONY: demo taulu2c

.DELETE_ON_ERROR:
