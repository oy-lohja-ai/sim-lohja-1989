; Kappaleiden välit (proj.asm transform kutsuu; taulujen perässä, koska koodi $1a00-$3fff on täynnä).
;
; Kappale siirtyy edellisen mukaan niin, että etusärmien ero on tarkalleen VALI_*: palikka 1 x (ja heijastus),
; palikka 2 y, lukittu timantti x ja y. Ei purussa (sen kuvia ei näytetä).
gaps_b
        lda exiting
        bne _gx
        lda bact+1
        beq _g2
        lda sx+G_R0             ; palikka 1: sx += sx[R0] + VALI_X - sx[L1]
        clc
        adc #VALI_X
        sec
        sbc sx+G_L1
        ldx glast+1
        ldy gfirst+1
        jsr addx
        clc
        adc obx0+1
        sta obx0+1
        lda obx1+1
        clc
        adc tmp
        sta obx1+1
        lda rlive               ; heijastuksen kulmat rvx = sx (reflect kopioi ennen siirtoa)
        beq _g2
        ldx #7
-       lda rvx,x
        clc
        adc tmp
        sta rvx,x
        dex
        cpx #4
        bcs -
_g2     lda bact+2
        beq _gx
        lda sy+G_T0             ; palikka 2: sy += sy[T0] - VALI_Y - sy[B2]
        sec
        sbc #VALI_Y
        sec
        sbc sy+G_B2
        ldx glast+2
        ldy gfirst+2
        jsr addy
        clc
        adc oby0+2
        sta oby0+2
        lda oby1+2
        clc
        adc tmp
        sta oby1+2
_gx     rts

gaps_d                          ; lukittu timantti: x palikan 2 oikeasta, y palikan 1 yläkulmien keskeltä
        lda exiting
        bne _dx
        lda sx+G_R2
        clc
        adc #VALI_X
        sec
        sbc sx+G_DL
        ldx #NV - 1
        ldy #NB
        jsr addx
        lda sy+G_TL1
        clc
        adc sy+G_TR1
        ror a
        sec
        sbc #VALI_DY
        sec
        sbc sy+G_DB
        ldx #NV - 1
        ldy #NB
        jmp addy
_dx     rts

addx                            ; sx[Y..X] += A (tmp = A, palauttaa A:n)
        sta tmp
        sty tmp+1
-       lda sx,x
        clc
        adc tmp
        sta sx,x
        cpx tmp+1
        beq +
        dex
        bcs -                   ; aina (cpx: X > Y)
+       lda tmp
        rts

addy                            ; sy[Y..X] += A (tmp = A, palauttaa A:n)
        sta tmp
        sty tmp+1
-       lda sy,x
        clc
        adc tmp
        sta sy,x
        cpx tmp+1
        beq +
        dex
        bcs -                   ; aina (cpx: X > Y)
+       lda tmp
        rts
