"""Engine-side world model: a ``.WLD`` loaded into a playable level.

This is the data-facing half of the engine core.  It reuses the byte-exact
``wld`` container and the ``art`` decode unchanged, and builds the grid the
simulation walks on.  It interprets nothing beyond what is measured (see
``docs/file-formats.md``); every uncertain field is carried verbatim and
flagged.

The one deliberate model here is :class:`CollisionModel`, which maps a raw
``MAP`` collision byte to its class (empty / one-way floor / conservative solid);
see the class docstring for what is [V] and what stays [H].
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from .. import art, wld
from .. import anim_clip
from ..anim_nmy import (
    AnimDecode,
    AnimPixels,
    GnmyEntry,
    anim_tag_name,
    decode_anim_pixels,
    decode_gnmy,
    decode_nmy,
    placement_role,
)

#: A ``MAP`` cell is a 16x16-pixel block (``docs/file-formats.md`` §2.4).
CELL_PX = 16

#: Collision byte returned for positions outside the map: solid, so the player
#: is bounded by the level edge.  A real in-map byte is always 0..255, so 0xFF
#: can never collide with a genuine value.
OUT_OF_BOUNDS_COLLISION = 0xFF

#: The ``NMY`` record name of the player character in ``MAIN.WLD``'s global
#: sprite bank (``Hero`` carries the 47 ``WALK``/``RUN``/``STA1``/... animations).
PLAYER_NMY_NAME = "Hero"

#: The animation tag (forward ASCII, see ``anim_nmy.anim_tag_name``) whose first
#: keyframe is the player's standing pose (``STA1`` = "stand").
PLAYER_STAND_ANIM = "STA1"

#: Row 31's idle fidget clip (§2.6.2 a/d): played once, at rate 68, when the idle
#: counter reaches the threshold and bit 0 of the random source is set [H].
PLAYER_IDLE_ANIM = "STA2"

#: The clip drawn for a grounded player with ``0 < |vx| <= 2.0``.  The original
#: selects ``WALK`` below the speed gate (``cmp |vx|, 0x20000`` / ``jg`` at VA
#: ``0x411F79``; ``docs/file-formats.md`` §2.6.2 a row 34), and 2.0 px/tick is this
#: engine's only ground speed, so this is the everyday moving clip.  Its per-step
#: layer is a whole character (10 poses; ``anim_clip.resolve_body_poses`` turns
#: it into renderable whole-body frames, ``docs/file-formats.md`` §2.6.1).
PLAYER_WALK_ANIM = "WALK"

#: The clip drawn only above 2.0 px/tick (§2.6.2 a row 35, the same ``jg``).  It
#: has 12 whole-body poses.  Nothing in the engine moves that fast yet, so it is
#: loaded into the table and counted but not drawn.
PLAYER_RUN_ANIM = "RUN"

#: The landing clip (§2.6.2 a row 26): **one pose**, drawn on the ground while
#: the landing counter ``0x59F1CC`` is non-zero — 10 ticks after a straight-jump
#: touchdown, cut to a single tick by a held left/right (``0x411D3E``).
PLAYER_LAND_ANIM = "LND1"

#: The straight kind's jump clip (row 14, state bit ``0x2`` set) and the moving
#: kind's (row 20, bit clear); the airborne player never draws a ground clip.
PLAYER_JUMP_ANIM = "JMP1"
PLAYER_JUMP_MOVING_ANIM = "JMP2"

#: The fast-fall clips (rows 18/21), on the same straight/moving split: selected
#: in the air at ``vy`` >= 2.5 px/tick, not a slow float.
PLAYER_FASTFALL_ANIM = "FLO1"
PLAYER_FASTFALL_MOVING_ANIM = "FLO2"

#: The duck clip (§2.6.2 a row 23): drawn on the ground with state bit ``0x4``,
#: one-shot, 6 poses, rate 65 [V].  The setter conditions are [H] — this engine
#: ducks while grounded and Down is held.
PLAYER_DUCK_ANIM = "DUCK"

#: The clip tags the player's table carries, in table order (the report prints
#: clips in this order): the ground clips (including ``DUCK``), the landing clip
#: and the four air clips (``docs/file-formats.md`` §2.6.2 a).  The table is
#: **keyed by tag** (see :func:`load_clip_table`), so a later slice adds a clip
#: by naming it here — ``STA2`` (AN6) needs no new loader.
PLAYER_CLIP_TAGS = (
    PLAYER_STAND_ANIM,
    PLAYER_IDLE_ANIM,
    PLAYER_WALK_ANIM,
    PLAYER_RUN_ANIM,
    PLAYER_DUCK_ANIM,
    PLAYER_LAND_ANIM,
    PLAYER_JUMP_ANIM,
    PLAYER_JUMP_MOVING_ANIM,
    PLAYER_FASTFALL_ANIM,
    PLAYER_FASTFALL_MOVING_ANIM,
)


def load_clip_table(
    main_world_path: str | Path,
    *,
    clip_tags: Sequence[str] = PLAYER_CLIP_TAGS,
) -> dict[str, tuple[anim_clip.BodyPose, ...]]:
    """Resolve each requested clip tag to its whole-body poses, in play order.

    The result is the engine's **clip table** — ``{tag: (pose, ...)}`` — keyed by
    the animation tag as :func:`lomax_modern.anim_nmy.anim_tag_name` decodes it, so
    nothing here knows a clip by identity: ``Hero``'s ``STA1`` and ``RUN`` today,
    and any tag a caller names (or a later slice adds) without touching this
    function.  Each pose is the step's **whole-body** sprite decoded to palette
    indices (:func:`lomax_modern.anim_clip.resolve_body_poses`); the contact pose
    (sprite byte ``169``, in no ``.WLD`` bank) and step 0 are dropped, as there.

    Poses are ordered for playback: the pose named by the clip's **first keyframe**
    comes first (see :func:`_play_order`), so pose index 0 means "what the clip
    starts on" for every tag.  ``STA1``'s standing frame is exactly that pose, so
    :func:`load_player_sprite` and the table cannot disagree.

    A tag the file does not carry is *absent* from the table, and a file that is
    missing or does not parse yields ``{}`` — never an exception: the renderer
    falls back, so a synthetic world still renders.
    """
    source = Path(main_world_path)
    if not source.is_file():
        return {}
    try:
        world = wld.parse_file(source)
    except (OSError, wld.WLDError):
        return {}
    table: dict[str, tuple[anim_clip.BodyPose, ...]] = {}
    for tag in clip_tags:
        poses = anim_clip.resolve_body_poses(
            world, record_name=PLAYER_NMY_NAME, clip_tag=tag
        )
        if poses:
            table[tag] = _play_order(world, tag, poses)
    return table


def _play_order(
    world: wld.World, clip_tag: str, poses: tuple[anim_clip.BodyPose, ...]
) -> tuple[anim_clip.BodyPose, ...]:
    """Rotate a step-sorted pose tuple so the clip's first keyframe comes first.

    :func:`lomax_modern.anim_clip.resolve_body_poses` returns poses in ``step``
    order and drops ``step`` 0 (the resolver draws nothing there), which loses
    the position the clip starts at.  The pose the clip's **first keyframe** names
    is the one the engine draws for a still player (``STA1``'s standing frame), so
    it is rotated to index 0 and a pose index means the same thing for every tag.
    When the first keyframe's step has no resolvable pose (``RUN``'s step 0) the
    step order is left as it is.
    """
    anim = anim_clip.find_animation(
        world, record_name=PLAYER_NMY_NAME, clip_tag=clip_tag
    )
    if anim is None or not anim.frames:
        return poses
    first_step = anim.frames[0][1]
    start = next((i for i, pose in enumerate(poses) if pose.step == first_step), 0)
    if start == 0:
        return poses
    return poses[start:] + poses[:start]


def load_player_sprite(main_world_path: str | Path) -> AnimPixels | None:
    """Decode the player's standing frame from ``MAIN.WLD``'s global bank.

    The player is the ``NMY`` record named :data:`PLAYER_NMY_NAME`; its standing
    pose is the first pose of the :data:`PLAYER_STAND_ANIM` clip in the table
    :func:`load_clip_table` builds — the clip's first keyframe names that step, so
    the standing sprite is the clip's **whole-body layer** (``STA1``: sprite byte
    27 → ``type_index`` 26, 44×47–49).  The indexed layer is returned — the caller
    applies its own ``HEAD`` palette.

    Returns ``None`` when ``MAIN.WLD`` is absent or does not resolve; the
    renderer then falls back to the player marker, so a synthetic world without
    the global bank still renders.
    """
    poses = load_clip_table(main_world_path, clip_tags=(PLAYER_STAND_ANIM,)).get(
        PLAYER_STAND_ANIM, ()
    )
    return poses[0].pixels if poses else None


#: The eight collision values level 1's playfield uses (``docs/file-formats.md``
#: §2.9.a-d).
L1_COLLISION_VALUES = (0x00, 0xC0, 0xC8, 0xD0, 0xD8, 0xE0, 0xE8, 0xF0)

_SHAPE_NAMES = ("flat", "shallow lower half", "shallow upper half", "steep")


@dataclass(frozen=True)
class CollisionModel:
    """Decode a raw ``MAP`` collision byte (``docs/file-formats.md`` §2.9.a-d).

    Class = the top two bits.  ``0`` is passable.  ``0xC0`` (top bits ``11``) is a
    one-way FLOOR surface [V]: low 3 bits are the material (ignored), bits 4-5
    the shape, bit 3 the mirror.  Every other non-zero byte (wall/ceiling class
    ``0x80``-``0xBF``, or ``0x01``-``0x7F``) stays on the conservative rule
    "solid from all sides" [H].

    Residual [H]: steep (``0xF0``) grounded behaviour (``0x410F63`` untraced),
    ``0xC8``'s bit ``0x08``, the 8-16 px collision-vs-art offset (Q52) and the
    ground-follow tolerance choice.
    """

    def kind(self, byte: int) -> str:
        """``"empty"``, ``"floor"`` or ``"solid"`` (the conservative [H] kind)."""
        if byte == 0:
            return "empty"
        if (byte & 0xC0) == 0xC0:
            return "floor"
        return "solid"

    def is_solid(self, byte: int) -> bool:
        """Whether the byte blocks from every side: only the conservative kind."""
        return self.kind(byte) == "solid"

    def one_way(self, byte: int) -> bool:
        """Whether the byte is a one-way floor [V]."""
        return self.kind(byte) == "floor"

    def floor_shape(self, byte: int) -> int:
        return (byte & 0x30) >> 4

    def floor_mirror(self, byte: int) -> bool:
        """The mirror bit; shape 0 never reads it."""
        return self.floor_shape(byte) != 0 and bool(byte & 0x08)

    def floor_kind(self, byte: int) -> int:
        """Slope kind for the landing vy gate: flat 0, shallow 1, steep 2."""
        return (0, 1, 1, 2)[self.floor_shape(byte)]

    def floor_offset(self, byte: int, xi: int) -> int:
        """Surface y inside the cell (0 = top, 16 = bottom) at ``xi = feet_x & 15``."""
        shape = self.floor_shape(byte)
        if shape == 0:
            return CELL_PX
        mirror = self.floor_mirror(byte)
        if shape == 3:
            return 15 - xi if mirror else xi
        half = xi >> 1
        if shape == 1:
            return 8 + (7 - half if mirror else half)
        return 7 - half if mirror else half

    def describe(self, byte: int) -> str:
        """A one-line class + grade label for the byte."""
        kind = self.kind(byte)
        if kind == "empty":
            return f"{byte:#04x}: empty, passable [V]"
        if kind == "solid":
            return f"{byte:#04x}: solid from all sides, conservative [H]"
        shape = self.floor_shape(byte)
        parts = ["floor", _SHAPE_NAMES[shape]]
        if shape:
            parts.append("descends left" if self.floor_mirror(byte) else "descends right")
        parts.append("one-way")
        grade = "[V]"
        if shape == 3:
            grade = "[V] surface, grounded behaviour [H]"
        elif shape == 0 and byte & 0x08:
            grade = "[V] surface, bit 0x08 [H]"
        return f"{byte:#04x}: {', '.join(parts)} {grade}"

    def report(self, extra_values: Iterable[int] = ()) -> str:
        """The multi-line ``collision:`` block."""
        lines = [
            (
                "collision: FL2 classes [V] (top bits 11 = one-way floor, 10 = "
                "wall/ceiling not implemented -> conservative solid [H], other "
                "non-zero -> conservative solid [H])"
            )
        ]
        values = list(L1_COLLISION_VALUES)
        values += sorted(v for v in set(extra_values) if v not in values)
        lines += [f"  {self.describe(v)}" for v in values]
        lines.append(
            "  still [H]: steep (0xF0) grounded behaviour (0x410F63 untraced); "
            "0xC8's bit 0x08; 8-16 px collision-vs-art offset (Q52); "
            "ground-follow tolerance choice"
        )
        return "\n".join(lines)


#: ``GNMY`` placement names that drive a backdrop plane's motion.
BACKDROP_SCROLL_NAMES = ("ScrollMap", "Parallax")


@dataclass(frozen=True)
class ParallaxSprite:
    """A backdrop ``Parallax`` placement resolved to its sprite (§2.11.c).

    ``entry`` is the placement; ``pixels`` the first keyframe of its ``NMY``
    record's ``PARA`` clip (sprite byte 1-based, sub-frame ``step - 1``);
    ``dx``/``dy`` that keyframe's signed draw offsets; ``palette_slot`` the
    ``ANIM`` chunk's ``flags & 0x7FFF`` (``docs/file-formats.md`` §2.11.e).
    """

    entry: GnmyEntry
    pixels: AnimPixels
    dx: int
    dy: int
    palette_slot: int


@dataclass(frozen=True)
class BackdropPlane:
    """A non-playfield plane the level table names; ``render_tiles`` draws it.

    ``gnmy`` is every placement of that plane; ``scroll`` the subset named
    ``ScrollMap`` or ``Parallax`` (case-sensitive, as decoded); ``parallax``
    the ``Parallax`` placements whose sprite resolved (the others are not
    drawn).
    """

    plane: int
    gnmy: tuple[GnmyEntry, ...] = ()
    scroll: tuple[GnmyEntry, ...] = ()
    parallax: tuple[ParallaxSprite, ...] = ()


#: Idle clip per ``NMY`` name prefix (first four bytes, like
#: :data:`lomax_modern.anim_nmy.PLACEMENT_ROLES`); ``docs/file-formats.md``
#: §2.12.b "Idle clip" column.  A tuple of several tags is chosen by placement
#: index parity (``Bees``: the original reads a random bit, ``0x4270B2`` -> [H]).
PLACEMENT_IDLE_CLIPS: dict[str, tuple[str, ...]] = {
    "Bees": ("EINS", "DREI"),
    "Henc": ("STAY",),
    "Rope": ("ROPE",),
    "Jump": ("PAD",),
    "Mone": ("HANG",),
    "Exit": ("EXIT",),
    "Revi": ("EINS",),
    "Loro": ("HAT",),  # the four STAR satellites are not drawn [H]
    "Thie": ("STAY",),
}

#: Names not drawn as a sprite at their placement, with the reason (§2.12.b).
PLACEMENT_HIDDEN: dict[str, str] = {
    "Gene": "invisible spawn trigger [V]",
    "Musi": "music cue [V]",
    "Ufos": "ambient spawner, its children are not placements [V]",
    "Star": "hero entry point, hidden for its first 136 ticks; Trapdoor record "
    "lives in MAIN, not drawn in this slice [H]",
    "Para": "drawn as a layer, not a sprite; playfield Parallax not drawn yet [H]",
}

#: Placement flag of an object spawned by a ``Generator`` (``Pots``' ``0x2000``
#: attaches ``ROCK``; the ``Henchlemming`` at (1018, 320) carries it) [M].
GENERATOR_SPAWNED_FLAG = 0x2000
GENERATOR_SPAWNED_REASON = "does not exist until its Generator fires [M]"
#: ``Henchlemming`` is mirrored when ``x & 0x10`` (``0x42DDA8``) [V].
MIRROR_X_BIT = 0x10
#: ``Rope`` stacks keyframe 0 ``p1`` times, ``y`` stepping by 32 (``0x42A280``) [V].
ROPE_STEP_PX = 32


@dataclass(frozen=True)
class PlacedSprite:
    """One placement layer resolved to pixels, ready to blit (load time).

    ``x``/``y`` is the layer's top-left in level pixels (``origin + (dx, dy)``,
    mirrored about the origin column when the placement is mirrored);
    ``indices`` are palette indices, already flipped, index 0 transparent.
    """

    entry: GnmyEntry
    x: int
    y: int
    width: int
    height: int
    indices: tuple[int, ...]


@dataclass(frozen=True)
class PlacementSpriteReport:
    """How the playfield's placements split into drawn / hidden / missing."""

    total: int
    drawn: int
    #: ``(name, count, reason)`` per distinct hidden name, first-seen order.
    hidden: tuple[tuple[str, int, str], ...]
    #: Placements neither drawn nor hidden by design (drawn as markers).
    missing: tuple[GnmyEntry, ...]

    @property
    def hidden_count(self) -> int:
        return sum(count for _name, count, _reason in self.hidden)

    def format(self) -> str:
        lines = [
            (
                f"sprites: {self.drawn}/{self.total} drawn, "
                f"{self.hidden_count} hidden by design, {len(self.missing)} missing"
            )
        ]
        lines += [f"  hidden: {n} x{c} — {r}" for n, c, r in self.hidden]
        return "\n".join(lines)


