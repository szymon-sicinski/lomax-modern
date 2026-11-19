"""Pure keyboard → :class:`~lomax_modern.engine.entities.Input` mapping.

The keyboard half of M5 (``docs/roadmap/10-milestones.md`` §M5).  The plan
(``docs/roadmap/45-playable-level-plan.md`` §1.1) scopes *keyboard only* for
this milestone — gamepad, hot-plug, per-controller presets and rebinding are
deferred.  A :class:`Keymap` is therefore a pure function of two keycode
sets: it reads no SDL events and depends on no SDL library, so it is
unit-testable with no display and no pad attached.

The keycodes are SDL *keysym* values (``SDL_keycode.h``) — the same values
``sdl_window._decode_event`` already yields.  A caller maintains two sets per
tick:

* ``held`` — every keycode currently down, and
* ``pressed`` — the keycodes whose ``SDL_KEYDOWN`` arrived *this tick* (the
  press edge).

:meth:`Keymap.update` folds those two sets into one
:class:`~lomax_modern.engine.entities.Input`.  ``left``/``right`` are
level-triggered and mutually exclusive (both held ⇒ neutral), while ``jump``
is *edge-triggered*: it is set only from ``pressed``, so a held jump key does
not re-jump on landing — the exact ``Input.jump`` contract
(``engine/entities.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .engine.entities import Input

#: SDL keysym values for the keys the default mapping binds.  These are
#: SDL2's public ``SDL_keycode.h`` constants (a system library, not game
#: data); letters are their ASCII values and the arrows are the scancode
#: ``| 0x40000000`` encoding.  Pinned here as plain ints so the mapping stays
#: free of any SDL import.
SDLK_SPACE = 0x20  # 32
SDLK_a = 0x61  # 97
SDLK_d = 0x64  # 100
SDLK_w = 0x77  # 119
SDLK_UP = 0x40000052  # 1073741906
SDLK_DOWN = 0x40000051  # 1073741905
SDLK_LEFT = 0x40000050  # 1073741904
SDLK_RIGHT = 0x4000004F  # 1073741903

__all__ = [
    "DEFAULT_KEYMAP",
    "Keymap",
    "SDLK_DOWN",
    "SDLK_LEFT",
    "SDLK_RIGHT",
    "SDLK_SPACE",
    "SDLK_UP",
    "SDLK_a",
    "SDLK_d",
    "SDLK_w",
]


@dataclass(frozen=True)
class Keymap:
    """Bindings from keycodes to the ``Input`` axes.

    ``left``/``right``/``jump`` are keycode sets.  ``update`` is level
    (``left``/``right``) and edge (``jump``) triggered as documented at the
    module level.  Constructing one with lists or sets coerces them to
    ``frozenset`` so the value stays hashable and immutable.
    """

    left: frozenset[int] = field(default_factory=frozenset)
    right: frozenset[int] = field(default_factory=frozenset)
    jump: frozenset[int] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        for name in ("left", "right", "jump"):
            binding = getattr(self, name)
            if not isinstance(binding, frozenset):
                object.__setattr__(self, name, frozenset(binding))

    @classmethod
    def default(cls) -> "Keymap":
        """Arrow keys and WASD, with Space / Up / W as jump."""
        return cls(
            left=(SDLK_LEFT, SDLK_a),
            right=(SDLK_RIGHT, SDLK_d),
            jump=(SDLK_SPACE, SDLK_UP, SDLK_w),
        )

    def update(self, held: Iterable[int], pressed: Iterable[int]) -> Input:
        """One tick of :class:`Input` from the held and pressed keycodes.

        ``held`` is every keycode currently down; ``pressed`` is the subset
        whose press landed this tick.  ``left``/``right`` are set when only
        one side is held (both ⇒ neutral); ``jump`` is set only when a jump
        key appears in ``pressed``, so holding it never re-triggers a jump.
        """
        held_keys = frozenset(held)
        pressed_keys = frozenset(pressed)
        left_held = bool(self.left & held_keys)
        right_held = bool(self.right & held_keys)
        return Input(
            left=left_held and not right_held,
            right=right_held and not left_held,
            jump=bool(self.jump & pressed_keys),
        )


#: The arrow-keys-and-WASD layout, shared by the ``play`` presenter (P4).
DEFAULT_KEYMAP = Keymap.default()
