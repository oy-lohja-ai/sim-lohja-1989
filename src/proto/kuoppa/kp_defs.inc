; Kuopan yhteiset vakiot ja nollasivu (kuoppa.asm ja kuvien 2-3 koodi)
        .weak
FRAME_HOOK = $0408
R_IDLE  = $0422
DFRAME  = $d0
KP_ALKU = 0                             ; kuoppa-kyltit (Makefile VARIANT=kyltit): osan kehys 0 on kuopan kehys KP_ALKU
KP_TAUKO = 0                            ; kuoppa-kyltit: kerrontataulu 2c osan kehyksistä KP_TAULU KP_TAUKO kehystä
KP_TAULU = 0                            ; (kp_tauko / kp_jatka): kuopan kello seisoo taulun ajan
        .endweak

ZP0     = $30
IRQ_LINE = 250
PIC     = 3 * 320                       ; kuva-alue alkaa merkkiriviltä 3
PICS    = 3 * 40
BMP_N   = 18 * 320
SCR_N   = 18 * 40
RIVIT   = SCR_N / 40                    ; kuva-alueen merkkirivit

SHOT2   = 600                           ; kuva 2 (runko) alkaa: 5 tahtia x 120 kehystä
SHOT3   = 1200                          ; kuva 3 (torni): 10 tahtia
CUT2    = SHOT2 - 2                     ; vaihto IRQ:ssa kehyksellä cue - 2: näkyvä vaihto on tasan kehyksellä cue
CUT3    = SHOT3 - 2
KUVA1   = 420                           ; kuopan osalevyllä kuva 1 loppuu tähän (datassa SHOT2): kuvat
SIIRTO  = SHOT2 - KUVA1                 ; 2-3 näkyvät SIIRTO kehystä aiemmin kuin niiden data (kuopan kehyksinä,
SHOT2_O = SHOT2 - SIIRTO                ; kuoppa-kyltit KP_ALKU) sanoo
SHOT3_O = SHOT3 - SIIRTO
PYYHK0  = CUT2 - SIIRTO - RIVIT         ; kuva 2 pyyhkiytyy kuvan 1 päälle rivi kehyksessä ennen leikkausta
LEPO1   = PYYHK0 - 4                    ; (kuoppa2.asm py_hook): kuva 1 ei aloita enää kierrosta
LOPPU2  = SHOT3_O                       ; kuopan loppu (glue SCENE_END, kuva 3 pois): kuva 2 ei
                                        ; aloita työtä tästä, joten nosturin askel ei vie suoritinta saumalta

SCR1    = $4400
SCR2    = $8400
SCR3    = $c400
SPRX    = $3a40                         ; spritet pankin sisällä
SPRP    = SPRX / 64
SHAPE0  = $4800                         ; esisiirrot (2304 t: maski 1152 + data 1152)
SHAPE1  = $5100
SHAPE2  = $8800
SHAPE3  = $9100
COL2    = $fa40                         ; kuvan 2 värit (kp2b)
COL3    = $8800                         ; kuvan 3 värit (kp3, pankki 2)
PH      = 144                           ; kuva-alueen rivit

        .virtual ZP0
src     .word ?                         ; piirto: puhdas tausta, kohde, maski, data
dst     .word ?
msk     .word ?
dat     .word ?
zsrc    .word ?
zdst    .word ?
zrest   .byte ?
shot    .byte ?                         ; näkyvä kuva 0, 1, 2
busy    .byte ?                         ; työ käynnissä
flip    .byte ?                         ; 1 = vaihda puskuri seuraavassa IRQ:ssa
shown   .byte ?                         ; näkyvä puskuri 0 (A, pankki 1) / 1 (B, pankki 2)
bhi     .byte ?                         ; takapuskurin bittikartan ylätavu ($60 / $a0)
back    .byte ?                         ; takapuskurin indeksi
ax      .byte ?                         ; ankkuri (origon projektio) MC-px
ay      .byte ?
ia      .byte ?
ip      .byte ?
wt      .byte ?
ld      .byte ?
col0    .byte ?                         ; rungon ensimmäinen sarake (etumerkillinen)
sft     .byte ?                         ; esisiirto 0-3
by      .byte ?                         ; rungon ylin rivi
r0      .byte ?                         ; suorakaide: sarakkeet r0..r1-1, rivit ry0..ry1-1
r1      .byte ?
ry0     .byte ?
ry1     .byte ?
yy      .byte ?
tmp     .byte ?
tmp2    .byte ?
ox0     .byte ?                         ; päällyksen rajat tällä kierroksella (MC-px)
ox1     .byte ?
oy0     .byte ?
oy1     .byte ?
px      .fill 5                         ; monikulmion kärjet
py      .fill 5
np      .byte ?
tone    .byte ?
pya     .byte ?                         ; monikulmion ylin ja alin rivi
pyb     .byte ?
xa      .byte ?                         ; viiva / reuna
ya      .byte ?
xb      .byte ?
yb      .byte ?
ddx     .byte ?
ddy     .byte ?
sx      .byte ?
sy      .byte ?
err     .byte ?
q       .byte ?
rem     .byte ?
pe      .byte ?                         ; monikulmion reunalaskuri
minx    .byte ?
mx4     .byte ?                         ; vasen sarake * 4
mlo     .byte ?                         ; vasemman sarakkeen siirtymä + takapuskuri
mhi     .byte ?
lx      .byte ?
rx      .byte ?
rx2     .byte ?
yend2   .byte ?
lpix    .byte ?
nool    .byte ?                         ; 1 = ei ääriviivaa
pflow   .byte ?                         ; kuvion rivisiirto
rpix    .byte ?
yb2     .byte ?
yend    .byte ?
smask   .byte ?
rmsk    .byte ?
oi      .byte ?                         ; päällyksen laskurit
ai      .byte ?
fidx    .byte ?
ow      .byte ?
ob      .byte ?
itmp    .byte ?                         ; IRQ:n omat
itmp2   .byte ?
fnow    .word ?                         ; kuvan 1 työn kehys
zy0     .byte ?                         ; palautettava alue (rivit) tälle kuvalle
zy1     .byte ?
zp_end
        .cerror zp_end > $c0, "nollasivu ylittää $bf (runko $c0-)"
        .endv

