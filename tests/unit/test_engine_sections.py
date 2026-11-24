"""Tests for the section resolver, on tables parsed from synthetic files."""

from __future__ import annotations

import inspect

import pytest

from lomax_modern.engine import sections
from lomax_modern.engine.sections import find_level, resolve_level
from lomax_modern.exe_tables import read_section_table
from tests.fixtures.pe import DEFAULT_NAMES, DEFAULT_ROWS, build_exe


def _table(tmp_path, **kw):
    return read_section_table(build_exe(write_to=tmp_path / "LOMAX.EXE", **kw))


def _active(row, k):
    ranked = [b for b in range(32) if row.mask >> b & 1]
    return [ranked[r] for r in range(len(ranked)) if row.selectors[k] >> r & 1]


def test_resolve(tmp_path):
    table = _table(tmp_path)
    seen_single = seen_multi = seen_nonzero = False
    for s, row in enumerate(DEFAULT_ROWS):
        for k in range(len(row.selectors)):
            got = resolve_level(table, s, k)
            active = _active(row, k)
            name = DEFAULT_NAMES[row.world_index]
            assert got.section == s and got.sublevel == k
            assert got.world_file == name
            assert got.world == name[: -len(".WLD")]
            assert got.playfield == min(active)
            assert got.backdrop == tuple(sorted(active)[1:])
            seen_single |= len(row.selectors) == 1
            seen_multi |= len(row.selectors) > 1
            seen_nonzero |= got.playfield != 0
    assert seen_single and seen_multi and seen_nonzero


def test_takes_table_holds_none(tmp_path):
    with pytest.raises(TypeError):
        resolve_level(None, 0, 0)
    with pytest.raises(TypeError):
        find_level(None, "ALPHA", 0)
    with pytest.raises(TypeError):
        resolve_level()
    source = inspect.getsource(sections)
    assert "0x466" not in source and "open(" not in source
    other = [f"{n}.WLD" for n in "QRSTUVWXYZ"]
    assert (
        resolve_level(_table(tmp_path, names=other), 0, 0).world_file
        == other[DEFAULT_ROWS[0].world_index]
    )


def test_find_level(tmp_path):
    table = _table(tmp_path)
    for s, row in enumerate(DEFAULT_ROWS):
        for k in range(len(row.selectors)):
            got = resolve_level(table, s, k)
            first = find_level(table, got.world, got.playfield)
            expected = next(
                (a, b)
                for a, e in enumerate(table.entries)
                for b, planes in enumerate(e.sublevels)
                if table.world_names[e.world_index] == got.world_file
                and min(planes) == got.playfield
            )
            assert first == expected
            assert find_level(table, got.world_file, got.playfield) == expected
            assert find_level(table, got.world.lower(), got.playfield) == expected


def test_find_level_misses(tmp_path):
    table = _table(tmp_path)
    with pytest.raises(LookupError):
        find_level(table, "NOSUCH", 0)
    with pytest.raises(LookupError):
        find_level(table, "ALPHA", 99)
    with pytest.raises(LookupError):
        find_level(table, "ALPHA", -1)


def test_out_of_range(tmp_path):
    table = _table(tmp_path)
    with pytest.raises(IndexError, match="0..23"):
        resolve_level(table, len(table.entries), 0)
    with pytest.raises(IndexError, match="0..0"):
        resolve_level(table, 0, len(table.entries[0].sublevels))
