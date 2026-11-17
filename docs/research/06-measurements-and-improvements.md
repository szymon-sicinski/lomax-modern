# 6. Measurements and the resulting improvement plan

*Taken 2026-11-16 against a complete retail PC install (110 files, 12 MB,
`LOMAX.EXE` 505,344 bytes). Every number below was produced by a command in
§6.1 during this run; nothing here is inferred from a document. Where a
question needed something this environment cannot do, it is marked `blocked`
with the reason.*

## 6.1 Method

```bash
# environment: Linux container, Python 3.14.10, game folder mounted read-only
python3 -m venv .venv && . .venv/bin/pip install -e ".[dev]"
LOMAX_GAME_DIR="/path/to/Lomax"
lomax-modern doctor   "$LOMAX_GAME_DIR"
lomax-modern measure  "$LOMAX_GAME_DIR" --json /tmp/lomax-report.json
python -m pytest tests -m "not realgame" -q      # 28 passed
python -m pytest tests -m realgame -q
```

The install is the retail build: `LOMAX.EXE` hashes to `04cc4dfd260037ba…`,
which is the value published on VOGONS for the retail executable `[S4]`. The
full digest is deliberately not recorded in this repository.

`doctor` output (sizes only):

| Path | Files | Bytes |
|---|---|---|
| `WORLDS/` | 9 | 7,107,048 |
| `SFX/` | 67 | 1,391,846 |
| `AMBIENT/` | 12 | 2,480,444 |
| `JINGLES/` | 3 | 503,068 |
| `DEMOS/` | 14 | 65,536 |
| `GAME.TXT` | 1 | 19,532 |
| `LOMAX.EXE` | 1 | 505,344 |

## 6.2 Format facts now verified

| Claim | Measurement | Verdict |
|---|---|---|
| Chunk header is `tag[4]` + big-endian `u32` payload size | All 9 world files parse as a chain that reaches EOF (`confidence=confirmed-chain`, `layout=tag+size u32be (payload)`) | **verified** |
| Short tags are space-padded | `NMY ` at offset 16 and `END ` at 1,310,476 of `MEDIEVAL.WLD`; `WRLD` is unpadded | **verified** |
| `WRLD` payload is `"PS-X"` + 1234 | First chunk payload: `PS-X` then `d2 04 00 00` (1234 little-endian) | **verified** |
| Chunk order | `WRLD, NMY, PARA, (HEAD, TTAB, MAP, GNMY)*, …, MACR, PAGE, CELL, ANIM*, END` in all 9 files | **verified** |
| 104 planes | `HEAD`, `TTAB`, `MAP` and `GNMY` each appear exactly 104 times across the 9 files | **verified** |
| `HEAD` = two big-endian `u32` in 8-px units (width, height) | 104/104 planes agree with their sibling `MAP` size (§6.3) | **verified** |
| `MAP` = 3 bytes per 16×16 cell | `size − 3·cells` ∈ {0,1,2,3} for all 104 sections; every `MAP` size is a multiple of 4 | **verified** |
| `HEAD` payload is 5,240 bytes (0x1478) | Every `HEAD` chunk: 5,240 B. The documented ANIM bitmap at +0x1458 plus 32 bytes lands exactly on 0x1478 | **verified** |
| `CELL` = whole 8×8 cells | 14,974 cells × 64 B across 9 `CELL` chunks; every payload is a multiple of 64 | **verified** |
| `GNMY` entry = `u16` size (LE) + `u16` type (LE) | Walks cleanly to a 4-byte trailing remainder in every one of the 104 chunks; 3,593 entries total | **verified structure, unverified meaning** |
| `SFX`/`AMBIENT`/`JINGLES` are plain 22.05 kHz mono 16-bit PCM | 82/82 files are RIFF/WAVE with a 44-byte header and exactly that format | **verified** |
| `DEMOS/*.DAT` are fixed-size input recordings | 14 files: 8 × 2,048 B and 6 × 8,192 B; no ASCII framing | **verified sizes only** |
| `GAME.TXT` is single-byte, marker-delimited | 19,532 B, 1,321 lines, 0 non-ASCII bytes, longest line 53; markers `#` 420, `@` 4, `&` 1 | **verified shape only** |
| The PC build imports DirectInput | `LOMAX.EXE` import strings: `DDRAW.dll`, `DINPUT.dll`, `DSOUND.dll`, `WINMM.dll`, `COMCTL32.dll` | **verified** |

