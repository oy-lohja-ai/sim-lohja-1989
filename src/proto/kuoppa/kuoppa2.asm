; Kuva 2 (kuopan osa, kehykset 600-1199): Lohjantähden runko nousee ja torninosturi kääntyy. Data runko.py.
;
; Tämä koodi ja nosturin taulut ladataan ennen kelloa pankin 3 vapaaseen kohtaan ($c800-), joten nosturi liikkuu
; heti leikkauksesta. Rakennusjärjestys ja valmiin kuvan tavut (RUNS, kp2r) ladataan kuvan 1 koodin päälle
; (core_end-) ja jalankulkija $4800:aan (kp2w) kuvan 1 jälkeen; kp2_go ottaa ne käyttöön.
;
; job2 (IRQ:n sisäkkäinen työ): 1. nosturin puomi piirretään takimmaiseen spritesarjaan (4 x 2 X-levennettyä
; hires-spriteä, 96 x 42 MC-px, rakennuksen takana $d01b): ylä- ja alapaarre, ristikko, vastapuomi, vetotangot,
; vaunu ja koukku palkkeineen kääntökulman taulusta; IRQ-koukku vaihtaa sarjan osoittimet. 2. aktiiviset ajot
; paljastavat valmiin kuvan pikseleitä rivi kerrallaan (pilarit kasvavat, välipohjat valetaan, sisus täyttyy).

        .include "kp_defs.inc"
        .include "core.inc"
        .include "kp1_syms.inc"         ; kuoppa.labels: spr1, spos (Makefile)

BM3     = $e0                           ; pankin 3 bittikartta
NACT    = 56
ACT     = $ce00                         ; aktiivisten ajojen taulut (ajonaikaiset; kuvan 1 puhdas tausta vapautunut)
a_c     = ACT
a_y     = ACT + NACT
a_n     = ACT + 2 * NACT
a_m     = ACT + 3 * NACT
a_r     = ACT + 4 * NACT
a_tl    = ACT + 5 * NACT
a_th    = ACT + 6 * NACT
a_pl    = ACT + 7 * NACT                ; ajon seuraavan rivin tavu
a_ph    = ACT + 8 * NACT
        .cerror ACT + 9 * NACT > $d000, "kuvan 2 ajot eivät mahdu"
SPRA    = $c000                         ; spritesarjat A $c000, B $c200 (osoittimet 0-7, 8-15)
SCR3P   = SCR3 + $3f8
APEXY   = CR_APEXY > 0 ? CR_APEXY : 0   ; pukin huippu kuvan yläreunan yllä: vetotangot reunasta
SW      = 96                            ; spritelohkon leveys ja korkeus MC-px
SHH     = 42

        .virtual zp_end                 ; ytimen nollasivun jälkeen: osoittimet
rp      .word ?                         ; seuraava ajo
sp      .word ?                         ; spriterivin osoite
zp2_end
        .cerror zp2_end > $c0, "nollasivu"
        .endv

        * = $c800
; kp2_init (pääsäie ennen kelloa): työ jobv[1]:een, nosturi piirretään heti leikkauksesta
kp2_init
        ldx #PICS-1                     ; kuvan 2 ruudun reunarivit mustiksi (pankki 3 on vapaa kuvan 1 aikana)
        lda #0
-       sta SCR3,x
        sta SCR3+PICS+SCR_N,x
        sta SCR3+PICS+SCR_N+40,x
        dex
        bpl -
        lda #$ff
        sta clast
        lda #0
        sta rready
        sta s2init
        sta nact
        sta sset
        sta sflip
        lda #<job2
        sta jobv_lo+1
        lda #>job2
        sta jobv_hi+1
        rts

; kp2_go (pääsäie, kp2r ja kp2w ladattu): rakennusjärjestys käyttöön
kp2_go
        lda #<RUNS
        sta rp
        lda #>RUNS
        sta rp+1
        lda #<NRUN
        sta rleft
        lda #>NRUN
        sta rleft+1
        jsr ped_go
        lda #1
        sta rready
        rts

; flip2: IRQ-koukku, valmis spritesarja näkyviin
flip2
        lda sflip
        beq +
        lda sset
        eor #1
        sta sset
        asl
        asl
        asl
        ldx #0
-       sta SCR3P,x
        clc
        adc #1
        inx
        cpx #8
        bne -
        lda #0
        sta sflip
+       rts

job2
        lda DFRAME                      ; kuopan lopussa ei työtä: pääsäie ehtii saumaan (taulu2b) tai part_endiin
        cmp #<LOPPU2
        lda DFRAME+1
        sbc #>LOPPU2
        bcc +
        rts
