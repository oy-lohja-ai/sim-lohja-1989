; Savupiippujen savu. Pääsilmukan vapaa-ajalla 12,5 Hz:llä: savupallot nousevat piippujen suilta, ajautuvat tuulen
; mukana, kasvavat ja harvenevat (vaiheet iän mukaan). Pallo piirretään näkyvän asettelun bittikarttaan vain
; taivaspikseleihin (MC 00, taulukko smk_sky alkuperäisestä tavusta), solun savuroolin bittipareilla
; (build.py: smoke_roles).
;
; Näytölle kerralla: pääsilmukka ei kirjoita bittikarttaan, vaan tekee päivityksestä koodia (SM_CODE): ensin
; edellisen päivityksen tavujen palautus tietueista (lda #alkuperäinen, sta tavu), sitten uudet pallot
; (lda tavu, and #~maski, ora #savu, sta tavu: päällekkäiset pallot yhdistyvät). Alareunan IRQ ajaa sen
; ennen logiikkaa (sm_apply, säde ikkunan alla), joten puolivalmista päivitystä ei koskaan näy. Suoraan
; bittikarttaan piirto kestäisi pääsilmukassa useita kehyksiä, ja IRQ näyttäisi puolivalmiin tilan.
; Asettelu luetaan kerran päivityksen alussa (sm_lay); jos näkyvä asettelu vaihtuu ennen ajoa, päivitys jätetään
; pois ja palautuslista unohdetaan (vanha pankki rakennetaan uudelleen).

NPUFF   = 4
SM_RATE = 4                     ; päivitys enintään joka 4. kehys (12,5 Hz): päivitys vie 3-5 kehyksen pääsilmukka-ajan
LIFE    = SMOKE_NS * 5          ; päivityksiä (vaihe = ikä / 5)
SM_SPAWN = 150                  ; uusia palloja kehykseen asti
SM_EVERY = 2                    ; päivityksiä pallojen välillä (piiput vuorotellen)
NDIRTY  = 112                   ; tavuja päivityksessä (täynnä: ei piirretä)
; koodipuskuri (15 tavua per tavu) pankin 2 spritelohkojen perässä ennen tietueita ($8c00, build.py INT_REGIONS);
; luovutuskuvan ruutu $8800- kirjoitetaan vasta hil_finissä, kun savu on loppunut
SM_CODE = BANK2_SCR + SPR_BASE + N_BLOCKS * 64
        .cerror SM_CODE + 15 * NDIRTY + 1 > BANK2_SCR + $c00, "savun koodi"

smoke   lda frame+1
        bne _r
        lda frame               ; vähintään SM_RATE kehystä edellisestä
        sec
        sbc sm_last
        cmp #SM_RATE
        bcs smoke_now
_r      rts
smoke_now                       ; pääsilmukka heti asettelun vaihdon jälkeen
        lda sm_ready            ; edellinen päivitys vielä ajamatta
        bne _x
        lda frame
        sta sm_last
        lda k_cur
        cmp sm_lay
        sta sm_lay
        beq +
        lda #0                  ; asettelu vaihtui: vanha pankki rakennetaan uudelleen, palautuslista pois
        sta sm_nd
+       lda #<SM_CODE
        sta sm_cp
        lda #>SM_CODE
        sta sm_cp+1
        jsr sm_restore
        jsr sm_spawn
        jsr sm_move
        jsr sm_draw
        ldy #0
        lda #$60                ; rts
        sta (sm_cp),y
        inc sm_ready
_x      rts

; alareunan IRQ:sta ennen logiikkaa: valmis päivitys näytölle, jos sen asettelu näkyy yhä
sm_apply
        lda sm_ready
        beq _x
        lda sm_lay
        cmp k_cur
        bne +
        jsr SM_CODE
        inc sm_cnt
+       lda #0
        sta sm_ready
_x      rts

sm_restore                      ; edellisen päivityksen tavut alkuperäisiksi: lda #tietueen tavu, sta tavu
        ldx sm_nd
        beq _x
-       dex
        lda sd_rl,x
        sta sm_rp
        lda sd_rh,x
        sta sm_rp+1
        ldy #0
        lda (sm_rp),y
        ldy #1
        sta (sm_cp),y
        dey
        lda #$a9
        sta (sm_cp),y
        ldy #2
        lda #$8d
        sta (sm_cp),y
        iny
        lda sd_bl,x
        sta (sm_cp),y
        iny
        lda sd_bh,x
        sta (sm_cp),y
        lda sm_cp
        clc
        adc #5
        sta sm_cp
        bcc +
        inc sm_cp+1
+       txa
        bne -
        stx sm_nd
_x      rts

sm_spawn
        lda frame
        cmp #SM_SPAWN
        bcs _x
        dec sm_tmr
        bpl _x
        lda #SM_EVERY
        sta sm_tmr
        ldy sm_src              ; piiput vuorotellen
        iny
        cpy #SMOKE_NSRC
        bcc +
        ldy #0
+       sty sm_src
        ldx #NPUFF - 1          ; vapaa paikka
-       lda pf_age,x
        cmp #LIFE
        bcs +
        dex
        bpl -
_x      rts
+       lda #0
        sta pf_age,x
        sta pf_xl,x
        sta pf_yl,x
        lda smk_srcx,y
        sta pf_xh,x
        lda smk_srcy,y
        sta pf_yh,x
        rts

sm_move ldx #NPUFF - 1          ; nousu hidastuu iän mukaan, tuuli oikealle
-       lda pf_age,x
        cmp #LIFE
        bcs _n
        inc pf_age,x
        tay
        sec
        lda pf_yl,x
        sbc sm_vy,y
        sta pf_yl,x
        lda pf_yh,x
        sbc #0
        sta pf_yh,x
        bpl +
        lda #LIFE               ; kuvan yläreunan yli: pois
        sta pf_age,x
        bne _n
+       clc
        lda pf_xl,x
        adc sm_vx,y
        sta pf_xl,x
        bcc _n
        inc pf_xh,x
_n      dex
        bpl -
        rts

; Pallot koodiksi: rivin osoittimet (tietue sm_rp, bittikartta sm_bab, roolit sm_ri) kerran riviä kohden,
; tavu b indeksillä 8b.
sm_draw ldx #NPUFF - 1
_p      stx sm_i
        lda pf_age,x
        cmp #LIFE
        bcc +
        jmp _np
+       tay                     ; vaihe = ikä / 5
        lda sm_div5,y
        tay
        lda smk_dk,y
        sta sm_dk
        tya                     ; maski: (vaihe * 2 + (x & 2) / 2) * H * W
        asl a
        sta sm_t
        lda pf_xh,x
        sec
        sbc #6                  ; pallon vasen reuna
        and #$fe                ; 2 MC-px:n tarkkuus (esisiirrot 0 ja 2)
        sta sm_x
        and #2
        lsr a
        ora sm_t
        tay
        lda sm_mlo,y
        sta sm_mp
        lda sm_mhi,y
        sta sm_mp+1
        lda sm_x
        lsr a
        lsr a
        sta sm_cx
        lda pf_yh,x
        sec
        sbc #6
        sta sm_y
        lda #0
        sta sm_r
_row    lda sm_y                ; rivi kuvassa 0..8 * SMOKE_R1 - 1
        cmp #8 * SMOKE_R1
        bcc +
        jmp _np                 ; alempana ei savua (rivit vain kasvavat)
+       lsr a
        lsr a
        lsr a
        sta sm_cy
        ldx sm_lay              ; asettelun sm_lay pankkiin, rivi = kuvan rivi - asettelun alku
        sec
        sbc lay_row,x
        bcs +
        jmp _nr                 ; asettelun yläpuolella (ei näy)
+       tay
        lda sm_y
        and #7
        sta sm_t                ; rivi solussa
        lda sm_cx
        asl a
        asl a
        asl a
        ora sm_t                ; 8 * sarake + rivi solussa (C1 <= 32: alle 256)
        sta sm_o
        clc
        adc sm_blo,y
        sta sm_bab
        lda sm_bhi,y
        adc #0
        ora sm_bank,x
        sta sm_bab+1
        ldy sm_cy
        clc
        lda row_lo,y
        adc sm_o
        sta sm_rp
        lda row_hi,y
        adc #0
        sta sm_rp+1
        lda sm_rowc,y           ; roolit: solu (cy, cx - C0)
        clc
        adc sm_cx
        sec
        sbc #SMOKE_C0
        sta sm_ri
        lda #0
        sta sm_b
_byte   lda sm_r                ; maskin tavu r * W + b
        asl a
        asl a
        ora sm_b
        tay
        lda (sm_mp),y
        bne +
        jmp _nb
+       sta sm_m
        lda sm_cx
        clc
        adc sm_b
        cmp #SMOKE_C1
        bcs _nr                 ; oikealla savualueen ulkopuolella
        cmp #SMOKE_C0
        bcc _nb
        lda sm_ri
        clc
        adc sm_b
        tay
        lda sm_dk
        beq +
        lda smk_dark,y
        bne ++
        beq _nb
+       lda smk_light,y
        beq _nb
+       sta sm_role
        lda sm_b
        asl a
        asl a
        asl a
        sta sm_o                ; 8b
        tay
        lda (sm_rp),y           ; alkuperäinen tavu: korvattavat taivasparit maskin alla
        tax
        lda smk_sky,x
        and sm_m
        beq _nb
        sta sm_k
        ldx sm_nd               ; palautuslista täynnä: ei piirretä (muuten jälki jäisi)
        cpx #NDIRTY
        bcs _nb
        lda sm_bab              ; tavun osoite bittikartassa ja tietueessa palautuslistaan
        clc
        adc sm_o
        sta sd_bl,x
        lda sm_bab+1
        adc #0
        sta sd_bh,x
        lda sm_rp
        clc
        adc sm_o
        sta sd_rl,x
        lda sm_rp+1
        adc #0
        sta sd_rh,x
        inc sm_nd
        ldy #0                  ; lda tavu, and #~maski, ora #savu, sta tavu
        lda #$ad
        sta (sm_cp),y
        ldy #7
        lda #$8d
        sta (sm_cp),y
        ldy #1
        lda sd_bl,x
        sta (sm_cp),y
        ldy #8
        sta (sm_cp),y
        ldy #2
        lda sd_bh,x
        sta (sm_cp),y
        ldy #9
        sta (sm_cp),y
        ldy #3
        lda #$29
        sta (sm_cp),y
        iny
        lda sm_k
        eor #$ff
        sta (sm_cp),y
        iny
        lda #$09
        sta (sm_cp),y
        iny
        lda sm_role
        and sm_k
        sta (sm_cp),y
        lda sm_cp
        clc
        adc #10
        sta sm_cp
        bcc _nb
        inc sm_cp+1
_nb     inc sm_b
        lda sm_b
        cmp #SMOKE_W
        bcs _nr
        jmp _byte
_nr     inc sm_y
        inc sm_r
        lda sm_r
        cmp #SMOKE_H
        bcs _np
        jmp _row
_np     ldx sm_i
        dex
        bmi +
        jmp _p
+       rts

sm_div5 .byte range(LIFE) / 5
sm_mlo  .byte <(smk_mask + range(SMOKE_NS * 2) * SMOKE_H * SMOKE_W)
sm_mhi  .byte >(smk_mask + range(SMOKE_NS * 2) * SMOKE_H * SMOKE_W)
sm_rowc .byte range(0, SMOKE_R1 * (SMOKE_C1 - SMOKE_C0), SMOKE_C1 - SMOKE_C0)
sm_blo  .byte <(320 * range(SMOKE_R1))
sm_bhi  .byte >(320 * range(SMOKE_R1))
sm_bank .for k := 0, k < LAYOUTS, k += 1
        .byte (k & 1) ? >BANK3_BMP : >BANK2_BMP     ; asettelut vuorottelevat pankeissa 2 ja 3
        .next
sm_vy   .byte range(250, 250 - 5 * LIFE, -5)   ; nousu 8.8 riviä per päivitys iän mukaan
sm_vx   .byte range(30, 30 + 4 * LIFE, 4)      ; tuuli kiihtyy ylempänä
sm_last .byte 0
sm_cnt  .byte 0                 ; mittaus: ajetut päivitykset
sm_ready .byte 0                ; päivityksen koodi valmis, sm_apply ajaa
sm_lay  .byte 0                 ; asettelu, jolle palautuslista ja koodi on tehty
sm_tmr  .byte 0
sm_src  .byte 0
sm_nd   .byte 0
sm_i    .byte 0
sm_dk   .byte 0
sm_t    .byte 0
sm_x    .byte 0
sm_y    .byte 0
sm_cx   .byte 0
sm_cy   .byte 0
sm_r    .byte 0
sm_b    .byte 0
sm_m    .byte 0
sm_o    .byte 0
sm_k    .byte 0
sm_ri   .byte 0
sm_role .byte 0
pf_xl   .fill NPUFF, 0
pf_xh   .fill NPUFF, 0
pf_yl   .fill NPUFF, 0
pf_yh   .fill NPUFF, 0
pf_age  .fill NPUFF, LIFE
sd_rl   .fill NDIRTY
sd_rh   .fill NDIRTY
sd_bl   .fill NDIRTY
sd_bh   .fill NDIRTY
