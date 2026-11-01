; Verteksit kappaleittain (Model.transform, project_obj, centre): palikat 0-2, timantti 3, heijastus 0-1.
;
; Rinnakkaisprojektio. Kappale = keskipiste c (cz = 0) + c_k * h_k * e_k, kantavektorit ruudulla
; bx_k = h_k * mx_k (Q9), by_k = h_k * my_k (Q8). Palikoilla sama kanta: kulmien siirtymät XO (4) ja YO (8)
; lasketaan kerran, palikka lisää vain keskipisteensä. Timantti: rengas q = (0,-1) (1,0) (0,1) (-1,0) ja c3.
; Heijastus: kanta 2 peilattu = YO[i ^ 2], oma keskipisteen y (y' = -cy - kk).

XBASE   = CXQ9 + 256            ; x = (XBASE + xs) >> 9

ADDW    .macro d, a, b          ; d = a + b (16 bittiä)
        clc
        lda \a
        adc \b
        sta \d
        lda \a+1
        adc \b+1
        sta \d+1
        .endm
SUBW    .macro d, a, b
        sec
        lda \a
        sbc \b
        sta \d
        lda \a+1
        sbc \b+1
        sta \d+1
        .endm
HADD    .macro a, b             ; A = ylätavu(a + b)
        clc
        lda \a
        adc \b
        lda \a+1
        adc \b+1
        .endm
HSUB    .macro a, b
        sec
        lda \a
        sbc \b
        lda \a+1
        sbc \b+1
        .endm
MULW    .macro y80, w           ; w = kerroin * (y80 ^ $80)
        ldy \y80
        #MULY
        sta \w+1
        lda pl
        sta \w
        .endm
NEGW    .macro d, s             ; d = -s
        sec
        lda #0
        sbc \s
        sta \d
        lda #0
        sbc \s+1
        sta \d+1
        .endm

transform
        lda #0                  ; heijastus täytön alusta (SW0) purun alkuun
        ldx exiting
        bne +
        lda t
        cmp #<SW0
        lda t+1
        sbc #>SW0
        lda #0
        rol a
+       sta rlive
        lda a00                 ; sarakkeet: mx = (a00, 0, a02), my = (a10, a11, a12), muodossa ^$80
        eor #$80
        sta mcx
        sta a00x
        lda #$80
        sta mcx+1
        lda a02
        eor #$80
        sta mcx+2
        lda a10
        eor #$80
        sta mcy
        sta a10x
        lda a11
        eor #$80
        sta mcy+1
        sta a11x
        lda a12
        eor #$80
        sta mcy+2
        ldx #0                  ; palikoiden kanta, determinantit ja kulmasiirtymät
        jsr basis
        lda #0
        sta ok
        jsr dets
        ldx #2                  ; sama kanta kaikille palikoille
-       lda dl,x
        sta dl+3,x
        sta dl+6,x
        lda dh,x
        sta dh+3,x
        sta dh+6,x
        dex
        bpl -
        ; XO[(c1 > 0) * 2 + (c3 > 0)] = c1 bx1 + c3 bx3
        #NEGW w0, bxw
        #SUBW xo, w0, bxw+4
        #ADDW xo+2, w0, bxw+4
        #SUBW xo+4, bxw, bxw+4
        #ADDW xo+6, bxw, bxw+4
        ; YO[(c1 > 0) * 4 + (c2 > 0) * 2 + (c3 > 0)] = -(c1 by1 + c2 by2 + c3 by3)
        #ADDW w0, byw, byw+2    ; by1 + by2
        #SUBW w1, byw, byw+2    ; by1 - by2
        #ADDW yo, w0, byw+4     ; c = (-,-,-): by1 + by2 + by3
        #SUBW yo+2, w0, byw+4   ; (-,-,+)
        #ADDW yo+4, w1, byw+4   ; (-,+,-): by1 - by2 + by3
        #SUBW yo+6, w1, byw+4   ; (-,+,+)
        #NEGW yo+14, yo         ; (+,+,+) = -(-,-,-) jne.
        #NEGW yo+12, yo+2
        #NEGW yo+10, yo+4
        #NEGW yo+8, yo+6
        ; laatikon puolikkaat: AX = |bx1| + |bx3|, AY = |by1| + |by2| + |by3| (XO:n ja YO:n ääriarvot)
        lda #0
        sta ax_
        sta ax_+1
        sta ay_
        sta ay_+1
        ldx #0
        jsr _absx
        ldx #4
        jsr _absx
        ldx #0
        jsr _absy
        ldx #2
        jsr _absy
        ldx #4
        jsr _absy
        lda rlive               ; heijastuksen keskipisteen siirto QR * a11 (etumerkitön QR)
        beq +
        lda a11
        sta tmp
        #SETMUL
        ldy #QR
        jsr mulsu
        lda pl
        sta qra
        lda ph
        sta qra+1
+       lda #1
        sta bact+3
        ldx #2
_b      stx ok
        lda #0                  ; palikka ei vielä alkanut (t < LAND): ei projektiota, tahkoja eikä aluetta
        sta bact,x              ; (Model: tasot 0, kasvu ei ala, ei merkkejä)
        lda t
        cmp landt_l,x
        lda t+1
        sbc landt_h,x
        bcs +
        jmp _nr
+       lda #1
        sta bact,x
        jsr centre
        jsr boxxy
        ldx ok                  ; palikan ruutulaatikko piirtoalueelle
        #HSUB xd, ax_
        lsr a
        sta obx0,x
        #HADD xd, ax_
        lsr a
        sta obx1,x
        #HSUB yd, ay_
        sta oby0,x
        #HADD yd, ay_
        sta oby1,x
        lda gfirst,x
        sta tmp
        ldy glast,x
        jsr store
        ldx ok                  ; heijastus: palikat 0 ja 1
        cpx #2
        bcs _nr
        lda rlive
        beq _nr
        jsr reflect
_nr     ldx ok
        dex
        bpl _b
        jsr gaps_b
        lda dvis
        bne +
        rts
+       lda dfly
        beq +
        jsr flight              ; mx, my lennon kierrosta (^$80)
+       ldx #1
        jsr basis
        lda #3
        sta ok
        jsr dets
        ldx #3
        jsr centre
        jsr diax
        jsr diay
        lda dfly
        bne _fly
        ldx #NV - 1             ; lukittu: kuten palikat
-       ldy vxidx,x
        lda xh,y
        lsr a
        sta sx,x
        ldy vyidx,x
        lda yh,y
        sta sy,x
        dex
        cpx #NB
        bcs -
        jmp gaps_d
_fly    ldx #NV - 1             ; lento: siirtymä oikealle ylös ja leikkaus kankaaseen
-       ldy vxidx,x
        lda xh,y
        lsr a
        clc
        adc dox
        cmp #W
        bcc +
        lda #W - 1
+       sta sx,x
        ldy vyidx,x
        lda yh,y
        sec
        sbc doy
        sec
        sbc #DFLY               ; lukituksessa y-väli valmiiksi (model.DFLY)
        bpl +
        lda #0
+       sta sy,x
        dex
        cpx #NB
        bcs -
        rts

_absx   lda bxw+1,x             ; ax_ += |bxw[x]|
        bpl +
        sec
        lda #0
        sbc bxw,x
        tay
        lda #0
        sbc bxw+1,x
        jmp ++
+       ldy bxw,x
+       sta tmp
        tya
        clc
        adc ax_
        sta ax_
        lda tmp
        adc ax_+1
        sta ax_+1
        rts
_absy   lda byw+1,x             ; ay_ += |byw[x]|
        bpl +
        sec
        lda #0
        sbc byw,x
        tay
        lda #0
        sbc byw+1,x
        jmp ++
+       ldy byw,x
+       sta tmp
        tya
        clc
        adc ay_
        sta ay_
        lda tmp
        adc ay_+1
        sta ay_+1
        rts

basis                           ; X = 0 palikat, 1 timantti: kantavektorit bxw/byw = h_k * m_k (h1 = h2; X-rivin
        lda hbx1,x              ; kerroin venytettynä, Model.ohx)
        #SETMUL
        #MULW mcx, bxw
        #MULW mcx+1, bxw+2
        lda hby1,x
        #SETMUL
        #MULW mcy, byw
        #MULW mcy+1, byw+2
        lda hbx3,x
        #SETMUL
        #MULW mcx+2, bxw+4
        lda hby3,x
        #SETMUL
        #MULW mcy+2, byw+4
        rts

DETP    .macro b                ; pl/A = kerroin * b (ylätavu, etumerkillinen)
        lda \b
        eor #$80
        tay
        #MULY
        .endm
dets                            ; kappale ok: D01, D02, D12 = bx_i by_j - by_i bx_j (kantojen ylätavut)
        lda ok
        sta tmp+7
        asl a
        adc tmp+7
        tax                     ; ok * 3
        lda bxw+1
        #SETMUL
        #DETP byw+3
        sta dh,x
        lda pl
        sta dl,x
        #DETP byw+5
        sta dh+1,x
        lda pl
        sta dl+1,x
        lda byw+1
        #SETMUL
        #DETP bxw+3
        sta tmp+1
        sec
        lda dl,x
        sbc pl
        sta dl,x
        lda dh,x
        sbc tmp+1
        sta dh,x
        #DETP bxw+5
        sta tmp+1
        sec
        lda dl+1,x
        sbc pl
        sta dl+1,x
        lda dh+1,x
        sbc tmp+1
        sta dh+1,x
        lda bxw+3
        #SETMUL
        #DETP byw+5
        sta dh+2,x
        lda pl
        sta dl+2,x
        lda byw+3
        #SETMUL
        #DETP bxw+5
        sta tmp+1
        sec
        lda dl+2,x
        sbc pl
        sta dl+2,x
        lda dh+2,x
        sbc tmp+1
        sta dh+2,x
        rts

YDOF    .macro                  ; yd = ybq8 + 128 - oyr
        sec
        lda #128
        sbc oyr
        sta yd
        lda ybh
        sbc oyr+1
        sta yd+1
        .endm

centre                          ; X = kappale: xd = XBASE + cx a00, yd = ybq8 + 128 - (cx a10 + cy a11)
        lda ocy,x
        sta tmp+6
        lda ocxs,x
        #SETMUL
        #MULW a00x, xd
        lda ocx,x
        #SETMUL
        #MULW a10x, oyr
        lda tmp+6
        #SETMUL
        ldy a11x
        #MULY
        tax
        clc
        lda pl
        adc oyr
        sta oyr                 ; yc (heijastus jatkaa tästä)
        txa
        adc oyr+1
        sta oyr+1
        clc
        lda xd
        adc #<XBASE
        sta xd
        lda xd+1
        adc #>XBASE
        sta xd+1
        #YDOF
        rts

boxxy                           ; palikan kulmat: xh[i] = hi(xd + XO[i]), yh[i] = hi(yd + YO[i])
        ldx #6
        ldy #3
-       clc
        lda xd
        adc xo,x
        lda xd+1
        adc xo+1,x
        sta xh,y
        dey
        dex
        dex
        bpl -
        ldx #14
        ldy #7
-       clc
        lda yd
        adc yo,x
        lda yd+1
        adc yo+1,x
        sta yh,y
        dey
        dex
        dex
        bpl -
        rts

diax                            ; xh[q * 2 + (c3 > 0)], x = xd + c1 bx1 + c2 bx2 + c3 bx3
        #SUBW w0, xd, bxw+2
        #ADDW w1, xd, bxw
        #ADDW w2, xd, bxw+2
        #SUBW w3, xd, bxw
        #HSUB w0, bxw+4
        sta xh
        #HADD w0, bxw+4
        sta xh+1
        #HSUB w1, bxw+4
        sta xh+2
        #HADD w1, bxw+4
        sta xh+3
        #HSUB w2, bxw+4
        sta xh+4
        #HADD w2, bxw+4
        sta xh+5
        #HSUB w3, bxw+4
        sta xh+6
        #HADD w3, bxw+4
        sta xh+7
        rts

diay                            ; y = yd - (c1 by1 + c2 by2 + c3 by3)
        #ADDW w0, yd, byw+2
        #SUBW w1, yd, byw
        #SUBW w2, yd, byw+2
        #ADDW w3, yd, byw
        #HADD w0, byw+4
        sta yh
        #HSUB w0, byw+4
        sta yh+1
        #HADD w1, byw+4
        sta yh+2
        #HSUB w1, byw+4
        sta yh+3
        #HADD w2, byw+4
        sta yh+4
        #HSUB w2, byw+4
        sta yh+5
        #HADD w3, byw+4
        sta yh+6
        #HSUB w3, byw+4
        sta yh+7
        rts

store                           ; verteksit tmp..Y: sx = xh >> 1, sy = yh
        sty tmp+1
        ldx tmp+1
-       ldy vxidx,x
        lda xh,y
        lsr a
        sta sx,x
        ldy vyidx,x
        lda yh,y
        sta sy,x
        dex
        bmi +
        cpx tmp
        bcs -
+       rts

reflect                         ; palikka ok (0/1): yc' = yc - QR a11, h = hi(yd' + YO[i ^ 2]),
                                ; y = min(ROWS - 1, max(HZ + 1, h)) (horisontin alle, kankaan loppuun)
        sec
        lda oyr
        sbc qra
        sta oyr
        lda oyr+1
        sbc qra+1
        sta oyr+1
        #YDOF
        lda ok                  ; etutahkon 4 kulmaa: rvx = sx (sama x)
        asl a
        asl a
        tax
        lda #4
        sta tmp+1
-       ldy rfv,x
        lda sx,y
        sta rvx,x
        lda vyidx,y
        eor #2
        asl a
        tay
        clc
        lda yd
        adc yo,y
        lda yd+1
        adc yo+1,y
        cmp #HZ + 1
        bcs +
        lda #HZ + 1
+       cmp #ROWS - 1
        bcc +
        lda #ROWS - 1
+       sta rvy,x
        inx
        dec tmp+1
        bne -
        rts
