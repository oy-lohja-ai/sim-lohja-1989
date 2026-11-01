; Alun nimiruudun IRQ-osa (title.prg:n välissä TCODE, tools/gfx/logo/title.py liittää): hand.asm title kutsuu tcodea
; kerran kehyksessä, kun kuva on pankissa 2. Ensimmäisellä kerralla värimuisti mustaksi; sitten:
;   ilmakuva  solu = ruutu- ja värimuistitavu lähteestä, kehyksellä t = 2 |cy - TLROW| + (3 cx) % 5 (aframe)
;   logo      ilmakuvan avauduttua spritelohkot (SPR, ruudun lähteen paikalla) nollataan ja spritet päälle (son),
;             sitten logon solutietueet (TLREC, TLCNT: montako kullakin kehyksellä) maalausjärjestyksessä
;   lappuset  iskuilla popk solutietueet title2.prg:stä (TPOP), kun se on ladattu (T2RDY, hand.asm title2_go)
; Spritekaistat: hand.asm lisää kehyksen tapahtumalistaan TSEVN tapahtumaa riveille TSEVL, ja ev_irq kutsuu TSPR:ää
; (Y = $80 | kaista): kaistan spritejen paikat (vieritys $d016/$d011:stä) ja osoittimet. Ei nollasivua (Hillnerin
; lataus ja hil_prep käyttävät sitä), vain DFRAME.
;
;   näkyvä ruutu $8000 (alussa nollia), värimuistin lähde $8400, ruudun lähde $8800, bittikartta $a000

        .include "consts.inc"
DFRAME  = $d0
SCR     = $8000
CSRC    = $8400
SSRC    = $8800

        * = TCODE
        jmp tcode               ; TCODE
        jmp tspr                ; TSPR = TCODE + 3
tsevn   .byte 0                 ; TSEVN = TCODE + 6: spritekaistojen tapahtumia (0, kunnes spritet ovat päällä)
t2rdy   .byte 0                 ; T2RDY = TCODE + 7: title2.prg ladattu
tlrdy   .byte 0                 ; TLRDY = TCODE + 8: titleb.prg (LCNT, LREC) ladattu
tsevl   .byte SEVL              ; TSEVL = TCODE + 9: tapahtumien rivit
        .cerror tsevn != TSEVN || t2rdy != T2RDY || tsevl != TSEVL || tlrdy != TLRDY, "TSEVN/T2RDY/TSEVL/TLRDY"

tcode   lda tinit
        bne _go
        inc tinit
        lda #0                  ; värimuisti mustaksi (purun ja viivan värit pois)
        tax
-       sta $d800,x
        sta $d900,x
        sta $da00,x
        sta $dae8,x
        inx
        bne -
_go     sec                     ; k = DFRAME - SCENE_START - TITLE0, enintään 254
        lda DFRAME
        sbc #<(SCENE_START + TITLE0)
        tax
        lda DFRAME+1
        sbc #>(SCENE_START + TITLE0)
        stx tk16                ; koko k lappusille (viimeinen yli 255:n)
        sta tk16+1
        bne +
        cpx #255                ; 255: lnext kiertäisi ympäri
        bcc ++
+       ldx #254
+       stx tkk
        lda #2                  ; ilmakuva: kehykset anext..k, enintään 2 kutsussa (myöhästynyt lataus kiinni)
        sta tbud
_a      lda anext
        cmp #AEND + 1
        bcs _sp
        cmp tkk
        beq +
        bcs _r
+       jsr aframe
        inc anext
        dec tbud
        bne _a
        rts
_sp     lda spron               ; ilmakuva auki: ruudun lähde on käytetty, spritet sen paikalle
        bne +
        jsr son
+       lda tlrdy               ; logo: kehykset lnext..k, enintään LBUD solua kutsussa (myöhästynyt titleb
        beq _x                  ; kurotaan kiinni)
        lda tlptr
        sta cptr
        lda tlptr+1
        sta cptr+1
        lda #LBUD
        sta tbud
        lda ln
        bne _c
_t      lda lnext
        cmp tkk
        beq +
        bcs _x
+       tax
        lda TLCNT,x
        sta ln
        inc lnext
_c      lda ln
        beq _t
        dec tbud
        bmi _x
        dec ln
        jsr cell
        jmp _c
_x      lda cptr
        sta tlptr
        lda cptr+1
        sta tlptr+1
        lda t2rdy               ; lappunen ponnahtaa iskulla: solut ilmakuvasta lappuseksi (TPOP)
        beq _r
        ldx pnext
        cpx #NPOP
        bcs _r
        lda tk16
        cmp popkl,x
        lda tk16+1
        sbc popkh,x
        bcc _r
        inc pnext
        lda tpptr
        sta cptr
        lda tpptr+1
        sta cptr+1
        jsr cset                ; solujen määrä
        ldy #0
        jsr cb
        sta tn
        jsr cadv
_p      lda tn
        beq +
        dec tn
        jsr cell
        jmp _p
+       lda cptr
        sta tpptr
        lda cptr+1
        sta tpptr+1
_r      rts

aframe  sta ak                  ; A = k: rivit TLROW +- r, joilla m = k - 2 r on 0..4, sarakkeet cx5[m] + 5 j
        tax
        bne _r
        ldy #4                  ; k = 0: viivan rivi kokonaan
