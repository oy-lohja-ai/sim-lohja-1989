; Alkuruudun ajonaikaiset taulut (logo.asm nollaa nollasivun; nämä alustetaan käytössä)
sx      .fill NV
sy      .fill NV
fw      .fill NF                ; täyttöpaino 0..255
level   .fill NF                ; sävytaso, 0 = ei piirretä
bvx     .fill 2                 ; viiste: kulmien x (a, b), y, erotuskuviot
bvy     .fill 2
bvd     .fill 2
fvis    .fill NF                ; tahko näkyy (lankamallin takasärmät)
ndone   .fill NNID
ndot    .fill NNID
nlo     .fill COLS              ; tämän kuvan sarakevälit
nhi     .fill COLS
olo     .fill 2 * COLS          ; puskurin edellisen kuvan välit (A, B)
ohi     .fill 2 * COLS
hlw     .fill 2                 ; vaakaviivan leveys puskurin reunoissa
dl      .fill 12                ; kappaleiden kantadeterminantit
dh      .fill 12
lacc    .fill 14                ; valon summat
obx0    .fill 3                 ; palikoiden ruutulaatikot
obx1    .fill 3
oby0    .fill 3
oby1    .fill 3
fact    .fill 4                 ; ryhmällä näkyviä tahkoja
ncmin   .byte ?                 ; tämän kuvan sarakeväli (ranges)
ncmax   .byte ?
fcmin   .byte ?                 ; täytön sarakeväli
fcmax   .byte ?
ocmin   .fill 2                 ; puskurin edellisen kuvan sarakeväli (A, B)
ocmax   .fill 2
bact    .fill 4                 ; palikka laskettu tässä kuvassa (t >= LAND; timantti aina): muut ohitetaan
rvx     .fill NRV
rvy     .fill NRV
proflast .word ?
xh      .fill 8                 ; kappaleen kulmien x- ja y-ylätavut
yh      .fill 8
mx      .fill 3                 ; lento: M = R D' rivit ja D
my      .fill 3
mz      .fill 3
dd      .fill 9
xsn     .word ?
ysn     .word ?
zsn     .word ?
; mittarit (luetaan emulaattorista): kuvat, niihin kuluneet kehykset, näkyvän kuvan kehys, vaiheprofiili
renders .word ?
rframes .word ?
r0f     .word ?
shownt  .word ?
profl   .fill 8
profm   .fill 8
profh   .fill 8
profk   .byte ?
proff   .byte ?
; lento ja valo (eivät mahdu nollasivulle MUSIC_ZP:n alle)
ee      .byte ?                 ; lennon e (252..0)
dsc     .byte ?
dox     .byte ?
doy     .byte ?
drx     .word ?
dry     .word ?
drz     .word ?
lc0     .byte ?                 ; valo kamerassa (etumerkillinen)
lc1     .byte ?
lc2     .byte ?
lmx     .byte ?                 ; valo mallissa
lmy     .byte ?
lmz     .byte ?
objt    .fill 4
tt      .word ?                 ; IRQ: kohtauksen kehys
tmpi    .fill 4                 ; IRQ:n välitulokset
; tila (aikajana)
yaw     .word ?
light   .word ?
pitch   .byte ?
push    .byte ?
side    .byte ?
kd      .byte ?                 ; iskun kehys (0..19) tai $ff
fwblk   .byte ?                 ; palikoiden täyttöpainojen AND
slist   .byte ?                 ; lankamallin särmälistan indeksi ($ff = kaikki)
nmrest  .byte ?                 ; nimi asetettu lepoon
