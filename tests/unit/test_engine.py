"""Engine-core tests over synthetic data (no game bytes).

A helper builds a tiny ``.WLD`` with a chosen collision grid, so every physics
and collision claim below is asserted against a geometry the test controls.
"""

from __future__ import annotations

import inspect
import struct

import pytest

from lomax_modern.engine import (
    CELL_PX,
    CollisionModel,
    Collectible,
    Exit,
    Frame,
    Input,
    Player,
    camera,
    load_level,
    new_game_state,
    pack_rgb565,
    render,
    run_slice,
    step_player,
)
from lomax_modern.engine import entities as entities_module
from lomax_modern.engine.entities import GRAVITY, JUMP_SPEED, MAX_FALL, WALK_SPEED
from lomax_modern.engine.level import OUT_OF_BOUNDS_COLLISION
from lomax_modern.engine.render import (
    COLOUR_PLAYER,
    COLOUR_SOLID,
    frame_to_rgba,
    unpack_rgb565,
)
from lomax_modern.engine.state import capture, restore
from tests.fixtures.synth import (
    build_container,
    cell_payload,
    gnmy_payload,
    head_payload,
    map_payload,
    ttab_payload,
)


def _world_bytes(
    width_cells: int,
    height_cells: int,
    collision_grid: list[list[int]],
) -> bytes:
    """Build a one-plane world whose MAP collision bytes equal ``collision_grid``."""
    width_units = width_cells * 2
    height_units = height_cells * 2
    cells: list[tuple[int, int]] = []
    for y in range(height_cells):
        for x in range(width_cells):
            cells.append((0, collision_grid[y][x]))
    chunks = [
        ("WRLD", b"PS-X" + b"\0" * 4),
        ("NMY", b"\0" * 16),
        ("PARA", b"\0" * 8),
        ("HEAD", head_payload(width_units, height_units)),
        ("TTAB", ttab_payload([[0, 0, 0, 0, 0, 0, 0, 0]])),
        ("MAP", map_payload(width_units, height_units, cells=cells)),
        ("GNMY", gnmy_payload((0,))),
        ("MACR", b"\0" * 8),
        ("PAGE", b"\0" * 8),
        ("CELL", cell_payload([bytes(64)])),
        ("ANIM", b"\0" * 20),
        ("END", b""),
    ]
    return build_container(chunks, endian=">")


def _load(tmp_path, width_cells: int, height_cells: int, grid: list[list[int]]):
    path = tmp_path / "test.WLD"
    path.write_bytes(_world_bytes(width_cells, height_cells, grid))
    return load_level(path)


def _grid(w: int, h: int, solid_cells=()) -> list[list[int]]:
    """An ``w``x``h`` all-empty grid with the given ``(x, y)`` cells solid."""
    solid = set(solid_cells)
    return [[1 if (x, y) in solid else 0 for x in range(w)] for y in range(h)]


def _floor(w: int, h: int) -> list[list[int]]:
    """An ``w``x``h`` grid with a solid bottom row."""
    grid = _grid(w, h)
    for x in range(w):
        grid[h - 1][x] = 1
    return grid


# --------------------------------------------------------------------------
# Loading and collision model
# --------------------------------------------------------------------------


def test_level_geometry(tmp_path) -> None:
    level = _load(tmp_path, 4, 3, _floor(4, 3))
    assert level.width_px == 64
    assert level.height_px == 48
    assert level.plane.cell_count == 12
    assert level.plane.width_cells == 4
    assert level.plane.height_cells == 3
    assert len(level.cells) == 1  # one CELL record in the fixture
    assert len(level.palette) == 256


def test_collision_model_zero_is_passable() -> None:
    model = CollisionModel()
    assert not model.is_solid(0)
    assert model.is_solid(1)
    # 0xFF is a one-way floor now (top bits 11), not solid; off-map solidity is
    # Level.solid_at's own bounds test.
    assert not model.is_solid(0xFF)
    assert model.one_way(0xFF)
    assert not model.one_way(0x80)  # wall/ceiling class: conservative solid
    assert model.is_solid(0x80)
    assert "conservative solid [H]" in model.report()
    assert "FL2 classes [V]" in model.report()


def test_collision_at_bounds_is_solid(tmp_path) -> None:
    level = _load(tmp_path, 4, 3, _floor(4, 3))
    assert level.collision_at(-1, 0) == OUT_OF_BOUNDS_COLLISION
    assert level.solid_at(-1, 0)
    assert level.solid_at(4, 0)  # one past the right edge
    assert level.collision_at(0, 0) == 0  # in-map empty


def test_playfield_out_of_range_raises(tmp_path) -> None:
    path = tmp_path / "test.WLD"
    path.write_bytes(_world_bytes(2, 2, _grid(2, 2)))
    with pytest.raises(ValueError):
        load_level(path, playfield=3)


