; Alkuruudun kuva: näkyvyys ja sävy, särmien merkit, täyttö, vaakaviiva, lankamalli, AI ja heijastus.
; Model.render (tools/gfx/logo/model.py) samassa järjestyksessä.

render
        #PHASE $ff
        jsr state
        #PHASE 0
        jsr coeffs
        jsr transform
        #PHASE 1
        jsr shade
        #PHASE 2
        jsr marks
        jsr bevel
        #PHASE 3
        jsr ai
        jsr refl
        #PHASE 4
        jsr ranges
        jsr fill
        #PHASE 5
        jsr strokes
        #PHASE 6
        rts

; ---------------------------------------------------------------- näkyvyys ja sävy (Model.cull_shade)
DOT3    .macro r0, r1, r2       ; pl/ph = r0 lc0 + r1 lc1 + r2 lc2 -> A = >> 7
        lda \r0
        ldy lc0
        jsr mulacc0
        lda \r1
        ldy lc1
        jsr mulacc
        lda \r2
        ldy lc2
        jsr mulacc
        jsr shr7
        .endm

MACC    .macro v, acc           ; acc (16 bittiä) += kerroin * v (v etumerkillinen, Y = v ^ $80)
        lda \v
        eor #$80
        tay
        #MULY
        tax
        clc
        lda pl
        adc \acc
        sta \acc
        txa
        adc \acc+1
        sta \acc+1
        .endm

shade                           ; valo mallissa: lm = R^T lc >> 7, kappaleen paikka objt = (cx lc0 + cy lc1) >> 9
        ldx #13
        lda #0
-       sta lacc,x
        dex
        bpl -
        lda lc0
        #SETMUL
        #MACC cy_, lacc
        #MACC sy_, lacc+4
        ldx #3                  ; lacc+6.. alatavut, lacc+10.. ylätavut
-       ldy objcx,x
        #MULY
        sta lacc+10,x
        lda pl
        sta lacc+6,x
        dex
        bpl -
        lda lc1
        #SETMUL
        #MACC r10, lacc
        #MACC cp_, lacc+2
        #MACC r12, lacc+4
        ldx #3
-       ldy objcy,x
        #MULY
        sta ph
        clc
        lda pl
        adc lacc+6,x
        lda ph
        adc lacc+10,x
        cmp #$80                ; >> 9
        ror a
        sta objt,x
        dex
        bpl -
        lda lc2
        #SETMUL
        #MACC r20, lacc
        #MACC sp_, lacc+2
        #MACC r22, lacc+4
        lda lacc                ; >> 7
        asl a
        lda lacc+1
        rol a
        sta lmx
        lda lacc+2
        asl a
        lda lacc+3
        rol a
        sta lmy
        lda lacc+4
        asl a
        lda lacc+5
        rol a
        sta lmz
        ldx #NNID - 1
        lda #0
-       sta ndone,x
        dex
        bpl -
        ldx #3
-       sta fact,x
        dex
        bpl -
        ldx #NF - 1
_f      stx fi
        lda #0
        sta level,x
        sta fvis,x
        ldy fblk,x              ; palikka ei alkanut: ohi
        lda bact,y
        beq _n
        lda fcand,x
        beq _n
        cmp #2
        bne +
        lda dvis                ; timantti
        beq _n
+       ldy fda,x               ; F = +-D[a] (+-D[b]) > 0: näkyvä
        lda dl,y
        sta tmp
        lda dh,y
        sta tmp+1
        lda fsa,x
        beq +
        lda #0
        sec
        sbc tmp
        sta tmp
        lda #0
        sbc tmp+1
        sta tmp+1
+
        ldy fdb,x
        bmi _t
        lda fsb,x
        bne _sb
        clc
        lda tmp
        adc dl,y
        sta tmp
        lda tmp+1
        adc dh,y
        jmp _t2
_sb     sec
        lda tmp
        sbc dl,y
        sta tmp
        lda tmp+1
        sbc dh,y
_t2     sta tmp+1
_t      lda tmp+1           ; F > DET_MIN
        bmi _n
        bne +
        lda tmp
        cmp #DET_MIN + 1
        bcc _n
+        ldx fi
        lda #1
        sta fvis,x
        lda fcand,x
        cmp #2
        bne +
        lda dfly                ; lentävä timantti: vain lankamalli
        bne _n
