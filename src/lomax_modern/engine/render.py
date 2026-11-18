"""16-bit ``B5G6R5`` framebuffer and the collision-layer frame.

This is the engine's *geometric* frame — it proves the loop produces pixels at
the original resolution from decoded ``CELL``/``TTAB``/``MAP`` data — not the
full art renderer.  The tile art blit, palette transparency, scaling and
filters are owned by the M4 renderer card; here every non-zero collision cell
is drawn in one colour and the player/entities as markers, with the unresolved
bits (Q31) flagged in the report rather than painted.

``Frame`` is a genuine 16-bit buffer: pixels are packed ``B5G6R5`` and
``to_bytes()`` emits little-endian ``u16`` words suitable for a 16-bit surface.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

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
    """Inverse of :func:`pack_rgb565`, returning 8-bit channel values."""
    r = (word >> 11) & 0x1F
    g = (word >> 5) & 0x3F
    b = word & 0x1F
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 2), (b << 3) | (b >> 2))


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
