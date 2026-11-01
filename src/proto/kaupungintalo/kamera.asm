; Kamera-ajo patsaalta ikkunan läpi huoneeseen, osan kehykset 0 - KAM_LOPPU-1.
; Geometria, s kehyksittäin ja lohkolista kamera.py:ssä (host laskee vain taulut).
;
; Ruutu: MC-bittikartta pankissa 3 (KAM_BITMAP, KAM_SCREEN), alussa ulkonäkymä (aukio.kla, KT6). Kamera peruuttaa
; ikkunan tasosta huoneeseen; kehyksen s (S0 -> S_LOPPU, kamera.py) mukaan ikkunan taso liikkuu yhtenä kappaleena:
;   - ikkunan kehys on spritejä: oikea karmi ch1, välikarmi ch2 (leveänä ch2-4) ja ikkunalauta ch7- (vaakapalkki;
;     vasen karmi ja ylälista jäävät ruudun ulkopuolelle). Pystypalkit ovat Y-laajennettuja 42 rivin kopioita, joiden
;     ruudukko päättyy palkin alapäähän; kam_mux siirtää kopiot alas MUX_DY rivin välein. Palkkien lohkot tekee kam_gen
;     alustuksessa RAMiin KAM_BLK0- ($d000-$dfff, I/O:n alla; VIC-pankki 3 näkee sen): joka kehys lasketaan vain
;     reunat ja valitaan lohko leveyden mukaan (kam_vbar, kam_hbar). Kaksi kopiolistaa: toista näytetään, toista
;     lasketaan.
;   - ulkonäkymän solut vaihtuvat seinäksi (kam_cell) siinä järjestyksessä kuin skaalattu ikkuna väistyy niiden
;     päältä (kam_rev_*, enintään KAM_REV_MAX pystytahdin aikana), palkki peittää rajan.
;   - johtaja, PC ja pöytä ovat kameran takana: niitä ei ole kamera-ajon kuvassa (kamera.py).
; Kehyksessä KAM_LOPPU leikkaus huoneeseen (s = 1): VIC vaihtaa pankkiin 1 ja spritet pois (kam_vaihto), ja PC:n
; kuvaruutu vierii huoneessa KAM_PC_Z0 riviä perille (huone_frame alkaa kam_vaihdosta).
;
; IRQ: kam_irq rivillä KAM_LINE: FRAME_HOOK, valmiin listan rekisterit, cli ja seuraavan kehyksen laskenta
; (multipleksaus saa keskeyttää; jos laskenta on vielä kesken, kehys näyttää edellisen listan). kam_mux riveillä
; MUX0 + k * MUX_DY. IRQ-tason koodi käyttää omia apumuuttujiaan (ka_*), laskenta kam_*/kv_*.

KAM_BITMAP = $e000
KAM_SCREEN = $c400
KAM_VSRC = $c800                ; ulkonäkymän värit: kam_go kopioi $d800:aan
KAM_D018 = ((KAM_SCREEN & $3fff) >> 6) | ((KAM_BITMAP & $3fff) >> 10)
KAM_LINE = 250
KAM_OFS = 1                     ; näytettävä kehys = DFRAME + KAM_OFS rivillä KAM_LINE
MUX0 = 30
MUX_DY = 36                      ; kopiot 42 rivin välein: jokaiselle kopiolle vaihtorivi alun jälkeen ja >= 6 riviä ennen seuraavaa
MUX_N = 6                       ; rivit 30 ... 210 (viimeisen kopion alku <= 51 + KAM_YE_MAX - 42)
KAM_REV_MAX = 16                ; paljastettavia soluja ennen laskentaa enintään (pystytahdin aikana, näkyvät ajallaan;
                                ; loput kam_more:ssa ja seuraavissa): seinän paljastus vie kehyksessä enintään 17 solua
KAM_REV_END = 232               ; kam_more lopettaa tällä rivillä

