# File formats — what is known, and how much to trust it

**Confidence legend**

- **V** — verified against the retail PC install: a measurement, with the
  command recorded in
  [`research/06-measurements-and-improvements.md`](research/06-measurements-and-improvements.md)
  (2026-11-16), in the LMX-7 reports of 2026-11-17
  ([`research/07-wp3-asset-pipeline.md`](research/07-wp3-asset-pipeline.md),
  [`research/07-wp1-patching-surface.md`](research/07-wp1-patching-surface.md),
  [`research/07-wp4-runtime-distribution.md`](research/07-wp4-runtime-distribution.md)),
  or in the LMX-11 static-analysis pass of 2026-11-18 (the `ANIM`/`NMY`/`GNMY`
  readers in `LOMAX.EXE`, §2.5/§2.6, validated with
  `lomax-modern anim-nmy`), or in the tile-pipeline pass of 2026-11-18 (the
  `HEAD`/`CELL`/`MAP`/`TTAB` readers and the flag-consuming tile-cache builder
  in `LOMAX.EXE`, §2.4/§2.8, validated with `lomax-modern probe-tiles`).
- **D** — documented by a third party `[S2]` `[S3]`, not verified here.
- **H** — hypothesis in this repository, untested against a real file.
- **retracted** — stated here previously and contradicted by measurement. The
  sentence says what was measured instead and links the measurement.

No game data is stored in this repository. Everything below is a description of
a format, not a copy of it.

## 1. Install layout

A `SETUP.EXE` install writes 110 files, ~12 MB `[S3]` `[V: measured]`:

```
LOMAX.EXE        the game (PE32, MFC 4.2, DirectDraw 7, Direct3D 3)
GAME.TXT         localised text, @ # & markers                        [D]
LOMAX.HLP/.CNT/.GID   Windows help
WORLDS/          *.WLD world files (levels, tiles, sprites)
SFX/             sound effects (WAV)
DEMOS/           DEMOxxNy.DAT input recordings                       [D]
JINGLES/         short music stingers
AMBIENT/         ambient loops
MUSIC/           on the CD only: *.DAT pointers into CD-DA tracks    [D]
```

The disc also holds `DIRECTX/` (DirectX 3 setup), `SETUP.EXE`, `REMLOMAX.EXE`,
`AUTORUN.INF`, `LOMAX.ICO` and `BLANK.BIN` padding `[S3]`.

## 2. `WORLDS/*.WLD` — the world container

### 2.1 Chunk sequence **[V]**

Measured in all 9 retail world files (chunk counts across the set in
parentheses):

```
WRLD  ("PS-X" magic, 1234 little-endian)                                   (9)
NMY   object types and animations                                         (9)
PARA  parallax type names ("Parallax", "ScrollMap", ...)                   (9)
(HEAD, TTAB, MAP, GNMY) repeated once per plane                        (104 each)
MACR                                                                       (7)
PAGE                                                                       (7)
CELL  8x8 cell pixels                                                      (9)
ANIM  sprite frames, many small chunks per file                          (566)
END                                                                        (9)
```

`PARA`, `MACR` and `PAGE` are **not** in the loader's documented list `[S2]`
but occur in every retail file, so they are accepted by the scanner.

World files in the PC build: `BONUS`, `ED`, `HAUNTED`, `MAIN`, `MAP`,
`MEDIEVAL`, `TITLE`, `VILLAGE`, `WEST` **[V]** (`LOGO` is listed in the
executable but not shipped `[S2]`).

### 2.2 Chunk header **[V]**

- A 4-byte tag field, **space-padded** for 3-letter tags: `NMY ` and `END ` were
  observed verbatim, `WRLD` is unpadded.
- A **big-endian** `u32` payload size; the size is payload-only.
- Sizes are multiples of 4, consistent with `File_ReadChunk` advancing by
  `size & ~3` `[S2]`. The pad sits **inside** the declared size, so the rule
  never fires on retail data: 1,041/1,041 chunks are already 4-aligned, and the
  `MAP` payloads that need padding are padded within their declared size
  **[V]** (`research/07-wp3-asset-pipeline.md` G14). A writer must therefore pad
  to 4 and include the pad in the size; a reader must not assume the pad is
  absent.

All 9 files parse as a chain that reaches EOF (`wldscan`: `confirmed-chain`,
`layout=tag+size u32be (payload)`).

### 2.3 `HEAD` **[V]**

- `u32` width and `u32` height in **8-pixel units**, big-endian. Verified on
  104/104 planes by cross-checking the sibling `MAP` (§2.4); the little-endian
  reading fails for all of them.
- Payload size is constant: **5,240 bytes (0x1478)**.
- 10 palettes × 256 colours, little-endian, 15-bit (blue bits 0–4, red bits
  10–14) `[D]`.
- 0x50 bytes of editor data (0xFF filler) `[D]`.
- A 256-bit ANIM bitmap at +0x1458 `[D]` — arithmetic confirms it:
  0x1458 + 32 = 0x1478, the measured payload size.
- Colour 0 becomes the transparent key: white, with real white moved to 0x7FFE
  `[D]`.

Plane sizes are **not** bounded by the screen: measured widths 320–7,200 px and
heights 240–2,928 px. Heights 240 and 256 both occur (the 256-line ones are the
PS1 PAL layout leftovers `[S2]`).

Only HEADs whose plane bit is in the active plane mask load palettes; every
plane's tiles are built from the last palettes loaded, and all shipped tiles use
palette 0 `[D]` (unverified — Q8).

### 2.4 `TTAB`, `MAP`, `CELL` — the tile pipeline

Recovered by static analysis of the readers in `LOMAX.EXE` (§2.8) and validated
against all 9 retail world files with `lomax-modern probe-tiles` (2026-11-18).
This subsection closes Q20/Q21/Q22 and opened Q33 (the flip *pairing*, which no
measurement settles); Q33 was closed later by the copy-loop reading in §2.8
(FL2). Every count below is reproduced by that command.

- **`MAP` [V]**: `N` big-endian `u16` tile words, then `N` collision bytes,
  padded with 0–3 zero bytes to a multiple of 4. `N` is the plane's 16x16-cell
  count from the sibling `HEAD` (§2.3). The loader byte-swaps exactly the `2·N`
  word bytes in place (the preprocessor at VA `0x415430`) and keeps the `N`
  collision bytes at `map + 2·N`. Measured: **523,229 map words across 104
  planes, 1,476 distinct, max 1,475**. The earlier "3 bytes per cell,
  word+collision interleaved" reading is **retracted**: its `size − 3·cells`
  arithmetic still holds, but its byte order is wrong — under it 51,381 of
  523,229 words fall outside the plane's `TTAB` bank, against **0** for the
  split reading.
- **`MAP` word → `TTAB` record [V, Q20]**: the map word is a **direct index**
  into the plane's `TTAB` record array. Every one of the 523,229 map words
  resolves to an in-range record (0 out-of-bank, 104/104 planes). The tile
  count per plane is `TTAB` payload size ÷ 16 (the `TTAB` reader stores
  `size >> 4` at plane `+0x2C`).
- **`TTAB` [V]**: 16-byte records = eight big-endian `u16` words = four cells,
  each a `[index word, flag word]` pair. **37,561 records = 150,244 cells**
  across the 9 files (the earlier "75,122 records" was the same data read as
  8-byte records — 300,488 words ÷ 4 — a self-consistent but wrong framing).
  - *Index word*: a full 16-bit `CELL` index. 0/150,244 are out of bank;
    4,909 distinct (max 4,908). The blit resolves `CELL_base + index·64` with
    no mask (§2.8).
  - *Flag word*: bits 13–14 are the flip pair, bits 8–11 the palette index;
    bits 0–7/12/15 are never set (0/150,244).
- **`TTAB` flip bits [V, Q21]**: bits 13–14 of the flag word are the flip pair.
  Exactly three combinations occur across the 150,244 retail cells — `0x2000` on
  15,787, `0x4000` on 1,783, `0x6000` on 716, none on 131,958 — and every other
  high bit is zero. The tile-cache builder dispatches on `flags & 0x6000` into
  four distinct copy loops (§2.8). (The earlier "range" of 15,787–16,503 /
  1,783–2,499 came from two runs counting different units; the per-*flag-word*
  counts above are authoritative — Q27.)
  **`0x2000` = horizontal mirror, `0x4000` = vertical mirror, `0x6000` = both
  `[V, Q33]`**, applied to each 8x8 cell inside its own quadrant (quadrants are
  not swapped). Read from the strides of the copy loops in `0x4154B0` (§2.8). The
  decoder's pairing (`art.py`, `renderer.py`, `native/renderer.h`) was right; no
  rendering change follows.
- **Cell order inside a record [V, G1]**: the four cells assemble **column-major**
  — slot 0 top-left, slot 1 bottom-left, slot 2 top-right, slot 3 bottom-right.
  Measured by rendering a retail plane both ways: row-major produces visible
  vertical striping (cells from different columns meet), column-major is
  continuous art — palm fronds, stone platforms and foliage line up with no
  seams. `renderer.py`, `art.py`, `conformance.py` and `native/renderer.c` all
  use column-major; this closes G1, which had stood open since WP-3.
- **`TTAB` palette nibble [V]**: flag bits 8–11 select a palette (0–15). Retail
  data uses only 0–3: `1` on 124,118 cells, `0` on 21,116, `2` on 2,913, `3` on
  2,097 — consistent with the "palette 1 non-empty in 101/104 `HEAD`s"
  observation, and it narrows Q8: the palette *does* live in the tile word
  after all, in the flag word, not the index word.
- **`CELL` [V]**: whole 64-byte 8x8 palettised cells; 14,974 across the 9
  files, every payload a multiple of 64.
- **`BONUS.WLD` "index 256" [V, Q22]**: not a cell reference. The 1,644 words
  that decode to "index 256" under the 13-bit mask are the `BONUS` *flag* words
  `0x0100` (palette 1) — `0x0100 & 0x1FFF == 256`. The index words themselves
  are all in-bank. There is therefore **no out-of-bank cell index to reject or
  preserve**: a writer round-trips every word verbatim.
- **Collision byte [V for the classes, 2026-11-24]**: on the true collision run
  (the `N` bytes after the `N` words) the byte is `0x00` on **509,860 of 523,229
  cells (97.4 %)**, with 27 distinct values `[M]`. The earlier "third-byte
  bit-field" reading was retracted 2026-11-18 because its histogram was read off
  the interleaved bytes. The **top two bits are the class**: `11` = floor surface,
  `10` = wall/ceiling, and every one of the 27 retail values fits that schema `[M]`;
  the low bits are per class (§2.9.a–c). The engine's 0-vs-non-zero "solid from
  all sides" rule is a hypothesis superseded by §2.9.a; adopting the classes is
  FL7.

### 2.5 `GNMY` placements, and the `NMY` type table **[V]**

Recovered by static analysis of the readers in `LOMAX.EXE` — `NMY` at VA
`0x415199` / file offset `0x14599`, `GNMY` at VA `0x414d16` / file offset
`0x14116` — and validated against all 9 retail world files. Everything below is
little-endian (the readers use plain `mov` on these words; only the chunk-header
size and the `HEAD`/`WRLD` fields are byte-swapped big-endian).

**`NMY`** — a sequence of variable-length records:

```
u16 count0                    # name-field size in bytes; 0 ends the table
repeat (while count0 != 0):
  name                       # NUL-terminated, padded; reader skips (count0>>1)*2 bytes
  u16 W_A                    # flags word (high byte + two nibbles, used by GNMY)
  u16 W_B                    # number of animations for this type
  u16 gap1                   # 2 bytes, not read by the loader (0 in all retail data)
  W_B animations, each:
    u32 tag                  # 4-byte identifier, byte-swapped ASCII ("HANG"→"GNAH",
                             #   "JUMP"→"PMUJ", "GRAB"→"BARG", ...)
    u32 size                 # == 20 + 8·frame_count, not read by the loader
    u16 count2               # frame count
    9 × u16                  # animation parameters (width, height, offsets, ...)
    count2 × 8-byte frames   # each {u8, u8, u16, u16, u16}
  u16 count0                 # next record's name-field size (0 = end)
[2 trailing zero bytes]      # retail files pad the u16 terminator to a u32
```

The documented framing — "a list of `u16` size + NUL-terminated name" `[S2]` — is
**retracted**: the real records carry a *name plus a binary tail*, and the walk
consumes the whole chunk (records/animations counted below), not one record.

Measured record counts: **BONUS 30, ED 44, HAUNTED 74, MAIN 24, MAP 17,
MEDIEVAL 68, TITLE 22, VILLAGE 49, WEST 53** — each equals that world's maximum
`GNMY` type index **+ 1** (BONUS 29, WEST 52, HAUNTED 73) **[V]**, which is
exactly the "records == max type index + 1" falsifier named for Q23.

