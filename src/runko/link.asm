; Linkkiskripti: demon kulku kohtaustauluna (Next Levelin ja The Labin JSR-ketju datana).
; Ajaja kutsuu taulun askeleet pääsäikeessä; kohtaukset pyörivät omissa IRQ:issaan ja kutsuvat FRAME_HOOKia, joten
; taulu lataa seuraavaa samaan aikaan. Ajat ovat demon kehyksiä (DFRAME) aikajanalta (src/gen/timing.inc).
; Kohtauksen askeleet ovat kohtauksen omistajan tiedostossa (src/scene/<nimi>_glue.asm, makrot runko.inc:ssä);
; koodi on kohtauksen omissa tiedostoissa, ei residentissä.
; PART (runko.mk): 0 = koko demo, 1 = Hillner, 2 = koti, 3 = loppu, 4 = greetsit, 5 = alku, 97 = integraatio
; (tools/disk/kokoa.py: taulu ladataan levyltä kohtaus kerrallaan), 99 = muu osa yksin (osavaljas: make part P=nimi).

        .weak
PART    = 0
HAVE_KOTI = 0                           ; runko.mk: 1, kun kodin demo-PRG (build/koti/demo/koti.prg) on buildissa
HAVE_ALKU = 0                           ; runko.mk: 1, kun alun palat (build/logo/demo/syms.inc) ovat buildissa
HAVE_GREETSIT = 0                       ; runko.mk: 1, kun greetsien palat (build/greetsit/demo/syms.inc) ovat buildissa
koti_quiet = 0                          ; kodin syms.inc: palaa, kun kodin loppukuva on yhdessä pankissa
TIM_SCENE_GREETSIT_START = 0            ; aikajana ilman greetsejä (src/gen/timing.inc)
TIM_SCENE_ALKU_START = 0                ; aikajana ilman alkua: osalevy kehyksestä 0, kesto 960
TIM_SCENE_ALKU_END = TIM_SCENE_ALKU_START + 960
NAYTTO_ALKU = 0                         ; näyttölevy (PART 98): 1 = partti mukana
NAYTTO_HILLNER = 0
NAYTTO_KOTI = 0
NAYTTO_GREETSIT = 0
NAYTTO_LOPPU = 0
        .endweak
NAYTTO_START = NAYTTO_ALKU ? TIM_SCENE_ALKU_START : NAYTTO_HILLNER ? TIM_SCENE_HILLNER_START : NAYTTO_KOTI ? TIM_SCENE_KOTI_START : NAYTTO_GREETSIT ? TIM_SCENE_GREETSIT_START : TIM_SCENE_LOPPU_START
ALKU_ON = TIM_SCENE_HILLNER_START >= TIM_SCENE_ALKU_END   ; alku aikajanalla Hillnerin edellä
PART_START = PART == 99 ? SCENE_START : PART == 98 ? NAYTTO_START : PART == 97 ? KULKU_START : [0, TIM_SCENE_HILLNER_START, TIM_SCENE_KOTI_START, TIM_SCENE_LOPPU_START, TIM_SCENE_GREETSIT_START, TIM_SCENE_ALKU_START][PART]   ; payloadin START: kello ja musiikki tästä

        .if PART < 2 || (PART == 98 && NAYTTO_HILLNER)
        .include "hil.inc"              ; Hillner (ajo, purku): vakiot ja kulku
        .include "parts.inc"            ; build/d64 (tools/gfx/d64.py syms)
        .endif

s_ops                                   ; taulun rutiinit samalla sivulla: askeleen ensimmäinen tavu on alatavu
s_load  jmp R_LOADCOMPD                 ; S_LOAD: X/Y = nimi
s_loadr jmp R_LOADRAW                   ; S_LOAD raakatiedostolle
        .if PART == 98
s_skip  jmp skip_to                     ; NAYTTO_IN: X/Y = kehys
        .endif
s_wait  jmp R_WAIT                      ; S_WAIT: X/Y = kehys
        .if PART == 97
s_chunk jmp ku_chunk                    ; integraatio: X/Y = seuraavan kohtauksen taulun nimi
s_istart jmp ku_start                   ; I_START: X/Y = kohtauksen ensimmäinen kehys
s_iseam jmp ku_seam                     ; I_SEAM: X/Y = kohtauksen ensimmäinen kehys, jatkuva siirtymä
s_ishow stx ku_show                     ; I_SHOW: X/Y = kohtauksen ensimmäisen kuvan rutiini
        sty ku_show+1
        rts
