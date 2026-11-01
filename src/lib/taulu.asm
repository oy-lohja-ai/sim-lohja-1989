; Mykkäelokuvan kerrontataulu (musta pohja, teksti kirjoittuu efektillä, kulmissa krumeluurit): hires-bittikartta,
; jossa kaikki värit tulevat ruudusta, joten esiin kirjoittuminen, välke ja
; häivytys ovat ruudun värikirjoituksia. Data: tools/gfx/taulu.py (teksti, kesto, kirjasin ja kulmakoriste
; parametreina) -> taulu_<nimi>.inc ja taulu_<nimi>_data.asm. Käyttö: src/proto/taulu/taulu.asm ja
; src/proto/sokeripala/sokeripala.asm.
;
; Reaaliajassa 6510:llä:
;   - kehys valottuu kehyksissä 0-7, tekstin solut valottuvat mustasta valkoiseksi (4 askelta, TAULU_NOUSU
;     kehystä) kirjoitusjärjestyksessä (taulu_t_f = solun alkukehys)
;   - filmin välke: satunnaisesti (LFSR) koko taulu vaaleanharmaaksi 1-3 kehykseksi
;   - naarmu: pystyviiva 2-4 Y-levennetyllä spritellä, syntyy satunnaisesti, elää 12-43 kehystä ja liukuu
;     hitaasti sivulle (ei edestakaista nykimistä)
;   - pöly: 3 spritehiukkasta satunnaisissa paikoissa 1-2 kehystä kerrallaan
;   - lopussa (TAULU_KESTO - 8 - TAULU_MUSTA) taulu himmenee mustaksi
;
; Sisällyttäjä määrittelee:
;   TAULU_SCREEN  ruutu (VIC-pankissa, jossa bittikartta on)
;   TAULU_SPRBLK  ensimmäinen 4 spritelohkosta (taulu_spr kopioidaan sinne taulu_alussa, jos TAULU_SPRMEM)
;   TAULU_SPRMEM  spritelohkojen osoite (taulu_alku kopioi taulu_spr sinne; 0 = ei kopiota)
;   TZP           11 tavua nollasivua
; ja sisällyttää taulu_<nimi>.inc ennen tätä tiedostoa ja taulu_<nimi>_data.asm minne tahansa.
;
; Kutsut: taulu_alku (pääsäikeessä tai IRQ:ssa ennen ensimmäistä kehystä: ruutu mustaksi, spritet),
;         taulu_vic (VIC-rekisterit; pankki ja $d018 sisällyttäjältä), taulu_kehys (A = taulun kehys 0-255,
;         kerran kehyksessä rivin 250 jälkeen: kirjoitukset ennen ruudun yläreunaa)

        .cerror TAULU_KESTO > 255, "taulun kesto enintään 255 kehystä"
        .cerror TAULU_SCREEN & $3ff, "TAULU_SCREEN: _kehys_v ja _valmiit yhdistävät solun ylätavun (0-3) or:lla"
        .weak
TAULU_SPRMEM = 0                ; 0 = sisällyttäjä kopioi taulu_spr itse
TAULU_MERKKI = 0                ; 1 = hires-merkkitila: ruudussa merkkikoodit (sisällyttäjältä), värit värimuistiin
TAULU_MUSTA = 0                 ; kehyksiä mustaa lopussa häivytyksen jälkeen (taulu2: Hillnerin hil_prep, jatkuva)
TAULU_JALKI = 0                 ; 1 = taulu_jalki: taulun jälkeen vain naarmu ja pöly (siirtymä seuraavaan mustalla)
TAULU_TYHJAA_ERIKSEEN = 0       ; 1 = taulu_alku ei tyhjennä värejä: sisällyttäjä kutsuu taulu_tyhjaa (värimuisti vasta
        .endweak                ; taulun näkyessä, kun edellinen kohtaus pyörii taulu_alun aikana)
TAULU_COL = TAULU_MERKKI ? $d800 : TAULU_SCREEN  ; solujen värit: bittikartan ruutu (yläpuolisko) tai värimuisti
TAULU_TV = TAULU_MERKKI ? 4 : 0

        .virtual TZP
