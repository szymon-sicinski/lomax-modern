# 44. Window presenter — options, effort and the spike that settles it

[`43-demo-plan.md`](43-demo-plan.md) refuses to price demo option **C** (playable
demo) because its presentation half has no measured basis: today `present`
renders a frame and writes a PNG, and [`../architecture.md`](../architecture.md)
§5 marks the Win32/C presenter as "future" without saying what it would take.
This note replaces that blank with a scoped, optioned estimate of **the window
only** — not menus, not audio sync, not the controller (that is M5) — so `lead`
can cost C's presentation half honestly in the successor card.

Every performance claim is graded **V** (measured in this repo or in this
session), **D** (documented upstream) or **H** (hypothesis, unmeasured). Every
effort figure traces to the measured per-card unit in
[`41-measured-cost.md`](41-measured-cost.md) (§3 of the demo plan): **~42.0 k
output tokens / ~102 k fresh input / ~3.72 M cached input / ≈$0.165 per card
off-peak**, and the wall-clock bands from §3.1 (specialist 13–25 min, reviewer
5.5–7.5 min).

## 0. What "a window" has to do, at minimum

1. Open a window at a chosen surface size — 1920×1080 (modern profile) or
   320×240 (authentic), the same surfaces `config.py` already defines.
2. Blit a 16-bit `B5G6R5` framebuffer at 60 Hz.
3. Accept a quit event (window close, and keyboard Esc once input exists).
4. Scale with integer fit + letterbox — reuse the already-pure
   `scaler.fit_scale` geometry, never a fractional stretch.

**Explicitly out of scope for the window:** menus, audio sync, and the
controller/input path (M5). A window that does only the four items above is an
*animated* picture, not a *playable* demo; §3 says what has to be added on top
and which of that is engine/input work rather than presentation work.

Three facts fix the frame budget before any option is compared:

| fact | value | grade |
|---|---|---|
| source frame | 320×240, one `u16` per pixel (`B5G6R5`) = 76,800 px × 2 B = **153,600 B (150 KiB)** | V — `engine/render.py` `VIEWPORT_*` constants |
| frame throughput at 60 Hz | 150 KiB × 60 = **8.79 MiB/s** | derived from the above |
| 60 Hz frame budget | 1000 ms ÷ 60 = **16.67 ms/frame** | derived |
| Python scaler, `nearest` 4× | **~40 ms** (≈ 25 fps) | V — `scaler.py` module docstring, CPython 3.14 |
| Python scaler, `epx_aa` 4× | **~150 ms** (≈ 6.7 fps) | V — same source |
| SDL2 software-renderer blit, 320×240 → 1080p surface | **1.18 ms/frame, 847 fps** (≈14× headroom) | V — spike run on this machine, below |

The rows that do the work are the last three, and together they say one thing:
**the Python scaler is the bottleneck, not the blit.** 40 ms / 150 ms are both
above the 16.67 ms budget, so the window cannot run `scaler.py` per frame. The scaling must be either
SDL2-native (nearest/hardware) or a C port of the filter — never the Python
oracle, which exists to *grade* the result, not to render it live. The blit
itself is cheap, so the language of the blit (Python via ctypes vs C) is not
what the 60 Hz question turns on; the *scaling* is.

The engine→presenter seam already exists: `engine.run.run_slice` accepts an
`on_frame(tick_index, frame)` sink called after every 60 Hz tick (V —
`engine/run.py`). A window is that sink plus a real-time pacing loop and an
event poll; no engine change is needed to feed it.

## 1. The option table

Standing preference: **no third-party Python dependencies** (`pyproject.toml`
`dependencies = []`). Every option below keeps that list empty; what differs is
the *system* requirement at runtime, and where each option bends that rule is
called out.

### 1.1 ctypes + SDL2 (system library) — **default candidate**

| axis | value |
|---|---|
| Python dependency | none (`ctypes` is stdlib); `dependencies = []` unchanged |
| system requirement | `libSDL2-2.0.so.0` (Linux), SDL2.framework (macOS), SDL2.dll (Windows) |
| platforms | Linux / macOS / Windows |
| effort | **3 cards** (2 specialist + 1 reviewer); **+1 specialist card** for `epx-aa` parity (§1.1.1) |
| money | **≈$0.50** (3 cards) to **≈$0.66** (4 cards) off-peak |
| wall-clock | **0.53–0.96 h** (3 cards) to **0.74–1.38 h** (4 cards) |
| risk | low–medium |
| roadmap cost | minimal — this is the eventual real presenter's target anyway |

