; Lohjantähden kuoppa (partti 5): Hillnerin paikalle kaivetaan kuoppa 1989, runko nousee ja torni tuijottaa
; Sokeripalaa. Kolme kuvaa, leikkaukset tahdin rajalla. Data build.py ja kuormaaja.py (konseptin generaattoreista).
;
; Runko: kp_init (pääsäie, kuva musta: puskurit, puhdas tausta, spritet), kp_go (VIC, värit, oma IRQ; palaa heti).
;
; Kuva 1: pyöräkuormaaja ajaa penkereellä, nostaa kauhan ja kippaa. Piirto IRQ:ssa sisäkkäisenä työnä (cli) kahteen
; puskuriin vuorotellen: vanhan kuvan palautus puhtaasta taustasta, runko (maski ja neljä esisiirtoa), varret ja
; kauha monikulmioina, napojen pultit; ohjaamon lasi on neljä spriteä. Valmis puskuri vaihdetaan IRQ:ssa ($dd00).
;
; Muisti (kaikissa pankeissa ruutu +$0400, bittikartta +$2000, kuva-alue merkkirivit 3-20, $d018 = $18):
;   $1a00-$3fff koodi ja taulut
;   pankki 1   ruutu $4400, bittikartta $6000: kuvan 1 puskuri A; kuvan 2 jalankulkija $4800 (kp2w)
;   pankki 2   ruutu $8400, bittikartta $a000: kuvan 1 puskuri B; kuoppa-kylteissä kuva 3 (kp3, värit $8800)
;   pankki 3   ruutu $c400, bittikartta $e000, värit $fa40: kuva 2 (kp2a, kp2b)
;   runko      esisiirrot 0-1 $4800-$61ff, 2-3 $8800-$a1ff (bittikarttojen näkymättömät rivit 0-2 mukana)
;   puhdas     kuvan 1 tausta riveiltä 7-17, sarakkeet 0-20: $4000-$43bf, $8000-$83bf, $bcac-$bff3 (ei pankkia 3:
;              kuvan 1 aikana siellä vain varsien kärjet $c000-$c3ff, seuraava osa esiladataan $c400-:aan ja $e000-:aan)
;   spritet    $7a40 ja $ba40, kuvan 1 värit $7b40, jyvät $bb40 (bittikarttojen näkymättömät rivit 21-24)

        .include "kp_defs.inc"
PLANE   = (BODY_H + 7) / 8 * 128        ; esisiirron taso (maski, sitten data)

        * = $1a00
fcopy   .macro s, d, n              ; kuten copy, nopea (fcopy_n): vain ennen kelloa
        lda #<\s
        ldx #>\s
        sta zsrc
        stx zsrc+1
        lda #<\d
        ldx #>\d
        sta zdst
        stx zdst+1
        ldx #\n / 256
        ldy #\n % 256
        jsr fcopy_n
        .endm

copy    .macro s, d, n
        lda #<\s
        ldx #>\s
        sta zsrc
        stx zsrc+1
        lda #<\d
        ldx #>\d
        sta zdst
        stx zdst+1
        ldx #\n / 256
        ldy #\n % 256
        jsr copy_n
        .endm

; ================================================================== ydin ($1a00-core_end): pysyy koko osan ajan
; ------------------------------------------------------------------ apurutiinit
; copy_n: X sivua ja Y tavua zsrc -> zdst
copy_n
        sty zrest
        ldy #0
        txa
        beq _last
-       lda (zsrc),y
        sta (zdst),y
        iny
        bne -
        inc zsrc+1
        inc zdst+1
        dex
        bne -
_last
-       cpy zrest
        beq +
        lda (zsrc),y
        sta (zdst),y
        iny
        bne -
+       rts

; kp_stage (pääsäie ennen kp_initiä): koko demossa kuopan alkupalat esiladataan graafin aikana. Graafin muistin
; päälle osuvat välit ladataan välialueille, jotka graafi jättää vapaaksi, ja kopioidaan tässä paikalleen (noin
; 10,7 kt, noin 8 kehystä): STG_A-stg_b (graafin NEUVO-data) $c000:sta, kp1b (graafin ruutu ja koodi) $e000:sta ja
; kp1d (sen jälkeen, kohde $c000 vapautuu ensin) välialueen perästä. Osalevyllä samoin.
STG_A   = $2000                         ; graafin data $2000-$2d89
STG0    = $c000                         ; välialueet: graafi ei käytä $c000-$cfff:ää eikä $e000-$fff9:ää
STG1    = $e000
        .virtual STG_A + $0e00
stg_b                                   ; KP1 latautuu paikalleen tästä
        .endv
; fcopy_n: kuten copy_n (X sivua ja Y tavua zsrc -> zdst), sivut 8 tavua kierroksessa itseään muuttavilla abs,y-
; käskyillä (noin 10 sykliä tavulle, copy_n 16): kuopan alku ennen kelloa on mustaa, kp_stage ja
; kp_init kopioivat noin 20 kt. Ytimen alaosassa (kp_stage käyttää sitä ennen kuin $2000- on paikallaan).
fcopy_n
        stx fpages
        sty zrest
        ldx #0                          ; parin k operandit: lähde + k, kohde + k
        ldy #0
-       tya
        clc
        adc zsrc
        sta _body+1,x
        lda zsrc+1
        adc #0
        sta _body+2,x
        tya
        clc
        adc zdst
        sta _body+4,x
        lda zdst+1
        adc #0
        sta _body+5,x
        txa
        clc
        adc #6
        tax
        iny
        cpy #8
        bne -
        lda fpages
        beq _rest
_pg     ldy #0
_body
        .for fk = 0, fk < 8, fk += 1
        lda $ffff,y
        sta $ffff,y
        .next
        tya
        clc
        adc #8
        tay
        bne _body
        ldx #0                          ; seuraava sivu
-       inc _body+2,x
        inc _body+5,x
        txa
        clc
        adc #6
        tax
        cpx #48
        bne -
        inc zsrc+1
        inc zdst+1
        dec fpages
        bne _pg
_rest   ldx #0                          ; loput tavut copy_n:llä
        ldy zrest
        jmp copy_n
fpages  .byte 0

kp_stage                                ; KP1DS:n välialue KP1BS:n perässä (split.py laskee saman)
        #fcopy STG0, STG_A, (stg_b - STG_A)
        #fcopy STG1, kp1b, (kp1b_end - kp1b)
        #fcopy (STG1 + (kp1b_end - kp1b)), kp1d, (kp1d_end - kp1d)
        rts
kp_stage_end
        .cerror kp_stage_end > STG_A, "kp_stage latautuu paikalleen (alle STG_A)"
        .cerror stg_b - STG_A > $1000, "KP0S ei mahdu $c000-$cfff:ään"
        .cerror STG1 + (kp1b_end - kp1b) + (kp1d_end - kp1d) > $fffa, "KP1BS ja KP1DS eivät mahdu $e000-$fff9:ään"

; col_copy: X/Y = 720 värin lähde -> $d878. Rivi kerrallaan ylhäältä alas, joten leikkauksessa kopio on säteen
; edellä, kun se alkaa riviltä 250 (240 x 3 tavua, noin 7 700 sykliä).
col_copy
        stx _s0+1
        sty _s0+2
        txa
        clc
        adc #<240
        sta _s1+1
        tya
        adc #>240
        sta _s1+2
        lda _s1+1
        adc #<240
        sta _s2+1
        lda _s1+2
        adc #>240
        sta _s2+2
        ldx #0
_s0     lda $ffff,x
        sta $d878,x
_s1     lda $ffff,x
        sta $d878+240,x
_s2     lda $ffff,x
        sta $d878+480,x
        inx
        cpx #240
        bne _s0
        rts

; ------------------------------------------------------------------ IRQ
; Leikkaukset ja puskurin vaihto ennen FRAME_HOOKia, sitten piirtotyö sisäkkäin (cli), jos edellinen on valmis.
irq
        pha
        txa
        pha
        tya
        pha
        asl $d019
        lda shot
        cmp #2
        bcs _flip
        tax
        ldy DFRAME+1                    ; jatkuva sauma (taulu 2e): ku_seam asettaa kellon S - 1 = $ffff ennen
        bmi _flip                       ; ensimmäistä kutsua, joten ilman tätä leikkaus kuviin 2 ja 3 tulisi heti
        lda DFRAME
        cmp cut_lo,x
        lda DFRAME+1
        sbc cut_hi,x
        bcc _flip
        inc shot
        lda #$60                        ; edellisen kuvan IRQ-koukku pois (rts)
        sta irqhook
        lda #0
        sta $d015
        sta flip
        lda cut_dd,x
        sta $dd00
        lda cut_col_lo,x
        ldy cut_col_hi,x
        tax
        jsr col_copy
        jmp _hook
_flip   lda flip
        bne +
        lda idle                        ; molemmat puskurit valmiita: vaihto joka kehys (koneen tärinä)
        beq _hook
+       lda shot                        ; vaihto vain kuvassa, jonka puskurit ovat käytössä (fbank)
        cmp fshot
        beq +
        lda #0
        sta flip
        beq _hook
+       jsr do_flip
_hook   jsr irqhook                     ; kuvan oma IRQ-koukku (esim. kuvan 2 spritejen vaihto)
        jsr FRAME_HOOK
        lda busy
        bne _out
        inc busy
        cli
        jsr job
        sei
        dec busy
_out    pla
        tay
        pla
        tax
        pla
        rti

; do_flip: takapuskuri näkyviin
do_flip
        lda shown
        eor #1
        sta shown
        tax
        lda fbank,x
        sta $dd00
        lda #0
        sta flip
        rts

fbank   .byte 2, 1                      ; puskurien A ja B pankit ($dd00), kuva asettaa
fshot   .byte 0                         ; kuva, jonka vaihtopyynnöt toteutetaan
idle    .byte 0                         ; 1 = puskurit samat, IRQ vaihtaa joka kehys (ei näkyvää muutosta)
irqhook rts                             ; kuva kirjoittaa tähän jmp-käskyn
        .word 0
bit_tab .byte 1, 2, 4, 8
cut_lo  .byte <(CUT2 - SIIRTO), $ff      ; osalevyn kehyksinä; kuvaan 3 ei leikata (kuoppa loppuu kuvaan 2),
cut_hi  .byte >(CUT2 - SIIRTO), $ff      ; kuva 3 vain kuoppa-kylteissä (shot = 2)
cut_dd  .byte 0, 1                      ; kuva 2 pankissa 3, kuva 3 pankissa 2
cut_col_lo .byte <COL2, <COL3
cut_col_hi .byte >COL2, >COL3

