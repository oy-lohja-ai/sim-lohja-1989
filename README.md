# SIM LOHJA 1989

A Commodore 64 demo by **Oy Lohja AI**, released at the **Zooparty 2026 C64 demo competition** (31 October 2026).
PAL C64 and a 1541 drive, one disk with two sides.

Lohja, 1989. The mayor plays the newly released Sim Lohja and gets an idea: bulldoze the old wooden town and build
boxes. A C64 demo about the real Lohja, from Hillner's house to Lohjantähti and Sokeripala. All text on screen is in
Finnish.

- Production page: https://oylohja.ai/productions/sim-lohja-1989/
- Video: https://www.youtube.com/watch?v=TMfqbFdMmgM

This repository holds the group's own source code and data for the demo. Together with the third-party parts that
`tools/fetch-third-party.sh` downloads from their official sources, `make` rebuilds the released competition disk
images byte for byte (`make check`).

## Credits

- **dipe**: concept, direction, production
- **Patemathic**: music ("Äppelträd")
- **Claude Opus 5.5** (AI): code, tools, graphics

The demo builds on the work of others:

- Loader by Krill (Krill's Loader, repository version 194; fetched, not in this repository)
- Music player: Blackbird by lft (fetched, not in this repository)
- Fonts: Caveat (The Caveat Project Authors) and Cinzel (The Cinzel Project Authors), SIL Open Font License 1.1
  (fetched, not in this repository)
- Packing: ZX0 format by Einar Saukas, dali variant by Bitbreaker (the packer and depacker in this repository were
  written for the demo)
- Map data: the maps follow the real geometry of Lohja. The game maps and some pictures were drawn from
  OpenStreetMap data (© OpenStreetMap contributors, ODbL) and from the City of Lohja map service (old basic maps and
  building data, including National Land Survey of Finland topographic data)

## Running

Write `build/simlohja-a.d64` and `build/simlohja-b.d64` to the two sides of a disk (or use the released images),
then `LOAD"*",8,1` and `RUN` side A. When the screen says **KÄÄN TALRIIKKI NY** (Lohja dialect for "turn the disk
now"), flip to side B. The demo continues by itself; no key presses are needed.

In VICE, `make run` starts side A with a fliplist; press Alt+N to flip to side B.

## Building

Requirements (versions used for the release build in parentheses):

- GNU make (3.81) and the usual POSIX tools (sh, sed, awk, grep, cmp, shasum or sha256sum)
- [64tass](https://sourceforge.net/projects/tass64/) (1.60.3243)
- Python 3.10 or newer (3.14.6) and [uv](https://docs.astral.sh/uv/) (0.11.16). uv installs Python 3.12 and the exact
  packages from `tools/concept/uv.lock` (numpy, Pillow, SciPy, scikit-image, PyYAML); every Python step of `make` runs
  there. The system `python3` is only used by `tools/fetch-third-party.sh`.
- [VICE](https://vice-emu.sourceforge.io/) x64sc (3.10): needed for building too, because the sprite record scene
  captures its SID register stream by running the music player in VICE
- [cc65](https://cc65.github.io/) (ca65 V2.18), a C compiler, curl and unzip: only for `tools/fetch-third-party.sh`

```sh
tools/fetch-third-party.sh   # Krill's loader, Blackbird's Birdcruncher, fonts (pinned, SHA-256 checked)
make                         # build/simlohja-a.d64 and build/simlohja-b.d64, about a minute
make check                   # compare with the released images (rc10.sha256)
```

The build has been verified on macOS (Apple Silicon). Details, including how the disk layout is made reproducible:
[docs/building.md](docs/building.md).

## Directory structure

| Path | Contents |
| --- | --- |
| `Makefile` | build entry point: `make`, `make check`, `make run`, `make clean` |
| `rc10.sha256` | SHA-256 of the released disk images (competition version RC10) |
| `tekstit.yaml` | every text shown on screen |
| `music/` | Patemathic's songs in Blackbird 1.2 format and a measurement of the player (`*.mut.json`) |
| `src/runko/` | demo framework: boot, resident code, loader calls, link script, disk flip, transitions, MS-DOS intro, end credits, part disks |
| `src/scene/` | scene tables: what each part loads and when it starts, waits and hands over |
| `src/proto/<scene>/` | the scenes: 6510 code and the Python generators of their data |
| `src/lib/`, `src/purku/`, `src/music/` | shared 6510 modules, the demolition engine, the music player interface |
| `src/gen/timing.inc` | scene timing symbols (the same timeline as `timing/timeline.c64.json`) |
| `timing/` | timeline, beat grid and `integraatio/`: the measured state that fixes the disk layout of the release build |
| `tools/disk/` | disk tools: D64 writer, ZX0 packer, the integration that assembles both disk sides (`kokoa.py`) |
| `tools/gfx/` | graphics converters and `data/`, the demo's graphics in C64 form |
| `tools/concept/` | Python drawing and C64 conversion library used by the generators (uv project) |
| `tools/music/` | Blackbird song parser and player relocator (`music.py`) |
| `tools/krill/koosta.py` | builds Krill's loader from its source |
| `tools/fetch-third-party.sh` | fetches and builds the third-party parts |

Code comments and identifiers are in Finnish.

## What is not included, and why

- **Third-party code**: Krill's loader and lft's Blackbird player and Birdcruncher are not redistributed here.
  `tools/fetch-third-party.sh` downloads Krill's loader from [CSDb](https://csdb.dk/release/?id=226124) and Blackbird
  1.2 from [linusakesson.net](https://linusakesson.net/software/blackbird/), builds them and checks the results
  against the release build.
- **Fonts**: Caveat and Cinzel are fetched from [google/fonts](https://github.com/google/fonts) at pinned commits.
- **Other groups' logos**: the original logo artwork belongs to the groups and is not included. The C64-resolution
  renderings that appear on the released disks are in `tools/gfx/data/ryhmalogot/`, so that the build still works.
- **Map data**: the OpenStreetMap and City of Lohja map data the game maps and pictures were drawn from are not
  included. The finished maps and pictures are included in C64 form.

## License

The source code is licensed under the MIT license: see [LICENSE](LICENSE), "Copyright (c) 2026 Oy Lohja AI".

These are **not** under the MIT license:

- **Music**: the songs in `music/` ("Äppelträd" by Patemathic, Blackbird song data). All rights reserved.
- **Graphics data**: `tools/gfx/data/` and `tools/gfx/logo/data/` (the demo's graphics in C64 form and the
  Oy Lohja AI emblem model). Copyright (c) 2026 Oy Lohja AI. All rights reserved.
- **Other people's marks**: the logos and names of other groups, the party and real organisations that appear in the
  demo belong to their owners. Some maps and pictures were drawn from OpenStreetMap data (© OpenStreetMap
  contributors, ODbL) and from the City of Lohja map service (see Credits).
- **Third-party parts**: Krill's loader, Blackbird and the fonts are not in this repository; they keep their own
  licenses.
