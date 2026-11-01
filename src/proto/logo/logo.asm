; Alkuruutu: Oy Lohja AI -emblem C64:lle.
;
; Reaaliaikainen 3D 6510:llä, MC-bittikartta kaksoispuskuroituna kahdessa VIC-pankissa:
;   pankki 1: ruutu $4000, bittikartta $6000 (puskuri A); pankki 2: ruutu $8000, bittikartta $a000 (B)
; Kuva (main): aikajana -> kertoimet -> verteksit -> näkyvyys ja sävy -> särmien XOR-merkit merkkipuskuriin
; ($e000, 256 tavua per solurivi) -> pystysuora XOR-täyttö sarakkeittain (generoidut ketjut fill.asm, X =
; sarake * 8) -> vaakaviiva ja lankamallin viivat. Bittitarkka vertailumalli tools/gfx/logo/model.py.
;
; Nollasivu $02-$bf, muisti $1a00-$cfff ja $e000-$fff9 kuten demon osat (src/runko/runko.inc). Muisti:
;   $1a00 koodi, $4000 ruutu A, $4400 nimen spritet, taulut ja ajonaikaiset taulut, $6000 bittikartta A,
;   $8000 ruutu B, $8400 spritet (VIC näkee $9000-$9fff ROMina), sini (neljännes), täyttöketjut ja neliötaulut,
;   $a000 bittikartta B, $e000 merkkipuskuri (sivun tavut $a0-$ff vapaita), $f600 taulut 2 (valo, segmentit; demossa
;   oma tiedosto), $fb80 (T3) aaltoilu, pyyhkäisy ja purun IRQ. Purun kuva pankissa 3 ($c000 ruutu, $e000 bittikartta).
;   Omassa ohjelmassa musiikki $0a00.

        .include "consts.inc"
        .include "music.inc"

        .weak
INTEGRATED = 0                  ; 1: demon osa (rungon frame_hook, musiikki ja kello)
LEAD    = 3                     ; ensimmäinen kuva näin monta kehystä etukäteen (sitten edellisen kesto)
PROF    = 0                     ; vaiheprofiili (prof, luetaan emulaattorista)
        .endweak
        .if INTEGRATED
        .include "../../runko/runko.inc"
        .else
DFRAME  = $d0                   ; demon kehys kuten runko.inc:ssä
        .endif

        .virtual $02
t       .word ?                 ; laskettavan kuvan kehys kohtauksessa
sk      .byte ?
ybh     .byte ?                 ; ybq8:n ylätavu
exiting .byte ?
dvis    .byte ?
dfly    .byte ?
grow    .fill 8                 ; 4 x 16 bittiä
sp_     .byte ?
cp_     .byte ?
sy_     .byte ?
cy_     .byte ?
a00     .byte ?
a02     .byte ?
a10     .byte ?
a11     .byte ?
a12     .byte ?
r10     .byte ?
r12     .byte ?
r20     .byte ?
r21     .byte ?
r22     .byte ?
m1l     .word ?                 ; kertolaskun osoittimet (ylätavut kiinteät)
m1h     .word ?
m2l     .word ?
m2h     .word ?
pl      .byte ?
ph      .byte ?
uu      .byte ?
uv      .byte ?
ptr     .word ?
ptr2    .word ?
tmp     .fill 8
xa      .byte ?
ya      .byte ?
xb      .byte ?
yb      .byte ?
de      .byte ?
do      .byte ?
mdx     .byte ?                 ; särmä (mark.asm): leveys, suunta (0 alas, 8 ylös), |kaltevuus| Q8
mdir    .byte ?
slo     .byte ?
shi     .byte ?
f       .byte ?                 ; rivin murto-osa
row     .byte ?
mk      .fill 2
cx      .byte ?                 ; rivisegmentti: alku, pituus, jäljellä, tavuja - 1, kuviot
cn      .byte ?
nrem    .byte ?
nb      .byte ?
pa      .byte ?
pb      .byte ?
spx     .byte ?
pex     .fill 4                 ; täytön paikatut poistumiskohdat (parillinen, pariton)
fcol    .byte ?                 ; täyttö: sarake, rivit, X, vanhojen välien siirtymä
flo     .byte ?
fhi     .byte ?
fx8     .byte ?
boff    .byte ?
bx0     .byte ?                 ; ryhmän ruutulaatikko
bx1     .byte ?
by0     .byte ?
by1     .byte ?
rdone   .byte ?                 ; heijastus piirretty
mcx     .fill 3                 ; kappaleen sarakkeet mx, my (^$80)
mcy     .fill 3
a00x    .byte ?                 ; kertoimet ^$80
a10x    .byte ?
a11x    .byte ?
ok      .byte ?                 ; kappale
oyr     .word ?                 ; keskipisteen yc (heijastus: yc - QR a11)
qra     .word ?                 ; QR a11
bxw     .fill 6                 ; kantavektorit ruudulla
byw     .fill 6
xo      .fill 8                 ; palikan kulmien siirtymät
yo      .fill 16
ax_     .word ?                 ; palikan laatikon puolikkaat (x Q9, y Q8)
ay_     .word ?
xd      .word ?
yd      .word ?
w0      .word ?
w1      .word ?
w2      .word ?
w3      .word ?
rlive   .byte ?                 ; heijastus tässä kuvassa
fwall   .byte ?                 ; kaikkien tahkojen täyttöpainojen AND
fi      .byte ?                 ; silmukkaindeksit
ei      .byte ?
xs      .word ?
ys      .word ?
back    .byte ?                 ; piirrettävä puskuri 0 = A, 1 = B
shown   .byte ?
ready   .byte ?
readyt  .word ?
bufh    .byte ?                 ; $00 (A) tai $40 (B): bittikartan osoitteen ylätavun lisä
lx0     .byte ?
ly0     .byte ?
lx1     .byte ?
ly1     .byte ?
ldx_    .byte ?
ldy_    .byte ?
lerr    .byte ?
lmk     .byte ?                 ; viivan pikselimaski ja kerätyt bitit
mb      .byte ?
jv      .word ?                 ; täyttöketjun sisääntulo (jmp (jv))
lead    .byte ?                 ; kuvan etumatka kehyksinä
ptr3    .word ?                 ; IRQ:n osoitin
final   .byte ?                 ; kohtauksen viimeinen kuva laskettu
hand    .byte ?                 ; luovutus: 1 = pyydetty, 2 = tehty
zpend
        .endv
        .cerror zpend > MUSIC_ZP, "nollasivu yli musiikin"

