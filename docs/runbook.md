# Runbook — from your own copy to a running presenter

This is the long form of the README's **Runbook** section: how to install the
project, what to put where, how to run `lomax-modern present`, what the modern
defaults and the authentic toggle actually do, and what happens when files are
missing. It assumes one thing you supply yourself: **an unpacked game directory**.

Two statements up front, because they shape everything below:

- **This project ships no game data.** No world files, no audio, no sprites, no
  executable, no disc images. It reads *your* copy in place and writes nothing
  into it.
- **There is no music track.** It is not missing by accident and it cannot be
  downloaded here — see [§7](#7-audio-ambience-jingles-and-sfx--and-no-music).

## 1. What you need

| Need | Detail |
|---|---|
| Python | 3.10 or newer (`pyproject.toml`), tested on 3.10–3.13 |
| `git` | to clone the repository |
| Your own copy of the game | **unpacked into a normal folder**, retail layout — see [§3](#3-what-you-must-supply-the-data-manifest) |
| Compiler / GPU / network | **not** needed: the package has no runtime dependencies |

Platforms: **Linux** and **Windows** are the target hosts. **macOS is
deferred.** There is no store presence and nothing to buy.

If you only want the read-only inspection tools (`doctor`, `wldscan`,
`measure`, `export`, `wld roundtrip`, `probe-anim-nmy`), §2 is enough; §3–§4 are
about the presenter.

## 2. Install

```bash
git clone https://github.com/szymon-sicinski/lomax-modern.git
cd lomax-modern
python3 -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
lomax-modern --version
```

`".[dev]"` adds `pytest` for the test suite; `pip install -e .` is enough to run
the tools. The package itself is dependency-free, so there is no compiler step
and no download beyond `pip`'s own.

## 3. What you must supply: the data manifest

The engine takes **one path** — a folder holding the retail layout, normally the
folder you installed the game into. It does not take a disc, an image, an
archive, a URL, or a compressed copy:

```text
/path/to/Lomax/
├── LOMAX.EXE          present, never read (the install gate only checks it exists)
├── GAME.TXT           localised text; not read by the engine
├── WORLDS/
│   ├── VILLAGE.WLD    the world the presenter plays by default
│   └── *.WLD          the other eight world containers
├── SFX/               67 WAVs   (sound effects)
├── AMBIENT/           12 WAVs   (6 worlds x a stereo _L/_R pair)
├── JINGLES/           3 WAVs    (LEVELEND, GAMEOVER, WORLDEND)
└── DEMOS/             14 files  (recorded input; used by the original, not by us)
```

`LOMAX.HLP`, `LOMAX.CNT` and `LOMAX.GID` (Windows help) may also be there; they
are ignored. A `MUSIC/` folder does **not** exist in an installed copy — it lives
on the CD only, which is the whole reason for [§7](#7-audio-ambience-jingles-and-sfx--and-no-music).

### Which entries are required, and which the engine actually reads

| Entry | Required | Read by the engine today? | What it is |
|---|---|---|---|
| `LOMAX.EXE` | **yes** (presence only) | **never opened or executed by the engine**; only the read-only `doctor` inventory reports a 16-character digest prefix of it | the retail Win32 binary |
| `WORLDS/` with ≥ 1 `*.WLD` | **yes** | **yes — the only game bytes the engine reads** | 9 world containers: levels, tiles, sprites |
| `SFX/` | expected | not yet — the audio layer (M6, v0.7) will read it | 67 WAVs, mono 22,050 Hz 16-bit |
| `AMBIENT/` | expected | not yet — M6 | 12 loops, 6 worlds × stereo `_L`/`_R` |
| `JINGLES/` | expected | not yet — M6 | 3 stingers |
| `DEMOS/` | expected | no | recorded input for the original's demo mode |
| `GAME.TXT` | expected | no (`measure` inspects it as a diagnostic) | localised text, marker-delimited |

"Expected" means: its absence is **reported** as an incomplete copy but does not
stop the presenter. "Required" means the gate refuses the path. That split
exists so you can tell *"this is not the game"* apart from *"this is the game,
but an incomplete copy"* — see [§8](#8-when-data-is-missing-or-wrong).

Two leniencies, both for real installs rather than convenience:

- **Name case is ignored.** `worlds/village.wld` is fine; a case difference is
  not a missing file.
- **One level of nesting is resolved.** If you point the tool at a folder that
  contains `LOMAX/` as a sub-folder, the report says
  `install root resolved one level down: LOMAX/`. If **two** sub-folders both
  look like an install, it refuses and names them instead of guessing.

## 4. Run

```bash
export LOMAX_GAME_DIR="/path/to/Lomax"     # your folder; any name works

# What is in there? (read-only inventory: presence, counts, sizes)
lomax-modern doctor "$LOMAX_GAME_DIR"

# The presenter, with the modern defaults
lomax-modern present "$LOMAX_GAME_DIR"

# The authentic profile: native 320x240, nearest-neighbour
lomax-modern present "$LOMAX_GAME_DIR" --authentic

# Pin the surface / filter / scale for one run, and write the frame as a PNG
lomax-modern present "$LOMAX_GAME_DIR" --surface 1280x720 --filter nearest \
    --scale 3 --frame /tmp/frame.png

# Capture a frame sequence: one presented PNG per 60 Hz tick
lomax-modern present "$LOMAX_GAME_DIR" --authentic --surface 640x480 \
    --frames 300 --out /tmp/lomax-frames
```

A run prints the data manifest, then the engine and presentation numbers. Real
output from a retail-layout folder (the per-file table is abridged here):

```text
install: /path/to/Lomax

  entry        kind   state       files       bytes  note
  WORLDS/      dir    present         9     7107048
  SFX/         dir    present        67     1391846
  AMBIENT/     dir    present        12     2480444
  JINGLES/     dir    present         3      503068
  DEMOS/       dir    present        14       65536
  LOMAX.EXE    file   present                505344  unused by the engine
  GAME.TXT     file   present                 19532
  worlds       set    present         9     7107048  *.WLD
    ...one line per world file...

verdict: complete unpacked install (retail layout)
config: /home/you/.config/lomax-modern/config.json (created with modern defaults)
world: VILLAGE.WLD
engine: 300 ticks at 60 Hz (fixed by the engine core), 300 frames, exit reached: no
profile: modern (authentic toggle: off)
filter: epx-aa (runtime switch: --filter nearest|epx-aa)
source: 320x240 (engine frame)
surface: 1920x1080
scale: 4x (auto: largest integer fit)
content: 1280x960 at +320+60; pads left 320, right 320, top 60, bottom 60
frame: none written (pass --frame PATH for a PNG; or use `lomax-modern window` for a live SDL2 window)
```

How to read it:

| Line | Meaning |
|---|---|
| `world` | which `*.WLD` was loaded (`--world NAME` to pick another; default is `VILLAGE` when present, else the first file) |
| `engine` | fixed 60 Hz tick count, frames produced, whether the `Exit` placement was reached in `--ticks` |
| `profile` | modern (default) or authentic |
| `filter` | `epx-aa` or `nearest`; switchable per run with `--filter` |
| `source` / `surface` | the engine frame is **always** 320x240; `surface` is the presentation size |
| `scale` / `content` / `pads` | the integer factor actually used, the scaled content size, its offset, and the letterbox/pillarbox pads |
| `frame` | the PNG written by `--frame`, if any |
| `frames` | the `frame_NNNN.png` sequence written by `--frames N --out DIR`, and its size |

**A window now ships.** `present` computes the padded surface (and can write it
as a PNG with `--frame`, or one PNG per tick with `--frames N --out DIR`);
`lomax-modern window "<install>"` opens a live SDL2 window that letterboxes the
engine frame and prints a one-line HUD — `fps`, plane name, tile count, camera
and `collect N/M`, the `Moneybag`s picked up over those on the playfield
(`0/0` on a world with no `Moneybag` placement) — with `--seconds N`,
`--world NAME`, `--modern`/`--authentic`. The native Win32/C presenter
(packaging) is still future (`docs/architecture.md` §5). `present` is a
presentation pipeline, not a game you can play with the keyboard — `play` is
the interactive form (see §5).

## 5. Controls

`lomax-modern play "<install>"` is the interactive form of the engine: it opens
the same SDL2 window as `window` but reads the keyboard every tick, so you move
and jump live at the engine's 60 Hz. `present`, `slice` and `window` remain
scripted (walk right, jump periodically) — they never read the keyboard.

The default mapping (arrow keys and WASD):

| Action | Keys |
|---|---|
| Move left | ← or `A` |
| Move right | → or `D` |
| Jump | Space, ↑ or `W` |
| Duck (crouch) | ↓ or `S` |

- **Left/right are level-triggered** — hold to move, and holding both sides at
  once is neutral. **Jump is edge-triggered** — a fresh press jumps once; a
  held jump key does not re-jump on landing. **Down is level-triggered** too:
  a grounded player holding it draws `DUCK` (a one-shot 6-pose clip that holds
  its last pose, §2.6.2 a row 23) and releasing it stands back up; in the air
  the down key has no effect.
- **Esc** (or closing the window) quits.
- `--seconds N` (default 60) bounds the run so the headless
  `SDL_VIDEODRIVER=dummy` check exits cleanly; without the bound a real session
  ends when you reach the exit or quit.
- Gamepad support and rebinding remain **M5**
  ([`roadmap/10-milestones.md`](roadmap/10-milestones.md) §M5, release v0.7);
  the mapping above is the keyboard-only scope of the playable-level plan
  (`docs/roadmap/45-playable-level-plan.md` §1.1).

## 6. Modern defaults and the authentic toggle

Quality-of-life first: the modern experience is the default and authenticity is
the opt-in (`docs/roadmap/15-strategy-report.md` §7).

| | Modern (default) | Authentic (`--authentic`) |
|---|---|---|
| Surface | 1920x1080, content integer-scaled and centred | native 320x240, one screen pixel per source pixel |
| Filter | `epx-aa` (edge-directed pixel-art filter) | `nearest` |
| Scale | largest integer factor that fits | 1x |
| Tick rate | engine's fixed 60 Hz | engine's fixed 60 Hz |

The toggle is a **profile**, not one boolean: `--authentic` sets all three axes.
An explicit flag then overrides a single axis, and the report shows the mix, so
`--authentic --filter epx-aa` is a deliberate combination rather than a
contradiction. A `--scale N` that does not fit is refused with the largest factor
that does, instead of being silently shrunk.

### The config file

Settings persist in a small JSON file, created on the first run that gets past
the install gate:

| Platform | Default location |
|---|---|
| Linux / other | `$XDG_CONFIG_HOME/lomax-modern/config.json` (`~/.config/...` when unset) |
| Windows | `%APPDATA%\lomax-modern\config.json` |
| macOS (deferred) | `~/Library/Application Support/lomax-modern/config.json` |

`$LOMAX_CONFIG` or `--config PATH` overrides the location for a portable install.

```json
{
  "version": 1,
  "modern": true,
  "filter": "epx-aa",
  "surface": [1920, 1080],
  "scale": null
}
```

- `scale: null` means *auto* — the largest integer factor that fits.
- Keys: `modern` (bool), `filter` (`nearest` | `epx-aa`), `surface`
  (`[width, height]`), `scale` (`null` or a positive integer), `version` (1).
- **Unknown keys are an error, not a warning.** A silently ignored `filtre`
  would be a setting that never takes effect.
- Command-line flags apply to **one run**; `--save` persists them.
- The config is **refused inside the game folder** (`--config` elsewhere), and it
  is written atomically — a half-written config would break the next run.

## 7. Audio: ambience, jingles and SFX — and no music

**There is no music track, and this project will not ship one.** The retail PC
build's soundtrack was CD audio (MCI `cdaudio`); the installed data contains no
CD-DA, MP3, OGG or MOD file of any kind. A disc-less copy therefore has
**ambience, jingles and sound effects — and no music**. That is a property of the
data you own, not a feature that is "coming later".

What *is* on disk (measured, 82 RIFF/WAVE files, mono 22,050 Hz 16-bit):

| Folder | Files | Role in the plan |
|---|---|---|
| `SFX/` | 67 | sound effects, played as-is |
| `AMBIENT/` | 12 | 6 worlds × a stereo `_L`/`_R` pair — the per-world bed that replaces music |
| `JINGLES/` | 3 | `LEVELEND`, `GAMEOVER`, `WORLDEND` on transitions |

The audio layer is **M6** (release v0.7); this build's presenter is silent. No
audio is bundled, downloaded or extracted — the files are read from your folder
when that layer lands. An optional *user-supplied* music folder is a possible
later feature, not part of v0.1, and it would still never ship audio.

## 8. When data is missing or wrong

The gate (`docs/roadmap/30-risks.md` P5) reports **file by file** instead of
failing vaguely. Exit codes: **2** for a rejected path or configuration,
**1** for a world file that cannot be read.

**Not the game** — nothing is written, the run stops:

```text
  entry        kind   state       files       bytes  note
  WORLDS/      dir    MISSING                        required
  SFX/         dir    MISSING                        optional
  ...
  LOMAX.EXE    file   MISSING                        required

verdict: not an unpacked Lomax game directory -- missing: WORLDS/, LOMAX.EXE
error: not an unpacked Lomax game directory: /path/to/Lomax
hint: present expects the retail layout (WORLDS/ with *.WLD, SFX/, AMBIENT/, JINGLES/, DEMOS/, LOMAX.EXE). It never reads a disc image.
```

**The game, but an incomplete copy** — the presenter runs:

```text
verdict: unpacked install, incomplete optional entries: AMBIENT/, JINGLES/, DEMOS/, GAME.TXT (the presenter still runs)
```

Other cases:

| Situation | What happens |
|---|---|
| Path is a file, or does not exist | `verdict: not a directory -- pass the folder that holds WORLDS/ and LOMAX.EXE`, exit 2 |
| Retail folder copied *inside* the folder you named | resolved one level down, and the report says so |
| Two sub-folders look like an install | refused as `ambiguous`, both names printed — point at one |
| `--world` typo | `world 'X' not found; available: BONUS, ED, ...`, exit 2 |
| Config or `--frame` inside the game folder | refused before writing, exit 2 |
| `--out` inside the game folder (with `--frames`) | `error: refusing to write inside the game folder (...)`, exit 2, nothing created |
| `--frames` without `--out`, or `--out` without `--frames` | usage error, exit 2 |
| `--frames` together with `--frame` | usage error from the parser, exit 2 |
| A `*.WLD` that is not a world container | `error: cannot read VILLAGE.WLD: offset 0: empty input: no chunk header`, exit 1 — caught, no traceback (also on `slice` and `anim-nmy`) |

## 9. Platforms and packaging

| Host | This build (M2/M4 scope) | Planned |
|---|---|---|
| Linux | `pip install` + CLI; `python -m lomax_modern` also works | **AppImage** (M7, v0.8) |
| Windows | `pip install` + CLI | **`.exe`** (M7, v0.8; built in CI) |
| macOS | untested, deferred | not planned for v1 |

Packaging ships **only our MIT code**: no game bytes, no Wine, no closed DLLs. An
AppImage or `.exe` is a launcher that loads *your* data directory and fails with
the file-by-file manifest above when it is missing. A Windows binary is built by
CI; it has not been executed on a Linux development box, so treat "runs on
Windows" as CI-verified only until someone runs it there.

## 10. Where the rest is documented

- [`docs/architecture.md`](architecture.md) — module boundaries, clean-room rule,
  and why the presenter is C while the reference is Python.
- [`docs/file-formats.md`](file-formats.md) — every format claim with its
  evidence grade (**V** verified / **D** documented / **H** hypothesis).
- [`docs/research/05-open-questions.md`](research/05-open-questions.md) — Q29 is
  this manifest; Q30 is the no-music finding.
- [`docs/research/06-measurements-and-improvements.md`](research/06-measurements-and-improvements.md)
  — what a retail install actually contains, measured.
- [`docs/roadmap/10-milestones.md`](roadmap/10-milestones.md) — what each future
  milestone adds (M5 input, M6 audio, M7 packaging).
- [`docs/development.md`](development.md) — tests, fixtures, local game-data
  layout.

The retail executable is **not** part of this path: the project never runs
`LOMAX.EXE` and never works around its CD check. Disc owners who prefer the
original binary have an appendix in
[`docs/roadmap/15-strategy-report.md`](roadmap/15-strategy-report.md) §9, and it
too uses only a physical disc they own.
