# 20. Releases

Releases v0.1…v1.0. Each lists its theme, contents (which milestones), a
definition of done, upgrade/compat notes, the distribution form, and what a user
must legally own. Companion documents: [`00-research-plan.md`](00-research-plan.md),
[`10-milestones.md`](10-milestones.md), [`30-risks.md`](30-risks.md).

Versioning is [SemVer](https://semver.org/); everything before v1.0 is
pre-1.0 and may change incompatibly.

## Table of contents

- [v0.1 — Establish the premise (shipped)](#v01--establish-the-premise-shipped)
- [v0.2 — The plan (this PR)](#v02--the-plan-this-pr)
- [v0.3 — Strategy report](#v03--strategy-report)
- [v0.4 — Presenter (L1)](#v04--presenter-l1)
- [v0.5 — `.WLD` toolkit + exporter](#v05--wld-toolkit--exporter)
- [v0.6 — Password + upscaler](#v06--password--upscaler)
- [v0.7 — 2× pack writer](#v07--2x-pack-writer)
- [v0.8 — 2× render spike verdict](#v08--2x-render-spike-verdict)
- [v0.9 — Level editor + translation](#v09--level-editor--translation)
- [v1.0 — Modernised build](#v10--modernised-build)

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
- **Contents.** M0: `docs/roadmap/` (this document set) + the five research
  cards and one synthesis card on the board.
- **Definition of done.** All four roadmap documents present with resolving
  relative links; the one-page answer and the mechanism decision are in
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

- **Theme.** "Pleasant on a 2026 Linux desktop today."
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

## v0.5 — `.WLD` toolkit + exporter

- **Theme.** "The asset pipeline begins."
- **Contents.** M3: `lomax_modern.wld` reader/writer with byte-exact round trip,
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

## v0.6 — Password + upscaler

- **Theme.** "Small wins + art prep."
- **Contents.** M4 (password tool) and the matte-aware 2× upscaler part of M5.
- **Definition of done.** `lomax-modern password` round-trips and one password
  is verified in-game; the upscaler's comparison sheets show no key-colour
  bleed or transparency breakage on ≥20 tiles and ≥10 sprites.
- **Upgrade/compat notes.** Additive CLI subcommands; no breaking change.
- **Distribution form.** `pip install lomax-modern`.
- **User must own.** A legal copy of the game (to verify passwords and to run
  the upscaler on their own art).

## v0.7 — 2× pack writer

- **Theme.** "2× art, in-game."
- **Contents.** M5 (pack writer): transforms the user's own `WORLDS/*.WLD` in
  place with backup, refuses non-round-trippable files.
- **Definition of done.** The game starts with a 2× pack installed and at least
  one level renders without artefacts; the backup/restore path is tested.
- **Upgrade/compat notes.** The pack writer is a script + patch recipe, not a
  binary; it never ships upscaled art.
- **Distribution form.** **Mod package**: the generator + patch recipe in the
  repository; the user runs it against their own files.
- **User must own.** A legal copy of the game; the 2× output is a derivative of
  their copy's art and stays on their machine.

## v0.8 — 2× render spike verdict

- **Theme.** "True HD: the verdict."
- **Contents.** M6: the 2× internal-render proof-of-concept or the published
  findings that close it.
- **Definition of done.** Either one level renders at 640x480 with 2× art and
  the demos replay identically, or the "why not + what would have to change"
  document is merged and the milestone is marked abandoned.
- **Upgrade/compat notes.** Spike output is a separate branch/tool; it does not
  alter the stable presenter or toolkit.
- **Distribution form.** Source repository (research/spike code) — **patcher**
  recipe only if the spike succeeds and stays clean-room.
- **User must own.** A legal copy of the game.

## v0.9 — Level editor + translation

- **Theme.** "The modding story."
- **Contents.** M7: level editor (round-trips map/collision/placements) and
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
- **Contents.** The stable union of M2, M3, M4, M5 (+ M6 if it landed), M7 if
  ready, with the risk register re-reviewed.
- **Definition of done.** A new user follows the README, installs the shim on
  Linux/Proton, launches their own copy, switches filters, exports/inspects
  assets, and every tool's exit criteria still pass. No game bytes in the repo;
  CI green across the matrix.
- **Upgrade/compat notes.** A single documented upgrade path from v0.4 (shim)
  through v1.0; the shim remains version-independent.
- **Distribution form.** **Installer** (the shim + CLI) + the pip package + the
  mod-package generators; all MIT code, no assets.
- **User must own.** A legal copy of the game, always. We ship launchers and
  tooling, never the game itself.

## Release ↔ milestone map

| Release | Milestones | Distribution form |
|---|---|---|
| v0.1 | (research 01–06) | source + pip |
| v0.2 | M0 | source (docs) |
| v0.3 | M1 | source (docs) |
| v0.4 | M2 | DLL proxy + installer script |
| v0.5 | M3 | pip package |
| v0.6 | M4 + M5(scaler) | pip package |
| v0.7 | M5(pack writer) | mod package (generator + recipe) |
| v0.8 | M6 | source (spike / patcher recipe) |
| v0.9 | M7 | pip package + recipe |
| v1.0 | M2–M7 (stable union) | installer + pip + mod package |
