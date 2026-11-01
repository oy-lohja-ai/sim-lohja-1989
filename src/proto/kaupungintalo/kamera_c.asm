; Kamera-ajo (kamera.asm): vaihto huoneeseen. KT0:n lopussa.

; kam_vaihto: s = 1, kooste on huone: VIC pankkiin 1, spritet pois, huoneen värit ja huoneen IRQ
kam_vaihto
        lda #0
        sta $d015
        sta kam_on
        lda #2
        sta $dd00
        lda #((H_SCREEN & $3fff) >> 6) | ((H_BITMAP & $3fff) >> 10)
        sta $d018
        lda #<irq                       ; huoneen IRQ ennen värien kopiota: kopio kestää rivin HUONE_LINE yli, jolloin
        sta $fffe                       ; IRQ odottaa ja tulee rti:n jälkeen samassa kehyksessä (muuten FRAME_HOOK
        lda #>irq                       ; jäisi väliin kehyksessä KAM_LOPPU)
        sta $ffff
        lda #HUONE_LINE
        sta $d012
        ldx #<H_VCOL
        ldy #>H_VCOL
        jsr vcol
        jsr huone_frame
        pla
        tay
        pla
        tax
        pla
        rti

