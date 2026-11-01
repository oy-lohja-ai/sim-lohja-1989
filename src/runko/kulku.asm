; Integraatio (link.asm PART 97, tools/disk/kokoa.py): koko demo osalevyjen
; kohtaustauluista. Taulu ei mahdu residenttiin kokonaan, joten se on levyllä kohtaus kerrallaan (KUA, KUB,
; ..., kukin KU_WIN tavua nimineen) ja ladataan ikkunaan s_tab..s_end edellisen kohtauksen jälkeen; ensimmäinen kohtaus on
; ikkunassa valmiina. Jokainen kohtaus näkee omat kehyksensä kuten osalevyllään: kello (DFRAME) asetetaan kohtauksen
; alussa sen omaan alkukehykseen, ja musiikki soi yhtenä jatkuvana biisinä. Kohtaus alkaa iskulle samassa
; vaiheessa kuin osalevyllä (biisin kehys TIM_SONG_START + alku mod KU_BEAT).

ku_m    = $d9                           ; väliaikaiset (vain ku_startin ja ku_cutin aikana) runkon nollasivulla $d9-$de
ku_d    = $db
ku_f    = $dd
ku_tp   = $de
ku_s    = ZT                            ; kohtauksen alkukehys ku_startin ajan (runkon väliaikainen)
ku_lag  = $df                           ; ku_start: S_SHOW-rutiinin kesto kehyksinä (aloitus niin monta aiemmin)
KU_FAR  = 90                            ; I_SONGAT: kauempana olevaa T:tä ei odoteta (ku_start)
KU_WIN  = 256                           ; ikkunan koko (run_i on tavu; pienempi tiedosto olisi yksi lohko)
        .weak
KU_BEAT = MUSIC_BEAT_FRAMES             ; alun tahdistus: isku (kokoa.py --tahdistus)
        .endweak

        .for KU_MODN := 1, KU_BEAT << KU_MODN <= $ffff, KU_MODN += 1   ; ku_mod: suurin k, jolla KU_BEAT << k mahtuu
        .next
I_START .segment frame                  ; kohtauksen näkyvä alku integraatiossa (kokoa.py vaihtaa S_STARTin tähän)
        #S_STEP s_istart, \frame
        .endsegment
I_SHOW  .segment addr                   ; kohtauksen ensimmäinen kuva (S_SHOW) kutsutaan I_STARTin edellä
        #S_STEP s_ishow, \addr
        .endsegment
I_SONG  .segment off                    ; biisin kehys = DFRAME + off (kerneliosa soitti biisin itse, spritet)
        #S_STEP s_isong, \off
        .endsegment
I_SONGAT .segment t                     ; seuraava I_START tasan biisin kehykseen t (spritet: SID-virta alkaa siitä)
        #S_STEP s_isongat, \t
        .endsegment
I_SEAM  .segment frame                  ; jatkuva siirtymä: kohtaus alkaa edellisen viimeisen kehyksen jälkeen (kokoa.py)
        #S_STEP s_iseam, \frame
        .endsegment
I_CHUNK .segment n                      ; seuraavan kohtauksen taulu KU<n> ikkunaan (viimeinen askel), n = "A"...;
        #S_STEP s_chunk, \n               ; n | sivu << 8: taulu esiladattiin sivulle edellisen aikana (kokoa.py)
        .endsegment

ku_chunk                                ; X = taulun kirjain: KU<X> ikkunaan ja ajo alusta (nimi on residentissä,
        stx ku_name + 2                 ; joten R_LOADRAW:n uusi yritys virheestä lukee saman nimen). Y = 0: levyltä,
        tya                             ; muuten Y = sivu, jolle taulu esiladattiin: kopio (ei tiedoston avausta,
        bne _copy                       ; joka veisi 4-14 kehystä mustassa)
        ldx #<ku_name
        ldy #>ku_name
        jsr R_LOADRAW
_run    lda #0
        sta run_i
        rts
_copy   sta _s+2
        ldx #0
_s      lda $ff00,x
        sta s_tab,x
        inx
        bne _s
        beq _run

