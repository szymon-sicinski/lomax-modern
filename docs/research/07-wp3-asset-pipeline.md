# 7/WP-3 — Asset pipeline: what 2× WLD/SPR re-authoring needs

> **Provenance.** Work package **WP-3** of the LMX-7 roadmap, delivered as an
> attachment on kanban card `t_a2860e97` (2026-11-17) and committed here
> unchanged apart from the heading level and relative links. Evidence was
> produced against the retail PC install at `/game-files/LOMAX (1)/LOMAX`
> (read-only); nothing in the game folder was written.
>
> **No game bytes, no whole-file hashes.** Every number below is a count, a
> size, an offset or a header field. No payload bytes and no digest of a
> copyrighted file appear anywhere in this document.
>
> **Legend** — **V** verified in that session (command quoted), **D** documented
> by a third party `[S2]`/`[S3]`, **H** hypothesis in this repo. Grades are as
> the report left them.
>
> **Status.** The `TTAB` framing of §2 G1 and the round trip of §3 were
> independently reproduced by WP-5 (card `t_50f8aa85`); the two falsifications
> (G7 `ANIM`, G9 `NMY`) and the `TTAB`/`MAP` measurements are applied to
> [`../file-formats.md`](../file-formats.md) in this same change.

---

## 0. The three answers the card asked for

**(a) Gap list** — §2. Four items were previously graded `D` and are now
partly **V** (`TTAB` granularity and cell-index field, the `size & ~3` rule,
`ANIM`'s non-0x38 alignment). Two documented claims are **falsified** by
measurement: `ANIM` chunks are not arrays of 0x38-byte records, and the `NMY`
type table does not walk as `u16 size + NUL name`. The largest remaining hole is
`MAP`'s tile word (a 7-bit field bounded at 127 in all 104 sections, while the
sibling `TTAB` banks hold up to 2,952 entries — the two tables are not a plain
per-plane index pair).

**(b) Is 2× art representable in the container without engine changes?**
**In the container, yes — as bytes. To the stock engine, no.** Nothing in the
chunk container describes geometry: `HEAD` payload is a constant 5,240 B
(104/104), a `CELL` is an unlabelled 64 B record, and a `TTAB` entry is exactly
8 B = four cell-index slots with no size field. A 2× pack is byte-legal but
*indistinguishable from 1× art*, so the loader's constants (64 B cell stride,
8×8/16×16 blits) decide — meaning an engine patch, not a format change. Details
and the byte budget are in §4.

**(c) Legal boundary** — §5: what must never enter the repo, what may be
generated at run time, and what may never be committed even though it is
"generated".

---

## 1. What I ran, and the counts used

```bash
# required probe (read-only, writes only the JSON report to /tmp)
lomax-modern measure "/game-files/LOMAX (1)/LOMAX" --json /tmp/wl.json
```

Output used below (`/tmp/wl.json`, summarised):

```
worlds:  9 files, 7107048 bytes
chunk tags seen: ANIM, HEAD, TTAB, MAP, GNMY, WRLD, NMY, PARA, CELL, END, MACR, PAGE
planes: 104 (104 verified against MAP size)
HEAD endian votes: {'>': 104}
cells: 14974 x 64 B (all CELL payloads are whole cells)
GAME.TXT: 19532 bytes, 1321 lines ... DEMOS: 14 files, sizes {2048: 8, 8192: 6}
SFX 67 / AMBIENT 12 / JINGLES 3 — all RIFF/WAVE 22050 Hz 16-bit mono
```

Ten ad-hoc read-only probes (`/tmp/probe*.py`, stdlib only, `Struct`-level
reads, no writes to the game folder) produced the rest. **Units are named
everywhere**, because they differ by two orders of magnitude:

| Unit | Count |
|---|---|
| `CELL` records = 8×8 palettised cells | **14,974** (958,336 B) |
| `TTAB` tile records = 16×16, 8 B each | **75,122** (600,976 B = 300,488 u16 words) |
| `MAP` cell positions = 16×16 grid slots | **523,229** (3 B each + pad) |
| `ANIM` chunks | **566** (3,201,288 B) |
| `GNMY` entries | **3,593** across 104 chunks |
| chunks in all 9 files | **1,041** |

---

## 2. Gap list (before 2× re-authoring is possible)

Format: **item — grade now ↑ evidence — what would confirm it — exact test.**

