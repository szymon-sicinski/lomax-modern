"""AN4: the air states (``JMP1``/``JMP2``/``FLO1``/``FLO2``) and the ``LND1`` landing.

Rules graded here come from ``docs/file-formats.md`` §2.6.2 a rows 14-21 and 26,
b (jumps, landing, falling) and d ("Air poses follow ``vy``, not time").  Every
level is synthetic; the player is driven with real ticks.
"""

from __future__ import annotations

import pytest

from lomax_modern.engine import Input, Player, load_level, select_clip, step_player
from lomax_modern.engine.entities import JUMP_STRAIGHT_AT_LEVEL_START
from lomax_modern.engine.state import (
    air_clip_rate_px256,
    air_pose_from_vy,
)
from tests.fixtures.synth import (
    build_container,
    cell_payload,
    gnmy_payload,
    head_payload,
    map_payload,
    ttab_payload,
)

STAND, WALK, RUN = "STA1", "WALK", "RUN"
LAND, JUMP, JUMP_MOVING, FALL, FALL_MOVING = "LND1", "JMP1", "JMP2", "FLO1", "FLO2"
AIR_TAGS = {JUMP, JUMP_MOVING, FALL, FALL_MOVING}


def _world_bytes(width_cells: int, height_cells: int, grid: list[list[int]]) -> bytes:
    cells = [(0, grid[y][x]) for y in range(height_cells) for x in range(width_cells)]
    chunks = [
        ("WRLD", b"PS-X" + b"\0" * 4),
        ("NMY", b"\0" * 16),
        ("PARA", b"\0" * 8),
        ("HEAD", head_payload(width_cells * 2, height_cells * 2)),
        ("TTAB", ttab_payload([[0, 0, 0, 0, 0, 0, 0, 0]])),
        ("MAP", map_payload(width_cells * 2, height_cells * 2, cells=cells)),
        ("GNMY", gnmy_payload((0,))),
        ("MACR", b"\0" * 8),
        ("PAGE", b"\0" * 8),
        ("CELL", cell_payload([bytes(64)])),
        ("ANIM", b"\0" * 20),
        ("END", b""),
    ]
    return build_container(chunks, endian=">")


def _level(tmp_path, grid: list[list[int]]):
    path = tmp_path / "air.WLD"
    path.write_bytes(_world_bytes(len(grid[0]), len(grid), grid))
    return load_level(path)


def _flat(tmp_path, *, width: int = 12, height: int = 4):
    """A flat level: solid bottom row, floor at pixel ``(height - 1) * 16``."""
    grid = [[0] * width for _ in range(height)]
    grid[height - 1] = [1] * width
    return _level(tmp_path, grid)


FLAT_Y = 3 * 16 - 14  # a grounded 14 px box on the 4-row flat level


def _grounded(x: float = 0.0, y: float = FLAT_Y) -> Player:
    return Player(x=x, y=y, on_ground=True)


def _run(level, player: Player, inputs) -> list[tuple[str, int]]:
    """Tick once per input; return ``select_clip`` after each tick."""
    out = []
    for inp in inputs:
        step_player(level, player, inp)
        out.append(select_clip(player))
    return out


def _touchdown_tick(level, launch: Input, ticks_in_air: Input) -> int:
    """Index (0-based) of the tick on which a jump from rest touches down."""
    player = _grounded()
    step_player(level, player, launch)
    for index in range(1, 200):
        step_player(level, player, ticks_in_air)
        if player.on_ground:
            return index
    raise AssertionError("never landed")


# 1 ------------------------------------------------------------------------


def test_airborne_player_always_draws_an_air_clip() -> None:
    for straight in (True, False):
        for lockout in (0, 3, 10):
            for vx in (0.0, 2.0, -2.0):
                for step in range(21):
                    vy = -4.0 + step * 0.5
                    player = Player(
                        x=0.0,
                        y=0.0,
                        vx=vx,
                        vy=vy,
                        on_ground=False,
                        jump_straight=straight,
                        jump_lockout=lockout,
                    )
                    tag, _ = select_clip(player)
                    assert tag in AIR_TAGS, (straight, lockout, vx, vy, tag)
                    assert tag not in {STAND, WALK, RUN}


