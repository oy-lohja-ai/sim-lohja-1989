; Kylttien pudotus (moduuli): ryhmälogot putoavat spriteinä paikalleen MC-bittikarttaan, pomppaavat, siirtyvät
; bittikarttaan sammuneina ja syttyvät neonputken välkkeellä; lähtiessä ne lentävät palavina spriteinä ylös kuvasta
; (lennon vaiheet ovat kylttejä, joilla on vain spritet ja Y-taulu) ja paikka bittikartassa vaihtuu tilaan tyhjä.
; Data ja tapahtumataulu: src/lib/kylttipudotus.py (rakenna -> kp_*-symbolit).
;
; Isäntä määrittelee ennen .includea:
;   KP_SCREEN   näkyvä ruutu (spriteosoittimet +$3f8, kylttien värit)
;   KP_BITMAP   näkyvä MC-bittikartta
;   KP_SPRBUF   spritepuskuri VIC-pankissa (64:llä jaollinen, KP_NSPR * 64 tavua)
;   KP_SPR0     ensimmäinen moduulin sprite (spritet KP_SPR0 .. KP_SPR0 + KP_NSPR - 1)
;   KP_ZP       nollasivu, 14 tavua
;   KP_TAKANA   (valinnainen, oletus 0) 1 = pudotuksen alussa spritet bittikartan taakse ($d01b), kun isäntä tuo ne
;               eteen itse kuvan alussa (kuoppa: letterbox, kp4_spl); 0 = eteen
; ja ottaa mukaan buildin tuottaman datan (KP_NSPR ym.). Kutsut:
;   kp_init     tila alkuun (ei VIC-rekistereitä)
;   kp_frame    A = kehys lo, X = hi (seuraavaksi näytettävä kehys): kerran kehyksessä näkyvän kuvan jälkeen
;               (esim. IRQ rivillä 250). Putoavan kyltin spritet tähän kehykseen, sitten kehyksen tapahtumat.
; Reunaväriin ($d020) ja $d021:een moduuli ei koske.

        .weak
KP_TAKANA = 0
        .endweak

        .virtual KP_ZP
kp_f    .word ?                 ; kehys
kp_e    .word ?                 ; tapahtumataulun osoitin
kp_p    .word ?                 ; kopion lähde
kp_d    .word ?                 ; kopion kohde
kp_s0   .byte ?                 ; vapaa (putoava kyltti on kp_fl:ssä)
kp_s1   .word ?
kp_x    .byte ?                 ; käsiteltävä kyltti
kp_n    .byte ?                 ; kp_rect: tavuja riviltä
kp_r    .byte ?                 ; kp_rect: rivejä; kp_sprites: Y
        .endv

kp_init
        lda #<kp_ev
        sta kp_e
        lda #>kp_ev
        sta kp_e+1
        lda #$ff
        sta kp_fl
        sta kp_fl+1
        rts

; Kaksi spritepaikkaa (useampi logo lähtee samaan aikaan): pudotus ja paikan 0 lento
; spritet KP_SPR0 + kp_sb (kyltin taulut kp_sb, kp_ns, kp_mk), paikan 1 lento kp_sb = 4; kyltin kp_slot.
kp_fl   .byte $ff, $ff          ; paikan kyltti tai $ff (paikka 0 = pudotus tai lento)
kp_fsl  .byte 0, 0              ; sen alkukehys
kp_fsh  .byte 0, 0
kp_hw   .byte 0                 ; silmukat: laitteistosprite (KP_SPR0:sta), kp_sx-indeksi, jäljellä
kp_ix   .byte 0
kp_cn   .byte 0
kp_sl   .byte 0

kp_frame
        sta kp_f
        stx kp_f+1
        jsr kp_sprites
_ev     ldy #0                  ; tapahtuma: kehys (16 b), kyltti, tyyppi; ajetaan kun kehys <= kp_f
        lda kp_f
        cmp (kp_e),y
        iny
        lda kp_f+1
        sbc (kp_e),y
        bcc _rts                ; tapahtuman kehys > kp_f (loppumerkki $ffff)
        iny
        lda (kp_e),y
        tax
        iny
        lda (kp_e),y
        jsr kp_do
        lda kp_e
        clc
        adc #4
        sta kp_e
        bcc _ev
        inc kp_e+1
        jmp _ev
_rts    rts

