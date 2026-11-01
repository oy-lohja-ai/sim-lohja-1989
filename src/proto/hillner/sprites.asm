; Spritet vuorollaan samoilla spriteillä ja lohkoilla 0-4 (build.py kv_check varmistaa, etteivät ne ole ruudulla
; yhtä aikaa): alussa taustarivistö (talot 0-2 ja kirkko 3-4 bittikartan takana), sitten pääskyset (0-2), lopuksi
; katuvalo (spritet 0 - 1 + KV_NB), joten multiplekseriä ei tarvita. Kehyksen N lopussa (irq_bot) spr_frame laskee kehyksen N+1 rekisterit varjoon ja
; spr_apply kirjoittaa ne (valmis ennen riviä 73). Taivasriveillä saa olla vain spritejä 0-2 (DMA edellisen rivin
; lopussa) ja kirkko 3-4 (DMA päättyy syklissä 4).

SPR_TOP = 73
SPR_BOT = 215

SPR_N   = 2 + KV_NB > 5 ? 2 + KV_NB : 5      ; käytetyt spritet

spr_frame
        lda #0
        sta sp_en
        sta sp_010
        sta chb
        sta sp_xx
        sta sp_yx
        jsr pole                ; C = 1: katuvalo ruudulla (rivistö ja pääskyset ovat silloin poissa)
        bcs +
        jsr swallows
        jsr strip
+
; kirkon rivit taivassilmukalle (d21late): edellisen kehyksen 21 riviä pois, uudet tilalle
        ldx ch_r0
        beq +
        ldy #21
        lda #0
-       sta d21late,x
        inx
        dey
        bne -
+       ldx #0
        lda chb
        and #$08                ; kirkko (sprite 3) näkyy
        beq +
        ldx sp_y + 3            ; ensimmäinen rivi = Y-rekisteri + 1
        inx
        ldy #21
        lda #1
-       sta d21late,x
        inx
        dey
        bne -
        ldx sp_y + 3
        inx
+       stx ch_r0
        rts

spr_apply
        ldx #SPR_N - 1
-       lda sp_ptr,x
        sta BANK2_SCR + $3f8,x
        sta BANK3_SCR + $3f8,x
        lda sp_col,x
        sta $d027,x
        dex
        bpl -
        ldx #2 * (SPR_N - 1)
        ldy #SPR_N - 1
-       lda sp_x,y
        sta $d000,x
        lda sp_y,y
        sta $d001,x
        dex
        dex
        dey
        bpl -
        lda sp_010
        sta $d010
        lda #(1 << SPR_N) - 1   ; kaikki MC
        sta $d01c
        lda sp_xx
        sta $d01d
        lda sp_yx
        sta $d017
        lda chb
        sta $d01b
        lda sp_en
        sta $d015
        rts

; ---------------------------------------------------------------- pääskyset
; Lentävät kattojen ja antennien ympärillä kameran lähtiessä: x tasaisella nopeudella sivulta
; sivulle, y kuvan rivillä (liikkuu talon mukana) + pieni aalto, siivet 4 kehyksen välein.
swallows                        ; oma kello swf = frame - SW_F0 (0-255), lohkot 0-2 kopioidaan ensimmäisellä kehyksellä
        sec
        lda frame
        sbc #<SW_F0
        sta swf
        lda frame+1
        sbc #>SW_F0
        beq +
        rts
+       lda sw_init
        bne +
        inc sw_init
        ldy #3 * 64 - 1
-       lda sw_blk,y
        sta KVBLK2,y
        sta KVBLK3,y
        dey
        cpy #$ff
        bne -
+       ldx #0
_sw     stx cn
        lda swf
        cmp sw_t0,x
        bcc _swn
        bne _mv
        lda sw_x0lo,x
        sta sw_xlo,x
        lda sw_x0hi,x
        sta sw_xhi,x
        jmp _pos
_mv     lda sw_dx,x
        clc
        adc sw_xlo,x
        sta sw_xlo,x
        lda sw_dx,x
        and #$80
        beq +
        lda #$ff
+       adc sw_xhi,x
        sta sw_xhi,x
