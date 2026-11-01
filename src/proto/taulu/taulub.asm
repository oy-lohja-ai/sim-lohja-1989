; Kerrontataulun bittikartta omana tiedostonaan VIC-pankissa 3 (PANKKI = 3, taulu.asm): $e000-$ff3f.
        .include "taulu_osa.inc"
        .weak
P3_BITTI = $e000                ; latausosoite (taulu.asm kopiotila: taulu_init kopioi $e000:aan)
        .endweak
        * = P3_BITTI
        .binary TAULU_BIN
