; Linecrunch-pystyvieritys MC-bittikartalla ja $D021 rivi riviltä: yhteinen moottori (Hillnerin kamera-ajo,
; koti). Ajoituskriittiset kohdat (irq_top, sky_loop, cr_edge) on laskettu syklilleen.
;
; Ikkuna 320x144 riveillä T_LINE..B_LINE-1. Rivistä SEQ0 + 1 alkaen c riviä crunchataan, sitten tyhjiä rivejä
; niin, että ensimmäinen badline on rivillä T_LINE - f: kuvan pikseli p = 8c + f asettelun alusta. Asettelut
; (ROWS_BANK merkkiriviä) vuorottelevat VIC-pankeissa 2 ($8000 ruutu, $a000 bittikartta) ja 3 ($c000, $e000).
;
; Sisällyttäjä määrittelee:
;   nollasivu: ra rx ry plyt cc ff lb seqn lcur d11show d11hide dd00v bank bl7m d21end pre_k pre_bank
;              rowi rown dbmp dscr dcol tmp ltmp
;   seq (32 tavua, ei sivurajan yli), d21line (256 tavua, rivinumerolla), COLSTAGE (1000 tavua)
;   row_lo/row_hi (kuvan merkkirivin 400 tavun tietue: bittikartta 320, ruutu 40, väri 40), lay_row
;   CR_TOPCLR: absoluuttinen osoite, johon irq_top kirjoittaa 0 (6 sykliä ajoitukseen; Hillner: cr_topclr)
;   cr_top_tail: irq_top jatkuu tästä taivassilmukan jälkeen (rekisterit ra/rx/ry:ssä, $d019 kuittaamatta)
;   DEBUG: 1 = IRQ-vaiheet reunaväreinä
;   CR_LATE (valinnainen): 1 = d21late (256 t, sivulla, rivinumerolla), 1 rivillä, jolla spritet 3-4 näkyvät;
;              sisällyttäjä sijoittaa .cr_late_edge-makron labeliin cr_late ja asettaa CIA1:n ajastimen B latchiksi
;              62 ($dc06 = 62, $dc07 = 0) ennen ensimmäistä kehystä (irq_top käynnistää sen rivin tahtiin)
;   cr_row (valinnainen): build_layoutin rivikopio (tmp = tietue, rowi = kuvan rivi); oletus copy_row
;   CR_D020 (valinnainen): 1 = taivassilmukka kirjoittaa saman värin myös reunaan ($D020) heti $D021:n perään
;              (reunaton vaikutelma taivasriveillä; sisällyttäjä nollaa reunan ikkunan alla)
;   CR_IRQ_ONLY (valinnainen): 1 = vain IRQ-osat (irq_top, sky_loop, cr_edge), ei sekvensseriä eikä asettelun
;              rakennusta

        .weak
cr_row  = copy_row              ; sisällyttäjä voi korvata (koti: rivit näkyvästä pankista)
        .endweak
        .weak
CR_LATE = 0
CR_D020 = 0
CR_IRQ_ONLY = 0
        .endweak

T_LINE    = 72                  ; ikkunan ensimmäinen rivi
B_LINE    = 216                 ; ensimmäinen piilotettu rivi ikkunan alla
SEQ0      = 47                  ; sekvensserin ensimmäinen rivi (crunch alkaa riviltä 48)
LINE_TOP  = 44
CMAX      = 6
ROWS_BANK = 25
BANK2_SCR = $8000
BANK2_BMP = $a000
BANK3_SCR = $c000
BANK3_BMP = $e000

; ---------------------------------------------------------------- IRQ: yläreuna (rivi 44)
; Kaksois-IRQ vakauttaa ajoituksen, sitten sekvensseri kirjoittaa $d011:n rivin alussa (sykli 4)
; jokaisella rivillä 47..lb-1 taulusta seq (crunch / tyhjä / badline), ja ikkunan yläreuna avataan
; rivillä 72 (ECM pois). Tasaus: seqloop ei saa ylittää sivua (haarautumisen sykli).
        .align 128
