; Kaupungintalo, peli (demon kehykset PELI_ALKU - PELI_ALKU+PELI_PITUUS-1): SimCity-henkinen Lohja 1989
; MC-merkkitilassa. Taulut ja aikataulu peli_build.py -> OUT/peli.inc, peli_data.asm.
;
; Kehys:
;   251  irq_main: ylärivien merkistö A ja ruutu ($D018), $D011 = $1b, FRAME_HOOK, cli ja logiikka (tapahtumat,
;        vieritys, spritet, vilkku, kirjoitus). Raskas työ (värimuisti tai takapuskuri, 920 t) ylhäältä alas
;        säteen edellä.
;   62   irq_split: FLD-rako rivin 1 jälkeen (z_gapn >= 1 riviä, idle-tila), raon ensimmäisellä rivillä $D018 =
;        ruutu + vaiheen merkistö. Kartta alkaa riviltä 67 + z_gapn: vieritys = karkea rivi (ruutupuskurit) +
;        raon korkeus. Vierityksen aikana raon peittää 7 X-levennettyä spriteä (sininen kaista riveillä 67-74).
;        Sitten jonossa olevat värityöt (VARIT, cjobs) säteen perässä: ison palan (neuvonantajan ikkuna) värit
;        kehystä ennen kuin sen koodit vaihtuvat rajalla (KOODIT tai P4:n ruutu), joten pala vaihtuu kokonaan
;        yhdessä kehyksessä.
;
; Muisti (VIC-pankki 1):
;   KT4 $2000-$5fff  koodi, taulut, käyttöliittymä, värit; ruudut $4000/$4400, merkistöt A $4800 ja P1 $5000,
;                    spritet $5800 ja P1:n kartta niiden perässä
;   KT5 $6000-       merkistöt P2 $6000, P3 $6800, P4 $7000, kartat P2 $7800, P3 $8000, P4 $83e8 ($7fff = 0:
;                    idle-rivin kuvio)

        .include "peli.inc"

FRAME_HOOK = $0408
DFRAME  = $d0

SCR0    = $4000
SCR1    = $4400
CH_A    = $4800
CH_P1   = $5000
CH_P2   = $6000
CH_P3   = $6800
CH_P4   = $7000
SPRMEM  = $5800
IRQ_MAIN = 251                  ; alareunassa: $D018 rivin 250 aikana vaihtaisi viimeisen rivin loppuosan merkistön
COLBUF  = $7c00                 ; alkuvärit peli_initistä peli_go:hon (huoneen vapautunutta muistia, ennen KT5:ttä)

        .virtual $02
ra      .byte ?
rx      .byte ?
ry      .byte ?
z_t     .word ?                 ; pelin kehys
z_ev    .byte ?                 ; seuraava tapahtuma
z_scr   .byte ?                 ; näkyvän ruudun korkea tavu ($40 / $44)
z_back  .byte ?                 ; takapuskurin korkea tavu
z_chp   .byte ?                 ; vaiheen merkistön $D018-bitit
z_phase .byte ?                 ; 0-3 = P1-P4
z_c     .byte ?                 ; karkea vieritysrivi (kartan rivi ruudun rivillä 0)
z_gapn  .byte ?                 ; FLD-rako riveinä (>= GAP)
z_need  .byte ?                 ; takapuskuri täytettävä riville z_c+1 (vieritys)
z_band  .byte ?
z_flash .byte ?
z_type  .byte ?                 ; kirjoitettava pala ($ff = ei)
z_tn    .byte ?                 ; kirjoitettuja merkkejä
z_colhi .byte ?                 ; värien kohde: $d8 tai puskuri
z_kbase .word ?                 ; vaiheen kartan koodit riviltä z_c (ruudun rivi 0)
src     .word ?
dst     .word ?
dsc     .word ?
z_rows  .byte ?
z_w     .byte ?
z_tmp   .byte ?
z_ok    .byte ?
z_i     .word ?                 ; kursorin taulun indeksi T / 2
z_hi    .byte ?
z_en    .byte ?
z_k     .byte ?
z_busy  .byte ?
z_cok   .byte ?                 ; peli_go: värit jo kopioitu
col_src .word ?
z_rm    .byte ?                 ; restore: $40 = vain värit
z_cjn   .byte ?                 ; värityöt jonossa (cjobs)
z_cjx   .byte ?
z_cj    .fill 2                 ; värityöt: pala, | $80 = alla olevan kartan värit
zp_end
        .cerror zp_end > $30, "pelin nollasivu osuu ytimen nollasivuun $30- (peli_init ajetaan ytimen IRQ:n aikana)"
        .endv

