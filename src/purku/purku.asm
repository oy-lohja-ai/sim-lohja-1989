; Hillnerin purku: lähikuvassa purkupallo heilahtaa kyltin yllä, TIM_CUE_PURKU:ssa leikataan laajaan kuvaan koko
; talosta, ja pallo iskee kolme kertaa (TIM_CUE_OSUMA, _OSUMA2, _OSUMA3): vasen pääty, oikea pääty, keskusta.
; Jokainen isku irrottaa kaksi seinäkappaletta: alaosa ja yläosa katon kanssa painuvat jäykkinä talon pohjan rivin
; alle kasaan, sisus ja puurunko jäävät näkyviin. Seuraavan iskun jälkeen siipi liukenee kasaksi (purku2:n kasa3),
; joten keskusta seisoo hetken tornina. Data: tools/gfx/purku.py
; (tools/gfx/data/hillner/purku2).
;
; Moduuli (src/scene/hil_glue.asm): purku_init (pääsäikeessä, kyltti pyörii), purku_go (ottaa näytön ja IRQ:n
; ja PALAA; kaikki työ on IRQ:ssa, raskas osa sisäkkäisenä työnä cli:n jälkeen).
;
; Näyttö: MC-bittikartat $4000 (A) ja $6000 (B), yhteinen ruutu $5c00, kuva merkkiriveillä 3-20. Lähikuva on B:ssä
; purku_go:n aikaan, ja A:han kopioidaan laaja kuva (BG2). Leikkauksessa yksi musta kehys (ruutu ja värit), sitten
; A näkyviin ja moottori piirtää takapuskuriin:
;   1. palautus: puskurin palautuslistan rivit (rivi, sarake, tavuja) työtaustasta BG2
;   2. irtoavat kappaleet: BG2:ssa kappaleen pikselit sisukseksi (TAUSTA), sama takapuskuriin, ja kappaleen
;      rivit etupuskurin palautuslistaan (se näkyy vielä pystyssä, kunnes puskuri vaihtuu)
;   3. fysiikka ja liikkuvat kappaleet pystyssä takapuskuriin; painuva kappale leikataan talon pohjan rivillä.
; Siiven liukeneminen kasaksi kirjoittaa solut (BG2, A, B, ruutu, värit) IRQ:ssa ketjun palautuksen jälkeen.

        .weak
PURKU_BASE = $8000              ; koodi ja data (tiedosto purku1)
FRAME_HOOK = 0                  ; musiikki ja demon kello kerran kehyksessä (rekisterit vapaat)
KYL_TICK = 0                    ; lähikuvan kyltti (hw 0-6) jatkuu purun alusta leikkaukseen: tick ja piirto
KYL_RENDER = 0                  ; (sisäkkäin) IRQ:ssa; pallo on hw 7
KYL_NSPR = 6                    ; kyltin hw-spritet 0..KYL_NSPR-1 (kylsym.inc: lähikuvan kyltin K_NSPR)
TIM_CUE_OSUMA2 = TIM_CUE_OSUMA + 120
TIM_CUE_OSUMA3 = TIM_CUE_OSUMA2 + 120
TIM_CUE_PURKU = TIM_CUE_OSUMA - 60
        .endweak

R_IDLE   = $0408 + 26           ; rungon tyhjäkäyntikierros (src/runko/runko.inc, vakaa ABI): CPU-mittari

        .include "gen/timing.inc"
        .include "music.inc"
        .include "hil.inc"
        .include "kylsym.inc"   ; lähikuvan kyltin sisääntulot (tools/gfx/d64.py kylsym)

KYL      = KYL_TICK != 0
PIC_ROW0 = 3
NROWS    = 144
PIC_BYTES = NROWS / 8 * 320
PICA     = $4000 + PIC_ROW0 * 320
PICB     = $6000 + PIC_ROW0 * 320
SCREEN   = $5c00
BG2      = ROM_AT               ; työtausta: laaja kuva (tiedosto purku3), sitten kappaleet leivottuina
ROM_SCR  = ROM_AT + PIC_BYTES
ROM_COL  = ROM_SCR + 720
TAUSTA   = TAUSTA_AT            ; sisus kappaleiden takana (tiedosto purku2, rivit 0..TAUSTA_ROWS*8-1)
SPRA     = $5a40                ; spritelohkot letterboxissa: A:n rivit 21-23 (7), B:n rivi 24 ja bittikartan perä
SPRB     = $7dc0                ; $7dc0-$7fbf (8), B:n rivit 0-2 (loput). A:n rivit 0-2 ovat lähikuvan kyltin koodia
SPR1     = $6000                ; ($1a00-$405f), B:n rivit 21-23 kyltin kangasta (7 spriteä $7a40-$7dbf), joten kyltti
                                ; elää purun alun yli
LINE_IRQ = 250
SHK_Y    = [7, 5, 2, 0, 4, 5, 3, 0, 2, 3, 1, 0, 2, 2, 1, 0, 1, 1, 0, 0, 1, 0, 0, 0]  ; tärähdys iskusta: yscroll
SHK_X    = [6, 4, 0, 2, 4, 2, 0, 2, 4, 2, 0, 0, 2, 2, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0]  ; ja xscroll (parillinen: MC)
SHAKE_LEN = len(SHK_Y)          ; kehystä (vaimeneva pomppu 12,5 Hz)
AFTER_LEN = SHAKE_LEN - 4       ; jälkitärähdys alkaa taulun 5. kehyksestä (heikompi kuin isku)
NPART    = 8
; kehykset: IRQ:ssa idx = DFRAME - (T_GO - 2); asetukset näkyvät kehyksellä T_GO + idx (mitattu)
IDX0     = T_GO - 2
CUT_I    = TIM_CUE_PURKU - T_GO ; leikkaus laajaan kuvaan
HIT1_I   = TIM_CUE_OSUMA - T_GO
HIT2_I   = TIM_CUE_OSUMA2 - T_GO
HIT3_I   = TIM_CUE_OSUMA3 - T_GO
END_I    = HIL_END - T_GO       ; kuva pimenee
AFTER_AT = 20                   ; jälkitärähdys iskuista 2 ja 3 (yläosa rysähtää sisään)
LIFT_AT  = 40                   ; viimeisen iskun jälkeen nosturi nostaa pallon (kehystä iskusta)
LIFT_V   = 3                    ; nosto (1/8 riviä per kehys)
FREE_PAD = 8                    ; kyltin viimeinen (sisäkkäinen) piirto päättyy viimeistään näin monta kehystä
FREE_LO  = $1a00                ; leikkauksen jälkeen; lähikuvan kyltti ja kaatoalue, A:n bittikartta alkaa $4000
FREE_END = $4000
UPD      = 2                    ; moottorin päivitysväli (kehystä)
REG_C0   = 7                    ; romahdusalueen ensimmäinen solusarake
PW0      = 1200                 ; kaatuvan alkukulmanopeus (8.8 kulmayksikköä per askel)
BAKE_COL = 11                   ; kadulle kaatuneen seinän %11 (tumma harmaa laasti; 12 ja 15 näyttäisivät pölyltä,
                                ; vaaleanpunainen 10 näyttäisi litteältä pinkiltä)
TIP_ACC  = 30                   ; kaatuvan seinän kulmakiihtyvyyden vakio-osa (+ sin / 2)
NY       = 150                  ; kaatuvan kappaleen kohti kameraa -suunnan pystykomponentti (1/256)
GRAV     = 40                   ; putoavan kappaleen kiihtyvyys (1/256 riviä per askel^2, askel = 2 kehystä)
DIS_NEXT = 30                   ; sivusiivet liukenevat kasaksi iskun 3 jälkeen (kehystä): sisus ja puurunko
DIS_WAIT = 8                    ; näkyvät siihen asti; viimeinen siipi kappaleiden jälkeen
DIS_PER  = 6                    ; liukenevia soluja kehyksessä
VF_PER   = 4                    ; vapaita soluja enintään kehyksessä
DIS_LAST = 6                    ; viimeisen siiven (keskustan) soluja kehyksessä
EMPTY_PTR = (SCREEN & $3fff) / 64
NLIST    = 250                  ; palautuslistan rivejä per puskuri
LIST_A   = $d000                ; palautuslistat (rivi, sarake, tavuja) I/O:n alla: moottori ajaa $01 = $34
LIST_B   = LIST_A + 4 * NLIST
SPRITES  = ROM_COL + 720        ; spritelohkojen 0-14 lähde (tiedosto purku3 BG2:n perässä), kopioidaan letterboxiin
SPRITES2 = TAUSTA_AT + TAUSTA_ROWS * 320   ; lohkot 15- (tiedosto purku2 sisuksen perässä)
CHAIN_BUF = $6200               ; ketjun talteenotto (3 x 145): B:n letterboxrivit 0-2 (näkymättömät, SPR1:n perässä)
ROWA     = $be40                ; kuvarivin siirtymä bittikartassa (lo 144, hi 144) ja sarake * 8, purku_init ($be40-$bfaf)
TAB_TH   = TAB_AT               ; pallon kulma per kehys (128 = 90 astetta), purku.py
TAB_PX   = TAB_AT + TAB_N - CUT_I ; nosturin x per kehys (MC-px) leikkauksesta alkaen (lähikuvassa CL_PX)

        .virtual $02
dst     .word ?
src     .word ?
t16     .word ?
mula    .byte ?
mulb    .byte ?
mulr    .word ?
zs      .byte ?
tmp     .byte ?
idx     .word ?                 ; kehys purun alusta (IRQ)
        .cerror * > $10, "IRQ:n nollasivu moottorin päällä"
        .endv
        .virtual $10            ; moottori (sisäkkäinen työ): omat, IRQ ei käytä
ep      .word ?                 ; kappaleen rivin data
eq      .word ?                 ; kohde (rivin alku)
eb      .word ?                 ; BG2 / TAUSTA
ex      .word ?                 ; kaatuvan rivin x (8.8); release: kappaleen sarake
ed      .word ?                 ; leikkaus per kohderivi (8.8)
er      .word ?                 ; lähderivi (8.8)
es      .word ?                 ; lähderivin askel (8.8)
edir    .byte ?                 ; kohderivien suunta: 0 ylös saranasta, 1 alas
ey      .byte ?                 ; kohderivi
en      .byte ?                 ; kohderivejä
ei      .byte ?
ec      .byte ?
em0     .byte ?
em1     .byte ?
etgt    .byte ?                 ; 0/1 puskuri A/B
epc     .byte ?                 ; kappale
et      .word ?
ew      .byte ?
emula   .byte ?
emulb   .byte ?
emulr   .word ?
        .cerror * > $30, "moottorin nollasivu"
        .endv
        .virtual $90            ; IRQ: liukeneminen ja pallon rata (lähikuvan kyltti $40-$85, musiikki $c0-)
