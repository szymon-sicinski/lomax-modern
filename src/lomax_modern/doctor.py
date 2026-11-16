"""Read-only inventory of a Lomax installation.

Reports presence, sizes and hashes only -- never file contents.  Game bytes
must never leave the user's machine, and never enter this repository.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

#: Files a ``SETUP.EXE`` install writes next to the executable.
EXPECTED_FILES: tuple[str, ...] = (
    "LOMAX.EXE",
    "GAME.TXT",
)

#: Data folders a ``SETUP.EXE`` install writes.
EXPECTED_DIRS: tuple[str, ...] = (
    "WORLDS",
    "SFX",
    "DEMOS",
    "JINGLES",
    "AMBIENT",
)

#: Optional but expected on a full install.
OPTIONAL_FILES: tuple[str, ...] = (
    "LOMAX.HLP",
    "LOMAX.CNT",
    "LOMAX.GID",
)

_HASH_LIMIT = 64 * 1024 * 1024


@dataclass(frozen=True)
class EntryReport:
    name: str
    kind: str  # "file" | "dir"
    present: bool
    files: int = 0
    bytes: int = 0
    sha256: str | None = None


def _sha256(path: Path) -> str | None:
    try:
        if path.stat().st_size > _HASH_LIMIT:
            return None
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def _dir_stats(path: Path) -> tuple[int, int]:
    files = 0
    size = 0
    for child in path.rglob("*"):
        if child.is_file():
            files += 1
            try:
                size += child.stat().st_size
            except OSError:
                pass
    return files, size


def inventory(game_dir: str | Path) -> list[EntryReport]:
    """Describe the game folder. Raises ``NotADirectoryError`` if it is missing."""
    root = Path(game_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")

    reports: list[EntryReport] = []
    for name in EXPECTED_FILES + OPTIONAL_FILES:
        p = root / name
        exists = p.is_file()
        reports.append(
            EntryReport(
                name=name,
                kind="file",
                present=exists,
                bytes=p.stat().st_size if exists else 0,
                sha256=_sha256(p) if exists else None,
            )
        )
    for name in EXPECTED_DIRS:
        p = root / name
        exists = p.is_dir()
        files, size = _dir_stats(p) if exists else (0, 0)
        reports.append(
            EntryReport(
                name=name + "/",
                kind="dir",
                present=exists,
                files=files,
                bytes=size,
            )
        )
    return reports


def find_world_files(game_dir: str | Path) -> list[Path]:
    root = Path(game_dir)
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.WLD") if p.is_file()) + sorted(
        p for p in root.rglob("*.wld") if p.is_file()
    )


def format_report(reports: list[EntryReport], worlds: list[Path]) -> str:
    lines = [
        f"{'entry':<14}{'kind':<7}{'state':<10}{'files':>7}{'bytes':>12}  sha256",
        "-" * 72,
    ]
    missing_core = []
    for r in reports:
        state = "present" if r.present else "MISSING"
        digest = (r.sha256[:16] + "...") if r.sha256 else ""
        lines.append(
            f"{r.name:<14}{r.kind:<7}{state:<10}{r.files or '':>7}"
            f"{(r.bytes or ''):>12}  {digest}"
        )
        if not r.present and r.name in EXPECTED_FILES + EXPECTED_DIRS:
            missing_core.append(r.name)

    lines.append("")
    if worlds:
        total = sum(p.stat().st_size for p in worlds)
        lines.append(f"world files: {len(worlds)} ({total} bytes)")
        for p in worlds:
            lines.append(f"  {p.name:<20}{p.stat().st_size:>10} bytes")
    else:
        lines.append("world files: none found (no *.WLD in the tree)")
        missing_core.append("WORLDS/*.WLD")

    lines.append("")
    if missing_core:
        lines.append("verdict: incomplete install, missing: " + ", ".join(missing_core))
    else:
        lines.append("verdict: looks like a complete PC install")
    return "\n".join(lines)
