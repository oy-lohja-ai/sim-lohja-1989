; Koti (demon kohtaus 2): kamera nousee kissan korkeudelta portailta, ja aidan ja naapurien kattojen takaa
; paljastuu Lohjanjärvi.
;
; Kerrokset:
;   taivas ja järvi    $D021 (bittikartan MC 00) rivi riviltä taivassilmukassa (crunch.asm), paikallaan;
;                      järven kimallusrivien väri kiertää väriliukujonoa
;   vastaranta         spritet bittikartan takana, paikallaan, leikataan taivasvyöhykkeeseen
;   keskiala           MC-bittikartta, linecrunch alaspäin (src/lib/crunch.asm), asettelut pankeissa 2 ja 3
;   etuala             kissa MC-spriteinä (nopeus FG_K16 / 16 x kuva), multiplekseri ja leikkaus;
;                      pää ja häntä elävät omissa tahdeissaan (an_head, an_tail: muunnelman osoitin ja lähde)
;
; Kehys: irq_top (rivi 44, kirjasto: sekvensseri ja taivassilmukka) -> cr_top_tail: tämän kehyksen tapahtumat
; ja seuraavan kehyksen liike sisäkkäin -> irq_ev (spritejen seuraavat instanssit rivijärjestyksessä) ->
; irq_bot (rivi 213): alareuna, vaihtokehyksen värimuisti, joukon vaihto, ensimmäiset instanssit, musiikki ja
; kahden kehyksen päästä näytettävä spritejoukko sisäkkäin.

        .include "koti.inc"
        .include "music.inc"
        .if INTEGRATED
        .include "timing.inc"
        .endif

        .weak
DFRAME  = $d0                   ; demon kehys (runko.inc)
TIM_SCENE_KOTI_START = 2400     ; src/gen/timing.inc, oletus
DEBUG   = 0
PREWAIT = 0                     ; kehyksiä ennen kelloa (kaappaus pääsee alkukehyksiin)
INTEGRATED = 0                  ; 1 = demon osa: koti_init, koti_go ja FRAME_HOOK kerran kehyksessä
FRAME_HOOK = 0
R_IDLE  = $0422                 ; rungon tyhjäkäyntikierros (src/runko/runko.inc)
        .endweak

LINE_BOT  = 213
TXT_HW    = 0                   ; tekstien ensimmäinen sprite
TXT_EN    = ((1 << N_TXT) - 1) << TXT_HW
COL_BOT   = 13                  ; vaihtokehyksen alareunassa kirjoitettavat väririvit (cc = 6: rivit 6..PRE_ROW-1)
PRE_ROW   = (WIN_H + 7) / 8 + 1 ; tästä alkaen rivit ovat piilossa, kun vanhan asettelun cc = 0 (pääsilmukka kirjoittaa
WIN_H     = 144                 ; ne etukäteen, prewrite)
MAXE      = 32                  ; spritetapahtumia per kehys (joukko)
SPR_TOP   = 73                  ; spritet vain riveillä 73-215 (sekvensseri ja alareunan kirjoitus)
SPR_BOT   = 215

        .virtual $02
frame   .word ?
mptr    .word ?                 ; liikekäyrän osoitin (nopeus 1/PSUB px per kehys)
mcount  .word ?
phase   .byte ?                 ; 0 pito, 1 nousu, 2 pito
pos     .word ?                 ; kameran paikka 1/PSUB px (P_MAX * PSUB -> 0)
ppx     .byte ?                 ; kokonaiset pikselit
lbase   .byte ?                 ; näkyvän asettelun alku pikseleinä
k_cur   .byte ?                 ; näkyvä asettelu
pre_req .byte ?                 ; pääsilmukka: rakenna asettelu pre_k pankkiin pre_bank
built   .byte ?                 ; viimeksi rakennettu asettelu
ready   .byte ?                 ; takapankin asettelu valmis
colsw   .byte ?                 ; vaihtokehys: väririvit cc..24 alareunassa
colpend .byte ?
colmid  .byte ?                 ; vaihtokehyksen loput väririvit tästä (0 = ei)
colrest .byte ?
colend  .byte ?                 ; vaihtokehyksen väririvien loppu (PRE_ROW, jos pääsilmukka kirjoitti loput, muuten 25)
prew    .byte ?                 ; asettelu + 1, jonka rivit PRE_ROW..24 pääsilmukka kirjoitti värimuistiin (prewrite)
stalls  .byte ?                 ; kehykset, joina takapankki ei ehtinyt (pitäisi olla 0)
gph     .byte ?                 ; kimalluksen vaihe
bank    .byte ?                 ; crunch.asm: 1 = pankki 3
plyt    .byte ?
cc      .byte ?
ff      .byte ?
lb      .byte ?
seqn    .byte ?
lcur    .byte ?
d11show .byte ?
d11hide .byte ?
dd00v   .byte ?
bl7m    .byte ?
d21end  .byte ?
pre_k   .byte ?
pre_bank .byte ?
late    .byte ?                 ; kehykset, joina spritelaskenta ei ehtinyt (joukko toistettiin)
busy    .byte ?
done    .byte ?                 ; seuraava joukko valmis
cur     .byte ?                 ; näytettävä joukko (0/1)
ev_pos  .byte ?
cptr    .word ?                 ; tekijät taivaalle: seuraava pikseli (osoite, maski)
cleft   .word ?                 ; piirtämättä
cdel    .byte ?                 ; odotus nousun jälkeen
cz      .word ?
badj    .byte ?                 ; bittikartan ylätavun korjaus näkyvään pankkiin: 0 = pankki 3 ($e000), $c0 = pankki 2
                                ; ($a000); motion_step kameran pysähtyessä (asettelu ei enää vaihdu)
ev_end  .byte ?
drops   .byte ?                 ; instanssit, joille ei löytynyt spriteä (kaikista kehyksistä)
bot_d11 .byte ?
bot_ff  .byte ?
ra      .byte ?
rx      .byte ?
ry      .byte ?
rowi    .byte ?
rown    .byte ?
tmp     .word ?
ltmp    .word ?
dbmp    .word ?
dscr    .word ?
dcol    .word ?
; spritelaskenta
eb      .byte ?                 ; seuraavan joukon tapahtumien kanta (0 / MAXE)
ib      .byte ?                 ; seuraavan joukon alkuinstanssien kanta (0 / 8)
nx      .byte ?                 ; seuraava joukko (cur ^ 1)
ne      .byte ?                 ; tapahtumia
first   .byte ?                 ; spritet, joilla on jo instanssi tässä kehyksessä
fgl     .word ?                 ; etualan rivin 0 näyttörivi (etumerkillinen)
fi      .byte ?
si      .byte ?
cl      .word ?                 ; ehdokkaan rivi (16 bittiä)
c_start .byte ?
c_k     .byte ?                 ; leikatut rivit
c_side  .byte ?                 ; 0 ei, 1 ylä, 2 ala
c_xlo   .byte ?
c_bits  .byte ?                 ; bitti 0 X >= 256, 1 X-laajennus, 2 takana, 3 hires, 4 silmien takana, 5 vain 0-2
c_ptr   .byte ?
c_col   .byte ?
c_src   .word ?
hw      .byte ?
zs      .word ?
zd      .word ?
sh010   .byte ?
sh01d   .byte ?
sh01b   .byte ?
zt      .byte ?
zy      .byte ?
kg      .byte ?
zvec    .word ?
zcf     .word ?
ezt     .byte ?                 ; IRQ-puolen väliaikaiset (logiikka on sisäkkäin keskeytettävissä)
ezy     .byte ?
zl      .byte ?                 ; taivasvyöhykkeen viimeinen rivi (takana olevat spritet leikataan siihen)
c_lim   .byte ?
mtmp    .byte ?                 ; logic_frame:n väliaikaiset (se ajetaan joka kehys myös myöhästyneen
mzt     .byte ?                 ; spritelaskennan päällä)
mzy     .byte ?
stmp    .word ?                 ; spritelaskennan väliaikaiset (pääsilmukan build_layout käyttää tmp/ltmp:tä)
sltmp   .word ?
spos    .word ?                 ; spritelaskennan kameran paikka ja kokonaiset pikselit
sppx    .byte ?
zd2     .word ?                 ; leikkauspuskurin kohde pankissa 3 (zd + $4000)
glp     .word ?                 ; kimalluksen värijono (gl_ring, auringonlaskussa gl_ring2)
il_p    .word ?                 ; ilta_step: kohde (ruutu tai bittikartta)
il_s    .word ?                 ; ilta_step: maskirivi (puolikas seuraavassa kehyksessä)
vkp     .word ?                 ; vk_step: vaihdoksen lista
catf    .byte ?                 ; spr_frame: kissan joukon alareunan tapahtumat (varjot cs_shadissa)
ct_t0   .byte ?                 ; cat_set: ensimmäinen alareunan tapahtuma ($ff: ei)
cr_y    .byte ?                 ; cred_step: kynän rivi ja MC-x
cr_x    .byte ?
k5ok    .byte ?                 ; KOTI5 ladattu (koti_quiet; protossa heti): vk_step, ilta_step ja dusk_step
vk_md   .byte ?                 ; vk_step: $80 päivä (vain välke), $c0 tyhjennys, 0 ilta (maskin tavu ja välke)
vk_s    .byte ?                 ; vk_step: 0 päivän alku, 1 värimuisti, 2 alku, 3 käynnissä, 4 odottaa iltaa
vk_j    .byte ?                 ; vk_step: seuraava värimuistisolu
vk_p    .byte ?                 ; vk_step: vaihe
vk_e    .byte ?                 ; vk_step: listan pituus tavuina
vk_y    .byte ?                 ; vk_step: listassa kirjoitettu tähän asti
vk_lim  .byte ?
vk_t    .word ?                 ; vk_step: kohdetavu (ei il_s: päivän välke jatkuu ilta_stepin maalatessa rivejä)
        .endv

        .if INTEGRATED
        * = CODE_BASE
; koti_init1: alustus purun pysähdyttyä, kun purun viimeinen kuva on vielä näkyvissä (rungon IRQ soittaa): ei
; VIC-rekistereitä, ei $d800:aa eikä pankkia 1. Ylin asettelu on valmiina pankissa 3 (KOTI2 ja KOTI3 purun aikana),
; sen värit l2col:ssa; keskimmäisen rakentaa koti_build kodin pyöriessä. koti_go: kuva, värit ja oma IRQ rivillä 250,
; nousu alkaa ja palaa heti (pääsäie vapaa lataukselle).
koti_init1
        lda #0
        sta $d015
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
        jmp koti_init
nmi     rti
        * = CODE_BASE
koti_init
        lda #$0b
        sta $d011
        lda #0
        sta $d015
        sta $d020
        sta $d021
        .endif
        ldx #0
        txa
-       sta $02,x               ; nollasivun muuttujat
        inx
        cpx #$a0
        bne -
        ldx #0                  ; koko sivut (X:n jatko $a0:sta jättäisi sivujen tavut $00-$9f nollaamatta: koko
-       .for _p := 0, _p < BSS_PAGES, _p += 1   ; demossa edellisen osan roskaa, ja kissa puuttuisi)
        sta bss_start + 256 * _p,x
        .next
        inx
        bne -
        .if BSS_REST
        ldx #BSS_REST
-       sta bss_start + 256 * BSS_PAGES - 1,x
        dex
        bne -
        .endif
        .if !INTEGRATED
        lda #1                  ; protossa KOTI5:n koodi ja taulut ovat ohjelmassa
        sta k5ok
        .endif
        lda #<cred_data
        sta cptr
        lda #>cred_data
        sta cptr+1
        lda #<CRED_N
        sta cleft
        lda #>CRED_N
        sta cleft+1
        lda #CRED_WAIT
        sta cdel
        lda #<motion_v
        sta mptr
        lda #>motion_v
        sta mptr+1
        lda #<(P_MAX * PSUB)
        sta pos
        lda #>(P_MAX * PSUB)
        sta pos+1
        .if HAVE_MUSIC && !INTEGRATED
        ldx #<MSTART
        ldy #>MSTART
        jsr music_seek
        .endif
        lda #LAYOUTS - 1        ; ensimmäinen asettelu (ylin kanta)
        sta k_cur
        sta built
        tax
        lda lay_px_lo,x
        sta lbase
        .if INTEGRATED
        lda #1                  ; valmiina pankissa 3; keskimmäinen pankkiin 2 (koti_build)
        sta bank
        .else
        stx pre_k               ; tietueista pankkiin 2 ja värit, keskimmäinen pankkiin 3
        lda #0
        sta pre_bank
        sta bank
        jsr build_layout
        jsr colcopy
          .if LAYOUTS > 1
        jsr koti_lay1
          .endif
        .endif
        jsr spr_init
        jsr logic_frame         ; ensimmäisen kehyksen parametrit ja spritet joukkoon 1
        jsr spr_frame
        jsr swap_set
        lda d11hide
        sta bot_d11
        lda ff
        sta bot_ff
        .if INTEGRATED
        jmp koti_prep           ; koti_shown ikkunan ulkopuoliset ruuturivit talteen (näyttö vielä purun)
koti_go lda DFRAME              ; myöhässä kohtauksen alusta (lataus, init): nousu kiinni demon kelloon, jotta se
        sec                     ; loppuu kohtauksen lopussa
        sbc #<TIM_SCENE_KOTI_START
        sta zs
        lda DFRAME+1
        sbc #>TIM_SCENE_KOTI_START
        sta zs+1
        bcc _go                 ; ajoissa
        ora zs
        beq _go
-       jsr motion_step
        lda zs
        bne +
        dec zs+1
+       dec zs
        lda zs
        ora zs+1
        bne -
        jsr logic_frame         ; ensimmäisen kehyksen parametrit ja spritet uudesta paikasta
        jsr spr_frame
        jsr swap_set
_go     php                     ; rungon IRQ päällä (I = 0): sen FRAME_HOOK (rivi 250) soi vielä tämän kehyksen,
        pla                     ; sitten näyttö ja IRQ kodille heti (muuten kello ja musiikki jäisivät kehyksen)
        and #4
        bne _sei
-       bit $d011               ; rivit 251-311: rungon IRQ on jo ajettu (se keskeyttää tämän silmukan rivillä 250)
        bmi +
        lda $d012
        cmp #251
        bcc -
+       sei
        jmp sh_go
_sei
        .endif
        .if PREWAIT
        ldx #<PREWAIT
        ldy #>PREWAIT + 1
-       bit $d011
        bpl -
-       bit $d011
        bmi -
        dex
        bne --
        dey
        bne --
        .endif
-       lda $d012               ; rivit 250-255 (heti, jos kutsuja on jo siellä: kohtaustaulun S_START)
        cmp #250
        bcc -
        .if INTEGRATED
sh_go   jsr sh_rest             ; koti_shown nollaamat ruuturivit takaisin (kuva näkyy taas vasta clock0:n jälkeen)
        .endif
clock0  lda d11hide             ; kuva (demossa purun viimeinen kuva näkyy tähän asti)
        sta $d011
        lda #0
        sta $d020
        sta $d021
        lda #$18                ; MC, 40 saraketta
        sta $d016
        lda #$08                ; ruutu +$0000, bittikartta +$2000
        sta $d018
        jsr spr_first
        lda #<irq_top
        sta $fffe
        lda #>irq_top
        sta $ffff
        lda #LINE_TOP
        sta $d012
        lda #$ff
        sta $d019
        lda #1
        sta $d01a
        lda #$ff
        sta $d019
        cli
        .if INTEGRATED
        .for _r := 0, _r < ROWS_BANK, _r += 5   ; ylimmän asettelun värit ylhäältä alas säteen edellä, 5 riviä
        ldx #39                                 ; kierroksessa (10 sykliä tavu: kissa 3:n spritejen DMA:n kanssa
-                                               ; rivi kerrallaan 14 sykliä, ja säde ohittaisi rivit 15-19 kehyksessä 1)
        .for _k := 0, _k < 5, _k += 1
        lda l2col + 40 * (_r + _k),x
        sta $d800 + 40 * (_r + _k),x
        .next
        dex
        bpl -
        .next
        .cerror ROWS_BANK % 5 != 0
        rts
        .else
        jmp main
        .endif

        .if INTEGRATED
