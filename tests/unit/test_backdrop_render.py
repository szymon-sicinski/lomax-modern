"""Backdrop planes drawn behind the playfield (FL9), over synthetic worlds only.

Facts under test come from ``docs/file-formats.md`` §2.11: draw order (a), the
``ScrollMap`` ratio and drift (b), the ``Parallax`` sky (c) and the palette
slot (e).  No game bytes: every world is built by ``tests.fixtures.synth``.
"""

from __future__ import annotations

import gc
import importlib
from pathlib import Path

import pytest

from lomax_modern import art
from lomax_modern.anim_nmy import GnmyEntry
from lomax_modern.engine import (
    camera,
    load_level,
    new_game_state,
    render_tiles,
    run_slice,
)
from lomax_modern.engine.level import BackdropPlane
from lomax_modern.engine.render import (
    COLOUR_PLAYER,
    COLOUR_SKY,
    backdrop_plane_origin,
    trunc_div,
)
from lomax_modern.renderer import rgb15_to_rgb565
from tests.fixtures.synth import (
    anim_payload,
    backdrop_palettes,
    backdrop_world,
)

# ``lomax_modern.engine`` re-exports the ``render`` function, shadowing the module.
render_mod = importlib.import_module("lomax_modern.engine.render")

K7 = 7 << 4  # W_A: seven placement params
SCROLL_MAP, PARALLAX, OTHER = 0, 1, 2
RECORDS = [("ScrollMap", K7, []), ("Parallax", K7, []), ("Other", 0, [])]


def colour(slot: int, index: int) -> int:
    """The B5G6R5 word the engine paints for palette ``index`` of ``slot``."""
    return rgb15_to_rgb565(backdrop_palettes()[slot][index])


def scroll(params: tuple[int, ...], flags: int = 0):
    return (SCROLL_MAP, 0, 0, flags, params, None)


def make_level(tmp_path: Path, planes, backdrops, **kw):
    path = tmp_path / "W.WLD"
    path.write_bytes(backdrop_world(planes, **kw))
    return load_level(path, playfield=0, backdrop_planes=backdrops)


def playfield(w: int = 40, h: int = 20) -> dict:
    return {"w": w, "h": h}


def state_at(level, cx: float, cy: float, ticks: int = 0):
    state = new_game_state(level)
    state.player.x = cx - state.player.width / 2
    state.player.y = cy - state.player.height / 2
    state.tick_count = ticks
    return state


def find(frame, value: int) -> tuple[int, int] | None:
    """Top-left of the pixels equal to ``value`` (None when absent)."""
    hits = [
        (i % frame.width, i // frame.width) for i, p in enumerate(frame.pixels) if p == value
    ]
    return (min(x for x, _ in hits), min(y for _, y in hits)) if hits else None


def row(frame, y: int, x0: int, x1: int) -> list[int]:
    return frame.pixels[y * frame.width + x0 : y * frame.width + x1]


# --- integer truncation ------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(7, 2, 3), (-7, 2, -3), (7, -2, -3), (-7, -2, 3), (0, 5, 0), (-1, 100, 0), (160 * 50, 100, 80)],
)
def test_trunc_div_truncates_toward_zero(a: int, b: int, expected: int) -> None:
    assert trunc_div(a, b) == expected


def test_plane_origin_formula_and_drift() -> None:
    def plane(params):
        entry = GnmyEntry(0, 0, 0, 0, 0, params, None, "ScrollMap")
        return BackdropPlane(1, (entry,), (entry,))

    p = plane((100, 50, 0xFFFF - 99, 16, 3, 4, 0))  # p2 = -100
    assert backdrop_plane_origin(p, 160, 40, 0) == (80 + 3, 6 + 4)
    # offsets: (3 << 16) - 2*100*655 = 65608 -> 1; (4 << 16) + 2*100*655 -> 5
    assert backdrop_plane_origin(p, 160, 40, 2) == (80 + 1, 6 + 5)
    # the ratio term truncates toward zero: -3 * 50 / 100 = -1 (a floor gives -2)
    assert backdrop_plane_origin(plane((0, 50, 0, 0, 0, 0, 0)), -3, 0, 0) == (-1, 0)
    # no ScrollMap placement: fixed at (0, 0) [H]
    assert backdrop_plane_origin(BackdropPlane(1), 500, 500, 99) == (0, 0)