s_isong stx ku_song                     ; I_SONG: X/Y = biisin kehys - DFRAME (kerneli soitti biisin itse)
        sty ku_song+1
        rts
s_isongat stx ku_at                     ; I_SONGAT: X/Y = biisin kehys seuraavan kohtauksen alussa
        sty ku_at+1
        rts
        .endif
s_call  stx _j+1                        ; S_CALL: X/Y = osoite
        sty _j+2
_j      jmp 0
        .cerror (s_ops ^ *) >> 8, "taulun rutiinit eivät ole samalla sivulla"
        .if PART == 97
        .include "kulku.asm"            ; integraation rutiinit ja makrot (src/runko/kulku.asm)
        .endif
; Kohtausten väli koko demossa, kun kohtaukset eivät mahdu muistiin yhtä aikaa: edellinen kohtaus pimenee lead
; kehystä ennen seuraavan alkua (seuraavan latausten ja alustuksen mitattu aika ja varaus), jolloin seuraava alkaa
; tahdilleen. Osalevyllä kohtauksen loppu on pimeys ja musiikin häivytys.
SCENE_IN .segment frame, lead, cut = blank_res   ; cut: edellisen kohtauksen lopetus (oletus: kuva pimeäksi)
        .if PART == 0 && S_G.CLOCKED
        #S_WAIT \frame - \lead
          .if !S_PRE
        #S_NEXT
          .endif
S_PRE   := 0
        #S_FREE_ALL
        #S_CALL \cut
        .endif
        .endsegment
SCENE_PRE .segment              ; koko demossa: tästä eteenpäin seuraavan kohtauksen esilataukset edellisen aikana
        .if PART == 0
        #S_NEXT
S_PRE   := 1
        .endif
        .endsegment
S_PRE   := 0
NAYTTO_IN .segment frame        ; näyttölevy: edellisen partin jälkeen muisti vapaaksi ja kello ja musiikki hiljaa eteenpäin
        .if S_G.CLOCKED               ; NAYTTO_LEAD kehystä ennen seuraavan alkua (latauksille aikaa), mustaa saa olla
        #S_NEXT
        #S_FREE_ALL
        #S_STEP s_skip, \frame - NAYTTO_LEAD
        .endif
        .endsegment
NAYTTO_OUT .segment frame       ; partin loppu: kuva pimeäksi rungon IRQ:lla
        #S_WAIT \frame
        #S_CALL blank_res
        .endsegment
NAYTTO_LEAD = 200                       ; partin lataukset ja alustus ennen sen S_STARTia (pisimmät noin 200 kehystä)
SCENE_OUT .segment frame
        .if PART
        #S_WAIT \frame
        #S_CALL part_end
        .endif
        .endsegment
LEAD_GREETSIT = 180                     ; GREETSIT1-2 (mitattu 170) ja greetsit_init purun jälkeen
LEAD_KOTI = 180                         ; KOTI1-3 ja koti_init1 (koti_prep) greetsien jälkeen
LOPPU_STEPS .segment            ; loppu (runko, src/runko/loppu.asm) SCENE_IN:in tai NAYTTO_IN:in jälkeen
        .include "loppu_glue.asm"   ; src/runko/loppu_glue.asm (myös integraation kohtaus)
        .endsegment
LEAD_LOPPU = 30                         ; loppu_pre 3 ja loppu_init 2 (LOPPU0-2 esiladattu kodin aikana; muuten LOPPU0 ja
                                        ; LOPPU1 kodin jälkeen: aikajanalla väli)

script  ldx run_i                       ; taulun ajaja (pääsäie): askel = rutiini ja X/Y (runko.inc S_STEP)
        lda s_tab,x
        sta _op+1
        lda s_tab+1,x
        ldy s_tab+2,x
        inx
        inx
        inx
        stx run_i
        tax
_op     jsr s_ops
        jmp script
run_i   .byte 0
s_sync  bit $d011                       ; levyn ensimmäinen S_START: kehys 0 alkaa rivillä RES_IRQ_LINE
        bpl s_sync
