"""Art-layer checks against a real installation (opt-in).

Set ``LOMAX_GAME_DIR`` to a folder containing ``LOMAX.EXE`` to run these.  They
are read-only on the install; the sheets they write go to a pytest temp
directory and are never committed.  Output is counts, sizes and offsets only.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lomax_modern import art, png, wld

GAME_DIR = os.environ.get("LOMAX_GAME_DIR")

pytestmark = [
    pytest.mark.realgame,
    pytest.mark.skipif(
        not GAME_DIR or not Path(GAME_DIR).is_dir(),
        reason="set LOMAX_GAME_DIR to a Lomax installation to run",
    ),
]


def worlds() -> list[Path]:
    return sorted((Path(GAME_DIR or "") / "WORLDS").glob("*.WLD"))


def test_every_world_decodes_into_planes() -> None:
    files = worlds()
    assert files, "no *.WLD found: is LOMAX_GAME_DIR the game folder?"

    total_planes = total_cells = total_records = 0
    for path in files:
        world = wld.parse_file(path)
        cells = art.decode_cells(next(c for c in world.chunks if c.tag == "CELL"))
        sections = art.planes(world)
        print(f"{path.name:<14} cells={len(cells):<5} planes={len(sections)}")
        for section in sections:
            plane = section.plane
            assert plane.cell_count == plane.width_cells * plane.height_cells
            assert len(plane.pad) == len(section.map.payload) - plane.cell_count * 3
            assert all(word.index < 0x2000 for record in section.tiles for word in record.words)
        total_planes += len(sections)
        total_cells += len(cells)
        total_records += sum(len(s.tiles) for s in sections)
    print(f"totals: planes={total_planes} cells={total_cells} ttab_records={total_records}")
    assert total_planes == 104
    assert total_cells == 14974
    assert total_records == 75122


def test_bonus_out_of_bank_index_is_preserved() -> None:
    path = Path(GAME_DIR or "") / "WORLDS" / "BONUS.WLD"
    if not path.is_file():
        pytest.skip("BONUS.WLD not present in this install")
    world = wld.parse_file(path)
    cells = art.decode_cells(next(c for c in world.chunks if c.tag == "CELL"))
    indices = [
        word.index
        for section in art.planes(world)
        for record in section.tiles
        for word in record.words
    ]
    over = [index for index in indices if index >= len(cells)]
    print(f"cells={len(cells)} max_index={max(indices)} out_of_bank_words={len(over)}")
    # Q22: index 256 out of a 251-record bank.  Decoding must not clamp it.
    assert 256 in indices
    assert all(index == 256 for index in over)


def test_export_one_world_writes_sheets(tmp_path) -> None:
    path = Path(GAME_DIR or "") / "WORLDS" / "VILLAGE.WLD"
    if not path.is_file():
        pytest.skip("VILLAGE.WLD not present in this install")

    report = art.export_world(path, tmp_path / "art", scale=1)
    text = report.format()
    print(text)

    assert "map cell -> tile record: unresolved (Q20)" in text
    # Q24 (the ANIM layout) is answered; the sheet is missing because
    # sprite-frame export is not implemented, not because the layout is open.
    assert "sprite frames: not exported" in text
    assert "Q24" not in text
    assert report.files and all(p.is_file() and p.stat().st_size > 0 for p in report.files)
    for sheet in report.files:
        assert sheet.read_bytes().startswith(png.SIGNATURE)
    # Sheets describe a real sheet, not a 0-pixel placeholder.
    assert (tmp_path / "art" / "village_cells.png").stat().st_size > 10_000
