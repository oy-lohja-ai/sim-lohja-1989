; Kuva 3 (kuopan osa, kehykset 1200-1799): valmis Lohjantähti sinisellä hetkellä. Ladataan pankkiin 2 kuvan 2
; aikana (kp3: ruutu, värit $8800, tämä koodi ja data; kp3b: bittikartta $a3c0). Data torni.py: pimeä kuva näkyy,
; valaistun kuvan ero XOR-ajoina ryhmittäin (tornin kerrokset, kerrostalon ikkunat, torin heijastus).
;
; kp3_go (pääsäie latauksen jälkeen): työ jobv[2]:een. job3 (IRQ:n sisäkkäinen työ, joka kehys): ryhmän tila
; sen välkekuviosta (alkuajasta kulunut aika), ja kun tila vaihtuu, ryhmän XOR-ajot näkyvään bittikarttaan.

        .include "kp_defs.inc"
        .include "core.inc"

BM2     = $a000 + PIC                   ; pankin 2 bittikartan kuva-alue

        .virtual zp_end
now3    .word ?
gi      .byte ?
gp      .word ?                         ; XOR-ajon osoitin
gd      .word ?                         ; kohde
gcnt    .byte ?
pl      .word ?                         ; kulunut aika kuviossa
ng      .byte ?                         ; ryhmän kello
ntog    .byte ?                         ; vaihtoja tällä kehyksellä (kuoppa4:n täyte)
zp3_end
        .cerror zp3_end > $a0, "nollasivu (kuoppa4: KP_ZP $a0)"
        .endv

        * = $8ad0
kp3_go
        sei
        lda #<job3
        sta jobv_lo+2
        lda #>job3
        sta jobv_hi+2
        cli
        rts

; kuoppa-kyltit (osalevy P=kuoppa-kyltit, KP_ALKU): kuva 3 ilman kuvia 1-2. Ydin (kp0c), kp3 ja kp4 ladattu.
; kp3_init: nollasivu, kuva 3 näkyvään tilaan (kp_init ei käy: se piirtää kuvaa 1), ruudun reunarivit mustiksi ja
; ryhmien valot osan kehyksen 0 tilaan ennen kuvaa (muuten ensimmäinen työ sytyttää koko tornin kerralla).
kp3_init
        ldx #ZP0
        lda #0
-       sta $00,x
        inx
        cpx #$c0
        bne -
        ldx #PICS-1
-       sta SCR2,x
        sta SCR2+PICS+SCR_N,x
        sta SCR2+PICS+SCR_N+40,x
        dex
        bpl -
        lda #2                          ; ytimen IRQ: ei leikkauksia eikä puskurin vaihtoa, työ jobv[2]
        sta shot
        jsr kp3_go
        lda #0
        tax
        jmp job3_at

