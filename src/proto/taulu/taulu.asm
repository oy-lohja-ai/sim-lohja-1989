; Kerrontataulu omalla osalevyllä (make part P=tauluN, N = tekstit.yaml:n taulut-kohdan avain):
; sama koodi jokaiselle taululle, teksti ja kesto buildissa (Makefile, tools/gfx/taulu.py). Moduuli
; src/lib/taulu.asm. Integraatiossa taulu liitetään minkä tahansa osan väliin.
;
; Muisti (VIC-pankki 2): spritet $8800 (lohkot 0-3) ja ruutu $8c00 (taulu_init kirjoittaa molemmat, eivät
; tiedostossa), koodi ja taulut $9800, bittikartta $a000: tiedosto $9800-$bf3f, joten koko demossa taulu esiladataan
; kaupungintalon ($9400-$97ff ikkunan kädet, $6000-$87cf pelin merkistöt) aikana. PANKKI = 3 (Makefile, taulu2b: koko
; demossa kuopan ja kylttien välissä, joiden alut esiladataan $1a00-$bfff:ään): spritet $c000, koodi $c100, ruutu
; $cc00, bittikartta $e000 omana tiedostonaan (taulub.asm), koska Krill ei lataa $d000-$dfff:ään.
; MERKKI (Makefile, taulut 1 ja 1b: kaupungintalon edellä, joka tarvitsee koko muistin): sama kuva hires-merkkitilana
; 8 kt:n lohkossa MERKKI: merkistö +$0000, ruutu (merkkikoodit) +$0800, spritet +$0c00, koodi +$0d00; värit
; värimuistissa ja tausta musta. LATAUS = tiedoston osoite: jos eri, taulu_init kopioi lohkon MERKKIin.
; Oma IRQ rivillä 250: FRAME_HOOK ja taulu_kehys (DFRAME = taulun kehys).

        .include "taulu_osa.inc"

        .weak
PANKKI  = 2
MERKKI  = 0
LATAUS  = MERKKI
P3_KOODI = 0                    ; PANKKI 3: koodin latausosoite, jos ei ajoalueella $c100 (taulu_init kopioi), 0 = paikallaan
P3_BITTI = $e000                ; PANKKI 3: bittikartan (taulub.asm) latausosoite
TAULU_DF0 = 0                   ; taulun kehys 0 = DFRAME TAULU_DF0 (taulu 2c kuoppa-kylttien sisällä: osan kehys)
        .endweak
FRAME_HOOK = $0408
R_IRQ_ON = $041b                ; runko.inc: rungon IRQ rivillä 250 (kopion ajan, taulu_go kopiotilassa)
R_TICK  = $041e                 ; runko.inc: jmp-vektori, jota rungon IRQ kutsuu kerran kehyksessä
R_TICK_RTS = $0421              ; runko.inc: rts (R_TICK:n oletus)
TAULU_JALKI = 1                 ; taulu_jalki: siirtymä seuraavaan (src/runko/siirtymat.json "filmi")
DFRAME  = $d0
TZP     = $f0                   ; $f0-$fd: edellinen kohtaus pyörii vielä taulu_initin aikana (jatkuva siirtymä), ja
                                ; vuosi ($90-), kaupungintalon peli ($02-$28) ja ikkuna ($30-$8f) käyttävät alempia
IRQ_LINE = 250
        .if MERKKI
VB      = MERKKI & $c000
TAULU_MERKKI = 1
TAULU_TYHJAA_ERIKSEEN = 1       ; värimuisti taulu_go:ssa (edellinen kohtaus käyttää sitä taulu_initin aikana)
TAULU_SCREEN = MERKKI + $0800
TAULU_SPRMEM = MERKKI + $0c00
D018    = ((TAULU_SCREEN & $3fff) >> 6) | ((MERKKI & $3fff) >> 10)
        .else
