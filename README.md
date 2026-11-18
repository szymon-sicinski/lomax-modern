# lomax-modern

Research and read-only tooling for **The Adventures of Lomax** (Psygnosis,
1996/97, Windows 95), plus the beginnings of an open-source engine that presents
the game's own data on a modern screen.

> **Current build: `0.4.0-alpha.1`** — an alpha. It runs, it is tested, and it
> will change. This document covers how to install it, how to launch it, and how
> to configure it. Nothing here is a release candidate.

## What works in this alpha

| | State |
|---|---|
| Read the game's data (`.WLD` worlds, `CELL`/`TTAB`/`MAP` tiles, `ANIM`/`NMY` sprites, audio headers) | **works**, read-only |
| Decode tile art to PNG sheets | **works** (`export`) |
| Headless engine slice: map, collision, 60 Hz tick, 16-bit frame | **works** (`slice`) |
| Present the frame at an integer scale, modern or authentic profile | **works**, writes a PNG (`present`) |
| Conformance harness: depth 16 vs 24, transparency, integer scale | **works**, `PASS 10/10` |
| A window you can watch | **not yet** — `present` renders and writes a PNG; the windowed presenter is the next milestone |
| Keyboard or gamepad input | **not yet** (M5 / v0.7) |
| Audio playback (ambience, jingles, SFX) | **not yet** (M6) — decoded, not played |
| Music | **never** — the PC build's soundtrack was CD audio, absent from a disc-less install |

## Why this exists

The question the project starts from: *what can actually be improved in Lomax
today, and which improvements are still missing?* The headline answer is in
[`docs/research/02-resolution.md`](docs/research/02-resolution.md):

- **The game is Windows-only, Win32 + MFC 4.2 + DirectDraw 7**, with an optional
  Direct3D 3 path. It is not a DOS game, so DOSBox is the wrong tool.
- **The internal resolution is hard-coded at 320x240** (8 or 16 bpp, 256-colour
  palettes). Height is effectively locked; only width can grow, and the level
  data does not impose a 512 px ceiling: of the 104 planes, 16 are narrower than
  432 px, 18 than 512 px and 24 than 640 px — beyond 512 the binding constraint
  is the engine, not the data ([measurements](docs/research/06-measurements-and-improvements.md)).
- **The widescreen/high-refresh space is occupied** by a closed-source project,
  `Lomax+`. Competing feature-for-feature is not a good use of effort.
- **What is still open**: an open-source, Linux/Wine-usable presentation layer
  with pixel-art filters; a documented asset pipeline for the `.WLD` files; and —
  as a spike, not a promise — higher-resolution internal rendering.

## What you need

- **Python 3.10 or newer** — the package has no Python dependencies.
- **Your own copy of the game, already unpacked** into a folder. The engine reads
  that folder and writes nothing into it. It never executes `LOMAX.EXE`.
- A C compiler only if you want to build the native renderer
  (`make -C native`); the Python package does not need one.

This project ships **no game data**, contains no ISO handling, and has no path
that reads a disc image.

## Install

Three ways, in increasing order of commitment.

**1. Editable install (recommended while testing):**

```bash
git clone https://github.com/szymon-sicinski/lomax-modern.git
cd lomax-modern
python3 -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e .
lomax-modern --version          # -> lomax-modern 0.4.0-alpha.1
```

**2. Build and install the wheel:**

```bash
pip wheel . -w dist/
pip install dist/lomax_modern-0.4.0a1-py3-none-any.whl
```

The wheel filename carries `0.4.0a1` because PEP 440 normalises the `-alpha.1`
tag; `lomax-modern --version` and the changelog keep the readable spelling.

**3. No install at all** — run it from the checkout:

```bash
PYTHONPATH=src python3 -m lomax_modern --version
```

`lomax-modern` and `python -m lomax_modern` are the same program; the examples
below use the short form.

## What you must supply

The engine takes **one path: an unpacked game directory** in the retail layout.
It refuses anything else with a file-by-file manifest instead of a traceback.

| Entry | Required | Read by the engine? |
|---|---|---|
| `LOMAX.EXE` | **yes** — presence only | **never** (a layout marker, never executed) |
| `WORLDS/` with ≥ 1 `*.WLD` | **yes** | **yes — the only game bytes the engine reads** |
| `SFX/` (67 WAVs) | expected | not yet (audio layer, M6) |
| `AMBIENT/` (12 loops) | expected | not yet (M6) |
| `JINGLES/` (3 stingers) | expected | not yet (M6) |
| `DEMOS/` (14 recordings) | expected | no |
| `GAME.TXT` | expected | no (`measure` reads it as a diagnostic) |

"Expected" means the run reports an incomplete copy and continues; "required"
means the run refuses the path.

**Leniency differs per command, and it is the usual source of confusion.**
`present` matches names case-insensitively and resolves a retail root nested one
level down (`slot/LOMAX/WORLDS/...`). `doctor` matches the retail names exactly
and prints `MISSING` rows for anything else. `measure` finds `*.WLD` in either
case at any depth, but its folder probes (`SFX/`, `AMBIENT/`, `JINGLES/`,
`DEMOS/`, `GAME.TXT`) are root-exact — a lowercased `sfx/` reports `SFX: 0
files` while the worlds are still listed. `slice` expects `WORLDS/VILLAGE.WLD`
literally and stops with `error: no world file at …`. If `doctor` disagrees with
`present`, believe `present`.

