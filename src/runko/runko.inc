; Demon runko: pysyvät osoitteet ja osien rajapinta. Osat sisällyttävät tämän tiedoston.
;
; Pysyvä muisti koko demon ajan:
;   $c0-$cf musiikki, $d0-$df runko, $e0-$ef Krill (latauksen aikana: osan IRQ ei saa kirjoittaa näihin)
;   $0100-$01fb pino, $01fc-$0406 Krillin resident (tools/krill/koosta.py), $0408-$07ff runko, $0800-$19ff musiikki ja puskuri
; Osat: $02-$bf, $f0-$ff, $1a00-$cfff ja $e000-$fff9. $d000-$dfff RAM vain kopioimalla (Krill ei lataa sinne).
; VIC-pankki: $dd00:aan vain arvot 0-3 (Krillin sarjaväylä samassa portissa).

        .weak                   ; samat arvot src/scene/hil.inc:ssä
DFRAME  = $d0                   ; demon kehys (16 bittiä) clock0:sta, kasvaa kerran kehyksessä (frame_hook)
ZT      = $d2                   ; runkon väliaikaiset $d2-$d3 ($d4-$d8: hil_glue.asm, $d9-$df: kulku.asm integraatiossa)
        .endweak

RES_AT  = $0408                 ; frame_hook ja hyppytaulu (vakaa ABI, osat kutsuvat näitä osoitteita)
FRAME_HOOK = RES_AT + 0         ; jsr kerran kehyksessä osan omasta IRQ:sta: musiikki + DFRAME (A, X, Y muuttuvat)
R_LOADRAW  = RES_AT + 10        ; X/Y = nimi: lataa raakana; virheestä uusi yritys, lopulta reunus vilkkuu
R_LOADCOMPD = RES_AT + 13       ; X/Y = nimi: lataa ja purkaa lennossa (ZX0)
R_WAIT     = RES_AT + 16        ; X/Y = kehys: odottaa (tyhjäkäyntinä), kunnes DFRAME >= X/Y
R_IRQ_ON   = RES_AT + 19        ; runkon oma IRQ (rivi 250: frame_hook + R_TICK) päälle; kutsu sei:n kanssa tai ilman
R_TICK     = RES_AT + 22        ; jmp-vektori (oletuksena R_TICK_RTS): runkon IRQ kutsuu kerran kehyksessä frame_hookin jälkeen
R_TICK_VEC = R_TICK + 1
R_TICK_RTS = RES_AT + 25        ; rts (R_TICK:n oletus)
R_IDLE     = RES_AT + 26        ; yksi tyhjäkäyntikierros: osan pääsilmukan odotus kutsuu tätä (CPU-mittari)
; Muistipurku (ZX0, tools/disk/zx0.py) ei ole residentissä: osa sisällyttää src/runko/unzx0.asm:n (280 t) ja oman UZ:n.

; Mittarit pinosivun pohjalla:
M_BASE  = $0100
M_VER   = M_BASE + 0            ; muodon versio (2: M_IDLE sykleinä)
M_LINE  = M_BASE + 1            ; varattu (0): IRQ:n alkurivi muuttaisi frame_hookin ajoitusta
M_IDLE  = M_BASE + 2            ; 2 t: tyhjäkäyntisyklit edellisessä kehyksessä (CIA1 ajastin A)
M_IDLE_F = M_BASE + 4           ; DFRAME:n alatavu, jolle M_IDLE kuuluu
M_LOAD  = M_BASE + 5            ; 2 t: ladattavan nimen osoite, ylätavu 0 = ei latausta
M_WAIT  = M_BASE + 7            ; 2 t: viimeisimmän waitin tavoitekehys
idle_f  = M_BASE + 9            ; sisäiset: kuluva kehys, summa, edellinen ajastinluku, väli
idle_n  = M_BASE + 10
idle_t  = M_BASE + 12
idle_d  = M_BASE + 14
M_END   = M_BASE + 15
IDLE_GAP = 160                  ; idle-kutsujen väli, joka vielä lasketaan tyhjäkäynniksi (kutsujan silmukka < 100 sykliä)

