; Kyltti-moduuli koodeineen ja datoineen yhtenä includena: aseta * sivun alkuun (sivutasattu data tulee
; ensin, koodi sen perään) ja .include "kyltti_all.asm". Ennen tätä: .include "kyltti.inc" (vakiot) ja
; tarvittaessa omat K_CANVAS, K_PTRS, K_ZP, K_RATE (.weak-oletukset kyltti.asm:ssä). Hakemistot:
; -I build/kyltti[-ajo]/mod -I src/proto/kyltti.

kyltti_start
        .include "kyltti_data.inc"      ; taulut, siirtotaulut, nauhat (build.py)
        .include "kyltti.asm"
kyltti_end
