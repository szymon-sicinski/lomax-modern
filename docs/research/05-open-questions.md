# 5. Open questions

Each question states how to resolve it and what decision hangs on it. None of
these can be answered from public documentation alone.

> **Revision v1** (LMX-7/WP-6 synthesis, 2026-11-17). Q2, Q8–Q11 updated with
> the WP-1…WP-5 findings; Q15–Q19 added by WP-4; Q20–Q28 added by this synthesis
> (asset/tooling/password unknowns and the one open product decision). Two
> documented format claims were falsified by measurement and are recorded at
> their questions (Q23, Q24), not silently dropped.
>
> **Revision v2** (LMX-9/M2, 2026-11-18). The M2 target-host decision (Q28) is
> resolved — disc-less, own engine — and Q29/Q30 are added and answered by the
> strategy report ([`../roadmap/15-strategy-report.md`](../roadmap/15-strategy-report.md)):
> input is an unpacked game directory (no ISO, no ripping); music is ambient +
> jingles + SFX (no CD-DA content in the data).
>
> **Revision v3** (LMX-10/M3, 2026-11-18). Q31 added: the `MAP` collision
> byte's per-value semantics are unresolved and the documented `[D]` bit-field
> is retracted (near-uniform byte histogram across all 104 planes,
> [`../file-formats.md`](../file-formats.md) §2.4). The engine core ships only
> the 0-vs-non-zero solidity rule as a labelled hypothesis.
> **Revision v3** (LMX-11, 2026-11-18). Q23 (`NMY`) and Q24 (`ANIM`) are
> resolved by static analysis of the readers in `LOMAX.EXE` and validated with
> `lomax-modern anim-nmy` (ANIM 566/566, NMY 9/9); the framings and
> addresses are in [`../file-formats.md`](../file-formats.md) §2.5/§2.6.

> **Revision v4** (LMX-10/M7 runbook, 2026-11-18). Q17 is marked **out of
> scope**: the project's only input is an unpacked game directory, so nothing
> here mounts a disc image or describes making one
> ([`../roadmap/15-strategy-report.md`](../roadmap/15-strategy-report.md) §8).
> The question stays listed — unanswered, not answered by omission — and the
> image-mounting probe was removed from
> [`07-wp4-runtime-distribution.md`](07-wp4-runtime-distribution.md).

> **Revision v5** (C-blocker 2, 2026-11-18). The `GNMY` entry *layout* is
> recovered from the reader in `LOMAX.EXE` (VA `0x414D16`) and validated on all
> 104 retail chunks (3,593 entries, `size == structural length` on 3,593/3,593,
> `x`/`y` as pixel coordinates) — see [`../file-formats.md`](../file-formats.md)
> §2.5. What a `GNMY` entry *means* (which entry is the player start, the level
> exit, or a collectable) remains open and is recorded as **Q32** below.

