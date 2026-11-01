; Siirtymä graafi -> kuoppa (siirtymä kohtausvälin mustan tilalla): graafin
; tietokoneruutu sammuu kuin kuvaputki. Kehykset 0-1: graafin viimeinen kuva kaistana, joka painuu keskiriville
; (rasterikeskeytykset: kaistan ulkopuolella laiton tila ECM + BMM = musta), sitten valkoinen vaakaviiva
; spriteinä kutistuu pisteeksi, joka hiipuu jälkihehkuna. Kuoppa alkaa iskulle (I_SHOW kutsuu crt_endin).
; Työ rungon IRQ:n R_TICKissä (rivi 250, musiikin jälkeen) ja kaistan kahdessa keskeytyksessä; pääsäie
; valmistelee kuoppaa samaan aikaan.
; Muisti: tiedosto CRT1 ladataan graafin aikana $8000:aan (graafin vapaat sivut, siirtymat.json "esilataus").
; Kuopan kp_init kirjoittaa $8000-$83bf:n päälle noin kehyksestä 3 (kp_stage ensin), joten siellä on vain
; kaistavaihe; crt_go kopioi spritevaiheen graafin kuolleeseen muistiin alueille, joihin kp_stage ja kp_init eivät
; koske ennen kuopan kp_go:ta (mitattu VICEllä: muistin vertailu kp_stage -> kp_go): koodi $9fc0-$a0ff, taulut
; $a200-$a2ff ja spritet $bec0-$bfff (siirtymat.json "ajoalueet", kartoitus ei kirjoita niihin). Kaista näyttää
; graafin bittikartan rivit 4-19, joten kopio ei näy. Spritet VIC-pankissa 2 (graafin pankki, ei $dd00:aa): ruutu
; $bc00 eli osoittimet $bff8, lohkot $bec0-. Muuttujat ajoalueella (ei nollasivua: kuopan kp_init nollaa omansa).
; Data tools/disk/crt.py.

        .include "runko.inc"

KOODI   = $9fc0                 ; spritevaihe (kopiot)
TAULU   = $a200
SHAPES  = $bec0
SCR     = $bc00                 ; spritevaiheen ruutu: kuva mustana ($d018 = $f8)
PTRS    = SCR + $3f8
BLK     = (SHAPES & $3fff) / 64

        * = $8000
        .include "crt.inc"      ; vakiot ja kaistan taulut

; crt_go (taulusta ku_cutin jälkeen, reunuksessa; rungon IRQ päällä): kehyksen 0 kaista heti, R_TICK, sitten
; spritevaihe ajoalueille (alle 0,3 kehystä, ennen ensimmäistä R_TICKiä rivillä 250)
crt_go
        sei
        lda #0
        sta $d015
        sta $d01b
        sta $d01c
        lda #CY
        ldx #14
-       sta $d001,x
        dex
        dex
        bpl -
        ldx #0
        jsr arm                 ; kaistan yläreuna on vielä edessä: ku_cut palaa reunuksessa
        #TICK crt_tick
        cli
        #copy koodi_src, KOODI, koodi_end - KOODI
        #copy taulu_src, TAULU, taulu_end - TAULU
        #copy muoto_src, SHAPES, $100
        #copy muoto_src + $100, SHAPES + $100, muoto_end - SHAPES - $100
        rts

copy    .macro src, dst, n      ; n = 1-256 tavua
        .cerror \n < 1 || \n > 256, "copy: 1-256 tavua"
        ldx #<\n
-       lda \src - 1,x
        sta \dst - 1,x
        dex
        bne -
        .endm

; arm (X = kaistakehys): ylä- ja alaosa mustina, keskeytys kaistan yläreunaan
arm     stx bi
        lda band_top,x
        sta $d012
        lda #<irq_top
        sta $fffe
        lda #>irq_top
        sta $ffff
        lda #$7b
        sta $d011
        rts

