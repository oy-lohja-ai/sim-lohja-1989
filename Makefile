# SIM LOHJA 1989 (Oy Lohja AI, Zooparty 2026): make -> build/simlohja-a.d64 ja build/simlohja-b.d64 (1 levy, 2 puolta).
# Ensin kolmannen osapuolen osat: tools/fetch-third-party.sh (docs/building.md). make check vertaa levyjä
# kompoversioon (rc10.sha256), make run käynnistää VICEn.
#
# Koko demon levyt kokoaa tools/disk/kokoa.py (järjestys src/runko/jarjestys.json, lähtötila timing/integraatio/).
# Se rakentaa jokaisen osan osalevynä (make part P=osa, src/runko/runko.mk) puhtaasti (make -B), joten jokainen
# make on täysi build. Kaikki Python-ajot (myös python3 -I) käyttävät uv:n ympäristöä tools/concept/.venv
# (Python 3.12 ja paketit tools/concept/uv.lock:sta): sen bin on PATHin alussa kaikissa resepteissä.
TASS   = 64tass
UV     = uv run --project tools/concept python
TFLAGS = -C -a -B -q -I build -I src
export PATH := $(CURDIR)/tools/concept/.venv/bin:$(PATH)
.DEFAULT_GOAL := all

all: build/simlohja-a.d64

build/simlohja-a.d64: FORCE
	@test -f tools/krill/krill.inc || { echo "kolmannen osapuolen osat puuttuvat: tools/fetch-third-party.sh"; exit 1; }
	@uv sync -q --locked --project tools/concept
	@mkdir -p build
	@MAKEFLAGS=-B python3 -I tools/disk/kokoa.py > build/kokoa.log || { tail -40 build/kokoa.log; exit 1; }
	@cp build/integraatio/simlohja-1.d64 build/simlohja-a.d64
	@cp build/integraatio/simlohja-1-b.d64 build/simlohja-b.d64
	@cp build/integraatio/simlohja-1.labels build/simlohja.labels
	@echo "build/simlohja-a.d64, build/simlohja-b.d64 (raportti build/integraatio/kokoa.txt)"

check:
	@if command -v sha256sum > /dev/null; then sha256sum -c rc10.sha256; else shasum -a 256 -c rc10.sha256; fi

# VICE: puoli A käyntiin; kun ruudulla lukee KÄÄN TALRIIKKI NY, vaihda levyksi puoli B (fliplist: Alt+N)
run:
	@printf '# Vice fliplist file\n\nUNIT 8\n%s\n%s\n' "$(CURDIR)/build/simlohja-a.d64" "$(CURDIR)/build/simlohja-b.d64" > build/simlohja.vfl
	x64sc -pal -flipname build/simlohja.vfl -autostart build/simlohja-a.d64

# Osat. Demon runko (src/runko/) lataa ne; kohtausten kulku on kohtaustauluissa src/scene/*_glue.asm.
DEMO   = build/d64
HTAS   = $(TASS) $(TFLAGS) -I $(DEMO) -I src/scene -I tools/krill

$(DEMO)/music.inc: tools/music/music.py tools/music/song.json Makefile
	@mkdir -p $(DEMO)
	@python3 -I tools/music/music.py build $(DEMO) --addr 0800 --zp c0 --buf 1700 > /dev/null
build/kyltti-ajo/mod/lohja_text.npy: src/proto/kyltti/build.py src/proto/kyltti/font.py
	@$(MAKE) -s -C src/proto/kyltti module VARIANT=ajo > /dev/null