; ================================================================ KT4
        * = $2000
        jmp peli_init                   ; $2000: pääsäie latauksen jälkeen (kuva ennallaan)
        jmp peli_go                     ; $2003: ydin kutsuu IRQ:sta kehyksessä PELI_ALKU

; peli_init: ruutu 0 ja värit puskuriin (näyttö pyörii vielä pankissa 2 eikä värimuistiin saa kirjoittaa)
peli_init
        ldx #ra
        lda #0
-       sta $00,x
        inx
        cpx #zp_end
        bne -
        sta $7fff                       ; idle-rivin kuvio tyhjä
        lda #>SCR0
        sta z_scr
        lda #>SCR1
        sta z_back
        lda #$ff
        sta z_type
        lda #GAP
        sta z_gapn
        lda #((CH_P1 & $3fff) >> 10)
        sta z_chp
        lda #<K_P1
        sta z_kbase
        lda #>K_P1
        sta z_kbase+1
        lda #>COLBUF
        sta z_colhi
        lda #<K_P1                      ; rivit 0-24 P1:n kartasta ja väreistä
        sta src
        lda #>K_P1
        sta src+1
        lda #<SCR0
        sta dst
        lda #>SCR0
        sta dst+1
        lda #25
        jsr copy_rows
        lda #<VARIT
        sta src
        lda #>VARIT
        sta src+1
        lda #<COLBUF
        sta dst
        lda #>COLBUF
        sta dst+1
        lda #25
        jsr copy_rows
        ldx #7                          ; spriteosoittimet molempiin ruutuihin
-       lda #SL_KAISTA
        sta SCR0 + $3f8,x
        sta SCR1 + $3f8,x
        dex
        bpl -
_ev0    ldx z_ev                        ; kehyksen 0 tapahtumat (valikko auki)
        lda ev_t_lo,x
        ora ev_t_hi,x
        bne +
        jsr do_event
        jmp _ev0
+       inc z_ok
        rts

; peli_go: IRQ:sta (kehyksen 0 alussa rivin 250 jälkeen): VIC pankkiin 1, värit, oma IRQ-ketju
; X = 1: ydin kopioi värit jo säteen perässä edellisessä kehyksessä (kt.asm cc_copy)
peli_go
        lda z_ok
        bne +
        rts
+       stx z_cok
        lda #$d8
        sta z_colhi
        lda #2                          ; VIC-pankki 1 heti rajalla, värit vasta sen jälkeen säteen edellä
        sta $dd00
        lda #D021
        sta $d021
        lda #D022
        sta $d022
        lda #D023
        sta $d023
        lda #$18                        ; MC
        sta $d016
        lda #0
        sta $d020
        sta $d015
        sta $d017
        sta $d01b
        sta $d01d
        lda #0                          ; $D025 musta, $D026 tummanharmaa (purkajan MC-spritet)
        sta $d025
        lda #11
        sta $d026
        lda #%00001100
        sta $d01c
        lda #1
        sta $d027
        lda #0
        sta $d028
        lda #7
        sta $d029
        sta $d02a
        jsr top_regs
        jsr sprites
        lda #<irq_split                 ; jako ensin päälle: värikopio kestää rivin 62 yli
        sta $fffe
        lda #>irq_split
        sta $ffff
        lda #62
        sta $d012
        lda #$ff
        sta $d019
        lda z_cok
        bne _done
        cli                             ; jako saa keskeyttää
        ldx #39                         ; värit kahdessa osassa: rivit 0-12 valmiit ennen riviä 51,
