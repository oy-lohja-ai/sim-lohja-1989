; Spritet: samanaikaisten spritejen ennätys. Jokainen 8 spritestä käynnistyy 17 rivin välein katkeamatta myös
; kehysrajan yli (crunch lyhentää instanssin 17 riviin), joten kehykseen osuu 146-147 DMA-käynnistystä. Aikataulu
; ja hostin todennus: plan.py, kerneli ja data: build.py, musiikki SID-virtana: sidvirta.py. DEN pois, ei
; keskeytyksiä kernelin aikana. Kerneli kasvattaa DFRAMEa ($d019:n rasterilippu, rivi 250) ja kirjoittaa biisin
; muuttuvat SID-rekisterit kerran kierroksessa.
;
; INTEGRATED (osalevy, src/scene/spritet-lentavat_glue.asm): spr_init (pääsäie ennen kelloa), spr_go (kellon alussa
; rivillä 250: VIC, kerneli; palaa kehyksessä E_FRAME soittimen tila kohdallaan). Proto: BASIC-käynnistys, ilman
; soitinta.

        .include "kernel.inc"
        .weak
INTEGRATED = 0
WAITPOKE = 0
WAITF   = 3
D1H     = 6                     ; viive IRQ-riviltä riville ENTRY - 3 (noin)
D1L     = 46
D2C     = 4                     ; 5 * D2C + 1 + 2 * D2N + 3 * D2O sykliä
D2N     = 1
D2O     = 1
        .endweak

DFRAME  = $d0                   ; demon kehys (runko.inc), kerneli kasvattaa
FRAME_HOOK = $0408              ; runko.inc RES_AT + 0: soitin ja kello (spr_exit)
ZERO    = $f0                   ; aina 0 (kernelin 3 syklin lda)
ZH      = $f1                   ; virran sivu
ZBLK    = $f2                   ; virran lohko
ZK      = $b8                   ; leijuvat logot: logon n tila ZK + n (6 t), logon X ja $d010 taulusta (build.py floats)
KNP     = $be                   ; askelsivu (2 t): laskurit lda (KNP),y, virta kirjoittaa ylätavun kehyksittäin
save_sp = $f4
ZXR     = $f5                   ; X kernelin alussa (tietueen siirros)
ZPH     = $f6                   ; tilarivin vaihe 0..NPH - 1 (NPH, NPH + 1: ensimmäinen kehys ilman tekstiä)
ZS0     = $f7                   ; SID-virran laskuri s (2 t): seuraa DFRAMEa enintään tietue kierroksessa
ZS1     = $f8
IRQ_LINE = ENTRY - 30           ; kaksois-IRQ (lämmittelyt alkavat riveillä WARM)
TICK_LINE = 250                 ; kehyksen raja kuten rungon IRQ (frame_hook)

        .if INTEGRATED
        * = $1a00
        .else
        * = $0801
        .word (+), 2026
        .null $9e, format("%d", start)
+       .word 0
        jmp start

        * = $1a00
start   sei                     ; proto: kohtaus alusta loputtomiin, SID-virta ilman soitinta
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #$35
        sta $01
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        lda #$0b
        sta $d011
        jsr spr_init
        ldx #24
-       lda first_all,x
        sta $d400,x
        dex
        bpl -
again   lda #<S_FRAME
        sta DFRAME
        lda #>S_FRAME
        sta DFRAME+1
        .if WAITPOKE            ; mittaus: odottaa, kunnes $02:een kirjoitetaan ulkoa muu kuin 0
        lda #0
        sta $02
-       lda $02
        beq -
        ldx #WAITF              ; vielä WAITF kehystä ennen alkua
-       bit $d011
        bpl -
-       bit $d011
        bmi -
        dex
        bne --
        .endif
-       bit $d011               ; kuten rungon s_sync: kello alkaa rivillä 250
        bpl -
-       lda $d012
        cmp #TICK_LINE
        bne -
        jsr spr_go
        jmp again
nmi     rti
        .endif

; spr_hiljaa (pääsäie): rungon IRQ:n R_TICKissä pyörivä efekti pois ja kuva mustaksi, jotta efektin muistiin voi
; ladata; osalevyllä R_TICK on jo rts.
R_TICK_VEC = $041f              ; runko.inc R_TICK + 1
R_TICK_RTS = $0421              ; runko.inc RES_AT + 25
spr_hiljaa
        sei
        lda #<R_TICK_RTS
        sta R_TICK_VEC
        lda #>R_TICK_RTS
        sta R_TICK_VEC+1
        lda #$0b                ; DEN pois: musta
        sta $d011
        lda #0
        sta $d015
        cli
        rts

; Pääsäie ennen kelloa (kuva musta): taulut. Ei VIC:iä.
spr_init
        ldx #0                  ; $d011 riveittäin: RSEL 0 riveillä 248-251 (pystyreuna ei sulkeudu), DEN pois,
