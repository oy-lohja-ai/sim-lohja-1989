; Kuopan nousu mustasta: kuva 1 pyyhkiytyy
; esiin ylhäältä alas, kaksi merkkiriviä kehyksessä, ja pyyhkäisyn etureuna on puolivalossa (väriketjut,
; src/lib/haivytys.asm, taso 2/4), joten 18 kuvariviä ovat esillä kehyksessä 9. Varsien ja kauhan spritet nousevat
; väriketjuja pitkin, kun pyyhkäisy saavuttaa ne. Bittikartan värit ovat ruudussa (kaksi väriä tavussa) ja
; värimuistissa, joten kuva pimennetään niistä: kpn_prep (kp_initin jälkeen) ottaa ruudun rivit talteen ja nollaa
; molempien puskurien rivit, kpn_show (S_SHOW) tekee kp_show:n työn ilman värimuistin kopiota; kpn_go (kp_go:n jälkeen)
; vaihtaa kuvan IRQ-koukun (irqhook, rivi 250) kpn_tickiin, joka palauttaa rivit (ruutu talteenotosta, värimuisti COL1:stä) ja hyppää spr1:een; lopussa koukku takaisin spr1:een.
; Työ enintään noin 6 000 sykliä kehyksessä rivillä 250 ennen kuopan piirtotyötä, kehykset 0-9.
; Muisti: KPN $fc00- (koodi ja taulut; koko demossa vapaa graafin ja kuopan alun aikana, KP1DS päättyy $fbb6), ruudun
; talteenotto $c400-$c6cf (KP0S on vapaa kp_stagen jälkeen). Glue odottaa kehykseen 11 ennen kuin seuraavan
; osan esilataukset voivat alkaa (ne käyttävät $c400-:ää ja $e000-:ää, part-kuoppa.json vapaana_lopussa).

        .include "kp_defs.inc"
        .include "nousu_syms.inc"       ; kuoppa.labels: irqhook, spr1, COL1, fbank (Makefile)

BUF     = $c400                         ; ruudun rivit 3-20 talteen (SCR_N tavua)
HV_N    = 4
PUOLI   = 2                             ; etureunan taso

        * = $fc00
        .include "../../lib/haivytys.asm"

; kpn_prep (kp_initin jälkeen, kuva ei näy): ruudun rivit talteen ja molempien puskurien rivit mustiksi
kpn_prep
        ldx #0
-       .for _o := 0, _o < SCR_N, _o += SCR_N / 3
        lda SCR1 + PICS + _o,x
        sta BUF + _o,x
        lda #0
        sta SCR1 + PICS + _o,x
        sta SCR2 + PICS + _o,x
        .endfor
        inx
        cpx #SCR_N / 3
        bne -
        rts

; kpn_show (S_SHOW kp_show:n tilalla): kuten kp_show, mutta värimuisti jää mustaksi (ei col_copya), joten lyhyempi;
; toistettava (koko demossa ku_start kutsuu uudelleen, jos kuvan asetus myöhästyi iskusta)
kpn_show
        ldx #0
        txa
-       sta $d800,x
        sta $d900,x
        sta $da00,x
        sta $dae8,x
        inx
        bne -
        lda shown                       ; do_flip:in tuleva puskuri
        eor #1
        tax
        lda fbank,x
        sta $dd00
        lda #$18                        ; ruutu +$0400, bittikartta +$2000 pankissa
        sta $d018
        sta $d016
        lda #0                          ; (reuna on jo musta: rungon pimennys)
        sta $d021
        sta $d015
        lda #$3b
        sta $d011
        rts

; kpn_go (kp_go:n jälkeen): koukku kpn_tickiin ja spritet mustiksi
kpn_go
        lda #0
        sta kk
        jsr sprv
        sei
        lda #<kpn_tick
        sta irqhook+1
        lda #>kpn_tick
        sta irqhook+2
        cli
        rts

