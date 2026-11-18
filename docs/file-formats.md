# File formats — what is known, and how much to trust it

**Confidence legend**

- **V** — verified in this repository against the retail PC install
  (2026-11-16): a measurement, with the command recorded in
  [`research/06-measurements-and-improvements.md`](research/06-measurements-and-improvements.md).
- **D** — documented by a third party `[S2]` `[S3]`, not verified here.
- **H** — hypothesis in this repository, untested against a real file.

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
  `size & ~3` `[S2]`; `MAP` is the one chunk that needs padding to reach it.

All 9 files parse as a chain that reaches EOF (`wldscan`: `confirmed-chain`,
`layout=tag+size u32be (payload)`).

### 2.3 `HEAD` **[V]**

- `u32` width and `u32` height in **8-pixel units**, big-endian. Verified on
  104/104 planes by cross-checking the sibling `MAP` (§2.4); the little-endian
  reading fails for all of them.
- Payload size is constant: **5,240 bytes (0x1478)**.
- 10 palettes × 256 colours, little-endian, 15-bit (blue bits 0–4, red bits
  10–14) `[D]`; bit 15 is clear in **all 266,240 words** of the 104 `HEAD`
  blocks **[V: `art.head_palette`]**, which is consistent with the 15-bit
  reading but does not prove the channel order.
- **The ten slots are not interchangeable [V measured].** In `VILLAGE.WLD` the
  cells render as natural art with slot 1 and as a hue-shifted variant with
  slot 0; slot 1 is the only slot non-empty in **101 of 104** `HEAD` blocks
  (slot 0: 83). So the `[D]` claim "all shipped tiles use palette 0" is not what
  the data shows — but no field in the container names the slot either (Q8), so
  the exporter defaults to slot 1 **and prints that this is a hypothesis**.
- ~~Colour 0 becomes the transparent key: white, with real white moved to
  0x7FFE~~ — **retracted.** Measured over the 104 `HEAD` blocks, palette entry 0
  of slot 0 takes seven different values (`0x0000`, `0x0008`, `0x1800`,
  `0x1802`, `0x2806`, …), none of them white; `0x7FFE` occurs 10 times in the
  whole palette block and `0x7FFF` 374 times. Index 0 is still the transparent
  key — it is the index the renderer must skip — but its palette colour is not
  special.
- 0x50 bytes of editor data (0xFF filler) `[D]`.
- A 256-bit ANIM bitmap at +0x1458 `[D]` — arithmetic confirms it:
  0x1458 + 32 = 0x1478, the measured payload size.

Plane sizes are **not** bounded by the screen: measured widths 320–7,200 px and
heights 240–2,928 px. Heights 240 and 256 both occur (the 256-line ones are the
PS1 PAL layout leftovers `[S2]`).

Only HEADs whose plane bit is in the active plane mask load palettes; every
plane's tiles are built from the last palettes loaded, and all shipped tiles use
palette 0 `[D]` (unverified — Q8).

### 2.4 `TTAB`, `MAP`, `CELL`

- **`MAP` [V]**: 3 bytes per 16x16 cell — a 16-bit tile word plus one collision
  byte — padded with 0–3 zero bytes so the payload size is a multiple of 4.
  Verified on all 104 sections: `size − 3·cells ∈ {0,1,2,3}` and every size is
  4-aligned; every pad byte is zero (pad 0 on 85 planes, 1 on 3, 2 on 10, 3 on
  6). 523,229 cells in total over 104 planes, whose cell widths run 20–450
  (320–7,200 px).
- **`MAP` tile word — unresolved (Q20).** The word is decodable but its meaning
  is not: the best-scoring reading (`byte0 & 0x7F` as a tile index) has 0
  violations on all 523,229 words, yet that field **saturates at 127** in every
  section that uses tiles, while sibling `TTAB` banks hold up to 2,952 records.
  The two tables are therefore not a plain per-plane index pair, so no tool in
  this repository reports a unique-tile count; `lomax-modern export` prints
  `map cell -> tile record: unresolved (Q20)`.
- **`CELL` [V size, H pixels]**: 14,974 records of exactly 64 bytes, every
  payload a multiple of 64. 64 one-byte pixels spanning the full 0–255 range
  (222 distinct values, 18 % zeros) — which rules out packed 4-bpp pixels — so
  8x8 is forced by the record size; the **row-major pixel order is still a
  hypothesis** (`[H]`), and the exporter labels it as such.
- **`TTAB` [V structure]**: 8-byte records — four **big-endian** `u16` cell
  indices each, 75,122 records / 300,488 words across the 9 files, every
  payload a multiple of 8. A word is a **13-bit index** (mask `0x1FFF`) plus
  flags: `0x2000` is set on 16,503 words, `0x4000` on 2,499, `0x8000` never.
  What the flags mean is open (Q21) and they are counted, never interpreted.
- **Out-of-bank indices are preserved, not repaired (Q22).** `BONUS.WLD`
  references index **256** while its `CELL` chunk holds 251 records: 1,644
  words, and the same value is in range in every other world. Decoders keep the
  word verbatim and re-emit it unchanged; a rendering that cannot resolve the
  cell leaves it empty instead of drawing a substitute.
- **Order of the four cells inside a record — unresolved (G1).** Every
  permutation is equally consistent with the container, and a seam test found no
  continuity across the four cells (18 % adjacent-equality at cell seams versus
  46 % inside a cell), so the 16x16 assembly is *not* supported by the data.
  The exporter therefore draws each record's four cells **in stored order** by
  default and offers `--tile-layout 2x2` only as a labelled hypothesis.
- **Collision byte [D]**: `(b & 0xC0) == 0xC0` is a one-way floor (bits 4–5
  shape, bit 3 mirror, bits 0–2 material); `0x80` is solid with
  `0x08`/`0x10`/`0x20` blocking from below, left and right. Measured shape of
  the field: 86.6 % of the 523,229 bytes are `0x00`, 2.4 % are `0x01`, and the
  `0x80` class appears as coherent ledges — consistent with the documented
  meaning, still not proof of it.
- **Reproduce**: `lomax-modern export WORLDS/VILLAGE.WLD --out /tmp/lomax-art`
  writes `_cells.png`, `_tiles_planeNN.png` and `_map_planeNN_collision.png`
  (stdlib PNG, no Pillow) and prints the confidence of every step. Exported art
  is a derivative work: it must never be committed.

### 2.5 `GNMY` placements **[V structure, D meaning]**

Entries walk cleanly as `u16` size (little-endian) + `u16` type (little-endian):
104 chunks, 3,593 entries, each chunk ending in a 4-byte remainder. The type
*index* is measured; what each index means is not, because the NMY type table
(index → name) is still unconfirmed.

### 2.6 `ANIM` / sprites **[D]**

`SpriteFrame` records are 0x38 bytes `[S2]`, but measured `ANIM` payload sizes
are **not** multiples of 0x38 (566 chunks, e.g. 2,700 and 27,176 bytes), so a
chunk carries more than a bare array of frames — a header, a bank table, or
pixel data appended. Treat the record size as unverified.

### 2.7 Palette rules that bite any art pipeline

Because index 0 is the transparent key (its palette colour is not white — see
§2.3), upscaling must be **matte-aware**: treat index 0 as alpha and scale
colour and coverage separately, or every sprite gets a halo. See
[`research/02-resolution.md §2.5`](research/02-resolution.md#25-layer-3--higher-pixel-density-the-real-ceiling).

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