; kam_go (kt_go): kooste näkyviin (ulkonäkymä), spritet ja kam_irq. Ensimmäinen IRQ laskee ensimmäisen listan.
kam_go
        ldx #<KAM_VSRC
        ldy #>KAM_VSRC
        jsr vcol
        lda #0                          ; VIC-pankki 3 ($c000-$ffff)
        sta $dd00
        lda #KAM_D018
        sta $d018
        lda #$ff
        sta $d01c
        lda #0
        sta $d01b
        lda #KAM_D025
        sta $d025
        lda #KAM_D026
        sta $d026
        ldx #7
        lda #KAM_OMA
-       sta $d027,x
        dex
        bpl -
        lda #<kam_irq
        sta $fffe
        lda #>kam_irq
        sta $ffff
        lda #KAM_LINE
        sta $d012
        rts

; ---------------------------------------------------------------- IRQ
kam_irq
        pha
        txa
        pha
        tya
        pha
        asl $d019
        jsr FRAME_HOOK
        clc
        lda DFRAME
        adc #<KAM_OFS
        sta kam_n
        lda DFRAME+1
        adc #>KAM_OFS
        sta kam_n+1
        cmp #>KAM_LOPPU                 ; huoneeseen kehyksessä KAM_LOPPU
        bcc +
        bne _vaihto
        lda kam_n
        cmp #<KAM_LOPPU
        bcc +
_vaihto jmp kam_vaihto
+       lda kam_ready                   ; valmis puskuri tälle kehykselle? muuten edellinen uudelleen
        cmp kam_n
        bne +
        lda kam_ready+1
        cmp kam_n+1
        bne +
        lda kam_n
        and #1
        sta kam_db
+       jsr kam_apply
        lda #0
        sta kam_ml
        lda #<kam_mux
        sta $fffe
        lda #>kam_mux
        sta $ffff
        .if KAM_TA
        lda kam_top                     ; vaihtoehto: yläreunan tila ja puskurin lista
        sta $d011
        lda kam_il
        .else
        lda #MUX0
        .endif
        sta $d012
        lda kam_busy                    ; edellinen laskenta kesken: vain musiikki ja rekisterit
        bne _out
        inc kam_busy
        cli
        jsr kam_reveal
        clc
        lda kam_n
        adc #1
        sta kam_c
        lda kam_n+1
        adc #0
        sta kam_c+1
        jsr kam_compute
        jsr kam_more
        sei
        dec kam_busy
_out    pla
        tay
        pla
        tax
        pla
        rti

kam_mux
        pha
        txa
        pha
        tya
        pha
        asl $d019
        .if KAM_TA
        ldx kam_ml                      ; vaihtoehto: $d011:n vaihto rivillä kam_iw
        lda kam_iw,x
        beq +
-       lda $d012
        cmp kam_iw,x
        bcc -
        lda kam_iv,x
        sta $d011
+
        .endif
        .for ch = 0, ch < 8, ch += 1
        ldy kam_idx+ch
        cpy kam_end+ch
        bcs +
        lda kb_e,y                      ; vaihtorivi: pystypalkin kopio alkanut, muu piirretty
        cmp $d012
        bcs +
        iny
        sty kam_idx+ch
        lda kb_y,y
        sta $d001+2*ch
        lda kb_x,y
        sta $d000+2*ch
        lda kb_p,y
        sta KAM_SCREEN+$3f8+ch
+
        .next
        inc kam_ml
        ldx kam_ml
        .if KAM_TA
        cpx kam_in
        bcs _last
        lda kam_il,x
        .else
        cpx #MUX_N
        bcs _last
        lda mux_line,x
        .endif
        sta $d012
        jmp _out
_last   lda #<kam_irq
        sta $fffe
        lda #>kam_irq
        sta $ffff
        lda #KAM_LINE
        sta $d012
_out    pla
        tay
        pla
        tax
        pla
        rti

; kam_more: laskennan jälkeen lisää jonossa olevia soluja, kunnes säde on rivillä KAM_REV_END (seuraava kam_irq
; ei saa jäädä odottamaan)
kam_more
        lda $d011
        bmi +
        lda $d012
        cmp #KAM_REV_END
        bcs _x