dsrc    .word ?                 ; kasan solu (12 t)
dbg     .word ?                 ; BG2
dpa     .word ?                 ; A
dpb     .word ?                 ; B
dsc     .word ?                 ; ruutu
dco     .word ?                 ; värit
tp      .word ?                 ; pallon radan osoitin (IRQ; src ja dst ovat sisäkkäisen kopion)
cp      .word ?                 ; ketjun rivi näkyvässä puskurissa
cbm     .word ?                 ; solun bittikartan lähde (cellput)
cscr    .byte ?
ccol    .byte ?
        .endv

; seuraavan kohtauksen lataus purun aikana: arvot labeleina, jotta d64.py syms vie ne parts.inc:iin.
; purku_go palaa heti (kohtaustaulu jatkaa), FREE_LO..FREE_END-1 vapaa demon kehyksestä purku_free_at alkaen,
; koko muisti paitsi resident ja musiikki kuvan pimennyttyä (HIL_END)
        .virtual TIM_CUE_PURKU + FREE_PAD
purku_free_at
        .endv
        .virtual FREE_LO
purku_free_lo
        .endv
        .virtual FREE_END
purku_free_end
        .endv

        * = PURKU_BASE

; ---------------------------------------------------------------- rajapinta
; purku_init: pääsäikeessä kyltin pyöriessä (ei koske näyttöön): spritet letterboxiin, laaja kuva takapuskuriin A,
; kappaleiden tila ja ajonaikaiset taulut
purku_init
        lda #<sprites
        sta src
        lda #>sprites
        sta src+1
        lda #<SPRA
        sta dst
        lda #>SPRA
        sta dst+1
        ldx #1                  ; lohkot 0-6 (448 tavua)
        jsr copy_pages
        ldy #7 * 64 - 256
        jsr copy_rest
        lda #<(sprites + 7 * 64)
        sta src
        lda #>(sprites + 7 * 64)
        sta src+1
        lda #<SPRB
        sta dst
        lda #>SPRB
        sta dst+1
        ldx #2                  ; lohkot 7-14
        jsr copy_pages
        lda #<SPRITES2
        sta src
        lda #>SPRITES2
        sta src+1
        lda #<SPR1
        sta dst
        lda #>SPR1
        sta dst+1
        ldx #2                  ; lohkot 15- (enintään 8)
        jsr copy_pages
        lda #<BG2               ; laaja kuva puskuriin A (näkyviin leikkauksessa)
        sta src
        lda #>BG2
        sta src+1
        lda #<PICA
        sta dst
        lda #>PICA
        sta dst+1
        jsr copy_pic
        ldx #NPIECE - 1
-       lda pc_vs,x
        sta vi,x
        lda pc_m0,x
        sta smi,x
        lda pc_r0,x
        sta smr,x
        lda #0
        sta smb,x
        sta ps,x
        sta pdust,x
        dex
        bpl -
        lda #0
        sta lnA
        sta lnB
        sta hitn
        sta t16                 ; kuvarivien siirtymät: +1, merkkirivin lopussa +313
        sta t16+1
        tay
-       lda t16
        sta rowa_lo,y
        lda t16+1
        sta rowa_hi,y
        tya
        and #7
        cmp #7
        beq _cr
        inc t16                 ; merkkirivin sisällä (alin tavu 64 k + j, ei ylivuotoa)
        jmp _nx
_cr     clc
        lda t16
        adc #<313
        sta t16
        lda t16+1
        adc #>313
        sta t16+1
_nx     iny
        cpy #NROWS
        bne -
        ldy #39                 ; sarake * 8
-       tya
        asl a
        asl a
        asl a
        sta colx8l,y
        tya
        lsr a
        lsr a
        lsr a
        lsr a
        lsr a
        sta colx8h,y
        dey
        bpl -
        rts

; purku_quiet (pääsäie, runko: S_CALL leikkauksen jälkeen): odottaa, että kappaleet ovat kasassa ja kasa
; valmis ja näkyvissä on B, sitten moottori pois ja hiukkaset pois (lohkot 0-6 ovat A:n letterboxissa). Palaa,
; kun $4000-$5bff on vapaa seuraavan kohtauksen latauksille; pallo, ketju ja kuva jatkuvat IRQ:ssa.
purku_quiet
-       jsr R_IDLE
        lda dwing               ; kaikki siivet liuenneet
        cmp #4
        bcc -
        lda dact
        bne -
        sei
        lda jbusy
        ora flip
        bne +
        lda front
        bne ++                  ; B näkyvissä
+       cli
        jmp -
+       lda #0
        sta eng
        sta mburst
        sta dburst
        ldx #NPART - 1
-       sta pkind,x
        dex
        bpl -
        lda #1
        sta quiet
        cli
        rts

; purku_go: ottaa näytön (lähikuva B:ssä) ja IRQ:n, vapauttaa pallon ja palaa
purku_go
        sei
        lda #$35
        sta $01
        lda #$78                ; ruutu $5c00, bittikartta $6000
        sta $d018
        lda #1
        sta front
        lda $d01c               ; pallo (hw 7) monivärinen ja kuvan edessä, kyltin hw 0-6 ennallaan
        ora #$80
        sta $d01c
        lda $d01b
        and #$7f
        sta $d01b
        lda #0
        sta flip
        sta jbusy
        sta eng
        sta wide
        lda #9
        sta $d025
        lda #15
        sta $d026
        lda #$80
        sta bmask
        lda #7
        sta bsp
        .if KYL
        lda #1
        sta kylon
        lda #(1 << KYL_NSPR) - 1  ; kyltin spritet eivät ole hiukkasten ($3f sammuttaisi 7. kyltin spriten)
        sta kblk
        .endif
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        lda #LINE_IRQ
        sta $d012
        lda #$30
        sta $d011
        lda #1
        sta $d01a
        lda #$ff
        sta $d019
        cli
        rts

; ---------------------------------------------------------------- IRQ (alareuna, rivi 250)
irq     pha
        txa
        pha
        tya
        pha
        lda $01
        pha
        lda #$35
        sta $01
        lda #$ff
        sta $d019
        lda DFRAME              ; leikkaus laajaan kuvaan ensimmäisenä (värimuisti säteen edellä); näkyy
        cmp #<(IDX0 + CUT_I)    ; kehyksellä TIM_CUE_PURKU (mitattu)
        bne +
        lda DFRAME+1
        cmp #>(IDX0 + CUT_I)
        bne +
        jsr cut
+       .if FRAME_HOOK
        jsr FRAME_HOOK
        .endif
        inc frame
        sec                     ; kehys purun alusta
        lda DFRAME
        sbc #<IDX0
        sta idx
        lda DFRAME+1
        sbc #>IDX0
        sta idx+1
        lda #0                  ; tärähdys: koko kuva yscroll 0-7 ja xscroll 0-6, spritet mukana (yoff, sx_*).
        tay                     ; $d011 ja $d016 heti IRQ:n alussa, kun säde on kuvan alapuolella: myöhemmin
        ldx shake               ; kirjoitettuna yscroll vaihtuisi kesken kuvan (rivit venyisivät)
        beq +
        dec shake
        lda shk_y,x
        ldy shk_x,x
+       sta yoff
        ora #$30
        sta $d011
        tya
        ora #$18                ; MC, 40 saraketta; vasempaan reunaan jää $d021:n musta
        sta $d016
        tya
        clc
        adc #12
        sta sx_p
        adc #12
        sta sx_b
        jsr chain_off           ; ketju pois näkyvästä puskurista ennen vaihtoa
        lda flip
        beq +
        lda front
        eor #1
        sta front
        jsr show_front
        lda #0
        sta flip
+       lda idx                 ; purun loppu: kuva pimeäksi, spritet pois (seuraava kohtaus); näytön
        cmp #<(END_I + 1)       ; sammutus näkyy kehystä aiemmin kuin $d018 (mitattu)
        lda idx+1
        sbc #>(END_I + 1)
        bcc +
        lda #0
        sta $d015
        sta eng
        sta kylon
        lda #$0b
        sta $d011
        jmp irq_out
+       .if KYL
        lda kylon
        beq +
        jsr KYL_TICK
+       .endif
        jsr timeline
        jsr dissolve
        jsr vfree
        jsr ball_step
        jsr chain_step
        jsr parts_step
irq_job lda jbusy               ; raskas työ sisäkkäin: kyltin piirto ja moottori (seuraavat IRQ:t keskeyttävät)
        bne irq_out
        inc jbusy
        cli
        .if KYL
        lda kylon
        beq +
        jsr KYL_RENDER
+       .endif
        jsr engine
        dec jbusy
irq_out pla
        sta $01
        pla
        tay
        pla
        tax
        pla
        rti

; leikkaus: kyltti ja spritet pois (ei sprite-DMA:ta), A näkyviin heti rivillä 250, sitten laajan kuvan ruutu ja
; värit riveittäin ylhäältä alas säteen edellä (4 solua kierroksella noin 810 sykliä merkkiriviä kohden; säde
; ehtii kuvan riville r noin 7 000 + 464 r syklissä), joten leikkaus on suoraan kuvasta kuvaan ilman mustaa.
; Sitten pallo yhtenä spritenä ja moottori päälle (B = BG2).
cut     lda #0
        sta $d015
        sta kylon
        sta kblk
        lda #$70                ; A näkyviin
        sta $d018
        .for blk = 0, blk < 3, blk += 1
        ldx #0
-       lda ROM_SCR + blk * 240,x
        sta SCREEN + PIC_ROW0 * 40 + blk * 240,x
        lda ROM_SCR + blk * 240 + 1,x
        sta SCREEN + PIC_ROW0 * 40 + blk * 240 + 1,x
        lda ROM_SCR + blk * 240 + 2,x
        sta SCREEN + PIC_ROW0 * 40 + blk * 240 + 2,x
        lda ROM_SCR + blk * 240 + 3,x
        sta SCREEN + PIC_ROW0 * 40 + blk * 240 + 3,x
        lda ROM_COL + blk * 240,x
        sta $d800 + PIC_ROW0 * 40 + blk * 240,x
        lda ROM_COL + blk * 240 + 1,x
        sta $d800 + PIC_ROW0 * 40 + blk * 240 + 1,x
        lda ROM_COL + blk * 240 + 2,x
        sta $d800 + PIC_ROW0 * 40 + blk * 240 + 2,x
        lda ROM_COL + blk * 240 + 3,x
        sta $d800 + PIC_ROW0 * 40 + blk * 240 + 3,x
        inx
        inx
        inx
        inx
        cpx #240
        bne -
        .next
        lda #0
        sta front
        jsr show_front
        lda #1
        sta wide
        sta eng
        sta copyb
        sta bmask               ; pallo hw 0:ksi (murskan ja pölyn edessä)
        lda #0
        sta bsp
        lda #$ff
        sta $d01c
        lda #0
        sta $d017
        sta $d01d
        rts

