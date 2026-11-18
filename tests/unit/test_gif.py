"""Tests for the pure-Python animated GIF writer and the ``gif`` command.

Synthetic frames only: every pixel here is generated in the test, so no game
bytes are involved.  The structural assertions mirror the card's acceptance
points (GIF89a header, logical screen, NETSCAPE2.0 loop, frame count), and the
pixel round trip decodes the LZW streams the encoder produced -- a structural
check alone would pass on a file whose payload is garbage.
"""

from __future__ import annotations

import random
import struct
from pathlib import Path

import pytest

from lomax_modern import gif, png
from lomax_modern.cli import build_parser, main


# ---------------------------------------------------------------------------
# Helpers: build frames, parse the file back
# ---------------------------------------------------------------------------


def solid(width: int, height: int, colour: tuple[int, int, int]) -> bytes:
    """One flat RGBA frame."""
    red, green, blue = colour
    return bytes((red, green, blue, 255)) * (width * height)


def pattern(width: int, height: int) -> bytes:
    """An RGBA frame whose pixels all differ, so LZW has something to do."""
    out = bytearray()
    for y in range(height):
        for x in range(width):
            out += bytes(((x * 37) % 256, (y * 61) % 256, ((x + y) * 11) % 256, 255))
    return bytes(out)


def sub_blocks(data: bytes, offset: int) -> tuple[bytes, int]:
    """Read GIF data sub-blocks; returns ``(payload, offset after terminator)``."""
    payload = bytearray()
    while True:
        size = data[offset]
        offset += 1
        if size == 0:
            return bytes(payload), offset
        payload += data[offset : offset + size]
        offset += size


class ParsedGIF:
    """The pieces of a GIF this test suite cares about."""

    def __init__(self, data: bytes) -> None:
        assert data[:6] == gif.SIGNATURE, data[:6]
        self.data = data
        self.version = data[4:6]
        (
            self.width,
            self.height,
            packed,
            self.background,
            self.aspect,
        ) = struct.unpack("<HHBBB", data[6:13])
        offset = 13
        self.global_palette: tuple[tuple[int, int, int], ...] = ()
        if packed & 0x80:
            size = 2 ** ((packed & 0x07) + 1)
            self.global_palette = _palette(data[offset : offset + size * 3], size)
            offset += size * 3
        self.loop: int | None = None
        self.frames: list[dict] = []
        delay = 0
        while True:
            block = data[offset]
            if block == 0x3B:
                assert offset == len(data) - 1, "trailer must be the last byte"
                break
            if block == 0x21:
                label = data[offset + 1]
                offset += 2
                size = data[offset]
                if label == 0xF9:
                    control = data[offset + 1 : offset + 1 + size]
                    delay = struct.unpack("<H", control[1:3])[0]
                    offset += 1 + size
                    assert data[offset] == 0, "control extension must terminate"
                    offset += 1
                elif label == 0xFF:
                    self.name = data[offset + 1 : offset + 1 + size]
                    offset += 1 + size
                    while True:
                        block_size = data[offset]
                        if block_size == 0:
                            offset += 1
                            break
                        payload = data[offset + 1 : offset + 1 + block_size]
                        if self.name == b"NETSCAPE2.0" and payload[0] == 1:
                            self.loop = struct.unpack("<H", payload[1:3])[0]
                        offset += 1 + block_size
                else:  # pragma: no cover - the writer emits no other extension
                    offset += 1 + size
                    _, offset = sub_blocks(data, offset)
                continue
            assert block == 0x2C, f"unexpected block {block:#04x} at {offset}"
            left, top, frame_width, frame_height, packed = struct.unpack(
                "<HHHHB", data[offset + 1 : offset + 10]
            )
            offset += 10
            palette = self.global_palette
            if packed & 0x80:
                size = 2 ** ((packed & 0x07) + 1)
                palette = _palette(data[offset : offset + size * 3], size)
                offset += size * 3
            min_code_size = data[offset]
            offset += 1
            compressed, offset = sub_blocks(data, offset)
            self.frames.append(
                {
                    "left": left,
                    "top": top,
                    "width": frame_width,
                    "height": frame_height,
                    "delay": delay,
                    "min_code_size": min_code_size,
                    "palette": palette,
                    "indices": lzw_decode(compressed, min_code_size),
                }
            )
        assert offset == len(data) - 1, "trailer must be the last byte"

    def pixels(self, index: int) -> bytes:
        """Reconstruct frame ``index`` as RGBA8888 bytes."""
        frame = self.frames[index]
        out = bytearray()
        for value in frame["indices"]:
            red, green, blue = frame["palette"][value]
            out += bytes((red, green, blue, 255))
        return bytes(out)