+       lda #1
        jsr kam_reveal_a
        lda kam_bud
        beq kam_more
_x      rts

; kam_reveal: kehysten kam_rf ... kam_n solut (kam_rev_n[kehys] kpl), enintään KAM_REV_MAX (kam_reveal_a: A) tällä
; kertaa; kam_bud = jäljelle jäänyt määrä
kam_reveal
        lda #KAM_REV_MAX
kam_reveal_a
        sta kam_bud
_loop   lda kam_rleft
        bne _cell
        lda kam_rf+1                    ; seuraava kehys, jos kam_rf <= kam_n
        cmp kam_n+1
        bcc +
        bne _done
        lda kam_rf
        cmp kam_n
        beq +
        bcs _done
+       clc
        lda #<kam_rev_n
        adc kam_rf
        sta kam_t0
        lda #>kam_rev_n
        adc kam_rf+1
        sta kam_t0+1
        ldy #0
        lda (kam_t0),y
        sta kam_rleft
        inc kam_rf
        bne _loop
        inc kam_rf+1
        jmp _loop
_cell   jsr kam_cell
        dec kam_rleft
        dec kam_bud
        bne _loop
_done   rts


; ---------------------------------------------------------------- seuraavan kehyksen puskuri
; kam_compute: kehys kam_c puskuriin kam_c & 1: s taulusta, palkkien reunat, lohkot ja kopiolistat
kam_compute
-       lda kam_sfr                     ; s (8.8) kehykselle kam_c: juokseva arvo, askeleet kam_ds (kehykset kasvavat)
        cmp kam_c
        lda kam_sfr+1
        sbc kam_c+1
        bcs _sok
        inc kam_sfr
        bne _sd
        inc kam_sfr+1
_sd     clc
        lda #<kam_ds
        adc kam_sfr
        sta kam_t0
        lda #>kam_ds
        adc kam_sfr+1
        sta kam_t0+1
        ldy #0
        sec
        lda kam_sf
        sbc (kam_t0),y
        sta kam_sf
        bcs -
        dec kam_si
        jmp -
_sok
        ; monikerrat: kam_b*[j] = 1/2 + j * s (j = 0..15), kam_a*[a] = a * 16 * s (a = 0..7), 24 b (murto, ala, ylä)
        lda #$80
        sta kam_bf
        lda #0
        sta kam_bl
        sta kam_bh
        sta kam_af
        sta kam_al
        sta kam_ah
        tax
-       clc
        lda kam_bf,x
        adc kam_sf
        sta kam_bf+1,x
        lda kam_bl,x
        adc kam_si
        sta kam_bl+1,x
        lda kam_bh,x
        adc #0
        sta kam_bh+1,x
        inx
        cpx #15
        bne -
        sec                             ; 16 s = 15 s + s (ilman puolikasta)
        lda kam_bf+15
        sbc #$80
        sta kam_af+1
        lda kam_bl+15
        sbc #0
        sta kam_al+1
        lda kam_bh+15
        sbc #0
        sta kam_ah+1
        clc
        lda kam_af+1
        adc kam_sf
        sta kam_af+1
        lda kam_al+1
        adc kam_si
        sta kam_al+1
        lda kam_ah+1
        adc #0
        sta kam_ah+1
        ldx #1
-       clc
        lda kam_af,x
        adc kam_af+1
        sta kam_af+1,x
        lda kam_al,x
        adc kam_al+1
        sta kam_al+1,x
        lda kam_ah,x
        adc kam_ah+1
        sta kam_ah+1,x
        inx
        cpx #7
        bne -
        ; puskuri tyhjäksi
        lda kam_c
        and #1
        sta kam_b
        tax
        lda #0
        sta kb_d010,x
        sta kb_d01d,x
        sta kb_d017,x
        txa
        asl a
        asl a
        asl a
        tax
        lda #0
        ldy #7
-       sta kb_cnt,x
        inx
        dey
        bpl -
        .if KAM_TA
        jsr kam_ra                      ; vaihtoehdon alkuvaihe: maskit ja lista, ei palkkeja
        bcc +
        jmp _d015
