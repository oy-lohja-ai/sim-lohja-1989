; Sokeripala (demon loppu ennen lopputekstejä).
; Data tools/gfx/data/sokeripala/, aikataulut build.py ja lehti.py, taulu tools/gfx/taulu.py.
;
; Kuvat (kehykset kohtauksen alusta, sp.inc):
;   0 - T_LEHTI-1        panoraama: kamera kääntyy pimeästä Lohjantähdestä oikealle torin
;                        yli ja lähestyy Sokeripalaa (vieritys 0-T_PYSAHTYY pikseli kehyksessä), pysähdyksessä
;                        Sokeripalan ikkunat sammuvat yksi kerrallaan (tapahtumat ruutuun ja värimuistiin).
;                        Hyppy iskun tahdissa (YSCROLL letterboxissa, hyppy) on pois käytöstä (build.py HYPPY_H = 0).
;                        Nimi SOKERIPALA kelluu kehyksestä NIMI_KELLU.
;                        MC-bittikartta: $d016 hienovieritys, merkkiaskel 8 kehyksen välein vaihtaa puskuria (A pankki
;                        1, B pankki 3); kuudessa kehyksessä 6510 kopioi näkyvän puskurin sarakkeen siirrettynä
;                        piilossa olevaan ja uuden sarakkeen tietueesta, vaihtokehyksessä värimuisti siirtyy säteen
;                        edellä (rivit PR0-PR1, letterbox musta)
;   T_LEHTI - T_SIVU-1   Länsi-Uusimaa pyörii pystyakselinsa ympäri perspektiivissä ja tulee lähelle (MC-merkkitila,
;                        VIC-pankki 2, kaksi ruutua vuorotellen): joka kehys 6510 laskee sarakkeittain korkeuden ja
;                        perspektiivin u:n ja kopioi sarakkeen merkit profiilitaulusta (spin_render)
;   T_SIVU - T_PELI-1    sivu pysähtyy terävänä (hires-bittikartta, VIC-pankki 1), kynä alleviivaa ja ympyröi
;   T_PELI - T_TAULU-1   SimCity 2026: kaupunginjohtaja vie timanttikursorin Sokeripalalle ja klikkaa,
;                        neuvonantajan ikkuna avautuu ja «Museovirasto: Rakennusta ei saa purkaa.» kirjoittuu,
;                        budjetti-ikkunaan «SSO + WasaGroup: hotellihanke» ja +€€€, Kulttuuriarvo laskee nollaan,
;                        kursori epäröi Ohitan päällä ja jää OK:n ja Ohitan väliin; kuva leikkautuu ennen klikkausta
;                        (hires-bittikartta, VIC-pankki 2; tapahtumat = solujen kopioita, spritet taulusta)
;   T_TAULU - T_LOPPU-1  kerrontataulu «JATKUU...» (src/lib/taulu.asm, VIC-pankki 1)
;
; Muisti:
;   SP0  $1a00-        ydin: sisääntulot, IRQ, tapahtumien ajajat, panoraama, pyörähdys, taulun moduuli
;   SPP1 $5c00-$7f3f   panoraama: puskuri A (ruutu $5c00, bittikartta $6000) ja välien tietueet 0-11, ennen kelloa
;   SPP2 $4000-$5bff   tietueet 12-50 ja SPP3 $c000-$cbff tietueet 51-59: ladataan panoraaman aikana käyttöjärjestyksessä
;                      (tietue n tarvitaan kehyksestä 8 n + 1); puskurin B ruutu $cc00 (sp_init nollaa), bittikartta $e000
;   SP2A $8000-$bfff   pyörähdys: ruudut $8000 ja $8400, merkistö $8800, profiilit $9000, asennot SPIN_POSE
;                      (ladataan panoraaman aikana, panoraama ei käytä pankkia 2)
;   SP2D $4000-$7f3f   sivu (panoraaman jälkeen): kynän tapahtumat $4000, ruutu $5c00, bittikartta $6000
;   SP3  $8000-$bf3f   peli (pyörähdyksen jälkeen): spritet $8000, ruutu $8c00, solupalat $9000, spritetaulu $9400,
;                      bittikartta $a000          SP3B $e000-   pelin solukopiot
;   SP4  $6000-$7f3f   taulun bittikartta (sivun jälkeen); taulun spritet $4000 ja ruutu $5c00 (taulu_alku)
;   SP4K $4800-        taulun ajonaikainen koodi (IRQ, taulumoduuli, kiilto): taulun aikana ydin $1a00- on vapaa
; IRQ rivillä 250: FRAME_HOOK, sitten valmistellaan kehys DFRAME + 1 (sen näkyvä alue piirtyy seuraavaksi).

        .include "sp.inc"
        .include "taulu_jatkuu.inc"

FRAME_HOOK = $0408
DFRAME  = $d0
IRQ_LINE = 250
PA_SA   = $5c00                 ; panoraaman puskurit: A pankki 1, B pankki 3
PA_BA   = $6000
PA_SB   = $cc00
PA_BB   = $e000
D018_PA = ((PA_SA & $3fff) >> 6) | ((PA_BA & $3fff) >> 10)
D018_PB = ((PA_SB & $3fff) >> 6) | ((PA_BB & $3fff) >> 10)
SIVU_SCR = $5c00
SIVU_BMP = $6000
SIVU_EV  = $4000
SPIN_SCR = $8000                ; ruudut $8000 ja $8400
SPIN_CS  = $8800
PELI_SPRMEM = $8000
PELI_SCR = $8c00
PELI_BLOB = $9000
PELI_BMP = $a000
PE_TAB  = $e000
TAULU_SCREEN = $5c00
TAULU_SPRMEM = $4000
TAULU_SPRBLK = (TAULU_SPRMEM & $3fff) / 64
TZP     = $f0                   ; taulun nollasivu $f0-$fb (kuten src/proto/taulu): koti_init1 nollaa $02-$9f
                                ; taulun häivytyksessä, ja alempana taulun IRQ kirjoittaisi kodin muuttujien päälle
TK      = $4800                 ; taulun ajonaikainen koodi (SP4K): kodin bss $4000-$4771 (koti_init1 ajetaan taulun
                                ; häivytyksen aikana, jatkuva siirtymä sokeripala -> koti)
SP4K_VARA = $5600                ; SP4K ja kiillon listat (sp_taulu) tähän asti; $5600-$5bff vapaa (part-sokeripala.json)
tk_l    = TZP + 11
D018_P1 = ((SIVU_SCR & $3fff) >> 6) | ((SIVU_BMP & $3fff) >> 10)
D018_P2 = ((PELI_SCR & $3fff) >> 6) | ((PELI_BMP & $3fff) >> 10)
D018_S  = ((SPIN_SCR & $3fff) >> 6) | ((SPIN_CS & $3fff) >> 10)
SPRBLK2 = (PELI_SPRMEM & $3fff) / 64    ; kaupunginjohtaja 0-1, timantin keltainen kerros 2-17, musta 18-33,
                                        ; kopteri 34-35 (kaksi roottorivaihetta)

        .virtual $02
z_t     .word ?                 ; valmisteltava kehys (DFRAME + 1)
z_l     .word ?                 ; kuvan oma kehys
z_te    .word ?                 ; pysähdyksen / sivun seuraava tapahtuma
z_pe    .word ?                 ; pelin seuraava solukopio
z_ps    .word ?                 ; pelin spritetaulu (5 t kehyksessä)
z_s     .word ?
z_d     .word ?
z_c     .word ?
z_busy  .byte ?
z_sivu  .byte ?                 ; 1, kun SP2D (sivu) on ladattu
z_fld   .byte ?                 ; kameran pystyliike: FLD-rivejä ruudun yläreunassa (0 = ei)
z_ha    .byte ?                 ; hyppy: kuva alempana z_ha + z_hb riviä (YSCROLL-kirjoitukset letterboxissa)
z_hb    .byte ?
s_buf   .byte ?                 ; panoraama: näkyvä puskuri (0 = A, 1 = B)
s_k     .byte ?                 ; näkyvän puskurin ikkuna (merkkisarake)
s_chunk .byte ?                 ; piilopuskurin kopio: valmiit kolmen rivin palat (6 = valmis)
s_rec   .word ?                 ; uuden sarakkeen tietue
s_r     .byte ?
z_lehti .byte ?                 ; 1 = pyörähdyksen asennot valmiina (sp_lehti), 2 = pyörähdys käynnissä
z_h     .byte ?                 ; pelin kopterin kohta kierroksella (0 - KIERROS-1)
z_iv    .word ?                 ; alun nousutietue
zp_end
        .endv
        .cerror zp_end > TZP, "nollasivu"
        .cerror z_c != z_d + 2, "kiire: z_d ja z_c peräkkäin"

        .virtual $40            ; pyörähdys (spin_render)
q_xl    .byte ?
q_xr    .byte ?
q_hl    .byte ?
q_hr    .byte ?
q_back  .byte ?
q_w     .byte ?
q_cr    .byte ?                 ; oikean reunan sarake
q_ce    .byte ?                 ; viimeinen sisäsarake
q_buf   .byte ?                 ; piirrettävä ruutu: 0 = $8000, 1 = $8400
q_valmis .byte ?                ; näkyvä (viimeksi valmistunut) ruutu
q_or    .byte ?                 ; reunasarakkeen versio (16 x v)
q_rw    .word ?                 ; 1024 / W (8.8): s:n askel sarakkeessa
q_dh    .word ?                 ; korkeuden askel sarakkeessa (8.8, etumerkillinen)
q_s     .word ?
q_h     .word ?
q_eb    .word ?                 ; sp_exp + log hr
q_e     .word ?
q_sp    .word ?                 ; sarakkeen merkit
q_k     .byte ?
q_m     .word ?                 ; kertolasku
q_p     .word ?
q_end
        .endv

        * = $1a00
