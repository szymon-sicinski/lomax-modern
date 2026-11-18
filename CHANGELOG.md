# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Research report: platform assessment (Win32/MFC/DirectDraw 7, not DOS),
  three-layer resolution analysis, prior-art and licence review, ranked
  improvement backlog, open questions, cited source list.
- `lomax-modern` CLI with two read-only commands:
  - `doctor <game_dir>` — install inventory (presence, counts, sizes, SHA-256 of
    the executable, world-file listing). Prints no file contents.
  - `wldscan <file>` — `.WLD` chunk scanner that ranks header hypotheses
    (tag/size order, endianness, size semantics) and reports tag names and
    offsets without decoding payloads.
- Synthetic chunk-container fixtures and 16 unit tests, including negative cases
  (unaligned sizes, truncation, garbage, unknown tags).
- Measurement probe: `lomax-modern measure` / `scripts/measure_worlds.py` reports
  the chunk sequence and counts per world file, the plane-width histogram per
  section (the number that decides the widescreen ceiling), the HEAD endianness
  vote, RIFF/WAVE formats in `SFX`/`AMBIENT`/`JINGLES`, `GAME.TXT` structure and
  `DEMOS` framing — read-only, sizes and header fields only, with the documented
  HEAD layout labelled as a hypothesis until real files confirm it.
- **First measurements against the retail PC install** (`06-measurements-and-improvements.md`):
  - `.WLD` container confirmed on 9/9 files: tag[4] space-padded + big-endian
    `u32` payload size; order includes the previously undocumented `PARA`,
    `MACR`, `PAGE`.
  - `HEAD` width/height verified on **104/104 planes** by cross-checking the
    sibling `MAP` (3 bytes per 16x16 cell, padded to 4). `CELL` payloads are
    whole 64-byte cells (14,974 cells).
  - 104 plane widths measured: 16 are narrower than 432 px, 18 narrower than
    512, 24 narrower than 640 — so the 512 px widescreen ceiling is a code
    limit, not a level-data limit.
  - All 82 audio files are RIFF/WAVE mono 22,050 Hz 16-bit with a 44-byte
    header; `DEMOS` are fixed 2,048/8,192-byte recordings; `GAME.TXT` is
    19,532 bytes / 1,321 lines with no non-ASCII bytes.
  - `LOMAX.EXE` imports `DINPUT.dll`, so DirectInput is used by the PC build.
  - `measure.py`'s first geometry heuristic was replaced by the `MAP`
    cross-check after it discarded 69 of 104 real planes.
- Opt-in integration tests behind `LOMAX_GAME_DIR`.
- **Presenter data layer (M4)**: `lomax_modern.scaler` — pure, dependency-free,
  integer-only scaling for the 16-bit `B5G6R5` framebuffer:
  - `nearest` (exact block replication, invents no colour) and `epx_aa` (Scale2x/
    EPX corner rule with fractional edge anti-aliasing; index copies in
    palettised mode, and the transparent key is never painted into a sprite);
  - `fit_scale` / `present` — largest integer scale that fits, shared by both
    axes so aspect is never stretched, explicit letterbox/pillarbox offsets and
    per-side pads, optional `max_scale`;
  - `Image` buffer type with explicit little-endian `B5G6R5` conversion, and
    `pack_rgb565`/`unpack_rgb565` in the hardware's 5/6/5 units.
  - 50 unit tests over synthetic buffers, including the negative cases (no
    smear of 1-px dither, no erasure of 1-px detail, ≤50 % neighbour coverage,
    no colour outside the 3x3 window, rejection of fractional/zero factors and
    of surfaces too small for any integer fit).
- `examples/scale_demo.py` — side-by-side demonstration of both filters on a
  generated 16x16 sprite: ASCII in indexed mode (diffable) plus an optional
  truecolour PNG written with `zlib` only.
- `lomax_modern.wld` — a `.WLD` parser/writer that reads a world file into
  `Chunk`/`World` records and re-emits it byte-for-byte. Only the verified
  layout is interpreted (chunk header `tag[4]` + big-endian `u32` payload size,
  `HEAD` width/height, whole 64-byte `CELL` count, `MAP` cell/padding math);
  every other tag (`TTAB`, `ANIM`, `NMY`, `MACR`, `PAGE`, ...) round-trips as
  opaque bytes. Round-trip is proven against all 9 retail world files
  (SHA-256 in == out).
