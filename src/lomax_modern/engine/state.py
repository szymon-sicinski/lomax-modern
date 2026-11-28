"""Game state, the 60 Hz tick, and the save-state design.

The tick is a pure function of the current state and one :class:`Input`, so it
is deterministic and unit-testable.  Save states are *designed in* here as a
JSON-serialisable :class:`Snapshot`; persistence to disk belongs to the input
card, which owns the save/load UX.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from random import Random

from .enemies import apply_tuple, enemy_to_tuple, new_enemies, step_enemies
from .entities import (
    AIR_POSE2_MAX_VY_MOVING,
    AIR_POSE2_MAX_VY_STRAIGHT,
    AIR_POSE4_MIN_VY,
    AIR_POSE5_MIN_VY,
    AIR_POSE6_MIN_VY,
    COINS_PER_LIFE,
    DUCK_POSES,
    DUCK_RATE,
    EXIT_Y_TOLERANCE_PX,
    EXIT_ZONE_PX,
    FASTFALL_MIN_VY,
    FLO1_RATE,
    FLO2_RATE,
    GRAVITY,
    GROUND_FOLLOW_TOLERANCE_PX,
    IDLE_MIN_THRESHOLD,
    IDLE_REFREEZE_THRESHOLD,
    IDLE_START_THRESHOLD,
    IDLE_THRESHOLD_MASK,
    JUMP_HOLD_RELEASED,
    JUMP_HOLD_SCALE,
    JUMP_HOLD_START,
    JUMP_HOLD_STEP,
    JUMP_LOCKOUT_MOVING,
    JUMP_LOCKOUT_RATE,
    JUMP_LOCKOUT_STRAIGHT,
    JUMP_SPEED,
    JUMP_STRAIGHT_AT_LEVEL_START,
    LANDING_TICKS,
    MAX_FALL,
    MAX_LIVES,
    MONEYBAG_BURST_COINS,
    REVIVE_SLACK_BELOW_PX,
    STA1_POSES,
    STA1_RATE,
    STA2_POSES,
    STA2_RATE,
    START_FEET_OFFSET_Y,
    STARTING_LIVES,
    WALK_SPEED,
    Collectible,
    Entities,
    Exit,
    Input,
    Player,
    Revive,
)
from .level import (
    CELL_PX,
    PLAYER_DUCK_ANIM,
    PLAYER_FASTFALL_ANIM,
    PLAYER_FASTFALL_MOVING_ANIM,
    PLAYER_IDLE_ANIM,
    PLAYER_JUMP_ANIM,
    PLAYER_JUMP_MOVING_ANIM,
    PLAYER_LAND_ANIM,
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

#: Bit 0 of the value is the idle cycle's decision bit.
RandomBits = Callable[[], int]
IDLE_DEFAULT_SEED = 0


def default_random_bits(seed: int = IDLE_DEFAULT_SEED) -> RandomBits:
    """A deterministic source for the idle cycle's bits (``random.Random(seed)``)."""
    generator = Random(seed)
    return lambda: generator.getrandbits(32)


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


def _advance(phase: int, frame: int, rate_px256: int) -> tuple[int, int]:
    """Add ``rate_px256`` to a 1/256-pose position; return ``(frame, phase)``."""
    phase += rate_px256
    steps, phase = divmod(phase, POSE_PHASE)
    return frame + steps, phase


def advance_pose(player: Player, rate_px256: int) -> None:
    """Add ``rate_px256`` to the phase and carry whole poses into ``anim_frame``.

    Integer only, so rate 73 holds 3, 4, 3, 4... ticks and never drifts.
    """
    player.anim_frame, player.anim_phase = _advance(
        player.anim_phase, player.anim_frame, rate_px256
    )