-                                       ; rivit 13-24 ennen kuin säde ehtii niihin
        .for r = 0, r < 13, r += 1
        lda COLBUF + r * 40,x
        sta $d800 + r * 40,x
        .next
        dex
        bpl -
        ldx #39
-
        .for r = 13, r < 25, r += 1
        lda COLBUF + r * 40,x
        sta $d800 + r * 40,x
        .next
        dex
        bpl -
        sei
_done   rts

top_regs
        lda z_scr
        and #$3c                        ; ($40 / $44) -> ruutu * 16 pankin sisällä
        asl
        asl
        ora #((CH_A & $3fff) >> 10)
        sta $d018
        lda #$1b
        sta $d011
        rts

; ---------------------------------------------------------------- IRQ
irq_main
        pha                             ; pinoon: cli:n jälkeen seuraava irq_main voi keskeyttää edellisen (logic yli
        txa                             ; kehyksen, esim. latauksen aikana), joten kiinteät muuttujat ylikirjoittuisivat
        pha
        tya
        pha
        asl $d019
        jsr top_regs
        lda #<irq_split
        sta $fffe
        lda #>irq_split
        sta $ffff
        lda #62
        sta $d012
        jsr FRAME_HOOK
        lda DFRAME                      ; pelin kehys demon kellosta (myöhästynyt lataus kurotaan kiinni)
        sec
        sbc #<PELI_ALKU
        sta z_t
        lda DFRAME+1
        sbc #>PELI_ALKU
        sta z_t+1
        lda z_busy                      ; edellinen logiikka kesken: vain musiikki ja kello tällä kertaa
        bne _skip
        inc z_busy
        cli                             ; jako saa keskeyttää logiikan
        jsr logic
        sei
        dec z_busy
_skip   pla
        tay
        pla
        tax
        pla
        rti

irq_split
        pha
        txa
        pha
        tya
        pha
        asl $d019
        lda z_scr
        and #$3c
        asl
        asl
        ora z_chp
        tax                             ; X = alaosan $D018
-       lda $d012                       ; odota riviä 66; jos IRQ myöhästyi (lataaja), vain $D018 ja paluu
        cmp #66
        bcc -
        beq +
        stx $d018
        jmp _last
+       lda #$18 | ((66 + 2) & 7)       ; rivi 67 idle
        sta $d011
        lda #67
-       cmp $d012
        bne -
        stx $d018                       ; raon ensimmäisellä rivillä (ei merkkihakuja)
        ldy z_gapn
_gap    dey
        beq _last
        lda $d012                       ; rivi L idle: L+1 myös idle
        clc
        adc #2
        and #7
        ora #$18
        sta $d011
        lda $d012
-       cmp $d012
        beq -
        jmp _gap
_last   lda $d012                       ; rivi 66+n: badline seuraavalla rivillä
        clc
        adc #1
        and #7
        ora #$18
        sta $d011
        lda #<irq_main
        sta $fffe
        lda #>irq_main
        sta $ffff
        lda #IRQ_MAIN
        sta $d012
        lda z_cjn                       ; värityöt säteen perässä (VARIT); jos ne kestävät rivin IRQ_MAIN yli,
        beq +                           ; irq_main tulee heti niiden jälkeen (ei jää väliin)
        jsr cjobs
+
        pla
        tay
        pla
        tax
        pla
        rti

; ---------------------------------------------------------------- logiikka (kerran kehyksessä)
logic
        jsr sprites
        lda z_need                      ; takapuskuri ensin: vierityksen askel ei osu samaan kehykseen
        beq +
        jsr prefill
        lda z_phase
        cmp #1
        bne _ev
        jsr scroll
        jmp _ev
+       lda z_phase
        cmp #1
        bne +
        jsr scroll
+       lda z_type
        bmi _ev
        jsr type_char
