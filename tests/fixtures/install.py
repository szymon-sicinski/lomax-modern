"""Build a synthetic *unpacked game directory* for install/present tests.

No game data: the world container comes from :mod:`tests.fixtures.synth`, the
executable is a 64-byte ``MZ`` stub and the audio files are ``RIFF`` headers
with zero payload.  Names are configurable so the case-insensitive layout path
can be tested without a real Windows install.
"""

from __future__ import annotations

from pathlib import Path

from .synth import synthetic_world


def build_install(
    root: Path,
    *,
    worlds: tuple[str, ...] = ("VILLAGE",),
    dirs: tuple[str, ...] = ("SFX", "AMBIENT", "JINGLES", "DEMOS"),
    worlds_dir: str = "WORLDS",
    exe: str = "LOMAX.EXE",
    game_txt: bool = True,
) -> Path:
    """Create the retail layout under ``root`` and return ``root``.

    ``worlds`` are stems (``.WLD`` is appended when absent); pass
    ``worlds_dir="worlds"`` / ``exe="lomax.exe"`` to model an extracted tree
    with different name case.
    """
    root.mkdir(parents=True, exist_ok=True)

    world_root = root / worlds_dir
    world_root.mkdir(exist_ok=True)
    for name in worlds:
        filename = name if name.casefold().endswith(".wld") else f"{name}.WLD"
        (world_root / filename).write_bytes(synthetic_world(endian=">"))

    for name in dirs:
        folder = root / name
        folder.mkdir(exist_ok=True)
        (folder / "STUB.WAV").write_bytes(b"RIFF" + b"\0" * 60)

    (root / exe).write_bytes(b"MZ" + b"\0" * 62)
    if game_txt:
        (root / "GAME.TXT").write_text("synthetic marker file\n", encoding="ascii")
    return root
