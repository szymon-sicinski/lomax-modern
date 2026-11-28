"""FL13: the in-game HUD (``docs/file-formats.md`` §2.12.d, plan 47 §2.2).

The HUD is a data-driven, ordered list of :class:`HudElement` s; each element
owns :class:`HudPart` s (one draw call of §2.12.d each).  Parts are drawn in
the original's call order (``HudPart.order``, 1..9), in **screen** coordinates
of the 320 x 240 view, after everything else.

Sprites are decoded at runtime from the user's own ``MAIN.WLD`` (``Display`` and
``Icons`` ``NMY`` records, through the ``ANIM`` bank, the same keyframe-layer
path as placements).  Nothing here embeds game bytes.

Grades: draw order, origins and clip choices are **[V]** (FL4, the code); the
*meaning* names (face, box, "greyed" weapon icon, digit -> pose mapping) are
**[H]**.  Where the code does not say, the choice is labelled **[H]**.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .. import anim_clip, wld
from ..anim_nmy import anim_tag_name, decode_nmy
from ..renderer import Framebuffer, Palette565

if TYPE_CHECKING:  # pragma: no cover
    from .state import GameState

#: ``NMY`` record names of the two HUD sprite sources [V].
DISPLAY_RECORD = "Display"
ICONS_RECORD = "Icons"

#: Draw-call 9's 4th argument ``0xA0`` (count 0); "greyed" is [H].  Rendered as
#: a halving of each RGB565 channel.
DIM_MASK = 0x7BEF

#: Initial (non-live) values [V from L1's first frame, §2.12.d].
INITIAL_FREED_LEMMINGS = 0
INITIAL_WEAPON_COUNT = 0


@dataclass(frozen=True)
class HudSprite:
    """One keyframe layer: palette indices drawn at ``origin + (dx, dy)``."""

    dx: int
    dy: int
    width: int
    height: int
    indices: tuple[int, ...]


Pose = tuple[HudSprite, ...]


@dataclass(frozen=True)
class HudClip:
    """A clip's poses; each pose is the layer(s) drawn together."""

    record: str
    tag: str
    poses: tuple[Pose, ...]

    @property
    def key(self) -> str:
        return f"{self.record}.{self.tag}"


@dataclass(frozen=True)
class HudPart:
    """One draw call of §2.12.d.

    ``kind`` is ``"digits"`` (``source`` gives the count; units at ``origin``,
    tens at ``tens_origin`` only when non-zero) or ``"sprite"`` (``pose`` gives
    the pose index from the tick).  ``stacked`` draws every keyframe of the clip
    as layers of one pose (the box, three layers [V by hud_boxes]).
    """

    order: int
    clip: str  # "Display.KLEI"
    kind: str
    origin: tuple[int, int]
    tens_origin: tuple[int, int] | None = None
    source: Callable[[GameState], int] | None = None
    pose: Callable[[int], int] = lambda _tick: 0
    dim: bool = False
    stacked: bool = False


@dataclass(frozen=True)
class HudElement:
    """A named HUD element: parts + a value for the report (and live flag)."""

    name: str
    live: bool
    parts: tuple[HudPart, ...]
    value: Callable[[GameState], int]
    #: Grade of the meaning, always ``[H]`` here: positions are [V], names [H].
    grade: str = "[H]"
    note: str = ""


def _spin(tick: int) -> int:
    return (tick >> 2) & 7  # [V] 0x42A601: (+0x80 >> 2) & 7


def _weapon_pose(tick: int) -> int:
    return tick >> 2  # [V] 0x42A6F7: (+0x80 >> 2) mod the clip's poses


def _lives(state: GameState) -> int:
    return max(0, state.lives)


def _coins(state: GameState) -> int:
    return max(0, state.coins)


def _freed(_state: GameState) -> int:
    return INITIAL_FREED_LEMMINGS


def _weapon(_state: GameState) -> int:
    return INITIAL_WEAPON_COUNT