_ev     ldx z_ev                        ; tapahtumat: T >= ev_t
        lda z_t
        cmp ev_t_lo,x
        lda z_t+1
        sbc ev_t_hi,x
        bcc _flash
        jsr do_event
        jmp _ev
_flash  lda z_flash
        beq +
        lda z_t
        and #7
        bne +
        jsr flash
+       rts

do_event
        ldx z_ev
        inc z_ev
        ldy ev_arg,x
        lda ev_op,x
        cmp #OP_DRAW
        bne +
        jmp draw
+       cmp #OP_RESTORE
        bne +
        jmp restore
+       cmp #OP_PREP
        bne +
        jmp prep
+       cmp #OP_SWAP
        bne +
        jmp swap_phase
+       cmp #OP_TYPE
        bne +
        sty z_type
        lda #0
        sta z_tn
        rts
+       cmp #OP_FLASH
        bne +
        sty z_flash
        rts
+       cmp #OP_BAND
        bne +
        sty z_band
        rts
+       cmp #OP_VARIT
        bne +
        ldx z_cjn
        sty z_cj,x
        inc z_cjn
        rts
+       cmp #OP_KOODIT
        bne +
        jmp draw_k
+       rts

; ---------------------------------------------------------------- käyttöliittymäpalat
; osa_setup: Y = pala -> src (koodit), dst (ruutu), dsc (värit), z_rows, z_w
osa_setup
        lda osa_lo,y
        sta src
        lda osa_hi,y
        sta src+1
        lda osa_kork,y
        sta z_rows
        lda osa_lev,y
        sta z_w
        ldx osa_rivi,y
        lda osa_sar,y
        clc
        adc row_lo,x
        sta dst
        sta dsc
        lda row_hi,x
        adc #0
        sta z_tmp
        clc
        adc z_scr
        sta dst+1
        lda z_tmp
        clc
        adc z_colhi
        sta dsc+1
        rts

; draw: Y = pala: koodit ruutuun, värit värimuistiin (pala: koodit h*w, sitten värit h*w). draw_k vain koodit
; (KOODIT), draw_c vain värit (cjobs)
draw
        jsr draw_k
        jmp draw_cv
draw_k
        jsr osa_setup
        lda z_rows
        sta z_tmp
_r      ldy z_w
        dey
-       lda (src),y
        sta (dst),y
        dey
        bpl -
        ldx #0                          ; dst
        jsr adv
        dec z_tmp
        bne _r
        rts
draw_cv
_c      ldy z_w                         ; värit: src jatkuu koodien perästä, dsc riviltä 0
        dey
-       lda (src),y
        sta (dsc),y
        dey
        bpl -
        ldx #2                          ; dsc
        jsr adv
        dec z_rows
        bne _c
        rts
; adv: src += w ja (dst+X) += 40 (X = 0: dst, 2: dsc)
adv     clc
        lda src
        adc z_w
        sta src
        bcc +
        inc src+1
+       clc
        lda dst,x
        adc #40
        sta dst,x
        bcc +
        inc dst+1,x
+       rts

; restore: Y = pala: alla oleva kartta (vaiheen koodit ja värit), rivit < 2 ohitetaan. restore_c vain värit
; (cjobs: ikkunan sulkeutuessa koodit vaihtaa P4:n ruutu)
restore
        lda #0
        .byte $2c                       ; bit abs: ohittaa seuraavan lda #:n
restore_c
        lda #$40
        sta z_rm
        jsr osa_setup
        ldx osa_rivi,y
        lda osa_sar,y
        clc                             ; src = kartan koodit: z_kbase + rivi*40 + sarake
        adc row_lo,x
        sta z_tmp
        lda z_kbase
        clc
        adc z_tmp
        sta src
        lda z_kbase+1
        adc row_hi,x
        sta src+1
        lda z_c                         ; värit: VARIT + (z_c + rivi)*40 + sarake
        clc
        adc osa_rivi,y
        tax
        lda osa_sar,y
        clc
        adc row_lo,x
        sta col_src
        lda row_hi,x
        adc #>VARIT
        sta col_src+1
        lda col_src
        clc
        adc #<VARIT
        sta col_src
        bcc +
        inc col_src+1