RES_IRQ_LINE = 250

; Linkkiskriptin ja osien makrot. Tiedostot ovat build/runko/<levy>/files.inc:ssä (tools/disk/levy.py names):
; jokainen on lohko f_x, jossa name (nimi) ja packed (1 = ZX0).
LOAD    .macro f                ; lataa tiedoston levyltä (pakattu tai raaka levy.json:n mukaan)
        ldx #<\f.name
        ldy #>\f.name
        .if \f.packed
        jsr R_LOADCOMPD
        .else
        jsr R_LOADRAW
        .endif
        .endm

WAIT    .macro frame            ; odottaa demon kehykseen
        ldx #<(\frame)
        ldy #>(\frame)
        jsr R_WAIT
        .endm

TICK    .macro addr             ; runkon IRQ kutsuu addr:ia kerran kehyksessä (0 = pois)
        .if \addr
        lda #<\addr
        ldx #>\addr
        .else
        lda #<R_TICK_RTS
        ldx #>R_TICK_RTS
        .endif
        sta R_TICK_VEC
        stx R_TICK_VEC+1
        .endm

; Kohtaustaulu (src/runko/link.asm): demon kulku datana. Askel on 3 t: rutiinin alatavu
; (link.asm:n s_ops-sivulla) ja X/Y. Taulun ajaja kutsuu askeleet järjestyksessä pääsäikeessä eikä muuta I-lippua.
; Build seuraa ladattuja tiedostoja: S_LOAD pysähtyy, jos alue ei ole kohtausten muistia tai jos se osuu
; tiedostoon, jota ei ole vapautettu (S_FREE). Tiedostot f_x: build/runko/<levy>/files.inc (name, packed, lo, hi, txt).
; Kirjanpito on lohkossa S_G, jotta makrot päivittävät samaa muuttujaa myös kohtauksen omassa .blockissa
; (integraatio, tools/disk/kokoa.py: blokin sisällä `x := ...` tekisi paikallisen kopion).
S_G     .block
LIVE    := []                   ; ladatut ja käytössä olevat tiedostot (alku, loppu, nimi, kohtaus)
SCENE   := 0                    ; kohtauksen numero: S_NEXT kasvattaa (seuraavan kohtauksen esilataukset)
CLOCKED := 0                    ; 1, kun levyn ensimmäinen S_START on aloittanut kellon
        .endblock

S_STEP  .segment op, arg
        .byte <(\op)
        .word \arg
        .endsegment

S_LOAD  .segment f              ; lataa tiedoston (pakattu: purku lennossa; levy.py vie pienen raakana);
_pre    := 0                    ; jo ladattu eikä vapautettu (esilataus edellisen kohtauksen aikana): ei askelta
        .for _i := 0, _i < len(S_G.LIVE), _i += 1
_pre    := _pre || S_G.LIVE[_i][2] == \f.txt
        .next
        .if !_pre
        .cerror \f.lo < $1a00 || \f.hi > $fffa || (\f.lo < $e000 && \f.hi > $d000), "S_LOAD ", \f.txt, format(": $%04x-$%04x ei ole kohtausten muistia", \f.lo, \f.hi - 1)
        .for _i := 0, _i < len(S_G.LIVE), _i += 1
        .cerror S_G.LIVE[_i][0] < \f.hi && \f.lo < S_G.LIVE[_i][1], "S_LOAD ", \f.txt, format(" ($%04x-$%04x)", \f.lo, \f.hi - 1), " kirjoittaa tiedoston ", S_G.LIVE[_i][2], format(" ($%04x-$%04x)", S_G.LIVE[_i][0], S_G.LIVE[_i][1] - 1), " päälle: S_FREE puuttuu"
        .next
S_G.LIVE := S_G.LIVE .. [(\f.lo, \f.hi, \f.txt, S_G.SCENE)]
        #S_STEP \f.packed ? s_load : s_loadr, \f.name
        .endif
        .endsegment