; kpn_tick (kuopan IRQ, rivi 250): rivit 2k ja 2k+1 täysiksi, 2k+2 puolivaloon
kpn_tick
        lda kk
        asl
        jsr full
        lda kk
        asl
        ora #1
        jsr full
        lda kk
        asl
        clc
        adc #2
        jsr half
        inc kk
        jsr sprv
        lda kk
        cmp #RIVIT / 2 + 1
        bcc +
        lda #<spr1                      ; valmis: koukku takaisin kuvan omaan
        sta irqhook+1
        lda #>spr1
        sta irqhook+2
+       jsr spr1                        ; spritet piiloon, kunnes pyyhkäisy on niiden kohdalla (spr1 ottaa ne
        lda kk                          ; joka kehys, ja jakorivin spl asettaa varsien värin itse)
        cmp #SPR0 + 1
        bcs +
        lda #0
        sta $d015
+       rts

; sprv: spritevärit tasolle kk - SPR0 (0-HV_N): varret ja kauha ovat kuvan alaosassa, joten ne pysyvät mustina,
; kunnes pyyhkäisy on niiden kohdalla (kp_go: $d025 musta, $d026 oranssi, $d027- keltainen)
SPR0    = RIVIT / 2 + 1 - HV_N
sprv    lda kk
        sec
        sbc #SPR0
        bcs +
        lda #0
+       cmp #HV_N
        bcc +
        lda #HV_N
+       asl
        asl
        asl
        asl
        tay
        lda hv_tab + 8,y
        sta $d026
        lda hv_tab + 7,y
        ldx #7
-       sta $d027,x
        dex
        bpl -
        rts

; aseta (A = rivi 0-RIVIT-1): rivin osoitteet kopioihin, C = 1 jos rivi ei ole kuvassa
aseta   cmp #RIVIT
        bcs _pois
        tax
        lda alo + 0 * RIVIT,x
        sta fb+1
        sta hb+1
        lda ahi + 0 * RIVIT,x
        sta fb+2
        sta hb+2
        lda alo + 1 * RIVIT,x
        sta fs1+1
        sta hs1+1
        lda ahi + 1 * RIVIT,x
        sta fs1+2
        sta hs1+2
        lda alo + 2 * RIVIT,x
        sta fs2+1
        sta hs2+1
        lda ahi + 2 * RIVIT,x
        sta fs2+2
        sta hs2+2
        lda alo + 3 * RIVIT,x
        sta fc+1
        sta hc+1
        lda ahi + 3 * RIVIT,x
        sta fc+2
        sta hc+2
        lda alo + 4 * RIVIT,x
        sta fd+1
        sta hd+1
        lda ahi + 4 * RIVIT,x
        sta fd+2
        sta hd+2
        clc
_pois   rts

full    jsr aseta
        bcs fx
        ldy #39
fb      lda $ffff,y
fs1     sta $ffff,y
fs2     sta $ffff,y
fc      lda $ffff,y
fd      sta $ffff,y
        dey
        bpl fb
fx      rts

half    jsr aseta
        bcs hx
        ldy #39
hb      lda $ffff,y                     ; ruudun tavu: molemmat värit tasolle PUOLI
        pha
        and #15
        tax
        lda lo_t,x
        sta _l+1
        pla
        lsr
        lsr
        lsr
        lsr
        tax
        lda hi_t,x
_l      ora #0
hs1     sta $ffff,y
hs2     sta $ffff,y
hc      lda $ffff,y
        and #15
        tax
        lda hv_tab + PUOLI * 16,x
hd      sta $ffff,y
        dey
        bpl hb
hx      rts

kk      .byte 0
lo_t    .for _v := 0, _v < 16, _v += 1
        .byte hv_vari_s(_v, PUOLI)
        .next
hi_t    .for _v := 0, _v < 16, _v += 1
        .byte hv_vari_s(_v, PUOLI) << 4
        .next
KOHTEET = (BUF, SCR1 + PICS, SCR2 + PICS, COL1, $d800 + PICS)   ; talteenotto, puskurit, värit, värimuisti
alo     .for _b in KOHTEET
        .byte <(_b + range(RIVIT) * 40)
        .next
ahi     .for _b in KOHTEET
        .byte >(_b + range(RIVIT) * 40)
        .next
kpn_end
        .cerror kpn_end > $fffa, "kp_nousu: yli $fff9"
