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
  10–14) `[V]` (§2.11.e).
- 0x50 bytes of editor data (0xFF filler) `[D]`.
- A 256-bit ANIM bitmap at +0x1458 `[D]` — arithmetic confirms it:
  0x1458 + 32 = 0x1478, the measured payload size.
- Colour 0 becomes the transparent key: white, with real white moved to 0x7FFE
  `[V]` (§2.11.e).

Plane sizes are **not** bounded by the screen: measured widths 320–7,200 px and
heights 240–2,928 px. Heights 240 and 256 both occur (the 256-line ones are the
PS1 PAL layout leftovers `[S2]`).

Palettes load only from the HEADs whose file plane bit is in the section's third
loader argument `A`, each overwriting all ten global slots; a tile uses the slot
given by its own `TTAB` palette nibble; a sprite uses the slot in its `ANIM`
header — see §2.11.e `[V]`.

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
u16 flags          # bit 15 = packed (4-bit) pixels; low 15 bits = the sprite's palette slot [V, §2.11.e]
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

**Sprite palette slot `[V]` (§2.11.e).** The `ANIM` header's `flags & 0x7FFF`
is the slot the sprite is converted through. The hero's chunks (`MAIN.WLD` ANIM
26 and 32) carry 0 [M], which is why slot 0 shows the hero's true colours (red
plume 13-15, orange face 1-5, green tunic 16-19, blue helmet/pants 20-23), where
slot 1 maps indices 16-31 to an all-green ramp — the "green hero" defect the
tile slot produced before the split.

**The slot is per `ANIM` chunk, not a global sprite setting** [M]: across all
566 `ANIM` chunks of the 9 worlds the field is 0–9, always one of the ten
slots. In `MAIN.WLD` 95 of 148 chunks carry 0 and the others 1 (1 chunk), 2
(1), 3 (1), 6 (16), 7 (11), 8 (8), 9 (15); in `MEDIEVAL` 0 (10), 1 (19), 4 (4),
5 (12), 6 (27), 7 (11), 8 (2), 9 (1). The earlier reading — that sampling
`Items` (type 35), `Trapdoor` (40), `Explosions` (101) and `Cset` (143) by eye
showed a global setting — is retracted. Reproduce: `env PYTHONPATH=src python3
anim_fields.py "$LOMAX_GAME_DIR" MAIN MEDIEVAL BONUS ED HAUNTED MAP TITLE
VILLAGE WEST` (scratch script, histogram of the field per world).

The engine: `art.SPRITE_PALETTE_SLOT` hard-codes 0 for the sprite paths
(`engine.render_tiles`'s sprite blits, `anim_clip.pose_rgba_frames`, the
`anim-clip` CLI), while tiles stay on `art.DEFAULT_PALETTE_SLOT` (1). That is
right for the hero's chunks but not for the 53 other `MAIN` chunks or for level
sprites; adopting the header field is engine follow-up work, not part of this
pass. Which HEAD's palette set colours the `MAIN`-bank sprites is Q53. `Cset`
(`CSET`/`PINK`/`BLUE`/`GREE`/`RED`) is the candidate for the player's colour
*swap*, not the default selection [H].

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
| 2 | `WAHL` | state `0x80` | `0x4114B2` | [V] (the weapon wheel is open, §2.14.f) | 47 |
| 3 | `HEL8` / `HEL5` / `HEL0` | state `0x8000` with `0x10000`: `HEL8` if state `0x1` else `HEL5`; without `0x10000`: `HEL0` (one-shot) | `0x4114E2` / `0x4114F9` / `0x411529` | [V] test; "helicopter" [H] | 64 |
| 4 | `THR2` / `THR3` / `THR1` | state `0x100`: `THR2` if state `0x4`, `THR3` if `0x1000`, else `THR1`; one-shot | `0x4115C1` / `0x4115D2` / `0x4115D9` | [V] (the helmet throw, §2.14.d) | 91 / 64 / 96 |
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
| player build (uses the spawn plane index; points `0x498F1C` at the spawn plane's record) | `0x40F856` | `0xEC56` |
| `ScrollMap` handler (§2.11.b) | `0x42B670` | `0x2AA70` |
| `Parallax` handler (§2.11.c) | `0x42D460` | `0x2C860` |
| `Birds` handler (§2.11.d) | `0x431110` | `0x30510` |
| `ForceScrolling` handler (§2.11.f) | `0x41C270` | `0x1B670` |
| camera update (in the hero tick; §2.11.f) | `0x4120B2` | `0x114B2` |
| plane depth assignment (§2.11.a) | `0x40F420` | `0xE820` |
| plane blit queue (§2.11.a) | `0x40CE80` | `0xC280` |
| sprite depth (§2.11.a) | `0x416920` | `0x15D20` |
| plane-depth table — **data** | `0x464B28` | — |
| sprite-depth table — **data** | `0x464B48` | — |
| BITMAPINFO palette set — **data** | `0x471B28` | — |
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
`PAGE`/`PARA`/`MACR` are read and discarded (the `PARA` *chunk*; the `PARA`
*clip* of a `Parallax` record is unrelated, §2.11.c), and in `MAIN.WLD` (the "MAIN" bank
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
`Start` placement), records its plane in `0x52C540`, and `0x40F856` points
`0x498F1C` at that plane's *record* (`0x40F875`–`0x40F87C`), which is the camera
(§2.11.f); the hero entity is `0x59F200` — so the player start is the `Start`
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
- **Gravity is skipped for a few ticks after a jump — adopted (FL8).**
  `0x59E764` is set to 5 (jumping while moving) or 10 (a straight-up jump) at
  `0x4106EC`/`0x4106FF`, decremented once a tick (`0x410D36`, in the same tick as
  the set), and while it is non-zero the gravity add (`0x410B19`–`0x410B21`), the
  vertical integration (`0x410BED`–`0x410BF5`) and the ground probe
  (`0x410D4A`–`0x410D52`) are all skipped; x still moves. The hero therefore
  hangs for the launch tick plus N−1 ticks: first vertical move on tick 6
  (moving) / 11 (straight), counting the launch as tick 1. The engine's
  `step_player` gates on `launched or jump_lockout > 1` at the start of the tick
  (its `jump_lockout` is the clip counter, not decremented on the launch tick).
- **Holding the jump raises with reduced gravity — adopted (FL8, normal launch
  only).** Counter `0x59E94C` (16.16): not held → −1 (`0x4105AD`); held with
  counter > 0 and the lockout clear → `new = counter − 0x800`, `vy −= new`,
  counter = new (`0x4105D4`–`0x4105E7`), before the tick's gravity add. The
  normal launch sets `0x9800` (`0x410667`); `0xA800` (`0x41065B`) and `0xB000`
  (`0x4106A5`) are other launch kinds, **not modelled**. The landing reset is
  not traced [H]. A held slide/down input instead uses a **0.125** fall
  (`0x2000` at `0x410B9A`) clamped to **1.0** (not modelled).
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

The jump gravity-lockout and the hold-to-rise counter are adopted by the engine
(FL8); the water/slide gravity, the other launch kinds and the stomp/spring
impulses remain unmodelled.

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
  (`JMP2`/`FLO2`) [V]. The engine's `JUMP_STRAIGHT_AT_LEVEL_START = True`
  (`engine/entities.py`, FL8) now matches; a bare `Player(...)` keeps the
  state-0 kind. `new_game_state` also places a Start-derived spawn so the feet
  are at `(sx, sy − 40)` (`START_FEET_OFFSET_Y`); the 240-tick entry hold and
  the vy +4.0 drop are not modelled [H].
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
  counts down by 1 a tick (`0x4100D0`–`0x4100E7`). `0x52C570` is set by
  picking up an `Items` `HELM` (`0x42C8FF`, §2.12.c), so the power-up is the
  helmet [V]; `0x59E944` is [H]. Other callers of `0x412E30`: `0x41E0D4`,
  `0x41F849`, `0x428ED1` — by address range the `Flue` (16), `Slim` (22) and
  `Boul` (59) handlers, none placed in L1 [V by address range]. Direct writers
  of the 300 death timer: `0x410216` (the pit, below), `0x412EAE`, `0x41BE99`,
  `0x41C0F2`, `0x41C3E3` [V]; by address range the last three lie in the
  `Airs` (7: `0x41BE99`, `0x41C0F2`) and `Forc` (8: `0x41C3E3`) handlers, none
  placed in L1 [V by address range].
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

### 2.11 Backdrop, palette and camera (2026-11-25, FL3)

Recovered by a read-only objdump pass over `LOMAX.EXE` for the first-level plan
([`../roadmap/47-first-level-plan.md`](../roadmap/47-first-level-plan.md), FL3;
Q44, Q45; risk R2). Grades and the reproduce convention are those of §2.10:
**[V]** an instruction in `LOMAX.EXE` carries it, **[M]** measured by running a
command on the user's install, **[H]** guess / interpretation, **[derived]**
arithmetic on graded numbers. The rules below come from the code, so the console
video/screenshot (plan 47 D4) is not needed for them.

**Reproduce.** The scripts are scratch files outside the repository and are not
committed; run them against the user's install (`$LOMAX_GAME_DIR` = install dir,
`$EXE` = its `LOMAX.EXE`):

```
objdump -d -M intel --no-show-raw-insn "$EXE" > /tmp/fl3/lomax.asm
python3 -I tables.py "$EXE"                                   # 89 names -> handler VAs (0x464650 / 0x4647B8)
python3 -I bytes.py "$EXE" 464b28 8 u16                       # plane depth table -> 144 64 32 16 0 0 0 0
python3 -I bytes.py "$EXE" 464b48 8 i16                       # sprite depth offsets -> 3 4 8 10 12 14 6 2
python3 -I bytes.py "$EXE" 4643c0 13 u32                      # default key table (DirectInput codes)
python3 -I bytes.py "$EXE" 466458 4 u8                        # section 0 bytes +0x08..+0x0B -> 1 0 0 0
env PYTHONPATH=src python3 parallax_entries.py "$LOMAX_GAME_DIR" MEDIEVAL   # ScrollMap/Parallax/Birds/ForceScrolling placements
env PYTHONPATH=src python3 para_probe.py "$LOMAX_GAME_DIR" MEDIEVAL 0 11 12 13  # record index, W_A, clips, sprite sizes
env PYTHONPATH=src python3 chunks.py "$LOMAX_GAME_DIR" MEDIEVAL               # chunk order (CELL after all 17 HEADs)
env PYTHONPATH=src python3 pal_probe.py "$LOMAX_GAME_DIR" MEDIEVAL 0 11 12 13  # tile palette nibble per plane
env PYTHONPATH=src python3 colour_probe.py "$LOMAX_GAME_DIR" MEDIEVAL 12 0     # mean colour, engine rule vs original rule
env PYTHONPATH=src python3 sprite_pal.py "$LOMAX_GAME_DIR" MEDIEVAL 0 16 20 21 # ANIM palette field + mean colour
env PYTHONPATH=src python3 anim_fields.py "$LOMAX_GAME_DIR" MAIN MEDIEVAL BONUS ED HAUNTED MAP TITLE VILLAGE WEST  # ANIM palette field per world
env PYTHONPATH=src python3 sky_cover.py "$LOMAX_GAME_DIR" MEDIEVAL 16 160 128 0 -128  # tiled sky coverage of 320x240
env PYTHONPATH=src python3 head_cmp.py "$LOMAX_GAME_DIR" MAIN 0 MEDIEVAL 0    # slot-by-slot HEAD difference
```

Names table (from `tables.py`) [M]: `Forc` index 8 → `0x41C270`; `Bird` 83 →
`0x431110`; `Scro` 87 → `0x42B670`; `Para` 88 → `0x42D460`. (`Brid` 77 is a
different type.)

#### §2.11.a Plane records and draw order

- Plane records are `0x9C` bytes from `0x49B880`, **one per loaded `HEAD`, in
  file order** [V]: the loader discards `HEAD`/`TTAB`/`MAP`/`GNMY` of a plane
  whose bit is not in the sub-level's plane mask (second loader argument,
  `0x41496B`–`0x414997`; the file plane counter `[ebp-0x38]` still counts every
  `HEAD`, `0x41492D`), and the `HEAD` reader advances the record pointer by
  `0x9C` (`0x414E18`–`0x414E27`). So in L1 (section 0, sub-level 0, planes
  `[0, 11, 12, 13]`, plan 47 §1.2) record 0 = plane 0, 1 = plane 11, 2 = plane
  12, 3 = plane 13 [V rule; plane list M].
- Record fields used by this pass [V]: `+0x0` placement-list head (`0x42B696`);
  `+0x4`/`+0x8` scroll x/y in integer pixels (read `0x42B80A`, `0x42B839`; the
  camera writes the hero's plane, §2.11.f); `+0x10`/`+0x14` width/height in
  16-px cells (`0x414E4B`, `0x414E64`); `+0x30`/`+0x32` maximum scroll x/y
  (`0x40ECC2`, `0x40ECD4`); `+0x38` depth (`0x40F49D`); `+0x3C` zoom flag
  (`0x414ECF`/`0x414ED8`).
- **Depth** [V]: `0x40F420` gives every plane whose `+0x3C` is 0 the next value
  of the `u16` table at `0x464B28` (`0x40F494`–`0x40F49D`) = **144, 64, 32,
  16**, 0, 0, 0, 0 [M, initialised data], in load order. The zoom flag is set
  only when the section entry's byte `+0x0B` is non-zero
  (`0x414EA3`–`0x414EB4`); section 0's is 0 [M] → **no zoom in L1**, so L1's
  depths are plane 0 = 144, plane 11 = 64, plane 12 = 32, plane 13 = 16
  [derived].
- **Draw** [V]: `0x40CE80` queues a plane's blits in the bucket list
  `0x471B24[z+1]` (`0x40CE97`–`0x40CE9B`); the frame loop walks the 256 buckets
  from 0 upward (`0x404DA9`–`0x404EB3`, `add edi,4 / cmp edi,0x400`), so a lower
  depth is drawn first = further back.
- **Sprite depth** [V]: `0x416920`–`0x416982` returns plane depth + `i16` table
  `0x464B48[v]` for `v = entity+0x60` in 0..7, where `+0x60 = (placement flags
  >> 10) & 7` (§2.5). Table = **3, 4, 8, 10, 12, 14, 6, 2** [M]. (For v ≥ 8 it
  returns plane depth − v, for v < 0 it returns 248 − v [V].)
- **L1 back-to-front order** [V rule, derived values]: plane 13 tiles (16; they
  have no visible pixel) → plane 13's `Parallax` = the sky (16+3 = 19) → plane
  12 tiles (32) → the two `Birds` (35) → plane 11 tiles (64) → plane 0 tiles
  (144) with its sprites (144 + 2…14) → plane 0's own `Parallax` (flags
  `0x4C00` → v = 3 → 144+10 = 154), drawn **in front of** the playfield.
- **Backdrop planes wrap** [V]: the non-zoom plane blit takes column = (scroll
  x / 16) mod width and row = (scroll y / 16) mod height, with a fix-up for
  negatives (`0x40D2D8`–`0x40D337`), and fills until x < 320 (`0x40D3DD`) and
  y < 240 (`0x40D344`). This is needed: plane 11 is 592 px wide but scrolls to
  x = 1,424 [derived: 2,848 · 50 / 100].
- **No screen clear in L1**: a fill blit is issued only when bit 2 of the
  section byte `+0x08` is set or `0x4699FC` is non-zero
  (`0x404D1C`–`0x404D33`) [V]; section 0's byte is 1 [M]; that `0x4699FC` is 0
  in L1 is [H]. The tiled sky covers the whole 320 × 240 view (0 uncovered
  pixels, `sky_cover.py`) [M], so nothing shows through.

#### §2.11.b `ScrollMap` — per-plane scroll ratio (`0x42B670`; tick `0x42B790`; draw `0x42B7E0`)