ku_cut                                  ; kohtauksen viimeisen kehyksen jälkeen (taulu: S_WAIT loppu - 2): kuva pimeäksi
        lda DFRAME                      ; seuraavassa reunuksessa (kesken kuvan $0b näyttäisi alaosan tekstitilana),
-       cmp DFRAME                      ; rungon IRQ, kohtauksen CIA- ja NMI-keskeytykset pois. Ensin kohtauksen viimeinen
        beq -                           ; soittimen kutsu (loppu - 1); ku_cut2: kerneliosa palasi juuri (ei IRQ:ta,
        bne ku_cut3                     ; ajastin nollasta: kerneli soitti viimeisen kehyksensä juuri)
ku_cut2 jsr ku_tclr
ku_cut3 sei                             ; Rungon riville 250 tultaessa ku_catch kutsuu soitinta niin monta kertaa kuin
                                        ; edellisestä kutsusta kului kehyksiä (FRAME_HOOK nollaa CIA1 A:n, ku_fh), joten
                                        ; kohtauksen kutsurivistä riippumatta mikään kutsu ei jää väliin eikä tuplaannu.
                                        ; Odotus keskeytykset pois (kohtauksen IRQ voi viedä reunuksen).
-       bit $d011
        bmi +
        lda $d012
        cmp #251
        bcs +
        cmp #$30
        bcs -
+       jsr blank
        jsr ku_catch
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d                       ; (NMI on reunaliipaistu: CIA2:n kuittaus kuuluu seuraavalle)
        lda #<nmi_rti
        sta $fffa
        lda #>nmi_rti
        sta $fffb
        jsr R_IRQ_ON
        #TICK 0
        cli
        rts

ku_seam                                 ; I_SEAM: X/Y = kohtauksen alkukehys S, jatkuva siirtymä (taulu: S_WAIT edellisen
        stx ku_s                        ; loppu - 2): edellisen kohtauksen viimeisen kehyksen kutsun jälkeen kello S:ään
        sty ku_s+1                      ; rivillä 250 kuten ku_start, ilman pimennystä, iskun odotusta ja S_SHOW:ta
        lda DFRAME                      ; (edellinen kutsuu soitinta omalla rivillään: kutsut ku_catchilla)
-       cmp DFRAME
        beq -
        sei
        bit $d011                       ; edellisen kutsu rivin 250 jälkeen (reunuksessa): kello heti, ei odotusta
        bmi +                           ; seuraavalle riville 250 keskeytykset pois (koti: koko kehys ilman
        lda $d012                       ; kodin IRQ:ta, kehys 14705 musta); kutsu tuli juuri, joten ku_catch ei
        cmp #RES_IRQ_LINE               ; kutsuisi
        bcs +
        jsr ku_catch                    ; (biisi pysyy vaiheessa: ku_fh ottaa kohtausten väliin jääneet kutsut kiinni)
