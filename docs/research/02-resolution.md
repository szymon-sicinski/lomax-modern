# 2. Resolution and display — what can actually be improved

*This is the main research deliverable. Citations `[S#]` resolve in
[`sources.md`](sources.md); arithmetic marked `[derived]` is reproducible with
the snippets at the end of this document.*

## 2.1 "Improve available resolutions" decomposes into three different problems

People say "resolution" about three unrelated things. Separating them is what
makes the question answerable:

| Layer | What changes | Player-visible effect | Touches gameplay code? |
|---|---|---|---|
| **L1 Presentation** | How the finished frame reaches the monitor | Sharper, correctly scaled picture; no shimmer; works on any screen | No |
| **L2 Framebuffer width** | How much of the world the 240-line frame contains | Widescreen: more level visible left/right | Camera/scroll only |
| **L3 Pixel density** | How many source pixels the art is made of | Genuinely higher-resolution art, not a stretched 320x240 image | No (render-only, if done right) |

Everything below follows that order, because cost and risk rise steeply from L1
to L3.

## 2.2 Baseline facts

1. **Internal resolution is 320x240**, written as instruction immediates; a
   widescreen patch has to rewrite **199 sites** of hard-coded width `[S2]`
   `[S3]`.
2. **Only 8 or 16 bpp** are supported; the game refuses to start otherwise
   `[S1]` `[S2]`.
3. **Art is palettised**: each world carries 10 palettes of 256 colours, built
   into `BITMAPINFO` blocks and blitted through GDI `StretchDIBits` `[S2]`.
   Index 0 becomes the transparent key — "white, with real white moved to
   0x7FFE" `[S2]`.
4. **Tiles are 16x16, assembled from 8x8 cells** (`TTAB` references `CELL`),
   and a plane can carry a zoom of 750 per-mille, i.e. 12x12 pre-shrunk tiles
   `[S2]`.
5. **Sprites are surfaces with a 0x38-byte `SpriteFrame` descriptor** (an
   in-memory struct `[S2]`; the `ANIM` *file-chunk* record framing is retracted —
   see `file-formats.md` §2.6), 256 banks per world, mirrored left/right through
   `DDBLTFX` blocks `[S2]`.
6. **The frame is presented with a DirectDraw `Blt` to the primary surface**;
   the Direct3D 3 path emits quads from a fixed 0x5624-byte execute buffer that
   has room for **128 quads** `[S2]`.
7. **Height is 240** and the documented camera logic is horizontal
   (`camera_x = player.x − W/2`) `[S3]`; the level grid is 15 tiles tall.
8. **A working loader already exists** that presents the game borderless, at up
   to 512x240, with 60+ FPS and a modern D3D11 presenter `[S3]` `[S5]` — and it
   is **unlicensed** (all rights reserved) `[S5]`, see
   [`03-prior-art.md`](03-prior-art.md).

## 2.3 Layer 1 — presentation: the cheapest real win

### What is broken today

- **Exclusive fullscreen is unreachable.** It requires a 320x240 8/16-bpp
  mode; modern DirectDraw enumerates 32-bpp modes only `[S3]`.
- **Windowed mode is gated** on an 8/16-bpp desktop `[S2]`.
- **The stock path is a 1:1 blit**, so the picture is either a postage stamp or
  stretched by the OS with no aspect correction.
- **Non-integer scaling shimmers.** At 1080p a 4:3 frame is 1440x1080, i.e.
  exactly 4.5x, so some source pixels must be 4 screen pixels wide and others 5
  — and those widths move as the camera scrolls `[S3]` `[derived]`.

### What is achievable without touching the engine

| Technique | Gain | Notes |
|---|---|---|
| Integer scaling with letterbox | Crisp pixels, no shimmer | Trivial; wastes screen area on 16:9 |
| Sharp/area-average hybrid scalar | Near-integer sharpness at any window size | Implemented in the prior art on CPU and in a shader `[S3]` |
| Pixel-art filters (xBRZ / MMPX / HQx) | Smoother cartoon edges, "remastered" feel | Not implemented anywhere for this game; opinionated look |
| CRT / LCD masks, scanline shaders | Period-correct look on flat panels | Cheap, complements the above |
| Per-monitor DPI, borderless window, multi-monitor | Usability, not quality | Prior art has borderless; DPI awareness is unaddressed |
| Frame-rate decoupling / VSync | Smoothness | Prior art has it; genuinely needs engine hooks for >60 FPS logic `[S3]` |

