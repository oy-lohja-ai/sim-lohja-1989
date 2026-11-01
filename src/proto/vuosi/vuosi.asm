; Vuosipartti (vuosi1989 / vuosi2026, sama koodi, vuosi buildin parametrina): isot kromivuosiluvut Oceanin
; latausruutujen tyyliin. Data ja generoitu koodi (merkistö, numeroiden nauhat ja siirtorutiinit, kerneli,
; kehystaulut): build.py -> build/vuosi/<vuosi>/.
;
; Kehys:
;   LINE_TOP irq_top (vuosi.inc: numeroiden ensimmäinen rivi - 6, tällä datalla 77): kaksois-IRQ vakauttaa
;           ajoituksen, sitten kerneli (kernel.asm) vain numeroiden merkkiriveille (tällä datalla 83-210; muut rivit
;           tyhjiä, jolloin pääsäie saa niiden ajan seuraavan kohtauksen esilataukselle): joka rivin $D022 (kromi)
;           ja $D023 (ekstruusio, Y-indeksi) rivien välissä, kaistan rajalla $D018
;   kernelin perään: FRAME_HOOK (musiikki), seuraavan kehyksen tila: kromin vaihe ja kehyksen tapahtumat
;           (numeron liuku uuteen asemaan, laskeutuneen naapurin solut, lopulliset yhdistelmäsolut)

        .include "vuosi.inc"

        .weak
FRAME_HOOK = $0408
R_IDLE  = $0422
R_IRQ_ON = $041b                ; runko.inc: rungon IRQ rivillä 250 (vuosi_sauma)
DFRAME  = $d0
        .endweak

ZP0     = $90                   ; greetsit_init (jatkuva siirtymä) käyttää $30-$8f vuoden pyöriessä

        .virtual ZP0
z_pad   .byte ?                 ; bit z_pad: 3 syklin täyte kernelissä
z_d016  .byte ?                 ; seuraavan kehyksen $D016
z_src   .word ?                 ; slide: lähde, kohde, leveys, rivit, rivitaulun askel
z_dst   .word ?
z_n     .byte ?
z_r     .byte ?
z_s     .byte ?
z_y0    .byte ?                 ; seuraavan kehyksen kromin alkuindeksi (Y)
z_f     .word ?                 ; seuraavan kehyksen numero (0 = ensimmäinen näkyvä)
z_ev    .word ?                 ; tapahtumataulun osoitin
ra      .byte ?
rx      .byte ?
ry      .byte ?
busy    .byte ?                 ; kehyksen logiikka kesken
zp_end
        .cerror zp_end > $a2, "nollasivu ylittää $a1 (alun nimiruutu käyttää $a2:ta, jatkuva siirtymä alku -> vuosi1989)"
        .endv
drops   = $bf                   ; kehykset, joina logiikka ei ehtinyt (pitää olla 0); nollasivulla (inc 2 t),
                                ; mutta alun ($02-$bb) ja greetsien alustuksen ($30-$8f) ulkopuolella

        * = SCREEN
        .fill 1000, 0                   ; ruutu (ei levyllä: vuosi_init tyhjentää, numerot tulevat tapahtumista)
        * = CHARSET                     ; kaistojen merkistöt 2 kt:n välein (VIC-pankki 0, $2800-$3fff)
        .binary "charset.bin"
vic_end
        .cerror vic_end > $4000, "merkistöt yli $3fff"

        * = CODE_BASE                   ; VUOSI3: IRQ ja kerneli (init ja go logiikan alueella): vuosi1989
                                        ; esiladataan alun nimiruudun aikana, jolloin alku käyttää $fb00- (otb, IRQ)
; ---------------------------------------------------------------- IRQ: kerneli
irq_top
        sta ra
        stx rx
        sty ry
        lda #<irq_top2
        sta $fffe
        lda #>irq_top2
        sta $ffff
        inc $d012
        asl $d019
        tsx
        cli
        .fill 16, $ea
        sei
irq_top2
        txs
        ldx #8
-       dex
        bne -
        bit $00
        lda $d012
        cmp $d012
        beq irq_stable
irq_stable
        asl $d019               ; vakaa tästä (kernelin alku: build.py --start)
        .include "kernel.asm"
        lda #<irq_top
        sta $fffe
        lda #>irq_top
        sta $ffff
        lda #LINE_TOP
        sta $d012
        asl $d019
        lda ra                  ; rekisterit pinoon: sisäkkäinen irq_top käyttää ra/rx/ry:tä
        pha
        lda rx
        pha
        lda ry
        pha
        jsr FRAME_HOOK
        lda busy
        beq +
        inc drops
        jmp _out
