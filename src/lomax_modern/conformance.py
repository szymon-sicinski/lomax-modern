"""Headless render-conformance harness: depth 16 vs depth 24, transparency, scale.

This module is the M4 **exit criterion as an executable check**.  It renders
synthetic scenes — known ``CELL``/``TTAB`` tiles, synthetic palettes, deliberate
index-0 holes — through the own renderer and asserts the output pixels.  It
needs no game data, no ``LOMAX.EXE``, no Wine, no display and no window: it runs
as ``python -m lomax_modern.conformance`` in CI and exits non-zero on the first
broken invariant.

What it grades, and why each case exists
----------------------------------------

depth 16 vs 24
    The same scene is rendered twice: through the shipping 16-bit path
    (:class:`lomax_modern.renderer.Framebuffer`, ``B5G6R5``) and through an
    independent **24-bit reference** (``RGB888``) that shares no blit code with
    the renderer.  Both take their colours from the same 15-bit palette words, so
    any difference is the renderer's *colour handling* and nothing else.  The
    tolerance is not a guess: :func:`depth_tolerance` enumerates all 32,768
    15-bit words and returns the worst per-channel difference the two arithmetic
    paths can produce.  A geometric or transparency divergence — the reference
    places cells itself — shows up as a mismatch, not as a silent pass.

transparency
    Index 0 is the palette's transparent key (``docs/file-formats.md`` §2.3).
    The check counts every source pixel that is index 0, requires the destination
    to keep the background there (in both depths), and requires the key *colour*
    to appear nowhere in the frame.  A blit that paints index 0 fails both ways.
    Fixtures guarantee the key colour is unique in the palette and differs from
    the background, so "0 leaks" cannot be vacuous; :class:`Scene` rejects a
    fixture that breaks that rule.

no shimmer at integer scale
    The presenter only ever scales by an integer factor
    (:func:`lomax_modern.scaler.fit_scale`).  The check proves the consequence on
    pixels: every source pixel becomes a uniform ``factor x factor`` block, and
    scrolling the scene by one source pixel moves the output by exactly
    ``factor`` pixels.  A fractional factor — the thing that makes pixel widths
    wobble as the camera moves (``docs/research/02-resolution.md`` §2.3) — cannot
    survive either assertion, and a surface whose ideal ratio is 2.5x is shown
    to apply 2x with integer pads.

Confidence
----------

Everything asserted here is a property of **our** code, not a measured property
of the retail game, so it is graded "design invariant, proven by this harness".
The two game facts it depends on are cited above and separately graded in
``docs/file-formats.md``: a palette word is 15-bit (blue 0-4, green 5-9, red
10-14) and palette index 0 is the transparent key.  The 15-bit -> 8-bit and
15-bit -> ``B5G6R5`` expansions are ``[H]`` design choices of this project (see
``renderer``), which is exactly why they are pinned by a test rather than
assumed.

The harness is also a **checker that can fail**: every ``check_*`` function takes
the render call as a parameter, so ``tests/unit/test_conformance.py`` feeds it a
deliberately broken renderer and asserts the report says so.  A conformance
harness that cannot fail is a tautology.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from enum import IntEnum
from functools import lru_cache
from typing import Callable, Iterable, Sequence

from . import art
from .art import (
    FLIP_H,
    FLIP_MASK,
    FLIP_V,
    PALETTE_ENTRY_COUNT,
    Cell,
    TileRecord,
    TileSlot,
)
from .renderer import (
    CELL_PIXELS,
    TRANSPARENT_INDEX,
    Framebuffer,
    Palette565,
    rgb15_to_rgb565,
    rgb565_to_rgb8,
)
from .scaler import Filter, Image, Mode, fit_scale, present

__all__ = [
    "Depth",
    "DepthReport",
    "FitReport",
    "Frame",
    "HarnessResult",
    "Scene",
    "ScaleReport",
    "Sprite",
    "Tile",
    "TransparencyReport",
    "check_depth",
    "check_integer_fit",
    "check_integer_scale",
    "check_transparency",
    "depth_tolerance",
    "main",
    "pattern_cell",
    "render",
    "run",
    "scenes",
]

#: Bytes per pixel in each supported depth.
BPP = {16: 2, 24: 3}


class Depth(IntEnum):
    """Colour depth of a rendered frame.

    ``BPP16`` is the game's own ``B5G6R5`` frame; ``BPP24`` is ``RGB888``, used
    as the full-precision reference the 16-bit frame is graded against.
    """

    BPP16 = 16
    BPP24 = 24


#: The RGB triple a packed 24-bit word / ``B5G6R5`` word carries, as 8-bit channels.
RGB = tuple[int, int, int]


def _pack8(rgb: RGB) -> int:
    """Pack 8-bit channels into a ``0xRRGGBB`` word."""
    red, green, blue = rgb
    return (red << 16) | (green << 8) | blue


@dataclass(frozen=True, slots=True)
class Frame:
    """A rendered frame at one :class:`Depth`.

    ``pixels`` holds one integer per pixel in that depth's own units — a
    ``B5G6R5`` word at depth 16, a ``0xRRGGBB`` word at depth 24 — so a frame is
    never silently reinterpreted in the wrong colour space.
    """

    depth: Depth
    width: int
    height: int
    pixels: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"frame must be positive, got {self.width}x{self.height}")
        expected = self.width * self.height
        if len(self.pixels) != expected:
            raise ValueError(
                f"{self.width}x{self.height} needs {expected} pixels, "
                f"got {len(self.pixels)}"
            )
        limit = 0x10000 if self.depth is Depth.BPP16 else 0x1000000
        bad = [value for value in self.pixels if not 0 <= value < limit]
        if bad:
            raise ValueError(f"pixel {bad[0]} does not fit depth {int(self.depth)}")

    def pixel(self, x: int, y: int) -> int:
        """The raw pixel word at ``(x, y)``; out-of-frame raises."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"({x}, {y}) outside {self.width}x{self.height}")
        return self.pixels[y * self.width + x]

    def rgb8(self, x: int, y: int) -> RGB:
        """The pixel as 8-bit channels, in this depth's own conversion."""
        value = self.pixel(x, y)
        if self.depth is Depth.BPP24:
            return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)
        return rgb565_to_rgb8(value)

    def to_bytes(self) -> bytes:
        """The frame in its depth's on-surface layout.

        Depth 16 is little-endian ``u16`` words (a real ``B5G6R5`` surface);
        depth 24 is three bytes per pixel, ``R`` then ``G`` then ``B``.
        """
        if self.depth is Depth.BPP16:
            return b"".join(value.to_bytes(2, "little") for value in self.pixels)
        out = bytearray()
        for value in self.pixels:
            out += bytes(((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF))
        return bytes(out)

    def to_image(self) -> Image:
        """Hand a depth-16 frame to the scaler/presenter unchanged."""
        if self.depth is not Depth.BPP16:
            raise ValueError("only a depth-16 frame maps onto a B5G6R5 surface")
        return Image(Mode.RGB565, self.width, self.height, self.pixels)


@dataclass(frozen=True, slots=True)
class Sprite:
    """One ``CELL`` placed at ``(x, y)`` in scene pixels."""

    cell: Cell
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class Tile:
    """One ``TTAB`` record placed at ``(x, y)``, drawn as its four cells.

    ``cells`` is the cell bank the record indexes into, so an out-of-bank cell
    index is visible to the harness (and is skipped by both render paths, never
    repaired).  Each slot's flag word carries a flip the reference honours too.
    """

    record: TileRecord
    cells: tuple[Cell, ...]
    x: int
    y: int
    layout: str = "strip"


@dataclass(frozen=True, slots=True)
class Scene:
    """A synthetic scene: background, palette, and what is drawn over it.

    A scene is only meaningful as a conformance fixture if its transparent key
    colour is unambiguous, so construction enforces three invariants: the key
    colour occurs once in the palette, it differs from the background, and every
    palette entry is a legal 15-bit word.  A fixture that broke one of these
    would make "the key colour never appears" vacuous, so it is rejected rather
    than quietly accepted.
    """

    name: str
    width: int
    height: int
    background: int
    palette: tuple[int, ...]
    sprites: tuple[Sprite, ...] = ()
    tiles: tuple[Tile, ...] = ()

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"scene must be positive, got {self.width}x{self.height}")
        if len(self.palette) != PALETTE_ENTRY_COUNT:
            raise ValueError(
                f"scene palette holds {len(self.palette)} words, "
                f"expected {PALETTE_ENTRY_COUNT}"
            )
        for label, words in (("palette", self.palette), ("background", (self.background,))):
            bad = [word for word in words if not 0 <= word < 0x8000]
            if bad:
                raise ValueError(f"{label} word {bad[0]:#06x} is not 15-bit")
        key = self.palette[TRANSPARENT_INDEX]
        if self.palette.count(key) != 1:
            raise ValueError(
                "scene palette repeats the transparent key colour; the "
                "key-leak assertion would be ambiguous"
            )
        if key == self.background:
            raise ValueError("scene background equals the transparent key colour")

    def palette565(self) -> Palette565:
        """This scene's palette widened to ``B5G6R5`` (the depth-16 path)."""
        return Palette565(
            slot=0, words=tuple(rgb15_to_rgb565(word) for word in self.palette)
        )

    @property
    def key_rgb(self) -> RGB:
        """The transparent key colour as 8-bit channels."""
        return art.rgb15_to_rgb8(self.palette[TRANSPARENT_INDEX])

    @property
    def background_rgb(self) -> RGB:
        return art.rgb15_to_rgb8(self.background)


