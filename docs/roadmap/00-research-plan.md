# 0. Research plan — the question set

This document is the spine of the roadmap. It states the one question the whole
project is trying to answer, records what the earlier research (docs 01–06)
already settled so we do not re-derive it, then groups the *remaining* questions
into work packages. Each package states what evidence would settle its questions
and what decision that evidence unblocks. Companion documents:

- [`10-milestones.md`](10-milestones.md) — the staged plan (M0…M7).
- [`20-releases.md`](20-releases.md) — releases v0.1…v1.0 and their contents.
- [`30-risks.md`](30-risks.md) — the risk register.

## Table of contents

1. [The one-page answer](#1-the-one-page-answer)
2. [What the earlier research already answered](#2-what-the-earlier-research-already-answered)
3. [Work packages](#3-work-packages)
4. [The strategy decision: three mechanisms, one winner](#4-the-strategy-decision-three-mechanisms-one-winner)
5. [How the packages map to board cards](#5-how-the-packages-map-to-board-cards)

---

## 1. The one-page answer

**The smallest change that makes Lomax pleasant on a 2026 Linux desktop is an
open-source presentation layer** — a clean-room DirectDraw shim (a `ddraw.dll`
proxy) that takes the stock game's finished 16-bit frame and presents it
borderless, integer-scaled, with pixel-art filters, under Wine/Proton.

Why this and not something bigger:

- The game is a Win32/MFC 4.2/DirectDraw 7 application, not DOS
  ([`01-platform-assessment.md`](../research/01-platform-assessment.md)), so the
  platform problem is "get a Win32 binary to present a 320x240 frame nicely on a
  modern Linux screen", not "emulate a console".
- Presentation (**L1**) needs no knowledge of game internals beyond "there is a
  16-bit framebuffer", is the cheapest real win, and is the one improvement the
  unlicensed prior art does **not** provide on Linux
  ([`02-resolution.md` §2.3](../research/02-resolution.md#23-layer-1--presentation-the-cheapest-real-win)).
- Widescreen (**L2**) and CD/audio/controller fixes are **already solved** by
  `Lomax+` but that project is Windows-only and unlicensed
  ([`03-prior-art.md`](../research/03-prior-art.md)); we interoperate with its
  *facts*, we do not reimplement its *code*.

**The path from there to a modernised build**, in order of decreasing
value-per-risk:

1. **M1** — settle the platform strategy (Wine/Proton vs shim vs native) and the
   hook mechanism (see [§4](#4-the-strategy-decision-three-mechanisms-one-winner)).
2. **M2** — ship the open-source presenter (L1). Lomax is pleasant on Linux.
3. **M3** — ship the `.WLD` read/write toolkit with byte-exact round trip plus a
   tile/sprite exporter. This unlocks every content project.
4. **M4** — password tool (small, self-contained, immediately useful).
5. **M5** — matte-aware 2× upscaler + 2× pack writer. The art pipeline.
6. **M6** — 2× internal-render spike (true HD) with an explicit go/no-go.
7. **M7** — long tail: level editor, translation support.

Every step before M6 is distributable as code without shipping a single game
byte; M6/M7 are only pursued if their falsifiers stay green (see
[`10-milestones.md`](10-milestones.md) and [`30-risks.md`](30-risks.md)).

## 2. What the earlier research already answered

The following questions are **settled input**, not research tasks. They are
listed here so no card re-asks them; the answer column points at the document
and section that closed them.

| # | Question | Status | Where it was settled |
|---|---|---|---|
| — | Is the PC build DOS or Win32? | Win32 (PE32, MFC 4.2, DirectDraw 7, Direct3D 3, 8/16 bpp) | [`01-platform-assessment.md` §1.1](../research/01-platform-assessment.md#11-the-premise-check) |
| — | What is the internal resolution, and which axis is free? | 320x240; width only; three layers (presentation / width / pixel density) | [`02-resolution.md` §2.1–§2.4](../research/02-resolution.md) |
| — | Is the widescreen/loader space already occupied, and may we reuse it? | Yes; `Lomax+` is unlicensed → facts only, never code | [`03-prior-art.md` §3.1–§3.2](../research/03-prior-art.md) |
| Q1 | Exact `.WLD` chunk header layout | **answered** — tag[4] space-padded + big-endian u32 payload size, 9/9 files | [`06-measurements-and-improvements.md` §6.2](../research/06-measurements-and-improvements.md#62-format-facts-now-verified), [`05-open-questions.md`](../research/05-open-questions.md) |
| Q4 | DirectInput in the PC build? | **answered** — `DINPUT.dll` in the import table | [`06-measurements-and-improvements.md` §6.4](../research/06-measurements-and-improvements.md#64-q1q14) |
| Q7 | Audio format? | **answered** — 82/82 RIFF/WAVE mono 22.05 kHz 16-bit | [`06-measurements-and-improvements.md` §6.4](../research/06-measurements-and-improvements.md#64-q1q14) |
| Q13 | Is `HEAD` height ever ≠ 240? | **answered** — yes, 256 (PS1 PAL) and 272–2,928 occur | [`06-measurements-and-improvements.md` §6.4](../research/06-measurements-and-improvements.md#64-q1q14) |
| Q14 | Retail `LOMAX.EXE` identity | **answered** — hash prefix matches VOGONS; full value stays local | [`06-measurements-and-improvements.md` §6.4](../research/06-measurements-and-improvements.md#64-q1q14) |
| LMX-1 | Confirm `.WLD` chunk layout on real files | **done** | [`04-improvement-backlog.md`](../research/04-improvement-backlog.md) |
| Q3 | Map-width histogram | **partial** — 104 plane widths measured; playfield attribution needs `g_LevelDefs` | [`06-measurements-and-improvements.md` §6.4–§6.5](../research/06-measurements-and-improvements.md) |

The following are **explicitly out of scope for research** because they are
already decided by policy, not by evidence:

- **Widescreen re-implementation (L2)** — out of scope; competing with the
  unlicensed loader costs months for no delta
  ([`02-resolution.md` §2.7](../research/02-resolution.md#27-recommendation)).
- **CD-check bypass, disc installers, EXE patchers** — never shipped
  ([`03-prior-art.md` §3.4](../research/03-prior-art.md#34-licensing-rules-this-project-follows)).
- **Redistributing extracted art, audio, or level data** — never.

## 3. Work packages

Five research packages, each sized to a 1–2 h off-peak shift, plus one synthesis
pass. The packages are independent of one another except where noted; the
synthesis runs last.

### WP-1 — Patching surface (`specialist`)

**Question set.**

- What does `LOMAX.EXE`'s import table actually allow: which DLLs are imported
  (`DDRAW.dll`, `DINPUT.dll`, `DSOUND.dll`, `WINMM.dll`, `COMCTL32.dll` are
  documented `[S2]`), and can a `ddraw.dll` proxy capture the present call
  without touching the executable?
- What is the MFC 4.2 startup order, and at which point may a hook inject
  safely without breaking the property-sheet/`CTL3D` init
  ([`01-platform-assessment.md` §1.3](../research/01-platform-assessment.md#13-why-there-is-no-quick-just-run-it-answer))?
- Where can a persistent patch live that does **not** modify `LOMAX.EXE`: a
  dropped-in `ddraw.dll`/`dsound.dll` proxy, a `LOADER` process, a Wine
  registry override, or an app-compatibility shim?

**Evidence that settles it.** A documented, reproducible injection recipe that
starts the stock binary under Wine, observes the DirectDraw surface creation,
and states exactly which call sequence a proxy must intercept — with the MFC
startup constraint written down.

**Decision it unblocks.** The mechanism for the open-source presenter (M2):
DLL proxy vs an app-level frame grabber, and whether the hook needs to wait for
the game's own thread to reach the entry point.

### WP-2 — Display path (`specialist`)

**Question set.**

- DirectDraw 7 → what can a `ddraw.dll` wrapper (DXVK-style) fix and what can it
  not fix — specifically the 8/16-bpp desktop gate and the missing 320x240
  exclusive mode ([`01-platform-assessment.md` §1.3](../research/01-platform-assessment.md#13-why-there-is-no-quick-just-run-it-answer))?
- Where does the **512 px ceiling** actually live in code: the fade surface
  whose width must be a multiple of 32, the 199 patched width sites, or both
  ([`02-resolution.md` §2.4](../research/02-resolution.md#24-layer-2--wider-framebuffer-how-wide-can-it-get))?
- Does the fade-surface constraint (multiple of 32) bite the **presenter** too,
  or only the widescreen renderer?
- Does the Direct3D 3 execute-buffer path (128-quad budget `[S2]`) matter for a
  presentation-only shim, or can we ignore it until the 2× render spike (M6)?

**Evidence that settles it.** A written analysis (facts citable from `Lomax+`,
code never) that names the exact functions/sites, plus a minimal probe that
demonstrates whether a proxy can present a 16-bit surface without the game
calling `SetVideoMode`.

**Decision it unblocks.** Whether the presenter is a full `ddraw.dll` shim or a
lighter "present at the last `Blt`" hook, and whether ultra-widescreen beyond
512 is a small patch or a rewrite (feeds M6's go/no-go).

### WP-3 — Asset pipeline (`scout`)

**Question set.**

- What is missing from [`file-formats.md`](../file-formats.md) before a 2×
  re-authoring of the art is possible: the `TTAB` tile→cell encoding, the `ANIM`
  record layout (payloads are not multiples of 0x38), the palette-per-tile
  question (Q8), and the `GNMY` type names?
- What does a byte-exact `read → write` round trip require beyond the confirmed
  chunk container (the `size & ~3` padding rule interacting with per-chunk
  padding — the LMX-5 falsifier)?
- What must never enter the repository (game bytes, `.WLD`, sprites, palettes)
  and what may be generated at run time (inventory counts, fixture graphs).

**Evidence that settles it.** A gap list for `file-formats.md` with each item
graded H/D and a note on how to verify it, plus a confirmed answer to Q8 if the
decoder exists by then.

**Decision it unblocks.** The scope of LMX-5/6/8/9: whether 2× art is even
representable in the container without changing the engine (it is — cells are
counted in bytes `[S2]`), and how much of the pipeline is distributable code vs
a user-side script.

### WP-4 — Runtime & distribution (`scout`)

**Question set.**

- Wine/Proton vs a native port vs a shim: what does a modern Linux user actually
  install, and which of the four blockers (colour-depth gate, missing 320x240
  mode, CD check, MFC startup order) survive under Wine/Proton with and without
  `dgVoodoo`/`DxWnd` (LMX-3)?
- What is the compat matrix (Wine version × DXVK × virtual desktop), and does
  Wine's own DirectDraw already present 16-bit surfaces well enough that only a
  filter pass is needed (the LMX-4 falsifier)?
- Packaging options for a shim (an AppImage/Flatpak/Lutris recipe that loads the
  user's own files), and whether CI can run any of this headless (it cannot run
  the game, but it can build and smoke-test the shim).

**Evidence that settles it.** A first-run recipe for at least one distro with
game SFX and no graphical corruption, plus the (stock game, wrapper, loader) ×
(Wine, DXVK, virtual desktop) matrix.

**Decision it unblocks.** The target host for M2, and whether the presenter must
also act as a `ddraw.dll` proxy under Wine or can be an app-level filter on top
of Wine's own presenter.

### WP-5 — Tooling debt (`builder`)

**Question set.** What must the existing read-only CLI gain before it can serve
the roadmap?

- `TTAB`/`CELL` decoding (16x16 tiles over 8x8 cells, big-endian words) so
  `measure` can report unique cells/tiles and answer Q8/Q9.
- A byte-exact `WLD` rebuild skeleton (the LMX-5 round-trip falsifier, one chunk
  at a time).
- A `password` command from the documented algorithm (LMX-7).
- `GNMY` index→name mapping against the NMY type table.

**Evidence that settles it.** Each addition lands with a synthetic-fixture test
(`tests/fixtures/synth.py`) and a negative test; the round-trip test passes
bytes-in == bytes-out on fixtures before any real file is touched.

**Decision it unblocks.** Whether the presenter (M2) and the 2× pipeline (M5/M6)
have the introspection tools they need, and whether the CLI can stay
dependency-free Python (it must — [`architecture.md` §5](../architecture.md#5-future-components-and-where-they-sit)).

### WP-6 — Synthesis (`lead`)

Runs after WP-1…WP-5. Merges their findings into
[`10-milestones.md`](10-milestones.md) and [`20-releases.md`](20-releases.md)
v1, resolves contradictions between packages, and records what is still unknown
in [`../research/05-open-questions.md`](../research/05-open-questions.md). It
does **not** start new research.

## 4. The strategy decision: three mechanisms, one winner

Where two strategies compete for how to reach the game's frame, we name the
winner now and re-open it only if M1's evidence contradicts it.

| Mechanism | Verdict | Why |
|---|---|---|
| **DLL proxy** (`ddraw.dll` shim, import-table hook) | **Winner** | Clean-room buildable from public DirectDraw API docs; does not modify `LOMAX.EXE`, so it is legal to distribute and version-independent; works under Wine/Proton and on Windows; can present the 16-bit frame without touching gameplay code. |
| **Binary patching** (hex-edit the exe, as the VOGONS patch does) | Loses | Modifies the user's executable in place (fragile across builds, awkward to distribute legally), and the known patch already regresses transparency ([`01-platform-assessment.md` §1.3](../research/01-platform-assessment.md#13-why-there-is-no-quick-just-run-it-answer)). Fine as a *documented fact*, not as our product. |
| **Reimplementation** (clean-room engine) | Loses (for now) | A full rewrite of a 2D engine is months of work for no user-visible delta over the existing loader, and it is exactly the scope-creep the product risk warns about ([`30-risks.md`](30-risks.md#product)). Revisit only if a source port becomes the only way to unlock true HD (M6) — and even then it is a spike, not a plan. |

The provisional decision is therefore: **M2 is a clean-room `ddraw.dll` proxy /
app-level presenter.** M1 confirms or refutes it; the refutation criterion is
written into the WP-1 and WP-2 acceptance below.

## 5. How the packages map to board cards

Each package WP-1…WP-5 is a child card on the `retrolab` board, assigned to the
profile named in its heading, with the `retro-game-modernization` skill
attached. WP-6 is one synthesis card assigned to `lead` with WP-1…WP-5 as
parents. Card ids are recorded in `10-milestones.md` and in the completion
metadata of the planning card (LMX-7).
