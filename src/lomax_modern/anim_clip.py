"""Resolve one ``NMY`` animation clip (e.g. ``Hero.WALK``) to per-pose pixels.

This is the "one clip, proven" layer for the animation spike.  It maps each
keyframe of a named ``NMY`` animation to the ``ANIM`` sprite it references,
decodes that sprite's pixels, and composites the clip's stride poses, so a
caller can render a whole walking character without re-deriving the mapping.

The mapping is settled **[V]** against the retail binary and the retail install:
a keyframe's first byte is **1-based** — it is the ``ANIM`` sprite-table slot
``type_index + 1``.  The ``ANIM`` reader bumps the chunk's ``type_index``
(``inc edi`` at VA ``0x414A9A``) before storing the chunk's frame array at
``sprite_table[bank | index]`` (``0x414B54``), and the frame resolver looks a
keyframe's sprite byte up in that same table with **no** offset before its NULL
check (VA ``0x4163E4``–``0x4163FC``, byte 0 → NULL at ``0x4163CB``).  So
``sprite byte S`` references ``type_index S - 1`` and byte 0 draws nothing
(:func:`chunk_index_for_sprite`, :func:`sprite_for`).  The second byte is that
chunk's own frame selector (``step - 1``, wrapped into the chunk's frame range —
see :func:`frame_for_step`); ``step == 0`` also draws nothing (``0x4163D3``).
The remaining three words are the signed draw offsets ``dx``/``dy`` and the
per-frame flag word ``flags``.  A stride pose is the keyframes that share one
``step`` value — for ``Hero.WALK`` a **base** layer (sprite 33 → ``type_index``
32, 36×46, the whole character) and a smaller **overlay** layer (sprite 34 →
``type_index`` 33, 18×23) — and :func:`resolve_poses` composites them at their
recorded offsets, painting the base first and the overlay on top.  The game's
vertical axis points up (the sprite decompressor at VA ``0x415E30`` negates the
frame height), so a layer draws at screen position ``(dx, -dy)``, which is what
puts the head above the body.  Evidence: ``docs/file-formats.md`` §2.6.1, and a
``Hero.WALK`` render whose 20 resolvable keyframes all show one coherent
walking character.

Nothing here reads game bytes into the repository: every decode happens at run
time against the caller's own ``.WLD``.
"""

from __future__ import annotations

from collections.abc import Mapping
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


#: The ``NMY`` keyframe's sprite byte is **1-based**: it is the slot the ``ANIM``
#: reader stored the chunk in, ``type_index + 1``.  The reader bumps the index
#: (``inc edi`` at VA ``0x414A9A``) before the store at ``0x414B54``, and the
#: frame resolver reads the raw byte into that same table with no offset
#: (``0x4163FC``), so ``sprite byte S`` selects ``type_index S - 1``.  [V]
#: ``docs/file-formats.md`` §2.6.1.
SPRITE_BYTE_BIAS = 1


def chunk_index_for_sprite(sprite_byte: int) -> int | None:
    """The ``ANIM`` ``type_index`` a keyframe's 1-based sprite byte selects.

    Returns ``None`` for sprite byte 0, the "no sprite" sentinel the resolver
    turns into NULL (VA ``0x4163CB``) — there is no ``type_index -1``.
    """
    if sprite_byte < SPRITE_BYTE_BIAS:
        return None
    return sprite_byte - SPRITE_BYTE_BIAS


def sprite_for(
    sprites: Mapping[int, AnimDecode], sprite_byte: int
) -> AnimDecode | None:
    """Look one keyframe's sprite byte up in :func:`sprite_map` (1-based, [V])."""
    index = chunk_index_for_sprite(sprite_byte)
    return sprites.get(index) if index is not None else None


