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

from ..anim_nmy import placement_role
from ..art import DEFAULT_PALETTE_SLOT, SPRITE_PALETTE_SLOT
from .entities import WALK_SPEED, Input
from .level import (
    PLAYER_IDLE_ANIM,
    PLAYER_RUN_ANIM,
    PLAYER_STAND_ANIM,
    PLAYER_WALK_ANIM,
    Level,
    load_level,
)
from .render import Frame, render_tiles
from .state import POSE_PHASE, GameState, new_game_state, pose_rate_px256, select_clip

#: A script turns the current tick and state into one tick of input.
InputScript = Callable[[int, GameState], Input]

#: A frame sink receives ``(tick_index, frame)`` after each engine tick.
FrameSink = Callable[[int, Frame], None]


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
    #: The spawn placement's ``NMY`` name (``"Start"``), or ``None`` when the
    #: level has no ``Start`` placement and the spawn fell back to the first
    #: passable cell.
    spawn_name: str | None
    ticks: int
    frames: int
    complete: bool
    final_position: tuple[float, float]
    collected: int
    collected_total: int
    clean_exit: bool
    gnmy_entries: int
    #: Placement count per ``NMY`` role: ``start``/``exit``/``moneybag`` are
    #: Q32 **[V]**; ``other`` is every unmapped name (one bucket, no glyph).
    gnmy_roles: dict[str, int]
    #: Pixel ``(x, y)`` of every ``Exit`` placement, in file order.
    exits: tuple[tuple[int, int], ...]
    #: One line stating how the player is drawn: the standing clip when idle,
    #: the moving clip's pose count and hold when moving, and the sprite palette
    #: slot.  Empty when the caller did not describe it (old constructions).
    player_anim: str = ""
    #: Ticks drawn per clip tag, in the level's clip-table order: each engine tick
    #: is booked to the clip :func:`lomax_modern.engine.state.select_clip` chose
    #: and the table could resolve, so ``sum`` is the number of ticks drawn as a
    #: clip.  Empty when there is no clip table (a world without ``MAIN.WLD`` draws
    #: the marker, and nothing is named).
    clip_ticks: tuple[tuple[str, int], ...] = ()
    next_level: str | None = None

    def format(self) -> str:
        if self.spawn_name is not None:
            spawn_line = (
                f"spawn: {self.spawn_name} "
                f"({self.spawn[0]:.0f}, {self.spawn[1]:.0f}) px"
            )
        else:
            spawn_line = (
                f"spawn: ({self.spawn[0]:.1f}, {self.spawn[1]:.1f}) px "
                "(no Start placement; fell back to the first passable cell)"
            )
        if self.exits:
            first = self.exits[0]
            exit_line = f"exit: Exit ({first[0]}, {first[1]}) px"
            if len(self.exits) > 1:
                exit_line += f" (+{len(self.exits) - 1} more Exit placement(s))"
        else:
            exit_line = "exit: none (no Exit placement)"
        lines = [
            f"world: {self.world} ({self.planes} planes, playfield plane {self.playfield})",
            f"playfield: {self.playfield_size[0]}x{self.playfield_size[1]} cells "
            f"({self.playfield_size[0] * 16}x{self.playfield_size[1] * 16} px)",
            self.collision_model,
            "collision-byte histogram (value: count): "
            + ", ".join(
                f"{value:#04x}:{count}" for value, count in self.collision_histogram.items()
            ),
            spawn_line,
            f"collect: {self.collected_total} Moneybag(s)",
            f"result: {'reached exit' if self.complete else 'did not reach exit'} "
            f"after {self.ticks} ticks",
            f"frames: {self.frames} (fixed 60 Hz: one frame per tick)",
            f"final position: ({self.final_position[0]:.1f}, {self.final_position[1]:.1f}) px",
            f"next level: {self.next_level or 'none (end of sequence or exit not reached)'}",
            exit_line,
            f"run exit: {'clean' if self.clean_exit else 'ERROR'}",
            "tile art: composed -- map cell -> tile record resolved (Q20), each "
            "record blitted as four CELLs in 2x2 column-major order (V, G1) "
            "with the HEAD palette (slot 1) and index-0 transparency; flip "
            "pairing [H] (Q33); the geometric collision grid stays on render() "
            "as a debug path",
            f"GNMY markers: {self.gnmy_entries} placements drawn by NMY name "
            f"-- start {self.gnmy_roles.get('start', 0)}, "
            f"exit {self.gnmy_roles.get('exit', 0)}, "
            f"moneybag {self.gnmy_roles.get('moneybag', 0)}, "
            f"other {self.gnmy_roles.get('other', 0)} "
            "(Start/Exit/Moneybag [V]; the other names' handlers are unmapped)",
        ]
        if self.player_anim:
            lines.append(self.player_anim)
        drawn = [f"{tag} {count}" for tag, count in self.clip_ticks if count]
        if drawn:
            lines.append("clips: " + ", ".join(drawn))
        return "\n".join(lines)