irq_top
        sta ra
        stx rx
        sty ry
        lda $d012               ; vain rivillä 44 (ei ylimääräisiä)
        cmp #LINE_TOP
        bne irq_spur
        lda #<irq_top2
        sta $fffe
        lda #>irq_top2
        sta $ffff
        inc $d012
        asl $d019
        tsx
        cli
        .fill 16, $ea
        sei                     ; toinen IRQ ei tullut (irq_top myöhässä): ei keskeytyksiä irq_top2:n sisään,
                                ; muuten myöhässä tuleva IRQ ajaisi txs:n roskalla (pino, JAM)
irq_top2
        txs
        ldx #8
-       dex
        bne -
        bit $00
        lda $d012
        cmp $d012
        beq +
+       asl $d019               ; vakaa tästä
        lda dd00v
        sta $dd00
        lda #0                  ; 6 sykliä + 12 rivin 72-73 taustaväreille (sekvensserin ajoitus)
        sta CR_TOPCLR
        .if CR_LATE             ; 22 sykliä ja 8 tavua kuten alla: CIA1:n ajastin B (latch 62, jakso 63 = rivi)
        jsr dly40 + 12          ; ladataan ja käynnistetään joka kehys samassa syklissä, joten sen arvo kertoo
        lda #$11                ; rivin syklin (cr_late_edge); DEBUG-reunaväri jää tästä pois
        sta $dc0f
        .else
        ldx #TOPDLY
-       dex
        bne -
        .if DEBUG
        lda #2
        sta $d020
        .else
        nop
        nop
        nop
        .endif
        .endif
        lda d21line + T_LINE    ; rivin 72 taustaväri jo rivillä 46 (laiton tila, musta)
        sta $d021
        ldy d21line + T_LINE + 1
        ldx #0
seqloop lda seq,x               ; 63 sykliä per kierros (Y = rivin 73 taustaväri)
        sta $d011
        jsr dly41
        bit $00
        bit $00
        inx
        cpx seqn
        bne seqloop
        lda d11show
        ldx #T_LINE
-       cpx $d012
        bne -
        sta $d011               ; rivi 72 (W0 = kyselyn luku + 6)
s72jmp  jmp s72a                ; cr_seq valitsee: s72b (rivi 73 badline), s72c (rivi 74 badline)
s72a    inx                     ; rivi 73: arvo valmiina Y:ssä (rivi 72 voi olla badline)
-       cpx $d012
        bne -
        sty $d021
        .if CR_D020             ; reuna ikkunan ylimmistä riveistä 1-3 rivin viiveellä (ajastetut polut ennallaan)
        sty $d020
        .endif
        ldx #T_LINE + 2
        bne s72d
s72b    lda d21line + T_LINE + 2
        jsr dly40
        sty $d021               ; rivin 73 arvo rivin 72 oikeassa reunassa (W0 + 51)
        ldx #T_LINE + 2
-       cpx $d012
        bne -
        sta $d021               ; rivi 74 badlinen jälkeen
        .if CR_D020
        sta $d020
        .endif
        ldx #T_LINE + 3
        bne s72d
s72c    inx                     ; rivi 73 alussa, rivi 74 (badline) rivin 73 reunassa, rivi 75 heti
-       cpx $d012
        bne -
        sty $d021               ; W0
        lda d21line + T_LINE + 2
        ldy d21line + T_LINE + 3
        jsr dly39
        sta $d021               ; W0 + 51
        ldx #T_LINE + 3
-       cpx $d012
        bne -
        sty $d021
        .if CR_D020
        sty $d020
        .endif
        ldx #T_LINE + 4
s72d    .if DEBUG
        lda #0
        sta $d020
        .endif
        cpx d21end
        bcs +
        jsr sky_loop
+       jmp cr_top_tail
irq_spur asl $d019
        lda ra
        ldx rx
        ldy ry
        rti
TOPDLY = 3
        .cerror (>seqloop) != (>(seqloop + 17)), "seqloop ylittää sivun"
dly41   .fill 13, $ea           ; jsr + 29 + rts = 41 sykliä
        bit $00
        rts
dly40   .fill 14, $ea           ; jsr + 28 + rts = 40 sykliä
        rts
dly39   .fill 12, $ea           ; jsr + 27 + rts = 39 sykliä
        bit $00
        rts
D20     = CR_D020 ? 4 : 0       ; sta $d020 W0:n perässä: oikean reunan kirjoitukseen 4 sykliä vähemmän viivettä
        .if CR_D020
