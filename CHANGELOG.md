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
- Local-only game-data layout: `scripts/new_game_folder.sh` creates one slot per
  repository outside every git working tree, and `.gitignore` covers
  `game-files/`, `gamedata/`, `GAMES/` as a second line of defence.
- CI workflow: Python 3.10–3.13, byte-compile, unit tests, CLI smoke test.
- Project scaffolding: `AGENTS.md`, `CONTRIBUTING.md`, `docs/architecture.md`,
  `docs/development.md`, `docs/file-formats.md`, `.gitignore` covering game data.

### Notes

- No format layout has been verified against a real game file yet; every
  documented chunk claim is graded H/D in `docs/file-formats.md`.
- No engine work, no loader, no patcher in this release.

## [0.1.0] - 2026-11-16

Initial research-phase scaffold.
