"""Integer scalers and a pixel-art filter for the presenter's framebuffer.

The presenter (M4) owns a 16-bit ``B5G6R5`` frame and has to put it on a modern
display at an **integer** scale with the source aspect preserved.  This module
is the pure part of that layer: buffer geometry, padding and filters.  No
window, no I/O, no game data, no third-party code, no compiler.

It is a **reference implementation and test oracle**, not the shipping hot
path: the presenter itself is C (``native/``, see ``docs/architecture.md``
§5), and it is expected to reproduce these results bit-for-bit.  The pure
Python path is what unit tests grade, so the rules are stated here in code and
proven on synthetic buffers.  Cost is the reason: on CPython 3.14 a 320x240
frame takes about 40 ms for ``nearest`` at 4x and 150 ms for ``epx_aa`` — fine
for an oracle, hopeless for 60 Hz.

Two filters
-----------

``nearest``
    Exact block replication: every output pixel equals the source pixel it came
    from, so no colour outside the source frame is ever invented and the frame
    is recoverable by sampling.

``epx_aa``
    Edge-directed pixel-art filter in the Scale2x/EPX — xBR family.  For every
    source pixel and each of its four block corners it applies the EPX corner
    test and, when it fires, paints the corner region with the outside colour:
    fractional coverage in ``B5G6R5`` (so stair steps get anti-aliased instead
    of looking blocky) and an integer **index copy** in indexed mode, because a
    palette index cannot be averaged.

    EPX corner test, for corner direction ``(dx, dy)`` with orthogonal
    neighbours ``o_h = (dx, 0)`` and ``o_v = (0, dy)`` and their opposites
    ``o_h' = (-dx, 0)``, ``o_v' = (0, -dy)``::

        o_h == o_v  and  o_h != p  and  o_h != o_v'  and  o_v != o_h'

    The last two clauses are what keep the filter honest, and they are the
    reason it is not a smear:

    * a two-colour checkerboard is left completely untouched (every corner has
      an opposite neighbour of the matching colour), so 1-px dither art stays
      crisp instead of collapsing into grey;
    * a genuine one-pixel stair step fires on exactly one corner and gets
      rounded; a one-pixel diagonal line keeps every one of its pixels and
      gains a rounded outside corner, which is EPX's documented behaviour —
      such a line gets slightly heavier, it is never erased or blurred away;
    * the outermost one-pixel ring is replicated unfiltered, because an edge
      direction cannot be read at the frame border without inventing
      neighbours (clamping there manufactures corners).

    Blending is capped at 50 % coverage, so a filtered pixel is always at least
    as close to its own source colour as to the colour blended into it.  The
    filter only ever samples the 3x3 neighbourhood of a pixel, so it cannot
    pull colour across the frame.

Confidence
----------

The geometry — integer factors, aspect preservation, pad placement — is
**verified** by ``tests/unit/test_scaler.py``.  The *look* of ``epx_aa`` is a
**design choice, not a measured property** of the game (grade H): the rule set
is the published EPX/Scale2x corner rule, implemented from its description, not
read or ported from any implementation.  xBRZ's reference implementation is
GPL-licensed and this package is MIT, so no xBRZ or MMPX source was consulted;
the xBR-family traits reproduced here are the corner test, edge-only sampling
and contrast preservation.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "Filter",
    "Fit",
    "Image",
    "Mode",
    "Presentation",
    "epx_aa",
    "fit_scale",
    "nearest",
    "pack_rgb565",
    "present",
    "scale",
    "unpack_rgb565",
]


class Mode(str, Enum):
    """Pixel layout of a buffer.

    ``RGB565``    one ``u16`` per pixel, ``B5G6R5`` (5 red, 6 green, 5 blue),
                  the format of the game's 16-bpp DirectDraw frame.
    ``INDEXED8``  one ``u8`` index per pixel into a caller-supplied palette.
                  The game is palettised and index 0 is its transparent key.
    """

    RGB565 = "rgb565"
    INDEXED8 = "indexed8"

    @property
    def limit(self) -> int:
        """Exclusive upper bound of a legal pixel value in this mode."""
        return 0x10000 if self is Mode.RGB565 else 0x100


class Filter(str, Enum):
    """Filter selectable at runtime (the M4 exit criterion)."""

    NEAREST = "nearest"
    EPX_AA = "epx-aa"


#: Corner directions ``(dx, dy)`` in the order NW, NE, SW, SE.
_CORNERS: tuple[tuple[int, int], ...] = ((-1, -1), (1, -1), (-1, 1), (1, 1))

#: Blend cap, expressed as the denominator of the coverage fraction: the most a
#: single corner may contribute to a pixel is 1/2.
_MAX_COVERAGE_DEN = 2


def pack_rgb565(red: int, green: int, blue: int) -> int:
    """Pack 5/6/5 channels into a ``B5G6R5`` word.

    Out-of-range channels raise instead of clipping: a silently clipped colour
    is a bug that survives all the way to the screen.
    """
    if not 0 <= red < 32 or not 0 <= green < 64 or not 0 <= blue < 32:
        raise ValueError(
            f"B5G6R5 channel out of range: r={red} g={green} b={blue}"
        )
    return (red << 11) | (green << 5) | blue


def unpack_rgb565(value: int) -> tuple[int, int, int]:
    """Split a ``B5G6R5`` word into ``(r5, g6, b5)``, the hardware's own units."""
    if not 0 <= value < 0x10000:
        raise ValueError(f"not a 16-bit word: {value}")
    return (value >> 11) & 0x1F, (value >> 5) & 0x3F, value & 0x1F