What the 3 cards are:

1. **specialist** — the SDL2 binding: open a window, create a renderer and a
   `SDL_PIXELFORMAT_RGB565` texture, upload one frame, `SDL_RenderCopy` to the
   letterboxed destination rect, poll the quit event. Integer fit + letterbox
   geometry reuses `scaler.fit_scale` (already pure and unit-tested); the
   scaling itself is SDL2-native nearest (`SDL_HINT_RENDER_SCALE_QUALITY`),
   which for an integer factor is exact block replication by construction. The
   binding is tested headless with `SDL_VIDEODRIVER=dummy`, so CI needs no
   display.
2. **specialist** — the `lomax-modern window` command: wire `run_slice`'s
   `on_frame` sink to the window, add real-time pacing (sleep to 16.67 ms) and
   the event loop, and add the missing-library fallback (§1.1.2). Unit tests on
   synthetic fixtures; no game data.
3. **reviewer** — review the PR.

**1.1.2 What breaks when SDL2 is absent.** The only open question the default
candidate leaves: `ctypes.util.find_library("SDL2")` returns `None`, and the
command must print a one-line "install libsdl2" message and exit cleanly — no
traceback.

Distribution does not make this a non-issue today, and this note must not lean on
it: `pyproject.toml` builds a plain setuptools wheel with `dependencies = []` and
no frozen-exe recipe, so **there is no Windows package** — the alpha installs with
pip (**V** — this tree). Were one built later, it *would* ship `SDL2.dll` beside
the executable, which the zlib licence permits (**D** for the licence, **H** for
the packaging, which does not exist yet). Likewise a Steam-bundled SDL2 belongs to
the Steam runtime, not to a system `libSDL2-2.0.so.0` that
`ctypes.util.find_library` resolves from a non-Steam process, so it cannot be
counted as coverage.

What that means for the estimate: the missing-library path stays a real
requirement — a one-line "install libsdl2" message and a clean exit — and it is
carried in card 2 rather than being assumed away. It is small, but it is work, not
a risk that distribution already removed.

The remaining unmeasured claim is the ctypes marshalling cost: one
`SDL_UpdateTexture` of a 150 KiB frame per tick. It is a single call with an
SDL-side copy, so the expectation is microseconds (**H**); §2's follow-up spike
is what turns that H into a V.

**1.1.1 The `epx-aa` question.** The modern profile's filter is `epx-aa`
(`config.py`), and the Python `epx_aa` is the 150 ms one. SDL2 cannot reproduce
it natively (its filters are nearest/linear), so an in-window modern profile
with the shipped look needs `epx_aa` + `_blend565` ported to C (the same
bit-for-bit port discipline already used for `native/renderer.c`), golden-tested
against `scaler.py`. That is the **+1 specialist card**. The alternative — ship
the window with nearest for both profiles and keep `epx_aa` for the recorded/PNG
path — is an honest first cut (nearest is shimmer-free at integer factors, which
is the property that actually matters), and it is a decision for `lead`, not one
this note makes silently.

### 1.2 tkinter / PhotoImage — **reject**

| axis | value |
|---|---|
| Python dependency | none in `pyproject`, but **tkinter is not actually bundled** |
| system requirement | a `python3-tk`-class distro package on Linux; absent from many builds |
| platforms | wherever Tk is installed |
| effort | 3–4 cards **plus a viability spike**, and it probably loses the spike |
| risk | high — unmeasured ceiling, and Tk owns the event loop |
| roadmap cost | a dead end if it cannot reach 60 Hz, which it has no evidence of reaching |

Two claims people reach for are both false here:

- **"tkinter ships with CPython"** — no. It is an optional build-time component;
  on Debian/Ubuntu/Fedora it is a *separate* package, and it is **not present in
  this sandbox** (V: `ModuleNotFoundError: No module named 'tkinter'`, CPython
  3.14.10). It is the same *class* of system requirement as SDL2, but without
  any performance headroom to justify it.
