; Lohjantähden kuoppa (partti 5) yleisellä osalevyllä (make part P=kuoppa, runko PART 99): kello ja
; musiikki kehyksestä SCENE_START, loppu SCENE_END: kauhakohtaus 0-419 ja runko nousee 420-1019 (kp_defs.inc KUVA1,
; SIIRTO). Valmis torni (kuva 3) ei ole kuopassa (valmiin Lohjantähden vilahdus, jossa syttyy valoja, tuntuisi
; rikkinäiseltä). Kyltit omalla osalevyllään (src/scene/kuoppa-kyltit_glue.asm, välissä taulu2b).
; Koodi src/proto/kuoppa.
SCENE_START = 0
SCENE_END = 1020
        .include "../../build/kuoppa/demo/syms.inc"
        #S_LOAD f_kp0                   ; $1a00-$1fff: ytimen alku (kp_stage)
        #S_LOAD f_kp0s                  ; välialue $c000-: ydin $2000-$2dff (koko demossa graafin datan päällä)
        #S_LOAD f_kp1                   ; $2e00-$3fff: kuvan 1 koodi ja taulut
        #S_LOAD f_kp1c                  ; $4478-$7faf: kuva 1 pankissa 1, rungon esisiirrot 0-1, spritet, värit
        #S_LOAD f_kp1bs                 ; välialue $e000-: esisiirrot 2-3 ja kulun taulut $8800-$9fff
        #S_LOAD f_kp1ds                 ; välialue KP1BS:n perässä: varsien kärjet $c000-$c3ff
        #S_LOAD f_kpn                   ; $fc00-: nousu mustasta (kp_nousu.asm, väriketjut src/lib/haivytys.asm)
        #S_CALL kp_stage                ; välialueet paikalleen (koko demossa nämä esiladataan graafin aikana)
        #S_FREE f_kp0s
        #S_FREE f_kp1bs
        #S_FREE f_kp1ds
        #S_CALL kp_init
        #S_CALL kpn_prep                ; ruudun rivit talteen $c400-:aan ja mustiksi (nousu, kp_nousu.asm)
        #S_SHOW kpn_show                ; kuva 1 ennen kelloa mustana (kp_show ilman värimuistin kopiota)
        #S_START SCENE_START
        #S_CALL kp_go
        #S_CALL kpn_go                  ; kuva pyyhkiytyy esiin ylhäältä kehyksissä 0-9 (kuopan IRQ-koukku)
        #S_WAIT SCENE_START + 11        ; nousu valmis: talteenotto $c400- ja KPN $fc00- vapaiksi (KP2A, KP2B)
        #S_FREE f_kpn
        #S_LOAD f_kp2a                  ; $c478-$cfff: kuvan 2 ruutu pankissa 3, kuvan 2 koodi ja nosturi $c800-
        #S_LOAD f_kp2b                  ; $e000-$fd0f: kuvan 2 taulut, alkukuva ja värit (kuvan 1 aikana)
        #S_LOAD f_kpy                   ; $fd10-: pyyhkäisy kuvasta 1 kuvaan 2 (levyn loppuun: muiden paikat ennallaan)
        #S_CALL kp2_init
        #S_CALL py_init                 ; kuva 2 pyyhkiytyy esiin 402-419
        #S_WAIT SCENE_START + 432        ; kuva 2 näkyy (leikkaus 418) ja kuvan 1 viimeinen piirtotyö on päättynyt
        #S_FREE f_kp1
        #S_FREE f_kp1c
        #S_LOAD f_kp2r                  ; core_end-: kuvan 2 rakennusjärjestys ja valmiin rungon tavut
        #S_LOAD f_kp2w                  ; $4800-: jalankulkija
        #S_CALL kp2_go                  ; (ei S_WAITia loppuun: taulu päättyy tähän, joten taulu2b ja kylttien KP3
                                        ; esiladataan kuvan 2 aikana, part-kuoppa.json vapaana_lopussa)
