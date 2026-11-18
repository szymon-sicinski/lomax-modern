"""End-to-end tests for ``lomax-modern present`` (synthetic install only).

The command is graded on the card's acceptance points: it writes a config file
on first run, resolves the filter at runtime, honours the modern/authentic
toggle, and refuses a directory that is not an unpacked install with a
file-by-file manifest.  The frame comes from the engine over a synthetic world,
so no game bytes are involved anywhere.
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from lomax_modern import png
from lomax_modern.cli import build_parser, main
from lomax_modern.config import PresentSettings, load_config, write_config
from lomax_modern.scaler import Filter
from tests.fixtures.install import build_install

ROOT = Path(__file__).resolve().parents[2]


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == png.SIGNATURE
    return struct.unpack(">II", data[16:24])


def _run(capsys: pytest.CaptureFixture[str], argv: list[str]) -> tuple[int, str, str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _game(tmp_path: Path) -> Path:
    return build_install(tmp_path / "game")


def test_present_help_exits_zero() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "lomax_modern", "present", "--help"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
        timeout=60,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "--authentic" in result.stdout
    assert "--filter" in result.stdout


def test_present_is_registered() -> None:
    args = build_parser().parse_args(["present", "/tmp/game"])

    assert args.command == "present"
    assert args.game_dir == "/tmp/game"
    assert args.modern is None
    assert args.save is False


def test_first_run_uses_modern_defaults_and_writes_the_config(
    tmp_path: Path, capsys
) -> None:
    root = _game(tmp_path)
    config = tmp_path / "config.json"
    frame = tmp_path / "frame.png"

    code, out, err = _run(
        capsys,
        [
            "present",
            str(root),
            "--config",
            str(config),
            "--frame",
            str(frame),
            "--ticks",
            "10",
        ],
    )

    assert code == 0, err
    assert "verdict: complete unpacked install" in out
    assert "LOMAX.EXE" in out and "unused by the engine" in out
    assert "config:" in out and "created with modern defaults" in out
    assert "profile: modern (authentic toggle: off)" in out
    assert "filter: epx-aa (runtime switch" in out
    assert "surface: 1920x1080" in out
    assert "scale: 4x (auto: largest integer fit)" in out
    assert "engine: 10 ticks at 60 Hz" in out
    assert "world: VILLAGE.WLD" in out
    assert config.is_file()
    assert json.loads(config.read_text(encoding="utf-8"))["modern"] is True
    assert frame.is_file()
    assert _png_size(frame) == (1920, 1080)


def test_authentic_toggle_changes_profile_filter_surface_and_scale(
    tmp_path: Path, capsys
) -> None:
    root = _game(tmp_path)
    config = tmp_path / "config.json"
    frame = tmp_path / "frame.png"

    code, out, err = _run(
        capsys,
        [
            "present",
            str(root),
            "--config",
            str(config),
            "--authentic",
            "--frame",
            str(frame),
            "--ticks",
            "5",
        ],
    )

    assert code == 0, err
    assert "profile: authentic (authentic toggle: on)" in out
    assert "filter: nearest (runtime switch" in out
    assert "surface: 320x240" in out
    assert "scale: 1x (auto: largest integer fit)" in out
    assert _png_size(frame) == (320, 240)
    # Without --save the file keeps the documented modern defaults.
    assert json.loads(config.read_text(encoding="utf-8"))["modern"] is True


def test_save_persists_the_toggle_for_the_next_run(tmp_path: Path, capsys) -> None:
    root = _game(tmp_path)
    config = tmp_path / "config.json"

    code, out, err = _run(
        capsys,
        [
            "present",
            str(root),
            "--config",
            str(config),
            "--authentic",
            "--surface",
            "640x480",
            "--save",
            "--ticks",
            "1",
        ],
    )

    assert code == 0, err
    assert "saved:" in out
    saved = json.loads(config.read_text(encoding="utf-8"))
    assert saved["modern"] is False
    assert saved["filter"] == "nearest"
    assert saved["surface"] == [640, 480]

    code, out, err = _run(
        capsys,
        ["present", str(root), "--config", str(config), "--ticks", "1"],
    )

    assert code == 0, err
    assert "profile: authentic" in out
    assert "surface: 640x480" in out


def test_stored_config_is_honoured_and_flag_overrides_only_this_run(
    tmp_path: Path, capsys
) -> None:
    root = _game(tmp_path)
    config = tmp_path / "config.json"
    write_config(
        config,
        PresentSettings(modern=True, filter=Filter.NEAREST, surface=(640, 480)),
    )

    code, out, err = _run(
        capsys,
        ["present", str(root), "--config", str(config), "--ticks", "1"],
    )

    assert code == 0, err
    assert "filter: nearest" in out
    assert "surface: 640x480" in out

    code, out, err = _run(
        capsys,
        [
            "present",
            str(root),
            "--config",
            str(config),
            "--filter",
            "epx-aa",
            "--ticks",
            "1",
        ],
    )

    assert code == 0, err
    assert "filter: epx-aa" in out
    assert load_config(config).filter is Filter.NEAREST


def test_runtime_filter_switch_changes_the_written_frame(tmp_path: Path, capsys) -> None:
    root = _game(tmp_path)
    config = tmp_path / "config.json"
    write_config(config, PresentSettings(surface=(640, 480)))

    frames = {}
    for name in ("nearest", "epx-aa"):
        path = tmp_path / f"{name}.png"
        code, out, err = _run(
            capsys,
            [
                "present",
                str(root),
                "--config",
                str(config),
                "--filter",
                name,
                "--frame",
                str(path),
                "--ticks",
                "5",
            ],
        )
        assert code == 0, err
        assert f"filter: {name}" in out
        frames[name] = path.read_bytes()

    assert frames["nearest"] != frames["epx-aa"]


def test_scale_auto_returns_to_the_largest_fit(tmp_path: Path, capsys) -> None:
    root = _game(tmp_path)
    config = tmp_path / "config.json"
    write_config(config, PresentSettings(surface=(960, 720), scale=2))

    code, out, err = _run(
        capsys,
        ["present", str(root), "--config", str(config), "--scale", "auto", "--ticks", "1"],
    )

    assert code == 0, err
    assert "scale: 3x (auto: largest integer fit)" in out


def test_scale_that_does_not_fit_is_a_usage_error(tmp_path: Path, capsys) -> None:
    root = _game(tmp_path)

    code, out, err = _run(
        capsys,
        [
            "present",
            str(root),
            "--config",
            str(tmp_path / "config.json"),
            "--scale",
            "99",
            "--ticks",
            "1",
        ],
    )

    assert code == 2
    assert "does not fit" in err
    assert "largest integer fit" in err


def test_not_a_game_directory_is_refused_with_a_manifest(
    tmp_path: Path, capsys
) -> None:
    empty = tmp_path / "random-folder"
    empty.mkdir()
    config = tmp_path / "config.json"

    code, out, err = _run(
        capsys, ["present", str(empty), "--config", str(config)]
    )

    assert code == 2
    assert out == ""
    assert "not an unpacked Lomax game directory" in err
    assert "WORLDS/" in err and "MISSING" in err
    assert "LOMAX.EXE" in err
    assert not config.exists()


def test_a_file_path_is_refused_as_not_a_directory(tmp_path: Path, capsys) -> None:
    target = tmp_path / "LOMAX.EXE"
    target.write_bytes(b"MZ")

    code, out, err = _run(
        capsys, ["present", str(target), "--config", str(tmp_path / "config.json")]
    )

    assert code == 2
    assert "not a directory" in err


def test_nested_install_root_is_reported_and_used(tmp_path: Path, capsys) -> None:
    slot = tmp_path / "slot"
    root = build_install(slot / "LOMAX")

    code, out, err = _run(
        capsys,
        [
            "present",
            str(slot),
            "--config",
            str(tmp_path / "config.json"),
            "--surface",
            "320x240",
            "--ticks",
            "1",
        ],
    )

    assert code == 0, err
    assert f"requested: {slot}" in out
    assert f"install: {root}" in out
    assert "one level down" in out


def test_incomplete_optional_folders_still_run(tmp_path: Path, capsys) -> None:
    root = build_install(tmp_path / "game", dirs=())

    code, out, err = _run(
        capsys,
        [
            "present",
            str(root),
            "--config",
            str(tmp_path / "config.json"),
            "--surface",
            "320x240",
            "--ticks",
            "1",
        ],
    )

    assert code == 0, err
    assert "incomplete optional entries" in out
    assert "SFX/" in out


def test_lower_case_layout_runs(tmp_path: Path, capsys) -> None:
    root = build_install(
        tmp_path / "game",
        worlds_dir="worlds",
        exe="lomax.exe",
        dirs=("sfx", "ambient", "jingles", "demos"),
    )

    code, out, err = _run(
        capsys,
        [
            "present",
            str(root),
            "--config",
            str(tmp_path / "config.json"),
            "--surface",
            "320x240",
            "--ticks",
            "1",
        ],
    )

    assert code == 0, err
    assert "world: VILLAGE.WLD" in out


def test_unknown_world_lists_the_available_ones(tmp_path: Path, capsys) -> None:
    root = build_install(tmp_path / "game", worlds=("VILLAGE", "HAUNTED"))

    code, out, err = _run(
        capsys,
        [
            "present",
            str(root),
            "--config",
            str(tmp_path / "config.json"),
            "--world",
            "BONUS",
        ],
    )

    assert code == 2
    assert "BONUS" in err
    assert "VILLAGE" in err and "HAUNTED" in err


def test_config_inside_the_game_folder_is_refused(tmp_path: Path, capsys) -> None:
    root = _game(tmp_path)
    config = root / "config.json"

    code, out, err = _run(capsys, ["present", str(root), "--config", str(config)])

    assert code == 2
    assert "refusing to write the config inside the game folder" in err
    assert not config.exists()


def test_frame_inside_the_game_folder_is_refused(tmp_path: Path, capsys) -> None:
    root = _game(tmp_path)

    code, out, err = _run(
        capsys,
        [
            "present",
            str(root),
            "--config",
            str(tmp_path / "config.json"),
            "--frame",
            str(root / "frame.png"),
        ],
    )

    assert code == 2
    assert "--frame must not be written inside the game folder" in err
    assert not (root / "frame.png").exists()


def test_malformed_config_is_a_usage_error(tmp_path: Path, capsys) -> None:
    root = _game(tmp_path)
    config = tmp_path / "config.json"
    config.write_text("{not json", encoding="utf-8")

    code, out, err = _run(capsys, ["present", str(root), "--config", str(config)])

    assert code == 2
    assert "invalid JSON" in err
    assert str(config) in err


def test_bad_surface_syntax_is_an_argparse_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as caught:
        build_parser().parse_args(
            ["present", str(tmp_path), "--surface", "wide"]
        )

    assert caught.value.code == 2
