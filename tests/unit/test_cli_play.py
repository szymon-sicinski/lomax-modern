"""Tests for the ``play`` subcommand (C-playable card P4).

``play`` is ``window`` with a keyboard-driven input script: each tick polls
``Window.poll_input`` (held keys + the press edge) and folds it through the P3
``Keymap`` into one ``Input`` fed to ``run_slice``'s tick.  Synthetic install
only — no game bytes.  The deterministic tests drive a fake window (recorded
frames + a scripted keyboard), so they run without SDL2; the one ``@needs_sdl2``
test runs the real backend headless under ``SDL_VIDEODRIVER=dummy``.
"""

from __future__ import annotations

import ctypes.util
import time
from pathlib import Path

import pytest

from lomax_modern import cli, sdl_window
from lomax_modern.cli import _cmd_play, build_parser, main
from lomax_modern.engine.entities import Input
from lomax_modern.input import SDLK_RIGHT, SDLK_SPACE
from lomax_modern.sdl_window import MISSING_SDL2_MESSAGE, SDL2MissingError
from tests.fixtures.install import build_install

_SDL2_AVAILABLE = ctypes.util.find_library("SDL2") is not None

needs_sdl2 = pytest.mark.skipif(not _SDL2_AVAILABLE, reason="SDL2 not installed")


class _FakeWindow:
    """Records presented frames and polls a scripted keyboard, no real SDL2."""

    def __init__(self, source_size, surface_size):
        self.source_size = source_size
        self.surface_size = surface_size
        self.layout = sdl_window.plan_layout(source_size, surface_size)
        self.presented = []
        self.titles = []
        self.closed = False
        self.poll_count = 0
        #: The keyboard state returned by every ``poll_input`` call.
        self.held = frozenset()
        self.pressed = frozenset()
        self.quit = False

    def present(self, frame):
        self.presented.append(frame)

    def poll_input(self):
        self.poll_count += 1
        return self.held, self.pressed, self.quit

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


def test_play_is_registered() -> None:
    args = build_parser().parse_args(["play", "/tmp/game"])
    assert args.command == "play"
    assert args.game_dir == "/tmp/game"
    assert args.world == "VILLAGE"
    assert args.seconds == 60
    assert args.modern is None  # no toggle flag -> modern default in _cmd_play
    assert args.func is _cmd_play


def test_play_authentic_toggle_parses() -> None:
    args = build_parser().parse_args(["play", "/tmp/game", "--authentic", "--seconds", "7"])
    assert args.modern is False
    assert args.seconds == 7


def test_play_rejects_non_positive_seconds(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["play", str(tmp_path), "--seconds", "0"])
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# Deterministic runs through a fake Window (no SDL2, pacing frozen)
# ---------------------------------------------------------------------------


def test_play_presents_exactly_seconds_times_60_frames(tmp_path, monkeypatch, capsys) -> None:
    root = build_install(tmp_path / "game")
    before = _install_snapshot(root)
    created: list = []

    class RecordingWindow(_FakeWindow):
        def __init__(self, *args):
            super().__init__(*args)
            created.append(self)

    monkeypatch.setattr(cli, "Window", RecordingWindow)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    code = main(["play", str(root), "--seconds", "1"])
    out = capsys.readouterr().out
    fake = created[-1]

    assert code == 0, out
    assert len(fake.presented) == 60  # 1 second * 60 Hz
    frame = fake.presented[0]
    assert frame.width == 320
    assert frame.height == 240
    assert len(frame.to_bytes()) == 320 * 240 * 2
    assert fake.closed
    assert fake.poll_count == 60  # the keyboard is polled once per tick
    assert fake.layout == sdl_window.plan_layout((320, 240), (1920, 1080))
    assert "play:" in out
    assert "at 4x" in out
    # Zero writes into the install.
    assert _install_snapshot(root) == before


