"""Tests for the .WLD chunk scanner (synthetic data only)."""

from __future__ import annotations

import struct

import pytest

from lomax_modern.wldscan import KNOWN_TAGS, scan_bytes
from tests.fixtures.synth import build_container, synthetic_world


@pytest.mark.parametrize("endian", ["<", ">"])
def test_detects_documented_layout(endian: str) -> None:
    data = synthetic_world(endian=endian)
    result = scan_bytes(data)

    assert result.chunks, "expected a chunk chain"
    assert result.tags == list(KNOWN_TAGS)
    assert result.confidence == "confirmed-chain"
    assert result.coverage == pytest.approx(1.0)
    expected = "u32le" if endian == "<" else "u32be"
    assert expected in (result.layout or "")


@pytest.mark.parametrize("order", ["tag+size", "size+tag"])
def test_detects_header_order(order: str) -> None:
    data = build_container(
        [("HEAD", b"\0" * 8), ("END", b"")], order=order, endian="<"
    )
    result = scan_bytes(data)
    assert [c.tag for c in result.chunks] == ["HEAD", "END"]
    assert result.confidence == "confirmed-chain"


def test_offsets_are_exact() -> None:
    data = synthetic_world()
    result = scan_bytes(data)
    by_tag = {c.tag: c for c in result.chunks}

    assert by_tag["WRLD"].header_offset == 0
    assert by_tag["WRLD"].payload_offset == 8
    assert by_tag["WRLD"].payload_size == 8

    # WRLD is 8 header + 8 payload bytes long, so NMY starts at 16.
    assert by_tag["NMY"].header_offset == 16
    assert by_tag["NMY"].payload_offset == 24


def test_zero_length_last_chunk_reaches_eof() -> None:
    data = build_container([("WRLD", b"\0" * 4), ("END", b"")])
    result = scan_bytes(data)
    assert result.chunks[-1].tag == "END"
    assert result.chunks[-1].payload_size == 0
    assert result.coverage == pytest.approx(1.0)


def test_unaligned_size_breaks_chain() -> None:
    header = b"WRLD" + struct.pack("<I", 6)  # 6 is not a multiple of 4
    result = scan_bytes(header + b"\0" * 6)
    assert result.chunks == []
    assert result.confidence == "no-chain"


def test_garbage_is_reported_not_guessed() -> None:
    result = scan_bytes(bytes(range(256)) * 4)
    assert result.chunks == []
    assert result.confidence == "no-chain"
    assert "not be a chunk container" in result.notes[0]


def test_truncated_file_reports_partial_chain() -> None:
    data = synthetic_world()
    truncated = data[:-12]  # cut inside CELL's payload
    result = scan_bytes(truncated)
    assert result.chunks
    assert result.confidence == "partial-chain"
    assert result.coverage < 1.0


def test_unknown_tags_are_flagged() -> None:
    data = build_container([("ABCD", b"\0" * 4), ("END", b"")])
    result = scan_bytes(data)
    assert result.confidence == "confirmed-chain"
    assert result.chunks[0].known is False
    assert any("documented set" in note for note in result.notes)


def test_empty_file() -> None:
    result = scan_bytes(b"")
    assert result.chunks == []
    assert result.confidence == "no-chain"
