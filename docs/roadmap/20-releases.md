# 20. Releases

Releases v0.1…v1.0. Each lists its theme, contents (which milestones), a
definition of done, upgrade/compat notes, the distribution form, and what a user
must legally own. Companion documents: [`00-research-plan.md`](00-research-plan.md),
[`10-milestones.md`](10-milestones.md), [`30-risks.md`](30-risks.md), and
[`40-budget.md`](40-budget.md) (the token/cost model behind the "cost to date"
column below).

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
- **Contents.** M1: the Wine/Proton compat matrix, the first-run recipe, the
  injection/startup-order findings, and the confirmed mechanism choice
  (DLL proxy vs app-level filter).
- **Definition of done.** A maintainer can read the report and know the target
  host and hook mechanism without re-doing the experiments; open questions are
  filed in `05-open-questions.md`.
- **Upgrade/compat notes.** Docs + README guidance; no runtime artefact yet.
- **Distribution form.** Source repository (docs) + updated README.
- **User must own.** Nothing (prose only).

## v0.4 — Presenter (L1)

- **Theme.** "Pleasant on a 2026 Linux desktop today" — the display half.
- **Contents.** M2: the clean-room `ddraw.dll` proxy / app-level presenter with
  integer scaling and at least one selectable pixel-art filter, for Windows and
  Linux/Proton.
- **Definition of done.** Stock `LOMAX.EXE` + our shim runs borderless at 4K with
  correct aspect, no shimmer and no transparency regression, on one Linux
  distro and on Windows; filter switching is demonstrated; tests green.
- **Upgrade/compat notes.** The shim is version-independent (it does not patch
  the exe); Wine version constraints are documented from M1's matrix.
- **Distribution form.** **DLL proxy** (a dropped-in `ddraw.dll`, built in CI)
  plus an install script that copies it next to the user's own files. No game
  bytes.
- **User must own.** A legal copy of the game (retail `LOMAX.EXE` + data). We
  ship only our MIT shim.

## v0.5 — Controller

- **Theme.** "Play it with a pad" — the input half of *pleasant*.
- **Contents.** M3: a clean-room `dinput.dll` proxy translating XInput/evdev to
  the game's DirectInput calls — analogue movement, buttons, d-pad menu
  navigation, hot-plug, per-controller presets. Rumble deferred.
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
- **Contents.** M4: `lomax_modern.wld` reader/writer with byte-exact round trip,
  tile/sprite PNG exporter, and the `H → V` promotion pass in
  `file-formats.md`.
- **Definition of done.** `read → write` is bit-identical on all 9 world files
  and the game loads the rebuilt file; exporter sheets are recognisable;
  round-trip and negative tests pass.
- **Upgrade/compat notes.** Read-only CLI semantics preserved; the new write
  path always backs up and refuses if it cannot round-trip.
- **Distribution form.** `pip install lomax-modern` (Python, dependency-free).
- **User must own.** A legal copy of the game; exported art stays on their disk
  (we never redistribute it).

## v0.7 — Password tool

- **Theme.** "Small win."
- **Contents.** M5: `lomax-modern password` encoder/decoder from the documented
  layout.
- **Definition of done.** Round-trips with unit tests; one generated password
  is verified in-game.
- **Upgrade/compat notes.** Additive CLI subcommand; no breaking change. A thin
  release — it may ride along with v0.6 or v0.8 if fewer releases are preferred.
- **Distribution form.** `pip install lomax-modern`.
- **User must own.** A legal copy of the game (to verify passwords).

## v0.8 — Asset pipeline: upscaler + pack writer

- **Theme.** "2× art, in-game."
- **Contents.** M6: the matte-aware 2× upscaler and the 2× pack writer that
  transforms the user's own `WORLDS/*.WLD` in place with backup.
- **Definition of done.** Comparison sheets show no key-colour bleed or
  transparency breakage on ≥20 tiles and ≥10 sprites; the game starts with a 2×
  pack installed and at least one level renders without artefacts; the
  backup/restore path is tested.
- **Upgrade/compat notes.** The pack writer is a script + patch recipe, not a
  binary; it never ships upscaled art.
- **Distribution form.** **Mod package**: the generator + patch recipe in the
  repository; the user runs it against their own files.
- **User must own.** A legal copy of the game; the 2× output is a derivative of
  their copy's art and stays on their machine.

## v0.9 — 2× render spike verdict

- **Theme.** "True HD: the verdict."
- **Contents.** M7: the 2× internal-render proof-of-concept or the published
  findings that close it.
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
  `GAME.TXT` translation support.
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