# 2 ------------------------------------------------------------------------


def test_straight_jump_lands_for_ten_lnd1_ticks_then_stands(tmp_path) -> None:
    level = _flat(tmp_path)
    player = _grounded()
    step_player(level, player, Input(jump=True))
    assert player.jump_straight is True
    for _ in range(200):
        step_player(level, player, Input())
        if player.on_ground:
            break
    assert player.on_ground
    tags = [select_clip(player)[0]]
    for _ in range(11):
        step_player(level, player, Input())
        tags.append(select_clip(player)[0])
    assert tags[:10] == [LAND] * 10
    assert tags[10:] == [STAND, STAND]
    assert select_clip(player) == (STAND, 0)


# 3 ------------------------------------------------------------------------


def test_moving_jump_lands_with_no_lnd1(tmp_path) -> None:
    level = _flat(tmp_path)
    player = _grounded()
    step_player(level, player, Input(jump=True, right=True))
    assert player.jump_straight is False
    for _ in range(200):
        step_player(level, player, Input(right=True))
        if player.on_ground:
            break
    assert player.on_ground
    assert select_clip(player)[0] != LAND
    for _ in range(12):
        step_player(level, player, Input())
        assert select_clip(player)[0] == STAND


# 4 ------------------------------------------------------------------------


def test_left_right_held_from_touchdown_draws_exactly_one_lnd1(tmp_path) -> None:
    level = _flat(tmp_path)
    n = _touchdown_tick(level, Input(jump=True), Input())
    player = _grounded()
    inputs = [Input(jump=True)] + [Input()] * (n - 1) + [Input(right=True)] * 6
    clips = _run(level, player, inputs)
    after = [tag for tag, _ in clips[n:]]
    assert after.count(LAND) == 1
    assert after[0] == LAND
    assert after[1] == WALK


# 5 ------------------------------------------------------------------------


@pytest.mark.parametrize("k", [1, 2, 5, 10])
def test_left_right_first_pressed_on_kth_lnd1_tick_draws_k(tmp_path, k: int) -> None:
    level = _flat(tmp_path)
    n = _touchdown_tick(level, Input(jump=True), Input())
    player = _grounded()
    inputs = (
        [Input(jump=True)]
        + [Input()] * (n - 1)
        + [Input()] * (k - 1)
        + [Input(right=True)] * 14
    )
    clips = _run(level, player, inputs)
    after = [tag for tag, _ in clips[n:]]
    assert after.count(LAND) == k
    assert after[:k] == [LAND] * k
    assert LAND not in after[k:]


# 6 ------------------------------------------------------------------------


def test_jump_kind_in_the_open_is_moving(tmp_path) -> None:
    level = _flat(tmp_path)
    player = _grounded()
    step_player(level, player, Input(jump=True, right=True))
    assert player.jump_straight is False
    assert player.jump_lockout == 5
    assert select_clip(player)[0] == JUMP_MOVING


def test_jump_kind_into_a_wall_is_straight(tmp_path) -> None:
    grid = [[0] * 8 for _ in range(4)]
    grid[3] = [1] * 8
    for row in range(3):
        grid[row][3] = 1  # wall at x = 48
    level = _level(tmp_path, grid)
    player = _grounded(x=48.0 - 12.0)
    step_player(level, player, Input(right=True))
    assert player.vx == 0.0 and player.on_ground
    step_player(level, player, Input(jump=True, right=True))
    assert player.vx == 0.0
    assert player.jump_straight is True
    assert player.jump_lockout == 10
    assert select_clip(player)[0] == JUMP


