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
| `[S8]` | WineHQ AppDB, *Lomax 1*, test by LunaVorax, Wine 1.7.0, Arch x86_64, 2013-08-03 — <https://appdb.winehq.org/objectManager.php?sClass=version&iId=3884> (archived: `web.archive.org/web/20240221150621/…`) | Stock game launches and plays from the CD under a **depth-16 X server** (`xinit … -- :1 -ac -depth 16`); CD audio music works; graphical glitches (invisible moving platforms, one-frame sprite zoom); otherwise refuses to launch | AppDB report (facts) |
| `[S9]` | Wine source, `master` (mirror `github.com/wine-mirror/wine`) | `dlls/ddraw/ddraw.c:1121-1139` (8/16-bpp `SetDisplayMode` → `P8_UINT`/`B5G6R5`), `:2466-2500` (`EnumDisplayModes` filtered to 32/16/8); `dlls/winex11.drv/display.c:42-45` (supported depths 8/16/24/32), `:76-101` (one mode = host size at `screen_bpp`), `:132-136` (mode change ignored, returns success); `dlls/win32u/sysparams.c:2148-2206` (virtual mode list), `:4508` (`is_virtual_desktop() \|\| emulate_modeset` → `DISP_CHANGE_SUCCESSFUL`), `:6093` (`EmulateModeset` key); `dlls/desk.cpl/main.c:245-257` (writes `HKCU\Software\Wine\X11 Driver\EmulateModeset`) | LGPL-2.1+ (facts cited) |
| `[S10]` | WineHQ news, *Wine 10.0 Released* (2025-01-21) and *Wine 11.0 Released* (2026-01-13) | Opt-in emulated modesetting (pad/scale to the physical display, `desk.cpl` control); Wine 11 is the current stable line and one 64-bit prefix runs 32-bit PE | Release notes (facts) |
| `[S11]` | PCGamingWiki, *DgVoodoo 2*, and the community file *dgVoodoo2 v2.79.3 & v2.81.3 (Wine/Proton compatible)* | Under Linux/Wine, dgVoodoo 2 needs `WINEDLLOVERRIDES="ddraw=n,b"`; "versions below 84 should work"; 2.79.3/2.81.3 are the last Wine/Proton-compatible releases | Wiki prose (facts); the tool itself is closed and not redistributable |
| `[S12]` | dgVoodoo 2 official *About* — <https://dege.freeweb.hu/dgVoodoo2> | Implements DirectX 1–7 (all DirectDraw/Direct3D ≤ 7), Glide, D3D8.1 and D3D9 on Direct3D 11/12 output devices; Windows 7+ | Closed source, freeware |
| `[S13]` | DxWnd release notes — `github.com/DxWnd/DxWnd.reloaded`, `build/readme-relnotes.txt` | Hooks DirectDraw, emulates primary/backbuffer on a virtual desktop, 8-bpp palettised handling, neutralises `ChangeDisplaySettings`/registry modes | GPL-2.0 (facts cited) |
| `[S14]` | DXVK README | Vulkan translation for **Direct3D 8/9/10/11** only — no DirectDraw, no GDI | zlib (facts cited) |
| `[S15]` | `Xvfb(1)`, Debian manpages | `-screen screennum WxHxD` sets depth; "the fb code for any depth can be exercised … without the need for real hardware" | Manpage (facts) |
| `[S16]` | Lutris docs, `docs/installers.rst` | Installer YAML keys used by the packaging options: `wine: version`, `wine: overrides`, `wine: Desktop`, `system: env`, `game: exe/prefix/working_dir` | GPL-3.0 docs (facts cited) |

`[S8]`–`[S16]` were added by the LMX-7 reports
([`07-wp4-runtime-distribution.md`](07-wp4-runtime-distribution.md) §9) and were
accessed **2026-11-17**; `[S1]`–`[S7]` were accessed 2026-11-16.

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
