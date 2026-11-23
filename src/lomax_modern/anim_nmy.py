"""Validated framings for the ``ANIM`` and ``NMY`` chunk payloads.

Both framings were recovered by static analysis of the retail ``LOMAX.EXE``
readers and then **validated against the retail install**:

* ``ANIM`` — reader at VA ``0x414A82`` (file offset ``0x13E82``): 566/566 chunks
  parse cleanly under the framing in :func:`decode_anim`.
* ``NMY`` — reader at VA ``0x415199`` (file offset ``0x14599``): 9/9 chunks parse
  cleanly under the framing in :func:`decode_nmy` (the sequence ends with a
  ``u16`` zero terminator; retail files carry two further zero bytes of pad).
* ``GNMY`` — reader at VA ``0x414D16`` (file offset ``0x14116``): 104/104
  chunks parse cleanly under the framing in :func:`decode_gnmy`, yielding
  **3,593 entries** whose ``u16`` size field equals the structural entry length
  on **3,593/3,593** entries, and whose ``x``/``y`` words are pixel coordinates
  (3,584/3,593 land inside their plane's cell bounds at one 16-px cell each).

The recovery and evidence are recorded in ``docs/file-formats.md`` §2.5/§2.6 and
``docs/research/05-open-questions.md`` Q23/Q24/Q32.

Payload fields are **little-endian** (the readers use plain ``mov`` on the words;
only the chunk header's size — and the ``HEAD``/``WRLD`` fields — are byte-swapped
big-endian).  This module reports structure plus each ``NMY`` record's **name**
(the game's object vocabulary, matched on its first four bytes — Q32).

Pixel data is decoded only on request, at run time, from the caller's own files:
:func:`decode_anim` carries each ``ANIM`` frame's raw pixel bytes, and
:func:`decode_anim_pixels` expands them into palette indices (4-bit packed or
raw 8-bit) — see the docstring there for the recovered nibble order.  The
repository commits only this decoding code, never game content.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# ANIM
# ---------------------------------------------------------------------------


def _round4(x: int) -> int:
    """Round ``x`` up to a multiple of 4 (the reader's ``(x+3) & ~3``)."""
    return (x + 3) & ~3


@dataclass(frozen=True)
class AnimFrame:
    """One frame of an ``ANIM`` chunk (structure plus the raw pixel bytes)."""

    width: int
    height: int
    field_d: int
    field_e: int
    pixel_bytes: int
    pixels: bytes = b""  # the frame's raw pixel data, still packed if 4-bit


@dataclass(frozen=True)
class AnimDecode:
    """The ``ANIM`` chunk header plus its frames (structural only)."""

    a: int
    b: int
    frame_count: int
    flags: int
    packed: bool
    type_index: int
    pad: int
    frames: tuple[AnimFrame, ...]


def decode_anim(payload: bytes) -> AnimDecode | None:
    """Decode an ``ANIM`` payload under the recovered framing.

    Layout (all little-endian, 12-byte header then ``n`` frames)::

        u16 a            # copied verbatim
        u16 b            # copied verbatim
        u16 n            # frame count
        u16 flags        # bit 15 = packed (4-bit) pixels
        u16 type_index   # animation slot key (reader stores at slot index+1)
        u16 pad          # skipped by the reader
        n x frame:
            i16 width
            i16 height
            u16 field_d
            u16 field_e
            pixel data -- round4(w*h) bytes, or round4((w*h)>>1) when packed

    Returns ``None`` if the bytes do not parse cleanly (truncated frame, or the
    frames do not consume the payload exactly).
    """
    if len(payload) < 12:
        return None
    a, b, n, flags, type_index, pad = struct.unpack_from("<6H", payload, 0)
    packed = bool(flags & 0x8000)
    pos = 12
    frames: list[AnimFrame] = []
    for _ in range(n):
        if pos + 8 > len(payload):
            return None
        width, height, field_d, field_e = struct.unpack_from("<hhHH", payload, pos)
        pos += 8
        area = width * height  # signed, as the reader computes it (imul)
        if packed:
            # cdq; sub eax,edx; sar eax,1  ==  (area + (area<0)) >> 1
            pixels = (area + (1 if area < 0 else 0)) >> 1
        else:
            pixels = area
        pixel_bytes = _round4(pixels)
        if pixel_bytes < 0 or pos + pixel_bytes > len(payload):
            return None
        frame_pixels = payload[pos : pos + pixel_bytes]
        frames.append(AnimFrame(width, height, field_d, field_e, pixel_bytes, frame_pixels))
        pos += pixel_bytes
    if pos != len(payload):
        return None
    return AnimDecode(a, b, n, flags, packed, type_index, pad, tuple(frames))


@dataclass(frozen=True)
class AnimPixels:
    """One decoded ``ANIM`` frame as row-major palette indices.

    ``indices`` holds exactly ``width * height`` palette indices; index 0 is
    the transparent key (the same rule the tile blit uses).  This is the
    indexed layer only — the caller applies its own ``HEAD`` palette.
    """

    width: int
    height: int
    indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.indices) != self.width * self.height:
            raise ValueError(
                f"frame has {len(self.indices)} indices for "
                f"{self.width}x{self.height} ({self.width * self.height})"
            )

    def at(self, x: int, y: int) -> int:
        """Palette index at ``(x, y)`` — row-major."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"pixel ({x}, {y}) outside {self.width}x{self.height}")
        return self.indices[y * self.width + x]


def decode_anim_pixels(anim: AnimDecode, frame_index: int) -> AnimPixels | None:
    """Decode one ``ANIM`` frame's pixel data into palette indices.

    Two storage paths, both recovered from the sprite decompressor at
    ``VA 0x415E30`` (the loop that unpacks a frame into an 8-bit index buffer):

    * **raw** (``packed`` False) — one palette index per byte, row-major
      (``mov al,[esi]`` / ``mov [ebx],al``, ``VA 0x415F65``).
    * **packed** (``packed`` True) — two 4-bit pixels per byte, **low nibble
      first** then high nibble: ``and al,0xf`` stores pixel 0, ``shr al,4``
      stores pixel 1 (``VA 0x415F18..0x415F2C``), ``width>>1`` bytes per row.
      An odd ``width`` drops the trailing pixel of each row (the reader halved
      ``width`` per row), so it is emitted as transparent index 0.

    ``frame_index`` is zero-based.  Returns ``None`` when the index is out of
    range or the frame is degenerate (a non-positive dimension).
    """
    if not 0 <= frame_index < len(anim.frames):
        return None
    frame = anim.frames[frame_index]
    width, height = frame.width, frame.height
    if width <= 0 or height <= 0:
        return None
    data = frame.pixels
    if not anim.packed:
        indices = tuple(data[: width * height])
    else:
        row_bytes = width >> 1
        out: list[int] = []
        for y in range(height):
            base = y * row_bytes
            for i in range(row_bytes):
                byte = data[base + i]
                out.append(byte & 0x0F)  # low nibble first
                out.append(byte >> 4)  # then high nibble
            if width & 1:
                out.append(0)  # odd width: the reader drops the trailing pixel
        indices = tuple(out)
    if len(indices) != width * height:
        return None
    return AnimPixels(width, height, indices)


# ---------------------------------------------------------------------------
# NMY
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NmyAnim:
    """One animation of an ``NMY`` type record (structure plus keyframes).

    ``frames`` is one entry per 8-byte per-frame record.  Each is the raw
    ``(sprite, b1, w2, w3, w4)`` tuple decoded ``u8, u8, u16, u16, u16``.  Only
    the first byte is mapped: ``sprite`` is a **1-based** ``ANIM`` sprite slot,
    selecting ``type_index`` ``sprite - 1`` (byte 0 draws nothing; see
    :func:`lomax_modern.anim_clip.chunk_index_for_sprite`).
    ``b1``/``w2``/``w3``/``w4`` are carried verbatim; their
    meaning (sub-frame index, draw offset, flip/duration flags) is read by the
    animation scheduler, not this module, and is left unresolved here.
    """

    tag: int  # 4-byte identifier (byte-swapped ASCII on disk)
    size_field: int  # the u32 after the tag; measured to equal 20 + 8*frames
    frame_count: int
    frames: tuple[tuple[int, int, int, int, int], ...] = ()


def anim_tag_name(tag: int) -> str:
    """The forward-ASCII name of an ``NMY`` animation tag.

    The tag is stored byte-swapped on disk: ``0x53544159`` ("STAY" as a
    big-endian dword) appears as the little-endian bytes ``YATS``.  Reading the
    dword big-endian recovers the name the game compares against its animation
    vocabulary (``STAY``, ``JUMP``, ``STA1``, ...).  Non-ASCII bytes are
    preserved as ``\\xNN`` escapes so an unexpected tag is visible, not mangled.
    """
    raw = struct.pack("<I", tag)[::-1]
    return "".join(
        chr(b) if 0x20 <= b < 0x7F else f"\\x{b:02x}" for b in raw
    )


@dataclass(frozen=True)
class NmyRecord:
    """One ``NMY`` type record (structure plus the record's name)."""

    name: str  # NUL-terminated name field, forward ASCII ("Start", "Moneybag")
    flags: int  # W_A
    anim_count: int  # W_B
    anims: tuple[NmyAnim, ...]


def decode_nmy(payload: bytes) -> tuple[list[NmyRecord], int] | None:
    """Decode an ``NMY`` payload under the recovered framing.

    Layout (all little-endian)::

        u16 count0            # name-field size; 0 terminates the table
        repeat:
            name (NUL-terminated, skipped by (count0>>1)*2 bytes)
            u16 W_A           # flags word
            u16 W_B           # animation count
            u16 gap1          # 2 bytes, not read (always 0 in retail data)
            W_B x animation:
                u32 tag       # 4-byte identifier (byte-swapped ASCII on disk)
                u32 size      # == 20 + 8*frame_count (not read by the loader)
                u16 count2    # frame count
                9 x u16 fields
                count2 x 8-byte frames {u8, u8, u16, u16, u16}
            u16 count0        # next name-field size (0 = end)

    ``name`` is returned as forward ASCII: the bytes on disk read ``Start``,
    ``Exit``, ``Moneybag``.  The loader loads them as a little-endian dword and
    compares *that* to the name table's ASCII dwords, which is what the docs'
    "byte-swapped to ASCII" describes — the string itself is never reversed.
    Matching uses the first four bytes, exactly as the 89-entry table does
    (``Start`` → ``Star``, ``Moneybag`` → ``Mone``; Q32).

    Returns ``(records, consumed)`` on success (``consumed`` is the byte offset
    just after the terminating ``u16`` zero), or ``None`` on a malformed stream.
    """
    if len(payload) < 2:
        return None
    pos = 0
    count0 = struct.unpack_from("<H", payload, pos)[0]
    pos += 2
    records: list[NmyRecord] = []
    while count0 != 0:
        name_start = pos
        advance = (count0 >> 1) * 2
        # the name must be NUL-terminated within the bytes the reader skips
        nul = payload.find(b"\x00", name_start)
        if nul < 0 or nul >= name_start + advance:
            return None
        name = payload[name_start:nul].decode("ascii", errors="replace")
        pos += advance
        if pos + 6 > len(payload):
            return None
        w_a = struct.unpack_from("<H", payload, pos)[0]
        pos += 2
        w_b = struct.unpack_from("<H", payload, pos)[0]
        pos += 2
        pos += 2  # gap1
        anims: list[NmyAnim] = []
        for _ in range(w_b):
            if pos + 28 > len(payload):
                return None
            tag = struct.unpack_from("<I", payload, pos)[0]
            pos += 4
            size_field = struct.unpack_from("<I", payload, pos)[0]
            pos += 4
            count2 = struct.unpack_from("<H", payload, pos)[0]
            pos += 2
            pos += 18  # 9 x u16 fields
            if pos + 8 * count2 > len(payload):
                return None
            frames = tuple(
                struct.unpack_from("<BBHHH", payload, pos + 8 * i)
                for i in range(count2)
            )
            pos += 8 * count2
            anims.append(NmyAnim(tag, size_field, count2, frames))
        records.append(NmyRecord(name, w_a, w_b, tuple(anims)))
        if pos + 2 > len(payload):
            return None
        count0 = struct.unpack_from("<H", payload, pos)[0]
        pos += 2
    return records, pos


#: ``NMY`` name prefixes whose ``GNMY`` placement role Q32 evidenced **[V]**.
#: The loader matches a record's name on its first four bytes against the
#: 89-entry name table, so ``Start``/``Moneybag`` match as ``Star``/``Mone``.
PLACEMENT_ROLES: dict[str, str] = {
    "Star": "start",
    "Exit": "exit",
    "Mone": "moneybag",
}


def placement_role(name: str | None) -> str:
    """The evidenced role of a ``GNMY`` placement from its ``NMY`` name.

    Returns ``"start"``, ``"exit"`` or ``"moneybag"`` for the three roles Q32
    resolved, and ``"other"`` for everything else — a missing/unknown name, a
    name whose handler is unmapped, or a documented sibling this overlay does
    not distinguish.  Matching is on the four-byte table prefix
    (:data:`PLACEMENT_ROLES`), never on the whole string.
    """
    if not name:
        return "other"
    return PLACEMENT_ROLES.get(name[:4], "other")


# ---------------------------------------------------------------------------
# GNMY
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GnmyEntry:
    """One ``GNMY`` placement entry (structural fields only, no content).

    Field grades are in ``docs/file-formats.md`` §2.5.  Each field below is
    **[V]** as *structure* (the reader's ``mov``/``and``/``shr`` sequence is
    reproduced by ``decode_gnmy``), with the *meaning* of the semantic fields
    graded separately:

    * ``size`` **[V]** — the entry's total byte length (the reader only tests it
      for ``0`` as the list terminator; the data always stores the true length).
    * ``type_index`` **[V]** — index into the world's ``NMY`` type table (the
      reader ORs ``0x100`` for ``MAIN.WLD`` before the lookup).
    * ``x``/``y`` **[V]** — pixel coordinates, stored to object ``+0xC``/``+0xE``.
    * ``flags`` **[V structure, H meaning]** — stored to ``+0x10``; bits 8–9 are
      extracted to ``+0x12`` (a 2-bit subfield) and bit 15 gates the extra word.
    * ``params`` **[V structure, H meaning]** — ``K`` per-animation ``u16``
      values, ``K = (NMY record's W_A >> 4) & 0xF``.
    * ``extra`` **[V structure, H meaning]** — present iff ``flags & 0x8000``,
      stored to object ``+0x4``.
    * ``name`` **[V]** — the ``NMY`` record's name, resolved by
      :func:`lomax_modern.engine.level.load_level` from ``type_index`` (Q32).
      :func:`decode_gnmy` leaves it ``None`` because it never reads the
      ``NMY`` table itself.
    """

    size: int  # total entry length in bytes, as stored (0 terminates the list)
    type_index: int  # zero-based index into the world's ``NMY`` type table
    x: int  # pixel X (a MAP cell is 16 px)
    y: int  # pixel Y
    flags: int  # bit 15 = extra u16 follows; bits 8-9 = a 2-bit subfield
    params: tuple[int, ...]  # K per-animation u16 values, K = (W_A >> 4) & 0xF
    extra: int | None  # present iff flags & 0x8000
    name: str | None = None  # NMY record name (resolved by load_level, Q32)

    @property
    def structural_size(self) -> int:
        """The byte length the reader advances by: 10 + 2*K + (2 if extra)."""
        return 10 + 2 * len(self.params) + (2 if self.extra is not None else 0)


def decode_gnmy(
    payload: bytes, k_of: Mapping[int, int]
) -> tuple[list[GnmyEntry], int] | None:
    """Decode a ``GNMY`` payload under the recovered entry layout.

    Layout (all little-endian)::

        u16 size     # total entry bytes == 10 + 2*K + (2 if flags & 0x8000); 0 ends
        u16 type     # index into the NMY type table (the loader ORs 0x100 for MAIN)
        u16 x        # pixel X
        u16 y        # pixel Y
        u16 flags    # bit 15 = extra u16 follows; bits 8-9 = a 2-bit subfield
        K x u16      # per-animation params, K = (NMY record's W_A >> 4) & 0xF
        [u16 extra]  # present iff flags & 0x8000

    ``k_of`` maps a type index to K (the reader derives it from the type's
    ``NMY`` record: ``K = (W_A >> 4) & 0xF``, the high nibble of the flags
    word, read from the record's ``+0x18`` slot).  Returns ``(entries,
    consumed)`` where ``consumed`` is the offset just after the ``u16`` zero
    terminator, or ``None`` on a malformed stream.

    The ``size`` field is read only to test for the zero terminator — the
    reader advances *structurally* (``esi`` is bumped by fixed ``add $0x2``
    steps), so ``decode_gnmy`` does the same and never trusts ``size`` to
    advance.  A caller that wants to assert ``size == structural_size`` does
    that as a measurement, not as a parse gate: on the retail install that
    equality holds on **3,593/3,593** entries, which is what proves ``K`` (and
    the base-10-byte header and the bit-15 extra rule) correct — the wrong
    ``K`` desynchronises and the walk fails with a params overrun.
    """
    entries: list[GnmyEntry] = []
    pos = 0
    n = len(payload)
    while pos + 2 <= n:
        size = struct.unpack_from("<H", payload, pos)[0]
        if size == 0:
            pos += 2
            return entries, pos
        if pos + 10 > n:
            return None
        type_index = struct.unpack_from("<H", payload, pos + 2)[0]
        k = k_of.get(type_index)
        if k is None:
            return None
        x, y, flags = struct.unpack_from("<HHH", payload, pos + 4)
        pend = pos + 10 + 2 * k
        if pend > n:
            return None
        params = struct.unpack_from("<" + "H" * k, payload, pos + 10) if k else ()
        extra = None
        if flags & 0x8000:
            if pend + 2 > n:
                return None
            extra = struct.unpack_from("<H", payload, pend)[0]
            pend += 2
        entries.append(GnmyEntry(size, type_index, x, y, flags, tuple(params), extra))
        pos = pend
    return None  # payload exhausted without a u16 terminator


# ---------------------------------------------------------------------------
# Probe over an install
# ---------------------------------------------------------------------------


@dataclass
class AnimNmyReport:
    """Per-world and whole-install clean-parse counts (no content)."""

    worlds: list[dict] = field(default_factory=list)
    anim_chunks: int = 0
    anim_clean: int = 0
    nmy_chunks: int = 0
    nmy_clean: int = 0


def probe_anim_nmy(world_files: list[Path]) -> AnimNmyReport:
    """Walk world files and validate every ``ANIM``/``NMY`` chunk.

    ``world_files`` is the list of ``*.WLD`` paths (see
    :func:`lomax_modern.doctor.find_world_files`).  Purely structural: the
    report carries counts and sizes only.
    """
    from .wld import parse_file  # local import keeps the module dependency-free

    report = AnimNmyReport()
    for path in world_files:
        world = parse_file(path)
        anim_chunks = anim_clean = 0
        nmy_records = None
        nmy_ok = False
        for chunk in world.chunks:
            if chunk.tag == "ANIM":
                anim_chunks += 1
                if decode_anim(chunk.payload) is not None:
                    anim_clean += 1
            elif chunk.tag == "NMY":
                result = decode_nmy(chunk.payload)
                if result is not None:
                    records, consumed = result
                    # reader stops at the u16 zero terminator; 2 pad bytes remain
                    if len(chunk.payload) - consumed == 2:
                        nmy_records = len(records)
                        nmy_ok = True
        report.worlds.append(
            {
                "name": path.name,
                "anim_chunks": anim_chunks,
                "anim_clean": anim_clean,
                "nmy_records": nmy_records,
                "nmy_clean": nmy_ok,
            }
        )
        report.anim_chunks += anim_chunks
        report.anim_clean += anim_clean
        report.nmy_chunks += 1
        report.nmy_clean += 1 if nmy_ok else 0
    return report


def format_anim_nmy_report(report: AnimNmyReport) -> str:
    """Human-readable digest of :func:`probe_anim_nmy` (counts only)."""
    lines = [
        f"ANIM: {report.anim_clean}/{report.anim_chunks} chunks parse cleanly",
        f"NMY:  {report.nmy_clean}/{report.nmy_chunks} chunks parse cleanly",
        "",
        f"{'world':<12}{'ANIM':>8}{'clean':>8}{'NMY recs':>10}{'clean':>8}",
    ]
    for w in report.worlds:
        lines.append(
            f"{w['name']:<12}{w['anim_chunks']:>8}{w['anim_clean']:>8}"
            f"{str(w['nmy_records'] or '-'):>10}"
            f"{str(int(w['nmy_clean'])):>8}"
        )
    return "\n".join(lines)


def _plane_geometry(head, map_chunk) -> tuple[int, int, bytes]:
    """Plane size in cells plus the collision bytes (corrected MAP layout).

    ``MAP`` is ``N`` big-endian ``u16`` tile words then ``N`` collision bytes,
    padded to 4 (``docs/file-formats.md`` §2.4, recovered by the map→tile
    pass — the reader at VA ``0x415430`` byte-swaps exactly ``2·N`` bytes and
    stores the collision pointer at ``payload + 2·N``); ``N = width_cells *
    height_cells`` and the ``HEAD`` dimensions are big-endian ``u32`` in
    8-pixel units (§2.3).  Read directly here rather than through
    ``art.decode_map`` to keep this module free of the art layer.
    """
    width_units, height_units = struct.unpack(">II", head.payload[0:8])
    width_cells = width_units * 8 // 16
    height_cells = height_units * 8 // 16
    n = width_cells * height_cells
    payload = map_chunk.payload
    collision = payload[2 * n : 2 * n + n]
    return width_cells, height_cells, collision


@dataclass
class GnmyReport:
    """Per-world and whole-install ``GNMY`` placement stats (no content)."""

    worlds: list[dict] = field(default_factory=list)
    entries: int = 0
    size_mismatches: int = 0
    x_min: int | None = None
    x_max: int | None = None
    y_min: int | None = None
    y_max: int | None = None
    with_extra: int = 0  # entries whose flags carry bit 15 (extra u16 present)
    on_map: int = 0  # (x // 16, y // 16) inside the plane's cell bounds
    walkable: int = 0  # of the on-map placements, collision byte == 0
    total_cells: int = 0  # every plane's cell count, summed
    walkable_cells: int = 0  # of those cells, collision byte == 0
    type_entries: dict[int, int] = field(default_factory=dict)  # type -> total entries
    type_worlds: dict[int, int] = field(default_factory=dict)  # type -> distinct worlds


def probe_gnmy(world_files: list[Path]) -> GnmyReport:
    """Walk world files and validate every ``GNMY`` entry.

    ``world_files`` is the list of ``*.WLD`` paths (see
    :func:`lomax_modern.doctor.find_world_files`).  Structural only: the report
    carries counts, ranges and a coordinate-vs-map correlation, never a name, a
    payload or a pixel.
    """
    from .wld import parse_file  # local import keeps the module dependency-free

    report = GnmyReport()
    for path in world_files:
        world = parse_file(path)
        nmy_chunk = next((c for c in world.chunks if c.tag == "NMY"), None)
        if nmy_chunk is None:
            continue
        result = decode_nmy(nmy_chunk.payload)
        if result is None:
            continue
        records, _ = result
        k_of = {i: (r.flags >> 4) & 0xF for i, r in enumerate(records)}
        world_entries = 0
        world_types: set[int] = set()
        head = None
        map_chunk = None
        for chunk in world.chunks:
            if chunk.tag == "HEAD":
                head = chunk
                map_chunk = None
            elif chunk.tag == "MAP":
                map_chunk = chunk
            elif chunk.tag == "GNMY":
                if head is None or map_chunk is None:
                    continue
                decoded = decode_gnmy(chunk.payload, k_of)
                if decoded is None:
                    continue
                entries, _consumed = decoded
                width_cells, height_cells, collision = _plane_geometry(head, map_chunk)
                report.total_cells += len(collision)
                report.walkable_cells += sum(1 for b in collision if b == 0)
                for entry in entries:
                    world_entries += 1
                    world_types.add(entry.type_index)
                    report.entries += 1
                    report.type_entries[entry.type_index] = (
                        report.type_entries.get(entry.type_index, 0) + 1
                    )
                    if entry.size != entry.structural_size:
                        report.size_mismatches += 1
                    report.x_min = (
                        entry.x if report.x_min is None else min(report.x_min, entry.x)
                    )
                    report.x_max = (
                        entry.x if report.x_max is None else max(report.x_max, entry.x)
                    )
                    report.y_min = (
                        entry.y if report.y_min is None else min(report.y_min, entry.y)
                    )
                    report.y_max = (
                        entry.y if report.y_max is None else max(report.y_max, entry.y)
                    )
                    if entry.extra is not None:
                        report.with_extra += 1
                    cell_x, cell_y = entry.x // 16, entry.y // 16
                    if 0 <= cell_x < width_cells and 0 <= cell_y < height_cells:
                        report.on_map += 1
                        if collision[cell_y * width_cells + cell_x] == 0:
                            report.walkable += 1
        for t in world_types:
            report.type_worlds[t] = report.type_worlds.get(t, 0) + 1
        report.worlds.append({"name": path.name, "entries": world_entries})
    return report


def format_gnmy_report(report: GnmyReport) -> str:
    """Human-readable digest of :func:`probe_gnmy` (counts and ranges only)."""
    base = report.entries
    walkable_frac = (
        f"{report.walkable_cells / report.total_cells * 100:.1f}%"
        if report.total_cells
        else "-"
    )
    n_worlds = len(report.worlds)
    distinct = len(report.type_entries)
    once_per_world = [
        t
        for t, total in report.type_entries.items()
        if total == n_worlds and report.type_worlds.get(t, 0) == n_worlds
    ]
    rarest = sorted(report.type_worlds.items(), key=lambda kv: (kv[1], kv[0]))[:8]
    rarest_desc = ", ".join(
        f"{t}({report.type_entries[t]} in {w} world{'s' if w != 1 else ''})"
        for t, w in rarest
    )
    lines = [
        f"GNMY: {report.entries} entries; size field == structural length on "
        f"{base - report.size_mismatches}/{base}",
        f"x range {report.x_min}..{report.x_max} px, "
        f"y range {report.y_min}..{report.y_max} px (a MAP cell is 16 px)",
        f"flags bit 15 (extra u16 follows) set on {report.with_extra}/{base} entries",
        f"coordinate correlation: {report.on_map}/{base} placements inside their "
        f"plane's cell bounds; {report.walkable}/{base} on collision-byte 0 "
        f"(baseline walkable {walkable_frac})",
        f"spawn/exit: {distinct} distinct types; {len(once_per_world)} appear "
        f"exactly once per world (a player start or level exit would have to), "
        f"so spawn/exit is not a unique type index; rarest types: {rarest_desc}",
        "",
        f"{'world':<12}{'entries':>10}",
    ]
    for w in report.worlds:
        lines.append(f"{w['name']:<12}{w['entries']:>10}")
    return "\n".join(lines)