| # | Question | Why it matters | How to resolve |
|---|---|---|---|
| Q1 | What is the exact chunk header layout of a `.WLD`? | Every parser depends on it | ✅ **answered** — tag[4] space-padded + `u32` **BE** payload size, payload-only; 9/9 files reach EOF (`06-measurements-and-improvements.md`) |
| Q2 | Why does the widescreen ceiling sit at 512 px? | Decides whether ultra-widescreen is a small patch or a rewrite | ⚠️ **blocked** (exact cause unproven), but **narrowed**: it is renderer-side — the fade/dissolve surface rounded to a multiple of 32, and the 199 hard-coded width sites — *not* a data limit (plane widths reach 7,200 px, 8-px aligned) and *not* a single check. Needs experimentation on a patched engine |
| Q3 | What is the map-width distribution across all 104 planes? | Decides how much of a wider view any level can fill | ⚠️ **partial** — 104 plane widths measured (< 432 px: 16; < 512: 18; < 640: 24); playfield→plane mapping needs `g_LevelDefs` from the EXE |
| Q4 | Does the PC build use DirectInput for joysticks? | Input work may be covered by prior art | ✅ **answered** — `DINPUT.dll` (`DirectInputCreateA`) **and** `WINMM.dll!joyGetPosEx` are both in the import table (WP-1) |
| Q5 | Is there any vertical camera logic? | A taller framebuffer is only viable with vertical scroll | ⚠️ **partial** — playfield planes are 240/256 tall while backgrounds reach 2,928, so height is per-plane; no vertical scrolling observed in data |
| Q6 | What is the `DEMOS/*.DAT` format? | Needed for regression-testing any render change | ⚠️ **partial** — 14 files, fixed sizes 2,048 B (×8) and 8,192 B (×6); record layout unknown |
| Q7 | Are the audio files plain PCM? | Determines whether audio tooling is trivial | ✅ **answered** — 82/82 RIFF/WAVE mono 22,050 Hz 16-bit, 44-byte header |
| Q8 | Do all shipped tiles use palette 0 only? | If true, tile upscaling is much simpler | ⚠️ **blocked, narrowed** — a `TTAB` word has no free bit for a palette (13-bit index + 2 flags + 1 unused), so a per-cell palette must live in `NMY`/`MACR`/`PAGE` or nowhere. Needs those layouts decoded or the EXE's tile-blit read |
| Q9 | How many unique cells, tiles and sprite frames exist? | Sizes the art upscaling job | ⚠️ **partial → cells answered** — 14,974 cells total, 14,862 referenced / 112 unreferenced (V structure); `TTAB` 75,122 records. Tile *identity per map cell* stays unknown (Q20); sprite frames blocked on the `ANIM` layout (Q24) |
| Q10 | Does the stock game run under Wine at all? | Sets the target for an open-source presenter | ⚠️ **blocked** (runtime) with mechanism now **V**: the colour gate is a GDI `GetDeviceCaps(BITSPIXEL×PLANES)` query, so a 16-bpp X server clears it; one archived 2013 Wine 1.7.0 report reached gameplay at depth-16. No Wine/display here to re-verify — see Q15 |
| Q11 | Can a 16-bit offscreen surface be presented outside the game's mode set? | Same target question | ⚠️ mechanism **V**: a `ddraw.dll` proxy owns its own present path, so presenting a 16-bit surface is *yes* and `SetDisplayMode` (a vtable method) can be neutralised; sidestepping the GDI gate alone is *no*. Runtime confirmation still blocked (no Wine) |
| Q12 | Will `Lomax+` ever get a licence? | Cheapest path to licensed widescreen | ⚠️ **blocked** — needs the author's answer |
| Q13 | Is the `HEAD` height field ever != 240/8 = 30? | A taller plane makes a vertical-camera patch conceivable | ✅ **answered** — yes: 240 (×5) and 256 (×10) plus 272–2,928 (×89); 256 is the PS1 PAL leftover |
| Q14 | What is the full SHA-256 of the retail `LOMAX.EXE`? | Pins the baseline locally | ✅ **answered** — prefix `04cc4dfd260037ba…` matches the VOGONS retail hash; the full value stays out of the repo |
| Q15 | Does Wine 11.x still pass B1 (colour gate) with a 16-bpp X server, or has something in 12 years broken it? | The first-run recipe's linchpin | probe P1 (`ddrawprobe` at depth 16 vs 24 on a real host with Wine) |
| Q16 | Do the 2013 glitches (invisible platforms, one-frame sprite zoom) persist on Wine 11, and does dgVoodoo 2 remove them? | Whether the conformance oracle is trustworthy | play test on Wine 11 |
| Q17 | Does a CD-DA-capable device backed by a disc image satisfy both the disc check and `open cdaudio`? | Whether disc owners could avoid a physical disc | ⛔ **out of scope** (2026-11-18) — this project mounts no disc images and gives no instructions for making one; its only input is an unpacked game directory ([`../roadmap/15-strategy-report.md`](../roadmap/15-strategy-report.md) §8). The question stays listed for anyone who pursues it independently |
| Q18 | Does `EmulateModeset=Y` change what B1 sees (the gate runs before any mode set)? | Whether a software-only Wine knob helps at all | probe P2 (same probe with `EmulateModeset=Y` at depth 32) |
| Q19 | Are 16-bpp X screens still usable under Mesa/XWayland on modern GPUs, or is Xvfb+VNC the only reliable depth-16 vehicle? | Whether the depth-16 route survives on current hardware | run Xephyr at depth 16 on the target GPU; fall back to Xvfb |
| Q20 | How does a `MAP` cell name its `TTAB` tile record? | Unblocks "unique tiles per level" and a correct exporter | three disagreeing counts (43,612 distinct map words vs 75,122 records vs 14,862 distinct indices; `byte0 & 0x7F` saturates at 127) — find the map→tile lookup in the EXE. Until then, print `map cell → tile record: unresolved` |
| Q21 | What do the `TTAB` flags `0x2000`/`0x4000` mean? | Correct tile rendering (flip-H/flip-V is the guess, not evidence) | render one flagged tile under each flag, or read the blit routine that consumes the word |
| Q22 | Why does `BONUS.WLD` reference `TTAB` index 256 while its `CELL` chunk holds only 251 records? | Decides whether a writer must reject or preserve out-of-bank indices | find the cell-array allocation (max-index+1 vs 256-rung rounding); do **not** clamp index 256 |
| Q23 | What is the `NMY` table's record framing? | Unblocks the `GNMY` index→name mapping and the editor's placement falsifier | ✅ **answered** — recovered from the EXE reader (VA `0x415199`, file offset `0x14599`): each record is a NUL-terminated name plus a binary tail (`W_A` flags, `W_B` animation count, then `W_B` animations of a 4-byte tag + size field + frame count + 9×u16 params + 8-byte frames). Validated 9/9; record counts 30/44/74/24/17/68/22/49/53 each equal max `GNMY` type index **+ 1** (`anim-nmy`, `file-formats.md` §2.5) |
| Q24 | What is the `ANIM` record layout? | Unblocks 2× sprite scaling and any sprite exporter | ✅ **answered** — recovered from the EXE reader (VA `0x414A82`, file offset `0x13E82`): 12-byte header (`a, b, n, flags, type_index, pad`) then `n` frames of `i16 w, i16 h, u16 d, u16 e, pixel data`; bit 15 of `flags` = packed 4-bit pixels. Validated **566/566** (`anim-nmy`, `file-formats.md` §2.6). The 0x38-byte `SpriteFrame` is the in-memory stride, not the on-disk unit |
| Q25 | What are the password checksum function, field bit order and gem alphabet? | The password tool can decode but not yet generate | read the password routine in the EXE, or verify two generated words in-game (LMX-7's stated falsifier) |
| Q26 | What are the `MACR`/`PAGE` chunk layouts? | A level editor needs them decoded (7 each, 24–968 B / 1,092–40,344 B) | structural probe + the EXE's reader |
| Q27 | Which `TTAB` counting units are authoritative? | The flag counts disagree between WP-3 (`0x2000` 15,787 / `0x4000` 1,783) and WP-5 (16,503 / 2,499), and distinct indices differ by 1 (14,861 vs 14,862) | agree a single unit (per-word vs per-record, `BONUS.WLD` included or not) before these numbers enter `file-formats.md` |
| Q28 | Does M2 serve **disc owners only** (ddraw proxy over the retail exe), or also **disc-less users** (own engine + presenter over the MIT data layer)? | A scope and budget fork, not a mechanism change | ✅ **resolved** — disc-less: own engine + presenter over the MIT data layer (human decision, 2026-11-18); the `ddraw.dll` proxy is demoted to an optional disc-owner appendix ([`../roadmap/15-strategy-report.md`](../roadmap/15-strategy-report.md)) |
| Q29 | What is the input a disc-less user supplies, and is anything the engine references absent from a plain data-only copy? | "Disc-less" still means the user supplies data; the engine must name its inputs and the repo must never contain them | ✅ **answered** — an unpacked game directory in the retail layout (`WORLDS/`, `SFX/`, `AMBIENT/`, `JINGLES/`, `DEMOS/`, `LOMAX.EXE` present but unused); the engine takes a path. **No ISO handling, no ripping instructions** (2026-11-18) |
| Q30 | What is the licence-clean source for the soundtrack once the CD is out of the picture? | The PC build's music is CD-DA only (MCI `cdaudio`), so the own engine has no music | ✅ **answered** — measured: 82 WAVs (67 SFX, 12 ambient loops = 6 worlds × stereo `_L`/`_R`, 3 jingles); no CD-DA/MP3/OGG/MOD in the data. Plan: ambient L/R pair as the per-world bed, jingles on transitions, SFX as-is; no ripping, no bundled audio. An optional user-supplied music folder is a later possibility, not v0.1 (2026-11-18) |
| Q31 | What do the individual `MAP` collision-byte values mean? | The engine's collision (solid vs passable, one-way, hazards) needs per-value semantics, not a flat "non-zero = solid" guess | the documented `[D]` bit-field (`0x80` solid, `0xC0` one-way, `0x08`/`0x10`/`0x20` directional) is **retracted** — the byte is near-uniform over all 256 values (measured 2026-11-18, `file-formats.md` §2.4). Read the collision lookup in the EXE, or correlate each byte value with observed solidity in a playtest. Until then the engine ships 0-vs-non-zero `[H]` and preserves the byte verbatim |
| Q32 | What do a `GNMY` entry's `flags` bits 8–9 and the optional extra word mean — and which entries are the player start, the level exit, and the collectables? | Finishes the M3 `spawn → … → next-level` loop: the engine must know which placement to spawn as the player and which to treat as the exit/collectable | ⚠️ **partial** — the entry *layout* is recovered (VA `0x414D16`, §2.5: `u16 size/type/x/y/flags` + `K` params + optional extra; 3,593/3,593 `size == structural length`, `x`/`y` pixel coords). The *semantics* are not: the reader turns every entry into an identical sprite instance and **0/74 types appear once-per-world**, so spawn/exit/collectable is not a unique `NMY` type. Resolve by static analysis of the game-loop code that consumes the sprite list (find where the player instance and the exit trigger are selected), or by a runtime experiment on a copy — flip a candidate field (flags bits 8–9, or the extra word) and observe, never on the operator's install |

**Opened by the LMX-7 reports (2026-11-17).** `TTAB` is now framed — 8 bytes per
16×16 tile, four big-endian `u16`, 13-bit index plus `0x2000`/`0x4000` flags —
but its *meaning* is not: the order of the four cells in an entry, the
`0x2000`/`0x4000` flag semantics, and the `MAP` tile-word saturation (0
violations at `b[0] & 0x7F`, yet a 7-bit field against `TTAB` banks of up to
2,952 entries) all stay open, as do the `ANIM` layout, palette-per-`CELL` (Q8,
narrowed to "no palette field exists in the tile word") and the `BONUS.WLD`
index-256 anomaly. Each has its test named in
[`07-wp3-asset-pipeline.md`](07-wp3-asset-pipeline.md) §2 and §6; the
runtime-only questions Q15–Q19 are in
[`07-wp4-runtime-distribution.md`](07-wp4-runtime-distribution.md) §10.

## Deliberately unanswered for now

- **Copy protection strength.** Research may describe the CD check `[S3]`; we
  do not need to defeat it to do any of the work above, and we will not ship a
  bypass. Revisit only if a user-owned-disc workflow cannot be supported
  otherwise.
- **PS1 version parity.** The console build has assets the PC build lacks
  (loading screen, language select, `LOGO*.WLD`) `[S2]`, and a third-party mod
  already ports Sega CD *Flink* content `[S6]`. Interesting for preservation,
  irrelevant to the resolution question.