def run_slice(
    game_dir: str | Path,
    *,
    worlds: tuple[str, ...] = ("VILLAGE",),
    world_path: str | Path | None = None,
    max_ticks: int = 300,
    playfield: int = 0,
    backdrop_planes: tuple[int, ...] = (),
    script: InputScript | None = None,
    on_frame: FrameSink | None = None,
) -> tuple[SliceReport, Frame]:
    """Run one level (the first in ``worlds``) headless and return its report.

    Returns ``(report, final_frame)``.  Only the first world is played here: a
    vertical slice is one level end to end before any second world, and the
    next-level transition is exercised by the unit tests on synthetic data.

    ``on_frame`` is called with ``(tick_index, frame)`` after every tick, before
    the exit check, so a caller that wants one image per 60 Hz tick (the
    ``--frames`` capture) never has to hold the whole run in memory.  The sink
    is the only thing that writes; the engine itself stays read-only.

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

    level = load_level(resolved, playfield=playfield, backdrop_planes=backdrop_planes)
    state = new_game_state(level)
    spawn_pos = (state.player.x, state.player.y)
    spawn_name = "Start" if level.spawn is not None else None

    ticks = 0
    captured: Frame | None = None
    # One counter per clip in the table, in table order, so the ``clips:`` line is
    # stable across runs and diffs read as data ("which clip, how many ticks").
    clip_ticks = {tag: 0 for tag in level.clips}
    for tick in range(max_ticks):
        state.tick(script(tick, state))
        ticks += 1
        tag, _pose_index = select_clip(state.player)
        if tag in clip_ticks:
            clip_ticks[tag] += 1
        if on_frame is not None:
            captured = render_tiles(level, state)
            on_frame(ticks - 1, captured)
        if state.complete:
            break

    final_frame = captured if captured is not None else render_tiles(level, state)
    next_level = worlds[1] if state.complete and len(worlds) > 1 else None
    gnmy_roles = collections.Counter(placement_role(e.name) for e in level.gnmy)
    walk_poses = level.clips.get(PLAYER_WALK_ANIM, ())
    if walk_poses:
        rate = pose_rate_px256(WALK_SPEED)
        run_note = (
            f"{PLAYER_RUN_ANIM} ({len(level.clips[PLAYER_RUN_ANIM])} poses, "
            f"|vx|>>11) is the clip above 2.0, loaded but not drawn at "
            f"{WALK_SPEED:g}"
            if PLAYER_RUN_ANIM in level.clips
            else f"{PLAYER_RUN_ANIM} not resolved"
        )
        player_anim = (
            f"player: idle = {PLAYER_STAND_ANIM} held on pose 0, then "
            f"{PLAYER_STAND_ANIM} or {PLAYER_IDLE_ANIM} played once (100 idle ticks at level "
            f"start, 30-93 after); moving = "
            f"{PLAYER_WALK_ANIM} {len(walk_poses)} whole-body poses at "
            f"{rate}/{POSE_PHASE} pose per tick at {WALK_SPEED:g} px/tick "
            f"(|vx|/0x700; {POSE_PHASE / rate:.1f} ticks per pose) [V]; "
            f"{run_note}; airborne: JMP1/JMP2 by jump kind (a launch at the "
            f"resolved vx = 0 is straight), FLO1/FLO2 at vy >= 2.5, LND1 for 10 "
            f"ticks after a straight landing, cut to 1 while left/right is held; "
            f"facing = single sprite mirrored; ANIM "
            f"sprites through HEAD palette slot {SPRITE_PALETTE_SLOT}, tiles "
            f"through slot {DEFAULT_PALETTE_SLOT}"
        )
    else:
        player_anim = (
            f"player: no {PLAYER_WALK_ANIM} clip resolved (no sibling MAIN.WLD) "
            "-- the standing sprite is reused while moving"
        )
    report = SliceReport(
        world=world_name,
        planes=len(level.sections),
        playfield=playfield,
        playfield_size=(level.plane.width_cells, level.plane.height_cells),
        collision_histogram=_collision_histogram(level),
        collision_model=level.collision.report(),
        spawn=spawn_pos,
        spawn_name=spawn_name,
        ticks=ticks,
        frames=ticks,
        complete=state.complete,
        final_position=(state.player.x, state.player.y),
        collected=len(state.entities.collected),
        collected_total=len(state.entities.collectibles),
        clean_exit=True,
        gnmy_entries=len(level.gnmy),
        gnmy_roles=dict(gnmy_roles),
        exits=level.exits,
        player_anim=player_anim,
        clip_ticks=tuple(clip_ticks.items()),
        next_level=next_level,
    )
    return report, final_frame
