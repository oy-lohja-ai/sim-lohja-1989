; Särmien XOR-merkit merkkipuskuriin (Model.mark_edge). Täyttö: alue.asm.
;
; Merkkipuskuri E on bittikartan muotoinen: rivi r, sarake c -> EBUF + (r >> 3) * 256 + c * 8 + (r & 7).
; Merkki: ptr = sivu(r) : c * 8, Y = r & 7, rivit r ja r + 1 vierekkäisinä tavuina (paitsi r & 7 = 7).
; Särmä kulkee pikseleittäin x:n mukaan; loiva särmä (|kaltevuus| < 1 riviä / px) kerää saman rivin pikselit
; tavuun ja kirjoittaa kerran, jyrkkä kirjoittaa joka pikselin. Muunnelmat: loiva/jyrkkä x ylös/alas x
; pikselin paikka tavussa (0..3), jolloin maskit ovat vakioita.

; ---------------------------------------------------------------- yksi särmä
mark                            ; xa ya xb yb, de do; sotkee A X Y
        lda xb
        sec
        sbc xa
        bne +
        rts
+       bcs _ord
        eor #$ff                ; C = 0: dx = xa - xb, päät vaihtoon
        adc #1
        ldx xa
        ldy xb
        stx xb
        sty xa
        ldx ya
        ldy yb
        stx yb
        sty ya
_ord    sta mdx
        lda xa
        and #$fc
        asl a
        sta ptr                 ; sarake * 8
        lda yb
        sec
        sbc ya
        ldx mdx
        cpx #1
        bne _gen
        cmp #$80                ; yksi pikseli: rivi ya + (dy >> 1)
        ror a
        clc
        adc ya
        tax
        lda ephi,x
        sta ptr+1
        txa
        and #7
        tay
        lda xa
        and #3
        tax
        lda maskt,x
        jmp flush
_gen    cmp #0
        bne +
        jmp hspan
+       cmp #1                  ; |dy| = 1, 2: segmenttien pituudet taulusta (loiva, dx >= 2)
        bne +
        ldy kc1d,x
        lda #$ff
        sta mk+1
        lda #1
        jmp dk
+       cmp #$ff
        bne +
        ldy kc1u,x
        lda #$ff
        sta mk+1
        jmp dk
+       cmp #2
        bne +
        cpx #3
        bcc +
        lda kc2d1,x
        sta mk+1
        ldy kc2d0,x
        lda #1
        jmp dk
+       cmp #$fe
        bne +
        cpx #3
        bcc +
        lda kc2u1,x
        sta mk+1
        ldy kc2u0,x
        lda #$ff
        jmp dk
+       ldy #0                  ; mdir: 0 alas (dy >= 0), 8 ylös
        cmp #$80
        bcc +
        eor #$ff
        adc #0                  ; C = 1: -dy
        ldy #8
+       sty mdir
        sta tmp                 ; |dy| = s
        cmp #3                  ; loiva ja |dy| = 3: kaltevuus taulusta
        bne _mul
        cmp mdx
        bcs _mul
        ldy mdx
        lda slt3,y
        sta slo
        lda #0
        sta shi
        jmp _hs
_mul    #SETMUL                 ; |kaltevuus| = s * RQ[dx] >> 8, s * u = s (u - 128) + (s << 7)
        lda tmp
        lsr a
        sta tmp+1
        lda #0
        ror a
        sta tmp+2               ; s << 7
        ldy rq_l,x
        #MULY
        tay
        lda pl
        clc
        adc tmp+2
        tya
        adc tmp+1
        sta tmp+3               ; (s * RQlo) >> 8
        ldx mdx
        ldy rq_h,x
        #MULY
        tay
        lda pl
        clc
        adc tmp+2
        sta slo
        tya
        adc tmp+1
        sta shi
        lda slo
        clc
        adc tmp+3
        sta slo
        lda shi
        adc #0
        sta shi
_hs     lsr a                   ; puolikas: s >> 1 alas, (s + 1) >> 1 ylös
        sta tmp+1
        lda slo
        ror a
        ldy mdir
        bne _up
        clc                     ; acc = ya * 256 + 127 + (s >> 1)
        adc #127
        sta f
        lda ya
        adc tmp+1
        jmp _row
