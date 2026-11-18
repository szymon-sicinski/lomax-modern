"""Tests for the integer scaler and pixel-art filter (synthetic buffers only).

The buffers here are built from strings and small word tables; no game data is
read or written.  What is graded:

* nearest-neighbour is exact block replication and invents no colour;
* the filter rounds stair steps, leaves 1-px lines and 1-px dither alone, never
  exceeds half coverage and never paints the transparent index;
* the fit is the largest *integer* scale, both axes share it, pads are explicit;
* the side-by-side demo really draws two different panels.
"""

from __future__ import annotations

import importlib.util
import struct
import zlib
from pathlib import Path

import pytest

from lomax_modern.scaler import (
    Filter,
    Fit,
    Image,
    Mode,
    epx_aa,
    fit_scale,
    nearest,
    pack_rgb565,
    present,
    scale,
    unpack_rgb565,
)

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "examples" / "scale_demo.py"

#: Glyph -> palette index for indexed fixtures (same legend as the demo).
GLYPHS = {".": 1, "#": 2, "o": 3, "@": 4}

#: Glyph -> B5G6R5 word for rgb565 fixtures.
COLOURS = {
    "k": pack_rgb565(0, 0, 0),  # black
    "w": pack_rgb565(31, 63, 31),  # white
    "r": pack_rgb565(31, 0, 0),  # red
    "g": pack_rgb565(0, 63, 0),  # green
    "b": pack_rgb565(0, 0, 31),  # blue
}


def indexed(*rows: str) -> Image:
    """Indexed buffer from glyph rows; the glyph set maps to indices 1..4."""
    width = len(rows[0])
    assert all(len(row) == width for row in rows), "rows must be equal length"
    values = []
    for row in rows:
        for glyph in row:
            assert glyph in GLYPHS, f"unknown glyph {glyph!r}"
            values.append(GLYPHS[glyph])
    return Image(Mode.INDEXED8, width, len(rows), tuple(values))


def rgb565(*rows: str) -> Image:
    """B5G6R5 buffer from glyph rows."""
    width = len(rows[0])
    assert all(len(row) == width for row in rows), "rows must be equal length"
    values = []
    for row in rows:
        for glyph in row:
            assert glyph in COLOURS, f"unknown colour glyph {glyph!r}"
            values.append(COLOURS[glyph])
    return Image(Mode.RGB565, width, len(rows), tuple(values))


