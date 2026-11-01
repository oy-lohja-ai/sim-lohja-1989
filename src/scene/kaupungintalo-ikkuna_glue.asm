; Kaupungintalo-ikkuna yleisellä osalevyllä (make part P=kaupungintalo-ikkuna, runko PART 99).
; Koodi src/proto/kaupungintalo (VARIANT=ikkuna): kamera-ajo patsaalta ikkunan läpi huoneeseen 0-179, huoneessa johtaja
; pelaa (pää nyökkää iskuihin, kädet näppäilevät, PC:n kuvaruutu vierii) 180 - SCENE_END-1.
SCENE_START = 0
SCENE_END = 360
        .include "../../build/kaupungintalo-ikkuna/demo/syms.inc"
        #S_LOAD f_kt1                   ; $1a00-$7f3f: kamera-ajon taulut ja huone
        #S_LOAD f_kt2                   ; $8000-$bf3f: kamera-ajon koodi ja muuttujat (ja näytön data)
        #S_LOAD f_kt0                   ; $c000-$cfff: ydin (kt_init, kt_go, IRQ), koosteen ruutu ja värit
        #S_LOAD f_kt6                   ; $e000-$ff3f: kamera-ajon alkukuvan (ulkonäkymä) bittikartta
        #S_CALL kt_init
        #S_SHOW kt_show                 ; osalevyllä kuva ennen kelloa: kehys 0 ei musta
        #S_START SCENE_START
        #S_CALL kt_go
