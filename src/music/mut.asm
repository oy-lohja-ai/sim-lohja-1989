; Soittimen muuttuvat tavut (music.py mut): soittaa biisin (luuppaavasta yhden luupin yli) ja merkitsee binäärin
; tavut, jotka joskus eroavat alkuperäisestä. Levynvaihdon tahtisilmukka (src/runko/levynvaihto.asm) tallentaa nämä.
        .include "music.inc"
N       = MUSIC_END - MUSIC_LOAD
NP      = (N + 255) / 256
FR      = 2 * MUSIC_LOOP_FRAMES - MUSIC_LOOP_TO + 60
PRIS    = $4000
MASK    = $6000
        .cerror MUSIC_BUF_END > PRIS || PRIS + NP * 256 > MASK

        * = $0801
        .word +, 2026
        .null $9e, format("%d", start)
+       .word 0

        * = MUSIC_LOAD
        .binary "music.bin"

        * = MUSIC_BUF_END
start   sei
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda #$0b
        sta $d011
        ldx #0
-       .for p := 0, p < NP, p += 1
        lda MUSIC_LOAD + p * 256,x
        sta PRIS + p * 256,x
        lda #0
        sta MASK + p * 256,x
        .endfor
        inx
        bne -
        lda #0
        jsr MUSIC_INIT
loop    jsr MUSIC_PLAY
        ldx #0
-       .for p := 0, p < NP, p += 1
        lda MUSIC_LOAD + p * 256,x
        cmp PRIS + p * 256,x
        beq +
        lda #1
        sta MASK + p * 256,x
+
        .endfor
        inx
        bne -
        inc cnt
        bne +
        inc cnt+1
+       lda cnt
        cmp #<FR
        lda cnt+1
        sbc #>FR
        bcc loop
halt    .byte $02               ; JAM: VICE:n -initbreak
cnt     .word 0
        .virtual MASK
mask    .fill N
mask_end
        .endv