- **"a 1920×1080 60 Hz blit is viable"** — no measured number exists (**H**).
  The discouraging floor is this repo's own measured pure-Python scaler
  (40 ms / 150 ms, V): `PhotoImage.put` copies 76,800 pixels through Python per
  frame, and Tk's integer `zoom()` is a different, equally unmeasured path. To
  recommend tkinter at all we would first have to *spend* a spike proving it can
  beat 16.67 ms — and if it cannot, the fallback is SDL2 anyway.

There is a second, architectural objection: Tk owns the main loop
(`mainloop()`), which collides with the engine's fixed 60 Hz tick. You either
drive the tick from Tk `after()` callbacks (timer jitter) or run the tick in a
thread (GIL contention). SDL2 has the same ownership question answered by its
`SDL_PollEvent` model, which is built for exactly this loop.

### 1.3 X11/Wayland directly via ctypes — **reject now**

| axis | value |
|---|---|
| Python dependency | none |
| system requirement | none (X11 is a socket protocol) — but you re-implement it |
| platforms | **Linux only** |
| effort | 4–6 cards (two backends, or drop one) |
| risk | high |
| roadmap cost | a Linux-only dead end for a cross-platform project |

"No dependency" here means "implement the client by hand": `XPutImage`/XShm
over the X11 wire protocol, and then Wayland is a *different* protocol where an
arbitrary client cannot blit at all without a `wl_shm` compositor surface. Two
backends, one of them genuinely hard, re-implementing what SDL2 already does —
worse. Justify it only if SDL2 turns out to be unavailable where it matters; it
is not (V: `libSDL2-2.0.so.0` present here, and ubiquitous on desktop Linux).

### 1.4 A separate C presenter reusing `native/renderer.c` — **defer**

| axis | value |
|---|---|
| Python dependency | none |
| system requirement | a C toolchain + SDL2 at build/install time |
| platforms | Linux / macOS / Windows |
| effort | 4–6 cards (fork + IPC + scaling port + build) |
| risk | medium–high |
| roadmap cost | this **is** the long-term destination, but not for the demo |

The honest scoping of "reuse": `native/renderer.c` is 80 lines of palette/blit/
fade (V) — it has **no window, no scaling, no event loop**. The presenter's real
surface area (window, integer scaling, event loop, pacing) is all new C anyway,
so the reuse saves only the blit, which the spike shows is *not* the expensive
part. The actual cost is the **fork**: the engine is Python (M3), so a C
presenter means either a C process fed frames over IPC (a 150 KiB-per-tick
serialization + sync design) or porting the engine to C too (M-scale, out of
scope). The blit is language-independent (V — the spike measures the blit, not
the caller); the fork is what you would be paying for, and the demo does not
need it.

The C presenter is the right answer *later* — `architecture.md` §5 already says
the presenter is C in `native/`, and a ctypes+SDL2 window swaps for it cleanly
whenever the engine itself moves to C (same geometry, same frame format). It is
the destination, not the first step.

### 1.5 Summary

| option | cards | money | risk | verdict |
|---|---:|---:|---|---|
| ctypes + SDL2 | 3 (4 with `epx-aa`) | ≈$0.50 (≈$0.66) | low–medium | **default** |
| tkinter / PhotoImage | 3–4 + spike | ≈$0.50–$0.66 + wasted spike | high | reject |
| X11/Wayland via ctypes | 4–6 | ≈$0.66–$0.99 | high | reject now |
| separate C presenter | 4–6 | ≈$0.66–$0.99 | medium–high | defer (later destination) |

## 2. The measurement that settles it