# --------------------------------------------------------------------------
# Physics: gravity, walking, jumping, wall and floor collision
# --------------------------------------------------------------------------


def test_player_lands_on_floor(tmp_path) -> None:
    level = _load(tmp_path, 4, 3, _floor(4, 3))
    player = Player(x=0.0, y=0.0)
    for _ in range(120):
        step_player(level, player, Input())
    assert player.on_ground
    assert player.vy == 0.0
    # Bottom of the 14px player rests on the floor row (pixel 32): y = 32 - 14.
    assert player.y == pytest.approx(18.0)


def test_player_walks_right_on_floor(tmp_path) -> None:
    level = _load(tmp_path, 8, 4, _floor(8, 4))
    player = Player(x=0.0, y=0.0)
    for _ in range(120):
        step_player(level, player, Input())
    y = player.y
    step_player(level, player, Input(right=True))
    assert player.x == pytest.approx(2.0)
    assert player.y == pytest.approx(y)  # stays on the floor


def test_wall_stops_player(tmp_path) -> None:
    # Wall at column 2, floor at row 2.  Player walks right and stops flush.
    grid = _grid(4, 3, {(2, 0), (2, 1), (2, 2)})
    for x in range(4):
        grid[2][x] = 1  # bottom row solid
    level = _load(tmp_path, 4, 3, grid)
    player = Player(x=0.0, y=0.0)
    for _ in range(120):
        step_player(level, player, Input())
    for _ in range(30):
        step_player(level, player, Input(right=True))
    # Right edge rests exactly at the wall's left face (pixel 32).
    assert player.x == pytest.approx(32.0 - player.width)


def test_jump_sets_upward_velocity(tmp_path) -> None:
    level = _load(tmp_path, 4, 3, _floor(4, 3))
    player = Player(x=0.0, y=0.0)
    for _ in range(120):
        step_player(level, player, Input())
    step_player(level, player, Input(jump=True))
    assert player.vy < 0.0
    assert not player.on_ground


def test_out_of_bounds_floor_holds_player(tmp_path) -> None:
    # An all-passable level: the solid *boundary* is what holds the player, so
    # it can never fall out of the world or walk off an edge.
    level = _load(tmp_path, 3, 3, _grid(3, 3))
    player = Player(x=0.0, y=0.0)
    for _ in range(200):
        step_player(level, player, Input(right=True))
    assert player.on_ground
    assert 0 <= player.x < level.width_px
    assert 0 <= player.y < level.height_px
    # Resting on the bottom boundary: bottom edge = 48 = 3*16.
    assert player.y == pytest.approx(48.0 - player.height)


def test_physics_constants_match_measured_original_rates() -> None:
    """The four rates are read from ``LOMAX.EXE``, not our own design.

    Each immediate is a 16.16-fixed-point value read by the objdump pass
    (``docs/file-formats.md`` §2.9); the floats here are the same rates in
    pixels per 60 Hz tick.
    """
    assert WALK_SPEED == 2.0
    assert GRAVITY == 0.375
    assert JUMP_SPEED == -4.0
    assert MAX_FALL == 6.0


def test_physics_constants_document_their_source() -> None:
    """Every constant names the virtual address it was measured at.

    A value without a VA (or with the wrong VA) is a guess, and this test must
    fail on it — which is what keeps a future edit honest.
    """
    src = inspect.getsource(entities_module)
    for va in ("0x426E28", "0x410BB8", "0x41083C", "0x410BC2"):
        assert va in src, f"missing measured VA {va} in entities.py comments"


# --------------------------------------------------------------------------
# Collect, exit, next level
# --------------------------------------------------------------------------


def test_collectible_picked_up(tmp_path) -> None:
    level = _load(tmp_path, 8, 4, _floor(8, 4))
    state = new_game_state(
        level, spawn_x=0.0, spawn_y=16.0, collectibles=[Collectible(2, 2)]
    )
    for _ in range(120):
        state.tick(Input())
    for _ in range(30):
        state.tick(Input(right=True))
    assert 0 in state.entities.collected


def test_exit_completes_level(tmp_path) -> None:
    level = _load(tmp_path, 8, 4, _floor(8, 4))
    state = new_game_state(level, spawn_x=0.0, spawn_y=16.0, exits=[Exit(1, 2)])
    for _ in range(120):
        state.tick(Input())
    for _ in range(60):  # walk to the last 50 px of the 128 px plane
        state.tick(Input(right=True))
        if state.complete:
            break
    assert state.complete


