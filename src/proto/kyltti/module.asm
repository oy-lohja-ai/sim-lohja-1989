; Kyltti-moduuli ladattavana tiedostona (Krillin lataaja): make -C src/proto/kyltti module
; -> build/kyltti/mod/kyltti.prg (lataosoite K_BASE) ja kyltti_sym.inc (rajapinnan symbolit 64tass-muodossa).
; Data on pääbuildin luovutuskuvan asemassa (kuvan rivi 0 = rasteririvi 72).

        .include "kyltti.inc"

        .weak
K_BASE  = $8000                 ; moduulin alue $8000-$afff
        .endweak

        * = K_BASE              ; 64tass kirjoittaa PRG-lataosoitteen
        .include "kyltti_all.asm"
        .cerror kyltti_end > $b000, "kyltti-moduuli yli $afff"
