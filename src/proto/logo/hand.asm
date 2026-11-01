; Alun purku ja luovutus Hillnerille. Viimeinen täysi kuva (kehys EX0 - 1) jää
; bittikartta B:hen ($a000-$bf3f, ruutu $bc00), ja tämä IRQ pyyhkii sen: rivit ylhäältä rivin TB yläpuolelle ja
; rivistä RB alaspäin näytetään tyhjänä tilana ($d011 = $7b, ECM + BMM = musta), TB kulkee emblemin yläreunasta
; viivaan ja RB heijastuksen alareunasta viivan alle (Model.wipe, taulut wtb, wrb). Pyyhkäisyn jälkeen jää viiva,
; joka välähtää iskuilla. Koodi ja muuttujat ovat taulut 2:n alueella ($f600-): kun logo_go on palannut, alku
; käyttää vain $a000-$bfff, taulut 2:n ja nollasivun DFRAME:n, joten Hillnerin CRANE1 ($1a00-$9fff) latautuu.
; IRQ:t: TB (näkyviin), RB (tyhjäksi), 250 (frame_hook, seuraavan kehyksen rajat). hil_prep ottaa IRQ:n (sei).

HLINE   = 51 + Y0 + HZ          ; viivan rasteririvi

; ---------------------------------------------------------------- rivitapahtumat
; Pyyhkäisyn rajat ja niiden välissä näkyvät aaltoilun kaistat kehyksen listana fl/fd/fr (rivi, $d011, kaista;
; $ff = ei, fl $ff = loppu): IRQ tulee riviä ennen; $d011 odottaa rivin alkuun, aaltoilu kirjoitetaan heti (kaistan
; alkua edeltävä pariton rivi on heijastuksessa musta). Lähekkäiset tapahtumat samalla kertaa. Nimiruudussa kaista
; $80 | k on spritekaista k (title.asm TSPR: paikat ja osoittimet heti).

ev_start                        ; A/X = lopun käsittelijä (rivi 250): ensimmäinen tapahtuma IRQ:ksi
        sta evend
        stx evend+1
        lda #0
        sta ek
        lda #<ev_irq
        sta $fffe
        lda #>ev_irq
        sta $ffff
        lda fl
        sec
        sbc #1
        sta $d012
        rts

ev_irq  pha                     ; tapahtuma rivillä L: IRQ riviä ennen, odotus rivin vaihtumiseen, kirjoitus heti
        txa                     ; (rivin alku vasemmassa reunassa, ennen näyttöikkunaa)
        pha
        tya
        pha
        asl $d019               ; kuittaus heti: seuraava IRQ voi tulla jo rivin päästä (ei saa kuitata pois)
        ldx ek
_l      ldy fl,x
        lda fd,x
        bmi _r                  ; pelkkä aaltoilu: heti riviä ennen (heijastuksen pariton rivi on musta)
-       cpy $d012               ; odota riviä (myöhässä: heti)
        beq +
        bcs -
+       sta $d011
_r      ldy fr,x
        bmi _s
        lda ripv,y
        sta $d016
        jmp _nx
_s      .if INTEGRATED          ; $80 | k: nimiruudun spritekaista k (title.asm TSPR), $ff: ei
        cpy #$ff
        beq _nx
        jsr TSPR
        .endif
_nx     inx
        lda fl,x
        cmp #$ff
        beq _end
        sec
        sbc #1                  ; seuraavan IRQ-rivi (rivi - 1)
        cmp $d012
        bcc _l                  ; jo ohitettu tai menossa: samalla kertaa (aaltoilu 2 rivin välein ei saa
        beq _l                  ; ketjuuntua etuajassa näkyvälle riville)
        sta $d012
        stx ek
        jmp _x
_end    lda evend
        sta $fffe
        lda evend+1
        sta $ffff
        lda #IRQ_BOT
        sta $d012
_x      pla
        tay
        pla
        tax
        pla
        rti

