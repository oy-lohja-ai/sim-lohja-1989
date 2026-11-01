; Kyltti: greetsit LOHJAN RAUTA -kylttiin perspektiivissä oikeissa mittasuhteissa (moduuli).
; Data: build.py -> kyltti.inc, kyltti_data.inc, strips.bin, clear.inc.
;
; Teksti piirretään kahdeksaan hires-spriteen (1 data-px = 1 hires-px, joten kirjaimen leveys ja korkeus
; ovat samaa mittakaavaa) kyltin mustan kaistan päälle. Kirjaimet ovat kokoluokittain piirrettyjä glyfejä
; (font.py); jokaisen kirjaimen paikka (k_xt alusta) sekä kokoluokka ja ylärivi (k_ctt keskikohdasta)
; luetaan tekstiavaruuden paikasta u perspektiivitauluista, joten kirjain kutistuu kaukopäätä kohti
; samassa suhteessa pysty- ja vaakasuunnassa. 6510 asettelee ja piirtää kaikki näkyvät kirjaimet joka
; päivityksellä.
;
; Kangas: puskurit A ja B lomitettuina, sprite k = K_CANVAS + 128k (+64 puskurissa B), rivi r = +3r.
; Kirjain piirretään 8 px leveinä nauhoina: nauhan tavu on sanakirjaindeksi, ja siirtotaulu k_shtab
; antaa sen oikealle siirretyt osat kahteen vierekkäiseen kankaan tavuun (R ja L). Nauhat on lomitettu
; kolmen välein, joten sama Y = 3r indeksoi sekä nauhan että kankaan rivin ((zp),y molemmissa).
;
; Spritejen Y on porras (k_ys): jokainen sprite alkaa omien kirjaintensa kohdalta, joten kaistan kaltevuus
; ei kuluta spriten 21 riviä. Kallistus (purku) lisää portaaseen kulmakertoimen k_tilt (rivejä per px,
; 8.8): sarakkeen siirto k_trow, spriten oma siirto sen keskisarakkeesta, ja kirjain piirretään oman
; alkusarakkeensa siirrolla. Kirjaimet pysyvät pystyssä (leikkaus eikä kierto, kuten romahdusmoottorissa).
;
; Rajapinta:
;   kyltti_init    alusta (spritet, osoittimet, käsikirjoitus)
;   kyltti_tick    kerran kehyksessä IRQ:sta kyltin rivien jälkeen: käsikirjoitus, puskurin vaihto, Y
;   kyltti_render  pääsilmukasta: piirtää takapuskurin, jos tarvitaan (palaa heti, jos ei)
;   k_tilt, k_yoff kallistus ja pystysiirto (purkutila asettaa ne itse; integraatiossa romahdusmoottori)

        .cpu "6502i"            ; lax (zp),y: vakaa laiton opkoodi
        .weak
K_CANVAS = $4000                ; kangas K_NSPR x 128 tavua, VIC-pankin sisällä, 64:llä jaollinen
K_SCRATCH = K_CANVAS + $400     ; kaatoalue ja muuttujat $300 tavua (ei näytetä, mikä tahansa RAM)
K_PTRS   = $5ff8                ; sprite-osoittimet (ruutu + $3f8)
K_ZP     = $40
K_SPR_X0 = 24 + K_XA            ; ensimmäisen spriten X
K_RATE   = 3                    ; piirtoväli kehyksinä vierityksessä, purussa ja välkkeessä (2 = 25 Hz)
K_DTILT  = $0003                ; purku: kallistus kasvaa (rivejä per px 8.8 per kehys)
K_TMAX   = $0040                ; purku: suurin kallistus 0,25 (14 astetta), sitten putoaa
K_G      = $005c                ; purku: painovoima (rivejä per kehys^2, 8.8): noin 100 riviä 24 kehyksessä
K_FALLN  = 24                   ; purku: kyltti poissa (k_gone) näin monen kehyksen jälkeen
K_YHIDE  = 215                  ; sprite pois, kun sen ensimmäinen rivi on kuvan alla (Y-rekisteri >= tämä)
K_LOCK   = 0                    ; 1 = valmis puskuri näkyviin vain piirron käynnistävällä kehyksellä (build.py, ajo):
                                ; piirrolla on koko piirtoväli aikaa ja kuva vaihtuu tasan K_RATE kehyksen välein
K_XLIIKE = 0                    ; 1 = 50 Hz:n vieritys: piirtojen välillä spritejen X siirtyy joka kehys tilan mukaan
                                ; (k_xmove; build.py kirjoittaa k_fx:n: px per u spriten keskellä)
        .endweak

K_PBASE   = (K_CANVAS & $3fff) / 64 ; kankaan ensimmäinen sprite-osoitin VIC-pankissa
K_VARS    = K_SCRATCH + $200    ; ajonaikaiset taulut (kaatoalueen kirjoitukset enintään +$1c8)
K_XMSB    = ((K_SPR_X0 >= 256) ? 1 : 0) | ((K_SPR_X0 + 24 >= 256) ? 2 : 0) | ((K_SPR_X0 + 48 >= 256) ? 4 : 0) | ((K_SPR_X0 + 72 >= 256) ? 8 : 0) | ((K_SPR_X0 + 96 >= 256) ? 16 : 0) | ((K_SPR_X0 + 120 >= 256) ? 32 : 0) | ((K_SPR_X0 + 144 >= 256) ? 64 : 0) | ((K_SPR_X0 + 168 >= 256) ? 128 : 0)
K_MASK    = (1 << K_NSPR) - 1   ; kyltin spritet 0..K_NSPR-1
K_ON      = 8                   ; välkkeen kesto kirjainta kohden (kehystä)
K_FALL    = 2                   ; käsikirjoituksen tilat: 0 näytä, 1 vieritä, 2 putoa

        .virtual K_ZP
