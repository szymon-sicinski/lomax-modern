"""AN6: the idle cycle -- ``STA1`` held, then ``STA1``/``STA2`` played once.

``docs/file-formats.md`` §2.6.2 a rows 30-31 and d "Idle": the numbers (100 at
level start, ``30 + (rand & 63)``, 10,000 after a wrap, rates 64/68) are [V]/[M];
the counter's increment site, the reset on leaving the idle branch, row 30's
reset firing on (re-)entry and "bit 0 set means ``STA2``" are this engine's [H]
choices.  Every level is synthetic; the player is driven with real ticks.
"""

from __future__ import annotations

import itertools
import math

from lomax_modern.engine import (
    Input,
    Player,
    load_level,
    new_game_state,
    select_clip,
    step_player,
)
from lomax_modern.engine.entities import (
    IDLE_REFREEZE_THRESHOLD,
    IDLE_START_THRESHOLD,
    STA1_POSES,
    STA1_RATE,
    STA2_POSES,
    STA2_RATE,
)
from lomax_modern.engine.state import (
    IDLE_DEFAULT_SEED,
    Snapshot,
    capture,
    default_random_bits,
    restore,
)
from tests.fixtures.synth import (
    build_container,
    cell_payload,
    gnmy_payload,
    head_payload,
    map_payload,
    ttab_payload,
)

FLAT_Y = 3 * 16 - 14  # a grounded 14 px box on the 4-row flat level
STA1 = ("STA1", 0)


def _bit(value: int):
    return lambda: value


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


def _flat(tmp_path, *, width: int = 12, height: int = 4):
    grid = [[0] * width for _ in range(height)]
    grid[height - 1] = [1] * width
    path = tmp_path / "idle.WLD"
    path.write_bytes(_world_bytes(width, height, grid))
    return load_level(path)


def _grounded() -> Player:
    return Player(x=0.0, y=FLAT_Y, on_ground=True)


def _idle(level, player, n, rand):
    out = []
    for _ in range(n):
        step_player(level, player, Input(), rand=rand)
        out.append(select_clip(player))
    return out


def test_sta1_held_for_exactly_the_100_level_start_ticks(tmp_path) -> None:
    """Row 30: counter < threshold forces STA1 pose 0; threshold 100 at start."""
    assert IDLE_START_THRESHOLD == 100
    level, player = _flat(tmp_path), _grounded()
    for _ in range(100):
        step_player(level, player, Input(), rand=_bit(1))
        assert select_clip(player) == STA1
    assert player.idle_counter == 100
    assert player.idle_threshold == 100


def test_tick_101_starts_exactly_one_played_clip(tmp_path) -> None:
    """Row 31: at counter == threshold one clip is played, then row 30 re-freezes."""
    for bit, tag, poses, rate, ticks in (
        (1, "STA2", STA2_POSES, STA2_RATE, 38),
        (0, "STA1", STA1_POSES, STA1_RATE, 28),
    ):
        level, player = _flat(tmp_path), _grounded()
        rand = _bit(bit)
        _idle(level, player, 100, rand)
        step_player(level, player, Input(), rand=rand)
        assert select_clip(player) == (tag, 0)
        shown = [select_clip(player)]
        while True:
            step_player(level, player, Input(), rand=rand)
            shown.append(select_clip(player))
            if player.idle_threshold == IDLE_REFREEZE_THRESHOLD:
                break
            assert len(shown) < 100
        assert shown[-1] == STA1  # the wrap tick draws the held STA1 again
        played = shown[:-1]
        assert len(played) == ticks == math.ceil(poses * 256 / rate)
        assert {t for t, _ in played} == {tag}
        seen = [p for _, p in played]
        assert seen[0] == 0 and seen == sorted(seen) and max(seen) == poses - 1
        # the next idle tick re-freezes with a new 30..93 threshold
        step_player(level, player, Input(), rand=rand)
        assert select_clip(player) == STA1
        assert 30 <= player.idle_threshold <= 93


def test_bit_zero_picks_the_clip_and_seeds_reach_both(tmp_path) -> None:
    """Row 31 [H] mapping: bit 0 set -> STA2, clear -> STA1; seeds reach both."""
    for bit, tag in ((1, "STA2"), (0, "STA1"), (65, "STA2"), (64, "STA1")):
        level, player = _flat(tmp_path), _grounded()
        _idle(level, player, 101, _bit(bit))
        assert player.idle_clip_tag == tag
    tags = set()
    for seed in range(8):  # seeds 0..7 reach both clips (checked below)
        level, player = _flat(tmp_path), _grounded()
        _idle(level, player, 101, default_random_bits(seed))
        tags.add(player.idle_clip_tag)
    assert tags == {"STA1", "STA2"}


def test_cycle_repeats_after_the_new_threshold(tmp_path) -> None:
    """Row 30: the new threshold is 30 + (rand & 63); 65 -> 31 held ticks."""
    level, player = _flat(tmp_path), _grounded()
    rand = _bit(65)
    _idle(level, player, 101, rand)
    while player.idle_clip_tag:
        step_player(level, player, Input(), rand=rand)
    assert player.idle_threshold == IDLE_REFREEZE_THRESHOLD
    held = 0
    while True:
        step_player(level, player, Input(), rand=rand)
        held += 1
        if player.idle_clip_tag:
            break
        assert select_clip(player) == STA1
    assert player.idle_threshold == 31
    assert held == 32  # 31 held ticks, then the tick that starts the next clip


