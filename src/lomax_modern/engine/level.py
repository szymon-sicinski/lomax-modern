"""Engine-side world model: a ``.WLD`` loaded into a playable level.

This is the data-facing half of the engine core.  It reuses the byte-exact
``wld`` container and the ``art`` decode unchanged, and builds the grid the
simulation walks on.  It interprets nothing beyond what is measured (see
``docs/file-formats.md``); every uncertain field is carried verbatim and
flagged.

The one deliberate model here is :class:`CollisionModel`, which maps a raw
``MAP`` collision byte to solidity.  It is a labelled hypothesis, not a claim:
see the class docstring.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from .. import art, wld
from .. import anim_clip
from ..anim_nmy import (
    AnimPixels,
    GnmyEntry,
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


@dataclass(frozen=True)
class CollisionModel:
    """Map a raw ``MAP`` collision byte to gameplay solidity.

    The ``N`` collision bytes that follow the ``N`` tile words are preserved
    verbatim; their per-value
    semantics are **unresolved** (Q31).  The only robust invariant measured
    across all 104 retail planes is *0 vs non-zero*: byte ``0`` is passable and
    every non-zero byte is treated as solid.  That rule is a **hypothesis [H]**,
    printed as such and never asserted as the game's own collision.

    The documented third-party bit-field ``[D]`` (``0x80`` solid, ``0xC0``
    one-way, ``0x08``/``0x10``/``0x20`` directional) is **retracted**: the
    measured histogram of the byte is near-uniform over all 256 values (with
    ``0x00`` dominant and ``0x01`` the clear second), which a flag byte would
    not produce.  See ``docs/file-formats.md`` §2.4 and Q31.
    """

    def is_solid(self, byte: int) -> bool:
        """Whether the byte blocks movement from any side (``[H]`` non-zero)."""
        return byte != 0

    def one_way(self, byte: int) -> bool:
        """Whether the byte is a one-way platform.  Unknown; never guessed."""
        return False

    def report(self) -> str:
        """One-line statement of what is used and what is flagged unknown."""
        return (
            "collision: byte 0 = passable, non-zero = solid [H]; per-value "
            "semantics (material/one-way/hazard) unresolved (Q31); the "
            "documented [D] bit-field is retracted"
        )


#: ``GNMY`` placement names that drive a backdrop plane's motion.
BACKDROP_SCROLL_NAMES = ("ScrollMap", "Parallax")


@dataclass(frozen=True)
class BackdropPlane:
    """A non-playfield plane the level table names, decoded only (never drawn).

    ``gnmy`` is every placement of that plane; ``scroll`` the subset named
    ``ScrollMap`` or ``Parallax`` (case-sensitive, as decoded).
    """

    plane: int
    gnmy: tuple[GnmyEntry, ...] = ()
    scroll: tuple[GnmyEntry, ...] = ()


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
        return self.collision.is_solid(self.collision_at(cell_x, cell_y))

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
            )
        )

    # One decode of the global bank feeds both the clip table and the standing
    # sprite, which is the table's ``STA1`` pose — they cannot disagree.
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
    )
