; Greetsit (partti 4): ajo Lohjanharjun tiellä auringonlaskussa, kerrokset omilla nopeuksillaan ja
; sinusskrolleri runkojen takana.
; Data ja generoitu koodi (merkistöt, kartat, kerneli, kopiokoodi): build.py -> build/greetsit/, kaikki levyllä
; (C64 ei generoi koodia: init on muutama kehys myös edellisen kohtauksen pidon aikana).
;
; Kehys (rasteririvit):
;   44/45   irq_top: kaksois-IRQ vakauttaa ajoituksen, sitten generoitu kerneli (kernel.asm) riveille 45-198.
;           Spritejen DMA pysäyttää CPU:n joka rivin syklistä 55 syklin 11:een, joten jokainen rivi alkaa
;           samasta syklistä: $D021 joka rivillä (taivas, mäkien takana, järvi), kaistojen saumat ($D016,
;           $D018, $D022, $D023 yksivärisellä saumarivillä, merkistö badlinea edeltävällä paikalla),
;           spritepinojen vaihto ($D018:n ruutubitti vaihtaa kaikkien 8 spriten osoittimet kerralla),
;           seuraavan pinon Y ja osoittimet piilossa olevaan ruutuun.
;   217     irq_s1: pientareen sauma (rivi 218)
;   221     irq_sh: tien spritet: pyöräilijä (0, rivit 226-246), lenkkeilijä ja koira (1), varjot (2-6); alakulmat
;           ovat tien merkeissä (kernel päivittää ne tien mukana, build.py corner_cells)
;   225     irq_s2: tien sauma (rivi 226): merkistö R, tien värit
;   230     irq_bot: FRAME_HOOK, sitten seuraavan kehyksen logiikka sisäkkäin (cli): kaistojen karkeat siirrot,
;           skrolleri, spritet (rekisterit, S0:n osoittimet ja $D017 vasta, kun Y-laajennetut varjot ovat
;           loppuneet rivillä 270, spr_commit), varjot. irq_top keskeyttää sen.
;   251     irq_rest: varjot näytetty (tien rivit 227-250), rungot takaisin (MC, X-laajennus, omat värit)

        .include "greetsit.inc"
        .if INTEGRATED
        .include "timing.inc"
        .else
        .include "music/music.inc"
        .endif

        .weak
INTEGRATED = 0                  ; 1 = demon osa (greetsit_init, greetsit_go, FRAME_HOOK)
DFRAME  = $d0
R_IDLE  = $0422
FRAME_HOOK = $0408
TIM_SCENE_GREETSIT_START = 3840 ; src/gen/timing.inc, oletus
TIM_SONG_START = 2400
DEBUG   = 0
        .endweak

ZP0     = $30                   ; nollasivu $30-$8f: kodin pito käyttää $02-$2f ja $90-$a1 greetsit_go:hon asti
CODE_BASE = $8000                       ; koko osa $4800-$bfff: kodin aikana vapaa (koti_build, koti_quiet)
RUN_BASE = $1a00                        ; ajonaikaiset muuttujat (nollataan initissä, ei levyllä)
CODE3 = $1b00                           ; GREETSIT3: kulkevan aallon koodi ja taulut
WV_BASE = $2200                         ; aallon ajonaikaiset taulut (wave_init)
LINE_TOP = 44
LINE_S1 = 217
LINE_S2 = 225
LINE_SH = 221
LINE_BOT = 230                  ; irq_bot heti tien sauman jälkeen (irq_s2 asettaa sen rivillä 228), jotta logiikalla
                                ; on aikaa (muuten raskas kaistan kopio myöhästyttäisi tekstin vierityksen kernelin
                                ; yli ja teksti seisoisi kehyksen)
LINE_V1 = 242                   ; alareunan vinjetin portaat (kirjoitus rivin alussa: rivit 243 ja 247 tummempia)
LINE_V2 = 246
LINE_REST = 300                 ; irq_rest (pystypaluussa, 9. bitti): rungot takaisin MC-tilaan, reuna yläreunan
                                ; väriin (taivaan ensimmäinen rivi), ei näy kuvassa
SH_END = 270                    ; Y-laajennetut varjospritet päättyvät rivillä 268 (tyhjät rivit 12-20 reunuksessa):
                                ; spritejen rekisterit, osoittimet ja $D017 vasta tämän jälkeen (spr_commit)
X_HIDE  = 400                   ; vapaan spriten X (oikean reunan takana)
SH0     = 2                     ; ensimmäinen varjosprite (0 pyöräilijä, 1 lenkkeilijä: molemmat varjojen edessä)

        .virtual ZP0
z_pad   .byte ?                 ; bit z_pad: 3 syklin täyte kernelissä
z_dx_taivas .byte ?             ; kaistojen $D016 seuraavalle kehykselle
z_dx_maet .byte ?
z_dx_teksti .byte ?
z_dx_kaupunki .byte ?
z_dx_piennar .byte ?
z_d18f1 .byte ?                 ; spritepinojen vaihdot (ruutubitti + kaistan merkistö)
z_d18f2 .byte ?
z_d18f3 .byte ?
z_d18f4 .byte ?
z_d18f5 .byte ?
z_d18f6 .byte ?
z_d18f7 .byte ?
z_d18s_teksti .byte ?           ; saumojen $D018 (badlinea edeltävä paikka)
z_d18s_kaupunki .byte ?
z_gp    .word ?                 ; skrollerin uuden sarakkeen osoitin gidtab + tq + 40
ra      .byte ?
rx      .byte ?
ry      .byte ?
busy    .byte ?                 ; frame_logic kesken
drops   .byte ?                 ; kehykset, joina logiikka ei ehtinyt (pitäisi olla 0)
spr_over .byte ?
drop_f  .word ?                ; rungot, joille ei ollut vapaata spriteä (pitäisi olla 0)
pos_taivas .word ?              ; kaistojen hienopaikka 8.8 (0..2047 = 8 px)
pos_maet .word ?
pos_kaupunki .word ?
pos_piennar .word ?
q_taivas .byte ?                ; karkea paikka (kartan sarake)
q_maet  .byte ?
q_kaupunki .byte ?
q_piennar .byte ?
tpos    .byte ?                 ; tekstin hienopaikka hires 0..7
tq      .word ?                 ; tekstin karkea paikka (sarake), 0..NTC-1
tb      .byte ?                 ; ruudun sarake 0 näyttää puskurin sarakkeen tb (0..TB_N-1)
z_d010  .byte ?
zs      .word ?
zt      .byte ?
zi      .byte ?
z_nb    .byte ?                 ; seuraava uusi sarake (puskurin sarake, $ff = piirretty) ja sen tasoindeksi
z_ng    .byte ?
sq      .byte ?                 ; copy_*: q talteen
noregs  .byte ?
z_vnear .byte ?                 ; lähimpien runkojen nopeus px/kehys (2)
z_vfar  .byte ?                 ; kaukaisten: 1 ja 2 vuorotellen = 1,5 px/kehys (tekstiä nopeampi)                 ; 1 = initissä: sprites ei kirjoita VIC-rekistereihin
z_ph    .byte ?                 ; aallon vaihe (näkyvä kehys), pienenee 1 joka kehys
z_n     .byte ?                 ; col_draw: uusi siirto
z_o     .byte ?
z_t     .byte ?
z_c     .byte ?
z_c2    .byte ?
z_k     .byte ?
z_gid   .byte ?
z_qh    .byte ?                 ; näkyvän puskurin päivitysjono wv_q: pää ja häntä (0..31)
z_qt    .byte ?
z_pq    .byte ?                 ; vis_put: viimeisin käsitelty vaihe
z_vn    .byte ?
zptr    .word ?
jog_t   .word ?                 ; lenkkeilijän rata, askelvaihe, kehys, $D010:n bitti ja osoitin (kuten pyöräilijä;
jog_phl .byte ?                 ; bss on täynnä)
jog_fr  .byte ?
jog_d010 .byte ?
jog_p   .byte ?
zp_end
        .cerror zp_end > $90, "nollasivu ylittää $8f"
        .endv

