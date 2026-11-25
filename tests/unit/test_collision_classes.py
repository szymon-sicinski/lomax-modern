"""Collision classes (FL7): synthetic ``MAP`` fixtures only."""

from __future__ import annotations

import pytest

from lomax_modern import art
from lomax_modern.engine import CollisionModel, Input, Player, step_player
from lomax_modern.engine.level import L1_COLLISION_VALUES, OUT_OF_BOUNDS_COLLISION
from tests.unit.test_engine import _load

M = CollisionModel()


def _grid(w, h, cells):
    grid = [[0] * w for _ in range(h)]
    for (x, y), b in cells.items():
        grid[y][x] = b
    return grid


def _run(level, player, inp=None, ticks=1):
    for _ in range(ticks):
        step_player(level, player, inp or Input())


def _feet(player):
    return player.y + player.height


def test_empty_is_passable() -> None:
    assert M.kind(0) == "empty"
    assert not M.is_solid(0) and not M.one_way(0)


def test_flat_c0_and_c8_identical() -> None:
    for xi in range(16):
        assert M.floor_offset(0xC0, xi) == M.floor_offset(0xC8, xi) == 16
    assert M.floor_kind(0xC0) == M.floor_kind(0xC8) == 0


@pytest.mark.parametrize(
    ("byte", "xi0", "xi15"),
    [
        (0xD0, 8, 15),
        (0xD8, 15, 8),
        (0xE0, 0, 7),
        (0xE8, 7, 0),
        (0xF0, 0, 15),
        (0xF8, 15, 0),
    ],
)
def test_slope_shapes_and_mirror(byte, xi0, xi15) -> None:
    assert M.floor_offset(byte, 0) == xi0
    assert M.floor_offset(byte, 15) == xi15
    assert M.floor_kind(byte) == (2 if (byte & 0x30) == 0x30 else 1)


def test_unknown_bytes_stay_solid() -> None:
    for b in (0x01, 0x91, 0xA0):
        assert M.is_solid(b) and not M.one_way(b)
        assert "conservative" in M.describe(b) and "[H]" in M.describe(b)


def test_off_map_solid_and_no_floor(tmp_path) -> None:
    level = _load(tmp_path, 2, 2, _grid(2, 2, {}))
    assert OUT_OF_BOUNDS_COLLISION == 0xFF and M.one_way(0xFF)
    assert level.solid_at(-1, 0) and level.solid_at(2, 0) and level.solid_at(0, 2)
    assert level.floor_at(-1, 20) is None and level.floor_at(32, 20) is None
    assert level.floor_at(4, 8) is None  # feet_y < 16


def test_falling_player_lands_on_flat_floor(tmp_path) -> None:
    level = _load(tmp_path, 4, 4, _grid(4, 4, {(x, 2): 0xC0 for x in range(4)}))
    player = Player(x=10.0, y=0.0)
    _run(level, player, ticks=60)
    assert player.on_ground and player.vy == 0.0
    assert _feet(player) == 48  # bottom edge of the floor cell (row 2)


def test_one_way_jump_up_through_then_land(tmp_path) -> None:
    cells = {(x, 3): 0xC0 for x in range(4)} | {(x, 5): 1 for x in range(4)}
    level = _load(tmp_path, 4, 6, _grid(4, 6, cells))
    player = Player(x=10.0, y=66.0)  # below the floor row, above the solid row
    _run(level, player, ticks=40)
    assert player.on_ground and _feet(player) == 80  # standing on the solid row
    _run(level, player, Input(jump=True))
    top = _feet(player)
    landed = False
    for _ in range(80):
        _run(level, player)
        top = min(top, _feet(player))
        if player.on_ground and _feet(player) == 64:
            landed = True
            break
    assert top < 64  # rose through the one-way floor
    assert landed  # and landed on it while falling