# Hillner: kamera-ajon data tools/gfx/data/hillner/korkea2
HIL_AINEISTO = hillner/korkea2
build/hilint/hillner.prg: src/proto/hillner/hillner.asm src/proto/hillner/sprites.asm src/proto/hillner/smoke.asm src/lib/crunch.asm src/gen/timing.inc src/proto/hillner/build.py build/kyltti-ajo/mod/lohja_text.npy $(wildcard tools/gfx/data/$(HIL_AINEISTO)/*)
	@mkdir -p build/hilint
	@$(UV) src/proto/hillner/build.py build/hilint --integrated --aineisto $(HIL_AINEISTO) > /dev/null
	@$(TASS) $(TFLAGS) -I build/hilint -D INTEGRATED=1 -D FRAME_HOOK='$$0408' --vice-labels -l build/hilint/hillner.labels -o $@ src/proto/hillner/hillner.asm
# Hillnerin vaiheiden sisääntulot ja IRQ:t kyltin tiedostoissa (src/proto/hillner/glue_*.asm, HIL_GLUE): kamera-ajon
# label hil_sign build/d64/hilsym.inc:iin
$(DEMO)/hilsym.inc: build/hilint/hillner.prg
	@mkdir -p $(DEMO)
	@sed -n -E 's/^al ([0-9a-f]+) \.(hil_sign)$$/\2 = $$\1/p' build/hilint/hillner.labels > $@
KGLUE  = -I src/scene -I src/runko -I $(DEMO) -I src/proto/hillner
$(DEMO)/kyltti.prg: src/scene/kyltti_part.asm src/proto/hillner/glue_ajo.asm src/proto/hillner/glue_lahi.asm $(DEMO)/hilsym.inc FORCE
	@mkdir -p $(DEMO)
	@$(MAKE) -s -C src/proto/kyltti module > /dev/null
	@$(MAKE) -s -C src/proto/kyltti module VARIANT=ajo > /dev/null
	@$(TASS) $(TFLAGS) -I build/kyltti/mod -I src/proto/kyltti $(KGLUE) -D HIL_GLUE=2 -D KSPLIT=1 -D 'K_BASE=$$1a00' -D 'K_END=$$43c0' -D 'K_CANVAS=$$7a40' -D 'K_SCRATCH=$$40c0' -D 'K_PTRS=$$5ff8' --vice-labels -l $(DEMO)/kyltti.labels -o $@ src/scene/kyltti_part.asm
	@python3 tools/gfx/d64.py kylsym
	@$(TASS) $(TFLAGS) -I build/kyltti-ajo/mod -I src/proto/kyltti $(KGLUE) -D HIL_GLUE=1 -D 'K_BASE=$$4400' -D 'K_END=$$6400' -D 'K_CANVAS=$$8000' -D 'K_PTRS=$$8bf8' --vice-labels -l $(DEMO)/ajo.labels -o $(DEMO)/ajo.prg src/scene/kyltti_part.asm
$(DEMO)/purku1.prg: src/purku/purku.asm build/purku/purku.inc src/scene/hil.inc src/gen/timing.inc $(DEMO)/music.inc $(DEMO)/kyltti.prg
	@$(HTAS) -I build/purku -D FRAME_HOOK='$$0408' --vice-labels -l $(DEMO)/purku1.labels -o $@ src/purku/purku.asm
$(DEMO)/parts.inc: build/hilint/hillner.prg build/purku/purku.inc $(DEMO)/kyltti.prg $(DEMO)/purku1.prg tools/gfx/d64.py
	@python3 tools/gfx/d64.py parts
	@python3 tools/gfx/d64.py syms
# Hillnerin purku (kolme iskua): data tools/gfx/purku.py
build/purku/purku.inc: tools/gfx/purku.py tools/gfx/c64fmt.py src/gen/timing.inc $(wildcard tools/gfx/data/hillner/purku2/*)
	@$(UV) tools/gfx/purku.py build/purku

HDEMO    = $(DEMO)/parts.inc
# koti (src/proto/koti), greetsit (src/proto/greetsit) ja alku (src/proto/logo): palat ja syms.inc
KDEMO    = build/koti/demo/koti.prg
$(KDEMO): FORCE
	@$(MAKE) -s -C src/proto/koti demo > /dev/null
GDEMO    = build/greetsit/demo/greetsit.prg
$(GDEMO): FORCE
	@$(MAKE) -s -C src/proto/greetsit demo > /dev/null
ADEMO    = build/logo/demo/alku.prg
$(ADEMO): FORCE
	@$(MAKE) -s -C src/proto/logo demo > /dev/null
include src/runko/runko.mk

clean:
	rm -rf build

.PHONY: all check run clean FORCE