tz_t    .byte ?
tz_lo   .byte ?                 ; ensimmäinen tekstin solu, joka ei ole vielä täysin valottunut
tz_lvl  .byte ?                 ; välke: 0 = valkoinen, 1 = vaaleanharmaa
tz_flk  .byte ?                 ; välkkeen jäljellä olevat kehykset
tz_rnd  .byte ?
tz_sx   .byte ?                 ; naarmun x (sprite-koordinaatti, alatavu; yläbitti tz_sxh)
tz_sl   .byte ?                 ; naarmun elinaika (0 = ei naarmua)
tz_sd   .byte ?                 ; naarmun liuku: +1 / $ff / 0 joka 4. kehys
tz_p    .word ?
tz_rh   .byte ?                 ; satunnaisluvun yläbitit (16-bittinen LFSR)
        .endv

taulu_ramp .byte $00 >> TAULU_TV, $b0 >> TAULU_TV, $c0 >> TAULU_TV, $f0 >> TAULU_TV, $10 >> TAULU_TV   ; musta, tummanharmaa, harmaa,
                                                ; vaaleanharmaa, valkoinen (bittikartan ruudun yläpuolisko)

taulu_alku
        .if !TAULU_TYHJAA_ERIKSEEN
        lda #0
        ldx #0
-       sta TAULU_COL,x
        sta TAULU_COL+$100,x
        sta TAULU_COL+$200,x
        sta TAULU_COL+$2e8,x
        inx
        bne -
        .endif
        ldx #TZP
        lda #0
-       sta $00,x
        inx
        cpx #TZP + 11
        bne -
        lda #$5a
        sta tz_rnd
        lda #$c3
        sta tz_rh
        .if TAULU_SPRMEM != 0
        ldx #0
-       lda taulu_spr,x
        sta TAULU_SPRMEM,x
        inx
        bne -
        .endif
        lda #TAULU_SPRBLK
        ldx #3
-       sta TAULU_SCREEN + $3f8,x       ; naarmu: spritet 0-3 samaa lohkoa
        dex
        bpl -
        ldx #2
-       txa
        clc
        adc #TAULU_SPRBLK + 1
        sta TAULU_SCREEN + $3fc,x       ; pöly: spritet 4-6
        dex
        bpl -
        rts

taulu_vic
        lda #TAULU_MERKKI ? $1b : $3b   ; hires-bittikartta tai -merkkitila
        sta $d011
        lda #$08
        sta $d016
        lda #0
        sta $d020
        sta $d021
        sta $d015
        sta $d01c
        sta $d01d
        lda #%00001111                  ; naarmun spritet Y-levennettyinä
        sta $d017
        lda #12                         ; naarmu harmaa, pöly vaaleanharmaa ja valkoinen
        ldx #3
-       sta $d027,x
        dex
        bpl -
        lda #15
        sta $d02b
        sta $d02d
        lda #1
        sta $d02c
        rts

; satunnaisluku -> A: 16-bittinen Galois-LFSR (x^16+x^14+x^13+x^11+1) 8 askelta kerralla, jotta peräkkäiset
; luvut eivät ole toistensa siirtoja (8-bittisellä välke ja naarmu eivät koskaan osuisi). Y säilyy.
taulu_rnd
        sty _ry+1
        ldy #8
-       lsr tz_rh
        ror tz_rnd
        bcc +
        lda tz_rh
        eor #$b4
        sta tz_rh
+       dey
        bne -
_ry     ldy #0
        lda tz_rnd
        rts

        .if TAULU_TYHJAA_ERIKSEEN
; taulu_tyhjaa: kaikki solut mustiksi (värit TAULU_COL:iin, noin 6 400 sykliä)
taulu_tyhjaa
        lda #0
        ldx #0
-       sta TAULU_COL,x
        sta TAULU_COL+$100,x
        sta TAULU_COL+$200,x
        sta TAULU_COL+$2e8,x
        inx
        bne -
        rts
        .endif