**Corrections (2026-11-17).** Two rows above were re-measured during LMX-7 and are
superseded, without rewriting what this run observed: the `GNMY` trailing
remainder is 4 B in 63 chunks and **2 B in the other 41** (not 4 B in all 104),
and `TTAB` is now framed as 8-byte records of four big-endian `u16`
(`07-wp3-asset-pipeline.md` G1, independently reproduced by WP-5, card
`t_50f8aa85`), so the "`TTAB` semantics unverified" reason behind Q8 above is
narrower: no palette field exists in the tile word at all. The current grades
are in [`../file-formats.md`](../file-formats.md) §2.4–2.5.

### 6.3 The cross-check that pins the HEAD layout

Decoding `HEAD` as big-endian width/height in 8-px units is not taken on faith:
the decoded cell count must match the sibling `MAP` chunk, which is 3 bytes per
cell rounded up to 4:

```
cells    = (width_px / 16) * (height_px / 16)
expected = cells * 3
verified = expected <= map_size <= expected + 3  and  map_size % 4 == 0
```

**104/104 planes pass**, and the little-endian reading fails for every one of
them (its cell count is astronomically larger than any `MAP`). That is also why
the earlier heuristic in `measure.py` — "width ≤ 4096, height ∈ {240, 480}" —
was wrong and has been removed: real planes go up to 7,200 × 2,928, and 69 of
the 104 would have been discarded by it.

## 6.4 Q1–Q14

| # | Question | Status | Method / command | Numbers observed | Decision it unlocks |
|---|---|---|---|---|---|
| Q1 | Exact `.WLD` chunk layout | **answered** | `lomax-modern measure`, plus the `MAP` cross-check | tag[4] space-padded + `u32` **BE** payload size; payload-only sizes; 9/9 files reach EOF; order includes `PARA`, `MACR`, `PAGE` | Unblocks a real reader/writer (LMX-5) |
| Q2 | Why the widescreen cap is 512 px | **blocked** | Not observable without running the patched engine | Data shows nothing at 512: plane widths are multiples of 8 and reach 7,200, so the cap is engine-side, not data-side | Keep 512 as prior-art territory; do not chase ultra-widescreen |
| Q3 | Map-width distribution | **partial** | Width histogram over verified planes | 104 planes; < 432 px: **16**; < 512: **18**; < 640: **24**; < 800: **30**. Heights: 240 (×5), 256 (×10), then 272…2,928 | 16:9 at 432 needs bars on 16/104 planes — **the same 16 the prior art reports**, see §6.5 |
| Q4 | DirectInput in the PC build | **answered** | Import strings of `LOMAX.EXE` | `DINPUT.dll` present | Input work is a mapping/UX problem, not a missing API |
| Q5 | Vertical camera | **partial** | Plane heights vs the 240/256 playfields | Playfields are 240 or 256 tall; backgrounds are far taller, so height is a per-plane property and scrolling is horizontal in the levels observed | A taller framebuffer stays a dead end |
| Q6 | `DEMOS/*.DAT` layout | **partial** | `measure` → `DEMOS` probe | 14 files, 2,048 B × 8 and 8,192 B × 6, no ASCII header | Enough to regression-check replay; the record layout is still unknown |
| Q7 | Audio formats | **answered** | RIFF parser over `SFX`/`AMBIENT`/`JINGLES` | 82 files, all mono 22,050 Hz 16-bit, 44-byte header; 31.4 s + 56.2 s + 11.4 s | Replacing/adding audio is a trivial WAV job; no custom mixer needed |
| Q8 | Do all tiles use palette 0 | **blocked** | Needs tile decoding (TTAB semantics unverified) | `HEAD` carries 10×512 B palettes; which palette a tile uses is not derivable from the container alone | Bounds how hard a 2x tile pack is |
| Q9 | Unique cells/tiles/sprites | **partial** | `CELL` totals; chunk counts | 14,974 cells total (uniqueness unknown); 104 `TTAB`; 566 `ANIM` chunks | Sizes the art job roughly; exact dedupe needs decoding |
| Q10 | Does the stock game run under Wine | **blocked** | No display, no Wine in this environment | — | Target for an open-source presenter |
| Q11 | 16-bit surface presentation outside the game's mode set | **blocked** | Same as Q10 | — | Same |
| Q12 | Will `Lomax+` ever be licensed / collaborate | **blocked** | Needs the author's answer | — | Could remove the licence obstacle entirely |
| Q13 | Is `HEAD` height ever ≠ 240 | **answered** | Height histogram | 240 (×5), **256 (×10)**, 272–2,928 (×89) | Confirms the PS1 PAL 256-line leftovers exist in PC data; a fixed 240 view is a design choice, not a data limit |
| Q14 | Full SHA-256 of the retail EXE | **answered** | `lomax-modern doctor` | Prefix `04cc4dfd260037ba…`, matching the VOGONS-published retail hash `[S4]` | Baseline pin; full value stays out of the repo |

