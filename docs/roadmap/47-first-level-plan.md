# 47. The first level, fully recreated — plan

> **Status: proposed — planning only.** No code and no implementation card
> exists until the maintainer approves this PR. Written against `main` =
> `290cb61` (2026-11-24). Everything marked as measured was run on the retail
> install through `LOMAX_GAME_DIR` (read-only) at that head; the command for
> each number is in [§6](#6-reproduce-every-number).
>
> **Revision 2** (2026-11-24) records the maintainer's answers to §5.1.
> **D1**: unit A, confirmed. **D2**: the `Henchlemming` must *move*, so it is in
> scope — a new disassembly pass FL4b and two builder slices FL14–FL15 (§1.4,
> §2, G13, §4, R9–R10). **D3**: the section table is read **at runtime from the
> user's own `LOMAX.EXE`** and nothing from the executable is embedded (§1.5,
> FL5/FL5b, R6). **D4**: the screenshot and the video are from a **console**
> build (§1.3, R4, Q49). Two follow-on decisions are asked in §5.1 (D5, D6).

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

> **Revision 3** (2026-11-25) records the maintainer's answer to Q57 (FL4b,
> PR #80): *"Yes, they should be killable. I see other options to kill them,
> spin attack or helmet attack for example."* **D7**: hero attacks — `SPIN`,
> the helmet throw, and `TUMB` if it is cheap — are **in scope** for L1, so the
> `Henchlemming`s are killable and the `Moneybag`s and `Pots` can be opened (a
> new disassembly pass FL4c and four builder slices FL15b–FL15e: §1.4, §2.1
> AC20–AC23, §2.3, G14, §4, R11–R12). **D8**: Q54 is read as "bring attacks
> into scope", which keeps AC12's *collects both `Moneybag`s* — that reading
> is the lead's, **not confirmed by the maintainer**; if he objects, Q54
> reverts to dropping the `Moneybag` clause of AC12 (§5.1).

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
| **A** | **Section 0, sub-level 0 = `MEDIEVAL.WLD`, playfield plane 0** (198 × 40 cells = 3,168 × 640 px), with backdrop planes 11, 12, 13 | §1.2 [V] table decode, [M] plane sizes | **Chosen by the maintainer (D1).** It is the first entry of the original's own level table, and its backdrop is the screenshot's backdrop (§1.3) |
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
bytes**, and a world-file name table at VA `0x466690`: ten 4-byte pointers,
index 0–9, to the NUL-terminated strings `MEDIEVAL.WLD`, `VILLAGE.WLD`,
`HAUNTED.WLD`, `WEST.WLD`, `ED.WLD`, `BONUS.WLD`, `MAP.WLD`, `TITLE.WLD`,
`LOGO.WLD`, `MAIN.WLD` [M: script K follows the ten pointers]. The layout below
is what the readers use; each row cites the reading instruction. The engine
reads both tables from the user's executable at runtime (§1.5, decision D3).

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
   they are set; the table at VA `0x466410` (8 entries) is the attract-mode demo
   playlist, not a map-node table (`file-formats.md` §2.10.a, FL1), and has no
   entry for section 0. So the original reaches section 0 through a title/map flow
   this pass did not trace. Index 0 being first is [V]; *that a new game lands
   in it without a map choice* is [H] (FL1).

### 1.3 Matching the maintainer's screenshot, and the video

