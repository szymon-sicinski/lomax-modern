"""Integration checks against a real installation (opt-in).

Set ``LOMAX_GAME_DIR`` to a folder containing ``LOMAX.EXE`` to run these.
They are read-only: nothing is written into the game folder.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lomax_modern.doctor import find_world_files, format_report, inventory
from lomax_modern.probe_anim_nmy import format_report as format_probe_report
from lomax_modern.probe_anim_nmy import probe_anim_nmy
from lomax_modern.wldscan import scan_file

GAME_DIR = os.environ.get("LOMAX_GAME_DIR")

pytestmark = [
    pytest.mark.realgame,
    pytest.mark.skipif(
        not GAME_DIR or not Path(GAME_DIR).is_dir(),
        reason="set LOMAX_GAME_DIR to a Lomax installation to run",
    ),
]


def test_inventory_of_real_install() -> None:
    root = Path(GAME_DIR or "")
    text = format_report(inventory(root), find_world_files(root))
    print(text)
    assert "LOMAX.EXE" in text


def test_every_world_file_scans() -> None:
    root = Path(GAME_DIR or "")
    worlds = find_world_files(root)
    assert worlds, "no *.WLD found: is LOMAX_GAME_DIR the game folder?"

    failures = []
    for wld in worlds:
        result = scan_file(wld)
        print(
            f"{wld.name:<16} size={result.file_size:<8} "
            f"layout={result.layout} confidence={result.confidence} "
            f"tags={','.join(result.tags)}"
        )
        if not result.chunks:
            failures.append(wld.name)

    # Record what we learned rather than asserting a layout we have not
    # confirmed yet: this test must not invent a format.
    assert not failures, f"no chunk chain found in: {failures}"


def test_probe_anim_nmy_reports_coverage_scores() -> None:
    root = Path(GAME_DIR or "")
    report = probe_anim_nmy(root)
    print(format_probe_report(report))

    groups = {g["tag"]: g for g in report["groups"]}
    assert set(groups) == {"ANIM", "NMY", "GNMY"}
    assert groups["ANIM"]["chunks"] and groups["NMY"]["chunks"] and groups["GNMY"]["chunks"]

    # The two falsified framings stay retracted; ANIM/NMY have no winning
    # candidate, GNMY's structure is consistent but its meaning is not.
    assert groups["ANIM"]["verdict"] == "unresolved"
    assert groups["NMY"]["verdict"] == "unresolved"
    assert groups["GNMY"]["verdict"] == "structure-consistent (meaning unresolved)"

    def candidate(group: dict, key: str) -> dict:
        return next(c for c in group["candidates"] if c["key"] == key)

    assert candidate(groups["ANIM"], "fixed-0x38")["status"] == "retracted"
    assert candidate(groups["NMY"], "u16-size-nul-name")["status"] == "retracted"

    # The text report labels every framing a hypothesis and never decodes a
    # record table: it carries coverage fractions, not a dump of entries.
    text = format_probe_report(report)
    assert "unresolved" in text and "retracted" in text
    assert "hypothesis" in text
