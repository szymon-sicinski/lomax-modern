# lomax-modern

Research and read-only tooling for **The Adventures of Lomax** (Psygnosis,
1996/97, Windows 95). Status: **research + read-only tooling + an engine-core
vertical slice + an integer-scaling presenter** — no game data in this
repository; the measured state of the retail install is in
[`docs/research/06-measurements-and-improvements.md`](docs/research/06-measurements-and-improvements.md).

The question this project starts from: *what can actually be improved in Lomax
today, and which of those improvements are still missing?* The headline answer
is in [`docs/research/02-resolution.md`](docs/research/02-resolution.md):

- **The game is Windows-only, Win32 + MFC 4.2 + DirectDraw 7**, with an
  optional Direct3D 3 path. It is not a DOS game, so DOSBox is the wrong tool.
- **The internal resolution is hard-coded at 320x240** (8 or 16 bpp, 256-colour
  palettes). Height is effectively locked; only width can grow, and the level
  data does not impose a 512 px ceiling: of the 104 planes, 16/104 are narrower
  than 432 px, 18/104 narrower than 512 px and 24/104 narrower than 640 px, so
  beyond 512 the binding constraint is the engine, not the data (measured in
  [`06-measurements-and-improvements.md`](docs/research/06-measurements-and-improvements.md)).
- **The widescreen/high-refresh/loader space is already occupied** by a
  closed-source (all rights reserved) project, `Lomax+`, which covers
  borderless fullscreen, up to 512x240 widescreen, 60+ FPS, controller and
  audio fixes. Competing feature-for-feature is not a good use of effort.
- **What is still open**: an open-source, Linux/Wine-usable presentation layer
  with pixel-art filters; a documented, distributable **asset pipeline** for
  the `.WLD` world files; and — as a spike, not a promise — higher-resolution
  internal rendering backed by upscaled art.

## What this repository is

- A citation-backed research report on the game's platform, file formats and
  improvement options.
- Read-only Python tooling that inspects **your own** copy of the game:
  `doctor` (install inventory), `wldscan` (chunk scanner for `.WLD` files),
  `measure` (install measurement: chunk sequence, per-section plane widths,
  audio formats), `export` (decode `CELL`/`TTAB`/`MAP` into PNG sheets),
  `wld roundtrip` (byte-exact round-trip proof) and `probe-anim-nmy` (structural
  probe for the `ANIM`/`NMY`/`GNMY` chunks: offsets and record hypotheses scored
  by coverage) and `anim-nmy` (decodes the recovered `ANIM`/`NMY` framings and
  reports per-world counts).
- A **reference engine core** (`lomax_modern.engine` + `lomax-modern slice`):
  a headless vertical slice that loads the first world, ticks at the original
  60 Hz, collides against the decoded `MAP`, and draws a 16-bit `B5G6R5` frame —
  with every unresolved format field flagged, not guessed.
- A **presenter** (`lomax-modern present`): reads a JSON config (written on
  first run), defaults to the modern profile — 16:9 surface, integer scaling,
  `epx-aa` filter — with `--authentic` as the native 320x240 / nearest-
  neighbour escape hatch, switches the filter at runtime, and refuses a folder
  that is not an unpacked retail install with a file-by-file manifest. It
  writes the presented surface as a PNG; the windowed presenter is future work.
  See the [runbook](docs/runbook.md).
- A **demo path** (`lomax-modern gif`): folds a directory of frame PNGs — one
  file per 60 Hz tick — into one looping animated GIF89a that a README or a
  chat window can play. Pure standard library (`src/lomax_modern/gif.py`): the
  colour table is chosen by measured size, `--fps` sets the delay and
  `--max-frames` samples evenly so a 300-tick capture does not become a 60 MB
  file.

## What this repository is not

- Not a game download, and it contains **no game assets**.
- Not a CD-check bypass, and it does not patch or redistribute `LOMAX.EXE`.
- Not a fork of `Lomax+` (that project has no licence; see
  [`docs/research/03-prior-art.md`](docs/research/03-prior-art.md)).

## Runbook: from your own copy to a running presenter

The engine takes **one path: an unpacked game directory** in the retail layout.
It ships no game data, reads only the files below from *your* folder, and writes
nothing into it.

```bash
git clone https://github.com/szymon-sicinski/lomax-modern.git && cd lomax-modern
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
lomax-modern present "/path/to/Lomax"            # modern defaults
lomax-modern present "/path/to/Lomax" --authentic  # native 320x240, nearest
```

