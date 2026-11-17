"""Tests for the measurement probes (synthetic data only)."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from lomax_modern.measure import (
    measure_install,
    measure_world,
    probe_demos,
    probe_game_txt,
    probe_gnmy,
    probe_wav,
    summarise,
)
from tests.fixtures.synth import (
    build_container,
    gnmy_payload,
    head_payload,
    map_payload,
    synthetic_world,
)


def world_bytes(*planes: tuple[int, int]) -> bytes:
    """A world whose MAP sizes agree with its HEAD sizes."""
    chunks = [("WRLD", b"PS-X" + b"\0" * 4), ("NMY", b"\0" * 8)]
    for w, h in planes:
        chunks += [
            ("HEAD", head_payload(w, h)),
            ("TTAB", b"\0" * 16),
            ("MAP", map_payload(w, h)),
            ("GNMY", gnmy_payload((0, 3))),
        ]
    chunks += [("CELL", b"\0" * 64), ("END", b"")]
    return build_container(chunks, endian=">")


def make_wav(path: Path, *, channels: int = 1, rate: int = 22050, bits: int = 16, samples: int = 100) -> None:
    data_bytes = samples * channels * bits // 8
    fmt = struct.pack("<HHIIHH", 1, channels, rate, rate * channels * bits // 8, channels * bits // 8, bits)
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    chunks += b"data" + struct.pack("<I", data_bytes) + b"\0" * data_bytes
    path.write_bytes(b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks)


def test_head_verified_against_map_size(tmp_path: Path) -> None:
    path = tmp_path / "WEST.WLD"
    path.write_bytes(world_bytes((40, 30), (48, 30)))
    result = measure_world(path)

    verified = result.verified_heads
    assert len(verified) == 2
    assert {h.endian for h in verified} == {">"}
    assert sorted(h.width_px for h in verified) == [320, 384]
    assert {h.height_px for h in verified} == {240}
    assert [h.tiles for h in verified] == [(20, 15), (24, 15)]


def test_map_mismatch_leaves_plane_unverified(tmp_path: Path) -> None:
    path = tmp_path / "BAD.WLD"
    data = world_bytes((40, 30))
    # Corrupt the MAP size by rebuilding with a deliberately wrong size.
    chunks = [("WRLD", b"PS-X" + b"\0" * 4), ("NMY", b"\0" * 8)]
    chunks += [
        ("HEAD", head_payload(40, 30)),
        ("TTAB", b"\0" * 16),
        ("MAP", b"\0" * 64),  # far too small for 300 cells
        ("GNMY", gnmy_payload((0,))),
    ]
    chunks += [("CELL", b"\0" * 64), ("END", b"")]
    path.write_bytes(build_container(chunks, endian=">"))

    result = measure_world(path)
    assert result.heads
    assert not result.verified_heads
    assert all(h.map_bytes is not None for h in result.heads)
    assert all(not h.map_ok for h in result.heads)
    assert data  # sanity: the good fixture differs


def test_map_padding_is_accepted(tmp_path: Path) -> None:
    """MAP may be up to 3 bytes larger than 3*cells, as long as it is 4-aligned.

    7x43 tiles = 301 cells -> 903 bytes, padded to 904 (+1). Only cell counts
    that are not a multiple of 4 exercise the padding rule.
    """
    path = tmp_path / "PAD.WLD"
    path.write_bytes(world_bytes((14, 86)))
    result = measure_world(path)

    verified = result.verified_heads
    assert len(verified) == 1
    head = verified[0]
    assert (head.tiles, head.expected_map_bytes, head.map_bytes) == ((7, 43), 903, 904)


def test_chunk_sequence_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "MAIN.WLD"
    path.write_bytes(world_bytes((40, 30)))
    result = measure_world(path)
    assert result.confidence == "confirmed-chain"
    assert result.chunk_counts["HEAD"] == 1
    assert result.chunk_counts["MAP"] == 1


def test_gnmy_walk(tmp_path: Path) -> None:
    info = probe_gnmy(gnmy_payload((0, 3, 3, 42)))
    assert info["entries"] == 4
    assert info["trailing_bytes"] == 4
    assert info["top_types"] == {3: 2, 0: 1, 42: 1}


def test_measure_install_histogram(tmp_path: Path) -> None:
    root = tmp_path / "game"
    (root / "WORLDS").mkdir(parents=True)
    (root / "SFX").mkdir()
    (root / "DEMOS").mkdir()
    (root / "LOMAX.EXE").write_bytes(b"MZ" + b"\0" * 62)
    (root / "GAME.TXT").write_text("@Hello&World#\nPlain line\n", encoding="latin-1")
    (root / "WORLDS" / "WEST.WLD").write_bytes(world_bytes((40, 30), (48, 30)))
    (root / "WORLDS" / "ED.WLD").write_bytes(world_bytes((40, 30)))
    make_wav(root / "SFX" / "JUMP.WAV")

    report = measure_install(root)
    totals = report["world_totals"]

    assert totals["files"] == 2
    assert totals["planes"] == 3
    assert totals["planes_verified"] == 3
    assert totals["width_histogram_px"] == {"320": 2, "384": 1}
    assert totals["head_endian_votes"] == {">": 3}
    assert totals["cells"] == 2  # one 64-byte CELL per file
    assert totals["cells_multiple_of_64"] is True
    assert report["audio"]["SFX"][0]["valid"] is True
    assert report["audio"]["SFX"][0]["rate"] == 22050
    assert report["game_txt"]["markers"] == {"@": 1, "#": 1, "&": 1}


def test_summarise_lists_histogram(tmp_path: Path) -> None:
    root = tmp_path / "game"
    (root / "WORLDS").mkdir(parents=True)
    (root / "WORLDS" / "WEST.WLD").write_bytes(world_bytes((40, 30)))
    text = summarise(measure_install(root))
    assert "plane-width histogram" in text
    assert "320 px ( 20 tiles)" in text
    assert "planes: 1 (1 verified" in text


def test_wav_probe_handles_non_wav(tmp_path: Path) -> None:
    path = tmp_path / "ODD.WAV"
    path.write_bytes(b"\x00\x01\x02\x03" + b"\0" * 60)
    info = probe_wav(path)
    assert info.valid is False
    assert info.rate is None


def test_wav_probe_reports_format(tmp_path: Path) -> None:
    path = tmp_path / "VOICE.WAV"
    make_wav(path, channels=2, rate=44100, bits=8, samples=50)
    info = probe_wav(path)
    assert info.valid is True
    assert (info.channels, info.rate, info.bits) == (2, 44100, 8)
    assert info.header_bytes == 44


def test_game_txt_structure(tmp_path: Path) -> None:
    path = tmp_path / "GAME.TXT"
    path.write_bytes("linha @um\nlinha #dois&tres\n".encode("latin-1") + b"\xe9\n")
    got = probe_game_txt(path)
    assert got["lines"] == 3
    assert got["non_ascii_bytes"] == 1
    assert got["lines_with_marker"] == 2


def test_demos_structure(tmp_path: Path) -> None:
    folder = tmp_path / "DEMOS"
    folder.mkdir()
    (folder / "DEMO01N1.DAT").write_bytes(b"\x01\x02\x03\x04" + b"\0" * 12)
    (folder / "DEMO01N2.DAT").write_bytes(b"\x01\x02\x03\x04" + b"\0" * 12)
    got = probe_demos(folder)
    assert got["files"] == 2
    assert got["size_histogram"] == {16: 2}
    assert got["first8_printable_ascii"] is False


def test_scan_of_a_chunkless_file_is_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "NOTWLD.WLD"
    path.write_bytes(b"\xff" * 64)
    result = measure_world(path)
    assert result.heads == []
    assert result.confidence == "no-chain"