@dataclass(frozen=True, slots=True)
class Image:
    """A frozen pixel buffer: mode, size and one integer per pixel.

    Values are logical pixels, not a raw memory image: ``RGB565`` holds the
    16-bit word (``B5G6R5``) and ``INDEXED8`` the palette index.  Conversion to
    and from the little-endian bytes a Windows surface holds is explicit
    (:meth:`from_rgb565_le`, :meth:`to_rgb565_le`) so endianness is never
    implied by the byte order of the host.
    """

    mode: Mode
    width: int
    height: int
    pixels: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError(
                f"image must have positive size, got {self.width}x{self.height}"
            )
        expected = self.width * self.height
        if len(self.pixels) != expected:
            raise ValueError(
                f"{self.width}x{self.height} {self.mode.value} needs "
                f"{expected} pixels, got {len(self.pixels)}"
            )
        limit = self.mode.limit
        bad = [value for value in self.pixels if not 0 <= value < limit]
        if bad:
            raise ValueError(
                f"pixel value {bad[0]} out of range for {self.mode.value} "
                f"(0..{limit - 1})"
            )

    # -- construction -----------------------------------------------------

    @classmethod
    def new(cls, mode: Mode, width: int, height: int, value: int = 0) -> "Image":
        """A buffer filled with one value — pads, clear colour, fixtures."""
        return cls(mode, width, height, (value,) * (width * height))

    @classmethod
    def from_indexed(cls, width: int, height: int, data: bytes) -> "Image":
        """One palette index per byte."""
        if len(data) != width * height:
            raise ValueError(
                f"expected {width * height} index bytes, got {len(data)}"
            )
        return cls(Mode.INDEXED8, width, height, tuple(data))

    @classmethod
    def from_rgb565_le(cls, width: int, height: int, data: bytes) -> "Image":
        """Read ``w*h`` little-endian ``u16`` words (a Windows ``B5G6R5`` surface)."""
        count = width * height
        if len(data) != count * 2:
            raise ValueError(f"expected {count * 2} bytes, got {len(data)}")
        return cls(Mode.RGB565, width, height, struct.unpack(f"<{count}H", data))

    def to_rgb565_le(self) -> bytes:
        """Write the frame as little-endian ``u16`` words."""
        if self.mode is not Mode.RGB565:
            raise ValueError("only an RGB565 buffer has 16-bit words")
        return struct.pack(f"<{len(self.pixels)}H", *self.pixels)

    # -- access -----------------------------------------------------------

    def at(self, x: int, y: int) -> int:
        """Pixel with edge clamping (out-of-frame reads replicate the border)."""
        x = 0 if x < 0 else self.width - 1 if x >= self.width else x
        y = 0 if y < 0 else self.height - 1 if y >= self.height else y
        return self.pixels[y * self.width + x]


def _check_factor(factor: int) -> None:
    if isinstance(factor, bool) or not isinstance(factor, int):
        raise TypeError(f"scale factor must be an int, got {type(factor).__name__}")
    if factor < 1:
        raise ValueError(f"integer scale factor must be >= 1, got {factor}")