+       lda DFRAME                      ; now = DFRAME - SHOT2_O (kuvan 2 kehys)
        sec
        sbc #<SHOT2_O
        sta now
        lda DFRAME+1
        sbc #>SHOT2_O
        sta now+1
        lda s2init
        bne +
        jsr spr_init
+       lda sflip                       ; nosturi vain kun kääntöaskel vaihtuu (8 kehystä): suoritinaikaa latauksille
        bne +
        lda now
        lsr
        lsr
        lsr
        cmp clast
        beq +
        sta clast
        jsr crane
+       lda rready
        beq _done
        jsr ped
        jmp reveal_runs
_done   rts

; spr_init: spritet nosturille (X-levennetty hires, keltainen, rakennuksen takana), IRQ-koukku
spr_init
        inc s2init
        lda #0
        tax
-       sta SPRA,x
        sta SPRA+$100,x
        sta SPRA+$200,x
        sta SPRA+$300,x
        inx
        bne -
        ldx #7
-       txa
        sta SCR3P,x
        dex
        bpl -
        ldx #0
        ldy #0
-       lda spr_xl,x
        sta $d000,y
        lda spr_y,x
        sta $d001,y
        lda #7
        sta $d027,x
        iny
        iny
        inx
        cpx #8
        bne -
        lda #SPR_MSB
        sta $d010
        lda #$ff
        sta $d01d
        sta $d01b
        lda #0
        sta $d017
        sta $d01c
        lda #$4c                        ; irqhook: jmp flip2
        sta irqhook
        lda #<flip2
        sta irqhook+1
        lda #>flip2
        sta irqhook+2
        lda #$ff
        sta $d015
        rts

spr_xl  .byte <(SPR_HX)                  ; runko.py: x = 24 + 2 * (SPR_X0 + 24 * sarake), y = 74 + SPR_Y0 + 21 * kaista
spr_y   .byte SPR_YS

; crane: takimmainen sarja tyhjäksi, puomi viivoina, vaihtopyyntö
crane
        lda now+1                       ; askel = now / 8
        sta k8
        lda now
        lsr k8
        ror
        lsr k8
        ror
        lsr k8
        ror
        cmp #NSTEP2
        bcc +
        lda #NSTEP2-1
+       tax
        lda CR_S,x
        sta cs
        lda CR_U,x
        sta cu
        lda sset                        ; takimmainen sarja: $c000 / $c200
        eor #1
        asl
        ora #>SPRA
        sta spbase
        sta _c0+2
        clc
        adc #1
        sta _c1+2
        lda #0
        tax
_c0     sta SPRA,x                      ; (itsemuokkaus)
_c1     sta SPRA+$100,x
        inx
        bne _c0
        ldx cs
        ; yläpaarre ja alapaarre, vastapuomi
        #seg #CR_PTX, #CR_PTY, CR_TTX,x, CR_TTY,x
        ldx cs
        #seg #CR_PBX, #CR_PBY, CR_TBX,x, CR_TBY,x
        ldx cs
        #seg #CR_PTX, #CR_PTY, CR_CTX,x, CR_CTY,x
        ldx cs
        #seg #CR_PBX, #CR_PBY, CR_CBX,x, CR_CBY,x
        ldx cs
        #seg CR_CTX,x, CR_CTY,x, CR_CBX,x, CR_CBY,x
        ldx cs
        #seg #CR_APEXX, #APEXY, CR_TTX,x, CR_TTY,x
        ldx cs
        #seg #CR_APEXX, #APEXY, CR_CTX,x, CR_CTY,x
        ; ristikko: 8 lenkkiä alapaarteelta yläpaarteelle ja takaisin
        ldx cs
        lda CR_TBX,x
        ldy #CR_PBX
        jsr diff8y
        sta dxs+1
        stx dxs
        ldx cs
        lda CR_TBY,x
        ldy #CR_PBY
        jsr diff8y
        sta dys+1
        stx dys
        ldx cs
        lda CR_TTX,x
        ldy #CR_PTX
        jsr diff8y
        sta dxt+1
        stx dxt
        ldx cs
        lda CR_TTY,x
        ldy #CR_PTY
        jsr diff8y
        sta dyt+1
        stx dyt
        lda #CR_PBX                     ; alapaarteen piste (fx, fy), yläpaarteen (gx_, gy_) puoli askelta edellä
        sta fx+1
        lda #CR_PBY
        sta fy+1
        lda #$80
        sta fx
        sta fy
        lda #CR_PTX
        sta gx_+1
        lda #CR_PTY
        sta gy_+1
        lda #$80
        sta gx_
        sta gy_
        #add16 gx_, dxt, 1
        #add16 gy_, dyt, 1
        lda #8
        sta k8