**G1. `TTAB` entry granularity and the cell-index field — D → V(structure).**
All 104 `TTAB` payloads are divisible by 8 (and by 16), i.e. 8 B per 16×16
tile. Each entry is four big-endian `u16` cell indices; word = 13-bit index +
flags in `0x2000`/`0x4000`, `0x8000` never set. Votes over all 300,488 words
(`probe3.py`): mask `0x1FFF` → 1,644 bad words (0.55%, all in one world);
mask `0x3FFF` → 18,147 bad in 7 worlds; bare `u16` → 19,930 bad in 7 worlds.
Coverage: distinct in-bank indices 14,861 of 14,974 records (99.2%), and
max index = cells−1 exactly in 6 worlds. *Still open:* the order of the four
cells inside an entry. **Test:** render one plane with the four permutations
and compare against a screenshot of the running game, or find the tile-build
loop in `LOMAX.EXE`.

**G2. `TTAB` flag semantics — H.** `0x2000` set on 15,787 words, `0x4000` on
1,783, both on 716. Flip-H/flip-V is the obvious guess and is *not* evidence.
**Test:** pick a tile used with each flag and diff its rendering; or read the
blit routine that consumes the word.
*(Superseded: the bit roles are `[V]` (Q21) and the axis pairing is `[V]` (Q33: `0x2000` horizontal, `0x4000` vertical, `0x6000` both), read from the copy loops, `file-formats.md` §2.4/§2.8.)*

**G3. `TTAB` → `CELL` resolution anomaly — V(observation) / H(cause).** In
`BONUS.WLD` 1,644 words carry index **256** while that world's `CELL` chunk
holds only 251 records; the same value is in range in every other world, so the
bank size cannot be the explanation. **Test:** find the loader's cell-array
allocation (does it size by max index + 1, or by 256-rung rounding?) — this
decides whether a writer must reject or preserve out-of-bank indices.

**G4. `CELL` pixel layout and palette-per-cell (Q8) — D/H.** 64 B records,
pretended 8×8 indices, but *no field anywhere says which of the ten `HEAD`
palettes a cell uses*, and none of the 16 bits of a `TTAB` index word is free
for one (13 index + 2 flags + 1 unused, G1). Measured support for the
documented "palette 0 only": all palette words in 104/104 `HEAD` blocks have
bit 15 clear (15-bit colour, consistent with §2.3 `[D]`). **Test:** export one
`CELL` as an 8×8 index grid, render with palettes 0 and 1, compare with a
screenshot; then grep the tile-blit for the palette-pointer argument.

**G5. `MAP` tile word — D, now measurable but unresolved.** 3 B per 16×16
cell is V (104/104, `size − 3·cells ∈ {0,1,2,3}`, pad bytes all zero). The
*word* is not: candidate readings scored on 523,229 words —
`byte0 & 0x7F` as tile index → **0 violations** (`probe13.py`), `byte0` unmasked
→ 189 violations in 6 sections, `byte1` as index → 187, `word & 0x1FFF` →
41,857. But the winning field saturates at **127** in every section that uses
tiles (max used per section ∈ {0, 105…127}) while sibling `TTAB` banks reach
**2,952** entries — so either the bank is shared per level group, or the 7-bit
field indexes something else. **Test:** find the map→tile lookup in the EXE
(the routine that turns a `MAP` word into a `TTAB` entry).

**G6. `MAP` collision byte — D.** Bit meanings (`0xC0`, `0x80`, `0x08/0x10/0x20`)
are documented, not measured. **Test:** in-game probe (walk into a cell of each
class), or the collision routine.

**G7. `ANIM` record layout — D → falsified as stated, still H.** 566 chunks:
all payloads are multiples of 4, *none* is a multiple of 0x38 (remainders
0…52 spread uniformly), so 0x38 is not a chunk-level unit. Eight header offsets
× two endiannesses for "w,h then w·h pixels" → 0/566 matches (`probe6.py`).
u16-token walkers reach at best 339/566 exact-consumption, which is not proof.
**Test:** static analysis of the `ANIM` reader in `LOMAX.EXE` (the only cheap
route left); the 52-byte chunk in `MAIN.WLD` is the smallest fixture and its
first tokens are 16, 7, 3, 0x8009, 129, 0 — a token stream, not a header.

**G8. `ANIM` ↔ `NMY` association — unknown.** 566 chunks vs 27–148 per world
and type counts of 6–73: there is no key in the data mapping a chunk to an
object type. **Test:** measure chunk order against the EXE's type array, or
compare in-game sprite changes against chunk replacements.