; ---------------------------------------------------------------- erillisohjelma
        .if !INTEGRATED
        * = $0801
        .word (+), 2026
        .null $9e, format("%d", start)
+       .word 0
        * = $0810
music_src
        .binary "music/music.bin"
music_src_end
        .endif

        .if !INTEGRATED
        * = $3e00                       ; erillisohjelman käynnistys ajonaikaisen alueen lopussa (ei demossa)
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
        ldx #0                  ; musiikki $0810 -> $0800 (kohde alempana: eteenpäin)
_cp     lda music_src,x
        sta MUSIC_LOAD,x
        inx
        bne _cp
        inc _cp + 2
        inc _cp + 5
        lda _cp + 2
        cmp #>(music_src_end + 255)
        bne _cp
        jsr greetsit_init
        ldx #<(TIM_SONG_START + TIM_SCENE_GREETSIT_START)
        ldy #>(TIM_SONG_START + TIM_SCENE_GREETSIT_START)
        jsr music_seek
        lda #<TIM_SCENE_GREETSIT_START
        sta DFRAME
        lda #>TIM_SCENE_GREETSIT_START
        sta DFRAME+1
        jsr greetsit_go
main    jmp main
nmi     rti
frame_hook
        jsr MUSIC_PLAY
        inc DFRAME
        bne +
        inc DFRAME+1
+       rts
        .include "../../music/music.asm"
        .cerror * > $4000, "erillisohjelman käynnistys ylittää $4000"
        .endif

        * = CODE_BASE

; ---------------------------------------------------------------- sisääntulot
; greetsit_init: ruudut, kaistat, tie, spritet ja skrollerin näkyvä puskuri valmiiksi (noin 3 kehystä kodin pidon
; aikana). Init ei koske näyttöön ($d011, $d016, $d018, $dd00, värimuistin rivit 0-21, näkyvät spritet): runko
; pitää edellisen kohtauksen kuvan pankissa 3 näkyvissä, kunnes greetsit_go (spritet ovat pois, $d015 = 0, joten
; niiden rekisterit eivät näy). Merkistöt X0 ja R ovat levyltä ladattuina nollia (GREETSIT6 ja 7), joten niitä ei
; tyhjennetä. Skrollerin seuraava sarake piirtyy greetsit_go:n jälkeen taustatyönä (dycp_run) kuten aina karkean
; askeleen jälkeen.
greetsit_init
        ldx #ZP0
        lda #0
-       sta $00,x               ; nollasivun muuttujat
        inx
        cpx #$90
        bne -
        ldx #bss_end - bss_start
-       sta bss_start - 1,x
        dex
        bne -
        lda #1
        sta noregs
        sta z_vfar
        lda #2
        sta z_vnear
        lda #<CYC_T0
        sta cyc_t
        lda #>CYC_T0
        sta cyc_t+1
        lda #<JOG_T0
        sta jog_t
        lda #>JOG_T0
        sta jog_t+1
        lda #SH_EMPTY           ; ensimmäinen kehys (frame_step ei aja joggeria)
        sta jog_p
        jsr static_rows         ; tekstin ja tien ruuturivit, tien värimuistin rivit 22-24
        lda #$ff
        sta sx_free
        lda near_xlo            ; ensimmäisten runkojen etäisyys
        sta nd
        lda near_xhi
        sta nd+1
        lda far_xlo
        sta nd+2
        lda far_xhi
        sta nd+3
        lda #D18F1
        sta z_d18f1
        lda #D18F2
        sta z_d18f2
        lda #D18F3
        sta z_d18f3
        lda #D18F4
        sta z_d18f4
        lda #D18F5
        sta z_d18f5
        lda #D18F6
        sta z_d18f6
        lda #CSB_X0 | SEAM_TEKSTI_SCR << 4
        sta z_d18s_teksti
        lda #D18F7
        sta z_d18f7
        lda #D18S_KAUPUNKI
        sta z_d18s_kaupunki
        ; kaistat alkuun (q = 0): ruutu nyt, solukohtaiset värit color_go:ssa
        lda #<P0_taivas
        sta pos_taivas
        lda #>P0_taivas
        sta pos_taivas+1
        lda #<P0_maet
        sta pos_maet
        lda #>P0_maet
        sta pos_maet+1
        lda #<P0_kaupunki
        sta pos_kaupunki
        lda #>P0_kaupunki
        sta pos_kaupunki+1
        lda #<P0_piennar
        sta pos_piennar
        lda #>P0_piennar
        sta pos_piennar+1
        ldx #0
        jsr copys_taivas
        ldx #0
        jsr copys_maet
        ldx #0
        jsr copys_kaupunki
        ldx #0
        jsr copys_piennar
        ; teksti: ruudun sarakkeet 0-39 = puskurin sarakkeet 0-39 (static_rows), seuraava sarake 40 taustatyönä
        jsr wave_init
        ldy #39
-       lda gidtab,y
        sta z_ng
        sty z_c2
        jsr draw_new
        ldy z_c2
        dey
        bpl -
        jsr next_col
        lda #$17                ; tpos 0
        sta z_dx_teksti
        jsr fade_init
        jmp frame_step          ; ensimmäinen kehys (ilman taustatyötä)

; greetsit_go: oma IRQ-ketju päälle (rivi 44), näyttö päälle seuraavassa kehyksessä. Palaa heti.
; greetsit_go: odottaa edellisen kohtauksen ikkunan lopun (ensimmäinen hetki rivillä GO_LINE tai sen jälkeen),
; kopioi värimuistin rivit 0-21 (color_go, noin 4 900 sykliä; edellisen kohtauksen IRQ:t saavat keskeyttää), ottaa
; VIC:n ja IRQ:n ennen riviä LINE_TOP ja palaa. Edellinen kohtaus näyttää siis vielä kutsukehyksen (ja enintään
; yhden lisää). Jos kopio myöhästyy (rivi LINE_TOP - 4 ohi), kehys pimennetään ja greetsit alkaa seuraavasta
; (irq_bot asettaa $d011:n). Ei yhtä riviä vaan ikkunan alku: kodin pitomoottorin IRQ varaa rivit 214-236, joten
; pääsäie näkee ensimmäisenä rivin 237 (kodin kuva loppuu riville 215). Kutsu riveillä GO_LINE..GO_LATE alkaa heti,
; myöhempi odottaa seuraavan kehyksen ikkunaa.
GO_LINE = 216
GO_LATE = 254                   ; mitattu pidon aikana: alku rivillä 237 -> luovutus 1 507 sykliä ennen riviä 44;
                                ; kellon (rivi 250) jälkeen heti: ensimmäinen kuva ei riipu initin kestosta
greetsit_go
        .if INTEGRATED
        lda $d011
        bmi _w1
        lda $d012
        cmp #GO_LINE
        bcc _w2
        cmp #GO_LATE + 1
        bcc _now
_w1     lda $d011               ; ikkunaa edeltävälle riville (0..GO_LINE-1)
        bmi _w1
        lda $d012
        cmp #GO_LINE
        bcs _w1
_w2     lda $d011               ; ensimmäinen hetki rivillä GO_LINE..311
        bmi _now
        lda $d012
        cmp #GO_LINE
        bcc _w2
_now
        .endif
        jsr color_go            ; erillisohjelmassa ei edellistä kuvaa, demossa ikkuna on jo piirretty
        sei
        lda #<irq_top
        sta $fffe
        lda #>irq_top
        sta $ffff
        .if !INTEGRATED
-       bit $d011               ; erillisohjelma: kello alkaa ruudun alusta
        bpl -
-       bit $d011
        bmi -
