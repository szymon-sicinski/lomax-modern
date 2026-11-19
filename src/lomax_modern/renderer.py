"""The M4 renderer: a 16-bit ``B5G6R5`` framebuffer, palette lookup and blit.

This is the own-engine *renderer* half of the presenter (``docs/roadmap/
15-strategy-report.md`` §6): it draws the decoded ``CELL``/``TTAB``/``MAP`` data
into a 16-bit ``B5G6R5`` framebuffer with correct palette conversion and
transparency.  It is a clean-room implementation — it never reads ``LOMAX.EXE``
and it interprets nothing beyond the measured layout in
``docs/file-formats.md``.

Two halves, one rule set
------------------------

The hot path belongs in C (``native/``, built in CI only — see
``docs/architecture.md`` §5); this module is the **reference implementation and
test oracle**.  ``native/renderer.c`` reproduces these functions bit-for-bit and
its smoke binary asserts the same golden words the unit tests here assert.  The
rules are therefore stated once, in this module, and the C port is graded
against them.

Confidence, per claim (see ``docs/file-formats.md``):

**Verified against the retail install (V)**

* A ``CELL`` record is 8x8 palette indices (whole 64-byte records).
* A ``TTAB`` record is 16 bytes = four ``[index word, flag word]`` cells; the
  index word is a full 16-bit ``CELL`` index and the flag word carries the flip
  pair in bits 13-14 and a palette in bits 8-11.  A ``MAP`` cell is one
  big-endian ``u16`` tile word (a direct ``TTAB`` record index) plus one
  collision byte — ``N`` words then ``N`` collision bytes, padded to a multiple
  of 4.
* The ``HEAD`` palette block is 10 x 256 little-endian 15-bit words.

**Design choice, stated so a test can pin it (H)**

* *Palette conversion.*  The game's palettes are 15-bit (blue bits 0-4, green
  5-9, red 10-14) and the frame is 16-bit ``B5G6R5``, so each 15-bit word is
  widened: red and blue pass through 5->5, green 5->6 by bit replication
  (``g6 = g5<<1 | g5>>4``).  That is the round-trip-preserving expansion and the
  one the hardware uses; whether the retail exe truncated instead is not
  measured, so it is labelled ``[H]``.
* *Transparency.*  Index 0 is the transparent key (``docs/file-formats.md``
  §2.3 ``[D]``): a blit leaves the destination pixel untouched for index 0, so
  the key colour is never painted.
* *Cell pixel order.*  Row-major 8x8, the same ``[H]`` reading the exporter
  uses.
* *Tile cell order.*  A ``TTAB`` record's four cells are placed in stored order
  (``"strip"``) by default; the documented 16x16 2x2 assembly is an explicit
  ``"2x2"`` option and is labelled ``[H]`` (the seam test failed, see
  ``art``).
* *Flip pairing.*  Bits 13-14 are the flip pair ``[V]`` (three combinations
  occur, Q21); that ``0x2000`` is the *horizontal* one and ``0x4000`` the
  vertical is this decoder's convention ``[H]`` — no render has been compared
  against the game (Q33).  A flipped cell occupies the same 8x8 destination box
  as its unflipped form.

**Kept explicit so a test can pin it**

* *Palette selection.*  A flag word names a palette slot in bits 8-11, but
  :func:`Framebuffer.blit_tile` takes a single :class:`Palette565` (the
  exporter's default slot) and does not switch slots per cell; multi-slot
  selection is out of the M4 blit contract.
* *Map->tile art blit.*  A ``MAP`` word is a direct ``TTAB`` record index
  (Q20).  :meth:`blit_map_field` still draws the raw ``MAP`` byte as greyscale
  — a field visualisation — while the map->tile *art* assembly is the engine's
  job and now lives in :func:`lomax_modern.engine.render_tiles`, which calls
  :meth:`blit_tile` once per visible map cell.

The fade rule
-------------

The fade/dissolve surface is rounded up to a multiple of 32
(``docs/research/02-resolution.md`` §2.4): :func:`fade_surface_width` returns
``ceil(w / 32) * 32``.  Because we own the renderer, this ceiling is ours to
lift (M9) rather than a patch target — but the rule is still honoured so the
authentic frame matches the original allocation.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Sequence

from . import art
from .art import (
    FLIP_H,
    FLIP_MASK,
    FLIP_V,
    PALETTE_BLOCK_OFFSET,
    PALETTE_BLOCK_SIZE,
    PALETTE_ENTRY_COUNT,
    PALETTE_SLOT_COUNT,
    ArtError,
    Cell,
    MapPlane,
    TileRecord,
)
from .scaler import Image, Mode

#: Index into a palette slot that is the transparent key (never painted).
TRANSPARENT_INDEX = 0

#: Pixels per side of a ``CELL`` block (``docs/file-formats.md`` §2.4 ``[V]``).
CELL_PIXELS = 8

#: Tile cell-order layouts: stored order, or the documented (``[H]``) 2x2 tile.
TILE_LAYOUTS = ("strip", "2x2")

#: ``MAP`` raw-byte channels the field blit can visualise.
MAP_CHANNELS = ("collision", "word-hi", "word-lo")


def rgb15_to_rgb565(word: int) -> int:
    """Widen a 15-bit little-endian colour to a 16-bit ``B5G6R5`` word.

    Source layout (``docs/file-formats.md`` §2.3 ``[V]``): blue bits 0-4,
    green 5-9, red 10-14.  Red and blue stay 5 bits; green widens 5->6 by bit
    replication (``[H]``, see the module docstring), so a 15-bit value and its
    16-bit form carry the same colour.
    """
    if not 0 <= word < 0x8000:
        raise ValueError(f"not a 15-bit colour word: {word}")
    red = (word >> 10) & 0x1F
    green = (word >> 5) & 0x1F
    blue = word & 0x1F
    green6 = (green << 1) | (green >> 4)
    return (red << 11) | (green6 << 5) | blue


def rgb565_to_rgb15(word: int) -> int:
    """Narrow a ``B5G6R5`` word back to 15-bit (inverse of :func:`rgb15_to_rgb565`).

    Green drops its low bit (``g5 = g6 >> 1``), which inverts the bit-replicated
    widening exactly for every colour a 15-bit source can express.
    """
    if not 0 <= word < 0x10000:
        raise ValueError(f"not a 16-bit colour word: {word}")
    red = (word >> 11) & 0x1F
    green = (word >> 5) & 0x3F
    blue = word & 0x1F
    return (red << 10) | ((green >> 1) << 5) | blue


def rgb565_to_rgb8(word: int) -> tuple[int, int, int]:
    """Widen a ``B5G6R5`` word to 8-bit channels by bit replication.

    Red and blue are 5 bits, green is 6, so each channel is widened with the
    same rule — shift up and replicate the top bits into the gap::

        r8 = r5 << 3 | r5 >> 2      g8 = g6 << 2 | g6 >> 4      b8 = b5 << 3 | b5 >> 2

    Bit replication is the only expansion that keeps full white at 255 and full
    black at 0 while making every 5/6-bit step the same width.  The tempting
    variant ``g6 << 2 | g6 >> 2`` (which the green channel used before the
    conformance harness measured it) is not replication: it changes 55 of the 64 green values — over-brightens 46 by up to 12/255, under-brightens 9 by up to 3/255
    — enough to fail a depth 16 vs 24 comparison.
    """
    if not 0 <= word < 0x10000:
        raise ValueError(f"not a 16-bit colour word: {word}")
    red = (word >> 11) & 0x1F
    green = (word >> 5) & 0x3F
    blue = word & 0x1F
    return ((red << 3) | (red >> 2), (green << 2) | (green >> 4), (blue << 3) | (blue >> 2))


def fade_surface_width(width: int) -> int:
    """Round ``width`` up to a multiple of 32 — the fade/dissolve surface rule.

    ``ceil(w / 32) * 32`` (``docs/research/02-resolution.md`` §2.4).  A negative
    or non-integer width is rejected rather than silently rounded, because a
    wrong surface width is a bug that survives to the screen.
    """
    if isinstance(width, bool) or not isinstance(width, int):
        raise TypeError(f"width must be an int, got {type(width).__name__}")
    if width < 0:
        raise ValueError(f"width must be >= 0, got {width}")
    return -(-width // 32) * 32


@dataclass(frozen=True)
class Palette565:
    """One ``HEAD`` palette slot converted to 256 ``B5G6R5`` words.

    ``transparent_index`` is never painted by a blit; the word stored at that
    index is kept so the palette round-trips, but the blit path skips it.
    """

    slot: int
    words: tuple[int, ...]
    transparent_index: int = TRANSPARENT_INDEX

    def __post_init__(self) -> None:
        if len(self.words) != PALETTE_ENTRY_COUNT:
            raise ArtError(
                f"palette slot {self.slot} holds {len(self.words)} words, "
                f"expected {PALETTE_ENTRY_COUNT}"
            )
        bad = [w for w in self.words if not 0 <= w < 0x10000]
        if bad:
            raise ArtError(f"palette word {bad[0]} does not fit in 16 bits")

    def __len__(self) -> int:
        return len(self.words)

    def word(self, index: int) -> int:
        if not 0 <= index < len(self.words):
            raise ArtError(f"palette index {index} outside 0-{len(self.words) - 1}")
        return self.words[index]


def head_palette565(head_chunk, slot: int = art.DEFAULT_PALETTE_SLOT) -> Palette565:
    """Build a :class:`Palette565` from a ``HEAD`` chunk's ``slot``.

    Reads the same 512-byte slot region the exporter reads (``art``), then
    widens each 15-bit word to ``B5G6R5`` with :func:`rgb15_to_rgb565`.
    """
    if head_chunk.tag != "HEAD":
        raise ArtError(f"head_palette565() needs a HEAD chunk, got {head_chunk.tag!r}")
    payload = head_chunk.payload
    if len(payload) < PALETTE_BLOCK_OFFSET + PALETTE_BLOCK_SIZE:
        raise ArtError(
            f"HEAD payload is {len(payload)} bytes; the palette block needs "
            f"{PALETTE_BLOCK_OFFSET + PALETTE_BLOCK_SIZE}"
        )
    if not 0 <= slot < PALETTE_SLOT_COUNT:
        raise ArtError(f"palette slot must be 0-{PALETTE_SLOT_COUNT - 1}, got {slot}")
    start = PALETTE_BLOCK_OFFSET + slot * PALETTE_ENTRY_COUNT * 2
    raw = struct.unpack(
        "<" + "H" * PALETTE_ENTRY_COUNT,
        payload[start : start + PALETTE_ENTRY_COUNT * 2],
    )
    return Palette565(slot=slot, words=tuple(rgb15_to_rgb565(w) for w in raw))


class Framebuffer:
    """A mutable 16-bit ``B5G6R5`` framebuffer with the blit primitives.

    Pixels are packed ``u16`` words; ``to_bytes()`` emits little-endian words
    suitable for a 16-bit surface, and :meth:`to_image` hands the buffer to the
    scaler/presenter unchanged.  ``set`` clips silently, so a tile blitted
    partly off-screen is clipped rather than rejected.
    """

    def __init__(self, width: int, height: int, fill: int = 0) -> None:
        if width <= 0 or height <= 0:
            raise ValueError(f"framebuffer must be positive, got {width}x{height}")
        self.width = width
        self.height = height
        self.pixels = [fill] * (width * height)

    def set(self, x: int, y: int, value: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y * self.width + x] = value

    def pixel(self, x: int, y: int) -> int:
        return self.pixels[y * self.width + x]

    def fill_rect(self, x0: int, y0: int, w: int, h: int, value: int) -> None:
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                self.set(x, y, value)

    def blit_cell(
        self,
        cell: Cell,
        palette: Palette565,
        x0: int,
        y0: int,
        *,
        flip: int = 0,
        transparent_index: int = TRANSPARENT_INDEX,
    ) -> None:
        """Draw one 8x8 cell at ``(x0, y0)``; index ``transparent_index`` is skipped.

        ``flip`` is ``FLIP_H``/``FLIP_V`` (or both) from a tile flag word; the
        cell is mirrored about its own axis so it still occupies the same 8x8
        destination box.
        """
        for dy in range(CELL_PIXELS):
            for dx in range(CELL_PIXELS):
                sx = (CELL_PIXELS - 1 - dx) if flip & FLIP_H else dx
                sy = (CELL_PIXELS - 1 - dy) if flip & FLIP_V else dy
                index = cell.pixels[sy * CELL_PIXELS + sx]
                if index == transparent_index:
                    continue
                self.set(x0 + dx, y0 + dy, palette.word(index))

    def blit_tile(
        self,
        record: TileRecord,
        cells: Sequence[Cell],
        palette: Palette565,
        x0: int,
        y0: int,
        *,
        layout: str = "strip",
        transparent_index: int = TRANSPARENT_INDEX,
    ) -> None:
        """Draw a ``TTAB`` record as its four cells, in ``layout`` order.

        ``"strip"`` places the four cells side by side (stored order, 32x8);
        ``"2x2"`` assembles the documented 16x16 tile (cell order ``[H]``).
        Each cell honours its flag word's flip; a cell index outside the bank
        is left empty (background), never repaired.
        """
        if layout not in TILE_LAYOUTS:
            raise ArtError(f"layout must be {TILE_LAYOUTS}, got {layout!r}")
        for slot, cell_slot in enumerate(record.slots):
            if not 0 <= cell_slot.index < len(cells):
                continue
            if layout == "strip":
                dx, dy = slot * CELL_PIXELS, 0
            else:
                dx = (slot % 2) * CELL_PIXELS
                dy = (slot // 2) * CELL_PIXELS
            self.blit_cell(
                cells[cell_slot.index],
                palette,
                x0 + dx,
                y0 + dy,
                flip=cell_slot.flip,
                transparent_index=transparent_index,
            )

    def blit_map_field(
        self,
        plane: MapPlane,
        x0: int = 0,
        y0: int = 0,
        *,
        channel: str = "collision",
        scale: int = 1,
    ) -> None:
        """Draw one raw ``MAP`` byte per cell as greyscale (no invented art).

        ``channel`` picks the collision byte or one byte of the tile word (a
        direct ``TTAB`` record index); the value is drawn verbatim as greyscale,
        so the field is made visible, never re-derived.  Value 0 (empty) is
        skipped.  This is a field visualisation, not the map->tile art blit.
        """
        if channel not in MAP_CHANNELS:
            raise ArtError(f"channel must be {MAP_CHANNELS}, got {channel!r}")
        if scale < 1:
            raise ArtError(f"scale must be >= 1, got {scale}")
        for cy in range(plane.height_cells):
            for cx in range(plane.width_cells):
                cell = plane.at(cx, cy)
                if channel == "collision":
                    value = cell.collision
                elif channel == "word-hi":
                    value = (cell.tile_word >> 8) & 0xFF
                else:
                    value = cell.tile_word & 0xFF
                if value == 0:
                    continue
                # 8-bit byte -> 5/6/5 grey by truncation; byte values 1..7
                # collapse to black in 5-bit precision (inherent, not a bug).
                grey = (value >> 3) << 11 | (value >> 2) << 5 | (value >> 3)
                self.fill_rect(x0 + cx * scale, y0 + cy * scale, scale, scale, grey)

    def to_bytes(self) -> bytes:
        """The buffer as little-endian ``u16`` words (a real 16-bit surface)."""
        return struct.pack("<" + "H" * len(self.pixels), *self.pixels)

    def to_image(self) -> Image:
        """Freeze the buffer as a scaler ``Image`` in ``RGB565`` mode."""
        return Image(Mode.RGB565, self.width, self.height, tuple(self.pixels))

    def to_rgba(self) -> bytes:
        """Convert the buffer to RGBA8888 bytes (opaque), for PNG export.

        Channels are widened with :func:`rgb565_to_rgb8` (bit replication), so
        the exported image carries the same colour the surface does.
        """
        out = bytearray()
        for word in self.pixels:
            out += bytes((*rgb565_to_rgb8(word), 255))
        return bytes(out)
