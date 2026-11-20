"""16-bit ``B5G6R5`` framebuffer and the engine's two render paths.

:func:`render_tiles` composes the visible tile art: it walks the visible
``MAP`` cells, resolves each ``tile_word`` to a ``TTAB`` record, blits the
record's four ``CELL`` blocks (flips applied) with the ``HEAD`` palette and
index-0 transparency into the 320x240 viewport, overlays the playfield's
``GNMY`` placements as markers styled by the placement's ``NMY`` name
(``Start``/``Exit``/``Moneybag`` distinct, every other name one grey "other
type" bucket — Q32 **[V]**), and finally the player — its standing ``ANIM``
sprite from the global ``MAIN.WLD`` bank, falling back to a marker when that
bank is absent — so the camera-follow and scrolling are visible.
:func:`render` remains the
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

from ..anim_nmy import placement_role
from .. import anim_clip
from ..art import DEFAULT_PALETTE_SLOT, SPRITE_PALETTE_SLOT
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

#: Marker colours for the three ``GNMY`` placement roles Q32 evidenced **[V]**
#: (``Start``/``Exit``/``Moneybag``) and one grey bucket for every other ``NMY``
#: name.  Purely diagnostic.
COLOUR_GNMY_START = pack_rgb565(255, 255, 255)
COLOUR_GNMY_EXIT = pack_rgb565(0, 220, 0)
COLOUR_GNMY_MONEYBAG = pack_rgb565(255, 140, 0)
COLOUR_GNMY_OTHER = pack_rgb565(120, 120, 120)


@dataclass(frozen=True)
class MarkerStyle:
    """How one placement is drawn: its evidenced role, colour and pixel size."""

    role: str
    colour: int
    size: int


#: One style per role.  The three evidenced roles differ in colour *and* size
#: so a greyscale capture still separates them; ``other`` is the single bucket
#: for the names whose handlers are unmapped — no per-name glyph is invented.
GNMY_MARKER_STYLES: dict[str, MarkerStyle] = {
    "start": MarkerStyle("start", COLOUR_GNMY_START, 7),
    "exit": MarkerStyle("exit", COLOUR_GNMY_EXIT, 5),
    "moneybag": MarkerStyle("moneybag", COLOUR_GNMY_MONEYBAG, 3),
    "other": MarkerStyle("other", COLOUR_GNMY_OTHER, 3),
}


def gnmy_marker(name: str | None) -> MarkerStyle:
    """The marker style for a placement's ``NMY`` name.

    The name is classified by :func:`lomax_modern.anim_nmy.placement_role`, so
    only ``Start``/``Exit``/``Moneybag`` (Q32 **[V]**) get their own style and
    every other name — including a missing one — falls into the grey ``other``
    bucket instead of inventing a meaning.
    """
    return GNMY_MARKER_STYLES[placement_role(name)]


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


def overlay_gnmy(
    frame: Framebuffer,
    entries,
    cam_x: int,
    cam_y: int,
) -> None:
    """Draw one marker per ``GNMY`` placement, styled by its ``NMY`` name.

    ``entries`` are the playfield plane's :class:`lomax_modern.anim_nmy.GnmyEntry`
    placements; each is drawn as a filled square centred on its pixel ``(x, y)``,
    camera-relative (``cam_x``/``cam_y`` are the viewport top-left in level
    pixels).  Colour and size come from :func:`gnmy_marker`: ``Start`` (spawn),
    ``Exit`` and ``Moneybag`` (collectable) are the three roles Q32 resolved
    **[V]**, and every other name — or a missing one — is one grey "other type"
    marker, so no meaning is invented for the unmapped names.  A marker whose
    centre is off the viewport is clipped by the buffer, not drawn.
    """
    for entry in entries:
        style = gnmy_marker(entry.name)
        sx = entry.x - cam_x
        sy = entry.y - cam_y
        d = style.size
        frame.fill_rect(sx - d // 2, sy - d // 2, d, d, style.colour)


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
    The playfield's ``GNMY`` placements are overlaid as markers styled by the
    placement's ``NMY`` name — ``Start`` (spawn), ``Exit`` and ``Moneybag``
    (collectable) distinct, every other name one grey "other type" bucket
    (Q32 **[V]**; the remaining handlers are unmapped, so nothing is invented)
    — then the player is overlaid last so camera-follow and scrolling stay
    visible.  The player is its standing ANIM sprite (decoded from the global
    ``MAIN.WLD`` bank, see :func:`lomax_modern.engine.level.load_player_sprite`),
    blitted through the ``HEAD`` palette with index-0 transparency; when that
    bank is absent (a synthetic world) the player falls back to the marker.
    """
    vw, vh = viewport
    cam_x, cam_y = camera(level, state.player, vw, vh)
    section = level.sections[level.playfield]
    plane = section.plane
    tiles = section.tiles
    cells = level.cells
    # Tiles and sprites resolve their palette indices through *different* slots:
    # tiles through the tile slot (1), ANIM sprites through the sprite slot (0).
    # See ``art.SPRITE_PALETTE_SLOT`` — the hero's true colours live in slot 0.
    tile_palette = head_palette565(section.head, DEFAULT_PALETTE_SLOT)
    sprite_palette = head_palette565(section.head, SPRITE_PALETTE_SLOT)

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
                    tile_palette,
                    cell_x * CELL_PX - cam_x,
                    cell_y * CELL_PX - cam_y,
                    layout="2x2",
                )

    overlay_gnmy(fb, level.gnmy, cam_x, cam_y)

    sprite = level.player_sprite
    moving = state.player.vx != 0.0
    if moving and level.walk_frames:
        # Walk cycle: one composited stride pose per movement tick, flipped to
        # the facing direction.  Each pose is the base+overlay composite on one
        # shared canvas (see anim_clip.resolve_poses); the canvas is anchored
        # with its bottom at the collision-box bottom and centred, the same
        # convention the standing sprite uses (docs/file-formats.md 2.6.1 [H]).
        pose = level.walk_frames[state.player.anim_frame % len(level.walk_frames)]
        pixels = pose.pixels
        if state.player.facing < 0:
            pixels = anim_clip.mirrored(pixels)
        sx = int(state.player.centre_x - pixels.width / 2) - cam_x
        sy = int(state.player.y + state.player.height - pixels.height) - cam_y
        fb.blit_sprite(pixels.indices, pixels.width, pixels.height, sprite_palette, sx, sy)
    elif sprite is None:
        # No global bank (synthetic world): fall back to the player marker so
        # camera-follow stays visible without a sprite.
        sx = int(state.player.x) - cam_x
        sy = int(state.player.y) - cam_y
        fb.fill_rect(sx, sy, state.player.width, state.player.height, COLOUR_PLAYER)
    else:
        # Standing pose: centre the sprite on the player's collision box; feet
        # at its bottom.  Flipped to the facing direction.
        if state.player.facing < 0:
            sprite = anim_clip.mirrored(sprite)
        sx = int(state.player.centre_x - sprite.width / 2) - cam_x
        sy = int(state.player.y + state.player.height - sprite.height) - cam_y
        fb.blit_sprite(sprite.indices, sprite.width, sprite.height, sprite_palette, sx, sy)

    frame = Frame(vw, vh)
    frame.pixels = fb.pixels
    return frame