-       lda $d012
        cmp #RES_IRQ_LINE
        bne -
clock0  rts                             ; kehys 0 alkaa tästä
        .if PART != 97                  ; integraatio: ku_cut (kulku.asm)
blank_res                               ; rungon IRQ ja kuva pimeäksi
        jsr irq_res_on
        lda #$0b
        sta $d011
        rts
blank_go                                ; osalevyn oma kulku rungon IRQ:lla (biisi, latausväli): pimeä kuva ja IRQ päälle
        jsr blank_res
        cli
        rts
irq_res_on                              ; rungon IRQ kohtausten välissä (kuva jää, spritet pois), I-lippu ennallaan
        php
        sei
        jsr R_IRQ_ON
        lda #0
        sta $d015
        plp
        rts
        .endif

s_tab
        .if PART == 97                  ; integraatio: ikkuna, johon kohtausten taulut ladataan (KUA-, ensimmäinen tässä)
        .include "kulku0.asm"
        .fill s_tab + KU_WIN - *, 0
        .endif
        .if PART == 98                  ; näyttölevy: valitut partit peräkkäin omilla latauksillaan
          .if NAYTTO_ALKU
        #NAYTTO_IN TIM_SCENE_ALKU_START
        .include "alku_glue.asm"
        #NAYTTO_OUT TIM_SCENE_ALKU_END
          .endif
          .if NAYTTO_HILLNER
        #NAYTTO_IN TIM_SCENE_HILLNER_START
        .include "hil_glue.asm"
        #NAYTTO_OUT HIL_END
          .endif
          .if NAYTTO_KOTI
        #NAYTTO_IN TIM_SCENE_KOTI_START
        .include "koti_glue.asm"
        #NAYTTO_OUT TIM_SCENE_KOTI_END
          .endif
          .if NAYTTO_GREETSIT
        #NAYTTO_IN TIM_SCENE_GREETSIT_START
        .include "greetsit_glue.asm"
        #NAYTTO_OUT TIM_SCENE_GREETSIT_END
          .endif
          .if NAYTTO_LOPPU
        #NAYTTO_IN TIM_SCENE_LOPPU_START
        #LOPPU_STEPS
        #S_CALL blank_res
          .endif
        #S_CALL part_end
        .endif
        .if PART == 99                  ; yleinen osalevy (runko.mk: make part P=nimi, src/scene/<nimi>_glue.asm, jossa
        .include PART_GLUE              ; SCENE_START ja SCENE_END ovat kohtauksen kehykset)
        #SCENE_OUT SCENE_END
        .endif
        .if PART == 5 || (PART == 0 && HAVE_ALKU && ALKU_ON)   ; alku: src/scene/alku_glue.asm
          .if PART == 0
        #S_LOAD f_crane2                ; Hillnerin $c400-: alku ei käytä sitä
          .endif
        .include "alku_glue.asm"
        #SCENE_OUT TIM_SCENE_ALKU_END
          .if PART == 0
        #S_FREE f_alku2                 ; ALKU2:n loppu $fb00- (alku_glue vapautti ALKU1:n ja $f600-$faff): alun IRQ
          .endif                        ; on siellä, kunnes Hillnerin S_START (hil_go) ottaa VIC:n ja IRQ:n
        .endif
        .if PART < 2                    ; Hillner: kamera-ajo -> ajo-kyltti -> lähikuva -> purku (purku jää IRQ:hunsa)
        .include "hil_glue.asm"
        #SCENE_OUT HIL_END              ; koko demossa purku pimenee itse HIL_END:ssä, sitten greetsit (SCENE_IN)
        .endif

        ; koko demo järjestyksessä Hillner -> greetsit -> koti -> loppu. Greetsejä ei
        ; voi esiladata purun aikana eikä kotia greetsien aikana (muisti), joten niiden alku on aikajanalla
        ; latausajan (LEAD_*) verran edellisen lopun jälkeen; lopun palat esiladataan kodin aikana.
        .if PART == 4 || (PART == 0 && HAVE_GREETSIT && TIM_SCENE_GREETSIT_START)   ; greetsit: greetsit_glue.asm
        #SCENE_IN TIM_SCENE_GREETSIT_START, LEAD_GREETSIT
        .include "greetsit_glue.asm"
        #SCENE_OUT TIM_SCENE_GREETSIT_END
        .endif

        .if PART == 2 || (PART == 0 && HAVE_KOTI)   ; koti: src/scene/koti_glue.asm
        #SCENE_IN TIM_SCENE_KOTI_START, LEAD_KOTI
        .include "koti_glue.asm"
        #SCENE_OUT TIM_SCENE_KOTI_END
          .if PART == 0                 ; lopun palat kodin aikana: kodin taulu päättyy koti_quietiin ($6000-$7fff ja
        #SCENE_PRE                      ; $8000-$bfff vapaat)
        #S_LOAD f_loppu2
            .if f_loppu1.lo >= $8000 && f_loppu1.hi <= $c000   ; lopun muistikartta, jossa LOPPU1 on $8000-$bfff:ssä
        #S_LOAD f_loppu1                ; (runko); muuten se latautuu kodin jälkeen
            .endif
          .endif
        .endif

        .if PART == 0 || PART == 3      ; loppu (runko): lopputekstit auringonlaskussa, src/runko/loppu.asm
        #SCENE_IN TIM_SCENE_LOPPU_START, LEAD_LOPPU   ; kodin perään (palat esiladattu kodin aikana; integraatiossa
                                        ; jatkuva siirtymä, kokoa.py)
        #LOPPU_STEPS
        #S_CALL part_end                ; pimeys ja musiikin häivytys (myös koko demon loppu)
        .endif
        .if PART != 97
        #S_CALL forever                 ; viimeisen kohtauksen IRQ jatkaa
        .endif
