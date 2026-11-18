# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `lomax-modern probe-tiles` — a read-only probe that validates the recovered
  `MAP`/`TTAB`/`CELL` tile-pipeline layouts against an install and reports the
  counts (map words, tiles, flips, palettes, collision bytes) plus the scores of
  the superseded interleaved/8-byte readings, so a wrong assumption stays visible.

### Changed

- `docs/file-formats.md` §2.4/§2.8: the `MAP` payload is `N` big-endian `u16`
  tile words then `N` collision bytes (not 3 bytes interleaved per cell); a
  `TTAB` record is 16 bytes = four `[16-bit index word, flag word]` cells (not
  four 13-bit indices). The map word is a direct `TTAB` record index; the flag
  word carries flip (`0x2000` H / `0x4000` V / `0x6000` both) and palette
  (bits 8-11).
- `docs/research/05-open-questions.md`: Q20, Q21, Q22 and Q27 answered; Q8, Q9
  and Q31 narrowed by the same correction.

### Fixed

- `anim-nmy` refuses a `*.WLD` that is not a world container the way `slice`
  and `present` already did: one `error: cannot read …` line and exit 1,
  instead of a `WLDParseError` traceback.

## [0.4.0-alpha.1] — 2026-11-18

The M2–M4 vertical slice: decoded data layer, headless engine, 16-bit
renderer with a C99 hot path, a presenter you can look at, and the runbook
that ties them together. Everything below under *Added* since 0.1.0.

### Added

