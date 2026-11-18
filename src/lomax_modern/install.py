"""P5 install gate: is this path an unpacked Lomax game directory?

``docs/roadmap/30-risks.md`` P5 — "disc-less still means the user supplies
data" — requires the presenter to fail loudly with a **file-by-file** report
instead of a vague "cannot find its data".  This module is that check.

The card's contract is one path: an unpacked game directory in the retail
layout (``WORLDS/``, ``SFX/``, ``AMBIENT/``, ``JINGLES/``, ``DEMOS/``, with
``LOMAX.EXE`` present but unused).  There is no ISO, image or ripping path
here, and nothing in this module reads file *contents* or prints a digest.

Two deliberate leniencies, both learned from real installs:

* **Name case is ignored.** A retail install copied from Windows uses
  upper-case names; an extracted tree may not.  A case difference is not a
  missing file, and reporting it as one sends the user to re-copy a good
  install.
* **One level of nesting is resolved.** A user often drops the install as a
  *folder* inside the directory they point at (``slot/LOMAX/WORLDS/...``).
  When exactly one immediate sub-directory satisfies the layout it is used and
  the report names it; two candidates are reported as ambiguous instead of
  guessed.

Required for :attr:`InstallManifest.ok`: ``LOMAX.EXE``, ``WORLDS/`` and at
least one ``*.WLD`` inside it.  The other retail folders are *expected*: their
absence is printed as incomplete and non-fatal, because a presenter can render
a world without the sound folders.  That keeps "this is not the game" and "this
is an incomplete copy of the game" as two different verdicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "EXPECTED_DIRS",
    "EXPECTED_FILES",
    "InstallManifest",
    "ManifestEntry",
    "REQUIRED_DIRS",
    "REQUIRED_FILES",
    "WORLDS_DIR_NAME",
    "check_install",
    "is_inside_tree",
    "resolve_world",
]

#: Folder that holds the world containers.
WORLDS_DIR_NAME = "WORLDS"

#: Without these a path is not a Lomax game directory.
REQUIRED_DIRS: tuple[str, ...] = (WORLDS_DIR_NAME,)

#: Written by ``SETUP.EXE``; listed in the manifest, never used by the engine.
REQUIRED_FILES: tuple[str, ...] = ("LOMAX.EXE",)

#: Retail layout folders.  Missing ones are reported, not fatal.
EXPECTED_DIRS: tuple[str, ...] = ("SFX", "AMBIENT", "JINGLES", "DEMOS")

#: Optional retail files worth naming in the manifest.
EXPECTED_FILES: tuple[str, ...] = ("GAME.TXT",)

#: Case-insensitive suffix of a world container.
WORLD_SUFFIX = ".WLD"

#: World the presenter plays when no ``--world`` is given, matching
#: ``lomax-modern slice``'s default.  Falls back to the first ``*.WLD`` when the
#: install does not have it (e.g. a partial copy).
PREFERRED_WORLD = "VILLAGE"


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """One line of the install manifest: presence, count and size only."""

    name: str
    kind: str  # "dir" | "file"
    required: bool
    present: bool
    files: int = 0
    bytes: int = 0

    @property
    def state(self) -> str:
        return "present" if self.present else "MISSING"

    def format(self) -> str:
        note = ""
        if not self.present:
            note = "required" if self.required else "optional"
        elif self.name == "LOMAX.EXE":
            note = "unused by the engine"
        files = self.files or ""
        size = self.bytes or ""
        return (
            f"  {self.name:<13}{self.kind:<7}{self.state:<10}"
            f"{files:>7}{size:>12}  {note}"
        ).rstrip()


@dataclass(frozen=True, slots=True)
class InstallManifest:
    """The result of :func:`check_install`; ``ok`` is the gate."""

    requested_root: Path
    root: Path
    entries: tuple[ManifestEntry, ...]
    world_files: tuple[Path, ...]
    worlds_dir: Path | None
    notes: tuple[str, ...] = ()

    @property
    def missing_required(self) -> tuple[str, ...]:
        names = [entry.name for entry in self.entries if entry.required and not entry.present]
        if self.worlds_dir is not None and not self.world_files:
            names.append(f"{WORLDS_DIR_NAME}/*{WORLD_SUFFIX}")
        return tuple(names)

    @property
    def missing_expected(self) -> tuple[str, ...]:
        return tuple(
            entry.name
            for entry in self.entries
            if not entry.required and not entry.present
        )

    @property
    def ok(self) -> bool:
        """True only when every required entry is present."""
        return bool(self.entries) and not self.missing_required

    def world_sizes(self) -> int:
        total = 0
        for path in self.world_files:
            try:
                total += path.stat().st_size
            except OSError:
                pass
        return total

    def verdict(self) -> str:
        if not self.ok:
            if self.missing_required:
                return (
                    "verdict: not an unpacked Lomax game directory -- missing: "
                    + ", ".join(self.missing_required)
                )
            if not self.entries:
                return (
                    "verdict: not a directory -- pass the folder that holds "
                    f"{WORLDS_DIR_NAME}/ and {REQUIRED_FILES[0]}"
                )
            return "verdict: not an unpacked Lomax game directory"
        if self.missing_expected:
            return (
                "verdict: unpacked install, incomplete optional entries: "
                + ", ".join(self.missing_expected)
                + " (the presenter still runs)"
            )
        return "verdict: complete unpacked install (retail layout)"

    def format(self) -> str:
        """A file-by-file manifest: names, counts and sizes; no contents, no hashes."""
        lines: list[str] = []
        if self.requested_root != self.root:
            lines.append(f"requested: {self.requested_root}")
        lines.append(f"install: {self.root}")
        for note in self.notes:
            lines.append(f"note: {note}")
        if self.entries:
            lines.append("")
            lines.append(
                f"  {'entry':<13}{'kind':<7}{'state':<10}{'files':>7}{'bytes':>12}  note"
            )
            lines.extend(entry.format() for entry in self.entries)
            if self.world_files:
                lines.append(
                    f"  {'worlds':<13}{'set':<7}{'present':<10}"
                    f"{len(self.world_files):>7}{self.world_sizes():>12}  *{WORLD_SUFFIX}"
                )
                for path in self.world_files:
                    try:
                        size = path.stat().st_size
                    except OSError:
                        size = 0
                    lines.append(f"    {path.name:<20}{size:>10} bytes")
            elif self.worlds_dir is not None:
                lines.append(
                    f"  {WORLDS_DIR_NAME + '/*' + WORLD_SUFFIX:<13}{'set':<7}"
                    f"{'MISSING':<10}  required"
                )
        lines.append("")
        lines.append(self.verdict())
        return "\n".join(lines)


def _children(directory: Path) -> list[Path]:
    try:
        return list(directory.iterdir())
    except OSError:
        return []


def _child(directory: Path, name: str) -> Path | None:
    """Find a child by case-insensitive name (first match, deterministic order)."""
    wanted = name.casefold()
    for child in sorted(_children(directory), key=lambda p: p.name.casefold()):
        if child.name.casefold() == wanted:
            return child
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


def _world_files(worlds_dir: Path | None) -> tuple[Path, ...]:
    if worlds_dir is None:
        return ()
    found = [
        path
        for path in _children(worlds_dir)
        if path.is_file() and path.suffix.casefold() == WORLD_SUFFIX.casefold()
    ]
    return tuple(sorted(found, key=lambda p: p.name.casefold()))


def _missing_required(root: Path) -> list[str]:
    """Required entries absent under ``root`` (cheap, for nesting detection)."""
    missing: list[str] = []
    exe = _child(root, REQUIRED_FILES[0])
    if exe is None or not exe.is_file():
        missing.append(REQUIRED_FILES[0])
    worlds = _child(root, WORLDS_DIR_NAME)
    if worlds is None or not worlds.is_dir():
        missing.append(WORLDS_DIR_NAME + "/")
    elif not _world_files(worlds):
        missing.append(f"{WORLDS_DIR_NAME}/*{WORLD_SUFFIX}")
    return missing


def check_install(path: str | Path) -> InstallManifest:
    """Describe ``path`` as an unpacked install, resolving one level of nesting."""
    requested = Path(path).expanduser()
    if not requested.is_dir():
        return InstallManifest(
            requested_root=requested,
            root=requested,
            entries=(),
            world_files=(),
            worlds_dir=None,
            notes=(f"not a directory: {requested}",),
        )

    root = requested
    notes: list[str] = []
    if _missing_required(root):
        candidates = [
            child
            for child in sorted(_children(root), key=lambda p: p.name.casefold())
            if child.is_dir() and not _missing_required(child)
        ]
        if len(candidates) == 1:
            root = candidates[0]
            notes.append(
                "install root resolved one level down: "
                f"{root.name}/ (the retail folder was copied inside the directory)"
            )
        elif len(candidates) > 1:
            names = ", ".join(child.name + "/" for child in candidates)
            notes.append(
                f"ambiguous: {len(candidates)} sub-directories look like an install "
                f"({names}); point present at one of them"
            )

    entries: list[ManifestEntry] = []
    worlds_dir: Path | None = None
    for name in REQUIRED_DIRS + EXPECTED_DIRS:
        found = _child(root, name)
        if found is not None and found.is_dir():
            files, size = _dir_stats(found)
            entries.append(
                ManifestEntry(
                    name=name + "/",
                    kind="dir",
                    required=name in REQUIRED_DIRS,
                    present=True,
                    files=files,
                    bytes=size,
                )
            )
            if name == WORLDS_DIR_NAME:
                worlds_dir = found
        else:
            entries.append(
                ManifestEntry(
                    name=name + "/",
                    kind="dir",
                    required=name in REQUIRED_DIRS,
                    present=False,
                )
            )

    for name in REQUIRED_FILES + EXPECTED_FILES:
        found = _child(root, name)
        present = found is not None and found.is_file()
        size = 0
        if present:
            try:
                size = found.stat().st_size
            except OSError:
                pass
        entries.append(
            ManifestEntry(
                name=name,
                kind="file",
                required=name in REQUIRED_FILES,
                present=present,
                bytes=size,
            )
        )

    return InstallManifest(
        requested_root=requested,
        root=root,
        entries=tuple(entries),
        world_files=_world_files(worlds_dir),
        worlds_dir=worlds_dir,
        notes=tuple(notes),
    )


def resolve_world(manifest: InstallManifest, name: str | None = None) -> Path:
    """Pick one world file: ``name`` (case-insensitive, ``.WLD`` optional) or the default.

    The default is :data:`PREFERRED_WORLD` when present (the same start the
    ``slice`` command uses) and the first file otherwise.  A missing ``name``
    raises ``LookupError`` with the available stems, so a typo is actionable.
    """
    if not manifest.world_files:
        raise LookupError(
            f"no *{WORLD_SUFFIX} under {manifest.worlds_dir or manifest.root}"
        )
    if name is None:
        for path in manifest.world_files:
            if path.stem.casefold() == PREFERRED_WORLD.casefold():
                return path
        return manifest.world_files[0]
    wanted = name.casefold()
    if wanted.endswith(WORLD_SUFFIX.casefold()):
        wanted = wanted[: -len(WORLD_SUFFIX)]
    for path in manifest.world_files:
        if path.stem.casefold() == wanted:
            return path
    available = ", ".join(path.stem for path in manifest.world_files)
    raise LookupError(f"world {name!r} not found; available: {available}")


def is_inside_tree(path: str | Path, root: str | Path) -> bool:
    """True when ``path`` is ``root`` or below it (used to refuse writes)."""
    candidate = Path(path).expanduser().resolve()
    anchor = Path(root).expanduser().resolve()
    return candidate == anchor or anchor in candidate.parents
