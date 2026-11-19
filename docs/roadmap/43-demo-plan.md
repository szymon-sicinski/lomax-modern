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
| **C. Playable demo** | window + tile art + input + a playable first world | now staged: animated slice ≈$0.99–$1.49, playable gated on Q32 | the game itself |

- **A** is available *today*. `doctor` → `present` → `conformance` → `export`
  all run on the current alpha (outputs reproduced in §5). The only work is the
  recording and the write-up.
- **B** adds a frame sequence so the slice visibly animates: capture N frames
  (one per 60 Hz tick) through the existing presenter and emit them as PNG/GIF
  (MP4 via the viewer's own `ffmpeg`, a script line, not our code). This is the
  one genuinely new feature.
- **C** is M5 (input) plus a window presenter plus finishing M3's
  "first world playable end to end". Two of the three blockers are now closed:
  `Q20`/`Q21`/`Q22` (map cell → tile) are resolved — with `Q21` split as
  bit roles `[V]` and axis pairing `[H]` (`Q33`) — and the window presenter
  is scoped and measured (ctypes+SDL2, V), so the *animated* slice is costed at
  ≈$0.99–$1.49 (§6.1). The one remaining blocker is `GNMY` entry *semantics*
  (which entry is the spawn/collectable/exit) — the layout is recovered (V) but
  the meaning is still H, recorded as `Q32` — so a *playable* slice is a
  milestone with a priced first step (§6.2), not an open "weeks". (`Q23`/`Q24`,
  the `NMY`/`ANIM` framings, are **answered** and validated 9/9 and 566/566.)

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
  milestone built on *unfamiliar* territory (like M3's spawn/collect/exit loop)
  runs far above the board average — which is why option C's *playable* loop is
  not costed at this unit rate (§6.2), while C's animated slice is (§6.1).

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

C is no longer "unbudgeted." The old §6 refused to price it on two grounds —
the map→tile format was unresolved and the window presenter was unscoped. Both
now have measured answers, and the third blocker (what a `GNMY` entry *means*)
is half-answered: enough to price an **animated** slice, not enough to price a
**playable** one. The honest result is that **C has split into two things**, and
only one is a demo we can price today.

| old blocker | research card | outcome | grade |
|---|---|---|---|
| map cell → tile (`Q20`/`Q21`/`Q22`) | `t_830f4d0d` | resolved — `MAP` = N big-endian `u16` `TTAB` indices + N collision bytes; `TTAB` = 16 B records of four `[index, flag]` cells; **0 / 523,229 out-of-bank**; `Q21` bit roles `[V]`, axis pairing `[H]` (`Q33`) | **V** (roles) / **H** (axis) |
| window presenter (unscoped) | `t_5bc2f4cf` | scoped + measured — ctypes+SDL2 blits at 847 fps (~14× headroom) | **V** |
| `GNMY` entry meaning | `t_050db875` | layout recovered (`x`/`y` are pixel coords, V); *spawn/collectable/exit* semantics not a unique type (0/74 once-per-world) | **V layout / H meaning** |

### 6.1 The costable part — C-animated

**C-animated** is a live window showing the real world animating at 60 Hz with
correctly-composed tile art and the correct population density, driven by the
scripted walk-right/jump input that already exists (`engine/run.py`, V). No
keyboard, no player, no collect/exit — motion, not play. It is costable now:

| piece | cards (profiles) | money (off-peak) | wall-clock | evidence |
|---|---|---|---:|---:|---|
| window presenter (ctypes+SDL2) | 3–4 (2–3 specialist + 1 reviewer) | ≈$0.50–$0.66 | 0.53–1.38 h | V — `44-presenter-options.md`, blit spike |
| tile-art composition (Q20 port) | 2–3 (1–2 specialist + 1 reviewer) | ≈$0.33–$0.50 | 0.31–0.96 h | V — `t_830f4d0d`, 104/104 planes |
| GNMY population density | 1–2 (specialist [+ reviewer]) | ≈$0.17–$0.33 | 0.22–0.54 h | V — `t_050db875`, pixel coords |
| **C-animated total** | **6–9** | **≈$0.99–$1.49** | **~1.1–2.9 h** | |

*Derived:* each row is its card count × the §3 unit (~42.0 k output / ~102 k
fresh / ≈$0.165 off-peak); the total is ≈252–378 k output · ≈612–918 k fresh ·
≈22.3–33.5 M cached. Wall-clock is specialist 13–25 min + reviewer 5.5–7.5 min
per card (§3.1). The low end assumes nearest scaling for both profiles (no
`epx-aa` port) and the population card folded into the tile-port PR; the high
end adds the `epx-aa` parity card and a separate population card.

**What the research bought.** The old §6 folded this whole loop into "M3 —
unbudgeted, weeks, order-of-magnitude" (`40-budget.md` §7's ≈$4.28 @pro row).
Two of its three blockers are now closed, so the price fell from "weeks" to
two concrete ports: the map→tile half is now a **≈$0.33–$0.50 port** (was an
unresolved format) and the window is **≈$0.50–$0.66** (was "future"). Only the
third — `GNMY` *semantics* — stays open, and it is now one named experiment,
not a blank.

### 6.2 The part that still cannot be closed — C-playable

A *playable* slice additionally needs the player to **spawn** somewhere, to
**collect** items, to **exit** a level and **advance** to the next. All four
read the same thing: which `GNMY` entries are the spawn, the collectables and
the exit. That is `Q32`, and `t_050db875` left it **unresolved** — the layout
is V but the meaning is H, and the obvious hypothesis ("the unique entry is the
spawn") is **falsified** on retail data. So C-playable is a **milestone with a
known first step, not a demo**, and no total is invented for it.

The first step is the **Q32 experiment**: trace the consumer of the `GNMY`
flags' 2-bit field (stored to `obj+0x12`) and the bit-15 extra word (`obj+0x4`)
in `LOMAX.EXE` to learn how the game itself decides spawn/collectable/exit.
That is **1–2 specialist cards, ≈$0.17–$0.33 off-peak**. Only its result prices
the loop: if the 2-bit field is a clean spawn/collectable/exit enum, the
playable loop is 2–3 more cards; if it needs a runtime probe under Wine or
per-world special-casing, it is more. Both are milestones, priced *after* the
experiment, not before.

The other known addition is **M5 input** (keyboard → `Input`), already
re-forecast at **~7 cards / ≈$1.16 off-peak / ~1.2–1.9 h** (3 specialist + 3
review + 1 lead synthesis — a re-forecast, not a measurement; the old §6 and
the `40-budget.md` Revision). M6 audio stays optional and out of C's core.

So the honest number for C-playable is **≈$2.32–$2.98** for everything *except*
the playable loop itself — C-animated (≈$0.99–$1.49) + M5 (≈$1.16) + the Q32
experiment (≈$0.17–$0.33) — and the loop is priced after the experiment. To
approve something *today*, approve C-animated, or approve the experiment and
let the loop price itself.

### 6.3 The V/D/H rule, restated

Every figure above carries a grade, and a number resting on an **H** is labelled
as one. The map→tile and window rows rest on **V** measurements (validated on
all 104 retail planes; a blit spike run on this machine). The population row
rests on **V** coordinates, but the coordinate→walkability link stays **H**
(`t_050db875`: placements skew toward solid ~7.6×, a correlation, not a proof).
The playable loop rests on **H** until `Q32` is measured. Do not let "6–9
cards" harden into certainty: the two ends exist because the `epx-aa` parity
card and the population card are decisions, and because `Q32`'s answer is not in
yet.

## 7. Recommendation — do **B** now, then **C-animated** as v0.5, and price C-playable after the Q32 experiment

**B (~$0.50)** is still the right first dollar: it shows the project *doing the
thing it exists to do* — running the game's own data at 60 Hz — for three cards
and ~0.35–0.57 h, and it is the entire emotional payoff ("the engine is alive")
for $0.17 more than A. What changed since the old §7 is what comes *after* B:
C stopped being "weeks" and became a ladder with a number on every rung except
the last.

- **C-animated ≈$0.99–$1.49 (6–9 cards)** — a live window with correct tile art
  and population density. This is the "the game is coming back" shot B cannot
  deliver: B is a recording, C-animated is a window. That is the v0.5 target.
- **Q32 experiment ≈$0.17–$0.33 (1–2 cards)** — the one open question left
  (which `GNMY` entry is the spawn/collectable/exit). Cheap, and it is the
  *gate*: run it and the playable loop stops being an H and gets a price.
- **C-playable** — C-animated + M5 input (≈$1.16) + the experiment + the loop
  the experiment prices. A milestone (v0.6/v0.7), not a demo.

So the recommendation is **B now**; if B lands well, **C-animated next** (v0.5)
with the **Q32 experiment bought alongside it** so the step after that is a
priced milestone rather than another blank. Do *not* approve "C" as a single
number yet — approve C-animated, or approve the experiment.

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