VB      = PANKKI * $4000
TAULU_SCREEN = VB + $0c00
TAULU_SPRMEM = PANKKI == 2 ? VB + $0800 : VB   ; pankki 2: $8800 (kaupungintalon peli käyttää $8000-$87cf initin aikana)
D018    = ((TAULU_SCREEN & $3fff) >> 6) | (($a000 & $3fff) >> 10)
        .endif
TAULU_SPRBLK = (TAULU_SPRMEM & $3fff) / 64

        .virtual TZP + 11
ra      .byte ?
rx      .byte ?
ry      .byte ?
        .endv

        .if MERKKI
        * = LATAUS
RUN     = MERKKI
        .elsif PANKKI == 2
        * = $9800                       ; spritelohkot $8000 ja ruutu taulu_alussa, eivät tiedostossa
RUN     = $9800
        .else
        * = P3_KOODI ? P3_KOODI : VB + $0100
RUN     = VB + $0100
        .endif
        .logical RUN
        .if MERKKI
        .binary TAULU_CHR               ; merkistö (tyhjä solu = 0)
        .fill MERKKI + $0800 - *, 0
        .binary TAULU_SCR               ; ruudun merkkikoodit (taulu_alku tyhjentää värimuistin)
        .fill MERKKI + $0d00 - *, 0     ; spritelohkot (taulu_alku kopioi)
        .endif
; taulu_init: pääsäikeessä ennen kelloa (kuva ennallaan): ruutu mustaksi, spritet
        .if LATAUS == MERKKI && !P3_KOODI
taulu_init
        .endif
        jmp taulu_alku

; taulu_go: VIC pankkiin ja oma IRQ; palaa heti
        .if LATAUS != MERKKI
taulu_go_r                              ; kopiotila: taulu_go on latausalueen tynkä
        .else
taulu_go
        .endif
        sei
        .if MERKKI
        jsr taulu_tyhjaa                ; rivin 250 jälkeen ennen kuvan alkua (noin 100 riviä)
        .endif
        jsr taulu_vic
        lda #3 - (VB >> 14)             ; VIC-pankki ($dd00:aan vain 0-3)
        sta $dd00
        lda #D018
        sta $d018
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
        cli
        rts

; taulu_jalki (koko demo, siirtymä "filmi": edellisen taulun askel ku_cutin jälkeen): taulun naarmu ja pöly jatkuvat
; mustalla rungon IRQ:n R_TICKissä, kun seuraavan alku latautuu ja alustuu.
; Kuva on taulun pankissa, ruudun värit häivytyksen jälkeen mustia, joten seuraavan kirjoitukset bittikarttaan eivät
; näy. Seuraava ottaa VIC:n ja spritet alussaan (Hillner: vic_init); R_TICK lakkaa, kun ku_start ottaa rungon IRQ:n pois.
        .if !MERKKI
taulu_jalki
        lda #1
        sta tz_jalki
        lda #$ff                        ; naarmu näkyy koko siirtymän (ei odota satunnaista syntyä mustalla)
        sta tz_sl
        lda #0
        sta jalki_t
        sei
        jsr taulu_vic
        lda #3 - (VB >> 14)
        sta $dd00
        lda #D018
        sta $d018
        lda #<jalki_tick
        sta R_TICK + 1
        lda #>jalki_tick
        sta R_TICK + 2
        cli
        rts
jalki_tick
        inc jalki_t
        lda jalki_t
        jmp taulu_kehys
jalki_t .byte 0
        .endif

irq
        sta ra
        stx rx
        sty ry
        lda $01                         ; seuraavan kohtauksen alustus voi pitää I/O:n pois (ikkunan kam_gen $01 = $34)
        pha
        lda #$35
        sta $01
        asl $d019
        jsr FRAME_HOOK
        .if TAULU_DF0
        lda DFRAME
        sec
        sbc #<TAULU_DF0
        tax
        lda DFRAME+1
        sbc #>TAULU_DF0
        bne +
        txa
        .else
        lda DFRAME+1
        bne +
        lda DFRAME
        .endif
        cmp #TAULU_KESTO
        bcs +
        jsr taulu_kehys