+       lda fw,x
        beq _n
        sta tmp+6
        ldy fnid,x              ; pistetulo normaalin kanssa (kerran per normaali)
        lda ndone,y
        bne _hav
        lda #1
        sta ndone,y
        sty tmp+7
        lda lmx
        ldx nx7,y
        jsr dotacc0
        ldy tmp+7
        lda lmy
        ldx ny7,y
        jsr dotacc
        ldy tmp+7
        lda lmz
        ldx nz7,y
        jsr dotacc
        jsr shr7
        ldy tmp+7
        sta ndot,y
        ldx fi
_hav    lda ndot,y
        bpl +
        lda #0
+       tay
        lda dift,y
        clc
        adc #AMBIENT
        sta tmp
        ldy fblk,x
        lda objt,y
        bmi _neg
        clc
        adc tmp
        bcc _cl
        lda #255
        bne _cl
_neg    clc
        adc tmp
        bcs _cl
        lda #0
_cl     tay
        lda fside,x             ; sivu- ja ylätahkot himmeämmin (Model.FULLS)
        beq +
        lda fullside,y
        jmp _fs
+       lda fulltab,y
_fs     ldy tmp+6
        cpy #255
        beq _st
        sta tmp                 ; max(1, (full * (w >> 1) + 64) >> 7)
        #SETMUL
        lda tmp+6
        lsr a
        eor #$80
        tay
        #MULY
        sta ph
        clc
        lda pl
        adc #64
        sta pl
        bcc +
        inc ph
+       jsr shr7
        bne _st
        lda #1
_st     ldx fi
        sta level,x
        ldy fblk,x
        sta fact,y
_n      ldx fi
        dex
        bmi +
        jmp _f
+       rts

dotacc0                         ; A = kerroin, X = kerrottava ^$80 -> pl/ph
        stx tmp+5
        #SETMUL
        ldy tmp+5
        #MULY
        sta ph
        rts
dotacc  stx tmp+5
        ldx pl
        stx xs
        ldx ph
        stx xs+1
        #SETMUL
        ldy tmp+5
        #MULY
        sta ph
        clc
        lda pl
        adc xs
        sta pl
        lda ph
        adc xs+1
        sta ph
        rts

; ---------------------------------------------------------------- särmien merkit
marks                           ; särmät, joiden tahkojen tasot eroavat (verkko suljettu: ef1 aina tahko)
        ldx #NE - 1
_e      ldy ef0,x
        lda level,y
        ldy ef1,x
        cmp level,y
        bne _d
_n      dex
        bpl _e
        rts
_d      stx ei
        sta tmp
        ldy ea,x                ; pystysuora (sama x): ei merkkejä
        lda sx,y
        ldy eb,x
        cmp sx,y
        beq _s
        sta xa
        lda sx,y
        sta xb
        lda sy,y
        sta yb
        ldy ea,x
        lda sy,y
        sta ya
        ldy ef1,x
        lda level,y
        tay
        ldx tmp
        lda pat,x
        eor pat,y
        sta de
        lda pato,x
        eor pato,y
        sta do
        jsr mark
_s      ldx ei
        jmp _n

; ---------------------------------------------------------------- viisteet (Model.render: bevels)
bevel                           ; etutahkon vasen reuna a-b tummana BW MC px suikaleena: a-b, b-b+BW, b+BW-a+BW, a+BW-a
        ldx #NBEV - 1
_e      stx ei
        ldy bvf,x
        lda level,y
        beq _s
        tay
        lda pat,y
        eor bevp,y
        sta bvd
        lda pato,y
        eor bevpo,y
        sta bvd+1
        ldy bva,x
        lda sx,y
        sta bvx
        lda sy,y
        sta bvy
        ldy bvb,x
        lda sx,y
        sta bvx+1
        lda sy,y
        sta bvy+1
        lda bvx                 ; a - b
        ldx bvy
        ldy #0
        jsr _m
        lda bvx+1               ; b - b+1 (pystysuuntaiset a-b ja a+1-b+1 kuten marks: sama x ei merkitse)
        ldx bvy+1
        ldy #1
        jsr _m
        lda bvx                 ; a+BW - b+BW
        clc
        adc #BW
        sta bvx
        lda bvx+1
        clc
        adc #BW
        sta bvx+1
        lda bvx
        ldx bvy
        ldy #0
        jsr _m
        lda bvx                 ; a+BW - a
        sec
        sbc #BW
        sta bvx
        clc
        adc #BW
        ldx bvy
        ldy #2
        jsr _m
