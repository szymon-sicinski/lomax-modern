"""Player, input and entity records for the engine core.

All values here are *our own design* — a small, reasonable platformer physics
model with no claim to match the original's exact tuning, which lives inside
``LOMAX.EXE`` and is never read.  The constants are stated so a test can assert
on them rather than on magic numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Simulation rate: the original runs a 60 Hz logic tick (``WINMM.timeSetEvent``,
#: ``docs/roadmap/15-strategy-report.md`` §6).
TICK_RATE = 60

#: One tick in seconds.
TICK_SECONDS = 1.0 / float(TICK_RATE)

#: Horizontal walk speed, pixels per tick (120 px/s at 60 Hz).
WALK_SPEED = 2.0

#: Gravity, pixels per tick squared (1260 px/s^2 at 60 Hz).
GRAVITY = 0.35

#: Jump impulse, pixels per tick (an upward velocity of ~330 px/s at 60 Hz).
JUMP_SPEED = -5.5

#: Terminal fall speed, pixels per tick.
MAX_FALL = 8.0


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
