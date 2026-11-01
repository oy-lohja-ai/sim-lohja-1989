; Lopputekstit (partti 6): tekijät ja AI-ilmoitus nousevat spriteriveinä auringonlaskun
; ja Lohjanjärven yllä. 6510 piirtää jokaisen tekstirivin spriteihin (kyltin kirjaimisto) juuri ennen kuin rivi tulee
; ruutuun, ja spritet kierrätetään riveittäin rasteri-IRQ:lla. Vedessä välkkeet ja taivaalla tähdet vaihtavat
; väriä joka kehys (värimuisti), ja kiilto kulkee kirjainten yli. Lopussa aurinko laskee, valot sammuvat, ja keskelle
; jäävät 2026, ZOO ja OY LOHJA AI.
; Data: tools/disk/loppu.py. Kulku: loppu_init (kuva musta), loppu_run (ottaa IRQ:n, palaa kohtauksen lopussa).

        .include "runko.inc"
        .include "gen/timing.inc"

        .weak
TIM_SCENE_LOPPU_START = 3840
TIM_SCENE_LOPPU_END = 4920
        .endweak

LOPPU_AT = $8000                ; LOPPU1: koodi, kirjaimisto, tekstit (ladataan kodin aikana: kodin muisti $c000-$ffff)
SPR     = $4000                 ; VIC-pankki 1: spriterivit NSLOT x 512 t
NSLOT   = 12
SCR     = $5800                 ; ruutu A (MC-värit %01 ja %10), spriteosoittimet $5bf8; kodin lopussa vapaa (loppu_init)
SCR2    = $5c00                 ; ruutu B, kopio: loppukortin yhtenäisten spriterivien osoittimet vaihtuvat $d018:lla
D18A    = ((SCR & $3fff) / $400) << 4 | ((BMP & $3fff) / $800) << 1
D18B    = ((SCR2 & $3fff) / $400) << 4 | ((BMP & $3fff) / $800) << 1
BMP     = $6000                 ; MC-bittikartta
ROW_H   = 24                    ; spriterivien väli rasteririveinä (tools/disk/loppu.py)
YSTART  = 320                   ; vierityksen nollakohta (pos): rivin 0 yläreuna, kun pos = 0
; Ylä- ja alareuna auki:
; tekstit nousevat alareunan alta ja menevät yläreunan yli. Rivien Y on 9-bittinen (cur_h, yfirst_h, rnext_h): alin
; rivi alkaa enintään riviltä YB - 1 (> 255, spriten Y = rivi - 256). 12 paikkaa x 24 riviä riittää väliin YTOP..YB,
; kun rivit ovat reunoilla mustia (FADE_Y): ylhäällä Y 0-7, alhaalla 264-271, joten rivi syntyy ja poistuu mustana.
TXT_LEAD = 6                    ; tekstirivin tapahtuma riviä ennen (loppu.py ROWL): vesi, badline ja spritet myöhästyttävät
                                ; IRQ:ta, set_ptr odottaa riville Y - 3 (edellisen rivin viimeiset osoittimet luettu)
YTOP    = 4                     ; rivi on näkyvissä, kun sen yläreuna >= YTOP (alin rivi 21 riviä alempana)
YB      = 272                   ; ... ja yläreuna < YB (9 bittiä)
        .cerror YB <= 256 || YB - 256 > 21, "loppu: rivejä yli 255:n enintään yksi (YB - 256 < pienin väli 21)"
BORDER  = 249                   ; reunan avaus: NMI (CIA2 A, kehyksen välein) kirjoittaa RSEL 0 rivin 249 alussa (ikkuna 248-250,
                                ; VIC vertaa riveillä 247 ja 251) eikä odota: lyhyt, loppukortin vaihto ehtii ikkunaansa. IRQ-ketjun
                                ; $d011-kirjoitukset (wr11) käyttävät d11b:tä, jonka NMI asettaa RSEL 0:ksi
TOPLINE = 276                   ; kehyksen IRQ (yli 255, $d011:n bitti 7) alimman rivin (Y < YB) alettua: musiikki,
                                ; vieritys ja ensimmäinen rivi, sitten cli ja välkkeet. Alimmat rivit näkyvät vielä
                                ; riville 291 asti, joten spritejen rekisterit vasta ensimmäisen rivin tapahtumassa (first_ev)
X0      = 24 + 64               ; spriterivin vasen reuna (192 px keskellä)
STOP    = LEN - HOLD            ; loppukortti pysähtyy keskelle (loppu.py STOP), sen jälkeen pito
SUN0    = STOP - 390            ; aurinko laskee horisontin alle, askel SUN_DT kehystä
SUN_DT  = 10
FADE0   = STOP - 300            ; valot sammuvat: NFADE porrasta FADE_DT kehyksen välein (taivas, vesi, aurinko, rivit
FADE_DT = 30                    ; paitsi loppukortti)
CARD_DT = 2                     ; loppukortti häipyy mustaan pysähdyttyään: NFADE porrasta CARD_DT kehyksen välein
CARD0   = TIM_SCENE_LOPPU_END - NFADE * CARD_DT - 4 ; häivytyksen alku: kortti seisoo pidon (5 s pysähtyneenä ennen
                                ; häivytystä mustaan), musta ennen loppua
LEN     = TIM_SCENE_LOPPU_END - TIM_SCENE_LOPPU_START
POS_MAX = YSTART + ROWSPAN - YCENTER     ; ROWSPAN: rivivälien summa (loppu.inc, loppukortin rivit 21 rivin välein)
POS0    = YSTART - Y0               ; Y0, YCENTER ja HOLD: loppu.inc (loppu.py lisää tyhjiä rivejä, jotta matka = LEN - HOLD)
SPEED   = 256                       ; vieritys 8.8 px/kehys: tasan 1 px joka kehys (pehmeä vieritys)
        .cerror SPEED != 256, "loppu: irq_top vierittää 1 px kehyksessä DFRAMEsta"
        .cerror POS_MAX - POS0 != LEN - HOLD, "loppu: vierityksen matka ", POS_MAX - POS0, " != ", LEN - HOLD, " (loppu.py LEN)"

        .virtual $f0            ; nollasivu (osan alue $f0-$ff)
rp      .word ?                 ; tekstirivin data
sb      .word ?                 ; spriterivin alku
pa      .word ?                 ; kirjaimen sarake
pb      .word ?                 ; viereinen sarake
gp      .word ?                 ; kirjaimen data
gx      .byte ?
gy      .byte ?
gn      .byte ?                 ; kirjaimen rivit
gb      .byte ?                 ; tavusarake
        .endv
        .virtual $a9            ; IRQ:n avautuminen (open_step)
oz      .fill 4
        .endv
        .virtual $ad            ; pääsäikeen liukeneminen (dissolve)
dz      .word ?
dm      .word ?
        .endv
        .virtual $a2            ; (koti käyttää $02-$a1: loppu_init kodin aikana)
ri      .byte ?                 ; tekstirivin lukukohta
gcol    .byte ?
gidx    .byte ?
gbyte   .byte ?
sh      .byte ?
slo     .byte ?
cnt     .byte ?
        .endv

        * = LOPPU_AT
loppu_pre                       ; ei kutsuta (koti -> loppu on jatkuva); symboli jää levy.json:n ja part-loppu.json:n
        rts                     ; vientilistaan
pre_done .byte 0

loppu_show                      ; kuva ja otsikkorivi näkyviin ilman IRQ:ta (osalevyllä ennen kelloa: kehys 0 ei musta)
        jsr vis_init
        lda #2                  ; pankki 1, ruutu SCR, bittikartta BMP, MC (sarakkeet kuten loppu_run)
        sta $dd00
        lda #((SCR & $3fff) / $400) << 4 | ((BMP & $3fff) / $800) << 1
        sta $d018
        lda #WBASE
        sta $d016
        lda #0
        sta $d020
        sta $d021
        sta $7fff               ; idle-kuvio avatuissa reunoissa mustaksi
        lda #$3b
        sta $d011
        lda #$80
        sta $d010
        .for i := 0, i < 8, i += 1
        lda #<(X0 + 24 * i)
        sta $d000 + 2 * i
        lda #<Y0
        sta $d001 + 2 * i
        lda #(SPR & $3fff) / 64 + i
        sta SCR + $3f8 + i
        lda #1
        sta $d027 + i
        .next
        lda #0
        sta $d01c
        sta $d017
        sta $d01d
        sta $d01b
        sta $d015               ; otsikko on kehyksellä 0 vielä alareunan mustassa (kehys 0 = kodin kuva)
        rts

scr_copy                        ; ruutu taustasta (LOPPU1) pankkiin 1 (kodin aikana vapaa)
        ldx #0
-       .for p := 0, p < 4, p += 1
        lda scr_src + p * 250,x
        sta SCR + p * 250,x
        sta SCR2 + p * 250,x
        .next
        inx
        cpx #250
        bne -
        rts

col_copy                        ; värimuisti taustasta (näkyy heti: vasta kun kuva vaihtuu loppuun)
        ldx #0
-       .for p := 0, p < 4, p += 1
        lda col_src + p * 250,x
        sta $d800 + p * 250,x
        .next
        inx
        cpx #250
        bne -
        rts

scr_to  .macro                  ; ruutu taustasta (LOPPU1) ruutuun \1
        ldx #0
-       .for p := 0, p < 4, p += 1
        lda scr_src + p * 250,x
        sta \1 + p * 250,x
        .next
        inx
        cpx #250
        bne -
        .endm

col_rows                        ; jatkuva siirtymä: värimuisti kaksi riviä kerrallaan ylhäältä alas säteen edellä (23 sykliä
        .for r := 0, r < 24, r += 2 ; kahdelta tavulta, säde 8 x 63 - 40 sykliä merkkiriviltä), noin 11 600 sykliä
        ldx #39
-       lda col_src + r * 40,x
        sta $d800 + r * 40,x
        lda col_src + r * 40 + 40,x
        sta $d800 + r * 40 + 40,x
        dex
        bpl -
        .next
        ldx #39
-       lda col_src + 24 * 40,x
        sta $d800 + 24 * 40,x
        dex
        bpl -
        rts

loppu_init                      ; kodin aikana (koti -> loppu jatkuva): muuttujat ja ruutu A (SCR $5800-$5be7, jonka
        lda pre_done            ; koti_build vapautti); ei näyttöä, värimuistia eikä kodin muistia (bss $4000-$47ff,
        bne +                   ; KOTI5 $4800-, $c000-$ffff, nollasivu $02-$a1)
        #scr_to SCR
        jmp vars_init
+       rts

vis_scr                         ; ruutu ja värimuisti (kodin viimeisessä kuvassa bittikartta on tyhjä: $d800 ei näy)
        lda vis_done
        bne +
        inc vis_done
        jsr scr_copy
        jmp col_copy
+       rts

vis_init                        ; näkyvä osa ennen kelloa (loppu_show): ruutu, värimuisti, spriterivit tyhjiksi ja
        lda vis_done            ; otsikkorivi (rivi 0) piirretyksi
        bne _x
        jsr vis_scr
        lda #0
        tax
