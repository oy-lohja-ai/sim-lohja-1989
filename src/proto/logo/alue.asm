; Piirtoalue ja pystysuora täyttö (Model.render: täyttövaihe). Merkkipuskuri: mark.asm.

; ---------------------------------------------------------------- piirtoalue
; Sarakkeiden rivivälit ryhmien (palikat 0-2, timantti 3, heijastus 4) ruutulaatikoista: aktiivinen ryhmä
; kattaa sarakkeensa rivit min..max + 1 (alemman rivin merkki). Viivat ja AI ovat ryhmänsä laatikossa.
ranges
        ldx #COLS - 1
-       lda #$ff
        sta nlo,x
        lda #0
        sta nhi,x
        dex
        bpl -
        lda #$ff                ; käytetyt sarakkeet (täyttö käy vain välin min..max ja edellisen kuvan välin)
        sta ncmin
        lda #0
        sta ncmax
        ldx #2                  ; palikka aktiivinen: tahkoja tai kasvu > D0
_b      lda fact,x
        bne _bon
        txa
        asl a
        tay
        lda d0_l,x
        cmp grow,y
        lda d0_h,x
        sbc grow+1,y
        bcs _bn
_bon    lda obx0,x
        sta bx0
        lda obx1,x
        sta bx1
        lda oby0,x
        sta by0
        lda oby1,x
        sta by1
        jsr range1
_bn     dex
        bpl _b
        lda dvis
        beq +
        ldx #3
        lda gfirst,x
        ldy glast,x
        jsr vbox
        jsr range1
+       lda rdone
        beq _r
        ldx #1                  ; heijastus: palikoittain, alkaneet (viivojen peilikuva jo ennen täyttöä)
_rb     lda bact,x
        beq _rn
        lda #255
        sta bx0
        sta by0
        lda #0
        sta bx1
        sta by1
        txa
        asl a
        asl a
        tay
        lda #4
        sta tmp+6
-       lda rvx,y
        cmp bx0
        bcs +
        sta bx0
+       cmp bx1
        bcc +
        sta bx1
+       lda rvy,y
        cmp by0
        bcs +
        sta by0
+       cmp by1
        bcc +
        sta by1
+       iny
        dec tmp+6
        bne -
        jsr range1
_rn     dex
        bpl _rb
_r      rts

vbox                            ; verteksit A..Y -> bx0 bx1 by0 by1 (X säilyy)
        sta tmp
        lda #255
        sta bx0
        sta by0
        lda #0
        sta bx1
        sta by1
-       lda sx,y
        cmp bx0
        bcs +
        sta bx0
+       cmp bx1
        bcc +
        sta bx1
+       lda sy,y
        cmp by0
        bcs +
        sta by0
+       cmp by1
        bcc +
        sta by1
+       dey
        bmi +
        cpy tmp
        bcs -
+       rts

range1                          ; laatikko sarakeväleihin (X säilyy)
        stx tmp+7
        lda by1
        clc
        adc #1
        cmp #ROWS
        bcc +
        lda #ROWS - 1
+       sta by1
        lda bx1
        lsr a
        lsr a
        sta tmp
        lda bx0
        lsr a
        lsr a
        tax
        cmp ncmin
        bcs +
        sta ncmin
+       lda tmp
        cmp ncmax
        bcc +
        sta ncmax
+
-       lda by0
        cmp nlo,x
        bcs +
        sta nlo,x
+       lda by1
        cmp nhi,x
        bcc +
        sta nhi,x
+       inx
        cpx tmp
        bcc -
        beq -
        ldx tmp+7
        rts

; ---------------------------------------------------------------- täyttö
; Sarake c: rivit min(uusi, puskurin edellinen) .. max, pariteetit erikseen: ketjuun rivin r0 kohdalta,
; poistuminen rts:llä rivin r1 + 2 kohdalla. Jokainen ketjun rivi alkaa eor abs,x ($5d): paikka palautetaan
; sillä, ja sama poistumiskohta jää paikalleen seuraavalle sarakkeelle. X = sarake * 8, A = kertymä, Y = 0.
fill
        ldx #0                  ; sisääntulotaulut puskurin mukaan (paikataan hakuihin)
        lda back
        beq +
        ldx #4
