; Kuva 3: ryhmälogokyltit putoavat valmiiseen Lohjantähteen (src/lib/kylttipudotus.asm, paikat ja ajat kyltit.py
; KYLTIT), neon hengittää ja ikkunavalot vaihtuvat rauhallisesti (liike joka kehys). Vain kuoppa-kylteissä (VARIANT=kyltit):
; ytimen perään $2800-, kuvien 1-2 muisti vapaa; spritet pankissa 2.
        .include "kp_defs.inc"
        .include "core.inc"
        .include "k3.inc"               ; kuoppa3: toggle, gstate, ovr, ntog

KP_SCREEN = $8400               ; kuva 3: ruutu ja bittikartta pankissa 2
KP_BITMAP = $a000
KP_SPRBUF = $8000               ; kuvan 1 puhdas tausta (vapaa kuvassa 3); $9000-$9fff on VIC:lle merkistö-ROM
KP_SPR0   = 0
KP_ZP     = $a0                 ; kuoppa3: zp3_end <= $a0
EVP       = $ae                 ; täytteen tapahtumaosoitin
BRS       = $b0                 ; hengitys: palavan tilan data, ruutu, solulista
BRD       = $b2
BRC       = $b4
FILL0     = 1200                ; täyte koko kuvaan 3 (1201-; työn kehys f näkyy kehyksellä f + 1)

        * = $2800                       ; ytimen (kp0c $1a00-core_end) perään
kp4_go                          ; pääsäie kuvan 2 aikana (kp3:n jälkeen): pankin 2 letterbox, työ jobv[2]:een (ajetaan
                                ; leikkauksesta 1198 alkaen); IRQ-koukku kuvan 3 ensimmäisessä työssä
        jsr kpm.kp_init
        ldx #0                  ; letterbox-rivit 0-2: bittikarttaan %11 mustalla värimuistilla, jotta putoava kyltti
        lda #$ff                ; on niiden takana ($d01b) eikä näy kuvan yläpuolella
-       sta KP_BITMAP,x
        sta KP_BITMAP + $100,x
        sta KP_BITMAP + $200,x
        sta KP_BITMAP + $2c0,x
        inx
        bne -
        lda #0
        ldx #119
-       sta $d800,x
        dex
        bpl -
        sei
        lda jobv_lo+2           ; kuvan 3 työ ensin kyltit, sitten valaistus
        sta kp4_nxt+1
        lda jobv_hi+2
        sta kp4_nxt+2
        lda #<kp4_job
        sta jobv_lo+2
        lda #>kp4_job
        sta jobv_hi+2
        cli
        rts

kp4_job                         ; sisäkkäinen työ (cli) FRAME_HOOKin jälkeen: laskeutumisen kopio ei myöhästytä musiikkia
        lda kp4_hk
        bne +
        inc kp4_hk              ; leikkaus tehty (leikkaus nollaa koukun): spritet letterboxin taakse riveillä 250-74
        lda #<kp4_hook
        sta irqhook+1
        lda #>kp4_hook
        sta irqhook+2
        lda #$4c
        sta irqhook
+
        jsr kp_df               ; työn muutokset näkyvät kehyksellä DFRAME + 1: moduulille se (kyltti iskulle);
        clc                     ; kuopan kehyksinä (kuoppa-kyltit: + KP_ALKU, taulun 2c jälkeen - KP_TAUKO)
        adc #<(1 + KP_ALKU)
        sta kp4_f
        txa
        adc #>(1 + KP_ALKU)
        sta kp4_f+1
        lda #0
        sta kp4_cov
        ldy #0                  ; pudotus alkaa tällä kehyksellä (spritejen kopio myöhästyttää työn): ikkunan valo
        lda kp4_f               ; vaihtuu heti alussa
        cmp (kpm.kp_e),y
        iny
        lda kp4_f+1
        sbc (kpm.kp_e),y
        bcc +
        ldy #3
        lda (kpm.kp_e),y
        bne +
        jsr kp4_flip
