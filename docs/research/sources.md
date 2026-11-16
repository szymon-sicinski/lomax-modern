# Sources

All URLs accessed **2026-11-16**. Facts are cited, prose and code are not copied.
Where a source is an unlicensed reverse-engineering project, only its factual
claims (addresses, constants, documented layouts) are used; see
[`03-prior-art.md`](03-prior-art.md) for the licence analysis.

| Tag | Source | What was taken from it | Licence / status |
|---|---|---|---|
| `[S1]` | PCGamingWiki, *The Adventures of Lomax* — <https://www.pcgamingwiki.com/wiki/The_Adventures_of_Lomax> | Release years, developer/port credits, registry config path, password saves, API table (DirectDraw 7, Direct3D 3, 32-bit exe), 8/16-bpp requirement, known fixes, system requirements, Lomax+ feature summary | CC BY-NC-SA (prose); facts reused |
| `[S2]` | `Hipnosis183/Lomax`, `docs/decompilation.md` — <https://github.com/Hipnosis183/Lomax> | Internal 320x240, 8/16 bpp, palette/DIB handling, 16x16 tiles from 8x8 cells, `SpriteFrame` 0x38, 256 banks, D3D3 execute buffer and 128-quad budget, `.WLD` chunk order, `HEAD`/`TTAB`/`MAP`/`GNMY`/`CELL` details, collision bytes, password layout, `GAME.TXT` markers, `g_bSpeed50Hz`, console leftovers | **No licence (all rights reserved)** — facts cited, no text or code copied |
| `[S3]` | `Hipnosis183/Lomax`, `docs/loader.md` — same repository | Widescreen implementation (199 patch sites, 432/512 widths, 448-wide surfaces, multiple-of-32 fade tiles), camera clamp formula, 16/104 narrow maps, demo tracing, D3D11 presenter and "fast sharp" scaler, install manifest (110 files, 11.6 MB), CD check behaviour, `MUSIC\*.DAT` pitfall, truncated SHA-256 of `LOMAX.EXE` | **No licence** — facts cited |
| `[S4]` | VOGONS forum, *Patching Lomax to run on modern displays* — <https://www.vogons.org/viewtopic.php?t=51166> | The `83 FD 08 74 1E 83 FD 10 74 19` → `…EB 19` patch, the black-transparency regression it causes, `DxWnd` as a workaround | Forum post (facts) |
| `[S5]` | `Hipnosis183/Lomax`, `readme.md` + GitHub API `license: null` | Feature list of Lomax+, AI-assistance disclosure, no licence | **No licence** |
| `[S6]` | `Hipnosis183/Lomax`, `mods/flink/docs/flink.md` | That `XPK`/NUKE packing belongs to the Sega CD *Flink* data, **not** to PC Lomax; Flink mod scope | **No licence** — facts cited |
| `[S7]` | GitHub REST API — <https://api.github.com> | Repository search results used to establish that no open-source Lomax engine/format library exists; licence fields of Lomax+ and the two password generators | Metadata, public |

## Checks performed

- `GET /repos/Hipnosis183/Lomax` → `license: null`, `language: C`, created
  2026-11-05, pushed 2026-11-16.
- Repository searches for `lomax lemmings`, `"adventures of lomax"`,
  `misadventures of flink`, `psygnosis WLD chunk` → no engine, decompilation or
  format library beyond the above (only two unlicensed password generators).
- The cited widescreen arithmetic was recomputed independently: a 432-px
  picture needs 448-px surfaces when rounded up to a multiple of 32, matching
  `[S3]`.

## Access-date policy

Sources are re-checked before any claim is promoted from "documented" to
"verified in this project". A promotion requires an artefact in this repository
(a measurement table, a test, or a screenshot with no game data in it), not a
second reading of the same page.