def blocks(image: Image, factor: int) -> list[tuple[int, ...]]:
    """Split a scaled image back into the per-source-pixel blocks."""
    return [
        tuple(
            image.at(x * factor + i, y * factor + j)
            for j in range(factor)
            for i in range(factor)
        )
        for y in range(image.height // factor)
        for x in range(image.width // factor)
    ]


# --------------------------------------------------------------------------
# nearest
# --------------------------------------------------------------------------


def test_nearest_replicates_every_pixel_into_a_block() -> None:
    source = indexed(".o", "o.")
    out = nearest(source, 3)
    assert (out.width, out.height) == (6, 6)
    assert (out.mode, len(out.pixels)) == (Mode.INDEXED8, 36)
    for y in range(6):
        for x in range(6):
            assert out.at(x, y) == source.at(x // 3, y // 3)


def test_nearest_invents_no_colour_in_either_mode() -> None:
    for source in (indexed(".o", "o."), rgb565("kr", "gk")):
        out = nearest(source, 4)
        assert set(out.pixels) <= set(source.pixels)


def test_nearest_at_factor_one_is_the_same_buffer() -> None:
    source = indexed(".#", "o@")
    assert nearest(source, 1) == source


def test_scale_dispatches_on_the_filter_name() -> None:
    source = indexed("...", ".o.", "...")
    assert scale(source, 2, Filter.NEAREST) == nearest(source, 2)
    assert scale(source, 2, "nearest") == nearest(source, 2)
    assert scale(source, 2, "epx-aa") == epx_aa(source, 2)
    assert scale(source, 2) == nearest(source, 2)


@pytest.mark.parametrize("factor", [0, -1, -8])
def test_negative_or_zero_factors_are_rejected(factor: int) -> None:
    with pytest.raises(ValueError, match=">= 1"):
        nearest(indexed("..", ".."), factor)


@pytest.mark.parametrize("factor", [1.5, "2", None, True])
def test_factors_must_be_plain_integers(factor: object) -> None:
    with pytest.raises(TypeError, match="must be an int"):
        nearest(indexed("..", ".."), factor)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# epx_aa — what it must not do
# --------------------------------------------------------------------------


def test_epx_aa_leaves_a_flat_region_untouched() -> None:
    out = epx_aa(rgb565("wwww", "wwww", "wwww", "wwww"), 3)
    assert set(out.pixels) == {COLOURS["w"]}


def test_epx_aa_does_not_smear_a_one_pixel_diagonal_line() -> None:
    """EPX rounds the line's outside steps but never bleeds it into the field.

    Two failure modes are excluded: a smear (line colour appearing in
    background pixels that have no line-coloured neighbour) and an erasure (a
    line pixel's block losing its colour entirely).
    """
    source = indexed(
        "o....",
        ".o...",
        "..o..",
        "...o.",
        "....o",
    )
    line, background = 3, 1
    for factor in (2, 3, 4):
        out = epx_aa(source, factor)
        assert set(out.pixels) <= set(source.pixels)
        for y in range(source.height):
            for x in range(source.width):
                block = [
                    out.at(x * factor + i, y * factor + j)
                    for j in range(factor)
                    for i in range(factor)
                ]
                if source.at(x, y) == line:
                    assert line in block, "the line must never be erased"
                    continue
                touches_line = any(
                    source.at(x + dx, y + dy) == line
                    for dy in (-1, 0, 1)
                    for dx in (-1, 0, 1)
                )
                if touches_line:
                    continue
                assert set(block) == {background}, "a smear reached two pixels out"


def test_epx_aa_leaves_a_one_pixel_checkerboard_untouched() -> None:
    """1-px dither art must not collapse into a grey average."""
    source = rgb565(
        "kwkwkwk",
        "wkwkwkw",
        "kwkwkwk",
        "wkwkwkw",
        "kwkwkwk",
        "wkwkwkw",
        "kwkwkwk",
    )
    out = epx_aa(source, 3)
    assert set(out.pixels) <= set(source.pixels)
    assert out.pixels.count(COLOURS["k"]) == source.pixels.count(COLOURS["k"]) * 9


def test_epx_aa_at_factor_one_is_the_same_buffer() -> None:
    source = rgb565("kw", "wk")
    assert epx_aa(source, 1) == source


# --------------------------------------------------------------------------
# epx_aa — what it must do
# --------------------------------------------------------------------------


def test_epx_aa_rounds_each_outside_corner_of_a_block() -> None:
    """A block's four corners take the background colour at their outward corner."""
    source = indexed(
        ".....",
        ".ooo.",
        ".ooo.",
        ".ooo.",
        ".....",
    )
    out = epx_aa(source, 2)
    assert source.at(1, 1) == 3
    assert out.at(2, 2) == 1  # (1,1) north-west sub-pixel
    assert out.at(7, 2) == 1  # (3,1) north-east
    assert out.at(2, 7) == 1  # (1,3) south-west
    assert out.at(7, 7) == 1  # (3,3) south-east
    # Each corner pixel rounds exactly one sub-pixel; the rest is untouched.
    changed = [
        (block_index % 5, block_index // 5)
        for block_index, block in enumerate(blocks(out, 2))
        if block != (source.pixels[block_index],) * 4
    ]
    assert sorted(changed) == [(1, 1), (1, 3), (3, 1), (3, 3)]


def test_epx_aa_preserves_an_isolated_pixel_in_both_directions() -> None:
    """One-pixel detail and one-pixel holes are left alone.

    EPX cannot tell an eye or a sparkle from a hole in a surface, so the safe
    behaviour is to keep both sharp rather than erase art. This is a documented
    limit of the filter, not an oversight.
    """
    hole = indexed(
        "ooooo",
        "oo.oo",
        "ooooo",
    )
    out = epx_aa(hole, 3)
    assert set(out.pixels) <= set(hole.pixels)
    assert out.pixels.count(1) == 9  # the hole is still exactly one source pixel

    dot = indexed(
        ".....",
        "..o..",
        ".....",
    )
    out = epx_aa(dot, 3)
    assert set(out.pixels) <= set(dot.pixels)
    assert out.pixels.count(3) == 9  # a 1-px detail stays exactly one source pixel


def test_epx_aa_blends_the_corner_towards_the_neighbour_in_rgb565() -> None:
    source = rgb565(
        "kkw",
        "kww",
        "www",
    )
    out = epx_aa(source, 2)
    corner = out.at(2, 2)  # NW sub-pixel of the centre pixel
    assert corner != COLOURS["w"] and corner != COLOURS["k"]
    red, green, blue = unpack_rgb565(corner)
    assert 0 < red < 31 and 0 < green < 63 and 0 < blue < 31
    # 50 % of black into white, in 5/6/5 units.
    assert (red, green, blue) == (16, 32, 16)


def test_epx_aa_never_mixes_more_than_half_of_the_neighbour_in() -> None:
    """Coverage is capped at 1/2, so a two-colour edge cannot wash out."""
    source = rgb565(
        "kkkw",
        "kkww",
        "kwww",
        "wwww",
    )
    out = epx_aa(source, 4)
    black = unpack_rgb565(COLOURS["k"])
    white = unpack_rgb565(COLOURS["w"])
    for y in range(out.height):
        for x in range(out.width):
            own = source.at(x // 4, y // 4)
            other = COLOURS["w"] if own == COLOURS["k"] else COLOURS["k"]
            own_channels = unpack_rgb565(own)
            other_channels = unpack_rgb565(other)
            got = unpack_rgb565(out.at(x, y))
            for channel in range(3):
                distance = abs(other_channels[channel] - own_channels[channel])
                assert abs(got[channel] - own_channels[channel]) <= (
                    distance + 1
                ) // 2, "more than half the neighbour was mixed in"
    # The cap is reached, not just respected: a corner is an exact 50 % mix.
    halved = pack_rgb565(16, 32, 16)
    assert halved in out.pixels


def test_epx_aa_only_mixes_colours_from_the_three_by_three_neighbourhood() -> None:
    """Every output channel is a convex combination of the 3x3 window."""
    source = rgb565(
        "kkkkk",
        "kwwwk",
        "kwgwk",
        "kwwwk",
        "kkkkk",
    )
    out = epx_aa(source, 3)
    for y in range(out.height):
        for x in range(out.width):
            window = [
                unpack_rgb565(source.at(x // 3 + dx, y // 3 + dy))
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
            ]
            got = unpack_rgb565(out.at(x, y))
            for channel in range(3):
                low = min(colour[channel] for colour in window)
                high = max(colour[channel] for colour in window)
                assert low <= got[channel] <= high, (
                    f"({x},{y}) invented a channel value outside its 3x3 window"
                )


def test_epx_aa_indexed_copies_indices_only() -> None:
    source = indexed(
        "..o..",
        ".ooo.",
        "ooooo",
        ".ooo.",
        "..o..",
    )
    out = epx_aa(source, 3)
    assert set(out.pixels) <= set(source.pixels)


def test_epx_aa_indexed_never_paints_the_transparent_key() -> None:
    """A corner whose outside colour is index 0 must stay opaque.

    Index 0 is the game's transparent key; painting it into a sprite corner
    would bite a hole out of the edge instead of smoothing it. The same fixture
    with the key moved away must paint, so the guard is what stopped it.
    """
    sprite = indexed(
        "..o",
        ".oo",
        "ooo",
    )
    guarded = epx_aa(sprite, 2, transparent_index=1)
    assert guarded.at(2, 2) == 3  # background is the key: not painted

    unguarded = epx_aa(sprite, 2, transparent_index=4)
    assert unguarded.at(2, 2) == 1  # same corner, opaque outside: painted


# --------------------------------------------------------------------------
# Image and colour words
# --------------------------------------------------------------------------


def test_rgb565_words_round_trip() -> None:
    for red, green, blue in ((0, 0, 0), (31, 63, 31), (17, 32, 5)):
        assert unpack_rgb565(pack_rgb565(red, green, blue)) == (red, green, blue)
    assert pack_rgb565(31, 0, 0) == 0xF800  # pure red, as the hardware packs it


@pytest.mark.parametrize(
    "channels",
    [(32, 0, 0), (0, 64, 0), (0, 0, 32), (-1, 0, 0)],
)
def test_pack_rgb565_rejects_out_of_range_channels(
    channels: tuple[int, int, int],
) -> None:
    with pytest.raises(ValueError, match="out of range"):
        pack_rgb565(*channels)


def test_image_validates_size_length_and_value_range() -> None:
    with pytest.raises(ValueError, match="positive size"):
        Image(Mode.INDEXED8, 0, 4, ())
    with pytest.raises(ValueError, match="needs 4 pixels"):
        Image(Mode.INDEXED8, 2, 2, (1, 2, 3))
    with pytest.raises(ValueError, match="out of range"):
        Image(Mode.INDEXED8, 2, 1, (1, 256))
    with pytest.raises(ValueError, match="out of range"):
        Image(Mode.RGB565, 2, 1, (0, 0x10000))


def test_rgb565_surface_bytes_round_trip() -> None:
    data = struct.pack("<4H", 0xF800, 0x07E0, 0x001F, 0xFFFF)
    image = Image.from_rgb565_le(2, 2, data)
    assert image.pixels == (0xF800, 0x07E0, 0x001F, 0xFFFF)
    assert image.to_rgb565_le() == data
    with pytest.raises(ValueError, match="expected 8 bytes"):
        Image.from_rgb565_le(2, 2, data[:-1])
    with pytest.raises(ValueError, match="only an RGB565 buffer"):
        Image(Mode.INDEXED8, 2, 2, (0, 0, 0, 0)).to_rgb565_le()


def test_image_constructors_build_filled_and_indexed_buffers() -> None:
    filled = Image.new(Mode.RGB565, 3, 2, 0x07E0)
    assert (filled.width, filled.height, set(filled.pixels)) == (3, 2, {0x07E0})
    indexed_image = Image.from_indexed(2, 2, b"\x00\x01\x02\x03")
    assert indexed_image.pixels == (0, 1, 2, 3)
    with pytest.raises(ValueError, match="expected 4 index bytes"):
        Image.from_indexed(2, 2, b"\x00\x01")


def test_image_at_clamps_to_the_border() -> None:
    image = indexed(".o", "o.")
    assert image.at(-5, -5) == image.at(0, 0)
    assert image.at(99, 99) == image.at(1, 1)


# --------------------------------------------------------------------------
# fit and pad geometry
# --------------------------------------------------------------------------


def test_fit_picks_the_largest_integer_scale_that_fits() -> None:
    fit = fit_scale(320, 240, 1920, 1080)
    assert (fit.scale, fit.content_width, fit.content_height) == (4, 1280, 960)
    assert (fit.offset_x, fit.offset_y) == (320, 60)
    assert (fit.pad_left, fit.pad_right) == (320, 320)
    assert (fit.pad_top, fit.pad_bottom) == (60, 60)
    assert fit.pillarbox and fit.letterbox


def test_fit_at_an_exact_multiple_leaves_no_pads() -> None:
    fit = fit_scale(320, 240, 1920, 1440)
    assert fit.scale == 6
    assert (fit.pad_left, fit.pad_right, fit.pad_top, fit.pad_bottom) == (0, 0, 0, 0)
    assert not fit.pillarbox and not fit.letterbox


def test_fit_never_stretches_one_axis_more_than_the_other() -> None:
    surfaces = ((1366, 768), (1920, 1080), (2560, 1440), (3840, 2160), (800, 600))
    for width, height in surfaces:
        for source in ((320, 240), (432, 240), (320, 200)):
            fit = fit_scale(*source, width, height)
            assert fit.content_width * source[1] == fit.content_height * source[0]
            assert fit.content_width <= width and fit.content_height <= height
            # One more step up in either axis would not fit.
            assert (
                fit.content_width + source[0] > width
                or fit.content_height + source[1] > height
            )


def test_fit_puts_the_odd_pad_pixel_on_the_right_and_bottom() -> None:
    fit = fit_scale(5, 3, 11, 7)
    assert fit.scale == 2
    assert (fit.offset_x, fit.pad_right, fit.offset_y, fit.pad_bottom) == (0, 1, 0, 1)


def test_fit_honours_a_maximum_scale() -> None:
    fit = fit_scale(320, 240, 3840, 2160, max_scale=3)
    assert (fit.scale, fit.content_width, fit.content_height) == (3, 960, 720)
    assert fit.pad_left == (3840 - 960) // 2


def test_fit_refuses_to_pretend_a_fractional_scale_fits() -> None:
    with pytest.raises(ValueError, match="does not fit"):
        fit_scale(320, 240, 300, 200)


@pytest.mark.parametrize(
    "arguments",
    [(0, 240, 1920, 1080), (320, 240, 0, 1080), (320.5, 240, 1920, 1080)],
)
def test_fit_validates_its_geometry(arguments: tuple[object, ...]) -> None:
    with pytest.raises(ValueError, match="positive int"):
        fit_scale(*arguments)  # type: ignore[arg-type]


def test_fit_compares_against_the_documented_display_maths() -> None:
    """Cross-check the number quoted in docs/research/02-resolution.md §2.3.

    4:3 content at 1080p is exactly 4.5x, so the largest integer scale is 4 and
    the frame is pillarboxed to 1280x960 — the shimmer-free choice.
    """
    fit = fit_scale(320, 240, 1920, 1080)
    assert fit.scale == 4
    assert fit.content_width < 1440  # the non-integer 4.5x width
    wide = fit_scale(432, 240, 1920, 1080)
    assert wide.scale == 4 and wide.content_width == 1728


# --------------------------------------------------------------------------
# present
# --------------------------------------------------------------------------


def test_present_centres_the_content_and_fills_the_pads() -> None:
    source = Image(Mode.INDEXED8, 4, 4, (3,) * 16)
    result = present(source, 10, 10, pad_value=1)
    assert result.surface.mode is Mode.INDEXED8
    assert (result.surface.width, result.surface.height) == (10, 10)
    assert result.fit.scale == 2
    assert (result.fit.offset_x, result.fit.offset_y) == (1, 1)
    for y in range(10):
        for x in range(10):
            inside = 1 <= x < 9 and 1 <= y < 9
            assert result.surface.at(x, y) == (3 if inside else 1)


def test_present_at_an_exact_multiple_is_just_the_scaled_frame() -> None:
    source = rgb565("kw", "wk")
    result = present(source, 8, 8)
    assert result.surface == nearest(source, 4)
    assert not result.fit.pillarbox and not result.fit.letterbox


def test_present_uses_the_selected_filter() -> None:
    source = rgb565(
        "kkw",
        "kww",
        "www",
    )
    filtered = present(source, 6, 6, filter="epx-aa")
    assert filtered.surface == epx_aa(source, 2)
    plain = present(source, 6, 6)
    assert plain.surface == nearest(source, 2)
    assert filtered.surface != plain.surface


def test_present_caps_the_scale_and_pads_the_rest() -> None:
    result = present(Image(Mode.INDEXED8, 4, 4, tuple([2] * 16)), 32, 32, max_scale=3)
    assert result.fit.scale == 3
    assert (result.scaled.width, result.scaled.height) == (12, 12)
    assert (result.fit.pad_left, result.fit.pad_right) == (10, 10)


def test_present_rejects_an_out_of_range_pad_colour() -> None:
    source = Image(Mode.INDEXED8, 2, 2, (1, 1, 1, 1))
    with pytest.raises(ValueError, match="pad_value 300 out of range"):
        present(source, 4, 4, pad_value=300)


def test_present_returns_a_buffer_with_the_documented_default_pad() -> None:
    source = Image(Mode.RGB565, 5, 5, (0xFFFF,) * 25)
    result = present(source, 12, 12)
    assert result.fit.scale == 2
    assert (result.fit.offset_x, result.fit.offset_y) == (1, 1)
    assert result.surface.at(0, 0) == 0  # black pad
    assert result.surface.at(1, 1) == 0xFFFF  # content starts at the offset


# --------------------------------------------------------------------------
# the side-by-side demo
# --------------------------------------------------------------------------


def load_demo():
    spec = importlib.util.spec_from_file_location("scale_demo", DEMO)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_draws_two_different_panels_of_the_same_size() -> None:
    demo = load_demo()
    sprite = demo.synthetic_sprite()
    assert (sprite.width, sprite.height) == (16, 16)
    plain, filtered = demo.ascii_panels(sprite, 4)
    assert len(plain) == len(filtered) == 64
    assert all(len(line) == 64 for line in plain + filtered)
    assert plain != filtered, "the filter must be visible at 4x"


def test_demo_ascii_rounds_diagonals_and_keeps_one_pixel_detail() -> None:
    demo = load_demo()
    sprite = demo.synthetic_sprite()
    plain, filtered = demo.ascii_panels(sprite, 4)
    # Indexed mode repaints indices only: the filter invents no glyph.
    assert set("".join(filtered)) <= set("".join(plain))

    def block(lines: list[str], x: int, y: int) -> str:
        return "".join(lines[y * 4 + j][x * 4 : x * 4 + 4] for j in range(4))

    changed = [
        (x, y)
        for y in range(sprite.height)
        for x in range(sprite.width)
        if block(plain, x, y) != block(filtered, x, y)
    ]
    assert len(changed) >= 20, "the gem's diagonals must visibly round off"

    # The 1-px notch is untouched and the 1-px line keeps every step.
    assert block(filtered, 8, 7) == "." * 16
    for step in range(4):
        assert "o" in block(filtered, 11 + step, 1 + step)


def decode_png(path: Path) -> tuple[int, int, list[bytes]]:
    """Minimal PNG reader for the truecolour, filter-0 images this repo writes."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    width = height = 0
    idat = b""
    while offset < len(data):
        (length,) = struct.unpack(">I", data[offset : offset + 4])
        tag = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        (crc,) = struct.unpack(">I", data[offset + 8 + length : offset + 12 + length])
        assert crc == zlib.crc32(tag + payload) & 0xFFFFFFFF, f"bad CRC in {tag!r}"
        if tag == b"IHDR":
            width, height, depth, colour_type = struct.unpack(">IIBB", payload[:10])
            assert (depth, colour_type) == (8, 2)
        elif tag == b"IDAT":
            idat += payload
        offset += 12 + length
    raw = zlib.decompress(idat)
    stride = 1 + width * 3
    rows = [raw[y * stride : (y + 1) * stride] for y in range(height)]
    assert all(row[0] == 0 for row in rows), "demo writes unfiltered rows only"
    return width, height, [row[1:] for row in rows]


def test_demo_writes_a_png_and_the_filtered_panel_differs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    demo = load_demo()
    target = tmp_path / "side_by_side.png"
    assert demo.main(["--scale", "4", "--png", str(target)]) == 0
    printed = capsys.readouterr().out
    assert "nearest 4x" in printed and "epx-aa 4x" in printed
    assert target.is_file()

    width, height, rows = decode_png(target)
    sprite = demo.synthetic_sprite()
    panel = sprite.width * 4
    assert (width, height) == (panel * 2 + 8, panel)
    left = [row[: panel * 3] for row in rows]
    right = [row[(panel + 8) * 3 :] for row in rows]
    assert left != right, "the two panels must differ pixel for pixel"

    def colours(panel: list[bytes]) -> set[tuple[int, int, int]]:
        return {
            (row[index], row[index + 1], row[index + 2])
            for row in panel
            for index in range(0, len(row), 3)
        }

    # The filtered panel is anti-aliased: strictly more distinct colours.
    assert len(colours(right)) > len(colours(left))
