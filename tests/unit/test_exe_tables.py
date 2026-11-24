"""Tests for the section-table reader, on synthetic PE-like files only."""

from __future__ import annotations

import builtins
import dataclasses
import inspect

import pytest

from lomax_modern import exe_tables
from lomax_modern.exe_tables import ExeLayoutError, read_section_table
from tests.fixtures.pe import DEFAULT_NAMES, DEFAULT_ROWS, Row, build_exe


def _write(tmp_path, **kw):
    return build_exe(write_to=tmp_path / "LOMAX.EXE", **kw)


def _with_row(index, row):
    rows = list(DEFAULT_ROWS)
    rows[index] = row
    return rows


def _expect(tmp_path, label, **kw):
    with pytest.raises(ExeLayoutError) as info:
        read_section_table(_write(tmp_path, **kw))
    assert str(info.value).startswith(label + ": ")


def test_round_trip(tmp_path):
    table = read_section_table(_write(tmp_path))
    assert table.world_names == DEFAULT_NAMES
    assert len(table.entries) == 24
    for entry, row in zip(table.entries, DEFAULT_ROWS):
        assert entry.plane_mask == row.mask
        assert entry.loader_argument == row.loader_argument
        assert entry.world_index == row.world_index
        ranked = [b for b in range(32) if row.mask >> b & 1]
        expected = tuple(
            tuple(ranked[r] for r in range(len(ranked)) if sel >> r & 1)
            for sel in row.selectors
        )
        assert entry.sublevels == expected


def test_va_mapping_with_shifted_raw_offsets(tmp_path):
    table = read_section_table(_write(tmp_path, text_raw=0x900, name_raw=0x3000))
    assert table.world_names == DEFAULT_NAMES
    assert table.entries[5].loader_argument == DEFAULT_ROWS[5].loader_argument


def test_virtual_size_larger_than_raw_is_not_trusted(tmp_path):
    _expect(tmp_path, "table range", text_trim=100, text_virtual_size=0x10000)


def test_read_only_single_read(tmp_path, monkeypatch):
    path = _write(tmp_path)
    calls = []
    real_open = builtins.open

    class Spy:
        def __init__(self, handle):
            self._h = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            calls.append(("close",))
            self._h.close()

        def read(self, *args):
            calls.append(("read", args))
            return self._h.read(*args)

        def __getattr__(self, name):
            calls.append((name,))
            return getattr(self._h, name)

    def fake_open(*args, **kwargs):
        calls.append(("open", args[1:], kwargs))
        return Spy(real_open(*args, **kwargs))

    monkeypatch.setattr(builtins, "open", fake_open)
    table = read_section_table(path)
    monkeypatch.undo()

    assert calls[0] == ("open", ("rb",), {})
    assert [c for c in calls if c[0] == "open"] == [calls[0]]
    reads = [c for c in calls if c[0] == "read"]
    assert reads == [("read", ())]
    assert {c[0] for c in calls} <= {"open", "read", "close"}

    def walk(value):
        assert not isinstance(value, (bytes, bytearray))
        if dataclasses.is_dataclass(value):
            for f in dataclasses.fields(value):
                walk(getattr(value, f.name))
        elif isinstance(value, tuple):
            for v in value:
                walk(v)
        else:
            assert isinstance(value, (int, str))

    walk(table)


def test_no_hashing_or_logging_in_source():
    from lomax_modern.engine import sections

    for module in (exe_tables, sections):
        source = inspect.getsource(module)
        for word in ("hashlib", "sha256", "md5", "logging"):
            assert word not in source


def test_structure_constants():
    assert exe_tables.SECTION_TABLE_VA == 0x466450
    assert exe_tables.SECTION_ENTRY_STRIDE == 24
    assert exe_tables.SECTION_ENTRY_COUNT == 24
    assert exe_tables.WORLD_NAME_TABLE_VA == 0x466690
    assert exe_tables.WORLD_NAME_COUNT == 10


def test_mz_signature(tmp_path):
    _expect(tmp_path, "MZ signature", dos_signature=b"NZ")


def test_pe_signature(tmp_path):
    _expect(tmp_path, "PE signature", pe_signature=b"PX\0\0")


def test_two_byte_file(tmp_path):
    path = tmp_path / "LOMAX.EXE"
    path.write_bytes(b"MZ")
    with pytest.raises(ExeLayoutError) as info:
        read_section_table(path)
    assert str(info.value).startswith("PE signature: ")


def test_machine(tmp_path):
    _expect(tmp_path, "machine", machine=0x8664)


def test_optional_magic(tmp_path):
    _expect(tmp_path, "PE32 optional header", optional_magic=0x20B)


def test_entry_table_outside_every_section(tmp_path):
    _expect(tmp_path, "table range", section_table_va=0x00310000)


def test_name_pointer_table_outside_every_section(tmp_path):
    _expect(tmp_path, "table range", name_table_va=0x00380000)


def test_table_runs_past_raw_end(tmp_path):
    _expect(tmp_path, "table range", text_trim=100)


def test_world_index(tmp_path):
    _expect(tmp_path, "world index", rows=_with_row(3, Row(0b111, 1, 12, (3,))))


def test_plane_mask_zero(tmp_path):
    _expect(tmp_path, "plane mask", rows=_with_row(2, Row(0, 1, 0, (1,))))


@pytest.mark.parametrize("count", [0, 6])
def test_sublevel_count(tmp_path, count):
    row = Row(0b1111, 1, 0, (1, 1, 1, 1, 1), count=count)
    _expect(tmp_path, "sub-level count", rows=_with_row(5, row))


def test_selector_zero(tmp_path):
    _expect(tmp_path, "sub-level selector", rows=_with_row(0, Row(0b1111, 1, 0, (0,))))


def test_selector_out_of_range(tmp_path):
    mask = 0b10110
    row = Row(mask, 1, 0, (1, 1 << mask.bit_count()))
    _expect(tmp_path, "sub-level selector", rows=_with_row(0, row))


def test_unused_selectors_are_not_validated(tmp_path):
    # Short entries pad their unused selectors with 0, which would fail if checked.
    row = Row(0b1111, 1, 0, (5,))
    table = read_section_table(_write(tmp_path, rows=_with_row(0, row)))
    assert len(table.entries[0].sublevels) == 1


@pytest.mark.parametrize(
    "bad",
    ["ALPHA.BIN", "ABCDEFGHIJKLM.WLD", "AL\x01HA.WLD"],
    ids=["suffix", "too-long", "non-printable"],
)
def test_world_name(tmp_path, bad):
    names = list(DEFAULT_NAMES)
    names[4] = bad
    _expect(tmp_path, "world name", names=names)


def test_world_name_pointer_outside(tmp_path):
    pointers = [0x7FFF0000] * 10
    _expect(tmp_path, "world name pointer", name_pointers=pointers)


def test_garbage_and_truncated_files(tmp_path):
    good = build_exe()
    cases = [b"", b"\0" * 40, good[:0x90], good[:0x178], good[:0x190], good[:0x500]]
    for blob in cases:
        path = tmp_path / "LOMAX.EXE"
        path.write_bytes(blob)
        with pytest.raises(ExeLayoutError):
            read_section_table(path)
