"""Resolve one ``NMY`` animation clip (e.g. ``Hero.WALK``) to per-pose pixels.

This is the "one clip, proven" layer for the animation spike.  It maps each
keyframe of a named ``NMY`` animation to the ``ANIM`` sprite it references,
decodes that sprite's pixels, and composites the clip's stride poses, so a
caller can render a whole walking character without re-deriving the mapping.

The mapping is settled **[V]** against the retail install and a ground-truth
screenshot: a keyframe's first byte is the referenced ``ANIM`` ``type_index``
directly (0-based).  ``Hero.STA1``'s first keyframe byte 28 resolves to the
type_index 28 chunk (54×41) and matches the retail screenshot of the running
character pose-for-pose, so the sprite byte is *not* ``type_index + 1``.  The
second byte is that chunk's own frame selector (``step - 1``, clamped into the
chunk's frame range); the remaining three words are the signed draw offsets
``dx``/``dy`` and the per-frame flag word ``flags`` (bit ``0x80`` = last
keyframe of a pose run).

A stride pose is the keyframes that share one ``step`` value.  The core clips
each pair a full-body base sprite with a small overlay: ``RUN`` = sprite 24
(54×57 body) + 23 (26×13), ``STA1`` = 28 (54×41) + 27 (14×23), ``SPIN`` = 26
(44×49) + 25 (30×14), ``TUMB`` = 44 (58×54) + 43 (28×9).  ``Hero.WALK`` is the
anomaly — its two sprites 33 (18×23) and 34 (16×17) are both small fragments
and there is no full-body sprite, so no composite of them is a character (Q36,
``docs/file-formats.md`` §2.6.1).  The engine therefore animates the moving
player with ``RUN``, not ``WALK`` (``engine.level.PLAYER_RUN_ANIM``).

:func:`resolve_poses` composites each pose's layers at their recorded offsets,
painting the largest layer first.  The game's vertical axis points up (the
sprite decompressor at VA ``0x415E30`` negates the frame height), so a layer
draws at screen position ``(dx, -dy)``.  The contact-pose sprite byte 169 is
absent from every ``.WLD`` bank (Q34) and its steps are dropped, never
half-drawn.

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

    ``sprite_index`` is the keyframe's first byte — the referenced ``ANIM``
    ``type_index`` directly (0-based; see :func:`sprite_map`).
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


@dataclass(frozen=True)
class PoseFrame:
    """One composited stride pose: every layer of one ``step`` at its offset.

    ``pose`` is the keyframe's second byte (``step``).  A stride pose is the
    keyframes that share a ``step`` value — for ``RUN`` a full-body base layer
    (sprite 24, 54×57) and a smaller overlay (sprite 23, 26×13) — and ``pixels``
    is the composite of those layers painted at their recorded signed draw
    offsets into a canvas sized to the clip's union content bounding box.  The
    larger layer is painted first and smaller overlays on top.  Every pose
    therefore shares one canvas, so the clip can be blitted pose to pose without
    per-pose jitter.  Index 0 is transparent.  A ``step`` whose layers do not all
    resolve (the contact pose, sprite byte 169) is dropped rather than
    half-drawn.
    """

    pose: int
    pixels: AnimPixels


def sprite_map(world: wld.World) -> dict[int, AnimDecode]:
    """Map each ``ANIM`` chunk's ``type_index`` to its decoded chunk.

    A keyframe's first byte is the referenced ``ANIM`` ``type_index`` directly
    (0-based) **[V]**: ``Hero.STA1``'s first keyframe byte 28 resolves to the
    type_index 28 chunk (54×41) and matches the retail screenshot of the running
    character, so the sprite byte is *not* ``type_index + 1``.
    """
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

    The keyframe's first byte selects the ``ANIM`` chunk through
    :func:`sprite_map` (sprite byte = ``type_index``, 0-based), and ``step - 1``
    (the second byte, clamped into the chunk's frame range) selects that chunk's
    own frame.  A keyframe whose sprite byte is outside the world's ``ANIM`` bank
    is returned with ``resolved=False`` and ``pixels=None``.
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


def _content_bbox(pixels: AnimPixels) -> tuple[int, int, int, int] | None:
    """The ``(x0, y0, x1, y1)`` of non-transparent pixels, or ``None`` if empty."""
    x0 = y0 = x1 = y1 = None
    for y in range(pixels.height):
        for x in range(pixels.width):
            if pixels.at(x, y) == 0:
                continue
            x0 = x if x0 is None else min(x0, x)
            y0 = y if y0 is None else min(y0, y)
            x1 = x if x1 is None else max(x1, x)
            y1 = y if y1 is None else max(y1, y)
    if x0 is None:
        return None
    return x0, y0, x1, y1


def _content_area(pixels: AnimPixels) -> int:
    """The tight bounding-box area of a layer's non-transparent pixels.

    This is the "size" used to order a pose's layers: the largest layer is
    painted first and smaller layers on top.  For the core clips this makes the
    full-body sprite the base and the small accessory the overlay (``RUN``:
    sprite 24 body under sprite 23).
    """
    box = _content_bbox(pixels)
    if box is None:
        return 0
    x0, y0, x1, y1 = box
    return (x1 - x0 + 1) * (y1 - y0 + 1)


def resolve_poses(
    world: wld.World, *, record_name: str, clip_tag: str
) -> tuple[PoseFrame, ...]:
    """Resolve a clip to one composited pose per stride ``step``, in step order.

    Keyframes are grouped by their second byte (``step``); each group is one
    pose and every keyframe in the group is one sprite layer drawn at its
    recorded signed offsets.  The game stores its vertical axis pointing **up**
    (the sprite decompressor at VA ``0x415E30`` negates the frame height before
    storing it), so a layer's screen position is ``(dx, -dy)``.  Layers are
    painted largest-first: the full-body base is painted first and any smaller
    overlay on top, so the overlay's detail is never buried (``RUN``: sprite 24
    body first, sprite 23 overlay on top).

    Every pose is painted into the *same* canvas, sized to the clip's union
    content bounding box, so the whole clip can be blitted pose to pose with a
    single anchor and no per-pose jitter.  A ``step`` whose layers do not all
    resolve (the contact pose, sprite byte 169) is dropped, never half-drawn.
    """
    anim = find_animation(world, record_name=record_name, clip_tag=clip_tag)
    if anim is None:
        return ()
    sprites = sprite_map(world)
    by_step: dict[int, list[tuple[int, int, AnimPixels]]] = {}
    dropped: set[int] = set()
    for sprite, step, w2, w3, _w4 in anim.frames:
        dx, dy = _signed(w2), _signed(w3)
        chunk = sprites.get(sprite)
        if chunk is None:
            dropped.add(step)  # contact pose (sprite 169): the step is incomplete
            continue
        sub = 0 if chunk.frame_count <= 0 else max(0, min(step - 1, chunk.frame_count - 1))
        pixels = decode_anim_pixels(chunk, sub)
        if pixels is None:
            dropped.add(step)
            continue
        by_step.setdefault(step, []).append((dx, dy, pixels))

    # Union content bounding box in screen coords (x right, y down).
    ux0 = uy0 = ux1 = uy1 = None
    for step, layers in by_step.items():
        if step in dropped:
            continue
        for dx, dy, pixels in layers:
            box = _content_bbox(pixels)
            if box is None:
                continue
            x0, y0, x1, y1 = box
            ux0 = dx + x0 if ux0 is None else min(ux0, dx + x0)
            uy0 = -dy + y0 if uy0 is None else min(uy0, -dy + y0)
            ux1 = dx + x1 if ux1 is None else max(ux1, dx + x1)
            uy1 = -dy + y1 if uy1 is None else max(uy1, -dy + y1)
    if ux0 is None:
        return ()
    width = ux1 - ux0 + 1
    height = uy1 - uy0 + 1

    poses: list[PoseFrame] = []
    for step in sorted(by_step):
        if step in dropped:
            continue
        canvas = [0] * (width * height)
        # Largest layer first: the full-body base is painted first and any
        # smaller overlay on top, so the overlay's detail is never buried
        # under the body (for RUN: sprite 24 body, sprite 23 overlay).
        layers = sorted(
            by_step[step], key=lambda layer: _content_area(layer[2]), reverse=True
        )
        for dx, dy, pixels in layers:
            for y in range(pixels.height):
                for x in range(pixels.width):
                    index = pixels.at(x, y)
                    if index == 0:
                        continue
                    cx = dx - ux0 + x
                    cy = -dy - uy0 + y
                    canvas[cy * width + cx] = index
        poses.append(PoseFrame(step, AnimPixels(width, height, tuple(canvas))))
    return tuple(poses)


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


def pose_rgba_frames(
    poses: tuple[PoseFrame, ...], palette: art.Palette
) -> tuple[int, int, list[bytes]]:
    """Convert each composited pose to a shared-size RGBA8888 buffer.

    Every pose already shares one canvas (see :func:`resolve_poses`), so the
    buffers are the same size and can be written as individual PNGs or fed
    straight to :func:`lomax_modern.gif.write` with no re-centring.
    """
    if not poses:
        raise art.ArtError("clip has no composited poses to draw")
    width = poses[0].pixels.width
    height = poses[0].pixels.height
    out: list[bytes] = []
    for pose in poses:
        buffer = bytearray(width * height * 4)
        for y in range(height):
            for x in range(width):
                index = pose.pixels.at(x, y)
                if index == 0:
                    continue
                r, g, b = palette.rgb(index)
                offset = (y * width + x) * 4
                buffer[offset : offset + 3] = bytes((r, g, b))
                buffer[offset + 3] = 255
        out.append(bytes(buffer))
    return width, height, out


def pose_strip(
    poses: tuple[PoseFrame, ...],
    palette: art.Palette,
    *,
    background: tuple[int, int, int, int] = (0, 0, 0, 0),
    padding: int = 1,
) -> art.Image:
    """Composite the clip's poses side by side into one strip image."""
    if not poses:
        raise art.ArtError("clip has no composited poses to draw")
    width = poses[0].pixels.width
    height = poses[0].pixels.height
    cell = width + padding
    canvas = art._Canvas(cell * len(poses), height, background)
    for n, pose in enumerate(poses):
        x0 = n * cell
        for y in range(height):
            for x in range(width):
                index = pose.pixels.at(x, y)
                if index == 0:
                    continue
                canvas.set(x0 + x, y, (*palette.rgb(index), 255))
    return canvas.image()
