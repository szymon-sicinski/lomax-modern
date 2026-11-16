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
    probe_wav,
    summarise,
)
from tests.fixtures.synth import build_container, synthetic_world


def head_payload(width_units: int, height_units: int, *, endian: str = ">") -> bytes:
    """A minimal HEAD payload: plane width/height in 8-pixel units."""
    return struct.pack(endian + "II", width_units, height_units) + b"\0" * 24


def world_bytes(*heads: tuple[int, int]) -> bytes:
    chunks = [("WRLD", b"PS-X" + b"\0" * 4), ("NMY", b"\0" * 8)]
    for w, h in heads:
        chunks.append(("HEAD", head_payload(w, h)))
        chunks.append(("TTAB", b"\0" * 16))
        chunks.append(("MAP", b"\0" * 16))
        chunks.append(("GNMY", b"\0" * 8))
    chunks.append(("CELL", b"\0" * 16))
    chunks.append(("END", b""))
    return build_container(chunks, endian=">")


def make_wav(path: Path, *, channels: int = 1, rate: int = 22050, bits: int = 16, samples: int = 100) -> None:
    data_bytes = samples * channels * bits // 8
    fmt = struct.pack("<HHIIHH", 1, channels, rate, rate * channels * bits // 8, channels * bits // 8, bits)
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    chunks += b"data" + struct.pack("<I", data_bytes) + b"\0" * data_bytes
    path.write_bytes(b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks)


def test_head_hypothesis_prefers_big_endian(tmp_path: Path) -> None:
    path = tmp_path / "WEST.WLD"
    path.write_bytes(world_bytes((40, 30), (48, 30)))
    result = measure_world(path)

    plausible = [h for h in result.heads if h.plausible]
    assert len(plausible) == 2
    assert {h.endian for h in plausible} == {">"}
    assert sorted(h.width_px for h in plausible) == [320, 384]
    assert {h.height_px for h in plausible} == {240}


def test_implausible_geometry_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "BAD.WLD"
    # 13 units wide -> 104 px, below the floor and not a multiple of 16.
    path.write_bytes(world_bytes((13, 30)))
    result = measure_world(path)
    assert not [h for h in result.heads if h.plausible]


def test_chunk_sequence_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "MAIN.WLD"
    path.write_bytes(world_bytes((40, 30)))
    result = measure_world(path)
    assert result.confidence == "confirmed-chain"
    assert result.chunk_counts["HEAD"] == 1
    assert result.chunk_counts["MAP"] == 1


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

    assert report["world_totals"]["files"] == 2
    hist = report["world_totals"]["width_histogram_px"]
    assert hist == {"320": 2, "384": 1}
    assert report["world_totals"]["head_endian_votes"] == {">": 3}
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
    assert info.seconds == pytest.approx(50 * 2 * 8 / 8 / (44100 * 2 * 8 / 8), rel=1e-6)


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
