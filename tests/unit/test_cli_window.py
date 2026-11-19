"""Tests for the ``window`` subcommand (C-animated card B).

The ``window`` command drives ``run_slice``'s ``on_frame`` sink into the SDL2
window backend, letterboxes the 320x240 frame at the integer fit and prints a
one-line HUD.  Synthetic install only — no game bytes.  The deterministic tests
drive a fake window (recorded frames) so they run without SDL2; the one
``@needs_sdl2`` test runs the real backend headless under ``SDL_VIDEODRIVER=dummy``.
"""

from __future__ import annotations

import ctypes.util
import time
from pathlib import Path

import pytest

from lomax_modern import cli, sdl_window
from lomax_modern.cli import _cmd_window, build_parser, main
from lomax_modern.sdl_window import MISSING_SDL2_MESSAGE, SDL2MissingError
from tests.fixtures.install import build_install

_SDL2_AVAILABLE = ctypes.util.find_library("SDL2") is not None

needs_sdl2 = pytest.mark.skipif(not _SDL2_AVAILABLE, reason="SDL2 not installed")


class _FakeWindow:
    """Records presented frames; mirrors the ``Window`` seam card B drives."""

    def __init__(self, source_size, surface_size):
        self.source_size = source_size
        self.surface_size = surface_size
        self.layout = sdl_window.plan_layout(source_size, surface_size)
        self.presented = []
        self.titles = []
        self.closed = False

    def present(self, frame):
        self.presented.append(frame)

    def poll_quit(self):
        return False

    def set_title(self, title):
        self.titles.append(title)

    def close(self):
        self.closed = True


class _MissingSDL2Window:
    """A Window that fails at construction exactly like a missing system lib."""

    def __init__(self, source_size, surface_size):
        raise SDL2MissingError(MISSING_SDL2_MESSAGE)


def _install_snapshot(root: Path) -> tuple[tuple[str, int], ...]:
    """Every file under ``root`` as (relative path, size), sorted — for the
    zero-writes check."""
    return tuple(
        sorted(
            (str(path.relative_to(root)), path.stat().st_size)
            for path in root.rglob("*")
            if path.is_file()
        )
    )


# ---------------------------------------------------------------------------
# Argument contract
# ---------------------------------------------------------------------------


def test_window_is_registered() -> None:
    args = build_parser().parse_args(["window", "/tmp/game"])
    assert args.command == "window"
    assert args.game_dir == "/tmp/game"
    assert args.world == "VILLAGE"
    assert args.seconds == 60
    assert args.modern is None  # no toggle flag -> modern default in _cmd_window
    assert args.func is _cmd_window


def test_window_authentic_toggle_parses() -> None:
    args = build_parser().parse_args(["window", "/tmp/game", "--authentic", "--seconds", "7"])
    assert args.modern is False
    assert args.seconds == 7


def test_window_rejects_non_positive_seconds(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["window", str(tmp_path), "--seconds", "0"])
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# Deterministic runs through a fake Window (no SDL2, pacing frozen)
# ---------------------------------------------------------------------------


def _run_fake_window(monkeypatch, capsys, argv, created):
    monkeypatch.setattr(cli, "Window", _FakeWindow)
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    code = main(argv)
    out = capsys.readouterr().out
    fake = created[-1]
    return code, out, fake


def test_window_presents_exactly_seconds_times_60_frames(tmp_path, monkeypatch, capsys) -> None:
    root = build_install(tmp_path / "game")
    before = _install_snapshot(root)
    created: list = []

    class RecordingWindow(_FakeWindow):
        def __init__(self, *args):
            super().__init__(*args)
            created.append(self)

    monkeypatch.setattr(cli, "Window", RecordingWindow)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    code = main(["window", str(root), "--seconds", "1"])
    out = capsys.readouterr().out
    fake = created[-1]

    assert code == 0, out
    assert len(fake.presented) == 60  # 1 second * 60 Hz
    frame = fake.presented[0]
    assert frame.width == 320
    assert frame.height == 240
    assert len(frame.to_bytes()) == 320 * 240 * 2
    assert fake.closed
    # The modern default: 320x240 integer-fits 1920x1080 at 4x.
    assert fake.layout == sdl_window.plan_layout((320, 240), (1920, 1080))
    assert "1920x1080" in out
    assert "at 4x" in out
    # Zero writes into the install.
    assert _install_snapshot(root) == before