; ---------------------------------------------------------------- purku
handover                        ; irq_bot:sta (A, X, Y pinossa), kun viimeinen kuva näkyy
        .if !INTEGRATED         ; omassa ohjelmassa pankissa 3 ei ole spritejä ($c400 musiikin puskuri)
        lda #0
        sta $d015
        .endif
        lda #$18
        sta $d016
        lda #$7b                ; seuraava kehys alkaa tyhjänä
        sta $d011
        lda #2
        sta hand
        jmp hw_next

hw_250  pha                     ; rivi 250: musiikki ja kello, seuraavan kehyksen rajat
        txa
        pha
        tya
        pha
        lda #$18                ; aaltoilun jälkeen suoraan
        sta $d016
        .if INTEGRATED
        jsr FRAME_HOOK
        .else
        .if HAVE_MUSIC
        jsr MUSIC_PLAY
        .endif
        inc DFRAME
        bne +
        inc DFRAME+1
+
        .endif
        lda hbank               ; kuva kopioitu pankkiin 3 (bank3): näkyviin
        cmp #1
        bne hw_next
        lda #0                  ; pankki 3 ($dd00 vain 0-3: Krill), ruutu $c000, bittikartta $e000
        sta $dd00
        lda #$08
        sta $d018
        lda #2
        sta hbank
hw_next sec                     ; k = DFRAME - SCENE_START - EX0, rajattuna 0..WIPE
        lda DFRAME
        sbc #<(SCENE_START + EX0)
        tax
        lda DFRAME+1
        sbc #>(SCENE_START + EX0)
        bcc _z
        bne _e
        cpx #WIPE
        bcc _k
_e      ldx #WIPE
        .byte $2c
_z      ldx #0
_k      lda wtb,x               ; nimiruudussa title korvaa htb:n ja hrb:n: wtb ja wrb saavat olla roskaa
        sta htb                 ; (seuraavan kohtauksen esilataus $e000-$faff, part-alku.json)
        lda wrb,x
        sta hrb
        .if INTEGRATED
        lda tready              ; nimiruutu ladattu (title_go): kehyksestä TITLE0 se avautuu viivasta
        beq _nt
        sec
        lda DFRAME
        sbc #<(SCENE_START + TITLE0)
        tay
        lda DFRAME+1
        sbc #>(SCENE_START + TITLE0)
        bcc _nt
        bne _tf
        cpy #TOPEN
        bcc _tk
_tf     ldy #TOPEN
_tk     sty tk
        jsr title
        ldx #$18                ; kuva paikallaan (ei driftiä: hidas vieritys
        lda #$7b                ; 1 px:n askelin näyttäisi hyppimiseltä)
        stx $d016
        sta rbv
        sta $d011               ; RB: tyhjä tila
        eor #$40                ; TB: näkyvä tila
        sta tbv
        jmp _rb
_nt
        .endif
        ; ei viivaa eikä sen välähdyksiä
_n
        .if INTEGRATED
        jsr nmout               ; nimi putoaa pois (logo.asm, alku1: vapautuu vasta nimiruudun alettua)
        .endif
        sec                     ; aaltoilun arvot kuten deco
        lda DFRAME
        sbc #<SCENE_START
        jsr ripcalc
        lda htb                 ; kehyksen lista: TB, kaistat ennen RB:tä, RB (TB < viiva < kaistat)
        sta fl
        lda #$3b
        sta fd
        lda #$ff
        sta fr
        ldx #1
        ldy #0
_b      lda hrl,y
        cmp hrb
        bcs _rb2
        sta fl,x
        lda #$ff
        sta fd,x
        tya
        sta fr,x
        inx
        iny
        cpy #RIPN
        bne _b
        .if INTEGRATED
        jmp _rb2
_rb     lda htb                 ; nimiruutu: TB, spritekaistat (title.asm: TSEVN riviä TSEVL, 0 kunnes spritet
        sta fl                  ; ovat päällä) ja RB (ei aaltoilua)
        lda tbv
        sta fd
        lda #$ff
        sta fr
        ldx #1
        ldy #0
-       cpy TSEVN
        bcs _rb2
        lda TSEVL,y
        sta fl,x
        lda #$ff
        sta fd,x
        tya
        ora #$80
        sta fr,x
        inx
        iny
        bne -
        .endif
