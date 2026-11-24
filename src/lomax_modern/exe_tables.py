"""Read the section table out of the user's own ``LOMAX.EXE`` at runtime.

Specified by ``docs/roadmap/47-first-level-plan.md`` §1.2 and §1.5 (decision
D3).  This module is a minimal PE32 reader plus the parser for two tables: the
24-entry section table and the ten-pointer world-file name table.  Both are
parsed from the executable each time they are needed.  **Nothing from the
executable is stored in the repository**: no row, selector, string or hash.
The only literals here are structure: virtual addresses, field offsets and
bounds.

The file is opened read-only, read once, and never written, cached or logged.
A file that fails any structural check raises :class:`ExeLayoutError`; the
checks compare with small integers and string shapes, never with a stored copy
of the executable.  This is not a build identity.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass

__all__ = [
    "COFF_MACHINE_I386",
    "DOS_E_LFANEW",
    "ENTRY_LOADER_ARG_OFFSET",
    "ENTRY_MASK_OFFSET",
    "ENTRY_SELECTORS_OFFSET",
    "ENTRY_SUBLEVEL_COUNT_OFFSET",
    "ENTRY_WORLD_INDEX_OFFSET",
    "MAX_SUBLEVELS",
    "MAX_WORLD_INDEX",
    "MAX_WORLD_NAME",
    "PE32_OPTIONAL_MAGIC",
    "SECTION_ENTRY_COUNT",
    "SECTION_ENTRY_STRIDE",
    "SECTION_TABLE_VA",
    "WORLD_NAME_COUNT",
    "WORLD_NAME_TABLE_VA",
    "WORLD_SUFFIX",
    "ExeLayoutError",
    "SectionEntry",
    "SectionTable",
    "read_section_table",
]

SECTION_TABLE_VA = 0x466450  # entry table, 24 entries
SECTION_ENTRY_STRIDE = 24
SECTION_ENTRY_COUNT = 24
WORLD_NAME_TABLE_VA = 0x466690  # ten 4-byte VA pointers
WORLD_NAME_COUNT = 10
MAX_WORLD_INDEX = 9
MAX_WORLD_NAME = 16  # characters, excluding the NUL
MAX_SUBLEVELS = 5
WORLD_SUFFIX = ".WLD"
# entry field offsets
ENTRY_MASK_OFFSET = 0x00  # u32
ENTRY_LOADER_ARG_OFFSET = 0x04  # u32
ENTRY_WORLD_INDEX_OFFSET = 0x0A  # u8
ENTRY_SUBLEVEL_COUNT_OFFSET = 0x0C  # u16
ENTRY_SELECTORS_OFFSET = 0x0E  # u16 x MAX_SUBLEVELS
# PE header constants
DOS_E_LFANEW = 0x3C  # u32
COFF_MACHINE_I386 = 0x14C
PE32_OPTIONAL_MAGIC = 0x10B

_SECTION_HEADER_SIZE = 40
_NAME_TABLE_BYTES = 4 * WORLD_NAME_COUNT
_ENTRY_TABLE_BYTES = SECTION_ENTRY_STRIDE * SECTION_ENTRY_COUNT


class ExeLayoutError(ValueError):
    """The executable does not have the expected layout.

    The message starts with the name of the failed check, then ``": "`` and a
    detail made of integers, indices and check names only.
    """


@dataclass(frozen=True)
class SectionEntry:
    plane_mask: int
    loader_argument: int
    world_index: int
    # Per sub-level: the active plane numbers, ascending.
    sublevels: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class SectionTable:
    world_names: tuple[str, ...]
    entries: tuple[SectionEntry, ...]


@dataclass(frozen=True)
class _Region:
    va: int  # image base + RVA
    raw_size: int
    raw_pointer: int


def _unpack(fmt: str, data: bytes, offset: int, label: str, what: str):
    size = struct.calcsize(fmt)
    if offset < 0 or offset + size > len(data):
        raise ExeLayoutError(f"{label}: {what} lies past the end of the file")
    return struct.unpack_from(fmt, data, offset)


def _map_range(regions: list[_Region], data: bytes, va: int, size: int):
    """Return ``(file_offset, section_raw_end)`` or ``None``.

    The range must lie inside one section's raw bytes (and the file).  The raw
    size is the bound, never the virtual size.
    """
    for r in regions:
        rel = va - r.va
        if rel >= 0 and rel + size <= r.raw_size:
            end = r.raw_pointer + r.raw_size
            if end > len(data):
                return None
            return r.raw_pointer + rel, end
    return None


def read_section_table(exe_path: str | os.PathLike[str]) -> SectionTable:
    """Parse the section table and world-name table of ``exe_path``."""
    with open(os.fspath(exe_path), "rb") as handle:
        data = handle.read()

    # --- DOS / PE / COFF headers -------------------------------------
    if len(data) < 2 or data[0:2] != b"MZ":
        raise ExeLayoutError("MZ signature: the file does not start with MZ")
    (e_lfanew,) = _unpack("<I", data, DOS_E_LFANEW, "PE signature", "e_lfanew")
    if e_lfanew < 0x40:
        raise ExeLayoutError(f"PE signature: e_lfanew {e_lfanew} is below 64")
    if e_lfanew + 4 > len(data) or data[e_lfanew : e_lfanew + 4] != b"PE\0\0":
        raise ExeLayoutError(f"PE signature: no PE signature at offset {e_lfanew}")
    pe = e_lfanew
    (machine,) = _unpack("<H", data, pe + 4, "PE header", "COFF header")
    (n_sections,) = _unpack("<H", data, pe + 6, "PE header", "COFF header")
    (opt_size,) = _unpack("<H", data, pe + 20, "PE header", "COFF header")
    if machine != COFF_MACHINE_I386:
        raise ExeLayoutError(f"machine: {machine:#x} is not {COFF_MACHINE_I386:#x}")
    if n_sections == 0:
        raise ExeLayoutError("PE header: number of sections is 0")
    opt = pe + 24
    if opt_size < 32 or opt + opt_size > len(data):
        raise ExeLayoutError("PE header: the optional header is cut off or too small")
    (magic,) = _unpack("<H", data, opt, "PE header", "optional header")
    if magic != PE32_OPTIONAL_MAGIC:
        raise ExeLayoutError(
            f"PE32 optional header: magic {magic:#x} is not {PE32_OPTIONAL_MAGIC:#x}"
        )
    (image_base,) = _unpack("<I", data, opt + 28, "PE header", "optional header")

    regions: list[_Region] = []
    first = opt + opt_size
    for i in range(n_sections):
        base = first + i * _SECTION_HEADER_SIZE
        _vsize, rva, raw_size, raw_ptr = _unpack(
            "<IIII", data, base + 8, "PE header", f"section header {i}"
        )
        regions.append(_Region(image_base + rva, raw_size, raw_ptr))

    # --- the two tables ----------------------------------------------
    entry_at = _map_range(regions, data, SECTION_TABLE_VA, _ENTRY_TABLE_BYTES)
    if entry_at is None:
        raise ExeLayoutError(
            f"table range: the {SECTION_ENTRY_COUNT}-entry table at {SECTION_TABLE_VA:#010x}"
            " is outside every section's raw bytes"
        )
    ptr_at = _map_range(regions, data, WORLD_NAME_TABLE_VA, _NAME_TABLE_BYTES)
    if ptr_at is None:
        raise ExeLayoutError(
            f"table range: the name-pointer table at {WORLD_NAME_TABLE_VA:#010x}"
            " is outside every section's raw bytes"
        )

    names: list[str] = []
    for i in range(WORLD_NAME_COUNT):
        (pointer,) = struct.unpack_from("<I", data, ptr_at[0] + 4 * i)
        where = _map_range(regions, data, pointer, 1)
        if where is None:
            raise ExeLayoutError(
                f"world name pointer: pointer {i} ({pointer:#010x}) is outside every section"
            )
        start, end = where
        stop = data.find(b"\0", start, end)
        if stop < 0:
            raise ExeLayoutError(
                f"world name: name {i} has no terminating NUL in its section"
            )
        raw = data[start:stop]
        if len(raw) > MAX_WORLD_NAME:
            raise ExeLayoutError(
                f"world name: name {i} is {len(raw)} characters (max {MAX_WORLD_NAME})"
            )
        if any(b < 0x20 or b > 0x7E for b in raw):
            raise ExeLayoutError(f"world name: name {i} has a non-printable byte")
        name = raw.decode("ascii")
        if not name.endswith(WORLD_SUFFIX):
            raise ExeLayoutError(
                f"world name: name {i} does not end with {WORLD_SUFFIX}"
            )
        names.append(name)

    entries: list[SectionEntry] = []
    for i in range(SECTION_ENTRY_COUNT):
        off = entry_at[0] + i * SECTION_ENTRY_STRIDE
        (mask,) = struct.unpack_from("<I", data, off + ENTRY_MASK_OFFSET)
        (loader,) = struct.unpack_from("<I", data, off + ENTRY_LOADER_ARG_OFFSET)
        world_index = data[off + ENTRY_WORLD_INDEX_OFFSET]
        (count,) = struct.unpack_from("<H", data, off + ENTRY_SUBLEVEL_COUNT_OFFSET)
        selectors = struct.unpack_from(
            f"<{MAX_SUBLEVELS}H", data, off + ENTRY_SELECTORS_OFFSET
        )
        if mask == 0:
            raise ExeLayoutError(f"plane mask: 0 in entry {i}")
        if world_index > MAX_WORLD_INDEX:
            raise ExeLayoutError(
                f"world index: {world_index} in entry {i} (must be < {WORLD_NAME_COUNT})"
            )
        if not 1 <= count <= MAX_SUBLEVELS:
            raise ExeLayoutError(
                f"sub-level count: {count} in entry {i} (must be 1..{MAX_SUBLEVELS})"
            )
        ranked = [b for b in range(32) if mask >> b & 1]
        possible = 1 << len(ranked)
        sublevels = []
        for k in range(count):
            sel = selectors[k]
            if sel == 0 or sel >= possible:
                raise ExeLayoutError(
                    f"sub-level selector: {sel} in entry {i} sub-level {k}"
                    f" ({possible - 1} possible)"
                )
            sublevels.append(
                tuple(ranked[r] for r in range(len(ranked)) if sel >> r & 1)
            )
        entries.append(SectionEntry(mask, loader, world_index, tuple(sublevels)))

    return SectionTable(tuple(names), tuple(entries))
