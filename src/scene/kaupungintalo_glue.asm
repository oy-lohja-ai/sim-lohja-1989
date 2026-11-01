; Kaupungintalo yleisellä osalevyllä (make part P=kaupungintalo, runko PART 99): näytön lähikuva 0-119 (kursori
; Katastrofit-valikolle, kuvaruutu laajenee 60-119) ja peli 120 - SCENE_END-1 (kamera-ajo ja huone ovat osa
; kaupungintalo-ikkuna). Koodi src/proto/kaupungintalo.
SCENE_START = 0
SCENE_END = 840
        .include "../../build/kaupungintalo/demo/syms.inc"
        #S_LOAD f_kt2                   ; $8000-$bf3f: näytön lähikuva
        #S_LOAD f_kt0                   ; $c000-$cfff: ydin (kt_init, kt_go, IRQ)
        #S_LOAD f_kt3                   ; $e000-$ff3f: pelin ruutu bittikarttana (näytön laajeneminen 60-)
        #S_LOAD f_kt4                   ; $2000-$5fff: pelin koodi, P1, ruudut, merkistöt A ja P1, spritet
        #S_CALL kt_init
        #S_SHOW kt_show                 ; osalevyllä kuva ennen kelloa: kehys 0 ei musta
        #S_START SCENE_START
        #S_CALL kt_go
        #S_CALL peli_init
        #S_CALL kt_peli_ok              ; ydin vaihtaa peliin kehyksessä 120
        #S_WAIT 122                     ; näyttö on ohi: loput merkistöt sen muistiin
        #S_FREE f_kt2
        #S_LOAD f_kt5                   ; $6000-$85ff: merkistöt ja kartat P2-P4
