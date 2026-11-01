; Kamera-ajo (kamera.asm): alustus ja IRQ-tason listan vaihto. Näytön taulujen perässä (KT2).

; kam_init (kt_init): tilat alkuun ja palkkien lohkot (kam_gen)
kam_init
        lda #1
        sta kam_on
        lda #$ff
        sta kam_ready
        sta kam_ready+1
        lda #<KAM_S0                    ; s kehyksessä 0 (kam_sfr = 0)
        sta kam_sf
        lda #>KAM_S0
        sta kam_si
        lda #<kam_rev_lo
        sta kam_rp
        lda #>kam_rev_lo
        sta kam_rp+1
        lda #<kam_rev_hi
        sta kam_hp
        lda #>kam_rev_hi
        sta kam_hp+1
        .if KAM_TA
        jsr kam_gen
        lda #0                          ; vaihtoehto: kehys 0 valmiiksi puskuriin 0 (lista ja maskit ensimmäiseen kuvaan)
        sta kam_c
        sta kam_c+1
        jmp kam_compute
        .else
        jmp kam_gen
        .endif

; kam_apply: puskurin kam_db rekisterit ja ensimmäiset kopiot (multipleksaus etenee kam_idx:stä). IRQ-tasolla.
kam_apply
        ldx kam_db
        lda kb_d010,x
        sta $d010
        lda kb_d01d,x
        sta $d01d
        lda kb_d017,x
        sta $d017
        lda kb_d015,x
        sta $d015
        lda #0                          ; ka_t0 = listan alku (puskuri * 48 + kanava * 6), ka_t1 = kb_cnt-indeksi
        cpx #0
        beq +
        lda #48
+       sta ka_t0
        txa
        asl a
        asl a
        asl a
        sta ka_t1
        ldx #0
-       lda ka_t0
        sta kam_idx,x
        ldy ka_t1
        lda kb_cnt,y
        beq _z
        clc
        adc ka_t0
        sbc #0                          ; C = 0: viimeinen = alku + määrä - 1
        sta kam_end,x
        ldy ka_t0
        lda kb_p,y
        sta KAM_SCREEN+$3f8,x
        txa
        asl a
        sta ka_t2
        lda kb_y,y
        pha
        lda kb_x,y
        ldy ka_t2
        sta $d000,y
        pla
        sta $d001,y
        jmp _n
_z      lda ka_t0
        sta kam_end,x
_n      lda ka_t0
        clc
        adc #6
        sta ka_t0
        inc ka_t1
        inx
        cpx #8
        bne -
        .if KAM_TA
        jmp kam_ra_apply                ; vaihtoehto: värit, yläreunan tila ja lista
        .else
        rts
        .endif