- **Variant selection** [V] (`0x42B686`–`0x42B6F7`): key = sub-level
  (`0x4645BC`) + 10 · section (`0x4645C0`) + 11. A placement with flags bit 0
  (and its record's `W_A & 0xF` ≥ 1) is kept only if its 7th parameter p6
  equals the key; a placement without bit 0 is the default, and is removed
  (`0x412B80`, the entity release, which refuses the hero `0x59F200`) when the
  same plane holds a bit-0 placement of the same record whose p6 equals the key.
- MEDIEVAL's p6 values are 41, 42, 61 [M] = section 3 sub-level 0, section 3
  sub-level 1, section 5 sub-level 0 [derived] — exactly the sections that
  reuse planes 11–13 (plan 47 §1.2). L1 (section 0, keys 11–13 for its three
  sub-levels) therefore uses the defaults [derived]: plane 11 placement
  (53, 147) params `(0, 50, 0, 16, 0, 0, 0)`; plane 12 placement (33, 75)
  params `(0, 25, 0, 5, 0, 24, 0)` [M].
- Parameter → entity field [V]: p0 → `+0x84` = p0 · 655 (X drift in 16.16,
  ≈ p0/100 px/tick; `0x42B727`–`0x42B738`); p1 → `+0x88` X ratio in %
  (`0x42B742`); p2 → `+0x90` = p2 · 655 Y drift (`0x42B755`–`0x42B768`); p3 →
  `+0x94` Y ratio in % (`0x42B773`); p4 → `+0x80` = p4 << 16 X offset
  (`0x42B71A`–`0x42B721`); p5 → `+0x8C` = p5 << 16 Y offset
  (`0x42B748`–`0x42B74F`); p6 = the key above.
- Tick `0x42B790` [V]: `+0x80 -= +0x84`, `+0x8C -= +0x90`
  (`0x42B797`–`0x42B7B9`), and appends the entity to the list
  `0x52C4CC[++0x52C55C]` (`0x42B7C0`–`0x42B7CD`; the list's purpose is [H]).
- Draw `0x42B7E0` [V]: unless the entity's plane is the hero's plane
  (`0x42B802`), **plane.x = cam.x · p1 / 100 + offset_x**
  (`0x42B80A`–`0x42B82A`) and **plane.y = cam.y · p3 / 100 + offset_y**
  (`0x42B82D`–`0x42B849`), integer `imul`/`idiv` (truncating), where cam is the
  hero's plane record (`[0x498F1C]` +0x4/+0x8, §2.11.f) and offset is the
  integer part of `+0x80`/`+0x8C`. The zoom branch after it
  (`0x42B84C`–`0x42B8FD`) only runs when plane `+0x3C` ≠ 0.
- **L1 result**: plane 11 x = cam.x · 50/100, y = cam.y · 16/100; plane 12 x =
  cam.x · 25/100, y = cam.y · 5/100 + 24 [V formula, M params]. The hypothesis
  "the second `ScrollMap` parameter is a scroll ratio" is confirmed [V]: it is
  the X ratio in percent. With cam.x ∈ [0, 2,848] and cam.y ∈ [16, 400]
  (§2.11.f): plane 11 x 0…1,424, y 2…64; plane 12 x 0…712, y 24…44 [derived].
  Plane 11 is 320 px tall and plane 12 304 px, so y + 240 stays inside both: no
  vertical wrap is needed [derived].

#### §2.11.c `Parallax` — tiled sprite layers, and the sky (`0x42D460`; tick `0x42D600`; draw `0x42D6B0`)

- The handler sets the entity's clip to `PARA` (`push 0x50415241` + `0x416140`,
  `0x42D48B`–`0x42D497`) [V]. This is the `NMY` record's animation named
  `PARA`, not the `PARA` *chunk*, which the loader discards (§2.8).
- Parameter → field [V]: p0 → `+0x88` X period (0 = no repeat;
  `0x42D51E`–`0x42D522`); p1 → `+0x98` Y period (`0x42D552`–`0x42D556`); p2 →
  `+0x90` = p2 · 655, added to `+0x8C` every tick (`0x42D531`–`0x42D542`,
  `0x42D679`–`0x42D693`); p3 → `+0x94` X ratio % (`0x42D548`–`0x42D54C`); p4 →
  `+0xA0` = p4 · 655 Y drift (`0x42D565`–`0x42D57B`); p5 → `+0xA4` Y ratio %
  (`0x42D581`–`0x42D586`); p6 → `+0x80`, passed to the sprite draw `0x40C270`
  as its 4th argument (`0x42D514`–`0x42D518`, `0x42D887`–`0x42D89B`; its
  meaning is [H]); p7, only when the record's K ≥ 8, is added to y
  (`0x42D4A3`–`0x42D4B7`).
- Placement flags [V]: bit 0 (with the record's `W_A & 0xF` ≥ 1) adds a random
  horizontal sway (`0x42D4BB`–`0x42D4FA`, tick `0x42D60F`–`0x42D673`); bit 1
  (with `W_A & 0xF` ≥ 2) while `0x46441C` is 0 draws it 16 px higher
  (`0x42D5C0`–`0x42D5D9`, `0x42D77D`–`0x42D790`).
- Draw [V]: screen x = x (integer part of `+0x8C`) − plane.x · p3 / 100
  (`0x42D721`–`0x42D733`), reduced mod the X period (`0x42D735`–`0x42D742`); y
  the same with `+0x9C`, p5 and the Y period (`0x42D744`–`0x42D7A5`). The
  drift accumulator is reset to 0 whenever its integer part is a multiple of
  the period (`0x42D70D`–`0x42D718`, `0x42D753`–`0x42D75E`). It then draws the
  clip on a grid starting one period left and up and stepping by the periods
  across the view (`0x42D7F7`–`0x42D8B3`), skipping copies whose box falls
  outside x ∈ [−10, 330], y ∈ [−10, 250] (`0x42D7D6`–`0x42D7F2`; `0x464424` =
  240).
- **The sky (R2 resolved)**: plane 13's only placement is a `Parallax` at
  (0, 128), record 0, flags `0x4000`, params `(160, 128, −17, 0, 0, 0, 0)` [M].
  Record 0's `PARA` clip is one keyframe: sprite byte 17 = `ANIM` type_index 16,
  164 × 129 px, keyframe dy −128 [M]. So the sky is that sprite **tiled every
  160 × 128 px, fixed to the screen (both ratios 0), drifting left by 17/100 px
  per tick** (≈ 10 px/s at 60 Hz) [V rule, M params, derived speed]; flags bits
  0 and 1 are clear, so no sway and no lift [M]. The copies overlap by 4 px
  horizontally and 1 px vertically [derived] and cover the whole 320 × 240 view
  (0 uncovered px) [M]. Plane 13's tiles stay empty, as measured (plan 47
  §1.3). Plane 16 (section 1's backdrop) has three such `Parallax` placements
  (params `(384, 0, −17, 0, 0, 0, 0)`) [M], not part of L1.
- **Plane 0's own `Parallax`** (L1 playfield): placement (1252, 568), record 7
  (its `PARA` clip has three keyframes on sprite byte 18 = ANIM 17, palette
  field 5), flags `0x4C00` → depth 154, params `(1280, 80, 0, 150, 0, 150, 0)`
  [M]: copies every 1,280 × 80 px moving at 150 % of the camera, in front of
  plane 0 [V rule]. What it shows on screen was not looked at [H].

#### §2.11.d `Birds` (`0x431110`; tick `0x431140`)

- Spawn sets x = −1000 (`0x43111D`–`0x431132`) so the first tick re-seeds it;
  the placement's x/y are never used [V].
- Tick [V]: when x − plane.x > 420 or < −100, or y − plane.y < −20
  (`0x431163`–`0x431183`), it re-seeds: clip `EINS` or `ZWEI` at random
  (`0x431189`–`0x43119F`); vx = `0xA000` + (rand & 15) · `0x800` = 0.625…1.094
  px/tick (`0x4311AE`–`0x4311BE`) [V, derived range]; entering from the left at
  x = plane.x − (20 + rand & 31), or (when rand & 4) from the right at x =
  plane.x + 320 + (20 + rand & 31) with vx negated and flag `0x8` set (mirrored
  is the reading [H]) (`0x4311C1`–`0x431227`); y = plane.y + 70 + (rand & 63)
  (`0x43122A`–`0x43124F`); vy = −(rand & 31) · 256 = 0…−0.121 px/tick
  (`0x431251`–`0x43126B`) [derived range]; then it integrates x/y
  (`0x431277`–`0x431298`). `0x43AAD0` is the random source (that it is the C
  runtime `rand` is [H]).
- L1: two `Birds` placements in plane 12 [M] → two birds at depth 35 in
  plane-12 coordinates, so they scroll with plane 12 [derived]; clips
  `EINS`/`ZWEI` = sprite bytes 21/22 (ANIM 20/21, 8 frames each, palette field
  7) [M].

#### §2.11.e Palettes: why the islands came out teal

- **Which HEADs load palettes** [V]: the `HEAD` reader writes the palettes into
  one global set of ten BITMAPINFOs at `0x471B28` + n · `0x528` (biSize `0x28`
  stored at `0x414FA4`; 8 bpp at `0x414FCF`; loop `0x414F12`–`0x4150AA` up to
  `0x474EE0`) **only when the `HEAD`'s file plane bit is in the section's third
  loader argument `A`** (`[ebp+0x10]`, `0x414EE9`–`0x414EF6`); `MAIN` HEADs
  always load (`0x414EE2`–`0x414EE7`). Every qualifying `HEAD` overwrites all
  ten slots. This settles the meaning of plan 47's field `A` (section `+0x04`):
  it is the palette-source plane mask [V]. Section 0 has A = `0x7` and
  sub-level 0 does not load planes 1 and 2, so **L1's palette set is HEAD 0's
  ten slots** [V rule, M A].
- **Colour conversion** [V]: red and blue fields are swapped in place
  (`0x414F24`–`0x414F51`), then each entry is stored as an RGBQUAD whose
  rgbBlue is bits 0–4, rgbGreen bits 5–9 and rgbRed bits 10–14 of the file word
  (`0x41500A`–`0x415060`), each 5-bit field expanded as (c << 3) | 7
  (`0x415030`–`0x415054`). Entry 0 is forced to `0x7FFF`
  (`0x41500D`–`0x415011`) and a real `0x7FFF` becomes `0x7FFE`
  (`0x415017`–`0x415026`). (The engine expands with bit replication,
  (c << 3) | (c >> 2): at most 7 apart per channel [derived].)
- **Which slot a tile uses** [V]: `CELL` follows all 17 `HEAD`s in `MEDIEVAL`
  [M], and the `CELL` reader builds every plane's tile cache through `0x4154B0`
  (called at `0x414C0E`) only then. Each 16×16 tile is converted through
  BITMAPINFO[n], n = the palette nibble (flag bits 8–11) of the record's last
  non-empty cell (`0x41561D`–`0x415629`, used at `0x415AD9`–`0x415B5F`; the
  conversion is a plain copy, `0xCC0020` at `0x415B39`). So **a tile's colours
  = the global set's slot n, n = its own nibble** — this answers Q8's open
  nibble→slot mapping.
- L1 nibbles [M] (`pal_probe.py`): plane 0: 1 on all 2,668 non-empty cells;
  plane 11: 2 on all 323; plane 12: 3 on all 212; plane 13: none (all 300
  empty).
- **Why teal** [M] (`colour_probe.py`, mean of the drawn pixels): plane 12
  (37,748 px) under the engine's rule (its own HEAD 12, slot 1) is RGB
  (37, 79, 71), hue 169°, lightness 0.23 — dark teal; under the original's rule
  (HEAD 0, slot 3) it is RGB (125, 141, 163), hue 215°, lightness 0.56,
  saturation 0.17 — a pale blue-grey, which matches the reference's pale
  islands. Plane 11 (60,116 px): (24, 37, 16) hue 97° vs (55, 71, 74) hue 189°.
  Plane 0 (466,757 px): (39, 54, 30) under both — the playfield is unaffected.
  So the teal is a **palette-selection difference (wrong HEAD and fixed slot
  1), not a blend, a fog or a different palette slot in the data** [V
  mechanism, M colours]; the measured colours need no blend to explain the
  reference.
- **Sprites carry their slot in the ANIM header** [V]: the `ANIM` reader stores
  `flags & 0x7FFF` at the chunk record `+6` (bit 15 → the packed flag at `+8`)
  (`0x414B1D`–`0x414B32`); `0x415DD0` passes `+6` as the decompressor's 4th
  argument (`0x415DFD`–`0x415E0C`), and `0x415E30` converts the frame through
  BITMAPINFO `0x471B28` + that · `0x528` (`0x415FD5`–`0x415FEF`). The
  conversion runs at load (`0x415DD0` is called from the `ANIM` reader at
  `0x414BDD`/`0x414BEF`), with the palette set current at that moment [V].
- Measured fields [M] (`sprite_pal.py`): the sky sprite (MEDIEVAL ANIM 16) →
  slot 4; under HEAD 0 slot 4 its mean colour is RGB (160, 192, 237), hue 215°,
  lightness 0.78 — light sky blue, 20,480 of 21,156 px opaque. Birds (ANIM 20,
  21) → slot 7. The hero (`MAIN.WLD` ANIM 26 and 32) → slot 0; across all 566
  `ANIM` chunks the field is 0–9 and varies per chunk (`MAIN`: 95 of 148 carry
  0), so the slot is per chunk (§2.6), so the engine's fixed
  `SPRITE_PALETTE_SLOT = 0` is right for the hero's chunks only. Which HEAD colours
  `MAIN`-bank sprites — `MAIN`'s own (loaded by `0x40836A`, with `MAIN`
  palettes always loading) or the level's — is new **Q53**; `MAIN` HEAD 0 slot
  0 and `MEDIEVAL` HEAD 0 slot 0 differ in 9 of 256 entries [M].

#### §2.11.f The camera (`0x4120B2`–`0x4122B7`, in the hero tick) and `ForceScrolling`

- The camera is the hero's plane record [V]: `0x40F856`–`0x40F87C` points
  `0x498F1C` at `0x49B880` + `0x9C` · (spawn plane), and the camera writes its
  `+0x4` (x) and `+0x8` (y), integer px.
- Level start [V]: cam.y = hero_y − 160 (`0x40FA67`–`0x40FA8C`, `0x464420` =
  160 [M]); vertical speed `0x59E78C` = 0 (`0x40FA8F`); forced-y word
  `0x52C588` = sentinel `0xFF439EB2` (`0x40FAE1`). The level build `0x40F856` runs
  straight-line to `0x40FAEB`. It first places the hero provisionally at x = 160
  (`0x40F8B9`) and y = the floor probe `0x413B90` from (160, 32)
  (`0x40F8C3`–`0x40F8DB`); `0x40FA85`–`0x40FA8C` then sets cam.y = that
  provisional y − 160. Only after that does `0x40FB45` call `0x4123A0`, which
  runs the spawn pass `0x4126A0` (call at `0x412423`), where the `Start` handler
  moves the hero (§2.10.c). So in the first ticks cam.y eases from the
  provisional value toward the `Start` position, while cam.x snaps on the first
  tick (no smoothing). The provisional y in L1 was not measured [H].
- Per tick, in this order [V]:
  1. If `0x52C588` ≠ `0xFF439EB2`, cam.y = `0x52C588`
     (`0x4120B7`–`0x4120DD`; it undoes the shake below).
  2. Hero state bit `0x80` skips the whole update (`0x4120E0`–`0x4120E7`).
  3. **Horizontal**, unless hero bit `0x20` (`0x4120ED`): **cam.x = hero_x −
     160** (`0x4120F1`–`0x412102`), then < 0 → 0 (`0x412111`–`0x412115`), >
     plane `+0x30` → plane `+0x30` (`0x41211D`–`0x41212A`). **No dead zone, no
     lead, no smoothing.**
  4. **Vertical target speed** t = (cam.y − bias − hero_y + 160) · 65536 / 16
     (`0x41212C`–`0x41215E`): the error divided by 16, as 16.16 px/tick; bias =
     `0x52C590`.
  5. The speed v (`0x59E78C`) moves toward t by `0x4000` (0.25 px/tick per
     tick), or by `0xC000` (0.75) while v has the opposite sign, and never
     passes t (`0x412161`–`0x4121C1`).
  6. Unless hero bit `0x40` (`0x4121C6`–`0x4121CD`): cam.y −= v, kept in 16.16
     at `0x52C5BC` with the integer in `0x52C5BE` (`0x4121CF`–`0x4121EA`).
  7. **Shake** while `0x59E93C` ≠ 0: on even frames a random offset of
     ((rand & 15) + 15) · counter / 64 (negated, and the counter decremented,
     on frames where frame-counter bit 1 is set; `0x4121EC`–`0x412237`) is
     added to cam.y after saving cam.y to `0x52C588` (`0x412252`–`0x412269`);
     at 0 the sentinel is restored (`0x412246`). Who sets `0x59E93C` was not
     traced.
  8. **Clamp y**: < 16 → 16 (`0x41226B`–`0x41227B`; 32 when zoomed,
     `0x412281`–`0x412298`), > plane `+0x32` → plane `+0x32`
     (`0x41229E`–`0x4122B7`).
- **Bias** (`0x40FCF7`–`0x40FD37`) [V]: −40 while hero bit `0x2000000`;
  otherwise +40 while pad bit `0x0001`; otherwise −40 while pad bit `0x0004`;
  otherwise 0. The pad word `0x464434` is built in `0x416660`–`0x416803` from
  the key table at `0x4643C0`, whose initialised DirectInput codes are [M]: 203
  → `0x8000`, 205 → `0x2000`, 200 → `0x1000`, 208 → `0x4000`, 17 → `0x0040`,
  18 → `0x0020`, 16 → `0x0080`, 57 → `0x0100`, 157 → `0x0008`, 31 → `0x0010`,
  **209 (Page Down) → `0x0001`**, **201 (Page Up) → `0x0004`**, 25 →
  `0x0800`. So Page Down lowers the view by 40 px (look down) and Page Up
  raises it (look up) [V for the bits, M for the default codes; whether the
  player can remap them was not traced, H]. The bit layout is the PlayStation
  pad's (up `0x1000`, right `0x2000`, down `0x4000`, left `0x8000` from the
  arrow keys' codes 200/205/208/203) [M].
- **Clamps** (`0x40ECB7`–`0x40ECD4`) [V]: plane `+0x30` = (width_cells − 20) ·
  16 = width − 320, plane `+0x32` = height_cells · 16 − 240. L1 plane 0
  (198 × 40 cells): **cam.x ∈ [0, 2,848], cam.y ∈ [16, 400]** [derived].
- **The rule in words**: horizontally the view is locked to the hero, feet
  origin at screen x 160, except within 160 px of the plane's ends; vertically
  it eases toward keeping the feet at screen y 160 − bias (two thirds of the way
  down a 240-line view), closing 1/16 of the error per tick with the speed
  change capped at 0.25 px/tick per tick (0.75 when reversing); y never goes
  above 16 [V].
- **Compared with the engine (plan 47 G9)** [derived]: horizontally the
  engine's "centre and clamp" is the same rule, if it centres on the feet origin
  x; vertically it differs (centred instead of 160 px from the top, immediate
  instead of eased, top clamp 0 instead of 16, no look-up/look-down).
- **`ForceScrolling`** (`0x41C270`; tick `0x41C2E0`) [V]: spawn stores the
  target speed p0 · 655 (p0/100 px/tick) at `+0x80` (`0x41C28B`–`0x41C29C`), the
  hero's vx as the current speed `+0x84` (`0x41C2A2`–`0x41C2A7`) and cam.x in
  16.16 at `+0x88` (`0x41C2AD`–`0x41C2B9`), and sets hero bits `0x28000020`
  (`0x41C2BF`–`0x41C2CB`), whose `0x20` turns off the horizontal follow and its
  clamp. Each tick the speed approaches the target through
  `0x413A80(speed, target, 0x1000)` (`0x41C2E1`–`0x41C300`; the step size is
  [H]); unless the death timer `0x59C708`, `0x59F174` or `0x59E75C` is set,
  cam.x advances by exactly 1 px when the speed equals the target, otherwise by
  the speed (`0x41C306`–`0x41C35A`); the hero is pushed to stay within screen x
  16…304 and its vx clamped to the scroll speed at those edges
  (`0x41C35D`–`0x41C3BA`); hero x − cam.x < 20 while `0x59E950` = 2 kills the
  hero (death timer 300, vy −5.0; `0x41C3BF`–`0x41C428`) — crushed by the scroll
  is the reading [H]. In `MEDIEVAL` it is placed only in plane 10, with p0 = 100
  (1 px/tick) [M]; **L1 has no `ForceScrolling`, so no autoscroll** [M].

**What stays open.** [H]: `Parallax` p6 (the 4th argument of `0x40C270`); what
plane 0's `Parallax` shows; the purpose of the `ScrollMap` list `0x52C4CC`;
whether the backdrop draw (which reads the camera) runs before or after the
camera update within a frame (a one-frame lag); who sets hero bits
`0x20`/`0x40`/`0x80`/`0x2000000` besides `ForceScrolling`, and the shake
counter `0x59E93C`; Q53. Builders (FL9, FL12) take the ratios, order, sky
source, palette rule and camera rule from here.

### 2.12 Placed objects of L1 and the HUD (2026-11-25, FL4)

Recovered by a read-only objdump pass over `LOMAX.EXE` for the first-level plan
([`../roadmap/47-first-level-plan.md`](../roadmap/47-first-level-plan.md), FL4;
Q46, Q47; AC5, AC6, AC11). Grades and the reproduce convention are those of
§2.10. L1 = `MEDIEVAL` section 0 sub-level 0, playfield plane 0. The
`Henchlemming`'s behaviour is §2.13 (FL4b); here it is only classified.

**Reproduce.** Scratch files outside the repository, not committed:

```
objdump -d -M intel --no-show-raw-insn "$EXE" > /tmp/fl4/lomax.asm
python3 -I tables.py "$EXE"                                   # 89 names -> handler VAs, sorted by VA (gives each handler's address range)
env PYTHONPATH=src python3 names15.py "$LOMAX_GAME_DIR"         # plan 47 §6 script C + handler VA + placements (x, y, flags, params)
env PYTHONPATH=src python3 l1_types.py "$LOMAX_GAME_DIR"        # placement -> NMY record index -> its clips
env PYTHONPATH=src python3 gen_chain.py "$LOMAX_GAME_DIR"       # bit-15 placements and each Generator's chain
env PYTHONPATH=src python3 hud_clips.py "$LOMAX_GAME_DIR" MAIN Display Icons Items Krug Trapdoor   # keyframes, offsets, sprite sizes
env PYTHONPATH=src python3 poses.py "$LOMAX_GAME_DIR" MEDIEVAL Jumppad            # pose count (keyframes with flag 0x80)
env PYTHONPATH=src python3 hud_boxes.py "$LOMAX_GAME_DIR"       # screen boxes of the HUD draw calls [derived]
python3 -I bytes.py "$EXE" 46441c 1 u32                       # -> 0
python3 -I bytes.py "$EXE" 466818 6 tag                       # -> VIER FUNF SECH EINS ZWEI DREI
python3 -I bytes.py "$EXE" 466830 6 hex                       # -> 0x49c4c0 0x59f1e0 0x59f320 0x46abb8 0x4777d4 0x52c544
python3 -I cstr.py "$EXE" 466920 4669d0 466974 466904 4669b4 4669c0 466984   # Display Icons Items Krug Trapdoor Inserts Classic
```

#### §2.12.a How a placed object lives (the shared machinery)

- **Dispatch [V].** The spawn pass `0x4126A0` turns a placement into an entity
  and calls the type's init through `0x4647B8[index]` (`0x4127CE`). An init sets
  the update pointer `+0x18`, optionally a draw pointer `+0x1C` (0 = the default
  draw, `0x40C270(entity, 1000, 0, 0)`, `0x40F3A1`–`0x40F3AB`) and forces a clip
  with `0x416140(entity, tag)` (the tag is the byte-swapped four-letter name
  pushed as an immediate).
- **Entity flags `+0x58` [V]**, read by the shared code: bit `0x4` — not drawn
  (the update loop leaves it out of the draw mask, `0x40EF89`–`0x40EF90`); bit
  `0x2` — not updated unless bit `0x4000000` (always updated) is set
  (`0x40EF6D`–`0x40EF84`); bit `0x40` — drawn in **screen coordinates**, the
  camera is not subtracted (`0x40C50C`–`0x40C52F`); bit `0x8` — mirrored; bit
  `0x20` — hurts the hero on contact (§2.10.d, `0x40FF07`); bit `0x10000` — can
  be **hit** (below). Removal `0x412C50` sets `0x6` (`0x412D00`–`0x412D03`).
- **When a placement spawns [V].** At level build `0x4123A0` spawns every
  placement whose flags have `0x4000` (`0x412411`–`0x41242F`; in L1: `Start`,
  `Music` `0x4001`, `Parallax` `0x4C00`). The windowed spawn `0x412450` spawns
  the rest as the camera nears, but **skips placements with flag `0x2000`**
  (`test [node+0x11], 0x20` at `0x4125A0`) and those already spawned
  (`0x4125AA`). So placement flag `0x2000` means **"spawned only by a
  trigger"** — in L1 by a `Generator` (`0x42D22F` calls `0x4126A0`). Plan 47
  §1.4's reading of the `Henchlemming`'s `0x2000` as "an initial facing [H]"
  does not hold; the plan file is not edited by this pass.
- **Contact tests [V].** `0x414390` — the hero's box overlaps the entity's box
  (same plane, no death in progress). `0x413510` — the entity is a
  **platform**: the hero lands on its top and `0x59C744` := the entity
  (`0x41368F`). `0x413E40` — the entity is **hit**: true if `+0x58` has
  `0x20000` (set by a projectile through `0x414130`, `0x41423F`), or it has
  `0x10000` and the hero's current clip is `SPIN` or `TUMB`
  (`0x413E97`–`0x413EA3`) and the boxes overlap. Plan 47 revision 3 (D7)
  brings `SPIN`, the helmet throw and `TUMB` into scope; they are specified in
  §2.14.
- **Helpers [V].** `0x4162D0(name)` finds a record by name in the `MAIN.WLD`
  bank (`or 0x100`, `0x4162E9`) — `Krug`, `Trapdoor`, `Display`, `Icons`,
  `Inserts`, `Classic` are `MAIN` records; `0x4160E0(clip)` counts a clip's
  poses (keyframes with flag `0x80`); `0x4161B0` advances the 8.8 pose position
  `+0x6A` by `+0x68` and returns 1 when it wraps; `0x412B50` moves an entity to
  another slot bank (copies it, removes the original) — what the bank changes
  is [H].
- **Shared enemy-defeat routine `0x42CD00`** ([V] writes; the `Henchlemming`'s use: §2.13.g):
  spawns a `Classic` lemming (`MAIN` record, clip `CLA1`;
  `0x42CD06`–`0x42CD54`), adds 1 to the freed-lemming counter `0x52C5A8` — at
  50 it sets the bonus flag `0x59C718` and resets the counter to 0
  (`0x42CD1B`–`0x42CD37`) — sets the HUD flash timer `0x52C700` := 60
  (`0x42CD3C`), and drops one coin when the enemy's x is odd
  (`0x42CDE4`–`0x42CDED`). Callers: `0x41F878`, `0x42030D`, `0x420A1C`,
  `0x421A4E`, `0x42DDF4` (the `Henchlemming`), `0x42E06F`, `0x42E386`,
  `0x42E5C8` — by address range the `Slim`, `Cowb`, `Drac`, `Were`, `Henc`,
  `Barr`, `Muta`, `Zomb` handlers [V by address range].

#### §2.12.b The 15 names: role, idle clip, contact, visibility

| Name (count) | Index → handler | Role | Idle clip | At contact | Drawn? | Grade |
|---|---|---|---|---|---|---|
| `Beestjes` (19) | 52 → `0x4270A0` | ambient critter (a bug is the reading [H]) | `EINS` or `DREI`, by bit 0 of `0x43AAD0` (`0x4270B2`–`0x4270C8`) | walks at ±0.125 px/tick (`0x2000`, `0x4270D5`–`0x4270E0`) and turns on random timers (`0x42724F`–`0x42726D`); when the hero touches it (`0x414390`, `0x4271D5`) it switches to `ZWEI` (from `EINS`) or `VIER` (from `DREI`) and flies off at vy −1.0…0 px/tick (`0x42728B`–`0x4272F6`; flight `0x427176`–`0x4271AC`). No `0x20`/`0x10000`: harmless | yes, default draw | [V] |
| `Henchlemming` (8) | 84 → `0x42DD70` | **enemy** | `STAY` (`0x42DD82`); mirrored when x & `0x10` (`0x42DDA8`–`0x42DDAF`) | `+0x58` gets `0x20` (hurts the hero, §2.10.d) and `0x10000` (can be hit; stomp per §2.10.d) (`0x42DD7F`–`0x42DD90`); behaviour, contact and defeat: §2.13. The placement at (1018, 320) has flag `0x2000` and is spawned only by the `Generator` at (1231, 336) [M] | yes | role [V]; behaviour §2.13 |
| `Rope` (5) | 67 → `0x429F60` | **climbable rope** | `ROPE`; draw `0x42A280` paints keyframe 0 p1 times stepping y by 32, then keyframe 1 (`0x42A292`–`0x42A2D9`) | length = p1 · 32 px (`0x429F9A`–`0x429FA1`). Grab `0x413D60`: hero airborne, \|hero x − rope x\| ≤ 2 and rope y + 20 ≤ hero y ≤ rope y + length + 20 → hero x := rope x, vx = vy = 0, state \|= `0x1010` (`0x413DAC`–`0x413E05`). Then (update `0x42A000`) input `0x1000` (Up) climbs and `0x4000` (Down) descends 1 px/tick within that span, leaving the bottom releases (`0x42A0D3`–`0x42A161`); the jump input releases with vx ±2.0 (`0x42A06E`–`0x42A0C9`), being hurt releases (`0x42A019`–`0x42A04F`); 10-tick re-grab delay (`+0x80` := 10). L1 p1 = 5, 3, 4, 5, 3 → 160, 96, 128, 160, 96 px [derived]; placement flags `0x100`/`0x200` reach `+0x58`, meaning [H] | yes | [V] |
| `Generator` (4) | 86 → `0x42D0D0` | **invisible spawn trigger** | none (no clips) | `+0x58` \|= `0x4` (`0x42D0E0`); target = the placement's resolved extra word (`0x42D0DA`–`0x42D0E3`), none → removed (`0x42D0F7`); height = p1, or 64 when p1 = 0 (`0x42D10A`–`0x42D11E`); repeat = placement flag bit 0 (`0x42D128`–`0x42D145`). When the hero (same plane) has the generator's x inside its box's x-span and its box's y-span overlaps [y − height, y] (`0x42D18F`–`0x42D1DA`), it spawns the target and then each placement the target's own extra word names, skipping those already spawned (`0x42D228`–`0x42D25E`); a one-shot generator then removes itself (`0x42D287`–`0x42D292`). L1: all four flags `0x8000`, p1 0 → 64 px, one-shot [M/derived]; chains: (424, 560) → `Pots` (521, 560); (1231, 336) → `Henchlemming` (1018, 320); (1129, 544) → `Pots` (1238, 464); (1934, 272) → `Pots` (2032, 240) [M, `gen_chain.py`] | **hidden by design** | [V] |
| `Jumppad` (3) | 68 → `0x433ED0` | **springboard platform** | `PAD` pose 0, held: the animation advances only while `+0x80` = 1 (`0x433F48`–`0x433F59`) | the hero stands on it (`0x413510` with a per-pose surface-height function `0x433F20`, table `0x466870`; `0x433F5B`–`0x433F69`) → sound `0x3F` once, the pad animates; when its pose (`+0x6A >> 8`) equals the launch pose — poses − 2, or 4 when poses > 5 (`0x433EFC`–`0x433F18`; `PAD` has 9 poses [M] → 4) — the hero gets state \|= `0x403`, **vy := −6.0** (`0xFFFA0000`) and the hold counter `0x59E94C` := `0xA000`, sound `0x35` (`0x433FA0`–`0x433FDE`); at the wrap it re-forces `PAD` and stops (`0x433FF2`–`0x434001`). The normal jump is −4.0 (§2.9) | yes | [V] |
| `Pots` (3) | 85 → `0x42BEE0` | **breakable container** (not a platform: no call to `0x413510` in `0x42BEE0`–`0x42D0CF` [V by scan]; no `0x20`: harmless) | record replaced by `MAIN`'s `Krug` (`0x42BFBC`–`0x42BFC9`), clip `CLAY` (`0x42BFD5`) | content = p1 (`0x42BEED`–`0x42BEF1`); `+0x58` \|= `0x10000` (`0x42BFDA`). With placement flag `0x2000` it attaches `ROCK` (`0x42BFFE`–`0x42C004`) and starts 40 px low, launched at vy −4.0 (`0x42C00C`–`0x42C03C`) and pulled back to its placement y (`0x42C184`–`0x42C18D`) — "it pops out of the ground" is [H]. **Hit** (`0x413E40`, `0x42C067`): sound `0x11`, a `LID` child flies off at vy −6.0, vx ±2.0 (`0x42C0C9`–`0x42C132`), and the pot releases its content (`0x42C2E0`): p1 −200 empty (`0x42C367`–`0x42C372`); p1 < 0 → −p1 coins (`0x42C37C`–`0x42C3BC`); 0 → an `Items` `HELM` (`0x42C42C`–`0x42C48B`); 1 → an `Items` `UP` (`0x42C490`–`0x42C4EB`); 2–7 → an `Icons` clip for weapon p1 − 2 (`0x42C4ED`–`0x42C55E`; "ammo" [H]); then content := −200 (`0x42C56B`). Hit again it drops one coin when its x is odd and shatters into `BOOM` debris (`0x42C590`–`0x42C5DB`, §2.14.h). L1: (521, 560) p1 0 → helmet; (1238, 464) p1 −5 → 5 coins; (2032, 240) p1 0 → helmet; all three flags `0x2000` → spawned only by their `Generator` [M] | yes, once its `Generator` fires | [V] |
| `Moneybag` (2) | 57 → `0x428190` | **hanging coin bag** | `HANG` (`0x428191`), own draw `0x428400` passing a rotation argument `+0x80`/10 (`0x428400`–`0x42841C`); `+0x80` swings between ±400 (`0x428226`–`0x428280`; "swinging" is the reading [H]) | `+0x58` \|= `0x10000` (`0x4281B1`), no `0x20`: **not stompable, not harmful**. **Hit** (`0x413E40`, `0x428287`) → clip `JUMP`, falls with \|vx\| = 1.0 + (x & 31)/64 px/tick, signed like the hero's vx at the hit (`+0x54`, stored by `0x413E40` at `0x413F43`), y + 32, default draw, `0x10000` cleared (`0x428297`–`0x4282FC`); gravity 0.1875/tick capped at 5.0 (`0x428391`–`0x4283A3`), bounces off walls (`0x42837A`–`0x42838E`); on the ground sound `0x4A`, vy := −4.0 (`0x4283DB`–`0x4283EA`), and when its pose position reaches 2.0 (`+0x6A` = `0x200`) it releases **3 coins** (`0x428323`–`0x428373`; velocities from `0x4645E8`). It bursts on every landing until the despawn window releases it (Q56, §2.14.h) | yes | [V] |
| `Exit` (1) | 2 → `0x427670` | level end (§2.10.b) | `EXIT` | §2.10.b: the last 50 px of the plane at its height | yes | [V] |
| `Lorock` (1) | 69 → `0x4339B0` | **talking NPC** (the wizard) | `HAT` (`0x433A1F`) with four `STAR` satellites (`0x433A0D`–`0x433A17`) in its own draw `0x433DC0`; the hat bobs at ±0.25 px/tick, flipping every 32 ticks (`0x433AFE`–`0x433B2F`) | touch (`0x414390`, `0x433AA5`) → `APPE` (`0x433ACA`), then `STAY`/`TALK`/`EXHA`/`BLAH` at random every 60–183 ticks (`0x433CB9`–`0x433D3A`), with a speech-bubble child (draw `0x433DF0`, created at `0x433B9E`); message index = p1 (`0x433A49`; L1 p1 = 0). When the hero is more than 100 px away horizontally or 80 px vertically → `DISA`, sound `0x1B`, removed when `DISA` ends (`0x433D47`–`0x433D85`, `0x433C84`–`0x433C95`). **No write** to lives, coins, power-up or hero state in `0x4339B0`–`0x433ECF` [V by scan] | yes | [V] |
| `Music` (1) | 37 → `0x423A60` | **music cue** | none | at spawn: p1 > 0 → `0x40E0B0(p1)` (`0x423A65`–`0x423A6E`; "plays track p1" [H]); flag bit 0 with K ≥ 1 → `0x59F170` := 1, else 0 (`0x423A76`–`0x423A92`) — the `Exit` copies it to `0x59E75C` (`0x42774E`); then removes itself (`0x423AA1`). L1: p1 1, flags `0x4001` (spawned at load) | **hidden by design** | [V] |
| `Parallax` (1) | 88 → `0x42D460` | foreground backdrop layer (§2.11.c) | `PARA`, own draw `0x42D6B0`, screen-space flag `0x40` (`0x42D490`) | none | drawn as a tiled layer (§2.11.c), not as a sprite at its placement | [V] |
| `Revive` (1) | 3 → `0x427760` | checkpoint (§2.10.b) | `EINS`; `ZWEI` once touched | §2.10.b | yes | [V] |
| `Start` (1) | 0 → `0x42A780` | hero entry point (§2.10.c) | record replaced by `MAIN`'s `Trapdoor` (`0x42A780`–`0x42A791`); fresh entry forces `EINS` and sets `+0x58` \|= `0x4` (`0x42AC46`–`0x42AC62`), timer 240; at 120 it calls `0x42B2D0(4)` (`0x42B163`–`0x42B16B`, effect [H]), at 104 it clears `0x4` (`0x42B179`–`0x42B184`) | the shared init also **creates the HUD** (`0x42A862` → `0x42A2F0`) unless the demo flag `0x52C6D0` is set (`0x42A859`) | **hidden for the first 136 ticks** of a fresh entry [derived: 240 − 104], then `Trapdoor` `EINS`; also hidden on the after-`Exit` walk-in (`0x42AA1A`–`0x42AA20`) and on a `Revive` respawn when the node's bit 0 is set (`0x42AB57`–`0x42AB5D`) | [V] |
| `Thief` (1) | 44 → `0x4249D0` | **coin thief** | `STAY` (`0x4249D1`) | `+0x58` \|= `0x90000` (`0x4249F9`: `0x10000` hittable, `0x80000` [H]); no `0x20`: no damage. Hit → knocked away vx ±2.5, vy −4.0, 20 ticks, `0x10000` cleared (`0x424BE8`–`0x424C18`). With `+0x8C` set and \|thief x − hero x\| ≤ 4, \|thief y − hero y + 10\| ≤ 8 it **grabs** the hero: clip `GRAB`, update `0x424A30`, draw `0x424B40` at the hero's position, up to 10 coins (`0x424CDB`–`0x424D68`); every 16 ticks one coin leaves `0x498F2C` and flies out as a collectable coin (`0x424AB7`–`0x424AFD`); it lets go when the hero has no coins after a 30-tick hold, or is hurt/dying (`0x424A50`–`0x424AB1`), with vy −4.0, vx ±3.0 (`0x424B0C`–`0x424B34`). It moves with `WALK`/`JUMP` (`0x424D77`–`0x424E60`); what sets `+0x8C` and the pursuit rule are [H] | yes | [V] |
| `Ufos` (1) | 53 → `0x427300` | **ambient spawner** (rising objects; "UFOs/bubbles" [H]) | none for the spawner; children take a random clip of its record (L1: record 41, `EINS`, `ZWEI`, `DREI` [M]) (`0x42739F`–`0x4273BD`, `0x42741F`–`0x427435`) | spawner `+0x58` \|= `0x4` (`0x427320`–`0x427326`); every p1 ticks (`0x4273DE`–`0x427406`) a child appears at the view's edge: from below (x = cam.x + random · 4/3 − 10, y = cam.y + 240 + 10) when \|p3\| > \|p2\| (`0x427494`–`0x4274EB`), else from the left or right edge (`0x427521`–`0x427590`); velocities p2 · 650, p3 · 650 in 16.16 (`0x427329`–`0x427361`); the child update `0x4275F0` only integrates velocity (no contact test). L1: p (10, 0, −200) → a child every 10 ticks rising from the bottom at −2.30…−0.33 px/tick [derived] | spawner **hidden by design**, children drawn | [V] |

- **Hidden by design (AC6) [V]:** `Generator` (4), `Music` (1), the `Ufos`
  spawner (1; its children are drawn); `Start` for its first 136 ticks;
  `Parallax` is drawn, but as a layer. The three `Pots` and the `Henchlemming`
  at (1018, 320) do not exist until their `Generator` fires. So of 52
  placements, 6 are never drawn as a sprite at their placement (4 + 1 + 1) and
  1 more (`Parallax`) is a layer [derived].
- **Which the route needs (Q47) [H]:** the handlers fix the mechanics, not the
  route. `Jumppad`s are platforms that launch at −6.0 vs the normal −4.0;
  `Rope`s are climbable over 96–160 px; `Pots` are not platforms and only hold
  pickups. Whether the `Start` → `Exit` route needs a `Jumppad` or a `Rope` is
  for the solver (FL16). **Collecting a `Moneybag` (AC12) needs a hit** —
  `SPIN`/`TUMB` or a projectile (§2.12.a) — brought into scope by plan 47
  revision 3 (D7, D8; §2.14).

#### §2.12.c Coins, lives and the other counters

- **A coin is worth 1 [V].** A coin item is created by `0x42C240` (`MAIN`
  `Items`, clip `COIN`, `+0x84` = −1; `0x42C24B`–`0x42C2DB`); after a 40-tick
  delay (`+0x80` := 40, `0x42C2B6`) touching it (`0x414390`, `0x42C7EA`) adds 1
  to the coin counter `0x498F2C` (`0x42C809`–`0x42C80F`). **At 100** the counter
  becomes 0, `0x59E770` := 1 and a screen-space `Items` `UP` starts at (190, 40)
  moving right (vx 0.5, `0x42C81D`–`0x42C8C1`); when its x passes 295 the lives
  go up by 1, at most 30 (`0x42CAA9`–`0x42CAD6`).
- **What a `Moneybag` is worth:** 3 coins per burst (row 7) [V]; 3 more
  every landing (§2.14.h, Q56). Other coin sources in L1: the `Pots` at (1238, 464),
  5 coins; any defeated enemy with an odd x, 1 (§2.12.a). Sinks: the `Thief`, 1
  per 16 ticks while it holds the hero.
- **Lives** (`0x52C56C`, §2.10.d): + 1 for an `Items` `UP` touched
  (`0x42CA25`–`0x42CA3D`) and for 100 coins, capped at 30 (`0x42CA37`,
  `0x42CACB`) [V].
- **Helmet [V]:** touching an `Items` `HELM` sets `0x52C570` when neither
  `0x52C570` nor `0x59E944` is set, otherwise the spare `0x59F1E4`
  (`0x42C8E8`–`0x42C90B`). This is the "power-up" of §2.10.d.
- **Freed lemmings** `0x52C5A8` (§2.12.a): + 1 per defeated enemy, 50 → the
  bonus flag and back to 0 [V].
- **Weapon selection** `0x52C58C` cycles 0–5 on the input bits `0x8000`/`0x2000`
  (`0x430DAF`–`0x430DF9`, in the weapon wheel `0x430BA0`/`0x430C90` opened by
  the `0x0100` input, §2.14.f); its six counts are the u16 words listed by `0x466830` (all 0 at reset).
- **Initial values (new game, reset `0x40EDC0`) [V]:** lives 3 (`0x40EE06`),
  coins 0 (`0x40EE11`), freed lemmings 0 (`0x40EE0C`), weapon selection 1
  (`0x40EDE3`), the six weapon counts 0 (`0x40EDC7`–`0x40EE00`), helmet and
  spare 0 (`0x40EE16`–`0x40EE1B`), `0x59E770` 0 (`0x40EE2A`). The attract-demo
  setup also clears them: `0x41C939`–`0x41C99A` zeroes the six weapon counts,
  the freed-lemming and coin counters, the helmet and spare, the bonus flag and
  `0x59E770`, and sets the weapon selection from the demo table `0x466414`
  (`0x41C992`–`0x41C9A0`) [V]. No level load resets the coin or lemming
  counters (their other writers are the HUD's mod-100 store-back, the pickups,
  the `Thief` and `0x42CD00`) [V by scan], so they carry across levels.

#### §2.12.d The HUD (Q46, AC11)

- **The HUD is one entity [V].** `0x42A2F0` (called by the entry point, §2.12.b
  row `Start`) creates it from `MAIN`'s `Display` record
  (`0x42A2F1`–`0x42A2F8`): update `0x42A370` (a frame counter `+0x80` + 1 per
  tick unless paused, `0x52C5F8`), draw `0x42A390`, `+0x58` \|= `0x4000040`
  (always updated, screen coordinates; `0x42A314`–`0x42A31C`), `+0x74` := 1
  (`0x42A32A`; tested by the draw loop at `0x40F36C`, meaning [H]), `+0x84` =
  the `Display` record, `+0x88` = the `Icons` record (`0x42A341`–`0x42A351`).
- **Coordinates [V]+[M].** Screen pixels of the 320 × 240 view. Each y depends
  on `0x46441C`: 0 in the file [M] and never written by a direct store (only
  read or compared) [V by scan] — so the values below are the `0x46441C` = 0
  branch; with it set every y is 4 less. With it set a `Timer` also counts p1 · 50 ticks
  instead of p1 · 60 (`0x427F19`–`0x427F3C`), so a 50 Hz mode is the reading
  [H]. What could set it is Q55.
- **Draw calls, in order** (what | counter / condition | clip | origin (x, y) |
  VA):
  1. freed-lemming count, `0x52C5A8` mod 100 (stored back,
     `0x42A3C2`–`0x42A3CB`) | `Display` `KLEI` digits | units (138, 41), tens
     (133, 41) only when ≠ 0 | `0x42A3D9`–`0x42A42F`
  2. coin count, `0x498F2C` mod 100 (stored back, `0x42A437`–`0x42A444`) |
     `KLEI` | units (184, 41), tens (179, 41) when ≠ 0 |
     `0x42A453`–`0x42A4A9`
  3. lives `0x52C56C` | `GROS` digits | units (285, 43), tens (278, 43) when
     ≠ 0 | `0x42A4AC`–`0x42A52D`
  4. the box | `EINS` | (160, 51); `+0x70` := 2, or 0 when the bonus flag is set
     (`0x42A545`–`0x42A554`, meaning [H]) | `0x42A55A`–`0x42A579`
  5. the spare helmet, only if `0x59F1E4` | `HELM`, pose ((`+0x80` >> 2) & 7) ·
     2 | (160, 51) | `0x42A581`–`0x42A5BD`
  6. the lemming figure | `DREI`, pose 1 while `0x52C700` > 0 (decremented per
     draw), else 0 | (130, 51) | `0x42A5C5`–`0x42A5F9`
  7. the coin | `VIER`, pose (`+0x80` >> 2) & 7 (spins) | (190, 51) |
     `0x42A601`–`0x42A631`
  8. the face (the reading [H]; it is `Display` `ZWEI`, not a `Hero` sprite) |
     `ZWEI` | (295, 51) | `0x42A639`–`0x42A658`
  9. the weapon: count = the u16 that `0x466830[sel]` points to, mod 100 |
     `KLEI` | units (35, 41), tens (30, 41) when ≠ 0 |
     `0x42A660`–`0x42A6F4`; icon = `Icons` clip `0x466818[sel]` (`VIER FUNF
     SECH EINS ZWEI DREI` for 0–5), pose (`+0x80` >> 2) mod its poses, at (27,
     30), drawn with a 4th argument `0xA0` when the count is 0
     (`0x42A6F7`–`0x42A773`; "greyed" [H])
- **The four elements of plan 47 §2.2 [V positions; names H]:** element 1
  (top-left) = the weapon icon and its count; element 2 (top-centre) = the
  lemming figure with the freed-lemming count, beside the box that shows the
  spare helmet; element 3 = the spinning coin and the coin count; element 4
  (top-right) = the face and the life count. Sprite sources: `Display` (all of
  2–4 and the digits) and `Icons` (element 1) [V]; `Items` is used by pickups
  only, `Inserts` by the `Timer` object (`0x427ECE`) and the continue screen
  (`0x42A8F8`), not by this HUD [V]; `Timer` (index 55, `0x427EB0`) is a placed
  object and L1 places none [M].
- **L1's first frame [derived from the initial values]:** lemmings "0", coins
  "0", lives "3", empty box, figure pose 0, the coin spinning, the face, and the
  weapon icon `FUNF` with count "0", drawn with the `0xA0` argument.
- **Screen boxes [derived, `hud_boxes.py`; top-left = origin + (dx, dy), §2.6.2
  c]:** weapon icon x 19–36, y 22–38; weapon digits x 27–39, y 34–41; lemming
  figure x 119–142, y 22–42; lemming digits x 130–142, y 34–41; box x 144–177,
  y 14–50 (three layers); spare helmet x 154–170, y 22–45; coin x 183–200, y
  26–41; coin digits x 176–188, y 34–41; lives digits x 274–291, y 34–43; face
  x 280–309, y 19–44. The digits overlap the icons drawn after them; whether
  `0x40C270` paints the HUD in call order (its `+0x60` is −1) is [H].

#### §2.12.e What stays open

Q54 (the `Moneybag`/`Pots` need a hit; plan 47 rev 3 brought the attacks in,
§2.14), Q55 (`0x46441C`); Q56 (bursts per `Moneybag`) is answered in §2.14.h;
[H]: entity `+0x70`, `+0x74`, `0x80000`, placement
flags `0x100`/`0x200`, the `Thief`'s pursuit, what `0x42B2D0(4)` shows.
Builders: FL6 takes the role column, FL10 the idle clips and the hidden list,
FL11 the coin/lives rules, FL13 the HUD table.

### 2.13 The Henchlemming (2026-11-25, FL4b)

Plan 47 calls this section §2.11; the number moved because FL3/FL4 took §2.11
and §2.12 (the plan file is not edited by this pass). Recovered by a read-only
objdump pass over `LOMAX.EXE` for the first-level plan (FL4b; Q50; AC16–AC18).
Grades and the reproduce convention are those of §2.10; L1 = `MEDIEVAL`
section 0 sub-level 0, plane 0. Entity fields as §2.5/§2.12.a: `+0x3C`/`+0x40`
integer x/y, `+0x44`/`+0x48` 16.16 x/y (the spawn `0x4126A0` sets both 16.16
words with zero fraction and the integer high words from x/y,
`0x4127A1`–`0x4127B1` [V]), `+0x4C` vx, `+0x50` vy (16.16, y grows downward),
`+0x58` flags (`0x8` = mirrored = facing left), `+0x6A` 8.8 pose position,
`+0x68` rate.

**Reproduce.** Scratch files outside the repository, not committed:

```
objdump -d -M intel --no-show-raw-insn "$EXE" > /var/tmp/fl4b/lomax.asm
python3 -I r.py 42dd70 42dfdf                                  # the whole handler (init + update), by address range
python3 -I r.py 414450 41450c; python3 -I r.py 414510 4145cf; python3 -I r.py 4146a0 41474d   # its three probes
python3 -I r.py 42cd00 42ce25; python3 -I r.py 430320 4304c7   # the defeat and the death pop
python3 -I r.py 412450 41269c; python3 -I r.py 40f1c8 40f35d; python3 -I r.py 40f3f3 40f403  # spawn / despawn windows
python3 -I r.py 40ffb6 4100a2; python3 -I r.py 412d90 412e2f; python3 -I r.py 413e40 413f61  # stomp, bounce, hit test
python3 -I owners.py "$EXE" /var/tmp/fl4b/lomax.asm 4146a0 414510 414450 42cd00 430320   # callers -> owning handler
python3 -I bytes.py "$EXE" 464540 8 s16                        # -> 80 80 160 110 340 140 340 140
python3 -I bytes.py "$EXE" 464b70 1 cstr                       # -> Lemming
env PYTHONPATH=src python3 clips.py "$LOMAX_GAME_DIR" MEDIEVAL Henc    # STAY/JUMP keyframes, poses, rate, box
env PYTHONPATH=src python3 clips.py "$LOMAX_GAME_DIR" MAIN Hero Lemming # OUCH/OHNO/TUMB/SPIN, Lemming PLOP
env PYTHONPATH=src python3 henchlemming.py "$LOMAX_GAME_DIR"           # plan 47 §6 script M
python3 -I arith.py                                            # hop arc, cycle lengths, per-placement values [derived]
```

#### §2.13.a Code map, and what is shared (R10)

- **Own code [V]:** init `0x42DD70`–`0x42DDD1`, update `0x42DDE0`–`0x42DFDF` =
  0x270 = 624 bytes; the next handler (`Barr`, index 75) starts at `0x42DFE0`.
  No draw pointer (default draw, §2.12.a).
- **What it calls** (callers counted in the whole executable, owners by address
  range [V]):
  - animation helpers `0x416140` (set clip, 279 callers), `0x416110` (set if
    different, 109), `0x4161B0` (advance, 69), `0x416210` (pose → keyframe,
    29) — the generic clip machinery of §2.6.2;
  - the hit test `0x413E40` (21 callers; §2.12.a);
  - the landing probe `0x414450` (25 callers, 17 handlers), the ledge/step
    probe `0x414510` (8 callers: `Slim` 22, `Cowb` 25 ×2, `Pira` 29, `Thie`
    44, `Henc` 84, `Barr` 75, `Muta` 74), the same-kind-ahead probe `0x4146A0`
    (2 callers: `Pira` 29 at `0x4217E0`, `Henc` at `0x42DEDB`);
  - the sound call `0x40D5F0(entity, id)` (93 callers);
  - on defeat only: `0x42CD00` and `0x430320` (8 callers each, the same 8
    enemy handlers: `Slim` 22, `Cowb` 25, `Drac` 26, `Were` 30, `Henc` 84,
    `Barr` 75, `Muta` 74, `Zomb` 70);
  - the floor probe `0x413B90` is reached only through `0x414450`/`0x414510`
    (§2.9.a).
- **Verdict for R10 [V]: separable.** There is no enemy base routine with
  per-enemy behaviour: every shared routine is a parameterised utility (entity
  in, a yes/no or a position out) that reads only the calling entity, the floor
  probe, the hero globals, and — for `0x4146A0` — other entities whose update
  pointer equals the caller's. No call reaches another enemy's update. The only
  path of a shared utility that depends on other objects is `0x414510`'s
  entity-wall branch `0x4145D0` (entities with flag `0x800000`), taken only
  while `0x4777D0` ≠ 0; its setters are `0x41F8E0` (`Pile`, 23) and `0x4210D3`
  (`Wall`, 28), cleared at `0x40EED5` and `0x4210F9`, written at `0x40FA73`
  [V]; neither name is placed in L1 (§2.12.b's 15 names) [derived], so in L1
  the branch is dead. FL14 ports: the handler, `0x414450`, `0x414510` without
  `0x4145D0`, `0x4146A0`, and the floor probe (already specified, §2.9.a). The
  death path (`0x42CD00`, `0x430320`) is shared by 8 enemies but is a single
  fixed effect, not behaviour (§2.13.g).

#### §2.13.b States and transitions [V]

The update uses three counters: `+0x80` (rest timer; −1 = "just landed"),
`+0x84` (ground countdown; 0 = airborne), `+0x88` (turn on the next take-off).
Init (`0x42DD70`–`0x42DDD1`): update `0x42DDE0`; `+0x58` \|= `0x20` \|
`0x10000` (`0x42DD7F`, `0x42DD8B`); `+0x60` := 1 and `+0x62` := 1
(`0x42DD93`–`0x42DD9C`; `+0x60` = sprite depth index → plane depth + 4,
§2.11.a; `+0x62` = despawn class, §2.13.f); force `STAY` (`0x42DD82`,
`0x42DDA0`); mirrored (faces left) when x & `0x10` (`0x42DDA8`–`0x42DDAF`);
`+0x84` := 10, `+0x88` := 0, `+0x80` := x & `0x1F` (`0x42DDB3`–`0x42DDCA`).

Per tick, in order:

| State | Entered when | Each tick | Leaves when | VA |
|---|---|---|---|---|
| 1. **Hit** | every tick, tested first | `0x413E40(self)` true → defeat (§2.13.g) and return | — (the entity becomes a `Lemming`) | `0x42DDE7`–`0x42DE10` |
| 2. **Rest (`STAY`, animated)** | `+0x80` > 0 | `+0x80` − 1; if still > 0: set `STAY` if different and advance the pose at the clip's rate; return | the decrement reaches 0: the same tick falls through to 3 (a rest of R ticks shows `STAY` for R − 1 ticks) | `0x42DE11`–`0x42DE3F` (`0x42DE2C`, `0x42DE35`) |
| 3. **On the ground in `JUMP`** | `+0x80` ≤ 0 and `+0x84` ≠ 0 | set `JUMP` if different (`0x42DE46`), `+0x68` := 0 (poses are chosen by hand, `0x42DE54`); `+0x84` − 1 (`0x42DE62`); pose 0 (`+0x6A` := 0, `0x42DF25`) | `+0x84` reaches 0 with `+0x80` < 0 (**after a landing**): choose the next rest — if (x XOR hero x `0x59F23C`) & 7 ≠ 0, `+0x80` := 20 (`0x42DE89`); else `+0x88` := 1 and `+0x80` := 60 + (x & `0x7F`) (`0x42DE95`–`0x42DEA5`); then `+0x84` := 10, pose 0 (`0x42DEAB`–`0x42DEB5`). `+0x84` reaches 0 with `+0x80` = 0 (**after a rest**): **take-off** (§2.13.c/d), pose 0 | `0x42DEC0`–`0x42DF22` |
| 4. **Airborne** | `+0x84` = 0 (`0x42DE5C`) | integrate and test for landing (§2.13.c) | landing: sound `0x0D`, vy := 0, `+0x84` := 10, `+0x80` := −1 → state 3 | `0x42DF30`, `0x42DF69`–`0x42DF82` |

Every path except the hit and the `STAY` path ends in `0x416210` (pose →
keyframe, `0x42DFD5`).

The cycle on flat ground [derived, `arith.py`]: take-off → 31 airborne ticks →
10 ticks pose 0 of `JUMP` (landing squash) → `STAY` for R − 1 ticks → 10 ticks
pose 0 of `JUMP` (crouch; the 10th is the take-off) — **R + 50 ticks per hop**:
70 ticks for R = 20; 110–237 for the long rest R = 60…187. First action after a
spawn: `STAY` for (x & 31) − 1 ticks (0 when x & 31 ≤ 1), then the 10-tick
crouch and a hop [derived]. **Clips [M, `clips.py`]:** `STAY` 5 keyframes = 5
poses, rate 40 (one loop per 32 ticks [derived]); `JUMP` 6 keyframes = 6
poses, rate 57 in the file but forced to 0 by the handler.

#### §2.13.c Movement: the hop [V]

- **Only hops; no walking.** x and y change only in the airborne branch
  (`0x42DF30`–`0x42DF5A`); on the ground the update never writes the position
  (gravity is not applied while `+0x84` ≠ 0) [V].
- **Take-off** (`0x42DEFE`–`0x42DF22`): vx := −1.0 (`0xFFFF0000`) when facing
  left (`+0x58` & `0x8`), else +1.0 (`0x10000`); vy := −4.0 (`0xFFFC0000`);
  sound `0x19` (`0x40D5F0`, `0x42DF1D`).
- **Per airborne tick** (`0x42DF30`–`0x42DF5D`): vy += 0.25 (`0x4000`); y16 +=
  vy; x16 += vx; integer x/y := the high words; then `0x414450(self)`. No
  horizontal collision test in the air: the hop is committed at take-off.
- **`0x414450` (landing probe) [V]:** if vy < 0 it sets bit 0 of vy (vy \|= 1,
  a 1/65536 drift) and returns 0 (`0x414455`–`0x414465`). That bit matters: on
  a flat hop vy would be exactly 0 on the 16th airborne tick, and with vy = 0
  the depth test below is skipped, so the hop would snap to any floor the probe
  finds; with the bit set vy is 1/65536 there [derived, `arith.py`]. Else floor
  := `0x413B90(plane, x, y, 4)`; none (`0x4E20`) → 0; if vy ≠ 0 and (floor > y
  or y − floor ≥ 8) → 0 (`0x41449E`–`0x4144AE`); otherwise it lands: y := floor
  (integer and 16.16 high word), vy := 0 (`0x4144B2`–`0x4144B9`). On a steep
  slope (`0x52C4C8` = 2) it then **reverses** vx and toggles `0x8` when moving
  uphill — vx > 0 on a rising-right slope (`0x52C5A4` = 1) or vx < 0 on a
  descending-right one — and returns 2, else 1 (`0x4144C0`–`0x414506`). The
  handler only tests non-zero.
- **The arc [derived, `arith.py`]:** on flat ground it lands on the 31st
  airborne tick, 31 px forward, apex 30 px above the take-off y, vy 3.75 at
  landing. Airborne poses by vy (`0x42DF91`–`0x42DFCE`): vy < −3.0 → pose 1;
  < −1.0 → 2; < 0.5 → 3; < 2.0 → 4; else 5 (per tick: 3 × 1, 8 × 2, 6 × 3, 6 ×
  4, 7 × 5 on a flat hop); the landing tick keeps the previous pose. Mean speed
  0.443 px/tick for R = 20, 0.131–0.282 for long rests. vy has no cap: a fall
  longer than ~8 px/tick can pass a floor (`y − floor ≥ 8`) [derived from
  `0x4144A9`].

#### §2.13.d Turning [V]

At take-off, before vx is set, three toggles of `0x8`, each applied once, in
this order, none re-checked (`0x42DEC0`–`0x42DEFA`):

1. `+0x88` set (the long-rest case) → clear it and turn (`0x42DECA`–`0x42DED4`);
2. `0x4146A0(self, 80)` → turn: another entity in the slot banks (`0x52C5A0`,
   then `0x59E768`) with the **same update pointer** (another living
   `Henchlemming`) on the same plane, with \|other y − self y + 16\| < 40, and
   ahead within 80 px (facing left: self x − 80 < other x < self x; facing
   right: self x < other x < self x + 80) (`0x4146C3`–`0x414721`);
3. `0x414510(self, 3)` → turn (§2.13.e).

Then vx takes its sign from the final facing. Because nothing is re-checked, a
`Henchlemming` blocked on both sides hops toward the side it turned to
[derived]. The landing probe's steep-slope reversal (§2.13.c) is a fourth turn,
in the air.

#### §2.13.e Collision with the level; ledges and walls [V]

- **Only the floor probe.** The handler and its probes call `0x413B90` and
  nothing else of the level; the wall and ceiling probes `0x412F50`/`0x413130`
  are never reached, so only floor-class cells (`0xC0`–`0xFF`, §2.9.a) matter.
  L1 has no wall/ceiling cell (§2.9.d) [M].
- **`0x414510(self, n)`, the look-ahead (`0x414510`–`0x4145C5`):** probes n + 1
  columns — x, x ± 16, …, x ± 16n, stepping in the facing direction — with
  `0x413B90(plane, xi, y, 4)`; it returns 1 (turn) at the first column with
  **no floor** (`0x4E20`), a **steep slope** (`0x52C4C8` = 2), or a floor **16
  px or more above or below** y; else 0 (or the `0x4145D0` result, §2.13.a).
  The `Henchlemming` passes n = 3: columns x, x ± 16, x ± 32, x ± 48 — so it
  turns at a ledge or step of ≥ 16 px or a 45° slope within 48 px ahead, before
  a 31 px hop [derived].
- **Box:** the probes use the origin column only; the entity's box is its
  current clip's box (the four words at animation node `+0x10`, as for the
  hero, §2.10.c): `STAY` −9, −24, 9, −3; `JUMP` −10, −31, 10, −7 (left, top,
  right, bottom relative to the feet origin) [M, `clips.py`]. It is used for
  contact (§2.13.g), not for terrain.

#### §2.13.f Wake rule: spawn and despawn windows [V]

- **No wake test of its own:** the handler never reads the camera; the only
  hero read in its live behaviour is hero x in the rest choice (§2.13.b). It
  acts from the tick it is spawned [V].
- **Tick order [V]:** per logic tick `0x412450` (spawn) → `0x40EE50` (entity
  updates, the handler) → `0x40FB70` (hero; its contact loop, §2.10.d) →
  `0x40F530` → … ; `0x40F040` (despawn) runs once per tick (inside the
  catch-up loop and once after it) (`0x404C5B`–`0x404CA6`).
- **Spawn (`0x412450`):** each call handles the placements whose 2-bit field
  (`node+0x12`, flags bits 8–9, §2.5) equals a phase `0x498F30` that cycles
  0–3 (`0x412682`–`0x412697`), skipping `0x2000` and already-spawned nodes
  (§2.12.a). For a plane with zoom flag `+0x3C` = 0 (L1, §2.11.a) a node spawns
  when x ∈ [cam x − mx, cam x + 320 + mx] and y ∈ [cam y − my, cam y + 240 +
  my] with (mx, my) = `0x464540[field]` = (80, 80), (160, 110), (340, 140),
  (340, 140) [M, `bytes.py`] (`0x412520`–`0x4125E0`); while `0x59F1DC` ≠ 0 it
  is **not** spawned inside [cam x − 40, cam x + 360] × [cam y − 30, cam y +
  270] (`0x41262B`–`0x41264C`). `0x59F1DC` := 1 when the countdown `0x52C5F4`
  passes 60 (`0x40F5C6`), := 0 at `0x403C36` [V]; "not after the level's
  opening" is the reading [H]. L1's `Henchlemming` placements have field 0
  (flags `0x0`/`0x2000`) → margin 80 × 80 [derived].
- **Despawn (`0x40F040`):** each call handles entities whose `+0x62` equals a
  phase `0x49B878` that cycles 0–2 (`0x40F3F3`–`0x40F403`) — so `+0x62` = 3 is
  never despawned. With `+0x3C` = 0 an entity outside [cam x − mx, cam x + 320
  + mx] × [cam y − my, cam y + 240 + my], (mx, my) = `0x464540[+0x62]`, is
  released by `0x412B80` (`0x40F320`–`0x40F34F`), which clears the placement's
  spawned bit (`0x412C2E`) so it can spawn again. The `Henchlemming`'s init
  sets `+0x62` := 1 → it is released outside cam x − 160 … cam x + 480, cam y −
  110 … cam y + 350 [derived].
- **Consequence [derived]:** a `Henchlemming` exists only while the camera is
  near; leaving the window resets it, and re-entering re-runs the init at its
  placement (x, y, facing, first rest). The `Generator`-spawned one at (1018,
  320) (flag `0x2000`) is never spawned by the window, so once released it is
  gone unless its one-shot `Generator` fires again (§2.12.b).

#### §2.13.g Contact with the hero, and death [V]

- **Contact is the hero's code, not the handler's.** Flags `0x20` + `0x10000`
  put it in the hero's contact loop (§2.10.d, `0x40FF07`–`0x4100A2`): boxes
  overlap (§2.13.e boxes), same plane, hero clip not `SPIN`/`TUMB`, loop
  skipped while `0x59E938` ≠ 0 or `0x52C568` ≠ 0 or a death is in progress.
- **Stomp [V]:** `0x10000` set, hero airborne (state `0x49C4C4` bit `0x1`), vy
  `0x59F250` > 0, and the hero's previous-tick feet ((y16 − vy) >> 16) + its
  box bottom ≤ the entity's y + box top (`0x40FFB6`–`0x410007`; mirrored branch
  `0x410051`–`0x410090`) → `0x412D90` (`0x410092`): hero vy := −4.0, hero y :=
  previous y − 8 px, \|vx\| < 2.0 → vx := ±2.0 by facing, `0x59E94C` := 0,
  `0x59E764` := 0, sound 2, and a 7-tick `PLO2` effect of the `Hero` record at
  the hero (`0x4286D0`; string `0x464B5C`) (`0x412D90`–`0x412E2F`). **Neither
  routine writes the entity: a stomp does not kill a `Henchlemming`**; it is a
  harmless bounce.
- **Otherwise the hero is hurt:** `0x412E30(entity x)` (`0x41009A`), §2.10.d:
  without the helmet (`0x52C570` = 0 and `0x59E944` = 0) a **death** — death
  timer 300, `0x59E938` := 1000, vy −4.0, sound `0x20`, lives − 1 at timer 250
  (`0x4102FB`, 50 ticks after the hit), respawn 214 ticks after the hit; with
  the helmet: helmet lost, sound `0x22`, `0x59E938` := 180 (input cleared and
  the contact loop skipped for 180 ticks = 3.0 s [derived]), vy −5.0. Both:
  knockback vx := −2.5 (`0xFFFD8000`) when entity x > hero x, else +2.5
  (`0x28000`), unless state `0x200` (`0x412F1E`–`0x412F3C`). The `Henchlemming`
  itself is unchanged by the contact (no write in its code). **In L1 the
  helmet comes only from two `Pots`, which open on a `SPIN`/`TUMB`/projectile
  hit (§2.14.i); until the first is opened a contact is a death** [derived].
  With the helmet in flight a contact costs the helmet, not a life (§2.14.e).
- **Hero clips for it (D6) [V rows of §2.6.2 a, M data]:** death → airborne,
  row 9 `OHNO` while `0x59C708` ≠ 0 (`OHNO` 6 poses, rate 76); helmet hurt →
  row 10 `OUCH` while `0x59E938` > 0 (`OUCH` 3 poses, rate 34); at timer 250
  `0x42FFB0` (the death clip is [H], §2.10.d).
- **What kills it [V]:** only `0x413E40` true (`0x42DDE7`): flag `0x20000` (a
  projectile, `0x414130`) or `0x10000` with the hero's clip `SPIN` or `TUMB`,
  same plane, `0x52C568` = 0, boxes overlap (`0x413E74`–`0x413F57`). `SPIN` is
  selected while `0x59F164` ≠ 0, set at `0x41074D` when the jump input is
  newly pressed (`0x464438` & `0x4777CC`) while airborne and `0x59E94C` <
  `0x9000` (§2.14.c). **`TUMB`** is state `0x8`, set at
  `0x4107A3` when the Down input (`0x464435` & `0x40` = `0x4000`) is pressed
  **on the ground on a steep slope** (`0x52C574` = 2, the hero's floor kind,
  §2.9.b), with `0x46AB4C` := 180, `0x4770B0` := 3 and sound `0x33`
  (`0x410757`–`0x4107A6`); cleared at `0x4107C9`. That is a movement-only way
  to kill — TUMB is graded cheap in §2.14.g; it has no motion of its own.
- **Defeat (`0x42DDF4`–`0x42DE10`) [V]:** `0x42CD00(self)` (§2.12.a: a `Classic`
  lemming `CLA1` is spawned, vy −4.0, vx = hero vx / 2, `+0x88` := 40 + random
  & 63, sounds `0x43` and `0x39`; freed counter + 1, flash 60; a coin when x is
  odd; and **`+0x4` := 0** at `0x42CD18`, detaching the entity from its
  placement, so the release cannot clear the node's spawned bit and **a
  defeated `Henchlemming` never respawns** [V]); then `0x430320(self)`: the
  entity becomes `MAIN`'s `Lemming` record (string `0x464B70`) in clip `PLOP`,
  update `0x42FD20` (advance; release `0x412B80` when it wraps), flags &
  `0xFFD6FFC7` (no longer harmful, hittable or mirrored), `+0x62` := 3, `+0x60`
  := 1, plus a particle burst (`0x412800`, 2 × 16 particles with random
  velocities) (`0x430320`–`0x4304C7`); then y − 10 (`0x42DE05`). `Lemming`
  `PLOP` = 5 poses at rate 92 → removed after 14 ticks [M + derived].

#### §2.13.h Randomness [V]

The living behaviour draws **no** random number: no call to `0x43AAD0` in
`0x42DD70`–`0x42DFDF` or in `0x414450`, `0x414510`, `0x4146A0`. Its only
variation is deterministic: x & 31 (first rest), x & 16 (facing), x & 127 (long
rest), and (x XOR hero x) & 7 (rest choice). The death path uses the shared
source `0x43AAD0` (`0x42CDBD` and the particle loops of `0x430320`), so a kill
would advance the shared random state; FL14's `Snapshot` needs no random state
for the living enemy [derived].

#### §2.13.i L1's eight [M + derived, `henchlemming.py`, `arith.py`]

| Placement (x, y) | Flags | First `STAY` ticks | Initial facing | Long rest | Coin on defeat |
|---|---|---|---|---|---|
| (701, 542) | `0x0` | 28 | left | 121 | yes |
| (1018, 320) | `0x2000` (by `Generator`) | 25 | left | 182 | no |
| (1068, 544) | `0x0` | 11 | right | 104 | no |
| (1454, 208) | `0x0` | 13 | right | 106 | no |
| (1597, 246) | `0x0` | 28 | left | 121 | yes |
| (2115, 265) | `0x0` | 2 | right | 127 | yes |
| (2441, 387) | `0x0` | 8 | right | 69 | yes |
| (2997, 448) | `0x0` | 20 | left | 113 | yes |

No parameters. The x-dependent values change as it hops (they read the current
x). Whether each placement's y lies on a floor, and where each first hop lands,
is FL14's measurement [H].

#### §2.13.j Constants for FL14/FL15 (D5)

| Name | Value | VA | Grade |
|---|---|---|---|
| `HENCH_TAKEOFF_VX` | ±1.0 | `0x42DEFE`/`0x42DF0C` | [V] |
| `HENCH_TAKEOFF_VY` | −4.0 | `0x42DF13` | [V] |
| `HENCH_GRAVITY` | 0.25 | `0x42DF36` | [V] |
| `HENCH_GROUND_TICKS` | 10 | `0x42DDB3`/`0x42DEAB`/`0x42DF78` | [V] |
| `HENCH_SHORT_REST` | 20 | `0x42DE89` | [V] |
| `HENCH_LONG_REST_BASE` | 60 + (x & 127) | `0x42DE9F`–`0x42DEA2` | [V] |
| `HENCH_REST_MATCH_MASK` | 7 | `0x42DE84` | [V] |
| `HENCH_FIRST_REST_MASK` | 31 | `0x42DDC7` | [V] |
| `HENCH_FACING_BIT` | x & 16 | `0x42DDAB` | [V] |
| `HENCH_AHEAD_SAME_KIND` | 80 px, y window \|dy + 16\| < 40 | `0x42DED8`, `0x4146EB`–`0x4146F3` | [V] |
| `HENCH_LOOKAHEAD_COLUMNS` | 3 (→ 4 columns, 16 px apart) | `0x42DEEB` | [V] |
| `LOOKAHEAD_STEP_LIMIT` | 16 px | `0x41457D` | [V] |
| `LANDING_DEPTH_LIMIT` | 8 px | `0x4144A9` | [V] |
| `PROBE_ROWS` | 4 | `0x414466`/`0x41453D` | [V] |
| pose thresholds | −3.0 / −1.0 / 0.5 / 2.0 | `0x42DF94`/`0x42DFA3`/`0x42DFB2`/`0x42DFC7` | [V] |
| `STAY` rate 40, boxes `STAY`/`JUMP` | read from the user's data at run time — not constants | — | [M] |
| despawn class 1 → margins 160 × 110 | `+0x62` := 1, table `0x464540` | `0x42DD98` | [V+M] |
| spawn margins | 80 × 80 | — | [M] |
| sounds | `0x19` take-off, `0x0D` landing | — | [V ids; meaning H] |
| stomp bounce | −4.0, −8 px, \|vx\| ≥ 2.0 | `0x412DAB`/`0x412DC3`/`0x412DE8` | [V] |
| knockback | ±2.5 | `0x412F31`/`0x412F3C` | [V] |
| helmet window | 180 | §2.10.d | [V] |

#### §2.13.k Builder list (FL14, FL15) with `[H]` fallbacks

- **FL14 (movement):** (1) an entity with the three counters and the init of
  §2.13.b; (2) the state order of §2.13.b including "`STAY` shows R − 1 ticks";
  (3) the hop of §2.13.c with 16.16 arithmetic, vy \|= 1 while rising, and the
  landing probe on the FL7 floor probe (one-way floor class only); (4) the turn
  order of §2.13.d; (5) the look-ahead of §2.13.e without the entity-wall
  branch (dead in L1); (6) spawn/despawn windows of §2.13.f, or — simpler,
  labelled `[H]` in code and `slice` output — spawn all 7 window-spawned at
  level start and the eighth when its `Generator` fires, never despawn (differs
  from the original only while the camera is far); (7) poses by vy and the
  `JUMP` rate 0; (8) mirror = facing left. A static fallback `[H]` (stays at its
  placement in `STAY`) is needed only for what FL14 cannot measure; nothing in
  the movement is `[H]` in the code itself.
- **FL15 (contact):** (1) the hero's contact test with the clip boxes; (2)
  stomp = the bounce of §2.13.g, enemy unharmed; (3) side contact =
  `0x412E30`: death (no helmet in L1) with `OHNO`, life − 1 at 50 ticks, or
  with a helmet `OUCH` + 180-tick window; knockback ±2.5; (4) the kill is FL15d's
  (§2.14.k): a `SPIN`, `TUMB` or helmet hit; (5) R9: the enemy update is
  deterministic and needs no random state.

#### §2.13.l What stays open

Q57 answered by the maintainer (D7); `TUMB` graded cheap in §2.14.g. `[H]`: `0x59F1DC`'s meaning, sound meanings,
`TUMB`'s motion, `0x52C568`, the `0x42FFB0` death clip. Q50 is answered.

### 2.14 The hero's attacks (2026-11-25, FL4c)

Recovered by a read-only objdump pass over `LOMAX.EXE` for the first-level
plan ([`../roadmap/47-first-level-plan.md`](../roadmap/47-first-level-plan.md)
revision 3: D7, AC20, row FL4c; Q58). Plan 47 asks for "a new subsection after
FL4b's"; this is §2.14. Grades and the reproduce convention are those of
§2.10; L1 = `MEDIEVAL` section 0 sub-level 0, plane 0. Entity fields as §2.13
(`+0x3C`/`+0x40` integer x/y, `+0x44`/`+0x48` 16.16 x/y, `+0x4C` vx, `+0x50`
vy (y grows downward), `+0x58` flags, `+0x60` depth index, `+0x62` despawn
class, `+0x68` rate, `+0x6A` 8.8 pose position). Hero globals: entity
`0x59F200`, clip pointer `0x59F208` (clip tag at clip `+0x4`, clip box = four
signed words at clip `+0x10`–`+0x16`: left, top, right, bottom), x `0x59F23C`,
y `0x59F240`, vx `0x59F24C`, vy `0x59F250`, plane `0x59F25E`, flags `0x59F258`
(bit `0x8` = mirrored = facing left), state bits `0x49C4C4`.

A correction to the card's brief: `0x414130` is **not** the `Pots` hit entry.
It is the projectile's *marker* (it sets `0x20000` on what it touches,
§2.14.e); `Pots` are hit through `0x413E40` at `0x42C067`/`0x42C591`
(§2.12.b) [V].