# -- synthetic fixtures ----------------------------------------------------


def pattern_cell(index: int, seed: int, *, holes: bool = True) -> Cell:
    """A deterministic 8x8 cell, optionally with index-0 holes on a lattice."""
    pixels = bytearray(CELL_PIXELS * CELL_PIXELS)
    for y in range(CELL_PIXELS):
        for x in range(CELL_PIXELS):
            if holes and (x + y) % 3 == 0:
                pixels[y * CELL_PIXELS + x] = TRANSPARENT_INDEX
                continue
            # 1..255 only: 0 is the key and is never a painted colour here.
            pixels[y * CELL_PIXELS + x] = 1 + ((seed + x * 7 + y * 11) % 255)
    return Cell(index=index, pixels=bytes(pixels))


def _tile_record(cells: Iterable[tuple[int, int] | int]) -> TileRecord:
    """A ``TileRecord`` from four cells: ``(index, flags)`` pairs or bare indices.

    A bare ``int`` is an index with no flags; a ``(index, flags)`` pair sets a
    flip (``FLIP_H``/``FLIP_V``/``FLIP_MASK``).  ``TileRecord`` enforces four.
    """
    slots = []
    for cell in cells:
        if isinstance(cell, tuple):
            index, flags = cell
        else:
            index, flags = cell, 0
        slots.append(TileSlot(index=index, flags=flags))
    return TileRecord(index=0, slots=tuple(slots))


