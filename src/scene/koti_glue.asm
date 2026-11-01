; Koti (kohtaus 2) kohtaustaulussa: src/runko/link.asm sisällyttää tämän taulun kohtaan Hillnerin jälkeen
; (demo) tai ensimmäiseksi (osalevy). Palat ja sisääntulot: src/proto/koti/split.py. KOTI1-3 mahtuvat purun aikana
; vapaisiin alueisiin ($1a00-$3fff, $c000-$cfff, $e000-), joten runko voi ladata ne etukäteen (S_LOAD jo ladatulle ei
; tee askelta). koti_init1 ei koske näyttöön (purun viimeinen kuva jää näkyviin), koti_go ottaa sen. KOTI4 ($4800-,
; purun näyttöpankki) latautuu kodin pyöriessä. Kodin käytössä loppuun: $1a00-koti1_end, $4000-$47ff, $c000-$cfff,
; $e000-$ff3f.
        .include "../../build/koti/demo/syms.inc"
        #S_LOAD f_koti1                 ; $1a00-: koodi, taulut, ylimmän asettelun värit
        #S_LOAD f_koti2                 ; $c000-$cfff: ylimmän asettelun ruutu ja spritelohkot
        #S_LOAD f_koti3                 ; $e000-$ff3f: ylimmän asettelun bittikartta
        #S_CALL koti_init1              ; muuttujat ja spritet (noin kehys), ei näyttöä
        #S_SHOW koti_show               ; osalevyllä ensimmäinen kuva ennen kelloa (kehys 0 ei musta)
        #S_START TIM_SCENE_KOTI_START   ; näkyvä alku kiinteässä kehyksessä
        #S_CALL koti_go                 ; kuva, värit ja IRQ; palaa heti (nousu kirii DFRAMEen)
        #S_LOAD f_koti4                 ; $4800-: alempien asettelujen uudet rivit, tekijöiden käsiala
        #S_CALL koti_build              ; alemmat asettelut takapankkiin vaihtojen mukaan; palaa, kun alin on valmis.
                                        ; $4800-$5fff (KOTI4: tietueet ja tekijöiden data) kodin loppuun
        #S_FREE_RANGE f_koti4, $4800, koti4_live   ; tietueet käytetty, tekijät jäävät
        #S_LOAD f_koti5                 ; $4800-: illan maski tietueiden päälle (ilta_step kameran pysähdyttyä, ILTA_F),
                                        ; dusk_step ja fc_sync: käytössä kodin loppuun
        #S_CALL koti_quiet              ; viimeinen asettelun vaihto: $8000-$bfff vapaa (lopun esilataus)
