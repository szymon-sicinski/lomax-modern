"""CLI wiring for the two ANIM/NMY commands.

They are distinct on purpose: ``probe-anim-nmy`` is the structural probe that
scores hypotheses and never claims a parse, while ``anim-nmy`` decodes the
recovered framings.  A merge once collapsed the two handlers into one name, so
the separation is pinned here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lomax_modern.cli import _cmd_anim_nmy, _cmd_probe_anim_nmy, build_parser, main


def _subparser(name: str):
    parser = build_parser()
    import argparse

    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return action.choices[name]


def test_both_commands_are_registered() -> None:
    assert _subparser("probe-anim-nmy").get_default("func") is _cmd_probe_anim_nmy
    assert _subparser("anim-nmy").get_default("func") is _cmd_anim_nmy


def test_anim_nmy_takes_optional_game_dir(tmp_path: Path) -> None:
    args = build_parser().parse_args(["anim-nmy", str(tmp_path)])
    assert args.game_dir == str(tmp_path)
    assert build_parser().parse_args(["anim-nmy"]).game_dir is None


def test_anim_nmy_missing_folder_is_usage_error(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.delenv("LOMAX_GAME_DIR", raising=False)
    assert main(["anim-nmy"]) == 2
    assert "LOMAX_GAME_DIR" in capsys.readouterr().err


def test_anim_nmy_without_worlds_exits_2(tmp_path: Path) -> None:
    assert main(["anim-nmy", str(tmp_path)]) == 2


def test_probe_still_requires_a_directory() -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["probe-anim-nmy"])
    assert exc.value.code == 2
