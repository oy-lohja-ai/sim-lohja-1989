; MS-DOS-käynnistys koko demon alussa RUNin jälkeen:
; 80 saraketta hires-bittikartalla PC-henkisellä 4x8-kirjasimella, vaaleanharmaa mustalla, vilkkuva alaviivakursori.
; Käsikirjoitus (tekstit.yaml dos -> tools/disk/dos.py -> dos_data.inc) ajetaan rasteri-IRQ:ssa merkki kerrallaan,
; ja näppäin naksahtaa SID:n äänellä 1 (kohina). Musiikkina Patemathicin Appeltrad Act 0 (ACT0_*, $a000-, payload
; lataa sen ennen COMMAND.COMia, DOS_GO kelaa sen kohtaan ACT0_SEEK, IRQ soittaa). Pääsäie lataa
; samaan aikaan: payload musiikin, kokoa.py:n taulu ensimmäisen kohtauksen tiedostot. DOS_END odottaa
; käsikirjoituksen loppuun, pimentää kuvan reunuksessa, palauttaa VIC:n ja IRQ-vektorin ja kelaa biisin
; (music_seek, payloadin kopio jää ensimmäisen kohtauksen alle).
;
; Muisti: kaksi puskuria, vieritys kopioi näkyvästä toiseen ja kuva vaihtuu kerralla reunuksessa (ei repeytymistä).
; A: VIC-pankki 3, bittikartta $c000-$df3f (kirjoitus $01 = $34, osa I/O:n alla), värit $e000-$e3e7. B: pankki 1,
; värit $5c00-$5fe7, bittikartta $6000-$7f3f (ensimmäisen kohtauksen alkulataukset eivät saa osua, kokoa.py
; tarkistaa). Ohjelma, kirjasin ja käsikirjoitus DOS_AT-. Nollasivu $f0-$f7.

        .include "music.inc"
        .include "act0.inc"             ; DOS-ruudun musiikki (tools/music/music.py --laulu act0)
        .include "dos.inc"
        .include "runko.inc"            ; FRAME_HOOK (häivytys)

BMP     = $c000                 ; puskuri A
SCR     = $e000
BMP_B   = $6000                 ; puskuri B
SCR_B   = $5c00
IRQ_LINE = $fb                  ; reunus: puskurin vaihto ei osu kuvaan
dptr    = $f0                   ; bittikartan solu
gptr    = $f2                   ; kirjasimen merkki
sptr    = $f4                   ; käsikirjoitus
cnt     = $f6

        * = DOS_AT
        jmp dos_go
        jmp dos_end
        jmp dos_part

; Osalevy dos: DOS-ruutu kellon alusta ilman latauksia, sitten pimeä. DFRAME
; osan loppuun, jotta SCENE_OUT ei jää odottamaan (rungon IRQ ei käy DOS-ruudun aikana, joten kello seisoo).
dos_part sei
        ldx #0
        ldy #0
        jsr dos_go
        jsr dos_end
        lda #0
        sta $d0                 ; DFRAME (runko.inc)
        lda #$7f
        sta $d1
        rts

; X/Y = biisin kehys DOS_ENDin kelaukseen. Kutsu keskeytykset pois ja kuva pimeänä ($01 = $35); palaa cli:n kanssa.
dos_go  stx seek_f
        sty seek_f+1
        lda $fffe
        sta old_irq
        lda $ffff
        sta old_irq+1
        lda $dd00
        sta old_dd00
        lda $d018
        sta old_d018
        lda $d016
        sta old_d016
        lda #$34                ; bittikartta tyhjäksi, $d000- I/O:n alla
        sta $01
        lda #0
        tax
-       .for p := 0, p < $20, p += 1
        sta BMP + p * $100,x
        sta BMP_B + p * $100,x
        .next
        inx
        bne -
        lda #$35
        sta $01
        lda #$f0                ; vaaleanharmaa (PC:n väri 7) mustalla
