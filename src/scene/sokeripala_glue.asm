; Sokeripala (demon loppu ennen lopputekstejä) yleisellä osalevyllä (make part P=sokeripala,
; runko PART 99): kello ja musiikki kehyksestä SCENE_START, loppu SCENE_END (13,5 tahtia: panoraama 4,5,
; lehti 3, peli 4, taulu 2). Koodi src/proto/sokeripala, rakenne ja muisti sokeripala.asm:n alussa.
SCENE_START = 0
SCENE_END = 1620
        .include "../../build/sokeripala/demo/syms.inc"
        #S_LOAD f_sp0                   ; $1a00-: ydin (IRQ, tapahtumat, panoraama, pyörähdys, taulun moduuli)
        #S_LOAD f_spp1                  ; $5c00-$7f3f: panoraaman puskuri A ja sarakkeet 0-11
        #S_LOAD f_sppi                  ; $c000-: alku, kaupunki nousee esiin yötaivaan alta
        #S_CALL sp_init
        #S_SHOW sp_show
        #S_START SCENE_START
        #S_CALL sp_go
        #S_LOAD f_spp2                  ; $4000-$5bff: sarakkeet 12-50 panoraaman aikana (sarake n kehyksestä 8 n + 1)
        #S_WAIT SCENE_START + T_ALKU    ; alku ohi: SPP3 sen paikalle
        #S_FREE f_sppi
        #S_LOAD f_spp3                  ; $c000-$cbff: sarakkeet 51-59
        #S_LOAD f_spt                   ; $fa40-: puskutraktorin spritet pankissa 3 ja koodi (TRAK_T0-)
        #S_CALL sp_trak
        #S_LOAD f_sp2a                  ; $8000-$bfff: pyörähdyksen ruudut, merkistö, profiilit, asennot
        #S_CALL sp_lehti                ; pyörähdyksen kaksi ensimmäistä asentoa pankkiin 2
        #S_WAIT SCENE_START + T_LEHTI + 1        ; panoraama ohi: terävä sivu sen paikalle pyörähdyksen aikana
        #S_FREE f_spp1
        #S_FREE f_spp2
        #S_FREE f_spp3
        #S_FREE f_spt
        #S_LOAD f_sp2d                  ; $4000-$7f3f: sivu (kynä, ruutu, bittikartta)
        #S_CALL sp_sivu
        #S_WAIT SCENE_START + T_SIVU + 1        ; pyörähdys ohi: peli sen paikalle
        #S_FREE f_sp2a
        #S_LOAD f_sp3                   ; $8000-$bf3f: peli (spritet, ruutu, solupalat, spritetaulu, bittikartta)
        #S_LOAD f_sp3b                  ; $e000-: pelin solukopiot
        #S_WAIT SCENE_START + T_PELI + 1        ; sivu ohi: taulun bittikartta sen paikalle
        #S_FREE f_sp2d
        #S_LOAD f_sp4                   ; $6000-$7f3f: taulun bittikartta
        #S_LOAD f_sp4k                  ; $4800-: taulun ajonaikainen koodi (taulun aikana ydin on vapaa)
        #S_CALL sp_taulu
        #S_WAIT SCENE_START + T_TAULU + 1       ; peli ohi ja IRQ pankissa 1: ydin, pankki 2, $c000-$cfff ja
        #S_FREE f_sp3                   ; $e000-$fff9 vapaita loppuun asti (part-sokeripala.json vapaana_lopussa:
        #S_FREE f_sp3b                  ; seuraavan osan esilataus taulun aikana)
        #S_FREE f_sp0
