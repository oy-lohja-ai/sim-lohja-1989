; Levynvaihtoruudut: 5,25" levyke pyörii
; 3D:nä pystyakselinsa ympäri perspektiivissä (lepokulma noin -35 astetta) ja kääntyy (puoli vaihtuu) tai poistuu ja
; uusi tulee tilalle, alla teksti Lohjan murteella (tekstit.yaml: levynvaihdot). Pinta on levykkeen
; kuva (40 x 80 MC-px, ditheröity kuori, tarra, aukot) ja se näytetään pikselisarakkeittain: jokaisen
; tavusarakkeen neljä pikseliä ovat pinnan sarakkeita q..q+3 (perspektiivikorjattu u, kapenevalla levyllä mip-tasot
; 20, 10, 5..1), ja sarakkeen rivit kirjoitetaan aukikirjoitetulla koodilla: ldy v-kartta,x (puolikorkeus) /
; lda (pintasarake),y / sta bittikartta. Ylä- ja alareuna maskataan pikseleittäin. Vain muuttuneet sarakkeet
; piirretään. Musiikki ja kello soivat rungon FRAME_HOOKilla rivin 250 IRQ:ssa.
; Data tools/disk/levynvaihto.py (Levy on tämän piirron viitemalli). Tiedostot: LV1 koodi ja taulut ($1a00-),
; LV3 ruutu, U-taulu ja bittikartta ($4400-$7f3f, VIC-pankki 1: ruutu $4400, bittikartta $6000), LV2 aukikirjoitettu
; koodi ($8000-). lv_init generoi pintasarakkeet ($5800-$5fff, $a900-$afff, $c300-$cfff, $e000-$fff2) ja v-kartan
; ($b200-$c23f); $b000-$b1ff jää seuraavan levyn tunnistetiedostolle.

        .include "runko.inc"
        .include "krill.inc"
        .include "lv_defs.inc"
        .include "music.inc"            ; build/runko: MUSIC_LOAD, MUSIC_BUF, MUSIC_ZP (LV4: tahdin silmukka)

BMP     = $6000
SCR     = $4400
LV_LEN  = NVAIHTO * PER
GUARD   = 14848                 ; kehyksen työ (CIA-sykleinä) tätä pidemmällä: ei enää uutta saraketta (sarake <= 1 800)
zq      = $f0                   ; nollasivu $f0-$f7 (piirto): pintasarake (aukikirjoitettu koodi)
zt      = $f2                   ; paikattava rivi, maskattava rivi
zu      = $f4                   ; U-taulun rivi k
zhh     = $f6                   ; yleisen sarakekoodin v-kartan indeksi
zs      = $f8                   ; pääsäie (levynvaihdon allekirjoitus): IRQ:n piirto käyttää $f0-$f7
gsrc    = $f0                   ; lv_init: pintasarakkeiden generointi
gprev   = $f2
gdst    = $f4

        * = $1a00
        .dsection code
        .cerror * > SCR, "LV1 yli ruudun: ", format("$%04x", *)
        * = SCR
        .dsection gfx
        * = $8000
        .dsection speed
        .cerror * > st_t3, "LV2 yli sarakkeiden tilan: ", format("$%04x", *)
        * = $5f00               ; LV4: biisin pysähdys vaihdon ajaksi (LV1 ja LV2 täynnä; pintasarakkeet $5800-$5eff,
        .dsection hold          ; $a900-$afff, $c300-$cfff ja $e000-, v-kartta $b200-$c23f, ID_AT $b000-)
        .cerror * > BMP, "LV4 yli bittikartan: ", format("$%04x", *)

        .section gfx
        .binary "lv_ruutu.bin"          ; ruutu (levynvaihto.py screen): levyn soluissa %10 tummanharmaa 11
        .fill $4800 - *, 0
                                        ; U-taulu ut [k][t] (sivun rajalla)
        .include "lv_ut.inc"
lv_trow                                 ; $5800-: bittikartan rivitavut (tausta on rivivakio, levynvaihto.py): lv_bg
        .for _y := 0, _y < 200, _y += 1 ; täyttää bittikartan niistä ennen kuin lv_gen kirjoittaa tähän pintasarakkeet,
        .binary "lv_tausta.bin", (_y >> 3) * 320 + (_y & 7), 1   ; joten bittikarttaa ei ladata (koko demossa LV1
        .next                           ; ja tämä esiladataan purun aikana, ruutu näkyy heti hillnerin jälkeen)
; lv_bg (lv_init0, ennen lv_geniä, joka kirjoittaa tämän päälle): bittikartta $6000-$7f3f rivitavuista, noin 4 kehystä
lv_bg   lda #<BMP
        sta zs
        lda #>BMP
        sta zs+1
        ldx #0                  ; X = merkkirivi * 8 (lv_trow)
_cr     ldy #0
-       lda lv_trow,x           ; merkkirivin 8 rivitavua nollasivulle $f0-$f7
        sta zq,y
        inx
        iny
        cpy #8
        bne -
        lda #40
        sta lvb_n
        ldy #0
_c      .for _k := 0, _k < 8, _k += 1   ; solu: 8 tavua
        lda zq + _k
        sta (zs),y
        iny
        .next
        bne +
        inc zs+1                ; solut 32-39 seuraavalla sivulla
+       dec lvb_n
        bne _c
        tya                     ; seuraava merkkirivi: +320 (sivu jo +1, Y = 64)
        clc
        adc zs
        sta zs
        bcc +
        inc zs+1
+       cpx #200
        bne _cr
        rts
lvb_n   .byte 0
        .cerror * > lv_trow + $200, "lv_trow ja lv_bg yli $59ff (lv_init0 nollaa sen)"
        .send gfx

        .section speed          ; nopeat sarakkeet FC0..FC0+NF-1: rivi r = ldy vm_r,x / lda (zq),y / sta (8 t, 13 sykliä).
                                ; Yläpuolisko rivit 0..CY-1, sitten alapuolisko takaperin NR-1..CY: rivit lo..NR-1-lo
                                ; ovat kaksi kutsua samalla siirtymällä 8 lo kummankin puoliskon alusta (ei paikkausta)
fsc0
        .for j := 0, j < NF, j += 1
        .for i := 0, i < NR, i += 1
r       := i < CY ? i : NR - 1 - (i - CY)
        .byte $bc
        .word VM + r * NH
        .byte $b1, zq, $8d
        .word BMP + ((R0 + r) / 8) * 320 + (R0 + r) % 8 + (C0 + FC0 + j) * 8
        .if i == CY - 1
        rts
        .endif
        .next
        rts
        .next
gsc                             ; muut sarakkeet (X = 8 c): ldy zhh / lda vm_r,y / tay / lda (zq),y / sta ,x (11 t)
        .for i := 0, i < NR, i += 1
r       := i < CY ? i : NR - 1 - (i - CY)
        .byte $a4, zhh, $b9
        .word VM + r * NH
        .byte $a8, $b1, zq, $9d
        .word BMP + ((R0 + r) / 8) * 320 + (R0 + r) % 8 + C0 * 8
        .if i == CY - 1
        rts
        .endif
        .next
        rts

hold_init                       ; lv_swapin alussa (pääsäie, LV2): seuraavan tahdin alku bd = DFRAME + (-(DFRAME +
        sei                     ; lv_song) mod LOOP_N), sirq ottaa tilan talteen siinä
        lda DFRAME
        sta bd
        clc
        adc lv_song
        tax
        lda DFRAME+1
        sta bd+1
        adc lv_song+1
-       tay                     ; mod LOOP_N vähentämällä (enintään 546 kierrosta)
        txa
        sec
        sbc #LOOP_N
        tax
        tya
        sbc #0
        bcs -
        txa                     ; C = 0: jäännös r = X + LOOP_N, bd + LOOP_N - r (r = 0: bd)
        adc #LOOP_N
        beq +
        eor #$ff
        sec
        adc #LOOP_N
        clc
        adc bd
        sta bd
        bcc +
        inc bd+1
+       lda #0
        sta lend
        lda #1
        sta lmode
        cli
        rts

        .send speed

        .section code
lv_init                         ; pääsäikeestä ennen kelloa: värit, pintasarakkeet ja v-kartta, teksti, ensimmäinen kuva
        jsr lv_init0
        jsr text_all
        jsr lv_gen
        jmp lv_first

lv_init0                        ; kevyt valmistelu (värit, sarakkeet tyhjiksi) ilman pintasarakkeita ja tekstiä: lv_swap
        jsr lv_bg               ; näyttää ruudun heti ja generoi pinnat pääsäikeessä (noin 1 s), levy kääntyy esiin
        ldx #0                  ; lv_trow ja lv_bg nolliksi: pintasarakkeiden generointi olettaa $5800-$5fff nollatuksi
        txa
