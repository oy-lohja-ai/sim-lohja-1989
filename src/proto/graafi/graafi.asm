; Graafi (puutalot vs. laatikot): paluu kaupungintalon peliin Hillnerin purun jälkeen, Kaaviot-ikkuna.
; Data tools/gfx/data/graafi/, taulut build.py. Hires-bittikartta VIC-pankissa 2.
;
; Reaaliajassa 6510:llä (IRQ rivillä 250, kerran kehyksessä):
;   - kehyksestä 10: käyrät piirtyvät 2 x 2 px:n pisteinä vasemmalta oikealle (askel = 6/17 kehystä kohti,
;     ASKELEET askelta ~kehykseen 237): PUUTALOT punaisena laskee, LAATIKOT tummanharmaana nousee, KULTTUURIARVO
;     sinisenä nollassa. Piste: bittikartan tavu row_lo/hi[y] + (x & $f8), maski x:n mukaan, solun etuväri ruutuun.
;   - otsikon vuosi juoksee käyrän mukana 1989 -> 2026 (numeroiden kuviot solu kerrallaan)
;   - kehyksessä NEUVO_ALKU neuvonantajan ikkuna avautuu ylhäältä alas kolmessa kehyksessä, sitten teksti
;     «Kaupunkikuva: Erinomaista!» kirjoittuu merkki kerrallaan
;
; Muisti: neuvonantajan pala $2000, ruutu $8c00, koodi ja taulut $9000, bittikartta $a000.

        .include "graafi.inc"

FRAME_HOOK = $0408
DFRAME  = $d0
SCREEN  = $8c00
BITMAP  = $a000
IRQ_LINE = 250
NEUVO_ALKU = 240
TEKSTI_ALKU = NEUVO_ALKU + 12

        .virtual $02
ra      .byte ?
rx      .byte ?
ry      .byte ?
z_i     .byte ?                 ; seuraava piirrettävä askel
z_acc   .byte ?                 ; askelkertymä (6 / kehys, askel 17:n välein)
z_p     .word ?
z_x     .byte ?
z_y     .byte ?
z_c     .byte ?
z_np    .byte ?                 ; neuvonantajan ikkunan vaihe (0-3)
z_nt    .byte ?                 ; kirjoitettuja merkkejä
z_src   .word ?
z_dst   .word ?
z_dsc   .word ?
z_rows  .byte ?
zp_end
        .endv

        * = $2000
NEUVO   .binary "neuvo.bin"                     ; NEUVO_H riviä x NEUVO_W solua x 8 t, sitten värit
NTEKSTI .binary "neuvo_teksti.bin"              ; merkki: 8 t + väri
kt_data_end                                     ; GRAAFI1 $2000-tähän (syms.py)

        * = SCREEN
graafi2 .binary "graafi_scr.bin"                ; GRAAFI2 tästä graafi_endiin (syms.py)
        * = $9000
graafi_init
        ldx #ra
        lda #0
-       sta $00,x
        inx
        cpx #zp_end
        bne -
        rts

