"""``Level.backdrops``: backdrop planes are decoded, never drawn (synthetic worlds)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lomax_modern import art
from lomax_modern.engine.level import BackdropPlane, load_level
from tests.fixtures.synth import multi_plane_world


@pytest.fixture
def world(tmp_path: Path) -> Path:
    path = tmp_path / "W.WLD"
    # plane 0: Other; plane 1: ScrollMap, Other, Parallax, scrollmap;
    # plane 2: empty; plane 3: Parallax
    path.write_bytes(multi_plane_world([[3], [0, 3, 1, 2], [], [1]]))
    return path


def test_default_has_no_backdrops(world: Path) -> None:
    assert load_level(world).backdrops == ()


def test_backdrop_planes_carry_gnmy_and_scroll(world: Path) -> None:
    level = load_level(world, playfield=0, backdrop_planes=(1, 3))
    assert [b.plane for b in level.backdrops] == [1, 3]
    one, three = level.backdrops
    assert isinstance(one, BackdropPlane)
    assert [e.name for e in one.gnmy] == ["ScrollMap", "Other", "Parallax", "scrollmap"]
    # case-sensitive: the lower-case name is not a scroll placement
    assert [e.name for e in one.scroll] == ["ScrollMap", "Parallax"]
    assert [e.name for e in three.scroll] == ["Parallax"]
    assert [e.name for e in level.gnmy] == ["Other"]  # playfield unchanged


def test_empty_backdrop_plane(world: Path) -> None:
    (b,) = load_level(world, backdrop_planes=(2,)).backdrops
    assert b.gnmy == () and b.scroll == ()


def test_out_of_range_backdrop_plane(world: Path) -> None:
    with pytest.raises(art.ArtError):
        load_level(world, backdrop_planes=(4,))
    with pytest.raises(art.ArtError):
        load_level(world, backdrop_planes=(-1,))
