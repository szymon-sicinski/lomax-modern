"""Game state, the 60 Hz tick, and the save-state design.

The tick is a pure function of the current state and one :class:`Input`, so it
is deterministic and unit-testable.  Save states are *designed in* here as a
JSON-serialisable :class:`Snapshot`; persistence to disk belongs to the input
card, which owns the save/load UX.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .entities import (
    GRAVITY,
    JUMP_SPEED,
    MAX_FALL,
    WALK_SPEED,
    Collectible,
    Entities,
    Exit,
    Input,
    Player,
)
from .level import (
    CELL_PX,
    PLAYER_RUN_ANIM,
    PLAYER_STAND_ANIM,
    PLAYER_WALK_ANIM,
    Level,
)

# Ground clip choice and pose rate come from the original (docs/file-formats.md
# §2.6.2 a rows 34-35, [V]).  Rates are in 1/256 pose per tick: ``WALK`` =
# |vx| / 0x700, ``RUN`` = |vx| >> 11, with a strict ``>`` at 2.0 (``cmp esi,
# 0x20000`` / ``jg`` at VA 0x411F79), so exactly 2.0 is ``WALK``.  The engine's
# only ground speed (2.0) is therefore ``WALK`` at 73/256 pose per tick.

#: Rates are in 1/256 poses per tick (file-formats §2.6.2 a).
POSE_PHASE = 256
#: 2.0 px/tick in 16.16 fixed point; the ``cmp esi, 0x20000`` at 0x411F79.
WALK_MAX_SPEED_PX16 = 0x20000


@dataclass(frozen=True)
class GroundClipRule:
    """One row of the original's ground-moving clip selector (§2.6.2 a rows 34-35)."""

    tag: str
    max_speed_px16: int | None  # inclusive upper bound on |vx|; None = no upper bound
    rate_divisor: int  # poses/tick in 1/256 units = |vx|(16.16) // rate_divisor


GROUND_CLIP_RULES: tuple[GroundClipRule, ...] = (
    GroundClipRule(PLAYER_WALK_ANIM, WALK_MAX_SPEED_PX16, 0x700),  # row 34, |vx|/0x700
    GroundClipRule(PLAYER_RUN_ANIM, None, 0x800),  # row 35, |vx| >> 11
)


def speed_px16(vx: float) -> int:
    """``|vx|`` in 16.16 fixed point.

    Truncating to an integer is exact here: the engine's speeds are binary
    fractions (2.0 -> 0x20000, 2.5 -> 0x28000), and the original stores ``vx`` in
    16.16 too.
    """
    return int(abs(vx) * (1 << 16))


def ground_clip_rule(vx: float) -> GroundClipRule | None:
    """The rule for a grounded player at ``vx``; ``None`` when standing.

    The first row whose bound is ``None`` or ``>= |vx|``: inclusive on the walk
    row, so exactly 2.0 is ``WALK`` (the original's strict ``jg``).
    """
    if abs(vx) == 0:
        return None
    speed = speed_px16(vx)
    for rule in GROUND_CLIP_RULES:
        if rule.max_speed_px16 is None or rule.max_speed_px16 >= speed:
            return rule
    return None


def pose_rate_px256(vx: float) -> int:
    """Pose advance per tick in 1/256 poses: 0 standing, 73 at 2.0, 80 at 2.5."""
    rule = ground_clip_rule(vx)
    if rule is None:
        return 0
    return speed_px16(vx) // rule.rate_divisor


def advance_pose(player: Player, rate_px256: int) -> None:
    """Add ``rate_px256`` to the phase and carry whole poses into ``anim_frame``.

    Integer only, so rate 73 holds 3, 4, 3, 4... ticks and never drifts.
    """
    player.anim_phase += rate_px256
    steps, player.anim_phase = divmod(player.anim_phase, POSE_PHASE)
    player.anim_frame += steps


def select_clip(player: Player) -> tuple[str, int]:
    """The clip the player draws now: ``(clip tag, pose index)``.

    **Pure**: a function of the player's own state — no I/O, no module-level
    mutable state, no level.  The pair is the key into the level's clip table
    (``Level.clip_pose``), so the render path names no sprite id and needs no
    branch per clip; a later slice changes *this* function (air states in AN4,
    duck in AN5, idle in AN6) instead of the renderer.

    Rules (``docs/file-formats.md`` §2.6.2 a rows 34-35; Q38 is answered [V]):

    * standing (``|vx| == 0``) → :data:`PLAYER_STAND_ANIM` (``STA1``), pose 0;
    * ``0 < |vx| <= 2.0`` → ``WALK``; ``|vx| > 2.0`` → ``RUN``; the pose index is
      :attr:`Player.anim_frame`.

    Facing is not part of the choice (the sign of ``vx`` only sets
    ``player.facing``).  Airborne is not special-cased yet (AN4), so a moving
    airborne player resolves to ``WALK`` too.
    """
    rule = ground_clip_rule(player.vx)
    if rule is None:
        return PLAYER_STAND_ANIM, 0
    return rule.tag, player.anim_frame