**Scaled sizes** `[derived]`: 4:3 content at 1080p = 1440x1080 (4.5x); at 1440p
= 1920x1440 (6x); at 4K = 2880x2160 (9x). 16:9 widescreen content (432x240) at
1080p = 1920x1066.

**Verdict.** L1 is where the visible improvement per hour of work is highest,
and it needs **no knowledge of game internals beyond "there is a 16-bit
framebuffer"**. The gap versus prior art is not quality but availability:
there is **no open-source presenter**, nothing that runs on Linux/Proton, and
no filter support. This is a viable, self-contained project.

## 2.4 Layer 2 — wider framebuffer: how wide can it get?

### Geometry

Width grows in 16-px tiles; height stays 240 (15 rows) `[S2]` `[S3]`.

| Width | Aspect | Tiles wide | Surface width (multiple of 32) `[derived]` | Verdict |
|---|---|---|---|---|
| 320 | 4:3 | 20 | 320 | original |
| 336 | 1.40 | 21 | 352 | negligible gain |
| 384 | 1.60 (16:10) | 24 | 384 | good compromise |
| 432 | 1.80 (16:9) | 27 | 448 | matches prior-art default `[S3]` |
| 448 | 1.87 | 28 | 448 | |
| 480 | 2.00 | 30 | 480 | |
| 512 | 2.13 | 32 | 512 | documented maximum `[S3]` |
| 560 | 2.33 (21:9) | 35 | 576 | outside the documented cap |
| 640 | 2.67 | 40 | 640 | far outside |

### The constraints behind the ceiling

1. **The fade transition forces the surface width up to a multiple of 32.**
   With a 432-px picture the loader allocates 448-px surfaces "multiple of 32
   for the dissolve-fade tiles" `[S3]` `[derived: ⌈432/32⌉·32 = 448]`. Any width
   must therefore be rounded up, which costs fill rate but not correctness.
2. **The camera clamp is level-data dependent.** Scroll limit is
   `(map_tiles − W/16) · 16` `[S3]`, so a wider view is only useful if the maps
   are wider than it. **16 of 104 maps are narrower than 27 tiles** `[S3]`.
   Below that, the prior art centres the map and paints black bars at the sides,
   with a hook that keeps player and HUD inside the visible region `[S3]`.
3. **Width is compiled into 199 instruction sites**, each verified by byte
   pattern before patching `[S3]`. Every extra width is the same table
   re-evaluated, so cost grows with *risk of a missed site*, not linearly with
   width.
4. **Demos pin the camera.** The 8 recorded attract demos replay input, so the
   logic must see the original camera while the renderer sees the wide one; the
   prior art implements exactly that and verifies tick-for-tick equality `[S3]`.
   Anything we build must pass the same test.

### Why the cap sits at 512

The published documentation states the maximum (512) but **not its cause**
`[S3]`. Candidates, in decreasing order of plausibility:

- a fixed-size fade buffer or blit count that assumes at most 32 tiles across
  (512/16 = 32 `[derived]`);
- a surface allocation or pitch assumption in `DDraw_InitSurfaces`;
- arithmetic in the 199-site formula table that was only verified up to 512.

Confirming this is a Phase 0 task for anyone who wants ultra-widescreen; it is
**not** needed to ship L1 or the asset pipeline.

### Why height cannot simply grow

`HEAD` stores width *and* height in 8-px units per world `[S2]`, so the
container can describe taller planes. But the picture, the level design and the
HUD are all 240 px, and the documented camera logic is horizontal only `[S3]`.
Growing height would reveal undesigned rows above/below the action and require
a vertical camera, new HUD anchoring, and re-checking every placement. Cost is
high and the visual gain is negative — the genre is a horizontal platformer.