def synthetic_palette(key: int = 0x7C1F) -> tuple[int, ...]:
    """256 15-bit words: a unique transparent key plus a spread over RGB.

    Entry 0 is the key (``0x7C1F`` = magenta by default); entries 1-255 walk
    red/green/blue with coprime strides so every bit plane is exercised.  The
    strides make the key unreachable from entry 1 onwards, which
    :class:`Scene` verifies rather than trusts.
    """
    if not 0 <= key < 0x8000:
        raise ValueError(f"key colour {key:#06x} is not 15-bit")
    words = [key]
    for i in range(1, PALETTE_ENTRY_COUNT):
        red = (i * 5) & 0x1F
        green = (i * 11) & 0x1F
        blue = (i * 17) & 0x1F
        words.append((red << 10) | (green << 5) | blue)
    return tuple(words)


_SCENE_TILES = Scene(
    name="tiles",
    width=64,
    height=40,
    # Differs from every palette entry, so a painted key colour is recognisable.
    background=0x2108,
    palette=synthetic_palette(),
    tiles=(
        # Stored-order ("strip") record: four cells side by side, 32x8.
        Tile(
            record=_tile_record((0, 1, 2, 3)),
            cells=tuple(pattern_cell(i, i * 5) for i in range(4)),
            x=0,
            y=0,
        ),
        # The documented 16x16 assembly ([H]); a different placement rule, so the
        # reference and the renderer must agree on it or the depth case fails.
        Tile(
            record=_tile_record((0, 1, 2, 3)),
            cells=tuple(pattern_cell(i, 100 + i * 3) for i in range(4)),
            x=40,
            y=4,
            layout="2x2",
        ),
        # Slot 3 indexes outside the 4-cell bank: both paths must skip it and
        # leave the background alone (never repaired).
        Tile(
            record=_tile_record((0, 1, 2, 9)),
            cells=tuple(pattern_cell(i, 200 + i) for i in range(4)),
            x=0,
            y=20,
        ),
        # Flips: H, V, both and none.  The reference must mirror each cell the
        # same way blit_tile does or the depth case fails.
        Tile(
            record=_tile_record(
                ((0, FLIP_H), (1, FLIP_V), (2, FLIP_MASK), (3, 0))
            ),
            cells=tuple(pattern_cell(i, 300 + i) for i in range(4)),
            x=32,
            y=20,
        ),
    ),
)

_SCENE_SPRITE = Scene(
    name="sprites",
    width=32,
    height=24,
    background=0x2108,
    palette=synthetic_palette(),
    sprites=(
        Sprite(pattern_cell(0, 1), 4, 4),
        Sprite(pattern_cell(1, 77), 20, 12),
        Sprite(pattern_cell(2, 154), 4, 14),
    ),
)

_SCENE_SWEEP = Scene(
    name="palette-sweep",
    width=16,
    height=16,
    background=0x2108,
    palette=synthetic_palette(),
    sprites=(
        # 64 consecutive palette indices per cell: 191 of the 256 entries land on
        # screen, including the entries whose green channel the 5->6 widening
        # moves furthest.  Every 19th pixel is index 0, so the sweep also carries
        # transparent pixels (a fixture with none could not test the key rule).
        Sprite(
            cell=Cell(
                index=0,
                pixels=bytes(
                    TRANSPARENT_INDEX if i % 19 == 0 else 1 + ((i * 5) % 255)
                    for i in range(CELL_PIXELS**2)
                ),
            ),
            x=0,
            y=0,
        ),
        Sprite(
            cell=Cell(
                index=0,
                pixels=bytes(
                    TRANSPARENT_INDEX if i % 23 == 0 else 128 + (i % 128)
                    for i in range(CELL_PIXELS**2)
                ),
            ),
            x=8,
            y=8,
        ),
    ),
)


def scenes() -> tuple[Scene, ...]:
    """The synthetic fixtures the harness runs, in a stable order."""
    return (_SCENE_TILES, _SCENE_SPRITE, _SCENE_SWEEP)


# -- rendering -------------------------------------------------------------