def _overlaps_cell(player: Player, cell_x: int, cell_y: int) -> bool:
    """Whether the player's box overlaps a 16x16 map cell."""
    px0 = cell_x * CELL_PX
    py0 = cell_y * CELL_PX
    return (
        player.x < px0 + CELL_PX
        and player.x + player.width > px0
        and player.y < py0 + CELL_PX
        and player.y + player.height > py0
    )


def _resolve_x(level: Level, player: Player) -> None:
    """Resolve horizontal penetration against solid cells, along ``vx``.

    The leading edge is tested with the *edge* coordinate (one past the last
    pixel) so a player exactly flush with a wall is recognised as resting, not
    as penetrating — which keeps a grounded player from jittering 1 px/tick.
    """
    if player.vx > 0:
        cell_x = int((player.x + player.width) // CELL_PX)
        cy0 = int(player.y // CELL_PX)
        cy1 = int((player.y + player.height - 1) // CELL_PX)
        for cell_y in range(cy0, cy1 + 1):
            if level.solid_at(cell_x, cell_y):
                player.x = cell_x * CELL_PX - player.width
                player.vx = 0.0
                break
    elif player.vx < 0:
        cell_x = int(player.x // CELL_PX)
        cy0 = int(player.y // CELL_PX)
        cy1 = int((player.y + player.height - 1) // CELL_PX)
        for cell_y in range(cy0, cy1 + 1):
            if level.solid_at(cell_x, cell_y):
                player.x = (cell_x + 1) * CELL_PX
                player.vx = 0.0
                break


def _resolve_y(level: Level, player: Player) -> None:
    """Resolve vertical penetration; landing sets ``on_ground``.

    Uses the bottom edge (one past the last pixel) so resting on a floor is a
    no-op rather than a 1-px penetration each tick.
    """
    if player.vy > 0:
        cell_y = int((player.y + player.height) // CELL_PX)
        cx0 = int(player.x // CELL_PX)
        cx1 = int((player.x + player.width - 1) // CELL_PX)
        for cell_x in range(cx0, cx1 + 1):
            if level.solid_at(cell_x, cell_y):
                player.y = cell_y * CELL_PX - player.height
                player.vy = 0.0
                player.on_ground = True
                break
    elif player.vy < 0:
        cell_y = int(player.y // CELL_PX)
        cx0 = int(player.x // CELL_PX)
        cx1 = int((player.x + player.width - 1) // CELL_PX)
        for cell_x in range(cx0, cx1 + 1):
            if level.solid_at(cell_x, cell_y):
                player.y = (cell_y + 1) * CELL_PX
                player.vy = 0.0
                break


def step_player(level: Level, player: Player, inp: Input) -> None:
    """Advance the player one tick: input, gravity, then axis-separated moves.

    Movement is axis-separated (X then Y) so a landing and a wall-hit in the
    same tick resolve independently.  ``on_ground`` is recomputed each tick.
    """
    if inp.left and not inp.right:
        player.vx = -WALK_SPEED
    elif inp.right and not inp.left:
        player.vx = WALK_SPEED
    else:
        player.vx = 0.0

    # Moving-animation bookkeeping: the pose advances at the original's rate
    # (``pose_rate_px256``).  The facing is the sign of the current velocity and
    # is kept when the player stops, so a standing player still faces where they
    # were going; the pose resets when they stop.
    if player.vx != 0.0:
        player.facing = 1 if player.vx > 0 else -1
        advance_pose(player, pose_rate_px256(player.vx))
    else:
        player.anim_phase = 0
        player.anim_frame = 0

    if inp.jump and player.on_ground:
        player.vy = JUMP_SPEED
        player.on_ground = False
    player.vy = min(player.vy + GRAVITY, MAX_FALL)

    player.x += player.vx
    _resolve_x(level, player)
    player.y += player.vy
    player.on_ground = False
    _resolve_y(level, player)


@dataclass
class GameState:
    """Everything mutable in one play session, advanced by :meth:`tick`.

    The counter field is ``tick_count`` (not ``tick``) so it cannot shadow the
    :meth:`tick` method on the class.
    """

    level: Level
    player: Player
    entities: Entities = field(default_factory=Entities)
    tick_count: int = 0
    complete: bool = False

    def tick(self, inp: Input) -> None:
        """Advance exactly one 60 Hz logic tick."""
        step_player(self.level, self.player, inp)
        self._collect_and_exit()
        self.tick_count += 1

    def _collect_and_exit(self) -> None:
        for i, item in enumerate(self.entities.collectibles):
            if i not in self.entities.collected and _overlaps_cell(
                self.player, item.cell_x, item.cell_y
            ):
                self.entities.collected.add(i)
        for exit_ in self.entities.exits:
            for dy in range(exit_.height_cells):
                for dx in range(exit_.width_cells):
                    if _overlaps_cell(self.player, exit_.cell_x + dx, exit_.cell_y + dy):
                        self.complete = True
                        return


def new_game_state(
    level: Level,
    *,
    spawn_x: float | None = None,
    spawn_y: float | None = None,
    collectibles: list[Collectible] | None = None,
    exits: list[Exit] | None = None,
) -> GameState:
    """Build a fresh state from the level's ``GNMY`` placements (Q32 **[V]**).

    The defaults come from the playfield plane's placements, each resolved on
    the ``NMY`` record's four-byte name prefix (``docs/file-formats.md`` §2.5):
    the spawn is the ``Start`` placement's pixel position, the collectibles are
    the ``Moneybag`` placements and the exits are the ``Exit`` placements, each
    converted to its ``CELL_PX`` map cell.  A level without a ``Start``
    placement falls back to the first passable cell, and one without
    ``Moneybag``/``Exit`` placements yields empty entity lists, so a synthetic
    level with no ``NMY``/``GNMY`` data still runs.  Any of the four may be
    overridden explicitly by the caller.
    """
    if spawn_x is None or spawn_y is None:
        spawn = level.spawn
        if spawn is not None:
            sx, sy = spawn
            spawn_x = spawn_x if spawn_x is not None else float(sx)
            spawn_y = spawn_y if spawn_y is not None else float(sy)
        else:
            sx, sy = first_passable_cell(level)
            spawn_x = spawn_x if spawn_x is not None else sx * CELL_PX
            spawn_y = spawn_y if spawn_y is not None else sy * CELL_PX
    player = Player(x=float(spawn_x), y=float(spawn_y))
    if collectibles is None:
        collectibles = [
            Collectible(px_x // CELL_PX, px_y // CELL_PX)
            for px_x, px_y in level.collectables
        ]
    if exits is None:
        exits = [Exit(px_x // CELL_PX, px_y // CELL_PX) for px_x, px_y in level.exits]
    return GameState(
        level=level,
        player=player,
        entities=Entities(
            collectibles=list(collectibles),
            exits=list(exits),
        ),
    )


def first_passable_cell(level: Level) -> tuple[int, int]:
    """The first cell (row-major) whose collision byte is zero."""
    for cell_y in range(level.plane.height_cells):
        for cell_x in range(level.plane.width_cells):
            if level.passable(cell_x, cell_y):
                return cell_x, cell_y
    raise ValueError("level has no passable cell")


@dataclass(frozen=True)
class Snapshot:
    """A serialisable save state.

    Captures the level identity (name + playfield plane) and the mutable
    simulation state.  :meth:`to_dict` / :meth:`from_dict` round-trip to plain
    JSON types so persistence can land in the input card without re-designing
    the state model.
    """

    world: str
    playfield: int
    tick: int
    complete: bool
    x: float
    y: float
    vx: float
    vy: float
    on_ground: bool
    collected: tuple[int, ...]

    def to_dict(self) -> dict:
        return {
            "world": self.world,
            "playfield": self.playfield,
            "tick": self.tick,
            "complete": self.complete,
            "x": self.x,
            "y": self.y,
            "vx": self.vx,
            "vy": self.vy,
            "on_ground": self.on_ground,
            "collected": list(self.collected),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Snapshot":
        return cls(
            world=data["world"],
            playfield=data["playfield"],
            tick=data["tick"],
            complete=data["complete"],
            x=data["x"],
            y=data["y"],
            vx=data["vx"],
            vy=data["vy"],
            on_ground=data["on_ground"],
            collected=tuple(data["collected"]),
        )


def capture(state: GameState) -> Snapshot:
    """Snapshot the mutable parts of ``state``."""
    return Snapshot(
        world=state.level.name,
        playfield=state.level.playfield,
        tick=state.tick_count,
        complete=state.complete,
        x=state.player.x,
        y=state.player.y,
        vx=state.player.vx,
        vy=state.player.vy,
        on_ground=state.player.on_ground,
        collected=tuple(sorted(state.entities.collected)),
    )


def restore(state: GameState, snapshot: Snapshot) -> None:
    """Overwrite ``state``'s mutable parts from a snapshot.

    ``snapshot.world``/``snapshot.playfield`` must match the loaded level; the
    caller is responsible for loading the right world before restoring.
    """
    if snapshot.world != state.level.name:
        raise ValueError(
            f"snapshot is for world {snapshot.world!r}, state is {state.level.name!r}"
        )
    if snapshot.playfield != state.level.playfield:
        raise ValueError(
            f"snapshot is for plane {snapshot.playfield}, state is {state.level.playfield}"
        )
    state.tick_count = snapshot.tick
    state.complete = snapshot.complete
    state.player.x = snapshot.x
    state.player.y = snapshot.y
    state.player.vx = snapshot.vx
    state.player.vy = snapshot.vy
    state.player.on_ground = snapshot.on_ground
    state.entities.collected = set(snapshot.collected)