def _palette(raw: bytes, size: int) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (raw[index * 3], raw[index * 3 + 1], raw[index * 3 + 2]) for index in range(size)
    )


def lzw_decode(payload: bytes, min_code_size: int) -> bytes:
    """Decode GIF LZW as a browser would; used to prove the payload is real.

    The encoder is cross-checked against Pillow during development; this
    decoder is the in-repo guard, so a future change that breaks the code-width
    progression fails here instead of in someone's browser.
    """
    clear = 1 << min_code_size
    end = clear + 1

    def new_table() -> list[bytes]:
        return [bytes([index]) for index in range(clear)] + [b"", b""]

    table = new_table()
    width = min_code_size + 1
    bit_position = 0
    total_bits = len(payload) * 8
    previous: bytes | None = None
    out = bytearray()
    while bit_position + width <= total_bits:
        code = 0
        for bit in range(width):
            position = bit_position + bit
            if payload[position >> 3] >> (position & 7) & 1:
                code |= 1 << bit
        bit_position += width
        if code == clear:
            table = new_table()
            width = min_code_size + 1
            previous = None
            continue
        if code == end:
            return bytes(out)
        if code < len(table):
            entry = table[code]
        elif code == len(table) and previous is not None:
            entry = previous + previous[:1]
        else:  # pragma: no cover - a corrupt stream, never produced here
            raise AssertionError(f"undecodable LZW code {code} at bit {bit_position}")
        out += entry
        if previous is not None:
            table.append(previous + entry[:1])
            if len(table) == (1 << width) and width < 12:
                width += 1
        previous = entry
    return bytes(out)


# ---------------------------------------------------------------------------
# Encoding: structure
# ---------------------------------------------------------------------------


def test_header_is_gif89a() -> None:
    report = gif.encode(4, 4, [solid(4, 4, (255, 0, 0))] * 3)
    assert report.data[:6] == b"GIF89a"
    assert report.data[-1] == 0x3B


def test_logical_screen_matches_frame_size() -> None:
    report = gif.encode(6, 5, [solid(6, 5, (1, 2, 3))] * 2)
    parsed = ParsedGIF(report.data)
    assert (parsed.width, parsed.height) == (6, 5)
    for frame in parsed.frames:
        assert (frame["left"], frame["top"]) == (0, 0)
        assert (frame["width"], frame["height"]) == (6, 5)


def test_netscape_extension_loops_forever() -> None:
    parsed = ParsedGIF(gif.encode(4, 4, [solid(4, 4, (9, 9, 9))] * 3).data)
    assert parsed.name == b"NETSCAPE2.0"
    assert parsed.loop == 0, "loop count 0 means forever"


def test_frame_count_equals_input_count() -> None:
    frames = [solid(4, 4, (255, 0, 0)), solid(4, 4, (0, 255, 0)), solid(4, 4, (0, 0, 255))]
    report = gif.encode(4, 4, frames)
    parsed = ParsedGIF(report.data)
    assert report.frames == 3
    assert len(parsed.frames) == 3


def test_trivial_animation_is_small() -> None:
    """Three 4x4 flat frames must be a few hundred bytes, not kilobytes."""
    report = gif.encode(4, 4, [solid(4, 4, (0, 0, 0)), solid(4, 4, (255, 255, 255))] * 2)
    assert report.size < 400, report.size


# ---------------------------------------------------------------------------
# Encoding: timing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fps", "expected"),
    [(60, 2), (30, 3), (24, 4), (10, 10), (1000, 1)],
)
def test_delay_is_centiseconds_from_fps(fps: int, expected: int) -> None:
    report = gif.encode(2, 2, [solid(2, 2, (0, 0, 0))], fps=fps)
    assert report.delay_cs == expected
    assert ParsedGIF(report.data).frames[0]["delay"] == expected


