"""Tests for :func:`lomax_modern.png.decode` -- the reader the GIF command needs.

Synthetic images only.  The writer always emits filter type 0 RGBA, so the
reader's filter/colour-type coverage is exercised with hand-built PNGs here:
that is the shape a frame re-saved by another tool would arrive in, and a
reader that only handled its own output would fail confusingly on it.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from lomax_modern import png


def pixels(width: int, height: int) -> bytes:
    out = bytearray()
    for y in range(height):
        for x in range(width):
            out += bytes(
                (
                    (x * 13 + y * 7) % 256,
                    (x * 3 + y * 29) % 256,
                    (x * 17 + y * 5) % 256,
                    255,
                )
            )
    return bytes(out)


def chunk(kind: bytes, body: bytes) -> bytes:
    return (
        struct.pack(">I", len(body))
        + kind
        + body
        + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    )


def build(
    width: int,
    height: int,
    rgba: bytes,
    *,
    colour_type: int = png.COLOUR_TYPE_RGBA,
    filter_type: int = 0,
    interlace: int = 0,
    depth: int = 8,
) -> bytes:
    """Assemble a PNG by hand so every filter/colour-type path can be tested."""
    channels = 4 if colour_type == png.COLOUR_TYPE_RGBA else 3
    stride = width * channels
    raw = bytearray()
    previous = bytes(stride)
    for row in range(height):
        line = bytearray(rgba[row * stride : (row + 1) * stride])
        raw.append(filter_type)
        if filter_type == 0:
            raw += line
        elif filter_type == 1:  # Sub
            encoded = bytearray(line)
            for index in range(stride - 1, channels - 1, -1):
                encoded[index] = (line[index] - line[index - channels]) & 0xFF
            raw += encoded
        elif filter_type == 2:  # Up
            raw += bytes((line[index] - previous[index]) & 0xFF for index in range(stride))
        elif filter_type == 3:  # Average
            encoded = bytearray(stride)
            for index in range(stride):
                left = line[index - channels] if index >= channels else 0
                encoded[index] = (line[index] - ((left + previous[index]) >> 1)) & 0xFF
            raw += encoded
        elif filter_type == 4:  # Paeth
            encoded = bytearray(stride)
            for index in range(stride):
                left = line[index - channels] if index >= channels else 0
                upper_left = previous[index - channels] if index >= channels else 0
                encoded[index] = (
                    line[index] - png._paeth(left, previous[index], upper_left)
                ) & 0xFF
            raw += encoded
        else:  # pragma: no cover - the test matrix never asks for this
            raise AssertionError(filter_type)
        previous = line
    header = struct.pack(
        ">IIBBBBB", width, height, depth, colour_type, 0, 0, interlace
    )
    return b"".join(
        (
            png.SIGNATURE,
            chunk(b"IHDR", header),
            chunk(b"IDAT", zlib.compress(bytes(raw))),
            chunk(b"IEND", b""),
        )
    )


def test_round_trip_of_our_own_writer(tmp_path: Path) -> None:
    width, height = 7, 5
    raw = pixels(width, height)
    path = tmp_path / "frame.png"
    png.write(path, width, height, raw)
    decoded_width, decoded_height, decoded = png.read(path)
    assert (decoded_width, decoded_height) == (width, height)
    assert decoded == raw


@pytest.mark.parametrize("filter_type", [0, 1, 2, 3, 4])
def test_every_scanline_filter_is_reversed(filter_type: int) -> None:
    width, height = 6, 5
    raw = pixels(width, height)
    decoded = png.decode(build(width, height, raw, filter_type=filter_type))
    assert decoded == (width, height, raw)


def test_rgb_image_is_expanded_to_opaque_rgba() -> None:
    width, height = 4, 3
    rgb = bytearray()
    for index in range(width * height):
        rgb += bytes((index, index * 2 % 256, index * 3 % 256))
    decoded_width, decoded_height, decoded = png.decode(
        build(width, height, bytes(rgb), colour_type=png.COLOUR_TYPE_RGB)
    )
    assert (decoded_width, decoded_height) == (width, height)
    expected = bytearray()
    for index in range(width * height):
        expected += bytes((rgb[index * 3], rgb[index * 3 + 1], rgb[index * 3 + 2], 255))
    assert decoded == bytes(expected)


def test_bad_signature_is_refused() -> None:
    with pytest.raises(png.PNGError, match="not a PNG"):
        png.decode(b"GIF89a and some other bytes")


def test_truncated_file_is_refused() -> None:
    data = build(2, 2, pixels(2, 2))
    with pytest.raises(png.PNGError, match="truncated"):
        png.decode(data[:-10])


def test_corrupt_chunk_crc_is_refused() -> None:
    data = bytearray(build(2, 2, pixels(2, 2)))
    # Flip a byte inside the IDAT payload: the CRC no longer matches.
    position = data.index(b"IDAT") + 6
    data[position] ^= 0xFF
    with pytest.raises(png.PNGError, match="CRC mismatch"):
        png.decode(bytes(data))


def test_interlaced_image_is_refused() -> None:
    with pytest.raises(png.PNGError, match="interlaced"):
        png.decode(build(2, 2, pixels(2, 2), interlace=1))


def test_sixteen_bit_image_is_refused() -> None:
    with pytest.raises(png.PNGError, match="8-bit"):
        png.decode(build(2, 2, pixels(2, 2), depth=16))


def test_palettised_image_is_refused_with_the_typename() -> None:
    with pytest.raises(png.PNGError, match="colour types"):
        png.decode(build(2, 2, pixels(2, 2), colour_type=3))


def test_short_pixel_buffer_is_refused() -> None:
    with pytest.raises(png.PNGError, match="pixel buffer"):
        png.encode(4, 4, bytes(10))