-       sta lv_trow,x
        sta lv_trow + $100,x
        inx
        bne -
        stx ready
        stx ent
        lda #1                  ; %11: teksti valkoinen (levyn alueen rivit: shade)
-       sta $d800,x
        sta $d900,x
        sta $da00,x
        sta $dae8,x
        inx
        bne -
        ldx #NC - 1             ; sarakkeet tyhjiä
-       lda #0
        sta st_hi,x
        lda #CY
        sta st_otop,x
        dex
        bpl -
        lda #1
        sta ocl
        lda #0
        sta ocr
        sta var
        sta disk
        sta lvl
        sta pend
        jmp shade               ; teksti vasta levyn kanssa (lv_swap: text_all; ensin pelkkä taustaväri, jotta ruutu ei
                                ; näytä rikkinäiseltä):
                                ; tcopy pysyy 8:ssa ja tc0 0:ssa (LV1 ladataan joka vaihdolle), joten IRQ ei piirrä

lv_show                         ; koko demo: ruutu (pelkkä tausta, lv_init0) näkyviin, kun LV2 (aukikirjoitettu piirto)
        lda #0                  ; latautuu vielä; sirq ei piirrä levyä ennen lv_swapin pintasarakkeita (ready = 0), mutta
        sta busy                ; tekstin kiilto elää (kokoa.py: LV1 ja LV3:n alku esiladattu, LV3:n loppu, lv_init0,
        sta quit                ; lv_show, LV2, lv_swap)
        sei
        lda #<sirq
        ldx #>sirq
        jmp show

lv_gen  jsr gen_quads           ; pintasarakkeet ja v-kartta (noin 1 000 000 sykliä), sitten levy piirretään
        jsr gen_vm
        lda #1
        sta ready
        rts

lv_first                        ; ensimmäinen kuva valmiiksi (ei aikavartijaa)
        jsr pose
        lda #$ff
        sta glimit
        jsr render
        lda #GUARD >> 8
        sta glimit
        rts

lv_go                           ; ottaa näytön ja IRQ:n, piirtää joka kehys, palaa kehyksellä t0 + LV_LEN
        sei
        lda DFRAME
        sta t0
        lda DFRAME+1
        sta t0+1
        lda #<lirq
        ldx #>lirq
        jsr show
_loop   jsr R_IDLE
        lda DFRAME
        cmp lastf
        beq _loop
        sta lastf
        sec                     ; t = DFRAME - t0
        sbc t0
        sta t
        lda DFRAME+1
        sbc t0+1
        sta t+1
        lda t
        cmp #<LV_LEN
        lda t+1
        sbc #>LV_LEN
        bcc +
        rts
+       jsr frame
        jmp _loop

frame                           ; kehyksen työ (asento, teksti, piirto) ja sen syklit (CIA1 A, mittari lv_cyc/lv_max)
        lda ready               ; pintasarakkeet vielä generoimatta (lv_init0 + lv_swap): ei piirtoa
        bne +
        rts
+       jsr cia
        sta cyc0
        sty cyc0+1
        jsr pose
        ldx ent                 ; esiinkääntö: levy syrjästä lepoon ENT kehyksessä (ent_tab kulman lisäys)
        beq +
        dex
        stx ent
        lda th
        clc
        adc ent_tab,x
        sta th
+       jsr render
        lda drawn               ; teksti vain kehyksillä, joilla levy ei muuttunut
        bne +
        jsr text_step
+       jsr cia
        sta d
        lda cyc0                ; ajastin laskee alaspäin ($ffff:stä): syklit = alku - loppu
        sec
        sbc d
        sta lv_cyc
        tya
        eor #$ff
        adc cyc0+1              ; cyc0+1 - Y - 1 + C
        sta lv_cyc+1
        cmp lv_max+1
        bcc ++
        bne +
        lda lv_cyc
        cmp lv_max
        bcc ++
+       lda lv_cyc
        sta lv_max
        lda lv_cyc+1
        sta lv_max+1
+       inc lv_n
        rts

cia     ldy $dc05               ; CIA1:n ajastin A -> A ala, Y ylä (kulku.asm ku_cia)
        lda $dc04
        cpy $dc05
        beq +
        ldy $dc05
        lda $dc04
+       rts

; ---------------------------------------------------------------- oikea levynvaihto

ID_AT   = $b000                 ; seuraavan levyn tunnistetiedosto ladataan tänne
RETRY   = 25                    ; uusi yritys kehyksinä (tyhjä asema tai väärä levy)
AFTER   = 50                    ; tunnistuksen jälkeen ruutu vielä näin monta kehystä

lv_swap0                        ; vaihdot kohtaustaulun S_CALLeille (0: kääntö puolelle B, 1: levy 2 sisään, ...)
        ldx #0
        .byte $2c
lv_swap1
        ldx #1
        .byte $2c
lv_swap2
        ldx #2
        .byte $2c
lv_swap3
        ldx #3
        .byte $2c
lv_swap4
        ldx #4
lv_swap                         ; X = vaihto: ruutu kuten lv_go, mutta piirto rivin 250 IRQ:ssa, ja pääsäie yrittää
        stx var                 ; ladata seuraavan levyn tunnistetiedoston (Krill), kunnes se
                                ; löytyy ja allekirjoitus täsmää; sitten AFTER kehystä ja paluu kuva mustana rungon IRQ:lla.
        jsr hold_init           ; sama tahti soi silmukkana ruudun ajan (jatkuu tahdin alusta, kun levy tunnistetaan)
        lda #1                  ; Valmistelu rungon IRQ:n soittaessa (ei sei:tä: soittimen kutsu ei jää väliin)
        sta fixed
        lda #0
        sta disk
        sta busy
        sta quit
        jsr shade
        lda DFRAME
        sta t0
        lda DFRAME+1
        sta t0+1
        lda #0
        sta t
        sta t+1
        lda ready
        beq +
        jsr lv_first
+       sei                     ; IRQ-vektorin vaihto (show tekee cli:n); rungon ja sirq:n kutsu molemmat rivillä 250
        lda #<sirq
        ldx #>sirq
        jsr show
        lda ready               ; lv_init0: ruutu (pelkkä tausta) näkyy, pinnat generoidaan nyt ja levy kääntyy esiin
        bne +
        lda #ENT
        sta ent
        jsr lv_gen
        ldx #1                  ; teksti samaan kehykseen, jossa levy alkaa kääntyä esiin: sirq piirtää levyn
        jsr after               ; rivillä 250 seuraavaan kuvaan, teksti piirtyy sen jälkeen ennen tekstiriviä
+       jsr text_all
_poll   lda var                 ; nimi ja allekirjoitus vaihdon mukaan
        asl a
        tax
        lda id_names,x
        ldy id_names + 1,x
        tax
        jsr loadraw
        bcs _retry
        lda var
        asl a
        tax
        lda id_sigs,x
        sta zs
        lda id_sigs + 1,x
        sta zs+1
        ldy #SIG_LEN - 1
-       lda (zs),y
        cmp ID_AT,y
        bne _retry
        dey
        bpl -
        jsr hold_end            ; silmukan loppuun: biisi jatkuu tahdin alusta (kello samaan vaiheeseen)
        ldx #AFTER
        jsr after
        lda lv_lead             ; koko demo (kokoa.py): ruutu jatkuu, kunnes DFRAME + lv_lead on iskulla (mod 30 = 0;
        beq _q                  ; seuraava kohtaus alkaa iskulle samassa vaiheessa), joten seuraavan latauksen jälkeen
-       clc                     ; ei odoteta iskua mustassa
        adc DFRAME
        sta zs
        lda DFRAME+1
        adc #0
        sta zs+1
        ldx #8                  ; zs mod 30: vähennetään 30 << k, k = 8..0
-       lda zs+1
        cmp _m30h,x
        bcc _nx
        bne _sb
        lda zs
        cmp _m30l,x
        bcc _nx
_sb     lda zs                  ; C = 1
        sbc _m30l,x
        sta zs
        lda zs+1
        sbc _m30h,x
        sta zs+1
_nx     dex
        bpl -
        lda zs
        beq _q
        ldx #1
        jsr after
        lda lv_lead
        jmp --
_q      lda #1                  ; sirq pimentää ja vaihtaa rungon IRQ:hun omalla rivillään (sen piirto vie reunuksen,
        sta quit                ; joten pääsäie ei näkisi sitä; soittimen kutsu ei jää väliin eikä tuplaannu)