-       lda fx+1
        sta lx0
        lda fy+1
        sta ly0
        lda gx_+1
        sta lx1
        lda gy_+1
        sta ly1
        jsr sline
        #add16 fx, dxs, 0
        #add16 fy, dys, 0
        lda gx_+1
        sta lx0
        lda gy_+1
        sta ly0
        lda fx+1
        sta lx1
        lda fy+1
        sta ly1
        jsr sline
        #add16 gx_, dxt, 0
        #add16 gy_, dyt, 0
        dec k8
        bne -
        ; vaunu alapaarteella kohdassa cu / 16 ja koukku palkkeineen
        lda #CR_PBX
        sta hx
        lda #CR_PBY
        sta hy
        ldx cu
        beq +
-       lda dxs+1                       ; askel 8.8 on 1/8 välistä: vaunu cu / 16 = cu / 2 askelta
        cmp #$80
        ror
        clc
        adc hx
        sta hx
        lda dys+1
        cmp #$80
        ror
        clc
        adc hy
        sta hy
        dex
        bne -
+       lda hx
        sta lx0
        sta lx1
        lda hy
        sta ly0
        clc
        adc #9
        sta ly1
        jsr sline
        lda hx
        sec
        sbc #4
        sta lx0
        clc
        adc #8
        sta lx1
        lda hy
        clc
        adc #9
        sta ly0
        sta ly1
        jsr sline
        lda #1
        sta sflip
        rts

spbase  .byte 0

seg     .macro x0, y0, x1, y1           ; viiva sline: (x0, y0) - (x1, y1)
        lda \x0
        sta lx0
        lda \y0
        sta ly0
        lda \x1
        sta lx1
        lda \y1
        sta ly1
        jsr sline
        .endm

add16   .macro a, d, half               ; a += d (half: puolikas askel)
        .if \half
        lda \d+1
        cmp #$80
        ror
        sta k8b+1
        lda \d
        ror
        sta k8b
        lda \a
        clc
        adc k8b
        sta \a
        lda \a+1
        adc k8b+1
        sta \a+1
        .else
        lda \a
        clc
        adc \d
        sta \a
        lda \a+1
        adc \d+1
        sta \a+1
        .endif
        .endm

k8b     .word 0

; diff8y: A = kärki, Y = tyvi: (A - Y) * 256 / 8 etumerkillisenä 8.8 -> X = lo, A = hi
diff8y
        sty k8c
        sec
        sbc k8c                         ; etumerkillinen erotus
        sta k8c+1
        lda #0
        sta k8c
        ldx #3                          ; >> 3 (16 bittiä, etumerkillinen)
-       lda k8c+1
        cmp #$80
        ror k8c+1
        ror k8c
        dex
        bne -
        ldx k8c
        lda k8c+1
        rts
k8c     .word 0

; sline: viiva (lx0, ly0) - (lx1, ly1) takimmaiseen spritesarjaan; pikselit lohkon ulkopuolella ohitetaan
sline
        lda lx1
        sec
        sbc lx0
        ldx #1
        bcs +
        eor #$ff
        adc #1
        ldx #$ff
+       sta ldx_
        stx lsx
        lda ly1
        sec
        sbc ly0
        ldx #1
        bcs +
        eor #$ff
        adc #1
        ldx #$ff
+       sta ldy_
        stx lsy
        lda ldx_
        cmp ldy_
        bcc _ym
        sta lcnt2
        lsr
        sta lerr
-       jsr _pl
        lda lcnt2
        beq _end
        dec lcnt2
        lda lx0
        clc
        adc lsx
        sta lx0
        lda lerr
        sec
        sbc ldy_
        sta lerr
        bcs -
        adc ldx_
        sta lerr
        lda ly0
        clc
        adc lsy
        sta ly0
        jmp -
_ym     lda ldy_
        sta lcnt2
        lsr
        sta lerr
-       jsr _pl
        lda lcnt2
        beq _end
        dec lcnt2
        lda ly0
        clc
        adc lsy
        sta ly0
        lda lerr
        sec
        sbc ldx_
        sta lerr
        bcs -
        adc ldy_
        sta lerr
        lda lx0
        clc
        adc lsx
        sta lx0
        jmp -
_end    rts
_pl     ldx lx0
        cpx #SW
        bcs +
        ldy ly0
        cpy #SHH
        bcs +
        lda spy_lo,y
        sta sp
        lda spy_hi,y
        clc
        adc spbase
        sta sp+1
        ldy spx_off,x
        txa
        and #7
        tax
        lda (sp),y
        ora spx_bit,x
        sta (sp),y
+       rts


kp2_end
        .virtual kp2_end                ; muuttujat koodin perässä