def _keyframe_layer(sprites, kf):
    """``(dx, dy, pixels)`` of one keyframe, or ``None`` if it does not resolve."""
    sprite, step, w2, w3, _flags = kf
    chunk = anim_clip.sprite_for(sprites, sprite)
    sub = anim_clip.frame_for_step(step, chunk.frame_count) if chunk else None
    if chunk is None or sub is None:
        return None
    pixels = decode_anim_pixels(chunk, sub)
    if pixels is None:
        return None
    return _signed16(w2), _signed16(w3), pixels


def _placement_layers(entry: GnmyEntry, anim, sprites):
    """The ``(dx, dy, pixels, y_offset)`` layers one placement draws, or ``None``."""
    frames = anim.frames
    if not frames:
        return None
    if entry.name[:4] == "Rope":
        # [H] One layer per keyframe drawn (kf 0 repeated p1 times, then kf 1),
        # not a whole pose each; kf 1 sits below the last repeat.
        p1 = entry.params[0] if entry.params else 0
        first = _keyframe_layer(sprites, frames[0])
        if first is None:
            return None
        out = [(*first, ROPE_STEP_PX * i) for i in range(p1)]
        if len(frames) > 1:
            last = _keyframe_layer(sprites, frames[1])
            if last is None:
                return None
            out.append((*last, ROPE_STEP_PX * p1))
        return out
    # Pose 0: every keyframe sharing the first keyframe's step, base layer first.
    layers = []
    for kf in frames:
        if kf[1] != frames[0][1]:
            continue
        layer = _keyframe_layer(sprites, kf)
        if layer is None:
            return None
        layers.append((*layer, 0))
    layers.sort(key=lambda lay: anim_clip._content_area(lay[2]), reverse=True)
    return layers