@dataclass(frozen=True)
class ClipFrame:
    """One keyframe of an ``NMY`` animation, resolved to pixel indices.

    ``sprite_index`` is the keyframe's raw sprite byte (1-based: it selects the
    ``ANIM`` ``type_index`` ``sprite_index - 1``, see :func:`sprite_for`);
    ``sub_frame`` is the ``ANIM`` chunk's own frame selected by ``step - 1``.
    ``dx``/``dy`` are the signed draw offsets and ``flags`` the flag word.  When
    the sprite byte does not resolve to an ``ANIM`` chunk, or the keyframe's
    ``step`` is 0 (the resolver draws nothing there), ``resolved`` is ``False``
    and ``pixels`` is ``None`` — the gap is kept visible, never silently dropped.
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

    ``pose`` is the keyframe's second byte (``step``, 1..10 for ``WALK``).  A
    stride pose is *two* keyframes that share a ``step`` value — a **base**
    layer (sprite byte 33 → ``type_index`` 32, the whole character) and a
    smaller **overlay** layer (sprite byte 34 → ``type_index`` 33) — and
    ``pixels`` is the composite of those layers
    painted at their recorded signed draw offsets into a canvas sized to the
    clip's union content bounding box.  The base (the largest layer) is painted
    first and any overlay on top.  Every pose therefore shares one canvas, so
    the clip can be blitted pose to pose without per-pose jitter.  Index 0 is
    transparent.  A ``step`` whose layers do not all resolve (the contact pose,
    sprite byte 169) is dropped rather than half-drawn.
    """

    pose: int
    pixels: AnimPixels


@dataclass(frozen=True)
class BodyPose:
    """One step of a clip drawn from its **whole-body layer** alone.

    ``sprite_index``/``sub_frame`` name the layer this pose came from, so a
    caller can report which sprite a supplied frame is (and a test can pin it).
    Unlike :class:`PoseFrame` the canvas is the layer's own frame, not a union
    composite: the protagonist is one sprite in RUN, not a stack of body parts.
    """

    step: int
    sprite_index: int
    sub_frame: int
    dx: int
    dy: int
    pixels: AnimPixels


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


def frame_for_step(step: int, frame_count: int) -> int | None:
    """The ``ANIM`` sub-frame a keyframe's ``step`` selects, wrapping.

    ``step`` is 1-based (``step - 1`` indexes the chunk on the retail data:
    ``Hero.WALK``'s 10 steps over sprite byte 33's (``type_index`` 32) 10
    frames).  ``step == 0`` on its own **draws nothing** — the frame resolver
    returns NULL there (VA ``0x4163D3``) — so this returns ``None`` rather than
    clamping or wrapping ``-1`` into a real frame; so does a chunk with no
    frames.

    A clip may declare *more* steps than the referenced chunk has frames — 45 of
    691 retail clips do (``Hero.STA2``: 10 steps over ``type_index`` 27's 7
    frames) — so the index wraps modulo the frame count instead of clamping onto
    the last frame.  ``WALK`` (10/10) and ``RUN`` (12/12) are exact and never
    wrap.  Which rule the original uses is unresolved (Q36), so the wrap is a
    chosen convention, not a recovered one **[H]**.
    """
    if step <= 0 or frame_count <= 0:
        return None
    return (step - 1) % frame_count


