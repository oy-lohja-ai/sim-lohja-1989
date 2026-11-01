; Väriketjuhäivytys (siirtymät mustaan ja mustasta): jokainen C64-väri
; tummuu oman ketjunsa kautta mustaan (sama kuin tools/disk/loppu.py CHAINS, valoisuudet lähekkäin), joten häivytys ei
; harmaannu eikä hyppää sävystä toiseen. HV_N + 1 tasoa: taso 0 = musta, taso HV_N = alkuperäinen väri. Nousu mustasta
; = tasot 0 -> HV_N, häivytys = HV_N -> 0; kohtaus valitsee tahdin (esim. taso 2 kehyksen välein = 8 kehystä).
;
;   .include "../lib/haivytys.asm"      ; HV_N ennen includea muuttaa tasojen määrää (oletus 4)
;   lda taso / ldx #väri / jsr hv_vari  ; A = väri tasolla (X ja Y säilyvät, ei nollasivua)
;   lda hv_tab + taso * 16, x           ; sama vakiotasolle
;
; Värimuistin tai ruudun palalle (ruudun tavussa kaksi väriä) kohtaus tekee oman silmukkansa hv_tab:lla tai
; HV_TAB2-makron 256 tavun taululla (molemmat puolikkaat), koska kopio ja sen ajoitus ovat kohtauksen omia.

        .weak
HV_N    = 4
        .endweak

hv_ketju = [[0], [1, 15, 12, 11, 0], [2, 9, 0], [3, 14, 6, 0], [4, 6, 0], [5, 11, 0], [6, 0], [7, 10, 8, 2, 9, 0], [8, 2, 9, 0], [9, 0], [10, 8, 2, 9, 0], [11, 0], [12, 11, 0], [13, 5, 11, 0], [14, 6, 0], [15, 12, 11, 0]]
hv_vari_s .function c, s        ; väri c tasolla s: ketjun indeksi (HV_N - s) / HV_N pyöristettynä
        .endf hv_ketju[c][((HV_N - s) * (len(hv_ketju[c]) - 1) + HV_N / 2) / HV_N]

        .cerror HV_N < 1 || HV_N > 15, "haivytys: HV_N 1-15"
hv_tab                          ; taso * 16 + väri -> väri
        .for _s := 0, _s <= HV_N, _s += 1
          .for _c := 0, _c < 16, _c += 1
        .byte hv_vari_s(_c, _s)
          .next
        .next

hv_vari                         ; A = taso (0-HV_N), X = väri (ylänelikko ohitetaan) -> A = väri tasolla
        asl
        asl
        asl
        asl
        sta _o+1
        txa
        and #15
_o      ora #0
        sty _y+1
        tay
        lda hv_tab,y
_y      ldy #0
        rts

HV_TAB2 .macro taso              ; 256 tavua: ruudun tavu (kaksi väriä) -> molemmat tasolla
        .for _b := 0, _b < 256, _b += 1
        .byte hv_vari_s(_b >> 4, \taso) << 4 | hv_vari_s(_b & 15, \taso)
        .next
        .endm