; ---------------------------------------------------------------- makrot
SETMUL  .macro                  ; A = etumerkillinen kerroin
        eor #$80
        sta m1l
        sta m1h
        eor #$ff
        sta m2l
        sta m2h
        .endm

MULY    .macro                  ; Y = kerrottava ^ $80 -> pl = alatavu, A = ylätavu (etumerkillinen tulo)
        lda (m1l),y
        sec
        sbc (m2l),y
        sta pl
        lda (m1h),y
        sbc (m2h),y
        .endm

        .if INTEGRATED
        * = $1a00
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
        lda #0
        sta $d01a
        lda #$3f
        sta $dd02
        ldx #<MSTART
        ldy #>MSTART
        jsr music_seek
        jmp logo_init
nmi     rti
        .include "../../music/music.asm"
        * = $1a00
        .endif

; ---------------------------------------------------------------- init
logo_init
        lda #$0b
        sta $d011
        lda #0
        sta $d015
        sta $d020
        sta $d021
        ldx #$02
-       sta $00,x
        inx
        cpx #$c0
        bne -
        lda #>q1l
        sta m1l+1
        lda #>q1h
        sta m1h+1
        lda #>q2l
        sta m2l+1
        lda #>q2h
        sta m2h+1
        .if !INTEGRATED
        ldx #>(T2END - T2)              ; taulut 2 bittikartan B paikalta: täydet sivut, sitten loput
        ldy #0                          ; (ei vektoreiden $fffa- päälle)
_cs     lda BMPB,y
_cd     sta T2,y
        iny
        bne _cs
        inc _cs + 2
        inc _cd + 2
        dex
        bne _cs
_ce     cpy #<(T2END - T2)
        beq +
        lda (BMPB & $ff00) + ((T2END - T2) & $ff00),y
        sta T2 + ((T2END - T2) & $ff00),y
        iny
        bne _ce
+
        .endif
        lda #0
        sta hbank
        jsr clear_mem
        jsr colors
        ldx #2 * COLS - 1
-       lda #$ff
        sta olo,x
        lda #0
        sta ohi,x
        dex
        bpl -
        lda #$ff                ; puskureiden sarakevälit tyhjiksi
        sta ocmin
        sta ocmin+1
        lda #0
        sta ocmax
        sta ocmax+1
        lda #LEAD
        sta lead
        lda #0
        sta hlw
        sta hlw+1
        sta nmrest
        lda #1
        sta back                ; A näkyvissä, piirretään B:hen
        lda #0
        sta shown
        ldx #NM_N - 1           ; nimen spritet: osoittimet molemmilla ruuduilla, x-paikat, hires, edessä
-       txa
        clc
        adc #(SPRA & $3fff) / 64
        sta SCRA + $3f8,x
        sta SCRB + $3f8,x
        txa
        asl a
        tay
        lda nm_xl,x
        sta $d000,y
        dex
        bpl -
        lda #NM_XMSB
        sta $d010
        lda #0
        sta $d015
        sta $d017
        sta $d01b
        sta $d01c
        sta $d01d
        lda #$02                ; VIC-pankki 1
        sta $dd00
        lda #$08                ; ruutu +$0000, bittikartta +$2000
        sta $d018
        lda #$18
        sta $d016
        .if INTEGRATED
        rts
logo_go
        .endif
        sei
        lda #<irq_top
        sta $fffe
        lda #>irq_top
        sta $ffff
        lda #$0b                ; ruutu pimeänä kelloon asti (rivin 9. bitti 0); $1b näyttäisi tekstitilassa
        sta $d011               ; ruutumuistin värit merkkeinä kehyksessä 1
        lda #IRQ_TOP
        sta $d012
        lda #1
        sta $d01a
        sta $d019
        .if !INTEGRATED
-       bit $d011               ; kehys 0 alkaa rivillä 240
        bmi -
-       lda $d012
        cmp #240
        bne -
clock0  lda #0
        sta DFRAME
        sta DFRAME+1
        .endif
        lda back                ; näkyviin tyhjä puskuri (ei piirrettävä): ilman tätä VIC näyttäisi edellisen osan
        eor #1                  ; pankin (runko: pankki 0, bittikartta $2000 = alun koodia) ensimmäisen kuvan ajan
        tax
        lda bankval,x
        sta $dd00
        lda d018val,x
        sta $d018
        lda #$18                ; MC ennen ruutua (hires-tila näyttäisi tyhjän bittikartan ruutumuistin alanibbleinä,
        sta $d016               ; heijastuksen solujen värit kehyksessä 1)
        lda #$3b                ; MC-bittikartta, ruutu päälle
        sta $d011
        cli

; ---------------------------------------------------------------- pääsilmukka
main    lda ready
        beq +
        .if INTEGRATED
        jsr R_IDLE              ; CPU-mittari
        .endif
        jmp main
+       lda final               ; viimeinen kuva näkyy: luovutus pieneen IRQ:hun (hand.asm, T3), kuva pankkiin 3
        beq +                   ; (Hillnerin hil_prep rakentaa pankkiin 2), sitten paluu kohtaustauluun
        lda #1
        sta hand
-       .if INTEGRATED
        jsr R_IDLE
        .endif
        lda hand
        cmp #2
        bne -
        jsr bank3
        lda #1                  ; hw_250 vaihtaa pankin 3 näkyviin
        sta hbank
-       .if INTEGRATED
        jsr R_IDLE
        .endif
        lda hbank
        cmp #2
        bne -
        .if INTEGRATED
        rts
        .else
-       jmp -
        .endif
+       lda back
        beq +
        lda #$40
+       sta bufh
        sec
        lda DFRAME
        sbc #<SCENE_START
        sta t
        lda DFRAME+1
        sbc #>SCENE_START
        sta t+1
        lda DFRAME
        sta r0f
        lda DFRAME+1
        sta r0f+1
        clc
        lda t
        adc lead
        sta t
        bcc +
        inc t+1
