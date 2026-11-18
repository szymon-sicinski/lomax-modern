"""Turn an engine frame into the surface the presenter hands to the display.

The pieces already exist: :mod:`lomax_modern.engine` produces a 16-bit
``B5G6R5`` frame at the original 320x240, :mod:`lomax_modern.scaler` owns
integer fitting and the two filters, and :mod:`lomax_modern.renderer` owns the
palette/blit path for decoded art.  This module is the seam between them: one
plan (source size, surface size, integer factor, filter) and one call that
produces the padded surface.

Two properties are deliberate:

* **Plan once, present with the same numbers.**  :func:`plan_presentation`
  computes the fit and validates an explicitly pinned factor against it, so a
  request for 6x on a 1080p surface fails *before* any pixel is produced.  The
  surface geometry in the report is therefore the geometry that was actually
  used, not a second guess.
* **The filter is a runtime argument, not a build-time constant.**  The profile
  in :mod:`lomax_modern.config` only chooses a *default*; :func:`present_frame`
  takes the filter from the plan, so switching it re-filters the same frame
  through the same path.

The frame may be an :class:`lomax_modern.engine.Frame` (a ``pixels`` list) or a
:class:`lomax_modern.renderer.Framebuffer` (which exposes ``to_image()``); both
are ``RGB565``.  The current ``present`` command feeds the engine's geometric
frame, because composing decoded tile art into a world view still needs the
unresolved ``MAP`` cell -> ``TTAB`` record link (Q20); inventing that link to
look more finished would violate the repository's own rule.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import scaler
from .config import PresentSettings
from .scaler import Filter, Fit, Image, Mode

__all__ = [
    "PresentPlan",
    "PresentationError",
    "image_from_frame",
    "image_to_rgba",
    "plan_presentation",
    "present_frame",
]


class PresentationError(ValueError):
    """The requested presentation cannot be produced as specified."""


@dataclass(frozen=True, slots=True)
class PresentPlan:
    """The exact geometry ``present`` will use for one source frame."""

    settings: PresentSettings
    source: tuple[int, int]
    fit: Fit
    filter: Filter

    @property
    def surface(self) -> tuple[int, int]:
        return self.settings.surface

    def describe(self) -> tuple[str, ...]:
        """Human-readable, deterministic settings block for the CLI report."""
        fit = self.fit
        pinned = self.settings.scale is not None
        scale_note = "fixed by --scale" if pinned else "auto: largest integer fit"
        authentic_note = "on" if not self.settings.modern else "off"
        lines = [
            f"profile: {self.settings.profile_name} "
            f"(authentic toggle: {authentic_note})",
            f"filter: {self.filter.value} (runtime switch: "
            f"--filter {'|'.join(item.value for item in Filter)})",
            f"source: {self.source[0]}x{self.source[1]} (engine frame)",
            f"surface: {self.surface[0]}x{self.surface[1]}",
            f"scale: {fit.scale}x ({scale_note})",
            f"content: {fit.content_width}x{fit.content_height} at "
            f"+{fit.offset_x}+{fit.offset_y}; pads left {fit.pad_left}, "
            f"right {fit.pad_right}, top {fit.pad_top}, bottom {fit.pad_bottom}",
        ]
        if fit.scale == 1 and self.filter is not Filter.NEAREST:
            lines.append("note: the filter has no effect at 1x (nothing is scaled)")
        return tuple(lines)


def plan_presentation(
    settings: PresentSettings,
    source_width: int,
    source_height: int,
) -> PresentPlan:
    """Compute the integer fit for ``settings`` and reject an impossible pin.

    ``settings.scale = None`` selects the largest integer factor that fits both
    axes.  An explicit factor must fit exactly: silently shrinking it would
    make the report (and the screenshot) disagree with the config.
    """
    surface_width, surface_height = settings.surface
    try:
        fit = scaler.fit_scale(
            source_width,
            source_height,
            surface_width,
            surface_height,
            max_scale=settings.scale,
        )
    except ValueError as exc:
        raise PresentationError(str(exc)) from None

    if settings.scale is not None and fit.scale != settings.scale:
        largest = min(surface_width // source_width, surface_height // source_height)
        raise PresentationError(
            f"scale {settings.scale}x does not fit {source_width}x{source_height} "
            f"on a {surface_width}x{surface_height} surface; the largest integer "
            f"fit is {largest}x (use --scale {largest} or --scale auto)"
        )

    return PresentPlan(
        settings=settings,
        source=(source_width, source_height),
        fit=fit,
        filter=Filter(settings.filter),
    )


def image_from_frame(frame: object) -> Image:
    """Freeze an engine ``Frame`` or renderer ``Framebuffer`` as a scaler image.

    The renderer's buffer exposes ``to_image()``; the engine's frame exposes
    ``pixels``.  The fallback also accepts any object with integer
    ``width``/``height`` and a ``pixels`` sequence, so a test double does not
    need to import the engine.  Only ``B5G6R5`` content is accepted — a
    palettised buffer has no single meaning without its palette and must be
    expanded by the caller.
    """
    to_image = getattr(frame, "to_image", None)
    if isinstance(frame, Image):
        image = frame
    elif callable(to_image):
        image = to_image()
        if not isinstance(image, Image):
            raise PresentationError("frame.to_image() did not return a scaler Image")
    else:
        width = getattr(frame, "width", None)
        height = getattr(frame, "height", None)
        pixels = getattr(frame, "pixels", None)
        if not isinstance(width, int) or not isinstance(height, int) or pixels is None:
            raise PresentationError(
                "frame must expose to_image(), or integer width/height plus pixels"
            )
        try:
            image = Image(Mode.RGB565, width, height, tuple(pixels))
        except ValueError as exc:
            raise PresentationError(f"frame is not a valid RGB565 buffer: {exc}") from None

    if image.mode is not Mode.RGB565:
        raise PresentationError(
            f"present needs a B5G6R5 frame, got {image.mode.value}; "
            "palettised frames must be expanded through their palette first"
        )
    return image


def present_frame(frame: object, plan: PresentPlan) -> scaler.Presentation:
    """Scale and centre ``frame`` exactly as ``plan`` specifies."""
    image = image_from_frame(frame)
    size = (image.width, image.height)
    if size != plan.source:
        raise PresentationError(
            f"plan is for a {plan.source[0]}x{plan.source[1]} frame, got "
            f"{size[0]}x{size[1]}"
        )
    surface_width, surface_height = plan.surface
    presentation = scaler.present(
        image,
        surface_width,
        surface_height,
        filter=plan.filter,
        max_scale=plan.settings.scale,
    )
    if presentation.fit.scale != plan.fit.scale:
        raise PresentationError(
            f"internal: fit changed between plan ({plan.fit.scale}x) and present "
            f"({presentation.fit.scale}x)"
        )
    return presentation


def image_to_rgba(image: Image) -> bytes:
    """Convert a ``B5G6R5`` image to 8-bit RGBA bytes for the PNG writer.

    Channels are widened by bit replication (5->8, 6->8), the inverse of the
    narrowing in :func:`lomax_modern.engine.render.pack_rgb565`, so the PNG
    carries the same colour the surface would.
    """
    if image.mode is not Mode.RGB565:
        raise PresentationError("only an RGB565 surface can be written as RGBA here")
    out = bytearray(len(image.pixels) * 4)
    for position, word in enumerate(image.pixels):
        red = (word >> 11) & 0x1F
        green = (word >> 5) & 0x3F
        blue = word & 0x1F
        base = position * 4
        out[base] = (red << 3) | (red >> 2)
        out[base + 1] = (green << 2) | (green >> 2)
        out[base + 2] = (blue << 3) | (blue >> 2)
        out[base + 3] = 255
    return bytes(out)
