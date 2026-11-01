; Demon runko, pysyvä osa RES_AT:sta (src/runko/payload.asm kopioi tämän paikalleen).
; Hyppytaulu on osien vakaa rajapinta (runko.inc). Krillin resident on $01fc-$0406. Mittarit M_* ($0100-): runko.inc.

frame_hook                      ; +0 FRAME_HOOK: kerran kehyksessä musiikki ja demon kello (koodi suoraan osoitteessa)
        jsr MUSIC_PLAY
        .if PART == 97                  ; integraatio: kello ja aika edellisestä kutsusta (kulku.asm ku_fh)
        jmp ku_fh
        .fill R_LOADRAW - *, 0
        .else
        inc DFRAME
        bne +
        inc DFRAME+1
+       rts
        .endif
        .cerror * != R_LOADRAW, "hyppytaulu"
        jmp loadraw_chk         ; R_LOADRAW
        jmp loadcompd_chk       ; R_LOADCOMPD
        jmp wait                ; R_WAIT
        jmp irq_on              ; R_IRQ_ON
        jmp tick_rts            ; R_TICK (vektori)
tick_rts rts                    ; R_TICK_RTS
        .cerror tick_rts != R_TICK_RTS, "hyppytaulu"
        jmp idle                ; R_IDLE
        .cerror * - 3 != R_IDLE, "hyppytaulu"

idle                            ; R_IDLE: tyhjäkäynti mitataan CIA1:n ajastimella A (vapaasti juokseva, ei keskeytyksiä).
        ldy $dc05               ; Väli edellisestä idle-kutsusta lasketaan tyhjäkäynniksi, jos se on lyhyt (kutsujan
        lda $dc04               ; odotussilmukka); IRQ:n mittainen väli ei ole. Summa sykleinä kehyksittäin M_IDLE:en.
        cpy $dc05
        beq +
        ldy $dc05               ; alatavu pyörähti lukujen välissä: uusi luku
        lda $dc04
+       tax
        sec                     ; väli = edellinen - nyt (ajastin laskee alaspäin)
        lda idle_t
        stx idle_t
        sbc idle_t
        sta idle_d
        lda idle_t+1
        sty idle_t+1
        sbc idle_t+1
        bne idle_fr             ; yli 255 sykliä: ei tyhjäkäyntiä
        lda idle_d
        cmp #IDLE_GAP
        bcs idle_fr
        adc idle_n              ; C = 0
        sta idle_n
        bcc idle_fr
        inc idle_n+1
idle_fr lda DFRAME              ; uusi kehys: edellisen kehyksen summa ja kehys mittariin, nollaus
        cmp idle_f
        beq +
        ldx idle_f
        stx M_IDLE_F
        sta idle_f
        lda idle_n
        sta M_IDLE
        lda idle_n+1
        sta M_IDLE+1
        lda #0
        sta idle_n
        sta idle_n+1
+       rts

irq_res pha                     ; runkon IRQ: musiikki, kello ja R_TICK. Osan oma IRQ korvaa tämän.
        txa
        pha
        tya
        pha
        lda $01
        pha
        lda #$35
        sta $01
        asl $d019
        .if PART == 97                  ; integraatio: rungon IRQ on tasainen (rivi 250), joten ku_fh ottaa välissä
        inc ku_first                    ; hukatut kutsut kiinni (x_init keskeytykset pois: kaupungintalo-ikkuna -2)
        .endif
        jsr frame_hook
        jsr R_TICK
        pla
        sta $01
        pla
        tay
        pla
        tax
        pla
nmi_rti rti

irq_on  lda #<irq_res           ; runkon IRQ rivillä RES_IRQ_LINE (ei muuta $d011:n muita bittejä kuin rivin 8:tta)
        sta $fffe
        lda #>irq_res
        sta $ffff
        lda #RES_IRQ_LINE
        sta $d012
        lda $d011
        and #$7f
        sta $d011
        lda #1
        sta $d01a
        sta $d019
        rts

loadraw_chk                     ; X/Y = nimi. Virheestä (C = 1, A = Krillin tila) uusi yritys, lopulta pysähdys
        lda #0
        .byte $2c               ; bit abs: ohittaa seuraavan lda:n
loadcompd_chk
        lda #1
        sta ld_mode
        stx ld_x
        sty ld_y
        stx M_LOAD              ; mittari: ladattava nimi (0 = ei latausta)
        sty M_LOAD+1
        lda #LOAD_TRIES
        sta ld_try
-       ldx ld_x
        ldy ld_y
        lda ld_mode
        bne +
        jsr loadraw
        jmp ++
+       jsr loadcompd
+       bcc ld_ok
        dec ld_try
        bne -
ld_fail sta $d020               ; reunus = Krillin virhekoodi ($fb-$ff, krill.inc status_*), pysähdys
        jmp ld_fail
ld_ok   lda #0                  ; latauksen loppu (M_LOAD: ylätavu 0 = ei latausta)
        sta M_LOAD+1
        rts
ld_mode .byte 0
ld_x    .byte 0
ld_y    .byte 0
ld_try  .byte 0
LOAD_TRIES = 3

load    = loadcompd_chk           ; X/Y = nimi (kohtaustiedostot, esim. src/scene/hil_glue.asm): kohtausten tiedostot
                                ; ovat aina pakattuja (levy.py tarkistaa)

wait    stx M_WAIT              ; odottaa, kunnes DFRAME >= X/Y (tavoite mittariin), odotus on tyhjäkäyntiä
        sty M_WAIT+1
-       jsr idle
        ldy DFRAME+1            ; yhtenäinen lukema: IRQ voi kasvattaa kelloa välissä ($06ff -> $0700)
        bmi -                   ; jatkuvan sauman alussa kello S - 1 = $ffff (ku_seam): ei vielä (muuten taulu2f
        lda DFRAME              ; loppuisi heti)
        cpy DFRAME+1
        bne -
        cmp M_WAIT
        tya
        sbc M_WAIT+1
        bcc -
        rts