clock0
        .endif
        lda #2                  ; VIC-pankki 1 ($4000-$7fff); $dd00:aan vain 0-3
        sta $dd00
        ; spritet (init ei koske VIC-rekistereihin)
        lda #$ff
        sta $d01c               ; MC
        lda #D01D_TOP           ; X-laajennus (latvuspinot laajentamattomia, kerneli kytkee rungoille)
        sta $d01d
        lda #0
        sta $d017
        sta $d01b               ; rungot kaiken edessä
        lda #0
        sta noregs
        jsr spr_regs
        .for i := 0, i < 8, i += 1
        lda tcol + i
        sta $d027 + i
        .next
        lda #0                  ; reuna musta (kuvan kehys)
        sta $d020
        lda #LINE_TOP
        sta $d012
        lda #$1b                ; YSCROLL 3, 25 riviä, näyttö päälle (rivin 8. bitti 0)
        ldx $d011               ; aikaraja: rivit 256-311 tai < LINE_TOP - 4 ovat ajoissa
        bmi +
        ldx $d012
        cpx #LINE_TOP - 4
        bcc +
        cpx #GO_LINE
        bcs +
        lda #$0b                ; myöhässä: tämä kehys pimeänä
+       sta $d011
        lda #$ff
        sta $d015
        sta $d019
        lda #1
        sta $d01a
        cli
        rts

; ---------------------------------------------------------------- IRQ: kerneli
        .align 256
irq_top
        sta ra
        stx rx
        sty ry
        lda #<irq_top2
        sta $fffe
        lda #>irq_top2
        sta $ffff
        inc $d012
        asl $d019
        tsx
        cli
        .fill 16, $ea
        sei
irq_top2
        txs
        ldx #8
-       dex
        bne -
        bit $00
        lda $d012
        cmp $d012
        beq irq_stable
irq_stable
        asl $d019               ; vakaa tästä (kernelin alku: build.py --start)
        .include "kernel.asm"
        lda #<irq_s1
        sta $fffe
        lda #>irq_s1
        sta $ffff
        lda #LINE_S1
        sta $d012
        lda ra
        ldx rx
        ldy ry
        rti
        .cerror irq_top2 >> 8 != irq_stable >> 8, "irq_top2:n tasaus ylittää sivun"

; irq_s1: pientareen sauma. Spritet ovat vielä päällä: nopit pysähtyvät rivin 217 syklissä 55 ja jatkuvat
; rivin 218 syklistä 11, joten kirjoitukset osuvat yksiväriselle saumariville 218.
irq_s1  sta ra
        .fill 20, $ea
        lda z_dx_piennar
        sta $d016
        lda #PIENNAR_D022
fa_pn22 = * - 1
        sta $d022
        lda #PIENNAR_D023
fa_pn23 = * - 1
        sta $d023
        lda #226                ; varjot riveille 227-250 (Y-laajennus, spritet 2-6, pinon 7 instanssi on jo alkanut)
        .for i := 0, i < N_NEAR, i += 1
        sta $d001 + 2 * (SH0 + i)
        .next
        .for i := 0, i < N_NEAR, i += 1
        lda sh_p + i            ; S0:n osoittimet ovat vapaat rivin 198 jälkeen
        sta S0 + $3f8 + SH0 + i
        .next
        lda #<irq_sh
        sta $fffe
        lda #>irq_sh
        sta $ffff
        lda #LINE_SH
        sta $d012
        asl $d019
        lda ra
        rti

; irq_sh (rivi 221, ei spritejä näkyvissä, pinon 7 instanssi loppui 219): tien spritet. Ensin pyöräilijä (sprite 0,
; Y = CYC_Y: näkyy riviltä CYC_Y + 1), lenkkeilijä (1, JOG_Y) ja kaikkien tien spritejen tilat (varjot alkavat
; vasta 227), sitten varjojen X ja värit (2-6). Prioriteetti: pyöräilijä ja lenkkeilijä varjojen edessä. Sprite 7
; ei näy tiellä (Y jäi pinon 7 riville). Alakulmat ovat tien merkeissä (värimuistin musta, kernel).
irq_sh  sta ra
        lda #CYC_Y
        sta $d001
        lda #JOG_Y
        sta $d003
        lda #0                  ; kaikki hires: pyöräilijä, lenkkeilijä ja varjot
        sta $d01c
        lda #((1 << N_NEAR) - 1) << SH0 ; X- ja Y-laajennus vain varjoille (12 data-riviä = tien 24 riviä)
        sta $d01d
        sta $d017
        lda cyc_t
        sta $d000
        lda jog_t
        sta $d002
        lda jog_d010
        asl
        ora cyc_d010
        ora sh_d010
        sta $d010
        lda cyc_p
        sta S0 + $3f8
        lda jog_p
        sta S0 + $3f9
        lda #CYC_COL
        sta $d027
        sta $d028
        .for i := 0, i < N_NEAR, i += 1
        lda sh_x + i
        sta $d000 + 2 * (SH0 + i)
        .next
        lda #SH_COL
fa_sh = * - 1
        .for i := 0, i < N_NEAR, i += 1
        sta $d027 + SH0 + i
        .next
        lda #<irq_s2
        sta $fffe
        lda #>irq_s2
        sta $ffff
        lda #LINE_S2
        sta $d012
        asl $d019
        lda ra
        rti

; irq_s2: tien sauma rivillä 226 (yksivärinen). $D018 ja $D021 rivin oikeassa reunassa (sykli 56-63) tai
; badlinen 227 vasemmassa (ennen sykliä 15).
irq_s2  sta ra
        stx rx
        lda #LINE_S2 + 1
-       cmp $d012
        bne -
        lda #$10                ; tie vierii datassa: $D016 kiinteä
        sta $d016
        lda #TIE_D022
fa_t22 = * - 1
        sta $d022
        lda #TIE_D023
fa_t23 = * - 1
        sta $d023
        ldx #4                  ; $D018 ja $D021 rivin 226 syklistä 56-63 (kyselyn heitto 0-6): $D021 viimeistään
                                ; badlinen 227 syklissä 9 (5:llä se menisi heitosta riippuen rivin 228 alkuun)
-       dex
        bne -
        lda #ROAD_D018
        ldx #TIE_BG
fa_tbg = * - 1
        sta $d018
        stx $d021
        lda #<irq_bot
        sta $fffe
        lda #>irq_bot
        sta $ffff
        lda #LINE_BOT
        sta $d012
        asl $d019
        lda ra
        ldx rx
        rti

; irq_bot (rivi LINE_BOT, varjot vielä näkyvissä): FRAME_HOOK ja seuraavan kehyksen logiikka sisäkkäin. Logiikka ei
; saa koskea spritejen rekistereihin eikä S0:n osoittimiin ennen riviä LINE_REST (spr_commit odottaa).
irq_bot pha
        txa
        pha
        tya
        pha
        lda #<irq_v1            ; seuraavat: alareunan vinjetti (rivit 243 ja 247), sitten irq_rest
        sta $fffe
        lda #>irq_v1
        sta $ffff
        lda #LINE_V1
        sta $d012
        asl $d019
        cli                     ; vinjetin IRQ:t eivät odota musiikkia (pinon kautta, eivät koske muuttujiin)
        .if INTEGRATED
        jsr FRAME_HOOK
        .else
        jsr frame_hook
        .endif
        lda busy
        beq +
        inc drops
        lda DFRAME              ; viimeisin pudotus (mittaus)
        sta drop_f
        lda DFRAME+1
        sta drop_f+1
        jmp _out
+       inc busy
        cli
        jsr frame_logic
        dec busy
_out    pla
        tay
        pla
        tax
        pla
        rti

; irq_v1 ja irq_v2: alareunan vinjetti: tien värit tummuvat kahdessa
; portaassa kohti mustaa (lumaketju 15 -> 12 -> 11 -> 0); irq_s2 palauttaa tien värit seuraavassa kehyksessä
irq_v1  pha
        lda #TIE_V1_D022
fa_v122 = * - 1
        sta $d022
        lda #TIE_V1_D023