**G9. `NMY` table structure — D → falsified.** The documented "list of
`u16 size + NUL-terminated name`" walks **1 record** per file (8–16 B of
2,352–19,292 B) in 9/9 worlds. Measured instead: 58–212 printable runs of 4–14
chars, at even offsets, pitch 12–18 with jumps of 36/38, each run followed by
`00 00` in 70–85% of cases — a variable-length record table whose records carry
a name *plus* a binary tail. **Test:** read the `NMY` walker in the EXE; the
target check is "number of records == max `GNMY` type index + 1"
(`BONUS` 29, `WEST` 52, `HAUNTED` 73).

**G10. `GNMY` type meaning — index V, name D.** 3,593 entries of `u16` size (LE)
+ `u16` type (LE); per-world max index 16–73. Names live in `NMY` and cannot
be resolved until G9 lands. **Test:** after G9, print the record at the index of
a known object (e.g. the level start) and confirm in-game.

**G11. `MACR` / `PAGE` — wholly undocumented.** 7 each; `MACR` 24–968 B,
`PAGE` 1,092–40,344 B. A round trip only needs them copied verbatim; a **level
editor** needs them decoded. **Test:** structural probe + EXE reader.

**G12. `HEAD` sub-layout — size V, internals D.** Payload is 5,240 B (0x1478)
in 104/104. The documented segmentation is arithmetic-consistent
(`8 + 5,120 + 0x50 + 0x20 = 0x1478`); measured corroboration: all 5,120 palette
words have bit 15 clear, and 72–80 of the 80 "editor data" bytes are `0xFF` in
all 104 (i.e. mostly filler, which is consistent but not proof of the
boundary). **Test:** the `HEAD` reader in the EXE, or a `-0xFF` count sweep
to find the exact filler run.

**G13. Chunk header + `WRLD` magic — V** (`tag[4]` space-padded, BE `u32`
payload size, payload-only, `"PS-X"` + 1234). Nothing to do.

**G14. Padding rule `size & ~3` — V, and it is benign.** 1,041 chunks, `size &
~3 == size` for **every one**; `MAP` pad lengths 0–3 with all pad bytes zero
(104/104); all 9 files are 4-aligned (`probe9.py`). See §3.

**G15. Repo inconsistency — `src/lomax_modern/wldscan.py:1-17`.** The module
docstring still says the chunk header "has not been confirmed against a real
`.WLD` file inside this repository", while
[`../file-formats.md`](../file-formats.md) grades the same layout **V**. Doc-trust
bug, one-line fix, worth doing before a reader/writer is built on top
(`src/lomax_modern/measure.py:7-15` is up to date).

---

## 3. Round trip: what a byte-exact `read → write` needs

Measured on all 9 files (`probe9.py`):

1. **Structural re-emit is byte-identical in 9/9 files.** `tag + BE size +
   payload`, in reading order, reproduces 184,376 … 1,753,572 B exactly.
2. **A *semantic* rebuild of `MAP` is also byte-exact: 104/104.** Take the
   decoded cell count, keep the first `3·cells` bytes, re-pad with zeros to the
   next multiple of 4 — identical to the shipped payload every time.