def nearest(image: Image, factor: int) -> Image:
    """Replicate every pixel into a ``factor x factor`` block.

    This is the reference result: no colour is invented, and the frame can be
    recovered by sampling any corner of each block.
    """
    _check_factor(factor)
    if factor == 1:
        return image
    width, height = image.width, image.height
    out_width = width * factor
    out = [0] * (out_width * height * factor)
    src = image.pixels
    for y in range(height):
        row = [px for px in src[y * width : (y + 1) * width] for _ in range(factor)]
        for j in range(factor):
            start = (y * factor + j) * out_width
            out[start : start + out_width] = row
    return Image(image.mode, out_width, height * factor, tuple(out))


def _blend565(base: int, other: int, numerator: int, denominator: int) -> int:
    """Mix two ``B5G6R5`` words by ``numerator/denominator`` in 5/6/5 units.

    Integer arithmetic only: the same inputs always give the same word, which
    is what lets the C presenter match this oracle exactly.
    """
    br, bg, bb = unpack_rgb565(base)
    orr, og, ob = unpack_rgb565(other)
    keep = denominator - numerator
    half = denominator // 2
    return pack_rgb565(
        (br * keep + orr * numerator + half) // denominator,
        (bg * keep + og * numerator + half) // denominator,
        (bb * keep + ob * numerator + half) // denominator,
    )