_s      ldx ei
        dex
        bpl _e
        rts
_m      sta xa                  ; (xa, ya) = A, X; (xb, yb): Y = 0 b, 1 b+BW samalla rivillä, 2 a samalla rivillä
        stx ya
        cpy #1
        beq _h1
        bcs _h2
        lda bvx+1
        sta xb
        lda bvy+1
        sta yb
        jmp _go
_h1     clc
        adc #BW
        sta xb
        stx yb
        jmp _go
_h2     lda bvx
        sta xb
        stx yb
_go     lda xa                  ; sama x: ei merkkejä (Model.mark_edge 0 saraketta)
        cmp xb
        beq +
        lda bvd
        sta de
        lda bvd+1
        sta do
        jmp mark
+       rts

; ---------------------------------------------------------------- lankamalli (Model.strokes)
strokes
        lda fwall               ; kaikki tahkot kiinteitä: ei viivoja
        cmp #255
        bne +
        rts
+       lda #$ff                ; palikat kiinteitä (lento): vain timantin särmät listasta
        sta slist
        lda fwblk
        cmp #255
        bne +
        lda #0
        sta slist
        ldx dedge
        .byte $2c
+       ldx #0
_e      stx ei
        lda edia,x
        beq _nd
        lda dfly
        beq _dx
        lda dvis
        bne +
        jmp _n
+       ldy ef0,x               ; takasärmä pois
        lda fvis,y
        bne +
        ldy ef1,x
        lda fvis,y
        bne +
        jmp _n
+       ldy ea,x
        lda sx,y
        sta lx0
        lda sy,y
        sta ly0
        ldy eb,x
        lda sx,y
        sta lx1
        lda sy,y
        sta ly1
        jmp _draw
_dx                             ; lukittu timantti: rautalankana kuten palikat (purussa kasvu)
_nd     ldy ef0,x               ; takasärmä (kumpikaan tahko ei näy): ei viivaa
        lda fvis,y
        bne +
        ldy ef1,x
        cpy #255
        beq _nj
        lda fvis,y
        beq _nj
+       ldy ef0,x               ; molemmat tahkot kiinteitä: ei viivaa
        lda fw,y
        beq +
        ldy ef1,x
        cpy #255
        beq _nj
        lda fw,y
        bne _nj
+       lda edia,x              ; lukittu timantti ennen purkua: koko särmä (Model.strokes)
        beq +
        lda exiting
        bne +
        jmp _full
+       ldy eblk,x              ; g = grow[blk] - start
        tya
        asl a
        tay
        sec
        lda grow,y
        sbc est_l,x
        sta tmp
        lda grow+1,y
        sbc est_h,x
        sta tmp+1
        bmi _nj
        ora tmp
        beq _nj
        ldy ea,x
        lda sx,y
        sta lx0
        lda sy,y
        sta ly0
        ldy eb,x
        lda sx,y
        sta lx1
        lda sy,y
        sta ly1
        lda tmp                 ; g >= len: koko särmä
        cmp eln_l,x
        lda tmp+1
        sbc eln_h,x
        bcs _draw
        lda erl_l,x             ; p = g * RLEN >> 8 (< 256)
        sta tmp+2
        lda erl_h,x
        sta tmp+3
        jsr mulshr8
        lda tmp+4
        lsr a
        jsr lpart
        jmp _draw
_full   ldy ea,x
        lda sx,y
        sta lx0
        lda sy,y
        sta ly0
        ldy eb,x
        lda sx,y
        sta lx1
        lda sy,y
        sta ly1
_draw   jsr line
_nj
_n      ldy slist
        bpl _l
        ldx ei
        inx
        cpx #NE
        beq +
        jmp _e
+       rts
_l      iny
        cpy #NDE
        beq +
        sty slist
        ldx dedge,y
        jmp _e
+       rts

lpart                           ; A = p >> 1: (lx1, ly1) = a + (b - a) * (p >> 1) >> 7 (Model.part)
        #SETMUL
        lda lx1
        sec
        sbc lx0
        eor #$80
        tay
        #MULY
        sta ph
        jsr shr7
        clc
        adc lx0
        sta lx1
        lda ly1
        sec
        sbc ly0
        eor #$80
        tay
        #MULY
        sta ph
        jsr shr7
        clc
        adc ly0
        sta ly1
        rts