fa_v123 = * - 1
        sta $d023
        lda #LINE_V2
        sta $d012
        lda #<irq_v2
        sta $fffe
        lda #>irq_v2
        sta $ffff
        asl $d019
        pla
        rti
irq_v2  pha
        lda #TIE_V2_D022
fa_v222 = * - 1
        sta $d022
        lda #TIE_V2_D023
fa_v223 = * - 1
        sta $d023
        lda #TIE_V2_BG
fa_v2bg = * - 1
        sta $d021
        lda #<LINE_REST
        sta $d012
        lda #$1b | ((LINE_REST >> 1) & $80)    ; rasterin 9. bitti
fa_d11a = * - 1
        sta $d011
        lda #<irq_rest
        sta $fffe
        lda #>irq_rest
        sta $ffff
        asl $d019
        pla
        rti

; irq_rest (rivi LINE_REST, varjot näytetty): rungot takaisin MC-tilaan, X-laajennus, IRQ kerneliin
irq_rest
        sta ra
        lda #$1b                ; näyttö päälle (greetsit_go voi pimentää myöhästyneen ensimmäisen kehyksen), 9. bitti 0
fa_d11b = * - 1
        sta $d011
        lda #$ff                ; rungot takaisin varjoista: MC ja omat värit
        sta $d01c
        .for i := 0, i < 8, i += 1
        lda tcol + i
        sta $d027 + i
        .next
        lda #D01D_TOP           ; latvuspinot laajentamattomia (kerneli palauttaa laajennuksen)
        sta $d01d
        lda #<irq_top
        sta $fffe
        lda #>irq_top
        sta $ffff
        lda #LINE_TOP
        sta $d012
        asl $d019
        lda ra
        rti

; ---------------------------------------------------------------- kehyksen logiikka (seuraava kehys)
frame_logic
        jsr frame_step
        jsr fade_run            ; häivytyksen taso ja sen työ
        jsr jogger              ; häivytyksen jälkeen: sen työt ajoitetaan rivin 40 mukaan (fd_time)
        jmp dycp_run            ; skrollerin taustatyö määräaikaan asti
frame_step
        jsr bands_step          ; kaistojen rivit ovat näytetty (rivit 51-226): kopio heti
        jsr text_step
        jsr sprites             ; spr_commit odottaa riviä LINE_REST
        jsr shadows
        jmp cyclist

; ---------------------------------------------------------------- skrolleri
; Teksti liikkuu TXT_V (3) hires px/kehys (rungot 2 ja 1,5 px, joten kirjaimet ohittavat ne).
; Puskuri X0 kiertää: ruudun sarake c näyttää puskurin sarakkeen (tb + c) mod TB_N,
; ja karkea askel (3 kehystä 8:sta) vain kiertää tekstikaistan ruuturivit (text_rows) ja antaa seuraavan uuden
; sarakkeen (tq + 40, ruudun sarake 39 on 38 sarakkeen tilassa piilossa) taustatyölle (dycp_run). Aalto on kiinni
; puskurin sarakkeissa, joten askel ei siirrä kirjaimia pystyyn.
text_step
        jsr wave_step
        lda tpos
        clc
        adc #TXT_V
        cmp #8
        bcs _crs
        sta tpos
        eor #7                  ; hienovieritys joka kehys
        ora #$10
        sta z_dx_teksti
        rts
_crs    sbc #8                  ; C = 1
        sta tpos
        eor #7
        ora #$10
        sta z_dx_teksti
        lda z_nb                ; edellinen uusi sarake kesken (raskas kehys): piirretään nyt, ennen kuin se näkyy
        bmi +
        jsr new_col
+       inc tq                  ; uusi karkea paikka näkyviin
        bne +
        inc tq+1
+       lda tq
        cmp #<NTC
        lda tq+1
        sbc #>NTC
        bcc +
        lda #0
        sta tq
        sta tq+1
+       ldx tb
        inx
        cpx #TB_N
        bcc +
        ldx #0
+       stx tb
        jsr text_rows           ; X = tb: ruuturivit (kaista on näytetty, seuraava kerneli näyttää uuden)
next_col                        ; seuraava uusi sarake: puskuriin (tb + 40) mod TB_N teksti tq + 40
        lda tb
        clc
        adc #40
        cmp #TB_N
        bcc +
        sbc #TB_N
+       sta z_nb
        lda tq
        clc
        adc #<(gidtab + 40)
        sta z_gp
        lda tq+1
        adc #>(gidtab + 40)
        sta z_gp+1
        ldy #0
        lda (z_gp),y
        sta z_ng
        rts

; ---------------------------------------------------------------- rungot (spritet)
; Lähimmät spritet 0..N_NEAR-1 (2 px/kehys), kaukaiset N_NEAR..7 (1 px/kehys). Jokaisella spritellä on
; ruudun X (16 bittiä, 0 = näkyvän alueen vasen reuna), joka pienenee kerroksen nopeudella; alle -48 = vapaa.
; Kerroksen seuraavan rungon etäisyys (nd) pienenee samoin; kun se on alle 344, runko saa vapaan spriten ja
; nd kasvaa listan välillä seuraavaan. Pinon rivin 0 Y ja osoittimet kirjoitetaan tässä, muut kernelissä.
sprites
        lda z_vfar              ; kaukaiset 1,5 px/kehys: 1 ja 2 vuorotellen
        eor #3
        sta z_vfar
        lda #N_NEAR             ; lähimmät
        sta zt
        lda #0
        sta zi
        lda z_vnear
        ldx #0
        jsr enter
        lda #8                  ; kaukaiset
        sta zt
        lda #N_NEAR
        sta zi
        lda z_vfar
        ldx #2
        jsr enter
        lda #0
        sta z_d010
        lda sx_free             ; sprite 0
        and #1
        bne _free0
        lda sx_lo+0
        sec
        sbc 0 + (0 < N_NEAR ? z_vnear : z_vfar)
        sta sx_lo+0
        lda sx_hi+0
        sbc #0
        sta sx_hi+0
        bpl _vis0
        cmp #$ff
        bne _off0
        lda sx_lo+0
        cmp #$d0                ; -48
        bcc _off0
_vis0  lda sx_lo+0           ; X = x + 24, alle 0 -> + 504
        clc
        adc #24
        tay
        lda sx_hi+0
        adc #0
        bpl +
        tya
        clc
        adc #$f8
        tay
        lda #1
+       sty sprx + 0
        lsr
        ror z_d010
        jmp _done0
_off0  lda sx_free
        ora #1
        sta sx_free
_free0 lda #<X_HIDE
        sta sprx + 0
        sec
        ror z_d010
_done0
        lda sx_free             ; sprite 1
        and #2
        bne _free1
        lda sx_lo+1
        sec
        sbc 0 + (1 < N_NEAR ? z_vnear : z_vfar)
        sta sx_lo+1
        lda sx_hi+1
        sbc #0
        sta sx_hi+1
        bpl _vis1
        cmp #$ff
        bne _off1
        lda sx_lo+1
        cmp #$d0                ; -48
        bcc _off1
_vis1  lda sx_lo+1           ; X = x + 24, alle 0 -> + 504
        clc
        adc #24
        tay
        lda sx_hi+1
        adc #0
        bpl +
        tya
        clc
        adc #$f8
        tay
        lda #1
+       sty sprx + 1
        lsr
        ror z_d010
        jmp _done1
_off1  lda sx_free
        ora #2
        sta sx_free
_free1 lda #<X_HIDE
        sta sprx + 1
        sec
        ror z_d010
_done1
        lda sx_free             ; sprite 2
        and #4
        bne _free2
        lda sx_lo+2
        sec
        sbc 0 + (2 < N_NEAR ? z_vnear : z_vfar)
        sta sx_lo+2
        lda sx_hi+2
        sbc #0
        sta sx_hi+2
        bpl _vis2
        cmp #$ff
        bne _off2
        lda sx_lo+2
        cmp #$d0                ; -48
        bcc _off2