show_front
        ldx front
        lda d018tab,x
        sta $d018
        rts
d018tab .byte $70, $78           ; ruutu $5c00, bittikartta $4000 / $6000


; ---------------------------------------------------------------- aikajana
; iskut kehyksillä (pallon rata osuu iskukohtaan samalla kehyksellä, purku.py); kappaleet irtoavat oman iskunsa
; jälkeen viiveellään (alaosa ensin), viimeisen iskun jälkeen pallo nostetaan
timeline
        ldx hitn                ; seuraava isku
        cpx #3
        bcs +
        lda idx
        cmp hit_lo,x
        bne +
        lda idx+1
        cmp hit_hi,x
        bne +
        jsr hit
+       lda hitn
        bne +
        rts
+       inc hitf                ; kehyksiä viimeisestä osumasta
        bne +
        dec hitf
+       ldx #NPIECE - 1         ; irtoavat kappaleet: oma isku tullut ja viive kulunut
-       lda ps,x
        bne _np
        lda pc_hit,x
        cmp hitn
        beq +
        bcs _np
        lda #1                  ; aiemman iskun kappale: heti
        sta ps,x
        bne _np
+       lda hitf
        cmp pc_del,x
        bcc _np
        lda #1
        sta ps,x
_np     dex
        bpl -
        lda hitn                ; iskut 2 ja 3: yläosa rysähtää, jälkitärähdys
        cmp #2
        bcc +
        lda hitf
        cmp #AFTER_AT
        bne +
        lda #AFTER_LEN
        sta shake
+       lda hitn
        cmp #3
        bne +
        lda hitf
        cmp #LIFT_AT            ; nosturi vetää pallon ylös
        bcc +
        clc
        lda lift
        adc #LIFT_V
        sta lift
        bcc +
        inc lift+1
+       rts

hit_lo  .byte <HIT1_I, <HIT2_I, <HIT3_I
hit_hi  .byte >HIT1_I, >HIT2_I, >HIT3_I

hit     inc hitn                ; osuma: tärähdys, murska iskukohdasta
        lda #0
        sta hitf

        lda #SHAKE_LEN
        sta shake
        lda #6
        sta mburst
        ldx hitn
        lda hit_x - 1,x
        sta mpx
        lda hit_y - 1,x
        sta mpy
        rts

; ---- siipi liukenee kasaksi: kun iskun dwing kappaleet ovat poissa (ps = 4) ja seuraavasta iskusta on
; DIS_NEXT kehystä (viimeinen siipi: DIS_WAIT kappaleiden jälkeen), sen kasan solut (BG2, A, B, ruutu,
; värit), DIS_PER kehyksessä. Ketju on jo palautettu, ja moottori ei enää koske siiven soluihin.
dissolve
        lda dact
        bne _run
        lda dwing
        cmp #3
        beq +                   ; viimeinen: kappaleiden jälkeen
        lda hitn                ; sivusiivet vasta iskun 3 jälkeen: kasan harmaat eivät ole kuvassa iskun 3
        cmp #3                  ; tärähdyksessä, ja sisus ja puurunko näkyvät tornin vieressä
        bcc _x
        lda hitf
        cmp #DIS_NEXT
        bcc _x
+       lda dwing
        cmp hitn
        beq +
        bcs _x                  ; isku ei ole vielä tullut
+       ldx #NPIECE - 1
-       lda pc_hit,x
        cmp dwing
        bne +
        lda ps,x
        cmp #4
        bne _x                  ; kappale vielä liikkeessä
+       dex
        bpl -
        inc dwait
        lda dwait
        cmp #DIS_WAIT
        bcc _x
        lda #0
        sta dwait
        lda dwing               ; siiven solut kasa_w0..kasa_w1
        asl a
        tax
        lda kasa_w1 - 2,x
        sec
        sbc kasa_w0 - 2,x
        sta dleft
        lda kasa_w1 - 1,x
        sbc kasa_w0 - 1,x
        sta dleft+1
        lda kasa_w0 - 2,x       ; dsrc = KASA_AT + 12 * alku
        sta dsrc
        lda kasa_w0 - 1,x
        sta dsrc+1
        asl dsrc                ; * 4
        rol dsrc+1
        asl dsrc
        rol dsrc+1
        lda dsrc                ; * 3
        sta t16
        lda dsrc+1
        sta t16+1
        asl dsrc
        rol dsrc+1
        clc
        lda dsrc
        adc t16
        sta dsrc
        lda dsrc+1
        adc t16+1
        sta dsrc+1
        clc
        lda dsrc
        adc #<KASA_AT
        sta dsrc
        lda dsrc+1
        adc #>KASA_AT
        sta dsrc+1
        ldy #DIS_PER            ; viimeinen siipi hitaammin: purku jatkuu kuvan pimenemiseen asti
        lda dwing
        cmp #3
        bne +
        ldy #DIS_LAST
+       sty dper
        inc dwing
        lda #1
        sta dact
_run    lda dper
        sta dcnt
_c      lda dleft
        ora dleft+1
        bne +
        lda #0
        sta dact
_x      rts
+       lda dleft
        bne +
        dec dleft+1
+       dec dleft
        ldy #0                  ; solu: ruudun siirtymä, bittikartta 8 t, ruutu, väri
        lda (dsrc),y
        sta dsc
        iny
        lda (dsrc),y
        sta dsc+1
        jsr cellptr
        ldy #10
        lda (dsrc),y
        sta cscr
        iny
        lda (dsrc),y
        sta ccol
        clc
        lda dsrc
        adc #2
        sta cbm
        lda dsrc+1
        adc #0
        sta cbm+1
        jsr cellput
        clc
        lda dsrc
        adc #12
        sta dsrc
        bcc +
        inc dsrc+1
+       dec dcnt
        beq +
        jmp _c
+       rts

; ---- solun osoittimet: dsc = ruudun siirtymä o -> dsc ruutu, dco värit, dbg/dpa/dpb bittikartat (t16 = 8 o)
cellptr lda dsc
        sta t16
        lda dsc+1
        sta t16+1
        asl t16
        rol t16+1
        asl t16
        rol t16+1
        asl t16
        rol t16+1
        clc
        lda dsc
        adc #<($d800 + PIC_ROW0 * 40)
        sta dco
        lda dsc+1
        adc #>($d800 + PIC_ROW0 * 40)
        sta dco+1
        clc
        lda dsc
        adc #<(SCREEN + PIC_ROW0 * 40)
        sta dsc
        lda dsc+1
        adc #>(SCREEN + PIC_ROW0 * 40)
        sta dsc+1
        clc
        lda t16
        adc #<BG2
        sta dbg
        lda t16+1
        adc #>BG2
        sta dbg+1
        clc
        lda t16
        adc #<PICA
        sta dpa
        lda t16+1
        adc #>PICA
        sta dpa+1
        clc
        lda t16
        adc #<PICB
        sta dpb
        lda t16+1
        adc #>PICB
        sta dpb+1
        rts

; ---- solu näkyviin: 8 tavua (cbm) BG2:een ja molempiin puskureihin, ruutu cscr ja väri ccol (X säilyy)
cellput ldy #7
-       lda (cbm),y
        sta (dbg),y
        sta (dpa),y
        sta (dpb),y
        dey
        bpl -
        iny
        lda cscr
        sta (dsc),y
        lda ccol
        sta (dco),y
        rts

; ---- vapaat solut: kun kappale on painunut solun alle, solu sisuksesta kokonaan omalla paletillaan (talon
; takainen maisema täysvärinä, purku2:n tausta_v2), enintään VF_PER kehyksessä
vfree   lda quiet               ; purku_quietin jälkeen sisusta ($c000-) ei enää lueta
        beq +
        rts
+       lda #VF_PER
        sta dcnt
        ldx #NPIECE - 1
_p      lda ps,x
        cmp #2
        bcc +
        jsr sfree               ; ensin sisuksen solut (0/2/9/15), sitten vapaat (maisema)
        lda dcnt
        beq _x
+       lda ps,x
        cmp #2
        bcc _n
        lda #255                ; valmis: kaikki solut
        ldy ps,x
        cpy #4
        beq +
        lda pts,x               ; näkyvä yläreuna
+       sta vtop
_l      ldy vi,x
        tya
        cmp pc_ve,x
        bcs _n
        lda vrow,y              ; solun alareuna + 1 <= yläreuna
        cmp vtop
        beq +
        bcs _n
+       lda vlo,y
        sta dsc
        lda vhi,y
        sta dsc+1
        lda vscr,y
        sta cscr
        lda vcol,y
        sta ccol
        jsr cellptr
        clc
        lda t16
        adc #<TAUSTA
        sta cbm
        lda t16+1
        adc #>TAUSTA
        sta cbm+1
        jsr cellput
        inc vi,x
        dec dcnt
        beq _x
        bne _l
_n      dex
        bpl _p
_x      rts
vtop    .byte 0
vi      .fill NPIECE, 0

; ---- kappaleen X sisuksen solut: merkkirivi kerrallaan, kun yläreuna on rivin alla (maski sm_lo/hi, sarakkeet
; x0/4 + bitti), solu sisuksesta romahdusalueen paletilla; dcnt solua enintään
sfree   lda #255                ; näkyvä yläreuna (valmis: kaikki)
        ldy ps,x
        cpy #4
        beq +
        lda pts,x
+       sta vtop
_row    lda smi,x
        cmp pc_m0 + 1,x
        bcs _x                  ; kaikki rivit tehty
        lda smr,x               ; rivin ylin rivi < yläreuna: osa solusta paljastunut, sisus heti omilla
        asl a                   ; väreillään (kappaleen %01/%10 ovat samat 2/9, vain %11 vaihtuu solurivillä)
        asl a
        asl a
        cmp vtop
        bcs _x
        ldy smi,x
        lda sm_lo,y
        sta smm
        lda sm_hi,y
        sta smm+1
_bit    ldy smb,x
        cpy #16
        bcs _nrow
        lda bitm,y              ; bitti y (bitm 8 alkiota: ylätavulle y - 8)
        cpy #8
        bcc +
        lda bitm - 8,y
        and smm+1
        jmp ++
+       and smm
+       beq _nb
        lda smr,x               ; solu: rivi * 40 + x0 / 4 + bitti
        tay
        lda row40l,y
        sta dsc
        lda row40h,y
        sta dsc+1
        lda pc_x0,x
        lsr a
        lsr a
        clc
        adc smb,x
        adc dsc
        sta dsc
        bcc +
        inc dsc+1
