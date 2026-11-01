; Biisin häivytys sisään koko demon alussa (ilman sitä biisin alku kuulostaa oudolta).
; Kelauksen (music_seek) jälkeen kutsuttava hv_on:
; SID hiljaa (kelauksen rekisterit portit päällä soivat muuten sointuna kellon alkuun asti), soittimen ainoa
; STA $D418 (MUSIC_D418_OP) muuttujaan ja FRAME_HOOKin soittimen kutsu hv_playhin. hv_play kirjoittaa SID:iin
; soittimen suotimen ja tason enintään hv_l (1..15, HV_DT kutsua tasoa kohden) ja palauttaa lopuksi soittimen ja
; FRAME_HOOKin ennalleen. Biisin ja kellon kulku ei muutu. Koodi on pinosivun alaosassa HV_AT- (mittarit
; $0100-$010e, pino $01fb:stä alas): se tarvitaan vain häivytyksen ajan, eikä runkoon tai ku_hihin mahdu tavuakaan.
; Mukana payloadissa (integraatio ilman DOSia) ja DOS-ohjelmassa (DOS_END).

HV_AT   = $0110
HV_DT   = 5                     ; 15 tasoa x 5 kehystä = 1,5 s

hv_on   ldx #hv_end - hv_img    ; kutsu keskeytykset pois, $01 = $35
-       lda hv_img - 1,x
        sta HV_AT - 1,x
        dex
        bne -
        lda #<hv_v418
        sta MUSIC_D418_OP
        lda #>hv_v418
        sta MUSIC_D418_OP+1
        lda #<hv_play
        sta FRAME_HOOK+1
        lda #>hv_play
        sta FRAME_HOOK+2
        lda #0
        sta $d418
        rts

hv_img
        .logical HV_AT
hv_play jsr MUSIC_PLAY          ; soitin kirjoitti $d418:n hv_v418:aan
        lda hv_v418
        and #15
        cmp hv_l
        bcc +
        lda hv_l
+       eor hv_v418             ; suodin ennallaan, taso enintään hv_l
        and #15
        eor hv_v418
        sta $d418
        dec hv_s
        bne +
        lda #HV_DT
        sta hv_s
        inc hv_l
        lda hv_l
        cmp #16
        bcc +
        lda #<$d418             ; täysi: soitin kirjoittaa taas SID:iin ja FRAME_HOOK kutsuu sitä suoraan
        sta MUSIC_D418_OP
        lda #>$d418
        sta MUSIC_D418_OP+1
        lda #<MUSIC_PLAY
        sta FRAME_HOOK+1
        lda #>MUSIC_PLAY
        sta FRAME_HOOK+2
+       rts
hv_v418 .byte 0
hv_l    .byte 1
hv_s    .byte HV_DT
        .endlogical
hv_end
        .cerror HV_AT + hv_end - hv_img > $0160, "häivytys yli pinosivun alaosan"