> **D4 — the references are from a console version** (maintainer's answer,
> 2026-11-24). The screenshot and the gameplay video are captures of a
> **console** build, not of the PC game the engine targets. The HUD layout, the
> view width (16:9 here, 4:3 in the PC source frame), the translucency and the
> corner watermark may all differ from the PC build. **Consequence for every
> criterion:** the references are evidence of *scene content only* — which
> backdrop layers, which kinds of object, what sort of level — never of a
> layout, size, timing or look. Each criterion is anchored to the code and data
> of the user's PC install (`LOMAX.EXE`, the `.WLD` files); where the code does
> not say (the HUD's position, say) the criterion is graded `[H]` and says the
> reference may be wrong for the PC build. This closes Q49.

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
| The view is **16:9** (1920 × 1080; the screenshot is 800 × 446 = 1.79) while the engine's source frame is 320 × 240 (4:3, [`15`](15-strategy-report.md) §3); dithered translucency and a corner watermark | Whether any of it holds for the PC build: **both references are console captures** (D4), so the view width, the HUD layout and the translucency are not evidence about the PC game. The 16:9 view is *not* a requirement (widescreen stays deferred, [`45`](45-playable-level-plan.md)) |

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

**The `Henchlemming`** (decision D2 puts it in scope). Its name is entry **84** of
the executable's 89-name table and `0x4647B8[84]` is its handler at VA
**`0x42DD70`** [M: script M reads the two tables; the handler's *code* is not
read yet — that is FL4b]. Eight placements in plane 0, at `(701, 542)`,
`(1018, 320)`, `(1068, 544)`, `(1454, 208)`, `(1597, 246)`, `(2115, 265)`,
`(2441, 387)`, `(2997, 448)`, none with placement parameters; their flags word is
`0x0` or `0x2000` (meaning [H] — an initial facing, say) [M]. The type also
appears in planes 1–5 of the world (12, 10, 4, 7 and 8 placements), so what is
learned here serves the next milestone. Its `NMY` record carries **two clips
only, `STAY` (5 keyframes) and `JUMP` (6)** [M]: no walk-like clip, so how it
travels (a hop driven by `JUMP`, or a slide in `STAY`) is a question for FL4b —
both are [H]. The held-right + periodic-jump scripts of G7 (22 runs) pass within
**15 px** of the first placement and **23 px** of the third; the other six come
no closer than 166–349 px [M, script L]. So a scripted walk plausibly touches
the first or third; contact is not shown, which is why FL15 finds its own input
(AC18).

**D7 (revision 3): the `Henchlemming`s are killable, and the means is a hero
attack.** FL4b found that the only kills are `SPIN`, `TUMB` or a projectile
(`file-formats.md` §2.13; the defeat routine is `0x42CD00`, called from the
handler at `0x42DDF4`); the maintainer names the spin attack and the helmet
attack. The same hit (`0x413E40`, `0x414130`) is what opens the two `Moneybag`s
and the three `Pots` of L1 (§2.12.b, Q54). So hero attacks are part of this
milestone: FL4c reads them, FL15b–FL15e port them (§4).

### 1.5 Reading the section table at runtime (decision D3)

**The rule.** The 24-entry table (VA `0x466450`, stride 24) and the world-file
name table (VA `0x466690`) are **parsed from the user's own `LOMAX.EXE` each
time they are needed**, the way the engine already reads `WORLDS/*.WLD`.
**Nothing from the executable is embedded in the repository**: no table, no row,
no selector, no string copied from it, no hash of it. Constants that are
structure or physics values already in the repository (the 89-name table's
role, the four measured physics constants in `entities.py`) are not touched by
this decision.

| Question | Specification |
|---|---|
| **Where the reader lives** | `src/lomax_modern/exe_tables.py` (new, FL5): a minimal PE32 reader, `read_section_table(exe_path) -> SectionTable`, with the frozen dataclasses `SectionEntry` (plane mask, loader argument, world index, per-sub-level tuples of active plane numbers) and `SectionTable` (ten world names, 24 entries). The resolver `section, sublevel → (world file, playfield, backdrop planes)` and the reverse lookup `(world, plane) → (section, sublevel)` live in `engine/sections.py` (new, FL5) and **take a `SectionTable`; the module holds no table of its own** — called without one it raises. Only the CLI opens the file (`<install>/LOMAX.EXE`, the install path `slice`/`play` already take; FL5b) |
| **VA → file offset** | From the PE headers, not from constants: ImageBase plus each section header's VA, virtual size, raw offset and raw size give `offset = raw + (VA − sectionVA)` for a range that lies inside the section's *raw* bytes. Script K prints this mapping for the retail file (6 sections) and the three ranges that script A hard-codes equal it [M] |
| **Read-only** | `open(path, "rb")` and one `read()` of the file; no write, no temporary copy, no cache file, no hashing, no logging of bytes. The parsed table lives in memory as frozen dataclasses for the run. The CLI's existing refusal to write into a folder that holds `LOMAX.EXE` is untouched |
| **Structural validation — no hash** | The reader accepts the file only if **all** hold: an `MZ` signature and a `PE\0\0` signature at `e_lfanew`; machine `0x14C` (i386); optional-header magic `0x10B` (PE32); both tables lie wholly inside the raw bytes of a section; the name table is ten pointers that each resolve to a printable-ASCII NUL-terminated string of at most 16 bytes ending `.WLD`; and for **each of the 24 entries** the world index is `< 10`, the plane mask is non-zero, the sub-level count is `1..5`, and every sub-level's selector is non-zero and below `2 ^ popcount(mask)`. Every check compares with a small integer or a string shape; none compares with a stored copy of the executable. The retail file passes: 24 entries, 0 failing, 10 names, largest mask 13 planes, largest sub-level count 5 [M, script K] |
| **Cross-check with the data** | Resolving a level also checks that every plane it names exists in the world file (`plane <` its plane count). An executable and a data folder from different builds fail here with the same error even if the tables passed |
| **What this is not** | Not a build identity. The checks catch a *moved or reshaped* table (a different build or language whose addresses differ); a build with the same layout and different strings would pass, and that is accepted. Only the one retail install was read for this plan, so nothing is claimed about any other build |
| **The error** | A failed check raises `ExeLayoutError` (a `ValueError`) naming the check; the CLI prints one line — `error: LOMAX.EXE does not have the expected section table (<check>); a different build or language is not supported here — use --world/--playfield, or the supported install` — and exits with the CLI's existing install-error status. No traceback, no partial table, no guess |
| **Tests** | `tests/fixtures/pe.py` (new) builds a **synthetic PE-like file** in memory or `tmp_path`: invented headers, invented section VAs and invented table values — structure only. Unit tests cover the round trip, the VA mapping across two sections and one case per failed check above (bad signature, wrong machine, table outside every section, world index 12, sub-level count 0 and 6, selector 0 and out of range, a name without `.WLD`, a pointer outside the file). **No test reads a real executable**, no fixture is derived from one, and no integration test is added for `LOMAX.EXE`; the real file is exercised only by the commands of §2.1, run by the closing card on the user's install |
| **`VILLAGE` / `ED` test worlds** | Still selectable by name: `--world VILLAGE` / `--world ED` (with `--playfield`) keep working as today. When `LOMAX.EXE` is readable the reader resolves their sections **the same way** as any other: the reverse lookup takes the first `(section, sub-level)` in table order whose lowest active plane is the requested playfield — `(MEDIEVAL, 0)` → section 0, `(VILLAGE, 0)` → section 2 sub-level 0 (active planes 0 1 13 14), `(ED, 0)` → section 18 sub-level 0 (active planes 0 14 15) [M, script K] — and `slice` prints `level: section 2 sub-level 0 = VILLAGE, playfield plane 0, active planes 0 1 13 14`. When the executable is missing or fails validation, `--world` still loads the plane and prints `level: world VILLAGE, playfield plane 0 (section unknown: <reason>)` with no backdrop: the test worlds never depend on the executable. `--section N` always needs the table and stops with the error above, before any world file is opened |


---

## 2. Definition of "fully recreated"

**The unit** is option A (maintainer's answer D1): `MEDIEVAL.WLD` section 0, sub-level 0 — playfield
plane 0 with backdrop planes 11–13 — called **L1** below.

**Reachability rule for this milestone.** The last two milestones each hit an
unreachable criterion once (a 60 s run that the plane edge ends; a collectable
no scripted walk touches). So: **no criterion needs a human at the keyboard,
and none needs more than ~10 s of scripted play, except AC8/AC12, which need the
route from `Start` to `Exit`.** That route is at least `3079 − 89 = 2,990` px,
i.e. ≥ 1,495 ticks = **24.9 s** at 2.0 px/tick [derived]; the straight walk is
*not* a route — held-right scripts reach the plane's right edge at the bottom
border and never touch the `Exit` (G7). AC12 therefore makes the route itself a
deliverable, found by a solver over the engine's own physics (FL16), with a
named fallback if it cannot be found (§5, R1). Commands that do not exist yet
name the slice that adds them.

### 2.1 Acceptance criteria

`<install>` is the read-only retail folder (`$LOMAX_GAME_DIR`). New flags:
`slice`/`play` gain `--section N --sublevel M` (FL5b), `slice` gains
`--input FILE` (FL16, a list of per-tick key states — inputs only).

| # | What the maintainer sees | Command that shows it | Reachable because | Grade of the thing it checks | Slice |
|---|---|---|---|---|---|
| **AC1** | The level is named from the original's table, **read from the user's `LOMAX.EXE` at runtime** (§1.5), not from `--world`/`--playfield`: `slice` prints `level: section 0 sub-level 0 = MEDIEVAL, playfield plane 0, backdrop planes 11 12 13` and `playfield: 198x40 cells (3168x640 px)`. `VILLAGE`/`ED` stay selectable as test worlds and are reported as sections 2 / 18 | `python3 -m lomax_modern slice "<install>" --section 0 --sublevel 0 --frames 1 --out /tmp/f` | the table is decoded from the retail file today (§1.2, script K) and the plane size is measured (§6 B) | table [V]; sizes [M] | FL5, FL5b |
| **AC2** | Tile art matches the original's orientation: the flip pairing (`0x2000`/`0x4000`, Q33) is settled from the copy loops, and `slice` says `flip pairing [V]` | same, plus the maintainer's look at the witness frames at three camera positions (x = 0, 1,500, 3,000) | the four copy loops are located (`0x41566B`, `0x415686`, `0x4156A8`, `0x4156C6`, `file-formats.md` §2.8); reading their strides settles it | [V] after FL2; [H] today | FL2 (docs), FL7 |
| **AC3** | L1's **eight** collision-byte values behave as the original's: each of `0x00 0xC0 0xC8 0xD0 0xD8 0xE0 0xE8 0xF0` has a documented class (solid / one-way / slope / terrain …) with a grade, and `slice` prints one line per value. Unit tests on a synthetic `MAP` cover every class found | `…slice … --section 0 --sublevel 0` → `collision:` block | the eight values are measured (§6 B); the terrain dispatch (`0x413C93`, bits `0x30`) and the edge probe (`0x413940`) are located. **If a value stays [H] after FL2 it is named on the card, kept on the conservative solid rule, and AC3 closes as partial — it does not silently pass** | values [M]; classes [V] after FL2 | FL2 (docs), FL7 |
| **AC4** | The **backdrop is drawn**: sky, the island/tower layer (plane 12) and the trunk layer (plane 11) behind plane 0, each scrolling at its own ratio, with the original's palette. A frame at spawn is recognisably the screenshot's scene (maintainer's eye); unit tests pin the scroll ratio on a synthetic two-layer world | `…slice … --frames 120 --out /tmp/f` and the first and last frame | planes 11–13 are decoded and render (§1.3); the sky source (`Parallax` records) is named but not read yet → FL3 | layers [M]; ratios, sky source, palette/blend [H] until FL3 | FL3 (docs), FL9 |
| **AC5** | **Every placement resolved to a role.** `slice` prints `objects: 52 placements, 15 names, 0 unresolved` and a table `name → role → grade`; every name has a role label in a table citing its handler (`0x4647B8[index]`, index from `0x464650`) or an `[H]` reason; the `Henchlemming` row is `enemy — behaviour: AC16–AC18`. Today: 3 of 15 names resolved | `…slice … --section 0 --sublevel 0` → `objects:` block | all 15 names already match the 89-name table (0 unmatched, §6 B), so every handler address is known and only has to be read | roles [V] after FL4; today 3/15 | FL4 (docs), FL6 |
| **AC6** | **Every placed object is drawn with its own sprite**, in its idle/stay clip, at its placement (the `Henchlemming`s then move, AC17) — enemies, `Lorock`, `Beestjes`, `Jumppad`, `Rope`, `Pots`, `Moneybag`, `Revive` — instead of a grey square. Objects with no sprite by design (`Start`, `Music`, `Generator`, `Parallax` — which of these hold is FL4's to say) are listed as `hidden by design` with the reason. `slice` prints `sprites: N/52 drawn, M hidden by design, 0 missing` | `…slice … --frames 120` → `sprites:` line and the maintainer's look at the frames | the clips exist in `MEDIEVAL`'s `NMY` table (`Henchlemming` `STAY`/`JUMP`, `Lorock` 9 clips, `Moneybag` `HANG`/`JUMP`, `Jumppad` `PAD`, `Rope` `ROPE`, …) and the `ANIM` decode already draws the hero | clips [M]; which clip is "idle" per name [H] until FL4 | FL10, FL14 |
| **AC7** | **Start**: the hero appears where and how the original puts it (position origin, facing, jump kind at level start — Q40a, Q48), with the original's initial state; `slice` prints `start: …` with the grade of each part | `…slice … --frames 30` | `0x40ED7C`/`0x40F856` are located (`file-formats.md` §2.8) | [V] after FL1; [H] today (the engine places the 12 × 14 box top-left on `(89, 407)`) | FL1 (docs), FL8 |
| **AC8** | **Goal**: reaching the `Exit` placement completes L1; `slice` prints `result: level complete at tick N` for the witness input (AC12) and stops there. *Loading the next sub-level is out of scope* | `…slice … --input <witness> --section 0 --sublevel 0` | the `Exit` is at (3079, 444) [M]; the witness (AC12) exists by construction | trigger [V] (`0x427670`); region size [H] after FL1 | FL11, FL16 |
| **AC9** | **Fail and restart**: the original's rule for losing a life (leaving the plane's bottom is the guess [H], Q42) takes one of the **3** starting lives, respawns at the `Start` or the last-touched `Revive` (1 placement in L1), and at 0 lives reports `game over` (no screen); **if FL4b establishes that contact with a `Henchlemming` costs a life, that is a second way to lose one (AC18)**. The HUD life count follows. `slice` prints `life lost at tick N: lives 3 -> 2, respawn (x, y)` for a scripted fall | `…slice … --input <fall script>` (held right with a jump every 30 ticks; the hero first reaches the plane's bottom at tick 397 = 6.6 s today, G7) | the fall is reachable: all 22 scripted runs reach the bottom border, the last at 14.7 s (G7); lives start at 3 [V] | lives [V]; death rule, respawn rule [H] until FL1 | FL1 (docs), FL11, FL15 |
| **AC10** | **Scrolling and camera**: the viewport follows the hero by the original's rule (dead zone / lead / vertical bias, clamps), not "centre on the player"; backdrops scroll against it (AC4). `slice` prints `camera: <rule>` with its grade | `…slice … --frames 120` | the video gives the hero's on-screen offsets as a sanity check; the routine is to be found (Q45) | [H] today (centre + clamp); [V] only if FL3 finds the routine, else the video-measured rule stays [H] and is said so | FL3 (docs), FL12 |
| **AC11** | **HUD — the four elements of the reference** (§2.2) drawn from the original's own sprites at the reference's layout: item counter (top-left), the figure counter and the framed item box (top-centre), the coin counter (centre-right), the face with the life count (top-right). Lives (3) and coins are **live**; the others show their initial value, with the grade of that value. `slice` prints `hud: 4 elements, 2 live` | `…slice … --frames 120` and the maintainer's look at the frames against the screenshot | the candidate sprite records exist in `MAIN.WLD`'s table (`Display`, `Icons`, `Items`, `Inserts`, `Timer`) and the hero's face sprite is not yet located; sources are named [H] and read in FL4 | layout [H] (from the reference, not pixel-exact); values [V] only where FL4 reads them | FL4 (docs), FL13 |
| **AC11b** | **The HUD shows the weapon** the hero can throw: the weapon icon and its count follow the original's selection and counts (`0x52C58C`, six counts, `file-formats.md` §2.12.c; the helmet flag `0x52C570` and spare `0x59F1E4`), and the count falls by what FL4c establishes when the helmet is thrown. `slice` prints `hud: weapon <icon>, count N` and the changed count after a throw | `…slice … --input <attack script> --out /tmp/f` and the maintainer's look at the frames | the counters and their reset values are [V] (§2.12.c); a script that picks up the helmet and throws it is ≤ 10 s once FL4c says where the helmet comes from | counts [V]; icon position [H] (D4) | FL4c (docs), FL15e |
| **AC12** | **L1 is completable on the engine.** `lomax-modern solve` (FL16) searches the engine's own physics, collision, objects, the hero's attacks (FL15b–FL15e) and the live `Henchlemming`s (named fallbacks if that cannot finish: R9, R11 — a scripted witness for the attack parts is legitimate when it is named) for an input list from `Start` to `Exit` that also collects both `Moneybag`s — **which now means opening each with a hero attack** (D7, D8: a `Moneybag` opens only on a `SPIN`/`TUMB`/projectile hit, `0x413E40`) and catching the coins — prints its length (≥ 1,495 ticks) and writes it **outside the repo**; `slice --input` replays it to `result: level complete` | `python3 -m lomax_modern solve "<install>" --section 0 --sublevel 0 --out /tmp/witness.json && python3 -m lomax_modern slice "<install>" --section 0 --sublevel 0 --input /tmp/witness.json --out /tmp/f` | the level is a platform route 3,168 px long with a bottom pit; three `Jumppad`s and five `Rope`s may be required, and the `Moneybag`s need an attack, so FL16 depends on every behaviour slice including FL15b–FL15e. **No-go rule:** if no route exists after FL13, the cause is named and the milestone is not closed | [M] by construction | FL16 |
| **AC13** | **It runs at the original's rate**: `play` on L1 for 20 s keeps a mean ≥ 55 fps at the 4× 1920 × 1080 profile and the logic tick stays 60 Hz | `SDL_VIDEODRIVER=dummy python3 -m lomax_modern play "<install>" --section 0 --sublevel 0 --seconds 20` | today `play` on the same plane ran 120 frames in 2.00 s, mean 59.9 fps (G10), with one layer and no sprites — the added layers are what could break it, so it is measured at FL9, FL10 and FL14 (8 moving enemies), not only at the end | [M] | FL9, FL10, FL13, FL14 |
| **AC15** | **The test worlds improve as a by-product** (the other half of the maintainer's milestone): every builder slice is world-generic, so `VILLAGE` (section 2) and `ED` (section 18) draw their own backdrop planes and report their placements' roles, with no exception and no per-world code. Only L1 is graded for fidelity | `python3 -m lomax_modern slice "<install>" --section 2 --sublevel 0 --frames 30 --out /tmp/v` and the same with `--section 18` | the table covers all 24 sections (§1.2) and both worlds already load | [M] | FL5b, FL6, FL9 |
| **AC14** | **Housekeeping**: plan 46's Status sentence is corrected (done in this PR, §4.3) | `grep -n "unit tests only" docs/roadmap/46-character-animation-plan.md` | a one-line doc edit | — | this PR |
| **AC16** | **The `Henchlemming` handler is specified from the executable.** `file-formats.md` §2.11 has a row for each of: states and transitions; movement (speed, direction, what drives `JUMP`); turning; collision with the level; ledge and wall reaction; wake rule (does it act only near the camera or hero); contact with the hero (damage, life, knockback, invulnerability); whether and how it dies; randomness — each with the VA of the instruction that carries it and a grade `[V]`/`[M]`/`[H]`. Q50 closed or narrowed | `grep -n "Henchlemming" docs/file-formats.md docs/research/05-open-questions.md`, and the reviewer re-reads the cited VAs with `objdump -d -M intel --no-show-raw-insn "$EXE"` | the handler's VA is [M] today (`0x42DD70`, index 84, script M), so the read starts from a known address | [V] after FL4b | FL4b (docs) |
| **AC17** | **The Henchlemmings move** as FL4b says. `slice` prints `enemies: 8 Henchlemming, N moving, M static fallback [H]` and per enemy `henchlemming i: (x0, y0) -> (x1, y1) at tick T, clip C`. The moving ones differ between tick 0 and tick T, never leave the plane, never end inside a solid cell and stop or turn at ledges and walls as FL4b records | `python3 -m lomax_modern slice "<install>" --section 0 --sublevel 0 --frames 600 --out /tmp/f` — 600 ticks = 10 s. If FL4b finds that enemies act only near the camera or hero, the command adds `--input` of a held-right script, which passes x = 701 after at least (701 − 89) / 2.0 = 306 ticks = 5.1 s [derived] | the 8 placements are data [M]; the walk is within the ~10 s rule | rules [V] where FL4b reads them, `[H]` for every static fallback | FL14 |
| **AC18** | **Contact does what the original's does.** When the hero's box touches a living `Henchlemming` the engine applies exactly the rule FL4b establishes — damage, a life, knockback, an invulnerability window, whichever it finds — draws the hero's hurt/death clip for it and, if FL4b says the enemy can die by a movement-only means (a stomp), removes it that way. **No kill is needed in this slice any more: FL4b found none by contact, and the kill by hero attack is AC22 (FL15d).** `slice` prints `contact at tick N: henchlemming i, effect <E>`. Where FL4b leaves a rule `[H]`, contact does nothing, and `slice` says so; the enemy's death is AC22's | `python3 -m lomax_modern slice "<install>" --section 0 --sublevel 0 --input <script> --out /tmp/f`, the script found by FL15 (the G7 walks come within 15 px of the first and 23 px of the third placement, [M] script L, so a touching walk plausibly exists, but contact is not shown). Unit tests on a synthetic level and enemy cover every rule regardless | FL15 names which of the 8 placements a scripted walk can touch | rules [V]/`[H]` per FL4b | FL15 |
| **AC19** | **The section table is read from the user's executable and nothing from it is committed** (D3, §1.5). (a) With a `LOMAX.EXE` that has not the supported layout the CLI prints the one-line error and exits non-zero, before any world file is opened; (b) `--world VILLAGE` and `--world ED` still load without a usable executable; (c) the diff of `exe_tables.py`/`sections.py` carries only VAs, field offsets and bounds — no table row, selector or string of the executable, no hash | (a) `mkdir /tmp/fake && printf 'MZ' > /tmp/fake/LOMAX.EXE && python3 -m lomax_modern slice /tmp/fake --section 0 --sublevel 0 --frames 1 --out /tmp/f` (a two-byte file of invented content — no game bytes); (b) `python3 -m lomax_modern slice "<install>" --world VILLAGE --frames 1 --out /tmp/v` and, for the unusable-executable case, the unit test; (c) the reviewer reads the diff | the reader parses whatever file the CLI is handed; the synthetic fixture covers each failed check; the retail file passes the checks [M, script K] | structure [M] | FL5, FL5b |
| **AC20** | **The hero's attacks are specified from the executable (D7).** `file-formats.md` has a section with a row for each of: `SPIN` (input, states, clip, duration, hit box, what it hits, cooldown); the helmet throw (input, the projectile entity, speed / arc / range / return, hit box, what it kills or opens, the helmet flag `0x52C570`, the spare `0x59F1E4`, the weapon selection and counts, the HUD icon); `TUMB` (the `Down`-on-steep-slope kill at `0x4107A3`) with a verdict *cheap / not cheap* and why; the effect of a hit on a `Henchlemming` (defeat routine `0x42CD00`: effect, freed-lemming count, coin on an odd x, score), on a `Moneybag` (3 coins per burst, Q56) and on `Pots` (contents); **whether the hero starts L1 with the helmet or must pick it up there** (the counters are 0 at reset, §2.12.c; which placement or `Pots` content supplies a `HELM`, if any) — each with its VA and a grade. New Q58 closed or narrowed | `grep -n "SPIN" docs/file-formats.md`, and the reviewer re-reads the cited VAs with `objdump -d -M intel --no-show-raw-insn "$EXE"` | `0x413E40`, `0x414130`, `0x42CD00`, `0x4107A3`, `0x52C570`, `0x59F1E4` are known addresses [V]; the read starts from them | [V] after FL4c | FL4c (docs) |
| **AC21** | **The hero can attack as the original's does.** The `SPIN` input starts the spin state with its clip, hit box, duration and cooldown; the helmet throw (when the hero has a helmet, per FL4c) spawns the projectile with its arc and range and decrements the helmet or weapon count; both are drawn with the hero's own clips (`SPIN`, `THR1`–`THR3` as FL4c names them; the Hero's `SPIN`/attack tags are on [`46`](46-character-animation-plan.md)'s deferred list). `slice` prints `attack at tick N: spin` / `attack at tick N: helmet thrown, count a -> b` and the clips drawn | `python3 -m lomax_modern slice "<install>" --section 0 --sublevel 0 --input <attack script> --out /tmp/f`; the script is inputs only, ≤ 10 s, and is the unit-tested synthetic one on a synthetic level where the real level cannot be reached in 10 s | the inputs are keys; no enemy is needed to start a spin | input and constants [V] where FL4c reads them, `[H]` otherwise (named, kept as a named constant) | FL15b, FL15c |
| **AC22** | **A `Henchlemming` can be killed.** A `SPIN` hit, a helmet-projectile hit and, if FL4c found it cheap, a `TUMB` hit on a living `Henchlemming` run the defeat FL4c establishes (`0x42CD00`: `+0x4` := 0 at `0x42CD18`, so it **never respawns**; the freed-lemming count, the coin on an odd x, as FL4c records); the enemy is no longer drawn, no longer hurts the hero and does not come back after the camera leaves and returns or after a respawn of the hero. `slice` prints `kill at tick N: henchlemming i by <spin\|helmet\|tumb>, effect <E>` and `enemies: 8 Henchlemming, K killed` | `python3 -m lomax_modern slice "<install>" --section 0 --sublevel 0 --input <script> --out /tmp/f`, the script found by FL15d (a walk to the first or third placement, which a held-right walk comes within 15 px / 23 px of, [M] script L, plus an attack); unit tests on a synthetic level and enemy cover every rule regardless. **Both means (spin and helmet) are shown at least once** | the placements are data [M]; the attack and defeat rules come from FL4c | rules [V]/`[H]` per FL4c | FL15d |
| **AC23** | **A `Moneybag` and a `Pots` open on an attack hit** (Q54, D8). A `Moneybag` hit by `SPIN`, `TUMB` or the projectile (`0x413E40`) plays its `JUMP` clip, falls and bursts into the coins FL4c records (3 per burst, Q56); a `Pots` hit (`0x414130`) opens and releases its contents (5 coins for the one at (1238, 464) [V]); the coin counter and the HUD follow. `slice` prints `opened: moneybag i at tick N, coins +3` / `opened: pots i at tick N, +5` and `hud: coins N` | the same command with a script found by FL15d that opens a `Moneybag` and the `Pots` | the placements are data [M] (2 `Moneybag`s, 3 `Pots`; the three `Pots` and one `Henchlemming` appear only when their `Generator` fires, `file-formats.md` §2.12.b, so the script waits for it) | burst and contents [V] where FL4c reads them, Q56 `[H]` until then | FL15d |

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
| **Enemy and NPC behaviour other than the `Henchlemming`** — `Thief`, `Ufos`, `Beestjes`, `Lorock`'s speech, `Generator` spawning, every other placed name; the hurt/death animations (`OUCH`, `OHNO`) *except* what the `Henchlemming`'s contact effect needs (AC18) | each is a handler to read and port; they are *drawn* (AC6) but static. **Decision D2 moved the `Henchlemming` in** (§1.4, FL4b, FL14–FL15); the rest stays out unless FL4b finds it **inseparable** (a shared enemy base routine) — then the card names it and the maintainer is asked, it is not ported silently. **No AI port beyond the `Henchlemming`** |
| Climbing, helicopter, swimming, doors, and **every hero attack L1 does not need** (the other weapon types of the six-count selection, `0x52C58C`, beyond `SPIN`, the helmet throw and `TUMB`) | the deferred set of [`46`](46-character-animation-plan.md); L1's `Rope`s and `Jumppad`s are the exception *if* FL16 shows they are on the route. **Revision 3 (D7) moved `SPIN`, the helmet throw (`THR1`–`THR3`) and, if cheap, `TUMB` in** (§1.4, FL4c, FL15b–FL15e): they kill the `Henchlemming`s and open the `Moneybag`s and `Pots`. Their effect on any other enemy (`Thief`, `Ufos`, `Beestjes`) is **not** ported: those stay static (§2.3 first row) and an attack that hits one does nothing in this milestone |
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
| G3 | **Tile art, plane 0** | composed correctly in the sense of §1.3 — the same ferns, orange earth, vine trunk as the reference; flip pairing was the decoder's convention when this row was written; Q33 is now answered [V] from the copy loops (`file-formats.md` §2.8: `0x2000` horizontal, `0x4000` vertical, `0x6000` both) and the decoder's pairing is right | **works** (was: one [H]) |
| G4 | **Collision** | plane 0 has **8 distinct collision values**: `0x00` 7,624, `0xC0` 76, `0xC8` 114, `0xD0` 26, `0xD8` 18, `0xE0` 26, `0xE8` 18, `0xF0` 18 (sum 7,920 = 198 × 40; 296 non-zero = 3.7 %). The engine treats every non-zero as solid from all sides. The high nibbles `C`/`D`/`E`/`F` map onto the terrain bits (`0x30`, §2.9) as 0/1/2/3 [derived, no routine read] — so up to four classes may be folded into one | **wrong in an unknown amount** (Q31, Q43) |
| G5 | **Placed objects** | 52 placements, 15 names, 0 unmatched in the 89-name table; the engine resolves 3 names (`Start`, `Exit`, `Moneybag` = 4 placements), draws **48 grey 3 × 3 markers** for the rest and nothing for the sprites. The 8 `Henchlemming`s (D2) are among the 48: they are markers — no sprite, no movement (G13) | **mostly missing** |
| G6 | **Spawn** | `Start (89, 407)`; the first solid row below that column is y = 480 in the engine (the original's surface rule gives 496, `file-formats.md` §2.9.d item 7 [M], Q52), so the hero falls 73 px from where the engine puts its 12 × 14 box's top-left. Whether `Start` is the box's top-left or the actor's feet origin is untraced (Q48) | **works**, origin [H] |
| G7 | **Goal and fail** | `Exit (3079, 444)`, 2 `Moneybag`s. A held-right script with a jump every *p* ticks (*p* = 15…120 step 5, 22 runs, 3,600 ticks each) reaches x = 3,156 in **all 22 runs** and ends at y = 625 or 626 with `complete = False` in all 22: the hero walks along the **bottom border** — the off-map sentinel is solid, so there is no pit. It first touches that border at tick 382 (*p* = 15) to 879 (*p* = 105), i.e. 6.4–14.7 s. The bottom map row has 0 non-zero collision cells. There is no life, no death, no respawn, no `Revive` | **wrong** (no fail state) and **missing** (rules) |
| G8 | **Physics** | `entities.py` carries the four measured constants; `file-formats.md` §2.9 records that the original **skips gravity for 5/10 ticks after a jump** and **raises with reduced gravity while jump is held**, neither implemented — the engine's jump is shorter than the original's. Whether the platforms of L1 need the longer jump is unknown | **partly wrong** (known) |
| G9 | **Camera** | centred on the hero's box and clamped to the plane; measured on the `play` HUD line at spawn: `camera=(0,353)`. The original's rule is untraced (Q45) | **works as a placeholder**, [H] |
| G10 | **HUD and rate** | the HUD is one **text line**: `fps=60.2 plane=MEDIEVAL tiles=7920 camera=(0,353) collect 0/2`; no icons, no lives, no coin sprite. `play --world MEDIEVAL --seconds 2` under `SDL_VIDEODRIVER=dummy`: 120 frames in 2.00 s, mean 59.9 fps | rate **works**; HUD **missing** |
| G11 | **Hero** | the 120-tick slice prints `clips: WALK 34, JMP2 62, FLO2 24`: the clip machinery works on this plane | **works** |
| G12 | **Tests of retail data** | the repository's tests use synthetic fixtures only; nothing asserts anything about L1 | by design; the closing card checks by execution |
| G13 | **Enemies** | `grep -in -e enem -e hurt -e damage src/lomax_modern/engine/*.py` prints nothing: the engine has no enemy entity, no contact test, no hurt state and no life loss. The `Henchlemming` has a handler (`0x42DD70`), two clips (`STAY` 5, `JUMP` 6) and 8 placements in L1 (§1.4, [M]); none of its behaviour has been read | **missing** — the largest new block after D2 |
| G14 | **Hero attacks and openable objects** (D7) | `grep -in -e spin -e throw -e helmet -e projectile src/lomax_modern/engine/*.py` prints nothing (re-run on the PR head): no attack state, no projectile, no hit test, no helmet or weapon counter, no `Moneybag`/`Pots` opening, no defeat; the Hero's `SPIN` and attack clip tags are known to the animation code but unplayed (plan 46 deferred list); the two `Moneybag`s are drawn at most as a role marker. FL4b/FL4 found the handlers (`0x413E40`, `0x414130`, `0x42CD00`) but not the attack's own code | **missing** — a block of the size of D2's, behind a disassembly pass (FL4c) |

**What already works**, in short: reading the world, composing plane 0's tile
art, resolving three roles, the 60 Hz tick with the original's four physics
constants, the hero's clips, keyboard `play`, 4× presenter at ≈ 60 fps.
**What is wrong:** all-solid collision, no pit, a jump shorter than the
original's. **What is missing:** backdrop, objects, enemies (D2), rules, camera,
HUD, the section concept.

### 3.1 New open questions (a `Q` block)

These are added to [`05-open-questions.md`](../research/05-open-questions.md)
as Q41–Q50 in this PR (Q49 already answered by the maintainer, D4).

| # | Question | Needs | Slice |
|---|---|---|---|
| **Q41** | How does a new game reach section 0 — title → map → which node? The reset `0x40EDC0` sets the title and map flags and the `0x466410` table is the attract-demo playlist, not a map-node table (`file-formats.md` §2.10.a), so it has no section-0 entry | **disassembly (specialist)** | FL1 |
| **Q42** | Level flow and the fail rule: what the `Exit` handler (`0x427670`) does to the section/sub-level counters; what the `Finish` and `Revive` handlers do; what takes a life (pit, enemy, drowning?) and where the hero respawns; what a spent `Credit` does | **specialist** | FL1 |
| **Q43** | The eight collision values of L1 (`0xC0 … 0xF0`): solid / one-way / slope / terrain, and the use of the low bits (narrows Q31) | **specialist** | FL2 |
| **Q44** | The backdrop: draw order and scroll ratios of the three planes (the second `ScrollMap` parameter is 50 on plane 11 and 25 on plane 12 — a ratio is the guess [H]); what draws the sky (planes 13 and 16 are empty); why the engine's palette makes the islands teal where the reference is pale (blend, a different palette slot, or a fog) | **specialist** | FL3 |
| **Q45** | The camera rule: dead zone, lead, vertical bias, clamps; what `ForceScrolling` (present in plane 10 of this world) does | **specialist** | FL3 |
| **Q46** | The HUD: which sprites, positions, initial values and update rules for the four elements; the coin value of a `Moneybag` | **specialist** | FL4 |
| **Q47** | The role and idle clip of each of L1's 15 names, and which of them the route to `Exit` needs (`Jumppad`, `Rope`, `Pots`, …) | **specialist** | FL4 |
| **Q48** | `Start`'s origin (box top-left or actor feet), the hero's initial facing and jump kind (Q40a) and collision box | **specialist** | FL1 |
| **Q49** | Provenance of the maintainer's references: PC or console capture, and what differs (HUD layout, view width, translucency) | **answered by the maintainer (D4): both are from a console version**; HUD layout, view width and translucency may differ from the PC build, so criteria stay anchored to code and data (§1.3) | — |
| **Q50** | The `Henchlemming` handler `0x42DD70` (D2): states and transitions; movement (speed, direction, what drives `JUMP`); turning; collision with the level (which probe, which box); ledge and wall reaction; wake rule; contact with the hero (damage, life, knockback, invulnerability); whether and how it dies; randomness; which routines it shares with the other enemy handlers | **disassembly (specialist)** | FL4b |

| **Q54** | (answered, FL4/FL4b) The `Moneybag` and `Pots` open only on a `SPIN`/`TUMB`/projectile hit (`0x413E40`, `0x414130`) | **maintainer: read as "bring attacks into scope" (D8), not confirmed** | FL15d |
| **Q57** | Must the `Henchlemming`s be killable? | **answered by the maintainer (D7): yes, by the spin or the helmet attack** | FL15d |
| **Q58** | The hero's attacks: `SPIN` (input, states, clip, duration, hit box, what it hits, cooldown); the helmet throw (input, projectile entity, speed/arc/range/return, hit box, interaction with `HELM`, `0x52C570`, `0x59F1E4`, the weapon icon and count); `TUMB` and whether it is cheap; what a hit does to a `Henchlemming` (`0x42CD00`), a `Moneybag` and `Pots`; whether the hero starts L1 with the helmet. (The number is the next free after Q57; FL4c takes the next free one if it is taken.) | **disassembly (specialist)** | FL4c |

**Specialist (disassembly) versus builder (pure engine/data change).** Nine of
ten questions are things only the machine code says — specialist, in **six
docs-only passes** (FL1–FL4, FL4b and, from revision 3, FL4c for Q58), justified
under the routing table's first reason (behaviour that exists only in machine
code); Q49 is answered (D4). Every
slice that changes engine code is **builder** — it acts on data the engine
already decodes, on the executable's tables through the reader FL5 adds, or on
facts a preceding pass records; the builder has not been tried on any of them
yet, so none goes to the specialist "to be safe". A card the builder hands back
with `kind=needs_input` and a stated reason goes to the specialist **once**.

---

## 4. Slices

Twenty-four cards: six docs-only disassembly passes, seventeen builder PRs, one
closing synthesis (revision 3 added FL4c and FL15b–FL15e). Each is independently reviewable, branches from the
then-current `main`, and carries the standard card contract (Context / Goal /
Acceptance / Verify / Constraints) and the routing note: **code and the
reviewer's verdict come from `.claude-agent/bin/claude-task`, the worker owns
the brief, verification, PR and board state, and exit `75` means park the card —
do not reassign it.** Skills are named in each card body
(`retro-game-modernization`, `github`), not attached.

### 4.1 The table

| Slice | Work | Owner | Depends on | Files | Acceptance |
|---|---|---|---|---|---|
| **FL1** | *Disassembly — level flow, start and fail.* Q41, Q42, Q48: the title → map → section path from the reset `0x40EDC0` and the selector `0x417C2C`; the `Exit`/`Finish`/`Revive` handlers and what they write to `0x4645C4`/`0x4645BC`; the death/pit rule and respawn; the spawn build `0x40F856`: origin, facing, jump kind, box. Output: `file-formats.md` §2.10, Q41/Q42/Q48 closed or narrowed with VAs. **Docs only.** | **specialist** | — | `docs/file-formats.md`, `docs/research/05-open-questions.md` | every claim has a VA and a grade; every number re-run with its command |
| **FL2** | *Disassembly — collision and flips.* Q43 + Q31 + Q33: the per-value meaning of `0xC0 … 0xF0` and their low bits from the collision probes (`0x413940`, the terrain dispatch `0x413C93`) and the hero's wall/floor code; which flip bit is horizontal from the strides of `0x415686`/`0x4156A8`. **Docs only.** | **specialist** | FL1 (same two files) | same | a table `value → class` for L1's eight values; Q33 closed |
| **FL3** | *Disassembly — backdrop and camera.* Q44, Q45: the `ScrollMap`/`Parallax`/`Birds` handlers (scroll ratio, order, what draws the sky) and the palette/blend of the backdrop; the camera-follow routine. **Docs only.** | **specialist** | FL2 | same | ratios and rule with VAs, or named `[H]` with the video as the only evidence (D4: the video is a console capture — scene content only) |
| **FL4** | *Disassembly — objects and HUD.* Q46, Q47: the 15 handlers of L1's names via `0x4647B8` — role, idle clip, what each does at contact (only to *classify*; the `Henchlemming`'s behaviour is FL4b's, not this pass's) — and the HUD's sprite sources, positions, initial values and the `Moneybag` coin value. **Docs only.** | **specialist** | FL3 | same | the `name → role → idle clip → grade` table for 15 names; the four HUD elements specified |
| **FL4b** | *Disassembly — the `Henchlemming` handler* (D2, Q50). Read `0x42DD70` (index 84, `0x4647B8[84]`) and what it calls, the way FL4 reads handlers: **states** and their transitions (when `STAY` and `JUMP` play); **movement** (speed, direction, what starts and stops a `JUMP`, the arc if it hops); **turning**; **collision with the level** (which probe, which box, which FL2 classes stop it); **ledge and wall reaction**; **wake rule** (does it act only near the camera or the hero?); **contact with the hero** — what it does to the hero (damage or life loss: the decrement site of `0x52C56C`, Q42; knockback; invulnerability window; hurt/death clip); **whether it can be killed** and by what (stomp, attack, other); randomness (does it draw from a shared random source?). Also which routines it shares with the other enemy handlers, and so which are inseparable. Output: `file-formats.md` §2.11, Q50 closed or narrowed, **every claim with a VA and a grade `[V]`/`[M]`/`[H]`**, and a builder-sized list for FL14/FL15 with its `[H]` fallbacks. **Docs only.** | **specialist** (reason 1: behaviour that exists only in machine code) | FL4 (same two files) | same | the AC16 table; every number re-run with its command |
| **FL4c** | *Disassembly — the hero's attacks* (D7, Q58). `SPIN`: input, states and transitions, clip, duration, hit box, what it hits, cooldown. The helmet throw: input, the projectile entity (its handler, speed, arc, range, return, hit box), what it kills or opens, the helmet flag `0x52C570` / spare `0x59F1E4`, the weapon selection `0x52C58C` and counts, the HUD icon and count. `TUMB` (`0x4107A3`): input, hit box, **cheap or not**. What a hit does: a `Henchlemming` (the defeat `0x42CD00`: effect, freed-lemming count, the coin on an odd x, score), a `Moneybag` (`0x413E40`; 3 coins per burst, Q56 bursts per bag), `Pots` (`0x414130`; contents). **How it meets the helmet-less L1 start**: do the counters 0 at reset (§2.12.c) mean the hero starts without the helmet, which placement or `Pots` content in L1 gives a `HELM`, and does the helmet throw need the helmet or a weapon count. Output: `file-formats.md` (a new subsection after FL4b's), Q58 closed or narrowed, **every claim with a VA and a grade, every number re-run**, and a builder-sized list for FL15b–FL15e with `[H]` fallbacks. **Docs only.** | **specialist** (reason 1: behaviour that exists only in machine code) | FL4b (PR #80; same two files, so the card's start-up check is "PR #N not merged yet") | `docs/file-formats.md`, `docs/research/05-open-questions.md` | the AC20 table; every number re-run with its command |
| **FL5** | *The section-table reader (D3).* `exe_tables.py` (new): the PE32 reader, VA → file-offset mapping from the headers, the two tables parsed from the user's `LOMAX.EXE`, the structural validation and `ExeLayoutError` (§1.5). `engine/sections.py` (new): the resolver `section, sublevel → (world file, playfield, backdrop planes)` and the reverse lookup `(world, plane) → (section, sublevel)`, both taking a parsed table — **no table in the repository, no hash**. `tests/fixtures/pe.py`: the synthetic PE-like builder. | **builder** | — (parallel with FL1–FL4b: code versus docs, disjoint files) | `exe_tables.py`, `engine/sections.py`, `tests/fixtures/pe.py`, `tests/unit/` | AC19 at unit level: one synthetic-fixture test per failed check of §1.5; no test opens a real executable |
| **FL5b** | *The section concept in the CLI.* `slice`/`play` gain `--section N --sublevel M`; the CLI reads `<install>/LOMAX.EXE` through FL5's reader (read-only), resolves the level, prints the `level:` line and cross-checks the planes against the world file; `Level` loads and carries the backdrop planes and their `ScrollMap`/`Parallax` placements (decoded, not yet drawn); `VILLAGE`/`ED` stay selectable by `--world` and are reported as sections 2 / 18 when the executable is readable, and load without it. | **builder** | FL5 | `engine/level.py`, `cli.py`, `tests/unit/` | AC1, AC15, AC19; `slice … --section 0 --sublevel 0` prints the AC1 lines |
| **FL6** | *Object roles.* The `name → role` table for L1's 15 names (extending `anim_nmy.PLACEMENT_ROLES`, grade per row from FL4; `Henchlemming` → `enemy`); `slice` prints the AC5 block. No drawing yet. | **builder** | FL5b, FL4 | `anim_nmy.py`, `engine/level.py`, `cli.py`, tests | AC5: `objects: 52 placements, 15 names, 0 unresolved` |
| **FL7** | *Collision semantics.* `CollisionModel` implements FL2's classes for the eight values (and keeps unknown values on the conservative solid rule, printed); the axis resolution in `state.py` uses them; tile-flip pairing follows Q33's answer. | **builder** | FL6, FL2 | `engine/level.py`, `engine/state.py`, `engine/render.py` (flips only), tests | AC2, AC3; the `collision:` block; synthetic-`MAP` tests per class |
| **FL8** | *Physics fidelity and start state.* The jump gravity gate (5/10 ticks), the hold-to-rise counter (`file-formats.md` §2.9), the start state and origin from FL1 (resolves the engine's `JUMP_STRAIGHT_AT_LEVEL_START`, Q40a, if FL1 answers it). | **builder** | FL7, FL1 | `engine/state.py`, `engine/entities.py`, tests | AC7; unit tests assert the measured gating; the 120-tick `clips:` line is re-measured and plan 46's AC1/AC2 lines updated if they move |
| **FL9** | *Backdrop rendering.* Draw planes 11–13 behind plane 0 with FL3's ratios, order, sky source and palette/blend. Measures AC13 at this point. | **builder** | FL7 (level.py order), FL3 — **parallel with FL8** (render/level vs state/entities) | `engine/render.py`, `engine/level.py`, tests | AC4, AC13; frame at spawn vs the screenshot's scene content by the maintainer's eye |
| **FL10** | *Placed-object sprites.* Draw each of the 52 placements with its idle clip from FL4's table through the existing clip machinery; `hidden by design` list; static (the `Henchlemming`s too, until FL14 moves them). | **builder** | FL9, FL6 | `engine/render.py`, `engine/level.py`, tests | AC6, AC13: `sprites: N/52 drawn, M hidden by design, 0 missing` |
| **FL11** | *Rules.* Lives (3), the pit/fail rule and respawn (FL1), `Revive` checkpoints, `Moneybag` value, `Exit` region and level-complete, game-over state. | **builder** | FL8, FL10, FL1, FL4 | `engine/state.py`, `engine/entities.py`, `cli.py`, tests | AC8 (trigger), AC9 |
| **FL12** | *Camera.* The follow rule from FL3 (or a rule graded `[H]` — D4: not copied from the console video), clamps, backdrop scroll against it. | **builder** | FL11, FL3 | `engine/render.py`, tests | AC10 |
| **FL13** | *HUD.* Four elements from the original's sprites; layout from FL4 where the code says, `[H]` otherwise (D4: the reference layout is a console one and may be wrong for PC); lives and coins live. **The weapon icon and count (AC11b) are not in this slice** — FL4c has not read them yet; they are FL15e. | **builder** | FL12, FL4 | `engine/render.py`, `cli.py`, tests | AC11, AC13 |
| **FL14** | *`Henchlemming` movement (D2).* An enemy entity in `entities.py`, its per-tick update in `state.py`, its clip drawn by state in `render.py` — implementing **exactly what FL4b establishes**: states, speed, direction, turning, collision with FL7's classes, ledge and wall reaction, wake rule. Where FL4b leaves a rule `[H]` the code takes the **static fallback**: the enemy stays at its placement in its `STAY` clip, labelled `[H]` in the code, in the `slice` output (`static fallback [H]`) and in the docs. Enemy state and any random-number state are part of `Snapshot` (the open item recorded in the CHANGELOG — the idle rules' random source is not in a `Snapshot` — is not widened). Behaviour constants are named constants citing the VA that carries each (D5). Measures AC13 with 8 moving enemies. | **builder** | FL13, FL4b | `engine/entities.py`, `engine/state.py`, `engine/render.py`, `cli.py`, tests | AC17, AC13; a synthetic-level unit test per rule FL4b records |
| **FL15** | *`Henchlemming` contact and death (D2).* The hero–enemy contact test and the effect FL4b establishes — damage, a life (through FL11's lives), knockback, invulnerability window, the hero's hurt/death clip for it (D6) — and the enemy's death if a movement-only kill (stomp) exists — FL4b found none, so **this slice has no kill**: the kill by hero attack is FL15d (D7). Static fallback `[H]` where FL4b establishes no rule: contact does nothing and `slice` prints that (the enemy's death is FL15d's). | **builder** | FL14, FL11 | `engine/state.py`, `engine/entities.py`, `engine/render.py`, `cli.py`, tests | AC18, AC9 (contact part), AC13 |
| **FL15b** | *Hero attack — `SPIN` (D7).* The spin state in `state.py` from FL4c's input, states, duration and cooldown; the `SPIN` clip in the hero's clip selection (it leaves plan 46's deferred list); the hit box as a per-tick query (`attack_hits(snapshot) -> boxes`) that FL15d consumes — **no target is touched in this slice**; the attack state and cooldown are part of `Snapshot`. `slice` prints `attack at tick N: spin`. Constants are named, citing the VA (D5); `[H]` where FL4c leaves one open. | **builder** | FL15, FL4c | `engine/state.py`, `engine/entities.py`, `engine/render.py`, `cli.py`, tests | AC21 (spin part), AC13; a synthetic-level unit test per rule FL4c records |
| **FL15c** | *Hero attack — the helmet throw (D7).* The helmet and weapon counters (`0x52C570`, `0x59F1E4`, the selection and six counts: the reset values of §2.12.c), how the hero obtains the helmet in L1 as FL4c says (the `HELM` pickup, or the start state), the throw input, the **projectile entity** in `entities.py` (speed, arc, range, return as FL4c records; the `THR1`–`THR3` clips), its hit box as a query like FL15b's, and its removal; projectile state is in `Snapshot`. `slice` prints `attack at tick N: helmet thrown, count a -> b`. **No target is touched in this slice.** If FL4c shows the helmet is a pickup L1 does not contain, the card says so and the throw is exercised on a synthetic level (the maintainer decides what L1's route does about it). | **builder** | FL15b | `engine/entities.py`, `engine/state.py`, `engine/render.py`, `cli.py`, tests | AC21 (helmet part), AC13 |
| **FL15d** | *Attack hits: the defeat and the openings (D7, D8).* Consume FL15b/FL15c's hit boxes against the `Henchlemming` (`0x42DD70`'s "can be hit" flag): the defeat `0x42CD00` — `+0x4` := 0 at `0x42CD18`, never respawns, the freed-lemming count, the coin on an odd x, the effect FL4c records; against the `Moneybag` (`0x413E40`: the `JUMP` clip, the fall, the burst of 3 coins, Q56 as FL4c settles it) and `Pots` (`0x414130`: contents), through FL11's coin counter; `TUMB` too **only if FL4c graded it cheap**. Other enemies are not hit-tested (§2.3). `slice` prints the `kill at …`, `opened: …` and `enemies: … K killed` lines. The slice names the script that kills a `Henchlemming` with a spin and with a helmet and opens a `Moneybag` and a `Pots` (AC22, AC23). | **builder** | FL15c | `engine/state.py`, `engine/entities.py`, `engine/render.py`, `cli.py`, tests | AC22, AC23, AC13; a synthetic-level test per rule |
| **FL15e** | *HUD — weapon icon and count (AC11b).* The weapon icon and its count from FL4c's reading of `0x52C58C` and the six counts (and the helmet flag), drawn with the HUD sprites FL13 uses, at FL4c's position where the code says, `[H]` otherwise (D4); the count follows a throw (FL15c). | **builder** | FL15d | `engine/render.py`, `cli.py`, tests | AC11b, AC13 |
| **FL16** | *Witness solver.* `slice --input FILE` (per-tick key states) and `solve` (a search over the engine's physics, collision, objects, **the hero's attacks (FL15b–FL15e) and the live `Henchlemming`s** from `Start` to `Exit`, opening and collecting both `Moneybag`s); `solve --enemies off` is the named fallback of R9 and a **scripted witness** (the route found without attacks, plus a hand-written attack script from FL15d for the `Moneybag`s, replayed by `slice --input`) is the named fallback of R11; writes outside the repo; no retail-derived file is committed. | **builder** | FL15, FL15e | `engine/solve.py` (new), `cli.py`, tests | AC8, AC12; `solve` prints length ≥ 1,495 ticks or names why none exists |
| **close** | *Synthesis.* On merged `main`, re-derive the merge gate, run **every** AC in §2.1 by execution on the real install, run `solve` and replay its witness (naming any scripted attack segment, R11), record the clip and attach it to the card (**never committed**), file the verdict per AC. | **lead** | all of the above | — | the AC table filled with command output; clip attached |

Order: `FL1 → FL2 → FL3 → FL4 → FL4b → FL4c` (the six docs passes share two files, so
they are serial; FL4c starts when PR #80 is merged), `FL5 → FL5b` in parallel with them (code versus docs), then
`FL6 → FL7 → (FL8 ∥ FL9) → FL10 → FL11 → FL12 → FL13 → FL14 → FL15 → FL15b → FL15c → FL15d → FL15e → FL16 →
close` (FL15b needs FL4c as well as FL15: it is the first builder card that reads it). FL8 and FL9 are the only parallel pair among builder slices: FL8 touches
`state.py`/`entities.py`, FL9 `render.py`/`level.py`.

**Hotspots.** `engine/render.py` is touched by FL7, FL9, FL10, FL12, FL13, FL14,
FL15, FL15b–FL15e; `engine/state.py` by FL7, FL8, FL11, FL14, FL15, FL15b–FL15d;
`engine/entities.py` by FL8, FL11, FL14, FL15, FL15b–FL15d; `engine/level.py` by FL5b, FL6, FL7, FL9, FL10; `cli.py`
by FL5b, FL6, FL11, FL13, FL14, FL15, FL15b–FL15e, FL16. D2 added FL14 and FL15 to the three
files that were already the busiest; **D7 added FL15b–FL15e to the same files**
(`state.py` FL15b, FL15c, FL15d; `entities.py` the same three; `render.py` all
four; `cli.py` all four). Counting both revisions, **`state.py` has eight touches
and `render.py` eleven; both are the files to watch**; the four attack slices
are strictly serial and each is split by *what it owns* (spin, projectile,
hits, HUD) so no two share a function; if FL14/FL15 or any attack slice collides
in `state.py`, that slice is split rather than widened, and the worker leaves
the `hotspot:` comment. The new files (`exe_tables.py`, `engine/sections.py`,
`tests/fixtures/pe.py`, `engine/solve.py`) are disjoint. That is why the builder
chain is serial except FL8 ∥ FL9: each slice branches from the main that
contains its predecessor, and an `FL` card does not start until its
predecessor's PR is merged (the start-up check; the `chain-unblock-watch` cron
releases a card blocked on "PR #N not merged"). If a slice's diff collides with
a sibling's or touches a file named in another card's comments, the worker
leaves a `hotspot: <path> — <reason>` comment and repeats it in its completion
metadata.

**Fallbacks that keep the chain moving.** If FL2/FL3/FL4/FL4b cannot resolve a
question after one rework, the dependent builder slice proceeds with the
conservative rule, **labelled `[H]` in the code, the `slice` output and the
docs**, and the question stays open in `05-open-questions.md` with the
narrowing — the AC then closes as *partial* in the synthesis, with the named
cause, never as a pass. For the `Henchlemming` that rule is the static one of
FL14/FL15 (stays put, contact does nothing). For the attacks it is: the `SPIN`
and the helmet throw take FL4c's rules or, where one stays `[H]`, a named
constant with the label; a hit that FL4c cannot read does the defeat/opening
the maintainer asked for (the `Henchlemming` is removed for good, the
`Moneybag` and `Pots` give their coins) with `[H]` effects, and the AC closes as
*partial*, never as a pass. Q57 is answered *yes*, so "cannot be killed" is no
longer an acceptable end state.

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
| **R1** | **L1 is not completable on a faithful engine**: the route needs `Jumppad`/`Rope`/`Pots` behaviour, or a jump the engine does not yet have (G8) | AC8/AC12 cannot close; FL16 is a no-go | A purely geometric reachability pass (jump arcs on the collision grid, no objects, no enemies) run at FL7 — it needs no new engine feature and says early whether objects are on the route. Fallback: the maintainer plays L1 by hand and the closing card says so; the AC is then *partial*, not passed |
| **R2** | **The sky has no tile source** (planes 13 and 16 are empty) and FL3 cannot find what draws it | the backdrop looks wrong in the one place the reference makes obvious | Read the `Parallax` record's `PARA` clip sprites and the plane-13 `Parallax` placement first (a short read in FL3); fallback: the `PARA` sprite or a `[H]` gradient, graded as such |
| **R3** | **Collision classes stay `[H]`** (Q43) | wrong platforms (a one-way ledge solid, a slope a wall) — the first thing a player feels. A moving enemy that obeys the same classes (FL14) inherits the error | FL2 reads two probes; the synthetic-`MAP` tests pin whatever is found; unresolved values are printed and listed on the card |
| **R4** | **The references are from a console version** (answered, D4; Q49) | HUD layout, view width and translucency differ from the PC build; a criterion anchored to the video would drift (AC4's blend, AC10's camera offsets, AC11's layout) | Criteria are anchored to the code and data of the user's PC install (§1.3). Where the code does not say, the layout or rule is `[H]` and the card says the reference may be wrong for PC; AC4, AC10 and AC11 then close as *partial* rather than copy a console layout. The screenshot stays a reference for scene content only |
| **R5** | **Pure-Python rendering and ticking at ≈ 60 fps** with three backdrop layers, 52 sprites, 8 moving enemies and a HUD: today one layer and no sprites ran 59.9 fps | AC13 fails at FL10, FL14 or FL13 | AC13 is measured at FL9, FL10 and FL14, not only at the end; the dirty-region or cached-layer fix is a slice-local change |
| **R6** | **Reading the user's `LOMAX.EXE` at runtime** (D3; replaces the earlier embed-the-table risk) | the file is a different build or language (the layout moves), is unreadable, or the parser is wrong on a build nobody here has read — a parse error would become a wrong level instead of a stop | The structural checks and the cross-check with the world file (§1.5) stop with one clear error and never guess; only the one retail build has been read here, so nothing is claimed about others; `--world` keeps the test worlds independent of the file; tests use synthetic fixtures only, so no fixture can carry the executable; nothing from it is embedded, copied or hashed |
| **R7** | **Serial chain on four hot files** (`state.py` has five touches) | longer elapsed time | Accepted: it is the trade for not re-reviewing; FL8 ∥ FL9 is the only safe overlap |
| **R8** | **Plan-limit stop** | a card parks mid-slice | Exit `75` parks it; resume when the window reopens; no reassignment, no model switch |
| **R9** | **A moving enemy that can kill makes the witness harder** (D2): FL16 searches a state space that now holds 8 enemies, and a route found with them is valid only if the enemy update is deterministic | the search does not finish, or the replay differs from the search | (1) Enemy state and any random-number state are in `Snapshot` (FL14), so one input list always gives one run; the solver searches the full state under a node limit. (2) **Named fallback — a solver that ignores enemies:** `solve --enemies off` finds the route on a copy of the level with the `Henchlemming`s removed, and `slice --input` replays it **with** them on and prints the outcome either way (`result: level complete`, or `life lost at tick N: henchlemming i`). A replay that is hit is reported as *route verified without enemies; with enemies the hero is hit at tick N* and AC12 closes as **partial** with that sentence, never as a pass. (3) The maintainer playing L1 by hand stays R1's last fallback |
| **R10** | **The `Henchlemming` handler shares code with the other enemies** (inseparable base routine) | porting it is in effect porting the enemy framework, against "no AI port beyond the `Henchlemming`" | FL4b names the shared routines first; FL14/FL15 port only the paths the `Henchlemming` takes; if it is inseparable the card says so and the maintainer decides — it is not ported silently. Fallback: the static `[H]` `Henchlemming` of AC6, with AC17/AC18 *partial* |
| **R11** | **The solver now has attacks, moving enemies that can be killed, and projectiles** (D7): the state space grows by the spin state and cooldown, a projectile, the helmet count, 8 enemies each alive or not, 2 `Moneybag`s and 3 `Pots` open or not; a kill changes the future | FL16 does not finish, or its route depends on an attack timing the search cannot model | (1) Attack, projectile, kill and opening state are all in `Snapshot` (FL15b–FL15d), so one input list gives one run. (2) FL16 searches the **route first** (geometry, `Jumppad`s, `Rope`s) with `--enemies off` and treats attacks as **macro-moves** the search may insert (spin in place; throw; their fixed length and cooldown from FL4c) rather than free per-tick choices. (3) **Named fallback — a scripted witness:** the route is the solver's; the attack parts (which `Henchlemming` to clear, the spin at each `Moneybag`, the throw) are a short hand-written input segment per target found by FL15d and spliced in, replayed by `slice --input`, and the card says *route found by search; attack segments scripted*. AC12 then closes as **partial** with that sentence, not as a pass. (4) The maintainer playing L1 by hand stays R1's last fallback |
| **R12** | **Q54's wording is the lead's reading, not the maintainer's** (D8): he answered Q57, not Q54 | AC12's *collects both `Moneybag`s* is wrong if he wanted them dropped, and FL15d's `Moneybag`/`Pots` openings are then scope the maintainer did not ask for | The openings share FL15d's hit test with the kill, so they cost little; if he objects, Q54 reverts to dropping the `Moneybag` clause of AC12, AC23 is struck, and FL15d keeps only the `Henchlemming` defeat. The question is put to him again in the closing report |

**Non-goals.** Audio; enemy and NPC behaviour **other than the `Henchlemming`'s**
(**no AI port beyond the `Henchlemming`**; an attack that hits any other enemy
does nothing); hero attacks **other than `SPIN`, the helmet throw and, if cheap,
`TUMB`** (D7 moved those in), the other weapon types, bosses, climbing,
helicopter, swimming, doors; contact effects and hurt/death animations other than those the
`Henchlemming`'s contact needs; every other sub-level and section; the title,
map, password and level-complete screens; a gamepad, rebinding and widescreen
(still deferred as in [`45`](45-playable-level-plan.md)); pixel-identical output;
**embedding any table, row or string of `LOMAX.EXE` in the repository**.

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
* **Nothing is embedded from the executable** (D3): the section table is parsed
  at runtime from the user's own `LOMAX.EXE`, read-only; tests use synthetic
  PE-like fixtures and no test reads a real executable.
* **No code from unlicensed projects** (`Lomax+` has no licence: facts, not code).
* **No CD-check bypass.** No upstream PRs. No push to `main`; every commit
  signed (`git log -1 --format=%G?` prints `G`).

### 5.1 Decisions — answered, and two follow-ons

The maintainer answered D1–D4 on 2026-11-24; this revision applies them.

| # | Decision | Answer |
|---|---|---|
| **D1** | The unit: **A** (section 0, sub-level 0 = plane 0) or **B** (all three sub-levels of section 0)? | **A.** Section 0's other sub-levels stay the next milestone |
| **D2** | **Enemy behaviour** out of scope, or is at least `Henchlemming` (8 in L1) in? | **The Henchlemmings must move** — in scope: FL4b (disassembly), FL14 (movement), FL15 (contact, death). Everything else (the other names' behaviour, boss logic) stays out unless inseparable (R10); **hero attacks moved in under D7**. No AI port beyond the `Henchlemming` |
| **D3** | May the engine carry the 24-entry section table as constants? | **No — read it at runtime from the user's own `LOMAX.EXE`**; nothing from the executable is embedded (§1.5, FL5/FL5b, R6). Replaces the earlier recommendation |
| **D4** | Q49: are the screenshot and the video PC or console captures? | **Console.** Criteria stay anchored to code and data and to the user's PC install; the screenshot is a scene-content reference only (§1.3, R4) |
| **D7** | (answered 2026-11-25, Q57) Must the `Henchlemming`s be killable, and by what? | **Yes** — "they should be killable. I see other options to kill them, spin attack or helmet attack for example." **Hero attacks are in scope**: `SPIN` and the helmet throw; `TUMB` if FL4c finds it cheap. Reverses the old §2.3 non-goal. Slices FL4c, FL15b–FL15e |
| **D8** | (**lead's reading, not confirmed**) Q54: do the `Moneybag`s and `Pots`, which open only on an attack hit, stay in AC12? | **Yes, read from D7** (bring attacks into scope, option 2). The maintainer has **not** confirmed this wording; if he objects, Q54 reverts to dropping the `Moneybag` clause (R12) |

Asked now, both follow from D2/D3:

| # | Decision | Recommendation |
|---|---|---|
| **D5** | The `Henchlemming`'s behaviour constants (speed, hop arc, contact amounts) are *logic*, not a table. May FL14/FL15 write them as **named constants citing the VA** that carries each, like the four physics constants already in `entities.py`, and `[H]` where unread — or must they too be read from the executable at runtime? | Named constants with VAs: D3 is about the section table and strings, a few measured numbers with a citation are the repository's existing convention, and a runtime reader for code immediates would be a per-constant disassembler |
| **D6** | If contact hurts the hero, the hero's hurt/death clip (`OUCH`, `OHNO`, `TUMB`) is needed to show it. In scope **only** for the effect FL4b establishes for the `Henchlemming`'s contact, every other cause staying out? | Yes |

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
| The 24-entry section table, sub-level → active planes, world names (§1.2) | `python3 leveltab.py "$EXE"` (A; it hard-codes the three section ranges, script K reads them from the headers and agrees) |
| Plane sizes of `MEDIEVAL` (plane 0 198 × 40 = 3,168 × 640 px; planes 11–13) | `python3 planes_info.py "$INSTALL" MEDIEVAL` (B) |
| Plane 0: 52 placements, 15 names, table index of each, 0 unmatched (§1.4, G5) | `python3 plane0_roles.py "$INSTALL" MEDIEVAL 0` (C) |
| `Start`/`Exit`/`Finish`/`Revive`/`Moneybag` per plane (planes 0–2 each have a `Start`; `Exit` in 0, 1; `Finish` in 2) | `python3 roles.py "$INSTALL" MEDIEVAL` (D) |
| Planes 13 and 16 have 0 cells with a visible pixel; planes 11 and 12 have 323 and 212 (§1.3) | `python3 opaque_census.py "$INSTALL" MEDIEVAL 0 11 12 13 14 15 16` (E) |
| `ScrollMap` second parameter 50 on plane 11 and 25 on plane 12 (Q44) | `python3 parallax_entries.py "$INSTALL" MEDIEVAL 0 11 12 13` (F) |
| Spawn (89, 407), first solid row 30 (y = 480 in the engine; 496 under the original's rule, `file-formats.md` §2.9.d), bottom map row 0 non-zero, sky pixel (G2, G6, G7) | `python3 spawn_probe.py "$INSTALL"` (G) |
| 22 held-right + periodic-jump runs: max x 3,156, final y 625–626, 0 complete, first tick on the bottom border 382 (*p* = 15) … 879 (*p* = 105), 397 for *p* = 30 (G7, AC9) | `python3 reach.py "$INSTALL" MEDIEVAL 0` (H) |
| Plane-0 collision histogram, spawn, 2 `Moneybag`s, `Exit (3079, 444)`, `GNMY markers: 52 placements … start 1, exit 1, moneybag 2, other 48`, `clips: WALK 34, JMP2 62, FLO2 24` (G4, G5, G11) | `python3 -m lomax_modern slice "$INSTALL" --world MEDIEVAL --frames 120 --out /tmp/med` |
| `play`: 120 frames in 2.00 s, mean 59.9 fps; the one-line HUD (G10) | `SDL_VIDEODRIVER=dummy python3 -m lomax_modern play "$INSTALL" --world MEDIEVAL --seconds 2` |
| PE section mapping from the headers (6 sections, equals script A's three ranges), ten name pointers → `*.WLD` strings, 24 entries with 0 failing the structural checks (largest mask 13 planes, largest sub-level count 5), reverse lookups `(MEDIEVAL, 0)` → section 0, `(VILLAGE, 0)` → 2, `(ED, 0)` → 18 (§1.5, AC19) | `python3 -I pe_sections.py "$EXE"` (K) |
| `Henchlemming`: table index 84, handler VA `0x42DD70`, 8 placements and their coordinates, flags `0x0`/`0x2000`, no parameters, per-plane counts 8/12/10/4/7/8, clips `STAY` 5 and `JUMP` 6 (§1.4, G13) | `PYTHONPATH=<repo>/src python3 henchlemming.py "$INSTALL"` (M) |
| Closest approach of the 22 held-right + jump runs to each `Henchlemming` placement: 15 and 23 px for the first and third, 166–349 px for the other six (§1.4, AC18) | `PYTHONPATH=<repo>/src python3 near_enemy.py "$INSTALL"` (L) |
| No enemy code in the engine (G13) | `grep -in -e enem -e hurt -e damage src/lomax_modern/engine/*.py` prints nothing; likewise `grep -in -e spin -e throw -e helmet -e projectile src/lomax_modern/engine/*.py` (G14) |
| 306 ticks, 5.1 s to x = 701 (AC17) | arithmetic: `701 − 89`, `/ 2.0`, `/ 60` |
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

```python
# file: pe_sections.py  (K) — PE section mapping and structural sanity of the two tables
import struct, sys
d = open(sys.argv[1], "rb").read()
pe = struct.unpack_from("<I", d, 0x3C)[0]
assert d[pe:pe + 4] == b"PE\0\0"
nsec = struct.unpack_from("<H", d, pe + 6)[0]
optsz = struct.unpack_from("<H", d, pe + 20)[0]
base = struct.unpack_from("<I", d, pe + 24 + 28)[0]
print("magic", hex(struct.unpack_from("<H", d, pe + 24)[0]), "image base", hex(base), "sections", nsec)
secs = []
for i in range(nsec):
    o = pe + 24 + optsz + 40 * i
    name = d[o:o + 8].rstrip(b"\0").decode("latin-1")
    vsize, rva, rsize, raw = struct.unpack_from("<IIII", d, o + 8)
    secs.append((name, base + rva, vsize, raw, rsize))
    print(f"  {name:8s} VA {base + rva:#x} vsize {vsize:#x} raw {raw:#x} rawsize {rsize:#x}")

def off(va, n=1):
    for _, v, vs, r, rs in secs:
        if v <= va and va + n <= v + min(vs, rs):
            return r + va - v
    return None

def cstr(va):
    o = off(va, 1)
    e = d.index(b"\0", o)
    return d[o:e].decode("latin-1")

o = off(0x466690, 40)
ptrs = struct.unpack_from("<10I", d, o)
names = [cstr(p) for p in ptrs]
print("names:", names)
bad = 0
for i in range(24):
    o = off(0x466450 + 24 * i, 24)
    M, A = struct.unpack_from("<II", d, o)
    w = d[o + 10]
    cnt = struct.unpack_from("<H", d, o + 12)[0]
    sel = struct.unpack_from("<5H", d, o + 14)
    ranked = bin(M).count("1")
    ok = w < 10 and 1 <= cnt <= 5 and M != 0 and all(s != 0 and s < (1 << ranked) for s in sel[:cnt])
    bad += not ok
print("entries", 24, "failing the structural checks", bad,
      "| max popcount(M)", max(bin(struct.unpack_from('<I', d, off(0x466450 + 24 * i, 4))[0]).count('1') for i in range(24)),
      "| max sub-levels", max(struct.unpack_from('<H', d, off(0x466450 + 24 * i + 12, 2))[0] for i in range(24)))

# reverse lookup: first (section, sub-level) whose lowest active plane is the requested playfield
rows = []
for i in range(24):
    o = off(0x466450 + 24 * i, 24)
    M = struct.unpack_from("<I", d, o)[0]
    w = d[o + 10]
    cnt = struct.unpack_from("<H", d, o + 12)[0]
    sel = struct.unpack_from("<5H", d, o + 14)
    ranked = [p for p in range(32) if M >> p & 1]
    for k in range(cnt):
        act = [ranked[r] for r in range(len(ranked)) if sel[k] >> r & 1]
        rows.append((i, k, names[w][:-4], act))
for world, plane in (("MEDIEVAL", 0), ("VILLAGE", 0), ("ED", 0)):
    hit = next(r for r in rows if r[2] == world and min(r[3]) == plane)
    print(f"reverse ({world}, plane {plane}) -> section {hit[0]} sub-level {hit[1]} active planes {hit[3]}")
```

```python
# file: henchlemming.py  (M) — the Henchlemming's table index, handler VA, clips and placements
import struct, sys
from collections import Counter
from pathlib import Path
from lomax_modern import wld
from lomax_modern.anim_nmy import decode_nmy, anim_tag_name
from lomax_modern.engine import level as L
install = Path(sys.argv[1])
exe = (install / "LOMAX.EXE").read_bytes()
secs = [(0x401000, 0x400, 0x57e00), (0x459000, 0x58200, 0x7800), (0x461000, 0x5fa00, 0x8a00)]
def off(va):
    for v, r, s in secs:
        if v <= va < v + s:
            return r + va - v
tab, hand = off(0x464650), off(0x4647B8)
names = [exe[tab + 4 * i: tab + 4 * i + 4] for i in range(89)]
for i, n in enumerate(names):
    if n in (b"Henc", b"cneH"):
        print("Henchlemming: table index", i, "handler VA", hex(struct.unpack_from("<I", exe, hand + 4 * i)[0]))
w = wld.parse_file(install / "WORLDS" / "MEDIEVAL.WLD")
per = L._decode_gnmy_per_plane(w)
hs = [e for e in per[0] if e.name == "Henchlemming"]
print("plane 0:", len(hs), "placements", sorted((e.x, e.y) for e in hs), "distinct params", {e.params for e in hs}, "distinct flags", {hex(e.flags) for e in hs})
print("per plane:", {i: sum(1 for e in p if e.name == "Henchlemming") for i, p in enumerate(per) if any(e.name == "Henchlemming" for e in p)})
recs, _ = decode_nmy(next(c for c in w.chunks if c.tag == "NMY").payload)
for r in recs:
    if r.name.startswith("Henc"):
        print("clips:", [(anim_tag_name(a.tag), a.frame_count) for a in r.anims])
```

```python
# file: near_enemy.py  (L) — closest approach of the held-right + periodic-jump runs to each Henchlemming placement
import sys
from pathlib import Path
from lomax_modern.engine.level import load_level
from lomax_modern.engine.state import new_game_state
from lomax_modern.engine.entities import Input
from lomax_modern import wld
from lomax_modern.engine import level as L
root = Path(sys.argv[1]) / "WORLDS" / "MEDIEVAL.WLD"
lv = load_level(root, playfield=0)
per = L._decode_gnmy_per_plane(wld.parse_file(root))
hs = sorted((e.x, e.y) for e in per[0] if e.name == "Henchlemming")
best = [10**9] * len(hs)
for period in range(15, 121, 5):
    s = new_game_state(lv)
    for t in range(3600):
        s.tick(Input(right=True, jump=(t % period == 0)))
        cx = s.player.x + s.player.width / 2
        cy = s.player.y + s.player.height / 2
        for i, (hx, hy) in enumerate(hs):
            best[i] = min(best[i], max(abs(cx - hx), abs(cy - hy)))
for i, (h, b) in enumerate(zip(hs, best)):
    print(f"henchlemming {i} at {h}: closest approach over 22 runs {b:.0f} px (Chebyshev, box centre to placement point)")
```