-       bit quit
        bpl -
        rts
_retry  ldx #RETRY
        jsr after
        jmp _poll
_m30l   .byte <(30 << 0), <(30 << 1), <(30 << 2), <(30 << 3), <(30 << 4), <(30 << 5), <(30 << 6), <(30 << 7), <(30 << 8)
_m30h   .byte >(30 << 0), >(30 << 1), >(30 << 2), >(30 << 3), >(30 << 4), >(30 << 5), >(30 << 6), >(30 << 7), >(30 << 8)
lv_lead .byte 0                 ; kokoa.py: arvio kehyksistä ruudun lopusta seuraavan kohtauksen alkuun (0: ei odotusta)


sirq    pha                     ; rivi 250: musiikki ja kello, kiilto ja (sisäkkäin, cli) levyn kehys
        txa
        pha
        tya
        pha
        lda $01
        pha
        lda #$35
        sta $01
        asl $d019
        jsr hold_hook           ; tahdin silmukka ja FRAME_HOOK (LV4)
        jsr glint_step
        lda quit                ; lv_swapin loppu: kuva pimeäksi (rivi 250, kuva piirretty) ja seuraavat kehykset
        beq +                   ; rungon IRQ:lla
        lda #$0b
        sta $d011
        lda #0
        sta fixed
        jsr R_IRQ_ON
        lda #$80
        sta quit
        bne _out
+       lda busy                ; edellinen piirto kesken: tämä kehys jää piirtämättä (musiikki ei koskaan)
        bne _out
        inc busy
        cli
        lda DFRAME
        sec
        sbc t0
        sta t
        lda DFRAME+1
        sbc t0+1
        sta t+1
        jsr frame
        lda #GUARD >> 8         ; (hold_hook: tilan kopion kehyksellä pienempi)
        sta glimit
        sei
        dec busy
_out    pla
        sta $01
        pla
        tay
        pla
        tax
        pla
        rti


; ---------------------------------------------------------------- LV4: biisi levynvaihdon ajaksi
; Sama tahti soi silmukkana ja jatkuu samasta kohdasta. Seuraavan tahdin alussa (biisin kehys
; DFRAME + lv_song jaollinen LOOP_N:llä) soittimen tila talteen RAMiin I/O:n alle, ja tahdin lopussa tila takaisin ja
; kello (DFRAME, ruudun t0) tahdin verran taaksepäin. Kun levy on tunnistettu, silmukka loppuu tahdin lopussa ja biisi
; jatkuu tahdin alusta, joten vaihdon jälkeinen aikajana ei riipu vaihdon kestosta eikä aseman nopeudesta (spritetin
; kerneli soittaa biisiä kiinteästä kohdasta T). Kellon biisin kohta on joka kehys soitettu kohta (ääni).
        .section hold
LOOP_N  = 120                   ; tahti (4 iskua)
SNAP    = $d000                 ; soittimen tila $d000-$d410: puskuri 3 sivua, nollasivu MUSIC_ZP ja binäärin muuttuvat
SNAPPG  = (MUSIC_BUF, MUSIC_BUF + $100, MUSIC_BUF + $200, MUSIC_MUT_WIN)   ; tavut (music.inc: music.py mut soittaa
SNAPZP  = SNAP + len(SNAPPG) * $100     ; koko biisin luupin yli: 44 t, +$189 ja +$25f..+$315)
SNAPB   = MUSIC_MUT_BYTE
LOOP_CYC = 11392                ; tilan kopio (sykliä, +128 MUSIC_MUT_WINin sivunylityksille): levyn piirron aikavartija pienemmällä rajalla sillä kehyksellä
after   txa                     ; odottaa X kehystä (sirq:n laskuri; DFRAME palaa silmukassa taaksepäin)
        clc
        adc tick
-       cmp tick
        bne -
        rts

hold_hook                       ; sirq: tahdin silmukka (lmode), sitten soitin ja kello (FRAME_HOOK)
        inc tick
        lda lmode
        beq _play
        cmp #2
        bcs _loop
_wait   lda DFRAME              ; 1: tahdin alussa (bd) tila talteen ennen sen ensimmäistä soittoa
        cmp bd
        lda DFRAME+1
        sbc bd+1
        bcc _play
        lda DFRAME
        eor bd
        beq +
        lda bd                  ; kello ohitti alun (sirq vasta hold_initin jälkeen, ku_fh:n kiinniotto): seuraava
        adc #LOOP_N - 1         ; tahti (C = 1)
        sta bd
        bcc _play
        inc bd+1
        bcs _play
+
        ldy #$34
        sty $01
        ldx #0
-       .for i := 0, i < len(SNAPPG), i += 1
        lda SNAPPG[i],x
        sta SNAP + i * $100,x
        .endfor
        inx
        bne -
        ldx #15
-       lda MUSIC_ZP,x
        sta SNAPZP,x
        dex
        bpl -
        lda SNAPB
        sta SNAPZP + 16
        lda #LOOP_N
        sta lwait
        inc lmode
        bne _io
_loop   dec lwait               ; 2: tahdin lopussa tila takaisin, kello tahdin verran taaksepäin (lend: silmukka loppuu)
        bne _play
        lda #LOOP_N
        sta lwait
        ldy #$34
        sty $01
        ldx #0
-       .for i := 0, i < len(SNAPPG), i += 1
        lda SNAP + i * $100,x
        sta SNAPPG[i],x
        .endfor
        inx
        bne -
        ldx #15
-       lda SNAPZP,x
        sta MUSIC_ZP,x
        dex
        bpl -
        lda SNAPZP + 16
        sta SNAPB
        lda DFRAME              ; DFRAME ja t0 miinus LOOP_N
        sec
        sbc #LOOP_N
        sta DFRAME
        bcs +
        dec DFRAME+1
+       lda t0
        sec
        sbc #LOOP_N
        sta t0
        bcs +
        dec t0+1
+       lda lend
        beq _io
        lda #0
        sta lmode
_io     lda #(GUARD - LOOP_CYC) >> 8
        sta glimit
        lda #$35
        sta $01
_play   jmp FRAME_HOOK

hold_end                        ; levy tunnistettu (pääsäie): silmukan loppuun, biisi jatkuu tahdin alusta
        lda lmode
        cmp #2
        bcs +
        lda #0                  ; tahti ei vielä alkanut: biisi soi jo yhtenäisenä
        sta lmode
        rts
+       inc lend
-       lda lmode
        bne -
        rts

lmode   .byte 0                 ; 0 soi, 1 odottaa tahdin alkua (bd), 2 silmukka
lend    .byte 0                 ; 1: silmukka loppuu seuraavan tahdin lopussa
lwait   .byte 0                 ; kehyksiä tahdin loppuun
tick    .byte 0                 ; sirq:n kutsut (after)
bd      .word 0                 ; tahdin alku DFRAMEna
lv_song .word 0                 ; kokoa.py: rungon ku_song (biisin kehys - DFRAME) ennen lv_swapia
        .if * < $5ffd           ; vähintään 253 tavua: levy.py tallentaa raakana kaksi lohkoa (Krill ei lataa yhden
        .fill $5ffd - *, 0      ; lohkon tiedostoa oikein)
        .endif
        .send hold

SIG_LEN = 16
id_names .word n_puolib, n_levy2, n_levy2b, n_levy3, n_levy3b
id_sigs  .word s_puolib, s_levy2, s_levy2b, s_levy3, s_levy3b
n_puolib .text "puoli b", 0     ; levy 1 puoli B (kaansi.py: puolib.prg)
n_levy2  .text "levy 2", 0      ; seuraavat levyt: tunnistetiedostot tehdään, kun levyjä on enemmän
n_levy2b .text "levy 2 b", 0
n_levy3  .text "levy 3", 0
n_levy3b .text "levy 3 b", 0
s_puolib .text "simlohja puoli b"
s_levy2  .text "simlohja levy 2 "
s_levy2b .text "simlohja levy2 b"
s_levy3  .text "simlohja levy 3 "
s_levy3b .text "simlohja levy3 b"

show    sta $fffe               ; A/X = IRQ: näyttö päälle (pankki 1, MC-bittikartta), rivin 250 IRQ, cli
        stx $ffff
        lda #0
        sta $d020
        sta $d015
        sta $d021
        lda #2                  ; VIC-pankki 1 (Krill: $dd00:aan vain 0-3)
        sta $dd00
        lda #$18                ; ruutu $4400, bittikartta $6000
        sta $d018
        sta $d016               ; MC, 40 saraketta
        lda #RES_IRQ_LINE
        sta $d012
        lda #$3b
        sta $d011
        lda #1
        sta $d01a
        sta $d019
        cli
        rts