+       lda t                   ; purun alusta viimeinen kuva (EX0 - 1) puskuriin B, sitten pyyhkäisy (hand.asm)
        cmp #<EX0
        lda t+1
        sbc #>EX0
        bcc +
        lda #<(EX0 - 1)
        sta t
        lda #>(EX0 - 1)
        sta t+1
        lda back
        beq +
        inc final
+       jsr render
        lda t
        sta readyt
        lda t+1
        sta readyt+1
        inc renders             ; mittari: kuvat ja kehykset (fps = 50 * renders / rframes)
        bne +
        inc renders+1
+       sec                     ; seuraava kuva yhtä kauan etukäteen kuin tämä kesti (2..6)
        lda DFRAME
        sbc r0f
        tax
        cpx #2
        bcs +
        ldx #2
+       cpx #7
        bcc +
        ldx #6
+       stx lead
        clc
        adc rframes
        sta rframes
        bcc +
        inc rframes+1
+       lda #1
        sta ready
        jmp main

; ---------------------------------------------------------------- keskeytykset
IRQ_TOP = 40
IRQ_BOT = 250

irq_top pha
        txa
        pha
        tya
        pha
        lda ready
        beq _no
        sec                     ; näytetään, kun demon kello on kuvan kehyksessä
        lda DFRAME
        sbc #<SCENE_START
        tax
        lda DFRAME+1
        sbc #>SCENE_START
        cpx readyt
        sbc readyt+1
        bcc _no
        lda readyt              ; mittari: näytetyn kuvan kehys
        sta shownt
        lda readyt+1
        sta shownt+1
        lda back
        sta shown
        tax
        lda bankval,x
        sta $dd00
        lda d018val,x
        sta $d018
        txa
        eor #1
        sta back
        lda #0
        sta ready
_no     lda #$3b                    ; kangas näkyviin (rip_end tyhjentää sen alla)
        sta $d011
        lda #<rip_irq               ; heijastuksen aaltoilu: kaistojen IRQ-ketju (rip_irq), sitten irq_bot
        sta $fffe
        lda #>rip_irq
        sta $ffff
        lda #RIP0 - 1
        sta $d012
        asl $d019
        pla
        tay
        pla
        tax
        pla
        rti


irq_bot pha
        txa
        pha
        tya
        pha
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
        lda #$18                ; aaltoilun jälkeen suoraan
        sta $d016
        lda hand
        cmp #1
        bne +
        jsr deco
        jmp handover
+       lda #<irq_top           ; seuraava IRQ ensin: decon välähdys (emflash) kestää yli kehyksen rajan ja
        sta $fffe               ; sallii keskeytykset (irq_top ja aaltoilu ajallaan)
        lda #>irq_top
        sta $ffff
        lda #IRQ_TOP
        sta $d012
        asl $d019
        jsr deco
        pla
        tay
        pla
        tax
        pla
        rti

bankval .byte $02, $01          ; A = pankki 1, B = pankki 2
d018val .byte (SCRA & $3c00) >> 6 | $08, (SCRB & $3c00) >> 6 | $08   ; ruutu (A $4000, B $bc00), bittikartta +$2000

deco                            ; kerran kehyksessä: välähdys, nimi, aaltoilun arvot seuraavalle kehykselle
        sec                     ; tt = kohtauksen kehys (seuraava näytettävä)
        lda DFRAME
        sbc #<SCENE_START
        sta tt
        lda DFRAME+1
        sbc #>SCENE_START
        sta tt+1
        sec                     ; välähdys: emblem valkoinen, seuraava vaaleanharmaa, sitten värit takaisin;
        lda tt                  ; tausta pysyy mustana
        sbc #<FLASH
        tay
        lda tt+1
        sbc #>FLASH
        bne +
        cpy #3
        bcs +
        tya
        cli                     ; noin 5-6k sykliä: irq_top ja aaltoilu saavat keskeyttää (irq_bot ei ole päällä)
        jsr emflash
        sei
+
        ; nimi: d = tt - NM_NAME - i * NM_STEP
        sec
        lda tt
        sbc #<NM_NAME
        sta tmpi
        lda tt+1
        sbc #>NM_NAME
        bcs +
        lda #0                  ; ennen nimeä
        sta $d015
        jmp _rip
+       bne _late               ; yli 255 kehystä: kaikki laskeutuneet
        lda tmpi
        cmp #(NM_N - 1) * NM_STEP + NM_DROPN
        bcs _late               ; viimeinenkin laskeutunut
        lda #0
        sta tmpi+1              ; näkyvät
        ldx #NM_N - 1
_s      txa                     ; i * NM_STEP
        tay
        lda #0
-       dey
        bmi +
        clc
        adc #NM_STEP
        bcc -
+       sta tmpi+2
        lda tmpi
        sec
        sbc tmpi+2
        bcc _off
        tay                     ; d
        cpy #NM_DROPN
        bcc +
        ldy #NM_DROPN - 1
+       txa
        asl a
        sta tmpi+3
        lda nm_drop,y
        ldy tmpi+3
        sta $d001,y
        tay
        lda tmpi
        sec
        sbc tmpi+2
        cmp #NM_RAMPN
        bcc +
        lda #NM_RAMPN - 1
+       tay
        lda nm_ramp,y
        sta $d027,x
        sec
        rol tmpi+1
        jmp _n
_off    asl tmpi+1
_n      dex
        bpl _s
        lda tmpi+1
        sta $d015
        jmp _rip
_late   lda nmrest              ; kaikki paikallaan, väri 1 (purun jälkeen putoavat pois: nmout); jo asetettu?
        bne _rip
        inc nmrest
        ldx #NM_N - 1
-       txa
        asl a
        tay
        lda nm_drop + NM_DROPN - 1
        sta $d001,y
        lda #1
        sta $d027,x
        dex
        bpl -
        lda #$ff
        sta $d015
_rip    lda tt                  ; aaltoilu heijastuksen ajan: SW0 <= tt < EX0
        cmp #<SW0
        lda tt+1
        sbc #>SW0
        bcc _ro
        lda tt
        cmp #<EX0
        lda tt+1
        sbc #>EX0
        bcs _ro
        lda tt
        jmp ripcalc
_ro     lda #$18                ; ei aaltoilua: suora $d016
        ldy #RIPN - 1
-       sta ripv,y
        dey
        bpl -
        rts


        .cerror NM_OUT < EX0 + 12, "nimi putoaa pois vasta purun IRQ:ssa (nmout)"

        .if INTEGRATED
