; Graafi yleisellä osalevyllä (make part P=graafi, runko PART 99): kello ja musiikki
; kehyksestä SCENE_START, loppu SCENE_END (12 iskua x 30 kehystä). Koodi src/proto/graafi, data tools/gfx/data/graafi/.
SCENE_START = 0
SCENE_END = 360
        .include "../../build/graafi/syms.inc"
        #S_LOAD f_graafi2               ; $8c00-$bf3f: ruutu, koodi, taulut ja bittikartta
        #S_CALL graafi_init
        #S_SHOW graafi_show             ; osalevyllä kuva ennen kelloa: kehys 0 ei musta
        #S_START SCENE_START
        #S_CALL graafi_go
        #S_LOAD f_graafi1               ; $2000-$2d89: neuvonantajan pala (vasta kehyksestä NEUVO_ALKU 240): graafin
                                        ; aikana, joten koko demossa levynvaihdon jälkeen ladataan vain GRAAFI2
