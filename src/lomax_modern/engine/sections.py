"""Resolve ``(section, sub-level)`` to a world and planes, and back.

Specified by ``docs/roadmap/47-first-level-plan.md`` §1.5.  Every function
takes a :class:`~lomax_modern.exe_tables.SectionTable` parsed by the caller;
this module holds no table of its own and does no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..exe_tables import SectionTable

__all__ = ["ResolvedLevel", "find_level", "resolve_level"]

_SUFFIX = ".WLD"


@dataclass(frozen=True)
class ResolvedLevel:
    section: int
    sublevel: int
    world: str  # the world name without its .WLD suffix
    world_file: str  # the name verbatim from the table
    playfield: int  # the lowest active plane number of that sub-level
    backdrop: tuple[int, ...]  # the remaining active planes, ascending


def _check(table: object) -> None:
    if not isinstance(table, SectionTable):
        raise TypeError(f"expected a SectionTable, got {type(table).__name__}")


def _stem(name: str) -> str:
    return name[: -len(_SUFFIX)] if name.upper().endswith(_SUFFIX) else name


def resolve_level(table: SectionTable, section: int, sublevel: int) -> ResolvedLevel:
    _check(table)
    if not 0 <= section < len(table.entries):
        raise IndexError(f"section {section} is outside 0..{len(table.entries) - 1}")
    entry = table.entries[section]
    if not 0 <= sublevel < len(entry.sublevels):
        raise IndexError(
            f"sub-level {sublevel} of section {section} is outside 0..{len(entry.sublevels) - 1}"
        )
    active = sorted(entry.sublevels[sublevel])
    world_file = table.world_names[entry.world_index]
    return ResolvedLevel(
        section=section,
        sublevel=sublevel,
        world=_stem(world_file),
        world_file=world_file,
        playfield=active[0],
        backdrop=tuple(active[1:]),
    )


def find_level(table: SectionTable, world: str, playfield: int) -> tuple[int, int]:
    """First ``(section, sublevel)`` in table order for ``world`` whose lowest
    active plane is ``playfield``."""
    _check(table)
    want = _stem(world).upper()
    for s, entry in enumerate(table.entries):
        if _stem(table.world_names[entry.world_index]).upper() != want:
            continue
        for k, planes in enumerate(entry.sublevels):
            if planes and min(planes) == playfield:
                return s, k
    raise LookupError(
        f"no sub-level of world {world!r} has playfield plane {playfield}"
    )