+       pla
        sta $01
        lda ra
        ldx rx
        ldy ry
        rti

        .include "../../lib/taulu.asm"
        .include "taulu_osa_data.asm"
blk_end
        .endlogical
        .if MERKKI
        .cerror blk_end > MERKKI + $2000, "taulun koodi ja taulut ylittävät 8 kt:n lohkon"
          .if LATAUS != MERKKI
; Kopiotila (latausalue on edellisen kohtauksen aikana vapaa, ajoalue MERKKI vasta sen jälkeen): taulu_init ei tee
; mitään (jatkuvassa siirtymässä edellinen näyttää vielä MERKKI-aluetta), taulu_show (osalevy, ennen kelloa) kopioi
; lohkon ja alustaa, ja taulu_go kopioi itse, jos taulu_show:ta ei ajettu (jatkuva sauma: kuva mustana noin 3 kehystä
; rungon IRQ:n soittaessa, sitten taulu kehyksestään).
taulu_init
        lda #0
        sta kopioitu
        rts
taulu_show
        jsr kopio
        jmp taulu_alku
taulu_go
        lda kopioitu
        bne +
        sei
        lda #$0b
        sta $d011
        jsr R_IRQ_ON
        cli
        jsr kopio
        jsr taulu_alku
+       jmp taulu_go_r
kopio   ldy #>(blk_end - MERKKI + 255)
        ldx #0
_c      lda LATAUS,x
_d      sta MERKKI,x
        inx
        bne _c
        inc _c+2
        inc _d+2
        dey
        bne _c
        inc kopioitu
        rts
kopioitu .byte 0
          .endif
        .else
        .cerror blk_end > (PANKKI == 2 ? $a000 : TAULU_SCREEN), "taulun koodi ja taulut ylittävät bittikartan tai ruudun"
          .if P3_KOODI
; Kopiotila (PANKKI 3, taulu2b koko demossa kuopan perään jatkuvana): kuopan viimeinen kuva käyttää pankkia 3
; viimeiseen kehykseen asti, joten koodi ladataan kuopan aikana välialueelle P3_KOODI ja bittikartta $e000-:aan tai
; välialueelle P3_BITTI (Makefile: taulu2b $5800 ja $6000), ja taulu_sauma (sauman jälkeen, part-taulu2b.json
; jatkuva_alustus) pimentää kuvan, ottaa rungon IRQ:n ja ajaa taulu_initin: koodi paikalleen $c100-:aan (eteenpäin,
; kohde ei saa olla lähteen sisällä), välialueelta bittikartta $e000-:aan ja alustus. Taulun ensimmäiset kehykset
; ovat lähes mustia.
taulu_sauma
        lda #$0b
        sta $d011
        lda #0
        sta $d015
        jsr R_IRQ_ON
        cli
taulu_init
        ldy #>(blk_end - RUN + 255)
        ldx #0
_c      lda P3_KOODI,x
_d      sta RUN,x
        inx
        bne _c
        inc _c+2
        inc _d+2
        dey
        bne _c
          .if P3_BITTI != $e000
        ldy #>$1f00                     ; bittikartta 8000 t = $1f00 + $40
_b      lda P3_BITTI,x
_e      sta $e000,x
        inx
        bne _b
        inc _b+2
        inc _e+2
        dey
        bne _b
-       lda P3_BITTI + $1f00,x
        sta $ff00,x
        inx
        cpx #$40
        bne -
          .endif
        jmp taulu_alku
        .cerror * > (P3_BITTI != $e000 ? P3_BITTI : TAULU_SCREEN), "kopiotilan koodi osuu bittikartan latausalueeseen tai ruutuun"
        .cerror P3_KOODI < RUN && P3_KOODI + blk_end - RUN > RUN, "kopiotila: eteenpäin kopio, kohde ei saa olla lähteen sisällä"
          .endif
          .if PANKKI == 2
        * = $a000
        .binary TAULU_BIN
          .endif
        .endif
taulu_end
