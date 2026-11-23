# 46. Character animation — plan + budget

The playable level shipped (**C-playable**, PR #61) and PR #64 gave the moving
player `Hero.RUN`'s whole-body sprite. The maintainer's next milestone is
**more animations of the player character**, and he delegated the scoping. This
document is that scope, the slicing into reviewable PRs, and the cost in tokens
and dollars. It is **planning only**: no code, and no implementation card exists
until the maintainer approves this PR.

Grades used throughout: **[V]** located in the disassembly and recorded in
[`../file-formats.md`](../file-formats.md); **[M]** measured by this document,
reproduced with the command in [§7](#7-reproduce-every-number); **[H]**
hypothesis — a guess that the data or the name suggests, not a finding. A
number with none of these is quoted from a cited document.

## Table of contents

1. [Goal and acceptance criteria](#1-goal-and-acceptance-criteria)
2. [Candidate animations](#2-candidate-animations)
3. [Slices](#3-slices)
4. [Budget](#4-budget)
5. [Coordination overhead, and how this plan avoids it](#5-coordination-overhead-and-how-this-plan-avoids-it)
6. [Risks and non-goals](#6-risks-and-non-goals)
7. [Reproduce every number](#7-reproduce-every-number)
8. [Appendix A — every `Hero` clip in `MAIN.WLD`](#8-appendix-a--every-hero-clip-in-mainwld)

---

## 1. Goal and acceptance criteria

**Goal.** The player stops being a two-state sprite (stand, run) and becomes a
small state machine that plays the *original's own clips* for **standing,
moving, jumping/falling and landing**, with each pose placed where the clip's
`dx`/`dy` put it instead of bottom-pinned. A stretch tier adds **ducking** and
the **idle fidget**. Attack, hurt/death, climbing and every other clip are
deferred (§2, §6), with reasons.

### 1.1 Starting point (read from `main` = `457aa53`)

| fact | grade |
|---|---|
| The standing player draws `STA1`'s whole-body layer (sprite byte 27 → `type_index` 26, 44 × 47–49); the moving player draws `RUN`'s (byte 23 → 22, 48–62 × 34–43, 12 poses, one pose per 3 ticks, mirrored for facing) | shipped, [`05-open-questions.md`](../research/05-open-questions.md) Q36/Q37 |
| The `NMY` sprite byte is **1-based** (`anim_clip.chunk_index_for_sprite`); byte 0 and step 0 draw nothing | [V] `file-formats.md` §2.6.1 |
| `render_tiles` discards each pose's `dx`/`dy`; the bottom-pinned `RUN` head bobs by **9 px** across the cycle | [M] §8 column "top spread" (RUN = 9); cited Q36 |
| `WALK` composites one figure in 10/10 poses at 8-connectivity, 2/10 at 4-connectivity | cited Q34/Q35 (not re-run here) |
| The 3-tick hold, mirroring-as-facing and the choice of `RUN` for "moving" are `[H]`; `WALK` is the slow-walk clip, gate `\|vx\| ≤ 2.0` at VA `0x411F79` | cited `file-formats.md` §2.6.1 |
| The engine's inputs are `left` / `right` / `jump` only; it knows `on_ground`, `vx`, `vy`, `facing` | `engine/entities.py`, `engine/state.py` |

### 1.2 Reachability — what the real data allows

Card H of the previous milestone (`t_1848654b`, "60 s run @ ≥ 55 fps") is the
cautionary case. Its text asks for a 60 s **run**; a criterion that reads as a
60 s **walk** cannot be met, because the scripted walk ends at the plane edge.
Measured here, on the retail install, with the engine's own `default_script`
(walk right, jump every 45 ticks):

| measurement | value | grade |
|---|---|---|
| `VILLAGE` playfield width / the tick the scripted walk stops advancing | 4,880 px / tick 2,443 = **40.7 s**, at x = 4,868 | [M] `reach` |
| `ED` playfield width / the same stall | 3,744 px / tick 1,906 = **31.8 s**, at x = 3,732 | [M] `reach` |
| a *held* right key alone on `VILLAGE` | blocked by a wall after 41 ticks = **0.7 s**, x = 180 | [M] `reach` |
| a flat-ground jump (engine constants) | **21 airborne ticks** = 0.35 s, apex 19.4 px | [M] `reach` |
| first 120 ticks of `default_script` on `VILLAGE` | 4 airborne spans — ticks 0–17 (the fall from the spawn), 20–39, 65–78, 110–119 (open) — **62 airborne ticks**; 9 grounded-moving; 49 grounded with `vx == 0` | [M] `reach` |

**Rule for this milestone:** *no criterion may require more than **30 s** of
scripted or held play* (the shortest measured edge is 31.8 s), and every
criterion below names the tick or second at which the thing it asks for first
happens, taken from this table. The leftover (b) — card H's unreachable
criterion — is closed by this rule. It is **not** in
[`45-playable-level-plan.md`](45-playable-level-plan.md) (the string does not
occur there: `grep -n "60 s" docs/roadmap/45-playable-level-plan.md` is empty),
only in that card's body, so there is no document line to edit.

Two further observations the criteria use: the 49 grounded ticks with `vx == 0`
are consistent with the player **pushing into the wall at x = 180** (input right,
velocity zeroed by the collision — the hold-right test blocks at x = 180 `[M]`,
but I did not trace those 49 ticks one by one `[H]`), which today draws the
standing sprite; and a
`JMP1`/`JMP2` clip is 7 steps, so at the engine's 3 ticks per pose it plays for
**21 ticks — exactly the measured flat-ground airtime** `[H]` (a coincidence of
two chosen/derived numbers, worth testing, not evidence).

### 1.3 Acceptance criteria

Each is observable on the running game or its headless twin. `<install>` is the
read-only retail folder (`$LOMAX_GAME_DIR`). **AC1–AC7 are the milestone;
AC8–AC9 belong to the stretch tier (§3).** "Slice" names the PR that makes the
criterion pass.

| # | What the maintainer sees | Command that shows it | Reachable because | Slice |
|---|---|---|---|---|
| **AC1** | While the player is in the air it draws a jump clip, never the standing or running sprite. The report names what was drawn and for how many ticks. | `python3 -m lomax_modern slice "<install>" --world VILLAGE --frames 120 --out /tmp/f` → a `clips:` line such as `clips: STA1 n, RUN n, JMP1 n …` whose air-clip tick total **equals the 62 airborne ticks** and which shows **no** `STA1`/`RUN` tick inside an air span | the first airborne tick is tick 0 (spawn fall), the first jump is tick 20 (0.33 s) | AN2 adds the line, AN4 makes the air clips appear |
| **AC2** | Touching down plays the landing pose once, then returns to stand/run. | same command: `clips:` shows `LND1` ≥ 1 tick after each air span | landings at ticks 18, 40, 79 inside the 120 | AN4 |
| **AC3** | The character no longer jitters its head up and down as the run cycles; feet and head sit where the clip's offsets put them. | `python3 -m lomax_modern anim-clip "<install>" --name RUN --out /tmp/c` prints an `anchor:` line giving the **bottom-pinned** top spread (**9 px**, today's value) and the **offset-placed** one; the second is the value AN1 freezes in `file-formats.md` §2.6.2 | pure data; no play time | AN3 |
| **AC4** | In the live window the same behaviour, played by hand: stand, run right, jump over the wall at x = 180, land. | `python3 -m lomax_modern play "<install>" --world VILLAGE --seconds 20`; headless smoke `SDL_VIDEODRIVER=dummy … --seconds 5` exits 0 | the wall is 0.7 s from the spawn; 20 s ≪ the 31.8 s limit | AN4 (visible), AN2 (no regression) |
| **AC5** | Clip choice is **data**, not hard-coded sprite ids: a clip tag → poses table. A moving, standing and airborne player each resolve through it. | `python3 -m pytest tests -m "not realgame" -q` (synthetic fixtures); each slice adds its own tests | none needed | AN2 |
| **AC6** | `file-formats.md` §2.6.2 lists **every clip the engine draws** with its selector graded [V]/[H] and the VA where known; Q38 and Q39 are each answered or restated as open with the narrowing. | `grep -n "2.6.2" docs/file-formats.md`; `grep -n "Q38" docs/research/05-open-questions.md`; `grep -n "Q39" docs/research/05-open-questions.md` | docs | AN1 |
| **AC7** | The repository stays clean-room: no game bytes, no new binary files, no hashes. | the §7.1 guard block (below) prints nothing | — | every slice |
| **AC8** *(stretch)* | Holding **Down** on the ground crouches (`DUCK`); releasing stands. | `play … --seconds 20`, hold ↓; unit test on `Keymap` + the selector | instant | AN5 |
| **AC9** *(stretch)* | Standing still long enough plays the idle fidget (`STA2`) instead of freezing on `STA1`. | `play … --seconds 20`, touch nothing for the chosen idle delay (**[H]**, set ≤ 10 s); unit test on the selector | idle delay ≤ 10 s | AN6 |

**The witness the maintainer can watch.** The closing card renders
`slice --frames 120` and `gif` into a GIF **attached to the card, never
committed** (a rendered frame carries game pixels; the same rule as
`t_1848654b`).

---

## 2. Candidate animations

### 2.1 What exists — measured

`Hero` is one `NMY` record in `MAIN.WLD` with **47 clips** (the record's
`W_B`). No other world has a `Hero` record `[M]`:

| world | `NMY` records | clips | distinct tags | has `Hero` | tags shared with `Hero`'s vocabulary |
|---|---:|---:|---:|---|---|
| BONUS | 30 | 28 | 14 | no | WALK |
| ED | 44 | 58 | 34 | no | BOOM, IN, OUCH, OUT, WALK |
| HAUNTED | 74 | 138 | 74 | no | BOOM, IN, OUCH, OUT, WALK |
| MAIN | 24 | 142 | 107 | yes | (all 47) |
| MAP | 17 | 11 | 5 | no | — |
| MEDIEVAL | 68 | 115 | 61 | no | BOOM, OUCH, WALK |
| TITLE | 22 | 30 | 23 | no | — |
| VILLAGE | 49 | 88 | 51 | no | BOOM, IN, OUCH, OUT, WALK |
| WEST | 53 | 81 | 43 | no | BOOM, IN, OUCH, OUT, WALK |
| **total** | | **691** | | | |

Across the nine worlds there are **691** clips (the figure the earlier docs
cite; the sum re-measured here matches). The `Hero` vocabulary is shared with
other actors: `WALK` appears in six of the eight non-`MAIN` worlds, and
`OUCH`/`IN`/`OUT`/`BOOM` in up to five. Those are **enemy/NPC clips with the
same four-letter names**, not player data — the tag is a generic state name,
which is consistent with a generic actor selector `[H]` and means a tag found
in the executable is not proof the *player* uses it. **Everything the player
can show is in `MAIN.WLD`'s 47 `Hero` clips; none of the other worlds adds a
pose.** (`MAP` and `TITLE` share no tag with `Hero`.)

Appendix A lists all 47 with keyframes, steps, layers (resolved / unresolved
sprite bytes — `169` and a few others are not in any `.WLD`), the body layer's
size range, the bottom-pinned top spread, the `dy + h` range (§2.4) and
the number of times the tag appears as a 4-byte value in `LOMAX.EXE`. That last
column is a **lead for AN1, not a use proof**: 500 random four-letter uppercase
sequences occur in the executable 0.00 times on average (max 1)
`[M] control`, so a count ≥ 2 is above noise — `WALK` 14, `SPIN` 11, `IN` 8,
`OUT` 7, `HELI` 7, `OUCH` 6 — but it counts enemy code too, and `RUN` (1),
`DUCK` (1) and `LND1` (1) sit at the noise level while `JMP1` (3) and `JMP2` (2)
are barely above it, so the executable probably selects those by another route
(an index or a computed state), which is exactly what AN1 must find.

### 2.2 What is known about *when* each clip plays

Almost nothing is located in the disassembly. The complete [V] list:

* **`WALK`** — selected at VA `0x411F79` under a speed gate written `|vx| ≤ 2.0`
  in `file-formats.md` §2.6.1 *(and "below 2.0" in a comment in
  `engine/level.py`: see §2.4, finding 1)*.
* **Two jump kinds** — a post-jump gravity lockout of **5** ticks when jumping
  while moving and **10** for a straight-up jump (VA `0x4106EC`/`0x4106FF`),
  plus stomp/spring/hop impulses (−5/−6/−2), a held-jump reduced-gravity rise,
  and a held-slide/down fall of **0.125** clamped to **1.0** (`0x410B9A`)
  — `file-formats.md` §2.9. These prove the original *has* a moving-jump
  / straight-jump split and a slow-fall state; they do not say which clip each
  one draws.
* **Terrain-dependent walk speed** 1.5 / 2.0 / 2.5 (`0x426DEC`–`0x426E26`).

Everything else below is a **name-based guess [H]**.

### 2.3 The candidate table

> **AN1 outcome (2026-11-23), read this first.** The disassembly pass
> ([`../file-formats.md`](../file-formats.md) §2.6.2) overturns four `[H]`
> entries below. Where this table or §2.4/§3 disagree, §2.6.2 wins.
> (1) **`JMP1` is the straight-up jump and `JMP2` the moving jump** — the
> reverse of the fallback order in §3. (2) **`FLO1`/`FLO2` are the
> fast-fall clips** (`vy` ≥ 2.5), not a slow float, so the engine can already
> trigger them. (3) **`WALK`, not `RUN`, is drawn at 2.0 px/tick** (Q38;
> the gate is `jg`). (4) `STA2` is part of the data-driven idle cycle (frozen
> `STA1` for 30–93 ticks, then `STA1` or `STA2` once), so AN6 needs no invented
> delay, and Q36 is answered. The `dx`/`dy` placement is top-left =
> origin + (dx, dy), y down (Q39).

"In scope" = reachable with today's inputs (`left`/`right`/`jump`) and physics;
"stretch" = needs one new input or one resolved question; "deferred" = needs a
mechanic the engine does not have. Sizes are `[M]` from Appendix A.

| clip | steps | what the name suggests `[H]` | trigger | engine can produce the trigger today? | verdict |
|---|---:|---|---|---|---|
| `STA1` | 7 | stand | `[H]` (vx == 0) — shipped | yes | **in scope** (already drawn; re-anchored by AN3) |
| `RUN` | 12 | moving | `[H]` — and see §2.4 finding 1 | yes (`vx ≠ 0`) | **in scope** (re-anchored; the WALK/RUN split is AN1's first question) |
| `WALK` | 10 | slow walk | **[V]** gate `\|vx\| ≤ 2.0` at `0x411F79`; strictness unsettled | the engine's only ground speed is 2.0, exactly on the gate (§2.4, finding 1); it has no terrain speeds and no acceleration ramp | **in scope for AN1** (decide the gate); drawn only if AN1 shows the player reaches it |
| `JMP1`, `JMP2` | 7, 7 | moving jump / straight jump | the *split* is **[V]** (§2.9: lockout 5 vs 10); which clip is which is `[H]` | yes (`jump`, `vx ≠ 0` or `== 0`) | **in scope** (AN4) |
| `LND1` | 1 | landing | `[H]` (first grounded tick after air) | yes | **in scope** (AN4); one step, held 3 ticks `[H]` |
| `FLO1`, `FLO2` | 5, 5 | float / slow fall | mechanism **[V]** (0.125 fall, `0x410B9A`); clip mapping `[H]` | **no** — the engine has no reduced-gravity fall (§2.9 notes the adoption as follow-up) | **deferred** |
| `DUCK` | 6 | crouch | `[H]`; the down input exists in the original **[V]** (`0x410B9A`) | needs `Input.down` + a key | **stretch** (AN5) |
| `STA2` | 10 | idle fidget after waiting | `[H]` | needs an idle timer; and Q36: its steps overrun a layer's frames (10 steps over `type_index` 27's 7) | **stretch** (AN6, only if AN1 settles Q36) |
| `BRAK` | 7 | brake / turn | `[H]` | **no** — `vx` flips instantly, there is no momentum to brake | deferred |
| `EDGE` | 10 | teeter on a ledge | `[H]` | partly (ledge probe) but ledge semantics rest on Q31 | deferred |
| `RU45` | 8 | run up a slope | `[H]` | **no** — no slope semantics (Q31) | deferred |
| `PUSH` | 14 | push a block / wall | `[H]` | the 49-tick wall contact in §1.2 is a *possible* trigger, but the original probably pushes an object | deferred |
| `THR1`–`THR3`, `SPIN` | 5, 5, 4, 8 | throw / spin attack | `[H]` | **no** — no attack input, projectile or enemy collision | deferred (next milestone candidate) |
| `OUCH`, `OHNO`, `TUMB`, `DIZZ`, `PLOP`, `PLO2`, `DROW`, `BOOM` | 3, 3, 9, 8, 5, 1, 14, 3 | hurt / death / stun / splash | `[H]` | **no** — no hazard semantics (Q31), fail state deferred in `45` §1 | deferred |
| `CLIM`, `CLI2`–`CLI4`, `JPAD`, `HELI`, `HEL0`–`HEL8`, `BUI1`, `BUI2`, `DIG1`, `WAHL`, `IN`, `OUT` | 3–21 | climb / jetpad / helicopter / build / dig / doors | `[H]` | **no** — each needs a world object the engine lacks | deferred |

**Used in the original vs guessed.** Of 47 clips, the repo has located the
selector for **one** (`WALK`) **[V]**, the *existence* of two jump kinds and a
slow-fall state **[V]**, and nothing else. That is the honest count; the rest
of the table is naming. This is why AN1 (§3) is first: the slices that follow
are cheap only if their selection rules are not guessed.

### 2.4 Two findings that change the plan

**Finding 1 — "moving = `RUN`" may be wrong at the default speed (Q38).**
`file-formats.md` §2.6.1 says `WALK` is chosen at `|vx| ≤ 2.0`, the engine's
`level.py` comment says "below 2.0", and §2.9 gives the terrain-0 maximum
horizontal speed as **exactly 2.0** (`WALK_SPEED`). If the gate is `≤` the
original draws `WALK` for the ordinary walk and `RUN` only on terrain whose
speed is 2.5; PR #64's choice of `RUN` for every `vx ≠ 0` would then be the
**exception, not the rule**. Neither reading is re-verified here (I read no
disassembly). It is cheap for AN1 to settle and it decides whether `WALK` or
`RUN` is the everyday clip.

**Finding 2 — the `dx`/`dy` convention is not settled by the repo's own claim
(Q39).** §2.6.1 records "a layer draws at `(dx, −dy)`" **[V]**. Reading the
fields the other way — layer **top = `+dy`** — makes the body layer's bottom edge
`dy + h` is **constant to the pixel** in **24 of the 47 clips** (19 of them over
more than one body keyframe; 5 have a single keyframe, so are trivially
constant — "keyframe" here counts only the records whose sprite byte resolves
to the body layer, per clip; this count is not an Appendix A column (its
*keyframes* column counts all layers) and was recomputed independently by the
reviewer of PR #65). The constant is **+1** in 16 of the 24 — `WALK`, `STA1`, `STA2`,
`DUCK`, `BRAK`, `EDGE`, `DIG1`, `DIZZ`, `IN`, `OUT`, … — and 6–7 in `FLO1`/`FLO2`,
`CLI2`–`CLI4` and `THR3` (`HEL4` −1, `PLO2` 11). It is **not**
constant where the body moves: `RUN` takes the values {−6, −1, 0, 1}, `JMP1`
{−17 … +1}, `JMP2` {−15 … +1}. That reads like **"feet on the origin, give or
take a pixel"** — a far more natural anchor than the bottom-pinning
`render_tiles` uses — and it makes `RUN`'s offsets mostly "feet down" with a
7 px lift on some poses `[H]`. The two conventions are different readings of the
same bytes; which is right decides how AN3 places every pose, and I have not
reconciled them against the blit code. AN1 does. **Until then the bottom-pinned
`RUN` bob of 9 px is the artefact to fix and the `dy + h` regularity is the best
candidate for the fix `[H]`.** `top spread` (bottom-pinned) exceeds 4 px in
**23** of the 47 clips, so the anchor is the prerequisite for every clip that is
not `STA1`/`LND1`/`FLO`.

**A hazard inside finding 2: the jump arc may be counted twice.** `JMP1`'s body
bottom edge spans **18 px** under that reading (−17 … +1), against the engine's
measured flat-ground apex of **19.4 px** (§1.2). If the clip's offsets already
encode the jump's rise, then applying `dy` on top of the engine moving the
player up by the same arc would draw the sprite about twice as high `[H]`. This
is a reason AN1 reads the blit *before* AN3 writes anything, and the AN3
acceptance includes an air-pose check (§6).

---

## 3. Slices

Six PRs: four in the milestone, two stretch. Each is independently
reviewable, branches from the then-current `main`, and carries the standard
card contract (Context / Goal / Acceptance / Verify / Constraints) and the
routing note: code and the reviewer's verdict come from
`.claude-agent/bin/claude-task`, the worker owns the brief, verification, PR and
board state, and **exit `75` means park the card — do not reassign it**.

| Slice | Work | Owner | Cards (impl + review) | Depends on | Files |
|---|---|---|---:|---|---|
| **AN1** | *Disassembly pass — the player's clip selector and the `dx`/`dy` blit.* Answer, with VAs: (a) the function around `0x411F79`: which tag is chosen under which state, `<` vs `≤`, what is compared (Q38); (b) which clip the two jump kinds, the landing and the airborne fall draw; (c) the sign/origin of `dx`/`dy` (Q39); (d) whether the original holds a pose for a fixed tick count and how steps map across layers with different frame counts (Q36). Output: `file-formats.md` §2.6.2 (clip → selector → VA, graded), Q38/Q39 closed or narrowed, and the **leftover (a) link fix** as its own commit (below). **Docs only; no code.** | **specialist** | 1 + 1 | — | `docs/file-formats.md`, `docs/research/05-open-questions.md` |
| **AN2** | *Behaviour-neutral refactor.* Replace the single-purpose `load_move_poses` with a tag-keyed loader and a pure `select_clip(player) → (tag, pose)`; today's stand/run rules move into it unchanged; `slice` prints the `clips:` line. | **builder** | 1 + 1 | — (parallel with AN1) | `engine/level.py`, `engine/state.py`, `engine/render.py`, `cli.py` |
| **AN3** | *Anchoring fix.* `render_tiles` places each pose at its `dx`/`dy` under AN1's convention; `anim-clip` prints the `anchor:` line. The prerequisite for every air clip (jump bodies are 38–53 px tall: bottom-pinned they bob 13–15 px). | **builder** (specialist only if AN1 cannot settle Q39 — see fallback) | 1 + 1 | AN1, AN2 | `engine/render.py`, `anim_clip.py`, `cli.py` |
| **AN4** | *Air states.* Rising/falling → `JMP1`/`JMP2` (moving vs straight), landing → `LND1`; `FLO*` **not** used. | **builder** | 1 + 1 | AN2, AN3 (and AN1's mapping) | `engine/state.py`, `engine/entities.py`, `engine/render.py` |
| **AN5** *(stretch)* | *Duck.* `Input.down`, a Down key in `Keymap`, `DUCK` while grounded and held; collision box unchanged `[H]`. | **builder** | 1 + 1 | AN4 | `input.py`, `engine/entities.py`, `engine/state.py` |
| **AN6** *(stretch)* | *Idle fidget.* `STA2` after an idle delay `[H]`; **dropped, not guessed**, if AN1 does not settle Q36. | **builder** | 1 + 1 | AN4, AN1 (Q36) | `engine/state.py`, `engine/level.py` |
| **close** | *Synthesis.* Re-derive the merge gate live, run AC1–AC7 on merged `main`, attach the GIF, report spend against §4. | **lead** | 1 | all milestone PRs | — |

Order: `AN1 ∥ AN2` → `AN3` → `AN4` → *(stretch)* `AN5` → `AN6` → close.
`AN1` is docs and `AN2` is code in disjoint files, so they are the only pair
that may run in parallel.

**Specialist vs builder.** Disassembly — what the executable does that no data
file says — is **specialist, one card (AN1)**, justified under the routing
table's first reason (behaviour that exists only in machine code). Everything
else is a **pure render/state change on data we already decode — builder**;
the builder has not been tried on any of it yet, so no card goes to the
specialist "to be safe". If the builder returns a card with `kind=needs_input`
and a stated reason, it moves to the specialist once, not twice.

**Fallback if AN1 does not answer.** The slices must not stall on a research
card. If AN1 closes inconclusive after one rework, AN3/AN4 proceed with their
conventions **labelled `[H]`** — the `top = +dy` anchor (§2.4 finding 2, backed
by 19 non-trivial clips with a 0-px bottom spread), `vy < 0` ⇒ rising,
moving-vs-straight ⇒ `JMP1`/`JMP2` in that order — and Q38/Q39 stay open in
`05-open-questions.md` with that narrowing. AN6 is dropped.

**Hotspots.** `engine/render.py` and `engine/state.py` are touched by AN2, AN3,
AN4, AN5 and AN6. That is why the chain is serial: five PRs on two files cannot
run in parallel without a head-moves-after-review cycle each. Each slice
branches from the main that contains its predecessor.

**Housekeeping, folded in.**

* **(a) The broken link** at `docs/file-formats.md:616`:
  `../research/07-wp1-patching-surface.md` resolves to `docs/../research/…`
  (it does not exist); the file is `docs/research/07-wp1-patching-surface.md`,
  so from `docs/file-formats.md` the link is `research/07-wp1-patching-surface.md`.
  It rides **AN1 as a separate commit** (AN1 edits the same file), so it costs no
  card of its own. *Not applied in this PR* — this PR is the plan only.
* **(b) Card H's unreachable criterion** — closed by §1.2; no code or document
  line to change.

---

## 4. Budget

**Unit rate** (cited, not re-run): **≈42.0 k output / ≈102 k fresh /
≈3.72 M cached tokens and ≈$0.165 per card**, the board-wide average from
[`43-demo-plan.md`](43-demo-plan.md) §3 (`scripts/token_cost_report.py`), a
**lower bound** (34 of 92 runs had no log line). **Dollars are API-equivalent
list-price figures, not a bill:** the provider is Claude through the
subscription plugin, so the real constraint is the plan window, not dollars.
There is **no fallback provider**; a plan-limit stop parks the card (exit `75`)
and it resumes when the window reopens. Tokens are therefore the unit to compare
with the plan's limit — which this document does not know and has not measured.

**Card count.** The 16-card low case is: **3 plan-overhead cards** (this card,
its review, its merge) + the 13-card core (4 PRs × [implementation + review +
merge turn] = 12, plus 1 closing synthesis). Merge turns are counted as cards
because last time they were (§5).

| band | basis | core cards | output tok | fresh tok | cached tok | $ (≈) |
|---|---|---:|---:|---:|---:|---:|
| **low** | no rework | **16** | 0.67 M | 1.63 M | 59.5 M | **$2.64** |
| **expected** | one rework cycle on AN1 (a disassembly pass is the likeliest to be sent back) and one on AN4, each = rework run + re-review = 2 cards | **20** | 0.84 M | 2.04 M | 74.4 M | **$3.30** |
| **high** | last milestone's observed overrun repeats: 35 ÷ 15 = **2.33×** the modelled core | **37** | 1.55 M | 3.77 M | 137.6 M | **$6.11** |

Stretch tier (AN5 + AN6, 3 cards each — implementation, review, merge turn):

| band | cards | output tok | fresh tok | cached tok | $ (≈) |
|---|---:|---:|---:|---:|---:|
| low | 6 | 0.25 M | 0.61 M | 22.3 M | $0.99 |
| expected (one rework cycle) | 8 | 0.34 M | 0.82 M | 29.8 M | $1.32 |
| high (2.33×) | 14 | 0.59 M | 1.43 M | 52.1 M | $2.31 |

| core + stretch | cards | output tok | fresh tok | cached tok | $ (≈) |
|---|---:|---:|---:|---:|---:|
| low | 22 | 0.92 M | 2.24 M | 81.8 M | $3.63 |
| expected | 28 | 1.18 M | 2.86 M | 104.2 M | $4.62 |
| high | 51 | 2.14 M | 5.20 M | 189.7 M | $8.42 |

The recommendation is **core only**, with the stretch tier approved separately
once AN4 has merged and the real spend is known.

How to read these:

* **Reference.** The previous milestone forecast **15 cards ≈ $2.48** and spent
  **35 ≈ $5.78** (`45` §8.4; $5.78 is 35 × $0.165, a derived figure, not an
  invoice). The *high* band here is that same ratio applied once more; it is a
  ceiling for planning, not a prediction.
* **What the rate does not capture.** The $0.165 average blends cheap
  review cards with larger implementation cards; AN1 (disassembly) is likely
  **heavier than average** and AN2 (a refactor across four files) too. The
  expected band carries that only through the rework cycle; I have no
  per-profile token measurement to price them separately and do not invent one.
* **Wall clock** at the measured per-profile bands in `43` §3 (specialist
  13–25 min, builder 7.7–13.3 min, reviewer 5.5–7.5 min, lead synthesis 14.9 +
  2.0 min): core = 1 specialist (13–25) + 3 builder (23–40) + 4 reviews (22–30)
  + 1 closing (≈17) ≈ **75–112 min ≈ 1.3–1.9 h** of agent time summed across
  cards, excluding the merge turns, whose duration was not measured; elapsed time
  is longer because the chain is serial.
* **Stop rule.** If cumulative cards for this milestone pass **30** (1.5× the
  expected 20), the lead stops creating cards and reports to the maintainer
  instead of continuing.

---

## 5. Coordination overhead, and how this plan avoids it

**What it was last time** (`45` §8.4, quoted, not re-measured): the plan's graph
was 15 cards; adding rework (+3) and merge cards the plan did not model (+3) made
**21**; every card actually dispatched through the PR #61 merge was **35** —
the extra 14 are **not itemised** in §8.4 beyond these causes: review cards
**re-opened because a PR's head moved** (PR #51 ×3, PR #57 ×2, PR #59 ×2),
**duplicated Q32 review cards** (several made by the coordinator, not the
poller), and **per-PR merge cards** where the plan assumed one synthesis card.
The implementation itself came in at the predicted 7 cards; the overrun was all
coordination.

| last time | this plan |
|---|---|
| review card re-opened every time a head moved | **One review card per PR, created by the lead with the slice, as a child of the implementation card.** Changes are requested on the **same** card (`kanban_request_changes`), never a new one. The implementer posts the head SHA at hand-off and pushes **nothing** afterwards except in answer to a change request. |
| heads moved because a branch was cut before its dependency merged, then `main` was merged in (P2, P4) | **The chain is serial** (§3) and each slice branches from the `main` that already contains its predecessor, so no slice needs a merge-of-`main` before review. `AN1 ∥ AN2` touch disjoint files. |
| duplicated review cards | The lead lists the board for the PR number before creating any review card; a poller-created duplicate is closed before it dispatches. |
| per-PR merge cards unmodelled | **Modelled**: one lead merge turn per PR is in the card count (4 core, 2 stretch). Independent PRs (AN1 + AN2) may share one turn, saving one card. |
| the forecast excluded the plan card | The plan card, its review and its merge are **counted** (the "3 plan-overhead cards"). |
| no ceiling | The **30-card stop rule** (§4). |

The merge gate is unchanged: the reviewer's `**Ready for merge** — verdict:
approve` comment naming the **current** head, every check on that head green,
`mergeable: true`, not a draft, merge commit only, never a PR the lead
implemented.

---

## 6. Risks and non-goals

| Risk | What it could do | Cheapest retirement |
|---|---|---|
| **AN1 cannot find the selector** (stripped, computed state, inlined) | Selection stays `[H]`; Q38/Q39 stay open | The fallback in §3 — slices ship with `[H]` labels; AN6 is dropped. Cost of the failure: ~1 card |
| **Q38 flips the everyday clip** (`WALK`, not `RUN`) | PR #64's visible choice changes; AN2's "unchanged behaviour" baseline moves | AN1 answers it before AN3/AN4; AN2 is written to keep the rule in **one table**, so flipping it is a one-line change |
| **`dx`/`dy` convention wrong** (§2.4 finding 2) | Every pose placed a few pixels off — looks "almost right" | AN1's blit read; AN3 acceptance pins a number (AC3), and the check is a synthetic fixture with a known offset |
| **Jump arc counted twice** (§2.4 hazard) | An air pose drawn ~2× too high | AN1 states whether `dy` already carries the rise; AN3's acceptance compares the drawn air-pose bottom edge with the engine's `y` over one flat-ground jump (apex 19.4 px, 21 ticks) before AN4 starts |
| **`STA2`'s overrunning steps** (Q36) | Idle fidget loops wrongly | AN6 is conditional on AN1 |
| **Serial chain on two hot files** | Longer elapsed time | Accepted: it is the price of not re-reviewing |
| **Plan-limit stop** | A card parks mid-slice | Exit `75` parks it; resume when the window reopens; no reassignment, no fallback model |
| **Overrun** (last time 2.3×) | Spend passes the expected band | The 30-card stop rule |

**Non-goals.** Attack/throw/spin (`THR*`, `SPIN`), hurt/death (`OUCH`, `OHNO`,
…), climbing, helicopter/jet-pad, build/dig, swimming, doors, slope running,
braking/turning (no momentum), edge-teeter, the slow-fall `FLO*` (needs the
held-jump gravity mechanics of §2.9), changing the collision box, the
unresolved `169` contact sprite, the `Cset` colour swap, enemy animation, audio.
Gamepad and rebinding stay deferred as in `45`.

**Hard rules, restated for every card** (`AGENTS.md`):

* **No game bytes, ever** — no sprite pixels, no extracted art, no dumps in the
  repo, tests, issues, PR bodies or CI logs. Rendered frames and GIFs are
  attached to cards, never committed. Tests use synthetic fixtures.
* The retail data stays **outside Git and read-only** (`LOMAX_GAME_DIR`); the CLI
  already refuses to write into a folder that holds `LOMAX.EXE`.
* **No code from unlicensed projects** (`Lomax+` has no licence: facts, not code).
* **No CD-check bypass.** No upstream PRs. No push to `main`; no unsigned
  commits (`git log -1 --format=%G?` must print `G`).

---

## 7. Reproduce every number

Every measured figure above comes from one script, below. Save it **outside the
repository** (it reads the retail files; nothing it prints is game data — only
counts, sizes and offsets), install the package, and run each subcommand:

```bash
python3 -m pip install --user -e .          # from the repo root
export PYTHONPATH="$PWD/src"
python3 /path/outside/repo/anim_audit.py worlds   "$LOMAX_GAME_DIR"   # §2.1 table, 691 clips
python3 /path/outside/repo/anim_audit.py appendix "$LOMAX_GAME_DIR"   # Appendix A columns
python3 /path/outside/repo/anim_audit.py reach    "$LOMAX_GAME_DIR"   # §1.2 table
python3 /path/outside/repo/anim_audit.py control  "$LOMAX_GAME_DIR"   # §2.1 noise baseline
python3 /path/outside/repo/anim_audit.py budget                       # §4 arithmetic
```

Output at `main` = `457aa53` on the author's install, 2026-11-23: `worlds`
→ 691 clips; `reach` → `VILLAGE` stall at tick 2443 (40.7 s), `ED` tick 1906
(31.8 s), hold-right blocked after 41 ticks at x = 180, flat jump 21 ticks /
apex 19.4 px, first-120 spans `[(0,17), (20,39), (65,78), (110,119,open)]`;
`control` → mean 0.00, max 1; `budget` → the §4 rows.

### 7.1 Guard block (run before every push)

```bash
git -C "<install>" rev-parse --show-toplevel 2>/dev/null && echo "install must not be a repo" || true
grep -rniE '[0-9a-f]{64}' src tests docs && echo "FAIL: hash in tree" || true
git diff --name-only origin/main | grep -iE '\.(wld|exe|wav|png|gif|bmp|bin|dat)$' && echo "FAIL: binary/game file" || true
python3 -m pip install --user pytest && python3 -m pip install --user -e .
python3 -m pytest tests -m "not realgame" -q
```

### 7.2 The audit script

```python
"""anim_audit.py -- reproduce every measured number in docs/roadmap/46.

Run OUTSIDE the repository, read-only:
    PYTHONPATH=src python3 anim_audit.py <subcommand> "$LOMAX_GAME_DIR"
Subcommands: appendix | worlds | reach | control | budget
Prints counts, sizes and offsets only -- never pixels or file bytes.
"""
import random
import statistics
import string
import sys
from pathlib import Path

from lomax_modern import anim_nmy, wld
from lomax_modern.anim_clip import _signed, chunk_index_for_sprite, sprite_map


def nmy_records(path):
    world = wld.parse_file(path)
    chunk = next((c for c in world.chunks if c.tag == "NMY"), None)
    return (world, anim_nmy.decode_nmy(chunk.payload)[0]) if chunk else (world, [])


def appendix(game):
    exe = (game / "LOMAX.EXE").read_bytes()
    world, recs = nmy_records(game / "WORLDS" / "MAIN.WLD")
    hero = next(r for r in recs if r.name == "Hero")
    sm = sprite_map(world)
    print("| # | tag | keyframes | steps | layers (res / unres) | body layer w x h | top spread | `dy+h` range | `LOMAX.EXE` hits |")
    print("|---:|---|---:|---:|---|---|---:|---|---:|")
    for i, a in enumerate(hero.anims, 1):
        name = anim_nmy.anim_tag_name(a.tag)
        raw = name.encode("latin-1").ljust(4, b" ")[:4]
        sbytes = sorted({f[0] for f in a.frames})
        res = [s for s in sbytes if chunk_index_for_sprite(s) in sm]
        kfs = [f for f in a.frames if f[1] > 0 and f[0] in res]

        def area(sb):
            ch = sm[chunk_index_for_sprite(sb)]
            return sum(f.width * abs(f.height) for f in ch.frames) / ch.frame_count

        body = max(res, key=area)  # the largest-area layer = the whole-body layer
        ch = sm[chunk_index_for_sprite(body)]
        ws = [f.width for f in ch.frames]
        hs = [abs(f.height) for f in ch.frames]
        used = [(f, ch.frames[(f[1] - 1) % ch.frame_count]) for f in kfs if f[0] == body]
        uh = [abs(fr.height) for _, fr in used]
        b = [_signed(f[3]) + abs(fr.height) for f, fr in used]  # convention B: top = +dy
        steps = len({f[1] for f in a.frames if f[1] > 0})
        rng = f"{min(b)}" if min(b) == max(b) else f"{min(b)}..{max(b)}"
        print(f"| {i} | `{name.strip()}` | {a.frame_count} | {steps} | {len(res)} / {len(sbytes)-len(res)} | "
              f"{min(ws)}-{max(ws)} x {min(hs)}-{max(hs)} | {max(uh)-min(uh)} | {rng} | "
              f"{exe.count(raw[::-1])} |")


def worlds(game):
    _, main = nmy_records(game / "WORLDS" / "MAIN.WLD")
    vocab = {anim_nmy.anim_tag_name(a.tag).strip()
             for r in main if r.name == "Hero" for a in r.anims}
    print("| world | `NMY` records | clips | distinct tags | has `Hero` | tags shared with `Hero`'s vocabulary |")
    print("|---|---:|---:|---:|---|---|")
    total = 0
    for p in sorted((game / "WORLDS").glob("*.WLD")):
        _, rs = nmy_records(p)
        tags = [anim_nmy.anim_tag_name(a.tag).strip() for r in rs for a in r.anims]
        total += len(tags)
        shared = sorted(set(tags) & vocab) if p.stem != "MAIN" else ["(all 47)"]
        print(f"| {p.stem} | {len(rs)} | {len(tags)} | {len(set(tags))} | "
              f"{'yes' if any(r.name == 'Hero' for r in rs) else 'no'} | {', '.join(shared) or '—'} |")
    print(f"| **total** | | **{total}** | | | |")


def reach(game):
    from lomax_modern.engine.entities import TICK_RATE, Input
    from lomax_modern.engine.level import load_level
    from lomax_modern.engine.run import default_script
    from lomax_modern.engine.state import new_game_state

    for name in ("VILLAGE", "ED"):  # default_script: walk right, jump every 45 ticks
        lvl = load_level(game / "WORLDS" / f"{name}.WLD")
        st = new_game_state(lvl)
        xs = []
        for t in range(6000):
            st.tick(default_script(t, st))
            xs.append(st.player.x)
        stall = next(i for i in range(len(xs) - 120) if xs[i] == xs[i + 120])
        print(f"{name}: width {lvl.width_px} px; default_script x stalls from tick {stall} "
              f"= {stall / TICK_RATE:.1f} s at x={xs[stall]}")
    lvl = load_level(game / "WORLDS" / "VILLAGE.WLD")
    st = new_game_state(lvl)
    for _ in range(60):
        st.tick(Input())
    last, still = st.player.x, 0
    for t in range(1, 600):
        st.tick(Input(right=True))
        still = still + 1 if st.player.x == last else 0
        last = st.player.x
        if still >= 30:
            print(f"VILLAGE hold-right only: blocked after {t - 30} ticks = {(t - 30) / 60:.1f} s at x={last}")
            break
    st = new_game_state(lvl)
    for _ in range(60):
        st.tick(Input())
    y0 = st.player.y
    st.tick(Input(jump=True))
    air, apex = 1, y0 - st.player.y
    while not st.player.on_ground and air < 600:
        st.tick(Input())
        air += 1
        apex = max(apex, y0 - st.player.y)
    print(f"flat-ground jump: {air} airborne ticks = {air / 60:.2f} s, apex {apex:.1f} px")
    st = new_game_state(lvl)
    spans, cur, idle, moving = [], None, 0, 0
    for t in range(120):
        st.tick(default_script(t, st))
        if not st.player.on_ground:
            cur = [t, t] if cur is None else [cur[0], t]
        else:
            if cur:
                spans.append(tuple(cur))
                cur = None
            if st.player.vx:
                moving += 1
            else:
                idle += 1
    if cur:
        spans.append(tuple(cur) + ("open",))
    print("first 120 default_script ticks on VILLAGE: air spans", spans,
          "| grounded moving", moving, "| grounded vx==0", idle)


def control(game):
    exe = (game / "LOMAX.EXE").read_bytes()
    rng = random.Random(46)
    counts = sorted(exe.count("".join(rng.choice(string.ascii_uppercase) for _ in range(4)).encode())
                    for _ in range(500))
    print(f"500 random 4-letter tags in LOMAX.EXE: mean {statistics.mean(counts):.2f}, "
          f"p95 {counts[475]}, max {counts[-1]}")


def budget(_game=None):
    out, fresh, cached, usd = 42_000, 102_000, 3_720_000, 0.165  # per card, 43-demo-plan.md s3
    core_low, st_low = 3 + 13, 6
    bands = {"low": (core_low, st_low), "expected": (core_low + 4, st_low + 2),
             "high": (round(core_low * 35 / 15), round(st_low * 35 / 15))}
    print("band | core cards | out M | fresh M | cached M | USD || +stretch cards | out M | fresh M | cached M | USD")
    for k, (c, s) in bands.items():
        print(f"{k} | {c} | {c*out/1e6:.2f} | {c*fresh/1e6:.2f} | {c*cached/1e6:.1f} | {c*usd:.2f} || "
              f"{s} | {s*out/1e6:.2f} | {s*fresh/1e6:.2f} | {s*cached/1e6:.1f} | {s*usd:.2f}")
    print(f"previous milestone: 35 cards = ${35*usd:.2f}; forecast 15 = ${15*usd:.2f}; ratio {35/15:.2f}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    arg = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    {"appendix": appendix, "worlds": worlds, "reach": reach,
     "control": control, "budget": budget}[cmd](arg)
```

---

## 8. Appendix A — every `Hero` clip in `MAIN.WLD`

Produced by `anim_audit.py appendix`. *Layers* is `resolved / unresolved` sprite
bytes (unresolved = not in any `.WLD` bank; `169` is the shared contact pose).
*Body layer* is the largest-area layer (the one the engine draws). *Top spread*
is the pixel spread of the body layer's height across the clip — the head bob
under today's bottom-pinned blit. *`dy+h` spread* is the spread of `dy + h`
(§2.4, finding 2): 0 means the body's bottom edge sits on a fixed line if
`top = +dy`. *`LOMAX.EXE` hits* is §2.1's lead column, not a use proof.

| # | tag | keyframes | steps | layers (res / unres) | body layer w x h | top spread | `dy+h` range | `LOMAX.EXE` hits |
|---:|---|---:|---:|---|---|---:|---|---:|
| 1 | `WALK` | 22 | 10 | 2 / 1 | 36-42 x 44-48 | 4 | 1 | 14 |
| 2 | `RUN` | 26 | 12 | 2 / 1 | 48-62 x 34-43 | 9 | -6..1 | 1 |
| 3 | `STA1` | 60 | 7 | 2 / 0 | 44-44 x 47-49 | 2 | 1 | 5 |
| 4 | `STA2` | 153 | 10 | 4 / 0 | 44-56 x 38-42 | 4 | 1 | 2 |
| 5 | `THR1` | 8 | 5 | 1 / 1 | 38-50 x 49-55 | 6 | -4..0 | 2 |
| 6 | `THR2` | 8 | 5 | 1 / 1 | 42-52 x 36-44 | 8 | 1 | 2 |
| 7 | `DUCK` | 12 | 6 | 2 / 0 | 44-54 x 27-36 | 9 | 1 | 1 |
| 8 | `BRAK` | 21 | 7 | 2 / 1 | 50-54 x 45-47 | 2 | 1 | 1 |
| 9 | `JPAD` | 42 | 21 | 2 / 0 | 32-48 x 53-57 | 4 | 0..3 | 3 |
| 10 | `OUCH` | 3 | 3 | 1 / 0 | 38-38 x 44-46 | 2 | -3..-2 | 6 |
| 11 | `OHNO` | 6 | 3 | 1 / 0 | 40-62 x 41-75 | 34 | -9..8 | 1 |
| 12 | `PUSH` | 30 | 14 | 2 / 2 | 54-70 x 28-29 | 1 | 1 | 2 |
| 13 | `SPIN` | 24 | 8 | 2 / 1 | 50-56 x 56-57 | 1 | 1..3 | 11 |
| 14 | `JMP1` | 14 | 7 | 3 / 0 | 38-52 x 38-53 | 15 | -17..1 | 3 |
| 15 | `JMP2` | 14 | 7 | 2 / 0 | 42-48 x 39-52 | 13 | -15..1 | 2 |
| 16 | `LND1` | 3 | 1 | 2 / 1 | 52-52 x 38-38 | 0 | 1 | 1 |
| 17 | `FLO1` | 15 | 5 | 3 / 0 | 50-50 x 61-61 | 0 | 7 | 1 |
| 18 | `FLO2` | 15 | 5 | 3 / 0 | 44-44 x 62-63 | 1 | 6 | 1 |
| 19 | `RU45` | 24 | 8 | 2 / 1 | 46-60 x 47-61 | 14 | 1..15 | 1 |
| 20 | `PLOP` | 10 | 5 | 1 / 0 | 28-52 x 41-80 | 39 | 4..31 | 5 |
| 21 | `TUMB` | 20 | 9 | 2 / 1 | 44-54 x 37-52 | 15 | -8..7 | 5 |
| 22 | `EDGE` | 20 | 10 | 2 / 0 | 30-62 x 44-56 | 12 | 1 | 2 |
| 23 | `WAHL` | 70 | 3 | 3 / 0 | 38-40 x 47-49 | 2 | 1 | 2 |
| 24 | `DIZZ` | 16 | 8 | 2 / 0 | 50-56 x 48-52 | 4 | 1 | 3 |
| 25 | `CLIM` | 32 | 16 | 2 / 0 | 28-44 x 47-67 | 20 | -4..7 | 4 |
| 26 | `CLI2` | 6 | 3 | 2 / 0 | 30-44 x 62-62 | 0 | 6 | 4 |
| 27 | `CLI3` | 67 | 7 | 3 / 0 | 34-40 x 62-62 | 0 | 6 | 2 |
| 28 | `DIG1` | 24 | 12 | 2 / 0 | 42-64 x 39-48 | 9 | 1 | 3 |
| 29 | `DROW` | 25 | 14 | 2 / 0 | 50-58 x 43-58 | 15 | -1..7 | 4 |
| 30 | `IN` | 20 | 10 | 2 / 0 | 32-36 x 44-48 | 4 | 1 | 8 |
| 31 | `OUT` | 20 | 10 | 2 / 0 | 36-40 x 44-48 | 4 | 1 | 7 |
| 32 | `HELI` | 16 | 8 | 2 / 0 | 32-40 x 70-81 | 11 | 2..12 | 7 |
| 33 | `HEL1` | 15 | 7 | 1 / 1 | 48-80 x 25-44 | 19 | -2..3 | 3 |
| 34 | `HEL2` | 2 | 2 | 1 / 0 | 18-26 x 3-14 | 11 | 1..5 | 2 |
| 35 | `HEL3` | 2 | 2 | 1 / 0 | 18-26 x 3-14 | 6 | 1..4 | 1 |
| 36 | `CLI4` | 6 | 3 | 2 / 0 | 30-44 x 62-62 | 0 | 6 | 2 |
| 37 | `HEL0` | 4 | 3 | 1 / 1 | 48-80 x 25-44 | 9 | -3..-1 | 2 |
| 38 | `HEL4` | 2 | 2 | 1 / 0 | 48-80 x 25-44 | 3 | -1 | 3 |
| 39 | `THR3` | 6 | 4 | 2 / 1 | 34-40 x 62-62 | 0 | 6 | 3 |
| 40 | `PLO2` | 1 | 1 | 1 / 0 | 24-24 x 22-22 | 0 | 11 | 1 |
| 41 | `BUI1` | 15 | 10 | 2 / 0 | 16-50 x 19-68 | 49 | -36..-1 | 3 |
| 42 | `BUI2` | 4 | 3 | 1 / 0 | 40-44 x 17-24 | 7 | 9..13 | 1 |
| 43 | `HEL5` | 2 | 1 | 1 / 1 | 44-44 x 53-53 | 0 | 1 | 1 |
| 44 | `HEL6` | 2 | 2 | 1 / 0 | 4-14 x 17-25 | 8 | 11..14 | 2 |
| 45 | `HEL7` | 2 | 2 | 1 / 0 | 4-14 x 17-25 | 8 | 11..14 | 1 |
| 46 | `BOOM` | 3 | 3 | 1 / 0 | 24-24 x 17-20 | 3 | 9..11 | 5 |
| 47 | `HEL8` | 3 | 2 | 2 / 1 | 38-52 x 38-53 | 0 | 1 | 1 |