def test_default_scrollmap_is_the_one_without_variant_bit() -> None:
    variant = GnmyEntry(0, 0, 0, 0, 1, (0, 9, 0, 9, 0, 0, 41), None, "ScrollMap")
    default = GnmyEntry(0, 0, 0, 0, 0, (0, 50, 0, 16, 0, 0, 0), None, "ScrollMap")
    plane = BackdropPlane(1, (variant, default), (variant, default))
    assert backdrop_plane_origin(plane, 100, 100, 0) == (50, 16)


# --- scroll ratio (AC4 pin) --------------------------------------------------


@pytest.fixture
def ratio_level(tmp_path: Path):
    near = {
        "w": 100,
        "h": 30,
        "tiles": {(12, 4): 1},
        "gnmy": [scroll((0, 50, 0, 16, 0, 0, 0))],
    }
    far = {
        "w": 100,
        "h": 30,
        "tiles": {(3, 8): 2},
        "gnmy": [scroll((0, 25, 0, 5, 0, 24, 0))],
    }
    return make_level(
        tmp_path, [playfield(), near, far], (1, 2), records=RECORDS, tile_slots={1: 1, 2: 1}
    )


def test_scroll_ratio_pins_the_backdrop_shift(ratio_level) -> None:
    level = ratio_level
    a = state_at(level, 160, 120)
    b = state_at(level, 320, 160)
    cam_a = camera(level, a.player, 320, 240)
    cam_b = camera(level, b.player, 320, 240)
    assert (cam_b[0] - cam_a[0], cam_b[1] - cam_a[1]) == (160, 40)
    fa, fb = render_tiles(level, a), render_tiles(level, b)

    near, far = colour(1, 1), colour(1, 2)
    na, nb = find(fa, near), find(fb, near)
    assert na == (192, 64)  # cell (12, 4) at plane origin (0, 0)
    assert (na[0] - nb[0], na[1] - nb[1]) == (160 * 50 // 100, 40 * 16 // 100)
    ra, rb = find(fa, far), find(fb, far)
    assert ra == (48, 128 - 24)  # cell (3, 8), plane y offset +24
    assert (ra[0] - rb[0], ra[1] - rb[1]) == (160 * 25 // 100, 40 * 5 // 100)


def test_scroll_drift_moves_the_plane_per_tick(tmp_path: Path) -> None:
    drift = {"w": 40, "h": 30, "tiles": {(10, 4): 1}, "gnmy": [scroll((100, 0, 0, 0, 0, 0, 0))]}
    level = make_level(tmp_path, [playfield(), drift], (1,), records=RECORDS)
    f0 = render_tiles(level, state_at(level, 160, 120, ticks=0))
    f60 = render_tiles(level, state_at(level, 160, 120, ticks=60))
    x0, x60 = find(f0, colour(1, 1))[0], find(f60, colour(1, 1))[0]
    # offset accumulates -= p0 * 655 (16.16); integer part = acc >> 16 (floor), so
    # after 60 ticks acc = -3,930,000 -> -60 and plane.x = -60: the art moves right
    assert x60 - x0 == -((-60 * 100 * 655) >> 16) == 60


# --- order, wrap, palette ----------------------------------------------------


def test_nearer_plane_covers_farther_and_transparent_lets_it_show(tmp_path: Path) -> None:
    near = {"w": 40, "h": 30, "tiles": {(2, 2): 1}}
    far = {"w": 40, "h": 30, "tiles": {(2, 2): 2, (3, 2): 2}}
    for order, front, back in (((1, 2), 1, 2), ((2, 1), 2, 1)):
        level = make_level(tmp_path, [playfield(), near, far], order, records=RECORDS)
        frame = render_tiles(level, state_at(level, 160, 120))
        assert frame.pixel(40, 40) == colour(1, front)  # both opaque: nearer wins
        assert frame.pixel(56, 40) == colour(1, 2)  # only the far plane is opaque
        assert frame.pixel(100, 100) == COLOUR_SKY
        del back


def test_plane_narrower_than_view_wraps_both_directions(tmp_path: Path) -> None:
    narrow = {
        "w": 8,
        "h": 20,
        "tiles": {(1, 1): 1, (7, 1): 2},
        "gnmy": [scroll((0, 0, 0, 0, 0xFFFF - 19, 0, 0))],  # p4 = -20: plane.x = -20
    }
    level = make_level(tmp_path, [playfield(), narrow], (1,), records=RECORDS)
    frame = render_tiles(level, state_at(level, 160, 120))
    one, two = colour(1, 1), colour(1, 2)
    y = 20
    for start in (36, 164, 292):  # cell 1 = plane px 16..31, shifted by -20 + k * 128
        assert row(frame, y, start - 1, start + 17)[0] != one
        assert set(row(frame, y, start, start + 16)) == {one}
    # cell 7 = plane px 112..127 shows at 132..147 and, wrapped negatively, at 4..19
    assert set(row(frame, y, 4, 20)) == {two}
    assert set(row(frame, y, 132, 148)) == {two}
    assert row(frame, y, 3, 4) == [COLOUR_SKY]


def test_tile_palette_slot_is_the_nibble_of_the_last_non_empty_cell(tmp_path: Path) -> None:
    far = {"w": 40, "h": 30, "tiles": {(2, 2): 1, (3, 2): 2}}
    level = make_level(
        tmp_path, [playfield(), far], (1,), records=RECORDS, tile_slots={1: 3, 2: 6}
    )
    frame = render_tiles(level, state_at(level, 160, 120))
    assert frame.pixel(40, 40) == colour(3, 1)
    assert frame.pixel(56, 40) == colour(6, 2)


def test_tile_slot_picks_last_non_empty_and_falls_back() -> None:
    cells = (
        art.Cell(0, bytes(64)),
        art.Cell(1, bytes([1] * 64)),
        art.Cell(2, bytes([2] * 64)),
    )

    def record(*pairs):
        return art.TileRecord(0, tuple(art.TileSlot(i, n << 8) for i, n in pairs))

    # slots 2 and 3 are empty (index 0, out of range) and must not decide
    rec = record((1, 1), (2, 5), (0, 7), (9, 8))
    assert render_mod._tile_slot(rec, cells) == 5
    assert render_mod._tile_slot(record((0, 4), (0, 4), (0, 4), (0, 4)), cells) == (
        art.DEFAULT_PALETTE_SLOT
    )


# --- the sky -----------------------------------------------------------------

#: 4x4 sprite: index 3 top-left, 6 bottom-right, a transparent hole in the middle.
SKY_PIXELS = bytes([3, 5, 5, 5, 5, 0, 0, 5, 5, 0, 0, 5, 5, 5, 5, 6])


def sky_world(
    tmp_path: Path,
    params,
    *,
    x=10,
    y=9,
    dx=-2,
    dy=-3,
    pixels=SKY_PIXELS,
    size=(4, 4),
    plane_scroll=None,
):
    """A world whose backdrop plane 1 holds one ``Parallax`` (and a ``ScrollMap``
    with ``plane_scroll`` params when given: the sky's ratio multiplies the
    *plane's* x/y, which is 0 without one)."""
    records = [
        ("ScrollMap", K7, []),
        ("Parallax", K7, [("PARA", [(1, 1, dx, dy, 0)])]),
        ("Other", 0, []),
    ]
    sprite = anim_payload(1, width=size[0], height=size[1], flags=4, pixels=pixels)
    gnmy = [(PARALLAX, x, y, 0, params, None)]
    if plane_scroll is not None:
        gnmy.append(scroll(plane_scroll))
    sky = {"w": 4, "h": 4, "gnmy": gnmy}
    return make_level(
        tmp_path, [playfield(), sky], (1,), records=records, sprites=[sprite]
    )


def test_sky_draws_the_periodic_sprite_in_its_palette_slot(tmp_path: Path) -> None:
    level = sky_world(tmp_path, (8, 6, 0, 0, 0, 0, 0))
    assert [p.palette_slot for p in level.backdrops[0].parallax] == [4]
    f = render_tiles(level, state_at(level, 160, 120))
    # grid origin (10 mod 8, 9 mod 6) = (2, 3); sprite top-left = origin + (-2, -3)
    assert f.pixel(0, 0) == colour(4, 3)
    assert f.pixel(3, 3) == colour(4, 6)
    assert f.pixel(1, 1) == COLOUR_SKY  # the sprite's hole shows the fill
    assert f.pixel(8, 0) == colour(4, 3) and f.pixel(0, 6) == colour(4, 3)
    assert f.pixel(304, 36) == colour(4, 3)  # copies repeat across the view


def test_sky_drifts_by_p2_per_tick(tmp_path: Path) -> None:
    level = sky_world(tmp_path, (8, 6, 0xFFFF - 99, 0, 0, 0, 0))  # p2 = -100
    f0 = render_tiles(level, state_at(level, 160, 120, ticks=0))
    f1 = render_tiles(level, state_at(level, 160, 120, ticks=1))
    # (-100 * 655) >> 16 == -1: the whole pattern moves one pixel left
    for y in range(100):  # above the player marker, which does not shift
        assert row(f1, y, 0, 300) == row(f0, y, 1, 301)
    assert row(f1, 0, 0, 20) != row(f0, 0, 0, 20)


def test_sky_ratio_zero_ignores_camera_and_ratio_follows_it(tmp_path: Path) -> None:
    follow_cam = (0, 100, 0, 100, 0, 0, 0)  # the sky's plane tracks the camera 1:1
    fixed = sky_world(tmp_path, (20, 6, 0, 0, 0, 0, 0), plane_scroll=follow_cam)
    a = render_tiles(fixed, state_at(fixed, 160, 120))
    b = render_tiles(fixed, state_at(fixed, 320, 160))
    assert all(row(a, y, 0, 320) == row(b, y, 0, 320) for y in range(50))

    follow = sky_world(tmp_path, (20, 6, 0, 5, 0, 0, 0), plane_scroll=follow_cam)  # X ratio 5 %
    c = render_tiles(follow, state_at(follow, 160, 120))
    d = render_tiles(follow, state_at(follow, 320, 160))  # camera 160 px right
    shift = 160 * 5 // 100
    assert row(d, 0, 0, 200) == row(c, 0, shift, 200 + shift)
    assert row(d, 0, 0, 40) != row(c, 0, 0, 40)


def test_sky_overlap_later_copy_wins_and_period_zero_draws_once(tmp_path: Path) -> None:
    level = sky_world(
        tmp_path, (3, 0, 0, 0, 0, 0, 0), x=0, y=5, dx=0, dy=0, pixels=bytes([1, 2, 3, 4]),
        size=(4, 1),
    )
    f = render_tiles(level, state_at(level, 160, 120))
    c = [colour(4, i) for i in (1, 2, 3)]
    assert row(f, 5, 0, 9) == c + c + c  # copy k+1 covers copy k's 4th pixel
    assert row(f, 4, 0, 9) == [COLOUR_SKY] * 9  # Y period 0: drawn once
    assert row(f, 6, 0, 9) == [COLOUR_SKY] * 9


def test_unresolved_sky_keeps_the_placeholder_fill(tmp_path: Path) -> None:
    sky = {"w": 4, "h": 4, "gnmy": [(PARALLAX, 0, 0, 0, (8, 6, 0, 0, 0, 0, 0), None)]}
    level = make_level(tmp_path, [playfield(), sky], (1,), records=RECORDS)  # no PARA clip
    assert level.backdrops[0].parallax == ()
    frame = render_tiles(level, state_at(level, 160, 120))
    others = {p for p in frame.pixels} - {COLOUR_PLAYER}
    assert others == {COLOUR_SKY}


# --- cache, no-backdrop identity, report -------------------------------------


def test_cache_is_built_once_and_frames_repeat(ratio_level, monkeypatch) -> None:
    builds = []
    real = render_mod._build_backdrop_cache
    monkeypatch.setattr(
        render_mod, "_build_backdrop_cache", lambda lvl: builds.append(lvl) or real(lvl)
    )
    state = state_at(ratio_level, 160, 120)
    first = render_tiles(ratio_level, state)
    second = render_tiles(ratio_level, state)
    assert first.pixels == second.pixels
    assert len(builds) == 1
    render_tiles(ratio_level, state_at(ratio_level, 320, 160))
    assert len(builds) == 1


def test_cache_entry_dies_with_its_level(tmp_path: Path) -> None:
    level = make_level(tmp_path, [playfield(), {"w": 4, "h": 4}], (1,), records=RECORDS)
    render_mod.backdrop_cache(level)
    key = id(level)
    assert key in render_mod._CACHES
    del level
    gc.collect()
    assert key not in render_mod._CACHES


def test_no_backdrops_is_the_plain_fill(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        render_mod,
        "_build_backdrop_cache",
        lambda lvl: pytest.fail("no backdrops: the cache must not be touched"),
    )
    level = make_level(tmp_path, [playfield(), {"w": 4, "h": 4, "tiles": {(0, 0): 1}}], ())
    frame = render_tiles(level, state_at(level, 160, 120))
    assert set(frame.pixels) <= {COLOUR_SKY, COLOUR_PLAYER}


def test_slice_report_backdrop_block(tmp_path: Path, ratio_level) -> None:
    path = tmp_path / "S.WLD"
    path.write_bytes(
        backdrop_world(
            [
                playfield(),
                {"w": 4, "h": 4, "tiles": {(0, 0): 1}, "gnmy": [scroll((0, 25, 0, 5, 0, 24, 0))]},
                {"w": 4, "h": 4, "tiles": {(1, 1): 2}},
            ],
            records=RECORDS,
            tile_slots={1: 3, 2: 2},
        )
    )
    report, _ = run_slice(tmp_path, world_path=path, max_ticks=3, backdrop_planes=(1, 2))
    text = report.format()
    lines = [ln for ln in text.splitlines() if ln.startswith("backdrop")]
    assert lines[0] == "backdrop plane 2: tiles, fixed at (0, 0) [H], tile slot 2 [V]"
    assert lines[1] == "backdrop plane 1: tiles, scroll 25%/5% +0/+24, tile slot 3 [V]"
    assert "backdrop: not drawn: playfield Parallax, Birds [H]" in lines
    assert any("palette set = playfield HEAD" in ln and ln.endswith("[H]") for ln in lines)
    assert any("without ScrollMap" in ln for ln in lines)

    plain, _ = run_slice(tmp_path, world_path=path, max_ticks=3)
    assert "backdrop" not in plain.format()


def test_sky_report_line(tmp_path: Path) -> None:
    level = sky_world(tmp_path, (160, 128, 0xFFFF - 16, 0, 0, 0, 0))
    assert (
        "backdrop plane 1: sky Parallax, 160x128 period, drift -17/100 px/tick, "
        "ratio 0%/0%, palette slot 4 [V]"
    ) in render_mod.backdrop_report(level).splitlines()
