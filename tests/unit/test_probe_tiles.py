"""Tests for the MAP/TTAB/CELL tile-pipeline probe (synthetic data only).

The fixtures here are built directly to the *recovered* layouts (docs §2.4/§2.8):
a ``MAP`` is ``N`` big-endian ``u16`` words then ``N`` collision bytes; a ``TTAB``
record is 16 bytes = four ``[index word, flag word]`` cells.  They deliberately
do **not** use ``tests.fixtures.synth.ttab_payload`` / ``map_payload``, which
still encode the superseded interleaved/8-byte readings this probe scores as
losing hypotheses.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from lomax_modern.cli import main as cli_main
from lomax_modern.probe_tiles import (
    FLIP_H,
    FLIP_V,
    PALETTE_MASK,
    format_report,
    probe_tiles,
    split_map,
    split_ttab,
)
from tests.fixtures.synth import build_container


def _head(width_units: int, height_units: int) -> bytes:
    return struct.pack(">II", width_units, height_units)


def _map(words: list[int], collisions: list[int]) -> bytes:
    """A corrected MAP payload: big-endian words, then collision bytes, pad to 4."""
    body = b"".join(struct.pack(">H", w) for w in words) + bytes(collisions)
    return body + b"\0" * (-len(body) % 4)


def _ttab(slots: list[tuple[int, int]]) -> bytes:
    """A corrected TTAB payload: 16-byte records of four (index, flags) cells."""
    out = bytearray()
    for record in range(0, len(slots), 4):
        quad = slots[record : record + 4]
        if len(quad) != 4:
            raise ValueError("TTAB slots must come in groups of four")
        for index, flags in quad:
            out += struct.pack(">HH", index, flags)
    return bytes(out)


def _world(*planes: tuple[bytes, bytes, bytes], cells: bytes) -> bytes:
    chunks: list[tuple[str, bytes]] = [("WRLD", b"PS-X" + b"\0" * 4)]
    for head, ttab, map_ in planes:
        chunks += [("HEAD", head), ("TTAB", ttab), ("MAP", map_)]
    chunks += [("CELL", cells), ("END", b"")]
    return build_container(chunks, endian=">")


def _install(tmp_path: Path, *worlds: tuple[str, bytes]) -> Path:
    root = tmp_path / "game"
    (root / "WORLDS").mkdir(parents=True)
    for name, data in worlds:
        (root / "WORLDS" / name).write_bytes(data)
    return root


def _cells(n: int) -> bytes:
    return b"\0" * (64 * n)


# ---------------------------------------------------------------------------
# Decoders.
# ---------------------------------------------------------------------------


def test_split_map_separates_words_from_collisions() -> None:
    payload = _map([0, 1, 1, 0], [0x00, 0xC0, 0xC0, 0x00])
    words, collisions = split_map(payload, 4)
    assert words == (0, 1, 1, 0)
    assert collisions == bytes([0x00, 0xC0, 0xC0, 0x00])


def test_split_ttab_reads_index_flag_pairs() -> None:
    payload = _ttab([(0, 0x0100), (1, 0x2100), (2, 0x4100), (3, 0x6100)])
    slots = split_ttab(payload)
    assert len(slots) == 4
    assert slots[0].index == 0 and slots[0].palette == 1 and slots[0].flip == 0
    assert slots[1].flip == FLIP_H
    assert slots[2].flip == FLIP_V
    assert slots[3].flip == FLIP_H | FLIP_V
    assert slots[1].palette == 1  # 0x2100 -> palette nibble 1, flip H


def test_split_ttab_rejects_unrecorded_size() -> None:
    with pytest.raises(ValueError):
        split_ttab(b"\0" * 24)  # 24 is not a multiple of 16


# ---------------------------------------------------------------------------
# Probe behaviour on synthetic installs.
# ---------------------------------------------------------------------------


def _sample() -> bytes:
    """One 2x2-cell plane (4 map cells, 2 tiles, 5 cells)."""
    head = _head(4, 4)  # 4*8/16 = 2 cells per side -> 4 cells
    map_ = _map([0, 1, 1, 0], [0x00, 0xC0, 0xC0, 0x00])
    ttab = _ttab(
        [
            (0, 0x0100), (1, 0x2100), (2, 0x4100), (3, 0x6100),  # tile 0
            (4, 0x0100), (0, 0x0000), (1, 0x0200), (2, 0x0300),  # tile 1
        ]
    )
    return _world((head, ttab, map_), cells=_cells(5))


def test_probe_reports_recovered_layout_counts(tmp_path: Path) -> None:
    root = _install(tmp_path, ("VILLAGE.WLD", _sample()))
    report = probe_tiles(root)

    assert report["planes"] == 1
    assert report["map"]["words"] == 4
    assert report["map"]["distinct_words"] == 2
    assert report["map"]["max_word"] == 1
    assert report["map"]["out_of_bank"] == 0

    assert report["ttab"]["records"] == 2
    assert report["ttab"]["slots"] == 8
    assert report["ttab"]["distinct_indices"] == 5  # {0,1,2,3,4}
    assert report["ttab"]["index_max"] == 4
    assert report["ttab"]["index_out_of_bank"] == 0

    flips = report["ttab"]["flag_flip_counts"]
    assert flips["0x0000"] == 5
    assert flips["0x2000"] == 1
    assert flips["0x4000"] == 1
    assert flips["0x6000"] == 1

    palettes = report["ttab"]["flag_palette_counts"]
    assert palettes["0"] == 1
    assert palettes["1"] == 5
    assert palettes["2"] == 1
    assert palettes["3"] == 1
    assert report["ttab"]["flag_words_with_unused_bits"] == 0

    assert report["collision"]["bytes"] == 4
    assert report["collision"]["distinct_values"] == 2
    assert report["collision"]["zero_count"] == 2


def test_probe_scores_superseded_readings_as_losing(tmp_path: Path) -> None:
    root = _install(tmp_path, ("VILLAGE.WLD", _sample()))
    s = probe_tiles(root)["superseded_hypothesis_scores"]

    # Interleaved 3-bytes-per-cell reads byte pairs that straddle the split and
    # produce out-of-bank "tile indices"; the recovered split has none.
    assert s["map_interleaved_out_of_bank"] > 0
    assert s["map_interleaved_total"] == 4


def test_probe_explains_bonus_256_as_flag_word(tmp_path: Path) -> None:
    # A flag word 0x0100 (palette 1) read as a 13-bit "cell index" is 256, which
    # is out of bank when the CELL chunk holds fewer than 257 records.  This is
    # the exact Q22 anomaly: index words are all in-bank; only the flag words
    # masquerade as "index 256" under the superseded 13-bit reading.
    head = _head(4, 4)
    map_ = _map([0, 0, 0, 0], [0, 0, 0, 0])
    ttab = _ttab([(0, 0x0100), (1, 0x0100), (2, 0x0100), (3, 0x0100)])
    root = _install(tmp_path, ("BONUS.WLD", _world((head, ttab, map_), cells=_cells(251))))
    report = probe_tiles(root)

    assert report["ttab"]["index_out_of_bank"] == 0
    s = report["superseded_hypothesis_scores"]
    assert s["ttab_13bit_index_out_of_bank"] == 4  # the four flag words
    assert s["ttab_13bit_bonus_256_count"] == 4


def test_probe_empty_install(tmp_path: Path) -> None:
    root = _install(tmp_path)  # no worlds
    report = probe_tiles(root)
    assert report["planes"] == 0
    assert report["map"]["words"] == 0
    assert report["ttab"]["records"] == 0


# ---------------------------------------------------------------------------
# Report formatting and CLI.
# ---------------------------------------------------------------------------


def test_format_report_mentions_verdicts(tmp_path: Path) -> None:
    root = _install(tmp_path, ("VILLAGE.WLD", _sample()))
    text = format_report(probe_tiles(root))
    assert "MAP -> TTAB -> CELL" in text
    assert "Q20" in text
    assert "Q21" in text
    assert "Q22" in text
    assert "out-of-bank" in text


def test_cli_subcommand_runs(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _install(tmp_path, ("VILLAGE.WLD", _sample()))
    assert cli_main(["probe-tiles", str(root)]) == 0
    out = capsys.readouterr().out
    assert "probe: MAP -> TTAB -> CELL" in out
    assert "records 2" in out


def test_cli_subcommand_missing_dir_errors(tmp_path: Path) -> None:
    assert cli_main(["probe-tiles", str(tmp_path / "nope")]) == 2
