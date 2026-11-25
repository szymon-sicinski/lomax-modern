"""Player, input and entity records for the engine core.

The four physics constants below are measured from the retail ``LOMAX.EXE``
player-movement code (a read-only ``objdump`` pass, 2026-11-19), recorded in
``docs/file-formats.md`` §2.9.  The original stores position and velocity as
16.16 fixed point; the values here are the same rates in float pixels per
60 Hz tick.  They are stated so a test can assert on them rather than on magic
numbers, and each carries its measured virtual address next to the value.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Simulation rate: the original runs a 60 Hz logic tick (``WINMM.timeSetEvent``,
#: ``docs/roadmap/15-strategy-report.md`` §6).
TICK_RATE = 60

#: One tick in seconds.
TICK_SECONDS = 1.0 / float(TICK_RATE)

#: Horizontal walk speed, pixels per tick (120 px/s at 60 Hz).
#: Measured: ``mov ebp, 0x20000`` (2.0 in 16.16 fixed point) at VA ``0x426E28``,
#: the terrain-0 max speed stored to the max-speed global ``0x49C4B4``
#: (``docs/file-formats.md`` §2.9). Terrain type 1 (cell bits 0x30 >> 4 == 1)
#: swaps it for a directional 1.5/2.5 instead.
WALK_SPEED = 2.0

#: Gravity, pixels per tick squared (1350 px/s^2 at 60 Hz).
#: Measured: ``add eax, 0x6000`` (0.375 in 16.16 fixed point) added to ``vy``
#: each airborne tick at VA ``0x410BB8`` (``docs/file-formats.md`` §2.9); a held
#: slide/down input uses 0.125 (``0x2000``) instead.
GRAVITY = 0.375

#: Jump impulse, pixels per tick (an upward velocity of 240 px/s at 60 Hz).
#: Measured: ``mov ds:0x59F250, 0xFFFC0000`` (−4.0 in 16.16 fixed point) at VA
#: ``0x41083C`` (also ``0x4108B7``/``0x410929``/``0x4109D1``/``0x412DAB``/
#: ``0x412EC2``) (``docs/file-formats.md`` §2.9). Stomps/springs use −5.0/−6.0.
JUMP_SPEED = -4.0

#: Ground-follow tolerance in px: a grounded player is snapped onto the floor
#: surface when ``|feet - floor|`` is within it.  [V] comparison at
#: 0x410F09-0x410F5E (18 px with 0x52C704 != 0, 3 px when 0); which one applies
#: in play is [H].
GROUND_FOLLOW_TOLERANCE_PX = 18

#: Terminal fall speed, pixels per tick (360 px/s at 60 Hz).
#: Measured: ``vy`` is clamped to ``0x60000`` (6.0 in 16.16 fixed point) at VA
#: ``0x410BC2`` (``docs/file-formats.md`` §2.9).
MAX_FALL = 6.0

#: Ticks of ``LND1`` after a straight-jump touchdown: the landing counter
#: ``0x59F1CC`` is written with 10 there (``0x410E96``-``0x410EBF``;
#: ``docs/file-formats.md`` §2.6.2 b).
LANDING_TICKS = 10

#: The jump lockout ``0x59E764`` in ticks: a launch at ``vx == 0`` — the
#: straight kind, state bit ``0x2`` — sets 10, a launch at ``vx != 0`` sets 5
#: (``0x4106DE``-``0x41070B``, §2.6.2 b).
JUMP_LOCKOUT_STRAIGHT = 10
JUMP_LOCKOUT_MOVING = 5

#: The jump clip's rate **while the lockout runs**, in 1/256 poses per tick:
#: 64, one pose every 4 ticks (§2.6.2 a rows 14/20).  Once it reaches 0 the
#: pose is forced from ``vy`` at rate 0 (row 19, ``0x411975``).
JUMP_LOCKOUT_RATE = 64

#: ``FLO1`` and ``FLO2``'s own clip rate, in 1/256 poses per tick — the fast-fall
#: clips, not a slow float (§2.6.2 a rows 18/21).
FLO1_RATE = 64
FLO2_RATE = 68

#: The fast-fall clips take over at ``vy`` >= 2.5 px/tick downward
#: (``cmp vy, 0x28000`` / ``jl`` at ``0x411A33``; §2.6.2 a rows 18/21).
FASTFALL_MIN_VY = 2.5

#: ``vy`` gates for the post-lockout jump pose, ``vy`` positive downward
#: (§2.6.2 d "Air poses follow ``vy``, not time", ``0x411A68``-``0x411AB5`` and
#: ``0x411BEB``-``0x411C38``): above 1.0 pose 6, above -0.5 pose 5, above -2.0
#: pose 4, otherwise 3 — plus pose 2 while ``vy`` is still at or above -3.5
#: (``JMP1``) / -3.875 (``JMP2``).
AIR_POSE6_MIN_VY = 1.0
AIR_POSE5_MIN_VY = -0.5
AIR_POSE4_MIN_VY = -2.0
AIR_POSE2_MAX_VY_STRAIGHT = -3.5
AIR_POSE2_MAX_VY_MOVING = -3.875

#: The jump kind before any jump has set state bit 0x2: ``False`` = the moving
#: kind (bit clear, ``JMP2``/``FLO2``).  **[H]** -- §2.6.2 b traces every writer
#: of the bit (the launch sites) but not what 0x49C4C4 holds at level load, so
#: a zero-initialised global (bit clear) is this engine's choice, in one place.
JUMP_STRAIGHT_AT_LEVEL_START = False

#: ``DUCK``'s own clip rate in 1/256 poses per tick: 65, one pose every ~3.94
#: ticks (§2.6.2 a row 23, [V]).  *When* the clip is selected is [H]: this
#: engine ducks while grounded and Down is held.
DUCK_RATE = 65

#: ``DUCK``'s pose count (§2.6.2 a row 23 / Appendix A row 7, [M]).  The clip is
#: one-shot: it holds the last pose (``0x4161B0``) instead of wrapping.
DUCK_POSES = 6

#: The idle cycle (§2.6.2 a rows 30-31, d "Idle").  The idle counter ``0x46ABBC``
#: is compared with the threshold ``0x52C584``, which is 100 at level start
#: (``0x40F986``, [V]); row 30 draws ``STA1`` pose 0 (rate 0) while the counter
#: is below it, and sets a new threshold of ``30 + (rand & 63)`` ticks [V].
IDLE_START_THRESHOLD = 100  # [V] 0x40F986
IDLE_MIN_THRESHOLD = 30  # [V] row 30: 30 + (rand & 63)
IDLE_THRESHOLD_MASK = 63
#: Row 31: when the played clip wraps the threshold becomes 10,000 so row 30
#: re-freezes ``STA1`` next tick [V].
IDLE_REFREEZE_THRESHOLD = 10_000  # [V] row 31: the post-wrap sentinel
#: Row 31's played clips: their own rates in 1/256 poses per tick and pose counts
#: [M] (Appendix A / §2.6.2 d).
STA1_RATE = 64  # [M] row 31 (the clip's own rate)
STA2_RATE = 68  # [M] row 31
STA1_POSES = 7  # [M] Appendix A / §2.6.2 d
STA2_POSES = 10  # [M]


@dataclass(frozen=True)
class Input:
    """One tick of player intent.

    ``jump`` is edge-triggered by the caller: the simulation reacts only when
    the player is grounded, so a held ``jump`` re-jumps on landing.  ``down`` is
    level-triggered: ``True`` while the down key is held.
    """

    left: bool = False
    right: bool = False
    jump: bool = False
    down: bool = False


@dataclass
class Player:
    """The player's body: a top-left position in pixels plus velocity.

    The bounding box is 12x14 px, smaller than a 16x16 cell so the player fits
    through a one-cell gap.
    """

    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    on_ground: bool = False
    width: int = 12
    height: int = 14
    #: Facing direction: +1 right, -1 left.  Drives the sprite's horizontal flip.
    facing: int = 1
    #: Index of the current moving-clip pose; the selector
    #: (``state.select_clip``) picks the clip, ``Level.clip_pose`` wraps the index.
    anim_frame: int = 0
    #: Sub-pose accumulator in 1/256-pose units (0..255 is the remainder); the
    #: pose advances whenever it reaches 256 (``state.advance_pose``).
    anim_phase: int = 0
    jump_straight: bool = JUMP_STRAIGHT_AT_LEVEL_START  # state bit 0x2; straight == JMP1/FLO1
    jump_lockout: int = 0  # 0x59E764, ticks of the time-driven jump clip still to draw
    landing_counter: int = 0  # 0x59F1CC, ticks of LND1 still to draw
    lnd1_shown: bool = False  # set by step_player when this tick's ground branch drew LND1
    air_clip_tag: str = ""  # the air clip set last tick (actor+0x08's role in the air branch)
    air_frame: int = 0  # its pose index
    air_phase: int = 0  # its 1/256-pose position (rate 64/68 while it runs)
    # The one-shot DUCK clip.  The advance routine 0x4161B0 holds the last pose
    # because bit 0 of actor+0x58 is set for a one-shot clip, so the position
    # must never wrap to pose 0.
    duck_frame: int = 0  # the clip's current pose index
    duck_phase: int = 0  # its 1/256-pose position (advanced at DUCK_RATE)
    duck_shown: bool = False  # set by step_player when this tick selected DUCK
    # The idle cycle (rows 30-31).  The counter's increment site and the reset on
    # leaving the idle branch are [H].
    idle_counter: int = 0  # 0x46ABBC
    idle_threshold: int = IDLE_START_THRESHOLD  # 0x52C584
    idle_clip_tag: str = ""  # "" = frozen STA1; else the clip being played once
    idle_frame: int = 0  # its pose index
    idle_phase: int = 0  # its 1/256-pose position

    @property
    def centre_x(self) -> float:
        return self.x + self.width / 2.0

    @property
    def centre_y(self) -> float:
        return self.y + self.height / 2.0


@dataclass(frozen=True)
class Collectible:
    """A collectible at a map cell (pixel position = cell * 16)."""

    cell_x: int
    cell_y: int


@dataclass(frozen=True)
class Exit:
    """A level exit: a rectangular cell region that completes the level."""

    cell_x: int
    cell_y: int
    width_cells: int = 1
    height_cells: int = 1


@dataclass
class Entities:
    """Mutable entity lists plus the collected set (indices into collectibles)."""

    collectibles: list[Collectible] = field(default_factory=list)
    exits: list[Exit] = field(default_factory=list)
    collected: set[int] = field(default_factory=set)
