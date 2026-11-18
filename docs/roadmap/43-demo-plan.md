# 43. Demo plan — what we would show, and what it costs

[`41-measured-cost.md`](41-measured-cost.md) measured what the M2–M4 work
actually consumed; [`42-input-token-reduction.md`](42-input-token-reduction.md)
put a dollar figure on it and closed the "91:1 input" scare. What neither file
answers is the *marketing* question: **what do we show a stranger, what has to
be built first, and what does showing it cost?** This file is that answer,
written so the human can say yes or no to a number, not to a feeling.

At `0.4.0-alpha.1` the project is a **data layer + headless engine + presenter
that writes a PNG** — there is no window and no input, so a live played session
is not on the table. Everything below is scoped as a **short recorded walkthrough
plus a runnable script**, not a shipped game.

## 1. The demo, in one paragraph

A two-to-three-minute recorded terminal walkthrough, plus a copy-paste runnable
script, that starts from a clean checkout and points the CLI at the viewer's
*own* unpacked Lomax copy. In order, a stranger sees: `doctor` inventory the
install; `present --modern` and `present --authentic` render the same engine
frame as a filtered 4× 1080p image and a native 1× nearest image; the headless
conformance harness print `PASS (10/10)` with no display and no game data; and
`export` decode a world file into tile sheets. It ends with the two frames and
the sheets open side by side, and a one-line disclaimer that this is the
data layer and headless engine — not yet a playable game.

### What a stranger sees (checklist)

1. **What the project is**, in one line: a from-scratch reimplementation of a
   1997 Windows game's data and engine, shipping no game bytes.
2. **The game's own data parsed**: `doctor` lists 9 world files (7,107,048 bytes),
   the `LOMAX.EXE` (505,344 B, hashed but not executed), and the SFX/DEMOS/
   JINGLES/AMBIENT folders.
3. **One engine frame, two ways**: the same 320×240 slice rendered modern
   (epx-aa, 4×, 1920×1080 surface) and authentic (nearest, 1×, 320×240).
4. **A conformance harness that cannot be faked**: `python -m lomax_modern.conformance`
   prints `verdict: PASS (10/10 cases)` without opening a window or reading game data.
5. **Tile sheets decoded from a `.WLD`**: `export` writes the `CELL` sheet and
   per-plane tile/collision sheets, with the open questions (`Q20` map
   cell → tile record) stated rather than guessed.
6. **Reproducible by the viewer**: every command exists in the alpha and is
   quoted with its real output in the script, so a stranger can replay it
   against their own copy.

## 2. The three options

| | What it shows | New code | Feels like |
|---|---|---|---|
| **A. Tooling demo** | data plumbing + one static frame + harness PASS | none | a research tool |
| **B. Engine demo** | the slice **animating** at 60 Hz, scaled | one small feature | a game waking up |
| **C. Playable demo** | window + input + a playable first world | a milestone (M5 + more) | the game itself |

- **A** is available *today*. `doctor` → `present` → `conformance` → `export`
  all run on the current alpha (outputs reproduced in §5). The only work is the
  recording and the write-up.