; kp_do: X = kyltti, A = tyyppi (0 pudotus tai lennon vaihe: spritet, 1 bittikarttaan, 2 + tila, $80 julkisivu)
kp_do   stx kp_x
        cmp #$80
        beq kp_julki
        cmp #1
        bcc kp_drop
        beq kp_land
        sbc #2                  ; C = 1
        clc                     ; tilan data kp_st[kp_stb[kyltti] + tila]
        adc kp_stb,x
        tax
        lda kp_st_lo,x
        sta kp_p
        lda kp_st_hi,x
        sta kp_p+1
        jmp kp_colours

; kp_julki: lähteneen kyltin paikalle rakennuksen julkisivu (rakennuksen muoto ilman logojen
; roskia): solukartta kp_jb (solun numero riveittäin) erillisistä soluista (KP_JC_N ensimmäistä osoitteesta KP_JC_A,
; loput KP_JC_B:stä, 8 t kukin) bittikarttaan, värit tilana 4. Solut jaetaan kylttien kesken (sama solu kerran).
kp_julki
        lda kp_jb_lo,x
        sta _map+1
        lda kp_jb_hi,x
        sta _map+2
        jsr kp_dbmp
        ldx kp_x
        lda kp_h,x
        sta kp_r
        lda #0
        sta _mi+1
_row    ldx kp_x
        lda kp_w,x
        sta kp_n
        ldy #0
_cell   sty _yy+1
_mi     ldx #0
_map    lda $ffff,x
        inc _mi+1
        ldx #0                  ; osoite = alku + 8 * numero
        stx _src+2
        cmp #KP_JC_N
        bcc +
        sbc #KP_JC_N
        ldx #1
+       asl
        rol _src+2
        asl
        rol _src+2
        asl
        rol _src+2
        clc
        adc _jcl,x
        sta _src+1
        lda _src+2
        adc _jch,x
        sta _src+2
        ldx #0
_yy     ldy #0
_src    lda $ffff,x
        sta (kp_d),y
        iny
        inx
        cpx #8
        bne _src
        dec kp_n
        bne _cell
        lda kp_d
        clc
        adc #<320
        sta kp_d
        lda kp_d+1
        adc #>320
        sta kp_d+1
        dec kp_r
        bne _row
        ldx kp_x
        lda kp_stb,x
        clc
        adc #4
        tax
        jmp kp_stcol
_jcl    .byte <KP_JC_A, <KP_JC_B
_jch    .byte >KP_JC_A, >KP_JC_B

; kp_land: kyltti bittikarttaan ja sammuneen värit (spritet peittävät kyltin vielä tämän kehyksen)
kp_land lda kp_bmp_lo,x
        sta kp_p
        lda kp_bmp_hi,x
        sta kp_p+1
        jsr kp_bcopy
        ldx kp_x                ; sammunut = tila 0
        lda kp_stb,x
        tax
kp_stcol
        lda kp_st_lo,x
        sta kp_p
        lda kp_st_hi,x
        sta kp_p+1
        jmp kp_colours

; kp_bcopy: kp_p = bittikartta kyltin kp_x suorakaiteeseen
kp_bcopy
        jsr kp_dbmp
        lda kp_w,x
        asl
        asl
        asl
        sta kp_n
        lda kp_h,x
        ldy #<320
        ldx #>320
        jmp kp_rect
; kp_dbmp: kp_d = kyltin kp_x suorakaide bittikartassa, X = kp_x
kp_dbmp ldx kp_x
        lda kp_boff_lo,x
        clc
        adc #<KP_BITMAP
        sta kp_d
        lda kp_boff_hi,x
        adc #>KP_BITMAP
        sta kp_d+1
        rts

; kp_colours: kp_p = tilan data (ruutu h*w, värimuisti h*w) kyltille kp_x
kp_colours
        ldx kp_x
        lda kp_soff_lo,x
        clc
        adc #<KP_SCREEN
        sta kp_d
        lda kp_soff_hi,x
        adc #>KP_SCREEN
        sta kp_d+1
        jsr _rows
        ldx kp_x
        lda kp_soff_lo,x
        clc
        adc #<$d800
        sta kp_d
        lda kp_soff_hi,x
        adc #>$d800
        sta kp_d+1
_rows   ldx kp_x
        lda kp_w,x
        sta kp_n
        lda kp_h,x
        ldy #40
        ldx #0
; kp_rect: A riviä, kp_n tavua riviltä (enintään 128) kp_p:stä (jatkuu) kp_d:hen, rivin askel Y lo, X hi
kp_rect sta kp_r
        sty _slo+1
        stx _shi+1
