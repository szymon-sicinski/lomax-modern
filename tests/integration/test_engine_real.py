"""Engine-core check against a real installation (opt-in).

Set ``LOMAX_GAME_DIR`` to a folder containing ``LOMAX.EXE`` to run this.  It is
read-only on the install and prints counts, positions and flags only — no game
bytes, no digests.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lomax_modern import wld
from lomax_modern.anim_nmy import decode_gnmy, decode_nmy
from lomax_modern.engine import (
    camera,
    gnmy_marker,
    load_level,
    new_game_state,
    render,
    render_tiles,
    run_slice,
    select_clip,
)
from lomax_modern.engine.entities import STA1_POSES, STA2_POSES, Player
from lomax_modern.engine.render import COLOUR_PLAYER

GAME_DIR = os.environ.get("LOMAX_GAME_DIR")

pytestmark = [
    pytest.mark.realgame,
    pytest.mark.skipif(
        not GAME_DIR or not Path(GAME_DIR).is_dir(),
        reason="set LOMAX_GAME_DIR to a Lomax installation to run",
    ),
]


def test_slice_first_world_reports_ticks_and_clean_exit() -> None:
    path = Path(GAME_DIR or "") / "WORLDS" / "VILLAGE.WLD"
    if not path.is_file():
        pytest.skip("VILLAGE.WLD not present in this install")

    report, frame = run_slice(GAME_DIR or "", worlds=("VILLAGE",), max_ticks=60)
    print(report.format())

    assert report.world == "VILLAGE"
    assert report.planes >= 1
    assert report.clean_exit
    assert report.frames == report.ticks
    assert report.frames <= 60
    assert frame.width == 320 and frame.height == 240
    # The collision byte is preserved and its semantics flagged, not guessed.
    assert report.collision_histogram  # non-empty: 0x00 and at least one solid
    assert "retracted" in report.format()
    assert "resolved (Q20)" in report.format()
    assert "Q31" in report.format()


def test_render_tiles_composes_real_tile_art() -> None:
    """The tile-art frame is strictly richer than the geometric debug grid."""
    path = Path(GAME_DIR or "") / "WORLDS" / "VILLAGE.WLD"
    if not path.is_file():
        pytest.skip("VILLAGE.WLD not present in this install")

    level = load_level(path)
    state = new_game_state(level, spawn_x=0.0, spawn_y=0.0)
    tiles = render_tiles(level, state)
    grid = render(level, state)

    print(
        f"tile-art distinct colours={len(set(tiles.pixels))}, "
        f"geometric distinct colours={len(set(grid.pixels))}"
    )
    assert tiles.width == 320 and tiles.height == 240
    # Composed art uses the whole HEAD palette; the geometric grid draws a
    # handful of marker colours.  Both assertions hold only if the frame is
    # tile art, not the grey collision grid.
    assert tiles.pixels != grid.pixels
    assert len(set(tiles.pixels)) > len(set(grid.pixels))


def test_render_tiles_scrolls_the_village_playfield() -> None:
    """The scripted walk-right scrolls the composed art past one 320 px screen."""
    path = Path(GAME_DIR or "") / "WORLDS" / "VILLAGE.WLD"
    if not path.is_file():
        pytest.skip("VILLAGE.WLD not present in this install")

    first = []
    report, final = run_slice(
        GAME_DIR or "",
        worlds=("VILLAGE",),
        max_ticks=300,
        on_frame=lambda i, frame: first.append(frame.pixels),
    )

    # Scrolling means later frames differ from the first (the camera advances
    # and the composed art moves), and the walk-right passes one 320 px screen.
    assert report.frames >= 1
    assert report.final_position[0] > 320
    assert any(pixels != first[0] for pixels in first[1:])


def _playfield_gnmy(world, playfield: int) -> list:
    """Independently decode the playfield plane's GNMY placements (mirrors probe)."""
    nmy = next((c for c in world.chunks if c.tag == "NMY"), None)
    k_of = {}
    if nmy is not None:
        result = decode_nmy(nmy.payload)
        if result is not None:
            records, _ = result
            k_of = {i: (rec.flags >> 4) & 0xF for i, rec in enumerate(records)}
    plane = -1
    entries = []
    for c in world.chunks:
        if c.tag == "HEAD":
            plane += 1
        elif c.tag == "GNMY" and plane == playfield:
            decoded = decode_gnmy(c.payload, k_of)
            if decoded is not None:
                entries.extend(decoded[0])
    return entries