_vis2  lda sx_lo+2           ; X = x + 24, alle 0 -> + 504
        clc
        adc #24
        tay
        lda sx_hi+2
        adc #0
        bpl +
        tya
        clc
        adc #$f8
        tay
        lda #1
+       sty sprx + 2
        lsr
        ror z_d010
        jmp _done2
_off2  lda sx_free
        ora #4
        sta sx_free
_free2 lda #<X_HIDE
        sta sprx + 2
        sec
        ror z_d010
_done2
        lda sx_free             ; sprite 3
        and #8
        bne _free3
        lda sx_lo+3
        sec
        sbc 0 + (3 < N_NEAR ? z_vnear : z_vfar)
        sta sx_lo+3
        lda sx_hi+3
        sbc #0
        sta sx_hi+3
        bpl _vis3
        cmp #$ff
        bne _off3
        lda sx_lo+3
        cmp #$d0                ; -48
        bcc _off3
_vis3  lda sx_lo+3           ; X = x + 24, alle 0 -> + 504
        clc
        adc #24
        tay
        lda sx_hi+3
        adc #0
        bpl +
        tya
        clc
        adc #$f8
        tay
        lda #1
+       sty sprx + 3
        lsr
        ror z_d010
        jmp _done3
_off3  lda sx_free
        ora #8
        sta sx_free
_free3 lda #<X_HIDE
        sta sprx + 3
        sec
        ror z_d010
_done3
        lda sx_free             ; sprite 4
        and #16
        bne _free4
        lda sx_lo+4
        sec
        sbc 0 + (4 < N_NEAR ? z_vnear : z_vfar)
        sta sx_lo+4
        lda sx_hi+4
        sbc #0
        sta sx_hi+4
        bpl _vis4
        cmp #$ff
        bne _off4
        lda sx_lo+4
        cmp #$d0                ; -48
        bcc _off4
_vis4  lda sx_lo+4           ; X = x + 24, alle 0 -> + 504
        clc
        adc #24
        tay
        lda sx_hi+4
        adc #0
        bpl +
        tya
        clc
        adc #$f8
        tay
        lda #1
+       sty sprx + 4
        lsr
        ror z_d010
        jmp _done4
_off4  lda sx_free
        ora #16
        sta sx_free
_free4 lda #<X_HIDE
        sta sprx + 4
        sec
        ror z_d010
_done4
        lda sx_free             ; sprite 5
        and #32
        bne _free5
        lda sx_lo+5
        sec
        sbc 0 + (5 < N_NEAR ? z_vnear : z_vfar)
        sta sx_lo+5
        lda sx_hi+5
        sbc #0
        sta sx_hi+5
        bpl _vis5
        cmp #$ff
        bne _off5
        lda sx_lo+5
        cmp #$d0                ; -48
        bcc _off5
_vis5  lda sx_lo+5           ; X = x + 24, alle 0 -> + 504
        clc
        adc #24
        tay
        lda sx_hi+5
        adc #0
        bpl +
        tya
        clc
        adc #$f8
        tay
        lda #1
+       sty sprx + 5
        lsr
        ror z_d010
        jmp _done5
_off5  lda sx_free
        ora #32
        sta sx_free
_free5 lda #<X_HIDE
        sta sprx + 5
        sec
        ror z_d010
_done5
        lda sx_free             ; sprite 6
        and #64
        bne _free6
        lda sx_lo+6
        sec
        sbc 0 + (6 < N_NEAR ? z_vnear : z_vfar)
        sta sx_lo+6
        lda sx_hi+6
        sbc #0
        sta sx_hi+6
        bpl _vis6
        cmp #$ff
        bne _off6
        lda sx_lo+6
        cmp #$d0                ; -48
        bcc _off6
_vis6  lda sx_lo+6           ; X = x + 24, alle 0 -> + 504
        clc
        adc #24
        tay
        lda sx_hi+6
        adc #0
        bpl +
        tya
        clc
        adc #$f8
        tay
        lda #1
+       sty sprx + 6
        lsr
        ror z_d010
        jmp _done6
_off6  lda sx_free
        ora #64
        sta sx_free
_free6 lda #<X_HIDE
        sta sprx + 6
        sec
        ror z_d010
_done6
        lda sx_free             ; sprite 7
        and #128
        bne _free7
        lda sx_lo+7
        sec
        sbc 0 + (7 < N_NEAR ? z_vnear : z_vfar)
        sta sx_lo+7
        lda sx_hi+7
        sbc #0
        sta sx_hi+7
        bpl _vis7
        cmp #$ff
        bne _off7
        lda sx_lo+7
        cmp #$d0                ; -48
        bcc _off7
_vis7  lda sx_lo+7           ; X = x + 24, alle 0 -> + 504
        clc
        adc #24
        tay
        lda sx_hi+7
        adc #0
        bpl +
        tya
        clc
        adc #$f8
        tay
        lda #1
+       sty sprx + 7
        lsr
        ror z_d010
        jmp _done7
_off7  lda sx_free
        ora #128
        sta sx_free
_free7 lda #<X_HIDE
        sta sprx + 7
        sec
        ror z_d010
_done7
; spr_commit: rivin 0 osoittimet S0:aan, spritejen rekisterit ja värit vasta, kun varjot (rivit 227-247) on näytetty
spr_commit
        lda noregs              ; initissä ei VIC-rekistereitä (edellisen kohtauksen kuva näkyy)
        bne _ptr
-       lda $d011               ; odota riviä SH_END (Y-laajennetut varjot loppuneet), jos ollaan välillä LINE_BOT..
        bmi +                   ; SH_END-1 (rivit 256-: 9. bitti)
        lda $d012
        cmp #LINE_BOT
        bcc _go                 ; seuraavan kehyksen alku: varjot ovat loppuneet
        bcs -
+       lda $d012
        cmp #SH_END - 256
        bcc -
_go     lda #0                  ; Y-laajennus pois (varjot loppuneet; kesken näyttöä kirjoitus voisi venyttää spritet)
        sta $d017
_ptr    .for i := 0, i < 8, i += 1
        lda ptrtab + i          ; rivin 0 osoittimet (S0:n osoittimet ovat varjojen rivin LINE_REST jälkeen vapaat)
        sta S0 + $3f8 + i
        .next
        lda noregs
        beq spr_regs
        rts

; spr_regs: spritejen X ($d010) ja rivin 0 Y ja yhteiset värit varjoista
spr_regs
        .for i := 0, i < 8, i += 1
        lda sprx + i
        sta $d000 + 2 * i
        .next
        lda z_d010
        sta $d010
        lda #SPR_R0 - 1
        .for i := 0, i < 8, i += 1
        sta $d001 + 2 * i
        .next
        lda #ROW0_D025
fa_r25 = * - 1
        sta $d025
        lda #ROW0_D026
fa_r26 = * - 1
        sta $d026
        rts

; enter: kerros X = 0 (lähimmät, lista near_*) tai 2 (kaukaiset, far_*), A = nopeus; spritet zi..zt-1.
; nd -= nopeus; niin kauan kuin nd < 344: runko saa vapaan spriten (x = nd), nd += väli seuraavaan.
enter   stx zs+1
        sta zs
        lda nd,x
        sec
        sbc zs
        sta nd,x
        bcs _chk
        dec nd+1,x
_chk    ldx zs+1
        lda nd,x
        sec
        sbc #<344
        lda nd+1,x
        sbc #>344
        bmi +
        rts
+       ldy zi                  ; vapaa sprite kerroksesta
-       lda sx_free
        and bit_of,y
        bne _got
        iny
        cpy zt
        bcc -
        inc spr_over            ; ei vapaata: runko jää pois (pitää olla 0)
        rts
_got    lda sx_free
        and bit_not,y
        sta sx_free
        lda nd,x
        sta sx_lo,y
        lda nd+1,x
        sta sx_hi,y
        tya
        pha
        cpx #0
        bne _f
        ldy nt                  ; lähimmät
        lda near_var,y
        sta zs
        lda nd
        clc
        adc near_glo,y
        sta nd
        lda nd+1
        adc near_ghi,y
        sta nd+1
        iny
        cpy #N_NEAR_T
        bcc +
        ldy #0