-       lda #$6b                ; alatavut 0-55 (rivit 0-55 ja 256-311) epäkelpo tila ECM+BMM: musta, taivaan
        cpx #56                 ; värin vaihto (kellon jälkeinen H-rivi, rivit 267-318) ei näy
        bcc +
        lda #$4b                ; reunarivit 56-59 ja 252-255 ECM: tyhjän tilan tavu $79ff (rasteri 50 %), joten
        cpx #EDGE_TOP           ; välähdyksen reuna liukenee eikä rivin lopun kirjoituksen porras erotu
        bcc +
        lda #$0b
        cpx #248
        bcc +
        lda #$03
        cpx #252
        bcc +
        lda #$4b
+       sta d11tab,x
        inx
        bne -
        lda #0
        sta ZERO
        sta $7fff               ; tyhjän tilan tavu (pankki 1): tausta näkyy
        lda #EDGE_DITHER
        sta $79ff               ; ECM-rivien tyhjän tilan tavu
        rts
EDGE_TOP = 60
EDGE_DITHER = $55

; Osalevyllä ennen kelloa (#S_SHOW): kehys 0 ei musta. Ilman IRQ:ta näkyvät vain lämmittelyinstanssit (kehyksen 1
; yläosa: raketti riveillä WARM) mustalla (ECM + BMM, DEN päällä: spritet näkyvät ikkunassa). spr_go asettaa kaiken.
spr_show
        jsr spr_regs
        .for i := 0, i < 8, i += 1
        lda #WARM[i] & $ff
        sta $d001 + 2 * i
        .next
        lda #$7b
        sta $d011
        lda #$ff
        sta $d015
        rts

; VIC-pankki, värit ja lämmittelyinstanssit (spr_show, spr_go)
spr_regs
        lda #0
        sta $d020
        sta $d021
        sta $d017
        sta $d01d
        sta $d01b
        sta $d018               ; ruutu $4000 (osoittimet $43f8)
        lda #2                  ; VIC-pankki 1
        sta $dd00
        lda #D010
        sta $d010
        lda #$ff                ; monivärispritet: $d025 ja $d026 yhteiset, oma väri instansseittain
        sta $d01c
        lda #7
        sta $d025
        lda #1
        sta $d026
        ldx #7
-       lda rimg0 + 200         ; lämmittelyinstanssit: raketti ja ensimmäisen kohteen X
        sta SCREEN + $3f8,x
        txa
        asl a
        tay
        lda sx_tab
        sta $d000,y
        lda sc_tab
        sta $d027,x
        dex
        bpl -
        rts

; Kellon alussa rivillä 250 (DFRAME = S_FRAME): VIC ja kerneli. Kehyksessä S_FRAME + 1 pystyreuna auki rivillä 51
; ja kaksois-IRQ rivillä IRQ_LINE; kernelin ensimmäinen kello rivillä 250. Palaa kehyksessä E_FRAME.
spr_go  tsx
        stx save_sp
        sei
        lda #0
        sta $d015
        sta $d01a
        jsr spr_regs
        ldy #<S_FRAME           ; virran osoitin kehykselle S_FRAME (kerneli päivittää kellon jälkeen)
        lda xrec,y
        sta ZXR
        lda dhi + (S_FRAME >> 8)
        clc
        adc dlo,y
        tay
        lda pagemap,y
        .include "patch.inc"    ; sivu jokaisen kirjoituskäskyn ylätavuun
        lda #<kloop             ; rungon viimeinen hyppy takaisin alkuun (virran tietue E: trampoliini spr_exitiin)
        sta kjmp+1
        lda #>kloop
        sta kjmp+2
        .if !TIIVIS
        .for _k := 0, _k <= CT_AHEAD, _k += 1   ; taivaan väri kehyksille S..S + CT_AHEAD (kerneli kirjoittaa loput)
        lda ct_init + _k
        sta CT + ((S_FRAME + _k) & $ff)
        .next
        lda ct_init
        sta $d021
        .endif                  ; tiivis: $D021 = 0 jo spr_regsissä (kirjoitus tässä tekisi harmaan pisteen kehykseen 0)
        lda #NPH
        sta ZPH
        .if WOBBLE
        .for _k := 0, _k < len(ZK_INIT), _k += 1   ; logojen alkutilat (aalto rungon matkalla)
        lda #ZK_INIT[_k]
        sta ZK + _k
        .next
        lda #<knA
        sta KNP
        lda #>knA
        sta KNP+1
        .endif
        lda #<S_FRAME
        sta ZS0
        lda #>S_FRAME
        sta ZS1
        lda #$03                ; rivi 250: RSEL 0 ennen riviä 251
        sta $d011
-       bit $d011
        bpl -
-       bit $d011               ; kehys S_FRAME + 1
        bmi -
        lda #$0b
        sta $d011