-       .for p := 0, p < NSLOT * 2, p += 1
        sta SPR + p * 256,x
        .next
        inx
        bne -
        jmp render_due          ; ensimmäinen rivi
_x      rts
vis_done .byte 0

vars_init                       ; vieritys alkuun (otsikkorivi rivillä Y0) ja muuttujat
        ldx #0
        stx first
        stx next
        stx glint
        stx tick
        lda #<POS0              ; otsikko OY LOHJA AI näkyy heti rivillä Y0 (koko demossa jo siirtymässä)
        sta pos
        lda #>POS0
        sta pos+1
        lda #<Y0
        sta yfirst
        lda #>Y0
        sta yfirst_h
        lda #0
        sta sun_d
        sta fade_l
        lda #0
        sta fade_r
        sta fade_left
        ldx #24
-       sta rowlev,x
        dex
        bpl -
        lda #<(TIM_SCENE_LOPPU_START + SUN0 + SUN_DT)
        sta next_sun
        lda #>(TIM_SCENE_LOPPU_START + SUN0 + SUN_DT)
        sta next_sun+1
        lda #<(TIM_SCENE_LOPPU_START + FADE0)
        sta next_fade
        lda #>(TIM_SCENE_LOPPU_START + FADE0)
        sta next_fade+1
        lda #0
        sta card_l
        sta card_s
        sta fix20
        ldx #15
-       lda fade_tab,x          ; taso 0: värit ennallaan
        sta fade_cur,x
        sta fade_sun,x
        sta cfade,x
        sta bg_cur,x
        asl a
        asl a
        asl a
        asl a
        sta bg_hi,x
        dex
        bpl -
        lda #0
        sta bg_l
        sta next_dusk
        sta next_star
        rts

loppu_go                        ; ottaa näytön ja IRQ:n ja piirtää näkyvät rivit; palaa heti (sitten S_LOAD f_loppu3, loppu_run)
        sei                     ; spritejä ei tarvitse tyhjätä: render tyhjää paikan ennen kuin rivi näkyy
        lda #2                  ; VIC-pankki 1 (Krill: $dd00:aan vain 0-3)
        sta $dd00
        lda #((SCR & $3fff) / $400) << 4 | ((BMP & $3fff) / $800) << 1
        sta $d018
        lda #WBASE              ; MC (WAVE: 38 saraketta, veden aallot vierittävät merkkirivejä; koti: 40 kuten kodissa)
        sta $d016
        lda #0
        sta $d020
        sta $d021
        sta $d01c               ; hires-spritet kuvan edessä ($d015: kehyksen IRQ)
        sta $d017
        sta $d01d
        sta $d01b
        lda #$80                ; spritet X0 + 24 i, sprite 7 yli 255
        sta $d010
        .for i := 0, i < 8, i += 1
        lda #<(X0 + 24 * i)
        sta $d000 + 2 * i
        .next
        lda #0                  ; idle-kuvio avatuissa reunoissa mustaksi (pankki 1: $3fff)
        sta $7fff
        lda #<TOPLINE           ; bittikartta, 25 riviä, kuva päälle
        jsr top_at
        lda vis_done            ; jatkuva siirtymä (ei S_SHOW:ta): kodin viimeisen kehyksen jälkeen reunuksessa ruutu A on
        bne +                   ; valmiina (loppu_init), joten seuraava kehys on jo lopun kuva, kun värimuisti kopioidaan
        sta $d015               ; säteen edellä ennen IRQ:ta (vis_scr veisi 1,5 kehystä: musta kehys, DFRAME seisoisi);
        jsr col_rows            ; kodin spritet pois, kehyksen IRQ (TOPLINE) ottaa spritet seuraavasta kehyksestä
        lda #0                  ; järven välke jo kehykseen 0: koti välkkyi viimeiseen kehykseensä asti
        sta rel
        sta rel+1
        inc vk_go
        jsr vk_step
+       lda #1
        sta $d01a
        sta $d019
        sta vk_go               ; järven välke heti (data LOPPU1:ssä)
        cli
        jsr nmi_on              ; reunat auki (NMI rivillä 251)
        lda vis_done
        bne +
        inc vis_done
        #scr_to SCR2            ; ruutu B (loppukortti) vasta kodin jälkeen: koti4_live- on kodin käytössä loppuun asti
+       ldx #NSLOT              ; paikat täyteen ennen loppukortin logojen latausta (LOPPU3, linkkiskripti), jonka aikana
-       txa                     ; rivejä ei piirretä (uusi paikka vapautuu 24 kehyksen välein)
        pha
        jsr render_due
        pla
        tax
        dex
        bne -
        rts

render_due                      ; piirtää rivin next, jos sen paikka on vapaa ja se tulee pian näkyviin
        lda next
        cmp #ROWS
        bcs _no
        sec                     ; vapaa: rivi next - NSLOT on jo poistunut (next - first < NSLOT)
        sbc first
        cmp #NSLOT
        bcs _no
        lda next
        jsr render
        inc next
_no     rts

; ---------------------------------------------------------------- loppu: aurinko laskee ja valot sammuvat
ending                          ; pääsäikeestä: auringon taso kiinni DFRAME:en (pääsäie voi jäädä jälkeen, jolloin
        lda sun_d               ; välitasot ohitetaan); valojen tasot kehyksen IRQ:ssa (fade_tick)
        sta sd
_s      lda sun_d
        cmp #SUN_R
        bcs +
        lda DFRAME
        cmp next_sun
        lda DFRAME+1
        sbc next_sun+1
        bcc +
        inc sun_d
        lda next_sun
        adc #SUN_DT - 1         ; C = 1
        sta next_sun
        bcc _s
        inc next_sun+1
        bcs _s
+       lda sun_d
        cmp sd
        beq +
        jsr sun_set
        lda #1                  ; heijastuksen välkkeiden taulu kehyksen IRQ:ssa (fade_tick)
        sta sun_dirty
+
_x      rts

bg_level                        ; A = taustan taso: värit ruudulle ja värimuistiin pyyhkäisyllä (fade_row)
        sta bg_l
        asl a
        asl a
        asl a
        asl a
        tax
        ldy #0
-       lda fade_tab,x
        sta bg_cur,y
        asl a
        asl a
        asl a
        asl a
        sta bg_hi,y
        inx
        iny
        cpy #16
        bne -
        lda #25                 ; pyyhkäisy jatkaa siitä rivistä, jossa se on, ja kiertää koko ruudun uudella tasolla
        sta fade_left
        rts

dusk_tick                       ; kehyksen IRQ:sta: taivas tummuu (taustan tasot 1..DUSK_N ajallaan) ja tähdet syttyvät
        ldx next_dusk
        cpx #DUSK_N
        bcs _st
        lda DFRAME
        cmp dusk_lo,x
        lda DFRAME+1
        sbc dusk_hi,x
        bcc _st
        inc next_dusk
        txa
        clc
        adc #1
        cmp bg_l
        beq _st
        bcc _st
        jsr bg_level
_st     ldx next_star
        cpx #STARS_N
        bcs _x
        lda DFRAME
        cmp star_lo,x
        lda DFRAME+1
        sbc star_hi,x
        bcc _x
        inc next_star
        lda star_ilo,x          ; ryhmän taulu syttyy (32 tavua dyn_tabiin)
        sta oz
        lda star_ihi,x
        sta oz+1
        txa
        asl a
        asl a
        asl a
        asl a
        asl a
        tax
        ldy #0
-       lda star_on,x
        sta (oz),y
        inx
        iny
        cpy #32
        bne -
_x      rts
dusk_lo .for t in DUSK_T
        .byte <(TIM_SCENE_LOPPU_START + t)
        .next
dusk_hi .for t in DUSK_T
        .byte >(TIM_SCENE_LOPPU_START + t)
        .next
star_lo .for t in STAR_T
        .byte <(TIM_SCENE_LOPPU_START + t)
        .next
star_hi .for t in STAR_T
        .byte >(TIM_SCENE_LOPPU_START + t)
        .next
star_ilo .for o in STAR_I
        .byte <(dyn_tab + o)
        .next
star_ihi .for o in STAR_I
        .byte >(dyn_tab + o)
        .next
star_on .byte STAR_ON

fade_tick                       ; kehyksen IRQ:sta (DFRAME juuri kasvanut): uusi valotaso ajallaan, heijastuksen taulu
        jsr dusk_tick
        lda fade_l
        cmp #NFADE
        bcs _sun
        lda DFRAME
        cmp next_fade
        lda DFRAME+1
        sbc next_fade+1
        bcc _sun
        inc fade_l
        lda next_fade
        adc #FADE_DT - 1        ; C = 1
        sta next_fade
        bcc +
        inc next_fade+1
+       jsr fade_level          ; asettaa sun_dirtyn
_sun    lda sun_dirty
        beq +
        lda #0
        sta sun_dirty
        jmp sun_table
+       rts

fade_row                        ; kehyksen IRQ:sta: merkkirivin fade_r puolikas (A = 0 sarakkeet 0-19, 1 sarakkeet 20-39)
        tay                     ; ruutuun ja värimuistiin lähteistä (LOPPU1) himmennettyinä: pyyhkäisy ylhäältä alas
        bne _go                 ; kiertäen, raja on aina yksi taso. Rivi ohitetaan, jos sen värit eivät muutu
        ldx fade_r              ; viimeksi piirretyn tason ja nykyisen välillä (ROWMASK, loppu.py)
        lda rowmask,x
        ldy bg_l
        and lomask,y
        ldy rowlev,x
        and himask,y
        sta fskip
        beq _no
        lda bg_l
        sta rowlev,x
        ldy #0
_go     lda fskip
        bne +
_no     rts
+       lda half_y0,y
        sta _y0+1
        lda half_end,y
        sta _end+1
        ldx fade_r
        lda ps_lo,x
        sta _s1+1
        sta _s2+1
        lda ps_hi,x
        sta _s1+2
        sta _s2+2
        lda pc_lo,x
        sta _c1+1
        lda pc_hi,x
        sta _c1+2
        lda pd_lo,x
        sta _d1+1
        sta _d3+1               ; ruudun kopio (SCR2) samalla siirroksella
        lda pd_hi,x
        sta _d1+2
        clc
        adc #((SCR2 - SCR) >> 8) & $ff
        sta _d3+2
        lda pk_lo,x
        sta _d2+1
        lda pk_hi,x
        sta _d2+2
_y0     ldy #39
_s1     lda $ffff,y
        and #$0f
        tax
        lda bg_cur,x
        sta fv
_s2     lda $ffff,y
        lsr a
        lsr a
        lsr a
        lsr a
        tax
        lda bg_hi,x
        ora fv
_d1     sta $ffff,y
_d3     sta $ffff,y
_c1     ldx $ffff,y
        lda bg_cur,x
_d2     sta $ffff,y
        dey
_end    cpy #$ff
        bne _s1
        rts