lirq    pha                     ; rivi 250: musiikki ja kello, tekstin kiilto
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
        jsr glint_step
        pla
        sta $01
        pla
        tay
        pla
        tax
        pla
        rti

glint_step
        lda tc0                 ; tc0 = 0: ei tekstiä vielä (lv_init0), kiillon sarakkeet eivät ole voimassa
        beq _r
        inc glint
        lda tc1                 ; Y = 2 x - glint
        asl a
        sec
        sbc glint
        tay
        ldx tc1
-       tya                     ; gl_tab toistuu 64:n jaksolla
        and #63
        tay
        lda gl_tab,y
        sta $d800 + TEXT_ROW * 40,x
        sta $d800 + TEXT_ROW * 40 + 40,x
        dey
        dey
        dex
        cpx tc0
        bcs -
_r      rts


; ---------------------------------------------------------------- asento kehyksestä t: th, tx, tz, hidden

pose    lda t                   ; vaihto var = t / PER, f = t mod PER
        sta f
        lda t+1
        sta f+1
        ldx #0
-       lda f
        sec
        sbc #<PER
        tay
        lda f+1
        sbc #>PER
        bcc +
        sta f+1
        sty f
        inx
        bne -
+       lda fixed               ; levynvaihto: ruutu pysyy samassa vaihdossa, animaatio kiertää
        beq +
        ldx var
+       cpx #NVAIHTO
        bcc +
        ldx #NVAIHTO - 1
+       cpx var
        beq +
        stx var                 ; uusi vaihto: teksti vaihtuu kahdeksassa kehyksessä, levy taas valkotarrainen
        lda #0
        sta tcopy
        sta disk
+       lda #0
        sta tx
        sta tz
        sta hidden
        lda f                   ; heilunta: TH0 + 4 sin(4 f) / 127, levy ei ole koskaan paikallaan
        asl a
        asl a
        tax
        lda sintab,x
        cmp #$80
        ror a
        cmp #$80
        ror a
        cmp #$80
        ror a
        cmp #$80
        ror a
        cmp #$80
        ror a
        clc
        adc #TH0
        sta th
        ldx var
        lda vaihto_anim,x
        bne vaihto
        lda f                   ; kääntö: 90 lepoa, 60 kääntöä, puoli vaihtuu joka jakso (PER = 2 FLIP)
        sec
        sbc #FLIP
        tay
        lda f+1
        sbc #0
        ldx #0
        lda f
        bcc +
        tya
        inx
+       cmp #90
        bcc +
        sbc #90                 ; 0..59 -> 0..128
        tay
        lda ease60,y
        lsr a
        clc
        adc th
        sta th
+       txa
        lsr a
        bcc +
        lda th
        eor #$80                ; pariton jakso: toinen puoli ylöspäin
        sta th
+       rts

vaihto  lda f                   ; 0-59 lepo, 60-129 vanha poistuu, 130-149 tyhjä, 150-219 uusi tulee, 220- lepo
        cmp #60
        bcs +
        lda #0                  ; jakson alussa taas vanha (valkoinen) levy (levynvaihdossa animaatio kiertää)
        sta disk
        rts
+       cmp #130
        bcs +
        sbc #60 - 1             ; C = 0: 0..69
        tay
        lda ease70,y
        jsr away
        lda tx                  ; vanha vasemmalle
        eor #$ff
        clc
        adc #1
        sta tx
        jmp _turn               ; ja kääntyy syrjittäin
+       cmp #150
        bcs +
        inc hidden
        cmp #140
        bcc _r
        lda #1                  ; uusi levy: keltainen tarra
        sta disk
_r      rts
+       cmp #220
        bcs _r
        eor #$ff                ; 150..219 -> 69..0
        clc
        adc #220
        tay
        lda ease70,y
        jsr away                ; uusi oikealta syrjittäin, kääntyy lepoon
_turn   lda e
        lsr a
        clc
        adc th
        sta th
        rts

away    sta e                   ; A = ease 0..255: tz = e / 4 + e / 16, tx = e / 8
        lsr a
        lsr a
        sta tz
        lsr a
        lsr a
        clc
        adc tz
        sta tz
        lda e
        lsr a
        lsr a
        lsr a
        sta tx
        rts

; ---------------------------------------------------------------- värit: tarra (%11, värimuisti) valoisuuden mukaan

shade                           ; koko alue heti (alussa)
        jsr lab_col
        sta lcol
        ldx #NCROW - 1
-       jsr crow
        dex
        bpl -
        lda #0
        sta pend
        rts

shade_step                      ; väri muuttui: yksi merkkirivi kehyksessä (13 kehystä)
        jsr lab_col
        cmp lcol
        beq +
        sta lcol
        lda #NCROW
        sta pend
+       ldx pend
        beq +
        dex
        stx pend
        jmp crow
+       rts

lab_col ldx lvl                 ; A = tarran väri (levy 0 valkoinen, uusi levy keltainen)
        lda disk
        beq +
        lda lit_lab2,x
        rts
+       lda lit_lab,x
        rts

crow    lda crow_lo,x           ; merkkirivi X: värimuisti lcol:ksi alueen leveydeltä
        sta zt
        lda crow_hi,x
        sta zt+1
        lda lcol
        ldy #NC - 1
-       sta (zt),y
        dey
        bpl -
        rts

; ---------------------------------------------------------------- piirto

render  lda th                  ; asento ennallaan: kuva ennallaan (vain tarran väri)
        cmp pth
        bne _new
        lda tx
        cmp ptx
        bne _new
        lda tz
        cmp ptz
        bne _new
        lda hidden
        cmp phid
        bne _new
        lda #0
        sta drawn
        jmp shade_step
_new    lda #1
        sta drawn
        lda th
        sta pth
        lda tx
        sta ptx
        lda tz
        sta ptz
        lda hidden
        sta phid
        beq +
        lda #1                  ; piilossa: uusi alue tyhjä
        sta cl
        lda #0
        sta cr
        jsr shade_step
        jmp stale
+       ldx th
        lda sintab,x
        cmp #$80                ; e = sin / 4 (Z yksikössä 1/32 puolileveyttä)
        ror a
        cmp #$80
        ror a
        sta e
        lda sintab + 64,x
        sta cs
        bpl +                   ; valoisuus min(3, |cos| / 32)
        eor #$ff
        clc
        adc #1
+       lsr a
        lsr a
        lsr a
        lsr a
        lsr a
        cmp #4
        bcc +
        lda #3
+       sta lvl
        jsr shade_step
        lda #ZD                 ; Zl = ZD - e + tz, Zr = ZD + e + tz
        sec
        sbc e
        clc
        adc tz
        sta zl
        lda #ZD
        clc
        adc e
        clc
        adc tz
        sta zr
        ldx zl                  ; reunojen puolikorkeudet (neljännesriveinä)
        lda hh4tab,x
        sta hl
        ldx zr
        lda hh4tab,x
        sta hr
        lda tx                  ; reunojen x (puolikkaina pikseleinä alueessa): CX2 + 2 tx +- cos r2[Z] / 256
        asl a
        clc
        adc #CX2
        sta base
        ldx zr
        lda cs
        jsr cmulz
        clc
        adc base
        sta xr2
        ldx zl
        lda cs
        eor #$ff
        clc
        adc #1
        jsr cmulz
        clc
        adc base
        sta xl2
        lda #0
        sta side
        lda xr2
        cmp xl2
        bcs +
        inc side                ; takapuoli: reunat vaihtavat paikkaa
        ldx xl2
        sta xl2
        stx xr2
        ldx hl
        lda hr
        sta hl
        stx hr
+       lda xr2                 ; vähintään yksi pikseli
        sec
        sbc xl2
        cmp #2
        bcs +
        lda xl2
        adc #2
        sta xr2
        lda #2
+       sta w2
        lda xl2
        lsr a
        sta xl
        lsr a
        lsr a
        sta cl
        lda xr2
        lsr a
        sta xr
        sec
        sbc xl
        sta w
        lda xr
        sec
        sbc #1
        lsr a
        lsr a
        sta cr
        lda #0                  ; k = pienempi / suurempi korkeus (6 bittiä), peili kun vasen on lähempänä
        sta mir
        lda hl
        ldx hr
        cmp hr
        bcc +
        beq +
        inc mir
        lda hr
        ldx hl
