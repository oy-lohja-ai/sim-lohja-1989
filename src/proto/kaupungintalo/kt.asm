; Kaupungintalo (partti ennen Hillneriä): kaupunginjohtaja pelaa IBM PC:llä, leikkaus peliin, Hillnerille
; lähetetään purkaja. Kahtena osalevynä (KT_IKKUNA build.py:n VARIANTista): kaupungintalo-ikkuna = kamera-ajo ja
; huone (kehykset 0 - HUONE_LOPPU-1), kaupungintalo = näytön lähikuva (0 - NAYTTO_LOPPU-1) ja peli.
; Data: tools/gfx/data/kaupungintalo/, generoitu koodi ja taulut build.py -> OUT/.
;
; Runko: kt_init (pääsäie, kuva ennallaan), kt_go (VIC, värimuisti ja oma IRQ, palaa heti).
; IRQ rivillä 250 kerran kehyksessä: FRAME_HOOK (musiikki, DFRAME), sitten vaiheen liike:
;
; Huone (kaupungintalo-ikkuna, kamera-ajon jälkeen HUONE_LOPPU-1 asti, VIC-pankki 1):
;   - pienoisruutu: joka RUUTU_ASKEL. kehys PC:n kuvaruutuun piirretään kartan nauha Y-siirrolla
;     (huone_nauhat.asm, huone_piirto.asm), kartta vierii kohti kaupungintaloa (Y HUONE_MAX -> 0)
;   - kädet: tapahtumataulun (kad_*) kehyksessä kopioidaan käden tila (solut) bittikarttaan (kadet.asm,
;     kadet_copy.asm); ei pään kopion eikä vierityksen kehyksissä
;   - pää: tapahtumataulun (ev_*) kehyksessä kopioidaan asento bittikarttaan (paat.asm). Huoneen IRQ on rivillä
;     HUONE_LINE pään rivien jälkeen, joten kopio (bittikartta, ruutu ja värit) on valmis ennen kuin säde palaa
;     päähän. Tapahtumat eivät osu vierityksen kehyksiin.
; Näytön lähikuva (kaupungintalo, 0 - NAYTTO_LOPPU-1, VIC-pankki 2): kuvaruudulla pelin oma ruutu 1:1 oikealla
;   paikallaan, kaupunginjohtajakursori (spritet 0-1) kulkee Katastrofit-valikolle. Viimeiset PALJASTUS kehystä
;   kuvaruutu laajenee koko ruuduksi: solut pelin bittikartasta (KT3) host-järjestyksessä, ja kehyksessä
;   NAYTTO_LOPPU leikataan merkkitilan peliin samaan kuvaan.
;
; Muisti (levyllä kolmena tiedostona, split.py):
;   KT1  $2000-$7f3f  huone: koodi ja data, ruutu $5c00, bittikartta $6000
;   KT2  $8000-$bf3f  näyttö: spritet ja taulut $8000, ruutu $8c00, värit $9000, pelin ruutu ja värit $9400,
;                     bittikartta $a000
;   KT0  $c000-       ydin: kt_init, kt_go, IRQ, vaihto peliin (peli.asm, $2003) kehyksessä PELI_ALKU
;   KT3  $e000-       pelin ruutu bittikarttana (näytön laajeneminen)
; Peli (peli.asm, KT4 ja KT5) ladataan huoneen ja näytön muistiin niiden jälkeen (src/scene/kaupungintalo_glue.asm).

        .include "kt.inc"

        .weak
FRAME_HOOK = $0408
R_IDLE  = $0422
DFRAME  = $d0
        .endweak

ZP0     = $30
IRQ_LINE = 250
HUONE_LINE = 170                ; huoneen IRQ pään rivien (3-13) jälkeen: asennon kopio valmis ennen kuin säde palaa
CC_LINE = 68                    ; lähikuvan viimeinen kehys: pelin värikopio alkaa, kun rivit 0-2 on haettu (cc_copy)
PELI_GO = $2003                 ; peli.asm: hyppytaulu
PELI_COLBUF = $7c00             ; = peli.asm COLBUF
PELI_VAIHTO = NAYTTO_LOPPU - 2  ; = peli_build.py PELI_ALKU: ensimmäinen pelikuva osan kehyksessä
                                ; NAYTTO_LOPPU - 1 (mitattu)

        .virtual ZP0
