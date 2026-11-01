; Hillnerin kauppatalo: kamera laskeutuu kattoikkunoista LOHJAN RAUTA -kylttiin (proto).
;
; Linecrunch-pystyvieritys MC-bittikartalla (All Hallows' Eve witch212, lft:n Spindle-esimerkki):
; ikkuna 320x144 riveillä 72-215. Rivistä 48 alkaen c riviä crunchataan (jokainen ohittaa yhden
; merkkirivin yhdellä rasteririvillä), sitten tyhjiä rivejä niin, että ensimmäinen badline on
; rivillä 72 - f. Pikselipaikka p = 8c + f asettelun sisällä. Laittoman ECM+BMM-tilan rivit ovat
; mustia, ikkunan reunat yhdellä $d011-kirjoituksella. Pankissa on 25 riviä (1000 solua), joten
; c <= 6: kun vieritys ylittää 48 px, vaihdetaan toiseen pankkiin, johon pääsilmukka on jo
; kopioinut seuraavan 25 rivin asettelun (6 riviä alempaa). Värimuisti kopioidaan vaihtokehyksessä
; säteen edellä.
;
; Syvyyskerrokset: taivas (0,25x) ja kaukainen kaupunki (0,5x) ovat bittikartan MC 00 -pikseleitä, joiden
; väri $D021 kirjoitetaan rivi riviltä yläreunan IRQ:ssa (taivassilmukka). Talo 1x, etuala spriteinä 1,5x.

        .include "hillner.inc"
        .include "music.inc"
        .if INTEGRATED
        .include "gen/timing.inc"       ; demon kello
        .endif

        .weak
DEBUG   = 0
PREWAIT = 0                     ; kehyksiä ennen kelloa (emulaattorikaappaus pääsee alkukehyksiin)
INTEGRATED = 0                  ; 1 = pääbuildin moduuli: ei käynnistystä eikä
FRAME_HOOK = 0                  ; omaa musiikkia; hil_prep, hil_go ja FRAME_HOOK kerran kehyksessä
KEEP_ROW = 16                   ; edellisen osan (alku) värimuistirivi, jonka hil_go kirjoittaa vasta clock0:ssa
CODE_BASE = $1a00               ; moduulin koodin alku (Krill $0200-$0407, integraattori, musiikki $0800-$19ff)
R_IDLE  = $0422                 ; rungon tyhjäkäyntikierros (src/runko/runko.inc), A ja X muuttuvat
        .endweak

LINE_BOT  = 213
        .if !INTEGRATED
COLSTAGE  = $0400               ; seuraavan asettelun värimuisti (1000 tavua)
d21line   = $0200               ; $D021 riveittäin rivinumerolla (vain rivit 72..d21end + 1)
        .endif

        .virtual $02
frame   .word ?
mptr    .word ?                 ; liikekäyrän osoitin (nopeus 1/16 px per kehys)
mcount  .word ?
phase   .byte ?                 ; 0 pito, 1 liike, 2 pito
pos     .word ?                 ; kameran paikka 1/16 px
tpos    .word ?                 ; liikekäyrän paikka (pos seuraa sitä)
lstep   .byte ?                 ; edellinen askel
ppx     .word ?                 ; kokonaiset pikselit
lbase   .word ?                 ; näkyvän asettelun alku pikseleinä
k_cur   .byte ?                 ; näkyvä asettelu
bank    .byte ?                 ; näkyvä pankki 0 = pankki 2, 1 = pankki 3
plyt    .byte ?                 ; p asettelun sisällä (0..55)
cc      .byte ?
ff      .byte ?
lb      .byte ?                 ; ensimmäinen badline
seqn    .byte ?
lcur    .byte ?
d11show .byte ?
d11hide .byte ?
dd00v   .byte ?
pre_req .byte ?                 ; pääsilmukka: rakenna asettelu pre_k pankkiin pre_bank
pre_k   .byte ?
pre_bank .byte ?
built   .byte ?                 ; viimeksi rakennettu asettelu
ready   .byte ?                 ; takapankin asettelu valmis
colreq  .byte ?
colpre  .byte ?                 ; seuraavan asettelun väririvejä jo kirjoitettu
colrest .byte ?                 ; vaihdon jälkeen kirjoitettavat rivit 20..24
fin_state .byte ?               ; luovutus: 0 kesken, 2 loppukuva valmis takapankissa, 3 vaihto, 4 näytössä
stalls  .byte ?                 ; kehykset, joina takapankki ei ehtinyt (pitäisi olla 0)
dbg19   .byte ?
bot_d11 .byte ?                 ; alareunan $d011 ja f näkyvälle kehykselle
bot_ff  .byte ?
bl7m    .byte ?                 ; (lb - 1) & 7: rivi X + 1 on badline, kun X & 7 = bl7m
d21end  .byte ?                 ; taivassilmukan viimeinen rivi + 1 (1 = ei taivasta)
d21z    .byte ?                 ; nollarivien paikka d21linessa (rivi 72 + d21z), $ff = ei nollia
ra      .byte ?
rx      .byte ?
ry      .byte ?
rowi    .byte ?
rown    .byte ?
fcol    .word ?                 ; fin_cells: värien kohde
tmp     .word ?                 ; pääsilmukka
ltmp    .word ?                 ; IRQ:n logiikka
dbmp    .word ?
dscr    .word ?
dcol    .word ?
s16     .word ?
cn      .byte ?
swx     .word ?
sm_mp   .word ?                 ; savu (smoke.asm): pallon maski, tietueen ja bittikartan rivi, koodipuskuri
sm_rp   .word ?
sm_bab  .word ?
sm_cp   .word ?
hm_to   .byte ?                 ; hil_main1: palaa, kun tämä asettelu on rakennettu
dbgtop  .byte ?                 ; mittaus: taivassilmukan loppurivi
dbgbot  .byte ?                 ; mittaus: alareunan IRQ:n loppurivi (+128 = seuraava kehys ennen riviä 213)
        .endv

        .if INTEGRATED
        * = CODE_BASE
; hil_prep: alustus edellisen osan kuvan vielä näkyessä (tarvitsee vain CRANE1:n ja CRANE2:n): ei koske VIC:n
; rekistereihin eikä keskeytyksiin; kirjoittaa nollasivun $02-$a1, koodialueen taulut, pankin 2 ruudun ja
; spritelohkot $8000-$853f, bittikartan $a000-$bf3f ja värimuistin paitsi rivin KEEP_ROW. hil_go: pystypaluussa
; VIC, IRQ:t ja rivin KEEP_ROW värit (alun viimeinen kuva näkyy siihen asti), palaa heti. hil_main: pääsilmukka (asettelut 1-5 ja
; savu, tarvitsee CRANE1B:n), palaa, kun viimeinen asettelu näkyy (kamera voi vielä liikkua).
hil_prep
        .else
        * = $0801
        .word (+), 2026
        .null $9e, format("%d", start)
+       .word 0

start   sei
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #$35
        sta $01
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        lda #$0b
        sta $d011
        lda #0
        sta $d015
        sta $d020
        sta $d021
        sta $d01a
        lda #$3f
        sta $dd02
        .endif                  ; integroituna $dd02 on Krillin (vain $dd00 0-3)
        .if !INTEGRATED
        jsr vic_init
        .endif
        ldx #0
        txa
-       sta $02,x               ; nollasivun muuttujat
        inx
        cpx #$a0
        bne -
        lda #<motion_v
        sta mptr
        lda #>motion_v
        sta mptr+1
        .if HAVE_MUSIC && !INTEGRATED
        ldx #<MSTART            ; biisi Hillnerin kohtauksen kohdasta (keskeytykset pois)
        ldy #>MSTART
        jsr music_seek
        .endif
        .if INTEGRATED          ; spritelohkot pankkiin 2 pankista 3 (CRANE2; pankin 2 lohkot ovat CRANE1B:n
        ldx #N_BLOCKS * 32      ; alueella, joka latautuu vasta kamera-ajon alussa)
-       lda BANK3_SCR + SPR_BASE - 1,x
        sta BANK2_SCR + SPR_BASE - 1,x
        lda BANK3_SCR + SPR_BASE + N_BLOCKS * 32 - 1,x
        sta BANK2_SCR + SPR_BASE + N_BLOCKS * 32 - 1,x
        dex
        bne -
        .endif
        lda #0                  ; ei kirkkoa vielä (sprites.asm)
        tax
-       sta d21late,x
        inx
        bne -
        ldx #0                  ; taivas ruudun riveittäin (logic_frame vaihtaa vain nollarivit)
-       lda sky_tab,x
        sta d21line + T_LINE,x
        inx
        cpx #B_LINE - T_LINE
        bne -
        lda #0                  ; asettelu 0 pankkiin 2 ja värit
        sta pre_k
        sta pre_bank
        jsr build_layout        ; (värit COLSTAGEen)
        .if INTEGRATED          ; värimuisti jo nyt paitsi rivi KEEP_ROW, jota edellinen osa (alku: viiva) vielä
        ldx #0                  ; näyttää; se kopioidaan clock0:ssa. Muilla riveillä edellisen osan kuvassa ei ole
-       cpx #KEEP_ROW           ; värimuistia käyttäviä pikseleitä (alku: vain viiva rivillä 16)
        beq +
        jsr col_row
+       inx
        cpx #ROWS_BANK
        bcc -
        .else
        jsr colcopy
        .endif
        lda #1                  ; asettelu 1 pankkiin 3 taustalla
        sta pre_k
        sta pre_bank
        sta pre_req
        jsr logic_frame         ; ensimmäisen kehyksen parametrit
        lda d11hide
        sta bot_d11
        lda ff
        sta bot_ff
        jsr spr_frame0          ; ajastin B ja spr_frame
        .if INTEGRATED
        rts
hil_go  sei
        .endif
        .if PREWAIT
        ldx #<PREWAIT
        ldy #>PREWAIT + 1
-       bit $d011
        bpl -
-       bit $d011
        bmi -
        dex
        bne --
        dey
        bne --
        .endif
        .if INTEGRATED          ; heti, jos ollaan pystypaluussa (rivit 250-311): edellisen osan IRQ (joka
        cli                     ; pitää sen kuvan näkyvissä) saa jatkua odotuksen ajan, ja Hillner ottaa
-       bit $d011               ; koneen saman pystypaluun aikana: ei mustaa kehystä (jos sei:n alla
        bmi +                   ; odotettaisiin rivin 256 jälkeen seuraavaa riviä 250, alun kuva sammuisi
        lda $d012               ; yhdeksi kehykseksi)
        cmp #250
        bcc -
+       sei
        .else
-       bit $d011
        bpl -
-       lda $d012
        cmp #250
        bne -
        .endif
clock0  jsr vic_init            ; pystypaluussa: edellisen osan kuva vaihtuu Hillneriin tästä kehyksestä
        jsr spr_apply
        lda #<irq_top
        sta $fffe
        lda #>irq_top
        sta $ffff
        lda #LINE_TOP
        sta $d012
        lda d11hide
        sta $d011
        lda #$ff                ; vanha rasterilippu pois ennen sallintaa
        sta $d019
        lda #1
        sta $d01a
        lda #$ff
        sta $d019
        .if INTEGRATED
        ldx #KEEP_ROW           ; edellisen osan värimuistirivi (muut kirjoitti hil_prep)
        jsr col_row
        cli
        rts                     ; taulu lataa loput tietueet hil_main1:n ja hil_main2:n jälkeen
        .else
        cli
        .endif
        .if INTEGRATED
hil_main1                       ; kunnes asettelu 3 on rakennettu (sen rivit ovat CRANE1:ssä ja CRANE2:ssa)
        lda #3
        .byte $2c               ; bit abs: ohittaa seuraavan lda:n
hil_main2                       ; kunnes asettelu 4 on rakennettu (CRANE1B)
        lda #4
        .byte $2c
hil_main                        ; kunnes viimeinen asettelu näkyy (CRANE1C)
        lda #$ff
        sta hm_to
        .endif

; pääsilmukka: rakentaa seuraavan asettelun takapankkiin. Savu vain vapaa-ajalla (rakennus ensin, muuten
; takapankki ei ehdi ja kamera seisoo), paitsi heti vaihdon jälkeen yksi päivitys uuteen asetteluun ennen
; rakennusta (muuten savu puuttuisi rakennuksen ajan, noin 10 kehystä).
main    lda pre_req
        beq _idle
        .if INTEGRATED
        lda k_cur
        cmp sm_lay
        beq +
-       lda sm_ready            ; vanhan asettelun päivitys hylätään seuraavassa alareunassa
        bne -
        jsr smoke_now
+
        .endif
        jsr build_layout
        lda pre_k
        sta built
        lda #0
        sta pre_req
        lda #1
        sta ready
        .if INTEGRATED
        lda built
        cmp hm_to
        bne main
        rts
        .else
        jmp main
        .endif
        .if INTEGRATED
_idle   jsr smoke               ; savupiippujen savu (25 Hz, näytölle alareunan IRQ:ssa)
        jsr R_IDLE              ; rungon CPU-mittari: tyhjäkäyntikierros
        lda k_cur               ; viimeinen asettelu näkyy (pankki 3): pääsilmukka kululle, joka lataa ajo-kyltin
        cmp #LAYOUTS - 1        ; pankin 2 ruudun ja spritelohkojen päälle ($8000-) kameran vielä liikkuessa;
        bne main                ; build.py tarkistaa, ettei viimeisen asettelun tietueita ole siellä
        rts

; hil_fin: kameran pysähdyttyä luovutus: loppukuva (pylväs leivottuna, kyltin kaista tyhjänä) pankkiin 2
; (FIN_SCR, FIN_BMP), vaihto alareunassa, sitten IRQ on pelkkä FRAME_HOOK rivillä 250. Palaa, kun loppukuva näkyy.
hil_fin
-       jsr R_IDLE
        lda phase               ; kamera pysähtynyt ja viimeinen asettelu (pankki 3) näkyy, joten pankki 2 on vapaa
        cmp #2
        bne -
        lda k_cur
        cmp #LAYOUTS - 1
        bne -
        lda pos                 ; ja kamera on kirinyt liikekäyrän kiinni
        cmp tpos
        bne -
        lda pos+1
        cmp tpos+1
        bne -
        jsr fin_build
-       jsr R_IDLE
        lda fin_state
        cmp #4
        bne -
        rts
        .else
_idle   lda phase               ; kamera pysähtynyt: loppukuva takapankkiin luovutusta varten
        cmp #2
        bne main
        lda fin_state
        bne main
        jsr fin_build
        jmp main
        .endif

nmi     rti

vic_init                        ; MC-bittikartta, spritet: yhteiset värit 0 ja 12, bittikartan edessä, ei laajennuksia
        lda #$18                ; MC, 40 saraketta
        sta $d016
        lda #$08                ; ruutu +$0000, bittikartta +$2000
        sta $d018
        lda #0
        sta $d015
        sta $d020
        sta $d021
        sta $d025
        sta $d01b
        sta $d017
        lda #12
        sta $d026
        rts

; ---------------------------------------------------------------- IRQ: yläreuna (rivi 44)
; Linecrunch-moottori, taivassilmukka, asettelut ja värit: yhteinen src/lib/crunch.asm (myös koti).
CR_TOPCLR = cr_topclr           ; irq_top kirjoittaa tähän 0 (absoluuttinen osoite: 6 sykliä ajoitukseen)
CR_LATE = 1                     ; d21late: kirkon rivit (sprites.asm spr_frame)
        .include "lib/crunch.asm"

; irq_top jatkuu tästä (rivi noin 75; ensimmäinen taivassegmentti, jos se alkaa ennen riviä SK_TOP, on jo
; kirjoitettu irq_topin taivassilmukassa): seuraavat taivassegmentit ja alareuna.
cr_top_tail
        lda $d012
        sta dbgtop
        lda d11hide             ; tämän kehyksen alareunan arvot talteen (seuraavan kehyksen logiikka on
        sta bot_d11             ; alareunan IRQ:ssa)
        lda ff
        sta bot_ff
        lda sk_first
        sta sk_i
        jmp sk_sched

; Taivassegmentit: taivas pysyy ruudulla paikallaan, ja sen väri vaihtuu vain harvoilla riveillä (build.py
; sky_segments: 4 tiheää aluetta, yhteensä noin 40 riviä 144:stä) sekä nollarivillä 72 + n, jonka alla
; taivasta ei ole. logic_frame tekee kehyksen listan sk_s/sk_e (ruudun rivit, loppu poissuljettu). Segmentin
; IRQ tulee 3 riviä ennen sen alkua ja ajaa taivassilmukan (sky_loop) segmentin riveille; väleissä CPU on
; vapaa. Jokaisen taivasrivin kirjoittava silmukka varaisi CPU:n riveille 44-211.
irq_sky sta ra
        stx rx
        sty ry
sk_run  ldy sk_i
        ldx sk_s,y
        lda sk_e,y
        sta d21end
        jsr sky_loop
        inc sk_i
sk_sched                        ; seuraava segmentti tai alareuna (rekisterit ra/rx/ry:ssä)
        asl $d019
        ldy sk_i
        cpy sk_n
        bcs _bot
        lda sk_s,y              ; IRQ 3 riviä ennen segmenttiä, tai heti jos se on alle 2 rivin päässä
        sec
        sbc #4
        cmp $d012
        bcc sk_run
        beq sk_run
        adc #0                  ; C = 1
        sta $d012
        lda #<irq_sky
        sta $fffe
        lda #>irq_sky
        sta $ffff
        bne _out
_bot    lda $d012               ; taivassilmukka kesti alareunaan asti (rivin LINE_BOT IRQ ei enää laukea):
        cmp #LINE_BOT - 1       ; alareuna suoraan (cr_edge odottaa riviä 215)
        bcs _dir
        lda #LINE_BOT
        sta $d012
        lda #<irq_bot
        sta $fffe
        lda #>irq_bot
        sta $ffff
_out    lda ra
        ldx rx
        ldy ry
        rti
_dir    lda ra
        ldx rx
        ldy ry
        jmp irq_bot
; ---------------------------------------------------------------- IRQ: alareuna (rivi 213)
; Ikkunan alareuna: ECM päälle rivin 215 oikeassa reunassa (syklit 58-64), jolloin rivin 216
; mahdollinen badline (f = 0) ja spritejen 3-7 DMA rivin 216 alussa eivät osu kirjoitukseen.
; Jos rivi 215 on itse badline (f = 1), CPU pysähtyy syklistä 12 sykliin 55 ja kirjoitus osuu
; sykleihin 58-66. Mikään sprite ei jatku rivin 215 yli (sprites.asm), joten rivin 216 DMA ei viivästä kirjoitusta.
; Sitten musiikki ja demon kello (FRAME_HOOK, aina samalla rivillä), seuraavan kehyksen logiikka ja spritet (valmiina
; ennen riviä 73) ja värimuistin kopio. Vaihtokehyksessä värimuisti kopioidaan ensin (col_sw), muuten spritejen jälkeen.
irq_bot
        pha
        txa
        pha
        tya
        pha
        lda bot_d11
        ldy bot_ff
        #cr_edge
        asl $d019
        lda #<irq_top
        sta $fffe
        lda #>irq_top
        sta $ffff
        lda #LINE_TOP
        sta $d012
        lda fin_state           ; loppukuva valmis: tämä on viimeinen linecrunch-kehys
        cmp #2
        bne +
        jmp fin_switch
+       jsr sm_apply            ; savun päivitys kerralla (säde ikkunan alla)
        cli
        .if INTEGRATED          ; musiikki ja demon kello ennen raskasta logiikkaa: aina samalla rivillä (lopussa
        jsr FRAME_HOOK          ; se valuisi joskus rivin 304 yli, ja DFRAME näyttäisi seisovan ja hyppäävän)
        .endif
        jsr logic_frame         ; seuraavan kehyksen paikka, asettelu, sekvensseri ja taivas (ennen spritejä)
        lda colreq              ; vaihtokehys: värimuisti ensin, valmis ennen riviä 44
        beq +
        jsr col_frame
        jsr spr_frame
        jsr spr_apply
        jmp ++
+       jsr spr_frame
        jsr spr_apply
        jsr col_frame
+
        .if DEBUG               ; diagnostiikka: rivi, jolla spritet valmiina, kehyksille 200..453 ($7901-)
        lda frame+1
        bne +
        lda frame
        cmp #200
        bcc ++
+       lda frame
        sec
        sbc #200
        tax
        cpx #254
        bcs +
        lda $d011               ; rivi / 4, +128 jos jo seuraavassa kehyksessä (rivi < 213)
        asl a
        lda $d012
        ror a
        lsr a                   ; 9-bittinen rivi / 4
        cmp #LINE_BOT / 4
        bcs _dl
        ora #$80
_dl     sta $7901,x
+
        lda #4
        sta $d020
        .endif
        .if DEBUG
        lda #6
        sta $d020
        .endif
        .if HAVE_MUSIC && !INTEGRATED
        jsr MUSIC_PLAY          ; kerran kehyksessä (enintään noin 1 030 sykliä); integroituna FRAME_HOOK yllä
        .endif
        .if DEBUG
        lda #0
        sta $d020
        .endif
        lda $d012
        cmp #LINE_BOT
        bcs +
        ora #$80
+       sta dbgbot
        pla
        tay
        pla
        tax
        pla
        rti

; ---------------------------------------------------------------- luovutus (loppukuva)
; Kamera on pysähtynyt (ppx = P_MAX): pääsilmukka rakentaa saman kuvan tavalliseksi MC-bittikartaksi
; takapankkiin 2 (FIN_BMP, FIN_SCR, merkkirivit FIN_ROW0..+17, yscroll 0, rivit 72-215 kuten ikkuna) ja
; leipoo pysähtyneen pylvään soluihin (fin_*). Letterbox-rivit ovat nollia (musta). Viimeisen
; linecrunch-kehyksen alareunassa värit kopioidaan värimuistiin (rivit 3-20), ja seuraavan kehyksen
; rivillä 44 irq_fin vaihtaa pankin, tilan ja spritet pois. Sen jälkeen IRQ on pelkkä musiikki.
fin_build
        lda #0                  ; rivit 0-2 ja 21-24: bittikartta ja ruutu nollaan
        ldx #0
-       sta FIN_BMP,x
        sta FIN_BMP + $100,x
        sta FIN_BMP + $200,x
        sta FIN_BMP + 21 * 320,x
        sta FIN_BMP + 21 * 320 + $100,x
        sta FIN_BMP + 21 * 320 + $200,x
        sta FIN_BMP + 21 * 320 + $300,x
        sta FIN_BMP + 21 * 320 + $400,x
        inx
        bne -
        ldx #3 * 320 - $300     ; rivin 2 loppu (192 tavua; bpl ei kelpaa, kun X >= 128)
-       sta FIN_BMP + $300 - 1,x
        dex
        bne -
        ldx #119
-       sta FIN_SCR,x
        sta FIN_SCR + 21 * 40,x
        sta FIN_SCR + 21 * 40 + 40,x
        dex
        bpl -
        lda #FIN_IMG0           ; kuvan rivit FIN_IMG0.. riveille FIN_ROW0..
        sta rowi
        lda #FIN_ROWS
        sta rown
        lda #<(FIN_BMP + FIN_ROW0 * 320)
        sta dbmp
        lda #>(FIN_BMP + FIN_ROW0 * 320)
        sta dbmp+1
        lda #<(FIN_SCR + FIN_ROW0 * 40)
        sta dscr
        lda #>(FIN_SCR + FIN_ROW0 * 40)
        sta dscr+1
        lda #<(COLSTAGE + FIN_ROW0 * 40)
        sta dcol
        lda #>(COLSTAGE + FIN_ROW0 * 40)
        sta dcol+1
        jsr build_layout._row
        lda #<COLSTAGE          ; pylvään solut (värit COLSTAGEen, kopioidaan vaihdossa)
        ldx #>COLSTAGE
        ldy #FIN_N
        jsr fin_cells
        lda #2
        sta fin_state
        rts

        .if INTEGRATED
; hil_sign: kyltin kaistan maalattu teksti pois näkyvästä luovutuskuvasta (ajo-kyltin alussa, sei pystypaluussa:
; noin 140 riviä, valmis ennen kaistaa). Kutsuttava ennen kuin kamera-ajon koodin alue ladataan uudelleen.
hil_sign
        ldy #FIN_N + FIN_SN
        lda #<$d800
        ldx #>$d800
        .endif
; fin_cells: solut X..Y-1 taulukoista fin_cell_lo/hi ja fin_data (8 bittikarttatavua, ruutu ja väri);
; A/X = värien kohde (COLSTAGE tai $d800). fin_build aloittaa solusta 0 ja hil_sign solusta FIN_N.
fin_cells
        sta fcol
        stx fcol+1
        sty rown
        ldx #0
        cpy #FIN_N + 1
        bcc +
        inx
+       lda fin_data_lo,x
        sta tmp
        lda fin_data_hi,x
        sta tmp+1
        lda fin_first,x
        tax
_pl     cpx rown
        beq _pd
        stx rowi
        lda fin_cell_lo,x
        sta dbmp
        lda fin_cell_hi,x
        sta dbmp+1
        clc
        lda dbmp
        adc #<FIN_SCR
        sta dscr
        lda dbmp+1
        adc #>FIN_SCR
        sta dscr+1
        clc
        lda dbmp
        adc fcol
        sta dcol
        lda dbmp+1
        adc fcol+1
        sta dcol+1
        asl dbmp                ; bittikartta = FIN_BMP + 8 * solu
        rol dbmp+1
        asl dbmp
        rol dbmp+1
        asl dbmp
        rol dbmp+1
        lda dbmp+1
        clc
        adc #>FIN_BMP
        sta dbmp+1
        ldy #7
-       lda (tmp),y
        sta (dbmp),y
        dey
        bpl -
        ldy #8
        lda (tmp),y
        ldy #0
        sta (dscr),y
        ldy #9
        lda (tmp),y
        ldy #0
        sta (dcol),y
        lda tmp
        clc
        adc #10
        sta tmp
        bcc +
        inc tmp+1
+       ldx rowi
        inx
        jmp _pl
_pd     rts
fin_data_lo .byte <fin_data, <(fin_data + 10 * FIN_N)
fin_data_hi .byte >fin_data, >(fin_data + 10 * FIN_N)
fin_first .byte 0, FIN_N

; viimeisen linecrunch-kehyksen alareuna (irq_bot): värit rivit 3-20, sitten irq_fin rivillä 44
fin_switch
        lda #<irq_fin
        sta $fffe
        lda #>irq_fin
        sta $ffff
        lda #3
        sta fin_state
        cli                     ; irq_fin saa keskeyttää, kopio loppuu ennen riviä 72
        ldx #FIN_ROW0
-       jsr col_row
        inx
        cpx #FIN_ROW0 + FIN_ROWS
        bcc -
        .if INTEGRATED
        jsr FRAME_HOOK
        .elsif HAVE_MUSIC
        jsr MUSIC_PLAY
        .endif
        pla
        tay
        pla
        tax
        pla
        rti

irq_fin pha
        lda #FIN_DD00           ; loppukuvan VIC-pankki, tavallinen MC-bittikartta, yscroll 0, spritet pois
        sta $dd00
        lda #(FIN_SCR & $3c00) >> 6 | (FIN_BMP & $2000) >> 10
        sta $d018
        lda #$38
        sta $d011
        lda #0
        sta $d015
        sta $d021
        lda #<irq_music
        sta $fffe
        lda #>irq_music
        sta $ffff
        lda #250
        sta $d012
        asl $d019
        lda #4                  ; luovutus näkyy (integraattori voi ottaa IRQ:n)
        sta fin_state
        pla
        rti

irq_music                       ; luovutuksen jälkeen: musiikki kerran kehyksessä
        pha
        txa
        pha
        tya
        pha
        asl $d019
        .if INTEGRATED
        jsr FRAME_HOOK
        .elsif HAVE_MUSIC
        jsr MUSIC_PLAY
        .endif
        pla
        tay
        pla
        tax
        pla
        rti

; ---------------------------------------------------------------- kehyksen logiikka
logic_frame
        inc frame
        bne +
        inc frame+1
+       lda phase
        beq _hold0
        cmp #1
        beq _move
        bne _place
_hold0  lda frame+1             ; pito katolla
        bne _go
        lda frame
        cmp #HOLD0
        bcc _place
_go     lda #1
        sta phase
        lda #<MOVE_N
        sta mcount
        lda #>MOVE_N
        sta mcount+1
_move   ldy #0                  ; tpos += nopeus[i]
        lda (mptr),y
        clc
        adc tpos
        sta tpos
        bcc +
        inc tpos+1
+       inc mptr
        bne +
        inc mptr+1
+       lda mcount
        bne +
        dec mcount+1
+       dec mcount
        lda mcount
        ora mcount+1
        bne _place
        lda #2
        sta phase
; Kamera (pos) seuraa liikekäyrää (tpos). Jos seuraava asettelu ei ole valmis (tietueiden lataus myöhässä, esim.
; oikealla raudalla), kamera hiipii: askel enintään 1/16 jäljellä olevasta asettelun varasta, joten se hidastuu
; pehmeästi eikä pysähdy kerralla. Kun asettelu valmistuu, kamera kirii tpos:n kiinni enintään CATCH:lla
; (1/16 px kehyksessä), kiihtyen enintään 2 per kehys. Muuten kamera seisoisi asettelun rajalla (stalls).
CATCH   = 36                    ; 2,25 px kehyksessä (normaali huippu noin 1,1 px)
_place  sec                     ; askel = min(tpos - pos, CATCH, edellinen + 2, varasto / 16)
        lda tpos
        sbc pos
        tay
        lda tpos+1
        sbc pos+1
        beq +
        ldy #CATCH
+       cpy #CATCH
        bcc +
        ldy #CATCH
+       tya
        sec
        sbc lstep
        bcc +                   ; hidastus: ei rajaa
        cmp #3
        bcc +
        ldy lstep
        iny
        iny
+       ldx k_cur               ; varasto: seuraava asettelu ei valmis -> pos <= (lbase + CMAX*8+7)*16 + 15
        cpx #LAYOUTS - 1
        bcs _step
        lda ready
        beq +
        lda colpre
        cmp #4
        bcs _step
+       lda lbase               ; ltmp = (lbase + CMAX*8 + 7) * 16 + 15 - pos
        clc
        adc #CMAX * 8 + 7
        sta ltmp
        lda lbase+1
        adc #0
        sta ltmp+1
        ldx #4
-       asl ltmp
        rol ltmp+1
        dex
        bne -
        lda ltmp
        ora #15
        sec
        sbc pos
        sta ltmp
        lda ltmp+1
        sbc pos+1
        bcc _zero               ; (ei pitäisi tapahtua)
        lsr a                   ; / 16
        ror ltmp
        lsr a
        ror ltmp
        lsr a
        ror ltmp
        lsr a
        ror ltmp
        cmp #0                  ; (ror asetti Z:n ltmp:stä)
        bne _step               ; >= 4096/16: ei rajaa
        cpy ltmp
        bcc _step
        ldy ltmp
        .byte $2c
_zero   ldy #0
_step   sty lstep
        tya
        clc
        adc pos
        sta pos
        bcc +
        inc pos+1
+       lda pos+1               ; ppx = pos >> 4
        sta ppx+1
        lda pos
        lsr ppx+1
        ror a
        lsr ppx+1
        ror a
        lsr ppx+1
        ror a
        lsr ppx+1
        ror a
        sta ppx
_layout ldx k_cur                ; vaihto, kun ppx >= seuraavan asettelun alku ja se on valmis
        cpx #LAYOUTS - 1
        bcs _in
        lda ppx
        cmp lay_px_lo+1,x
        lda ppx+1
        sbc lay_px_hi+1,x
        bcc _in
        lda ready
        beq _in
        lda colpre              ; värit: vähintään 4 ylintä riviä kirjoitettu etukäteen (säteen edellä
        cmp #4                  ; ehditään silloinkin, kun spritejen laskenta venyy)
        bcc _in
        inx                     ; näkyvä pankki vaihtuu seuraavan kehyksen yläreunassa
        stx k_cur
        lda lay_px_lo,x
        sta lbase
        lda lay_px_hi,x
        sta lbase+1
        lda bank
        eor #1
        sta bank
        lda #0
        sta ready
        lda #1
        sta colreq
        cpx #LAYOUTS - 1        ; pääsilmukka rakentaa seuraavan vanhaan pankkiin
        bcs _in
        inx
        stx pre_k
        lda bank
        eor #1
        sta pre_bank
        lda #1
        sta pre_req
_in     sec                     ; plyt = ppx - lbase (kyllästyy 255:een)
        lda ppx
        sbc lbase
        tax
        lda ppx+1
        sbc lbase+1
        beq +
        ldx #255
+       cpx #CMAX * 8 + 8
        bcc _ok
        ldx #CMAX * 8 + 7       ; takapankki ei ehtinyt: pysytään asettelun alarajalla
        inc stalls
_ok     jsr cr_seq
; taivasrivit: rivi L näyttää kuvan rivin ppx + L - 72; jos se on < SKY_T, $D021 on ruudun rivin taivas
; sky_tab[L - 72] (horisontti pysyy ruudulla paikallaan, build.py sky_rows), muuten 0. d21line on taivas
; valmiina (hil_prep), joten kehyksessä vaihtuvat vain nollarivit 72+n..72+n+3 (d21z = n): edellisen kehyksen
; nollat takaisin taivaaksi ja uudet paikalleen. Sitten kehyksen taivassegmentit (cr_top_tail, irq_sky):
; kiinteät värinvaihtoalueet (skg_s/skg_e) nollariviin sk_l = 72 + n asti ja nollarivi. Jos taivas täyttää
; ikkunan (n >= 144), nollariviä ei ole, ja rivi 188 jälkeinen väri jatkuu alareunaan (rivit 216- ovat
; laittomassa tilassa mustia). Nollarivi 212-215 jätetään kirjoittamatta, koska se osuisi alareunan
; kirjoitukseen (cr_edge): enintään 4 riviä taivasta liikaa.
        ldx d21z
        bmi +
        ldy #4
-       lda sky_tab,x
        sta d21line + T_LINE,x
        inx
        dey
        bne -
+       lda #T_LINE             ; nollarivi (ei taivasta: 72, s72-haarat kirjoittavat sen)
        sta sk_l
        ldx #0                  ; X = n
        lda ppx+1
        bne _z
        lda #SKY_T
        sec
        sbc ppx
        beq _z
        bcc _z
        cmp #B_LINE - T_LINE
        bcc +
        lda #B_LINE             ; taivas koko ikkunassa
        sta sk_l
        lda #$ff
        sta d21z
        bne _segs
+       tax
        adc #T_LINE             ; C = 0
        sta sk_l
_z      stx d21z
        lda #0
        sta d21line + T_LINE,x
        sta d21line + T_LINE + 1,x
        sta d21line + T_LINE + 2,x
        sta d21line + T_LINE + 3,x
_segs   ldx #0                  ; X = kiinteä alue, Y = kehyksen segmentti
        ldy #0
_sl     cpx #SKG_N
        bcs _zr
        lda skg_s,x
        cmp sk_l
        bcs _zr                 ; alue alkaa nollarivillä tai sen jälkeen
        sta sk_s,y
        lda skg_e,x
        cmp sk_l
        bcc +
        lda sk_l                ; nollarivi tämän alueen sisällä tai heti perässä: alue loppuu siihen
        adc #0                  ; C = 1: sk_l + 1
        sta sk_e,y
        iny
        bne _adj
+       sta sk_e,y
        iny
        inx
        bne _sl
_zr     lda sk_l                ; nollarivi omana segmenttinään (rivit 74..211), tai edellisen jatkona
        cmp #LINE_BOT - 1
        bcs _adj
        cmp #T_LINE + 2
        bcc _adj
        cpy #0
        beq _zn
        sbc sk_e - 1,y          ; C = 1: väli edelliseen
        cmp #8
        lda sk_l
        bcs _zn
        adc #0                  ; C = 0: sk_l + 1
        adc #1
        sta sk_e - 1,y
        bne _adj
_zn     sta sk_s,y
        adc #0                  ; C = 1: sk_l + 1
        sta sk_e,y
        iny
_adj    sty sk_n                ; badline-rivillä alkava segmentti alkaa riviä aiemmin (sky_loop kirjoittaa
        dey                     ; badline-rivin arvon edellisen rivin oikeassa reunassa)
        bmi _top
-       lda sk_s,y
        sec
        sbc #1
        and #7
        cmp bl7m
        bne +
        lda sk_s,y
        sbc #1                  ; C = 1 (cmp ==)
        sta sk_s,y
+       dey
        bpl -
_top    ldx #0                  ; ensimmäinen segmentti ennen riviä SK_TOP: irq_topin taivassilmukka
        lda #1
        ldy sk_n
        beq +
        ldy sk_s
        cpy #SK_TOP
        bcs +
        lda sk_e
        inx
+       sta d21end
        stx sk_first
        rts

; Värimuisti seuraavaan asetteluun kolmessa osassa (COLSTAGE -> $d800):
;   ennen vaihtoa: rivi kerrallaan rivit 0..c-1, joita näkyvä asettelu ei näytä (crunch-rivit eivät
;     lue värimuistia), kun takapankki on valmis
;   vaihtokehys: rivit 4..19 ennen riviä 44 (col_sw; seuraava kehys näyttää rivit 0..19)
;   seuraava kehys: rivit 20..24 (tarvitaan vasta, kun c >= 2)
col_frame
        lda colreq
        beq _rest
        lda #0
        sta colreq
        jsr col_sw
        lda #0
        sta colpre
        lda #20
        sta colrest
        rts
_rest   ldx colrest
        beq _pre
        cpx #ROWS_BANK
        bcs +
-       jsr col_row
        inx
        cpx #ROWS_BANK
        bcc -
+       lda #0
        sta colrest
        rts
_pre    lda ready
        beq +
        ldx colpre
        cpx cc
        bcs +
        jsr col_row
        inc colpre
+       rts

; vaihtokehys: rivit 4..19 sarakkeittain (noin 5 900 sykliä; rivit 0..3 on kirjoitettu ennen vaihtoa,
; logic_frame vaatii colpre >= 4)
col_sw  ldx #39
-
        .for r := 4, r < 20, r += 1
        lda COLSTAGE + r * 40,x
        sta $d800 + r * 40,x
        .next
        dex
        bpl -
        rts


        .if HAVE_MUSIC && !INTEGRATED
        .include "../../music/music.asm"
        .endif

        .include "sprites.asm"

sk_s    .fill 8                 ; kehyksen taivassegmentit: alkurivi, loppurivi (poissuljettu)
sk_e    .fill 8
sk_n    .byte 0
sk_i    .byte 0
sk_first .byte 0                ; 1 = ensimmäinen segmentti irq_topin taivassilmukassa
sk_l    .byte 0                 ; nollarivi
cr_topclr .byte 0
SK_TOP  = 82                    ; segmentit ennen tätä riviä irq_topissa (se päättyy noin riville 76)

        .align 256
seq     .fill 32, 0
cr_late .cr_late_edge           ; taivassilmukan kirkon rivit (crunch.asm): sivun vapaassa osassa, koodi ei siirry
spr_frame0                      ; alustuksen spr_frame-kutsu tätä kautta (sama koko): CIA1:n ajastimen B jakso 63
        lda #62                 ; (crunch.asm cr_late_edge; irq_top käynnistää sen joka kehys)
        sta $dc06
        lda #0
        sta $dc07
        jmp spr_frame
        .if INTEGRATED
        .align 256
d21line .fill 256               ; $D021 riveittäin rivinumerolla
d21late .fill 256               ; 1 riveillä, joilla kirkon spritet 3-4 näkyvät (crunch.asm sky_loop)
COLSTAGE .fill 1000             ; seuraavan asettelun värimuisti
        .endif

        .include "tables.inc"
        .if INTEGRATED
        .include "smoke.asm"
        .endif
code_end
        .cerror * > CODE_END, "koodi ja taulut tietueiden päällä: ", format("$%04x", *)
        .virtual CRANE1_END     ; tiedostojen rajat (build.py, tools/gfx/d64.py): CRANE1 = $1a00-crane1_end,
crane1_end                      ; CRANE1B = crane1_end-crane1b_end, CRANE1C = $8c00-$9fff
        .endv
        .virtual CRANE1B_END
crane1b_end
        .endv

        .include "records.inc"

        .if HAVE_MUSIC && !INTEGRATED
        * = MUSIC_LOAD
        .binary "music.bin"
        .endif
