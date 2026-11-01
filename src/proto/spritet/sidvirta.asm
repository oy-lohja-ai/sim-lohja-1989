; Spritet: biisin SID-rekisterivirta hostille (sidvirta.py). Soittaa P0 kehystä hiljaa ($01 = $34, kuten
; music_seek), sitten N kehystä ja kopioi joka kehyksen jälkeen I/O:n alla olevan RAMin $d400-$d418 tauluun
; (25 t kehystä kohden). Lopuksi soittimen tila (binääri, puskuri, nollasivu) on P0 + N kehyksen kohdalla: sidvirta.py
; tallentaa sen kohtauksen lopun tilaksi. JAM `halt`: VICE tallentaa muistin ja lopettaa.

        .include "music.inc"
        .weak
P0      = 0
N       = 4
        .endweak
TAB     = $1a00                 ; taulu $1a00-$bfff (soitin on demon osoitteessa $0800, ohjelma $c000-)
        .cerror TAB + 25 * N > $c000, "N liian suuri"

        * = $0801
        .word +, 2026
        .null $9e, format("%d", start)
+       .word 0

        * = $c000
start   sei
        ldx #0                  ; soitin paikalleen (osalevyn osoite, jotta tila vastaa demoa)
-       .for _p := 0, _p < MUSIC_END - MUSIC_LOAD, _p += 256
        lda player + _p,x
        sta MUSIC_LOAD + _p,x
        .next
        inx
        bne -
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda #$0b
        sta $d011
        lda #0
        jsr MUSIC_INIT
        lda #$34
        sta $01
        lda #<P0
        sta n
        lda #>P0
        sta n+1
skip    lda n
        ora n+1
        beq skipd
        jsr MUSIC_PLAY
        lda n
        bne +
        dec n+1
+       dec n
        jmp skip
skipd   lda #<TAB
        sta ptr
        lda #>TAB
        sta ptr+1
        lda #<N
        sta n
        lda #>N
        sta n+1
rec     lda n
        ora n+1
        beq halt
        jsr MUSIC_PLAY
        ldy #24
-       lda $d400,y
        sta (ptr),y
        dey
        bpl -
        clc
        lda ptr
        adc #25
        sta ptr
        bcc +
        inc ptr+1
+       lda n
        bne +
        dec n+1
+       dec n
        jmp rec
halt    .byte $02

n       .word 0
ptr     = $fb
player  .binary "music.bin"
