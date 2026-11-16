# 4. Improvement backlog

Ranked, evidence-linked, with an explicit "done" criterion for each item.
Effort is in relative units (S = days, M = weeks, L = months of part-time work).
"Licence-safe" means: may we ship everything this item produces?

## P0 — measurement and research (this repository, no game code)

### LMX-1 — Confirm the `.WLD` chunk layout on real files
- **Why:** every format claim in `docs/file-formats.md` is currently a
  hypothesis. The scanner in `src/lomax_modern/wldscan.py` deliberately refuses
  to decode payloads until the chain is confirmed.
- **Deliverable:** a one-page report with the layout of every shipped `WORLDS`
  file, including whether sizes are payload-only or header-inclusive, and the
  endianness of each field.
- **Evidence:** `[S2]` chunk order; `[S2]` "every size must be a multiple of 4".
- **Effort:** S · **Risk:** low · **Licence-safe:** yes (offsets only).
- **Done when:** `wldscan` reports `confidence: confirmed-chain` on all world
  files and the observed tag order matches `WRLD, NMY, HEAD, TTAB, MAP, GNMY,
  ANIM, CELL, END`.
- **Tool:** `lomax-modern measure <game_dir>` (or `scripts/measure_worlds.py`)
  reports the sequence, chunk counts and the HEAD endianness vote in one run.
  It encodes the documented layout as a *hypothesis* and labels it as such
  until real files confirm it.