-       lda cx5,y
        sta acx
        lda #TLROW
        jsr arow
        dey
        bpl -
        rts
_r      ldx #1
_l      txa
        asl a
        sta tmpr
        lda ak
        sec
        sbc tmpr
        bcc _e                  ; m < 0: suuremmat r myöhemmin
        cmp #5
        bcs _n
        tay
        lda cx5,y
        sta acx
        stx tmpr
        lda #TLROW
        sec
        sbc tmpr
        bcc +
        jsr arow
+       lda #TLROW
        clc
        adc tmpr
        cmp #25
        bcs _n
        jsr arow
_n      inx
        cpx #AEND / 2 - 1
        bcc _l
_e      rts

arow    sty _ry+1               ; A = rivi: sarakkeet acx, acx + 5, ... (X ja Y säilyvät)
        tay
        lda rlo,y
        sta _s+1
        sta _d+1
        sta _sc+1
        sta _dc+1
        lda rhi,y
        tay
        clc
        adc #>SSRC
        sta _s+2
        tya
        clc
        adc #>SCR
        sta _d+2
        tya
        clc
        adc #>CSRC
        sta _sc+2
        tya
        clc
        adc #>$d800
        sta _dc+2
        ldy acx
_s      lda SSRC,y
_d      sta SCR,y
_sc     lda CSRC,y
_dc     sta $d800,y
        tya
        clc
        adc #5
        tay
        cpy #40
        bcc _s
_ry     ldy #0
        rts

son     lda #0                  ; spritelohkot nollaan ja spritet päälle (MC, keltainen, $d025 vaaleanpunainen)
        tax
-       sta SPR,x
        sta SPR+$100,x
        sta SPR+$200,x
        sta SPR+$300,x
        inx
        bne -
        sta $d017
        sta $d01d
        sta $d01b
        sta $d026
        lda #SLRED
        sta $d025
        lda #SYELLOW
        ldx #7
-       sta $d027,x
        dex
        bpl -
        lda #SMASK
        sta $d01c
        sta $d015
        lda #NBAND
        sta tsevn
        inc spron
        rts

cell                            ; solutietue cptr:sta: o, o >> 8 | $80 (spritetavut), ruutu, väri, 8 tavua
        jsr cset                ; bittikarttaa $a000 + 8 o:hon, [spritetavujen osoite, 8 tavua 3 tavun välein]
        ldy #0
        jsr cb
        sta _ps+1
        sta _pc+1
        sta tmpo
        asl a
        asl a
        asl a
        sta _bm+1
        jsr cb
        sta tflag
        and #$7f
        tax
        clc
        adc #>SCR
        sta _ps+2
        txa
        clc
        adc #>$d800
        sta _pc+2
        txa
        asl a
        asl a
        asl a
        sta tmpb
        lda tmpo
        lsr a
        lsr a
        lsr a
        lsr a
        lsr a
        ora tmpb
        clc
        adc #$a0
        sta _bm+2
        jsr cb
_ps     sta SCR
        jsr cb
_pc     sta $d800
        ldx #0
-       jsr cb
_bm     sta $a000,x
        inx
        cpx #8
        bne -
        bit tflag
        bpl cadv
        jsr cb
        sta _sp+1
        jsr cb
        sta _sp+2
        ldx #0
-       jsr cb
_sp     sta SPR,x
        inx
        inx
        inx
        cpx #24
        bne -
cadv    tya                     ; cptr += luetut (Y)
        clc
        adc cptr
        sta cptr
        bcc +
        inc cptr+1
+       rts

cset    lda cptr                ; cb lukee cptr:sta
        sta cb+1
        lda cptr+1
        sta cb+2
        rts

cb      lda $ffff,y             ; A = (cptr + Y), Y + 1
        iny
        rts

tspr    stx _tx+1               ; ev_irq: Y = $80 | kaista (X säilyy)
        tya
        and #$7f
        tay
        lda $d011               ; Y = byb + ys (bittikartan vieritys), X = sxl/sxh + xs
        and #7
        clc
        adc byb,y
        sta _yv+1
        lda $d016
        and #7
        sta _xs+1
        lda bi+1,y
        sta _ie+1
        ldx bi,y
_l      ldy sreg,x
        lda sxl,x
        clc
_xs     adc #0
        sta $d000,y
_yv     lda #0
        sta $d001,y
        lda sxh,x
        adc #0
        lsr a                   ; C = X:n 9. bitti
        lda $d010
        ora smsk,x
        bcs +
        eor smsk,x
+       sta $d010
        ldy snum,x
        lda sptr,x
        sta SCR + $3f8,y
        inx
_ie     cpx #0
        bne _l
_tx     ldx #0
        rts

tinit   .byte 0
tbud    .byte 0
pnext   .byte 0
tkk     .byte 0
tk16    .word 0
anext   .byte 0
lnext   .byte 0
ln      .byte 0
tn      .byte 0
spron   .byte 0
ak      .byte 0
acx     .byte 0
tmpr    .byte 0
tmpo    .byte 0
tmpb    .byte 0
tflag   .byte 0
cptr    .word 0
tlptr   .word TLREC
tpptr   .word TPOP
        .include "title_tab.asm"        ; vakiot ja taulut (title.py)
        .cerror * > TLCNT, "nimiruudun koodi yli taulukoiden"
