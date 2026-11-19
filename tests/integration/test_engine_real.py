"""Engine-core check against a real installation (opt-in).

Set ``LOMAX_GAME_DIR`` to a folder containing ``LOMAX.EXE`` to run this.  It is
read-only on the install and prints counts, positions and flags only — no game
bytes, no digests.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lomax_modern.engine import (
    load_level,
    new_game_state,
    render,
    render_tiles,
    run_slice,
)

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