## Launch it

**Step 1 — check the folder before running anything.** `doctor` is read-only and
prints presence, counts, sizes and a hash; never file contents:

```bash
lomax-modern doctor "/path/to/Lomax"
```

Expect `verdict: looks like a complete PC install`. If entries are missing, it
names them. (`present` is stricter about what it will accept, and prints its own manifest —
`verdict: complete unpacked install (retail layout)` — before it renders.)

**Step 2 — present a frame.**

```bash
# Modern defaults: 1920x1080 surface, epx-aa filter, largest integer scale
lomax-modern present "/path/to/Lomax" --frame /tmp/lomax-modern.png

# Authentic: native 320x240, nearest-neighbour, no invented smoothing
lomax-modern present "/path/to/Lomax" --authentic --frame /tmp/lomax-native.png
```

You get a summary on stdout — excerpted below; `present` first prints the install
manifest, the config path and the world it picked — and a PNG where you asked for it:

```
engine: 300 ticks at 60 Hz (fixed by the engine core), 300 frames, exit reached: no
profile: modern (authentic toggle: off)
filter: epx-aa (runtime switch: --filter nearest|epx-aa)
source: 320x240 (engine frame)
surface: 1920x1080
scale: 4x (auto: largest integer fit)
content: 1280x960 at +320+60; pads left 320, right 320, top 60, bottom 60
frame: /tmp/lomax-modern.png (1920x1080)
```

The pads are the letterbox: 4× of 320×240 is 1280×960, centred in 1920×1080.

**Choosing a world.** `--world WEST` selects a world stem from `WORLDS/`;
`--playfield N` picks which map plane is treated as the playable grid;
`--ticks N` sets how long the headless engine runs (300 = 5 s at 60 Hz).

**Controls: none in this build.** `present` runs the engine's scripted input and
has no window yet ([`docs/architecture.md`](docs/architecture.md) §5); keyboard
and gamepad are M5. The engine's actions are left, right and jump — no bindings
are invented here.

**There is no music track.** The PC soundtrack was CD audio and a disc-less
install has none: ambience, jingles and SFX only. Nothing is bundled, downloaded
or extracted, and this build's presenter is silent until the audio layer (M6).

## Configure it

Configuration is a **versioned JSON file**, created on first run, kept **outside
your game folder**.

### Where the file lives

| Platform | Path |
|---|---|
| Linux / BSD | `$XDG_CONFIG_HOME/lomax-modern/config.json` (default `~/.config/lomax-modern/config.json`) |
| macOS | `~/Library/Application Support/lomax-modern/config.json` (path implemented, untested) |
| Windows | `%APPDATA%\lomax-modern\config.json` |
| Any | `$LOMAX_CONFIG=/path/to/file.json` wins outright |
| Any | `--config /path/to/file.json` for one run |

### What is in it

```json
{
  "version": 1,
  "modern": true,
  "filter": "epx-aa",
  "surface": [1920, 1080],
  "scale": null
}
```

| Key | Values | Meaning |
|---|---|---|
| `version` | `1` | Schema version. A file written by a newer build is **refused**, not silently misinterpreted. |
| `modern` | `true` / `false` | Profile. `true` = modern defaults; `false` = authentic 320×240 + nearest. |
| `filter` | `"nearest"` / `"epx-aa"` | Pixel-art filter used when scaling. |
| `surface` | `[width, height]` | Presentation surface; content is centred with integer padding. |
| `scale` | `null` or a positive integer | `null` = the largest integer that fits (the CLI spells this `--scale auto`); a number pins that factor. |

An unknown key, a corrupt file, or a `version` from the future is an error —
never a silent fallback — and invalid JSON is reported with its line and column.

### Precedence

```
command-line flags   >   the config file   >   built-in defaults
```

Flags apply to **one run**. Add `--save` to persist the effective settings:

```bash
# Try the filter, keep it if you like it
lomax-modern present "/path/to/Lomax" --filter nearest
lomax-modern present "/path/to/Lomax" --filter nearest --save

# A bigger surface with an explicit 5x scale
lomax-modern present "/path/to/Lomax" --surface 2560x1440 --scale 5 --save

# Back to the shipped defaults
lomax-modern present "/path/to/Lomax" --modern --filter epx-aa --surface 1920x1080 --scale auto --save
```

`--authentic` and `--modern` are mutually exclusive; the rest combine freely.
Deleting the config file is a safe reset — `present` writes a fresh one on the
next run.

## Command reference

Every command is read-only with respect to your game folder.