k_s     .word ?                 ; vierityspaikka u-yksikköinä (etumerkillinen) + murto-osa
k_sf    .byte ?
k_txt   .word ?                 ; nykyinen teksti
k_cmd   .word ?                 ; käsikirjoituksen osoitin
k_d     .word ?                 ; kehyksiä komennon alusta
k_dur   .word ?
k_spd   .word ?                 ; vieritysnopeus 8.8
k_mode  .byte ?                 ; 0 näytä (valomainos), 1 vieritä, K_FALL (kallistuu ja putoaa)
k_newt  .byte ?                 ; tick vaihtoi tekstin
k_dirty .byte ?
k_shown .byte ?                 ; näkyvä puskuri 0/1
k_ready .byte ?                 ; takapuskuri valmis vaihtoon
k_rc    .byte ?                 ; piirtovälin laskuri
k_gone  .byte ?                 ; 1 = kyltti pudonnut pois (spritet pois, ei piirtoa)
k_en    .byte ?                 ; näkyvät spritet (k_wy)
k_busy  .byte ?                 ; piirto käynnissä
k_tilt  .word ?                 ; kallistus rivejä per px 8.8 (etumerkillinen, + = oikea pää alempana)
k_yoff  .word ?                 ; pystysiirto 8.8 (etumerkillinen)
k_vy    .word ?
; renderin kopio ja työmuuttujat
r_s     .word ?
r_txt   .word ?
r_tilt  .word ?
r_a     .byte ?                 ; etäisyys lähimpään komennon päähän (välke), 255 = kaikki palaa
r_buf   .byte ?                 ; takapuskuri 0/1
r_bsel  .byte ?                 ; takapuskurin sarakeosoitteiden siirto 0/32
r_first .byte ?                 ; ensimmäinen ehkä näkyvä kirjain ja sen u
r_ufirst .word ?
r_i     .byte ?
r_g     .byte ?
r_idx   .word ?                 ; u - s + UM
r_sh    .byte ?
r_gb    .byte ?
r_k     .byte ?
r_nb    .byte ?
r_top3  .word ?                 ; 3 * ylärivi (etumerkillinen)
r_t     .word ?
r_x0    .byte ?
r_last  .byte ?
r_tp    .word ?                 ; taulujen sivuosoitin (alatavu aina 0)
r_gp    .word ?                 ; nauha
r_d0    .word ?                 ; kankaan tavut
r_d1    .word ?
r_rec   .word ?                 ; glyfitietue
r_gp2   .word ?                 ; nauhaparin toinen nauha
r_d2    .word ?
r_shp   .byte ?                 ; siirtotaulun sivu
r_or    .byte ?
        .endv

; ---------------------------------------------------------------- alustus
kyltti_init
        ldx #K_NSPR - 1         ; vain spritet 0..K_NSPR-1, muiden spritejen bitit ennallaan
-       lda k_sprcol,x
        sta $d027,x
        txa
        asl
        clc
        adc #K_PBASE
        sta K_PTRS,x            ; puskuri A
        dex
        bpl -
        jsr k_sprx
        lda #~K_MASK & $ff
        and $d01c               ; hires
        sta $d01c
        lda #~K_MASK & $ff
        and $d017
        sta $d017
        lda #~K_MASK & $ff
        and $d01d
        sta $d01d
        lda #~K_MASK & $ff
        and $d01b               ; bittikartan edessä
        sta $d01b
        lda #0
        sta k_shown
        sta k_ready
        sta k_rc
        sta k_busy
        sta k_gone
        sta r_tp
        sta k_tilt
        sta k_tilt+1
        sta k_yoff
        sta k_yoff+1
        sta r_tilt
        sta r_tilt+1
        tax
-       sta k_vars,x            ; kallistustaulut nolliksi
        inx
        cpx #k_varend - k_vars
        bne -
        tax                   ; kangas ja kaatoalue tyhjiksi
-       sta K_CANVAS,x
        sta K_CANVAS+$100,x
        sta K_CANVAS+$200,x
        sta K_CANVAS+$300,x
        sta K_SCRATCH,x
        sta K_SCRATCH+$100,x
        inx
        bne -
        lda #0                  ; molempien puskurien sarakeosoitteet ja Y ilman kallistusta
        sta r_buf
        jsr k_cols
        inc r_buf
        jsr k_cols
        ldx #K_NSPR - 1
-       lda k_ybuf,x
        sta k_ycur,x
        dex
        bpl -
        jsr k_wy
        lda #K_MASK
        ora $d015
        sta $d015
        lda #<k_script
        sta k_cmd
        lda #>k_script
        sta k_cmd+1
        .if K_XLIIKE
        jsr k_next
        jmp k_xpush             ; alkutila renkaaseen (ensimmäisen kuvan tilannekuva)
        .else
        jmp k_next
        .endif