; sp_init: pääsäikeessä ennen kelloa: nollasivu ja puskurin B ruutu (ei VIC-rekistereitä eikä värimuistia: edellinen
; kuva, runkon siirtymä, voi näkyä tämän aikana)
sp_init
        ldx #z_t
        lda #0
-       sta $00,x
        inx
        cpx #zp_end
        bne -
        sta $7fff                       ; VIC-pankin 1 viimeinen tavu: FLD:n alla tyhjä (musta)
        lda #<NOUSU0
        sta z_iv
        lda #>NOUSU0
        sta z_iv+1
        lda #<pano_ev
        sta z_te
        lda #>pano_ev
        sta z_te+1
        lda #<PE_TAB
        sta z_pe
        lda #>PE_TAB
        sta z_pe+1
        lda #<PELI_SPR
        sta z_ps
        lda #>PELI_SPR
        sta z_ps+1
        ldx #0                          ; puskurin B ruutu nollaksi (letterbox musta; rivit PR0-PR1 kopioidaan)
        txa
-       sta PA_SB,x
        sta PA_SB+$100,x
        sta PA_SB+$200,x
        sta PA_SB+$2e8,x
        inx
        bne -
        rts

; sp_show: kehys 0 ennen kelloa (osalevyn S_SHOW, ilman IRQ:ta): odottaa rivin 250, jotta edellinen kuva (runkon
; siirtymä) vaihtuu panoraamaan kokonaisen kehyksen rajalla, sitten nayta
sp_show
-       bit $d011
        bpl -
-       lda $d012
        cmp #IRQ_LINE
        bne -
; nayta: VIC-rekisterit ja värimuisti säteen edellä (sivu kerrallaan ylhäältä alas; rivillä 250 alkaessa valmis ennen
; ruudun yläreunaa). Kehys 0: yötaivas tähtineen, kaupunki mustana.
nayta   lda #2                          ; VIC-pankki 1; $dd00:aan vain 0-3
        sta $dd00
        lda #D018_PA
        sta $d018
        lda #$17                        ; MC, 38 saraketta, hienovieritys 7
        sta $d016
        lda #0
        sta $d020
        sta $d021
        sta $d015
        lda #$3b                        ; bittikartta
        sta $d011
        ldx #0
-       lda pano_col,x
        sta $d800,x
        inx
        bne -
-       lda pano_col+$100,x
        sta $d900,x
        inx
        bne -
-       lda pano_col+$200,x
        sta $da00,x
        inx
        bne -
-       lda pano_col+$2e8,x
        sta $dae8,x
        inx
        bne -
        rts

; sp_go: kellon alussa (rivi 250): oma IRQ ja kehys 1 (koko demossa S_SHOW ei tee mitään, joten kuva tulee tästä)
sp_go
        sei
        jsr nayta
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        lda #IRQ_LINE
        sta $d012
        lda #$ff
        sta $d019
        lda #1
        sta $d01a
        jsr kehys
        cli
        rts

; sp_lehti: pääsäikeessä, kun SP2A on ladattu (panoraaman aikana): pyörähdyksen kaksi ensimmäistä asentoa ruutuihin
sp_lehti
        ldx #q_end - q_xl - 1           ; ruutujen sarakeavaimet tyhjiksi ($ff: ensimmäinen piirto kirjoittaa kaiken)
        lda #0
-       sta q_xl,x
        dex
        bpl -
        ldx #79
        lda #$ff
-       sta avain_lo,x
        sta avain_hi,x
        sta avain_or,x
        dex
        bpl -
        lda #0                          ; asento 0 ruutuun 0 ja asento 1 ruutuun 1 (ensimmäinen kehys värittää
        sta q_buf                       ; värimuistin eikä ehdi piirtää)
        sta q_valmis
        jsr spin_render
        lda #1
        sta q_buf
        jsr spin_render
        lda #1                          ; pyörähdys saa alkaa (SP2A latautuu panoraaman aikana)
        sta z_lehti
        rts

; sp_sivu: pääsäikeessä, kun SP2D on ladattu: sivu saa näkyä (muuten pyörähdyksen viimeinen asento jää)
sp_sivu
        lda #1
        sta z_sivu
        rts


; IRQ: FRAME_HOOK aina; kehyksen valmistelu cli:n jälkeen, jotta pitkä piirto (pyörähdys) ei koskaan pysäytä
; musiikkia: jos edellinen valmistelu on kesken, tämä kehys soittaa vain musiikin
irq
        pha
        txa
        pha
        tya
        pha
        lda $01
        pha
        lda #$35
        sta $01
        asl $d019
        lda z_fld                       ; tämän kehyksen FLD tai hyppy jätti YSCROLLin muuksi: takaisin (myös
        ora z_ha                        ; pudotetussa kehyksessä, jossa kehys ei aja)
        beq +
        lda #$3b
        sta $d011
+       jsr FRAME_HOOK
        lda trak_on                     ; puskutraktori (SPP3:ssa, kun ladattu): nimen rekisterit, trak_irq
        beq +
        jsr trak
+       lda z_busy
        beq _vapaa
        jsr kiire                       ; edellinen kehys kesken: panoraaman ajoituskriittiset (vieritys, nimi, hyppy)
        jmp _pois
_vapaa  inc z_busy
        cli
        jsr kehys
        sei
        dec z_busy
        lda z_fld                       ; kamera: seuraavan kehyksen yläreunaan FLD
        beq _pois
        lda #<fld_irq
        sta $fffe
        lda #>fld_irq
        sta $ffff
        lda #FLD_LINE
        sta $d012
_pois   pla
        sta $01
        pla
        tay
        pla
        tax
        pla
        rti

; FLD rivillä FLD_LINE: z_fld riviä ilman badlinea (YSCROLL aina rivin edellä), kuva alkaa z_fld riviä
; alempana (kamera kallistuu); sitten taas rivin 250 IRQ
FLD_LINE = $2c
fld_irq
        pha
        txa
        pha
        asl $d019
        ldx z_fld
_rivi   lda $d012
_odota  cmp $d012
        beq _odota
        lda $d011
        clc
        adc #1
        and #7
        ora #$38
        sta $d011
        dex
        bne _rivi
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        lda #IRQ_LINE
        sta $d012
        pla
        tax
        pla
        rti

; kuva: z_l = z_t - A/Y (kuvan alku), C = 1, jos z_t >= alku
alku    .macro t
        lda z_t
        sec
        sbc #<\t
        sta z_l
        lda z_t+1
        sbc #>\t
        sta z_l+1
        .endm

; kehys: valmistelee kehyksen DFRAME + 1 (kirjoitukset ennen ruudun yläreunaa)
kehys
        lda DFRAME
        clc
        adc #1
        sta z_t
        lda DFRAME+1
        adc #0
        sta z_t+1
        lda #0
        sta z_fld
        sta z_ha
        #alku T_TAULU
        bcc +
        jmp taulu
+       #alku T_PELI
        bcc +
        jmp peli
+       #alku T_SIVU
        bcc _ennen
        lda z_sivu                      ; sivu alkaa, kun se on ladattu (myöhästynyt lataus kuroo kiinni);
        beq _odota                      ; siihen asti pyörähdyksen viimeinen asento
        jmp sivu
_odota  rts
_ennen  #alku T_LEHTI
        bcc +
        lda z_lehti                     ; myöhästynyt SP2A: panoraaman loppukuva jää, pyörähdys kuroo kiinni
        beq +
        jmp spin
+       jmp pano

; ---------------------------------------------------------------- panoraama (kehys z_t = vierityskohta px)
pano
        lda z_t                         ; alku: yötaivas ja tähdet, kaupunki nousee esiin (tietueet NOUSU0:sta)
        sec
        sbc #<(T_ALKU - 1)              ; vierityskohta 1 kehyksellä T_ALKU (joka kehys muuttuu)
        tax
        lda z_t+1
        sbc #>(T_ALKU - 1)
        bcc _alku
        stx z_l                         ; z_l = vierityskohta (px), 0 = vielä alkua
        sta z_l+1
        ora z_l
        bne _p
_alku   jmp nousu
_p      jsr hyppy
        jsr nimi
        lda z_t                         ; pysähdys: viimeinen ikkuna, Sokeripalan ikkunat sammuvat
        cmp #<(T_PYSAHTYY + 1)
        lda z_t+1
        sbc #>(T_PYSAHTYY + 1)
        bcc _vierii
        lda z_t
        sec
        sbc #<T_PYSAHTYY
        sta z_l
        lda #$17
        sta $d016
        jmp ajo
