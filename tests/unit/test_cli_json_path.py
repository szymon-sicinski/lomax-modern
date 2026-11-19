"""The ``--json`` report path obeys the install-folder rule.

Every writer in the CLI refuses to put a derived artifact inside a game folder
(the marker is ``LOMAX.EXE``): ``export --out``, ``slice --out``/``--frame``,
``present --frame`` and ``gif --out`` all go through
:func:`lomax_modern.art.refuse_into_game_folder`. ``measure`` and
``probe-anim-nmy`` were the exception: their ``--json`` destination was written
wherever it pointed. These tests pin the shared refusal (exit 2, the same
wording), the unchanged behaviour outside the install, and that a relative
``--json`` is resolved against the working directory before it is checked.

Everything here is synthetic: :mod:`tests.fixtures.install` builds an install
whose executable is a 64-byte ``MZ`` stub and whose worlds come from
:mod:`tests.fixtures.synth`. No game bytes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lomax_modern.cli import main
from tests.fixtures.install import build_install

COMMANDS = ("measure", "probe-anim-nmy")

#: A top-level key each command's report always has, so "wrote a report" is
#: checked against the real payload rather than just a non-empty file.
REPORT_KEYS = {"measure": "worlds", "probe-anim-nmy": "chunk_offsets"}


def _game(tmp_path: Path) -> Path:
    return build_install(tmp_path / "game")


@pytest.mark.parametrize("command", COMMANDS)
def test_json_inside_the_install_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture, command: str
) -> None:
    game = _game(tmp_path)
    target = game / "report.json"

    assert main([command, str(game), "--json", str(target)]) == 2

    err = capsys.readouterr().err
    assert "refusing to write inside the game folder" in err
    assert str(game.resolve()) in err
    assert not target.exists()


@pytest.mark.parametrize("command", COMMANDS)
def test_json_in_a_subfolder_of_the_install_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture, command: str
) -> None:
    """The marker is searched upward, so ``<install>/WORLDS/report.json`` fails."""
    game = _game(tmp_path)
    target = game / "WORLDS" / "report.json"

    assert main([command, str(game), "--json", str(target)]) == 2
    assert "refusing to write inside the game folder" in capsys.readouterr().err
    assert not target.exists()


@pytest.mark.parametrize("command", COMMANDS)
def test_json_outside_the_install_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture, command: str
) -> None:
    game = _game(tmp_path)
    target = tmp_path / f"{command}.json"

    assert main([command, str(game), "--json", str(target)]) == 0

    report = json.loads(target.read_text(encoding="utf-8"))
    assert REPORT_KEYS[command] in report
    assert report["game_dir"] == str(game)


@pytest.mark.parametrize("command", COMMANDS)
def test_json_outside_still_reaches_stdout_json_with_quiet(
    tmp_path: Path, capsys: pytest.CaptureFixture, command: str
) -> None:
    """``--quiet`` (JSON on stdout) keeps working alongside a guarded path."""
    game = _game(tmp_path)
    target = tmp_path / "report.json"

    assert main([command, str(game), "--json", str(target), "--quiet"]) == 0

    printed = json.loads(capsys.readouterr().out)
    assert REPORT_KEYS[command] in printed
    assert json.loads(target.read_text(encoding="utf-8")) == printed


def test_relative_json_path_is_checked_against_the_working_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bare ``--json report.json`` from inside the install is refused too."""
    game = _game(tmp_path)
    monkeypatch.chdir(game)

    assert main(["measure", str(game), "--json", "report.json"]) == 2

    assert "refusing to write inside the game folder" in capsys.readouterr().err
    assert not (game / "report.json").exists()


def test_json_dash_is_a_literal_filename_not_a_stdout_sentinel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--json -`` writes a file named ``-``; it was never a stdout sentinel.

    ``--quiet`` is the documented way to get the report on stdout. This test
    only pins that the new guard does not change the meaning of ``-``.
    """
    game = _game(tmp_path)
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    assert main(["measure", str(game), "--json", "-"]) == 0

    dash = workdir / "-"
    assert dash.is_file()
    assert "worlds" in json.loads(dash.read_text(encoding="utf-8"))