+       stx mx
        ldy #6
        ldx #0
        stx q6
-       asl a
        bcs +
        cmp mx
        bcc ++
+       sbc mx
        sec
+       rol q6
        dey
        bne -
        lda q6
        sec
        sbc #32
        bcs +
        lda #0
+       cmp #NK
        bcc +
        lda #NK - 1
+       lsr a                   ; zu = ut + k * 128
        sta zu+1
        lda #0
        ror a
        sta zu
        lda zu+1
        clc
        adc #>ut
        sta zu+1
        lda #0                  ; dh = (hr - hl) * 256 / w2 (neljännesriviä puolikasta pikseliä kohti, 8.8)
        sta nlo
        lda hr
        sec
        sbc hl
        sta nhi
        lda w2
        jsr sdivw
        lda q
        asl a
        sta dh2
        lda q+1
        rol a
        sta dh2+1
        lda dh2
        asl a
        sta dh8
        lda dh2+1
        rol a
        sta dh8+1
        asl dh8
        rol dh8+1
        lda q                   ; H (8.8) sarakkeen cl pikselissä 0: hl * 256 + dh * (8 cl + 1 - xl2), n0 = -6..1
        sta dh
        lda q+1
        sta dh+1
        lda #0
        sta hacc
        lda hl
        sta hacc+1
        lda cl
        asl a
        asl a
        asl a
        sta c8l
        clc
        adc #1
        sec
        sbc xl2
        beq _h0
        bmi _hn
        lda hacc                ; n0 = 1
        clc
        adc dh
        sta hacc
        lda hacc+1
        adc dh+1
        sta hacc+1
        jmp _h0
_hn     tax
-       lda hacc
        sec
        sbc dh
        sta hacc
        lda hacc+1
        sbc dh+1
        sta hacc+1
        inx
        bne -
_h0     lda cr                  ; u sarakkeiden cl+1..cr pikselissä 0 (vain kun välissä on kokonainen sarake)
        sec
        sbc cl
        cmp #2
        bcc _cols
        ldx w2
        lda dt1_lo,x
        sta dt
        lda dt1_hi,x
        sta dt+1
        lda c8l                 ; T = (8 cl + 9 - xl2) * dt, t = min(127, T / 256)
        clc
        adc #9
        sec
        sbc xl2
        tax
        lda #0
        sta tacc
        sta tacc+1
-       lda tacc
        clc
        adc dt
        sta tacc
        lda tacc+1
        adc dt+1
        sta tacc+1
        dex
        bne -
        lda dt                  ; askel 8 dt
        sta dt8
        lda dt+1
        asl dt8
        rol a
        asl dt8
        rol a
        asl dt8
        rol a
        sta dt8+1
        ldx cl
        inx
_u      lda tacc+1
        bpl +
        lda #NT - 1
+       ldy mir
        bne +
        tay
        lda (zu),y
        jmp ++
+       eor #NT - 1             ; peili: 160 - U[k][127 - t]
        tay
        lda #160
        sec
        sbc (zu),y
+       sta u4col,x
        lda tacc
        clc
        adc dt8
        sta tacc
        lda tacc+1
        adc dt8+1
        sta tacc+1
        inx
        cpx cr
        beq _u
        bcc _u
_cols   lda side                ; välisarakkeiden joukkojen alut + 3 tasoille 40, 20, 10 (puoli) ja 5 (yhteinen)
        asl a
        adc side
        tax
        lda qbase,x
        adc #3
        sta qb3
        lda qbase + 1,x
        adc #3
        sta qb3 + 1
        lda qbase + 2,x
        adc #3
        sta qb3 + 2
        lda qbase + 6
        adc #3
        sta qb3 + 3
        jsr stale
        lda hacc                ; H sarakkeessa cl (kierto alkaa sarakkeesta cl + rot)
        sta hcl
        lda hacc+1
        sta hcl+1
        lda cr
        sec
        sbc cl
        tax
        inx
        stx ncol
        cmp rot
        bcs +
        lda #0
        sta rot
+       ldx rot
        beq +
-       lda hacc                ; H += rot * 8 dh
        clc
        adc dh8
        sta hacc
        lda hacc+1
        adc dh8+1
        sta hacc+1
        dex
        bne -
+       lda cl
        clc
        adc rot
        sta c
_col    jsr cia                 ; aikavartija: kehyksen työ yli GUARD:n -> loput sarakkeet seuraavassa kehyksessä
        sta d
        lda cyc0
        sec
        sbc d
        tya
        eor #$ff
        adc cyc0+1
        cmp glimit
        bcs _stop
        jsr column
        inc c
        lda c
        cmp cr
        beq +
        bcc +
        lda cl                  ; kierto: takaisin sarakkeeseen cl
        sta c
        lda hcl
        sta hacc
        lda hcl+1
        sta hacc+1
+       dec ncol
        bne _col
        rts
_stop   lda c
        sec
        sbc cl
        sta rot
        lda #$ff                ; seuraava kehys piirtää, vaikka asento ei muuttuisi
        sta pth
        rts

stale   ldx ocl                 ; viime kehyksen sarakkeet uuden alueen ulkopuolella taustaksi
-       cpx ocr
        beq +
        bcs _sd
+       cpx cl
        bcc +
        cpx cr
        beq _sn
        bcc _sn
+       stx c
        jsr clearcol
        ldx c
_sn     inx
        jmp -
_sd     lda cl
        sta ocl
        lda cr
        sta ocr
        rts

column                          ; sarake c: pintasarake, pikselien yläreunat, puolikorkeus; piirto jos muuttui
        ldx c
        txa
        asl a
        asl a
        sta px
        asl a
        sta c8
        cpx cl
        beq _ecol
        cpx cr
        beq _ecol
        lda u4col + 1,x         ; välisarake: taso du:sta, q = u >> taso (0..nw-4), joukon alku qb3 (kehyksittäin)
        sec
        sbc u4col,x
        cmp #24
        bcs _v1
        lda u4col,x
        lsr a
        lsr a
        cmp #37
        bcc +
        lda #36
+       clc
        adc qb3
        jmp _vq
_v1     cmp #48
        bcs _v2
        lda u4col,x
        lsr a
        lsr a
        lsr a
        cmp #17
        bcc +
        lda #16
+       clc
        adc qb3 + 1
        jmp _vq
_v2     cmp #96
        bcs _v3
        lda u4col,x
        lsr a
        lsr a
        lsr a
        lsr a
        cmp #7
        bcc +
        lda #6
+       clc
        adc qb3 + 2
        jmp _vq
_v3     lda u4col,x
        lsr a
        lsr a
        lsr a
        lsr a
        lsr a
        cmp #2
        bcc +
        lda #1
+       clc
        adc qb3 + 3
_vq     tax
        lda qcol_lo,x
        sta nlo
        lda qcol_hi,x
        sta nhq
        jmp _ipx
_ecol   lda cl                  ; reunasarake
        cmp cr
        bne _multi
        lda #11                 ; koko levy yhdessä sarakkeessa: taso w (1..4)
        sec
        sbc w
        sta set
        jmp _left
_multi  lda cr
        sec
        sbc cl
        cmp #1
        bne _wide
        lda w                   ; kaksi saraketta: taso min(w, 5)
        cmp #5
        bcc +
        lda #5
+       sta nwv
        eor #$ff
        sec
        adc #11
        sta set
        jmp _edge
_wide   ldx c                   ; mip-taso u:n muutoksesta: du = u4[cc + 1] - u4[cc], cc välillä cl+1..cr-1
        cpx cl
        bne +
        inx
+       cpx cr
        bne +
        dex
+       lda u4col + 1,x
        sec
        sbc u4col,x
        ldx #0
        cmp #24
        bcc +
        inx
        cmp #48
        bcc +
        inx
        cmp #96
        bcc +
        inx
+       lda lev_nw,x
        sta nwv
        lda lev_sh,x
        sta shift
        cpx #3
        bne +
        lda #6                  ; taso 5 yhteinen
        bne ++
+       lda side
        asl a
        adc side
        sta set
        txa
        adc set
+       sta set
_edge   ldx c
        cpx cl
        beq _left
        cpx cr
        bne _mid
        lda xr                  ; oikea reuna: viimeinen pikseli = tason viimeinen sarake
        sbc #1                  ; C = 1 (cpx cr)
        and #3
        eor #$ff
        sec
        adc nwv
        sec
        sbc #1
        jmp _q
_left   lda xl                  ; vasen reuna: ensimmäinen pikseli = tason sarake 0
        and #3
        eor #$ff
        clc
        adc #1
        jmp _q