+       jsr cellptr
        clc
        lda t16
        adc #<TAUSTA
        sta cbm
        lda t16+1
        adc #>TAUSTA
        sta cbm+1
        lda #PAL3_SCR
        sta cscr
        lda #PAL3_COL
        sta ccol
        jsr cellput
        inc smb,x
        dec dcnt
        bne _bit
        rts
_nb     inc smb,x
        jmp _bit
_nrow   lda #0
        sta smb,x
        inc smi,x
        inc smr,x
        jmp _row
_x      rts
smm     .word 0
smi     .fill NPIECE, 0
smr     .fill NPIECE, 0
smb     .fill NPIECE, 0
row40l  .byte <(range(18) * 40)
row40h  .byte >(range(18) * 40)
vlo     = VF_AT
vhi     = VF_AT + VF_N
vscr    = VF_AT + 2 * VF_N
vcol    = VF_AT + 3 * VF_N
vrow    = VF_AT + 4 * VF_N


; ---- pallo: kulma ja nosturin x radasta (TAB_TH, TAB_PX) kehyksellä idx. Lähikuvassa 2 x 2 MC-spriteä (hw 0-3,
; vasen yläkulma keskipisteestä -12, -21), laajassa yksi (hw 0, -6, -10). Keskipiste x = nosturi + LX sin,
; y = tukipisteen rivi + LY cos (- nosto).
ball_step
        lda wide                ; lähikuvassa ei palloa
        bne +
        jmp _hide
+       lda idx+1               ; taulun indeksi (viimeinen kehys pitää paikkansa)
        cmp #>TAB_N
        bcc +
        bne _last
        lda idx
        cmp #<TAB_N
        bcc +
_last   lda #<(TAB_N - 1)
        sta t16
        lda #>(TAB_N - 1)
        sta t16+1
        jmp _tab
+       lda idx
        sta t16
        lda idx+1
        sta t16+1
_tab    clc
        lda t16
        adc #<TAB_PX
        sta tp
        lda t16+1
        adc #>TAB_PX
        sta tp+1
        ldy #0
        lda (tp),y
        sta bpx
        clc
        lda t16
        adc #<TAB_TH
        sta tp
        lda t16+1
        adc #>TAB_TH
        sta tp+1
        lda (tp),y
        sta bth
        bpl +                   ; |kulma|
        eor #$ff
        clc
        adc #1
+       sta tmp
        tax
        lda ball_sin,x          ; vaaka: LX sin
        sta mula
        lda wide
        bne _wx
        lda #CL_LX
        sta mulb
        lda #CL_PX
        sta bpx
        jmp _mx
_wx     lda #W_LX
        sta mulb
_mx     jsr mul8
        lda bth                 ; keskipiste x = bpx +- LX sin (16 bittiä)
        bmi _xn
        clc
        lda bpx
        adc mulr+1
        sta bx
        lda #0
        adc #0
        sta bx+1
        jmp _yy
_xn     sec
        lda bpx
        sbc mulr+1
        sta bx
        lda #0
        sbc #0
        sta bx+1
_yy     lda #128                ; cos = sin(128 - |kulma|)
        sec
        sbc tmp
        tax
        lda ball_sin,x
        sta mula
        sta tmp
        lda wide
        bne _wy
        lda #CL_LY - 256        ; LY cos >> 8 = cos + (LY - 256) cos >> 8
        sta mulb
        jsr mul8
        clc                     ; y = PY + LY cos
        lda #<(CL_PY & $ffff)
        adc mulr+1
        sta by
        lda #>(CL_PY & $ffff)
        adc #0
        sta by+1
        clc
        lda by
        adc tmp
        sta by
        bcc +
        inc by+1
+       jmp _pos
_wy     lda #W_LY
        sta mulb
        jsr mul8
        clc
        lda #<(W_PY & $ffff)
        adc mulr+1
        sta by
        lda #>(W_PY & $ffff)
        adc #0
        sta by+1
        lda lift+1              ; nosto (1/8 riviä)
        sta tmp
        lda lift
        lsr tmp
        ror a
        lsr tmp
        ror a
        lsr tmp
        ror a
        sta t16
        sec
        lda by
        sbc t16
        sta by
        lda by+1
        sbc tmp
        sta by+1
_pos    ldx wide                ; vasen yläkulma
        sec
        lda bx
        sbc half_w,x
        sta bx
        lda bx+1
        sbc #0
        sta bx+1
        sec
        lda by
        sbc half_h,x
        sta by
        lda by+1
        sbc #0
        sta by+1
        ; näkyvissä, jos rivi -korkeus..143. Kuvan yläpuolella (letterbox) näkyvä osa leikataan: spriten rivit
        ; kopioidaan leikkauspuskuriin ylimmästä näkyvästä alkaen, ja sprite alkaa kuvan riviltä 0.
        lda ptrtab + SPR_BALLX
        sta bptr
        lda by+1
        beq _yp
        cmp #$ff
        bne _hide
        lda #0                  ; k = -rivi (piilossa olevat näyttörivit)
        sec
        sbc by
        ldx wide
        cmp ball_h,x
        bcs _hide
        cpx #0
        bne +
        lsr a                   ; lähikuva: Y-laajennettu, 2 näyttöriviä per datarivi
+       sta tmp
        asl a                   ; ohitettavat tavut 3 k
        adc tmp
        tax
        ldy #0
-       lda ballspr,x
        sta clipspr,y
        iny
        inx
        cpx #63
        bcc -
        lda #0
-       sta clipspr,y
        iny
        cpy #63
        bcc -
        lda ptrtab + SPR_CLIP
        sta bptr
        lda #0
        sta by
        sta by+1
        beq _ok
_yp     lda by
        cmp #144
        bcs _hide
_ok     ldx bsp                 ; pallon hw-sprite: lähikuvassa 7 (kyltti 0-6), laajassa 0 (murskan edessä)
        txa
        asl a
        tay
        clc                     ; Y = 71 + rivi (+ tärähdys)
        lda by
        adc #71
        adc yoff
        sta $d001,y
        lda bx                  ; X = 24 + 2x (9 bittiä); vasemman reunan yli X + 504
        asl
        sta bxs
        lda bx+1
        rol
        sta bxs+1
        clc
        lda bxs
        adc sx_b                ; 24 + tärähdys
        sta bxs
        lda bxs+1
        adc #0
        sta bxs+1
        bpl +
        clc
        lda bxs
        adc #<504
        sta bxs
        lda bxs+1
        adc #>504
        sta bxs+1
+       lda bxs
        sta $d000,y
        lda bmask
        eor #$ff
        and $d010
        ldy bxs+1
        beq +
        ora bmask
+       sta $d010
        lda bptr                ; pallo_x: lähikuvassa laajennettu (24 x 42 MC-px), laajassa ei
        sta SCREEN + $3f8,x
        lda #11
        sta $d027,x
        ldx wide
        lda bmask
        eor #$ff
        sta tmp
        and $d017
        ora bexp,x
        sta $d017
        lda tmp
        and $d01d
        ora bexp,x
        sta $d01d
        lda $d01c
        ora bmask
        sta $d01c
        lda $d015
        ora bmask
        sta $d015
        lda bmask
        sta ballon
        rts
_hide   lda bmask
        eor #$ff
        and $d015
        sta $d015
        lda #0
        sta ballon
        rts
bexp    .byte $80, 0            ; laajennus (lähikuva hw 7)
ball_h  .byte 42, 21
half_w  .byte 12, 6
half_h  .byte 21, 10


; ---- ketju: bittikarttaviiva pallon yläreunasta kuvan yläreunaan tukipisteen suuntaan (lenkit: joka 4. rivi
; tyhjä), mustana (%00). Piirretään IRQ:ssa näkyvään puskuriin; alla olevat tavut talteen ja takaisin
; seuraavassa kehyksessä ennen puskurin vaihtoa (chain_off).
chain_off
        ldx chn                 ; vanha ketju pois (ennen puskurin vaihtoa)
        beq +
-       dex
        lda chlo,x
        sta _cha+1
        lda chhi,x
        sta _cha+2
        lda chv,x
_cha    sta $ffff
        txa
        bne -
        stx chn
+       rts

chain_step
        lda ballon
        bne +
        rts
+       lda by+1                ; ketjun alin rivi = pallon yläreuna - 1 (rivi 0..143)
        beq +
        rts                     ; pallo kuvan yläpuolella tai alla
+       lda by
        bne +
        rts
+       cmp #145
        bcc +
        lda #144
+       sec
        sbc #1
        sta chy
        ldx wide
        clc                     ; pallon keskipiste x
        lda bx
        adc half_w,x
        sta chx
        sec                     ; dx = xk - tukipiste (|dx| < 128)
        sbc bpx
        sta chdx
        lda half_h,x            ; nimittäjä (yk - PY + nosto) / 2, yk = by + puolikorkeus
        clc
        adc by
        sta cht
        lda by+1
        adc #0
        sta cht+1
        sec
        lda cht
        sbc py_lo,x
        sta cht
        lda cht+1
        sbc py_hi,x
        sta cht+1
        clc
        lda wide
        beq +
        lda lift+1              ; laajassa nosturi nousee pallon mukana
        sta tmp
        lda lift
        lsr tmp
        ror a
        lsr tmp
        ror a
        lsr tmp
        ror a
        clc
        adc cht
        sta cht
        lda cht+1
        adc tmp
        sta cht+1
+       lsr cht+1
        lda cht
        ror
        sta chden
        lda chdx                ; s = |dx| * 128 / den (8.8, |s| < 1)
        bpl +
        eor #$ff
        clc
        adc #1
+       lsr
        sta cht+1
        lda #0
        ror
        sta cht
        jsr div16
        lda chdx
        bpl +
        lda #0
        sec
        sbc chs
        sta chs
        lda #0
        sbc chs+1
        sta chs+1
+       lda chs                 ; kahden rivin askel
        asl a
        sta chs2
        lda chs+1
        rol a
        sta chs2+1
        lda chx                 ; x riviltä chy: xk - (puolikorkeus + 1) s
        sta chxa+1
        lda #0
        sta chxa
        ldx wide
        ldy half_h,x
        iny