_vierii lda z_l
        and #7
        eor #7
        ora #$10                        ; MC, 38 saraketta
        sta $d016
        lda z_l+1                       ; ikkuna l / 8: kun se vaihtuu (myös myöhästyneenä, jos vaihtokehys jäi
        lsr                             ; kiireen alle), merkkiaskel
        lda z_l
        ror
        lsr
        lsr
        cmp s_k
        beq _kopio
        lda #6                          ; piilopuskuri valmiiksi ensin (kopio jäljessä)
        sta kz_due
        jsr _kdue
        lda s_buf                       ; merkkiaskel: piilopuskuri (valmis) näkyviin, värimuisti perään
        eor #1
        sta s_buf
        tax                             ; A: $dd00 = 2 (pankki 1), B: 0 (pankki 3)
        lda pa_dd00,x
        sta $dd00
        lda pa_d018,x
        sta $d018
        inc s_k
        lda #0
        sta s_chunk
        ldx s_k                         ; oikean reunan sarake k + 39 = tietue k - 1
        dex
        lda pa_lo,x
        sta s_rec
        lda pa_hi,x
        sta s_rec+1
        ldy #8 * (PR1 - PR0) + (PR1 - PR0)      ; värimuistitavut tietueen lopussa
        .for r := PR0, r < PR1, r += 1
        ldx #0
-       lda $d801 + 40 * r,x
        sta $d800 + 40 * r,x
        inx
        cpx #39
        bne -
        lda (s_rec),y
        sta $d800 + 40 * r + 39
        iny
        .next
        rts
_kopio  lda z_l                         ; piilopuskuriin ikkuna k + 1: kolme riviä kehyksessä, palat 0 .. l & 7
        and #7                          ; (enintään 6) valmiiksi: kiireen yli jääneet kurotaan kiinni
        cmp #7
        bcc +
        lda #6
+       sta kz_due
_kdue   lda s_chunk
        cmp kz_due
        bcc +
        rts
+       ldx s_k                         ; uusi sarake k + 40 = tietue k
        lda pa_lo,x
        sta s_rec
        lda pa_hi,x
        sta s_rec+1
        lda s_chunk
        asl
        adc s_chunk
        sta s_r                         ; ensimmäinen rivi (0-17)
        clc
        adc #3
        sta _loppu+1
_rivi   ldx s_r
        lda s_buf                       ; lähde = näkyvä, kohde = piilo
        bne _ba
        lda #>PA_BA                     ; A näkyy: A -> B
        ldy #>PA_BB
        bne _bb
_ba     lda #>PA_BB
        ldy #>PA_BA
_bb     sta _sh+1
        sty _dh+1
        lda pa_rb_lo,x                  ; bittikartta: lähde + 8 -> kohde, 312 tavua
        clc
        adc #8
        sta z_s
        lda pa_rb_hi,x
_sh     adc #0
        sta z_s+1
        lda pa_rb_lo,x
        sta z_d
        lda pa_rb_hi,x
        clc
_dh     adc #0
        sta z_d+1
        jsr k312
        lda s_r                         ; uusi solu: 8 tavua tietueesta (y = 8 s_r + k) kohteen sarakkeeseen 39
        asl                             ; (z_d + 56 + k): z_c = z_d + 56 - 8 s_r, sama y
        asl
        asl
        sta z_c
        tay
        lda #56
        sec
        sbc z_c
        ldx #0
        bcs +
        dex
+       clc
        adc z_d
        sta z_c
        txa
        adc z_d+1
        sta z_c+1
        .for k := 0, k < 8, k += 1
        lda (s_rec),y
        sta (z_c),y
        iny
        .next
        lda s_r                         ; ruutu: lähde + 1 -> kohde, 39 tavua ja uuden solun ruututavu
        clc
        adc #PR0
        tax
        lda s_buf
        bne _sa
        lda #<PA_SA + 1
        ldy #>PA_SA
        bne _sb
_sa     lda #<PA_SB + 1
        ldy #>PA_SB
_sb     clc
        adc rivi40_lo,x
        sta z_s
        tya
        adc rivi40_hi,x
        sta z_s+1
        lda z_s
        sec
        sbc #1
        sta z_d
        lda z_s+1
        sbc #0
        eor #(>PA_SA) ^ (>PA_SB)        ; toinen puskuri
        sta z_d+1
        ldy #38
-       .for k := 0, k < 3, k += 1
        lda (z_s),y
        sta (z_d),y
        dey
        .next
        bpl -
        lda s_r
        clc
        adc #8 * (PR1 - PR0)
        tay
        lda (s_rec),y
        ldy #39
        sta (z_d),y
        inc s_r
        lda s_r
_loppu  cmp #3
        beq +
        jmp _rivi
+       inc s_chunk
        jmp _kdue

; nimi: SOKERIPALA Hillnerin otsikon fontilla 8 MC-spritenä letterboxin yläkaistalla
; Sokeripalan yllä. Kehyksissä NIMI_KOPIO + 8 b (vierityksen kevyet kehykset) lohko b puskurien A ($6000) ja B ($e000)
; yläkaistan bittikarttaan (tietueet 0-4 käytetty; ruutu ja värimuisti nollia, joten kaista pysyy mustana), lohkolla
; 0 VIC-rekisterit ja osoittimet. Joka kehys spriten i x = NIMI_X - min(z_t, T_PYSAHTYY) + 24 i: nimi on kiinni
; maailmassa (vierii talon mukana), sprite päällä vain x < NIMI_XMAX (ruudun x 376: PAL-kuvan oikean reunuksen
; takana, joten sprite ei välähdä näkyviin; ei kiedu vasempaan reunaan).
NIMI_SPR = $6000
NIMI_PTR = (NIMI_SPR & $3fff) / 64
nimi    lda z_t
        sec
        sbc #<NIMI_KOPIO
        tax
        lda z_t+1
        sbc #>NIMI_KOPIO
        bcc _out                        ; ennen kopiota spritet pois (nayta)
        bne _paikat
        cpx #64
        bcs _paikat
        txa
        and #7
        bne _paikat
        txa
        lsr
        lsr
        lsr
        tax                             ; lohko 0-7
        bne _kopio
        lda #$ff                        ; MC, ei suurennusta, spritet kuvan edessä
        sta $d01c
        lda #0
        sta $d017
        sta $d01d
        sta $d01b
        lda #NIMI_D025
        sta $d025
        lda #NIMI_D026
        sta $d026
        ldy #7
-       lda #NIMI_VARI
        sta $d027,y
        tya
        clc
        adc #NIMI_PTR
        sta PA_SA + $3f8,y
        sta PA_SB + $3f8,y
        dey
        bpl -                           ; (y: kellunta _paikat-osassa joka kehys)
_kopio  lda _slo,x
        sta _ld+1
        lda _shi,x
        sta _ld+2
        lda _dlo,x
        sta _sa+1
        sta _sb+1
        lda _dhi,x
        sta _sa+2
        ora #(>PA_BB) ^ (>NIMI_SPR)
        sta _sb+2
        ldy #63
_ld     lda $ffff,y
_sa     sta $ffff,y
_sb     sta $ffff,y
        dey
        bpl _ld
_paikat ldx z_t                         ; l = min(z_t, T_PYSAHTYY)
        ldy z_t+1
        cpx #<T_PYSAHTYY
        tya
        sbc #>T_PYSAHTYY
        bcc +
        ldx #<T_PYSAHTYY
        ldy #>T_PYSAHTYY
+       stx z_c
        sty z_c+1
        lda #<NIMI_X                    ; spriten 0 x
        sec
        sbc z_c
        sta z_c
        lda #>NIMI_X
        sbc z_c+1
        sta z_c+1
        lda #0
        sta z_d                         ; $d015
        sta z_d+1                       ; $d010
        ldx #0
_s      lda z_c+1
        beq _on
        cmp #2
        bcs _seur
        lda z_c
        cmp #NIMI_XMAX - 256
        bcs _seur
        lda z_d+1
        ora _bit,x
        sta z_d+1
_on     lda z_d
        ora _bit,x
        sta z_d
        txa
        asl
        tay
        lda z_c
        sta $d000,y
_seur   lda z_c
        clc
        adc #24
        sta z_c
        bcc +
        inc z_c+1
+       inx
        cpx #8
        bne _s
        lda z_d+1
        sta $d010
        lda z_d
        sta $d015
        lda z_t                         ; kellunta: kehyksestä NIMI_KELLU y = nimi_bob[z_t - NIMI_KELLU], kaikki
        sec                             ; samassa y:ssä (myöhästyneen lehden aikana viimeinen)
        sbc #<NIMI_KELLU
        tax
        lda z_t+1
        sbc #>NIMI_KELLU
        bcc _y0
        bne _yn
        cpx #T_LEHTI - NIMI_KELLU
        bcc +
_yn     ldx #T_LEHTI - NIMI_KELLU - 1
+       lda nimi_bob,x
        bne _y                          ; (y > 0)
_y0     lda #NIMI_Y
_y      ldy #14
-       sta $d001,y
        dey
        dey
        bpl -
_out    rts
_bit    .byte 1, 2, 4, 8, 16, 32, 64, 128
_slo    .byte <(nimi_spr + 64 * range(8))
_shi    .byte >(nimi_spr + 64 * range(8))
_dlo    .byte <(NIMI_SPR + 64 * range(8))
_dhi    .byte >(NIMI_SPR + 64 * range(8))
        .cerror ((NIMI_SPR ^ PA_BB) & $3fff) != 0, "nimen spritet samassa kohdassa molemmissa pankeissa"

