# Research index

Read in this order. Everything here is a research record; from `06` onward it is
measurement against the retail install rather than desk research, and each
document says which of its claims were measured in the session that produced it.

| Document | Question it answers |
|---|---|
| [`01-platform-assessment.md`](01-platform-assessment.md) | What *is* this build, and what does that rule out? |
| [`02-resolution.md`](02-resolution.md) | **Main deliverable:** what can be improved about resolution, in three layers, with numbers and a decision matrix |
| [`03-prior-art.md`](03-prior-art.md) | What already exists, what may be reused, what may not |
| [`04-improvement-backlog.md`](04-improvement-backlog.md) | Ranked work items with effort, risk and done criteria |
| [`05-open-questions.md`](05-open-questions.md) | What needs real files or a hex editor to answer |
| [`06-measurements-and-improvements.md`](06-measurements-and-improvements.md) | **Measurements from the retail install** and the resulting top-5 plan |
| [`07-wp1-patching-surface.md`](07-wp1-patching-surface.md) | **How do we reach the finished frame without touching `LOMAX.EXE`?** — PE32 identity, the full 13-DLL import table, and why a `ddraw.dll` proxy is the mechanism to build |
| [`07-wp3-asset-pipeline.md`](07-wp3-asset-pipeline.md) | **What does 2× `WLD`/`SPR` re-authoring need?** — a 15-item gap list with a test each, the `TTAB` framing measured, and the two documented claims that measurement falsified |
| [`07-wp4-runtime-distribution.md`](07-wp4-runtime-distribution.md) | **Wine/Proton, a shim, or a native port?** — the GDI colour gate at `0x40799c`, what dgVoodoo 2, DxWnd and DXVK can and cannot clear, and a package set verified for Fedora 44 |
| [`08-player-animation-selector.md`](08-player-animation-selector.md) | **How does the original pick, time and place the player's poses?** — reproduction commands (read-only `objdump` VAs and an audit script) for `file-formats.md` §2.6.2: the `WALK`/`RUN` gate, the jump/fall/landing clips, the `dx`/`dy` blit and the per-clip rate |
| [`sources.md`](sources.md) | Provenance for every `[S#]` citation |
| [`../roadmap/00-research-plan.md`](../roadmap/00-research-plan.md) | The staged roadmap (research plan, milestones, releases, risks, budget) |

## Executive summary

- The PC build is a 32-bit Windows 9x application (MFC 4.2, DirectDraw 7,
  Direct3D 3, DirectSound, 8/16 bpp, CD-DA audio), **not** a DOS game
  `[S1]` `[S2]`.
- Display, widescreen up to 512x240, high frame rate, controller, audio-from-CD
  and a Direct3D 11 presenter are **already solved** by an unlicensed loader
  `[S3]` `[S5]`.
- The remaining meaningful gaps are: an **open-source, Linux-capable
  presentation layer with pixel-art filters**; a **documented asset pipeline**
  for `.WLD`; and, as a spike, **true higher-resolution rendering with upscaled
  art**.
- Resolution work splits into presentation (cheap, safe), width (expensive,
  mostly solved) and pixel density (expensive, unsolved, legally constrained).
  The recommendation is to stop assuming "resolution = widescreen" and treat
  pixel density as the real frontier.
- **Measured on the retail install (2026-11-16):** the `.WLD` container layout is
  confirmed (9/9 files), `HEAD` dimensions are verified on 104/104 planes
  against their `MAP` sizes, all 82 audio files are plain mono 22.05 kHz PCM,
  and 16 of 104 planes are narrower than 432 px — which reproduces the prior
  art's "16 of 104 maps" exactly. The 512 px ceiling is therefore a code limit,
  not a data limit.

## Conventions used in these documents

- `[S#]` — citation, see [`sources.md`](sources.md).
- `[derived]` — arithmetic or inference from cited facts, reproducible from the
  snippets in the document.
- "Documented" ≠ "verified in this repository". Format claims are graded in
  [`../file-formats.md`](../file-formats.md) with D/H/V markers.
