; MS-DOS-käynnistys (src/runko/dos.asm): kiinteät osoitteet payloadille ja
; kokoa.py:n ensimmäisen kohtauksen taululle. Muisti: bittikartta $c000-$df3f, värit $e000-$e3e7, ohjelma DOS_AT-.
DOS_AT  = $e400
DOS_GO  = DOS_AT                ; X/Y = biisin kehys (kelaus DOS_ENDissä); IRQ päälle, palaa heti (sei:n kanssa)
DOS_END = DOS_AT + 3            ; odottaa käsikirjoituksen loppuun, pimentää, IRQ pois, kelaa biisin (keskeytykset pois)
DOS_PART = DOS_AT + 6           ; osalevy dos: koko DOS-ruutu kellon alusta (S_CALL), palaa pimeänä, DFRAME osan loppuun