; hyppy: kuva hyppii iskun tahdissa, alempana
; N = hyppy_fld[z_t - HYPPY_ALKU] riviä (0 = ylhäällä, laskeutuu iskulle). Ei FLD-silmukkaa (panoraaman
; kopiokehyksessä ei ole sille aikaa): kaksi YSCROLL-kirjoitusta mustassa letterboxissa siirtävät seuraavan badlinen
; a <= HYPPY_A ja b = N - a riviä myöhemmäksi. hop1 riveillä 57-58 (rivi 0 alkoi 51, seuraava 59 + a: Y = (3 + a) &
; 7, kirjoitusrivi ei ole badline vanhalla eikä uudella arvolla), hop2 riveillä 73 + a .. 74 + a (rivi 3 alkaa
; 75 + a + b). Välissä VIC on tyhjäkäynnillä, joka on bittikartassa musta. Rivin 250 IRQ palauttaa $3b:n. Asetetaan
; kehyksen alussa, koska panoraaman kopiokehys päättyy vasta kuvan aikana.
HOP1_LINE = 57
hyppy   lda z_t
        sec
        sbc #<HYPPY_ALKU
        tax
        lda z_t+1
        sbc #>HYPPY_ALKU
        bcc _out
        bne _yli
        cpx #T_LEHTI - HYPPY_ALKU
        bcc +
_yli    ldx #T_LEHTI - HYPPY_ALKU - 1  ; myöhästynyt lehti: viimeinen korkeus
+       lda hyppy_fld,x
        beq _out
        cmp #HYPPY_A + 1
        bcc +
        lda #HYPPY_A
+       sta z_ha
        eor #$ff
        sec
        adc hyppy_fld,x
        sta z_hb                        ; b = N - a
        lda #<hop1                      ; (rivin 250 IRQ on jo ohi)
        sta $fffe
        lda #>hop1
        sta $ffff
        lda #HOP1_LINE
        sta $d012
_out    rts

hop1    pha
        asl $d019
        lda z_ha
        clc
        adc #3
        and #7
        ora #$38
        sta $d011
        lda z_hb
        beq hop_pois
        lda z_ha
        clc
        adc #73
        sta $d012
        lda #<hop2
        sta $fffe
        lda #>hop2
        sta $ffff
        pla
        rti

hop2    pha
        asl $d019
        lda z_ha
        clc
        adc z_hb
        adc #3
        and #7
        ora #$38
        sta $d011
hop_pois lda trak_v                     ; puskutraktori tässä kehyksessä: sen IRQ seuraavaksi
        beq +
        lda #<trak_irq
        sta $fffe
        lda #>trak_irq
        sta $ffff
        lda #TRAK_LINE
        sta $d012
        pla
        rti
+       lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        lda #IRQ_LINE
        sta $d012
        pla
        rti

; kiire: rivin 250 IRQ, kun edellisen kehyksen valmistelu (kopiopala) on vielä kesken. Vierityksen kopio- ja
; kevyissä kehyksissä tehdään kuvan ajoituskriittiset: hienovieritys, hyppy ja nimi (keskeytetyn kopion z_t, z_c ja
; z_d talteen); kopio jatkuu IRQ:n jälkeen, ja seuraava kehys kuroo jääneet palat kiinni (_kdue). Vaihtokehys jää
; seuraavaan kehykseen (pano: ikkuna l / 8).
kiire   lda DFRAME
        sec
        sbc #<(T_ALKU - 2)
        sta kz_l
        lda DFRAME+1
        sbc #>(T_ALKU - 2)
        bcc _x                          ; alku
        sta kz_l+1
        cmp #>VIER                      ; l > VIER: pysähdys
        bcc +
        bne _x
        lda kz_l
        cmp #<VIER + 1
        bcs _x
+       lda kz_l
        and #7
        beq _x                          ; vaihtokehys (tai alku l = 0)
        eor #7
        ora #$10
        sta $d016
        lda z_t                         ; keskeytetyn kehyksen z_t, z_d ja z_c talteen (nimi ja hyppy käyttävät)
        sta kz_zp
        lda z_t+1
        sta kz_zp+1
        ldx #3
-       lda z_d,x
        sta kz_zp+2,x
        dex
        bpl -
        lda DFRAME
        clc
        adc #1
        sta z_t
        lda DFRAME+1
        adc #0
        sta z_t+1
        lda #0
        sta z_ha
        jsr hyppy
        jsr nimi
        lda kz_zp
        sta z_t
        lda kz_zp+1
        sta z_t+1
        ldx #3
-       lda kz_zp+2,x
        sta z_d,x
        dex
        bpl -
_x      rts

; trak_ryomi: puskutraktori jarrutuksen jälkeen (trak SPP3:ssa kutsuu): ryömintä W = TRAK_WC + s / 2 (s = dt -
; TRAK_D1) TRAK_CN kehystä Sokeripalan eteen, sitten seis W = TRAK_WS ja tr_s = 1 (tyhjäkäynti)
trak_ryomi
        lda DFRAME
        sec
        sbc #<(TRAK_T0 - 1 + TRAK_D1)
        tax
        lda DFRAME+1
        sbc #>(TRAK_T0 - 1 + TRAK_D1)
        bne _seis
        cpx #TRAK_CN
        bcs _seis
        txa
        lsr
        clc
        adc #<TRAK_WC
        sta tr_w
        lda #>TRAK_WC
        adc #0
        sta tr_w+1
        rts
_seis   inc tr_s
        lda #<TRAK_WS
        sta tr_w
        lda #>TRAK_WS
        sta tr_w+1
        rts

pa_dd00 .byte 2, 0
pa_d018 .byte D018_PA, D018_PB

; nousu: alun kehys z_t: tietueet (kehys, solu lo, solu hi, ruutu, värimuisti) kehykseen asti, pääte $ff
nousu
        lda #$17
        sta $d016
        ldy #0
_i      lda (z_iv),y
        cmp z_t
        beq +
        bcs _io
+       iny
        lda (z_iv),y
        sta _is+1
        sta _ic+1
        iny
        lda (z_iv),y
        tax
        clc
        adc #>PA_SA
        sta _is+2
        txa
        adc #$d8
        sta _ic+2
        iny
        lda (z_iv),y
_is     sta $ffff
        iny
        lda (z_iv),y
_ic     sta $ffff
        lda z_iv
        clc
        adc #5
        sta z_iv
        bcc +
        inc z_iv+1
+       ldy #0
        beq _i
_io     rts

; k312: (z_s) -> (z_d), 312 tavua
; k312: 312 tavua z_s -> z_d. Itseään muokkaava abs,y (2 sykliä tavulta vähemmän kuin (zp),y: noin 500 sykliä
; rivillä, 1 500 kopiokehyksessä), jotta nimen spritet mahtuvat panoraaman kehykseen.
k312    lda z_s
        .for i := 0, i < 4, i += 1
        sta _l0 + 7 * i + 1
        sta _l1 + 7 * i + 1
        .next
        lda z_d
        .for i := 0, i < 4, i += 1
        sta _l0 + 7 * i + 4
        sta _l1 + 7 * i + 4
        .next
        lda z_s+1
        .for i := 0, i < 4, i += 1
        sta _l0 + 7 * i + 2
        .next
        clc
        adc #1
        .for i := 0, i < 4, i += 1
        sta _l1 + 7 * i + 2
        .next
        lda z_d+1
        .for i := 0, i < 4, i += 1
        sta _l0 + 7 * i + 5
        .next
        clc
        adc #1
        .for i := 0, i < 4, i += 1
        sta _l1 + 7 * i + 5
        .next
        ldy #0
_l0
        .for i := 0, i < 4, i += 1
        lda $ffff,y
        sta $ffff,y
        iny
        .next
        bne _l0
        ldy #55                         ; häntä 56 tavua (4 x 14)
_l1
        .for i := 0, i < 4, i += 1
        lda $ffff,y
        sta $ffff,y
        dey
        .next
        bpl _l1
        inc z_s+1                       ; lopuksi z_s ja z_d + 256 (kutsuja jatkaa z_d + 312:sta)
        inc z_d+1
        rts

rivi40_lo .byte <(40 * range(25))
rivi40_hi .byte >(40 * range(25))

; ---------------------------------------------------------------- taulu «JATKUU...»: ajonaikainen koodi pankissa 1
taulu   jmp tk_alku                     ; (ydin vapaa taulun aikana: seuraavan osan esilataus $1a00-)

; ---------------------------------------------------------------- sivu: terävä Länsi-Uusimaa, kynä
sivu
        ldx z_l                         ; kamera kulkee sivua alas (kuva nousee FLD:llä)
        cpx #T_PELI - T_SIVU
        bcc +
        ldx #T_PELI - T_SIVU - 1
+       lda fld_sivu,x
        sta z_fld
        lda #$3b
        sta $d011
        lda z_sivu
        cmp #2
        beq ajo
        inc z_sivu                      ; ensimmäinen kehys: VIC-pankki 1, hires-bittikartta
        lda #2
        sta $dd00
        lda #D018_P1
        sta $d018
        lda #$3b
        sta $d011
        lda #$08
        sta $d016
        lda #<SIVU_EV
        sta z_te
        lda #>SIVU_EV
        sta z_te+1
        ; (kehys 0: ei tapahtumia)

; ---------------------------------------------------------------- tapahtumat (kehys, osoite, arvo): z_te, z_l
ajo
        ldy #0
_ev     lda (z_te),y
        cmp z_l
        beq +
        bcs _out                        ; tapahtuma myöhemmin (pääte $ff)
+       iny
        lda (z_te),y
        sta _st+1
        iny
        lda (z_te),y
        sta _st+2
        iny
        lda (z_te),y
