#!/bin/sh
# Fetches and builds the third-party parts that are not in this repository, pinned to the exact versions used for
# the Zooparty 2026 release (RC10), and checks every file against its SHA-256:
#
#   Krill's loader, repository version 194 (csdb.dk release 226124): built from source with ca65/ld65 (cc65)
#     -> tools/krill/install-c64.prg, tools/krill/loader-c64.prg, tools/krill/krill.inc
#   Blackbird 1.2 by lft (linusakesson.net): Birdcruncher built from source with cc, then the music player is made
#     for both songs in music/ -> third_party/blackbird/player/<song>/
#   Caveat and Cinzel fonts (SIL Open Font License 1.1, github.com/google/fonts)
#     -> tools/gfx/data/koti/Caveat.ttf, tools/gfx/data/taulu/Cinzel.ttf
#
# Downloads go to third_party/downloads/. Nothing downloaded is executed except Birdcruncher, which is compiled from
# its C source in the Blackbird zip. Run from anywhere: tools/fetch-third-party.sh
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DL="$ROOT/third_party/downloads"
mkdir -p "$DL"

sha256() {
    if command -v sha256sum > /dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

# fetch URL FILE SHA256: download unless already present, then verify
fetch() {
    if [ ! -f "$2" ]; then
        echo "fetch: $1"
        curl -fsSL -o "$2.part" "$1"
        mv "$2.part" "$2"
    fi
    got=$(sha256 "$2")
    if [ "$got" != "$3" ]; then
        echo "error: $2: sha256 $got, expected $3" >&2
        exit 1
    fi
}

# check FILE SHA256: a built file must match the release build
check() {
    got=$(sha256 "$1")
    if [ "$got" != "$2" ]; then
        echo "error: $1: sha256 $got, expected $2 (different tool version?)" >&2
        exit 1
    fi
    echo "ok: ${1#"$ROOT"/}"
}

for tool in curl unzip cc ca65 ld65 python3; do
    command -v "$tool" > /dev/null 2>&1 || { echo "error: $tool not found (docs/building.md)" >&2; exit 1; }
done

# Krill's loader v194: tools/krill/koosta.py unpacks the zip into a temporary directory and calls ca65/ld65 directly
# (no Makefiles or scripts from the zip are run), with two small source patches (watchdog off, no 1541U warning).
fetch https://csdb.dk/getinternalfile.php/238373/loader-v194.zip "$DL/loader-v194.zip" \
    c273980bb81eb5b16e6163869cec147fc76e27bdba6d03e8a3438b8251aa00f1
python3 -I "$ROOT/tools/krill/koosta.py" "$ROOT/tools/krill" --resident 01fc --vahtikoira-pois --1541u-varoitus-pois > /dev/null
check "$ROOT/tools/krill/install-c64.prg" ddb2c5e945c95f4d59f5b5f7bde5e1190c7c8c12c8a64d1e52a518a8cab256c9
check "$ROOT/tools/krill/loader-c64.prg" ba7303c46fb0e7558de505bbbaba29754a9e5bf3ba362bddcb7e9596f9fb1145
check "$ROOT/tools/krill/krill.inc" b87ae8b0089cfb64616185f09bd5dfae9086164f6a4ec60b8415d9416e739297

# Blackbird 1.2: Birdcruncher from Export/source, then music.py crunch (relocatable player for each song)
fetch https://hd0.linusakesson.net/files/blackbird-1.2.zip "$DL/blackbird-1.2.zip" \
    26082c56d45c825d838aa682ad23747be475951fa1f1557f6729a54071e501c1
BB="$ROOT/third_party/blackbird"
rm -rf "$BB/src"
mkdir -p "$BB/src"
unzip -q "$DL/blackbird-1.2.zip" 'blackbird-1.2/Export/source/*' -d "$BB/src"
SRC="$BB/src/blackbird-1.2/Export/source"
cc -O3 -DVERSION='"1.2"' -o "$BB/birdcruncher" "$SRC/cruncher.c"     # as Export/source/Makefile
python3 -I "$ROOT/tools/music/music.py" crunch > /dev/null
python3 -I "$ROOT/tools/music/music.py" --laulu act0 crunch > /dev/null
check "$BB/player/bb.appeltrad7-demo-luuppi/base.bin" 9948173a1cc13e44f8afefb05652b314359cdaf67a73bc219d5b5d6e7ea83da0
check "$BB/player/bb.appeltrad13/base.bin" b13366d1348a1c448aac4311215719cb816aeb183f9abcb17e26ba3afe4c600e

# Fonts (google/fonts, pinned commits)
GF=https://raw.githubusercontent.com/google/fonts
fetch "$GF/a85fc09e44c70c7159761adfdc9d5dd007792c15/ofl/caveat/Caveat%5Bwght%5D.ttf" "$DL/Caveat.ttf" \
    0bdb6b660482d31531b3945849fba5916b3ef8695da7024a9e6b9ee3c4157988
fetch "$GF/45071f07c63e863a539442ef3562b71ab1f147a6/ofl/cinzel/Cinzel%5Bwght%5D.ttf" "$DL/Cinzel.ttf" \
    f4d83d34d1f6c741193e4acf4b3dff9531e5a67b6aa65228d00a7db72a4e0f34
fetch "$GF/52c319f5d50c762f3d5730ccc78aeac8167abbb7/ofl/caveat/OFL.txt" "$DL/OFL-Caveat.txt" \
    1f9d81d094273d82f3898a1ee8b598a717d050ecbf5ff7bede105b704880157b
fetch "$GF/45071f07c63e863a539442ef3562b71ab1f147a6/ofl/cinzel/OFL.txt" "$DL/OFL-Cinzel.txt" \
    f2b3029aba64c378bf0963b62945eee15e564fe4330b934c8f2eb058282b5e83
cp "$DL/Caveat.ttf" "$DL/OFL-Caveat.txt" "$ROOT/tools/gfx/data/koti/"
cp "$DL/Cinzel.ttf" "$DL/OFL-Cinzel.txt" "$ROOT/tools/gfx/data/taulu/"
echo "ok: tools/gfx/data/koti/Caveat.ttf, tools/gfx/data/taulu/Cinzel.ttf (+ OFL license texts)"

echo "third-party parts ready, now: make"