; purku alkaa: nykyinen teksti jää paikalleen, kallistuu ja putoaa (romahdusmoottori kutsuu osumassa)
kyltti_fall
        lda #K_FALL
        sta k_mode
        lda #$ff
        sta k_dur
        sta k_dur+1
        lda #0
        sta k_d
        sta k_d+1
        sta k_spd
        sta k_spd+1
        lda #1
        sta k_dirty
        rts

k_sprcol .byte 1, 1, 1, 1, 1, 1, 1, 1               ; valkoinen kuten maalattu kyltti (ei värisaumaa spritejen välissä)

; ---------------------------------------------------------------- kehys (IRQ)
kyltti_tick
        lda k_ready             ; valmis takapuskuri näkyviin: osoittimet ja sen Y-porras
        beq +
        .if K_LOCK
        lda k_rc                ; vain kehyksellä, jolla seuraava piirto alkaa (yli kehyksen piirto ei siirrä
        bne +                   ; vaihtoa: ilman lukitusta 4 + 2 kehyksen nykäys ajo-kyltissä)
        .endif
        lda k_shown
        eor #1
        sta k_shown
        tay
        .if K_XLIIKE
        lda k_itk,y             ; X-siirto lasketaan tämän kuvan piirron tilasta alkaen
        sta k_bt
        lda k_isl,y
        sta k_bsl
        lda k_igen,y
        sta k_bgen
        .endif
        ldx #K_NSPR - 1
-       txa
        asl
        ora k_shown
        clc
        adc #K_PBASE
        sta K_PTRS,x
        dex
        bpl -
        lda k_ybofs,y
        tay
        ldx #0
-       lda k_ybuf,y
        sta k_ycur,x
        iny
        inx
        cpx #K_NSPR
        bne -
        lda #0
        sta k_ready
+       lda k_mode              ; tilan liike (komennon kehyksessä d: d askelta tehty)
        beq k_tmove
        cmp #K_FALL
        beq k_tfall
        clc                     ; vieritys: s += nopeus
        lda k_sf
        adc k_spd
        sta k_sf
        lda k_s
        adc k_spd+1
        sta k_s
        bcc k_tmove
        inc k_s+1
        jmp k_tmove
k_tfall lda k_tilt+1            ; purku: kallistus kasvaa maksimiin ja painovoima samaan aikaan
        cmp #>K_TMAX
        bcc +
        bne k_tgrav
        lda k_tilt
        cmp #<K_TMAX
        bcs k_tgrav
+       clc
        lda k_tilt
        adc #<K_DTILT
        sta k_tilt
        lda k_tilt+1
        adc #>K_DTILT
        sta k_tilt+1
k_tgrav clc
        lda k_vy
        adc #<K_G
        sta k_vy
        lda k_vy+1
        adc #>K_G
        sta k_vy+1
        clc
        lda k_yoff
        adc k_vy
        sta k_yoff
        lda k_yoff+1
        adc k_vy+1
        sta k_yoff+1
        lda k_d                 ; K_FALLN kehyksen jälkeen kyltti on poissa (spritet pois, ei piirtoa)
        cmp #K_FALLN - 1
        bcc k_tmove
        lda #1
        sta k_gone
k_tmove inc k_d                 ; käsikirjoitus
        bne +
        inc k_d+1
+       lda k_d
        cmp k_dur
        lda k_d+1
        sbc k_dur+1
        bcc +
        jsr k_next
+       .if K_XLIIKE
        jsr k_xmove
        .endif
        jsr k_wy
        dec k_rc                ; piirto joka K_RATE. kehys (vieritys, purku ja välke)
        bpl k_rts3
        lda #K_RATE - 1
        sta k_rc
        lda k_mode
        bne k_dset
k_tshow lda k_d+1               ; välke vain komennon alussa ja lopussa
        bne +
        lda k_d
        cmp #K_ON + 16 + K_RATE        ; viimeinen piirto välkkeen jälkeen (piirtoväli)
        bcc k_dset
+       sec
        lda k_dur
        sbc k_d
        tax
        lda k_dur+1
        sbc k_d+1
        bne +
        cpx #K_ON + 16 + K_RATE
        bcc k_dset
+
k_rts3  rts
k_dset  lda #1
        sta k_dirty
        rts

; spritejen Y = näkyvän puskurin porras + pystysiirto; sprite pois ($d015), kun se on kokonaan kuvan alla
; (Y >= K_YHIDE tai yli 255), kaikki pois, kun k_gone
k_wy    lda k_gone
        bne k_wyoff
        ldx #K_NSPR - 1
        ldy #2 * (K_NSPR - 1)
-       lda k_ycur,x
        clc
        adc k_yoff+1
        bcs k_wyh
        cmp #K_YHIDE
        bcs k_wyh
        sta $d001,y
        sec                     ; näkyvissä
        bcs +
k_wyh   clc
+       rol k_en                ; viimeisenä sprite 0 bittiin 0
        dey
        dey
        dex
        bpl -
        lda k_en                ; vain kyltin bitit (rol jättää vanhat bitit K_NSPR..7)
        and #K_MASK
        sta k_en
        lda $d015
        and #~K_MASK & $ff
        ora k_en
        sta $d015
        rts