_up     sta tmp
        lda slo
        lsr a                   ; s & 1 -> C: (s + 1) >> 1 = (s >> 1) + (s & 1)
        lda tmp
        adc #0
        sta tmp
        lda tmp+1
        adc #0
        sta tmp+1
        lda #127                ; acc = ya * 256 + 127 - ((s + 1) >> 1)
        sec
        sbc tmp
        sta f
        lda ya
        sbc tmp+1
_row    sta row
        ldx shi
        bne _st
        lda xa                  ; loiva: rivisegmentit
        sta cx
        ldx mdx
        lda mdir
        bne +
        jmp frd
+       jmp fru
_st     tax                     ; jyrkkä: pikseleittäin, muunnelma ylös * 4 + x & 3
        lda ephi,x
        sta ptr+1
        lda xa
        and #3
        ldx mdir
        beq +
        ora #4
+       tax
        lda mvec_l,x
        sta jv
        lda mvec_h,x
        sta jv+1
        lda row
        and #7
        tay
        ldx mdx
        jmp (jv)


dk                              ; |dy| = 1, 2: Y = 1. rivin pikselit, mk+1 = 2. rivin ($ff = loput), A = rivin askel
        sta tmp+2
        sty cn
        lda mk+1
        sta tmp+3
        lda mdx
        sta nrem
        lda ya
        sta row
        lda xa
        sta cx
_r      jsr span
        sec                     ; jäljellä
        lda nrem
        sbc cn
        beq _x
        sta nrem
        clc
        lda cx
        adc cn
        sta cx
        clc
        lda row
        adc tmp+2
        sta row
        lda tmp+3               ; seuraava segmentti: taulun pituus tai loput
        ldx #$ff
        stx tmp+3
        cmp nrem
        bcc +
        lda nrem
+       sta cn
        jmp _r
_x      rts

hspan                           ; vaakasuora särmä (dy = 0): rivin ya pikselit xa..xb-1 kerralla
        lda ya
        sta row
        lda xa
        sta cx
        lda mdx
        sta cn
        jmp span

; loiva särmä rivisegmentteinä: segmentin pituus askeltamalla f:ää (ylivuoto/lainaus = seuraava rivi),
; segmentti kerralla (span). X = jäljellä olevat pikselit, cx = segmentin alku.
FRUN    .macro up
_r      stx nrem
        dex
        beq _all
        lda f
        .if \up
        sec
        .else
        clc
        .endif
_s      .if \up
        sbc slo
        bcc _brk
        .else
        adc slo
        bcs _brk
        .endif
        dex
        bne _s
_all    lda nrem
        sta cn
        jmp span
_brk    sta f
        txa                     ; segmentti = nrem - X
        eor #$ff
        sec
        adc nrem
        sta cn
        jsr span
        clc
        lda cx
        adc cn
        sta cx
        .if \up
        dec row
        .else
        inc row
        .endif
        jmp _r
        .endm

frd     #FRUN 0
fru     #FRUN 1

span                            ; rivi row, pikselit cx .. cx + cn - 1 (cn >= 1); X säilyy
        stx spx
        ldy row
        lda ephi,y
        sta ptr+1
        sta ptr2+1
        tya
        and #7
        sta ptr
        cmp #7
        beq _w
        adc #1                  ; C = 0
        sta ptr2
        bne _p
_w      lda #0
        sta ptr2
        inc ptr2+1
_p      tya                     ; kuviot: rivi pa, seuraava pb
        lsr a
        lda de
        ldy do
        bcc +
        lda do
        ldy de
+       sta pa
        sty pb
        ldx cx                  ; maskit ja sarakkeet x-tauluista
        lda xlm,x
        sta mk
        ldy xc8,x
        txa
        clc
        adc cn
        tax                     ; x1 + 1
        lda xrm-1,x
        sta mk+1
        lda xc8-1,x
        sta nb                  ; viimeisen tavun sarake * 8
TOGM    .macro                  ; A = maski: rivi pa, seuraava pb
        sta mk
        and pa
        eor (ptr),y
        sta (ptr),y
        lda mk
        and pb
        eor (ptr2),y
        sta (ptr2),y
        .endm
        cpy nb
        beq _1
        lda mk
        #TOGM
        tya
        clc
        adc #8
        tay
        cpy nb
        beq _l
_f      lda pa                  ; täysi tavu
        eor (ptr),y
        sta (ptr),y
        lda pb
        eor (ptr2),y
        sta (ptr2),y
        tya
        clc
        adc #8
        tay
        cpy nb
        bne _f
_l      lda mk+1
        #TOGM
        ldx spx
        rts
