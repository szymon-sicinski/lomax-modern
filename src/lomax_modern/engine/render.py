"""16-bit ``B5G6R5`` framebuffer and the engine's two render paths.

:func:`render_tiles` composes the visible tile art: it walks the visible
``MAP`` cells, resolves each ``tile_word`` to a ``TTAB`` record, blits the
record's four ``CELL`` blocks (flips applied) with the ``HEAD`` palette and
index-0 transparency into the 320x240 viewport, overlays the playfield's
``GNMY`` placements as markers styled by the placement's ``NMY`` name
(``Start``/``Exit``/``Moneybag`` distinct, every other name one grey "other
type" bucket — Q32 **[V]**), and finally the player — a pose from the level's
clip table, chosen by the pure selector for every case (``STA1`` standing,
``WALK``/``RUN`` by ``|vx|`` on the ground, ``LND1`` after a straight landing,
``JMP1``/``JMP2``/``FLO1``/``FLO2`` in the air), falling back to the marker when
the ``MAIN.WLD`` bank is absent — so the camera-follow and scrolling are visible.
:func:`render` remains the
*geometric* debug path: every non-zero collision cell is drawn in one colour
and the player/entities as markers, with the unresolved bits (Q31) flagged in
the report rather than painted.

Two placements stay hypotheses and are rendered exactly as
:mod:`lomax_modern.renderer` blits them, so a wrong assumption shows up in the
output instead of hiding: the four cells of a ``TTAB`` record are assembled in
the verified 2x2 column-major order (``[V]``, G1) and the flip-axis pairing (``0x2000``
horizontal / ``0x4000`` vertical) is ``[V]`` (Q33, ``docs/file-formats.md`` §2.8).

``Frame`` is a genuine 16-bit buffer: pixels are packed ``B5G6R5`` and
``to_bytes()`` emits little-endian ``u16`` words suitable for a 16-bit surface.
"""

from __future__ import annotations

import struct
import weakref
from dataclasses import dataclass

from ..anim_nmy import placement_role
from .. import anim_clip
from ..art import DEFAULT_PALETTE_SLOT, PALETTE_SLOT_COUNT, SPRITE_PALETTE_SLOT
from ..renderer import Framebuffer, head_palette565
from .entities import Player
from .level import CELL_PX, Level
from .state import GameState, select_clip

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
    return GNMY_MARKER_STYLES.get(placement_role(name), GNMY_MARKER_STYLES["other"])


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


def pose_origin(player: Player) -> tuple[int, int]:
    """Origin column/row the original places poses on (AN3's chosen mapping).

    A **choice**, not a finding [H]: the column is the collision box's
    horizontal centre, the row is its last row (the feet row).
    ``docs/file-formats.md`` §2.6.2 c.
    """
    return int(player.centre_x), int(player.y + player.height - 1)


def pose_top_left(player: Player, pose: anim_clip.BodyPose) -> tuple[int, int]:
    """Top-left of a pose's drawn layer, in level pixels (y down).

    ``origin + (dx, dy)``; facing -x mirrors about the origin column,
    ``dx' = 1 - w - dx`` (``0x40C696``).  ``dy`` is applied as-is.
    """
    dx = pose.dx if player.facing >= 0 else 1 - pose.pixels.width - pose.dx
    ox, oy = pose_origin(player)
    return ox + dx, oy + pose.dy


#: ``ScrollMap``/``Parallax`` drift parameters are hundredths of a pixel per
#: tick, stored as ``p * 655`` in 16.16 fixed point (VA ``0x42B727``-``0x42B768``,
#: ``0x42D531``-``0x42D57B``; ``docs/file-formats.md`` §2.11.b/c [V]).
DRIFT_16_16 = 655

#: Marks a transparent pixel in a pre-rendered backdrop bitmap (not a colour word).
_CLEAR = -1


def trunc_div(a: int, b: int) -> int:
    """Integer ``a / b`` truncating toward zero, like x86 ``idiv`` (§2.11.b).

    Python's ``//`` floors, which differs for a negative quotient.
    """
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _s16(word: int) -> int:
    return word - 0x10000 if word & 0x8000 else word


