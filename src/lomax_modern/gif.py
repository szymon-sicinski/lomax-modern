"""Minimal animated GIF89a writer — standard library only.

Why this module exists
----------------------
The demo path ends in one shareable file: ``slice --frames`` writes a PNG per
60 Hz tick, and a README or a chat window needs a single animated image.  The
repository is dependency-free (``docs/development.md``), so the subset of
GIF89a an animation needs is implemented here: a logical screen descriptor, a
``NETSCAPE2.0`` loop extension, one graphic control extension per frame, and
LZW-compressed images.  Nothing here reads game data; the caller passes
finished RGBA8888 bytes, exactly what :mod:`lomax_modern.png` writes.

Three deliberate properties
---------------------------
* **The palette is chosen by measured size, not by opinion.**  A GIF may carry
  one global colour table or one table per frame.  A global table costs 3 bytes
  per entry once; a per-frame table costs them again per frame but lets a flat
  frame use a 2- or 16-colour table and shorter LZW codes.  :func:`encode`
  builds both candidates and keeps the smaller byte string, so the answer to
  "which is smaller" is the encoder's measurement rather than a guess.
* **Quantisation only happens when it has to.**  When the frames together use
  at most 256 colours the global palette is their exact set, the mapping is
  lossless, and no median cut runs.  Flat engine art lands in that case; a
  photographic-looking frame falls back to median-cut boxes.
* **Alpha is dropped, on purpose.**  The presenter's surfaces are opaque
  (``image_to_rgba`` writes 255 everywhere), so GIF's one-bit transparency has
  nothing to express here.  Frames are encoded as opaque pixels instead of
  inventing a transparent index that the pipeline never produces.

The frame's *playback* rate and the capture rate are separate knobs: the
capture ticks at 60 Hz, ``fps`` sets the delay written into the file, and
``max_frames`` thins the sequence.  Thinning by ``k`` and playing at ``60 / k``
fps keeps the animation at the capture's real speed.
"""

from __future__ import annotations

import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

__all__ = [
    "DEFAULT_FPS",
    "GIFError",
    "SIGNATURE",
    "EncodedGIF",
    "encode",
    "write",
]

#: The 6-byte GIF89a signature (also the first field of the file).
SIGNATURE = b"GIF89a"

#: Block terminator / file trailer.
TRAILER = 0x3B

#: GIF colour tables are at most 256 entries: 8-bit indices.
MAX_COLOURS = 256

#: LZW codes are at most 12 bits wide; beyond that the encoder emits a clear.
MAX_CODE_BITS = 12

#: Default playback rate: the capture is 60 Hz, and 60 fps GIFs are heavy.
DEFAULT_FPS = 30

#: Bytes per pixel in the RGBA8888 buffers this module encodes.
BYTES_PER_PIXEL = 4


class GIFError(ValueError):
    """The frames cannot be encoded as a GIF with this module."""


@dataclass(frozen=True)
class EncodedGIF:
    """The encoded bytes plus what the encoder actually did with them.

    Returned instead of a bare ``bytes`` so the CLI can report the sampling
    factor and the palette it measured without re-deriving either (and so a
    test can assert on them without parsing the file).
    """

    data: bytes
    width: int
    height: int
    frames: int
    frames_seen: int
    step: int
    delay_cs: int
    palette: str

    @property
    def size(self) -> int:
        return len(self.data)


# ---------------------------------------------------------------------------
# Colour tables
# ---------------------------------------------------------------------------


def _table_size(count: int) -> int:
    """Smallest legal GIF colour-table size that holds ``count`` colours.

    The format allows 2, 4, 8, ... 256 entries, so a 12-colour palette is
    padded to 16 rather than rounded up to 256.
    """
    if count < 1 or count > MAX_COLOURS:
        raise GIFError(f"palette must hold 1..{MAX_COLOURS} colours, got {count}")
    size = 2
    while size < count:
        size <<= 1
    return size


