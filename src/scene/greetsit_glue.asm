; Greetsit (partti 4) kohtaustaulussa: src/runko/link.asm sisällyttää tämän taulun. Palat ja
; sisääntulot: src/proto/greetsit/split.py. Koko osa on $1b00-$22bf ja
; $4000-$bfff: koko demossa vuosi2026 jättää ne vapaiksi, joten runko esilataa palat sen aikana (S_LOAD jo ladatulle
; ei tee askelta), ja siirtymä on jatkuva (part-greetsit.json "jatkuva"): greetsit_init (ruudut, kaistat,
; skrolleri, noin 1 kehys) vuoden pyöriessä, greetsit_go kopioi värit, ottaa IRQ:n ja palaa.
        .include "../../build/greetsit/demo/syms.inc"
        #S_LOAD f_greetsit6             ; $4800-$64ff ladattuna $2300-$3fff:ään ja $6500-$7fff $e000-$faff:ään (merkistöt,
        #S_LOAD f_greetsit7             ; spritet, color_u): koko demossa sokeripalan taulun aikana, joka käyttää
        #S_LOAD f_greetsit5             ; $4000-$7fff loppuun asti (split.py); $8000-code_end: koodi, kerneli, taulut
        #S_LOAD f_greetsit3             ; $1b00-: kulkevan aallon koodi ja taulut
        #S_CALL greetsit_kopio          ; GREETSIT6 ja 7 paikalleen $4800-$7fff (noin 10 kehystä, mustassa)
        #S_FREE f_greetsit6             ; $2300-$3fff ja $e000-$fbff vapaiksi (kodin KOTI3 greetsitin aikana)
        #S_FREE f_greetsit7
        #S_CALL greetsit_init
        #S_START TIM_SCENE_GREETSIT_START
        #S_CALL greetsit_go