def test_falling_from_below_the_surface_does_not_land(tmp_path) -> None:
    # Feet 4 px under the surface at the start of the tick (prev_floor < prev_y):
    # a one-way floor never catches a player who is already below it.
    level = _load(tmp_path, 4, 6, _grid(4, 6, {(x, 3): 0xC0 for x in range(4)}))
    player = Player(x=10.0, y=64.0 + 4 - 14)  # feet 68; row 3's bottom edge is 64
    _run(level, player)
    assert not player.on_ground
    assert _feet(player) > 68


def test_floor_does_not_block_sideways(tmp_path) -> None:
    grid = _grid(6, 4, {(x, 3): 1 for x in range(6)})
    grid[2][2] = 0xC0  # floor cell level with the walking player's body
    level = _load(tmp_path, 6, 4, grid)
    player = Player(x=4.0, y=34.0)
    _run(level, player, Input(right=True), ticks=20)
    assert player.x > 20.0


def _rising_right(level, feet_bottom, vy_after_gravity):
    """A player at column 1 (feet_x 20 -> 22) moving right with a given vy."""
    player = Player(x=14.0, y=feet_bottom - 14.0, vy=vy_after_gravity - 0.375)
    _run(level, player, Input(right=True))
    return player


def test_vy_gate_rising_fast_does_not_land(tmp_path) -> None:
    # 0xE8 rises to the right: surface 53 at xi=4, 52 at xi=6.  Start feet int 53
    # (floor0 >= feet0), end feet ~52.1 >= 52, so only the vy gate decides.
    level = _load(tmp_path, 4, 6, _grid(4, 6, {(1, 3): 0xE8}))
    assert level.floor_at(20, 53) == (53, 1) and level.floor_at(22, 53) == (52, 1)
    assert not _rising_right(level, 53.9, -1.8).on_ground  # faster than -1.5
    assert _rising_right(level, 53.9, -1.2).on_ground  # slower: lands
    flat = _load(tmp_path, 4, 6, _grid(4, 6, {(1, 3): 0xC0}))
    assert not _rising_right(flat, 63.9, -0.5).on_ground  # kind 0 needs vy > 0


def test_vy_gate_steep_kind(tmp_path) -> None:
    # 0xF8: surface 59 at xi=4, 57 at xi=6; gate -3.25.
    level = _load(tmp_path, 4, 6, _grid(4, 6, {(1, 3): 0xF8}))
    assert not _rising_right(level, 59.9, -3.4).on_ground
    ok = _rising_right(level, 59.9, -2.8)
    assert ok.on_ground and _feet(ok) == 57


def test_follows_descending_slope(tmp_path) -> None:
    grid = _grid(4, 4, {(0, 2): 0xE0, (1, 2): 0xD0, (2, 2): 0xC0, (3, 2): 0xC0})
    level = _load(tmp_path, 4, 4, grid)
    player = Player(x=0.0, y=0.0)
    _run(level, player, ticks=60)
    assert player.on_ground
    ys = []
    for _ in range(12):
        _run(level, player, Input(right=True))
        assert player.on_ground
        ys.append(player.y)
    assert ys[-1] > ys[0]  # the surface descends to the right and the feet follow


def test_report_lines_and_residues() -> None:
    lines = M.report().splitlines()
    assert lines[0].startswith("collision: FL2 classes [V]")
    for value in L1_COLLISION_VALUES:
        assert (
            sum(1 for line in lines if line.strip().startswith(f"{value:#04x}:")) == 1
        )
    assert "still [H]:" in lines[-1] and "0x410F63" in lines[-1] and "Q52" in lines[-1]
    assert "0x91" in M.report(extra_values=[0x91])
    assert (
        M.describe(0xD0)
        == "0xd0: floor, shallow lower half, descends right, one-way [V]"
    )


def test_flip_pairing_h_mirrors_columns_v_rows() -> None:
    pixels = bytes(range(64))
    cell = art.Cell(index=0, pixels=pixels)
    rows = art.cell_rows(cell)
    assert art.flipped_rows(cell, art.FLIP_H) == [row[::-1] for row in rows]
    assert art.flipped_rows(cell, art.FLIP_V) == rows[::-1]