-       sec
        lda chxa
        sbc chs
        sta chxa
        lda chxa+1
        sbc chs+1
        sta chxa+1
        dey
        bne -
        ldx #0                  ; talteenoton indeksi
        lda chxa+1              ; alin rivi: osoite kerran, sitten rivi kerrallaan ylös (-1, merkkirivin
        cmp #160                ; ylärajalla -313) ja sarake +-8, kun x ylittää 4 px:n rajan
        bcs _end
        lsr
        lsr
        sta chcol
        tay
        lda colx8l,y
        sta cp
        lda colx8h,y
        sta cp+1
        ldy chy
        clc
        lda cp
        adc rowa_lo,y
        sta cp
        lda cp+1
        adc rowa_hi,y
        sta cp+1
        ldy front
        clc
        lda cp
        adc pic_lo1,y
        sta cp
        lda cp+1
        adc pic_hi1,y
        sta cp+1
_row    lda chxa+1              ; lenkki joka toisella rivillä (2 riviä kerrallaan ylös)
        and #3
        tay
        lda chmask,y
        sta chm
        ldy #0
        lda (cp),y
        sta chv,x
        and chm
        sta (cp),y
        lda cp
        sta chlo,x
        lda cp+1
        sta chhi,x
        inx
        sec                     ; 2 riviä ylös: x -= 2 s
        lda chxa
        sbc chs2
        sta chxa
        lda chxa+1
        sbc chs2+1
        sta chxa+1
        cmp #160
        bcs _end                ; kuvan reunan yli
        lsr
        lsr
        cmp chcol
        beq _up
        sta chcol               ; sarake +-1 (|2 s| < 4 px)
        bcc _l
        clc
        lda cp
        adc #8
        sta cp
        bcc _up
        inc cp+1
        bcs _up
_l      sec
        lda cp
        sbc #8
        sta cp
        bcs _up
        dec cp+1
_up     lda chy                 ; rivit r -> r - 2: merkkirivin sisällä -2, rajan yli -314
        and #6
        bne _in
        sec
        lda cp
        sbc #<314
        sta cp
        lda cp+1
        sbc #>314
        sta cp+1
        jmp _dy
_in     sec
        lda cp
        sbc #2
        sta cp
        bcs _dy
        dec cp+1
_dy     dec chy
        dec chy
        bpl _row
_end    stx chn
        rts
py_lo   .byte <(CL_PY & $ffff), <(W_PY & $ffff)
py_hi   .byte >(CL_PY & $ffff), >(W_PY & $ffff)

; chs = cht / chden (16 / 8 -> 16)
div16   lda #0
        ldx #16
-       asl cht
        rol cht+1
        rol
        bcs +
        cmp chden
        bcc ++
+       sbc chden
        inc cht
+       dex
        bne -
        lda cht
        sta chs
        lda cht+1
        sta chs+1
        rts

chmask  .byte $3f, $cf, $f3, $fc
chn     .byte 0
chy     .byte 0
chx     .byte 0
chdx    .byte 0
chden   .byte 0
cht     .word 0
chs     .word 0
chxa    .word 0
chcol   .byte 0
chs2    .word 0
chm     .byte 0
chlo    = CHAIN_BUF             ; talteenotto (ajonaikainen)
chhi    = chlo + 145
chv     = chhi + 145

; ---------------------------------------------------------------- moottori (sisäkkäinen työ IRQ:ssa)
; Kerran UPD kehyksessä, kun edellinen vaihto on tehty: palautus, irtoavat kappaleet, fysiikka, piirto
; takapuskuriin ja vaihtopyyntö. Päivitys saa kestää useita kehyksiä (IRQ:t ja musiikki jatkuvat).
;
; Kappaleen tila ps: 0 paikallaan, 1 irtoaa (aikajana), 2 liikkuu, 4 valmis (painunut kasaan). Kappale putoaa
; pystyssä jäykkänä (alareuna phy, 8.8 riviä; nopeus pvy) ja painuu leikkausrivillä kasaan: rivit sen alla jäävät
; piirtämättä (draw_up). Kaatuva seinä ei näytä jäykältä liikkeeltä, joten kaikki kappaleet painuvat.

engine  lda eng
        beq +
        lda flip
        bne +
        lda frame
        sec
        sbc elast
        cmp #UPD
        bcs ++
+       rts
+       lda $01                 ; palautuslistat I/O:n alla; IRQ:t kytkevät I/O:n itselleen ja palauttavat $01:n
        pha
        lda #$34
        sta $01
        jsr eng_upd
        pla
        sta $01
        rts

eng_upd lda copyb               ; leikkauksen jälkeen ensin BG2 puskuriin B (A on näkyvissä)
        beq _go
        lda #<BG2
        sta src
        lda #>BG2
        sta src+1
        lda #<PICB
        sta dst
        lda #>PICB
        sta dst+1
        jsr copy_pic
        lda #0
        sta copyb
        lda frame
        sta elast
        sta plast
        rts
_go     lda frame
        sta elast
        lda front
        eor #1
        sta etgt
        jsr restore_back
        ldx front               ; irtoavien suorakaiteet etupuskurin listaan
        jsr list_sel
        ldx #NPIECE - 1         ; irtoavat kappaleet
-       lda ps,x
        cmp #1
        bne +
        stx epc
        jsr release
        ldx epc
+       dex
        bpl -
        lda frame               ; fysiikka kuluneiden kehysten mukaan (2 kehystä / askel, pariton jää
        sec                     ; seuraavalle päivitykselle)
        sbc plast
        lsr a
        beq _d
        cmp #8
        bcc +
        lda #8
+       sta esteps
        asl a
        adc plast               ; C = 0
        sta plast
-       ldx #NPIECE - 1
-       lda ps,x
        cmp #2
        bne +
        jsr physics
+       dex
        bpl -
        dec esteps
        bne --
_d      ldx etgt                ; piirretyt rivit takapuskurin listaan
        jsr list_sel
        ldx #NPIECE - 1         ; liikkuvat takapuskuriin
_p      stx epc
        lda ps,x
        cmp #3
        beq _bake
        cmp #2
        bne _n
        lda pk,x
        bne _up
        jsr pose                ; kaatuva
        jsr draw_tilt
        lda ermin               ; ylin piirretty rivi
        jmp _top
_up     jsr draw_up
        lda phy_hi,x            ; yläreuna (pohjan alla: 0 riviä näkyvissä)
        sec
        sbc pc_h,x
        bcs _top
        lda #0
_top    pha                     ; näkyvä yläreuna = edellisen päivityksen (etupuskuri), uusi talteen
        lda ptn,x
        sta pts,x
        pla
        sta ptn,x
        jmp _n
_bake   lda #4                  ; kadulla: leivotaan BG2:een ja romahdusalueen väreihin, piirretään vielä
        sta ps,x                ; takapuskuriin, ja suorakaide myös etupuskurin listaan (palautuu BG2:sta, kun
        jsr pose                ; puskuri on seuraavan kerran takana)
        lda etgt
        pha
        lda #2
        sta etgt
        ldx epc
        jsr draw_tilt
        pla
        sta etgt
        ldx epc
        jsr pose
        jsr draw_tilt
        ldx front
        jsr list_sel
        ldx front
        jsr list_add
        lda #1
        sta erows
        ldx etgt
        jsr list_sel
_n      ldx epc
        dex
        bpl _p
        lda #1
        sta flip
        rts
esteps  .byte 0

; ---- osoittimet: ey = rivi, ec = sarake -> eq (kohde etgt), eb (BG2), et (TAUSTA); X ja Y muuttuvat
ptrs    ldy ey
        ldx ec
        clc
        lda rowa_lo,y
        adc colx8l,x
        sta et
        lda rowa_hi,y
        adc colx8h,x
        sta et+1                ; siirtymä kuvan alusta
        ldy etgt
        lda et                  ; C = 0
        adc tgt_lo,y
        sta eq
        lda et+1
        adc tgt_hi,y
        sta eq+1
        clc
        lda et
        adc #<BG2
        sta eb
        lda et+1
        adc #>BG2
        sta eb+1
        clc
        lda et
        adc #<TAUSTA
        sta et
        lda et+1
        adc #>TAUSTA
        sta et+1
        rts

; ---- vain kohde: eq = etgt + rivi ey, sarake ec (piirto); X ja Y muuttuvat
ptrq    ldy ey
        ldx ec
        clc
        lda rowa_lo,y
        adc colx8l,x
        sta eq
        lda rowa_hi,y
        adc colx8h,x
        sta eq+1
        ldy etgt
        clc
        lda eq
        adc tgt_lo,y
        sta eq
        lda eq+1
        adc tgt_hi,y
        sta eq+1
        rts
rowa_lo = ROWA
rowa_hi = ROWA + NROWS
colx8l  = ROWA + 2 * NROWS      ; sarake * 8 (purku_init)
colx8h  = colx8l + 40
tgt_lo  .byte <PICA, <PICB, <BG2
tgt_hi  .byte >PICA, >PICB, >BG2

; ---- palautus: takapuskurin (etgt) listan rivit BG2:sta
restore_back
        ldx etgt
        lda ln_tab,x
        sta ew
        lda #0
        sta ln_tab,x
        lda lly_lo,x
        sta _ly + 1
        lda lly_hi,x
        sta _ly + 2
        lda llc_lo,x
        sta _lc + 1
        lda llc_hi,x
        sta _lc + 2
        lda lln_lo,x
        sta _ln + 1
        lda lln_hi,x
        sta _ln + 2
        lda llr_lo,x
        sta _lr + 1
        lda llr_hi,x
        sta _lr + 2
        ldx #0
_e      cpx ew
        bcs _x
_ly     lda $ffff,x
        sta ey
_lc     lda $ffff,x
        sta ec
_lr     lda $ffff,x
        sta rrows
_ln     lda $ffff,x
        asl a
        asl a
        asl a
        sta rbytes              ; tavuja * 8
        stx rix
        lda ey                  ; varmuus: vain kuvan rivit
        cmp #NROWS
        bcs _nx
        jsr ptrs                ; suorakaide: rrows riviä alkaen ey, osoittimet riveittäin eteenpäin
_row    ldy rbytes
-       tya                     ; tavut (n - 1) * 8 ... 0
        sec
        sbc #8
        tay
        lda (eb),y
        sta (eq),y
        tya
        bne -
        dec rrows
        beq _nx
        inc ey
        lda ey
        cmp #NROWS
        bcs _nx
        and #7
        beq _cb
        inc eq                  ; merkkirivin sisällä +1 (osoitteet eivät ylitä sivua: 8 * sarake + rivi)
        inc eb
        jmp _row
_cb     clc                     ; seuraava merkkirivi: +313
        lda eq
        adc #<313
        sta eq
        lda eq+1
        adc #>313
        sta eq+1
        clc
        lda eb
        adc #<313
        sta eb
        lda eb+1
        adc #>313
        sta eb+1
        jmp _row
_nx     ldx rix
        inx
        bne _e
_x      rts
rbytes  .byte 0
rix     .byte 0
rrows   .byte 0

; ---- palautuslistan valinta (X = puskuri 0/1): list_addin operandit kerran vaiheessa, ei joka rivillä
list_sel
        lda lly_lo,x
        sta list_add._a + 1
        sta list_add._a2 + 1
        sta list_add._a3 + 1
        sta list_add._a4 + 1
        lda lly_hi,x
        sta list_add._a + 2
        sta list_add._a2 + 2
        sta list_add._a3 + 2
        sta list_add._a4 + 2
        lda llc_lo,x
        sta list_add._b + 1
        sta list_add._b2 + 1
        lda llc_hi,x
        sta list_add._b + 2
        sta list_add._b2 + 2
        lda lln_lo,x
        sta list_add._c + 1
        sta list_add._c2 + 1
        lda lln_hi,x
        sta list_add._c + 2
        sta list_add._c2 + 2
        lda llr_lo,x
        sta list_add._d + 1
        sta list_add._d2 + 1
        sta list_add._d3 + 1
        sta list_add._d4 + 1
        lda llr_hi,x
        sta list_add._d + 2
        sta list_add._d2 + 2
        sta list_add._d3 + 2
        sta list_add._d4 + 2
        rts

; ---- listaan (list_sel): rivi ey, sarake ec, tavuja ew; X = puskuri (rivimäärä ln_tab)
list_add                        ; erows riviä (1 = yksi rivi); sama sarake ja leveys
        ldy ln_tab,x
        beq _new
        dey
_b2     lda $ffff,y
        cmp ec
        bne _new0
_c2     lda $ffff,y
        cmp ew
        bne _new0
_a2     lda $ffff,y             ; edellinen jatkuu alaspäin tähän?
        clc
_d2     adc $ffff,y
        cmp ey
        beq _join
        lda ey                  ; tai tämä päättyy edellisen yläpuolelle (piirto saranasta ylös)
        clc
        adc erows
_a3     cmp $ffff,y
        bne _new0
        lda ey
_a4     sta $ffff,y
_join   lda erows
        clc
_d3     adc $ffff,y
        bcs _new0
_d4     sta $ffff,y
        rts
_new0   ldy ln_tab,x
_new    cpy #NLIST
        bcs _x
        inc ln_tab,x
        lda ey
_a      sta $ffff,y
        lda ec
_b      sta $ffff,y
        lda ew
_c      sta $ffff,y
        lda erows
_d      sta $ffff,y
_x      rts

; ---- kappale X lähtee: BG2:n pikselit sisukseksi (TAUSTA), sama takapuskuriin, rivit etupuskurin listaan
release lda #2
        sta ps,x
        lda #0
        sta pvy,x
        sta phy,x
        sta pa,x
        sta pa_hi,x
        lda #<PW0               ; kaatuva lähtee heti liikkeelle (isku työntää)
        sta pw,x
        lda #>PW0
        sta pw_hi,x
        lda pc_kind,x
        sta pk,x
        lda pc_y0,x             ; näkyvä yläreuna levossa
        sta ptn,x
        sta pts,x
        lda pc_v0,x             ; alkunopeus (purku.py: isku 3 romahtaa heti nopeasti, sitten hidastuu)
        sta pvy_hi,x
        lda pc_y0,x             ; alareuna
        clc
        adc pc_h,x
        sta phy_hi,x
        lda pc_splo,x
        sta _s1 + 1
        sta _s2 + 1
        sta _s3 + 1
        sta _s4 + 1
        lda pc_sphi,x
        sta _s1 + 2
        sta _s2 + 2
        sta _s3 + 2
        sta _s4 + 2
        lda pc_y0,x
        sta ey
        lda pc_h,x
        sta en
        lda pc_x0,x
        lsr a
        lsr a
        sta ex                  ; sarake
        lda #0
        sta ei
_r      lda ei                  ; rivin tavut i0..i1 ja reunamaskit (purku.py)
        asl a
        asl a
        tay
_s1     lda $ffff,y
        clc
        adc ex
        sta ec
        iny
_s2     lda $ffff,y
        sta ei8
        iny
_s3     lda $ffff,y
        sta em0
        iny
_s4     lda $ffff,y
        sta em1
        jsr ptrs
        ldy ei8
-       lda #$ff                ; maski: reunoilla em0/em1
        cpy #0
        bne +
        and em0
+       cpy ei8
        bne +
        and em1
+       sta em
        eor #$ff
        and (eb),y
        sta etmp
        lda (et),y
        and em
        ora etmp
        sta (eb),y
        sta (eq),y
        tya
        beq +
        sec
        sbc #8
        tay
        jmp -
+       inc ey
        inc ei
        dec en
        bne _r
        ldx epc                 ; koko kappaleen suorakaide etupuskurin listaan (näkyy vielä pystyssä)
        lda pc_y0,x
        sta ey
        lda pc_h,x
        sta erows
        lda pc_x0,x
        lsr a
        lsr a
        sta ec
        lda pc_wb,x
        clc
        adc ec
        cmp #41
        bcc +
        lda #40
+       sec
        sbc ec
        sta ew
        lda front
        tax
        jsr list_add
        lda #1
        sta erows
        rts


; ---- fysiikka: yksi askel kappaleelle X (2 kehystä): painovoima, nopeus enintään pc_vm (purku.py)
physics lda pk,x
        bne _fall
        lda pa_hi,x             ; kaatuu: kulmakiihtyvyys TIP_ACC + sin / 2, kadulle 90 asteeseen
        jsr sin64
        lsr a
        clc
        adc #TIP_ACC
        clc
        adc pw,x
        sta pw,x
        bcc +
        inc pw_hi,x
+       clc
        lda pa,x
        adc pw,x
        sta pa,x
        lda pa_hi,x
        adc pw_hi,x
        sta pa_hi,x
        cmp #64
        bcc _x
        lda #64                 ; kadulla: leivotaan, pölyä seinän keskelle
        sta pa_hi,x
        lda #0
        sta pa,x
        lda #3
        sta ps,x
        lda #3
        clc
        adc dburst
        sta dburst
        lda pc_px,x
        sta dpx
        lda pc_h,x              ; sarana + 0,2 h
        lsr a
        lsr a
        clc
        adc phy_hi,x
        sta dpy
        rts
_fall   lda pvy,x               ; yli pc_vm: hidastuu kohti sitä (alkurysäys), muuten painovoima
        cmp pc_vmlo,x
        lda pvy_hi,x
        sbc pc_vmhi,x
        bcc _acc
        sec
        lda pvy,x
        sbc #GRAV
        sta pvy,x
        bcs +
        dec pvy_hi,x
+       lda pvy,x
        cmp pc_vmlo,x
        lda pvy_hi,x
        sbc pc_vmhi,x
        bcs _mv
        bcc _set
_acc    clc
        lda pvy,x
        adc #GRAV
        sta pvy,x
        bcc +
        inc pvy_hi,x
+       lda pvy,x
        cmp pc_vmlo,x
        lda pvy_hi,x
        sbc pc_vmhi,x
        bcc _mv
_set    lda pc_vmlo,x
        sta pvy,x
        lda pc_vmhi,x
        sta pvy_hi,x
_mv     clc
        lda phy,x
        adc pvy,x
        sta phy,x
        lda phy_hi,x
        adc pvy_hi,x
        sta phy_hi,x
        cmp pc_fl,x             ; alareuna pohjan rivillä: pölyä kerran
        bcc _x
        sec
        sbc pc_h,x
        cmp pc_fl,x             ; yläreunakin pohjan alla: kappale on painunut kasaan
        bcc +
        lda #4
        sta ps,x
+       lda pdust,x             ; vähän pölyä pohjan eteen (kappale näkyy painuessaan)
        bne _x
        inc pdust,x
        lda #2
        clc
        adc dburst
        sta dburst
        lda pc_px,x
        sta dpx
        lda pc_fl,x
        clc
        adc #10
        sta dpy
_x      rts

; ---- kappaleen X piirto pystyssä takapuskuriin (etgt): rivit yläreunasta (sarana - h) alas leikkausriviin asti.
; Leikkaus: pohja (pc_fl), tai saman iskun alaosan yläreuna, kun alaosa on vielä paikallaan. Kohde ja data rivi
; kerrallaan eteenpäin (put_row). Rajaava suorakaide palautuslistaan.
draw_up ldy pc_lo,x
        lda ps,y
        cmp #2
        lda pc_y0,y
        bcc +
        lda pc_fl,x
+       sta eclip
        lda phy_hi,x            ; yläreuna
        sec
        sbc pc_h,x
        sta ey
        sta ey0
        lda eclip
        sec
        sbc ey
        bcc _none
        beq _none
        cmp pc_h,x
        bcc +
        lda pc_h,x
+       sta en
        sta ek
        lda pc_wb,x
        sta ewb
        lda pc_d0lo,x
        sta ep
        lda pc_d0hi,x
        sta ep+1
        lda pc_splo,x
        sta et
        lda pc_sphi,x
        sta et+1
        lda pc_x0,x
        lsr a
        lsr a
        sta ec
        sta ec0
        jsr ptrq
_row    jsr put_row
        clc                     ; seuraava rivi: data + wb, rivit + 4, kohde +1 (merkkirivin lopussa +313)
        lda ep
        adc ewb
        sta ep
        bcc +
        inc ep+1
+       clc
        lda et
        adc #4
        sta et
        bcc +
        inc et+1
+       lda ey
        and #7
        cmp #7
        beq _cr
        inc eq
        bne _nx
        inc eq+1
        bne _nx
_cr     clc
        lda eq
        adc #<313
        sta eq
        lda eq+1
        adc #>313
        sta eq+1
_nx     inc ey
        dec ek
        bne _row
        lda ey0                 ; suorakaide: rivit ey0.., sarakkeet c0..c0 + wb - 1
        sta ey
        lda en
        sta erows
        lda ec0
        sta ec
        lda ewb
        sta ew
        ldx etgt
        jsr list_add
        lda #1
        sta erows
_none   ldx epc
        rts

; ---- yksi kappaleen rivi: data (ep), rivin tavut i0..i1 ja reunamaskit (et), kohde eq = rivin sarake x0/4
put_row ldy #0
        lda (et),y
        sta ei0
        iny
        lda (et),y
        sta ei8
        iny
        lda (et),y
        sta em0
        iny
        lda (et),y
        sta em1
        lda ep
        sta dmask._dd + 1
        sta _df + 1
        lda ep+1
        sta dmask._dd + 2
        sta _df + 2
        lda ei0                 ; Y = 8 i (kohde), X = i (data)
        asl a
        asl a
        asl a
        tay
        clc
        adc ei8
        sta eyend
        ldx ei0
        lda em0
        cpy eyend
        bne +
        and em1                 ; yksi tavu
+       jsr dmask
        cpy eyend
        beq _x
-       inx
        tya
        clc
        adc #8
        tay
        cpy eyend
        beq _lb
_df     lda $ffff,x
        sta (eq),y
        jmp -
_lb     lda em1
        jsr dmask
_x      rts

; ---- kaatuva kappale X asennossa (pose) kohteeseen etgt (0/1 puskuri, 2 BG2 = leivonta): kohderivi k
; saranasta ylös (edir 0) tai alas (1), lähderivi h - 1 - k * es (alareunasta), x = x0 + k * ed (tavuun).
; Rajaava suorakaide palautuslistaan (puskurit) tai romahdusalueen väreiksi (BG2).
draw_tilt
        lda pc_wb,x
        sta ewb
        lda pc_h,x              ; lähderivi h - 1: data ja rivitiedot sen kohdalle
        sec
        sbc #1
        sta ecur
        sta emula
        lda ewb
        sta emulb
        jsr emul8
        clc
        lda pc_d0lo,x
        adc emulr
        sta ep
        lda pc_d0hi,x
        adc emulr+1
        sta ep+1
        lda ecur
        asl a
        asl a
        clc
        adc pc_splo,x
        sta et
        lda pc_sphi,x
        adc #0
        sta et+1
        lda #0
        sta er
        sta er+1
        sta ek
        sta ermax
        sta ecmax
        lda #$ff
        sta ermin
        sta ecmin
_row    lda pc_h,x              ; lähderivi h - 1 - r
        clc
        sbc er+1
        bcc _done
        sta esr
-       lda ecur                ; data ja rivitiedot taaksepäin lähderiviin
        cmp esr
        beq _t
        dec ecur
        sec
        lda ep
        sbc ewb
        sta ep
        bcs +
        dec ep+1
+       sec
        lda et
        sbc #4
        sta et
        bcs -
        dec et+1
        jmp -
_t      lda ehy                 ; kohderivi
        ldy edir
        bne +
        clc
        sbc ek
        bcc _nr                 ; kuvan yläpuolella
        jmp ++
+       clc
        adc ek
+       cmp #NROWS
        bcs _nr
        sta ey
        lda ex+1
        lsr a
        lsr a
        sta ec
        jsr ptrq
        jsr put_row
        ldx epc
        lda ey                  ; suorakaide
        cmp ermin
        bcs +
        sta ermin
+       cmp ermax
        bcc +
        sta ermax
+       lda ec
        cmp ecmin
        bcs +
        sta ecmin
+       clc
        adc ewb
        cmp ecmax
        bcc _nr
        sta ecmax
_nr     ldx epc
        clc                     ; seuraava kohderivi
        lda er
        adc es
        sta er
        lda er+1
        adc es+1
        sta er+1
        clc
        lda ex
        adc ed
        sta ex
        lda ex+1
        adc ed+1
        sta ex+1
        inc ek
        lda ek
        cmp en
        bcc _row
_done   lda ermin
        cmp #$ff
        beq _x
        sta ey
        lda ermax
        sec
        sbc ermin
        adc #0                  ; C = 1: + 1
        sta erows
        lda ecmax
        cmp #41
        bcc +
        lda #40
+       sec
        sbc ecmin
        sta ew
        lda ecmin
        sta ec
        lda etgt
        cmp #2
        bcs _bk
        tax
        jsr list_add
        lda #1
        sta erows
_x      ldx epc
        rts
_bk     jsr bake_cols           ; BG2: suorakaiteen solut romahdusalueen paletiksi (kasa kadulla)
        lda #1
        sta erows
        ldx epc
        rts

; ---- leivotun suorakaiteen (ey, erows, ec, ew) solut romahdusalueen paletiksi
bake_cols
        lda ey
        lsr a
        lsr a
        lsr a
        sta ecr
        lda ey
        clc
        adc erows
        sec
        sbc #1
        lsr a
        lsr a
        lsr a
        sta ecr1
-       ldy ecr
        lda row40l,y
        clc
        adc #<(SCREEN + PIC_ROW0 * 40)
        sta et
        lda row40h,y
        adc #>(SCREEN + PIC_ROW0 * 40)
        sta et+1
        clc
        lda et
        adc ec
        sta et
        sta eb
        lda et+1
        adc #0
        sta et+1
        clc
        adc #>($d800 - SCREEN)
        sta eb+1
        lda #$35                ; värimuisti näkyviin (moottori ajaa $01 = $34)
        sta $01
        ldy ew
        dey
-       lda #PAL3_SCR
        sta (et),y
        lda #BAKE_COL
        sta (eb),y
        dey
        bpl -
        lda #$34
        sta $01
        inc ecr
        lda ecr
        cmp ecr1
        beq --
        bcc --
        rts
ecr     .byte 0
ecr1    .byte 0

; ---- asento kappaleelle X: sarana (ehy), suunta (edir), kohderivit (en), lähderivin askel (es, 8.8),
; leikkaus per kohderivi (ed, 8.8), alku-x (ex, 8.8). f = cos - NY sin (kappale kaatuu kohti kameraa ja
; lyhenee, käännyttyään saranan alle)
pose    lda pa_hi,x
        jsr cos64
        sta ecos
        lda pa_hi,x
        jsr sin64
        sta esin
        bne _tilt
        lda pc_h,x              ; pystyssä: kaikki rivit, askel 1
        sta en
        lda #0
        sta edir
        sta es
        sta ed
        sta ed+1
        lda #1
        sta es+1
        jmp _x0
_tilt   sta emula               ; f = cos - NY sin
        lda #NY
        sta emulb
        jsr emul8
        lda ecos
        sec
        sbc emulr+1
        bcs _f1b
        eor #$ff                ; negatiivinen: kappale saranan alapuolella
        adc #1
        ldy #1
        bne _f2
_f1b    ldy #0
_f2     sty edir
        cmp #8
        bcs +
        lda #8                  ; vähintään ohut viiva
+       sta emula
        lda pc_h,x
        sta emulb
        jsr emul8                ; en = h * f
        lda emulr+1
        bne +
        lda #1
+       sta en
        lda pc_h,x              ; askel = h / en (8.8)
        sta et+1
        lda #0
        sta et
        lda en
        sta ediv
        jsr div16e
        lda esin                ; leikkaus per kohderivi: nx * sin / 64 * askel
        sta emula
        lda pc_nx,x
        bpl +
        eor #$ff
        clc
        adc #1
+       sta emulb
        jsr emul8                ; |nx| * sin (16)
        ldy #6                  ; / 64 -> 8.8 px per lähderivi
-       lsr emulr+1
        ror emulr
        dey
        bne -
        lda emulr
        sta emula
        lda es+1                ; * askel (kokonaisosa riittää)
        sta emulb
        jsr emul8
        lda pc_nx,x
        bpl +
        lda #0
        sec
        sbc emulr
        sta emulr
        lda #0
        sbc emulr+1
        sta emulr+1
+       lda emulr
        sta ed
        lda emulr+1
        sta ed+1
_x0     lda #0
        sta ex
        lda pc_x0,x
        sta ex+1
        lda phy_hi,x
        sta ehy
        rts

; es = et / ediv (16 / 8 -> 16)
div16e  lda #0
        ldy #16
-       asl et
        rol et+1
        rol a
        bcs +
        cmp ediv
        bcc ++
+       sbc ediv
        inc et
+       dey
        bne -
        lda et
        sta es
        lda et+1
        sta es+1
        rts

emul8   lda #0                  ; emulr = emula * emulb (moottorin oma: IRQ:n pallo käyttää mul8:aa), X säilyy
        ldy #8
        lsr emula
-       bcc +
        clc
        adc emulb
+       ror a
        ror emula
        dey
        bne -
        sta emulr+1
        lda emula
        sta emulr
        rts

; sin/cos 0..64 -> 0..255 (ball_sin: 128 = 90 astetta)
sin64   cmp #65
        bcc +
        lda #64
+       asl a
        tay
        lda ball_sin,y
        rts
cos64   cmp #65
        bcc +
        lda #64
+       eor #$ff
        sec
        adc #64
        asl a
        tay
        lda ball_sin,y
        rts
ecos    .byte 0
esin    .byte 0
ehy     .byte 0
ediv    .byte 0
ecur    .byte 0
esr     .byte 0
ermin   .byte 0
ermax   .byte 0
ecmin   .byte 0
ecmax   .byte 0
ey0     .byte 0
ec0     .byte 0
eyend   .byte 0
eclip   .byte 0
ewb     .byte 0
ek      .byte 0

; maskattu tavu: A = maski, X = data, Y = kohde (eq); X ja Y säilyvät
dmask   sta em
        eor #$ff
        and (eq),y
        sta etmp
_dd     lda $ffff,x
        and em
        ora etmp
        sta (eq),y
        rts
ei0     .byte 0
ei8     .byte 0
em      .byte 0
etmp    .byte 0

; palautuslistat: rivi, sarake, tavuja (puskurit A ja B)
ln_tab  .byte 0, 0
lnA     = ln_tab
lnB     = ln_tab + 1
lly_lo  .byte <LIST_A, <LIST_B
lly_hi  .byte >LIST_A, >LIST_B
llc_lo  .byte <(LIST_A + NLIST), <(LIST_B + NLIST)
llc_hi  .byte >(LIST_A + NLIST), >(LIST_B + NLIST)
lln_lo  .byte <(LIST_A + 2 * NLIST), <(LIST_B + 2 * NLIST)
lln_hi  .byte >(LIST_A + 2 * NLIST), >(LIST_B + 2 * NLIST)
llr_lo  .byte <(LIST_A + 3 * NLIST), <(LIST_B + 3 * NLIST)
llr_hi  .byte >(LIST_A + 3 * NLIST), >(LIST_B + 3 * NLIST)
erows   .byte 1

; kappaleiden ajonaikainen tila
ps      .fill NPIECE, 0
pk      .fill NPIECE, 0         ; 0 kaatuu kadulle, 2 painuu
ptn     .fill NPIECE, 0         ; piirretty yläreuna (takapuskuri)
pts     .fill NPIECE, 0         ; näkyvä yläreuna (etupuskuri): solujen värit vaihtuvat sen yläpuolella
pa      .fill NPIECE, 0         ; kulma (8.8, 64 = 90 astetta)
pa_hi   .fill NPIECE, 0
pw      .fill NPIECE, 0
pw_hi   .fill NPIECE, 0
pvy     .fill NPIECE, 0
pvy_hi  .fill NPIECE, 0
phy     .fill NPIECE, 0
phy_hi  .fill NPIECE, 0
pdust   .fill NPIECE, 0

parts_step
        lda mburst              ; uusia murskaparvia iskukohdasta
        beq _nm
        dec mburst
        lda #1
        jsr spawn
        bcs _nm                 ; ei vapaata paikkaa
        lda mpx
        sta pxh,x
        lda mpy
        sta pyh,x
        jsr rnd                 ; vx -1..1 MC-px / kehys, vy ylös, sitten painovoima
        and #$7f
        sec
        sbc #$40                ; -64..63
        sta pvxl,x
        and #$80
        beq +
        lda #$ff
+       sta pvxh,x
        asl pvxl,x
        rol pvxh,x
        jsr rnd
        ora #$80
        sta pvyl,x
        lda #$ff
        sta pvyh,x
        jsr rnd
        and #3
        clc
        adc #SPR_MURSKA
        sta pshp,x
_nm     lda dburst              ; pölyä kohtaan, johon kappale osui
        beq +
        dec dburst
        lda #2
        jsr spawn
        bcs +
        jsr rnd
        and #15
        clc
        adc dpx
        sec
        sbc #8
        sta pxh,x
        lda dpy
        sec
        sbc #12
        sta pyh,x
        lda #0
        sta pvxl,x
        sta pvxh,x
        jsr rnd
        and #$3f
        ora #$c0
        sta pvyl,x
        lda #$ff
        sta pvyh,x
+       ldx #NPART - 1
        lda ballon
        ora kblk
        sta pmask
_p      lda pkind,x
        bne +
        jmp _off
+       lda bitm,x
        and pmask
        beq +
        jmp _nx                 ; pallo käyttää spriteä
+       dec plife,x
        bne +
        lda #0
        sta pkind,x
        jmp _off
+       clc
        lda pxl,x
        adc pvxl,x
        sta pxl,x
        lda pxh,x
        adc pvxh,x
        sta pxh,x
        clc
        lda pyl,x
        adc pvyl,x
        sta pyl,x
        lda pyh,x
        adc pvyh,x
        sta pyh,x
        lda pkind,x
        cmp #1
        bne _dust
        clc                     ; murska: painovoima
        lda pvyl,x
        adc #$10
        sta pvyl,x
        lda pvyh,x
        adc #0
        sta pvyh,x
        lda pshp,x
        jmp _draw
_dust   clc                     ; pöly: nousu hidastuu, muoto iän mukaan
        lda pvyl,x
        adc #2
        sta pvyl,x
        lda pvyh,x
        adc #0
        sta pvyh,x
        lda plife,x
        lsr
        lsr
        lsr
        lsr
        cmp #6
        bcc +
        lda #5
+       eor #$ff
        sec
        adc #5
        ldy plife,x             ; vanha (laajennettu, plife < 60) pöly: karkea poly_x
        cpy #60
        bcs +
        adc #SPR_POLYX          ; C = 0
        bcc _draw
+       clc
        adc #SPR_POLY
_draw   tay
        lda ptrtab,y
        sta SCREEN + $3f8,x
        lda pkind,x
        cmp #1
        bne +
        lda #2                  ; murska tiilenpunainen, pöly 12
        .byte $2c
+       lda #12
        sta $d027,x
        txa
        asl
        tay
        lda pyh,x               ; vain kuvan alueella (ei letterboxissa): rivit 12..139
        cmp #140
        bcs _off
        cmp #12
        bcc _off
        clc
        adc #71 - 10
        adc yoff
        sta $d001,y
        lda pkind,x             ; vanha pöly laajennetaan (48 x 42), keskitetään
        cmp #2
        bne _ne
        lda plife,x
        cmp #60
        bcs _ne
        lda bitm,x
        ora $d017
        sta $d017
        sta $d01d
        lda $d001,y
        sec
        sbc #10
        sta $d001,y
        lda pxh,x
        sec
        sbc #6
        jmp _xx
_ne     lda bitm,x
        eor #$ff
        and $d017
        sta $d017
        sta $d01d
        lda pxh,x
_xx     asl
        php
        clc
        adc sx_p                ; 24 - 12 + tärähdys
        sta $d000,y
        lda #0
        rol
        plp
        adc #0
        beq +
        lda bitm,x
        ora $d010
        sta $d010
        jmp ++
+       lda bitm,x
        eor #$ff
        and $d010
        sta $d010
+       lda bitm,x
        ora $d015
        sta $d015
        jmp _nx
_off    lda bitm,x
        and pmask
        bne _nx
        lda bitm,x
        eor #$ff
        and $d015
        sta $d015
_nx     dex
        bmi +
        jmp _p
+       rts

; vapaa hiukkaspaikka lajille A (1 murska, 2 pöly): X = paikka, C = 1 jos ei vapaata
spawn   sta tmp
        ldx quiet               ; purku_quietin jälkeen ei uusia hiukkasia
        bne _no
        ldx #NPART - 1
-       lda pkind,x
        bne +
        lda bmask
        ora kblk
        and bitm,x
        bne +
        lda tmp
        sta pkind,x
        lda #0
        sta pxl,x
        sta pyl,x
        lda #90
        sta plife,x
        clc
        rts
+       dex
        bpl -
_no     sec
        rts

rnd     lda seed
        asl
        bcc +
        eor #$1d
+       sta seed
        rts


; ---------------------------------------------------------------- apurutiinit
copy_pic                        ; kuva (NROWS riviä) src -> dst tarkasti: letterboxin spritet ja kyltin kangas säilyvät
        ldx #>PIC_BYTES
        jsr copy_pages
        ldy #<PIC_BYTES
copy_rest                       ; Y tavua (1-255) src -> dst
-       dey
        lda (src),y
        sta (dst),y
        tya
        bne -
        rts

copy_pages                      ; X sivua src -> dst
        ldy #0
-       lda (src),y
        sta (dst),y
        iny
        bne -
        inc src+1
        inc dst+1
        dex
        bne -
        rts

mul8    lda #0                  ; mulr = mula * mulb (IRQ)
        ldx #8
        lsr mula
-       bcc +
        clc
        adc mulb
+       ror
        ror mula
        dex
        bne -
        sta mulr+1
        lda mula
        sta mulr
        rts

pic_lo1 .byte <PICA, <PICB
pic_hi1 .byte >PICA, >PICB

ptrtab                          ; spritelohkojen osoittimet: 0-6 SPRA, 7-14 SPRB, 15- SPR1
        .byte range(7) + (SPRA & $3fff) / 64
        .byte range(8) + (SPRB & $3fff) / 64
        .byte range(SPR_N + 1 - 15) + (SPR1 & $3fff) / 64

frame   .byte 0
flip    .byte 0
front   .byte 1
wide    .byte 0                 ; 0 lähikuva, 1 laaja kuva (leikkauksesta)
shk_y   .byte 0, SHK_Y[::-1]    ; shake laskee alaspäin: shk_y[SHAKE_LEN] on iskun kehys
shk_x   .byte 0, SHK_X[::-1]
shake   .byte 0
yoff    .byte 0
sx_b    .byte 24                ; pallon ja hiukkasten X-perusta + xscroll
sx_p    .byte 12
bth     .byte 0
bpx     .byte 0                 ; tukipisteen x (MC-px)
bx      .word 0
bxs     .word 0
lift    .word 0
by      .word 0
ballon  .byte 0
bmask   .byte $80               ; pallon hw-sprite (hiukkaset eivät käytä): lähikuvassa 7, laajassa 0
bsp     .byte 7
bptr    .byte 0
hitn    .byte 0                 ; osumia tähän mennessä
hitf    .byte 0                 ; kehyksiä viimeisestä osumasta
mburst  .byte 0
mpx     .byte 0                 ; murskan lähtöpiste (iskukohta)
mpy     .byte 0
dburst  .byte 0
dpx     .byte 80
dpy     .byte 120
dact    .byte 0                 ; liukeneminen käynnissä
dwing   .byte 1                 ; seuraava liukeneva siipi (isku)
dwait   .byte 0
dleft   .word 0
dcnt    .byte 0
dper    .byte DIS_PER
pmask   .byte 0
seed    .byte $5a
kylon   .byte 0                 ; lähikuvan kyltti käynnissä (KYL)
kblk    .byte 0                 ; hiukkasilta kielletyt spritet kyltin aikana
jbusy   .byte 0                 ; sisäkkäinen työ käynnissä
quiet   .byte 0                 ; purku_quiet: moottori pysähtynyt
eng     .byte 0                 ; moottori päällä (leikkauksesta)
copyb   .byte 0
elast   .byte 0
plast   .byte 0
bitm    .byte 1, 2, 4, 8, 16, 32, 64, 128
pkind   .fill NPART, 0
plife   .fill NPART, 0
pshp    .fill NPART, 0
pxl     .fill NPART, 0
pxh     .fill NPART, 0
pyl     .fill NPART, 0
pyh     .fill NPART, 0
pvxl    .fill NPART, 0
pvxh    .fill NPART, 0
pvyl    .fill NPART, 0
pvyh    .fill NPART, 0

        .include "purku.inc"    ; taulut ja vakiot (tools/gfx/purku.py)
sprites = SPRITES
ballspr = SPR1 + (SPR_BALLX - 15) * 64      ; pallon sprite (purku_initin kopio)
clipspr = SPR1 + (SPR_CLIP - 15) * 64       ; leikattu pallo kuvan yläreunassa
SPR_CLIP = SPR_N                            ; vapaa lohko SPR1:n perässä
code_end
        .cerror code_end > $9800, "purun koodi yli kappaledatan: ", format("$%04x", code_end)
        .cerror PIECE_AT != $9800 || TAUSTA_AT != $c000 || ROM_AT != $e000, "purku.py: osoitteet"
        .cerror TAB_AT + 2 * TAB_N > ROWA || colx8h + 40 > $c000, "kappaledata, rata ja ajonaikaiset taulut"
        .cerror CHAIN_BUF + 3 * 145 > $6000 + PIC_ROW0 * 320, "ketjun talteenotto B:n kuvan päällä"
        .cerror SPRITES2 + (SPR_N - 15) * 64 > $d000, "tausta ja spritet I/O:n kohdalla"
        .cerror LIST_B + 4 * NLIST > $e000, "palautuslistat"
        .cerror SPRITES + 15 * 64 > $fffa, "spritet vektoreiden päällä"
        .cerror TAB_N != END_I, "pallon rata ei vastaa aikajanaa (make purku)"
        .cerror HIT2_I - HIT1_I > 255 || HIT3_I - HIT2_I > 255, "iskujen väli enintään 255 kehystä"
        .cerror CUT_I < 2 || CUT_I > 255 || HIT1_I <= CUT_I, "leikkaus ennen iskua 1, lähikuvan heilahdus enintään 255"
        .cerror CL_LY < 256 || CL_LY > 511 || W_LY > 255, "pallon varsi: lähikuva 256..511 riviä, laaja alle 256"
