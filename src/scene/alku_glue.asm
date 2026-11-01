; Alku (kohtaus 1, Oy Lohja AI -emblem) kohtaustaulussa: src/runko/link.asm sisällyttää tämän taulun
; kohtaan ennen Hillneriä (demo) tai ensimmäiseksi (osalevy). Osa: make -C src/proto/logo demo ->
; build/logo/demo/alku1.prg ($1a00-$9dff: koodi, taulut, spritet, täyttöketjut), alku2.prg ($f600-: valo,
; segmentit, aaltoilu) ja sisääntulot syms.inc.
; Ajonaikaiset: bittikartat $6000 ja $a000, merkkipuskuri $e000-$f5ff, nollasivu $02-$bf.
;
; logo_go piirtää pääsäikeessä purun alkuun (ALKU_FREE), sitten purku on IRQ-pyyhkäisy (T3 $fa40-, kuva pankissa 3)
; ja logo_go palaa. Nimiruutu (title.prg, $8000-$bf3f) ladataan ja näytetään pankissa 2 kehyksestä TITLE0 alun
; loppuun; Hillnerin CRANE1 ($1a00-$746f) latautuu sen aikana.
        .include "../../build/logo/demo/syms.inc"
        #S_LOAD f_alku1                 ; $1a00-$7fff
        #S_LOAD f_alku1b                ; $8000-$9fff (IRQ-koodi, täyttöketjut, neliötaulut)
        #S_LOAD f_alku2                 ; $f600-
        #S_CALL logo_init               ; muisti, värit, spritet (ruutu pimeänä)
        #S_START TIM_SCENE_ALKU_START   ; näkyvä alku kiinteässä kehyksessä
        #S_CALL logo_go                 ; emblem rakentuu, pito, purku viivaksi; palaa, kun purku on IRQ:ssa
        #S_FREE f_alku1b                ; piirto ohi: $8000-$9fff nimiruudulle (runko vapauttaa alku1:n ja alku2:n)
        #S_LOAD f_title                 ; nimiruutu pankkiin 2: $8000 ruutu, $8400 värit, $8800 ruudun lähde, TCODE
        #S_LOAD f_titlec                ; $a000-$bf3f ilmakuva
        #S_CALL title_go                ; IRQ avaa sen viivasta kehyksellä TITLE0 (purun jälkeen)
        #S_LOAD f_titleb                ; $9000-: logon solut, tarvitaan TITLE0 + 36 (logon maalaus)
        #S_CALL titleb_go
        #S_LOAD f_title2                ; lappusten ponnahdukset (TPOP-$7fff, CRANE1:n yläpuolella), tarvitaan TITLE0 + 120
        #S_CALL title2_go
        #S_FREE f_titleb
        #S_FREE f_titlec
        #S_FREE f_title                 ; kirjanpito: näkyy alun loppuun; seuraava kirjoittaja on hil_prep juuri ennen
        #S_FREE f_title2                ; Hillnerin kelloa ($8000-, $a000-), CRANE1 ($1a00-$746f) ei osu, CRANE1B
                                        ; ($7470-) vasta Hillnerin aikana
        #S_WAIT TIM_SCENE_ALKU_START + ALKU_TITLE0 + 2   ; nimiruutu pankissa 2: purun ruutu $c000-$c3e7 ja
                                        ; bittikartta $e000- vapaita (part-alku.json vapaana_lopussa: seuraavan
                                        ; kohtauksen esilataus, kuten vuosi1989)
        #S_FREE f_alku1                 ; logo_go palasi (ALKU_FREE): $1a00-$5a57 vapaa
        #S_FREE_RANGE f_alku2, $f600, $fb00   ; nimiruudun IRQ ja otb $fb00-, ALKU2:n alku vapaa
