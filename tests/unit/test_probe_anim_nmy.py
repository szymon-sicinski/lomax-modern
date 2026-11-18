"""Tests for the ANIM/NMY/GNMY structural probe (synthetic data only)."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from lomax_modern.cli import main as cli_main
from lomax_modern.probe_anim_nmy import (
    format_report,
    probe_anim_nmy,
    walk_fixed,
    walk_gnmy,
    walk_u16_size,
    walk_u16_size_nul_name,
    walk_u32_size,
)
from tests.fixtures.synth import build_container, gnmy_payload


def _world_bytes(
    *,
    anim: bytes = b"\x00" * 52,
    nmy: bytes = b"\x00" * 16,
    gnmy: bytes | None = None,
) -> bytes:
    """A minimal world with a controlled ANIM/NMY/GNMY payload.

    Only the chunks the probe reads need to be present; the chunk chain still
    has to be valid (4-aligned sizes, reaches EOF), which ``build_container``
    guarantees. The container uses the real big-endian size convention.
    """
    chunks: list[tuple[str, bytes]] = [("WRLD", b"PS-X" + b"\x00" * 4)]
    if nmy is not None:
        chunks.append(("NMY", nmy))
    if gnmy is not None:
        chunks.append(("GNMY", gnmy))
    if anim is not None:
        chunks.append(("ANIM", anim))
    chunks.append(("END", b""))
    return build_container(chunks, endian=">")


def _install(tmp_path: Path, *worlds: tuple[str, bytes]) -> Path:
    root = tmp_path / "game"
    (root / "WORLDS").mkdir(parents=True)
    (root / "LOMAX.EXE").write_bytes(b"MZ" + b"\x00" * 62)
    for name, data in worlds:
        (root / "WORLDS" / name).write_bytes(data)
    return root


def _group(report: dict, tag: str) -> dict:
    return next(g for g in report["groups"] if g["tag"] == tag)


def _candidate(group: dict, key: str) -> dict:
    return next(c for c in group["candidates"] if c["key"] == key)


# ---------------------------------------------------------------------------
# Walkers.
# ---------------------------------------------------------------------------


def test_walk_fixed_counts_whole_records_only() -> None:
    assert walk_fixed(b"\x00" * 56, 56) == (56, 1)
    assert walk_fixed(b"\x00" * 112, 56) == (112, 2)
    # 52 bytes is not a whole number of 56-byte records.
    assert walk_fixed(b"\x00" * 52, 56) == (0, 0)


def test_walk_u16_size_body_and_total() -> None:
    # two records of [size=4, body 4 bytes] => 12 bytes total.
    payload = struct.pack("<H", 4) + b"\x01\x02\x03\x04" + struct.pack("<H", 4) + b"\x05\x06\x07\x08"
    assert walk_u16_size(payload, "<", size_includes_field=False) == (12, 2)
    # Under the "size = total" reading a size of 4 consumes only 4 bytes, so
    # the walk stops earlier (and never reaches EOF cleanly).
    consumed, records = walk_u16_size(payload, "<", size_includes_field=True)
    assert records >= 1 and consumed < 12


def test_walk_u32_size() -> None:
    payload = struct.pack("<I", 4) + b"\x01\x02\x03\x04"
    assert walk_u32_size(payload, "<", size_includes_field=False) == (8, 1)


def test_walk_u16_size_nul_name_accepts_names_only() -> None:
    good = struct.pack("<H", 5) + b"NAMEx"
    assert walk_u16_size_nul_name(good) == (7, 1)
    # A size that points past EOF, or a non-printable byte, stops the walk.
    assert walk_u16_size_nul_name(struct.pack("<H", 0xFF) + b"\x00") == (0, 0)
    assert walk_u16_size_nul_name(struct.pack("<H", 2) + b"\x00\xFF") == (0, 0)


def test_walk_gnmy_reports_trailing() -> None:
    payload = gnmy_payload((0, 3))
    consumed, entries, leftover = walk_gnmy(payload)
    assert (entries, leftover) == (2, 4)
    assert consumed == len(payload) - leftover


# ---------------------------------------------------------------------------
# Probe behaviour on synthetic installs.
# ---------------------------------------------------------------------------


def test_anim_falsified_claim_is_retracted_and_unresolved(tmp_path: Path) -> None:
    root = _install(tmp_path, ("WEST.WLD", _world_bytes(anim=b"\x00" * 52)))
    report = probe_anim_nmy(root)

    anim = _group(report, "ANIM")
    assert anim["chunks"] == 1
    assert anim["verdict"] == "unresolved"

    fixed = _candidate(anim, "fixed-0x38")
    assert fixed["status"] == "retracted"
    assert fixed["chunks_consumed"] == 0  # 52 is not a multiple of 56
    assert fixed["chunks_total"] == 1


def test_anim_aligned_size_still_does_not_win(tmp_path: Path) -> None:
    # A 56-byte ANIM is 0x38-aligned, but that alone is not a record layout;
    # the retracted claim must not flip the group verdict to "consistent".
    root = _install(tmp_path, ("WEST.WLD", _world_bytes(anim=b"\x00" * 56)))
    anim = _group(probe_anim_nmy(root), "ANIM")

    fixed = _candidate(anim, "fixed-0x38")
    assert fixed["chunks_consumed"] == 1  # aligned, but retracted
    assert anim["verdict"] == "unresolved"


def test_anim_clean_size_prefixed_array_is_detected(tmp_path: Path) -> None:
    # A payload that *is* a clean u16-size-prefixed record array should be
    # recognised, proving the scoring detects a real framing when one exists.
    payload = struct.pack("<H", 6) + b"\x01\x02\x03\x04\x05\x06"
    root = _install(tmp_path, ("WEST.WLD", _world_bytes(anim=payload)))
    anim = _group(probe_anim_nmy(root), "ANIM")

    u16 = _candidate(anim, "u16-size-le")
    assert u16["chunks_consumed"] == 1
    assert anim["verdict"] == "consistent"


def test_nmy_falsified_claim_is_retracted(tmp_path: Path) -> None:
    # One valid name record then junk: the documented walk reads 1 record and
    # stalls, so 0/1 chunks are fully consumed.  (Payload is padded to 4 bytes
    # to satisfy the chunk-container rule; the name is synthetic.)
    nmy = struct.pack("<H", 4) + b"NAME" + b"\xFF\xFF"
    root = _install(tmp_path, ("WEST.WLD", _world_bytes(nmy=nmy)))
    nmy_group = _group(probe_anim_nmy(root), "NMY")

    nul = _candidate(nmy_group, "u16-size-nul-name")
    assert nul["status"] == "retracted"
    assert nul["chunks_consumed"] == 0
    assert nmy_group["verdict"] == "unresolved"
    # The printable "NAME" run is counted even though the walk does not parse it.
    assert nmy_group["printable_runs_total"] >= 1


def test_gnmy_walk_is_consistent(tmp_path: Path) -> None:
    root = _install(tmp_path, ("WEST.WLD", _world_bytes(gnmy=gnmy_payload((0, 3, 42)))))
    gnmy = _group(probe_anim_nmy(root), "GNMY")

    assert gnmy["entries"] == 3
    assert gnmy["verdict"] == "structure-consistent (meaning unresolved)"
    candidate = _candidate(gnmy, "u16-size-u16-type")
    assert candidate["status"] == "consistent"
    assert candidate["chunks_consumed"] == 1


def test_empty_install_reports_no_chunks(tmp_path: Path) -> None:
    root = _install(tmp_path)  # no world files
    report = probe_anim_nmy(root)
    for tag in ("ANIM", "NMY", "GNMY"):
        assert _group(report, tag)["verdict"] == "no chunks found"


def test_smallest_anim_token_diagnostic_is_bounded(tmp_path: Path) -> None:
    # Synthetic tokens only — never the real game's token values.
    anim = struct.pack("<8H", 100, 101, 102, 103, 104, 105, 106, 107)
    root = _install(tmp_path, ("MAIN.WLD", _world_bytes(anim=anim)))
    anim_group = _group(probe_anim_nmy(root), "ANIM")

    small = anim_group["smallest"]
    assert small["size"] == len(anim)
    assert small["leading_u16_le"] == [100, 101, 102, 103, 104, 105, 106, 107]
    assert len(small["leading_u16_le"]) <= 8


def test_offsets_are_reported(tmp_path: Path) -> None:
    root = _install(tmp_path, ("WEST.WLD", _world_bytes(anim=b"\x00" * 52, nmy=b"\x00" * 16)))
    report = probe_anim_nmy(root)

    anim_offsets = report["chunk_offsets"]["ANIM"]
    assert len(anim_offsets) == 1
    assert anim_offsets[0]["file"] == "WEST.WLD"
    assert anim_offsets[0]["header_offset"] < anim_offsets[0]["payload_offset"]
    assert anim_offsets[0]["size"] == 52


# ---------------------------------------------------------------------------
# Report formatting.
# ---------------------------------------------------------------------------


def test_format_report_labels_hypotheses_and_prints_unresolved(tmp_path: Path) -> None:
    root = _install(tmp_path, ("WEST.WLD", _world_bytes(anim=b"\x00" * 52)))
    text = format_report(probe_anim_nmy(root))

    assert "hypothesis" in text
    assert "retracted" in text
    assert "unresolved" in text
    assert "0/1" in text  # the coverage score for a single unaligned chunk


def test_cli_subcommand_runs(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _install(tmp_path, ("WEST.WLD", _world_bytes(anim=b"\x00" * 52)))
    assert cli_main(["probe-anim-nmy", str(root)]) == 0
    out = capsys.readouterr().out
    assert "ANIM" in out and "unresolved" in out


def test_cli_subcommand_missing_dir_errors(tmp_path: Path) -> None:
    assert cli_main(["probe-anim-nmy", str(tmp_path / "nope")]) == 2