_st     sta $ffff
        lda z_te
        clc
        adc #4
        sta z_te
        bcc +
        inc z_te+1
+       ldy #0
        beq _ev
_out    rts

; ---------------------------------------------------------------- pyörähdys
spin
        lda z_lehti
        cmp #2
        beq _nayta
        inc z_lehti
        lda #1                          ; ensimmäinen kehys: VIC-pankki 2, MC-merkkitila, sitten värimuisti
        sta $dd00                       ; (%11 valkoinen, MC) sivu kerrallaan ylhäältä alas säteen edellä
        lda #D018_S
        sta $d018
        lda #$1b
        sta $d011
        lda #$18
        sta $d016
        lda #0
        sta $d021
        sta $d015
        lda #SPIN_D022                  ; MC-värit lehti.py:stä (musta/tummanharmaa, vaaleanharmaa/valkoinen)
        sta $d022
        lda #SPIN_D023
        sta $d023
        ldx #0
        lda #9
-       sta $d800,x
        inx
        bne -
-       sta $d900,x
        inx
        bne -
-       sta $da00,x
        inx
        bne -
-       sta $dae8,x
        inx
        bne -
        lda #1                          ; seuraavaksi näkyviin asento 1 (piirretty sp_lehtissä)
        sta q_valmis
        rts
_nayta  lda q_valmis                    ; näkyviin viimeksi valmistunut ruutu
        beq +
        lda #$10
+       ora #D018_S
        sta $d018
        lda z_l                         ; seuraava asento (kello) toiseen ruutuun
        clc
        adc #1
        cmp #T_SIVU - T_LEHTI
        bcs +
        tax
        lda q_valmis
        eor #1
        sta q_buf
        txa
        jsr spin_render
        lda q_buf
        sta q_valmis
+       rts

; spin_render: A = asento, q_buf = ruutu. Sarakkeet 0-39: tyhjä, vasen reunasarake (reunus, kapea versio),
; sisäsarakkeet (s ja korkeus askeltaen, u = s * hr / h log/exp-tauluilla, profiili kartasta), oikea reunasarake.
spin_render
        pha                             ; suorat kopiot (q_or = 0) tämän ruudun rutiineihin: hyppy ilman taulua
        lda q_buf
        asl
        asl
        tay
        lda kopiot_lo,y
        sta v13
        lda kopiot_hi,y
        sta v13+1
        lda kopiot_lo+1,y
        sta v19
        lda kopiot_hi+1,y
        sta v19+1
        pla
        sta q_p                         ; asennon osoite = SPIN_POSE + 5 A
        lda #0
        sta q_p+1
        lda q_p
        asl
        rol q_p+1
        asl
        rol q_p+1
        adc q_p
        sta q_p
        lda q_p+1
        adc #>SPIN_POSE
        sta q_p+1
        lda q_p
        clc
        adc #<SPIN_POSE
        sta q_p
        bcc +
        inc q_p+1
+       ldy #4
-       lda (q_p),y
        sta q_xl,y
        dey
        bpl -
        lda q_back
        beq +
        lda #1                          ; takasivun kartta (sp_kartta + 256)
+       clc
        adc #>sp_kartta
        sta _kartta+2
        ldx #0                          ; X = sarake
        lda q_xr
        sec
        sbc q_xl
        sta q_w
        bne +
        jmp _tyhjat                     ; syrjittäin: ei sivua
+       tay
        lda sp_rwl,y
        sta q_rw
        lda sp_rwh,y
        sta q_rw+1
        jsr _dh
        ldy q_hr                        ; exp-pohja: sp_exp + log hr
        lda sp_log,y
        clc
        adc #<sp_exp
        sta q_eb
        lda #>sp_exp
        adc #0
        sta q_eb+1
        lda q_xr
        sec
        sbc #1
        lsr
        lsr
        sta q_cr
        sta q_ce
        lda q_xr
        and #3
        beq +
        dec q_ce                        ; oikea reunasarake erikseen (myös, kun se on vasemman reunan sarake)
+       lda q_xl                        ; tyhjät sarakkeet vasemmalla
        lsr
        lsr
        sta q_k
-       cpx q_k
        bcs +
        jsr _tyhja
        inx
        bne -
+       lda q_xl
        and #3
        beq _sis
        eor #3                          ; vasen reunasarake: peittää 4 - (xl & 3) MC-px, versio 1-3
        clc
        adc #1
        asl
        asl
        asl
        asl
        sta q_or
        lda q_hl
        jsr _reuna
        inx
_sis    cpx q_ce                        ; sisäsarakkeet X..q_ce
        beq +
        bcc +
        jmp _oik
+       txa                             ; k = 4 X + 2 - xl: s = k (rw / 4), h = hl + k (dh / 4)
        asl
        asl
        ora #2
        sec
        sbc q_xl
        sta q_k
        lda q_rw+1
        sta q_m+1
        lda q_rw
        lsr q_m+1
        ror
        lsr q_m+1
        ror
        sta q_m
        lda #0
        sta q_s
        sta q_s+1
        sta q_h
        lda q_hl
        sta q_h+1
        ldy q_k
-       lda q_s
        clc
        adc q_m
        sta q_s
        lda q_s+1
        adc q_m+1
        sta q_s+1
        dey
        bne -
        lda q_dh+1                      ; dh / 4 etumerkillisenä
        cmp #$80
        ror
        sta q_m+1
        lda q_dh
        ror
        sta q_m
        lda q_m+1
        cmp #$80
        ror q_m+1
        ror q_m
        ldy q_k
-       lda q_h
        clc
        adc q_m
        sta q_h
        lda q_h+1
        adc q_m+1
        sta q_h+1
        dey
        bne -
_sloop  ldy q_s+1                       ; u = exp(log s + log hr - log h)
        lda sp_log,y
        clc
        adc q_eb
        sta q_e
        lda q_eb+1
        adc #0
        sta q_e+1
        lda q_h+1
        cmp #2
        bcs +
        lda #2
+       cmp #HMAX + 1
        bcc +
        lda #HMAX
+       sta q_k                         ; h8
        tay
        lda #0
        sec
        sbc sp_log,y
        tay
        lda (q_e),y
        tay
_kartta lda sp_kartta,y
        tay                             ; Y = profiili
        lda #0
        sta q_or
        lda q_k
        lsr
        sec
        sbc #1                          ; korkeusindeksi i = h8 / 2 - 1 (h8 >= 2)
        cmp #SPIN_JAKO
        bcc _i13
        sbc #SPIN_JAKO                  ; 19 riviä: avain (N19 p + i - JAKO, $ff)
        clc
        adc sp_p19,y
        sta q_sp
        lda #$ff
        sta q_sp+1
        sec
        bcs _kop
_i13    sta q_k                         ; 13 riviä: q_sp = profiili + 13 i, C = 0
        lda sp_plo,y
        sta q_sp
        lda sp_phi,y
        sta q_sp+1
        ldy q_k
        lda q_sp
        adc sp_olo,y
        sta q_sp
        lda q_sp+1
        adc sp_ohi,y
        sta q_sp+1
        clc
_kop    jsr _kopio
        lda q_s                         ; s += rw (kyllästyen), h += dh
        clc
        adc q_rw
        sta q_s
        lda q_s+1
        adc q_rw+1
        bcc +
        lda #$ff
+       sta q_s+1
        lda q_h
        clc
        adc q_dh
        sta q_h
        lda q_h+1
        adc q_dh+1
        sta q_h+1
        inx
        cpx q_ce
        beq +
        bcs _oik
+       jmp _sloop
_oik    cpx q_cr                        ; oikea reunasarake: peittää xr & 3 MC-px, versio 4-6
        bne _tyhjat
        lda q_xr
        and #3
        beq _tyhjat
        clc
        adc #3
        asl
        asl
        asl
        asl
        sta q_or
        lda q_hr
        jsr _reuna
        inx
_tyhjat cpx #40
        bcs +
        jsr _tyhja
        inx
        bne _tyhjat
+       rts

_reuna  lsr                             ; A = korkeus: reunuksen sarake, versio q_or
        sec
        sbc #1
        cmp #SPIN_JAKO
        bcc _r13
        sbc #(SPIN_JAKO - SPIN_N19 * REUNUS) & $ff      ; 19 riviä: avain (N19 REUNUS + i - JAKO, $ff), C = 1
        sta q_sp
        lda #$ff
        sta q_sp+1
        sec
        bcs _kopio
_r13    tay
        lda sp_plo + REUNUS
        adc sp_olo,y
        sta q_sp
        lda sp_phi + REUNUS
        adc sp_ohi,y
        sta q_sp+1
        clc
        ; (jatkuu _kopio:on, C = 0: 13 riviä)
_kopio  php                             ; sarake ennallaan tässä ruudussa (sama data ja versio): ei kopiota
        ldy q_buf
        txa
        clc
        adc ruutu40,y
        tay
        lda q_sp
        cmp avain_lo,y
        bne +
        lda q_sp+1
        cmp avain_hi,y
        bne +
        lda q_or
        cmp avain_or,y
        bne +
        plp
        rts
+       lda q_sp
        sta avain_lo,y
        lda q_sp+1
        sta avain_hi,y
        lda q_or
        sta avain_or,y
        plp
        lda q_or                        ; C = 0: 13 riviä, C = 1: 19; q_or = 0: suora kopio, muuten ora
        bne _ora
        bcs +
        jmp (v13)