+
        sec                             ; DFRAME - M_WAIT (S_WAIT E - 2, E = edellisen loppu): 2 = ku_catch kutsui
        lda DFRAME                      ; edellisen viimeisen kutsun, 1 = ei kutsunut (edellisen kutsu alle puoli kehystä
        sbc M_WAIT                      ; sitten, kodin kutsu kesken kuvan): kello S - 1, jolloin seuraava kutsu
        tax                             ; (kohtauksen oma) tuo S:n ja biisi ja kello pysyvät samassa vaiheessa kuin
        lda DFRAME+1                    ; osalevyillä (kello aina S:ään veisi lopun kehyksen iskua edelle). Yli 2
        sbc M_WAIT+1                    ; (seuraavan lataus jatkui edellisen lopun yli): pimennys ja iskun
        bne _late                       ; vaiheeseen kuten leikkauksessa (heti aloitettuna greetsit alkaisi 10 kehystä
        cpx #3                          ; iskun jälkeen; edellisen IRQ:n kanssa ku_start osuisi kehyksen iskua edellä)
        bcs _late
        cpx #2
        bcs +
        lda ku_s
        bne _d
        dec ku_s+1
_d      dec ku_s
+       jmp ku_set
_late   jsr ku_cut3
        ldx ku_s
        ldy ku_s+1
        jmp ku_start

        .section ku_hi                  ; payload kopioi tämän musiikin perään (runkon alue MUSIC_END-MUSIC_BUF)
ku_start                                ; X/Y = kohtauksen alkukehys S. Odottaa iskun vaiheeseen (biisin kehys
        stx ku_s                        ; TIM_SONG_START + S mod KU_BEAT), kutsuu ensimmäisen kuvan rutiinin
        sty ku_s+1                      ; rivin 250 jälkeen ja palaa seuraavalla rivillä 250 kuten osalevyn clock0:
        txa                             ; DFRAME = S, I = 1, rasteri-IRQ pois
        clc
        adc #<TIM_SONG_START
        tax
        tya
        adc #>TIM_SONG_START
        tay
        jsr ku_mod
        sta ku_tp
        lda #0
        sta ku_lag
_lp     lda DFRAME                      ; biisin kehys 2 + ku_lag rivin 250 päästä: DFRAME + 2 + ku_lag + ku_song
        sta ku_f
        sec
        adc ku_song                     ; C = 1: +1
        tax
        lda DFRAME+1
        adc ku_song+1
        tay
        txa
        sec                             ; C = 1: +1
        adc ku_lag
        tax
        bcc +
        iny
+       lda ku_at+1                     ; I_SONGAT: iskun vaihe aikaisintaan biisin kehyksessä ku_at (spritet:
        beq _ph                         ; kernelin SID-virta alkaa siitä; ohi: iskun vaihe kuten muulloin, musiikki
        txa                             ; hyppää kernelissä)
        sec
        sbc ku_at
        sta ku_d
        tya
        sbc ku_at+1
        bcs _ph
        cmp #$ff                        ; yli KU_FAR kehystä edellä: T on vanhentunut (edeltävät kohtaukset lyhenivät
        bne _far                        ; mittauksen jälkeen; muuten odotus voisi olla esim. 1000 kehystä, jolloin
        lda ku_d                        ; latausväli (greetsien ilta) loppuisi ja demo pysähtyisi): iskun vaihe heti
        cmp #256 - KU_FAR
        bcs _wait
_far    lda #0
        sta ku_at+1
        beq _ph
_wait   lda #1                          ; Z = 0: odota
        bne _z
_ph     jsr ku_mod
        cmp ku_tp
_z      php
-       jsr R_IDLE                      ; seuraava rivi 250 (rungon IRQ kasvattaa DFRAMEn)
        lda DFRAME
        cmp ku_f
        beq -
        plp
        bne _lp
        lda ku_show+1                   ; nyt reunuksessa: kohtauksen ensimmäinen kuva näkyy seuraavassa kehyksessä
        beq +
        jsr ku_dshow                    ; kesto: kello on nyt DFRAME, tavoite ku_f + 1 + ku_lag
-       lda ku_f
        sec
        adc ku_lag                      ; ku_f + 1 + ku_lag
        sec
        sbc DFRAME
        beq +                           ; ajallaan
        bpl -                           ; etuajassa: kuva näkyy, odotetaan (enintään ku_lag kehystä)
        eor #$ff                        ; myöhässä (kuvan asetus kesti): ku_lag kasvaa ja vaihe haetaan uudelleen
        sec
        adc ku_lag
        sta ku_lag
        jmp _lp
+
ku_tick sei                             ; seuraavalla rivillä 250 tämän kehyksen soittimen kutsu pääsäikeessä (rungon
        jsr ku_catch                    ; IRQ ei pääse väliin)
ku_set
        clc                             ; ku_song = DFRAME + ku_song - S
        lda DFRAME
        adc ku_song
        tax
        lda DFRAME+1
        adc ku_song+1
        tay
        txa
        sec
        sbc ku_s
        sta ku_song
        tya
        sbc ku_s+1
        sta ku_song+1
        lda ku_s
        sta DFRAME
        lda ku_s+1
        sta DFRAME+1
        lda #0
        sta $d01a
        sta ku_show+1
        sta ku_at+1
        lda #$ff
        sta $d019
        inc ku_first                    ; kohtauksen ensimmäinen soittimen kutsu tulossa (ku_fh)
        rts                             ; R_TICK on jo tyhjä (ku_cut)
