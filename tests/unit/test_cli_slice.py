"""Regression tests for the ``slice`` subcommand's argument contract.

These exist because PR #20's conflict resolution silently broke ``slice``:
the ``game_dir`` positional disappeared from the subparser while ``_cmd_slice``
kept reading ``args.game_dir``, and the function's trailing ``return 0`` was
absorbed into the newly inserted ``_cmd_probe_anim_nmy``.  CI could not see it —
the workflow smoke test never invoked ``slice`` — so the contract is pinned here
instead.

Synthetic data only; nothing here reads a game installation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from lomax_modern.cli import _cmd_slice, build_parser, main


def test_slice_accepts_game_dir_positional(tmp_path: Path) -> None:
    """`slice <dir>` must parse the directory, not swallow it as an option."""
    args = build_parser().parse_args(["slice", str(tmp_path)])
    assert args.game_dir == str(tmp_path)
    assert args.func is _cmd_slice


def test_slice_game_dir_defaults_to_none() -> None:
    """Bare `slice` is valid: the folder may come from $LOMAX_GAME_DIR."""
    args = build_parser().parse_args(["slice"])
    assert args.game_dir is None


def test_slice_returns_int_when_folder_has_no_worlds(tmp_path: Path) -> None:
    """The command must fail loudly (exit code), never fall off the end.

    A missing ``WORLDS`` directory is an error path, which is enough to prove
    ``main()`` receives an ``int`` from ``_cmd_slice`` — the exact place the
    regression turned into ``TypeError: int() argument must be ... not NoneType``.
    """
    assert main(["slice", str(tmp_path)]) == 1


def test_slice_without_folder_is_usage_error(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.delenv("LOMAX_GAME_DIR", raising=False)
    assert main(["slice"]) == 2
    assert "LOMAX_GAME_DIR" in capsys.readouterr().err


def test_slice_rejects_unknown_flag(tmp_path: Path) -> None:
    """A typo must exit 2 through argparse, not reach the handler."""
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["slice", str(tmp_path), "--nope"])
    assert exc.value.code == 2


def test_slice_handler_signature_matches_namespace() -> None:
    """``_cmd_slice`` must read only fields the parser actually sets."""
    parser = build_parser()
    sub_action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    slice_parser = sub_action.choices["slice"]
    declared = {a.dest for a in slice_parser._actions}
    assert "game_dir" in declared
    assert "world" in declared
    assert "ticks" in declared
    assert "playfield" in declared
    assert "frame" in declared