+       ldx osa_rivi,y
_r      cpx #2
        bcc _skip
        ldy z_w
        dey
        bit z_rm
        bvs _vari
-       lda (src),y
        sta (dst),y
        lda (col_src),y
        sta (dsc),y
        dey
        bpl -
        bmi _skip
_vari   lda (col_src),y
        sta (dsc),y
        dey
        bpl _vari
_skip   lda #40                         ; seuraava rivi kaikille neljälle
        jsr add40
        inx
        dec z_rows
        bne _r
        rts
add40   ldy #0
-       clc
        lda src,y
        adc #40
        sta src,y
        bcc +
        lda src+1,y
        adc #0
        sta src+1,y
+       iny
        iny
        cpy #6
        bne -
        clc
        lda col_src
        adc #40
        sta col_src
        bcc +
        inc col_src+1
+       rts

; type_char: kirjoittaa palan z_type seuraavan merkin (koodi ja väri)
type_char
        ldy z_type
        jsr osa_setup
        ldy z_tn
        lda (src),y
        sta (dst),y
        tya
        clc
        adc z_w                         ; väri: koodien perässä
        tay
        lda (src),y
        ldy z_tn
        sta (dsc),y
        iny
        sty z_tn
        cpy z_w
        bne +
        lda #$ff
        sta z_type
+       rts

; flash: Hillnerin solut vuorotellen omaan väriin ja valkoiseen
flash
        lda z_t
        and #8
        beq +
        lda #<hil_v
        ldx #>hil_v
        bne ++
+       lda #<hil_c
        ldx #>hil_c
+       sta _f+1
        stx _f+2
        ldx #HIL_N-1
-       lda hil_lo,x
        sta dsc
        lda hil_hi,x
        sta dsc+1
        ldy #0
_f      lda $ffff,x
        sta (dsc),y
        dex
        bpl -
        rts

; ---------------------------------------------------------------- vaiheet ja vieritys
; prep: Y = vaihe: takapuskuriin rivit 0-1 näkyvästä ruudusta ja rivit 2-24 vaiheen kartasta riviltä z_c
prep
        lda ph_klo,y
        sta src
        lda ph_khi,y
        sta src+1
        lda z_c
        sec
        sbc ph_alku,y
        tax
        lda src
        clc
        adc row_lo+2,x
        sta src
        lda src+1
        adc row_hi+2,x
        sta src+1
        lda #0
        sta dst
        lda z_scr
        sta dsc+1                       ; rivit 0-1 talteen: dsc = näkyvä ruutu
        lda #0
        sta dsc
        lda z_back
        sta dst+1
        ldy #79
-       lda (dsc),y
        sta (dst),y
        dey
        bpl -
        lda #80
        sta dst
        lda #23
        jmp copy_rows

; swap_phase: Y = vaihe: näkyväksi takapuskuri ja vaiheen merkistö ja kartta
swap_phase
        sty z_phase
        cpy #1                          ; P2: takapuskuri heti seuraavalle riville
        bne +
        inc z_need
+
        lda ph_ch,y
        sta z_chp
        lda z_c
        sec
        sbc ph_alku,y
        tax
        lda ph_klo,y
        clc
        adc row_lo,x
        sta z_kbase
        lda ph_khi,y
        adc row_hi,x
        sta z_kbase+1
flip    lda z_scr
        ldx z_back
        sta z_back
        stx z_scr
        jmp top_regs

; scroll: P2: vierityksen kulku taulusta, karkea askel vaihtaa ruudun ja kopioi värit
scroll
        lda z_t
        sec
        sbc #<(120)
        cmp #120
        bcc +
        rts