+
        .endif
        ; pystypalkit (ohitetaan, kun s on niin suuri, ettei palkki osu ruudulle)
        lda #0
-       sta kam_pvo
        jsr kam_vbar
        lda kam_pvo
        clc
        adc #PV
        cmp #KAM_NPV * PV
        bne -
        ; vaakapalkit ylhäältä alas (kanavan kopiot Y-järjestyksessä)
        lda #0
-       sta kam_pvo
        jsr kam_hbar
        lda kam_pvo
        clc
        adc #HV
        cmp #KAM_NHV * HV
        bne -
_d015   ; $d015: kanavat, joilla on kopioita (8 kiertoa: kanava 0 päätyy bittiin 0)
        lda kam_b
        asl a
        asl a
        asl a
        tax
        lda #0
        sta kam_t1
        ldy #7
-       lda kb_cnt,x
        cmp #1
        ror kam_t1
        inx
        dey
        bpl -
        lda kam_t1
        ldx kam_b
        sta kb_d015,x
        lda kam_c
        sta kam_ready
        lda kam_c+1
        sta kam_ready+1
        rts

; pystypalkkien tietueet kam_pv (kamera.py): s-raja, ensimmäinen reuna, lohkon siirto tiloille u/x/w, tasainen
; lohko, kanavajonon alku. Vaakapalkkien kam_hv: s-raja, ensimmäinen reuna, lohkon siirto tiloille t/y, kanavajonon
; alku.
PV_S = 0
PV_E = 1
PV_U = 2
PV_X = 3
PV_W = 4
PV_T = 5
PV_CS = 6
PV = 7
HV_S = 0
HV_E = 1
HV_T = 2
HV_Y = 3
HV_CS = 4
HV = 5

; kam_vbar: pystypalkki kam_pv[kam_pvo] ruudun yläreunan yli riville kv_ye; kv_x0..kv_x1 hires-px ruudun vasemmasta
; reunasta. Leveys W <= 24: MC-sprite, kuvio N = W / 2 pikseliin; W <= 48: X-laajennettu, N = W / 4; leveämpi:
; alkupää (raidat round(s / 2) pikseliä) ja tasaiset X-laajennetut limittäin oikeaan reunaan (tai ruudun reunaan).
kam_vbar
        ldx kam_pvo
        lda kam_si
        cmp kam_pv+PV_S,x
        bcc +
        rts
+       lda kam_pv+PV_E,x
        pha
        tax
        ldy #3
        jsr kam_edges
        pla
        tax
        jsr kv_set
        ldx kam_pvo
        lda kv_x1+1                     ; näkyy: x1 > 0, x0 < 320, ye > 0
        bmi _off
        ora kv_x1
        beq _off
        lda kv_ye+1
        bmi _off
        ora kv_ye
        beq _off
        lda kv_x0+1
        bmi _vis
        cmp #>320
        bcc _vis
        bne _off
        lda kv_x0
        cmp #<320
        bcc _vis
_off    rts
_vis    lda kam_pv+PV_CS,x
        jsr kam_ch0
        lda #1
        sta kv_yx
        sta kv_vert
        lda kv_x0
        sta kv_xs
        lda kv_x0+1
        sta kv_xs+1
        sec                             ; W = x1 - x0
        lda kv_x1
        sbc kv_x0
        tay
        lda kv_x1+1
        sbc kv_x0+1
        bne _wide
        tya
        cmp #49
        bcs _wide
        cmp #25
        bcs _xexp
        adc #1                          ; C = 0: N = (W + 1) / 2
        lsr a
        clc
        adc kam_pv+PV_U,x
        ldy #0
        beq _one
_xexp   adc #1                          ; C = 1: N = (W + 2) / 4
        lsr a
        lsr a
        clc
        adc kam_pv+PV_X,x
        ldy #1
_one    sta kv_blk
        sty kv_xx
        clc                             ; yksi sprite: loppu = alku + 1
        lda kv_xs
        adc #1
        sta kv_xe
        lda kv_xs+1
        adc #0
        sta kv_xe+1
        lda #24
        sta kv_pw
        jmp kam_row