nmout                           ; purun IRQ (hand.asm hw_250, ennen nimiruutua): kirjain i putoaa pois kehyksestä
        sec                     ; NM_OUT + i * OSTEP (name.state); spritet pankissa 3 (bank3), ei nollasivua
        lda DFRAME
        sbc #<(SCENE_START + NM_OUT)
        sta nmk
        lda DFRAME+1
        sbc #>(SCENE_START + NM_OUT)
        bcc _x                  ; ennen: paikallaan (deco)
        bne _off
        lda #0
        sta nmon
        ldx #0
_l      lda nmk
        sec
        sbc nm_ost,x
        bcc _on                 ; ei vielä
        cmp #NM_ODROPN
        bcs _nx                 ; pudonnut
        tay
        lda nm_ocol,y
        sta $d027,x
        lda nm_odrop,y
        pha
        txa
        asl a
        tay
        pla
        sta $d001,y
_on     lda nmon
        ora nm_bit,x
        sta nmon
_nx     inx
        cpx #NM_N
        bne _l
        lda nmon
        .byte $2c
_off    lda #0
        sta $d015
_x      rts
nmk     .byte 0
nmon    .byte 0
        .endif

; ---------------------------------------------------------------- muisti ja värit
clear_mem                       ; bittikartat, merkkipuskuri ja ruudut nolliksi
        lda #0
        tay
        ldx #>BMPA
        jsr clr32
        ldx #>BMPB
        jsr clr32
        ldx #>EBUF
        lda #0
        sta ptr
-       stx ptr+1
        ldy #0
        tya
-       sta (ptr),y
        iny
        cpy #$a0                ; sivun $a0-$ff on taulujen käytössä
        bne -
        inx
        cpx #>(EBUF + $1600)        ; + vararivi ROWS
        bne --
        rts
clr32   lda #0                  ; X = ylätavu: $2000 tavua nolliksi
        sta ptr
        stx ptr+1
        ldx #$20
        ldy #0
-       sta (ptr),y
        iny
        bne -
        inc ptr+1
        dex
        bne -
        rts

HZCELL  = HZ / 8

; ---------------------------------------------------------------- kertolaskut
umul8                           ; A = u, Y = v (etumerkittömät) -> pl/ph = u * v; sotkee kertoimen
        sta uu
        sty uv
        sta m1l
        sta m1h
        eor #$ff
        sta m2l
        sta m2h
        #MULY                   ; (u - 128) (v - 128)
        sta ph
        clc                     ; + 128 (u + v) - 16384
        lda uu
        adc uv
        ror a
        tax
        lda #0
        ror a
        clc
        adc pl
        sta pl
        txa
        adc ph
        sec
        sbc #$40
        sta ph
        rts

mulshr8                         ; tmp,tmp+1 = x, tmp+2,tmp+3 = k (etumerkittömät) -> tmp+4,tmp+5 = (x * k) >> 8
        lda tmp
        ldy tmp+2
        jsr umul8
        lda ph
        sta tmp+4
        lda #0
        sta tmp+5
        lda tmp
        ldy tmp+3
        jsr umul8
        jsr _add
        lda tmp+1
        ldy tmp+2
        jsr umul8
        jsr _add
        lda tmp+1
        ldy tmp+3
        jsr umul8
        clc
        lda pl
        adc tmp+5
        sta tmp+5
        rts
_add    clc
        lda pl
        adc tmp+4
        sta tmp+4
        lda ph
        adc tmp+5
        sta tmp+5
        rts

sin8_of                         ; A/X = kulma (lo/hi) -> A = sin8 (etumerkillinen); X, Y sotkeutuvat
        tay                     ; neljännesaalto: q = kulma >> 8, i = alatavu
        txa
        and #3
        tax
        lsr a
        bcc _e                  ; q parillinen: S[i], pariton: S[256 - i]
        tya
        eor #$ff
        tay
        iny
        bne _e
        lda #127                ; S[256]
        bne _g
_e      lda squart,y
_g      cpx #2                  ; q >= 2: negatiivinen
        bcc +
        eor #$ff
        adc #0                  ; C = 1
+       rts
cos8_of inx                     ; cos(a) = sin(a + 256)
        jmp sin8_of

shr7                            ; pl/ph -> A = (p >> 7) alatavu
        asl pl
        rol ph
        lda ph
        rts

; ---------------------------------------------------------------- aikajana (timeline.state)
RAMP    .macro a, b, k, s = t   ; -> A = 0..255 (s: aika)
        sec
        lda \s
        sbc #<\a
        sta tmp
        lda \s+1
        sbc #>\a
        sta tmp+1
        bmi _z
        ora tmp
        beq _z
        lda \s
        cmp #<\b
        lda \s+1
        sbc #>\b
        bcs _f
        lda #<\k
        sta tmp+2
        lda #>\k
        sta tmp+3
        jsr mulshr8
        lda tmp+4
        jmp _x
_z      lda #0
        jmp _x
_f      lda #255
_x
        .endm

state
        ; isku: kehys d = t - kick, 0..19
        lda #$ff
        sta kd
        ldx #NKICK - 1
_kk     sec
        lda t
        sbc kicks_l,x
        tay
        lda t+1
        sbc kicks_h,x
        bne _kn
        cpy #20
        bcs _kn
        sty kd
        txa
        and #1
        sta side
_kn     dex
        bpl _kk
        #RAMP PUSH0, PUSH1, KPUSH, t
        tax
        lda smooth,x
        sta push
        ; tp = max(0, t - PUSH0)
        sec
        lda t
        sbc #<PUSH0
        sta tmp
        lda t+1
        sbc #>PUSH0
        sta tmp+1
        bpl +
        lda #0
        sta tmp
        sta tmp+1
+       lda tmp                 ; kaksi kertolaskua samalle tp:lle
        sta tmp+6
        lda tmp+1
        sta tmp+7
        lda #546 & 255          ; (tp * 546) >> 8 = 2 tp + tp_hi * 34 + (tp_lo * 34) >> 8
        ldx #546 >> 8
        jsr mulk
        lda tmp+4               ; sway
        ldx tmp+5
        jsr sin8_of
        sta tmp+4
        lda #10
        #SETMUL
        lda tmp+4
        eor #$80
        tay
        #MULY
        sta ph
        jsr shr7                ; sin * 10 >> 7
        sta tmp+4
        ldy push
        lda #124
        jsr umul8               ; 124 * push >> 8
        ldx #0                  ; sin-termi etumerkillisenä 16 bittiin + 124 push >> 8
        lda tmp+4
        bpl +
        dex