+       tax
        lda vier,x
        clc
        adc #7
        lsr
        lsr
        lsr                             ; c' = (p + 7) / 8
        sta z_tmp
        asl
        asl
        asl
        sec
        sbc vier,x                      ; g = 8c' - p
        clc
        adc #GAP
        sta z_gapn
        lda z_tmp
        cmp z_c
        beq _out
        sta z_c
        lda z_kbase                     ; kartta riviltä z_c (P2 alkaa riviltä 0)
        clc
        adc #40
        sta z_kbase
        bcc +
        inc z_kbase+1
+       jsr flip                        ; takapuskuri on täytetty riville z_c
        lda z_c                         ; värit: VARIT + (z_c+2)*40 -> $d800 + 80, 23 riviä
        clc
        adc #2
        tax
        lda row_lo,x
        clc
        adc #<VARIT
        sta src
        lda row_hi,x
        adc #>VARIT
        sta src+1
        lda #<($d800 + 80)
        sta dst
        lda #>($d800 + 80)
        sta dst+1
        lda #23
        jsr copy_rows
        lda z_c
        cmp #SMAX / 8
        bcs _out
        inc z_need
_out    rts

; prefill: takapuskuriin rivit 2-24 riviltä z_c+1 (P2)
prefill
        lda #0
        sta z_need
        lda z_kbase
        clc
        adc #<(40 * 3)
        sta src
        lda z_kbase+1
        adc #>(40 * 3)
        sta src+1
        lda #80
        sta dst
        lda z_back
        sta dst+1
        lda #23
        jmp copy_rows

; copy_rows: A riviä x 40 tavua (src) -> (dst), src += 40, dst += 40
copy_rows
        sta z_rows
_r      ldy #39
-       lda (src),y
        sta (dst),y
        dey
        bpl -
        clc
        lda src
        adc #40
        sta src
        bcc +
        inc src+1
+       clc
        lda dst
        adc #40
        sta dst
        bcc +
        inc dst+1
+       dec z_rows
        bne _r
        rts

; ---------------------------------------------------------------- spritet (taulut kahden kehyksen välein)
sprites
        lda z_band
        beq _norm
        ldx #6                          ; kaista: 7 X-levennettyä spriteä riville 67
-       ldy band_xi,x
        lda #67
        sta $d001,y
        lda band_x,x
        sta $d000,y
        lda #6
        sta $d027,x
        dex
        bpl -
        lda #%01100000
        sta $d010
        lda #%01111111
        sta $d01d
        sta $d015
        lda #0
        sta $d01c
        ldy #6
        jmp set_ptr_band
_norm   lda z_t+1                       ; z_i = T / 2
        lsr
        sta z_i+1
        lda z_t
        ror
        sta z_i
        lda #0
        sta $d01d
        sta z_hi                        ; $d010
        sta z_en                        ; $d015
        lda #1
        sta $d027
        lda #0
        sta $d028
        lda #7
        sta $d029
        sta $d02a
        lda #%00001100
        sta $d01c
        ldx #CUR_N-1                    ; kursori: P1 i, P3:sta alkaen i - 60 (P2:ssa kaista), rajattuna (lopussa
        lda z_i+1                       ; paikallaan)
        bne _cp3
        lda z_i
        cmp #120
        bcc _cp1
_cp3    lda z_i
        sec
        sbc #60
        tay
        lda z_i+1
        sbc #0
        bne _cur
        tya
_cp1    cmp #CUR_N
        bcs _cur
        tax
_cur    lda cur_t,x
        beq _doz
        sta z_k
        cmp #1
        bne _dia
        lda #SL_JOHTAJA_TAYTTO
        ldy #SL_JOHTAJA_REUNA
        jsr ptr01
        jmp _pos
_dia    lda #SL_TIMANTTI0
        ldy #SL_TIMANTTI1
        jsr ptr01
        lda z_t                         ; timantti vilkkuu valkoinen/musta 4 kehyksen välein (erottuu katoista);
        ldy z_flash                     ; valinnan jälkeen vastavaiheessa talon vilkkuun (valkoinen talo: musta)
        beq +
        eor #8
        lsr
+       and #4
        beq +
        lda #1