+       lda kpm.kp_e
        sta EVP
        lda kpm.kp_e+1
        sta EVP+1
        jsr kp4_breath          ; yksi solu (noin 100 sykliä) ennen kylttejä: laskeutumisen kopio ei siirrä sitä
        lda kp4_f               ; seuraavaan kehykseen; sitten kyltit: spritejen Y ennen kuin säde ehtii niihin
        ldx kp4_f+1
        jsr kpm.kp_frame
        jsr kp4_rest
        lda #0
        sta ntog
        jsr kp4_nxt             ; job3 (kerrokset ensin, ehtivät ennen tornia)
        jsr kp4_seen
        lda kp4_f               ; pimennys: kaupat lähtevät, rakennus pimenee (ei enää täytettä, joka sytyttäisi)
        cmp #<PIMEA0
        lda kp4_f+1
        sbc #>PIMEA0
        bcc +
        jmp kp4_pimea
+       lda kp4_f               ; täyte: jos kuva ei muuttunut tällä kehyksellä, ikkunan valo syttyy tai sammuu
        cmp #<(FILL0 + 1)       ; pysyvästi (seuraavan kerran vasta, kun kierto tulee siihen taas)
        lda kp4_f+1
        sbc #>(FILL0 + 1)
        bcc _rts
        lda ntog
        ora kp4_cov
        bne _rts
        jmp kp4_flip
_rts    rts

; kp4_pimea: PIMEA0:sta joka PIMEA_VALI. kehys seuraava valoryhmä (torni.py dark_data: ikkunat, sitten kerrokset)
; sammuu pysyvästi: palava ryhmä saa job3i:n ohitusbitin (ovr), jolloin sen valmis kuvio näyttää pimeää.
kp4_pimea
        .cerror PIMEA_VALI != 4 || (PIMEA0 & 3) != 0, "kp4_pimea: väli 4"
        lda kp4_f
        and #3
        bne _r
-       ldy kp4_di
        cpy #NDARK
        bcs _r
        inc kp4_di
        lda kp4_dend,y          ; askeleen viimeinen ryhmä (kerroksen sarakeryhmät samalla askeleella, torni.py)
        sta _end
        ldx kp4_dark,y
        lda gstate,x
        beq +                   ; jo pimeä
        lda ovr,x
        eor #1
        sta ovr,x
        lda #0
        sta gstate,x
        jsr toggle
+       lda _end
        beq -
_r      rts
_end    .byte 0

kp4_flip                        ; seuraavan kelpaavan täyteikkunan valo päinvastaiseksi pysyvästi: job3i:n ohitus
        jsr kp4_next            ; (ovr), tila ja XOR heti
        bcc +
        rts
+       inc kp4_cov
        lda ovr,x
        eor #1
        sta ovr,x
        lda gstate,x
        eor #1
        sta gstate,x
        jmp toggle

; kp4_rest: täyteikkuna, joka näkyy kyltin solusuorakaiteessa kyltin vieressä, omaan tilaansa (ovr pois) ennen kyltin
; pudotusta (torni.py fill_data: kehys R), koska kyltti kirjoittaa suorakaiteeseen laskeutumishetken tilan.
kp4_rest
        ldy kp4_ri
        cpy #NREST
        bcs _r
        lda kp4_f
        cmp kp4_rl,y
        lda kp4_f+1
        sbc kp4_rh,y
        bcc _r
        inc kp4_ri
        ldx kp4_rw,y
        lda ovr,x
        and #1
        beq kp4_rest
        inc kp4_cov
        lda ovr,x
        eor #1
        sta ovr,x
        lda gstate,x
        eor #1
        sta gstate,x
        jsr toggle
        jmp kp4_rest
_r      rts

; kp4_breath: neon hengittää. Syttyneistä kylteistä (kp4_on: syttyminen ohi) vuorollaan yksi solu vaihtaa värinsä
; sukulaisväriin (kp4_c*: valmiit ruutu- ja värimuistitavut, vain kyltin neon; rakennus solussa pysyy) tai takaisin
; palavan tilan väreihin; solut sarakkeittain vasemmalta (aalto), joten jokin kyltti muuttuu joka kehys, mutta yksi
; solu vain kerran kierroksessa (solut x syttyneet kyltit kehystä).
kp4_breath
        ldx kp4_nlit
        cpx #kpm.KP_NSIGN
        beq +
        lda kp4_f
        cmp kp4_on_lo,x
        lda kp4_f+1
        sbc kp4_on_hi,x
        bcc +
        inc kp4_nlit
