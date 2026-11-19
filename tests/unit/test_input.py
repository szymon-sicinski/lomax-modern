"""Tests for the pure keyboard → ``Input`` mapping (``lomax_modern.input``).

No display and no pad are needed: the ``Keymap`` consumes keycodes, so every
case below is a plain function call over two sets.  The acceptance cases are
left/right exclusivity (both held ⇒ neutral), jump edge-triggering (held
without a fresh press ⇒ no jump) and the no-keys neutral ``Input``.
"""

from __future__ import annotations

import pytest

from lomax_modern.engine.entities import Input
from lomax_modern.input import (
    DEFAULT_KEYMAP,
    SDLK_LEFT,
    SDLK_RIGHT,
    SDLK_SPACE,
    SDLK_UP,
    SDLK_a,
    SDLK_d,
    SDLK_w,
    Keymap,
)


def _default() -> Keymap:
    return Keymap.default()


# ---------------------------------------------------------------------------
# No keys
# ---------------------------------------------------------------------------


def test_no_keys_is_neutral() -> None:
    assert _default().update((), ()) == Input()


def test_unknown_keys_are_neutral() -> None:
    # A keycode bound to nothing drives no axis, whether held or pressed.
    assert _default().update({0xFF}, {0xFF}) == Input()


# ---------------------------------------------------------------------------
# Left / right level-triggering and exclusivity
# ---------------------------------------------------------------------------


def test_left_held() -> None:
    assert _default().update({SDLK_LEFT}, ()) == Input(left=True)


def test_right_held() -> None:
    assert _default().update({SDLK_RIGHT}, ()) == Input(right=True)


def test_wasd_left_right() -> None:
    assert _default().update({SDLK_a}, ()) == Input(left=True)
    assert _default().update({SDLK_d}, ()) == Input(right=True)


def test_both_arrows_held_is_neutral() -> None:
    assert _default().update({SDLK_LEFT, SDLK_RIGHT}, ()) == Input()


def test_both_wasd_held_is_neutral() -> None:
    assert _default().update({SDLK_a, SDLK_d}, ()) == Input()


def test_opposite_sides_mixed_inputs_are_neutral() -> None:
    # Arrow on one side, WASD on the other: both sides held ⇒ neutral.
    assert _default().update({SDLK_LEFT, SDLK_d}, ()) == Input()
    assert _default().update({SDLK_a, SDLK_RIGHT}, ()) == Input()


# ---------------------------------------------------------------------------
# Jump edge-triggering
# ---------------------------------------------------------------------------


def test_jump_fires_on_press_edge() -> None:
    # The key is both held and freshly pressed this tick: jump is set.
    assert _default().update({SDLK_SPACE}, {SDLK_SPACE}) == Input(jump=True)


def test_jump_held_without_press_is_not_jump() -> None:
    # Held from a previous tick but no fresh press: no jump.
    assert _default().update({SDLK_SPACE}, ()) == Input()


def test_jump_pressed_only_is_jump() -> None:
    # A press edge even when the key is already back up is still a press.
    assert _default().update((), {SDLK_SPACE}) == Input(jump=True)


def test_every_jump_key_edge_triggers() -> None:
    for key in (SDLK_SPACE, SDLK_UP, SDLK_w):
        assert _default().update({key}, {key}) == Input(jump=True)


def test_non_jump_key_press_does_not_jump() -> None:
    # Holding jump while pressing a movement key: no jump edge.
    assert _default().update({SDLK_SPACE}, {SDLK_a}) == Input()


# ---------------------------------------------------------------------------
# Combined axes
# ---------------------------------------------------------------------------


def test_left_and_jump_together() -> None:
    assert _default().update({SDLK_LEFT}, {SDLK_SPACE}) == Input(left=True, jump=True)


def test_right_held_with_jump_pressed() -> None:
    assert _default().update({SDLK_RIGHT}, {SDLK_w}) == Input(right=True, jump=True)


# ---------------------------------------------------------------------------
# Keymap construction and immutability
# ---------------------------------------------------------------------------


def test_custom_bindings() -> None:
    keymap = Keymap(left={1}, right={2}, jump={3})
    assert keymap.update({1}, ()) == Input(left=True)
    assert keymap.update({2}, ()) == Input(right=True)
    assert keymap.update((), {3}) == Input(jump=True)


def test_bindings_are_coerced_to_frozenset() -> None:
    keymap = Keymap(left=[SDLK_LEFT], right=(SDLK_RIGHT,), jump={SDLK_SPACE})
    assert keymap.left == frozenset({SDLK_LEFT})
    assert keymap.right == frozenset({SDLK_RIGHT})
    assert keymap.jump == frozenset({SDLK_SPACE})
    # Frozen: reassigning a field raises.
    with pytest.raises(AttributeError):
        keymap.left = frozenset()  # type: ignore[misc]


def test_default_keymap_bindings() -> None:
    assert DEFAULT_KEYMAP.left == frozenset({SDLK_LEFT, SDLK_a})
    assert DEFAULT_KEYMAP.right == frozenset({SDLK_RIGHT, SDLK_d})
    assert DEFAULT_KEYMAP.jump == frozenset({SDLK_SPACE, SDLK_UP, SDLK_w})
    assert DEFAULT_KEYMAP == _default()


def test_update_accepts_any_iterable() -> None:
    # Lists, tuples, generators and sets all work for both arguments.
    keymap = _default()
    assert keymap.update([SDLK_LEFT], iter(())) == Input(left=True)
    assert keymap.update((SDLK_LEFT,), (SDLK_SPACE,)) == Input(left=True, jump=True)


def test_default_keymap_returns_neutral_for_empty_every_time() -> None:
    keymap = _default()
    for _ in range(3):
        assert keymap.update(set(), set()) == Input()
