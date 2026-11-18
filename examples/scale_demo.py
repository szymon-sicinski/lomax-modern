#!/usr/bin/env python3
"""Side-by-side demonstration of the presenter's two filters, on synthetic art.

No game files: the 16x16 sprite below is generated in code, so this is
committable and reproducible.  Two views of the same buffer at the same integer
factor:

* **ASCII** — indexed mode, where the filter can only repaint a corner index, so
  the *geometry* change (rounded stair steps, untouched 1-px lines) is what you
  see.  Legible in a terminal and in a diff.
* **PNG** (`--png PATH`) — ``B5G6R5`` mode, where a fired corner is blended, so
  the *anti-aliasing* is visible.  Written with ``zlib`` only; no Pillow.

Run::

    python examples/scale_demo.py
    python examples/scale_demo.py --scale 6 --png scale_demo.png
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lomax_modern.scaler import (  # noqa: E402
    Image,
    Mode,
    epx_aa,
    nearest,
    unpack_rgb565,
)

#: Palette: index -> ASCII glyph and the ``B5G6R5`` colour used for the PNG.
PALETTE: dict[int, tuple[str, int]] = {
    1: (".", 0x0000),  # background, black
    2: ("#", 0xFFFF),  # one-pixel outline, white
    3: ("o", 0x07E0),  # body, green
    4: ("@", 0xFFE0),  # highlight, yellow
}

#: Gutter colour between the two PNG panels.
GUTTER = 0xF81F

BACKGROUND = 1
OUTLINE = 2
BODY = 3
HIGHLIGHT = 4


def synthetic_sprite(size: int = 16) -> Image:
    """A 16x16 diamond with a 1-px outline, a highlight, a notch and a 1-px line.

    Each feature exists to exercise one branch of the filter: the diamond gives
    stair steps on its diagonals, the notch is a one-pixel concave corner, and
    the 1-px diagonal line in the top-right corner has background on both
    orthogonal sides at every step, so a filter that fills it in is smearing.
    """
    if size < 10:
        raise ValueError("the demo sprite needs at least 10x10 pixels")
    pixels = [BACKGROUND] * (size * size)
    centre = (size - 1) / 2
    radius = size // 2 - 1

    def put(x: int, y: int, value: int) -> None:
        if 0 <= x < size and 0 <= y < size:
            pixels[y * size + x] = value

    for y in range(size):
        for x in range(size):
            distance = abs(x - centre) + abs(y - centre)
            if distance <= radius - 1:
                put(x, y, BODY)
            elif distance <= radius:
                put(x, y, OUTLINE)
    # Highlight: upper-left inner quadrant of the gem.
    for y in range(size):
        for x in range(size):
            if pixels[y * size + x] == BODY and x < centre and y < centre:
                put(x, y, HIGHLIGHT)
    # One-pixel notch inside the body: EPX cannot tell a hole in a surface from
    # background, so it must be left alone rather than eaten away.
    put(int(centre) + 1, int(centre), BACKGROUND)
    # One-pixel diagonal line in the empty top-right quadrant: every step has
    # background on both orthogonal sides. EPX rounds such a step's outside
    # corner (the line gets slightly heavier); it must never erase it.
    for step in range(4):
        put(size - 5 + step, 1 + step, BODY)
    return Image(Mode.INDEXED8, size, size, tuple(pixels))


def with_palette(image: Image) -> Image:
    """Map an indexed sprite to ``B5G6R5`` through :data:`PALETTE`."""
    return Image(
        Mode.RGB565,
        image.width,
        image.height,
        tuple(PALETTE[index][1] for index in image.pixels),
    )


def to_text(image: Image) -> list[str]:
    """One line per pixel row, one glyph per index."""
    glyph = {index: entry[0] for index, entry in PALETTE.items()}
    unknown = sorted(set(image.pixels) - set(glyph))
    if unknown:
        raise ValueError(f"no glyph for palette index {unknown[0]}")
    rows = []
    for y in range(image.height):
        start = y * image.width
        values = image.pixels[start : start + image.width]
        rows.append("".join(glyph[value] for value in values))
    return rows


def ascii_panels(sprite: Image, factor: int) -> tuple[list[str], list[str]]:
    """The nearest and filtered panels as text, at the same factor."""
    return to_text(nearest(sprite, factor)), to_text(epx_aa(sprite, factor))


def side_by_side(left: list[str], right: list[str], gutter: str = "   ") -> list[str]:
    return [a + gutter + b for a, b in zip(left, right)]


def _rgb8(value: int) -> tuple[int, int, int]:
    red, green, blue = unpack_rgb565(value)
    return (red * 255 + 15) // 31, (green * 255 + 31) // 63, (blue * 255 + 15) // 31


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def write_png(path: Path, image: Image) -> None:
    """Write an ``RGB565`` image as an 8-bit RGB PNG (truecolour, filter 0)."""
    if image.mode is not Mode.RGB565:
        raise ValueError("PNG output needs an RGB565 image")
    rows = []
    for y in range(image.height):
        row = bytes(
            channel
            for value in image.pixels[y * image.width : (y + 1) * image.width]
            for channel in _rgb8(value)
        )
        rows.append(b"\x00" + row)
    header = struct.pack(">IIBBBBB", image.width, image.height, 8, 2, 0, 0, 0)
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + _chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def png_panels(sprite: Image, factor: int, gutter: int = 8) -> Image:
    """Two filtered panels side by side in ``B5G6R5``, separated by a gutter."""
    rgb = with_palette(sprite)
    panels = (nearest(rgb, factor), epx_aa(rgb, factor))
    width = panels[0].width * 2 + gutter
    height = panels[0].height
    pixels = [GUTTER] * (width * height)
    for panel_index, panel in enumerate(panels):
        offset = panel_index * (panel.width + gutter)
        for y in range(height):
            start = y * width + offset
            pixels[start : start + panel.width] = panel.pixels[
                y * panel.width : (y + 1) * panel.width
            ]
    return Image(Mode.RGB565, width, height, tuple(pixels))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--scale",
        type=int,
        default=4,
        help="integer factor for both panels (default 4)",
    )
    parser.add_argument("--png", type=Path, help="also write a side-by-side PNG here")
    args = parser.parse_args(argv)

    sprite = synthetic_sprite()
    nearest_rows, filtered_rows = ascii_panels(sprite, args.scale)
    title_left = f"nearest {args.scale}x"
    title_right = f"epx-aa {args.scale}x"
    panel_width = len(nearest_rows[0])
    print(f"synthetic 16x16 sprite, indexed mode, factor {args.scale}")
    print(f"{title_left:<{panel_width}}   {title_right}")
    print("-" * (panel_width * 2 + 3))
    for line in side_by_side(nearest_rows, filtered_rows):
        print(line)
    print()
    print("legend: . background  # outline  o body  @ highlight")
    print(
        "the gem's diagonals round off, one stair step per corner; the 1-px "
        "notch and the 1-px line keep their shape, because EPX cannot tell a "
        "hole from background and erasing detail is worse than a sharp corner"
    )

    if args.png:
        write_png(args.png, png_panels(sprite, args.scale))
        print(f"\nwrote {args.png} ({args.scale}x, RGB565, anti-aliasing visible)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