def test_delay_never_drops_below_one_centisecond() -> None:
    """GIF cannot express a 0 cs delay: the floor is 1."""
    assert gif.encode(2, 2, [solid(2, 2, (0, 0, 0))], fps=500).delay_cs == 1


def test_default_fps_is_thirty() -> None:
    report = gif.encode(2, 2, [solid(2, 2, (0, 0, 0))])
    assert gif.DEFAULT_FPS == 30
    assert report.delay_cs == 3


def test_zero_or_negative_fps_is_refused() -> None:
    with pytest.raises(gif.GIFError, match="fps must be positive"):
        gif.encode(2, 2, [solid(2, 2, (0, 0, 0))], fps=0)


# ---------------------------------------------------------------------------
# Encoding: sampling
# ---------------------------------------------------------------------------


def test_max_frames_samples_evenly() -> None:
    frames = [solid(2, 2, (index * 20, 0, 0)) for index in range(10)]
    report = gif.encode(2, 2, frames, max_frames=4)
    assert (report.frames, report.frames_seen, report.step) == (4, 10, 3)
    parsed = ParsedGIF(report.data)
    assert len(parsed.frames) == 4
    # Every third frame: 0, 3, 6, 9 -- the frame at tick 0 is kept (red 0).
    assert parsed.pixels(0) == frames[0]
    assert parsed.pixels(1) == frames[3]
    assert parsed.pixels(3) == frames[9]


def test_max_frames_at_or_above_count_keeps_every_frame() -> None:
    frames = [solid(2, 2, (index, 0, 0)) for index in range(5)]
    assert gif.encode(2, 2, frames, max_frames=5).step == 1
    assert gif.encode(2, 2, frames, max_frames=0).frames == 5


def test_negative_max_frames_is_refused() -> None:
    with pytest.raises(gif.GIFError, match="max_frames"):
        gif.encode(2, 2, [solid(2, 2, (0, 0, 0))], max_frames=-1)


# ---------------------------------------------------------------------------
# Encoding: correctness of the pixel payload
# ---------------------------------------------------------------------------


def test_pixels_round_trip_losslessly() -> None:
    """A 200-colour animation must decode back to exactly the input pixels.

    4 096 pixels over 200 colours is long enough for the LZW table to grow to
    12-bit codes and reset, so this pins the payload (indices, code widths and
    sub-block framing), not just the headers.
    """
    rng = random.Random(20261118)
    colours = [
        ((index * 37) % 256, (index * 91) % 256, (index * 53) % 256)
        for index in range(200)
    ]
    frames = []
    for _ in range(2):
        frame = bytearray()
        for _ in range(64 * 64):
            frame += bytes(colours[rng.randrange(len(colours))] + (255,))
        frames.append(bytes(frame))
    parsed = ParsedGIF(gif.encode(64, 64, frames).data)
    assert len(parsed.frames) == 2
    for index, expected in enumerate(frames):
        assert parsed.pixels(index) == expected, f"frame {index} is not lossless"


def test_global_palette_is_used_when_frames_share_their_colours() -> None:
    """Shared colours: one table for the file, no per-frame tables."""
    frames = [solid(4, 4, (255, 0, 0)), solid(4, 4, (0, 0, 0)), solid(4, 4, (255, 0, 0))]
    parsed = ParsedGIF(gif.encode(4, 4, frames).data)
    assert parsed.global_palette, "the global table must be present"
    for frame in parsed.frames:
        assert frame["palette"] == parsed.global_palette
    assert parsed.pixels(0) == frames[0]


def test_per_frame_palette_can_win_and_stays_lossless() -> None:
    """Disjoint small palettes: a table per frame beats one quantised table.

    24 frames of 12 colours pool to 288 colours, so a global table must
    quantise to 256 while every frame is exact with a 16-entry local table.
    This is the branch that makes "encode both, keep the smaller" real.
    """
    rng = random.Random(11)
    frames = []
    for index in range(24):
        colours = [
            (
                (index * 17 + step * 5 + 3) % 256,
                (index * 29 + step * 3 + 7) % 256,
                (index * 41 + step * 11 + 13) % 256,
            )
            for step in range(12)
        ]
        frame = bytearray()
        for _ in range(32 * 32):
            frame += bytes(colours[rng.randrange(len(colours))] + (255,))
        frames.append(bytes(frame))
    report = gif.encode(32, 32, frames)
    assert report.palette.startswith("per frame"), report.palette
    parsed = ParsedGIF(report.data)
    assert parsed.global_palette == (), "no global table when every frame has its own"
    assert len(parsed.frames) == 24
    for index, expected in enumerate(frames):
        assert parsed.pixels(index) == expected, f"frame {index} is not lossless"


