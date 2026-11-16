# 5. Open questions

Each question states how to resolve it and what decision hangs on it. None of
these can be answered from public documentation alone.

| # | Question | Why it matters | How to resolve |
|---|---|---|---|
| Q1 | What is the exact chunk header layout of a `.WLD` — `tag+size` or `size+tag`, which endianness, and does the size include the header? Are 3-letter tags space-padded to 4 bytes? | Every parser depends on it; the current scanner only ranks hypotheses | `lomax-modern wldscan` on all `WORLDS/*.WLD`; a real file yields a clean chain to EOF (LMX-1) |
| Q2 | Why does the widescreen ceiling sit at 512 px? | Decides whether ultra-widescreen (>2.13:1) is a small patch or a rewrite | Inspect the fade loop and surface allocation; try widths 528/560 and observe which stage breaks (LMX-2) |
| Q3 | What is the map-width distribution across all 104 maps? | A 640-px view is only useful if most maps are ≥40 tiles wide | Parse `HEAD`/`MAP` per world and histogram (LMX-2) |
| Q4 | Does the PC build use DirectInput for joysticks, or only the PS1 build? | Input work may already be covered by prior art on Windows and impossible to test on Linux | Check imports/strings of `LOMAX.EXE`; test with a pad |
| Q5 | Is there any vertical camera logic? | A taller framebuffer is only viable if the engine can scroll vertically | Search the binary for a `camera_y` equivalent; observe the engine during a vertical drop |
| Q6 | What is the `DEMOS/*.DAT` format? | Needed for regression-testing any render change (demos must replay identically) | Compare demo files; the loader notes say they replay input `[S3]`, not what the bytes mean |
| Q7 | Are `SFX/*.WAV` plain PCM 22.05 kHz mono files, and are `AMBIENT`/`JINGLES` the same? | Determines whether audio tooling is a 20-line wave reader or needs a custom mixer | `file`/format probe on a real install; the loader documents replacement constraints `[S2]` |
| Q8 | Do all shipped tiles really use palette 0 only? | If true, tile upscaling is much simpler (one palette per world) | Measure palette indices per `CELL`/`TTAB` payload (LMX-6) |
| Q9 | How many unique cells, tiles and sprite frames exist in total? | Sizes the art upscaling job and predicts whether 2x can be hand-fixed | Inventory tool (LMX-6) |
| Q10 | Does the stock game run under Wine at all, and which blocker fails first? | Sets the target for an open-source presenter (DLL shim vs app-level) | LMX-3 matrix |
| Q11 | Can a 16-bit offscreen surface be presented without the game's own DirectDraw mode set? | The existing loader says yes on Windows; unverified on Wine/DXVK | Same as Q10 |
| Q12 | Will `Lomax+` ever get a licence, and does its author want collaborators? | The cheapest path to a licensed widescreen implementation is upstream cooperation | Ask the author; watch the repository |
| Q13 | Is the `HEAD` height field ever != 240/8 = 30 for shipped worlds? | A taller plane in data would make a vertical camera patch conceivable | Dump `HEAD` heads for all worlds (LMX-1) |
| Q14 | What is the full SHA-256 of the retail `LOMAX.EXE`? | Pins the baseline locally for patch verification | `lomax-modern doctor` — record locally, never commit |

## Deliberately unanswered for now

- **Copy protection strength.** Research may describe the CD check `[S3]`; we
  do not need to defeat it to do any of the work above, and we will not ship a
  bypass. Revisit only if a user-owned-disc workflow cannot be supported
  otherwise.
- **PS1 version parity.** The console build has assets the PC build lacks
  (loading screen, language select, `LOGO*.WLD`) `[S2]`, and a third-party mod
  already ports Sega CD *Flink* content `[S6]`. Interesting for preservation,
  irrelevant to the resolution question.