+       inc busy
        cli
        jsr frame_next
        dec busy
        lda z_f+1                       ; viimeinen numero poissa (kehys 241): ruutu tyhjä, kerneli pois, jotta
        bne +                           ; seuraavan kohtauksen esilataus ehtii (pääsäie saa koko kehyksen)
        lda z_f
        cmp #OFF_FRAME
        bcc _out
+       sei
        lda #<irq_light
        sta $fffe
        lda #>irq_light
        sta $ffff
        lda #LINE_END                   ; sama rivi kuin kernelin perän FRAME_HOOK (soitin tasavälein)
        sta $d012
_out    pla
        tay
        pla
        tax
        pla
        rti
        .cerror irq_top2 >> 8 != irq_stable >> 8, "irq_top2:n tasaus ylittää sivun"

irq_light                               ; tyhjä ruutu: vain musiikki ja kello
        pha
        txa
        pha
        tya
        pha
        asl $d019
        jsr FRAME_HOOK
        pla
        tay
        pla
        tax
        pla
        rti

; vuosi_init: VUOSI1 (merkistöt) paikalleen, jos se ladattiin osoitteeseen STAGE (vuosi2026:
; kuoppa-kylttien aikana vapaa $6000-), tyhjä ruutu ja init2
vuosi_init
        .if STAGE != CHARSET
        lda #<STAGE
        sta z_src
        lda #>STAGE
        sta z_src+1
        lda #<CHARSET
        sta z_dst
        lda #>CHARSET
        sta z_dst+1
        ldx #(vic_end - CHARSET + 255) >> 8
        ldy #0
-       lda (z_src),y
        sta (z_dst),y
        iny
        bne -
        inc z_src+1
        inc z_dst+1
        dex
        bne -
        .endif
        lda #0
        tax
-       sta SCREEN,x
        sta SCREEN + $100,x
        sta SCREEN + $200,x
        sta SCREEN + $2e8,x
        inx
        bne -
        jmp init2

        ; kehyksen logiikka VUOSI3:ssa kernelin perässä: vuosi ei koske $4000-$bfff:ään, joten greetsit esiladataan
        ; vuoden aikana ja greetsit_init (ruudut $4000-$47ff) ajetaan vuoden pyöriessä (jatkuva siirtymä)

; ---------------------------------------------------------------- kehyksen logiikka
; frame_next: seuraava kehys (z_f + 1, enintään NFRAMES - 1) ja sen tila
frame_next
        inc z_f
        bne +
        inc z_f+1
+       lda z_f+1
        beq frame_state
        lda #<(NFRAMES - 1)             ; taulujen loppu: viimeinen tila pysyy
        sta z_f
        lda #>(NFRAMES - 1)
        sta z_f+1