ra      .byte ?
rx      .byte ?
ry      .byte ?
z_ev    .byte ?                 ; seuraava pään tapahtuma
z_div   .byte ?                 ; kehyksiä vierityksen askeleeseen
z_off   .byte ?                 ; kuvaruudun Y-siirto (nauhan rivi)
z_ptr   .word ?                 ; asennon kopiorutiini, käsien tilan data (kad_copy)
z_kev   .byte ?                 ; seuraava käsien tapahtuma (kadet.asm)
z_kend  .byte ?                 ; kad_copy: tilan loppu (Y)
z_dst   .word ?                 ; kad_copy: solun osoite - 8 * solu
z_phase .byte ?                 ; 0 huone, 1 näyttö, 2 loppu (pysyy)
z_t     .byte ?                 ; kehys vaiheen alusta (näyttö)
z_peli  .byte ?                 ; 1 = peli ladattu ja valmisteltu (kt_peli_ok)
z_rv    .word ?                 ; seuraava paljastettava solu
z_cc    .byte ?                 ; 1 = kopioi pelin värit seuraavassa kehyksessä (irq_cc)
z_ccok  .byte ?                 ; 1 = pelin värit kopioitu
kam_on  .byte ?                 ; 1 = kamera-ajo (kamera.asm)
kam_n   .word ?                 ; näytettävä kehys
kam_c   .word ?                 ; laskettava kehys
kam_ready .word ?               ; viimeksi valmistunut puskuri (kehys)
kam_busy .byte ?
kam_db  .byte ?                 ; näytettävä puskuri
kam_b   .byte ?                 ; laskettava puskuri
kam_ml  .byte ?                 ; multipleksausrivi
kam_rp  .word ?                 ; seuraavan paljastettavan solun alatavu (kam_rev_lo)
kam_hp  .word ?                 ; sen yläbittien tavu (kam_rev_hi)
kam_hb  .byte ?                 ; yläbitit jäljellä
kam_hc  .byte ?                 ; soluja tavussa jäljellä
kam_rf  .word ?                 ; seuraava kehys, jonka solut paljastetaan
kam_t0  .word ?
kam_t1  .byte ?
kam_t2  .word ?
kam_t3  .byte ?
kam_t4  .word ?
kam_t5  .word ?
kam_t6  .byte ?
kam_r0  .byte ?
kam_r1  .byte ?
kam_r2  .byte ?
kam_sf  .byte ?                 ; s (8.8): murto-osa
kam_si  .byte ?                 ; kokonaisosa
kam_sfr .word ?                 ; kehys, jonka s on kam_sf/kam_si
kb0     .byte ?                 ; kam_gen: lohkon rivi
kb1     .byte ?
kb2     .byte ?
kv_x0   .word ?                 ; palkin reunat (kv_set)
kv_x1   .word ?
kv_ye                           ; pystypalkin alapää
kv_y0   .word ?
kv_y1   .word ?
kv_xs   .word ?                 ; spritejen alue (kam_row)
kv_xe   .word ?
kv_px   .word ?                 ; spriten kohta
kv_pw   .byte ?                 ; spriten leveys 24 tai 48
kv_blk  .byte ?                 ; ensimmäisen spriten lohko
kv_blk2 .byte ?                 ; muiden
kv_cur  .byte ?
kv_k    .byte ?                 ; kanava
kv_ci   .byte ?                 ; kohta kanavajonossa kam_chs
kv_xx   .byte ?                 ; 1 = X-laajennus
kv_yx   .byte ?                 ; 1 = Y-laajennus
kv_vert .byte ?                 ; 1 = pystypalkin kopiot alapäähän kv_ye asti
kv_hy   .byte ?                 ; vaakapalkin Y-rekisteri
kv_he   .byte ?                 ; vaakapalkin vaihtorivi (kam_mux)
zp_end
        .cerror zp_end > $90, "nollasivu ylittää $8f"
        .endv