@dataclass(frozen=True)
class _Palette:
    """A colour table, padded to its legal size when serialised."""

    colours: tuple[tuple[int, int, int], ...]

    @property
    def table_size(self) -> int:
        return _table_size(len(self.colours))

    @property
    def bits(self) -> int:
        """log2 of the table size: 1 for 2 colours, 8 for 256."""
        return self.table_size.bit_length() - 1

    @property
    def min_code_size(self) -> int:
        """LZW minimum code size: the spec floor is 2, even for 2 colours."""
        return max(2, self.bits)

    def to_bytes(self) -> bytes:
        rows = b"".join(bytes(colour) for colour in self.colours)
        padding = self.table_size - len(self.colours)
        return rows + b"\x00\x00\x00" * padding


def _word_to_rgb(word: int) -> tuple[int, int, int]:
    """Decode a native-endian packed RGBA8888 pixel into its RGB triple."""
    if sys.byteorder == "little":
        return (word & 0xFF, (word >> 8) & 0xFF, (word >> 16) & 0xFF)
    return ((word >> 24) & 0xFF, (word >> 16) & 0xFF, (word >> 8) & 0xFF)


def _rgba_words(pixels: bytes) -> memoryview:
    """View RGBA bytes as 32-bit words so counting happens in C, not Python."""
    view = memoryview(pixels)
    if view.format != "B" or not view.contiguous:
        view = memoryview(bytes(pixels))
    return view.cast("I")


def _rgb_counts(pixels: bytes) -> dict[tuple[int, int, int], int]:
    """Histogram of distinct RGB triples in one RGBA frame, with pixel counts."""
    counts: dict[tuple[int, int, int], int] = {}
    for word, count in Counter(_rgba_words(pixels)).items():
        rgb = _word_to_rgb(word)
        counts[rgb] = counts.get(rgb, 0) + count
    return counts