+       sta $d027
        sta $d028
_pos    lda cur_xl,x
        sta $d000
        sta $d002
        lda cur_xh,x
        beq +
        lda #%00000011
        sta z_hi
+       lda z_k
        cmp #2
        bne +
        lda $d000                       ; timantin oikea puolisko 24 px oikealle
        clc
        adc #24
        sta $d002
        bcc +
        lda z_hi
        ora #%00000010
        sta z_hi
+       lda cur_y,x
        sta $d001
        sta $d003
        lda #%00000011
        sta z_en
_doz    lda z_t                         ; purkaja joka kehys: j = T - DOZ0 >= 0
        sec
        sbc #<DOZ0
        tax
        lda z_t+1
        sbc #>DOZ0
        bcc _done
        lda doz_y,x
        beq _done
        sta $d005
        sta $d007
        lda doz_xh,x
        beq +
        lda z_hi
        ora #%00001100
        sta z_hi
+       lda doz_xl,x
        sta $d004
        clc
        adc #24
        sta $d006
        bcc +
        lda z_hi
        ora #%00001000
        sta z_hi
+       lda doz_f,x
        asl
        adc #SL_PURKAJA0A
        ldy doz_xh,x                    ; työkalupalkin kohdalla (X < PAL_X1): purkaja palkin alla
        bne +
        ldy doz_xl,x
        cpy #PAL_X1
        bcs +
        jsr doz_maski
+       jsr ptr23
        lda z_en
        ora #%00001100
        sta z_en
_done   lda z_hi
        sta $d010
        lda z_en
        sta $d015
        rts

; doz_maski: purkaja tulee työkalupalkin alta. A = kehyksen lohko a (b = a + 1), Y = spriten
; X (< PAL_X1). Lohkot kopioidaan SL_PURKAJA_MA/MB:hen niin, että palkin kohdalla olevat MC-pikselit (spritessä a
; h = (PAL_X1 - X + 1) / 2 vasemmalta, b:ssä h - 12) ovat läpinäkyviä (pal_mt: maskit h * 3 + tavu). A = SL_PURKAJA_MA.
MASKI_A = SPRMEM + (SL_PURKAJA_MA - SPR_LOHKO) * 64
doz_maski
        sty z_tmp
        tay                             ; src = $4000 + 64 * lohko (VIC-pankki 1)
        lsr
        lsr
        clc
        adc #>$4000
        sta src+1
        tya
        and #3
        lsr
        ror
        ror
        sta src
        lda #PAL_X1 + 1
        sec
        sbc z_tmp
        lsr
        sta z_k                         ; h spritelle a
        cmp #12
        bcc +
        lda #12
+       ldy #<MASKI_A
        jsr _kopio
        lda src                         ; lohko b
        clc
        adc #64
        sta src
        bcc +
        inc src+1
+       lda z_k
        sec
        sbc #12
        bcs +
        lda #0
+       cmp #12
        bcc +
        lda #12
+       ldy #<(MASKI_A + 64)
        jsr _kopio
        lda #SL_PURKAJA_MA
        rts
_kopio  sta z_tmp                       ; A = h, Y = kohteen alatavu: maski X = 3 h
        sty dst
        lda #>MASKI_A
        sta dst+1
        lda z_tmp
        asl
        adc z_tmp
        tax
        ldy #0
-       lda (src),y
        and pal_mt,x
        sta (dst),y
        iny
        lda (src),y
        and pal_mt+1,x
        sta (dst),y
        iny
        lda (src),y
        and pal_mt+2,x
        sta (dst),y
        iny
        cpy #63
        bne -
        rts
        .cerror (>MASKI_A) != (>(MASKI_A + 127)), "maskatut purkajan lohkot eri sivuilla"

ptr01   pha                             ; A = sprite 0, Y = sprite 1 molempiin ruutuihin
        sta SCR0 + $3f8
        sta SCR1 + $3f8
        tya
        sta SCR0 + $3f9
        sta SCR1 + $3f9
        pla
        rts