-       lda $d012
        cmp #49
        bne -
        lda #$1b                ; DEN riveillä 49-51 (ei rivillä 48: ei badlineja): pystyreunan kiikku auki rivillä 51
        sta $d011
-       lda $d012
        cmp #53
        bne -
        lda #$0b
        sta $d011
        .for i := 0, i < 8, i += 1
        lda #WARM[i] & $ff       ; lämmittely: täyskorkea instanssi, joka päättyy hilan ensimmäiseen aloitukseen
        sta $d001 + 2 * i
        .next
        lda #$ff
        sta $d015
        lda #<irq1              ; kaksois-IRQ rivillä IRQ_LINE (ennen lämmittelyjä): tarkka sykli
        sta $fffe
        lda #>irq1
        sta $ffff
        lda #IRQ_LINE
        sta $d012
        lda #1
        sta $d01a
        lda #$ff
        sta $d019
        cli
-       jmp -

        .align 256              ; viivesilmukat samalla sivulla
irq1    lda #<irq2
        sta $fffe
        lda #>irq2
        sta $ffff
        inc $d012
        asl $d019
        tsx
        cli
        .fill 16, $ea
irq2    txs
        ldx #8
-       dex
        bne -
        bit $00
        lda $d012
        cmp $d012
        beq +
+       sei                     ; tästä tarkka: lämmittelyt alkavat riveillä WARM (DMA-pysähdykset ovat samat joka kerta)
        lda #0
        sta $d01a
        lda #TICK_LINE          ; kernelin kello: $d019:n bitti 0 rivillä 250
        sta $d012
        lda #$ff
        sta $d019
        ldy #D1H                ; noin riville ENTRY - 3
-       ldx #D1L
-       dex
        bne -
        dey
        bne --
        .for i := 0, i < 8, i += 1
        lda #FIRST[i] & $ff
        sta $d001 + 2 * i
        .next
        ldy #D2C                ; viive kernelin vaiheeseen (crunch-kirjoitus syklillä 15)
-       dey
        bne -
        .fill D2N, $ea
        .if D2O
        bit $ea
        .endif
        ldx ZXR
        lda #0
kgo     jmp kentry
        .cerror (>irq1) != (>*), "viivekoodi ylittää sivun"


; Kerneli tänne, kun DFRAME >= E_FRAME (rungon viimeinen jmp, ZX = 1): viimeiset SID-arvot, VIC pois, soittimen tila.
spr_exit
        .for _r := 0, _r < len(EXITREG), _r += 1
        lda last_rec + _r
        sta EXITREG[_r]
        .next
        lda #0
        sta $d015
        sta $d017
        lda #$0b
        sta $d011
-       lda DFRAME              ; kello E_FRAMEen kernelin tapaan (rivin 250 lippu, ilman soitinta: kehyksen E tietue
        cmp #<E_FRAME           ; on last_rec): viimeinen kierros voi palata DFRAMEssa E - 1 ennen rivin 250 lippua
        lda DFRAME+1            ; (koko demossa rivillä 168), ja tilan palautus (noin 160 riviä) ylittäisi kehyksen
        sbc #>E_FRAME           ; rivin 250, jolloin kello jäisi kehyksen jälkeen (biisi kehyksen myöhässä)
        bcs +
        lda $d019
        sta $d019
        lsr a
        lda DFRAME
        adc #0
        sta DFRAME
        lda DFRAME+1
        adc #0
        sta DFRAME+1
        jmp -
+       lda #$ff
        sta $d019
        .if INTEGRATED          ; soittimen tila kehyksen E_FRAME kohdalla: erot alun tilaan (build.py restore)
        .include "tila.inc"
-       lda $d019               ; seuraavan kehyksen rivi 250: sen soittimen kutsu (biisin kehys E, kello E + 1) tässä,
        lsr a                   ; koska ku_cut2 nollaa ajastimen paluussa eikä runko saisi kutsua kiinni
        bcc -
        lda #1
        sta $d019
        jsr FRAME_HOOK
        .endif
        ldx save_sp
        txs
        rts





        .align 256              ; taulut (vain CPU)
d11tab  .fill 256
        .include "stream.inc"   ; Y-indeksoidut taulut sivun alussa, pagemap, tietueet
        .include "data.inc"
        .cerror * > CODE_TOP, "koodi ja taulut yli CODE_TOP:n (build.py): ", format("$%04x", *)
code_end

        * = SPR_BASE            ; VIC-pankki 1: ruutu $4000 (vain osoittimet), kuvat (valot, tilarivi)
        .include "sprites.inc"
        .cerror * > $7f00, "spritekuvat yli $7f00:n"

        .include "kernel_code.inc"
        .include "pages.inc"    ; tilarivin taulut ja SID-virta (build.py: vapaat sivut)
