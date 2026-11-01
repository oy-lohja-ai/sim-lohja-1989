; Hillner, ajo-kyltin vaihe (TIM_CUE_AJOKYLTTI - TIM_CUE_LAHIKUVA): sisääntulot ja IRQ ajo-kyltin tiedostossa AJO
; ($4400-, src/scene/kyltti_part.asm HIL_GLUE = 1). Kohtaustaulu src/scene/hil_glue.asm kutsuu:
;   ajo_on  luovutuksen jälkeen (hil_fin): tämän IRQ (rivi 250), ajo-kyltti alustetaan ja LOHJAN RAUTA
;           takapuskuriin (spritet näkymättömiä, kangas tyhjä)
;   ajo_go  kehyksellä HIL_AJO - 2 (odottaa itse maalatun pidon K_PITO): pystypaluussa spriteteksti näkyviin
;           maalatun päälle jo vierimässä, sitten
;           maalattu teksti pois sen alta (hil_sign): tyhjää kyltti-kehystä ei ole
; IRQ ottaa ajo-kyltin pois kehyksellä HIL_LAHI - 1 (IRQ:ssa, koska pääsilmukka voi olla sisäkkäisen piirron alla
; kokonaisen kehyksen). Sen jälkeen lahi_go (glue_lahi.asm) vaihtaa IRQ:n ennen kuin pankkikopio kirjoittaa tämän päälle.

        .include "gen/timing.inc"
        .include "hil.inc"
        .include "runko.inc"
        .include "hilsym.inc"           ; build/d64: hil_sign (kamera-ajon labelit)

ajo_on  lda #0
        sta kyl
        sta kbusy
        sei                     ; luovutuksen IRQ on jo rivillä 250 (hillner.asm irq_fin)
        lda #<irq_ajo
        sta $fffe
        lda #>irq_ajo
        sta $ffff
        cli
        jsr kyltti_init         ; keskeytysten kanssa: kangas tyhjä, joten spritet ovat näkymättömiä
        lda #$ff                ; teksti katuvalon takana (bittikartan %10/%11: build.py pole_front;
        sta $d01b               ; pylväs omana kerroksena, joten teksti käyttää koko kaistan)
        jmp kyltti_render       ; LOHJAN RAUTA takapuskuriin (k_ready), tick näyttää sen

ajo_go  ldx #<(HIL_AJO - 2 + K_PITO)  ; maalattu LOHJAN RAUTA pidetään K_PITO kehystä (kyltti build.py): spriteteksti
        ldy #>(HIL_AJO - 2 + K_PITO)  ; tulee näkyviin vasta vierityksessä, joten MC-maalauksen 1 px:n ero ei näy
        jsr R_WAIT              ; hyppynä paikallaan
        jsr k_xroll             ; tila K_RATE - 1 kehystä eteen: ensimmäinenkin kuva liikkuu 50 Hz:llä (K_XLIIKE)
-       bit $d011               ; pystypaluu
        bpl -
        jsr kyltti_tick         ; takapuskuri näkyviin (osoittimet ja Y-porras)
-       bit $d011               ; maalattu teksti pois vasta kyltin kaistan (rivit ~108-150) alapuolelta
        bmi -                   ; seuraavassa kehyksessä: noin 190 riviä + IRQ:t, valmis ennen seuraavaa kaistaa,
-       lda $d012               ; joten säde ei koskaan näe puolivalmista pyyhintää (mallista riippumaton kuva)
        cmp #160
        bcc -
        jsr hil_sign
        inc kyl                 ; IRQ: tick ja sisäkkäinen piirto
        rts

irq_ajo pha                     ; rivi 250: musiikki ja kello, kyltti (piirto sisäkkäin)
        txa
        pha
        tya
        pha
        lda $01
        pha
        lda #$35
        sta $01
        asl $d019
        jsr FRAME_HOOK_AT
        lda kyl
        beq _x
        lda DFRAME              ; leikkaus: kello kasvaa rivillä 250, vaihto heti perään pystypaluussa, joten
        cmp #<(HIL_LAHI - 1)    ; kehys HIL_LAHI näkyy jo ilman kylttiä (mitattu: DFRAME = näkyvä kehys, kun
        lda DFRAME+1            ; hil_go ottaa koneen samassa pystypaluussa)
        sbc #>(HIL_LAHI - 1)
        bcc _tick
        lda #0
        sta kyl
        sta $d015
        beq _x
_tick   jsr kyltti_tick
        lda kbusy               ; piirto sallii seuraavan kehyksen IRQ:n (lataus pääsilmukassa)
        bne _x
        inc kbusy
        cli
        jsr kyltti_render
        dec kbusy
_x      pla
        sta $01
        pla
        tay
        pla
        tax
        pla
        rti

kyl     .byte 0                 ; 1 = kyltti IRQ:ssa
kbusy   .byte 0                 ; piirto käynnissä