; graafi_show (#S_SHOW, ennen kelloa; graafi_go kutsuu myös): ensimmäinen kuva ilman IRQ:ta, jotta osalevyn kehys 0
; ei ole musta
graafi_show
        lda #1                          ; VIC-pankki 2
        sta $dd00
        lda #((SCREEN & $3fff) >> 6) | ((BITMAP & $3fff) >> 10)
        sta $d018
        lda #$3b                        ; hires-bittikartta
        sta $d011
        lda #$08
        sta $d016
        lda #0
        sta $d020
        sta $d015
        rts

graafi_go
        sei
        jsr graafi_show
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        lda #IRQ_LINE
        sta $d012
        lda #$ff
        sta $d019
        lda #1
        sta $d01a
        cli
        rts

irq
        sta ra
        stx rx
        sty ry
        asl $d019
        jsr FRAME_HOOK
        lda DFRAME+1
        bne _neuvo
        lda DFRAME
        cmp #10
        bcc _out
        cmp #NEUVO_ALKU
        bcs _neuvo
        lda z_acc                       ; käyrät
        clc
        adc #6
        sta z_acc
-       lda z_acc
        cmp #17
        bcc _out
        sbc #17
        sta z_acc
        ldx z_i
        cpx #ASKELEET
        bcs _out
        jsr askel
        inc z_i
        jmp -
_neuvo  jsr neuvo
_out    lda ra
        ldx rx
        ldy ry
        rti

; askel: X = askel: kolme käyrää ja otsikon vuosi
askel
        txa
        asl
        clc
        adc #GX0
        sta z_x
        lda y_kulttuuri,x
        ldy #VARI_KULTTUURI
        jsr piste
        ldx z_i
        lda y_laatikot,x
        ldy #VARI_LAATIKOT
        jsr piste
        ldx z_i
        lda y_puutalot,x
        ldy #VARI_PUUTALOT
        jsr piste
        ldx z_i                         ; vuosi: neljä numeroa otsikkoon
        lda v_tuh,x
        ldy #0
        jsr numero
        ldx z_i
        lda v_sat,x
        ldy #1
        jsr numero
        ldx z_i
        lda v_kym,x
        ldy #2
        jsr numero
        ldx z_i
        lda v_yks,x
        ldy #3
        jmp numero

; piste: A = y, Y = väri, z_x = x: 2 x 2 px riveille y ja y+1
piste
        sty z_c
        sta z_y
        jsr _rivi
        inc z_y
_rivi   ldx z_y
        lda z_x
        and #$f8
        clc
        adc row_lo,x
        sta z_p
        lda row_hi,x
        adc #0
        sta z_p+1
        lda z_x
        and #7
        tay
        lda _mask,y
        ldy #0
        ora (z_p),y
        sta (z_p),y
        lda z_y                         ; solun etuväri: ruutu rivi y/8, sarake x/8
        lsr
        lsr
        lsr
        tax
        lda z_x
        lsr
        lsr
        lsr
        clc
        adc crow_lo,x
        sta z_p
        lda crow_hi,x
        adc #0
        sta z_p+1
        lda z_c
        asl
        asl
        asl
        asl
        ora #15                         ; tausta vaaleanharmaa
        ldy #0
        sta (z_p),y
        rts
_mask   .byte $c0, $60, $30, $18, $0c, $06, $03, $01

; numero: A = numero 0-9, Y = paikka 0-3 otsikon vuodessa (kuvio solun 8 tavuun)
numero
        asl
        asl
        asl
        sta z_c                         ; kuvion alku numerot-taulussa
        tya
        clc
        adc #VUOSI_SAR
        asl
        asl
        asl
        clc
        adc #<(BITMAP + VUOSI_RIVI * 320)
        sta z_p
        lda #>(BITMAP + VUOSI_RIVI * 320)
        adc #0
        sta z_p+1
        ldx z_c
        ldy #0
-       lda numerot,x
        sta (z_p),y
        inx
        iny
        cpy #8
        bne -
        rts

; neuvonantaja: ikkuna kolmessa osassa (4 riviä / kehys), sitten teksti merkki kahden kehyksen välein
neuvo
        lda z_np
        cmp #3
        bcs _teksti
        jsr _osa
        inc z_np
        rts
_teksti lda DFRAME
        cmp #<TEKSTI_ALKU
        lda DFRAME+1
        sbc #>TEKSTI_ALKU
        bcc +
        lda DFRAME
        and #1
        bne +
        ldx z_nt
        cpx #NEUVO_N
        bcs +
        jsr _merkki
        inc z_nt
+       rts

; _osa: rivit z_np*4 .. +3 palasta NEUVO bittikarttaan ja ruutuun
_osa    lda z_np
        asl
        asl                             ; rivi palan sisällä
        sta z_rows
        ldx #4
-       stx _ox+1
        jsr _rivi_n
        inc z_rows
_ox     ldx #0
        dex
        bne -
        rts
_rivi_n lda z_rows                      ; bittikartta: NEUVO_W * 8 tavua palan riviltä
        ldx #NEUVO_W * 8
        jsr _mul                        ; z_src = NEUVO + rivi * W * 8
        lda z_rows
        clc
        adc #NEUVO_R0
        asl
        asl
        asl
        tax                             ; pikselirivi = solurivi * 8
        lda row_lo,x
        clc
        adc #<(NEUVO_C0 * 8)
        sta z_dst
        lda row_hi,x
        adc #>(NEUVO_C0 * 8)
        sta z_dst+1
        ldy #NEUVO_W * 8 - 1
-       lda (z_src),y
        sta (z_dst),y
        dey
        cpy #$ff
        bne -
        lda z_rows                      ; värit: NEUVO + H*W*8 + rivi * W
        ldx #NEUVO_W
        jsr _mul
        lda z_src
        clc
        adc #<(NEUVO_H * NEUVO_W * 8)
        sta z_src
        lda z_src+1
        adc #>(NEUVO_H * NEUVO_W * 8)
        sta z_src+1
        lda z_rows
        clc
        adc #NEUVO_R0
        tax
        lda crow_lo,x
        clc
        adc #NEUVO_C0
        sta z_dst
        lda crow_hi,x
        adc #0
        sta z_dst+1
        ldy #NEUVO_W - 1
-       lda (z_src),y
        sta (z_dst),y
        dey
        bpl -
        rts

; _mul: z_src = NEUVO + A * X (A < 16, X < 256)
_mul    sta _ma+1
        stx _mb+1
        lda #<NEUVO
        sta z_src
        lda #>NEUVO
        sta z_src+1
_ma     ldy #0
        beq _md
-       clc
        lda z_src
_mb     adc #0
        sta z_src
        bcc +
        inc z_src+1
+       dey
        bne -
_md     rts

; _merkki: X = merkki: 8 tavua ja väri NTEKSTI:stä soluun nt_lo/hi[X]
_merkki
        txa                             ; z_src = NTEKSTI + X * 9
        sta z_c
        asl
        asl
        asl
        clc
        adc z_c
        sta z_src
        lda #0
        adc #>NTEKSTI
        sta z_src+1
        lda z_src
        clc
        adc #<NTEKSTI
        sta z_src
        bcc +
        inc z_src+1
+       lda nt_lo,x                     ; bittikartta: BITMAP + solu * 8
        sta z_dst
        lda nt_hi,x
        sta z_dst+1
        asl z_dst
        rol z_dst+1
        asl z_dst
        rol z_dst+1
        asl z_dst
        rol z_dst+1
        lda z_dst+1
        clc
        adc #>BITMAP
        sta z_dst+1
        ldy #7
-       lda (z_src),y
        sta (z_dst),y
        dey
        bpl -
        lda nt_lo,x                     ; väri: SCREEN + solu
        sta z_dst
        lda nt_hi,x
        clc
        adc #>SCREEN
        sta z_dst+1
        ldy #8
        lda (z_src),y
        ldy #0
        sta (z_dst),y
        rts

numerot .binary "numerot.bin"
        .include "graafi_data.asm"
        .cerror * > $a000, "koodi ja taulut ylittävät bittikartan $a000"
        * = BITMAP
        .binary "graafi.bin"
graafi_end