; ================================================================ KT1: huone ja kamera-ajo
        * = $1a00
        .include "kamera_tab.asm"       ; kamera-ajon taulut (kamera.py)
kam_e_lo .fill KAM_REUNOJA, 0
kam_e_hi .fill KAM_REUNOJA, 0
kb_e    .fill 96, 0                        ; kopiolistojen vaihtorivi (kam_mux), kuten kb_y
        .dsection kam_etu1              ; kamera-ajon lohkolista ja kanavajonot (kamera.asm)
        .cerror * > $2000, "kamera-ajon taulut ylittävät $2000"
        * = $2000
        .include "huone_nauhat.asm"
        .include "huone_piirto.asm"
        .include "paat.asm"
        .include "kamera.asm"
        .if KAM_TA
        .include "kamera_rajaus_b.asm"
        .endif
H_VCOL  .binary "huone.kla", 2 + 9000, 1000
kt1_end
        .cerror kt1_end > $5c00, "huoneen koodi ja taulut ylittävät ruudun $5c00"
        * = $5c00
H_SCREEN .binary "huone.kla", 2 + 8000, 1000
        * = $6000
H_BITMAP .binary "huone.kla", 2, 8000
        .include "kamera_vak.asm"       ; kamera-ajon palkkien ja kuvaruudun vakiot bittikartan perässä
        .cerror * > $8000, "kamera-ajon vakiot ylittävät pankin 1"
kt1_data_end

; ================================================================ KT2: näyttö ja ydin
        * = $8000
SPR0    .include "naytto.asm"           ; spritelohkot 0-1 ($8000-$807f), kursorin reitti, paljastuksen solut
; ---------------------------------------------------------------- muuttujat: kamera-ajo (näytön taulujen perässä, näyttö ei käytä)
kam_idx .fill 8, 0
kam_end .fill 8, 0
kb_cnt  .fill 16, 0                        ; [puskuri * 8 + kanava]
kb_y    .fill 96, 0                        ; [puskuri * 48 + kanava * 6 + kopio]
kb_x    .fill 96, 0
kb_p    .fill 96, 0
kb_d010 .fill 2, 0
kb_d015 .fill 2, 0
kb_d01d .fill 2, 0
kb_d017 .fill 2, 0
ka_t0   .byte 0                         ; kam_apply (IRQ-taso)
ka_t1   .byte 0
ka_t2   .byte 0
kam_rleft .byte 0                       ; kehyksen soluja jäljellä
kam_bud .byte 0
kam_pvo .byte 0                         ; pystypalkin tietue (kam_pv)
        .include "kamera_init.asm"
        .dsection kam_etu3              ; kamera.asm kv_w ja kv_xe344 (KT1:n koodialue on täynnä)
        .cerror * > $8c00, "näytön taulut ylittävät ruudun $8c00"
        .if KT_IKKUNA                   ; ikkunassa ei näyttöä: ruutu, värit ja bittikartta vain symboleina, jotta KT2
N_SCREEN = $8c00                        ; on $8000-$9fff ja $a000-$bfff vapaa (koko demossa edellinen taulu siellä,
N_VCOL  = $9000                         ; kun KT2 esiladataan sen aikana)
N_BITMAP = $a000
        * = $8f40                       ; kamera-ajon solun kopio ja multipleksausrivit samalla sivun kohdalla kuin
        .include "kamera_b.asm"         ; kaupungintalossa ($bf40-): sivurajojen ylitykset ja syklit ennallaan
        .dsection kam_etu2
        .cerror * > $9000, "kamera-ajon koodi ylittää $9000"
        .else
        * = $8c00
N_SCREEN .binary "naytto.kla", 2 + 8000, 1000
        * = $9000