line                            ; Model.line: (lx0, ly0) - (lx1, ly1) vasemmalta oikealle, väri 11 OR
        lda lx0
        cmp lx1
        bcc +
        beq +
        ldx lx1
        stx lx0
        sta lx1
        lda ly0
        ldx ly1
        stx ly0
        sta ly1
+       lda ly0                 ; ptr = solurivi + sarake * 8, Y = rivi & 7
        and #$f8
        tay
        lda lx0
        and #$fc
        asl a
        clc
        adc drowa_l,y
        sta ptr
        lda drowa_h,y
        adc bufh
        sta ptr+1
        lda lx0
        and #3
        tax
        lda maskt,x
        sta lmk
        lda lx1
        sec
        sbc lx0
        sta ldx_
        lda ly1
        sec
        sbc ly0
        bcs _dn
        eor #$ff
        adc #1
        sta ldy_
        lda ly0
        and #7
        tay
        lda ldy_
        cmp ldx_
        bcc +
        beq +
        jmp ymu
+       jmp xmu
_dn     sta ldy_
        lda ly0
        and #7
        tay
        lda ldy_
        cmp ldx_
        bcc +
        beq +
        jmp ymd
+       jmp xmd

ROWDN   .macro                  ; Y = rivi & 7, ptr solurivi: rivi alas
        iny
        cpy #8
        bne +
        ldy #0
        lda ptr
        clc
        adc #<320
        sta ptr
        lda ptr+1
        adc #>320
        sta ptr+1
+
        .endm
ROWUP   .macro
        dey
        bpl +
        ldy #7
        lda ptr
        sec
        sbc #<320
        sta ptr
        lda ptr+1
        sbc #>320
        sta ptr+1
+
        .endm

XMAJ    .macro up               ; dx >= dy: saman rivin pikselit kerätään tavuun
        lda ldx_
        lsr a
        sta lerr
        ldx ldx_
        inx
        lda #0
        sta mb
_l      lda mb
        ora lmk
        sta mb
        dex
        beq _f
        lda lerr
        sec
        sbc ldy_
        bcs _n
        adc ldx_
        sta lerr
        lda (ptr),y
        ora mb
        sta (ptr),y
        lda #0
        sta mb
        .if \up
        #ROWUP
        .else
        #ROWDN
        .endif
        jmp _s
_n      sta lerr
_s      lsr lmk
        lsr lmk
        bne _l
        lda (ptr),y
        ora mb
        sta (ptr),y
        lda #0
        sta mb
        lda #$c0
        sta lmk
        lda ptr
        clc
        adc #8
        sta ptr
        bcc _l
        inc ptr+1
        jmp _l
_f      lda (ptr),y
        ora mb
        sta (ptr),y
        rts
        .endm

YMAJ    .macro up               ; dy > dx: piste joka rivillä
        lda ldy_
        lsr a
        sta lerr
        ldx ldy_
        inx
_l      lda (ptr),y
        ora lmk
        sta (ptr),y
        dex
        bne +
        rts
+       .if \up
        #ROWUP
        .else
        #ROWDN
        .endif
        lda lerr
        sec
        sbc ldx_
        bcs _n
        adc ldy_
        sta lerr
        lsr lmk
        lsr lmk
        bne _l
        lda #$c0
        sta lmk
        lda ptr
        clc
        adc #8
        sta ptr
        bcc _l
        inc ptr+1
        jmp _l
_n      sta lerr
        jmp _l
        .endm

xmd     #XMAJ 0
xmu     #XMAJ 1
ymd     #YMAJ 0
ymu     #YMAJ 1

; ---------------------------------------------------------------- kaiverrettu AI (Model.ai_place, ai_stamp)
; Kirjainten rajojen merkit valmiista leimasta (koko pystylävistäjän mukaan, siirros x & 3) etutahkon keskelle.
ai
        ldx level + DFRONT
        bne +
        rts
+       lda pat,x               ; erotus tahkon ja tummemman tason kuvioista
        sta tmp
        lda pato,x
        sta tmp+1
        ldy aidim,x
        lda pat,y
        eor tmp
        sta de
        lda pato,y
        eor tmp+1
        sta do
        lda sx + DF_B           ; keskipiste
        clc
        adc sx + DF_T
        lsr a
        sta tmp+2               ; cx
        lsr a
        lsr a
        sta tmp+3               ; cx >> 2
        lda sy + DF_B
        clc
        adc sy + DF_T
        ror a
        sta tmp+4               ; cy
        lda sy + DF_B           ; koko: pystylävistäjä - AI_VY0 rajattuna 0..AI_NK-1
        sec
        sbc sy + DF_T
        sec
        sbc #AI_VY0
        bcs +
        lda #0