+       jmp (v19)
_ora    lda #0
        rol
        ldy q_or
        beq +
        ora #2
+       ldy q_buf
        beq +
        ora #4
+       tay
        lda kopiot_lo,y
        sta _jsr+1
        lda kopiot_hi,y
        sta _jsr+2
_jsr    jmp $ffff

_tyhja  ldy q_buf                       ; X = sarake: tyhjä (avain 0)
        txa
        clc
        adc ruutu40,y
        tay
        lda avain_hi,y
        beq +
        lda #0
        sta avain_hi,y
        lda q_buf
        bne _tb
        jmp tyhja_a
_tb     jmp tyhja_b
+       rts

_dh     lda q_hr                        ; dh = (hr - hl) rw / 256, etumerkillinen 8.8
        sec
        sbc q_hl
        php
        bcs +
        eor #$ff
        adc #1
+       sta q_k                         ; |hr - hl| x rw (8 x 16 -> 24), tulos tavut 1-2
        lda #0
        sta q_dh
        sta q_dh+1
        sta q_m
        ldy #8
-       asl q_m
        rol q_dh
        rol q_dh+1
        asl q_k
        bcc +
        lda q_m
        clc
        adc q_rw
        sta q_m
        lda q_dh
        adc q_rw+1
        sta q_dh
        bcc +
        inc q_dh+1
+       dey
        bne -
        plp
        bcs +
        lda #0
        sec
        sbc q_dh
        sta q_dh
        lda #0
        sbc q_dh+1
        sta q_dh+1
+       rts

; sarakkeen kopiot: X = sarake; 13 riviä (q_sp) = merkit (SPIN_R13-, muut rivit SPIN_R19-:sta tyhjiksi) tai 19
; (SPIN_R19-) taulusta SPIN_T19 indeksillä q_sp (lda abs,y: 9 sykliä riviltä, joten täysikokoinen sivu
; mahtuu kehykseen), ora q_or. Rivejä 0 - SPIN_R19-1 ei kirjoiteta koskaan (sivu enintään 152 px, alareuna rivillä 24).
kopio   .macro scr, n, orv
        .if \n == 13
        ldy #0
        .for r := SPIN_R13, r < SPIN_R13 + 13, r += 1
        lda (q_sp),y
        .if \orv
        ora q_or
        .endif
        sta \scr + 40 * r,x
        iny
        .next
        lda #0
        .for r := SPIN_R19, r < SPIN_R13, r += 1
        sta \scr + 40 * r,x
        .next
        .for r := SPIN_R13 + 13, r < SPIN_R19 + 19, r += 1
        sta \scr + 40 * r,x
        .next
        .else
        ldy q_sp
        .for j := 0, j < 19, j += 1
        lda SPIN_T19 + j * 10 * SPIN_N19,y
        .if \orv
        ora q_or
        .endif
        sta \scr + 40 * (SPIN_R19 + j),x
        .next
        .endif
        rts
        .endm
tyhja   .macro scr
        lda #0
        .for r := SPIN_R19, r < SPIN_R19 + 19, r += 1
        sta \scr + 40 * r,x
        .next
        rts
        .endm
k13a    #kopio SPIN_SCR, 13, 0
k25a    #kopio SPIN_SCR, 19, 0
k13ao   #kopio SPIN_SCR, 13, 1
k25ao   #kopio SPIN_SCR, 19, 1
k13b    #kopio SPIN_SCR + $400, 13, 0
k25b    #kopio SPIN_SCR + $400, 19, 0
k13bo   #kopio SPIN_SCR + $400, 13, 1
k25bo   #kopio SPIN_SCR + $400, 19, 1
tyhja_a #tyhja SPIN_SCR
tyhja_b #tyhja SPIN_SCR + $400
ruutu40 .byte 0, 40
v13     .word 0                         ; spin_render: tämän ruudun suorat kopiot (13 ja 19 riviä)
v19     .word 0
        .cerror (<v13) == $ff || (<v19) == $ff, "jmp (v) sivun rajalla"
avain_lo .fill 80               ; sarakkeen data ruuduittain: osoite (ylätavu 0 = tyhjä) ja versio
avain_hi .fill 80
avain_or .fill 80
kopiot_lo .byte <k13a, <k25a, <k13ao, <k25ao, <k13b, <k25b, <k13bo, <k25bo
kopiot_hi .byte >k13a, >k25a, >k13ao, >k25ao, >k13b, >k25b, >k13bo, >k25bo

; ---------------------------------------------------------------- peli: VIC, spritet ja solukopiot
peli
        lda z_l
        ora z_l+1
        bne _sprt
        lda #1                          ; ensimmäinen kehys: VIC-pankki 2, hires-bittikartta, spritet
        sta $dd00
        lda #D018_P2
        sta $d018
        lda #$3b
        sta $d011
        lda #$08
        sta $d016
        lda #0
        sta $d01c
        sta $d017
        sta $d01d
        sta $d01b
        sta $d027                       ; kaupunginjohtajan reuna musta, täyttö valkoinen, timantti keltainen
        sta $d02b                       ; ja musta (muurahaisviiva)
        sta $d02c
        lda #1
        sta $d028
        lda #7
        sta $d029
        sta $d02a
        lda #SPRBLK2
        sta PELI_SCR+$3f8
        lda #SPRBLK2+1
        sta PELI_SCR+$3f9
        lda #$c0                        ; kaksi uutiskopteria: spritet 6-7 kaksinkertaisina mustina siluetteina
        sta $d017
        sta $d01d
        lda #0
        sta $d02d
        sta $d02e
        lda #$ff
        sta $d015
_sprt   ldx z_h                         ; kopterit kiertävät Sokeripalaa: paikat taulusta, roottori kahdessa vaiheessa
        lda HELI,x
        sta $d00c
        lda HELI + KIERROS,x
        sta $d00d
        lda HELI + 2 * KIERROS,x
        sta $d00e
        lda HELI + 3 * KIERROS,x
        sta $d00f
        inx
        cpx #KIERROS
        bcc +
        ldx #0
+       stx z_h
        lda z_l
        and #1
        clc
        adc #SPRBLK2+34
        sta PELI_SCR+$3fe
        eor #1
        sta PELI_SCR+$3ff
        ldy #0                          ; spritetaulu: kaupunginjohtajan x, y, timantin x, y, x:n yläbitit
        lda (z_ps),y
        sta $d000
        sta $d002
        iny
        lda (z_ps),y
        sta $d001
        sta $d003
        iny
        lda (z_ps),y
        sta $d004
        sta $d008
        clc
        adc #24
        sta $d006
        sta $d00a
        iny
        lda (z_ps),y
        sta $d005
        sta $d007
        sta $d009
        sta $d00b
        iny
        lda (z_ps),y
        sta $d010
        lda z_ps
        clc
        adc #5
        sta z_ps
        bcc +
        inc z_ps+1
+       lda z_l                         ; timantin viiva kiertää: vaihe kehyksittäin
        and #7
        asl
        adc #SPRBLK2+2
        sta PELI_SCR+$3fa
        adc #1
        sta PELI_SCR+$3fb
        adc #15
        sta PELI_SCR+$3fc
        adc #1
        sta PELI_SCR+$3fd
_ev     ldy #1                          ; solukopiot, joiden kehys <= z_l (pääte $ffff)
        lda (z_pe),y
        cmp z_l+1
        bcc _do
        bne _out
        dey
        lda (z_pe),y
        cmp z_l
        beq _do
        bcs _out
_do     ldy #2
        lda (z_pe),y
        sta z_d
        iny
        lda (z_pe),y
        sta z_d+1
        iny
        lda (z_pe),y
        sta z_c
        iny
        lda (z_pe),y
        sta z_c+1
        iny
        lda (z_pe),y
        sta z_s
        iny
        lda (z_pe),y
        sta z_s+1
        ldy #8
        lda (z_s),y
        ldy #0
        sta (z_c),y
        ldy #7
-       lda (z_s),y
        sta (z_d),y
        dey
        bpl -
        lda z_pe
        clc
        adc #8
        sta z_pe
        bcc _ev
        inc z_pe+1
        bne _ev
_out    rts

        .include "sp_data.asm"
pano_col .binary "pano_col.bin"         ; panoraaman ikkunan 0 värimuisti (sp_init kopioi $d800:aan)
nimi_spr .binary "nimi_spr.bin"         ; SOKERIPALA 8 MC-spritenä (nimi kopioi pankkeihin 1 ja 3)
trak_on .byte 0                         ; 1 = SPP3 ja SPT ladattu (sp_trak) ja traktori kesken
trak_v  .byte 0                         ; 1 = traktori tässä kehyksessä (hop_pois ketjuttaa trak_irq:hin)
kz_due  .byte 0                         ; _kopio: palat valmiina tähän asti
kz_l    .word 0                         ; kiire: vierityskohta
kz_zp   .fill 6                         ; kiire: keskeytetyn kehyksen z_t, z_d, z_c
sp0_end
        .cerror * > $4000, "ydin ylittää $4000"

; ---------------------------------------------------------------- SP4K $4800-: taulun ajonaikainen koodi pankissa 1
; Taulun aikana ydintä ($1a00-) ei käytetä: ytimen IRQ hyppää taulun ensimmäisessä kehyksessä tk_alkuun, joka
; vaihtaa IRQ-vektorin tk_irq:hin. Pankissa 1 taulun spritet $4000, tämä koodi $4800, ruutu $5c00, bittikartta $6000.
        * = TK