The 8-byte per-frame record (each `{u8, u8, u16, u16, u16}`) is an animation
keyframe: its **first byte is the referenced `ANIM` sprite slot, 1-based**
(`type_index = byte - 1`) **[V]** — across the 9 retail worlds' `NMY`
animations, 4,789 of 4,891 keyframes resolve to a same-world `ANIM` chunk
under that read (97.9 %; the rest are global-bank/absent bytes such as `169`,
since `MAIN.WLD`'s bank carries the `0x100` flag). Reading it 0-based lands
every clip on the neighbouring chunk — the off-by-one behind the wrong sprite
labels (§2.6.1). The other five bytes (`step`, a sub-frame selector, two signed
draw offsets and a flag word) are mapped in §2.6.1 (Q34). This is what lets
`lomax_modern.engine.level.load_player_sprite` find the player's standing
frame: `MAIN.WLD`'s `Hero` record, its `STA1` ("stand") animation, and that
clip's **whole-body layer** (sprite byte 27 → `type_index` 26, 44×47–49).

**`GNMY`** entries reference those records directly, one per placed object
(3,593 entries across 104 chunks). The loader walks them **structurally** — its
read pointer is bumped by fixed `add $0x2` steps, and the leading `u16` is read
only to test for the `0` list terminator — so the entry layout below is the
reader's own arithmetic, not a size-driven walk. On the retail data that `u16`
equals the entry's structural length on **3,593/3,593** entries, which is what
proves the variable-length part correct. All little-endian:

```
u16 size        # total entry length in bytes; 0 ends the list
u16 type        # zero-based index into the world's NMY table
u16 x           # pixel X
u16 y           # pixel Y
u16 flags       # bit 15 = extra u16 follows; bits 8-9 = a 2-bit subfield
K × u16         # per-animation parameters, K = (W_A >> 4) & 0xF
[u16 extra]     # present iff flags & 0x8000
```

The reader resolves the type with `type_table[bank | type_index]`, where `bank`
is `0x100` for `MAIN.WLD` and 0 for every other world (the loader ORs a
per-world "MAIN" flag into the index). So **a `GNMY` type index is the
zero-based position of the record in the `NMY` table** — not a name, a hash, or
an offset into a string blob. `K` is the high nibble of the type's `W_A` flags
word: the `NMY` reader stores `(W_A >> 4) & 0xF` at record slot `+0x18`, and
the `GNMY` reader loads that slot back as its param-loop count.

Per-field evidence grades:

| Field | Grade | What the reader does (VA `0x414D16`) |
|---|---|---|
| `size` | **[V]** | `0x414D21` `cmpw $0` — terminator test only; never used to advance |
| `type` | **[V]** | `0x414D2B` `or 0x100` (MAIN), then `type_table[type·4 + 0x498F78]` |
| `x` | **[V]** | `0x414D67` stored to object `+0xC` |
| `y` | **[V]** | `0x414D6F` stored to object `+0xE` |
| `flags` | **[V structure, H meaning]** | `0x414D7F` stored to `+0x10`; `and 0x300; shr 8` → `+0x12` (2-bit); `testb $0x80,0x11` gates the extra word |
| `params` | **[V structure, H meaning]** | `0x414DA2` copied to object `+0x1A…` (K values) |
| `extra` | **[V structure, H meaning]** | `0x414DBF` stored to object `+0x4` (dword) when bit 15 set |

The coordinates are **pixel** coordinates: 3,584/3,593 entries place
`(x // 16, y // 16)` inside their plane's cell bounds, against 2/3,593 for
cell units, 9/3,593 for 8-px units and 1,146/3,593 for swapped `x`/`y` — the
pixel reading wins by an order of magnitude **[V]**. On collision — read under
the corrected `MAP` layout (`N` big-endian tile words then `N` collision bytes,
the map→tile pass's revision of §2.4, where byte 0 is passable on 97.4 % of
cells) — 2,881/3,593 entries land on a passable cell, so placements skew
*toward* solid cells (≈7.6× enrichment) — consistent with entities anchored to
ground/platforms, but **not** the "walkable more than chance" signature the
demo plan assumed, so the coordinate→walkability claim stays **[H]**. Reproduce
with `lomax-modern gnmy <dir>`.

**Spawn/exit/collectable is resolved by the *consumer*, not this reader
([V], Q32 closed 2026-11-19).** The reader turns every entry into a *placement*
node (a linked-list element; struct below), and a later pass consumes them. The
three candidate fields resolve as follows:

* **The identity is the `NMY` record's *name*, not a flag.** The `NMY` reader
  (`0x415199`) looks up each record's name — its first four bytes, byte-swapped
  to ASCII — in an **89-entry name table at VA `0x464650`** and stores the
  matched index at record slot `+0x16` (`0xFFFF` when the name is not in the
  table). A spawn pass (`0x4126A0`) then dispatches that index through a
  **function-pointer table at VA `0x4647B8`** (89 handlers, one per type). The
  table's four-byte names are the game's object vocabulary; the retail level
  data uses longer names that match on the first four bytes — `Start`→`Star`
  (index 0), `Finish`→`Fini` (1), `Exit`→`Exit` (2), `Revive`→`Revi` (3),
  `Moneybag`→`Mone` (57). Measured across the 9 retail
  worlds: the **player start** is the type `Start` (present in all 9, ~once per
  plane), the **level/plane exit** is `Exit` (`Finish`/`Revive` are the
  sibling end-of-plane and checkpoint types), and the **collectable** is
  `Moneybag`. The earlier "0 types once-per-world" observation was a *world*-scoped
  heuristic; a plane-based level has a `Start`/`Exit`/`Finish` per *plane*, not
  per world.
* **The 2-bit flags subfield (bits 8–9) is a per-instance state seed, not an
  enum.** The spawn pass copies `(flags & 0x300) >> 8` into the live entity's
  `+0x62`, and the type handlers read and rewrite `+0x62` as a two-bit state
  machine (0–3) across their update loops (`Mone` reads/increments it on
  pickup, `Lock` resets it to 3, most handlers reset it to 3 at update entry).
* **The bit-15 extra word is an intra-plane object reference, not an enum.**
  After a plane's list is built, a post-pass (`0x414DB7`–`0x414E13`) rewrites
  the raw `+0x4` value by calling `0x4165F0(head, extra)`, which walks the
  plane's placement list `extra` steps (0-based) and returns the Nth node's
  pointer. A bit-15 placement therefore names *another placement in the same
  plane* (a switch→door, lock→key or teleporter→destination link); which types
  link to which stays `[H]` (per-type, needs a runtime probe or per-handler
  read).

**Placement and entity structs ([V] offsets).** A `GNMY` entry becomes a
*placement* node — `+0x0` next, `+0x4` extra (the resolved reference), `+0x8`
`NMY` record pointer, `+0xC`/`+0xE` x/y, `+0x10` flags, `+0x12` the 2-bit
field, `+0x16` plane index, `+0x1A…` the `K` params — and the spawn pass
(`0x4126A0`) turns it into a 0x120-byte *entity* keeping the record at `+0x0`,
a back-pointer to the placement at `+0x4`, x/y at `+0x3C`/`+0x40`,
`flags & 0xFF00` at `+0x58`, the plane at `+0x5E`, `(flags >> 10) & 7` at
`+0x60` and the 2-bit state at `+0x62`. The in-memory `NMY` record is `+0x0`
animation list, `+0x4` name, `+0x14` `W_A >> 8`, `+0x16` type index, `+0x18`
`K`, `+0x1A` `W_A & 0xF`, `+0x1C` the `0x100` MAIN bank bit.

**The marker overlay and the simulation consume this mapping.**
`engine.overlay_gnmy` draws the playfield's placements styled by their `NMY`
name: `Start`, `Exit` and `Moneybag` get distinct colours and sizes **[V]**,
and every other name is one grey "other type" bucket — the remaining 86 names'
handlers are unmapped, so no per-name glyph is invented for them. The engine's
*simulation* also consumes the mapping: `Level.spawn` / `Level.collectables` /
`Level.exits` resolve the same placements by name (Q32) and `new_game_state`
turns them into the live spawn, exit and collectables, falling back to the
first passable cell when a plane has no `Start` placement.

### 2.6 `ANIM` / sprites **[V]**

Recovered from the reader at VA `0x414A82` / file offset `0x13E82`, validated on
**566/566** chunks. Little-endian; a 12-byte header then `n` frames:

```
u16 a              # copied verbatim by the reader
u16 b              # copied verbatim by the reader
u16 n              # frame count
u16 flags          # bit 15 = packed (4-bit) pixels; low bits carried to the frame
u16 type_index     # animation slot (reader stores the frame array at slot index+1)
u16 pad            # skipped by the reader
n × frame:
   i16 width
   i16 height
   u16 d
   u16 e
   pixel data      # round4(w·h) bytes, or round4((w·h)>>1) when packed
```

The packed flag halves the storage (two 4-bit pixels per byte) and is set on
**340** of the 566 chunks; the remaining **226** are 8-bit. Measured frame
geometry: widths 2–220 px, heights 2–241 px, 1–46 frames per chunk, type indices
0–147.

**Pixel decode** (recovered from the sprite decompressor at VA `0x415E30`,
the loop at `0x415F18` that expands a frame into an 8-bit index buffer):

* **raw** (8-bit) — one palette index per byte, row-major (`mov al,[esi]` /
  `mov [ebx],al` at `0x415F65`).
* **packed** (4-bit) — two pixels per byte, **low nibble first** then high
  nibble: `and al,0xf` stores pixel 0, `shr al,4` stores pixel 1
  (`0x415F18`–`0x415F2C`), `width>>1` bytes per row. An odd `width` drops the
  trailing pixel of each row (the reader halves `width` per row), so it is
  transparent (index 0).

Index 0 is the transparent key (the same rule the tile blit uses); the caller
applies a `HEAD` palette slot to the indices. `lomax-modern` decodes this with
`lomax_modern.anim_nmy.decode_anim_pixels`, and the player's standing frame is
the whole-body layer of `MAIN.WLD`'s `Hero` → `STA1` animation (sprite byte 27
→ `type_index` 26, 44×47–49 — see §2.6.1 for the 1-based byte).

The documented "`SpriteFrame` is 0x38 bytes" `[S2]` is **not the on-disk unit** —
it is the in-memory stride the loader allocates per frame (`0x38` bytes in RAM);
the on-disk framing is the one above, and no chunk is an array of `0x38`-byte
records (re-measured: 0/566 chunk sizes are multiples of 0x38).

### 2.6.1 The `NMY` keyframe record, and the `Hero.WALK` clip (2026-11-20)

The 8-byte keyframe (`{u8, u8, u16, u16, u16}`) is resolved against the retail
install:

```
u8 sprite   # ANIM sprite slot, 1-based: type_index = sprite - 1   [V]
u8 step     # 1-based frame of THIS keyframe's own sprite (step-1); not a
            # pose index; step 0 = not blitted, an attachment point  [V, §2.6.2]
i16 dx      # layer left edge relative to the actor origin x        [V, §2.6.2]
i16 dy      # layer top edge relative to the actor origin y, y DOWN [V, §2.6.2]
u16 flags   # 0x80 = last keyframe of a pose; 0x18 = per-layer mirror
            # (XOR with the actor's); 0x07 = layer / callback slot   [V, §2.6.2]
```

*Updated by §2.6.2 (AN1, 2026-11-23).* The previous block called `step` a
"stride pose index", `dy` "y-up" and the `0x80` bit "unresolved"; those three
readings are **retracted** — the blit at `0x40C270` settles each (§2.6.2 c/d).

**Chunk ↔ clip mapping `[V]`.** A keyframe's first byte is **1-based**: it is
the slot the `ANIM` reader stored the chunk in, `type_index + 1`. The reader
bumps the index (`inc edi` at VA `0x414A9A`) before storing the chunk's frame
array at `sprite_table[bank | index]` (`0x414B52`/`0x414B54`), and the frame
resolver reads a keyframe's raw byte into that same table with **no** offset
before its NULL check (VA `0x4163E4`–`0x4163FC`; sprite byte 0 and step 0 both
return NULL, `0x4163CB`/`0x4163D3`). So `sprite byte S` selects
`type_index S - 1`, and byte 0 is the "no sprite" sentinel.

