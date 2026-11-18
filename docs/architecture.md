# Architecture

## 1. Purpose

This repository has two deliverables with a strict separation:

| Layer | Contents | Runs where |
|---|---|---|
| **Research** | `docs/research/*` | read by humans |
| **Read-only tooling** | `src/lomax_modern/` | the user's machine, against the user's own copy |

There is deliberately no C/loader layer yet. The engine core (M3) is a
dependency-free Python reference simulation in this package; the renderer (M4)
ships the same way — a Python reference (`renderer.py`, the oracle) plus a
C99 core in `native/` that reproduces it bit-for-bit and is built in CI only.
The C/Win32 *presenter* (window + surface) is still a separate future
component, because this package stays dependency-free Python.

## 2. The clean-room boundary

The most detailed public source on this game is an **unlicensed** project
(`Lomax+`, all rights reserved). Facts are not copyrightable; expression is.
This repository therefore enforces:

**Allowed**

- Memory addresses, struct offsets, constants, magic values, documented chunk
  layouts and observed behaviour, **with citation** (`[S#]` →
  `docs/research/sources.md`).
- Independent re-derivation of numbers from cited facts (marked `[derived]`).
- Interoperating with that project's *output files* (e.g. reading a `MUSIC`
  folder it created), without linking to or copying its code.

**Not allowed**

- Copying code, comments, doc prose, naming schemes or table contents from an
  unlicensed project.
- Linking against its `LOADER.DLL`, or shipping its `minhook` copy.
- Vendoring its documentation into this repository.

Practically: our scanner was written from a *description* of the chunk order
plus our own plausibility rules; it does not reproduce any upstream function.
Where a future component needs the same technique (import patching, MinHook),
it will be written from public API documentation, and the file will say so.

## 3. Module layout

```
src/lomax_modern/
  __init__.py     version
  cli.py          argparse entry point (doctor, wldscan, measure, export, wld, slice)
  doctor.py       install inventory: presence, counts, sizes, SHA-256
  wld.py          .WLD chunk parser/writer (byte-exact round trip)
  wldscan.py      chunk/tag scanner with hypothesis ranking
  measure.py      read-only probes: chunk sequence, plane widths, audio, text
  art.py          TTAB/CELL/MAP decode + palette + PNG sheets (data layer)
  png.py          stdlib-only PNG writer
  scaler.py       integer scalers, pixel-art filter, integer fit + padding
  renderer.py     M4 renderer: 16-bit B5G6R5 blit, palette, transparency, fade
  engine/         engine core (M3): map/collision, 60 Hz tick, entities, frame
    level.py      Level + CollisionModel + load_level
    entities.py   Player, Input, Collectible, Exit, physics constants
    state.py      GameState, tick, save-state Snapshot, capture/restore
    render.py     16-bit B5G6R5 Frame, camera, collision-layer frame
    run.py        headless vertical-slice runner + report
native/           the C99 hot-path port of renderer.py (CI-only, not at install)
  renderer.c/.h   B5G6R5 palette/blit/fade, bit-for-bit vs renderer.py
  smoke.c         headless golden smoke test (same words test_renderer.py grades)
  Makefile        builds and runs the smoke binary
tests/
  fixtures/synth.py     synthetic chunk containers (no game data)
  unit/                 scanner, inventory, probe, scaler, renderer, art, engine
  integration/          opt-in, needs LOMAX_GAME_DIR
```

### The scaler is the specification, the presenter is the port

`scaler.py` is the pure part of the M4 presentation layer: buffers in, buffers
out, no window, no I/O, no compiler, no third-party code. The presenter itself
is C (`native/`, §5), so this module is written to be **reproduced bit-for-bit**
— integer-only arithmetic, no floating point, and one documented rule set — and
it is what the unit tests grade.

Three decisions are load-bearing:

- **Integer factors only.** A non-integer factor makes some source pixels wider
  than others and the widths move as the camera scrolls; that is the shimmer
  analysed in `docs/research/02-resolution.md` §2.3. `fit_scale` returns the
  largest integer scale that fits and refuses when none does, rather than
  silently stretching one axis.
- **The pad strategy is explicit.** Both axes share one factor (aspect is
  preserved by construction, never by two different stretches), the content is
  centred, and the odd pad pixel goes to the right and bottom — `Fit` reports
  `offset_x`/`offset_y` and all four pads so a caller never guesses.