def resolve_placed_sprites(
    world: wld.World, entries: Sequence[GnmyEntry]
) -> tuple[tuple[PlacedSprite, ...], PlacementSpriteReport]:
    """Resolve every placement to its idle-clip sprite layers, once, at load.

    Idle clips, hidden-by-design names and the Generator-spawned rule come from
    :data:`PLACEMENT_IDLE_CLIPS` / :data:`PLACEMENT_HIDDEN`; a name in neither,
    or one whose record, clip or sprite does not resolve, is *missing* (never
    invented).  Sprites come from the world's own ``ANIM`` bank.
    """
    nmy = next((c for c in world.chunks if c.tag == "NMY"), None)
    decoded = decode_nmy(nmy.payload) if nmy is not None else None
    records: dict[str, object] = {}
    for record in decoded[0] if decoded else ():
        records.setdefault(record.name, record)
    sprites = anim_clip.sprite_map(world)

    placed: list[PlacedSprite] = []
    hidden: dict[str, list] = {}
    missing: list[GnmyEntry] = []
    drawn = 0
    for index, entry in enumerate(entries):
        prefix = (entry.name or "")[:4]
        spawned = prefix == "Pots" or (
            prefix == "Henc" and entry.flags & GENERATOR_SPAWNED_FLAG
        )
        reason = GENERATOR_SPAWNED_REASON if spawned else PLACEMENT_HIDDEN.get(prefix)
        if reason is not None:
            hidden.setdefault(entry.name, [0, reason])[0] += 1
            continue
        tags = PLACEMENT_IDLE_CLIPS.get(prefix)
        record = records.get(entry.name) if tags else None
        if record is None:
            missing.append(entry)
            continue
        tag = tags[index % len(tags)]
        anim = next((a for a in record.anims if anim_tag_name(a.tag).strip() == tag), None)
        layers = _placement_layers(entry, anim, sprites) if anim else None
        if not layers:
            missing.append(entry)
            continue
        mirrored = prefix == "Henc" and bool(entry.x & MIRROR_X_BIT)
        for dx, dy, pixels, y_off in layers:
            if mirrored:
                dx = 1 - pixels.width - dx
                pixels = anim_clip.mirrored(pixels)
            placed.append(
                PlacedSprite(
                    entry,
                    entry.x + dx,
                    entry.y + dy + y_off,
                    pixels.width,
                    pixels.height,
                    tuple(pixels.indices),
                )
            )
        drawn += 1
    report = PlacementSpriteReport(
        total=len(entries),
        drawn=drawn,
        hidden=tuple((n, c, r) for n, (c, r) in hidden.items()),
        missing=tuple(missing),
    )
    return tuple(placed), report


