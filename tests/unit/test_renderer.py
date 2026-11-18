"""Tests for the M4 renderer: palette conversion, transparency blit, fade rule.

Synthetic fixtures only: every byte is generated here or by
``tests/fixtures/synth.py``.  No game data is read or written.  What is graded:

* ``rgb15_to_rgb565`` widens the 15-bit palette to ``B5G6R5`` with the exact
  bit-replication rule (and its inverse round-trips);
* the cell blit paints the palette word for every non-transparent index and
  leaves the destination untouched for index 0 — so the key colour never leaks;
* the tile blit places four cells in stored order (``strip``) or the documented
  2x2 order, and skips out-of-bank indices instead of inventing pixels;
* the fade-surface rule rounds any width up to a multiple of 32;
* the ``MAP`` field blit draws raw bytes as greyscale, never art.

The golden ``B5G6R5`` words here are hand-derived from the synthetic palette
and are the same words ``native/smoke.c`` asserts, so the C port and this
oracle are graded against one rule set.
"""

from __future__ import annotations

import struct

import pytest

from lomax_modern import art
from lomax_modern.renderer import (
    Palette565,
    TRANSPARENT_INDEX,
    Framebuffer,
    fade_surface_width,
    head_palette565,
    rgb15_to_rgb565,
    rgb565_to_rgb15,
)
from lomax_modern.scaler import Mode
from lomax_modern.wld import Chunk
from tests.fixtures.synth import cell_payload, head_payload, ttab_payload


def chunk(tag: str, payload: bytes) -> Chunk:
    return Chunk(
        tag=tag,
        tag_field=tag.encode("ascii").ljust(4, b" "),
        size=len(payload),
        payload=payload,
        header_offset=0,
    )


def cell(*rows) -> art.Cell:
    """An 8x8 ``Cell`` from rows of palette indices."""
    flat = [index for row in rows for index in row]
    assert len(flat) == 64, f"cell needs 64 indices, got {len(flat)}"
    assert all(0 <= i < 256 for i in flat)
    return art.Cell(index=0, pixels=bytes(flat))


#: Hand-written 15-bit source words and their expected ``B5G6R5`` widening.
RGB15_TO_565 = [
    (0x7FFF, 0xFFFF),  # white: r31 g31 b31 -> r31 g63 b31
    (0x7C00, 0xF800),  # red
    (0x03E0, 0x07E0),  # green 5-bit 31 -> 6-bit 63 (bit replication)
    (0x001F, 0x001F),  # blue
    (0x0020, 0x0040),  # green 5-bit 1 -> 6-bit 2
    (0x0000, 0x0000),  # black
]


#: Golden palette for the blit tests: B5G6R5 words, index 0 the transparent key.
PAL_WORDS = [0] * 256
PAL_WORDS[0] = 0xF81F  # magenta — transparent, must never be painted
PAL_WORDS[1] = 0xF800  # red
PAL_WORDS[2] = 0x07E0  # green
PAL_WORDS[3] = 0x001F  # blue
PAL_WORDS[4] = 0xFFFF  # white
PALETTE = Palette565(slot=0, words=tuple(PAL_WORDS))


# ---------------------------------------------------------------------------
# Palette conversion
# ---------------------------------------------------------------------------


def test_rgb15_to_rgb565_golden() -> None:
    for src, expected in RGB15_TO_565:
        assert rgb15_to_rgb565(src) == expected, f"0x{src:04X}"


def test_rgb565_to_rgb15_round_trips() -> None:
    for src, _ in RGB15_TO_565:
        assert rgb565_to_rgb15(rgb15_to_rgb565(src)) == src


def test_rgb15_to_rgb565_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        rgb15_to_rgb565(0x8000)
    with pytest.raises(ValueError):
        rgb15_to_rgb565(-1)


# ---------------------------------------------------------------------------
# Fade-surface width rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("width", "expected"),
    [
        (0, 0),
        (1, 32),
        (31, 32),
        (32, 32),
        (33, 64),
        (320, 320),
        (336, 352),
        (384, 384),
        (432, 448),
        (448, 448),
        (512, 512),
        (560, 576),
        (640, 640),
        (7200, 7200),
        (7201, 7232),
    ],
)
def test_fade_surface_width(width: int, expected: int) -> None:
    assert fade_surface_width(width) == expected