_wide   lda kam_si                     ; alkupää: raidat (int(s) + 1) / 2 pikseliä
        clc
        adc #1
        lsr a
        clc
        adc kam_pv+PV_W,x
        sta kv_blk
        lda kam_pv+PV_T,x
        sta kv_blk2
        lda #1
        sta kv_xx
        lda #48
        sta kv_pw
        jsr kv_xe344                    ; loppu = min(x1, 344)
        jmp kam_row

; kam_odota: A = solun bittikarttaosoitteen ylätavu - KAM_BITMAP (H8, rivi r: H8 ~ 1,25 r). Odottaa, kunnes säde ei
; ole solun riveillä 51 + 8 r - 5 ... 51 + 8 r + 7 (kopio kestää noin 4 riviä): v = (L - 46) / 8, vaarallinen, kun
; 0 <= v + v / 4 - H8 + 1 <= 3 (tarkistettu kaikille soluille ja riveille). Riveillä < 46 ja >= 240 ei odoteta
; (rivi 24 voi revetä, jos kam_more kopioi sen rivillä 240-250).
; X, Y säilyvät.
kam_odota
        sta kam_t6
-       lda $d011
        bmi _x
        lda $d012
        cmp #240                        ; kam_more loppuu rivillä KAM_REV_END: ei odotusta kam_irq:n (250) yli
        bcs _x
        sbc #46 - 1                     ; C = 0
        bcc _x
        lsr a
        lsr a
        lsr a
        sta kam_t3
        lsr a
        lsr a
        clc
        adc kam_t3
        sec
        sbc kam_t6
        clc
        adc #1
        cmp #4
        bcc -
_x      rts

; kam_ch0: A = kanavajonon kohta: kv_ci ja kv_k = kam_chs[kv_ci]
kam_ch0
        sta kv_ci
        tay
        lda kam_chs,y
        sta kv_k
        rts

; kam_hbar: vaakapalkki kam_hv[kam_pvo]: kv_y0..kv_y1, kv_x0..kv_x1. Rivikuvio T = y1 - y0 riviin (T > 20:
; Y-laajennettu T / 2), X-laajennetut limittäin ruudulla näkyvälle osalle; kapea (6-47) on yksi sprite oikean reunan
; mukaan (kamera.py vaaka_valit).
kam_hbar
        ldx kam_pvo
        lda kam_si
        cmp kam_hv+HV_S,x
        bcc +
        rts
+       lda kam_hv+HV_E,x
        pha
        tax
        ldy #4
        jsr kam_edges
        pla
        tax
        jsr kv_set
        ldx kam_pvo
        lda kv_y1+1                     ; näkyy: y1 > 0, y0 < 200, x1 > 0
        bmi _off
        ora kv_y1
        beq _off
        lda kv_x1+1
        bmi _off
        ora kv_x1
        beq _off
        lda kv_y0+1
        bmi _vis
        bne _off
        lda kv_y0
        cmp #200
        bcc _vis
_off    rts
_vis    lda kam_hv+HV_CS,x
        jsr kam_ch0
        lda #0
        sta kv_vert
        sta kv_yx
        lda #1
        sta kv_xx
        lda #48
        sta kv_pw
        lda kv_y0                       ; Y-rekisteri 51 + y0 (y0 >= -51, kamera.py)
        clc
        adc #51
        sta kv_hy
        clc                             ; vaihtorivi min(51 + y1, 255)
        lda kv_y1
        adc #51
        sta kv_he
        lda kv_y1+1
        adc #0
        beq +
        lda #255
        sta kv_he
+
        sec                             ; T = y1 - y0
        lda kv_y1
        sbc kv_y0
        tay
        lda kv_y1+1
        sbc kv_y0+1
        bne _ty
        tya
        cmp #21
        bcs _ty
        adc kam_hv+HV_T,x               ; C = 0
        jmp _blk
_ty     tya                             ; T / 2 pyöristettynä, Y-laajennettu
        clc
        adc #1
        lsr a
        clc
        adc kam_hv+HV_Y,x
        inc kv_yx
