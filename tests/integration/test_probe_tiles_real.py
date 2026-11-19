"""Tile-pipeline probe against a real installation (opt-in).

Set ``LOMAX_GAME_DIR`` to a folder containing ``LOMAX.EXE`` to run these.  They
are read-only; the probe reports counts and offsets only, never payload bytes.
The assertions pin the numbers quoted in ``docs/file-formats.md`` §2.4 so a
regression in the layout is caught here, not in the docs.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lomax_modern.probe_tiles import probe_tiles

GAME_DIR = os.environ.get("LOMAX_GAME_DIR")

pytestmark = [
    pytest.mark.realgame,
    pytest.mark.skipif(
        not GAME_DIR or not Path(GAME_DIR).is_dir(),
        reason="set LOMAX_GAME_DIR to a Lomax installation to run",
    ),
]


def test_recovered_layout_reproduces_documented_counts() -> None:
    report = probe_tiles(GAME_DIR)

    assert report["planes"] == 104

    m = report["map"]
    assert m["words"] == 523_229
    assert m["distinct_words"] == 1_476
    assert m["max_word"] == 1_475
    assert m["out_of_bank"] == 0

    t = report["ttab"]
    assert t["records"] == 37_561
    assert t["slots"] == 150_244
    assert t["distinct_indices"] == 4_909
    assert t["index_max"] == 4_908
    assert t["index_out_of_bank"] == 0
    assert t["flag_flip_counts"] == {
        "0x0000": 131_958,
        "0x2000": 15_787,
        "0x4000": 1_783,
        "0x6000": 716,
    }
    assert t["flag_palette_counts"] == {"0": 21_116, "1": 124_118, "2": 2_913, "3": 2_097}
    assert t["flag_words_with_unused_bits"] == 0

    c = report["collision"]
    assert c["bytes"] == 523_229
    assert c["distinct_values"] == 27
    assert c["zero_count"] == 509_860

    s = report["superseded_hypothesis_scores"]
    # The interleaved MAP reading produces tens of thousands of out-of-bank
    # "tiles"; the recovered split produces none.
    assert s["map_interleaved_out_of_bank"] == 51_381
    # The 13-bit-index reading yields exactly the BONUS flag words misread as
    # "index 256" (palette 1 = 0x0100).
    assert s["ttab_13bit_index_out_of_bank"] == 1_644
    assert s["ttab_13bit_bonus_256_count"] == 1_644
