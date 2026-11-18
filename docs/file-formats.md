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
  `lomax-modern anim-nmy`).
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

### 2.4 `TTAB`, `MAP`, `CELL`

- **`MAP` [V size, H word]**: 3 bytes per 16x16 cell — a 16-bit tile word plus
  one collision byte — padded with 0–3 zero bytes so the payload size is a
  multiple of 4. Verified on all 104 sections: `size − 3·cells ∈ {0,1,2,3}` and
  every size is 4-aligned. The *word* is not verified as a plain index: read as
  a tile field, the first of the three bytes masked to 7 bits (`b[0] & 0x7F`)
  scores **0 violations** over all 523,229 cells, against 189 for unmasked `b[0]`
  and 187 for `b[1]` **[V]**
  ([`research/07-wp3-asset-pipeline.md`](research/07-wp3-asset-pipeline.md) G5).
  **Open anomaly:** that 7-bit field saturates at 127 in every section that uses
  tiles, while sibling `TTAB` banks hold up to 2,952 entries — so a map cell is
  not a plain `TTAB` index and the map-cell → tile-record link stays unresolved
  ([`research/05-open-questions.md`](research/05-open-questions.md)).
- **`CELL` [V]**: whole 64-byte 8x8 palettised cells. 14,974 cells across the 9
  files, every payload a multiple of 64.
- **Collision byte [retracted, measured 2026-11-18]**: the third byte of a
  `MAP` cell was documented `[D]` as a bit-field (`0x80` solid, `0xC0` one-way
  floor, `0x08`/`0x10`/`0x20` directional blocking). That is **retracted**: the
  byte measured across all 104 retail planes is near-uniform over all 256
  values — `0x00` dominates (81–95 % by world) and every value `0x01`–`0xFF`
  occurs, with `0x01` a clear second in the playable worlds (VILLAGE 5.7 %,
  HAUNTED 2.9 %, WEST 1.7 %, MEDIEVAL 2.2 %) **[V]** (reproducible with
  `python -m lomax_modern slice --world <W>` or `art.planes` + a byte
  histogram). A flag byte clusters at a handful of values; this does not. The
  byte's per-value semantics (material / one-way / hazard) are **unresolved**
  ([`research/05-open-questions.md`](research/05-open-questions.md) Q31). The
  engine core therefore ships only the 0-vs-non-zero rule (`0` passable,
  non-zero solid) as a labelled hypothesis `[H]`, preserves the byte verbatim,
  and never interprets its bits.
- **`TTAB` [V structure, H meaning]**: 8 bytes per 16x16 tile — four big-endian
  `u16` cell indices, each a 13-bit index plus flags in `0x2000`/`0x4000`
  (`0x8000` never set). All 104 payloads are divisible by 8 and by 16, giving
  **75,122 records = 300,488 words**; decoding under the 13-bit mask leaves
  1,644 of the 300,488 indices outside the file's `CELL` count (0.55 %, all in
  `BONUS.WLD`, index 256 against 251 cells), against 18,147 under the 14-bit
  mask and 19,930 unmasked **[V]**
  ([`research/07-wp3-asset-pipeline.md`](research/07-wp3-asset-pipeline.md)
  G1–G3). Still **[D]**: 16x16 tiles assembled from four 8x8 cells, tile 0 and
  cell 0 empty. The order of the four cells inside an entry, the flag semantics
  and the map-cell link are **not** known. Flag counts come from two independent
  runs that used different counting units — `0x2000` on 15,787–16,503 and
  `0x4000` on 1,783–2,499 of the 300,488 words (G2 of the same report; WP-5,
  card `t_50f8aa85`, §7) — so they are quoted as a range, not a number.

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

**`GNMY`** entries reference those records directly. Each entry is a `u16` size
+ `u16` type index (little-endian, 3,593 entries across 104 chunks); the reader
resolves the type with `type_table[bank | type_index]`, where `bank` is `0x100`
for `MAIN.WLD` and 0 for every other world (the loader ORs a per-world "MAIN"
flag into the index). So **a `GNMY` type index is the zero-based position of the
record in the `NMY` table** — not a name, a hash, or an offset into a string
blob.

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

The documented "`SpriteFrame` is 0x38 bytes" `[S2]` is **not the on-disk unit** —
it is the in-memory stride the loader allocates per frame (`0x38` bytes in RAM);
the on-disk framing is the one above, and no chunk is an array of `0x38`-byte
records (re-measured: 0/566 chunk sizes are multiples of 0x38).

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
| `NMY` reader | `0x415199` | `0x14599` |
| `GNMY` reader | `0x414D16` | `0x14116` |
| `File_Read` (reads N bytes into a buffer) | `0x416A70` | `0x15E70` |
| byte-swap (`bswap`, big-endian→little-endian) | `0x416620` | `0x15A20` |

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
