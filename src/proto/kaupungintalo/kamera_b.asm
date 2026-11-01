; Kamera-ajo (kamera.asm): solun kopio ja multipleksausrivit. KT2:n lopussa ($bf40-).

; kam_cell: seuraava paljastettava solu (kam_rev_lo[kam_rp], yläbitit kam_rev_hi:ssä 4 solua tavussa) seinäksi:
; bittikartan pikselit %11 ja väri KAM_SEINA (kam_odota: ei kesken säteen)
kam_cell
        ldy #0
        lda (kam_rp),y                  ; solun alatavu
        inc kam_rp
        bne +
        inc kam_rp+1
+       tay
        lda kam_hc                      ; yläbitit: uusi tavu joka neljäs solu
        bne +
        lda #4
        sta kam_hc
        ldx #0
        lda (kam_hp,x)
        sta kam_hb
        inc kam_hp
        bne +
        inc kam_hp+1
+       dec kam_hc
        lda kam_hb
        and #3
        tax                             ; X = solun yläbitit (0..3)
        lsr kam_hb
        lsr kam_hb
        txa                             ; väri: sivu + X, Y = alatavu
        clc
        adc #$d8
        sta _d2+2
        tya                             ; bittikartta: 8 * (X * 256 + Y)
        asl a
        asl a
        asl a
        sta _d3+1
        tya
        lsr a
        lsr a
        lsr a
        lsr a
        lsr a
        sta kam_t2
        txa
        asl a
        asl a
        asl a
        ora kam_t2
        tax
        ora #>KAM_BITMAP
        sta _d3+2
        txa
        jsr kam_odota                   ; ei säteen alla
        lda #KAM_SEINA
_d2     sta $d800,y
        ldy #7
        lda #$ff
_d3     sta $ffff,y
        dey
        bpl _d3
        rts

mux_line
        .for k = 0, k < MUX_N, k += 1
        .byte MUX0 + k * MUX_DY
        .next