; sp_taulu: pääsäikeessä, kun SP4/SP4K on ladattu (peli näkyy pankissa 2): taulun ruutu ja spritet pankkiin 1
sp_taulu
        jsr taulu_alku
        ; kiillon solut lävistäjäluokittain (rivi + sarake) & 31 (taulun 3 pidempi teksti ei mahdu
        ; solukohtaiseen koodiin): ensin luokat väliaikaisiin tauluihin (KD, TD), sitten listat luokka kerrallaan,
        ; tekstin solut järjestysnumeron mukaan nousevina (valottunut alkuosa tz_lo)
        ldx #TAULU_NK - 1
-       ldy taulu_k_hi,x
        lda taulu_k_lo,x
        jsr _diag
        sta KD,x
        dex
        cpx #$ff
        bne -
        ldx #TAULU_NT - 1
-       ldy taulu_t_hi,x
        lda taulu_t_lo,x
        jsr _diag
        sta TD,x
        dex
        cpx #$ff
        bne -
        lda #0
        sta g_c
        sta g_nk
        sta g_nt
_luokka ldx g_c
        lda g_nk
        sta kf_s,x
        lda g_nt
        sta kt_s,x
        cpx #32
        beq _valmis
        ldx #0
-       lda KD,x
        cmp g_c
        bne +
        ldy g_nk
        lda taulu_k_lo,x
        sta kf_lo,y
        lda taulu_k_hi,x
        ora #>TAULU_SCREEN
        sta kf_hi,y
        inc g_nk
+       inx
        cpx #TAULU_NK
        bne -
        ldx #0
-       lda TD,x
        cmp g_c
        bne +
        ldy g_nt
        lda taulu_t_lo,x
        sta kt_lo,y
        lda taulu_t_hi,x
        ora #>TAULU_SCREEN
        sta kt_hi,y
        txa
        sta kt_i,y
        inc g_nt
+       inx
        cpx #TAULU_NT
        bne -
        inc g_c
        bne _luokka
_valmis lda #1                          ; ensimmäinen kiiltokehys kirjoittaa koko juovan
        sta g_koko
        rts
_diag   sta g_lo                        ; A/Y = solu (0-999) -> A = (rivi + sarake) & 31
        sty g_hi
        lda #0
        sta g_r
-       lda g_lo
        sec
        sbc #40
        tay
        lda g_hi
        sbc #0
        bcc +
        sta g_hi
        sty g_lo
        inc g_r
        bne -
+       lda g_lo
        clc
        adc g_r
        and #31
        rts
g_lo    .byte 0
g_hi    .byte 0
g_r     .byte 0
g_c     .byte 0
g_nk    .byte 0
g_nt    .byte 0

; tk_alku: ytimen IRQ:sta taulun ensimmäisessä kehyksessä: VIC-pankki 1, taulun ruutu, oma IRQ
tk_alku
        jsr taulu_vic
        lda #0
        sta $d010
        lda #2
        sta $dd00
        lda #D018_P1
        sta $d018
        lda #<tk_irq
        sta $fffe
        lda #>tk_irq
        sta $ffff
        jmp tk_kehys

tk_irq
        pha
        txa
        pha
        tya
        pha
        lda $01
        pha
        lda #$35
        sta $01
        asl $d019
        jsr FRAME_HOOK
        jsr tk_kehys
        pla
        sta $01
        pla
        tay
        pla
        tax
        pla
        rti

; tk_kehys: taulun kehys tk_l = DFRAME + 1 - T_TAULU: taulumoduuli ja kiilto
tk_kehys
        lda DFRAME
        clc
        adc #1
        tax
        lda DFRAME+1
        adc #0
        tay
        txa
        sec
        sbc #<T_TAULU
        sta tk_l
        tya
        sbc #>T_TAULU
        bne _ohi
        lda tk_l
        cmp #TAULU_KESTO
        bcs _ohi
        jsr taulu_kehys
        ; kiilto (koristeet elävät): leveä harmaa juova kulkee vinosti valmiiden solujen yli (kehys ja jo
        ; valottunut teksti), ei valottuessa, välkkeessä eikä häivytyksessä. Luokan r arvo = g_kiilto[(r - tk_l) & 31];
        ; kehyksessä vaihtuu vain neljän luokan arvo (indeksit 31, 1, 9, 11). Koko juova (indeksit 0-11 ja 31), kun
        ; edellinen kehys ei kiiltänyt (taulumoduuli kirjoitti solut tavalliseksi) tai tekstiä valottui lisää.
        lda tk_l
        cmp #8
        bcc _tauko
        cmp #TAULU_KESTO - 8
        bcs _tauko
        lda tz_flk
        bne _tauko
        lda tz_lo
        cmp g_lo_ed
        sta g_lo_ed
        bne _koko
        lda g_koko
        bne _koko
        ldy #3
-       ldx _vaihtuu,y
        jsr _luokka
        dey
        bpl -
        rts
_koko   lda #0
        sta g_koko
        ldx #31
        jsr _luokka
        ldx #11
-       jsr _luokka
        dex
        bpl -
        rts
_tauko  lda #1
        sta g_koko
_ohi    rts
_vaihtuu .byte 31, 1, 9, 11

; _luokka: X = juovan indeksi i (säilyy, samoin Y): luokan (i + tk_l) & 31 solut arvoon g_kiilto[i]
_luokka stx g_i
        sty g_y
        lda g_kiilto,x
        sta _fv+1
        sta _tv+1
        txa
        clc
        adc tk_l
        and #31
        tax
        lda kf_s+1,x
        sta _fe+1
        lda kt_s+1,x
        sta _te+1
        lda kt_s,x
        sta g_t0
        ldy kf_s,x
        cpy _fe+1
        beq _teksti
-       lda kf_lo,y
        sta _fs+1
        lda kf_hi,y
        sta _fs+2
_fv     lda #0
_fs     sta $ffff
        iny
_fe     cpy #0
        bne -
_teksti ldy g_t0
        cpy _te+1
        beq _pois
-       lda kt_i,y
        cmp tz_lo
        bcs _pois
        lda kt_lo,y
        sta _ts+1
        lda kt_hi,y
        sta _ts+2
_tv     lda #0
_ts     sta $ffff
        iny
_te     cpy #0
        bne -
_pois   ldx g_i
        ldy g_y
        rts
g_i     .byte 0
g_y     .byte 0
g_t0    .byte 0
g_koko  .byte 0
g_lo_ed .byte 0
g_kiilto .byte $f0, $f0, $c0, $c0, $c0, $c0, $c0, $c0, $c0, $c0, $f0, $f0      ; leveä juova 32 kehyksen välein
        .fill 20, $10
        .byte $f0, $f0, $c0, $c0, $c0, $c0, $c0, $c0, $c0, $c0, $f0, $f0      ; toisto: indeksi (-tk_l & 31) + r
        .fill 20, $10


        .include "../../lib/taulu.asm"
        .include "taulu_jatkuu_data.asm"
sp4k_end
        .virtual sp4k_end               ; sp_taulu kirjoittaa (ei tiedostossa)
kf_s    .fill 33                        ; kehyksen solujen lista luokittain: alku (kf_s[32] = loppu)
kt_s    .fill 33                        ; tekstin solut samoin
kf_lo   .fill TAULU_NK
kf_hi   .fill TAULU_NK
kt_lo   .fill TAULU_NT
kt_hi   .fill TAULU_NT
kt_i    .fill TAULU_NT                  ; tekstin solun järjestysnumero (nouseva luokan sisällä)
g_end
        .endv
KD = SP4K_VARA                          ; sp_taulu: solujen luokat ennen listoja ($5600-, vapaa pelin aikana)
TD = KD + TAULU_NK
        .cerror TD + TAULU_NT > TAULU_SCREEN, "KD ja TD"
        .cerror g_end > SP4K_VARA, "kiillon listat ylittävät $55ff (part-sokeripala.json vapaana_kesken $5600-)"
        .cerror * > TAULU_SCREEN, "taulun koodi ylittää ruudun $5c00"

        * = SPIN_SCR
        .fill $800, 0
        .binary "spin_cs.bin"
        .for k := 0, k < 10, k += 1
        .binary format("spin_p%d.bin", k)
        .next
        .cerror * != SPIN_T19, "T19 profiilien perässä"
        .binary "spin_t19.bin"
        .cerror * != SPIN_POSE, "asennot T19:n perässä"
        .binary "spin_pose.bin"
sp2a_end
        .cerror * > $c000, "SP2A"

; ---------------------------------------------------------------- SPP3:n häntä: puskutraktori
; Kaupunginjohtajan puskutraktori ajaa etualalla samaan suuntaan (build.py): Hillnerin purkajan kone 4 x 2
; MC-spritenä torin etualalla, ruudulla x = TRAK_X0 + 9/4 dt kehyksissä TRAK_T0 + dt (tausta vierii 1 px
; vasemmalle). Spritelohkot TRAK_A (pankki 1, SPP2) ja TRAK_B (pankki 3, SPT puskurin B letterboxissa), trak
; SPP3:ssa tietueiden perässä ja trak_irq SPT:ssä lohkojen perässä. Nimen spritet ovat yläkaistalla (rivit 51-77): rivin 250 IRQ palauttaa niiden rekisterit
; (trak), ja trak_irq rivillä TRAK_LINE asettaa samat 8 laitteistospriteä traktoriksi. Paikka, telavaihe ja
; pomppu lasketaan kehyksen numerosta (pudonnut kehys ei siirrä mitään).
        * = TRAK_KOODI