#: The ordered element list.  Append an element (with its own ``HudPart.order``
#: values) to add a fifth; nothing else hard-codes the count.
HUD_ELEMENTS: tuple[HudElement, ...] = (
    HudElement(
        "weapon",
        False,
        (
            HudPart(9, "Display.KLEI", "digits", (35, 41), (30, 41), _weapon),
            HudPart(
                9,
                "Icons.FUNF",
                "sprite",
                (27, 30),
                pose=_weapon_pose,
                dim=True,
            ),
        ),
        _weapon,
        note="icon Icons.FUNF dimmed (0xA0 arg, meaning [H]); selection/counts not live (FL15e)",
    ),
    HudElement(
        "lemmings",
        False,
        (
            HudPart(1, "Display.KLEI", "digits", (138, 41), (133, 41), _freed),
            HudPart(4, "Display.EINS", "sprite", (160, 51), stacked=True),
            HudPart(6, "Display.DREI", "sprite", (130, 51)),
        ),
        _freed,
        note="figure Display.DREI pose 0 + freed count + box Display.EINS; "
        "spare helmet (draw 5) not drawn: flag 0 in L1",
    ),
    HudElement(
        "coins",
        True,
        (
            HudPart(2, "Display.KLEI", "digits", (184, 41), (179, 41), _coins),
            HudPart(7, "Display.VIER", "sprite", (190, 51), pose=_spin),
        ),
        _coins,
        note="spinning coin Display.VIER + count (mod 100)",
    ),
    HudElement(
        "lives",
        True,
        (
            HudPart(3, "Display.GROS", "digits", (285, 43), (278, 43), _lives),
            HudPart(8, "Display.ZWEI", "sprite", (295, 51)),
        ),
        _lives,
        note="face Display.ZWEI (meaning [H]) + life count (mod 100)",
    ),
)


def required_clips(elements: Sequence[HudElement] = HUD_ELEMENTS) -> tuple[str, ...]:
    """Distinct clip keys the element list needs, first-use order."""
    seen: dict[str, None] = {}
    for el in elements:
        for part in el.parts:
            seen.setdefault(part.clip, None)
    return tuple(seen)


def digits(value: int) -> tuple[int | None, int]:
    """``(tens, units)`` of ``value`` mod 100; tens is ``None`` when zero."""
    value = abs(value) % 100
    tens = value // 10
    return (tens or None), value % 10


@dataclass(frozen=True)
class _Span:
    """An opaque horizontal run, offsets relative to the part origin."""

    rel_y: int
    rel_x: int
    words: tuple[int, ...]


