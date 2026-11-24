# 47. The first level, fully recreated — plan

> **Status: proposed — planning only.** No code and no implementation card
> exists until the maintainer approves this PR. Written against `main` =
> `290cb61` (2026-11-24). Everything marked as measured was run on the retail
> install through `LOMAX_GAME_DIR` (read-only) at that head; the command for
> each number is in [§6](#6-reproduce-every-number).

The character-animation milestone ([`46`](46-character-animation-plan.md)) is
shipped and the maintainer watched it on a real display. His next milestone:
**improve the test worlds, and make the first level of the first world fully
recreated.** He delegated the scoping. This document is that scope: which level
it is (§1), what "fully recreated" means as observable criteria (§2), how far
today's engine is from it, measured (§3), and the slicing into reviewable PRs
(§4).

Grades used throughout: **[V]** an instruction or table in `LOMAX.EXE` was read
(read-only `objdump`, no execution) and carries the claim; **[M]** measured by
running a command in §6; **[H]** a guess the data or a name suggests, not a
finding. A number or address with none of these is quoted from a cited
document. A clause that names a measurement or an address is a claim that it
was done.

## Table of contents

1. [Which level is "the first level of the first world"](#1-which-level-is-the-first-level-of-the-first-world)
2. [Definition of "fully recreated"](#2-definition-of-fully-recreated)
3. [Gap analysis — today's engine, measured](#3-gap-analysis--todays-engine-measured)
4. [Slices](#4-slices)
5. [Risks, non-goals and decisions for the maintainer](#5-risks-non-goals-and-decisions-for-the-maintainer)
6. [Reproduce every number](#6-reproduce-every-number)

---

## 1. Which level is "the first level of the first world"

Nothing in the repository defined it. The executable does, in a table that no
earlier pass read.

### 1.1 The answer, and the options

| Option | What it is | Evidence | Verdict |
|---|---|---|---|
| **A** | **Section 0, sub-level 0 = `MEDIEVAL.WLD`, playfield plane 0** (198 × 40 cells = 3,168 × 640 px), with backdrop planes 11, 12, 13 | §1.2 [V] table decode, [M] plane sizes | **Recommended.** It is the first entry of the original's own level table, and its backdrop is the screenshot's backdrop (§1.3) |
| B | **All of section 0** — three sub-levels (planes 0, 1, 2; 3,168 + 6,352 + 5,152 px of playfield) | the same table: section 0 has 3 sub-levels | The original groups them under one password "section"; a follow-up milestone, not this one (3 × the content, and plane 2 ends on `Finish`, not `Exit`) |
| C | The level in the screenshot, if it is **not** section 0 | `MEDIEVAL` sections 0 **and** 3 share backdrop planes 11–13 (§1.2) | Cannot be excluded from the picture alone (§1.3); the table says the first section is 0, so A stands unless the maintainer says the screenshot is a later section |

**Today's test worlds are not the first level.** `VILLAGE` and `ED` appear in
the table as **section 2** (and 4) and **sections 18–20** respectively — see the
table below. `slice --world VILLAGE` loads plane 0, which is section 2
sub-level 0 (planes 0, 1, 13, 14 active), the *third* section; `--world ED`
loads plane 0 of section 18. The first level is in a third world file the
engine has never used as a target: **`MEDIEVAL`**.

### 1.2 How the original orders worlds and levels [V]

`LOMAX.EXE` carries a **24-entry section table at VA `0x466450`, stride 24
bytes**, and a world-file name table at VA `0x466690` (index 0–9: `MEDIEVAL`,
`VILLAGE`, `HAUNTED`, `WEST`, `ED`, `BONUS`, `MAP`, `TITLE`, `LOGO`, `MAIN`).
The layout below is what the readers use; each row cites the reading
instruction.

| Entry field | Meaning | Read at |
|---|---|---|
| `+0x00` u32 `M` | the set of planes the section may load (bit *n* = plane *n* of the world file) | `0x40EB26` |
| `+0x04` u32 `A` | third argument of the world loader `0x4147E0`; in section 0 it equals the three playfield planes `0x7` (its meaning is [H]) | `0x40EC06` |
| `+0x08` u8, `+0x09` i8 | two small selectors (ambient/music choice is the guess [H]) | `0x417DA6`, `0x417DCB` |
| `+0x0A` u8 | **world-file index** into the name table | `0x40EC1E`–`0x40EC24` |
| `+0x0C` u16 | **number of sub-levels** in the section | `0x417E0C`, `0x417E48` (compared with the sub-level counter `0x4645BC`) |
| `+0x0E…` u16 × 5 | one **selector per sub-level**: bit *r* chooses the *r*-th set bit of `M` | `0x40EB39`–`0x40EB6E` (loop over the 32 plane bits; unselected planes are cleared from the mask returned in `eax`, which `0x40EBF9` stores at `0x59E77C` and `0x40EC15` passes as the loader's second argument) |

Decoding all 24 entries with the script in §6 (A) prints, [M]:

| Section | World file | Sub-levels → active planes (`playfield + backdrop`) |
|---:|---|---|
| **0** | **MEDIEVAL** | **[0, 11, 12, 13] · [1, 11, 12, 13] · [2, 11, 12, 13]** |
| 1 | MEDIEVAL | [3, 14, 15, 16] · [4, 14, 15, 16] · [5, 14, 15, 16] |
| 2 | VILLAGE | [0, 1, 13, 14] · [2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14] |
| 3 | MEDIEVAL | [6, 11, 12, 13] · [7, 11, 12, 13] · [8, 14, 15, 16] |
| 4 | VILLAGE | [11, 12, 13, 14] |
| 5 | MEDIEVAL | [9, 11, 12, 13] · [10, 15, 16] |
| 6–12 | HAUNTED | 7 sections, 1–2 sub-levels each |
| 13–17 | WEST | 5 sections |
| 18–20 | ED | 3 sections |
| 21 / 22 / 23 | BONUS / MAP / TITLE | 5 / 1 / 2 sub-levels |

Four facts follow, each with its grade:

1. **The first section is index 0.** The current-section word `0x4645C4` and the
   sub-level word `0x4645BC` are zero in the file's initialised data [M: read
   from the `.data` image of the file], the new-game reset `0x40EDC0` writes 0 to
   `0x4645BC` and `0x4645C8` and never touches `0x4645C4`, and the advance routines
   count up from there: next section `0x417DF0` (`+1`, wraps at 22) and next
   sub-level `0x417E30` (`+1`, wraps at the entry's count) [V]. The password
   screen prints `Section %d` with `index + 1` (`0x417A04`–`0x417A1A`, format at
   VA `0x466884`), so the first section is shown as **Section 1** [V].
2. **A sub-level is one playfield plane plus shared backdrop planes.** Within
   section 0 the sub-levels differ only in the first plane; planes 11–13 are
   shared. The same three backdrop planes serve section 3's first two
   sub-levels — the reason option C exists. [V arithmetic; "playfield versus
   backdrop" is [H] for `A`, but it matches the data: planes 0–2 have `Start`
   placements, planes 11–13 have only `ScrollMap`/`Birds`/`Parallax` ones (§1.4)]
3. **A new game starts with 3 lives and 3 credits** — the reset stores 3 into
   `0x52C56C` (`0x40EE06`) and `0x59F160` (`0x40EDFA`), the two values the
   password decoder fills from its `Lives` and `Credits` fields
   (`0x417A4E`, `0x417A54`) [V].
4. **What is not established — Q41:** the reset also sets the title and map
   flags (`0x52C6C4` at `0x40EE2F`, `0x59E958` at `0x40EE35`), and the selector
   at `0x417C2C`–`0x417CDF` loads `TITLE` (23), `BONUS` (21) or `MAP` (22) when
   they are set; the map-node table at VA `0x466410` (8 entries) has no node
   for section 0. So the original reaches section 0 through a title/map flow
   this pass did not trace. Index 0 being first is [V]; *that a new game lands
   in it without a map choice* is [H] (FL1).

### 1.3 Matching the maintainer's screenshot, and the video

`artifacts/reference/first-level-screenshot.jpg` (800 × 446, outside the Git
tree; never committed, quoted or hashed) shows a forest-canopy level. How each
element matches the retail data, by rendering each plane with the engine's own tile decoder (script J in §6; the renders were looked at, never committed):

| In the screenshot | In the data | Grade |
|---|---|---|
| Thick vine-covered grassy ledge, orange earth, twisting trunk | `MEDIEVAL` plane 0's tile art — the engine's current frames show the same ferns, orange earth and twisting vine trunk | [M] by eye, same tileset; not pixel-compared (the reference is upscaled and compressed) |
| Big trunks with red-orange flower vines | **plane 11** (37 × 20 cells): two tall trunks, red flowers on the left one | [M] by eye |
| Pale floating islands with stone towers | **plane 12** (35 × 19 cells): towers on islands, drawn over cloud banks | [M] by eye; the engine's palette gives teal cloud banks where the screenshot is pale (Q44) |
| Blue sky and clouds | **not tile art**: plane 13 (20 × 15 cells) has **0 cells with a visible pixel** (so does plane 16); the sky comes from elsewhere — `MEDIEVAL` carries nine `Parallax` `NMY` records, each with a `PARA` clip, which is the candidate | [M] for the empty plane; the source is [H] (Q44) |
| Small hatted creature at the right edge with a trail of blue dots | `Lorock` — one placement in plane 0; its record's clips are `HAT`, `APPE`, `LAND`, `EXHA`, `TALK`, `STAY`, `BLAH`, `DISA`, `STAR` (an appear / talk / disappear NPC) | [H] from clip names only |
| Tiny red flying object | `Beestjes` ("little beasts"), 19 placements in plane 0, clips `EINS`…`VIER` | [H] from the name |
| Red flowers on the ground | not identified: either tile art or a `Pots`/`Generator`-class object | [H] |

Nothing in the screenshot separates section 0 from section 3's `[11, 12, 13]`
sub-levels, so identity rests on §1.2. **Compare the engine now:** the same
level rendered by `slice --world MEDIEVAL` has the right foreground and no
backdrop at all — the sky is a flat placeholder colour (§3, G2).

**The video** (`/game-files/gameplay trimmed.mp4`, 1920 × 1080, 59.94 fps,
398.8 s, with audio; sampled every 10 s and every 3.5 s with `ffmpeg`, looked at
frame by frame — not decoded programmatically):

| It shows | It does not show |
|---|---|
| 0–140 s: a castle-and-sea level with a stone-bridge foreground, in-game hint boxes, then a **password screen**. Then a sunset-sky level with palm-like trees on stone ledges (the `VILLAGE` look, section 2 [H]), a **bonus** level (a field of coins, a `LEVEL COMPLETE` banner), a second password screen, and a `LET'S GO!` banner at **≈ 335–345 s** over the forest-canopy level, played for the last ≈ 60 s | A new game, a title or map screen, or the **first level from the start**: the canopy level is the *last* minute, after two password screens, so the video is not in game order |
| The HUD (§2, AC11): four elements along the top, present in every gameplay frame | The level's exit, a death, a fall, or any end-of-level for the canopy segment; which sub-level the canopy segment is (the beanstalk at its start matches plane 2's start region [H], not plane 0's) |
| Enemies, a hanging barrel, floating wooden platforms, pickups, a talking NPC with a hat | Numbers for enemy behaviour that can be checked: it is a compressed upscale |
| The view is **16:9** (1920 × 1080; the screenshot is 800 × 446 = 1.79) while the engine's source frame is 320 × 240 (4:3, [`15`](15-strategy-report.md) §3) | Whether the capture is of the PC build: the dithered translucency and the corner watermark suggest an emulator capture of a **console** build [H] — Q49 |

Use: **what** a recreated level shows and does, never pixel positions or
timings. Every positional or timing criterion below is anchored to the
executable or the data, with the video as a sanity check.

### 1.4 What the first level contains [M]

Plane 0 carries **52 placements of 15 names**, every name matching an entry of
the executable's 89-name table (0 unmatched) — `Beestjes` 19, `Henchlemming` 8,
`Rope` 5, `Generator` 4, `Jumppad` 3, `Pots` 3, `Moneybag` 2, and one each of
`Exit`, `Lorock`, `Music`, `Parallax`, `Revive`, `Start`, `Thief`, `Ufos`.
The engine resolves three of those 15 names to a role (`Start`, `Exit`,
`Moneybag`); the other 12 names (48 of 52 placements) are one grey marker.
Planes 11–13 carry only `ScrollMap` (4 and 4), `Birds` (2) and `Parallax` (1);
**no `Start`/`Exit`/`Finish`/`Revive`** — the backdrop planes are not playable.
Sub-levels 1 and 2 (planes 1, 2) are out of scope (§2.3) and end on `Exit` and
`Finish`.

---

## 2. Definition of "fully recreated"

**The unit** is option A: `MEDIEVAL.WLD` section 0, sub-level 0 — playfield
plane 0 with backdrop planes 11–13 — called **L1** below.

**Reachability rule for this milestone.** The last two milestones each hit an
unreachable criterion once (a 60 s run that the plane edge ends; a collectable
no scripted walk touches). So: **no criterion needs a human at the keyboard,
and none needs more than ~10 s of scripted play, except AC8/AC12, which need the
route from `Start` to `Exit`.** That route is at least `3079 − 89 = 2,990` px,
i.e. ≥ 1,495 ticks = **24.9 s** at 2.0 px/tick [derived]; the straight walk is
*not* a route — held-right scripts reach the plane's right edge at the bottom
border and never touch the `Exit` (G7). AC12 therefore makes the route itself a
deliverable, found by a solver over the engine's own physics (FL14), with a
named fallback if it cannot be found (§5, R1). Commands that do not exist yet
name the slice that adds them.

### 2.1 Acceptance criteria

`<install>` is the read-only retail folder (`$LOMAX_GAME_DIR`). New flags:
`slice`/`play` gain `--section N --sublevel M` (FL5), `slice` gains
`--input FILE` (FL14, a list of per-tick key states — inputs only).

| # | What the maintainer sees | Command that shows it | Reachable because | Grade of the thing it checks | Slice |
|---|---|---|---|---|---|
| **AC1** | The level is named from the original's table, not from `--world`/`--playfield`: `slice` prints `level: section 0 sub-level 0 = MEDIEVAL, playfield plane 0, backdrop planes 11 12 13` and `playfield: 198x40 cells (3168x640 px)`. `VILLAGE`/`ED` stay selectable as test worlds and are reported as sections 2 / 18 | `python3 -m lomax_modern slice "<install>" --section 0 --sublevel 0 --frames 1 --out /tmp/f` | the table is decoded today (§1.2) and the plane size is measured (§6 B) | table [V]; sizes [M] | FL5 |
| **AC2** | Tile art matches the original's orientation: the flip pairing (`0x2000`/`0x4000`, Q33) is settled from the copy loops, and `slice` says `flip pairing [V]` | same, plus the maintainer's look at the witness frames at three camera positions (x = 0, 1,500, 3,000) | the four copy loops are located (`0x41566B`, `0x415686`, `0x4156A8`, `0x4156C6`, `file-formats.md` §2.8); reading their strides settles it | [V] after FL2; [H] today | FL2 (docs), FL7 |
| **AC3** | L1's **eight** collision-byte values behave as the original's: each of `0x00 0xC0 0xC8 0xD0 0xD8 0xE0 0xE8 0xF0` has a documented class (solid / one-way / slope / terrain …) with a grade, and `slice` prints one line per value. Unit tests on a synthetic `MAP` cover every class found | `…slice … --section 0 --sublevel 0` → `collision:` block | the eight values are measured (§6 B); the terrain dispatch (`0x413C93`, bits `0x30`) and the edge probe (`0x413940`) are located. **If a value stays [H] after FL2 it is named on the card, kept on the conservative solid rule, and AC3 closes as partial — it does not silently pass** | values [M]; classes [V] after FL2 | FL2 (docs), FL7 |
| **AC4** | The **backdrop is drawn**: sky, the island/tower layer (plane 12) and the trunk layer (plane 11) behind plane 0, each scrolling at its own ratio, with the original's palette. A frame at spawn is recognisably the screenshot's scene (maintainer's eye); unit tests pin the scroll ratio on a synthetic two-layer world | `…slice … --frames 120 --out /tmp/f` and the first and last frame | planes 11–13 are decoded and render (§1.3); the sky source (`Parallax` records) is named but not read yet → FL3 | layers [M]; ratios, sky source, palette/blend [H] until FL3 | FL3 (docs), FL9 |
| **AC5** | **Every placement resolved to a role.** `slice` prints `objects: 52 placements, 15 names, 0 unresolved` and a table `name → role → grade`; every name has a role label in a table citing its handler (`0x4647B8[index]`, index from `0x464650`) or an `[H]` reason. Today: 3 of 15 names resolved | `…slice … --section 0 --sublevel 0` → `objects:` block | all 15 names already match the 89-name table (0 unmatched, §6 B), so every handler address is known and only has to be read | roles [V] after FL4; today 3/15 | FL4 (docs), FL6 |
| **AC6** | **Every placed object is drawn with its own sprite**, in its idle/stay clip, at its placement — enemies, `Lorock`, `Beestjes`, `Jumppad`, `Rope`, `Pots`, `Moneybag`, `Revive` — instead of a grey square. Objects with no sprite by design (`Start`, `Music`, `Generator`, `Parallax` — which of these hold is FL4's to say) are listed as `hidden by design` with the reason. `slice` prints `sprites: N/52 drawn, M hidden by design, 0 missing` | `…slice … --frames 120` → `sprites:` line and the maintainer's look at the frames | the clips exist in `MEDIEVAL`'s `NMY` table (`Henchlemming` `STAY`/`JUMP`, `Lorock` 9 clips, `Moneybag` `HANG`/`JUMP`, `Jumppad` `PAD`, `Rope` `ROPE`, …) and the `ANIM` decode already draws the hero | clips [M]; which clip is "idle" per name [H] until FL4 | FL10 |
| **AC7** | **Start**: the hero appears where and how the original puts it (position origin, facing, jump kind at level start — Q40a, Q48), with the original's initial state; `slice` prints `start: …` with the grade of each part | `…slice … --frames 30` | `0x40ED7C`/`0x40F856` are located (`file-formats.md` §2.8) | [V] after FL1; [H] today (the engine places the 12 × 14 box top-left on `(89, 407)`) | FL1 (docs), FL8 |
| **AC8** | **Goal**: reaching the `Exit` placement completes L1; `slice` prints `result: level complete at tick N` for the witness input (AC12) and stops there. *Loading the next sub-level is out of scope* | `…slice … --input <witness> --section 0 --sublevel 0` | the `Exit` is at (3079, 444) [M]; the witness (AC12) exists by construction | trigger [V] (`0x427670`); region size [H] after FL1 | FL11, FL14 |
| **AC9** | **Fail and restart**: the original's rule for losing a life (leaving the plane's bottom is the guess [H], Q42) takes one of the **3** starting lives, respawns at the `Start` or the last-touched `Revive` (1 placement in L1), and at 0 lives reports `game over` (no screen). The HUD life count follows. `slice` prints `life lost at tick N: lives 3 -> 2, respawn (x, y)` for a scripted fall | `…slice … --input <fall script>` (held right with a jump every 30 ticks; the hero first reaches the plane's bottom at tick 397 = 6.6 s today, G7) | the fall is reachable: all 22 scripted runs reach the bottom border, the last at 14.7 s (G7); lives start at 3 [V] | lives [V]; death rule, respawn rule [H] until FL1 | FL1 (docs), FL11 |
| **AC10** | **Scrolling and camera**: the viewport follows the hero by the original's rule (dead zone / lead / vertical bias, clamps), not "centre on the player"; backdrops scroll against it (AC4). `slice` prints `camera: <rule>` with its grade | `…slice … --frames 120` | the video gives the hero's on-screen offsets as a sanity check; the routine is to be found (Q45) | [H] today (centre + clamp); [V] only if FL3 finds the routine, else the video-measured rule stays [H] and is said so | FL3 (docs), FL12 |
| **AC11** | **HUD — the four elements of the reference** (§2.2) drawn from the original's own sprites at the reference's layout: item counter (top-left), the figure counter and the framed item box (top-centre), the coin counter (centre-right), the face with the life count (top-right). Lives (3) and coins are **live**; the others show their initial value, with the grade of that value. `slice` prints `hud: 4 elements, 2 live` | `…slice … --frames 120` and the maintainer's look at the frames against the screenshot | the candidate sprite records exist in `MAIN.WLD`'s table (`Display`, `Icons`, `Items`, `Inserts`, `Timer`) and the hero's face sprite is not yet located; sources are named [H] and read in FL4 | layout [H] (from the reference, not pixel-exact); values [V] only where FL4 reads them | FL4 (docs), FL13 |
| **AC12** | **L1 is completable on the engine.** `lomax-modern solve` (FL14) searches the engine's own physics, collision and objects for an input list from `Start` to `Exit` that also collects both `Moneybag`s, prints its length (≥ 1,495 ticks) and writes it **outside the repo**; `slice --input` replays it to `result: level complete` | `python3 -m lomax_modern solve "<install>" --section 0 --sublevel 0 --out /tmp/witness.json && python3 -m lomax_modern slice "<install>" --section 0 --sublevel 0 --input /tmp/witness.json --out /tmp/f` | the level is a platform route 3,168 px long with a bottom pit; three `Jumppad`s and five `Rope`s may be required, so FL14 depends on every behaviour slice. **No-go rule:** if no route exists after FL13, the cause is named and the milestone is not closed | [M] by construction | FL14 |
| **AC13** | **It runs at the original's rate**: `play` on L1 for 20 s keeps a mean ≥ 55 fps at the 4× 1920 × 1080 profile and the logic tick stays 60 Hz | `SDL_VIDEODRIVER=dummy python3 -m lomax_modern play "<install>" --section 0 --sublevel 0 --seconds 20` | today `play` on the same plane ran 120 frames in 2.00 s, mean 59.9 fps (G10), with one layer and no sprites — the added layers are what could break it, so it is measured at FL9 and FL10, not only at the end | [M] | FL9, FL10, FL13 |
| **AC15** | **The test worlds improve as a by-product** (the other half of the maintainer's milestone): every builder slice is world-generic, so `VILLAGE` (section 2) and `ED` (section 18) draw their own backdrop planes and report their placements' roles, with no exception and no per-world code. Only L1 is graded for fidelity | `python3 -m lomax_modern slice "<install>" --section 2 --sublevel 0 --frames 30 --out /tmp/v` and the same with `--section 18` | the table covers all 24 sections (§1.2) and both worlds already load | [M] | FL5, FL6, FL9 |
| **AC14** | **Housekeeping**: plan 46's Status sentence is corrected (done in this PR, §4.3) | `grep -n "unit tests only" docs/roadmap/46-character-animation-plan.md` | a one-line doc edit | — | this PR |

### 2.2 The HUD, element by element (AC11)

What the reference shows — screenshot and video agree on the four elements; the
**meanings and initial values are [H]** (no counter value is read from the
executable yet, Q46):

| Element | Position (reference, 16:9) | What is drawn | Candidate source in `MAIN.WLD` [H] | In scope |
|---|---|---|---|---|
| 1 | top-left | a small framed item icon and a counter | `Items` (`HELM`, `COIN`, `STAR`, `TAIL`, `UP`) / `Icons` | **drawn**; counter shows its initial value |
| 2 | top-centre | the hero figure with a counter, beside a gold-framed box holding an item | `Display` (`HELM`, `KLEI`, `GROS`) / `Inserts` | **drawn**; counter shows its initial value (it changed from 36 to 21 within one video segment — a timer or a collected count, [H]) |
| 3 | centre-right | a gold coin and a counter | `Items` `COIN` | **drawn and live**: incremented by `Moneybag` (amount from FL4) |
| 4 | top-right | the hero's face and the life count | `Hero`-record face sprite | **drawn and live**: starts at 3 [V], falls on a lost life (AC9) |

### 2.3 Deliberately out of scope

| Out | Why |
|---|---|
| **Audio** — music, ambient loops, SFX, jingles (`LETSGO`, `LEVELEND`, …) | its own milestone (M6, [`10`](10-milestones.md)); the data carries no music track ([`15`](15-strategy-report.md) §8, Q30). The `Music` placement is classified, not played |
| **Enemy and NPC behaviour** — `Henchlemming`, `Thief`, `Ufos`, `Beestjes`, `Lorock`'s speech, `Generator` spawning; contact damage and the hurt/death animations (`OUCH`, `OHNO`, `TUMB`) | each is a handler to read and port; they are *drawn* (AC6) but static. This is the largest single deferral — D2 in §5 asks the maintainer to confirm it |
| Hero attacks (`THR1`–`THR3`, `SPIN`), climbing, helicopter, swimming, doors | the deferred set of [`46`](46-character-animation-plan.md); L1's `Rope`s and `Jumppad`s are the exception *if* FL14 shows they are on the route |
| Sub-levels 1 and 2 (planes 1, 2), every other section, `BONUS`, `MAP`, `TITLE`, password, level-complete screen, `LET'S GO!` banner | other levels and flow screens; AC8 stops at `level complete` |
| Pixel-exact comparison with the references | impossible: upscaled and compressed (§1.3); the criteria are anchored to data and code instead |

---

## 3. Gap analysis — today's engine, measured

Run on the retail install at `main` = `290cb61`, command in §6 for every row.
"Works" means observed in the output, not read from the source.

| # | Area | Observed | Verdict |
|---|---|---|---|
| G1 | **Level selection** | `slice --world MEDIEVAL` loads plane 0 of the world file because the default playfield is 0; the engine never reads the section table, so it cannot say which section a plane belongs to (`VILLAGE` plane 0 and `ED` plane 0 are sections 2 and 18) | **works by coincidence** for L1; **missing** as a concept |
| G2 | **Backdrop** | none. The frame behind plane 0 is the placeholder navy: pixel (0, 0) and (319, 0) of the first frame equal `COLOUR_SKY`. Planes 11–13 are never decoded into the level, and the `ScrollMap`/`Birds`/`Parallax` placements are carried but not interpreted | **missing** |
| G3 | **Tile art, plane 0** | composed correctly in the sense of §1.3 — the same ferns, orange earth, vine trunk as the reference; flip pairing is the decoder's convention (Q33) | **works**, one [H] |
| G4 | **Collision** | plane 0 has **8 distinct collision values**: `0x00` 7,624, `0xC0` 76, `0xC8` 114, `0xD0` 26, `0xD8` 18, `0xE0` 26, `0xE8` 18, `0xF0` 18 (sum 7,920 = 198 × 40; 296 non-zero = 3.7 %). The engine treats every non-zero as solid from all sides. The high nibbles `C`/`D`/`E`/`F` map onto the terrain bits (`0x30`, §2.9) as 0/1/2/3 [derived, no routine read] — so up to four classes may be folded into one | **wrong in an unknown amount** (Q31, Q43) |
| G5 | **Placed objects** | 52 placements, 15 names, 0 unmatched in the 89-name table; the engine resolves 3 names (`Start`, `Exit`, `Moneybag` = 4 placements), draws **48 grey 3 × 3 markers** for the rest and nothing for the sprites | **mostly missing** |
| G6 | **Spawn** | `Start (89, 407)`; the first solid row below that column is y = 480, so the hero falls 73 px from where the engine puts its 12 × 14 box's top-left. Whether `Start` is the box's top-left or the actor's feet origin is untraced (Q48) | **works**, origin [H] |
| G7 | **Goal and fail** | `Exit (3079, 444)`, 2 `Moneybag`s. A held-right script with a jump every *p* ticks (*p* = 15…120 step 5, 22 runs, 3,600 ticks each) reaches x = 3,156 in **all 22 runs** and ends at y = 625 or 626 with `complete = False` in all 22: the hero walks along the **bottom border** — the off-map sentinel is solid, so there is no pit. It first touches that border at tick 382 (*p* = 15) to 879 (*p* = 105), i.e. 6.4–14.7 s. The bottom map row has 0 non-zero collision cells. There is no life, no death, no respawn, no `Revive` | **wrong** (no fail state) and **missing** (rules) |
| G8 | **Physics** | `entities.py` carries the four measured constants; `file-formats.md` §2.9 records that the original **skips gravity for 5/10 ticks after a jump** and **raises with reduced gravity while jump is held**, neither implemented — the engine's jump is shorter than the original's. Whether the platforms of L1 need the longer jump is unknown | **partly wrong** (known) |
| G9 | **Camera** | centred on the hero's box and clamped to the plane; measured on the `play` HUD line at spawn: `camera=(0,353)`. The original's rule is untraced (Q45) | **works as a placeholder**, [H] |
| G10 | **HUD and rate** | the HUD is one **text line**: `fps=60.2 plane=MEDIEVAL tiles=7920 camera=(0,353) collect 0/2`; no icons, no lives, no coin sprite. `play --world MEDIEVAL --seconds 2` under `SDL_VIDEODRIVER=dummy`: 120 frames in 2.00 s, mean 59.9 fps | rate **works**; HUD **missing** |
| G11 | **Hero** | the 120-tick slice prints `clips: WALK 34, JMP2 62, FLO2 24`: the clip machinery works on this plane | **works** |
| G12 | **Tests of retail data** | the repository's tests use synthetic fixtures only; nothing asserts anything about L1 | by design; the closing card checks by execution |

**What already works**, in short: reading the world, composing plane 0's tile
art, resolving three roles, the 60 Hz tick with the original's four physics
constants, the hero's clips, keyboard `play`, 4× presenter at ≈ 60 fps.
**What is wrong:** all-solid collision, no pit, a jump shorter than the
original's. **What is missing:** backdrop, objects, rules, camera, HUD, the
section concept.

### 3.1 New open questions (a `Q` block)

These are added to [`05-open-questions.md`](../research/05-open-questions.md)
as Q41–Q49 in this PR.

| # | Question | Needs | Slice |
|---|---|---|---|
| **Q41** | How does a new game reach section 0 — title → map → which node? The reset `0x40EDC0` sets the title and map flags and the 8-node map table (`0x466410`) has no section-0 node | **disassembly (specialist)** | FL1 |
| **Q42** | Level flow and the fail rule: what the `Exit` handler (`0x427670`) does to the section/sub-level counters; what the `Finish` and `Revive` handlers do; what takes a life (pit, enemy, drowning?) and where the hero respawns; what a spent `Credit` does | **specialist** | FL1 |
| **Q43** | The eight collision values of L1 (`0xC0 … 0xF0`): solid / one-way / slope / terrain, and the use of the low bits (narrows Q31) | **specialist** | FL2 |
| **Q44** | The backdrop: draw order and scroll ratios of the three planes (the second `ScrollMap` parameter is 50 on plane 11 and 25 on plane 12 — a ratio is the guess [H]); what draws the sky (planes 13 and 16 are empty); why the engine's palette makes the islands teal where the reference is pale (blend, a different palette slot, or a fog) | **specialist** | FL3 |
| **Q45** | The camera rule: dead zone, lead, vertical bias, clamps; what `ForceScrolling` (present in plane 10 of this world) does | **specialist** | FL3 |
| **Q46** | The HUD: which sprites, positions, initial values and update rules for the four elements; the coin value of a `Moneybag` | **specialist** | FL4 |
| **Q47** | The role and idle clip of each of L1's 15 names, and which of them the route to `Exit` needs (`Jumppad`, `Rope`, `Pots`, …) | **specialist** | FL4 |
| **Q48** | `Start`'s origin (box top-left or actor feet), the hero's initial facing and jump kind (Q40a) and collision box | **specialist** | FL1 |
| **Q49** | Provenance of the maintainer's references: PC or console capture, and what differs (HUD layout, view width, translucency) | **maintainer** | — |

**Specialist (disassembly) versus builder (pure engine/data change).** Eight of
nine questions are things only the machine code says — specialist, in **four
docs-only passes** (FL1–FL4), justified under the routing table's first reason
(behaviour that exists only in machine code); Q49 is the maintainer's. Every
slice that changes engine code is **builder** — it acts on data the engine
already decodes or on facts a preceding pass records; the builder has not been
tried on any of them yet, so none goes to the specialist "to be safe". A card
the builder hands back with `kind=needs_input` and a stated reason goes to the
specialist **once**.

---

## 4. Slices

Fifteen cards: four docs-only disassembly passes, ten builder PRs, one closing
synthesis. Each is independently reviewable, branches from the then-current
`main`, and carries the standard card contract (Context / Goal / Acceptance /
Verify / Constraints) and the routing note: **code and the reviewer's verdict
come from `.claude-agent/bin/claude-task`, the worker owns the brief,
verification, PR and board state, and exit `75` means park the card — do not
reassign it.** Skills are named in each card body (`retro-game-modernization`,
`github`), not attached.

### 4.1 The table

| Slice | Work | Owner | Depends on | Files | Acceptance |
|---|---|---|---|---|---|
| **FL1** | *Disassembly — level flow, start and fail.* Q41, Q42, Q48: the title → map → section path from the reset `0x40EDC0` and the selector `0x417C2C`; the `Exit`/`Finish`/`Revive` handlers and what they write to `0x4645C4`/`0x4645BC`; the death/pit rule and respawn; the spawn build `0x40F856`: origin, facing, jump kind, box. Output: `file-formats.md` §2.10, Q41/Q42/Q48 closed or narrowed with VAs. **Docs only.** | **specialist** | — | `docs/file-formats.md`, `docs/research/05-open-questions.md` | every claim has a VA and a grade; every number re-run with its command |
| **FL2** | *Disassembly — collision and flips.* Q43 + Q31 + Q33: the per-value meaning of `0xC0 … 0xF0` and their low bits from the collision probes (`0x413940`, the terrain dispatch `0x413C93`) and the hero's wall/floor code; which flip bit is horizontal from the strides of `0x415686`/`0x4156A8`. **Docs only.** | **specialist** | FL1 (same two files) | same | a table `value → class` for L1's eight values; Q33 closed |
| **FL3** | *Disassembly — backdrop and camera.* Q44, Q45: the `ScrollMap`/`Parallax`/`Birds` handlers (scroll ratio, order, what draws the sky) and the palette/blend of the backdrop; the camera-follow routine. **Docs only.** | **specialist** | FL2 | same | ratios and rule with VAs, or named `[H]` with the video as the only evidence |
| **FL4** | *Disassembly — objects and HUD.* Q46, Q47: the 15 handlers of L1's names via `0x4647B8` — role, idle clip, what each does at contact (only to *classify*; no AI port) — and the HUD's sprite sources, positions, initial values and the `Moneybag` coin value. **Docs only.** | **specialist** | FL3 | same | the `name → role → idle clip → grade` table for 15 names; the four HUD elements specified |
| **FL5** | *The section concept.* `engine/sections.py`: the 24-entry table as constants citing `0x466450` (world, plane set, per-sub-level selectors, sub-level count) and a resolver `section, sublevel → (world file, playfield, backdrop planes)`; `Level` loads and carries the backdrop planes and their `ScrollMap`/`Parallax` placements (decoded, not yet drawn); `slice`/`play` gain `--section/--sublevel`; `VILLAGE`/`ED` stay selectable and are reported as sections 2 / 18. The runtime never reads `LOMAX.EXE` (decision D3). | **builder** | — (parallel with FL1–FL4: docs versus code, disjoint files) | `engine/sections.py` (new), `engine/level.py`, `cli.py`, `tests/unit/` | AC1; unit tests on a synthetic table; `python3 -m lomax_modern slice … --section 0 --sublevel 0` prints the AC1 lines |
| **FL6** | *Object roles.* The `name → role` table for L1's 15 names (extending `anim_nmy.PLACEMENT_ROLES`, grade per row from FL4); `slice` prints the AC5 block. No drawing yet. | **builder** | FL5, FL4 | `anim_nmy.py`, `engine/level.py`, `cli.py`, tests | AC5: `objects: 52 placements, 15 names, 0 unresolved` |
| **FL7** | *Collision semantics.* `CollisionModel` implements FL2's classes for the eight values (and keeps unknown values on the conservative solid rule, printed); the axis resolution in `state.py` uses them; tile-flip pairing follows Q33's answer. | **builder** | FL6, FL2 | `engine/level.py`, `engine/state.py`, `engine/render.py` (flips only), tests | AC2, AC3; the `collision:` block; synthetic-`MAP` tests per class |
| **FL8** | *Physics fidelity and start state.* The jump gravity gate (5/10 ticks), the hold-to-rise counter (`file-formats.md` §2.9), the start state and origin from FL1 (resolves the engine's `JUMP_STRAIGHT_AT_LEVEL_START`, Q40a, if FL1 answers it). | **builder** | FL7, FL1 | `engine/state.py`, `engine/entities.py`, tests | AC7; unit tests assert the measured gating; the 120-tick `clips:` line is re-measured and plan 46's AC1/AC2 lines updated if they move |
| **FL9** | *Backdrop rendering.* Draw planes 11–13 behind plane 0 with FL3's ratios, order, sky source and palette/blend. Measures AC13 at this point. | **builder** | FL7 (level.py order), FL3 — **parallel with FL8** (render/level vs state/entities) | `engine/render.py`, `engine/level.py`, tests | AC4, AC13; frame at spawn vs the screenshot by the maintainer's eye |
| **FL10** | *Placed-object sprites.* Draw each of the 52 placements with its idle clip from FL4's table through the existing clip machinery; `hidden by design` list; static (no AI). | **builder** | FL9, FL6 | `engine/render.py`, `engine/level.py`, tests | AC6, AC13: `sprites: N/52 drawn, M hidden by design, 0 missing` |
| **FL11** | *Rules.* Lives (3), the pit/fail rule and respawn (FL1), `Revive` checkpoints, `Moneybag` value, `Exit` region and level-complete, game-over state. | **builder** | FL8, FL10, FL1, FL4 | `engine/state.py`, `engine/entities.py`, `cli.py`, tests | AC8 (trigger), AC9 |
| **FL12** | *Camera.* The follow rule from FL3 (or the video-measured rule, graded `[H]`), clamps, backdrop scroll against it. | **builder** | FL11, FL3 | `engine/render.py`, tests | AC10 |
| **FL13** | *HUD.* Four elements from the original's sprites at the reference layout; lives and coins live. | **builder** | FL12, FL4 | `engine/render.py`, `cli.py`, tests | AC11, AC13 |
| **FL14** | *Witness solver.* `slice --input FILE` (per-tick key states) and `solve` (a search over the engine's physics, collision and objects from `Start` to `Exit` collecting both `Moneybag`s); writes outside the repo; no retail-derived file is committed. | **builder** | FL13 | `engine/solve.py` (new), `cli.py`, tests | AC8, AC12; `solve` prints length ≥ 1,495 ticks or names why none exists |
| **close** | *Synthesis.* On merged `main`, re-derive the merge gate, run **every** AC in §2.1 by execution on the real install, run `solve` and replay its witness, record the clip and attach it to the card (**never committed**), file the verdict per AC. | **lead** | all of the above | — | the AC table filled with command output; clip attached |

Order: `FL1 → FL2 → FL3 → FL4` (the four docs passes share two files, so they are
serial), `FL5` in parallel with them (code versus docs), then `FL6 → FL7 → (FL8 ∥
FL9) → FL10 → FL11 → FL12 → FL13 → FL14 → close`. FL8 and FL9 are the only
parallel pair among builder slices: FL8 touches `state.py`/`entities.py`, FL9
`render.py`/`level.py`.

**Hotspots.** `engine/render.py` is touched by FL7, FL9, FL10, FL12, FL13;
`engine/state.py` by FL7, FL8, FL11; `engine/level.py` by FL5, FL6, FL7, FL9,
FL10; `cli.py` by FL5, FL6, FL11, FL13, FL14. That is why the builder chain is
serial except FL8 ∥ FL9: each slice branches from the main that contains its
predecessor, and an `FL` card does not start until its predecessor's PR is merged
(the start-up check; the `chain-unblock-watch` cron releases a card blocked on
"PR #N not merged"). If a slice's diff collides with a sibling's or touches a file
named in another card's comments, the worker leaves a `hotspot: <path> — <reason>`
comment and repeats it in its completion metadata.

**Fallbacks that keep the chain moving.** If FL2/FL3/FL4 cannot resolve a
question after one rework, the dependent builder slice proceeds with the
conservative rule, **labelled `[H]` in the code, the `slice` output and the
docs**, and the question stays open in `05-open-questions.md` with the
narrowing — the AC then closes as *partial* in the synthesis, with the named
cause, never as a pass.

### 4.2 After approval

On the maintainer's approval of this PR the lead creates these cards —
parent-linked, serial as above, each starting with a check that its
predecessor's PR is merged — and does not create review or merge cards (the
crons do). Until then, **no implementation card exists.**

### 4.3 Housekeeping, folded in

`docs/roadmap/46-character-animation-plan.md`'s Status block said "AC1–AC9 are
verified". AC8 (duck) and AC9 (idle) were verified by unit tests only until the
maintainer watched the animations on a real display (Wayland, his machine) on
2026-11-24 and judged them correct. **Corrected in this PR** — one sentence, no
slice needed. AC1–AC7 were verified by execution on merged `main`
(synthesis card `t_7ecf0316`).

---

## 5. Risks, non-goals and decisions for the maintainer

| # | Risk | What it could do | Smallest experiment that retires it |
|---|---|---|---|
| **R1** | **L1 is not completable on a faithful engine**: the route needs `Jumppad`/`Rope`/`Pots` behaviour, or a jump the engine does not yet have (G8) | AC8/AC12 cannot close; FL14 is a no-go | A purely geometric reachability pass (jump arcs on the collision grid, no objects) run at FL7 — it needs no new engine feature and says early whether objects are on the route. Fallback: the maintainer plays L1 by hand and the closing card says so; the AC is then *partial*, not passed |
| **R2** | **The sky has no tile source** (planes 13 and 16 are empty) and FL3 cannot find what draws it | the backdrop looks wrong in the one place the reference makes obvious | Read the `Parallax` record's `PARA` clip sprites and the plane-13 `Parallax` placement first (a short read in FL3); fallback: the `PARA` sprite or a `[H]` gradient, graded as such |
| **R3** | **Collision classes stay `[H]`** (Q43) | wrong platforms (a one-way ledge solid, a slope a wall) — the first thing a player feels | FL2 reads two probes; the synthetic-`MAP` tests pin whatever is found; unresolved values are printed and listed on the card |
| **R4** | **The references are a console capture** (Q49) | HUD layout, view width or translucency differ from the PC build; criteria anchored to the video drift | Criteria are anchored to code and data, not to the video (§1.3); the maintainer answers Q49 |
| **R5** | **Pure-Python rendering at ≈ 60 fps** with three backdrop layers, 52 sprites and a HUD: today one layer and no sprites ran 59.9 fps | AC13 fails at FL10 or FL13 | AC13 is measured at FL9 and FL10, not only at the end; the dirty-region or cached-layer fix is a slice-local change |
| **R6** | **Embedding the section table** (D3) is a decision, not a free move | the repository would carry a table derived from the executable | It is 24 rows of small integers with a VA citation — structure, not content, like the 89-name table and the §2.9 constants; if the maintainer rejects it, FL5 takes it from a user-supplied file instead |
| **R7** | **Serial chain on three hot files** | longer elapsed time | Accepted: it is the trade for not re-reviewing; FL8 ∥ FL9 is the only safe overlap |
| **R8** | **Plan-limit stop** | a card parks mid-slice | Exit `75` parks it; resume when the window reopens; no reassignment, no model switch |

**Non-goals.** Audio; enemy and NPC behaviour and contact damage; hero attacks,
climbing, helicopter, swimming, doors; every other sub-level and section; the
title, map, password and level-complete screens; a gamepad, rebinding and
widescreen (still deferred as in [`45`](45-playable-level-plan.md));
pixel-identical output.

**Hard rules, restated for every card** (`AGENTS.md`):

* **No game bytes, ever** — no sprite pixels, no extracted art, no tile data, no
  level dumps, no full hash of a copyrighted binary in the repository, tests,
  issues, PR bodies or CI logs. Rendered frames, clips and the witness input list
  are attached to cards or kept in `/tmp`, never committed. Tests use synthetic
  fixtures. The scripts in §6 print names and small integers only.
* The retail install stays **outside Git and read-only** (`LOMAX_GAME_DIR`); the
  CLI already refuses to write into a folder that holds `LOMAX.EXE`. The two
  reference files stay outside the repository and are never copied, quoted or
  hashed.
* **No code from unlicensed projects** (`Lomax+` has no licence: facts, not code).
* **No CD-check bypass.** No upstream PRs. No push to `main`; every commit
  signed (`git log -1 --format=%G?` prints `G`).

### 5.1 Decisions the maintainer is asked to make

| # | Decision | Recommendation |
|---|---|---|
| **D1** | The unit: **A** (section 0, sub-level 0 = plane 0) or **B** (all three sub-levels of section 0)? | **A**; B is the next milestone |
| **D2** | **Enemy behaviour** stays out of scope — enemies are drawn and static, and the only way to lose a life is the fail rule from FL1? Or is at least `Henchlemming` (8 in L1) in? | Out, as written; moving them is a separate milestone with its own passes, and "fully recreated" is then *as to geometry, objects, rules, camera and HUD* |
| **D3** | May the engine carry the 24-entry section table as constants citing `0x466450` (R6)? | Yes; the runtime still never reads `LOMAX.EXE` |
| **D4** | Q49: are the screenshot and the video PC or console captures? Is the screenshot a section-0 scene, or section 3? | Answer when convenient; nothing blocks on it |

---

## 6. Reproduce every number

Every command runs read-only against the install. The scripts print names and
small integers, never pixels or tile data. Save each fenced block below under
the file name on its first line, in an **empty scratch directory outside the
repository**, and run it with `PYTHONPATH=<repo>/src python3 <file> …` from
elsewhere. `INSTALL` is `$LOMAX_GAME_DIR` (`/game-files/LOMAX (1)/LOMAX` here);
`EXE` is `$INSTALL/LOMAX.EXE`.

| Number | Command |
|---|---|
| The 24-entry section table, sub-level → active planes, world names (§1.2) | `python3 leveltab.py "$EXE"` (A) |
| Plane sizes of `MEDIEVAL` (plane 0 198 × 40 = 3,168 × 640 px; planes 11–13) | `python3 planes_info.py "$INSTALL" MEDIEVAL` (B) |
| Plane 0: 52 placements, 15 names, table index of each, 0 unmatched (§1.4, G5) | `python3 plane0_roles.py "$INSTALL" MEDIEVAL 0` (C) |
| `Start`/`Exit`/`Finish`/`Revive`/`Moneybag` per plane (planes 0–2 each have a `Start`; `Exit` in 0, 1; `Finish` in 2) | `python3 roles.py "$INSTALL" MEDIEVAL` (D) |
| Planes 13 and 16 have 0 cells with a visible pixel; planes 11 and 12 have 323 and 212 (§1.3) | `python3 opaque_census.py "$INSTALL" MEDIEVAL 0 11 12 13 14 15 16` (E) |
| `ScrollMap` second parameter 50 on plane 11 and 25 on plane 12 (Q44) | `python3 parallax_entries.py "$INSTALL" MEDIEVAL 0 11 12 13` (F) |
| Spawn (89, 407), first solid row 30 (y = 480), bottom map row 0 non-zero, sky pixel (G2, G6, G7) | `python3 spawn_probe.py "$INSTALL"` (G) |
| 22 held-right + periodic-jump runs: max x 3,156, final y 625–626, 0 complete, first tick on the bottom border 382 (*p* = 15) … 879 (*p* = 105), 397 for *p* = 30 (G7, AC9) | `python3 reach.py "$INSTALL" MEDIEVAL 0` (H) |
| Plane-0 collision histogram, spawn, 2 `Moneybag`s, `Exit (3079, 444)`, `GNMY markers: 52 placements … start 1, exit 1, moneybag 2, other 48`, `clips: WALK 34, JMP2 62, FLO2 24` (G4, G5, G11) | `python3 -m lomax_modern slice "$INSTALL" --world MEDIEVAL --frames 120 --out /tmp/med` |
| `play`: 120 frames in 2.00 s, mean 59.9 fps; the one-line HUD (G10) | `SDL_VIDEODRIVER=dummy python3 -m lomax_modern play "$INSTALL" --world MEDIEVAL --seconds 2` |
| `VILLAGE`/`ED` are sections 2 / 18: planes in §1.1 | script (A) rows 2 and 18 |
| 2,990 px, 1,495 ticks, 24.9 s | arithmetic: `3079 − 89`, `/ 2.0`, `/ 60` |
| Screenshot size 800 × 446 | `python3 jpeg_size.py <path>` (I; header only) |
| Video: 1920 × 1080, 59.94 fps, 398.8 s | `ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate -of default=nw=1 "<video>"` |
| Video frames of §1.3 (contact sheets, looked at, not committed) | `ffmpeg -v error -i "<video>" -vf "fps=1/10,scale=384:216,tile=5x4" -frames:v 1 sheet.png` (put `-ss 200 -t 200` before `-i` for the second half; `fps=1/3.5` with `-ss 320 -t 79` for the last minute) |
| Per-plane renders of §1.3 (tile art, `HEAD` slot 1; transparent drawn as a flat colour) | `python3 plane_full.py "$INSTALL" MEDIEVAL /tmp/bd.png 1 11 12 13` (J) |
| Instruction-level claims of §1.2 (VAs) | `objdump -d -M intel --no-show-raw-insn "$EXE" > dis.txt` (to a scratch file), then read the cited addresses |
| Initial `0x4645C4`/`0x4645BC` = 0 | script (A) prints the table; the two words are read from the `.data` image at file offset `0x5FA00 + (VA − 0x461000)` |

```python
# file: leveltab.py  (A) — decode the section table at VA 0x466450 (stride 24)
import struct, sys
d = open(sys.argv[1], "rb").read()
secs = [(0x401000, 0x400, 0x57e00), (0x459000, 0x58200, 0x7800), (0x461000, 0x5fa00, 0x8a00)]
def off(va):
    for v, r, s in secs:
        if v <= va < v + s:
            return r + va - v
worlds = ["MEDIEVAL","VILLAGE","HAUNTED","WEST","ED","BONUS","MAP","TITLE","LOGO","MAIN"]
base = 0x466450
for i in range(24):
    o = off(base + 24 * i)
    M, A = struct.unpack_from("<II", d, o)
    w = d[o + 10]
    cnt = struct.unpack_from("<H", d, o + 12)[0]
    sel = struct.unpack_from("<5H", d, o + 14)
    ranked = [p for p in range(32) if M >> p & 1]
    subs = [[ranked[r] for r in range(len(ranked)) if sel[k] >> r & 1] for k in range(cnt)]
    print(f"section {i:2d} {worlds[w]:8s} M={M:#x} A={A:#x} subs={cnt}: {subs}")
for name, va in (("0x4645C4 section", 0x4645c4), ("0x4645BC sub-level", 0x4645bc)):
    print(name, "initial", struct.unpack_from("<I", d, off(va))[0])
```

```python
# file: planes_info.py  (B) — plane sizes and the most common placed names
import sys
from collections import Counter
from pathlib import Path
from lomax_modern import art, wld
from lomax_modern.engine import level as L
w = wld.parse_file(Path(sys.argv[1]) / "WORLDS" / f"{sys.argv[2]}.WLD")
secs, per = art.planes(w), L._decode_gnmy_per_plane(w)
for i, s in enumerate(secs):
    pl = s.plane
    c = Counter(e.name for e in per[i]) if i < len(per) else Counter()
    print(f"plane {i:2d} {pl.width_cells}x{pl.height_cells} cells = {pl.width_cells*16}x{pl.height_cells*16} px; gnmy={sum(c.values())}", dict(c.most_common(8)))
```

```python
# file: plane0_roles.py  (C) — placed names -> index in the executable's 89-name table
import sys
from collections import Counter
from pathlib import Path
from lomax_modern import wld
from lomax_modern.engine import level as L
install, world, plane = sys.argv[1], sys.argv[2], int(sys.argv[3])
exe = (Path(install) / "LOMAX.EXE").read_bytes()
tab = 0x464650 - 0x461000 + 0x5fa00
names = [exe[tab + 4 * i: tab + 4 * i + 4] for i in range(89)]
def tab_index(n):
    key = n[:4].encode("latin-1")
    return next((i for i, t in enumerate(names) if t == key or t[::-1] == key), None)
w = wld.parse_file(Path(install) / "WORLDS" / f"{world}.WLD")
c = Counter(e.name for e in L._decode_gnmy_per_plane(w)[plane])
print("placements", sum(c.values()), "distinct names", len(c))
unmatched = 0
for n, k in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])):
    ti = tab_index(n)
    unmatched += k if ti is None else 0
    print(f"  {n!r:16} x{k:3d}  table_idx={ti}")
print("placements matching no table entry:", unmatched)
```

```python
# file: roles.py  (D) — Start/Exit/Finish/Revive/Moneybag per plane
import sys
from collections import Counter
from pathlib import Path
from lomax_modern import wld
from lomax_modern.engine import level as L
w = wld.parse_file(Path(sys.argv[1]) / "WORLDS" / f"{sys.argv[2]}.WLD")
for i, es in enumerate(L._decode_gnmy_per_plane(w)):
    c = Counter((e.name or "")[:4] for e in es if (e.name or "")[:4] in ("Star", "Exit", "Fini", "Revi", "Mone"))
    print(i, dict(c))
```

```python
# file: opaque_census.py  (E) — map cells whose tile has any non-transparent pixel
import sys
from pathlib import Path
from lomax_modern import art, wld
w = wld.parse_file(Path(sys.argv[1]) / "WORLDS" / f"{sys.argv[2]}.WLD")
secs = art.planes(w)
cells = art.decode_cells(next(c for c in w.chunks if c.tag == "CELL"))
for p in map(int, sys.argv[3:]):
    s = secs[p]; pl = s.plane
    opaque = [any(any(cells[sl.index].pixels) for sl in t.slots if 0 <= sl.index < len(cells)) for t in s.tiles]
    n = sum(1 for y in range(pl.height_cells) for x in range(pl.width_cells)
            if 0 <= pl.at(x, y).tile_word < len(opaque) and opaque[pl.at(x, y).tile_word])
    print(f"plane {p}: {pl.width_cells}x{pl.height_cells} cells, {n} with visible pixels")
```

```python
# file: parallax_entries.py  (F) — Parallax/ScrollMap/Birds/Music placements (structure only)
import sys
from pathlib import Path
from lomax_modern import wld
from lomax_modern.engine import level as L
w = wld.parse_file(Path(sys.argv[1]) / "WORLDS" / f"{sys.argv[2]}.WLD")
per = L._decode_gnmy_per_plane(w)
for p in map(int, sys.argv[3:]):
    for e in per[p]:
        if e.name in ("Parallax", "ScrollMap", "Birds", "Music", "ForceScrolling"):
            print(p, e.name, "x", e.x, "y", e.y, "flags", hex(e.flags), "params", e.params)
```

```python
# file: spawn_probe.py  (G) — spawn, first solid row below it, bottom row, placeholder sky
import sys
from pathlib import Path
from lomax_modern.engine.level import load_level
from lomax_modern.engine.state import new_game_state
from lomax_modern.engine.render import render_tiles, COLOUR_SKY
lv = load_level(Path(sys.argv[1]) / "WORLDS" / "MEDIEVAL.WLD", playfield=0)
sx, sy = lv.spawn
first = next((r for r in range(sy // 16, lv.plane.height_cells) if lv.solid_at(sx // 16, r)), None)
print("spawn", (sx, sy), "first solid row below ->", first, "y px", first * 16)
print("bottom map row non-zero collision bytes:", sum(1 for c in range(lv.plane.width_cells) if lv.collision_at(c, lv.plane.height_cells - 1)))
f = render_tiles(lv, new_game_state(lv))
print("frame0 (0,0) is COLOUR_SKY:", f.pixel(0, 0) == COLOUR_SKY, "(319,0):", f.pixel(319, 0) == COLOUR_SKY)
```

```python
# file: reach.py  (H) — how far a held-right + periodic-jump script gets
import sys
from pathlib import Path
from lomax_modern.engine.level import load_level
from lomax_modern.engine.state import new_game_state
from lomax_modern.engine.entities import Input
lv = load_level(Path(sys.argv[1]) / "WORLDS" / f"{sys.argv[2]}.WLD", playfield=int(sys.argv[3]))
print("level px", lv.width_px, "x", lv.height_px, "exit", lv.exits, "spawn", lv.spawn)
best = 0.0; done_any = 0
for period in range(15, 121, 5):
    s = new_game_state(lv); maxx = 0.0; bottom = None
    for t in range(3600):
        s.tick(Input(right=True, jump=(t % period == 0)))
        maxx = max(maxx, s.player.x)
        if bottom is None and s.player.y + s.player.height >= lv.height_px - 1:
            bottom = t
        if s.complete:
            done_any += 1; break
    best = max(best, maxx)
    print(f"period {period:3d}: max x {maxx:7.1f}  complete={s.complete}  final y {s.player.y:.0f}  first tick on the bottom border {bottom}")
print("runs", len(range(15, 121, 5)), "best max x", best, "completed", done_any)
```

```python
# file: jpeg_size.py  (I) — pixel dimensions of a JPEG, header only
import struct, sys
d = open(sys.argv[1], "rb").read(); i = 2
while i < len(d):
    if d[i] != 0xFF:
        i += 1; continue
    if d[i + 1] in (0xC0, 0xC1, 0xC2):
        h, w = struct.unpack(">HH", d[i + 5:i + 9]); print(w, "x", h); break
    i += 2 + struct.unpack(">H", d[i + 2:i + 4])[0]
```

```python
# file: plane_full.py  (J) — whole planes, tile art, stacked into one PNG (keep it outside the repository)
import sys
from pathlib import Path
from lomax_modern import art, wld, png
from lomax_modern.renderer import Framebuffer, head_palette565
from lomax_modern.engine.render import unpack_rgb565
install, world, out, slot = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
w = wld.parse_file(Path(install) / "WORLDS" / f"{world}.WLD")
secs = art.planes(w)
cells = art.decode_cells(next(c for c in w.chunks if c.tag == "CELL"))
KEY, rows, TW, imgs = 0xF81F, [], 0, []
for p in map(int, sys.argv[5:]):
    s = secs[p]; pl = s.plane; pal = head_palette565(s.head, slot)
    W, H = pl.width_cells * 16, pl.height_cells * 16
    fb = Framebuffer(W, H, fill=KEY)
    for cy in range(pl.height_cells):
        for cx in range(pl.width_cells):
            t = pl.at(cx, cy).tile_word
            if 0 <= t < len(s.tiles):
                fb.blit_tile(s.tiles[t], cells, pal, cx * 16, cy * 16, layout="2x2")
    imgs.append((W, H, fb.pixels)); TW = max(TW, W)
for W, H, px in imgs:
    for y in range(H):
        row = bytearray()
        for x in range(TW):
            v = px[y * W + x] if x < W else KEY
            row += bytes((120, 170, 230, 255)) if v == KEY else bytes((*unpack_rgb565(v), 255))
        rows.append(bytes(row))
    rows.append(bytes((255, 0, 0, 255)) * TW)
png.write(out, TW, len(rows), b"".join(rows)); print("wrote", out, TW, len(rows))
```