def _slot_offset(slot: int, layout: str) -> tuple[int, int]:
    """Top-left of cell ``slot`` of a ``TTAB`` record, per ``layout``."""
    if layout == "strip":
        return slot * CELL_PIXELS, 0
    if layout == "2x2":
        # Column-major (verified against a retail render): slots 0/1 are the
        # left column, 2/3 the right.  The reference must agree with the
        # renderer, which is the point of this harness.
        return (slot // 2) * CELL_PIXELS, (slot % 2) * CELL_PIXELS
    raise ValueError(f"unknown tile layout {layout!r}; expected 'strip' or '2x2'")


def _placements(
    scene: Scene, scroll_x: int = 0, scroll_y: int = 0
) -> list[tuple[Cell, int, int, int]]:
    """Every cell the scene draws, with its absolute top-left corner and flip.

    Shared by the 24-bit reference and the transparency checker so the *fixture*
    has one placement rule.  The depth-16 path never uses this list: it calls
    :meth:`Framebuffer.blit_tile` / :meth:`Framebuffer.blit_cell`, which is how a
    placement or flip divergence between the two paths becomes a mismatch.
    """
    placed: list[tuple[Cell, int, int, int]] = []
    for sprite in scene.sprites:
        placed.append((sprite.cell, sprite.x - scroll_x, sprite.y - scroll_y, 0))
    for tile in scene.tiles:
        for slot, cell_slot in enumerate(tile.record.slots):
            if not 0 <= cell_slot.index < len(tile.cells):
                continue
            dx, dy = _slot_offset(slot, tile.layout)
            placed.append(
                (
                    tile.cells[cell_slot.index],
                    tile.x - scroll_x + dx,
                    tile.y - scroll_y + dy,
                    cell_slot.flip,
                )
            )
    return placed


class _Buffer24:
    """A plain ``RGB888`` buffer for the reference path (no shared code)."""

    def __init__(self, width: int, height: int, fill: int) -> None:
        self.width = width
        self.height = height
        self.pixels = [fill] * (width * height)

    def set(self, x: int, y: int, value: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y * self.width + x] = value


def _blit_cell24(
    buffer: _Buffer24, cell: Cell, palette: Sequence[int], x0: int, y0: int, flip: int = 0
) -> None:
    """Reference cell blit: skip the transparent key, paint everything else.

    ``flip`` mirrors the cell the same way :meth:`Framebuffer.blit_cell` does.
    """
    for dy in range(CELL_PIXELS):
        for dx in range(CELL_PIXELS):
            sx = (CELL_PIXELS - 1 - dx) if flip & FLIP_H else dx
            sy = (CELL_PIXELS - 1 - dy) if flip & FLIP_V else dy
            index = cell.pixels[sy * CELL_PIXELS + sx]
            if index == TRANSPARENT_INDEX:
                continue
            buffer.set(x0 + dx, y0 + dy, palette[index])


def _render16(scene: Scene, scroll_x: int, scroll_y: int) -> Frame:
    """Render through the shipping 16-bit renderer."""
    frame = Framebuffer(
        scene.width, scene.height, fill=rgb15_to_rgb565(scene.background)
    )
    palette = scene.palette565()
    for sprite in scene.sprites:
        frame.blit_cell(sprite.cell, palette, sprite.x - scroll_x, sprite.y - scroll_y)
    for tile in scene.tiles:
        frame.blit_tile(
            tile.record,
            tile.cells,
            palette,
            tile.x - scroll_x,
            tile.y - scroll_y,
            layout=tile.layout,
        )
    return Frame(Depth.BPP16, scene.width, scene.height, tuple(frame.pixels))


def _render24(scene: Scene, scroll_x: int, scroll_y: int) -> Frame:
    """Render the same scene at full precision, from the documented rule."""
    buffer = _Buffer24(scene.width, scene.height, _pack8(scene.background_rgb))
    palette = tuple(_pack8(art.rgb15_to_rgb8(word)) for word in scene.palette)
    for cell, x0, y0, flip in _placements(scene, scroll_x, scroll_y):
        _blit_cell24(buffer, cell, palette, x0, y0, flip)
    return Frame(Depth.BPP24, scene.width, scene.height, tuple(buffer.pixels))


RenderFn = Callable[..., Frame]


def render(
    scene: Scene, depth: Depth, *, scroll_x: int = 0, scroll_y: int = 0
) -> Frame:
    """Render ``scene`` at ``depth``, optionally scrolled by whole pixels."""
    chosen = Depth(depth)
    if chosen is Depth.BPP16:
        return _render16(scene, scroll_x, scroll_y)
    return _render24(scene, scroll_x, scroll_y)


# -- the depth-16 vs depth-24 tolerance, measured not guessed --------------


@lru_cache(maxsize=1)
def depth_tolerance() -> RGB:
    """Worst per-channel difference between the two colour paths, in 8-bit units.

    Enumerates every one of the 32,768 15-bit palette words and compares

    * ``15-bit -> 8-bit`` directly (the depth-24 reference), with
    * ``15-bit -> B5G6R5 -> 8-bit`` (the depth-16 frame, expanded back).

    Red and blue pass through 5 bits on both paths, so they agree exactly.
    Green gains a bit on the way in (5->6) and loses it on the way out, which
    costs at most one 5-bit step; the number returned is whatever that costs for
    the *actual* code, so a change to the expansion rule moves the bound instead
    of hiding under a hand-written constant.
    """
    worst = [0, 0, 0]
    for word in range(0x8000):
        direct = art.rgb15_to_rgb8(word)
        via_surface = rgb565_to_rgb8(rgb15_to_rgb565(word))
        for channel, (a, b) in enumerate(zip(direct, via_surface)):
            delta = abs(a - b)
            if delta > worst[channel]:
                worst[channel] = delta
    return (worst[0], worst[1], worst[2])


# -- reports ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Mismatch:
    """One pixel where the 16-bit frame disagrees with the 24-bit reference."""

    x: int
    y: int
    depth16: RGB
    depth24: RGB
    delta: RGB

    def line(self) -> str:
        return (
            f"({self.x},{self.y}) 16={self.depth16} 24={self.depth24} "
            f"delta={self.delta}"
        )


@dataclass(frozen=True, slots=True)
class DepthReport:
    """Result of comparing a depth-16 frame against the depth-24 reference."""

    scene: str
    width: int
    height: int
    tolerance: RGB
    max_delta: RGB
    mismatches: tuple[Mismatch, ...]
    mismatch_count: int

    @property
    def ok(self) -> bool:
        return self.mismatch_count == 0

    def detail(self) -> str:
        head = (
            f"{self.width}x{self.height} px, max delta rgb={self.max_delta}, "
            f"tolerance {self.tolerance}"
        )
        if self.ok:
            return f"depth 16 vs 24: {head}"
        return (
            f"depth 16 vs 24: {head} — {self.mismatch_count} px outside tolerance; "
            f"first {self.mismatches[0].line()}"
        )


def compare_frames(
    frame16: Frame,
    frame24: Frame,
    *,
    scene: str = "",
    tolerance: RGB | None = None,
    report_limit: int = 8,
) -> DepthReport:
    """Compare a depth-16 frame with a depth-24 frame, pixel by pixel.

    Both frames must come from the same scene geometry; the comparison is on
    8-bit channels so the two depths are compared in one colour space.  A pixel
    is a mismatch when any channel exceeds ``tolerance`` (default: the measured
    :func:`depth_tolerance`).
    """
    if frame16.depth is not Depth.BPP16 or frame24.depth is not Depth.BPP24:
        raise ValueError("compare_frames() needs one depth-16 and one depth-24 frame")
    if (frame16.width, frame16.height) != (frame24.width, frame24.height):
        raise ValueError(
            f"frame sizes differ: {frame16.width}x{frame16.height} vs "
            f"{frame24.width}x{frame24.height}"
        )
    bound = tuple(depth_tolerance() if tolerance is None else tolerance)
    mismatches: list[Mismatch] = []
    max_delta = [0, 0, 0]
    count = 0
    for y in range(frame16.height):
        for x in range(frame16.width):
            a = frame16.rgb8(x, y)
            b = frame24.rgb8(x, y)
            delta = tuple(abs(p - q) for p, q in zip(a, b))
            for channel, value in enumerate(delta):
                if value > max_delta[channel]:
                    max_delta[channel] = value
            if any(value > bound[i] for i, value in enumerate(delta)):
                count += 1
                if len(mismatches) < report_limit:
                    mismatches.append(
                        Mismatch(x, y, a, b, (delta[0], delta[1], delta[2]))
                    )
    return DepthReport(
        scene=scene,
        width=frame16.width,
        height=frame16.height,
        tolerance=(bound[0], bound[1], bound[2]),
        max_delta=(max_delta[0], max_delta[1], max_delta[2]),
        mismatches=tuple(mismatches),
        mismatch_count=count,
    )


def check_depth(
    scene: Scene,
    *,
    scroll_x: int = 0,
    scroll_y: int = 0,
    render_fn: RenderFn = render,
) -> DepthReport:
    """Render ``scene`` at both depths and compare the pixels.

    ``render_fn`` is the injection point for the harness's own negative tests: a
    broken renderer must make this report fail, or the check is worthless.
    """
    return compare_frames(
        render_fn(scene, Depth.BPP16, scroll_x=scroll_x, scroll_y=scroll_y),
        render_fn(scene, Depth.BPP24, scroll_x=scroll_x, scroll_y=scroll_y),
        scene=scene.name,
    )


@dataclass(frozen=True, slots=True)
class TransparencyReport:
    """Result of the key-colour / untouched-destination check."""

    scene: str
    transparent_pixels: int
    occluded_pixels: int
    untouched_pixels: int
    altered_pixels: int
    key_leaks_16: int
    key_leaks_24: int
    first_bad: tuple[int, int, RGB, RGB] | None

    @property
    def ok(self) -> bool:
        return (
            self.transparent_pixels > 0
            and self.altered_pixels == 0
            and self.key_leaks_16 == 0
            and self.key_leaks_24 == 0
        )

    def detail(self) -> str:
        head = (
            f"{self.transparent_pixels} transparent px, {self.untouched_pixels} "
            f"untouched, {self.occluded_pixels} occluded, "
            f"key-colour leaks 16={self.key_leaks_16} 24={self.key_leaks_24}"
        )
        if self.ok:
            return f"transparency: {head}"
        if self.transparent_pixels == 0:
            return "transparency: scene has no transparent pixels — vacuous fixture"
        if self.first_bad is not None:
            x, y, got, expected = self.first_bad
            return (
                f"transparency: {head} — {self.altered_pixels} px painted; "
                f"first ({x},{y}) got {got} expected background {expected}"
            )
        return f"transparency: {head} — the key colour was painted"


def check_transparency(scene: Scene, *, render_fn: RenderFn = render) -> TransparencyReport:
    """Assert index 0 is never painted and always leaves the destination alone.

    Two independent assertions, because a leak can show up in either:

    * every destination pixel fed by a source index of 0 still shows the
      background (checked at both depths; pixels covered by another sprite later
      are counted as ``occluded`` and excluded, so fixture overlap cannot hide a
      leak);
    * the transparent key *colour* appears nowhere in either frame.
    """
    coverage = bytearray(scene.width * scene.height)
    transparent: list[tuple[int, int]] = []
    for cell, x0, y0, flip in _placements(scene):
        for dy in range(CELL_PIXELS):
            for dx in range(CELL_PIXELS):
                px, py = x0 + dx, y0 + dy
                if not (0 <= px < scene.width and 0 <= py < scene.height):
                    continue
                sx = (CELL_PIXELS - 1 - dx) if flip & FLIP_H else dx
                sy = (CELL_PIXELS - 1 - dy) if flip & FLIP_V else dy
                index = cell.pixels[sy * CELL_PIXELS + sx]
                if index == TRANSPARENT_INDEX:
                    transparent.append((px, py))
                else:
                    coverage[py * scene.width + px] += 1

    background16 = rgb15_to_rgb565(scene.background)
    background24 = _pack8(scene.background_rgb)
    key16 = rgb15_to_rgb565(scene.palette[TRANSPARENT_INDEX])
    key24 = _pack8(scene.key_rgb)

    frames = {
        Depth.BPP16: render_fn(scene, Depth.BPP16),
        Depth.BPP24: render_fn(scene, Depth.BPP24),
    }
    untouched = occluded = altered = 0
    first_bad: tuple[int, int, RGB, RGB] | None = None
    for x, y in transparent:
        if coverage[y * scene.width + x]:
            occluded += 1
            continue
        good = (
            frames[Depth.BPP16].pixel(x, y) == background16
            and frames[Depth.BPP24].pixel(x, y) == background24
        )
        if good:
            untouched += 1
        else:
            altered += 1
            if first_bad is None:
                first_bad = (x, y, frames[Depth.BPP16].rgb8(x, y), scene.background_rgb)

    return TransparencyReport(
        scene=scene.name,
        transparent_pixels=len(transparent),
        occluded_pixels=occluded,
        untouched_pixels=untouched,
        altered_pixels=altered,
        key_leaks_16=sum(1 for value in frames[Depth.BPP16].pixels if value == key16),
        key_leaks_24=sum(1 for value in frames[Depth.BPP24].pixels if value == key24),
        first_bad=first_bad,
    )


@dataclass(frozen=True, slots=True)
class BlockReport:
    """Result of the "every source pixel is a uniform k x k block" check."""

    factor: int
    source: tuple[int, int]
    surface: tuple[int, int]
    compared_pixels: int
    violations: int
    first: tuple[int, int, int, int] | None

    @property
    def ok(self) -> bool:
        return self.violations == 0

    def detail(self) -> str:
        head = (
            f"{self.source[0]}x{self.source[1]} -> {self.surface[0]}x"
            f"{self.surface[1]} at x{self.factor}, "
            f"{self.compared_pixels} px compared"
        )
        if self.ok:
            return f"integer blocks: {head}, all uniform"
        x, y, got, expected = self.first
        return (
            f"integer blocks: {head} — {self.violations} px not a uniform "
            f"{self.factor}x{self.factor} block; first ({x},{y}) got {got} expected {expected}"
        )


def check_block_replication(
    source: Frame,
    presented: Sequence[int],
    surface: tuple[int, int],
    factor: int,
    *,
    offset: tuple[int, int] = (0, 0),
) -> BlockReport:
    """Assert every source pixel became a uniform ``factor x factor`` block.

    ``presented`` is the surface's pixels, ``surface`` its size and ``offset``
    where the content starts.  A handful of duplicated/skipped columns (what a
    fractional scale produces) shows up here as a non-uniform block.
    """
    if factor < 1:
        raise ValueError(f"factor must be >= 1, got {factor}")
    surface_w, surface_h = surface
    if len(presented) != surface_w * surface_h:
        raise ValueError(
            f"presented buffer holds {len(presented)} px, expected "
            f"{surface_w * surface_h} for {surface_w}x{surface_h}"
        )
    off_x, off_y = offset
    violations = 0
    first: tuple[int, int, int, int] | None = None
    compared = 0
    for y in range(source.height):
        for x in range(source.width):
            expected = source.pixel(x, y)
            for j in range(factor):
                row = (off_y + y * factor + j) * surface_w + off_x + x * factor
                for i in range(factor):
                    compared += 1
                    got = presented[row + i]
                    if got != expected:
                        violations += 1
                        if first is None:
                            first = (x, y, got, expected)
    return BlockReport(
        factor=factor,
        source=(source.width, source.height),
        surface=(surface_w, surface_h),
        compared_pixels=compared,
        violations=violations,
        first=first,
    )


def check_scroll_shift(
    base: Sequence[int],
    shifted: Sequence[int],
    surface: tuple[int, int],
    *,
    factor: int,
    shift_px: int,
    offset: tuple[int, int] = (0, 0),
    content: tuple[int, int],
) -> int:
    """Count pixels where a 1-px scroll did not move the output by exactly ``factor``.

    ``base`` and ``shifted`` are two presentations of the same scene, the second
    scrolled left by ``shift_px`` source pixels, so content that sat at source
    column ``x`` now sits at ``x - shift_px`` and the rigid-translation invariant
    is ``shifted(x) == base(x + factor * shift_px)`` over the overlap.  Any
    resampling wobble breaks that equality.
    """
    surface_w, _ = surface
    content_w, content_h = content
    off_x, off_y = offset
    step = factor * shift_px
    if step >= content_w:
        raise ValueError(f"shift of {shift_px} px covers the whole {content_w}px content")
    violations = 0
    for y in range(content_h):
        row = (off_y + y) * surface_w + off_x
        for x in range(content_w - step):
            if shifted[row + x] != base[row + x + step]:
                violations += 1
    return violations


@dataclass(frozen=True, slots=True)
class ScaleReport:
    """Result of the "no shimmer at integer scale" check."""

    scene: str
    factor: int
    ideal_ratio: float
    applied_scale: int
    content: tuple[int, int]
    surface: tuple[int, int]
    pads: tuple[int, int, int, int]
    blocks: BlockReport
    shifts: int
    shift_violations: int

    @property
    def ok(self) -> bool:
        return (
            self.applied_scale == self.factor
            and self.content == (self.blocks.source[0] * self.factor, self.blocks.source[1] * self.factor)
            and self.blocks.ok
            and self.shift_violations == 0
            and all(pad >= 0 for pad in self.pads)
        )

    def detail(self) -> str:
        head = (
            f"ideal {self.ideal_ratio:.3f}x -> applied x{self.applied_scale}, "
            f"pads {self.pads}, {self.shifts} scroll shifts"
        )
        if self.ok:
            return f"integer scale: {head}, {self.blocks.violations} block violations"
        return (
            f"integer scale: {head} — {self.blocks.violations} block violations, "
            f"{self.shift_violations} shift violations"
        )


def check_integer_scale(
    scene: Scene,
    factor: int,
    *,
    surface: tuple[int, int] | None = None,
    shifts: Sequence[int] = (1, 2, 3, 5, 7),
    render_fn: RenderFn = render,
) -> ScaleReport:
    """Present ``scene`` at an integer factor and prove nothing wobbles.

    The surface is deliberately a couple of pixels wider/taller than the content
    so the pads are exercised; the block check then runs on the padded surface
    with the real offset, which is what the presenter does.
    """
    base_frame = render_fn(scene, Depth.BPP16)
    if surface is None:
        surface = (scene.width * factor + 2, scene.height * factor + 4)
    surface_w, surface_h = surface
    base = present(
        base_frame.to_image(), surface_w, surface_h, filter=Filter.NEAREST
    )
    blocks = check_block_replication(
        base_frame,
        base.surface.pixels,
        surface,
        factor,
        offset=(base.fit.offset_x, base.fit.offset_y),
    )
    content = (base.scaled.width, base.scaled.height)
    shift_violations = 0
    for shift in shifts:
        shifted_frame = render_fn(scene, Depth.BPP16, scroll_x=shift)
        shifted = present(
            shifted_frame.to_image(), surface_w, surface_h, filter=Filter.NEAREST
        )
        shift_violations += check_scroll_shift(
            base.surface.pixels,
            shifted.surface.pixels,
            surface,
            factor=factor,
            shift_px=shift,
            offset=(base.fit.offset_x, base.fit.offset_y),
            content=content,
        )
    return ScaleReport(
        scene=scene.name,
        factor=factor,
        ideal_ratio=surface_w / scene.width,
        applied_scale=base.fit.scale,
        content=content,
        surface=surface,
        pads=(base.fit.pad_left, base.fit.pad_right, base.fit.pad_top, base.fit.pad_bottom),
        blocks=blocks,
        shifts=len(shifts),
        shift_violations=shift_violations,
    )


@dataclass(frozen=True, slots=True)
class FitReport:
    """Result of the "never scale fractionally" check on a realistic surface."""

    source: tuple[int, int]
    surface: tuple[int, int]
    ideal_ratio: float
    applied_scale: int
    content: tuple[int, int]
    pads: tuple[int, int, int, int]

    @property
    def ok(self) -> bool:
        return (
            self.applied_scale >= 1
            and isinstance(self.applied_scale, int)
            and self.content
            == (self.source[0] * self.applied_scale, self.source[1] * self.applied_scale)
            and all(pad >= 0 for pad in self.pads)
            and self.content[0] + self.pads[0] + self.pads[1] == self.surface[0]
            and self.content[1] + self.pads[2] + self.pads[3] == self.surface[1]
        )

    def detail(self) -> str:
        state = "integer only" if self.ok else "NOT integer / pads do not add up"
        return (
            f"fit: {self.source[0]}x{self.source[1]} in {self.surface[0]}x"
            f"{self.surface[1]}, ideal {self.ideal_ratio:.3f}x -> x{self.applied_scale} "
            f"content {self.content[0]}x{self.content[1]}, pads {self.pads} ({state})"
        )


def check_integer_fit(
    source: tuple[int, int], surface: tuple[int, int]
) -> FitReport:
    """Show that an awkward ratio (e.g. 2.5x) resolves to an integer factor.

    This is the geometry half of "no shimmer": :func:`scaler.fit_scale` has no
    fractional fallback, so the pixels can only ever be duplicated whole.
    """
    fit = fit_scale(source[0], source[1], surface[0], surface[1])
    return FitReport(
        source=source,
        surface=surface,
        ideal_ratio=min(surface[0] / source[0], surface[1] / source[1]),
        applied_scale=fit.scale,
        content=(fit.content_width, fit.content_height),
        pads=(fit.pad_left, fit.pad_right, fit.pad_top, fit.pad_bottom),
    )


# -- the harness -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Case:
    """One named conformance case and its outcome."""

    name: str
    ok: bool
    detail: str

    def line(self) -> str:
        return f"{'PASS' if self.ok else 'FAIL'}  {self.name}: {self.detail}"


@dataclass(frozen=True, slots=True)
class HarnessResult:
    """Every case the harness ran, in order."""

    cases: tuple[Case, ...]

    @property
    def ok(self) -> bool:
        return bool(self.cases) and all(case.ok for case in self.cases)

    @property
    def failures(self) -> tuple[Case, ...]:
        return tuple(case for case in self.cases if not case.ok)

    def summary(self) -> str:
        passed = sum(1 for case in self.cases if case.ok)
        head = (
            "render conformance (headless, no display, no game data)\n"
            f"depth-bound: 15-bit -> 8-bit directly vs 15-bit -> B5G6R5 -> 8-bit "
            f"max delta rgb={depth_tolerance()} (measured over 32768 words)\n"
        )
        body = "\n".join(f"  {case.line()}" for case in self.cases)
        verdict = "PASS" if self.ok else "FAIL"
        return f"{head}{body}\nverdict: {verdict} ({passed}/{len(self.cases)} cases)"

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "display": "not required",
            "depth_tolerance": list(depth_tolerance()),
            "cases": [
                {"name": case.name, "ok": case.ok, "detail": case.detail}
                for case in self.cases
            ],
        }