S_HAVE  .segment f              ; ei tavuja: tiedosto on muistissa (siirretty esilataus kopioitu paikalleen, kokoa.py)
        .for _i := 0, _i < len(S_G.LIVE), _i += 1
        .cerror S_G.LIVE[_i][0] < \f.hi && \f.lo < S_G.LIVE[_i][1], "S_HAVE ", \f.txt, format(" ($%04x-$%04x)", \f.lo, \f.hi - 1), " kirjoittaa tiedoston ", S_G.LIVE[_i][2], format(" ($%04x-$%04x)", S_G.LIVE[_i][0], S_G.LIVE[_i][1] - 1), " päälle: S_FREE puuttuu"
        .next
S_G.LIVE := S_G.LIVE .. [(\f.lo, \f.hi, \f.txt, S_G.SCENE)]
        .endsegment

S_FREE  .segment f              ; ei tavuja: tiedoston muisti ei ole enää kenenkään käytössä
_live   := []
        .for _i := 0, _i < len(S_G.LIVE), _i += 1
        .if S_G.LIVE[_i][2] != \f.txt
_live   := _live .. [S_G.LIVE[_i]]
        .endif
        .next
        .cerror len(_live) == len(S_G.LIVE), "S_FREE ", \f.txt, ": ei ladattu"
S_G.LIVE := _live
        .endsegment

S_FREE_RANGE .segment f, lo, hi   ; ei tavuja: tiedoston alue lo..hi-1 vapaa, loppu käytössä (purun data osittain)
_live   := []
        .for _i := 0, _i < len(S_G.LIVE), _i += 1
        .if S_G.LIVE[_i][2] != \f.txt
_live   := _live .. [S_G.LIVE[_i]]
        .else
          .if S_G.LIVE[_i][0] < \lo
_live   := _live .. [(S_G.LIVE[_i][0], \lo, S_G.LIVE[_i][2], S_G.LIVE[_i][3])]
          .endif
          .if \hi < S_G.LIVE[_i][1]
_live   := _live .. [(\hi, S_G.LIVE[_i][1], S_G.LIVE[_i][2], S_G.LIVE[_i][3])]
          .endif
        .endif
        .next
S_G.LIVE := _live
        .endsegment

S_NEXT  .segment                ; ei tavuja: tästä eteenpäin ladatut kuuluvat seuraavaan kohtaukseen (esilataus)
S_G.SCENE := S_G.SCENE + 1
        .endsegment

S_FREE_ALL .segment             ; ei tavuja: aiempien kohtausten tiedostot vapaita (S_NEXTin jälkeen esiladatut jäävät,
_live   := []                   ; myös kahden kohtauksen päähän esiladatut, kokoa.py)
        .for _i := 0, _i < len(S_G.LIVE), _i += 1
        .if S_G.LIVE[_i][3] >= S_G.SCENE
_live   := _live .. [S_G.LIVE[_i]]
        .endif
        .next
S_G.LIVE := _live
        .endsegment

S_WAIT  .segment frame          ; odottaa, kunnes DFRAME >= kehys
        #S_STEP s_wait, \frame
        .endsegment

S_CALL  .segment addr           ; jsr kohtauksen sisääntuloon, paluu = seuraava askel
        #S_STEP s_call, \addr
        .endsegment

S_SHOW  .segment addr           ; ennen S_STARTia: levyn ensimmäinen kohtaus näyttää kuvansa ennen kelloa (osalevyn
        .if !S_G.CLOCKED      ; kehys 0 ei musta); addr asettaa kuvan ilman IRQ:ta eikä muuta kohtauksen tilaa
        #S_CALL \addr
        .endif
        .endsegment

S_START .segment frame          ; kohtauksen näkyvä alku: levyn ensimmäinen kohtaus aloittaa kellon (clock0)
        .if S_G.CLOCKED
        #S_WAIT \frame
        .else
        #S_CALL s_sync
S_G.CLOCKED := 1
        .endif
        .endsegment