- `lomax-modern wld roundtrip [--check]` — re-parses every `WORLDS/*.WLD` file
  (a single file, or the whole folder via `LOMAX_GAME_DIR`/`--game-dir`),
  re-emits it in memory and reports per-file `identical`/`DIFFERENT` without
  ever printing payload bytes or a digest. `--check` exits non-zero on the
  first mismatch. `python -m lomax_modern` now works via a new `__main__.py`.
- Local-only game-data layout: `scripts/new_game_folder.sh` creates one slot per
  repository outside every git working tree, and `.gitignore` covers
  `game-files/`, `gamedata/`, `GAMES/` as a second line of defence.
- **`ANIM`/`NMY` framings recovered from `LOMAX.EXE` (LMX-11)** — `lomax_modern.anim_nmy`
  plus `lomax-modern probe-anim-nmy`, which validates the recovered sprite and
  type-table framings against an install (read-only, counts only). `ANIM` is a
  12-byte header + `n` frames (`i16` width/height, `u16` fields, then `w·h`
  (or packed 4-bit `(w·h)>>1`) pixel bytes) — **566/566** chunks parse cleanly;
  `NMY` is a variable-length name + binary-tail type table (tag/animations/frames)
  — **9/9** parse cleanly, and each world's record count equals its max `GNMY`
  type index + 1. Addresses and the load chain are in `docs/file-formats.md`
  §2.8. Unit tests use synthetic fixtures only.
- CI workflow: Python 3.10–3.13, byte-compile, unit tests, CLI smoke test.
- Project scaffolding: `AGENTS.md`, `CONTRIBUTING.md`, `docs/architecture.md`,
  `docs/development.md`, `docs/file-formats.md`, `.gitignore` covering game data.
- **Engine core (M3) — vertical slice**: `lomax_modern.engine`, the simulation
  half of the own engine, and `lomax-modern slice`, a headless vertical-slice
  runner:
  - `level` — loads a `.WLD` into a playable grid via `wld` + `art`, with a
    `CollisionModel` that uses only the measured 0-vs-non-zero rule (`0`
    passable, non-zero solid `[H]`), preserves every collision byte verbatim,
    and retracts the documented `[D]` bit-field.
  - `state` — a fixed **60 Hz** tick: input, gravity, axis-separated movement
    and collision resolution (player bounded by the level edge), collect and
    exit detection, and a JSON-serialisable `Snapshot` save-state design.
  - `render` — a 16-bit `B5G6R5` `Frame` (little-endian `u16` words) and a
    camera that composes the collision grid plus player/collectible/exit
    markers at the native 320x240 viewport; the art blit/palette path is M4's.
  - `run` — `run_slice`, the headless harness that reports ticks, frames, the
    collision-byte histogram, and a clean exit, without a display or
    `LOMAX.EXE`.
  - 23 unit tests over synthetic worlds (loading, collision model, gravity,
    walking, wall/floor collision, jump, collect, exit, next-level transition,
    fixed timestep, save-state round-trip, `B5G6R5` packing, frame
    serialisation, camera, rendering, the headless runner).
- **Measurement (2026-11-18)**: the `MAP` collision byte is near-uniform over
  all 256 values across the 104 retail planes (`0x00` 81–95 % by world, `0x01`
  the clear second in playable worlds) — retracting the `[D]` "`0x80` solid /
  `0xC0` one-way" bit-field and filing the byte's true semantics as **Q31**.

### Notes

- Format claims are graded V/D/H in `docs/file-formats.md`: the chunk container,
  `HEAD` dimensions, `MAP` cell math, `CELL` sizing, the audio formats and the
  `ANIM`/`NMY`/`GNMY` framings are verified against the retail install; `TTAB`
  internals (cell order, flag semantics) remain documented or hypothetical.
- The engine core (M3) is a Python reference simulation: a playable first world
  at the original 60 Hz, drawing a geometric frame from decoded `CELL`/`TTAB`/
  `MAP` data. The tile-art blit, palette transparency and scaling are the M4
  renderer card; entity and spawn placement wait on the `GNMY` semantics (Q23)
  and the map→tile link (Q20).

## [0.1.0] - 2026-11-16

Initial research-phase scaffold.