rleft   .word ?                         ; ajoja jäljellä
now     .word ?                         ; kuvan 2 kehys
nact    .byte ?
ai2     .byte ?
rready  .byte ?                         ; ajot ladattu
s2init  .byte ?
sset    .byte ?                         ; näkyvä spritesarja 0 / 1
sflip   .byte ?                         ; 1 = vaihda sarja IRQ:ssa
lx0     .byte ?                         ; viiva
ly0     .byte ?
lx1     .byte ?
ly1     .byte ?
ldx_    .byte ?
ldy_    .byte ?
lsx     .byte ?
lsy     .byte ?
lerr    .byte ?
lcnt2   .byte ?
cs      .byte ?                         ; kääntöaskel
cu      .byte ?                         ; vaunun paikka 0-15
k8      .byte ?
fx      .word ?                         ; ristikon askellus 8.8
fy      .word ?
gx_     .word ?
gy_     .word ?
dxs     .word ?
dys     .word ?
dxt     .word ?
dyt     .word ?
hx      .byte ?
clast   .byte ?
hy      .byte ?
vars_end
        .endv
        .cerror vars_end > $d000, "kuvan 2 koodi ylittää $cfff"

; ------------------------------------------------------------------ taulut pankin 3 näkymättömillä bittikarttariveillä 0-2
        * = $e000
; spritelohkon taulut: x -> (sarake * 64 + tavu, bitti), y -> (rivi * 3 + kaista * 256)
spx_off .byte (range(SW) / 24) * 64 + (range(SW) % 24) / 8
spx_bit .byte $80 >> range(8)              ; (x % 24) % 8 = x % 8
spy_lo  .byte <((range(SHH) / 21) * 256 + (range(SHH) % 21) * 3)
spy_hi  .byte >((range(SHH) / 21) * 256 + (range(SHH) % 21) * 3)
        .include "k2data.asm"

kp2t_end
        .cerror kp2t_end > $e3c0, "kuvan 2 taulut osuvat bittikarttaan"

; ------------------------------------------------------------------ pyyhkäisy kuvasta 1 kuvaan 2 (kpy, kp2b:n perässä)
; Siirtymä kuopalta rakentamiseen: ikkuna aukeaa
; ylhäältä alas merkkirivi kehyksessä. Kuvan 2 alkukuvan rivi (bittikartta ja ruutu pankista 3,
; värit COL2) kopioidaan kuvan 1 näkyvään puskuriin, ja kehyksellä CUT2 - SIIRTO - 1 koko kuva on kuva 2, joten
; leikkaus (pankki 3) ei näy. Kuva 1 ei aloita kierrosta LEPO1:stä (kuormaaja jää asentoonsa), puskurit eivät vaihdu
; pyyhkäisyn aikana (fshot), ja spritet, joiden yläreuna on jo pyyhkäisyn alla, piiloon.
        * = $fd10
; py_init (pääsäie kp2_initin jälkeen): kuvan 1 IRQ-koukuksi py_hook
py_init
        lda #0
        sta py_n
        sta py_done
        sei
        lda #<py_hook
        sta irqhook+1
        lda #>py_hook
        sta irqhook+2
        cli
        rts

; py_hook: kuvan 1 IRQ-koukku py_initistä leikkaukseen (spr1 ja pyyhkäisyn tila)
py_hook
        jsr spr1
        lda DFRAME
        sec
        sbc #<LEPO1
        tay
        lda DFRAME+1
        sbc #>LEPO1
        bcc _x
        lda #<py_job                    ; kuvan 1 työ: ei uusia kierroksia, vain pyyhkäisy
        sta jobv_lo
        lda #>py_job
        sta jobv_hi
        tya                             ; rivejä kehys - PYYHK0 + 1
        sec
        sbc #PYYHK0 - LEPO1 - 1
        bcc _x
        beq _x
        cmp #RIVIT
        bcc +
        lda #RIVIT
+       sta py_n
        lda #$ff                        ; ei puskurin vaihtoa (molemmat valmiita, näkyvään kopioidaan)
        sta fshot
        lda py_n                        ; pyyhkäisyn reuna spriten Y:nä
        asl
        asl
        asl
        adc #74
        sta py_e
        lda #$ff
        sta py_m
        ldx #0                          ; kauha 0-3, varret 4-7 (jakorivin alla)
        ldy #0
-       lda spos+1,y
        cmp py_e
        bcs +
        lda py_m
        and py_clr,x
        sta py_m
+       iny
        iny
        inx
        cpx #8
        bne -
        ldy #6                          ; savu (spritet 4-7 jakorivin yllä): Y = 0 piiloon
-       lda $d009,y
        cmp py_e
        bcs +
        lda #0
        sta $d009,y
+       dey
        dey
        bpl -
        lda py_m
        sta $d015
_x      rts