+       stx tmp+5
        clc
        adc ph
        tax
        lda tmp+5
        adc #0
        sta tmp+5
        txa
        sec
        sbc #72
        tax
        lda tmp+5
        sbc #0
        sta tmp+5
        ldy kd                  ; + side * kyaw
        bmi _ny
        lda side
        bne +
        txa
        sec
        sbc kyaw,y
        tax
        lda tmp+5
        sbc #0
        sta tmp+5
        jmp _ny
+       txa
        clc
        adc kyaw,y
        tax
        lda tmp+5
        adc #0
        sta tmp+5
_ny     stx yaw
        lda tmp+5
        and #3
        sta yaw+1
        ldy kd
        lda #26
        cpy #$ff
        beq +
        clc
        adc kpitch,y
+       sta pitch
        ; valo
        lda tmp+6
        sta tmp
        lda tmp+7
        sta tmp+1
        lda #1092 & 255
        ldx #1092 >> 8
        jsr mulk
        clc
        lda tmp+4
        adc #200
        sta light
        lda tmp+5
        adc #0
        and #3
        sta light+1
        ; mittakaava: S4 = 184 + (24 push >> 8) + kscale
        ldy push
        lda #S4_PUSH
        jsr umul8
        lda ph
        clc
        adc #S4_BASE
        ldy kd
        cpy #$ff
        beq +
        clc
        adc kscale,y
+       sta tmp+6               ; S4 (< 256)
        ldy #129
        jsr umul8
        lda ph
        sta sk
        lda tmp+6
        lsr a
        lsr a
        sta tmp
        lda #HZ
        sec
        sbc tmp
        sta ybh
        ; purku?
        lda t
        cmp #<EX0
        lda t+1
        sbc #>EX0
        lda #0
        rol a
        sta exiting
        bne _exit
        ldx #7
        lda #0
-       sta grow,x
        dex
        bpl -
        #RAMP LAND0, DONE0, KBLK0
        ldx #0
        jsr growk
        #RAMP LAND1, DONE1, KBLK1
        ldx #1
        jsr growk
        #RAMP LAND2, DONE2, KBLK2
        ldx #2
        jsr growk
        jmp _fly
_exit   #RAMP EXG0, EXG1, KEXG
        tax
        lda smooth,x
        eor #$ff
        sta tmp+2
        lda #<GALL2
        sta tmp
        lda #>GALL2
        sta tmp+1
        jsr mul16x8
        ldx #6
-       lda tmp+4
        sta grow,x
        lda tmp+5
        sta grow+1,x
        dex
        dex
        bpl -
_fly    #RAMP FLY0, LOCK, KFLY
        sta tmp+6
        ldx #0
        cmp #0
        beq +
        inx
+       stx dvis
        lda t
        cmp #<LOCK
        lda t+1
        sbc #>LOCK
        lda #0
        rol a
        eor #1
        sta dfly
        lda dvis                ; lennon kierto ja siirtymä vain lennon aikana
        and dfly
        bne +
        jmp _lite
+       ldx tmp+6
        lda ease3,x
        eor #$ff
        sta ee                  ; e = 255 - ease3[u]
        ldy #10                 ; dry = e * 10, drx = e * 5, drz = e * 3 >> 1 (& 1023)
        jsr umul8
        lda pl
        sta dry
        lda ph
        and #3
        sta dry+1
        lda ee
        ldy #5
        jsr umul8
        lda pl
        sta drx
        lda ph
        and #3
        sta drx+1
        lda ee
        ldy #3
        jsr umul8
        lsr ph
        ror pl
        lda pl
        sta drz
        lda ph
        and #3
        sta drz+1
        lda ee
        ldy #150
        jsr umul8
        lda ph
        eor #$ff
        sta dsc                 ; 255 - (e * 150 >> 8)
        lda ee
        ldy #40
        jsr umul8
        lda ph
        sta dox
        lda ee
        ldy #56
        jsr umul8
        lda ph
        sta doy
        ; valo kamerassa (ei vaakaviivaa)
_lite
        lda light+1
        sta tmp
        lda light
        lsr tmp
        ror a
        lsr tmp
        ror a
        tax
        lda lcamx,x
        eor #$80
        sta lc0
        lda lcamy,x
        eor #$80
        sta lc1
        lda lcamz,x
        eor #$80
        sta lc2
        ; tahkojen täyttöpainot w (täyttö ylhäältä alas porrastettuna: fin[t - ft] RL kehystä, sitten 255;
        ; purussa 255 -> 0); pidossa (FTEND <= t < UTBEG) kaikki 255
        lda #$ff
        sta fwall
        lda t
        cmp #<FTEND
        lda t+1
        sbc #>FTEND
        bcc _fwl
        lda t
        cmp #<UTBEG
        lda t+1
        sbc #>UTBEG
        bcs _fwl
        ldx #NF - 1
        lda #255
        sta fwblk
-       sta fw,x
        dex
        bpl -
        rts
_fwl
        ldx #NF - 1
_fw     sec
        lda t
        sbc ft_l,x
        tay
        lda t+1
        sbc ft_h,x
        bmi _w0
        bne _wf
        cpy #RL
        bcs _wf
        lda fin,y
        .byte $2c
_wf     lda #255
        jmp _wex
_w0     lda #0
        sta fw,x
        sta fwall
        jmp _wn
_wex    sta tmp+2               ; fade out: b = t - ut
        sec
        lda t
        sbc ut_l,x
        tay
        lda t+1
        sbc ut_h,x
        bmi _wk
        bne _wz
        cpy #5
        bcs _wz
        tya                     ; 255 - b * 51
        sta tmp
        asl a
        asl a
        asl a
        asl a
        sta tmp+1
        asl a
        clc
        adc tmp+1
        adc tmp
        asl tmp
        adc tmp
        eor #$ff
        cmp tmp+2
        bcs _wk
        sta tmp+2
_wk     lda tmp+2
        sta fw,x
        and fwall
        sta fwall
        jmp _wn