def air_pose_from_vy(vy: float, *, straight: bool) -> int:
    """The post-lockout jump pose, taken from ``vy`` (down positive) [V].

    ``docs/file-formats.md`` §2.6.2 d "Air poses follow ``vy``, not time"
    (``0x411A68``-``0x411AB5`` for ``JMP1``, ``0x411BEB``-``0x411C38`` for
    ``JMP2``).  Order matters: the near-apex pose 2 is tested first, because
    every other gate is a ``>`` on a larger ``vy``.
    """
    if straight and vy <= AIR_POSE2_MAX_VY_STRAIGHT:
        return 2
    if not straight and vy <= AIR_POSE2_MAX_VY_MOVING:
        return 2
    if vy > AIR_POSE6_MIN_VY:
        return 6
    if vy > AIR_POSE5_MIN_VY:
        return 5
    if vy > AIR_POSE4_MIN_VY:
        return 4
    return 3


def air_clip_tags(player: Player) -> tuple[str, str]:
    """``(jump tag, fast-fall tag)`` for the player's jump kind (rows 14/18/20/21)."""
    if player.jump_straight:
        return PLAYER_JUMP_ANIM, PLAYER_FASTFALL_ANIM
    return PLAYER_JUMP_MOVING_ANIM, PLAYER_FASTFALL_MOVING_ANIM


def select_air_clip(player: Player) -> tuple[str, int]:
    """The airborne clip: the jump clip, or the fast-fall clip in a fast fall [V]."""
    jump_tag, fall_tag = air_clip_tags(player)
    if player.jump_lockout > 0:
        return jump_tag, player.air_frame
    if player.vy >= FASTFALL_MIN_VY:
        return fall_tag, player.air_frame
    return jump_tag, air_pose_from_vy(player.vy, straight=player.jump_straight)


def air_clip_rate_px256(player: Player) -> int:
    """The air clip's pose advance this tick, in 1/256 poses.

    64 while the jump lockout runs (time-driven, rows 14/20), 64/68 for
    ``FLO1``/``FLO2`` (their own rates, rows 18/21), and **0** once the lockout
    has ended and the pose is forced from ``vy`` (row 19, ``0x411975``).
    """
    if player.jump_lockout > 0:
        return JUMP_LOCKOUT_RATE
    if player.vy >= FASTFALL_MIN_VY:
        return FLO1_RATE if player.jump_straight else FLO2_RATE
    return 0


def select_clip(player: Player) -> tuple[str, int]:
    """The clip the player draws now: ``(clip tag, pose index)``.

    **Pure**: a function of the player's own state — no I/O, no module-level
    mutable state, no level.  The pair is the key into the level's clip table
    (``Level.clip_pose``), so the render path names no sprite id and needs no
    branch per clip; a later slice changes *this* function (idle in AN6)
    instead of the renderer.

    Rules (``docs/file-formats.md`` §2.6.2 a; Q38 is answered [V]):

    * airborne (``not on_ground``) → :func:`select_air_clip`: ``JMP1``/``JMP2``
      by jump kind, ``FLO1``/``FLO2`` in a fast fall; never a ground clip;
    * grounded with the duck flag set by :func:`step_player` →
      :data:`PLAYER_DUCK_ANIM` (``DUCK``) at :attr:`Player.duck_frame` (row 23,
      one-shot, holds its last pose; the setter is [H]).  Row 23 precedes rows
      24-26 in the original's priority chain, so a duck outranks ``LND1``;
    * grounded with the landing flag set by :func:`step_player` →
      :data:`PLAYER_LAND_ANIM` (``LND1``), pose 0 (the clip is one pose);
    * standing (``|vx| == 0``) → :data:`PLAYER_STAND_ANIM` (``STA1``), pose 0, or
      the idle clip :func:`_update_idle` is playing once (rows 30-31);
    * ``0 < |vx| <= 2.0`` → ``WALK``; ``|vx| > 2.0`` → ``RUN``; the pose index is
      :attr:`Player.anim_frame`.

    Facing is not part of the choice (the sign of ``vx`` only sets
    ``player.facing``).
    """
    if not player.on_ground:
        return select_air_clip(player)
    if player.duck_shown:
        return PLAYER_DUCK_ANIM, player.duck_frame
    if player.lnd1_shown:
        return PLAYER_LAND_ANIM, 0
    rule = ground_clip_rule(player.vx)
    if rule is None:
        if player.idle_clip_tag:
            return player.idle_clip_tag, player.idle_frame
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