k_wyoff lda $d015
        and #~K_MASK & $ff
        sta $d015
        rts

; kaikkien kyltin spritejen tila kerralla (purun IRQ:sta jakorivillä): värit, osoittimet, X, $d010,
; $d01c/$d017/$d01d ja k_wy:n kautta Y ja $d015. Värit kirjoitetaan, joten kutsu rivillä, jolla kyltin
; spritejä ei piirretä (8565:n harmaa piste).
kyltti_spr
        ldx #K_NSPR - 1
-       lda k_sprcol,x
        sta $d027,x
        txa
        asl
        ora k_shown
        clc
        adc #K_PBASE
        sta K_PTRS,x
        dex
        bpl -
        jsr k_sprx
        lda #~K_MASK & $ff
        and $d01c
        sta $d01c
        lda #~K_MASK & $ff
        and $d017
        sta $d017
        lda #~K_MASK & $ff
        and $d01d
        sta $d01d
        jmp k_wy

k_sprx  .for k = 0, k < K_NSPR, k += 1  ; X ja $d010 (kiinteät)
        lda #<(K_SPR_X0 + 24 * k)
        sta $d000 + 2 * k
        .next
        lda $d010
        and #~K_MASK & $ff
        ora #K_XMSB & K_MASK
        sta $d010
        rts

k_ybofs .byte 0, 8

        .if K_XLIIKE
; 50 Hz:n vieritys (kaikki liike joka kehys): kuva piirretään joka K_RATE. kehys, ja välikehyksinä
; spritet siirtyvät vasemmalle sen verran kuin tila on edennyt kuvan piirrosta. Näytetty kuva on tilasta
; L kehystä jäljessä (piirto -> vaihto); kehyksellä n vaihdon jälkeen siirto on s(piirto + n) - s(piirto)
; u-yksikköä, sprite i:lle px = u * k_fx[i] / 256 (perspektiivi: lähipää liikkuu nopeammin). Tilahistoria
; renkaassa (8 kehystä); komennon vaihtuessa (k_gen) siirto pysyy, kunnes seuraava kuva vaihtuu.
k_xmove jsr k_xpush
        lda k_tk                ; näytettävä tila K_RATE kehystä jäljessä (lukittu vaihto: kuva vaihtuu K_RATE
        sec                     ; kehystä piirron tilannekuvan jälkeen, joten vaihdossa siirto on 0)
        sbc #K_RATE
        tax
        sec
        sbc k_bt
        bmi k_xzero             ; kuvaa vanhempi tila (lyhyempi viive): kuva sellaisenaan
        cmp #8
        bcs k_xset              ; rengas ohi: siirto ennallaan
        txa
        and #7
        tax
        lda k_rgen,x
        cmp k_bgen
        bne k_xset              ; eri komento: siirto ennallaan
        lda k_rsl,x             ; d = s - kuvan s (8.8 u), dq = d * 16 (1/16 u, enintään 255)
        sec
        sbc k_bsl
        bmi k_xzero
        cmp #16
        bcs k_xmax
        sta k_dq
        lda k_rsf,x
        lsr k_dq
        ror
        lsr k_dq
        ror
        lsr k_dq
        ror
        lsr k_dq
        ror
        sta k_dq                ; d_hi (< 16) ja d_lo:n ylin nibble
        jmp k_xmul
k_xzero lda #0
        .byte $2c
k_xmax  lda #255
        sta k_dq
k_xmul  ldx #K_NSPR - 1         ; k_off[i] = round(dq * k_fx[i] / 4096)
-       lda k_fx,x
        sta k_mf
        lda k_dq
        sta k_ma
        lda #0
        ldy #8
        lsr k_ma
k_xm1   bcc +
        clc
        adc k_mf
+       ror
        ror k_ma
        dey
        bne k_xm1
        clc                     ; A:k_ma = tulo, px = (tulo + $800) >> 12
        adc #8
        ror
        lsr
        lsr
        lsr
        sta k_off,x
        dex
        bpl -
k_xset  ldx #K_NSPR - 1         ; X = kanta - siirto, ylin bitti $d010:aan (vain kyltin bitit)
        ldy #2 * (K_NSPR - 1)
        lda #0
        sta k_msb
-       sec
        lda k_xblo,x
        sbc k_off,x
        sta $d000,y
        lda k_xbhi,x
        sbc #0
        lsr
        rol k_msb
        dey
        dey
        dex
        bpl -
        lda $d010
        and #~K_MASK & $ff
        ora k_msb
        sta $d010
        rts

; tila renkaaseen (tick ja k_xroll)
k_xpush inc k_tk
        lda k_tk
        and #7
        tax
        lda k_s
        sta k_rsl,x
        lda k_sf
        sta k_rsf,x
        lda k_gen
        sta k_rgen,x
        rts

; ensimmäisen kuvan esivieritys (glue_ajo ajo_go ennen ensimmäistä tickiä): tila K_RATE - 1 kehystä eteen ilman
; vaihtoa, joten ensimmäinen kuva näkyy samalla viiveellä kuin muut ja liike on tasainen alusta asti
k_xroll ldy #K_RATE - 1
-       clc
        lda k_sf
        adc k_spd
        sta k_sf
        lda k_s
        adc k_spd+1
        sta k_s
        bcc +
        inc k_s+1