## 6.5 What the width data actually says about widescreen

`docs/research/02-resolution.md` argued the 512 px ceiling from the prior art's
documentation. The data now gives the missing half — the level side:

- 104 planes, median width **1,280 px**; the narrowest is 320 px.
- **16 of 104 planes are narrower than 432 px (27 tiles)** — which is exactly
  the figure the prior art quotes for "maps narrower than 27 tiles" `[S3]`.
  Two independent measurements agreeing is strong evidence that their "104
  maps" are these 104 planes, and that our parser is right.
- Going wider costs little on the data side: 512 px would bar 18 planes, 640 px
  would bar 24, 800 px would bar 30. In other words **77 % of planes would fill
  a 40-tile view**.

**But** a plane is not necessarily the plane the camera scrolls: a level's
parallax layers are planes too, and several of the 7,200-px ones are clearly
backgrounds. Which plane a section uses as its playfield is chosen by the level
table inside `LOMAX.EXE` (`g_LevelDefs`), not by the world file. So the honest
reading is:

> The data does **not** justify "512 is all the maps can fill". It does justify
> "16 of 104 planes cannot fill 432". The binding constraint for any width
> beyond 512 is the engine (the fade system and the 199 patched width sites),
> not the level data.

That shifts the decision: ultra-widescreen is blocked by code, not by content,
so it stays out of scope for a data-layer project — and the "true HD" path
(pixel density) remains the only resolution improvement with headroom.

## 6.6 Top 5 improvements

Ranked for a maintainer deciding where to spend a month. Each lists the
user-visible benefit, effort, risk, licence posture, the observation that would
falsify it, and the first executable step.

### 1. Open-source presentation layer with pixel-art filters (LMX-4)
- **Benefit:** the game becomes playable borderless on any modern screen, with
  integer scaling plus xBRZ/MMPX/CRT options, on Windows **and** Linux/Proton —
  none of which exists today (the only loader is Windows-only and unlicensed).