def test_render_tiles_shows_the_player_sprite_not_the_marker() -> None:
    """The player is its standing ANIM sprite from MAIN.WLD, not the marker."""
    path = Path(GAME_DIR or "") / "WORLDS" / "VILLAGE.WLD"
    if not path.is_file():
        pytest.skip("VILLAGE.WLD not present in this install")

    level = load_level(path)
    sprite = level.player_sprite
    assert sprite is not None, "VILLAGE should resolve the Hero's standing frame"
    assert sprite.width > 0 and sprite.height > 0
    # Not all-transparent: the standing Lomax sprite has real pixels.
    assert any(v != 0 for v in sprite.indices)

    state = new_game_state(level, spawn_x=99.0, spawn_y=189.0)
    frame = render_tiles(level, state)

    print(
        f"player sprite: {sprite.width}x{sprite.height}, "
        f"{sum(1 for v in sprite.indices if v)}/{len(sprite.indices)} opaque"
    )
    # The marker is gone: the sprite replaced the solid-colour rectangle.
    assert COLOUR_PLAYER not in frame.pixels


def test_render_tiles_overlays_gnmy_markers() -> None:
    """The playfield's GNMY placements paint name-styled markers in the frame."""
    path = Path(GAME_DIR or "") / "WORLDS" / "VILLAGE.WLD"
    if not path.is_file():
        pytest.skip("VILLAGE.WLD not present in this install")

    level = load_level(path)
    # Loading is wired: the level carries exactly the playfield's placements.
    expected = _playfield_gnmy(wld.parse_file(path), level.playfield)
    assert len(level.gnmy) == len(expected)
    assert len(level.gnmy) > 0
    assert [(e.x, e.y, e.type_index) for e in level.gnmy] == [
        (e.x, e.y, e.type_index) for e in expected
    ]
    # Every placement resolved its type to an NMY record name (Q32).
    assert all(entry.name for entry in level.gnmy)

    state = new_game_state(level, spawn_x=0.0, spawn_y=0.0)
    frame = render_tiles(level, state)
    cam_x, cam_y = camera(level, state.player, frame.width, frame.height)

    # Every in-view placement paints its name-styled marker at its exact
    # pixel — except inside the player marker, which is drawn last and wins.
    px = int(state.player.x) - cam_x
    py = int(state.player.y) - cam_y
    in_view = 0
    painted = 0
    for entry in level.gnmy:
        sx, sy = entry.x - cam_x, entry.y - cam_y
        if not (0 <= sx < frame.width and 0 <= sy < frame.height):
            continue
        in_view += 1
        if px <= sx < px + state.player.width and py <= sy < py + state.player.height:
            continue
        if frame.pixel(sx, sy) == gnmy_marker(entry.name).colour:
            painted += 1

    print(
        f"GNMY: {len(level.gnmy)} placements, {in_view} in view at spawn, "
        f"{painted} markers painted"
    )
    assert in_view > 0
    assert painted == in_view


def test_sta2_idle_clip_resolves_from_the_retail_clip_table() -> None:
    """AN6: ``STA2`` has 10 poses, bottom-anchored, and is selectable as idle."""
    path = Path(GAME_DIR or "") / "WORLDS" / "VILLAGE.WLD"
    if not path.is_file():
        pytest.skip("VILLAGE.WLD not present in this install")

    level = load_level(path)
    poses = level.clips.get("STA2", ())
    offsets = [(p.dx, p.dy, p.pixels.height) for p in poses]
    print(f"STA2: {len(poses)} poses; (dx, dy, height) per pose: {offsets}")
    print(f"STA1: {len(level.clips['STA1'])} poses")
    assert len(poses) == STA2_POSES
    assert len(level.clips["STA1"]) == STA1_POSES
    assert all(p.dy + p.pixels.height - 1 == 0 for p in poses)

    player = Player(x=0.0, y=0.0, on_ground=True, idle_clip_tag="STA2", idle_frame=9)
    assert select_clip(player) == ("STA2", 9)
    assert level.clip_pose("STA2", 9) is not None
