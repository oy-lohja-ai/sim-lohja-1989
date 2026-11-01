; Hillner, lähikuva (TIM_CUE_LAHIKUVA - purku): sisääntulot ja IRQ lähikuvan kyltin tiedostossa KYLTTI ($1a00-,
; src/scene/kyltti_part.asm HIL_GLUE = 2). Kohtaustaulu src/scene/hil_glue.asm kutsuu:
;   lahi_go   kehyksellä HIL_LAHI (ajo-kyltin IRQ on ottanut kyltin pois kehyksellä HIL_LAHI - 1): tämän IRQ,
;             luovutuskuva pankkiin 1 (pankki 2 näkyy sillä aikaa), pankki 1 näkyviin, pyyhkäisy
;             lähikuvaan FADE_N kehyksessä (fin $e000-) ja lähikuvan kyltin alustus
;   lahi_prep fin-tiedoston latauksen jälkeen (ajo-kyltin aikana): pyyhkäisyn solulistat askelittain
;   lahi_on   kyltti tämän IRQ:hun
;   lahi_end  ennen purku_go:ta: sei ja kyltti pois tämän IRQ:sta (purku jatkaa sitä omassaan)
; lahi_go ja siirtymän koodi ovat kyltin kaatoalueella (K_SCRATCH), jonka kyltti_init nollaa: lahi_go päättyy siksi
; hyppyyn kyltti_initiin, ja IRQ on kaatoalueen alapuolella.

        .include "gen/timing.inc"
        .include "hil.inc"
        .include "runko.inc"

FIN     = $e000                 ; tiedosto fin: lähikuvan rivit 3-20 (ruutu, bittikartta, värit) ja pyyhkäisyn järjestys
F_SCR   = FIN
F_BMP   = F_SCR + 720
F_COL   = F_BMP + 5760
F_TAB   = F_COL + 720           ; solun askel 0..FADE_N-1 (tools/gfx/d64.py: diagonaali + Bayer 4 x 4)
F_LIST  = $c000                 ; lahi_prep: solut askelittain (2 t, rivi * 40 + sarake), pankki 3 on vapaa
F_STLO  = F_LIST + 720 * 2      ; askelten alut (FADE_N + 1)
F_STHI  = F_STLO + 32
FADE_N  = 24
CUT_SCR = $5c00                 ; pankki 1: ruutu $5c00, bittikartta $6000
CUT_BMP = $6000
FIN_SCR = $8800                 ; luovutuskuva pankissa 2 (src/proto/hillner/build.py INT_FIN_SCR)
FIN_BMP = $a000
        .cerror HIL_LAHI < HIL_AJO + 180, "TIM_CUE_LAHIKUVA liian aikaisin: lähikuvan kyltin ja kuvan lataus ei ehdi"

lahi_on inc kyl
        rts

lahi_end
        sei
        lda #0
        sta kyl
        rts

LAHI_LINE = 220                 ; lähikuvan rivit 3-20 päättyvät riville 218: pyyhkäisyn askel alkaa heti niiden alla
irq_lahi pha                    ; rivi LAHI_LINE: pyyhkäisy, musiikki ja kello, kyltti (piirto sisäkkäin)
        txa
        pha
        tya
        pha
        lda $01
        pha
        lda #$35
        sta $01
        asl $d019
        lda fade_on             ; pyyhkäisyn askel heti kuvan alla riveittäin (kopio säteen edellä, sama kuva
        beq +                   ; kaikilla VIC-malleilla; pääsilmukassa askel repeäisi kehysten välillä)
        jsr fade_irq
+       jsr FRAME_HOOK_AT
        lda kyl
        beq _x
        jsr kyltti_tick
        lda kbusy               ; piirto sallii seuraavan kehyksen IRQ:n (lataus pääsilmukassa)
        bne _x
        inc kbusy
        cli
        jsr kyltti_render
        dec kbusy
_x      pla
        sta $01
        pla
        tay
        pla
        tax
        pla
        rti

kyl     .byte 0                 ; 1 = kyltti IRQ:ssa
kbusy   .byte 0                 ; piirto käynnissä
fade_on .byte 0                 ; pyyhkäisy käynnissä (fade_irq kaatoalueella)
        .cerror * > K_SCRATCH, "lähikuvan IRQ kaatoalueella: ", format("$%04x", *)
        * = K_SCRATCH           ; siirtymä: kertakäyttöinen koodi kaatoalueella

lahi_go sei
        lda #<irq_lahi
        sta $fffe
        lda #>irq_lahi
        sta $ffff
        lda #LAHI_LINE
        sta $d012
        lda #0
        sta kyl
        sta kbusy
        cli
        jsr bankcopy            ; luovutuskuva pankkiin 1 (ajo-kyltin koodi on ollut $5c00-$63ff:ssä)
        lda #0                  ; värimuisti kuvan ylä- ja alapuolelta mustaksi ennen vaihtoa: pankin 1 rivien
        ldx #4 * 40             ; 0-2 bittikartassa on ajo-kyltin koodia (purun spritet letterboxissa)
-       sta $d800 + 21 * 40 - 1,x
        dex
        bne -
        ldx #3 * 40
-       sta $d800 - 1,x
        dex
        bne -
