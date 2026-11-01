; Latausväli spritet -> sokeripala: kun sprite-ennätys
; on pimentynyt ja sokeripalan alku latautuu, viimeiset logot (ADAPT ja CR!SP, X+Y-laajennetut MC-spritet) nousevat ja
; haihtuvat tähdiksi (5 vaihetta), 31 tähteä liukuu sokeripalan kehyksen 0 tähtien paikoille ja taivas
; tulee esiin Bayer-ditherinä sokeripalan värein. Sokeripalan sp_show vaihtaa kuvan rivillä 250: sama taivas ja tähdet
; samoissa pikseleissä, joten leikkausta ei näe.
; Kaikki työ rungon IRQ:n R_TICKissä (rivi 250, musiikin jälkeen); pääsäie lataa sokeripalaa. Ei nollasivua
; (sokeripalan sp_init nollaa omansa samaan aikaan), osoitteet itsemuokkaavina.
; Tiedostot: TV1 $8400- (logojen vaiheet, tähtipuskurit, koodi), TV2 $b2c0- (taivaan lähde bittikartan riveillä
; 15-24, joiden värit ovat mustia, joten se ei näy). Ruutu $8000, bittikartta $a000 (VIC-pankki 2).
; Data tools/disk/tahtivali.py (laatikot, tähdet, käyrä, maskit).

        .include "runko.inc"

SCR     = $8000
BMP     = $a000
LOGO    = $8400                 ; 2 logoa x 5 vaihetta x 2 spriteä
STARB   = $8900                 ; tähtipuskurit: puskuri b, laatikko k: STARB + b * $200 + k * 64
SKY_SRC = BMP + 15 * 320        ; TV2: taivaan rivit, sitten ruudun tavut ja värimuisti
SKY_SCR = SKY_SRC + 7 * 320
SKY_COL = SKY_SCR + 7 * 40
BLK     = (LOGO - SCR) / 64     ; logojen ensimmäinen lohko
SBLK    = (STARB - SCR) / 64

        * = LOGO
        .binary "tv_logo.bin"
        .fill STARB + $400 - *, 0
        * = $9000

; tv_go (taulusta, pääsäie, rungon IRQ päällä, kuva pimeänä ku_cutin jälkeen): ruutu, värimuisti ja bittikartan rivit
; 0-14 nollaksi, logot paikalleen, ja VIC rivin 250 jälkeen (ei latausta käynnissä: $dd00 turvallinen)
tv_go
        lda #0
        tax
-       sta SCR,x
        sta SCR+$100,x
        sta SCR+$200,x
        sta SCR+$2e8,x
        sta $d800,x
        sta $d900,x
        sta $da00,x
        sta $dae8,x
        inx
        bne -
        ldy #>(SKY_SRC - BMP)
_clrb   sta BMP,x               ; rivit 0-14 ($a000-$b2bf)
        inx
        bne _clrb
        inc _clrb + 2
        dey
        bne _clrb
        lda #>BMP
        sta _clrb + 2
        tya
-       sta SKY_SRC - $c0,x     ; $b200-$b2bf
        inx
        cpx #$c0
        bne -
        sta t
        sta tw
        sta sky_on
        sta st_on
        lda #LOGO_Y0
        sta ly
        lda #RISE
        sta rc
        cli                     ; (osalevyllä kello alkoi I = 1; koko demossa ku_cut jätti I = 0)
        lda DFRAME              ; rivin 250 IRQ juuri ajettu: VIC kokonaisen kehyksen rajalla
-       cmp DFRAME
        beq -
        lda logo_x
        sta $d000
        lda logo_x+1
        sta $d002
        lda logo_x+2
        sta $d004
        lda logo_x+3
        sta $d006
        lda logo_xh
        sta $d010
        lda ly
        sta $d001
        sta $d003
        sta $d005
        sta $d007
        lda #BLK
        sta SCR+$3f8
        lda #BLK+1
        sta SCR+$3f9
        lda #BLK+10
        sta SCR+$3fa
        lda #BLK+11
        sta SCR+$3fb
        lda #3                  ; %10 = spriten väri
        sta $d027
        sta $d028
        sta $d029
        sta $d02a
        lda #1                  ; %01 valkoinen
        sta $d025
        lda #15                 ; %11 vaaleanharmaa
        sta $d026
        lda #$0f
        sta $d01c
        sta $d017
        sta $d01d
        sta $d015
        lda #0
        sta $d01b
        sta $d021
        lda #1                  ; VIC-pankki 2
        sta $dd00
        lda #$08                ; ruutu $8000, bittikartta $a000
        sta $d018
        lda #$17                ; MC, 38 saraketta, hienovieritys 7 (kuten sokeripala)
        sta $d016
        lda #$3b
        sta $d011
        #TICK tv_tick
        rts