def test_exit_transitions_to_next_level(tmp_path) -> None:
    world_a = tmp_path / "WORLDS"
    world_a.mkdir()
    (world_a / "A.WLD").write_bytes(_world_bytes(8, 4, _floor(8, 4)))
    (world_a / "B.WLD").write_bytes(_world_bytes(4, 3, _floor(4, 3)))

    level = load_level(world_a / "A.WLD")
    state = new_game_state(level, spawn_x=0.0, spawn_y=16.0, exits=[Exit(1, 2)])
    for _ in range(120):
        state.tick(Input())
    for _ in range(60):
        state.tick(Input(right=True))
        if state.complete:
            break
    assert state.complete

    # "Next level": load the next world and start a fresh state there.
    next_level = load_level(world_a / "B.WLD")
    fresh = new_game_state(next_level, spawn_x=0.0, spawn_y=0.0)
    assert fresh.level.name == "B"
    assert fresh.tick_count == 0
    assert not fresh.complete
    assert fresh.player.x == 0.0


# --------------------------------------------------------------------------
# Fixed timestep and save states
# --------------------------------------------------------------------------


def test_fixed_timestep_counts_ticks(tmp_path) -> None:
    level = _load(tmp_path, 4, 3, _floor(4, 3))
    state = new_game_state(level, spawn_x=0.0, spawn_y=0.0)
    for _ in range(60):
        state.tick(Input())
    assert state.tick_count == 60


def test_save_state_capture_restore(tmp_path) -> None:
    level = _load(tmp_path, 8, 4, _floor(8, 4))
    state = new_game_state(
        level, spawn_x=0.0, spawn_y=16.0, collectibles=[Collectible(2, 1)]
    )
    for _ in range(120):
        state.tick(Input())
    for _ in range(10):
        state.tick(Input(right=True))
    snap = capture(state)

    # Keep mutating, then restore.
    for _ in range(50):
        state.tick(Input(right=True))
    assert state.tick_count != snap.tick
    restore(state, snap)
    assert state.tick_count == snap.tick
    assert state.player.x == pytest.approx(snap.x)
    assert state.player.y == pytest.approx(snap.y)
    assert state.entities.collected == set(snap.collected)


def test_snapshot_dict_roundtrip(tmp_path) -> None:
    level = _load(tmp_path, 4, 3, _floor(4, 3))
    state = new_game_state(level, spawn_x=0.0, spawn_y=0.0)
    state.tick(Input(right=True))
    snap = capture(state)
    again = type(snap).from_dict(snap.to_dict())
    assert again == snap


def test_restore_rejects_wrong_world(tmp_path) -> None:
    level = _load(tmp_path, 4, 3, _floor(4, 3))
    state = new_game_state(level, spawn_x=0.0, spawn_y=0.0)
    snap = capture(state)
    other = type(snap)(
        world="OTHER",
        playfield=snap.playfield,
        tick=snap.tick,
        complete=snap.complete,
        x=snap.x,
        y=snap.y,
        vx=snap.vx,
        vy=snap.vy,
        on_ground=snap.on_ground,
        collected=snap.collected,
    )
    with pytest.raises(ValueError):
        restore(state, other)


# --------------------------------------------------------------------------
# Framebuffer, colour packing, camera, rendering
# --------------------------------------------------------------------------


def test_pack_rgb565_exact() -> None:
    assert pack_rgb565(255, 0, 0) == 0xF800
    assert pack_rgb565(0, 255, 0) == 0x07E0
    assert pack_rgb565(0, 0, 255) == 0x001F
    assert pack_rgb565(255, 255, 255) == 0xFFFF
    assert pack_rgb565(0, 0, 0) == 0x0000


def test_unpack_rgb565_roundtrip() -> None:
    for r, g, b in [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255), (0, 0, 0)]:
        assert unpack_rgb565(pack_rgb565(r, g, b)) == (r, g, b)


def test_unpack_rgb565_widens_green_by_bit_replication() -> None:
    """The 6->8 widening is ``g6 << 2 | g6 >> 4``, pinned at mid-range values.

    The round trip above cannot see the difference: both ``g6 << 2 | g6 >> 4``
    and the wrong ``g6 << 2 | g6 >> 2`` map 0 and 63 to 0 and 255, so they agree
    on every primary.  In between they disagree on 55 of the 64 greens:
    over-brightened 46 (by up to 12/255) and under-brightened 9 (by up to
    3/255) — hence the explicit mid-range cases and the exhaustive loop.
    """
    # (g6, correct g8, g8 produced by the wrong `>> 2` widening)
    for g6, expected, wrong in [(4, 16, 17), (16, 65, 68), (45, 182, 191)]:
        assert unpack_rgb565(g6 << 5) == (0, expected, 0), (
            f"g6={g6} must widen to {expected}, not {wrong}"
        )
    assert unpack_rgb565(0) == (0, 0, 0)
    assert unpack_rgb565(63 << 5) == (0, 255, 0)
    for g6 in range(64):
        assert unpack_rgb565(g6 << 5)[1] == (g6 << 2) | (g6 >> 4)

    # The pair still round-trips through the 6-bit green channel.
    assert pack_rgb565(0, 182, 0) == 45 << 5
    assert unpack_rgb565(pack_rgb565(0, 182, 0)) == (0, 182, 0)


