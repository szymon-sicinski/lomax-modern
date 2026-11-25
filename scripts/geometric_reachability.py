#!/usr/bin/env python3
"""Purely geometric reachability pass for one level (plan 47, R1).

Breadth-first search over the engine's own ``step_player`` on the collision grid
only: jump arcs and walking, **no objects and no enemies** (no Jumppad, Rope,
Pots, Henchlemming).  It answers one question early: can the hero get from the
``Start`` placement to an ``Exit`` placement on geometry alone?

Reads the user's install at run time and prints counts and coordinates only; it
writes nothing and embeds no game data.  Usage::

    python3 scripts/geometric_reachability.py "<install>" [--section 0 --sublevel 0]
        [--max-nodes 4000000]
"""

from __future__ import annotations

import argparse
import copy
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lomax_modern.engine import Input, new_game_state
from lomax_modern.engine.level import CELL_PX, load_level
from lomax_modern.engine.state import step_player

ACTIONS = tuple(
    Input(left=left, right=right, jump=jump)
    for left, right in ((False, False), (True, False), (False, True))
    for jump in (False, True)
)


def _key(p) -> tuple:
    return (int(p.x), round(p.y * 8), round(p.vy * 8), p.on_ground, p.jump_straight)


def _at_exit(p, exits) -> bool:
    for ex, ey in exits:
        if (
            p.x < ex + CELL_PX
            and p.x + p.width > ex
            and p.y < ey + CELL_PX
            and p.y + p.height > ey
        ):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_dir")
    parser.add_argument("--world", default="MEDIEVAL")
    parser.add_argument("--max-nodes", type=int, default=4_000_000)
    args = parser.parse_args()

    level = load_level(Path(args.game_dir) / "WORLDS" / f"{args.world}.WLD")
    state = new_game_state(level)
    start = state.player
    exits = level.exits
    seen = {_key(start)}
    queue = deque([start])
    frontier_x = start.x
    best = start
    nodes = 0
    reached = None
    while queue and nodes < args.max_nodes:
        player = queue.popleft()
        for action in ACTIONS:
            nxt = copy.copy(player)
            step_player(level, nxt, action, rand=lambda: 0)
            nodes += 1
            if nxt.y + nxt.height > level.height_px - CELL_PX:
                # The engine treats the map edge as solid; the original has no such
                # floor, so a fall to the bottom row counts as a lost life, not a path.
                continue
            key = _key(nxt)
            if key in seen:
                continue
            seen.add(key)
            if nxt.x > frontier_x:
                frontier_x, best = nxt.x, nxt
            if _at_exit(nxt, exits):
                reached = nxt
                queue.clear()
                break
            queue.append(nxt)
    print(f"level: {args.world}, {level.plane.width_cells}x{level.plane.height_cells} cells")
    print(f"start: ({start.x:.1f}, {start.y:.1f}); exits: {list(exits)}")
    print(f"states explored: {len(seen)}; transitions: {nodes}; queue left: {len(queue)}")
    if reached is not None:
        print(f"RESULT: exit reachable on geometry alone, at ({reached.x:.1f}, {reached.y:.1f})")
    else:
        done = "search exhausted" if not queue else "node limit hit"
        print(f"RESULT: exit NOT reached ({done}); farthest x = {frontier_x:.1f} "
              f"at y = {best.y:.1f}")
        near = sorted(
            (e for e in level.gnmy),
            key=lambda e: abs(e.x - frontier_x) + abs(e.y - best.y),
        )[:6]
        print("placements nearest the frontier (name, x, y): "
              + ", ".join(f"{e.name} ({e.x},{e.y})" for e in near))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