_row    ldy kp_n
        dey
-       lda (kp_p),y
        sta (kp_d),y
        dey
        bpl -
        lda kp_p
        clc
        adc kp_n
        sta kp_p
        bcc +
        inc kp_p+1
+       lda kp_d
        clc
_slo    adc #0
        sta kp_d
        lda kp_d+1
_shi    adc #0
        sta kp_d+1
        dec kp_r
        bne _row
        rts

; kp_drop: kyltin X spritet puskuriin (KP_SPRBUF + 64 * kp_sb), rekisterit (X, osoittimet, värit, laajennus, MC,
; edessä) sen spriteille, pudotus tai lento alkaa sen paikassa kp_slot
kp_drop lda $d015                ; spritet pois kopion ajaksi: edellisen lennon Y näyttäisi uuden kuvan vanhassa
        and kp_mkn,x            ; paikassa (letterboxissa) kehyksen ajan
        sta $d015
        lda kp_spr_lo,x
        sta kp_p
        lda kp_spr_hi,x
        sta kp_p+1
        lda kp_sb,x             ; 0 tai 4: puskurin sivu + 1
        lsr a
        lsr a
        clc
        adc #>KP_SPRBUF
        sta kp_d+1
        lda #<KP_SPRBUF
        sta kp_d
        lda #64
        sta kp_n
        lda kp_ns,x             ; vain käytetyt spritet (lennon vaihe vaihtuu kuvan päällä: kopio ennen sädettä)
        ldy #64
        ldx #0
        jsr kp_rect
        ldx kp_x
        lda kp_sb,x
        sta kp_hw
        lda kp_ib,x
        sta kp_ix
        lda kp_ns,x
        sta kp_cn
_dl     ldy kp_ix
        lda kp_hw
        asl a
        tax
        lda kp_sx,y
        sta $d000 + 2 * KP_SPR0,x
        ldx kp_hw
        txa
        clc
        adc #(KP_SPRBUF & $3fff) >> 6
        sta KP_SCREEN + $3f8 + KP_SPR0,x
        ldy kp_x
        lda kp_col,y
        sta $d027 + KP_SPR0,x
        inc kp_hw
        inc kp_ix
        dec kp_cn
        bne _dl
        ldx kp_x
        lda #0
        sta $d025
        lda kp_c26,x
        sta $d026
        lda $d010
        and kp_mkn,x
        ora kp_d010,x
        sta $d010
        lda $d017
        and kp_mkn,x
        ora kp_ye,x
        sta $d017
        lda $d01d
        and kp_mkn,x
        ora kp_xe,x
        sta $d01d
        lda $d01c
        ora kp_mk,x
        sta $d01c
        lda $d01b
        .if KP_TAKANA
        ora kp_mk,x
        .else
        and kp_mkn,x
        .endif
        sta $d01b
        ldy kp_slot,x
        txa
        sta kp_fl,y
        lda kp_f
        sta kp_fsl,y
        lda kp_f+1
        sta kp_fsh,y
; kp_sprites: molempien paikkojen spritejen Y kehykselle kp_f (Y-taulu kehyksestä kp_f - alkukehys), lopussa pois
kp_sprites
        ldy #0
        jsr _one
        ldy #1
_one    ldx kp_fl,y
        bmi _rts
        sty kp_sl
        lda kp_f
        sec
        sbc kp_fsl,y
        sta kp_r
        lda kp_f+1
        sbc kp_fsh,y
        bne _off
        lda kp_r
        cmp kp_ny,x             ; Y-taulun pituus kyltittäin (pudotuksen kesto)
        bcs _off
        tay
        lda kp_ytab_lo,x
        sta kp_p
        lda kp_ytab_hi,x
        sta kp_p+1
        lda (kp_p),y
        sta kp_r
        lda kp_sb,x
        sta kp_hw
        lda kp_ib,x
        sta kp_ix
        lda kp_ns,x
        sta kp_cn
_yl     ldy kp_ix
        lda kp_r
        clc
        adc kp_yo,y
        pha
        lda kp_hw
        asl a
        tay
        pla
        sta $d001 + 2 * KP_SPR0,y
        inc kp_hw
        inc kp_ix
        dec kp_cn
        bne _yl
        lda $d015
        and kp_mkn,x
        ora kp_en,x
        sta $d015
_rts    rts
_off    lda $d015
        and kp_mkn,x
        sta $d015
        ldy kp_sl
        lda #$ff
        sta kp_fl,y
        rts
