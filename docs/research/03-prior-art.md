# 3. Prior art and licensing

*Every entry was checked against its own repository/API on 2026-11-16. Licences
are quoted from the GitHub API's `license` field; `None` means no licence file
was detected, i.e. all rights reserved.*

## 3.1 Summary table

| Project | What it is | Licence | Can we fork/redistribute? | Can we cite facts? |
|---|---|---|---|---|
| `Hipnosis183/Lomax` ("Lomax+") | Win32 in-memory loader with widescreen, HFR, D3D11 presenter, audio/CD fixes, mods | **none** (`license: null`) | **No** | Yes, with citation |
| VOGONS hex-edit thread | Two-byte EXE patch to bypass the colour-depth gate; documents the transparency regression | forum post | n/a (facts) | Yes |
| `rafalkarczmarzyk/lomax-password-generator` | Password generator (level/lives/continues) | **none** | No | Yes |
| `SafaSafari/lomax_password_generator` | Same idea, PHP | **none** | No | Yes |
| `dgVoodoo 2`, `DxWnd` | Generic DirectDraw/D3D wrappers | own (proprietary, free) | No | Yes |
| PCGamingWiki article | Consolidated fixes, feature matrix | CC BY-NC-SA | Text only under that licence | Yes |

No open-source engine, decompilation, or format library for Lomax was found.
The closest thing to a format library is the *Flink* mod inside `Lomax+`, and it
is unlicensed like the rest of that repository.

## 3.2 Lomax+ in detail

The only serious modernisation effort, created 2026-11-05 (i.e. days old at the
time of writing) and still being pushed to.

**What it does** `[S5]` `[S3]`:

- Borderless fullscreen with a "fast sharp" scaler, or a Direct3D 11 flip-model
  presenter with a pixel-shader equivalent.
- Widescreen: internal width 320 → **432** (16:9 preset) or **512** (max),
  custom 320–512 in steps of 16. Height stays 240.
- High frame rate / VSync override, 50 Hz PAL mode restoration.
- Fixes: CD check, 32-bit desktop colour depth (renders to 16-bit offscreen
  surfaces and converts at present), broken translucency, DirectSound mixer
  detection on modern Windows, fast sprite blitting, crash fixes.
- Controller + keyboard simultaneously, better mapping, XInput/DualShock.
- Music from files instead of CD; installs the game from a `.bin`/`.cue` image.
- Restores console leftovers: loading screen, language select, cheat mode.
- A mod loader, with a "Flink" mod that ports the Sega CD game
  *The Misadventures of Flink* onto the Lomax engine `[S6]`.

**Why we cannot build on it.** The repository has no licence file and the API
reports `license: null`. Under default copyright that is *all rights reserved*:
no forking, no copying of code, no redistribution, no derivative work. The
project's own README does not grant any rights either. Facts (addresses, struct
offsets, documented format layouts) are not copyrightable and may be cited with
attribution; the prose, code and comments may not be copied into this
repository.

**What that means for our plan.** The realistic options are (a) interoperate
(e.g. our tools read the files the loader also reads, without linking), or (b)
build something adjacent that the loader does not attempt — the resolution
research in [`02-resolution.md`](02-resolution.md) argues for (b), because
feature-for-feature competition against a working loader is a bad trade.

**Quality caveats.** The repository states that most of the code was written by
an AI agent from a human plan, tested manually. The reverse-engineering notes
(`docs/decompilation.md`, 70 KB; `docs/library.md`, 86 KB) are unusually
detailed and internally consistent — but they are one author's notes, not a
peer-reviewed reference. Every fact we rely on should eventually be confirmed
against a real executable, which is a task for Phase 0.

## 3.3 Generic wrappers

`dgVoodoo 2` (DirectDraw/D3D → D3D11/12) and `DxWnd` (windowed mode shim) both
make the stock game start on modern Windows `[S1]` `[S4]`. They do **not**
solve: 4:3-only picture, 320x240 internal resolution, CD check, or the
transparency bug. They are closed-source and not redistributable, but they are
legitimate "run it today" advice for the README.

## 3.4 Licensing rules this project follows

1. **No code from unlicensed projects.** Not even "small" helper functions.
2. **Facts are cited, code is not.** A memory address or a chunk layout may be
   used if its source is named; see [`sources.md`](sources.md).
3. **No game bytes.** No executables, no `.WLD`, no sprites, no music, no disc
   images, no hashes of copyrighted files in the repository.
4. **No DRM/CD-check circumvention shipped by us.** Research may describe what
   the CD check does; our tooling does not bypass it. Users run their own disc.
5. **Derived art stays local.** Any upscaled texture pack is a derivative of
   copyrighted art: distribute the *generator* and a patch recipe, never the
   output.