| Command | What it does |
|---|---|
| `doctor <dir>` | Inventory an install: presence, counts, sizes, executable hash. |
| `measure <dir>` | Chunk sequence per world, plane widths, audio formats; `--json` for a report. |
| `wldscan <file.wld>` | List chunk tags and offsets; ranks header hypotheses. |
| `wld roundtrip --check` | Prove the reader/writer reproduces every world file byte-for-byte. |
| `export <file.wld> --out DIR` | Decode `CELL`/`TTAB`/`MAP` into PNG sheets. |
| `slice <dir>` | Headless vertical slice: map, collision, 60 Hz tick, 16-bit frame. |
| `present <dir>` | Present the frame at an integer scale; writes a PNG. |
| `probe-anim-nmy <dir>` | Structural probe of `ANIM`/`NMY`/`GNMY`: offsets and hypotheses scored by coverage, never a claimed parse. |
| `anim-nmy <dir>` | Decode the recovered `ANIM`/`NMY` framings; report per-world counts. |

Exit codes: `0` success · `1` a run failed (for example the PNG could not be
written) · `2` usage error or a refused install.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `error: not a directory: /path` | Typo, or a relative path from another shell | Use the absolute path to the folder that contains `WORLDS/` |
| `present`: `verdict: not an unpacked Lomax game directory -- missing: …` | Not an unpacked retail copy; the list names what is absent | Point at the folder holding `LOMAX.EXE` and `WORLDS/`; an ISO or mounted disc image is not accepted |
| `doctor`: `verdict: incomplete install, missing: …` | `doctor` matches retail names exactly; `present` and `measure` are more forgiving | `doctor` still inventories the folder; if `present` accepts the same folder, the `MISSING` rows are the naming difference, not missing files |
| `error: no *.WLD found under …` (from `wld roundtrip` / `anim-nmy`) | No `.WLD`/`.wld` exists anywhere under the path — the search is recursive and case-insensitive, so an oddly named folder is *not* the cause | Point at the install root, or pass a single world file |
| `unsupported config version N` | The config was written by a newer build | Delete the config file (it is recreated) or point `--config` elsewhere |
| `surface must be WIDTHxHEIGHT` | Malformed `--surface` | `1920x1080`, `1920*1080` and `1920,1080` are accepted |
| `frame: none written` | No `--frame` given | This build has no window; pass `--frame PATH` to get a PNG |
| Colours look brighter than the original | A build before `0.4.0-alpha.1` | The 6→8-bit green expansion was wrong in three places; fixed in `0.4.0-alpha.1` |
| `lomax-modern: command not found` | The venv is not active | `. .venv/bin/activate`, or use `python -m lomax_modern` |

Nothing in this build needs a display: it runs headless, in CI, and over SSH.

## Develop

```bash
pip install -e ".[dev]"

python -m pytest tests -m "not realgame"                  # synthetic fixtures only
LOMAX_GAME_DIR="/path/to/Lomax" python -m pytest tests    # + real-install checks

make -C native && ./native/smoke                          # C99 renderer, 20 golden checks
python -m lomax_modern.conformance                        # M4 exit criterion, PASS 10/10
```

The conformance harness is the interesting one: it renders the same synthetic
scene through the 16-bit renderer and an independent RGB888 reference and
asserts pixels, with a tolerance **measured** over all 32,768 colour words
(`(0, 2, 0)`). It exists because a checker that cannot fail proves nothing —
it is what caught a green-channel bug in three separate copies.

## Repository layout

```
docs/runbook.md        the long-form guide: manifest, config, examples, exit codes
docs/architecture.md   layering, the windowed-presenter plan, clean-room boundary
docs/file-formats.md   what is known about .WLD / CELL / TTAB / MAP / ANIM / NMY
docs/roadmap/          milestones, releases, risks, budget
docs/research/         the research deliverables (read in order)
src/lomax_modern/      CLI, engine core, renderer, scaler, presenter, config,
                       install gate, conformance harness
native/                C99 hot path + golden smoke test
tests/                 unit tests on synthetic fixtures + opt-in real-install tests
```

## Research documents

1. [Platform assessment](docs/research/01-platform-assessment.md) — what the
   binary actually is, and what that rules out.
2. [Resolution and display](docs/research/02-resolution.md) — the main question,
   in three layers, with the numbers.
3. [Prior art and licensing](docs/research/03-prior-art.md) — what exists, what
   may be reused, what may not.
4. [Improvement backlog](docs/research/04-improvement-backlog.md) — ranked, with
   effort and risk.
5. [Open questions](docs/research/05-open-questions.md) — what needed a real
   installation to answer, and which are now answered.
6. [Measurements and improvements](docs/research/06-measurements-and-improvements.md)
   — what a retail install actually contains.
7. [Sources](docs/research/sources.md) — every claim's provenance.

## What this repository is not

- Not a game download, and it contains **no game assets**.
- Not a CD-check bypass, and it does not patch or redistribute `LOMAX.EXE`.
- Not a fork of `Lomax+` (that project has no licence; see
  [`docs/research/03-prior-art.md`](docs/research/03-prior-art.md)).
- Not a finished engine: see the alpha table at the top.

## Licence

Code and documentation: MIT (see `LICENSE`). Game data belongs to its
rightsholders and is never included. Facts taken from third-party
reverse-engineering notes are cited, not copied; the clean-room boundary is
described in [`docs/architecture.md`](docs/architecture.md).