Measured across all 9 retail worlds (4,891 keyframes): **4,789 resolve
(97.9 %)** under that read, and **0 `ANIM` chunks are unreferenced** in every
world — each world's bank is exactly the set of chunks its own clips point at.
`MAIN.WLD`'s **148** is the number of *sprite images* (`ANIM` chunks,
`type_index` 0–147); the **142** an earlier card compared it against is the
number of *clips* (the sum of every `NMY` record's `W_B`) — different units, not
a six-orphan gap. 160 distinct sprite bytes occur; 13 do not resolve in any
world's bank —
`0, 106, 169, 222, 236, 240, 242, 244, 247, 248, 249, 254, 255` (byte 0 × 9
keyframes) — and are kept as explicit gaps. Reading the byte 0-based shifts
**every** clip onto its *neighbouring* chunk, which is why `WALK` looked like a
18×23/16×17 pair and the maintainer's six state labels were all wrong: the
0-based read gave `RUN` the 54×57 art that is really `SPIN`'s. `169` occurs in
`WALK`/`RUN`/`BRAK`/`SPIN`/… and `Krug.CLAY`. **Retracted** (§2.6.2 d): the
earlier reading "the hero's shared contact pose, its pixels likely embedded in
`LOMAX.EXE`". Every one of the 12 non-zero unresolved bytes sits only on a
`step 0` keyframe, which the blit never draws — it calls an actor callback at
that point — so `169` is an attachment-point marker, not a missing sprite.

**Pose structure `[V]` (step grouping and paint order); the `0x80` bit's
meaning — settled in §2.6.2 d.** `Hero.WALK` is **10 stride poses × 2 sprite layers**, not 22
independent frames. Grouping the 22 keyframes by their second byte (`step`)
gives exactly two keyframes per `step` 1..10 — a **base** layer (sprite byte
33 → `type_index` 32, 36–42 × 44–48, the whole character) and a smaller
**overlay** layer (sprite byte 34 → `type_index` 33, 18–26 × 17–24) — plus two
`step 0` contact keyframes (sprite byte 169). `type_index` 32 has exactly 10
frames and 33's first 10 frames are used, so `step - 1` selects the matching
frame of each layer: the two keyframes sharing a `step` are one composite pose,
not two separate frames. The compositor paints the **base first, then the
overlay** on top. `flags 0x80` sits on the **base** keyframe in 9/10 steps
(step 6's base keyframe 12 is `0x00`). *Settled by §2.6.2 d `[V]`:* `0x80`
ends a pose — a pose is the run of keyframes up to and including the next
`0x80` (step 6's pose ends on the `step 0` marker after the base, flagged
`0x82`) — and the paint order base-first/overlay-on-top is now shown by the
renderer's list order, not inferred from layer size. Grouping by `step` happens
to agree with the `0x80` grouping in `WALK`; it does not in general (`STA1`:
30 poses over 7 distinct steps).

**Timing.** *Retracted (§2.6.2 d):* "none of the animation's 9 `u16` params
carry a per-frame hold". The first of them is the clip's **rate** in `/256`
poses per tick (64 = 4 ticks per pose), and the selector overrides it for
`WALK` (`|vx| / 0x700`, 3.5 ticks per pose at 2.0 px/tick) and `RUN`
(`|vx| >> 11`). The engine still advances one pose every **three** 60 Hz ticks
(`engine.state.MOVE_ANIM_TICKS_PER_POSE = 3`), a rate chosen by eye `[H]`; the
previous wiring advanced one pose per tick and stuttered by construction. Q36.

**The moving player draws `RUN`, one whole-body sprite per step `[V]` structure,
`[H]` layer choice.** `Hero.RUN` is 26 keyframes over **12 steps**: per step a
**whole-body** layer (sprite byte **23** → `type_index` 22, 48–62 × 34–43 across
the 12 frames: one image of head, torso, arms and legs) plus a smaller companion
(sprite byte **24** → `type_index` 23, 26×13–34×14). Measured on the retail install at the recorded
`(dx, -dy)`, the companion's opaque pixels land **on** the body layer's pixels
**39–97 %** of the time (WALK's pair: 65–100 %) — it is a genuine overlay on the
character, not a detached fragment. *Those two ranges were taken under the
`(dx, −dy)` placement that §2.6.2 c retracts; under the verified placement
(top = `+dy`) the same measure is `RUN` 21–65 %, `WALK` 52–66 %
(`an1_audit.py overlap`, [`research/08`](research/08-player-animation-selector.md)):
the overlay still overlaps the body but partly extends beyond it.* The 0-based read made it look detached
(0–8 %) because it paired each clip's overlay with its *neighbour's* body;
`docs/file-formats.md` §2.6.1's `RUN`/`SPIN` swap is the same mistake. The
engine's moving player still blits the whole-body layer alone
(`anim_clip.resolve_body_poses`, chosen by content bounding box, not by a
hard-coded sprite id) because that renders a complete figure on its own; what
the overlay depicts is open (**Q37**). The `anim-clip` strips composite both
layers (`anim_clip.resolve_poses`), and they too render one coherent character
per pose. **Which clip the original draws while moving is settled `[V]`
(§2.6.2 a, Q38):** `cmp esi, 0x20000` / `jg` at VA `0x411F79` with `esi = |vx|`
draws `WALK` for `0 < |vx| ≤ 2.0` and `RUN` only above 2.0 — so at the
terrain-0 walking speed of exactly 2.0 px/tick the original draws **`WALK`**,
and the engine's `RUN` for every `vx ≠ 0` is a divergence to correct, not the
original's rule. The `dx`/`dy` placement below is likewise settled in §2.6.2 c
(Q39).

**Frame selector when a clip has more steps than its chunk has frames —
retracted (§2.6.2 d).** This paragraph claimed that **45 of 691** retail clips
declare a step beyond one of their layers' frame counts (`Hero.STA2`: 10 steps
over `type_index` 27's 7 frames), and the engine wraps modulo the frame count
(`anim_clip.frame_for_step`) as a chosen convention `[H]`. The count came from
treating `step` as a pose index shared by all layers. In the original each
keyframe's `step` selects a frame of **its own** sprite, and **0 of 4,788**
drawn keyframes in the nine worlds exceed their own sprite's frame count, so
the wrap never fires on retail data and no wrap/clamp rule exists to recover.
`step == 0` is not drawn: the resolver returns NULL (VA `0x4163D3`) and the blit
treats such a keyframe as an attachment point (§2.6.2 d).

**Alignment — the placement is retracted and replaced (§2.6.2 c, Q39).** *The
pre-AN3 text below is kept as the record of the retracted `(dx, -dy)` reading —
the `neg ecx` at `0x415FF9` writes a top-down GDI DIB height, not a y-up axis,
and the actor blit (`0x40C270`) places a layer's top-left at
`origin + (dx, dy)` with y down. Its prose about where the engine drew a pose
describes the engine before AN3; **its composite measurements were re-taken for
AN3 under the verified placement** — 10 `WALK` poses on one 40×59 canvas, 5/10
poses strictly one component at 4-connectivity (steps 1, 2, 5, 6, 7) and 10/10
at 8-connectivity. AN3 now places each pose at origin + (`dx`, `dy`), y down and
mirrors about the origin column, so the offset-placed `RUN` head moves 8 px.*
Pre-AN3 text, measurements re-taken:
`dx`/`dy` are signed offsets with
the game's **y-up** axis — the sprite decompressor at VA `0x415E30` negates the
frame height before storing it (`neg ecx` at `0x415FF9`), so a layer is drawn at
screen position `(dx, -dy)`, which is what puts the head *above* the body. Each
pose composites its layers at those offsets into one canvas (the clip's union
content bounding box, so every pose shares a canvas and there is no per-pose
jitter); `anim_clip.resolve_poses` does this, painting the base first and the
overlay on top. Measured at this head on the retail install with
`anim_clip.resolve_poses(world, record_name="Hero", clip_tag="WALK")` over
`MAIN.WLD` (10 poses on one 40×59 canvas): at **4-connectivity 5/10 poses are
strictly one component** (steps 1, 2,
5, 6, 7); the other five carry one isolated 1-px pixel each (step 10 carries two).
At **8-connectivity 10/10 poses are one component**. The honest claim is "one
figure per pose at 8-connectivity, with a stray 1-px pixel in four poses and two
in one at 4-connectivity" — not "8/10 poses", which also named the wrong steps.
The exact anchor — which point on the collision box the offsets are relative
to — is not confirmed here, so the pre-AN3 engine anchored the composite like
the standing sprite: bottom at the collision-box bottom, horizontally centred,
mirrored by the player's facing direction. Anchor and facing convention were
graded `[H]`. *(§2.6.2 c: the
original's origin is the actor's integer position `0x59F23C`/`0x59F240`, the
standing body's bottom row sits exactly on it, and mirroring reflects about
the origin column, `x ↦ −x`; only the engine-to-original position mapping is
still open.)* Because
`engine.render_tiles` draws each `RUN` pose's whole-body layer and **discards
that pose's `dx`/`dy`**, the bottom-anchored blit moved the top of the sprite —
the head — from pose to pose: the twelve body layers are 34–43 px tall
(measured), so one fixed bottom anchor put their tops up to **9 px** apart. That
was an artefact of the chosen anchor, not a claim about the original's
registration. The `ANIM` frame's
`d`/`e` words (carried verbatim as `field_d`/`field_e`) look like per-frame
registration offsets but their sign and role are unresolved (Q35); the actor
blit does not read them (§2.6.2 c).

**Sprite palette slot `[H]` (user-confirmed against retail).** Sprites resolve
their indices through `HEAD` palette **slot 0**, not the tile slot (1): slot 0
carries the hero's true colours (red plume 13-15, orange face 1-5, green tunic
16-19, blue helmet/pants 20-23), where slot 1 maps indices 16-31 to an all-green
ramp — the "green hero" defect the tile slot produced before the split. There is
no palette field in the `ANIM` chunk header, so the selection is game state:
`art.SPRITE_PALETTE_SLOT` hard-codes 0 for the sprite paths only
(`engine.render_tiles`'s sprite blits, `anim_clip.pose_rgba_frames`, the
`anim-clip` CLI), while tiles stay on `art.DEFAULT_PALETTE_SLOT` (1). The
mechanism — a fixed `MAIN.WLD`-bank slot, a level-load global, or a swap through
the `Cset` NMY record (`CSET`/`PINK`/`BLUE`/`GREE`/`RED`) — is not yet traced to
a VA, so this is graded `[H]` "user-confirmed against retail" rather than `[V]`.
Sampling the other `MAIN.WLD` sprite records (`Items` type 35, `Trapdoor` 40,
`Explosions` 101, `Cset` 143) shows the same split — slot 0 yields red/orange/
blue/white art where slot 1 yields the green/grey ramp — so the slot is a
**global sprite setting**, not per-record; `Cset` is the candidate for the
player's colour *swap* (pink/blue/green/red), not the default selection.

`lomax-modern anim-clip <install> --world MAIN --name WALK --out DIR` renders
the clip's **10 composited poses** as PNGs plus a strip and a GIF, each a whole
walking character. The two contact keyframes (sprite 169) are reported as
unresolved and dropped, not half-drawn.

### 2.6.2 Clip → selector → VA: how the original picks, times and places a pose (2026-11-23, AN1)

Read-only `objdump -d -M intel` pass over `LOMAX.EXE` (no execution), plus
measurements over the retail `NMY` data with the audit script in
[`research/08-player-animation-selector.md`](research/08-player-animation-selector.md),
which also gives the command behind every number below. Grades: **[V]** the
instruction at the cited VA was read and carries the claim; **[M]** measured
over retail data with that script; **[H]** a hypothesis — usually the *meaning*
of a state bit whose test is located but whose setter is not traced. This
section **supersedes** the parts of §2.6.1 marked *retracted* there.

**The actor animation state [V].** The player is the actor struct at
`0x59F200` (its position/velocity fields are §2.9's `0x59F23C`…`0x59F250`). Four
routines run every clip, for the player and for every other actor:

| Routine | VA | What it does |
|---|---|---|
| set clip | `0x416140` | finds the tag in the actor's record's clip list; stores the clip at `actor+0x08`, its keyframe count at `+0x66`, its **pose count** at `+0x64`, its **rate** at `+0x68`; zeroes the position `+0x6A`, the resolved pose `+0x6C` and the keyframe index `+0x6E`; clears the hold-last bit 0 of `actor+0x58` (`0x416180`) |
| set clip if different | `0x416110` | returns 0 without touching the state if `actor+0x08` already holds that tag, else calls `0x416140` and returns 1 — so re-selecting the playing clip every tick does **not** restart it |
| advance | `0x4161B0` | `+0x6A += +0x68` (a 16-bit **8.8** position: the high byte `+0x6B` is the pose index); on reaching the pose count it **holds the last pose** if `actor+0x58` bit 0 is set, else **wraps** (subtract the count; add it when the byte has gone negative — a clip played backwards); returns 1 when it wrapped/ended |
| pose → keyframe | `0x416210` | walks the keyframe list counting keyframes whose flag word has bit `0x80`, so pose *n* starts after the *n*-th `0x80`; stores the index at `+0x6E` |

**The clip header [V].** The `NMY` reader (`0x415199`, the clip loop at
`0x41524C`–`0x4152D6`) copies the clip's nine `u16` fields after the keyframe
count to `clip+0x0C`…`clip+0x1E`; the first of them (`clip+0x0C`) is the rate
the set-clip routine loads. The pose count (`clip+0x0A`) is computed, not read:
`0x4160E0` counts the keyframes whose flag word has bit `0x80` (`0x415322`).

**The per-tick order [V].** The game loop calls the player routine
(`0x40FB70`) once per logic tick from the catch-up loop at `0x404C5B`–`0x404C9F`
(at most 5 ticks per rendered frame, `0x404C1F`); the tick is §2.9's 60 Hz
timer. Inside `0x40FB70` the advance runs first (`0x40FC91`; its result — "the
clip wrapped" — is the flag the selector reads) and the clip selector runs
afterwards (`0x411480`–`0x412004`).

#### a. The player's clip selector — every `Hero` clip (Q38)

`|vx|` below is `esi`, the absolute value of the velocity `0x59F24C`
(`0x411454`–`0x411467`) **[V]**; `vy` is `0x59F250`; *state* is the bit field
`0x49C4C4`. The selector is a priority chain: the first matching row wins.
Rows 1–8 are tested before the airborne/grounded split. "set" = `0x416110`
(no restart if already playing), "**force**" = `0x416140` (always restarts).
Rates are `/256` poses per tick: 64 = one pose every 4 ticks.

| # | Clip | Selected when | VA (selector) | Grade | Rate (default, `[M]`) / override |
|---:|---|---|---|---|---|
| 1 | `JPAD` | global `0x52C568` ≠ 0 **and** state `0x400` (with `0x52C568` ≠ 0 and `0x400` clear nothing is selected) | `0x411497` | [V] test; meaning of both [H] | 186 |
| 2 | `WAHL` | state `0x80` | `0x4114B2` | [V] test; meaning [H] | 47 |
| 3 | `HEL8` / `HEL5` / `HEL0` | state `0x8000` with `0x10000`: `HEL8` if state `0x1` else `HEL5`; without `0x10000`: `HEL0` (one-shot) | `0x4114E2` / `0x4114F9` / `0x411529` | [V] test; "helicopter" [H] | 64 |
| 4 | `THR2` / `THR3` / `THR1` | state `0x100`: `THR2` if state `0x4`, `THR3` if `0x1000`, else `THR1`; one-shot | `0x4115C1` / `0x4115D2` / `0x4115D9` | [V] test; "throw" [H] | 91 / 64 / 96 |
| 5 | `BUI1` | state `0x80000`; one-shot, clears the bit when it ends | `0x41162D` | [V] | 64 |
| 6 | `DROW` | state `0x200` | `0x41165B` | [V] test; "drown" [H] | 78 |
| 7 | `SPIN` | `0x59F164` ≠ 0 or `0x498F70` ≠ 0 | `0x411FD0` | [V] | **override 128** (`0x411FDF`) |
| 8 | *(air or ground split)* | state bit `0x1` set → air branch (rows 9–21); clear → ground branch (rows 22–37) | `0x4116E8` | [V] test; "`0x1` = airborne" [V] by its setters: the jump launch `0x410626`, the walk-off-a-ledge path `0x410F3A`; cleared on touchdown `0x410E19` | — |
| 9 | `OHNO` (or keep `PLOP`) | air, `0x59C708` ≠ 0; if `PLOP` is already playing it is kept | `0x411727` | [V] test; meaning [H] | 76 |
| 10 | `OUCH` | air, `0x59E938` > 0; one-shot | `0x411747` | [V] test; "hurt" [H] | 34 |
| 11 | `HELI` | air, state `0x20000` | `0x411777` | [V] | 68 |
| 12 | `DROW` | air, state `0x800000` | `0x41179A` | [V] | 78 |
| 13 | `CLIM` / `CLI2` / `CLI3` / `CLI4` | air, state `0x1000` (sub-states `0x2000`/`0x4000`) | `0x411811`–`0x411927` | [V] test; "climb" [H] | `CLIM` override ±128 (`0x411820`, `0x4118C3`) |
| 14 | **`JMP1`** | air, state bit **`0x2`** (straight jump), jump lockout `0x59E764` ≠ 0 | `0x411955` | **[V]** | 64 — time-driven while the lockout runs; **rate 0** once it reaches 0 (`0x411975`) |
| 15 | `JPAD` | air, state `0x2`, state `0x400` and `vy` < 0 | `0x411996` | [V] | 186 |
| 16 | `DROW` | air, state `0x2`, state `0x400000` | `0x4119B9` | [V] | 78 |
| 17 | `HELI` | air, state `0x2`, a held-input / counter / `vy` > 0 condition (`0x4119D0`–`0x411A06`) | `0x411A08` | [V] test; meaning [H] | 68 |
| 18 | **`FLO1`** | air, state `0x2`, **`vy` ≥ 2.5** px/tick (`cmp vy, 0x28000; jl` at `0x411A33`) | `0x411A3A` | **[V]** | 64 |
| 19 | **`JMP1`** | air, state `0x2`, otherwise — pose taken **from `vy`** (§c) | `0x411A51` | **[V]** | pose forced, then `0x416210` (`0x411AC1`) |
| 20 | **`JMP2`** | air, state bit `0x2` **clear** (moving jump): the same chain as 14–19 with `JMP2` / `FLO2` (`0x411AD8`, `0x411B19`, `0x411B3C`, `0x411B8B`, `0x411BBD`, `0x411BD4`) | `0x411AD8` / `0x411BD4` | **[V]** | as 14 / 19 |
| 21 | **`FLO2`** | air, `0x2` clear, `vy` ≥ 2.5 | `0x411BBD` | **[V]** | 68 |
| 22 | `TUMB` | ground, state `0x8` | `0x411C5A` | [V] test; meaning [H] | 64 |
| 23 | `DUCK` | ground, state `0x4`; one-shot (holds its last pose) | `0x411C7A` | [V] test; state `0x4` is set at `0x410A89` together with a facing update from the left/right input bits. **Engine rule [M]/[H]:** this engine selects `DUCK` while grounded and Down is held, one-shot from pose 0 at rate 65, holding its last pose (`engine/state.py`, `_update_duck`); whether the original sets state `0x4` while moving is untraced, and the engine suppresses horizontal input while ducking [H] | 65 |
| 24 | `DIG1` | ground, state `0x1000000`; clears the bit when it ends | `0x411CD1` | [V] | 73 |
| 25 | `PUSH` | ground, `0x59F1FC` ≠ 0 (an object pointer) and not state `0x200000` | `0x411CFD` | [V] test; "pushing" [H] | 64 |
| 26 | **`LND1`** | ground, landing counter `0x59F1CC` ≠ 0 (decremented here, `0x411D37`); cancelled by a left/right input (`test 0x464435, 0xA0` at `0x411D50`) | `0x411D3E` | **[V]** | 64 |
| 27 | `EDGE` | ground, `\|vx\|` = 0, the ledge probe `0x413940` true, not yet teetered (`0x46ABB4`) | `0x411DAB` | [V] test; "ledge" [H] | 68 |
| 28 | `DIZZ` | ground, `\|vx\|` = 0, `0x4770B0` ≠ 0 (decremented per loop) | `0x411DFA` | [V] | 76 |
| 29 | `WAHL` | ground, `\|vx\|` = 0, `0x52C56C` ≤ 0 | `0x411E46` | [V] test; meaning [H] | 47 |
| 30 | **`STA1`** (frozen) | ground, `\|vx\|` = 0, idle counter `0x46ABBC` < threshold `0x52C584`: **force** `STA1` with **rate 0** (pose 0 held), counter reset, new threshold `30 + (rand & 63)` ticks (`0x411EE7`–`0x411F11`). **Engine rule [M]/[H]:** `engine/state.py` `_update_idle` holds `STA1` pose 0 for 100 ticks at level start; the counter's increment site and the reset to 0 on leaving the idle branch are [H], and the reset/new threshold fires on (re-)entry of the frozen state, not every tick [H] | `0x411EE7` | **[V]** | **override 0** |
| 31 | **`STA2`** or **`STA1`** (played) | ground, idle counter **=** threshold: **force** `STA2` or `STA1` at the clip's own rate, chosen by bit 0 of `0x43AAD0()` (`0x411E7C`–`0x411E9C`); when it wraps the threshold becomes 10,000 so row 30 re-freezes `STA1` next tick. **Engine rule [M]/[H]:** `engine/state.py` `_update_idle` plays exactly one clip from pose 0 at rate 68/64 (`STA2`/`STA1`, 10/7 poses [M]); bit 0 set means `STA2` [H] | `0x411E85` / `0x411E9C` | **[V]** (that `0x43AAD0` is a random-number routine is [H]) | 68 / 64 |
| 32 | `RU45` | ground, `\|vx\|` ≠ 0, `0x52C574` = 2 | `0x411F25` | [V] test; "slope" [H] | **override `\|vx\|` / 0x900** (`0x411F37`) |
| 33 | `BRAK` | ground, `\|vx\|` ≠ 0, the brake flag: the input opposite the facing (`0x8000` while not mirrored, `0x2000` while mirrored) with `vx` ≠ 0 (`0x41038A`, `0x41043B`) | `0x411F54` | [V] | 93 |
| 34 | **`WALK`** | ground, `\|vx\|` ≠ 0, **`\|vx\|` ≤ 2.0** — `cmp esi, 0x20000` / **`jg`** to `RUN` | **`0x411F79`** | **[V]** | **override `\|vx\|` / 0x700** (`0x411F93`) — 73 at 2.0 px/tick |
| 35 | **`RUN`** | ground, `\|vx\|` **> 2.0** | `0x411FA8` | **[V]** | **override `\|vx\|` >> 11** (`0x411FBA`–`0x411FC5`) — 80 at 2.5 px/tick |
| 36 | `IN` / `OUT` | not in this selector: set (`0x416110`) on the player by the door/transfer code (`0x41DA89`/`0x41DB57`, also `0x432DE9`/`0x432EB7`, `0x433486`/`0x433554`) | — | [V] call site; "door" [H] | 64 |
| 37 | `HEL1` / `HEL4` | not in this selector: forced on the player, one-shot (`0x42F13C` / `0x42F208`) | — | [V] call site | 64 |

**Not drawn on the player [V call site, H owner].** `PLOP` (`0x422054`,
`0x42FFD0`), `HEL2`/`HEL6` (`0x42ED51`, `0x42ECD5`), `PLO2` (`0x428703`),
`BUI2` (`0x4285AD`) and `BOOM` (`0x41B084`, `0x41FC98`, …) are set on another
actor (`esi`/`edi`/`eax`, not `0x59F200`) — a separate splash/rotor/debris actor
that uses the `Hero` record is the likely reading [H]. `HEL3` (`0x42F18C`) and
`HEL7` (`0x42EE48`) are pushed as immediates whose consumer was not traced [H].
All 47 `Hero` tags are accounted for: 39 in the table's rows, 8 here.

**Q38 settled [V].** The comparison is `cmp esi, 0x20000` followed by **`jg`**
(signed `>`) at `0x411F79`, and `esi` is `|vx|` — not the max-speed global
`0x49C4B4`. So `WALK` is drawn for `0 < |vx| ≤ 2.0` and `RUN` only for
`|vx| > 2.0`. At the terrain-0 maximum of **exactly 2.0** (§2.9) the ordinary
walk draws **`WALK`**, at 3.5 ticks per pose (rate `0x20000 / 0x700 = 73`); `RUN`
needs a speed above 2.0, and the only one recorded in §2.9 is terrain 1's
directional 2.5 (`0x426DEC`–`0x426E26`) — whether anything else exceeds 2.0 is
not traced. The `engine/level.py` comment that said "below 2.0" (corrected by AN3)
and PR #64's "moving = `RUN`" are therefore both the exception, not the
original's rule; **AN3b made the engine follow it** — every grounded-moving tick
at the engine's only ground speed (2.0) draws `WALK`, so
`slice --world VILLAGE --frames 120` prints `clips: STA1 61, WALK 59` with no
`RUN`.

#### b. Jumps, landing and falling

* **Which jump is which [V].** The jump launch (`0x4106DE`–`0x41070B`) tests
  `vx`: moving → lockout `0x59E764` = **5** and state bit `0x2` **cleared**
  (`0x4106F5`); standing → lockout **10** and bit `0x2` **set** (`0x410708`).
  The selector draws **`JMP1` for bit `0x2`** and **`JMP2` without it** (rows
  14–21). So **`JMP1` is the straight-up jump and `JMP2` the moving jump** — the
  reverse of the plan's `[H]` "moving-vs-straight ⇒ `JMP1`/`JMP2` in that
  order". The other −4.0 launch sites (`0x41083C`, `0x4108B7`, `0x410929`,
  `0x4109D1`) clear bit `0x2` (`JMP2`); `0x412E72` sets it (`JMP1`).
* **Falling without a jump [V path, H coverage].** Walking off a ledge sets
  the airborne bit at `0x410F3A` without touching bit `0x2`, and touchdown
  (`0x410E19`) does not clear it either — so such a fall draws the clip of the
  *last* jump kind. Every writer of bit `0x2` was not enumerated. Its value at
  **level load** is now traced (§2.10.c, FL1): a fresh entry sets it — the
  straight kind **[V]**. The engine still keeps it in one constant,
  `JUMP_STRAIGHT_AT_LEVEL_START = False` — bit clear, the moving kind, which
  plan 47's FL8 is to change — and with it the 120-tick `VILLAGE` slice's spawn fall draws `JMP2`
  on ticks 0–5 and `FLO2` on ticks 6–17, whose landing at tick 18 arms no
  `LND1` (measured; plan §1.3 AC1).
* **`FLO1` / `FLO2` are the fast-fall clips, not a slow float [V].** They are
  selected when `vy` ≥ 2.5 px/tick downward (rows 18/21), on the same bit `0x2`
  split. The 0.125 held-down fall of §2.9 is a different mechanic; this
  corrects the plan's "float / slow fall" naming guess. The threshold lies below
  the +4.0 touchdown speed of a symmetric −4.0 jump under §2.9's gravity, so an
  ordinary jump is expected to end in `FLO*` for its last few ticks
  [derived from §2.9's constants, not run].
* **The landing [V].** Touchdown (`0x410E96`–`0x410EBF`) sets the landing counter
  `0x59F1CC` to **10** only when bit `0x2` is set (a straight jump) and the
  current clip is not `SPIN` and state `0x100` is clear; otherwise 0. The
  ground branch then draws `LND1` (one pose) while the counter is non-zero
  (row 26), so **`LND1` is shown for 10 ticks after a straight jump, never after
  a moving jump**, and a left/right input cuts it short. The engine follows
  that order (`engine/state.py`, `_update_air_and_landing`): the counter is
  decremented and `LND1` selected first, and only then does a left/right input
  zero the counter (`0x411D50`) — so held left/right draws **exactly one** tick
  and an input first pressed on the *k*-th `LND1` tick draws *k* (both covered
  by `tests/unit/test_air_states.py`). Measured: `slice --world VILLAGE
  --frames 120` prints `clips: STA1 49, WALK 8, LND1 1, JMP1 24, JMP2 23,
  FLO2 15`; the single `LND1` tick is the tick-79 landing after the straight
  jump at tick 65, with right held **[M — measured in this engine, not in the
  original]**. Which frame the arm at `0x410EB4` shares with this block, and
  that no earlier selector branch bypasses `0x411D2D` on that tick, remain
  untraced **[H]**.

#### c. Placement: the sign and origin of `dx`/`dy` (Q39)

The actor blit is `0x40C270`; its per-keyframe loop is `0x40C600`–`0x40CE6A`.
For each keyframe of the current pose it reads the frame at
`table[bank | sprite] + 0x10 + 0x38·step` (`0x40C63C`–`0x40C671`; the `ANIM`
reader lays frame *i* at `+0x48 + 0x38·i`, `0x414AE1`–`0x414B64`, so `step` *S*
is frame *S − 1*, confirming §2.6.1's 1-based step **[V]**), then:

* **Origin [V].** The actor's integer position: `actor+0x3C` (x) and
  `actor+0x40` (y) — for the player `0x59F23C` / `0x59F240`.
* **Sign [V].** The layer's **top-left** is at `origin + (dx, dy)` with screen
  **y pointing down** — **top = `+dy`**, not `(dx, −dy)`. The vertical clip at
  `0x40C6F0`–`0x40C71E` computes the layer's bottom row as
  `y + dy + height − 1` and its top row as `y + dy` (`add ebx, edi` /
  `lea eax, [ebx+ebp−1]`), and adds the clipped rows back onto `dy`
  (`0x40C7A5`). The player sprites are always read from the `MAIN` bank (bank
  flag `0x100` forced for `0x59F200`, `0x40C332`–`0x40C339`).
* **Mirroring [V].** Actor flag `0x08` (`actor+0x58`) mirrors horizontally:
  `dx' = 1 − width − dx` (`0x40C696`), i.e. columns `[dx, dx+w−1]` become
  `[−(dx+w−1), −dx]` — a reflection **about the origin column**, not about the
  sprite's centre. Flag `0x10` mirrors vertically the same way (`0x40C6B1`).
  The player's `0x08` is **cleared when `vx` > 0 and set when `vx` < 0**
  (`0x4104ED`–`0x41050A`; unchanged at `vx` = 0, and not updated while `SPIN`,
  `HELI` or `PUSH` plays or under state `0x400000`, `0x4104C8`–`0x4104EB`), so
  **the art as stored faces +x** [V]; input bit `0x2000` faces +x and `0x8000`
  faces −x (`0x410A8C`–`0x410ABA`). A keyframe's own flag bits `0x18` are XOR-ed with the actor's to
  pick the mirrored surface (`0x40C6E1`), so a single layer can be pre-mirrored.
* **What the measured numbers mean [M].** Under this placement the body layer's
  bottom row `dy + h − 1` is **0 — exactly the origin row — in every pose** of
  16 clips, among them the standing and walking ones: `WALK`, `STA1`, `STA2`,
  `DUCK`, `BRAK`, `PUSH`, `LND1`, `EDGE`, `WAHL`, `DIZZ`, `DIG1`, `IN`, `OUT`
  (and `THR2`, `HEL5`, `HEL8`). So the origin y is the row the feet stand on, and the
  "`dy + h` = +1" regularity of plan §2.4 is the same fact counted from 1.
  `RUN`'s bottom row spans −7 … 0 (feet lifted up to 7 px in two poses), its
  top row −42 … −34: **the offset-placed head moves 8 px over the cycle**,
  against 9 px bottom-pinned — the run cycle genuinely bobs. `JMP1` −18 … 0,
  `JMP2` −16 … 0, `FLO1` +6, `FLO2` +5.
* **The jump arc is not a double count in the original [V].** The blit adds
  `dy` to the physics position with no compensation, so the original itself
  draws a `JMP1` pose up to 18 px above the actor origin while the actor is also
  displaced by the jump. A faithful port applies `dy` as-is at the actor origin;
  what remains open is only how the engine's player position maps onto
  `0x59F23C`/`0x59F240` (Q39).
* **The engine's chosen mapping [H] — a choice, not a finding.** AN3 maps the
  player onto the original's actor origin as: origin column = the collision
  box's horizontal centre (`Player.centre_x`), origin row = the box's last row
  (`y + height − 1`, the feet row). A pose's top-left is
  `(origin_x + dx, origin_y + dy)`, or `(origin_x + 1 − w − dx, origin_y + dy)`
  for facing −x; `dy` is applied as-is on top of the physics y
  (`engine.render.pose_origin` / `pose_top_left`). The original's own mapping
  stays untraced (Q39).
* **The negation at `0x415FF9` is not about `dx`/`dy` [V].** It stores
  `−height` into a header block at `0x471B30` just after a
  `GDI32!SetStretchBltMode` call (`0x415FCF`) — the top-down-DIB height
  convention of the GDI sprite path. It was the evidence for §2.6.1's
  "`(dx, −dy)`, y-up" reading, which is **retracted**.
* **The `ANIM` frame's `d`/`e` words are not read by this blit [V].** The loop
  reads the frame's width (`+0x0C`), height (`+0x0E`) and its two surface
  pointers (`+0x14`, `+0x18`) and nothing at `+0x10`/`+0x12` (Q35 narrowed).

#### d. Pose timing and the layers of a pose (Q36)

* **A pose is a run of keyframes ended by flag `0x80` [V].** The draw loop takes
  keyframes from `actor+0x6E` and stops after the first one with bit `0x80`
  (`test al, 0x80` / `je 0x40C600` at `0x40CE68`); the pose count is the number
  of `0x80` keyframes (`0x4160E0`). So `0x80` is the **end-of-pose marker** —
  not a flip flag or a priority hint. It is not on `WALK`'s base keyframe in
  pose 5 (§2.6.1's "step 6") because that pose ends with a step-0 marker
  keyframe that carries `0x82` instead [M].
* **Each keyframe selects its own frame [V], so steps never overrun [M].**
  `step` is the 1-based frame index within *that keyframe's* sprite, with no
  bounds check or wrap in the blit (`0x40C663`–`0x40C671`). It is **not** a
  pose index shared by the layers: `STA1` has 30 poses over 7 distinct steps,
  `STA2` 76 poses over 10. Across all nine worlds **0 of 4,788** drawn keyframes
  have a step beyond their own sprite's frame count (0 of 691 clips) — the
  "45 of 691 overrun" of §2.6.1 came from treating `step` as a shared pose
  index and is retracted; no wrap/clamp rule is needed.
* **Paint order within a pose [V].** Each drawn keyframe is **prepended** to a
  depth bucket (`0x40C86E`–`0x40C87A`), and the renderer walks each bucket from
  its head, blitting in list order (`0x404DC4`–`0x404E09`). The keyframes are
  stored overlay first, body last (the `0x80` keyframe), so the **body is
  painted first and the overlay on top** — §2.6.1's order, now by mechanism.
* **Step-0 keyframes are attachment points, not sprites [V].** A keyframe with
  sprite ≠ 0 and `step` = 0 is not blitted: the loop calls the actor's callback
  slot `actor+0x1C + 4·(flags & 7)` with `origin + (dx, dy)`, mirrored with the
  facing (`0x40CD39`–`0x40CE52`). The sprite byte is only tested for non-zero.
  **The 12 non-zero sprite bytes that resolve in no `.WLD` bank (`106, 169,
  222, 236, 240, 242, 244, 247, 248, 249, 254, 255`) occur only on step-0
  keyframes** [M]: 94 keyframes have a non-zero sprite and step 0 (93 with
  those bytes, 1 with byte 100, which resolves), and no keyframe with step > 0
  carries one of those 12 bytes. So `169` is a contact-point marker for a callback, not a missing
  sprite, and nothing is "embedded in `LOMAX.EXE`" — §2.6.1's guess is
  retracted. Sprite byte 0 draws nothing (`0x40C609`).
* **Low flag bits [V].** `flags & 7` is a layer slot: a drawn keyframe is
  skipped when bit `(flags & 7)` of the actor's mask `actor+0x70` is set
  (`0x40C72A`–`0x40C740`); on a step-0 keyframe the same three bits pick the
  callback. In `WALK`, `RUN`, `STA1`, `JMP1`, `JMP2` and `LND1` the overlay
  carries slot 1 and the body slot 0; `FLO1`/`FLO2` add a third layer on slot 2
  [M].
* **The hold is per clip, not a fixed count [V].** The advance adds the rate
  (`/256` poses per tick) once per tick; the rate is the clip's first `u16`
  field unless the selector overrides it. Over the 47 `Hero` clips it is **64
  (4 ticks/pose) in 24**, and between 33 (`BUI2`) and 186 (`JPAD`) in the other
  23 [M]. Overrides [V]: `WALK` `|vx|/0x700` (3.5 ticks/pose at 2.0), `RUN`
  `|vx| >> 11` (3.2 at 2.5), `RU45` `|vx|/0x900`, `SPIN` 128, frozen `STA1` 0,
  `CLIM` ±128, `JMP1`/`JMP2` 0 once the lockout ends.
* **Air poses follow `vy`, not time [V].** After the lockout the selector writes
  the pose byte `+0x6B` directly (`0x411A68`–`0x411AB5`, `0x411BEB`–`0x411C38`):
  `vy` > 1.0 → pose 6; > −0.5 → 5; > −2.0 → 4; otherwise 3, and pose 2 when
  `vy` ≤ −3.5 (`JMP1`) / ≤ −3.875 (`JMP2`). During the lockout the clip runs at
  rate 64 from pose 0, which reaches poses 0–2 over a straight jump's 10 ticks
  and 0–1 over a moving jump's 5 [derived]. The engine implements exactly this
  (`engine/state.py`: `select_air_clip`, `air_pose_from_vy`,
  `air_clip_rate_px256`, and the lockout pose carried in `Player.air_frame` at
  rate 64), and AN4 measured the resulting per-tick tags on the `VILLAGE`
  slice: 62 airborne ticks drawn as `JMP1` 24 + `JMP2` 23 + `FLO2` 15, with no
  ground clip inside an air span **[M]** (plan §1.3 AC1).
* **Idle [V].** Standing still holds `STA1` pose 0 (rate 0) for a random
  30–93 ticks (threshold 100 at level start, `0x40F986`), then plays `STA2` or
  `STA1` once at its own rate (50/50), then freezes again (rows 30–31). `STA2`
  is therefore the idle fidget, and it needs no idle *delay* to be invented —
  it is part of the data-driven idle cycle. The engine models it in `engine/state.py` (`_update_idle`, `select_clip`; `tests/unit/test_idle.py`); the counter's increment site, the reset on leaving the idle branch, row 30's reset firing on (re-)entry rather than every tick, and bit 0 set meaning `STA2` are this engine's [H] choices.

**What stays open.** The *meaning* of several state bits (rows graded [H]); the
owner of the clips drawn on other actors; whether anything other than terrain
1 lifts `|vx|` above 2.0; how the engine's player position maps onto the
original's origin (`0x59F23C`/`0x59F240`) — the placement rule itself is
settled; and, for the air states, whether the original zeroes `vx` on a wall
contact, so that a jump launched against a wall is a *straight* jump there too
(Q40b; the jump kind at level start, Q40a, is answered in §2.10.c — a fresh entry
is the straight kind, which the engine's `JUMP_STRAIGHT_AT_LEVEL_START = False`
does not yet follow, FL8).

### 2.7 Palette rules that bite any art pipeline

Because index 0 is the transparent key and real white lives at 0x7FFE,
upscaling must be **matte-aware**: treat index 0 as alpha and scale colour and
coverage separately, or every sprite gets a halo. See
[`research/02-resolution.md §2.5`](research/02-resolution.md#25-layer-3--higher-pixel-density-the-real-ceiling).

### 2.8 Reader locations and the load chain (static analysis)

The `ANIM`/`NMY`/`GNMY` framings above were recovered from the readers inside
`LOMAX.EXE` (read-only `objdump`/Capstone pass, no execution). Addresses are
virtual address + file offset:

| Routine | VA | File offset |
|---|---|---|
| World loader (opens a `.WLD`, dispatches chunks) | `0x4147E0` | `0x13BE0` |
| `ANIM` reader | `0x414A82` | `0x13E82` |
| `CELL` reader (stores the payload pointer at `0x498F68`) | `0x414BFC` | `0x13FFC` |
| `GNMY` reader | `0x414D16` | `0x14116` |
| `HEAD` reader (plane width/height `>> 1`, palettes) | `0x414E18` | `0x14218` |
| `MAP` reader | `0x4150B5` | `0x144B5` |
| `TTAB` reader (stores `size >> 4` = tile count) | `0x415107` | `0x14507` |
| `MAP`/`TTAB` preprocessor (byte-swaps the big-endian words in place) | `0x415430` | `0x14430` |
| tile-cache builder (consumes the `0x2000`/`0x4000` flips) | `0x4154B0` | `0x148B0` |
| `NMY` reader | `0x415199` | `0x14599` |
| sprite decompressor (unpacks a frame: 4-bit low nibble first / 8-bit) | `0x415E30` | `0x15230` |
| `File_Read` (reads N bytes into a buffer) | `0x416A70` | `0x15E70` |
| byte-swap (`bswap`, big-endian→little-endian) | `0x416620` | `0x15A20` |
| spawn pass (placement → 0x120-byte entity; dispatches `record+0x16`) | `0x4126A0` | `0x11AA0` |
| arena allocator (bump allocator for placement/entity nodes) | `0x4165D0` | `0x159D0` |
| placement-list resolver (extra word → Nth node, 0-based) | `0x4165F0` | `0x159F0` |
| player-spawn plane scan (finds the type-0 `Start` placement) | `0x40ED7C` | `0xE17C` |
| player build (uses the spawn plane index) | `0x40F856` | `0xEC56` |
| `Exit` handler (last 50 px of the plane at the Exit's height → exit flag `0x49C4B0`; §2.10.b) | `0x427670` | `0x26A70` |
| `Mone` handler (collectable pickup) | `0x428190` | `0x27590` |
| ledge test (one caller, `0x411D85`; §2.9.b) | `0x413940` | `0x12D40` |
| wall probe (§2.9.c) | `0x412F50` | `0x12350` |
| ceiling probe (§2.9.c) | `0x413130` | `0x12530` |
| floor probe (§2.9.a) | `0x413B90` | `0x12F90` |
| name→type table (89 four-byte names) — **data** | `0x464650` | — |
| type handler table (89 function pointers) — **data** | `0x4647B8` | — |

**Call chain.** The world loader (`0x4147E0`, called from `0x40836A` and
`0x40EC2C`) opens the world file, then loops: it reads the 8-byte chunk header
(tag[4] + big-endian `u32` size) with `File_Read(8)`, byte-swaps the tag and the
size with `0x416620`, compares the tag as a big-endian `u32` (e.g. `"ANIM"` =
`0x414E494D`, `"NMY "` = `0x4E4D5920`) and dispatches. For a chunk it consumes it
calls `File_Read(size)` to get the payload buffer and hands it to the per-tag
reader. `ANIM` receives the payload and a per-world "MAIN" bank flag (`0x100` for
`MAIN.WLD`, else 0); `NMY` receives the payload and the same bank flag; `GNMY`
receives the payload, the bank flag and a plane mask. The `WRLD` chunk is the one
place the loader checks a magic (`"PS-X"` + `1234`).

**Tile-pipeline dispatch.** The same loader dispatches `HEAD` → `0x414E18`,
`CELL` → `0x414BFC`, `MAP` → `0x4150B5`, `TTAB` → `0x415107` (tags compared as
the big-endian `u32`s `0x48454144`, `0x43454C4C`, `0x4D415020`, `0x54544142`).
`PAGE`/`PARA`/`MACR` are read and discarded, and in `MAIN.WLD` (the "MAIN" bank
flag) `CELL`/`TTAB`/`MAP` are skipped entirely. The `MAP` reader calls the
preprocessor `0x415430`, which byte-swaps the `2·N` tile-word bytes in place —
leaving the `N` collision bytes at `map + 2·N` untouched — and then the `size/2`
`TTAB` words; it also records `plane+0x1C = map + 2·N`. The `TTAB` reader stores
the payload at `plane+0x20` and `size >> 4` (the tile count) at `plane+0x2C`.
After `CELL` is loaded, `0x4154B0` builds the per-plane tile cache: for each of
the four cells of a 16-byte record it reads the index word, computes
`CELL_base + index·64` (the `CELL` buffer pointer lives at `0x498F68`), and reads
the flag word — masking bits 13–14 (`and bx, 0x6000`) to dispatch into one of
four copy loops at `0x41566B` (no flip), `0x415686`, `0x4156A8` and `0x4156C6`
(flag word has both bits set — 180°), and bits 8–11 (`and bp, 0xF00; shr bp, 8`)
for the palette index. The loops are read as follows `[V]` (Q33 answered). The 16x16 tile is
assembled in a stack buffer with a **16-byte row stride**; the four cell
pointers are buffer+0 (top-left), +0x80 (bottom-left, 8 rows x 16), +8
(top-right) and +0x88 (bottom-right), stored in slot order TL, BL, TR, BR
(`0x4154CD`–`0x41550B`) — which independently matches the column-major cell
order of §2.4. The buffer is then blitted as a 16x16 surface (`push 0x10` width
and height, `0x415B1C`–`0x415B26`). Each source `CELL` is 64 bytes, 8 rows of 8.
Dispatch on `flags & 0x6000` is at `0x415634`–`0x415667`:

| flag bits | loop VA | what the loop does | transform |
|---|---|---|---|
| none | `0x41566B` | src forward, dst forward 8 bytes, then dst `+8` (`0x41567E`) to the next 16-byte row | identity |
| `0x2000` | `0x415686` | src `+8` (`0x41568B`); reads `[edx-1]` and decrements src (`0x415693`/`0x415696`) while dst increments; after the row src `+8` (`0x41569D`), dst `+8` | each row reversed = **horizontal mirror** |
| `0x4000` | `0x4156A8` | dst starts at `+0x70` = row 7 (`0x4156A8`); src forward 8 bytes; after the row dst `−0x18` (`0x4156BE`): +8 −24 = −16 = previous row | row order reversed = **vertical mirror** |
| `0x6000` | `0x4156C6` | src `+0x40` (`0x4156C6`), all 64 bytes read backwards (`[edx-1]`, `dec edx`), dst forward with the 16-byte stride | both = 180° rotation |

So `0x2000` is horizontal, `0x4000` vertical, `0x6000` both `[V]`. Each loop
writes only through its own quadrant pointer, so quadrants are not swapped `[V]`.
There is also a 12x12 path at `0x41581B` that copies 3 of every 4 bytes of the
already-flipped 16x16 buffer; it does not change the pairing `[V]`. The map word
itself is consumed elsewhere as a direct tile index (Q20).

**GNMY consumer chain (Q32).** After the loader builds each plane's placement
list, a post-pass (`0x414DB7`–`0x414E13`) resolves every bit-15 entry's raw
`+0x4` value into a pointer to the Nth list node via `0x4165F0`. At spawn time,
`0x4126A0` walks the lists, allocates a 0x120-byte entity per placement, copies
the placement fields into it, and calls the type handler at
`0x4647B8[record+0x16]` (index `−1` → `0x434060`, the unknown-name fallback).
The player is *not* spawned from this list: a separate level-load scan
(`0x40ED7C`) walks each plane's list for the `record+0x16 == 0` node (the
`Start` placement), records its plane in `0x52C540`, and `0x40F856` builds the
player struct (`0x498F1C`) from that plane — so the player start is the `Start`
placement's *plane*. `Start` (placement flag `0x4000`) is the hero's entry
point, `Exit` the sub-level exit, `Finish` (flag `0x4000` clear) a section-ending
lift, `Revive` a checkpoint and `Moneybag` a collectable (§2.5, §2.10).

### 2.9 Player movement constants (walk/jump/gravity/fall) **[V]**

Recovered from the player-movement code in `LOMAX.EXE` (read-only `objdump`
pass, 2026-11-19). The player's position and velocity are **16.16 fixed point**
(integer part = pixels, fraction = 1/65536 px): position `X`/`Y` live at
`0x59F244`/`0x59F248`, the integer pixels at `0x59F23C`/`0x59F240`, and
velocity `vx`/`vy` at `0x59F24C`/`0x59F250` (each store then re-reads the high
word back as the integer coordinate — the fixed-point signature). The tick is
the 60 Hz `WINMM.timeSetEvent` loop
([`07-wp1-patching-surface.md`](research/07-wp1-patching-surface.md) §4),
so "per tick" is "per 1/60 s". The four rates, which the engine carries as
`engine/entities.py` constants:

| Constant | Value (px/tick) | Fixed-point | VA (file offset) | Evidence |
|---|---|---|---|---|
| `WALK_SPEED` | **2.0** | `0x20000` | `0x426E28` (`0x26228`) | `mov ebp, 0x20000` — the flat-floor (slope kind 0) speed of the `Tonn` state function `0x426D20`, stored to the hero's max-speed override `0x49C4B4` (`0x426E78`) [V]; whether 2.0 is also the hero's own on-foot maximum is Q51 [H] |
| `GRAVITY` | **0.375** | `0x6000`/tick | `0x410BB8` (`0xFFB8`) | `add eax, 0x6000` added to `vy` every airborne tick |
| `JUMP_SPEED` | **−4.0** | `0xFFFC0000` | `0x41083C` (`0xFC3C`) | `mov ds:0x59F250, 0xFFFC0000` (also `0x4108B7`, `0x410929`, `0x4109D1`, `0x412DAB`, `0x412EC2`) |
| `MAX_FALL` | **6.0** | `0x60000` | `0x410BC2` (`0xFFC2`) | `cmp vy, 0x60000; jle` … `mov vy, 0x60000` terminal-velocity clamp |

Measured nuances the engine's simple `impulse + constant gravity` model does
not yet reproduce, recorded here so they are not silently dropped:

- **The normal jump impulse is −4.0 everywhere.** Stomping an enemy or a spring
  uses a higher impulse (**−5.0** at `0x412F14`, **−6.0** at `0x41022A`), and a
  small hop uses **−2.0** (`0x41067B`); the engine's single `JUMP_SPEED` is the
  normal jump.
- **Gravity is skipped for a few ticks after a jump.** `0x59E764` is set to 5
  (jumping while moving) or 10 (a straight-up jump) at `0x4106EC`/`0x4106FF`,
  decremented once a tick (`0x410D36`), and while it is non-zero the gravity
  add is gated off (`0x410B19`–`0x410B21`) — so the impulse plays out before
  gravity bites. The engine applies gravity unconditionally, so for the same
  constants its jump arc is shorter than the original's.
- **Holding the jump raises with reduced gravity** via a per-tick counter
  `0x59E94C` (initialised to `0x9800`/`0xA800`/`0xB000`, decremented `0x800`
  per tick at `0x4105D4`, the remainder subtracted from `vy`). A held
  slide/down input instead uses a **0.125** fall (`0x2000` at `0x410B9A`)
  clamped to **1.0**.
- **A speed override depends on the slope kind `[V]`.** `0x426DEC`–`0x426E28`
  lie in the `Tonn` state function `0x426D20` (installed by the `Tonn` handler,
  name index 50, `0x426A10`: `mov [esi+0x18], 0x426D20` at `0x426A1B`), an
  object's code, not the hero's tick; riding a barrel is `[H]`. It branches on
  `0x52C4C8 == 1`, the floor probe's **slope kind** (1 for both shallow shapes,
  §2.9.a), and replaces 2.0 with a directional **1.5** / **2.5**
  (`0x426DEC`–`0x426E26`). Slope kind 2 (steep) forces that object's `vx` to
  ±1.5 (`0x426DC7`–`0x426DEA`). The function writes `0x49C4B4` at `0x426E78`;
  `0x427036` (in the next function, `0x427030`) clears it; the hero reads
  `0x49C4B4` at `0x4103B0`/`0x410461` only as an override when it is non-zero
  (`0x4103B6`–`0x4103B8`). The hero's own limit is Q51.

The jump gravity-lockout and the hold-to-rise counter are the two measured
mechanics that would make the engine's jump feel exactly like the original's;
adopting them is follow-up work, not an open question — the mechanism is
measured, only the engine's adoption is missing.

#### §2.9.a The collision byte: classes (2026-11-24, FL2; Q31, Q43)

Recovered by a read-only objdump pass over `LOMAX.EXE`. Grades as in §2.10:
**[V]** an instruction in `LOMAX.EXE` carries it, **[M]** measured by running a
command, **[H]** a guess / interpretation, **[derived]** arithmetic on graded
numbers. Plane records are `0x9C` bytes from `0x49B880`; `plane+0x1C` is the
collision-byte pointer (`map + 2·N`, §2.8), `+0x10` the width in cells, `+0x14`
the height in cells. The **top two bits are the class**; exactly two classes
have a reader:

| bits 7–6 | class | reader(s) | grade |
|---|---|---|---|
| `11` (`0xC0`–`0xFF`) | **floor surface** | `0x413B90` only: `and cl,0xC0; cmp cl,0xC0` at `0x413C46`/`0x413C49` | [V] |
| `10` (`0x80`–`0xBF`) | **wall / ceiling** | `0x412F50` (walls, `and dl,0xC0; cmp dl,0x80` at `0x413064`/`0x413067`) and `0x413130` (ceiling, `0x413196`/`0x413199`) | [V] |
| `01`, `00` (non-zero) | no reader found | — | [M] by a search of the disassembly for every `and/test/cmp …,0xC0` (9 hits; the other 5 are unrelated: `0x40C499`, `0x4161E6`, `0x43E1AA`, `0x43E1E5`, `0x44B4C7`). A reader written another way (e.g. `shr 6`) would be missed; no retail cell carries such a value (C8 below), so it does not matter for data |

**The floor probe `0x413B90(plane, x, y, rows)` [V].**

- Returns the floor y in pixels, or `0x4E20` (20000) = "no floor".
- Special planes: if `plane+0x48` ≠ 0 it returns 190; if the loaded section's
  world-kind byte (section entry +10, `0x46645A`) is 6 it returns 122
  (`0x413BB1`–`0x413BCA`, `0x413D19`–`0x413D38`). The meaning of those two cases
  is [H]; `MEDIEVAL` plane 0 uses neither (plan 47's L1).
- `y < 16` → no floor (`0x413BD4`). `x` outside `[0, width·16)` → no floor,
  unless hero state bit `0x20000000` of `0x49C4C4` is set, in which case `x`
  wraps modulo the plane width (`0x413BEF`–`0x413C10`).
- Scan: column `x >> 4`; first row `max(0, (y − 16) & ~15)`; it walks **down** at
  most `rows` cells (the hero passes 4, `0x410C4E`) while inside the plane, and
  stops at the first byte with `(b & 0xC0) == 0xC0` (`0x413C3A`–`0x413C57`).
- On a hit (`0x413C66`–`0x413C93`): `xi = x & 15`; `0x59E760 = b & 7`
  (material); `0x52C5A4 = 0`; shape `= (b & 0x30) >> 4`, dispatched through the
  4-entry jump table at `0x413D48` (`jmp [ecx*4+0x413D48]` at `0x413C93`), whose
  entries are `0x413C9A`, `0x413CAF`, `0x413CB2`, `0x413CE0` (read from the
  table, C9). Let `top` be the pixel y of the hit cell's top edge:

| shape (`b & 0x30`) | entry | floor y returned | `0x52C4C8` (slope kind) | bit `0x08` |
|---|---|---|---|---|
| 0 (`0x00`) flat | `0x413C9A` | `top + 16` (the cell's **bottom** edge) | 0 | not read |
| 1 (`0x10`) shallow, lower half | `0x413CAF` | `top + 8 + (xi >> 1)` | 1 | if set: `top + 8 + 7 − (xi >> 1)` and `0x52C5A4 = 1` |
| 2 (`0x20`) shallow, upper half | `0x413CB2` (enters shape 1's code after its `+8`) | `top + (xi >> 1)` | 1 | if set: `top + 7 − (xi >> 1)`, `0x52C5A4 = 1` |
| 3 (`0x30`) steep 45° | `0x413CE0` | `top + xi` | 2 | if set: `top + 15 − xi`, `0x52C5A4 = 1` |

y grows downward, so without bit `0x08` a slope **descends to the right**; bit
`0x08` mirrors it (rises to the right) [V for the arithmetic, "descends/rises"
[derived]]. `0x52C4C8` is a slope *kind* (0 flat, 1 shallow, 2 steep), **not** the
raw `(b & 0x30) >> 4`: shapes 1 and 2 both give kind 1, shape 3 gives kind 2 [V].

**Material (low 3 bits).** [V for the plumbing, the name is [H].] `0x59E760` is
copied to `0x46AB40` each hero tick (`0x410C76`/`0x410C8D`; zeroed when an object
platform wins, `0x410D27`). On landing without an object platform the hero calls
`0x4309F0` three times (`0x410E01`–`0x410E0C`): material 0 spawns an object of
`NMY` name `Gras` (string at `0x4669F0`, C10); material 2 spawns `Geld`
(`0x4669F8`) only when the section's world-kind byte is 5 (`0x430A05`–`0x430A23`);
other materials spawn nothing. The particle's launch speed also differs between
material 0 and the rest (`0x430ACE`–`0x430AF8`). A walking-dust spawner `0x42FCA0`
also fires only on material 0 (`0x42FCB3`). "Grass/dust particles" is [H]; the
branches are [V].

#### §2.9.b Floor contact: landing, one-way, ground-follow (Q43)

The hero tick function starts at `0x40FB70` [V].

- At the start of the tick the hero keeps `prev_y` (`[esp+0x34]` ← `0x59F24A`),
  `prev_floor` (`[esp+0x38]` ← `0x52C558`) and `prev_kind` (`[esp+0x44]` ←
  `0x52C574`) (`0x40FCA4`–`0x40FCBE`) [V].
- Each tick after the move it probes `0x413B90(hero plane, x, y, 4)` (`0x410C5E`)
  → `0x52C558` = floor y, `0x52C574` = kind, `0x52C5B0` = mirror, `0x46AB40` =
  material (`0x410C66`–`0x410C8D`). An object platform's top (`0x52C704`,
  `0x4E20` = none, set at `0x40EF16`) replaces the floor when it is higher
  (`0x410CE8`–`0x410D27`) [V].
- **Landing** (airborne bit `0x1` of `0x49C4C4` set, jump gravity-lock `0x59E764`
  = 0, death timer `0x59C708` = 0; `0x410D3D`–`0x410D5F`) [V]:
  1. if `prev_floor` is `0x4E20` it is replaced by the current floor
     (`0x410D65`–`0x410D75`);
  2. a vertical-speed gate by kind: kind 0 needs `vy > 0` (falling); kind 1 needs
     `vy > −1.5` (`0xFFFE8000`); kind 2 needs `vy > −3.25` (`0xFFFCC000`)
     (`0x410D79`–`0x410DB9`);
  3. `prev_floor ≥ prev_y` (the feet were on or above the surface before the move,
     `0x410DBF`–`0x410DC9`) **and** `floor ≤ y` now (`0x410DCF`–`0x410DDC`);
  4. then `y = floor` (`0x410E25`), the airborne/`0x400`/`0x400000` bits are
     cleared (`and 0xFFBFFBFE`, `0x410E19`) and `vy = 0` (`0x410E4E`).

  Rule 3 makes every floor-class cell **one-way**: the hero passes up through it
  from below and lands only when it comes down onto it [V]. Floor-class cells
  never block sideways motion or the head; only the wall/ceiling class does
  (§2.9.c) [V].
- **Staying grounded** (`0x410F09`–`0x410F5E`): with `d = |y − floor|`, the hero
  stays on the ground if `d ≤ 18` when `0x52C704` ≠ 0, or if `d < 3` when it is 0;
  otherwise it becomes airborne (`y += 2`, floor = `0x4E20`). [V] for the
  comparisons; which branch applies in ordinary play is [H] (`0x52C704` holds
  `0x4E20` when there is no platform, which is non-zero, so the 18 px tolerance is
  the likely one).
- What the hero does while **standing on a steep (kind 2) slope** (code from
  `0x410F63`, using `prev_kind` and extra probes at `x ± 1`) was **not traced**
  [H]; named in Q43.
- **Ledge test `0x413940`** (called once, at `0x411D85`) [V] is a ledge test, not a
  class probe. With no object platform it probes the floor at `x − 7` and `x + 7`
  (`0x4139AC`–`0x413A49`, rows 4); a side counts as "edge" when there is no floor,
  when the kind is 2 and the floor is below the feet (`0x4139D6`–`0x4139EA`; it
  checks `0x52C4C8 == 2`), or when `|floor − y| > 10`. It returns 1 and records the
  side in bit `0x08` of `0x59F258` (left edge → set, right edge → cleared); 0 when
  both sides have floor. On an object platform it compares `x` with the platform
  box ± 8 instead (`0x413941`–`0x4139AB`). What the caller does with it (a teeter
  clip?) is [H].

#### §2.9.c Walls and ceilings (Q31)

- **Wall probe `0x412F50(entity, clamp)`** [V]: returns 0 at once when
  `plane+0x48` ≠ 0. Moving left (`vx < 0`) it tests `x − 8` with mask `0x10`;
  moving right `x + 8` with mask `0x20`; `vx = 0` tests right then left (sentinel
  `0xBC614E`, `0x412FC2`, `0x413088`–`0x413092`). Rows: the cells at `y − 1`,
  `y − 17`, `y − 33` (3 cells, stepping up 16 px; `0x41302A`–`0x413086`). A hit is
  `(b & 0xC0) == 0x80` and `b & mask`; it returns 1 (left blocked) or 2 (right
  blocked) and pins the x fraction (`0x413097`–`0x4130BF`). So bit `0x10` blocks
  movement to the left and bit `0x20` movement to the right. The hero calls it at
  `0x411150` with `(0x59F200, 0)` and on a hit sets `vx = 0` (`0x411161`). The
  probe ignores the clip box: the hero's wall width is ±8 px about the feet
  origin [V].
- **Ceiling probe `0x413130(entity)`** [V]: only while moving up (`[entity+0x50]`
  < 0); tests the cell at the box top `+ 11` px; a hit is `(b & 0xC0) == 0x80` and
  `b & 0x08` (`0x413191`–`0x4131A2`). The hero calls it at `0x410AEA` and on a hit
  raises `vy` to at least **+2.0** (`0x20000`, `0x410AF6`–`0x410B05`) — a bonk
  that turns the jump into a fall.
- The low 3 bits of a wall byte (`0x91`, `0xA1` occur): no reader found [H].

#### §2.9.d L1's eight values (AC3)

`MEDIEVAL` plane 0 is 198 × 40 = 7,920 cells. Counts are [M] (C1).

| value | class | shape | mirror | material | count in L1 [M] | behaviour for the engine | grade |
|---|---|---|---|---|---|---|---|
| `0x00` | none | — | — | — | 7,624 | passable | [V: no reader matches 0] |
| `0xC0` | floor | flat (0) | no | 0 | 76 | one-way surface at the cell's bottom edge | [V] |
| `0xC8` | floor | flat (0) | bit set, **not read for shape 0** | 0 | 114 | behaves exactly as `0xC0` | [V] for `0x413B90`; "no other reader" [M] by search |
| `0xD0` | floor | shallow, lower half (1) | no | 0 | 26 | one-way slope, descending to the right | [V] |
| `0xD8` | floor | shallow, lower half (1) | yes | 0 | 18 | one-way slope, rising to the right | [V] |
| `0xE0` | floor | shallow, upper half (2) | no | 0 | 26 | one-way slope, descending to the right | [V] |
| `0xE8` | floor | shallow, upper half (2) | yes | 0 | 18 | one-way slope, rising to the right | [V] |
| `0xF0` | floor | steep 45° (3) | no | 0 | 18 | one-way slope, descending to the right; landing gate `vy > −3.25` | [V] |

Measurements on L1 (all [M] unless marked; commands under **Reproduce**):

1. **Population (C1).** `0x00` 7,624, `0xC0` 76, `0xC8` 114, `0xD0` 26, `0xD8` 18,
   `0xE0` 26, `0xE8` 18, `0xF0` 18. All 296 non-zero cells are floor class (top
   bits `11`); there is **no wall or ceiling cell in L1**.
2. **Slope pairing (C2).** Every `0xE0` has `0xD0` on its right (26/26) and every
   `0xD0` has `0xE0` on its left (26/26); every `0xD8` has `0xE8` on its right
   (18/18) and every `0xE8` has `0xD8` on its left (18/18). Shallow slopes are
   two-cell pieces: `E0,D0` descends 16 px over 32 px to the right, `D8,E8` rises
   to the right [M]+[derived].
3. **Surface continuity (C3).** Emulating `0x413B90` around every slope cell, the
   surface height between adjacent pixel columns changes by 0 px 811 times and by
   1 px 1,097 times, never more. This supports the shape table on real data.
4. **Steep cells (C4).** The 18 `0xF0` cells have `0x00` as left and right
   neighbour; diagonally they form staircases (up-left/down-right neighbours
   `(0xD0, 0xF0)` 3, `(0xF0, 0xF0)` 12, `(0xF0, 0xE0)` 3): three 45° runs of 6
   cells, each entered from a shallow `D0` and left into a shallow `E0`, all
   descending to the right (no `0xF8` in L1).
5. **One cell thick (C5).** All 76 `0xC0` and all 114 `0xC8` have `0x00` directly
   above and below: collision is a surface line, not a solid volume.
6. **Art vs collision (C6).** Mean opaque-pixel share for flat cells — `0xC0`:
   cell above 0.27, own top 8 rows 0.532, own bottom 8 rows 0.995, top 8 rows of
   the cell below 1.0; `0xC8`: 0.307 / 0.516 / 0.982 / 1.0. The drawn ground top
   lies **inside** the flat cell (around its middle), while `0x413B90` puts the
   surface at the cell's **bottom** edge. The 8–16 px difference is unexplained
   (sprite draw offset, map draw offset, or a deliberate sink) → Q52 [H].
7. **Spawn (C7).** `Start (89, 407)`, feet at `(89, 367)` (§2.10.c); the floor
   probe from the feet finds nothing within 4 rows, and the first floor below is
   at **y = 496** (row 30's bottom edge) [M, emulation of `0x413B90`]. Plan 47
   §6 (G) reports the engine's "first solid row 30 (y = 480)"; the original's
   surface rule gives 496 [derived].
8. **Retail census (C8).** All 104 planes (523,229 cells): 27 distinct values and
   **every one fits the class schema** — `0x00` 509,860; wall/ceiling `0x88` 112
   (ceiling only), `0x90` 215 / `0x91` 18 (block left), `0xA0` 242 / `0xA1` 39
   (block right); floors `0xC0` 1,153, `0xC1` 1,874, `0xC2` 146, `0xC8` 1,599,
   `0xC9` 2,921, `0xCA` 136, `0xD0` 569, `0xD1` 371, `0xD2` 100, `0xD8` 459,
   `0xD9` 349, `0xDA` 94, `0xE0` 690, `0xE1` 576, `0xE2` 106, `0xE8` 580, `0xE9`
   522, `0xEA` 106, `0xF0` 130, `0xF1` 232, `0xF8` 30. Materials used: 0, 1, 2
   only; no value with top bits `00`/`01` other than `0x00`.

**Still [H]:**

1. the hero's grounded behaviour on kind-2 (steep, `0xF0`) cells — code from
   `0x410F63` not traced;
2. the 8–16 px offset between the collision surface and the drawn ground (Q52);
3. the meaning of `0xC8`'s bit `0x08` on a flat cell, if any (no reader found);
4. which ground-follow tolerance (18 or 3 px) applies in play.

**For the engine (FL7).**

- Floor class = a one-way surface: land only when coming down from at or above
  it; surface y by the shape formula above; no sideways or head blocking from
  floor-class cells.
- Wall class blocks only in the direction of its bit (`0x10` leftward, `0x20`
  rightward) over the three cells at feet −1/−17/−33.
- Ceiling bit `0x08` bonks to `vy ≥ +2.0`.
- Values outside both classes stay on the conservative rule and are printed.

**Reproduce.** The scripts are scratch files outside the repository and are not
committed; run them against the user's install:

```
objdump -d -M intel --no-show-raw-insn "$LOMAX_GAME_DIR/LOMAX.EXE" > /tmp/fl2/lomax.asm
env PYTHONPATH=src python3 coll_census.py "$LOMAX_GAME_DIR" MEDIEVAL 0   # histogram, slope neighbours, surface continuity, Start landing
env PYTHONPATH=src python3 coll_ctx.py    "$LOMAX_GAME_DIR" MEDIEVAL 0   # 0xF0 diagonals; cells above/below flat cells
env PYTHONPATH=src python3 coll_art.py    "$LOMAX_GAME_DIR" MEDIEVAL 0   # opaque-pixel share around flat cells
env PYTHONPATH=src python3 coll_all.py    "$LOMAX_GAME_DIR"              # every plane of every world
python3 -I va_str.py "$LOMAX_GAME_DIR/LOMAX.EXE" 0x4669f0 0x4669f8       # the two object names
od -A x -t x4 -j $((0x413d48-0x400c00)) -N 16 "$LOMAX_GAME_DIR/LOMAX.EXE"  # the 4 jump-table targets
```

Measured outputs: C1–C8 as listed above. C9: the jump table at `0x413D48` holds
`0x413C9A`, `0x413CAF`, `0x413CB2`, `0x413CE0`. C10: `0x4669F0` = `Gras`,
`0x4669F8` = `Geld`.

### 2.10 Level flow, start state and the fail rule (2026-11-24, FL1)

Recovered by a read-only objdump pass over `LOMAX.EXE` for the first-level plan
([`../roadmap/47-first-level-plan.md`](../roadmap/47-first-level-plan.md), FL1;
Q41, Q42, Q48). Grades as in §2.6.2: **[V]** an instruction in `LOMAX.EXE`
carries it, **[M]** measured by running a command, **[H]** a guess /
interpretation, **[derived]** arithmetic on graded numbers. Every VA can be
re-read with `objdump -d -M intel --no-show-raw-insn "$LOMAX_GAME_DIR/LOMAX.EXE"`
written to a file outside the repository.

| Global | Meaning | Grade |
|---|---|---|
| `0x4645C4` | section to load (index into the 24-entry table at `0x466450`) | [V] |
| `0x4645BC` | sub-level within the section | [V] |
| `0x4645C0` | the section actually loaded (copy of `0x4645C4`, `0x40EBDB`, `0x417CF8`) | [V] |
| `0x4645C8` | the *story* section: set to the loaded section only when the entry's world index is ≤ 4 (`0x40EBE3`–`0x40EBEF`; indices 0–4 are `MEDIEVAL`…`ED`, plan 47 §1.2), so bonus/map/title loads do not overwrite it | [V] |
| `0x52C56C` | lives | [V] |
| `0x59F160` | credits (continues) | [V] |
| `0x52C6C4` / `0x59E958` / `0x59C718` / `0x52C6D0` | the selector's four mode flags: title, map, bonus, attract demo (names [H], the branches they select are [V]) | [V]/[H] |
| `0x52C59C` | "level ended — run the selector" flag (main loop `0x404AC4`–`0x404AD6` calls the selector `0x417BD0` when it is set and `0x59F1DC` is clear) | [V] |
| `0x52C5F4` | screen-transition counter: set to `+64` at a level start and to `−64` when a level ends or the hero dies; the negative count runs up to 0 and then calls `0x405990` and, unless `0x52C59C` is set, rebuilds the level with `0x40F670` (`0x40F646`–`0x40F65D`). Calling it a fade is [H] | [V] |
| `0x49C4B0` | "exit reached" flag (set by the `Exit` handler) | [V] |
| `0x46AB44` / `0x46AB48` | respawn point x / y: `−1` on every level load (`0x40EC7A`), set by a touched `Revive` | [V] |
| `0x59C708` | death timer (300 at a death) | [V] |
| `0x49C4C4` | hero state bits: `0x1` airborne, `0x2` straight-jump kind (§2.6.2 b), `0x10` frozen (vx and vy zeroed every tick, `0x410BD9`–`0x410BE4`; input cleared, `0x40FBE3`–`0x40FBF8`), `0x200` set at `0x431C89`, inside the code of the `Water` handler (name index 81, `0x4317F0`) [V by address range], `0x40000000` suppresses every life decrement (writers `0x419DEB`, `0x41A00F`; meaning [H]) | [V] bits as read; names [H] where marked |
| `0x59F23C` / `0x59F240` | hero integer x / y (§2.9) — **the feet origin**, see §2.10.c | [V] |

**Reproduce.** The scripts are scratch files outside the repository and are not
committed; run them against the user's install:

```
objdump -d -M intel --no-show-raw-insn "$LOMAX_GAME_DIR/LOMAX.EXE" > /tmp/fl1/lomax.asm
python3 -I names.py "$LOMAX_GAME_DIR/LOMAX.EXE"      # name index -> handler VA (0x464650 / 0x4647B8)
python3 -I demo_check.py "$LOMAX_GAME_DIR"           # 0x466410 entries vs DEMOS/: 8/8 exist, 0 name section 0
env PYTHONPATH=src python3 spawn_facts.py "$LOMAX_GAME_DIR" MEDIEVAL Hero   # Start/Exit/Finish/Revive flags; Hero clip boxes
```

Measured outputs: handler VAs as listed in §2.10.b; `entries 8, DEMOS file
exists for 8/8, entries naming section 0: 0`; `DEMOS files: 14`; `Start`
placement flags have bit `0x4000` in all 11 planes 0–10 that have a `Start`
(plane 3's is `0x4300`, also with bit `0x4000`); `0x464424` = 240 and
`0x464420` = 160 (initialised data) [M].

#### §2.10.a How a new game reaches section 0 (Q41)

1. **The reset `0x40EDC0` [V].** Writes 0 to the sub-level `0x4645BC`
   (`0x40EDD8`) and the story section `0x4645C8` (`0x40EDCD`), 3 to lives
   `0x52C56C` (`0x40EE06`) and credits `0x59F160` (`0x40EDFA`), 1 to the title
   flag `0x52C6C4` (`0x40EE2F`) and the map flag `0x59E958` (`0x40EE35`), 0 to
   the bonus flag `0x59C718` (`0x40EE25`) and the demo flag `0x52C6D0`
   (`0x40EE3B`). It does not write `0x4645C4`. Callers: `0x403453` (start-up),
   `0x40E2AA` (it also sets `0x52C59C` at `0x40E2AF`; a menu "new game"
   command is the reading [H]), `0x417A43` (password accepted), `0x417C27`
   (selector, game over), `0x41D674` and `0x41D86F` (the `TITLE` level's
   handler) [V].
2. **The selector `0x417BD0` [V]** (the branch block is `0x417C2C`–`0x417CDF`).
   It first resets the game (`0x417C27`) when lives < 0, or when lives and
   credits are both 0 (`0x417BFC`–`0x417C25`). Then, first match wins:
   title flag → section 23 (`TITLE`), sub-level 1, lives := 3
   (`0x417C35`–`0x417C49`); bonus flag → section 21 (`BONUS`), sub-level from a
   counter `0x59F178` that cycles 0…4, flag cleared (`0x417C5A`–`0x417C90`);
   map flag → section 22 (`MAP`), sub-level 0 (`0x417C9B`–`0x417CA5`);
   demo flag → section and sub-level from the table at `0x466410`
   (`0x417CBA`–`0x417CDA`); otherwise `0x4645C4`/`0x4645BC` are kept as they
   are. A section ≥ 24 becomes 0 (`0x417CE4`–`0x417CE9`) [V]. Section numbers
   to world names: plan 47 §1.2 [M].
3. **`0x466410` is the attract-mode demo playlist, not a map-node table
   [V]+[M].** Each 8-byte entry holds `section + 1` and `sub-level + 1` as its
   first two `i16`s (`0x417CC4`–`0x417CD3` subtract 1 from each). The selector
   then formats a `DEMOS` file name from `section + 1` and `sub-level + 1` with
   the format string at VA `0x4668A8` (`0x417D02`–`0x417D1A`) and, in title or
   demo mode only, opens it and copies `0x2000` bytes of it to `0x59C758` as
   the input record (`0x417D22`–`0x417D83`). Measured: all **8/8** entries name
   an existing file in `DEMOS/` (14 files), and **0** entries name section 0;
   the `TITLE` load (section 23, sub-level 1) names an existing file too [M,
   commands above]. So section 0 is absent from it because it is a demo list.
   This also narrows Q6 (the `DEMOS` file name is `section + 1`,
   `sub-level + 1`). The demo flag is set by the `TITLE` handler when the hero's
   x passes `plane+0x30` + 320 (`0x41D7BA`–`0x41D7D6` store `0x4D2`, then
   `0x41D88B`) [V] — on the title the hero is driven by the title demo's input,
   so this acts as an idle time-out [H] — and by `0x419E1F`;
   the playlist index `0x46AB50` advances and wraps at `0x41C9D8`–`0x41C9EB`
   [V].
4. **The path of a new game [V for each write; order of ticks H].** Reset
   (title = 1, map = 1, story section = 0) → selector loads `TITLE` (23 / 1) →
   the `TITLE` handler (name-table index 14, `0x41D670`) waits for a key
   (`0x464440` bits `0x1F8` or `0x40`, `0x41D812`–`0x41D832`), sets `0x52C59C`,
   and at the end of the transition calls the reset again and clears the title
   flag (`0x41D86F`–`0x41D874`), leaving the map flag set → selector loads
   `MAP` (22 / 0) → the `MAP` handler (index 41, `0x424100`) clears the map
   flag (`0x424109`), and its update `0x4241C0` writes sub-level := 0
   (`0x424234`), `0x52C59C` := 1 (`0x42423E`) and section := `0x4645C8`
   (`0x424244`–`0x42424A`) once `0x59F1DC` is set (`0x424224`) → selector, no
   flag set → **section 0, sub-level 0** is loaded by `0x40EB80(0)`
   (`0x417DE3`). So a new game reaches section 0 through `TITLE` and `MAP`,
   with no player choice of a node: the map just carries the story section
   [V]. The password path is the same with the decoded section:
   `0x417A43`–`0x417A9C` reset, then set section, lives, credits, story
   section, sub-level 0, title 0, map 1 [V].
5. **Section advance is the story section + 1 [V].** The banner routine
   `0x427940(kind)` with kind 4 (`0x427AFE`) or 6 (`0x427B9E`) sets the map
   flag and `0x52C59C` and adds 1 to `0x4645C8` when the loaded entry's world
   index is ≤ 4 (`0x427B56`–`0x427B62`, `0x427BE7`–`0x427BF3`) — the next `MAP`
   load then hands section + 1 to the selector. Kind 4 is raised by a
   `Finish`-type lift (§2.10.b); kind 6 by `0x41B495` (handler not identified
   [H]). The F1/F2/F3 keys call next-section `0x417DF0`, next-sub-level
   `0x417E30` and the selector only while `0x4645B8` is set
   (`0x40468C`–`0x4046BC`) — a debug path; neither routine has another caller
   [V].

#### §2.10.b `Exit`, `Finish`, `Revive` and the continue screen (Q42)

Handler VAs from the name/handler tables (name index → `0x4647B8[index]`) [M,
the `names.py` command above]: `Start` 0 → `0x42A780`, `Finish` 1 →
`0x42A7B0`, `Exit` 2 → `0x427670`, `Revive` 3 → `0x427760`, the `TITLE`
handler 14 → `0x41D670`, the `MAP` handler 41 → `0x424100`, the continue
handler 42 → `0x424500`.

- **`Exit` (`0x427670`) [V].** Init: clip `EXIT`, `+0x80` := 0, `+0x84` := 30
  (`0x427687`–`0x427694`). Update `0x4276A0`: it fires when the hero is on the
  Exit's plane (`0x4276E7`), is **not airborne** (state bit `0x1`, `0x4276F8`),
  its x is **greater than the plane width in pixels − 50** (`plane+0x10` is the
  width in 16-px cells, written by the `HEAD` reader at `0x414E4B`; compare at
  `0x427701`–`0x427717`) and `|hero y − Exit y| < 48` (`0x427719`–`0x42772B`).
  **The Exit's own x is not read**: the trigger is the last 50 px of the plane
  at the Exit's height. On firing it sets `+0x80` := 1, `0x59F174` := 1,
  `0x52C52C` := 1 (input is cleared every tick while this is set,
  `0x40FBE7`–`0x40FBF8`) and `0x49C4B0` := 1 (`0x42772D`–`0x427744`). It
  **writes neither `0x4645C4` nor `0x4645BC`**. 30 ticks later it starts the
  `−64` transition (`0x4276B9`–`0x4276DB`). For L1 (198 cells wide, `Exit` at
  `(3079, 444)` [M plan 47]): hero x ≥ 3,119 and 396 < hero y < 492 [derived].
- **The sub-level advance is in the level rebuild `0x40F670` [V].** When the
  transition ends without `0x52C59C`, `0x40F670` runs; with lives ≠ 0,
  `0x59C748` = 0 and `0x49C4B0` ≠ 0 it increments `0x4645BC`
  (`0x40F718`–`0x40F720`), reloads the world with `0x40EB80(0)` and rescans the
  spawn with `0x40EC40(0)`. **There is no check against the section's
  sub-level count** at this site [V]; the last sub-level of a section ends on a
  `Finish` instead (section 0's plane 2 has a `Finish` and no `Exit` [M]).
- **`Start` and `Finish` are one object [V].** Both handlers call the same init
  `0x42A820`; placement flag bit `0x4000` (`[placement+0x11] & 0x40`,
  `0x42A853`, `0x42A867`) chooses the role, **not the name**. With the bit set
  it is the **hero's entry point** (§2.10.c). With it clear it is a **lift**:
  update `0x42AD80`, active because `+0x94` = 1 (`0x42A8DC`; `0x42ADF2`). When
  the hero is on its plane, `|hero x − lift x| < 32`, lift y < hero y <
  lift y + 120, not airborne, `0x52C52C` = 0 and the input has bit `0x1000`
  (Up — the bit that subtracts vy at `0x40FDF4`–`0x40FE07`), or any of
  `0x10F0` when lives < 0 (`0x42ADDF`–`0x42ADED`, `0x42AFF2`–`0x42B06F`), the
  hero is launched (vy := −4.0, state `|= 0x43`, `0x42B071`–`0x42B094`),
  pulled to the lift's x and raised (`0x42AF5C`–`0x42AFAF`); once it is 50 px
  above the lift it raises banner kind 4 (`0x42AFE3`), which advances the story
  section and returns to `MAP` (§2.10.a 5). Placement flags measured: every
  `Start` in `MEDIEVAL` planes 0–10 has bit `0x4000` set (11/11) and every
  `Finish`, `Exit` and `Revive` has it clear [M, `spawn_facts.py`]. L1 has no
  `Finish`.
- **`Revive` (`0x427760`) is a checkpoint [V].** Init picks clip `ZWEI` if the
  placement node's run-time bit 0 (`[node+0x14] & 1`) is set, else `EINS`
  (`0x42777C`–`0x427797`). Update `0x4277A0`: when not yet touched, no death in
  progress (`0x59C708` = 0), on the hero's plane, and the Revive's point lies
  inside the hero's box (the current clip's box, §2.10.c, with 20 px slack
  below; `0x4277F0`–`0x427831`), it sets node bit 0, stores its own (x, y) in
  `0x46AB44`/`0x46AB48`, keeps the plane pointer in `0x59E918`, switches to
  `ZWEI` and plays sound `0x21` (`0x427837`–`0x4278AF`). The node bit survives
  a death (the rebuild does not clear it) and is cleared only when the level is
  loaded: `0x40EC40(0)` writes 0 to every node's `+0x14` (`0x40ED8B`) and sets
  `0x46AB44` := −1 (`0x40EC7A`).
- **Respawn rule [V].** After a death the rebuild re-runs the entry point's
  init: if `0x46AB44` ≥ 0 the hero is placed **at the touched `Revive`'s
  (x, y)** with state 0 (`0x42AAB9`–`0x42AB51`); otherwise the entry sequence
  of §2.10.c runs again from the `Start`. After an `Exit` (`0x49C4B0` set) the
  next sub-level's entry point instead places the hero at x = −100 on the
  floor under the `Start` (`0x42A95F`–`0x42AA15`), and `0x49C4B0` is cleared
  when the hero x reaches the `Start`'s x (`0x42ADB5`–`0x42ADD9`) — a walk-in
  [V writes; that the hero walks in on its own is H].

#### §2.10.c The spawn: origin, facing, jump kind, box (Q48, Q40a)

- **The player build `0x40F856`–`0x40FB5D` [V]** (inside the level rebuild
  `0x40F670`): plane from `0x52C540` (the plane of the last type-0 node found
  by the scan `0x40ED7C`), clip `STA1` (`0x40F89A`), a placeholder position
  x = 160, y = the floor probe `0x413B90(plane, 160, 32, 100)`
  (`0x40F8B9`–`0x40F8DB`), vx = vy = 0, entity flags `0x59F258` := 0
  (`0x40F8FD`), **state `0x49C4C4` := 0** (`0x40F9A7`), jump lockout
  `0x59E764` := 0, death timer and contact timer `0x59E938` := 0. Then the
  spawn pass (`0x4123A0`, called at `0x40FB45`) runs every placement's init,
  and the entry point overrides the placeholder.
- **Start origin = the hero's feet, 40 px above the placement [V].** Fresh
  entry (`0x46AB44` < 0, `0x49C4B0` = 0; `0x42ABA0`–`0x42ACDF`): hero x :=
  `Start` x, hero y := `Start` y − 40 (`0x42AC10`, `0x42AC22`–`0x42AC3E`).
  `(x, y)` is the **feet origin (bottom-centre)**, not a box corner: the hero's
  box offsets are signed and straddle it — `STA1`'s box is x −9…+9,
  y −41…−1 [M, `spawn_facts.py`] — and the ground probe reads at the origin
  column `0x413B90(plane, x, y, 4)` (`0x410C4E`–`0x410C66`) [V]. For L1
  (`Start` (89, 407) [M]): the hero's feet start at **(89, 367)** and the first
  solid row under x = 89 is y = 480 (plan 47 G6) — a 113 px drop [derived].
  The engine's "12 × 14 box, top-left on the placement" is therefore not the
  original's [V].
- **The entry sequence [V writes; physical reading H].** The same branch sets
  state `|= 0x53` (airborne `0x1`, straight-jump `0x2`, frozen `0x10`, `0x40`)
  (`0x42AC35`–`0x42AC56`), the entry point's clip `EINS`, its timer `+0x80` :=
  240 (`0x42AC6A`), the camera's left/top to hero x − 160 / floor y − 160
  (`0x42AC77`–`0x42AC9D`; `0x464420` = 160 [M]), `0x59E938` := −1, and starts
  the `+64` transition. While `+0x80` > −200 the input is cleared (`0x42B257`).
  The hero is held (state `0x10` zeroes vx/vy) for **240 ticks**; at 0 the
  entry point clears `0x10`, sets **vy := +4.0 (downward)** and plays sound
  `0x45` (`0x42B18B`–`0x42B1AF`); when the hero is no longer airborne it clears
  `0x40`, plays sound `0x1A` and raises banner kind 1 (clip `ZWEI` of the
  banner object) (`0x42B1ED`–`0x42B242`). Reading the 4 s hold as "the hero
  appears inside the entry object and drops out" is [H].
- **Initial facing: +x (right) [V].** Facing is bit `0x8` of the hero's entity
  flags `0x59F258` (set by Left input `0x8000`, cleared by Right `0x2000`,
  `0x410A8C`–`0x410ABA`; `0x8000` subtracts and `0x2000` adds vx,
  `0x40FDC7`–`0x40FDEF`). The build writes 0 (`0x40F8FD`) and no entry branch
  writes it, so a level starts facing right.
- **Jump kind at level start — answers Q40a [V].** A fresh entry sets bit `0x2`
  (`0x42AC3B`, `or 0x53`): the **straight kind**. The drop therefore draws the
  bit-`0x2` clips (`JMP1`, then `FLO1` once vy ≥ 2.5 — already true at the
  +4.0 launch) and its touchdown arms `LND1` for 10 ticks, state `0x100` being
  clear (§2.6.2 b) [derived from §2.6.2 b]. A respawn at a `Revive` and the
  walk-in after an `Exit` keep the build's state 0 — bit clear, the moving kind
  (`JMP2`/`FLO2`) [V]. The engine's `JUMP_STRAIGHT_AT_LEVEL_START = False`
  (`engine/entities.py`) is therefore wrong for a fresh entry; changing it is
  FL8's, not this pass's.
- **Collision box [V]+[M].** The hero's box for objects is the **current
  clip's** four signed words at animation-node `+0x10..+0x16` (the 2nd–5th of
  the nine `NMY` animation parameters, stored by the `NMY` reader at
  `0x41528D`–`0x4152A3`): left, top, right, bottom, relative to the feet
  origin. The player's contact loop builds it from `[0x59F208] + 0x10`
  (`0x40FB73`–`0x40FB96`, `0x40FE66`–`0x40FEA5`), and the `Revive` test reads
  the same words (`0x4277B0`). It changes with the clip: `STA1` −9, −41, 9, −1;
  `WALK` −9, −42, 9, −1; `JMP1` −11, −31, 11, −4; `JMP2` −10, −33, 12, −2;
  `DUCK` −11, −19, 15, −1 [M, `MAIN.WLD` `Hero` record]. The terrain probes
  this pass read take the origin column only; how wide the hero is against
  walls is FL2's question [H].

#### §2.10.d What takes a life (Q42)

- **Contact with a harmful object [V].** The player update walks the entity
  table at `0x46ABC0` (stride `0x120`, active-slot bitmask `0x52C5A0`,
  `0x40FED7`–`0x40FF0A`; a second bank from `0x59E768`,
  `0x4100B2`–`0x4100C9`). An entity counts when its flags `+0x58` have bit
  `0x20`, it is on the hero's plane, and the hero's clip is not `SPIN` or
  `TUMB` (unless the entity has `0x200000`) (`0x40FF07`–`0x40FF3C`), and its
  box overlaps the hero's (entity box mirrored when its flag `0x8` is set,
  `0x40FF42`–`0x41004F`). The loop is skipped while a death is in progress,
  while `0x59E938` ≠ 0 or `0x52C568` ≠ 0 (`0x40FE8F`–`0x40FEC9`). If the
  entity has flag `0x10000` and the hero is airborne, falling, and its feet
  were above the entity's top on the previous tick, it is a **stomp**:
  `0x412D90` bounces the hero (vy := −4.0) and plays sound 2
  (`0x40FFB6`–`0x410092`). Otherwise the hero is **hurt**:
  `0x412E30(entity x)` (`0x41009A`).
- **The hurt routine `0x412E30` [V].** No effect while dying, while
  `0x59E938` ≠ 0, while `0x59F174` is set or with state `0x20000`
  (`0x412E30`–`0x412E65`). Otherwise state `|= 0x3`. **Without** the power-up
  (`0x52C570` = 0 and `0x59E944` = 0): a death — death timer `0x59C708` := 300,
  `0x59E938` := 1000, vy := −4.0, sound `0x20` (`0x412E9F`–`0x412ECC`).
  **With** it: the power-up is lost (`0x42E850`), sound `0x22`,
  `0x59E938` := 180, vy := −5.0 (`0x412EDB`–`0x412F14`). Both knock the hero
  2.5 px/tick away from the source's x unless state `0x200`
  (`0x412F1E`–`0x412F3C`). While `0x59E938` > 0 the input is cleared and it
  counts down by 1 a tick (`0x4100D0`–`0x4100E7`). Calling `0x52C570`/`0x59E944`
  "a power-up" (a helmet, say) is [H]. Other callers of `0x412E30`: `0x41E0D4`,
  `0x41F849`, `0x428ED1` (inside handlers not identified [H]). Direct writers
  of the 300 death timer: `0x410216` (the pit, below), `0x412EAE`, `0x41BE99`,
  `0x41C0F2`, `0x41C3E3` [V]; which objects own the last three is FL4's [H].
- **The pit [V].** In the player update (`0x4101B4`–`0x41025A`): when state
  `0x200` is clear, vy ≥ 0 and hero y − camera top (`plane+0x8`) > view height
  (`0x464424` = 240 [M]) + 60 — i.e. the feet are **more than 60 px below the
  bottom of the view** — the hero dies: death timer 300, `0x59E938` := 1000,
  vy := −6.0, sound `0x20`, the power-up is dropped. In a `BONUS`-world
  section (world index 5) the same fall instead ends the level and returns to
  `MAP` (`0x4101D3`–`0x41020A`) [V]. **So the original has a pit and no solid
  floor under the plane** — the engine's solid bottom border (plan 47 G7) is
  not the original's [derived]. Where the camera may scroll to is Q45 (FL3).
- **Water [V].** With state `0x200` (set at `0x431C89`, inside the code of the `Water` handler, name index 81, `0x4317F0` [V by address range])
  the threshold is 30 px below the view (`0x41011A`–`0x410126`) and the life
  is taken at once, without the death timer (`0x410160`–`0x410166`), then the
  transition starts or, with no lives and no credits, the game-over banner.
  "Drowning" is [H].
- **The death timer [V].** `0x59C708` counts down once a tick
  (`0x41025F`–`0x41026D`). At **250** (50 ticks after the hit): state
  `|= 0x10`, `0x42FFB0` on the hero (the death clip [H]), entity flag `0x4`,
  and **lives − 1** unless state `0x40000000` (`0x4102AA`–`0x4102FB`). At
  **150**: with lives = 0 and credits = 0 the game-over banner `0x427940(2)`,
  else the `−64` transition (`0x410272`–`0x4102A0`). The transition then
  rebuilds the level (64 ticks) — **214 ticks from the hit to the respawn**
  [derived]. While dying, gravity is 0.125/tick clamped at 6.0
  (`0x410B27`–`0x410B50`). **The lives decrement sites are `0x410166` and
  `0x4102FB`**, nowhere else (the other writers: reset `0x40EE06`, selector
  `0x417C49` and password `0x417A4E` set it, the continue handler sets 0 at
  `0x4245C5` and −1 at `0x42463F`, `0x42B0C3` sets 3, and `0x40F775`,
  `0x42CA3D`, `0x42CAD1` add 1 up to 30) [V].
- **Game over and the spent credit [V].** Lives 0 and credits 0: banner kind 2
  (`0x427A4D`) sets the title flag and `0x52C59C` → the selector resets the
  game (`0x417C27`) → `TITLE`. Lives 0 and credits > 0: the rebuild `0x40F670`
  calls `0x40EC40(0)`, which with lives = 0 scans **only plane slot 19** for
  the entry point (`0x40EC5B`–`0x40EC6E`) — the continue screen [H: which file
  supplies slot 19 is not traced]. The continue handler (index 42, `0x424500`)
  raises banner kind 5 (clip `CONT`), sets lives := 0, shows the credit count,
  and when the hero lands sets **lives := −1** and `0x52C59C`
  (`0x42462B`–`0x424649`). A lift (the rule in §2.10.b, with lives < 0) then
  decides — that the screen carries two of them is [H], the plane was not read:
  a lift at x < 160 (`0x42B0A4`–`0x42B0CE`) **spends a credit**: credits − 1,
  lives := 3, `0x52C59C` := 0, `0x59C748` := 1 — the rebuild then skips the
  sub-level advance and **restarts the same section and sub-level from its
  `Start`** (`0x40F706`–`0x40F72D`; `0x40EC40(0)` resets the `Revive`s). A lift
  at x ≥ 160 leaves `0x52C59C` set with lives −1 → the selector resets the game
  → `TITLE`. Which lift reads "yes" and which "no" is [H] (clips set at
  `0x42A90C`–`0x42A922`). **The only credit decrement is `0x42B0CE`** [V].

## 3. `SFX/*.WAV` **[V]**

All 82 audio files (`SFX` 67, `AMBIENT` 12, `JINGLES` 3) are RIFF/WAVE, PCM
mono, 22,050 Hz, 16-bit, with a plain 44-byte header — exactly the format the
loader documents for replacements `[S2]`. Durations: 31.4 s, 56.2 s, 11.4 s.

## 4. `MUSIC/*.DAT` — a trap **[D]**

These are **not** audio files. Each is an ISO 9660 entry pointing at the first
sector of a CD-DA track (`MEDI1.DAT` = track 2 … `WESTWLD4.DAT` = track 25), and
its length counts 2048 bytes per sector while audio sectors are 2352 bytes. A
file-system copy therefore keeps bytes 24–2071 of every sector and silently
drops 13% of the audio `[S3]`. Extract from the raw image, not from a mounted
disc.

## 5. `DEMOS/DEMOxxNy.DAT` **[V sizes, D layout]**

Input recordings for the title-screen and attract demos, named by section and
sub-level (`DEMO%02dN%d.DAT`) `[S2]`. Measured: 14 files, fixed sizes of
**2,048 bytes (×8)** and **8,192 bytes (×6)** — a size class per demo type,
which is a useful regression handle. The record layout is still unknown (Q6),
and any render-layer change must keep these replaying tick-for-tick.

## 6. `GAME.TXT` **[V shape, D markers]**

Localised strings with `@`, `#` and `&` markers, loaded once at startup `[S2]`.
Measured: 19,532 bytes, 1,321 lines, **0 non-ASCII bytes** (single-byte
encoding, consistent with latin-1/latin-2 for the Polish retail release),
longest line 53 characters, marker counts `#` 420, `@` 4, `&` 1 — so nearly all
strings are `#`-prefixed and the other two markers are rare.

## 7. Registry **[D]**

`HKCU\Software\Psygnosis\Lomax` for configuration `[S1]`, with `System` and
`Extra` subkeys used by the existing loader for its own options `[S3]`. Window
size is stored as `WinW`/`WinH` `[S3]`. There are no save files: progress is a
password `[S1]` `[S2]`.

## 8. Password format **[D]**

The password is XORed with `0xB7A4` and packs section (5 bits), lives (5 bits),
continues (2 bits) and a 4-bit checksum, displayed as eight two-bit gems `[S2]`.
Reimplementing this is LMX-7; the algorithm is documented, the two existing
generators are unlicensed.

## 9. Rules for this repository

1. A format may be **described** here before it can be **parsed** in code.
2. Parsers ship only for **confirmed** layouts; before that, ship a scanner that
   reports offsets.
3. Every parser gets a synthetic-fixture test (`tests/fixtures/synth.py`) and,
   where possible, a byte-exact round-trip test.
4. Never commit a game file, a disc image, extracted art or a full hash of a
   copyrighted binary.
