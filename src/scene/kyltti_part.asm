; Kyltti-moduuli (kyltti-greets, src/proto/kyltti) levyn tiedostoksi (kulku src/scene/hil_glue.asm): sama koodi kahdella datalla.
;   "ajo":    kamera-ajon loppukuva, koodi $4400-, kangas $8000 (pankki 2, luovutuskuvan ruutu $8800)
;   "kyltti": lähikuva, koodi $1a00-, kangas pankissa 1 (ruutu $5c00, bittikartta $6000); KSPLIT = 1 lisää
;             kyl_splitin, jolla purku jakaa spritet pallon kanssa (pallo hw 0-3 ylhäällä, kyltti hw 0..K_NSPR-1 alla)
; Makefile antaa K_BASE, K_END, K_CANVAS ja K_PTRS sekä datan hakemiston (build/kyltti[-ajo]/mod, kuvan rivi 0 = 72).
        .weak
KSPLIT  = 0
KYL_FREE = 120                  ; pallon spritet päättyvät viimeistään tätä edeltävällä rivillä (purku.asm, ball_step)
HIL_GLUE = 0                    ; Hillnerin vaiheen sisääntulot ja IRQ: 1 = ajo-kyltti (src/proto/hillner/glue_ajo.asm),
        .endweak                ; 2 = lähikuva (glue_lahi.asm)

        .include "kyltti.inc"
        * = K_BASE
        .include "kyltti_all.asm"

        .if KSPLIT
; Purun IRQ:sta kerran kehyksessä pallon spritejen alettua (rivi noin 116): ensin Y ja $d015 (k_wy, pallon
; näytössä olevat spritet jatkuvat), pallon päätyttyä rivillä KYL_FREE muut rekisterit. Kyltin portaassa hw 3
; alkaa ylimpänä (noin rivi 122), joten se kirjoitetaan ensin. Värit kirjoitetaan rivillä, jolla kyltin ja
; pallon spritejä ei piirretä (8565:n harmaa piste).
kyl_split
        jsr k_wy
-       lda $d012
        cmp #KYL_FREE
        bcc -
        lda #~K_MASK & $ff
        and $d01c
        sta $d01c
        lda #~K_MASK & $ff
        and $d017
        sta $d017
        lda #~K_MASK & $ff
        and $d01d
        sta $d01d
        lda $d010
        and #~K_MASK & $ff
        ora #K_XMSB & K_MASK
        sta $d010
        jsr _one3
        jsr _one2
        jsr _one1
        jsr _one0
        jsr _one4               ; hw 4-6: pallo ei käytä, kirjoitetaan silti (purku_go nollaa tilan)
        .if K_NSPR > 6
        jsr _one5
_one6   ldx #6
        .byte $2c
        .endif
_one5   ldx #5
        .byte $2c
_one4   ldx #4
        .byte $2c
_one3   ldx #3
        .byte $2c
_one2   ldx #2
        .byte $2c
_one1   ldx #1
        .byte $2c
_one0   ldx #0
        lda k_sprcol,x
        sta $d027,x
        txa
        asl
        ora k_shown
        clc
        adc #K_PBASE
        sta K_PTRS,x
        txa
        asl
        tay
        lda kx_tab,x
        sta $d000,y
        rts
kx_tab  .byte <(K_SPR_X0 + 24 * range(K_NSPR))
        .endif
        .if HIL_GLUE == 1
        .include "glue_ajo.asm"
        .elsif HIL_GLUE == 2
        .include "glue_lahi.asm"
        .endif
kyl_end
        .cerror kyl_end > K_END, "kyltti yli rajan: ", format("$%04x", kyl_end)