ku_dshow jmp (ku_show)
ku_more jsr MUSIC_PLAY                  ; ku_fh: hukattu kutsu kiinni, kello mukana (biisi ja kuva samassa vaiheessa;
        inc DFRAME                      ; kuva hyppää kehyksen kohtauksen alussa, muuten se ja biisi seisoisivat)
        bne +
        inc DFRAME+1
+       rts


        .send ku_hi

ku_fh   lsr ku_first                    ; FRAME_HOOKin loppu integraatiossa. Kohtauksen ensimmäinen kutsu (ku_set): jos
        bcc _clk                        ; edellisestä kutsusta on yli puolitoista kehystä (ajastin alle $ffff - 29 484;
        lda $dc05                       ; kohtauksen IRQ alkoi myöhässä tai x_init piti keskeytykset pois), soitin ja
        cmp #>($ffff - FRAME_CYCLES * 3 / 2) + 1   ; kello vielä kerran, jotta biisi ei nyki (muuten kehyksen hyppy).
        bcs _clk                        ; Vain ensimmäinen kutsu (ku_set, ku_catch, rungon IRQ): kohtauksen
                                        ; sisällä kutsurivi vaihtelee (hillner), mikä ei ole hukattu kutsu.
        jsr ku_more
_clk    inc DFRAME                      ; kello ja CIA1:n ajastin A $ffff:stä, joten ajastin kertoo ajan edellisestä
        bne ku_tclr                     ; soittimen kutsusta (ku_catch; osa voi muuttaa latchia, mutta uudelleenlatauksen
        inc DFRAME+1                    ; jälkeen ensimmäinen jakso on aina $ffff)
ku_tclr lda #$ff                        ; Idle-mittari näkee kutsun kohdalla yhden virheellisen välin.
        sta $dc04
        sta $dc05
        lda #$11
        sta $dc0e
        rts
FRAME_CYCLES = 63 * 312

ku_catch                                ; seuraavalle riville 250 (rivin 249 kautta) ja soittimen kutsut edellisestä
-       lda $d012                       ; kutsusta (ku_fh): kulunut = $ffff - ajastin, kutsuja kehyksiä pyöristettynä
        cmp #RES_IRQ_LINE - 1           ; (ylätavu: puoli kehystä 9 828 = $26.., puolitoista 29 484 = $73..)
        bne -
-       lda $d012
        cmp #RES_IRQ_LINE
        bne -
        jsr ku_cia                      ; kulunut edellisestä kutsusta = $ffff - ajastin (ku_fh nollaa), ylätavu:
        tya                             ; puoli kehystä $26.., puolitoista $73..
        eor #$ff
        cmp #>(FRAME_CYCLES / 2)
        bcc +
        inc ku_first                    ; yli puolitoista kehystä: ku_fh soittaa toisen kutsun
        jsr FRAME_HOOK
+       rts

ku_cia  ldy $dc05                       ; CIA1:n ajastin A (idle-mittarin vapaasti juokseva) -> A ala, Y ylä
        lda $dc04
        cpy $dc05
        beq +
        ldy $dc05
        lda $dc04
+       rts

ku_mod                                  ; X/Y mod KU_BEAT -> A: vähennetään KU_BEAT << k, k = KU_MODN - 1 .. 0
        stx ku_m
        sty ku_m+1
        lda #<(KU_BEAT << (KU_MODN - 1))
        sta ku_d
        lda #>(KU_BEAT << (KU_MODN - 1))
        sta ku_d+1
        ldx #KU_MODN
-       lda ku_m
        sec
        sbc ku_d
        tay
        lda ku_m+1
        sbc ku_d+1
        bcc +
        sta ku_m+1
        sty ku_m
+       lsr ku_d+1
        ror ku_d
        dex
        bne -
        lda ku_m
        rts


ku_song .word TIM_SONG_START            ; biisin kehys - DFRAME (payload: biisi kehyksestä TIM_SONG_START + START)
ku_show .word 0
ku_at   .word 0                         ; I_SONGAT: biisin kehys kohtauksen alussa (0 = vain iskun vaihe)
ku_first .byte 0                        ; ku_set: kohtauksen ensimmäinen soittimen kutsu tulossa (ku_fh)
ku_name .text "ku?", 0                ; -a: pienet kirjaimet ovat PETSCII:n isoja
