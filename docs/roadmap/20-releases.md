# 20. Releases

Releases v0.1…v1.0. Each lists its theme, contents (which milestones), a
definition of done, upgrade/compat notes, the distribution form, and what a user
must legally own. Companion documents: [`00-research-plan.md`](00-research-plan.md),
[`10-milestones.md`](10-milestones.md), [`30-risks.md`](30-risks.md), and
[`40-budget.md`](40-budget.md) (the token/cost model behind the "cost to date"
column below).

> **Revision v1** (LMX-7/WP-6 synthesis, 2026-11-17). v0.3–v0.9 contents now
> reflect the landed WP-1…WP-5 findings: the confirmed ddraw-proxy mechanism and
> the GDI-gate split (v0.3/v0.4), the closed round-trip falsifier and
> V(structure) `TTAB` (v0.6), the codec-only password scope (v0.7), the
> engine-blocked 2× constraint (v0.8), and the renderer-side 512 px ceiling
> (v0.9).

Versioning is [SemVer](https://semver.org/); everything before v1.0 is
pre-1.0 and may change incompatibly.

## Table of contents

- [v0.1 — Establish the premise (shipped)](#v01--establish-the-premise-shipped)
- [v0.2 — The plan (this PR)](#v02--the-plan-this-pr)
- [v0.3 — Strategy report](#v03--strategy-report)
- [v0.4 — Presenter (L1)](#v04--presenter-l1)
- [v0.5 — Controller](#v05--controller)
- [v0.6 — `.WLD` toolkit + exporter](#v06--wld-toolkit--exporter)
- [v0.7 — Password tool](#v07--password-tool)
- [v0.8 — Asset pipeline: upscaler + pack writer](#v08--asset-pipeline-upscaler--pack-writer)
- [v0.9 — 2× render spike verdict](#v09--2-render-spike-verdict)
- [v0.10 — Level editor + translation](#v010--level-editor--translation)
- [v1.0 — Modernised build](#v10--modernised-build)
- [Cost to date (cumulative)](#cost-to-date-cumulative)
- [Release ↔ milestone map](#release--milestone-map)

---

## v0.1 — Establish the premise (shipped)

- **Theme.** Prove what the game *is* and what can be improved, with numbers.
- **Contents.** Docs 01–06 (platform, resolution, prior art, backlog, open
  questions, measurements); read-only CLI `doctor` / `wldscan` / `measure`;
  CI matrix.
- **Definition of done.** Research published with citations; CLI read-only and
  dependency-free; 28 unit tests green.
- **Upgrade/compat notes.** N/A (first release).
- **Distribution form.** Source repository + `pip install lomax-modern`.
- **User must own.** Nothing beyond the tool (MIT); to *use* `doctor`/`wldscan`
  they need their own legal copy of the game, which the tool never contains.

## v0.2 — The plan (this PR)

- **Theme.** Turn research into a reviewed, costed roadmap and dispatch the work.
- **Contents.** M0: `docs/roadmap/` (this document set, incl. the budget) + the
  five research cards and one synthesis card on the board.
- **Definition of done.** All roadmap documents present with resolving relative
  links; the one-page answer and the mechanism decision are in
  `00-research-plan.md`; the risk register names the four technical blockers,
  the licence constraint and the CD-check prohibition; the PR is merged.
- **Upgrade/compat notes.** Docs only; no behaviour change.
- **Distribution form.** Source repository (docs).
- **User must own.** Nothing (no game bytes; no code change).

## v0.3 — Strategy report

- **Theme.** Settle "where it runs and how we hook it" from evidence.
- **Contents.** M1, now research-complete: the Wine/Proton compat matrix (B1 GDI
  colour gate, B2 missing 320×240 mode, B3 CD check, B4 MFC start order — and
  which wrapper clears which), the Fedora/Nobara first-run recipe (Wine 11.21 +
  Xephyr depth-16 + the user's own disc), the injection/startup-order findings
  (sole DDRAW import `DirectDrawCreate`, safe injection after `AfxWinInit`/CTL3D),
  and the confirmed mechanism choice: a clean-room **`ddraw.dll` proxy**, refined
  to a lighter forward-everything hook at the final `Blt`/`Flip` — *not* a full
  DXVK-style translator.
- **Definition of done.** A maintainer can read the report and know the target
  host and hook mechanism without re-doing the experiments; open questions
  (Q15–Q19) are filed in `05-open-questions.md`.
- **Upgrade/compat notes.** Docs + README guidance; no runtime artefact yet.
- **Distribution form.** Source repository (docs) + updated README.
- **User must own.** Nothing (prose only).

## v0.4 — Presenter (L1)

- **Theme.** "Pleasant on a 2026 Linux desktop today" — the display half.
- **Contents.** M2: the clean-room `ddraw.dll` proxy with integer scaling and at
  least one selectable pixel-art filter, for Windows and Linux/Proton. The proxy
  owns the 16-bit primary surface and hooks the final `Blt`/`Flip`; it presents
  a 16-bit frame and neutralises `SetDisplayMode`, but it **cannot clear the
  8/16-bpp GDI gate alone** — the release pairs it with a GDI-side hook or a
  depth-16 X display (the conformance oracle is Wine + Xephyr depth-16).
- **Definition of done.** Stock `LOMAX.EXE` + our shim runs borderless at 4K with
  correct aspect, no shimmer and no transparency regression, on one Linux distro
  and on Windows; filter switching is demonstrated; the CI `ddrawprobe` smoke
  test proves the B1/B2 mechanics headlessly; tests green.
- **Scope note.** This release serves **disc owners** (the CD check is satisfied
  by their own disc). Whether to also target **disc-less** users — which requires
  our own engine + presenter over the data layer rather than running the retail
  exe — is an open decision for the human (`30-risks.md`), and is a budget fork,
  not part of v0.4 by default.
- **Upgrade/compat notes.** The shim is version-independent (it does not patch
  the exe); Wine version constraints are documented from M1's matrix.
- **Distribution form.** **DLL proxy** (a dropped-in `ddraw.dll`, built in CI)
  plus an install script that copies it next to the user's own files. No game
  bytes.
- **User must own.** A legal copy of the game (retail `LOMAX.EXE` + data) and,
  for the CD check, their own disc. We ship only our MIT shim.

## v0.5 — Controller

- **Theme.** "Play it with a pad" — the input half of *pleasant*.
- **Contents.** M3: a clean-room `dinput.dll` proxy translating XInput/evdev to
  the game's DirectInput calls — analogue movement, buttons, d-pad menu
  navigation, hot-plug, per-controller presets. The mapping layer also accounts
  for the measured second input path (`WINMM.dll!joyGetPosEx`). Rumble deferred.
- **Definition of done.** A DualSense and an Xbox pad both move Lomax, navigate
  the menus, and survive hot-plug, verified by playtest on the target distro;
  the mapping layer has unit tests that run without a pad attached.
- **Upgrade/compat notes.** Ships as a second dropped-in DLL (`dinput.dll`) next
  to the presenter's `ddraw.dll`; the two are independent, so a controller-only
  or presenter-only install both work. Reuses the M1/M2 hook mechanism.
- **Distribution form.** **DLL proxy** (`dinput.dll`) alongside the presenter,
  in the same installer/zip. No game bytes.
- **User must own.** A legal copy of the game. We ship only our MIT proxy.

## v0.6 — `.WLD` toolkit + exporter

- **Theme.** "The asset pipeline begins."
- **Contents.** M4: `lomax_modern.wld` reader/writer with byte-exact round trip
  (the falsifier is already closed: structural re-emit 9/9, semantic `MAP`
  rebuild 104/104, `size & ~3` benign), tile/sprite PNG exporter for
  `CELL`/`TTAB`/`MAP`, the `measure --tiles` addition (14,862 of 14,974 cells
  referenced, 112 unreferenced), and the `H → V` promotion pass in
  `file-formats.md` (`TTAB` V(structure); `ANIM`/`NMY` claims retracted).
- **Definition of done.** `read → write` is bit-identical on all 9 world files;
  the exporter sheets are recognisable and the inventory totals match chunk
  sizes; the report prints `map cell → tile record: unresolved` (the link is
  unknown) rather than a guessed unique-tile count; round-trip and negative
  tests pass.
- **Upgrade/compat notes.** Read-only CLI semantics preserved; the new write
  path always backs up and refuses if it cannot round-trip. `ANIM`/`NMY` export
  is out of this release (their layouts are unverified).
- **Distribution form.** `pip install lomax-modern` (Python, dependency-free).
- **User must own.** A legal copy of the game; exported art stays on their disk
  (we never redistribute it).

## v0.7 — Password tool

- **Theme.** "Small win."
- **Contents.** M5: `lomax-modern password`, a 16-bit **word codec** — decode
  the documented 5+5+2+4 layout under both candidate bit orders, re-encode with
  the checksum nibble preserved, and refuse to generate until the checksum
  function is known. Gem-symbol I/O is deferred until the alphabet is
  established.
- **Definition of done.** Round-trips with unit tests over the full 65,536-word
  domain; in-game verification of a generated password is recorded as blocked,
  not claimed.
- **Upgrade/compat notes.** Additive CLI subcommand; no breaking change. A thin
  release — it may ride along with v0.6 or v0.8 if fewer releases are preferred.
- **Distribution form.** `pip install lomax-modern`.
- **User must own.** A legal copy of the game (to verify passwords).

## v0.8 — Asset pipeline: upscaler + pack writer

- **Theme.** "2× art, in-game."
- **Contents.** M6: the matte-aware 2× upscaler and the 2× pack writer that
  transforms the user's own `WORLDS/*.WLD` in place with backup, using the one
  container-legal design (one cell per cell at 256 B; `CELL` 958,336 →
  3,833,344 B, worlds ~9.98 MB). Four-cells-per-2×-cell is ruled out (13-bit
  index overflow).
- **Definition of done.** Comparison sheets show no key-colour bleed or
  transparency breakage on ≥20 tiles and ≥10 sprites; the game starts with a 2×
  pack installed and at least one level renders without artefacts; the
  backup/restore path is tested. (2× **sprites** stay blocked on the `ANIM`
  layout; making the game *display* 2× art is the M7 engine hook, not this
  release.)
- **Upgrade/compat notes.** The pack writer is a script + patch recipe, not a
  binary; it never ships upscaled art.
- **Distribution form.** **Mod package**: the generator + patch recipe in the
  repository; the user runs it against their own files.
- **User must own.** A legal copy of the game; the 2× output is a derivative of
  their copy's art and stays on their machine.

## v0.9 — 2× render spike verdict

- **Theme.** "True HD: the verdict."
- **Contents.** M7: the 2× internal-render proof-of-concept or the published
  findings that close it, now framed by the confirmed 512 px ceiling
  (renderer-side: fade multiple-of-32 + the 199 width sites) and the render-side
  D3D3 execute-buffer path.
- **Definition of done.** Either one level renders at 640x480 with 2× art and
  the demos replay identically, or the "why not + what would have to change"
  document is merged and the milestone is marked abandoned.
- **Upgrade/compat notes.** Spike output is a separate branch/tool; it does not
  alter the stable presenter, controller or toolkit.
- **Distribution form.** Source repository (research/spike code) — **patcher**
  recipe only if the spike succeeds and stays clean-room.
- **User must own.** A legal copy of the game.

## v0.10 — Level editor + translation

- **Theme.** "The modding story."
- **Contents.** M8: level editor (round-trips map/collision/placements) and
  `GAME.TXT` translation support. The editor's placement falsifier is gated on
  the `NMY` framing and `MACR`/`PAGE` decoding, which are unresolved; the
  translation half is independent and may ship earlier.
- **Definition of done.** The editor re-emits a level the game loads; a
  translated `GAME.TXT` renders in-game with correct encoding.
- **Upgrade/compat notes.** Built on the stable `wld` toolkit; editor files that
  embed original art remain derivative and non-redistributable.
- **Distribution form.** `pip install lomax-modern` (editor) + a translation
  recipe.
- **User must own.** A legal copy of the game.

## v1.0 — Modernised build

- **Theme.** Everything stable and documented: playable on Linux, asset pipeline
  open, optional 2× path behind its go/no-go.
- **Contents.** The stable union of M2, M3, M4, M5, M6 (+ M7 if it landed), M8 if
  ready, plus the integration/QA pass, with the risk register re-reviewed.
- **Definition of done.** A new user follows the README, installs the shim on
  Linux/Proton, launches their own copy, plays with a pad, switches filters,
  exports/inspects assets, and every tool's exit criteria still pass. No game
  bytes in the repo; CI green across the matrix.
- **Upgrade/compat notes.** A single documented upgrade path from v0.4 (shim)
  through v1.0; the shim and input proxy remain version-independent.
- **Distribution form.** **Installer** (the shim + input proxy + CLI) + the pip
  package + the mod-package generators; all MIT code, no assets.
- **User must own.** A legal copy of the game, always. We ship launchers and
  tooling, never the game itself.

## Cost to date (cumulative)

From [`40-budget.md`](40-budget.md): cumulative **expected** token spend and
cost at the two model rates, off-peak. Peak (01:00–04:00 and 06:00–10:00 UTC
Mon–Fri) is 2× these costs; the plan assumes off-peak execution. Tokens are
thousands.

| Release | Milestones | cum input | cum output | cum $ @pro | cum $ @flash |
|---|---|---|---|---|---|
| v0.2 | M0 | 175k | 152k | $0.60 | $0.21 |
| v0.3 | M1 | 655k | 432k | $1.78 | $0.61 |
| v0.4 | M2 | 1,873k | 1,128k | $4.72 | $1.60 |
| v0.5 | M3 | 2,494k | 1,484k | $6.22 | $2.11 |
| v0.6 | M4 | 3,037k | 1,775k | $7.47 | $2.53 |
| v0.7 | M5 | 3,142k | 1,837k | $7.73 | $2.62 |
| v0.8 | M6 | 3,756k | 2,183k | $9.19 | $3.11 |
| v0.9 | M7 | 4,874k | 2,835k | $11.93 | $4.04 |
| v0.10 | M8 | 5,566k | 3,208k | $13.53 | $4.58 |
| v1.0 | integration | 5,879k | 3,398k | $14.32 | $4.85 |

The "natural mix" (scout/builder on flash, lead/specialist/reviewer on pro)
falls between the two columns — roughly $8–9 cumulative by v1.0. See
[`40-budget.md`](40-budget.md) for the method and the per-milestone low/high
ranges.

**Budget caveat (v1).** The M2 row prices the *disc-owner ddraw proxy*. If the
target-host decision selects the *own-engine* path for disc-less users, M2's
estimate is no longer representative — it becomes a larger, unpriced milestone
and the table must be re-costed before v0.4 is committed. The M2 scope decision
is an open item for the human, not a number this table silently assumes.

## Release ↔ milestone map

| Release | Milestones | Distribution form |
|---|---|---|
| v0.1 | (research 01–06) | source + pip |
| v0.2 | M0 | source (docs) |
| v0.3 | M1 | source (docs) |
| v0.4 | M2 | DLL proxy (`ddraw.dll`) + installer script |
| v0.5 | M3 | DLL proxy (`dinput.dll`) alongside the presenter |
| v0.6 | M4 | pip package |
| v0.7 | M5 | pip package |
| v0.8 | M6 | mod package (generator + recipe) |
| v0.9 | M7 | source (spike / patcher recipe) |
| v0.10 | M8 | pip package + recipe |
| v1.0 | M2–M8 (stable union) | installer + pip + mod package |