_blk    sta kv_blk
        sta kv_blk2
        lda kv_x0+1                     ; alku = max(x0, 0), loppu = min(x1, 344)
        bpl +
        lda #0
        sta kv_x0
        sta kv_x0+1
+       lda kv_x0
        sta kv_xs
        lda kv_x0+1
        sta kv_xs+1
        jsr kv_xe344
        jsr kam_hkapea                  ; kapea: yksi sprite oikean reunan mukaan
        bcs _done
        jmp kam_row
_done   rts

; kam_row: spritet välille kv_xs..kv_xe: kv_xs + pw * i ja viimeinen kv_xe - pw (limittäin), ensimmäinen lohko
; kv_blk, muut kv_blk2; kanavat kanavajonosta kv_ci:stä alkaen
kam_row
        lda kv_xs
        sta kv_px
        lda kv_xs+1
        sta kv_px+1
        lda kv_blk
        sta kv_cur
_l      sec                             ; jäljellä = xe - px
        lda kv_xe
        sbc kv_px
        tax
        lda kv_xe+1
        sbc kv_px+1
        bmi _last
        bne _mid
        cpx kv_pw
        bcc _last
        beq _last
_mid    lda kv_cur
        jsr kam_emit
        jsr kam_nch
        lda kv_blk2
        sta kv_cur
        clc
        lda kv_px
        adc kv_pw
        sta kv_px
        bcc _l
        inc kv_px+1
        jmp _l
_last   lda kv_px                       ; viimeinen oikean reunan mukaan (ei, jos ainoa)
        cmp kv_xs
        bne +
        lda kv_px+1
        cmp kv_xs+1
        beq _e
+       sec
        lda kv_xe
        sbc kv_pw
        sta kv_px
        lda kv_xe+1
        sbc #0
        sta kv_px+1
_e      lda kv_cur
        jsr kam_emit
        ; jatkuu kam_nch:iin

; kam_nch: seuraava kanava kanavajonosta
kam_nch
        inc kv_ci
        ldy kv_ci
        lda kam_chs,y
        sta kv_k
        rts

; kam_emit: A = lohko (osoitin), sprite kanavalle kv_k kohtaan kv_px (hires-px ruudun vasemmasta reunasta):
; X-laajennus kv_xx, Y-laajennus kv_yx; pystypalkki (kv_vert): kopiot palkin alapäähän kv_ye asti, muuten yksi
; kopio riville kv_hy
kam_emit
        sta kam_t1
        jsr kam_list                    ; Y = listan kohta, kam_t2 = kb_cnt-indeksi
        clc
        lda kv_px
        adc #24
        sta kam_t5
        lda kv_px+1
        adc #0
        beq +
        ldx kv_k                        ; X:n yläbitti
        lda kam_bit,x
        ldx kam_b
        ora kb_d010,x
        sta kb_d010,x
+       ldx kv_k
        lda kam_bit,x
        sta kam_t6
        ldx kam_b
        lda kv_xx
        beq +
        lda kam_t6
        ora kb_d01d,x
        sta kb_d01d,x
+       lda kv_yx
        beq +
        lda kam_t6
        ora kb_d017,x
        sta kb_d017,x
+       lda kv_vert
        bne _v
        lda kv_he
        sta kb_e,y
        lda kv_hy
        sta kb_y,y
        lda kam_t5
        sta kb_x,y
        lda kam_t1
        sta kb_p,y
        ldx kam_t2
        inc kb_cnt,x
        rts
_v      ; Y-kopiot: viimeinen = 51 + min(ye, YE_MAX) - 42, ensimmäinen >= 9
        lda kv_ye+1
        bne _ym
        lda kv_ye
        cmp #KAM_YE_MAX
        bcc +
_ym     lda #KAM_YE_MAX
+       clc
        adc #51 - 42
        sta kam_t3                      ; viimeinen
-       cmp #9 + 42
        bcc +
        sbc #42
        jmp -