dly35   .fill 10, $ea           ; jsr + 23 + rts
        bit $00
        rts
        .endif
        .if CR_LATE
dly32   .fill 10, $ea           ; jsr + 20 + rts
        rts
        .fill 8, 0              ; täyte: osoitteet eivät siirry
        .if CR_D020             ; reunan kirjoitus W0:n perässä: viiveet 4 sykliä lyhyempiä
dly28   .fill 8, $ea            ; jsr + 16 + rts
        rts
dly21   .fill 3, $ea            ; jsr + 9 + rts
        bit $00
        rts
        .endif
        .endif

; Taivassilmukka: $D021 riveille X..d21end taulusta d21line (rivinumerolla), kirjoitus rivin alussa
; (kysely + 6 = syklit 7-13, näyttö alkaa syklissä 16). Taivasrivien spritet ovat 0-2, joiden DMA on edellisen
; rivin lopussa (syklit 55-63). Badline-rivillä CPU seisoo syklistä 12, joten:
;   - badline-rivin arvo kirjoitetaan edellisen rivin oikeassa reunassa (syklit 57-64, viive dly39)
;   - badlinen jälkeisen rivin arvo on valmiina Y:ssä: kysely + kirjoitus heti, kun CPU vapautuu.
; bl7m = (lb - 1) & 7: X & 7 = bl7m, kun rivi X + 1 on badline.
sky_loop
_top    txa
        eor bl7m
        and #7
        beq _pb
        lda d21line,x           ; tavallinen rivi
-       cpx $d012
        bne -
        sta $d021
        .if CR_D020
        sta $d020
        .endif
        inx
        cpx d21end
        bcc _top
        rts
_pb     lda d21line,x           ; rivi X, badline X + 1 ja rivi X + 2
-       cpx $d012
        bne -
        sta $d021               ; W0
        .if CR_D020
        sta $d020
        .endif
        .if CR_LATE             ; sisällyttäjän d21late (sivulla, rivinumerolla): kirkon rivit (spritet 3-4 rivillä
        ldy d21late,x           ; X, Hillnerin taustarivistön talot 0-2 rivillä X + 1). Kyselyn värinä 7 sykliä
        beq _pn                 ; (mitattu ajastimella) ei mahdu väliin, jossa kirjoitus on näkymätön (sykli 57) eikä
        .if CR_D020             ; spritejen DMA vie sitä badlinen BA:n taakse: vakaa kirjoitus cr_late_edgessä
        lda d21line + 1,x
        ldy d21line + 2,x
        jsr dly21
        jmp _pw
        .else
        jmp cr_late
        .fill 9, 0              ; täyte: sama koko kuin CR_D020:n viivepolku, osoitteet eivät siirry
        .endif
_pn     .cerror (>_pn) != (>(_pn - 12)), "sky_loop: beq ylittää sivun"
        lda d21line + 1,x       ; tavallinen: 4 + 3 + 8 + 32 = 47 kuten ilman d21latea
        ldy d21line + 2,x
        .if CR_D020
        jsr dly28
        .else
        jsr dly32
        .endif
        .else
        lda d21line + 1,x
        ldy d21line + 2,x
        .if CR_D020
        jsr dly35
        .else
        jsr dly39
        .endif
        .endif
_pw     sta $d021               ; W0 + 51: rivin X oikea reuna
        .if CR_D020
        sta $d020
        .endif
_pw2    inx                     ; (cr_late_edge palaa tähän)
        inx
-       cpx $d012
        bne -
        sty $d021
        .if CR_D020
        sty $d020
        .endif
        inx
        cpx d21end
        bcc _top
        rts

cr_skyret = sky_loop._pw2

