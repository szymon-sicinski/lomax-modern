"""Decode `TTAB` / `CELL` / `MAP` and export sprite sheets as PNG.

Confidence, per claim (see ``docs/file-formats.md``):

**Verified against the retail install (V)**

* ``TTAB`` payloads are a whole number of 8-byte records; a record is four
  big-endian ``u16`` cell indices (75,122 records / 300,488 words in 9 files).
* ``CELL`` payloads are a whole number of 64-byte records (14,974 in 9 files).
* ``MAP`` is 3 bytes per 16x16 cell plus 0-3 zero pad bytes to a multiple of 4,
  and the cell count follows from the sibling ``HEAD`` dimensions.
* A ``TTAB`` word is a 13-bit index in the low bits with ``0x2000``/``0x4000``
  set on some words; ``0x8000`` is never set.  Words are **preserved verbatim**
  including indices past the world's ``CELL`` count (``BONUS.WLD`` uses index
  256 with 251 cells -- Q22), never clamped.

**Hypothesis (H), and therefore printed as such by the exporter**

* A ``CELL`` record is 8x8 palette indices, row-major, index 0 transparent.
  The container only says "64 bytes"; the full byte range is used, which rules
  out packed 4-bpp pixels, and 64 = 8x8 is the square reading.
* Which of the ten ``HEAD`` palette slots a cell uses.  The tile word has no
  free bit for a palette, so the slot must come from elsewhere (Q8).  Measured
  observation: slot 1 renders natural art for ``VILLAGE``/``HAUNTED``/
  ``TITLE`` where slot 0 renders a hue-shifted variant, and slot 1 is the only
  slot non-empty in 101 of 104 ``HEAD`` blocks.  Slot 1 is the default; it is
  an observation, not a proof of what the engine loads.
* The order of the four cells inside a ``TTAB`` record (G1, open).  The default
  tile sheet therefore draws each record as its four cells **in stored order**
  and labels the 2x2 assembly an explicit option.

**Unresolved, and reported as unresolved**

* How a ``MAP`` cell names a ``TTAB`` record (Q20) -- prints
  ``map cell -> tile record: unresolved``.
* What the ``TTAB`` flags ``0x2000``/``0x4000`` mean (Q21) -- counted, not
  interpreted.
* Sprite frames: ``ANIM``'s layout is unknown (Q24), so no sprite sheet is
  fabricated; ``ANIM`` is reported as unresolved.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from . import png, wld

#: Bytes in one ``CELL`` record: an 8x8 block of palette indices.
CELL_SIZE = 64

#: Pixels per side of a ``CELL`` block.
CELL_PIXELS = 8

#: ``u16`` cell-index words per ``TTAB`` record (a 16x16 tile, four 8x8 cells).
TILE_WORDS = 4

#: Bytes per ``TTAB`` record.
TILE_SIZE = TILE_WORDS * 2

#: Mask for the 13-bit cell index inside a ``TTAB`` word.
TILE_INDEX_MASK = 0x1FFF

#: Flag bits observed in ``TTAB`` words; their meaning is open (Q21).
TILE_FLAGS = (0x2000, 0x4000, 0x8000)

#: Palette index that is the transparent key.
TRANSPARENT_INDEX = 0

#: ``HEAD`` palette block: 10 slots of 256 little-endian 15-bit colours.
PALETTE_SLOT_COUNT = 10
PALETTE_ENTRY_COUNT = 256
PALETTE_BLOCK_OFFSET = 8
PALETTE_BLOCK_SIZE = PALETTE_SLOT_COUNT * PALETTE_ENTRY_COUNT * 2

#: Default slot: see the module docstring -- an observation, not a proof.
DEFAULT_PALETTE_SLOT = 1

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]


class ArtError(ValueError):
    """A chunk does not match the layout this module can decode."""


def rgb15_to_rgb8(word: int) -> RGB:
    """Expand a 15-bit little-endian colour (blue 0-4, green 5-9, red 10-14)."""
    red = (word >> 10) & 0x1F
    green = (word >> 5) & 0x1F
    blue = word & 0x1F
    # Bit replication keeps full white at 255 instead of 248.
    return ((red << 3) | (red >> 2), (green << 3) | (green >> 2), (blue << 3) | (blue >> 2))


@dataclass(frozen=True)
class Palette:
    """One ``HEAD`` palette slot, plus the transparency rule."""

    slot: int
    colours: tuple[RGB, ...]
    transparent_index: int = TRANSPARENT_INDEX

    def __len__(self) -> int:
        return len(self.colours)

    def rgb(self, index: int) -> RGB:
        if not 0 <= index < len(self.colours):
            raise ArtError(f"palette index {index} is outside 0-{len(self.colours) - 1}")
        return self.colours[index]

    def rgba(self, index: int) -> RGBA:
        """RGBA for a palette index; the transparent key gets alpha 0."""
        if index == self.transparent_index:
            return (0, 0, 0, 0)
        return (*self.rgb(index), 255)


def head_palette(head_chunk: wld.Chunk, slot: int = DEFAULT_PALETTE_SLOT) -> Palette:
    """Extract one 256-colour slot from a ``HEAD`` chunk.

    The palette block is documented ``[D]`` at offset 8 with 10 x 256
    little-endian 15-bit words; its arithmetic is confirmed by the constant
    0x1478 payload size (``docs/file-formats.md`` §2.3).
    """
    if head_chunk.tag != "HEAD":
        raise ArtError(f"head_palette() needs a HEAD chunk, got {head_chunk.tag!r}")
    payload = head_chunk.payload
    if len(payload) < PALETTE_BLOCK_OFFSET + PALETTE_BLOCK_SIZE:
        raise ArtError(
            f"HEAD payload is {len(payload)} bytes; the palette block needs "
            f"{PALETTE_BLOCK_OFFSET + PALETTE_BLOCK_SIZE}"
        )
    if not 0 <= slot < PALETTE_SLOT_COUNT:
        raise ArtError(f"palette slot must be 0-{PALETTE_SLOT_COUNT - 1}, got {slot}")
    start = PALETTE_BLOCK_OFFSET + slot * PALETTE_ENTRY_COUNT * 2
    words = struct.unpack(
        "<" + "H" * PALETTE_ENTRY_COUNT,
        payload[start : start + PALETTE_ENTRY_COUNT * 2],
    )
    return Palette(slot=slot, colours=tuple(rgb15_to_rgb8(word) for word in words))


def palette_slots_non_empty(head_chunk: wld.Chunk) -> tuple[int, ...]:
    """Slots of a ``HEAD`` that hold at least one non-zero colour."""
    if len(head_chunk.payload) < PALETTE_BLOCK_OFFSET + PALETTE_BLOCK_SIZE:
        raise ArtError("HEAD payload too short for the palette block")
    body = head_chunk.payload[
        PALETTE_BLOCK_OFFSET : PALETTE_BLOCK_OFFSET + PALETTE_BLOCK_SIZE
    ]
    return tuple(
        slot
        for slot in range(PALETTE_SLOT_COUNT)
        if any(body[slot * 512 : (slot + 1) * 512])
    )


@dataclass(frozen=True)
class Cell:
    """One 8x8 block of palette indices, exactly as stored."""

    index: int
    pixels: bytes

    def __post_init__(self) -> None:
        if len(self.pixels) != CELL_SIZE:
            raise ArtError(
                f"cell {self.index} holds {len(self.pixels)} bytes, expected {CELL_SIZE}"
            )

    def pixel(self, x: int, y: int) -> int:
        """Palette index at ``(x, y)`` -- row-major, 8 pixels per row."""
        if not (0 <= x < CELL_PIXELS and 0 <= y < CELL_PIXELS):
            raise ArtError(f"cell pixel ({x}, {y}) outside 0-7")
        return self.pixels[y * CELL_PIXELS + x]


def decode_cells(chunk: wld.Chunk) -> tuple[Cell, ...]:
    """Split a ``CELL`` chunk into 64-byte records (``[V]`` multiples of 64)."""
    if chunk.tag != "CELL":
        raise ArtError(f"decode_cells() needs a CELL chunk, got {chunk.tag!r}")
    if len(chunk.payload) % CELL_SIZE:
        raise ArtError(
            f"CELL payload is {len(chunk.payload)} bytes, not a multiple of {CELL_SIZE}"
        )
    return tuple(
        Cell(index=i, pixels=chunk.payload[i * CELL_SIZE : (i + 1) * CELL_SIZE])
        for i in range(len(chunk.payload) // CELL_SIZE)
    )


@dataclass(frozen=True)
class TileWord:
    """One ``u16`` of a ``TTAB`` record, kept verbatim.

    ``index`` is the 13-bit cell index; ``reserved`` holds the remaining bits so
    a writer can re-emit the word unchanged.
    """

    raw: int

    @property
    def index(self) -> int:
        return self.raw & TILE_INDEX_MASK

    @property
    def reserved(self) -> int:
        return self.raw & ~TILE_INDEX_MASK & 0xFFFF

    def has_flag(self, bit: int) -> bool:
        if bit not in TILE_FLAGS:
            raise ArtError(f"unknown TTAB flag {bit:#06x}; known: {TILE_FLAGS}")
        return bool(self.raw & bit)


@dataclass(frozen=True)
class TileRecord:
    """A 16x16 tile as four cell-index words, in stored order."""

    index: int
    words: tuple[TileWord, ...]

    def __post_init__(self) -> None:
        if len(self.words) != TILE_WORDS:
            raise ArtError(
                f"tile record holds {len(self.words)} words, expected {TILE_WORDS}"
            )

    @property
    def cell_indices(self) -> tuple[int, ...]:
        return tuple(word.index for word in self.words)

    def to_bytes(self) -> bytes:
        """Re-emit the record unchanged (flags and out-of-bank indices included)."""
        return b"".join(struct.pack(">H", word.raw) for word in self.words)


def decode_tiles(chunk: wld.Chunk) -> tuple[TileRecord, ...]:
    """Split a ``TTAB`` chunk into 8-byte records of four big-endian ``u16``."""
    if chunk.tag != "TTAB":
        raise ArtError(f"decode_tiles() needs a TTAB chunk, got {chunk.tag!r}")
    if len(chunk.payload) % TILE_SIZE:
        raise ArtError(
            f"TTAB payload is {len(chunk.payload)} bytes, not a multiple of {TILE_SIZE}"
        )
    words = struct.unpack(">" + "H" * (len(chunk.payload) // 2), chunk.payload)
    return tuple(
        TileRecord(
            index=record,
            words=tuple(TileWord(raw=value) for value in words[record * 4 : record * 4 + 4]),
        )
        for record in range(len(words) // TILE_WORDS)
    )


@dataclass(frozen=True)
class MapCell:
    """One 16x16 map position: a tile word plus a collision byte, verbatim."""

    tile_word: int
    collision: int


@dataclass(frozen=True)
class MapPlane:
    """A decoded ``MAP`` chunk plus the geometry of its ``HEAD``."""

    width_cells: int
    height_cells: int
    cells: tuple[MapCell, ...]
    pad: bytes

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    def at(self, x: int, y: int) -> MapCell:
        if not (0 <= x < self.width_cells and 0 <= y < self.height_cells):
            raise ArtError(f"map cell ({x}, {y}) outside {self.width_cells}x{self.height_cells}")
        return self.cells[y * self.width_cells + x]


def decode_map(map_chunk: wld.Chunk, head_chunk: wld.Chunk) -> MapPlane:
    """Decode a ``MAP`` payload, using the sibling ``HEAD`` for the geometry.

    ``3 * cells + pad`` must equal the payload size (0 <= pad <= 3, all zero);
    that cross-check is what makes the plane geometry ``[V]`` rather than a
    guess, so a mismatch raises instead of being padded away.
    """
    if map_chunk.tag != "MAP":
        raise ArtError(f"decode_map() needs a MAP chunk, got {map_chunk.tag!r}")
    if head_chunk.tag != "HEAD":
        raise ArtError(f"decode_map() needs a HEAD chunk, got {head_chunk.tag!r}")
    width_units, height_units = head_chunk.head_dimensions()
    width_cells = width_units * 8 // 16
    height_cells = height_units * 8 // 16
    cells = width_cells * height_cells
    body = cells * 3
    pad = len(map_chunk.payload) - body
    if not 0 <= pad <= 3 or pad != (-body % 4):
        raise ArtError(
            f"MAP payload is {len(map_chunk.payload)} bytes, expected {body} + "
            f"{(-body % 4)} pad for a {width_units}x{height_units} (8-px) plane"
        )
    payload = map_chunk.payload
    pad_bytes = payload[body:]
    if any(pad_bytes):
        raise ArtError(f"MAP pad bytes are not zero: {pad_bytes.hex()}")
    return MapPlane(
        width_cells=width_cells,
        height_cells=height_cells,
        cells=tuple(
            MapCell(
                tile_word=struct.unpack(">H", payload[i * 3 : i * 3 + 2])[0],
                collision=payload[i * 3 + 2],
            )
            for i in range(cells)
        ),
        pad=pad_bytes,
    )


@dataclass(frozen=True)
class PlaneSection:
    """One ``HEAD``/``TTAB``/``MAP`` triple of a world file."""

    head: wld.Chunk
    ttab: wld.Chunk
    map: wld.Chunk
    tiles: tuple[TileRecord, ...]
    plane: MapPlane


def planes(world: wld.World) -> tuple[PlaneSection, ...]:
    """Pair each ``HEAD`` with the ``TTAB``/``MAP`` that follow it.

    Retail order is ``HEAD, TTAB, MAP, GNMY`` repeated per plane, so a plane is
    the run between two ``HEAD`` chunks.  A run missing either chunk raises:
    silently decoding a partial plane would put wrong pixels on screen.
    """
    sections: list[PlaneSection] = []
    pending: dict[str, wld.Chunk] = {}
    for chunk in world.chunks:
        if chunk.tag == "HEAD":
            if pending:
                raise ArtError(
                    f"plane at offset {pending['HEAD'].header_offset} has no "
                    f"{'TTAB' if 'TTAB' not in pending else 'MAP'}"
                )
            pending = {"HEAD": chunk}
        elif chunk.tag in ("TTAB", "MAP") and pending:
            pending[chunk.tag] = chunk
        if "MAP" in pending and "HEAD" in pending and "TTAB" in pending:
            head, ttab, mapc = pending["HEAD"], pending["TTAB"], pending["MAP"]
            sections.append(
                PlaneSection(
                    head=head,
                    ttab=ttab,
                    map=mapc,
                    tiles=decode_tiles(ttab),
                    plane=decode_map(mapc, head),
                )
            )
            pending = {}
    if pending:
        raise ArtError(
            f"plane at offset {pending['HEAD'].header_offset} is incomplete"
        )
    return tuple(sections)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Image:
    """An RGBA8888 image; the only thing the exporters hand to :mod:`png`."""

    width: int
    height: int
    pixels: bytes

    def __post_init__(self) -> None:
        if len(self.pixels) != self.width * self.height * 4:
            raise ArtError(
                f"image buffer is {len(self.pixels)} bytes, expected "
                f"{self.width * self.height * 4} for {self.width}x{self.height}"
            )

    def write(self, path: str | Path, *, compression_level: int = 9) -> Path:
        return png.write(
            path, self.width, self.height, self.pixels, compression_level=compression_level
        )


class _Canvas:
    """A tiny RGBA canvas; pasting is explicit so every pixel is accounted for."""

    def __init__(self, width: int, height: int, background: RGBA = (0, 0, 0, 0)) -> None:
        self.width = width
        self.height = height
        self.buffer = bytearray(bytes(background) * (width * height))

    def set(self, x: int, y: int, colour: RGBA) -> None:
        offset = (y * self.width + x) * 4
        self.buffer[offset : offset + 4] = bytes(colour)

    def paste_indexed(
        self,
        rows: list[list[int]],
        palette: Palette,
        x0: int,
        y0: int,
        *,
        scale: int = 1,
    ) -> None:
        for y, row in enumerate(rows):
            for x, index in enumerate(row):
                colour = palette.rgba(index)
                for dy in range(scale):
                    for dx in range(scale):
                        self.set(x0 + x * scale + dx, y0 + y * scale + dy, colour)

    def image(self) -> Image:
        return Image(self.width, self.height, bytes(self.buffer))


def cell_rows(cell: Cell) -> list[list[int]]:
    """The cell as 8 rows of 8 palette indices (row-major hypothesis)."""
    return [
        list(cell.pixels[row * CELL_PIXELS : (row + 1) * CELL_PIXELS])
        for row in range(CELL_PIXELS)
    ]


def cell_sheet(
    cells: tuple[Cell, ...],
    palette: Palette,
    *,
    columns: int = 32,
    scale: int = 1,
    background: RGBA = (0, 0, 0, 0),
) -> Image:
    """All cells in file order, ``columns`` per row, index 0 transparent."""
    if not cells:
        raise ArtError("cell_sheet() needs at least one cell")
    if columns < 1:
        raise ArtError(f"columns must be >= 1, got {columns}")
    if scale < 1:
        raise ArtError(f"scale must be >= 1, got {scale}")
    rows = (len(cells) + columns - 1) // columns
    side = CELL_PIXELS * scale
    canvas = _Canvas(columns * side, rows * side, background)
    for n, cell in enumerate(cells):
        canvas.paste_indexed(
            cell_rows(cell),
            palette,
            (n % columns) * side,
            (n // columns) * side,
            scale=scale,
        )
    return canvas.image()


def tile_sheet(
    records: tuple[TileRecord, ...],
    cells: tuple[Cell, ...],
    palette: Palette,
    *,
    layout: str = "strip",
    columns: int = 16,
    scale: int = 1,
    background: RGBA = (0, 0, 0, 0),
) -> Image:
    """Draw ``TTAB`` records; ``strip`` keeps the four cells in stored order.

    ``layout="2x2"`` arranges them as the documented 16x16 tile, which uses an
    order the data does not prove (G1) and is therefore never the default.
    Cells whose index falls outside the world's ``CELL`` bank are left empty --
    drawing something else would hide Q22.
    """
    if not records:
        raise ArtError("tile_sheet() needs at least one record")
    if layout not in ("strip", "2x2"):
        raise ArtError(f"layout must be 'strip' or '2x2', got {layout!r}")
    if columns < 1:
        raise ArtError(f"columns must be >= 1, got {columns}")
    if scale < 1:
        raise ArtError(f"scale must be >= 1, got {scale}")
    cell_w = CELL_PIXELS * (TILE_WORDS if layout == "strip" else 2) * scale
    cell_h = CELL_PIXELS * (1 if layout == "strip" else 2) * scale
    rows = (len(records) + columns - 1) // columns
    canvas = _Canvas(columns * cell_w, rows * cell_h, background)
    for n, record in enumerate(records):
        origin_x = (n % columns) * cell_w
        origin_y = (n // columns) * cell_h
        for slot, index in enumerate(record.cell_indices):
            if index >= len(cells):
                continue
            if layout == "strip":
                dx, dy = slot * CELL_PIXELS * scale, 0
            else:
                dx = (slot % 2) * CELL_PIXELS * scale
                dy = (slot // 2) * CELL_PIXELS * scale
            canvas.paste_indexed(
                cell_rows(cells[index]), palette, origin_x + dx, origin_y + dy, scale=scale
            )
    return canvas.image()


def map_field_image(
    plane: MapPlane,
    *,
    channel: str = "collision",
    scale: int = 1,
    background: RGBA = (0, 0, 0, 0),
) -> Image:
    """A 1-pixel-per-cell view of one raw ``MAP`` byte.

    ``channel="collision"`` draws the third byte, ``"word-hi"``/``"word-lo"``
    the two bytes of the tile word.  Values are drawn verbatim as greyscale:
    the field's meaning (Q20/Q6) is not invented here, only made visible.
    """
    if channel not in ("collision", "word-hi", "word-lo"):
        raise ArtError(f"channel must be collision/word-hi/word-lo, got {channel!r}")
    if scale < 1:
        raise ArtError(f"scale must be >= 1, got {scale}")
    canvas = _Canvas(plane.width_cells * scale, plane.height_cells * scale, background)
    for y in range(plane.height_cells):
        for x in range(plane.width_cells):
            cell = plane.at(x, y)
            if channel == "collision":
                value = cell.collision
            elif channel == "word-hi":
                value = (cell.tile_word >> 8) & 0xFF
            else:
                value = cell.tile_word & 0xFF
            if value == 0:
                continue
            for dy in range(scale):
                for dx in range(scale):
                    canvas.set(
                        x * scale + dx, y * scale + dy, (value, value, value, 255)
                    )
    return canvas.image()


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ExportReport:
    """What was written, and which links stay unresolved."""

    world: Path
    palette_slot: int
    files: tuple[Path, ...]
    lines: tuple[str, ...]

    def format(self) -> str:
        return "\n".join(self.lines)


def refuse_into_game_folder(directory: str | Path) -> None:
    """Refuse a destination directory inside a tree that holds ``LOMAX.EXE``.

    Shared by every writer: ``check_output_dir`` uses it for art, and the GIF
    command uses it for its ``--out`` file, so a derived artifact can never land
    inside the user's install.
    """
    target = Path(directory).resolve()
    for candidate in (target, *target.parents):
        if (candidate / "LOMAX.EXE").is_file():
            raise ArtError(
                f"refusing to write inside the game folder ({candidate}); "
                "choose an output directory outside it"
            )


def check_output_dir(out_dir: str | Path, world_path: str | Path) -> None:
    """Refuse to write art into a game folder (the repository is read-only there).

    Two rules: never use the directory that holds the source ``.WLD`` itself as
    the output, and never write into a directory tree that holds ``LOMAX.EXE``.
    A scratch directory anywhere else is fine.
    """
    out = Path(out_dir).resolve()
    source = Path(world_path).resolve()
    if out == source.parent:
        raise ArtError(
            f"refusing to write into the game folder ({source.parent}); "
            "choose an output directory outside it"
        )
    refuse_into_game_folder(out)


def _count_out_of_bank(
    records: tuple[TileRecord, ...], cell_count: int
) -> dict[int, int]:
    counts: dict[int, int] = {}
    for record in records:
        for word in record.words:
            if word.index >= cell_count:
                counts[word.index] = counts.get(word.index, 0) + 1
    return counts


def export_world(
    world_path: str | Path,
    out_dir: str | Path,
    *,
    palette_slot: int = DEFAULT_PALETTE_SLOT,
    tile_layout: str = "strip",
    cell_columns: int = 32,
    tile_columns: int = 16,
    scale: int = 1,
    map_channel: str = "collision",
) -> ExportReport:
    """Write the sheets for one ``.WLD`` into ``out_dir`` and describe them.

    ``out_dir`` is chosen by the caller and is never the game folder; nothing
    is written next to the source file by default.
    """
    source = Path(world_path)
    check_output_dir(out_dir, source)
    world = wld.parse_file(source)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = source.stem.lower()

    sections = planes(world)
    cell_chunk = next((c for c in world.chunks if c.tag == "CELL"), None)
    if cell_chunk is None:
        raise ArtError(f"{source.name} has no CELL chunk")
    cells = decode_cells(cell_chunk)
    head = sections[0].head if sections else None
    if head is None:
        raise ArtError(f"{source.name} has no planes (HEAD/TTAB/MAP), so no palette")
    palette = head_palette(head, palette_slot)
    non_empty = palette_slots_non_empty(head)

    files: list[Path] = []
    lines: list[str] = [
        f"world: {source.name}",
        f"chunks: {len(world)} ({len(sections)} planes)",
        (
            f"palette: HEAD slot {palette_slot} of {PALETTE_SLOT_COUNT} "
            f"(hypothesis H -- the container names no slot, Q8; "
            f"non-empty slots in this HEAD: "
            f"{', '.join(str(s) for s in non_empty) or 'none'})"
        ),
        f"transparency: index {palette.transparent_index} has alpha 0",
    ]

    sheet = cell_sheet(cells, palette, columns=cell_columns, scale=scale)
    cells_path = sheet.write(out / f"{stem}_cells.png")
    files.append(cells_path)
    lines.append(
        f"CELL: {len(cells)} records of {CELL_SIZE} B = {CELL_PIXELS}x{CELL_PIXELS} "
        f"pixels -> {cells_path.name} ({sheet.width}x{sheet.height}) "
        f"[pixel order H: row-major]"
    )

    total_records = sum(len(section.tiles) for section in sections)
    flag_counts = {bit: 0 for bit in TILE_FLAGS}
    out_of_bank: dict[int, int] = {}
    referenced: set[int] = set()
    for section in sections:
        for record in section.tiles:
            for word in record.words:
                if word.index < len(cells):
                    referenced.add(word.index)
                for bit in TILE_FLAGS:
                    if word.has_flag(bit):
                        flag_counts[bit] += 1
        for index, count in _count_out_of_bank(section.tiles, len(cells)).items():
            out_of_bank[index] = out_of_bank.get(index, 0) + count

    lines.append(
        f"TTAB: {total_records} records of {TILE_SIZE} B "
        f"(four big-endian u16 cell indices, 13-bit index) -- "
        f"record-level count only, not map-referenced tiles"
    )
    lines.append(
        "TTAB flags preserved verbatim: "
        + ", ".join(f"{bit:#06x} on {flag_counts[bit]} words" for bit in TILE_FLAGS)
        + " (meaning unresolved, Q21)"
    )
    if out_of_bank:
        detail = ", ".join(
            f"index {index} referenced {count}x" for index, count in sorted(out_of_bank.items())
        )
        lines.append(
            f"TTAB out-of-bank indices preserved verbatim, not repaired: {detail} "
            f"(CELL bank holds {len(cells)} records, Q22)"
        )
    else:
        lines.append(
            f"TTAB out-of-bank indices: none (CELL bank holds {len(cells)} records, Q22)"
        )

    for plane_no, section in enumerate(sections):
        tile_image = tile_sheet(
            section.tiles,
            cells,
            palette,
            layout=tile_layout,
            columns=tile_columns,
            scale=scale,
        )
        tile_path = tile_image.write(out / f"{stem}_tiles_plane{plane_no:02d}.png")
        files.append(tile_path)
        field_image = map_field_image(section.plane, channel=map_channel, scale=scale)
        map_path = field_image.write(
            out / f"{stem}_map_plane{plane_no:02d}_{map_channel}.png"
        )
        files.append(map_path)
        lines.append(
            f"plane {plane_no:02d}: {section.plane.width_cells}x{section.plane.height_cells} "
            f"cells = {section.plane.cell_count}, {len(section.tiles)} TTAB records, "
            f"MAP pad {len(section.plane.pad)} B -> {tile_path.name}, {map_path.name}"
        )
    lines.append(
        f"tile sheet layout: {tile_layout}"
        + (
            " (stored order, four cells per record -- the order inside a record is "
            "unresolved, G1)"
            if tile_layout == "strip"
            else " (2x2 assembly is a hypothesis: the order inside a record is unresolved, G1)"
        )
    )

    distinct_words = {
        cell.tile_word for section in sections for cell in section.plane.cells
    }
    lines.append(
        f"MAP: {sum(s.plane.cell_count for s in sections)} cells "
        f"(3 B each: 16-bit tile word + collision byte), "
        f"{len(distinct_words)} distinct tile words; "
        f"map sheet shows the raw {map_channel} byte as greyscale, no art"
    )
    lines.append(
        f"distinct TTAB cell indices referenced: {len(referenced)} of {len(cells)} records"
    )
    lines.append("map cell -> tile record: unresolved (Q20)")
    lines.append(
        "sprite frames: unresolved (Q24 -- ANIM record layout unknown; no sheet written)"
    )
    lines.append(
        "note: no unique-tile count is reported, because MAP->TTAB is unresolved (Q20)"
    )

    return ExportReport(
        world=source, palette_slot=palette_slot, files=tuple(files), lines=tuple(lines)
    )