def test_window_authentic_is_320x240_at_1x(tmp_path, monkeypatch, capsys) -> None:
    root = build_install(tmp_path / "game")
    created: list = []

    class RecordingWindow(_FakeWindow):
        def __init__(self, *args):
            super().__init__(*args)
            created.append(self)

    monkeypatch.setattr(cli, "Window", RecordingWindow)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    code = main(["window", str(root), "--authentic", "--seconds", "1"])
    out = capsys.readouterr().out
    fake = created[-1]

    assert code == 0, out
    assert fake.layout == sdl_window.plan_layout((320, 240), (320, 240))
    assert fake.layout.scale == 1
    assert "320x240" in out
    assert "at 1x" in out


def test_hud_line_prints_collect_count() -> None:
    """The HUD formatter appends ``collect N/M`` (P7) — synthetic counts only."""
    line = cli._hud_line(59.9, "ED", 300, 12, 34, 1, 2)
    assert line == "fps=59.9 plane=ED tiles=300 camera=(12,34) collect 1/2"


def test_hud_line_collect_count_at_spawn_and_when_empty() -> None:
    # spawn: nothing picked up yet
    assert cli._hud_line(60.0, "MEDIEVAL", 300, 0, 0, 0, 2).endswith("collect 0/2")
    # a world with no Moneybag placements must read 0/0, not crash or read 100%
    assert cli._hud_line(60.0, "VILLAGE", 300, 0, 0, 0, 0).endswith("collect 0/0")


def test_window_hud_prints_fps_plane_tiles_camera(tmp_path, monkeypatch, capsys) -> None:
    root = build_install(tmp_path / "game")
    # A clock that advances 1.0 s per read makes the ~1/s HUD fire deterministically.
    clock = {"t": 0.0}

    def fake_monotonic() -> float:
        clock["t"] += 1.0
        return clock["t"]

    monkeypatch.setattr(cli, "Window", _FakeWindow)
    monkeypatch.setattr(time, "monotonic", fake_monotonic)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    code = main(["window", str(root), "--seconds", "1"])
    out = capsys.readouterr().out

    assert code == 0
    # The synthetic world is 20x15 cells -> 300 tiles, camera clamped at (0,0).
    assert "plane=VILLAGE" in out
    assert "tiles=300" in out
    assert "camera=(0,0)" in out
    assert "fps=" in out
    # The synthetic world has no Moneybag placement, so the counter reads 0/0.
    assert "collect 0/0" in out


def test_window_missing_sdl2_prints_one_line_and_exits_1(tmp_path, monkeypatch, capsys) -> None:
    root = build_install(tmp_path / "game")
    monkeypatch.setattr(cli, "Window", _MissingSDL2Window)

    code = main(["window", str(root)])
    out = capsys.readouterr().out

    assert code == 1
    assert MISSING_SDL2_MESSAGE in out
    assert "Traceback" not in out


def test_window_not_a_game_directory_is_refused(tmp_path, monkeypatch, capsys) -> None:
    empty = tmp_path / "random"
    empty.mkdir()
    monkeypatch.setattr(cli, "Window", _FakeWindow)

    code = main(["window", str(empty)])
    err = capsys.readouterr().err

    assert code == 2
    assert "not an unpacked Lomax game directory" in err


# ---------------------------------------------------------------------------
# Real SDL2, headless (dummy driver) — skipped when SDL2 is absent
# ---------------------------------------------------------------------------


@needs_sdl2
def test_window_command_runs_headless(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    root = build_install(tmp_path / "game")
    before = _install_snapshot(root)

    code = main(["window", str(root), "--seconds", "2"])
    out = capsys.readouterr().out

    assert code == 0, out
    assert "120 frames" in out  # 2 seconds * 60 Hz, no early exit on the synthetic world
    assert "fps=" in out  # at least one HUD line within the 2 s run
    assert _install_snapshot(root) == before