+       inc k_d
        bne +
        inc k_d+1
+       jsr k_xpush
        dey
        bne -
        rts

k_xblo  .byte <(K_SPR_X0 + 24 * range(K_NSPR))
k_xbhi  .byte >(K_SPR_X0 + 24 * range(K_NSPR))
        .endif

; seuraava käsikirjoituksen komento: tila, teksti, kesto, alku-s, nopeus 8.8 (9 tavua)
k_next  ldy #0
        lda (k_cmd),y
        bpl +
        lda #<k_script          ; $ff = alkuun
        sta k_cmd
        lda #>k_script
        sta k_cmd+1
        lda (k_cmd),y
+       sta k_mode
        iny
        lda (k_cmd),y
        sta k_txt
        iny
        lda (k_cmd),y
        sta k_txt+1
        iny
        lda (k_cmd),y
        sta k_dur
        iny
        lda (k_cmd),y
        sta k_dur+1
        iny
        lda (k_cmd),y
        sta k_s
        iny
        lda (k_cmd),y
        sta k_s+1
        iny
        lda (k_cmd),y
        sta k_spd
        iny
        lda (k_cmd),y
        sta k_spd+1
        lda #0
        sta k_sf
        sta k_d
        sta k_d+1
        sta k_tilt
        sta k_tilt+1
        sta k_yoff
        sta k_yoff+1
        sta k_vy
        sta k_vy+1
        lda #1
        sta k_newt
        sta k_dirty
        .if K_XLIIKE
        inc k_gen               ; uusi komento: tila ei jatku edellisestä (k_xmove pitää siirron)
        .endif
        clc
        lda k_cmd
        adc #9
        sta k_cmd
        bcc +
        inc k_cmd+1
+       rts

; ---------------------------------------------------------------- piirto (pääsilmukka)
kyltti_render                   ; saa kutsua myös IRQ:sta (cli:n jälkeen): sisäkkäinen kutsu palaa heti
        lda k_dirty
        beq k_rts
        lda k_gone
        bne k_rts
        sei
        lda k_busy              ; piirto kesken tai edellinen ei vielä näkyvissä
        ora k_ready
        beq k_rbeg
        cli
        rts
k_rbeg  lda #1                  ; kopio tilasta (k_rbeg..k_rend: mittaus)
        sta k_busy
        lda #0
        sta k_dirty
        .if K_XLIIKE
        lda k_shown             ; takapuskurin kuvan tila X-siirtoa varten (k_xmove)
        eor #1
        tax
        lda k_tk
        sta k_itk,x
        lda k_s
        sta k_isl,x
        lda k_gen
        sta k_igen,x
        .endif
        lda k_s
        sta r_s
        lda k_s+1
        sta r_s+1
        lda k_txt
        sta r_txt
        lda k_txt+1
        sta r_txt+1
        lda k_tilt
        sta r_tilt
        lda k_tilt+1
        sta r_tilt+1
        ldx #255                ; välkkeen etäisyys a = min(d, dur - d), vain näyttötilassa
        lda k_mode
        bne k_adone
        sec
        lda k_dur
        sbc k_d
        tay
        lda k_dur+1
        sbc k_d+1
        bne +
        tya
        tax
+       lda k_d+1
        bne k_adone
        cpx k_d
        bcc k_adone
        ldx k_d
k_adone stx r_a
        ldy #0
        lda k_newt
        sty k_newt
        cli
        beq +
        sty r_first             ; uusi teksti: ensimmäinen kirjain alusta
        sty r_ufirst
        sty r_ufirst+1
+       lda k_shown             ; takapuskuri
        eor #1
        sta r_buf
        tax
        lda k_bsel,x
        sta r_bsel
        txa                     ; kallistus muuttui tämän puskurin edellisestä piirrosta?
        asl
        tax
        lda r_tilt
        cmp k_tlast,x
        bne k_rtilt
        lda r_tilt+1
        cmp k_tlast+1,x
        bne k_rtilt
        ora r_tilt              ; sama kallistus: nolla = kapea tyhjennys, muuten koko kangas
        bne k_rfull
        ldx r_buf
        ldy k_bufoff,x
        jsr k_clear
        jmp k_rdraw
k_rtilt lda k_tlast,x           ; vanha sisältö kallistettu: koko kangas
        ora k_tlast+1,x
        php
        lda r_tilt
        sta k_tlast,x
        lda r_tilt+1
        sta k_tlast+1,x
        jsr k_trows
        jsr k_cols
        plp
        bne k_rfull
        lda r_tilt
        ora r_tilt+1
        bne k_rfull
        ldx r_buf
        ldy k_bufoff,x
        jsr k_clear
        jmp k_rdraw
k_rfull ldx r_buf
        lda k_bufoff,x
        tax
        jsr k_clearf
k_rdraw jsr k_trows             ; (palaa heti, jos siirrot ovat jo tälle kallistukselle)
        jsr k_letters
k_rend  lda #1
        sta k_ready
        lda #0
        sta k_busy
k_rts   rts

k_bufoff .byte 0, 64
k_bsel   .byte 0, 32

; sarakkeiden kallistussiirrot: trow[i] = floor((tilt * (8 (i - G) + 4) + $80) / 256), i = 0..31,
; G = K_GUTTER / 8 kaatoalueen saraketta kankaan vasemmalla puolella
k_trows lda r_tilt+1
        cmp k_trowt+1
        bne +
        lda r_tilt
        cmp k_trowt
        beq k_rts
