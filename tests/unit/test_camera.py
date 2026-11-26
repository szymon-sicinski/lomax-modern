"""The camera rule (docs/file-formats.md §2.11.f [V]); synthetic levels only."""

from __future__ import annotations

from lomax_modern.engine import Player, camera, new_game_state, render_tiles
from lomax_modern.engine.state import CameraRig, Snapshot, capture, restore
from tests.unit.test_backdrop_render import (
    RECORDS,
    colour,
    find,
    make_level,
    playfield,
    scroll,
)
from tests.unit.test_engine import _floor, _load

ACCEL = 0x4000


def _player(feet_x: int, feet_y: int) -> Player:
    p = Player(x=0.0, y=0.0, width=12, height=14)
    p.x = float(feet_x - 6)
    p.y = float(feet_y - 14)
    return p


def _wide(tmp_path, w=200, h=60):
    return _load(tmp_path, w, h, _floor(w, h))


def test_horizontal_feet_minus_160_and_clamps(tmp_path) -> None:
    level = _wide(tmp_path)  # 3200 x 960 px
    rig = CameraRig.snap(level, _player(1000, 500))
    assert rig.cam_x == 840
    rig.update(level, _player(50, 500))
    assert rig.cam_x == 0
    rig.update(level, _player(level.width_px - 1, 500))
    assert rig.cam_x == level.width_px - 320


def test_horizontal_has_no_dead_zone(tmp_path) -> None:
    level = _wide(tmp_path)
    rig = CameraRig.snap(level, _player(1000, 500))
    for fx in (1001, 1002, 1000, 999):
        rig.update(level, _player(fx, 500))
        assert rig.cam_x == fx - 160


def test_vertical_drop_eases_within_accel_cap_and_converges(tmp_path) -> None:
    level = _wide(tmp_path)
    rig = CameraRig.snap(level, _player(1000, 400))
    assert rig.cam_y == 240
    hero = _player(1000, 500)
    prev_y, prev_v = rig.cam_y_fp, rig.speed_fp
    for _ in range(600):
        rig.update(level, hero)
        assert rig.cam_y_fp >= prev_y  # monotonic: the cam never moves back up
        assert abs(rig.speed_fp - prev_v) <= ACCEL  # same-direction cap 0.25
        prev_y, prev_v = rig.cam_y_fp, rig.speed_fp
    assert abs(rig.cam_y - 340) <= 1  # feet - 160


def test_vertical_clamps_top_16_and_bottom(tmp_path) -> None:
    level = _wide(tmp_path)  # height 960
    rig = CameraRig.snap(level, _player(1000, 100))
    assert rig.cam_y == 16
    for _ in range(50):
        rig.update(level, _player(1000, 30))
    assert rig.cam_y == 16
    for _ in range(2000):
        rig.update(level, _player(1000, 950))
    assert rig.cam_y == level.height_px - 240


def test_short_level_clamps_at_zero_without_crashing(tmp_path) -> None:
    level = _load(tmp_path, 4, 3, _floor(4, 3))
    rig = CameraRig.snap(level, _player(32, 40))
    rig.update(level, _player(32, 40))
    assert (rig.cam_x, rig.cam_y) == (0, 0)


def test_reversing_uses_the_larger_step_hand_computed(tmp_path) -> None:
    level = _wide(tmp_path)
    rig = CameraRig(cam_y_fp=100 << 16, speed_fp=-0x8000, cam_x=0)
    hero = _player(1000, 100)  # target = (100-100+160)/16 = +10 px/tick
    rig.update(level, hero)
    # v < 0 with the target above it: reversing, +0xC000 -> 0x4000; cam_y -= v
    assert rig.speed_fp == 0x4000
    assert rig.cam_y_fp == (100 << 16) - 0x4000
    rig.update(level, hero)  # same direction now: +0x4000
    assert rig.speed_fp == 0x8000
    assert rig.cam_y_fp == (100 << 16) - 0x4000 - 0x8000


def test_reversing_the_other_way(tmp_path) -> None:
    level = _wide(tmp_path)
    # v > 0 but the target is negative: step 0xC000 toward it.
    rig = CameraRig(cam_y_fp=300 << 16, speed_fp=0x10000, cam_x=0)
    hero = _player(1000, 500)  # t = (300-500+160)/16 = -2.5 px/tick
    rig.update(level, hero)
    assert rig.speed_fp == 0x10000 - 0xC000
    rig.update(level, hero)  # v was still > 0 -> 0xC000 again (short of -0x28000)
    assert rig.speed_fp == 0x4000 - 0xC000


def test_snapshot_roundtrip_and_old_save(tmp_path) -> None:
    level = _wide(tmp_path)
    state = new_game_state(level, spawn_x=1000.0, spawn_y=400.0)
    state.player.y = 480.0
    for _ in range(5):
        state.camera.update(level, state.player)
    assert state.camera.speed_fp != 0
    snap = Snapshot.from_dict(capture(state).to_dict())
    other = new_game_state(level, spawn_x=1000.0, spawn_y=400.0)
    restore(other, snap)
    assert other.camera.cam_y_fp == state.camera.cam_y_fp
    assert other.camera.speed_fp == state.camera.speed_fp
    old = capture(state).to_dict()
    del old["cam_y_fp"], old["cam_speed_fp"]
    restore(other, Snapshot.from_dict(old))
    assert other.camera.speed_fp == 0
    assert other.camera.cam_y == int(other.player.y + 14) - 160


def test_camera_function_uses_rig_or_snapped_rule(tmp_path) -> None:
    level = _wide(tmp_path)
    hero = _player(1000, 500)
    assert camera(level, hero, 320, 240) == (840, 340)
    rig = CameraRig(cam_y_fp=300 << 16, speed_fp=0, cam_x=7)
    assert camera(level, hero, 320, 240, rig) == (7, 300)


def test_backdrop_shifts_by_ratio_relative_to_new_camera(tmp_path) -> None:
    near = {
        "w": 100,
        "h": 30,
        "tiles": {(12, 4): 1},
        "gnmy": [scroll((0, 50, 0, 0, 0, 0, 0))],
    }
    level = make_level(
        tmp_path, [playfield(100, 30), near], (1,), records=RECORDS, tile_slots={1: 1}
    )
    a = new_game_state(level, spawn_x=300.0, spawn_y=200.0)
    b = new_game_state(level, spawn_x=500.0, spawn_y=200.0)
    ca = camera(level, a.player, 320, 240, a.camera)
    cb = camera(level, b.player, 320, 240, b.camera)
    assert cb[0] - ca[0] == 200
    pa = find(render_tiles(level, a), colour(1, 1))
    pb = find(render_tiles(level, b), colour(1, 1))
    assert pa[0] - pb[0] == 200 * 50 // 100
