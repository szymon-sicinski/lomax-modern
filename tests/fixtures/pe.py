"""Build synthetic PE-like executables for tests.

No game bytes: every value here is invented.  The image base, section layout,
world names and table rows are made up; only the *structure* (where the reader
looks, field offsets, strides) mirrors the documented layout.

The reader finds its two tables at fixed virtual addresses, so ``build_exe``
defaults to those addresses (imported from ``exe_tables``).  The sections that
hold them get invented raw offsets with *different* VA-to-file deltas, so a
reader that ignores the section headers lands in the wrong bytes.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from lomax_modern.exe_tables import SECTION_TABLE_VA, WORLD_NAME_TABLE_VA

IMAGE_BASE = 0x00300000
DEFAULT_NAMES: tuple[str, ...] = tuple(
    f"{n}.WLD"
    for n in (
        "ALPHA",
        "BRAVO",
        "CHARLIE",
        "DELTA",
        "ECHO",
        "FOXTROT",
        "GOLF",
        "HOTEL",
        "INDIA",
        "JULIET",
    )
)

_ENTRY_BYTES = 24 * 24
_PAD_BEFORE_ENTRIES = 0x40
_OPT_SIZE = 224


@dataclass(frozen=True)
class SectionSpec:
    name: str  # <= 8 ASCII characters
    rva: int  # RVA; the builder adds IMAGE_BASE
    raw_offset: int
    data: bytes
    virtual_size: int | None = None  # default: len(data)


@dataclass(frozen=True)
class Row:
    mask: int
    loader_argument: int
    world_index: int
    selectors: tuple[int, ...]  # 1..5, length == sub-level count
    count: int | None = None  # override the stored count (defects only)


def _default_rows() -> tuple[Row, ...]:
    rows = []
    for i in range(24):
        mask = ((i * 37 + 5) % 0x3FF) + 1
        possible = 1 << mask.bit_count()
        n = 1 + i % 5
        sels = tuple((i * 7 + k * 3) % (possible - 1) + 1 for k in range(n))
        rows.append(Row(mask, 100 + 3 * i, i % 10, sels))
    return tuple(rows)


DEFAULT_ROWS: tuple[Row, ...] = _default_rows()


def build_pe(
    sections: Sequence[SectionSpec],
    *,
    image_base: int = IMAGE_BASE,
    e_lfanew: int = 0x80,
    dos_signature: bytes = b"MZ",
    pe_signature: bytes = b"PE\0\0",
    machine: int = 0x14C,
    optional_magic: int = 0x10B,
) -> bytes:
    """Serialise a PE-like file: DOS stub, COFF, optional header, sections."""
    first = e_lfanew + 24 + _OPT_SIZE
    end = first + 40 * len(sections)
    for s in sections:
        end = max(end, s.raw_offset + len(s.data))
    out = bytearray(end)
    out[0:2] = dos_signature
    struct.pack_into("<I", out, 0x3C, e_lfanew)
    out[e_lfanew : e_lfanew + 4] = pe_signature
    struct.pack_into(
        "<HHIIIHH", out, e_lfanew + 4, machine, len(sections), 0, 0, 0, _OPT_SIZE, 0x102
    )
    opt = e_lfanew + 24
    struct.pack_into("<H", out, opt, optional_magic)
    struct.pack_into("<I", out, opt + 28, image_base)
    for i, s in enumerate(sections):
        vsize = len(s.data) if s.virtual_size is None else s.virtual_size
        h = first + 40 * i
        out[h : h + 8] = s.name.encode("ascii").ljust(8, b"\0")
        struct.pack_into("<IIII", out, h + 8, vsize, s.rva, len(s.data), s.raw_offset)
        out[s.raw_offset : s.raw_offset + len(s.data)] = s.data
    return bytes(out)


def _row_bytes(row: Row) -> bytes:
    count = len(row.selectors) if row.count is None else row.count
    sels = (tuple(row.selectors) + (0,) * 5)[:5]
    return struct.pack(
        "<II2xBxH5H", row.mask, row.loader_argument, row.world_index, count, *sels
    )


def build_exe(
    *,
    rows: Sequence[Row] | None = None,
    names: Sequence[str] | None = None,
    name_pointers: Sequence[int] | None = None,
    section_table_va: int = SECTION_TABLE_VA,
    name_table_va: int = WORLD_NAME_TABLE_VA,
    sections: Sequence[SectionSpec] = (),
    text_raw: int = 0x400,
    name_raw: int = 0x1000,
    text_trim: int = 0,
    text_virtual_size: int | None = None,
    write_to: Path | None = None,
    **header_overrides,
) -> bytes | Path:
    """Build a synthetic executable holding the two tables.

    The entry table goes in a ``.text``-like section, the name-pointer block
    and the names in a second one; ``text_trim`` cuts bytes off the end of the
    first section's raw data (and ``text_virtual_size`` can claim more).
    """
    rows = DEFAULT_ROWS if rows is None else rows
    names = DEFAULT_NAMES if names is None else names
    if len(rows) != 24 or len(names) != 10:
        raise ValueError("need 24 rows and 10 names")

    table = b"".join(_row_bytes(r) for r in rows)
    text = (b"\x90" * _PAD_BEFORE_ENTRIES + table)[
        : _PAD_BEFORE_ENTRIES + len(table) - text_trim
    ]

    strings = b""
    pointers = []
    for n in names:
        pointers.append(name_table_va + 40 + len(strings))
        strings += n.encode("latin-1") + b"\0"
    if name_pointers is not None:
        pointers = list(name_pointers)
    data = struct.pack("<10I", *pointers) + strings

    specs = [
        SectionSpec(
            ".text",
            section_table_va - _PAD_BEFORE_ENTRIES - IMAGE_BASE,
            text_raw,
            text,
            text_virtual_size,
        ),
        SectionSpec(".data", name_table_va - IMAGE_BASE, name_raw, data),
        *sections,
    ]
    blob = build_pe(specs, **header_overrides)
    if write_to is None:
        return blob
    write_to.write_bytes(blob)
    return write_to