def test_frame_to_rgba_widens_green_like_the_renderer() -> None:
    """The PNG export path (``frame_to_rgba``) must use the same widening."""
    frame = Frame(3, 1)
    frame.set(0, 0, pack_rgb565(0, 182, 0))
    frame.set(1, 0, pack_rgb565(0, 16, 0))
    frame.set(2, 0, pack_rgb565(0, 0, 0))
    assert frame_to_rgba(frame) == bytes(
        (0, 182, 0, 255, 0, 16, 0, 255, 0, 0, 0, 255)
    )


def test_frame_is_16_bit_and_serialises_little_endian() -> None:
    frame = Frame(2, 1)
    frame.set(0, 0, 0xF800)
    frame.set(1, 0, 0x07E0)
    assert frame.pixel(0, 0) == 0xF800
    assert frame.to_bytes() == struct.pack("<2H", 0xF800, 0x07E0)
    assert frame_to_rgba(frame) == bytes((255, 0, 0, 255, 0, 255, 0, 255))


def test_camera_centres_and_clamps(tmp_path) -> None:
    level = _load(tmp_path, 40, 20, _floor(40, 20))
    player = Player(x=0.0, y=0.0, width=12, height=14)
    x, y = camera(level, player, 320, 240)
    assert (x, y) == (0, 16)  # clamped to the top-left (y floor is 16, §2.11.f)
    player.x = level.width_px - player.width
    x, y = camera(level, player, 320, 240)
    assert x == level.width_px - 320  # clamped to the right edge


def test_render_draws_solid_cell_and_player(tmp_path) -> None:
    grid = _grid(4, 3, {(0, 0)})
    level = _load(tmp_path, 4, 3, grid)
    state = new_game_state(level, spawn_x=16.0, spawn_y=0.0)
    frame = render(level, state)
    # Level (64x48) is smaller than the viewport, so the camera sits at (0,0).
    assert frame.pixel(0, 0) == COLOUR_SOLID
    # Player is at screen (16, 0) and drawn as a marker.
    assert frame.pixel(16, 0) == COLOUR_PLAYER


def test_render_does_not_draw_empty_cell(tmp_path) -> None:
    level = _load(tmp_path, 4, 3, _grid(4, 3))
    state = new_game_state(level, spawn_x=16.0, spawn_y=0.0)
    frame = render(level, state)
    # No solid cell at (0,0): the sky colour stays, not the solid colour.
    assert frame.pixel(0, 0) != COLOUR_SOLID


# --------------------------------------------------------------------------
# Headless vertical slice runner
# --------------------------------------------------------------------------


def test_run_slice_reports_ticks_and_clean_exit(tmp_path) -> None:
    game_dir = tmp_path / "game"
    (game_dir / "WORLDS").mkdir(parents=True)
    (game_dir / "WORLDS" / "VILLAGE.WLD").write_bytes(_world_bytes(8, 4, _floor(8, 4)))
    report, frame = run_slice(game_dir, worlds=("VILLAGE",), max_ticks=60)
    assert 0 < report.ticks <= 60
    assert report.frames == report.ticks
    assert report.clean_exit
    assert report.world == "VILLAGE"
    assert frame.width == 320 and frame.height == 240
    text = report.format()
    # The corrected MAP/TTAB layout resolves Q20 on this branch.
    assert "resolved (Q20)" in text
    assert "unresolved (Q20)" not in text
    assert "collision: FL2 classes [V]" in text
    assert "still [H]:" in text
    # Q32 is now wired, not just named: this synthetic fixture carries no NMY
    # names, so the engine falls back and says so instead of blaming Q32.
    assert report.spawn_name is None
    assert report.exits == ()
    assert report.collected_total == 0
    assert "placeholder" not in text
    assert "does not consume" not in text
    assert "no Start placement" in text
    assert "collect: 0 Moneybag(s)" in text
    assert "exit: none (no Exit placement)" in text
    assert "Start/Exit/Moneybag [V]" in text
    assert "Q23" not in text
    assert "entry meaning unverified" not in text
    assert "semantics unresolved" not in text


def test_new_game_state_docstring_records_the_resolved_roles() -> None:
    """The docstring must record Q32's answer and that the engine consumes it."""
    doc = new_game_state.__doc__ or ""
    assert "Q32" in doc
    assert "Start" in doc and "Exit" in doc and "Moneybag" in doc
    assert "does not consume" not in doc
    assert "falls back" in doc
    assert "Q23" not in doc
    assert "unresolved" not in doc
