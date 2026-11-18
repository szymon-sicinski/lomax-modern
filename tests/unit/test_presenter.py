"""Tests for the plan/present seam between the engine frame and the scaler.

The geometry is asserted exactly (integer factor, centred content, explicit
pads) and the two filters are compared on the same synthetic frame, because
"the filter is switchable at runtime" is only meaningful if the pixels change.
"""

from __future__ import annotations

import pytest

from lomax_modern.config import PresentSettings
from lomax_modern.engine.render import Frame
from lomax_modern.presenter import (
    PresentationError,
    image_from_frame,
    image_to_rgba,
    plan_presentation,
    present_frame,
)
from lomax_modern.renderer import Framebuffer
from lomax_modern.scaler import Filter, Image, Mode


def _diagonal() -> Image:
    """A 5x5 red diagonal on blue: an edge EPX can see and nearest cannot round."""
    pixels = tuple(0xF800 if x == y else 0x001F for y in range(5) for x in range(5))
    return Image(Mode.RGB565, 5, 5, pixels)


def test_modern_plan_on_1080p_fits_4x_with_pillarbox_and_letterbox() -> None:
    plan = plan_presentation(PresentSettings(), 320, 240)

    assert plan.filter is Filter.EPX_AA
    assert plan.fit.scale == 4
    assert (plan.fit.content_width, plan.fit.content_height) == (1280, 960)
    assert (plan.fit.offset_x, plan.fit.offset_y) == (320, 60)
    assert (plan.fit.pad_left, plan.fit.pad_right) == (320, 320)
    assert (plan.fit.pad_top, plan.fit.pad_bottom) == (60, 60)
    assert plan.fit.pillarbox and plan.fit.letterbox


def test_authentic_plan_is_native_scale_one() -> None:
    plan = plan_presentation(PresentSettings().with_profile(False), 320, 240)

    assert plan.filter is Filter.NEAREST
    assert plan.fit.scale == 1
    assert (plan.fit.pad_left, plan.fit.pad_right) == (0, 0)
    assert (plan.fit.pad_top, plan.fit.pad_bottom) == (0, 0)


def test_explicit_scale_is_honoured_when_it_fits() -> None:
    settings = PresentSettings(surface=(1920, 1080), scale=2)

    plan = plan_presentation(settings, 320, 240)

    assert plan.fit.scale == 2
    assert (plan.fit.offset_x, plan.fit.offset_y) == (640, 300)


def test_explicit_scale_that_does_not_fit_is_refused_not_shrunk() -> None:
    settings = PresentSettings(surface=(1920, 1080), scale=6)

    with pytest.raises(PresentationError) as caught:
        plan_presentation(settings, 320, 240)

    message = str(caught.value)
    assert "scale 6x does not fit" in message
    assert "largest integer fit is 4x" in message


def test_surface_too_small_for_any_integer_fit_is_refused() -> None:
    settings = PresentSettings(surface=(200, 100))

    with pytest.raises(PresentationError, match="does not fit"):
        plan_presentation(settings, 320, 240)


def test_plan_description_states_profile_filter_and_geometry() -> None:
    lines = "\n".join(plan_presentation(PresentSettings(), 320, 240).describe())

    assert "profile: modern (authentic toggle: off)" in lines
    assert "filter: epx-aa" in lines
    assert "surface: 1920x1080" in lines
    assert "scale: 4x (auto: largest integer fit)" in lines
    assert "pads left 320, right 320, top 60, bottom 60" in lines

    authentic = "\n".join(
        plan_presentation(PresentSettings().with_profile(False), 320, 240).describe()
    )
    assert "profile: authentic (authentic toggle: on)" in authentic
    assert "filter: nearest" in authentic
    assert "scale: 1x" in authentic


def test_filter_at_one_x_is_reported_as_a_no_op() -> None:
    filtered = plan_presentation(
        PresentSettings(surface=(320, 240), filter=Filter.EPX_AA), 320, 240
    )
    text = "\n".join(filtered.describe())

    assert "scale: 1x" in text
    assert "the filter has no effect at 1x" in text

    plain = plan_presentation(
        PresentSettings(surface=(320, 240), filter=Filter.NEAREST), 320, 240
    )
    assert "note:" not in "\n".join(plain.describe())