**What you must supply** (the Q29 manifest — the full table with counts is in
[`docs/runbook.md`](docs/runbook.md#3-what-you-must-supply-the-data-manifest)):

| Entry | Required | Read by the engine? |
|---|---|---|
| `LOMAX.EXE` | yes — presence only | **never** (presence check only) |
| `WORLDS/` with ≥ 1 `*.WLD` | yes | **yes — the only game bytes the engine reads** |
| `SFX/` (67 WAVs) | expected | not yet (audio layer, M6) |
| `AMBIENT/` (12 loops) | expected | not yet (M6) |
| `JINGLES/` (3 stingers) | expected | not yet (M6) |
| `DEMOS/` (14 files) | expected | no |
| `GAME.TXT` | expected | no (`measure` inspects it as a diagnostic) |

"Expected" means the run reports it as an incomplete copy and continues;
"required" means the run refuses the path with a file-by-file manifest. Name case
is ignored, and a retail folder copied one level inside the named directory is
resolved automatically.

- **Modern defaults vs authentic toggle.** Modern (default) = 1920x1080 surface
  with `epx-aa` and the largest integer scale; `--authentic` = native 320x240
  with `nearest`. Flags override one axis for one run; `--save` persists them to
  the config file (`$XDG_CONFIG_HOME/lomax-modern/config.json`,
  `%APPDATA%\lomax-modern\config.json` on Windows, `$LOMAX_CONFIG` to override).
- **Controls: none in this build.** `present` runs the engine's scripted input
  for `--ticks` and has no window yet (the Win32 presenter is future,
  [`docs/architecture.md`](docs/architecture.md) §5); keyboard and gamepad are
  M5 (v0.7). The engine's actions are left, right and jump — no bindings are
  invented here.
- **There is no music track.** The PC build's soundtrack was CD audio and the
  installed data has none: a disc-less copy has ambience (`AMBIENT/`), jingles
  and SFX only. Nothing is bundled, downloaded or extracted, and this build's
  presenter is silent until the audio layer (M6) reads those WAVs.

Full runbook — config-file reference, example output, exit codes, the
missing-data paths and the platform/packaging status:
[`docs/runbook.md`](docs/runbook.md).

**The three-minute demo.** [`docs/demo.md`](docs/demo.md) is the alpha's whole
capability in seven commands with the output they really printed, and
[`examples/demo.sh`](examples/demo.sh) runs the same seven in order against
*your* copy — `bash examples/demo.sh "<install>"` — stopping at the first
failure and writing only to `./demo-out`.

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# Inventory your own installation (read-only, prints hashes and sizes only)
lomax-modern doctor "/path/to/Lomax"

# Walk the chunk chain of a world file
lomax-modern wldscan "/path/to/Lomax/WORLDS/MAIN.WLD"

# Prove the reader/writer round-trips every world file byte-for-byte (read-only)
LOMAX_GAME_DIR="/path/to/Lomax" python -m lomax_modern wld roundtrip --check

# Measure the install: chunk sequence, plane widths per section, audio formats
lomax-modern measure "/path/to/Lomax" --json /tmp/lomax-report.json

# Decode one world's CELL/TTAB/MAP into PNG sheets (read-only on the source)
lomax-modern export "/path/to/Lomax/WORLDS/VILLAGE.WLD" --out /tmp/art

# Run the headless vertical slice of the first world (no display, no LOMAX.EXE)
LOMAX_GAME_DIR="/path/to/Lomax" python -m lomax_modern slice --world VILLAGE --ticks 300

# Structural probe for ANIM/NMY/GNMY: offsets and record hypotheses scored by
# coverage (labels every framing a hypothesis; prints "unresolved" when none wins)
lomax-modern probe-anim-nmy "/path/to/Lomax"
# Present the engine frame at the largest integer scale (modern defaults; the
# config file is written on first run and can be saved from flags with --save)
lomax-modern present "/path/to/Lomax" --frame /tmp/lomax-frame.png

# Authentic toggle: native 320x240, nearest-neighbour, no invented smoothing
lomax-modern present "/path/to/Lomax" --authentic --frame /tmp/lomax-native.png

# Capture one presented PNG per 60 Hz tick: frame_0000.png ... (the naming
# `ffmpeg -i frame_%04d.png` expects); --out is created and must be outside
# the game folder
lomax-modern present "/path/to/Lomax" --authentic --surface 640x480 \
    --frames 300 --out /tmp/lomax-frames

# Switch the filter for one run; persist a choice with --save
lomax-modern present "/path/to/Lomax" --filter nearest --save

# Fold a directory of frame PNGs into one looping animated GIF (stdlib only;
# --fps sets the delay, --max-frames samples evenly)
lomax-modern gif /tmp/frames --out /tmp/demo.gif --fps 30
```

Run the tests with `python -m pytest tests -m "not realgame"`. The integration
tests are opt-in: `LOMAX_GAME_DIR=/path/to/Lomax python -m pytest tests`.

## Repository layout

```
docs/runbook.md        install -> run -> controls -> the data manifest (read this first)
docs/research/     the research deliverables (read in order)
docs/file-formats.md   what is known about .WLD / SFX / DEMOS / registry
src/lomax_modern/  read-only CLI (doctor, wldscan, measure, export, wld, slice,
                   probe-anim-nmy) + presenter (config, install gate, scaler)
                   + engine core (engine/: map/collision, 60 Hz tick, frame)
                   present) + engine core (map/collision, 60 Hz tick, frame),
                   scaler/filter, renderer, config and the P5 install gate
tests/             unit tests on synthetic fixtures + opt-in real-install tests
```

## Research documents

1. [Platform assessment](docs/research/01-platform-assessment.md) — what the
   binary actually is, and what that rules out.
2. [Resolution and display](docs/research/02-resolution.md) — the main
   question, in three layers, with the numbers.
3. [Prior art and licensing](docs/research/03-prior-art.md) — what exists, what
   may be reused, what may not.
4. [Improvement backlog](docs/research/04-improvement-backlog.md) — ranked,
   with effort and risk.
5. [Open questions](docs/research/05-open-questions.md) — what needs a real
   installation to answer.
6. [Measurements and improvements](docs/research/06-measurements-and-improvements.md)
   — what the retail install actually contains, and the top-5 plan it implies.
7. [Sources](docs/research/sources.md) — every claim's provenance.

## Licence

Code and documentation: MIT (see `LICENSE`). Game data belongs to its
rightsholders and is never included. Facts taken from third-party
reverse-engineering notes are cited, not copied; the clean-room boundary is
described in [`docs/architecture.md`](docs/architecture.md).