+       sty nt
        jmp _set
_f      ldy ntf                 ; kaukaiset
        lda far_var,y
        sta zs
        lda nd+2
        clc
        adc far_glo,y
        sta nd+2
        lda nd+3
        adc far_ghi,y
        sta nd+3
        iny
        cpy #N_FAR_T
        bcc +
        ldy #0
+       sty ntf
_set    pla
        tax
        lda zs
        jsr set_var
        ldx zs+1
        jmp _chk

; shadows: lähimpien runkojen (spritet 0-4) varjot tielle seuraavaan kehykseen. Tyven paikka x + tx valitsee
; kaltevuuden (pakopiste SH_XV, varjo kiertyy rungon ohittaessa) ja spriten X:n. irq_s1 asettaa Y:n ja
; osoittimet, irq_sh X:n, värit ja hires-tilan, irq_bot palauttaa rungot.
shadows lda #0                  ; varjot spriteinä 2-6: $D010:n bitit 2-6 (bit_of + SH0)
        sta sh_d010
        ldx #0
_sh     lda sx_free
        and bit_of,x
        beq +
        lda #SH_EMPTY
        sta sh_p,x
        jmp _nx
+       lda tx,x                ; tyvi = x + tx (16 bittiä)
        clc
        adc sx_lo,x
        sta zs
        lda sx_hi,x
        adc #0
        sta zs+1
        lda zs                  ; indeksi (tyvi + 32) >> 3, rajattuna 0..55
        clc
        adc #32
        sta zt
        lda zs+1
        adc #0
        bmi _k0
        lsr
        ror zt
        lsr
        ror zt
        lsr
        ror zt
        lda zt
        cmp #56
        bcc +
        lda #55
        bne +
_k0     lda #0
+       tay
        lda sh_k,y
        tay
        lda sh_ptr,y
        sta sh_p,x
        lda zs                  ; X = tyvi + 24 - sh_off (alle 0 -> + 504)
        clc
        adc #24
        sta zs
        bcc +
        inc zs+1
+       lda zs
        sec
        sbc sh_off,y
        sta zs
        lda zs+1
        sbc #0
        bpl +
        lda zs
        clc
        adc #$f8
        sta zs
        lda #1
+       sta zs+1
        lda zs
        sta sh_x,x
        lda sh_d010
        and bit_not + SH0,x
        ldy zs+1
        beq +
        ora bit_of + SH0,x
+       sta sh_d010
_nx     inx
        cpx #N_NEAR
        bcc _sh
        rts

; cyclist ja jogger: pyöräilijä ja lenkkeilijä koiran kanssa.
CYC_COL = 0                     ; musta (vastavalo), myös lenkkeilijä
CYC_PER = 470
CYC_T0 = 133                    ; alussa edellinen kierros vasemmalla (näkyy 0-125); seuraava 259-594, keskellä noin 430
JOG_PER = 700                   ; lenkkeilijä: näkyy 0-162, 345-512, 695-862 ja 1045-, pyöräilijä
JOG_T0 = 335                    ; ohittaa sen keskellä ruutua noin kehyksellä 430

; rider: tien hahmo seuraavaan kehykseen. Rata t (hires X) pienenee v joka kehys; näkyvissä, kun 8 <= t < 344
; (38 sarakkeen alue 31-334, sprite 24 leveä), muuten tyhjä lohko. Alle 8:n rata jatkuu per:n päästä (oikean reunan
; takana odottaa (per - 344 + 8) / v kehystä). Animaatio: fr = kehys 0..n-1, askel dph/256 kehystä (maan nopeudesta,
; build.py cyclist_consts ja jogger_consts). Tulos (irq_sh): X = t, hi9 (X:n 9. bitti bitissä 0) ja osoitin spr.
rider   .macro trk, phl, frm, hi9, spr, vel, per, dph, num, ptab
        .cerror (\per & 255) > 248, "radan jatkon alatavu ylivuotaa"
        lda \trk
        sec
        sbc #\vel
        sta \trk
        bcs +
        dec \trk+1
+       lda \trk+1
        bne +
        lda \trk
        cmp #8
        bcs +
        adc #<\per             ; C = 0
        sta \trk
        lda #>\per
        sta \trk+1
+       lda \phl
        clc
        adc #\dph
        sta \phl
        bcc ++
        ldx \frm
        inx
        cpx #\num
        bcc +
        ldx #0
+       stx \frm
+       lda \trk+1
        beq +                   ; 0..255: näkyy (A = 0)
        cmp #1
        bne ++                  ; 512-: oikean reunan takana
        lda \trk
        cmp #344 - 256
        bcs ++
        lda #1
+       sta \hi9               ; vain bitti 0 (irq_sh siirtää lenkkeilijän bittiin 1)
        ldx \frm
        lda \ptab,x
        sta \spr
        rts
+       lda #0
        sta \hi9
        lda #SH_EMPTY
        sta \spr
        rts
        .endm

cyclist #rider cyc_t, cyc_phl, cyc_fr, cyc_d010, cyc_p, CYC_V, CYC_PER, CYC_DPH, CYC_N, cyc_ptr
jogger  #rider jog_t, jog_phl, jog_fr, jog_d010, jog_p, JOG_V, JOG_PER, JOG_DPH, JOG_N, jog_ptr

; ---------------------------------------------------------------- häivytys (build.py fade_code)
; Sisääntulo häivytyksenä mustasta (kuva ei lävähdä suoraan ruutuun). Kun viimeinen nimi on mennyt ulos (FD_OUT),
; taso kasvaa F_OUT kehyksen välein mustaan, ja kohtaus loppuu mustana.
; Taso fd_lv: 0 = täysi väri, FD_N = musta. Sisääntulo: taso FD_N initissä, pienenee F_IN kehyksen välein. Tason
; vaihtuessa fade_map täyttää kartat (fmap rekistereille, fmapc värimuistille, fmask solukohtaisille väreille) ja
; työt fj_lo/fj_hi (operandit, $D021-taulu, värimuisti) ajetaan yksi kerrallaan, kun aikaa on (fd_time).

; fade_init (greetsit_init): taso FD_N karttoihin ja operandeihin; värimuistin kirjoittaa greetsit_go (color_go:n
; operandit), joten init ei koske siihen.
fade_init
        lda #FD_N
        sta fd_lv
        sta fd_ap
        lda #$ff
        sta fd_st
        lda #F_IN
        sta fd_cd
        sta fd_per
        lda #FJ_N
        sta fd_j
        jsr fade_map
        sta fd_cm               ; A = fmask: solukohtaiset värit color_go:ssa
        jmp fade_sites

fade_run
        inc fd_t
        bne +
        inc fd_t+1
+       lda fd_t                ; viimeinen nimi ulos: häivytys mustaan
        cmp #<FD_OUT
        bne +
        lda fd_t+1
        cmp #>FD_OUT
        bne +
        lda #1
        sta fd_st
        sta fd_cd               ; ensimmäinen askel heti
        lda #F_OUT
        sta fd_per
+       lda fd_st               ; taso askel kerrallaan kohti päätä
        beq _job
        dec fd_cd
        bne _job
        lda fd_per
        sta fd_cd
        lda fd_lv
        clc
        adc fd_st
        sta fd_lv
        beq _end                ; täysi väri
        cmp #FD_N
        bne _job
_end    lda #0
        sta fd_st
_job    ldx fd_j
        cpx #FJ_N
        bcc _run
        lda fd_lv               ; edellinen taso tehty: uusi, jos taso vaihtui
        cmp fd_ap
        beq _out
        sta fd_ap
        jsr fade_map
        ldx #0
