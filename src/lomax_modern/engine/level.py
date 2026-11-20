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

from dataclasses import dataclass, replace
from pathlib import Path

from .. import art, wld
from .. import anim_clip
from ..anim_nmy import (
    AnimPixels,
    GnmyEntry,
    anim_tag_name,
    decode_anim,
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

#: The animation tag whose keyframes drive the player's walk cycle.  Each of its
#: keyframes references an ``ANIM`` chunk (the hero's leg sub-sprites) plus a
#: signed draw offset and a flip flag; ``anim_clip.resolve_clip`` turns the clip
#: into renderable frames.
PLAYER_WALK_ANIM = "WALK"


def load_player_sprite(main_world_path: str | Path) -> AnimPixels | None:
    """Decode the player's standing frame from ``MAIN.WLD``'s global bank.

    The player is the ``NMY`` record named :data:`PLAYER_NMY_NAME`; its
    standing pose is the first keyframe of the :data:`PLAYER_STAND_ANIM`
    animation.  Each keyframe's first byte is the referenced ``ANIM``
    type_index (``anim_nmy.NmyAnim.frames``, measured ~99% on the retail
    install), so the standing sprite is that chunk's first frame, decoded to
    palette indices.  The indexed layer is returned — the caller applies its
    own ``HEAD`` palette.

    Returns ``None`` when ``MAIN.WLD`` is absent or does not resolve; the
    renderer then falls back to the player marker, so a synthetic world
    without the global bank still renders.
    """
    source = Path(main_world_path)
    if not source.is_file():
        return None
    try:
        world = wld.parse_file(source)
    except (OSError, wld.WLDError):
        return None
    nmy = next((c for c in world.chunks if c.tag == "NMY"), None)
    if nmy is None:
        return None
    result = decode_nmy(nmy.payload)
    if result is None:
        return None
    records, _ = result
    hero = next((r for r in records if r.name == PLAYER_NMY_NAME), None)
    if hero is None:
        return None
    stand = next(
        (a for a in hero.anims if anim_tag_name(a.tag) == PLAYER_STAND_ANIM),
        None,
    )
    if stand is None or not stand.frames:
        return None
    sprite_index = stand.frames[0][0]
    anim = None
    for chunk in world.chunks:
        if chunk.tag != "ANIM":
            continue
        decoded = decode_anim(chunk.payload)
        if decoded is not None and decoded.type_index == sprite_index:
            anim = decoded
            break
    if anim is None:
        return None
    return decode_anim_pixels(anim, 0)


def load_walk_clip(main_world_path: str | Path) -> tuple[anim_clip.PoseFrame, ...]:
    """Resolve the player's ``WALK`` clip to one composited pose per stride.

    Returns one :class:`lomax_modern.anim_clip.PoseFrame` per resolvable stride
    ``step`` (10 for ``Hero.WALK``), each the composite of that step's two
    sprite layers — legs (sprite 34) and body (sprite 33) — painted at their
    recorded ``(dx, -dy)`` screen offsets into one shared canvas (see
    :func:`lomax_modern.anim_clip.resolve_poses`).  The contact pose (step 0,
    sprite byte 169) is not in any ``.WLD`` bank and is dropped.  ``()`` when
    ``MAIN.WLD`` is absent or does not resolve; the renderer then falls back to
    the standing sprite.
    """
    source = Path(main_world_path)
    if not source.is_file():
        return ()
    try:
        world = wld.parse_file(source)
    except (OSError, wld.WLDError):
        return ()
    return anim_clip.resolve_poses(
        world, record_name=PLAYER_NMY_NAME, clip_tag=PLAYER_WALK_ANIM
    )


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


@dataclass(frozen=True)
class Level:
    """One world file loaded for play.

    ``playfield`` selects which of the world's planes is the walkable grid.
    The plane → level mapping lives in the executable's level table (Q3), which
    this repository never reads, so the default is the first plane and the
    caller may override it.
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
    #: The player's resolved ``WALK`` clip (see :func:`load_walk_clip`), one
    #: :class:`lomax_modern.anim_clip.PoseFrame` per stride step (10 for
    #: ``Hero.WALK``), each the composite of that step's two sprite layers on
    #: one shared canvas.  Empty when ``MAIN.WLD`` is absent; the renderer
    #: falls back to the standing sprite while moving.
    walk_frames: tuple[anim_clip.PoseFrame, ...] = ()

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

    return Level(
        name=source.stem,
        path=source,
        sections=sections,
        cells=cells,
        palette=palette,
        playfield=playfield,
        collision=collision or CollisionModel(),
        gnmy=gnmy,
        player_sprite=load_player_sprite(source.parent / "MAIN.WLD"),
        walk_frames=load_walk_clip(source.parent / "MAIN.WLD"),
    )