def test_two_colour_frame_uses_the_minimum_code_size() -> None:
    """A 2-entry table is 1 bit; the spec floors the LZW code size at 2."""
    frame = bytearray()
    for y in range(8):
        for x in range(8):
            frame += bytes((255, 255, 255, 255) if (x + y) % 2 else (0, 0, 0, 255))
    frame = bytes(frame)
    parsed = ParsedGIF(gif.encode(8, 8, [frame]).data)
    assert parsed.frames[0]["min_code_size"] == 2
    assert parsed.pixels(0) == frame


def test_more_than_256_colours_are_quantised_to_a_256_entry_table() -> None:
    """A 64x64 gradient has 4096 distinct colours: the table must cap at 256."""
    report = gif.encode(64, 64, [pattern(64, 64)])
    parsed = ParsedGIF(report.data)
    assert len(parsed.frames[0]["palette"]) == 256
    assert len(parsed.frames[0]["indices"]) == 64 * 64
    assert max(parsed.frames[0]["indices"]) <= 255


def test_alpha_is_dropped_not_invented() -> None:
    """GIF has no alpha here; a translucent pixel keeps its colour."""
    frame = bytes((10, 20, 30, 0)) * (4 * 4)
    parsed = ParsedGIF(gif.encode(4, 4, [frame]).data)
    assert parsed.pixels(0) == bytes((10, 20, 30, 255)) * (4 * 4)


# ---------------------------------------------------------------------------
# Encoding: refusals
# ---------------------------------------------------------------------------


def test_encoding_is_deterministic() -> None:
    """Same frames in, same bytes out: a demo GIF must be reproducible."""
    frames = [pattern(8, 6), solid(8, 6, (3, 4, 5))]
    assert gif.encode(8, 6, frames).data == gif.encode(8, 6, frames).data


def test_frame_with_wrong_buffer_size_is_refused() -> None:
    frames = [solid(4, 4, (0, 0, 0)), solid(4, 5, (0, 0, 0))]
    with pytest.raises(gif.GIFError, match="frame 1 is 80 bytes, expected 64"):
        gif.encode(4, 4, frames)


def test_empty_sequence_is_refused() -> None:
    with pytest.raises(gif.GIFError, match="no frames"):
        gif.encode(4, 4, [])