; tv_sky (taulusta TV2:n latauksen jälkeen): taivaan värit ruutuun ja värimuistiin (bittikartta vielä musta), paljastus
tv_sky
        ldx #7 * 20 - 1         ; 280 tavua kahtena puoliskona
-       lda SKY_SCR,x
        sta SCR + SKY_R0 * 40,x
        lda SKY_SCR + 140,x
        sta SCR + SKY_R0 * 40 + 140,x
        lda SKY_COL,x
        sta $d800 + SKY_R0 * 40,x
        lda SKY_COL + 140,x
        sta $d800 + SKY_R0 * 40 + 140,x
        dex
        cpx #$ff
        bne -
        lda #0
        sta sk_s
        sta sk_r
        jsr sk_mask
        inc sky_on
        rts

; tv_end (sokeripalan I_SHOW ennen sp_showta): päivitys pois, kuva ja spritet jäävät, kunnes sp_show vaihtaa rivillä 250
tv_end
        #TICK 0
        rts

; ---------------------------------------------------------------- kehys (rungon IRQ, rivi 250)
tv_tick
        lda t
        cmp #T_HAND
        bcs _stars
        dec rc                  ; logot nousevat
        bne +
        lda #RISE
        sta rc
        dec ly
+       lda ly
        sta $d001
        sta $d003
        sta $d005
        sta $d007
        ldx #0                  ; vaihe = montako phase_t:tä <= t
-       lda phase_t+1,x
        cmp t
        beq +
        bcs ++
+       inx
        bne -
+       txa
        asl a
        adc #BLK
        sta SCR+$3f8
        adc #1
        sta SCR+$3f9
        adc #9
        sta SCR+$3fa
        adc #1
        sta SCR+$3fb
        lda t
        cmp #T_HAND - 1
        bne _sky
        jsr st_init             ; tähdet alkupaikoilleen puskuriin 0 (näkyy seuraavassa kehyksessä)
        jmp _sky
_stars  lda st_on
        bne +
        inc st_on               ; logot -> tähdet
        lda #$ff
        sta $d015
        sta $d01d
        lda #0
        sta $d01c
        sta $d017
        lda #1
        ldx #7
-       sta $d027,x
        dex
        bpl -
+       lda gf
        cmp #GLIDE
        bcs _hold
        jsr st_show             ; liuku: edellisen kehyksen puskuri näkyviin, uusi taakse
        jsr st_step
        jmp _sky
_hold   lda st_fin              ; liuku valmis: piirto vain, kun tuikkeen piilotettu tähti vaihtuu (kevyt IRQ,
        bne +                   ; lataus etenee)
        inc st_fin
        jsr st_show             ; viimeinen liu'un kuva
        lda #$ff
        sta shown
+       jsr tw_hide             ; tuike: vain kahden tähden piste näkyvässä puskurissa (koko piirto veisi IRQ:ssa noin
        cmp shown               ; 100 riviä, ja ku_start kutsuisi sokeripalan showta kesken kuvan: iskun uusinta, 27
        beq _sky                ; kehystä samaa kuvaa)
        pha
        ldx shown
        bmi +
        jsr tw_flip             ; edellinen piilotettu takaisin
+       pla
        sta shown
        tax
        bmi _sky
        jsr tw_flip             ; uusi piiloon
_sky    lda sky_on
        beq +
        jsr sk_row
+       inc tw
        inc t
        bne +
        dec t
+       rts

; ---------------------------------------------------------------- tähdet
; Laatikko k (sprite k): paikka VIC-koordinaateissa 24-bittisenä (bxf, bxl, bxh: 1/256 px), lisäys bdx * de.
; Tähti i laatikossa: (sx, sy) sprite-pikseleinä 16-bittisenä, lisäys s_dx * de. Puskuri vaihtuu joka kehys.
st_init
        ldx #7
-       lda bx0_lo,x
        sta bxl,x
        lda bx0_hi,x
        sta bxh,x
        lda by0,x
        sta byl,x
        lda #0
        sta bxf,x
        sta byf,x
        dex
        bpl -
        ldx #NSTAR - 1
