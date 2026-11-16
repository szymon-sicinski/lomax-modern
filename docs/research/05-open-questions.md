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
| Q8 | Do all shipped tiles use palette 0 only? | If true, tile upscaling is much simpler | ⚠️ **blocked** — needs `TTAB`/`CELL` decoding; the container alone does not say which palette a tile uses |
| Q9 | How many unique cells, tiles and sprite frames exist? | Sizes the art upscaling job | ⚠️ **partial** — 14,974 cells total (uniqueness unknown), 104 `TTAB`, 566 `ANIM` chunks |
| Q10 | Does the stock game run under Wine at all? | Sets the target for an open-source presenter | ⚠️ **blocked** — no display/Wine in the measurement environment |
| Q11 | Can a 16-bit offscreen surface be presented outside the game's mode set? | Same target question | ⚠️ **blocked** — as Q10 |
| Q12 | Will `Lomax+` ever get a licence? | Cheapest path to licensed widescreen | ⚠️ **blocked** — needs the author's answer |
| Q13 | Is the `HEAD` height field ever != 240/8 = 30? | A taller plane makes a vertical-camera patch conceivable | ✅ **answered** — yes: 240 (×5) and 256 (×10) plus 272–2,928 (×89); 256 is the PS1 PAL leftover |
| Q14 | What is the full SHA-256 of the retail `LOMAX.EXE`? | Pins the baseline locally | ✅ **answered** — prefix `04cc4dfd260037ba…` matches the VOGONS retail hash; the full value stays out of the repo |

## Deliberately unanswered for now

- **Copy protection strength.** Research may describe the CD check `[S3]`; we
  do not need to defeat it to do any of the work above, and we will not ship a
  bypass. Revisit only if a user-owned-disc workflow cannot be supported
  otherwise.
- **PS1 version parity.** The console build has assets the PC build lacks
  (loading screen, language select, `LOGO*.WLD`) `[S2]`, and a third-party mod
  already ports Sega CD *Flink* content `[S6]`. Interesting for preservation,
  irrelevant to the resolution question.
