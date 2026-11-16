# File formats — what is known, and how much to trust it

**Confidence legend**

- **D** — documented by a third party `[S2]` `[S3]`, not verified here.
- **H** — hypothesis in this repository, untested against a real file.
- **V** — verified here by a test or a measurement (nothing is **V** yet).

No game data is stored in this repository. Everything below is a description of
a format, not a copy of it.

## 1. Install layout

A `SETUP.EXE` install writes 110 files, ~11.6 MB `[S3]`:

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

### 2.1 Chunk sequence **[D]**

The loader reads the chunks in this fixed order:

```
WRLD  ("PS-X" magic, 1234)
NMY   object types and animations
HEAD  plane count, 10 palettes, editor data, ANIM bitmap
TTAB  16x16 tiles made from 8x8 cells (big-endian tile words)
MAP   tile map + collision bytes
GNMY  object placements (first word = entry size)
ANIM  sprite frames
CELL  8x8 cell pixels
END
```

World files in the PC build: `MEDIEVAL`, `VILLAGE`, `HAUNTED`, `WEST`, `ED`,
`BONUS`, `MAP`, `TITLE`, `LOGO`, `MAIN` `[S2]`. `LOGO.WLD` is listed but not
shipped `[S2]`.

### 2.2 Chunk header **[H]**

Not documented. The scanner assumes:

- a 4-byte tag field, space-padded (`"NMY "`, `"MAP "`, `"END "`),
- a 4-byte size, and
- sizes that are multiples of 4, because `File_ReadChunk` advances by
  `size & ~3` while counting `size` bytes `[S2]`.

The scanner tries tag+size / size+tag, little/big endian and
payload-only/header-inclusive sizes, then reports which hypothesis reaches EOF
cleanly. **Until that is confirmed on a real file, treat every offset as
provisional** (`lomax-modern wldscan`, LMX-1).

### 2.3 `HEAD` **[D]**

- `u32` width and `u32` height in **8-pixel units**, big-endian.
- 10 palettes × 256 colours, little-endian, 15-bit (blue bits 0–4, red bits
  10–14).
- 0x50 bytes of editor data (0xFF filler).
- A 256-bit ANIM bitmap at +0x1458.
- Colour 0 becomes the transparent key: white, with real white moved to 0x7FFE.

Only HEADs whose plane bit is in the active plane mask load palettes; every
plane's tiles are built from the last palettes loaded, and all shipped tiles use
palette 0 `[S2]`.

### 2.4 `TTAB`, `MAP`, `CELL` **[D]**

- A tile is 16x16, assembled from four 8x8 cells; tile 0 and cell 0 are empty.
- `TTAB` is stored big-endian; the `MAP` handler byte-swaps both the tile words
  and the plane's whole `TTAB`.
- `MAP` holds the tile indices plus one collision byte per cell:
  `(b & 0xC0) == 0xC0` is a one-way floor (bits 4–5 shape, bit 3 mirror, bits
  0–2 material); `0x80` is solid with `0x08`/`0x10`/`0x20` blocking from below,
  left and right.

### 2.5 `ANIM` / sprites **[D]**

`SpriteFrame` records are 0x38 bytes; each world has 256 sprite banks; frames
are blitted with `DDBLTFX` mirroring for left/right flips. Alpha lives in bits
16–23 of the sprite flags and in the sprite queue's bucket bits 22–29.

### 2.6 Palette rules that bite any art pipeline

Because index 0 is the transparent key and real white lives at 0x7FFE,
upscaling must be **matte-aware**: treat index 0 as alpha and scale colour and
coverage separately, or every sprite gets a halo. See
[`research/02-resolution.md §2.5`](research/02-resolution.md#25-layer-3--higher-pixel-density-the-real-ceiling).

## 3. `SFX/*.WAV` **[D]**

Replacement effects must be PCM, mono, 22050 Hz, 16-bit, with a plain 44-byte
header `[S2]`. Whether every shipped file matches that exactly is an open
question (Q7).

## 4. `MUSIC/*.DAT` — a trap **[D]**

These are **not** audio files. Each is an ISO 9660 entry pointing at the first
sector of a CD-DA track (`MEDI1.DAT` = track 2 … `WESTWLD4.DAT` = track 25), and
its length counts 2048 bytes per sector while audio sectors are 2352 bytes. A
file-system copy therefore keeps bytes 24–2071 of every sector and silently
drops 13% of the audio `[S3]`. Extract from the raw image, not from a mounted
disc.

## 5. `DEMOS/DEMOxxNy.DAT` **[D]**

Input recordings for the title-screen and attract demos, named by section and
sub-level (`DEMO%02dN%d.DAT`) `[S2]`. Their internal layout is undocumented
(Q6). Any render-layer change must keep these replaying tick-for-tick.

## 6. `GAME.TXT` **[D]**

Localised strings with `@`, `#` and `&` markers, loaded once at startup `[S2]`.
Encoding is unverified (Q12 in the backlog is related).

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