-       bit $d011               ; pankin vaihto pystypaluussa: $dd00:n ja $d018:n välissä VIC hakisi ruudun
        bpl -                   ; väärästä paikasta (kehys 909: 8 px)
        lda #2                  ; VIC-pankki 1 näkyviin, sama kuva (Krill: $dd00:aan vain 0-3)
        sta $dd00
        lda #$78
        sta $d018
        lda #0
        sta fk
        inc fade_on             ; IRQ tekee askeleet FADE_N kehyksessä
-       jsr R_IDLE
        lda fade_on
        bne -
        lda #0                  ; lähikuvan kyltti bittikartan edessä (ajo-kyltti oli katuvalon takana)
        sta $d01b
        jmp kyltti_init         ; lähikuvan kyltti (nollaa kaatoalueen, jolla tämä koodi on)

; ---------------------------------------------------------------- siirtymä lähikuvaan
        .virtual $40            ; kyltin nollasivu: lähikuvan kyltti alustetaan pyyhkäisyn jälkeen
fp      .word ?                 ; askeleen solutietue
fe      .word ?                 ; askeleen loppu
qs      .word ?                 ; solu
qa      .word ?                 ; lähde
qb      .word ?                 ; kohde
fk      .byte ?                 ; askel
        .endv

BC      = ZT + 2                ; bankcopy: integraattorin nollasivu
bankcopy                        ; pankki 2 -> pankki 1: ruutu 4 sivua, bittikartta 32 sivua
        lda #>FIN_SCR
        ldx #>CUT_SCR
        ldy #4
        jsr _pc
        lda #>FIN_BMP
        ldx #>CUT_BMP
        ldy #32
_pc     sta BC+1
        stx BC+3
        sty BC+4
        ldy #0
        sty BC
        sty BC+2
-       lda (BC),y
        sta (BC+2),y
        iny
        bne -
        inc BC+1
        inc BC+3
        dec BC+4
        bne -
        rts

; pääsilmukasta ajo-kyltin aikana (sen nollasivu on $40-, siksi Hillnerin $d4-$d8 kuten bankcopy): F_TAB:n solut
; askelittain F_LISTiin (noin 155 000 sykliä); solu = PA - F_TAB
PP      = ZT + 2
PK      = ZT + 4
PA      = ZT + 5
lahi_prep
        lda #<F_LIST
        sta PP
        lda #>F_LIST
        sta PP+1
        lda #0
        sta PK
_k      ldx PK                  ; askeleen alku
        lda PP
        sta F_STLO,x
        lda PP+1
        sta F_STHI,x
        cpx #FADE_N
        beq _r
        lda #<F_TAB
        sta PA
        lda #>F_TAB
        sta PA+1
_s      ldy #0
        lda (PA),y
        cmp PK
        bne _n
        sec
        lda PA
        sbc #<F_TAB
        sta (PP),y
        iny
        lda PA+1
        sbc #>F_TAB
        sta (PP),y
        clc
        lda PP
        adc #2
        sta PP
        bcc _n
        inc PP+1
_n      inc PA
        bne +
        inc PA+1
+       lda PA
        cmp #<(F_TAB + 720)
        bne _s
        lda PA+1
        cmp #>(F_TAB + 720)
        bne _s
        inc PK
        bne _k
_r      rts

fade_irq                        ; IRQ:sta: askeleen fk solut (ruutu, värit, 8 bittikarttatavua) riveittäin
        ldx fk                  ; ylhäältä alas, fp = askeleen alku, fe = loppu
        lda F_STLO,x
        sta fp
        lda F_STHI,x
        sta fp+1
        lda F_STLO + 1,x
        sta fe
        lda F_STHI + 1,x
        sta fe+1
_cell   lda fp
        cmp fe
        bne +
        lda fp+1
        cmp fe+1
        beq _done
+       ldy #0                  ; solu c: ruutu ja värit
        lda (fp),y
        sta qs
        iny
        lda (fp),y
        sta qs+1
        clc
        lda qs
        adc #<F_SCR
        sta qa
        lda qs+1
        adc #>F_SCR
        sta qa+1
        clc
        lda qs
        adc #<(CUT_SCR + 3 * 40)
        sta qb
        lda qs+1
        adc #>(CUT_SCR + 3 * 40)
        sta qb+1
        ldy #0
        lda (qa),y
        sta (qb),y
        clc
        lda qs
        adc #<F_COL
        sta qa
        lda qs+1
        adc #>F_COL
        sta qa+1
        clc
        lda qs
        adc #<($d800 + 3 * 40)
        sta qb
        lda qs+1
        adc #>($d800 + 3 * 40)
        sta qb+1
        lda (qa),y
        sta (qb),y
        asl qs                  ; bittikartta: 8 * solu
        rol qs+1
        asl qs
        rol qs+1
        asl qs
        rol qs+1
        clc
        lda qs
        adc #<F_BMP
        sta qa
        lda qs+1
        adc #>F_BMP
        sta qa+1
        clc
        lda qs
        adc #<(CUT_BMP + 3 * 320)
        sta qb
        lda qs+1
        adc #>(CUT_BMP + 3 * 320)
        sta qb+1
        ldy #7
-       lda (qa),y
        sta (qb),y
        dey
        bpl -
        clc
        lda fp
        adc #2
        sta fp
        bcc _cell
        inc fp+1
        bne _cell
_done   inc fk
        lda fk
        cmp #FADE_N
        bne +
        lda #0
        sta fade_on
+       rts

