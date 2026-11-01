; Hillnerin kohtaus kohtaustauluna: src/runko/link.asm sisällyttää tämän taulun kohtaan
; (HIL_TABLE = 1, src/scene/hil.inc). Vain lataukset, odotukset ja sisääntulot; koodi on Hillnerin tiedostoissa:
;   CRANE1, 2, 1B, 1C  kamera-ajo (src/proto/hillner): hil_prep, hil_go, hil_main1, hil_main, hil_fin, hil_sign
;   AJO             ajo-kyltti (src/proto/kyltti VARIANT=ajo) ja sen vaihe: ajo_on, ajo_go, IRQ (glue_ajo.asm)
;   KYLTTI          lähikuvan kyltti ja siirtymä: lahi_go, lahi_end, IRQ (glue_lahi.asm)
;   FIN             lähikuva pyyhkäisyä varten; PURKU1-3 purku (src/purku): purku_init, purku_go
; Levyn tiedostot luetaan tämän #S_LOAD-riveistä (levy.json names_from).

        #S_LOAD f_crane1                ; $1a00-$746f: koodi, savu ja asettelujen 0-2 tietueet
        #S_LOAD f_crane2                ; $c400-: spritet ja asettelun 3 tietueet
        #S_CALL hil_prep                ; ennen kelloa: asettelu 0 kuvan ollessa musta (noin 6 kehystä)
        #S_START HIL_SCENE
        #S_CALL hil_go                  ; kamera-ajo IRQ:ssaan, palaa heti
        #S_CALL hil_main1               ; asettelut 1-3 ja savu, palaa noin kehyksellä 160
        #S_LOAD f_crane1b               ; asettelun 4 tietueet (noin 50 kehystä, asettelu 4 tarvitaan kehyksellä 258)
        #S_CALL hil_main2               ; asettelu 4, palaa noin kehyksellä 220
        #S_LOAD f_crane1c               ; $8c00-: asettelun 5 tietueet ja luovutuksen solut (noin 30 kehystä)
        #S_CALL hil_main                ; asettelu 5, palaa kun viimeinen asettelu näkyy
        #S_FREE f_crane1                ; ajo-kyltin alueella ($4400-$63ff) vain asettelun 0 tietueita (build.py);
        #S_LOAD f_ajo                   ; koodi ja luovutuksen tietueet ovat yhä muistissa
        #S_CALL hil_fin                 ; kameran pysähdyttyä luovutuskuva pankkiin 2
        #S_CALL ajo_on                  ; ajo-kyltin IRQ ja ensimmäinen kuva takapuskuriin
        #S_WAIT HIL_AJO - 2
        #S_CALL ajo_go                  ; greetsit iskulla HIL_AJO, maalattu teksti pois (hil_sign)
        #S_LOAD f_kyltti                ; $1a00-$43bf kamera-ajon koodin päälle (hil_sign oli viimeinen kutsu)
        #S_LOAD f_fin                   ; $e000-
        #S_CALL lahi_prep               ; pyyhkäisyn solulistat $c000-:aan (pankki 3 on vapaa)
        #S_WAIT HIL_LAHI                ; ajo-kyltin IRQ ottaa kyltin pois kehyksellä HIL_LAHI - 1
        #S_FREE f_ajo
        #S_CALL lahi_go                 ; pankki 1, pyyhkäisy lähikuvaan, lähikuvan kyltin alustus
        #S_CALL lahi_on                 ; lähikuvan kyltti IRQ:hun
        #S_FREE f_crane1b
        #S_FREE f_crane1c
        #S_FREE f_crane2
        #S_FREE f_fin
        #S_LOAD f_purku1                ; purku greetsien aikana: koodi $8000, korkea kuva $aa00, kasa $e000
        #S_LOAD f_purku2
        #S_LOAD f_purku3
        #S_CALL purku_init              ; spritet letterboxiin ja painuman koodi, kyltti pyörii
        #S_WAIT HIL_HIT - BALL_SWING - PURKU_LEAD
        #S_CALL lahi_end                ; sei, kyltti purun IRQ:lle
        #S_CALL purku_go                ; ottaa IRQ:n (kutsuu frame_hookia), palaa heti; pimenee HIL_END:ssä
        #S_WAIT purku_free_at           ; laaja kuva: lähikuvan kyltti sammui leikkauksessa
        #S_FREE f_kyltti
        #S_CALL purku_quiet             ; kasa valmis, B näkyvissä: $1a00-$5bff vapaa (part-hillner.json
                                        ; vapaana_lopussa, seuraavan osan esilataus purun lopun aikana)