; Kirkon rivin X oikean reunan kirjoitus (CR_LATE, rivi X + 1 badline; sky_loopista jmp cr_late, A ja Y vapaat,
; X = rivi). Kysely kirjoitti rivin X värin syklissä W0, jonka värinä on 7 sykliä (ajastimen arvot W0 + 17:ssä
; 12-18, kaukana ylivuodosta 0/62). Liukuhyppy (lda #$a9 -ketju, 8 - o sykliä, o = CR_TK - arvo = 0..6) tasaa
; sen, joten rivin X + 1 värin kirjoitus on aina syklissä 57: rivin X näkyvä osa on päättynyt (55-56 = oikean
; reunan 7-16 pikseliä edellisen rivin väriä) eikä luku osu badlinen BA:han. Jos rivin X + 1 sprite 0 pysäyttää
; CPU:n syklistä 55, kirjoitus tulee 2 sykliä DMA:n jälkeen ennen badlinea. and #7: odottamaton arvo ei hyppää
; rampin ohi (o = 7: heti rampin perään).
CR_TK   = 18
cr_late_edge .macro
        lda #CR_TK
        sec
        sbc $dc06
        and #7
        sta _br + 1
_br     bpl _sl                 ; 3 sykliä (ei sivurajaa)
_sl     .byte $a9, $a9, $a9, $a9, $a9, $24, $ea
        .cerror (>_br) != (>(_sl + 7)), "cr_late_edge: liukurampin haara ylittää sivun"
        lda d21line + 1,x
        ldy d21line + 2,x
        sta $d021               ; sykli 57
        jmp cr_skyret
        .endm

; ---------------------------------------------------------------- alareuna
; Ikkunan alareuna: ECM päälle rivin 215 oikeassa reunassa (syklit 58-64), jolloin rivin 216
; mahdollinen badline (f = 0) ja spritejen 3-7 DMA rivin 216 alussa eivät osu kirjoitukseen.
; Jos rivi 215 on itse badline (f = 1), CPU pysähtyy syklistä 12 sykliin 55 ja kirjoitus osuu
; sykleihin 58-66. Mikään sprite ei saa jatkua rivin 215 yli. A = $d011 (piilotettu), Y = f. Kutsutaan
; IRQ:sta, joka alkaa ennen riviä B_LINE - 1 (A, X, Y muuttuvat).
cr_edge .macro
        ldx #B_LINE - 1
-       cpx $d012
        bne -
        cpy #1
        beq _f1
        ldy #8                  ; 47 sykliä (kirjoitus syklissä 57-63; 44:llä 54-60 leikkaisi rivin 215
-       dey                     ; viimeiset 8 hires-px, mitattu koti-protossa f = 2 ja 3)
        bne -
        bit $00
        bit $00
        sta $d011
        jmp _edge
_f1     nop
        sta $d011
_edge
        .endm

        .if !CR_IRQ_ONLY
; ---------------------------------------------------------------- sekvensseri
; X = p asettelun sisällä (0..CMAX*8+7) -> c, f, lb, sekvensseritaulu seq, $d011-arvot ja rivin 72 haara.
; Pankki (bank: 0 = pankki 2, 1 = pankki 3) -> dd00v.
cr_seq
        stx plyt
        txa
        lsr a
        lsr a
        lsr a
        sta cc
        txa
        and #7
        sta ff
        lda #T_LINE
        sec
        sbc ff
        sta lb
        sec
        sbc #SEQ0
        sta seqn
        lda lb
        and #7
        ora #$38
        sta d11show
        ora #$40
        sta d11hide
        lda bank                ; pankki 2: %01, pankki 3: %00
        eor #1
        sta dd00v
; sekvensseritaulu: rivi L kirjoittaa arvon, joka on voimassa seuraavan rivin alussa
;   L < 47 + c  : L + 1  (seuraava rivi crunchataan)
;   L < lb - 1  : L + 2  (seuraava rivi tyhjä)
;   L = lb - 1  : lb     (badline)
        ldx #0
        lda #SEQ0 + 1
        sta lcur
        ldy cc
        beq _idle
_crn    lda lcur                ; rivit 47..46+c: L + 1
        and #7
        ora #$78
        sta seq,x
        inc lcur
        inx
        dey
        bne _crn
_idle   inc lcur                ; rivit 47+c..lb-2: L + 2
        lda lb
        sec
        sbc #SEQ0 + 1
        sbc cc
        tay
        beq _bl
_idl    lda lcur
        and #7
        ora #$78
        sta seq,x
        inc lcur
        inx
        dey
        bne _idl
