"""Tests for the read-only install inventory."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from lomax_modern.doctor import find_world_files, format_report, inventory
from tests.fixtures.synth import synthetic_world


def _make_install(root: Path) -> Path:
    (root / "WORLDS").mkdir(parents=True)
    (root / "SFX").mkdir()
    (root / "DEMOS").mkdir()
    (root / "JINGLES").mkdir()
    (root / "AMBIENT").mkdir()
    (root / "LOMAX.EXE").write_bytes(b"MZ" + b"\0" * 62)
    (root / "GAME.TXT").write_text("Hello @ marker\n", encoding="ascii")
    (root / "WORLDS" / "MAIN.WLD").write_bytes(synthetic_world())
    (root / "SFX" / "JUMP.WAV").write_bytes(b"RIFF" + b"\0" * 60)
    return root


def test_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        inventory(tmp_path / "nope")


def test_inventory_reports_core_entries(tmp_path: Path) -> None:
    root = _make_install(tmp_path / "game")
    reports = inventory(root)
    by_name = {r.name: r for r in reports}

    assert by_name["LOMAX.EXE"].present
    assert by_name["LOMAX.EXE"].sha256 == hashlib.sha256(
        (root / "LOMAX.EXE").read_bytes()
    ).hexdigest()
    assert by_name["WORLDS/"].files == 1
    assert by_name["WORLDS/"].bytes == (root / "WORLDS" / "MAIN.WLD").stat().st_size
    assert by_name["LOMAX.HLP"].present is False


def test_verdict_and_world_listing(tmp_path: Path) -> None:
    root = _make_install(tmp_path / "game")
    worlds = find_world_files(root)
    text = format_report(inventory(root), worlds)

    assert "looks like a complete PC install" in text
    assert "MAIN.WLD" in text
    assert len(worlds) == 1


def test_missing_worlds_changes_verdict(tmp_path: Path) -> None:
    root = _make_install(tmp_path / "game")
    for wld in (root / "WORLDS").iterdir():
        wld.unlink()
    statements: list[str] = []
    text = format_report(inventory(root), find_world_files(root))
    statements.append(text)
    assert "incomplete install" in text
    assert "no *.WLD" in text


def test_report_never_contains_file_contents(tmp_path: Path) -> None:
    root = _make_install(tmp_path / "game")
    (root / "GAME.TXT").write_text("TOP-SECRET-TEXT\n", encoding="ascii")
    text = format_report(inventory(root), find_world_files(root))
    assert "TOP-SECRET-TEXT" not in text