+       ldx #0
-       sta kb_y,y
        sta kb_e,y
        pha
        lda kam_t5
        sta kb_x,y
        lda kam_t1
        sta kb_p,y
        pla
        inx
        iny
        cmp kam_t3
        bcs +
        adc #42
        jmp -
+       txa
        ldx kam_t2
        sta kb_cnt,x
        rts

; kam_edges: X = ensimmäinen reuna, Y = määrä
kam_edges
        sty kam_t3
-       jsr kam_edge
        inx
        dec kam_t3
        bne -
        rts

; kv_set: X = ensimmäinen reuna: kv_x0, kv_x1, kv_ye (pysty) tai kv_x0, kv_x1, kv_y0, kv_y1 (vaaka)
kv_set
        .for i = 0, i < 4, i += 1
        lda kam_e_lo+i,x
        sta kv_x0+2*i
        lda kam_e_hi+i,x
        sta kv_x0+2*i+1
        .next
        rts

; kam_edge: X = reuna: kam_e[X] = (kam_eb[X] < 0 ? 0 : kam_e[kam_eb[X]]) + kam_ech:ec[X] +- round(k * s), k = 16 *
; kam_eka[X] + kam_ekb[X] (monikertataulut kam_compute:ssa), etumerkillinen 16 b. X säilyy.
kam_edge
        ldy kam_eka,x                   ; r = a * 16 * s + 1/2 + b * s, kokonaisosa (pyöristetty)
        lda kam_af,y
        sta kam_r0
        lda kam_al,y
        sta kam_r1
        lda kam_ah,y
        sta kam_r2
        ldy kam_ekb,x
        clc
        lda kam_bf,y
        adc kam_r0
        lda kam_bl,y
        adc kam_r1
        sta kam_r1
        lda kam_bh,y
        adc kam_r2
        sta kam_r2
        ldy kam_eb,x                    ; pohja: vakio (+ toinen reuna)
        bmi _c
        clc
        lda kam_e_lo,y
        adc kam_ec,x
        sta kam_t5
        lda kam_e_hi,y
        adc kam_ech,x
        jmp _b
_c      lda kam_ec,x
        sta kam_t5
        lda kam_ech,x
_b      sta kam_t5+1
        lda kam_es,x
        bne _neg
        clc
        lda kam_t5
        adc kam_r1
        sta kam_e_lo,x
        lda kam_t5+1
        adc kam_r2
        sta kam_e_hi,x
        rts
_neg    sec
        lda kam_t5
        sbc kam_r1
        sta kam_e_lo,x
        lda kam_t5+1
        sbc kam_r2
        sta kam_e_hi,x
        rts

; kam_list: kanava kv_k puskurissa kam_b: Y = kopiolistan seuraava kohta (b * 48 + k * 6 + cnt), kam_t2 = kb_cnt-indeksi
kam_list
        lda kam_b
        asl a
        asl a
        asl a
        clc
        adc kv_k
        sta kam_t2
        tax
        lda kam_b
        beq +
        lda #48
+       sta kam_t3
        lda kv_k
        asl a
        adc kv_k
        asl a
        adc kam_t3
        adc kb_cnt,x
        tay
        rts

kam_bit .byte 1, 2, 4, 8, 16, 32, 64, 128

; kam_gen (kam_init): palkkien lohkot RAMiin KAM_BLK0- (I/O pois kirjoituksen ajaksi): pystypalkkien KAM_NV lohkoa
; (rivi 3 tavua, 21 kertaa), sitten vaakapalkkien KAM_NH lohkoa (rivikuvio T riviin, kukin rivi 3 tavua)
kam_gen
        php                             ; ei sei:tä: koko demossa rungon IRQ soittaa musiikin generoinnin (noin 3,8
        lda $01                         ; kehystä) aikana ja asettaa $01 = $35 itse (sei:llä biisi hyppäisi 2 kehystä)
        pha
        lda #<KAM_BLK0
        sta kam_t4
        lda #>KAM_BLK0
        sta kam_t4+1
        lda #<kam_gv
        sta kam_t0
        lda #>kam_gv
        sta kam_t0+1
        lda #$34
        sta $01
        ldx #KAM_NV
