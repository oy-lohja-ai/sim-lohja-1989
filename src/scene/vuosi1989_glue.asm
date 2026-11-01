; Vuosipartti 1989 yleisellä osalevyllä (make part P=vuosi1989, runko PART 99): kello ja musiikki
; kehyksestä SCENE_START, loppu SCENE_END (2 tahtia = 8 iskua x 30 kehystä). Koodi src/proto/vuosi (VUOSI=1989).
SCENE_START = 0
SCENE_END = 240
        .include "../../build/vuosi/1989/demo/syms.inc"
        #S_LOAD f_vuosi1                ; $2800-: kaistojen merkistöt (VIC-pankki 0)
        #S_LOAD f_vuosi2                ; $3000-: taulut ja tapahtumataulu (build.py DATA_BASE: $c000 vapaa)
        #S_LOAD f_vuosi3                ; $e000-$faff: IRQ, kerneli, vuosi_init ja kehyksen logiikka
        #S_CALL vuosi_init              ; (2026: VUOSI1 paikalleen) tyhjä ruutu $2400, ensimmäinen kehys
        #S_START SCENE_START
        #S_CALL vuosi_go