ptr23   sta SCR0 + $3fa                 ; A = sprite 2, A+1 = sprite 3
        sta SCR1 + $3fa
        clc
        adc #1
        sta SCR0 + $3fb
        sta SCR1 + $3fb
        rts
set_ptr_band
        lda #SL_KAISTA
-       sta SCR0 + $3f8,y
        sta SCR1 + $3f8,y
        dey
        bpl -
        rts

band_x  .byte <(24 + 48 * range(7))
band_xi .byte 0, 2, 4, 6, 8, 10, 12

; vaiheiden taulut: merkistön $D018-bitit, kartan alkurivi ja koodien osoite
ph_ch   .byte (CH_P1 & $3fff) >> 10, (CH_P2 & $3fff) >> 10, (CH_P3 & $3fff) >> 10, (CH_P4 & $3fff) >> 10
ph_alku .byte 0, 0, PELI_RIVIT - 25, PELI_RIVIT - 25
ph_klo  .byte <K_P1, <K_P2, <K_P3, <K_P4
ph_khi  .byte >K_P1, >K_P2, >K_P3, >K_P4
row_lo  .byte <(40 * range(40))
row_hi  .byte >(40 * range(40))

        .include "peli_data.asm"
PELI_UI .binary "peli_ui.bin"
VARIT   .binary "peli_varit.bin"
kt4_code_end
        .cerror kt4_code_end > SCR0, "pelin koodi ja data ylittävät $4000"

        * = SCR0
        .fill 1000                      ; peli_init täyttää
        * = SCR1
        .fill 1000
        * = CH_A
        .binary "peli_merkit_A.bin"
        * = CH_P1
        .binary "peli_merkit_P1.bin"
        * = SPRMEM
        .include "peli_spritet.asm"
K_P1    .binary "peli_kartta_P1.bin"   ; spritejen perässä (koodialue on täynnä)

; cjobs (irq_split, rivin 1 raon jälkeen): jonon värityöt säteen perässä. Jokainen työ odottaa, kunnes säde on
; ohittanut palan ylärivin badlinen (värit haettu tähän kehykseen), ja 38 solun rivin värit kestävät kauemmin kuin
; säteen rivi, joten kirjoitus pysyy säteen perässä: kuva vaihtuu vasta seuraavassa kehyksessä, jonka koodit
; KOODIT kirjoittaa rajalla säteen edellä (sulkeutuessa P4:n ruutu vaihtuu). Logiikka ei saa olla kesken samoja
; osoittimia (peli_build: VARIT-kehyksessä ei muita palatöitä).
cjobs   ldx #0
_j      stx z_cjx
        lda z_cj,x
        and #$7f
        tay
        lda osa_rivi,y
        asl
        asl
        asl
        adc #51 + GAP + 1               ; C = 0 (rivi < 32)
-       cmp $d012
        bcs -
        ldx z_cjx
        lda z_cj,x
        bmi _r
        jsr draw_c
        jmp _n
_r      jsr restore_c
_n      ldx z_cjx
        inx
        cpx z_cjn
        bne _j
        lda #0
        sta z_cjn
        rts

; draw_c: Y = pala: vain värit (src koodien h * w tavun yli)
draw_c  jsr osa_setup
        ldx z_rows
-       clc
        lda src
        adc z_w
        sta src
        bcc +
        inc src+1
+       dex
        bne -
        jmp draw_cv
kt4_end
        .cerror kt4_end > CH_P2, "KT4 ylittää $6000"

; ================================================================ KT5
        * = CH_P2
        .binary "peli_merkit_P2.bin"
        * = CH_P3
        .binary "peli_merkit_P3.bin"
        * = CH_P4
        .binary "peli_merkit_P4.bin"
        * = $7800
K_P2    .binary "peli_kartta_P2.bin"
        .fill $8000 - *, 0              ; $7fff = 0 (idle-rivi)
K_P3    .binary "peli_kartta_P3.bin"
K_P4    .binary "peli_kartta_P4.bin"
kt5_end