_mid    lda u4col,x             ; välissä: q = u >> taso, 0..nw-4
        ldy shift
-       lsr a
        dey
        bne -
        sta e
        lda nwv
        sec
        sbc #4
        cmp e
        bcc _q
        lda e
_q      clc
        adc #3
        ldx set
        clc
        adc qbase,x
        tax
        lda qcol_lo,x
        sta nlo
        lda qcol_hi,x
        sta nhq
        jmp _epx
_ipx    ldx hacc+1              ; välisarake: kaikki pikselit levyllä, yläreunat monotoniset
        lda toptab,x
        sta tops
        lda hacc
        clc
        adc dh2
        tay
        lda hacc+1
        adc dh2+1
        tax
        lda toptab,x
        sta tops+1
        tya
        clc
        adc dh2
        tay
        txa
        adc dh2+1
        tax
        lda toptab,x
        sta tops+2
        tya
        clc
        adc dh2
        txa
        adc dh2+1
        tax
        lda toptab,x
        sta tops+3
        lda hacc
        clc
        adc dh8
        sta hacc
        lda hacc+1
        adc dh8+1
        sta hacc+1
        lda tops
        ldx tops+3
        cmp tops+3
        bcc +
        stx tmin
        sta tmax
        jmp _tops
+       sta tmin
        stx tmax
        jmp _tops
_epx    lda #CY                 ; reunasarake: pikselit levyn ulkopuolella CY, min ja max levyn pikseleistä
        sta tmin
        lda #0
        sta tmax
        ldy #0
_px     lda px
        cmp xl
        bcc _po
        cmp xr
        bcs _po
        ldx hacc+1
        lda toptab,x
        cmp #CY
        bcs _po
        sta tops,y
        cmp tmin
        bcs +
        sta tmin
+       cmp tmax
        bcc _pn
        sta tmax
        bcs _pn
_po     lda #CY
        sta tops,y
_pn     lda hacc
        clc
        adc dh2
        sta hacc
        lda hacc+1
        adc dh2+1
        sta hacc+1
        inc px
        iny
        cpy #4
        bne _px
_tops   lda tmin
        cmp #CY
        bcc +
        ldx c                   ; ei pikseleitä: tyhjä
        jmp clearcol
+       lda #2 * CY + 1         ; puolikorkeus (2 CY + 1 - min - max) / 2, vähintään HMIN
        sec
        sbc tmin
        sec
        sbc tmax
        lsr a
        cmp #HMIN
        bcs +
        lda #HMIN
+       sta hhc
        sec
        sbc #HMIN
        sta hx
        ldx c                   ; sama kuin viime kehyksessä: ei piirretä
        lda nlo
        cmp st_lo,x
        bne _chg
        lda nhq
        cmp st_hi,x
        bne _chg
        lda hx
        cmp st_hx,x
        bne _chg
        lda tops
        cmp st_t0,x
        bne _chg
        lda tops + 1
        cmp st_t1,x
        bne _chg
        lda tops + 2
        cmp st_t2,x
        bne _chg
        lda tops + 3
        cmp st_t3,x
        bne _chg
        rts
_chg    lda tmin                ; rivit tmin..NR-1-tmin aukikirjoitetulla koodilla
        sta lo
        lda nlo
        sta zq
        lda nhq
        sta zq+1
        lda hx
        jsr runsc
        ldx c                   ; vanhat rivit uuden yläreunan yläpuolella taustaksi
        ldy st_otop,x
        cpy tmin
        bcs +
        jsr bgrows
+       jsr maskrows            ; reunarivit tmin..tmax-1 pikseleittäin
        jsr edgebg
        ldx c
        lda nlo
        sta st_lo,x
        lda nhq
        sta st_hi,x
        lda hx
        sta st_hx,x
        lda tops
        sta st_t0,x
        lda tops + 1
        sta st_t1,x
        lda tops + 2
        sta st_t2,x
        lda tops + 3
        sta st_t3,x
        lda tmin
        sta st_otop,x
        rts

clearcol                        ; X = c: sarakkeen vanhat rivit taustaksi
        lda st_hi,x
        beq +
        lda st_otop,x
        sta lo
        lda #0
        sta st_hi,x
        lda #CY
        sta st_otop,x
        lda #<bgcol
        sta zq
        lda #>bgcol
        sta zq+1
        lda c
        asl a
        asl a
        asl a
        sta c8
        lda #0
        jsr runsc
        ldx lo
        lda #$ff
        jmp bgfix
+       rts

runsc                           ; sarakkeen c rivit lo..NR-1-lo aukikirjoitetulla koodilla, A = v-kartan indeksi
        sta hxv
        lda c
        sec
        sbc #FC0
        cmp #NF
        bcs _gen
        tay
        ldx lo
        lda r8lo,x
        clc
        adc ft_lo,y
        sta _j1 + 1
        lda r8hi,x
        adc ft_hi,y
        sta _j1 + 2
        lda r8lo,x
        clc
        adc fb_lo,y
        sta _j2 + 1
        lda r8hi,x
        adc fb_hi,y
        sta _j2 + 2
        ldx hxv
_j1     jsr $ffff
_j2     jmp $ffff
_gen    ldx lo
        lda r11lo,x
        clc
        adc #<gsc
        sta _g1 + 1
        lda r11hi,x
        adc #>gsc
        sta _g1 + 2
        lda r11lo,x
        clc
        adc #<(gsc + CY * 11 + 1)
        sta _g2 + 1
        lda r11hi,x
        adc #>(gsc + CY * 11 + 1)
        sta _g2 + 2
        lda hxv
        sta zhh
        ldx c8
_g1     jsr $ffff
_g2     jmp $ffff

bgrows                          ; Y = ensimmäinen rivi: rivit Y..tmin-1 (bgr) ja peilirivit ($55) taustaksi
        tya
        tax
        ldy c8
-       lda rowlo,x
        sta zt
        lda rowhi,x
        sta zt+1
        lda bgr,x
        sta (zt),y
        lda rowlo2,x
        sta zt
        lda rowhi2,x
        sta zt+1
        lda #$55
        sta (zt),y
        inx
        cpx tmin
        bcc -
        rts

maskrows                        ; rivit tmin..tmax-1 ja peilirivit: pikselit tops[i] <= r näkyvät, muut taustaksi
        ldx tmin
        ldy c8
-       cpx tmax
        bcs _x
        lda #0
        cpx tops
        bcc +
        ora #$c0
+       cpx tops + 1
        bcc +
        ora #$30
+       cpx tops + 2
        bcc +
        ora #$0c
+       cpx tops + 3
        bcc +
        ora #$03
+       sta m
        eor #$ff
        sta bgm
        and #$55
        sta bgm2
        lda bgm
        and bgr,x
        sta bgm
        lda rowlo,x
        sta zt
        lda rowhi,x
        sta zt+1
        lda (zt),y
        and m
        ora bgm
        sta (zt),y
        lda rowlo2,x
        sta zt
        lda rowhi2,x
        sta zt+1
        lda (zt),y
        and m
        ora bgm2
        sta (zt),y
        inx
        bne -
_x      rts

edgebg                          ; reunasarake: levyn ulkopuolen pikselit (tops = CY) riveillä tmax..TR1 taustaksi
        lda c                   ; (pintasarake antaa niille %01; taustan siirtymärivit TR0..TR1 ovat yläpuoliskolla)
        cmp cl
        beq +
        cmp cr
        bne _x
+       lda #0
        ldx tops
        cpx #CY
        bcc +
        ora #$c0
+       ldx tops + 1
        cpx #CY
        bcc +
        ora #$30
+       ldx tops + 2
        cpx #CY
        bcc +
        ora #$0c
+       ldx tops + 3
        cpx #CY
        bcc +
        ora #$03
+       cmp #0
        beq _x
        ldx tmax
        jmp bgfix
_x      rts

bgfix                           ; A = pikselimaski, X = ensimmäinen rivi: maskin pikselit taustaksi riveillä X..TR1
        eor #$ff
        sta nom
        cpx #TR0
        bcs +
        ldx #TR0
+       cpx #TR1 + 1
        bcs _x
        lda bf_lo - TR0,x
        sta _j + 1
        lda bf_hi - TR0,x
        sta _j + 2
        ldx c8
_j      jmp $ffff
_x      rts
bfrows                          ; rivi r: ((tavu ^ tausta) & ~maski) ^ tausta (16 sykliä)
        .for r := TR0, r <= TR1, r += 1
        lda BMP + ((R0 + r) / 8) * 320 + (R0 + r) % 8 + C0 * 8,x
        eor #BGR[r]
        and nom
        eor #BGR[r]
        sta BMP + ((R0 + r) / 8) * 320 + (R0 + r) % 8 + C0 * 8,x
        .next
        rts