; frame_state: kehyksen z_f kromin vaihe ja tapahtumat (liu'ut, naapurin solut, yhdistelmäsolut)
frame_state
        ldx z_f
        lda ch_ph,x
        sta z_y0
_ev     ldy #0                          ; tapahtuma: kehys (16 b), rutiini - 1, lähde, kohde, leveys, rivit, askel
        lda z_f
        cmp (z_ev),y
        iny
        lda z_f+1
        sbc (z_ev),y
        bcc _rts                        ; tapahtuman kehys > z_f (loppumerkki $ffff)
        ldy #10
-       lda (z_ev),y                    ; parametrit nollasivulle
        sta z_src - 4,y
        dey
        cpy #3
        bne -
        lda #>(_back - 1)               ; rts-hyppy rutiiniin, paluu _back:iin
        pha
        lda #<(_back - 1)
        pha
        lda (z_ev),y
        pha
        dey
        lda (z_ev),y
        pha
        rts
_back   lda z_ev
        clc
        adc #11
        sta z_ev
        bcc _ev
        inc z_ev+1
        jmp _ev
_rts    rts

; slide: z_r riviä, rivillä z_n tavua (z_src),y -> (z_dst),y; lähde z_s ja kohde 40 tavua eteenpäin riviltä
slide   ldx z_r
_row    ldy z_n
        dey
-       lda (z_src),y
        sta (z_dst),y
        dey
        bpl -
        lda z_src
        clc
        adc z_s
        sta z_src
        bcc +
        inc z_src+1
+       lda z_dst
        clc
        adc #40
        sta z_dst
        bcc +
        inc z_dst+1
+       dex
        bne _row
        rts

; init2: ruudun ja värimuistin alku (edellinen kohtaus voi näkyä: ei VIC-rekistereitä)
init2
        ldx #ZP0
        lda #0
-       sta $00,x
        inx
        cpx #zp_end
        bne -
        lda #D016_BASE
        sta z_d016
        lda #<ev_tab
        sta z_ev
        lda #>ev_tab
        sta z_ev+1
        jmp frame_state                 ; kehyksen 0 tila (tapahtumat ruutuun)

; vuosi_go: värimuisti, VIC (pankki 0) ja oma IRQ-ketju; palaa heti
vuosi_go
        sei
        lda #CELL_COL | 8               ; reunavalo (%11) ja MC-tila jokaiseen soluun
        ldx #0
-       sta $d800,x
        sta $d900,x
        sta $da00,x
        sta $dae8,x
        inx
        bne -
        lda #<irq_top
        sta $fffe
        lda #>irq_top
        sta $ffff
        lda #3                          ; VIC-pankki 0 ($0000-$3fff, ruutu $2400); $dd00:aan vain 0-3
        sta $dd00
        lda #((SCREEN & $3fff) >> 6) | ((CHARSET & $3fff) >> 10)
        sta $d018
        lda #D016_BASE
        sta $d016
        lda #D021_BG
        sta $d021
        lda #0
        sta $d020
        sta $d015
        lda #LINE_TOP
        sta $d012
        lda #$1b
        sta $d011
        lda #$ff
        sta $d019
        lda #1
        sta $d01a
        cli
        rts

        .include "code.asm"

code_end
        .cerror code_end > $fb00, "VUOSI3 yli $faff (alun nimiruutu käyttää $fb00-, part-alku.json vapaana_lopussa)"
        .cerror STAGE != CHARSET && (STAGE < $5f00 || STAGE + vic_end - CHARSET > $8000), "VUOSI1:n latausalue yli $5f00-$7fff"
        .cerror STAGE != CHARSET && STAGE < vic_end, "VUOSI1:n latausalue osuu kohteeseen"

        * = DATA_BASE                   ; taulut (sivutasatut kromitaulut, kromin vaihe, numeroiden rivitaulut)
data_start
        .include "data.asm"
        .include "evtab.asm"
        .if STAGE != CHARSET
; vuosi_sauma (koko demo, jatkuva siirtymä kuoppa-kyltit -> vuosi2026, part-vuosi2026.json jatkuva_alustus): kyltit
; käyttävät $1a00-$5e6a viimeiseen kehykseensä asti (viimeinen logo lentää), joten vuosi_init vasta sauman jälkeen:
; kuva pimeäksi, rungon IRQ (musiikki ja kello kulkevat), vuosi_init ja kehysten tila kiinni kelloon (vuoden omat
; ensimmäiset kehykset ovat mustia, liu'ut alkavat ajallaan). Palaa rivin 250 jälkeen, jolloin taulun vuosi_go ehtii
; ennen kernelin riviä LINE_TOP ja näkyvä kehys on z_f = DFRAME. VUOSI2:ssa (taulujen perässä), koska kyltit
; käyttävät $f800-:aa ja VUOSI3 päättyy $f7e3:een.
vuosi_sauma
        lda #$0b
        sta $d011
        lda #0
        sta $d015
        jsr R_IRQ_ON
        cli
        jsr vuosi_init
        jsr _kiinni
        lda DFRAME
-       cmp DFRAME                      ; rungon IRQ rivillä 250: kello kasvaa
        beq -
_kiinni lda z_f
        cmp DFRAME
        lda z_f+1
        sbc DFRAME+1
        bcs +
        jsr frame_next
        jmp _kiinni
+       rts
        .endif
data_end
        .cerror data_end > $d000, "taulut ylittävät $cfff"
        .cerror DATA_BASE == $4000 && data_end > $5000, "taulut yli $4fff (part-vuosi2026.json vapaana_lopussa $5000-)"
        .cerror DATA_BASE < $4000 && (data_start < vic_end || data_end > $4000), "taulut osuvat merkistöihin tai yli $3fff"