class Hud:
    """Resolved HUD sprites plus the lazily compiled, palette-bound spans."""

    def __init__(
        self,
        clips: dict[str, HudClip],
        elements: tuple[HudElement, ...] = HUD_ELEMENTS,
    ) -> None:
        self.clips = clips
        self.elements = elements
        # Parts in the original's draw order (stable within equal order).
        self.parts = tuple(
            sorted(
                (p for el in elements for p in el.parts),
                key=lambda p: p.order,
            )
        )
        self._spans: dict[tuple, tuple[_Span, ...]] = {}
        self._palette: Palette565 | None = None

    # -- rendering ---------------------------------------------------------

    def _compile(self, clip: HudClip, pose_index: int, dim: bool, stacked: bool):
        palette = self._palette
        assert palette is not None
        key = (clip.key, pose_index, dim, stacked)
        hit = self._spans.get(key)
        if hit is not None:
            return hit
        layers: Pose
        if stacked:
            layers = tuple(layer for pose in clip.poses for layer in pose)
        else:
            layers = clip.poses[pose_index % len(clip.poses)]
        spans: list[_Span] = []
        for layer in layers:
            w = layer.width
            for row in range(layer.height):
                line = layer.indices[row * w : (row + 1) * w]
                x = 0
                while x < w:
                    if not line[x]:
                        x += 1
                        continue
                    start = x
                    while x < w and line[x]:
                        x += 1
                    words = tuple(palette.word(i) for i in line[start:x])
                    if dim:
                        words = tuple((wd >> 1) & DIM_MASK for wd in words)
                    spans.append(_Span(layer.dy + row, layer.dx + start, words))
        out = tuple(spans)
        self._spans[key] = out
        return out

    def draw(self, fb: Framebuffer, state: GameState, palette: Palette565) -> None:
        """Blit every part, last, in screen coordinates (camera-independent)."""
        if palette is not self._palette:
            self._palette = palette
            self._spans.clear()
        pix, vw, vh = fb.pixels, fb.width, fb.height
        tick = state.tick_count
        for part in self.parts:
            clip = self.clips[part.clip]
            if part.kind == "digits":
                assert part.source is not None
                tens, units = digits(part.source(state))
                if tens is not None and part.tens_origin is not None:
                    self._blit(pix, vw, vh, clip, tens, part.tens_origin, False, False)
                self._blit(pix, vw, vh, clip, units, part.origin, False, False)
            else:
                self._blit(
                    pix,
                    vw,
                    vh,
                    clip,
                    part.pose(tick),
                    part.origin,
                    part.dim,
                    part.stacked,
                )

    def _blit(self, pix, vw, vh, clip, pose_index, origin, dim, stacked) -> None:
        ox, oy = origin
        for span in self._compile(clip, pose_index, dim, stacked):
            y = oy + span.rel_y
            if not 0 <= y < vh:
                continue
            x = ox + span.rel_x
            words = span.words
            if x < 0:
                words = words[-x:]
                x = 0
            if x + len(words) > vw:
                words = words[: vw - x]
            if words:
                base = y * vw + x
                pix[base : base + len(words)] = words

    # -- reporting ---------------------------------------------------------

    def report(self, state: GameState) -> str:
        """The ``hud:`` block of the slice report."""
        live = sum(1 for el in self.elements if el.live)
        lines = [f"hud: {len(self.elements)} elements, {live} live"]
        for el in self.elements:
            xs = sorted({p.origin for p in el.parts})
            clips = ", ".join(sorted({p.clip for p in el.parts}))
            lines.append(
                f"  {el.name}: at {', '.join(f'({x}, {y})' for x, y in xs)}, "
                f"value {el.value(state) % 100}, clips {clips}, "
                f"positions [V] meaning {el.grade}, "
                f"{'live' if el.live else 'initial'}; {el.note}"
            )
        lines.append(
            "  digit -> pose mapping (pose = digit) [H]; face/box/greying meanings [H]; "
            "flash timer 0x52C700 and 50 Hz mode not modelled"
        )
        return "\n".join(lines)


NOT_DRAWN_NO_RECORDS = "hud: not drawn (no Display/Icons record)"


def hud_report(hud: Hud | None, state: GameState) -> str:
    """Report text for a level's HUD (resolved or not)."""
    if hud is None:
        return NOT_DRAWN_NO_RECORDS
    return hud.report(state)


def _resolve_clip(records, sprites, key: str, keyframe_layer) -> HudClip | None:
    record_name, tag = key.split(".")
    record = next((r for r in records if r.name == record_name), None)
    anim = (
        next((a for a in record.anims if anim_tag_name(a.tag).strip() == tag), None)
        if record is not None
        else None
    )
    if anim is None or not anim.frames:
        return None
    layers: list[HudSprite] = []
    for kf in anim.frames:  # one pose per keyframe [H] (pose index = keyframe)
        layer = keyframe_layer(sprites, kf)
        if layer is None:
            return None
        dx, dy, pixels = layer
        layers.append(
            HudSprite(dx, dy, pixels.width, pixels.height, tuple(pixels.indices))
        )
    return HudClip(record_name, tag, tuple((layer,) for layer in layers))


def hud_from_world(
    world: wld.World, elements: tuple[HudElement, ...] = HUD_ELEMENTS
) -> Hud | None:
    """Resolve every clip the elements need from a world's ``NMY``/``ANIM``."""
    from .level import _keyframe_layer

    nmy = next((c for c in world.chunks if c.tag == "NMY"), None)
    decoded = decode_nmy(nmy.payload) if nmy is not None else None
    if decoded is None:
        return None
    records = decoded[0]
    sprites = anim_clip.sprite_map(world)
    clips: dict[str, HudClip] = {}
    for key in required_clips(elements):
        clip = _resolve_clip(records, sprites, key, _keyframe_layer)
        if clip is None:
            return None
        clips[key] = clip
    return Hud(clips, elements)


def load_hud(main_world_path: str | Path) -> Hud | None:
    """The HUD from ``MAIN.WLD``, or ``None`` if the file/records are absent."""
    source = Path(main_world_path)
    if not source.is_file():
        return None
    try:
        world = wld.parse_file(source)
    except (OSError, wld.WLDError):
        return None
    return hud_from_world(world)