### Verdict on L2

- **320 → 432** is proven and cheap *if you accept the prior art's approach*;
  we would be re-implementing 199 verified patches plus HUD/parallax/demo
  handling. Large, unglamorous, and already solved.
- **432 → 512** is the same table with more bar logic.
- **Beyond 512** is blocked by an unexplained ceiling: research-worthy, but it
  is a small win (2.13 → 2.33 aspect at best) for a lot of risk.
- **Height** is a dead end.

**Recommendation: do not pursue L2 as our core contribution.** Cite it,
interoperate with it, and revisit only if measurement shows the maps are wide
enough to make 640 worthwhile.

## 2.5 Layer 3 — higher pixel density: the real ceiling

### Why the art sets the limit

A higher-resolution framebuffer is useless with 320x240-era art: the sprites
and tiles would simply be upscaled by the engine instead of by the monitor.
True HD means **new source art**, which is why publishers called this
"remastering" rather than "patching".

What the engine already gives us `[S2]`:

- **Tile drawing is scale-aware.** Planes can carry a zoom (750 per-mille =
  12x12 tiles) and `TileLayer_Draw` places tile *k* at
  `floor(k · 16 · zoom / 1000) − scroll`. A 2x path is the same formula with
  zoom 2000.
- **Sprite drawing is scale-aware.** `Sprite_QueueWorldScaled`, rotated sprites
  and zoomed planes exist for camera zooms, and D3D quads are emitted with
  texture extents `(w−1)/T` `[S3]`.
- **Simulation is separate.** Collision is a byte per 16-px cell and actor
  positions are world pixels `[S2]`, so a 2x *render* does not disturb the
  *simulation* — no gameplay retuning, no physics regressions.

What stands in the way:

1. **Format.** `TTAB` tiles are 16x16 over 8x8 `CELL` cells `[S2]`; a 2x pack
   needs 32x32 tiles over 16x16 cells. `CELL`/`TTAB` payloads are counted in
   bytes, so the container can hold them, but the engine's blit sizes, tile
   strides and cell indexing are hard-coded alongside the 199 width sites.
2. **Sprites.** `SpriteFrame` is a 0x38-byte *in-memory* descriptor `[S2]` (the
   `ANIM` *file-chunk* record framing is retracted — see `file-formats.md` §2.6);
   2x art doubles pixel dimensions (a size field change, not a record-layout
   change), but every consumer that assumes "sprite is at most 64 px wide"
   (e.g. edge-extension logic in the presenter `[S3]`) must be re-derived.
3. **UI and fonts.** HUD glyphs, banners, the password screen and the menus are
   1x art; they need 2x equivalents or clean vector/text rendering.
4. **Presenter.** The fade system, the z-buffer/viewport and the 128-quad
   execute buffer `[S2]` all have to agree with the new frame size. The quad
   count does **not** grow (same object count), which is the one piece of good
   news.

### Art pipeline: the part that can live in Python

The palettised 8-bit format is both an obstacle and an opportunity:

