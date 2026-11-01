; Johtajan kädet huoneessa (kaupungintalo-ikkuna, kt.asm huone_frame): käden tila bittikarttaan. Data ja
; tapahtumat kadet.asm (build.py kadet()). Vain bittikartta: ruutu ja värit ovat huone.kla:n.

KAD_RIVI0 = 160                 ; kätten solurivit 19-22 näkyvät riveillä 203-234: kopio (enintään noin 35 riviä)
KAD_RIVI1 = 235                 ; alkaa ennen riviä KAD_RIVI0 tai rivillä KAD_RIVI1, jotta säde ei ohita sitä

; kad_copy: Y = tila: solut kad_c0[Y]..: tavut kad_slo/shi[Y] + 8 * solu (Y-indeksi kad_y0 .. kad_y1) soluun
; kad_dlo/dhi[solu] + 8 * solu
kad_copy
        lda kad_slo,y
        sta z_ptr
        lda kad_shi,y
        sta z_ptr+1
        lda kad_y1,y
        sta z_kend
        ldx kad_c0,y
        lda kad_y0,y
        tay
-       lda $d011                       ; säde rivillä >= 256: heti
        bmi _cell
        lda $d012
        cmp #KAD_RIVI0
        bcc _cell
        cmp #KAD_RIVI1
        bcc -
_cell   lda kad_dlo,x
        sta z_dst
        lda kad_dhi,x
        sta z_dst+1
-       lda (z_ptr),y
        sta (z_dst),y
        iny
        tya
        and #7
        bne -
        inx
        cpy z_kend
        bne _cell
        rts
