"""HUD sprites against a real installation (opt-in, read-only, FL13).

Asserts only counts and sizes of what ``MAIN.WLD`` resolves to; no pixel data is
compared or stored.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lomax_modern.engine.hud import load_hud, required_clips

GAME_DIR = os.environ.get("LOMAX_GAME_DIR")

pytestmark = [
    pytest.mark.realgame,
    pytest.mark.skipif(
        not GAME_DIR or not Path(GAME_DIR).is_dir(),
        reason="set LOMAX_GAME_DIR to a Lomax installation to run",
    ),
]

#: Measured keyframe (= pose) counts of the HUD clips in the retail MAIN.WLD.
POSES = {
    "Display.KLEI": 10,
    "Display.GROS": 10,
    "Display.EINS": 3,
    "Display.DREI": 2,
    "Display.VIER": 8,
    "Display.ZWEI": 1,
    "Icons.FUNF": 4,
}


def test_real_main_resolves_every_hud_sprite() -> None:
    path = Path(GAME_DIR or "") / "WORLDS" / "MAIN.WLD"
    if not path.is_file():
        pytest.skip("MAIN.WLD not present in this install")
    hud = load_hud(path)
    assert hud is not None
    assert set(required_clips()) == set(POSES)
    for key, count in POSES.items():
        clip = hud.clips[key]
        assert len(clip.poses) == count, key
        for pose in clip.poses:
            for layer in pose:
                assert layer.width > 0 and layer.height > 0
                assert len(layer.indices) == layer.width * layer.height
    assert len(hud.elements) == 4 and sum(e.live for e in hud.elements) == 2