def test_fade_surface_width_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        fade_surface_width(-1)
    with pytest.raises(TypeError):
        fade_surface_width(3.5)
    with pytest.raises(TypeError):
        fade_surface_width(True)


# ---------------------------------------------------------------------------
# Cell blit: palette lookup + transparency
# ---------------------------------------------------------------------------


def test_blit_cell_golden_frame() -> None:
    """The hand-derived scene: palette words painted, index 0 skipped."""
    scene = cell(
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 0, 0, 0, 0, 0, 0, 4],
        [4, 0, 1, 1, 1, 1, 0, 4],
        [4, 0, 1, 2, 2, 1, 0, 4],
        [4, 0, 1, 2, 3, 2, 0, 4],
        [4, 0, 1, 1, 1, 1, 0, 4],
        [4, 0, 0, 0, 0, 0, 0, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
    )
    fb = Framebuffer(8, 8, fill=0x0000)
    fb.blit_cell(scene, PALETTE, 0, 0)

    expected = [
        0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF,
        0xFFFF, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0xFFFF,
        0xFFFF, 0x0000, 0xF800, 0xF800, 0xF800, 0xF800, 0x0000, 0xFFFF,
        0xFFFF, 0x0000, 0xF800, 0x07E0, 0x07E0, 0xF800, 0x0000, 0xFFFF,
        0xFFFF, 0x0000, 0xF800, 0x07E0, 0x001F, 0x07E0, 0x0000, 0xFFFF,
        0xFFFF, 0x0000, 0xF800, 0xF800, 0xF800, 0xF800, 0x0000, 0xFFFF,
        0xFFFF, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0xFFFF,
        0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF,
    ]
    assert fb.pixels == expected
    # The transparent key colour (0xF81F) never appears.
    assert 0xF81F not in fb.pixels


def test_blit_cell_leaves_background_on_transparent() -> None:
    """Index 0 leaves the destination; a non-black background is preserved."""
    fb = Framebuffer(8, 8, fill=0xFFFF)  # white background
    hole = cell(*([0] * 8 for _ in range(8)))
    fb.blit_cell(hole, PALETTE, 0, 0)
    assert all(px == 0xFFFF for px in fb.pixels)


def test_blit_cell_clips_at_edges() -> None:
    fb = Framebuffer(8, 8, fill=0x0000)
    solid = cell(*([4] * 8 for _ in range(8)))
    fb.blit_cell(solid, PALETTE, 6, 6)  # only the 2x2 overlap is inside
    assert [fb.pixel(x, y) for x in range(6) for y in range(8)] == [0] * 48
    assert fb.pixel(6, 6) == 0xFFFF and fb.pixel(7, 7) == 0xFFFF
    assert fb.pixel(0, 0) == 0x0000


# ---------------------------------------------------------------------------
# Tile blit: four cells in stored or 2x2 order
# ---------------------------------------------------------------------------


def _solid_cells(*words) -> tuple[art.Cell, ...]:
    cells = []
    for w in words:
        idx = PAL_WORDS.index(w)
        cells.append(cell(*([idx] * 8 for _ in range(8))))
    return tuple(cells)


def _tile_record(*indices) -> art.TileRecord:
    payload = ttab_payload([indices])
    records = art.decode_tiles(chunk("TTAB", payload))
    return records[0]


def test_blit_tile_strip_is_stored_order() -> None:
    red, green, blue, white = _solid_cells(0xF800, 0x07E0, 0x001F, 0xFFFF)
    record = _tile_record(0, 1, 2, 3)
    fb = Framebuffer(32, 8, fill=0x0000)
    fb.blit_tile(record, (red, green, blue, white), PALETTE, 0, 0, layout="strip")
    assert fb.pixel(0, 0) == 0xF800
    assert fb.pixel(8, 0) == 0x07E0
    assert fb.pixel(16, 0) == 0x001F
    assert fb.pixel(24, 0) == 0xFFFF


def test_blit_tile_2x2_is_documented_layout() -> None:
    red, green, blue, white = _solid_cells(0xF800, 0x07E0, 0x001F, 0xFFFF)
    record = _tile_record(0, 1, 2, 3)
    fb = Framebuffer(16, 16, fill=0x0000)
    fb.blit_tile(record, (red, green, blue, white), PALETTE, 0, 0, layout="2x2")
    assert fb.pixel(0, 0) == 0xF800
    assert fb.pixel(8, 0) == 0x07E0
    assert fb.pixel(0, 8) == 0x001F
    assert fb.pixel(8, 8) == 0xFFFF