#: Landing vy gate by floor kind (flat, shallow, steep): land only when
#: ``vy`` exceeds it (§2.9.d [V]).
_LANDING_MIN_VY = (0.0, -1.5, -3.25)


def _feet(player: Player) -> tuple[int, int]:
    """The floor probe's feet origin: bottom centre of the box, floored to ints."""
    return int(player.x + player.width / 2), int(player.y + player.height)


def _resolve_floor(
    level: Level,
    player: Player,
    start_feet: tuple[int, int],
    start_floor: tuple[int, int] | None,
    *,
    grounded: bool,
) -> None:
    """One-way floor landing (airborne) or ground-follow (grounded at tick start)."""
    feet_x, feet_y = _feet(player)
    bottom = player.y + player.height
    found = level.floor_at(feet_x, feet_y)
    if found is None:
        return
    floor1, kind = found
    if grounded:
        if abs(bottom - floor1) > GROUND_FOLLOW_TOLERANCE_PX:
            return
    else:
        floor0 = start_floor[0] if start_floor is not None else floor1
        if not (
            player.vy > _LANDING_MIN_VY[kind]
            and floor0 >= start_feet[1]
            and floor1 <= bottom
        ):
            return
    player.y = floor1 - player.height
    player.vy = 0.0
    player.on_ground = True


def _update_air_and_landing(
    player: Player, inp: Input, *, was_grounded: bool, launched: bool
) -> None:
    """The touchdown, landing-counter and air-clip bookkeeping of one tick.

    Mirrors the original's order: the physics (jump kind, landing counter at
    ``0x410E96``-``0x410EBF``) runs first, then the selector's own state
    (``0x411D2D``-``0x411D5D`` for ``LND1``, rows 14-21 for the air clips).
    ``select_clip`` reads what this leaves, so it stays pure and a caller may
    call it more than once per tick (the slice books the clip it drew, the
    renderer draws one).
    """
    if launched:
        # 0x4106DE-0x41070B: the kind comes from the *resolved* vx -- the value
        # _resolve_x leaves, so a jump launched pressed against a wall (vx
        # zeroed by the wall) is the straight kind.
        player.jump_straight = player.vx == 0.0
        player.jump_lockout = (
            JUMP_LOCKOUT_STRAIGHT if player.jump_straight else JUMP_LOCKOUT_MOVING
        )
        player.air_clip_tag = ""  # the clip is set afresh: pose 0, position 0
    elif player.jump_lockout > 0:
        # The decrement's own VA is not in §2.6.2 [H]: modelled as one per tick,
        # ground or air, so a lockout cannot survive a landing.
        player.jump_lockout -= 1

    player.lnd1_shown = False
    if player.on_ground:
        if not was_grounded:
            # Touchdown: 10 only after the straight kind (bit 0x2), else 0.
            player.landing_counter = LANDING_TICKS if player.jump_straight else 0
        if player.landing_counter > 0:
            player.landing_counter -= 1
            player.lnd1_shown = True
            if inp.left or inp.right:
                # 0x411D50 (`test BYTE PTR ds:0x464435, 0xa0`) runs *after* this
                # tick's LND1 was selected, so held left/right still draws 1 tick.
                player.landing_counter = 0
        return

    tag, _pose = select_air_clip(player)
    if tag != player.air_clip_tag:
        # 0x416110: set-if-different resets the clip position; the same clip
        # keeps advancing, which is why a switch lands on pose 0.
        player.air_clip_tag = tag
        player.air_frame = 0
        player.air_phase = 0
    else:
        player.air_frame, player.air_phase = _advance(
            player.air_phase, player.air_frame, air_clip_rate_px256(player)
        )


