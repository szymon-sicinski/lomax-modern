"""Tests for the SDL2 window backend (``lomax_modern.sdl_window``).

Synthetic buffers only — no game bytes.  The pure pieces (geometry, frame
coercion, pacing, event decoding) are tested directly; the two SDL2-touching
tests run under ``SDL_VIDEODRIVER=dummy`` and are skipped when SDL2 is not
installed.  The missing-library path is exercised by injecting a finder that
returns ``None``.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import struct
import time

import pytest

from lomax_modern import sdl_window
from lomax_modern.input import SDLK_LEFT, SDLK_RIGHT, SDLK_SPACE
from lomax_modern.sdl_window import (
    SDL_KEYDOWN,
    SDL_KEYUP,
    SDL_PIXELFORMAT_RGB565,
    SDL_QUIT,
    SDLK_ESCAPE,
    Layout,
    Window,
    _decode_event,
    _decode_key_event,
    _frame_bytes,
    _sleep_to,
    _synthetic_frames,
    fold_key_events,
    load_sdl2,
    open_window,
    plan_layout,
)

_SDL2_AVAILABLE = ctypes.util.find_library("SDL2") is not None

needs_sdl2 = pytest.mark.skipif(not _SDL2_AVAILABLE, reason="SDL2 not installed")


# ---------------------------------------------------------------------------
# Missing library
# ---------------------------------------------------------------------------


def test_load_sdl2_missing_raises() -> None:
    with pytest.raises(sdl_window.SDL2MissingError) as excinfo:
        load_sdl2(finder=lambda: None)
    assert str(excinfo.value) == sdl_window.MISSING_SDL2_MESSAGE


def test_open_window_missing_prints_one_line_and_exits(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as excinfo:
        open_window((320, 240), (320, 240), finder=lambda: None)
    assert excinfo.value.code == 1
    out = capsys.readouterr().out
    assert out == sdl_window.MISSING_SDL2_MESSAGE + "\n"
    assert "Traceback" not in out


# ---------------------------------------------------------------------------
# Geometry: integer fit + letterbox
# ---------------------------------------------------------------------------


def test_plan_layout_modern_integer_fit() -> None:
    # 320x240 fits 1920x1080 at 4x: 1280x960 centred with 320/60 pads.
    layout = plan_layout((320, 240), (1920, 1080))
    assert layout == Layout(scale=4, x=320, y=60, width=1280, height=960)


def test_plan_layout_authentic_is_1x() -> None:
    assert plan_layout((320, 240), (320, 240)) == Layout(scale=1, x=0, y=0, width=320, height=240)


def test_plan_layout_rejects_surface_too_small() -> None:
    with pytest.raises(ValueError):
        plan_layout((320, 240), (160, 120))


# ---------------------------------------------------------------------------
# Frame coercion (B5G6R5 -> bytes)
# ---------------------------------------------------------------------------


class _FrameLike:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def to_bytes(self) -> bytes:
        return self._data


def test_frame_bytes_accepts_bytes() -> None:
    assert _frame_bytes(b"\x00\xf8", 2) == b"\x00\xf8"


def test_frame_bytes_accepts_to_bytes_object() -> None:
    assert _frame_bytes(_FrameLike(b"\xe0\x07"), 2) == b"\xe0\x07"


def test_frame_bytes_rejects_wrong_length() -> None:
    with pytest.raises(ValueError):
        _frame_bytes(b"\x00\xf8", 4)


def test_frame_bytes_rejects_non_frame() -> None:
    with pytest.raises(TypeError):
        _frame_bytes(12345, 2)


# ---------------------------------------------------------------------------
# Event decoding (synthetic 56-byte SDL_Event buffers)
# ---------------------------------------------------------------------------


def _event(event_type: int, key_sym: int = 0) -> bytes:
    raw = bytearray(sdl_window._SDL_EVENT_SIZE)
    struct.pack_into("<I", raw, 0, event_type)
    struct.pack_into("<i", raw, sdl_window._KEY_SYM_OFFSET, key_sym)
    return bytes(raw)


def test_decode_event_quit() -> None:
    assert _decode_event(_event(SDL_QUIT)) == (SDL_QUIT, 0)


def test_decode_event_keydown_escape() -> None:
    assert _decode_event(_event(SDL_KEYDOWN, SDLK_ESCAPE)) == (SDL_KEYDOWN, SDLK_ESCAPE)


def test_decode_event_keydown_other_key() -> None:
    event_type, key = _decode_event(_event(SDL_KEYDOWN, ord("a")))
    assert event_type == SDL_KEYDOWN
    assert key != SDLK_ESCAPE


def _key_event(event_type: int, key_sym: int = 0, repeat: int = 0) -> bytes:
    raw = bytearray(sdl_window._SDL_EVENT_SIZE)
    struct.pack_into("<I", raw, 0, event_type)
    struct.pack_into("<i", raw, sdl_window._KEY_SYM_OFFSET, key_sym)
    raw[sdl_window._KEY_REPEAT_OFFSET] = repeat
    return bytes(raw)


def test_decode_key_event_keydown_no_repeat() -> None:
    assert _decode_key_event(_key_event(SDL_KEYDOWN, SDLK_RIGHT)) == (
        SDL_KEYDOWN,
        SDLK_RIGHT,
        0,
    )


def test_decode_key_event_keydown_repeat() -> None:
    assert _decode_key_event(_key_event(SDL_KEYDOWN, SDLK_RIGHT, 1)) == (
        SDL_KEYDOWN,
        SDLK_RIGHT,
        1,
    )


def test_decode_key_event_keyup() -> None:
    assert _decode_key_event(_key_event(SDL_KEYUP, SDLK_RIGHT)) == (
        SDL_KEYUP,
        SDLK_RIGHT,
        0,
    )


# ---------------------------------------------------------------------------
# Keyboard state folding (held + press edge), pure
# ---------------------------------------------------------------------------


def test_fold_key_events_empty() -> None:
    assert fold_key_events([]) == (frozenset(), frozenset())


def test_fold_key_events_keydown_held_and_pressed() -> None:
    held, pressed = fold_key_events([(SDL_KEYDOWN, SDLK_RIGHT, 0)])
    assert held == frozenset({SDLK_RIGHT})
    assert pressed == frozenset({SDLK_RIGHT})


def test_fold_key_events_repeat_is_held_not_pressed() -> None:
    # A held key that repeats re-adds to `held` but never re-edges `pressed`.
    held, pressed = fold_key_events([(SDL_KEYDOWN, SDLK_RIGHT, 1)], held={SDLK_RIGHT})
    assert held == frozenset({SDLK_RIGHT})
    assert pressed == frozenset()


def test_fold_key_events_keyup_removes() -> None:
    held, pressed = fold_key_events(
        [(SDL_KEYUP, SDLK_RIGHT, 0)], held={SDLK_RIGHT, SDLK_LEFT}
    )
    assert held == frozenset({SDLK_LEFT})
    assert pressed == frozenset()


def test_fold_key_events_press_repeat_release() -> None:
    held, pressed = fold_key_events(
        [
            (SDL_KEYDOWN, SDLK_RIGHT, 0),
            (SDL_KEYDOWN, SDLK_RIGHT, 1),
            (SDL_KEYUP, SDLK_RIGHT, 0),
        ]
    )
    assert held == frozenset()
    assert pressed == frozenset({SDLK_RIGHT})


def test_fold_key_events_press_and_release_same_tick() -> None:
    # A tap (down then up within one poll) ends held but still carries the edge.
    held, pressed = fold_key_events(
        [(SDL_KEYDOWN, SDLK_SPACE, 0), (SDL_KEYUP, SDLK_SPACE, 0)]
    )
    assert held == frozenset()
    assert pressed == frozenset({SDLK_SPACE})


# ---------------------------------------------------------------------------
# Pacing: sleep the remaining budget, never a spin
# ---------------------------------------------------------------------------


def test_sleep_to_sleeps_remaining_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(time, "sleep", sleeps.append)
    _sleep_to(0.0, 1 / 60)
    assert sleeps == [pytest.approx(1 / 60)]


def test_sleep_to_skips_when_over_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(time, "monotonic", lambda: 0.1)  # already 100 ms into a 16.67 ms tick
    monkeypatch.setattr(time, "sleep", sleeps.append)
    _sleep_to(0.0, 1 / 60)
    assert sleeps == []


# ---------------------------------------------------------------------------
# Synthetic animated pattern
# ---------------------------------------------------------------------------


def test_synthetic_frames_are_correct_size_and_animate() -> None:
    frames = _synthetic_frames((320, 240))
    first = next(frames)
    second = next(frames)
    assert len(first) == 320 * 240 * 2
    assert len(second) == 320 * 240 * 2
    assert first != second  # the bar sweeps, so consecutive frames differ


# ---------------------------------------------------------------------------
# The paced loop, driven by a fake Window (no real SDL2)
# ---------------------------------------------------------------------------


class _FakeWindow:
    def __init__(self, source_size, surface_size, *, title, finder):
        self.source_size = source_size
        self.surface_size = surface_size
        self.title = title
        self.presented: list[bytes] = []
        self.quit_after = None
        self.closed = False

    def present(self, frame):
        self.presented.append(bytes(frame))

    def poll_quit(self):
        if self.quit_after is not None and len(self.presented) >= self.quit_after:
            return True
        return False

    def close(self):
        self.closed = True


def _freeze_pacing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda *_: None)


def test_open_window_loop_quits_on_escape_like_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeWindow((320, 240), (320, 240), title="t", finder=lambda: "x")
    fake.quit_after = 3
    monkeypatch.setattr(sdl_window, "Window", lambda *a, **k: fake)
    _freeze_pacing(monkeypatch)

    open_window((320, 240), (320, 240), max_frames=100)

    assert len(fake.presented) == 3
    assert fake.closed


def test_open_window_loop_stops_when_frames_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeWindow((2, 1), (2, 1), title="t", finder=lambda: "x")
    monkeypatch.setattr(sdl_window, "Window", lambda *a, **k: fake)
    _freeze_pacing(monkeypatch)

    open_window((2, 1), (2, 1), frames=[b"\x00\xf8\xe0\x07", b"\x1f\x00\x00\x00"])

    assert len(fake.presented) == 2
    assert fake.closed


def test_open_window_loop_respects_max_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeWindow((2, 1), (2, 1), title="t", finder=lambda: "x")
    monkeypatch.setattr(sdl_window, "Window", lambda *a, **k: fake)
    _freeze_pacing(monkeypatch)

    open_window((2, 1), (2, 1), max_frames=5)

    assert len(fake.presented) == 5
    assert fake.closed


# ---------------------------------------------------------------------------
# Real SDL2, headless (dummy driver) — skipped when SDL2 is absent
# ---------------------------------------------------------------------------


@needs_sdl2
def test_rgb565_format_constant_matches_sdl2() -> None:
    """Pin ``SDL_PIXELFORMAT_RGB565`` against the real SDL2 mask tables."""
    sdl = load_sdl2()
    bpp, rmask, gmask, bmask, amask = sdl.pixel_format_masks(SDL_PIXELFORMAT_RGB565)
    assert bpp == 16
    assert rmask == 0xF800
    assert gmask == 0x07E0
    assert bmask == 0x001F
    assert amask == 0


@needs_sdl2
def test_window_opens_and_closes_headless(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    window = Window((320, 240), (320, 240))
    try:
        assert window.source_size == (320, 240)
        assert window.layout == Layout(scale=1, x=0, y=0, width=320, height=240)
        window.present(next(_synthetic_frames((320, 240))))
        assert window.poll_quit() is False  # dummy driver never delivers events
    finally:
        window.close()


@needs_sdl2
def test_open_window_runs_headless(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    # Opens, presents a few synthetic frames, and closes with no input/display.
    open_window((320, 240), (320, 240), max_frames=3)