def test_played_clip_runs_at_its_own_rate(tmp_path) -> None:
    """Row 31: STA2 steps every 3/4 ticks (68), STA1 every 4 ticks (64)."""
    for bit, rate in ((1, STA2_RATE), (0, STA1_RATE)):
        level, player = _flat(tmp_path), _grounded()
        rand = _bit(bit)
        _idle(level, player, 100, rand)
        poses = [p for _, p in _idle(level, player, 20, rand)]
        change = [i for i in range(1, 20) if poses[i] != poses[i - 1]]
        expected = [i for i in range(1, 20) if i * rate // 256 != (i - 1) * rate // 256]
        assert len(change) >= 4
        assert change[:4] == expected[:4]
        gaps = {b - a for a, b in itertools.pairwise(change)}
        assert gaps <= ({3, 4} if rate == 68 else {4})


def _raise_counter(level, player, n=50):
    _idle(level, player, n, _bit(0))
    assert player.idle_counter == n


def test_moving_resets_the_idle_cycle(tmp_path) -> None:
    """Rows 30-31 [H]: leaving the idle branch resets the counter."""
    level, player = _flat(tmp_path), _grounded()
    _raise_counter(level, player)
    step_player(level, player, Input(right=True), rand=_bit(0))
    assert player.idle_counter == 0
    step_player(level, player, Input(), rand=_bit(0))
    assert select_clip(player) == STA1 and player.idle_counter == 1


def test_airborne_resets_the_idle_cycle(tmp_path) -> None:
    """Rows 30-31 [H]: a jump leaves the idle branch."""
    level, player = _flat(tmp_path), _grounded()
    _raise_counter(level, player)
    step_player(level, player, Input(jump=True), rand=_bit(0))
    assert not player.on_ground and player.idle_counter == 0
    for _ in range(3):
        step_player(level, player, Input(), rand=_bit(0))
        assert not player.on_ground and player.idle_counter == 0


def test_landing_resets_the_idle_cycle(tmp_path) -> None:
    """Row 26 outranks 30-31: LND1 ticks keep the counter at 0."""
    level, player = _flat(tmp_path), _grounded()
    _raise_counter(level, player)
    step_player(level, player, Input(jump=True), rand=_bit(0))
    lnd1 = 0
    for _ in range(60):
        step_player(level, player, Input(), rand=_bit(0))
        if player.on_ground and player.lnd1_shown:
            lnd1 += 1
            assert select_clip(player)[0] == "LND1"
            assert player.idle_counter == 0
    assert lnd1 > 0
    assert 0 < player.idle_counter < 60  # idle resumed from 0 after LND1


def test_duck_resets_the_idle_cycle(tmp_path) -> None:
    """Row 23 outranks 30-31: a duck resets the counter."""
    level, player = _flat(tmp_path), _grounded()
    _raise_counter(level, player)
    step_player(level, player, Input(down=True), rand=_bit(0))
    assert select_clip(player)[0] == "DUCK" and player.idle_counter == 0
    step_player(level, player, Input(), rand=_bit(0))
    assert select_clip(player) == STA1 and player.idle_counter == 1


def test_interrupted_play_returns_to_sta1_and_keeps_threshold(tmp_path) -> None:
    """Row 31 [H]: moving during the played clip abandons it; threshold kept."""
    level, player = _flat(tmp_path), _grounded()
    _idle(level, player, 105, _bit(1))
    assert player.idle_clip_tag == "STA2"
    step_player(level, player, Input(right=True), rand=_bit(1))
    assert player.idle_clip_tag == "" and player.idle_counter == 0
    assert player.idle_threshold == IDLE_START_THRESHOLD
    step_player(level, player, Input(), rand=_bit(1))
    assert select_clip(player) == STA1


def _script_run(level, seed):
    state = new_game_state(level, spawn_x=0.0, spawn_y=float(FLAT_Y), seed=seed)
    out = []
    for i in range(400):
        state.tick(Input(right=True) if 250 <= i < 255 else Input())
        p = state.player
        out.append(
            (
                select_clip(p),
                p.idle_counter,
                p.idle_threshold,
                p.idle_clip_tag,
                p.idle_frame,
                p.idle_phase,
            )
        )
    return out


def test_determinism_with_a_seed(tmp_path) -> None:
    """Rows 30-31: the idle cycle is a function of the seed alone."""
    level = _flat(tmp_path)
    assert _script_run(level, 7) == _script_run(level, 7)
    assert _script_run(level, 7) != _script_run(level, 8)
    assert IDLE_DEFAULT_SEED == 0
    a, b = default_random_bits(3), default_random_bits(3)
    assert [a() for _ in range(20)] == [b() for _ in range(20)]


def _idle_fields(p: Player):
    return (
        p.idle_counter,
        p.idle_threshold,
        p.idle_clip_tag,
        p.idle_frame,
        p.idle_phase,
    )


def test_snapshot_round_trip_keeps_the_idle_cycle(tmp_path) -> None:
    """Rows 30-31: the idle fields are saved and restored (stream is not)."""
    level = _flat(tmp_path)
    state = new_game_state(level, spawn_x=0.0, spawn_y=float(FLAT_Y))
    state.rand = _bit(1)
    for _ in range(50):
        state.tick(Input())
    assert state.player.idle_counter == 50
    snap = capture(state)
    assert Snapshot.from_dict(snap.to_dict()) == snap
    assert (snap.idle_counter, snap.idle_threshold) == (50, 100)

    captured_clip = select_clip(state.player)
    reference = []
    for _ in range(80):  # far enough to start and play a clip
        state.tick(Input())
        reference.append(select_clip(state.player))
    assert {t for t, _ in reference} == {"STA1", "STA2"}
    assert _idle_fields(state.player) != _idle_fields(Player(x=0, y=0))

    restore(state, snap)
    assert _idle_fields(state.player) == (50, 100, "", 0, 0)
    assert select_clip(state.player) == captured_clip
    again = []
    for _ in range(80):
        state.tick(Input())
        again.append(select_clip(state.player))
    assert again == reference