- **Effort:** M–L. **Risk:** medium (a `ddraw.dll` shim is fragile; an
  app-level presenter is safer but needs the game's frame).
- **Licence:** ship the code, not the game. No prior-art code.
- **Falsified if:** Wine's own DirectDraw already presents 16-bit surfaces well
  enough that only a filter pass is needed (which would shrink the job).
- **First step:** LMX-3 — run the stock game under Wine/DXVK and record which of
  the four blockers (colour depth, missing 320×240 mode, CD check, MFC startup)
  still fires. One afternoon, no code.

### 2. `WLD` reader/writer with byte-exact round trip (LMX-5)
- **Benefit:** unlocks art replacement, level editing, translation; the only
  asset tooling that exists is inside an unlicensed project.
- **Effort:** M. **Risk:** medium (the remaining unknown is `TTAB`/`ANIM`).
- **Licence:** fully distributable; operates on the user's own files.
- **Falsified if:** the round trip cannot be made byte-exact because of the
  `size & ~3` padding rule interacting with per-chunk padding — discoverable in
  the first day.
- **First step:** parse `TTAB` (16×16 tiles over 8×8 cells, big-endian words)
  and re-emit it unchanged; assert on all 104 sections.

### 3. Matte-aware 2x asset upscaler + pack writer (LMX-8/9)
- **Benefit:** the only route to genuinely higher resolution. Index 0 is the
  transparent key with real white at 0x7FFE, so a naive scaler produces halos;
  index-space scaling keeps the palette intact.
- **Effort:** M for the scaler, M more for the pack writer. **Risk:** medium.
- **Licence:** ship the tool; the output is a derivative of copyrighted art and
  must stay on the user's disk.
- **Falsified if:** 2x upscaled 8×8 cells look worse than the engine's own
  scaling (possible — the art is hand-dithered).
- **First step:** export one world's `CELL` chunk as 64-byte cells → PNG sheets,
  and compare nearest vs EPX/xBR in index space on the same tiles.

### 4. Password tool + deterministic regression harness (LMX-7)
- **Benefit:** the game has no save files; a correct generator/decoder is
  immediately useful, and the demos give a tick-exact regression check for any
  future render work.
- **Effort:** S. **Risk:** low. **Licence:** fully distributable (algorithm is
  documented behaviour, reimplemented from facts).
- **Falsified if:** the checksum turns out to include a hidden counter (visible
  as two passwords for the same state failing).
- **First step:** generate all 8 two-bit gem values for section 0 / 5 lives and
  verify one in the real game.

### 5. Level editor on top of the `WLD` writer (LMX-11)
- **Benefit:** the modding story that the format work makes possible; the map,
  collision bytes and placement format are now measurable.
- **Effort:** L. **Risk:** medium (needs a previewer and validation rules).
- **Licence:** distributable editor; levels it produces are derivatives only if
  they embed original art.
- **Falsified if:** `GNMY` placement records cannot be re-emitted without the
  NMY type table (which is currently unverified).
- **First step:** decode `GNMY` type indices against the NMY name list and check
  that a Start/Exit pair round-trips.

## 6.7 What changed versus the hypothesis-driven plan

- **Plane ≠ playfield.** The earlier plan treated "map width" as one number per
  level. The data has 104 planes, not 24 levels, and the level→plane mapping
  lives in the executable. Q3 is therefore `partial`, and the histogram in
  `04-improvement-backlog.md` is now described as *plane* widths.
- **The 512 px ceiling is not a data limit** (§6.5). That removes ultra-wide
  from the tempting-but-blocked list and confirms pixel density as the real
  frontier.
- **Per-world section counts differ from the card's starting note.** Measured:
  BONUS 6, ED 16, HAUNTED 29, MAIN 1, MAP 1, MEDIEVAL 17, TITLE 5, VILLAGE 15,
  WEST 14 — total 104. The earlier note said ED 17, HAUNTED 33, WEST 15; those
  do not sum with the rest to the documented 104, so the measured counts are
  used.
- **`measure.py`'s first heuristic was wrong** and is gone: plane dimensions are
  unbounded (up to 7,200 × 2,928), so validity now comes from the `MAP`
  cross-check, not from a plausible-looking size range.
- **Three undocumented chunk tags exist** (`PARA`, `MACR`, `PAGE`) in all 9
  files, and `PARA` holds readable type names (`Parallax`, `ScrollMap`, …).

## 6.8 Limits of these measurements

- Playfield attribution needs `g_LevelDefs` from the executable (not the data).
- `TTAB` tile→cell mapping, `ANIM` frame layout and palette-per-tile are still
  unverified; nothing here should be read as a spec for them.
- `GNMY` type indices are measured but their names are not: the NMY type table
  is a list of `u16 size + NUL-terminated name` blocks, yet the index→type
  mapping has not been confirmed.
- Q2, Q8, Q10, Q11, Q12 stay `blocked` for the reasons in §6.4.