def test_blit_tile_skips_out_of_bank_index() -> None:
    # Index 99 names no cell in a 4-cell bank: skipped, background preserved.
    record = _tile_record(0, 99, 1, 2)
    red, green, blue = _solid_cells(0xF800, 0x07E0, 0x001F)
    fb = Framebuffer(32, 8, fill=0x0000)
    fb.blit_tile(record, (red, green, blue), PALETTE, 0, 0, layout="strip")
    assert fb.pixel(0, 0) == 0xF800
    assert fb.pixel(8, 0) == 0x0000  # the out-of-bank slot stays background
    assert fb.pixel(16, 0) == 0x07E0


def test_blit_tile_rejects_unknown_layout() -> None:
    with pytest.raises(art.ArtError):
        Framebuffer(8, 8).blit_tile(
            _tile_record(0, 1, 2, 3), (), PALETTE, 0, 0, layout="diagonal"
        )


# ---------------------------------------------------------------------------
# MAP field blit (raw bytes, no invented art)
# ---------------------------------------------------------------------------


def _map_plane(width_cells: int = 2, height_cells: int = 1) -> art.MapPlane:
    # two cells: (tile_word 0xABCD, collision 255), (tile_word 0, collision 0)
    return art.MapPlane(
        width_cells=width_cells,
        height_cells=height_cells,
        cells=(
            art.MapCell(tile_word=0xABCD, collision=255),
            art.MapCell(tile_word=0x0000, collision=0),
        ),
        pad=b"",
    )


def test_blit_map_field_draws_collision_greyscale_and_skips_zero() -> None:
    fb = Framebuffer(2, 1, fill=0x0000)
    fb.blit_map_field(_map_plane(), channel="collision", scale=1)
    assert fb.pixel(0, 0) == 0xFFFF  # collision 255 -> full white grey
    assert fb.pixel(1, 0) == 0x0000  # collision 0 -> skipped


def test_blit_map_field_word_bytes_differ() -> None:
    hi = Framebuffer(2, 1)
    lo = Framebuffer(2, 1)
    hi.blit_map_field(_map_plane(), channel="word-hi")
    lo.blit_map_field(_map_plane(), channel="word-lo")
    assert hi.pixel(0, 0) != lo.pixel(0, 0)  # 0xAB vs 0xCD differ


def test_blit_map_field_rejects_unknown_channel() -> None:
    with pytest.raises(art.ArtError):
        Framebuffer(2, 1).blit_map_field(_map_plane(), channel="alpha")


# ---------------------------------------------------------------------------
# HEAD palette -> Palette565
# ---------------------------------------------------------------------------


def test_head_palette565_converts_slot() -> None:
    words = [0] * 256
    words[1] = 0x7C00  # red
    words[2] = 0x03E0  # green
    head = chunk("HEAD", head_payload(8, 4, palettes=[[0] * 256, words]))
    palette = head_palette565(head, slot=1)
    assert palette.word(1) == 0xF800
    assert palette.word(2) == 0x07E0
    assert palette.word(0) == 0x0000
    assert palette.transparent_index == TRANSPARENT_INDEX


def test_head_palette565_rejects_wrong_tag() -> None:
    with pytest.raises(art.ArtError):
        head_palette565(chunk("CELL", b"\0" * 64))


# ---------------------------------------------------------------------------
# Framebuffer <-> scaler.Image / bytes / RGBA
# ---------------------------------------------------------------------------


def test_framebuffer_to_image_and_bytes_round_trip() -> None:
    fb = Framebuffer(2, 1, fill=0x0000)
    fb.set(0, 0, 0xF800)
    fb.set(1, 0, 0x07E0)

    image = fb.to_image()
    assert image.mode is Mode.RGB565
    assert image.pixels == (0xF800, 0x07E0)

    raw = fb.to_bytes()
    assert raw == struct.pack("<2H", 0xF800, 0x07E0)


def test_framebuffer_to_rgba_expands_channels() -> None:
    fb = Framebuffer(1, 1, fill=0xFFFF)  # white
    assert fb.to_rgba() == bytes((255, 255, 255, 255))
    fb.set(0, 0, 0xF800)  # pure red
    assert fb.to_rgba() == bytes((255, 0, 0, 255))


def test_framebuffer_rejects_bad_size() -> None:
    with pytest.raises(ValueError):
        Framebuffer(0, 8)