s_end
        .cerror s_end - s_tab > 256, "kohtaustaulu yli 256 tavua"
        .cerror !S_G.CLOCKED, "kohtaustaulussa ei ole S_STARTia (kello ei ala)"

forever jsr R_IDLE
        jmp forever

        .if PART == 98
skip_to                                 ; X/Y = kehys: kello ja musiikki hiljaa eteenpäin sinne (näyttölevy, kuva musta),
        stx sk_t                        ; jos kello on vielä ennen sitä. Soitin I/O:n alla ($01 = $34) kuten music_seek,
        sty sk_t+1                      ; lopuksi viimeiset SID-arvot SID:iin ja RAM $d400- takaisin
        php
        sei
        lda #$34
        sta $01
        ldx #24
-       lda $d400,x
        sta sk_ram,x
        dex
        bpl -
_l      lda DFRAME
        cmp sk_t
        lda DFRAME+1
        sbc sk_t+1
        bcs _d
        jsr MUSIC_PLAY
        inc DFRAME
        bne _l
        inc DFRAME+1
        bne _l
_d      ldx #24
-       lda $d400,x
        sta sk_sid,x
        lda sk_ram,x
        sta $d400,x
        dex
        bpl -
        lda #$35
        sta $01
        ldx #24
-       lda sk_sid,x
        sta $d400,x
        dex
        bpl -
        plp
        rts
sk_t    .word 0
sk_ram  .fill 25
sk_sid  .fill 25
        .endif

part_end                                ; demon ja osavaljaan loppu: kuva pimeäksi, musiikki hiljenee 2 s, sitten hiljaa
        sei                             ; $0b kesken kuvan näyttäisi loppukehyksen tekstitilana (DEN luetaan vasta rivillä
        bit $d011                       ; $30): heti vain reunuksessa (rasteri 251-311 tai alle $30), muuten rungon IRQ:ssa
        bmi _now                        ; (fade rivin 250 jälkeen, samassa kehyksessä)
        lda $d012
        cmp #251
        bcs _now
        cmp #$30
        bcs +
_now    jsr blank
+       jsr R_IRQ_ON
        #TICK fade
        cli
        jmp forever
fade    jsr blank                       ; R_TICK soittimen jälkeen (kuvan alla)
        lda fade_n                      ; äänenvoimakkuus 15 -> 0 (soitin kirjoittaa $d418:n joka kehys)
        beq +
        dec fade_n
+       lsr a
        lsr a
        lsr a
        sta $d418
        rts
fade_n  .byte 15 * 8
blank   lda #$0b
        sta $d011
        lda #0
        sta $d015
        rts