_1      lda mk
        and mk+1
        #TOGM
        ldx spx
        rts

; jyrkät: ylös * 4 + j
mvec_l  .byte <sd0, <sd1, <sd2, <sd3, <su0, <su1, <su2, <su3
mvec_h  .byte >sd0, >sd1, >sd2, >sd3, >su0, >su1, >su2, >su3
lmask   .byte $ff, $3f, $0f, $03      ; pikselit j..3 (myös vaakaviiva)
rmask   .byte $c0, $f0, $fc, $ff      ; pikselit 0..j
LMK     = [$ff, $3f, $0f, $03]
RMK     = [$c0, $f0, $fc, $ff]
PMK     = [$c0, $30, $0c, $03]

FLE     .macro                  ; A = maski, Y parillinen: rivi kuviolla de, seuraava do (sama sivu)
        sta mk
        and de
        eor (ptr),y
        sta (ptr),y
        iny
        lda mk
        and do
        eor (ptr),y
        sta (ptr),y
        dey
        .endm
FLO     .macro                  ; Y pariton: rivi do, seuraava de (Y = 7: seuraava sivu)
        sta mk
        and do
        eor (ptr),y
        sta (ptr),y
        lda mk
        and de
        cpy #7
        beq _w
        iny
        eor (ptr),y
        sta (ptr),y
        dey
        jmp _x
_w      inc ptr+1
        ldy #0
        eor (ptr),y
        sta (ptr),y
        dec ptr+1
        ldy #7
_x
        .endm
FL      .macro odd
        .if \odd
        #FLO
        .else
        #FLE
        .endif
        .endm
NEXTROW .macro up, odd          ; rivi seuraavaksi (alas) tai edelliseksi (ylös)
        .if \up
        dey
        .if !\odd
        bpl +
        ldy #7
        dec ptr+1
+
        .endif
        .else
        iny
        .if \odd
        cpy #8
        bne +
        ldy #0
        inc ptr+1
+
        .endif
        .endif
        .endm

STEEP   .macro j, next, up      ; jyrkkä: jokainen pikseli omalla rivillään
        tya
        lsr a
        lda #PMK[\j]
        bcs _o
        #FLE
        jmp _s
_o      #FLO
_s      dex
        bne +
        rts
+       .if \up                ; rivi Y +/- (shi + murto-osan siirto), sivu ptr+1 mukana
        sec
        lda f
        sbc slo
        sta f
        tya
        sbc shi
        bpl _y
_u      clc
        adc #8
        dec ptr+1
        cmp #0
        bmi _u
        .else
        clc
        lda f
        adc slo
        sta f
        tya
        adc shi
        cmp #8
        bcc _y
_d      sbc #8
        inc ptr+1
        cmp #8
        bcs _d
        .endif
_y      tay
        .if \j == 3
        lda ptr
        clc
        adc #8
        sta ptr
        .endif
        jmp \next
        .endm

sd0     #STEEP 0, sd1, 0
sd1     #STEEP 1, sd2, 0
sd2     #STEEP 2, sd3, 0
sd3     #STEEP 3, sd0, 0
su0     #STEEP 0, su1, 1
su1     #STEEP 1, su2, 1
su2     #STEEP 2, su3, 1
su3     #STEEP 3, su0, 1

flush                           ; A = pikselimaski, rivi (ptr, Y): rivi parillisuutensa kuviolla, seuraava toisella
        sta mk
        tya
        lsr a
        bcs _o
        lda mk
        and de
        eor (ptr),y
        sta (ptr),y
        iny
        lda mk
        and do
        eor (ptr),y
        sta (ptr),y
        dey
        rts
_o      lda mk
        and do
        eor (ptr),y
        sta (ptr),y
        lda mk
        and de
        cpy #7
        beq _w
        iny
        eor (ptr),y
        sta (ptr),y
        dey
        rts
_w      inc ptr+1
        ldy #0
        eor (ptr),y
        sta (ptr),y
        dec ptr+1
        ldy #7
        rts

mulsu                           ; kerroin s asetettu (SETMUL) ja tallessa tmp:ssä, Y = u (etumerkitön) -> pl/ph = s * u
        #MULY                   ; s (u - 128)
        sta ph
        lda tmp                 ; + s * 128
        cmp #$80
        ror a
        sta tmp+1
        lda #0
        ror a
        clc
        adc pl
        sta pl
        lda tmp+1
        adc ph
        sta ph
        rts