**Reproduce.** Scratch files outside the repository, not committed:

```
objdump -d -M intel --no-show-raw-insn "$EXE" > /home/nwah/Development/RetroLab/.scratch/fl4c/lomax.asm
python3 -I r.py 4106c3 4107eb     # jump launch tail, SPIN trigger 0x41074D, TUMB trigger 0x4107A3
python3 -I r.py 4107eb 410a47     # the throw (0x4107ED) and the weapon modes (0x41084F–0x410A47)
python3 -I r.py 410520 4105b7     # weapon-1 glide/jump, spare-helmet key (0x410572)
python3 -I r.py 410ed8 410efa; python3 -I r.py 411fd0 412037   # SPIN on touchdown, SPIN row + ground timer
python3 -I r.py 413e40 413fdf; python3 -I r.py 414130 414279   # hit test, projectile marker
python3 -I r.py 42f440 42fb2a     # helmet projectile: spawn, update, draw
python3 -I r.py 42e690 42e9e6     # spare-helmet drop, helmet loss
python3 -I r.py 40cd39 40ce57     # event keyframes in the actor blit
python3 -I r.py 428190 4283fb; python3 -I r.py 42bee0 42c13b; python3 -I r.py 42c2e0 42c5ea; python3 -I r.py 42cd00 42ce25
python3 -I r.py 430ba0 430c84; python3 -I r.py 430d98 430e0f   # weapon wheel
python3 -I r.py 412e30 412f45; python3 -I r.py 40f737 40f75d   # hurt with the helmet in flight; restore at (re)entry
python3 -I bytes.py "$EXE" 464580 1 u32                         # -> 0 (control scheme)
python3 -I bytes.py "$EXE" 464588 16 hex                        # -> 0x40 0x20 0x80 0x10 | 0x80 0x40 0x10 0x20 | 0x20 0x10 0x40 0x80 | 0x0 0x0 0xffffffff 0x0
python3 -I bytes.py "$EXE" 4669e0 1 cstr                        # -> Helmet
python3 -I bytes.py "$EXE" 4645e8 12 s32                        # coin velocity table (6 pairs, 16.16)
python3 -I owners.py "$EXE" --callers lomax.asm 413e40 414130 42cd00 430320 42c240 4286d0
env PYTHONPATH=src python3 clips.py "$LOMAX_GAME_DIR" MAIN Hero Helmet Items Classic    # rate, poses, box, event keyframes
env PYTHONPATH=src python3 clips.py "$LOMAX_GAME_DIR" MEDIEVAL Henchlemming Moneybag
env PYTHONPATH=src python3 henchlemming.py "$LOMAX_GAME_DIR"    # plan 47 §6 script M
env PYTHONPATH=src python3 l1_attack.py "$LOMAX_GAME_DIR"       # Pots/Moneybag/Generator placements, steep cells
python3 -I arith.py                                             # every [derived] number below
```

