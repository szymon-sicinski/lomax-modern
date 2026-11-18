# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **`lomax-modern export` — `TTAB`/`CELL`/`MAP` decoder and PNG sheet exporter**
  (`src/lomax_modern/art.py`, `png.py`; stdlib only, no Pillow). Verified on the
  retail install: 75,122 `TTAB` records / 300,488 cell-index words, 14,974
  `CELL` records (14,861 of them referenced by `TTAB`), 523,229 `MAP` cells over
  104 planes. The exporter writes `_cells.png`, `_tiles_planeNN.png` and
  `_map_planeNN_collision.png` for one world to a user-chosen directory and
  prints the confidence of every step:
  - `MAP` → `TTAB` stays **unresolved (Q20)** and no unique-tile count is
    invented; the tile sheet draws each record's four cells in stored order
    because the order inside a record is not proven (G1).
  - `TTAB` flag bits (`0x2000` on 16,503 words, `0x4000` on 2,499, `0x8000`
    never) and out-of-bank indices (index 256 in `BONUS.WLD`, 1,644 words) are
    preserved verbatim, never repaired or clamped.
  - `ANIM` sprite frames are reported as **unresolved (Q24)** instead of being
    guessed.
  - The palette slot is a printed hypothesis (Q29): slot 1 renders natural art
    where slot 0 is hue-shifted, and no container field names the slot.
  - `export` refuses an output directory inside the install.
- Retracted two documented format claims after measurement and recorded the
  evidence: `colors[0]` is **not** white and real white is not at `0x7FFE`
  (§2.3), and "all shipped tiles use palette 0" does not survive rendering
  (§2.3, Q8). `CELL` pixel order and the `TTAB` 2x2 assembly are now graded
  hypotheses rather than documented fact (§2.4).
- Synthetic fixtures for `CELL`/`TTAB`/`MAP` payloads and palettes; 84 unit
  tests plus 3 opt-in `realgame` tests that decode all 104 planes.
- `python -m lomax_modern` now works (module entry point), not only the console
  script.

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
- `lomax_modern.wld` — a `.WLD` parser/writer that reads a world file into
  `Chunk`/`World` records and re-emits it byte-for-byte. Only the verified
  layout is interpreted (chunk header `tag[4]` + big-endian `u32` payload size,
  `HEAD` width/height, whole 64-byte `CELL` count, `MAP` cell/padding math);
  every other tag (`TTAB`, `ANIM`, `NMY`, `MACR`, `PAGE`, ...) round-trips as
  opaque bytes. Round-trip is proven against all 9 retail world files
  (SHA-256 in == out).
- Local-only game-data layout: `scripts/new_game_folder.sh` creates one slot per
  repository outside every git working tree, and `.gitignore` covers
  `game-files/`, `gamedata/`, `GAMES/` as a second line of defence.
- CI workflow: Python 3.10–3.13, byte-compile, unit tests, CLI smoke test.
- Project scaffolding: `AGENTS.md`, `CONTRIBUTING.md`, `docs/architecture.md`,
  `docs/development.md`, `docs/file-formats.md`, `.gitignore` covering game data.

### Notes

- Format claims are graded V/D/H in `docs/file-formats.md`: the chunk container,
  `HEAD` dimensions, `MAP` cell math, `CELL` sizing and the audio formats are
  verified against the retail install; `TTAB`, `ANIM` and `GNMY` internals remain
  documented or hypothetical.
- No engine work, no loader, no patcher in this release.

## [0.1.0] - 2026-11-16

Initial research-phase scaffold.