_pos    lda sw_xhi,x            ; X = x >> 4, näkyvä 1..343
        bmi _swn
        sta swx+1
        lda sw_xlo,x
        lsr swx+1
        ror a
        lsr swx+1
        ror a
        lsr swx+1
        ror a
        lsr swx+1
        ror a
        sta swx
        ldy swx+1
        bne +
        cmp #0
        beq _swn
        bne _y
+       cmp #<344
        bcs _swn
_y      lda swf                 ; y = 72 + rivi - ppx + aalto
        lsr a
        lsr a
        clc
        adc sw_ph,x
        and #15
        tay
        lda bob,y
        clc
        adc sw_row,x
        sta s16
        lda #0
        adc #0
        sta s16+1
        lda s16
        clc
        adc #T_LINE
        sta s16
        bcc +
        inc s16+1
+       sec
        lda s16
        sbc ppx
        sta s16
        lda s16+1
        sbc ppx+1
        bne _swn
        lda s16
        cmp #SPR_TOP
        bcc _swn
        cmp #SPR_BOT - 20
        bcs _swn
        sbc #0                  ; C = 0: Y-rekisteri = ensimmäinen rivi - 1
        sta sp_y,x
        lda swx
        sta sp_x,x
        lda swx+1
        beq +
        lda bit_t,x
        ora sp_010
        sta sp_010
+       lda bit_t,x
        ora sp_en
        sta sp_en
        lda #6
        sta sp_col,x
        lda frame
        lsr a
        lsr a
        clc
        adc sw_ph,x
        and #3
        tay
        lda wing,y
        clc
        adc #SPR_PTR0 + BLK_SW
        sta sp_ptr,x
_swn    ldx cn
        inx
        cpx #N_SW
        bcs +
        jmp _sw
+       rts
wing    .byte 0, 1, 2, 1
bob     .byte 3, 4, 5, 5, 6, 5, 5, 4, 3, 2, 1, 1, 0, 1, 1, 2   ; +3 (sw_row on rivi - 3)

; ---------------------------------------------------------------- katuvalo
; Talon edessä 1,5 x julkisivun nopeudella: pään A ensimmäinen rivi = KV_Y0 + d + d / 2, d = P_MAX - ppx.
; Ensimmäisellä näkyvällä kehyksellä lohkot kv_blk pääskysten ja kirkon lohkoihin 0-2 molempiin pankkeihin.
; Pää rivin KV_BOT alla: lohko 3 (A) tai 4 (B) on pää siirrettynä alas, sprite rivillä KV_BOT (ei yli rivin 214).
; Runko: spritet 2.. riveillä KV_BOT, KV_BOT - 21, ..., vain pään yläreunasta alaspäin. Palauttaa C = 1, kun näkyy.
KVBLK2  = BANK2_SCR + SPR_BASE
KVBLK3  = BANK3_SCR + SPR_BASE

pole    lda #P_MAX
        sec
        sbc ppx
        sta s16
        lsr a
        clc
        adc s16
        bcs _off
        adc #KV_Y0
        bcs _off
        cmp #KV_BOT + 21
        bcc _on
_off    clc
        rts
_on     sta cn                  ; pään A ensimmäinen rivi
        lda kv_init
        bne +
        inc kv_init
        ldy #3 * 64 - 1
-       lda kv_blk,y
        sta KVBLK2,y
        sta KVBLK3,y
        dey
        cpy #$ff
        bne -
+       ldx #0                  ; pää A: sprite 0
        lda cn
        jsr _head
        lda cn                  ; pää B: sprite 1, KV_DB riviä alempana (voi olla negatiivinen)
        clc
        adc #KV_DB & $ff
        cmp #KV_BOT + 21
        bcs +
        ldx #1
        jsr _head
+       lda #<KV_X
        sta sp_x
        lda #<KV_XB
        sta sp_x + 1
        lda #KV_CA
        sta sp_col
        lda #KV_CB
        sta sp_col + 1
        ldx #KV_NB - 1          ; runko alhaalta: rivi KV_BOT - 21 * k, kun >= pään yläreuna
        lda #KV_BOT - 1
-       sta s16
        cmp cn                  ; Y-rekisteri = rivi - 1 >= pään rivi - 1
        bcc _nb
        sta sp_y + 2,x
        lda #<KV_X
        sta sp_x + 2,x
        lda #KV_CC
        sta sp_col + 2,x
        lda #SPR_PTR0 + 2
        sta sp_ptr + 2,x
        lda sp_en
        ora bit_k + 2,x
        sta sp_en