N_VCOL  .binary "naytto.kla", 2 + 9000, 1000
        .endif
        * = $9400
        .if KT_IKKUNA
G_SCR                                   ; ikkunassa ei näyttöä: pelin ruudun tilalla johtajan kädet
        .include "kadet.asm"
        .include "kadet_copy.asm"
        .cerror * > $9800, "kädet ylittävät $9800"
        .else
G_SCR   .binary "naytto_peli.kla", 2 + 8000, 1000      ; pelin ruutu bittikarttana: ruutu ja värit
        .endif
        * = $9800
        .if KT_IKKUNA
G_COL                                   ; ikkunassa ei näyttöä: pelin värien paikka vapaa
kt2_data_end
        .else
G_COL   .binary "naytto_peli.kla", 2 + 9000, 1000
        * = $a000
N_BITMAP .binary "naytto.kla", 2, 8000
        .include "kamera_b.asm"         ; kamera-ajo: solun kopio ja multipleksausrivit näytön kuvan perässä
        .dsection kam_etu2              ; kamera.asm kam_hkapea
        .cerror * > $c000, "kamera-ajon koodi ylittää pankin 2"
kt2_data_end
        .endif

        * = $c000
; kt_init: nollasivu ja kuvaruudut valmiiksi (edellinen kohtaus voi näkyä: ei VIC-rekistereitä)
kt_init
        ldx #ZP0
        lda #0
-       sta $00,x
        inx
        cpx #zp_end
        bne -
        .if !KT_IKKUNA
        rts
        .endif
        lda #RUUTU_ASKEL-1
        sta z_div
        lda #KAM_PC_Z0                  ; PC:n kuvaruutu kamera-ajon ajan paikallaan, vierii huoneessa (kamera.asm)
        sta z_off
        jsr kam_init
        ldy z_off
        jmp huone_piirto

; kt_go: ikkuna: kamera-ajon kooste (ulkonäkymä, VIC-pankki 3) ja sen IRQ (kamera.asm kam_go); huone (pankki 1)
; tulee kehyksessä KAM_LOPPU (kam_vaihto). Muuten näytön lähikuva ja sen IRQ. Palaa heti.
kt_go
        sei
        .if KT_IKKUNA
        jsr kam_go
        jsr kt_vic
        .else
        jsr kt_vic
        jsr naytto_on
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        .endif
        lda #$ff
        sta $d019
        lda #1
        sta $d01a
        cli
        rts

; kt_vic: kooste MC-bittikarttana, reuna musta, spritet pois (kt_go, kt_show)
kt_vic
        lda #$18
        sta $d016
        lda #HUONE_BG
        sta $d021
        lda #0
        sta $d020
        sta $d015
        lda #$3b                        ; bittikartta päälle, rivi < 256
        sta $d011
        rts

; kt_peli_ok: kohtaustaulu kutsuu, kun peli (KT4) on ladattu ja peli_init ajettu
kt_peli_ok
        lda #1
        sta z_peli
        rts

; vcol: X/Y = 1000 tavun lähde -> $d800 (rivi kerrallaan ylhäältä: säde ei ohita rivillä 250 alkavaa kopiota)
vcol
        stx _s1+1
        sty _s1+2
        lda #<$d800
        sta _d1+1
        lda #>$d800
        sta _d1+2
        ldy #25
_row    ldx #39
_s1     lda $ffff,x
_d1     sta $ffff,x
        dex
        bpl _s1
        clc
        lda _s1+1
        adc #40
        sta _s1+1
        bcc +
        inc _s1+2
+       clc
        lda _d1+1
        adc #40
        sta _d1+1
        bcc +
        inc _d1+2
+       dey
        bne _row
        rts

; IRQ: musiikki ja kello, sitten vaiheen liike
irq
        sta ra
        stx rx
        sty ry
        asl $d019
        jsr FRAME_HOOK
        lda z_phase
        beq _huone                      ; 0 huone (ikkuna), 1 näyttö
        cmp #1
        bne _out
        jsr naytto_frame
        lda z_cc                        ; viimeinen lähikuvakehys tulossa: värikopio rivillä CC_LINE
        beq _out
        lda #<irq_cc
        sta $fffe
        lda #>irq_cc
        sta $ffff
        lda #CC_LINE
        sta $d012
        jmp _out