def run(*, render_fn: RenderFn = render) -> HarnessResult:
    """Run every conformance case over the synthetic fixtures."""
    cases: list[Case] = []
    for scene in scenes():
        depth = check_depth(scene, render_fn=render_fn)
        cases.append(Case(f"depth-16-vs-24/{scene.name}", depth.ok, depth.detail()))
        alpha = check_transparency(scene, render_fn=render_fn)
        cases.append(Case(f"transparency/{scene.name}", alpha.ok, alpha.detail()))
    for scene, factor in ((_SCENE_TILES, 3), (_SCENE_SWEEP, 2)):
        scale = check_integer_scale(scene, factor, render_fn=render_fn)
        cases.append(Case(f"integer-scale/{scene.name}-x{factor}", scale.ok, scale.detail()))
    normal = check_integer_fit((320, 240), (800, 600))
    cases.append(Case("integer-fit/320x240-in-800x600", normal.ok, normal.detail()))
    native = check_integer_fit((320, 240), (1920, 1080))
    cases.append(Case("integer-fit/320x240-in-1920x1080", native.ok, native.detail()))
    return HarnessResult(tuple(cases))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the harness and print a report; exit 0 on pass, 1 on any failure.

    ``--json PATH`` writes the same result as JSON.  Nothing here needs a
    display: the harness never opens a window or a GPU surface, so it runs under
    a bare ``python`` in CI (``xvfb-run`` is not required).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    json_path: str | None = None
    if args:
        if args[0] in ("-h", "--help"):
            print("usage: python -m lomax_modern.conformance [--json PATH]")
            return 0
        if args[0] == "--json" and len(args) == 2:
            json_path = args[1]
        else:
            print(f"unrecognised arguments: {args}", file=sys.stderr)
            print("usage: python -m lomax_modern.conformance [--json PATH]", file=sys.stderr)
            return 2

    result = run()
    print(result.summary())
    print(f"display: not required (DISPLAY={os.environ.get('DISPLAY', 'unset')})")
    if json_path is not None:
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(result.to_dict(), handle, indent=2)
            handle.write("\n")
        print(f"json: {json_path}")
    return 0 if result.ok else 1


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