**Already run** (V — operator's assistant, this machine): SDL2 2.32.74, software
renderer, `SDL_VIDEODRIVER=dummy`, 600 frames of 16-bit `RGB565` 320×240 scaled
to 1280×960 content in a 1920×1080 surface:

```
frames: 600  total: 0.708 s  per frame: 1.180 ms  fps: 847.2
budget at 60 Hz: 16.67 ms/frame -> HEADROOM
```

That settles "can SDL2 blit this at 60 Hz from Python" — **yes**, with ~14×
headroom, so `ctypes` overhead is irrelevant next to 1.18 ms. It *eliminates*
the performance objection to SDL2 and sets the bar tkinter has to beat (it has
no number). It does **not** measure: a real display present path (the dummy
driver never presents), GPU scaling, vsync, or input latency. Those need a real
X/Wayland session.

**The one spike still worth a card** (throwaway script, ≤1 card, do not ship):
the same SDL2-in-ctypes path with `SDL_VIDEODRIVER=x11` (then `wayland`), 600
frames, timing three things separately — (a) the ctypes `SDL_UpdateTexture`
upload of 150 KiB, (b) `SDL_RenderCopy` + `SDL_RenderPresent`, (c) end-to-end
frame time. The results eliminate options:

- end-to-end > 16.67 ms → SDL2's software renderer is not enough; escalate to
  the accelerated renderer or the C presenter;
- upload alone > ~5 ms → the Python↔C boundary is the bottleneck, and the C
  presenter (or a single-memcpy path) becomes necessary;
- both comfortably under budget (expected: upload µs–sub-ms **H**, blit 1.18 ms
  **V**) → ctypes+SDL2 is confirmed, tkinter is dead, and only the missing-lib
  message and the `epx-aa` parity question remain open.

## 3. What the window does to the demo's honesty

C is marketed as *the game*, so a window that shows a static slice is worse than
no window: it provokes "is it even running?" rather than "it's coming back". To
qualify as a *playable* demo the window must additionally prove three things,
and only one of them is presentation work:

1. **Motion** — the player visibly walks and jumps in real time. The motion is
   *engine* work already done: `run_slice` drives a fixed 60 Hz tick with a
   scripted walk-right/jump input (V — `engine/run.py`). The window just has to
   drive that tick live instead of run-to-completion — presentation wiring, not
   new engine code. But for the motion to *look like the game* it needs the
   tile-art blit composed on the map, which depends on the map→tile link (Q20 —
   resolved by sibling `t_830f4d0d`, port into `art.py`/`renderer.py` filed as
   its own card, not yet in `main`).
2. **Collision visibly working** — the player lands on platforms, does not fall
   through. That is engine work (M3's `CollisionModel`, the 0-vs-non-zero
   hypothesis) and is done; until the tile art is composed it renders as flat
   coloured rectangles rather than the game's platforms.
3. **Input** — to be *playable* rather than a movie, the player must be
   steerable. That is M5 (keyboard → `Input`), explicitly out of scope here.
   Without it the window shows an *animated* slice, not a *playable* demo.

The partition this note hands to `lead`:

| half | what | whose card |
|---|---|---|
| **presentation** | window, blit, quit, scale, letterbox, 60 Hz pacing, live tick | this note: 3–4 cards |
| **engine** | tile-art composition (Q20 port), spawn/collect/exit/next-level (GNMY), collision semantics (Q31) | `t_830f4d0d` (filed port) + `t_050db875` (GNMY) |
| **input** | keyboard → `Input` | M5 |

The honest statement: a window turns the PNG into a live picture for ~$0.50–$0.66;
"playable" *additionally* requires M5 input and the engine-loop completion, and
those are engine/input work, not presentation work. The window is the cheapest
third of "playable" and the only third this note costs.

## 4. Recommendation (for the successor card)

Ship **ctypes + SDL2** as the window presenter. Cost the presentation half at
**3 cards / ≈$0.50** (nearest scaling for both profiles) or **4 cards /
≈$0.66** (with the `epx_aa` C port so the modern profile's filter is honoured
in-window). The remaining open items are the missing-library fallback message
(inside card 2) and the one follow-up spike in §2 that turns the ctypes-upload
hypothesis into a measurement. Every other option either has no measured 60 Hz
path (tkinter), is a Linux-only dead end (X11/Wayland), or forks the runtime for
a demo that does not need it yet (C presenter).

## 5. Reproduce

- **Frame sizes and the Python-scaler numbers:** `src/lomax_modern/engine/render.py`
  (`VIEWPORT_WIDTH`/`HEIGHT`) and the `scaler.py` module docstring.
- **The blit spike:** run by the operator's assistant on this machine; quoted in
  §2 and in the task comment thread. Not committed — it is a throwaway, and the
  numbers above are the record.
- **Per-card unit:** `python3 scripts/token_cost_report.py --board retrolab --json`
  (host), as in `41-measured-cost.md` / `43-demo-plan.md` §3.