_huone  jsr huone_frame
_out    lda ra
        ldx rx
        ldy ry
        rti

; irq_cc: lähikuvan viimeinen kehys, pelin värit säteen perässä. Pelin FLD-rako (peli.asm irq_split, 1 idle-rivi
; rivin 1 jälkeen) on leivottu pelin bittikarttaan (naytto_peli.kla), joten lähikuvassa ei ole
; FLD:tä eikä raon viiva vuoda näytön kuvaan, ja leikkaus peliin osuu samaan kuvaan.
irq_cc
        sta ra
        stx rx
        sty ry
        asl $d019
        lda #<irq                       ; rivin 250 IRQ ensin (cc_copy kestää rivin 250 yli: IRQ jää odottamaan)
        sta $fffe
        lda #>irq
        sta $ffff
        lda #IRQ_LINE
        sta $d012
        jsr cc_copy
        lda #0
        sta z_cc
        inc z_ccok
        jmp irq._out

; cc_copy: pelin värit (peli_init valmisti ne PELI_COLBUF:iin) värimuistiin ylhäältä alas säteen perässä: kutsutaan
; rivillä CC_LINE (rivit 0-2 jo haettu), ja rivi kestää 560 sykliä eli enemmän kuin säteen rivi (504), joten kopio ei
; ohita sädettä. Lähikuvan viimeinen kehys näkyy omilla väreillään ja peli seuraavassa kehyksessä omillaan (ei
; värivälähdystä leikkauksessa). Odotussilmukoita ei ole: rivin 255 jälkeen $d012 kiertyisi.
cc_copy
        .for r = 0, r < 25, r += 1
        ldx #39
-       lda PELI_COLBUF + r * 40,x
        sta $d800 + r * 40,x
        dex
        bpl -
        .next
        rts

; ---------------------------------------------------------------- huone
huone_frame
        dec z_div                       ; pienoisruutu joka RUUTU_ASKEL. kehys
        bpl _pose
        lda #RUUTU_ASKEL-1
        sta z_div
        ldy z_off
        beq +
        dey
        sty z_off
+       jmp huone_piirto
_pose   ldx z_ev                        ; pään asento tapahtumataulusta (DFRAME >= ev_f)
        lda DFRAME
        cmp ev_f_lo,x
        lda DFRAME+1
        sbc ev_f_hi,x
        bcc +
        inc z_ev
        ldy ev_pose,x
        lda paa_lo,y
        sta z_ptr
        lda paa_hi,y
        sta z_ptr+1
        jmp (z_ptr)
+
        .if KT_IKKUNA
        ldx z_kev                       ; käsien tila tapahtumataulusta (DFRAME >= kad_f), ei pään kopion kehyksessä
        lda DFRAME
        cmp kad_f_lo,x
        lda DFRAME+1
        sbc kad_f_hi,x
        bcc +
        inc z_kev
        ldy kad_s,x
        jmp kad_copy
        .endif
+       rts

; ---------------------------------------------------------------- näytön lähikuva
naytto_on
        inc z_phase
        lda #IRQ_LINE
        sta $d012
        lda #1                          ; VIC-pankki 2 ($8000-$bfff) heti rajalla, värit sen jälkeen säteen edellä
        sta $dd00
        lda #((N_SCREEN & $3fff) >> 6) | ((N_BITMAP & $3fff) >> 10)
        sta $d018
        lda #NAYTTO_BG
        sta $d021
        ldx #<N_VCOL
        ldy #>N_VCOL
        jsr vcol
        lda #0
        sta z_t
        sta z_rv
        sta z_rv+1
        sta $d01c                       ; hires-spritet
        sta $d010
        sta $d01d
        sta $d017
        ldx #1