def _params(entry, count: int = 7) -> tuple[int, ...]:
    """A placement's params as signed words, zero-padded to ``count``."""
    values = [_s16(p) for p in entry.params]
    return tuple(values + [0] * (count - len(values)))


def scroll_map_params(plane) -> tuple[int, ...] | None:
    """The default ``ScrollMap`` placement's params, or ``None`` (fixed plane).

    [H] The variant-key rule (§2.11.b: sub-level + 10 * section + 11 against
    p6) is NOT implemented.  Placements with flags bit 0 are the keyed
    variants (L1's planes 11/12 carry three each), so the first placement
    *without* bit 0 is used (the default, which L1 uses); a plane whose
    placements all carry bit 0 falls back to the first one.
    """
    found = [e for e in plane.scroll if e.name == "ScrollMap"]
    if not found:
        return None
    default = next((e for e in found if not e.flags & 1), found[0])
    return _params(default)


def backdrop_plane_origin(plane, cam_x: int, cam_y: int, ticks: int) -> tuple[int, int]:
    """``plane.x/y`` of a backdrop plane (``ScrollMap`` draw ``0x42B7E0``, [V]).

    ``plane.x = cam.x * p1 / 100 + offset_x`` and ``plane.y = cam.y * p3 / 100 +
    offset_y`` with truncating division; the offsets start at ``p4``/``p5`` and
    drift by ``p0``/``p2`` * 655 in 16.16 per tick (integer part = ``acc >> 16``).
    [H] A plane with no ``ScrollMap`` placement stays at (0, 0): nothing in the
    code writes its scroll.
    """
    p = scroll_map_params(plane)
    if p is None:
        return 0, 0
    off_x = ((p[4] << 16) - ticks * p[0] * DRIFT_16_16) >> 16
    off_y = ((p[5] << 16) - ticks * p[2] * DRIFT_16_16) >> 16
    return trunc_div(cam_x * p[1], 100) + off_x, trunc_div(cam_y * p[3], 100) + off_y


class _Bitmap:
    """A pre-rendered RGB565 bitmap: per-row words plus opaque ``(a, b)`` runs."""

    def __init__(self, width: int, height: int, rows: list[list[int]]) -> None:
        self.width = width
        self.height = height
        self.rows = rows
        self.runs: list[list[tuple[int, int]]] = []
        for row in rows:
            runs: list[tuple[int, int]] = []
            start = -1
            for x, word in enumerate(row):
                if word != _CLEAR:
                    if start < 0:
                        start = x
                elif start >= 0:
                    runs.append((start, x))
                    start = -1
            if start >= 0:
                runs.append((start, width))
            self.runs.append(runs)
        self.empty = not any(self.runs)