3. **The `size & ~3` rule never fires on retail data.** The pad is *inside* the
   declared size, so every chunk is already 4-aligned (1,041/1,041). The LMX-5
   falsifier ("round trip may be impossible because of `size & ~3` interacting
   with per-chunk padding") is therefore **closed**: writers must pad to 4 and
   *include* the pad in the size, and readers must not assume the pad is absent.

Writer requirements that follow, all cheap to test:

- Payload sizes must be written as multiples of 4; `TTAB` (8 B/entry), `CELL`
  (64 B), `HEAD` (0x1478) and `MAP` (3·cells + pad) satisfy this by construction,
  so 2× data stays aligned too.
- Preserve `TTAB` flag bits and out-of-bank indices verbatim (G3) — do not
  "repair" index 256.
- Preserve chunk order exactly; `MACR`/`PAGE`/`PARA`/`NMY` may be opaque blobs.
- Round-trip test shape: rebuild in memory, compare `bytes ==`, **never** store
  the original or a hash of it (see §5).

---

## 4. Is 2× art representable? Byte budget and the real blocker

Only one design is container-compatible:

- **(a) one 8×8 cell stays one cell record, at 16×16 pixels → 256 B.** `TTAB`
  indices are unchanged, the 13-bit index field (max used 4,908 at `MEDIEVAL`)
  keeps 8,192 of headroom, and `TTAB` *does not grow at all* — an entry is still
  four index slots.
- **(b) four cells per 2× cell is impossible in the container.** `MEDIEVAL`
  would need 19,636 indices and `HAUNTED` 14,936, both beyond the 13-bit field
  (8,192) that the data proves (G1). That design needs a format change *and* an
  engine change; do not plan for it.

Byte growth under (a), measured inputs:

| Component | Now | At 2× | Note |
|---|---|---|---|
| `CELL` (9 files) | 958,336 B | 3,833,344 B | +2,875,008 B |
| `TTAB` (9 files) | 600,976 B | 600,976 B | unchanged (4 index slots per tile) |
| `ANIM` (9 files) | 3,201,288 B | ~12,805,152 B | 4× pixels; layout unknown (G7) |
| `WORLDS/` total | 7,107,048 B | ~9.98 MB (+40 %) | largest file `MEDIEVAL` 1.31 MB → 2.25 MB |

**No format field records geometry.** `HEAD` payload is constant, `CELL` records
are unlabelled 64 B, `TTAB` entries are 8 B of indices. A 2× pack therefore
looks exactly like 1× art to the stock engine: the cell stride (64 B), the 8×8
and 16×16 blits, the sprite extents and the HUD are engine constants
([`02-resolution.md`](02-resolution.md) §2.5 items 1–4). **Conclusion for the
roadmap: the asset pipeline (reader, exporter, matte-aware 2× scaler, repacker)
is distributable and testable with no engine work; making the game *display* 2×
art is an engine patch (LMX-5 + a render-scale hook), and 2× **sprites** are
blocked at the format level until G7 lands.**

---

## 5. Legal boundary — never in the repo vs generated at run time

**Must never enter the repository, a comment, an attachment or a log**

- any `*.WLD`, or a 2×-rebuilt variant of one; any `CELL`/`TTAB`/`MAP`/`GNMY`/
  `NMY`/`PARA`/`MACR`/`PAGE`/`ANIM` payload bytes — including a single 64-byte
  cell or one 8-byte `TTAB` entry pasted as hex;
- a `HEAD` palette block (10 × 256 words = 5,120 B): a palette is art;
- extracted or upscaled PNGs/atlases/spritesheets, *including "just one tile"* —
  upscaled output is a derivative work of Psygnosis/Sony assets;
- `LOMAX.EXE`, disc images, `*.DAT`, `*.WAV`, `GAME.TXT` content;
- full digests of copyrighted files (prefix only, as Q14 already does), and any
  hash quoted into chat must be masked (`sed -E 's/[0-9a-f]{64}/[sha256 omitted]/g'`);
- any code, comment or doc prose from `Lomax+` (licence `null` = all rights
  reserved). Facts — addresses, offsets, layouts — may be used **with citation**
  ([`03-prior-art.md`](03-prior-art.md)).

**May live in the repo (authored or generated at run time)**

- readers/writers/exporters/scalers/repacker code; a `measure`-style probe;
- synthetic fixtures built by the test itself (`tests/fixtures/synth.py`);
- **structural** statistics: counts, sizes, offsets, histograms, index-coverage
  numbers, byte-value histograms — the numbers in this document are exactly
  that, and they are publishable;
- tests that rebuild *the user's own* file in memory and compare `bytes ==`
  against it at run time (no golden file, no stored hash).

**Run-time-only, never committed**

- any transformation of the user's install: the tool takes `LOMAX_GAME_DIR`,
  writes a backup beside the user's own file, and must refuse to write anywhere
  else. Distribute the *generator* and a patch recipe, never a 2× pack.

---

## 6. Suggested follow-ups (for the card owner, not applied here)

1. LMX-5 first step is now concrete: `TTAB` re-emit with flag bits preserved,
  asserted on all 104 sections, plus the `MAP` semantic rebuild (§3, 104/104).
2. Promote G1/G9/G14 to `V` in [`../file-formats.md`](../file-formats.md)
  §2.2–2.4 and mark the two
  falsified `D` claims (`ANIM` 0x38 records, `NMY` length-prefixed names) as
  `retracted`, quoting `probe*.py` output.
3. Open Q8 stays `blocked`, but the *reason* narrows: no palette field exists in
  `TTAB`, so a per-cell palette must live in `NMY`/`MACR`/`PAGE` or nowhere.
4. Fix `wldscan.py:1-17` (G15).
