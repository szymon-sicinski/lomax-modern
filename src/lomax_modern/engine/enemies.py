"""Henchlemming movement (FL14): the hop-only STAY/JUMP update, per tick.

Implements ``docs/file-formats.md`` §2.13.b-f (handler ``0x42DD70``-``0x42DFDF``,
landing probe ``0x414450``, look-ahead ``0x414510``, same-kind probe
``0x4146A0``, wake rule ``0x412450``/``0x40F040``).  Pure functions on a
:class:`~lomax_modern.engine.entities.Henchlemming` and a level that offers
``floor_probe(x, y, rows)`` and ``width_px``.  Contact, stomp, hurt and kill are
FL15: here the enemy is harmless and unkillable.  The living behaviour draws no
random number (§2.13.h).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .entities import (
    FLOOR_KIND_STEEP,
    HENCH_AHEAD_SAME_KIND,
    HENCH_AHEAD_Y_OFFSET,
    HENCH_AHEAD_Y_WINDOW,
    HENCH_DESPAWN_MARGIN,
    HENCH_DESPAWN_PERIOD,
    HENCH_DESPAWN_PHASE_TICK,
    HENCH_FACING_BIT,
    HENCH_FIRST_REST_MASK,
    HENCH_GRAVITY,
    HENCH_GROUND_TICKS,
    HENCH_LONG_REST_BASE,
    HENCH_LONG_REST_MASK,
    HENCH_LOOKAHEAD_COLUMNS,
    HENCH_POSE_THRESHOLDS,
    HENCH_REST_MATCH_MASK,
    HENCH_SHORT_REST,
    HENCH_SPAWN_MARGIN,
    HENCH_SPAWN_PERIOD,
    HENCH_SPAWN_PHASE_TICK,
    HENCH_TAKEOFF_VX,
    HENCH_TAKEOFF_VY,
    LANDING_DEPTH_LIMIT,
    LOOKAHEAD_COLUMN_PX,
    LOOKAHEAD_STEP_LIMIT,
    PROBE_ROWS,
    VIEW_H,
    VIEW_W,
    Henchlemming,
)
from .level import GENERATOR_SPAWNED_FLAG

if TYPE_CHECKING:
    from .state import GameState

CLIP_STAY = "STAY"
CLIP_JUMP = "JUMP"
_CLIP_CODES = {CLIP_STAY: 0, CLIP_JUMP: 1}
_CLIP_NAMES = {v: k for k, v in _CLIP_CODES.items()}

#: Field order of :func:`enemy_to_tuple` (bools as 0/1, clip STAY 0 / JUMP 1).
ENEMY_TUPLE_FIELDS = (
    "spawned",
    "released",
    "x",
    "y",
    "x16",
    "y16",
    "vx16",
    "vy16",
    "facing_left",
    "rest",
    "ground",
    "turn_next",
    "clip",
    "pose",
    "pose_phase",
    "hops",
)


def new_enemies(level) -> list[Henchlemming]:
    """One unspawned :class:`Henchlemming` per ``Henc*`` placement, in order."""
    out: list[Henchlemming] = []
    for entry in level.gnmy:
        if (entry.name or "")[:4] != "Henc":
            continue
        out.append(
            Henchlemming(
                index=len(out),
                place_x=entry.x,
                place_y=entry.y,
                flags=entry.flags,
                x=entry.x,
                y=entry.y,
                static_fallback=bool(entry.flags & GENERATOR_SPAWNED_FLAG),
            )
        )
    return out


def init_enemy(e: Henchlemming) -> None:
    """The init ``0x42DD70`` (§2.13.b), also run at every (re)spawn."""
    e.x, e.y = e.place_x, e.place_y
    e.x16, e.y16 = e.x << 16, e.y << 16
    e.vx16 = e.vy16 = 0
    e.clip, e.pose, e.pose_phase = CLIP_STAY, 0, 0
    e.facing_left = bool(e.x & HENCH_FACING_BIT)
    e.ground = HENCH_GROUND_TICKS
    e.turn_next = 0
    e.rest = e.x & HENCH_FIRST_REST_MASK
    e.spawned = True
    e.released = False


def _landing_probe(level, e: Henchlemming) -> int:
    """``0x414450`` (§2.13.c): 0 airborne, 1 landed, 2 landed on a steep slope."""
    if e.vy16 < 0:
        e.vy16 |= 1  # the 1/65536 drift that keeps vy != 0 on a flat hop [V]
        return 0
    found = level.floor_probe(e.x, e.y, PROBE_ROWS)
    if found is None:
        return 0
    surface, kind, rising_right = found
    if e.vy16 != 0 and (surface > e.y or e.y - surface >= LANDING_DEPTH_LIMIT):
        return 0
    e.y = surface
    e.y16 = (surface << 16) | (e.y16 & 0xFFFF)
    e.vy16 = 0
    if kind == FLOOR_KIND_STEEP:
        uphill = (e.vx16 > 0 and rising_right) or (e.vx16 < 0 and not rising_right)
        if uphill:
            e.vx16 = -e.vx16
            e.facing_left = not e.facing_left
        return 2
    return 1


def look_ahead_turns(level, e: Henchlemming, n: int = HENCH_LOOKAHEAD_COLUMNS) -> bool:
    """``0x414510`` without the entity-wall branch (§2.13.e): ``True`` = turn."""
    step = -LOOKAHEAD_COLUMN_PX if e.facing_left else LOOKAHEAD_COLUMN_PX
    for k in range(n + 1):
        found = level.floor_probe(e.x + k * step, e.y, PROBE_ROWS)
        if found is None:
            return True
        surface, kind, _rising = found
        if kind == FLOOR_KIND_STEEP or abs(surface - e.y) >= LOOKAHEAD_STEP_LIMIT:
            return True
    return False


def same_kind_ahead(e: Henchlemming, others) -> bool:
    """``0x4146A0(self, 80)`` (§2.13.d.2): another living one ahead within 80 px."""
    for o in others:
        if o is e or not o.spawned:
            continue
        if abs(o.y - e.y + HENCH_AHEAD_Y_OFFSET) >= HENCH_AHEAD_Y_WINDOW:
            continue
        if e.facing_left:
            if e.x - HENCH_AHEAD_SAME_KIND < o.x < e.x:
                return True
        elif e.x < o.x < e.x + HENCH_AHEAD_SAME_KIND:
            return True
    return False


def _air_pose(vy16: int) -> int:
    for pose, limit in enumerate(HENCH_POSE_THRESHOLDS, start=1):
        if vy16 < limit:
            return pose
    return len(HENCH_POSE_THRESHOLDS) + 1


def step_enemy(level, e: Henchlemming, others, hero_x: int, stay_clip=None) -> None:
    """One update of a living enemy (§2.13.b table, states 2-4)."""
    if e.rest > 0:
        e.rest -= 1
        if e.rest > 0:
            e.clip = CLIP_STAY
            rate = stay_clip.rate if stay_clip else 0
            e.pose_phase += rate
            if stay_clip and stay_clip.poses:
                e.pose_phase %= len(stay_clip.poses) << 8
            e.pose = e.pose_phase >> 8
            return
    if e.ground != 0:
        e.clip, e.pose = CLIP_JUMP, 0
        e.ground -= 1
        if e.ground != 0:
            return
        if e.rest < 0:  # after a landing: choose the next rest
            if ((e.x ^ hero_x) & HENCH_REST_MATCH_MASK) != 0:
                e.rest = HENCH_SHORT_REST
            else:
                e.turn_next = 1
                e.rest = HENCH_LONG_REST_BASE + (e.x & HENCH_LONG_REST_MASK)
            e.ground = HENCH_GROUND_TICKS
            return
        # after a rest: take-off, three toggles in order, none re-checked
        if e.turn_next:
            e.turn_next = 0
            e.facing_left = not e.facing_left
        if same_kind_ahead(e, others):
            e.facing_left = not e.facing_left
        if look_ahead_turns(level, e):
            e.facing_left = not e.facing_left
        e.vx16 = -HENCH_TAKEOFF_VX if e.facing_left else HENCH_TAKEOFF_VX
        e.vy16 = HENCH_TAKEOFF_VY
        e.hops += 1
        return
    # airborne
    e.clip = CLIP_JUMP
    e.vy16 += HENCH_GRAVITY
    e.y16 += e.vy16
    e.x16 += e.vx16
    e.x, e.y = e.x16 >> 16, e.y16 >> 16
    if _landing_probe(level, e):
        e.ground = HENCH_GROUND_TICKS
        e.rest = -1
    else:
        e.pose = _air_pose(e.vy16)


def _hero_x(state: GameState) -> int:
    p = state.player
    return int(p.x + p.width / 2)


def step_enemies(state: GameState) -> None:
    """Spawn -> update -> despawn for one tick (§2.13.f), before the hero steps."""
    if state.game_over:
        return
    enemies = state.entities.enemies
    if not enemies:
        return
    level, cam, tick = state.level, state.camera, state.tick_count
    cx, cy = cam.cam_x, cam.cam_y
    if tick % HENCH_SPAWN_PERIOD == HENCH_SPAWN_PHASE_TICK:
        mx, my = HENCH_SPAWN_MARGIN
        # The original's extra 0x59F1DC exclusion window is not modelled [H].
        for e in enemies:
            if e.spawned or e.static_fallback:
                continue
            if (
                cx - mx <= e.place_x <= cx + VIEW_W + mx
                and cy - my <= e.place_y <= cy + VIEW_H + my
            ):
                init_enemy(e)
    stay = getattr(level, "enemy_clips", {}).get(CLIP_STAY)
    hero_x = _hero_x(state)
    for e in enemies:
        if e.spawned:
            step_enemy(level, e, enemies, hero_x, stay)
    if tick % HENCH_DESPAWN_PERIOD == HENCH_DESPAWN_PHASE_TICK:
        mx, my = HENCH_DESPAWN_MARGIN
        for e in enemies:
            if e.spawned and not (
                cx - mx <= e.x <= cx + VIEW_W + mx
                and cy - my <= e.y <= cy + VIEW_H + my
            ):
                e.spawned = False
                e.released = True


def enemy_to_tuple(e: Henchlemming) -> tuple[int, ...]:
    """Flat int tuple in :data:`ENEMY_TUPLE_FIELDS` order."""
    return (
        int(e.spawned),
        int(e.released),
        e.x,
        e.y,
        e.x16,
        e.y16,
        e.vx16,
        e.vy16,
        int(e.facing_left),
        e.rest,
        e.ground,
        e.turn_next,
        _CLIP_CODES[e.clip],
        e.pose,
        e.pose_phase,
        e.hops,
    )


def apply_tuple(e: Henchlemming, data: tuple[int, ...]) -> None:
    """Inverse of :func:`enemy_to_tuple` onto an existing placement record."""
    (
        spawned,
        released,
        e.x,
        e.y,
        e.x16,
        e.y16,
        e.vx16,
        e.vy16,
        facing,
        e.rest,
        e.ground,
        e.turn_next,
        clip,
        e.pose,
        e.pose_phase,
        e.hops,
    ) = data
    e.spawned, e.released, e.facing_left = bool(spawned), bool(released), bool(facing)
    e.clip = _CLIP_NAMES[clip]


def enemies_report(state: GameState) -> str:
    """The ``enemies:`` block of the slice report."""
    enemies = state.entities.enemies
    if not enemies:
        return "enemies: none"
    static = sum(e.static_fallback for e in enemies)
    summary = (
        f"enemies: {len(enemies)} Henchlemming, {len(enemies) - static} moving, "
        f"{static} static fallback [H]"
    )
    lines = [summary]
    for i, e in enumerate(enemies):
        head = f"  henchlemming {i}: ({e.place_x}, {e.place_y}) -> ({e.x}, {e.y}) at tick {state.tick_count}, "
        if e.static_fallback:
            tail = (
                f"clip {e.clip} (static fallback [H]: Generator-spawned, "
                "the Generator is not ported)"
            )
        elif e.spawned:
            tail = f"clip {e.clip}, {e.hops} hops"
        elif e.released:
            tail = f"released, {e.hops} hops"
        else:
            tail = f"not yet spawned, {e.hops} hops"
        lines.append(head + tail)
    lines.append(
        "  rules: hop-only STAY/JUMP, turns at ledges/walls/same-kind [V §2.13]; "
        "wake = spawn 80x80 / release 160x110 windows around the camera [V]; "
        "contact, stomp and kill are FL15 (enemies are harmless and unkillable here)"
    )
    return "\n".join(lines)