; job: kuvan piirtotyö jobv-taulusta (kuvan 2 ja 3 koodi asettaa omansa ladattuaan)
job
        ldx shot
        lda jobv_lo,x
        sta _j+1
        lda jobv_hi,x
        sta _j+2
_j      jmp $ffff
jobv_lo .byte <job1, <job_rts, <job_rts
jobv_hi .byte >job1, >job_rts, >job_rts
job_rts rts

; clip: sarakkeet r0..r1 välille 0..40 (etumerkilliset), rivit ry0..ry1 välille zy0..zy1. C = 1: tyhjä.
clip
        lda r0
        bpl +
        lda #0
        sta r0
+       lda r1
        bmi _empty
        cmp #41
        bcc +
        lda #40
        sta r1
+       lda ry0
        cmp #ZONE_Y0
        bcs +
        lda #ZONE_Y0
        sta ry0
+       lda ry1
        cmp #ZONE_Y1+1
        bcc +
        lda #ZONE_Y1
        sta ry1
+       lda r0
        cmp r1
        bcs _empty
        lda ry0
        cmp ry1
        bcs _empty
        clc
        rts
_empty  sec
        rts

; copyrect: puhdas tausta -> takapuskuri, sarakkeet r0..r1-1, rivit ry0..ry1-1
copyrect
        jsr clip
        bcc +
        rts
+       lda r1                          ; poistumiskohta: rts sarakkeen r1 - r0 slottiin
        sec
        sbc r0
        tax
        lda cs_lo,x
        sta _pa+1
        sta _pr+1
        lda cs_hi,x
        sta _pa+2
        sta _pr+2
        lda #$60
_pa     sta $ffff
        ldx r0
        lda ry0
        sta yy
-       ldy yy
        lda cl_lo,y
        clc
        adc colofs_lo,x
        sta src
        lda cl_hi,y
        adc colofs_hi,x
        sta src+1
        lda bmrow_lo,y
        clc
        adc colofs_lo,x
        sta dst
        lda bmrow_hi,y
        adc colofs_hi,x
        clc
        adc bhi
        sta dst+1
        jsr cslot
        inc yy
        lda yy
        cmp ry1
        bne -
        lda #$a0                        ; ldy takaisin
_pr     sta $ffff
        rts

; Slotit: sarake k = Y 8 k osoittimista (src, dst, msk, dat); rts kirjoitetaan poistumisslottiin
cslot
        .for k in range(32)
        ldy #k*8
        lda (src),y
        sta (dst),y
        .endfor
        ldy #0                          ; slotti 32 (poistuminen)
        rts
cs_lo   .byte <(cslot + range(33) * 6)
cs_hi   .byte >(cslot + range(33) * 6)

; rnd: 8-bittinen LFSR (säilyttää X ja Y)
rnd
        lda g_rnd
        asl
        bcc +
        eor #$1d
+       sta g_rnd
        rts

; plotat: pikseli (X, Y) roolilla g_c bittikarttaan, jonka ylätavu on g_hi
plotat
        lda bmrow_lo,y
        sta zdst
        lda bmrow_hi,y
        clc
        adc g_hi
        sta zdst+1
plotz   txa
        lsr
        lsr
        tay
        lda zdst
        clc
        adc colofs_lo,y
        sta zdst
        lda zdst+1
        adc colofs_hi,y
        sta zdst+1
        txa
        and #3
        sta g_m
        lda g_c                         ; rooli bittipaikkaan: taulu [rooli * 4 + pikseli]
        asl
        asl
        ora g_m
        tax
        ldy #0
        lda (zdst),y
        and pclr16,x
        ora role16,x
        sta (zdst),y
        rts

; bound: päivittää päällyksen rajat pisteellä (X, Y)
bound
        cpx ox0
        bcs +
        stx ox0
+       cpx ox1
        bcc +
        stx ox1
+       cpy oy0
        bcs +
        sty oy0
+       cpy oy1
        bcc +
        sty oy1
+       rts

; plot0: musta pikseli X = x, Y = y takapuskuriin
plot0
        lda bmrow_lo,y
        sta zdst
        lda bmrow_hi,y
        clc
        adc bhi
        sta zdst+1
        txa
        lsr
        lsr
        tay
        lda zdst
        clc
        adc colofs_lo,y
        sta zdst
        lda zdst+1
        adc colofs_hi,y
        sta zdst+1
        txa
        and #3
        tax
        ldy #0
        lda (zdst),y
        and pclr,x
        sta (zdst),y
        rts

pclr    .byte $3f, $cf, $f3, $fc

; ------------------------------------------------------------------ kupera monikulmio
; poly: np kärkeä (px, py) vastapäivään ruudulla (kuormaaja.py tarkistaa), täyttö sävyllä tone (PAT) ja musta
; ääriviiva rivin reunoissa (ligne claire): alaspäin menevät reunat ovat vasen reuna (xl_t), ylöspäin oikea (xr_t).
; x mitataan monikulmion vasemmasta sarakkeesta (mcol), joten Y = sarake * 8 riittää. Rivit 144:stä alas leikataan.
poly
        lda #255
        sta pya
        sta minx
        lda #0
        sta pyb
        ldx #0
-       stx pe
        ldy py,x
        lda px,x
        tax
        jsr bound
        ldx pe
        lda px,x
        cmp minx
        bcs +
        sta minx
+       lda py,x
        cmp pya
        bcs +
        sta pya
+       cmp pyb
        bcc +
        sta pyb
+       inx
        cpx np
        bne -
        lda pyb
        cmp #PH
        bcc +
        lda #PH-1
        sta pyb
+       lda pyb
        cmp pya
        bcs +
        rts                             ; kokonaan alareunan alla
+       lda minx                        ; vasen sarake ja sen osoite
        lsr
        lsr
        tax
        asl
        asl
        sta mx4
        lda colofs_lo,x
        sta mlo
        lda colofs_hi,x
        clc
        adc bhi
        sta mhi
        txa                             ; kuvio sarakkeen pariteetin mukaan: patp+0 parillinen, +8 pariton (Y & 8)
        and #1
        sta tmp
        lda tone
        asl
        asl
        asl
        ora tmp
        tax
        .for r in range(4)
        lda PAT+r*2,x
        sta prow+r
        txa
        eor #1
        tax
        lda PAT+r*2,x
        sta prow+4+r
        txa
        eor #1
        tax
        .endfor
        lda #0                          ; reunat
        sta pe
_edges  jsr edge_pts
        lda yb
        cmp ya
        beq _enext                      ; vaakareuna: päät tulevat viereisistä reunoista
        bcs _left
        ldx xb                          ; ylöspäin: oikea reuna, kuljetaan alhaalta ylös vaihtamalla päät
        lda xa
        sta xb
        stx xa
        ldx yb
        lda ya
        sta yb
        stx ya
        lda #<xr_t
        ldx #>xr_t
        bne _walk
_left   lda #<xl_t
        ldx #>xl_t
_walk   sta wst+1
        stx wst+2
        jsr walk
_enext  inc pe
        lda pe
        cmp np
        bne _edges
        ldy pya                         ; rivit
_row    sty yy
        lda xl_t,y
        sec
        sbc mx4
        sta lx
        lda xr_t,y
        sec
        sbc mx4
        sta rx
        cmp lx
        bcs +
        jmp _rnext                      ; tyhjä rivi
+       lda bmrow_lo,y                  ; (itsemuokkaus: bittikartta / spritekangas)
prt_lo  = * - 3
        clc
        adc mlo
        sta zdst
        lda bmrow_hi,y
prt_hi  = * - 3
        adc mhi
        sta zdst+1
        lda nool                        ; ilman ääriviivaa (valuva hiekka): kuvio virtaa rivisiirrolla
        bne _flow
        cpy pya                         ; ylin ja alin rivi kokonaan mustana
        beq _black
        cpy pyb
        beq _black
        tya
        and #3
        tax
        lda prow,x
        sta patp
        lda prow+4,x
        sta patp+8
        jsr fill
        ; ääriviivat: reunapikselit lx ja rx tulivat täytössä; loivalla reunalla ajo naapuririvin reunaan asti
        ldy yy
        lda xl_t-1,y                    ; vasen: d = max(xl[y-1], xl[y+1]) - xl[y], ajo lx+1 .. lx+d-1
        cmp xl_t+1,y
        bcs +
        lda xl_t+1,y
+       sec
        sbc xl_t,y
        bcc _right
        cmp #2
        bcc _right
        adc lx                          ; C = 1: lx + d + 1
        sec
        sbc #2                          ; lx + d - 1
        cmp rx
        bcc +
        lda rx
+       tax
        lda lx
        jsr blackrun
_right  ldy yy
        lda xr_t-1,y                    ; oikea: d = xr[y] - min(xr[y-1], xr[y+1]), ajo rx-d+1 .. rx
        cmp xr_t+1,y
        bcc +
        lda xr_t+1,y
+       sta tmp
        lda xr_t,y
        sec
        sbc tmp
        bcc _rnext
        cmp #2
        bcc _rnext
        sta tmp
        lda rx
        sec
        sbc tmp
        clc
        adc #1
        bcc +
        lda lx
+       cmp lx
        bcs +
        lda lx
+       ldx rx
        jsr blackrun
        jmp _rnext
_black  lda #0
        sta patp
        sta patp+8
        jsr fill
        jmp _rnext
_flow   tya
        sec
        sbc pflow
        and #3
        tax
        lda prow,x
        sta patp
        lda prow+4,x
        sta patp+8
        lda #$ff
        sta lpix
        sta rpix
        jsr fill_np
_rnext  ldy yy
        cpy pyb
        iny
        bcs +
        jmp _row
+       rts