def test_zero_dimension_is_refused() -> None:
    with pytest.raises(gif.GIFError, match="must be positive"):
        gif.encode(0, 4, [b""])


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def write_frames(directory: Path, frames: list[bytes], width: int, height: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        png.write(directory / f"frame_{index:04d}.png", width, height, frame)


def test_cli_writes_a_gif_from_a_frame_directory(tmp_path: Path, capsys) -> None:
    frame_dir = tmp_path / "frames"
    width, height = 5, 4
    frames = [solid(width, height, (index * 40, 0, 0)) for index in range(3)]
    write_frames(frame_dir, frames, width, height)
    out = tmp_path / "demo.gif"

    assert main(["gif", str(frame_dir), "--out", str(out), "--fps", "30"]) == 0
    assert out.is_file()
    parsed = ParsedGIF(out.read_bytes())
    assert (parsed.width, parsed.height) == (width, height)
    assert len(parsed.frames) == 3
    for index in range(3):
        assert parsed.pixels(index) == frames[index]
    printed = capsys.readouterr().out
    assert "frames: 3, 5x4" in printed
    assert "timing: 30 fps -> 3 cs per frame, loops forever" in printed
    assert f"size: {len(parsed.data)} bytes" in printed


def test_cli_samples_with_max_frames(tmp_path: Path, capsys) -> None:
    frame_dir = tmp_path / "frames"
    frames = [solid(3, 3, (index, 0, 0)) for index in range(9)]
    write_frames(frame_dir, frames, 3, 3)
    out = tmp_path / "demo.gif"
    assert main(["gif", str(frame_dir), "--out", str(out), "--max-frames", "3"]) == 0
    parsed = ParsedGIF(out.read_bytes())
    assert len(parsed.frames) == 3
    assert parsed.pixels(0) == frames[0]
    assert parsed.pixels(1) == frames[3]
    assert parsed.pixels(2) == frames[6]
    assert "(step 3)" in capsys.readouterr().out


def test_cli_reads_frames_in_numeric_filename_order(tmp_path: Path) -> None:
    """frame_9.png must come before frame_10.png, not after it."""
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    for name, colour in (
        ("frame_10.png", (10, 0, 0)),
        ("frame_2.png", (2, 0, 0)),
        ("frame_9.png", (9, 0, 0)),
    ):
        png.write(frame_dir / name, 2, 2, solid(2, 2, colour))
    out = tmp_path / "demo.gif"
    assert main(["gif", str(frame_dir), "--out", str(out)]) == 0
    parsed = ParsedGIF(out.read_bytes())
    assert [parsed.pixels(index)[:3] for index in range(3)] == [
        bytes((2, 0, 0)),
        bytes((9, 0, 0)),
        bytes((10, 0, 0)),
    ]


def test_cli_refuses_frames_of_different_sizes(tmp_path: Path, capsys) -> None:
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    png.write(frame_dir / "frame_0000.png", 4, 4, solid(4, 4, (0, 0, 0)))
    png.write(frame_dir / "frame_0001.png", 5, 4, solid(5, 4, (0, 0, 0)))
    out = tmp_path / "demo.gif"
    assert main(["gif", str(frame_dir), "--out", str(out)]) == 2
    assert not out.exists(), "a refused sequence must not leave a broken GIF"
    err = capsys.readouterr().err
    assert "frames must all be the same size" in err
    assert "frame_0000.png is 4x4" in err
    assert "frame_0001.png is 5x4" in err


def test_cli_refuses_a_directory_without_png_frames(tmp_path: Path, capsys) -> None:
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    (frame_dir / "notes.txt").write_text("not a frame", encoding="utf-8")
    assert main(["gif", str(frame_dir), "--out", str(tmp_path / "demo.gif")]) == 2
    assert "no *.png frames" in capsys.readouterr().err


def test_cli_refuses_a_missing_directory(tmp_path: Path, capsys) -> None:
    assert main(["gif", str(tmp_path / "nope"), "--out", str(tmp_path / "x.gif")]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_cli_refuses_a_corrupt_png(tmp_path: Path, capsys) -> None:
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    (frame_dir / "frame_0000.png").write_bytes(b"\x89PNG\r\n\x1a\n not really")
    assert main(["gif", str(frame_dir), "--out", str(tmp_path / "demo.gif")]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_refuses_output_inside_a_game_folder(tmp_path: Path, capsys) -> None:
    """The repository never writes into an install, even for a derived file."""
    install = tmp_path / "LOMAX"
    install.mkdir()
    (install / "LOMAX.EXE").write_bytes(b"synthetic stand-in, not game data")
    frame_dir = tmp_path / "frames"
    write_frames(frame_dir, [solid(2, 2, (1, 2, 3))], 2, 2)
    out = install / "demo.gif"
    assert main(["gif", str(frame_dir), "--out", str(out)]) == 2
    assert not out.exists()
    assert "refusing to write inside the game folder" in capsys.readouterr().err


def test_cli_requires_out_and_positive_fps(tmp_path: Path) -> None:
    frame_dir = tmp_path / "frames"
    write_frames(frame_dir, [solid(2, 2, (0, 0, 0))], 2, 2)
    with pytest.raises(SystemExit) as missing:
        main(["gif", str(frame_dir)])
    assert missing.value.code == 2
    with pytest.raises(SystemExit) as zero:
        main(["gif", str(frame_dir), "--out", str(tmp_path / "x.gif"), "--fps", "0"])
    assert zero.value.code == 2


def test_gif_parser_contract() -> None:
    """The subparser exposes the card's flags with the documented defaults."""
    args = build_parser().parse_args(["gif", "frames", "--out", "demo.gif"])
    assert args.func.__name__ == "_cmd_gif"
    assert args.frame_dir == "frames"
    assert args.out == "demo.gif"
    assert args.fps == 30
    assert args.max_frames == 0
