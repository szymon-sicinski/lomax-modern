# 20. Releases

Releases v0.1…v1.0. Each lists its theme, contents (which milestones), a
definition of done, upgrade/compat notes, the distribution form, and what a user
must legally own. Companion documents: [`00-research-plan.md`](00-research-plan.md),
[`10-milestones.md`](10-milestones.md), [`15-strategy-report.md`](15-strategy-report.md),
[`30-risks.md`](30-risks.md), and [`40-budget.md`](40-budget.md) (the token/cost
model behind the "cost to date" column below).

> **Revision v2** (LMX-9/M2, 2026-11-18). Re-cut for the **disc-less / own-engine**
> decision: v0.4 is no longer the ddraw presenter. The ladder now follows the new
> spine — data layer (v0.4) → engine core (v0.5) → presenter (v0.6) → input +
> audio (v0.7) → packaging (v0.8) — with the surviving tooling (asset pipeline,
> 2× spike, password, editor) behind it. The `ddraw.dll` proxy is an optional
> disc-owner appendix, not a release.

Versioning is [SemVer](https://semver.org/); everything before v1.0 is
pre-1.0 and may change incompatibly.

## Table of contents

- [v0.1 — Establish the premise (shipped)](#v01--establish-the-premise-shipped)
- [v0.2 — The plan (shipped)](#v02--the-plan-shipped)
- [v0.3 — Strategy report](#v03--strategy-report)
- [v0.4 — Data layer](#v04--data-layer)
- [v0.5 — Engine core](#v05--engine-core)
- [v0.6 — Presenter](#v06--presenter)
- [v0.7 — Input + audio](#v07--input--audio)
- [v0.8 — Packaging](#v08--packaging)
- [v0.9 — Asset pipeline](#v09--asset-pipeline)
- [v0.10 — 2× render spike verdict](#v010--2-render-spike-verdict)
- [v0.11 — Password + editor + translation](#v011--password--editor--translation)
- [v1.0 — Modernised build](#v10--modernised-build)
- [Cost to date (cumulative)](#cost-to-date-cumulative)
- [Release ↔ milestone map](#release--milestone-map)

---

## v0.1 — Establish the premise (shipped)

- **Theme.** Prove what the game *is* and what can be improved, with numbers.
- **Contents.** Docs 01–06; read-only CLI `doctor` / `wldscan` / `measure`;
  CI matrix.
- **Definition of done.** Research published with citations; CLI read-only and
  dependency-free; 28 unit tests green.
- **Distribution form.** Source repository + `pip install lomax-modern`.
- **User must own.** Nothing beyond the tool (MIT).

## v0.2 — The plan (shipped)

- **Theme.** Turn research into a reviewed, costed roadmap and dispatch the work.
- **Contents.** M0: `docs/roadmap/` + the research and synthesis cards.
- **Definition of done.** Roadmap docs present with resolving links; PR merged.
- **Distribution form.** Source repository (docs).
- **User must own.** Nothing.

## v0.3 — Strategy report

- **Theme.** Settle "where it runs and how we present it" from evidence — now
  with the target-host decision made.
- **Contents.** M1's deliverable, [`15-strategy-report.md`](15-strategy-report.md):
  the compat matrix (B1 GDI gate, B2 missing 320×240, B3 CD check, B4 MFC
  order), the **disc-less / own-engine** target-host decision, the demoted
  `ddraw.dll` proxy (appendix), the renderer facts the own engine must reproduce,
  and the disc-owner Fedora/Nobara recipe with its three probes.
- **Definition of done.** A maintainer can read the report and know the target
  host and mechanism without re-doing the experiments; open questions Q15–Q19
  (appendix-track) and Q28 (resolved) plus Q29/Q30 (new) are filed in
  [`../research/05-open-questions.md`](../research/05-open-questions.md).
- **Upgrade/compat notes.** Docs only; no runtime artefact.
- **Distribution form.** Source repository (docs).
- **User must own.** Nothing (prose only).

## v0.4 — Data layer

- **Theme.** The foundation the engine rests on: every container parsed (and
  where a writer exists, round-tripped) byte-exactly.
- **Contents.** M2: `lomax_modern.wld` byte-exact reader/writer (the round-trip
  falsifier is already closed — 9/9 structural, 104/104 `MAP` rebuild), the
  `TTAB`/`CELL`/`MAP` decode and tile/sprite exporter, the `ANIM`/`NMY`
  retraction + structural probe, and the audio reader (82 WAVs).
- **Definition of done.** `read → write` is bit-identical on all 9 world files;
  the exporter sheets are recognisable; the probe prints `map cell → tile
  record: unresolved` (never a guessed count); the two falsified `D` claims
  (`ANIM` 0x38, `NMY` length-prefixed) are marked `retracted` in
  `file-formats.md`; tests green.
- **Upgrade/compat notes.** Additive; the read-only CLI semantics are preserved.
- **Distribution form.** `pip install lomax-modern` (dependency-free Python).
- **User must own.** A legal copy of the game (the data files, not a disc).

## v0.5 — Engine core

- **Theme.** The game, reproduced from data: map/collision/entities/timing.
- **Contents.** M3: a **vertical slice** — the first world playable end to end
  (spawn → move → collide → collect → exit → next level) — loaded from
  `WORLDS/*.WLD`, drawn to a 16-bit `B5G6R5` framebuffer from `CELL`/`TTAB`/`MAP`,
  driven by the 60 Hz tick, honouring the fade `⌈w/32⌉·32` rule.
- **Definition of done.** The first world is fully playable end to end with
  keyboard input at the original logic rate; the 8 attract demos replay
  tick-for-tick (or the milestone records why `DEMOS/*.DAT` cannot yet be
  decoded); tests green.
- **Upgrade/compat notes.** The first release that runs the game's own data
  without the exe; still developer-facing (no borderless/4K yet — that is v0.6).
- **Distribution form.** `pip install lomax-modern` (engine module).
- **User must own.** A legal copy of the game's data files.

## v0.6 — Presenter

- **Theme.** "Pleasant on a 2026 desktop today" — our own renderer, borderless,
  integer-scaled, filtered, **modern by default**.
- **Contents.** M4: the own renderer with integer scaling and at least one
  selectable pixel-art filter (nearest vs xBRZ/MMPX), plus the runtime
  `lomax-modern present` entry point. **Modern defaults** (widescreen, 60 fps,
  smooth scaling, save states) are on; an *authentic* toggle is the escape
  hatch.
- **Definition of done.** The engine's frame renders at 4K borderless with
  correct aspect, no shimmer and no transparency regression; filter switching is
  demonstrated in a side-by-side screenshot; the headless render-conformance
  harness passes in CI at depth 16 vs 24; tests green.
- **Upgrade/compat notes.** The renderer is our own code — no Wine, no closed
  DLLs, version-independent of the game.
- **Distribution form.** `pip install lomax-modern` (presenter) — **no game
  bytes, no Wine bundle**.
- **User must own.** A legal copy of the game's data files.

## v0.7 — Input + audio

- **Theme.** "Play it with a pad, and hear it" — input and sound.
- **Contents.** M5 (keyboard first, then our own input layer: evdev/XInput →
  game action, d-pad menus, hot-plug, presets, rebinding, save states) + M6
  (SFX + ambient L/R bed + jingles from the on-disk WAVs; **no music track**).
- **Definition of done.** Keyboard plays the vertical slice end to end; a
  DualSense and an Xbox pad both move Lomax and navigate menus, surviving
  hot-plug; save states round-trip; SFX/ambience/jingles play in-engine; the
  runbook states plainly there is no music.
- **Upgrade/compat notes.** Additive over v0.6.
- **Distribution form.** `pip install lomax-modern`.
- **User must own.** A legal copy of the game's data.

## v0.8 — Packaging

- **Theme.** "Download and run" — a launcher that ships only our code.
- **Contents.** M7: a Linux AppImage and a Windows `.exe` that load the user's
  data directory and fail loudly (file-by-file manifest, P5) when data is
  missing. macOS deferred; no store presence.
- **Definition of done.** A clean Linux and a clean Windows machine, each with
  only the user's data directory, go from download to a running presenter; the
  missing-data path prints an actionable manifest, not a vague error.
- **Upgrade/compat notes.** First release aimed at non-developers.
- **Distribution form.** AppImage + Windows `.exe` + pip package — MIT code only.
- **User must own.** A legal copy of the game's data files.

## v0.9 — Asset pipeline

- **Theme.** "2× art, in-game (once the render hook exists)."
- **Contents.** M8: the matte-aware 2× upscaler and the 2× pack writer
  (one-cell-per-cell at 256 B; four-cells-per-2×-cell ruled out by the 13-bit
  index overflow).
- **Definition of done.** Comparison sheets show no key-colour bleed or
  transparency breakage on ≥20 tiles and ≥10 sprites; the backup/restore path is
  tested. (2× **sprites** stay blocked on the `ANIM` layout; displaying 2× art is
  the M9 render hook.)
- **Distribution form.** **Mod package**: generator + recipe; never upscaled art.
- **User must own.** A legal copy of the game (the 2× output is a derivative of
  their copy's art).

## v0.10 — 2× render spike verdict

- **Theme.** "True HD: the verdict."
- **Contents.** M9: the 2× internal-render proof-of-concept, now that the
  renderer is ours (the 512 px ceiling is a code limit we wrote, not a patch
  target).
- **Definition of done.** Either one level renders at 640x480 with 2× art and
  the demos replay identically, or the "why not + what would have to change"
  document is merged and the milestone is marked abandoned.
- **Distribution form.** Source repository (spike) — patcher recipe only if the
  spike succeeds.
- **User must own.** A legal copy of the game.

## v0.11 — Password + editor + translation

- **Theme.** The modding/progress tail.
- **Contents.** M10 (password word codec) + M11 (level editor + `GAME.TXT`
  translation). The editor's placement falsifier is gated on `NMY`/`MACR`/`PAGE`
  decoding; translation is independent and may ship earlier.
- **Definition of done.** The password codec round-trips (and refuses to
  generate until the checksum is known); the editor re-emits a level the engine
  loads; a translated `GAME.TXT` renders with correct encoding.
- **Distribution form.** `pip install lomax-modern`.
- **User must own.** A legal copy of the game.

## v1.0 — Modernised build

- **Theme.** Everything stable and documented: the own-engine presenter playable
  on Linux and Windows, asset pipeline open, optional 2× path behind its
  go/no-go.
- **Contents.** The stable union of M2–M11 (+ M9 if it landed), plus the
  integration/QA pass and a re-reviewed risk register.
- **Definition of done.** A new user follows the README, points the tool at
  their own data, launches, plays with a pad, switches filters, exports/inspects
  assets — and every tool's exit criteria still pass. No game bytes in the repo;
  CI green.
- **Distribution form.** **Installer** (engine + presenter + CLI) + pip package
  + mod-package generators; all MIT code, no assets, no Wine, no game bytes.
- **User must own.** A legal copy of the game's data files, always. We ship
  tooling, never the game.

## Cost to date (cumulative)

From [`40-budget.md`](40-budget.md): cumulative **expected** spend, off-peak.
Tokens are thousands.

| Release | Milestones | cum input | cum output | cum $ @pro | cum $ @flash |
|---|---|---|---|---|---|
| v0.2 | M0 | 175k | 152k | $0.60 | $0.21 |
| v0.3 | M0–M1 | 655k | 432k | $1.78 | $0.61 |
| v0.4 | +M2 | 1,615k | 952k | $3.98 | $1.36 |
| v0.5 | +M3 | 3,415k | 1,972k | $8.26 | $2.83 |
| v0.6 | +M4 | 4,255k | 2,452k | $10.27 | $3.52 |
| v0.7 | +M5+M6 | 4,775k | 2,747k | $11.51 | $3.95 |
| v0.8 | +M7 | 5,015k | 2,882k | $12.08 | $4.14 |
| v0.9 | +M8 | 5,629k | 3,228k | $13.55 | $4.63 |
| v0.10 | +M9 | 6,747k | 3,880k | $16.29 | $5.56 |
| v0.11 | +M10+M11 | 7,545k | 4,316k | $18.15 | $6.19 |
| v1.0 | +integration | 7,857k | 4,506k | $18.94 | $6.46 |

The **natural mix** (scout/builder on flash, lead/specialist/reviewer on pro)
lands around **$13 cumulative by v1.0** — ~1.5× the old shim plan's ~$8–9, driven
almost entirely by the engine core (M3). See [`40-budget.md`](40-budget.md) §5
and §7 for the multiplier and its confidence.

## Release ↔ milestone map

| Release | Milestones | Distribution form |
|---|---|---|
| v0.1 | (research 01–06) | source + pip |
| v0.2 | M0 | source (docs) |
| v0.3 | M1 | source (docs) |
| v0.4 | M2 | pip package |
| v0.5 | M3 | pip package (engine) |
| v0.6 | M4 | pip package (presenter) |
| v0.7 | M5 + M6 | pip package |
| v0.8 | M7 | installer + pip |
| v0.9 | M8 | mod package (generator + recipe) |
| v0.10 | M9 | source (spike / patcher recipe) |
| v0.11 | M10 + M11 | pip package |
| v1.0 | M2–M11 (stable union) | installer + pip + mod package |