### LMX-2 — Map-width histogram and the widescreen ceiling
- **Why:** decides whether anything beyond 512x240 is worth pursuing (see
  [02-resolution.md §2.4](02-resolution.md#24-layer-2--wider-framebuffer-how-wide-can-it-get)).
  The only public number is "16 of 104 maps are narrower than 27 tiles" `[S3]`.
- **Deliverable:** histogram of map widths in tiles, count of maps wider than
  32 tiles, list of the single-screen areas.
- **Effort:** S (after LMX-1) · **Risk:** low · **Licence-safe:** yes.
- **Done when:** a table of all 104 maps with widths is in
  `docs/research/measurements.md`.
- **Tool:** the same `measure` run prints the plane-width histogram (px and
  tiles) across every section of every world, which is that table.

### LMX-3 — Linux/Wine feasibility report
- **Why:** the existing loader is Windows-only `[S3]` `[S5]`; nobody has
  documented what the stock game, `DxWnd`, `dgVoodoo` or the loader actually do
  under Proton/Wine, nor which of the four blockers survive there.
- **Deliverable:** a matrix of (stock game, wrapper, loader) × (Wine version,
  DXVK, virtual desktop) with what fails and why; no binaries redistributed.
- **Effort:** M · **Risk:** medium · **Licence-safe:** yes (prose only).
- **Done when:** a first-run recipe exists for at least one Linux distro with
  audio (game SFX at minimum) and no graphical corruption.

## P1 — distributable tooling (open-source, legal, self-contained)

### LMX-4 — Open-source presentation layer with pixel-art filters
- **Why:** the only genuinely *missing* display feature. Integer scaling,
  xBRZ/MMPX/HQx, CRT masks, per-monitor DPI, and Linux support — none of which
  the prior art offers, and all of which need nothing but a 16-bit framebuffer.
- **Deliverable:** a `ddraw.dll`-style shim or an app-level presenter that
  takes the 16-bit frame and outputs a filtered, correctly scaled image.
- **Effort:** M–L · **Risk:** medium (DLL shims are fragile under Wine).
- **Licence-safe:** yes, if written from scratch (no `Lomax+` code).
- **Done when:** the stock game plus shim runs borderless at 4K with selectable
  filter, and the same build runs on Linux under Proton.
- **Depends on:** LMX-3 (to know which host path is viable).

### LMX-5 — `WLD` read/write toolkit with byte-exact round trip
- **Why:** the prerequisite for every content project (art packs, levels,
  translations) and the piece that can be tested without running the game.
- **Deliverable:** `lomax_modern.wld` — chunk container, `HEAD` header,
  `TTAB`/`MAP`/`CELL` readers, `ANIM` sprite table, plus a rebuild that is
  byte-identical before any edit.
- **Effort:** M · **Risk:** medium · **Licence-safe:** yes (code only).
- **Done when:** `read → write` reproduces every shipped world file bit for bit
  and the game loads the rebuilt file.

### LMX-6 — Tile/sprite exporter and asset inventory
- **Why:** you cannot judge "can this art be upscaled?" without looking at it,
  and modders need an export path that is not a screenshot.
- **Deliverable:** PNG export of cells, tiles and sprite frames, with palette,
  transparency mask and usage counts; an inventory of unique assets.
- **Effort:** M · **Risk:** low-medium · **Licence-safe:** the tool yes; the
  exported art may not be redistributed.
- **Done when:** a tile sheet and a sprite sheet for one world are recognisable
  and the inventory totals match the chunk sizes.

### LMX-7 — Password system reimplementation
- **Why:** the game has no save files, only passwords `[S1]` `[S2]`, and the two
  existing generators are unlicensed.
- **Deliverable:** encode/decode per the documented layout (XOR with 0xB7A4,
  5-bit section, 5-bit lives, 2-bit continues, 4-bit checksum) `[S2]`, with
  tests; CLI `lomax-modern password`.
- **Effort:** S · **Risk:** low · **Licence-safe:** yes (algorithm from
  documented facts).
- **Done when:** round-trip tests pass and one generated password is verified in
  the real game.

## P2 — content pipeline (go/no-go research)

### LMX-8 — Matte-aware upscaler (2x, optionally 3x/4x)
- **Why:** index 0 is the transparent key with real white moved to 0x7FFE `[S2]`;
  naive upscalers produce halos. Upscaling in index space keeps the game's
  palette handling untouched.
- **Deliverable:** scaler that treats index 0 as alpha, upscales colour and
  coverage separately, and emits 8-bit indexed output with the original palette.
- **Effort:** M · **Risk:** low (pure data work) · **Licence-safe:** tool yes,
  output no.
- **Done when:** comparison sheets at 2x show no key-colour bleed and no broken
  transparency, judged on at least 20 representative tiles and 10 sprites.

### LMX-9 — 2x asset pack writer
- **Why:** turns LMX-8 output into something the engine can consume.
- **Deliverable:** writer for doubled `CELL`/`TTAB`/sprite payloads plus a
  backup/restore path; refuses to touch a file it cannot round-trip.
- **Effort:** M · **Risk:** medium · **Licence-safe:** yes (transforms the
  user's own files in place).
- **Done when:** the game starts with a 2x pack installed and at least one
  level renders without visual artefacts.

## P3 — engine research spike

### LMX-10 — 2x internal render (640x480) proof of concept
- **Why:** the only route to genuinely higher resolution. Enabled by the fact
  that tile and sprite drawing are already scale-aware and the simulation lives
  on a 16-px grid `[S2]`.
- **Deliverable:** an in-memory patch that (a) changes the framebuffer to
  640x480, (b) rewrites the tile/sprite blit sizes, (c) keeps the logic at 1x.
- **Effort:** L · **Risk:** high (199 width sites, fade system, z-buffer,
  viewport, UI art at 1x will look wrong) · **Licence-safe:** yes if clean-room.
- **Done when:** one level renders at 640x480 with 2x art, the attract demos
  still replay identically, and the failure modes are written down.
- **Kill criterion:** if it needs more than viewport + tile + sprite + fade
  patching, stop and publish the findings instead.

## P4 — long term

### LMX-11 — Level editor
Builds directly on LMX-5/6. The map, collision bytes and `GNMY` placement format
are documented `[S2]`, so a tile/placement editor is a data problem, not a
binary problem. Needs a rendering preview and validation rules (start/exit
trapdoors, finish).

### LMX-12 — Translation support
`GAME.TXT` holds localised text with `@`, `#`, `&` markers `[S2]`, and the
console language-select screen still exists in the PC build `[S2]`. Mostly a
font/encoding and layout problem.

## Non-goals

- **Widescreen re-implementation.** Solved by unlicensed prior art; duplicating
  it costs months and adds nothing.
- **CD-check bypass, disc installers, or EXE patchers.** Legally and ethically
  out of scope; document, do not ship.
- **Redistributing any upscaled art, extracted audio or level data.**
- **Frame-rate/controller/audio fix re-implementation.** Same reasoning as
  widescreen; recommend the existing loader in the README instead.