-       txa
        sta N_SCREEN + $3f8,x           ; lohkot 0-1 = SPR0
        lda spr_col,x
        sta $d027,x
        dex
        bpl -
        jsr spr_pos
        lda #%00000011
        sta $d015
        rts

naytto_frame
        lda z_peli                      ; peliin, kun kello on PELI_ALKU:ssa ja peli on ladattu
        beq _nf
        lda DFRAME+1                    ; kehystä ennen: värit säteen perässä seuraavassa kehyksessä (irq_cc)
        cmp #>(PELI_VAIHTO-1)
        bne +
        lda DFRAME
        cmp #<(PELI_VAIHTO-1)
        bne +
        inc z_cc
+
        lda DFRAME+1
        cmp #>PELI_VAIHTO
        bcc _nf
        bne +
        lda DFRAME
        cmp #<PELI_VAIHTO
        bcc _nf
+       inc z_phase
        ldx z_ccok                      ; X = 1: värit jo kopioitu (cc_copy)
        jmp PELI_GO
_nf     lda z_t
        cmp #N_MOVE
        bcs +
        inc z_t
+       jsr spr_pos
        lda z_t                         ; laajeneminen: kehys f = z_t - PAL0
        sec
        sbc #PAL0
        bcc _nod
        cmp #PALJASTUS
        bcs _nod
        tax
_cell   lda z_rv                        ; solut z_rv .. pal_end[f]-1
        cmp pal_end_lo,x
        lda z_rv+1
        sbc pal_end_hi,x
        bcs _nod
        jsr reveal
        inc z_rv
        bne _cell
        inc z_rv+1
        jmp _cell
_nod    rts

; reveal: solu pal[z_rv] pelin bittikartasta näkyviin (8 tavua, ruutu, väri). X säilyy.
reveal
        clc                             ; solun indeksi pal_lo[z_rv], pal_hi[z_rv] (z_rv 16-bittinen)
        lda #<pal_lo
        adc z_rv
        sta _l+1
        lda #>pal_lo
        adc z_rv+1
        sta _l+2
        clc
        lda #<pal_hi
        adc z_rv
        sta _h+1
        lda #>pal_hi
        adc z_rv+1
        sta _h+2
_l      lda $ffff
        sta z_ptr
_h      lda $ffff
        sta z_ptr+1                     ; z_ptr = solun indeksi 0-999
        ldy #0
        lda z_ptr                       ; ruutu ja väri
        sta _s1+1
        sta _d1+1
        sta _s2+1
        sta _d2+1
        lda z_ptr+1
        clc
        adc #>G_SCR
        sta _s1+2
        adc #>(N_SCREEN - G_SCR)
        sta _d1+2
        lda z_ptr+1
        clc
        adc #>G_COL
        sta _s2+2
        lda z_ptr+1
        clc
        adc #$d8
        sta _d2+2
_s1     lda $ffff
_d1     sta $ffff
_s2     lda $ffff
_d2     sta $ffff
        asl z_ptr                       ; bittikartta: indeksi * 8
        rol z_ptr+1
        asl z_ptr
        rol z_ptr+1
        asl z_ptr
        rol z_ptr+1
        lda z_ptr
        sta _s3+1
        sta _d3+1
        lda z_ptr+1
        clc
        adc #>G_BITMAP
        sta _s3+2
        lda z_ptr+1
        clc
        adc #>N_BITMAP
        sta _d3+2
        ldy #7
_s3     lda $ffff,y
_d3     sta $ffff,y
        dey
        bpl _s3
        rts

; kursori kulkee taulukon kur_x/kur_y mukaan (naytto.asm)
spr_pos
        ldx z_t
        lda kur_x,x
        sta $d000
        sta $d002
        lda kur_y,x
        sta $d001
        sta $d003
        rts

