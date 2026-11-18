"""Headless vertical-slice runner.

Loads the first world, drives the 60 Hz tick with scripted input, produces a
frame, and reports ticks/frames and a clean exit — no display, no ``LOMAX.EXE``.
This is the M3 acceptance harness; the interactive presenter (keyboard, window)
lands in the input and presenter cards.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .entities import Collectible, Exit, Input
from .level import Level, load_level
from .render import Frame, render
from .state import GameState, first_passable_cell, new_game_state

#: A script turns the current tick and state into one tick of input.
InputScript = Callable[[int, GameState], Input]


def default_script(tick: int, state: GameState) -> Input:
    """Walk right, jump periodically — enough to exercise move + collide."""
    return Input(right=True, jump=(tick % 45 == 20))


def _collision_histogram(level: Level) -> dict[int, int]:
    counts: dict[int, int] = collections.Counter(
        level.plane.at(x, y).collision
        for y in range(level.plane.height_cells)
        for x in range(level.plane.width_cells)
    )
    return dict(sorted(counts.items()))


def _last_passable_cell(level: Level) -> tuple[int, int]:
    for cell_y in range(level.plane.height_cells - 1, -1, -1):
        for cell_x in range(level.plane.width_cells - 1, -1, -1):
            if level.passable(cell_x, cell_y):
                return cell_x, cell_y
    raise ValueError("level has no passable cell")


@dataclass(frozen=True)
class SliceReport:
    """What one vertical-slice run did; ``format()`` renders a text digest."""

    world: str
    planes: int
    playfield: int
    playfield_size: tuple[int, int]
    collision_histogram: dict[int, int]
    collision_model: str
    spawn: tuple[float, float]
    ticks: int
    frames: int
    complete: bool
    final_position: tuple[float, float]
    collected: int
    collected_total: int
    clean_exit: bool
    next_level: str | None = None

    def format(self) -> str:
        lines = [
            f"world: {self.world} ({self.planes} planes, playfield plane {self.playfield})",
            f"playfield: {self.playfield_size[0]}x{self.playfield_size[1]} cells "
            f"({self.playfield_size[0] * 16}x{self.playfield_size[1] * 16} px)",
            self.collision_model,
            "collision-byte histogram (value: count): "
            + ", ".join(
                f"{value:#04x}:{count}" for value, count in self.collision_histogram.items()
            ),
            f"spawn: ({self.spawn[0]:.1f}, {self.spawn[1]:.1f}) px "
            "(placeholder -- real spawn lives in GNMY, Q23)",
            f"collect: {self.collected}/{self.collected_total} "
            "(placement is placeholder -- GNMY semantics unresolved, Q23)",
            f"result: {'reached exit' if self.complete else 'did not reach exit'} "
            f"after {self.ticks} ticks",
            f"frames: {self.frames} (fixed 60 Hz: one frame per tick)",
            f"final position: ({self.final_position[0]:.1f}, {self.final_position[1]:.1f}) px",
            f"next level: {self.next_level or 'none (end of sequence or exit not reached)'}",
            f"exit: {'clean' if self.clean_exit else 'ERROR'}",
            "tile art: decoded (CELL/TTAB) but not placed on the map -- "
            "map cell -> tile record unresolved (Q20)",
        ]
        return "\n".join(lines)


def run_slice(
    game_dir: str | Path,
    *,
    worlds: tuple[str, ...] = ("VILLAGE",),
    world_path: str | Path | None = None,
    max_ticks: int = 300,
    playfield: int = 0,
    script: InputScript | None = None,
) -> tuple[SliceReport, Frame]:
    """Run one level (the first in ``worlds``) headless and return its report.

    Returns ``(report, final_frame)``.  Only the first world is played here: a
    vertical slice is one level end to end before any second world, and the
    next-level transition is exercised by the unit tests on synthetic data.

    ``world_path`` overrides the ``<game_dir>/WORLDS/<world>.WLD`` lookup.  The
    presenter passes the path the install check resolved, so a lower-case
    ``worlds/`` folder (or an install found one level down) runs without
    renaming the user's files.
    """
    script = script or default_script
    root = Path(game_dir)
    world_name = worlds[0]
    if world_path is not None:
        resolved = Path(world_path)
        world_name = resolved.stem
    else:
        resolved = root / "WORLDS" / f"{world_name}.WLD"
    if not resolved.is_file():
        raise FileNotFoundError(f"no world file at {resolved}")

    level = load_level(resolved, playfield=playfield)
    spawn_cell = first_passable_cell(level)
    exit_cell = _last_passable_cell(level)
    state = new_game_state(
        level,
        spawn_x=spawn_cell[0] * 16,
        spawn_y=spawn_cell[1] * 16,
        exits=[Exit(exit_cell[0], exit_cell[1])],
    )

    ticks = 0
    for tick in range(max_ticks):
        state.tick(script(tick, state))
        ticks += 1
        if state.complete:
            break

    final_frame = render(level, state)
    next_level = worlds[1] if state.complete and len(worlds) > 1 else None
    report = SliceReport(
        world=world_name,
        planes=len(level.sections),
        playfield=playfield,
        playfield_size=(level.plane.width_cells, level.plane.height_cells),
        collision_histogram=_collision_histogram(level),
        collision_model=level.collision.report(),
        spawn=(spawn_cell[0] * 16, spawn_cell[1] * 16),
        ticks=ticks,
        frames=ticks,
        complete=state.complete,
        final_position=(state.player.x, state.player.y),
        collected=len(state.entities.collected),
        collected_total=len(state.entities.collectibles),
        clean_exit=True,
        next_level=next_level,
    )
    return report, final_frame