- **Obstacle:** index 0 is the transparent key ("white, with real white moved
  to 0x7FFE") `[S2]`. A naive RGB upscaler bleeds the key colour into
  neighbours and produces white/black halos around every sprite.
- **Opportunity:** upscaling **in index space** preserves the palette exactly,
  so a 2x pack can stay 8-bit and keep the engine's colour handling unchanged.
  A matte-aware scaler (treat index 0 as alpha, upscale the colour plane and
  the coverage mask separately) is the correct approach and is pure Python/NumPy
  work.
- **Simplification:** all shipped tiles use palette 0 `[S2]`, so tile
  upscaling only has to respect one palette per world; sprites use the world
  palettes.

### Legal reality

Upscaled art is a derivative work of Psygnosis/Sony assets. **We can ship the
upscaler and the repacker; we cannot ship the output.** Distribution model:
a script that transforms *the user's own* `WORLDS/*.WLD` in place (with backup),
plus optionally a binary patch recipe. That is the same model as texture-pack
installers for other 1990s games.

### Staged plan with an explicit go/no-go

| Stage | Deliverable | Proof of success | Stop condition |
|---|---|---|---|
| L3.0 | `WLD` reader/rebuilder in Python, byte-exact round trip | Rebuilt file == original, and the game loads it | Layout assumptions fail on real files |
| L3.1 | Tile/sprite exporter (PNG + palette + mask) | A human recognises the exported art | Assets are not where documented |
| L3.2 | Matte-aware 2x/3x upscaler | Side-by-side sheets look clean, no halos | Art quality unacceptable at 2x |
| L3.3 | 2x pack writer + engine hook (render scale only) | Game runs at 640x480 internal with 2x art | Needs more than viewport/tile/sprite patching |

**L3.0–L3.2 are worth doing regardless of L3.3**: they are distributable,
testable without the game running, portfolio-grade, and they unblock level
editing, art replacement and translation projects.

## 2.6 Decision matrix

| Option | Visual gain | Effort | Risk | Distributable | Novelty vs prior art |
|---|---|---|---|---|---|
| L1a integer scaling | medium | low | low | yes | low (but open-source, Linux) |
| L1b pixel-art filters (xBRZ/MMPX) | medium-high | medium | low | yes | **high** |
| L1c DPI/multi-monitor polish | low | low | low | yes | medium |
| L2 widescreen 432/512 | medium | very high | high | yes | none (solved, unlicensed) |
| L2b ultra-widescreen >512 | low-medium | high | high | yes | medium (research) |
| L2c higher height | negative | high | high | yes | — |
| L3a `WLD` read/write + export | none directly | medium | medium | **yes** | **high** |
| L3b matte-aware upscaler + 2x pack | high (if art holds up) | high | medium | tools only | **high** |
| L3c 2x internal render hook | high | very high | high | yes | **high** |

## 2.7 Recommendation

1. **Now (this repository):** finish Phase 0 measurement (see 2.8) and publish
   the research. No engine work until the measurements are in.
2. **Next:** build **L1b + L3a** — an open-source presentation layer with
   filters, and a Python `WLD` toolkit with byte-exact round trip. These are
   independent, individually useful, and legally clean.
3. **Then:** L3.2 (upscaler) with a public go/no-go sheet comparing 2x and 3x
   output on representative tiles and sprites.
4. **Only if that lands:** L3c as a research spike. It is the only path to a
   genuinely higher-resolution Lomax, and it needs the loader-hook technique
   from the prior art (facts citable, code not) plus a renderer rewrite.

Explicitly **not** planned: competing with the existing loader on widescreen,
frame rate, controller or CD handling. That work exists, it is unlicensed, and
duplicating it would cost months for no user-visible delta.

## 2.8 Phase 0 measurements (run against your own files)

```bash
# 1. Confirm the install and record local hashes (never commit the output)
lomax-modern doctor "/path/to/Lomax"

# 2. Confirm the chunk layout hypothesis on every world file
for f in "/path/to/Lomax"/WORLDS/*.WLD; do lomax-modern wldscan "$f"; done

# 3. Once the layout is confirmed, harvest the numbers that decide L2/L3:
#    - map width histogram (tiles) over all 104 sub-levels -> useful max width
#    - how many maps are wider than 32 tiles (i.e. would benefit from 640)
#    - how many distinct palettes are actually used by tiles and by sprites
#    - total unique cells/tiles/sprites to size the upscaling job
LOMAX_GAME_DIR=/path/to/Lomax python -m pytest tests -m realgame -s
```

The widescreen ceiling question (2.4) and the map-width histogram are the two
facts that could change this plan; both need real files and neither is
answerable from public documentation.

## 2.9 Reproducing the arithmetic

```python
def fade_surface(w: int) -> int:      # multiple of 32, as the loader allocates
    return -(-w // 32) * 32

for w in (320, 336, 384, 432, 448, 480, 512, 560, 640):
    print(w, w / 240, w // 16, fade_surface(w))
# scale factors for common displays
print(1440 / 320, 2160 / 240, 1920 / 432)   # 4.5, 9.0, 4.44
```