; set_cell: X = solun ala-, Y = ylätavu (0-3), A = väri ruutuun
taulu_set
        pha
        tya
        clc
        adc #>TAULU_COL
        sta tz_p+1
        stx tz_p
        pla
        ldy #0
        sta (tz_p),y
        rts

taulu_kehys
        sta tz_t
        .if TAULU_JALKI
        ldx tz_jalki                    ; taulun jälkeen: vain naarmu ja pöly (värit jo mustia)
        beq +
        jmp _naarmu
+       lda tz_t
        .endif
        ; ---------------------------------------------------------------- loppuhäivytys
        cmp #TAULU_KESTO - 8 - TAULU_MUSTA
        bcc _ei_loppu
        sec
        sbc #TAULU_KESTO - 8 - TAULU_MUSTA
        .if TAULU_MUSTA                 ; häivytyksen jälkeen musta loppuun asti: värit ovat jo mustia (ramp 0 kahdessa
        cmp #8                          ; viimeisessä häivytyskehyksessä), joten ei kirjoituksia: seuraavan kohtauksen
        bcc +                           ; alustus (hil_prep) saa kehyksen ajan
          .if TAULU_MERKKI              ; merkkitila: ensimmäisellä mustalla kehyksellä ruutu tyhjiksi merkeiksi, jotta
        bne _m0                         ; seuraavan alustuksen värimuistikirjoitukset eivät näytä taulua (koti_init1,
        lda #0                          ; kp_init)
        tax
-       sta TAULU_SCREEN,x
        sta TAULU_SCREEN+$100,x
        sta TAULU_SCREEN+$200,x
        sta TAULU_SCREEN+$2e8,x
        inx
        bne -
        sta $d015                       ; rungon IRQ:hon (musiikki ja kello): taulun koodi ja merkistö ovat vapaita
        lda #<R_TICK_RTS                ; mustan ajan, joten seuraavan alustus saa kirjoittaa niiden päälle (kuopan
        sta R_TICK + 1                  ; kp_init kirjoittaa bittikartan $a000-:aan taulu 2e:n päälle, muuten demo
        lda #>R_TICK_RTS                ; jäisi jumiin; edellisen latausvälin R_TICK pois)
        sta R_TICK + 2
        jmp R_IRQ_ON
_m0
          .endif
        lda #0
        sta $d015
        rts
+
        .endif
        lsr
        eor #3                          ; 3, 3, 2, 2, 1, 1, 0, 0
        tax
        lda taulu_ramp,x
        jsr _kaikki
        lda #0
        sta $d015
        rts
_ei_loppu
        ; ---------------------------------------------------------------- kehys valottuu
        lda tz_t
        cmp #8
        bcs _teksti
        lsr
        clc
        adc #1
        tax
        lda taulu_ramp,x
        ldx #TAULU_NK - 1
        jsr _kehys_v
        ; ---------------------------------------------------------------- teksti
_teksti
-       ldx tz_lo                       ; täysin valottuneet: lo eteenpäin
        cpx #TAULU_NT
        beq _valke
        lda taulu_t_f,x
        clc
        adc #TAULU_NOUSU
        bcs _act
        cmp tz_t
        beq +
        bcs _act
+       ldy tz_lvl                      ; f + NOUSU <= T: täysi (välkkeen) taso
        lda _taso,y
        pha
        ldy taulu_t_hi,x
        lda taulu_t_lo,x
        tax
        pla
        jsr taulu_set
        inc tz_lo
        jmp -
_act    ldx tz_lo                       ; valottuvat solut: väri (T - f) / 2
-       cpx #TAULU_NT
        beq _valke
        lda tz_t
        sec
        sbc taulu_t_f,x
        bcc _valke                      ; alkaa myöhemmin (taulukko alkukehyksen mukaan)
        lsr
        tay
        lda taulu_ramp+1,y
        stx _sx+1
        pha
        ldy taulu_t_hi,x
        lda taulu_t_lo,x
        tax
        pla
        jsr taulu_set
_sx     ldx #0
        inx
        jmp -
        ; ---------------------------------------------------------------- välke
_valke  lda tz_flk
        beq +
        dec tz_flk
        bne _naarmu
        lda #0                          ; välke päättyy: takaisin valkoiseksi
        jmp _taso_v
+       jsr taulu_rnd
        cmp #20                         ; noin 1/13 kehyksistä
        bcs _naarmu
        and #1
        clc
        adc #1
        sta tz_flk
        lda #1
_taso_v sta tz_lvl
        lda tz_t
        cmp #8
        bcc _naarmu                     ; kehys valottuu vielä
        ldy tz_lvl
        lda _taso,y
        ldx #TAULU_NK - 1
        jsr _kehys_v
        ldy tz_lvl
        lda _taso,y
        jsr _valmiit
        ; ---------------------------------------------------------------- naarmu ja pöly
_naarmu lda tz_sl
        bne _elaa
        jsr taulu_rnd
        cmp #8                          ; uusi naarmu noin 1/32 kehyksistä
        bcs _poly
        jsr taulu_rnd
        and #31
        clc
        adc #12
        sta tz_sl
        jsr taulu_rnd
        and #$7f
        clc
        adc #60
        sta tz_sx
        jsr taulu_rnd
        and #2
        sec
        sbc #1                          ; +1 tai $ff
        sta tz_sd
_elaa   dec tz_sl
        lda tz_t
        and #3
        bne +
        lda tz_sx
        clc
        adc tz_sd
        sta tz_sx
+       ldx #0
        ldy #50
-       lda tz_sx
        sta $d000,x
        tya
        sta $d001,x
        clc
        adc #42
        tay
        inx
        inx
        cpx #8
        bne -
        lda #%00001111
        ldx tz_sl
        bne +
        lda #0
+       sta _spr_on+1
        jmp _poly2
_poly   lda #0
        sta _spr_on+1
_poly2  ldx #0                          ; pöly: spritet 4-6, kukin noin 1/4 kehyksistä
_pl     jsr taulu_rnd
        cmp #64
        bcs _pois
        jsr taulu_rnd
        txa
        asl
        tay
        lda tz_rnd
        sta $d008,y
        jsr taulu_rnd
        and #$7f
        clc
        adc #60
        sta $d009,y
        lda _bit,x
        ora _spr_on+1
        sta _spr_on+1
_pois   inx
        cpx #3
        bne _pl
_spr_on lda #0
        sta $d015
        lda #0
        sta $d010
        rts

_bit    .byte %00010000, %00100000, %01000000
_taso   .byte $10 >> TAULU_TV, $f0 >> TAULU_TV    ; välkkeen tasot: valkoinen, vaaleanharmaa

; _kehys_v: A = väri kehyksen soluihin (X = TAULU_NK - 1). Solu suoraan ruutuun ilman taulu_setiä: 31 sykliä
; solulta, joten välke ja häivytys (kaikki kehyksen ja tekstin solut) mahtuvat kehykseen (taulu_setillä noin 70
; sykliä, jolloin taulu1:n 373 solua veisi yli kehyksen ja IRQ jäisi väliin)
_kehys_v
        sta _kv+1
        ldy #0
-       lda taulu_k_lo,x
        sta tz_p
        lda taulu_k_hi,x
        ora #>TAULU_COL
        sta tz_p+1
_kv     lda #0
        sta (tz_p),y
        dex
        cpx #$ff
        bne -
        rts

; _valmiit: A = väri täysin valottuneisiin tekstin soluihin (0 .. tz_lo - 1)
_valmiit
        ldx tz_lo
        beq +
        sta _vv+1
        ldy #0
-       dex
        lda taulu_t_lo,x
        sta tz_p
        lda taulu_t_hi,x
        ora #>TAULU_COL
        sta tz_p+1
_vv     lda #0
        sta (tz_p),y
        txa
        bne -
+       rts

; _kaikki: A = väri kaikkiin kehyksen ja tekstin soluihin (häivytys)
_kaikki
        pha
        ldx #TAULU_NK - 1
        jsr _kehys_v
        lda #TAULU_NT
        sta tz_lo
        pla
        jmp _valmiit

        .if TAULU_JALKI
tz_jalki .byte 0                ; 1 = taulu_kehys tekee vain naarmun ja pölyn (taulu_jalki)
        .endif