+       lda r_tilt
        sta k_trowt
        sta r_d0                ; r_d0 = 4 tilt, r_d1 = 8 tilt
        lda r_tilt+1
        sta k_trowt+1
        asl r_d0
        rol
        asl r_d0
        rol
        sta r_d0+1
        lda r_d0
        asl
        sta r_d1
        lda r_d0+1
        rol
        sta r_d1+1
        clc                     ; acc = $80 - (8 G - 4) tilt
        lda r_d0
        adc r_d1
        sta r_t
        lda r_d0+1
        adc r_d1+1
        sta r_t+1
        .rept K_GUTTER / 8 - 2
        clc
        lda r_t
        adc r_d1
        sta r_t
        lda r_t+1
        adc r_d1+1
        sta r_t+1
        .endrept
        sec
        lda #$80
        sbc r_t
        sta r_t
        lda #0
        sbc r_t+1
        sta r_t+1
        ldx #0
-       lda r_t+1
        sta k_trow,x
        clc
        lda r_t
        adc r_d1
        sta r_t
        lda r_t+1
        adc r_d1+1
        sta r_t+1
        inx
        cpx #32
        bne -
        rts

; puskurin r_buf sarakeosoitteet: osoite = kanta - 3 v, v = spriten porras + sen keskisarakkeen siirto
; (kaatoalueen sarakkeilla v = oma siirto) ja spritejen Y puskurille
k_cols  lda r_buf
        asl
        asl
        asl
        sta r_k                 ; 8 * puskuri (k_ybuf)
        asl
        asl
        sta r_gb                ; 32 * puskuri
        ldx #0                  ; sarake i = 0..31, c = i - G: kanta ja v lasketaan suoraan
k_cl    stx r_i
        txa
        sec
        sbc #K_GUTTER / 8
        bcc k_cgut              ; c < 0: kaatoalue
        cmp #K_NCOLS            ; näkyvät sarakkeet (loput kaatoalueelle)
        bcs k_cgut
        ldy #0                  ; k = c / 3 (Y), m = c % 3 (A)
k_cdiv  cmp #3
        bcc +
        sbc #3
        iny
        bne k_cdiv
+       sta r_last              ; m
        sty r_x0                ; k
        tya                     ; kanta = K_CANVAS + 64 puskuri + 128 k + m
        lsr
        tay                     ; k >> 1 (sivu)
        lda #0
        ror                     ; (k & 1) * 128
        ora r_last
        clc
        adc r_gb                ; + 32 puskuri, kahdesti = 64 puskuri
        adc r_gb
        adc #<K_CANVAS
        sta r_d1
        tya
        adc #>K_CANVAS
        sta r_d1+1
        ldy r_x0                ; v = porras[k] + siirto[3k + 1 + G] (keskisarake)
        lda r_i                 ; 3k + 1 + G = c - m + 1 + G = i - m + 1
        sec
        sbc r_last
        tax
        lda k_ys,y
        clc
        adc k_trow+1,x
        jmp k_cset
k_cgut  lda #<(K_SCRATCH + $100) ; kaatoalue: kanta = K_SCRATCH + $100 + 64 puskuri, v = oma siirto
        clc
        adc r_gb
        adc r_gb
        sta r_d1
        lda #>(K_SCRATCH + $100)
        adc #0
        sta r_d1+1
        ldx r_i
        lda k_trow,x
k_cset  ldy #0                  ; v etumerkillisenä 16 bittiin, 3 v
        sta r_t
        ora #0
        bpl +
        dey
+       sty r_t+1
        asl
        sta r_d0
        tya
        rol
        sta r_d0+1
        clc
        lda r_d0
        adc r_t
        sta r_d0
        lda r_d0+1
        adc r_t+1
        sta r_d0+1
        lda r_i                 ; kanta - 3 v
        ora r_gb
        tay
        sec
        lda r_d1
        sbc r_d0
        sta k_collo,y
        lda r_d1+1
        sbc r_d0+1
        sta k_colhi,y
        ldx r_i
        inx
        cpx #32
        bne k_cl
        ldx #0                  ; spritejen Y: K_ROW0 - 1 + porras + keskisarakkeen siirto
        ldy r_k
-       stx r_i
        lda k_ys,x
        clc
        adc #K_ROW0 - 1
        pha
        txa
        asl
        adc r_i
        tax
        pla
        clc
        adc k_trow + 1 + K_GUTTER / 8,x
        sta k_ybuf,y
        iny
        ldx r_i
        inx
        cpx #K_NSPR
        bne -
        rts

; kaikki näkyvät kirjaimet
k_letters
        ldy r_first             ; ohita kokonaan vasemmalle kadonneet: u + adv - s < 0
-       lda (r_txt),y           ; (piirrettävillä u - s >= -adv >= -UM, joten tauluindeksi >= 0)
        bmi k_rts2
        tax
        clc
        lda r_ufirst
        adc k_adv,x
        sta r_idx
        lda r_ufirst+1
        adc #0
        sta r_idx+1
        lda r_idx               ; u + adv - s < 0 ?
        cmp r_s
        lda r_idx+1
        sbc r_s+1
        bvc +
        eor #$80                ; etumerkillinen vertailu
