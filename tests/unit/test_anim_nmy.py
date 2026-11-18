"""Unit tests for the recovered ANIM/NMY framings (synthetic fixtures only)."""

from __future__ import annotations

import struct

from lomax_modern.anim_nmy import decode_anim, decode_gnmy, decode_nmy, probe_anim_nmy, probe_gnmy
from tests.fixtures.synth import (
    anim_payload,
    build_container,
    gnmy_entries_payload,
    head_payload,
    nmy_payload,
)


# ---------------------------------------------------------------------------
# ANIM
# ---------------------------------------------------------------------------


def test_anim_unpacked_round_trips() -> None:
    payload = anim_payload(frame_count=3, packed=False, width=8, height=8)
    dec = decode_anim(payload)
    assert dec is not None
    assert dec.frame_count == 3
    assert dec.packed is False
    assert dec.type_index == 0
    assert [f.pixel_bytes for f in dec.frames] == [64, 64, 64]


def test_anim_packed_halves_pixel_bytes() -> None:
    payload = anim_payload(frame_count=1, packed=True, width=8, height=8)
    dec = decode_anim(payload)
    assert dec is not None
    assert dec.packed is True
    assert dec.frames[0].pixel_bytes == 32  # 64 pixels >> 1


def test_anim_odd_packed_area_uses_floor_halving() -> None:
    # 3x3 = 9 pixels; packed byte count is round4(9 >> 1) = 4 (matches the reader)
    payload = anim_payload(frame_count=1, packed=True, width=3, height=3)
    dec = decode_anim(payload)
    assert dec is not None
    assert dec.frames[0].pixel_bytes == 4


def test_anim_truncated_header_rejected() -> None:
    assert decode_anim(b"\x00" * 11) is None


def test_anim_frame_overrun_rejected() -> None:
    # declare 2 frames but supply bytes for only 1
    payload = anim_payload(frame_count=2, width=4, height=4)
    assert decode_anim(payload[:-16]) is None


def test_anim_trailing_bytes_rejected() -> None:
    payload = anim_payload(frame_count=1, width=4, height=4)
    assert decode_anim(payload + b"\x00\x00\x00\x00") is None


# ---------------------------------------------------------------------------
# NMY
# ---------------------------------------------------------------------------


def test_nmy_single_record_round_trips() -> None:
    payload = nmy_payload([("Moneybag", 2)], trailer=2)
    records, consumed = decode_nmy(payload)
    assert records is not None
    assert len(records) == 1
    assert records[0].anim_count == 2
    assert [a.frame_count for a in records[0].anims] == [1, 1]
    assert all(a.size_field == 20 + 8 * 1 for a in records[0].anims)
    assert len(payload) - consumed == 2  # u16 terminator consumed, 2 pad bytes left


def test_nmy_multiple_records() -> None:
    payload = nmy_payload([("A", 0), ("B", 1), ("C", 3)], trailer=2)
    records, consumed = decode_nmy(payload)
    assert len(records) == 3
    assert [r.anim_count for r in records] == [0, 1, 3]
    assert len(payload) - consumed == 2


def test_nmy_empty_table() -> None:
    # a lone u16 zero terminator (plus pad) parses to zero records
    records, consumed = decode_nmy(b"\x00\x00" + b"\x00\x00")
    assert records == []
    assert consumed == 2


def test_nmy_truncated_rejected() -> None:
    payload = nmy_payload([("Type", 1)], trailer=2)
    assert decode_nmy(payload[:-4]) is None


def test_nmy_non_nul_terminated_name_rejected() -> None:
    # name field with no NUL inside the skipped bytes
    payload = struct.pack("<H", 8) + b"ABCDEFGH" + b"\x00\x00\x00\x00"
    assert decode_nmy(payload) is None


# ---------------------------------------------------------------------------
# Probe over a synthetic world container
# ---------------------------------------------------------------------------


def test_probe_counts_anim_and_nmy(tmp_path) -> None:
    world = build_container(
        [
            ("WRLD", b"PS-X" + b"\x00" * 4),
            ("NMY", nmy_payload([("T", 1)], trailer=2)),
            ("ANIM", anim_payload(frame_count=2)),
            ("ANIM", anim_payload(frame_count=1, packed=True)),
            ("END", b""),
        ],
        endian=">",
    )
    (tmp_path / "T.WLD").write_bytes(world)
    from lomax_modern.anim_nmy import probe_anim_nmy

    report = probe_anim_nmy([tmp_path / "T.WLD"])
    assert report.anim_chunks == 2
    assert report.anim_clean == 2
    assert report.nmy_chunks == 1
    assert report.nmy_clean == 1
    assert report.worlds[0]["nmy_records"] == 1


