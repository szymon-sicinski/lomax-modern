# 1. Platform assessment

*Status: desk research. Every claim is tagged `[S#]` with a source in
[`sources.md`](sources.md). Claims derived by arithmetic from cited facts are
tagged `[derived]`. Nothing here was produced by running the game, because the
game files are not part of this repository.*

## 1.1 The premise check

The task starts with "The Adventures of Lomax, 1996, PC". The first job is to
establish what the PC build actually is, because that single fact decides every
downstream option (DOSBox vs Wine vs a native port) `[S1]` `[S2]`.

| Property | Value | Evidence |
|---|---|---|
| Executable | `LOMAX.EXE`, PE32 (32-bit Windows) | `[S1]` API table: "Executable: 32-bit"; `[S3]` refers to `LOMAX.EXE` and its SHA-256 |
| Framework | MFC 4.2 + statically linked MSVC runtime, CTL3D | `[S2]` "MFC classes and compiler-generated code" |
| Video | DirectDraw 7 for surfaces/present; Direct3D 3 (execute buffers) optional | `[S1]`, `[S2]` "Direct3D (DirectX 3, execute buffers)" |
| Colour depth | 8 or 16 bpp only; refuses to start otherwise | `[S1]`, `[S2]` compatibility patches |
| Internal resolution | 320x240, hard-coded | `[S2]` "Rendering / boot and main loop" |
| Audio | DirectSound software mixer + CD-DA via MCI `cdaudio` | `[S2]` "Sound", `[S3]` "The CD check" |
| Config | Windows registry, `HKCU\Software\Psygnosis\Lomax` | `[S1]` |
| Saves | None: password system | `[S1]`, `[S2]` "Passwords" |
| Copy protection | CD presence: `CD_VerifyLomaxDisc` compares track 2–24 lengths against a table | `[S3]` "The CD check" |
| Disc layout | ISO 9660 with 24 audio tracks; `MUSIC\*.DAT` are pointers into audio tracks | `[S3]` "CD music" |
| Installed footprint | 110 files, ~11.6 MB (`LOMAX.EXE`, `GAME.TXT`, help files, `WORLDS`, `SFX`, `DEMOS`, `JINGLES`, `AMBIENT`) | `[S3]` "Installing from the disc image" |
| Tick rate | 60 Hz step (`mov ebx, 0xA7` in `Game_Frame`); the PS1 PAL 50 Hz switch is present but never written on PC | `[S2]` compatibility patches |

**Conclusion.** This is a 32-bit Windows 9x application, not a DOS program.
DOSBox is the wrong tool, and so is any "DOS-era" advice found in
abandonware listings. The viable platform paths are Wine/Proton, a Win32
in-memory loader, or a clean-room reimplementation.

## 1.2 What the architecture implies

**It is a 2D engine with a tile/sprite renderer.** Levels are tile maps
(16x16 tiles made of 8x8 cells) with a parallax plane stack, actor placement
lists and byte-per-cell collision `[S2]` "Levels and files". Sprites are
palettised surfaces blitted through GDI DCs, assembled into a per-frame queue,
and a subset of them is emitted as Direct3D 3 quads (scaled, rotated or
translucent ones) `[S2]` "Rendering".

Three consequences matter for modernisation:

1. **No 3D asset pipeline.** All art is raster and palettised. There is no
   polygon budget to raise and no model/texture resolution to unlock.
2. **The logical world grid is 16 px.** Collision is one byte per map cell and
   actor coordinates are world pixels `[S2]`. Rendering scale and simulation
   are therefore separable — important for the true-HD question in
   [`02-resolution.md`](02-resolution.md).
3. **The platform layer is thin but pervasive.** Display, input, audio and CD
   checks are concentrated in a handful of functions (`DDraw_InitSurfaces`,
   `Display_SetVideoMode`, `D3D_InitDevice`, audio init, `CD_VerifyLomaxDisc`)
   `[S2]` `[S3]`, which is what makes an in-memory loader practical at all.

## 1.3 Why there is no quick "just run it" answer

The stock executable fails on current systems for reasons that are all
platform-layer, not gameplay:

- **Colour-depth gate.** Windowed mode aborts unless the desktop is 8 or 16 bpp
  (`DDraw_InitSurfaces`, 0x40799c) `[S2]`.
- **Missing fullscreen mode.** Exclusive fullscreen needs a 320x240 8/16-bpp
  mode; DirectDraw on Windows 10/11 enumerates 32-bpp modes only `[S3]`.
  A community hex patch (`83 FD 08 74 1E 83 FD 10 74 19` →
  `… 74 1E 83 FD 10 EB 19`) bypasses the check but leaves every transparent
  sprite black `[S4]`.
- **CD check.** Two dialogs (insert CD / wrong CD) plus an MCI `cdaudio` open
  `[S3]`.
- **MFC-era dependencies.** Common controls and the property sheet behave badly
  when the process is started the wrong way round; the existing loader has to
  let the game's own thread reach the entry point before injecting `[S3]`.

Existing workarounds: `DxWnd`/`dgVoodoo 2` for the DirectDraw failures `[S1]`
`[S4]`, and `Lomax+`, an in-memory loader that fixes all four issues plus
widescreen and high frame rate `[S3]` `[S5]`. See
[`03-prior-art.md`](03-prior-art.md).

## 1.4 Reproducible baseline

To talk about "improving" anything, the baseline has to be pinned:

- The retail executable's SHA-256 is quoted (truncated) by the existing loader
  as `5D5DE600…8CA13A79` `[S3]`. A full hash should be recorded locally with
  `lomax-modern doctor` and **never committed** — it is a fingerprint of a
  copyrighted binary, and publishing it is unnecessary.
- Reference behaviour to compare against: 60 Hz logic step `[S2]`, 320x240
  picture, borderless scaling, CD-DA music `[S1]`.
- Regression criterion for anything we build later: the 8 attract demos must
  replay tick-for-tick at the original camera width (this is exactly the check
  the prior art used for its widescreen patches) `[S3]` "Demos".

## 1.5 Unknowns carried forward

Recorded in [`05-open-questions.md`](05-open-questions.md). The important ones
for planning: the precise reason for the 512 px widescreen ceiling, the map
width distribution across all 104 maps, and whether the game's DirectInput
joystick path exists in the PC build or only in the PS1 build.
