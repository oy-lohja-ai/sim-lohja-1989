; Vuosipartti 2026 yleisellä osalevyllä (make part P=vuosi2026, runko PART 99): kello ja musiikki
; kehyksestä SCENE_START, loppu SCENE_END (2 tahtia = 8 iskua x 30 kehystä). Koodi src/proto/vuosi (VUOSI=2026).
SCENE_START = 0
SCENE_END = 240
        .include "../../build/vuosi/2026/demo/syms.inc"
        #S_LOAD f_vuosi1                ; $6000-: kaistojen merkistöt (VIC-pankki 0) (vuosi_init kopioi $2800:aan)
        #S_LOAD f_vuosi2                ; $c000-: taulut ja tapahtumataulu
        #S_LOAD f_vuosi3                ; $e000-$faff: IRQ, kerneli, vuosi_init ja kehyksen logiikka
        #S_CALL vuosi_init              ; (2026: VUOSI1 paikalleen) tyhjä ruutu $2400, ensimmäinen kehys
        #S_FREE f_vuosi1                ; kopioitu: $6000- vapaa (greetsit esiladataan $4800-$bfff:ään)
        #S_START SCENE_START
        #S_CALL vuosi_go
