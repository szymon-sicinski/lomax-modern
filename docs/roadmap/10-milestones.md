# 10. Milestones

Staged plan, M0…M8. Each milestone states its goal, observable exit criteria
(things a reviewer can *run* or *open*, not promises), dependencies, what is
explicitly out of scope, and an effort estimate in agent-days with a confidence
level. Companion documents: [`00-research-plan.md`](00-research-plan.md),
[`20-releases.md`](20-releases.md), [`30-risks.md`](30-risks.md),
[`40-budget.md`](40-budget.md).

> **Revision v1** (LMX-7/WP-6 synthesis, 2026-11-17). The five research packages
> WP-1…WP-5 have landed; this revision folds their findings into M1–M7 exit
> criteria. The mechanism decision (ddraw proxy), the 512 px-ceiling answer, the
> Wine compat matrix and the tooling gaps below are now *evidence*, not
> hypotheses. Contradictions between packages and what remains unknown are
> itemised in ["Synthesis notes"](#synthesis-notes) at the end and in
> [`../research/05-open-questions.md`](../research/05-open-questions.md).

Confidence legend: **high** (the work is data/prose and the path is known),
**medium** (real build work with a known fallback), **low** (spike; may be
abandoned).

## Table of contents

- [M0 — Roadmap published and research dispatched](#m0--roadmap-published-and-research-dispatched)
- [M1 — Platform & patching strategy settled](#m1--platform--patching-strategy-settled)
- [M2 — Open-source presenter (L1)](#m2--open-source-presenter-l1)
- [M3 — Controller & input](#m3--controller--input)
- [M4 — `.WLD` toolkit + exporter](#m4--wld-toolkit--exporter)
- [M5 — Password tool](#m5--password-tool)
- [M6 — Asset pipeline: upscaler + pack writer](#m6--asset-pipeline-upscaler--pack-writer)
- [M7 — 2× internal-render spike (go/no-go)](#m7--2-internal-render-spike-gono-go)
- [M8 — Long tail: level editor + translation](#m8--long-tail-level-editor--translation)
- [Dependency graph](#dependency-graph)
- [Synthesis notes](#synthesis-notes)

---

## M0 — Roadmap published and research dispatched

- **Goal.** Turn the research corpus (docs 01–06) into a reviewed, costed roadmap
  and dispatch the research packages to the board.
- **Exit criteria (observable).**
  - `docs/roadmap/00-research-plan.md`, `10-milestones.md`, `20-releases.md`,
    `30-risks.md`, `40-budget.md` exist and their relative links resolve
    (link-check loop exits 0).
  - `git diff --stat main...HEAD` shows only `docs/roadmap/**` and (at most) one
    line in `docs/research/README.md`.
  - `python -m pytest tests -m "not realgame" -q` reports the unchanged pass
    count (28).
  - One PR open against `main`; CI green (Python 3.10–3.13 matrix).
  - Five research cards + one synthesis card created on `retrolab`, each with the
    four-block body (Goal / Acceptance / Verify / Constraints).
- **Dependencies.** None (this card). Uses everything in docs 01–06 as input.
- **Out of scope.** Engine source, patches, build changes, game data, `main`
  pushes, upstream PRs.
- **Effort.** 1 agent-day. **Confidence:** high (it is the card in progress).

## M1 — Platform & patching strategy settled

> **Status: research complete.** WP-1 (patching surface), WP-2 (display path) and
> WP-4 (runtime & distribution) landed this card; their findings *are* this
> milestone's deliverable. What remains open is recorded in
> [`../research/05-open-questions.md`](../research/05-open-questions.md).

- **Goal.** Decide the target host (Wine/Proton vs native vs shim) and the hook
  mechanism, from evidence rather than preference.
- **Exit criteria (observable) — now settled evidence.**
  - **Compat matrix (WP-4).** The four blockers resolve as: **B1** colour-depth
    gate is a GDI query (`GetDC(NULL)` + `GetDeviceCaps(BITSPIXEL)×GetDeviceCaps(PLANES)`,
    compared to 8/16 at `0x40799c`, fatal dialog at `0x462be0`) — cleared only by
    a genuinely 16-bpp display, a GDI-level hook (DxWnd), or Lomax+'s patch;
    dgVoodoo 2 and DXVK **cannot** clear it. **B2** missing 320×240 mode is
    `IDirectDraw::SetDisplayMode` (vtable method) — cleared by dgVoodoo 2/DxWnd
    surface emulation or Wine ≥10 `EmulateModeset` (padded/scaled, not native).
    **B3** CD check is MCI `cdaudio` (`open cdaudio`, `status cdaudio length
    track %d` in the binary) — a **disc problem, not a Wine problem**; survives
    everywhere except Lomax+. **B4** MFC start order is an artefact of
    injection-based loaders, not of the game — stock-under-Wine never meets it.
  - **First-run recipe (WP-4).** Fedora/Nobara 44, package set *verified* in the
    sandbox (`wine 11.21`, `wine-core`, `xorg-x11-server-Xephyr 21.1.26`): a
    16-bpp `Xephyr :2 -screen 640x480x16` clears B1, `wineboot` once, then the
    user's own disc (or CDEmu-backed image) satisfies B3. Runtime behaviour is
    **unverified here** (no Wine/display in the sandbox) — the recipe ships with
    three one-line probes (P1/P2/P3) for whoever has Wine.
  - **Injection recipe (WP-1).** `LOMAX.EXE` imports `DDRAW.dll` for exactly one
    function — `DirectDrawCreate` — so the entire surface/present path runs
    through the returned COM vtables. The safe injection point is the game's own
    main thread at the first `DirectDrawCreate`, after `AfxWinInit`/CTL3D; a
    dropped-in proxy satisfies this *by construction*.
  - **512 px ceiling (WP-2).** Renderer-side, two named causes, no single check:
    the fade/dissolve surface rounded to a multiple of 32, and the 199 hard-coded
    width sites. It is **not** a data limit (plane widths reach 7,200 px). The
    fade constraint binds only the widescreen *renderer*, not a presentation-only
    shim. Q2's exact cause stays `blocked` (unproven).
  - **Mechanism choice (WP-1 → WP-2).** A clean-room **`ddraw.dll` proxy wins**;
    refined to a **lighter forward-everything proxy with a hook at the final
    `Blt`/`Flip`** — *not* a full DXVK-style translator. Recorded in
    [`00-research-plan.md` §4](00-research-plan.md#4-the-strategy-decision-three-mechanisms-one-winner).
  - **New split this synthesis records.** The GDI depth gate (B1) is *not*
    reachable by the ddraw proxy; it needs a GDI-side hook, a depth-16 X server,
    or a (documented-only) exe patch. The proxy can present a 16-bit surface and
    neutralise `SetDisplayMode`, but it cannot sidestep B1 alone. This changes
    M2's scope, below.
- **Dependencies.** M0 (cards dispatched). **Out of scope.** Shipping the
  presenter (M2); re-implementing widescreen (L2); any CD-check handling beyond
  describing it.
- **Effort.** Incurred (three parallel research cards). **Confidence:** high.

## M2 — Open-source presenter (L1)

- **Goal.** The stock game plus our shim renders borderless, integer-scaled, with
  at least one selectable pixel-art filter, on Linux/Proton (and Windows).
- **Mechanism (confirmed).** A clean-room **`ddraw.dll` proxy** that exports
  `DirectDrawCreate`, forwards to the real backend, and wraps the returned
  `IDirectDraw`/`IDirectDrawSurface(7)` vtables to hook the **final
  `Blt`/`Flip`** — own the 16-bit primary surface, scale/filter, present via a
  modern backend. Everything else forwards. **Not** a full DXVK-style translator
  (that is only justified by render-path work, M6/M7).
- **Exit criteria (observable).**
  - `lomax-modern present` (or the dropped-in `ddraw.dll` proxy) launches the
    user's own `LOMAX.EXE` under Wine and presents a 4K borderless frame with
    correct aspect, no shimmer, no transparency regression, and game SFX.
  - **The 8/16-bpp GDI gate is cleared** by one of the documented routes — a
    GDI-side hook, a depth-16 X display (Xephyr/Xvfb), or the documented-only exe
    patch — because the proxy alone cannot (WP-2). The conformance oracle is
    Wine + Xephyr-at-depth-16; disc owners use their own disc for B3.
  - A filter is switchable at runtime (nearest vs xBRZ/MMPX) and the choice is
    visible in a side-by-side screenshot (no game bytes committed).
  - Unit tests: the scaling/filter code is pure and covered; the DLL proxy is
    built in CI only (per
    [`architecture.md` §5](../architecture.md#5-future-components-and-where-they-sit)).
  - CI smoke: the `ddrawprobe` Win32 probe (WP-4 §7) built with mingw and run
    under `xvfb-run` at depth 16 vs 24, proving the B1/B2 mechanics headlessly.
- **Scope decision to record (target host).** The ddraw-proxy path serves **disc
  owners** (the CD check B3 is satisfied by their own disc). A **disc-less**
  modern user is blocked under Wine by B3 and by B1, so the licence-clean path
  for them is *our own engine + presenter over the MIT data layer* (WP-4 §8).
  Whether to scope M2 to disc owners only, or to grow it into an own-engine
  presenter, is an **open decision for the human**
  ([`30-risks.md`](30-risks.md#open-decisions-for-the-human)) — it is a scope and
  budget fork, not a mechanism change.
- **Dependencies.** M1.
- **Out of scope.** Widescreen (L2), true-HD art (L3/M7), controller remapping
  (M3), CD-music replacement, anything that writes into the game folder, and (as
  above) the own-engine fork until the human decides.
- **Effort.** 12–20 agent-days for the disc-owner proxy (the lighter hook is
  cheaper than a full shim, but the GDI-gate handling adds a component); the
  own-engine fork is materially larger and unpriced until decided. **Confidence:**
  medium.

## M3 — Controller & input

- **Goal.** Let a modern gamepad drive the stock game, via a clean-room
  `dinput.dll` proxy that translates XInput (Windows) / evdev (Linux) into the
  DirectInput calls the game already makes. No `LOMAX.EXE` patch.
- **Why here, not earlier or later.** Earlier is impossible: a working pad is
  worthless while the display path still fights the user (fullscreen/colour-depth
  handling), so M3 is hard-gated on M2. Later is wrong: this is a platformer, so
  a pad is the single most user-visible "pleasant to play" change after the
  picture stops misbehaving, and the route is cheap because it reuses the exact
  DLL-proxy mechanism WP-1/M2 establish for display — `DirectInputCreateA` is
  intercepted the same way `DirectDrawCreate` is. It slots immediately after M2,
  ahead of the asset/tooling work (M4+) which a player does not feel directly.
- **Scope — what "controller support" means.**
  - Analogue movement + buttons mapped to the documented input sites.
  - D-pad navigation of the in-game menus.
  - Hot-plug (pad connected mid-session).
  - Per-controller mapping presets (Xbox, DualSense, generic).
  - **Rumble is out of scope** — the PC build has no force-feedback API in its
    documented surface; it is deferred, not forgotten.
- **Route.** The measured fact that `LOMAX.EXE` imports `DINPUT.dll`
  (`DirectInputCreateA`, the only DINPUT import — WP-1) means the cheapest path
  is a `dinput.dll` proxy — the same import-table-hook shape as the display
  proxy, so the distribution form (a dropped-in DLL next to the user's own
  files) and the legal posture are identical. WP-1 also measured a **second**
  input path — `WINMM.dll!joyGetPosEx`, the legacy joystick poller — so the
  mapping layer must be aware of both (the proxy intercepts DirectInput; the
  WINMM path is noted, and if it proves live in the 320×240 mode it is a second
  hook, not a blocker). A binary patch at the input sites loses (edits the exe,
  version-fragile); Steam Input / an external wrapper loses as *our* product (it
  outsources the feature to a proprietary runtime) — it remains valid user-side
  advice in the README. Prior art: `Lomax+` advertises controller support
  `[S3]` `[S5]`; we cite that as a fact, never as code.
- **Exit criteria (observable).**
  - A DualSense **and** an Xbox pad both move Lomax, navigate the menus, and
    survive hot-plug, verified by playtest on the target distro.
  - The mapping layer has unit tests (XInput/evdev → DirectInput translation)
    that run without a pad attached.
- **Dependencies.** M2 (display stable) and M1 (mechanism). The `dinput.dll`
  proxy is a separate DLL from the presenter's `ddraw.dll` — independent install.
- **Out of scope.** Rumble, an in-game rebinding UI (presets only), PS1 parity.
- **Effort.** 5–8 agent-days. **Confidence:** medium (same proxy technique as M2,
  already de-risked; the new surface is the input-event translation, plus the
  measured joyGetPosEx path).

## M4 — `.WLD` toolkit + exporter

- **Goal.** A byte-exact `.WLD` reader/writer (LMX-5) plus a tile/sprite PNG
  exporter (LMX-6), fully distributable.
- **Exit criteria (observable).**
  - `read → write` reproduces every shipped world file bit for bit (`cmp` clean
    on all 9 files in the user's install). **The round-trip falsifier is already
    closed** (WP-3/WP-5): structural re-emit is byte-identical in 9/9 files, a
    semantic `MAP` rebuild (3·cells + zero pad to 4) is byte-exact 104/104, and
    the `size & ~3` rule never fires (1,041/1,041 chunks already 4-aligned; the
    pad sits *inside* the declared size). WP-5 prototyped the skeleton
    (`wldrebuild.py`, 12 synthetic-fixture tests passing) — this is the M4
    starting point.
  - `TTAB`/`CELL`/`MAP` decode correctly. `TTAB` framing is now **V(structure)**
    (WP-3, re-verified by WP-5): 8-byte records, four big-endian `u16` cell
    indices per 16×16 tile, a 13-bit index plus flags `0x2000`/`0x4000`
    (mask `0x1FFF`: 1,644 of 300,488 words out of range, all in `BONUS.WLD`).
    An exporter writes recognisable tile/sprite sheets with palette and
    transparency mask for the `CELL`/`TTAB`/`MAP` decode; `ANIM`/`NMY` export is
    **blocked** (their layouts are falsified-as-stated, see below).
  - Synthetic-fixture and negative tests pass; a round-trip test asserts
    bytes-in == bytes-out before any real file is touched.
  - `file-formats.md` grades flip **H → V** for the layouts that got confirmed
    (`TTAB` structure), and the two falsified `D` claims (`ANIM` 0x38-record
    arrays, `NMY` `u16`-size + NUL-name walk) are marked `retracted`.
- **Tooling gaps this milestone closes (WP-5 priority order).** (1) `WLD` rebuild
  skeleton [prototyped] → (2) `measure --tiles` (answers Q9 for cells: 14,862 of
  14,974 cells referenced, 112 unreferenced) → (3) `password` word codec → (4)
  `gnmy --check` coherence probe. The `MAP`-cell → `TTAB`-record link is
  **unknown** (three disagreeing counts: 43,612 distinct map words vs 75,122
  records vs 14,862 distinct indices; `byte0 & 0x7F` saturates at 127) — the
  exporter must print `map cell → tile record: unresolved`, never a guessed
  unique-tile count.
- **Dependencies.** M0 (and WP-3/WP-5 findings).
- **Out of scope.** Writing 2× art (M6), engine hooks (M7), redistributing
  exported art (never).
- **Effort.** 6–10 agent-days. **Confidence:** high (the chunk container and
  `TTAB` structure are confirmed; the open risks — `ANIM`, `NMY`, `MAP` link,
  the `BONUS.WLD` index-256 anomaly — are priced in via the round-trip falsifier
  and the "unresolved" reporting rule).

## M5 — Password tool

- **Goal.** A correct password encoder/decoder (LMX-7) from the documented
  layout, so the game's password-only progress is usable with tooling.
- **Exit criteria (observable).**
  - `lomax-modern password` round-trips (encode → decode is the identity) with
    unit tests over the documented bit layout.
  - **Scope narrowed by WP-5:** the field widths are consistent (5+5+2+4 = 16
    bits = 8×2 gems), but the **checksum function, field bit order, and gem
    alphabet are unknown** — so v1 ships a *word codec* only: decode the
    canonical 16-bit word under both candidate bit orders (printed side by
    side), re-encode with the checksum nibble preserved, and **refuse to
    generate** a password until the checksum function is known. Gem-symbol I/O
    is a second step gated on the alphabet.
  - One generated password is verified in the real game — **blocked here** (no
    display/game run); recorded as blocked, not answered by analogy.
- **Dependencies.** M0.
- **Out of scope.** Save files (none exist), any change to the game.
- **Effort.** 1–2 agent-days for the codec. **Confidence:** high for the codec
  structure (arithmetic-consistent, `[S2]`-documented); the in-game verification
  is blocked, which the exit criteria state explicitly.

## M6 — Asset pipeline: upscaler + pack writer

- **Goal.** A matte-aware 2× upscaler (LMX-8) and a 2× pack writer (LMX-9) that
  transform the user's own files, with backup and refuse-if-no-round-trip.
- **Exit criteria (observable).**
  - Comparison sheets at 2× show no key-colour bleed and no broken transparency
    on ≥20 representative tiles and ≥10 sprites (the LMX-8 done-criterion).
  - The game starts with a 2× pack installed and at least one level renders
    without visual artefacts.
  - The writer refuses to touch a file it cannot round-trip, and a backup path
    is exercised in a test.
- **2× representability (WP-3).** 2× art is **container-permissive but
  engine-blocked**: no format field records geometry (`HEAD` payload is a
  constant 5,240 B in 104/104, a `CELL` is an unlabelled 64 B record, a `TTAB`
  entry is 8 B of indices). The only container-legal design is **(a) one cell
  stays one cell at 256 B** — `CELL` grows 958,336 → 3,833,344 B, `TTAB` is
  unchanged, worlds go 7.1 MB → ~9.98 MB (+40 %). Design **(b) four cells per 2×
  cell** overflows the 13-bit index (`MEDIEVAL` 19,636 > 8,192) and **must not
  be planned**. 2× **sprites** are blocked at the format level until the `ANIM`
  layout lands; making the game *display* 2× art is an engine patch (a
  render-scale hook), not the pipeline's job.
- **Dependencies.** M4.
- **Out of scope.** Shipping any upscaled art (derivative of copyrighted assets
  — the generator ships, the output stays on the user's disk); the 2× render
  hook (M7).
- **Effort.** 8–14 agent-days. **Confidence:** medium (the matte-aware scaler is
  pure data work; the pack writer's risk is the unverified `ANIM`/`NMY` layout
  and the `MAP` link, which the "unresolved" rule keeps from leaking).

## M7 — 2× internal-render spike (go/no-go)

- **Goal.** Prove or disprove that a 2× internal framebuffer with 2× art is
  achievable by patching only viewport + tile + sprite + fade (LMX-10).
- **Exit criteria (observable).**
  - One level renders at 640x480 with 2× art, or the spike publishes why not.
  - The 8 attract demos still replay identically (tick-for-tick) at the original
    camera width.
  - The failure modes and the "what would have to change" list are written down.
- **Findings that frame the spike (WP-2).** The 512 px ceiling is renderer-side,
  so widening means re-deriving the fade multiple-of-32 and the 199 width sites —
  not a data change. The Direct3D 3 execute-buffer path (0x5624-byte buffer,
  128-quad budget, `CreateExecuteBuffer` at `0x407545`) is **render-side, not
  present-side**: for 2× it scales the quad *extents*, while the quad *count*
  (and budget) does not grow. The fade rule must be re-applied at the widened
  width (`⌈w/32⌉·32`).
- **Dependencies.** M6 (art) and M1 (hook mechanism).
- **Out of scope.** Shipping it; turning it into a full reimplementation.
- **Effort.** 15–25 agent-days. **Confidence:** low (it is a spike; the kill
  criterion is "if it needs more than viewport + tile + sprite + fade patching,
  stop and publish the findings").

## M8 — Long tail: level editor + translation

- **Goal.** A level editor (LMX-11) and translation support (LMX-12) on top of
  the toolkit.
- **Exit criteria (observable).**
  - The editor round-trips a level (map + collision + placements) and re-emits a
    file the game loads.
  - A translation of `GAME.TXT` loads and renders in-game with correct encoding.
- **Dependencies and unknowns.** M4. The level editor's placement falsifier
  ("can a Start/Exit pair round-trip") is **blocked on the `NMY` framing**
  (WP-5: no candidate framing consumes a whole chunk, 0/104), which also blocks
  the `GNMY` index→name mapping. `MACR`/`PAGE` chunks (7 each, 24–968 B and
  1,092–40,344 B) are wholly undocumented and need decoding for an editor.
  Translation (`GAME.TXT`) is independent of these.
- **Out of scope.** A full game remake; PS1 parity.
- **Effort.** 20–40 agent-days. **Confidence:** medium (the toolkit part is
  proven; the editor is gated on `NMY`/`MACR`/`PAGE` decoding).

## Dependency graph

```
M0 ──► M1 ──► M2 ──► M3
  │
  ├──► M4 ──► M6 ──► M7
  │        └─► M8
  └──► M5
```

M1, M4 and M5 are parallelisable once M0 lands (M1 is now complete). M3 depends
on M2; M7 depends on both M1 and M6; M8 depends only on M4.

## Synthesis notes

**Contradictions between packages, and which evidence won.**

1. **`TTAB` framing — WP-5 rev 1 said "unknown", WP-3 said V(structure).**
   *Resolved: V(structure).* WP-5's "unknown" was an argument from a missing
   arithmetic anchor (no relation between a plane's `TTAB` size and its `MAP`
   word count holds), which a per-plane *bank* of tile records does not need.
   WP-5 re-ran WP-3's structural checks independently and agrees: 104/104
   payloads divisible by 8, 300,488 words = 4 × 75,122 records, and the
   index-range vote 1,644 (mask `0x1FFF`) vs 18,147 (`0x3FFF`) vs 19,930 (bare).
   WP-5's "framing unknown" conclusion is withdrawn.
2. **Mechanism vs target host — WP-1/WP-2 "ddraw proxy" vs WP-4 "own engine over
   the data layer".** *Reconciled, not a real conflict.* They answer different
   questions: WP-1/WP-2 settle the *mechanism* (ddraw proxy, lighter final
   `Blt`/`Flip` hook), which is confirmed; WP-4 settles the *target host* and
   found the CD check (B3, a disc problem) and the GDI gate (B1) together block a
   disc-less user under Wine, so the licence-clean path for that user is our own
   engine + presenter over the data layer. The two are recorded as M2's mechanism
   vs its target-host **open decision**, not as a contradiction.
3. **`TTAB` flag counts disagree** — WP-3 reports `0x2000` on 15,787 words and
   `0x4000` on 1,783; WP-5 reports 16,503 and 2,499. *Unresolved unit
   discrepancy* (per-record vs per-word counting, likely with `BONUS.WLD`
   excluded). One agreed unit must be chosen before these numbers enter
   `file-formats.md`; recorded in
   [`../research/05-open-questions.md`](../research/05-open-questions.md).
4. **Distinct 13-bit indices** — WP-3 counts 14,861, WP-5 counts 14,862 (summed
   per file). *Summation-boundary delta of 1*; this document uses 14,862 (the
   per-file sum) and notes the delta.

**What remains unknown** (full list and resolution methods in
[`../research/05-open-questions.md`](../research/05-open-questions.md)): the
`MAP`-cell → `TTAB`-record link, `TTAB` flag semantics, the `BONUS.WLD`
index-256 anomaly, the `ANIM` record layout, the `NMY` framing, `MACR`/`PAGE`
layout, the password checksum function / bit order / gem alphabet, the runtime
behaviour of the Wine recipe (Q15–Q19), and the M2 target-host scope decision.