bf_lo   .for r := TR0, r <= TR1, r += 1
        .byte <(bfrows + (r - TR0) * 12)
        .next
bf_hi   .for r := TR0, r <= TR1, r += 1
        .byte >(bfrows + (r - TR0) * 12)
        .next

; ---------------------------------------------------------------- lv_init: pintasarakkeet ja v-kartta

gen_quads                       ; joukot ja q:t qaddrs-järjestyksessä: tavu = edellinen << 2 | uusi pikseli (lähde srcq)
        lda #0
        sta gci
        sta gset
_set    ldx gset
        lda set_nw,x
        sta gnw
        clc
        adc #3
        sta gcnt
        lda set_uoff,x
        sta guo
        lda set_side,x
        sta gside
        lda #<bgcol             ; ennen q = -3: kaikki taustaa
        sta gprev
        lda #>bgcol
        sta gprev+1
        lda #0
        sta gm
_col    ldx gci
        lda qcol_lo,x
        sta gdst
        lda qcol_hi,x
        sta gdst+1
        ldy #VB
        lda #$55
        sta (gdst),y
        lda gm                  ; uusi pikseli: tason sarake gm (tai tausta)
        cmp gnw
        bcs _bg
        adc guo
        tax
        lda set_u,x
        sta gu
        lsr a
        lsr a
        ldx gside
        beq +
        clc
        adc #10
+       tax
        lda srcj_lo,x
        sta gsrc
        lda srcj_hi,x
        sta gsrc+1
        lda gu
        and #3
        beq _l0
        cmp #2
        bcc _l1
        beq _l2
        ldy #VB - 1
-       lda (gsrc),y            ; pikseli 3: bitit 1-0
        and #3
        sta gtmp
        lda (gprev),y
        asl a
        asl a
        ora gtmp
        sta (gdst),y
        dey
        bpl -
        bmi _done
_l0     ldy #VB - 1
-       lda (gsrc),y            ; pikseli 0: bitit 7-6
        rol a
        rol a
        rol a
        and #3
        sta gtmp
        lda (gprev),y
        asl a
        asl a
        ora gtmp
        sta (gdst),y
        dey
        bpl -
        bmi _done
_l1     ldy #VB - 1
-       lda (gsrc),y            ; pikseli 1: bitit 5-4
        lsr a
        lsr a
        lsr a
        lsr a
        and #3
        sta gtmp
        lda (gprev),y
        asl a
        asl a
        ora gtmp
        sta (gdst),y
        dey
        bpl -
        bmi _done
_l2     ldy #VB - 1
-       lda (gsrc),y            ; pikseli 2: bitit 3-2
        lsr a
        lsr a
        and #3
        sta gtmp
        lda (gprev),y
        asl a
        asl a
        ora gtmp
        sta (gdst),y
        dey
        bpl -
        bmi _done
_bg     ldy #VB - 1
-       lda (gprev),y
        asl a
        asl a
        ora #1
        sta (gdst),y
        dey
        bpl -
_done   lda gdst
        sta gprev
        lda gdst+1
        sta gprev+1
        inc gci
        inc gm
        dec gcnt
        beq +
        jmp _col
+       inc gset
        lda gset
        cmp #NSETS
        beq +
        jmp _set
+       rts

gen_vm                          ; v-kartta VM[r][h - HMIN] = 40 + (2 r - 103) * 20 // h (0..79), reunan yli VB
        lda #0
        sta gh
_h      lda gh
        clc
        adc #HMIN
        sta gnw                 ; h
        asl a
        clc
        adc #2 * MARGIN
        sta glim                ; |2 r - 103| < 2 h + 2 MARGIN
        lda #<(VM + CY * NH)    ; alapuolisko r = CY..NR-1: N = 20, 60, ...
        clc
        adc gh
        sta gdst
        lda #>(VM + CY * NH)
        adc #0
        sta gdst+1
        lda #20
        ldx #40
-       cmp gnw
        bcc +
        sbc gnw
        inx
        bne -
+       sta grem
        stx gv
        lda #1
        sta gd
        lda #NR - CY
        sta gcnt
_lo     lda gv
        cmp #VB
        bcc +
        lda #VB - 1
+       ldx gd
        cpx glim
        bcc +
        lda #VB
+       ldy #0
        sta (gdst),y
        lda gdst
        clc
        adc #NH
        sta gdst
        bcc +
        inc gdst+1
+       inc gd
        inc gd
        lda grem
        clc
        adc #40
-       cmp gnw
        bcc +
        sbc gnw
        inc gv
        bne -
+       sta grem
        dec gcnt
        bne _lo
        lda #<(VM + (CY - 1) * NH)      ; yläpuolisko r = CY-1..0: N = -20, -60, ...
        clc
        adc gh
        sta gdst
        lda #>(VM + (CY - 1) * NH)
        adc #0
        sta gdst+1
        lda #0                  ; rem = -20 + ceil(20 / h) h, v = 40 - ceil(20 / h)
        ldx #40
-       dex
        clc
        adc gnw
        cmp #20
        bcc -
        sbc #20
        sta grem
        stx gv
        lda #1
        sta gd
        lda #CY
        sta gcnt
_up     lda gv
        bpl +
        lda #0
+       ldx gd
        cpx glim
        bcc +
        lda #VB
+       ldy #0
        sta (gdst),y
        lda gdst
        sec
        sbc #NH
        sta gdst
        bcs +
        dec gdst+1
+       inc gd
        inc gd
        lda grem
        sec
        sbc #40
-       bpl +
        clc
        adc gnw
        dec gv
        cmp #0
        jmp -
+       sta grem
        dec gcnt
        bne _up
        inc gh
        lda gh
        cmp #NH
        beq +
        jmp _h
+       rts

; ---------------------------------------------------------------- aritmetiikka

cmulz   sta sgn                 ; A = (A etumerkillinen) * r2tab[X] / 256 (pyöristys kohti nollaa)
        lda r2tab,x
        sta ml
        lda sgn
        bpl +
        eor #$ff
        clc
        adc #1
+       sta kk
        lda #0
        ldy #8
-       lsr kk
        bcc +
        clc
        adc ml
+       ror a
        dey
        bne -
        bit sgn
        bpl +
        eor #$ff
        clc
        adc #1
+       rts

sdivw   sta d                   ; q = (nhi:nlo etumerkillinen) / A (kohti nollaa)
        lda nhi
        sta sgn
        bpl +
        lda #0
        sec
        sbc nlo
        sta nlo
        lda #0
        sbc nhi
        sta nhi
+       lda d
        jsr udiv
        bit sgn
        bpl +
        lda #0
        sec
        sbc q
        sta q
        lda #0
        sbc q+1
        sta q+1
+       rts

udiv    sta d                   ; q = nhi:nlo / A (16 / 8)
        lda #0
        ldx #16
-       asl nlo
        rol nhi
        rol a
        bcs +
        cmp d
        bcc ++
+       sbc d
        inc nlo
+       dex
        bne -
        lda nlo
        sta q
        lda nhi
        sta q+1
        rts

; ---------------------------------------------------------------- teksti

text_step                       ; kahdeksasosa tekstistä (80 tavua puolitavuista) kehyksessä, kunnes tcopy = 8
        lda tcopy
        cmp #8
        bcs _x
        inc tcopy
        tax
        jsr text_part
        jmp text_cols
_x      rts

text_all                        ; koko teksti heti (var: vaihdon teksti), sitten kiilto. lv_swap ajaa tämän pääsäikeessä
        lda #8                  ; sirq:n ollessa päällä (teksti ei saa repeytyä): tcopy 8:ssa, joten sirq:n
        sta tcopy               ; frame ei piirrä tekstiä samaan aikaan, ja text_part käyttää omia nollasivutavujaan
        ldx #0                  ; (tzt, tzu, te, tsg), joita levyn piirto ($f0-$f7, e, sgn) ei kirjoita
-       stx tpart
        jsr text_part
        ldx tpart
        inx
        cpx #8
        bcc -
text_cols                       ; kiillon sarakkeet: tekstin ensimmäinen ja viimeinen
        ldx var
        lda tcol_lo,x
        sta tzt
        lda tcol_hi,x
        sta tzt+1
        ldy #0
        lda (tzt),y
        sta tc0
        iny
        lda (tzt),y
        sta tc1
        rts

