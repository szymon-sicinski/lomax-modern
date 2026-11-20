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

#: Terminal fall speed, pixels per tick (360 px/s at 60 Hz).
#: Measured: ``vy`` is clamped to ``0x60000`` (6.0 in 16.16 fixed point) at VA
#: ``0x410BC2`` (``docs/file-formats.md`` §2.9).
MAX_FALL = 6.0


@dataclass(frozen=True)
class Input:
    """One tick of player intent.

    ``jump`` is edge-triggered by the caller: the simulation reacts only when
    the player is grounded, so a held ``jump`` re-jumps on landing.
    """

    left: bool = False
    right: bool = False
    jump: bool = False


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
    #: Index of the current WALK keyframe (cycles over the resolved clip).
    anim_frame: int = 0

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