_wz     lda #0
        sta fw,x
        sta fwall
_wn     dex
        bpl _fw
        lda #$ff                ; palikoiden tahkot (ensimmäiset NFB)
        ldx #NFB - 1
-       and fw,x
        dex
        bpl -
        sta fwblk
        rts

mul16x8                         ; tmp,tmp+1 = x, tmp+2 = k (etumerkittömät) -> tmp+4,tmp+5 = (x * k) >> 8
        lda tmp
        ldy tmp+2
        jsr umul8
        lda ph
        sta tmp+4
        lda tmp+1
        ldy tmp+2
        jsr umul8
        clc
        lda pl
        adc tmp+4
        sta tmp+4
        lda ph
        adc #0
        sta tmp+5
        rts

mulk                            ; tmp,tmp+1 = x (x < 1024), K = X * 256 + A -> tmp+4,tmp+5 = (x * K) >> 8
        sta tmp+2
        stx tmp+3
        lda tmp                 ; x_lo * K_lo >> 8
        ldy tmp+2
        jsr umul8
        lda ph
        sta tmp+4
        lda #0
        sta tmp+5
        ldy tmp+1               ; + x_hi * K_lo (x_hi <= 3)
        beq _h
-       clc
        lda tmp+4
        adc tmp+2
        sta tmp+4
        bcc +
        inc tmp+5
+       dey
        bne -
_h      ldy tmp+3               ; + x * K_hi
        beq _x
-       clc
        lda tmp+4
        adc tmp
        sta tmp+4
        lda tmp+5
        adc tmp+1
        sta tmp+5
        dey
        bne -
_x      rts

growk                           ; A = u, X = palikka: grow[X] = D0 + (SPAN * smooth[u]) >> 8
        tay
        txa
        asl a
        sta tmp+6
        lda smooth,y
        beq _z                  ; 0: D0
        cmp #255
        beq _f                  ; 255: valmis vakio
        sta tmp+2
        lda span_l,x
        sta tmp
        lda span_h,x
        sta tmp+1
        stx tmp+7
        jsr mul16x8
        ldx tmp+7
        lda tmp+6
        tay
        clc
        lda tmp+4
        adc d0_l,x
        sta grow,y
        lda tmp+5
        adc d0_h,x
        sta grow+1,y
        rts
_z      ldy tmp+6
        lda d0_l,x
        sta grow,y
        lda d0_h,x
        sta grow+1,y
        rts
_f      ldy tmp+6
        lda gf_l,x
        sta grow,y
        lda gf_h,x
        sta grow+1,y
        rts
gf_l    .byte <GFULL0, <GFULL1, <GFULL2
gf_h    .byte >GFULL0, >GFULL1, >GFULL2
span_l  .byte <SPAN0, <SPAN1, <SPAN2
span_h  .byte >SPAN0, >SPAN1, >SPAN2
d0_l    .byte <D0_0, <D0_1, <D0_2
d0_h    .byte >D0_0, >D0_1, >D0_2

; ---------------------------------------------------------------- kertoimet (Model.coeffs)
coeffs
        lda pitch
        ldx #0
        jsr sin8_of
        sta sp_
        lda pitch
        ldx #0
        jsr cos8_of
        sta cp_
        lda yaw
        ldx yaw+1
        jsr sin8_of
        sta sy_
        lda yaw
        ldx yaw+1
        jsr cos8_of
        sta cy_
        ; r10 = sp * sy >> 7, r12 = -(sp * cy >> 7), r20 = -(cp * sy >> 7), r22 = cp * cy >> 7
        lda sp_
        #SETMUL
        lda sy_
        eor #$80
        tay
        #MULY
        sta ph
        jsr shr7
        sta r10
        lda cy_
        eor #$80
        tay
        #MULY
        sta ph
        jsr shr7
        eor #$ff
        clc
        adc #1
        sta r12
        lda cp_
        #SETMUL
        lda sy_
        eor #$80
        tay
        #MULY
        sta ph
        jsr shr7
        eor #$ff
        clc
        adc #1
        sta r20
        lda cy_
        eor #$80
        tay
        #MULY
        sta ph
        jsr shr7
        sta r22
        lda sp_
        sta r21
        ; A = r7 * sk >> 7: a00 = cy, a02 = sy, a10 = r10, a11 = cp, a12 = r12
        lda sk
        #SETMUL
        ldx #4
-       lda _src,x
        sta _ld+1
_ld     lda cy_
        eor #$80
        tay
        #MULY
        sta ph
        jsr shr7
        ldy _dst,x
        sta $00,y
        dex
        bpl -
        rts
_src    .byte cy_, sy_, r10, cp_, r12
_dst    .byte a00, a02, a10, a11, a12

flight                          ; Model.transform_flight
        ; D = Rx(drx) Ry(dry) Rz(drz) Q7, D' = D * dsc >> 8
        lda drx
        ldx drx+1
        jsr sin8_of
        sta tmp
        lda drx
        ldx drx+1
        jsr cos8_of
        sta tmp+1
        lda dry
        ldx dry+1
        jsr sin8_of
        sta tmp+2
        lda dry
        ldx dry+1
        jsr cos8_of
        sta tmp+3
        lda drz
        ldx drz+1
        jsr sin8_of
        sta tmp+4
        lda drz
        ldx drz+1
        jsr cos8_of
        sta tmp+5
        ; yz rivit: [cy cz >> 7, -(cy sz >> 7), sy], [sz, cz, 0], [-(sy cz >> 7), sy sz >> 7, cy]
        lda tmp+3
        #SETMUL
        lda tmp+5
        jsr mul7
        sta dd+0                ; yz00
        lda tmp+4
        jsr mul7
        jsr neg
        sta dd+1                ; yz01
        lda tmp+2
        sta dd+2                ; yz02
        lda tmp+2
        #SETMUL
        lda tmp+5
        jsr mul7
        jsr neg
        sta dd+6                ; yz20
        lda tmp+4
        jsr mul7
        sta dd+7                ; yz21
        lda tmp+3
        sta dd+8                ; yz22
        ; d1j = (cx yz1j - sx yz2j) >> 7, d2j = (sx yz1j + cx yz2j) >> 7, yz1 = (sz, cz, 0)
        ldx #2