+       lda _tabs,x
        sta _t0+1
        sta _t2+1
        sta _t4+1
        lda _tabs+1,x
        sta _t0+2
        sta _t2+2
        sta _t4+2
        lda _tabs+2,x
        sta _t1+1
        sta _t3+1
        sta _t5+1
        lda _tabs+3,x
        sta _t1+2
        sta _t3+2
        sta _t5+2
        lda back
        beq +
        lda #COLS
+       sta boff
        lda #0
        sta pex+1               ; ei paikattuja poistumiskohtia
        sta pex+3
        ldy back                ; sarakeväli: tämä ja puskurin edellinen (tyhjä: min $ff > max)
        lda ncmin
        cmp ocmin,y
        bcc +
        lda ocmin,y
+       sta fcmin
        lda ncmax
        cmp ocmax,y
        bcs +
        lda ocmax,y
+       sta fcmax
        lda ncmin
        sta ocmin,y
        lda ncmax
        sta ocmax,y
        lda fcmin
        cmp fcmax
        beq +
        bcc +
        jmp _pp                 ; ei sarakkeita
+       ldx fcmax
_c      stx fcol
        txa
        clc
        adc boff
        tay
        lda nlo,x
        cmp olo,y
        bcc +
        lda olo,y
+       sta flo
        lda nhi,x
        cmp ohi,y
        bcs +
        lda ohi,y
+       sta fhi
        lda nlo,x
        sta olo,y
        lda nhi,x
        sta ohi,y
        lda flo
        cmp fhi
        beq +
        bcs _nx
+       txa
        asl a
        asl a
        asl a
        sta fx8
        lda flo                 ; parillinen ketju: r0 = (lo + 1) & ~1, r1 = hi & ~1
        clc
        adc #1
        and #$fe
        sta tmp
        lda #0
        sta tmp+2
        lda fhi
        and #$fe
        jsr _par
        lda flo                 ; pariton: r0 = lo | 1, r1 = (min(hi, ODDMAX + 1) - 1) | 1 (heijastuksen
        ora #1                  ; parittomat rivit pysyvät tyhjinä)
        sta tmp
        lda #2
        sta tmp+2
        lda fhi
        cmp #ODDMAX + 1
        bcc +
        lda #ODDMAX + 1
+       sec
        sbc #1
        ora #1
        jsr _par
_nx     ldx fcol
        cpx fcmin
        beq _pp
        dex
        jmp _c
_pp     ldx #2                  ; paikat pois
-       lda pex+1,x
        beq +
        lda #$5d
        sta (pex,x)
+       dex
        dex
        bpl -
        rts

_tabs   .word fentA_l, fentA_h, fentB_l, fentB_h

_par    cmp tmp                 ; A = r1, tmp = r0 (samaa pariteettia), tmp+2 = pariteetti * 2; r1 < r0: ei rivejä
        bcc _px
        cmp #$f0
        bcs _px                 ; r1 = -1
        adc #2                  ; C = 0
        tay
        ldx tmp+2               ; pariteetin oma poistumispaikka (ketjut erilliset: molemmat voivat olla päällä)
_t0     lda fentA_l,y           ; (paikattu)
        cmp pex,x
        bne _new
_t1     lda fentA_h,y
        cmp pex+1,x
        beq _go
_new    lda pex+1,x             ; vanha paikka pois, uusi rts
        beq +
        lda #$5d
        sta (pex,x)
+
_t2     lda fentA_l,y
        sta pex,x
_t3     lda fentA_h,y
        sta pex+1,x
        lda #$60
        sta (pex,x)
_go     ldy tmp
_t4     lda fentA_l,y
        sta jv
_t5     lda fentA_h,y
        sta jv+1
        ldx fx8
        ldy #0
        tya
        jmp (jv)
_px     rts