-       lda s_x0,x
        sta sxh,x
        lda s_y0,x
        sta syh,x
        lda s_box,x             ; puskurin sivu ja laatikon siirtymä sivulla
        lsr a
        lsr a
        sta s_pg,x
        lda s_box,x
        and #3
        lsr a
        ror a
        ror a
        sta s_bo,x
        lda #0
        sta old0,x
        sta old1,x
        sta oldp0,x
        sta oldp1,x
        dex
        bpl -
        lda #0
        sta gf
        sta buf
        sta st_fin
        sta ecur
        sta ecur+1
        lda #$ff
        sta hide
        jmp st_plot

st_show                         ; edellisen kehyksen puskuri näkyviin: osoittimet ja paikat
        lda buf
        asl a
        asl a
        asl a
        adc #SBLK
        ldx #0
-       sta SCR+$3f8,x
        clc
        adc #1
        inx
        cpx #8
        bne -
        lda #0
        sta msb
        ldx #7
        ldy #14
-       lda bxl,x
        sta $d000,y
        lda byl,x
        sta $d001,y
        lda bxh,x
        lsr a
        rol msb                 ; viimeisenä sprite 0 bittiin 0
        dey
        dey
        dex
        bpl -
        lda msb
        sta $d010
        lda buf
        eor #1
        sta buf
        rts

st_step                         ; liuku: de lisäystä käyrästä, sitten piirto toiseen puskuriin
        ldx gf
        cpx #GLIDE
        bcs st_plot
        inc gf
        lda de_tab,x
        beq st_plot
        sta de
_de     ldx #7                  ; laatikot
-       ldy #0
        lda bdx_hi,x
        bpl +
        dey
+       clc
        lda bxf,x
        adc bdx_lo,x
        sta bxf,x
        lda bxl,x
        adc bdx_hi,x
        sta bxl,x
        tya
        adc bxh,x
        sta bxh,x
        lda bdy,x
        bpl +
        clc
        adc byf,x
        sta byf,x
        bcs ++
        dec byl,x
        bcc ++
+       clc
        adc byf,x
        sta byf,x
        bcc +
        inc byl,x
+       dex
        bpl -
        dec de
        bne _de
        ldx gf                  ; e = käyrän kertymä (0..256): taulu (d * e + 128) >> 8, d = 0..23
        lda de_tab - 1,x
        clc
        adc ecur
        sta ecur
        bcc +
        inc ecur+1
+       lda #128
        sta acc
        lda #0
        sta acc+1
        sta etab
        ldy #1
-       lda acc
        clc
        adc ecur
        sta acc
        lda acc+1
        adc ecur+1
        sta acc+1
        sta etab,y
        iny
        cpy #24
        bne -
        ldx #NSTAR - 1          ; tähdet: alku + etumerkki * etab[|d|]
-       lda s_dx,x
        bmi +
        tay
        lda etab,y
        clc
        adc s_x0,x
        jmp ++
+       eor #$ff
        tay
        iny
        lda s_x0,x
        sec
        sbc etab,y
+       sta sxh,x
        lda s_dy,x
        bmi +
        tay
        lda etab,y
        clc
        adc s_y0,x
        jmp ++
+       eor #$ff
        tay
        iny
        lda s_y0,x
        sec
        sbc etab,y
+       sta syh,x
        dex
        bpl -

st_plot                         ; puskuriin buf (ei näkyvissä): vanhat pisteet pois, uudet. Tuike: liu'un jälkeen yksi
        lda buf                 ; tähti pois 2 kehystä kahdeksasta
        asl a
        adc #>STARB
        sta pg0
        ldx #NSTAR - 1
-       lda buf                 ; vanha piste tästä puskurista
        bne +
        lda oldp0,x
        ldy old0,x
        jmp ++
+       lda oldp1,x
        ldy old1,x
+       clc
        adc pg0
        sta _clr + 2
        lda #0
_clr    sta STARB,y
        dex
        bpl -
        ldx #NSTAR - 1
_pl     lda s_pg,x
        clc
        adc pg0
        sta _or + 2
        sta _st + 2
        ldy syh,x
        lda s_bo,x
        clc
        adc mul3,y
        sta zz
        lda sxh,x
        lsr a
        lsr a
        lsr a
        clc
        adc zz
        tay
        lda buf
        bne +
        tya
        sta old0,x
        lda s_pg,x
        sta oldp0,x
        jmp ++
+       tya
        sta old1,x
        lda s_pg,x
        sta oldp1,x
+       cpx hide
        beq +
        lda sxh,x
        and #7
        sta zz
        stx zx
        ldx zz
        lda bitv,x
        ldx zx
_or     ora STARB,y
_st     sta STARB,y
+       dex
        bpl _pl
        rts