slot_blank .fill NSLOT + 1, 0    ; paikka (ja välipuskuri) on tyhjä (render)
half_y0 .byte 19, 39
rowlev  .fill 25, 0               ; rivin viimeksi piirretty taso
fskip   .byte 0
lomask  .byte 0, 1, 3, 7, 15, 31, 63, 127, 255   ; tasot 1..l (bitti l - 1)
himask  .byte 255, 254, 252, 248, 240, 224, 192, 128, 0
rowmask .byte ROWMASK            ; tasot, joilla rivin värit muuttuvat
half_end .byte $ff, 19
fade_cur .fill 16
bg_cur  .fill 16                ; taustan (ruutu ja värimuisti) värit tasolla bg_l = max(hämärä, valot)
bg_hi   .fill 16
bg_l    .byte 0
next_dusk .byte 0               ; seuraava hämärän taso (indeksi dusk_t:hen)
next_star .byte 0               ; seuraava tähtiryhmä
fade_sun .fill 16
fv      .byte 0                 ; fade_row:n väliaikainen (IRQ)
sun_d   .byte 0
fade_l  .byte 0
fade_r  .byte 0                 ; pyyhkäisyn seuraava merkkirivi (kiertää)
fade_left .byte 0               ; rivejä jäljellä nykyisellä tasolla
sun_dirty .byte 0               ; pääsäie: aurinko liikkui, IRQ laskee fade_sunin
next_sun .word 0
next_fade .word 0
sd      .byte 0
ss      .byte 0

; ---------------------------------------------------------------- piirto: tekstirivi spriteriviin
render  tax                     ; A = rivi; paikka = rivi mod NSLOT
        lda row_lo,x
        sta rp
        lda row_hi,x
        sta rp+1
        txa
-       cmp #NSLOT
        bcc +
        sbc #NSLOT
        bcs -
+       tax                     ; X = paikka
        asl a                   ; 512 t / paikka
        adc #>SPR
        sta sb+1
render_at                       ; rp, sb+1 (sivun raja) ja X = tyhjä-lippu (paikka, NSLOT = välipuskuri) valmiina
        lda #0
        sta sb
        tay
        lda (rp),y              ; loppukortin logo: 8 spriteä x 63 tavua valmiina (LOGO_AT, loppu.py)
        cmp #$fc
        bne _nl
        lda #0
        sta slot_blank,x
        iny
        lda (rp),y
        sta gp
        iny
        lda (rp),y
        sta gp+1
        ldx #8
_lg     ldy #62
-       lda (gp),y
        sta (sb),y
        dey
        bpl -
        lda gp
        clc
        adc #63
        sta gp
        bcc +
        inc gp+1
+       lda sb
        clc
        adc #64
        sta sb
        bcc +
        inc sb+1
+       dex
        bne _lg
        rts
_nl     lda (rp),y              ; tyhjä rivi tyhjään paikkaan: ei mitään tehtävää (tyhjiä rivejä 34, pääsäikeen aika
        cmp #$ff                ; rivien piirtoon ja aurinkoon)
        bne +
        lda slot_blank,x
        bne _done
        lda #1
        .byte $2c               ; bit abs: ohittaa seuraavan lda:n
+       lda #0
        sta slot_blank,x
        lda #0                  ; tyhjäksi
-       sta (sb),y
        iny
        bne -
        inc sb+1
-       sta (sb),y
        iny
        bne -
        dec sb+1
        sty ri                  ; Y = 0
_line   ldy ri
        lda (rp),y
        cmp #$ff
        beq _done
        sta gx
        iny
        lda (rp),y
        sta gy
        iny
_ch     lda (rp),y
        iny
        cmp #$fd
        beq _eol
        cmp #$fe
        bne _gl
        lda (rp),y              ; väli
        iny
        clc
        adc gx
        sta gx
        jmp _ch
_gl     sty ri
        jsr glyph
        jsr ending              ; auringon askel kirjainten välissä (rivin piirto kestää kymmeniä kehyksiä)
        ldy ri
        jmp _ch
_eol    sty ri
        jmp _line
_done   rts

glyph   tax                     ; X = kirjain: piirtää kohtaan gx, gy (spriterivin pikselit) ja siirtää gx:ää
        lda gl_lo,x
        sta gp
        lda gl_hi,x
        sta gp+1
        lda gl_nb,x
        sta gb
        lda gl_h,x
        sta gn
        lda gl_w,x
        pha
        lda gx
        and #7
        sta sh
        lda gx
        lsr a
        lsr a
        lsr a
        sta gcol
        lda #0
        sta gbyte
_col    ldx gcol                ; tavusarake: sen ja seuraavan sarakkeen osoitteet spriterivissä
        lda colofs_lo,x
        clc
        adc sb
        sta pa
        lda colofs_hi,x
        adc sb+1
        sta pa+1
        lda colofs_lo+1,x
        clc
        adc sb
        sta pb
        lda colofs_hi+1,x
        adc sb+1
        sta pb+1
        lda gy                  ; spriterivin tavu = 3 * (gy + r)
        asl a
        adc gy
        sta cnt
        ldx gn
        ldy gbyte
_row    lda (gp),y              ; kirjaimen tavu siirrettynä sh pikseliä oikealle: 16 bittiä kahteen sarakkeeseen
        sty gidx
        ldy sh
        beq _put
        sta slo
        lda #0
-       lsr slo
        ror a
        dey
        bne -
        ldy cnt
        ora (pb),y
        sta (pb),y
        lda slo
_put    ldy cnt
        ora (pa),y
        sta (pa),y
        iny
        iny
        iny
        sty cnt
        lda gidx
        clc
        adc gb
        tay
        dex
        bne _row
        inc gcol
        inc gbyte
        lda gbyte
        cmp gb
        bne _col
        pla
        clc
        adc gx
        sta gx
        rts

; spriterivin tavusarake c: (c / 3) * 64 + c mod 3. Sarake 24 = sarake 23: kirjain ei ulotu 192 px:n yli
; (tools/disk/loppu.py), joten sinne OR-ataan vain nollia.
colofs_lo .for c := 0, c < 25, c += 1
        .byte <(((c < 23 ? c : 23) / 3) * 64 + (c < 23 ? c : 23) % 3)
        .next
colofs_hi .for c := 0, c < 25, c += 1
        .byte >(((c < 23 ? c : 23) / 3) * 64 + (c < 23 ? c : 23) % 3)
        .next

; ---------------------------------------------------------------- IRQ
irq_top pha                     ; rivi TOPLINE: musiikki, vieritys ja ensimmäinen rivi, sitten cli ja välkkeet
        txa
        pha
        tya
        pha
_body   asl $d019               ; (irq_ev hyppää tähän, jos tämän rivi meni ohi)
        jsr FRAME_HOOK          ; musiikki ennen cli:tä (muuten rivien IRQ:t veisivät sen ajan loppukortin aikana)
        lda DFRAME
        sta now
        lda DFRAME+1
        sta now+1
        lda now                 ; rel = kehys kohtauksen alusta: vieritys, kiilto, aallot, välke ja tick siitä, joten
        sec                     ; osalevy ja koko demo (jossa lopun tiedostot latautuvat myöhemmin) kulkevat samoin
        sbc #<TIM_SCENE_LOPPU_START
        sta rel
        lda now+1
        sbc #>TIM_SCENE_LOPPU_START
        sta rel+1
        jsr card_tick
        lda pos+1               ; vieritys kunnes loppukortti on keskellä
        cmp #>POS_MAX
        bcc +
        lda pos
        cmp #<POS_MAX
        bcs _still
+       lda rel                 ; 1 px kehyksessä (SPEED 256): px = POS0 + rel - pos, 0-2 (myöhässä alkanut vieritys
        clc                     ; kirii 2 px kehyksessä)
        adc #<POS0
        tax
        lda rel+1
        adc #>POS0
        tay
        txa
        sec
        sbc pos
        tax
        tya
        sbc pos+1
        bmi _still
        bne _two
        txa
        beq _still
        cmp #3
        bcc +
_two    ldx #2
+                               ; px tällä kehyksellä (X)
-       inc pos
        bne +
        inc pos+1
+       lda yfirst              ; ylin rivi 1 px ylemmäs (9 bittiä: alussa otsikko on alareunan alla)
        bne +
        dec yfirst_h
+       dec yfirst
        lda yfirst_h
        bne +
        lda yfirst
        cmp #YTOP
        bcs +
        ldy first               ; ylin rivi poistui: seuraava on ensimmäinen (C = 0, alle 256)
        adc rowh,y
        sta yfirst
        inc first
+       dex
        bne -
_still  lda rel
        sta glint
        ldx #WBASE              ; taivas ilman vieritystä: kehys 0 40 saraketta (kodin kuva), sitten 38 (aallon vieritys
        lda ot                  ; jää reunan alle)
        beq +
        ldx #$10
+       stx $d016
        stx wbase
        lda #0
        sta wi
        lda wline
        sta wnext
        lda #$ff
        sta rnext
        lda #$80
        sta rnext_h
        lda #1
        sta fresh               ; ensimmäisen rivin tapahtuma: Y, ruutu A ja hires (first_ev)
        lda #$3b                ; RSEL 1 seuraavan kehyksen IRQ-ketjulle (NMI vaihtaa rivillä 249)
        sta d11b
        lda #$ff                ; Y riville 255 (alimmat rivit jatkuvat: Y:n vaihto ei katkaise näkyvää spriteä), jottei
        .for i := 0, i < 8, i += 1  ; alimman rivin Y - 256 täsmää seuraavan kehyksen yläreunassa ennen first_ev:tä
        sta $d001 + 2 * i
        .next
        lda #0
        sta act
        jsr irq_ev._rjoff
        lda #<set_ptr
        sta irq_ev._rs + 1
        lda #>set_ptr
        sta irq_ev._rs + 2
        lda fix20               ; alareunassa lainattu rivi 20 takaisin
        beq +
        jsr fix_back
+       jsr bl_scan             ; badlinella alkavat loppukortin rivit: rivi 20 lainaan
        lda first               ; ensimmäinen näkyvä rivi: Y nyt (edellisen kehyksen rivit ovat jo päättyneet),
        cmp #ROWS               ; Y, osoittimet ja värit sen omassa tapahtumassa juuri ennen riviä (first_ev)
        bcs _off
        sta cur
        lda yfirst_h
        sta cur_h
        beq +
        lda yfirst
        cmp #<YB
        bcs _off
