"""FL8: the jump gravity gate, hold-to-rise and the fresh-entry start state.

Numbers come from the hero update (``docs/file-formats.md`` §2.9 / §2.10.c):
lockout gate, hold counter ``0x59E94C``, start feet offset.  Synthetic levels only.
"""

from __future__ import annotations

from lomax_modern.engine import Input, Player, load_level, new_game_state, step_player
from lomax_modern.engine.entities import (
    GRAVITY,
    JUMP_HOLD_RELEASED,
    JUMP_HOLD_START,
    JUMP_HOLD_STEP,
    JUMP_SPEED,
    START_FEET_OFFSET_Y,
)
from lomax_modern.engine.state import _feet
from tests.fixtures.synth import (
    build_container,
    cell_payload,
    gnmy_payload,
    head_payload,
    map_payload,
    ttab_payload,
)

ROWS = 12
FLOOR_Y = (ROWS - 1) * 16 - 14  # grounded top-left y of a 14 px box


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


def _flat(tmp_path, width: int = 40):
    grid = [[0] * width for _ in range(ROWS)]
    grid[ROWS - 1] = [1] * width
    path = tmp_path / "jump.WLD"
    path.write_bytes(_world_bytes(width, ROWS, grid))
    return load_level(path)


def _launch(level, *, right: bool, held: bool, ticks: int):
    """Launch from the floor, then ``ticks - 1`` more ticks; return the per-tick log."""
    player = Player(x=16.0, y=float(FLOOR_Y), on_ground=True)
    log = []
    for tick in range(ticks):
        inp = Input(right=right, jump=held or tick == 0)
        step_player(level, player, inp)
        log.append((player.x, player.y, player.vy, player.on_ground, player.jump_hold))
    return player, log


def test_constants() -> None:
    assert JUMP_HOLD_START == 0x9800
    assert JUMP_HOLD_STEP == 0x800
    assert JUMP_HOLD_RELEASED == -1
    assert START_FEET_OFFSET_Y == 40


def test_moving_jump_hangs_five_ticks_then_moves_on_the_sixth(tmp_path) -> None:
    _, log = _launch(_flat(tmp_path), right=True, held=False, ticks=6)
    for tick in range(5):
        x, y, vy, on_ground, _ = log[tick]
        assert (y, vy, on_ground) == (float(FLOOR_Y), JUMP_SPEED, False), tick
        assert x == 16.0 + 2.0 * (tick + 1)  # x keeps moving while hanging
    assert log[5][1] != float(FLOOR_Y)
    assert log[5][2] == JUMP_SPEED + GRAVITY  # tapped: no hold assist


def test_straight_jump_hangs_ten_ticks_then_moves_on_the_eleventh(tmp_path) -> None:
    _, log = _launch(_flat(tmp_path), right=False, held=False, ticks=11)
    for tick in range(10):
        x, y, vy, on_ground, _ = log[tick]
        assert (x, y, vy, on_ground) == (16.0, float(FLOOR_Y), JUMP_SPEED, False), tick
    assert log[10][1] == FLOOR_Y + JUMP_SPEED + GRAVITY


def test_held_jump_first_moving_tick_subtracts_0x9000(tmp_path) -> None:
    _, log = _launch(_flat(tmp_path), right=True, held=True, ticks=6)
    assert [entry[4] for entry in log[:5]] == [JUMP_HOLD_START] * 5  # gated: no rise
    assert log[5][2] == JUMP_SPEED - 0x9000 / 65536 + GRAVITY
    assert log[5][4] == 0x9000


def test_hold_counter_sequence_runs_down_to_zero(tmp_path) -> None:
    _, log = _launch(_flat(tmp_path), right=True, held=True, ticks=5 + 21)
    counters = [entry[4] for entry in log[5:]]
    assert counters[:19] == [0x9000 - n * 0x800 for n in range(19)]  # ends at 0
    assert counters[19:] == [0, 0]  # a zero counter does nothing more


def test_release_cuts_the_assist(tmp_path) -> None:
    level = _flat(tmp_path)
    player = Player(x=16.0, y=float(FLOOR_Y), on_ground=True)
    for tick in range(5 + 3):
        step_player(level, player, Input(right=True, jump=True))
    assert player.jump_hold == 0x9000 - 2 * 0x800
    step_player(level, player, Input(right=True, jump=False))
    assert player.jump_hold == JUMP_HOLD_RELEASED
    vy_before = player.vy
    step_player(level, player, Input(right=True, jump=True))  # re-press: no rise
    assert player.vy == vy_before + GRAVITY


def _apex_by_hand(*, held: bool, frozen_ticks: int) -> float:
    """Closed-form loop of the brief's rule: the lowest y reached from FLOOR_Y."""
    y, vy, counter = float(FLOOR_Y), JUMP_SPEED, JUMP_HOLD_START
    apex = y
    for _ in range(frozen_ticks, 400):
        if held and counter > 0:
            counter -= 0x800
            vy -= counter / 65536
        vy += GRAVITY
        y += vy
        apex = min(apex, y)
        if vy > 0:
            break
    return apex


def test_held_arc_is_strictly_higher_than_the_tapped_arc(tmp_path) -> None:
    level = _flat(tmp_path)
    apexes = {}
    for held in (True, False):
        player = Player(x=16.0, y=float(FLOOR_Y), on_ground=True)
        apex = player.y
        for tick in range(400):
            step_player(level, player, Input(jump=held or tick == 0))
            apex = min(apex, player.y)
            if player.vy > 0:
                break
        apexes[held] = apex
        assert apex == _apex_by_hand(held=held, frozen_ticks=10)
    assert apexes[True] < apexes[False]


def test_snapshot_carries_jump_hold_and_old_snapshots_default() -> None:
    from lomax_modern.engine.state import Snapshot

    data = {
        "world": "w", "playfield": 0, "tick": 0, "complete": False, "x": 0.0,
        "y": 0.0, "vx": 0.0, "vy": 0.0, "on_ground": True, "collected": [],
    }  # fmt: skip
    assert Snapshot.from_dict(data).jump_hold == JUMP_HOLD_RELEASED
    assert (
        Snapshot.from_dict({**data, "jump_hold": 0x9000}).to_dict()["jump_hold"]
        == 0x9000
    )


def _start_level(tmp_path, sx: int, sy: int):
    from tests.unit.test_gnmy_semantics import _load, _world

    return _load(
        tmp_path,
        _world(20, 15, [(0, sx, sy, 0x0000, (1,), None)], nmy_names=("Start",)),
    )


def test_start_placement_puts_the_feet_forty_px_above(tmp_path) -> None:
    state = new_game_state(_start_level(tmp_path, 89, 407))
    assert _feet(state.player) == (89, 407 - 40)
    assert state.player.facing == 1
    assert state.player.jump_straight is True


def test_explicit_spawn_keeps_the_top_left_meaning(tmp_path) -> None:
    state = new_game_state(_start_level(tmp_path, 89, 407), spawn_x=5.0, spawn_y=6.0)
    assert (state.player.x, state.player.y) == (5.0, 6.0)
    assert Player(x=0.0, y=0.0).jump_straight is False
