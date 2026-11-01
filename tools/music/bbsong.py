"""Blackbird-laulutiedoston (bb.*, latausosoite $61E0) rakenne ja ajoitus.

Tiedostomuoto Birdcruncher 1.2:n lähteestä (cruncher.c, loadfile/build_voice):
otsake $61DE-$68FF (metatiedot, soittimet, taulut), sen jälkeen laulurivit
(3 x [tt, raita]) ja raidat lopusta alkaen (pituus viimeisenä, rivit takaperin
ins, fx, nuotti). tt 04-3F = tempo (alanibble kehyksiä per rivi, ylänibble
swing: lisäkehykset joka toiselle riville), 40-C0 = transponointi.

Käyttö: python3 -I tools/music/bbsong.py SONG.prg [--json OUT.json]
Tiedosto on dataa: sitä vain luetaan, mitään ei suoriteta.
"""

FILEORG = 0x61E0 - 2
HDR_END = 0x6900
NTRACK = 256


def petscii(raw):
    out = []
    for c in raw:
        if c == 0:
            break
        if 0x41 <= c <= 0x5A:
            out.append(chr(c + 0x20))
        elif 0x61 <= c <= 0x7A:
            out.append(chr(c - 0x20))
        elif 0xC1 <= c <= 0xDA:
            out.append(chr(c - 0x80))
        else:
            out.append(chr(c))
    return "".join(out)


def parse(data):
    if data[:6] != bytes([0xE0, 0x61, 0x62, 0x62, 0x30, 0x30]):
        raise SystemExit("ei Blackbird-tiedosto (otsake ei ole $61E0 'bb00')")
    hdr = data[: HDR_END - FILEORG]
    end = data[6] | (data[7] << 8)
    more = data[HDR_END - FILEORG : HDR_END - FILEORG + end - HDR_END]
    at = lambda a: hdr[a - FILEORG]
    songlen = at(0x61E6) + 1
    loopflag, loop = at(0x61E7), at(0x61E8)
    meta = [petscii(hdr[0x61F0 - FILEORG + 32 * i : 0x61F0 - FILEORG + 32 * i + 32]) for i in range(3)]

    tracks = [None] * NTRACK
    pos = len(more)
    for t in range(NTRACK - 1, -1, -1):
        pos -= 1
        n = more[pos]
        rows = [None] * n
        for r in range(n - 1, -1, -1):
            note, fx, ins = more[pos - 1], more[pos - 2], more[pos - 3]
            pos -= 3
            rows[r] = (ins, fx, note)
        tracks[t] = rows

    song = []
    for i in range(songlen):
        refs = [(more[i * 6 + 2 * j], more[i * 6 + 2 * j + 1]) for j in range(3)]
        lens = [len(tracks[r]) for _, r in refs if len(tracks[r])]
        song.append({"refs": refs, "rows": min(lens) if lens else len(tracks[0])})
    return {"title": meta[0], "author": meta[1], "released": meta[2],
            "songlen": songlen, "loop": loop if loopflag else None,
            "tracks": tracks, "song": song}


def timing(p):
    """Laulurivien alkukehykset. Swing: rivi 0, 2, 4 ... saa lisäkehykset (globaali rivilaskuri)."""
    tempo = 0x06
    frame = 0
    row = 0
    out = []
    for i, line in enumerate(p["song"]):
        for tt, _ in line["refs"]:
            if 0 < tt < 0x40 and (tt & 0x0F) >= 4:
                tempo = tt
        base, swing = tempo & 0x0F, (tempo >> 4) & 3
        start = frame
        for _ in range(line["rows"]):
            frame += base + (swing if row % 2 == 0 else 0)
            row += 1
        notes = [sum(1 for _, _, note in p["tracks"][r][: line["rows"]] if note != 0xFF)
                 for _, r in line["refs"]]
        out.append({"line": i, "start": start, "frames": frame - start, "rows": line["rows"],
                    "tempo": "%02x" % tempo, "refs": ["%02x%02x" % rf for rf in line["refs"]],
                    "events": notes})
    return out, frame