- Token-cost measurement and reduction analysis: `scripts/token_cost_report.py`
  joins the board's `worker_session_id` against per-call `logs/agent.log` lines
  and now splits input into **cached vs fresh** (from the per-call `cache=`
  field), so the processed-vs-billed split is reproducible
  (`docs/roadmap/41-measured-cost.md`). `docs/roadmap/42-input-token-reduction.md`
  shows the 91:1 input:output headline is a cache artifact — 2.4:1 fresh:output,
  ~$10 off-peak rather than the ~$104 the raw number implies — and ranks the
  measured levers on `calls × context`.
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
- `lomax-modern probe-anim-nmy` — a structural probe for the `ANIM`/`NMY`/`GNMY`
  chunks that reports offsets, sizes and token-stream diagnostics, then scores
  candidate record framings by how cleanly each consumes the chunks. Every
  framing is labelled a hypothesis (or `retracted` for the two falsified `[S2]`
  claims); the group prints `unresolved` when no framing wins. No layout is
  asserted and no payload is decoded. Run against the retail install it shows:
  `ANIM` only **44/566** chunk sizes are multiples of 0x38 (so the "array of
  0x38-byte records" claim stays retracted), `NMY`'s "`u16` size + NUL name"
  walk consumes **0/9** chunks, and `GNMY`'s `u16` size + `u16` type walk holds
  on **104/104** chunks (3,593 entries). `docs/file-formats.md` §2.5–2.6 and the
  Q23/Q24 open questions were corrected to these numbers.
- `lomax-modern wld roundtrip [--check]` — re-parses every `WORLDS/*.WLD` file
  (a single file, or the whole folder via `LOMAX_GAME_DIR`/`--game-dir`),
  re-emits it in memory and reports per-file `identical`/`DIFFERENT` without
  ever printing payload bytes or a digest. `--check` exits non-zero on the
  first mismatch. `python -m lomax_modern` now works via a new `__main__.py`.
- Local-only game-data layout: `scripts/new_game_folder.sh` creates one slot per
  repository outside every git working tree, and `.gitignore` covers
  `game-files/`, `gamedata/`, `GAMES/` as a second line of defence.
- **`ANIM`/`NMY` framings recovered from `LOMAX.EXE` (LMX-11)** — `lomax_modern.anim_nmy`
  plus `lomax-modern anim-nmy`, which decodes and validates the recovered sprite and
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
- **Renderer (M4) — 16-bit blit**: `lomax_modern.renderer`, the own-engine
  renderer, plus a C99 core in `native/`:
  - a 16-bit `B5G6R5` `Framebuffer` with palette lookup and the cell/tile blit
    path from decoded `CELL`/`TTAB`, honouring transparency (index 0 leaves the
    destination pixel untouched, so the key colour never leaks);
  - `rgb15_to_rgb565` — the 15-bit `HEAD` palette widened to `B5G6R5` (green
    5→6 by bit replication, `[H]`) with its inverse for round-tripping;
  - `blit_map_field` — the raw `MAP` byte drawn as greyscale, because the
    map→tile art link is still unresolved (Q20); no art is invented;
  - `fade_surface_width` — the fade/dissolve surface rule `⌈w/32⌉·32`, the
    ceiling we own and will lift at M9;
  - `native/` reproduces the palette/blit/fade path bit-for-bit in C99, built
    only in CI (`make -C native`), with a headless smoke binary asserting the
    same golden `B5G6R5` words the Python oracle grades;
  - 34 unit tests over synthetic fixtures, including the hand-derived golden
    frame (transparent key never painted, green 5→6 expansion pinned).
- **Presenter CLI (M4)**: `lomax-modern present <game_dir>` — the engine frame
  through the presentation layer, with the config file written on first run:
  - `config.py` — versioned, validated JSON (`modern`, `filter`, `surface`,
    `scale`) at the platform config path (`--config` / `$LOMAX_CONFIG`
    override). Modern defaults are 1920x1080, `epx-aa`, auto integer scale;
    authentic is a whole profile (`--authentic`: native 320x240, `nearest`).
    Flags apply to one run; `--save` persists the effective settings.
  - `install.py` — the P5 gate: a file-by-file manifest (names, counts, sizes;
    no contents, no digests). Required: `LOMAX.EXE` and `WORLDS/` with at least
    one `*.WLD`. Expected: `SFX/`, `AMBIENT/`, `JINGLES/`, `DEMOS/`, reported as
    incomplete but non-fatal. Name case is ignored and exactly one level of
    nested install (retail folder copied inside the slot) is resolved.
  - `presenter.py` — one plan (source size, surface, integer fit, filter) and
    one call to `scaler.present`; a pinned scale that does not fit is refused
    with the largest integer fit instead of being silently shrunk.
  - `present --frame out.png` writes the padded surface with the stdlib PNG
    writer. There is no window in this build (the Win32 presenter remains
    future), and the frame is the engine's geometric frame: the `MAP`→`TTAB`
    art link (Q20) is still unresolved, so no art is invented to fill it.
  - `engine.run_slice` accepts an explicit world path, so a resolved install
    with lower-case folder names runs without renaming the user's files.
  - 79 unit tests over synthetic installs and frames: first-run config, schema
    rejection, modern/authentic resolution, `--save` persistence, manifest
    refusal, nested and case-insensitive layouts, runtime filter change (the
    written frame differs), and scale refusal.
- **Conformance harness (M4)**: `lomax_modern.conformance` +
  `python -m lomax_modern.conformance` — renders synthetic scenes (own cells,
  own palettes, deliberate index-0 holes) through the renderer and asserts the
  output pixels:
  - **depth 16 vs 24**: the same scene rendered as a 16-bit `B5G6R5` frame and
    as an independent `RGB888` reference that shares no blit code, compared with
    a tolerance *measured* by enumerating all 32,768 15-bit words — red and blue
    must match exactly, green may differ by at most 2/255 (its 5→6→5 round
    trip);
  - **transparency**: every index-0 source pixel must still show the background
    at both depths, and the transparent key colour must appear nowhere in the
    frame (the fixture rejects an ambiguous palette, so the assertion is not
    vacuous);
  - **no shimmer at integer scale**: every source pixel becomes a uniform
    `k x k` block, a one-source-pixel scroll moves the output by exactly `k`
    pixels, and a 2.5x surface applies 2x with integer pads;
  - headless by construction (no display, window, GPU, `LOMAX.EXE` or game data)
    and run as its own CI step; 31 unit tests, including negative cases that
    hand the harness a truncated green channel, a key-colour leak, a placement
    offset and a fractional-scale presentation and require it to fail.
- **Runbook + data manifest (M2/M7, docs only)**: `docs/runbook.md`, linked from
  the README, takes a new user from `pip install` to `lomax-modern present` with
  only their own unpacked game directory:
  - the Q29 manifest in full — which entries are **required** (`LOMAX.EXE`
    presence, `WORLDS/` with ≥1 `*.WLD`) and which are **expected but
    non-fatal** (`SFX/`, `AMBIENT/`, `JINGLES/`, `DEMOS/`, `GAME.TXT`), with
    which of them the engine actually reads today (only `WORLDS/*.WLD`), plus
    the case-insensitivity and one-level-nesting rules;
  - install, run, the modern-defaults/authentic toggle and the config-file
    reference (location per platform, keys, `--save`, unknown-key rejection);
  - an honest controls section: **no interactive input in this build** (the
    engine runs a scripted input for `--ticks`; keyboard/pad is M5/v0.7) — no
    invented key bindings;
  - an honest audio section: **there is no music track** (the PC build's music
    was CD audio; the installed data holds 67 SFX, 12 ambient loops and 3
    jingles → 82 WAVs), nothing bundled, downloaded or extracted;
  - the missing-data behaviour (required vs expected verdicts, exit codes, typo
    and nesting cases) and the platform/packaging status (Linux AppImage +
    Windows `.exe` at M7/v0.8, macOS deferred, no store).
- `docs/development.md` — the local game-data layout now has **one** slot, an
  unpacked install; the disc-image slot is gone, since an unpacked directory is
  the project's only input.
- **Measurement (2026-11-18)**: the `MAP` collision byte is near-uniform over
  all 256 values across the 104 retail planes (`0x00` 81–95 % by world, `0x01`
  the clear second in playable worlds) — retracting the `[D]` "`0x80` solid /
  `0xC0` one-way" bit-field and filing the byte's true semantics as **Q31**.

### Fixed

- `renderer.Framebuffer.to_rgba()` over-brightened green: the 6-bit channel was
  widened with `g<<2 | g>>2` instead of the bit-replicating `g<<2 | g>>4`, which
  changes 55 of the 64 green values — over-brightens 46 by up to 12/255, under-brightens 9 by up to 3/255. The expansion now lives in
  `renderer.rgb565_to_rgb8()` (5-bit red/blue `r<<3 | r>>2`, 6-bit green
  `g<<2 | g>>4`) and is pinned by pixel tests; found by the new depth 16 vs 24
  conformance harness.
- `engine.render.unpack_rgb565` had the same over-brightened green (it feeds
  `frame_to_rgba()`, i.e. every PNG the engine frame writes); now widened by bit
  replication too, matching `renderer.rgb565_to_rgb8`.
- `lomax-modern present` and `lomax-modern slice` no longer dump a traceback on
  a `*.WLD` that is not a world container: the `WLDParseError` is caught and
  reported as `error: cannot read <name>: offset …` with exit 1.

### Notes

- Format claims are graded V/D/H in `docs/file-formats.md`: the chunk container,
  `HEAD` dimensions, `MAP` cell math, `CELL` sizing, the audio formats and the
  `ANIM`/`NMY`/`GNMY` framings are verified against the retail install; `TTAB`
  internals (cell order, flag semantics) remain documented or hypothetical.
- The engine core (M3) is a Python reference simulation: a playable first world
  at the original 60 Hz, drawing a geometric frame from decoded `CELL`/`TTAB`/
  `MAP` data. The tile-art blit, palette transparency and the fade rule ship in
  `renderer.py` (+ C99 `native/`); scaling and filters stay in `scaler.py`.
  Composing them into the engine frame, entity/spawn placement (Q23) and the
  map→tile link (Q20) remain for the synthesis card.

## [0.1.0] - 2026-11-16

Initial research-phase scaffold.