; py_job: rivit py_done..py_n-1 näkyvään puskuriin (rivi noin 4 200 sykliä, valmis ennen kuin säde ehtii kuvaan)
py_job
        ldx shown
        lda py_sub,x
        sta py_sb
-       ldx py_done
        cpx py_n
        bcs +
        jsr py_row
        inc py_done
        bne -
+       rts

; py_row: X = rivi
py_row
        lda py_slo,x
        sta py_s+1
        sta py_s+4
        lda py_shi,x
        sta py_s+2
        sec
        sbc py_sb
        sta py_s+5
        lda py_clo,x
        sta py_c+1
        lda py_chi,x
        sta py_c+2
        lda py_dlo,x
        sta py_c+4
        lda py_dhi,x
        sta py_c+5
        lda py_rlo,x
        sta py_t
        lda py_rhi,x
        sta py_t+1
        .for _k := 0, _k < 8, _k += 1
        lda py_t
        clc
        adc #<(40 * _k)
        sta py_b + 1 + 6 * _k
        sta py_b + 4 + 6 * _k
        lda py_t+1
        adc #>(40 * _k)
        sta py_b + 2 + 6 * _k
        sec
        sbc py_sb
        sta py_b + 5 + 6 * _k
        .next
        ldx #39
py_b    .rept 8                         ; bittikartta 8 x 40 tavua
        lda $ffff,x
        sta $ffff,x
        .endrept
py_s    lda $ffff,x                     ; ruutu
        sta $ffff,x
py_c    lda $ffff,x                     ; värit
        sta $ffff,x
        dex
        bpl py_b
        rts

py_sub  .byte $80, $40                  ; pankin 3 osoite -> puskuri A (pankki 1) / B (pankki 2), alatavu sama
py_rlo  .byte <($e000 + PIC + 320 * range(RIVIT))
py_rhi  .byte >($e000 + PIC + 320 * range(RIVIT))
py_slo  .byte <(SCR3 + PICS + 40 * range(RIVIT))
py_shi  .byte >(SCR3 + PICS + 40 * range(RIVIT))
py_clo  .byte <(COL2 + 40 * range(RIVIT))
py_chi  .byte >(COL2 + 40 * range(RIVIT))
py_dlo  .byte <($d800 + PICS + 40 * range(RIVIT))
py_dhi  .byte >($d800 + PICS + 40 * range(RIVIT))
py_clr  .byte $ff ^ (1 << range(8))
py_n    .byte 0                         ; rivejä näkyvissä tällä kehyksellä
py_done .byte 0                         ; rivejä kopioitu
py_sb   .byte 0
py_t    .word 0
py_e    .byte 0
py_m    .byte 0
py_end
        .cerror COL2 + SCR_N > $fd10, "kuvan 2 värit osuvat pyyhkäisyyn"
        .cerror py_end > $fffa, "pyyhkäisy ylittää $fff9"

; ------------------------------------------------------------------ kp2r: kuvan 1 koodin päälle kehyksestä 612
        * = core_end
; reveal_runs: uudet ajot, joiden aika on tullut, aktiivisiksi; aktiiviset paljastavat rivejä. Ajo: aika / 4, sarake,
; alin rivi, rivejä, ~maski, kehystä riviä kohden ja rivien tavut (valmis kuva & maski) alhaalta ylös.
reveal_runs
_act    lda rleft
        ora rleft+1
        beq _proc
        ldx nact
        cpx #NACT
        bcs _proc
        ldy #0
        lda (rp),y                      ; aika * 4
        sta a_tl,x
        lda #0
        asl a_tl,x
        rol
        asl a_tl,x
        rol
        sta a_th,x
        lda now
        cmp a_tl,x
        lda now+1
        sbc a_th,x
        bcc _proc
        iny
        lda (rp),y
        sta a_c,x
        iny
        lda (rp),y
        sta a_y,x
        iny
        lda (rp),y
        sta a_n,x
        sta tmp
        iny
        lda (rp),y
        sta a_m,x
        iny
        lda (rp),y
        sta a_r,x
        lda rp                          ; tavut alkavat +6
        clc
        adc #6
        sta a_pl,x
        lda rp+1
        adc #0
        sta a_ph,x
        inc nact
        lda a_pl,x                      ; seuraava ajo: tavujen jälkeen
        clc
        adc tmp
        sta rp
        lda a_ph,x
        adc #0
        sta rp+1
        lda rleft
        bne +
        dec rleft+1
+       dec rleft
        jmp _act
_proc   ldx nact
        dex
        bmi _done
_run    stx ai2
-       lda now
        cmp a_tl,x
        lda now+1
        sbc a_th,x
        bcc _next
        jsr reveal
        ldx ai2
        dec a_y,x
        inc a_pl,x
        bne +
        inc a_ph,x
