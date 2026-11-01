; Levyn ensimmäinen tiedosto: LOAD"*",8,1 tai LOAD"*",8 ja RUN. KERNAL lataa tämän (ainoa hidas lataus),
; joten sisältö on pakattu: siirretään pakattu payload paikalleen ja puretaan, sitten payloadin start
; (Krillin asennus, runko, linkkiskripti).
;
; RUNin jälkeen BASIC-ruutu romahtaa mustaan: merkkirivit irtoavat alhaalta alkaen kuin puretun talon kerrokset ja
; putoavat painovoimalla ruudun alle.
; Joka kehys FLD (Flexible Line Distance) jokaisen rivin yläpuolelle: rivin badline viivästyy rivin pudotuksen
; verran, ja välin rasteririvit ovat VIC:n tyhjää tilaa ($3fff = $ff: musta). YSCROLL kirjoitetaan vain
; tapahtumariveillä (rasteri-IRQ noin 6-8 rivin välein, ei odottavaa silmukkaa), joten pääsäie purkaa payloadia
; samaan aikaan lähes täydellä nopeudella.

        .include "payload.inc"  ; PAY_AT (pakatun paikka purettaessa), PAY_LEN, PAY_DEST, PAY_START

UZ      = $02                   ; purkajan nollasivu $02-$0d (BASICin, ei käytössä SYSin jälkeen)
L1      = $f7                   ; viimeinen rasteririvi, jolla badline on mahdollinen
LEND    = $fa                   ; kehyksen loppu: seuraavan kehyksen tapahtumat
ROW0    = $33                   ; rivin 0 badline ilman pudotusta (YSCROLL 3)
DT      = 1                     ; rivi irtoaa DT kehystä alemman rivin jälkeen (alin ensin)
FALL    = 32                    ; putoamisen kesto: y = k * k / 4 riviä kehyksessä k, 256 = ruudun alla
FX_END  = 24 * DT + FALL + 1    ; kaikki rivit ruudun alla

        * = $0801
        .word (+), 2026
        .null $9e, format("%d", entry)
+       .word 0

entry   sei
        lda #$7f                ; CIA1:n keskeytys pois romahduksen ajaksi (KERNAL-tila palautetaan ennen payloadia)
        sta $dc0d
        lda $dc0d
        lda #$35                ; KERNAL ja BASIC pois: IRQ-vektori RAMissa, payload ja kopio ovat $d000:n alla
        sta $01
        jsr fx_on               ; romahdus alkaa heti (kopio ja purku sen aikana)
        ldx #<(packed + PAY_LEN)        ; kopio ylöspäin lopusta alkuun (alueet voivat limittyä)
        ldy #>(packed + PAY_LEN)
        stx UZ
        sty UZ+1
        ldx #<(PAY_AT + PAY_LEN)
        ldy #>(PAY_AT + PAY_LEN)
        stx UZ+2
        sty UZ+3
        ldy #0
-       lda UZ
        bne +
        dec UZ+1
+       dec UZ
        lda UZ+2
        bne +
        dec UZ+3
+       dec UZ+2
        lda (UZ),y
        sta (UZ+2),y
        lda UZ
        cmp #<packed
        bne -
        lda UZ+1
        cmp #>packed
        bne -
        ldx #<PAY_AT
        ldy #>PAY_AT
        jsr unzx0
-       lda fx_t                ; romahdus loppuun (kuva on silloin jo musta)
        cmp #FX_END
        bcc -
        sei
        lda #$0b                ; kuva pois (IRQ ei ehkä ehtinyt)
        sta $d011
        lda #0
        sta $d01a
        lda #$ff
        sta $d019
        lda #$81                ; KERNAL-tila kuten ennen: CIA1:n ajastin A keskeyttää (payload asentaa Krillin KERNALilla)
        sta $dc0d
        lda #$37
        sta $01
        cli
        jmp PAY_START

fx_on   lda #0
        sta $d020               ; reuna musta
        sta fx_t
        lda #$ff                ; VIC:n tyhjä tila (FLD:n välit) piirtää $3fff:n tavua mustana
        sta $3fff
        lda #<fx_irq
        sta $fffe
        lda #>fx_irq
        sta $ffff
        lda #<fx_nmi
        sta $fffa
        lda #>fx_nmi
        sta $fffb
        lda #$1b
        sta $d011
        jsr fx_frame            ; ensimmäisen kehyksen tapahtumat
        lda #1
        sta $d01a
        sta $d019
        cli
        rts