text_part                       ; X = osa 0..7: tekstin var tavut 40 X.. -> bittikartan tekstirivien tavut 80 X..
        ldy var
        lda text_lo,y
        sta tzt
        lda text_hi,y
        sta tzt+1
        lda q40,x
        clc
        adc tzt
        sta tzt
        lda q40h,x
        adc tzt+1
        sta tzt+1
        lda q80,x
        clc
        adc #<(BMP + TEXT_ROW * 320)
        sta tzu
        lda q80h,x
        adc #>(BMP + TEXT_ROW * 320)
        sta tzu+1
        ldy #0
-       lda (tzt),y             ; tavu i -> kohteet 2 i (ylempi puolitavu) ja 2 i + 1
        sta te
        sty tsg
        tya
        asl a
        tay
        lda te
        lsr a
        lsr a
        lsr a
        lsr a
        tax
        lda nibmc,x
        sta (tzu),y
        iny
        lda te
        and #$0f
        tax
        lda nibmc,x
        sta (tzu),y
        ldy tsg
        iny
        cpy #40
        bne -
        rts

q40     .for i := 0, i < 8, i += 1
        .byte <(i * 40)
        .next
q40h    .for i := 0, i < 8, i += 1
        .byte >(i * 40)
        .next
q80     .for i := 0, i < 8, i += 1
        .byte <(i * 80)
        .next
q80h    .for i := 0, i < 8, i += 1
        .byte >(i * 80)
        .next
nibmc   .for n := 0, n < 16, n += 1     ; puolitavu -> MC-tavu: bitti 3 - i = pikseli i %11, muuten %01
        .byte (n & 8 ? $c0 : $40) | (n & 4 ? $30 : $10) | (n & 2 ? $0c : $04) | (n & 1 ? $03 : $01)
        .next

gl_tab  .fill 40, 1               ; kiilto kulkee tekstin yli
        .byte 15, 15, 12, 12, 11, 11, 12, 12, 15, 15, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1

NCROW = (R0 + NR - 1) / 8 - R0 / 8 + 1
crow_lo .for r := R0 / 8, r <= (R0 + NR - 1) / 8, r += 1
        .byte <($d800 + r * 40 + C0)
        .next
crow_hi .for r := R0 / 8, r <= (R0 + NR - 1) / 8, r += 1
        .byte >($d800 + r * 40 + C0)
        .next
ft_lo   .for j := 0, j < NF, j += 1   ; nopean sarakkeen yläpuolisko ja (takaperin) alapuolisko
        .byte <(fsc0 + j * (8 * NR + 2))
        .next
ft_hi   .for j := 0, j < NF, j += 1
        .byte >(fsc0 + j * (8 * NR + 2))
        .next
fb_lo   .for j := 0, j < NF, j += 1
        .byte <(fsc0 + j * (8 * NR + 2) + 8 * CY + 1)
        .next
fb_hi   .for j := 0, j < NF, j += 1
        .byte >(fsc0 + j * (8 * NR + 2) + 8 * CY + 1)
        .next
rowlo   .for r := 0, r < NR, r += 1        ; alueen rivin r osoite sarakkeessa 0
        .byte <(BMP + ((R0 + r) / 8) * 320 + (R0 + r) % 8 + C0 * 8)
        .next
rowhi   .for r := 0, r < NR, r += 1
        .byte >(BMP + ((R0 + r) / 8) * 320 + (R0 + r) % 8 + C0 * 8)
        .next
rowlo2  .for r := 0, r < NR, r += 1        ; peilirivi NR-1-r
        .byte <(BMP + ((R0 + NR - 1 - r) / 8) * 320 + (R0 + NR - 1 - r) % 8 + C0 * 8)
        .next
rowhi2  .for r := 0, r < NR, r += 1
        .byte >(BMP + ((R0 + NR - 1 - r) / 8) * 320 + (R0 + NR - 1 - r) % 8 + C0 * 8)
        .next
srcj_lo .for i := 0, i < 20, i += 1
        .byte <(srcq + i * VB)
        .next
srcj_hi .for i := 0, i < 20, i += 1
        .byte >(srcq + i * VB)
        .next
toptab  .for h := 0, h < 256, h += 1      ; pikselin yläreuna puolikorkeudesta h (neljännesriveinä): (HH4MAX + 2 - h) / 4
        .byte (HH4MAX + 2 - (h < HH4MAX ? h : HH4MAX)) / 4
        .next
lev_nw  .byte 40, 20, 10, 5
lev_sh  .byte 2, 3, 4, 5
bgcol   .fill VB + 1, $55       ; tyhjä sarake (tausta)

        .include "lv.inc"

t0      .word 0
t       .word 0
f       .word 0
lastf   .byte $ff
var     .byte 0
disk    .byte 0
tcopy   .byte 8
glint   .byte 0
hidden  .byte 0
th      .byte 0
tx      .byte 0
tz      .byte 0
lvl     .byte 0
lcol    .byte 1
pend    .byte 0
fixed   .byte 0
ready   .byte 0                 ; pintasarakkeet generoitu (lv_gen)
ent     .byte 0                 ; esiinkäännön kehyksiä jäljellä
busy    .byte 0
quit    .byte 0                 ; lv_swapin loppu: 1 = sirq pimentää ja vaihtaa IRQ:n, $80 = tehty
tc0     .byte 0
tc1     .byte 39
lv_cyc  .word 0                 ; mittari: viimeisen kehyksen työ sykleinä, suurin, kehyksiä
lv_max  .word 0
lv_n    .byte 0
ocl     .byte 1
ocr     .byte 0
pth     .byte $ff
ptx     .byte 0
ptz     .byte 0
phid    .byte $ff
drawn   .byte 0
rot     .byte 0
glimit  .byte GUARD >> 8

        .virtual $10            ; nollasivu $10-: piirron ja lv_initin työmuuttujat (osien $02-$bf)
cyc0    .word ?
cs      .byte ?
zl      .byte ?
zr      .byte ?
hl      .byte ?
hr      .byte ?
base    .byte ?
xl2     .byte ?
xr2     .byte ?
xl      .byte ?
xr      .byte ?
w2      .byte ?
w       .byte ?
cl      .byte ?
cr      .byte ?
side    .byte ?
mir     .byte ?
mx      .byte ?
q6      .byte ?
dh      .word ?
dh2     .word ?
dh8     .word ?
qb3     .fill 4
hacc    .word ?
hcl     .word ?
ncol    .byte ?
dt      .word ?
dt8     .word ?
tacc    .word ?
c8l     .byte ?
c       .byte ?
c8      .byte ?
px      .byte ?
set     .byte ?
nwv     .byte ?
shift   .byte ?
nlo     .byte ?
nhi     .byte ?
nhq     .byte ?
tops    .fill 4
tmin    .byte ?
tmax    .byte ?
hhc     .byte ?
hx      .byte ?
lo      .byte ?
r1      .byte ?
hxv     .byte ?
sb      .word ?
orig    .byte ?
rr      .byte ?
m       .byte ?
bgm     .byte ?
bgm2    .byte ?
nom     .byte ?
e       .byte ?
d       .byte ?
sgn     .byte ?
q       .word ?
ml      .byte ?
kk      .byte ?
gci     .byte ?
gset    .byte ?
gnw     .byte ?
gcnt    .byte ?
guo     .byte ?
gside   .byte ?
gm      .byte ?
gu      .byte ?
gtmp    .byte ?
gh      .byte ?
glim    .byte ?
grem    .byte ?
gv      .byte ?
gd      .byte ?
tzt     .word ?             ; tekstin piirto (text_part, myös pääsäikeessä sirq:n aikana): vain tekstin omat
tzu     .word ?
te      .byte ?
tsg     .byte ?
tpart   .byte ?
        .cerror * > $c0, "nollasivu yli osien alueen"
        .endv
        .virtual $c240          ; sarakkeiden tila v-kartan perässä ja LV2:n perässä (lv_init alustaa st_hi, st_otop)
st_lo   .fill NC                ; sarakkeen viime kehyksen tila (st_hi 0 = tyhjä)
st_hi   .fill NC
st_hx   .fill NC
st_t0   .fill NC
st_t1   .fill NC
st_t2   .fill NC
        .cerror * > $c300, "tila yli pintasarakkeiden"
        .endv
        .virtual $a900 - 3 * NC - 1     ; LV2:n perässä (hold_init, hold_end)
st_t3   .fill NC
st_otop .fill NC
u4col   .fill NC + 1
        .cerror * > $a900, "tila yli pintasarakkeiden"
        .endv
        .send code
