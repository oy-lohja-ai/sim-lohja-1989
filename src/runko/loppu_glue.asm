; Loppu (lopputekstit, runko, src/runko/loppu.asm) kohtaustaulussa: link.asm:n LOPPU_STEPS sisällyttää tämän
; SCENE_IN:in tai NAYTTO_IN:in jälkeen, ja integraatio (tools/disk/kokoa.py) käyttää tätä kohtauksen tauluna.
        #S_LOAD f_loppu1                ; $8000-$bfff: koodi, data ja välke (esiladattu kodin aikana)
        #S_LOAD f_loppu2                ; $6000-$7f3f: bittikartta
        #S_CALL loppu_init
        #S_SHOW loppu_show              ; osalevyllä kuva ennen kelloa: kehys 0 ei musta
        #S_START TIM_SCENE_LOPPU_START
        #S_CALL loppu_go                ; IRQ ja näkyvät rivit, sitten LOPPU3 ($e000-: logot ja rivit) kohtauksen aikana
        #S_LOAD f_loppu3
        #S_CALL loppu_run               ; palaa kohtauksen lopussa
