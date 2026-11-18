# 15. Strategy report — where it runs and how we present it (v0.3)

> **Status.** This is the **v0.3 deliverable** — the artefact of milestone **M1**
> ([`10-milestones.md`](10-milestones.md#m1--platform--patching-strategy-settled),
> [`20-releases.md`](20-releases.md#v03--strategy-report)). It consolidates the
> WP-1/WP-2/WP-4 findings — previously scattered across
> [`../research/07-wp1-patching-surface.md`](../research/07-wp1-patching-surface.md),
> [`../research/07-wp3-asset-pipeline.md`](../research/07-wp3-asset-pipeline.md)
> and [`../research/07-wp4-runtime-distribution.md`](../research/07-wp4-runtime-distribution.md)
> — into one statement of the **target host**, the **mechanism**, and the
> **product stance**, so a maintainer can read this and know all three without
> re-running the experiments.

> **Revision v1** (2026-11-18). The human resolved the target-host decision in
> favour of **disc-less users**: we do **not** run `LOMAX.EXE`, the clean-room
> `ddraw.dll` proxy is demoted to an optional disc-owner appendix, and the main
> line becomes **our own engine + presenter over the MIT data layer**. The same
> decisions fixed the input format (an unpacked game directory — no ISO, no
> ripping), the product stance (**quality-of-life first**, authentic as an
> opt-in), the platforms (Linux AppImage + Windows `.exe` now; macOS deferred),
> and the budget (no ceiling — track actual spend). See
> [`30-risks.md`](30-risks.md) and
> [`../research/05-open-questions.md`](../research/05-open-questions.md).

## 1. Decision summary

| Decision | Answer | Status |
|---|---|---|
| **Target host** | Our own engine + presenter over the MIT data layer — **not** Wine/Proton + `LOMAX.EXE`, **not** a shim | decided (human) |
| **Mechanism** | Data-layer reader (`wld.py`, byte-exact) → engine core → own renderer/presenter; **no hooking** of the original binary | decided |
| **Input** | An unpacked game directory (retail layout: `WORLDS/`, `SFX/`, `AMBIENT/`, `JINGLES/`, `DEMOS/`, `LOMAX.EXE` present but unused); the engine takes a path. **No ISO handling, no ripping instructions** anywhere | decided (human) |
| **Product stance** | **Quality-of-life first** — modern defaults (widescreen, 60 fps, smooth scaling, save states, generous input) with an *authentic* toggle; native 320×240 integer-scaled first, HD render later | decided (human) |
| **Platforms** | Linux (AppImage) + Windows (`.exe`) now; macOS deferred; no store presence | decided (human) |
| **`ddraw.dll` proxy** | Optional appendix track for disc owners; not part of v0.4 | demoted |
| **Scope / CD check** | Disc-less users; the CD check is never reached and never bypassed | decided (human) |
| **Repository** | One repository — engine (`native/`) and Python tooling together; no split | decided (human) |

## 2. Target host: why we are not hosting the original at all

Three paths were on the table at the start of M1: run the retail binary under
**Wine/Proton**, wrap it with a **shim** (a dropped-in `ddraw.dll` proxy), or
write our **own engine** over the data layer. WP-4's compatibility matrix
([`07-wp4-runtime-distribution.md`](../research/07-wp4-runtime-distribution.md)
§4) settles it: for a **disc-less** user, both of the first two paths are
blocked by things that live *inside* the executable, so the only licence-clean
path that reaches a playable frame for that audience is the third.

- **Wine + stock `LOMAX.EXE`** is blocked by **B1** (the 8/16-bpp GDI colour
  gate) and **B3** (the MCI `cdaudio` disc check) — §4 below. Neither is a Wine
  bug; both are decisions the executable makes.
- **Wine + a `ddraw.dll` proxy** can own the present call and neutralise
  `SetDisplayMode` (B2), but it **cannot clear B1** — the GDI query runs on the
  screen DC *before* `DirectDrawCreate` — and it does **nothing** about B3. So a
  proxy serves **disc owners** and no one else.
- **Our own engine + presenter over the data layer** never runs the exe, so it
  never meets B1, B2, B3 or B4. It reads the user's unpacked directory and
  renders it itself. This is the path the human chose.

The decision is recorded as resolved in
[`30-risks.md`](30-risks.md) (decisions) and in
[`../research/05-open-questions.md`](../research/05-open-questions.md) (Q28).

## 3. The original, in one paragraph

The retail PC build is a **32-bit Windows 9x application** — PE32, statically
linked MSVC 4.x CRT and MFC 4.2, DirectDraw 7 + Direct3D 3 + DirectSound, 8/16
bpp, CD-DA music — **not** a DOS game
([`01-platform-assessment.md`](../research/01-platform-assessment.md) §1.1,
[`07-wp1-patching-surface.md`](../research/07-wp1-patching-surface.md) §1). It
imports `DDRAW.dll` for exactly one function (`DirectDrawCreate`), `DINPUT.dll`
for `DirectInputCreateA`, and `DSOUND.dll` for `DirectSoundCreate`
([`07-wp1-patching-surface.md`](../research/07-wp1-patching-surface.md) §2).
Internal resolution is 320x240, 16-bit (`B5G6R5`), driven by a 60 Hz multimedia
timer (`WINMM.timeSetEvent`); the renderer is DirectDraw blits with an optional
Direct3D 3 execute-buffer path
([`02-resolution.md`](../research/02-resolution.md) §2.1–§2.2). This paragraph
is the ground truth the own engine must reproduce from data.

## 4. The four blockers and what they force

WP-4 re-verified these from the binary and the Wine source
([`07-wp4-runtime-distribution.md`](../research/07-wp4-runtime-distribution.md)
§2–§4). They are the *reason* the exe path is closed to disc-less users, and
they name exactly what any disc-owner tool would have to clear (§9).

| Blocker | What it is (measured) | For us |
|---|---|---|
| **B1** — 8/16-bpp colour gate | A **GDI** query: `USER32.GetDC(NULL)` + `GDI32.GetDeviceCaps(BITSPIXEL)×GetDeviceCaps(PLANES)`, compared to 8/16 at `0x40799c`; fatal dialog `"Lomax will only run on 8 and 16 bit deep desktops."` at `0x462be0`. dgVoodoo 2 and DXVK **cannot** clear it (they own `ddraw`/D3D, not the display DC). | never reached — we don't run the exe |
| **B2** — missing 320x240 mode | `IDirectDraw::SetDisplayMode` (a vtable method): Wine enumerates only the host mode; `EmulateModeset` pads/scales rather than advertising 320x240. | never reached |
| **B3** — CD check | MCI `cdaudio` (`open cdaudio`, `status cdaudio length track %d`) — a **disc problem, not a Wine problem**. | never reached — and we never bypass it |
| **B4** — MFC start order | An artefact of injection-based loaders, not of the game. | never reached |

The decisive pair is **B1 + B3**: a disc-less user cannot reach the frame
through the retail exe under Wine no matter what we wrap around it, unless we
patch the exe or ship a disc-check bypass — both forbidden
([`../research/03-prior-art.md`](../research/03-prior-art.md) §3.4,
[`30-risks.md`](30-risks.md) L3).

## 5. Mechanism: the `ddraw.dll` proxy is an appendix, not the main line

WP-1 settled the *patching surface*: `DDRAW.dll` is imported for exactly
`DirectDrawCreate`, so a clean-room proxy could export that one function, forward
to the real `ddraw`, and wrap the returned `IDirectDraw`/`IDirectDrawSurface(7)`
vtables to hook the final `Blt`/`Flip` — a **forward-everything proxy with a
hook at the present call**, explicitly *not* a DXVK-style translator
([`07-wp1-patching-surface.md`](../research/07-wp1-patching-surface.md) §3, §6).
That verdict is **kept as evidence**, not as the plan:

- The proxy is the correct mechanism **for disc owners**, and it remains
  documented here as an *optional* appendix (v0.4 does not depend on it). Its
  findings also explain *how the original renders*, which is input to our own
  renderer (§6).
- The **main-line mechanism** is now: `wld.py` (byte-exact `read → write`, the
  LMX-5 foundation named in
  [`../research/07-wp3-asset-pipeline.md`](../research/07-wp3-asset-pipeline.md)
  §3) → an **engine core** (map/collision/entities/timing) → an **own
  renderer/presenter** (integer scaling + pixel-art filters). No import hook, no
  injection, no exe byte is touched — the clean-room boundary
  ([`../architecture.md`](../architecture.md#2-the-clean-room-boundary)) is met
  by construction because we never read the executable's code into ours.

## 6. Renderer facts our engine must reproduce

Renderer-side constraints measured by WP-2, restated because the own engine
*owns* the renderer now:

- **16-bit `B5G6R5` primary.** DirectDraw maps 16-bpp mode requests to
  `B5G6R5` ([`07-wp4-runtime-distribution.md`](../research/07-wp4-runtime-distribution.md)
  §3).
- **60 Hz logic tick.** `WINMM.timeSetEvent` / `timeGetTime`
  ([`07-wp1-patching-surface.md`](../research/07-wp1-patching-surface.md) §4).
- **512 px ceiling is renderer-side, not data-side.** Fade/dissolve surface
  rounded to a multiple of 32 (`⌈w/32⌉·32`) plus 199 hard-coded width sites;
  plane widths reach 7,200 px ([`02-resolution.md`](../research/02-resolution.md)
  §2.4). Because we own the renderer, this ceiling is *ours to lift*, not a
  patch target.
- **Direct3D 3 execute buffers are render-side.** The 0x5624-byte buffer /
  128-quad budget / `CreateExecuteBuffer` at `0x407545` emit quads into a
  DirectDraw surface presented by a `Blt`
  ([`02-resolution.md`](../research/02-resolution.md) §2.2). Our renderer draws
  the same geometry directly and is not bound by the quad budget.

## 7. Fidelity stance: quality-of-life first

The product stance **inverts** the fidelity-first assumption of the original:
**the default experience is the modern one**, and authenticity is an opt-in
toggle.

| Aspect | Modern default | Authentic toggle |
|---|---|---|
| Resolution | widescreen, integer-scaled to fill | native 320×240 pillarboxed |
| Frame rate | 60 fps (or unlocked) | original 60 Hz pacing, tick-faithful |
| Scaling | smooth, integer + optional filter | nearest-neighbour |
| Progress | our own save states **and** password both ways | password-only |
| Input | generous (rebinding, hot-plug) | original mapping |

The first ship is still **native 320×240 integer-scaled** (HD internal render is
later, M9): the modern defaults land progressively as each milestone ships, and
the authentic toggle is the escape hatch for purists. This stance is re-checked
in **M4** (presenter) and in the release definitions
([`20-releases.md`](20-releases.md)).

## 8. What a disc-less user supplies

The engine takes **one path: an unpacked game directory** in the retail layout —
`WORLDS/`, `SFX/`, `AMBIENT/`, `JINGLES/`, `DEMOS/`, and `LOMAX.EXE` (present
but **never read**). **No ISO handling and no ripping instructions appear
anywhere** — not in the README, not in docs, not in the runbook. Everything the
engine reads is a file already on disk in that directory (Q29).

The audio inventory is measured (Q7, Q30): **82 RIFF/WAVE files, mono
22,050 Hz 16-bit** — 67 SFX (1.4 MiB), **12 ambient loops** (6 worlds × a stereo
`_L`/`_R` pair, 3.74–6.20 s each, 2.4 MiB), and 3 jingles (`LEVELEND` 2.98 s,
`GAMEOVER` 4.01 s, `WORLDEND` 4.40 s). There is **no CD-DA, MP3, OGG or MOD**
content: the soundtrack lived on the disc as CD audio, so a disc-less user gets
ambience and jingles but **no music**. The plan is the ambient L/R pair as the
per-world bed, jingles on transitions, SFX as-is — **no ripping, no bundled
audio**. An optional user-supplied music folder may be designed later and is
**not** a v0.1 requirement.

The project is **one repository**: the engine (`native/`) and the Python tooling
live together — there is no split.

## 9. First-run recipe — disc-owner appendix (unverified)

Kept for disc owners who prefer the retail exe, and for conformance comparisons
against the original. It is **not** the v0.4 path and is **unverified** here (no
Wine/display in the sandbox). It uses the user's **physical disc** only — no
image mounting, no ripping.

```bash
# Fedora/Nobara 44
sudo dnf install wine wine-core xorg-x11-server-Xephyr

# A 16-bpp X display clears B1; a virtual desktop does not.
Xephyr :2 -screen 640x480x16 -ac -resizeable &
export DISPLAY=:2

export WINEPREFIX="$HOME/.local/share/lomax-wine"
wineboot -u

# B3: the user's own physical disc in the drive.
cd "$LOMAX_GAME_DIR" && wine LOMAX.EXE
```

Three probes settle the unverified cells
([`07-wp4-runtime-distribution.md`](../research/07-wp4-runtime-distribution.md)
§7): **P1** `DISPLAY=:2 wine ddrawprobe.exe` at depth 16 vs 24 (B1 mechanism) ·
**P2** same with `EmulateModeset=Y` at depth 32 · **P3** `wine LOMAX.EXE` with
the user's own disc (B3 clears). These map to Q15–Q19 (§10).

## 10. Open questions

Filed in
[`../research/05-open-questions.md`](../research/05-open-questions.md):

- **Q15–Q19** — Wine runtime questions (appendix-track only; they gate the
  disc-owner fallback of §9, not the main line).
- **Q20–Q27** — the data-layer unknowns (map→tile link, `TTAB` flags, the
  `BONUS.WLD` index-256 anomaly, `NMY` framing, `ANIM` layout, password codec,
  `MACR`/`PAGE`, counting units). These are the backlog for M2 via the WP-3 gap
  list G1–G15.
- **Q28** — the M2 target-host fork — **resolved**: disc-less, own engine.
- **Q29** — the input/data-manifest question — **resolved**: an unpacked game
  directory in the retail layout; `LOMAX.EXE` present but unused.
- **Q30** — the music question — **resolved**: no music content in the data;
  ambient L/R bed + jingles + SFX; an optional user-supplied music folder is a
  later possibility, not v0.1.
