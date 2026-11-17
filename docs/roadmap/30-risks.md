# 30. Risk register

Each risk has a likelihood and impact (H/M/L), a mitigation, and a **stop
trigger** — the observable signal that means "stop, escalate to a human, do not
keep building". The register is re-reviewed before every release; it is a
living list, not a one-off.

Companion documents: [`00-research-plan.md`](00-research-plan.md),
[`10-milestones.md`](10-milestones.md), [`20-releases.md`](20-releases.md).

## Table of contents

- [Technical](#technical)
  - [T1 — Fade-surface width must be a multiple of 32](#t1--fade-surface-width-must-be-a-multiple-of-32)
  - [T2 — 8-bpp desktop gate (GDI, not DirectDraw)](#t2--8-bpp-desktop-gate-gdi-not-directdraw)
  - [T3 — MFC startup ordering](#t3--mfc-startup-ordering)
  - [T4 — Direct3D 3 execute buffers](#t4--direct3d-3-execute-buffers)
- [Legal](#legal)
  - [L1 — No licence to `Lomax+`](#l1--no-licence-to-lomax)
  - [L2 — No game assets in the repository](#l2--no-game-assets-in-the-repository)
  - [L3 — The CD check must never be bypassed](#l3--the-cd-check-must-never-be-bypassed)
- [Product](#product)
  - [P1 — Scope creep into a rewrite](#p1--scope-creep-into-a-rewrite)
- [Open decisions for the human](#open-decisions-for-the-human)

---

## Technical

### T1 — Fade-surface width must be a multiple of 32

- **What.** The dissolve/fade transition forces surface widths up to the next
  multiple of 32 (`⌈w/32⌉·32`, e.g. 432 → 448) `[S3]`
  ([`02-resolution.md` §2.4](../research/02-resolution.md#24-layer-2--wider-framebuffer-how-wide-can-it-get)).
  WP-2 confirmed this is an **internal renderer surface**: a widescreen/2×
  *render* path that allocates a width that is *not* a multiple of 32 can
  corrupt the fade tiles, but a presentation-only shim sits after the finished
  frame and never touches it.
- **Likelihood.** H (it is a documented, measured constraint). **Impact.** M
  (visual corruption, not a crash, and confined to the render path).
- **Mitigation.** In any *render* change (widescreen L2, 2× spike M7), round
  surface widths up to a multiple of 32; encode the rule as a unit test
  (`fade_surface(w) == -(-w // 32) * 32`) and assert it in the 2× spike. The
  presenter (M2) is unaffected.
- **Stop trigger.** A width that violates the rule *and* passes tests — i.e. the
  constraint is found to be data/level-dependent rather than a fixed rule. Then
  stop and re-derive before touching the fade path.

### T2 — 8-bpp desktop gate (GDI, not DirectDraw)

- **What.** Windowed mode aborts unless the desktop is 8 or 16 bpp. WP-2/WP-4
  measured the mechanism: a **GDI** query — `USER32.GetDC(NULL)` +
  `GDI32.GetDeviceCaps(BITSPIXEL)×GetDeviceCaps(PLANES)` compared to 8/16 at
  `0x40799c`, with the fatal dialog `"Lomax will only run on 8 and 16 bit deep
  desktops."` at `0x462be0`. The community hex patch rewrites those bytes
  (`83 FD 08 74 1E 83 FD 10 74 19`) and regresses transparency `[S4]`
  ([`01-platform-assessment.md` §1.3](../research/01-platform-assessment.md#13-why-there-is-no-quick-just-run-it-answer)).
- **Likelihood.** H (reproduces on every modern system). **Impact.** H (the
  game will not start without handling it; a naive bypass regresses transparency).
- **Mitigation.** A `ddraw.dll` proxy **cannot** clear this gate — it is
  evaluated before `DirectDrawCreate`. It is cleared only by a genuinely 16-bpp
  display (Xephyr/Xvfb depth-16), a GDI-level hook (DxWnd's class of fix), or a
  documented-only exe patch. The presenter therefore pairs the ddraw proxy with
  one of those routes; the clean-room presentation path renders to 16-bit
  offscreen surfaces and converts at present, as the prior art does `[S3]` —
  reimplemented clean-room from the documented behaviour, not from its code.
- **Stop trigger.** If the only workable path under Wine turns out to require
  editing `LOMAX.EXE` in place, stop: that crosses into the non-goals
  ([`03-prior-art.md` §3.4](../research/03-prior-art.md#34-licensing-rules-this-project-follows))
  and needs a human decision.

### T3 — MFC startup ordering

- **What.** The MFC 4.2/common-controls/property-sheet initialisation breaks
  when the process is started "the wrong way round"; a loader must let the
  game's own thread reach the entry point before injecting `[S3]`
  ([`01-platform-assessment.md` §1.3](../research/01-platform-assessment.md#13-why-there-is-no-quick-just-run-it-answer)).
- **Likelihood.** M (known hazard, but the injection order is the fix).
  **Impact.** H (a wrong-order hook crashes the game before it draws).
- **Mitigation.** WP-1 documents the exact startup order and the safe injection
  point; the presenter's hook is built to that order and covered by a launch
  test, not left to a guess.
- **Stop trigger.** If the safe injection point is found to be loader-specific
  and unreproducible clean-room (i.e. every clean-room attempt crashes), stop
  and escalate — do not copy the prior art's code to make it work.

### T4 — Direct3D 3 execute buffers

- **What.** The optional D3D3 path emits scaled/rotated/translucent sprites from
  a fixed 0x5624-byte execute buffer with room for 128 quads `[S2]`
  ([`02-resolution.md` §2.2](../research/02-resolution.md#22-baseline-facts)).
  WP-2 confirmed it is **render-side, not present-side**: the frame is presented
  by a DirectDraw `Blt`; D3D3 only emits quads into that surface first
  (`CreateExecuteBuffer` call at `0x407545`, vtable index 6).
- **Likelihood.** L (presentation-only work does not need D3D3; it matters only
  for the 2× render spike). **Impact.** M (a buffer overrun corrupts the frame
  or crashes when the quad budget is exceeded).
- **Mitigation.** Keep the presenter on the DirectDraw `Blt` path and defer any
  D3D3 handling to the M7 spike; if the spike needs it, scale the quad *extents*
  (the quad *count*, and hence the 128-quad budget, does not grow — same object
  count) and bound/assert the count before submitting.
- **Stop trigger.** If 2× rendering requires growing the execute buffer beyond a
  documented, safe reallocation (i.e. patching D3D device state), stop the spike
  and publish findings — that is the LMX-10 kill criterion.

## Legal

### L1 — No licence to `Lomax+`

- **What.** `Lomax+` has no licence (`license: null` — all rights reserved); we
  may cite its *facts* (addresses, offsets, layouts, switch values) but never
  its code, comments or prose `[S5]`
  ([`03-prior-art.md` §3.2](../research/03-prior-art.md#32-lomax-in-detail)).
- **Likelihood.** H (the project is actively developed and unlicensed).
  **Impact.** H (copying it would make this repository legally non-distributable
  and kill the project).
- **Mitigation.** Enforce the clean-room boundary
  ([`architecture.md` §2](../architecture.md#2-the-clean-room-boundary)): facts
  with `[S#]` citations only; a review gate before any `native/` component
  merges; the `doctor`/`measure` tools already print hashes/sizes only.
- **Stop trigger.** Any proposed change that would require copying, linking or
  vendoring `Lomax+` code to function — stop and re-plan as an interoperability
  or re-derivation task, or escalate.

### L2 — No game assets in the repository

- **What.** `LOMAX.EXE`, `*.WLD`, sprites, palettes, audio and disc images must
  never enter the repo, tests, issues, CI logs or artifacts; even full hashes of
  copyrighted binaries are banned from logs.
  ([`03-prior-art.md` §3.4](../research/03-prior-art.md#34-licensing-rules-this-project-follows),
  [`file-formats.md` §9](../file-formats.md#9-rules-for-this-repository)).
- **Likelihood.** M (accidental inclusion is the risk, e.g. a stray `git add` or
  a fixture that embeds a real byte). **Impact.** H (a single committed asset
  makes the repo a redistribution of copyrighted work).
- **Mitigation.** Three-layer guard (sibling game-data tree outside every work
  tree, per-slot `.gitignore` of `*`, repo `.gitignore` covering the data
  extensions); synthetic fixtures only; `grep -rniE '[0-9a-f]{64}'` must be
  empty before push; mask hashes when quoting into chat.
- **Stop trigger.** Any game byte or 64-hex game hash detected in the working
  tree or a proposed diff — stop, remove it, and do not proceed until the guard
  passes.

### L3 — The CD check must never be bypassed

- **What.** `CD_VerifyLomaxDisc` compares track lengths against a table `[S3]`;
  the game needs the user's own disc/install. We may *describe* the check, never
  defeat it ([`03-prior-art.md` §3.4](../research/03-prior-art.md#34-licensing-rules-this-project-follows),
  [`05-open-questions.md`](../research/05-open-questions.md)).
- **Likelihood.** M (a "just make it run" pull request will tempt a bypass).
  **Impact.** H (a DRM-circumvention shipper is both a licence problem and an
  ethical/legal non-goal).
- **Mitigation.** The non-goal is stated in `03-prior-art.md`, `architecture.md`
  and this register; any strategy that *depends on* a bypass is rejected in
  review; the README directs users to their own disc.
- **Stop trigger.** Any card, PR or design whose acceptance depends on
  circumventing the CD check — reject it outright and record the rejection.

## Product

### P1 — Scope creep into a rewrite

- **What.** The temptation to "do it properly" by reimplementing the whole
  engine, which costs months and delivers no delta over the working
  (unlicensed) loader — and is exactly what the earlier research ruled out
  ([`02-resolution.md` §2.7](../research/02-resolution.md#27-recommendation)).
- **Likelihood.** M (rewrites are attractive). **Impact.** H (schedule blowout,
  no shippable result, loss of the "smallest change" thesis).
- **Mitigation.** The one-page answer in
  [`00-research-plan.md`](00-research-plan.md#1-the-one-page-answer) names the
  smallest change and the DLL-proxy winner; M6 is framed as a bounded spike with
  a kill criterion, not a rewrite; non-goals are listed in
  [`04-improvement-backlog.md`](../research/04-improvement-backlog.md).
- **Stop trigger.** A milestone's scope grows to touch gameplay/simulation
  logic beyond viewport + tile + sprite + fade (the M6 boundary) — stop and
  re-scope before continuing.

## Open decisions for the human

The following are written here rather than blocking the plan; each continues
under a stated assumption until the human decides:

1. **Target audience / legal posture.** Assumed: "hobbyist who owns a retail
   copy; ship only MIT code and tooling, never assets." If the human wants a
   different posture (e.g. a packaged disc-image workflow), re-open L3.
2. **Budget ceiling.** Assumed: part-time, off-peak agent effort; effort
   estimates in `10-milestones.md` are agent-days, not calendar-days.
3. **Whether to contact the `Lomax+` author** about a licence (Q12). Assumed:
   no contact for now; we stay interoperable, not derivative.
4. **M2 target host: disc owners vs disc-less users.** New from WP-4: the CD
   check (B3) is MCI `cdaudio` in the binary and blocks a disc-less user under
   Wine regardless of our shim, and the GDI gate (B1) is not reachable by a
   ddraw proxy. Assumed for now: M2 serves **disc owners** (their own disc
   satisfies B3); a **disc-less** user would need our own engine + presenter over
   the MIT data layer instead of running the retail exe. That is a scope and
   budget fork (re-opening the "reimplementation loses" verdict), so it is left
   to the human before M2 is costed — see [`10-milestones.md`](10-milestones.md#m2--open-source-presenter-l1)
   and [`40-budget.md`](40-budget.md).