The scripts are scratch files outside the repository (`r.py` prints an
address range of the listing, `bytes.py` reads values by VA, `owners.py` maps
call sites to the handler whose address range holds them, `clips.py` lists a
record's clips with keyframes, poses (flag `0x80`), rate, box and event
keyframes, `l1_attack.py`/`arith.py` as named) and are not committed.

#### §2.14.a Code map, and what is shared (R10/R11)

- **No weapon framework [V].** The attacks are hero-side: three hero state
  bits/globals (`0x59F164`/`0x498F70` SPIN, state `0x100` throw, state `0x8`
  TUMB), the hero's clips, and one projectile entity. A hit is resolved **in
  the target's own update** by the parameterised test `0x413E40` (hero clip
  `SPIN`/`TUMB` + box overlap, or the projectile mark `0x20000`); the
  projectile marks targets with `0x414130`.
- **Hero weapon code region, from `0x42E690` up to the next handler at
  `0x431110` [V]** (it lies after the
  `Zomb` handler `0x42E440` in address order, so "owner by address range"
  would wrongly say `Zomb`; it is installed from the hero init: `0x59F234`
  := `0x42EC70` and `0x59F238` := `0x42F5F0` at `0x40F966`/`0x40F970`):
  spare-helmet drop `0x42E690` (+ update `0x42E760`, draw `0x42E7E0`), helmet
  loss `0x42E850` (+ update `0x42E980`), the weapon-2 bomb `0x42E9F0`
  (+ `0x42EB20`, `0x42EAE0`), the helicopter hook `0x42EC70`, the throw
  callback `0x42F5F0`, the helmet projectile `0x42F440` (spawn) /
  `0x42F660` (update) / `0x42FA50` (draw), the weapon wheel `0x430BA0`
  (+ update `0x430C90`, draw `0x430FA0`).