_v      ldy #2
-       lda (kam_t0),y
        sta kb0,y
        dey
        bpl -
        ldy #62
-       lda kb2
        sta (kam_t4),y
        dey
        lda kb1
        sta (kam_t4),y
        dey
        lda kb0
        sta (kam_t4),y
        dey
        bpl -
        clc
        lda kam_t0
        adc #3
        sta kam_t0
        bcc +
        inc kam_t0+1
+       jsr _next
        dex
        bne _v
        lda #<kam_gh                    ; vaakapalkit: (kuvion kohta, kuvion rivit h0, T): rivi r < T = kuvio[r * h0 / T]
        sta kam_t0
        lda #>kam_gh
        sta kam_t0+1
        lda #KAM_NH
        sta kam_t6
_h      ldy #0
        lda (kam_t0),y
        sta kam_t1                      ; kuvion kohta
        iny
        lda (kam_t0),y
        sta kam_r0                      ; h0
        iny
        lda (kam_t0),y
        sta kam_r1                      ; T
        lda #0
        sta kam_r2                      ; r * h0 mod T
        sta kam_t3                      ; r
        tay
_r      lda #0
        ldx kam_t3
        cpx kam_r1
        bcs +
        ldx kam_t1
        lda kam_ghk,x
+       sta (kam_t4),y
        iny
        sta (kam_t4),y
        iny
        sta (kam_t4),y
        iny
        clc
        lda kam_r2
        adc kam_r0
-       cmp kam_r1
        bcc +
        sbc kam_r1
        inc kam_t1
        bcs -
+       sta kam_r2
        inc kam_t3
        cpy #63
        bne _r
        clc
        lda kam_t0
        adc #3
        sta kam_t0
        bcc +
        inc kam_t0+1
+       jsr _next
        dec kam_t6
        bne _h
        pla
        sta $01
        plp
        rts
_next   clc
        lda kam_t4
        adc #64
        sta kam_t4
        bcc +
        inc kam_t4+1
+       rts

; ---------------------------------------------------------------- rutiinit ja taulut vapaisiin koloihin (kt.asm)
        .section kam_etu1
        .include "kamera_gen.asm"       ; lohkolista ja kanavajonot (KT1:n taulualueella, koodialue täynnä)
        .send

        .section kam_etu2
; kam_hkapea: C = 1, jos väli [kv_xs, kv_xe) on alle 6 tai kapea ja kv_xe < 24 (ei mitään); kapea (6-47):
; kv_xs = kv_xe - 48 (yksi sprite oikean reunan mukaan)
kam_hkapea
        jsr kv_w
        beq _no
        cmp #2
        beq _ok
        lda kv_xe+1
        bne +
        lda kv_xe
        cmp #24
        bcc _no
+       sec
        lda kv_xe
        sbc #48
        sta kv_xs
        lda kv_xe+1
        sbc #0
        sta kv_xs+1
_ok     clc
        rts
_no     sec
        rts
        .send


        .section kam_etu3
; kv_w: W = kv_xe - kv_xs: A = 0 (Z), jos W < 6; A = 1, jos 6 <= W < 48 (kapea: yksi sprite); A = 2, jos W >= 48
kv_w
        sec
        lda kv_xe
        sbc kv_xs
        tay
        lda kv_xe+1
        sbc kv_xs+1
        bmi _no
        bne _w
        cpy #48
        bcs _w
        cpy #6
        bcc _no
        lda #1
        rts
_no     lda #0
        rts
_w      lda #2
        rts
        .send

        .section kam_etu3
; kv_xe344: kv_xe = min(kv_x1, 344)
kv_xe344
        lda kv_x1+1
        cmp #>344
        bcc +
        bne _c
        lda kv_x1
        cmp #<344
        bcc +
_c      lda #<344
        sta kv_x1
        lda #>344
        sta kv_x1+1
+       lda kv_x1
        sta kv_xe
        lda kv_x1+1
        sta kv_xe+1
        rts
        .send