+       bpl +
        lda r_idx
        sta r_ufirst
        lda r_idx+1
        sta r_ufirst+1
        inc r_first
        ldy r_first
        jmp -
+       sty r_i                 ; idx = u - s + UM, kasvaa kirjaimen etenemällä
        sec
        lda r_ufirst
        sbc r_s
        tax
        lda r_ufirst+1
        sbc r_s+1
        tay
        txa
        clc
        adc #K_UM
        sta r_idx
        tya
        adc #0
        sta r_idx+1
k_lloop ldy r_i
        lda (r_txt),y
        bmi k_rts2              ; $ff = tekstin loppu
        sta r_g
        lda r_idx+1             ; alku oikean pään takana: valmis
        cmp #>(K_NU + K_UM + 1)
        bcc +
        bne k_rts2
        lda r_idx
        cmp #<(K_NU + K_UM + 1)
        bcs k_rts2
+       lda r_a                 ; välke: palaa, jos a >= t_i + K_ON tai (a >= t_i ja kohina)
        bmi k_lit
        tya
        and #63
        tax
        lda r_a
        sec
        sbc k_rnd,x
        bcc k_skip
        cmp #K_ON
        bcs k_lit
        txa
        adc r_a                 ; kohina = k_rnd[(i + a) & 63] bitti 0
        and #63
        tax
        lda k_rnd,x
        lsr
        bcc k_skip
k_lit   ldx r_g
        beq k_skip              ; välilyönti
        jsr k_glyph
k_skip  ldx r_g
        clc
        lda r_idx
        adc k_adv,x
        sta r_idx
        bcc +
        inc r_idx+1
+       inc r_i
        jmp k_lloop
k_rts2  rts

; yksi kirjain: r_idx = alku u - s + UM, X = r_g = merkki
k_glyph clc                     ; keskikohta: kokoluokka << K_TBITS | ylärivi (k_ctt)
        lda r_idx
        adc k_adv2,x
        tay
        lda r_idx+1
        adc #>k_ctt
        sta r_tp+1
        lda (r_tp),y
        tay
        and #(1 << K_TBITS) - 1
        sta r_t                 ; ylärivi ilman kallistusta
        tya
        and #~((1 << K_TBITS) - 1) & $ff
        .if K_TBITS == 6        ; jyrkkä kaista: kokoluokka bitit 6-7 -> 5-6
        lsr
        .endif
        ora r_g
        tax                     ; X = kokoluokka << 5 | merkki
        lda k_reclo,x           ; glyfitietue: [3 (s - 1), nauhoja, (lo, hi, viimeinen sarake) x nauhoja]
        sta r_rec
        lda k_rechi,x
        sta r_rec+1
        ldy #0
        lda (r_rec),y
        sta r_x0
        iny
        lda (r_rec),y
        sta r_nb
        iny
        sty r_k                 ; nauhakentän paikka tietueessa
        lda r_idx+1             ; alku: x + GUTTER
        clc
        adc #>k_xt
        sta r_tp+1
        ldy r_idx
        lda (r_tp),y
        tay
        and #7
        sta r_sh
        adc #>k_shtab           ; carry 0: siirron sivu (alatavu kiinteä)
        sta r_shp
        tya
        lsr
        lsr
        lsr
        tax                     ; ylärivi += alkusarakkeen kallistussiirto
        ora r_bsel
        sta r_gb
        lda r_t
        clc
        adc k_trow,x
        bmi k_tneg              ; 3 * ylärivi: tavallisesti 0..85, jolloin yläosa on 0 tai 1
        sta r_t
        asl
        adc r_t
        sta r_top3
        lda #0
        adc #0
        sta r_top3+1
        jmp k_strip
k_tneg  sta r_t                 ; negatiivinen (vain kallistuksessa)
        asl
        sta r_top3
        lda #$ff
        rol
        sta r_top3+1
        clc
        lda r_top3
        adc r_t
        sta r_top3
        lda r_top3+1
        adc #$ff
        sta r_top3+1

; nauha (tai nauhapari) kerrallaan; r_k = seuraavan nauhan kenttä tietueessa
k_strip ldy r_k
        lda (r_rec),y
        sta r_gp
        iny
        lda (r_rec),y
        sta r_gp+1
        iny
        lda (r_rec),y
        iny
        sty r_k
        clc
        adc r_sh
        sta r_last              ; >= 8: oikea osa ulottuu seuraavaan tavuun
        ldx r_gb                ; d0 = sarakkeen osoite + 3 * ylärivi
        clc
        lda k_collo,x
        adc r_top3
        sta r_d0
        lda k_colhi,x
        adc r_top3+1
        sta r_d0+1
        lda r_nb
        cmp #2
        bcs k_pair
        ldy r_x0                ; yksi nauha
        lda r_last
        cmp #8
        bcs k_twos
        lda r_shp
        sta k_r1+2
k_onel  lax (r_gp),y            ; sanakirjaindeksi A:han ja X:ään
k_r1    lda k_shtab,x
        ora (r_d0),y
        sta (r_d0),y
        dey
        dey
        dey
        bpl k_onel
        rts