_dr     lda _yz1,x
        tay
        lda $00,y
        cpx #2
        bne +
        lda #0
+       sta mx                  ; yz1j
        lda dd+6,x
        sta mx+1                ; yz2j
        lda tmp+1
        #SETMUL
        ldy mx
        tya
        eor #$80
        tay
        #MULY
        sta ph
        lda pl
        sta xs
        lda ph
        sta xs+1
        lda mx+1
        eor #$80
        tay
        #MULY
        sta ph
        lda pl                  ; cx yz2j
        sta ys
        lda ph
        sta ys+1
        lda tmp
        #SETMUL
        lda mx+1
        eor #$80
        tay
        #MULY
        sta ph
        sec                     ; d1 = (cx yz1 - sx yz2) >> 7
        lda xs
        sbc pl
        sta pl
        lda xs+1
        sbc ph
        sta ph
        jsr shr7
        sta my,x
        lda mx
        eor #$80
        tay
        #MULY
        sta ph
        clc
        lda pl
        adc ys
        sta pl
        lda ph
        adc ys+1
        sta ph
        jsr shr7
        sta mz,x
        dex
        bpl _dr
        lda my
        sta dd+3
        lda my+1
        sta dd+4
        lda my+2
        sta dd+5
        lda mz
        sta dd+6
        lda mz+1
        sta dd+7
        lda mz+2
        sta dd+8
        ; D' = D * dsc >> 8 (dsc etumerkitön: (d * (dsc >> 1)) >> 7)
        lda dsc
        lsr a
        #SETMUL
        ldx #8
-       lda dd,x
        eor #$80
        tay
        #MULY
        sta ph
        jsr shr7
        sta dd,x
        dex
        bpl -
        ; mx_j = (a00 d0j + a02 d2j) >> 7, my_j = (a10 d0j + a11 d1j + a12 d2j) >> 7 -> mcx, mcy (^$80)
        ldx #2
_mm     lda a00
        ldy dd,x
        jsr mulacc0
        lda a02
        ldy dd+6,x
        jsr mulacc
        jsr shr7
        eor #$80
        sta mcx,x
        lda a10
        ldy dd,x
        jsr mulacc0
        lda a11
        ldy dd+3,x
        jsr mulacc
        lda a12
        ldy dd+6,x
        jsr mulacc
        jsr shr7
        eor #$80
        sta mcy,x
        dex
        bpl _mm
        rts
_yz1    .byte tmp+4, tmp+5, tmp+5

mul7                            ; A = kerrottava (etumerkillinen), kerroin asetettu -> A = p >> 7
        eor #$80
        tay
        #MULY
        sta ph
        jmp shr7
neg     eor #$ff
        clc
        adc #1
        rts
mulacc0                         ; A = kerroin, Y = kerrottava (etumerkilliset) -> pl/ph = A * Y
        sta tmp+6
        lda #0
        sta xs
        sta xs+1
        jmp mulacc_
mulacc                          ; pl/ph += A * Y
        sta tmp+6
        lda pl
        sta xs
        lda ph
        sta xs+1
mulacc_ tya
        eor #$80
        sta tmp+7
        lda tmp+6
        #SETMUL
        ldy tmp+7
        #MULY
        sta ph
        clc
        lda pl
        adc xs
        sta pl
        lda ph
        adc xs+1
        sta ph
        rts


PHASE   .macro n                ; vaiheprofiilin raja (PROF = 1)
        .if PROF
        ldx #\n
        jsr prof
        .endif
        .endm

        .include "proj.asm"
        .include "render.asm"
        .include "mark.asm"
        .include "alue.asm"
        .cerror * > $4000, "koodi yli $4000 (ruutu A): ", format("$%04x", *)

; ---------------------------------------------------------------- data
        * = SPRA + NM_N * 64
        .include "tables.asm"
        .include "gaps.asm"
        .include "bss.asm"

        .cerror * > $6000, "taulut yli $6000 (bittikartta A)"

        * = $8000                       ; pankin 2 alku (ruutu B on $bc00): piirron ajan IRQ:t, välähdys ja
                                        ; purun kopio; Hillnerin hil_prep kirjoittaa tänne vasta logo_go:n jälkeen
RIPSZ   = 27                    ; rip_irq: yhden kaistan käsittelijän tavut
rip_irq                         ; aaltoilukaista k: IRQ kaistan alkua edeltävällä rivillä (pariton, heijastuksessa
        .for k := 0, k < RIPN, k += 1   ; musta), joten $d016 vaihtuu ennen kaistan ensimmäistä riviä ilman odotusta
        pha
        lda ripv + k
        sta $d016
          .if k < RIPN - 1
        lda #<(rip_irq + (k + 1) * RIPSZ)
        sta $fffe
        lda #>(rip_irq + (k + 1) * RIPSZ)
        sta $ffff
        lda #RIP0 - 1 + (k + 1) * RIPD
          .else
        lda #<rip_end
        sta $fffe
        lda #>rip_end
        sta $ffff
        lda #51 + Y0 + ROWS - 1
          .endif
        sta $d012
        asl $d019
        pla
        rti
        .endfor
        .cerror * != rip_irq + RIPN * RIPSZ, "RIPSZ"
        .cerror RIP0 - 1 + (RIPN - 1) * RIPD >= 51 + Y0 + ROWS - 2, "rip_end liian lähellä"
