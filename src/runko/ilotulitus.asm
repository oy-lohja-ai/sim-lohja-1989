; Siirtymä kuoppa-kyltit -> spritet (logojen lento jatkuu ilotulitukseen): kylttien logot ovat lentäneet taivaalle,
; ja mustalle yötaivaalle nousee raketteja, jotka räjähtävät kuten sprite-ennätyksen ilotulitus (samat kuvat,
; korkeudet ja värit); laukaisut tihenevät ennätystä kohti.
; Työ rungon IRQ:n R_TICKissä (rivi 250, musiikin jälkeen); pääsäie lataa spritetin alkua (SPR1-SPR3).
; Muisti: ILOT $c400-$cabf VIC-pankissa 3. Sprite-ennätys jättää sivut $c4-$ca vapaiksi (build.py lentavat "varattu"),
; joten ILOT ladataan ku_cutin jälkeen. Pyörii spritetin I_STARTiin asti (ku_start ottaa rungon IRQ:n pois, spr_go
; VIC:n; it_tick lopettaa itsensä, kun VIC ei ole pankissa 3); it_end vain osalevylle. Kuva on laiton tila ECM + BMM
; (musta), joten ruutu $c400 (koodi) ei näy; spriteosoittimet $c7f8-, kuvat $c800-. Muuttujat tiedostossa (ei
; nollasivua: Krill $e0-$ef latauksen aikana). Data tools/disk/ilotulitus.py.

        .include "runko.inc"

SCR     = $c400
PTRS    = SCR + $3f8
KUVAT   = $c800
BLK0    = (KUVAT & $3fff) / 64

        * = SCR
; it_go (taulusta ku_cutin jälkeen, ILOT:n latauksen jälkeen; rungon IRQ päällä): VIC pankkiin 3 mustana, R_TICK
it_go
        ldy #0                  ; laukaisulista 1: tihenee ennätystä kohti
        beq it_alku
; it_jatko (siirtymä uusivuosi, spritet -> vuosi2026, taulusta ku_cutin jälkeen): ILOT on yhä muistissa (ennätyksen
; varatut sivut), laukaisulista 2: tiheä alku harvenee ja taivas tyhjenee ennen vuoden alkua (vuosi_go ottaa IRQ:n)
it_jatko
        ldy #L2
it_alku
        sei
        sty li
        lda #0                  ; raketit ennätyksen kokoisina (vaihto isoista ilotulitteista
        sta $d015               ; logoihin näyttäisi huonolta), laskuri kertoo määrän
        sta $d017
        sta $d01d
        sta $d01b
        sta $dd00               ; VIC-pankki 3 (lataaja on vapaana: S_CALL latausten välissä)
        sta t
        ldx #7
-       sta act,x
        dex
        bpl -
        lda #$ff                ; monivärispritet: $d025 kipinä, $d026 valkoinen kuten ennätyksessä
        sta $d01c
        lda #1
        sta $d026
        lda #$7b                ; ECM + BMM + DEN: musta, spritet näkyvät
        sta $d011
        lda #(SCR & $3fff) >> 6
        sta $d018
        ldx #7 - TSPR0          ; laskurin spritet TSPR0-7: paikka, väri ja kiinteät kuvat (numeron sarake joka kehys)
-       txa
        clc
        adc #TSPR0
        tay
        lda t_blk,x
        clc
        adc #BLK0
        sta PTRS,y
        lda #1
        sta $d027,y
        tya
        asl
        tay
        lda t_xlo,x
        sta $d000,y
        lda #TY
        sta $d001,y
        dex
        bpl -
        #TICK it_tick
        cli
        rts

; ---------------------------------------------------------------- kehys (rungon IRQ, rivi 250)
it_tick
        lda $dd00               ; kerneliosa (ennätys, VIC-pankki 1) palasi rungon IRQ:hun: ilotulitus pois, muuten se
        and #3                  ; jatkaisi ennätyksen spritet ennen ku_cutia (glue ei kutsu spr_hiljaata, joka
        beq +                   ; nollaisi R_TICKin)
        #TICK 0
        rts
+       inc t                   ; kehys 1-255 (ei kierrä: listan loppumerkki 0)
        bne +
        dec t
+       ldy li                  ; tämän kehyksen laukaisu (enintään yksi, ilotulitus.py)
        lda l_t,y
        cmp t
        bne _u
        ldx l_s,y
        lda l_xlo,y
        sta xlo,x
        lda l_xhi,y
        sta xhi,x
        lda l_seq,y
        sta ph,x
        lda l_col,y
        sta $d027,x
        lda #Y0
        sta yy,x
        lda #1
        sta act,x
        inc li
_u      lda #0
        sta en
        sta msb
        ldx #NR - 1
_s      lda act,x
        beq _n
        ldy ph,x
        lda seq,y
        bmi _off                ; $ff: yläreunan takana
        clc
        adc #BLK0
        sta PTRS,x
        inc ph,x
        txa
        asl
        tay
        lda yy,x
        sta $d001,y
        sec
        sbc #STEP
        sta yy,x
        lda xlo,x
        sta $d000,y
        lda bits,x
        ora en
        sta en
        lda xhi,x
        beq _n
        lda bits,x
        ora msb
        sta msb
        bne _n
_off    lda #0
        sta act,x
_n      dex
        bpl _s
        lda msb
        ora #TMSB
        sta $d010
        lda en
        ora #TMASK
        sta $d015
        ldy #0                  ; laskuri: N = tekstispritet + lennossa olevat raketit (laukaisusta yläreunan taakse;
        lda en                  ; lista 1 laukaisee uudelleen samassa kehyksessä, joten luku vain kasvaa)
-       lsr
        bcc +
        iny
+       cmp #0
        bne -
        lda d_blk,y
        clc
        adc #BLK0
        sta PTRS + DSPR
        lda t
        and #15
        tay
        lda spark,y
        sta $d025
        rts

; it_end (osalevy): R_TICK pois, spritet pois ja kuva pimeäksi kuten spritetin spr_hiljaa
it_end
        #TICK 0
        lda #$0b
        sta $d011
        lda #0
        sta $d015
        rts

bits    .byte 1, 2, 4, 8, 16, 32, 64, 128
t       .byte 0
li      .byte 0
en      .byte 0
msb     .byte 0
act     .fill 8
ph      .fill 8
yy      .fill 8
xlo     .fill 8
xhi     .fill 8
        .include "it.inc"
        .cerror * > PTRS, "ilotulitus: koodi ja taulut osuvat spriteosoittimiin ($c7f8)"

        * = KUVAT
        .include "it_kuvat.inc"
        .cerror * > $ce00, "ilotulitus: kuvat yli sivun $cd (ennätyksen varattu $c4-$cd)"