k_twos  clc                     ; d1 = seuraava sarake (X = r_gb)
        lda k_collo+1,x
        adc r_top3
        sta r_d1
        lda k_colhi+1,x
        adc r_top3+1
        sta r_d1+1
        lda r_shp
        sta k_r2+2
        sta k_l2+2
k_twol  lax (r_gp),y
k_r2    lda k_shtab,x
        ora (r_d0),y
        sta (r_d0),y
k_l2    lda k_shtab + K_LOFS,x
        sta (r_d1),y            ; seuraava tavu on vielä koskematon: ei ora
        dey
        dey
        dey
        bpl k_twol
        rts

; kaksi nauhaa samalla rivisilmukalla: d0 |= R(a), d1 = L(a) | R(b), d2 = L(b)
k_pair  clc                     ; d1 = seuraava sarake (X = r_gb)
        lda k_collo+1,x
        adc r_top3
        sta r_d1
        lda k_colhi+1,x
        adc r_top3+1
        sta r_d1+1
        ldy r_k
        lda (r_rec),y
        sta r_gp2
        iny
        lda (r_rec),y
        sta r_gp2+1
        iny
        lda (r_rec),y
        iny
        sty r_k
        clc
        adc r_sh
        cmp #8
        lda r_shp
        ldy r_x0
        bcs k_p3s
        sta k_p2a+2
        sta k_p2b+2
        sta k_p2c+2
k_p2l   lax (r_gp),y
k_p2a   lda k_shtab,x
        ora (r_d0),y
        sta (r_d0),y
k_p2b   lda k_shtab + K_LOFS,x
        sta r_or
        lax (r_gp2),y
k_p2c   lda k_shtab,x
        ora r_or
        sta (r_d1),y
        dey
        dey
        dey
        bpl k_p2l
        jmp k_pnext
k_p3s   sta k_p3a+2
        sta k_p3b+2
        sta k_p3c+2
        sta k_p3d+2
        ldx r_gb                ; d2
        clc
        lda k_collo+2,x
        adc r_top3
        sta r_d2
        lda k_colhi+2,x
        adc r_top3+1
        sta r_d2+1
k_p3l   lax (r_gp),y
k_p3a   lda k_shtab,x
        ora (r_d0),y
        sta (r_d0),y
k_p3b   lda k_shtab + K_LOFS,x
        sta r_or
        lax (r_gp2),y
k_p3c   lda k_shtab,x
        ora r_or
        sta (r_d1),y
k_p3d   lda k_shtab + K_LOFS,x
        sta (r_d2),y
        dey
        dey
        dey
        bpl k_p3l
k_pnext inc r_gb                ; kolmas nauha (leveä W, M) alkaa sarakkeesta gb + 2
        inc r_gb
        dec r_nb
        dec r_nb
        beq +
        jmp k_strip
+       rts

; kankaan tyhjennys: Y = puskurin siirto 0/64, kirjainten rivit ilman kallistusta (build.py)
k_clear tya
        tax
        lda #0
        .include "clear.inc"
        rts

; koko kankaan tyhjennys (kallistus): X = puskurin siirto 0/64
k_clearf txa
        clc
        adc #62
        tax
        ldy #63
        lda #0
-       .for k = 0, k < K_NSPR, k += 1
        sta K_CANVAS + 128 * k,x
        .next
        dex
        dey
        bne -
        rts

; välkkeen satunnaisviiveet (0..15); kohina on saman taulun bitti 0
k_rnd   .byte 2, 11, 6, 14, 0, 8, 4, 12, 7, 0, 10, 5, 14, 2, 8, 12, 4, 1, 10, 6, 15, 3, 9, 13
        .byte 6, 0, 11, 4, 8, 14, 2, 10, 12, 5, 0, 8, 14, 3, 7, 10, 1, 12, 4, 15, 6, 9, 2, 13
        .byte 4, 8, 0, 12, 10, 6, 14, 2, 11, 7, 0, 5, 9, 14, 3, 10

; ajonaikaiset taulut (kyltti_init nollaa): kankaan varauksen lopussa, eivät vie moduulin tilaa
        .virtual K_VARS
k_vars
k_collo .fill 64                ; sarakkeen osoite kallistuksineen, puskuri A 0..31, B 32..63
k_colhi .fill 64
k_trow  .fill 32                ; sarakkeen kallistussiirto riveinä
k_ybuf  .fill 16                ; spritejen Y puskureittain
k_ycur  .fill 8                 ; näkyvän puskurin Y
k_tlast .fill 4                 ; puskurin viimeisimmän piirron kallistus
k_trowt .fill 2                 ; kallistus, jolla k_trow on laskettu
        .if K_XLIIKE            ; k_xmove: tilarengas, kuvien tilannekuvat, siirrot
k_rsl   .fill 8                 ; tilarengas (k_tk & 7): s:n alatavu, murto-osa, komento
k_rsf   .fill 8
k_rgen  .fill 8
k_itk   .fill 2
k_isl   .fill 2
k_igen  .fill 2
k_off   .fill 8
k_tk    .byte ?
k_gen   .byte ?
k_bt    .byte ?
k_bsl   .byte ?
k_bgen  .byte ?
k_dq    .byte ?
k_ma    .byte ?
k_mf    .byte ?
k_msb   .byte ?
        .endif
k_varend
        .endv
        .cerror k_varend > K_SCRATCH + $300, "kyltin muuttujat yli kaatoalueen varauksen"
