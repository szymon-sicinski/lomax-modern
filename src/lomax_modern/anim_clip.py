"""Resolve one ``NMY`` animation clip (e.g. ``Hero.WALK``) to per-frame pixels.

This is the "one clip, proven" layer for the animation spike.  It maps each
keyframe of a named ``NMY`` animation to the ``ANIM`` sprite it references and
decodes that sprite's pixels, so a caller can render the clip frame by frame
without re-deriving the mapping every time.

The mapping is the one ``docs/file-formats.md`` §2.5/§2.6 already grade: the
keyframe's first byte is the referenced ``ANIM`` ``type_index`` **[V]** (3,124/3,156
same-world resolutions on the retail install), and the second byte is that
chunk's own frame selector (``step - 1``, clamped into the chunk's frame range).
The remaining three words are carried verbatim as the signed draw offsets
``dx``/``dy`` and the per-frame flag word ``flags``.

Nothing here reads game bytes into the repository: every decode happens at run
time against the caller's own ``.WLD``.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import art, wld
from .anim_nmy import (
    AnimDecode,
    AnimPixels,
    anim_tag_name,
    decode_anim,
    decode_anim_pixels,
    decode_nmy,
)


def _signed(word: int) -> int:
    """A little-endian ``u16`` read back as a signed value."""
    return word - 0x10000 if word & 0x8000 else word


@dataclass(frozen=True)
class ClipFrame:
    """One keyframe of an ``NMY`` animation, resolved to pixel indices.

    ``sprite_index`` is the keyframe's sprite byte (the ``ANIM`` ``type_index``);
    ``sub_frame`` is the ``ANIM`` chunk's own frame selected by ``step - 1``.
    ``dx``/``dy`` are the signed draw offsets and ``flags`` the flag word.  When
    the sprite byte does not resolve to an ``ANIM`` chunk, ``resolved`` is
    ``False`` and ``pixels`` is ``None`` — the gap is kept visible, never
    silently dropped.
    """

    keyframe: int
    sprite_index: int
    sub_frame: int
    dx: int
    dy: int
    flags: int
    resolved: bool
    pixels: AnimPixels | None = None


def sprite_map(world: wld.World) -> dict[int, AnimDecode]:
    """Map each ``ANIM`` chunk's ``type_index`` to its decoded chunk."""
    result: dict[int, AnimDecode] = {}
    for chunk in world.chunks:
        if chunk.tag != "ANIM":
            continue
        decoded = decode_anim(chunk.payload)
        if decoded is not None:
            result[decoded.type_index] = decoded
    return result


def find_animation(
    world: wld.World, *, record_name: str, clip_tag: str
):
    """Return the ``NmyAnim`` named ``clip_tag`` in the ``NMY`` record ``record_name``.

    ``clip_tag`` is matched on the forward-ASCII tag name (trailing spaces from
    the 4-byte tag field are stripped), so ``"WALK"`` matches the tag the game
    stores byte-swapped as ``KLAW``.  Returns ``None`` when the world, record or
    clip is absent.
    """
    nmy = next((c for c in world.chunks if c.tag == "NMY"), None)
    if nmy is None:
        return None
    result = decode_nmy(nmy.payload)
    if result is None:
        return None
    records, _ = result
    record = next((r for r in records if r.name == record_name), None)
    if record is None:
        return None
    return next(
        (a for a in record.anims if anim_tag_name(a.tag).strip() == clip_tag),
        None,
    )