- **Index space is not colour space.** In `RGB565` a filter corner blends in
  5/6/5 units. In `INDEXED8` a palette index cannot be averaged, so a corner is
  an index **copy**, and the transparent key (index 0 in this game) is never
  painted into a sprite: that would bite a hole out of the edge instead of
  smoothing it.

The filter is named for what it implements, not for what it resembles:
`epx-aa` is the published Scale2x/EPX corner rule plus fractional coverage.
xBRZ's reference implementation is GPL and this package is MIT, and MMPX was
not re-derived from a source we can cite, so neither was copied. Swapping in a
bit-exact xBRZ or MMPX later is a drop-in behind `Filter`, with
`tests/unit/test_scaler.py` as the contract.

### Why the scanner ranks hypotheses instead of assuming one

`docs/file-formats.md` §2.2 lists four unknowns in an 8-byte header (tag order,
endianness, size semantics, tag padding). Guessing wrong produces plausible
offsets that are silently off by four bytes — the worst failure mode for format
work. The scanner enumerates the plausible combinations, scores each by how
cleanly the chain reaches EOF with known tags, and refuses to decode payloads
until a real file resolves the ambiguity.

### `doctor` never reads content

It reports which expected files exist, how many files and bytes each folder
holds, and the SHA-256 of the executable — never file contents. This keeps game
bytes out of logs, bug reports and CI output. A unit test asserts that a string
written into `GAME.TXT` never appears in the report.

## 4. Data flow

```
user's install ──> doctor ──> inventory report (sizes, hashes, completeness)
                 └> wldscan ─> chunk table (tags, offsets) ──> research docs
                 └> wld/art ─> decoded TTAB/CELL/MAP ──> engine ──> 16-bit frame
```

All paths are read-only; none writes to the game folder. Fixtures used in
tests are generated by `tests/fixtures/synth.py` at test time.

### The engine core is a reference simulation, not the presenter

`engine/` (M3) loads a world through `wld` + `art` and advances a fixed 60 Hz
tick (input, gravity, axis-separated collision, collect, exit) to a 16-bit
`B5G6R5` frame. It is deliberately the *logic* half only:

- **Collision is a labelled hypothesis.** The `MAP` collision byte's per-value
  semantics are unresolved (Q31), so `CollisionModel` uses only the measured
  0-vs-non-zero rule, flags it `[H]` in its report, and preserves every byte
  verbatim — a future decode plugs in without losing data.
- **The frame is geometric.** It draws the collision grid and entity markers at
  native 320x240. The tile-art blit, palette transparency and the fade rule
  are the M4 renderer card's job, and they now ship in `renderer.py` (oracle)
  + `native/` (C99); scaling and filters stay in `scaler.py`. Composing the
  art blit into the engine frame — and resolving the map→tile link (Q20) — is
  the synthesis card's job, not invented here.
- **Entity placement is deferred.** Spawn, collectibles and exit are explicit
  (placeholder) in the slice; the real placements live in `GNMY`, whose record
  semantics are unresolved (Q23). The map→tile link (Q20) is likewise flagged,
  not invented.

## 5. Future components and where they sit

| Component | Language | Boundary |
|---|---|---|
| `WLD` reader/writer (LMX-5) | Python | shipped in `lomax_modern.wld`, byte-exact round trip verified |
| Exporter (LMX-6) | Python | shipped in `lomax_modern.art` + `lomax-modern export` |
| **Engine core (M3)** | Python | shipped in `lomax_modern.engine`; reference simulation, not the presenter |
| **Renderer (M4)** | Python reference + C core | `renderer.py` is the oracle; `native/` (C99) reproduces it bit-for-bit and is built in CI only; `scaler.py` grades the presentation half |
| Upscaler (LMX-8) | Python + NumPy | index-space only; output is never committed |
| 2x render spike (LMX-10) | C (Win32) | separate spike branch, may be abandoned |

The Python package must never grow a dependency that requires a compiler, a GPU
or network access. Tools that do belong in `native/`.

## 6. Failure policy

- Unknown layout → report, do not parse.
- Ambiguous hypothesis → say so in output and in tests.
- Missing game files → skip integration tests, never fail the build.
- Anything that would write into the game folder → requires an explicit backup
  path and a refuse-if-no-round-trip rule.
