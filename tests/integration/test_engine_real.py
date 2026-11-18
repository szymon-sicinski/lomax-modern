"""Engine-core check against a real installation (opt-in).

Set ``LOMAX_GAME_DIR`` to a folder containing ``LOMAX.EXE`` to run this.  It is
read-only on the install and prints counts, positions and flags only — no game
bytes, no digests.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lomax_modern.engine import run_slice

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
    assert "unresolved (Q20)" in report.format()
    assert "Q31" in report.format()