def test_engine_frame_and_renderer_framebuffer_are_both_accepted() -> None:
    frame = Frame(2, 2, fill=0x1234)
    frame.set(1, 1, 0xABCD)

    engine_image = image_from_frame(frame)
    assert engine_image.mode is Mode.RGB565
    assert engine_image.pixels == (0x1234, 0x1234, 0x1234, 0xABCD)

    buffer = Framebuffer(2, 2, fill=0x1234)
    buffer.set(1, 1, 0xABCD)
    renderer_image = image_from_frame(buffer)
    assert renderer_image == engine_image


def test_indexed_image_is_refused_with_an_explanation() -> None:
    indexed = Image(Mode.INDEXED8, 2, 2, (1, 2, 3, 4))

    with pytest.raises(PresentationError, match="palettised"):
        image_from_frame(indexed)


def test_present_frame_places_content_and_pads() -> None:
    frame = Frame(4, 3, fill=0x07E0)
    frame.set(0, 0, 0xF800)
    plan = plan_presentation(PresentSettings(surface=(10, 8)), 4, 3)

    presentation = present_frame(frame, plan)

    surface = presentation.surface
    assert (surface.width, surface.height) == (10, 8)
    assert presentation.fit.scale == 2
    # Pad pixel is black, content starts at (1, 1), source (0, 0) is red.
    assert surface.at(0, 0) == 0
    assert surface.at(1, 1) == 0xF800
    assert surface.at(2, 2) == 0xF800
    assert surface.at(3, 3) == 0x07E0


def test_filter_switch_changes_pixels_of_the_same_frame() -> None:
    image = _diagonal()
    nearest = plan_presentation(
        PresentSettings(surface=(20, 20), filter=Filter.NEAREST), 5, 5
    )
    filtered = plan_presentation(
        PresentSettings(surface=(20, 20), filter=Filter.EPX_AA), 5, 5
    )

    assert nearest.fit.scale == filtered.fit.scale == 4
    plain = present_frame(image, nearest).surface
    smooth = present_frame(image, filtered).surface

    assert plain.pixels != smooth.pixels
    # The filter may smooth the corner but must not erase the diagonal's colour
    # counts into a single blob: both source colours survive.
    assert 0xF800 in smooth.pixels and 0x001F in smooth.pixels


def test_present_frame_rejects_a_frame_of_the_wrong_size() -> None:
    plan = plan_presentation(PresentSettings(surface=(640, 480)), 320, 240)

    with pytest.raises(PresentationError, match="plan is for a 320x240 frame"):
        present_frame(Frame(40, 30), plan)


def test_image_to_rgba_expands_channels() -> None:
    image = Image(
        Mode.RGB565,
        3,
        1,
        (0xF800, 0x07E0, 0x001F),
    )

    assert image_to_rgba(image) == bytes(
        (
            255, 0, 0, 255,
            0, 255, 0, 255,
            0, 0, 255, 255,
        )
    )


def test_image_to_rgba_expands_mid_tone_green_by_replication() -> None:
    """Green is 6 bits: 6->8 must be ``(g << 2) | (g >> 4)``, not ``>> 2``.

    Full-scale green (0x07E0, g = 63) agrees under both formulas, so the
    channel test above cannot see the difference; mid-tones can.  g = 4 -> 65
    (>>2 would give 68), and the whole channel is checked against the rule.
    """
    assert image_to_rgba(Image(Mode.RGB565, 1, 1, (0x0200,))) == bytes((0, 65, 0, 255))

    for g6 in range(64):
        assert image_to_rgba(Image(Mode.RGB565, 1, 1, (g6 << 5,))) == bytes(
            (0, (g6 << 2) | (g6 >> 4), 0, 255)
        ), g6


def test_image_to_rgba_refuses_a_non_rgb565_buffer() -> None:
    with pytest.raises(PresentationError, match="RGB565"):
        image_to_rgba(Image(Mode.INDEXED8, 1, 1, (0,)))