def _update_duck(player: Player, inp: Input) -> None:
    """The one-shot DUCK clip's one tick of bookkeeping.

    State bit 0x4 in the original (docs/file-formats.md §2.6.2 a row 23): this
    engine sets it while the player is grounded and Down is held [H] — where the
    original sets it (0x410A89) the exact conditions are untraced.  Setting the
    clip restarts it unless it is already playing (0x416110), and the advance
    routine (0x4161B0) holds the last pose because bit 0 of actor+0x58 is set
    for a one-shot clip.
    """
    was_shown = player.duck_shown
    player.duck_shown = bool(player.on_ground and inp.down)
    if not player.duck_shown:
        return
    if not was_shown:
        # 0x416140 (via 0x416110): a freshly set clip starts at pose 0.
        player.duck_frame = 0
        player.duck_phase = 0
    position = player.duck_frame * POSE_PHASE + player.duck_phase + DUCK_RATE
    # Hold the last pose: the position never reaches the pose count.
    position = min(position, DUCK_POSES * POSE_PHASE - 1)
    player.duck_frame, player.duck_phase = divmod(position, POSE_PHASE)


def _update_idle(player: Player, rand: RandomBits) -> None:
    """The idle cycle's one tick (§2.6.2 a rows 30-31, d "Idle").

    The numbers are [V]/[M]; the counter's increment site, the reset on leaving
    the idle branch, row 30's reset firing on (re-)entry of the frozen state and
    "bit 0 set means ``STA2``" are this engine's [H] choices.
    """
    in_idle = (
        player.on_ground
        and player.vx == 0.0
        and not player.duck_shown
        and not player.lnd1_shown
    )
    if not in_idle:
        # [H] leaving the idle branch resets the cycle: counter to 0, a playing
        # clip abandoned; rows 30-31 do not pin this.  The threshold is kept.
        player.idle_counter = 0
        player.idle_clip_tag = ""
        player.idle_frame = 0
        player.idle_phase = 0
        return
    if player.idle_clip_tag:  # row 31: the played clip runs at its own rate
        tag = player.idle_clip_tag
        rate = STA2_RATE if tag == PLAYER_IDLE_ANIM else STA1_RATE
        poses = STA2_POSES if tag == PLAYER_IDLE_ANIM else STA1_POSES
        frame, phase = _advance(player.idle_phase, player.idle_frame, rate)
        if frame >= poses:  # wrapped: it has played once
            player.idle_clip_tag = ""
            player.idle_frame = 0
            player.idle_phase = 0
            player.idle_counter = 0
            player.idle_threshold = IDLE_REFREEZE_THRESHOLD  # 10,000 [V]
            return
        player.idle_frame, player.idle_phase = frame, phase
        return
    if player.idle_counter < player.idle_threshold:  # row 30
        if player.idle_threshold == IDLE_REFREEZE_THRESHOLD:
            # [H] row 30's "reset the counter, new threshold 30 + (rand & 63)"
            # fires when the frozen state is (re-)entered, not on every tick
            # (otherwise the counter could never reach the threshold).
            player.idle_threshold = IDLE_MIN_THRESHOLD + (rand() & IDLE_THRESHOLD_MASK)
        player.idle_counter += 1
        return
    # row 31: play exactly one clip, chosen by bit 0 of the source
    # [H] mapping: bit 0 set -> STA2
    player.idle_clip_tag = PLAYER_IDLE_ANIM if (rand() & 1) else PLAYER_STAND_ANIM
    player.idle_frame = 0
    player.idle_phase = 0