def resolve_clip(
    world: wld.World, *, record_name: str, clip_tag: str
) -> tuple[ClipFrame, ...]:
    """Resolve ``record_name.clip_tag`` to one :class:`ClipFrame` per keyframe.

    The keyframe's sprite byte selects the ``ANIM`` chunk and ``step - 1`` (the
    second byte, clamped into the chunk's frame range) selects that chunk's own
    frame.  A keyframe whose sprite byte is outside the world's ``ANIM`` bank is
    returned with ``resolved=False`` and ``pixels=None``.
    """
    anim = find_animation(world, record_name=record_name, clip_tag=clip_tag)
    if anim is None:
        return ()
    sprites = sprite_map(world)
    frames: list[ClipFrame] = []
    for index, (sprite, step, w2, w3, w4) in enumerate(anim.frames):
        dx, dy = _signed(w2), _signed(w3)
        chunk = sprites.get(sprite)
        if chunk is None:
            frames.append(ClipFrame(index, sprite, step, dx, dy, w4, False))
            continue
        if chunk.frame_count <= 0:
            sub = 0
        else:
            sub = max(0, min(step - 1, chunk.frame_count - 1))
        pixels = decode_anim_pixels(chunk, sub)
        frames.append(ClipFrame(index, sprite, sub, dx, dy, w4, True, pixels))
    return tuple(frames)


def mirrored(pixels: AnimPixels) -> AnimPixels:
    """A horizontally mirrored copy of one decoded frame."""
    mirrored_indices = tuple(
        pixels.at(pixels.width - 1 - x, y)
        for y in range(pixels.height)
        for x in range(pixels.width)
    )
    return AnimPixels(pixels.width, pixels.height, mirrored_indices)


def clip_strip(
    frames: tuple[ClipFrame, ...],
    palette: art.Palette,
    *,
    background: tuple[int, int, int, int] = (0, 0, 0, 0),
    padding: int = 1,
) -> art.Image:
    """Composite the clip's resolved frames side by side into one image.

    Unresolved frames contribute an empty (background) cell so the strip keeps
    one column per keyframe and the gap is visible rather than collapsed.
    """
    resolved = [f for f in frames if f.resolved and f.pixels is not None]
    if not resolved:
        raise art.ArtError("clip has no resolvable frames to draw")
    width = max(f.pixels.width for f in resolved)
    height = max(f.pixels.height for f in resolved)
    cell = width + padding
    canvas = art._Canvas(cell * len(frames), height, background)
    for n, frame in enumerate(frames):
        if frame.pixels is None:
            continue
        pixels = frame.pixels
        x0 = n * cell + (width - pixels.width) // 2
        y0 = (height - pixels.height) // 2
        for y in range(pixels.height):
            for x in range(pixels.width):
                index = pixels.at(x, y)
                if index == 0:
                    continue
                canvas.set(x0 + x, y0 + y, (*palette.rgb(index), 255))
    return canvas.image()


def clip_rgba_frames(
    frames: tuple[ClipFrame, ...], palette: art.Palette
) -> tuple[int, int, list[bytes]]:
    """Normalise each keyframe to a common-size RGBA8888 buffer.

    Every frame (including an unresolved one) becomes one buffer of the clip's
    largest frame dimensions, centred, with index 0 transparent — so the list
    has one entry per keyframe and the buffers can be written as individual PNGs
    or fed straight to :func:`lomax_modern.gif.write`.
    """
    resolved = [f for f in frames if f.resolved and f.pixels is not None]
    if not resolved:
        raise art.ArtError("clip has no resolvable frames to draw")
    width = max(f.pixels.width for f in resolved)
    height = max(f.pixels.height for f in resolved)
    out: list[bytes] = []
    for frame in frames:
        buffer = bytearray(width * height * 4)
        if frame.pixels is not None:
            pixels = frame.pixels
            x0 = (width - pixels.width) // 2
            y0 = (height - pixels.height) // 2
            for y in range(pixels.height):
                for x in range(pixels.width):
                    index = pixels.at(x, y)
                    if index == 0:
                        continue
                    r, g, b = palette.rgb(index)
                    offset = ((y0 + y) * width + (x0 + x)) * 4
                    buffer[offset : offset + 3] = bytes((r, g, b))
                    buffer[offset + 3] = 255
        out.append(bytes(buffer))
    return width, height, out