def test_fall_without_a_jump_keeps_the_last_kind(tmp_path) -> None:
    grid = [[0] * 12 for _ in range(6)]
    grid[5] = [1] * 6 + [0] * 6  # a ledge at x = 96
    level = _level(tmp_path, grid)
    player = Player(x=0.0, y=5 * 16 - 14, on_ground=True)
    step_player(level, player, Input(jump=True))
    assert player.jump_straight is True
    for _ in range(40):
        step_player(level, player, Input())
    assert player.on_ground
    for _ in range(200):
        step_player(level, player, Input(right=True))
        if not player.on_ground:
            break
    assert not player.on_ground
    assert player.jump_lockout == 0
    assert select_clip(player)[0] == JUMP


# 7 ------------------------------------------------------------------------


def test_straight_jump_lockout_poses_and_rate(tmp_path) -> None:
    level = _flat(tmp_path)
    player = _grounded()
    clips = []
    for _ in range(10):
        step_player(level, player, Input(jump=True) if not clips else Input())
        assert player.jump_lockout > 0
        assert air_clip_rate_px256(player) == 64
        clips.append(select_clip(player))
    assert clips == [(JUMP, p) for p in (0, 0, 0, 0, 1, 1, 1, 1, 2, 2)]
    step_player(level, player, Input())
    assert player.jump_lockout == 0
    assert air_clip_rate_px256(player) == 0


def test_moving_jump_lockout_poses(tmp_path) -> None:
    level = _flat(tmp_path)
    player = _grounded()
    clips = []
    for tick in range(5):
        step_player(level, player, Input(jump=True, right=True) if tick == 0 else Input(right=True))
        assert player.jump_lockout > 0
        assert air_clip_rate_px256(player) == 64
        clips.append(select_clip(player))
    assert clips == [(JUMP_MOVING, p) for p in (0, 0, 0, 0, 1)]
    step_player(level, player, Input(right=True))
    assert player.jump_lockout == 0


# 8 ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("vy", "straight", "pose"),
    [
        (1.5, True, 6),
        (1.5, False, 6),
        (1.0, True, 5),
        (1.0, False, 5),
        (0.0, True, 5),
        (-0.5, True, 4),
        (-0.5, False, 4),
        (-1.0, True, 4),
        (-2.0, True, 3),
        (-2.0, False, 3),
        (-2.5, True, 3),
        (-3.5, True, 2),
        (-3.5, False, 3),
        (-3.625, False, 3),
        (-3.875, False, 2),
        (-4.0, True, 2),
        (-4.0, False, 2),
    ],
)
def test_air_pose_follows_vy(vy: float, straight: bool, pose: int) -> None:
    assert air_pose_from_vy(vy, straight=straight) == pose
    player = Player(
        x=0.0, y=0.0, vy=vy, jump_straight=straight, jump_lockout=0, on_ground=False
    )
    assert select_clip(player) == (JUMP if straight else JUMP_MOVING, pose)
    assert air_clip_rate_px256(player) == 0


# 9 ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("straight", "tag", "rate"), [(True, FALL, 64), (False, FALL_MOVING, 68)]
)
def test_fast_fall_takes_over_after_the_lockout(straight: bool, tag: str, rate: int) -> None:
    player = Player(
        x=0.0, y=0.0, vy=2.5, jump_straight=straight, jump_lockout=0, air_frame=3
    )
    assert select_clip(player) == (tag, 3)
    assert air_clip_rate_px256(player) == rate
    player.vy = 2.49
    assert select_clip(player)[0] == (JUMP if straight else JUMP_MOVING)


def test_fast_fall_waits_for_the_lockout() -> None:
    player = Player(x=0.0, y=0.0, vy=3.0, jump_straight=True, jump_lockout=3)
    assert select_clip(player)[0] == JUMP
    assert air_clip_rate_px256(player) == 64
    player.jump_lockout = 0
    assert select_clip(player)[0] == FALL


# 10 -----------------------------------------------------------------------


def test_level_start_kind_is_one_named_constant() -> None:
    # Q40a [V] (0x42AC3B): a fresh entry is the straight kind; a bare Player keeps
    # the build's state-0 kind (moving).
    assert JUMP_STRAIGHT_AT_LEVEL_START is True
    assert Player(x=0.0, y=0.0).jump_straight is False