; kp3_show (runko #S_SHOW): osan kehys 0 ennen kelloa, värimuisti ja VIC kuvaan 3 (pankki 2). Jatkuvassa saumassa
; (part-kuoppa-kyltit.json) kp3_col edellisen osan aikana (taulu2b on hires-bittikartta: värimuisti ei näy) ja kp3_vic
; kellon vaihdon jälkeen, joten kehys 0 on kuva eikä musta
kp3_show
        jsr kp3_col
kp3_vic
        lda #1
        sta $dd00
        lda #$18                        ; ruutu +$0400, bittikartta +$2000 pankissa
        sta $d018
        sta $d016
        lda #0                          ; reuna on rungon (musta)
        sta $d021
        sta $d015
        lda #$3b
        sta $d011
        rts

kp3_col
        ldx #0
        txa
-       sta $d800,x
        sta $d900,x
        sta $da00,x
        sta $dae8,x
        inx
        bne -
        ldx #<COL3
        ldy #>COL3
        jmp col_copy

; kp_df: A/X = osan kehys kuopan kellolle: DFRAME, kerrontataulun 2c jälkeen DFRAME - KP_TAUKO (kp_jatka)
kp_df
        sec
        lda DFRAME
        sbc tauko
        pha
        lda DFRAME+1
        sbc tauko+1
        tax
        pla
        rts
tauko   .word 0

; kp_tauko (kuoppa-kyltit, ennen kerrontataulun 2c taulu_go:ta): spritejen rekisterit talteen ja
; spritet pois; taulu ottaa VIC:n (pankki 3) ja IRQ:n. Kuopan muisti (pankki 2, ydin, kyltit) ja nollasivu ($30-$bf)
; säilyvät taulun ajan (taulu: $c000-$ff3f, nollasivu $f0-).
kp_tauko
        ldx #$2e
-       lda $d000,x
        sta sprreg,x
        dex
        bpl -
        lda #0
        sta $d015
        rts

; kp_jatka (taulun jälkeen): kuopan kello jatkaa siitä, mihin se taulun alussa jäi (tauko = KP_TAUKO), VIC kuvaan 3,
; spritejen rekisterit takaisin ja ytimen IRQ kuten alussa (kp3_start: ensimmäinen työ heti).
kp_jatka
        lda #<KP_TAUKO
        sta tauko
        lda #>KP_TAUKO
        sta tauko+1
        jsr kp3_vic
        ldx #$2e
-       cpx #$11                        ; $d011-$d014 ja $d019-$d01a ovat IRQ:n ja kp3_vicin
        bcc +
        cpx #$15
        bcc _n
        cpx #$19
        bcc +
        cpx #$1b
        bcc _n
+       lda sprreg,x
        sta $d000,x
_n      dex
        bpl -
        jmp kp3_start
sprreg  .fill $2f

; kp3_start (kellon jälkeen): ytimen IRQ riville IRQ_LINE kuten kp_go, spritet kylttimoduulille
kp3_start
        sei
        lda #0
        sta $d010
        sta $d017
        sta $d01d
        sta $d01b
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        lda #IRQ_LINE
        sta $d012
        lda #$3b
        sta $d011
        lda #$ff
        sta $d019
        lda #1
        sta $d01a
        inc busy                        ; ensimmäinen työ heti (kehys 1 eroaa kehyksestä 0), IRQ ei aloita toista
        cli
        jsr job
        dec busy
        rts

job3
        jsr kp_df
job3_at                                 ; A/X = osan kehys (kp3_init: 0)
        .if KP_ALKU                     ; kuoppa-kyltit: kuvan 3 kehys = osan kehys + KP_ALKU - SHOT3
        clc
        adc #<(KP_ALKU - SHOT3)
        sta now3
        txa
        adc #>(KP_ALKU - SHOT3)
        .else
        sec                             ; kuvan 3 kehys
        sbc #<SHOT3_O
        sta now3
        txa
        sbc #>SHOT3_O
        bcs +
        lda #$80                        ; leikkaus on kehyksellä cue - 2: ennen kuvan alkua kaikki pimeinä (ilman
+                                       ; tätä negatiivinen aika luettaisiin isoksi ja koko torni välähtäisi valaistuna)
        .endif
        sta now3+1
        bmi +
        lda now3                        ; kuvan kehyksestä T_INC: inkrementaalinen polku (job3i)
        cmp #<T_INC
        lda now3+1
        sbc #>T_INC
        bcs job3i
+
        ldx #0                          ; kerrokset (isot ryhmät) ensin: niiden XOR valmis ennen kuin säde ehtii torniin
_g      stx gi
        bit now3+1
        bmi _off
        lda now3                        ; ryhmän kello (kehys - vaihe) / 2: vaihe 1 vaihtaa parittomilla kehyksillä,
        sec                             ; joten alussa jokin muuttuu joka kehys (torni.py FIRST_N)
        sbc GR_PH,x
        sta ng
        lda now3+1
        sbc #0
        bcc _off
        lsr a
        ror ng
        lda ng                          ; kulunut = kello - GR_T (ennen alkua: pois)
        sec
        sbc GR_T,x
        bcc _off
        sta pl                          ; kuvio: (kesto/2, tila) pareittain, kesto 0 = loppuun asti
        ldy GR_P,x
        lda pat_lo,y
        sta gp
        lda pat_hi,y
        sta gp+1
        ldy #0
-       lda (gp),y
        beq _last
        cmp pl
        beq +
        bcs _last                       ; tämä vaihe kesken
+       lda pl
        sec
        sbc (gp),y
        sta pl
        iny
        iny
        jmp -
_last   iny
        lda (gp),y
        jmp _set
_off    lda #0
_set    ldx gi
        cmp gstate,x
        beq _next
        sta gstate,x
        jsr toggle
