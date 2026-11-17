"""Parse and re-emit Lomax ``.WLD`` world files byte-for-byte.

The chunk container layout is verified against the retail PC install and
documented in ``docs/file-formats.md``:

* ``2.2 Chunk header [V]`` -- a 4-byte tag field (space-padded for 3-letter
  tags, e.g. ``"NMY "``) followed by a **big-endian** ``u32`` payload size
  (payload only; the 8-byte header is not counted).
* ``2.3 HEAD [V]`` -- two big-endian ``u32``: plane width/height in 8-pixel
  units.
* ``2.4 MAP/CELL [V]`` -- ``MAP`` is 3 bytes per 16x16 cell padded with 0-3
  zero bytes to a multiple of 4; ``CELL`` is whole 64-byte 8x8 cells.

This module reads a file into a :class:`World` of :class:`Chunk` records and
re-emits it identically.  Payloads are carried as opaque bytes; the only
interpretation exposed is the ``[V]`` subset above.  Every other tag
(``WRLD``, ``NMY``, ``PARA``, ``TTAB``, ``GNMY``, ``ANIM``, ``MACR``,
``PAGE``, ``END``, ...) is round-tripped verbatim.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

#: Bytes in a chunk header: tag field + big-endian ``u32`` payload size.
HEADER_SIZE = 8


class WLDError(Exception):
    """Base class for ``.WLD`` read/write failures."""


class WLDParseError(WLDError):
    """A ``.WLD`` byte stream does not match the verified chunk layout."""

    def __init__(self, offset: int, message: str) -> None:
        self.offset = offset
        super().__init__(f"offset {offset}: {message}")


def encode_tag(tag: str) -> bytes:
    """Space-pad a tag to the 4-byte header field width (docs §2.2)."""
    if not 1 <= len(tag) <= 4:
        raise WLDError(f"tag must be 1-4 ASCII characters, got {tag!r}")
    try:
        raw = tag.encode("ascii")
    except UnicodeEncodeError as exc:
        raise WLDError(f"tag must be ASCII, got {tag!r}") from exc
    return raw.ljust(4, b" ")


@dataclass(frozen=True)
class Chunk:
    """One chunk of a world file.

    ``tag_field`` and ``payload`` are the exact bytes read from disk, so
    re-emitting them reproduces the file bit for bit.  ``tag`` is the decoded,
    space-stripped name for display and matching.
    """

    tag: str
    tag_field: bytes
    size: int
    payload: bytes
    header_offset: int

    @property
    def payload_offset(self) -> int:
        """Offset of the first payload byte in the file."""
        return self.header_offset + HEADER_SIZE

    @property
    def end_offset(self) -> int:
        """Offset one past the end of this chunk."""
        return self.header_offset + HEADER_SIZE + len(self.payload)

    def head_dimensions(self) -> tuple[int, int]:
        """Plane width and height in 8-pixel units (docs §2.3 ``[V]``)."""
        if self.tag != "HEAD":
            raise WLDError(
                f"head_dimensions() needs a HEAD chunk, got {self.tag!r}"
            )
        if len(self.payload) < 8:
            raise WLDError(
                f"HEAD payload is {len(self.payload)} bytes; need 8 for the "
                "two big-endian u32 dimensions"
            )
        width, height = struct.unpack(">II", self.payload[:8])
        return width, height

    def cell_count(self) -> int:
        """Number of whole 64-byte 8x8 cells in a CELL chunk (docs §2.4 ``[V]``)."""
        if self.tag != "CELL":
            raise WLDError(f"cell_count() needs a CELL chunk, got {self.tag!r}")
        if len(self.payload) % 64:
            raise WLDError(
                f"CELL payload is {len(self.payload)} bytes, not a multiple of 64"
            )
        return len(self.payload) // 64


@dataclass
class World:
    """An ordered list of chunks; serialises back to the source bytes."""

    chunks: list[Chunk] = field(default_factory=list)

    @property
    def tags(self) -> list[str]:
        return [c.tag for c in self.chunks]

    def __len__(self) -> int:
        return len(self.chunks)

    def __iter__(self):
        return iter(self.chunks)

    def __getitem__(self, index):
        return self.chunks[index]

    def to_bytes(self) -> bytes:
        """Re-serialise the world exactly as parsed."""
        out = bytearray()
        for chunk in self.chunks:
            if len(chunk.tag_field) != 4:
                raise WLDError(
                    f"chunk {chunk.tag!r} has a {len(chunk.tag_field)}-byte tag "
                    "field; expected 4 bytes"
                )
            out += chunk.tag_field
            out += struct.pack(">I", len(chunk.payload))
            out += chunk.payload
        return bytes(out)


def parse(data: bytes, path: str = "<memory>") -> World:
    """Parse ``data`` as a ``.WLD`` chunk chain into a :class:`World`.

    Raises :class:`WLDParseError` if the chain does not consume the input
    exactly (truncated payload, trailing bytes, or a non-printable tag).
    """
    if not isinstance(data, bytes):
        raise TypeError(f"expected bytes, got {type(data).__name__}")
    if not data:
        raise WLDParseError(0, "empty input: no chunk header")

    chunks: list[Chunk] = []
    pos = 0
    n = len(data)
    while pos < n:
        if n - pos < HEADER_SIZE:
            raise WLDParseError(
                pos, f"trailing {n - pos} byte(s) after the last chunk"
            )
        tag_field = data[pos : pos + 4]
        if not all(0x20 <= b < 0x7F for b in tag_field):
            raise WLDParseError(pos, f"non-printable tag field: {tag_field!r}")
        (size,) = struct.unpack(">I", data[pos + 4 : pos + 8])
        payload_start = pos + HEADER_SIZE
        payload_end = payload_start + size
        if payload_end > n:
            raise WLDParseError(
                pos,
                f"chunk {tag_field!r} declares {size} payload bytes but only "
                f"{n - payload_start} remain",
            )
        chunks.append(
            Chunk(
                tag=tag_field.decode("ascii").rstrip(" "),
                tag_field=tag_field,
                size=size,
                payload=data[payload_start:payload_end],
                header_offset=pos,
            )
        )
        pos = payload_end
    return World(chunks=chunks)


def parse_file(path: str | Path) -> World:
    p = Path(path)
    return parse(p.read_bytes(), path=str(p))


def write_file(world: World, path: str | Path) -> None:
    """Write ``world`` to ``path``; the caller owns the destination.

    The module never chooses to write into a game folder itself: round-trip
    callers should write to a scratch/temp location and compare hashes.
    """
    Path(path).write_bytes(world.to_bytes())


def map_cells(width_units: int, height_units: int) -> int:
    """Cell count of a plane's MAP, from HEAD dimensions (docs §2.4 ``[V]``)."""
    cells_x = width_units * 8 // 16
    cells_y = height_units * 8 // 16
    return cells_x * cells_y


def map_padded_size(width_units: int, height_units: int) -> int:
    """MAP payload size in bytes: 3 per cell, padded to a multiple of 4."""
    raw = map_cells(width_units, height_units) * 3
    return raw + (-raw % 4)


def map_cell_count(map_chunk: Chunk, head_chunk: Chunk) -> int:
    """Cell count a MAP chunk must hold for the plane in ``head_chunk``.

    Cross-checks the two ``[V]`` claims (HEAD dimensions §2.3, MAP layout
    §2.4): 3 bytes per 16x16 cell plus 0-3 zero pad bytes.  Raises
    :class:`WLDError` when the payload length disagrees with the dimensions.
    """
    width, height = head_chunk.head_dimensions()
    expected = map_padded_size(width, height)
    if len(map_chunk.payload) != expected:
        raise WLDError(
            f"MAP payload is {len(map_chunk.payload)} bytes, expected {expected} "
            f"for a {width}x{height} (8-px) plane"
        )
    return map_cells(width, height)