def epx_aa(
    image: Image,
    factor: int,
    *,
    transparent_index: int | None = 0,
) -> Image:
    """Edge-directed pixel-art filter: EPX corner test plus fractional AA.

    In ``RGB565`` a fired corner is blended at up to 50 % coverage, graded
    towards the block interior, so diagonal edges get anti-aliased.  In
    ``INDEXED8`` no arithmetic is possible, so the outermost corner pixel is
    repainted with the neighbouring index (an exact EPX corner cut).  A corner
    is never painted with ``transparent_index`` and a transparent centre is
    never painted at all, so the filter cannot bite holes in sprites; composite
    sprites before filtering if you want background bleed.
    """
    _check_factor(factor)
    if factor == 1:
        return image
    width, height = image.width, image.height
    out_width = width * factor
    stride = out_width
    out = [0] * (out_width * height * factor)
    src = image.pixels

    # 1. Each source pixel owns a factor x factor block of its own colour.
    for y in range(height):
        for x in range(width):
            value = src[y * width + x]
            row = [value] * factor
            for j in range(factor):
                start = (y * factor + j) * stride + x * factor
                out[start : start + factor] = row

    # 2. Corner pass. The corner region grows with the factor but covers at
    #    most half of the block, so the source colour stays dominant and the
    #    four corners of one block never overlap each other.
    #
    #    The outermost one-pixel ring is not filtered: an edge direction cannot
    #    be read at the frame edge without inventing neighbours, and clamping
    #    there manufactures corners (a 1-px checkerboard acquired a blend in
    #    each frame corner before this guard existed). Replicating the ring is
    #    the honest choice, and it is a per-monitor-invisible 1-px band.
    region = max(1, factor // 2)
    denominator = _MAX_COVERAGE_DEN * region
    indexed = image.mode is Mode.INDEXED8

    for y in range(1, height - 1):
        for x in range(1, width - 1):
            value = src[y * width + x]
            for dx, dy in _CORNERS:
                across = image.at(x + dx, y)
                down = image.at(x, y + dy)
                if across != down or across == value:
                    continue
                if across == image.at(x, y - dy) or down == image.at(x - dx, y):
                    continue
                if indexed and (
                    value == transparent_index or across == transparent_index
                ):
                    continue
                corner_x = x * factor + (0 if dx < 0 else factor - 1)
                corner_y = y * factor + (0 if dy < 0 else factor - 1)
                step_x = 1 if dx < 0 else -1
                step_y = 1 if dy < 0 else -1
                if indexed:
                    out[corner_y * stride + corner_x] = across
                    continue
                for b in range(region):
                    coverage = region - b
                    row_offset = (corner_y + b * step_y) * stride + corner_x
                    for a in range(coverage):
                        index = row_offset + a * step_x
                        out[index] = _blend565(
                            out[index], across, region - a - b, denominator
                        )
    return Image(image.mode, out_width, height * factor, tuple(out))


def scale(image: Image, factor: int, filter: Filter | str = Filter.NEAREST) -> Image:
    """Scale by ``filter``. The switch the presenter exposes at runtime."""
    chosen = Filter(filter)
    if chosen is Filter.NEAREST:
        return nearest(image, factor)
    return epx_aa(image, factor)


@dataclass(frozen=True, slots=True)
class Fit:
    """Integer scale and pad geometry for one source frame on one surface.

    Pads are split evenly; the odd pixel goes to the right and bottom, so the
    content sits at :attr:`offset_x` / :attr:`offset_y` and the pad on each
    side is explicit.  Aspect is preserved by construction: the same integer
    :attr:`scale` applies to both axes, never one stretch per axis.
    """

    source_width: int
    source_height: int
    surface_width: int
    surface_height: int
    scale: int
    max_scale: int | None = None

    @property
    def content_width(self) -> int:
        return self.source_width * self.scale

    @property
    def content_height(self) -> int:
        return self.source_height * self.scale

    @property
    def offset_x(self) -> int:
        return (self.surface_width - self.content_width) // 2

    @property
    def offset_y(self) -> int:
        return (self.surface_height - self.content_height) // 2

    @property
    def pad_left(self) -> int:
        return self.offset_x

    @property
    def pad_right(self) -> int:
        return self.surface_width - self.content_width - self.offset_x

    @property
    def pad_top(self) -> int:
        return self.offset_y

    @property
    def pad_bottom(self) -> int:
        return self.surface_height - self.content_height - self.offset_y

    @property
    def pillarbox(self) -> bool:
        """True when bars sit left and right (surface wider than content)."""
        return self.pad_left + self.pad_right > 0

    @property
    def letterbox(self) -> bool:
        """True when bars sit top and bottom (surface taller than content)."""
        return self.pad_top + self.pad_bottom > 0


def fit_scale(
    source_width: int,
    source_height: int,
    surface_width: int,
    surface_height: int,
    *,
    max_scale: int | None = None,
) -> Fit:
    """Largest integer scale that fits, or ``ValueError`` if none does.

    There is deliberately no fractional fallback: a non-integer factor makes
    some source pixels wider than others and those widths move as the camera
    scrolls (the shimmer described in ``docs/research/02-resolution.md`` §2.3).
    """
    for name, value in (
        ("source_width", source_width),
        ("source_height", source_height),
        ("surface_width", surface_width),
        ("surface_height", surface_height),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{name} must be a positive int, got {value!r}")
    if max_scale is not None:
        if not isinstance(max_scale, int) or isinstance(max_scale, bool):
            raise TypeError("max_scale must be an int or None")
        if max_scale < 1:
            raise ValueError(f"max_scale must be >= 1, got {max_scale}")

    scale = min(surface_width // source_width, surface_height // source_height)
    if max_scale is not None:
        scale = min(scale, max_scale)
    if scale < 1:
        raise ValueError(
            f"{source_width}x{source_height} does not fit {surface_width}x"
            f"{surface_height} at any integer scale >= 1; the smallest integer "
            f"fit is {source_width}x{source_height}"
        )
    return Fit(
        source_width=source_width,
        source_height=source_height,
        surface_width=surface_width,
        surface_height=surface_height,
        scale=scale,
        max_scale=max_scale,
    )


@dataclass(frozen=True, slots=True)
class Presentation:
    """Result of :func:`present`: the padded surface and the geometry used."""

    surface: Image
    scaled: Image
    fit: Fit


def present(
    image: Image,
    surface_width: int,
    surface_height: int,
    *,
    filter: Filter | str = Filter.NEAREST,
    pad_value: int | None = None,
    max_scale: int | None = None,
) -> Presentation:
    """Scale ``image`` by an integer factor and centre it on a pad-coloured surface.

    ``pad_value`` defaults to 0 (black ``B5G6R5``).  For ``INDEXED8`` input,
    index 0 is the game's transparent key, so pass an explicit opaque index if
    the result is going to be blitted rather than viewed.
    """
    fit = fit_scale(
        image.width, image.height, surface_width, surface_height, max_scale=max_scale
    )
    if pad_value is None:
        pad_value = 0
    if not 0 <= pad_value < image.mode.limit:
        raise ValueError(f"pad_value {pad_value} out of range for {image.mode.value}")

    scaled = scale(image, fit.scale, filter)
    pixels = [pad_value] * (surface_width * surface_height)
    for y in range(scaled.height):
        dst = (fit.offset_y + y) * surface_width + fit.offset_x
        src = y * scaled.width
        pixels[dst : dst + scaled.width] = scaled.pixels[src : src + scaled.width]
    surface = Image(image.mode, surface_width, surface_height, tuple(pixels))
    return Presentation(surface=surface, scaled=scaled, fit=fit)
