"""FL11 rules: lives, fail/respawn, Revive, coins, Exit trigger, game over.

Synthetic worlds only (no game bytes).  Placement types index the ``NMY`` names
``("Start", "Exit", "Moneybag", "Revive")``.
"""

from __future__ import annotations

from pathlib import Path

from lomax_modern.engine import (
    Collectible,
    Exit,
    Input,
    load_level,
    new_game_state,
    run_slice,
)
from lomax_modern.engine.entities import (
    COINS_PER_LIFE,
    MAX_LIVES,
    STARTING_LIVES,
)
from lomax_modern.engine.state import Snapshot, capture, restore
from tests.fixtures.synth import (
    build_container,
    cell_payload,
    gnmy_entries_payload,
    head_payload,
    map_payload,
    nmy_payload,
    ttab_payload,
)

NAMES = ("Start", "Exit", "Moneybag", "Revive")
START, EXIT, MONEYBAG, REVIVE = 0, 1, 2, 3


def _world(width: int, height: int, entries, *, floor: bool) -> bytes:
    """``width`` x ``height`` cells; ``floor`` makes the bottom row solid."""
    cells = [
        (0, 1 if floor and y == height - 1 else 0)
        for y in range(height)
        for _ in range(width)
    ]
    chunks = [
        ("WRLD", b"PS-X" + b"\0" * 4),
        ("NMY", nmy_payload([(name, 0) for name in NAMES], trailer=2)),
        ("PARA", b"\0" * 8),
        ("HEAD", head_payload(width * 2, height * 2)),
        ("TTAB", ttab_payload([[0, 0, 0, 0, 0, 0, 0, 0]])),
        ("MAP", map_payload(width * 2, height * 2, cells=cells)),
        ("GNMY", gnmy_entries_payload(entries)),
        ("MACR", b"\0" * 8),
        ("PAGE", b"\0" * 8),
        ("CELL", cell_payload([bytes(64)])),
        ("ANIM", b"\0" * 20),
        ("END", b""),
    ]
    return build_container(chunks, endian=">")


def _entry(kind: int, x: int, y: int):
    return (kind, x, y, 0x0000, (1,), None)


def _level(tmp_path: Path, entries, *, floor: bool = False, width=8, height=6):
    path = tmp_path / "TEST.WLD"
    path.write_bytes(_world(width, height, entries, floor=floor))
    return load_level(path), path


#: Start (64, 60) -> feet (64, 20); a 96 px tall plane with no floor is a pit.
PIT = [_entry(START, 64, 60)]


def _run_until(state, predicate, limit=2000) -> None:
    for _ in range(limit):
        if predicate():
            return
        state.tick(Input())
    raise AssertionError("condition never reached")


def _feet(state) -> tuple[float, float]:
    return state.player.centre_x, state.player.y + state.player.height


# ---------------------------------------------------------------------------


def test_starts_with_three_lives(tmp_path: Path) -> None:
    level, _ = _level(tmp_path, PIT)
    state = new_game_state(level)
    assert STARTING_LIVES == 3
    assert (state.lives, state.coins, state.game_over, state.complete) == (3, 0, False, False)
    assert state.events == []


def test_leaving_through_the_bottom_takes_a_life_and_respawns_at_start(
    tmp_path: Path,
) -> None:
    level, _ = _level(tmp_path, PIT)
    state = new_game_state(level)
    _run_until(state, lambda: state.lives < 3)
    assert state.lives == 2 and not state.game_over
    assert state.events == [
        f"life lost at tick {state.tick_count - 1}: lives 3 -> 2, respawn (64, 20)"
    ]
    assert _feet(state) == (64.0, 20.0)
    assert (state.player.vx, state.player.vy) == (0.0, 0.0)
    assert state.player.jump_straight is True  # Start respawn


def test_respawn_goes_to_the_touched_revive(tmp_path: Path) -> None:
    level, _ = _level(tmp_path, PIT + [_entry(REVIVE, 64, 50)])
    assert level.revives == ((64, 50),)
    state = new_game_state(level)
    _run_until(state, lambda: state.lives < 3)
    assert state.entities.touched_revive == 0
    assert state.events[0].endswith("lives 3 -> 2, respawn (64, 50)")
    assert _feet(state) == (64.0, 50.0)
    assert state.player.jump_straight is False  # Revive respawn: state 0
    assert (state.player.vx, state.player.vy) == (0.0, 0.0)


def test_third_loss_is_game_over_and_the_player_stops(tmp_path: Path) -> None:
    level, _ = _level(tmp_path, PIT)
    state = new_game_state(level)
    _run_until(state, lambda: state.game_over)
    assert state.lives == 0
    assert state.events[-1] == f"game over at tick {state.tick_count - 1}"
    assert sum(e.startswith("life lost") for e in state.events) == 3
    pos = (state.player.x, state.player.y)
    ticks = state.tick_count
    for _ in range(5):
        state.tick(Input(right=True))
    assert (state.player.x, state.player.y) == pos
    assert state.lives == 0
    assert state.tick_count == ticks + 5


def test_no_life_lost_while_complete(tmp_path: Path) -> None:
    level, _ = _level(tmp_path, PIT)
    state = new_game_state(level)
    state.complete = True
    for _ in range(40):
        state.tick(Input())
    assert state.lives == 3 and state.events == []


# --- Exit ------------------------------------------------------------------


def _exit_state(tmp_path: Path, exits):
    level, _ = _level(tmp_path, [], floor=True, width=8, height=4)  # 128 x 64 px
    return new_game_state(level, spawn_x=0.0, spawn_y=0.0, exits=exits)


