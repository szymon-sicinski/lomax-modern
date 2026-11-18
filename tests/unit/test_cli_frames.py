"""Tests for the ``--frames N --out DIR`` capture (PNG per 60 Hz tick).

Everything here is synthetic: the frames are :class:`lomax_modern.scaler.Image`
buffers built in the test, and the end-to-end cases run the real CLI over the
synthetic install from :mod:`tests.fixtures.install`.  No game bytes.

The card's acceptance points are pinned directly: one file per tick, the
``frame_0000.png`` naming that ``ffmpeg -i frame_%04d.png`` expects, the
presented dimensions (authentic 320x240, 2x -> 640x480), the two usage errors,
and the refusal to write inside the game folder.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from lomax_modern import png
from lomax_modern.cli import (
    SLICE_CAPTURE_SETTINGS,
    _frame_filename,
    _frame_sink,
    build_parser,
    main,
)
from lomax_modern.config import PresentSettings
from lomax_modern.engine.render import frame_to_rgba
from lomax_modern.engine.run import run_slice
from lomax_modern.presenter import write_presented_png
from lomax_modern.scaler import Filter, Image, Mode
from tests.fixtures.install import build_install

#: BMP-ish red in B5G6R5: max red, no green, no blue.
RED = 0xF800


def _game(tmp_path: Path) -> Path:
    return build_install(tmp_path / "game")


def _frame(width: int = 320, height: int = 240) -> Image:
    """A flat synthetic frame at the engine's native size."""
    return Image.new(Mode.RGB565, width, height, RED)


def _settings(
    surface: tuple[int, int],
    *,
    scale: int | None = None,
    modern: bool = False,
) -> PresentSettings:
    return PresentSettings(
        modern=modern, filter=Filter.NEAREST, surface=surface, scale=scale
    )


def _png_rgba(path: Path) -> tuple[int, int, bytes]:
    """Decode the PNGs this repository writes (8-bit RGBA, filter 0 rows)."""
    data = path.read_bytes()
    assert data[:8] == png.SIGNATURE
    position = 8
    width = height = 0
    idat = bytearray()
    while position < len(data):
        length = struct.unpack(">I", data[position : position + 4])[0]
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        position += 12 + length
        if kind == b"IHDR":
            width, height = struct.unpack(">II", payload[:8])
        elif kind == b"IDAT":
            idat += payload
        elif kind == b"IEND":
            break
    raw = zlib.decompress(bytes(idat))
    stride = width * 4
    rows = bytearray()
    for row in range(height):
        start = row * (stride + 1)
        assert raw[start] == 0, f"row {row} is not filter type 0"
        rows += raw[start + 1 : start + 1 + stride]
    return width, height, bytes(rows)


def _pixel(rgba: bytes, width: int, x: int, y: int) -> tuple[int, ...]:
    base = (y * width + x) * 4
    return tuple(rgba[base : base + 4])


# -- naming ----------------------------------------------------------------


def test_frame_filename_is_zero_padded_to_at_least_four_digits() -> None:
    assert _frame_filename(0) == "frame_0000.png"
    assert _frame_filename(7) == "frame_0007.png"
    assert _frame_filename(9999) == "frame_9999.png"
    # "at least" four: a longer run keeps every tick, nothing is truncated.
    assert _frame_filename(12345) == "frame_12345.png"


# -- one presented PNG -----------------------------------------------------


def test_write_presented_png_scales_a_native_frame_to_the_pinned_factor(
    tmp_path: Path,
) -> None:
    path = tmp_path / "frame.png"

    plan = write_presented_png(path, _frame(), _settings((640, 480), scale=2))

    assert plan.fit.scale == 2
    width, height, _ = _png_rgba(path)
    assert (width, height) == (640, 480)


def test_write_presented_png_letterboxes_on_a_wider_surface(tmp_path: Path) -> None:
    """The pads are the surface's, not the frame's: 800x480 at 2x pads 80 a side."""
    path = tmp_path / "frame.png"

    plan = write_presented_png(path, _frame(), _settings((800, 480), scale=2))

    assert (plan.fit.offset_x, plan.fit.offset_y) == (80, 0)
    width, height, rgba = _png_rgba(path)
    assert (width, height) == (800, 480)
    assert _pixel(rgba, width, 0, 0) == (0, 0, 0, 255)  # pad
    assert _pixel(rgba, width, 79, 0) == (0, 0, 0, 255)  # last pad column
    assert _pixel(rgba, width, 80, 0) == (255, 0, 0, 255)  # first content pixel


def test_write_presented_png_with_the_authentic_profile_keeps_320x240(
    tmp_path: Path,
) -> None:
    path = tmp_path / "frame.png"

    write_presented_png(path, _frame(), SLICE_CAPTURE_SETTINGS)

    width, height, rgba = _png_rgba(path)
    assert (width, height) == (320, 240)
    assert _pixel(rgba, width, 0, 0) == (255, 0, 0, 255)