PAL0    = NAYTTO_LOPPU - PALJASTUS     ; laajeneminen näytön viimeisinä kehyksinä (näyttö alkaa osan kehyksestä 0)
kt0_core_end
        .cerror kt0_core_end > KAM_SCREEN, "ydin ylittää kamera-ajon ruudun"
        * = KAM_SCREEN
        .binary "kooste.kla", 2 + 8000, 1000    ; kamera-ajon alkukuva (ulkonäkymä): ruutu ja värit (KAM_VSRC)
        * = KAM_VSRC
        .binary "kooste.kla", 2 + 9000, 1000
kam_af  .fill 8, 0                      ; kamera-ajon monikerrat a * 16 * s (kam_edge)
kam_al  .fill 8, 0
kam_ah  .fill 8, 0
kam_bf  .fill 16, 0                     ; 1/2 + b * s
kam_bl  .fill 16, 0
kam_bh  .fill 16, 0
        .if KAM_TA
kb_il   .fill 16, 0                     ; vaihtoehdon multipleksauslista puskureittain: laukaisurivi
kb_iw   .fill 16, 0                     ; odotusrivi ($d011:n vaihto), 0 = ei
kb_iv   .fill 16, 0                     ; $d011
kb_in   .fill 2, 0                      ; rivejä
kb_col  .fill 2, 0                      ; spritejen väri
kb_top  .fill 2, 0                      ; $d011 kuvan alussa
kam_il  .fill 8, 0                      ; näytettävä lista (kam_ra_apply)
kam_iw  .fill 8, 0
kam_iv  .fill 8, 0
kam_in  .byte 0
kam_top .byte 0
ra_u8   .byte 0                         ; kam_ra
ra_yt   .byte 0
ra_yb   .byte 0
ra_al   .fill 2, 0
ra_av   .fill 2, 0
ra_ai   .byte 0
ra_na   .byte 0
ra_o    .byte 0
ra_m    .byte 0
ra_n    .byte 0
        .include "kamera_ra.asm"        ; alkuvaiheen u kehyksittäin (kamera.py rajaus_u)
        .cerror * > $cd00, "kamera-ajon vaihtoehdon muuttujat ylittävät $cd00"
        .endif
        * = $cd00
        .include "kamera_d.asm"         ; s:n askeleet kehyksittäin, vakioiden ylätavut
        .include "kamera_c.asm"
; kt_show (#S_SHOW, ennen kelloa) ilman IRQ:ta, jotta osalevyn kehys 0 ei ole musta; kt_go asettaa saman uudelleen.
; Ikkuna: kamera-ajon ensimmäinen kuva (ulkonäkymä ilman palkkeja, kuten kehyksissä 0-2); rajauksen alkuvaihe tarvitsee
; IRQ:n, joten sille ei ole kt_show:ta. Muuten näytön lähikuva ilman kursoria (kursori kehyksestä 1).
        .if KT_IKKUNA && !KAM_TA
kt_show
        ldx #<KAM_VSRC
        ldy #>KAM_VSRC
        jsr vcol
        lda #0                          ; VIC-pankki 3 (kuten kam_go)
        sta $dd00
        lda #KAM_D018
        sta $d018
        jmp kt_vic
        .elsif !KT_IKKUNA
kt_show
        ldx #<N_VCOL
        ldy #>N_VCOL
        jsr vcol
        lda #1                          ; VIC-pankki 2 (kuten naytto_on)
        sta $dd00
        lda #((N_SCREEN & $3fff) >> 6) | ((N_BITMAP & $3fff) >> 10)
        sta $d018
        jsr kt_vic
        lda #NAYTTO_BG
        sta $d021
        rts
        .endif
        .if KAM_TA
        .include "kamera_rajaus.asm"
        .endif
kt0_end
        .cerror kt0_end > $d000, "ydin ylittää $cfff"

; ================================================================ KT3: pelin ruutu bittikarttana (näytön laajeneminen)
        * = $e000
G_BITMAP .binary "naytto_peli.kla", 2, 8000
kt3_end

; KT6 = kamera-ajon alkukuvan (ulkonäkymä) bittikartta $e000-$ff3f (split.py, kooste.kla)