-       sta SCR,x
        sta SCR + $100,x
        sta SCR + $200,x
        sta SCR + $2e8,x
        sta SCR_B,x
        sta SCR_B + $100,x
        sta SCR_B + $200,x
        sta SCR_B + $2e8,x
        inx
        bne -
        lda #0
        ldx #$18
-       sta $d400,x
        dex
        bpl -
        lda #0                  ; act 0 alusta ja kelaus kohtaan ACT0_SEEK hiljaa: soittimen STA $d418 muuttujaan,
        jsr ACT0_INIT           ; SID:n taso on 0 (nollattu yllä), ensimmäinen IRQ:n play-kutsu antaa tason
        lda #<a0_vol
        sta ACT0_D418_OP
        lda #>a0_vol
        sta ACT0_D418_OP+1
        lda #<ACT0_SEEK
        sta sfc
        lda #>ACT0_SEEK
        sta sfc+1
_seek   lda sfc
        ora sfc+1
        beq _seeked
        jsr ACT0_PLAY
        lda sfc
        bne +
        dec sfc+1
+       dec sfc
        jmp _seek
_seeked lda #31                 ; act 0:n häivytys (a0_fade) alusta
        sta flv
        lda #<$d418
        sta ACT0_D418_OP
        lda #>$d418
        sta ACT0_D418_OP+1
        lda #<script
        sta sptr
        lda #>script
        sta sptr+1
        jsr getb
        sta wait
        jsr setvic              ; puskuri A näkyviin
        lda #$08
        sta $d016
        lda #$3b                ; bittikartta, kuva päälle
        sta $d011
        lda #IRQ_LINE
        sta $d012
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        lda #1
        sta $d01a
        sta $d019
        cli
        rts

; Odottaa käsikirjoituksen loppuun (IRQ päällä), pimentää kuvan reunuksessa ja palauttaa koneen kuten ennen
; DOS_GOta; biisi kelataan DOS_GOn kehykseen. Palaa keskeytykset pois.
dos_end lda done
        beq dos_end
        sei
-       lda $d011               ; reunus alhaalla (rivi >= 256)
        bpl -
        lda #$0b
        sta $d011
        lda #0
        sta $d01a
        lda #$ff
        sta $d019
        lda old_irq
        sta $fffe
        lda old_irq+1
        sta $ffff
        lda old_dd00
        and #3
        sta $dd00
        lda old_d018
        sta $d018
        lda old_d016
        sta $d016
        lda #0
        ldx #$18
-       sta $d400,x
        dex
        bpl -
        ldx seek_f
        ldy seek_f+1
        jsr music_seek
        jmp hv_on               ; SID hiljaa, biisi häivyy sisään (haivytys.asm)

irq     pha
        txa
        pha
        tya
        pha
        lda $01
        pha
        lda #$35
        sta $01
        asl $d019
        jsr ACT0_PLAY           ; act 0 joka kehys, myös vierityksen aikana: vieritys (frame) voi kestää yli
        inc sfc                 ; kehyksen, joten frame ajetaan keskeytykset päällä; sisäkkäinen IRQ soittaa ja
        bne +                   ; kirjaa kehyksen (pend), ja frame ajetaan perään kiinni, joten käsikirjoitus ja
        inc sfc+1               ; act 0 pysyvät samassa kehyksessä (muuten IRQ:ita putoaisi)
+       jsr a0_fade
        lda busy
        beq _run
        inc pend
        bne _out
_run    inc busy
        cli
_again  jsr frame
        sei
        lda pend
        beq _fin
        dec pend
        cli
        jmp _again
_fin    dec busy
_out    pla
        sta $01
        pla
        tay
        pla
        tax
        pla
        rti

; Act 0 häivytetään nollaan IRQ:sta FADE_AT alkaen (dos.py ACT0_FADE): soittimen $d418-kirjoitus
; ohjataan a0_vol-muuttujaan ja SID:n tasoksi tulee min(soittimen taso, flv / 2), flv 31 -> 0 yhden per IRQ.
a0_fade lda sfc+1
        cmp #>FADE_AT
        bcc _x
        bne +
        lda sfc
        cmp #<FADE_AT
        bcc _x