def _box_average(
    entries: Sequence[tuple[tuple[int, int, int], int]],
) -> tuple[int, int, int]:
    """Population-weighted mean colour of one median-cut box."""
    total = sum(count for _, count in entries)
    if total <= 0:  # pragma: no cover - a box always carries pixels
        return entries[0][0]
    sums = [0, 0, 0]
    for (red, green, blue), count in entries:
        sums[0] += red * count
        sums[1] += green * count
        sums[2] += blue * count
    return (
        (sums[0] + total // 2) // total,
        (sums[1] + total // 2) // total,
        (sums[2] + total // 2) // total,
    )


def _median_cut(
    counts: dict[tuple[int, int, int], int], limit: int
) -> tuple[tuple[int, int, int], ...]:
    """Reduce ``counts`` to at most ``limit`` representative colours.

    Classic median cut: repeatedly split the box with the widest channel range
    (weighted by population so a big flat area is not starved) at the
    population median, then use each box's weighted mean.  Sorting by
    ``(channel value, colour)`` keeps the result deterministic across runs.
    """
    entries = sorted(counts.items())
    boxes: list[list[tuple[tuple[int, int, int], int]]] = [entries]
    while len(boxes) < limit:
        choice = -1
        widest = 0
        for index, box in enumerate(boxes):
            if len(box) < 2:
                continue
            span = max(
                max(colour[channel] for colour, _ in box)
                - min(colour[channel] for colour, _ in box)
                for channel in range(3)
            )
            # Weighted span: split the box that covers the most pixels.
            score = span * sum(count for _, count in box)
            if score > widest:
                widest = score
                choice = index
        if choice < 0:
            break
        box = boxes.pop(choice)
        channel = max(
            range(3),
            key=lambda position: max(colour[position] for colour, _ in box)
            - min(colour[position] for colour, _ in box),
        )
        box.sort(key=lambda item: (item[0][channel], item[0]))
        total = sum(count for _, count in box)
        running = 0
        split = len(box) - 1
        for position, (_, count) in enumerate(box, start=1):
            running += count
            if running * 2 >= total:
                split = position
                break
        split = min(max(split, 1), len(box) - 1)
        boxes.append(box[:split])
        boxes.append(box[split:])
    return tuple(sorted({_box_average(box) for box in boxes}))


def _palette_for(counts: dict[tuple[int, int, int], int]) -> _Palette:
    """Exact palette when the colours fit, median cut when they do not."""
    if len(counts) <= MAX_COLOURS:
        return _Palette(tuple(sorted(counts)))
    return _Palette(_median_cut(counts, MAX_COLOURS))


class _Nearest:
    """Map a colour to its palette index, exactly when possible.

    The palette is small and the distinct-colour set of one frame is bounded,
    so a dict memo per palette is enough; the linear scan only runs once per
    distinct colour that is not already in the table.
    """

    def __init__(self, palette: _Palette) -> None:
        self.palette = palette
        self._memo: dict[tuple[int, int, int], int] = {
            colour: index for index, colour in enumerate(palette.colours)
        }

    def __call__(self, colour: tuple[int, int, int]) -> int:
        index = self._memo.get(colour)
        if index is not None:
            return index
        red, green, blue = colour
        best = 0
        best_distance = None
        for position, (p_red, p_green, p_blue) in enumerate(self.palette.colours):
            distance = (
                (red - p_red) ** 2 + (green - p_green) ** 2 + (blue - p_blue) ** 2
            )
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best = position
                if distance == 0:
                    break
        self._memo[colour] = best
        return best


def _index_frame(pixels: bytes, nearest: _Nearest) -> bytes:
    """Map every pixel of one RGBA frame to its palette index."""
    lookup = {
        word: nearest(_word_to_rgb(word))
        for word in Counter(_rgba_words(pixels))
    }
    return bytes(map(lookup.__getitem__, _rgba_words(pixels)))


# ---------------------------------------------------------------------------
# LZW
# ---------------------------------------------------------------------------


class _BitWriter:
    """Pack variable-width codes least-significant-bit first, as GIF requires."""

    __slots__ = ("_bytes", "_accumulator", "_bits")

    def __init__(self) -> None:
        self._bytes = bytearray()
        self._accumulator = 0
        self._bits = 0

    def write(self, code: int, width: int) -> None:
        self._accumulator |= code << self._bits
        self._bits += width
        while self._bits >= 8:
            self._bytes.append(self._accumulator & 0xFF)
            self._accumulator >>= 8
            self._bits -= 8

    def flush(self) -> bytes:
        if self._bits:
            self._bytes.append(self._accumulator & 0xFF)
            self._accumulator = 0
            self._bits = 0
        return bytes(self._bytes)


def _lzw(indices: bytes, min_code_size: int) -> bytes:
    """Compress palette indices with GIF's LZW variant.

    Codes start one bit wider than ``min_code_size``; the table is cleared and
    the width reset when it would exceed 12 bits, which is what a decoder
    expects to see.
    """
    clear = 1 << min_code_size
    end = clear + 1
    width = min_code_size + 1
    next_code = end + 1
    table: dict[int, int] = {}
    out = _BitWriter()
    out.write(clear, width)
    if indices:
        prefix = indices[0]
        for value in indices[1:]:
            key = (prefix << 8) | value
            found = table.get(key)
            if found is not None:
                prefix = found
                continue
            out.write(prefix, width)
            if next_code < 1 << MAX_CODE_BITS:
                table[key] = next_code
                next_code += 1
                if next_code > (1 << width) and width < MAX_CODE_BITS:
                    width += 1
            else:
                # Table full: tell the decoder to reset and start again.
                out.write(clear, width)
                table.clear()
                width = min_code_size + 1
                next_code = end + 1
            prefix = value
        out.write(prefix, width)
    out.write(end, width)
    return out.flush()


def _sub_blocks(data: bytes) -> bytes:
    """Frame ``data`` as GIF data sub-blocks (<=255 bytes each, 0-terminated)."""
    out = bytearray()
    for start in range(0, len(data), 255):
        chunk = data[start : start + 255]
        out.append(len(chunk))
        out += chunk
    out.append(0)
    return bytes(out)


# ---------------------------------------------------------------------------
# File assembly
# ---------------------------------------------------------------------------


def _loop_forever() -> bytes:
    """NETSCAPE2.0 application extension with loop count 0 (forever)."""
    return b"".join(
        (
            b"\x21\xff\x0b",
            b"NETSCAPE2.0",
            b"\x03\x01",
            struct.pack("<H", 0),
            b"\x00",
        )
    )


def _control(delay_cs: int) -> bytes:
    """Graphic control extension: delay in centiseconds, disposal "do not".

    Disposal 1 (leave the frame in place) is correct because every frame covers
    the whole logical screen; a partial-frame encoder would need disposal 2.
    """
    return b"".join(
        (b"\x21\xf9\x04", bytes([0x04]), struct.pack("<H", delay_cs), b"\x00\x00")
    )


def _frame_block(
    width: int,
    height: int,
    packed: int,
    table: bytes,
    min_code_size: int,
    indices: bytes,
) -> bytes:
    """One image descriptor + its colour table + LZW data.

    ``packed`` carries the local-colour-table flag and size bits; ``table`` is
    empty when the frame reuses the logical screen's global table.
    """
    descriptor = struct.pack("<BHHHHB", 0x2C, 0, 0, width, height, packed)
    lzw = _lzw(indices, min_code_size)
    return b"".join((descriptor, table, bytes([min_code_size]), _sub_blocks(lzw)))


def _assemble(
    width: int,
    height: int,
    delay_cs: int,
    global_palette: _Palette | None,
    frames: Sequence[tuple[_Palette | None, bytes]],
) -> bytes:
    """Write the whole file: header, descriptors, extensions, trailer.

    A frame whose palette is ``None`` reuses the global table instead of
    repeating it, which is the whole point of the global candidate.
    """
    packed = 0
    if global_palette is not None:
        # Global colour table present, 8-bit colour resolution, table size bits.
        packed = 0x80 | (7 << 4) | (global_palette.bits - 1)
    out = bytearray(SIGNATURE)
    out += struct.pack("<HHBBB", width, height, packed, 0, 0)
    if global_palette is not None:
        out += global_palette.to_bytes()
    out += _loop_forever()
    for palette, indices in frames:
        out += _control(delay_cs)
        if palette is None:
            if global_palette is None:  # pragma: no cover - caller guarantees one
                raise GIFError("internal: frame has no palette and there is no global one")
            out += _frame_block(
                width,
                height,
                0,
                b"",
                global_palette.min_code_size,
                indices,
            )
        else:
            out += _frame_block(
                width,
                height,
                0x80 | (palette.bits - 1),
                palette.to_bytes(),
                palette.min_code_size,
                indices,
            )
    out.append(TRAILER)
    return bytes(out)


def _sample(count: int, max_frames: int) -> tuple[list[int], int]:
    """Evenly spaced frame indices; returns ``(indices, step)``.

    ``step`` is ``ceil(count / max_frames)``, so a 300-tick capture with
    ``max_frames=120`` keeps ticks 0, 3, 6, ... -- the same motion at a third
    of the bytes, and real-time again when played at ``60 / step`` fps.
    """
    if max_frames <= 0 or count <= max_frames:
        return list(range(count)), 1
    step = -(-count // max_frames)
    return list(range(0, count, step)), step


def _check_frames(width: int, height: int, frames: Sequence[bytes]) -> list[bytes]:
    if not isinstance(width, int) or not isinstance(height, int):
        raise GIFError("width and height must be ints")
    if width <= 0 or height <= 0:
        raise GIFError(f"width and height must be positive, got {width}x{height}")
    if width > 0xFFFF or height > 0xFFFF:
        raise GIFError(
            f"GIF dimensions are 16-bit, got {width}x{height} (max 65535x65535)"
        )
    if not frames:
        raise GIFError("no frames to encode")
    expected = width * height * BYTES_PER_PIXEL
    checked: list[bytes] = []
    for index, pixels in enumerate(frames):
        if len(pixels) != expected:
            raise GIFError(
                f"frame {index} is {len(pixels)} bytes, expected {expected} "
                f"for {width}x{height} RGBA"
            )
        checked.append(bytes(pixels))
    return checked


def _delay_centiseconds(fps: float) -> int:
    """Delay per frame in centiseconds: ``100 / fps``, never below 1."""
    if fps <= 0:
        raise GIFError(f"fps must be positive, got {fps}")
    delay = int(round(100.0 / fps))
    return max(1, delay)


def encode(
    width: int,
    height: int,
    frames: Sequence[bytes],
    *,
    fps: float = DEFAULT_FPS,
    max_frames: int = 0,
) -> EncodedGIF:
    """Encode ``frames`` (row-major RGBA8888) as an animated GIF89a.

    ``frames`` must all be exactly ``width * height * 4`` bytes; a short or long
    buffer raises :class:`GIFError` rather than producing a shifted image.  All
    frames share the logical screen only if their buffers agree, so a mixed-size
    sequence is rejected by construction.

    ``max_frames > 0`` thins the sequence evenly (see :func:`_sample`).
    The animation loops forever and each frame's delay is ``100 / fps``
    centiseconds, with a 1 cs floor because GIF cannot express 0.
    """
    if not isinstance(max_frames, int) or max_frames < 0:
        raise GIFError(f"max_frames must be a non-negative int, got {max_frames!r}")
    checked = _check_frames(width, height, frames)
    delay_cs = _delay_centiseconds(fps)
    indices, step = _sample(len(checked), max_frames)
    selected = [checked[index] for index in indices]

    # Candidate 1: one global table for every frame.
    pooled: dict[tuple[int, int, int], int] = {}
    for pixels in selected:
        for colour, count in _rgb_counts(pixels).items():
            pooled[colour] = pooled.get(colour, 0) + count
    global_palette = _palette_for(pooled)
    nearest = _Nearest(global_palette)
    global_frames: list[tuple[_Palette | None, bytes]] = [
        (None, _index_frame(pixels, nearest)) for pixels in selected
    ]
    global_data = _assemble(width, height, delay_cs, global_palette, global_frames)

    # Candidate 2: a table per frame, sized to that frame's own colours.
    local_frames: list[tuple[_Palette, bytes]] = []
    local_sizes: list[int] = []
    for pixels in selected:
        palette = _palette_for(_rgb_counts(pixels))
        local_sizes.append(len(palette.colours))
        local_frames.append((palette, _index_frame(pixels, _Nearest(palette))))
    local_data = _assemble(width, height, delay_cs, None, local_frames)

    if len(local_data) < len(global_data):
        data = local_data
        palette = (
            f"per frame, {min(local_sizes)}-{max(local_sizes)} colours"
            if len(set(local_sizes)) > 1
            else f"per frame, {local_sizes[0]} colours"
        )
    else:
        data = global_data
        palette = f"global, {len(global_palette.colours)} colours"
    return EncodedGIF(
        data=data,
        width=width,
        height=height,
        frames=len(selected),
        frames_seen=len(checked),
        step=step,
        delay_cs=delay_cs,
        palette=palette,
    )


def write(
    path: str | Path,
    width: int,
    height: int,
    frames: Sequence[bytes],
    *,
    fps: float = DEFAULT_FPS,
    max_frames: int = 0,
) -> EncodedGIF:
    """Encode and write ``path``; returns the encoder's report.

    The caller owns the destination.  This module never decides to write into a
    game folder.
    """
    report = encode(width, height, frames, fps=fps, max_frames=max_frames)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(report.data)
    return report
