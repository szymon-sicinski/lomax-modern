# 5. Open questions

Each question states how to resolve it and what decision hangs on it. None of
these can be answered from public documentation alone.

> **Revision v1** (LMX-7/WP-6 synthesis, 2026-11-17). Q2, Q8–Q11 updated with
> the WP-1…WP-5 findings; Q15–Q19 added by WP-4; Q20–Q28 added by this synthesis
> (asset/tooling/password unknowns and the one open product decision). Two
> documented format claims were falsified by measurement and are recorded at
> their questions (Q23, Q24), not silently dropped.

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
| Q17 | Does a CDEmu-backed CD-DA device satisfy both the disc check and `open cdaudio`? | Whether disc owners can use an image instead of the physical disc | probe P3 (`cdemu load 0 your.cue` then `wine LOMAX.EXE`) |
| Q18 | Does `EmulateModeset=Y` change what B1 sees (the gate runs before any mode set)? | Whether a software-only Wine knob helps at all | probe P2 (same probe with `EmulateModeset=Y` at depth 32) |
| Q19 | Are 16-bpp X screens still usable under Mesa/XWayland on modern GPUs, or is Xvfb+VNC the only reliable depth-16 vehicle? | Whether the depth-16 route survives on current hardware | run Xephyr at depth 16 on the target GPU; fall back to Xvfb |
| Q20 | How does a `MAP` cell name its `TTAB` tile record? | Unblocks "unique tiles per level" and a correct exporter | three disagreeing counts (43,612 distinct map words vs 75,122 records vs 14,862 distinct indices; `byte0 & 0x7F` saturates at 127) — find the map→tile lookup in the EXE. Until then, print `map cell → tile record: unresolved` |
| Q21 | What do the `TTAB` flags `0x2000`/`0x4000` mean? | Correct tile rendering (flip-H/flip-V is the guess, not evidence) | render one flagged tile under each flag, or read the blit routine that consumes the word |
| Q22 | Why does `BONUS.WLD` reference `TTAB` index 256 while its `CELL` chunk holds only 251 records? | Decides whether a writer must reject or preserve out-of-bank indices | find the cell-array allocation (max-index+1 vs 256-rung rounding); do **not** clamp index 256 |
| Q23 | What is the `NMY` table's record framing? | Unblocks the `GNMY` index→name mapping and the editor's placement falsifier | the documented "`u16` size + NUL name" walk was **falsified** (0/104 chunks consumed); read the `NMY` walker in the EXE, check "records == max `GNMY` type index + 1" |
| Q24 | What is the `ANIM` record layout? | Unblocks 2× sprite scaling and any sprite exporter | the documented "0x38-byte record array" was **falsified** (0/566 chunks 0x38-aligned); static-analysis the `ANIM` reader in the EXE (the 52 B chunk in `MAIN.WLD` is the smallest fixture) |
| Q25 | What are the password checksum function, field bit order and gem alphabet? | The password tool can decode but not yet generate | read the password routine in the EXE, or verify two generated words in-game (LMX-7's stated falsifier) |
| Q26 | What are the `MACR`/`PAGE` chunk layouts? | A level editor needs them decoded (7 each, 24–968 B / 1,092–40,344 B) | structural probe + the EXE's reader |
| Q27 | Which `TTAB` counting units are authoritative? | The flag counts disagree between WP-3 (`0x2000` 15,787 / `0x4000` 1,783) and WP-5 (16,503 / 2,499), and distinct indices differ by 1 (14,861 vs 14,862) | agree a single unit (per-word vs per-record, `BONUS.WLD` included or not) before these numbers enter `file-formats.md` |
| Q28 | Does M2 serve **disc owners only** (ddraw proxy over the retail exe), or also **disc-less users** (own engine + presenter over the MIT data layer)? | A scope and budget fork, not a mechanism change | human decision — see [`../roadmap/30-risks.md`](../roadmap/30-risks.md#open-decisions-for-the-human) |

## Deliberately unanswered for now

- **Copy protection strength.** Research may describe the CD check `[S3]`; we
  do not need to defeat it to do any of the work above, and we will not ship a
  bypass. Revisit only if a user-owned-disc workflow cannot be supported
  otherwise.
- **PS1 version parity.** The console build has assets the PC build lacks
  (loading screen, language select, `LOGO*.WLD`) `[S2]`, and a third-party mod
  already ports Sega CD *Flink* content `[S6]`. Interesting for preservation,
  irrelevant to the resolution question.
