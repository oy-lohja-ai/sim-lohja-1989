; Yhteinen musiikkimoduuli protoille: demon biisi Blackbird-soittimella.
; Symbolit tulevat build-hakemiston music.inc:stä (tools/music/music.py build).
;
;   .include "music.inc"                 ; HAVE_MUSIC, MUSIC_LOAD, MUSIC_PLAY, ...
;   .include "../music/music.asm"        ; tämä tiedosto koodialueelle (145 tavua)
;   jsr music_init                       ; tai: ldx #<kehys / ldy #>kehys / jsr music_seek
;   IRQ: jsr MUSIC_PLAY kerran kehyksessä (enintään 1 030 sykliä, keskimäärin 630)
;   * = MUSIC_LOAD / .binary "music.bin"
;
; Soitin käyttää vain omaa aluettaan (MUSIC_LOAD..MUSIC_END, puskuri MUSIC_BUF..MUSIC_BUF_END),
; nollasivua MUSIC_ZP..MUSIC_ZP+15 ja SID:iä. Se ei koske $01:een, CIA:han eikä VIC:iin.

; A = 0. Nollaa SID:n ja aloittaa biisin alusta.
music_init
        lda #0
        jmp MUSIC_INIT

; Aloittaa biisin kehyksestä X (lo) / Y (hi), kun kello alkaa kesken biisin (esim. payload.asm START).
; Soitinta kelataan X/Y play-kutsua I/O pois päältä ($01 = $34), joten SID-kirjoitukset
; menevät I/O:n alle RAMiin eikä kelaus kuulu. Lopuksi viimeiset arvot kopioidaan SID:iin
; ja RAM $d400-$d418 palautetaan. Luupin yli ei oikaista: toisen kierroksen tila (purku-
; puskurin historia) eroaa ensimmäisestä, ja kelaus antaa saman tilan kuin demo ajossa.
; Kesto noin 630 sykliä per kehys (kehys 6 000 = 3,8 s, VICE:n warpissa hetki).
; Kutsu keskeytykset pois päältä.
music_seek
        stx ms_n
        sty ms_n+1
        jsr music_init
        lda $01
        pha
        lda #$34
        sta $01
        ldx #24                 ; RAM I/O:n alla talteen
-       lda $d400,x
        sta ms_ram,x
        dex
        bpl -
ms_loop lda ms_n
        ora ms_n+1
        beq ms_done
        jsr MUSIC_PLAY
        lda ms_n
        bne +
        dec ms_n+1
+       dec ms_n
        jmp ms_loop
ms_done ldx #24                 ; kelauksen SID-arvot talteen, RAM takaisin
-       lda $d400,x
        sta ms_sid,x
        lda ms_ram,x
        sta $d400,x
        dex
        bpl -
        lda #$35
        sta $01
        ldx #24
-       lda ms_sid,x
        sta $d400,x
        dex
        bpl -
        pla
        sta $01
        rts

ms_n    .word 0
ms_ram  .fill 25
ms_sid  .fill 25