_run    stx fd_j
        jsr fd_time
        bcs _out
        lda fj_lo,x
        sta fd_vec
        lda fj_hi,x
        sta fd_vec+1
        jsr _call
        ldx fd_j
        inx
        cpx #FJ_N
        bcc _run
        stx fd_j
        lda fd_ap               ; musta valmis: näyttö pois (VIC:n väri-
        cmp #FD_N               ; rekisterien kirjoitukset kuvan aikana jättäisivät mustaan harmaita pisteitä, 8565)
        bne _out
        lda #$0b | ((LINE_REST >> 1) & $80)
        sta fa_d11a
        lda #$0b
        sta fa_d11b
_out    rts
_call   jmp (fd_vec)

; fd_time: X = työ. C = 0: työ (fj_rows: kesto riveinä) ehtii ennen riviä FD_END, jolloin kernelin IRQ (rivi 44) ei
; keskeytä sitä (kesken kernelin jäänyt työ venyttäisi logiikan seuraavan irq_bot:n yli: pudotus). Jäljellä olevat
; rivit: 256-311 -> FD_END + 56 - (rivi - 256), LINE_BOT-255 -> FD_END + 312 - rivi, seuraavan kehyksen 0-FD_END -> FD_END - rivi.
FD_END = 40
fd_time lda $d011
        bmi _hi
        lda $d012
        cmp #LINE_BOT
        bcs _lo
        cmp #FD_END
        bcs _no
        eor #$ff                ; FD_END - rivi
        sec
        adc #FD_END
        jmp _cmp
_lo     eor #$ff                ; FD_END + 312 - rivi = (FD_END + 56) + (256 - rivi)
        sec
        adc #FD_END + 56        ; (256 - rivi = 256 + ~rivi + 1)
        jmp _cmp
_hi     lda $d012               ; rivi - 256
        eor #$ff
        sec
        adc #FD_END + 56
_cmp    cmp fj_rows,x           ; C = 1: jäljellä >= kesto
        bcc _no
        clc
        rts
_no     sec
        rts

fade_map                        ; tason fd_ap kartat; A = fmask
        lda fd_ap
        asl
        asl
        asl
        asl
        tax
        ldy #0
-       lda fade_tab,x
        sta fmap,y
        lda fadec_tab,x
        sta fmapc,y
        inx
        iny
        cpy #16
        bne -
        ldx fd_ap
        lda fmask_tab,x
        sta fmask
        rts

fade_asm                        ; greetsit.asm:n IRQ-vakiot ja runkojen värit (fade_sites:n lopusta)
        ldx #7
-       ldy tcolo,x
        lda fmap,y
        sta tcol,x
        dex
        bpl -
        lda fmap + PIENNAR_D022
        sta fa_pn22
        lda fmap + PIENNAR_D023
        sta fa_pn23
        lda fmap + SH_COL
        sta fa_sh
        lda fmap + TIE_D022
        sta fa_t22
        lda fmap + TIE_D023
        sta fa_t23
        lda fmap + TIE_BG
        sta fa_tbg
        lda fmap + TIE_V1_D022
        sta fa_v122
        lda fmap + TIE_V1_D023
        sta fa_v123
        lda fmap + TIE_V2_D022
        sta fa_v222
        lda fmap + TIE_V2_D023
        sta fa_v223
        lda fmap + TIE_V2_BG
        sta fa_v2bg
        lda fmap + ROW0_D025
        sta fa_r25
        lda fmap + ROW0_D026
        sta fa_r26
        rts

; set_var: sprite X saa variantin A: oma väri ja 8 pinon osoitinta ptrtab:iin (sarake X).
set_var sta zs
        tay
        lda var_col,y
        sta tcolo,x
        lda var_tx,y
        sta tx,x
        ldy tcolo,x             ; häivytyksen taso (fmap): $d027+i kirjoittaa irq_rest (ja greetsit_go)
        lda fmap,y
        sta tcol,x
        lda zs
        asl
        asl
        asl
        tay
        .for k := 0, k < 8, k += 1
        lda var_ptr + k,y
        sta ptrtab + 8 * k,x
        .next
        rts

bit_of  .byte 1, 2, 4, 8, 16, 32, 64, 128
bit_not .byte $fe, $fd, $fb, $f7, $ef, $df, $bf, $7f

        .include "gen_lo.asm"
        .include "maps.asm"
        .include "gen_hi.asm"
        .include "tables.asm"
code_end                                ; ladattavan osan loppu
        .cerror code_end > $c000, "koodi ylittää $c000 (kodin pankki 3)"

; ---------------------------------------------------------------- kulkeva aalto (GREETSIT3 $1b00-, koodi $8000-$bfff on täynnä)
        * = CODE3
code3
; dycp_run: kehyksen logiikan jälkeen työtä aikarajan sisällä (ajasta): ensin karkean askeleen uusi sarake
; (new_col, ruudun piilossa olevaan sarakkeeseen), sitten aallon vaiheen askeleet yksi kerrallaan (vis_step: portaiden
; sarakkeet jonoon), sitten jonon sarakkeet (enintään VMAX). Sarake (noin 400 sykliä) ei saa jäädä kesken kernelin
; (rivit 44-198) yli, koska sen perässä irq_s1, irq_sh ja irq_s2 venyttäisivät sen irq_bot:n (230) yli: rivit 36-197
; odotetaan, kernelin jälkeen vielä rivit 198-199 sarakkeelle, ei vaiheen askeleelle (noin 1 000 sykliä: raskaan
; kaistakopion kehyksessä askel riveiltä 198- venyisi riville 230, kehys pudotettaisiin ja seuraava kerneli olisi
; rikki).
dycp_run
        ldx #0                  ; z_k = 1: kehys on vaihtunut (logiikka myöhässä, rivi < LINE_BOT)
        lda $d011
        bmi +
        lda $d012
        cmp #LINE_BOT
        bcs +
        inx
+       stx z_k
        lda #VMAX
        sta z_vn
_lp     jsr ajasta
        bcs _out
        lda z_nb
        bmi _ph
        jsr new_col
        jmp _lp
_ph     lda z_pq                ; käsittelemättömät vaiheen askeleet z_pq -> z_ph (WAVE_DP kehyksessä)
        cmp z_ph
        beq _vis
        lda $d011
        bmi +
        lda $d012
        cmp #198
        bcc +
        cmp #200
        bcc _out                ; rivit 198-199: vain sarakkeelle
+       jsr vis_step
        jmp _lp
_vis    lda z_vn
        beq _out
        ldx z_qh
        cpx z_qt
        beq _out
        dec z_vn
        lda wv_q,x
        tay
        inx
        txa
        and #31
        sta z_qh
        jsr vis_col
        jmp _lp
_out    rts

ajasta                          ; C = 0: sarakkeelle on aikaa, C = 1: lopeta
        lda $d011
        bmi _ok0                ; rivit 256-311
        lda $d012
        cmp #LINE_BOT
        bcs _hi
        cmp #36
        bcc _wr                 ; rivit 0-35
        cmp #198
        bcc _wait               ; 36-197: kerneli tulee; odota sen yli
        cmp #200
        bcc _wr                 ; 198-199 (spritejen DMA ja badlinet: sarake noin 10 riviä, valmis ennen irq_s1:tä)
        sec                     ; 200-229: loppu
        rts
_hi     lda z_k                 ; 230-255: vain ennen kehyksen vaihtoa
        bne _no
_ok0    clc
        rts
_wr     lda #1
        sta z_k
        clc
        rts
_wait   lda #1
        sta z_k
-       lda $d012               ; kerneli keskeyttää rivillä 44 ja palaa rivillä 198
        cmp #198
        bcc -
        bcs ajasta
_no     sec
        rts

wave_step                       ; aallon vaihe tälle kehykselle (pienenee WAVE_DP)
        lda z_ph
        sec
        sbc #WAVE_DP
        sta z_ph
        rts

; new_col: uusi sarake z_nb (tasoindeksi z_ng) aallon nykyiseen siirtoon, z_nb = $ff.
new_col
        ldy z_nb
        lda #$ff
        sta z_nb
draw_new                        ; Y = puskurin sarake, z_ng = tasoindeksi
        lda z_ng
        sta z_gid
        lda cph,y
        clc
        adc z_ph
        tax
        lda wv_sin,x
        sta z_n
        tya
        tax
        jmp col_draw

; vis_step: ruudun sarakkeet (ja seuraava uusi), joiden siirto muuttui vaiheen askeleessa z_pq -> z_pq - 1 (aallon
; portaat wst_i: puskurin sarakkeet, joilla cph = s - 1 - p, wv_inv, ja + WAVE_COLS), jonoon wv_q; dycp_run piirtää
; jonosta enintään VMAX saraketta kehyksessä (portaat kasautuvat), yksi rivi kohti aaltoa; kesken jäänyt sarake palaa
; jonoon.
VMAX = 6
vis_step
        dec z_pq
        ldx #WST_N - 1
-       stx z_c2
        lda wst_i,x
        clc
        sbc z_pq                ; s - 1 - p
        tay
        lda wv_inv,y
        bmi _nx
        jsr q_put
        clc
        adc #WAVE_COLS
        jsr q_put
_nx     ldx z_c2
        dex
        bpl -
        rts

q_put   pha                     ; A = puskurin sarake jonoon (A säilyy), jos se on ruudulla tai seuraava uusi
        sec                     ; ((A - tb) mod TB_N <= 40); täysi jono: sarake jää pois
        sbc tb
        bcs +
        adc #TB_N
+       cmp #41
        bcs _no
        ldx z_qt
        pla
        sta wv_q,x
        inx
        pha
        txa
        and #31
        cmp z_qh
        beq _no
        sta z_qt
_no     pla
        rts

vis_col                         ; Y = puskurin sarake: yksi rivi kohti aaltoa
        lda cph,y
        clc
        adc z_ph
        tax
        lda wv_sin,x
        sta z_t
        tya
        tax
        lda wv_vy,x
        cmp z_t
        beq _ok
        bcc _inc                ; vanha < aalto
        sbc #1                  ; C = 1
        jmp _st
_inc    adc #1                  ; C = 0
_st     sta z_n
        cmp z_t
        beq +
        tya                     ; askel jäi kesken: jonoon uudelleen
        jsr q_put
        tya
        tax
+       lda wv_gd,x
        sta z_gid
        jmp col_draw
_ok     rts

; col_draw: Y = X = puskurin sarake, z_n = uusi siirto, z_gid = tasoindeksi. Vanhan siirron (wv_vy) ja uuden väliin
; jäävät rivit nollataan, sitten kirjain 25 riviä (dycp_g<ryhmä>).
col_draw
        sty z_c
        lda z_gid               ; tyhjä sarake tyhjän päälle: vain siirto talteen (rivit ovat jo nollia)
        cmp #G_BLANK
        bne +
        cmp wv_gd,x
        bne +
        lda z_n
        sta wv_vy,x
        rts
+       sta wv_gd,x
        lda wv_vy,x
        sta z_o
        lda z_n
        sta wv_vy,x
        lda wv_pg,x
        sta zptr+1
        lda z_n
        sec
        sbc z_o
        beq _zd
        bcc _up
        tax                     ; uusi alempana: rivit o..n-1
        lda dy_yo,y
        adc z_o                 ; C = 1: +1 korjataan
        sbc #0
        tay
        jmp _zl
_up     eor #$ff                ; uusi ylempänä: rivit n+25..o+24 (C = 0: -A)
        adc #1
        tax
        lda dy_yo,y
        clc
        adc z_n
        adc #GLYPH_H
        tay
_zl     lda #0
-       sta (zptr),y
        iny
        dex
        bne -
        ldy z_c
_zd     lda dyg_lo,y
        sta _j+1
        lda dyg_hi,y
        sta _j+2
        lda dy_yo,y
        clc
        adc z_n
        tay
        ldx z_gid
_j      jmp $ffff

; wave_init: siirrot alkuun 3 ja piirretty taso tyhjä (puskuri on levyltä nollia, joten initin tyhjät sarakkeet
; ohitetaan), jono tyhjä. Taulut wv_sin, wv_inv ja wv_pg ovat valmiina (wave.asm).
wave_init
        lda #0
        sta z_ph
        sta z_pq
        sta z_qh
        sta z_qt
        sta zptr
        ldx #TB_N - 1
-       lda #G_BLANK
        sta wv_gd,x
        lda #3
        sta wv_vy,x
        dex
        bpl -
        rts

        .include "wave.asm"
code3_end
        .cerror code3_end > WV_BASE, "GREETSIT3 yli aallon taulujen"

; ---------------------------------------------------------------- ajonaikaiset (nollataan initissä)
        .virtual RUN_BASE
bss_start
ptrtab  .fill 64
sx_lo   .fill 8                 ; spriten X ruudulla (0 = näkyvän alueen vasen reuna)
sx_hi   .fill 8
sx_free .byte ?
nt      .byte ?                 ; seuraava runko listassa
ntf     .byte ?
nd      .fill 4                 ; seuraavan rungon etäisyys (lähimmät, kaukaiset)
sprx    .fill 8                 ; spritejen X (alatavu) seuraavaan kehykseen
rox_t   .fill 24                ; tien rivien siirtotaulun indeksit (kerneli kopioi)
tcol    .fill 8                 ; runkojen värit häivytyksen tasolla (irq_rest; varjot vaihtavat ne tien ajaksi)
tcolo   .fill 8                 ; runkojen omat värit (täysi väri)
tx      .fill 8                 ; rungon tyven keskikohta spriten vasemmasta reunasta (hires)
sh_p    .fill N_NEAR            ; varjojen osoittimet, X ja $D010 seuraavaan kehykseen
sh_x    .fill N_NEAR
sh_d010 .byte ?
cyc_t   .word ?                 ; pyöräilijän rata (hires X)
cyc_phl .byte ?                 ; kammen vaihe (alatavu)
cyc_fr  .byte ?                 ; kammen kehys 0..CYC_N-1
cyc_d010 .byte ?                ; seuraavan kehyksen $D010:n bitti 0 ja osoitin (irq_sh; X = cyc_t)
cyc_p   .byte ?
racc_lo .fill 24
racc_hi .fill 24
fmap    .fill 16                ; häivytyksen tason kartat (init nollaa: musta)
fmapc   .fill 16
fmask   .byte ?
fd_t    .word ?                 ; kehyksiä (fade_run)
fd_lv   .byte ?                 ; taso 0 (täysi) .. FD_N (musta)
fd_st   .byte ?                 ; askel: $ff sisään, 1 ulos, 0 ei
fd_cd   .byte ?                 ; kehyksiä seuraavaan askeleeseen
fd_per  .byte ?
fd_ap   .byte ?                 ; tehtävä taso
fd_j    .byte ?                 ; seuraava työ (FJ_N = valmis)
fd_cm   .byte ?                 ; solukohtaisten värien maski värimuistissa
fd_vec  .word ?
        .cerror fd_vec & $ff == $ff, "jmp (fd_vec) sivun rajalla"
bss_end
        .cerror bss_end - bss_start > 255, "bss yli 255 tavua"
        .endv
        .virtual WV_BASE
wv_vy   .fill TB_N              ; puskurin X0 sarakkeiden piirretty siirto
wv_gd   .fill TB_N              ; sarakkeen piirretty tasoindeksi
wv_q    .fill 32                ; näkyvän puskurin päivitysjono
wv_end
        .cerror wv_end > $2400, "aallon taulut yli $23ff"
        .endv


        * = CS_A
        .binary "cs_a.bin"
        * = CS_T
        .binary "cs_t.bin"
        * = $5900
        .binary "sprites.bin"
        .include "layout.inc"
        * = SPR_END                     ; color_u VIC-pankin 1 loppuun spritejen perään (GREETSIT7), taulut koodin perässä
        .include "color_u.asm"
        .cerror * > $8000, "taulukot ylittävät $8000"

maps_end = code_end