+       lda a_tl,x
        clc
        adc a_r,x
        sta a_tl,x
        bcc +
        inc a_th,x
+       dec a_n,x
        bne -
        ldy nact
        dey
        sty nact
        .for t in (a_c, a_y, a_n, a_m, a_r, a_tl, a_th, a_pl, a_ph)
        lda t,y
        sta t,x
        .endfor
_next   ldx ai2
        dex
        bpl _run
_done   rts

; reveal: ajon X seuraava rivi a_y: (vanha & ~maski) | tavu näkyvään bittikarttaan
reveal
        lda a_pl,x
        sta src
        lda a_ph,x
        sta src+1
        ldy a_y,x
        lda a_c,x
        tax
        lda bmrow_lo,y
        clc
        adc colofs_lo,x
        sta dst
        lda bmrow_hi,y
        adc colofs_hi,x
        clc
        adc #BM3
        sta dst+1
        ldx ai2
        ldy #0
        lda (dst),y
        and a_m,x
        ora (src),y
        sta (dst),y
        rts

RUNS    .binary "k2runs.bin"

; kupla: jalankulkijan puhekupla «MÄÄ NUKKUSI KU HEI HERÄTTIVÄ» osan kehyksillä KUPLA0-KUPLA1:
; spritet 0-5 (MC, valkoinen, $d025 musta)
; jakorivin alla hahmon pään yläpuolella, nuolen kärki pään kohdalla. pmid asettaa ne, hook2 palauttaa nosturille.
; Pääsäie (ped, KP2R ladattu) laskee rekisterit b_reg:iin ja kopioi datan kerran pyyhkäisyn vapauttamaan BSPR:ään.
KUPLA0  = 796                           ; näkyy 803-990: pääsäikeen työ (ped) on muutaman kehyksen jäljessä
KUPLA1  = 988
KDX     = 75                            ; kuplan vasen reuna = hahmon x - KDX (kärki runko.py KUPLA_KARKI 43)
BSPR    = $fd40                         ; pyyhkäisyn (KPY) paikka pankissa 3, vapaa leikkauksen jälkeen ($fd40-$febf)
BPTR    = (BSPR & $3fff) / 64
kupla
        ldx #0
        lda DFRAME
        cmp #<KUPLA0
        lda DFRAME+1
        sbc #>KUPLA0
        bcc _off
        lda DFRAME
        cmp #<KUPLA1
        lda DFRAME+1
        sbc #>KUPLA1
        bcs _off
        lda b_init
        bne +
        inc b_init
-       lda kupla_d,x                   ; 6 spriteä (64 t kukin)
        sta BSPR,x
        lda kupla_d+192,x
        sta BSPR+192,x
        inx
        cpx #192
        bne -
+       lda p_y                         ; y: hahmon yläreuna - 22 kaikille
        sec
        sbc #22
        ldx #10
-       sta b_reg+1,x
        dex
        dex
        bpl -
        lda p_x                         ; x 9 bittiä (p_msb $c0 / 0) - KDX
        sec
        sbc #KDX
        sta b_lo
        lda p_msb
        beq +
        lda #1
+       sbc #0
        sta b_t
        lda #0
        sta b_msb
        ldx #10                         ; spritet 5..0: x = vasen + 24 * i
        ldy #5
-       lda b_lo
        clc
        adc b_off,y
        sta b_reg,x
        lda b_t
        adc #0
        lsr
        rol b_msb
        dex
        dex
        dey
        bpl -
        ldx #1
_off    stx b_on
        rts
b_off   .byte range(0, 144, 24)
kupla_d .binary "k2kupla.bin"             ; jalankulkijan puhekupla (runko.py kupla, kopio BSPR:ään)
kp2r_end
        .cerror kp2r_end > $4000, "kp2r ylittää $4000"

        * = $4800                       ; pankki 1 vapaa kuvan 1 jälkeen
kp2w
; ------------------------------------------------------------------ jalankulkija (kp2w, pankki 1 $4800-): spritet 6-7 jakorivin alla
; Nosturin spritet 6-7 näyttävät jakorivin PIRQ jälkeen jalankulkijaa (kaksi MC-spriteä päällekkäin, 12 x 42 MC-px):
; hahmo piirretään reaaliajassa korkeuden (perspektiivi) ja askelvaiheen mukaan, kun ne vaihtuvat. Rivin 250
; IRQ-koukku palauttaa spritet nosturille ja virittää jakorivin.
PSPR    = $cd00                         ; sarjat: 0 $cd00/$cd40, 1 $cd80/$cdc0 (kuvan 1 puhdas tausta vapautunut)
PPTR    = (PSPR & $3fff) / 64
PIRQ    = 74 + SPR_Y0 + 42 + 8          ; nosturilohkon alapuolella