+       lda kp4_nlit
        bne +
        rts
+       ldy kp4_nlit            ; seuraava syttynyt kyltti, joka ei ole lähtenyt (kp4_off: sen paikka on tyhjä)
        ldx kp4_rr
-       inx
        cpx kp4_nlit
        bcc +
        ldx #0
+       lda kp4_f
        cmp kp4_off_lo,x
        lda kp4_f+1
        sbc kp4_off_hi,x
        bcc +
        dey
        bne -
        rts                     ; kaikki syttyneet lähteneet
+       stx kp4_rr
        stx kp4_x
        lda kpm.kp_stb,x        ; palava tila = kp_st[kp_stb[kyltti] + 2]
        clc
        adc #2
        tay
        lda kpm.kp_st_lo,y
        sta BRS
        lda kpm.kp_st_hi,y
        sta BRS+1
        lda kpm.kp_soff_lo,x
        clc
        adc #<KP_SCREEN
        sta BRD
        lda kpm.kp_soff_hi,x
        adc #>KP_SCREEN
        sta BRD+1
        lda kp4_cl,x
        sta BRC
        lda kp4_ch,x
        sta BRC+1
        lda kp4_pass,x          ; parillinen kierros: sukulaisväri, pariton: takaisin
        and #1
        sta kp4_v
        ldy kp4_ci,x
        lda (BRC),y
        sta kp4_k               ; solu tilan datassa
        iny
        lda (BRC),y
        sta kp4_o               ; solu ruudulla kyltin kulmasta
        iny
        lda (BRC),y
        sta kp4_t               ; sukulaisvärit: ruutu
        iny
        lda (BRC),y
        sta kp4_tc              ; ja värimuisti
        iny
        tya
        cmp kp4_nc,x
        bcc +
        inc kp4_pass,x
        lda #0
+       sta kp4_ci,x
        lda kp4_v
        bne _back
        lda kp4_t
        ldy kp4_o
        sta (BRD),y
        lda kp4_tc
        jmp _col
_back   ldy kp4_k
        lda (BRS),y             ; ruutu: värit %01 ja %10
        ldy kp4_o
        sta (BRD),y
        lda kp4_k
        clc
        adc kp4_wh,x
        tay
        lda (BRS),y             ; värimuisti: %11
_col    tax
        lda BRD+1
        clc
        adc #>($d800 - KP_SCREEN)
        sta BRD+1
        txa
        ldy kp4_o
        sta (BRD),y
        inc kp4_cov
        rts

kp4_next                        ; X = seuraava kelpaava täyteikkuna (C = 0), C = 1: ei yhtään. Kelpaa: kyltti ei ole
        lda #NFILL              ; vielä tulossa sen päälle (kp4_u), oma kuvio ei käynnissä (kp4_bl..kp4_bh) ja
        sta kp4_n               ; edellisestä vaihdosta vähintään FILL_GAP kehystä
_try    ldy kp4_fi
        iny
        cpy #NFILL
        bcc +
        ldy #0
+       sty kp4_fi
        lda kp4_f
        cmp kp4_ul,y
        lda kp4_f+1
        sbc kp4_uh,y
        bcs _no
        lda kp4_f
        cmp kp4_bll,y
        lda kp4_f+1
        sbc kp4_blh,y
        bcc _gap
        lda kp4_bhl,y
        cmp kp4_f
        lda kp4_bhh,y
        sbc kp4_f+1
        bcs _no
_gap    lda kp4_f
        sec
        sbc kp4_lal,y
        tax
        lda kp4_f+1
        sbc kp4_lah,y
        bne _ok
        cpx #FILL_GAP
        bcc _no
_ok     lda kp4_f
        sta kp4_lal,y
        lda kp4_f+1
        sta kp4_lah,y
        ldx kp4_fill,y
        clc
        rts
_no     dec kp4_n
        bne _try
        sec
        rts
kp4_nxt jmp $ffff               ; job3