VIER = T_PYSAHTYY - T_ALKU + 1          ; vierityskohta pysähdyksessä
TRAK_LINE = 96                          ; nimen spritet loppuvat riville 77, traktori alkaa riviltä TRAK_Y - 1
TRAK_VARI = 7                           ; runko purkajan keltainen, %01 = 0 (Hillnerissä 9) ja %11 = 12 (concept/dozer.py)

sp_trak lda #1                          ; kohtaustaulu, kun SPP3 ja SPT on ladattu
        sta trak_on
        rts

; trak: rivin 250 IRQ:ssa (I = 1) ennen kehyksen valmistelua; dt = DFRAME + 1 - TRAK_T0. Sarakkeet: X = x + 24 c,
; päällä kun 0 <= X < 344 (muuten reunuksen takana, eikä spriten DMA vie kopiokehyksen syklejä)
trak    lda #0
        sta trak_v
        lda DFRAME
        sec
        sbc #<(TRAK_T0 - 1)
        tay                             ; dt (lo), tr_dh (hi)
        lda DFRAME+1
        sbc #>(TRAK_T0 - 1)
        bcc _x                          ; ennen traktoria
        sta tr_dh
        cmp #>(TRAK_N + 1)
        bcc +
        bne _loppu
        cpy #<(TRAK_N + 1)
        bcs _loppu
+       jsr trak_nimi                   ; nimen rekisterit takaisin (edellisen kehyksen trak_irq)
        lda tr_dh
        cmp #>TRAK_N
        bcc _tila
        bne _loppu
        cpy #<TRAK_N
        bcc _tila
_loppu  lda #0
        sta trak_on
_x      rts
_tila   ldx #0                          ; maailman paikka W (hires): ajo W0 + 13/4 dt, jarrutus taulusta, seis WS
        stx tr_s
        stx tr_w+1
        lda tr_dh
        bne _seis
        cpy #TRAK_D0
        bcc _aja
        cpy #TRAK_D0 + TRAK_DN
        bcs _seis
        tya
        sbc #TRAK_D0 - 1                ; (C = 0)
        tax
        lda trak_jarru,x
        clc
        adc #<TRAK_WD
        sta tr_w
        lda #>TRAK_WD
        adc #0
        sta tr_w+1
        jmp _l
_seis   jsr trak_ryomi                  ; ryömintä ja seis (ytimessä)
        jmp _l
_aja    sty tr_a
        tya
        asl
        rol tr_w+1
        sta tr_w
        tya
        lsr
        lsr
        clc
        adc tr_w
        bcc +
        inc tr_w+1
+       clc
        adc tr_a
        bcc +
        inc tr_w+1
+       clc
        adc #<TRAK_W0
        sta tr_w
        lda tr_w+1
        adc #>TRAK_W0
        sta tr_w+1
_l      lda DFRAME                      ; vierityskohta l = kehys - (T_ALKU - 1), enintään VIER (pysähdys)
        sec
        sbc #<(T_ALKU - 2)
        sta tr_a
        lda DFRAME+1
        sbc #>(T_ALKU - 2)
        cmp #>VIER
        bcc +
        bne _lmax
        ldx tr_a
        cpx #<VIER + 1
        bcc +
_lmax   lda #<VIER
        sta tr_a
        lda #>VIER
+       sta tr_b
        lda tr_w                        ; ruudulla x = W - l (maassa: liikkuu taustan mukana)
        sec
        sbc tr_a
        sta tr_x
        lda tr_w+1
        sbc tr_b
        tax
        lda #0
        sta tr_on
        sta tr_msb
        .for c := 0, c < 4, c += 1
        .block
        cpx #$80                        ; X < 0 tai X >= 344: pois (reunuksen takana, ei DMA:ta)
        bcs seur
        lda tr_x
        sta tr_xs + c
        cpx #1
        bcc on
        cmp #<344
        bcs seur
        lda #$11 << c
        ora tr_msb
        sta tr_msb
on      lda #$11 << c
        ora tr_on
        sta tr_on
seur
        .bend
        .if c < 3
        lda tr_x
        clc
        adc #24
        sta tr_x
        bcc +
        inx
+
        .endif
        .next
        lda tr_w+1                      ; a = W / 4 (< 256)
        lsr
        sta tr_b
        lda tr_w
        ror
        lsr tr_b
        ror
        sta tr_a
        lsr                             ; töyssy (koko kone 1 rivi ylös) 8 hires-px:n paloittain, seis: ei
        and #15                         ; töyssyä eikä nytkähdystä (pomppiminen näyttäisi rumalta),
        tax                             ; tyhjäkäynnillä värisee vain ylärivi
        lda tr_bump,x
        ldx tr_s
        beq +
        lda #0
+       sta tr_b
        lda #TRAK_Y + 21
        sec
        sbc tr_b
        sta tr_ya
        lda DFRAME                      ; ylärivi 21 ylempänä, värisee moottorin tahdissa (1 rivi alas)
        and #2
        lsr
        adc tr_ya                       ; (C = 0)
        sbc #21 - 1                     ; (C = 0)
        sta tr_yy
        lda tr_a                        ; telavaihe a mod 3 (vaihtuu 4 hires-px:n välein maailmassa)
        .for k := 192, k >= 3, k /= 2
        cmp #k
        bcc +
        sbc #k
+
        .next
        asl
        asl
        asl
        asl
        sta tr_ph
        lda #1                          ; (hyppy asettaa kehyksessä hop1:n, ja hop_pois ketjuttaa tänne)
        sta trak_v
        lda #<trak_irq
        sta $fffe
        lda #>trak_irq
        sta $ffff
        lda #TRAK_LINE
        sta $d012
        rts
trak_end
        .cerror * > PA_SB, "traktori ylittää puskurin B ruudun"

        * = TRAK_IRQ                    ; SPT: lohkojen perässä
; trak_irq rivillä TRAK_LINE: samat 8 laitteistospriteä traktoriksi (ylärivi hw 0-3, alarivi hw 4-7), sitten taas
; rivin 250 IRQ
trak_irq
        pha
        txa
        pha
        lda $01
        pha
        lda #$35
        sta $01
        asl $d019
        .for c := 0, c < 4, c += 1
        lda tr_xs + c
        sta $d000 + 2 * c
        sta $d008 + 2 * c
        .next
        lda z_ha                        ; hyppy: kuva z_ha + z_hb riviä alempana (z_ha = 0: ei hyppyä)
        beq +
        clc
        adc z_hb
+       tax
        clc
        adc tr_yy
        .for c := 0, c < 4, c += 1
        sta $d001 + 2 * c
        .next
        txa
        clc
        adc tr_ya
        .for c := 0, c < 4, c += 1
        sta $d009 + 2 * c
        .next
        ldx tr_ph                       ; osoittimet näkyvään ruutuun (piilossa olevassa pysyvät nimen)
        lda s_buf
        bne +
        .for i := 0, i < 8, i += 1
        lda trak_osoit + i,x
        sta PA_SA + $3f8 + i
        .next
        jmp ++
+
        .for i := 0, i < 8, i += 1
        lda trak_osoit + 8 + i,x
        sta PA_SB + $3f8 + i
        .next
+        lda #TRAK_VARI
        .for i := 0, i < 8, i += 1
        sta $d027 + i
        .next
        lda tr_msb
        sta $d010
        lda tr_on
        sta $d015
        lda #0                          ; %01 ääriviiva ja telan kylki mustana (ruskealla maalla erottuu)
        sta $d025
        lda #12
        sta $d026
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        lda #IRQ_LINE
        sta $d012
        pla
        sta $01
        pla
        tax
        pla
        rti

; trak_nimi: nimen rekisterit takaisin rivin 250 IRQ:ssa; spritet pois, kunnes kehys (nimi) asettaa ne:
; myöhästynyt kehys ei näytä nimeä traktorin paikalla. Osoittimet vain näkyvään ruutuun (trak_irq kirjoitti vain siihen)
trak_nimi
        lda #NIMI_D025
        sta $d025
        lda #NIMI_D026
        sta $d026
        lda #0
        sta $d015
        lda #NIMI_VARI
        .for i := 0, i < 8, i += 1
        sta $d027 + i
        .next
        lda s_buf
        bne +
        .for i := 0, i < 8, i += 1
        lda #NIMI_PTR + i
        sta PA_SA + $3f8 + i
        .next
        rts
+
        .for i := 0, i < 8, i += 1
        lda #NIMI_PTR + i
        sta PA_SB + $3f8 + i
        .next
        rts

trak_jarru .byte TRAK_JARRU             ; jarrutus: W - TRAK_WD kehyksittäin
trak_osoit .byte TRAK_OSOITTIMET        ; telavaihe v (16 v): ruutu A 8, ruutu B 8
tr_bump .byte 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0
tr_x    .word 0
tr_w    .word 0                         ; maailman paikka
tr_dh   .byte 0
tr_s    .byte 0                         ; 1 = pysähtynyt
tr_b    .byte 0
tr_a    .byte 0
tr_ya   .byte 0                         ; alarivin y
tr_yy   .byte 0                         ; ylärivin y
tr_ph   .byte 0
tr_on   .byte 0
tr_msb  .byte 0
tr_xs   .fill 4
trak_irq_end
        .cerror * > $fffa, "trak_irq ylittää $fff9"
