"""Minimal PNG codec (8-bit RGBA/RGB), standard library only.

The repository is deliberately dependency-free (see ``docs/development.md``), so
this module implements the small subset of PNG that this pipeline needs:
non-interlaced 8-bit truecolour, one ``IDAT`` chunk, filter type 0 on every row
when writing.  That is enough for a sprite sheet, and it is trivially checkable
with any viewer.

The :func:`decode` reader exists for one caller: ``lomax-modern gif`` reads back
the frame sequence the ``--frames`` exporter wrote.  It accepts what
:func:`encode` produces plus the common 8-bit RGB variant, and refuses
palettised, 16-bit or interlaced input with the reason rather than guessing.

Nothing in this module reads game data; the caller passes finished RGBA bytes.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

#: The 8-byte PNG file signature.
SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: PNG colour type 6 = truecolour with alpha.
COLOUR_TYPE_RGBA = 6

#: PNG colour type 2 = truecolour (no alpha).
COLOUR_TYPE_RGB = 2

#: Bytes per pixel for the only pixel format this module writes.
BYTES_PER_PIXEL = 4

#: Channel counts for the colour types :func:`decode` accepts.
_CHANNELS = {COLOUR_TYPE_RGBA: 4, COLOUR_TYPE_RGB: 3}


class PNGError(ValueError):
    """The image cannot be encoded as a PNG with this module."""


def _chunk(kind: bytes, data: bytes) -> bytes:
    """Frame ``data`` as a PNG chunk: length, type, payload, CRC."""
    if len(kind) != 4:
        raise PNGError(f"chunk type must be 4 bytes, got {len(kind)}")
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def encode(
    width: int,
    height: int,
    pixels: bytes,
    *,
    compression_level: int = 9,
) -> bytes:
    """Encode ``pixels`` (row-major RGBA8888) as a PNG byte string.

    ``pixels`` must hold exactly ``width * height * 4`` bytes.  Raises
    :class:`PNGError` on any other size, so a mis-sized buffer can never be
    written as a plausible-looking but shifted image.
    """
    if not isinstance(width, int) or not isinstance(height, int):
        raise PNGError("width and height must be ints")
    if width <= 0 or height <= 0:
        raise PNGError(f"width and height must be positive, got {width}x{height}")
    expected = width * height * BYTES_PER_PIXEL
    if len(pixels) != expected:
        raise PNGError(
            f"pixel buffer is {len(pixels)} bytes, expected {expected} "
            f"for {width}x{height} RGBA"
        )
    if not 0 <= compression_level <= 9:
        raise PNGError(f"compression level must be 0..9, got {compression_level}")

    stride = width * BYTES_PER_PIXEL
    view = memoryview(pixels)
    # Filter type 0 (None) on every scanline: portability over size.  The
    # sheets are flat-colour art and zlib already does the work.
    filtered = b"".join(
        b"\x00" + bytes(view[row * stride : (row + 1) * stride])
        for row in range(height)
    )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, COLOUR_TYPE_RGBA, 0, 0, 0)
    return b"".join(
        (
            SIGNATURE,
            _chunk(b"IHDR", ihdr),
            _chunk(b"IDAT", zlib.compress(filtered, compression_level)),
            _chunk(b"IEND", b""),
        )
    )


def write(
    path: str | Path,
    width: int,
    height: int,
    pixels: bytes,
    *,
    compression_level: int = 9,
) -> Path:
    """Encode and write ``path``; returns the path written.

    The caller owns the destination.  This module never decides to write into a
    game folder.
    """
    data = encode(width, height, pixels, compression_level=compression_level)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def _paeth(left: int, above: int, upper_left: int) -> int:
    """PNG's Paeth predictor (filter type 4)."""
    estimate = left + above - upper_left
    distance_left = abs(estimate - left)
    distance_above = abs(estimate - above)
    distance_upper_left = abs(estimate - upper_left)
    if distance_left <= distance_above and distance_left <= distance_upper_left:
        return left
    if distance_above <= distance_upper_left:
        return above
    return upper_left