irq_top pha
        lda $01
        pha
        lda #$35
        sta $01
        lda #$3b                ; graafin hires-bittikartta
        sta $d011
        asl $d019
        txa
        pha
        ldx bi
        lda band_bot,x
        sta $d012
        lda #<irq_bot
        sta $fffe
        lda #>irq_bot
        sta $ffff
        pla
        tax
        pla
        sta $01
        pla
        rti

irq_bot pha
        lda $01
        pha
        lda #$35
        sta $01
        lda #$7b
        sta $d011
        jsr R_IRQ_ON            ; rungon IRQ riville 250 (kuittaa)
        pla
        sta $01
        pla
        rti

bi      .byte 0

koodi_src
        .logical KOODI
; crt_end (kuopan I_SHOW ennen kp_showta, ku_start rivin 250 jälkeen): spritet pois, R_TICK pois ja kuva
; pimeäksi kuten ku_cut (DEN 0: kp_show:n puolivalmis kuva ei näy kehyksen alaosassa)
crt_end
        lda #$0b
        sta $d011
        lda #0
        sta $d015
        sta $d017
        sta $d01d
        #TICK 0
        rts

; ---------------------------------------------------------------- kehys (rungon IRQ, rivi 250)
crt_tick
        inc t
        lda t
        cmp #NBAND
        bcs +
        tax
        jmp arm                 ; latausalue ehjä kehyksiin 0-1 asti
+       sbc #NBAND
        cmp #NLINE
        bcc _line
        lda #0                  ; viimeisen jälkeen musta iskuun asti
        sta $d015
        rts
_line   tax
        lda #$7b
        sta $d011
        lda #$f8                ; ruutu SCR, bittikartta $a000 (pankki 2)
        sta $d018
        lda ln_ptr,x
        clc
        adc #BLK
        ldy #7
-       sta PTRS,y
        dey
        bpl -
        lda ln_col,x
        ldy #7
-       sta $d027,y
        dey
        bpl -
        lda ln_mode,x           ; bitit 0-2 spritejä, 3 X-laajennus, 4 x:n 9. bitti, 7 Y-laajennus
        and #7
        sta n
        tay
        lda masks,y
        sta $d015
        sta en
        ldy #0
        lda ln_mode,x
        bpl +
        ldy en
+       sty $d017
        ldy #0
        and #8
        beq +
        ldy en
+       sty $d01d
        lda ln_mode,x
        lsr
        lsr
        lsr
        lsr
        and #1
        sta xh
        lda ln_xlo,x
        sta xl
        lda ln_step,x
        sta step
        lda #0
        sta msb
        tax                     ; X = sprite, Y = rekisterin kohta
        tay
_pos    lda xl
        sta $d000,y
        lda xh
        beq +
        lda bits,x
        ora msb
        sta msb
+       clc
        lda xl
        adc step
        sta xl
        bcc +
        inc xh
+       iny
        iny
        inx
        cpx n
        bne _pos
        lda msb
        sta $d010
        rts

koodi_end
        .cerror koodi_end > $a100, "koodi yli $a0ff:n (kuoppa kirjoittaa $a100-)"
        .endlogical

taulu_src
        .logical TAULU
masks   .byte 0, 1, 3, 7, 15, 31, 63, 127
bits    .byte 1, 2, 4, 8, 16, 32, 64, 128
        .include "crt_ajo.inc"  ; viivan kehystaulu
t       .byte 0
n       .byte 0
en      .byte 0
xl      .byte 0
xh      .byte 0
step    .byte 0
msb     .byte 0
taulu_end
        .cerror taulu_end > $a300, "taulut yli $a2ff:n (kuopan PUFFX $a300-)"
        .endlogical

muoto_src
        .logical SHAPES
        .include "crt_muodot.inc"
        .cerror * > PTRS, "muodot osoittimien päällä"
        .fill PTRS - *, 0
        .fill 8, 0              ; osoittimet (crt_tick kirjoittaa)
muoto_end
        .endlogical
