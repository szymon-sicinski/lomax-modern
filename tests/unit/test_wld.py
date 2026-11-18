"""Tests for the .WLD parser/writer (synthetic data only).

Round-trip is the core guarantee: parse -> to_bytes must reproduce the input
bit for bit.  Fixtures are built from scratch; no game bytes.
"""

from __future__ import annotations

import struct

import pytest

from lomax_modern import wld
from lomax_modern.wld import Chunk, WLDError, WLDParseError, World, parse
from tests.fixtures.synth import build_container, head_payload, map_payload, synthetic_world


def test_round_trip_synthetic_world() -> None:
    data = synthetic_world(endian=">")
    assert parse(data).to_bytes() == data


def test_round_trip_multiple_planes() -> None:
    data = synthetic_world(endian=">", planes=((40, 30), (80, 60), (120, 45)))
    world = parse(data)
    assert world.to_bytes() == data
    assert world.tags.count("HEAD") == 3


def test_round_trip_big_endian_container() -> None:
    # The verified layout is big-endian regardless of the synthetic endianness,
    # so build one explicitly in the verified convention and round-trip it.
    chunks = [("WRLD", b"PS-X\x00\x00\x00\x00"), ("END", b"")]
    data = build_container(chunks, endian=">")
    assert parse(data).to_bytes() == data


def test_chunk_fields_and_offsets() -> None:
    data = synthetic_world(endian=">")
    world = parse(data)
    first, last = world[0], world[-1]

    assert first.tag == "WRLD" and first.tag_field == b"WRLD"
    assert first.header_offset == 0
    assert first.payload_offset == 8
    assert first.size == 8
    assert first.end_offset == 16

    assert last.tag == "END"
    assert last.size == 0
    assert last.end_offset == len(data)


def test_space_padded_tags_round_trip() -> None:
    data = build_container(
        [("NMY", b"\x00" * 4), ("END", b"")], endian=">"
    )
    world = parse(data)
    # 3-letter tags are space-padded to the 4-byte field and stripped on decode.
    assert world[0].tag_field == b"NMY "
    assert world[0].tag == "NMY"
    assert world[1].tag_field == b"END "
    assert world.to_bytes() == data


def test_unverified_chunks_carried_opaque() -> None:
    payloads = {
        "TTAB": bytes(range(24)),
        "ANIM": b"\xde\xad\xbe\xef" * 4,
        "NMY": b"\x00" * 16,
        "MACR": b"MACR" + b"\x00" * 4,
        "PAGE": b"PAGE" + b"\x00" * 4,
    }
    chunks = [(tag, payload) for tag, payload in payloads.items()] + [("END", b"")]
    data = build_container(chunks, endian=">")
    world = parse(data)
    assert world.to_bytes() == data
    for chunk in world:
        if chunk.tag in payloads:
            assert chunk.payload == payloads[chunk.tag]


def test_head_dimensions_big_endian() -> None:
    data = build_container([("HEAD", head_payload(40, 30, endian=">"))], endian=">")
    chunk = parse(data)[0]
    assert chunk.head_dimensions() == (40, 30)


def test_head_dimensions_wrong_tag_raises() -> None:
    data = build_container([("CELL", b"\x00" * 64)], endian=">")
    with pytest.raises(WLDError):
        parse(data)[0].head_dimensions()


def test_cell_count() -> None:
    data = build_container([("CELL", b"\x00" * 128)], endian=">")
    assert parse(data)[0].cell_count() == 2


def test_cell_count_rejects_unaligned() -> None:
    data = build_container([("CELL", b"\x00" * 100)], endian=">")
    with pytest.raises(WLDError):
        parse(data)[0].cell_count()


def test_map_padding_and_cell_math() -> None:
    # 40x30 8-px plane -> 20x15 16x16 cells = 300 cells -> 900 bytes, already
    # 4-aligned.  A 41x30 plane -> 20x15 cells -> 900 -> pad 0 too; use an odd
    # width in cells: 42x16 -> 21x8 = 168 cells -> 504 bytes (4-aligned).  Force
    # a padded case via the pure helpers below.
    for w, h in [(40, 30), (42, 16), (40, 17), (100, 100)]:
        cells = wld.map_cells(w, h)
        padded = wld.map_padded_size(w, h)
        assert padded % 4 == 0
        assert 0 <= padded - cells * 3 <= 3


def test_map_cell_count_cross_check() -> None:
    w, h = 40, 30
    head = Chunk("HEAD", b"HEAD", 5240, head_payload(w, h, endian=">"), 0)
    mp = map_payload(w, h)
    map_chunk = Chunk("MAP", b"MAP ", len(mp), mp, 0)
    assert wld.map_cell_count(map_chunk, head) == wld.map_cells(w, h)


def test_map_cell_count_mismatch_raises() -> None:
    head = Chunk("HEAD", b"HEAD", 5240, head_payload(40, 30, endian=">"), 0)
    bad = Chunk("MAP", b"MAP ", 4, b"\x00" * 4, 0)
    with pytest.raises(WLDError):
        wld.map_cell_count(bad, head)


def test_truncated_payload_raises() -> None:
    data = synthetic_world(endian=">")
    with pytest.raises(WLDParseError) as exc:
        parse(data[:-12])  # cut inside CELL's payload
    assert exc.value.offset > 0
    assert "remain" in str(exc.value)


def test_trailing_bytes_raise() -> None:
    data = synthetic_world(endian=">")
    with pytest.raises(WLDParseError) as exc:
        parse(data + b"\x00\x00\x00\x00")
    assert "trailing" in str(exc.value)


def test_non_printable_tag_raises() -> None:
    header = b"\x00\x01\x02\x03" + struct.pack(">I", 4) + b"\x00" * 4
    with pytest.raises(WLDParseError):
        parse(header)


def test_empty_input_raises() -> None:
    with pytest.raises(WLDParseError):
        parse(b"")


def test_parse_rejects_non_bytes() -> None:
    with pytest.raises(TypeError):
        parse("not bytes")  # type: ignore[arg-type]


def test_encode_tag() -> None:
    assert wld.encode_tag("WRLD") == b"WRLD"
    assert wld.encode_tag("NMY") == b"NMY "
    assert wld.encode_tag("E") == b"E   "
    with pytest.raises(WLDError):
        wld.encode_tag("TOOLONG")


def test_world_length_and_iteration() -> None:
    world = parse(synthetic_world(endian=">", planes=((40, 30), (80, 60))))
    assert len(world) == len(list(world))
    assert world.tags == [c.tag for c in world]