def step_player(
    level: Level, player: Player, inp: Input, *, rand: RandomBits | None = None
) -> None:
    """Advance the player one tick: input, gravity, then axis-separated moves.

    ``rand`` is the idle cycle's random source; ``None`` uses a fresh
    ``default_random_bits()`` for this call, so a caller driving ``step_player``
    directly still gets a reproducible fixed-seed stream.

    Movement is axis-separated (X then Y) so a landing and a wall-hit in the
    same tick resolve independently.  ``on_ground`` is recomputed each tick.
    """
    if inp.down and player.on_ground:
        # [H] Holding Down on the ground suppresses horizontal input, so the
        # crouch always starts from rest; airborne input is unaffected.
        player.vx = 0.0
    elif inp.left and not inp.right:
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

    was_grounded = player.on_ground  # capture first, before the jump
    launched = bool(inp.jump and player.on_ground)
    # Physics gate (0x410B19, 0x410BED, 0x410D4A): while the original's lockout
    # 0x59E764 != 0 there is no gravity, no vertical integration and no ground
    # probe.  It is set on the launch tick and decremented at the end of that same
    # tick, while this engine's ``jump_lockout`` is the clip counter and is not
    # decremented on the launch tick.  So the original's value at physics time on
    # tick k after launch is (engine value at the start of tick k) - 1: frozen iff
    # launched now, or the engine value read *before* this tick's update is > 1.
    frozen = launched or (not was_grounded and player.jump_lockout > 1)
    if launched:
        player.vy = JUMP_SPEED
        player.jump_hold = JUMP_HOLD_START
        player.on_ground = False
    elif not was_grounded and not frozen:
        # Hold-to-rise (0x4105A0-0x4105ED), before this tick's gravity add.
        if not inp.jump:
            player.jump_hold = JUMP_HOLD_RELEASED
        elif player.jump_hold > 0:
            player.jump_hold -= JUMP_HOLD_STEP
            player.vy -= player.jump_hold * JUMP_HOLD_SCALE
    elif not was_grounded and not inp.jump:
        player.jump_hold = JUMP_HOLD_RELEASED
    if not frozen:
        player.vy = min(player.vy + GRAVITY, MAX_FALL)

    start_feet = _feet(player)
    start_floor = level.floor_at(*start_feet)
    player.x += player.vx
    _resolve_x(level, player)
    if frozen:
        player.on_ground = False
    else:
        player.y += player.vy
        player.on_ground = False
        _resolve_y(level, player)
        if not player.on_ground:
            _resolve_floor(
                level, player, start_feet, start_floor,
                grounded=was_grounded and not launched,
            )
        if player.on_ground:
            # [H] the original's landing reset of the counter is not traced.
            player.jump_hold = JUMP_HOLD_RELEASED
    _update_air_and_landing(player, inp, was_grounded=was_grounded, launched=launched)
    _update_duck(player, inp)
    _update_idle(player, rand if rand is not None else default_random_bits())


#: Camera rule (§2.11.f [V]): easing step per tick, and the step while reversing,
#: in 1/65536 px/tick; 1/16 of the error is the target speed; y floor is 16.
CAM_ACCEL_FP = 0x4000
CAM_REVERSE_ACCEL_FP = 0xC000
CAM_EASE_DIVISOR = 16
CAM_MIN_Y = 16


@dataclass
class CameraRig:
    """The camera's mutable state: x in px, y and the vertical speed in 16.16.

    Implements the original's per-tick rule (``docs/file-formats.md`` §2.11.f,
    ``0x4120B2``-``0x4122B7`` [V]): x = feet - vw/2 clamped, no smoothing; y
    eased toward keeping the feet at 2/3 of the view height.  Not implemented:
    the Page Up/Down look bias (pad bits unbound in :class:`Input`; bias is 0)
    [H], the shake (``0x59E93C``, no source in L1) and ``ForceScrolling`` (L1
    has none).
    """

    cam_y_fp: int = 0
    speed_fp: int = 0
    cam_x: int = 0

    @property
    def cam_y(self) -> int:
        return self.cam_y_fp >> 16

    @classmethod
    def snap(
        cls, level: Level, player: Player, vw: int = 320, vh: int = 240
    ) -> CameraRig:
        """x by the rule, y = feet - anchor (the original's start, §2.11.f; its
        provisional start value is unmeasured [H]); speed 0."""
        feet_x, feet_y = _feet(player)
        anchor_y = (2 * vh) // 3
        rig = cls(cam_y_fp=(feet_y - anchor_y) << 16, speed_fp=0)
        rig.cam_x = _clamp_cam_x(level, feet_x, vw)
        rig._clamp_y(level, vh)  # the tick's clamp, so a pre-tick frame is in bounds
        return rig

    def _clamp_y(self, level: Level, vh: int) -> None:
        # Step 8: floor 16, then the plane's max; a short level clamps at 0.
        y = min(max(self.cam_y, CAM_MIN_Y), max(0, level.height_px - vh))
        if y != self.cam_y:
            self.cam_y_fp = y << 16

    def update(self, level: Level, player: Player, vw: int = 320, vh: int = 240) -> None:
        feet_x, feet_y = _feet(player)
        self.cam_x = _clamp_cam_x(level, feet_x, vw)
        anchor_y = (2 * vh) // 3
        # Step 4: target speed (positive = cam_y decreases), bias = 0.
        target = ((self.cam_y - feet_y + anchor_y) << 16) // CAM_EASE_DIVISOR
        # Step 5: approach the target, faster when reversing, never passing it.
        speed = self.speed_fp
        if speed < target:
            step = CAM_REVERSE_ACCEL_FP if speed < 0 else CAM_ACCEL_FP
            speed = min(speed + step, target)
        elif speed > target:
            step = CAM_REVERSE_ACCEL_FP if speed > 0 else CAM_ACCEL_FP
            speed = max(speed - step, target)
        self.speed_fp = speed
        self.cam_y_fp -= speed  # step 6
        self._clamp_y(level, vh)


