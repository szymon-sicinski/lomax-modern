# 10. Milestones

Staged plan, M0…M8. Each milestone states its goal, observable exit criteria
(things a reviewer can *run* or *open*, not promises), dependencies, what is
explicitly out of scope, and an effort estimate in agent-days with a confidence
level. Companion documents: [`00-research-plan.md`](00-research-plan.md),
[`20-releases.md`](20-releases.md), [`30-risks.md`](30-risks.md),
[`40-budget.md`](40-budget.md).

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

- **Goal.** Decide the target host (Wine/Proton vs native vs shim) and the hook
  mechanism, from evidence rather than preference.
- **Exit criteria (observable).**
  - A compat matrix `(stock game, dgVoodoo/DxWnd, Lomax+) × (Wine version, DXVK,
    virtual desktop)` documenting which of the four blockers fires in each cell.
  - A first-run recipe for at least one Linux distro with game SFX and no
    graphical corruption (the LMX-3 done-criterion).
  - A written, reproducible injection recipe naming the DirectDraw call sequence
    a proxy must intercept and the MFC startup constraint (WP-1).
  - A written answer to "where does the 512 px ceiling live" and whether the
    fade/multiple-of-32 constraint affects a presentation-only shim (WP-2).
  - A confirmed choice of mechanism (DLL proxy vs app-level filter) recorded in
    `00-research-plan.md` §4, or an explicit refutation with evidence.
- **Dependencies.** M0 (cards dispatched).
- **Out of scope.** Shipping the presenter (that is M2); re-implementing
  widescreen (L2); any CD-check handling beyond describing it.
- **Effort.** ≈1 agent-day across three parallel research cards. **Confidence:**
  high (desk research + a Wine install; the game binary and its imports are
  already partly measured).

## M2 — Open-source presenter (L1)

- **Goal.** The stock game plus our shim renders borderless, integer-scaled, with
  at least one selectable pixel-art filter, on Linux/Proton (and Windows).
- **Exit criteria (observable).**
  - `lomax-modern present` (or the dropped-in `ddraw.dll` proxy) launches the
    user's own `LOMAX.EXE` under Wine and presents a 4K borderless frame.
  - A playtest on one distro shows correct aspect, no shimmer, no transparency
    regression, and game SFX.
  - A filter is switchable at runtime (e.g. nearest vs xBRZ/MMPX) and the choice
    is visible in a side-by-side screenshot (no game bytes committed).
  - Unit tests: the scaling/filter code is pure and covered; the DLL proxy is
    built in CI only (per [`architecture.md` §5](../architecture.md#5-future-components-and-where-they-sit)).
- **Dependencies.** M1.
- **Out of scope.** Widescreen (L2), true-HD art (L3/M7), controller remapping
  (that is M3), CD-music replacement, anything that writes into the game folder.
- **Effort.** 12–20 agent-days. **Confidence:** medium (the technique is known;
  the fragile part is DLL-shim behaviour under Wine, which is exactly what M1
  de-risks).

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
  ([`06-measurements-and-improvements.md`](../research/06-measurements-and-improvements.md#64-q1q14))
  means the cheapest path is a `dinput.dll` proxy — the same import-table-hook
  shape as the display proxy, so the distribution form (a dropped-in DLL next to
  the user's own files) and the legal posture are identical. A binary patch at
  the input sites loses (edits the exe, version-fragile); Steam Input / an
  external wrapper loses as *our* product (it outsources the feature to a
  proprietary runtime) — it remains valid user-side advice in the README.
  Prior art: `Lomax+` advertises controller support `[S3]` `[S5]`; we cite that
  as a fact, never as code.
- **Exit criteria (observable).**
  - A DualSense **and** an Xbox pad both move Lomax, navigate the menus, and
    survive hot-plug, verified by playtest on the target distro.
  - The mapping layer has unit tests (XInput/evdev → DirectInput translation)
    that run without a pad attached.
- **Dependencies.** M2 (display stable) and M1 (mechanism).
- **Out of scope.** Rumble, an in-game rebinding UI (presets only), PS1 parity.
- **Effort.** 5–8 agent-days. **Confidence:** medium (same proxy technique as M2,
  already de-risked; the new surface is the input-event translation).

## M4 — `.WLD` toolkit + exporter

- **Goal.** A byte-exact `.WLD` reader/writer (LMX-5) plus a tile/sprite PNG
  exporter (LMX-6), fully distributable.
- **Exit criteria (observable).**
  - `read → write` reproduces every shipped world file bit for bit
    (`cmp` clean on all 9 files in the user's install), and the game loads the
    rebuilt file.
  - `TTAB`/`CELL`/`MAP` decode correctly; an exporter writes recognisable tile
    and sprite sheets with palette and transparency mask, and the inventory
    totals match the chunk sizes.
  - Synthetic-fixture and negative tests pass; a round-trip test asserts
    bytes-in == bytes-out before any real file is touched.
  - `file-formats.md` grades flip **H → V** for the layouts that get confirmed,
    each with its evidence line.
- **Dependencies.** M0 (and WP-3/WP-5 findings).
- **Out of scope.** Writing 2× art (M6), engine hooks (M7), redistributing
  exported art (never).
- **Effort.** 6–10 agent-days. **Confidence:** high (the chunk container is
  confirmed; the open risk is `TTAB`/`ANIM`, priced in via the round-trip
  falsifier).

## M5 — Password tool

- **Goal.** A correct password encoder/decoder (LMX-7) from the documented
  layout, so the game's password-only progress is usable with tooling.
- **Exit criteria (observable).**
  - `lomax-modern password` round-trips (encode → decode is the identity) with
    unit tests over the documented bit layout.
  - One generated password is verified in the real game.
- **Dependencies.** M0.
- **Out of scope.** Save files (none exist), any change to the game.
- **Effort.** 1–2 agent-days. **Confidence:** high (algorithm is documented
  behaviour reimplemented from facts `[S2]`).

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
- **Dependencies.** M4.
- **Out of scope.** Shipping any upscaled art (derivative of copyrighted assets
  — the generator ships, the output stays on the user's disk); the 2× render
  hook (M7).
- **Effort.** 8–14 agent-days. **Confidence:** medium (the matte-aware scaler is
  pure data work; the pack writer's risk is the unverified `ANIM` layout).

## M7 — 2× internal-render spike (go/no-go)

- **Goal.** Prove or disprove that a 2× internal framebuffer with 2× art is
  achievable by patching only viewport + tile + sprite + fade (LMX-10).
- **Exit criteria (observable).**
  - One level renders at 640x480 with 2× art, or the spike publishes why not.
  - The 8 attract demos still replay identically (tick-for-tick) at the original
    camera width.
  - The failure modes and the "what would have to change" list are written down.
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
- **Dependencies.** M4.
- **Out of scope.** A full game remake; PS1 parity.
- **Effort.** 20–40 agent-days. **Confidence:** medium.

## Dependency graph

```
M0 ──► M1 ──► M2 ──► M3
  │
  ├──► M4 ──► M6 ──► M7
  │        └─► M8
  └──► M5
```

M1, M4 and M5 are parallelisable once M0 lands. M3 depends on M2; M7 depends on
both M1 and M6; M8 depends only on M4.
