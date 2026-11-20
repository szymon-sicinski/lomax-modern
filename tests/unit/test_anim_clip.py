"""Unit tests for clip resolution and rendering (synthetic fixtures only)."""

from __future__ import annotations

import struct

from lomax_modern import anim_clip, art, wld
from lomax_modern.anim_nmy import decode_anim_pixels
from tests.fixtures.synth import anim_payload, build_container, head_payload


def _nmy_clip_payload(
    record_name: str,
    clip_tag: str,
    keyframes: tuple[tuple[int, int, int, int, int], ...],
    *,
    trailer: int = 2,
) -> bytes:
    """An ``NMY`` payload with one record holding one animation of ``keyframes``.

    ``keyframes`` entries are ``(sprite, step, dx, dy, flags)``; ``dx``/``dy``
    are signed and stored as little-endian ``u16``.  ``clip_tag`` is stored
    byte-swapped, exactly as the game writes its 4-byte animation tags.
    """
    out = bytearray()
    name_field = record_name.encode("ascii") + b"\x00"
    name_size = len(name_field)
    name_size += -name_size % 4
    out += struct.pack("<H", name_size)
    out += name_field
    out += b"\x00" * (name_size - len(name_field))
    out += struct.pack("<H", 0x0010)  # W_A
    out += struct.pack("<H", 1)  # W_B = 1 animation
    out += b"\x00" * 2  # gap1
    tag_bytes = clip_tag.encode("ascii").ljust(4, b" ")
    out += struct.pack("<I", struct.unpack("<I", tag_bytes[::-1])[0])  # byte-swapped
    out += struct.pack("<I", 20 + 8 * len(keyframes))  # size field
    out += struct.pack("<H", len(keyframes))  # count2
    out += b"\x00" * 18  # 9 x u16 params
    for sprite, step, dx, dy, flags in keyframes:
        out += struct.pack("<BBHHH", sprite, step, dx & 0xFFFF, dy & 0xFFFF, flags)
    out += b"\x00" * 2  # u16 terminator
    out += b"\x00" * trailer
    return bytes(out)


def _world_with_clip(
    keyframes: tuple[tuple[int, int, int, int, int], ...],
    *,
    sprites: dict[int, bytes] | None = None,
    head: bytes | None = None,
) -> wld.World:
    """A synthetic world holding ``Hero.WALK`` plus one ANIM chunk per sprite.

    ``sprites`` maps an ANIM ``type_index`` to a ready-made ``anim_payload``.
    By default sprite 0 is one raw 8x8 frame and sprite 1 is a packed 4x4 frame.
    ``head`` overrides the ``HEAD`` payload (e.g. to supply a palette).
    """
    if sprites is None:
        sprites = {
            0: anim_payload(frame_count=1, packed=False, width=8, height=8, type_index=0),
            1: anim_payload(
                frame_count=2, packed=True, width=4, height=4, type_index=1
            ),
        }
    chunks: list[tuple[str, bytes]] = [
        ("WRLD", b"PS-X" + b"\x00" * 4),
        ("NMY", _nmy_clip_payload("Hero", "WALK", keyframes)),
        ("HEAD", head if head is not None else head_payload(16, 16, endian=">")),
    ]
    for type_index, payload in sprites.items():
        chunks.append(("ANIM", payload))
    chunks.append(("END", b""))
    return wld.parse(build_container(chunks, endian=">"))


def test_resolve_clip_maps_sprite_step_offsets_and_flags() -> None:
    """A keyframe's 8 bytes map to sprite type_index, step-1, signed dx/dy, flags."""
    world = _world_with_clip(
        (
            (0, 1, 6, -1, 2),  # sprite 0, sub-frame 0, dx +6, dy -1, flags 2
            (1, 2, -6, -57, 0x80),  # sprite 1, sub-frame 1, dx -6, dy -57
        )
    )
    frames = anim_clip.resolve_clip(world, record_name="Hero", clip_tag="WALK")
    assert len(frames) == 2
    first, second = frames
    assert first.sprite_index == 0
    assert first.sub_frame == 0
    assert (first.dx, first.dy, first.flags) == (6, -1, 2)
    assert first.resolved and first.pixels is not None
    assert (first.pixels.width, first.pixels.height) == (8, 8)

    assert second.sprite_index == 1
    assert second.sub_frame == 1  # step 2 -> the chunk's second frame
    assert (second.dx, second.dy, second.flags) == (-6, -57, 0x80)
    assert second.resolved and second.pixels is not None
    assert (second.pixels.width, second.pixels.height) == (4, 4)