_next   ldx gi
        inx
        cpx #NGRP
        bne _g
        rts

; job3i (kuvan kehyksestä T_INC, torni.py; kuoppa4:n täyte 1500-): sama tila kuin job3:ssa, mutta ryhmän kuvion
; kohta (gidx) ja sen alun aika (gacc, 16 b; alkutila kehykselle T_INC torni.py:stä) muistetaan, joten kehys ei käy
; kuvioita alusta (heijastuksen kuvio on 90 vaihetta). Työ valmistuu ennen kuin säde ehtii ikkunoihin, joten
; kuoppa4:n täytteen valonvaihto näkyy samalla kehyksellä. Valmis kuvio (lopputila saavutettu, gdone) ohitetaan:
; sen tila muuttuu enää kuoppa4:ssä (täyte ja pimennys vaihtavat ovr:n, gstaten ja XOR:n itse), joten työ kevenee
; kuvan edetessä (laskeutumisen kopio ja seuraavan kehyksen työ mahtuvat kehykseen).
job3i   ldx #0
_g      stx gi
        lda gdone,x
        bne _nx
        lda now3                        ; kello (kehys - vaihe) / 2, 9 bittiä
        sec
        sbc GR_PH,x
        sta ng
        lda now3+1
        sbc #0
        bcc _off                        ; kuvan alussa ennen ryhmän vaihetta
        lsr a
        ror ng
        sta pl+1
        lda ng                          ; kuviossa kulunut - nykyisen vaiheen alku
        sec
        sbc GR_T,x
        sta pl
        lda pl+1
        sbc #0
        bcc _off                        ; ei alkanut
        sta pl+1
        lda pl
        sec
        sbc gacc_lo,x
        sta pl
        lda pl+1
        sbc gacc_hi,x
        sta pl+1
        ldy GR_P,x
        lda pat_lo,y
        sta gp
        lda pat_hi,y
        sta gp+1
        ldy gidx,x
-       lda (gp),y                      ; kesto
        beq _end
        sta gd
        lda pl
        sec
        sbc gd
        sta gd+1
        lda pl+1
        sbc #0
        bcc _fin                        ; tämä vaihe kesken
        sta pl+1
        lda gd+1
        sta pl
        lda gacc_lo,x
        clc
        adc gd
        sta gacc_lo,x
        bcc +
        inc gacc_hi,x
+       iny
        iny
        jmp -
_end    inc gdone,x                     ; lopputila: kuvio valmis
_fin    tya
        sta gidx,x
        iny
        lda (gp),y
        jmp _set
_off    lda #0
_set    eor ovr,x                       ; kuoppa4:n täyte: ikkunan valo pysyvästi päinvastoin
        cmp gstate,x
        beq _nx
        sta gstate,x
        jsr toggle
_nx     ldx gi
        inx
        cpx #NGRP
        bne _g
        rts

; toggle: ryhmän X XOR-ajot näkyvään bittikarttaan (pankki 2)
toggle
        inc ntog
        lda GR_LO,x
        sta gp
        lda GR_HI,x
        sta gp+1
_run    ldy #2
        lda (gp),y
        beq _done
        sta gcnt
        ldy #0
        lda (gp),y
        clc
        adc #<BM2
        sta gd
        iny
        lda (gp),y
        adc #>BM2
        sta gd+1
        lda gp                          ; arvot alkavat +3
        clc
        adc #3
        sta gp
        bcc +
        inc gp+1
+       ldy #0
-       lda (gd),y
        eor (gp),y
        sta (gd),y
        iny
        cpy gcnt
        bne -
        tya
        clc
        adc gp
        sta gp
        bcc _run
        inc gp+1
        jmp _run
_done   rts

; välkekuviot pat_* (kesto kehyksinä / 2, tila) ja job3i:n alkutila: torni.py -> k3data.asm
        .include "k3data.asm"
gstate  .fill NGRP
gdone   .fill NGRP                      ; job3i: kuvio valmis, ohitetaan
ovr     .fill NGRP                      ; job3i: tila päinvastoin (kuoppa4 kp4_flip)
kp3_end
        .cerror kp3_end > $a000, "kuvan 3 koodi osuu bittikarttaan (rivit 0-2: kuoppa4:n letterbox)"
