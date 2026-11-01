# Kerrontataulu omalla osalevyllä: make -C src/proto/taulu demo N=1 -> build/taulu1/taulu.prg (+ taulu.labels,
# syms.inc, taulu1_glue.asm). N = tekstit.yaml:n taulut-kohdan avain (teksti sieltä),
# KESTO kehyksinä (oletus 240 = 2 tahtia), PANKKI VIC-pankki (oletus 2; 3: bittikartta omana tiedostonaan taulub.prg,
# taulu2b koko demossa kuopan ja kylttien välissä), MERKKI merkkitila 8 kt:n lohkossa (heksana; taulut 1 ja 1b koko
# demossa kaupungintalon edellä, jonka alku esiladataan muualle taulun aikana) ja LATAUS tiedoston osoite, jos eri
# (taulu_init kopioi). Osalevy: make part P=taulu<N> (src/runko/part-taulu<N>.json).
# Moduuli src/lib/taulu.asm, työkalu tools/gfx/taulu.py.
ROOT   = ../../..
N     ?= 1
KESTO ?= 240
PANKKI_2b = 3
PANKKI_2c = 3
DF0_2c = 450                    # taulu 2c kuoppa-kylttien sisällä (src/proto/kuoppa KP_TAULU): taulun kehys 0 = osan 450
DF0 ?= $(DF0_$(N))
PANKKI ?= $(or $(PANKKI_$(N)),2)
MERKKI_1 = a000
MERKKI_1b = 6000
LATAUS_1b = a000
MERKKI ?= $(MERKKI_$(N))
LATAUS ?= $(or $(LATAUS_$(N)),$(MERKKI))
comma := ,
MUSTA_2 = 14
MUSTA_3b = 10
MERKKI_3b = 6000
MERKKI_2d = 6000
MERKKI_2e = a000
MUSTA_2e = 26
MUSTA ?= $(MUSTA_$(N))
P3_KOODI_2b = 5800
P3_BITTI_2b = 6000
P3_KOODI ?= $(P3_KOODI_$(N))
P3_BITTI ?= $(P3_BITTI_$(N))
OUT    = $(ROOT)/build/taulu$(N)
TFLAGS = -C -a -B -q -D PANKKI=$(PANKKI) $(if $(MERKKI),-D MERKKI='$$$(MERKKI)' -D LATAUS='$$$(LATAUS)') \
         $(if $(P3_KOODI),-D P3_KOODI='$$$(P3_KOODI)' -D P3_BITTI='$$$(P3_BITTI)') $(if $(DF0),-D TAULU_DF0=$(DF0)) $(if $(MUSTA),-D TAULU_MUSTA=$(MUSTA))
DATA   = $(wildcard $(ROOT)/tools/gfx/data/taulu/*)

$(OUT)/taulu_osa.inc: $(ROOT)/tools/gfx/taulu.py $(ROOT)/tekstit.yaml $(ROOT)/tools/tekstit.py $(DATA) Makefile
	@mkdir -p $(OUT)
	@PYTHONDONTWRITEBYTECODE=1 uv run -q --project $(ROOT)/tools/concept python -I $(ROOT)/tools/gfx/taulu.py $(OUT) osa --taulu $(N) --kesto $(KESTO) --pankki $(PANKKI) --glue $(if $(MERKKI),--merkki $(MERKKI) --lataus $(LATAUS)) $(if $(P3_KOODI),--p3 $(P3_KOODI)$(comma)$(P3_BITTI))
	@mv $(OUT)/osa_glue.asm $(OUT)/taulu$(N)_glue.asm

$(OUT)/taulu.prg: taulu.asm $(ROOT)/src/lib/taulu.asm $(OUT)/taulu_osa.inc syms.py Makefile
	@64tass $(TFLAGS) -I $(OUT) --vice-labels -l $(OUT)/taulu.labels -o $@ taulu.asm
	@python3 -I syms.py $(OUT)

$(OUT)/taulub.prg: taulub.asm $(OUT)/taulu_osa.inc Makefile
	@64tass $(TFLAGS) -I $(OUT) -o $@ taulub.asm

demo: $(OUT)/taulu.prg $(if $(filter 3,$(PANKKI)),$(OUT)/taulub.prg)

.PHONY: demo