def resolve_clip(
    world: wld.World, *, record_name: str, clip_tag: str
) -> tuple[ClipFrame, ...]:
    """Resolve ``record_name.clip_tag`` to one :class:`ClipFrame` per keyframe.

    The keyframe's sprite byte selects the ``ANIM`` chunk (1-based, see
    :func:`sprite_for`) and ``step - 1`` (the second byte, wrapped into the
    chunk's frame range by :func:`frame_for_step`) selects that chunk's own
    frame.  A keyframe whose sprite byte is outside the world's ``ANIM`` bank, or
    whose ``step`` is 0, is returned with ``resolved=False`` and ``pixels=None``.
    """
    anim = find_animation(world, record_name=record_name, clip_tag=clip_tag)
    if anim is None:
        return ()
    sprites = sprite_map(world)
    frames: list[ClipFrame] = []
    for index, (sprite, step, w2, w3, w4) in enumerate(anim.frames):
        dx, dy = _signed(w2), _signed(w3)
        chunk = sprite_for(sprites, sprite)
        sub = frame_for_step(step, chunk.frame_count) if chunk is not None else None
        if chunk is None or sub is None:
            frames.append(ClipFrame(index, sprite, 0, dx, dy, w4, False))
            continue
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

    This is the "size" used to pick a pose's **base** sprite: the largest layer
    is the base (the whole character), and any smaller layer is an overlay
    (e.g. the head) painted on top at its own offset.
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
    storing it), so a layer's screen position is ``(dx, -dy)`` — which is what
    makes the head sit *above* the body.  Layers are painted base-first: the
    largest layer (by content area) is the whole character and any smaller
    layer paints on top of it, so the smaller sprite's detail is never buried.

    Every pose is painted into the *same* canvas, sized to the clip's union
    content bounding box, so the whole clip can be blitted pose to pose with a
    single anchor and no per-pose jitter.  A ``step`` whose layers do not all
    resolve (the contact pose, sprite byte 169) is dropped, never half-drawn —
    and so is ``step`` 0, where the resolver draws nothing at all (VA
    ``0x4163D3``).
    """
    anim = find_animation(world, record_name=record_name, clip_tag=clip_tag)
    if anim is None:
        return ()
    sprites = sprite_map(world)
    by_step: dict[int, list[tuple[int, int, AnimPixels]]] = {}
    dropped: set[int] = set()
    for sprite, step, w2, w3, _w4 in anim.frames:
        dx, dy = _signed(w2), _signed(w3)
        chunk = sprite_for(sprites, sprite)
        if chunk is None:
            dropped.add(step)  # contact pose (sprite 169): the step is incomplete
            continue
        sub = frame_for_step(step, chunk.frame_count)
        if sub is None:
            dropped.add(step)  # step 0: the resolver draws nothing
            continue
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
        # Base first, overlays last: the largest layer is the whole character
        # (the base) and any smaller layer (the head) paints on top of it at
        # its own offset, so the smaller sprite's detail is never buried under
        # the base.
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


def resolve_body_poses(
    world: wld.World, *, record_name: str, clip_tag: str
) -> tuple[BodyPose, ...]:
    """Resolve a clip to one **whole-body sprite** per stride ``step``.

    This is the "one character, one sprite" reading that ``engine.render_tiles``
    draws the moving player from.  ``Hero.RUN`` has 26 keyframes over 12 steps:
    per step a **whole-body** layer (sprite byte **23** → ``type_index`` 22,
    60×34 — head, torso, arms and legs in one image) plus a much smaller
    companion (sprite byte **24** → ``type_index`` 23, 26×13–34×14).  The body
    layer is the one with the larger content bounding box, so the selection is a
    measurement (:func:`_content_area`), not a hard-coded id.

    The companion layer is **not** painted here.  Measured over RUN's 12 steps
    at the recorded ``(dx, -dy)``, its opaque pixels land on the body layer's
    pixels **39–97 %** of the time — it is a genuine overlay on the character
    (a cape or a limb), not a detached fragment, which is what the 0-based read
    of the byte made it look like.  This function exists for the engine's
    "whole-body sprite per step" path; :func:`resolve_poses` paints the layers,
    and that is the reading the clip strips use.

    Steps whose layers do not all resolve (the shared contact pose, sprite
    byte 169) are dropped, as is ``step`` 0 — exactly as in :func:`resolve_poses`
    — so every pose returned is a complete frame.
    """
    anim = find_animation(world, record_name=record_name, clip_tag=clip_tag)
    if anim is None:
        return ()
    sprites = sprite_map(world)
    layers: dict[int, list[tuple[int, int, int, int, AnimPixels]]] = {}
    dropped: set[int] = set()
    for sprite, step, w2, w3, _w4 in anim.frames:
        dx, dy = _signed(w2), _signed(w3)
        chunk = sprite_for(sprites, sprite)
        if chunk is None:
            dropped.add(step)
            continue
        sub = frame_for_step(step, chunk.frame_count)
        if sub is None:
            dropped.add(step)  # step 0: the resolver draws nothing
            continue
        pixels = decode_anim_pixels(chunk, sub)
        if pixels is None:
            dropped.add(step)
            continue
        layers.setdefault(step, []).append((sprite, sub, dx, dy, pixels))

    poses: list[BodyPose] = []
    for step in sorted(layers):
        if step in dropped:
            continue
        sprite, sub, dx, dy, pixels = max(
            layers[step], key=lambda layer: _content_area(layer[4])
        )
        poses.append(BodyPose(step, sprite, sub, dx, dy, pixels))
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