_nb     lda s16
        sec
        sbc #21
        dex
        bpl -
        lda sp_010
        ora #KV_010
        sta sp_010
        sec
        rts

_head   cmp #KV_BOT + 1         ; X = sprite (0 = A, 1 = B), A = ensimmäinen rivi
        bcs _clip
        sbc #0                  ; C = 0: Y-rekisteri = rivi - 1
        sta sp_y,x
        txa
        clc
        adc #SPR_PTR0
        bne _hon
_clip   sbc #KV_BOT             ; C = 1: siirto riveinä 1..20, tavuina 3 *
        sta s16+1
        asl a
        adc s16+1
        sta s16+1
        lda #KV_BOT - 1
        sta sp_y,x
        txa
        bne _cb
        #kvclip kv_blk, 3
        ldx #0
        lda #SPR_PTR0 + 3
        bne _hon
_cb     #kvclip kv_blk + 64, 4
        ldx #1
        lda #SPR_PTR0 + 4
_hon    sta sp_ptr,x
        lda sp_en
        ora bit_k,x
        sta sp_en
        rts

kvclip  .macro src, blk         ; lohko \blk = lähde siirrettynä s16+1 tavua alas (ylärivit tyhjiksi)
        ldy #62
_l      tya
        sec
        sbc s16+1
        bcc _z
        tax
        lda \src,x
        bcs _w                  ; C = 1 (sbc ilman lainausta)
_z      lda #0
_w      sta KVBLK2 + \blk * 64,y
        sta KVBLK3 + \blk * 64,y
        dey
        bpl _l
        .endm

; ---------------------------------------------------------------- taustarivistö
; Talot (0-2, X- ja Y-laajennus) ja Pyhän Laurin kirkko (3-4) kaukaisessa kerroksessa bittikartan takana ($d01b),
; rivi kamera-ajon kohdan mukaan (rv_y: 5 tavua per kohta ppx >> 3, $ff = piilossa), X ja värit vakioita.
strip   lda ppx
        lsr a
        lsr a
        lsr a
        cmp #RV_N
        bcs _x
        sta cn
        asl a
        asl a
        adc cn                  ; C = 0 (kohta < 64): 5 * kohta
        tay
        ldx #0
_k      lda rv_y,y
        cmp #$ff
        beq _n
        adc #T_LINE - 1         ; C = 0 (cmp: A < $ff): Y-rekisteri = ensimmäinen rivi - 1
        sta sp_y,x
        lda rv_x,x
        sta sp_x,x
        lda rv_c,x
        sta sp_col,x
        txa
        clc
        adc #SPR_PTR0
        sta sp_ptr,x
        lda sp_en
        ora bit_k,x
        sta sp_en
        lda chb
        ora bit_k,x
        sta chb
        lda sp_010
        ora rv_hi,x
        sta sp_010
        lda sp_xx
        ora rv_xx,x
        sta sp_xx
        lda sp_yx
        ora rv_yx,x
        sta sp_yx
_n      iny
        inx
        cpx #5
        bne _k
_x      rts

bit_t   .byte $01, $02, $04, $08, $10
sp_x    .fill SPR_N, 0          ; rekisterit kehykselle N+1 (spr_apply)
sp_y    .fill SPR_N, 0
sp_col  .fill SPR_N, 0
sp_ptr  .fill SPR_N, SPR_PTR0
sp_010  .byte 0
sp_en   .byte 0
kv_init .byte 0                 ; katuvalon lohkot kopioitu
bit_k   .byte $01, $02, $04, $08, $10, $20, $40, $80
chb     .byte 0                 ; $d01b: taustarivistö bittikartan takana
sp_xx   .byte 0                 ; $d01d
sp_yx   .byte 0                 ; $d017
ch_r0   .byte 0                 ; kirkon ensimmäinen rivi d21latessa (0 = ei)
swf     .byte 0                 ; pääskysten kello
sw_init .byte 0                 ; pääskysten lohkot kopioitu
sw_xlo  .fill N_SW
sw_xhi  .fill N_SW