tw_flip                         ; X = tähti: sen piste näkyvässä puskurissa (buf ^ 1) päälle tai pois
        lda buf
        bne +
        lda oldp1,x
        clc
        adc #>STARB + 2
        ldy old1,x
        jmp ++
+       lda oldp0,x
        clc
        adc #>STARB
        ldy old0,x
+       sta _fe + 2
        sta _fs + 2
        lda sxh,x
        and #7
        tax
        lda bitv,x
_fe     eor STARB,y
_fs     sta STARB,y
        rts

tw_hide                         ; A = tuikkeessa piilotettu tähti: 2 kehystä kahdeksasta, muuten $ff
        lda tw
        and #7
        cmp #2
        lda #$ff
        bcs +
        lda tw
        lsr a
        lsr a
        lsr a
        and #31
        tax
        lda tw_tab,x
+       rts

; ---------------------------------------------------------------- taivas: Bayer-paljastus, rivi kehyksessä
; Askel s: kohde = lähde & maski (rivin tavu & 3 = merkkirivin rivi & 3, 4 x 4 Bayer MC-pikseleille, tasot pareittain).
; Kehyksessä yksi bittikartan merkkirivi kahtena 160 tavun puoliskona (noin 5 000 sykliä), 7 riviä askelta kohden.
sk_row  lda sk_s
        cmp #SKY_STEPS
        bcs _r
        lda sk_r
        asl a
        tax
        jsr _half
        inx
        jsr _half
        inc sk_r
        lda sk_r
        cmp #SKY_NR
        bcc _r
        lda #0
        sta sk_r
        inc sk_s
        lda sk_s
        cmp #SKY_STEPS
        bcs _r
        jmp sk_mask
_r      rts

_half   .for n := 0, n < 4, n += 1      ; X = puolirivi: 4 lähde- ja kohdeosoitetta (tavut n, n + 4, ...)
        lda sk_src_lo,x
        clc
        adc #n
        sta ska0 + 8 * n + 1
        lda sk_src_hi,x
        adc #0
        sta ska0 + 8 * n + 2
        lda sk_dst_lo,x
        clc
        adc #n
        sta ska0 + 8 * n + 6
        lda sk_dst_hi,x
        adc #0
        sta ska0 + 8 * n + 7
        .next
        stx zx
        ldx #0
ska0     .for n := 0, n < 4, n += 1
        lda $ffff,x
        and #0
        sta $ffff,x
        .next
        txa
        clc
        adc #4
        tax
        cpx #160
        bne ska0
        ldx zx
        rts

sk_mask lda sk_s                ; askeleen maskit (rivin tavu & 3)
        asl a
        asl a
        tax
        .for n := 0, n < 4, n += 1
        lda sky_mask + n,x
        sta ska0 + 8 * n + 4
        .next
        rts

        .include "tv.inc"
mul3    .byte range(0, 63, 3)
bitv    .byte $80, $40, $20, $10, $08, $04, $02, $01
tw_tab  .byte 3, 17, 9, 28, 1, 22, 12, 30, 6, 19, 14, 25, 0, 10, 27, 4, 21, 8, 16, 29, 2, 24, 11, 18, 7, 26, 13, 5, 20, 15, 23, 3
sk_src_lo .byte <(SKY_SRC + range(14) * 160)        ; puolirivit
sk_src_hi .byte >(SKY_SRC + range(14) * 160)
sk_dst_lo .byte <(BMP + SKY_R0 * 320 + range(14) * 160)
sk_dst_hi .byte >(BMP + SKY_R0 * 320 + range(14) * 160)

        .virtual *              ; tila (ei ladata: tv_go ja st_init alustavat)
t       .byte ?
tw      .byte ?
rc      .byte ?
ly      .byte ?
sky_on  .byte ?
st_on   .byte ?
sk_s    .byte ?
sk_r    .byte ?
gf      .byte ?
buf     .byte ?
de      .byte ?
pg0     .byte ?
hide    .byte ?
zz      .byte ?
zx      .byte ?
msb     .byte ?
bxf     .fill 8
bxl     .fill 8
bxh     .fill 8
byf     .fill 8
byl     .fill 8
sxh     .fill NSTAR
syh     .fill NSTAR
etab    .fill 24
ecur    .word ?
acc     .word ?
st_fin  .byte ?
shown   .byte ?
s_pg    .fill NSTAR
s_bo    .fill NSTAR
old0    .fill NSTAR
old1    .fill NSTAR
oldp0   .fill NSTAR
oldp1   .fill NSTAR
tv_end_var
        .endv
        .cerror tv_end_var > BMP, "TV1 yli bittikartan"
