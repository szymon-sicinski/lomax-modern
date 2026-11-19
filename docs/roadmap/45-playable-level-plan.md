# 45. One playable level — plan + budget

The demo shipped as **C-animated** — a live SDL2 window showing the real world
animating at 60 Hz with correctly-composed tile art and population markers,
driven by a *scripted* walk-right/jump input. This document is the plan and
budget to take the next step: **one level fully playable** (C-playable) — the
player spawned from the game's own data, real collectables, a real exit, and
keyboard input, so a human can actually play VILLAGE end to end.

This document supersedes the "cannot be priced yet" conclusion in
[`43-demo-plan.md`](43-demo-plan.md) §6.2, because its blocker has closed:
**Q32 is answered** (card `t_6fa1ecf8`, docs PR #50). The spawn/collectable/exit
identity is **not** a `GNMY` flag field — it is the `NMY` record's **name**,
resolved through an 89-entry name table into a per-type handler. That makes the
spawn → collect → exit loop designable from evidence instead of guesswork, and
this document prices it.

## Table of contents

1. [What "one level fully playable" means](#1-what-one-level-fully-playable-means)
2. [Scope table](#2-scope-table)
3. [The card graph](#3-the-card-graph)
4. [Budget](#4-budget)
5. [Risks and the cheapest experiment for each](#5-risks-and-the-cheapest-experiment-for-each)
6. [The checkpoint](#6-the-checkpoint)
7. [Guardrails and reproduce](#7-guardrails-and-reproduce)

---

## 1. What "one level fully playable" means

The five things the request must pin down, each decided here.

1. **M5 input — keyboard/gamepad → `Input`, at the original logic rate.**
   **In scope, keyboard only.** The engine already advances at a fixed 60 Hz
   tick ([`engine/entities.py`](../../src/lomax_modern/engine/entities.py)
   `TICK_RATE = 60`) and consumes a per-tick `Input(left, right, jump)`. The
   slice drives it with a script; the missing piece is reading the keyboard and
   feeding it into the existing tick. **Gamepad, hot-plug, presets and
   rebinding are deferred** — they are the "generous" half of M5
   ([`10-milestones.md`](10-milestones.md) §M5) and none of them is required to
   *prove* the level is playable.

2. **Player entity from the game's own data.** **In scope, static frame.**
   `Start` placement supplies the spawn (the level-load scan at `0x40ED7C`
   finds the type-0 `Start` node and builds the player on its plane). The
   player *sprite* is **in scope as one static frame** decoded from `ANIM` —
   the framing is recovered (566/566) but the **pixels are not yet decoded**,
   so this is real work, priced as its own card. **Sprite *animation* (walk/
   jump/idle frame cycling) is deferred** to a follow-up card: it is the
   largest single risk in the plan and is not needed to prove playability.

3. **Collectables — `Moneybag`.** **In scope.** `Moneybag` (name prefix `Mone`)
   is the collectable (`0x428190`). Spawn from placement, collide, despawn,
   increment a counter. Sibling types from the 89-entry name table are
   **recognised but not wired**: only `Start`/`Exit`/`Moneybag` drive the
   acceptance; `Finish` (end-of-plane) and `Revive` (checkpoint) are classified
   and left inert.

4. **Exit and level transition.** **Exit in scope; next-level deferred.**
   `Exit` (`0x427670`) is proximity → level-complete. **Finishing one level is
   the acceptance** — reaching `Exit` on VILLAGE sets `complete`. The
   *next-level* transition is deferred: the plane→level sequence lives in the
   executable's level table (Q3), which this repository never reads.

5. **Game rules that make it *playable*.** Three sub-decisions:
   - **Gravity/jump tuned to the original rates — in scope, research-gated.**
     The constants were "our own design, no claim to match"; P6 read the
     original rates from the player-movement code and they are cleanly
     readable — `WALK_SPEED 2.0`, `GRAVITY 0.375`, `JUMP_SPEED −4.0`,
     `MAX_FALL 6.0` (`docs/file-formats.md` §2.9), so `entities.py` now
     carries those measured values with their virtual-address citations.
   - **Death/respawn / fail state — deferred.** There is no hazard semantics
     yet (Q31, per-value collision bytes, is unresolved), so a fail state has
     nothing to trigger on. Out of scope, named, not forgotten.
   - **HUD showing the collectable count — in scope.** The window HUD line
     already prints `fps`/plane/tiles/camera; it gains `collect N/M`.

## 2. Scope table

| Piece | In / out | Why |
|---|---|---|
| Keyboard → `Input` at 60 Hz | **in** | the difference between demonstrable and playable |
| Gamepad / hot-plug / presets / rebinding | out (defer) | generous-M5; not needed to prove playable |
| `Start` → player spawn | **in** | the loop needs a real spawn |
| `NMY` name surfacing + role classifier | **in** | prerequisite for Start/Exit/Moneybag |
| Player sprite, static `ANIM` frame | **in** | "player from the game's own data"; a marker does not count |
| Sprite *animation* (cycle by state) | out (adjacent) | real cost, largest risk; not needed to prove playable |
| `Moneybag` collectable (spawn/collide/despawn/count) | **in** | named requirement |
| Sibling name-table types | out (classified only) | only `Moneybag` drives acceptance |
| `Exit` → level complete | **in** | named requirement |
| Next-level transition | out (defer) | level sequence is Q3, inside the executable |
| Gravity/jump tuned to original rates | **in** (delivered by P6) | measured, not floaty: `2.0`/`0.375`/`−4.0`/`6.0` (`docs/file-formats.md` §2.9) |
| Death/respawn / fail state | out (defer) | no hazard semantics yet (Q31) |
| HUD collectable count | **in** | progress must be visible |
| Audio / music | out (M6) | separate milestone; data carries no music track |
| Save states | out (defer) | `Snapshot` is already designed; persistence is M5 UX, not one level |

## 3. The card graph

Seven implementation cards (`P1`–`P7`), one reviewer pass per implementation
card (`R1`–`R7`, created when each PR opens and referencing its number), and one
lead synthesis (`S1`). `P1`–`P7` are created on the board as children of this
plan card, so they do not dispatch until the plan is accepted.

```
P1 ──► P2 ──┬──► P4 ──► (checkpoint)
             ├──► P5
             └──► P7
P3 ─────────► P4
P6  (parallel, independent)
```

Critical path `P1 → P2 → P4` is three cards; `P3` and `P6` run in parallel with
the data-semantics chain, `P5` and `P7` fan out after `P2`.

| Card | Assignee | Skills | Depends on | Acceptance |
|---|---|---|---|---|
| **P1** NMY name + role classifier | specialist | retro-game-modernization, github | — | `decode_nmy` returns each record's `name` (first four bytes, byte-swapped to ASCII per Q32); `role(name)` maps the documented 4-byte prefixes `Star`/`Exit`/`Fini`/`Revi`/`Mone` to `start`/`exit`/`finish`/`revive`/`moneybag` (else `unknown`); unit tests over synthetic `NMY` payloads |
| **P2** wire GNMY semantics into `Level` + slice | specialist | retro-game-modernization, github | P1 | `Level` resolves `spawn`/`collectables`/`exits` from the playfield plane's `GNMY` entries via role; `run_slice`/`new_game_state` drop the `first_passable_cell`/`_last_passable_cell` placeholders; `slice` reports `spawn: Start (x,y)`, `collect: N Moneybag(s)`, `exit: Exit (x,y)` on VILLAGE |
| **P3** keyboard → `Input` mapping | specialist | retro-game-modernization, github | — | a pure `Keymap` turns held+pressed keycodes into `Input`, jump edge-triggered; unit tests cover left/right exclusivity, jump edge, no-key neutral — no display required |
| **P4** interactive `play` loop | specialist | retro-game-modernization, github | P2, P3 | `lomax-modern play <install> --world VILLAGE` opens the SDL2 window and the player moves/jumps from the keyboard at 60 Hz; Esc/close quits; `SDL_VIDEODRIVER=dummy` headless smoke test exits cleanly |
| **P5** player sprite from `ANIM` (static frame) | specialist | retro-game-modernization, github | P2 | `render_tiles` draws the player as a decoded `ANIM` sprite (the standing frame) instead of the marker; a self-generated 4-bit fixture decodes to expected pixels and a real VILLAGE frame shows the actual Lomax sprite |
| **P6** tune player physics to original rates | specialist | retro-game-modernization, github | — | `entities.py` constants carry their source (measured VA citation, or `[H]` placeholder); a unit test asserts the values are the measured facts or the documented placeholders |
| **P7** HUD collectable counter | builder | github | P2 | the window HUD line prints `collect N/M` (collected vs total `Moneybag`s); a unit test covers the formatter |
| **R1–R7** review of the P-card's PR | reviewer | github | its P card | approve-or-changes verdict naming the PR's current head, per the merge gate |
| **S1** assemble + merge the landed PRs | lead | github | P1–P7, R1–R7 | re-derive every merge-gate condition live; merge via merge commit |

Each implementation card body carries the standard contract (Context / Goal /
Acceptance / Verify / Constraints), `workspace_kind="worktree"` (code changes),
`completion_contract="local-only"`, and the guards: no game bytes, no 64-hex
hashes, `dependencies = []`, read-only install via `LOMAX_GAME_DIR`, off-peak
dispatch, merge only through the gate.

## 4. Budget

Unit rate: **≈$0.165 per card, off-peak**, the board-wide measured average
([`43-demo-plan.md`](43-demo-plan.md) §3, reproduced by
`scripts/token_cost_report.py --board retrolab --json`; ≈42.0 k output / ≈102 k
fresh / ≈3.72 M cached tokens per card, ~$9.59 over 58 cards).

| line | cards | profile band | money |
|---|---:|---|---:|
| implementation | 7 (6 specialist + 1 builder) | specialist 13–25 min, builder 7.7–13.3 min | — |
| review passes | 7 (one per P-card) | reviewer 5.5–7.5 min | — |
| lead synthesis + merge | 1 | 14.9 + 2.0 min | — |
| **expected total** | **15** | | **15 × $0.165 = $2.48** |

**Wall-clock band.** Summing the measured per-profile per-card minutes
([`40-budget.md`](40-budget.md) Revision):

- 6 specialist × 13–25 min = 78–150 min
- 1 builder × 7.7–13.3 min = 7.7–13.3 min
- 7 reviews × 5.5–7.5 min = 38.5–52.5 min
- 1 synthesis + merge ≈ 17 min

→ **≈2.4–3.9 h** of agent time, summed across cards. The critical path is only
three cards (`P1 → P2 → P4`), so with `P3`/`P6`/`P5`/`P7` overlapping, elapsed
time is lower than the sum.

**High band.** The $0.165 unit already embeds the measured rework rate (41.9 %
changes-required over the M2–M4 verdicts). The three *unfamiliar* cards — `P5`
(sprite pixel format, unproven), `P6` (physics reverse-engineering), `P4`
(input feel) — are where the M4 leaf-plus-integration double-review pattern
would bite. If each of those three cycles one extra pass, the total grows by
~5–6 cards:

- **high ≈ $3.30–$3.50 off-peak** (~1.3–1.4× expected), triggered specifically
  by a second cycle on the unfamiliar cards, **not** by a blanket factor.

There is no lower-than-expected number to state honestly: the unit is
rework-inclusive and is a **lower bound** (34 of 92 measured runs had no
matching log line, so the true per-card average is at least $0.165).

**Total and delta.**

| item | cards | money (off-peak) |
|---|---:|---:|
| C-animated (already shipped) | 6–9 | ≈$0.99–$1.49 ([`43-demo-plan.md`](43-demo-plan.md) §6.1) |
| **this milestone — new work** | **15** | **≈$2.48** (high ≈$3.50) |
| **C-playable end to end (cumulative)** | **21–24** | **≈$3.47–$3.97** |

None of the 15 cards is a C-animated card, so the new spend is the **whole
$2.48**, not a delta over the shipped milestone. Adding the shipped C-animated
band gives **21–24 cards ≈$3.47–$3.97** for one playable level end to end.

This **supersedes** [`43-demo-plan.md`](43-demo-plan.md) §6.2 rather than adding
to it. §6.2's "≈$2.32–$2.98 for everything *except* the playable loop" composes
as C-animated ($0.99–1.49) + the M5 re-forecast ($1.16) + the Q32 experiment
($0.17–0.33). This plan replaces that M5 re-forecast with an explicit 15-card
graph and retires the Q32 experiment line entirely, because Q32 is answered
([`05-open-questions.md`](../research/05-open-questions.md)). The loop is
therefore inside the $2.48, not on top of it.

## 5. Risks and the cheapest experiment for each

| Risk | What could double | Cheapest experiment to retire it |
|---|---|---|
| **Sprite / `ANIM` pixel decode (P5)** — the 4-bit packed pixel path is unproven (framing is V, pixels are untested) | P5 becomes spike → decode → re-review, and could drag the milestone | a self-generated 4-bit `ANIM` fixture **plus one real VILLAGE `ANIM` chunk**, decoded and eyeballed as a sprite. If it does not decode cleanly, descope P5 to "marker + documented blocked" and the milestone still completes — a marker is still provably playable |
| **Exit handler semantics (P2/P4)** — `Exit` = proximity → complete is documented, but whether exit is gated on "all `Moneybag`s collected" is not pinned | P2/P4 grow an "exit requires N/N" gate and a re-review | a one-line close read of handler `0x427670`: does it test the collect counter before setting complete? The slice report already prints the `Exit` placement, so the probe is static, not a runtime experiment |
| **Input feel (P3/P4)** — jump edge-triggering, key-repeat, and whether the placeholder physics feel floaty | P4 re-cycles after playtesting | the existing `default_script` already walks and jumps; after P4, a 10-minute playtest against the placeholder physics retires most feel risk *before* P6 |
| **Physics tuning (P6)** — the original constants may not be cleanly readable (computed or table-driven in the executable) | P6 becomes a deeper RE pass | the static read itself is the experiment; the fallback (keep placeholders, mark `[H]`) is already the acceptance, so the card cannot blow up silently |
| **Name ambiguity (P1)** — names match on the first four bytes (`Start`→`Star`, `Moneybag`→`Mone`) | a wrong prefix match mislabels placements | a unit test asserting `Star`→start (not `Start`→start) and `Mone`→moneybag retires it at P1, before anything depends on it |

## 6. The checkpoint

The smallest slice that is **provably playable** is `P1 + P2 + P3 + P4 + P7` —
real spawn/collectable/exit placements, keyboard input, and the collectable
count on the HUD — with the **existing marker sprite and placeholder physics**.
That is **5 implementation + 5 review = 10 cards ≈ $1.65 off-peak**.

After the checkpoint you can play VILLAGE end to end: move with the keyboard,
collect the `Moneybag`s, reach `Exit`, and watch the counter. If the *feel* is
wrong — floaty jump, wrong speed — stop before `P5`/`P6` and say so; those two
cards are where the remaining ~$0.83 is spent, and neither is needed to prove
the level is playable.

## 7. Guardrails and reproduce

- **No game bytes** in the repo, tests, CI logs or captures; the install is
  read-only and pointed at via `LOMAX_GAME_DIR` (the real path here is
  `/game-files/LOMAX (1)/LOMAX`). Tests build synthetic fixtures; nothing
  decrypts or redistributes the executable.
- **No 64-hex hashes** of game binaries in any transcript; `doctor` reports
  hashes masked.
- **`dependencies = []`** stays empty (SDL2 is a system library via ctypes;
  the `ANIM` decode and keyboard mapping add no package).
- **Off-peak dispatch only; merge only through the gate** (reviewer verdict
  naming the current head, all checks green, `mergeable: true`, merge commit).
- The verification command every card body ends with:

```bash
git -C "<install>" rev-parse --show-toplevel 2>/dev/null && echo "install must not be a repo" || true
grep -rniE '[0-9a-f]{64}' src tests docs && echo "FAIL: hash in tree" || true
python3 -m pip install --user pytest && python3 -m pip install --user -e .
python3 -m pytest tests -m "not realgame" -q
```
