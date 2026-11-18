"""Minimal PNG writer (8-bit RGBA), standard library only.

The repository is deliberately dependency-free (see ``docs/development.md``), so
this module implements the small subset of PNG that an art exporter needs:
non-interlaced 8-bit RGBA, one ``IDAT`` chunk, filter type 0 on every row.
That is enough for a sprite sheet, and it is trivially checkable with any
viewer.

Only the *encoder* lives here.  Nothing in this module reads game data; the
caller passes finished RGBA bytes.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

#: The 8-byte PNG file signature.
SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: PNG colour type 6 = truecolour with alpha.
COLOUR_TYPE_RGBA = 6

#: Bytes per pixel for the only pixel format this module writes.
BYTES_PER_PIXEL = 4


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