ped_go
        lda #0
        sta p_set
        sta p_vis
        tax
-       sta PSPR,x
        inx
        bne -
        lda #$ff
        sta p_lh
        sta p_lp
        lda #0                          ; MC-yhteiset värit: musta, vaaleanpunainen (kasvot, takin valoreuna)
        sta $d025
        lda #10
        sta $d026
        sei
        lda #$4c
        sta irqhook
        lda #<hook2
        sta irqhook+1
        lda #>hook2
        sta irqhook+2
        cli
        rts

; hook2: rivin 250 IRQ:ssa: nosturin osoittimet (flip2), spritet 6-7 takaisin nosturille, jakorivi
hook2
        jsr flip2
        lda spr_xl+6
        sta $d00c
        lda spr_y+6
        sta $d00d
        lda spr_xl+7
        sta $d00e
        lda spr_y+7
        sta $d00f
        lda #SPR_MSB
        sta $d010
        lda #7
        sta $d02d
        sta $d02e
        lda #0
        sta $d01c
        lda #$ff
        sta $d01d
        sta $d01b
        lda b_shown                     ; kupla näytettiin: spritet 0-5 takaisin nosturille
        beq +
        lda #0
        sta b_shown
        tax
        tay
-       lda spr_xl,x
        sta $d000,y
        lda spr_y,x
        sta $d001,y
        lda #7
        sta $d027,x
        iny
        iny
        inx
        cpx #6
        bne -
        lda sset
        asl
        asl
        asl
        ldx #0
-       sta SCR3P,x
        clc
        adc #1
        inx
        cpx #6
        bne -
+
        lda sset
        asl
        asl
        asl
        ora #6
        sta SCR3P+6
        ora #7
        sta SCR3P+7
        lda p_vis
        beq +
        lda #PIRQ
        sta $d012
        lda #<pmid
        sta $fffe
        lda #>pmid
        sta $ffff
+       rts

; pmid: jakorivin IRQ: spritet 6-7 jalankulkijaksi, sitten takaisin riville 250 ytimen IRQ:hon
pmid
        pha
        asl $d019
        lda p_x
        sta $d00c
        sta $d00e
        lda p_y
        sta $d00d
        clc
        adc #21
        sta $d00f
        lda p_msb                       ; spritet 0-5 kuplana (nosturin rivit ovat jo ohi)
        ora b_msb
        sta $d010
        lda #2
        sta $d02d
        sta $d02e
        lda #$ff
        sta $d01c
        lda #0
        sta $d01d
        sta $d01b
        lda p_ptr
        sta SCR3P+6
        ora #1
        sta SCR3P+7
        lda b_on
        beq +
        sta b_shown
        stx b_sx
        ldx #11
-       lda b_reg,x
        sta $d000,x
        dex
        bpl -
        ldx #5
-       lda #1
        sta $d027,x
        txa
        clc
        adc #BPTR
        sta SCR3P,x
        dex
        bpl -
        ldx b_sx
+
        lda #IRQ_LINE
        sta $d012
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        pla
        rti

; ped: paikka taulusta (4 kehyksen välein) ja hahmo takimmaiseen sarjaan, kun korkeus tai askel vaihtui
ped
        lda now+1                       ; askel = now / 4
        sta p_t
        lda now
        lsr p_t
        ror
        lsr p_t
        ror
        cmp #151
        bcc +
        lda #150
+       tax
        lda PW_X,x                      ; x + 32 -> rasteri 24 + 2 * (x - 6) = 2 * (x + 32) - 52
        cmp #32 - 4
        bcs +
        lda #0                          ; vasemman reunan takana
        sta p_vis
        rts
+       asl
        sta p_t
        lda #0
        rol
        sta p_msb
        lda p_t
        sec
        sbc #52
        sta p_x
        lda p_msb
        sbc #0
        beq +
        lda #$c0
+       sta p_msb
        lda PW_Y,x
        clc
        adc #74
        sta p_y
        lda PW_Y,x
        sta p_top
        lda PW_H,x
        sta p_h
        lda PW_P,x
        sta p_ph
        cmp p_lp
        bne +
        lda p_h
        cmp p_lh
        beq _vis
+       lda p_ph
        sta p_lp
        lda p_h
        sta p_lh
        jsr pdraw
        lda p_set                       ; valmis sarja näkyviin seuraavassa jakorivissä
        eor #1
        sta p_set
        asl
        ora #PPTR
        sta p_ptr
_vis    lda #1
        sta p_vis
        jmp kupla