def test_play_script_maps_keyboard_to_input(tmp_path, monkeypatch) -> None:
    """The script ``play`` hands ``run_slice`` folds the keyboard through the
    keymap: a held right arrow plus a fresh Space press becomes
    ``Input(right=True, jump=True)``."""
    root = build_install(tmp_path / "game")
    captured = {}

    class PlayWindow(_FakeWindow):
        def poll_input(self):
            return frozenset({SDLK_RIGHT}), frozenset({SDLK_SPACE}), False

    monkeypatch.setattr(cli, "Window", PlayWindow)

    def stub_run_slice(*args, **kwargs):
        captured["script"] = kwargs["script"]
        return (None, None)

    monkeypatch.setattr(cli, "run_slice", stub_run_slice)

    code = main(["play", str(root), "--seconds", "1"])

    assert code == 0
    assert captured["script"](0, None) == Input(right=True, jump=True)


def test_play_held_right_walks_not_jumps(tmp_path, monkeypatch) -> None:
    """A held movement key without a fresh jump press drives only that axis."""
    root = build_install(tmp_path / "game")
    captured = {}

    class PlayWindow(_FakeWindow):
        def poll_input(self):
            return frozenset({SDLK_RIGHT}), frozenset(), False

    monkeypatch.setattr(cli, "Window", PlayWindow)

    def stub_run_slice(*args, **kwargs):
        captured["script"] = kwargs["script"]
        return (None, None)

    monkeypatch.setattr(cli, "run_slice", stub_run_slice)

    code = main(["play", str(root), "--seconds", "1"])

    assert code == 0
    assert captured["script"](0, None) == Input(right=True)


def test_play_quits_on_esc_signal(tmp_path, monkeypatch) -> None:
    """A quit from ``poll_input`` stops the loop after the frame is shown."""
    root = build_install(tmp_path / "game")
    created: list = []

    class QuitWindow(_FakeWindow):
        def __init__(self, *args):
            super().__init__(*args)
            created.append(self)

        def poll_input(self):
            return frozenset(), frozenset(), True

    monkeypatch.setattr(cli, "Window", QuitWindow)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    code = main(["play", str(root), "--seconds", "5"])
    fake = created[-1]

    assert code == 0
    assert fake.closed
    assert len(fake.presented) == 1  # the first tick presents, then quits


def test_play_hud_prints_fps_plane_tiles_camera(tmp_path, monkeypatch, capsys) -> None:
    root = build_install(tmp_path / "game")
    # A clock that advances 1.0 s per read makes the ~1/s HUD fire deterministically.
    clock = {"t": 0.0}

    def fake_monotonic() -> float:
        clock["t"] += 1.0
        return clock["t"]

    monkeypatch.setattr(cli, "Window", _FakeWindow)
    monkeypatch.setattr(time, "monotonic", fake_monotonic)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    code = main(["play", str(root), "--seconds", "1"])
    out = capsys.readouterr().out

    assert code == 0
    # The synthetic world is 20x15 cells -> 300 tiles, camera clamped at (0,0).
    assert "plane=VILLAGE" in out
    assert "tiles=300" in out
    assert "camera=(0,0)" in out
    assert "fps=" in out


def test_play_missing_sdl2_prints_one_line_and_exits_1(tmp_path, monkeypatch, capsys) -> None:
    root = build_install(tmp_path / "game")
    monkeypatch.setattr(cli, "Window", _MissingSDL2Window)

    code = main(["play", str(root)])
    out = capsys.readouterr().out

    assert code == 1
    assert MISSING_SDL2_MESSAGE in out
    assert "Traceback" not in out


def test_play_not_a_game_directory_is_refused(tmp_path, monkeypatch, capsys) -> None:
    empty = tmp_path / "random"
    empty.mkdir()
    monkeypatch.setattr(cli, "Window", _FakeWindow)

    code = main(["play", str(empty)])
    err = capsys.readouterr().err

    assert code == 2
    assert "not an unpacked Lomax game directory" in err


# ---------------------------------------------------------------------------
# Real SDL2, headless (dummy driver) — skipped when SDL2 is absent
# ---------------------------------------------------------------------------


@needs_sdl2
def test_play_command_runs_headless(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    root = build_install(tmp_path / "game")
    before = _install_snapshot(root)

    code = main(["play", str(root), "--seconds", "2"])
    out = capsys.readouterr().out

    assert code == 0, out
    assert "120 frames" in out  # 2 seconds * 60 Hz, no early exit on the synthetic world
    assert "fps=" in out  # at least one HUD line within the 2 s run
    assert _install_snapshot(root) == before