+       lda #<a0_vol
        sta ACT0_D418_OP
        lda #>a0_vol
        sta ACT0_D418_OP+1
        lda flv
        beq +
        dec flv
+       lsr
        sta ftmp
        lda a0_vol
        and #$0f
        cmp ftmp
        bcc +
        lda ftmp
+       sta ftmp
        lda a0_vol
        and #$f0
        ora ftmp
        sta $d418
_x      rts

; Kerran kehyksessä: edellisen näppäimen portti kiinni, käsikirjoituksen tapahtumat, joiden viive on kulunut,
; ja kursorin vilkku (8 kehystä näkyvissä, 8 pois kuten CGA:n laitteistokursori).
frame   lda flip                ; vieritetty puskuri näkyviin (IRQ reunuksessa)
        beq +
        jsr setvic
+       lda gate                ; naksahduksen portti kiinni
        beq +
        lda #$80
        sta $d404
        lda #0
        sta gate
+       lda done
        bne blink
        lda wait
        beq run
        dec wait
        bne blink
run     jsr cur_hide
-       jsr step
        lda done
        bne blink
        jsr getb                ; seuraavan tapahtuman viive, 0 = samassa kehyksessä
        sta wait
        beq -
blink   inc bcnt
        lda bcnt
        and #8
        bne cur_hide
cur_show lda cur_on
        bne +
        lda crow
        sta cur_r
        lda ccol
        sta cur_c
        jsr cur_xor
        lda #1
        sta cur_on
+       rts
cur_hide lda cur_on
        beq +
        jsr cur_xor
        lda #0
        sta cur_on
+       rts

cur_xor lda cur_c               ; alaviiva solun riveille 6-7 koko solun leveydeltä
        ldx cur_r
        jsr cell
        tax
        lda nib,x
        sta t_m
        lda #$34
        sta $01
        ldy #6
        lda (dptr),y
        eor t_m
        sta (dptr),y
        iny
        lda (dptr),y
        eor t_m
        sta (dptr),y
        lda #$35
        sta $01
        rts

; A = sarake (0-79), X = rivi (0-24) -> dptr = solun tavu, A = 0 vasen puolitavu (bitit 7-4), 1 oikea
cell    sta t_col
        and #$fe                ; (sarake / 2) * 8
        sta dptr
        lda #0
        sta dptr+1
        asl dptr
        rol dptr+1
        asl dptr
        rol dptr+1
        clc
        lda dptr
        adc rowlo,x
        sta dptr
        lda dptr+1
        adc rowhi,x
        adc front               ; ei muistinumeroa: rivin ja sarakkeen siirto alle $2000
        sta dptr+1
        lda t_col
        and #1
        rts

getb    ldy #0                  ; käsikirjoituksen seuraava tavu, Z = 0-tavu
        lda (sptr),y
        inc sptr
        bne +
        inc sptr+1
+       cmp #0
        rts

step    jsr getb                ; op: 0 loppu, 1 tulosta, 2 rivinvaihto, 3 näppäin, 4 tyhjä
        beq op_end
        cmp #1
        beq op_print
        cmp #2
        beq newline
        cmp #3
        beq op_key
        rts
op_end  lda #1
        sta done
        rts
op_print jsr getb
        sta cnt
-       jsr getb
        jsr out
        dec cnt
        bne -
        rts
op_key  jsr getb                ; merkki, kohinan taajuus, AD (tömähdyksen, ei käytössä)
        sta t_ch
        jsr getb
        tax
        jsr getb
        lda sfc+1               ; naksahdus vain ennen IRQ:ta CLICK_END (act 0:n ääni 1 alkaa, dos.py ACT0_V1)
        cmp #>CLICK_END
        bcc +
        bne _nokey
        lda sfc
        cmp #<CLICK_END
        bcs _nokey
+       stx $d401               ; naksahdus: kohina
        lda #0
        sta $d400
        sta $d406
        sta $d405               ; kohina: yksi lyhyt naksu (decay 6 ms), ei häntää
        lda #$81
        sta $d404
        lda #1
        sta gate