@dataclass(frozen=True)
class Level:
    """One world file loaded for play.

    ``playfield`` selects which of the world's planes is the walkable grid.
    The plane → level mapping lives in the executable's section table (Q3),
    which only the CLI reads (``exe_tables``); this module takes plane numbers
    from its caller, so the default is the first plane.
    """

    name: str
    path: Path
    sections: tuple[art.PlaneSection, ...]
    cells: tuple[art.Cell, ...]
    palette: art.Palette
    playfield: int
    collision: CollisionModel
    #: The playfield plane's ``GNMY`` placements, decoded from the ``GNMY``
    #: chunk that follows that plane's ``MAP``.  Each entry carries its pixel
    #: position, ``type_index`` and the resolved ``NMY`` record ``name`` (Q32
    #: **[V]**: ``Start`` = spawn, ``Exit`` = level exit, ``Moneybag`` =
    #: collectable; every other name is unmapped).
    gnmy: tuple[GnmyEntry, ...] = ()
    #: The player's standing frame as palette indices, decoded from the global
    #: ``MAIN.WLD`` sprite bank (see :func:`load_player_sprite`).  ``None``
    #: when the bank is absent (synthetic worlds); the renderer then falls back
    #: to the player marker.
    player_sprite: AnimPixels | None = None
    #: The player's clip table: animation tag -> its whole-body poses in play
    #: order (see :func:`load_clip_table`).  Query it through
    #: :meth:`clip_pose`; :func:`lomax_modern.engine.state.select_clip` names the
    #: ``(tag, pose index)`` pair, so the render path holds no sprite id.  Empty
    #: when ``MAIN.WLD`` is absent or the clips do not resolve; the renderer then
    #: falls back to the standing sprite, and to the marker without that.
    clips: dict[str, tuple[anim_clip.BodyPose, ...]] = field(default_factory=dict)
    #: Backdrop planes requested from :func:`load_level`, decoded only.
    backdrops: tuple[BackdropPlane, ...] = ()
    #: Playfield placements resolved to idle-clip sprite layers
    #: (:func:`resolve_placed_sprites`); empty for a level built without a world.
    placed_sprites: tuple[PlacedSprite, ...] = ()
    #: The drawn / hidden / missing split; ``None`` when not resolved.
    placement_report: PlacementSpriteReport | None = None

    def marker_entries(self) -> tuple[GnmyEntry, ...]:
        """Placements still drawn as grey markers (all of them if unresolved)."""
        if not self.placed_sprites or self.placement_report is None:
            return self.gnmy
        return self.placement_report.missing

    def clip_pose(self, tag: str, pose_index: int) -> anim_clip.BodyPose | None:
        """The pose ``pose_index`` of the clip ``tag``, cycling over its poses.

        ``None`` when the table carries no such clip (or the clip resolved to no
        pose), which is the renderer's cue to fall back rather than to invent
        art.  The index is reduced modulo the clip's length, so a caller such as
        :func:`lomax_modern.engine.state.select_clip` may return the raw
        animation frame counter.
        """
        poses = self.clips.get(tag, ())
        if not poses:
            return None
        return poses[pose_index % len(poses)]

    @property
    def plane(self) -> art.MapPlane:
        return self.sections[self.playfield].plane

    @property
    def width_px(self) -> int:
        return self.plane.width_cells * CELL_PX

    @property
    def height_px(self) -> int:
        return self.plane.height_cells * CELL_PX

    def collision_at(self, cell_x: int, cell_y: int) -> int:
        """The raw collision byte at a cell, or a solid sentinel off-map."""
        if not (0 <= cell_x < self.plane.width_cells and 0 <= cell_y < self.plane.height_cells):
            return OUT_OF_BOUNDS_COLLISION
        return self.plane.at(cell_x, cell_y).collision

    def solid_at(self, cell_x: int, cell_y: int) -> bool:
        """Conservative-solid cell; off-map is solid (the byte 0xFF is a floor now)."""
        if not (0 <= cell_x < self.plane.width_cells and 0 <= cell_y < self.plane.height_cells):
            return True
        return self.collision.is_solid(self.collision_at(cell_x, cell_y))

    def floor_at(self, feet_x: int, feet_y: int, rows: int = 4) -> tuple[int, int] | None:
        """Floor probe (original ``0x413B90``): ``(surface_y, kind)`` or ``None``.

        Column ``feet_x >> 4``; scans down at most ``rows`` rows from
        ``max(0, (feet_y - 16) // 16)``; the first floor-class cell wins.
        """
        if feet_y < CELL_PX or not (0 <= feet_x < self.width_px):
            return None
        cell_x = feet_x >> 4
        first = max(0, (feet_y - CELL_PX) // CELL_PX)
        for row in range(first, min(first + rows, self.plane.height_cells)):
            byte = self.collision_at(cell_x, row)
            if self.collision.one_way(byte):
                offset = self.collision.floor_offset(byte, feet_x & 15)
                return row * CELL_PX + offset, self.collision.floor_kind(byte)
        return None

    def solid_px(self, px_x: int, px_y: int) -> bool:
        return self.solid_at(px_x // CELL_PX, px_y // CELL_PX)

    def passable(self, cell_x: int, cell_y: int) -> bool:
        return not self.solid_at(cell_x, cell_y)

    @property
    def spawn(self) -> tuple[int, int] | None:
        """Pixel ``(x, y)`` of the playfield's ``Start`` placement (Q32 **[V]**).

        ``None`` when the plane carries no ``Start`` placement (or its ``NMY``
        table is missing), in which case a caller falls back to the first
        passable cell.  A level has at most one spawn; if several ``Start``
        placements exist the first in file order wins.
        """
        for entry in self.gnmy:
            if placement_role(entry.name) == "start":
                return entry.x, entry.y
        return None

    @property
    def collectables(self) -> tuple[tuple[int, int], ...]:
        """Pixel ``(x, y)`` of every ``Moneybag`` placement, in file order."""
        return tuple(
            (entry.x, entry.y)
            for entry in self.gnmy
            if placement_role(entry.name) == "moneybag"
        )

    @property
    def exits(self) -> tuple[tuple[int, int], ...]:
        """Pixel ``(x, y)`` of every ``Exit`` placement, in file order."""
        return tuple(
            (entry.x, entry.y)
            for entry in self.gnmy
            if placement_role(entry.name) == "exit"
        )

    @property
    def revives(self) -> tuple[tuple[int, int], ...]:
        """Pixel ``(x, y)`` of every ``Revive`` placement, in file order."""
        return tuple(
            (entry.x, entry.y)
            for entry in self.gnmy
            if placement_role(entry.name) == "revive"
        )


def _decode_gnmy_per_plane(world: wld.World) -> tuple[tuple[GnmyEntry, ...], ...]:
    """Decode each plane's ``GNMY`` placements, one tuple per plane, in order.

    A ``GNMY`` chunk belongs to the plane whose ``HEAD`` precedes it (retail
    order ``HEAD, TTAB, MAP, GNMY`` repeats once per plane).  The entry layout
    is recovered and graded ``[V]`` in ``docs/file-formats.md`` §2.5, and each
    entry's ``name`` is resolved from the world's ``NMY`` table (Q32 **[V]**:
    ``Start`` = spawn, ``Exit`` = level exit, ``Moneybag`` = collectable; the
    remaining names are unmapped, so no other meaning is attached).

    A missing ``NMY``/``GNMY`` (or one that does not parse under the recovered
    framing) yields an empty tuple for that plane rather than raising: markers
    are a diagnostic overlay, never a parse gate.
    """
    nmy_chunk = next((c for c in world.chunks if c.tag == "NMY"), None)
    k_of: dict[int, int] = {}
    names: tuple[str, ...] = ()
    if nmy_chunk is not None:
        result = decode_nmy(nmy_chunk.payload)
        if result is not None:
            records, _ = result
            k_of = {i: (record.flags >> 4) & 0xF for i, record in enumerate(records)}
            names = tuple(record.name for record in records)

    per_plane: list[list[GnmyEntry]] = []
    plane_index = -1
    in_plane = False
    for chunk in world.chunks:
        if chunk.tag == "HEAD":
            plane_index += 1
            in_plane = True
            per_plane.append([])
        elif chunk.tag == "GNMY" and in_plane:
            decoded = decode_gnmy(chunk.payload, k_of)
            if decoded is not None:
                per_plane[plane_index].extend(
                    replace(entry, name=names[entry.type_index])
                    if entry.type_index < len(names)
                    else entry
                    for entry in decoded[0]
                )
    return tuple(tuple(entries) for entries in per_plane)


def _signed16(word: int) -> int:
    """A little-endian ``u16`` read back as signed."""
    return word - 0x10000 if word & 0x8000 else word


def _resolve_parallax(
    world: wld.World,
    entries: Iterable[GnmyEntry],
    sprites: dict[int, AnimDecode],
) -> tuple[ParallaxSprite, ...]:
    """Resolve each ``Parallax`` placement's ``PARA`` clip, first keyframe.

    Same helpers as :func:`lomax_modern.anim_clip.resolve_clip`; a placement
    whose record, clip, sprite byte or step does not resolve is left out.
    """
    out: list[ParallaxSprite] = []
    for entry in entries:
        if entry.name != "Parallax":
            continue
        anim = anim_clip.find_animation(world, record_name=entry.name, clip_tag="PARA")
        if anim is None or not anim.frames:
            continue
        sprite, step, w2, w3, _flags = anim.frames[0]
        chunk = anim_clip.sprite_for(sprites, sprite)
        sub = anim_clip.frame_for_step(step, chunk.frame_count) if chunk else None
        if chunk is None or sub is None:
            continue
        pixels = decode_anim_pixels(chunk, sub)
        if pixels is None:
            continue
        out.append(
            ParallaxSprite(entry, pixels, _signed16(w2), _signed16(w3), chunk.flags & 0x7FFF)
        )
    return tuple(out)


def load_level(
    path: str | Path,
    *,
    playfield: int = 0,
    backdrop_planes: Sequence[int] = (),
    collision: CollisionModel | None = None,
) -> Level:
    """Load a ``.WLD`` into a :class:`Level`.

    Decodes the ``CELL`` bank and the ``HEAD`` palette (default slot 1, the
    ``[H]`` choice documented in ``art``) so the level carries the art needed
    to render, alongside the collision grid the simulation walks on.  It also
    decodes the playfield plane's ``GNMY`` placements into ``Level.gnmy``,
    resolving each entry's ``NMY`` record name (Q32 **[V]**: ``Start`` = spawn,
    ``Exit`` = level exit, ``Moneybag`` = collectable; every other name is
    unmapped).
    """
    source = Path(path)
    world = wld.parse_file(source)
    sections = art.planes(world)
    if not sections:
        raise art.ArtError(f"{source.name} has no planes (HEAD/TTAB/MAP)")

    cell_chunk = next((c for c in world.chunks if c.tag == "CELL"), None)
    cells = art.decode_cells(cell_chunk) if cell_chunk is not None else ()
    palette = art.head_palette(sections[0].head, art.DEFAULT_PALETTE_SLOT)

    if not 0 <= playfield < len(sections):
        raise art.ArtError(
            f"playfield plane {playfield} is out of range for {len(sections)} planes"
        )

    gnmy_planes = _decode_gnmy_per_plane(world)
    gnmy = gnmy_planes[playfield] if playfield < len(gnmy_planes) else ()

    backdrops: list[BackdropPlane] = []
    sprites = anim_clip.sprite_map(world) if backdrop_planes else {}
    for plane in backdrop_planes:
        if not 0 <= plane < len(sections):
            raise art.ArtError(
                f"backdrop plane {plane} is out of range for {len(sections)} planes"
            )
        entries = gnmy_planes[plane] if plane < len(gnmy_planes) else ()
        backdrops.append(
            BackdropPlane(
                plane=plane,
                gnmy=entries,
                scroll=tuple(e for e in entries if e.name in BACKDROP_SCROLL_NAMES),
                parallax=_resolve_parallax(world, entries, sprites),
            )
        )

    # One decode of the global bank feeds both the clip table and the standing
    # sprite, which is the table's ``STA1`` pose — they cannot disagree.
    placed, placement_report = resolve_placed_sprites(world, gnmy)
    clips = load_clip_table(source.parent / "MAIN.WLD")
    stand_poses = clips.get(PLAYER_STAND_ANIM, ())

    return Level(
        name=source.stem,
        path=source,
        sections=sections,
        cells=cells,
        palette=palette,
        playfield=playfield,
        collision=collision or CollisionModel(),
        gnmy=gnmy,
        player_sprite=stand_poses[0].pixels if stand_poses else None,
        clips=clips,
        backdrops=tuple(backdrops),
        placed_sprites=placed,
        placement_report=placement_report,
    )