_bl     lda lb                  ; rivi lb-1: lb (badline)
        and #7
        ora #$78
        sta seq,x
        lda lb
        sec
        sbc #1
        and #7
        sta bl7m
        tax                     ; alku: rivi 73 badline (bl7m = 0), rivi 74 badline (bl7m = 1), muuten s72a
        lda s72lo,x
        sta s72jmp + 1
        lda s72hi,x
        sta s72jmp + 2
        rts
s72lo   .byte <s72b, <s72c, <s72a, <s72a, <s72a, <s72a, <s72a, <s72a
s72hi   .byte >s72b, >s72c, >s72a, >s72a, >s72a, >s72a, >s72a, >s72a

; ---------------------------------------------------------------- asettelun rakennus
; pre_k: asettelu (rivit lay_row[k]..+24) pankkiin pre_bank: bittikartta ja ruutu suoraan, väri COLSTAGEen.
; Rivi kerrallaan (Hillner: savu rivien välissä): build_init, sitten rown = 1 ja build_layout._row ROWS_BANK kertaa.
build_init
        ldx pre_k               ; ensimmäinen rivi
        lda lay_row,x
        sta rowi
        lda #ROWS_BANK
        sta rown
        ldx pre_bank
        lda #0
        sta dbmp
        sta dscr
        lda bmp_hi,x
        sta dbmp+1
        lda scr_hi,x
        sta dscr+1
        lda #<COLSTAGE
        sta dcol
        lda #>COLSTAGE
        sta dcol+1
        rts
build_layout
        jsr build_init
_row    ldx rowi
        lda row_lo,x
        sta tmp
        lda row_hi,x
        sta tmp+1
        jsr cr_row
        inc rowi
        lda dbmp                ; seuraava kohde
        clc
        adc #<320
        sta dbmp
        lda dbmp+1
        adc #>320
        sta dbmp+1
        lda dscr
        clc
        adc #40
        sta dscr
        bcc +
        inc dscr+1
+       lda dcol
        clc
        adc #40
        sta dcol
        bcc +
        inc dcol+1
+       dec rown
        bne _row
        rts
bmp_hi  .byte >BANK2_BMP, >BANK3_BMP
scr_hi  .byte >BANK2_SCR, >BANK3_SCR

; 400 tavun tietue (tmp) -> bittikartta (dbmp), ruutu (dscr), väri (dcol); noin 3 900 sykliä
copy_row
        .for i := 0, i < 10, i += 1
        lda tmp
        clc
        adc #<(i * 40)
        sta _cr + i * 6 + 1
        lda tmp+1
        adc #>(i * 40)
        sta _cr + i * 6 + 2
        .next
        .for i := 0, i < 8, i += 1
        lda dbmp
        clc
        adc #<(i * 40)
        sta _cr + i * 6 + 4
        lda dbmp+1
        adc #>(i * 40)
        sta _cr + i * 6 + 5
        .next
        lda dscr
        sta _cr + 8 * 6 + 4
        lda dscr+1
        sta _cr + 8 * 6 + 5
        lda dcol
        sta _cr + 9 * 6 + 4
        lda dcol+1
        sta _cr + 9 * 6 + 5
        ldx #39
_cr
        .for i := 0, i < 10, i += 1
        lda $ffff,x
        sta $ffff,x
        .next
        dex
        bpl _cr
        rts

; X = rivi (säilyy): COLSTAGE + 40X -> $d800 + 40X, noin 500 sykliä
col_row
        stx _x + 1
        lda row40_lo,x
        sta ltmp
        lda row40_hi,x
        sta ltmp+1
        .for k := 0, k < 4, k += 1
        lda ltmp
        clc
        adc #10 * k
        sta _s0 + 6 * k + 1
        sta _s0 + 6 * k + 4
        lda ltmp+1
        adc #0
        tay
        adc #>COLSTAGE
        sta _s0 + 6 * k + 2
        tya
        adc #>$d800
        sta _s0 + 6 * k + 5
        .next
        ldx #9
_s0
        .for k := 0, k < 4, k += 1
        lda $ffff,x
        sta $ffff,x
        .next
        dex
        bpl _s0
_x      ldx #0
        rts
row40_lo .byte <(range(0, 1000, 40))
row40_hi .byte >(range(0, 1000, 40))

; koko asettelun värit (alustus)
colcopy
        ldx #0
-       jsr col_row
        inx
        cpx #ROWS_BANK
        bcc -
        rts
        .endif
