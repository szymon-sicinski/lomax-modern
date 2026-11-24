"""AN5: ``Input.down``, the Down key and the one-shot ``DUCK`` clip.

``DUCK`` is ``docs/file-formats.md`` §2.6.2 a row 23: 6 poses, rate 65/256,
one-shot, holds its last pose [V].  The engine's setter rule (grounded + Down
held) is [H].  Every level is synthetic; the player is driven with real ticks.
"""

from __future__ import annotations

from lomax_modern.engine import Input, Player, load_level, select_clip, step_player
from lomax_modern.engine.entities import DUCK_POSES, DUCK_RATE, WALK_SPEED
from lomax_modern.input import (
    DEFAULT_KEYMAP,
    SDLK_DOWN,
    SDLK_LEFT,
    SDLK_RIGHT,
    SDLK_SPACE,
    Keymap,
    SDLK_s,
)
from tests.fixtures.synth import (
    build_container,
    cell_payload,
    gnmy_payload,
    head_payload,
    map_payload,
    ttab_payload,
)

DUCK = "DUCK"
AIR_TAGS = {"JMP1", "JMP2", "FLO1", "FLO2"}
FLAT_Y = 3 * 16 - 14  # a grounded 14 px box on the 4-row flat level


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
    path = tmp_path / "duck.WLD"
    path.write_bytes(_world_bytes(len(grid[0]), len(grid), grid))
    return load_level(path)


def _flat(tmp_path, *, width: int = 12, height: int = 4):
    grid = [[0] * width for _ in range(height)]
    grid[height - 1] = [1] * width
    return _level(tmp_path, grid)


def _grounded(x: float = 0.0, y: float = FLAT_Y) -> Player:
    return Player(x=x, y=y, on_ground=True)


def _run(level, player: Player, inputs) -> list[tuple[str, int]]:
    out = []
    for inp in inputs:
        step_player(level, player, inp)
        out.append(select_clip(player))
    return out


# Keymap -------------------------------------------------------------------


def test_default_keymap_binds_down_arrow_and_s() -> None:
    keymap = Keymap.default()
    assert keymap.update({SDLK_DOWN}, ()) == Input(down=True)
    assert keymap.update({SDLK_s}, ()) == Input(down=True)
    assert DEFAULT_KEYMAP.down == frozenset({SDLK_DOWN, SDLK_s})


def test_down_is_level_triggered() -> None:
    keymap = Keymap.default()
    for _ in range(3):
        assert keymap.update({SDLK_DOWN}, ()).down is True
    assert keymap.update((), ()).down is False


def test_existing_mappings_are_unchanged() -> None:
    keymap = Keymap.default()
    assert keymap.update({SDLK_LEFT}, ()) == Input(left=True)
    assert keymap.update({SDLK_RIGHT}, ()) == Input(right=True)
    assert keymap.update({SDLK_SPACE}, ()) == Input()
    assert keymap.update({SDLK_SPACE}, {SDLK_SPACE}) == Input(jump=True)
    custom = Keymap(left=[1], right=[2], jump=[3])
    assert custom.down == frozenset()
    assert custom.update({1, 2, 3}, {3}) == Input(jump=True)


# select_clip / step_player ------------------------------------------------


def test_held_duck_plays_to_the_last_pose_and_holds_it(tmp_path) -> None:
    level = _flat(tmp_path)
    clips = _run(level, _grounded(), [Input(down=True)] * 40)
    assert {tag for tag, _ in clips} == {DUCK}
    poses = [pose for _, pose in clips]
    assert poses[0] == 0
    assert poses == sorted(poses)
    last = DUCK_POSES - 1
    first_last = poses.index(last)
    assert len(poses) - first_last >= 20
    assert set(poses[first_last:]) == {last}
    assert max(poses) == last


def test_duck_cadence_pins_the_rate(tmp_path) -> None:
    assert DUCK_RATE == 65
    assert DUCK_POSES == 6
    level = _flat(tmp_path)
    clips = _run(level, _grounded(), [Input(down=True)] * 4)
    assert clips[2] == (DUCK, 0)
    assert clips[3] == (DUCK, 1)


def test_releasing_down_returns_to_stand_and_walk(tmp_path) -> None:
    level = _flat(tmp_path)
    player = _grounded()
    _run(level, player, [Input(down=True)] * 10)
    assert _run(level, player, [Input()]) == [("STA1", 0)]
    player = _grounded()
    _run(level, player, [Input(down=True)] * 10)
    ((tag, _),) = _run(level, player, [Input(right=True)])
    assert tag == "WALK"


def test_repressing_down_replays_from_pose_zero(tmp_path) -> None:
    level = _flat(tmp_path)
    player = _grounded()
    clips = _run(level, player, [Input(down=True)] * 12)
    assert clips[-1][1] > 0
    _run(level, player, [Input()])
    assert _run(level, player, [Input(down=True)]) == [(DUCK, 0)]


def test_airborne_never_draws_duck(tmp_path) -> None:
    level = _flat(tmp_path)
    player = _grounded()
    tags = set()
    inp = Input(jump=True, down=True)
    for _ in range(60):
        step_player(level, player, inp)
        inp = Input(down=True)
        if player.on_ground:
            break
        tags.add(select_clip(player)[0])
    assert tags and tags <= {"JMP1", "FLO1"}

    floating = Player(x=0.0, y=0.0, on_ground=False)
    for _ in range(5):
        step_player(_flat(tmp_path), floating, Input(down=True))
        if floating.on_ground:
            break
        assert select_clip(floating)[0] in AIR_TAGS


def test_down_suppresses_horizontal_input_only_on_the_ground(tmp_path) -> None:
    level = _flat(tmp_path)
    player = _grounded()
    (clip,) = _run(level, player, [Input(right=True, down=True)])
    assert player.vx == 0.0
    assert clip[0] == DUCK

    air = Player(x=0.0, y=0.0, on_ground=False)
    (clip,) = _run(level, air, [Input(right=True, down=True)])
    assert air.vx == WALK_SPEED
    assert clip[0] in AIR_TAGS


def test_duck_outranks_lnd1() -> None:
    player = Player(x=0.0, y=0.0, on_ground=True, lnd1_shown=True, duck_shown=True)
    assert select_clip(player)[0] == DUCK


def test_collision_box_is_untouched() -> None:
    player = Player(x=0.0, y=0.0)
    assert (player.width, player.height) == (12, 14)