def _place(state, centre_x: float, *, grounded: bool = True) -> None:
    # Feet at the floor top (y = 48); grounded or hovering well above it.
    state.player.x = centre_x - state.player.width / 2
    state.player.y = 34.0 if grounded else 10.0
    state.player.on_ground = grounded
    state.player.vy = 0.0


def test_exit_fires_only_past_width_minus_50(tmp_path: Path) -> None:
    state = _exit_state(tmp_path, [Exit(0, 0, px_y=48)])
    _place(state, 78.0)  # width 128 - 50 = 78: strictly greater is required
    state.tick(Input())
    assert not state.complete
    _place(state, 79.0)
    state.tick(Input())
    assert state.complete


def test_exit_ignores_its_own_x(tmp_path: Path) -> None:
    for cell_x in (0, 7):
        state = _exit_state(tmp_path, [Exit(cell_x, 3, px_y=48)])
        _place(state, 100.0)
        state.tick(Input())
        assert state.complete


def test_exit_y_tolerance_is_48_px(tmp_path: Path) -> None:
    for exit_y, expected in ((48 + 47, True), (48 - 47, True), (48 + 48, False), (48 - 48, False)):
        state = _exit_state(tmp_path, [Exit(0, 0, px_y=exit_y)])
        _place(state, 100.0)
        state.tick(Input())
        assert state.complete is expected, exit_y


def test_exit_falls_back_to_the_cell_row_without_px_y(tmp_path: Path) -> None:
    state = _exit_state(tmp_path, [Exit(0, 3)])  # cell row 3 -> y 48
    _place(state, 100.0)
    state.tick(Input())
    assert state.complete


def test_airborne_hero_at_the_exit_does_not_complete(tmp_path: Path) -> None:
    state = _exit_state(tmp_path, [Exit(0, 0, px_y=48)])
    _place(state, 100.0, grounded=False)
    state.tick(Input())
    assert not state.player.on_ground
    assert not state.complete


# --- Coins -----------------------------------------------------------------


def _coin_state(tmp_path: Path, bags: int):
    level, _ = _level(tmp_path, [], floor=True, width=8, height=4)
    return new_game_state(
        level, spawn_x=0.0, spawn_y=34.0, collectibles=[Collectible(0, 2)] * bags
    )


def test_a_moneybag_is_three_coins(tmp_path: Path) -> None:
    state = _coin_state(tmp_path, 1)
    state.tick(Input())
    assert state.entities.collected == {0}
    assert (state.coins, state.lives) == (3, 3)


def test_hundred_coins_make_a_life(tmp_path: Path) -> None:
    assert COINS_PER_LIFE == 100
    state = _coin_state(tmp_path, 34)  # 102 coins
    state.tick(Input())
    assert (state.coins, state.lives) == (2, 4)


def test_lives_are_capped_at_thirty(tmp_path: Path) -> None:
    state = _coin_state(tmp_path, 34)
    state.lives = MAX_LIVES
    state.tick(Input())
    assert (state.coins, state.lives) == (2, 30)


# --- Snapshot --------------------------------------------------------------


def test_snapshot_round_trips_the_rule_fields(tmp_path: Path) -> None:
    level, _ = _level(tmp_path, PIT + [_entry(REVIVE, 64, 50)])
    state = new_game_state(level)
    _run_until(state, lambda: state.lives < 3)
    state.coins = 7
    snap = capture(state)
    assert (snap.lives, snap.coins, snap.game_over, snap.touched_revive) == (2, 7, False, 0)
    assert Snapshot.from_dict(snap.to_dict()) == snap
    state.lives, state.coins, state.entities.touched_revive = 1, 0, None
    state.game_over = True
    restore(state, snap)
    assert (state.lives, state.coins, state.game_over) == (2, 7, False)
    assert state.entities.touched_revive == 0


def test_old_snapshot_dicts_still_load() -> None:
    old = {
        "world": "w", "playfield": 0, "tick": 0, "complete": False, "x": 0.0,
        "y": 0.0, "vx": 0.0, "vy": 0.0, "on_ground": False, "collected": [],
    }
    snap = Snapshot.from_dict(old)
    assert (snap.lives, snap.coins, snap.game_over, snap.touched_revive) == (3, 0, False, None)


# --- run_slice -------------------------------------------------------------


def test_run_slice_reports_lives_and_game_over(tmp_path: Path) -> None:
    _, path = _level(tmp_path, PIT)
    report, _frame = run_slice(tmp_path, world_path=path, max_ticks=500)
    text = report.format()
    assert report.game_over and report.lives == 0
    assert len(report.events) == 4  # three losses and the game over
    assert "life lost at tick" in text
    assert f"result: game over at tick {report.ticks}" in text
    assert "lives: 0, coins: 0" in text
    assert "rules: lives 3 start [V]; fail rule = box bottom reaches plane bottom [H]" in text
    assert text.index("life lost at tick") < text.index("result: game over")


def test_run_slice_reports_level_complete(tmp_path: Path) -> None:
    # Start feet (100, 48) = on the floor top of a 4-row plane; Exit at y 48.
    entries = [_entry(START, 100, 88), _entry(EXIT, 0, 48)]
    _, path = _level(tmp_path, entries, floor=True, width=8, height=4)
    report, _frame = run_slice(tmp_path, world_path=path, max_ticks=60)
    assert report.complete and not report.game_over
    assert f"result: level complete at tick {report.ticks}" in report.format()
    assert "reached exit" not in report.format()