; pdraw: hahmo sarjaan 1 - p_set: hiukset, kasvot, takki (punainen, vasen reuna vaalea), jalat keinuvat askeleen mukaan
pdraw
        lda p_set
        eor #1
        asl
        asl
        asl
        asl
        asl
        asl
        asl                             ; sarja * 128
        clc
        adc #<PSPR
        sta sp
        lda #>PSPR
        adc #0
        sta sp+1
        ldy #127
        lda #0
-       sta (sp),y
        dey
        bpl -
        ldx p_h
        lda PF_HAIR,x
        sta pr1
        lda PF_FACE,x
        sta pr2
        lda PF_COAT,x
        sta pr3
        lda PF_LEG,x
        sta pr4
        lda PF_LEG2,x
        sta pr5
        lda PF_W,x
        sta pw
        ldx p_ph                        ; keinu: -2..2
        lda swing,x
        sta psw
        lda #0
        sta pr
_r      lda pr                          ; rivi kuvan alareunan alla: lopetetaan
        clc
        adc p_top
        cmp #PH
        bcc +
        rts
+       lda pr
        cmp pr1
        bcs +
        lda #1                          ; hiukset musta (%01)
        ldx #5
        jsr ppx
        lda #1
        ldx #6
        jsr ppx
        jmp _nx
+       cmp pr2
        bcs +
        lda #3                          ; kasvot vaaleanpunainen (%11)
        ldx #5
        jsr ppx
        lda #3
        ldx #6
        jsr ppx
        jmp _nx
+       cmp pr3
        bcc _nx                         ; kaula
        cmp pr4
        bcs _legs
        lda #6                          ; takki: 6 - w .. 6 + w - 1, vasen reuna valossa
        clc
        adc pw
        sta pdx
        lda #6
        sec
        sbc pw
        tax
        lda #3
        jsr ppx
-       inx
        cpx pdx
        bcs +
        lda #2
        jsr ppx
        jmp -
+
        lda pr                          ; kassi oikealla takin puolivälissä
        sec
        sbc pr3
        cmp #4
        bcs _nx
        lda pw
        clc
        adc #7
        tax
        lda #1
        jsr ppx
        jmp _nx
_legs   lda pr                          ; jalat: yläosa suoraan, alaosa keinuu
        cmp pr5
        lda #0
        bcc +
        lda psw
+       sta pdx
        lda #5
        clc
        adc pdx
        tax
        lda #1
        jsr ppx
        lda #7
        sec
        sbc pdx
        tax
        lda #1
        jsr ppx
_nx     inc pr
        lda pr
        cmp p_h
        bcs +
        jmp _r
+       rts

; ppx: pikseli (X, rivi pr) roolilla A spriteparin datasta (sp)
ppx
        cpx #12
        bcs +
        stx pxx
        sta prole
        ldy pr
        lda psrow,y
        sta pyo
        txa
        lsr
        lsr
        clc
        adc pyo
        tay
        txa
        and #3
        sta pyo
        lda prole
        asl
        asl
        ora pyo
        tax
        lda (sp),y
        ora role16,x                    ; ytimen taulu: rooli << (6 - 2 * pikseli) indeksillä rooli * 4 + pikseli
        sta (sp),y
        ldx pxx
+       rts

psrow   .byte (range(42) / 21) * 64 + (range(42) % 21) * 3
swing   .byte 0, 1, 1, 2, 2, 2, 1, 1, 0, -1 & 255, -1 & 255, -2 & 255, -2 & 255, -2 & 255, -1 & 255, -1 & 255
p_set   .byte 0
p_vis   .byte 0
p_x     .byte 0
p_y     .byte 0
p_msb   .byte 0
p_ptr   .byte 0
p_t     .byte 0
p_top   .byte 0
p_h     .byte 0
p_ph    .byte 0
p_lh    .byte 0
p_lp    .byte 0
pr      .byte 0
pr1     .byte 0
pr2     .byte 0
pr3     .byte 0
pr4     .byte 0
pr5     .byte 0
pw      .byte 0
psw     .byte 0
pdx     .byte 0
pxx     .byte 0
prole   .byte 0
pyo     .byte 0
        .include "k2walk.asm"
b_init  .byte 0                         ; kuplan muuttujat (kupla kp2b:n perässä): data kopioitu BSPR:ään
b_on    .byte 0                         ; kupla näkyvissä (pmid)
b_shown .byte 0                         ; pmid näytti kuplan: hook2 palauttaa spritet 0-5 nosturille
b_sx    .byte 0
b_lo    .byte 0
b_t     .byte 0
b_msb   .byte 0                         ; spritejen 0-5 x:n 9. bitit
b_reg   .fill 12                        ; $d000-$d00b kuplana
kp2w_end
        .cerror kp2w_end > $4f00, "kp2w osuu taulu2b:n esilatauksiin ($4f00-)"