; blackrun: pikselit A..X mustiksi rivillä zdst (x' monikulmion vasemmasta sarakkeesta)
blackrun
        stx rx2
        tax
        lda lmask_t,x
        ldy ytab,x
        ldx rx2
        sty yend2
        ldy ytab,x
        sty yb2
        ldy yend2
        cpy yb2
        bne _two
        and rmask_t,x
        eor #$ff
        and (zdst),y
        sta (zdst),y
        rts
_two    eor #$ff                        ; vasen tavu, välit nollaksi, oikea tavu
        and (zdst),y
        sta (zdst),y
-       tya
        clc
        adc #8
        tay
        cpy yb2
        beq +
        lda #0
        sta (zdst),y
        beq -
+       lda rmask_t,x
        eor #$ff
        and (zdst),y
        sta (zdst),y
        rts

; fill: rivin pikselit lx..rx kuviolla patp (Y & 8 valitsee parillisen / parittoman sarakkeen kuvion), päätypikselit
; lx ja rx mustina (ääriviiva). Reunatavujen maskit tauluista: lmk_t = vasemman tavun kuviopikselit (lx musta),
; nlm_t = vanhat pikselit, rmk_t ja nrm_t samoin oikealle.
fill
        ldx rx
        lda ytab,x
        sta yend
        ldx lx
        ldy ytab,x
        cpy yend
        bne _wide
        lda lmk_t,x                     ; yksi tavu: kuviopikselit lx+1..rx-1, vanhat lx:n vasemmalla ja rx:n oikealla
        ldx rx
        and rmk_t,x
        sta smask
        ldx lx
        lda nlm_t,x
        ldx rx
        ora nrm_t,x
        and (zdst),y
        sta lpix
        tya
        and #8
        tax
        lda patp,x
        and smask
        ora lpix
        sta (zdst),y
        rts
_wide   lda nlm_t,x                     ; vasen tavu
        and (zdst),y
        sta lpix
        lda lmk_t,x
        sta smask
        tya
        and #8
        tax
        lda patp,x
        and smask
        ora lpix
        sta (zdst),y
-       tya                             ; välitavut
        clc
        adc #8
        tay
        cpy yend
        beq +
        and #8
        tax
        lda patp,x
        sta (zdst),y
        jmp -
+       ldx rx                          ; oikea tavu
        lda nrm_t,x
        and (zdst),y
        sta lpix
        lda rmk_t,x
        sta smask
        tya
        and #8
        tax
        lda patp,x
        and smask
        ora lpix
        sta (zdst),y
        rts

fill_np                                 ; lpix / rpix valmiina
        ldx rx
        lda ytab,x
        sta yend
        lda rmask_t,x
        sta rmsk
        ldx lx
        ldy ytab,x
        lda lmask_t,x
        cpy yend
        bne _wide
        and rmsk                        ; yksi tavu: molemmat päät
        sta smask
        lda lpix
        and rpix
        sta lpix
        jmp _one
_wide   sta smask
        jsr _one                        ; vasen reuna
-       tya
        clc
        adc #8
        tay
        cpy yend
        beq _last
        and #8
        tax
        lda patp,x
        sta (zdst),y
        jmp -
_last   lda rmsk
        sta smask
        lda rpix
        sta lpix
_one    tya                             ; (vanha & ~m) | (kuvio & päätypikseli & m)
        and #8
        tax
        lda patp,x
        and lpix
        eor (zdst),y
        and smask
        eor (zdst),y
        sta (zdst),y
        rts

; edge_pts: reunan pe päät (xa, ya) - (xb, yb), x mitattuna mx4:stä EI vielä (walk vähentää)
edge_pts
        ldx pe
        lda px,x
        sta xa
        lda py,x
        sta ya
        inx
        cpx np
        bne +
        ldx #0
+       lda px,x
        sta xb
        lda py,x
        sta yb
        rts

; walk: reuna (xa, ya) -> (xb, yb), yb > ya, x jokaiselle riville tauluun (wst, itsemuokkaus) 8.8-kiintopisteenä;
; rivit 144:stä alas jätetään pois
walk
        lda yb
        sec
        sbc ya
        sta ddy
        lda xb
        sec
        sbc xa
        ldx #0
        bcs +
        eor #$ff
        adc #1
        ldx #1
+       sta ddx
        stx sx
        lda #0                          ; kulmakerroin |dx| / dy 8.8: kokonaisosa q jakamalla, murto-osa 8 bittiä
        sta q
        lda ddx
-       cmp ddy
        bcc +
        sbc ddy
        inc q
        bne -
+       ldx #8                          ; murto: (jakojäännös << 8) / ddy
-       asl
        bcs _big
        cmp ddy
        bcc +
_big    sbc ddy
        sec
+       rol rem
        dex
        bne -
        lda sx                          ; vasemmalle: kerroin negatiiviseksi
        beq +
        lda rem
        eor #$ff
        clc
        adc #1
        sta rem
        lda q
        eor #$ff
        adc #0
        sta q
+       lda #$80                        ; pyöristys
        sta err
        ldy ya
        lda xa
-       cpy #PH
        bcs wdone
wst     sta xl_t,y
        cpy yb
        beq wdone
        iny
        tax
        lda err
        clc
        adc rem
        sta err
        txa
        adc q
        jmp -
wdone   rts

; ------------------------------------------------------------------ yhteiset taulut
        .include "kpcommon.asm"
bmrow_lo .byte <(PIC + (range(144) >> 3) * 320 + (range(144) & 7))
bmrow_hi .byte >(PIC + (range(144) >> 3) * 320 + (range(144) & 7))
colofs_lo .byte <(range(40) * 8)
colofs_hi .byte >(range(40) * 8)
cl_lo   .byte <(CL1)                    ; puhtaan taustan rivit (kuva 1; kuva 2 kirjoittaa omansa)
cl_hi   .byte >(CL1)
        .byte 0
xl_t    .fill 145                       ; monikulmion rivien reunat (ylimääräiset tavut naapuririvien lukuun)
        .byte 0
xr_t    .fill 145
prow    .fill 8                         ; kuvion rivit 0-3 parillinen, 4-7 pariton sarake
patp    .fill 9                         ; +0 parillinen, +8 pariton sarake
ytab    .byte (range(64) >> 2) * 8      ; x' -> Y (sarake * 8); monikulmio alle 64 px leveä
pclr_t  .byte [$3f, $cf, $f3, $fc] x 16
lmask_t .byte [$ff, $3f, $0f, $03] x 16 ; pikselit x..3
rmask_t .byte [$c0, $f0, $fc, $ff] x 16 ; pikselit 0..x
lmk_t   .byte [$3f, $0f, $03, $00] x 16 ; vasen reunatavu: kuvio pikseleihin x+1..3 (x musta)
nlm_t   .byte [$00, $c0, $f0, $fc] x 16 ; vasen reunatavu: vanhat pikselit 0..x-1
rmk_t   .byte [$00, $c0, $f0, $fc] x 16 ; oikea reunatavu: kuvio pikseleihin 0..x-1 (x musta)
nrm_t   .byte [$3f, $0f, $03, $00] x 16 ; oikea reunatavu: vanhat pikselit x+1..3
pclr16  .byte [$3f, $cf, $f3, $fc] x 4
role16  .byte (range(16) >> 2) << (6 - 2 * (range(16) & 3))
g_rnd   .byte $5a
g_c     .byte 0
g_hi    .byte 0
g_m     .byte 0
core_end

; ================================================================== kuva 1 (core_end-code_end): kuvan 2 koodi latautuu tähän
; ------------------------------------------------------------------ sisääntulot
; kp_init: nollasivu, ruutujen reunarivit mustiksi, puskuri B = A, puhdas tausta, spritet pankkiin 2
kp_init
        ldx #ZP0
        lda #0
-       sta $00,x
        inx
        cpx #zp_end
        bne -
        ldx #PICS-1
-       .for s in (SCR1, SCR2)                  ; SCR3 kp2_initissä (pankki 3 vapaa kuvan 1 aikana)
        sta s,x
        sta s+PICS+SCR_N,x
        sta s+PICS+SCR_N+40,x
        .endfor
        dex
        bpl -
        #fcopy SCR1+PICS, SCR2+PICS, SCR_N
        #fcopy $4000+PUFFX, $8000+PUFFX, 192
        #fcopy $6000+PIC, $a000+PIC, BMP_N
        ldx #0                          ; puhdas tausta merkkiriveittäin
-       lda clrow_lo,x
        sta zdst
        lda clrow_hi,x
        sta zdst+1
        txa
        asl
        asl
        asl
        adc #ZONE_Y0                    ; pikselirivi
        tay
        lda bmrow_lo,y
        sta zsrc
        lda bmrow_hi,y
        clc
        adc #$60
        sta zsrc+1
        txa
        pha
        ldx #0
        ldy #CLROW_N
        jsr fcopy_n
        pla
        tax
        inx
        cpx #NCLROW
        bne -
        ldx #NGR                        ; jyvät vapaiksi
        lda #0
-       sta gland-1,x
        dex
        bne -
        lda #ZONE_Y0                    ; palautettavat rivit
        sta zy0
        lda #ZONE_Y1
        sta zy1
        lda #0                          ; kehys 0 puskuriin B (kp_go vain vaihtaa sen näkyviin)
        sta shown
        sta fnow
        sta fnow+1
        jsr job1_t
-       jsr poses                       ; varret ja kauha valmiiksi ennen ensimmäistä kuvaa
        lda asflip
        and bsflip
        beq -
        rts

; kp_go: värimuisti, VIC (pankki 1), spritet ja oma IRQ riville IRQ_LINE; palaa heti
; kp_show: kuvan 1 kehys 0 ennen kelloa (runko #S_SHOW, myös koko demossa I_SHOW): värimuisti ja VIC kuvaan, jonka
; kp_go:n vaihto näyttää (kp_init piirsi sen molempiin puskureihin), ilman IRQ:ta ja spritejä; ei muuta kohtauksen tilaa
kp_show
        ldx #0
        txa
-       sta $d800,x
        sta $d900,x
        sta $da00,x
        sta $dae8,x
        inx
        bne -
        ldx #<COL1
        ldy #>COL1
        jsr col_copy
        lda shown                       ; do_flip:in tuleva puskuri
        eor #1
        tax
        lda fbank,x
        sta $dd00
        lda #$18                        ; ruutu +$0400, bittikartta +$2000 pankissa
        sta $d018
        lda #$18
        sta $d016
        lda #0
        sta $d021
        sta $d020
        sta $d015
        lda #$3b
        sta $d011
        rts

kp_go                                   ; värimuisti ja pankki kp_show:ssa (aina ennen kelloa)
        sei
        lda #0
        sta $d017
        sta $d01d
        sta $d01b
        sta $d025                       ; spritet: musta, oranssi ($d026), oma keltainen
        lda #$ff
        sta $d01c
        lda #8
        sta $d026
        lda #7
        ldx #7
-       sta $d027,x
        dex
        bpl -
        jsr do_flip
        jsr spr1                        ; spritet heti oikeaan kohtaan
        lda #$4c                        ; IRQ-koukku: varret ja kauha spriteinä joka kehys
        sta irqhook
        lda #<spr1
        sta irqhook+1
        lda #>spr1
        sta irqhook+2
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        lda #IRQ_LINE
        sta $d012
        lda #$3b
        sta $d011
        lda #$ff
        sta $d019
        lda #1
        sta $d01a
        cli
        rts

; ------------------------------------------------------------------ kuva 1: kuormaaja
job1
        lda DFRAME
        sta fnow
        lda DFRAME+1
        sta fnow+1
job1_t                                  ; aika fnow:ssa (kp_init piirtää kehyksen 0 ennen kelloa)
        lda fnow+1                      ; kehys / STEP (kehys < 1024)
        sta tmp
        lda fnow
        lsr tmp
        ror
        lsr tmp
        ror
        cmp #NSTEP
        bcc +
        lda #NSTEP-1
+       tax
        stx g_idx
        lda ST_AX,x                     ; ankkuri 2 kehyksen tarkkuudella: väliaskel keskiarvona
        sta ax
        lda ST_AY,x
        sta ay
        lda fnow
        and #2
        beq +
        lda ST_AX+1,x                   ; a + (b - a) / 2 etumerkillisenä (ankkuri voi olla < 0)
        sec
        sbc ax
        cmp #$80
        ror
        clc
        adc ax
        sta ax
        lda ST_AY+1,x
        sec
        sbc ay
        cmp #$80
        ror
        clc
        adc ay
        sta ay
+
        txa                             ; asennot 2 kehyksen välein: indeksi kehys / 2
        asl
        tay
        lda fnow
        and #2
        beq +
        iny
+       lda ST_IA,y
        sta ia
        lda ST_IP,y
        sta ip
        lda ST_WT,x
        sta wt
        lda ST_LD,x
        sta ld
        lda #0
        sta moved
        lda flip
        beq +
        jmp poses                       ; bittikartta odottaa vaihtoa: asentotyötä sillä aikaa
+       lda shown
        eor #1
        sta back
        tax
        lda bmp_hi,x
        sta bhi
        lda #0
        sta idle
        lda ax                          ; col0 = (ax + BODY_OX) >> 2 etumerkillisenä, siirto alimmat bitit
        clc
        adc #<BODY_OX
        tax
        and #3
        sta sft
        txa
        cmp #$80
        ror
        cmp #$80
        ror
        sta col0
        lda ay
        clc
        adc #<BODY_OY
        sta by
        ldx back                        ; ei muutoksia tähän puskuriin: vaihto IRQ:ssa joka kehys
        lda col0
        cmp lst_c0,x
        bne _work
        lda sft
        cmp lst_sf,x
        bne _work
        lda by
        cmp lst_by,x
        bne _work
        lda wt
        cmp lst_wt,x
        bne _work
        lda ov_c1,x                     ; hiekkaa tai jyviä
        ora g_alive
        bne _work
        ldx g_idx
        lda ST_PR,x
        bne _work
        inc idle
        jmp poses
_work   ldx back                        ; 1. edellisen hiekan ja pulttien palautus
        jsr ov_rect
        jsr copyrect
p_body  ldx back                        ; 2. runko
        lda col0
        cmp lst_c0,x
        bne _moved
        lda sft
        cmp lst_sf,x
        bne _moved
        lda by
        cmp lst_by,x
        bne _moved
        jsr ov_rect                     ; sama paikka: hiekan alue uudelleen
        jsr blitrect
        ldx back
        lda wt
        cmp lst_wt,x
        beq _over
        jsr hubs                        ; pyörän kulma vaihtui: vanhat pultit pois
        jmp _over
_moved  inc moved
        jsr strips                      ; vanhan laatikon reunat, jotka jäävät uuden ulkopuolelle
        lda col0
        sta r0
        clc
        adc #BODY_COLS
        sta r1
        lda by
        sta ry0
        clc
        adc #BODY_H
        sta ry1
        jsr blitrect
        ldx back
        lda col0
        sta lst_c0,x
        lda sft
        sta lst_sf,x
        lda by
        sta lst_by,x
_over   ldx back
        lda wt
        sta lst_wt,x
p_over  jsr overlay                     ; pultit ja hiekka
        ldx back
        lda ax
        sta buf_ax,x
        lda ay
        sta buf_ay,x
        lda #1
        sta flip
        lda moved                       ; asentotyö vaihtopyynnön jälkeen (vaihto ei odota sitä); ei rungon
        bne +                           ; siirtokierroksella eikä jos kehys jo vaihtui, jotta seuraava kuva
        lda DFRAME                      ; ehtii kehysparissa
        cmp fnow
        bne +
        jmp poses
+       rts

; hubs: napojen ympäristö rungosta uudelleen (vanhat pultit pois)
hubs
        ldx #NWHEEL-1
-       stx ow
        lda ax
        clc
        adc HCX,x
        sec
        sbc #6
        cmp #$80
        ror
        cmp #$80
        ror
        sta r0
        clc
        adc #4
        sta r1
        ldx ow
        lda ay
        clc
        adc HCY,x
        sec
        sbc #6
        sta ry0
        clc
        adc #13
        sta ry1
        jsr blitrect
        ldx ow
        dex
        bpl -
        rts

; ------------------------------------------------------------------ varret ja kauha spriteinä
; Varret (spritet 4-7) ja kauha (0-3) ovat 2 x 2 MC-spriteä (24 x 42 MC-px). Kun nostokulma tai kallistus vaihtuu,
; asento piirretään reaaliajassa spritekankaalle (bittikartan solumuoto 6 x 48, samat monikulmio- ja
; suunnikasrutiinit), muunnetaan spriteiksi (TRS: kankaan musta -> %01, tyhjä -> %00) takimmaiseen sarjaan
; molempiin pankkeihin ja vaihdetaan IRQ:ssa. Paikka lasketaan joka kehys näkyvän rungon ankkurista.
CANV    = $5e00                         ; kangas 6 x 48 (288 t), pankki 1 (rungon esisiirtojen jälkeen)
SPA_ARM = [$2000, $2100]                ; sarjat pankin sisällä (pankit 1 ja 2 samoissa kohdissa)
SPA_BK  = [$2200, $3a40]

poses
        lda ptask                       ; asentotyö paloina: yksi pala kierrosta kohden
        bne _run
        lda asflip                      ; uusi työ: varret
        bne _bk
        lda ia
        cmp arm_ip
        beq _bk
        sta arm_ip
        tax
        lda ARH,x                       ; asennon rivit
        sta pn
        lda aset
        eor #1
        sta pset
        lda #1
        bne _new
_bk     lda bsflip                      ; kauha (kuorma mukana avaimessa)
        bne _idle
        lda ld
        lsr
        ror
        ora ip
        cmp bk_key
        beq _idle
        sta bk_key
        lda ip
        sta bk_ip
        lda ld
        sta bk_ld
        ldx ip
        lda BKH,x
        sta pn
        lda bset
        eor #1
        ora #2
        sta pset
        lda #2
_new    sta ptask
        lda #0
        sta pstep
        lda pn                          ; tyhjennettävät kankaan rivit: max(uusi, edellinen piirto)
        cmp canv_rows
        bcs +
        lda canv_rows
+       sta crows
        lda pn
        sta canv_rows
        ldx pset                        ; muunnettavat rivit: max(uusi, sarjan edellinen)
        cmp srows,x
        bcs +
        lda srows,x
+       sta cn
        lda pn
        sta srows,x
_run    jsr to_canvas
        lda ptask
        cmp #1
        bne _bucket
        lda pstep                       ; varret: 0 tyhjennys, 1-2 varret, 3-4 muunnos kaistoittain
        bne +
        jsr canv_clear
        jmp _step
+       cmp #3
        bcs +
        sec
        sbc #1
        jsr render_arm
        jmp _step
+       sbc #3
        tax
        lda aset
        eor #1
        tay
        lda #0
        sta cs_lo0
        lda spa_arm_hi,y
        jsr canv_band
        lda pstep
        cmp #4
        bne _step
        inc asflip
        jmp _end
_bucket lda pstep                       ; kauha: 0 tyhjennys ja kärjet, 1-7 pinnat, 8-9 muunnos
        bne +
        jsr canv_clear
        jsr bucket_verts
        jmp _step
+       cmp #8
        bcs +
        sec
        sbc #1
        jsr bucket_face
        jmp _step
+       sbc #8
        tax
        lda bset
        eor #1
        tay
        lda spa_bk_lo,y
        sta cs_lo0
        lda spa_bk_hi,y
        jsr canv_band
        lda pstep
        cmp #9
        bne _step
        inc bsflip
_end    lda #0
        sta ptask
        jsr to_bitmap
        lda DFRAME
        cmp fnow
        bne +
        jmp poses
+       rts
_step   inc pstep
        jsr to_bitmap
        lda DFRAME                      ; aikaa jäljellä tässä kehyksessä: seuraava pala heti
        cmp fnow
        bne +
        jmp poses
+       rts
_idle   rts

spa_arm_hi .byte >SPA_ARM
spa_bk_lo .byte <SPA_BK
spa_bk_hi .byte >SPA_BK

; to_canvas / to_bitmap: monikulmion ja suunnikkaan kohde
to_canvas
        lda #<cv_lo
        sta prt_lo+1
        sta brt_lo+1
        lda #>cv_lo
        sta prt_lo+2
        sta brt_lo+2
        lda #<cv_hi
        sta prt_hi+1
        sta brt_hi+1
        lda #>cv_hi
        sta prt_hi+2
        sta brt_hi+2
        lda #48
        sta bst_lo+1
        lda #0
        sta bst_hi+1
        sta bhi
        rts
canv_clear
        lda crows                       ; kangas tyhjäksi (rooli 1) käytetyiltä solurileiltä: (rivit + 7) / 8 * 48
        clc
        adc #7
        lsr
        lsr
        lsr
        tax
        lda cl48,x
        tax
        lda #$55
        cpx #0
        beq _all
-       dex
        sta CANV,x
        bne -
        rts
_all    sta CANV+32,x                   ; 6 soluriviä (288 t)
        sta CANV,x
        inx
        bne _all
        rts
cl48    .byte 1, 48, 96, 144, 192, 240, 0

to_bitmap
        lda #<bmrow_lo
        sta prt_lo+1
        sta brt_lo+1
        lda #>bmrow_lo
        sta prt_lo+2
        sta brt_lo+2
        lda #<bmrow_hi
        sta prt_hi+1
        sta brt_hi+1
        lda #>bmrow_hi
        sta prt_hi+2
        sta brt_hi+2
        lda #<320
        sta bst_lo+1
        lda #>320
        sta bst_hi+1
        rts

; render_arm: varsi A (0 kauempi, 1 lähempi) kankaalle: kärjet AXjk / AYjk[arm_ip] - AOX / AOY
render_arm
        ldx arm_ip
        cmp #0
        bne _a1
        lda AX00,x
        sec
        sbc AOX,x
        sta px+0
        lda AY00,x
        sec
        sbc AOY,x
        sta py+0
        lda AX01,x
        sec
        sbc AOX,x
        sta px+1
        lda AY01,x
        sec
        sbc AOY,x
        sta py+1
        lda AX02,x
        sec
        sbc AOX,x
        sta px+2
        lda AY02,x
        sec
        sbc AOY,x
        sta py+2
        lda AX03,x
        sec
        sbc AOX,x
        sta px+3
        lda AY03,x
        sec
        sbc AOY,x
        sta py+3
        jmp bar
_a1
        lda AX10,x
        sec
        sbc AOX,x
        sta px+0
        lda AY10,x
        sec
        sbc AOY,x
        sta py+0
        lda AX11,x
        sec
        sbc AOX,x
        sta px+1
        lda AY11,x
        sec
        sbc AOY,x
        sta py+1
        lda AX12,x
        sec
        sbc AOX,x
        sta px+2
        lda AY12,x
        sec
        sbc AOY,x
        sta py+2
        lda AX13,x
        sec
        sbc AOX,x
        sta px+3
        lda AY13,x
        sec
        sbc AOY,x
        sta py+3
        jmp bar

; canv_band: kankaan kaista X -> sarja (A = sarjan ylätavu pankin sisällä, alatavu cs_lo0) molempiin pankkeihin:
; sprite (sx, sy) = sarja + (2 sy + sx) * 64, rivi r tavu b = kankaan (sx * 3 + b) * 8 riviltä 21 sy + r
canv_band
        sta cs_hi0
        stx cs_sy
        lda cs_lo0                      ; kohteiden kannat: pankki 1 $4000 + sarja + sy * 128, pankki 2 $8000 + ...
        clc
        adc cs_off,x
        sta cs_b
        lda cs_hi0
        adc #0
        sta cs_b+1
        lda cs_b
        clc
        adc #0
        sta _d000+1
        sta _d001+1
        sta _d002+1
        lda cs_b+1
        adc #$40
        sta _d000+2
        sta _d001+2
        sta _d002+2
        lda cs_b
        clc
        adc #0
        sta _d010+1
        sta _d011+1
        sta _d012+1
        lda cs_b+1
        adc #$80
        sta _d010+2
        sta _d011+2
        sta _d012+2
        lda cs_b
        clc
        adc #64
        sta _d100+1
        sta _d101+1
        sta _d102+1
        lda cs_b+1
        adc #$40
        sta _d100+2
        sta _d101+2
        sta _d102+2
        lda cs_b
        clc
        adc #64
        sta _d110+1
        sta _d111+1
        sta _d112+1
        lda cs_b+1
        adc #$80
        sta _d110+2
        sta _d111+2
        sta _d112+2
        lda cs_sy                       ; rivejä tässä kaistassa: cn - 21 sy rajattuna 0..21
        beq +
        lda cn
        sec
        sbc #21
        bcs ++
        rts
+       lda cn
+       beq _none
        cmp #21
        bcc +
        lda #21
+       sta cs_end
        asl
        adc cs_end
        sta cs_end                      ; * 3
        ldx #0                          ; rivi r: X = 3 r, kangasrivi y = 21 sy + r
        lda cs_sy
        beq +
        lda #21
+       sta cs_y
_row    ldy cs_y
        lda cv_lo,y
        sta src
        lda cv_hi,y
        sta src+1
        ldy #0
        lda (src),y
        tay
        lda TRS,y
_d000 sta $ffff,x
_d010 sta $ffff,x
        inx
        ldy #8
        lda (src),y
        tay
        lda TRS,y
_d001 sta $ffff,x
_d011 sta $ffff,x
        inx
        ldy #16
        lda (src),y
        tay
        lda TRS,y
_d002 sta $ffff,x
_d012 sta $ffff,x
        dex
        dex
        ldy #24
        lda (src),y
        tay
        lda TRS,y
_d100 sta $ffff,x
_d110 sta $ffff,x
        inx
        ldy #32
        lda (src),y
        tay
        lda TRS,y
_d101 sta $ffff,x
_d111 sta $ffff,x
        inx
        ldy #40
        lda (src),y
        tay
        lda TRS,y
_d102 sta $ffff,x
_d112 sta $ffff,x
        inx
        inc cs_y
        cpx cs_end
        bne _row
_none   rts

cs_off  .byte 0, 128
cs_end  .byte 0
pn      .byte 0
pset    .byte 0
crows   .byte 42
cn      .byte 42
canv_rows .byte 42
srows   .byte 42, 42, 42, 42
cs_lo0  .byte 0
cs_hi0  .byte 0
cs_sy   .byte 0
cs_y    .byte 0
cs_b    .word 0

; spr1: IRQ-koukku joka kehys: valmiit sarjat näkyviin, spritejen paikat näkyvän rungon ankkurista, jakorivi
; kuva-alueen alareunaan (spritet pois letterboxista)
spr1
        lda asflip
        beq +
        lda aset
        eor #1
        sta aset
        lda arm_ip
        sta arm_id
        lda #0
        sta asflip
+       lda bsflip
        beq +
        lda bset
        eor #1
        sta bset
        lda bk_ip
        sta bk_id
        lda #0
        sta bsflip
        ldx bset
        lda ptr_bk,x
        ldx #0
-       sta SCR1+$3f8,x
        sta SCR2+$3f8,x
        clc
        adc #1
        inx
        cpx #4
        bne -
+       ldx shown                       ; näkyvän rungon ankkuri
        lda buf_ax,x
        sta sx0
        lda buf_ay,x
        sta sy0
        ldx arm_id                      ; varret: ankkuri + AOX / AOY
        lda sx0
        clc
        adc AOX,x
        sta so_x+1
        lda sy0
        clc
        adc AOY,x
        sta so_y+1
        ldx arm_id                      ; kauha: ankkuri + näkyvien varsien tappi + BOX / BOY (nykyisestä
        lda sx0                         ; nostokulmasta kauha irtoaisi varsista, kun varsien asento on jäljessä)
        clc
        adc PINX,x
        ldy bk_id
        clc
        adc BOX,y
        sta so_x
        lda sy0
        clc
        adc PINY,x
        clc
        adc BOY,y
        sta so_y
        lda #0
        sta d010a
        ldx #7                          ; sprite X: ryhmä X >> 2, (X & 1) * 12, (X & 2) / 2 * 21
-       txa
        lsr
        lsr
        tay
        lda so_x,y
        clc
        adc spr_dx,x
        bpl _pos                        ; etumerkillinen: alle -11 piiloon
        cmp #$f5
        bcs _neg
        txa
        asl
        tay
        lda #0
        sta $d001,y
        jmp _n
_neg    asl                             ; -11..-1: 24 + 2 x mahtuu tavuun
        clc
        adc #24
        sta xlo
        jmp _st
_pos    asl                             ; 0..127: 24 + 2 x, ylin bitti $d010:een
        clc
        adc #24
        sta xlo
        bcc _st
        lda bit8,x
        ora d010a
        sta d010a
_st     txa                             ; paikat varjotauluun (0-3 heti, varret 4-7 jakorivillä)
        asl
        tay
        lda xlo
        sta spos,y
        txa
        lsr
        lsr
        tay
        lda so_y,y
        clc
        adc spr_dy,x
        clc
        adc #74
        pha
        txa
        asl
        tay
        pla
        sta spos+1,y
_n      dex
        bpl -
        ldx #7                          ; kauha nyt
-       lda spos,x
        sta $d000,x
        dex
        bpl -
        lda spos+9                      ; jakorivi: varsien yläreuna - 5 (savu sen yläpuolella)
        sec
        sbc #5
        sta split
        jsr puffs
        lda d010a
        and #$0f
        ora pf_msb
        sta $d010
        lda #$0f                        ; kauha MC, savu hires
        sta $d01c
        lda #$ff
        sta $d015
        lda split
        sta $d012
        lda #<spl
        sta $fffe
        lda #>spl
        sta $ffff
        rts

; spl: jakorivi: spritet 4-7 savusta varsiksi, sitten kuva-alueen alareuna
spl
        pha
        txa
        pha
        asl $d019
        ldx #7
-       lda spos+8,x
        sta $d008,x
        dex
        bpl -
        lda $d010
        and #$0f
        sta itmp
        lda d010a
        and #$f0
        ora itmp
        sta $d010
        lda #7
        sta $d02b
        sta $d02c
        sta $d02d
        sta $d02e
        lda #$ff
        sta $d01c
        ldx aset
        lda ptr_arm,x
        ldx shown
        beq +
        sta SCR2+$3fc
        clc
        adc #1
        sta SCR2+$3fd
        adc #1
        sta SCR2+$3fe
        adc #1
        sta SCR2+$3ff
        jmp ++
+       sta SCR1+$3fc
        clc
        adc #1
        sta SCR1+$3fd
        adc #1
        sta SCR1+$3fe
        adc #1
        sta SCR1+$3ff
+       lda #74 + PH                    ; spritet pois kuva-alueen alla
        sta $d012
        lda #<scut
        sta $fffe
        lda #>scut
        sta $ffff
        pla
        tax
        pla
        rti

; puffs: pakokaasu spriteihin 4-7 jakorivin yläpuolelle (pilvi pakoputkesta 9 kehyksen välein, nousee, kasvaa,
; vaalenee, haihtuu 50 kehyksessä; jakorivin alle ulottuva piiloon)
NPUFF   = 4
PUFFX   = $2300                         ; muodot pankin sisällä (osoittimet PUFFX / 64 + 0..2)
puffs
        lda #0
        sta pf_msb
        dec pf_t
        bpl _upd
        lda #8
        sta pf_t
        ldx #NPUFF-1
-       lda pf_age,x
        beq _new
        dex
        bpl -
        bmi _upd
_new    lda #1
        sta pf_age,x
        lda sx0
        clc
        adc #<EXH_DX + 64               ; x + 64 (vasemmalla negatiivinen)
        sta pf_xh,x
        lda sy0
        clc
        adc #<EXH_DY
        sta pf_yh,x
        lda #0
        sta pf_xl,x
        sta pf_yl,x
_upd    ldx #NPUFF-1
_p      txa
        asl
        tay
        lda pf_age,x
        beq _hide
        inc pf_age,x
        lda pf_age,x
        cmp #50
        bcc +
        lda #0
        sta pf_age,x
        beq _hide
+       lda pf_yl,x                     ; nousee 0,5 px, ajautuu 0,25 px kehyksessä
        sec
        sbc #128
        sta pf_yl,x
        bcs +
        dec pf_yh,x
+       lda pf_xl,x
        clc
        adc #64
        sta pf_xl,x
        bcc +
        inc pf_xh,x
+       lda pf_yh,x                     ; y = 74 + yh - 10; alareuna (+21) jakorivin yllä
        clc
        adc #74 - 10
        sta $d009,y
        clc
        adc #21
        cmp split
        bcs _hide
        lda pf_xh,x                     ; x = 2 * (xh - 64) + 24 - 12
        sec
        sbc #64 - 6
        bcc _hide
        asl
        sta $d008,y
        bcc +
        lda pf_bit,x
        ora pf_msb
        sta pf_msb
+       stx itmp2
        ldy pf_age,x
        lda pf_shape,y
        ldy shown
        beq +
        sta SCR2+$3fc,x
        jmp ++
+       sta SCR1+$3fc,x
+       ldy itmp2
        lda pf_age,y
        tay
        lda pf_col,y
        sta $d02b,x
        jmp _n
_hide   lda #0
        sta $d009,y
_n      dex
        bpl _p
        rts

pf_t    .byte 0
pf_msb  .byte 0
split   .byte 0
spos    .fill 16
pf_age  .fill NPUFF
pf_xl   .fill NPUFF
pf_xh   .fill NPUFF
pf_yl   .fill NPUFF
pf_yh   .fill NPUFF
pf_bit  .byte $10, $20, $40, $80
pf_shape .byte [PUFFX / 64] x 14, [PUFFX / 64 + 1] x 16, [PUFFX / 64 + 2] x 21
pf_col  .byte [11] x 20, [12] x 16, [15] x 15

; scut: kuva-alueen alareuna: spritet pois, takaisin riville 250
scut
        pha
        asl $d019
        lda #0
        sta $d015
        lda #IRQ_LINE
        sta $d012
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        pla
        rti

so_x    .byte 0, 0                      ; ryhmän origo: 0 kauha, 1 varret
so_y    .byte 0, 0
sx0     .byte 0
sy0     .byte 0
xlo     .byte 0
d010a   .byte 0
spr_dx  .byte 0, 12, 0, 12, 0, 12, 0, 12
spr_dy  .byte 0, 0, 21, 21, 0, 0, 21, 21
bit8    .byte 1, 2, 4, 8, 16, 32, 64, 128
ptr_arm .byte SPA_ARM[0] / 64, SPA_ARM[1] / 64
ptr_bk  .byte SPA_BK[0] / 64, SPA_BK[1] / 64
aset    .byte 0
bset    .byte 0
asflip  .byte 0
bsflip  .byte 0
arm_ip  .byte $ff                       ; piirretty / näkyvä nostokulma
arm_id  .byte 0
bk_key  .byte $ff
bk_ip   .byte 0
bk_ld   .byte 0
ptask   .byte 0                         ; asentotyö: 0 ei, 1 varret, 2 kauha
pstep   .byte 0
moved   .byte 0
rr      .byte 0
lipx    .byte 0, 0                      ; kauhan huuli ruudulla (hiekka)
lipy    .byte 0, 0
bk_id   .byte 0
buf_ax  .byte 0, 0
buf_ay  .byte 0, 0
lst_wt  .byte $ff, $ff

bmp_hi  .byte $60, $a0                  ; puskurin A / B bittikartan ylätavu

; ov_rect: puskurin X edellinen päällys suorakaiteeksi
ov_rect
        lda ov_c0,x
        sta r0
        lda ov_c1,x
        sta r1
        lda ov_y0,x
        sta ry0
        lda ov_y1,x
        sta ry1
        rts

; strips: vanhan rungon laatikon (lst_*) osat, jotka jäävät uuden ulkopuolelle, palautetaan puhtaasta
strips
        ldx back
        lda lst_c0,x
        cmp #$ff
        bne +
        rts                             ; ei vanhaa
+       sta tmp                         ; vanha col0
        lda lst_by,x
        sta tmp2                        ; vanha by
        lda tmp                         ; sarakeliuska
        cmp col0
        beq _rows
        bmi _left
        lda col0                        ; vanha oikealla: sarakkeet col0+16 .. vanha+16
        clc
        adc #BODY_COLS
        sta r0
        lda tmp
        clc
        adc #BODY_COLS
        sta r1
        jmp _cs
_left   lda tmp                         ; vanha vasemmalla: sarakkeet vanha .. col0
        sta r0
        lda col0
        sta r1
_cs     lda tmp2
        sta ry0
        clc
        adc #BODY_H
        sta ry1
        jsr copyrect
_rows   lda tmp2
        cmp by
        beq _done
        bcc _up
        lda by                          ; vanha alempana: rivit by+H .. vanha+H
        clc
        adc #BODY_H
        sta ry0
        lda tmp2
        clc
        adc #BODY_H
        sta ry1
        jmp _rs
_up     lda tmp2
        sta ry0
        lda by
        sta ry1
_rs     lda tmp
        sta r0
        clc
        adc #BODY_COLS
        sta r1
        jsr copyrect
_done   rts

; blitrect: runko (maski ja data esisiirrosta sft) puhtaan taustan päälle takapuskuriin, alue r0..r1 x ry0..ry1
; rajattuna rungon laatikkoon
blitrect
        lda r0                          ; rungon laatikkoon
        sec
        sbc col0
        bpl +
        lda col0
        sta r0
+       lda col0
        clc
        adc #BODY_COLS
        sta tmp
        lda r1
        sec
        sbc tmp
        bmi +
        lda tmp
        sta r1
+       lda ry0
        cmp by
        bcs +
        lda by
        sta ry0
+       lda by
        clc
        adc #BODY_H
        cmp ry1
        bcs +
        sta ry1
+       jsr clip
        bcc +
        rts
+       lda r1
        sec
        sbc r0
        tax
        lda bs_lo,x
        sta _pa+1
        sta _pr+1
        lda bs_hi,x
        sta _pa+2
        sta _pr+2
        lda #$60
_pa     sta $ffff
        ldx r0                          ; rivin vakiot: sarakkeen r0 siirtymä, puskuri
        lda colofs_lo,x
        sta _c1+1
        sta _c3+1
        lda colofs_hi,x
        sta _c2+1
        clc
        adc bhi
        sta _c4+1
        lda r0                          ; rungon sarake r0 - col0 ja esisiirto: S = muoto + sarake * 8
        sec
        sbc col0
        tax
        ldy sft
        lda shape_lo,y
        clc
        adc colofs_lo,x
        sta _s1+1
        lda shape_hi,y
        adc colofs_hi,x
        sta _s2+1
        lda _s1+1
        clc
        adc #<PLANE
        sta _s3+1
        lda _s2+1
        adc #>PLANE
        sta _s4+1
        lda ry0
        sta yy
        sec
        sbc by
        sta rr
        jmp _full
_row    lda yy                          ; solun sisällä seuraava rivi: osoittimet + 1
        and #7
        beq _full
        lda rr
        and #7
        beq _full
        inc src
        bne +
        inc src+1
+       inc dst
        bne +
        inc dst+1
+       inc msk
        bne +
        inc msk+1
+       inc dat
        bne _go
        inc dat+1
        jmp _go
_full   ldy yy
        lda cl_lo,y
        clc
_c1     adc #0
        sta src
        lda cl_hi,y
_c2     adc #0
        sta src+1
        lda bmrow_lo,y
        clc
_c3     adc #0
        sta dst
        lda bmrow_hi,y
_c4     adc #0
        sta dst+1
        ldx rr                          ; rungon rivi: (r >> 3) * 128 + (r & 7)
        lda grp_lo,x
        clc
_s1     adc #0
        sta msk
        lda grp_hi,x
_s2     adc #0
        sta msk+1
        lda grp_lo,x
        clc
_s3     adc #0
        sta dat
        lda grp_hi,x
_s4     adc #0
        sta dat+1
_go     jsr bslot
        inc rr
        inc yy
        lda yy
        cmp ry1
        bne _row
        lda #$a0
_pr     sta $ffff
        rts

shape_lo .byte <SHAPE0, <SHAPE1, <SHAPE2, <SHAPE3
shape_hi .byte >SHAPE0, >SHAPE1, >SHAPE2, >SHAPE3

bslot
        .for k in range(32)
        ldy #k*8
        lda (src),y
        and (msk),y
        ora (dat),y
        sta (dst),y
        .endfor
        ldy #0
        rts
bs_lo   .byte <(bslot + range(33) * 10)
bs_hi   .byte >(bslot + range(33) * 10)

; ------------------------------------------------------------------ päällys: varret, kauha, pultit
overlay
        lda #255
        sta ox0
        sta oy0
        lda #0
        sta ox1
        sta oy1
        jmp p_blt

; render_bucket: kauha spritekankaalle (kärjet tapista, kankaan origo BOX / BOY)
bucket_verts
        ldx bk_ip                       ; kankaalla: BKXj[ip * 5 + kärki] - BOX[ip]
        lda #0
        sec
        sbc BOX,x
        sta xa
        lda #0
        sec
        sbc BOY,x
        sta ya
        lda bk_ip                       ; ip * 5
        asl
        asl
        adc bk_ip
        tay
        ldx #0
-       lda BKX0,y                      ; kärki k: vx[2k] puoli 0, vx[2k+1] puoli 1
        clc
        adc xa
        sta vx,x
        lda BKY0,y
        clc
        adc ya
        sta vy,x
        lda BKX1,y
        clc
        adc xa
        sta vx+1,x
        lda BKY1,y
        clc
        adc ya
        sta vy+1,x
        iny
        inx
        inx
        cpx #10
        bne -
        rts

; bucket_face: pinta A (0-6), jos näkyy: FTONE[ip * 7 + pinta], kärjet FVERT
bucket_face
        sta oi
        lda bk_ip
        asl
        asl
        asl
        sec
        sbc bk_ip
        clc
        adc oi
        sta fidx
_face   ldx fidx
        lda FTONE,x
        cmp #255
        beq _next
        ldx oi
        cpx #MOUTH
        bne +
        lda #1                          ; suu: tyhjänä tumma sisus, kuormattuna hiekka
        ldx bk_ld
        beq +
        lda #5
+       sta tone
        lda oi                          ; kärjet FVERT[pinta * 5 + i]
        asl
        asl
        adc oi
        tay
        ldx #0
-       lda FVERT,y
        cmp #255
        beq +
        sty tmp
        tay
        lda vx,y
        sta px,x
        lda vy,y
        sta py,x
        ldy tmp
        iny
        inx
        cpx #5
        bne -
+       stx np
        jmp poly
_next   rts

p_blt   lda #0                          ; pultit: HUBX[pyörä * NT * 3 + wt * 3 + pultti], mustat pikselit
        sta ow
_wh     lda wt
        asl
        adc wt
        ldx ow
        beq +
        clc
        adc #NT * 3
+       sta ai
        lda #3
        sta ob
-       ldy ai
        lda HUBX,y
        clc
        adc ax
        sta xa
        lda HUBY,y
        clc
        adc ay
        sta ya
        jsr bolt
        inc ai
        dec ob
        bne -
        inc ow
        lda ow
        cmp #NWHEEL
        bne _wh
p_snd   ldx arm_id                      ; kauhan huuli ruudulla (kärki 2 puolilta 0 ja 1) hiekalle
        lda ax
        clc
        adc PINX,x
        sta xa
        lda ay
        clc
        adc PINY,x
        sta ya
        lda ip
        asl
        asl
        adc ip
        tay
        lda BKX0+2,y
        clc
        adc xa
        sta lipx
        lda BKY0+2,y
        clc
        adc ya
        sta lipy
        lda BKX1+2,y
        clc
        adc xa
        sta lipx+1
        lda BKY1+2,y
        clc
        adc ya
        sta lipy+1
p_gr    jsr grains
p_grd   ldx back                        ; päällyksen rajat talteen (sarakkeet, rivit + 1)
        lda ox0
        lsr
        lsr
        sta ov_c0,x
        lda ox1
        lsr
        lsr
        clc
        adc #1
        sta ov_c1,x
        lda oy0
        sta ov_y0,x
        lda oy1
        clc
        adc #1
        bcc +
        lda #255
+       sta ov_y1,x
        lda ox0                         ; ei päällystä: tyhjä (ov_c1 = 0)
        cmp #255
        bne +
        lda #0
        sta ov_c1,x
+       rts

vx      .fill 10
vy      .fill 10

; bolt: musta pikseli (xa, ya), jos kuva-alueella (rungon päällä: ei päällyksen rajoihin, runko peittää)
bolt
        ldx xa
        cpx #160
        bcs +
        ldy ya
        cpy #ZONE_Y1
        bcs +
        jsr plot0
+       rts

; bar: nostovarsi suunnikkaana (px, py): 0 nivel ylä, 1 nivel ala, 2 tappi ala, 3 tappi ylä (päät pystysuorat,
; kuormaaja.py tarkistaa). Täyttö sarakkeittain: ylä- ja alareuna kiintopisteinä, reunapikselit ja päätysarakkeet
; mustina, välissä kuvio (sävy tone). Halvempi kuin monikulmio pitkälle kapealle varrelle.
bar
        ldx #3
-       stx pe
        ldy py,x
        lda px,x
        tax
        jsr bound
        ldx pe
        dex
        bpl -
        lda px+3                        ; sarakkeita dx = tappi - nivel
        sec
        sbc px
        bne +
        lda #1
+       sta b_dx
        lda py+3                        ; yläreunan kulmakerroin (k3y - k0y) / dx
        sec
        sbc py
        jsr b_slope
        sta b_tsh
        stx b_tsl
        lda py+2                        ; alareunan (k2y - k1y) / dx
        sec
        sbc py+1
        jsr b_slope
        sta b_bsh
        stx b_bsl
        lda py
        sta b_yt
        lda py+1
        sta b_yb
        lda #$80
        sta b_ytf
        sta b_ybf
        lda px
        sta b_x
        lda b_dx
        sta b_n
        inc b_n                         ; sarakkeita dx + 1
_col    ldx b_x                         ; sarake: osoite solurivin alusta, Y = y & 7
        cpx #160
        bcs _skip
        txa
        and #3
        tay
        lda pclr,y
        sta _pc1+1
        sta _pc2+1
        sta _pc3+1
        txa                             ; kuviorivit: b_tab + (x & 7) * 8, päätysarakkeille nollat
        and #7
        asl
        asl
        asl
        clc
        adc #<b_tab
        sta _cv+1
        lda #>b_tab
        adc #0
        sta _cv+2
        lda b_n
        cmp #1
        beq _allb
        lda b_x
        cmp px
        bne _adr
_allb   lda #<b_zero
        sta _cv+1
        lda #>b_zero
        sta _cv+2
_adr    ldx b_x
        txa
        lsr
        lsr
        tax
        lda colofs_lo,x
        sta b_clo
        lda colofs_hi,x
        clc
        adc bhi
        sta b_chi
_rows   ldy b_yt
        cpy #PH
        bcs _skip
        lda b_yb                        ; välipikseleitä m = min(yb, PH) - yt - 1
        cmp #PH
        bcc +
        lda #PH
+       sec
        sbc b_yt
        sta b_m
        jsr b_ptr
        lda (zdst),y                    ; yläreunan pikseli (musta, hiekalla kuvio)
_pc1    and #0
        sta (zdst),y
        dec b_m
        beq _skip
        bmi _skip
-       iny
        cpy #8
        bne +
        jsr b_next
+       dec b_m
        beq _bot
        lda (zdst),y
_pc2    and #0
_cv     ora b_tab,y
        sta (zdst),y
        jmp -
_bot    lda b_yb                        ; alareunan pikseli musta (jos kuvassa)
        cmp #PH
        bcs _skip
        lda (zdst),y
_pc3    and #0
        sta (zdst),y
_skip   inc b_x
        lda b_ytf
        clc
        adc b_tsl
        sta b_ytf
        lda b_yt
        adc b_tsh
        sta b_yt
        lda b_ybf
        clc
        adc b_bsl
        sta b_ybf
        lda b_yb
        adc b_bsh
        sta b_yb
        dec b_n
        beq +
        jmp _col
+       rts

; b_ptr: zdst = solurivin alku (rivi Y & ~7) + sarake, Y = y & 7, b_y = y
b_ptr
        sty b_y
        tya
        and #$f8
        tax
        lda bmrow_lo,x                  ; (itsemuokkaus)
brt_lo  = * - 3
        clc
        adc b_clo
        sta zdst
        lda bmrow_hi,x
brt_hi  = * - 3
        adc b_chi
        sta zdst+1
        lda b_y
        and #7
        tay
        rts

; b_next: seuraava solurivi (+320), Y = 0
b_next
        lda zdst
        clc
        adc #<320                       ; (itsemuokkaus: solurivin pituus)
bst_lo  = * - 2
        sta zdst
        lda zdst+1
        adc #>320
bst_hi  = * - 2
        sta zdst+1
        ldy #0
        rts

; b_slope: A = dy (etumerkillinen, |dy| < 128), kerroin dy / b_dx 8.8 -> A = kokonaisosa, X = murto
b_slope
        ldx #0
        cmp #$80
        bcc +
        eor #$ff
        clc
        adc #1
        ldx #1
+       stx b_neg
        ldx #0                          ; kokonaisosa
-       cmp b_dx
        bcc +
        sbc b_dx
        inx
        bne -
+       stx b_q
        ldx #8                          ; murto
-       asl
        bcs _big
        cmp b_dx
        bcc +
_big    sbc b_dx
        sec
+       rol b_f
        dex
        bne -
        lda b_neg
        beq +
        lda b_f
        eor #$ff
        clc
        adc #1
        sta b_f
        lda b_q
        eor #$ff
        adc #0
        sta b_q
+       ldx b_f
        lda b_q
        rts

b_tab   = BARTAB                        ; kuormaaja.py: varren kuvio [(x & 7) * 8 + rivi & 7] sävyllä ARM_TONE
b_zero  .fill 8
b_m     .byte 0
b_dx    .byte 0
b_n     .byte 0
b_x     .byte 0
b_y     .byte 0
b_yt    .byte 0
b_ytf   .byte 0
b_yb    .byte 0
b_ybf   .byte 0
b_tsl   .byte 0
b_tsh   .byte 0
b_bsl   .byte 0
b_bsh   .byte 0
b_clo   .byte 0
b_chi   .byte 0
b_neg   .byte 0
b_q     .byte 0
b_f     .byte 0

; ------------------------------------------------------------------ hiekka: kippauksen jyvät
; Valuva hiekka on yksittäisiä jyviä (partikkeleita, ei yhtenäistä laattaa).
; Jyvä syntyy kauhan huulelle (kärjet 2 puolelta 0 puolelle 1, kaista 0-7),
; putoaa painovoimalla (FALL) ja ajautuu sivulle omalla nopeudellaan (gvx, päivitystä kohden), osuu kaistan maahan (LAND_Y), valuu
; luiskaa alas (SLIDE_DX, SLIDE_DY) ja leivotaan puhtaaseen taustaan ja molempiin puskureihin. Nopea jyvä piirretään
; kahden pikselin viiruna. Vapaa paikka: gland = 0; valuva: gage bitti 7 (laskuri alabiteissä, gy0 = y:n murto-osa).
NGR     = 52

grains
        lda fnow                        ; kuluneet kehykset edellisestä päivityksestä (1-12)
        sec
        sbc g_last
        beq +
        cmp #13
        bcc ++
+       lda #4
+       sta g_dt
        lda fnow
        sta g_last
        ldx g_dt                        ; valumisaskel tälle päivitykselle: dt * (SLIDE_DX, SLIDE_DY) 8.8
        lda sl_dxl,x
        sta g_sxl
        lda sl_dxh,x
        sta g_sxh
        lda sl_dyl,x
        sta g_syl
        lda sl_dyh,x
        sta g_syh
        ldx g_idx                       ; uudet jyvät: ST_PR[askel]
        lda ST_PR,x
        beq _upd
        sta g_new
        ldx #NGR-1
-       lda gland,x
        bne _full
        jsr rnd
        and #7
        tay                             ; kaista
        lda LAND_Y,y
        sta gland,x
        lda lipx+1                      ; x = huuli0 + (huuli1 - huuli0) * kaista / 8
        sec
        sbc lipx
        jsr lerp8
        clc
        adc lipx
        sta gx,x
        lda lipy+1
        sec
        sbc lipy
        jsr lerp8
        clc
        adc lipy
        sta gy0,x                       ; putoamisen alku
        sta gy,x
        jsr rnd
        sta gxf,x
        and #127                        ; sivunopeus -1/4..+1/4 px päivityksessä
        sec
        sbc #64
        sta gvx,x
        jsr rnd                         ; ikä 4-7: huulelta lähtee vauhdilla, eivätkä jyvät putoa tahdissa
        and #3
        ora #4
        sta gage,x
        inc g_alive
        dec g_new
        beq _upd
_full   dex
        bpl -
_upd    lda g_alive                     ; ei jyviä: ei kierrosta (kippauksen ulkopuolella ennallaan)
        bne +
        rts
+       lda #0
        sta g_alive
        ldx #NGR-1
_g      lda gland,x
        bne +
        jmp _gn
+       inc g_alive
        lda gage,x
        bpl +
        jmp _slide
+       clc                             ; putoaa: x += gvx (päivitystä kohden)
        lda gvx,x
        bmi _neg
        adc gxf,x
        sta gxf,x
        bcc _dn
        inc gx,x
        jmp _dn
_neg    adc gxf,x
        sta gxf,x
        bcs _dn
        dec gx,x
_dn     lda gage,x                      ; y = y0 + FALL[ikä]
        clc
        adc g_dt
        cmp #63
        bcc +
        lda #63
+       sta gage,x
        tay
        lda FALL,y
        clc
        adc gy0,x
        bcs _land
        cmp gland,x
        bcs _land
        sta gy,x
        lda #0                          ; viiru, kun jyvä putoaa yli 2 px kehyksessä
        cpy #STREAK_AGE
        bcc +
        lda #1
+       sta g_str
        txa                             ; joka neljäs oranssi, muut keltaisia (valossa)
        and #3
        beq +
        lda #1
+       ora #2
        jmp _draw
_land   lda gland,x
        sta gy,x
        jsr rnd                         ; valuu 2-9 kehystä
        and #7
        ora #$82
        sta gage,x
        lda #0
        sta gy0,x
        jmp _gn
_slide  lda gxf,x                       ; valuu: x += dt * dx, y += dt * dy
        clc
        adc g_sxl
        sta gxf,x
        lda gx,x
        adc g_sxh
        sta gx,x
        lda gy0,x
        clc
        adc g_syl
        sta gy0,x
        lda gy,x
        adc g_syh
        sta gy,x
        cmp #ZONE_Y1
        bcs _gone
        lda gage,x
        and #$7f
        sec
        sbc g_dt
        beq _bake
        bcc _bake
        ora #$80
        sta gage,x
        lda #0
        sta g_str
        lda #2
        jmp _draw
_bake   lda #0                          ; pysähtyi: leivotaan taustaan ja puskureihin
        sta gland,x
        stx g_i
        jsr rnd
        and #1
        ora #2
        sta g_col
        lda gx,x
        ldy gy,x
        tax
        cpx #160
        bcs +
        lda g_col
        jsr bakepx
+       ldx g_i
        jmp _gn
_gone   lda #0
        sta gland,x
        jmp _gn
_draw   sta g_col                       ; liikkuva jyvä takapuskuriin, rajat päällykseen
        stx g_i
        ldy gy,x
        lda gx,x
        tax
        cpx #160
        bcs _dd
        cpy #ZONE_Y1
        bcs _dd
        cpy #ZONE_Y0+1
        bcc _dd
        lda g_str
        beq +
        dey                             ; viirun yläpää rajoihin
        jsr bound
        lda g_col
        jsr plotc
        ldx g_i
        ldy gy,x
        lda gx,x
        tax
+       jsr bound
        lda g_col
        jsr plotc
_dd     ldx g_i
_gn     dex
        bmi +
        jmp _g
+       rts

sl_dxl  .byte <(range(13) * SLIDE_DX)
sl_dxh  .byte >(range(13) * SLIDE_DX)
sl_dyl  .byte <(range(13) * SLIDE_DY)
sl_dyh  .byte >(range(13) * SLIDE_DY)
g_sxl   .byte 0
g_sxh   .byte 0
g_syl   .byte 0
g_syh   .byte 0

; lerp8: A = erotus (etumerkillinen), Y = kaista 0-7 -> A = erotus * kaista / 8 (säilyttää X)
lerp8
        sta g_d
        lda #0
        cpy #0
        beq _done
        sty g_k
-       clc
        adc g_d
        dec g_k
        bne -
_done   cmp #$80
        ror
        cmp #$80
        ror
        cmp #$80
        ror
        rts

; plotc: pikseli (X, Y) roolilla A takapuskuriin
plotc
        sta g_c
        lda bhi
        sta g_hi
        jmp plotat

; bakepx: pikseli (X, Y) roolilla A puhtaaseen taustaan ja molempiin puskureihin
bakepx
        sta g_c
        stx g_px
        sty g_py
        lda #$60
        sta g_hi
        jsr plotat
        ldx g_px
        ldy g_py
        lda #$a0
        sta g_hi
        jsr plotat
        ldx g_px
        ldy g_py
        lda cl_lo,y             ; puhdas tausta
        sta zdst
        lda cl_hi,y
        sta zdst+1
        jmp plotz

; ------------------------------------------------------------------ kuvan 1 taulut
        .include "k1data.asm"
CLROW_N = 21 * 8                        ; rivistä vain koneen alueen sarakkeet 0-20 (kuormaaja.py ZONE_COLS)
CL_B    = GRAM + GRAM_N                 ; rivit 13-17 jyvien perään (pankin 2 näkymättömät rivit): pankki 3 vapaa
CLROWS  = [$4000, $4140, $4280, $8000, $8140, $8280] .. (CL_B + range(5) * CLROW_N)   ; seuraavan osan esilataukselle
NCLROW  = (ZONE_Y1 - ZONE_Y0) / 8
        .cerror NCLROW > len(CLROWS), "puhtaan taustan rivit eivät mahdu"
CL1     = [0] x ZONE_Y0 .. (CLROWS[(range(ZONE_Y0, ZONE_Y1) >> 3) - ZONE_Y0 / 8] + (range(ZONE_Y0, ZONE_Y1) & 7)) .. [0] x (144 - ZONE_Y1)
clrow_lo .byte <(CLROWS[:NCLROW])
clrow_hi .byte >(CLROWS[:NCLROW])
grp_lo  .byte <((range(BODY_H) >> 3) * 128 + (range(BODY_H) & 7))
grp_hi  .byte >((range(BODY_H) >> 3) * 128 + (range(BODY_H) & 7))

lst_c0  .byte $ff, $ff                  ; puskurin edellinen runko (col0, siirto, by)
lst_sf  .byte 0, 0
lst_by  .byte 0, 0
ov_c0   .byte 0, 0                      ; puskurin edellinen päällys (sarakkeet, rivit)
ov_c1   .byte 0, 0
ov_y0   .byte 0, 0
ov_y1   .byte 0, 0
g_last  .byte 0                         ; jyvien muuttujat
g_dt    .byte 0
g_idx   .byte 0
g_new   .byte 0
g_cnt   .byte 0
g_i     .byte 0
g_col   .byte 0
g_d     .byte 0
g_k     .byte 0
g_px    .byte 0
g_alive .byte 0
g_py    .byte 0
g_str   .byte 0
STREAK_AGE = 6                          ; FALL-ikä, josta jyvä piirretään viiruna
GRAM    = $bb40                         ; jyvien taulut (pankin 2 näkymättömät rivit, kp_init nollaa gland)
gx      = GRAM
gxf     = GRAM + NGR
gvx     = GRAM + 2 * NGR                ; sivunopeus (etumerkillinen, 1/256 px kehyksessä)
gy      = GRAM + 3 * NGR
gy0     = GRAM + 4 * NGR                ; putoamisen alku-y (valuessa y:n murto-osa)
gage    = GRAM + 5 * NGR                ; ikä kehyksinä (valuessa bitti 7 ja laskuri)
gland   = GRAM + 6 * NGR                ; kaistan maan y (0 = vapaa)
GRAM_N  = 7 * NGR
        .cerror CL_B + 5 * CLROW_N > $c000, "jyvät ja puhtaan taustan rivit"

code_end
        .cerror code_end > $4000, "koodi ylittää $4000"

; ------------------------------------------------------------------ kuva 1 pankeissa 1 ja 2 (kp1c, kp1b)
        * = SCR1 + PICS
kp1c
        .binary "k1.bin", BMP_N, SCR_N
        * = SHAPE0
        .binary "k1shape0.bin"
        * = SHAPE1
        .binary "k1shape1.bin"
        * = $6000 + PIC
        .binary "k1.bin", 0, BMP_N
        * = $5a00                       ; rungon esisiirtojen jälkeen: kankaan ja varsien taulut
        .include "k1bank.asm"
cv_lo   .byte <(CANV + (range(48) >> 3) * 48 + (range(48) & 7))
cv_hi   .byte >(CANV + (range(48) >> 3) * 48 + (range(48) & 7))
        .cerror * > CANV, "pankin 1 taulut osuvat kankaaseen"
        * = $4000 + PUFFX
        .binary "k1puff.bin"                    ; savun spritet (pieni, keski, iso)
        * = $7b40
COL1    .binary "k1.bin", BMP_N + SCR_N, SCR_N  ; $7b40: kuvan 1 värit (näkymättömät rivit)
        .include "k1t2.asm"                     ; $7e10-: kauhan pinnat, pultit
        .cerror * > $8000, "pankin 1 taulut"
kp1c_end
        * = $c000                       ; pankki 3 vapaa kuvan 1 aikana (kuvan 2 nosturin spritet myöhemmin)
kp1d
        .include "k1arm.asm"
kp1d_end
        .cerror kp1d_end > $c400, "varsien taulut"
        * = SHAPE2
kp1b
        .binary "k1shape2.bin"
        * = SHAPE3
        .binary "k1shape3.bin"
        * = $9a00                       ; esisiirtojen jälkeen (VIC näkee tässä merkistö-ROMin, suoritin RAMin)
        .include "k1st.asm"
        .cerror * > $a000, "kulun taulut"
kp1b_end
