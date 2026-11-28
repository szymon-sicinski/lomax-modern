"""FL14: Henchlemming movement (docs/file-formats.md §2.13).  Synthetic only."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from types import SimpleNamespace

from lomax_modern.anim_nmy import decode_nmy
from lomax_modern.engine import Input, load_level, new_game_state
from lomax_modern.engine.enemies import (
    _air_pose,
    _landing_probe,
    enemies_report,
    init_enemy,
    look_ahead_turns,
    new_enemies,
    same_kind_ahead,
    step_enemies,
    step_enemy,
)
from lomax_modern.engine.entities import Entities, Henchlemming, Player
from lomax_modern.engine.level import CollisionModel
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

FLOOR = 100


class FakeLevel:
    """A floor probe over ``surface(x) -> (y, kind, rising) | None`` with the
    original's row window (starts at ``(y-16)//16``, 4 rows)."""

    def __init__(self, surface=None, width=2000):
        self.width_px = width
        self.enemy_clips = {}
        self._surface = surface or (lambda x: (FLOOR, 0, False))

    def floor_probe(self, x, y, rows=4):
        if y < 16 or not 0 <= x < self.width_px:
            return None
        found = self._surface(x)
        if found is None:
            return None
        first = max(0, (y - 16) // 16) * 16
        return found if first <= found[0] < first + rows * 16 + 16 else None

    def floor_at(self, x, y, rows=4):
        found = self.floor_probe(x, y, rows)
        return None if found is None else found[:2]


def _enemy(x=500, y=FLOOR, flags=0):
    e = Henchlemming(0, x, y, flags, x=x, y=y)
    init_enemy(e)
    return e


def _run_until_hop(level, e, hero=lambda e: e.x ^ 1, limit=400):
    """Step until the next take-off; return the tick count used."""
    hops = e.hops
    for n in range(1, limit):
        step_enemy(level, e, [e], hero(e))
        if e.hops > hops:
            return n
    raise AssertionError("no take-off")


# --- init -----------------------------------------------------------------


def test_init_values():
    e = _enemy(x=500 + 0, y=FLOOR)  # 500 & 31 == 20, 500 & 16 == 16
    assert (e.rest, e.ground, e.turn_next) == (20, 10, 0)
    assert e.facing_left is True and (e.vx16, e.vy16) == (0, 0)
    assert (e.clip, e.pose, e.x16, e.y16) == ("STAY", 0, 500 << 16, FLOOR << 16)
    right = _enemy(x=1068)  # 1068 & 16 == 0, & 31 == 12
    assert right.facing_left is False and right.rest == 12


def test_rest_of_r_shows_stay_for_r_minus_1_ticks():
    level = FakeLevel()
    e = _enemy(x=500)  # R = 20
    stay = 0
    while e.rest > 0:
        step_enemy(level, e, [e], 0)
        if e.clip == "STAY":
            stay += 1
    assert stay == 19
    assert e.rest == 0 and e.ground == 9  # the 20th tick fell through to JUMP


# --- the hop --------------------------------------------------------------


def test_flat_hop_arc_and_cycle():
    level = FakeLevel()
    e = _enemy(x=500)
    _run_until_hop(level, e)
    x0, y0 = e.x, e.y
    assert (e.vx16, e.vy16) == (-0x10000, -0x40000) and e.hops == 1
    ys, vys = [], []
    n = 0
    while True:
        n += 1
        step_enemy(level, e, [e], e.x ^ 1)
        if e.ground:
            break
        ys.append(e.y)
        vys.append(e.vy16)
    assert n == 31  # lands on the 31st airborne tick
    assert x0 - e.x == 31 and e.y == y0 and e.rest == -1
    assert y0 - min(ys) == 30  # apex
    assert (
        vys[-1] == 3 * 0x10000 + 0x8000 + 1
    )  # 3.5 the tick before landing (+ the |1 drift)


def test_cycle_is_r_plus_50_between_takeoffs():
    level = FakeLevel()
    e = _enemy(x=500)
    _run_until_hop(level, e)  # first take-off
    total = _run_until_hop(level, e)  # next take-off, hero_x gives the short rest
    assert total == 20 + 50


def test_vy_drift_bit_keeps_flat_hop_from_snapping():
    """With vy |= 1 the apex tick has vy = 1/65536 (not 0), so the depth gate runs."""
    level = FakeLevel()
    e = _enemy(x=500)
    _run_until_hop(level, e)
    seen = []
    while not e.ground:
        step_enemy(level, e, [e], 0)
        seen.append(e.vy16)
    assert 1 in seen  # the apex value with the drift bit set
    assert 0 not in seen[:-1]


def test_long_rest_rule_and_turn_next():
    level = FakeLevel()
    e = _enemy(x=500)
    _run_until_hop(level, e)
    while not e.ground:
        step_enemy(level, e, [e], 0)
    x = e.x
    facing = e.facing_left
    for _ in range(10):  # the landing squash; the 10th chooses the rest
        step_enemy(level, e, [e], x)  # (x ^ hero) & 7 == 0
    assert (e.turn_next, e.rest) == (1, 60 + (x & 0x7F))
    _run_until_hop(level, e, hero=lambda e: e.x)
    assert e.turn_next == 0 and e.facing_left is (not facing)
    # a mismatch picks the short rest
    e2 = _enemy(x=500)
    _run_until_hop(level, e2)
    while not e2.ground:
        step_enemy(level, e2, [e2], 0)
    for _ in range(10):
        step_enemy(level, e2, [e2], e2.x ^ 1)
    assert (e2.turn_next, e2.rest) == (0, 20)


# --- turning --------------------------------------------------------------


def _facing_after_takeoff(level, e, others=None):
    for _ in range(400):
        step_enemy(level, e, others or [e], e.x ^ 1)
        if e.hops:
            return e.facing_left
    raise AssertionError


def test_same_kind_ahead_window_and_direction():
    e = _enemy(x=500)  # faces left
    other = Henchlemming(1, 0, 0, 0, spawned=True, x=421, y=FLOOR)
    assert same_kind_ahead(e, [e, other])
    other.x = 420  # 80 px is not "within": strict
    assert not same_kind_ahead(e, [e, other])
    other.x = 501  # behind
    assert not same_kind_ahead(e, [e, other])
    other.x, other.y = 450, FLOOR - 55  # |dy + 16| = 39
    assert same_kind_ahead(e, [e, other])
    other.y = FLOOR - 56  # |dy + 16| = 40
    assert not same_kind_ahead(e, [e, other])
    other.y = FLOOR + 23  # 39
    assert same_kind_ahead(e, [e, other])
    other.y = FLOOR + 24
    assert not same_kind_ahead(e, [e, other])
    other.spawned = False
    other.y = FLOOR
    assert not same_kind_ahead(e, [e, other])
    r = _enemy(x=1068)  # faces right
    ahead = Henchlemming(1, 0, 0, 0, spawned=True, x=1147, y=FLOOR)
    assert same_kind_ahead(r, [r, ahead])
    ahead.x = 1148
    assert not same_kind_ahead(r, [r, ahead])
    ahead.x = 1060  # behind
    assert not same_kind_ahead(r, [r, ahead])


def test_same_kind_ahead_turns_at_takeoff():
    level = FakeLevel()
    e = _enemy(x=500)
    other = Henchlemming(1, 0, 0, 0, spawned=True, x=450, y=FLOOR)
    assert _facing_after_takeoff(level, e, [e, other]) is False
    assert e.vx16 == 0x10000


def test_look_ahead_flat_gap_step_slope_and_edge():
    def lvl(f):
        return FakeLevel(f)

    e = _enemy(x=500)  # left: columns 500, 484, 468, 452
    assert not look_ahead_turns(lvl(None), e)
    # a gap 48 px ahead (column 452) turns; one more pixel away does not
    assert look_ahead_turns(lvl(lambda x: None if x <= 452 else (FLOOR, 0, False)), e)
    assert not look_ahead_turns(
        lvl(lambda x: None if x < 452 else (FLOOR, 0, False)), e
    )
    # a 16 px step turns, 15 px does not
    assert look_ahead_turns(
        lvl(lambda x: (FLOOR + 16 if x < 470 else FLOOR, 0, False)), e
    )
    assert not look_ahead_turns(
        lvl(lambda x: (FLOOR + 15 if x < 470 else FLOOR, 0, False)), e
    )
    assert look_ahead_turns(
        lvl(lambda x: (FLOOR - 16 if x < 470 else FLOOR, 0, False)), e
    )
    # a 45 degree (steep) slope turns
    assert look_ahead_turns(
        lvl(lambda x: (FLOOR, 2, True) if x < 470 else (FLOOR, 0, False)), e
    )
    # the plane edge is "no floor"
    edge = _enemy(x=20)
    assert look_ahead_turns(FakeLevel(), edge)  # columns 20, 4, -12
    far = _enemy(x=200)
    assert not look_ahead_turns(FakeLevel(), far)
    right = _enemy(x=1068)
    assert look_ahead_turns(FakeLevel(width=1100), right)  # columns up to 1116
    assert not look_ahead_turns(FakeLevel(width=1117), right)


def test_blocked_on_both_sides_still_hops_once():
    level = FakeLevel(lambda x: (FLOOR, 0, False) if 495 <= x < 505 else None)
    e = _enemy(x=500)
    for _ in range(400):
        step_enemy(level, e, [e], 0)
        if e.hops:
            break
    assert e.hops == 1 and e.facing_left is False and e.vx16 == 0x10000


def test_steep_slope_landing_reverses():
    level = FakeLevel(lambda x: (FLOOR, 2, True))
    e = _enemy(x=500)
    e.ground, e.vx16, e.vy16, e.y, e.y16 = (
        0,
        0x10000,
        0x20000,
        FLOOR + 2,
        (FLOOR + 2) << 16,
    )
    e.facing_left = False
    assert _landing_probe(level, e) == 2
    assert e.vx16 == -0x10000 and e.facing_left is True and e.y == FLOOR and e.vy16 == 0
    down = FakeLevel(lambda x: (FLOOR, 2, False))
    f = _enemy(x=500)
    f.vx16, f.vy16, f.y = (
        0x10000,
        0x20000,
        FLOOR + 2,
    )  # moving right, slope descends right
    assert _landing_probe(down, f) == 2 and f.vx16 == 0x10000
    flat = FakeLevel()
    g = _enemy(x=500)
    g.vx16, g.vy16, g.y = 0x10000, 0x20000, FLOOR + 2
    assert _landing_probe(flat, g) == 1 and g.vx16 == 0x10000


def test_landing_probe_depth_gate_and_rising():
    level = FakeLevel()
    e = _enemy(x=500)
    e.vy16, e.y = 0x20000, FLOOR - 1  # the floor is below y: not reached yet
    assert _landing_probe(level, e) == 0
    e.y = FLOOR + 8  # 8 px or more below the floor: passed it
    assert _landing_probe(level, e) == 0
    e.y = FLOOR + 7
    assert _landing_probe(level, e) == 1 and e.y == FLOOR
    r = _enemy(x=500)
    r.vy16 = -0x40000
    assert _landing_probe(level, r) == 0 and r.vy16 == -0x40000 | 1


def test_pose_thresholds():
    assert _air_pose(-0x30001) == 1 and _air_pose(-0x30000) == 2
    assert _air_pose(-0x10001) == 2 and _air_pose(-0x10000) == 3
    assert _air_pose(0x7FFF) == 3 and _air_pose(0x8000) == 4
    assert _air_pose(0x1FFFF) == 4 and _air_pose(0x20000) == 5


def test_stay_pose_advances_at_clip_rate():
    clip = SimpleNamespace(rate=40, poses=(0,) * 5)
    level = FakeLevel()
    e = _enemy(x=1068 + 19)  # rest = 31
    for _ in range(7):
        step_enemy(level, e, [e], 0, clip)
    assert e.pose_phase == 280 and e.pose == 1
    for _ in range(100):
        if e.rest <= 1:
            break
        step_enemy(level, e, [e], 0, clip)
    assert 0 <= e.pose < 5


def test_never_leaves_plane_on_a_strip():
    level = FakeLevel(lambda x: (FLOOR, 0, False) if 0 <= x < 320 else None, width=320)
    e = _enemy(x=100)
    for t in range(6000):
        step_enemy(level, e, [e], (t * 7) & 0xFFF)
        assert 0 <= e.x < 320
        if e.ground:
            assert e.y == FLOOR
    assert e.hops > 30


# --- wake rule ------------------------------------------------------------


def _stub(enemies, cam=(0, 0), tick=0):
    return SimpleNamespace(
        game_over=False,
        entities=Entities(enemies=enemies),
        level=FakeLevel(),
        camera=SimpleNamespace(cam_x=cam[0], cam_y=cam[1]),
        tick_count=tick,
        player=Player(x=0.0, y=0.0),
    )


def _placed(x, y, flags=0, index=0):
    return Henchlemming(
        index, x, y, flags, x=x, y=y, static_fallback=bool(flags & 0x2000)
    )


def test_spawn_window_and_phase():
    e = _placed(320 + 80, 100)
    st = _stub([e], cam=(0, 0), tick=0)
    step_enemies(st)
    assert e.spawned  # on the margin
    far = _placed(320 + 81, 100)
    st = _stub([far])
    step_enemies(st)
    assert not far.spawned
    below = _placed(100, 240 + 81)
    step_enemies(_stub([below]))
    assert not below.spawned
    ok = _placed(100, 240 + 80)
    step_enemies(_stub([ok]))
    assert ok.spawned
    # only on ticks with tick % 4 == 0
    late = _placed(100, 100)
    step_enemies(_stub([late], tick=1))
    assert not late.spawned
    step_enemies(_stub([late], tick=4))
    assert late.spawned
    left = _placed(100, 100)
    step_enemies(_stub([left], cam=(180, 0)))
    assert left.spawned  # 100 == 180 - 80
    left2 = _placed(99, 100)
    step_enemies(_stub([left2], cam=(180, 0)))
    assert not left2.spawned


def test_release_window_and_respawn_reinit():
    e = _placed(500, 100)
    st = _stub([e], cam=(500 - 100, 0), tick=0)
    step_enemies(st)
    assert e.spawned
    for _ in range(150):
        st.tick_count += 1
        step_enemies(st)
    hops = e.hops
    assert hops >= 1
    st.camera.cam_x = 500 + 200
    st.tick_count = 1  # 1 % 3 == 1: a despawn tick, not a spawn tick
    step_enemies(st)
    assert not e.spawned and e.released
    px = e.x
    st.camera.cam_x = 0
    st.tick_count = 2
    step_enemies(st)
    assert not e.spawned and e.x == px  # position persists for the report
    # re-enter the spawn window: init at the placement, hops kept
    st.camera.cam_x = 500 - 100
    st.tick_count = 4
    step_enemies(st)
    assert e.spawned and (e.place_x, e.place_y) == (500, 100)
    assert e.hops == hops  # not reset on respawn
    assert (e.rest, e.ground, e.clip) == (
        (500 & 31) - 1,
        10,
        "STAY",
    )  # init, then this tick's update
    assert (e.x, e.y) == (500, 100)


def test_release_margins_exact_and_phase():
    def released(cam_x, cam_y, tick, ex=500, ey=100):
        e = _placed(ex, ey)
        init_enemy(e)
        e.rest = 100  # stays put
        st = _stub([e], cam=(cam_x, cam_y), tick=tick)
        step_enemies(st)
        return not e.spawned

    assert released(500 + 161, 0, 1)  # cam_x - 160 > x
    assert not released(500 + 160, 0, 1)
    assert not released(500 - 320 - 160, 0, 1)  # x == cam_x + 320 + 160
    assert released(500 - 320 - 161, 0, 1)
    assert released(500 - 100, 100 + 111, 1)  # cam_y - 110 > y
    assert not released(500 - 100, 100 + 110, 1)
    assert released(500 - 100, 100 - 240 - 111, 1)
    assert not released(500 + 161, 0, 0)  # not a despawn tick
    assert not released(500 + 161, 0, 2)
    assert released(500 + 161, 0, 4)


def test_static_fallback_never_spawns_or_moves():
    e = _placed(1018, 320, flags=0x2000)
    assert e.static_fallback
    st = _stub([e], cam=(900, 250))
    for t in range(0, 400, 1):
        st.tick_count = t
        step_enemies(st)
    assert not e.spawned and (e.x, e.y, e.clip, e.hops) == (1018, 320, "STAY", 0)


def test_game_over_skips():
    e = _placed(100, 100)
    st = _stub([e])
    st.game_over = True
    step_enemies(st)
    assert not e.spawned


# --- level.floor_probe ----------------------------------------------------


def _wld(width, height, cells, entries, names=("Start", "Henchlemming")):
    chunks = [
        ("WRLD", b"PS-X" + b"\0" * 4),
        ("NMY", nmy_payload([(n, 0) for n in names], trailer=2)),
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


W, H, FLOOR_ROW = 40, 15, 10


def _level(tmp_path: Path, entries, extra=None):
    cells = []
    for row in range(H):
        for col in range(W):
            byte = 0xC0 if row == FLOOR_ROW else 0
            if extra and (col, row) in extra:
                byte = extra[(col, row)]
            cells.append((0, byte))
    path = tmp_path / "TEST.WLD"
    path.write_bytes(_wld(W, H, cells, entries))
    return load_level(path)


def _entry(kind, x, y, flags=0):
    return (kind, x, y, flags, (1,), None)


def test_floor_probe_matches_floor_at(tmp_path):
    # a steep mirrored cell (0xF8) at column 5, row 10; flat floor elsewhere
    level = _level(tmp_path, [_entry(0, 64, 216)], extra={(5, FLOOR_ROW): 0xF8})
    model = CollisionModel()
    for x in (0, 79, 80, 88, 95, 200, 639):
        for y in (0, 15, 16, 100, 176, 200, 239):
            probe = level.floor_probe(x, y)
            at = level.floor_at(x, y)
            assert (probe is None) == (at is None)
            if probe:
                assert probe[:2] == at
    surface, kind, rising = level.floor_probe(80, 176)
    assert (
        kind == 2
        and rising is True
        and surface == FLOOR_ROW * 16 + model.floor_offset(0xF8, 0)
    )
    assert level.floor_probe(200, 176) == (176, 0, False)
    assert level.floor_probe(700, 176) is None


# --- through the state ----------------------------------------------------


ENTRIES = [
    _entry(0, 64, 216),  # Start
    _entry(1, 300, 176),  # Henc, 300 & 31 = 12, facing right (300 & 16 = 16: left)
    _entry(1, 340, 176, 0x2000),  # Generator-spawned
    _entry(1, 620, 176),  # outside the first window
]


def test_new_game_state_builds_enemies(tmp_path):
    level = _level(tmp_path, ENTRIES)
    state = new_game_state(level)
    en = state.entities.enemies
    assert [(e.place_x, e.place_y, e.static_fallback) for e in en] == [
        (300, 176, False),
        (340, 176, True),
        (620, 176, False),
    ]
    assert not any(e.spawned for e in en)
    plain = new_game_state(_level(tmp_path, [_entry(0, 64, 216)]))
    assert plain.entities.enemies == [] and enemies_report(plain) == "enemies: none"


def _run(level, ticks):
    state = new_game_state(level)
    states = []
    for t in range(ticks):
        state.tick(Input())
        if t % 97 == 0:
            states.append(json.dumps(capture(state).to_dict(), sort_keys=True))
    return state, states


def test_enemy_hops_through_gamestate_and_is_deterministic(tmp_path):
    level = _level(tmp_path, ENTRIES)
    state, a = _run(level, 900)
    _, b = _run(level, 900)
    assert a == b
    first = state.entities.enemies[0]
    assert first.hops > 3
    assert first.spawned and first.y <= 176
    assert not state.entities.enemies[1].spawned
    assert not state.entities.enemies[2].spawned  # never inside the window


def test_snapshot_round_trip_and_old_save(tmp_path):
    level = _level(tmp_path, ENTRIES)
    state = new_game_state(level)
    for _ in range(200):
        state.tick(Input())
    snap = capture(state)
    data = json.loads(json.dumps(snap.to_dict()))
    assert Snapshot.from_dict(data) == snap
    cont = new_game_state(level)
    restore(cont, Snapshot.from_dict(data))
    assert [vars(e) for e in cont.entities.enemies] == [
        vars(e) for e in state.entities.enemies
    ]
    for _ in range(100):
        state.tick(Input())
        cont.tick(Input())
    assert capture(state).enemies == capture(cont).enemies
    old = {k: v for k, v in data.items() if k != "enemies"}
    loaded = Snapshot.from_dict(old)
    assert loaded.enemies == ()
    fresh = new_game_state(level)
    restore(fresh, loaded)
    assert len(fresh.entities.enemies) == 3 and not any(
        e.spawned for e in fresh.entities.enemies
    )


def test_enemies_report_text(tmp_path):
    level = _level(tmp_path, ENTRIES)
    state = new_game_state(level)
    text = enemies_report(state)
    lines = text.splitlines()
    assert lines[0] == "enemies: 3 Henchlemming, 2 moving, 1 static fallback [H]"
    assert (
        "henchlemming 0: (300, 176) -> (300, 176) at tick 0, not yet spawned, 0 hops"
        in lines[1]
    )
    assert (
        "static fallback [H]: Generator-spawned, the Generator is not ported"
        in lines[2]
    )
    assert lines[-1].startswith("  rules: hop-only STAY/JUMP")
    for _ in range(300):
        state.tick(Input())
    text = enemies_report(state)
    assert "at tick 300, clip " in text and " hops" in text
    state.entities.enemies[0].spawned = False
    state.entities.enemies[0].released = True
    assert "released, " in enemies_report(state)


def test_new_enemies_only_henc():
    level = SimpleNamespace(
        gnmy=(
            SimpleNamespace(name="Start", x=1, y=2, flags=0),
            SimpleNamespace(name="Henchlemming", x=5, y=6, flags=0x2000),
            SimpleNamespace(name=None, x=5, y=6, flags=0),
        )
    )
    en = new_enemies(level)
    assert len(en) == 1 and en[0].static_fallback and en[0].index == 0


# --- NmyAnim.rate ---------------------------------------------------------


def test_nmy_anim_rate_decoded():
    payload = bytearray(nmy_payload([("Henchlemming", 2)], trailer=2))
    tag = struct.pack("<I", 0x48414E47)
    first = bytes(payload).index(tag) + 10
    struct.pack_into("<H", payload, first, 40)
    second = bytes(payload).index(tag, first) + 10
    struct.pack_into("<H", payload, second, 57)
    records, _ = decode_nmy(bytes(payload))
    assert [a.rate for a in records[0].anims] == [40, 57]
    plain, _ = decode_nmy(nmy_payload([("Henchlemming", 1)], trailer=2))
    assert plain[0].anims[0].rate == 0


# --- clips and rendering --------------------------------------------------


def _clip_world(tmp_path: Path, entries):
    from lomax_modern.engine import render_tiles
    from tests.fixtures.synth import anim_frames_payload, nmy_records_payload

    def kf(step):  # sprite 1, dx -2, dy -16
        return (1, step, 0xFFFE, 0xFFF0, 0)

    nmy = bytearray(
        nmy_records_payload(
            [
                ("Start", 0x10, []),
                ("Henchlemming", 0x10, [("STAY", [kf(1), kf(2)]), ("JUMP", [kf(1)])]),
            ]
        )
    )
    tag = struct.pack("<I", struct.unpack("<I", b"STAY"[::-1])[0])
    struct.pack_into("<H", nmy, bytes(nmy).index(tag) + 10, 40)  # the STAY clip's rate
    cells = [(0, 0xC0 if r == FLOOR_ROW else 0) for r in range(H) for _ in range(W)]
    sprite = anim_frames_payload(
        0, (bytes([1] * 8 + [0] * 8), bytes([2] * 16)), width=4, height=4
    )
    chunks = [
        ("WRLD", b"PS-X" + b"\0" * 4),
        ("NMY", bytes(nmy)),
        ("PARA", b"\0" * 8),
        ("HEAD", head_payload(W * 2, H * 2)),
        ("TTAB", ttab_payload([[0, 0, 0, 0, 0, 0, 0, 0]])),
        ("MAP", map_payload(W * 2, H * 2, cells=cells)),
        ("GNMY", gnmy_entries_payload(entries)),
        ("MACR", b"\0" * 8),
        ("PAGE", b"\0" * 8),
        ("CELL", cell_payload([bytes(64)])),
        ("ANIM", sprite),
        ("END", b""),
    ]
    path = tmp_path / "CLIPS.WLD"
    path.write_bytes(build_container(chunks, endian=">"))
    return load_level(path), render_tiles


def test_enemy_clips_resolve_and_draw(tmp_path):
    from lomax_modern.engine.render import Framebuffer, draw_enemies

    level, _ = _clip_world(tmp_path, [_entry(0, 64, 216), _entry(1, 300, 176)])
    assert set(level.enemy_clips) == {"STAY", "JUMP"}
    stay = level.enemy_clips["STAY"]
    assert (
        stay.rate == 40 and len(stay.poses) == len(stay.mirrored) == 2
    )  # rate from the data
    assert level.enemy_clips["JUMP"].rate == 0
    state = new_game_state(level)
    state.tick(Input())  # spawns the enemy (tick 0) and updates it once
    e = state.entities.enemies[0]
    assert e.spawned and e.pose_phase == 40  # STAY advanced by the data's rate

    pose = stay.poses[0]
    calls = []
    fb = Framebuffer(320, 240)
    fb.blit_sprite = lambda idx, w, h, palette, sx, sy: calls.append((idx, sx, sy))
    e.x, e.y, e.pose, e.clip = 100, 100, 0, "STAY"
    for facing, dx, idx in (
        (False, pose.dx, pose.pixels.indices),
        (True, 1 - pose.pixels.width - pose.dx, stay.mirrored[0].indices),
    ):
        e.facing_left = facing
        calls.clear()
        draw_enemies(fb, level, [e], None, 0, 0)
        assert calls == [(idx, 100 + dx, 100 + pose.dy)]
    e.static_fallback = True  # never drawn
    calls.clear()
    draw_enemies(fb, level, [e], None, 0, 0)
    assert calls == []


def test_static_henc_sprites_skipped_only_with_clips(tmp_path):
    from lomax_modern.engine.render import Framebuffer, draw_placed_sprites

    level, _ = _clip_world(tmp_path, [_entry(0, 64, 216), _entry(1, 300, 176)])
    entry = SimpleNamespace(name="Henchlemming")
    sprites = [SimpleNamespace(entry=entry, x=0, y=0, width=1, height=1, indices=(1,))]
    pal = SimpleNamespace(word=lambda i: i)
    fb = Framebuffer(320, 240)
    draw_placed_sprites(fb, sprites, pal, 0, 0, skip_henc=True)
    assert not any(fb.pixels)
    draw_placed_sprites(fb, sprites, pal, 0, 0, skip_henc=False)
    assert fb.pixels[0] == 1
    assert level.enemy_clips  # the render path passes skip_henc=bool(enemy_clips)