- **Shared routines and their other users [V, owners by address range]:**
  - `0x413E40` (hit test): 21 call sites in 17 handlers — `Live` (5),
    `Slim` (22), `Pile` (23), `Cowb` (25, ×2), `Drac` (26, ×2), `Pira` (29,
    ×2), `Were` (30, ×2), `Dood` (34), `Thie` (44), `Shar` (48), `Mone` (57),
    `Pots` (85, ×2: `0x42C067`, `0x42C591`), `Henc` (84, `0x42DDE7`), `Barr`
    (75), `Muta` (74), `Zomb` (70).
  - `0x414130` (projectile marker): 3 sites — `Ball` (63, `0x4298BB`), the
    weapon-2 bomb's explosion (`0x42EB09`) and the helmet projectile
    (`0x42F6AE`).
  - `0x42CD00`/`0x430320` (defeat): the 8 enemies of §2.13.a.
  - `0x42C240` (coin): `Thie` `0x424AC1`, `Mone` `0x428349`, `Pots`
    `0x42C391`/`0x42C5A5`, the defeat `0x42CDED`.
  - `0x4286D0` (the 7-tick `PLO2` effect): the stomp `0x412E26` and the
    helmet's hit `0x42F704`.
  - `0x430690` (break into `BOOM` debris): 9 call sites, among them the
    `Pots` re-hit `0x42C5DB`.
