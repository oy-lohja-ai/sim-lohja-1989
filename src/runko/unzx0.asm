; ZX0 (dalin muoto, tools/disk/zx0.py) muistista paikallaan: bootin itsepurku ja osien muistipurku.
; Krillin loadcompd purkaa saman muodon latauksen aikana; tämä on oma toteutus samasta virrasta muistiin.
; Sisään: X/Y = pakatun datan alku (purkuosoitteen hi-tavu), pakattu data päättyy purun loppuun.
; Nollasivu: UZ..UZ+11. Y = 0 kopioiden välissä.

uz_src  = UZ                    ; luku
uz_dst  = UZ + 2                ; kirjoitus
uz_rep  = UZ + 4                ; offset - 1
uz_bits = UZ + 6                ; bittipuskuri, ylin ykkönen merkkinä
uz_tmp  = UZ + 7
uz_m    = UZ + 8                ; ottelun lähde
uz_n    = UZ + 10               ; laskuri

unzx0   stx uz_src
        sty uz_src+1
        ldy #0
        jsr uz_byte
        sta uz_dst+1
        jsr uz_byte
        sta uz_dst
        sty uz_rep
        sty uz_rep+1
        lda #1
        sta uz_bits
uz_lit  jsr uz_elias            ; literaali: X:A tavua lähteestä
        jsr uz_cnt
        lda uz_src
        sta uz_m
        lda uz_src+1
        sta uz_m+1
        jsr uz_move
        lda uz_m
        sta uz_src
        lda uz_m+1
        sta uz_src+1
        jsr uz_bit
        bcs uz_new
        jsr uz_elias            ; toisto viimeisellä offsetilla
        jsr uz_copy
        beq uz_done
        jsr uz_bit
        bcc uz_lit
uz_new  jsr uz_elias            ; uusi offset: ((hi - 1) << 7 | tavu >> 1), tavun bitti 0 = pituus 2
        sbc #1                  ; C = 1 (Eliaksen loppubitti)
        lsr a
        sta uz_rep+1
        jsr uz_byte
        ror a
        sta uz_rep
        lda #2
        ldx #0
        bcs +
        jsr uz_elias_s
        clc
        adc #1
        bcc +
        inx
+       jsr uz_copy
        beq uz_done
        jsr uz_bit
        bcs uz_new
        bcc uz_lit
uz_done rts

uz_copy jsr uz_cnt              ; X:A tavua osoitteesta dst - rep - 1; Z = 1, jos dst == src (loppu)
        clc
        lda uz_dst
        sbc uz_rep
        sta uz_m
        lda uz_dst+1
        sbc uz_rep+1
        sta uz_m+1
        jsr uz_move
        lda uz_dst
        cmp uz_src
        bne +
        lda uz_dst+1
        cmp uz_src+1
+       rts

uz_cnt  sta uz_n                ; laskuri X:A
        stx uz_n+1
        rts

uz_move ldx uz_n                ; uz_n tavua (m) -> (dst), molemmat etenevät; noin 19 sykliä tavulta, Y = 0 lopuksi
        beq uz_mp
-       lda (uz_m),y            ; ensin alle sivun osa
        sta (uz_dst),y
        iny
        dex
        bne -
        tya
        clc
        adc uz_m
        sta uz_m
        bcc +
        inc uz_m+1
+       tya
        clc
        adc uz_dst
        sta uz_dst
        bcc uz_mp
        inc uz_dst+1
uz_mp   ldx uz_n+1              ; sitten kokonaiset sivut
        beq uz_md
        ldy #0
-       lda (uz_m),y
        sta (uz_dst),y
        iny
        bne -
        inc uz_m+1
        inc uz_dst+1
        dex
        bne -
uz_md   ldy #0
        rts

UZBIT   .macro                  ; bitti C:hen, A säilyy (uz_bit ilman jsr:ää)
        lsr uz_bits
        bne *+5
        jsr uz_fill
        .endm

uz_elias lda #1                 ; Eliaksen lomitettu gamma -> X:A; yli 8 databittiä: alatavu ensin
-       #UZBIT
        bcs uz_e8
uz_ed   #UZBIT
        rol a
        bcc -
        sta uz_tmp
        lda #1
-       #UZBIT
        bcs +
        #UZBIT
        rol a
        jmp -
+       tax
        lda uz_tmp
        rts
uz_e8   ldx #0
        rts
uz_elias_s lda #1               ; ensimmäinen ohjausbitti oli offset-tavussa
        jmp uz_ed

uz_bit  lsr uz_bits             ; bitti C:hen, A säilyy
        beq uz_fill
        rts
uz_fill pha                     ; puskuri tyhjä: uusi tavu, ylin bitti merkiksi
        jsr uz_byte
        sec
        ror a
        sta uz_bits
        pla
        rts

uz_byte lda (uz_src),y
        inc uz_src
        bne +
        inc uz_src+1
+       rts

