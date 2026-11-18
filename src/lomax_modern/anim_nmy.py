"""Validated framings for the ``ANIM`` and ``NMY`` chunk payloads.

Both framings were recovered by static analysis of the retail ``LOMAX.EXE``
readers and then **validated against the retail install**:

* ``ANIM`` — reader at VA ``0x414A82`` (file offset ``0x13E82``): 566/566 chunks
  parse cleanly under the framing in :func:`decode_anim`.
* ``NMY`` — reader at VA ``0x415199`` (file offset ``0x14599``): 9/9 chunks parse
  cleanly under the framing in :func:`decode_nmy` (the sequence ends with a
  ``u16`` zero terminator; retail files carry two further zero bytes of pad).

The recovery and evidence are recorded in ``docs/file-formats.md`` §2.5/§2.6 and
``docs/research/05-open-questions.md`` Q23/Q24.

Payload fields are **little-endian** (the readers use plain ``mov`` on the words;
only the chunk header's size — and the ``HEAD``/``WRLD`` fields — are byte-swapped
big-endian).  This module reports structure only: it never returns a type name,
an animation tag string, pixel data or any other game content, so it is safe to
keep in the repository.
"""

from __future__ import annotations

import struct
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
    """One frame of an ``ANIM`` chunk (structural fields only, no pixels)."""

    width: int
    height: int
    field_d: int
    field_e: int
    pixel_bytes: int


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
        frames.append(AnimFrame(width, height, field_d, field_e, pixel_bytes))
        pos += pixel_bytes
    if pos != len(payload):
        return None
    return AnimDecode(a, b, n, flags, packed, type_index, pad, tuple(frames))


# ---------------------------------------------------------------------------
# NMY
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NmyAnim:
    """One animation of an ``NMY`` type record (structural only)."""

    tag: int  # 4-byte identifier (reported as an integer, never decoded)
    size_field: int  # the u32 after the tag; measured to equal 20 + 8*frames
    frame_count: int


@dataclass(frozen=True)
class NmyRecord:
    """One ``NMY`` type record (structural only; the name is never kept)."""

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
            pos += 8 * count2
            anims.append(NmyAnim(tag, size_field, count2))
        records.append(NmyRecord(w_a, w_b, tuple(anims)))
        if pos + 2 > len(payload):
            return None
        count0 = struct.unpack_from("<H", payload, pos)[0]
        pos += 2
    return records, pos


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
