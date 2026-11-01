; Spritet, muunnos lentavat: ryhmälogot lentävät rakettien seassa. make part
; P=spritet-lentavat (runko PART 99), koodi src/proto/spritet (VARIANT=lentavat).
; Kello ja musiikki kehyksestä SCENE_START, loppu SCENE_END (4 tahtia = 16 iskua x 30 kehystä). Kerneli pyörii
; pääsäikeessä ilman keskeytyksiä, kasvattaa DFRAMEa itse ja soittaa biisin hostin laskemana SID-virtana
; (src/proto/spritet/sidvirta.py); spr_go palaa kehyksessä SCENE_END soittimen tila kohdallaan.
SCENE_START = 0
SCENE_END = 480
        .include "../../build/spritet-lentavat/demo/syms.inc"
        #S_LOAD f_spr1                  ; $1a00-$7eff: koodi, taulut, soittimen lopputila, spritekuvat, tilarivin taulut
        #S_LOAD f_spr2                  ; $8000-$bfff: kerneli, tilarivin taulut, SID-virtaa
        #S_LOAD f_spr3                  ; $e000-$feff: SID-virtaa
                                        ; $c000-$cfff ei ladata: ennätys ei käytä sitä (split.py tarkistaa), ja
                                        ; siirtymän ilotulitus $c400-$cdff jatkuu spritet -> vuosi2026 -saumaan
                                        ; (tyhjänäkin alue olisi 17 lohkoa raakana ja veisi kylttien $cf00:n)
        #S_CALL spr_init
        #S_START SCENE_START
        #S_CALL spr_go                  ; palaa kehyksessä SCENE_END