- **Verdict [V]: separable.** Porting SPIN, the helmet throw and TUMB needs
  the hero bits, the clips, the projectile, `0x413E40`/`0x414130` and the
  three L1 targets (`Henchlemming`, `Moneybag`, `Pots`); no other enemy's code
  is reached. In L1 the `Thief` (44) also has `0x10000` and would react to a
  hit (knock-away, §2.12.b) — out of scope per plan 47 §2.3: an attack that
  hits it does nothing in this milestone. The weapon modes other than the
  plain throw (bomb, helicopter, glide, `BUI1`, `DREI` throw) are unreachable
  in L1 (their counts are 0 and nothing in L1 raises them, §2.14.f) — so no
  maintainer decision is needed (no R10 block).

#### §2.14.b Inputs [V bits, M default keys]

- Two words (built in `0x416660`–`0x4168DF`): `0x464434` = **held** bits,
  `0x464438` = **newly pressed** bits (`held & ~previous`,
  `0x4168C9`–`0x4168D9`). (§2.13.g formerly called the SPIN input "held"; it
  is an edge — corrected there.)
- The four action masks come from a control-scheme row: `0x464588 +
  16·[0x464580]` → jump `0x4777CC`, throw `0x52C6C8`, weapon `0x52C57C`,
  spare `0x46AB54` (`0x40FB0F`–`0x40FB3B`). `0x464580` = 0 in the file [M];
  row 0 = jump `0x0040`, throw `0x0020`, weapon `0x0080`, spare `0x0010` [M];
  rows 1–2 permute the same four bits; how a player picks a row is [H].
  With §2.11's default key table [M]: jump = DirectInput code 17, throw = 18,
  weapon = 16, spare = 31; Down = `0x4000` (code 208), Up = `0x1000` (200),
  the wheel = `0x0100` (57).

