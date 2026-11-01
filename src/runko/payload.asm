; Bootin pakattu sisältö $1000-: Krillin asennus, Krillin resident ja runko odottamassa kopiointia, käynnistys.
; boot.asm purkaa tämän ja hyppää start:iin KERNAL päällä.

        .include "runko.inc"
        .include "music.inc"
        .include "krill.inc"
        .include "gen/timing.inc"       ; TIM_SONG_START: biisin kehys clock0:ssa (aikajanalta)
        .include "dos.inc"              ; MS-DOS-käynnistys: DOS_GO, DOS_END (levyllä vain, jos f_dos on kuvauksessa)

        .weak
START   = PART_START            ; kello alkaa demon kehyksestä START (osavaljas: kohtauksen alku; make DSTART=n)
TESTI   = 0
f_dos   = 0                     ; MS-DOS-käynnistys: levy.py names määrittelee lohkon, kun kuvauksessa on f_dos
        .endweak

        * = install
        .binary "install-c64.prg", 2
        .cerror * > STAGE, "Krillin asennus yli"

STAGE   = $2c00
STACK_TOP = loadraw < $0200 ? (loadraw - 1) & $ff : $ff
        * = STAGE
krill_img
        .binary "loader-c64.prg", 2
        .cerror * - krill_img > RES_AT - loadraw, "Krillin resident osuu runkoon"
res_img
        .logical RES_AT
        .include "resident.asm"
        .if TESTI
        .include "link-testi.asm"
        .else
        .include "link.asm"
        .endif
        .include "files.inc"
res_end
        .cerror res_end > MUSIC_LOAD, "runko yli: ", format("$%04x", res_end)
        .endlogical
RES_LEN = res_end - RES_AT
        .if PART == 97                  ; integraatio: kohtauksen alun rutiinit (kulku.asm ku_hi) musiikin perään, runkon
hi_img                                  ; alueelle MUSIC_END-MUSIC_BUF, jota musiikki eikä mikään osa käytä
        .logical MUSIC_END
        .dsection ku_hi
hi_end
        .cerror hi_end > MUSIC_BUF, "kulku: ku_hi yli: ", format("$%04x", hi_end)
        .endlogical
        .endif
        .virtual MUSIC_LOAD
res_limit                       ; levy.py disk tulostaa residentin vapaat tavut res_limit - res_end
        .endv

start   lda #8                  ; laitenumero (FA) aina 8: Krill asentuu $ba:n asemalle, ja Ultimaten Mount & Run ei aja
        sta $ba                 ; KERNALin LOADia, joten $ba voi olla 0 tai roskaa
        jsr install             ; KERNAL päällä (Krill README: asennus ennen omia keskeytyksiä)
        bcc +
        sta $d020
        jmp *
+       sei
        lda #$7f                ; CIA-keskeytykset pois, runko käyttää rasteri-IRQ:ta
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #$35
        sta $01
        lda #$0b
        sta $d011
        lda #0
        sta $d015
        sta $d020
        sta $d021
        sta $d01a
        lda #$ff
        sta $d019
        ldx #0                  ; Krillin resident $0200- (KERNAL-kutsut sotkevat $0200-$03ff, siksi vasta nyt)
-       lda krill_img,x
        sta loadraw,x
        lda krill_img + $100,x
        sta loadraw + $100,x
        lda krill_img + $200,x
        sta loadraw + $200,x
        inx
        bne -
-       .for p := 0, p < (RES_LEN + 255) / 256, p += 1
        lda res_img + p * 256,x
        sta RES_AT + p * 256,x
        .next
        inx
        bne -
        .if PART == 97                  ; ku_hi paikalleen (Krillin asennus on jo ajettu, alue vapaa)
        ldx #hi_end - MUSIC_END
-       lda hi_img - 1,x
        sta MUSIC_END - 1,x
        dex
        bne -
        .endif
        lda #<nmi_rti
        sta $fffa
        sta $fffe
        lda #>nmi_rti
        sta $fffb
        sta $ffff
        ldx #STACK_TOP          ; pino $0100-: Krillin resident voi alkaa pinosivun lopusta (tools/krill/koosta.py)
        txs
        lda #0                  ; mittarit (runko.inc M_*): nollaus ja muodon versio
        ldx #M_END - M_BASE - 1
-       sta M_BASE,x
        dex
        bpl -
        lda #2
        sta M_VER
        lda #$ff                ; CIA1 ajastin A vapaasti juoksevaksi (tyhjäkäyntimittari), keskeytykset pois päältä
        sta $dc04
        sta $dc05
        lda #$11
        sta $dc0e
        .if f_dos                       ; MS-DOS-käynnistys: koko demon levy (kokoa.py); sen taulu kutsuu
        #LOAD f_act0                    ; DOS-ruudun musiikki Appeltrad Act 0 $a000- (dos.asm soittaa, kokoa.py ACT0)
        #LOAD f_dos                     ; $e400- (src/runko/dos.asm), bittikartta $c000-
        ldx #<(TIM_SONG_START + START)  ; DOS_END kelaa biisin tähän, kun kirjoitus on ohi
        ldy #>(TIM_SONG_START + START)
        jsr DOS_GO                      ; kirjoitus ja naputus IRQ:ssa, pääsäie lataa sillä aikaa
        #LOAD f_music                   ; DOS_ENDin ensimmäisen kohtauksen alkulatausten jälkeen
        .else
        #LOAD f_music
        ldx #<(TIM_SONG_START + START)   ; biisi demon kehyksestä START (hiljaa kelaten)
        ldy #>(TIM_SONG_START + START)
        jsr music_seek
        .if PART == 97
        jsr hv_on                       ; koko demo: biisi häivyy sisään (haivytys.asm; DOS-polulla DOS_END)
        .else
        lda #0                          ; osalevy: SID hiljaa kelauksen jälkeen (kelauksen arvot soivat muuten sointuna
        sta $d418                       ; latausten ajan), soitin palauttaa tason ensimmäisellä kutsulla kellossa
        .endif
        .endif
        lda #<START
        sta DFRAME
        lda #>START
        sta DFRAME+1
        jmp script

        .include "music/music.asm"      ; music_init, music_seek: vain käynnistyksessä
        .if PART == 97
        .include "haivytys.asm"         ; hv_on: biisin häivytys sisään koko demon alussa
        .endif
        .dsection boot_names            ; files.inc: levy.json:n boot-tiedostojen nimet (musiikki)
        .if PART == 97
        .include "kulku_n.asm"          ; integraatio: muiden kohtausten taulut (tools/disk/kokoa.py irrottaa ne)
        .endif
