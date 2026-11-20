"""Clip resolution against a real installation (opt-in, read-only).

Set ``LOMAX_GAME_DIR`` to a folder containing ``LOMAX.EXE`` to run these.  They
decode ``MAIN.WLD``'s ``Hero.WALK`` clip and assert the measured counts; nothing
is written and no game byte is copied into the repository.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lomax_modern import anim_clip, wld

GAME_DIR = os.environ.get("LOMAX_GAME_DIR")

pytestmark = [
    pytest.mark.realgame,
    pytest.mark.skipif(
        not GAME_DIR or not Path(GAME_DIR).is_dir(),
        reason="set LOMAX_GAME_DIR to a Lomax installation to run",
    ),
]


def main_world() -> Path:
    return Path(GAME_DIR or "") / "WORLDS" / "MAIN.WLD"


def test_walk_clip_resolves_to_22_keyframes_20_resolved() -> None:
    path = main_world()
    if not path.is_file():
        pytest.skip("MAIN.WLD not present in this install")
    world = wld.parse_file(path)
    anim = anim_clip.find_animation(world, record_name="Hero", clip_tag="WALK")
    assert anim is not None
    assert anim.frame_count == 22
    assert anim.size_field == 20 + 8 * 22

    frames = anim_clip.resolve_clip(world, record_name="Hero", clip_tag="WALK")
    assert len(frames) == 22
    resolved = [f for f in frames if f.resolved]
    assert len(resolved) == 20
    unresolved_sprites = sorted({f.sprite_index for f in frames if not f.resolved})
    print(f"resolved={len(resolved)}/{len(frames)} unresolved_sprites={unresolved_sprites}")
    # The two contact frames reference the shared hero pose (sprite byte 169),
    # which is not in MAIN.WLD's ANIM bank (0..147) — a documented gap, Q34.
    assert unresolved_sprites == [169]

    # Every resolved frame decodes to a valid, non-degenerate sprite.
    for frame in resolved:
        assert frame.pixels is not None
        assert frame.pixels.width > 0 and frame.pixels.height > 0


def test_walk_clip_resolves_to_10_composited_poses() -> None:
    path = main_world()
    if not path.is_file():
        pytest.skip("MAIN.WLD not present in this install")
    world = wld.parse_file(path)
    poses = anim_clip.resolve_poses(world, record_name="Hero", clip_tag="WALK")
    # 22 keyframes = 10 stride poses x 2 layers (sprite 34 legs + 33 body) plus
    # 2 contact keyframes (sprite 169, absent).  The contact step is dropped, so
    # exactly 10 composited poses remain, one per stride step 1..10.
    assert [p.pose for p in poses] == list(range(1, 11))
    assert len(poses) == 10
    # All poses share one canvas (the clip's union content bounding box).
    widths = {p.pixels.width for p in poses}
    heights = {p.pixels.height for p in poses}
    assert len(widths) == 1 and len(heights) == 1
    width, height = poses[0].pixels.width, poses[0].pixels.height
    assert width > 0 and height > 0
    # Every pose carries real opaque pixels (a whole character, not a fragment).
    for pose in poses:
        assert any(pose.pixels.indices)


def test_walk_clip_poses_are_renderable() -> None:
    path = main_world()
    if not path.is_file():
        pytest.skip("MAIN.WLD not present in this install")
    world = wld.parse_file(path)
    poses = anim_clip.resolve_poses(world, record_name="Hero", clip_tag="WALK")
    from lomax_modern import art

    head = next(c for c in world.chunks if c.tag == "HEAD")
    palette = art.head_palette(head, art.DEFAULT_PALETTE_SLOT)
    width, height, buffers = anim_clip.pose_rgba_frames(poses, palette)
    strip = anim_clip.pose_strip(poses, palette)
    assert len(buffers) == 10
    assert width > 0 and height > 0
    assert strip.width >= width * 10
    assert any(pixels for pixels in buffers)
