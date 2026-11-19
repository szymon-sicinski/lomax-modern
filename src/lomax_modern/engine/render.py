"""16-bit ``B5G6R5`` framebuffer and the engine's two render paths.

:func:`render_tiles` composes the visible tile art: it walks the visible
``MAP`` cells, resolves each ``tile_word`` to a ``TTAB`` record, blits the
record's four ``CELL`` blocks (flips applied) with the ``HEAD`` palette and
index-0 transparency into the 320x240 viewport, and overlays the player marker
so the camera-follow and scrolling are visible.  :func:`render` remains the
*geometric* debug path: every non-zero collision cell is drawn in one colour
and the player/entities as markers, with the unresolved bits (Q31) flagged in
the report rather than painted.

Two placements stay hypotheses and are rendered exactly as
:mod:`lomax_modern.renderer` blits them, so a wrong assumption shows up in the
output instead of hiding: the four cells of a ``TTAB`` record are assembled in
the verified 2x2 column-major order (``[V]``, G1) and the flip-axis pairing (``0x2000``
horizontal / ``0x4000`` vertical) is this decoder's convention (``[H]``, Q33).

``Frame`` is a genuine 16-bit buffer: pixels are packed ``B5G6R5`` and
``to_bytes()`` emits little-endian ``u16`` words suitable for a 16-bit surface.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from ..art import DEFAULT_PALETTE_SLOT
from ..renderer import Framebuffer, head_palette565
from .entities import Player
from .level import CELL_PX, Level
from .state import GameState

#: The original internal resolution (``docs/roadmap/15-strategy-report.md`` §3).
VIEWPORT_WIDTH = 320
VIEWPORT_HEIGHT = 240


def pack_rgb565(r: int, g: int, b: int) -> int:
    """Pack 8-bit ``r,g,b`` into a 16-bit ``B5G6R5`` word."""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def unpack_rgb565(word: int) -> tuple[int, int, int]:
    """Inverse of :func:`pack_rgb565`, returning 8-bit channel values.

    Every channel is widened by *bit replication* — shift up and copy the top
    bits back into the gap, so 0 stays 0 and full scale stays 255::

        r8 = r5 << 3 | r5 >> 2      g8 = g6 << 2 | g6 >> 4      b8 = b5 << 3 | b5 >> 2

    Green is the channel that is easy to get wrong: it has six bits, so the
    replication shift is ``>> 4`` and not ``>> 2``.  ``g6 << 2 | g6 >> 2``
    changes 55 of the 64 green values — over-brightens 46 by up to 12/255, under-brightens 9 by up to 3/255.  Both formulas
    agree on 0 and 255, which is why a primary-only round trip cannot see the
    difference; ``test_unpack_rgb565_widens_green_by_bit_replication`` pins the
    mid-range values instead.
    """
    r = (word >> 11) & 0x1F
    g = (word >> 5) & 0x3F
    b = word & 0x1F
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


#: Marker colours (B5G6R5) for the geometric frame.  Purely diagnostic.
COLOUR_SKY = pack_rgb565(16, 24, 48)
COLOUR_SOLID = pack_rgb565(200, 200, 200)
COLOUR_PLAYER = pack_rgb565(255, 220, 0)
COLOUR_COLLECTIBLE = pack_rgb565(255, 140, 0)
COLOUR_EXIT = pack_rgb565(0, 220, 0)


@dataclass
class Frame:
    """A width×height framebuffer of ``B5G6R5`` words."""

    width: int
    height: int
    pixels: list[int]

    def __init__(self, width: int, height: int, fill: int = COLOUR_SKY) -> None:
        self.width = width
        self.height = height
        self.pixels = [fill] * (width * height)

    def set(self, x: int, y: int, value: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y * self.width + x] = value

    def fill_rect(self, x0: int, y0: int, w: int, h: int, value: int) -> None:
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                self.set(x, y, value)

    def pixel(self, x: int, y: int) -> int:
        return self.pixels[y * self.width + x]

    def to_bytes(self) -> bytes:
        """The buffer as little-endian ``u16`` words (a real 16-bit surface)."""
        return struct.pack("<" + "H" * len(self.pixels), *self.pixels)


def frame_to_rgba(frame: Frame) -> bytes:
    """Convert a ``B5G6R5`` frame to RGBA8888 bytes (for PNG export, opaque)."""
    out = bytearray()
    for word in frame.pixels:
        r, g, b = unpack_rgb565(word)
        out += bytes((r, g, b, 255))
    return bytes(out)


def camera(level: Level, player: Player, vw: int, vh: int) -> tuple[int, int]:
    """Viewport top-left in pixels, centred on the player and clamped to bounds.

    When the level is smaller than the viewport the camera clamps at zero and
    the content is drawn from the top-left; levels are ordinarily at least as
    large as the 320x240 viewport.
    """
    x = int(player.centre_x - vw / 2)
    y = int(player.centre_y - vh / 2)
    x = max(0, min(x, max(0, level.width_px - vw)))
    y = max(0, min(y, max(0, level.height_px - vh)))
    return x, y


def render(
    level: Level,
    state: GameState,
    *,
    viewport: tuple[int, int] = (VIEWPORT_WIDTH, VIEWPORT_HEIGHT),
) -> Frame:
    """Compose the visible geometric frame: collision grid + entities."""
    vw, vh = viewport
    cam_x, cam_y = camera(level, state.player, vw, vh)
    frame = Frame(vw, vh)

    cx0 = cam_x // CELL_PX
    cy0 = cam_y // CELL_PX
    cx1 = (cam_x + vw - 1) // CELL_PX
    cy1 = (cam_y + vh - 1) // CELL_PX
    for cell_y in range(cy0, cy1 + 1):
        for cell_x in range(cx0, cx1 + 1):
            if level.solid_at(cell_x, cell_y):
                sx = cell_x * CELL_PX - cam_x
                sy = cell_y * CELL_PX - cam_y
                frame.fill_rect(sx, sy, CELL_PX, CELL_PX, COLOUR_SOLID)

    for i, item in enumerate(state.entities.collectibles):
        if i in state.entities.collected:
            continue
        sx = item.cell_x * CELL_PX - cam_x
        sy = item.cell_y * CELL_PX - cam_y
        frame.fill_rect(sx + 3, sy + 3, 10, 10, COLOUR_COLLECTIBLE)

    for exit_ in state.entities.exits:
        sx = exit_.cell_x * CELL_PX - cam_x
        sy = exit_.cell_y * CELL_PX - cam_y
        frame.fill_rect(
            sx, sy, exit_.width_cells * CELL_PX, exit_.height_cells * CELL_PX, COLOUR_EXIT
        )

    sx = int(state.player.x) - cam_x
    sy = int(state.player.y) - cam_y
    frame.fill_rect(sx, sy, state.player.width, state.player.height, COLOUR_PLAYER)
    return frame


def render_tiles(
    level: Level,
    state: GameState,
    *,
    viewport: tuple[int, int] = (VIEWPORT_WIDTH, VIEWPORT_HEIGHT),
) -> Frame:
    """Compose the visible tile art: MAP -> TTAB -> CELL -> HEAD palette.

    Walks the ``MAP`` cells visible under the camera and, for each, resolves
    its ``tile_word`` to the playfield's ``TTAB`` record and blits the record's
    four ``CELL`` blocks in the verified 2x2 column-major order with the ``HEAD`` palette
    (slot 1) and index-0 transparency.  A ``tile_word`` outside the plane's
    ``TTAB`` bank leaves the backdrop untouched — it is never repaired.

    The backdrop (transparent regions) is :data:`COLOUR_SKY`, a placeholder:
    the real parallax/sky layer is a separate plane this card does not draw.
    The player marker is overlaid last so camera-follow and scrolling are
    visible; no collectible/exit/GNMY markers are drawn here (that is a
    separate density card).
    """
    vw, vh = viewport
    cam_x, cam_y = camera(level, state.player, vw, vh)
    section = level.sections[level.playfield]
    plane = section.plane
    tiles = section.tiles
    cells = level.cells
    palette = head_palette565(section.head, DEFAULT_PALETTE_SLOT)

    fb = Framebuffer(vw, vh, fill=COLOUR_SKY)
    cx0 = max(0, cam_x // CELL_PX)
    cy0 = max(0, cam_y // CELL_PX)
    cx1 = min(plane.width_cells - 1, (cam_x + vw - 1) // CELL_PX)
    cy1 = min(plane.height_cells - 1, (cam_y + vh - 1) // CELL_PX)
    for cell_y in range(cy0, cy1 + 1):
        for cell_x in range(cx0, cx1 + 1):
            tile_word = plane.at(cell_x, cell_y).tile_word
            if 0 <= tile_word < len(tiles):
                fb.blit_tile(
                    tiles[tile_word],
                    cells,
                    palette,
                    cell_x * CELL_PX - cam_x,
                    cell_y * CELL_PX - cam_y,
                    layout="2x2",
                )

    sx = int(state.player.x) - cam_x
    sy = int(state.player.y) - cam_y
    fb.fill_rect(sx, sy, state.player.width, state.player.height, COLOUR_PLAYER)

    frame = Frame(vw, vh)
    frame.pixels = fb.pixels
    return frame