- **B** adds a frame sequence so the slice visibly animates: capture N frames
  (one per 60 Hz tick) through the existing presenter and emit them as PNG/GIF
  (MP4 via the viewer's own `ffmpeg`, a script line, not our code). This is the
  one genuinely new feature.
- **C** is M5 (input) plus a window presenter plus finishing M3's
  "first world playable end to end" — which is blocked on unresolved formats
  (`Q20` map cell → tile, and the still-unidentified `GNMY` entry semantics —
  note that `Q23`/`Q24`, the `NMY`/`ANIM` framings, are **answered** and
  validated 9/9 and 566/566). Weeks, not hours.

## 3. The measured unit rate

Every projection below uses the **measured** per-card figures, not the
`40-budget.md` estimates. The unit is derived by dividing the published totals
by the published card count, and is reproduced exactly by
`scripts/token_cost_report.py --board retrolab --json` (run on the host, which
mounts the per-profile `logs/agent.log`):

| quantity | total (source) | ÷ 58 cards |
|---|---:|---:|
| output tokens | 2,437,509 (42 §1) | **~42.0 k/card** |
| fresh input tokens | 5,929,963 (42 §1) | **~102 k/card** |
| cached input tokens | 215,817,088 (42 §1) | **~3.72 M/card** |
| money, off-peak | ~$9.59 (42 §2) | **~$0.165/card** |

The relationships the task asks for, stated plainly from 42:

- **output is ~40 % of the money** (42 §2: output $3.85 of $9.59);
- **fresh input is 2.43 × output** (42 §1);
- **cached input is the volume, not the money**: 3.72 M tokens/card but billed
  at the 30–50× cache-hit discount, so the whole cached line is ~$3 (42 §2).

The unit is a **board-wide average** across all 58 measured cards and all five
profiles — scout, builder, reviewer, specialist, lead — so a reviewer pass
(short, read-and-verdict) sits *below* it and a specialist implementation card
*above* it. `41-measured-cost.md` publishes per-profile *totals* but not
per-profile card counts, so the average is the honest unit; the profile
breakdown is instead handled on the wall-clock axis, where the board *does*
record per-card numbers (§3.1).

### Confidence, and what would move it

- **Medium.** Two caveats from `41-measured-cost.md` §Caveats apply unchanged:
  34 of 92 runs had no matching log line (logs rotate at 2 MiB), so the token
  totals — and therefore the per-card unit — are a **lower bound**; and the
  cache-aware pass captured ~1 % more input than the by-milestone pass (42 §1
  footnote), which is inside the rounding of every figure here.
- **What moves it:** (1) provider repricing moves every dollar figure while
  leaving token figures intact (40-budget §7); (2) a card that retries across
  sessions re-pays the spawn floor, pushing it above the average; (3) a
  milestone built on *unfamiliar* territory (like M3) runs far above the board
  average — which is why option C is not costed at this unit rate (§6).

### 3.1 Wall-clock, from `task_runs`

The board records wall-clock, not tokens. Per-profile per-card spreads, from the
`40-budget.md` Revision (already reconciled to measured), reproduce with:

```sql
SELECT task_id, profile,
       (ended_at - started_at) / 60.0 AS wall_clock_min
  FROM task_runs
 WHERE outcome = 'completed' AND ended_at IS NOT NULL;
```

| profile (what it did) | measured wall-clock per card |
|---|---|
| builder (implementation) | ~7.7–13.3 min (n=4 substantive) |
| specialist (implementation) | ~13–25 min (n=3) |
| reviewer (one pass) | ~5.5–7.5 min (central; n=20) |
| lead (synthesis) | ~14.9 min (n=1) |

These bands are the same ones `40-budget.md` used to re-forecast M5/M6; the
demo-plan cards are the same shape of work (one feature, one review), so they
are the right anchor.

## 4. Option A — the tooling demo (available now)

**Cards: 2.** One **builder** card authors the demo script and write-up, quoting
real output; one **reviewer** card verifies every command reproduces. Zero new
code; the screen recording itself is human effort (OBS/`ffmpeg`), not agent work.

| axis | projection |
|---|---|
| cards | 1 builder + 1 reviewer (review counted) |
| tokens | ~84 k output · ~204 k fresh · ~7.4 M cached |
| money | **~$0.33** off-peak |
| wall-clock | **~0.22–0.35 h** (13–21 min) |
| confidence | high on cost (no code, so the only uncertainty is the write-up length) |

*Derived:* 2 × the §3 unit; wall-clock = builder 7.7–13.3 + reviewer 5.5–7.5 min.

**Not included:** any new code; the recording is a human capture; MP4/GIF output.

## 5. Option B — the engine demo (recommended)

**Cards: 3.** Two **builder** cards and one **reviewer** card.

1. **builder** — frame-sequence capture: `--frames N --out DIR` on `slice` (and
   `present`), rendering one frame per 60 Hz tick through the existing presenter
   (so it lands already integer-scaled), writing PNG frames. Unit tests on
   synthetic fixtures. This is the "small feature" — it threads the existing
   `render(level, state)` call into the tick loop and reuses `png.write`.
2. **builder** — GIF output (a small pure-Python GIF encoder) + tests. MP4 is
   **not** our code: the demo script calls the viewer's own
   `ffmpeg -framerate 60 -i frame_%04d.png demo.mp4`.
3. **reviewer** — review the feature PR.

| axis | projection |
|---|---|
| cards | 2 builder + 1 reviewer (review counted) |
| tokens | ~126 k output · ~307 k fresh · ~11.2 M cached |
| money | **~$0.50** off-peak |
| wall-clock | **~0.35–0.57 h** (21–34 min) |
| confidence | medium (feature is small and well-scoped; the GIF encoder is the one part with real surface area) |

*Derived:* 3 × the §3 unit; wall-clock = 2 × builder 7.7–13.3 + reviewer 5.5–7.5 min.

### The commands B needs, and what exists today

Everything B depends on **already exists in the alpha** except the frame
*sequence* flag. The single-frame path is real and quoted below; `--frames N` is
the only addition:

```console
$ lomax-modern present "/game-files/LOMAX (1)/LOMAX" --modern --frame modern.png
(install manifest elided)
engine: 300 ticks at 60 Hz (fixed by the engine core), 300 frames, exit reached: no
profile: modern (authentic toggle: off)
filter: epx-aa (runtime switch: --filter nearest|epx-aa)
source: 320x240 (engine frame)
surface: 1920x1080
scale: 4x (auto: largest integer fit)
content: 1280x960 at +320+60; pads left 320, right 320, top 60, bottom 60
frame: modern.png (1920x1080)

$ lomax-modern present "/game-files/LOMAX (1)/LOMAX" --authentic --frame authentic.png
profile: authentic (authentic toggle: on)
filter: nearest (runtime switch: --filter nearest|epx-aa)
surface: 320x240
scale: 1x (auto: largest integer fit)
frame: authentic.png (320x240)
```

The animation is already latent: `slice` runs the 60 Hz tick to completion and
renders the *final* frame. B's feature captures the intermediate frames, so the
recording shows Lomax walking and jumping rather than one static pose.

## 6. Option C — the playable demo

C is **not costable at the §3 per-card rate**, and pretending otherwise would
violate the "verified vs hypothesis" rule. It spans work with no measured
precedent in this repo: the window presenter (`docs/architecture.md` §5 marks
the Win32 presenter as "future"), plus finishing M3's
spawn → move → collide → collect → exit → next-level loop, which is blocked on
unresolved formats (`Q20` map cell → tile, and what a `GNMY` entry means;
`Q23`/`Q24` are answered).
`40-budget.md` §7 already flags M3 as **order-of-magnitude** — "a tick-for-tick
reimplementation has no measured precedent … treat the $4.28 @pro M3 row as
order-of-magnitude."

The nearest *measured* anchors are the `40-budget.md` Revision re-forecasts:

| piece | cards | wall-clock | token figure |
|---|---|---|---|
| M5 controller & input | ~7 (3 specialist + 3 review + 1 lead synthesis) | ~1.2–1.9 h | §4 estimate 420 k/240 k exp, *not* measured |
| M6 audio (if SFX is wanted) | ~2 (1 specialist + 1 review) | ~0.3–0.5 h | §4 estimate 100 k/55 k exp, *not* measured |
| window presenter + M3 completion | **unbudgeted** | **weeks** | outside the measured M2–M4 spread |

So C is a **milestone decision**, not a demo decision: it is the v0.5/v0.7
ladder already in `20-releases.md`, and it is weeks not hours. The honest cost
number is "M3 at order-of-magnitude uncertainty plus M5 re-forecast above," not
a dollar figure off a per-card average.

## 7. Recommendation — do **B**, at ~$0.50

**B** is the only option that shows the project *doing the thing it exists to
do* — running the game's own data at the original 60 Hz, scaled to a modern
screen — for **~$0.50 off-peak** (3 cards, ~0.35–0.57 h wall-clock, ~126 k
output / ~307 k fresh / ~11.2 M cached tokens). It converts the demo from "a
research tool reads some files" into "the engine is alive," which is the claim a
stranger needs to see, for the price of one small feature plus its review. A is
$0.33 and C is weeks; B is the entire emotional payoff for $0.17 more than A.

### If you want the cheaper one, do A

A costs **~$0.33** (2 cards, ~0.22–0.35 h) and needs **zero new code** — it is a
recording plus a write-up of commands that already run today. It proves the
data layer is real and reproducible, but it shows a static frame, so a stranger
learns the project *parses* the game rather than that it *plays* it. Choose A if
the goal is a low-risk proof of life this week; choose B if the goal is a demo
that looks like the game is coming back.

## 8. What is *not* included (all options)

- **No game assets in the repository.** The demo runs against the viewer's own
  unpacked copy; we ship no `*.WLD`, sprites, or audio.
- **No ISO, ripping or acquisition instructions** anywhere in the doc or script;
  no emulation of a CD check; no redistributed `LOMAX.EXE` (the CLI hashes it
  for inventory but never executes it).
- **No audio/music** in the demo (M6, and the runbook states plainly there is
  no music track; music rights are out of scope entirely).
- **No Windows packaging** (M7 AppImage/exe) and no installer — the demo is a
  script against a `pip install` / source checkout.
- **No window or input** — A and B are recorded walkthroughs; a live played
  session is C and is explicitly not part of this plan.

## 9. Reproduce

- **Dollars/tokens:** `python3 scripts/token_cost_report.py --board retrolab --json`
  (host) reproduces the fresh/cached/output split; the money table is
  `42-input-token-reduction.md` §2 and the unit rate is §3 above (total ÷ 58).
- **Wall-clock:** the SQL in §3.1 against
  `/home/nwah/.hermes/kanban/boards/retrolab/kanban.db`; profile bands from the
  `40-budget.md` Revision.
- **The demo commands:** every command in §5 exists in `0.4.0-alpha.1` and its
  output above was captured on a real retail install; the `--frames N` flag is
  the single addition option B builds.