fx_irq  pha                     ; tapahtuma: YSCROLL rivillä ev_l (rivin aikana, ei badline-rivillä), seuraava
        txa
        pha
        ldx fx_i
        lda ev_v,x
        beq _end                ; 0: kehyksen loppu (LEND)
        sta $d011
        inx
        stx fx_i
        lda ev_l,x
        sta $d012
        lda #$ff
        sta $d019
        pla
        tax
        pla
        rti
_end    tya
        pha
        inc fx_t
        lda fx_t
        cmp #FX_END
        bcs _off
        lda #$1b                ; seuraava kehys alkaa rivit lepotilassa (YSCROLL 3)
        sta $d011
        jsr fx_frame
        jmp _ack
_off    lda #$0b                ; kaikki rivit pudonneet: kuva pois (musta), keskeytykset loppuvat
        sta $d011
        lda #0
        sta $d01a
_ack    lda #$ff
        sta $d019
        pla
        tay
        pla
        tax
        pla
fx_nmi  rti

fx_frame                        ; kehyksen fx_t tapahtumat: rivi Y alkaa rasteririviltä b = ROW0 + 8 Y + pudotus
        ldx #0                  ; (badline: YSCROLL = b & 7 rivin alussa). Seuraava luonnollinen badline nat (fpos:sta
        lda #3                  ; alkaen, YSCROLL fy) siirretään kirjoittamalla rivillä nat - 1 joko b & 7 (b enintään 7
        sta fy                  ; rivin päässä) tai (nat + 6) & 7 (taas 7 riviä eteenpäin); tapahtumien väli >= 6 riviä
        lda #$30
        sta fpos
        ldy #0
_row    stx fn
        lda fx_t                ; pudotus k * k / 4, k = kehyksiä irtoamisesta
        sec
        sbc fx_st,y
        bcc _y0
        cmp #FALL
        bcc +
        lda #FALL
+       tax
        lda fx_sq,x
        .byte $2c               ; bit abs: ohitus
_y0     lda #0
        ldx fn
        clc
        adc fx_r8,y
        bcs _tail               ; rivi ja sen alapuoliset ruudun alla
        cmp #L1 + 1
        bcs _tail
        sta fb
_ch     jsr fx_nat
        cmp fb
        beq _ok
        sbc #0                  ; C = 0 (nat < b): w = nat - 1
        sta ev_l,x
        sta fw
        lda fb
        sbc fw                  ; C = 1: b - w
        cmp #8
        lda fb
        bcc +
        lda fw
        adc #6                  ; C = 1: w + 7
+       jsr fx_ev
        jmp _ch
_ok     adc #0                  ; C = 1: fpos = b + 1
        sta fpos
        iny
        cpy #25
        bne _row
_tail   jsr fx_nat              ; ei enää rivejä: badlinet siirretään L1:n ohi
        cmp #L1 + 1
        bcs _done
        sbc #0                  ; C = 0: w = nat - 1
        sta ev_l,x
        sta fw
        adc #6                  ; C = 1: w + 7
        jsr fx_ev
        jmp _tail
_done   lda #LEND
        sta ev_l,x
        lda #0
        sta ev_v,x
        sta fx_i
        lda ev_l
        sta $d012
        rts

fx_ev   and #7                  ; tapahtuma (fw, YSCROLL A): fy, fpos = fw + 1
        sta fy
        ora #$18
        sta ev_v,x
        inx
        lda fw
        clc
        adc #1
        sta fpos
        rts

fx_nat  lda fy                  ; A = fpos + ((fy - fpos) & 7)
        sec
        sbc fpos
        and #7
        clc
        adc fpos
        rts

fx_t    .byte 0                 ; kehys romahduksen alusta
fx_i    .byte 0                 ; seuraava tapahtuma
fy      .byte 0
fpos    .byte 0
fb      .byte 0
fw      .byte 0
fn      .byte 0
fx_sq   .for k := 0, k <= FALL, k += 1
        .byte k * k / 4 < 255 ? k * k / 4 : 255
        .next
fx_r8   .for r := 0, r < 25, r += 1
        .byte ROW0 + 8 * r
        .next
fx_st   .for r := 0, r < 25, r += 1
        .byte (24 - r) * DT
        .next
ev_l    .fill 64
ev_v    .fill 64

        .include "unzx0.asm"
packed  .binary "payload.zx0", 2
        .cerror packed > PAY_AT, "payload siirtyy alaspäin"
        .cerror packed > PAY_DEST, "purkaja purkualueella"
        .cerror PAY_AT + PAY_LEN > $3fff, "payload romahduksen tyhjän tilan tavun $3fff päällä"
