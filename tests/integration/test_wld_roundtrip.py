"""Round-trip every retail world file (opt-in, read-only).

Set ``LOMAX_GAME_DIR`` to a folder containing ``LOMAX.EXE``.  Nothing is
written into the game folder: each file is parsed, re-serialised in memory,
and the two byte strings are compared by hash.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from lomax_modern.doctor import find_world_files
from lomax_modern.wld import parse_file

GAME_DIR = os.environ.get("LOMAX_GAME_DIR")

pytestmark = [
    pytest.mark.realgame,
    pytest.mark.skipif(
        not GAME_DIR or not Path(GAME_DIR).is_dir(),
        reason="set LOMAX_GAME_DIR to a Lomax installation to run",
    ),
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_every_world_file_round_trips_byte_exact() -> None:
    root = Path(GAME_DIR or "")
    worlds = find_world_files(root)
    assert worlds, "no *.WLD found: is LOMAX_GAME_DIR the game folder?"

    for wld in worlds:
        source = wld.read_bytes()
        world = parse_file(wld)
        rebuilt = world.to_bytes()

        src_hash, out_hash = _sha256(source), _sha256(rebuilt)
        print(f"{wld.name:<16} sha256-in ={src_hash}  sha256-out={out_hash}")
        assert rebuilt == source, (
            f"{wld.name}: round trip changed the bytes "
            f"(in={src_hash} out={out_hash})"
        )
        assert len(world) >= 2 and world.tags[0] == "WRLD" and world.tags[-1] == "END"


def test_every_world_file_preserves_chunk_padding() -> None:
    root = Path(GAME_DIR or "")
    worlds = find_world_files(root)
    assert worlds

    for wld in worlds:
        world = parse_file(wld)
        for chunk in world:
            # Every declared payload size is 4-aligned (docs §2.2 [V]).
            assert chunk.size % 4 == 0, (
                f"{wld.name}: chunk {chunk.tag!r} at {chunk.header_offset} "
                f"has size {chunk.size}, not 4-aligned"
            )
            assert len(chunk.payload) == chunk.size