#### §2.14.c SPIN [V unless marked]

| Item | Rule | VA | Grade |
|---|---|---|---|
| Input / trigger | The jump mask newly pressed (`0x464438` & `0x4777CC`) **while airborne** (state `0x1`) and the jump-hold counter `0x59E94C` < `0x9000` → `0x59F164` := 1. The press that launches a jump cannot also spin: the launch clears its edge bit and sets `0x59F164` := 0; while the jump is still held there is no new edge, and a release sets `0x59E94C` := −1. So **SPIN = press jump again in the air**: after releasing it during a jump, when falling off a ledge, after a stomp bounce (`0x59E94C` := 0), or during the hop of a standing throw (§2.14.d) | `0x410726`–`0x41074D`; `0x4106C3`–`0x4106CB`, `0x410710`; `0x4105AD`; `0x412DA5` | [V] paths; "double-jump spin" is the reading [H] |
| State / clip | The selector draws `SPIN` while `0x59F164` ≠ 0 or `0x498F70` ≠ 0 (row 7 of §2.6.2 a), set-if-different, **rate forced to 128**; `SPIN` has 8 poses → one loop per 16 ticks. A sound `0x2B` is requested through `0x40D570(0, 0x2B, 0x1E)` while the pose position is > `0x200` | `0x4116CE`–`0x4116E2`, `0x411FD0`; `0x411FDF`; `0x411FEB`–`0x411FFC` | [V]; poses [M]; loop [derived]; sound meaning [H] |
| Air phase | Lasts from the trigger to touchdown. No velocity change: of the 11 uses of the `SPIN` tag in the executable, none alters the hero's motion except that SPIN disables the weapon-1 glide/high jump; facing is not updated; at the plane edge | `0x410B8E`, `0x41055D`, `0x410654`; `0x4104D8`; `0x4113DB`, `0x41141D` | [V] by scan |
| Ground phase (after touchdown) | Touchdown sets `0x498F70` := 15 and `0x59F164` := 0 and arms no `LND1`. Each tick the selector decrements `0x498F70` and, while the clip has not wrapped, holds it at 1; the advance's "wrapped" result is the stack flag set at `0x40FC91`. So SPIN stays **15–17 ticks after touchdown, until the first wrap of the 16-tick loop at or after tick 15** | `0x410ED8`–`0x410EEB`; `0x410EA3`; `0x412004`–`0x41202D`; `0x40FC91` | [V]; [derived, `arith.py`]: 16 / 15 / 17 for loop phase 0 / 1 / 15 |
| Duration total | Air time after the re-press + 15–17 ticks | — | [derived] |
| Cooldown | None as a timer: a new spin needs a new airborne re-press; spinning again while spinning only re-sets `0x59F164` | — | [V] |
| Cancelled by | A hurt (zeroes both), death and level entry, a rope grab, a new jump launch | `0x412E86`, `0x412E8C`; `0x410255`/`0x41025A`, `0x40F9B4`/`0x40F9BA`; `0x413E18`/`0x413E27`; `0x410710` | [V] |
| Hit box | The hero's current clip box, i.e. `SPIN`'s box (−7, −50, 7, −8) around the hero's feet origin; it is **not mirrored** by facing (the hero box is used as is, the target box mirrored when the target's `0x8` is set) | `0x413E86`–`0x413FCB` | [V]; box [M] |
| What it hits | Every entity whose update calls `0x413E40` and has `0x10000`: in L1 the `Henchlemming`, `Moneybag`, `Pots` (and the `Thief`, out of scope); same plane (`+0x5E` = `0x59F25E`), `0x52C568` = 0, boxes overlap. The test stores the hero's vx in the target's `+0x54` and the hitter `0x59F200` in `+0x14` | `0x413E86`–`0x413FCB`; `0x413F43`, `0x413F4C` | [V] |
| Timing | Targets update before the hero (§2.13.f), so a target sees the clip selected on the previous tick | — | [derived] |
| Protection | While the hero's clip is `SPIN` or `TUMB` the contact loop skips that entity — no hurt and no stomp. So a spinning hero touching a `Henchlemming` kills it and is not hurt | `0x40FF28`–`0x40FF3C` → `0x4100A2` | [V] |

#### §2.14.d The helmet throw — hero side [V unless marked]

- **Input:** throw mask newly pressed (`0x464438` & `0x52C6C8`), the helmet
  worn (`0x52C570` ≠ 0) and no state `0x188100` (not already throwing,
  helicopter, `BUI1`, …) → state \|= `0x100` (`0x4107ED`–`0x410817`). **No
  weapon count and no weapon selection is read** — the plain throw needs only
  the helmet.
- **The throw hop:** if neither airborne (`0x1`) nor ducking (`0x4`), the same
  press launches a jump: airborne, vy := −4.0, jump-hold counter 0, lockout 0,
  bit `0x2` cleared (`0x41081D`–`0x410849`; this is §2.6.2 b's "other −4.0
  launch site `0x41083C`").
- **Clip:** state `0x100` → `THR2` if ducking (`0x4`), `THR3` if climbing
  (`0x1000`), else `THR1` (`0x4115B8`–`0x4115E3`), one-shot (hero `+0x58` \|=
  1, `0x4115EB`); when the clip has wrapped the selector clears `0x100`,
  `0x800`, `0x40000` (`0x41158D`–`0x4115AE`). [M]: `THR1` 7 poses rate 96,
  `THR2` 7 poses rate 91, `THR3` 5 poses rate 64 → `THR1` ends at tick 19,
  `THR2` 20, `THR3` 20 [derived].
- **Release point = an event keyframe [V mechanism, M data].** The actor
  blit `0x40C270` treats a keyframe with a sprite and step 0 as an event: it
  calls the entity's callback slot `+0x1C + 4·(flags & 7)` with the
  keyframe's offset applied to the actor's position (mirrored by facing,
  rotated/scaled when the blit is) (`0x40CD39`–`0x40CE52`). The hero's slot 7
  (`+0x38`) is `0x42F5F0`. Event keyframes with slot 7 [M]: `THR1` keyframe 5
  (pose 4) offset (22, −41); `THR2` keyframe 5 (pose 4) (25, −24); `THR3`
  keyframe 3 (pose 2) (14, −26). So the helmet leaves at pose 4 — **tick 11 of
  `THR1`**, tick 12 of `THR2`, tick 8 of `THR3` [derived, rate]. The callback
  fires on the first draw of that keyframe; it is one-shot because the spawn
  clears the helmet flag and the callback returns when it is 0
  (`0x42F5F0`–`0x42F5F7`) [V]. A port should spawn on the tick the pose
  becomes 4 [H: draw-time vs tick-time].
- **What the callback spawns (`0x42F5F0`):** state `0x800` (weapon 2) → the
  bomb (`0x42F5FE`–`0x42F626`, out of scope); otherwise the helmet projectile
  `0x42F440` from `MAIN`'s `Helmet` record (string `0x4669E0`; `0x412800`
  resolves names in `MAIN`, `0x412992` → `0x4162D0`) (`0x42F62F`–`0x42F652`).
- **One helmet at a time [V]:** the throw needs `0x52C570` ≠ 0 and the spawn
  sets it to 0, so no second throw until the helmet is caught.

#### §2.14.e The helmet projectile (`MAIN` `Helmet`, `0x42F440`/`0x42F660`/`0x42FA50`)

Spawn `0x42F440(entity, x, y)` [V]:

- `0x52C570` := 0 (helmet off), `0x59E944` := 1 (**helmet in flight**),
  `0x52C6F8` := the projectile (`0x42F44C`–`0x42F464`).
- Clip `EINS`; with state `0x40000` (weapon 5) `DREI` and flag `0x2000000`
  instead (`0x42F447`–`0x42F492`). Update `0x42F660`, draw `0x42FA50`, rate
  128, `+0x62` = `+0x60` = 3 (never despawned by the window, §2.13.f)
  (`0x42F495`–`0x42F4B2`). A looping sound `0x13` is started if none is
  playing (channel kept in `0x4645D0`, `0x42F4B6`–`0x42F4CC`).
- Phase `+0x80` := 0 (outbound), `+0x84` := 18, trail index `+0x88` := 0;
  x = the event x; **y = the event y + 16** (+ 5 when ducking)
  (`0x42F4D1`–`0x42F515`); a 16-entry position trail `+0x8C` is filled with
  the start point (`0x42F518`–`0x42F53B`).
- vx := −5.0 when the hero faces left (and the projectile gets `0x8`), else
  +5.0, **plus 3/4 of the hero's vx** (`0x42F53D`–`0x42F590`); vy := +3.0,
  rise rate `+0x11C` := 0.1875 (`0x3000`) and rise limit `+0x118` := −2.5
  (`0x42F569`–`0x42F57A`). Unless the helicopter flag `0x52C52C` is set:
  **Up held** (`0x1000`) → limit −3.25, rate 0.21875, vy 1.5; **Down held**
  (`0x4000`) → rate 0.125, vy 3.0 (`0x42F592`–`0x42F5D5`). Sound `0x30`
  (`0x42F5DC`).

Update `0x42F660` per tick [V]:

- **Hit (first):** while the clip is `EINS` or `DREI`, phase ≠ −1 and no
  death in progress (`0x59C708` = 0): `0x414130(self)` (`0x42F683`–
  `0x42F6AE`). If it marked anything and the clip is `EINS`: clip → `ZWEI`,
  vy := −3.0, vx := 0, phase := 1 (return), `+0x84` := 0, rate 128, and the
  `PLO2` effect `0x4286D0` at (x, y − 20) (`0x42F6BA`–`0x42F709`). So the
  plain helmet **hits once** — every overlapping target on that tick — and
  then only returns (`ZWEI` is not tested again); `DREI` (weapon 5) pierces.
- `0x414130` (`0x414130`–`0x414279`) walks both slot banks (`0x52C5A0`
  entries 0–32, `0x59E768` from 33); for each entity with `0x10000` on the
  projectile's plane whose clip box overlaps the projectile's clip box
  (neither box mirrored) it sets `0x20000`, `+0x54` := the projectile's vx and
  `+0x14` := the projectile (`0x414238`–`0x414252`); returns 1 if it marked
  any. The target's next `0x413E40` returns 1 and clears `0x20000`
  (`0x413E56`–`0x413E6A`).
- Advance the clip (`0x42F70D`).
- **Phase 0, outbound (18 ticks):** vy −= `+0x11C` (`0x42F72D`–`0x42F73D`);
  **hover:** the floor probe `0x413B90(plane, x, y − 48, 8)`
  (`0x42F738`–`0x42F75E`); if it finds a floor and this is not an Up throw:
  d = y − floor + 24, k = `0x200`/`0x400`/`0x800` (1/128, 1/64, 1/32 px/tick
  per px) by slope kind 0/1/2 (`0x42F663`–`0x42F673`, `0x42F794`); on a
  steep floor |vx| decays by 0.125 a tick toward 3.0 (`0x42F79B`–`0x42F7B8`);
  if 0 < d < 40 and vy > −3.0: vy −= d·k; if −40 < d < 0 and vy < 3.0: vy −=
  d·k/2 (`0x42F7BB`–`0x42F806`) — it is pushed toward 24 px above the floor.
  `+0x84` − 1; at 0 → phase 1, `+0x84` := 12 (`0x42F809`–`0x42F829`).
- **Phase 1, return:** x steers toward the hero: target = (hero x − x)/8
  px/tick, at least 4.0 in magnitude; vx moves toward it by 0.34375 a tick,
  clamped to ±5.5 (`0x42F82E`–`0x42F898`). Vertically it first keeps rising
  (vy −= 0.1875) until vy < `+0x118` (`0x42F89B`–`0x42F8B2`), then steers vy
  by 0.1875 a tick toward (hero y + hero box top + 8 − y)/16, at least 1.5
  in magnitude; during a death the target is 500 px higher (it flies off)
  (`0x42F8BE`–`0x42F925`).
- **Integrate** x16 += vx, y16 += vy; store the trail (pose `0xFFFF` once
  caught) (`0x42F928`–`0x42F9A1`).
- **No wall, ceiling or floor collision** — the only level probe is the hover
  probe at `0x42F75E` [V by scan of `0x42F440`–`0x42FA4C`]; the helmet flies
  through terrain, and phase 1 has no probe at all. **No range limit or
  timeout:** it returns until caught.
