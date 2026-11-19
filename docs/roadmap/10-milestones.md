# 10. Milestones

Staged plan, M0…M11. Each milestone states its goal, observable exit criteria
(things a reviewer can *run* or *open*, not promises), dependencies, what is
explicitly out of scope, and an effort estimate in agent-days with a confidence
level. Companion documents: [`00-research-plan.md`](00-research-plan.md),
[`15-strategy-report.md`](15-strategy-report.md),
[`20-releases.md`](20-releases.md), [`30-risks.md`](30-risks.md),
[`40-budget.md`](40-budget.md).

> **Revision v1** (LMX-7/WP-6 synthesis, 2026-11-17). The five research packages
> WP-1…WP-5 have landed; this revision folds their findings into M1–M7 exit
> criteria. The mechanism decision (ddraw proxy), the 512 px-ceiling answer, the
> Wine compat matrix and the tooling gaps below are now *evidence*, not
> hypotheses. Contradictions between packages and what remains unknown are
> itemised in ["Synthesis notes"](#synthesis-notes) at the end and in
> [`../research/05-open-questions.md`](../research/05-open-questions.md).

> **Revision v2** (LMX-9/M2, 2026-11-18). The M2 target-host decision is
> **resolved: disc-less users.** We do not run `LOMAX.EXE`, so the clean-room
> `ddraw.dll` proxy is demoted to an optional disc-owner appendix
> ([`15-strategy-report.md`](15-strategy-report.md)) and the spine is re-cut:
> **data layer → engine core → presenter → input → audio → packaging**, with the
> surviving tooling milestones (asset pipeline, password, level editor, 2× spike)
> renumbered behind it. Milestones that were removed or renumbered are named
> under [Dependency graph](#dependency-graph).

Confidence legend: **high** (the work is data/prose and the path is known),
**medium** (real build work with a known fallback), **low** (spike; may be
abandoned).

## Table of contents

- [M0 — Roadmap published and research dispatched](#m0--roadmap-published-and-research-dispatched)
- [M1 — Platform & patching strategy settled](#m1--platform--patching-strategy-settled)
- [M2 — Data-layer completeness](#m2--data-layer-completeness)
- [M3 — Engine core](#m3--engine-core)
- [M4 — Presenter (own renderer, integer scaling, filters)](#m4--presenter-own-renderer-integer-scaling-filters)
- [M5 — Controller & input](#m5--controller--input)
- [M6 — Audio (ambience + jingles + SFX)](#m6--audio-ambience--jingles--sfx)
- [M7 — Packaging](#m7--packaging)
- [M8 — Asset pipeline: upscaler + pack writer](#m8--asset-pipeline-upscaler--pack-writer)
- [M9 — 2× internal-render spike (go/no-go)](#m9--2-internal-render-spike-gono-go)
- [M10 — Password tool](#m10--password-tool)
- [M11 — Long tail: level editor + translation](#m11--long-tail-level-editor--translation)
- [Dependency graph](#dependency-graph)
- [Synthesis notes](#synthesis-notes)

---

## M0 — Roadmap published and research dispatched

- **Goal.** Turn the research corpus (docs 01–06) into a reviewed, costed roadmap
  and dispatch the research packages to the board.
- **Exit criteria (observable).** The `docs/roadmap/` set exists and its relative
  links resolve; the one-page answer and mechanism decision are in
  [`00-research-plan.md`](00-research-plan.md); the five research cards + one
  synthesis card are on the board.
- **Dependencies.** None. **Out of scope.** Engine source, patches, game data,
  `main` pushes, upstream PRs.
- **Effort.** Incurred. **Confidence:** high.

## M1 — Platform & patching strategy settled

> **Status: research complete.** WP-1 (patching surface), WP-2 (display path) and
> WP-4 (runtime & distribution) landed this card; their findings *are* this
> milestone's deliverable. **The deliverable is the strategy report:**
> [`15-strategy-report.md`](15-strategy-report.md) — the single artefact that
> states the target host and the hook mechanism without re-running the
> experiments. What remains open is recorded in
> [`../research/05-open-questions.md`](../research/05-open-questions.md).

- **Goal.** Decide the target host and the mechanism, from evidence rather than
  preference.
- **Exit criteria (observable) — now settled evidence.**
  - **Compat matrix (WP-4).** The four blockers resolve as: **B1** colour-depth
    gate is a GDI query (`GetDC(NULL)` + `GetDeviceCaps(BITSPIXEL)×GetDeviceCaps(PLANES)`,
    compared to 8/16 at `0x40799c`, fatal dialog at `0x462be0`) — cleared only by
    a genuinely 16-bpp display, a GDI-level hook (DxWnd), or Lomax+'s patch;
    dgVoodoo 2 and DXVK **cannot** clear it. **B2** missing 320×240 mode is
    `IDirectDraw::SetDisplayMode` (vtable method). **B3** CD check is MCI
    `cdaudio` — a **disc problem, not a Wine problem**. **B4** MFC start order is
    an artefact of injection-based loaders, not of the game.
  - **Target-host decision (v2, resolved).** For **disc-less** users, B1 + B3
    close the exe path entirely, so the target host is **our own engine +
    presenter over the MIT data layer** — never Wine + `LOMAX.EXE`. The
    `ddraw.dll` proxy survives only as an optional disc-owner appendix
    ([`15-strategy-report.md`](15-strategy-report.md) §5, §8).
  - **Mechanism (WP-1 → WP-2).** For disc owners: a clean-room `ddraw.dll` proxy
    — lighter forward-everything hook at the final `Blt`/`Flip`, *not* a full
    DXVK-style translator. For the main line, the mechanism is the data layer →
    engine → presenter chain (M2–M4), which hooks nothing.
  - **512 px ceiling (WP-2).** Renderer-side: fade/dissolve surface rounded to a
    multiple of 32, plus 199 hard-coded width sites; **not** a data limit (plane
    widths reach 7,200 px). Because the own engine *owns* the renderer, this
    ceiling is ours to lift (M9), not a patch target.
  - **First-run recipe (WP-4).** Fedora/Nobara 44, 16-bpp `Xephyr :2 -screen
    640x480x16`, `wineboot`, the user's own disc, plus probes P1/P2/P3 — kept as
    the disc-owner appendix, marked unverified at runtime.
- **Dependencies.** M0. **Out of scope.** Shipping the engine (M2–M4); any
  CD-check handling beyond describing it.
- **Effort.** Incurred. **Confidence:** high.

## M2 — Data-layer completeness

- **Goal.** Every data container the own engine will read is parsed (and, where a
  writer exists, round-tripped) byte-exactly: the `.WLD` chunk container, `CELL`/
  `TTAB`/`MAP`, palettes (`HEAD`), `ANIM`/`NMY`/`GNMY`, sprites, and audio —
  closing the WP-3 gap list **G1–G15** as the backlog
  ([`../research/07-wp3-asset-pipeline.md`](../research/07-wp3-asset-pipeline.md)
  §2). This is the LMX-5 foundation the target-host decision rests on.
- **Exit criteria (observable).**
  - `read → write` reproduces every shipped world file bit for bit. **The
    round-trip falsifier is already closed** (WP-3/WP-5): structural re-emit is
    byte-identical in 9/9 files, the semantic `MAP` rebuild (3·cells + zero pad
    to 4) is byte-exact 104/104, and the `size & ~3` rule never fires
    (1,041/1,041 chunks already 4-aligned).
  - `TTAB`/`CELL`/`MAP` decode correctly (`TTAB` V(structure): 8-byte records,
    four big-endian `u16`, 13-bit index + `0x2000`/`0x4000` flags) and a tile/
    sprite exporter writes recognisable sheets with palette + transparency.
  - `ANIM`/`NMY` are **retracted-as-stated and re-probed**: the falsified layouts
    (`ANIM` 0x38 records, `NMY` `u16`-size + NUL-name walk) are marked `retracted`
    in [`../file-formats.md`](../file-formats.md), and a structural probe reports
    what *is* there (token stream / variable-length records) — never a guessed
    layout. The `MAP`-cell → `TTAB`-record link prints `unresolved` until found.
  - The audio reader loads the 82 RIFF/WAVE files (22,050 Hz 16-bit mono, Q7):
    67 SFX, 12 ambient loops (6 worlds × a stereo `_L`/`_R` pair), 3 jingles.
  - `file-formats.md` grades the flip **bit pair** `H → V` (bits 13–14, Q21) for
    the confirmed layouts, keeps the **axis pairing** at `H` (Q33 — no render
    compared against the game), and marks the falsified `D` claims `retracted`.
- **Dependencies.** M1. **Out of scope.** The engine itself (M3); 2× art (M8);
  redistributing exported art (never).
- **Effort.** 6–10 agent-days (the chunk container and `TTAB` are confirmed; the
  `ANIM`/`NMY`/`MAP`-link unknowns are priced via the round-trip falsifier and
  the "unresolved" rule). **Confidence:** high.

## M3 — Engine core

- **Goal.** Reproduce the game from the data — map + collision + entities +
  timing, driven by the 60 Hz tick — as a **vertical slice**: the first world
  fully playable end to end (spawn → move → collide → collect → exit → next
  level), before any second world is touched.
- **Exit criteria (observable).**
  - The first world is fully playable end to end with keyboard input at the
    original logic rate.
  - The frame is drawn to a 16-bit `B5G6R5` framebuffer from the decoded
    `CELL`/`TTAB`/`MAP`, honouring the renderer facts of the strategy report
    (§6: 60 Hz tick, fade `⌈w/32⌉·32`).
  - The 8 attract demos replay tick-for-tick at the original camera width — the
    `DEMOS/*.DAT` format (Q6) must be decoded enough to feed this, or the
    milestone records why it cannot.
- **Dependencies.** M2. **Out of scope.** Pixel-art filters and borderless
  presentation (M4); audio (M6); controller (M5).
- **Effort.** 15–25 agent-days. **Confidence:** medium (the vertical slice is
  the unfamiliar core; M2 removes the format risk first).

## M4 — Presenter (own renderer, integer scaling, filters)

- **Goal.** Our own renderer presents the frame, defaulting to the **modern
  experience** — widescreen, 60 fps (or unlocked), smooth integer scaling, save
  states — with an *authentic* toggle as the escape hatch
  ([`15-strategy-report.md`](15-strategy-report.md) §7). Native 320×240
  integer-scaled ships first; HD internal render is M9.
- **Exit criteria (observable).**
  - `lomax-modern present` renders the engine's frame at 4K borderless with
    correct aspect, no shimmer, no transparency regression, and game SFX —
    **modern defaults on, authentic toggle off** by default.
  - A filter is switchable at runtime (nearest vs xBRZ/MMPX) and the choice is
    visible in a side-by-side screenshot (no game bytes committed).
  - Unit tests: the scaling/filter code is pure and covered; the renderer's
    blit/palette path is covered by synthetic-fixture tests
    ([`architecture.md` §5](../architecture.md#5-future-components-and-where-they-sit)).
  - CI smoke: a headless render-conformance harness renders a synthetic scene and
    asserts pixels at depth 16 vs 24, proving the renderer's colour handling
    without the game.
- **Dependencies.** M3. **Out of scope.** Controller (M5), music (M6),
  2× art (M8/M9).
- **Effort.** 8–14 agent-days. **Confidence:** medium.

## M5 — Controller & input

- **Goal.** Keyboard first, then a modern gamepad: analogue movement + buttons,
  d-pad menu navigation, hot-plug, per-controller presets (Xbox, DualSense,
  generic), generous input handling (rebinding) — via our own input layer
  (evdev/XInput), not a `dinput.dll` proxy. Our own save states ship here
  alongside the password system (both ways).
- **Why here.** Input is the most user-visible "pleasant to play" change after
  the picture stops misbehaving (M4). The exe's two input paths
  (`DINPUT.dll!DirectInputCreateA` and `WINMM.dll!joyGetPosEx`, WP-1) are no
  longer hooks — our engine reads the device directly.
- **Exit criteria (observable).** Keyboard plays the vertical slice end to end;
  a DualSense **and** an Xbox pad both move Lomax and navigate menus, surviving
  hot-plug; save states round-trip; the mapping layer has unit tests
  (XInput/evdev → game action) that run without a pad attached.
- **Dependencies.** M3 (a playable engine). **Out of scope.** Rumble, PS1
  parity.
- **Effort.** 4–7 agent-days. **Confidence:** medium.

## M6 — Audio (ambience + jingles + SFX)

- **Goal.** Play the on-disk audio: the ambient L/R pair as the per-world bed,
  jingles on transitions, SFX as-is. There is **no music track** (the soundtrack
  was CD-DA on the disc) — no ripping, no bundled audio.
- **Exit criteria (observable).** The 82 WAVs (67 SFX, 12 ambient loops, 3
  jingles — 22,050 Hz 16-bit mono) play in-engine at the right moments; the
  runbook states plainly that there is no music. An optional user-supplied music
  folder is a later possibility, not v0.1.
- **Dependencies.** M2 (audio reader) and M3 (timing). **Out of scope.**
  Redistributing any audio; synthesising a soundtrack.
- **Effort.** 1–3 agent-days. **Confidence:** high.

## M7 — Packaging

- **Goal.** A launcher/installer that ships **only our MIT code** and loads the
  user's data directory — no game bytes, no Wine, no closed DLLs. **Platforms:
  Linux (AppImage) and Windows (`.exe`) now; macOS deferred; no store presence.**
- **Exit criteria (observable).** A Linux AppImage and a Windows `.exe` both run
  on a clean machine pointed at the user's data directory, failing loudly
  (file-by-file manifest, P5) when data is missing.
- **Dependencies.** M4, M5, M6. **Out of scope.** Bundling Wine, the game, or
  any data.
- **Effort.** 2–4 agent-days. **Confidence:** medium.

## M8 — Asset pipeline: upscaler + pack writer

- **Goal.** A matte-aware 2× upscaler (LMX-8) and a 2× pack writer (LMX-9) that
  transform the user's own files, with backup and refuse-if-no-round-trip.
- **Exit criteria (observable).** Comparison sheets at 2× show no key-colour
  bleed and no broken transparency on ≥20 tiles and ≥10 sprites; the writer
  refuses to touch a file it cannot round-trip, and a backup path is exercised in
  a test.
- **2× representability (WP-3).** Only one container-legal design exists: **(a)
  one cell stays one cell at 256 B** (`CELL` 958,336 → 3,833,344 B, `TTAB`
  unchanged, worlds ~9.98 MB). Four-cells-per-2×-cell overflows the 13-bit index
  and **must not** be planned. 2× **sprites** stay blocked on the `ANIM` layout
  (M2).
- **Dependencies.** M2. **Out of scope.** Shipping upscaled art; the 2× render
  hook (M9).
- **Effort.** 8–14 agent-days. **Confidence:** medium.

## M9 — 2× internal-render spike (go/no-go)

- **Goal.** Prove or disprove a 2× internal framebuffer with 2× art, now that we
  own the renderer (the 512 px ceiling is a code limit we wrote, not a patch
  target).
- **Exit criteria (observable).** One level renders at 640x480 with 2× art, or
  the spike publishes why not; the 8 attract demos replay tick-for-tick at the
  original camera width; the failure modes are written down.
- **Dependencies.** M3 (engine) and M8 (art). **Out of scope.** Shipping it.
- **Effort.** 10–20 agent-days. **Confidence:** low (a spike with a kill
  criterion: "more than viewport + tile + sprite + fade" means stop and publish).

## M10 — Password tool

- **Goal.** A correct password word codec (LMX-7) from the documented layout, so
  password-based progress is usable with tooling and preserved by the engine
  (P4).
- **Exit criteria (observable).** `lomax-modern password` round-trips (encode →
  decode is identity) with unit tests; the field widths are consistent
  (5+5+2+4 = 16 bits), but the checksum function, bit order and gem alphabet are
  unknown — so v1 decodes under both candidate bit orders and **refuses to
  generate** until the checksum is known. In-game verification is recorded as
  blocked, not answered by analogy.
- **Dependencies.** None (independent). **Out of scope.** Save files (none
  exist); any change to the game.
- **Effort.** 1–2 agent-days for the codec. **Confidence:** high.

## M11 — Long tail: level editor + translation

- **Goal.** A level editor (LMX-11) and translation support (LMX-12) on top of
  the toolkit.
- **Exit criteria (observable).** The editor round-trips a level and re-emits a
  file the engine loads; a translated `GAME.TXT` loads with correct encoding.
- **Dependencies and unknowns.** M2. The placement falsifier is **blocked on the
  `NMY` framing** (WP-5: 0/104) and the editor also needs `MACR`/`PAGE` decoded
  (Q26). Translation (`GAME.TXT`) is independent.
- **Out of scope.** A full game remake; PS1 parity.
- **Effort.** 20–40 agent-days. **Confidence:** medium.

## Dependency graph

```
M0 ──► M1 ──► M2 ──► M3 ──► M4 ──► M5 ─┐
  │            │        │              ├──► M7 (packaging)
  │            │        └──► M6 ───────┘
  │            ├──► M8 ──► M9
  │            ├──► M10
  │            └──► M11
```

M1, M10 and (once M2 lands) M8/M11 are parallelisable. M3 depends on M2; M4 on
M3; M5 on M3; M6 on M2+M3; M7 on M4+M5+M6; M9 on M3+M8.

**Removed or renumbered by the v2 re-cut:**

| v1 milestone | v2 outcome |
|---|---|
| M2 open-source presenter (ddraw proxy) | **removed as the main line**; its presenter half re-scoped to the own renderer (now **M4**), its `ddraw.dll` proxy demoted to the disc-owner appendix ([`15-strategy-report.md`](15-strategy-report.md)) |
| M3 controller (dinput proxy) | **renumbered M5**, re-scoped to our own input layer |
| M4 `.WLD` toolkit + exporter | **renumbered M2**, broadened to full data-layer completeness |
| M5 password tool | **renumbered M10** |
| M6 asset pipeline | **renumbered M8** |
| M7 2× spike | **renumbered M9** |
| M8 level editor + translation | **renumbered M11** |
| — | **new: M3 engine core, M6 audio, M7 packaging** |

## Synthesis notes

**Contradictions between packages, and which evidence won.**

1. **`TTAB` framing — WP-5 rev 1 said "unknown", WP-3 said V(structure).**
   *Resolved: V(structure).* WP-5 re-ran WP-3's structural checks and agrees:
   104/104 payloads divisible by 8, 300,488 words = 4 × 75,122 records, and the
   index-range vote 1,644 (`0x1FFF`) vs 18,147 (`0x3FFF`) vs 19,930 (bare).
2. **Mechanism vs target host — WP-1/WP-2 "ddraw proxy" vs WP-4 "own engine".**
   *Resolved by the human (2026-11-18), not left as a contradiction.* They
   answered different questions: WP-1/WP-2 settled the *mechanism for disc
   owners* (ddraw proxy — retained as an appendix), WP-4 settled the *target
   host* (B1+B3 close the exe path to disc-less users). The human chose
   disc-less, so the main line is the own engine and the proxy is demoted.
3. **`TTAB` flag counts disagree** — WP-3 (`0x2000` 15,787 / `0x4000` 1,783) vs
   WP-5 (16,503 / 2,499). *Unresolved unit discrepancy* (Q27); agree a unit
   before these numbers enter `file-formats.md`.
4. **Distinct 13-bit indices** — WP-3 14,861 vs WP-5 14,862. *Summation-boundary
   delta of 1*; this document uses 14,862 (the per-file sum).

**What remains unknown** (full list and resolution methods in
[`../research/05-open-questions.md`](../research/05-open-questions.md)): the
`MAP`-cell → `TTAB`-record link, `TTAB` flag semantics, the `BONUS.WLD`
index-256 anomaly, the `ANIM` record layout, the `NMY` framing, `MACR`/`PAGE`
layout, the password checksum / bit order / gem alphabet, the data manifest
(Q29), the music-without-CD source (Q30), and — appendix-track only — the
runtime behaviour of the Wine recipe (Q15–Q19).