def test_resolve_clip_marks_unresolved_sprite_as_gap() -> None:
    """A sprite byte outside the ANIM bank stays visible, not silently dropped."""
    world = _world_with_clip(((99, 1, 0, 0, 0),))
    frames = anim_clip.resolve_clip(world, record_name="Hero", clip_tag="WALK")
    assert len(frames) == 1
    assert frames[0].resolved is False
    assert frames[0].pixels is None
    assert frames[0].sprite_index == 99


def test_resolve_clip_missing_record_or_clip_is_empty() -> None:
    world = _world_with_clip(((0, 1, 0, 0, 0),))
    assert anim_clip.resolve_clip(world, record_name="Nobody", clip_tag="WALK") == ()
    assert anim_clip.resolve_clip(world, record_name="Hero", clip_tag="RUN") == ()


def test_mirrored_is_an_exact_horizontal_flip() -> None:
    world = _world_with_clip(((0, 1, 0, 0, 0),))
    frames = anim_clip.resolve_clip(world, record_name="Hero", clip_tag="WALK")
    pixels = frames[0].pixels
    flipped = anim_clip.mirrored(pixels)
    assert flipped is not pixels
    for y in range(pixels.height):
        for x in range(pixels.width):
            assert flipped.at(x, y) == pixels.at(pixels.width - 1 - x, y)


def test_clip_rgba_frames_is_one_buffer_per_keyframe_and_deterministic() -> None:
    # A palette with distinct colours at indices 5 and 7, and two sprites that
    # use one or the other, so the buffers can differ.
    palette_words = [0] * 256
    palette_words[5] = 0x7FFF  # white
    palette_words[7] = 0x001F  # red
    world = _world_with_clip(
        ((0, 1, 0, 0, 0), (1, 1, 0, 0, 0), (0, 1, 0, 0, 0)),
        sprites={
            0: anim_payload(
                frame_count=1, packed=False, width=8, height=8,
                type_index=0, pixels=b"\x05" + b"\x00" * 63,
            ),
            1: anim_payload(
                frame_count=1, packed=False, width=8, height=8,
                type_index=1, pixels=b"\x07" + b"\x00" * 63,
            ),
        },
        head=head_payload(16, 16, endian=">", palettes=[[0] * 256, palette_words]),
    )
    frames = anim_clip.resolve_clip(world, record_name="Hero", clip_tag="WALK")
    palette = art.head_palette(
        next(c for c in world.chunks if c.tag == "HEAD"), art.DEFAULT_PALETTE_SLOT
    )
    width, height, buffers = anim_clip.clip_rgba_frames(frames, palette)
    # One buffer per keyframe, all the same (max) size, deterministically.
    assert len(buffers) == 3
    assert width == 8 and height == 8
    assert all(len(b) == width * height * 4 for b in buffers)
    assert buffers[0] == buffers[2]
    assert buffers[0] != buffers[1]  # index 5 (white) vs index 7 (red)


def test_clip_strip_has_one_cell_per_keyframe() -> None:
    world = _world_with_clip(((0, 1, 0, 0, 0), (99, 1, 0, 0, 0)))
    frames = anim_clip.resolve_clip(world, record_name="Hero", clip_tag="WALK")
    palette = art.head_palette(
        next(c for c in world.chunks if c.tag == "HEAD"), art.DEFAULT_PALETTE_SLOT
    )
    strip = anim_clip.clip_strip(frames, palette)
    # Two columns: the resolved 8x8 cell plus the blank unresolved cell.
    assert strip.width == (8 + 1) * 2
    assert strip.height == 8


def test_four_bit_fixture_decodes_deterministically_through_the_clip() -> None:
    """The 4-bit nibble order survives a clip-level decode (low nibble first)."""
    # A packed 4-bit frame: byte 0x12 -> pixel 0 = 0x2 (low), pixel 1 = 0x1 (high).
    data = bytes([0x12, 0x34])
    payload = anim_payload(
        frame_count=1, packed=True, width=4, height=1, type_index=7, pixels=data
    )
    world = _world_with_clip(((7, 1, 0, 0, 0),), sprites={7: payload})
    frames = anim_clip.resolve_clip(world, record_name="Hero", clip_tag="WALK")
    assert frames[0].pixels is not None
    assert frames[0].pixels.indices == (2, 1, 4, 3)