+       cmp #AI_NK
        bcc +
        lda #AI_NK - 1
+       asl a
        asl a
        sta tmp
        lda tmp+2
        and #3
        ora tmp
        tax
        lda aisp_l,x            ; tietueet aisp[x] .. aisp[x + 1]
        sta ptr2
        lda aisp_h,x
        sta ptr2+1
        sec
        lda aisp_l+1,x
        sbc ptr2
        sta tmp+5               ; tavuja
        ldy #0
_e      sty ei
        lda (ptr2),y            ; rivi
        clc
        adc tmp+4
        tax
        lda ephi,x
        sta ptr+1
        txa
        and #7
        sta tmp+6
        iny
        lda (ptr2),y            ; tavusarake
        clc
        adc tmp+3
        asl a
        asl a
        asl a
        sta ptr
        iny
        lda (ptr2),y            ; maski
        ldy tmp+6
        jsr flush
        lda ei
        clc
        adc #3
        tay
        cpy tmp+5
        bne _e
        rts

; ---------------------------------------------------------------- heijastus (Model.reflection)
refl                            ; Model.reflection: etutahkojen reunat kunkin palikan oman tason kuviolla, parittomat rivit tyhjinä
        lda rlive
        sta rdone
        bne +
        rts
+       ldx #7
_e      stx ei
        txa                     ; palikan etutahkon taso (0 = ei vielä)
        lsr a
        lsr a
        tay
        lda rff,y
        tay
        lda level,y
        beq _s
        tay
        lda rsolid,y            ; kiinteä koodi tason mukaan (Model.REFL_SOLID)
        sta de
        lda #0                  ; parittomat rivit mustia (vesi)
        sta do
        ldx ei
        lda rvx,x
        sta xa
        lda rvy,x
        sta ya
        txa                     ; seuraava kulma samassa tahkossa
        and #4
        sta tmp
        dex
        txa
        and #3
        ora tmp
        tax
        lda rvx,x
        sta xb
        lda rvy,x
        sta yb
        jsr mark
_s      ldx ei
        dex
        bpl _e
        rts

; ---------------------------------------------------------------- vaiheprofiili (mittari, luetaan emulaattorista)
; aika rasteririveinä: DFRAME * 312 + rivi (kehys vaihtuu rivillä IRQ_BOT); X = vaihe (0..7), $ff = vain aloitus
        .if PROF
prof    stx profk           ; aika: kehykset (DFRAME, vaihtuu rivillä IRQ_BOT) ja rivi; erotus edellisestä
        php
        sei
        lda $d011
        sta tmp+5
        lda $d012
        sta tmp+6
        lda DFRAME
        sta tmp+7
        plp
        lda tmp+5               ; rivi 9 bittiä -> rivi - IRQ_BOT (mod 312) = r'
        asl a
        lda #0
        rol a
        sta tmp+5
        sec
        lda tmp+6
        sbc #<IRQ_BOT
        sta tmp+6
        lda tmp+5
        sbc #>IRQ_BOT
        bcs +
        lda tmp+6
        adc #<312
        sta tmp+6
        lda #0
        adc #>312
+       sta tmp+5
        ldx profk
        cpx #$ff
        beq _st
        sec                     ; dF = kehykset edellisestä, delta = dF * 312 + (r' - r'_ed)
        lda tmp+7
        sbc proff
        ldy #56
        pha
        jsr umul8
        pla
        clc
        adc ph
        sta ph                  ; dF * 256 + dF * 56
        sec
        lda tmp+6
        sbc proflast
        sta tmp
        lda tmp+5
        sbc proflast+1
        sta tmp+1
        clc
        lda tmp
        adc pl
        sta tmp
        lda tmp+1
        adc ph
        sta tmp+1
        ldx profk
        clc
        lda profl,x
        adc tmp
        sta profl,x
        lda profm,x
        adc tmp+1
        sta profm,x
        bcc _st
        inc profh,x
_st     lda tmp+6
        sta proflast
        lda tmp+5
        sta proflast+1
        lda tmp+7
        sta proff
        rts
        .endif