+       lda yfirst
        sta cur_y
        ldx cur                 ; värit: tekstirivi calc_col:lla, loppukortin rivi suoraan rekistereihin (set_card ei
        cpx #KEEP_FROM          ; kirjoita yhtenäisen rivin värejä)
        bcs _kf
        jsr calc_col
        jmp _kr
_kf     jsr card_first
_kr     ldx cur                 ; tapahtuma rowl riviä ennen riviä (teksti 6, loppukortti 14, yhtenäinen 20), vähintään
        lda cur_y               ; rivillä 6 (tämä IRQ on edellisen kehyksen alareunassa; rivit Y < 8 ovat mustia)
        sec
        sbc rowl,x
        sta rnext
        lda cur_h
        sbc #0
        sta rnext_h
        bmi _r2
        bne +
        lda rnext
        cmp #BORDER - 5
        bcc ++
+       lda #BORDER - 5         ; alussa otsikko riveillä 247-: tapahtuma viimeistään rivillä 243, jotta first_ev kirjoittaa
        sta rnext               ; Y:n ennen kuin pysäköity Y 255 täsmää (ja ennen reunan avausta)
        lda #0
        sta rnext_h
        beq _sch
+       lda rnext
        cmp #6
        bcs _sch
_r2     lda #6                  ; (rivit Y < 8 ovat mustia: myöhästyvä first_ev ei näy)
        sta rnext
        lda #0
        sta rnext_h
        beq _sch
_off    lda #0                  ; ei rivejä (vain alussa ennen otsikkoa: alareunassa ei näy mitään)
        sta $d015
_sch    jsr schedule
        asl $d019               ; vertailurivin kirjoitus ei saa herättää irq_ev:tä nyt (seuraavan kehyksen tapahtumat
        jsr rast                ; näyttäisivät myöhästyneiltä). Jos tämä IRQ alkoi myöhään (alimmat rivit veivät ajan) ja
        bmi +                   ; ensimmäisen rivin tapahtuma meni jo, suoraan siihen (sama pino), muuten koko kehys
        lda tgth                ; jäisi ilman rivejä ja kehyksen IRQ:ta; häntä jää tältä kehykseltä
        bne +
        lda rr
        cmp tgt
        bcc +
        jmp irq_ev._loop
+       cli                     ; häntä keskeytettävänä
        lda ot                  ; veden merkkirivien vieritys tälle kehykselle (vesi alkaa riviltä WROW0 * 8 + 50, joten
        cmp #OPEN_N             ; tämä ehtii cli:n jälkeen): aalto, kun letterbox on auki, sitä ennen ilman vieritystä
        bcc +
        jsr waves
        jmp ++
+       lda wbase
        ldy #WROWS - 1
-       sta wtab,y
        dey
        bpl -
+
        lda rel                 ; kehys 0 ilman häntää: IRQ:lla se on vain koko demon jatkuvassa siirtymässä (osalevyllä
        ora rel+1               ; ensimmäinen IRQ on kehys 1), joten letterbox ja tick kulkevat kuten osalevyllä
        beq _sk
        lda tail_on             ; edellisen kehyksen välkkeet vielä kesken (rivien IRQ:t veivät ajan): tämä kehys ilman,
        bne _sk                 ; muuten sisäkkäinen kutsu sotkisi fade_row:n itseään muokkaavat osoitteet
        inc tail_on             ; välkkeet sisäkkäin: rivien IRQ:t keskeyttävät
        jsr open_step
        jsr vk_step
        jsr hw_step
        jsr fade_tick
        inc tick                ; vain hännän ajoista: fade_row:n puolikkaat pareittain (välkkeet relistä)
        lda bg_l                ; ennen hämärää välkkeet: värit ja kaikki solut parillisella
        bne _fade
        lda ot                  ; (kehys 0 = kodin kuva: välkkeet alkavat, kun letterbox on auki)
        cmp #OPEN_N
        bcc _sx
        lda rel                 ; välkkeiden ja tähtien tuikkeen vaihe kohtauksen kehyksestä (osalevy = koko demo)
        lsr a
        bcs _sx
        and #15
        jsr shim_rot
        jsr shim_q0
        jsr shim_q1
        jsr shim_q2
        jsr shim_q3
        jmp _sx
_fade   lda rel                 ; sammumisen aikana (työ mahtuu aina kehykseen) joka kehys
        and #3                  ; neljäsosa välkkeistä (värit joka 4. kehys) ja puoli merkkiriviä valojen pyyhkäisyä
        bne +                   ; (vasen parillisella, oikea parittomalla), jolloin rintama etenee joka kehys ja
        lda rel                 ; pääsäikeelle jää aikaa rivien piirtoon ja aurinkoon
        lsr a
        and #15
        jsr shim_rot
        jsr shim_q0
        jmp _fr
+       cmp #1
        bne +
        jsr shim_q1
        jmp _fr
+       cmp #2
        bne +
        jsr shim_q2
        jmp _fr
+       jsr shim_q3
_fr     lda fade_left
        beq _sx
        lda tick
        and #1
        pha
        jsr fade_row
        pla
        beq _sx
        dec fade_left
        ldx fade_r
        inx
        cpx #25
        bcc +
        ldx #0
+       stx fade_r
_sx     sei
        dec tail_on
_sk     pla
        tay
        pla
        tax
        pla
        rti
tail_on .byte 0
wbase   .byte WBASE             ; $d016 tällä kehyksellä (aallon pohja)

open_step                       ; letterbox avautuu (kehyksissä 1..OPEN_N): kuvarivit open.bin:stä OPEN_CNT[ot] asti
        ldx ot
        cpx #OPEN_N
        bcs _x
        inx
        stx ot
        lda open_cnt,x
        sta otgt
_l      ldx oc
        cpx otgt
        bcs _x
        lda open_lo,x           ; kohde: kuvarivin 40 tavua 8 tavun välein (32 + 8 sarakkeen puolikkaat)
        sta oz
        lda open_hi,x
        sta oz+1
        lda osrc_lo
        sta oz+2
        lda osrc_hi
        sta oz+3
        ldx #0
        ldy #0
-       lda (oz+2,x)            ; X = 0: (oz+2) = lähde
        sta (oz),y
        inc oz+2
        bne +
        inc oz+3
+       tya
        clc
        adc #8
        tay
        bne -
        inc oz+1                ; sarakkeet 32-39
-       lda (oz+2,x)
        sta (oz),y
        inc oz+2
        bne +
        inc oz+3
+       tya
        clc
        adc #8
        tay
        cpy #64
        bne -
        lda oz+2
        sta osrc_lo
        lda oz+3
        sta osrc_hi
        inc oc
        bne _l
_x      rts
vk_step                         ; järven välke (loppu_go:sta, vk_go): vaihe (rel / VK_DT) mod VK_N bittikarttaan,
        lda vk_go               ; edellinen pois; valojen sammuessa (fade_l) viimeinen vaihe pois ja loppu
        beq _x
        lda fade_l
        beq _ph
        lda vk_on
        beq _x
        lda #0
        sta vk_on
        sta vk_go
        ldx vk_p
        lda #3
        jmp vk_apply
_ph     lda rel                 ; rel mod VK_DT * VK_N (256 = 256 % VK_M rel+1:n jokaista yksikköä kohden)
-       cmp #VK_M
        bcc +
        sbc #VK_M
        bcs -
+       ldx rel+1
        beq _m
-       clc
        adc #256 % VK_M
        cmp #VK_M
        bcc +
        sbc #VK_M
+       dex
        bne -
_m      ldx #$ff                ; vaihe = (rel mod VK_M) / VK_DT
        sec
-       inx
        sbc #VK_DT
        bcs -
        txa
        ldx vk_on
        beq _on
        cmp vk_p
        beq _x
        pha
        ldx vk_p
        lda #3
        jsr vk_apply
        pla
_on     sta vk_p
        lda #1
        sta vk_on
        ldx vk_p
        lda #2
        jmp vk_apply
_x      rts

hw_step                         ; kodin käsiala liukenee taivaaseen: kehyksestä HW_T0 HW_PF tietuetta
        lda hw_left             ; kehyksessä (osoite, uusi tavu: hw_rec, loppu.py kasiala), yksi pikseli tietueessa
        ora hw_left+1
        beq _x
        lda DFRAME
        cmp #<(TIM_SCENE_LOPPU_START + HW_T0)
        lda DFRAME+1
        sbc #>(TIM_SCENE_LOPPU_START + HW_T0)
        bcc _x
        ldx #HW_PF
_l      jsr _rd
        sta oz
        jsr _rd
        sta oz+1
        jsr _rd
        ldy #0
        sta (oz),y
        lda hw_left
        bne +
        dec hw_left+1
+       dec hw_left
        lda hw_left
        ora hw_left+1
        beq _x
        dex
        bne _l
_x      rts
_rd     lda hw_rec
        inc _rd+1
        bne +
        inc _rd+2
+       rts
hw_left .word HW_N

vk_apply                        ; X = vaihe, A = 2 (päälle) tai 3 (pois): tietueet (osoite, päällä, pois) bittikarttaan
        sta _o+1
        lda vk_lo,x
        sta oz
        lda vk_hi,x
        sta oz+1
        lda vk_lo+1,x
        sta vk_e
        lda vk_hi+1,x
        sta vk_e+1
_l      lda oz
        cmp vk_e
        lda oz+1
        sbc vk_e+1
        bcs _x
        ldy #0
        lda (oz),y
        sta oz+2
        iny
        lda (oz),y
        sta oz+3
_o      ldy #2
        lda (oz),y
        ldy #0
        sta (oz+2),y
        lda oz
        clc
        adc #4
        sta oz
        bcc _l
        inc oz+1
        bne _l
_x      rts
vk_go   .byte 0                 ; loppu_go: välke päällä
vk_on   .byte 0
vk_p    .byte 0
vk_e    .word 0

ot      .byte 0                 ; kehys avautumisessa
oc      .byte 0                 ; avattuja kuvarivejä
otgt    .byte 0
osrc_lo .byte <open_src
osrc_hi .byte >open_src

irq_ev  pha                     ; rivin, veden ja reunan tapahtumat: kaikki erääntyneet, sitten seuraava (rivit 9 bittiä:
        txa                     ; rnext_h 0 alle 256, 1 yli, $80 ei tapahtumaa; tekstirivien ja veden polut suorina;
        pha                     ; loppukortti SMC:llä _rj, _rs)
        tya
        pha
        asl $d019
_loop   ldx $d012
        inx
        lda cur                 ; loppukortti: erääntynyt rivin tapahtuma ennen vettä (vaihto on syklitarkka, veden
        cmp #KEEP_FROM          ; vieritys kestää myöhästymisen)
        bcc _wat
        lda rnext_h
        bne _wat
        cpx rnext
        bcs _due
_wat    cpx wnext               ; veden merkkirivi: vieritys ennen riviä (myöhässä vain leikkaa rivin yläosaa)
        bcc _row
        cpx #$ff                ; rivillä 254 X = $ff täsmäisi "ei vettä" -merkkiin (rivit kulkevat reunassa)
        beq _row
        ldy wi
        lda wtab,y
        sta $d016
        iny
        sty wi
        lda wline,y
        sta wnext
        jmp _loop
_row    lda rnext_h
        bne _rh
        cpx rnext               ; rivi alle 256: erääntynyt, tai rasteri jo rivillä 255 (X = 0) tai yli (myöhässä)
        bcs _due
        txa
        beq _due
        bit $d011
        bmi _due
        bpl _done
_rh     bmi _done               ; $80: ei rivin tapahtumaa
        bit $d011               ; rivi yli 256: vasta kun rasterikin on
        bpl _done
        cpx rnext
        bcc _done
_due    lda fresh                ; kehyksen ensimmäinen rivi: Y, ruutu A, hires ja spritet päälle
        beq +
        jsr first_ev
+
_rj     lda cur                 ; spriterivi cur_y - 4: osoittimet ja värit, rivin alettua seuraavan Y
_rs     jsr set_ptr             ; (loppukortilla set_card; _rj = jmp _swt, kun $d018-vaihto odottaa)
_nc     lda cur_h               ; rivi yli 255 on kehyksen viimeinen (YB - 256 < 21): ei odotusta, chain ei löydä seuraavaa
        bne _ch
        ldy cur_y
        ldx cur                 ; seuraava tekstirivi: värit ja tapahtuma odotuksen aikana, Y rivin alettua (muuten
        inx                     ; noin 5 riviä turhaa odotusta: reunat auki rivejä on koko kehyksen, ja IRQ söisi
        cpx #KEEP_FROM          ; musiikin ajan)
        bcs _wt                 ; loppukortti: chain vasta rivin alettua (rivin 20 palautus)
        sty wy
        jsr chain_pre
        php
        ldy wy
-       bit $d011               ; myöhässä yli 255: rivi on jo alkanut
        bmi +
        cpy $d012               ; rivi on alkanut (rivin ylin spriterivi haettu)
        bcs -
+       plp
        bcs _lp
        lda cur_y
        .for i := 0, i < 8, i += 1
        sta $d001 + 2 * i
        .next
_lp     jmp _loop
_wt
-       bit $d011
        bmi _ch
        cpy $d012
        bcs -
_ch     jsr chain
        jmp _loop
_prep   ldx cur                 ; vaihtorivi: yhtenäinen rivi edellisen rivin viimeisellä näkyvällä rasteririvillä (= tämän
        lda rowf,x              ; rivin Y) sen datan haun jälkeen (syklit 11-57). Jos se on badline, CPU ei ehdi siihen
        lsr a                   ; ikkunaan (badline syklit 15-54, spritet 55-10): riviä aiemmin (bl_scan on lainannut rivin
        bcs _pc                 ; lohkoihin edellisen rivin rivin 20). Muu rivi aukossa Y - 2 (spritet ovat pois päältä).
        sta swcol
        lda cur_y
        sec
        sbc #2
        tay
        lda cur_h
        sbc #0
        jmp _pw
_pc     lda #0
        sta swcol
        ldy cur_y
        lda bitv - L20_ROW0,x
        and blmask
        beq +
        dey                     ; badline-tila (rivit $30-$f7)
+       lda cur_h
_pw     sta ysw_h
        sty ysw
        tya
        sec
        sbc #6
        sta rnext               ; herätys 6 riviä ennen vaihtoa (vesi, badline, spritet ja 9-bittinen polku viivästävät)
        lda ysw_h
        sbc #0
        sta rnext_h             ; herätys alle 8 rivin päässä tai ohi: suoraan odotukseen (IRQ:n paluu ja uusi IRQ
        bne +                   ; spritejen ja badlinejen alla veisivät vaihdon ohi; herätys yli 255 IRQ:lla)
        bit $d011
        bmi +
        lda rnext
        sec
        sbc $d012
        bcc _swt
        cmp #8
        bcc _swt
+       lda #$4c                ; jmp _swt
        ldx #<_swt
        ldy #>_swt
        jsr _rjset
        jmp _loop
_swt    lda ysw_h               ; vaihtorivi 9 bittiä: yli 255 odotetaan ensin rasterin bitti 8
        bne _sh
        ldy ysw
-       cpy $d012               ; rivi alle 256: silmukka katsoo myös bitin 8 (rivin 255 ohi mennyt rasteri näyttäisi
        beq _sw                 ; muuten aiemmalta ja odotus jatkuisi seuraavaan kehykseen)
        bcc _late
        bit $d011
        bpl -
        bmi _late
_sh
-       bit $d011
        bpl -
        ldy ysw
_w      cpy $d012
        beq _sw
        bcs _w
        bcc _late               ; myöhässä: vaihto heti
_sw     nop                     ; tunnistus syklissä 4-18, kirjoitus vähintään 11:n jälkeen
        nop
_late   lda d18n
        sta $d018
        lda swcol
        beq _sx
        .for i := 0, i < 8, i += 1
        lda colbuf + i
        sta $d027 + i
        .next
        ldx cur
        ldy rowm,x              ; MC-spritejen %01-väri (logo)
        lda cfade,y
        sta $d025
        lda swcol
        lsr a
        lda #0
        bcc +
        lda #$ff
+       sta $d01c
_sx     jsr _rjoff
        jmp _nc
_done   bit $d011               ; yli 255: veden rivit ohi
        bmi _hz
        lda rnext_h             ; seuraava rivin tai veden tapahtuma alle 3 rivin päässä: odotetaan silmukassa (paluu, schedule
        bne +                   ; ja uusi IRQ veisivät spritejen ja badlinejen alla rivejä, ja osoittimet myöhästyisivät)
        lda rnext
        sec
        sbc $d012
        bcc +
        cmp #3
        bcc _spin
+       lda wnext
        sec
        sbc $d012
        bcc _sc
        cmp #3
        bcs _sc
_spin   jmp _loop
_hz     lda #$ff
        sta wnext
_sc     jsr schedule            ; jos seuraavan tapahtuman rivi ehti jo alkaa (spritet ja badline hidastavat), IRQ jäisi
        bcs _tp                 ; tulematta ja kehyksen IRQ välistä: käsitellään heti
        jsr rast
        bmi _hi
        lda tgth                ; rasteri alle 256: myöhässä, jos tgt alle 256 ja rasteri jo sen rivillä (vertailun
        bne _x                  ; kirjoitus samalle riville ei herätä IRQ:ta)
        lda rr
        cmp tgt
        bcs _lt
        bcc _x
_hi     lda tgth                ; rasteri yli 255: tgt alle 256 on ohi
        beq _lt
        lda rr
        cmp tgt
        bcc _x
_lt     asl $d019               ; rivin IRQ on ehkä jo lukittu: kuitataan, ettei se laukaise seuraavaa vektoria
        jmp _loop
_tp     asl $d019               ; tapahtuman vertailu (käsitelty jo silmukassa) ei saa herättää kehyksen IRQ:ta etuajassa
        jsr rast                ; kehyksen IRQ:n rivi TOPLINE jo ohi: suoraan siihen (sama pino kuin IRQ:ssa)
        bpl _x
        lda rr
        cmp #<TOPLINE
        bcc _x
        jmp irq_top._body
_x      pla
        tay
        pla
        tax
        pla
        rti
_rjoff  lda #$ad                ; _rj takaisin: lda cur
        ldx #<cur
        ldy #>cur
_rjset  sta _rj
        stx _rj + 1
        sty _rj + 2
        rts

nmi_rsel                        ; NMI (CIA2 A) rivin 249 lopussa: RSEL 0 rivin 251 vertailun yli, joten ylä- ja alareuna
        pha                     ; pysyvät auki. d11s = viimeksi kirjoitettu $d011 (vertailurivin bitti 8 säilyy), d11b = RSEL
        lda d11s                ; IRQ-ketjun kirjoituksille kehyksen IRQ:hun asti (wr11). Lyhyt: loppukortin vaihto rivillä
        and #$f7                ; 250 ehtii vielä ikkunaansa (syklit 11-57)
        sta $d011
        sta d11s
        lda #$33
        sta d11b
        lda $dd0d               ; kuittaus
        pla
        rti
wr11                            ; A = vertailurivin bitti 8 ($00/$80): $d011 = A | d11b. Jos NMI tuli kirjoituksen välissä
        ora d11b                ; (d11b nyt RSEL 0), kirjoitetaan uudelleen RSEL 0:lla
        sta d11s
        sta $d011
        lda d11b
        cmp #$33
        bne +
        lda d11s
        and #$f7
        sta d11s
        sta $d011
+       rts
d11b    .byte $3b
NMI_C0  = (BORDER - 1) * 63 - NMI_LEAD ; ajastimen ensimmäinen jakso riviltä 1 riville BORDER
NMI_LEAD = 45                   ; syklejä: VICE NMI rivin 248 syklissä 43-45, $d011 noin 248:58 (ikkuna 248:0-250:62: marginaali noin 58 ja 130 sykliä; vaihto rivillä 248 ennen NMI:tä, 249 sen jälkeen)
nmi_on                          ; CIA2 A NMI:ksi rivin BORDER alkuun joka kehys. Ajastin käynnistetään aina rivin 1 alussa
        lda #<nmi_rsel          ; (keskeytykset pois vain rivillä 0-1), joten vaihe ei riipu siitä, missä kohtaa kehystä
        sta $fffa               ; loppu_go ajetaan (koko demossa eri kohdassa kuin osalevyllä: laskenta badlinejen alla
        lda #>nmi_rsel          ; siirtäisi NMI:n rivin 251 puolelle)
        sta $fffb
        lda #$7f
        sta $dd0d
        lda #0
        sta $dd0e
        lda $dd0d
        lda #<NMI_C0
        sta $dd04
        lda #>NMI_C0
        sta $dd05
_odota  lda $d012               ; riville 0 (IRQ:t päällä: kehyksen IRQ ja rivien tapahtumat kulkevat); bitti 8 vasta
        bne _odota              ; alatavun jälkeen, ettei rivin 255 -> 256 vaihto näytä riviltä 0
        bit $d011
        bmi _odota
        php
        sei
        ldx #1
        lda $d012               ; vielä rivillä 0 (IRQ ei vienyt riviä)?
        bne _uusi
        bit $d011
        bmi _uusi
-       cpx $d012               ; rivin 1 alkuun (alle 7 sykliä)
        bne -
        lda #%00010001          ; lataus ja käyntiin, jatkuva
        sta $dd0e
        lda #<(63 * 312 - 1)    ; sitten kehyksen välein
        sta $dd04
        lda #>(63 * 312 - 1)
        sta $dd05
        lda #$81
        sta $dd0d
        plp
        rts
_uusi   plp
        jmp _odota
d11s    .byte $3b               ; viimeksi kirjoitettu $d011 (nmi_rsel)
bmiss   .byte 0                 ; (mittari ei käytössä: NMI tarkistettu VICE:llä rivin 249 syklissä 50)

schedule                        ; seuraava IRQ: aikaisin rivin (9 bittiä) ja veden tapahtumista, muuten kehyksen IRQ
        ldx rnext_h             ; (TOPLINE). C = 0: tapahtuma rivillä tgth:tgt. $d011 ensin: välivaihe (uusi bitti 8,
        bne _rh                 ; vanha alatavu) ei osu nykyiselle riville
        lda rnext               ; rivin tapahtuma alle 256: pienin rivistä ja vedestä ($ff = ei)
        cmp wnext
        bcc _lo
        lda wnext
_lo     sta tgt
        lda #0
        sta tgth
        lda #0
        jsr wr11
        lda tgt
        sta $d012
_ev     lda #<irq_ev
        ldx #>irq_ev
        clc
        bcc +
_rh     lda wnext               ; rivin tapahtuma yli 255 tai ei: ensin vesi
        cmp #$ff
        bne _lo
        txa
        bmi _top
        lda #1
        sta tgth
        lda #$80
        jsr wr11
        lda rnext
        sta tgt
        sta $d012
        jmp _ev
_top    lda #<TOPLINE
top_at  pha                     ; kehyksen IRQ rivillä TOPLINE (yli 255), C = 1
        lda #$80
        jsr wr11
        pla
        sta $d012
        lda #<irq_top
        ldx #>irq_top
        sec
+       sta $fffe
        stx $ffff
        rts
tgt     .byte 0
tgth    .byte 0

waves                           ; veden merkkirivien vieritys: aalto kulkee, amplitudi kasvaa katsojaa kohti
        lda rel                 ; vaihe 2 kehyksessä kohtauksen alusta
        asl a
        .for i := 0, i < WROWS, i += 1
        clc
        adc #11
        and #63
        tax
        lda wsin + (i < 5 ? i : 5) * 64,x
        sta wtab + i
        txa
        .next
        rts

set_ptr                         ; A = rivi: spriteosoittimet paikkaan rivi mod NSLOT, kiilto riville. Osoittimet vasta
-       cmp #NSLOT              ; rivillä Y - 3: edellisen rivin viimeisen rivin osoittimet luetaan rivin Y - 4 lopusta
        bcc +                   ; rivin Y - 3 sykliin 10 (muuten sen viimeinen rivi näyttäisi tämän rivin dataa)
        sbc #NSLOT
        bcs -
+       asl a
        asl a
        asl a
        adc #(SPR & $3fff) / 64
        tax                     ; odotus riville Y - 3 (9 bittiä: alimman rivin Y voi olla yli 255)
        lda cur_y
        sec
        sbc #4
        tay
        lda cur_h
        sbc #0
        bmi _go                 ; (Y < 4: ylhäällä, ei odotusta)
        beq _wl
-       bit $d011               ; Y - 4 yli 255: ensin rasterin bitti 8
        bpl -
        tya
-       cmp $d012
        bcs -
        bcc _go
_wl     tya
-       bit $d011
        bmi _go
        cmp $d012
        bcs -
_go     txa
        clc
        .for i := 0, i < 8, i += 1
        sta SCR + $3f8 + i
        .if i < 7
        adc #1                  ; C = 0
        .endif
        .next
        .for i := 0, i < 8, i += 1
        lda colbuf + i
        sta $d027 + i
        .next
        rts                     ; C = 0

ptrs    .macro                  ; A = ensimmäinen osoitin, C = 0: 8 osoitinta ruutuun \1
        .for i := 0, i < 8, i += 1
        sta \1 + $3f8 + i
        .if i < 7
        adc #1
        .endif
        .next
        .endm

swcol   .byte 0                 ; vaihdossa värit ja MC (0 = yhtenäinen rivi, muuten rowf >> 1: bitti 0 MC)
act     .byte 0                 ; 0 = ruutu A (SCR), 1 = B (SCR2)
fix20   .byte 0                 ; rivin fixrow lohkojen rivi 20 lainassa (palautus kehyksen IRQ:ssa)
fixrow  .byte 0
blmask  .byte 0                 ; bl_scan: loppukortin rivit (bitti rivi - L20_ROW0), jotka alkavat badlinella
d18n    .byte D18A

calc_col                        ; rivin cur värit (Y = cur_h:cur_y) puskuriin: häivytys reunoilla ja kiilto spriteittäin
        lda cur_h               ; (reunat auki: rivejä on koko kehyksen, joten yksiväriset rivit ilman kiiltosilmukkaa)
        lsr a
        lda cur_y
        ror a
        lsr a
        lsr a
        tax
        lda fade,x
        sta lvl
        tax
        lda fade_l              ; valojen sammuessa tekstirivit (ei loppukortti) himmenevät taustan mukana
        beq _gl                 ; tasaisesti (ilman kiiltoa, joka hajottaisi rivin spriteittäin)
        lda cur
        cmp #KEEP_FROM
        bcs _gl
        ldy lvlcol,x
        lda fade_cur,y
        bcc _fill
_gl     cpx #3                  ; tasoilla 0-2 kiilto (3, 2) ei tummenna
        bcc _flat
        lda cur
        asl a
        asl a
        eor #$ff
        sec
        adc glint
        and #63
        tay                     ; Y = base: spriten i kiilto gl_tab[(base - 6 i) & 63]
        sec                     ; kiilto (gl_tab 54-58) ei osu yhteenkään spriteen (sarakkeet base - 6 i): yksi väri
        sbc #54
        and #63
        cmp #47
        bcs _flat
        cpx #4                  ; taulut gt3 ja gt4: väri = lvlcol[min(gl_tab, taso)] indeksillä base - 6 i + 42
        beq _t4                 ; (silmukka veisi noin 300 sykliä: reunat auki rivejä on koko kehyksen, ja tapahtumat
                                ; myöhästyisivät)
        .for i := 0, i < 8, i += 1
        lda gt3 + 42 - 6 * i,y
        sta colbuf + i
        .next
        rts
_t4     .for i := 0, i < 8, i += 1
        lda gt4 + 42 - 6 * i,y
        sta colbuf + i
        .next
        rts
_flat   lda lvlcol,x
_fill   .for i := 0, i < 8, i += 1
        sta colbuf + i
        .next
        rts

card_tick                       ; kehyksen IRQ:sta: loppukortin häivytys (card_tick3, LOPPU3) vasta kun vieritys on pysähtynyt
        lda pos+1
        cmp #>POS_MAX
        bcc _x
        bne +
        lda pos
        cmp #<POS_MAX
        bcc _x
+       jmp card_tick3
_x      rts

chain                           ; rivi cur on alkanut: seuraavan rivin Y ja tapahtuma sen yläpuolelle, muuten ei rivejä
        jsr chain_pre           ; (loppukortti chain_cardissa, joka kirjoittaa Y:n itse)
        bcs +
        lda cur_y
        .for i := 0, i < 8, i += 1
        sta $d001 + 2 * i
        .next
+       rts
chain_pre                       ; seuraava rivi: Y (cur_y, cur_h, 9 bittiä: rivi yli 255 on kehyksen viimeinen), värit ja
        inc cur                 ; tapahtuma; tekstirivin Y-rekisterit kirjoittaa kutsuja rivin alettua. C = 1: ei kirjoitettavaa
        lda cur
        cmp next                ; piirtämätön rivi (pääsäie myöhässä, väli YTOP..YB vie lähes kaikki 12 paikkaa): ei sitä
        bcs _no                 ; eikä alempia, joten paikan vanha rivi ei näy (rivi tulee alareunasta piirrettynä)
        cmp #KEEP_FROM
        bcc +
        jsr chain_card          ; (LOPPU3)
        sec
        rts
+       lda cur_h
        bne _no
        lda cur_y
        clc
        adc #ROW_H
        bcc +
        cmp #<YB                ; yli 255: näkyvissä, jos alle YB
        bcs _no
        inc cur_h
+       sta cur_y
        jsr calc_col
        lda cur_y
        sec
        sbc #TXT_LEAD
        sta rnext
        lda cur_h
        sbc #0
        sta rnext_h
        clc
        rts
_no     lda #$ff
        sta rnext
        lda #$80
        sta rnext_h
        sec
        rts

shim_rot                        ; A = vaihe 0-15: kierretyt värijaksot (rot) himmennettyinä
        tax
        .for t := 0, t < DYN_TABS, t += 1
        .for j := 0, j < 16, j += 1
        ldy dyn_tab + t * 32 + j,x
        .if t == SUN_T
        lda fade_sun,y          ; auringon heijastus himmenee auringon mukana
        .else
        lda fade_cur,y
        .endif
        sta rot + t * 16 + j
        .next
        .next
        rts
DYN_Q   = (len(DYN_A) + 3) / 4
; vaihtuvat solut neljäsosina (sammumisen aikana yksi neljäsosa kehyksessä)
shim_q0
        .for i := 0 * DYN_Q, i < len(DYN_A) && i < 1 * DYN_Q, i += 1
        lda rot + DYN_P[i]
        sta DYN_A[i]
        .next
        rts
shim_q1
        .for i := 1 * DYN_Q, i < len(DYN_A) && i < 2 * DYN_Q, i += 1
        lda rot + DYN_P[i]
        sta DYN_A[i]
        .next
        rts
shim_q2
        .for i := 2 * DYN_Q, i < len(DYN_A) && i < 3 * DYN_Q, i += 1
        lda rot + DYN_P[i]
        sta DYN_A[i]
        .next
        rts
shim_q3
        .for i := 3 * DYN_Q, i < len(DYN_A) && i < 4 * DYN_Q, i += 1
        lda rot + DYN_P[i]
        sta DYN_A[i]
        .next
        rts

; värit kirkkaustasoina 0-4 (0, 11, 12, 15, 1): rivin taso häivyttyy ylä- ja alareunassa (yötaivas, vesi) mustaan, joten
; kuva-alueen ulkopuolelle (reunaan) jäävä spriterivin osa on musta mustalla; kiilto kulkee kirjainten yli tummempana
; juovana; väri on tasoista pienempi
lvlcol  .byte 0, 11, 12, 15, 1
fade    .byte FADE_Y          ; Y / 8: taso (loppu.py: ylhäällä musta taivas, alhaalla letterboxin kohta kehyksellä 0)
gl_tab  .fill 54, 4
        .byte 3, 3, 2, 3, 3
        .fill 5, 4
lvl     .byte 0
gt3     .for j := 0, j < 106, j += 1  ; calc_col: lvlcol[min(gl_tab[(j - 42) & 63], 3)]
        .byte [0, 11, 12, 15, 1][(56 == ((j - 42) & 63)) ? 2 : 3]
        .next
gt4     .for j := 0, j < 106, j += 1  ; ... taso 4
        .byte [0, 11, 12, 15, 1][(54 <= ((j - 42) & 63) && ((j - 42) & 63) <= 58) ? [3, 3, 2, 3, 3][((j - 42) & 63) - 54] : 4]
        .next
rnext   .byte $ff               ; seuraavan spriterivin tapahtuman rasteririvi, alatavu
rnext_h .byte $80               ; ... ylätavu: 0, 1 (yli 255) tai $80 (ei tapahtumaa)
wnext   .byte $ff               ; seuraavan veden merkkirivin rasteririvi
wi      .byte 0
rel     .word 0                 ; kehys kohtauksen alusta (irq_top, DFRAME - TIM_SCENE_LOPPU_START)
WROW0   = HORIZON_ROW           ; ensimmäinen veden merkkirivi (tools/disk/loppu.py DIS_R0)
WROWS   = 25 - WROW0
wline   .for i := 0, i < WROWS, i += 1   ; vieritys rivin alkua edeltävällä rivillä
        .byte 51 + (WROW0 + i) * 8 - 1
        .next
        .fill 4, $ff            ; rivillä 254 X = $ff täsmää "ei tapahtumaa" -merkkiin: ylimääräiset käsittelyt reunuksessa
                                ; (vaaraton $d016) eivät saa lukea taulun ohi rivinumeroa seuraavaan kehykseen
wtab    .fill WROWS, WBASE
colbuf  .fill 8
first   .byte 0                 ; ylin näkyvä rivi
yfirst  .byte 0                 ; sen yläreuna (9 bittiä: alussa otsikko on alareunan alla)
yfirst_h .byte 0
next    .byte 0                 ; seuraava piirrettävä rivi
cur     .byte 0
cur_y   .byte 0
cur_h   .byte 0                 ; cur_y yli 255
ysw     .byte 0                 ; odottavan $d018-vaihdon rivi
ysw_h   .byte 0
now     .word 0                 ; DFRAME musiikin jälkeen (irq_top)
pos     .word 0
glint   .byte 0
tick    .byte 0
card_l  .byte 0                 ; loppukortin häivytyksen taso
card_s  .byte 0                 ; kortti pysähtynyt, häivytys ajastettu
cfade   .fill 16                ; loppukortin värit tasolla card_l
rot     .fill DYN_TABS * 16

        .include "loppu.inc"    ; kirjaimisto, rivit, vaihtuvat solut
loppu_end
SRC0    = (* + 255) & $ff00     ; ruudun ja värimuistin lähteet sivun rajalta (LOPPU1:n jatko)

        * = SRC0                ; ruudun ja värimuistin lähteet, taulut, välke (yksi tiedosto: kodin lopussa yksi avaus vähemmän)
scr_src .binary "tausta.scr"
col_src .binary "tausta.col"
; auringonlaskun taulut (loppu.inc:n listat): taivas auringon soluissa, kiekko ja sen maski, himmennystasot
sun_sky .byte SUN_SKY
wsin                            ; rivin i aalto: $10 | vieritys MC-pikseleinä (parillinen: MC-ruudukko säilyy),
        .for i := 0, i < (WROWS < 6 ? WROWS : 6), i += 1  ; amplitudi 0,6 + i / 5 (enintään 1,5) MC-px kohdan 1,5 ympärillä
        .for j := 0, j < 64, j += 1
        .byte WAVE ? $10 | 2 * round(1.5 + (i < 5 ? 0.6 + i / 5.0 : 1.5) * sin(rad(j * 360.0 / 64))) : WBASE
        .next
        .next
bitv    .for r := L20_ROW0, r < ROWS, r += 1     ; loppukortin rivin bitti blmaskissa (tekstirivi 0)
        .byte r < L20_ROW0 + L20_N ? 1 << (r - L20_ROW0) : 0
        .next
rowh    .byte ROWH              ; rivien välit, liput (0 yhtenäinen, 1 MC, 7 logo), logon väri ja MC-väri (loppu.py)
rowf    .byte ROWF
rowc    .byte ROWC
rowm    .byte ROWM
rowl    .byte ROWL              ; tapahtuman etumatka (teksti 6, kortti 14, yhtenäinen 20: heti edellisen alettua)
; valojen pyyhkäisyn rivien osoitteet: lähteet, ruutu, värimuisti
ps_lo   .for r := 0, r < 25, r += 1
        .byte <(scr_src + r * 40)
        .next
ps_hi   .for r := 0, r < 25, r += 1
        .byte >(scr_src + r * 40)
        .next
pc_lo   .for r := 0, r < 25, r += 1
        .byte <(col_src + r * 40)
        .next
pc_hi   .for r := 0, r < 25, r += 1
        .byte >(col_src + r * 40)
        .next
pd_lo   .for r := 0, r < 25, r += 1
        .byte <(SCR + r * 40)
        .next
pd_hi   .for r := 0, r < 25, r += 1
        .byte >(SCR + r * 40)
        .next
pk_lo   .for r := 0, r < 25, r += 1
        .byte <($d800 + r * 40)
        .next
pk_hi   .for r := 0, r < 25, r += 1
        .byte >($d800 + r * 40)
        .next
sun_bits .byte SUN_BITS
sun_mask .byte SUN_MASK
fade_tab .byte FADE_TAB
sun_dlo .for i := 0, i < SUN_YN, i += 1
        .byte <(BMP + ((SUN_Y0 + i) / 8) * 320 + SUN_CX0 * 8 + (SUN_Y0 + i) % 8)
        .next
sun_dhi .for i := 0, i < SUN_YN, i += 1
        .byte >(BMP + ((SUN_Y0 + i) / 8) * 320 + SUN_CX0 * 8 + (SUN_Y0 + i) % 8)
        .next
sun_mul .for i := 0, i < SUN_YN, i += 1
        .byte i * SUN_NC
        .next
open_src .binary "open.bin"     ; letterboxin takaiset kuvarivit avautumisjärjestyksessä (loppu.py)
open_lo .byte OPEN_LO
open_hi .byte OPEN_HI
open_cnt .byte OPEN_CNT
sun_lvl .for d := 0, d <= SUN_R, d += 1
        .byte d * (NFADE + 1) / (SUN_R + 1)
        .next
hw_rec  .binary "kasiala.bin"   ; käsialan tietueet (loppu.py kasiala): osoite ja uusi tavu
        .include "valke.inc"    ; järven välkkeen vaiheet (loppu.py, maisema.json): kodin aikana, joten
                                ; välke jatkuu saumassa kodin välkkeestä kehyksestä 1 (LOPPU3:ssa noin 2 s ilman)
src_end
        .cerror * > $c000, "loppu: LOPPU1 yli $bfff:n (koti käyttää $c000-): ", format("$%04x", *)

        * = BMP                 ; LOPPU2: bittikartta pankissa 1 (latautuu edellisen kohtauksen jälkeen)
        .binary "tausta.bmp"
fix_back                        ; IRQ:sta: rivin fixrow oma rivi 20 takaisin
        dec fix20
        lda fixrow
        clc
        adc #(L20_N - L20_ROW0) & 255   ; palautusrutiinit taulun loppupuolella
        bne +
put20                           ; X = logorivi: sen lohkojen rivi 20 = edellisen rivin rivi 20 (l20.inc)
        txa
        sec
        sbc #L20_ROW0
+       tax
        lda l20v_lo,x
        sta _j+1
        lda l20v_hi,x
        sta _j+2
_j      jmp $ffff

bl_scan                         ; kehyksen IRQ:sta ennen cli:tä: loppukortin yhtenäiset rivit, jotka alkavat tässä kehyksessä
        lda #0                  ; badlinella (Y & 7 = YSCROLL, rivit $30-$f7): niiden lohkojen rivi 20 lainaan (put20)
        sta blmask
        ldx first
        lda yfirst
        cpx #L20_ROW0
        bcs _r
        cpx #L20_ROW0 - NSLOT   ; näkyvissä enintään NSLOT riviä (reunat auki)
        bcc _x
-       clc                     ; tekstirivit ohi: kortin ensimmäisen rivin Y
        adc rowh,x
        bcs _x
        inx
        cpx #L20_ROW0
        bne -
_r      cpx #L20_ROW0 + L20_N
        bcs _x
        sta bly
        cpx #L20_ROW0
        bcc _n
        lda rowf,x
        lsr a
        bcc _n
        lda bly
        cmp #$f8
        bcs _n
        and #7
        cmp #$3b & 7
        bne _n
        stx blx
        jsr put20
        ldx blx
        lda blmask
        ora bitv - L20_ROW0,x
        sta blmask
_n      lda bly
        clc
        adc rowh,x
        bcs _x
        inx
        bne _r
_x      rts
bly     .byte 0
blx     .byte 0
; (LOPPU2:n loppu: LOPPU1 on täynnä)
first_ev                        ; kehyksen ensimmäisen rivin tapahtuma: Y, ruutu A ja hires (kehyksen IRQ on alimpien rivien
        lda #$ff                ; aikana, joten se ei koske näihin), spritet päälle (alussa kehyksen IRQ sammuttaa ne, kun
        sta $d015               ; rivejä ei ole)
        lda #0
        sta fresh
        sta $d01c               ; tekstirivit hires (loppukortin rivit asettavat itse)
        lda #D18A               ; kehyksen alussa ruutu A (loppukortin rivit vaihtavat B:hen ja takaisin)
        sta $d018
        lda cur_y
        .for i := 0, i < 8, i += 1
        sta $d001 + 2 * i
        .next
        rts
fresh   .byte 0

rast                            ; rasteri: rr = alatavu, N = bitti 8 ($d011 luettu samalla rivillä)
-       lda $d012
        ldx $d011
        cmp $d012
        bne -
        sta rr
        txa
        rts
rr      .byte 0
wy      .byte 0                 ; _nc: alkaneen rivin Y odotukseen

bmp_end
        .cerror * > $7fff, "loppu: LOPPU2:n koodi idle-tavun $7fff päällä (reunat auki): ", format("$%04x", *)

        * = LOGO_AT             ; LOPPU3 (ladataan kohtauksen alussa): loppukortin logot spriteriveinä (render kopioi
        .binary "logot.bin"     ; paikkaan) ja niiden rivien 20 lainausrutiinit (put20)
        .include "l20.inc"
        .include "rivit.inc"    ; tekstirivit ROWS_EARLY- (loppu.py): piirretään vasta LOPPU3:n latauksen jälkeen
; loppukortin rivien rutiinit (LOPPU1 on täynnä): kortin rivit ovat LOPPU3:ssa, joten irq_ev ja irq_top kutsuvat
; näitä vasta sen latauduttua (cur >= KEEP_FROM)
set_card                        ; A = loppukortin rivi (irq_ev:_rs chainin valitsemana): osoittimet piilossa olevaan ruutuun,
        tax                     ; vaihto $d018:lla irq_ev:_swt:ssä (näkyvän ruudun osoittimet näkyisivät edellisen rivin
        lda slot_p,x            ; loppuriveillä). Paikan ensimmäinen osoitin taulusta (reunat auki: vaihto ehtii)
        clc
        ldy act
        bne _pa
        #ptrs SCR2
        lda #D18B
        ldy #1
        bne _sw
_pa     #ptrs SCR
        lda #D18A
        ldy #0
_sw     sta d18n
        sty act
        pla                     ; irq_ev valmistelee vaihdon (ei paluuta _rs:n perään)
        pla
        jmp irq_ev._prep
slot_p  .for r := 0, r < ROWS, r += 1
        .byte (SPR & $3fff) / 64 + (r % NSLOT) * 8
        .next
card_col                        ; X = loppukortin rivi: yksi väri (rowc) kortin häivytystasolla, ei kiiltoa
        ldy rowc,x
        lda cfade,y
        .for i := 0, i < 8, i += 1
        sta colbuf + i
        .next
        rts

card_first                      ; kehyksen IRQ:sta: ensimmäinen näkyvä rivi on loppukortin rivi X: set_card, värit ja MC
        lda #<set_card
        sta irq_ev._rs + 1
        lda #>set_card
        sta irq_ev._rs + 2
        jsr card_col
        .for i := 0, i < 8, i += 1
        sta $d027 + i
        .next
        ldy rowm,x
        lda cfade,y
        sta $d025
        lda rowf,x
        and #2
        beq +
        lda #$ff
+       sta $d01c
        rts

chain_card                      ; loppukortti: välit, etumatka ja värit tauluista
        tax
        dex                     ; alkanut rivi: badline-vaihdon jälkeen oma rivi 20 takaisin (haetaan 20 riviä myöhemmin);
        cpx #L20_ROW0           ; (reunat auki: palautus aina heti)
        bcc +
        lda bitv - L20_ROW0,x
        and blmask
        beq +
        stx fixrow              ; (reunat auki: rivi 20 näkyy aina, joten palautus heti)
        inc fix20
        jsr fix_back
+       lda #<set_card
        sta irq_ev._rs + 1
        lda #>set_card
        sta irq_ev._rs + 2
        ldx cur
        cpx #ROWS
        bcs _no
        lda cur_h
        bne _no
        lda cur_y
        clc
        adc rowh - 1,x          ; edellisen rivin väli
        bcc +
        cmp #<YB
        bcs _no
        inc cur_h
+       sta cur_y
        .for i := 0, i < 8, i += 1
        sta $d001 + 2 * i
        .next
        lda rowf,x              ; yhtenäinen rivi: värit kuten edellisellä (set_card ei kirjoita niitä)
        lsr a
        bcs +
        jsr card_col
+       ldx cur
        lda cur_y
        sec
        sbc rowl,x
        sta rnext
        lda cur_h
        sbc #0
        sta rnext_h
        rts
_no     jmp chain_pre._no

card_tick3                      ; kehyksen IRQ:sta: loppukortti häipyy mustaan pysähdyttyään keskelle
        lda card_l              ; samoja tummuusketjuja pitkin kuin valot: NFADE tasoa CARD_DT kehyksen välein niin, että
        cmp #NFADE              ; musta on kohtauksen lopussa. Koko demossa vieritys alkaa myöhemmin (LOPPU2:n lataus), joten
        bcs _x                  ; jos pysähdys on myöhässä, häivytys alkaa heti pysähdyksestä tasolla kehyksessä
                                ; (now = DFRAME musiikin jälkeen, irq_top).
        lda card_s
        bne _run
        lda pos+1
        cmp #>POS_MAX
        bcc _x
        bne +
        lda pos
        cmp #<POS_MAX
        bcc _x
+       inc card_s              ; pysähtyi: alku max(nyt + 1, CARD0), tahti CARD_DT tai 1
        lda #CARD_DT
        sta card_dt
        lda now
        cmp #<CARD0
        lda now+1
        sbc #>CARD0
        bcs +
        lda #<CARD0
        sta next_card
        lda #>CARD0
        sta next_card+1
        rts
+       lda #1
        sta card_dt
        lda now
        clc
        adc #1
        sta next_card
        lda now+1
        adc #0
        sta next_card+1
        rts
_run    lda now
        cmp next_card
        lda now+1
        sbc next_card+1
        bcc _x
        clc
        lda next_card
        adc card_dt
        sta next_card
        bcc +
        inc next_card+1
+       inc card_l
        lda card_l
        asl a
        asl a
        asl a
        asl a
        tax
        ldy #0
-       lda fade_tab,x
        sta cfade,y
        inx
        iny
        cpy #16
        bne -
_x      rts

fade_level                      ; (LOPPU3: valot sammuvat vasta FADE0:sta) taso fade_l: väritaulu (välkkeet ja rivit heti) ja ruudun pyyhkäisy alkuun
        lda fade_l
        asl a
        asl a
        asl a
        asl a
        tax
        ldy #0
-       lda fade_tab,x
        sta fade_cur,y
        inx
        iny
        cpy #16
        bne -
        lda #1
        sta sun_dirty
        lda fade_l
        cmp bg_l
        beq +
        bcc +
        jmp bg_level
+       rts

render_due3                     ; loppu_run (LOPPU3): kuten render_due, mutta kun seuraavan rivin paikka on vielä käytössä,
        lda next                ; rivi piirretään valmiiksi välipuskuriin STAGE ja kopioidaan paikkaan sen vapauduttua.
        cmp #ROWS               ; Reunat auki: väli YTOP..YB vie lähes 12 paikkaa x 24 riviä, joten piirrolle jäisi vain
        bcs _no                 ; noin 16 kehystä, ja pääsäie saa rivien IRQ:ilta vähän aikaa (rivi 12-28 kehystä)
        sec
        sbc first
        cmp #NSLOT
        bcs _stage
        lda staged
        cmp next
        bne _direct
        jsr stage_copy
        jmp _inc
_direct lda next
        jsr render
_inc    inc next
_no     rts
_stage  lda staged
        cmp next
        beq _no
        ldx next
        lda row_lo,x
        sta rp
        lda row_hi,x
        sta rp+1
        lda #>STAGE
        sta sb+1
        ldx #NSLOT
        jsr render_at
        lda next
        sta staged
        rts
stage_copy                      ; välipuskuri rivin next paikkaan (vapaa)
        lda next
-       cmp #NSLOT
        bcc +
        sbc #NSLOT
        bcs -
+       tax
        asl a
        adc #>SPR
        sta _d1 + 2
        adc #1
        sta _d2 + 2
        ldy #0
-       lda STAGE,y
_d1     sta $ff00,y
        lda STAGE + 256,y
_d2     sta $ff00,y
        iny
        bne -
        lda slot_blank + NSLOT
        sta slot_blank,x
        rts
staged  .byte $ff               ; välipuskurissa valmiina oleva rivi

nmi_off lda #$7f                ; kohtauksen lopussa (LOPPU3)
        sta $dd0d
        lda #0
        sta $dd0e
        lda $dd0d
        rts

; loppu_run ja valojen sammumisen rutiinit (LOPPU1 on täynnä): käytössä vasta LOPPU3:n latauksen jälkeen (linkki:
; S_LOAD f_loppu3 ennen S_CALL loppu_run; sun_table ja sun_set vain auringon liikkuessa tai valojen sammuessa)
loppu_run                       ; pääsäie: rivit ennen kuin ne tulevat ruutuun, loppu (aurinko, valot); palaa lopussa
-       jsr R_IDLE
        jsr render_due3
        jsr ending
        jsr dissolve
        ldy DFRAME+1
        lda DFRAME
        cpy DFRAME+1
        bne -
        cmp #<TIM_SCENE_LOPPU_END
        tya
        sbc #>TIM_SCENE_LOPPU_END
        bcc -
        jmp nmi_off

si      .byte 0                 ; sun_set (LOPPU3)
s_lo    .byte 0                 ; sun_set: ylin päivitettävä rivi
sc      .byte 0
sv      .byte 0
ssky    .byte 0
card_dt .byte 0                 ; card_tick3 (LOPPU3)
next_card .word 0

dissolve                        ; pääsäikeestä: kuva liukenee mustaan Bayer-askelin (tasainen pinta ei hyppää kerralla
        ldx #1                  ; mustaksi): järvi (merkkirivit DIS_R0-24) valotasoilla 1-4, taivas (0..DIS_R0-1)
_ph     lda fade_l              ; tasoilla 2-5; merkkirivi kehyksessä (askel etenee pyyhkäisynä ylhäältä alas)
        sec
        sbc dis_lev,x           ; tavoiteaskel = clamp(fade_l - (0 tai 1), 0, 4)
        bcs +
        lda #0
+       cmp #5
        bcc +
        lda #4
+       cmp dcur,x
        beq _nx
        bcs _go
_nx     dex
        bpl _ph
        rts
_go     lda DFRAME
        cmp dlast
        beq _x
        sta dlast
        stx dph
        ldy drow,x
        lda dis_lo,y
        sta dz
        lda dis_hi,y
        sta dz+1
        lda dcur,x
        asl a
        tay
        lda dis_m,y
        sta dm
        lda dis_m+1,y
        sta dm+1
        ldy #0
-       jsr _two                ; tavut 0-255
        bne -
        inc dz+1
-       jsr _two                ; 256-319
        cpy #64
        bne -
        ldx dph
        inc drow,x
        lda drow,x
        cmp dis_end,x
        bcc _x
        lda dis_beg,x
        sta drow,x
        inc dcur,x
_x      rts
_two    lda (dz),y              ; kaksi tavua: parillinen ja pariton kuvarivi omilla maskeillaan
        and dm
        sta (dz),y
        iny
        lda (dz),y
        and dm+1
        sta (dz),y
        iny
        rts
dcur    .byte 0, 0              ; vaihe 0 järvi, 1 taivas
drow    .byte DIS_R0, 0
dis_beg .byte DIS_R0, 0
dis_end .byte 25, DIS_R0
dis_lev .byte 0, 1              ; taivas tasoilla 2-5: valtaosa poissa ennen kuin sininen 6 vaihtuu mustaksi (taso 5)
dph     .byte 0
dlast   .byte 0
dis_lo  .for r := 0, r < 25, r += 1
        .byte <(BMP + r * 320)
        .next
dis_hi  .for r := 0, r < 25, r += 1
        .byte >(BMP + r * 320)
        .next
dis_m   .byte DIS_M

sun_table                       ; kehyksen IRQ:sta: heijastuksen välkkeiden taulu fade_sun tasolla max(fade_l, auringon taso)
        ldx sun_d
        lda sun_lvl,x
        cmp fade_l
        bcs +
        lda fade_l
+       asl a
        asl a
        asl a
        asl a
        tax
        ldy #0
-       lda fade_tab,x
        sta fade_sun,y
        inx
        iny
        cpy #16
        bne -
        rts

sun_set                         ; kiekko sun_d riviä alempana, horisontin alle jäävä osa piiloon (taivas + kiekko); sd =
        lda sd                  ; edellinen d: sitä ylempänä rivit ovat jo taivasta. Rivit alhaalta ylös, jotta
        clc                     ; kesken jäänyt päivitys ei näytä kiekkoa matalampana kuin se on (yläreuna viimeisenä)
        adc #SUN_TOP - SUN_Y0
        sta s_lo
        lda sun_d
        sta sd
        lda #SUN_YN - 1
        sta si
_row    ldx si                  ; rivi SUN_Y0 + si: kohde bittikartassa ja kiekon rivi s = SUN_Y0 + si - SUN_TOP - d
        lda sun_dlo,x
        sta pa
        lda sun_dhi,x
        sta pa+1
        lda sun_mul,x           ; taivaan rivin alku = si * SUN_NC
        sta ssky
        txa
        clc
        adc #(SUN_Y0 - SUN_TOP) & 255
        sec
        sbc sd
        sta ss                  ; s (negatiivinen tai >= SUN_R: ei kiekkoa)
        ldx #0
        ldy #0
_c      stx sc
        txa
        clc
        adc ssky
        tax
        lda sun_sky,x
        sta sv
        lda ss
        cmp #SUN_R
        bcs _put                ; s < 0 (yli 127) tai >= SUN_R
        tax
        lda sun_mul,x
        clc
        adc sc
        tax
        lda sv
        and sun_mask,x
        ora sun_bits,x
        sta sv
_put    lda sv
        sta (pa),y
        tya
        clc
        adc #8
        tay
        ldx sc
        inx
        cpx #SUN_NC
        bne _c
        lda si
        cmp s_lo
        beq +
        dec si
        jmp _row
+       rts

        .cerror ROWS_EARLY < NSLOT, "loppu: loppu_go piirtää NSLOT riviä ennen LOPPU3:a"
l3_end
        .cerror * > $fffa, "loppu: LOPPU3 yli vektorien: ", format("$%04x", *)
STAGE   = (l3_end + 255) & $ff00 ; välipuskuri (render_due3), ei tiedostossa
        .cerror STAGE + 512 > $fffa, "loppu: välipuskuri yli vektorien"