; koti_show (kohtaustaulu #S_SHOW koti_init1:n jälkeen, ennen kelloa): ensimmäinen kuva ilman IRQ:ta, joten osalevyn
; kehys 0 ei ole musta. Ilman linecrunchia näytetään pankki 3 YSCROLL 0:lla: rasteririvi 72 = pankin 3 rivi
; P_MAX - 8 * LAY_TOP. Ikkunan ulkopuoli mustaksi (koti_prep nollaa ruuturivit, tämä värimuistin), värit $d800:aan
; (koti_go kirjoittaa omansa). Spritet pois: kissan 14 solua eivät mahdu 8 spriteen ilman multiplekseriä, joten kissa
; tulee kehyksessä 1. koti_go:n clock0 ja ensimmäinen IRQ asettavat kaiken uudelleen. Koodi on KOTI3:n bittikartan
; perässä ($ff40-).
SH_C0   = (P_MAX - 8 * LAY_TOP) / 8         ; pankin 3 ensimmäinen ikkunan merkkirivi
        .cerror (P_MAX - 8 * LAY_TOP) % 8 != 0, "koti_show: ikkunan alku ei ole merkkirivin rajalla"
koti_show_code .segment
koti_show
        ldx #240                ; värit ikkunan riveille
-       lda l2col + 40 * SH_C0 - 1,x
        sta $d800 + 3 * 40 - 1,x
        lda l2col + 40 * SH_C0 + 239,x
        sta $d800 + 3 * 40 + 239,x
        lda l2col + 40 * SH_C0 + 479,x
        sta $d800 + 3 * 40 + 479,x
        dex
        bne -
        lda #0                  ; värimuisti ikkunan ulkopuolella mustaksi (%11-pikselit)
        ldx #120
-       sta $d800 - 1,x
        dex
        bne -
        ldx #160
-       sta $d800 + 21 * 40 - 1,x
        dex
        bne -
        sta $dd00               ; pankki 3 (Krill: $dd00:aan vain 0-3)
        ldx #sh_vend - sh_vic - 2
-       lda sh_vic + 1,x
        ldy sh_vic,x
        sta $d000,y
        dex
        dex
        bpl -
        rts
; koti_prep (koti_init1:n lopussa, purun kuva vielä näkyvissä): koti_show näyttää pankin 3 suoraan (YSCROLL 0: ikkunan
; merkkirivit 3-20 ovat pankin 3 rivit SH_C0..), ja ikkunan ulkopuoliset ruuturivit 0-2 ja 21-24 nollataan (bittikartan
; pikselit mustina ruudun ja värimuistin nollilla, %00 = $d021 musta). Rivit talteen pankkiin 2 (vapaa koti_buildiin
; asti), sh_rest palauttaa ne koti_go:ssa näkyvän alueen jälkeen. Koko kuvan kopio pankkiin 2 (8 720 tavua) veisi
; noin 8 kehystä.
        .cerror SH_C0 != 3, "koti_show: pankin 3 ikkuna ei ole riveillä 3-20"
SH_SAVE = BANK2_SCR
koti_prep
        ldx #120
-       lda BANK3_SCR - 1,x
        sta SH_SAVE - 1,x
        lda #0
        sta BANK3_SCR - 1,x
        dex
        bne -
        ldx #160
-       lda BANK3_SCR + 21 * 40 - 1,x
        sta SH_SAVE + 120 - 1,x
        lda #0
        sta BANK3_SCR + 21 * 40 - 1,x
        dex
        bne -
        rts
sh_rest ldx #120                ; koti_go: ruuturivit 0-2 ja 21-24 takaisin (rivi 250 jälkeen, ennen seuraavaa kuvaa)
-       lda SH_SAVE - 1,x
        sta BANK3_SCR - 1,x
        dex
        bne -
        ldx #160
-       lda SH_SAVE + 120 - 1,x
        sta BANK3_SCR + 21 * 40 - 1,x
        dex
        bne -
        rts
sh_vic  .byte $15, 0, $20, 0, $21, 0, $18, $08, $16, $18, $11, $38   ; $d011: bittikartta, YSCROLL 0
sh_vend
sh_i    .byte 0
sh_n    .byte 0
sh_r    .byte 0
        .endsegment

; koti_quiet (pääsäie, kohtaustaulu koti_buildin jälkeen): odottaa viimeistä asettelun vaihtoa ja sen värikopiota,
; sitten spriteosoittimet ja leikkauspuskurit vain pankkiin 3. Palaa, kun pankki 2 ($8000-$bfff, myös COLSTAGE) on
; vapaa seuraavan kohtauksen latauksille. Kodin käytössä loppuun: $1a00-koti1_end, $4000-$47ff (bss), $c000-$cfff,
; $e000-$ff3f, $d800, nollasivu $02-$a1.
koti_quiet
        lda #1                  ; kohtaustaulu kutsuu tämän KOTI5:n latauksen jälkeen: välke, ilta ja tummuminen
        sta k5ok
        lda #0                  ; tästä eteenpäin prewrite pääsäikeessä (COLSTAGE vapautuu tämän jälkeen)
        sta bgpre
        lda cz2 + 1             ; jo tehty
        beq _done
-       jsr prewrite
        jsr R_IDLE
        lda k_cur
        ora colsw
        ora colpend
        ora colmid
        bne -
        lda #1                  ; vaihto IRQ:ssa (q_patch, spr_body ennen spritelaskentaa): sei-lohko pääsäikeessä
        sta qreq                ; osuisi koko demossa mihin riviin tahansa, ja 32 cb_hi-tavun silmukka riveillä 36-45
-       lda qreq                ; myöhästyttäisi yläreunan IRQ:n (kehys musta ja DFRAME seisoisi)
        bne -
_done   rts
        .endif

; koti_lay1: toiseksi ylin asettelu takapankkiin (värit COLSTAGEen vaihtoa varten). Protossa koti_init, demossa
; koti_build kodin pyöriessä; ensimmäinen vaihto odottaa sitä.
koti_lay1
        lda #LAYOUTS - 2
        sta pre_k
        lda bank
        eor #1
        sta pre_bank
        jsr build_layout
        lda pre_k
        sta built
        lda #1
        sta ready
        rts

; build_layoutin rivi (crunch.asm cr_row; rowi = kuvan rivi, tmp = tietue): ylintä alemman asettelun rivit, jotka ovat
; myös näkyvässä asettelussa (kanta lay_row[pre_k + 1] alkaen), kopioidaan sen pankista ja värimuistista. Tietueita
; tarvitaan vain asettelun uusille riveille (demossa ylintä asettelua ei rakenneta lainkaan).
cr_row
        ldx pre_k
        cpx #LAYOUTS - 1
        bcs _rec
        lda rowi
        sec
        sbc lay_row + 1,x
        bcs bank_row
_rec    lda tmp+1               ; tyhjä rivi (kuvan yläpuolen taivas): ei tietuetta, nollat
        beq zero_row
        jmp copy_row
; tyhjä rivi: bittikartta, ruutu ja värit nollia (MC 00: kaukainen kerros)
zero_row
        lda dbmp+1
        pha
        lda #0
        tay
-       sta (dbmp),y
        iny
        bne -
        inc dbmp+1
        ldy #63
-       sta (dbmp),y
        dey
        bpl -
        pla
        sta dbmp+1
        lda #0
        ldy #39
-       sta (dscr),y
        sta (dcol),y
        dey
        bpl -
        rts
; A = näkyvän asettelun rivi j: bittikartta 320 t ja ruutu 40 t toisesta pankista, värit $d800:sta COLSTAGEen
bank_row
        tay
        lda pre_bank
        eor #1
        tax
        lda r320_lo,y
        sta tmp
        lda r320_hi,y
        clc
        adc bmp_hi,x
        sta tmp+1
        lda dbmp
        sta ltmp
        lda dbmp+1
        sta ltmp+1
        tya
        pha
        ldy #0
-       lda (tmp),y
        sta (ltmp),y
        iny
        bne -
        inc tmp+1
        inc ltmp+1
        ldy #320 - 256 - 1
-       lda (tmp),y
        sta (ltmp),y
        dey
        bpl -
        pla
        tay
        lda row40_lo,y
        sta tmp
        sta ltmp
        lda row40_hi,y
        pha
        clc
        adc scr_hi,x
        sta tmp+1
        pla
        clc
        adc #>$d800
        sta ltmp+1
        ldy #39
-       lda (tmp),y
        sta (dscr),y
        lda (ltmp),y
        sta (dcol),y
        dey
        bpl -
        rts

; koti_build: pääsilmukka rakentaa seuraavan asettelun takapankkiin, kun vaihto on vapauttanut sen. Demossa
; kohtaustaulu (src/scene/koti_glue.asm) kutsuu tätä, kun tietueet rec_first-rec_end on ladattu: koti_init1:n jälkeen
; ensin keskimmäinen asettelu, sitten alin ensimmäisen vaihdon jälkeen; palaa, kun viimeinen on rakennettu.
koti_build
        .if INTEGRATED && LAYOUTS > 1
        lda built
        cmp #LAYOUTS - 1
        bne main
        jsr koti_lay1
        .endif
main    lda pre_req
        beq _idle
        jsr build_layout
        lda pre_k
        sta built
        lda #0
        sta pre_req
        lda #1
        sta ready
        jmp main
_idle   jsr prewrite
        .if INTEGRATED
        lda built
        beq +
        jsr R_IDLE              ; rungon CPU-mittari: tyhjäkäyntikierros (A, X, Y muuttuvat)
        jmp main
+       lda #1                  ; koti_quietiin asti prewrite IRQ:ssa (pre_irq): kohtaustaulu lataa välissä
        sta bgpre               ; (LOPPU2), eikä pääsäie kutsu prewritea
        rts
        .else
        jmp main
        .endif

; Takapankin asettelun väririvit PRE_ROW..24 värimuistiin ennen vaihtoa, kun ne ovat näkyvässä asettelussa piilossa
; (cc = 0 tässä ja edellisessä kehyksessä: plyt < 7): vaihtokehyksen värikopio lyhenee (alareuna ehtii ennen riviä
; 44 musiikin jälkeen). Pääsilmukasta ilman sei:tä: prew = asettelu + 1, joten jos vaihto tulee kesken, vaihtokehys
; kirjoittaa rivit itse eikä myöhästynyt prew osu seuraavaan asetteluun.
prewrite
        lda pre_req
        bne _no
        lda ready
        beq _no
        ldy built
        iny
        cpy prew
        beq _no
        lda ppx
        sec
        sbc lbase
        bcc _no
        cmp #7
        bcs _no
        ldx #(ROWS_BANK - PRE_ROW) * 40
-       lda COLSTAGE + PRE_ROW * 40 - 1,x
        sta $d800 + PRE_ROW * 40 - 1,x
        dex
        bne -
        sty prew
_no     rts

        .if INTEGRATED
; prewrite IRQ:ssa (logic_frame) koti_buildin paluun ja koti_quietin välillä, rivi kehyksessä: koko demossa runko
; lataa siinä välissä (LOPPU2), ja ilman prewritea asettelun vaihto kirjoittaisi kaikki rivit itse (vaihtokehyksen
; värikopio venyisi). Ehdot kuten prewrite; jos ne katkeavat kesken, alusta uudelleen.
pre_irq
        lda pre_req
        bne _rst
        lda ready
        beq _rst
        ldy built
        iny
        cpy prew
        beq _rst
        lda ppx
        sec
        sbc lbase
        bcc _rst
        cmp #7
        bcs _rst
        ldx #39
_s      lda COLSTAGE + PRE_ROW * 40,x
_d      sta $d800 + PRE_ROW * 40,x
        dex
        bpl _s
        lda _s + 1
        clc
        adc #40
        sta _s + 1
        bcc +
        inc _s + 2
+       lda _d + 1
        clc
        adc #40
        sta _d + 1
        bcc +
        inc _d + 2
+       inc prw_n
        lda prw_n
        cmp #ROWS_BANK - PRE_ROW
        bcc _r
        sty prew                ; valmis (Y = built + 1)
_rst    lda #0
        sta prw_n
        lda #<(COLSTAGE + PRE_ROW * 40)
        sta _s + 1
        lda #>(COLSTAGE + PRE_ROW * 40)
        sta _s + 2
        lda #<($d800 + PRE_ROW * 40)
        sta _d + 1
        lda #>($d800 + PRE_ROW * 40)
        sta _d + 2
_r      rts
        .endif

; Spritet: yhteiset värit, lohkot molempiin pankkeihin samaan kohtaan (sama osoitin), leikkauspuskurit tyhjinä
spr_init
        lda #SPR_D025
        sta $d025
        lda #SPR_D026
        sta $d026
        lda #$ff
        sta $d01c
        lda #0
        sta $d017
SPR_B2  = BANK2_SCR + SPR_OFS + 64 * N_CLIP
        ldx #0                  ; lohkot sivuittain molempiin pankkeihin (demossa lähde on jo pankissa 3)
-       .for _p := 0, _p < (64 * N_BLK + 255) / 256, _p += 1
        lda spr_src + 256 * _p,x
        sta SPR_B2 + 256 * _p,x
          .if spr_src != SPR_B2 + $4000
        sta SPR_B2 + $4000 + 256 * _p,x
          .endif
        .next
        inx
        bne -
        .if N_XBLK              ; loput lohkot joukon 0 yläreunan leikkauspuskureihin (yläreunaa ei ylitä mikään)
SPR_X2  = BANK2_SCR + SPR_OFS
-       .for _p := 0, _p < (64 * N_XBLK + 255) / 256, _p += 1
        lda spr_xsrc + 256 * _p,x
        sta SPR_X2 + 256 * _p,x
          .if spr_xsrc != SPR_X2 + $4000
        sta SPR_X2 + $4000 + 256 * _p,x
          .endif
        .next
        inx
        bne -
        .endif
        .if N_YBLK              ; ja joukon 1 yläreunan puskureihin
SPR_Y2  = BANK2_SCR + SPR_OFS + 64 * 16
-       .for _p := 0, _p < (64 * N_YBLK + 255) / 256, _p += 1
        lda spr_ysrc + 256 * _p,x
        sta SPR_Y2 + 256 * _p,x
          .if spr_ysrc != SPR_Y2 + $4000
        sta SPR_Y2 + $4000 + 256 * _p,x
          .endif
        .next
        inx
        bne -
        .endif
        ldx #31                 ; leikkauspuskurit: ei sisältöä
        lda #$ff
-       sta cb_src,x
        sta cb_srch,x
        dex
        bpl -
        .if !INTEGRATED         ; dusk_byte (demossa taulu KOTI1:ssä): ruututavun nibblet dusk_tabin kautta
        ldx #0
-       txa
        and #$0f
        tay
        lda dusk_tab,y
        sta il_b
        txa
        lsr a
        lsr a
        lsr a
        lsr a
        tay
        lda dusk_tab,y
        asl a
        asl a
        asl a
        asl a
        ora il_b
        sta dusk_byte,x
        inx
        bne -
        .endif
        lda #<gl_ring
        sta glp
        lda #>gl_ring
        sta glp+1
        ldx #WIN_H - 1          ; kaukainen kerros päivänä
-       lda far_tab,x
        sta far_cur,x
        dex
        cpx #$ff
        bne -
        lda #1
        sta fc_up
        sta fc_lo
        ldx #N_BIRD - 1         ; pääskysten lähtöpaikat (1/16 px); poissa ruudulta paluuseen (BIRD_RET) asti: lokit
-       lda bd_x0lo,x           ; lentävät taivaalla eivätkä portailla, ja taivasta ei näy
        sta bd_xl,x             ; ennen kameran nousua
        lda bd_x0hi,x
        sta bd_xh,x
        lda #1
        sta bd_gone,x
        dex
        bpl -
        rts

; ---------------------------------------------------------------- IRQ: yläreunan jatko
cr_top_tail
        lda #<irq_ev            ; tämän kehyksen spritetapahtumat (joukko cur)
        sta $fffe
        lda #>irq_ev
        sta $ffff
        lda cur
        beq +
        lda #MAXE
+       sta ev_pos
        clc
        adc ne_cur
        sta ev_end
        jsr ev_sched
        asl $d019
        lda d11hide             ; tämän kehyksen alareunan arvot talteen, sitten seuraavan kehyksen
        sta bot_d11             ; liike ja $D021-lista (joka kehys) ja spritet (kun edellinen joukko on vaihdettu)
        lda ff                  ; sisäkkäin
        sta bot_ff
        ldx colmid              ; vaihtokehyksen alemmat väririvit (säde on vasta ikkunan yläosassa)
        beq +
        lda #0
        sta colmid
        ldy colend
        cpx colend
        bcs +
        jsr colfast
+
        lda ra                  ; rekisterit pinoon: sisäkkäinen yläreunan IRQ (spritelaskenta yli kehyksen)
        pha                     ; kirjoittaa ra/rx/ry:n uudelleen
        lda rx
        pha
        lda ry
        pha
        cli
        jsr logic_frame
        pla
        tay
        pla
        tax
        pla
        rti

; seuraavan tapahtuman IRQ (käsittelyrivi) vähintään 2 riviä nykyisen jälkeen, tai alareuna
ev_sched
        jsr ev_pick
        bcs ev_tobot
        sta ezt
        lda $d012
        clc
        adc #2
        cmp ezt
        bcs +
        lda ezt
+       sta $d012
        rts
; seuraava tapahtuma: A = käsittelyrivi, Y = tapahtuma; C = 1: ei enää
ev_pick
        ldx ev_pos
        cpx ev_end
        bcs +
        ldy ev_ord,x
        lda ev_key,y
        clc
        rts
+       sec
        rts
ev_tobot
        lda #<irq_bot
        sta $fffe
        lda #>irq_bot
        sta $ffff
        lda #LINE_BOT
        sta $d012
        rts

; ---------------------------------------------------------------- IRQ: tapahtumat
; Spritet: rekisterit heti, kun rivi >= L (saman spriten edellinen instanssi on päättynyt riville L-1).
irq_ev
        pha
        txa
        pha
        tya
        pha
        asl $d019
_next   ldx ev_pos                  ; ev_pick auki (jsr/rts:llä kissan aikana ketjun tapahtumat myöhästyisivät)
        cpx ev_end
        bcs _fin
        ldy ev_ord,x
        lda ev_key,y
        cmp $d012
        bcc _snow
        beq _snow
        sta $d012
        jmp _out
_snow   lda ev_kind,y           ; 2: $D021 = ev_y rivin alussa (taivassilmukan alla, _d21ev)
        cmp #2
        bne +
        ldx ev_key,y            ; avain = rivi r - 3. Kirjoitus rivin r alussa (sykli noin 6-12, spritejen DMA
        inx                     ; myöhästyttää), paitsi jos r on badline: silloin kirjoitus jäisi syklille 55 (koko
        inx                     ; rivi vanhaa väriä), joten kirjoitus rivin r - 1 oikeassa reunassa
        inx
        stx ezt
        lda $d011
        eor ezt
        and #7
        beq _d21b
        lda ev_y,y
        cpx $d012               ; X = r
        bcc _d21w               ; jo ohi: heti
        beq _d21w               ; jo rivillä r (edellinen tapahtuma myöhästytti): heti. Muuten rivin lopussa luettu r
                                ; jäisi odotukseen, joka ei enää näe riviä r: kehys jumissa, ketju katki (esim.
                                ; pääskysen spritetapahtuma juuri ennen: kuva hajoaisi 2-4 kehykseksi)
-       cpx $d012               ; tiukka odotus (7 sykliä): kirjoitus syklillä 6-12, vasemmassa reunassa ennen
        bne -                   ; näkyvää aluetta (8565:n harmaa piste jää reunaan)
        beq _d21w
_d21b   dec ezt
        lda ev_y,y
-       ldx $d012               ; luku syklillä c (0-9): kirjoitus c + 57 ilman spritejen DMA:ta
        cpx ezt
        bcc -
        bne _d21w               ; jo myöhässä: heti
        ldx #9
-       dex
        bne -
_d21w   sta $d021
        inc ev_pos
        jmp _next
+       ldx ev_hw,y             ; väri, $D010 ja X ennen Y:tä (edellinen instanssi on jo päättynyt): Y:n jälkeen ne
        lda ev_col,y            ; osuisivat DMA:n venyttäessä vasta uuden instanssin ensimmäiselle riville, ja se
        sta $d027,x             ; piirtyisi vanhalla värillä tai 256 px vasemmalla (valkoiset viivat kissan aikana)
        ldx ev_hw2,y
        lda ev_010,y
        sta $d010
        lda ev_xlo,y
        sta $d000,x
        lda ev_y,y
        sta $d001,x
        ldx ev_hw,y             ; osoitin heti Y:n jälkeen ja ennen laajennusta: VIC lukee sen rivin alku - 1 syklillä
        lda ev_ptr,y            ; 58, laajennusta vasta piirrossa. Näkyvä pankki 3 (koko kissan ajan) ensin: muuten
        sta BANK3_SCR + $3f8,x  ; kissan alareunassa (8 spriteä ja badline) pankin 3 kirjoitus myöhästyisi rivin 195
pw1     = *                     ; alkuun, ja jalustan ensimmäinen rivi piirtyisi edellisen lohkosta (valkoinen viiva).
        sta BANK2_SCR + $3f8,x  ; koti_quiet: pankkiin 3 (pankki 2 vapaa)
        lda ev_01d,y
        sta $d01d
ev_bc   = *                     ; kissan joukossa ennallaan: spr_first vaihtaa tähän jmp ev_bce
        lda ev_01c,y
        sta $d01c
        lda ev_01b,y
        sta $d01b
ev_bce  = *
        inc ev_pos
        jmp _next
_fin    lda $d012               ; ketju loppui alareunan lähellä: alareuna suoraan (IRQ riville 213 ei enää laukeaisi)
        cmp #LINE_BOT - 1
        bcc +
        jmp bot_body
+       jsr ev_tobot
_out    pla
        tay
        pla
        tax
        pla
        rti

; Ikkunan alareuna kuten crunch.asm cr_edge, mutta kirjoitus r sykliä aiemmin (bot_r, spritelaskenta): spritet 3-7,
; jotka näkyvät rivillä 215, pysäyttävät CPU:n rivin 215 alussa (3 + 2 n sykliä), ja kissa 3:lla alareunassa on 3
; tällaista (sarakkeiden alimmat solut). Kahdella kirjoitus osuu vielä rivin 216 reunaan, kolmella ilman korjausta
; rivin 216 vasen reuna näkyisi (8 px). r = 2 (n - 2), liukurampilla (lda #$a9 -ketju, 8 - r sykliä): kun r = 0,
; kirjoitus on cr_edgen tapaan 47 sykliä kyselyn jälkeen.
kt_edge .macro
        sta ezy                 ; $d011 (ramppi käyttää A:ta)
        ldx cur
        lda bot_r,x
        sta _br + 1
        lda ezy
        ldx #B_LINE - 1
-       cpx $d012
        bne -
        cpy #1
        beq _f1
        ldy #6                  ; 31 + 2 + 3 + (8 - r) + 3 = 47 - r sykliä
-       dey
        bne -
        nop
_br     bpl _sl                 ; 3 sykliä (ei sivurajaa)
_sl     .byte $a9, $a9, $a9, $a9, $a9, $24, $ea
        .cerror (>_br) != (>(_sl + 7)), "kt_edge: liukurampin haara ylittää sivun"
        lda ezy
        sta $d011
        jmp _edge
_f1     nop
        sta $d011
_edge
        .endm

; ---------------------------------------------------------------- IRQ: alareuna (rivi 213)
irq_bot
        pha
        txa
        pha
        tya
        pha
bot_body
        lda bot_d11
        ldy bot_ff
        #kt_edge
        asl $d019
        jsr txt_spr             ; tekstit riville TXT_LINE ennen sitä
        .if DEBUG
        lda #6
        sta $d020
        .endif
        .if INTEGRATED          ; musiikki ja demon kello ennen värikopiota: DFRAME kasvaa joka kehys ennen riviä
        jsr FRAME_HOOK          ; 304, myös vaihtokehyksessä
        .elsif HAVE_MUSIC
        jsr MUSIC_PLAY
        .endif
        .if DEBUG
        lda #4
        sta $d020
        .endif
        jsr col_frame           ; vaihtokehys: uuden asettelun värit ennen riviä 44
        jsr cred_step           ; tekijät järvelle nousun jälkeen
        .if DEBUG
        lda #0
        sta $d020
        .endif
        lda #<irq_spr           ; seuraavan kehyksen spritet vasta tekstispritejen jälkeen (21 riviä)
        sta $fffe
        lda #>irq_spr
        sta $ffff
        bit $d011               ; jo ohi (vaihtokehyksen värikopio): suoraan
        bmi spr_body
        lda $d012               ; värikopio jatkui seuraavaan kehykseen (rivit 0..LINE_TOP-1): suoraan, muuten
        cmp #LINE_TOP           ; IRQ riville TXT_LINE + 21 ohittaisi seuraavan kehyksen yläreunan (ikkuna musta)
        bcc spr_body
        lda tx_off              ; tekstit pois (TXT_OFF): spritelaskenta heti, noin 30 riviä aiemmin (laskennan pitää
        bne spr_body            ; ehtiä ennen seuraavan kehyksen yläreunaa: pelivara)
        lda #TXT_LINE + 21
        cmp $d012
        bcc spr_body
        beq spr_body
        sta $d012
        jmp bot_out

; ---------------------------------------------------------------- IRQ: spritet (rivi TXT_LINE + 21)
; Joukon vaihto ja seuraavan kehyksen ensimmäiset instanssit, sitten kahden kehyksen päähän näytettävä joukko
; sisäkkäin (aikaa seuraavan kehyksen alareunaan asti; myöhästyessä joukko toistetaan).
irq_spr
        pha
        txa
        pha
        tya
        pha
        asl $d019
spr_body
        lda #<irq_top
        sta $fffe
        lda #>irq_top
        sta $ffff
        lda #LINE_TOP
        sta $d012
        lda done                ; seuraavan kehyksen spritejoukko valmis: vaihto, muuten sama joukko uudelleen
        beq +
        jsr swap_set
        jmp ++
+       inc late
+       jsr spr_first
        lda busy
        bne bot_out
        lda done
        bne bot_out
        lda qreq                ; koti_quiet: pankki 3 vain (tässä ei spritelaskentaa eikä tapahtumia kesken)
        beq +
        jsr q_patch
+       inc busy
        cli
        jsr spr_frame
        lda #1
        sta done
        dec busy
bot_out pla
        tay
        pla
        tax
        pla
        rti

; koti_quiet (spr_body, qreq): spriteosoittimet ja leikkauspuskurit vain pankkiin 3
q_patch lda #>(BANK3_SCR + $3f8)
        sta pw1 + 2
        sta pw2 + 2
        sta pw3 + 2
        lda #0
        sta cz2 + 1
        sta qreq
        lda #$40                ; clip: puskurien ylätavut pankista 3
        sta cbh + 1
        rts

swap_set
        lda cur
        eor #1
        sta cur
        tax
        lda ne_set,x
        sta ne_cur
        lda #0
        sta done
        rts

; joukon cur ensimmäiset instanssit (spritet päättyvät viimeistään riville 215, joten ne ovat vapaita)
spr_first
        lda cur
        asl a
        asl a
        asl a
        tax
        ldy #0
-       lda in_y,x
        sta $d001,y
        lda in_x,x
        sta $d000,y
        iny
        iny
        inx
        cpy #2 * MAX_HW
        bne -
        lda cur
        asl a
        asl a
        asl a
        tax
        ldy #0
-       lda in_ptr,x
pw2     = *                     ; koti_quiet: pankkiin 3 (pankki 2 vapaa)
        sta BANK2_SCR + $3f8,y
        sta BANK3_SCR + $3f8,y
        lda in_col,x
        sta $d027,y
        inx
        iny
        cpy #MAX_HW
        bne -
        ldx cur
        lda in_010,x
        sta $d010
        lda in_01d,x
        sta $d01d
        lda in_01b,x
        sta $d01b
        lda in_en,x
        sta $d015
        lda in_01c,x            ; multiplekserin spritet MC (tekstit hires)
        sta $d01c
        lda in_d025,x           ; kissan musta ja valkoinen, kun kissa näkyy (saari ei silloin näy, build.py)
        sta $d025
        lda in_d026,x
        sta $d026
        cmp #CAT_D026           ; kissan joukko ($D026 vain silloin CAT_D026): tapahtumien $D01C/$D01B ovat alkuarvot
        beq _cat                ; (ei hires- eikä takana-spritejä: kissan solut ja pääskyset; saari ei
        lda #$b9                ; näy), joten irq_ev ohittaa ne (jmp ev_bce; tapahtuma lyhenee, seuraava ehtii aiemmin)
        cmp ev_bc               ; muuten lda abs,y (vain vaihtuessa: spritelaskennan aika)
        beq _r
        sta ev_bc
        lda #<ev_01c
        sta ev_bc + 1
        lda #>ev_01c
        sta ev_bc + 2
_r      rts
_cat    lda #$4c
        cmp ev_bc
        beq _r
        sta ev_bc
        lda #<ev_bce
        sta ev_bc + 1
        lda #>ev_bce
        sta ev_bc + 2
        rts

; tekstit alempaan letterboxiin spriteille TXT_HW.. (ikkunan spritet ovat päättyneet riville 215)
txt_spr
        lda tx_off              ; tekstit pois: vain spritet pois (ei koko ohjelmointia joka kehys)
        bne _off
        ldx #N_TXT - 1
-       txa
        asl a
        tay
        lda #TXT_LINE - 1
        sta $d001 + 2 * TXT_HW,y
        lda tx_xlo,x
        sta $d000 + 2 * TXT_HW,y
        lda tx_ptr,x
pw3     = *                     ; koti_quiet: pankkiin 3 (pankki 2 vapaa)
        sta BANK2_SCR + $3f8 + TXT_HW,x
        sta BANK3_SCR + $3f8 + TXT_HW,x
        lda tx_col,x
        sta $d027 + TXT_HW,x
        dex
        bpl -
        lda #TXT_010
        sta $d010
        lda #0
        sta $d01c
        sta $d01d
        sta $d01b
        lda frame+1             ; 1959 pois, kun talo on poistunut kuvasta (TXT_OFF)
        cmp #>TXT_OFF
        bcc +
        bne ++
        lda frame
        cmp #<TXT_OFF
        bcs ++
+       lda #TXT_EN
        sta $d015
        rts
+       lda #1
        sta tx_off
_off    lda #0
        sta $d015
        rts

; Värimuisti uudelle asettelulle: vaihtokehyksen alareunassa rivit cc..cc+14 (noin 5 400 sykliä), yläreunan
; IRQ:n jälkeen loput rivit (säde on vasta ikkunan yläosassa), seuraavassa kehyksessä rivit 0..cc-1, jotka
; tulevat näkyviin vasta kameran noustessa.
; Sen jälkeen pääsilmukka saa rakentaa seuraavan asettelun (COLSTAGE vapaa).
col_frame
        lda colsw
        beq _rest
        lda #0
        sta colsw
        lda #1
        sta colpend
        ldx k_cur               ; uuden asettelun rivit PRE_ROW..24 jo kirjoitettu (pääsilmukan prewrite)?
        inx
        lda #ROWS_BANK
        cpx prew
        bne +
        lda #PRE_ROW
+       sta colend
        ldx cc                  ; rivit cc..cc+COL_BOT-1 nyt, loput yläreunan IRQ:n jälkeen (cr_top_tail), jotta
        stx colrest             ; alareunan IRQ päättyy ennen riviä 44
        txa
        clc
        adc #COL_BOT
        cmp colend
        bcc +
        lda colend
+       tay
        sta colmid
        jmp colfast
_rest   lda colpend
        beq _done
        lda #0
        sta colpend
        ldy colrest
        beq +
        ldx #0
        jsr colfast
+       ldx k_cur               ; seuraava asettelu takapankkiin
        beq _done
        dex
        stx pre_k
        lda bank
        eor #1
        sta pre_bank
        lda #1
        sta pre_req
_done   rts

; väririvit X..Y-1 COLSTAGE -> $d800 (build.py colfast: rivin Y alkuun jmp cf_end kopion ajaksi)
colfast
        lda cf_lo,y
        sta zcf
        lda cf_hi,y
        sta zcf+1
        ldy #2
-       lda (zcf),y             ; rivin Y kolme ensimmäistä tavua talteen
        sta cf_save,y
        dey
        bpl -
        lda zcf                 ; lopetusrivi < 25: jmp cf_end sen alkuun
        cmp #<cf_end
        bne +
        lda zcf+1
        cmp #>cf_end
        beq ++
+       lda #$4c
        ldy #0
        sta (zcf),y
        lda #<cf_end
        iny
        sta (zcf),y
        lda #>cf_end
        iny
        sta (zcf),y
+
        lda cf_lo,x             ; silmukan alku ja hyppy rivin X lohkoon
        sta cf_jmp + 1
        sta _j + 1
        lda cf_hi,x
        sta cf_jmp + 2
        sta _j + 2
        ldx #39
_j      jsr $ffff
        ldy #2
-       lda cf_save,y
        sta (zcf),y
        dey
        bpl -
        rts
cf_save .fill 3

; ---------------------------------------------------------------- kehyksen logiikka
logic_frame
        .if INTEGRATED
        lda bgpre
        beq +
        jsr pre_irq
+
        .endif
        jsr motion_step
        lda k5ok                ; ilta_step, dusk_step ja vk_step KOTI5:ssä (koti_quiet: ladattu)
        beq ++
        lda frame               ; ilta kehyksestä ILTA_F (kamera seisoo jo, tekijät piirtyvät sitä ennen sinitaivaalle)
        cmp #<ILTA_F
        lda frame+1
        sbc #>ILTA_F
        bcc +
        jsr ilta_step
        jsr dusk_step
+       lda phase               ; välke kameran pysähdyksestä (päivällä tekijäjaksossa)
        cmp #2
        beq _vk
        jsr vr_gate             ; ja jo nousun lopussa: kun vr_gate on kirjoittanut järven
        bcs +                   ; rivien värimuistin, kehyksestä VKC_F (vk_step: välkesolut, sitten listat siirrolla)
        nop                     ; (täyte: poisto siirtäisi myöhempää koodia ja muuttaisi ajoitusta)
        lda frame
        cmp #<VKC_F
        lda frame+1
        sbc #>VKC_F
        bcc +
_vk     jsr vk_step
+       jsr bird_ret
        ldx #N_BIRD - 1         ; pääskyset: x16 += dx (etumerkillinen)
-       lda bd_dx,x
        bpl +
        dec bd_xh,x
+       clc
        adc bd_xl,x
        sta bd_xl,x
        bcc +
        inc bd_xh,x
+       lda bd_lo               ; palanneet (BIRD_RET) kiertävät ruudun ympäri kehykseen BIRD_OUT asti, sitten
        beq _bn                 ; kokonaan piilossa (352 <= X < 480, X-laajennus) ei palaa: lopun kehys 0 ilman
        lda frame+1             ; pääskysiä (runko)
        cmp #>BIRD_OUT
        bcc _bn
        bne +
        lda frame
        cmp #<BIRD_OUT
        bcc _bn
+       lda bd_xh,x
        and #$1f
        cmp #$16
        bcc _bn
        cmp #$1e
        bcs _bn
        lda #1
        sta bd_gone,x
_bn     dex
        bpl -
        jsr lf_place
        jmp sunset_step

        .section koti1tail
; Välke jo nousun lopussa (ei vasta tekijöiden aikana). Järvi on $D021:tä ja paikallaan, bittikartta nousee: vk_step
; kirjoittaa päivän välkkeen
; listan kuvan riville y + ppx viimeisessä asettelussa (siirto d listan alussa, ppx <= VR_PR, build.py rise_valke), ja
; jos ppx on muuttunut, edellisen listan tavut nollataan sen siirrolla samassa tahdissa (VK_K3 / 3 tavua kehyksessä
; kumpaakin). Pysähdyksen jälkeen siirto on 0 ja vk_step kirjoittaa sellaisenaan. vr_gate: kehyksestä VR_F (viimeisen
; asettelun vaihto ja värikopio ohi, KOTI5 ladattu) värimuisti VD_C2 merkkiriveille VR_CR0.. (kaksi riviä
; kehyksessä), sitten vr_st 1.
vr_gate                         ; logic_frame ennen pysähdystä: C = 0, kun vk_step saa jatkaa (rivien värimuisti valmis)
        lda vr_st
        bne _ok
        lda frame+1
        cmp #>VR_F
        bcc _no
        bne +
        lda frame
        cmp #<VR_F
        bcc _no
+       lda #2                  ; kaksi riviä kehyksessä
        sta vr_t
_rw     ldx vr_c
        cpx #VR_CRN
        bcs _done
_cl     lda #<($d800 + 40 * VR_CR0)   ; rivin osoite koodissa (KOTI1 täynnä, ei taulua)
        sta vk_t
_ch     lda #>($d800 + 40 * VR_CR0)
        sta vk_t + 1
        ldy #39
        lda #VD_C2
-       sta (vk_t),y
        dey
        bpl -
        lda _cl + 1
        clc
        adc #40
        sta _cl + 1
        bcc +
        inc _ch + 1
+       inc vr_c
        dec vr_t
        bne _rw
_no     sec
        rts
_done   inc vr_st
_ok     clc
        rts

; vk_step:n uusi lista (A = vaihe, säilyy): siirto d = (ppx >> 3) * 320 + (ppx & 7) + pankki (d1 = d + 312, kun rivi
; ylittää merkkirivin); jos ppx on muuttunut, edellinen lista (vk_p) nollataan vanhalla siirrolla (vr_zon).
vr_list
        pha
        lda vr_on               ; perillä (siirto 0, ei nollausta): ei mitään (ei lisätyötä tekijäjaksoon)
        bne +
        lda ppx
        ora vr_pp
        bne +
        lda vr_pv
        bne _r
+       lda ppx                 ; lista näkyy noin 6-12 kehystä ja kamera nousee: siirto riviä alempaa (ppx - 1)
        beq +
        sec
        sbc #1
+       sta vr_t
        lda vr_pv
        beq _new
        lda vr_t
        cmp vr_pp
        beq _new
        ldx vk_p
        lda vk_llo,x
        sta il_p                ; vapaa iltaan (ILTA_F) asti
        lda vk_lhi,x
        sta il_p + 1
        lda vk_d0,x
        sta vr_zy
        lda vk_ln,x
        sta vr_ze
        ldx #4
-       lda vr_d,x              ; vr_d (4) ja vr_pl -> vr_zd, vr_zpl
        sta vr_zd,x
        dex
        bpl -
        inc vr_zon
_new    lda vr_t
        sta vr_pp
        and #7
        sta vr_pl
        lda vr_pp
        lsr a
        lsr a
        lsr a
        sta vr_t                ; q * 320 = (q & 3) << 6 + 256 * (q + (q >> 2))
        lsr a
        lsr a
        clc
        adc vr_t
        sta vr_d + 2
        lda vr_t
        ror a
        ror a
        ror a
        and #$c0
        ora vr_pl
        sta vr_d
        lda bank                ; näkyvä pankki kuten motion_step (badj): 3 ($e000) tai 2
        bne +
        lda #$c0
        clc
        adc vr_d + 2
        sta vr_d + 2
+       lda vr_d
        clc
        adc #<312
        sta vr_d + 1
        lda vr_d + 2
        adc #>312
        sta vr_d + 3
        inc vr_pv
        jsr vr_onf
_r      pla
        rts
vr_onf  lda vr_d                ; vr_on: siirto tai nollaus kesken
        ora vr_d + 2
        ora vr_zon
        sta vr_on
        rts

; vk_step:n osa siirrolla: ensin edellisen listan nollaus (vr_zon), sitten nykyinen lista kuten _part
vr_part
        lda vr_zon
        beq _w
        ldy vr_zy
        cpy vr_ze
        bcc +
        lda #0
        sta vr_zon
        jsr vr_onf
        jmp _w
+       tya
        clc
        adc #VK_K3
        bcs +
        cmp vr_ze
        bcc ++
+       lda vr_ze
+       sta vk_lim
-       lda (il_p),y            ; osoitteen alatavu: rivi y & 7
        tax
        and #7
        clc
        adc vr_zpl
        cmp #8                  ; C: kohde seuraavassa merkkirivissä
        txa
        ldx #0
        bcc +
        inx
+       clc
        adc vr_zd,x
        sta vk_t
        iny
        lda (il_p),y
        adc vr_zd + 2,x
        sta vk_t + 1
        iny
        iny
        lda #0
        tax
        sta (vk_t,x)
        cpy vk_lim
        bcc -
        sty vr_zy
_w      ldy vk_y
        cpy vk_e
        bcs _end
        tya
        clc
        adc #VK_K3
        bcs +
        cmp vk_e
        bcc ++
+       lda vk_e
+       sta vk_lim
-       lda (vkp),y
        tax
        and #7
        clc
        adc vr_pl
        cmp #8
        txa
        ldx #0
        bcc +
        inx
+       clc
        adc vr_d,x
        sta vk_t
        iny
        lda (vkp),y
        adc vr_d + 2,x
        sta vk_t + 1
        iny
        lda (vkp),y
        iny
        bit vk_md
        bpl _st                 ; ilta: maskin tavu ja välke
        bvs _z
        jsr pairs11             ; päivä: vain välke (%11)
        .byte $2c               ; bit abs: ohitetaan lda #0
_z      lda #0                  ; tyhjennys
_st     ldx #0
        sta (vk_t,x)
        cpy vk_lim
        bcc -
        sty vk_y
        rts
_end    bit vk_md               ; tyhjennys valmis: odottaa iltaa
        bvc +
        lda #4
        sta vk_s
+       rts

        .send koti1tail

; Auringonlasku: kehyksestä SUNSET_F askel s = 0..15 SUNSET_STEP kehyksen välein; askeleen
; vaihtuessa sen askeleen rivit far_curiin iltavärinä ss_c (rivin askel Bayer-ditherinä: liukenee); askeleesta 8 kimallus
; lämpimänä (gl_ring2). Liikkuvaa aurinkoa ei ole.
sunset_step
        lda frame+1             ; s = (frame - SUNSET_F) / SUNSET_STEP
        cmp #>SUNSET_F
        bcc _r
        bne +
        lda frame
        cmp #<SUNSET_F
        bcc _r
+       dec ss_cnt
        bpl _r
        lda #SUNSET_STEP - 1
        sta ss_cnt
        lda ss_s
        cmp #16
        bcs _r
        inc ss_s
        cmp #8
        bne +
        lda #<gl_ring2
        sta glp
        lda #>gl_ring2
        sta glp+1
+       ldx ss_s                ; askeleessa s illaksi vaihtuvat rivit: ss_rows[ss_beg[s - 1] .. ss_beg[s] - 1]
        ldy ss_beg - 1,x
        lda ss_beg,x
        sta mtmp
        cpy mtmp                ; ei rivejä (iltavärit tulevat ilta_stepistä): ei läpikäyntiä eikä taivasrivien
        bcs _r                  ; kopiota (fc_lo/fc_up 1 joka askeleessa veisi noin 1 600 sykliä + kopion
        lda #1                  ; kehyksessä illan maalauksen päälle, ja spritejoukko olisi rajalla)
        sta fc_up
        sta fc_lo
-       cpy mtmp
        bcs _r
        ldx ss_rows,y
        lda ss_c,x
        sta far_cur,x
        iny
        bne -
_r      rts


        .section koti5code
; Ilta ditherinä (KOTI5:ssä, KOTI1 täynnä; logic_frame kutsuu kehyksestä ILTA_F, kun KOTI5 on ladattu) (build.py
; ilta_tables, ilta_v4_maski.npy): ensin merkkirivien ruututavut (maskivärit %01/%10, IL_SCR_N kehystä, ei vielä
; näy), sitten maskirivi kehyksessä ylhäältä alas, ja rivien $D021 (far_cur) vaihtuu kaistoihin maskin mukana.
ilta_step
        lda il_h                ; maskirivin toinen puolikas (tavut 10-19) tässä kehyksessä: koko rivi kerralla
        beq +                   ; (noin 1 900 sykliä) ja järven alaosan tapahtumien läpikäynti myöhästyttäisivät
        lda #0                  ; spritejoukon (pääskyset 25 Hz)
        sta il_h
        lda #20
        sta il_je
        ldy il_j
        jmp _ml
+       ldx il_k
        cpx #IL_SCR_N + IL_N
        bcs _r
        inc il_k
        cpx #0
        bne _ni
        lda badj                ; ensimmäinen askel: näkyvän asettelun pankki, ruudun alku
        clc
        adc #$c0
        sta il_p + 1
        lda #0
        sta il_p
_ni     cpx #IL_SCR_N
        bcs _mask
        lda il_scr,x            ; ruuturivi x
        ldy #39
-       sta (il_p),y
        dey
        bpl -
        lda il_p
        clc
        adc #40
        sta il_p
        bcc _r
        inc il_p + 1
_r      rts
_mask   txa
        sbc #IL_SCR_N           ; C = 1
        tax
        lda il_row,x
        sta il_f
        and #$7f
        cpx #IL_N - 1
        bne +
        lda #SKY_MAX            ; viimeinen: $D021 loppuun asti
+       sta mzy
        ldy il_last
        sty fs_lo
-       lda il_d021,y           ; rivien $D021 kaistoihin tähän riviin asti
        sta far_cur,y
        iny
        cpy mzy
        bcc -
        beq -
        sty il_last
        sty fs_hi
        txa
        pha
        lda #0                  ; rajat voivat muuttua: _d21ev käy rivit läpi
        jsr fc_sync
        pla
        tax
        lda il_row,x
        and #$7f
        tay
        lsr a
        lsr a
        lsr a
        sta mzt
        tya
        and #7
        ldy mzt
        clc
        adc r320_lo,y
        sta il_p
        lda r320_hi,y
        adc #$e0
        clc
        adc badj
        sta il_p + 1
        lda il_mlo,x
        sta il_s
        lda il_mhi,x
        sta il_s + 1
        lda #10                 ; ensimmäinen puolikas
        sta il_je
        sta il_h
        ldy #0
        sty il_j
_ml     lda (il_s),y            ; 8 MC-pikseliä: 2 bittikarttatavua (sarakkeet 2j ja 2j + 1)
        sta il_b
        lsr a
        lsr a
        lsr a
        lsr a
        tax
        lda il_exp,x
        bit il_f
        bpl +
        asl a
+       ldy #0
        jsr il_put
        lda il_b
        and #$0f
        tax
        lda il_exp,x
        bit il_f
        bpl +
        asl a
+       ldy #8
        jsr il_put
        lda il_p
        clc
        adc #16
        sta il_p
        bcc +
        inc il_p + 1
+       inc il_j
        ldy il_j
        cpy il_je
        bcc _ml
        rts
        .send koti5code
il_exp  .byte $00, $01, $04, $05, $10, $11, $14, $15, $40, $41, $44, $45, $50, $51, $54, $55   ; ilta_step (KOTI1)

; Pääskyset palaavat järven ylle kehyksellä BIRD_RET (liike loppuun asti): rivit br_line, lähtö ruudun
; ulkopuolelta, spritet 0-2.
bird_ret
        lda frame+1
        cmp #>BIRD_RET
        bne _r
        lda frame
        cmp #<BIRD_RET
        bne _r
        ldy #N_BIRD - 1
-       ldx br_si,y
        lda br_line,y
        sta st_line,x
        lda br_xlo,y
        sta bd_xl,y
        lda br_xhi,y
        sta bd_xh,y
        lda #0
        sta bd_gone,y
        dey
        bpl -
        lda #32 + 2             ; vain spritet 0-2 (DMA edellisen rivin lopussa: spritet 3-7 hakevat 21 riviä rivin
        sta bd_lo               ; alussa ja myöhästyttäisivät $D021-tapahtumat, harmaa piste), X-laajennus
_r      rts

        .section koti5code      ; dusk_step ja fc_sync: demossa KOTI5:ssä (build.py), KOTI1 täynnä; kutsutaan vasta
                                ; kun KOTI5 on ladattu (k5ok) ja ilta on alkanut (ILTA_F)
; Hidas tummuminen kehyksestä DUSK_F: DUSK_N askelta DUSK_STEP kehyksen välein. Askel kulkee ylhäältä alas
; merkkirivi kerrallaan, rivi 40 / DK_B kehyksessä (build.py): ensimmäisessä sen 8 ikkunarivin $D021 (far_cur, dusk_tab),
; ja jokaisessa DK_B ruututavua (maskin värit %01/%10, nibblet dusk_tabin ja dusk_hin kautta). Rivi IL_SCR_N: loput
; $D021-rivit SKY_MAXiin. Koko askel kerralla (2 900 + 16 x 1 800 sykliä) venyttäisi kehystä: kuva hajoaisi ja
; spritejoukko myöhästyisi.
dusk_step
        lda dk_n
        cmp #DUSK_N
        bcs _r
        lda frame+1
        cmp #>DUSK_F
        bcc _r
        bne +
        lda frame
        cmp #<DUSK_F
        bcc _r
+       inc dk_w
        lda dk_w
        cmp #DUSK_STEP
        bcc +
        lda #0                  ; seuraava askel
        sta dk_w
        sta dk_j
        sta dk_q
        inc dk_n
_r      rts
+       ldx dk_j
        cpx #IL_SCR_N + 1
        bcs _r
        lda dk_q
        bne _scr
        txa                     ; merkkirivin $D021-rivit 8j..8j+7 (rivi IL_SCR_N: SKY_MAXiin)
        bne +
        sta il_p                ; askeleen alku: ruudun alku
        lda badj
        clc
        adc #$c0
        sta il_p + 1
        txa
+       asl a
        asl a
        asl a
        tax
        clc
        adc #8
        cpx #8 * IL_SCR_N
        bcc +
        lda #SKY_MAX + 1
+       sta dk_e
        sta fs_hi
        stx fs_lo
-       ldy far_cur,x
        lda dusk_tab,y
        sta far_cur,x
        inx
        cpx dk_e
        bcc -
        lda #1                  ; vain värit (build.py: rajat säilyvät)
        jsr fc_sync
        lda dk_j
        cmp #IL_SCR_N
        bcc _scr
        inc dk_j
        rts
_scr    ldy #DK_B - 1           ; DK_B ruututavua, nibblet dusk_tabin ja dusk_hin kautta (256 tavun taulu ei
-       lda (il_p),y            ; mahtuisi KOTI5:een)
        tax
        and #15
        sta dk_lo
        txa
        lsr a
        lsr a
        lsr a
        lsr a
        tax
        lda dusk_hi,x
        ldx dk_lo
        ora dusk_tab,x
        sta (il_p),y
        dey
        bpl -
        lda il_p
        clc
        adc #DK_B
        sta il_p
        bcc +
        inc il_p + 1
+       inc dk_q
        lda dk_q
        cmp #40 / DK_B
        bcc _r2
        lda #0
        sta dk_q
        inc dk_j
_r2     rts

; far_cur muuttui riveillä fs_lo..fs_hi - 1 (ilta_step, dusk_step; p = 0): taivassilmukan rivit suoraan d21line:en
; (lf_place ei kopioi kaikkia 73 riviä) ja rivistä SKY_LAST alas joko $D021-tapahtumien värit välimuistiin (A = 1,
; dusk_step: vain värit, rajat ennallaan) tai illan rajat il_hi:hin asti (A = 0, ilta_step: fc_lo = 2, _dil). Koko
; kopio tai läpikäynti joka kehys myöhästyttäisi spritejoukon (pääskyset 25 Hz).
fc_sync sta fs_m
        ldx fs_lo
-       cpx fs_hi
        bcs _tail
        cpx lf_mzt
        bcs _tail
        lda far_cur,x
        sta d21line + T_LINE,x
        inx
        bne -
_tail   ldx lf_mzt              ; silmukan jälkeiset rivit jatkavat sen viimeistä väriä (lf_place)
        beq _low
        dex
        cpx fs_lo
        bcc _low
        cpx fs_hi
        bcs _low
        lda far_cur,x
        sta d21line + T_LINE + 1,x
        sta d21line + T_LINE + 2,x
        sta d21line + T_LINE + 3,x
_low    lda fs_hi
        cmp #SKY_LAST + 1
        bcc _r
        lda fs_m
        beq _ilta
        lda d2_n
        cmp #D21EV_MAX + 1
        bne _scan
        ldx d2_cnt              ; tapahtumien värit: rivi = d2_line - (T_LINE - 3)
-       dex
        bmi _r
        ldy d2_line,x
        lda far_cur - (T_LINE - 3),y
        sta d2_col,x
        jmp -
_scan   lda #1                  ; _d21ev käy rivit läpi
        sta fc_lo
        rts
_ilta   lda fs_hi               ; ilta_step: _d21ev illan rajoista (fc_lo 2), ellei läpikäynti ole jo tulossa
        sta il_hi
        lda fc_lo
        cmp #1
        beq _r
        lda #2
        sta fc_lo
_r      rts


; Järven välke (maisema.json kuten lopussa: sauma jatkuu) kameran pysähdyksestä (logic_frame, phase 2).
; Päivällä (vk_md $80: tekijäjaksossa järvi ei seiso): välkesolujen värimuisti VD_C1/VD_C2, sitten samat
; vaiheet kuin illalla, mutta listat riviltä VD_ROW (vk_d0) ja tavusta vain %11 (pairs11, maski on %01/%10)
; päiväjärven päälle. Kehyksestä VD_END nykyisen vaiheen lista nollina (vk_md $c0), ennen kuin ilta_step maalaa
; järven (build.py: VK_PARTS kehystä ennen kuin maalaus on rivillä VD_ROW). Illalla (vk_md 0) kehyksestä VK_F, kun ilta on maalattu: ensin välkesolujen värimuisti (%11) 8 solua
; kehyksessä, sitten vaihe c / VK_DT, c demon kellosta niin, että lopun kehys 0 on vaihe 0 kuten loppu.asm vk_stepissä
; (build.py VK_OF). Välke alkaa seuraavasta vaihdoksesta. Vaiheen vaihtuessa sen lista vk_l<p> (osoite, uusi tavu:
; edellinen vaihe pois, uusi päälle) kirjoitetaan VK_PARTS kehyksessä näkyvän asettelun bittikarttaan (osoitteet
; pankissa 3, badj).
vk_step
        lda vk_s
        beq _day
        cmp #4
        beq _eve
        cmp #2
        bcs _run
        bcc _col
_eve    lda il_k                ; ilta maalattu?
        cmp #IL_SCR_N + IL_N
        bcc _r
        lda il_h
        bne _r
        lda frame+1
        cmp #>VK_F
        bcc _r
        bne +
        lda frame
        cmp #<VK_F
        bcc _r
+       lda #0                  ; ilta: maskin tavu ja välke
        .byte $2c               ; bit abs: ohitetaan lda #$80
_day    lda #$80                ; päivä: vain välke
        sta vk_md
        lda #1
        sta vk_s
        lda #0
        sta vk_j
_col    ldy #0
        ldx vk_j
-       cpx #VK_CELLS
        bcs _arm
        lda vk_clo,x
        sta vk_t
        lda vk_chi,x
        ora #$d8
        sta vk_t + 1
        lda vk_ccol,x
        bit vk_md
        bpl +
        lda #VD_C1              ; päivä: vaalealla kaistalla (solut 0..VD_K-1) VD_C1, sinisellä järvellä VD_C2
        cpx #VD_K
        bcc +
        lda #VD_C2
+       sta (vk_t),y
        inx
        txa
        and #7
        bne -
        stx vk_j
_r      rts
_arm    lda #2                  ; värimuisti valmis
        sta vk_s
        rts
_run    bit vk_md
        bvs _part               ; tyhjennys: lista loppuun
        bpl _c
        lda frame               ; päivä: kehyksestä VD_END nykyisen vaiheen lista nollina
        cmp #<VD_END
        lda frame+1
        sbc #>VD_END
        bcc _c
        lda #$c0
        sta vk_md
        ldx vk_p
        bpl _list
_c      lda DFRAME              ; c = (DFRAME - TIM_SCENE_KOTI_START + VK_OF) mod VK_M (ylätavun yksikkö = 256 % VK_M)
        sec
        sbc #<TIM_SCENE_KOTI_START
        tay
        lda DFRAME+1
        sbc #>TIM_SCENE_KOTI_START
        tax
        tya
-       cmp #VK_M
        bcc +
        sbc #VK_M
        bcs -
+       cpx #0
        beq _m
-       clc
        adc #256 % VK_M
        cmp #VK_M
        bcc +
        sbc #VK_M
+       dex
        bne -
_m      clc
        adc #VK_OF
        cmp #VK_M
        bcc +
        sbc #VK_M
+       ldx #0                  ; vaihe = c / VK_DT
-       cmp #VK_DT
        bcc +
        sbc #VK_DT
        inx
        bne -
+       txa
        ldx vk_s
        cpx #3
        bcs _ph
        inc vk_s                ; alku: vaihe talteen; seuraava vaihdos (lista: maskin tavu ja uuden vaiheen %11)
        sta vk_p                ; kirjoittaa uuden vaiheen myös välkkeettömään kuvaan
        rts
_ph     cmp vk_p
        beq _part
        jsr vr_list             ; nousun siirto ja edellisen listan nollaus (KOTI1)
        sta vk_p
        tax
_list   lda vk_llo,x
        sta vkp
        lda vk_lhi,x
        sta vkp + 1
        lda vk_ln,x
        sta vk_e
        lda #0
        bit vk_md
        bpl +
        lda vk_d0,x             ; päivä ja tyhjennys: järven rivit (VD_ROW-)
+       sta vk_y
_part   lda vr_on               ; nousussa: siirto (vr_part, KOTI1)
        beq +
        jmp vr_part
+       ldy vk_y                ; seuraavat enintään VK_K3 / 3 tavua
        cpy vk_e
        bcs _end
        tya
        clc
        adc #VK_K3
        bcs +
        cmp vk_e
        bcc ++
+       lda vk_e
+       sta vk_lim
        ldx #0
-       lda (vkp),y
        sta vk_t
        iny
        lda (vkp),y
        clc
        adc badj
        sta vk_t + 1
        iny
        lda (vkp),y
        iny
        bit vk_md
        bpl _st                 ; ilta: maskin tavu ja välke
        bvs _z
        jsr pairs11             ; päivä: vain välke (%11)
        .byte $2c               ; bit abs: ohitetaan lda #0
_z      lda #0                  ; tyhjennys
_st     sta (vk_t,x)
        cpy vk_lim
        bcc -
        sty vk_y
        rts
_end    bit vk_md               ; tyhjennys valmis: odottaa iltaa
        bvc +
        lda #4
        sta vk_s
+       rts
        .send koti5code

; kehyslaskuri ja kameran paikka yhden kehyksen eteenpäin
motion_step
        inc frame
        bne +
        inc frame+1
+       lda phase
        beq _hold0
        cmp #1
        beq _move
        bne _ret
_hold0  lda frame+1             ; pito portailla
        bne _go
        lda frame
        cmp #HOLD0
        bcc _ret
_go     lda #1
        sta phase
        lda #MDIV - 1
        sta mdiv
        lda #<MOVE_N
        sta mcount
        lda #>MOVE_N
        sta mcount+1
_move   ldy #0                  ; pos -= nopeus[i / MDIV]
        lda pos
        sec
        sbc (mptr),y
        sta pos
        bcs +
        dec pos+1
+       dec mdiv
        bpl +
        lda #MDIV - 1
        sta mdiv
        inc mptr
        bne +
        inc mptr+1
+       lda mcount
        bne +
        dec mcount+1
+       dec mcount
        lda mcount
        ora mcount+1
        bne _ret
        lda #2
        sta phase
        lda bank                ; kamera perillä: bittikartan pankki tekijöille, välkkeelle ja illalle (badj)
        beq +
        lda #0
        .byte $2c               ; bit abs: ohitetaan lda #$c0
+       lda #$c0
        sta badj
_ret    rts

; Tekijät järvelle (nimet tekstit.yaml tekijat): kun nousu on ohi (phase 2) ja
; CRED_WAIT kehystä kulunut, CRED_PF pikseliä kehyksessä build.py:n vetojärjestyksessä (luuranko kynänvetoina),
; MC %11 näkyvän asettelun bittikarttaan, värimuisti CRED_COL (vaalea, erottuu iltataivaasta), "dipe"n jälkeen tauko.
cred_step
        lda phase
        cmp #2
        bne _r
        lda cdel
        beq _go
        dec cdel
        bne _r
        lda #CRED_COL           ; tekijät %11: värimuisti nimien suorakaiteissa järvellä (build.py CRA_*, CRB_*).
        ldx #CRA_W - 1          ; Alussa ja tauon jälkeen: päivän välkkeen värimuisti (kamera pysähtyy) kirjoitetaan
-       .for _cr := CRA_R0, _cr <= CRA_R1, _cr += 1   ; samoihin aikoihin, tauon jälkeen nimien väri jää
        sta $d800 + 40 * _cr + CRA_C0,x
        .next
        dex
        bpl -
        ldx #CRB_W - 1
-       .for _cr := CRB_R0, _cr <= CRB_R1, _cr += 1
        sta $d800 + 40 * _cr + CRB_C0,x
        .next
        dex
        bpl -
        rts
_go     ldx #CRED_PF
_px     lda cleft
        ora cleft+1
        beq _r
        lda cleft               ; "dipe" valmis: tauko ennen "patemathic"ia
        cmp #<CRED_N2
        bne +
        lda cleft+1
        cmp #>CRED_N2
        bne +
        lda cpz
        bne +
        inc cpz
        lda #CRED_PAUSE
        sta cdel
        rts
+       ldy #0                  ; kynän askel (build.py cred_steps): (dy + 8) << 4 | (dx + 8), tai $88, rivi, MC-x
        lda (cptr),y
        cmp #$88
        bne _d
        iny
        lda (cptr),y
        sta cr_y
        iny
        lda (cptr),y
        sta cr_x
        lda #3
        bne _adv
_d      pha
        lsr a
        lsr a
        lsr a
        lsr a
        clc
        adc cr_y
        sec
        sbc #8
        sta cr_y
        pla
        and #15
        clc
        adc cr_x
        sec
        sbc #8
        sta cr_x
        lda #1
_adv    clc
        adc cptr
        sta cptr
        bcc +
        inc cptr+1
+       lda cr_y                ; bittikartta + (rivi >> 3) * 320 + (x >> 2) * 8 + (rivi & 7)
        lsr a
        lsr a
        lsr a
        tay
        lda cr_x
        and #$fc
        asl a
        sta cz
        lda #$e0 / 2
        rol a
        sta cz+1
        lda cr_y
        and #7
        ora cz
        clc
        adc r320_lo,y
        sta cz
        lda cz+1
        adc r320_hi,y
        clc
        adc badj
        sta cz+1
        lda cr_x
        and #3
        tay
        lda cbits,y
        ldy #0
        ora (cz),y
        sta (cz),y
        lda cleft
        bne +
        dec cleft+1
+       dec cleft
        dex
        bne _px
_r      rts
cbits   .byte $c0, $30, $0c, $03        ; %11

; ilta_step: maskin tavu A bittikarttaan (il_p),y niin, että jo piirretyt tekijöiden %11-pikselit jäävät (tekijät
; piirtyvät sinitaivaalle ennen iltaa): %11-parit vanhasta tavusta ovat ykkösiä, joten uusi | maski
il_put  sta mtmp
        lda (il_p),y
        jsr pairs11
        ora mtmp
        sta (il_p),y
        rts

; A:n MC-pikselit %11, muut nollia: tekijät ja välke ovat %11, illan maski %01/%10 (il_put, vk_step päivällä)
pairs11 sta mzt
        lsr a
        and mzt
        and #$55
        sta mzt
        asl a
        ora mzt
        rts

lf_place
        lda pos                 ; ppx = (pos + 128) >> 8: bittikartta pyöristettynä (kehyksessä 1 vielä P_MAX;
        cmp #$80                ; ensimmäisen kehyksen linecrunch ff = 7:llä ylärivin värit puuttuisivat)
        lda pos+1
        adc #0
        sta ppx
        .if LAYOUTS > 1
        ldx k_cur               ; vaihto edelliseen, kun ppx < näkyvän asettelun alku ja edellinen on valmis
        beq _in
        lda ppx
        cmp lbase
        bcs _in
        lda ready
        beq _in
        dex                     ; näkyvä pankki vaihtuu seuraavan kehyksen yläreunassa
        stx k_cur
        lda lay_px_lo,x
        sta lbase
        lda bank
        eor #1
        sta bank
        lda #0
        sta ready
        lda #1
        sta colsw
        .endif
_in     lda ppx                 ; plyt = ppx - lbase (alle 0: takapankki ei ehtinyt, pysytään alussa)
        sec
        sbc lbase
        bcs +
        lda #0
        inc stalls
+       cmp #CMAX * 8 + 8
        bcc +
        lda #CMAX * 8 + 7
+       tax
        cpx cs_x                ; sama plyt ja pankki kuin edellisessä: sekvensseritaulu ennallaan (noin 650 sykliä,
        bne +                   ; illalla kamera paikallaan: pelivara)
        lda bank
        ora #$80
        cmp cs_b
        beq ++
+       stx cs_x
        lda bank
        ora #$80
        sta cs_b
        jsr cr_seq
+
; taivasrivit: ikkunan rivi w näyttää kuvan rivin ppx + w; jos se on < SKY_T, $D021 = far_tab[w] (kimallusriveillä
; GL0..GL1-1 väriliukujonosta), muuten 0 (alempana vain mustat %00-pikselit)
        inc gph
        lda ppx                 ; taivasrivit vain, kun ppx tai far_cur riveillä 0..SKY_LAST on muuttunut (fc_up),
        cmp lf_ppx              ; muuten vain kimallus (kopio noin 1 000 sykliä joka kehys)
        bne _full
        lda fc_up
        bne _full
        lda lf_mzt
        sta mzt
        jmp _glr
_full   lda ppx
        sta lf_ppx
        lda #0
        sta fc_up
        sta lf_mzt
        lda #1
        sta d21end
        lda #0
        sta d21line + T_LINE
        sta d21line + T_LINE + 1
        sta d21line + T_LINE + 2
        sta d21line + T_LINE + 3
        lda #SKY_T
        sec
        sbc ppx
        beq _nsky
        bcc _nsky
        sta mtmp                ; taivasrivejä n
        lda #SKY_LAST + 1       ; enintään SKY_LAST + 1 riviä: silmukka päättyy ennen alareunan IRQ:ta, loput
        cmp mtmp                ; rivit jatkavat viimeisen värillä
        bcc +
        lda mtmp
+       sta mzt                 ; n taivasriviä (rivit 72..72+n-1), rivi 72+n = 0
        sta lf_mzt
        clc
        adc #T_LINE + 1
        sta d21end
        ldx #0
-       lda far_cur,x
        sta d21line + T_LINE,x
        inx
        cpx mzt
        bne -
        lda #0
        ldy mtmp
        cpy mzt
        beq +
        lda far_cur - 1,x       ; taivasta silmukan alapuolellakin: alarivit samaa väriä
+       sta d21line + T_LINE,x
        sta d21line + T_LINE + 1,x
        sta d21line + T_LINE + 2,x
_glr
        .if GL1 > GL0
        ldx #GL0                ; kimallus: gl_ring[((vaihe + gl_add[rivi]) & 255) / 8], rivit porrastettu
_gl     cpx mzt
        bcs _nsky
        lda gph
        clc
        adc gl_add - GL0,x
        lsr a
        lsr a
        lsr a
        tay
        lda (glp),y             ; gl_ring, auringonlaskussa gl_ring2 (sunset_step)
        sta d21line + T_LINE,x
        inx
        cpx #GL1
        bne _gl
        .endif
_nsky   rts

; ---------------------------------------------------------------- spritet seuraavaan kehykseen (joukko nx)
spr_frame
        lda frame               ; kehys ja pääskyset talteen: logic_frame (yläreunan IRQ) muuttaa niitä kesken
        sta sfr                 ; laskennan, ja pääskysen kuva riippuisi muuten siitä, ehtiikö laskenta ennen sitä
        ldx #N_BIRD - 1
-       lda bd_xl,x
        sta sbd_xl,x
        lda bd_xh,x
        sta sbd_xh,x
        lda bd_gone,x
        sta sbd_g,x
        dex
        bpl -
        lda pos                 ; paikka kehyksessä, jossa joukko näytetään (yksi liikeaskel eteenpäin)
        sta spos
        lda pos+1
        sta spos+1
        lda phase
        cmp #1
        bne +
        ldy #0
        lda spos
        sec
        sbc (mptr),y
        sta spos
        bcs +
        dec spos+1
+       lda spos                ; sppx = (spos + 128) >> 8 kuten lf_place
        cmp #$80
        lda spos+1
        adc #0
        sta sppx
        lda cur
        eor #1
        sta nx
        tax
        lda #0
        cpx #0
        beq +
        lda #MAXE
+       sta eb
        txa
        asl a
        asl a
        asl a
        sta ib
        lda #0
        sta ne
        sta first
        sta fi
        sta si
        sta catf
        sta in_01d,x
        sta in_01b,x
        sta in_en,x
        sta in_010,x
        ldx #7
-       sta lastend,x
        dex
        bpl -
        ldx nx
        lda #$ff
        sta in_01c,x
        lda #0
        sta rrhw
        lda #SKY_T - 1          ; taivasvyöhykkeen viimeinen rivi T_LINE + SKY_T - 1 - sppx (yli 255: 255)
        sec
        sbc sppx
        bcc +
        clc
        adc #T_LINE
        bcc ++
        lda #255
        bne ++
+       adc #T_LINE             ; C = 0, vyöhyke ikkunan yläpuolella
+       sta zl
; etualan rivi 0 näyttörivillä fgl = 72 + FG_T0 - (FG_K16 * spos) >> 12 (tulo 24 bittiä: stmp, stmp+1, zt; spos
; 1/256 px, joten kissa liikkuu tasaisesti myös hitaassa alussa); kun fgl >= 256, kissa on mennyt kuvan alle
; lopullisesti (kamera vain nousee): kertolasku pois (noin 300 sykliä)
        lda fgl+1
        bne _fgok
        lda #0
        sta stmp
        sta stmp+1
        sta zt
        sta zy
        lda spos
        sta sltmp
        lda spos+1
        sta sltmp+1
        lda #FG_K16
        sta c_k
        ldx #8
-       lsr c_k
        bcc +
        clc
        lda stmp
        adc sltmp
        sta stmp
        lda stmp+1
        adc sltmp+1
        sta stmp+1
        lda zt
        adc zy
        sta zt
+       asl sltmp
        rol sltmp+1
        rol zy
        dex
        bne -
        ldx #4                  ; >> 12
-       lsr zt
        ror stmp+1
        dex
        bne -
        lda #<(T_LINE + FG_T0)
        sec
        sbc stmp+1
        sta fgl
        lda #>(T_LINE + FG_T0)
        sbc zt
        sta fgl+1
_fgok   lda #0                  ; kissa näkyy (fgl <= SPR_BOT): $D025 kissan mustaksi ja pääskysten 21 rivin ikkuna
        sta boff                ; BIRD_LOW riviä aiemmin (alaversio: sama kuva, sprite vapautuu kissan viipaleille)
        lda #BIRD_PTR0
        sta bptr
        lda #SPR_D025
        ldy #SPR_D026
        ldx ss_s                ; auringonlaskussa Liessaari tummaksi
        cpx #10
        bcc +
        lda #EVE_D025
        ldy #EVE_D026
+       sta sd025
        sty sd026
        lda fgl+1               ; kissa näkyy, kun ylin instanssi alkaa ikkunassa (fgl <= CAT_VIS)
        bne _nocat
        lda fgl
        cmp #CAT_VIS + 1
        bcs _nocat
        lda #BIRD_LOW
        sta boff
        lda #BIRD_LPTR0
        sta bptr
        lda #CAT_D025
        sta sd025
        lda #CAT_D026
        sta sd026
        lda frame               ; kissan tilat: häntä 64 kehyksen kierrossa, pää kohtauksen alusta (an_st + 1 = 0;
        and #63                 ; taulut 2 bittiä tilaa kohden, demossa yläreunan puskureissa vain kissan aikana)
        tax
        lsr a
        lsr a
        tay
        lda an_tail,y
        jsr an_bits
        sta an_st + 2
        lda #0
        ldy frame+1
        bne +
        ldx frame
        cpx #AN_N
        bcs +
        txa
        lsr a
        lsr a
        tay
        lda an_head,y
        jsr an_bits
+       sta an_st
        jmp cat_set             ; kissan joukko kiinteällä jaolla (jatkuu sf_doneen)
; kiinteät ehdokkaat rivijärjestyksessä (kissa ei näy)
_nocat
_cand   ldx si
        cpx #N_ST
        bcs _d21ev
        jsr st_cand
        inc si
        jmp _cand
; Taivassilmukan (SKY_LAST) alapuolisten rivien $D021 tapahtumina (laji 2, arvo ev_y): rivin r väri on far_cur[r]
; taivasvyöhykkeellä (r < n) ja muuten 0; tapahtuma riville r - 1, kun väri vaihtuu (rivit SKY_LAST + 1..D21EV_MAX;
; alareunan IRQ 213:n lähellä tapahtuma rikkoisi ketjun). Edellinen väri: silmukan päätös (lf_place). Rivit käydään
; läpi (noin 1 600 sykliä) vain, kun n tai far_cur rivistä SKY_LAST alas on muuttunut (fc_lo), muuten välimuistista
; d2_*: pysähdyksen jälkeen läpikäynti joka kehys myöhästyttäisi spritejoukon joka toinen kehys (pääskyset 25 Hz).
_d21ev  lda #SKY_T
        sec
        sbc sppx
        bcs +
        lda #0
+       sta stmp                ; n
        cmp #D21EV_MAX + 2
        bcc +
        lda #D21EV_MAX + 1      ; n:n arvot D21EV_MAX + 1.. antavat saman listan
+       ldx fc_lo
        beq +
        cpx #2
        bne _dscan
        cmp #D21EV_MAX + 1
        beq _dil
        bne _dscan
+       cmp d2_n
        beq _drep
_dscan  sta d2_n
        lda #0                  ; ennen läpikäyntiä: kesken tullut kirjoitus (logic_frame) merkitsee uudelleen
        sta fc_lo
        sta d2_cnt
        ldx #SKY_LAST + 1       ; ensimmäinen taivassilmukan jälkeinen rivi
        cpx stmp
        bcs _drep               ; n <= rivi: silmukka kirjoittaa rajan itse
        lda far_cur - 1,x
        sta sltmp               ; edellinen väri: silmukan viimeinen rivi jatkuu
        lda stmp
        cmp #D21EV_MAX + 1
        bcc _dl
_df     lda far_cur,x           ; koko alue taivasvyöhykkeellä (p pieni): tiivis silmukka
        cmp sltmp
        bne _de
_dfn    inx
        cpx #D21EV_MAX + 1
        bcc _df
        bcs _drep
_de     sta sltmp
        ldy d2_cnt
        cpy #D2_MAX
        bcs _drep
        sta d2_col,y
        txa
        clc
        adc #T_LINE - 3
        sta d2_line,y
        inc d2_cnt
        jmp _dfn
_dl     lda #0
        cpx stmp
        bcs +
        lda far_cur,x
+       cmp sltmp
        beq _dn
        sta sltmp
        ldy d2_cnt
        cpy #D2_MAX
        bcs _drep
        sta d2_col,y
        txa
        clc
        adc #T_LINE - 3         ; IRQ kolme riviä ennen: IRQ:n alku vie noin rivin, ja saman rivin spritetapahtumat
        sta d2_line,y           ; ehtisivät ensin (kirjoitus kesken rivin, harmaa piste)
        inc d2_cnt
_dn     inx
        cpx #D21EV_MAX + 1
        bcc _dl
        bcs _drep
; ilta_step maalaa (fc_lo = 2): rivit il_hi:n yläpuolella ovat illan värejä, alla päiväjärveä (DAY_LO), joten lista on
; illan rajat (il_ev*, build.py) il_hi:n yläpuolelta ja raja riville il_hi
_dil    sta d2_n
        lda #0
        sta fc_lo
        lda il_hi
        sta sltmp
        ldx #0
-       cpx #IL_EVN
        bcs +
        lda il_evr,x
        cmp sltmp
        bcs +
        lda il_evl,x
        sta d2_line,x
        lda il_evc,x
        sta d2_col,x
        inx
        bne -
+       stx d2_cnt
        ldy sltmp
        cpy #D21EV_MAX + 1
        bcs _drep
        cpy #SKY_LAST + 1
        bcc _drep
        lda far_cur - 1,y
        cmp #DAY_LO
        beq _drep
        cpx #D2_MAX
        bcs _drep
        lda #DAY_LO
        sta d2_col,x
        tya
        clc
        adc #T_LINE - 3
        sta d2_line,x
        inc d2_cnt
_drep   ldx #0                  ; lista joukkoon
_dr     cpx d2_cnt
        bcs _srt
        ldy ne
        cpy #MAXE
        bcs _srt
        tya
        clc
        adc eb
        tay
        lda d2_col,x
        sta ev_y,y
        lda d2_line,x
        sta ev_line,y
        sta ev_key,y
        lda #2
        sta ev_kind,y
        tya
        sta ev_ord,y
        inc ne
        inx
        bne _dr
; järjestys: lisäyslajittelu käsittelyrivin (ev_key) mukaan, lähes järjestetty
_srt    ldx #1
sf_sort                         ; X = ensimmäinen järjestämätön (cat_set: alareunan tapahtumat)
_s1     cpx ne
        bcs _shadow
        stx stmp+1
        txa
        clc
        adc eb
        tay
        lda ev_ord,y
        sta zt
        tax
        lda ev_key,x
        sta stmp
        ldy stmp+1               ; j = i
_s2     beq _s3
        tya
        clc
        adc eb
        tax                     ; X = eb + j
        lda ev_ord - 1,x
        sta sltmp
        sty sltmp+1
        tay
        lda ev_key,y
        ldy sltmp+1
        cmp stmp
        bcc _s3
        beq _s3
        lda sltmp
        sta ev_ord,x
        dey
        jmp _s2
_s3     tya
        clc
        adc eb
        tax
        lda zt
        sta ev_ord,x
        ldx stmp+1
        inx
        jmp _s1
; rekisteribittien varjot tapahtumajärjestyksessä alkuinstansseista alkaen
_shadow lda catf
        bne cs_shad
        ldx nx
        lda in_010,x
        sta sh010
        lda in_01d,x
        sta sh01d
        lda in_01b,x
        sta sh01b
        lda in_01c,x
        sta sh01c
        ldx #0
_sh     cpx ne
        bcs sf_done
        txa
        clc
        adc eb
        tay
        lda ev_ord,y
        tay
        lda ev_kind,y
        cmp #1
        bne _shn
        stx stmp
        ldx ev_hw,y
        lda nbit,x
        and sh010
        sta sh010
        lda nbit,x
        and sh01d
        sta sh01d
        lda nbit,x
        and sh01b
        sta sh01b
        lda ev_bits,y           ; $D01C pysyy alkuarvossa (kaikki MC: hires-spritejä ei ole, tekstit txt_spr)
        lsr a
        bcc +
        lda bitv,x
        ora sh010
        sta sh010
+       lda ev_bits,y
        and #2
        beq +
        lda bitv,x
        ora sh01d
        sta sh01d
+       lda ev_bits,y
        and #4
        beq +
        lda bitv,x
        ora sh01b
        sta sh01b
+       lda sh010
        sta ev_010,y
        lda sh01d
        sta ev_01d,y
        lda sh01b
        sta ev_01b,y
        lda sh01c
        sta ev_01c,y
        ldx stmp
_shn    inx
        jmp _sh
; kissan joukon varjot tapahtumajärjestyksessä (alareunan tapahtumia): vain $D010 ja $D01D (irq_ev ohittaa kissan
; joukossa $D01C:n ja $D01B:n). Kissan X < 256 (pääskysen spritellä bitti pois), X-laajennus jalustalla
cs_shad ldx nx
        lda in_010,x
        sta sh010
        lda in_01d,x
        sta sh01d
        ldx #0
-       cpx ne
        bcs sf_done
        stx stmp
        txa
        ora eb
        tay
        lda ev_ord,y
        tay
        ldx ev_hw,y
        lda sh010
        and nbit,x
        sta sh010
        sta ev_010,y
        lda ev_bits,y
        and #2
        beq +
        lda bitv,x
+       sta zt
        lda sh01d
        and nbit,x
        ora zt
        sta sh01d
        sta ev_01d,y
        ldx stmp
        inx
        bne -
sf_done ldx nx
        lda ne
        sta ne_set,x
        lda sd025
        sta in_d025,x
        lda sd026
        sta in_d026,x
        ldy #0                  ; spritet 3-7 rivillä 215 -> alareunan kirjoitus aiemmin (kt_edge)
        ldx #3
-       lda lastend,x
        cmp #SPR_BOT
        bcc +
        iny
+       inx
        cpx #8
        bne -
        tya
        sec
        sbc #2
        bcs +
        lda #0
+       asl a
        cmp #7
        bcc +
        lda #6
+       ldx nx
        sta bot_r,x
        rts

; A = 4 tilan tavu, X = kehys: tila (A >> 2 (X & 3)) & 3
an_bits pha
        txa
        and #3
        tax
        pla
-       dex
        bmi +
        lsr a
        lsr a
        bpl -
+       and #3
        rts

; Kissan joukko (kissa näkyy: fgl <= CAT_VIS) kiinteällä jaolla (kissa tasaisesti 50 Hz:llä;
; yleinen place, lajittelu ja varjot veisivät 15 000-18 900 sykliä, kehykseen mahtuu noin 11 600):
;   pääskyset  spriteillä 5-7 (kissan takana), yksi alkuinstanssi kukin (alaversio kuten st_cand)
;   kissa      instanssi i riviltä fgl + fi_r[i] spritellä i & 3: edellinen samalla spritellä (i - 4) on päättynyt
;              vähintään 4 riviä aiemmin, joten tapahtumat syntyvät käsittelyjärjestyksessä (build.py cat_alloc)
;   alareuna   alku >= 196 (rivit kasvavat: loput instanssit): alku 195 ja data k riviä alas (cat_clip), joten DMA
;              päättyy riville 215 eikä myöhästytä alareunan $d011-kirjoitusta (rivin 216 DMA siirtäisi kirjoituksen
;              rivin 216 näkyvälle alueelle tai sen badlinen yli). Sprite järjestyksessä ct_hw (vapaa riviltä 191,
;              pääskyset ovat silloin päättyneet), tapahtumat lisäyslajittelulla paikalleen ja varjot cs_shadissa
; Varjot muuten samalla: $D010 pääskysten alkuarvo (kissan X < 256), $D01D 0. $D021-tapahtumia ei ole (taivasvyöhyke on
; kissan aikana taivassilmukan sisällä, build.py).
cat_set
        ldy #N_BIRD - 1
_bd     lda sbd_g,y             ; pääskynen Y spritelle 5 + Y: lentänyt pois?
        bne _bn
        lda sbd_xh,y            ; X = (x16 >> 4) & 511
        sta zy
        lda sbd_xl,y
        .rept 4
        lsr zy
        ror a
        .endrept
        sta c_xlo
        lda sfr                 ; rivi + aalto ja siipiasento (bd_fw, 32 kehyksen kierto)
        clc
        adc bd_ph,y
        and #31
        tax
        lda bd_fw,x
        pha
        and #3
        ldx br_si,y
        clc
        adc st_line,x
        sec
        sbc #BIRD_LOW + 1       ; Y-rekisteri: alkurivi - 1
        sta c_start
        lda st_col,x
        sta c_col
        pla
        lsr a
        lsr a
        clc
        adc #BIRD_LPTR0
        sta c_ptr
        sty hw
        tya
        clc
        adc #5
        tax
        lda bitv,x
        lsr zy                  ; X:n bitti 8
        bcc +
        ldy nx
        ora in_010,y
        sta in_010,y
        lda bitv,x
+       ora first
        sta first
        txa
        ora ib
        tay
        lda c_start
        sta in_y,y
        clc
        adc #21                 ; lastend = alkurivi + 20
        sta lastend,x
        lda c_xlo
        sta in_x,y
        lda c_ptr
        sta in_ptr,y
        lda c_col
        sta in_col,y
        ldy hw
_bn     dey
        bpl _bd
        ldx nx
        lda in_010,x
        sta sh010
        lda #$ff
        sta ct_t0
        ldx #0
_ct     stx fi
        lda fgl                 ; alkurivi fgl + fi_r[i]: yli 255 tai SPR_BOT, tämä ja loput ikkunan alla
        clc
        adc fi_rlo,x
        sta cl
        lda #0
        adc fi_rhi,x
        bne _cend
        lda cl
        cmp #SPR_BOT + 1
        bcs _cend
        ldy fi_an,x             ; muunnelma tilan mukaan: fi_ptr[an_mul[an_st[fi_an]] + i]
        lda an_st,y
        tay
        txa
        clc
        adc an_mul,y
        tay
        lda fi_ptr,y
        beq _cn                 ; ei instanssia (korvan kärki)
        sta c_ptr
        txa
        and #3
        sta hw
        lda cl
        cmp #SPR_BOT - 19
        bcc _put                ; alkaa <= 195: koko sprite ikkunassa
        ldy #0                  ; alareuna: vapaa sprite järjestyksessä ct_hw (edellinen päättynyt viimeistään riville
-       ldx ct_hw,y             ; 191, build.py cat_alloc)
        lda lastend,x
        cmp #SPR_BOT - 23
        bcc +
        iny
        cpy #MAX_HW
        bcc -
        inc drops
        bcs _cn
+       stx hw
        lda ne                  ; ensimmäinen alareunan tapahtuma (lajittelu)
        ldy ct_t0
        bpl +
        sta ct_t0
+       lda cl
        sec
        sbc #SPR_BOT - 20       ; k = cl - 195, alku 195
        sta c_k
        lda #SPR_BOT - 20
        sta cl
        jsr cat_clip            ; c_ptr = puskuri
        ldx fi
        clc
_put    ldy hw                  ; C = 0
        lda bitv,y
        bit first
        bne _ev
        ora first               ; alkuinstanssi (ei jalustaa: build.py)
        sta first
        tya
        ora ib
        tay
        lda cl
        sbc #0                  ; C = 0: cl - 1
        sta in_y,y
        lda fi_xlo,x
        sta in_x,y
        lda c_ptr
        sta in_ptr,y
        lda fi_col,x
        sta in_col,y
        lda fi_bits,x           ; jalusta alkuinstanssina (alareunassa spritellä 4): X-laajennus
        and #2
        beq +
        ldy hw
        lda bitv,y
        ldy nx
        ora in_01d,y
        sta in_01d,y
+       ldy hw
        bpl _le
_ev     lda ne                  ; tapahtuma riville lastend + 1 (X = paikka, Y = sprite)
        ora eb
        tax
        lda lastend,y
        adc #1                  ; C = 0
        sta ev_key,x
        lda #1
        sta ev_kind,x
        tya
        sta ev_hw,x
        asl a
        sta ev_hw2,x
        lda cl
        sec
        sbc #1
        sta ev_y,x
        lda c_ptr
        sta ev_ptr,x
        txa
        sta ev_ord,x
        lda sh010               ; varjot (alareunan tapahtumat: cs_shad)
        sta ev_010,x
        lda #0
        sta ev_01d,x
        ldy fi
        lda fi_bits,y
        sta ev_bits,x
        lda fi_xlo,y
        sta ev_xlo,x
        lda fi_col,y
        sta ev_col,x
        inc ne
        ldy hw
_le     lda cl                  ; Y = sprite
        clc
        adc #20
        sta lastend,y
_cn     ldx fi
        inx
        cpx #N_FI
        bcc _ct
_cend   ldx nx
        lda first
        sta in_en,x
        ldx ct_t0               ; alareunan tapahtumat (ensimmäinen indeksi, $ff: ei) paikalleen ja varjot cs_shadissa
        bmi _nos
        lda #1
        sta catf
        txa
        bne +
        inx                     ; lajittelu indeksistä >= 1
+       jmp sf_sort
_nos    jmp sf_done

ct_hw   .byte 4, 5, 6, 0, 1, 2, 3, 7

; Kissan alareunan leikkaus (cat_set): puskuri (joukko nx, alapuoli, sprite hw) <- osoittimen c_ptr lohko k riviä alas,
; rivit 0..k-1 nollia. Vain pankki 3: se näkyy koko kissan ajan (build.py: asettelun vaihto vasta kissan jälkeen).
; Nollarivit seurataan (cb_z), joten kameran liikkuessa kopioidaan vain data (ei koko 63 tavua molempiin
; pankkeihin). Avaimen bitti 6: yleinen clip (molemmat pankit) ei käytä näitä sisältöjä.
cat_clip
        lda nx
        asl a
        asl a
        asl a
        asl a
        ora #8
        ora hw
        tax
        clc
        adc #CLIP_PTR0
        sta stmp+1
        lda c_ptr               ; lähde = BANK3_SCR + 64 * osoitin (perus- ja lisälohkot ennallaan kissan aikana)
        lsr a
        ror zt
        lsr a
        ror zt
        ora #>BANK3_SCR
        sta zs+1
        lda zt
        and #$c0
        sta zs
        lda stmp+1
        sta c_ptr
        lda c_k
        ora #$40
        cmp cb_k,x
        bne _new
        lda zs
        cmp cb_src,x
        bne _new
        lda zs+1
        cmp cb_srch,x
        beq _r
_new    lda c_k
        ora #$40
        sta cb_k,x
        lda zs
        sta cb_src,x
        lda zs+1
        sta cb_srch,x
        lda cb_lo,x
        sta zd
        lda cb_hi,x
        clc
        adc #$40
        sta zd+1
        lda c_k                 ; 3k
        asl a
        adc c_k
        sta zt
        lda cb_z,x              ; nollarivit z..k-1 (0..z-1 ovat jo nollia)
        sta zy
        lda c_k
        sta cb_z,x
        sec
        sbc zy
        beq _d
        bcc _d
        tax
        lda zy
        asl a
        adc zy
        tay
        lda #0
-       sta (zd),y
        iny
        sta (zd),y
        iny
        sta (zd),y
        iny
        dex
        bne -
_d      lda zs                  ; data: lähde - 3k, Y = 3k..62
        sec
        sbc zt
        sta zs
        bcs +
        dec zs+1
+       ldy zt
        lda #21
        sec
        sbc c_k
        tax
-       lda (zs),y
        sta (zd),y
        iny
        lda (zs),y
        sta (zd),y
        iny
        lda (zs),y
        sta (zd),y
        iny
        dex
        bne -
_r      rts

; kiinteä ehdokas si: vastaranta (bittikartan takana) tai pääskynen (st_bird = pääskynen + 1, edessä, liikkuu)
st_cand
        ldx si
        lda st_line,x
        sta cl
        lda #0
        sta cl+1
        lda st_slo,x            ; lähde (leikkaus taivasvyöhykkeen alareunaan)
        sta c_src
        lda st_shi,x
        sta c_src+1
        lda #6                  ; X-laajennus, bittikartan takana
        sta c_bits
        lda st_ptr,x
        sta c_ptr
        lda st_col,x
        sta c_col
        ldy st_bird,x
        beq _shore
        dey                     ; pääskynen: edessä, MC, ei laajennusta, ei leikkausta
        lda sbd_g,y             ; poissa (ennen BIRD_RETiä tai BIRD_OUTin jälkeen)
        beq +
        rts
+
        lda #0
        sta c_bits
        sta c_src+1
        lda sbd_xh,y            ; X = (x16 >> 4) & 511
        sta zy
        lda sbd_xl,y
        .rept 4
        lsr zy
        ror a
        .endrept
        sta c_xlo
        lda zy
        and #1
        ora bd_lo
        sta c_bits
        lda sfr                 ; rivi + aalto ja siipiasento (bd_fw: lokin siivenlyönti ja liito, 32 kehyksen kierto)
        clc
        adc bd_ph,y
        and #31
        tax
        lda bd_fw,x
        pha
        and #3
        clc
        adc cl
        sec
        sbc boff
        sta cl
        pla
        lsr a
        lsr a
        clc
        adc bptr
        sta c_ptr
        jmp place
_shore  lda st_xlo,x
        sta c_xlo
        lda st_xhi,x
        ora c_bits
        sta c_bits
; ehdokas (cl, c_*) spritelle: leikkaus, vapaa sprite (edellinen päättynyt vähintään 4 riviä aiemmin),
; alkuinstanssi tai tapahtuma
place
        lda #SPR_BOT            ; alaraja: ikkuna, takana olevilla myös taivasvyöhyke
        sta c_lim
        lda c_bits
        and #4
        beq +
        lda zl
        cmp #SPR_BOT
        bcs +
        sta c_lim
+       lda cl
        cmp c_lim
        beq +
        bcc +
        rts                     ; alkaa rajan alapuolella
+       lda #0
        sta c_side
        lda cl
        cmp #SPR_TOP
        bcs _nt
        lda #SPR_TOP            ; yläreuna: k = 73 - L, alku 73, rivit k..20 ylös
        sec
        sbc cl
        sta c_k
        lda #SPR_TOP
        sta c_start
        lda #1
        sta c_side
        bne _find
_nt     sta c_start
        clc
        adc #20
        cmp c_lim
        bcc _find
        beq _find
        sbc c_lim               ; alareuna: k = L + 20 - raja
        sta c_k
        lda c_lim               ; taivasvyöhykkeen raja ja sprite päättyy ikkunassa: alku L, viimeiset k riviä
        cmp #SPR_BOT            ; nollia (DMA saa jatkua rajan alle; k muuttuu kameran mukana yhdellä, joten
        bcs _shift              ; puskuriin kirjoitetaan vain muuttuneet rivit)
        lda c_start
        adc #20                 ; C = 0
        cmp #SPR_BOT + 1
        bcs _shift
        lda #3
        sta c_side
        bne _find
_shift  lda c_start             ; ikkunan alareuna: data k riviä alas ja alku L - k (DMA päättyy rajalle)
        sec
        sbc c_k
        sta c_start
        lda #2
        sta c_side
; Vapaa sprite kierroksessa edellisen valitun jälkeen (kauimmin vapaana ollut ensin): tapahtumalla on aikaa ennen
; uutta instanssia. Alin vapaa sprite antaisi kissan rivillä 99 kaksi tapahtumaa samalle riville 3 riviä ennen
; alkua, ja 8 spriten DMA:n ja badlinen kanssa jälkimmäinen myöhästyisi (viipale puuttuisi kehyksen).
_find   lda c_bits
        and #32
        bne _flow
        ldx rrhw
        ldy #MAX_HW
_fl     lda lastend,x
        clc
        adc #4
        bcs +
        cmp c_start
        bcc _got
        beq _got
+       inx
        cpx #MAX_HW
        bcc +
        ldx #0
+       dey
        bne _fl
        beq _fdrop
_fdrop  inc drops
        rts
_flow   ldy #$ff                ; pääskyset: vain spritet 0-2 (DMA edellisen rivin lopussa: $D021-tapahtuman
        ldx #0                  ; kirjoitus rivin alussa ei myöhästy näkyvälle alueelle, ei harmaata pistettä). Vapaista
_fw     lda lastend,x           ; kauimmin vapaana ollut: tapahtuma aikaisin. Ensimmäinen vapaa antaisi kolmannelle
        clc                     ; pääskyselle ensimmäisen spriten, ja tapahtuma osuisi illan $D021-tapahtuman kohdalle
        adc #4                  ; ja myöhästyttäisi sen (rivit 99-100 väärää väriä)
        bcs _fnext
        cmp c_start
        beq +
        bcs _fnext
+       cpy #$ff
        beq _fbest
        lda lastend,x
        cmp lastend,y
        bcs _fnext
_fbest  txa
        tay
_fnext  inx
        cpx #3
        bcc _fw
        tya
        bmi _fdrop
        tax
_got    stx hw
        txa
        clc
        adc #1
        and #MAX_HW - 1
        sta rrhw
        lda c_side
        beq _noclip
        lda c_src+1
        beq _noclip
        jsr clip
_noclip ldx hw
        lda bitv,x
        and first
        bne _ev
        lda bitv,x               ; alkuinstanssi
        ora first
        sta first
        txa
        clc
        adc ib
        tay
        lda c_start
        sec
        sbc #1
        sta in_y,y
        lda c_xlo
        sta in_x,y
        lda c_ptr
        sta in_ptr,y
        lda c_col
        sta in_col,y
        ldy nx
        lda first
        sta in_en,y
        lda c_bits
        lsr a
        bcc +
        lda bitv,x
        ora in_010,y
        sta in_010,y
+       lda c_bits
        and #2
        beq +
        lda bitv,x
        ora in_01d,y
        sta in_01d,y
+       lda c_bits
        and #4
        beq _end
        lda bitv,x
        ora in_01b,y
        sta in_01b,y
        jmp _end
_ev     lda ne                  ; tapahtuma riville lastend + 1
        cmp #MAXE
        bcs _end
        clc
        adc eb
        tay
        lda lastend,x
        clc
        adc #1
        sta ev_line,y
        sta ev_key,y
        lda #1
        sta ev_kind,y
        txa
        sta ev_hw,y
        asl a
        sta ev_hw2,y
        lda c_start
        sec
        sbc #1
        sta ev_y,y
        lda c_xlo
        sta ev_xlo,y
        lda c_ptr
        sta ev_ptr,y
        lda c_col
        sta ev_col,y
        lda c_bits
        sta ev_bits,y
        tya
        sta ev_ord,y
        inc ne
_end    ldx hw
        lda c_start
        clc
        adc #20
        sta lastend,x
        rts

; Leikkauspuskuri (joukko nx, ylä- tai alapuoli, sprite hw; molemmat pankit) <- lähde c_src:
;   1 yläreuna: rivit k..20 -> 0..20-k (alku riviltä 73)
;   2 ikkunan alareuna: rivit 0..20-k -> k..20 (alku k riviä aiemmin, joten DMA päättyy rajalle: rivin 216 DMA
;     myöhästyttäisi alareunan kirjoitusta)
;   3 taivasvyöhykkeen raja: rivit 0..20-k ennallaan, k viimeistä riviä nollia. Saman lähteen puskurista
;     kirjoitetaan vain muuttuneet rivit (kameran noustessa 1-2 riviä, ei koko spriteä kehyksessä, jossa p vaihtuu).
; Ennallaan, jos lähde, puoli ja k samat (avain cb_k: k, tila 3 bitti 7).
clip
        lda nx                  ; indeksi = nx * 16 + alapuoli * 8 + hw
        asl a
        ldx c_side
        cpx #2                  ; C = 1: alapuoli (2 tai 3)
        adc #0
        asl a
        asl a
        asl a
        ora hw
        tax
        clc
        adc #CLIP_PTR0
        sta c_ptr
        lda cb_lo,x             ; pankki 2 (zd) ja pankki 3 (zd2) samalla kierroksella
        sta zd
        sta zd2
        lda cb_hi,x
        clc
cbh     = *                     ; koti_quiet: $40 (vain pankki 3)
        adc #0
        sta zd+1
        clc
cz2     = *                     ; koti_quiet: 0 (vain pankki 3)
        adc #$40
        sta zd2+1
        lda c_k
        ldy c_side
        cpy #3
        bne +
        ora #$80
+       sta zy                  ; avain
        lda c_src
        cmp cb_src,x
        bne _new
        lda c_src+1
        cmp cb_srch,x
        bne _new
        lda zy
        cmp cb_k,x
        bne +
        rts
+       and cb_k,x              ; molemmat tilaa 3: vain muuttuneet rivit
        bmi _inc
_new    lda c_src
        sta cb_src,x
        lda c_src+1
        sta cb_srch,x
        lda zy
        sta cb_k,x
        lda c_k                 ; 3k tavua
        asl a
        adc c_k
        sta zt
        lda c_side
        cmp #2
        beq _down
        lda #0                  ; tila 3: lähteen rivit 0..20-k ennallaan
        cpy #3
        beq +
        lda zt                  ; yläreuna: rivit k..20 -> 0..20-k (lähde + 3k)
+       clc
        adc c_src
        sta zs
        lda c_src+1
        adc #0
        sta zs+1
        ldy #0                  ; rivit 0..20-k, sitten k riviä nollia
        ldx c_k
        lda cpe_lo,x
        sta zvec
        lda cpe_hi,x
        sta zvec+1
        jsr _jv
        ldx c_k
        jmp zrk
_jv     jmp (zvec)
_down   lda c_src               ; alareuna: k riviä nollia, sitten rivit 0..20-k -> k..20 (lähde - 3k, Y jatkuu)
        sec
        sbc zt
        sta zs
        lda c_src+1
        sbc #0
        sta zs+1
        ldy #0
        ldx c_k
        jsr zrk
        ldx c_k
        lda cpe_lo,x
        sta zvec
        lda cpe_hi,x
        sta zvec+1
        jmp (zvec)
_inc    lda cb_k,x              ; tila 3, vanha k -> uusi k: rivit 21 - max .. 20 - min
        and #$7f
        sta zt
        lda zy
        sta cb_k,x
        lda c_src
        sta zs
        lda c_src+1
        sta zs+1
        lda c_k
        cmp zt
        bcs _zero
        ldx zt                  ; uusi k pienempi: rivit 21 - vanha .. 20 - uusi lähteestä
        jsr _rows
-       lda (zs),y
        sta (zd),y
        sta (zd2),y
        iny
        cpy zt
        bcc -
        rts
_zero   tax                     ; uusi k suurempi: rivit 21 - uusi .. 20 - vanha nolliksi
        lda zt
        sta c_k
        jsr _rows
        lda #0
-       sta (zd),y
        sta (zd2),y
        iny
        cpy zt
        bcc -
        rts
; X = suurempi k, c_k = pienempi: Y = 3 (21 - X), zt = 3 (21 - c_k)
_rows   lda #21
        sec
        sbc c_k
        sta zt
        asl a
        adc zt
        sta zt
        stx c_k
        lda #21
        sec
        sbc c_k
        sta c_k
        asl a
        adc c_k
        tay
        rts
; auki kirjoitetut kopiot riveittäin (3 tavua, molemmat pankit): sisään lohkosta i -> rivit i..20 (Y jatkuu)
cpblk
        .rept 21
        .rept 3
        lda (zs),y
        sta (zd),y
        sta (zd2),y
        iny
        .endrept
        .endrept
        rts
; X riviä nollia molempiin pankkeihin (Y jatkuu; X = 0: ei mitään)
zrk     txa
        beq _r
        lda #0
-       sta (zd),y
        sta (zd2),y
        iny
        sta (zd),y
        sta (zd2),y
        iny
        sta (zd),y
        sta (zd2),y
        iny
        dex
        bne -
_r      rts
cpe_lo  .byte <(cpblk + 21 * range(22))
cpe_hi  .byte >(cpblk + 21 * range(22))

bd_fw   .byte BD_FW                ; lokin aalto + 1 (bitit 0-1) ja siipiasento (bitit 2-4) kehyksittäin (build.py BIRD_SEQ)
bitv    .byte $01, $02, $04, $08, $10, $20, $40, $80
nbit    .byte $fe, $fd, $fb, $f7, $ef, $df, $bf, $7f
cb_lo   .byte <(BANK2_SCR + SPR_OFS + 64 * range(32))   ; pankki 3: + $4000
cb_hi   .byte >(BANK2_SCR + SPR_OFS + 64 * range(32))

        .include "../../lib/crunch.asm"


        .if HAVE_MUSIC && !INTEGRATED
        .include "../../music/music.asm"
        .endif


        .include "tables.inc"
        .dsection koti1tail     ; lopussa, joten muun koodin ja taulujen osoitteet eivät riipu sen koosta
code_end
        .include "records.inc"
        .cerror * > REC_LIMIT, "tietueet yli rajan: ", format("$%04x", *)
        .cerror INTEGRATED && koti5_end > $5800, "KOTI5 yli $5800:n (loppu kopioi ruudun $5800-$5be7 kodin aikana koti_quietin jälkeen): ", format("$%04x", koti5_end)
        .cerror INTEGRATED && rec_end > $6000, "KOTI4 yli $6000:n (runko esilataa LOPPU2:n $6000-$7fff koti_go:n jälkeen): ", format("$%04x", rec_end)

; ajonaikaiset taulukot (ei ladata; koti_init nollaa)
        .virtual BSS_BASE
bss_start
seq     .fill 32
CR_TOPCLR .byte ?
        .align 256
d21line .fill 256               ; $D021 riveittäin rivinumerolla
        .if !INTEGRATED
COLSTAGE .fill 1000             ; seuraavan asettelun värimuisti (demossa $9000, vapautuu koti_quietissa)
        .endif
; tapahtumat: 2 joukkoa x MAXE, ev_ord = joukon tapahtumat käsittelyjärjestyksessä
ev_line .fill 2 * MAXE
ev_key  .fill 2 * MAXE          ; käsittelyrivi (= rivi, jolla saman spriten edellinen on päättynyt + 1)
ev_kind .fill 2 * MAXE          ; 1 sprite
ev_ord  .fill 2 * MAXE
ev_hw   .fill 2 * MAXE
ev_hw2  .fill 2 * MAXE
ev_y    .fill 2 * MAXE
ev_xlo  .fill 2 * MAXE
ev_ptr  .fill 2 * MAXE
ev_col  .fill 2 * MAXE
ev_bits .fill 2 * MAXE
ev_010  .fill 2 * MAXE
ev_01d  .fill 2 * MAXE
ev_01b  .fill 2 * MAXE
ev_01c  .fill 2 * MAXE
ne_set  .fill 2
ne_cur  .byte ?
in_y    .fill 16                ; alkuinstanssit: 2 joukkoa x 8 spriteä
in_x    .fill 16
in_ptr  .fill 16
in_col  .fill 16
in_010  .fill 2
in_01d  .fill 2
in_01b  .fill 2
in_01c  .fill 2                 ; MC-bitit
in_d025 .fill 2                 ; $D025, $D026: kissan kehyksissä CAT_D025, CAT_D026
in_d026 .fill 2
bot_r   .fill 2                 ; kt_edge: alareunan kirjoitus näin monta sykliä aiemmin
sd026   .byte ?
an_st   .fill 3                 ; kissan tila: pää, 0, häntä (fi_an)
sd025   .byte ?
rrhw    .byte ?                 ; _find: kierroksen seuraava sprite
boff    .byte ?                 ; pääskysten alku (0 tai BIRD_LOW riviä aiemmin) ja siipiasennon osoitin
bptr    .byte ?
sh01c   .byte ?
in_en   .fill 2
lastend .fill 8
cb_src  .fill 32                ; leikkauspuskurien sisältö: lähde ja k
cb_srch .fill 32
cb_k    .fill 32
cb_z    .fill 32                ; cat_clip: puskurin alun nollarivit (pankki 3)
sfr     .byte ?                 ; spr_frame: laskennan alun frame ja pääskysten X ja tila
sbd_xl  .fill N_BIRD
sbd_xh  .fill N_BIRD
sbd_g   .fill N_BIRD
bd_xl   .fill N_BIRD            ; pääskysten X (1/16 hires-px, 16 bittiä)
bd_gone .fill N_BIRD            ; pääskynen lentänyt pois
        .if !INTEGRATED
dusk_byte .fill 256              ; dusk_step: ruututavu tummemmaksi (spr_init täyttää; demossa taulu)
        .endif
far_cur .fill WIN_H             ; kaukaisen kerroksen $D021 riveittäin (päivä, auringonlaskussa sunset_step)
ss_s    .byte ?                 ; auringonlaskun askel 0..16
mdiv    .byte ?                 ; liikekäyrän arvo vaihtuu MDIV kehyksen välein
ss_cnt  .byte ?
cpz     .byte ?                 ; tekijöiden tauko pidetty
il_k    .byte ?                 ; ilta_step: askel (ruuturivit, sitten maskirivit)
il_last .byte ?                 ; ilta_step: far_cur päivitetty tätä riviä edeltäviin asti
il_f    .byte ?                 ; ilta_step: maskiväri %10 (bitti 7)
il_j    .byte ?
il_je   .byte ?                 ; ilta_step: puolikkaan loppu (10 tai 20)
il_h    .byte ?                 ; ilta_step: toinen puolikas seuraavassa kehyksessä
bd_lo   .byte ?                 ; pääskysten paluu (BIRD_RET): 32 = vain spritet 0-2 (_find), 2 = X-laajennus
dk_n    .byte ?                 ; dusk_step: askeleita tehty
fc_up   .byte ?                 ; far_cur muuttui riveillä 0..SKY_LAST (lf_place kopioi taivasrivit)
fc_lo   .byte ?                 ; far_cur muuttui riveillä SKY_LAST.. (_d21ev käy rivit läpi)
lf_ppx  .byte ?                 ; lf_place: ppx, jolla taivasrivit on kopioitu
lf_mzt  .byte ?                 ; lf_place: silloinen taivassilmukan rivimäärä
qreq    .byte ?                 ; koti_quiet: pankki 3 vain (q_patch spr_bodyssa)
dk_lo   .byte ?                 ; dusk_step: ruututavun alanibble
cs_x    .byte ?                 ; cr_seq: edellinen plyt ja pankki | $80 (0: ei vielä)
cs_b    .byte ?
tx_off  .byte ?                 ; tekstit pois (txt_spr): spr_body heti alareunan IRQ:ssa
bgpre   .byte ?                 ; 1: koti_buildin paluusta koti_quietiin prewrite IRQ:ssa (pre_irq)
prw_n   .byte ?                 ; pre_irq: kirjoitettuja rivejä
fs_lo   .byte ?                 ; fc_sync: muuttuneet rivit, tila
fs_hi   .byte ?
fs_m    .byte ?
il_hi   .byte ?                 ; ilta_step: maalattu riviä edeltäviin asti (_d21ev, fc_lo = 2)
vr_st   .byte ?                 ; vr_gate: järven rivien värimuisti kirjoitettu
vr_c    .byte ?                 ; vr_gate: seuraava rivi
vr_on   .byte ?                 ; vk_step: vr_part (siirto tai nollaus kesken)
vr_zon  .byte ?                 ; vr_part: edellisen listan nollaus kesken
vr_pv   .byte ?                 ; vr_list: lista kirjoitettu (vr_pp, vr_d voimassa)
vr_pp   .byte ?                 ; vr_list: ppx listan alussa
vr_t    .byte ?
vr_d    .fill 4                 ; siirto: d0, d1 (ala), d0, d1 (ylä)
vr_pl   .byte ?                 ; ppx & 7 (vr_d:n perässä: vr_list kopioi viisi tavua)
vr_zd   .fill 4                 ; nollattavan listan siirto ja ppx & 7
vr_zpl  .byte ?
vr_zy   .byte ?                 ; nollauksen kohta ja loppu
vr_ze   .byte ?
d2_n    .byte ?                 ; _d21ev: n (enintään D21EV_MAX + 1), jolla d2_* on laskettu
d2_cnt  .byte ?
D2_MAX  = 16
d2_col  .fill D2_MAX            ; _d21ev: tapahtumien väri ja rivi (T_LINE + r - 3)
d2_line .fill D2_MAX
dk_j    .byte ?                 ; dusk_step: merkkirivi askeleen sisällä (IL_SCR_N: loput $D021-rivit)
dk_q    .byte ?                 ; dusk_step: rivin kahdeksan tavun pala (0-4)
dk_e    .byte ?                 ; dusk_step: $D021-rivien loppu
dk_w    .byte ?                 ; dusk_step: askeleen kehykset
il_b    .byte ?
bd_xh   .fill N_BIRD
bss_end
        .endv
        .cerror (>seq) != (>(seq + 31)), "seq ylittää sivun"
        .cerror !INTEGRATED && bss_end > $1700, "BSS musiikin purkupuskurin päällä"
        .cerror INTEGRATED && bss_end > $4800, "BSS yli $4800:n (greetsien esilataus $4800-)"
        .if INTEGRATED
COLSTAGE = $9000                ; pankin 2 merkkiROM-kohta: vain asettelujen rakennukseen ja vaihtoihin
        .endif
BSS_PAGES = (bss_end - bss_start) / 256
BSS_REST  = (bss_end - bss_start) % 256

        .if HAVE_MUSIC && !INTEGRATED
        * = MUSIC_LOAD
        .binary "music.bin"
        .endif