def _clamp_cam_x(level: Level, feet_x: int, vw: int) -> int:
    return max(0, min(feet_x - vw // 2, max(0, level.width_px - vw)))


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
    lives: int = STARTING_LIVES
    coins: int = 0
    game_over: bool = False
    #: Human-readable rule events (lives lost, game over), in tick order.
    events: list[str] = field(default_factory=list)
    #: Box top-left, and jump kind, the state was created with; the respawn for a
    #: level without a ``Start`` placement.
    initial_spawn: tuple[float, float] | None = None
    initial_jump_straight: bool = False
    #: The idle cycle's random source, bit 0 of ``0x43AAD0()`` in the original
    #: (that it is a random-number routine is [H]).
    rand: RandomBits = field(default_factory=default_random_bits)
    #: The scrolling camera; ``None`` until first needed (snapped then).
    camera: CameraRig | None = None

    def __post_init__(self) -> None:
        if self.camera is None:
            self.camera = CameraRig.snap(self.level, self.player)

    def tick(self, inp: Input) -> None:
        """Advance exactly one 60 Hz logic tick."""
        if not self.game_over:
            step_enemies(self)  # original order: spawn -> entity updates -> hero
            step_player(self.level, self.player, inp, rand=self.rand)
            self._collect_and_exit()
            self._touch_revives()
            self._check_fail()
            if not self.game_over:
                self.camera.update(self.level, self.player)
        self.tick_count += 1

    def _collect_and_exit(self) -> None:
        for i, item in enumerate(self.entities.collectibles):
            if i not in self.entities.collected and _overlaps_cell(
                self.player, item.cell_x, item.cell_y
            ):
                self.entities.collected.add(i)
                self._add_coins(MONEYBAG_BURST_COINS)
        if self.complete:
            return
        # Exit [V] 0x427701-0x42772B: grounded, in the last EXIT_ZONE_PX of the
        # plane, feet within EXIT_Y_TOLERANCE_PX of the Exit's y; its x is unread.
        player = self.player
        if not player.on_ground or player.centre_x <= self.level.width_px - EXIT_ZONE_PX:
            return
        feet_y = player.y + player.height
        for exit_ in self.entities.exits:
            if abs(feet_y - exit_.y_px) < EXIT_Y_TOLERANCE_PX:
                self.complete = True
                return

    def _add_coins(self, amount: int) -> None:
        self.coins += amount
        if self.coins >= COINS_PER_LIFE:
            self.coins -= COINS_PER_LIFE
            self.lives = min(self.lives + 1, MAX_LIVES)

    def _touch_revives(self) -> None:
        player = self.player
        for i, revive in enumerate(self.entities.revives):
            if i == self.entities.touched_revive:
                continue
            if (
                player.x <= revive.x < player.x + player.width
                and player.y <= revive.y < player.y + player.height + REVIVE_SLACK_BELOW_PX
            ):
                self.entities.touched_revive = i

    def _respawn_player(self) -> tuple[Player, tuple[int, int]]:
        """A fresh player at the respawn point, and its integer feet origin."""
        idx = self.entities.touched_revive
        if idx is not None:
            revive = self.entities.revives[idx]
            player = Player(x=revive.x - Player.width / 2, y=float(revive.y - Player.height))
            # jump_straight stays False: state 0 [V] 0x42AAB9-0x42AB51
            return player, (int(revive.x), int(revive.y))
        spawn = self.level.spawn
        if spawn is not None:
            sx, sy = spawn
            player = Player(
                x=sx - Player.width / 2, y=sy - START_FEET_OFFSET_Y - Player.height
            )
            player.jump_straight = JUMP_STRAIGHT_AT_LEVEL_START
            return player, (int(sx), int(sy - START_FEET_OFFSET_Y))
        ix, iy = self.initial_spawn if self.initial_spawn is not None else (0.0, 0.0)
        player = Player(x=ix, y=iy)
        player.jump_straight = self.initial_jump_straight
        return player, (int(ix + Player.width / 2), int(iy + Player.height))

    def _check_fail(self) -> None:
        """Fail rule [H]: the box bottom reaches the plane's bottom edge."""
        if self.complete or self.player.y + self.player.height < self.level.height_px:
            return
        before = self.lives
        self.lives -= 1
        player, (fx, fy) = self._respawn_player()
        self.events.append(
            f"life lost at tick {self.tick_count}: lives {before} -> {self.lives}, "
            f"respawn ({fx}, {fy})"
        )
        if self.lives <= 0:
            self.game_over = True
            self.events.append(f"game over at tick {self.tick_count}")
        else:
            self.player = player
            self.camera = CameraRig.snap(self.level, player)


def new_game_state(
    level: Level,
    *,
    spawn_x: float | None = None,
    spawn_y: float | None = None,
    collectibles: list[Collectible] | None = None,
    exits: list[Exit] | None = None,
    revives: list[Revive] | None = None,
    seed: int = IDLE_DEFAULT_SEED,
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
    fresh_entry = False
    if spawn_x is None or spawn_y is None:
        fresh_entry = True
        spawn = level.spawn
        if spawn is not None:
            sx, sy = spawn
            if spawn_x is None and spawn_y is None:
                # §2.10.c [V] 0x42AC22-0x42AC3E: the placement is 40 px below the
                # feet origin (bottom centre); the box is centred on the feet [H].
                spawn_x = sx - Player.width / 2
                spawn_y = sy - START_FEET_OFFSET_Y - Player.height
            else:
                spawn_x = spawn_x if spawn_x is not None else float(sx)
                spawn_y = spawn_y if spawn_y is not None else float(sy)
        else:
            sx, sy = first_passable_cell(level)
            spawn_x = spawn_x if spawn_x is not None else sx * CELL_PX
            spawn_y = spawn_y if spawn_y is not None else sy * CELL_PX
    player = Player(x=float(spawn_x), y=float(spawn_y))
    if fresh_entry:
        player.jump_straight = JUMP_STRAIGHT_AT_LEVEL_START  # 0x42AC3B, [V]
    if collectibles is None:
        collectibles = [
            Collectible(px_x // CELL_PX, px_y // CELL_PX)
            for px_x, px_y in level.collectables
        ]
    if exits is None:
        exits = [
            Exit(px_x // CELL_PX, px_y // CELL_PX, px_y=px_y)
            for px_x, px_y in level.exits
        ]
    if revives is None:
        revives = [Revive(px_x, px_y) for px_x, px_y in level.revives]
    return GameState(
        level=level,
        player=player,
        entities=Entities(
            collectibles=list(collectibles),
            exits=list(exits),
            revives=list(revives),
            enemies=new_enemies(level),
        ),
        initial_spawn=(player.x, player.y),
        initial_jump_straight=player.jump_straight,
        rand=default_random_bits(seed),
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
    the state model.  The idle cycle's counter, threshold and played clip are
    captured; the random *stream* is not (the original's RNG is not per-player
    either) [H].
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
    idle_counter: int = 0
    idle_threshold: int = IDLE_START_THRESHOLD
    idle_clip_tag: str = ""
    idle_frame: int = 0
    idle_phase: int = 0
    jump_hold: int = JUMP_HOLD_RELEASED
    lives: int = STARTING_LIVES
    coins: int = 0
    game_over: bool = False
    touched_revive: int | None = None
    #: Camera 16.16 y and speed; ``None`` (old saves) snaps on restore.
    cam_y_fp: int | None = None
    cam_speed_fp: int = 0
    #: One flat int tuple per Henchlemming (``enemies.ENEMY_TUPLE_FIELDS`` order,
    #: bools as 0/1); ``()`` = the initial, all-unspawned enemies (old saves).  The
    #: living enemy draws no random number (§2.13.h), so no random state is saved.
    enemies: tuple[tuple[int, ...], ...] = ()

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
            "idle_counter": self.idle_counter,
            "idle_threshold": self.idle_threshold,
            "idle_clip_tag": self.idle_clip_tag,
            "idle_frame": self.idle_frame,
            "idle_phase": self.idle_phase,
            "jump_hold": self.jump_hold,
            "lives": self.lives,
            "coins": self.coins,
            "game_over": self.game_over,
            "touched_revive": self.touched_revive,
            "cam_y_fp": self.cam_y_fp,
            "cam_speed_fp": self.cam_speed_fp,
            "enemies": [list(e) for e in self.enemies],
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
            # Defaults so a snapshot written before AN6 still loads.
            idle_counter=data.get("idle_counter", 0),
            idle_threshold=data.get("idle_threshold", IDLE_START_THRESHOLD),
            idle_clip_tag=data.get("idle_clip_tag", ""),
            idle_frame=data.get("idle_frame", 0),
            idle_phase=data.get("idle_phase", 0),
            jump_hold=data.get("jump_hold", JUMP_HOLD_RELEASED),
            lives=data.get("lives", STARTING_LIVES),
            coins=data.get("coins", 0),
            game_over=data.get("game_over", False),
            touched_revive=data.get("touched_revive"),
            cam_y_fp=data.get("cam_y_fp"),
            cam_speed_fp=data.get("cam_speed_fp", 0),
            enemies=tuple(tuple(e) for e in data.get("enemies", ())),
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
        idle_counter=state.player.idle_counter,
        idle_threshold=state.player.idle_threshold,
        idle_clip_tag=state.player.idle_clip_tag,
        idle_frame=state.player.idle_frame,
        idle_phase=state.player.idle_phase,
        jump_hold=state.player.jump_hold,
        lives=state.lives,
        coins=state.coins,
        game_over=state.game_over,
        touched_revive=state.entities.touched_revive,
        cam_y_fp=state.camera.cam_y_fp,
        cam_speed_fp=state.camera.speed_fp,
        enemies=tuple(enemy_to_tuple(e) for e in state.entities.enemies),
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
    state.player.idle_counter = snapshot.idle_counter
    state.player.idle_threshold = snapshot.idle_threshold
    state.player.idle_clip_tag = snapshot.idle_clip_tag
    state.player.idle_frame = snapshot.idle_frame
    state.player.idle_phase = snapshot.idle_phase
    state.player.jump_hold = snapshot.jump_hold
    state.lives = snapshot.lives
    state.coins = snapshot.coins
    state.game_over = snapshot.game_over
    state.entities.touched_revive = snapshot.touched_revive
    state.camera = CameraRig.snap(state.level, state.player)
    if snapshot.cam_y_fp is not None:
        state.camera.cam_y_fp = snapshot.cam_y_fp
        state.camera.speed_fp = snapshot.cam_speed_fp
    fresh = new_enemies(state.level)
    if len(snapshot.enemies) == len(fresh):
        for enemy, data in zip(fresh, snapshot.enemies):
            apply_tuple(enemy, data)
    state.entities.enemies = fresh
