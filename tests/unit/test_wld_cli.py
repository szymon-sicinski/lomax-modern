"""Tests for the ``wld roundtrip`` CLI (synthetic data only).

Every case here exercises the command added by this card and would fail against
``main`` before the change, where ``lomax-modern wld roundtrip`` is not a
registered command (``argparse`` exits 2 with "invalid choice").  The round
trip itself is delegated to :mod:`lomax_modern.wld`, which has its own tests.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lomax_modern.cli import main
from tests.fixtures.synth import synthetic_world


def _write_world(dir: Path, name: str = "TEST.WLD") -> Path:
    dir.mkdir(parents=True, exist_ok=True)
    path = dir / name
    path.write_bytes(synthetic_world(endian=">"))
    return path


def test_roundtrip_command_reports_identical(tmp_path: Path, capsys) -> None:
    path = _write_world(tmp_path)
    assert main(["wld", "roundtrip", "--check", str(path)]) == 0
    out = capsys.readouterr().out
    assert "identical" in out
    assert path.name in out


def test_roundtrip_command_fails_loud_on_bad_file(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "BAD.WLD"
    bad.write_bytes(b"\x00\x01\x02\x03" + b"\x00" * 16)  # non-printable tag
    assert main(["wld", "roundtrip", "--check", str(bad)]) == 1
    captured = capsys.readouterr()
    assert "ERROR" in captured.err
    assert "identical" not in captured.out


def test_roundtrip_without_source_is_usage_error(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.delenv("LOMAX_GAME_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert main(["wld", "roundtrip"]) == 2
    assert "LOMAX_GAME_DIR" in capsys.readouterr().err


def test_roundtrip_uses_game_dir_env(tmp_path: Path, monkeypatch, capsys) -> None:
    worlds = tmp_path / "WORLDS"
    path = _write_world(worlds)
    monkeypatch.setenv("LOMAX_GAME_DIR", str(tmp_path))
    assert main(["wld", "roundtrip", "--check"]) == 0
    out = capsys.readouterr().out
    assert "identical" in out
    assert path.name in out


def test_roundtrip_game_dir_flag(tmp_path: Path, monkeypatch, capsys) -> None:
    worlds = tmp_path / "WORLDS"
    path = _write_world(worlds)
    monkeypatch.delenv("LOMAX_GAME_DIR", raising=False)
    assert main(["wld", "roundtrip", "--check", "--game-dir", str(tmp_path)]) == 0
    assert "identical" in capsys.readouterr().out


def test_wld_roundtrip_is_registered() -> None:
    # The exact command the card's Verify section runs must parse.
    from lomax_modern.cli import build_parser

    args = build_parser().parse_args(["wld", "roundtrip", "--check"])
    assert args.command == "wld"
    assert args.wld_command == "roundtrip"
    assert args.check is True