# ---------------------------------------------------------------------------
# GNMY
# ---------------------------------------------------------------------------


def test_gnmy_entry_round_trips() -> None:
    payload = gnmy_entries_payload([(0, 320, 240, 0x0000, (1, 2, 3), None)])
    entries, consumed = decode_gnmy(payload, {0: 3})
    assert entries is not None
    assert len(entries) == 1
    entry = entries[0]
    assert entry.type_index == 0
    assert entry.x == 320 and entry.y == 240
    assert entry.flags == 0x0000
    assert entry.params == (1, 2, 3)
    assert entry.extra is None
    assert entry.size == entry.structural_size == 16
    assert len(payload) - consumed == 2  # u16 terminator consumed, 2 pad bytes


def test_gnmy_size_field_equals_structural_length() -> None:
    payload = gnmy_entries_payload(
        [
            (0, 1, 2, 0x0000, (), None),
            (1, 3, 4, 0x8000, (7,), 99),
        ],
    )
    entries, _ = decode_gnmy(payload, {0: 0, 1: 1})
    assert entries is not None and len(entries) == 2
    for entry in entries:
        assert entry.size == entry.structural_size


def test_gnmy_extra_present_only_on_bit15() -> None:
    payload = gnmy_entries_payload(
        [
            (0, 1, 2, 0x8000, (5,), 42),
            (1, 3, 4, 0x0000, (6,), None),
        ],
    )
    entries, _ = decode_gnmy(payload, {0: 1, 1: 1})
    assert entries[0].extra == 42
    assert entries[1].extra is None


def test_gnmy_type_index_out_of_table_rejected() -> None:
    payload = gnmy_entries_payload([(0, 1, 2, 0, (), None)])
    assert decode_gnmy(payload, {}) is None


def test_gnmy_truncated_rejected() -> None:
    payload = gnmy_entries_payload([(0, 1, 2, 0, (1, 2), None)])  # 14-byte entry
    # keep only size + type + x + y (8 bytes): the flags word and params are cut
    assert decode_gnmy(payload[:8], {0: 2}) is None


def test_gnmy_missing_terminator_rejected() -> None:
    payload = gnmy_entries_payload([(0, 1, 2, 0, (), None)], trailer=0)
    assert decode_gnmy(payload[:-2], {0: 0}) is None


def test_gnmy_empty_list() -> None:
    entries, consumed = decode_gnmy(b"\x00\x00", {})
    assert entries == []
    assert consumed == 2


def test_probe_gnmy_correlates_coordinates(tmp_path) -> None:
    # Corrected MAP layout (docs §2.4): N big-endian u16 tile words, then N
    # collision bytes.  A 16x16 (8-px) plane is 8x8 = 64 cells.
    n = 64
    collision = bytearray(n)
    collision[1 * 8 + 1] = 1  # cell (1,1) solid; all else passable (0)
    map_bytes = b"\x00" * (2 * n) + bytes(collision)
    world = build_container(
        [
            ("WRLD", b"PS-X" + b"\x00" * 4),
            ("NMY", nmy_payload([("T", 0)], trailer=2)),  # W_A=0x10 -> K=1
            ("HEAD", head_payload(16, 16, endian=">")),
            ("TTAB", b"\x00" * 24),
            ("MAP", map_bytes),
            (
                "GNMY",
                gnmy_entries_payload(
                    [
                        (0, 0, 0, 0x0000, (0,), None),  # cell (0,0) passable
                        (0, 16, 16, 0x0000, (0,), None),  # cell (1,1) solid
                    ]
                ),
            ),
            ("END", b""),
        ],
        endian=">",
    )
    (tmp_path / "T.WLD").write_bytes(world)
    report = probe_gnmy([tmp_path / "T.WLD"])
    assert report.entries == 2
    assert report.on_map == 2
    assert report.walkable == 1  # only the cell-(0,0) entry is on passable
    assert report.total_cells == 64
    assert report.walkable_cells == 63