; kp4_seen: muuttuiko kuva kylttien takia (kp4_cov != 0): tapahtumat EVP..kp_e (vain tilan vaihto näkyy: pudotus
; alkaa reunuksen takana, laskeutuminen on pikselilleen spritejen kuva), putoava kyltti siirtyi näkyvissä
kp4_seen
_ev     lda EVP
        cmp kpm.kp_e
        bne +
        lda EVP+1
        cmp kpm.kp_e+1
        beq _spr
+       ldy #2
        lda (EVP),y             ; kyltti
        tax
        iny
        lda (EVP),y             ; tyyppi: 0 pudotus, 1 bittikarttaan (sammunut = tila 0), 2 + tila
        beq _nx
        cmp #1
        bne _st
        lda #0
        sta kp4_cur,x
        beq _nx
_st     sbc #2                  ; C = 1
        cmp kp4_cur,x
        beq _nx
        sta kp4_cur,x
        inc kp4_cov
_nx     lda EVP
        clc
        adc #4
        sta EVP
        bcc _ev
        inc EVP+1
        jmp _ev
_spr    ldx kpm.kp_fl          ; paikka 0 (pudotus)
        bmi _r
        lda $d001 + 2 * KP_SPR0 ; kyltin ylin rivi
        cmp kp4_ly
        beq _r
        sta kp4_ly
        cmp kp4_vis,x           ; alareuna letterboxin alla
        bcc _r
        inc kp4_cov
_r      rts

kp4_f   .word 0                 ; näkyvä kehys (DFRAME + 1)
kp4_cov .byte 0
kp4_di  .byte 0                 ; pimennyksen seuraava ryhmä (kp4_dark)
kp4_ly  .byte 0
kp4_fi  .byte 0
kp4_n   .byte 0
kp4_hk  .byte 0                 ; IRQ-koukku asennettu
kp4_ri  .byte 0                 ; seuraava palautettava ikkuna (kp4_rest)
kp4_lal .fill NFILL, 0          ; ikkunan edellinen vaihto
kp4_lah .fill NFILL, 0
kp4_cur .fill kpm.KP_NSIGN, 0
kp4_nlit .byte 0                ; syttyneet kyltit (hengitys)
kp4_rr  .byte $ff               ; viimeksi hengittänyt kyltti
kp4_x   .byte 0
kp4_k   .byte 0
kp4_o   .byte 0
kp4_v   .byte 0
kp4_t   .byte 0
kp4_tc  .byte 0
kp4_ci  .fill kpm.KP_NSIGN, 0   ; kohta solulistassa (tavuina)
kp4_pass .fill kpm.KP_NSIGN, 0  ; kierros
        .include "kp4fill.asm"  ; torni.py: kp4_vis, kp4_fill, NFILL, hengityksen taulut

kp4_hook                        ; ytimen IRQ (rivi 250): spritet letterboxin takana, kuvan alusta edessä
        lda #kpm.KP_MASK
        ora $d01b
        sta $d01b
        lda #74
        sta $d012
        lda #<kp4_spl
        sta $fffe
        lda #>kp4_spl
        sta $ffff
        rts

kp4_spl pha                     ; rivi 74 (letterboxin viimeinen): spritet eteen vasta rivin 75 alussa, muuten
        txa                     ; putoavan kyltin alareuna näkyy rivillä 74 kehyksen ajan
        pha
        asl $d019
        lda $d01b
        and #$ff ^ kpm.KP_MASK
        ldx #75
-       cpx $d012
        bne -
        sta $d01b
        pla
        tax
        lda #IRQ_LINE
        sta $d012
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        pla
        rti

kpm     .block                  ; moduulin nimet omaan nimiavaruuteen (ytimessä on oma kp_init)
KP_TAKANA = 1                   ; letterbox: spritet bittikartan takana riville 74 asti (kp4_hook, kp4_spl)
        .include "kylttipudotus.asm"
        .include "kp_data.asm"
        .bend
kp4_end
        .cerror kp4_end > $8000, "kyltit osuvat spritepuskuriin ($8000)"
        .cerror kp4_go < core_end, "ydin (kp0c)"
        .cerror KP_SPRBUF + kpm.KP_NSPR * 64 > KP_SCREEN, "spritepuskuri"
