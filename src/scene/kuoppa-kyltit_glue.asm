; Kuoppa-kyltit (partti 5) yleisellä osalevyllä (make part P=kuoppa-kyltit, runko PART 99): valmis
; Lohjantähti kuopan kehyksestä KP_ALKU = 1260 alkaen, ryhmälogokyltit putoavat, kaupat avautuvat ja lentävät
; taivaalle, rakennus pimenee (kuoppa kahtena osana, välissä taulu2b).
; Kerrontataulu 2c (mustavalkoinen plakaatti):
; kylttien tultua osan kehyksistä T2C 240 kehystä (pankki 3, src/proto/taulu N=2c), kuopan kello seisoo sen ajan
; (kp_tauko, kp_jatka), sitten kyltit lentävät. Koodi src/proto/kuoppa (VARIANT=kyltit).
SCENE_START = 0
T2C = 450                               ; taulun kehys 0 (src/proto/taulu/Makefile DF0_2c, kuoppa Makefile KP_TAUKO)
SCENE_END = 780                         ; 540 + taulu 240 (lähdöt taulun jälkeen 8 kehyksen välein, viimeinen
                                        ; lento päättyy kehykseen 779)
        .include "../../build/kuoppa/demo-kyltit/syms.inc"
        .include "../../build/kuoppa/demo-kyltit/kpt_syms.inc"
        #S_LOAD f_kp0c                  ; $1a00-$2719: ydin (IRQ, työ, toggle-ajojen apu)
        #S_LOAD f_kp3                   ; $8200-$9f45: kuvan 3 ruutu, värit, koodi ja julkisivut pankkiin 2
        #S_LOAD f_kp3b                  ; $a3c0-$bf3f: kuvan 3 bittikartta (kaksi tiedostoa: esilataus kuopan aikana)
        #S_LOAD f_kp4                   ; $2800-: kyltit (pudotusmoduuli, logot), hengitys ja ikkunavalot
        #S_CALL kp3_init                ; valot osan kehyksen 0 tilaan
        #S_CALL kp4_go
        #S_SHOW kp3_show                ; kuva ennen kelloa: kehys 0 ei musta
        #S_START SCENE_START
        #S_CALL kp3_start
        #S_LOAD f_kpt                   ; $c100-: taulun 2c koodi (pankki 3, kuoppa-kyltit ei käytä sitä)
        #S_LOAD f_kptb                  ; $e000-$ff3f: taulun bittikartta
        #S_CALL taulu_init              ; ruutu $cc00 mustaksi, spritet $c000 (kuva ennallaan)
        #S_WAIT SCENE_START + T2C - 1
        #S_CALL kp_tauko
        #S_CALL taulu_go
        #S_WAIT SCENE_START + T2C + 240 - 1
        #S_CALL kp_jatka
        #S_FREE f_kpt                   ; pankki 3 vapaa taulun jälkeen (seuraavan esilataukset)
        #S_FREE f_kptb
