; Hillnerin kohtaus pääbuildissa: yhteiset vakiot (kohtaustaulu src/scene/hil_glue.asm, Hillnerin tiedostojen
; sisääntulot src/proto/hillner/glue_*.asm, purku). Ajat ovat demon kehyksiä clock0:sta, ja demon kehys 0 on biisin
; kehys TIM_SONG_START. Symbolit tulevat src/gen/timing.inc:stä (timing/timeline.c64.json);
; oletukset alla, jos timing.inc ei määrittele niitä.

        .weak
TIM_SONG_START = 2400           ; biisin kehys clock0:ssa (A1)
TIM_SCENE_HILLNER_START = 0
TIM_CUE_OSUMA = 1920            ; purkupallon osuma (biisin 4320, A2:n ykkönen)
TIM_SCENE_LOPPU_START = 2160    ; pimeys
TIM_SCENE_KOTI_START = 2400     ; kohtaus 2 (koti) Hillnerin perässä
TIM_SCENE_HILLNER_PURKU_END = TIM_SCENE_KOTI_START   ; Hillnerin viimeisen osan (purku) loppu (_END-symbolit timing.inc:stä)
TIM_CUE_AJOKYLTTI = 480         ; greetsit alkavat kamera-ajon loppukuvan kyltissä (isku 16)
TIM_CUE_LAHIKUVA = 900          ; leikkaus kamera-ajon loppukuvasta matalaan lähikuvaan (isku 30)
        .endweak

HIL_SCENE = TIM_SCENE_HILLNER_START
HIL_HIT   = TIM_CUE_OSUMA
HIL_END   = TIM_SCENE_HILLNER_PURKU_END  ; purku pimenee, kohtaus 2 alkaa (TIM_SCENE_HILLNER_END on vain alkulaskun loppu)
HIL_AJO   = TIM_CUE_AJOKYLTTI    ; luovutuksen jälkeen: ajo-kyltti (LOHJAN RAUTA ja tekstit.yaml:n hillner-eka)
HIL_LAHI  = TIM_CUE_LAHIKUVA     ; ajo-kyltti (kamera-ajon loppukuva) -> lähikuva ja sen kyltti
PURKU_LEAD = 2                   ; purku_go kehyksellä HIL_HIT - BALL_SWING - PURKU_LEAD: välähdys tasan HIL_HIT:ssä (mitattu)
HIL_TABLE = 1                    ; src/runko/link.asm: hil_glue.asm on pelkkä kohtaustaulu

DFRAME  = $d0                   ; demon kehys (16 bittiä), kasvaa kerran kehyksessä (frame_hook)
ZT      = $d2                   ; integraattorin nollasivu $d0-$df (Krill $e0-$ef, musiikki $c0-$cf)
INT_AT  = $0408                 ; integraattori (pysyvä) Krillin residentin perässä; frame_hook ensimmäisenä
FRAME_HOOK_AT = INT_AT