- **Catch (any phase):** no death in progress, |x − hero x| ≤ 4 and hero y +
  hero box top − 4 ≤ y ≤ hero y + hero box top + 20, phase ≠ −1 → stop the
  loop sound, sound `0x37`, `0x42FB30` (an effect at the hero's head [H]),
  **`0x52C570` := 1, `0x59E944` := 0**, phase := −1 (`0x42F9A7`–
  `0x42FA3B`).
- **Draw `0x42FA50`:** the projectile (unless caught) plus three trail images
  4, 8 and 12 ticks old with a fourth `0x40C270` argument 120, 100, 80
  ((4n + 12)·5 for n = 3, 2, 1; "fading" [H]); when all three trail entries
  are caught-marked it removes itself (`0x412B80`, `0x42FA5D`–`0x42FB20`) —
  about 12 ticks after the catch [derived].
- **Hit box:** the projectile's clip box, `Helmet` `EINS` (−10, −18, 10, −1)
  [M].
- **Numbers [derived, `arith.py`]:** phase-0 vx = 5.0 standing, 6.5 at hero
  vx 2.0, 6.875 at 2.5 → **90 / 117 / 124 px in the 18 outbound ticks**; the
  outbound drop without hover is +21.9 px (Up throw −10.4, Down throw +32.6).
  A full flight with the hero standing still on flat floor: caught after 68
  ticks, farthest 145 px ahead of the hero (including the 22 px release
  offset and the overshoot while turning).
- **Interaction with hurt:** with the helmet in flight a hurt is **not** a
  death (§2.13.g's test is `0x52C570` = 0 **and** `0x59E944` = 0): `0x412E30`
  → `0x42E850`, which releases the projectile and spawns a decorative `Items`
  `HELM` at its position flying off at vy −5.0 (−6.0 with `0x46441C`), then
  `0x52C570` := 0, `0x59E944` := 0 (`0x412EDB`–`0x412EFB`, `0x42E8E7`–
  `0x42E97B`) — the helmet is lost.
- **Level (re)entry:** if a helmet was in flight it is given back (`0x52C570`
  := 1 when `0x59E944` ≠ 0, `0x40F741`–`0x40F753`; `0x59E944` is cleared at
  `0x40FA07`).

#### §2.14.f Helmet, spare, weapon counts and the HUD [V unless marked]

- **`0x52C570` = helmet worn.** Writers: reset 0 (`0x40EE16`), pickup 1
  (`0x42C8FF`), spare pickup 1 (`0x42E7AF`), catch 1 (`0x42FA27`), (re)entry
  restore 1 (`0x40F753`), throw 0 (`0x42F44C`), hurt 0 (`0x412EF1`), death
  0 (`0x410146`, `0x4102DE`; with a helmet the death path first calls
  `0x42E850`, `0x410249`), attract-demo setup 0 (`0x41C970`), `0x4245BB`
  (in the `Cont` (42) handler's address range; its role is [H]), and three
  in `Airs`/`Forc` (`0x41BED4`, `0x41C12D`, `0x41C41E`; not in L1).
- **`0x59E944` = helmet in flight** (set by the throw, cleared by catch, hurt,
  entry).
- **`0x59F1E4` = spare helmet.** An `Items` `HELM` touched while the helmet is
  worn **or in flight** becomes the spare (`0x42C8ED`–`0x42C90B`). The spare
  key (mask `0x46AB54`, **held**) with a spare calls `0x42E690`: the spare is
  cleared and an `Items` `HELM` with a `STAR` overlay falls from the top of
  the view (camera + (160, 40), vy +1.0) (`0x410570`–`0x41058B`,
  `0x42E690`–`0x42E753`); touching it gives the helmet, or the spare again
  if one is worn (`0x42E781`–`0x42E7C5`). Losing the helmet to a hurt with a
  spare and no death in progress drops the spare the same way (`0x42E8A6`–
  `0x42E8B8`). HUD: the spare is drawn in the box (§2.12.d draw 5).
- **Worn helmet on the hero sprite:** `0x52C570` ≠ 0 clears bit `0x2` of hero
  `+0x70`, else sets it (`0x41050F`–`0x410523`); `+0x70` is a draw-layer
  mask whose meaning is [H] ("helmet layer shown" is the reading).
- **Weapon counts / selection.** The six counts are the u16 words of
  `0x466830` (§2.12.c). The weapon mask (default `0x0080`) newly pressed,
  helmet worn, uses the selected weapon if its count ≠ 0: selection 5 →
  count `0x52C544` − 1, state `0x40100` (a `DREI` throw); 4 → `0x4777D4` − 1,
  state `0x80000` (`BUI1`); 2 → `0x59F320` − 1, state `0x900` (the bomb
  throw); 0 → `0x49C4C0`, state `0x8000` (helicopter, `HEL*`)
  (`0x41084F`–`0x410A47`); 1 (`0x59F1E0`) is the held glide/high jump
  (`0x41052A`–`0x410569`, `0x410633`–`0x41065B`, `0x410B60`–`0x410BB1`).
  Selection is made in a **weapon wheel**: the `0x0100` input newly pressed
  on the ground with no `0x000F` bit held (`0x40FC9D`–`0x40FCD6`) creates
  `0x430BA0` (an `Icons` entity, hero state \|= `0x80` → clip `WAHL`, inputs
  cleared while open, `0x40FCDB`–`0x40FCEC`); left/right step `0x52C58C`
  through 0–5 with sound `0x41` (`0x430DAF`–`0x430E07`). This replaces
  §2.12.c's former "owner not identified".
- **In L1 [derived]:** all six counts are 0 at reset and L1 has no source of
  them (the three `Pots` hold `HELM`, 5 coins, `HELM`; `Pots` content 2–7 is
  the weapon pickup) → **no weapon mode is usable in L1**; the HUD shows
  `Icons` `FUNF` (selection 1) with count "0" drawn with the `0xA0`
  argument all level long. **A helmet throw changes no count**: the HUD's
  weapon count does not move on a throw (plan 47 AC11b expects it to fall —
  it does not; the only helmet-related HUD element is the spare in the box).

#### §2.14.g TUMB, and the verdict [V unless marked]

- **Input:** Down held (`0x464435` & `0x40` = `0x4000`) **on the ground**
  (state `0x1` clear) with the hero's floor kind `0x52C574` = 2 (a steep,
  `0xF0` cell, §2.9) → state \|= `0x8`, `0x46AB4C` := 180, `0x4770B0` := 3,
  sound `0x33` via `0x40D570(0, 0x33, 0x1E)` only when not already tumbling
  (`0x410757`–`0x4107A6`).
- **Duration:** re-armed every tick while that holds; otherwise cleared when
  the `TUMB` clip wraps or the hero is airborne (`0x4107AD`–`0x4107C9`).
  `TUMB` 9 poses rate 64 [M] → 36 ticks per loop [derived]. Afterwards
  `0x4770B0` = 3 gives `DIZZ` while standing still (§2.6.2 a row 28) until
  `0x46AB4C` counts 180 down (`0x4107D0`–`0x4107E1`).
- **Motion:** state `0x8` is read only by the trigger and the clip selector
  (`0x410778`, `0x411C56`) [V by scan] — TUMB has **no motion of its own**;
  any slide is the steep-slope ground behaviour, which is untraced (§2.9,
  "Still [H]" 1).
- **Hit box:** `TUMB`'s box (−12, −41, 12, −9) [M]; same test and the same
  contact protection as SPIN (§2.14.c).
- **L1 [M, `l1_attack.py`]:** 18 `0xF0` cells in three 6-cell runs: x
  1648–1743 y 272–367; x 2128–2223 y 272–367; x 2688–2783 y 288–383. The
  `Henchlemming`s at (2115, 265) and (1597, 246) start 36 and 93 px
  (|dx| + |dy| to the nearest steep cell centre) from one; the others 252–1217.
- **Verdict: cheap [V for the rule].** The kill side is one state bit, one
  clip and the shared hit test, all already needed for SPIN; nothing new in
  the projectile or the targets. What is *not* cheap — the steep-slope ground
  motion while tumbling — is FL7's open item, not TUMB's: FL15d can port the
  TUMB hit and leave the slide to whatever FL7 does on `0xF0` cells, labelled
  [H].

#### §2.14.h What a hit does [V unless marked]

- **`Henchlemming`** (`0x42DDE7`): defeat `0x42CD00` then `0x430320`, y − 10
  (§2.13.g). `0x42CD00`: a `MAIN` `Classic` lemming (string `0x466984`) in
  `CLA1`, update `0x42CE30`, y − 2, vy −4.0, **vx = hero vx / 2** (the hero's
  `0x59F24C` even for a helmet kill), mirrored when vx < 0, `+0x88` := 40 +
  random & 63, sounds `0x43` and `0x39` (`0x42CD4E`–`0x42CDDC`); **`+0x4` :=
  0** (`0x42CD18`: never respawns); **freed-lemming counter `0x52C5A8` + 1**
  (even if the `Classic` could not be created), at 50 → bonus flag `0x59C718`
  := 1 and counter 0, HUD flash `0x52C700` := 60 (`0x42CD1B`–`0x42CD3C`);
  **one coin when the enemy's x is odd** (`0x42CDE4`–`0x42CE1E`: coin vy
  −6.0, vx = 2/3 of the lemming's vx ± 0.5). **Score: none** — the game has
  no score counter; `0x42CD00` writes only `0x52C5A8`, `0x59C718`, `0x52C700`
  and the new entities [V by scan]. L1: 8 enemies → at most 8 freed lemmings,
  coins for the five odd-x placements of §2.13.i [derived].
- **`Moneybag`** (`0x428287`): on the hit `+0x8C` := 1, clip `JUMP` at rate
  128, |vx| = 1.0 + (x & 31)/64 signed like the hitter's vx in `+0x54` (0 →
  right), y + 32, `0x10000` cleared, default draw, depth 0, **despawn class
  `+0x62` := 2** and **`+0x4` := 0** (never respawns)
  (`0x428297`–`0x4282FC`). Falling: wall bounce (`0x412F50`), gravity
  0.1875 capped 5.0, landing probe `0x414450` (`0x42837A`–`0x4283D9`); on
  landing sound `0x4A`, vy := −4.0, `+0x90` := 1 (`0x4283DB`–`0x4283EA`).
  While `+0x90` = 1 it animates (no motion); **when the pose position is
  exactly `0x200` it releases 3 coins** (velocity pairs from `0x4645E8` at a
  random start 0–3, y − 19) (`0x428323`–`0x428373`); when the clip wraps
  `+0x90` := 0 and it hops (vy −4.0 kept) (`0x42830C`–`0x428319`).
  **Q56 answered: a burst on every landing**, not once — the update never
  removes the bag (no `0x412B80`/`0x412C50` in `0x428210`–`0x4283FB` [V by
  scan]); it stops only when the despawn window releases it (class 2: outside
  camera ± (340, 140), §2.13.f) [V], and it cannot come back. On flat ground
  one cycle is 42 airborne + 12 animation ticks = **3 coins every 54 ticks**
  [derived, `arith.py`]. L1 bags: (2104, 304) |vx| 1.375; (2175, 365) |vx|
  1.484375 [M + derived]. Burst at the 4th animation tick [derived].
- **`Pots`** (`0x42C067`): sound `0x11` only when the hitter is not the hero
  (a projectile) (`0x42C07A`–`0x42C087`); a `Generator`-spawned pot gets
  `+0x4` := 0 (`0x42C08F`–`0x42C099`); despawn class 2, clip `CLAY`, update
  `0x42C2E0`, 40-tick delay (`0x42C0A0`–`0x42C0BF`); a `LID` child flies off
  at vy −6.0, vx ±2.0 by the hero's vx sign (`0x42C0C9`–`0x42C132`). Content
  `+0xA8` (= placement p1, `0x42BEED`–`0x42BEF1`) on landing
  (`0x42C34D`–`0x42C56B`): p1 < 0 → −p1 coins from the `0x4645E8` table
  (the (1238, 464) pot: p1 −5 → **5 coins**, `0x42C37C`–`0x42C3BC`); 0 → an
  `Items` `HELM`; 1 → `UP`; 2–7 → a weapon icon; then content := −200
  (empty) (`0x42C56B`). The item: delay 40, vy −5.5, vx ±1.25 by hero vx
  sign (`0x42C3C3`–`0x42C470`). After the 40-tick delay **the next hit
  shatters the opened pot**: one coin if its x is odd (vy −6.0, vx 2/3 of the
  hitter's vx), sound `0x1C`, then `0x430690(self, 0x1400)` turns it into
  `BOOM` debris (clears `0x10000` and `0x80000`, depth 2, update `0x430840`,
  draw `0x4308F0`) (`0x42C575`–`0x42C5DB`, `0x4306E1`–`0x430833`); the
  debris's removal is [H]. The `Pots` init's "skip a helmet
  pot when the hero already has a helmet" rule (`0x42BEFA`–`0x42BFB8`)
  applies only to placements with flag bit `0x0001`; L1's three have
  `0x2000` [M] → not applied.
- **`Thief`** (out of scope): knocked away (§2.12.b row `Thief`).

#### §2.14.i The helmet-less L1 start [V + M]

- The hero **starts L1 without the helmet**: reset `0x40EDC0` zeroes
  `0x52C570`, `0x59F1E4` (`0x40EE16`–`0x40EE1B`) and the six counts; the only
  level-entry write (`0x40F753`) restores a helmet that was in flight; no
  `Start`/placement init sets it [V by the writer list of §2.14.f].
- **L1 has no `HELM` placement** (no `Items`/`Helmet`-like name in any
  `MEDIEVAL` plane) [M]. Its helmets come from **two `Pots` with p1 = 0**:
  (521, 560), spawned by the `Generator` at (424, 560), and (2032, 240), by
  the `Generator` at (1934, 272); the third, (1238, 464) by (1129, 544), holds
  5 coins [M, `l1_attack.py`, §2.12.b].
- **Consequence [derived]:** the throw needs the helmet, the first helmet is
  inside a pot, and a pot opens only on a hit → **the first attack of L1 must
  be a SPIN** (or TUMB) that opens the pot at (521, 560); from then on the
  helmet throw is available until the helmet is lost (a hurt while worn or
  in flight, or a death). The first `Henchlemming` (701, 542) lies after that
  pot. The throw needs no weapon count.

#### §2.14.j Constants for FL15b–FL15e (D5)

| Name | Value | VA | Grade |
|---|---|---|---|
| `SPIN_TRIGGER` | jump newly pressed, airborne, `0x59E94C` < `0x9000` | `0x41074D` | [V] |
| `SPIN_RATE` | 128 | `0x411FDF` | [V] |
| `SPIN_GROUND_TICKS` | 15, then to the wrap | `0x410EE1`, `0x412024`–`0x41202D` | [V] |
| `SPIN` loop | 16 ticks | — | [derived] |
| `THROW_HOP_VY` | −4.0 | `0x41083C` | [V] |
| `THROW_RELEASE_POSE` | 4 (`THR1`, `THR2`), 2 (`THR3`) | — | [M] |
| release offsets | (22, −41) / (25, −24) / (14, −26) | — | [M] |
| `HELMET_SPAWN_DY` | +16, +5 ducking | `0x42F4F2`–`0x42F4FD` | [V] |
| `HELMET_VX` | ±5.0 + 3/4 hero vx | `0x42F54C`/`0x42F55A`, `0x42F560`–`0x42F590` | [V] |
| `HELMET_VY0` | +3.0 / 1.5 Up | `0x42F569`, `0x42F5B9` | [V] |
| rise rate | 0.1875 / 0.21875 Up / 0.125 Down | `0x42F570`, `0x42F5AF`, `0x42F5CB` | [V] |
| rise limit | −2.5 / −3.25 Up | `0x42F57A`, `0x42F5A5` | [V] |
| `HELMET_OUT_TICKS` | 18 | `0x42F4D1` | [V] |
| hover | height 24, window ±40, gains 1/128, 1/64, 1/32 | `0x42F78D`, `0x42F663`–`0x42F673` | [V] |
| return | accel 0.34375, cap 5.5, min x speed 4.0 | `0x42F82E`, `0x42F84B`/`0x42F85E` | [V] |
| vertical return | step 0.1875, min 1.5, aim box top + 8 | `0x42F917`/`0x42F920`, `0x42F8F8`/`0x42F90B`, `0x42F8CD` | [V] |
| hit bounce | vy −3.0, vx 0 | `0x42F6CD`/`0x42F6D4` | [V] |
| catch window | x ± 4, y box top − 4 … + 20 | `0x42F9CE`–`0x42F9EC` | [V] |
| `TUMB` trigger and timers | 180 / 3 | `0x41078A`/`0x410794` | [V] |
| `Moneybag` hit | \|vx\| 1.0 + (x & 31)/64, y + 32, g 0.1875 cap 5.0, bounce −4.0, burst at pose position `0x200`, 3 coins | §2.14.h | [V] |
| `Pots` re-hit delay | 40 ticks, then the next hit shatters it | `0x42C0BF`, `0x42C5DB` | [V] |
| defeat | counter + 1, flash 60, 50 → bonus | §2.14.h | [V] |
| boxes `SPIN` (−7, −50, 7, −8), `TUMB` (−12, −41, 12, −9), `Helmet` `EINS` (−10, −18, 10, −1) | read from the user's data at run time — not constants | — | [M] |
| sounds | `0x2B` spin, `0x30` throw, `0x13` flight loop, `0x37` catch, `0x33` tumble, `0x11`/`0x1C` pot, `0x4A` bag landing, `0x43`/`0x39` defeat | — | ids [V]; meanings [H] |

#### §2.14.k Builder list (FL15b–FL15e) with `[H]` fallbacks

- **FL15b (SPIN):** (1) the trigger of §2.14.c on the jump edge (needs an
  edge-detected jump input; the engine's `Input` has a jump flag — FL15b
  derives the edge itself); (2) `SPIN` drawn while airborne-spinning and for
  15 ticks after touchdown then to the loop's wrap, rate 128; (3) no motion
  change, facing frozen; (4) contact protection while `SPIN`/`TUMB`;
  (5) `attack_hits(snapshot)` = the current `SPIN`/`TUMB` clip box at the
  hero, unmirrored, applied on the **next** tick's target update (or the
  same tick, labelled [H], if the engine's order differs); (6) no cooldown
  timer. `[H]` fallback: if the engine cannot draw `SPIN` yet, a named
  constant 16-tick loop with the box above.
- **FL15c (helmet throw):** `helmet_worn`, `helmet_in_flight`, `spare` and the
  six counts (all 0 at start); `HELM` pickup from the two L1 pots; the throw
  on the throw edge with the hop, `THR1`/`THR2`/`THR3`, release at pose 4
  (tick 11 of `THR1`) at the keyframe offset + (0, 16); the projectile of
  §2.14.e with phase 0 (18 ticks, hover), phase 1 (homing), catch, no terrain
  collision; one at a time. `[H]` fallbacks: if the floor probe cannot be
  called from the projectile, phase 0 without hover (labelled); if the
  event-keyframe offset is not available, (22, −41) as a named constant.
  `slice` prints `helmet thrown, count a -> b` with **a = b** (the counts do
  not change; the helmet flag does) — the card should print the helmet flag
  instead.
- **FL15d (hits):** the projectile marker `0x414130` (all overlapping
  `0x10000` targets, once per plain helmet, then the `ZWEI` return); the
  `Henchlemming` defeat (no respawn, freed + 1, coin on odd x, `Classic`
  lemming pop, no score); the `Moneybag` (fall, bounce, 3 coins **every
  landing**, released by the class-2 window, never respawned); `Pots` (open,
  contents, 5 coins at (1238, 464), the helmet at (521, 560) and (2032,
  240), the second hit shatters it, with one coin if its x is odd); TUMB hit (cheap; the slide is FL7's
  `[H]`). The `Thief` is not hit-tested. `[H]` fallback: if the window is not
  ported, stop a bag after a named number of bursts and say so in `slice`.
- **FL15e (HUD):** the weapon icon `Icons` clip by selection (`FUNF` for 1)
  at (27, 30) and the count of the selected weapon at (35, 41)/(30, 41),
  drawn with the `0xA0` argument when 0 — in L1 always `FUNF` "0" [derived];
  the spare helmet in the box (§2.12.d draw 5). No change on a throw.

#### §2.14.l What stays open

Q58 is answered (§2.14); Q56 answered (§2.14.h); Q57 answered by the
maintainer (D7) and TUMB graded cheap. `[H]`: the steep-slope ground motion
(§2.9), whether the throw event fires on the tick or the draw, how a control
scheme row is chosen, `+0x70` bit `0x2`, `0x42FB30`'s effect, sound meanings,
the role of `0x4245BB`, the `0x40D570` sound-call variant.

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