def _unfilter(raw: bytes, width: int, height: int, channels: int) -> bytes:
    """Reverse the per-scanline PNG filters into raw pixel rows."""
    stride = width * channels
    expected = (stride + 1) * height
    if len(raw) != expected:
        raise PNGError(
            f"image data is {len(raw)} bytes, expected {expected} for "
            f"{width}x{height} with {channels} channels"
        )
    rows = bytearray(stride * height)
    previous = bytes(stride)
    position = 0
    for row in range(height):
        filter_type = raw[position]
        start = position + 1
        line = bytearray(raw[start : start + stride])
        position = start + stride
        if filter_type == 0:
            pass
        elif filter_type == 1:
            for index in range(channels, stride):
                line[index] = (line[index] + line[index - channels]) & 0xFF
        elif filter_type == 2:
            for index in range(stride):
                line[index] = (line[index] + previous[index]) & 0xFF
        elif filter_type == 3:
            for index in range(stride):
                left = line[index - channels] if index >= channels else 0
                line[index] = (line[index] + ((left + previous[index]) >> 1)) & 0xFF
        elif filter_type == 4:
            for index in range(stride):
                left = line[index - channels] if index >= channels else 0
                upper_left = previous[index - channels] if index >= channels else 0
                line[index] = (
                    line[index] + _paeth(left, previous[index], upper_left)
                ) & 0xFF
        else:
            raise PNGError(f"unknown PNG filter type {filter_type} on row {row}")
        rows[row * stride : (row + 1) * stride] = line
        previous = line
    return bytes(rows)


def decode(data: bytes) -> tuple[int, int, bytes]:
    """Decode a PNG into ``(width, height, RGBA8888 pixels)``.

    Accepts non-interlaced 8-bit RGBA or RGB with any of the five scanline
    filters.  Every chunk CRC is verified, so a truncated or corrupted frame
    fails here instead of becoming a plausible-looking shifted image.
    """
    if not data.startswith(SIGNATURE):
        raise PNGError("not a PNG (bad signature)")
    offset = len(SIGNATURE)
    header: tuple[int, int, int] | None = None
    compressed = bytearray()
    while offset < len(data):
        if offset + 8 > len(data):
            raise PNGError("truncated PNG chunk header")
        (length,) = struct.unpack(">I", data[offset : offset + 4])
        kind = data[offset + 4 : offset + 8]
        body_start = offset + 8
        body_end = body_start + length
        if body_end + 4 > len(data):
            raise PNGError(f"truncated {kind!r} chunk")
        body = data[body_start:body_end]
        (crc,) = struct.unpack(">I", data[body_end : body_end + 4])
        if zlib.crc32(kind + body) & 0xFFFFFFFF != crc:
            raise PNGError(f"CRC mismatch in {kind!r} chunk")
        offset = body_end + 4
        if kind == b"IHDR":
            if length != 13:
                raise PNGError(f"IHDR must be 13 bytes, got {length}")
            width, height, depth, colour_type, compression, filter_method, interlace = (
                struct.unpack(">IIBBBBB", body)
            )
            if depth != 8:
                raise PNGError(f"only 8-bit PNGs are supported, got {depth}-bit")
            if colour_type not in _CHANNELS:
                raise PNGError(
                    f"only RGBA (6) and RGB (2) colour types are supported, got "
                    f"{colour_type}"
                )
            if compression != 0 or filter_method != 0:
                raise PNGError(
                    f"unsupported PNG compression/filter method {compression}/"
                    f"{filter_method}"
                )
            if interlace != 0:
                raise PNGError("interlaced PNGs are not supported")
            if width <= 0 or height <= 0:
                raise PNGError(f"width and height must be positive, got {width}x{height}")
            header = (width, height, colour_type)
        elif kind == b"IDAT":
            compressed += body
        elif kind == b"IEND":
            break
    if header is None:
        raise PNGError("no IHDR chunk")
    if not compressed:
        raise PNGError("no IDAT chunk")
    width, height, colour_type = header
    channels = _CHANNELS[colour_type]
    try:
        raw = zlib.decompress(bytes(compressed))
    except zlib.error as exc:
        raise PNGError(f"cannot decompress image data: {exc}") from None
    rows = _unfilter(raw, width, height, channels)
    if colour_type == COLOUR_TYPE_RGBA:
        return width, height, rows
    out = bytearray(width * height * BYTES_PER_PIXEL)
    for position in range(width * height):
        source = position * 3
        target = position * 4
        out[target : target + 3] = rows[source : source + 3]
        out[target + 3] = 255
    return width, height, bytes(out)


def read(path: str | Path) -> tuple[int, int, bytes]:
    """Read ``path`` and decode it as :func:`decode` does."""
    target = Path(path)
    return decode(target.read_bytes())