_rb2    lda hrb
        sta fl,x
        lda rbv
        sta fd,x
        lda #$ff
        sta fr,x
        sta fl+1,x
        asl $d019               ; rivin 250 IRQ kuitattu (muuten IRQ toistuu heti, ja rivin 256 jälkeen $d012:n
        lda #<hw_250            ; odotus kestäisi seuraavan kehyksen TB:hen asti)
        ldx #>hw_250
        jsr ev_start
        .if INTEGRATED
        lda twork               ; nimiruutu: solujen kopiointi voi kestää yli rivin 312; TB-IRQ saa keskeyttää
        beq +
        lda tbusy               ; ei sisäkkäin (seuraavan kehyksen hw_250 voi tulla kesken)
        bne +
        inc tbusy
        lda #0
        sta twork
        cli
        jsr TCODE
        sei
        dec tbusy
+
        .endif
        pla
        tay
        pla
        tax
        pla
        rti

        .if INTEGRATED
; ---------------------------------------------------------------- nimiruutu (title.py)
title_go                        ; kohtaustaulu: title.prg ladattu ($8000 ruutu, $8400 värit, $a000 bittikartta)
        lda #1
        sta tready
        rts

titleb_go                       ; kohtaustaulu: titleb.prg (logon solut LCNT, LREC) ladattu
        lda #1
        sta TLRDY
        rts

title2_go                       ; kohtaustaulu: title2.prg (lappuset, TPOP) ladattu
        lda #1
        sta T2RDY
        rts

title                           ; Y = avautumisen vaihe 0..TOPEN: rivit [otb, orb), pankki 2 ensimmäisellä kerralla;
        lda tstate              ; värimuisti, maalautuminen ja kiilto title.prg:n koodissa (title.asm, TCODE)
        bne +
        lda #1                  ; pankki 2: ruutu $8000, bittikartta $a000
        sta $dd00
        lda #$08
        sta $d018
        lda #1
        sta tstate
+       lda otb,y
        sta htb
        lda orb,y
        sta hrb
        lda #1                  ; maalaus ja ponnahdukset (TCODE) hw_250:n lopussa keskeytykset sallittuina
        sta twork
        rts

tready  .byte 0
tstate  .byte 0
twork   .byte 0
tbusy   .byte 0
tk      .byte 0
tbv     .byte $3b               ; nimiruudun TB-arvo ($d011)
        .endif

rbv     .byte $7b               ; RB:n $d011
htb     .byte 0
hrb     .byte 0
hbank   .byte 0                 ; 1 = kuva kopioitu pankkiin 3, 2 = näkyvissä
evend   .word 0
ek      .byte 0
ripcalc sta tmpr                ; A = kohtauksen kehys: aaltoilun $d016-arvot kaistoittain, vaihe tt & 63 (1,28 s
        ldy #RIPN - 1           ; kierros kuten alkuperäisessä animaatiossa), kaistan k luokka RIPA[k] ja vaihesiirto RIPP[k]
-       lda tmpr                ; (rtab: 64 vaihetta per luokka, indeksi luokka * 64 + vaihe)
        clc
        adc ripp,y
        and #63
        ora ripa64,y
        tax
        lda rtab,x
        sta ripv,y
        dey
        bpl -
        rts
tmpr    .byte 0
ripp    .for k := 0, k < RIPN, k += 1
        .byte RIPP[k]
        .endfor
ripa64  .for k := 0, k < RIPN, k += 1
        .byte RIPA[k] * 64
        .endfor
ripv    .fill RIPN, $18         ; aaltoilun $d016-arvot (pidossa deco, purussa hw_250); MC alusta (rip_irq ennen decoa)
hrl     .for k := 0, k < RIPN, k += 1   ; kaistojen rivit
        .byte RIP0 + k * RIPD
        .endfor
fl      .fill RIPN + 3          ; kehyksen rivitapahtumat: rivi ($ff = loppu),
fd      .fill RIPN + 2          ; $d011 ($ff = ei)
fr      .fill RIPN + 2          ; ja aaltoilun kaista ($ff = ei)