# -- the sink --------------------------------------------------------------


def test_frame_sink_writes_one_png_per_tick_with_sequential_names(
    tmp_path: Path,
) -> None:
    out = tmp_path / "missing" / "frames"  # created on the first write
    sink = _frame_sink(out, SLICE_CAPTURE_SETTINGS)

    for index in range(3):
        sink(index, _frame())

    names = sorted(path.name for path in out.iterdir())
    assert names == ["frame_0000.png", "frame_0001.png", "frame_0002.png"]
    for name in names:
        width, height, _ = _png_rgba(out / name)
        assert (width, height) == (320, 240)


# -- end to end ------------------------------------------------------------


def test_slice_frames_writes_the_whole_sequence(tmp_path: Path, capsys) -> None:
    game = _game(tmp_path)
    out = tmp_path / "frames"

    code = main(["slice", str(game), "--frames", "3", "--out", str(out)])
    captured = capsys.readouterr()

    assert code == 0, captured.err
    assert sorted(path.name for path in out.iterdir()) == [
        "frame_0000.png",
        "frame_0001.png",
        "frame_0002.png",
    ]
    for path in out.iterdir():
        width, height, _ = _png_rgba(path)
        assert (width, height) == (320, 240)
    assert "frames: 3 PNGs" in captured.out
    assert "frame_0000.png .. frame_0002.png" in captured.out


def test_present_frames_are_presented_at_the_chosen_scale(
    tmp_path: Path, capsys
) -> None:
    game = _game(tmp_path)
    out = tmp_path / "frames"
    config = tmp_path / "config.json"

    code = main(
        [
            "present",
            str(game),
            "--config",
            str(config),
            "--authentic",
            "--surface",
            "640x480",
            "--scale",
            "2",
            "--frames",
            "2",
            "--out",
            str(out),
        ]
    )
    captured = capsys.readouterr()

    assert code == 0, captured.err
    assert sorted(path.name for path in out.iterdir()) == [
        "frame_0000.png",
        "frame_0001.png",
    ]
    for path in out.iterdir():
        width, height, _ = _png_rgba(path)
        assert (width, height) == (640, 480)
    assert "scale: 2x" in captured.out
    assert "frames: 2 PNGs" in captured.out


def test_slice_frame_still_matches_the_engine_frame(tmp_path: Path) -> None:
    """The single-frame export is unchanged by routing it through the presenter."""
    game = _game(tmp_path)
    path = tmp_path / "frame.png"

    assert main(["slice", str(game), "--ticks", "2", "--frame", str(path)]) == 0

    _, frame = run_slice(str(game), max_ticks=2)
    expected = png.encode(frame.width, frame.height, frame_to_rgba(frame))
    assert path.read_bytes() == expected


# -- usage errors ----------------------------------------------------------


def test_frames_without_out_is_a_usage_error(tmp_path: Path, capsys) -> None:
    game = _game(tmp_path)

    code = main(["slice", str(game), "--frames", "3"])
    captured = capsys.readouterr()

    assert code == 2
    assert "--out" in captured.err
    assert not (game / "frame_0000.png").exists()


def test_out_without_frames_is_a_usage_error(tmp_path: Path, capsys) -> None:
    game = _game(tmp_path)
    out = tmp_path / "frames"

    code = main(["slice", str(game), "--out", str(out)])
    captured = capsys.readouterr()

    assert code == 2
    assert "--frames" in captured.err
    assert not out.exists()


@pytest.mark.parametrize("command", ["slice", "present"])
def test_frames_and_frame_are_mutually_exclusive(command: str) -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(
            [command, "/tmp/game", "--frames", "3", "--out", "/tmp/fr",
             "--frame", "/tmp/fr.png"]
        )

    assert exc.value.code == 2


# -- the game folder is read-only -----------------------------------------


def test_slice_frames_refuses_to_write_into_the_game_folder(
    tmp_path: Path, capsys
) -> None:
    game = _game(tmp_path)
    out = game / "capture"

    code = main(["slice", str(game), "--frames", "3", "--out", str(out)])
    captured = capsys.readouterr()

    assert code == 2
    assert "refusing to write" in captured.err
    assert "game folder" in captured.err
    assert not out.exists()


def test_present_frames_refuses_to_write_into_the_game_folder(
    tmp_path: Path, capsys
) -> None:
    game = _game(tmp_path)
    out = game / "worlds" / "capture"
    config = tmp_path / "config.json"

    code = main(
        [
            "present",
            str(game),
            "--config",
            str(config),
            "--frames",
            "2",
            "--out",
            str(out),
        ]
    )
    captured = capsys.readouterr()

    assert code == 2
    assert "refusing to write" in captured.err
    assert not out.exists()
