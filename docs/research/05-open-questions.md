# 5. Open questions

Each question states how to resolve it and what decision hangs on it. None of
these can be answered from public documentation alone.

| # | Question | Why it matters | How to resolve |
|---|---|---|---|
| Q1 | What is the exact chunk header layout of a `.WLD`? | Every parser depends on it | ✅ **answered** — tag[4] space-padded + `u32` **BE** payload size, payload-only; 9/9 files reach EOF (`06-measurements-and-improvements.md`) |
| Q2 | Why does the widescreen ceiling sit at 512 px? | Decides whether ultra-widescreen is a small patch or a rewrite | ⚠️ **blocked** — not visible in the data (plane widths reach 7,200 px, are 8-px aligned); needs experimentation on a patched engine |
| Q3 | What is the map-width distribution across all 104 planes? | Decides how much of a wider view any level can fill | ⚠️ **partial** — 104 plane widths measured (< 432 px: 16; < 512: 18; < 640: 24); playfield→plane mapping needs `g_LevelDefs` from the EXE |
| Q4 | Does the PC build use DirectInput for joysticks? | Input work may be covered by prior art | ✅ **answered** — `DINPUT.dll` is in the import table |
| Q5 | Is there any vertical camera logic? | A taller framebuffer is only viable with vertical scroll | ⚠️ **partial** — playfield planes are 240/256 tall while backgrounds reach 2,928, so height is per-plane; no vertical scrolling observed in data |
| Q6 | What is the `DEMOS/*.DAT` format? | Needed for regression-testing any render change | ⚠️ **partial** — 14 files, fixed sizes 2,048 B (×8) and 8,192 B (×6); record layout unknown |
| Q7 | Are the audio files plain PCM? | Determines whether audio tooling is trivial | ✅ **answered** — 82/82 RIFF/WAVE mono 22,050 Hz 16-bit, 44-byte header |
| Q8 | Do all shipped tiles use palette 0 only? | If true, tile upscaling is much simpler | ⚠️ **blocked, narrowed twice** — no `TTAB` word has a free bit for a palette (13-bit index + 2 flags + 1 unused), and decoding the `CELL` data shows slot 1 renders natural art while slot 0 renders a hue-shifted variant (slot 1 non-empty in 101/104 `HEAD` blocks). So "palette 0 only" is not what the data shows, but which slot the engine loads is still unproven — see Q29 |
| Q9 | How many unique cells, tiles and sprite frames exist? | Sizes the art upscaling job | ⚠️ **partial → cells/tiles counted** — 14,974 cells, of which **14,861 referenced / 113 unreferenced** by `TTAB` (measured here; this is the WP-3 figure, and it settles the 14,861-vs-14,862 disagreement in the roadmap's Q27 count in favour of 14,861), 75,122 `TTAB` records (300,488 index words), 523,229 map cells. Tile *identity per map cell* stays unknown (Q20); sprite frames blocked on the `ANIM` layout (Q24) |
| Q10 | Does the stock game run under Wine at all? | Sets the target for an open-source presenter | ⚠️ **blocked** — no display/Wine in the measurement environment |
| Q11 | Can a 16-bit offscreen surface be presented outside the game's mode set? | Same target question | ⚠️ **blocked** — as Q10 |
| Q12 | Will `Lomax+` ever get a licence? | Cheapest path to licensed widescreen | ⚠️ **blocked** — needs the author's answer |
| Q13 | Is the `HEAD` height field ever != 240/8 = 30? | A taller plane makes a vertical-camera patch conceivable | ✅ **answered** — yes: 240 (×5) and 256 (×10) plus 272–2,928 (×89); 256 is the PS1 PAL leftover |
| Q14 | What is the full SHA-256 of the retail `LOMAX.EXE`? | Pins the baseline locally | ✅ **answered** — prefix `04cc4dfd260037ba…` matches the VOGONS retail hash; the full value stays out of the repo |

**Opened by the asset exporter (LMX-10 M2, 2026-11-18).** Numbers match the
LMX-7 v1 synthesis table (Q15–Q19 are its runtime probes, Q23–Q28 its
tooling/product questions), so the two tables merge without renumbering.

| # | Question | Why it matters | How to resolve |
|---|---|---|---|
| Q20 | How does a `MAP` cell name its `TTAB` tile record? | Blocks "unique tiles per level" and a correct level render | three disagreeing counts (43,612 distinct map words, 75,122 `TTAB` records, 14,862 distinct cell indices; `byte0 & 0x7F` saturates at 127) — find the map→tile lookup in the EXE. Until then the exporter prints `map cell -> tile record: unresolved` |
| Q21 | What do the `TTAB` flags `0x2000`/`0x4000` mean? | Correct tile rendering (flip-H/flip-V is a guess, not evidence) | measured: `0x2000` on 16,503 of 300,488 words, `0x4000` on 2,499, `0x8000` never; render one flagged tile under each flag, or read the blit routine |
| Q22 | Why does `BONUS.WLD` reference `TTAB` index 256 when its `CELL` chunk holds 251 records? | Decides whether a writer must reject or preserve out-of-bank indices | measured: 1,644 words, the only out-of-bank value in the whole install; find the cell-array allocation. Decoders preserve it verbatim and never clamp |
| Q29 | Which `HEAD` palette slot do the cells use, and which byte order do the 15-bit colours have? | Decides whether an exported sheet shows the art as the game does | rendering `VILLAGE`/`HAUNTED`/`TITLE` cells with slot 1 gives natural art, slot 0 a hue-shifted variant, and slot 1 is non-empty in 101/104 `HEAD` blocks — but the container names no slot, so this is an observation: confirm with the tile-blit palette pointer or a screenshot comparison, and settle the channel order (blue-low vs red-low) |
| Q30 | Is a `CELL` record row-major 8x8, and in what order are its four cells combined into a 16x16 tile? | A wrong order silently scrambles every tile | measured: 64 one-byte pixels rule out 4-bpp; row-major and column-major are statistically indistinguishable from the pixel data, and no continuity exists across the four cells of a `TTAB` record (18 % seam adjacent-equality vs 46 % inside a cell), so the 2x2 assembly is unproven — needs the EXE's tile-build loop or a screenshot diff |

## Deliberately unanswered for now

- **Copy protection strength.** Research may describe the CD check `[S3]`; we
  do not need to defeat it to do any of the work above, and we will not ship a
  bypass. Revisit only if a user-owned-disc workflow cannot be supported
  otherwise.
- **PS1 version parity.** The console build has assets the PC build lacks
  (loading screen, language select, `LOGO*.WLD`) `[S2]`, and a third-party mod
  already ports Sega CD *Flink* content `[S6]`. Interesting for preservation,
  irrelevant to the resolution question.