_nokey  lda t_ch
        cmp #13
        beq newline
        cmp #8
        beq bs
out     jsr putc                ; A = merkki kursorin kohtaan, kursori eteenpäin
        inc ccol
        lda ccol
        cmp #80
        bcs newline
        rts
newline lda #0
        sta ccol
        inc crow
        lda crow
        cmp #25
        bcs +
        rts
+       dec crow
        jmp scroll
bs      lda ccol                ; askelpalautin: edellinen merkki pois
        beq +
        dec ccol
        lda #32
        jmp putc
+       rts

putc    sec                     ; A = merkki $20-$7f kohtaan crow, ccol
        sbc #32
        sta gptr
        lda #0
        sta gptr+1
        asl gptr
        rol gptr+1
        asl gptr
        rol gptr+1
        asl gptr
        rol gptr+1
        lda ccol
        ldx crow
        jsr cell
        tax
        clc
        lda gptr
        adc #<font
        sta gptr
        lda gptr+1
        adc #>font
        sta gptr+1
        lda keep,x
        sta t_m
        lda #$34
        sta $01
        ldy #7
-       lda (gptr),y            ; kirjasin puolitavun alabiteissä: vasemmalle (X = 0) siirretään ylös
        cpx #1
        bcs +
        asl a
        asl a
        asl a
        asl a
+       sta t_g
        lda (dptr),y
        and t_m
        ora t_g
        sta (dptr),y
        dey
        bpl -
        lda #$35
        sta $01
        lda ccol                ; rivin pituus vieritykselle
        lsr
        clc
        adc #1
        ldx crow
        cmp rlen,x
        bcc +
        sta rlen,x
+       rts

; Vieritys kaksoispuskurilla: näkyvän puskurin rivit 1-24 toisen riveille 0-23 (vain kirjoitettu leveys: rlen
; näkyvän, blen toisen puskurin rivien solut; pidempi kahdesta, joten vanha loppu pyyhkiytyy), toisen rivi 24
; tyhjäksi, sitten puskurit vaihtavat paikkaa. Kirjoitus jatkuu heti uuteen, VIC vaihtaa seuraavan IRQ:n alussa
; reunuksessa (flip), joten kuva vierii kerralla eikä keskeneräistä kopiota näy.
scroll  lda flip                ; edellinen vaihto vielä tekemättä (kaksi vieritystä samassa IRQ:ssa)
        beq +
        jsr setvic
+       lda #$34
        sta $01
        ldx #1
_row    lda rowlo,x             ; gptr = näkyvän rivi r, dptr = toisen rivi r - 1
        sta gptr
        lda rowhi,x
        clc
        adc front
        sta gptr+1
        lda rowlo-1,x
        sta dptr
        lda rowhi-1,x
        clc
        adc back
        sta dptr+1
        lda rlen,x              ; solut: pidempi kahdesta
        cmp blen-1,x
        bcs +
        lda blen-1,x
+       pha
        lda rlen,x
        sta blen-1,x
        pla
        jsr _copy
        inx
        cpx #25
        bne _row
        lda blen+24             ; toisen rivi 24 tyhjäksi
        ldy #0
        sty blen+24
        jsr _clear
        lda #$35
        sta $01
        ldx #24                 ; rlen <-> blen, front <-> back
-       lda rlen,x
        ldy blen,x
        sta blen,x
        tya
        sta rlen,x
        dex
        bpl -
        lda front
        ldy back
        sta back
        sty front
        lda #1
        sta flip
        rts

; A = solut (0-40), gptr -> dptr; solut 32- toisella sivulla
_copy   beq _done
        cmp #33
        bcc +
        sbc #32
        sta t_n
        lda #0                  ; 32 solua = 256 tavua (y kiertää nollaan)
        jsr _seg
        inc gptr+1
        inc dptr+1
        lda t_n
        jmp _seg
+       asl
        asl
        asl
_seg    sta t_m                 ; t_m = tavuja (0 = 256)
        ldy #0