def _composite(
    pix: list[int],
    vw: int,
    vh: int,
    bm: _Bitmap,
    ox: int,
    oy: int,
    wrap_x: bool,
    wrap_y: bool,
) -> None:
    """Draw ``bm`` into ``pix``: screen pixel ``(sx, sy)`` shows bitmap pixel
    ``(sx + ox, sy + oy)`` (modulo the size on a wrapping axis, absent outside
    it otherwise).  Opaque runs are copied with slice assignment; copies at
    ``a - ox + k * W`` handle the horizontal wrap.
    """
    width, height = bm.width, bm.height
    for sy in range(vh):
        by = sy + oy
        if wrap_y:
            by %= height
        elif not 0 <= by < height:
            continue
        runs = bm.runs[by]
        if not runs:
            continue
        src = bm.rows[by]
        base = sy * vw
        for a, b in runs:
            n = b - a
            s0 = a - ox
            s = s0 + ((-(s0 + n)) // width + 1) * width if wrap_x else s0
            while s < vw:
                lo = max(0, s)
                hi = min(vw, s + n)
                if lo < hi:
                    pix[base + lo : base + hi] = src[a + lo - s : a + hi - s]
                if not wrap_x:
                    break
                s += width


def _tile_slot(record, cells) -> int:
    """Palette nibble of a record's last non-empty cell (``0x41561D``, §2.11.e [V]).

    Non-empty = index in range and not all-transparent; none -> the default slot.
    """
    slot = DEFAULT_PALETTE_SLOT
    for cell_slot in record.slots:
        if 0 <= cell_slot.index < len(cells) and any(cells[cell_slot.index].pixels):
            slot = cell_slot.palette
    return slot if slot < PALETTE_SLOT_COUNT else DEFAULT_PALETTE_SLOT


def backdrop_tile_slots(level: Level, plane_number: int) -> tuple[int, ...]:
    """The sorted palette slots a backdrop plane's drawn tile records use."""
    section = level.sections[plane_number]
    cells = level.cells
    used = {
        section.plane.at(x, y).tile_word
        for y in range(section.plane.height_cells)
        for x in range(section.plane.width_cells)
    }
    slots = set()
    for word in used:
        if not 0 <= word < len(section.tiles):
            continue
        record = section.tiles[word]
        if any(0 <= s.index < len(cells) and any(cells[s.index].pixels) for s in record.slots):
            slots.add(_tile_slot(record, cells))
    return tuple(sorted(slots))


def _build_tile_bitmap(level: Level, plane_number: int, palettes) -> _Bitmap:
    """Pre-render one backdrop plane's tiles (each record in its own slot)."""
    section = level.sections[plane_number]
    plane = section.plane
    width, height = plane.width_cells * CELL_PX, plane.height_cells * CELL_PX
    fb = Framebuffer(width, height, fill=_CLEAR)
    for cy in range(plane.height_cells):
        for cx in range(plane.width_cells):
            word = plane.at(cx, cy).tile_word
            if not 0 <= word < len(section.tiles):
                continue
            record = section.tiles[word]
            fb.blit_tile(
                record,
                level.cells,
                palettes(_tile_slot(record, level.cells)),
                cx * CELL_PX,
                cy * CELL_PX,
                layout="2x2",
            )
    rows = [fb.pixels[y * width : (y + 1) * width] for y in range(height)]
    return _Bitmap(width, height, rows)


def _build_sky_bitmap(sprite, period_x: int, period_y: int, palette) -> _Bitmap:
    """The periodic sky bitmap: the sprite copies painted with overlap, k ascending.

    A period of 0 on an axis means "draw once": that axis is the sprite's own
    extent with the sprite at 0 (the keyframe offset goes into the screen offset).
    """
    pixels = sprite.pixels
    w, h = pixels.width, pixels.height
    bw = period_x if period_x > 0 else w
    bh = period_y if period_y > 0 else h
    words = [_CLEAR if i == 0 else palette.word(i) for i in range(256)]
    rows = [[_CLEAR] * bw for _ in range(bh)]

    def origins(period: int, kd: int, size: int) -> list[int]:
        if period <= 0:
            return [0]
        reach = (abs(kd) + size) // period + 2
        return [
            x0
            for k in range(-reach, reach + 1)
            if (x0 := kd + k * period) < period and x0 + size > 0
        ]

    for y0 in origins(period_y, sprite.dy, h):
        for x0 in origins(period_x, sprite.dx, w):
            for sy in range(h):
                y = y0 + sy
                if not 0 <= y < bh:
                    continue
                line = pixels.indices[sy * w : (sy + 1) * w]
                dst = rows[y]
                for sx, index in enumerate(line):
                    x = x0 + sx
                    if index and 0 <= x < bw:
                        dst[x] = words[index]
    return _Bitmap(bw, bh, rows)


class BackdropCache:
    """Pre-rendered backdrop layers of one :class:`Level`, back to front.

    Built once (:func:`backdrop_cache`); :meth:`draw` then composites per row.
    """

    def __init__(self, level: Level) -> None:
        head = level.sections[level.playfield].head
        palettes: dict[int, object] = {}

        def palette(slot: int):
            if slot not in palettes:
                palettes[slot] = head_palette565(head, slot)
            return palettes[slot]

        #: ``("tiles", plane, bitmap)`` / ``("sky", plane, sprite, bitmap)``
        self.layers: list[tuple] = []
        # §2.11.a: the plane with the lowest depth is drawn first, i.e. the
        # reverse of the ``backdrop`` tuple; a plane's Parallax follows its tiles.
        for plane in reversed(level.backdrops):
            bitmap = _build_tile_bitmap(level, plane.plane, palette)
            if not bitmap.empty:
                self.layers.append(("tiles", plane, bitmap))
            for sprite in plane.parallax:
                p = _params(sprite.entry, 6)
                slot = sprite.palette_slot
                if slot >= PALETTE_SLOT_COUNT:
                    slot = SPRITE_PALETTE_SLOT
                sky = _build_sky_bitmap(sprite, max(p[0], 0), max(p[1], 0), palette(slot))
                if not sky.empty:
                    self.layers.append(("sky", plane, sprite, sky))

    def draw(self, fb: Framebuffer, cam_x: int, cam_y: int, ticks: int) -> None:
        pix, vw, vh = fb.pixels, fb.width, fb.height
        for layer in self.layers:
            plane = layer[1]
            px, py = backdrop_plane_origin(plane, cam_x, cam_y, ticks)
            if layer[0] == "tiles":
                _composite(pix, vw, vh, layer[2], px, py, True, True)
                continue
            sprite, bm = layer[2], layer[3]
            ox, oy = _sky_offsets(sprite, px, py, ticks)
            _composite(pix, vw, vh, bm, ox, oy, _periodic(sprite, 0), _periodic(sprite, 1))


def _periodic(sprite, axis: int) -> bool:
    return _params(sprite.entry, 6)[axis] > 0


def _sky_offsets(sprite, plane_x: int, plane_y: int, ticks: int) -> tuple[int, int]:
    """Bitmap offsets of a sky layer (``Parallax`` draw ``0x42D6B0``, §2.11.c).

    Grid origin = ``placement + drift - plane * ratio / 100`` reduced modulo the
    period; p6/p7 and the placement flags' sway/lift (bits 0/1; clear in L1)
    are ignored [H].
    """
    p = _params(sprite.entry, 6)
    entry = sprite.entry
    x_int = entry.x + ((ticks * p[2] * DRIFT_16_16) >> 16)
    y_int = entry.y + ((ticks * p[4] * DRIFT_16_16) >> 16)
    gx = x_int - trunc_div(plane_x * p[3], 100)
    gy = y_int - trunc_div(plane_y * p[5], 100)
    if p[0] > 0:
        ox = -(gx % p[0])
    else:
        ox = -(gx + sprite.dx)
    if p[1] > 0:
        oy = -(gy % p[1])
    else:
        oy = -(gy + sprite.dy)
    return ox, oy


_CACHES: dict[int, tuple[weakref.ref, BackdropCache]] = {}


def backdrop_cache(level: Level) -> BackdropCache:
    """The level's :class:`BackdropCache`, built on first use (by identity).

    ``Level`` is frozen and unhashable (it holds a dict), so the cache is a
    module-level map keyed by ``id(level)`` and dropped by a weakref callback.
    """
    key = id(level)
    hit = _CACHES.get(key)
    if hit is not None and hit[0]() is level:
        return hit[1]
    cache = _build_backdrop_cache(level)
    _CACHES[key] = (weakref.ref(level, lambda _r, k=key: _CACHES.pop(k, None)), cache)
    return cache


def _build_backdrop_cache(level: Level) -> BackdropCache:
    return BackdropCache(level)


def backdrop_report(level: Level) -> str:
    """The ``backdrop:`` block of the slice report; empty without backdrops."""
    if not level.backdrops:
        return ""
    lines: list[str] = []
    fixed = variants = False
    for plane in reversed(level.backdrops):
        n = plane.plane
        slots = backdrop_tile_slots(level, n)
        p = scroll_map_params(plane)
        if not slots:
            tiles = "tiles (empty)"
        else:
            tag = ",".join(str(s) for s in slots)
            if p is None:
                fixed = True
                tiles = f"tiles, fixed at (0, 0) [H], tile slot {tag} [V]"
            else:
                drift = f", drift {p[0]}/{p[2]}" if p[0] or p[2] else ""
                tiles = (
                    f"tiles, scroll {p[1]}%/{p[3]}% {p[4]:+d}/{p[5]:+d}{drift}, "
                    f"tile slot {tag} [V]"
                )
        if sum(1 for e in plane.scroll if e.name == "ScrollMap") > 1:
            variants = True
        lines.append(f"backdrop plane {n}: {tiles}")
        for sprite in plane.parallax:
            q = _params(sprite.entry, 6)
            lines.append(
                f"backdrop plane {n}: sky Parallax, {q[0]}x{q[1]} period, "
                f"drift {q[2]}/100 px/tick, ratio {q[3]}%/{q[5]}%, "
                f"palette slot {sprite.palette_slot} [V]"
            )
        missed = sum(1 for e in plane.scroll if e.name == "Parallax") - len(plane.parallax)
        if missed:
            lines.append(
                f"backdrop plane {n}: {missed} Parallax placement(s) unresolved "
                "(no PARA sprite) -> placeholder fill [H]"
            )
    if fixed:
        lines.append("backdrop: plane without ScrollMap stays fixed at (0, 0) [H]")
    if variants:
        lines.append(
            "backdrop: several ScrollMap placements -> default (flags bit 0 "
            "clear) used; variant-key rule not implemented [H]"
        )
    lines.append(
        "backdrop: palette set = playfield HEAD (original's mask A not threaded "
        "through; equals it in L1) [H]"
    )
    lines.append("backdrop: not drawn: playfield Parallax, Birds [H]")
    return "\n".join(lines)


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
    visible.  The player is drawn from the level's **clip table**
    (:meth:`lomax_modern.engine.level.Level.clip_pose`): the pure
    :func:`lomax_modern.engine.state.select_clip` names a ``(tag, pose index)``
    pair and the table resolves it to a whole-body pose (standing ``STA1``,
    ``WALK``/``RUN`` by ``|vx|`` on the ground, ``LND1`` after a straight
    landing, ``JMP1``/``JMP2``/``FLO1``/``FLO2`` in the air), blitted through the
    ``HEAD`` palette with index-0 transparency.  A world without the global bank
    (a synthetic world) falls back to the marker.
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
    if level.backdrops:
        # Backdrop planes (and their sky) go under the playfield, back to front.
        backdrop_cache(level).draw(fb, cam_x, cam_y, state.tick_count)
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

    # Clip choice is data: the pure selector names a (tag, pose index) pair, the
    # level's clip table resolves it to a whole-body pose.  No branch per clip
    # lives here, so AN4's air states / AN5's duck / AN6's idle change the
    # selector, not this function.
    tag, pose_index = select_clip(state.player)
    pose = level.clip_pose(tag, pose_index)
    if pose is not None:
        # One whole-body sprite per pose (anim_clip.resolve_body_poses).  The
        # clip stores a single facing (+x), so left is a horizontal flip of the
        # pixels.  Placement is the original's verified rule: top-left =
        # origin + (dx, dy), y down, mirrored about the origin column for
        # facing -x, dy applied as-is on top of the physics y
        # (docs/file-formats.md 2.6.2 c [V]).  The origin itself is this
        # engine's chosen mapping -- see pose_origin.
        pixels = pose.pixels
        if state.player.facing < 0:
            pixels = anim_clip.mirrored(pixels)
        sx, sy = pose_top_left(state.player, pose)
        sx -= cam_x
        sy -= cam_y
        fb.blit_sprite(pixels.indices, pixels.width, pixels.height, sprite_palette, sx, sy)
    elif (sprite := level.player_sprite) is not None:
        # The clip table has no pose for the chosen tag (a world whose MAIN.WLD
        # lacks the clip): reuse the standing sprite rather than inventing art.
        # No dx/dy here, so this and the marker path keep their centred /
        # bottom-pinned placement.
        # Standing pose: centre the sprite on the player's collision box; feet at
        # its bottom.  Flipped to the facing direction.
        if state.player.facing < 0:
            sprite = anim_clip.mirrored(sprite)
        sx = int(state.player.centre_x - sprite.width / 2) - cam_x
        sy = int(state.player.y + state.player.height - sprite.height) - cam_y
        fb.blit_sprite(sprite.indices, sprite.width, sprite.height, sprite_palette, sx, sy)
    else:
        # No global bank (synthetic world): fall back to the player marker so
        # camera-follow stays visible without a sprite.
        sx = int(state.player.x) - cam_x
        sy = int(state.player.y) - cam_y
        fb.fill_rect(sx, sy, state.player.width, state.player.height, COLOUR_PLAYER)

    frame = Frame(vw, vh)
    frame.pixels = fb.pixels
    return frame