rip_end pha                     ; kankaan alla tyhjä tila (ruutu B:n tavut bittikarttana näkyisivät välähdyksen
        lda #6                  ; taustalla): IRQ kankaan viimeisellä rivillä, viive (6 x 7 sykliä) sen loppuun, ja
-       sec                     ; kirjoitus seuraavan rivin vasempaan reunaan ennen badlinen DMA:ta (sykli 12)
        sbc #1
        bne -
        lda #$7b
        sta $d011
        lda #<irq_bot
        sta $fffe
        lda #>irq_bot
        sta $ffff
        lda #IRQ_BOT
        sta $d012
        asl $d019
        pla
        rti

emflash                         ; välähdys: A = 0 valkoinen, 1 vaaleanharmaa, 2 värit takaisin (colors); kankaan
        cmp #2                  ; solurivit viivaan asti (sarakkeet X0..), viivan rivi koko leveydeltä, molemmat
        beq _rs                 ; ruudut ja värimuisti (sarake kerrallaan, rivit auki kirjoitettuina)
        tay
        lda flsc,y
        ldx #COLS - 1
-
        .for r := 0, r < HZCELL, r += 1
        sta SCRA + (Y0 / 8 + r) * 40 + X0,x
        sta SCRB + (Y0 / 8 + r) * 40 + X0,x
        .endfor
        dex
        bpl -
        lda flcl,y
        ldx #COLS - 1
-
        .for r := 0, r < HZCELL, r += 1
        sta $d800 + (Y0 / 8 + r) * 40 + X0,x
        .endfor
        dex
        bpl -
        ldx #39
-       lda flsc,y
        sta SCRA + (Y0 / 8 + HZCELL) * 40,x
        sta SCRB + (Y0 / 8 + HZCELL) * 40,x
        lda flcl,y
        sta $d800 + (Y0 / 8 + HZCELL) * 40,x
        dex
        bpl -
        rts
_rs     ldx #COLS - 1
-
        .for r := 0, r < HZCELL, r += 1
        lda #CELLSCR[r]
        sta SCRA + (Y0 / 8 + r) * 40 + X0,x
        sta SCRB + (Y0 / 8 + r) * 40 + X0,x
        lda #CELLCOL[r]
        sta $d800 + (Y0 / 8 + r) * 40 + X0,x
        .endfor
        dex
        bpl -
        ldx #39
-       lda #CELLSCR[HZCELL]
        sta SCRA + (Y0 / 8 + HZCELL) * 40,x
        sta SCRB + (Y0 / 8 + HZCELL) * 40,x
        lda #CELLCOL[HZCELL]
        sta $d800 + (Y0 / 8 + HZCELL) * 40,x
        dex
        bpl -
        rts
flsc    .byte $11, $ff          ; välähdyksen ruututavut (%01, %10) ja värimuisti (%11)
flcl    .byte 1, 15

bank3                           ; purun kuva pankkiin 3: bittikartan B kankaan solurivit ja ruutu B; merkkipuskuri ja
        ldx #0                  ; taulujen 2 piirto-osa jäävät alle, T3 ei
-
        .for p := 0, p < (T3 - BMP3) / 256, p += 1
        lda BMPB + p * 256,x
        sta BMP3 + p * 256,x
        .endfor
        inx
        bne -
        .if (T3 - BMP3) & 255
-       lda BMPB + (T3 - BMP3) & $ff00,x
        sta BMP3 + (T3 - BMP3) & $ff00,x
        inx
        cpx #(T3 - BMP3) & 255
        bne -
        .endif
        ldx #0
-       lda SCRB,x
        sta SCR3,x
        lda SCRB + $100,x
        sta SCR3 + $100,x
        lda SCRB + $200,x
        sta SCR3 + $200,x
        lda SCRB + $2e8,x
        sta SCR3 + $2e8,x
        .if INTEGRATED          ; nimen spritet pankkiin 3 (purun ajan, nmout)
        lda SPRA,x
        sta SPR3,x
        lda SPRA + $100,x
        sta SPR3 + $100,x
        .endif
        inx
        bne -
        .if INTEGRATED
        ldx #NM_N - 1
-       txa
        clc
        adc #(SPR3 & $3fff) / 64
        sta SCR3 + $3f8,x
        dex
        bpl -
        .endif
        rts
        .cerror * > SPRB, "IRQ-koodi yli spritejen B"

        * = SPRB + NM_N * 64
        .include "sintab.asm"
        .include "fill.asm"
        .include "qtab.asm"

colors                          ; solurivien värit (build: cellscr %01/%10, cellcol %11), molemmat ruudut ja värimuisti
        ldx #0
        lda #0
-       sta SCRA,x
        sta SCRA+$100,x
        sta SCRA+$200,x
        sta SCRA+$2e8,x
        sta SCRB,x
        sta SCRB+$100,x
        sta SCRB+$200,x
        sta SCRB+$2e8,x
        sta $d800,x
        sta $d900,x
        sta $da00,x
        sta $dae8,x
        inx
        bne -
        ldx #0                  ; kankaan solurivi (näytön solurivi Y0 / 8 + x)
_row    lda scrrow_l,x
        sta ptr
        lda scrrow_h,x
        sta ptr+1
        ldy #X0
        lda #X0 + COLS
        sta tmp
        cpx #HZCELL             ; vaakaviivan solurivi koko leveydeltä
        bne +
        ldy #0
        lda #40
        sta tmp
+       sty tmp+1
-       lda cellscr,x
        sta (ptr),y
        iny
        cpy tmp
        bne -
        lda ptr+1               ; ruutu B
        clc
        adc #>(SCRB - SCRA)
        sta ptr+1
        ldy tmp+1
-       lda cellscr,x
        sta (ptr),y
        iny
        cpy tmp
        bne -
        lda ptr+1               ; värimuisti
        clc
        adc #>($d800 - SCRB)
        sta ptr+1
        ldy tmp+1
-       lda cellcol,x
        sta (ptr),y
        iny
        cpy tmp
        bne -
        inx
        cpx #ROWS / 8
        bne _row
        rts
        .cerror * > $a000, "täyttöketjut ja neliötaulut yli $a000 (bittikartta B)"
        .include "sprites.asm"

T2      = EBUF + $1600              ; taulut 2: demossa oma tiedosto suoraan, omassa ohjelmassa kopio
BMP3    = $e000                     ; purun kuva pankissa 3 (bank3): bittikartta ja ruutu
SCR3    = $c000
T3      = BMP3 + (Y0 + ROWS) / 8 * 320   ; purun IRQ ja taulut: pankin 3 bittikartta kankaan alla (RB:n alla tyhjänä)
        .if INTEGRATED
        * = T2
        .include "tables2.asm"
        .include "hand.asm"
T2END
        .else
        * = BMPB                        ; bittikartan B paikalla (tyhjennetään kopion jälkeen)
        .logical T2
        .include "tables2.asm"
        .include "hand.asm"
T2END
        .endlogical
        .endif
        .cerror T2END > $fffa, "taulut 2 vektoreiden päällä"
        .cerror T3 < EBUF + $1600, "T3 merkkipuskurin päällä"

        .if !INTEGRATED && HAVE_MUSIC
        * = MUSIC_LOAD
        .binary "music.bin"
        .endif