-       .rept 8
        lda (gptr),y
        sta (dptr),y
        iny
        .endrept
        cpy t_m
        bne -
_done   rts

; A = solut, toisen puskurin rivi 24 nollaksi
_clear  ldx #24
        ldy rowlo,x
        sty dptr
        pha
        lda rowhi,x
        clc
        adc back
        sta dptr+1
        pla
        cmp #33
        bcc +
        sbc #32
        sta t_n
        lda #0
        jsr _zseg
        inc dptr+1
        lda t_n
        jmp _zseg
+       asl
        asl
        asl
        beq _done
_zseg   sta t_m
        ldy #0
        lda #0
-       .rept 8
        sta (dptr),y
        iny
        .endrept
        cpy t_m
        bne -
        rts

; VIC näyttämään puskuria front ($dd00: vain arvot 0-3, Krillin väylä samassa portissa; pankin vaihto IRQ:sta
; latauksen aikana on sallittu). Vaihto vain reunuksessa: pitkän vierityksen jälkeen seuraava IRQ
; tulee heti rti:n jälkeen millä rivillä tahansa, ja kesken kuvan vaihto näyttäisi rivin puoliksi kummastakin.
setvic  lda $d011               ; rivi >= 256, >= $fb tai < $30: reunus
        bmi +
        lda $d012
        cmp #IRQ_LINE
        bcs +
        cmp #$30
        bcs setvic
+       lda #0
        sta flip
        lda front
        cmp #>BMP
        bne +
        lda #0                  ; A: pankki 3, värit $e000, bittikartta $c000
        sta $dd00
        lda #$80
        sta $d018
        rts
+       lda #2                  ; B: pankki 1, värit $5c00, bittikartta $6000
        sta $dd00
        lda #$78
        sta $d018
        rts

sfc     .word 0                 ; IRQ:t DOS_GOsta (kelauksessa act 0:n laskuri)
busy    .byte 0                 ; 1: frame kesken (sisäkkäinen IRQ vain soittaa)
pend    .byte 0                 ; sisäkkäisten IRQ:iden kehykset, frame ajaa ne kiinni
a0_vol  .byte 0                 ; act 0:n $d418 kelauksen ja häivytyksen ajan
flv     .byte 31                ; häivytyksen taso * 2 + 1 (a0_fade)
ftmp    .byte 0

        .include "music/music.asm"      ; music_seek (payloadin kopio on ensimmäisen kohtauksen latausten alla)
        .include "haivytys.asm"         ; hv_on: biisin häivytys sisään kelauksen jälkeen

rowlo   .for r := 0, r < 25, r += 1  ; rivin alku puskurin alusta (puskurit sivun rajalla: + front tai back)
        .byte <(r * 320)
        .next
rowhi   .for r := 0, r < 25, r += 1
        .byte >(r * 320)
        .next
nib     .byte $f0, $0f
keep    .byte $0f, $f0
seek_f  .word 0
old_irq .word 0
old_dd00 .byte 0
old_d018 .byte 0
old_d016 .byte 0
wait    .byte 0
done    .byte 0
gate    .byte 0
bcnt    .byte 0
cur_on  .byte 0
cur_r   .byte 0
cur_c   .byte 0
crow    .byte 0
ccol    .byte 0
t_col   .byte 0
t_m     .byte 0
t_ch    .byte 0
t_n     .byte 0
t_g     .byte 0
rlen    .fill 25, 0           ; näkyvän puskurin rivin kirjoitetut solut (sarake / 2 + 1), vieritys kopioi vain ne
blen    .fill 25, 0           ; toisen puskurin
front   .byte >BMP            ; kirjoitettava puskuri (VIC näyttää sen viimeistään seuraavassa IRQ:ssa)
back    .byte >BMP_B
flip    .byte 0               ; 1: VIC vaihtaa puskuriin front seuraavan IRQ:n alussa

        .include "dos_data.inc"
dos_top
        .cerror dos_top > $f600, "dos: ohjelma yli $f5ff (ensimmäisen kohtauksen ALKU2 $f600-): ", format("$%04x", dos_top)
